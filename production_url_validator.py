import aiohttp
from urllib.robotparser import RobotFileParser
from typing import Dict
from config import PRODUCTION_SITES

class ProductionURLValidator:
    """Validates and verifies real website URLs before crawling."""

    async def _check_connectivity(self, url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    return resp.status < 400
        except Exception:
            return False

    async def _check_robots(self, base_url: str) -> bool:
        robots_url = base_url.rstrip('/') + '/robots.txt'
        parser = RobotFileParser()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=10) as resp:
                    if resp.status != 200:
                        return True
                    text = await resp.text()
            parser.parse(text.splitlines())
            return parser.can_fetch('*', '/')
        except Exception:
            return True

    async def validate_target_urls(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for name, cfg in PRODUCTION_SITES.items():
            base_url = cfg.get('base_url')
            ok = await self._check_connectivity(base_url)
            robots_ok = await self._check_robots(base_url)
            results[name] = ok and robots_ok
        return results

if __name__ == '__main__':
    import asyncio
    validator = ProductionURLValidator()
    report = asyncio.run(validator.validate_target_urls())
    for site, status in report.items():
        print(f'{site}: {"ok" if status else "failed"}')
