from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import DEFAULT_PRODUCT_NAME, DEFAULT_TARGET_URL, Settings
from .mcp_server import run_mcp
from .services.crawl_workflow import CrawlWorkflow
from .services.output_writer import default_run_dir


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "crawl":
        asyncio.run(run_crawl(args))
    elif args.command == "mcp":
        run_mcp()
    elif args.command == "api":
        run_api(args)
    else:
        parser.print_help()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-mcp-cdp",
        description="Use CDP + MCP to extract product features.",
    )
    subparsers = parser.add_subparsers(dest="command")

    crawl = subparsers.add_parser("crawl", help="crawl a page and extract product features")
    crawl.add_argument("--url", default=DEFAULT_TARGET_URL)
    crawl.add_argument("--product-name", default=DEFAULT_PRODUCT_NAME)
    crawl.add_argument("--output-dir", type=Path)
    crawl.add_argument("--cdp-url")
    crawl.add_argument("--browser-executable")
    crawl.add_argument("--headed", action="store_true", help="show the browser window")
    crawl.add_argument("--wait-ms", type=int)
    crawl.add_argument(
        "--search", "-s",
        action="store_true",
        help="search for product by name on the listing page",
    )
    crawl.add_argument(
        "--confidence",
        type=float,
        help="override search confidence threshold (default 0.3)",
    )
    crawl.add_argument(
        "--list-only",
        action="store_true",
        help="list available products without crawling a detail page",
    )
    crawl.add_argument(
        "--proofread",
        action="store_true",
        help="send extracted product features to the proofreading service",
    )
    crawl.add_argument(
        "--batch-proofread",
        action="store_true",
        help="proofread every product in the cached/full catalog",
    )
    crawl.add_argument(
        "--refresh-catalog",
        action="store_true",
        help="refresh the full product catalog cache before batch proofreading",
    )
    crawl.add_argument(
        "--batch-concurrency",
        type=int,
        help="number of products to process concurrently in batch proofreading",
    )
    crawl.add_argument(
        "--batch-limit",
        type=int,
        help="only process the first N catalog products in batch proofreading",
    )
    crawl.add_argument(
        "--no-proofread",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    subparsers.add_parser("mcp", help="start the MCP stdio server")

    api = subparsers.add_parser("api", help="start the HTTP API server")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--reload", action="store_true")
    return parser


def run_api(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Package 'uvicorn' is not installed. Run: pip install -r requirements.txt"
        ) from exc

    uvicorn.run(
        "agent_mcp_cdp.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


async def run_crawl(args: argparse.Namespace) -> None:
    output_dir = args.output_dir or default_run_dir()
    use_search = args.search or args.list_only

    settings = Settings.from_env(
        target_url=args.url,
        product_name=args.product_name,
        cdp_url=args.cdp_url,
        browser_executable=args.browser_executable,
        browser_headless=False if args.headed else None,
        wait_after_load_ms=args.wait_ms,
        output_dir=output_dir,
        batch_proofread_concurrency=args.batch_concurrency,
    )
    if args.confidence is not None:
        settings.search_confidence_threshold = args.confidence

    if args.batch_proofread:
        if args.batch_concurrency is not None and args.batch_concurrency < 1:
            raise ValueError("--batch-concurrency must be greater than 0")
        if args.batch_limit is not None and args.batch_limit < 0:
            raise ValueError("--batch-limit must be greater than or equal to 0")
        print("批量校对产品目录...")
        workflow = CrawlWorkflow(settings)
        batch_result = await workflow.run_batch_proofread(
            force_refresh_catalog=args.refresh_catalog,
            limit=args.batch_limit,
            concurrency=args.batch_concurrency,
            output_dir=output_dir,
        )
        summary = batch_result.agent_response["batch"]
        print(f"Output: {output_dir}")
        print(f"Catalog cache: {summary['cache_path']}")
        print(f"Catalog products: {summary['catalog_count']}")
        print(f"Processed: {summary['processed_count']}")
        print(f"Succeeded: {summary['succeeded_count']}")
        print(f"Failed: {summary['failed_count']}")
        return

    if use_search:
        print(f"搜索产品「{settings.product_name}」...")

    workflow = CrawlWorkflow(settings)
    workflow_result = await workflow.run(
        use_search=use_search,
        list_only=args.list_only,
        proofread=args.proofread and not args.no_proofread,
        output_dir=output_dir,
    )

    crawl = workflow_result.crawl
    search_result = workflow_result.search_result

    if search_result and search_result.matched_entry:
        print(
            f"匹配到: {search_result.matched_entry.name}"
            f"（置信度: {search_result.confidence:.2f}）"
        )
    if search_result and search_result.warnings:
        for w in search_result.warnings:
            print(f"  [WARNING] {w}")

    if crawl is None:
        if search_result and search_result.candidates:
            print(f"\n可用产品列表（共 {len(search_result.candidates)} 个）：")
            for i, entry in enumerate(search_result.candidates, 1):
                parts = [f"{i}. {entry.name}"]
                if entry.client_name:
                    parts.append(f"({entry.client_name})")
                if entry.introduction:
                    parts.append(f"\n   {entry.introduction[:100]}")
                parts.append(f"\n   {entry.detail_url}")
                print(" ".join(parts))
        return

    features = workflow_result.features
    proofreading = workflow_result.proofreading
    if features is None:
        return

    print(f"Output: {output_dir}")
    print(f"Browser: {crawl.browser_mode}")
    print(f"Title: {crawl.title}")
    print(f"Product: {features.product_name}")
    if proofreading is not None:
        if proofreading.error:
            print(f"Proofreading error: {proofreading.error}")
        else:
            suggestion_count = (
                len(proofreading.result)
                if isinstance(proofreading.result, list)
                else 0
            )
            correct_status = "yes" if proofreading.correct else "no"
            print(f"Proofreading suggestions: {suggestion_count}")
            print(f"Proofreading correct available: {correct_status}")
    if features.features:
        print("Features:")
        for item in features.features:
            print(f"- {item}")
    if features.warnings:
        print("Warnings:")
        for item in features.warnings:
            print(f"- {item}")
