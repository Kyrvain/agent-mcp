from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cdp_browser import CDPCrawler
from ..config import Settings
from ..extractors.product_features import ProductFeatureExtractor
from ..models import CrawlResult, ProductFeatures, ProofreadingResult
from ..product_search import ProductSearchResult
from ..schemas.payloads import build_agent_response, build_result_payload
from .output_writer import write_run_outputs
from .proofreading import ProofreadingClient


@dataclass(slots=True)
class CrawlWorkflowResult:
    crawl: CrawlResult | None = None
    search_result: ProductSearchResult | None = None
    features: ProductFeatures | None = None
    proofreading: ProofreadingResult | None = None
    result_payload: dict[str, Any] | None = None
    agent_response: dict[str, Any] | None = None


class CrawlWorkflow:
    def __init__(
        self,
        settings: Settings,
        crawler: Any | None = None,
        extractor: Any | None = None,
        proofreading_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self.crawler = crawler or CDPCrawler(settings)
        self.extractor = extractor or ProductFeatureExtractor(settings)
        self.proofreading_client = proofreading_client or ProofreadingClient(settings)

    async def run(
        self,
        *,
        use_search: bool,
        list_only: bool = False,
        proofread: bool = False,
        output_dir: Path | None = None,
    ) -> CrawlWorkflowResult:
        crawl: CrawlResult | None
        search_result: ProductSearchResult | None = None

        if use_search:
            crawl, search_result = await self.crawler.search_product(
                self.settings.product_name,
                output_dir,
                use_search_box=not list_only,
            )
            if list_only:
                crawl = None
        else:
            crawl = await self.crawler.crawl(self.settings.target_url, output_dir)

        if crawl is None:
            return CrawlWorkflowResult(crawl=None, search_result=search_result)

        features = await self.extractor.extract(crawl, self.settings.product_name)
        proofreading = None
        if proofread:
            proofreading = await self.proofreading_client.proofread_features(features)

        result_payload = build_result_payload(
            crawl,
            features,
            proofreading,
            search_result,
        )
        agent_response = build_agent_response(features, proofreading)

        if output_dir is not None:
            write_run_outputs(output_dir, result_payload, agent_response)

        return CrawlWorkflowResult(
            crawl=crawl,
            search_result=search_result,
            features=features,
            proofreading=proofreading,
            result_payload=result_payload,
            agent_response=agent_response,
        )
