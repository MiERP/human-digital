import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main


class TestProactiveConversation(unittest.TestCase):
    def test_pending_child_reply_blocks_proactive_nudge(self):
        state = {
            "last_user_at": 100.0,
            "last_bot_at": 90.0,
            "user_turn_open": False,
            "reply_pending": True,
            "nudges_since_user": 0,
            "nudges_total": 0,
            "bot_asked_question": False,
        }
        self.assertFalse(main.proactive_nudge_due(state, now=120.0))
        state["reply_pending"] = False
        self.assertTrue(main.proactive_nudge_due(state, now=120.0))

    def test_nudge_varies_and_stays_out_of_lesson_mode(self):
        profile = {"favorite_animal": "mèo", "hobbies": ["vẽ"]}
        seen = set()
        for _ in range(20):
            text = main.build_proactive_nudge(profile, 0)
            self.assertIn("HỆ THỐNG", text)
            self.assertIn("một người bạn", text)
            self.assertNotIn("đố bé", text.lower())
            self.assertNotIn("luyện tiếng Anh", text)
            seen.add(text)
        self.assertGreater(len(seen), 1)

    def test_repeated_silence_backs_off_instead_of_nagging(self):
        text = main.build_proactive_nudge({}, 2)
        self.assertIn("Đừng hỏi dồn", text)
        self.assertIn("để bé yên", text)


if __name__ == "__main__":
    unittest.main()
