"""
Research tools used by the agent nodes.

Each tool wraps a data source (DuckDuckGo web search, Wikipedia, arXiv)
and returns a list of Source objects.  All tools degrade gracefully so the
pipeline never crashes on a network error.
"""
from __future__ import annotations

import re
import time
import hashlib
import logging
from typing import List, Optional

from schemas import Source

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:8]


def _truncate(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo — no API key required)
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 5) -> List[Source]:
    """Search the web using DuckDuckGo."""
    sources: List[Source] = []
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        for r in results:
            url = r.get("href", r.get("url", ""))
            title = r.get("title", "")
            body = r.get("body", r.get("snippet", ""))
            sources.append(Source(
                id=_make_id(url or title),
                url=url,
                title=title,
                content=_truncate(body),
                source_type="web",
                credibility_score=0.6,
            ))
    except Exception as e:
        logger.warning(f"Web search failed for '{query}': {e}")
    return sources


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def wikipedia_search(query: str, max_results: int = 3) -> List[Source]:
    """Search Wikipedia for relevant articles."""
    sources: List[Source] = []
    try:
        import wikipedia as wiki
        wiki.set_lang("en")
        search_results = wiki.search(query, results=max_results)
        for title in search_results[:max_results]:
            try:
                page = wiki.page(title, auto_suggest=False)
                summary = _truncate(page.summary, 1500)
                sources.append(Source(
                    id=_make_id(page.url),
                    url=page.url,
                    title=page.title,
                    content=summary,
                    source_type="wikipedia",
                    credibility_score=0.75,
                    metadata={"categories": page.categories[:5]},
                ))
                time.sleep(0.2)          # be polite
            except Exception as inner:
                logger.debug(f"Wikipedia page error for '{title}': {inner}")
    except Exception as e:
        logger.warning(f"Wikipedia search failed for '{query}': {e}")
    return sources


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

def arxiv_search(query: str, max_results: int = 3) -> List[Source]:
    """Search arXiv for academic papers."""
    sources: List[Source] = []
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        for paper in client.results(search):
            abstract = _truncate(paper.summary, 1500)
            sources.append(Source(
                id=_make_id(str(paper.entry_id)),
                url=str(paper.entry_id),
                title=paper.title,
                content=abstract,
                source_type="arxiv",
                credibility_score=0.85,
                metadata={
                    "authors": [str(a) for a in paper.authors[:5]],
                    "published": str(paper.published)[:10],
                    "categories": paper.categories,
                },
            ))
    except Exception as e:
        logger.warning(f"arXiv search failed for '{query}': {e}")
    return sources


# ---------------------------------------------------------------------------
# Aggregate tool
# ---------------------------------------------------------------------------

def multi_source_search(
    query: str,
    max_results: int = 5,
    include_web: bool = True,
    include_wiki: bool = True,
    include_arxiv: bool = True,
) -> List[Source]:
    """Run all enabled source tools and deduplicate by URL."""
    seen_urls: set = set()
    all_sources: List[Source] = []

    def add(srcs: List[Source]):
        for s in srcs:
            key = s.url or s.title
            if key and key not in seen_urls:
                seen_urls.add(key)
                all_sources.append(s)

    per_tool = max(2, max_results // 3)

    if include_web:
        add(web_search(query, per_tool))
    if include_wiki:
        add(wikipedia_search(query, min(2, per_tool)))
    if include_arxiv:
        add(arxiv_search(query, min(2, per_tool)))

    return all_sources[:max_results]
