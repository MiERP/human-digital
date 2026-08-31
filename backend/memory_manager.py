import os
import json
import sqlite3
import secrets
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, date, timedelta

logger = logging.getLogger("digital-human-memory")

class MemoryManager:
    """
    Production-grade Child Memory System:
    - Lưu trữ hồ sơ cố định của bé (Core Profile)
    - Ghi nhận kỷ niệm & sự kiện theo từng buổi (Episodic Memory)
    - Theo dõi tiến độ học tập từ vựng/ngữ pháp (Learning Tracker)
    - Tuân thủ quyền riêng tư dữ liệu trẻ em (COPPA / GDPR-K: Export & Delete)
    - Tự động nạp Context tối ưu vào System Prompt của Gemini Live
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "child_memory.db")
        
        self.db_path = db_path
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Kích hoạt WAL mode để tối ưu đọc/ghi đồng thời
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_database(self):
        """Khởi tạo cấu trúc bảng cơ sở dữ liệu nếu chưa tồn tại"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Bảng hồ sơ cốt lõi của bé (Core Profile)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS child_profile (
                    child_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    nickname TEXT,
                    age INTEGER,
                    gender TEXT,
                    grade TEXT,
                    favorite_color TEXT,
                    favorite_animal TEXT,
                    favorite_food TEXT,
                    favorite_character TEXT,
                    family_info TEXT, -- JSON format: {"mom": "Hoa", "dad": "Minh", "pet": "Cat Miu"}
                    hobbies TEXT,     -- JSON array: ["drawing", "swimming", "dinosaurs"]
                    learning_level TEXT DEFAULT 'Starters',
                    personality TEXT, -- Mô tả tính cách / phong cách giao tiếp của bé
                    parent_pin TEXT DEFAULT '1234', -- Mã PIN 4 số bảo vệ Góc Phụ Huynh trên thiết bị
                    profile_completed INTEGER DEFAULT 0, -- 1 khi phụ huynh đã điền xong màn setup
                    streak_days INTEGER DEFAULT 0,       -- Chuỗi ngày học liên tiếp (Gamification)
                    last_active_date TEXT,               -- Ngày học gần nhất (YYYY-MM-DD)
                    total_sessions_count INTEGER DEFAULT 0, -- Tổng số phiên trò chuyện
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migration: thêm các cột mới cho DB đã tồn tại từ phiên bản cũ.
            cursor.execute("PRAGMA table_info(child_profile);")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            if "personality" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN personality TEXT;")
            if "parent_pin" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN parent_pin TEXT DEFAULT '1234';")
            if "gender" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN gender TEXT;")
            if "profile_completed" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN profile_completed INTEGER DEFAULT 0;")
            if "streak_days" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN streak_days INTEGER DEFAULT 0;")
            if "last_active_date" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN last_active_date TEXT;")
            if "total_sessions_count" not in existing_columns:
                cursor.execute("ALTER TABLE child_profile ADD COLUMN total_sessions_count INTEGER DEFAULT 0;")

            # 2. Bảng kỷ niệm thường ngày (Episodic Memories)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id TEXT NOT NULL,
                    category TEXT NOT NULL, -- DAILY_STORY, EMOTION, ACHIEVEMENT, FRIEND_FAMILY
                    content TEXT NOT NULL,
                    emotional_tag TEXT,     -- happy, excited, proud, sad, tired
                    importance INTEGER DEFAULT 3, -- 1 (nhỏ) -> 5 (rất quan trọng)
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES child_profile (child_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_child ON episodic_memories(child_id, created_at);")

            # 3. Bảng theo dõi tiến độ học tiếng Anh (Learning Progress Tracker)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id TEXT NOT NULL,
                    topic TEXT NOT NULL,     -- Animals, Colors, Food, School, Family
                    mastered_words TEXT,     -- JSON array: ["cat", "dog", "elephant"]
                    needs_practice TEXT,     -- JSON array: ["giraffe", "crocodile"]
                    mastery_score INTEGER DEFAULT 0, -- 0 -> 100%
                    last_practiced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES child_profile (child_id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_child_topic ON learning_progress(child_id, topic);")

            # 4. Bảng nhật ký phiên học (Session Logs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id TEXT NOT NULL,
                    session_topic TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES child_profile (child_id) ON DELETE CASCADE
                );
            """)

            # 5. Bảng đăng ký thiết bị & quản lý khóa chặn phần cứng (Device Registry & Ban Engine)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_registry (
                    device_fingerprint TEXT PRIMARY KEY,
                    child_id TEXT NOT NULL,
                    device_model TEXT,
                    android_version TEXT,
                    app_version TEXT,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_ip TEXT,
                    is_blocked INTEGER DEFAULT 0,
                    block_reason TEXT,
                    total_sessions INTEGER DEFAULT 0,
                    total_duration_sec INTEGER DEFAULT 0
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_child ON device_registry(child_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_blocked ON device_registry(is_blocked);")

            conn.commit()
            logger.info(f"Child Memory database initialized at: {self.db_path}")

    # ==================== Core Profile Methods ====================

    def get_or_create_profile(self, child_id: str = "default_child", default_name: str = "Bé") -> Dict[str, Any]:
        """Lấy hồ sơ của bé, nếu chưa có thì tạo mới"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM child_profile WHERE child_id = ?;", (child_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["family_info"] = json.loads(data["family_info"]) if data["family_info"] else {}
                data["hobbies"] = json.loads(data["hobbies"]) if data["hobbies"] else []
                return data
            
            # Tạo hồ sơ mặc định
            cursor.execute("""
                INSERT INTO child_profile (child_id, name, nickname, age, learning_level, family_info, hobbies, personality)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (child_id, default_name, default_name, 6, 'Starters', json.dumps({}), json.dumps([]), None))
            conn.commit()
            
            return {
                "child_id": child_id,
                "name": default_name,
                "nickname": default_name,
                "age": 6,
                "learning_level": "Starters",
                "family_info": {},
                "hobbies": [],
                "personality": None
            }

    def update_profile_fact(self, child_id: str, key: str, value: Any) -> bool:
        """Cập nhật một thuộc tính cụ thể trong hồ sơ của bé (từ hội thoại)"""
        COLUMN_MAP = {
            "name": "name",
            "nickname": "nickname",
            "age": "age",
            "grade": "grade",
            "favorite_color": "favorite_color",
            "favorite_animal": "favorite_animal",
            "favorite_food": "favorite_food",
            "favorite_character": "favorite_character",
            "learning_level": "learning_level",
            "personality": "personality",
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            
            # Đảm bảo profile tồn tại
            self.get_or_create_profile(child_id)

            if key in COLUMN_MAP:
                col = COLUMN_MAP[key]
                cursor.execute(
                    f"UPDATE child_profile SET {col} = ?, updated_at = ? WHERE child_id = ?;",
                    (value, now, child_id)
                )
            elif key == "hobby":
                # Thêm vào danh sách hobbies nếu chưa có
                cursor.execute("SELECT hobbies FROM child_profile WHERE child_id = ?;", (child_id,))
                row = cursor.fetchone()
                hobbies = json.loads(row["hobbies"]) if row and row["hobbies"] else []
                if value not in hobbies:
                    hobbies.append(str(value))
                    cursor.execute("UPDATE child_profile SET hobbies = ?, updated_at = ? WHERE child_id = ?;", 
                                   (json.dumps(hobbies), now, child_id))
            elif key.startswith("family_"):
                # Cập nhật thông tin người thân (vd: family_mom: "Mẹ Hoa", family_pet: "Chó Lu")
                relation = key.replace("family_", "")
                cursor.execute("SELECT family_info FROM child_profile WHERE child_id = ?;", (child_id,))
                row = cursor.fetchone()
                fam = json.loads(row["family_info"]) if row and row["family_info"] else {}
                fam[relation] = str(value)
                cursor.execute("UPDATE child_profile SET family_info = ?, updated_at = ? WHERE child_id = ?;", 
                               (json.dumps(fam), now, child_id))
            else:
                # Lưu vào dạng kỷ niệm thông tin
                self.add_episodic_memory(child_id, category="FACT", content=f"{key}: {value}", importance=3)

            conn.commit()
            logger.info(f"Updated profile fact for {child_id}: {key} = {value}")
            return True

    def update_profile(self, child_id: str, fields: Dict[str, Any]) -> bool:
        """
        Cập nhật toàn bộ hồ sơ từ phụ huynh (trang cấu hình). Khác với
        update_profile_fact() — method này set nguyên giá trị của hobbies và
        family_info (không append), vì phụ huynh đang gửi bộ dữ liệu hoàn chỉnh.
        """
        scalar_fields = {
            "name", "nickname", "age", "gender", "grade", "favorite_color",
            "favorite_animal", "favorite_food", "favorite_character",
            "learning_level", "personality", "parent_pin",
        }
        self.get_or_create_profile(child_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            for key, value in fields.items():
                if key in scalar_fields:
                    cursor.execute(
                        f"UPDATE child_profile SET {key} = ?, updated_at = ? WHERE child_id = ?;",
                        (value, now, child_id),
                    )
                elif key == "hobbies" and isinstance(value, list):
                    hobbies = [str(v).strip() for v in value if str(v).strip()]
                    cursor.execute(
                        "UPDATE child_profile SET hobbies = ?, updated_at = ? WHERE child_id = ?;",
                        (json.dumps(hobbies), now, child_id),
                    )
                elif key == "family_info" and isinstance(value, dict):
                    fam = {str(k): str(v) for k, v in value.items() if str(v).strip()}
                    cursor.execute(
                        "UPDATE child_profile SET family_info = ?, updated_at = ? WHERE child_id = ?;",
                        (json.dumps(fam), now, child_id),
                    )

            conn.commit()
            logger.info(f"Updated profile for {child_id} from parent config.")
            return True

    # ==================== Multi-Tenant Parent PIN Security ====================

    def verify_parent_pin(self, child_id: str, pin: str) -> bool:
        """Xác thực mã PIN của phụ huynh riêng cho từng thiết bị/child_id."""
        if not pin:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT parent_pin FROM child_profile WHERE child_id = ?;", (child_id,))
            row = cursor.fetchone()
            stored_pin = (row["parent_pin"] if row and row["parent_pin"] else "1234").strip()
            return secrets.compare_digest(stored_pin, str(pin).strip())

    def set_parent_pin(self, child_id: str, new_pin: str) -> bool:
        """Cập nhật mã PIN mới cho phụ huynh trên thiết bị."""
        clean_pin = str(new_pin).strip()
        if len(clean_pin) < 4:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            self.get_or_create_profile(child_id)
            cursor.execute(
                "UPDATE child_profile SET parent_pin = ?, updated_at = ? WHERE child_id = ?;",
                (clean_pin, now, child_id)
            )
            conn.commit()
            logger.info(f"Updated parent PIN for child [{child_id}].")
            return True

    # ==================== First-Run Setup Methods ====================

    def is_profile_completed(self, child_id: str) -> bool:
        """Kiểm tra phụ huynh đã hoàn thành màn cấu hình ban đầu chưa."""
        profile = self.get_or_create_profile(child_id)
        return bool(profile.get("profile_completed"))

    def mark_profile_completed(self, child_id: str) -> bool:
        """Đánh dấu màn cấu hình ban đầu đã hoàn thành."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "UPDATE child_profile SET profile_completed = 1, updated_at = ? WHERE child_id = ?;",
                (now, child_id),
            )
            conn.commit()
            logger.info(f"Profile setup completed for {child_id}.")
            return True

    # ==================== Episodic Memory Methods ====================

    def add_episodic_memory(
        self,
        child_id: str,
        category: str,
        content: str,
        emotional_tag: Optional[str] = None,
        importance: int = 3
    ) -> int:
        """Lưu một kỷ niệm / sự kiện đáng nhớ của bé trong buổi trò chuyện"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodic_memories (child_id, category, content, emotional_tag, importance)
                VALUES (?, ?, ?, ?, ?);
            """, (child_id, category.upper(), content.strip(), emotional_tag, max(1, min(5, importance))))
            conn.commit()
            memory_id = cursor.lastrowid
            logger.info(f"Saved memory for {child_id} [{category}]: {content}")
            return memory_id

    def get_recent_memories(self, child_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Lấy các kỷ niệm gần nhất có mức quan trọng cao để nhắc lại tự nhiên"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, content, emotional_tag, importance, created_at
                FROM episodic_memories
                WHERE child_id = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?;
            """, (child_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== Learning Progress Methods ====================

    def update_learning_progress(
        self,
        child_id: str,
        topic: str,
        mastered_words: Optional[List[str]] = None,
        needs_practice: Optional[List[str]] = None,
        score: Optional[int] = None
    ) -> bool:
        """Cập nhật từ vựng đã thuộc hoặc từ cần ôn luyện cho bé"""
        topic = topic.strip().capitalize()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM learning_progress WHERE child_id = ? AND topic = ?;", (child_id, topic))
            row = cursor.fetchone()
            
            curr_mastered = json.loads(row["mastered_words"]) if row and row["mastered_words"] else []
            curr_practice = json.loads(row["needs_practice"]) if row and row["needs_practice"] else []
            
            if mastered_words:
                for w in mastered_words:
                    w = w.lower().strip()
                    if w not in curr_mastered:
                        curr_mastered.append(w)
                    if w in curr_practice:
                        curr_practice.remove(w)
            
            if needs_practice:
                for w in needs_practice:
                    w = w.lower().strip()
                    if w not in curr_practice and w not in curr_mastered:
                        curr_practice.append(w)

            new_score = score if score is not None else (min(100, len(curr_mastered) * 10))
            now = datetime.now(timezone.utc).isoformat()

            if row:
                cursor.execute("""
                    UPDATE learning_progress
                    SET mastered_words = ?, needs_practice = ?, mastery_score = ?, last_practiced = ?
                    WHERE child_id = ? AND topic = ?;
                """, (json.dumps(curr_mastered), json.dumps(curr_practice), new_score, now, child_id, topic))
            else:
                cursor.execute("""
                    INSERT INTO learning_progress (child_id, topic, mastered_words, needs_practice, mastery_score, last_practiced)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (child_id, topic, json.dumps(curr_mastered), json.dumps(curr_practice), new_score, now))

            conn.commit()
            logger.info(f"Updated learning progress for {child_id} on topic '{topic}'")
            return True

    def get_learning_summary(self, child_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các chủ đề và từ vựng bé đang học"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT topic, mastered_words, needs_practice, mastery_score, last_practiced
                FROM learning_progress
                WHERE child_id = ?
                ORDER BY last_practiced DESC;
            """, (child_id,))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "topic": row["topic"],
                    "mastered_words": json.loads(row["mastered_words"]) if row["mastered_words"] else [],
                    "needs_practice": json.loads(row["needs_practice"]) if row["needs_practice"] else [],
                    "mastery_score": row["mastery_score"],
                    "last_practiced": row["last_practiced"]
                })
            return results

    # ==================== System Prompt Context Builder ====================

    def build_memory_context(self, child_id: str = "default_child") -> str:
        """
        Tạo đoạn ngữ cảnh ngắn gọn (<250 tokens) tối ưu để nhúng vào System Prompt của Gemini Live.
        Giúp Doraemon nhận diện ngay bé là ai, sở thích gì và cần ôn từ nào.
        """
        profile = self.get_or_create_profile(child_id)
        recent_memories = self.get_recent_memories(child_id, limit=3)
        learning = self.get_learning_summary(child_id)

        lines = [
            "### Child Profile & Living Memory (Always use this context to personalize):",
            f"- Child's Name/Nickname: {profile.get('nickname') or profile.get('name')} (Age: {profile.get('age', 6)})",
        ]

        if profile.get("gender"):
            gender_label = "boy" if profile["gender"].lower().startswith("male") else "girl"
            lines.append(f"- Gender: {gender_label} (use appropriate pronouns)")

        if profile.get("personality"):
            lines.append(f"- Personality & Communication Style: {profile.get('personality')}")
        if profile.get("grade"):
            lines.append(f"- Grade: {profile.get('grade')}")
        if profile.get("learning_level"):
            lines.append(f"- English Level: {profile.get('learning_level')}")

        if profile.get("favorite_animal"):
            lines.append(f"- Favorite Animal: {profile.get('favorite_animal')}")
        if profile.get("favorite_color"):
            lines.append(f"- Favorite Color: {profile.get('favorite_color')}")
        if profile.get("favorite_food"):
            lines.append(f"- Favorite Food: {profile.get('favorite_food')}")
        if profile.get("favorite_character"):
            lines.append(f"- Favorite Superhero/Character: {profile.get('favorite_character')}")
        
        fam = profile.get("family_info", {})
        if fam:
            fam_str = ", ".join([f"{k}: {v}" for k, v in fam.items()])
            lines.append(f"- Family & Pets: {fam_str}")

        hobbies = profile.get("hobbies", [])
        if hobbies:
            lines.append(f"- Hobbies/Interests: {', '.join(hobbies)}")

        if recent_memories:
            lines.append("- Recent Life Memories with Doraemon:")
            for m in recent_memories:
                lines.append(f"  * [{m['category']}] {m['content']}")

        if learning:
            recent_topic = learning[0]
            if recent_topic["needs_practice"]:
                lines.append(f"- English Practice Focus: Topic '{recent_topic['topic']}', encourage words: {', '.join(recent_topic['needs_practice'])}")

        # Streak & Gamification context
        streak = profile.get("streak_days", 0)
        total_sessions = profile.get("total_sessions_count", 0)
        if streak > 1:
            lines.append(f"- Streak: Bé đang có chuỗi {streak} ngày học liên tiếp! Hãy khen ngợi tinh thần chăm chỉ của bé!")
        elif total_sessions == 0:
            lines.append("- Session: Đây là buổi đầu tiên bé làm quen với Doraemon. Hãy mở đầu thật hào hứng, ấm áp và thân thiện!")

        last_session = self.get_last_session_summary(child_id)
        if last_session and last_session.get("summary"):
            lines.append(
                "- Cuối buổi trò chuyện lần trước, Doraemon và bé đã chốt lại: "
                f"{last_session['summary']} "
                "(hãy nhắc lại tự nhiên đầu buổi hôm nay như một kỷ niệm chung)."
            )

        return "\n".join(lines)

    # ==================== Session Lifecycle & Gamification ====================

    def log_session(
        self,
        child_id: str,
        duration_seconds: int = 0,
        summary: Optional[str] = None,
        session_topic: Optional[str] = None
    ) -> int:
        """Chốt lại một buổi trò chuyện: tổng kết buổi + thời lượng + cập nhật Streak.

        Lưu vào session_logs để Doraemon nhớ buổi trước đã làm gì và tính chuỗi
        ngày học liên tiếp (Streak) nhằm khuyến khích thói quen học tập của trẻ.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_dt = datetime.now(timezone.utc)
            today_str = now_dt.strftime("%Y-%m-%d")

            # 1. Lưu log phiên trò chuyện
            cursor.execute("""
                INSERT INTO session_logs (child_id, session_topic, duration_seconds, summary)
                VALUES (?, ?, ?, ?);
            """, (child_id, session_topic, max(0, duration_seconds), (summary or "").strip()))
            session_id = cursor.lastrowid

            # 2. Cập nhật Streak & Tổng số session trong child_profile
            cursor.execute("SELECT streak_days, last_active_date, total_sessions_count FROM child_profile WHERE child_id = ?;", (child_id,))
            row = cursor.fetchone()
            if row:
                current_streak = row["streak_days"] or 0
                last_date_str = row["last_active_date"]
                total_sessions = (row["total_sessions_count"] or 0) + 1

                new_streak = current_streak
                if not last_date_str:
                    new_streak = 1
                elif last_date_str == today_str:
                    # Đã học trong ngày hôm nay, giữ nguyên streak
                    new_streak = max(1, current_streak)
                else:
                    try:
                        last_d = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                        today_d = now_dt.date()
                        if today_d - last_d == timedelta(days=1):
                            new_streak = current_streak + 1
                        else:
                            new_streak = 1
                    except Exception:
                        new_streak = 1

                cursor.execute("""
                    UPDATE child_profile
                    SET streak_days = ?, last_active_date = ?, total_sessions_count = ?, updated_at = ?
                    WHERE child_id = ?;
                """, (new_streak, today_str, total_sessions, now_dt.isoformat(), child_id))

            conn.commit()
            logger.info(f"Session logged for {child_id}: {duration_seconds}s (Streak={new_streak if row else 1}) — {summary}")
            return session_id

    def get_last_session_summary(self, child_id: str) -> Optional[Dict[str, Any]]:
        """Lấy tổng kết của buổi trò chuyện gần nhất để nhắc lại đầu buổi sau."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_topic, duration_seconds, summary, created_at
                FROM session_logs
                WHERE child_id = ?
                ORDER BY created_at DESC
                LIMIT 1;
            """, (child_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== Parent Digest & Gamification Reports ====================

    def get_daily_digest(self, child_id: str = "default_child") -> Dict[str, Any]:
        """
        Tổng hợp báo cáo tiến độ học tập và huy hiệu dành cho Phụ huynh (Parent Dashboard).
        Bao gồm: Chuỗi ngày (Streak), Từ vựng đã làm chủ, Chủ đề đã khám phá, và Huy hiệu bảo bối.
        """
        profile = self.get_or_create_profile(child_id)
        learning = self.get_learning_summary(child_id)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Thống kê session
            cursor.execute("""
                SELECT COUNT(*) as total_sessions, SUM(duration_seconds) as total_duration
                FROM session_logs
                WHERE child_id = ?;
            """, (child_id,))
            stat_row = cursor.fetchone()
            total_sessions = stat_row["total_sessions"] if stat_row else 0
            total_duration_sec = stat_row["total_duration"] or 0

            # Lấy 5 session gần nhất
            cursor.execute("""
                SELECT id, session_topic, duration_seconds, summary, created_at
                FROM session_logs
                WHERE child_id = ?
                ORDER BY created_at DESC
                LIMIT 5;
            """, (child_id,))
            recent_sessions = [dict(r) for r in cursor.fetchall()]

        # Gom danh sách từ vựng
        all_mastered = []
        all_practice = []
        for topic_item in learning:
            all_mastered.extend(topic_item.get("mastered_words", []))
            all_practice.extend(topic_item.get("needs_practice", []))

        # Loại bỏ trùng lặp
        unique_mastered = sorted(list(set(all_mastered)))
        unique_practice = sorted(list(set(all_practice)))
        streak_days = profile.get("streak_days", 0)

        # Tính toán Huy hiệu Bảo bối (Badges)
        badges = [
            {
                "id": "first_step",
                "name": "🌱 Bước Chân Đầu Tiên",
                "desc": "Hoàn thành buổi trò chuyện đầu tiên với Doraemon",
                "icon": "🌱",
                "unlocked": total_sessions >= 1
            },
            {
                "id": "streak_3",
                "name": "🔥 Chăm Chỉ 3 Ngày",
                "desc": "Trò chuyện cùng Doraemon 3 ngày liên tiếp",
                "icon": "🔥",
                "unlocked": streak_days >= 3
            },
            {
                "id": "streak_7",
                "name": "⚡ Siêu Bền Bỉ 7 Ngày",
                "desc": "Đạt chuỗi 7 ngày học tập liên tục",
                "icon": "⚡",
                "unlocked": streak_days >= 7
            },
            {
                "id": "vocab_5",
                "name": "⭐ Thợ Săn Từ Vựng",
                "desc": "Làm chủ từ 5 từ vựng tiếng Anh mới",
                "icon": "⭐",
                "unlocked": len(unique_mastered) >= 5
            },
            {
                "id": "vocab_15",
                "name": "👑 Siêu Sao Tiếng Anh",
                "desc": "Làm chủ từ 15 từ vựng tiếng Anh",
                "icon": "👑",
                "unlocked": len(unique_mastered) >= 15
            },
            {
                "id": "explorer",
                "name": "🔭 Nhà Thám Hiểm Tri Thức",
                "desc": "Khám phá từ 3 chủ đề học tập và bách khoa",
                "icon": "🔭",
                "unlocked": len(learning) >= 3 or total_sessions >= 3
            }
        ]

        # Lời khuyên sư phạm tự động cho phụ huynh
        child_name = profile.get("nickname") or profile.get("name") or "Bé"
        if len(unique_mastered) > 0:
            advice = (
                f"{child_name} đang có phản xạ rất tốt với nhóm từ vựng tiếng Anh! "
                f"Phụ huynh có thể khuyến khích bé sử dụng các từ: '{', '.join(unique_mastered[:3])}' "
                "trong các hoạt động đời thường ở nhà."
            )
        elif streak_days > 0:
            advice = f"{child_name} đang duy trì thói quen học tập rất đều đặn! Hãy tiếp tục động viên bé mỗi ngày."
        else:
            advice = f"Hãy cùng {child_name} mở Doraemon trò chuyện 5-10 phút mỗi ngày để tạo phản xạ giao tiếp tự tin nhé!"

        return {
            "child_id": child_id,
            "child_name": child_name,
            "age": profile.get("age", 6),
            "learning_level": profile.get("learning_level", "Starters"),
            "streak_days": streak_days,
            "total_sessions": total_sessions,
            "total_duration_minutes": round(total_duration_sec / 60.0, 1),
            "mastered_words_count": len(unique_mastered),
            "mastered_words": unique_mastered,
            "needs_practice": unique_practice,
            "learning_topics": learning,
            "recent_sessions": recent_sessions,
            "badges": badges,
            "pedagogical_advice": advice,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    # ==================== Privacy & COPPA Compliance ====================

    def export_child_data(self, child_id: str = "default_child") -> Dict[str, Any]:
        """Xuất toàn bộ dữ liệu của bé ra JSON (Quyền kiểm soát của phụ huynh)"""
        return {
            "profile": self.get_or_create_profile(child_id),
            "memories": self.get_recent_memories(child_id, limit=100),
            "learning_progress": self.get_learning_summary(child_id)
        }

    def delete_all_child_data(self, child_id: str = "default_child") -> bool:
        """Xóa hoàn toàn dữ liệu của bé theo yêu cầu phụ huynh (Right to Erasure)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM child_profile WHERE child_id = ?;", (child_id,))
            conn.commit()
            logger.warning(f"All data for child {child_id} has been permanently deleted.")
            return True

    # ==================== Dynamic Discovery Topics ====================

    def generate_dynamic_topics(self, child_id: str = "default_child") -> List[Dict[str, Any]]:
        """
        Sinh danh sách 6 thẻ chủ đề thông minh (Dynamic Discovery Topics):
        1. Cá nhân hóa theo sở thích / nhân vật yêu thích của bé.
        2. Ôn tập từ vựng & kiến thức (Spaced Repetition nếu có từ needs_practice).
        3. Khám phá theo thời điểm trong ngày (Sáng / Chiều / Tối).
        4. Bách khoa tri thức (Vũ trụ, Khủng long, Đại dương, Khoa học).
        5. Tình huống Tiếng Anh nhập vai (English Roleplay).
        6. Bí ẩn đại dương & câu đố vui trí tuệ.
        """
        profile = self.get_or_create_profile(child_id)
        child_name = profile.get("nickname") or profile.get("name") or "Bé"
        hobbies = profile.get("hobbies") or []
        fav_animal = profile.get("favorite_animal") or ""
        learning = self.get_learning_summary(child_id)

        # Lấy từ vựng cần ôn tập
        practice_words: List[str] = []
        for item in learning:
            for w in item.get("needs_practice", []):
                if w and w not in practice_words:
                    practice_words.append(w)

        topics: List[Dict[str, Any]] = []

        # 1. Thẻ Cá nhân hóa theo sở thích (Personalized Hobby / Pet)
        if fav_animal:
            topics.append({
                "id": "fav_animal_quest",
                "title": f"Thế Giới {fav_animal.capitalize()}",
                "title_en": f"{fav_animal.capitalize()} Kingdom",
                "emoji": "🐾",
                "color_hex": "#F472B6",
                "tag": "Sở thích của bé",
                "description": f"Cùng Doraemon khám phá những bí mật siêu đáng yêu về {fav_animal}!",
                "prompt_hint": f"[Bé vừa chọn khám phá chủ đề: Thế giới loài {fav_animal} (sở thích của bé). Hãy mở đầu bằng một câu chào vui tươi, chia sẻ 1 bí mật bất ngờ về {fav_animal} và đố bé 1 câu hỏi gợi mở nhé!]"
            })
        elif hobbies:
            hobby_0 = str(hobbies[0])
            topics.append({
                "id": "fav_hobby_quest",
                "title": f"Thám Hiểm {hobby_0.capitalize()}",
                "title_en": f"{hobby_0.capitalize()} Adventure",
                "emoji": "🎨",
                "color_hex": "#F472B6",
                "tag": "Sở thích của bé",
                "description": f"Khám phá thế giới {hobby_0} tràn ngập niềm vui cùng Doraemon!",
                "prompt_hint": f"[Bé vừa chọn khám phá chủ đề: {hobby_0} (sở thích của bé). Hãy mở đầu thân thiện, hỏi bé về sở thích này và đố bé một câu đố vui nhé!]"
            })
        else:
            topics.append({
                "id": "dino_discovery",
                "title": "Khủng Long Khổng Lồ",
                "title_en": "Dinosaur Kingdom",
                "emoji": "🦖",
                "color_hex": "#F472B6",
                "tag": "Khám phá muôn loài",
                "description": "Giải mã sức mạnh của T-Rex bạo chúa và các loài khủng long kỷ Jura!",
                "prompt_hint": "[Bé vừa chọn khám phá chủ đề: Khủng Long Kỷ Jura. Hãy mở đầu hào hứng, giới thiệu một sự thật kỳ thú về khủng long và đố bé một câu hỏi nhé!]"
            })

        # 2. Thẻ Ôn tập từ vựng thông minh (Spaced Repetition Review)
        if practice_words:
            word_target = practice_words[0]
            topics.append({
                "id": "vocab_review",
                "title": f"Thử Thách Từ '{word_target.capitalize()}'",
                "title_en": f"Learn '{word_target.capitalize()}'",
                "emoji": "🌟",
                "color_hex": "#38BDF8",
                "tag": "Ôn tập từ mới",
                "description": f"Chinh phục từ vựng '{word_target}' trong các câu chuyện kỳ thú!",
                "prompt_hint": f"[Bé vừa chọn ôn tập từ vựng tiếng Anh '{word_target}'. Hãy tạo một câu chuyện ngắn thú vị, dạy bé cách phát âm chuẩn và khuyến khích bé nói từ '{word_target}' nhé!]"
            })
        else:
            topics.append({
                "id": "magic_english",
                "title": "Tiếng Anh Diệu Kỳ",
                "title_en": "Magic English Words",
                "emoji": "✨",
                "color_hex": "#38BDF8",
                "tag": "Học từ mới",
                "description": "Luyện phát âm chuẩn bản xứ và học các từ vựng tiếng Anh vui nhộn!",
                "prompt_hint": "[Bé vừa chọn chủ đề: Tiếng Anh Diệu Kỳ. Hãy mở đầu bằng một câu chào tiếng Anh ấm áp, giới thiệu 1-2 từ mới dễ nhớ và rủ bé cùng đọc theo nhé!]"
            })

        # 3. Thẻ Theo khung giờ trong ngày (Time-aware)
        current_hour = datetime.now().hour
        if 5 <= current_hour < 11:
            topics.append({
                "id": "morning_energy",
                "title": "Chào Ngày Mới Rực Rỡ",
                "title_en": "Sunny Morning Energy",
                "emoji": "☀️",
                "color_hex": "#FBBF24",
                "tag": "Khởi động buổi sáng",
                "description": "Tìm hiểu xem các bạn động vật thức dậy và ăn sáng thế nào nhé!",
                "prompt_hint": "[Bé vừa chọn chủ đề: Chào Ngày Mới Rực Rỡ. Hãy chúc bé một buổi sáng tràn đầy năng lượng và hỏi bé đã ăn sáng món gì ngon chưa nhé!]"
            })
        elif 11 <= current_hour < 18:
            topics.append({
                "id": "afternoon_science",
                "title": "Khoa Học Quanh Em",
                "title_en": "Curious Everyday Science",
                "emoji": "🔬",
                "color_hex": "#10B981",
                "tag": "Khoa học vui",
                "description": "Tại sao cầu vồng có 7 màu? Tại sao lá cây lại có màu xanh?",
                "prompt_hint": "[Bé vừa chọn chủ đề: Khoa Học Quanh Em. Hãy chia sẻ một hiện tượng tự nhiên thú vị như Cầu vồng hoặc Lá cây và đố bé giải thích nhé!]"
            })
        else:
            topics.append({
                "id": "night_stars",
                "title": "Bí Mật Bầu Trời Đêm",
                "title_en": "Night Sky & Stars",
                "emoji": "🌙",
                "color_hex": "#818CF8",
                "tag": "Chuyện trước giờ ngủ",
                "description": "Du hành qua các chòm sao lấp lánh và lắng nghe giai thoại êm dịu.",
                "prompt_hint": "[Bé vừa chọn chủ đề: Bí Mật Bầu Trời Đêm. Hãy dùng giọng điệu êm dịu, ấm áp, kể cho bé nghe về Mặt Trăng và các chòm sao lấp lánh nhé!]"
            })

        # 4. Thẻ Vũ trụ & Thiên văn (Space Adventure)
        topics.append({
            "id": "space_voyage",
            "title": "Du Hành Vũ Trụ",
            "title_en": "Space & Solar System",
            "emoji": "🚀",
            "color_hex": "#8B5CF6",
            "tag": "Vũ trụ & Thiên văn",
            "description": "Lái Tàu Vũ Trụ đổ bộ lên Mặt Trăng, Sao Hỏa và giải mã Hố Đen!",
            "prompt_hint": "[Bé vừa chọn chủ đề: Du Hành Vũ Trụ. Hãy thắt dây an toàn, cùng bé bước lên Tàu Vũ Trụ bay tới Sao Hỏa và đố bé về Hệ Mặt Trời nhé!]"
        })

        # 5. Thẻ Tiếng Anh Nhập Vai (Roleplay Adventure)
        roleplay_pool = [
            ("Tiệm Kem New York", "Ice Cream Shop", "🍦", "Nhập vai bác bán kem và gọi các vị kem yêu thích bằng tiếng Anh!"),
            ("Phi Hành Gia Thám Hiểm", "Astronaut Mission", "👨‍🚀", "Cùng đếm ngược phóng tên lửa: 3, 2, 1... Blast off!"),
            ("Đầu Bếp Nhí Tài Ba", "Master Junior Chef", "🍕", "Làm chiếc bánh pizza khổng lồ với phô mai và cà chua!"),
        ]
        day_seed = date.today().toordinal() % len(roleplay_pool)
        rp_title, rp_en, rp_emoji, rp_desc = roleplay_pool[day_seed]
        topics.append({
            "id": f"roleplay_{day_seed}",
            "title": rp_title,
            "title_en": rp_en,
            "emoji": rp_emoji,
            "color_hex": "#EC4899",
            "tag": "Nhập vai Tiếng Anh",
            "description": rp_desc,
            "prompt_hint": f"[Bé vừa chọn trò chơi nhập vai tiếng Anh: {rp_title} ({rp_en}). Hãy bắt đầu đóng vai một cách dí dỏm, hào hứng và hướng dẫn bé đối đáp nhé!]"
        })

        # 6. Thẻ Bí Ẩn Đại Dương (Ocean Mysteries)
        topics.append({
            "id": "ocean_depths",
            "title": "Đại Dương Huyền Bí",
            "title_en": "Ocean Mysteries",
            "emoji": "🌊",
            "color_hex": "#06B6D4",
            "tag": "Bách khoa thiên nhiên",
            "description": "Lặn sâu ngắm Cá Voi Xanh khổng lồ và thế giới san hô rực rỡ!",
            "prompt_hint": "[Bé vừa chọn khám phá: Đại Dương Huyền Bí. Hãy lặn sâu xuống đáy biển cùng bé, giới thiệu về Cá Voi Xanh và đố bé một câu hỏi kỳ thú nhé!]"
        })

        return topics

    # ==================== Device Registry & Ban Methods ====================

    def register_device(
        self,
        device_fingerprint: str,
        child_id: str,
        device_model: str = "",
        android_version: str = "",
        app_version: str = "",
        ip: str = ""
    ) -> Dict[str, Any]:
        """Đăng ký hoặc cập nhật thông tin thiết bị khi kết nối."""
        if not device_fingerprint:
            device_fingerprint = f"legacy_{child_id}"

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM device_registry WHERE device_fingerprint = ?;", (device_fingerprint,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE device_registry
                    SET child_id = ?,
                        device_model = COALESCE(NULLIF(?, ''), device_model),
                        android_version = COALESCE(NULLIF(?, ''), android_version),
                        app_version = COALESCE(NULLIF(?, ''), app_version),
                        last_ip = COALESCE(NULLIF(?, ''), last_ip),
                        last_seen_at = ?
                    WHERE device_fingerprint = ?;
                """, (child_id, device_model, android_version, app_version, ip, now_iso, device_fingerprint))
            else:
                cursor.execute("""
                    INSERT INTO device_registry (
                        device_fingerprint, child_id, device_model, android_version, app_version,
                        first_seen_at, last_seen_at, last_ip, is_blocked, block_reason, total_sessions, total_duration_sec
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 0, 0);
                """, (device_fingerprint, child_id, device_model, android_version, app_version, now_iso, now_iso, ip))

            conn.commit()
            cursor.execute("SELECT * FROM device_registry WHERE device_fingerprint = ?;", (device_fingerprint,))
            return dict(cursor.fetchone())

    def is_device_blocked(
        self,
        device_fingerprint: Optional[str] = None,
        child_id: Optional[str] = None,
        ip: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Kiểm tra xem thiết bị hoặc child_id có đang bị chặn không."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Kiểm tra theo device_fingerprint
            if device_fingerprint:
                cursor.execute("SELECT is_blocked, block_reason FROM device_registry WHERE device_fingerprint = ?;", (device_fingerprint,))
                row = cursor.fetchone()
                if row and row["is_blocked"]:
                    return True, row["block_reason"] or "Thiết bị này đã bị tạm ngưng kết nối bởi Quản trị viên."

            # 2. Kiểm tra theo child_id
            if child_id:
                cursor.execute("SELECT is_blocked, block_reason FROM device_registry WHERE child_id = ? AND is_blocked = 1;", (child_id,))
                row = cursor.fetchone()
                if row:
                    return True, row["block_reason"] or "Hồ sơ của bé đã bị tạm khóa bởi Quản trị viên."

            return False, None

    def set_device_block_status(
        self,
        device_fingerprint: str,
        is_blocked: bool,
        reason: Optional[str] = None
    ) -> bool:
        """Khóa hoặc mở khóa một thiết bị bất biến."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE device_registry
                SET is_blocked = ?,
                    block_reason = ?
                WHERE device_fingerprint = ?;
            """, (1 if is_blocked else 0, reason if is_blocked else None, device_fingerprint))
            conn.commit()
            return cursor.rowcount > 0

    def update_device_session_stats(self, device_fingerprint: str, duration_sec: int):
        """Cập nhật số phiên và tổng thời lượng đàm thoại cho thiết bị."""
        if not device_fingerprint:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE device_registry
                SET total_sessions = total_sessions + 1,
                    total_duration_sec = total_duration_sec + ?,
                    last_seen_at = ?
                WHERE device_fingerprint = ?;
            """, (max(0, duration_sec), now_iso, device_fingerprint))
            conn.commit()

    def get_all_devices(self, search: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Lấy danh sách thiết bị cho Admin Dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT d.*, p.name as child_name, p.age as child_age, p.learning_level
                FROM device_registry d
                LEFT JOIN child_profile p ON d.child_id = p.child_id
            """
            params = []
            if search and search.strip():
                query += " WHERE d.device_fingerprint LIKE ? OR d.child_id LIKE ? OR d.device_model LIKE ? OR d.last_ip LIKE ? OR p.name LIKE ?"
                s = f"%{search.strip()}%"
                params.extend([s, s, s, s, s])

            query += " ORDER BY d.last_seen_at DESC LIMIT ?;"
            params.append(limit)

            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

    def get_device_metrics(self) -> Dict[str, Any]:
        """Thống kê tổng quan thiết bị cho KPI Cards."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM device_registry;")
            total_devices = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM device_registry WHERE is_blocked = 1;")
            blocked_devices = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(total_duration_sec) FROM device_registry;")
            total_duration_sec = cursor.fetchone()[0] or 0

            return {
                "total_devices": total_devices,
                "blocked_devices": blocked_devices,
                "active_devices": max(0, total_devices - blocked_devices),
                "total_hours_spoken": round(total_duration_sec / 3600.0, 1)
            }

