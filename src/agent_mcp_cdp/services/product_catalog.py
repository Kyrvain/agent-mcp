from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Settings
from ..models import CrawlResult
from ..product_search import (
    ProductListEntry,
    parse_product_list,
    product_entry_from_dict,
    product_entry_to_dict,
)

CATALOG_CACHE_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ProductCatalog:
    entries: list[ProductListEntry]
    cache_path: Path
    loaded_from_cache: bool
    refreshed: bool
    generated_at: str | None = None
    crawl: CrawlResult | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_path": str(self.cache_path),
            "loaded_from_cache": self.loaded_from_cache,
            "refreshed": self.refreshed,
            "generated_at": self.generated_at,
            "count": len(self.entries),
            "warnings": list(self.warnings),
            "products": [product_entry_to_dict(entry) for entry in self.entries],
        }


class ProductCatalogService:
    def __init__(self, settings: Settings, crawler: Any) -> None:
        self.settings = settings
        self.crawler = crawler

    async def get_catalog(
        self,
        *,
        force_refresh: bool = False,
        output_dir: Path | None = None,
    ) -> ProductCatalog:
        cache_path = self.settings.product_catalog_cache_path
        if not force_refresh:
            cached = load_catalog_cache(cache_path)
            if cached is not None and cached.entries:
                return cached

        crawl, entries = await self._fetch_catalog(output_dir)
        generated_at = _now()
        save_catalog_cache(
            cache_path,
            entries,
            source_url=self.settings.listing_url,
            generated_at=generated_at,
        )
        warnings = [] if entries else ["未能从页面提取到任何产品。请确认网站可访问。"]
        return ProductCatalog(
            entries=entries,
            cache_path=cache_path,
            loaded_from_cache=False,
            refreshed=True,
            generated_at=generated_at,
            crawl=crawl,
            warnings=warnings,
        )

    async def _fetch_catalog(
        self,
        output_dir: Path | None,
    ) -> tuple[CrawlResult, list[ProductListEntry]]:
        if hasattr(self.crawler, "fetch_product_catalog"):
            return await self.crawler.fetch_product_catalog(output_dir=output_dir)

        catalog_crawl = await self.crawler._crawl_catalog_source(  # noqa: SLF001
            output_dir=output_dir,
            search_product=None,
        )
        return catalog_crawl, parse_product_list(catalog_crawl)


def load_catalog_cache(path: Path) -> ProductCatalog | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    products = payload.get("products")
    if not isinstance(products, list):
        return None

    entries = [
        entry
        for item in products
        if isinstance(item, dict)
        for entry in [product_entry_from_dict(item)]
        if entry._id and entry.name
    ]
    if not entries:
        return None

    return ProductCatalog(
        entries=entries,
        cache_path=path,
        loaded_from_cache=True,
        refreshed=False,
        generated_at=str(payload.get("generated_at") or "") or None,
    )


def save_catalog_cache(
    path: Path,
    entries: list[ProductListEntry],
    *,
    source_url: str,
    generated_at: str | None = None,
) -> None:
    payload = {
        "version": CATALOG_CACHE_VERSION,
        "source_url": source_url,
        "generated_at": generated_at or _now(),
        "count": len(entries),
        "products": [product_entry_to_dict(entry) for entry in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
