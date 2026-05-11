from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .models import ProductFeatures, ProofreadingResult


class ProofreadingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def proofread_features(self, features: ProductFeatures) -> ProofreadingResult:
        url = self.settings.proofreading_api_url
        if not url:
            return ProofreadingResult(
                service_url=None,
                error="Proofreading service URL is not configured.",
            )

        content = self._build_content(features)
        if not content:
            return ProofreadingResult(
                service_url=url,
                error="No product_features.features to proofread.",
            )

        try:
            async with httpx.AsyncClient(
                trust_env=False,
                timeout=self.settings.proofreading_timeout_s,
            ) as client:
                response = await client.post(
                    url,
                    json={"content": content},
                    headers={"Content-Type": "application/json"},
                )
            raw_response = response.text
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            correct = data.get("correct")
            return ProofreadingResult(
                service_url=url,
                correct=str(correct) if correct is not None else None,
                result=data.get("result"),
                raw_response=raw_response,
            )
        except Exception as exc:
            detail = str(exc) or repr(exc)
            return ProofreadingResult(
                service_url=url,
                error=f"{type(exc).__name__}: {detail}",
            )

    def _build_content(self, features: ProductFeatures) -> str:
        content = "".join(
            item.replace("\r\n", "").replace("\r", "").replace("\n", "")
            for item in features.features
            if item.strip()
        )
        max_chars = self.settings.proofreading_max_chars
        if max_chars > 0 and len(content) > max_chars:
            return content[:max_chars]
        return content
