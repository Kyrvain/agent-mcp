from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from .models import CrawlResult


@dataclass(slots=True)
class ProductListEntry:
    _id: str
    name: str
    client_name: str = ""
    introduction: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class ProductSearchResult:
    query: str
    matched_entry: ProductListEntry | None = None
    confidence: float = 0.0
    candidates: list[ProductListEntry] = field(default_factory=list)
    detail_url: str | None = None
    warnings: list[str] = field(default_factory=list)


def parse_product_list(crawl: CrawlResult) -> list[ProductListEntry]:
    """Extract product list from captured dse/service.do listing responses."""
    entries: list[ProductListEntry] = []
    seen: set[str] = set()

    for response in crawl.responses:
        if "dse/service.do" not in response.url:
            continue
        try:
            body = json.loads(response.body)
        except json.JSONDecodeError:
            continue
        hits = body.get("hits")
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            _id = hit.get("_id", "")
            if not _id or _id in seen:
                continue
            src = hit.get("_source") or {}
            if not isinstance(src, dict):
                continue
            seen.add(_id)
            entries.append(
                ProductListEntry(
                    _id=str(_id),
                    name=str(src.get("name", "")).strip(),
                    client_name=str(src.get("client_name", "")).strip(),
                    introduction=str(src.get("introduction", "")).strip(),
                    raw=src,
                )
            )
    return entries


async def match_product(
    query: str,
    entries: list[ProductListEntry],
    _settings: object | None = None,
) -> tuple[ProductListEntry | None, float, list[str]]:
    """Match user query to the best product entry using keyword scoring."""
    if not entries:
        return None, 0.0, ["列表页未返回任何产品。"]

    return _match_with_keywords(query, entries)


def _match_with_keywords(
    query: str,
    entries: list[ProductListEntry],
) -> tuple[ProductListEntry | None, float, list[str]]:
    """Keyword-based product matching using bigram overlap for CJK text."""
    query_lower = query.strip().lower()
    if not query_lower:
        return None, 0.0, ["查询为空。"]

    best_entry: ProductListEntry | None = None
    best_score = 0.0

    for entry in entries:
        name_lower = entry.name.lower()
        intro_lower = entry.introduction.lower()
        client_lower = entry.client_name.lower()

        score = 0.0

        # Exact name match
        if query_lower == name_lower:
            score += 10.0

        # Query as substring of name
        if query_lower in name_lower:
            score += 5.0

        # Name as substring of query
        if name_lower in query_lower:
            score += 5.0

        # Token / bigram overlap
        for token in _tokenize(query_lower):
            if token in name_lower:
                score += 3.0
            if token in intro_lower:
                score += 1.0
            if token in client_lower:
                score += 0.5

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_score < 3.0:
        warnings = [
            f"关键词匹配分数过低（{best_score:.1f}）。可用产品："
            + ", ".join(e.name for e in entries[:10])
        ]
        return None, 0.0, warnings

    confidence = min(best_score / 10.0, 1.0)
    return best_entry, confidence, []


def _tokenize(text: str) -> list[str]:
    """Tokenize CJK text into bigrams and whitespace-delimited tokens."""
    tokens: list[str] = []
    # Whitespace-delimited
    tokens.extend(text.split())
    # Character bigrams for CJK
    stripped = re.sub(r"\s+", "", text)
    for i in range(len(stripped) - 1):
        tokens.append(stripped[i : i + 2])
    return tokens


def build_detail_url(entry: ProductListEntry) -> str:
    encoded_name = urllib.parse.quote(entry.name, safe="")
    return (
        f"https://bjedures.bjedu.cn/ggzypt/#/ai/mark/detail"
        f"?id={entry._id}&name={encoded_name}"
    )
