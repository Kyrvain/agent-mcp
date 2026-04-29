from __future__ import annotations

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
    ) -> dict:
        """Crawl a dynamic web page through CDP and extract product features."""
        settings = Settings.from_env(
            target_url=url,
            product_name=product_name,
            wait_after_load_ms=wait_ms,
        )
        crawler = CDPCrawler(settings)
        crawl = await crawler.crawl(settings.target_url)
        agent = ProductFeatureAgent(settings)
        features = await agent.extract(crawl, settings.product_name)
        return {
            "crawl": crawl.to_dict(),
            "product_features": features.to_dict(),
        }


def run_mcp() -> None:
    if mcp is None:
        raise RuntimeError("Package 'mcp' is not installed. Run: pip install -r requirements.txt")
    mcp.run()
