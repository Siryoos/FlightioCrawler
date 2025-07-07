import aiohttp
import ssl
import time
import os
import logging
from urllib.robotparser import RobotFileParser
from typing import Dict, Tuple
from config import PRODUCTION_SITES
from security.ssl_manager import get_ssl_manager

logger = logging.getLogger(__name__)

class ProductionURLValidator:
    """Validates and verifies real website URLs before crawling."""

    def __init__(self):
        self.ssl_manager = get_ssl_manager()
        logger.info(f"ProductionURLValidator SSL verification: {self.ssl_manager.config.mode.value} mode")

    async def _check_connectivity(self, url: str) -> Tuple[bool, float, bool, bool]:
        """Return tuple (ok, response_time, rate_limited, anti_bot)"""
        start = time.monotonic()
        try:
            connector = self.ssl_manager.create_aiohttp_connector()
            timeout = aiohttp.ClientTimeout(total=10)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
                async with session.get(url) as resp:
                    rt = time.monotonic() - start
                    text = await resp.text(errors="ignore")
                    rate_limited = resp.status == 429
                    anti_bot = resp.status in {403, 503} and (
                        "captcha" in text.lower() or "cloudflare" in text.lower()
                    )
                    return resp.status < 400, rt, rate_limited, anti_bot
        except ssl.SSLError as e:
            logger.warning(f"SSL error for {url}: {e}")
            return False, float("inf"), False, False
        except aiohttp.ClientSSLError as e:
            logger.warning(f"SSL connection error for {url}: {e}")
            return False, float("inf"), False, False
        except Exception as e:
            logger.warning(f"Connection error for {url}: {e}")
            return False, float("inf"), False, False

    async def _check_robots(self, base_url: str) -> bool:
        robots_url = base_url.rstrip("/") + "/robots.txt"
        parser = RobotFileParser()
        try:
            connector = self.ssl_manager.create_aiohttp_connector()
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(robots_url) as resp:
                    if resp.status != 200:
                        return True
                    text = await resp.text()
            parser.parse(text.splitlines())
            return parser.can_fetch("*", "/")
        except Exception as e:
            logger.warning(f"Robots.txt check failed for {base_url}: {e}")
            return True

    async def validate_target_urls(self) -> Dict[str, bool]:
        """Validate all target URLs for accessibility"""
        results = {}
        
        for site_name, site_config in PRODUCTION_SITES.items():
            base_url = site_config.get("base_url")
            if not base_url:
                results[site_name] = False
                continue
                
            try:
                ok, rt, rate_limited, anti_bot = await self._check_connectivity(base_url)
                robots_ok = await self._check_robots(base_url)
                
                results[site_name] = ok and robots_ok and not rate_limited and not anti_bot
                logger.info(f"URL validation for {site_name}: {'PASS' if results[site_name] else 'FAIL'} "
                           f"(response_time: {rt:.2f}s, rate_limited: {rate_limited}, anti_bot: {anti_bot})")
                
            except Exception as e:
                logger.error(f"Failed to validate {site_name}: {e}")
                results[site_name] = False
        
        return results


if __name__ == "__main__":
    import asyncio

    validator = ProductionURLValidator()
    report = asyncio.run(validator.validate_target_urls())
    for site, status in report.items():
        print(f"{site}: {'ok' if status else 'failed'}")
