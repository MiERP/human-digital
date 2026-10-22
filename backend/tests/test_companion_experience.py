import os
import asyncio
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from emotion_engine import EmotionEngine
from memory_manager import MemoryManager
from personas import build_companion_prompt, resolve_persona
from session_lifecycle import wait_for_conversation


class TestCompanionExperience(unittest.TestCase):
    def test_persona_has_stable_distinct_conversation_style(self):
        playful = build_companion_prompt(resolve_persona({"companion_persona": "boy_green"}))
        thoughtful = build_companion_prompt(resolve_persona({"companion_persona": "girl_purple"}))
        self.assertIn("Siro", playful)
        self.assertIn("Luna", thoughtful)
        self.assertNotEqual(playful, thoughtful)
        self.assertIn("phản biện", playful)
        self.assertIn("AI", thoughtful)

    def test_shared_moment_survives_and_is_selected_for_next_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "child.db"))
            memory.get_or_create_profile("kid")
            memory.add_episodic_memory("kid", "FACT", "một chi tiết cũ", importance=5)
            memory.save_shared_moment("kid", "  Bé và Siro cược về T-rex biết bay  ")
            context = memory.build_memory_context("kid")
            self.assertIn("Bé và Siro cược về T-rex biết bay", context)
            self.assertIn("kỷ niệm chung", context)
            self.assertEqual(len(memory.get_shared_moments("kid")), 1)

    def test_blank_shared_moment_is_not_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "child.db"))
            self.assertIsNone(memory.save_shared_moment("kid", "  "))
            self.assertEqual(memory.get_shared_moments("kid"), [])

    def test_shared_moment_rejects_private_details_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager(db_path=os.path.join(tmp, "child.db"))
            self.assertIsNone(memory.save_shared_moment("kid", "Số điện thoại mẹ là 0912345678"))
            self.assertIsNone(memory.save_shared_moment("kid", "Mật khẩu của bé là abc"))
            self.assertIsNotNone(memory.save_shared_moment("kid", "Hai bạn cùng đặt tên cho tàu vũ trụ"))
            self.assertIsNone(memory.save_shared_moment("kid", "Hai bạn cùng đặt tên cho tàu vũ trụ"))
            self.assertEqual(len(memory.get_shared_moments("kid")), 1)

    def test_emotion_recovers_without_resetting_on_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            emotion = EmotionEngine(data_dir=tmp)
            emotion.start_session("kid")
            emotion.set_emotion("kid", emotion="surprised", energy="excited")
            next_session = EmotionEngine(data_dir=tmp).start_session("kid")
            self.assertEqual(next_session["emotion"], "surprised")
            self.assertEqual(next_session["energy"], "excited")

    def test_background_timekeeper_does_not_end_conversation(self):
        async def scenario():
            client_finished = asyncio.Event()
            async def client():
                await client_finished.wait()
            async def gemini():
                await asyncio.Event().wait()
            async def timekeeper():
                await asyncio.sleep(0)

            task = asyncio.create_task(wait_for_conversation(
                asyncio.create_task(client()), asyncio.create_task(gemini()),
                asyncio.create_task(timekeeper()),
            ))
            await asyncio.sleep(0.01)
            self.assertFalse(task.done())
            client_finished.set()
            await asyncio.wait_for(task, 1)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
