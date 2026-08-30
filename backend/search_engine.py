"""
Knowledge Search Engine for Encyclopedia Mode.

Pipeline:
1. Safety filter (ChildSafetyGuard.evaluate_content) on the query.
2. Check in-memory LRU cache (TTL 1 hour).
3. If GOOGLE_CSE_ID + GOOGLE_CSE_KEY are configured → call Google Programmable
   Search Engine (CSE). Returns top N from the whole web restricted by the
   Search Engine's "Sites to search" list.
4. If CSE is unavailable / rate-limited / returns <2 results → fall back to
   Simple English Wikipedia (refactored from safety_guard.py).
5. Validate every URL against the kid-safe whitelist; drop non-compliant ones.
6. Truncate snippets to MAX_SNIPPET_CHARS and dedupe by URL.

This module is standalone — it does NOT depend on main.py, so it can be
imported from tests easily.
"""

import os
import re
import json
import time
import logging
import asyncio
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from threading import Lock

from safety_guard import ChildSafetyGuard

logger = logging.getLogger("digital-human-search")


class _TTLCache:
    """Tiny thread-safe LRU + TTL cache. Keys are normalized queries."""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 3600):
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self._max_size:
                # Drop oldest by insertion order (dict preserves it in py3.7+).
                oldest = next(iter(self._data))
                self._data.pop(oldest, None)
            self._data[key] = (time.time() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class KnowledgeSearchEngine:
    """
    Unified search interface for Doraemon's Encyclopedia Mode.

    Output contract (always):
        {
          "success": bool,
          "results": [
              {"title": str, "snippet": str, "source": str,
               "source_url": str, "rank": int}
          ],
          "source_backend": "cse" | "wikipedia" | "cache" | "none",
          "is_blocked": bool,
          "safe_message": Optional[str],
          "query": str
        }
    """

    MAX_SNIPPET_CHARS = 400
    CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
    WIKI_SUMMARY_URL = "https://simple.wikipedia.org/api/rest_v1/page/summary/{title}"
    WIKI_SEARCH_URL = (
        "https://simple.wikipedia.org/w/api.php?action=opensearch"
        "&format=json&limit=5&search={query}"
    )
    WIKI_VI_SUMMARY_URL = "https://vi.wikipedia.org/api/rest_v1/page/summary/{title}"
    WIKI_VI_SEARCH_URL = (
        "https://vi.wikipedia.org/w/api.php?action=opensearch"
        "&format=json&limit=5&search={query}"
    )
    USER_AGENT = (
        "DoraemonKidEducationBot/2.0 (Educational AI Tutor for Kids; "
        "contact: admin@human-digital.local)"
    )

    def __init__(self):
        self.cse_id = os.getenv("GOOGLE_CSE_ID", "").strip()
        self.cse_key = os.getenv("GOOGLE_CSE_KEY", "").strip()
        self.safety = ChildSafetyGuard()
        self.cache = _TTLCache(max_size=256, ttl_seconds=3600)

    def is_cse_configured(self) -> bool:
        """Returns True when both CSE env vars are present and non-empty."""
        return bool(self.cse_id and self.cse_key)

    @staticmethod
    def _normalize_query(q: str) -> str:
        """Lowercase, strip, collapse whitespace — used as cache key."""
        return re.sub(r"\s+", " ", q.strip().lower())

    def _cache_key(self, query: str, topic_hint: Optional[str], child_id: str = "default_child") -> str:
        """Cache key includes topic_hint + child_id so identical queries never
        collide across different hints or different children. This keeps child
        data isolated (each child has their own Doraemon memory)."""
        norm = self._normalize_query(query)
        hint = (topic_hint or "").strip().lower()
        child = child_id.strip().lower() or "default_child"
        parts = [norm]
        if hint:
            parts.append(f"hint={hint}")
        parts.append(f"child={child}")
        return "::".join(parts)

    # Mapping topic_hint → extra terms appended to the search query so the
    # backend ranks the intended domain higher. This makes topic_hint REAL
    # (previously it was accepted but silently ignored).
    _HINT_QUERY_TERMS = {
        "history": "history",
        "geography": "geography place",
        "science": "science",
        "nature": "animal nature",
        "space": "space astronomy",
        "famous_people": "biography",
    }

    def _apply_topic_hint(self, query: str, topic_hint: Optional[str]) -> str:
        """Return an enriched query biased by topic_hint for the web backends."""
        if not topic_hint:
            return query
        extra = self._HINT_QUERY_TERMS.get(topic_hint.strip().lower())
        return f"{query} {extra}".strip() if extra else query

    def _lookup_curated(
        self, query: str, topic_hint: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Highest-priority knowledge source: the hand-written, kid-safe curated
        base in vietnamese_history.py. Returns a normalized payload in the same
        shape as web results (single result) so downstream formatting is uniform.
        """
        try:
            from vietnamese_history import lookup_curated
            hit = lookup_curated(query)
            if not hit:
                return None
            entry, key, source = hit
            vi = entry.get("vi", "")
            en = entry.get("en", "")
            figures = entry.get("key_figures", [])
            title = figures[0] if figures else key.replace("_", " ").title()
            result = {
                "title": title,
                # Primary snippet in Vietnamese (child-facing), English kept
                # as a secondary field for the bilingual sprinkle.
                "snippet": self._truncate_snippet(vi) if vi else self._truncate_snippet(en),
                "source": source,
                "source_url": "",
                "rank": 1,
                "is_curated": True,
            }
            if en:
                result["snippet_en"] = self._truncate_snippet(en)
            return {
                "success": True,
                "results": [result],
                "source_backend": "curated",
                "is_blocked": False,
                "safe_message": None,
                "query": query,
            }
        except Exception as e:
            logger.warning(f"Curated lookup failed for '{query}': {e}")
            return None

    async def search(
        self,
        query: str,
        top_k: int = 3,
        topic_hint: Optional[str] = None,
        child_id: str = "default_child",
    ) -> Dict[str, Any]:
        """
        Async-friendly entry point. Wraps sync urllib calls in `asyncio.to_thread`
        so that large latency from external HTTP doesn't block the WS event loop.

        Pipeline:
        1. Safety filter the raw query.
        2. Curated knowledge base (highest accuracy, hand-written for kids).
        3. In-memory cache (keyed by query + topic_hint + child_id).
        4. Google CSE when configured (topic_hint biases the query).
        5. Wikipedia Simple English fallback.
        """
        query = (query or "").strip()
        if not query:
            return {
                "success": False,
                "results": [],
                "source_backend": "none",
                "is_blocked": False,
                "safe_message": "Empty query.",
                "query": query,
            }

        # 1. Safety filter
        is_safe, category, redirect = self.safety.evaluate_content(query, child_id)
        if not is_safe:
            self.safety._log_safety_event(
                child_id, f"KNOWLEDGE_{category or 'BLOCKED'}", query, "BLOCK_AND_REDIRECT"
            )
            return {
                "success": False,
                "results": [],
                "source_backend": "none",
                "is_blocked": True,
                "safe_message": redirect,
                "query": query,
            }

        # 2. Curated knowledge base first (hand-written, safest + most accurate).
        #    If it hits, skip web search entirely — curated facts are already
        #    kid-safe and don't need URL validation or content filtering.
        curated = self._lookup_curated(query, topic_hint)
        if curated is not None:
            self.safety._log_safety_event(
                child_id, "KNOWLEDGE_CURATED", query, "FOUND:curated"
            )
            return curated

        # 3. Cache — key includes topic_hint + child_id so the same query with
        #    different hints or different children never returns a mismatched
        #    cached payload.
        cache_key = self._cache_key(query, topic_hint, child_id)
        cached = self.cache.get(cache_key)
        if cached is not None:
            cached = dict(cached)
            cached["source_backend"] = "cache"
            cached["query"] = query
            return cached

        results: List[Dict[str, Any]] = []
        backend_used = "none"

        # 4. Try Google CSE first when configured (topic_hint biases ranking).
        if self.is_cse_configured():
            try:
                cse_results = await asyncio.to_thread(
                    self._search_google_cse, query, top_k, topic_hint
                )
                cse_results = self._validate_and_clean(cse_results, child_id)
                if len(cse_results) >= 2:
                    results = cse_results[:top_k]
                    backend_used = "cse"
                    logger.info(f"CSE returned {len(results)} results for '{query}'")
                else:
                    logger.info(
                        f"CSE returned only {len(cse_results)} results for "
                        f"'{query}', falling back to Wikipedia."
                    )
            except Exception as e:
                logger.warning(f"CSE search failed for '{query}': {e}")

        # 5. Fallback to Wikipedia (Vietnamese / Simple / English) in parallel
        if not results:
            try:
                wiki_results = await self._search_wikipedia(
                    query, top_k, topic_hint
                )
                wiki_results = self._validate_and_clean(wiki_results, child_id)
                results = wiki_results[:top_k]
                if results:
                    backend_used = "wikipedia"
                    logger.info(
                        f"Wikipedia returned {len(results)} results for '{query}'"
                    )
            except Exception as e:
                logger.error(f"Wikipedia search failed for '{query}': {e}")

        if not results:
            payload = {
                "success": False,
                "results": [],
                "source_backend": backend_used,
                "is_blocked": False,
                "safe_message": (
                    f"Doraemon không tìm thấy thông tin về '{query}'. "
                    "Bạn thử hỏi cách khác xem sao?"
                ),
                "query": query,
            }
        else:
            payload = {
                "success": True,
                "results": results,
                "source_backend": backend_used,
                "is_blocked": False,
                "safe_message": None,
                "query": query,
            }
            # Cache successful results only (1 hour TTL handled by _TTLCache)
            self.cache.set(cache_key, {k: v for k, v in payload.items() if k != "query"})

        return payload

    # ==================== Backends ====================

    def _clean_natural_query(self, query: str) -> str:
        """Loại bỏ các từ hỏi tự nhiên và dấu câu để trích xuất thực thể chính cho Wikipedia / Search API."""
        q = query.strip()
        patterns = [
            r"^(ai là|ai sinh ra|ai lập nên|ai sáng lập|kể về|kể cho em về|kể cho bé về|giải thích về|giải thích|cho mình hỏi về|cho em hỏi về|đố doraemon biết|bạn có biết|bạn biết gì về|nguồn gốc của|lịch sử của|thông tin về|tìm hiểu về|hãy nói về|có bao nhiêu|bao nhiêu|việt nam có bao nhiêu|tại sao|vì sao)\s+",
            r"\s+(là ai|ở đâu|vào năm nào|sinh năm bao nhiêu|như thế nào|tại sao|để làm gì|là gì|có gì đặc biệt|có bao nhiêu|gồm những gì|gồm những ai|gồm mấy loại|thế nào)\s*[\?\!\.]*$",
        ]
        cleaned = q
        for p in patterns:
            cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = cleaned.rstrip("?!. ").strip()
        return cleaned if len(cleaned) >= 2 else q

    def _search_google_cse(
        self, query: str, top_k: int, topic_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Calls Google Programmable Search Engine REST API. topic_hint is applied
        to bias the query toward the intended domain.
        """
        clean_q = self._clean_natural_query(query)
        params = {
            "key": self.cse_key,
            "cx": self.cse_id,
            "q": self._apply_topic_hint(clean_q, topic_hint),
            "num": min(top_k, 10),
        }
        url = f"{self.CSE_ENDPOINT}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url, headers={"User-Agent": self.USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data.get("items", []) or []
        results: List[Dict[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            title = (item.get("title") or "").strip()
            snippet = (item.get("snippet") or "").strip()
            link = (item.get("link") or "").strip()
            results.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "source": item.get("displayLink") or "Google CSE",
                    "source_url": link,
                    "rank": idx,
                }
            )
        return results

    def _is_vietnamese(self, text: str) -> bool:
        """Kiểm tra xem câu hỏi có phải tiếng Việt không (cả có dấu và không dấu)."""
        vn_chars = "àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
        if any(c in vn_chars for c in text.lower()):
            return True
        vn_words = {"la", "cua", "va", "trong", "nguoi", "nuoc", "song", "nui", "vua", "bac", "nam", "thanh", "tran", "hai", "ba", "trung", "le", "ly", "dinh", "nguyen", "quang", "ho", "chi", "minh", "khung", "long"}
        tokens = set(text.lower().split())
        return bool(tokens & vn_words)

    async def _search_wikipedia(
        self, query: str, top_k: int, topic_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Wikipedia multi-tier async parallel search:
        1. Tiếng Việt (vi.wikipedia.org)
        2. Simple English Wikipedia (simple.wikipedia.org)
        3. Standard English Wikipedia fallback (en.wikipedia.org)
        """
        clean_query = self._clean_natural_query(query)
        is_vn = self._is_vietnamese(clean_query)

        # 1. Tiếng Việt
        if is_vn:
            results = await self._fetch_wiki_combined(
                query=clean_query,
                lang="vi",
                source_name="Wikipedia (Tiếng Việt)",
                top_k=top_k,
            )
            if results:
                return results

        # 2. Simple English Wikipedia
        results = await self._fetch_wiki_combined(
            query=clean_query,
            lang="simple",
            source_name="Wikipedia (Simple English)",
            top_k=top_k,
        )
        if results:
            return results

        # 3. Standard English Wikipedia fallback
        results = await self._fetch_wiki_combined(
            query=clean_query,
            lang="en",
            source_name="Wikipedia (English)",
            top_k=top_k,
        )
        return results

    def _sync_opensearch(self, query: str, lang: str) -> List[str]:
        """OpenSearch theo tiêu đề mục từ trên Wikipedia."""
        try:
            opensearch_url = (
                f"https://{lang}.wikipedia.org/w/api.php?action=opensearch"
                f"&format=json&limit=5&search={urllib.parse.quote(query)}"
            )
            req = urllib.request.Request(
                opensearch_url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if len(data) >= 2 and data[1]:
                return data[1]
        except Exception as e:
            logger.debug(f"Opensearch failed for '{query}' on {lang}.wikipedia: {e}")
        return []

    def _sync_fulltext_search(self, query: str, lang: str) -> List[str]:
        """Fulltext search theo nội dung trên Wikipedia."""
        try:
            ft_url = (
                f"https://{lang}.wikipedia.org/w/api.php?action=query"
                f"&list=search&format=json&srlimit=5&srsearch={urllib.parse.quote(query)}"
            )
            req = urllib.request.Request(
                ft_url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            search_items = data.get("query", {}).get("search", []) or []
            return [item.get("title") for item in search_items if item.get("title")]
        except Exception as e:
            logger.debug(f"Fulltext search failed for '{query}' on {lang}.wikipedia: {e}")
        return []

    async def _fetch_wiki_combined(
        self,
        query: str,
        lang: str,
        source_name: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm Wikipedia bất đồng bộ song song:
        - OpenSearch / Fulltext search để lấy danh sách tiêu đề.
        - Lấy toàn bộ bản tóm tắt (summary) đồng thời bằng asyncio.gather.
        """
        # Bước 1: OpenSearch
        titles = await asyncio.to_thread(self._sync_opensearch, query, lang)

        # Bước 2: Nếu OpenSearch không có -> Full-text search
        if not titles:
            titles = await asyncio.to_thread(self._sync_fulltext_search, query, lang)

        if not titles:
            return []

        # Bước 3: Lấy tóm tắt (Summary) song song qua REST API
        selected_titles = titles[:top_k]
        summary_endpoint = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{{title}}"
        
        # Bắn đồng thời các request lấy tóm tắt để giảm độ trễ từ 3x xuống 1x
        summary_tasks = [
            asyncio.to_thread(self._wikipedia_summary, title, summary_endpoint)
            for title in selected_titles
        ]
        summaries = await asyncio.gather(*summary_tasks, return_exceptions=True)

        results: List[Dict[str, Any]] = []
        base_wiki_url = f"https://{lang}.wikipedia.org/wiki/"

        for idx, (title, summary) in enumerate(zip(selected_titles, summaries), start=1):
            if isinstance(summary, str) and summary.strip():
                results.append(
                    {
                        "title": title,
                        "snippet": summary,
                        "source": source_name,
                        "source_url": f"{base_wiki_url}{urllib.parse.quote(title)}",
                        "rank": idx,
                    }
                )
        return results

    def _wikipedia_summary(
        self, title: str, summary_endpoint: Optional[str] = None
    ) -> Optional[str]:
        """Fetch plain-text extract for a Wikipedia title, truncate to MAX_SNIPPET_CHARS."""
        try:
            endpoint = summary_endpoint or self.WIKI_SUMMARY_URL
            url = endpoint.format(title=urllib.parse.quote(title))
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            extract = (data.get("extract") or "").strip()
            if not extract:
                return None
            return self._truncate_snippet(extract)
        except Exception as e:
            logger.warning(f"Wikipedia summary fetch failed for '{title}': {e}")
            return None

    # ==================== Helpers ====================

    def _truncate_snippet(self, text: str) -> str:
        """Truncate at the last sentence boundary near MAX_SNIPPET_CHARS."""
        if len(text) <= self.MAX_SNIPPET_CHARS:
            return text
        truncated = text[: self.MAX_SNIPPET_CHARS]
        last_period = truncated.rfind(". ")
        if last_period > 100:
            return truncated[: last_period + 1]
        return truncated + "..."

    def _validate_and_clean(
        self, results: List[Dict[str, Any]], child_id: str = "default_child"
    ) -> List[Dict[str, Any]]:
        """
        Two-stage safety on returned results:
        1. URL whitelist check (drop unsafe URLs).
        2. Content filter on the snippet itself using evaluate_educational_content
           (cho phép ngữ cảnh lịch sử giáo dục, loại bỏ nội dung khiêu dâm/tự hại/bạo lực kinh dị).
        """
        cleaned: List[Dict[str, Any]] = []
        for r in results:
            url = r.get("source_url", "")
            if not url:
                continue
            if not self.safety.assert_safe_url(url):
                logger.warning(f"Dropping unsafe URL from search results: {url}")
                continue

            snippet = self._truncate_snippet(r.get("snippet", "").strip())
            # Kiểm duyệt nội dung bằng bộ lọc giáo dục chuyên biệt
            is_safe, category = self.safety.evaluate_educational_content(snippet, child_id)
            if not is_safe:
                logger.warning(
                    f"Dropping result with unsafe snippet ({category}): {url}"
                )
                continue

            cleaned.append(
                {
                    "title": r.get("title", "").strip(),
                    "snippet": snippet,
                    "source": r.get("source", "").strip(),
                    "source_url": url,
                }
            )
        for i, r in enumerate(cleaned, start=1):
            r["rank"] = i
        return cleaned


# Module-level singleton (mirrors pattern of safety_guard + memory_manager)
search_engine = KnowledgeSearchEngine()
