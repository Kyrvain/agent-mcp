from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..cdp_browser import CDPCrawler
from ..config import Settings
from ..extractors.product_features import ProductFeatureExtractor
from ..models import CrawlResult, ProductFeatures, ProofreadingResult
from ..product_search import ProductListEntry, ProductSearchResult
from ..schemas.payloads import build_agent_response, build_result_payload
from .output_writer import write_batch_outputs, write_run_outputs
from .product_catalog import ProductCatalog, ProductCatalogService
from .proofreading import ProofreadingClient


@dataclass(slots=True)
class CrawlWorkflowResult:
    crawl: CrawlResult | None = None
    search_result: ProductSearchResult | None = None
    features: ProductFeatures | None = None
    proofreading: ProofreadingResult | None = None
    result_payload: dict[str, Any] | None = None
    agent_response: dict[str, Any] | None = None


@dataclass(slots=True)
class BatchProofreadingProductResult:
    product_id: str
    product_name: str
    detail_url: str
    client_name: str = ""
    output_dir: Path | None = None
    crawl: CrawlResult | None = None
    features: ProductFeatures | None = None
    proofreading: ProofreadingResult | None = None
    result_payload: dict[str, Any] | None = None
    agent_response: dict[str, Any] | None = None
    error: str | None = None

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if self.proofreading is not None and self.proofreading.error:
            return "proofreading_failed"
        if self.features is not None:
            return "succeeded"
        return "pending"

    def to_result_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.product_id,
            "product_name": self.product_name,
            "client_name": self.client_name,
            "detail_url": self.detail_url,
            "status": self.status,
            "output_dir": str(self.output_dir) if self.output_dir else None,
        }
        if self.crawl is not None:
            payload["crawl"] = self.crawl.to_dict()
        if self.features is not None:
            payload["product_features"] = self.features.to_dict()
        if self.proofreading is not None:
            payload["proofreading"] = self.proofreading.to_dict()
        if self.error:
            payload["error"] = self.error
        return payload

    def to_agent_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.product_id,
            "product_name": self.product_name,
            "client_name": self.client_name,
            "detail_url": self.detail_url,
            "status": self.status,
        }
        if self.agent_response is not None:
            payload.update(self.agent_response)
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(slots=True)
class BatchProofreadingWorkflowResult:
    catalog: ProductCatalog
    items: list[BatchProofreadingProductResult]
    result_payload: dict[str, Any]
    agent_response: dict[str, Any]


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

    async def run_batch_proofread(
        self,
        *,
        force_refresh_catalog: bool = False,
        limit: int | None = None,
        concurrency: int | None = None,
        output_dir: Path | None = None,
    ) -> BatchProofreadingWorkflowResult:
        batch_concurrency = max(
            1,
            concurrency
            if concurrency is not None
            else self.settings.batch_proofread_concurrency,
        )
        catalog_output_dir = output_dir / "_catalog" if output_dir else None
        catalog = await ProductCatalogService(self.settings, self.crawler).get_catalog(
            force_refresh=force_refresh_catalog,
            output_dir=catalog_output_dir,
        )
        entries = _limit_entries(catalog.entries, limit)
        items = [
            _batch_item_for_entry(entry, output_dir, index)
            for index, entry in enumerate(entries, 1)
        ]

        crawl_results = await self._crawl_batch_items(items, batch_concurrency)
        await self._extract_and_proofread_batch(
            items,
            crawl_results,
            batch_concurrency,
        )

        result_payload = _build_batch_result_payload(
            catalog,
            items,
            batch_concurrency,
        )
        agent_response = _build_batch_agent_response(
            catalog,
            items,
            batch_concurrency,
        )

        if output_dir is not None:
            write_batch_outputs(output_dir, result_payload, agent_response)

        return BatchProofreadingWorkflowResult(
            catalog=catalog,
            items=items,
            result_payload=result_payload,
            agent_response=agent_response,
        )

    async def _crawl_batch_items(
        self,
        items: list[BatchProofreadingProductResult],
        concurrency: int,
    ) -> list[CrawlResult | BaseException]:
        targets = [(item.detail_url, item.output_dir) for item in items]
        if hasattr(self.crawler, "crawl_many"):
            return await self.crawler.crawl_many(targets, concurrency=concurrency)

        semaphore = asyncio.Semaphore(concurrency)

        async def worker(
            item: BatchProofreadingProductResult,
        ) -> CrawlResult | BaseException:
            async with semaphore:
                try:
                    return await self.crawler.crawl(item.detail_url, item.output_dir)
                except Exception as exc:
                    return exc

        return await asyncio.gather(*(worker(item) for item in items))

    async def _extract_and_proofread_batch(
        self,
        items: list[BatchProofreadingProductResult],
        crawl_results: list[CrawlResult | BaseException],
        concurrency: int,
    ) -> None:
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(
            item: BatchProofreadingProductResult,
            crawl_result: CrawlResult | BaseException,
        ) -> None:
            async with semaphore:
                if isinstance(crawl_result, BaseException):
                    item.error = _format_exception(crawl_result)
                    return

                item.crawl = crawl_result
                try:
                    item.features = await self.extractor.extract(
                        crawl_result,
                        item.product_name,
                    )
                    item.proofreading = await self.proofreading_client.proofread_features(
                        item.features
                    )
                    item.result_payload = build_result_payload(
                        crawl_result,
                        item.features,
                        item.proofreading,
                    )
                    item.agent_response = build_agent_response(
                        item.features,
                        item.proofreading,
                    )
                    if item.output_dir is not None:
                        write_run_outputs(
                            item.output_dir,
                            item.result_payload,
                            item.agent_response,
                        )
                except Exception as exc:
                    item.error = _format_exception(exc)

        await asyncio.gather(
            *(
                worker(item, crawl_result)
                for item, crawl_result in zip(items, crawl_results)
            )
        )


