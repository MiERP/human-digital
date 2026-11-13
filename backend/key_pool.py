import os
import json
import time
import logging
import threading
import hashlib
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("digital-human-backend")

def key_id(key: str) -> str:
    """Opaque identifier used to keep a resumed session on its original API key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

class KeyInfo:
    """Đại diện cho trạng thái của 1 Google Gemini API Key trong Pool."""
    def __init__(self, key: str, source: str = "env"):
        self.key: str = key.strip()
        self.source: str = source  # "env" = từ GEMINI_API_KEY(S), "file" = thêm qua admin
        self.active_connections: int = 0
        self.total_sessions: int = 0
        self.consecutive_errors: int = 0
        self.cooldown_until: float = 0.0
        self.last_used_at: float = 0.0
        self.is_healthy: bool = True

    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def masked_key(self) -> str:
        if len(self.key) <= 10:
            return self.key[:3] + "..." + self.key[-3:] if len(self.key) >= 6 else "***"
        return f"{self.key[:8]}...{self.key[-4:]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": key_id(self.key),
            "masked_key": self.masked_key,
            "source": self.source,
            "active_connections": self.active_connections,
            "total_sessions": self.total_sessions,
            "consecutive_errors": self.consecutive_errors,
            "is_in_cooldown": self.is_in_cooldown,
            "cooldown_remaining_sec": max(0, int(self.cooldown_until - time.time())),
            "is_healthy": self.is_healthy
        }

class KeyPoolManager:
    """
    Quản lý cân bằng tải nhiều Gemini API Key (Dynamic Key Pool Load Balancer):
    - Thuật toán Least-Active-Connections: Chọn key đang có ít kết nối nhất.
    - Tự động Cooldown & Failover khi gặp lỗi 429 Quota Exceeded.
    - Hỗ trợ BYOK (Bring Your Own Key) từ client.
    - Thread-safe 100%.
    """
    def __init__(self, raw_keys: Optional[str] = None, storage_path: Optional[str] = None):
        self._lock = threading.Lock()
        self._pool: List[KeyInfo] = []
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.storage_path = storage_path or os.getenv(
            "GEMINI_KEYS_FILE", os.path.join(base_dir, "data", "gemini_keys.json")
        )
        self.reload_keys(raw_keys)

    @staticmethod
    def _parse_keys(raw_keys: Optional[str]) -> List[str]:
        """Tách chuỗi key theo dấu phẩy, chấm phẩy hoặc xuống dòng và loại placeholder."""
        if not raw_keys:
            return []
        key_strings = [raw_keys]
        for delimiter in [",", ";", "\n"]:
            expanded: List[str] = []
            for chunk in key_strings:
                expanded.extend(chunk.split(delimiter))
            key_strings = expanded

        cleaned: List[str] = []
        for raw in key_strings:
            key = raw.strip()
            if (
                key
                and not key.startswith("AIzaSy_YOUR_GEMINI")
                and not key.startswith("YOUR_")
                and len(key) >= 15
                and key not in cleaned
            ):
                cleaned.append(key)
        return cleaned

    def _load_persisted_keys(self) -> List[str]:
        """Đọc các key được thêm từ trang admin trong data/gemini_keys.json."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return []
        except Exception as exc:
            logger.warning(f"Cannot read persisted Gemini keys from {self.storage_path}: {exc}")
            return []

        if isinstance(payload, dict):
            raw = payload.get("keys", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []
        if not isinstance(raw, list):
            return []
        return self._parse_keys("\n".join(str(item) for item in raw))

    def _persist_file_keys(self) -> None:
        """Lưu bền các key thêm qua admin; không ghi key từ .env vào file."""
        file_keys = [info.key for info in self._pool if info.source == "file"]
        try:
            parent = os.path.dirname(self.storage_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump({"keys": file_keys}, handle, ensure_ascii=False, indent=2)
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, self.storage_path)
        except Exception as exc:
            logger.error(f"Cannot persist Gemini keys to {self.storage_path}: {exc}")

    def reload_keys(self, raw_keys: Optional[str] = None):
        """Nạp keys từ đối số (test), hoặc từ env + file data/gemini_keys.json (production)."""
        with self._lock:
            if raw_keys is not None:
                env_keys = self._parse_keys(raw_keys)
                file_keys: List[str] = []
            else:
                env_raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""
                env_keys = self._parse_keys(env_raw)
                file_keys = self._load_persisted_keys()

            previous = {info.key: info for info in self._pool}
            pool: List[KeyInfo] = []
            seen: set[str] = set()

            for key in env_keys:
                if key in seen:
                    continue
                seen.add(key)
                info = previous.get(key) or KeyInfo(key, source="env")
                info.source = "env"
                pool.append(info)

            for key in file_keys:
                if key in seen:
                    continue
                seen.add(key)
                info = previous.get(key) or KeyInfo(key, source="file")
                info.source = "file"
                pool.append(info)

            self._pool = pool
            logger.info(
                f"KeyPoolManager initialized with {len(self._pool)} valid Gemini API key(s) "
                f"(env={len(env_keys)}, file={len(file_keys)})."
            )

    def add_key(self, key: str) -> Tuple[bool, str]:
        """Thêm key từ trang admin và lưu bền vào data/gemini_keys.json."""
        cleaned = (key or "").strip()
        if not cleaned or cleaned.startswith("YOUR_") or len(cleaned) < 15:
            return False, "API key không hợp lệ (quá ngắn hoặc là placeholder)."

        with self._lock:
            if any(info.key == cleaned for info in self._pool):
                return False, "API key này đã có trong Key Pool."
            info = KeyInfo(cleaned, source="file")
            self._pool.append(info)
            self._persist_file_keys()
            logger.info(f"Admin added Gemini key [{info.masked_key}] (id={key_id(cleaned)}).")
            return True, "Đã thêm API key vào Key Pool."

    def remove_key(self, identifier: str) -> Tuple[bool, str]:
        """Xóa key do admin thêm. Key từ .env phải sửa trong .env rồi restart."""
        target = (identifier or "").strip()
        if not target:
            return False, "Thiếu mã key cần xóa."

        with self._lock:
            info = next(
                (item for item in self._pool
                 if key_id(item.key) == target or item.key == target),
                None,
            )
            if info is None:
                return False, "Không tìm thấy API key trong Key Pool."
            if info.source == "env":
                return False, "Key này được nạp từ .env; hãy sửa .env và restart container."
            self._pool.remove(info)
            self._persist_file_keys()
            logger.info(f"Admin removed Gemini key [{info.masked_key}] (id={key_id(info.key)}).")
            return True, "Đã xóa API key khỏi Key Pool."

    @property
    def total_keys(self) -> int:
        with self._lock:
            return len(self._pool)

    def acquire_key(self, client_api_key: Optional[str] = None,
                    preferred_key_id: Optional[str] = None) -> Optional[str]:
        """
        Lấy API key tối ưu cho một phiên kết nối mới:
        - Nếu client cung cấp key riêng hợp lệ -> Sử dụng key riêng đó (BYOK).
        - Nếu dùng Server Pool: Chọn key không trong cooldown có active_connections thấp nhất.
        """
        # 1. Xử lý BYOK từ client
        if client_api_key and isinstance(client_api_key, str) and client_api_key.strip():
            c_key = client_api_key.strip()
            if not c_key.startswith("AIzaSy_YOUR_") and len(c_key) >= 15:
                logger.info(f"Using Client BYOK Gemini Key: {c_key[:8]}...")
                return c_key

        with self._lock:
            if not self._pool:
                logger.warning("KeyPoolManager has no available API keys in pool!")
                return None

            now = time.time()
            if preferred_key_id:
                preferred = next((k for k in self._pool
                                  if key_id(k.key) == preferred_key_id
                                  and now >= k.cooldown_until), None)
                if preferred is not None:
                    preferred.active_connections += 1
                    preferred.total_sessions += 1
                    preferred.last_used_at = now
                    return preferred.key
            # Lọc các key sẵn sàng (không trong cooldown)
            available_keys = [k for k in self._pool if now >= k.cooldown_until]

            # Nếu tất cả các key đều đang trong cooldown -> Chọn key có cooldown_until nhỏ nhất
            if not available_keys:
                logger.warning("All Gemini keys are currently in cooldown! Selecting key with earliest recovery...")
                chosen = min(self._pool, key=lambda k: k.cooldown_until)
            else:
                # Thuật toán Least-Active-Connections kết hợp Least-Total-Sessions
                chosen = min(available_keys, key=lambda k: (k.active_connections, k.total_sessions))

            chosen.active_connections += 1
            chosen.total_sessions += 1
            chosen.last_used_at = now
            logger.info(f"Assigned Gemini Key [{chosen.masked_key}] for new session (Active on this key: {chosen.active_connections})")
            return chosen.key

    def release_key(self, key_str: Optional[str]):
        """Giải phóng 1 kết nối khỏi key khi phiên kết thúc."""
        if not key_str:
            return
        with self._lock:
            for k in self._pool:
                if k.key == key_str:
                    k.active_connections = max(0, k.active_connections - 1)
                    logger.debug(f"Released connection for key [{k.masked_key}]. Active now: {k.active_connections}")
                    break

    def report_quota_error(self, key_str: Optional[str], cooldown_seconds: float = 60.0):
        """Báo cáo lỗi 429 Quota Exceeded / Rate Limit cho key để tạm ngưng trong cooldown_seconds."""
        if not key_str:
            return
        with self._lock:
            for k in self._pool:
                if k.key == key_str:
                    k.consecutive_errors += 1
                    k.cooldown_until = time.time() + cooldown_seconds
                    k.is_healthy = False
                    logger.warning(f"🚨 Key [{k.masked_key}] hit 429 Quota Limit! Placed in cooldown for {int(cooldown_seconds)}s.")
                    break

    def report_success(self, key_str: Optional[str]):
        """Báo cáo key hoạt động bình thường."""
        if not key_str:
            return
        with self._lock:
            for k in self._pool:
                if k.key == key_str:
                    k.consecutive_errors = 0
                    k.is_healthy = True
                    break

    def get_pool_status(self) -> Dict[str, Any]:
        """Trả về báo cáo tình trạng toàn bộ Key Pool cho Monitoring / Health Check."""
        with self._lock:
            total_active = sum(k.active_connections for k in self._pool)
            healthy_count = sum(1 for k in self._pool if not k.is_in_cooldown)
            return {
                "total_keys": len(self._pool),
                "healthy_keys": healthy_count,
                "total_active_connections": total_active,
                "keys_detail": [k.to_dict() for k in self._pool]
            }

# Singleton instance
key_pool = KeyPoolManager()
