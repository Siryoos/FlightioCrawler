import asyncio
import logging
import ssl
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

from environment_manager import env_manager
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler
from monitoring import CrawlerMonitor
from persian_text import PersianTextProcessor
from rate_limiter import RateLimiter
from requests.url_requester import AdvancedCrawler
from stealth_crawler import StealthCrawler
from local_crawler import AsyncWebCrawler, BrowserConfig
from security.ssl_manager import get_ssl_manager

logger = logging.getLogger(__name__)


class BaseSiteCrawler(StealthCrawler, ABC):
    """Unified base class for all site crawlers."""

    def __init__(
        self,
        site_name: str,
        base_url: str,
        rate_limiter: RateLimiter,
        text_processor: PersianTextProcessor,
        monitor: CrawlerMonitor,
        error_handler: EnhancedErrorHandler,
        interval: int = 900,
    ) -> None:
        super().__init__()
        self.site_name = site_name
        self.base_url = base_url
        self.rate_limiter = rate_limiter
        self.text_processor = text_processor
        self.monitor = monitor
        self.error_handler = error_handler
        self.interval = interval

        # Environment configuration
        self.crawler_config = env_manager.get_crawler_config(site_name)
        self.use_mock = env_manager.should_use_mock_data()
        self.should_use_real = env_manager.should_use_real_crawler()

        self.browser_config = BrowserConfig(headless=True, viewport_width=1920, viewport_height=1080)
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        self.ssl_manager = get_ssl_manager()
        self.web_crawler = AdvancedCrawler(use_selenium=True) if self.should_use_real else None

        # Request statistics
        self.request_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time: Optional[float] = None

        logger.info(
            f"Initialized {site_name} crawler - Mock: {self.use_mock}, Real: {self.should_use_real}"
        )

    async def _api_fallback(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback JSON API fetch for sites with dynamic pages."""
        api_url = getattr(self, "api_url", f"{self.base_url}/api/search")
        try:
            connector = self.ssl_manager.create_aiohttp_connector()
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
                async with session.get(api_url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("flights", [])
        except ssl.SSLError as e:
            logger.error(f"SSL error in API fallback for {api_url}: {e}")
        except aiohttp.ClientSSLError as e:
            logger.error(f"SSL connection error in API fallback for {api_url}: {e}")
        except Exception as api_err:
            logger.error(f"API fallback failed: {api_err}")
        return []

    async def _execute_js(self, script: str, *args) -> Any:
        """Execute JavaScript with error handling"""
        try:
            return await self.crawler.execute_js(script, *args)
        except Exception as e:
            logger.error(f"JavaScript execution error: {e}")
            raise

    async def _wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element to be present"""
        try:
            return await self.crawler.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            logger.error(f"Wait for element error: {e}")
            return False

    async def _take_screenshot(self, name: str) -> None:
        """Take screenshot for debugging"""
        try:
            await self.crawler.screenshot(path=f"debug_{self.site_name}_{name}.png")
        except Exception as e:
            logger.error(f"Screenshot error: {e}")

    async def check_rate_limit(self) -> bool:
        """Check rate limit for the site"""
        return self.rate_limiter.check_rate_limit(self.site_name)

    async def get_wait_time(self) -> Optional[int]:
        """Get time to wait before next request"""
        return self.rate_limiter.get_wait_time(self.site_name)

    def process_text(self, text: str) -> str:
        """Process Persian text"""
        return self.text_processor.process(text)

    async def _validate_real_request_setup(self) -> None:
        if not self.web_crawler:
            raise RuntimeError(f"Web crawler not initialized for {self.site_name}")
        config_validation = env_manager.validate_real_request_config()
        logger.info(f"Real request config validation for {self.site_name}: {config_validation}")
        if not config_validation["should_use_real_crawler"]:
            logger.warning(f"Real requests disabled for {self.site_name}")

    async def _validate_real_request(self, url: str) -> Dict[str, Any]:
        validation_result = {
            "is_valid": True,
            "reason": "",
            "response_time": 0,
            "response_size": 0,
            "status_code": 0,
        }
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=env_manager.max_response_time) as response:
                    response_time = time.time() - start_time
                    content = await response.text()
                    validation_result.update(
                        {
                            "response_time": response_time,
                            "response_size": len(content),
                            "status_code": response.status,
                        }
                    )
                    if response_time > env_manager.max_response_time:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"Response time too slow: {response_time:.2f}s"
                    elif len(content) < env_manager.min_response_size:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"Response too small: {len(content)} bytes"
                    elif response.status >= 400:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"HTTP error: {response.status}"
        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["reason"] = f"Validation error: {str(e)}"
        return validation_result

    def _detect_anti_bot_measures(self, crawl_data: Dict[str, Any]) -> Dict[str, Any]:
        detection_result = {"detected": False, "measures": []}
        try:
            html_content = crawl_data.get("html", "").lower()
            anti_bot_indicators = [
                "captcha",
                "cloudflare",
                "bot detection",
                "security check",
                "please verify",
                "human verification",
                "access denied",
                "blocked",
                "suspicious activity",
                "rate limit",
            ]
            for indicator in anti_bot_indicators:
                if indicator in html_content:
                    detection_result["detected"] = True
                    detection_result["measures"].append(indicator)
            if crawl_data.get("status_code") in [403, 429, 503]:
                detection_result["detected"] = True
                detection_result["measures"].append(f"HTTP {crawl_data.get('status_code')}")
        except Exception as e:
            logger.warning(f"Error detecting anti-bot measures: {e}")
        return detection_result

    def _track_request_statistics(self, start_time: float, crawl_data: Dict[str, Any]) -> None:
        try:
            end_time = time.time()
            duration = end_time - start_time
            stats = {
                "site": self.site_name,
                "timestamp": time.time(),
                "duration": duration,
                "response_size": len(crawl_data.get("html", "")),
                "status_code": crawl_data.get("status_code", 0),
                "success": bool(crawl_data.get("html")),
            }
            logger.info(f"Request statistics for {self.site_name}: {stats}")
        except Exception as e:
            logger.warning(f"Error tracking request statistics: {e}")

    def get_request_stats(self) -> Dict[str, Any]:
        total_requests = self.request_count
        success_rate = (self.successful_requests / total_requests * 100) if total_requests > 0 else 0
        return {
            "site_name": self.site_name,
            "total_requests": total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "last_request_time": self.last_request_time,
            "using_real_requests": self.should_use_real,
            "using_mock_data": self.use_mock,
        }

    def get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def normalize_flight_data(self, raw_flight: Dict[str, Any], search_params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "flight_id": raw_flight.get("flight_id", ""),
            "airline": raw_flight.get("airline", ""),
            "flight_number": raw_flight.get("flight_number", ""),
            "origin": search_params.get("origin", ""),
            "destination": search_params.get("destination", ""),
            "departure_time": raw_flight.get("departure_time"),
            "arrival_time": raw_flight.get("arrival_time"),
            "price": raw_flight.get("price", 0),
            "currency": raw_flight.get("currency", "IRR"),
            "seat_class": search_params.get("seat_class", "economy"),
            "aircraft_type": raw_flight.get("aircraft_type"),
            "duration_minutes": raw_flight.get("duration_minutes", 0),
            "flight_type": raw_flight.get("flight_type", "domestic"),
            "source_site": self.site_name,
            "scraped_at": raw_flight.get("scraped_at"),
        }

    @abstractmethod
    async def search_flights(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search flights on the site."""
        raise NotImplementedError
