from __future__ import annotations

from .extractors.product_features import (
    ProductFeatureAgent,
    ProductFeatureExtractor,
    build_feature_candidates,
    dedupe,
    extract_product_function_section,
    extract_summary,
    normalize_lines,
)

__all__ = [
    "ProductFeatureAgent",
    "ProductFeatureExtractor",
    "build_feature_candidates",
    "dedupe",
    "extract_product_function_section",
    "extract_summary",
    "normalize_lines",
]
