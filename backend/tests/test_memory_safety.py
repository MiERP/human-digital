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

if __name__ == "__main__":
    unittest.main()