def _limit_entries(
    entries: list[ProductListEntry],
    limit: int | None,
) -> list[ProductListEntry]:
    if limit is None:
        return list(entries)
    return list(entries[: max(0, limit)])


def _batch_item_for_entry(
    entry: ProductListEntry,
    output_dir: Path | None,
    index: int,
) -> BatchProofreadingProductResult:
    return BatchProofreadingProductResult(
        product_id=entry._id,
        product_name=entry.name,
        client_name=entry.client_name,
        detail_url=entry.detail_url,
        output_dir=_product_output_dir(output_dir, entry, index)
        if output_dir is not None
        else None,
    )


def _product_output_dir(
    output_dir: Path,
    entry: ProductListEntry,
    index: int,
) -> Path:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", entry.name).strip(" ._")
    if not name:
        name = entry._id or "product"
    return output_dir / "products" / f"{index:03d}-{name[:80]}"


def _build_batch_result_payload(
    catalog: ProductCatalog,
    items: list[BatchProofreadingProductResult],
    concurrency: int,
) -> dict[str, Any]:
    return {
        "batch": _batch_summary(catalog, items, concurrency),
        "catalog": catalog.to_dict(),
        "products": [item.to_result_payload() for item in items],
    }


def _build_batch_agent_response(
    catalog: ProductCatalog,
    items: list[BatchProofreadingProductResult],
    concurrency: int,
) -> dict[str, Any]:
    return {
        "batch": _batch_summary(catalog, items, concurrency),
        "products": [item.to_agent_response() for item in items],
    }


def _batch_summary(
    catalog: ProductCatalog,
    items: list[BatchProofreadingProductResult],
    concurrency: int,
) -> dict[str, Any]:
    succeeded = sum(1 for item in items if item.status == "succeeded")
    failed = sum(1 for item in items if item.status != "succeeded")
    return {
        "catalog_count": len(catalog.entries),
        "processed_count": len(items),
        "succeeded_count": succeeded,
        "failed_count": failed,
        "concurrency": concurrency,
        "cache_path": str(catalog.cache_path),
        "loaded_from_cache": catalog.loaded_from_cache,
        "refreshed_catalog": catalog.refreshed,
        "generated_at": catalog.generated_at,
        "warnings": list(catalog.warnings),
    }


def _format_exception(exc: BaseException) -> str:
    detail = str(exc) or repr(exc)
    return f"{type(exc).__name__}: {detail}"
