from __future__ import annotations

from pathlib import Path

from .config import DEFAULT_PRODUCT_NAME, DEFAULT_TARGET_URL, Settings
from .schemas.payloads import build_search_response
from .services.crawl_workflow import CrawlWorkflow
from .services.output_writer import default_run_dir, write_run_outputs

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
        workflow = CrawlWorkflow(settings)
        workflow_result = await workflow.run(
            use_search=url is None or list_only,
            list_only=list_only,
            proofread=proofread,
            output_dir=None,
        )

        if list_only or workflow_result.crawl is None:
            return build_search_response(workflow_result.search_result)

        if workflow_result.result_payload and workflow_result.agent_response:
            _save_full(workflow_result.result_payload, workflow_result.agent_response)
        return workflow_result.agent_response or {}


def _runs_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "runs"


def _save_full(
    result_payload: dict,
    agent_response: dict,
) -> None:
    run_dir = default_run_dir(_runs_dir(), prefix="mcp-")
    write_run_outputs(run_dir, result_payload, agent_response)


def run_mcp() -> None:
    if mcp is None:
        raise RuntimeError("Package 'mcp' is not installed. Run: pip install -r requirements.txt")
    mcp.run()
