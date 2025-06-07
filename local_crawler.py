from dataclasses import dataclass
from typing import Optional
from playwright.async_api import async_playwright, Page

@dataclass
class BrowserConfig:
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000


@dataclass
class CrawlerRunConfig:
    cache_mode: Optional[object] = None
    timeout: int = 30000
    wait_for_timeout: int = 15000
    js_only: bool = False
    screenshot: bool = False
    verbose: bool = False

class AsyncWebCrawler:
    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self.page: Optional[Page] = None

    async def _ensure_browser(self):
        if self.page:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        self._context = await self._browser.new_context(
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height}
        )
        self.page = await self._context.new_page()

    async def goto(self, url: str):
        await self._ensure_browser()
        await self.page.goto(url, timeout=self.config.timeout)

    async def navigate(self, url: str):
        """Navigate to the given URL. Alias for ``goto`` for backward compatibility."""
        await self.goto(url)

    async def wait_for_selector(self, selector: str, timeout: int = 10):
        await self._ensure_browser()
        await self.page.wait_for_selector(selector, timeout=timeout * 1000)
        return True

    async def content(self) -> str:
        await self._ensure_browser()
        return await self.page.content()

    async def execute_js(self, script: str, *args):
        await self._ensure_browser()
        return await self.page.evaluate(script, *args)

    async def screenshot(self, path: str):
        await self._ensure_browser()
        await self.page.screenshot(path=path)

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.page = None
