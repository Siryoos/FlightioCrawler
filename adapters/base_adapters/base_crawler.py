"""
Base crawler class providing common functionality for all crawlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import asyncio
from datetime import datetime

from playwright.async_api import Page, TimeoutError
from bs4 import BeautifulSoup

from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring


@dataclass
class BaseConfig:
    """Base configuration for all crawlers"""

    timeout: int = 30
    max_retries: int = 3
    rate_limit: float = 1.0
    burst_limit: int = 5
    cooldown_period: int = 60


class BaseCrawler(ABC):
    """
    Abstract base class for all crawler implementations.

    Provides common functionality including:
    - Configuration management
    - Rate limiting
    - Error handling
    - Monitoring
    - Logging
    - Common crawling methods
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base crawler with configuration.

        Args:
            config: Configuration dictionary containing crawler settings
        """
        self.config = config
        self.base_url = config.get("base_url", "")
        self.search_url = config.get("search_url", "")
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize common components
        self._setup_rate_limiter()
        self._setup_error_handler()
        self._setup_monitoring()

    def _setup_rate_limiter(self) -> None:
        """Setup rate limiter from config"""
        rate_config = self.config.get("rate_limiting", {})
        self.rate_limiter = RateLimiter(
            requests_per_second=rate_config.get("requests_per_second", 2),
            burst_limit=rate_config.get("burst_limit", 5),
            cooldown_period=rate_config.get("cooldown_period", 60),
        )

    def _setup_error_handler(self) -> None:
        """Setup error handler from config"""
        error_config = self.config.get("error_handling", {})
        self.error_handler = ErrorHandler(
            max_retries=error_config.get("max_retries", 3),
            retry_delay=error_config.get("retry_delay", 5),
            circuit_breaker_config=error_config.get("circuit_breaker", {}),
        )

    def _setup_monitoring(self) -> None:
        """Setup monitoring from config"""
        monitoring_config = self.config.get("monitoring", {})
        self.monitoring = Monitoring(monitoring_config)

    @abstractmethod
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method that must be implemented by subclasses.

        Args:
            search_params: Search parameters for flight search

        Returns:
            List of flight data dictionaries
        """
        pass

    async def _navigate_to_search_page(self, page: Page) -> None:
        """
        Navigate to the search page.

        Args:
            page: Playwright page object
        """
        try:
            await page.navigate(self.search_url)
            await page.wait_for_load_state("networkidle")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise

    @abstractmethod
    async def _fill_search_form(
        self, page: Page, search_params: Dict[str, Any]
    ) -> None:
        """
        Fill the search form with parameters.

        Args:
            page: Playwright page object
            search_params: Search parameters
        """
        pass

    async def _extract_flight_results(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extract flight results from the page.

        Args:
            page: Playwright page object

        Returns:
            List of flight data dictionaries
        """
        try:
            container_selector = self.config["extraction_config"]["results_parsing"][
                "container"
            ]
            await page.wait_for_selector(container_selector)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            flight_elements = soup.select(container_selector)
            results = []

            for element in flight_elements:
                flight_data = self._parse_flight_element(element)
                if flight_data:
                    results.append(flight_data)

            return results

        except Exception as e:
            self.logger.error(f"Error extracting flight results: {str(e)}")
            raise

    @abstractmethod
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse individual flight element into structured data.

        Args:
            element: BeautifulSoup element containing flight data

        Returns:
            Dictionary containing parsed flight data or None if parsing fails
        """
        pass

    def _validate_search_params(self, search_params: Dict[str, Any]) -> None:
        """
        Validate search parameters.

        Args:
            search_params: Search parameters to validate

        Raises:
            ValueError: If required parameters are missing
        """
        required_fields = self.config.get("data_validation", {}).get(
            "required_fields", []
        )
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

    def _validate_flight_data(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate flight data against configuration rules.

        Args:
            results: List of flight data dictionaries

        Returns:
            List of validated flight data dictionaries
        """
        validation_config = self.config.get("data_validation", {})
        required_fields = validation_config.get("required_fields", [])
        price_range = validation_config.get(
            "price_range", {"min": 0, "max": float("inf")}
        )
        duration_range = validation_config.get(
            "duration_range", {"min": 0, "max": float("inf")}
        )

        validated_results = []
        for result in results:
            # Check required fields
            if not all(field in result for field in required_fields):
                continue

            # Check price range
            if not (price_range["min"] <= result.get("price", 0) <= price_range["max"]):
                continue

            # Check duration range
            if not (
                duration_range["min"]
                <= result.get("duration_minutes", 0)
                <= duration_range["max"]
            ):
                continue

            validated_results.append(result)

        return validated_results

    def _extract_price(self, price_text: str) -> float:
        """
        Extract numeric price from text.

        Args:
            price_text: Price text to extract from

        Returns:
            Extracted price as float
        """
        try:
            import re

            # Remove currency symbols and non-numeric characters
            cleaned = re.sub(r"[^\d.,]", "", price_text)
            # Handle different number formats
            cleaned = cleaned.replace(",", "")
            return float(cleaned)
        except Exception as e:
            self.logger.error(f"Error extracting price from '{price_text}': {e}")
            return 0.0

    async def _safe_crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Safely execute crawling with error handling and monitoring.

        Args:
            search_params: Search parameters

        Returns:
            List of flight data dictionaries
        """
        try:
            # Validate parameters
            self._validate_search_params(search_params)

            # Execute crawling
            results = await self.crawl(search_params)

            # Validate results
            validated_results = self._validate_flight_data(results)

            # Record success
            self.monitoring.record_success()

            return validated_results

        except Exception as e:
            self.logger.error(f"Error in safe crawl: {str(e)}")
            self.monitoring.record_error()
            raise
