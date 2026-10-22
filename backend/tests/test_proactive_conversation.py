import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main


class TestProactiveConversation(unittest.TestCase):
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
