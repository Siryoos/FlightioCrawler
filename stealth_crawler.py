import random
import os
import inspect
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from local_crawler import BrowserConfig
import asyncio
import time
from config import config
import aiohttp

@dataclass
class BrowserFingerprint:
    """Browser fingerprint configuration"""
    user_agent: str
    viewport_size: Tuple[int, int]
    screen_resolution: Tuple[int, int]
    timezone: str
    language: str
    webgl_vendor: str
    webgl_renderer: str

@dataclass
class HumanBehavior:
    """Human behavior simulation parameters"""
    typing_speed_ms: Tuple[int, int]  # min, max delay between keystrokes
    mouse_movement_style: str  # 'linear', 'curved', 'random'
    scroll_behavior: str  # 'smooth', 'stepped', 'random'
    pause_probability: float  # chance of random pause
    pause_duration_ms: Tuple[int, int]  # min, max pause duration

class StealthCrawler:
    def __init__(self, proxy_manager: Optional[Any] = None, captcha_solver: Optional[Any] = None):
        """Initialize the stealth crawler."""
        self.proxy_manager = proxy_manager
        self.captcha_solver = captcha_solver

    async def generate_random_fingerprint(self) -> BrowserFingerprint:
        """Generate a random browser fingerprint."""
        return BrowserFingerprint(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport_size=(1920, 1080),
            screen_resolution=(1920, 1080),
            timezone="Asia/Tehran",
            language="fa-IR",
            webgl_vendor="Google Inc.",
            webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)"
        )

    async def apply_fingerprint(self, browser_config: BrowserConfig, fingerprint: BrowserFingerprint) -> BrowserConfig:
        """Apply a browser fingerprint to the browser configuration."""
        browser_config.user_agent = fingerprint.user_agent
        browser_config.viewport_width, browser_config.viewport_height = fingerprint.viewport_size
        browser_config.timezone = fingerprint.timezone
        browser_config.language = fingerprint.language
        browser_config.webgl_vendor = fingerprint.webgl_vendor
        browser_config.webgl_renderer = fingerprint.webgl_renderer
        return browser_config

    async def simulate_human_typing(self, element_selector: str, text: str, behavior: HumanBehavior):
        """Simulate human typing behavior in the browser."""
        for char in text:
            await asyncio.sleep(random.uniform(*behavior.typing_speed_ms) / 1000)
            if random.random() < behavior.pause_probability:
                await asyncio.sleep(random.uniform(*behavior.pause_duration_ms) / 1000)

    async def simulate_mouse_movement(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], style: str = 'curved'):
        """Simulate mouse movement from start to end position."""
        if style == 'linear':
            # Linear movement
            pass
        elif style == 'curved':
            # Curved movement
            pass
        elif style == 'random':
            # Random movement
            pass

    async def random_scroll_behavior(self, page_height: int, behavior: HumanBehavior):
        """Simulate random scroll behavior on a page."""
        if behavior.scroll_behavior == 'smooth':
            # Smooth scrolling
            pass
        elif behavior.scroll_behavior == 'stepped':
            # Stepped scrolling
            pass
        elif behavior.scroll_behavior == 'random':
            # Random scrolling
            pass

    async def add_random_delays(self, min_ms: int = 100, max_ms: int = 2000):
        """Add random delays to simulate human interaction."""
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

    async def rotate_proxy(self) -> Optional[str]:
        """Rotate to a new proxy if available."""
        if not self.proxy_manager:
            return None

        get_next = getattr(self.proxy_manager, "get_next_proxy", None)
        if not get_next:
            return None

        proxy = get_next()
        # proxy may be a dict like {'http': 'http://ip:port', 'https': ...}
        # convert to string for convenience when needed
        if isinstance(proxy, dict):
            # choose https if available otherwise http
            proxy_url = proxy.get("https") or proxy.get("http")
        else:
            proxy_url = str(proxy)

        return proxy_url

    async def solve_captcha(self, captcha_image_selector: str) -> bool:
        """Attempt to solve a captcha on the page."""
        if not self.captcha_solver:
            return False

        solve_fn = getattr(self.captcha_solver, "solve", None)
        if not solve_fn:
            return False

        try:
            if inspect.iscoroutinefunction(solve_fn):
                result = await solve_fn(captcha_image_selector)
            else:
                result = solve_fn(captcha_image_selector)
            return bool(result)
        except Exception:
            return False

    async def detect_bot_challenges(self, page_content: str) -> List[str]:
        """Detect bot challenges in the page content."""
        detections: List[str] = []
        if not page_content:
            return detections

        lc = page_content.lower()
        if "captcha" in lc:
            detections.append("captcha")
        if "cloudflare" in lc:
            detections.append("cloudflare")
        if "are you human" in lc or "unusual traffic" in lc or "bot" in lc:
            detections.append("bot_detection")
        return detections

    async def bypass_cloudflare(self) -> bool:
        """Attempt to bypass Cloudflare protection."""
        try:
            await self.rotate_proxy()
            await self.add_random_delays(1000, 3000)
            return True
        except Exception:
            return False

    async def randomize_request_headers(self) -> Dict[str, str]:
        """Randomize HTTP request headers."""
        ua = random.choice(config.CRAWLER.USER_AGENTS)
        accept_langs = [
            "en-US,en;q=0.9",
            "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            "en-GB,en;q=0.8"
        ]
        headers = {
            "User-Agent": ua,
            "Accept-Language": random.choice(accept_langs),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1" if random.random() > 0.5 else "0",
            "Upgrade-Insecure-Requests": "1",
        }
        return headers

class ProxyChainManager:
    def __init__(self, proxy_sources: List[str]):
        """Initialize the proxy chain manager."""
        self.proxy_sources = proxy_sources
        self.proxies: List[str] = []
        for src in proxy_sources:
            if os.path.isfile(src):
                try:
                    with open(src, "r", encoding="utf-8") as f:
                        for line in f:
                            proxy = line.strip()
                            if proxy:
                                self.proxies.append(proxy)
                except Exception:
                    continue
            else:
                if src:
                    self.proxies.append(src)

        random.shuffle(self.proxies)

    async def get_working_proxy_chain(self, chain_length: int = 2) -> List[str]:
        """Get a working proxy chain of the specified length."""
        chain: List[str] = []
        for proxy in self.proxies:
            if await self.test_proxy_health(proxy):
                chain.append(proxy)
            if len(chain) >= chain_length:
                break
        return chain

    async def test_proxy_health(self, proxy: str) -> bool:
        """Test the health of a proxy."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://httpbin.org/ip"
                async with session.get(url, proxy=f"http://{proxy}", timeout=10) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def rotate_proxy_chains(self, interval_minutes: int = 30):
        """Rotate proxy chains at the specified interval."""
        while True:
            random.shuffle(self.proxies)
            await asyncio.sleep(interval_minutes * 60)

    async def get_proxy_geolocation(self, proxy: str) -> Dict[str, str]:
        """Get the geolocation of a proxy."""
        ip = proxy.split(":")[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://ipinfo.io/{ip}/json", timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "ip": ip,
                            "country": data.get("country"),
                            "region": data.get("region"),
                            "city": data.get("city"),
                        }
        except Exception:
            pass
        return {}
