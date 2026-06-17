from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .config import Settings
from .crawlers.browser_session import (
    BrowserSession,
    find_chromium_executable,
    wait_for_cdp,
)
from .models import CrawlResult, NetworkSnippet
from .product_search import (
    ProductListEntry,
    ProductSearchResult,
    build_detail_url,
    match_product,
    parse_product_list,
)


class CDPCrawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._max_response_chars_override: int | None = None
        self._max_responses_override: int | None = None

    async def crawl(self, url: str, output_dir: Path | None = None) -> CrawlResult:
        output_dir = output_dir or self.settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        async with BrowserSession(self.settings) as session:
            page = None
            try:
                page = await session.new_page()
                return await self._crawl_with_page(
                    page,
                    url,
                    output_dir,
                    session.browser_mode,
                )
            finally:
                if page is not None:
                    await page.close()

    async def crawl_many(
        self,
        targets: Sequence[tuple[str, Path | None]],
        *,
        concurrency: int,
    ) -> list[CrawlResult | BaseException]:
        if not targets:
            return []

        semaphore = asyncio.Semaphore(max(1, concurrency))

        async with BrowserSession(self.settings) as session:

            async def worker(
                index: int,
                url: str,
                output_dir: Path | None,
            ) -> CrawlResult:
                async with semaphore:
                    run_dir = (
                        output_dir
                        or self.settings.output_dir / f"batch-{index:03d}"
                    )
                    run_dir.mkdir(parents=True, exist_ok=True)
                    page = await session.new_page()
                    try:
                        return await self._crawl_with_page(
                            page,
                            url,
                            run_dir,
                            session.browser_mode,
                        )
                    finally:
                        await page.close()

            return await asyncio.gather(
                *(
                    worker(index, url, target_dir)
                    for index, (url, target_dir) in enumerate(targets, 1)
                ),
                return_exceptions=True,
            )

    async def _crawl_catalog_source(
        self,
        output_dir: Path | None = None,
        search_product: str | None = None,
    ) -> CrawlResult:
        """Crawl the listing page's 智链货架 directly for the full product catalog."""
        output_dir = output_dir or self.settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        self._max_response_chars_override = self.settings.listing_max_response_chars
        self._max_responses_override = 128

        async with BrowserSession(self.settings) as session:
            page = None
            try:
                page = await session.new_page()

                responses: list[NetworkSnippet] = []
                page.on("response", lambda response: asyncio.create_task(
                    self._capture_response(response, responses)
                ))

                # Navigate directly to the listing page
                await page.goto(
                    self.settings.listing_url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.navigation_timeout_ms,
                )
                try:
                    await page.wait_for_load_state("networkidle", timeout=20000)
                except PlaywrightTimeoutError:
                    pass
                await page.wait_for_timeout(self.settings.listing_wait_after_load_ms)

                if search_product:
                    responses.clear()
                    await self._search_listing_by_name(page, search_product)
                else:
                    # Paginate only when collecting the full product catalog.
                    await self._paginate_all_shelves(page)

                title = await page.title()
                text = await self._body_text(page)
                links = await self._links(page)
                screenshot_path = output_dir / "page.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)

                return CrawlResult(
                    requested_url=self.settings.listing_url,
                    final_url=page.url,
                    title=title,
                    text=clean_text(text),
                    links=links,
                    responses=responses[: self.settings.max_responses],
                    screenshot_path=screenshot_path,
                    browser_mode=session.browser_mode,
                )
            finally:
                self._max_response_chars_override = None
                self._max_responses_override = None
                if page is not None:
                    await page.close()

    async def fetch_product_catalog(
        self,
        output_dir: Path | None = None,
    ) -> tuple[CrawlResult, list[ProductListEntry]]:
        catalog_crawl = await self._crawl_catalog_source(
            output_dir=output_dir,
            search_product=None,
        )
        return catalog_crawl, parse_product_list(catalog_crawl)

    async def search_product(
        self,
        product_name: str,
        output_dir: Path | None = None,
        use_search_box: bool = True,
    ) -> tuple[CrawlResult | None, ProductSearchResult]:
        result = ProductSearchResult(query=product_name)

        catalog_crawl = await self._crawl_catalog_source(
            output_dir=output_dir,
            search_product=product_name if use_search_box else None,
        )
        entries = parse_product_list(catalog_crawl)

        if not entries:
            result.warnings.append("未能从页面提取到任何产品。请确认网站可访问。")
            return None, result

        matched, confidence, warnings = await match_product(
            product_name, entries, self.settings
        )
        result.candidates = entries
        result.warnings.extend(warnings)

        if matched is None or confidence < self.settings.search_confidence_threshold:
            if matched is None:
                result.warnings.append(
                    f"未找到匹配产品「{product_name}」，可用产品："
                    + "、".join(e.name for e in entries[:10])
                )
            else:
                result.warnings.append(
                    f"匹配度({confidence:.2f})低于阈值({self.settings.search_confidence_threshold})"
                )
            return None, result

        result.matched_entry = matched
        result.confidence = confidence
        result.detail_url = build_detail_url(matched)

        detail_crawl = await self.crawl(result.detail_url, output_dir)
        return detail_crawl, result

    async def _paginate_all_shelves(self, page: Page) -> None:
        """Click through all pagination pages on the listing page to capture all products."""
        # First scroll to trigger lazy content
        await page.evaluate(
            """
            async () => {
              const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
              for (let i = 0; i < 8; i += 1) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(400);
              }
              window.scrollTo(0, 0);
            }
            """
        )
        await page.wait_for_timeout(3000)

        # Find all pagination component groups (each shelf has its own)
        # Element UI pagination: .el-pagination within each shelf
        for _round in range(10):  # safety limit
            # Find all "next page" buttons that are not disabled
            btn_infos = await page.eval_on_selector_all(
                "button.btn-next",
                """els => els.map(el => ({
                    disabled: el.disabled || el.classList.contains('disabled'),
                    parentClass: el.parentElement?.className || ''
                }))"""
            )
            if not btn_infos:
                break

            clicked = False
            for _i, info in enumerate(btn_infos):
                if info["disabled"]:
                    continue
                # Click this next button
                buttons = await page.query_selector_all("button.btn-next")
                if _i < len(buttons):
                    try:
                        await buttons[_i].click()
                        clicked = True
                        await page.wait_for_timeout(4000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except PlaywrightTimeoutError:
                            pass
                        break  # process one page at a time
                    except Exception:
                        continue

            if not clicked:
                break

    async def _search_listing_by_name(self, page: Page, product_name: str) -> None:
        """Use the listing page's 名称 search box instead of paginating every shelf."""
        await self._fill_listing_name_input(page, product_name)
        button = page.locator("button:has-text('查询')").first
        await button.wait_for(timeout=5000)
        try:
            async with page.expect_response(
                lambda response: "dse/service.do" in response.url,
                timeout=15000,
            ):
                await button.click(timeout=5000)
        except PlaywrightTimeoutError:
            pass
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(3000)

    async def _fill_listing_name_input(self, page: Page, product_name: str) -> None:
        inputs = page.locator("input.el-input__inner:not([readonly])")
        if await inputs.count():
            await inputs.first.fill(product_name, timeout=5000)
            return

        filled = await page.evaluate(
            """
            (productName) => {
              const labels = Array.from(document.querySelectorAll(
                '.el-form-item__label,label,span,div'
              ));
              for (const label of labels) {
                if ((label.textContent || '').trim() !== '名称') {
                  continue;
                }
                const container = label.closest('.el-form-item') || label.parentElement;
                const input = container && container.querySelector('input');
                if (input) {
                  input.value = productName;
                  input.dispatchEvent(new Event('input', { bubbles: true }));
                  input.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
              }
              return false;
            }
            """,
            product_name,
        )
        if not filled:
            raise RuntimeError("Could not find the listing page name search input.")

    async def _crawl_with_page(
        self,
        page: Page,
        url: str,
        output_dir: Path,
        browser_mode: str,
    ) -> CrawlResult:
        responses: list[NetworkSnippet] = []
        page.on(
            "response",
            lambda response: asyncio.create_task(
                self._capture_response(response, responses)
            ),
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.settings.navigation_timeout_ms,
        )
        await self._settle_page(page)
        await self._auto_scroll(page)

        title = await page.title()
        text = await self._body_text(page)
        links = await self._links(page)
        screenshot_path = output_dir / "page.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        return CrawlResult(
            requested_url=url,
            final_url=page.url,
            title=title,
            text=clean_text(text),
            links=links,
            responses=responses[: self.settings.max_responses],
            screenshot_path=screenshot_path,
            browser_mode=browser_mode,
        )

    async def _settle_page(self, page: Page) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(self.settings.wait_after_load_ms)

    async def _auto_scroll(self, page: Page, max_scrolls: int = 12, delay_ms: int = 400) -> None:
        await page.evaluate(
            f"""
            async () => {{
              const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
              for (let i = 0; i < {max_scrolls}; i += 1) {{
                window.scrollTo(0, document.body.scrollHeight);
                await delay({delay_ms});
              }}
              window.scrollTo(0, 0);
            }}
            """
        )

    async def _body_text(self, page: Page) -> str:
        try:
            return await page.locator("body").inner_text(timeout=5000)
        except PlaywrightTimeoutError:
            return await page.evaluate("() => document.body ? document.body.innerText : ''")

    async def _links(self, page: Page) -> list[str]:
        values = await page.eval_on_selector_all(
            "a[href]",
            """
            els => els
              .map((el) => el.href)
              .filter(Boolean)
              .slice(0, 200)
            """,
        )
        return sorted({str(item) for item in values})

    async def _capture_response(
        self,
        response: Any,
        responses: list[NetworkSnippet],
    ) -> None:
        max_resp = self._max_responses_override or self.settings.max_responses
        if len(responses) >= max_resp:
            return

        content_type = response.headers.get("content-type", "")
        lower_type = content_type.lower()
        is_interesting = any(
            token in lower_type for token in ("json", "text/plain", "application/xml")
        )
        is_same_site = "bjedures.bjedu.cn" in response.url
        if not (is_interesting and is_same_site):
            return

        try:
            body = await response.text()
        except Exception:
            return

        body = clean_text(body)
        if not body:
            return
        max_chars = self._max_response_chars_override or self.settings.max_response_chars
        if len(body) > max_chars:
            body = body[:max_chars] + "\n...[truncated]"

        responses.append(
            NetworkSnippet(
                url=response.url,
                status=response.status,
                content_type=content_type,
                body=body,
            )
        )


def clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()
