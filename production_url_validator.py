import aiohttp
import time
from urllib.robotparser import RobotFileParser
from typing import Dict, Tuple
from config import PRODUCTION_SITES


class ProductionURLValidator:
    """Validates and verifies real website URLs before crawling."""

    async def _check_connectivity(self, url: str) -> Tuple[bool, float, bool, bool]:
        """Return tuple (ok, response_time, rate_limited, anti_bot)"""
        start = time.monotonic()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    rt = time.monotonic() - start
                    text = await resp.text(errors="ignore")
                    rate_limited = resp.status == 429
                    anti_bot = resp.status in {403, 503} and (
                        "captcha" in text.lower() or "cloudflare" in text.lower()
                    )
                    return resp.status < 400, rt, rate_limited, anti_bot
        except Exception:
            return False, float("inf"), False, False

    async def _check_robots(self, base_url: str) -> bool:
        robots_url = base_url.rstrip("/") + "/robots.txt"
        parser = RobotFileParser()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=10) as resp:
                    if resp.status != 200:
                        return True
                    text = await resp.text()
            parser.parse(text.splitlines())
            return parser.can_fetch("*", "/")
        except Exception:
            return True

    async def validate_target_urls(self) -> Dict[str, bool]:
        """Validate each target URL and return mapping of site -> status"""
        results: Dict[str, bool] = {}
        for name, cfg in PRODUCTION_SITES.items():
            base_url = cfg.get("base_url")
            ok, rt, rate_limited, anti_bot = await self._check_connectivity(base_url)
            robots_ok = await self._check_robots(base_url)
            results[name] = all([ok, robots_ok]) and not rate_limited and not anti_bot
        return results


if __name__ == "__main__":
    import asyncio

    validator = ProductionURLValidator()
    report = asyncio.run(validator.validate_target_urls())
    for site, status in report.items():
        print(f"{site}: {'ok' if status else 'failed'}")
