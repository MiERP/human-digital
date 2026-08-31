import os
import sys
import unittest
import asyncio
import tempfile
import shutil

# Thêm thư mục backend vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_manager import MemoryManager
from safety_guard import ChildSafetyGuard

class TestChildMemoryAndSafety(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_child_memory.db")
        self.log_path = os.path.join(self.test_dir, "test_safety_audit.log")
        self.memory = MemoryManager(db_path=self.db_path)
        self.safety = ChildSafetyGuard(log_path=self.log_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_profile_creation_and_update(self):
        """Kiểm tra tạo mới và cập nhật hồ sơ cốt lõi của bé"""
        child_id = "kid_sam_01"
        profile = self.memory.get_or_create_profile(child_id, default_name="Sam")
        self.assertEqual(profile["name"], "Sam")
        self.assertEqual(profile["age"], 6)

        # Cập nhật các thuộc tính sở thích
        self.memory.update_profile_fact(child_id, "favorite_animal", "White Cat")
        self.memory.update_profile_fact(child_id, "favorite_color", "Sky Blue")
        self.memory.update_profile_fact(child_id, "hobby", "Drawing Dinosaurs")
        self.memory.update_profile_fact(child_id, "family_mom", "Mẹ Hoa")

        updated = self.memory.get_or_create_profile(child_id)
        self.assertEqual(updated["favorite_animal"], "White Cat")
        self.assertEqual(updated["favorite_color"], "Sky Blue")
        self.assertIn("Drawing Dinosaurs", updated["hobbies"])
        self.assertEqual(updated["family_info"]["mom"], "Mẹ Hoa")

    def test_episodic_memory_and_context_builder(self):
        """Kiểm tra lưu kỷ niệm thường ngày và tạo prompt context"""
        child_id = "kid_sam_01"
        self.memory.get_or_create_profile(child_id, default_name="Sam")
        self.memory.update_profile_fact(child_id, "favorite_animal", "Puppy")

        # Thêm kỷ niệm
        self.memory.add_episodic_memory(child_id, "DAILY_STORY", "Bé Sam vừa được bố đưa đi công viên bơi", "happy", importance=5)
        self.memory.update_learning_progress(child_id, "Animals", mastered_words=["dog", "cat"], needs_practice=["elephant", "giraffe"])

        context = self.memory.build_memory_context(child_id)
        self.assertIn("Sam", context)
        self.assertIn("Puppy", context)
        self.assertIn("công viên bơi", context)
        self.assertIn("elephant", context)

    def test_safety_guard_content_moderation(self):
        """Kiểm tra bộ lọc an toàn trẻ em chặn nội dung không phù hợp"""
        # Test bạo lực
        is_safe, cat, redirect = self.safety.evaluate_content("I want to kill that monster with a knife")
        self.assertFalse(is_safe)
        self.assertEqual(cat, "VIOLENCE")
        self.assertIsNotNone(redirect)

        # Test hành vi nguy hiểm
        is_safe, cat, redirect = self.safety.evaluate_content("Con muốn nghịch lửa và bật lửa trong phòng")
        self.assertFalse(is_safe)
        self.assertEqual(cat, "DANGEROUS_ACTS")
        self.assertIn("nguy hiểm", redirect)

        # Test PII bảo vệ thông tin cá nhân
        is_safe, cat, redirect = self.safety.evaluate_content("Mật khẩu của bố con là 123456 và số tài khoản")
        self.assertFalse(is_safe)
        self.assertEqual(cat, "PII_EXPOSURE")

        # Test câu hỏi an toàn bình thường
        is_safe, cat, redirect = self.safety.evaluate_content("Can you teach me English about cute puppies?")
        self.assertTrue(is_safe)
        self.assertIsNone(cat)

    def test_ssrf_protection(self):
        """Kiểm tra cơ chế chống SSRF trên Safe URL Fetching"""
        # HTTP không an toàn -> Chặn
        self.assertFalse(self.safety.assert_safe_url("http://kids.nationalgeographic.com/animals"))

        # Domain độc hại / không trong whitelist -> Chặn
        self.assertFalse(self.safety.assert_safe_url("https://malicious-site.com/exploit"))

        # Domain whitelist hợp lệ -> Cho phép
        self.assertTrue(self.safety.assert_safe_url("https://kids.nationalgeographic.com/animals"))

    def test_privacy_export_and_delete(self):
        """Kiểm tra tuân thủ quyền riêng tư dữ liệu trẻ em (COPPA / GDPR)"""
        child_id = "test_kid_export"
        self.memory.get_or_create_profile(child_id, default_name="Tom")
        self.memory.update_profile_fact(child_id, "favorite_food", "Pizza")

        exported = self.memory.export_child_data(child_id)
        self.assertEqual(exported["profile"]["favorite_food"], "Pizza")

        # Xóa toàn bộ dữ liệu
        self.memory.delete_all_child_data(child_id)
        with self.memory._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM child_profile WHERE child_id = ?;", (child_id,))
            self.assertIsNone(cursor.fetchone())

    def test_personalization_profile_update(self):
        """Kiểm tra cập nhật hồ sơ cá nhân hóa từ phụ huynh"""
        child_id = "kid_personalized"
        self.memory.update_profile(child_id, {
            "name": "Minh",
            "age": 7,
            "personality": "nhút nhát, cần động viên",
            "hobbies": ["vẽ tranh", "bơi lội"],
            "family_info": {"mom": "Hoa", "pet": "Miu"},
        })
        profile = self.memory.get_or_create_profile(child_id)
        self.assertEqual(profile["name"], "Minh")
        self.assertEqual(profile["age"], 7)
        self.assertEqual(profile["personality"], "nhút nhát, cần động viên")
        self.assertEqual(profile["hobbies"], ["vẽ tranh", "bơi lội"])
        self.assertEqual(profile["family_info"]["mom"], "Hoa")
        self.assertEqual(profile["family_info"]["pet"], "Miu")

        # build_memory_context phải đưa tính cách + sở thích vào prompt
        context = self.memory.build_memory_context(child_id)
        self.assertIn("nhút nhát", context)
        self.assertIn("vẽ tranh", context)
        self.assertIn("Hoa", context)

    def test_first_run_setup_flow(self):
        """Kiểm tra luồng cấu hình lần đầu: setup chưa xong -> ghi hồ sơ -> đánh dấu xong"""
        child_id = "kid_first_run"
        self.assertFalse(self.memory.is_profile_completed(child_id))

        self.memory.update_profile(child_id, {
            "name": "Su",
            "age": 7,
            "gender": "female",
            "personality": "hoạt bát, thích được khen",
            "hobbies": ["vẽ", "đọc truyện"],
        })
        self.memory.mark_profile_completed(child_id)
        self.assertTrue(self.memory.is_profile_completed(child_id))

        profile = self.memory.get_or_create_profile(child_id)
        self.assertEqual(profile["gender"], "female")

        # Context phải chứa giới tính để Doraemon xưng hô đúng
        context = self.memory.build_memory_context(child_id)
        self.assertIn("girl", context)
        self.assertIn("hoạt bát", context)

    def test_reset_setup_flag(self):
        """Kiểm tra reset cờ setup không xóa dữ liệu hồ sơ"""
        child_id = "kid_reset"
        self.memory.update_profile(child_id, {"name": "Minh", "age": 8})
        self.memory.mark_profile_completed(child_id)
        self.assertTrue(self.memory.is_profile_completed(child_id))

        # Reset cờ (mô phỏng endpoint DELETE /api/child/setup)
        with self.memory._get_connection() as conn:
            conn.execute("UPDATE child_profile SET profile_completed = 0 WHERE child_id = ?;", (child_id,))
            conn.commit()

        self.assertFalse(self.memory.is_profile_completed(child_id))
        profile = self.memory.get_or_create_profile(child_id)
        self.assertEqual(profile["name"], "Minh")  # dữ liệu vẫn còn

    def test_personality_column_migration(self):
        """Kiểm tra migration thêm cột personality cho DB cũ"""
        # Tạo DB cũ không có cột personality bằng cách tạo bảng thủ công
        import sqlite3
        old_db = os.path.join(self.test_dir, "old.db")
        conn = sqlite3.connect(old_db)
        conn.execute("""
            CREATE TABLE child_profile (
                child_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                nickname TEXT,
                age INTEGER,
                grade TEXT,
                favorite_color TEXT,
                favorite_animal TEXT,
                favorite_food TEXT,
                favorite_character TEXT,
                family_info TEXT,
                hobbies TEXT,
                learning_level TEXT DEFAULT 'Starters',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

        # Khởi tạo MemoryManager trên DB cũ phải tự thêm cột mà không lỗi
        memory_old = MemoryManager(db_path=old_db)
        with memory_old._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(child_profile);")
            cols = {row["name"] for row in cursor.fetchall()}
        self.assertIn("personality", cols)
        self.assertIn("streak_days", cols)
        self.assertIn("last_active_date", cols)
        self.assertIn("total_sessions_count", cols)

    def test_streak_and_session_logging(self):
        """Kiểm tra logic tính chuỗi ngày học liên tiếp (Streak) và số buổi"""
        child_id = "kid_streak_test"
        self.memory.get_or_create_profile(child_id, default_name="Bi")

        # Buổi học 1 hôm nay
        self.memory.log_session(child_id, duration_seconds=300, summary="Học về khủng long")
        profile = self.memory.get_or_create_profile(child_id)
        self.assertEqual(profile["streak_days"], 1)
        self.assertEqual(profile["total_sessions_count"], 1)

        # Buổi học thứ 2 trong cùng ngày -> giữ nguyên streak, tăng total_sessions
        self.memory.log_session(child_id, duration_seconds=400, summary="Học về vũ trụ")
        profile = self.memory.get_or_create_profile(child_id)
        self.assertEqual(profile["streak_days"], 1)
        self.assertEqual(profile["total_sessions_count"], 2)

    def test_daily_digest_and_badges(self):
        """Kiểm tra báo cáo phụ huynh Daily Digest và hệ thống huy hiệu bảo bối"""
        child_id = "kid_digest_test"
        self.memory.get_or_create_profile(child_id, default_name="An")
        
        # Thêm từ vựng học tập
        self.memory.update_learning_progress(child_id, "Animals", mastered_words=["cat", "dog", "lion", "tiger", "bear"], needs_practice=["monkey"])
        self.memory.update_learning_progress(child_id, "Space", mastered_words=["sun", "moon", "earth"])
        
        # Ghi 1 session
        self.memory.log_session(child_id, duration_seconds=600, summary="Bé học rất giỏi về các loài động vật")

        digest = self.memory.get_daily_digest(child_id)
        self.assertEqual(digest["child_name"], "An")
        self.assertEqual(digest["total_sessions"], 1)
        self.assertEqual(digest["total_duration_minutes"], 10.0)
        self.assertGreaterEqual(digest["mastered_words_count"], 5)
        self.assertIn("cat", digest["mastered_words"])
        self.assertIn("monkey", digest["needs_practice"])

        # Kiểm tra huy hiệu
        badges = {b["id"]: b["unlocked"] for b in digest["badges"]}
        self.assertTrue(badges["first_step"]) # Đã học 1 session
        self.assertTrue(badges["vocab_5"])    # Đã thuộc >= 5 từ
        self.assertIsNotNone(digest["pedagogical_advice"])

    def test_api_child_digest_endpoint(self):
        """Kiểm tra REST API GET /api/child/digest hoạt động chính xác"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        child_id = "kid_api_test_01"
        self.memory.get_or_create_profile(child_id, default_name="Bé Bơ")
        self.memory.log_session(child_id, duration_seconds=180, summary="Làm quen với Doraemon")

        response = client.get(f"/api/child/digest?child_id={child_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["child_id"], child_id)
        self.assertIn("streak_days", data)
        self.assertIn("badges", data)
        self.assertIn("mastered_words", data)

    def test_generate_dynamic_topics(self):
        """Kiểm tra sinh thẻ chủ đề động theo sở thích và tiến độ học tập"""
        child_id = "kid_topic_test_01"
        self.memory.get_or_create_profile(child_id, default_name="Minh")
        self.memory.update_profile_fact(child_id, "favorite_animal", "Dolphin")
        self.memory.update_learning_progress(child_id, "Animals", mastered_words=["dog"], needs_practice=["brave"])

        topics = self.memory.generate_dynamic_topics(child_id)
        self.assertEqual(len(topics), 6)
        
        # Thẻ 1: Sở thích Dolphin
        self.assertEqual(topics[0]["id"], "fav_animal_quest")
        self.assertIn("Dolphin", topics[0]["title"])

        # Thẻ 2: Ôn tập từ 'Brave'
        self.assertEqual(topics[1]["id"], "vocab_review")
        self.assertIn("Brave", topics[1]["title"])

        # Tất cả các thẻ đều có prompt_hint và emoji
        for t in topics:
            self.assertIn("title", t)
            self.assertIn("emoji", t)
            self.assertIn("color_hex", t)
            self.assertIn("prompt_hint", t)

    def test_api_child_topics_endpoint(self):
        """Kiểm tra REST API GET /api/child/topics"""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        child_id = "kid_api_topics_01"
        response = client.get(f"/api/child/topics?child_id={child_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["count"], 6)
    def test_dns_cache_assert_safe_url(self):
        """Kiểm tra cơ chế cache DNS tránh gọi lại socket.getaddrinfo"""
        from unittest.mock import patch

        # Lần 1: Gọi bình thường -> resolve DNS và lưu cache
        url = "https://kids.nationalgeographic.com/animals"
        self.assertTrue(self.safety.assert_safe_url(url))

        # Lần 2: Giả lập socket.getaddrinfo bị lỗi/không được gọi -> Vẫn trả về True từ Cache
        with patch("socket.getaddrinfo", side_effect=Exception("Should not be called when cached")):
            self.assertTrue(self.safety.assert_safe_url(url))

    def test_parent_pin_verification(self):
        """Kiểm tra xác thực và đổi mã PIN phụ huynh theo từng child_id riêng biệt"""
        child_id = "kid_pin_test_01"
        self.memory.get_or_create_profile(child_id)

        # Mặc định PIN là 1234
        self.assertTrue(self.memory.verify_parent_pin(child_id, "1234"))
        self.assertFalse(self.memory.verify_parent_pin(child_id, "0000"))

        # Đổi sang PIN mới 9999
        self.assertTrue(self.memory.set_parent_pin(child_id, "9999"))
        self.assertTrue(self.memory.verify_parent_pin(child_id, "9999"))
        self.assertFalse(self.memory.verify_parent_pin(child_id, "1234"))

    def test_api_parent_pin_auth(self):
        """Kiểm tra xác thực REST API bằng mã PIN phụ huynh (Góc Phụ Huynh trên App)"""
        from fastapi.testclient import TestClient
        import main

        # Trỏ main.memory_manager sang DB test tạm thời
        orig_mm = main.memory_manager
        main.memory_manager = self.memory
        try:
            client = TestClient(main.app)
            child_id = "kid_pin_api_01"
            self.memory.get_or_create_profile(child_id, default_name="Bé Bắp")
            self.memory.set_parent_pin(child_id, "5678")

            # 1. Test verify-pin endpoint
            res_verify_fail = client.post("/api/child/verify-pin", json={"child_id": child_id, "pin": "1234"})
            self.assertEqual(res_verify_fail.status_code, 200)
            self.assertFalse(res_verify_fail.json()["valid"])

            res_verify_ok = client.post("/api/child/verify-pin", json={"child_id": child_id, "pin": "5678"})
            self.assertEqual(res_verify_ok.status_code, 200)
            self.assertTrue(res_verify_ok.json()["valid"])

            # 2. Test get profile with X-Parent-PIN header
            res_profile_no_auth = client.get(f"/api/child/profile?child_id={child_id}")
            self.assertEqual(res_profile_no_auth.status_code, 401)

            res_profile_ok = client.get(f"/api/child/profile?child_id={child_id}", headers={"X-Parent-PIN": "5678"})
            self.assertEqual(res_profile_ok.status_code, 200)
            self.assertEqual(res_profile_ok.json()["name"], "Bé Bắp")

            # 3. Test update profile with X-Parent-PIN
            res_update_ok = client.post(
                f"/api/child/profile?child_id={child_id}",
                headers={"X-Parent-PIN": "5678"},
                json={"name": "Bé Bắp Siêu Nhân", "favorite_animal": "Lion"}
            )
            self.assertEqual(res_update_ok.status_code, 200)
            self.assertEqual(res_update_ok.json()["profile"]["name"], "Bé Bắp Siêu Nhân")
        finally:
            main.memory_manager = orig_mm

if __name__ == "__main__":
    unittest.main()
