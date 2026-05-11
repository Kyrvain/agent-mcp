from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class NetworkSnippet:
    url: str
    status: int
    content_type: str
    body: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CrawlResult:
    requested_url: str
    final_url: str
    title: str
    text: str
    links: list[str] = field(default_factory=list)
    responses: list[NetworkSnippet] = field(default_factory=list)
    screenshot_path: Path | None = None
    browser_mode: str = "unknown"
    loaded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def source_text(self) -> str:
        response_text = "\n\n".join(
            f"[response] {item.url}\n{item.body}" for item in self.responses
        )
        return "\n\n".join(
            part
            for part in [
                f"[title]\n{self.title}",
                f"[url]\n{self.final_url}",
                f"[page text]\n{self.text}",
                response_text,
            ]
            if part.strip()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "title": self.title,
            "text": self.text,
            "links": self.links,
            "responses": [item.to_dict() for item in self.responses],
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
            "browser_mode": self.browser_mode,
            "loaded_at": self.loaded_at,
        }


@dataclass(slots=True)
class ProductFeatures:
    product_name: str
    summary: str
    features: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_name": self.product_name,
            "summary": self.summary,
            "features": list(self.features),
            "evidence": list(self.evidence),
            "warnings": [
                item
                for item in self.warnings
                if not _is_removed_extraction_warning(item)
            ],
        }


@dataclass(slots=True)
class ProofreadingResult:
    service_url: str | None
    correct: str | None = None
    result: Any = None
    raw_response: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_removed_extraction_warning(value: str) -> bool:
    lowered = value.lower()
    return any(
        token in lowered
        for token in (
            "api_key",
            "规则提取",
        )
    )
