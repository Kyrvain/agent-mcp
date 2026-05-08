from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent import ProductFeatureAgent
from .cdp_browser import CDPCrawler
from .config import DEFAULT_PRODUCT_NAME, DEFAULT_TARGET_URL, Settings

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
        url: str = DEFAULT_TARGET_URL,
        product_name: str = DEFAULT_PRODUCT_NAME,
        wait_ms: int | None = None,
        search_product: str | None = None,
        list_only: bool = False,
    ) -> dict:
        """Crawl a dynamic web page through CDP and extract product features.

        If search_product is provided, searches the AI marketplace listing for the
        product by name, then crawls the matched detail page. Set list_only=True
        to return the product catalog without crawling a detail page.
        """
        settings = Settings.from_env(
            target_url=url,
            product_name=product_name,
            wait_after_load_ms=wait_ms,
        )
        crawler = CDPCrawler(settings)

        if search_product or list_only:
            product_name = search_product or product_name
            crawl, result = await crawler.search_product(product_name)
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
        features = await agent.extract(crawl, settings.product_name)

        # 完整数据存本地供调试，只返回提取结果给 AI
        _save_full(crawl.to_dict(), features.to_dict())
        return features.to_dict()


def _runs_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "runs"


def _save_full(crawl: dict[str, Any], features: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = _runs_dir() / f"mcp-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"crawl": crawl, "product_features": features}
    (run_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # features.md
    lines = [
        f"# {features['product_name']} 产品功能提取",
        "",
        f"- URL: {crawl['final_url']}",
        f"- 标题: {crawl['title']}",
        f"- 浏览器模式: {crawl['browser_mode']}",
        f"- LLM used: {features['llm_used']}",
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
    (run_dir / "features.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run_mcp() -> None:
    if mcp is None:
        raise RuntimeError("Package 'mcp' is not installed. Run: pip install -r requirements.txt")
    mcp.run()
