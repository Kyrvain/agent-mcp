from __future__ import annotations

from typing import Any

from ..models import CrawlResult, ProductFeatures, ProofreadingResult
from ..product_search import ProductSearchResult


def product_features_payload(features: ProductFeatures) -> dict[str, Any]:
    return {
        "product_name": features.product_name,
        "summary": features.summary,
        "features": list(features.features),
        "evidence": list(features.evidence),
        "warnings": list(features.warnings),
    }


def proofreading_payload(proofreading: ProofreadingResult) -> dict[str, Any]:
    return proofreading.to_dict()


def build_result_payload(
    crawl: CrawlResult,
    features: ProductFeatures,
    proofreading: ProofreadingResult | None = None,
    search_result: ProductSearchResult | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "crawl": crawl.to_dict(),
        "product_features": product_features_payload(features),
    }
    if proofreading is not None:
        payload["proofreading"] = proofreading_payload(proofreading)
    if search_result and search_result.matched_entry:
        payload["search"] = {
            "query": search_result.query,
            "confidence": search_result.confidence,
        }
    return payload


def build_agent_response(
    features: ProductFeatures,
    proofreading: ProofreadingResult | None = None,
) -> dict[str, Any]:
    payload = product_features_payload(features)
    if proofreading is not None:
        payload["proofreading"] = proofreading_payload(proofreading)
    return payload


def build_search_response(
    search_result: ProductSearchResult | None,
    limit: int = 20,
) -> dict[str, Any]:
    if search_result is None:
        return {
            "search": {
                "query": "",
                "matched": False,
                "confidence": 0.0,
                "warnings": ["No product search result is available."],
                "candidates": [],
            }
        }

    return {
        "search": {
            "query": search_result.query,
            "matched": search_result.matched_entry is not None,
            "confidence": search_result.confidence,
            "warnings": list(search_result.warnings),
            "candidates": [
                {
                    "id": entry._id,
                    "name": entry.name,
                    "client_name": entry.client_name,
                    "introduction": entry.introduction,
                }
                for entry in search_result.candidates[:limit]
            ],
        }
    }
