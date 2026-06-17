from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.config import Settings
from agent_mcp_cdp.models import CrawlResult, ProductFeatures, ProofreadingResult
from agent_mcp_cdp.product_search import ProductListEntry, ProductSearchResult
from agent_mcp_cdp.schemas.payloads import build_search_response
from agent_mcp_cdp.services.crawl_workflow import CrawlWorkflow


class FakeCrawler:
    def __init__(self) -> None:
        self.search_args = None
        self.crawl_args = None

    async def crawl(self, url: str, output_dir: Path | None = None) -> CrawlResult:
        self.crawl_args = (url, output_dir)
        return CrawlResult(
            requested_url=url,
            final_url=url,
            title="Demo",
            text="产品功能\n1. 功能\n支持教师布置作业。",
        )

    async def search_product(
        self,
        product_name: str,
        output_dir: Path | None = None,
        use_search_box: bool = True,
    ) -> tuple[CrawlResult | None, ProductSearchResult]:
        self.search_args = (product_name, output_dir, use_search_box)
        search_result = ProductSearchResult(
            query=product_name,
            matched_entry=ProductListEntry(_id="1", name=product_name),
            confidence=1.0,
            candidates=[ProductListEntry(_id="1", name=product_name)],
        )
        return await self.crawl("https://example.test/detail", output_dir), search_result


class FakeBatchCrawler(FakeCrawler):
    def __init__(self) -> None:
        super().__init__()
        self.fetch_catalog_called = False
        self.crawl_many_args = None

    async def fetch_product_catalog(
        self,
        output_dir: Path | None = None,
    ) -> tuple[CrawlResult, list[ProductListEntry]]:
        self.fetch_catalog_called = True
        catalog_crawl = CrawlResult(
            requested_url="https://example.test/catalog",
            final_url="https://example.test/catalog",
            title="Catalog",
            text="",
        )
        entries = [
            ProductListEntry(_id="1", name="产品一", client_name="厂商一"),
            ProductListEntry(_id="2", name="产品二", client_name="厂商二"),
        ]
        return catalog_crawl, entries

    async def crawl_many(
        self,
        targets: list[tuple[str, Path | None]],
        *,
        concurrency: int,
    ) -> list[CrawlResult]:
        self.crawl_many_args = (targets, concurrency)
        return [
            CrawlResult(
                requested_url=url,
                final_url=url,
                title="Demo",
                text="产品功能\n1. 功能\n支持教师布置作业。",
            )
            for url, _output_dir in targets
        ]


class FakeExtractor:
    async def extract(self, crawl: CrawlResult, product_name: str) -> ProductFeatures:
        return ProductFeatures(
            product_name=product_name,
            summary="summary",
            features=["feature"],
        )


class FakeProofreadingClient:
    def __init__(self) -> None:
        self.called = False
        self.calls: list[str] = []

    async def proofread_features(self, features: ProductFeatures) -> ProofreadingResult:
        self.called = True
        self.calls.append(features.product_name)
        return ProofreadingResult(
            service_url="https://proofreading.test",
            correct="correct",
            result=[],
            raw_response="{}",
        )


class CrawlWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_workflow_does_not_proofread_by_default(self) -> None:
        crawler = FakeCrawler()
        proofreader = FakeProofreadingClient()
        workflow = CrawlWorkflow(
            Settings(target_url="https://example.test", product_name="demo"),
            crawler=crawler,
            extractor=FakeExtractor(),
            proofreading_client=proofreader,
        )

        result = await workflow.run(use_search=False, proofread=False)

        self.assertIsNotNone(result.crawl)
        self.assertIsNotNone(result.agent_response)
        self.assertNotIn("proofreading", result.agent_response or {})
        self.assertFalse(proofreader.called)
        self.assertEqual(crawler.crawl_args[0], "https://example.test")

    async def test_workflow_adds_proofreading_when_enabled(self) -> None:
        proofreader = FakeProofreadingClient()
        workflow = CrawlWorkflow(
            Settings(target_url="https://example.test", product_name="demo"),
            crawler=FakeCrawler(),
            extractor=FakeExtractor(),
            proofreading_client=proofreader,
        )

        result = await workflow.run(use_search=False, proofread=True)

        self.assertTrue(proofreader.called)
        self.assertEqual(
            result.agent_response["proofreading"]["correct"],
            "correct",
        )

    async def test_list_only_search_does_not_extract_features(self) -> None:
        crawler = FakeCrawler()
        workflow = CrawlWorkflow(
            Settings(product_name="demo"),
            crawler=crawler,
            extractor=FakeExtractor(),
            proofreading_client=FakeProofreadingClient(),
        )

        result = await workflow.run(use_search=True, list_only=True)

        self.assertIsNone(result.crawl)
        self.assertIsNone(result.features)
        self.assertEqual(crawler.search_args[2], False)
        self.assertTrue(build_search_response(result.search_result)["search"]["matched"])

    async def test_batch_proofread_fetches_catalog_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            crawler = FakeBatchCrawler()
            proofreader = FakeProofreadingClient()
            workflow = CrawlWorkflow(
                Settings(
                    product_catalog_cache_path=base / "catalog.json",
                    batch_proofread_concurrency=2,
                ),
                crawler=crawler,
                extractor=FakeExtractor(),
                proofreading_client=proofreader,
            )

            result = await workflow.run_batch_proofread(
                concurrency=2,
                output_dir=base / "run",
            )

            self.assertTrue(crawler.fetch_catalog_called)
            self.assertEqual(crawler.crawl_many_args[1], 2)
            self.assertEqual(proofreader.calls, ["产品一", "产品二"])
            self.assertEqual(result.agent_response["batch"]["succeeded_count"], 2)
            self.assertTrue((base / "catalog.json").exists())
            self.assertTrue((base / "run" / "result.json").exists())
            self.assertTrue(
                (base / "run" / "products" / "001-产品一" / "result.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
