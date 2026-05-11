from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent import ProductFeatureAgent
from .cdp_browser import CDPCrawler
from .config import DEFAULT_PRODUCT_NAME, DEFAULT_TARGET_URL, Settings
from .proofreading import ProofreadingClient

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    FastMCP = None


if FastMCP is not None:
    mcp = FastMCP("agent-mcp-cdp")
else:
    mcp = None


if mcp is not None:

    @mcp.tool()
    async def crawl_product_features(
        url: str | None = None,
        product_name: str = DEFAULT_PRODUCT_NAME,
        wait_ms: int | None = None,
        list_only: bool = False,
        proofread: bool = False,
    ) -> dict:
        """Crawl a dynamic web page through CDP and extract product features.

        By default, searches the AI marketplace listing for product_name, then
        crawls the matched detail page. If url is provided, crawls that detail URL
        directly. Set list_only=True to return the product catalog without crawling
        a detail page. Set proofread=True to send extracted product features to
        the proofreading service.
        """
        settings = Settings.from_env(
            target_url=url or DEFAULT_TARGET_URL,
            product_name=product_name,
            wait_after_load_ms=wait_ms,
        )
        crawler = CDPCrawler(settings)

        if url is None or list_only:
            crawl, result = await crawler.search_product(
                product_name,
                use_search_box=not list_only,
            )
            if list_only or crawl is None:
                return {
                    "search": {
                        "query": product_name,
                        "matched": result.matched_entry is not None,
                        "confidence": result.confidence,
                        "warnings": result.warnings,
                        "candidates": [
                            {
                                "id": e._id,
                                "name": e.name,
                                "client_name": e.client_name,
                                "introduction": e.introduction,
                            }
                            for e in result.candidates[:20]
                        ],
                    }
                }
        else:
            crawl = await crawler.crawl(settings.target_url)

        agent = ProductFeatureAgent(settings)
        features = await agent.extract(crawl, product_name)
        proofreading = None
        if proofread:
            proofreading = await ProofreadingClient(settings).proofread_features(features)

        response = features.to_dict()
        if proofreading is not None:
            response["proofreading"] = proofreading.to_dict()
        _save_full(
            crawl.to_dict(),
            features.to_dict(),
            response,
            proofreading.to_dict() if proofreading else None,
        )
        return response


def _runs_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "runs"


def _save_full(
    crawl: dict[str, Any],
    features: dict[str, Any],
    agent_response: dict[str, Any],
    proofreading: dict[str, Any] | None = None,
) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = _runs_dir() / f"mcp-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"crawl": crawl, "product_features": features}
    if proofreading is not None:
        payload["proofreading"] = proofreading
    (run_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "agent_response.json").write_text(
        json.dumps(agent_response, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # features.md
    lines = [
        f"# {features['product_name']} 产品功能提取",
        "",
        f"- URL: {crawl['final_url']}",
        f"- 标题: {crawl['title']}",
        f"- 浏览器模式: {crawl['browser_mode']}",
        "",
        "## 摘要", "", features.get("summary") or "无",
        "",
        "## 产品功能", "",
    ]
    if features.get("features"):
        lines.extend(f"- {item}" for item in features["features"])
    else:
        lines.append("- 未提取到明确功能")
    lines.extend(["", "## 证据", ""])
    if features.get("evidence"):
        lines.extend(f"- {item}" for item in features["evidence"])
    else:
        lines.append("- 无")
    if features.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in features["warnings"])
    if proofreading:
        lines.extend(["", "## Proofreading", ""])
        if proofreading.get("error"):
            lines.append(f"- Error: {proofreading['error']}")
        else:
            result = proofreading.get("result")
            suggestion_count = len(result) if isinstance(result, list) else 0
            lines.append(f"- Suggestions: {suggestion_count}")
            correct = proofreading.get("correct")
            if correct:
                lines.append(f"- Correct: {correct}")
            if result:
                lines.append(f"- Result: {result}")
    (run_dir / "features.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run_mcp() -> None:
    if mcp is None:
        raise RuntimeError("Package 'mcp' is not installed. Run: pip install -r requirements.txt")
    mcp.run()
