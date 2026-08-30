"""
Unit tests for KnowledgeSearchEngine (Encyclopedia Mode backend).

Covers:
  - Safety filtering (block unsafe queries before any backend is called)
  - Wikipedia fallback when CSE is unconfigured
  - URL whitelist validation drops unsafe results
  - Snippet truncation at sentence boundary
  - In-memory TTL cache deduplicates repeated queries
  - Graceful handling of CSE error / rate-limit → fallback Wikipedia
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from search_engine import KnowledgeSearchEngine


class TestKnowledgeSearchEngine(unittest.IsolatedAsyncioTestCase):
    """Asynchronous tests because KnowledgeSearchEngine.search() is async."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.test_dir, "test_safety.log")
        # Force-cache fresh each test by injecting fresh instance
        self.engine = KnowledgeSearchEngine()
        self.engine.safety = __import__("safety_guard").ChildSafetyGuard(
            log_path=self.log_path
        )
        self.engine.cache.clear()

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ==================== Safety ====================

    async def test_search_blocks_unsafe_query(self):
        """Violence / adult / dangerous queries must return is_blocked without hitting backend."""
        is_safe, category, _ = self.engine.safety.evaluate_content(
            "Tell me about guns and how to kill monsters", child_id="test"
        )
        self.assertFalse(is_safe)
        self.assertEqual(category, "VIOLENCE")

        # Now: search() should reflect the block even when backend would otherwise succeed
        res = await self.engine.search("how to kill with a knife", child_id="test")
        self.assertTrue(res["is_blocked"])
        self.assertEqual(res["results"], [])
        self.assertIsNotNone(res["safe_message"])

    async def test_search_blocks_personal_info_query(self):
        """PII queries must be blocked before hitting any backend."""
        res = await self.engine.search("My password 123456", child_id="test")
        self.assertTrue(res["is_blocked"])

    # ==================== Wikipedia fallback (no CSE) ====================

    async def test_search_wikipedia_fallback_when_cse_disabled(self):
        """When GOOGLE_CSE_ID/KEY are empty, must use Wikipedia without raising."""
        # We can't guarantee Wikipedia is reachable in CI; mock via wikipedia_search helpers.
        with patch.object(
            self.engine, "_search_wikipedia", return_value=[
                {
                    "title": "Blue whale",
                    "snippet": "The blue whale is the largest animal ever.",
                    "source": "Wikipedia (Simple English)",
                    "source_url": "https://simple.wikipedia.org/wiki/Blue_whale",
                    "rank": 1,
                }
            ]
        ) as mock_wiki:
            res = await self.engine.search("why is the sky blue")
            self.assertTrue(res["success"])
            self.assertEqual(res["source_backend"], "wikipedia")
            self.assertEqual(len(res["results"]), 1)
            self.assertEqual(res["results"][0]["title"], "Blue whale")
            self.assertIn("largest animal", res["results"][0]["snippet"])
            mock_wiki.assert_called_once()

    async def test_cse_disabled_does_not_call_cse(self):
        """Internal: when CSE env is empty, _search_google_cse must never be called."""
        self.assertFalse(self.engine.is_cse_configured())
        with patch.object(self.engine, "_search_google_cse") as mock_cse, \
             patch.object(
                 self.engine, "_search_wikipedia",
                 return_value=[{
                     "title": "Test",
                     "snippet": "Test snippet",
                     "source": "Wikipedia",
                     "source_url": "https://simple.wikipedia.org/wiki/Test",
                     "rank": 1,
                 }]
             ):
            res = await self.engine.search("anything")
            mock_cse.assert_not_called()
            self.assertEqual(res["source_backend"], "wikipedia")

    # ==================== CSE primary path (mocked) ====================

    async def test_search_cse_when_configured_and_returns_enough(self):
        """When CSE is configured and returns >= 2 results, must use CSE only."""
        self.engine.cse_id = "fake-cx"
        self.engine.cse_key = "fake-key"
        cse_results = [
            {
                "title": "Tokyo",
                "snippet": "Tokyo is the capital of Japan ..." * 5,
                "source": "en.wikipedia.org",
                "source_url": "https://en.wikipedia.org/wiki/Tokyo",
                "rank": 1,
            },
            {
                "title": "Tokyo - Kiddle",
                "snippet": "Kiddle says Tokyo is the capital of Japan ...",
                "source": "kiddle.co",
                "source_url": "https://kids.kiddle.co/Tokyo",
                "rank": 2,
            },
            {
                "title": "Tokyo - Britannica",
                "snippet": "Britannica entry for Tokyo ...",
                "source": "britannica.com",
                "source_url": "https://www.britannica.com/place/Tokyo",
                "rank": 3,
            },
        ]
        with patch.object(self.engine, "_search_google_cse", return_value=cse_results), \
             patch.object(self.engine, "_search_wikipedia") as mock_wiki:
            res = await self.engine.search("capital of Japan")
            self.assertEqual(res["source_backend"], "cse")
            self.assertEqual(len(res["results"]), 3)
            mock_wiki.assert_not_called()

    async def test_search_cse_insufficient_results_falls_back_to_wikipedia(self):
        """When CSE returns < 2 results, must fall back to Wikipedia to keep answer rich."""
        self.engine.cse_id = "fake-cx"
        self.engine.cse_key = "fake-key"
        cse_results = [
            {
                "title": "Only one result",
                "snippet": "Only one",
                "source": "wikipedia.org",
                "source_url": "https://en.wikipedia.org/wiki/Foo",
                "rank": 1,
            }
        ]
        with patch.object(self.engine, "_search_google_cse", return_value=cse_results), \
             patch.object(
                 self.engine, "_search_wikipedia",
                 return_value=[{
                     "title": "Foo Wikipedia",
                     "snippet": "Foo extended info.",
                     "source": "Wikipedia",
                     "source_url": "https://simple.wikipedia.org/wiki/Foo",
                     "rank": 1,
                 }]
             ) as mock_wiki:
            res = await self.engine.search("Foo history")
            self.assertEqual(res["source_backend"], "wikipedia")
            mock_wiki.assert_called_once()

    async def test_search_handles_cse_exception(self):
        """CSE throwing must not crash; fall back to Wikipedia gracefully."""
        self.engine.cse_id = "fake-cx"
        self.engine.cse_key = "fake-key"
        with patch.object(
            self.engine, "_search_google_cse",
            side_effect=Exception("HTTP 429"),
        ), patch.object(
            self.engine, "_search_wikipedia",
            return_value=[{
                "title": "Recovery",
                "snippet": "Wikipedia recovered.",
                "source": "Wikipedia",
                "source_url": "https://simple.wikipedia.org/wiki/Recovery",
                "rank": 1,
            }],
        ):
            res = await self.engine.search("recovery")
            self.assertTrue(res["success"])
            self.assertEqual(res["source_backend"], "wikipedia")

    # ==================== URL safety ====================

    async def test_search_validates_and_drops_unsafe_urls(self):
        """Results with URLs outside the whitelist must be filtered out."""
        results_with_mixed = [
            {
                "title": "Safe Wikipedia",
                "snippet": "OK",
                "source": "wikipedia",
                "source_url": "https://simple.wikipedia.org/wiki/Safe",
                "rank": 1,
            },
            {
                "title": "Unsafe Site",
                "snippet": "Should drop",
                "source": "bad",
                "source_url": "https://malicious-site.com/exploit",
                "rank": 2,
            },
        ]
        cleaned = self.engine._validate_and_clean(results_with_mixed)
        titles = [r["title"] for r in cleaned]
        self.assertIn("Safe Wikipedia", titles)
        self.assertNotIn("Unsafe Site", titles)
        # Ranks re-assigned 1..N
        self.assertEqual([r["rank"] for r in cleaned], [1])

    # ==================== Snippet truncation ====================

    def test_truncate_snippet_short_unchanged(self):
        short = "Hello world."
        self.assertEqual(self.engine._truncate_snippet(short), short)

    def test_truncate_snippet_cuts_at_last_sentence(self):
        long = ("Sentence one. " * 50).strip()
        out = self.engine._truncate_snippet(long)
        self.assertLessEqual(len(out), self.engine.MAX_SNIPPET_CHARS + 3)
        # Must not end mid-word
        self.assertTrue(out.endswith(".") or out.endswith("..."))

    # ==================== Cache ====================

    async def test_search_caches_results(self):
        """Repeated identical queries must hit cache (no second backend call)."""
        with patch.object(
            self.engine, "_search_wikipedia",
            return_value=[{
                "title": "Cached Topic",
                "snippet": "Cached.",
                "source": "Wikipedia",
                "source_url": "https://simple.wikipedia.org/wiki/Cached",
                "rank": 1,
            }],
        ) as mock_wiki:
            res1 = await self.engine.search("same query")
            res2 = await self.engine.search("same query")
            self.assertTrue(res1["success"])
            self.assertEqual(res2["source_backend"], "cache")
            # Backend hit only once
            self.assertEqual(mock_wiki.call_count, 1)

    async def test_empty_query_returns_failure(self):
        res = await self.engine.search("")
        self.assertFalse(res["success"])
        self.assertEqual(res["results"], [])

    # ==================== Curated Knowledge & Unaccented Lookups ====================

    async def test_curated_lookup_unaccented_and_aliases(self):
        """Unaccented queries like 'ngo quyen', 'dinh tien hoang', 'mat troi', 'vinh ha long' must hit curated knowledge."""
        test_queries = [
            ("ngo quyen", "Ngô Quyền"),
            ("dinh tien hoang", "Đinh Bộ Lĩnh"),
            ("mat troi", "Mặt Trời"),
            ("dien bien phu", "Điện Biên Phủ"),
            ("son doong", "Sơn Đoòng"),
            ("he mat troi", "Hệ Mặt Trời"),
            ("quang hop", "Quang hợp"),
            ("ai la bac ho", "Hồ Chí Minh"),
        ]
        for query, expected_keyword in test_queries:
            res = await self.engine.search(query)
            self.assertTrue(res["success"], f"Failed for query: {query}")
            self.assertEqual(res["source_backend"], "curated", f"Expected curated for {query}")
            self.assertIn(expected_keyword, res["results"][0]["snippet"] + res["results"][0]["title"])

    def test_clean_natural_query(self):
        """Natural language question patterns should be stripped."""
        self.assertEqual(self.engine._clean_natural_query("Ai là Ngô Quyền?"), "Ngô Quyền")
        self.assertEqual(self.engine._clean_natural_query("Kể cho em về Vịnh Hạ Long"), "Vịnh Hạ Long")
        self.assertEqual(self.engine._clean_natural_query("Bác Hồ sinh năm bao nhiêu?"), "Bác Hồ")
        self.assertEqual(self.engine._clean_natural_query("Đố Doraemon biết Mặt Trời là gì?"), "Mặt Trời")

    def test_educational_safety_allows_history_snippets(self):
        """Historical snippets containing battle/war/invader terms must NOT be dropped."""
        history_snippet = (
            "Ngô Quyền dùng kế cắm cọc nhọn dưới lòng sông Bạch Đằng, đánh tan quân Nam Hán "
            "giành lại độc lập cho dân tộc. Tướng giặc bị giết chết trong trận đánh."
        )
        is_safe, category = self.engine.safety.evaluate_educational_content(history_snippet)
        self.assertTrue(is_safe)
        self.assertIsNone(category)

        # Extreme non-educational violence still blocked
        violent_snippet = "Hướng dẫn tự tử cắt cổ tay bằng dao lam sắc nhọn."
        is_safe_v, cat_v = self.engine.safety.evaluate_educational_content(violent_snippet)
        self.assertFalse(is_safe_v)
        self.assertEqual(cat_v, "VIOLENCE")


if __name__ == "__main__":
    unittest.main()
