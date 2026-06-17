from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.config import Settings
from agent_mcp_cdp.product_search import ProductListEntry
from agent_mcp_cdp.services.product_catalog import (
    ProductCatalogService,
    load_catalog_cache,
    save_catalog_cache,
)


class FailingCatalogCrawler:
    async def fetch_product_catalog(self, output_dir=None):  # noqa: ANN001, ANN201
        raise AssertionError("cache should be used")


class ProductCatalogCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_catalog_is_reused_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "catalog.json"
            save_catalog_cache(
                cache_path,
                [ProductListEntry(_id="1", name="九章爱学")],
                source_url="https://example.test/catalog",
            )

            service = ProductCatalogService(
                Settings(product_catalog_cache_path=cache_path),
                FailingCatalogCrawler(),
            )
            catalog = await service.get_catalog()

        self.assertTrue(catalog.loaded_from_cache)
        self.assertFalse(catalog.refreshed)
        self.assertEqual(catalog.entries[0].name, "九章爱学")
        self.assertIn("detail?id=1", catalog.entries[0].detail_url)

    def test_invalid_cache_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "catalog.json"
            cache_path.write_text("not json", encoding="utf-8")

            self.assertIsNone(load_catalog_cache(cache_path))


if __name__ == "__main__":
    unittest.main()
