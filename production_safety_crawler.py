import asyncio
import logging
from typing import Dict
from urllib.robotparser import RobotFileParser

from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import CrawlerMonitor
from site_crawlers import BaseSiteCrawler
from production_url_validator import ProductionURLValidator

logger = logging.getLogger(__name__)

class ProductionSafetyCrawler:
    """Enhanced safety measures for production crawling."""

    def __init__(self):
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.circuit_breakers: Dict[str, ErrorHandler] = {}
        self.request_budgets: Dict[str, int] = {}
        self.monitor = CrawlerMonitor()
        self.validator = ProductionURLValidator()

    async def _pre_crawl_check(self, site_name: str, base_url: str) -> bool:
        validation = await self.validator.validate_target_urls()
        return validation.get(site_name, False)

    async def safe_crawl_with_verification(
        self, site_name: str, crawler: BaseSiteCrawler, search_params: dict
    ) -> list:
        """Safe crawling with real-time verification."""
        base_url = getattr(crawler, "base_url", "")
        if not await self._pre_crawl_check(site_name, base_url):
            logger.warning("Pre-crawl validation failed for %s", site_name)
            return []

        if site_name not in self.rate_limiters:
            self.rate_limiters[site_name] = RateLimiter()
        if site_name not in self.circuit_breakers:
            self.circuit_breakers[site_name] = ErrorHandler()

        try:
            if not await self.rate_limiters[site_name].check_rate_limit(site_name):
                wait = await self.rate_limiters[site_name].get_wait_time(site_name)
                await asyncio.sleep(wait)

            flights = await crawler.search_flights(search_params)
            await self.monitor.track_request(site_name, asyncio.get_event_loop().time())
            self.request_budgets[site_name] = self.request_budgets.get(site_name, 0) + 1
            return flights
        except Exception as exc:  # pragma: no cover - network dependent
            logger.error("Crawl failed for %s: %s", site_name, exc)
            await self.circuit_breakers[site_name].handle_error(site_name, str(exc))
            return []

