import os
import sys
import unittest
import tempfile
import shutil

# Thêm thư mục backend vào sys.path (giống test_memory_safety).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from memory_manager import MemoryManager
from personas import resolve_persona, normalize_gender, default_persona_id_for_gender


class TestPersonaResolution(unittest.TestCase):
    def test_normalize_gender_variants(self):
        self.assertEqual(normalize_gender("Bé trai"), "male")
        self.assertEqual(normalize_gender("Nam"), "male")
        self.assertEqual(normalize_gender("be gai"), "female")
        self.assertEqual(normalize_gender("Nữ"), "female")
        self.assertEqual(normalize_gender(""), "")

    def test_default_persona_by_gender(self):
        self.assertEqual(default_persona_id_for_gender("male"), "boy_blue")
        self.assertEqual(default_persona_id_for_gender("Bé gái"), "girl_pink")

    def test_resolve_persona_default_and_override(self):
        default_persona = resolve_persona({"gender": "female"})
        self.assertEqual(default_persona["id"], "girl_pink")
        self.assertEqual(default_persona["gender"], "female")
        self.assertTrue(default_persona["name"])

        overridden = resolve_persona({
            "gender": "male",
            "companion_persona": "girl_purple",
            "companion_name": "Luna Xinh",
            "companion_voice": "Kore",
        })
        self.assertEqual(overridden["id"], "girl_purple")
        self.assertEqual(overridden["name"], "Luna Xinh")
        self.assertEqual(overridden["gender"], "female")
        self.assertEqual(overridden["voice"], "Kore")


class TestLearningPlan(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = MemoryManager(db_path=os.path.join(self.test_dir, "test.db"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_upsert_get_and_contract(self):
        self.assertIsNone(self.memory.get_learning_plan("kid_plan"))

        plan = self.memory.upsert_learning_plan(
            "kid_plan",
            days=["mon", "Wed", "fri"],
            start_time="19:00",
            duration_minutes=20,
            focus_topics=["Animals"],
            weekly_goal="10 từ về động vật",
        )
        self.assertEqual(plan["days"], ["mon", "wed", "fri"])
        self.assertEqual(plan["start_time"], "19:00")
        self.assertEqual(plan["duration_minutes"], 20)
        self.assertTrue(plan["is_active"])

        fetched = self.memory.get_learning_plan("kid_plan")
        self.assertEqual(fetched["focus_topics"], ["Animals"])

        contract = self.memory.build_learning_contract("kid_plan")
        self.assertIn("Learning Plan", contract)
        self.assertIn("19:00", contract)
        self.assertIn("KHÔNG tự nhắc lịch", contract)

        # Learning is opt-in: without a plan the prompt must not mention it at all.
        self.assertEqual(self.memory.build_learning_contract("kid_none"), "")

    def test_adherence_counts(self):
        self.memory.upsert_learning_plan("kid_ad", days=["mon", "wed", "fri"], start_time="19:00")
        adherence = self.memory.get_plan_adherence("kid_ad", days=7)
        self.assertTrue(adherence["has_plan"])
        self.assertGreaterEqual(adherence["planned"], 1)

    def test_plan_cascade_delete(self):
        self.memory.update_profile("kid_del", {"name": "Bé"})
        self.memory.upsert_learning_plan("kid_del", days=["tue"], start_time="18:00")
        self.memory.delete_all_child_data("kid_del")
        self.assertIsNone(self.memory.get_learning_plan("kid_del"))


if __name__ == "__main__":
    unittest.main()
