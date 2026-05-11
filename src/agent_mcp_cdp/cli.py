from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent import ProductFeatureAgent
from .cdp_browser import CDPCrawler
from .config import DEFAULT_PRODUCT_NAME, DEFAULT_TARGET_URL, Settings
from .mcp_server import run_mcp
from .models import CrawlResult
from .proofreading import ProofreadingClient


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "crawl":
        asyncio.run(run_crawl(args))
    elif args.command == "mcp":
        run_mcp()
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
        "--no-proofread",
        action="store_true",
        help="skip sending crawled product details to the proofreading service",
    )

    subparsers.add_parser("mcp", help="start the MCP stdio server")
    return parser


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
    )
    if args.confidence is not None:
        settings.search_confidence_threshold = args.confidence

    crawler = CDPCrawler(settings)
    crawl: CrawlResult | None = None
    search_result = None

    if use_search:
        print(f"搜索产品「{settings.product_name}」...")
        crawl, search_result = await crawler.search_product(
            settings.product_name,
            output_dir,
            use_search_box=not args.list_only,
        )
        if search_result and search_result.matched_entry:
            print(
                f"匹配到: {search_result.matched_entry.name}"
                f"（置信度: {search_result.confidence:.2f}）"
            )
        if search_result and search_result.warnings:
            for w in search_result.warnings:
                print(f"  [WARNING] {w}")
        if args.list_only:
            crawl = None
    else:
        crawl = await crawler.crawl(settings.target_url, output_dir)

    if crawl is None:
        if search_result and search_result.candidates:
            print(f"\n可用产品列表（共 {len(search_result.candidates)} 个）：")
            for i, entry in enumerate(search_result.candidates, 1):
                parts = [f"{i}. {entry.name}"]
                if entry.client_name:
                    parts.append(f"({entry.client_name})")
                if entry.introduction:
                    parts.append(f"\n   {entry.introduction[:100]}")
                print(" ".join(parts))
        return

    agent = ProductFeatureAgent(settings)
    features = await agent.extract(crawl, settings.product_name)
    proofreading = None
    if not args.no_proofread:
        proofreading = await ProofreadingClient(settings).proofread_features(features)

    payload: dict[str, Any] = {
        "crawl": crawl.to_dict(),
        "product_features": features.to_dict(),
    }
    agent_response = features.to_dict()
    if proofreading is not None:
        payload["proofreading"] = proofreading.to_dict()
        agent_response["proofreading"] = proofreading.to_dict()
    if search_result and search_result.matched_entry:
        payload["search"] = {
            "query": search_result.query,
            "confidence": search_result.confidence,
        }
    write_json(output_dir / "result.json", payload)
    write_json(output_dir / "agent_response.json", agent_response)
    write_markdown(output_dir / "features.md", payload)

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


def default_run_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("data/runs") / stamp


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    features = payload["product_features"]
    crawl = payload["crawl"]
    lines = [
        f"# {features['product_name']} 产品功能提取",
        "",
        f"- URL: {crawl['final_url']}",
        f"- 标题: {crawl['title']}",
        f"- 浏览器模式: {crawl['browser_mode']}",
        "",
        "## 摘要",
        "",
        features["summary"] or "无",
        "",
        "## 产品功能",
        "",
    ]
    if features["features"]:
        lines.extend(f"- {item}" for item in features["features"])
    else:
        lines.append("- 未提取到明确功能")
    lines.extend(["", "## 证据", ""])
    if features["evidence"]:
        lines.extend(f"- {item}" for item in features["evidence"])
    else:
        lines.append("- 无")
    if features["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in features["warnings"])
    proofreading = payload.get("proofreading")
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
