"""
Base Crawler Class with Environment Management
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path
import aiohttp
from bs4 import BeautifulSoup
import time
import random

from environment_manager import env_manager
from requests.url_requester import AdvancedCrawler

logger = logging.getLogger(__name__)


class BaseSiteCrawler(ABC):
    """Abstract base class for all site crawlers with environment management"""

    def __init__(
        self,
        site_name: str,
        base_url: str,
        rate_limiter=None,
        text_processor=None,
        monitor=None,
        error_handler=None,
    ):
        self.site_name = site_name
        self.base_url = base_url
        self.rate_limiter = rate_limiter
        self.text_processor = text_processor
        self.monitor = monitor
        self.error_handler = error_handler

        # Environment-based configuration
        self.crawler_config = env_manager.get_crawler_config(site_name)
        self.use_mock = env_manager.should_use_mock_data()
        self.should_use_real = env_manager.should_use_real_crawler()

        # Initialize crawler based on environment
        if self.should_use_real:
            self.web_crawler = AdvancedCrawler(use_selenium=True)
            logger.info(f"Initialized real web crawler for {site_name}")
        else:
            self.web_crawler = None
            logger.info(f"Initialized mock crawler for {site_name}")

        # Real request validation
        self.request_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time = None

        logger.info(f"Initialized {site_name} crawler - Mock: {self.use_mock}, Real: {self.should_use_real}")

    async def search_flights(self, search_params: Dict[str, Any]) -> List[Dict]:
        """Main entry point for flight search"""
        env_manager.log_execution_mode(
            self.site_name, f"search_flights({search_params})"
        )

        # Validate real request configuration
        if self.should_use_real:
            await self._validate_real_request_setup()

        try:
            if self.use_mock:
                return await self._search_flights_mock(search_params)
            else:
                return await self._search_flights_real(search_params)
        except Exception as e:
            logger.error(f"Error in {self.site_name} search: {e}")
            if self.error_handler:
                await self.error_handler.handle_error(self.site_name, str(e))
            return []

    async def _validate_real_request_setup(self) -> None:
        """Validate that real request setup is correct"""
        if not self.web_crawler:
            raise RuntimeError(f"Web crawler not initialized for {self.site_name}")
        
        # Validate configuration
        config_validation = env_manager.validate_real_request_config()
        logger.info(f"Real request config validation for {self.site_name}: {config_validation}")
        
        # Check if we should proceed with real requests
        if not config_validation["should_use_real_crawler"]:
            logger.warning(f"Real requests disabled for {self.site_name}")

    async def _search_flights_mock(self, search_params: Dict[str, Any]) -> List[Dict]:
        """Search using mock/cached HTML files"""
        mock_file = env_manager.get_mock_file_path(self.site_name, search_params)

        if not mock_file or not mock_file.exists():
            logger.warning(f"No mock data available for {self.site_name}")
            return []

        try:
            html_content = mock_file.read_text(encoding="utf-8")
            soup = BeautifulSoup(html_content, "html.parser")

            # Parse flights from HTML
            flights = await self.parse_flights(soup, search_params)

            logger.info(f"[MOCK] {self.site_name}: Found {len(flights)} flights")
            return flights

        except Exception as e:
            logger.error(f"Error parsing mock data for {self.site_name}: {e}")
            return []

    async def _search_flights_real(self, search_params: Dict[str, Any]) -> List[Dict]:
        """Search using real web requests"""
        if not self.web_crawler:
            logger.error(f"Web crawler not initialized for {self.site_name}")
            return []

        start_time = time.time()
        self.request_count += 1
        self.last_request_time = time.time()

        try:
            # Build search URL
            search_url = await self.build_search_url(search_params)
            logger.info(f"[REAL] {self.site_name}: Making request to {search_url}")

            # Rate limiting
            if self.rate_limiter:
                await self.rate_limiter.wait_if_needed(self.site_name)

            # Real request validation
            if env_manager.should_validate_response():
                validation_result = await self._validate_real_request(search_url)
                if not validation_result["is_valid"]:
                    logger.warning(f"Real request validation failed for {self.site_name}: {validation_result['reason']}")
                    return []

            # Make the actual request
            success, crawl_data, message = self.web_crawler.crawl(search_url)
            
            if not success:
                logger.error(f"[REAL] {self.site_name}: Crawl failed - {message}")
                return []

            # Anti-bot detection
            if env_manager.should_detect_anti_bot():
                anti_bot_result = self._detect_anti_bot_measures(crawl_data)
                if anti_bot_result["detected"]:
                    logger.warning(f"Anti-bot measures detected for {self.site_name}: {anti_bot_result['measures']}")
                    # Continue but log the detection

            # Track request statistics
            if env_manager.should_track_statistics():
                self._track_request_statistics(start_time, crawl_data)

            # Parse flights from HTML
            html_content = crawl_data.get("html", "")
            if not html_content:
                logger.error(f"[REAL] {self.site_name}: No HTML content received")
                return []

            soup = BeautifulSoup(html_content, "html.parser")
            flights = await self.parse_flights(soup, search_params)

            logger.info(f"[REAL] {self.site_name}: Found {len(flights)} flights")
            return flights

        except Exception as e:
            logger.error(f"[REAL] {self.site_name}: Error during real search - {e}")
            return []

    async def _validate_real_request(self, url: str) -> Dict[str, Any]:
        """Validate real request before making it"""
        validation_result = {
            "is_valid": True,
            "reason": "",
            "response_time": 0,
            "response_size": 0,
            "status_code": 0
        }

        try:
            import aiohttp
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=env_manager.max_response_time) as response:
                    response_time = time.time() - start_time
                    content = await response.text()
                    
                    validation_result.update({
                        "response_time": response_time,
                        "response_size": len(content),
                        "status_code": response.status
                    })

                    # Check response time
                    if response_time > env_manager.max_response_time:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"Response time too slow: {response_time:.2f}s"

                    # Check response size
                    elif len(content) < env_manager.min_response_size:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"Response too small: {len(content)} bytes"

                    # Check status code
                    elif response.status >= 400:
                        validation_result["is_valid"] = False
                        validation_result["reason"] = f"HTTP error: {response.status}"

        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["reason"] = f"Validation error: {str(e)}"

        return validation_result

    def _detect_anti_bot_measures(self, crawl_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anti-bot measures in the response"""
        detection_result = {
            "detected": False,
            "measures": []
        }

        try:
            html_content = crawl_data.get("html", "").lower()
            
            # Common anti-bot indicators
            anti_bot_indicators = [
                "captcha", "cloudflare", "bot detection", "security check",
                "please verify", "human verification", "access denied",
                "blocked", "suspicious activity", "rate limit"
            ]

            for indicator in anti_bot_indicators:
                if indicator in html_content:
                    detection_result["detected"] = True
                    detection_result["measures"].append(indicator)

            # Check for suspicious response patterns
            if crawl_data.get("status_code") in [403, 429, 503]:
                detection_result["detected"] = True
                detection_result["measures"].append(f"HTTP {crawl_data.get('status_code')}")

        except Exception as e:
            logger.warning(f"Error detecting anti-bot measures: {e}")

        return detection_result

    def _track_request_statistics(self, start_time: float, crawl_data: Dict[str, Any]) -> None:
        """Track request statistics for monitoring"""
        try:
            end_time = time.time()
            duration = end_time - start_time
            
            stats = {
                "site": self.site_name,
                "timestamp": time.time(),
                "duration": duration,
                "response_size": len(crawl_data.get("html", "")),
                "status_code": crawl_data.get("status_code", 0),
                "success": bool(crawl_data.get("html"))
            }
            
            # Store statistics (could be sent to monitoring system)
            logger.info(f"Request statistics for {self.site_name}: {stats}")
            
        except Exception as e:
            logger.warning(f"Error tracking request statistics: {e}")

    def get_request_stats(self) -> Dict[str, Any]:
        """Get statistics about real requests"""
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

    @abstractmethod
    async def build_search_url(self, search_params: Dict[str, Any]) -> str:
        """Build search URL from parameters - must be implemented by subclasses"""
        pass

    @abstractmethod
    async def parse_flights(
        self, soup: BeautifulSoup, search_params: Dict[str, Any]
    ) -> List[Dict]:
        """Parse flight data from HTML - must be implemented by subclasses"""
        pass

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def normalize_flight_data(self, raw_flight: Dict, search_params: Dict) -> Dict:
        """Normalize flight data to standard format"""
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


class MockableCrawler(BaseSiteCrawler):
    """Example implementation showing how to extend BaseSiteCrawler"""

    async def build_search_url(self, search_params: Dict[str, Any]) -> str:
        """Build search URL - example implementation"""
        origin = search_params.get("origin", "")
        destination = search_params.get("destination", "")
        date = search_params.get("departure_date", "")

        return f"{self.base_url}/search?from={origin}&to={destination}&date={date}"

    async def parse_flights(
        self, soup: BeautifulSoup, search_params: Dict[str, Any]
    ) -> List[Dict]:
        """Parse flights - example implementation"""
        flights = []

        # This would be implemented by each specific site crawler
        # For now, return empty list as example

        return flights
