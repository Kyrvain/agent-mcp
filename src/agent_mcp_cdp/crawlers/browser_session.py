from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx
from playwright.async_api import Browser, Page, async_playwright

from ..config import Settings


class BrowserSession:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.browser: Browser | None = None
        self.browser_mode = "unknown"
        self.process: subprocess.Popen[Any] | None = None
        self._playwright_manager: Any | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._playwright_manager = async_playwright()
        playwright = await self._playwright_manager.__aenter__()
        self.browser, self.process, self.browser_mode = await self._connect_or_launch(
            playwright
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self.browser is not None:
                await self.browser.close()
        finally:
            try:
                if self.process is not None and self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
            finally:
                if self._playwright_manager is not None:
                    await self._playwright_manager.__aexit__(exc_type, exc, traceback)

    async def new_page(self) -> Page:
        if self.browser is None:
            raise RuntimeError("Browser session is not open.")

        if self.browser.contexts:
            context = self.browser.contexts[0]
        else:
            context = await self.browser.new_context(
                viewport={"width": 1440, "height": 1200},
                ignore_https_errors=True,
            )
        page = await context.new_page()
        await page.set_viewport_size({"width": 1440, "height": 1200})
        return page

    async def _connect_or_launch(
        self,
        playwright: Any,
    ) -> tuple[Browser, subprocess.Popen[Any] | None, str]:
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
