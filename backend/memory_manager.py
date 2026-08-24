import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

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
                    grade TEXT,
                    favorite_color TEXT,
                    favorite_animal TEXT,
                    favorite_food TEXT,
                    favorite_character TEXT,
                    family_info TEXT, -- JSON format: {"mom": "Hoa", "dad": "Minh", "pet": "Cat Miu"}
                    hobbies TEXT,     -- JSON array: ["drawing", "swimming", "dinosaurs"]
                    learning_level TEXT DEFAULT 'Starters',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

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
                INSERT INTO child_profile (child_id, name, nickname, age, learning_level, family_info, hobbies)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (child_id, default_name, default_name, 6, 'Starters', json.dumps({}), json.dumps([])))
            conn.commit()
            
            return {
                "child_id": child_id,
                "name": default_name,
                "nickname": default_name,
                "age": 6,
                "learning_level": "Starters",
                "family_info": {},
                "hobbies": []
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
        Giúp Robo nhận diện ngay bé là ai, sở thích gì và cần ôn từ nào.
        """
        profile = self.get_or_create_profile(child_id)
        recent_memories = self.get_recent_memories(child_id, limit=3)
        learning = self.get_learning_summary(child_id)

        lines = [
            "### Child Profile & Living Memory (Always use this context to personalize):",
            f"- Child's Name/Nickname: {profile.get('nickname') or profile.get('name')} (Age: {profile.get('age', 6)})",
        ]

        if profile.get("favorite_animal"):
            lines.append(f"- Favorite Animal: {profile.get('favorite_animal')}")
        if profile.get("favorite_color"):
            lines.append(f"- Favorite Color: {profile.get('favorite_color')}")
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
            lines.append("- Recent Life Memories with Robo:")
            for m in recent_memories:
                lines.append(f"  * [{m['category']}] {m['content']}")

        if learning:
            recent_topic = learning[0]
            if recent_topic["needs_practice"]:
                lines.append(f"- English Practice Focus: Topic '{recent_topic['topic']}', encourage words: {', '.join(recent_topic['needs_practice'])}")

        return "\n".join(lines)

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
