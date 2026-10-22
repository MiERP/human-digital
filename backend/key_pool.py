import os
import time
import logging
import threading
import hashlib
from typing import Optional, List, Dict, Any

logger = logging.getLogger("digital-human-backend")

def key_id(key: str) -> str:
    """Opaque identifier used to keep a resumed session on its original API key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

class KeyInfo:
    """Đại diện cho trạng thái của 1 Google Gemini API Key trong Pool."""
    def __init__(self, key: str):
        self.key: str = key.strip()
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
            "masked_key": self.masked_key,
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
    def __init__(self, raw_keys: Optional[str] = None):
        self._lock = threading.Lock()
        self._pool: List[KeyInfo] = []
        self.reload_keys(raw_keys)

    def reload_keys(self, raw_keys: Optional[str] = None):
        """Nạp danh sách keys từ đối số hoặc biến môi trường GEMINI_API_KEYS / GEMINI_API_KEY."""
        with self._lock:
            if raw_keys is None:
                raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""

            # Tách chuỗi theo dấu phẩy, chấm phẩy hoặc xuống dòng
            delimiters = [",", ";", "\n"]
            key_strings = [raw_keys]
            for d in delimiters:
                new_list = []
                for s in key_strings:
                    new_list.extend(s.split(d))
                key_strings = new_list

            cleaned_keys = []
            for k in key_strings:
                k_clean = k.strip()
                if (k_clean 
                    and not k_clean.startswith("AIzaSy_YOUR_GEMINI") 
                    and not k_clean.startswith("YOUR_")
                    and len(k_clean) >= 15):
                    if k_clean not in cleaned_keys:
                        cleaned_keys.append(k_clean)

            # Khởi tạo danh sách KeyInfo
            self._pool = [KeyInfo(k) for k in cleaned_keys]
            logger.info(f"KeyPoolManager initialized with {len(self._pool)} valid Gemini API key(s).")

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
