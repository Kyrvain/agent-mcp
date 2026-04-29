from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .config import Settings
from .models import CrawlResult, NetworkSnippet


class CDPCrawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def crawl(self, url: str, output_dir: Path | None = None) -> CrawlResult:
        output_dir = output_dir or self.settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            browser, process, browser_mode = await self._connect_or_launch(playwright)
            context = None
            page = None
            try:
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = await browser.new_context(
                        viewport={"width": 1440, "height": 1200},
                        ignore_https_errors=True,
                    )
                page = await context.new_page()
                await page.set_viewport_size({"width": 1440, "height": 1200})

                responses: list[NetworkSnippet] = []
                page.on("response", lambda response: asyncio.create_task(
                    self._capture_response(response, responses)
                ))

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
            finally:
                if page is not None:
                    await page.close()
                if browser is not None:
                    await browser.close()
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()

    async def _connect_or_launch(self, playwright: Any) -> tuple[Browser, subprocess.Popen[Any] | None, str]:
        if self.settings.cdp_url:
            browser = await playwright.chromium.connect_over_cdp(self.settings.cdp_url)
            return browser, None, f"cdp:{self.settings.cdp_url}"

        executable = self.settings.browser_executable or find_chromium_executable()
        if executable:
            endpoint = f"http://127.0.0.1:{self.settings.remote_debugging_port}"
            process = self._start_cdp_browser(executable)
            await wait_for_cdp(endpoint)
            browser = await playwright.chromium.connect_over_cdp(endpoint)
            return browser, process, f"cdp:{endpoint}"

        browser = await playwright.chromium.launch(headless=self.settings.browser_headless)
        return browser, None, "playwright-managed"

    def _start_cdp_browser(self, executable: str) -> subprocess.Popen[Any]:
        profile_dir = self.settings.browser_user_data_dir.resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)

        args = [
            executable,
            f"--remote-debugging-port={self.settings.remote_debugging_port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-features=Translate",
        ]
        if self.settings.browser_headless:
            args.append("--headless=new")
            args.append("--disable-gpu")

        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def _settle_page(self, page: Page) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(self.settings.wait_after_load_ms)

    async def _auto_scroll(self, page: Page) -> None:
        await page.evaluate(
            """
            async () => {
              const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
              const maxScrolls = 8;
              for (let i = 0; i < maxScrolls; i += 1) {
                window.scrollTo(0, document.body.scrollHeight);
                await delay(250);
              }
              window.scrollTo(0, 0);
            }
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
        if len(responses) >= self.settings.max_responses:
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
        if len(body) > self.settings.max_response_chars:
            body = body[: self.settings.max_response_chars] + "\n...[truncated]"

        responses.append(
            NetworkSnippet(
                url=response.url,
                status=response.status,
                content_type=content_type,
                body=body,
            )
        )


async def wait_for_cdp(endpoint: str, timeout_seconds: float = 15.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with httpx.AsyncClient(timeout=1.5) as client:
        while True:
            try:
                response = await client.get(f"{endpoint}/json/version")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f"CDP endpoint did not start: {endpoint}")
            await asyncio.sleep(0.25)


def clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def find_chromium_executable() -> str | None:
    candidates: list[Path] = []
    env_paths = [
        os.getenv("PROGRAMFILES"),
        os.getenv("PROGRAMFILES(X86)"),
        os.getenv("LOCALAPPDATA"),
    ]
    for base in env_paths:
        if not base:
            continue
        root = Path(base)
        candidates.extend(
            [
                root / "Google/Chrome/Application/chrome.exe",
                root / "Microsoft/Edge/Application/msedge.exe",
                root / "Chromium/Application/chrome.exe",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None
