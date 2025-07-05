"""
Enhanced Base crawler class providing comprehensive error handling and monitoring for all crawlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import asyncio
from datetime import datetime
import uuid

from playwright.async_api import Page, TimeoutError
from bs4 import BeautifulSoup

from rate_limiter import RateLimiter
from monitoring import Monitoring
from .enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    error_handler_decorator,
    get_global_error_handler
)


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
    Enhanced abstract base class for all crawler implementations.

    Provides comprehensive functionality including:
    - Configuration management
    - Rate limiting
    - Enhanced error handling with correlation and recovery
    - Circuit breaker pattern
    - Monitoring and metrics
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
        self.adapter_name = config.get("name", self.__class__.__name__)
        self.logger = logging.getLogger(f"crawler.{self.adapter_name}")
        
        # Session management
        self.session_id = str(uuid.uuid4())
        self.current_context: Optional[ErrorContext] = None

        # Initialize common components
        self._setup_rate_limiter()
        self._setup_error_handler()
        self._setup_monitoring()
        
        self.logger.info(f"Enhanced {self.adapter_name} crawler initialized")

    def _setup_rate_limiter(self) -> None:
        """Setup rate limiter from config"""
        rate_config = self.config.get("rate_limiting", {})
        self.rate_limiter = RateLimiter(
            requests_per_second=rate_config.get("requests_per_second", 2),
            burst_limit=rate_config.get("burst_limit", 5),
            cooldown_period=rate_config.get("cooldown_period", 60),
        )

    def _setup_error_handler(self) -> None:
        """Setup enhanced error handler from config"""
        # Use global enhanced error handler for consistency
        self.error_handler = get_global_error_handler()
        
        # Create adapter-specific error context template
        self.error_context_template = {
            "adapter_name": self.adapter_name,
            "session_id": self.session_id,
            "base_url": self.base_url,
            "search_url": self.search_url
        }

    def _setup_monitoring(self) -> None:
        """Setup monitoring from config"""
        monitoring_config = self.config.get("monitoring", {})
        self.monitoring = Monitoring(monitoring_config)

    def _create_error_context(
        self, 
        operation: str, 
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """Create error context for current operation"""
        context = ErrorContext(
            adapter_name=self.adapter_name,
            operation=operation,
            session_id=self.session_id,
            url=self.current_url,
            additional_info={**self.error_context_template, **(additional_info or {})}
        )
        return context

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

    @error_handler_decorator(
        operation_name="navigate_to_search_page",
        category=ErrorCategory.NAVIGATION,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def _navigate_to_search_page(self, page: Page) -> None:
        """
        Navigate to the search page with enhanced error handling.

        Args:
            page: Playwright page object
        """
        try:
            self.current_url = self.search_url
            await page.goto(self.search_url)
            await page.wait_for_load_state("networkidle")
            self.logger.debug(f"Successfully navigated to {self.search_url}")
            
        except TimeoutError as e:
            context = self._create_error_context(
                "navigate_to_search_page",
                {"url": self.search_url, "timeout": self.config.get("timeout", 30)}
            )
            
            should_retry, strategy = await self.error_handler.handle_error(
                e, context, ErrorSeverity.HIGH, ErrorCategory.NAVIGATION
            )
            
            if not should_retry:
                self.logger.error(f"Failed to navigate to search page: {e}")
                raise
            
            # Retry will be handled by the decorator
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

    @error_handler_decorator(
        operation_name="extract_flight_results",
        category=ErrorCategory.PARSING,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def _extract_flight_results(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extract flight results from the page with enhanced error handling.

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

            self.logger.info(f"Successfully extracted {len(results)} flight results")
            return results

        except Exception as e:
            context = self._create_error_context(
                "extract_flight_results",
                {
                    "container_selector": container_selector,
                    "page_url": page.url,
                    "elements_found": len(flight_elements) if 'flight_elements' in locals() else 0
                }
            )
            
            should_retry, strategy = await self.error_handler.handle_error(
                e, context, ErrorSeverity.HIGH, ErrorCategory.PARSING
            )
            
            if not should_retry:
                self.logger.error(f"Failed to extract flight results: {e}")
                raise
            
            # Retry will be handled by the decorator
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

    @error_handler_decorator(
        operation_name="validate_search_params",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        max_retries=1
    )
    def _validate_search_params(self, search_params: Dict[str, Any]) -> None:
        """
        Validate search parameters with enhanced error handling.

        Args:
            search_params: Search parameters to validate

        Raises:
            ValueError: If required parameters are missing
        """
        try:
            required_fields = self.config.get("data_validation", {}).get(
                "required_fields", []
            )
            
            missing_fields = []
            for field in required_fields:
                if field not in search_params:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValueError(f"Missing required search parameters: {missing_fields}")
                
            self.logger.debug("Search parameters validation passed")
            
        except Exception as e:
            context = self._create_error_context(
                "validate_search_params",
                {
                    "search_params": search_params,
                    "required_fields": required_fields,
                    "missing_fields": missing_fields if 'missing_fields' in locals() else []
                }
            )
            
            # For validation errors, we typically don't retry
            asyncio.create_task(self.error_handler.handle_error(
                e, context, ErrorSeverity.MEDIUM, ErrorCategory.VALIDATION, ErrorAction.ABORT
            ))
            
            raise

    @error_handler_decorator(
        operation_name="validate_flight_data",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        max_retries=1
    )
    def _validate_flight_data(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate flight data against configuration rules with enhanced error handling.

        Args:
            results: List of flight data dictionaries

        Returns:
            List of validated flight data dictionaries
        """
        try:
            validation_config = self.config.get("data_validation", {})
            required_fields = validation_config.get("required_fields", [])
            price_range = validation_config.get(
                "price_range", {"min": 0, "max": float("inf")}
            )
            duration_range = validation_config.get(
                "duration_range", {"min": 0, "max": float("inf")}
            )

            validated_results = []
            invalid_count = 0
            
            for result in results:
                # Check required fields
                if not all(field in result for field in required_fields):
                    invalid_count += 1
                    continue

                # Check price range
                if not (price_range["min"] <= result.get("price", 0) <= price_range["max"]):
                    invalid_count += 1
                    continue

                # Check duration range
                if not (
                    duration_range["min"]
                    <= result.get("duration_minutes", 0)
                    <= duration_range["max"]
                ):
                    invalid_count += 1
                    continue

                validated_results.append(result)

            if invalid_count > 0:
                self.logger.warning(f"Filtered out {invalid_count} invalid flight records")
                
            self.logger.info(f"Validated {len(validated_results)} flight records")
            return validated_results
            
        except Exception as e:
            context = self._create_error_context(
                "validate_flight_data",
                {
                    "total_results": len(results),
                    "validation_config": validation_config,
                    "invalid_count": invalid_count if 'invalid_count' in locals() else 0
                }
            )
            
            asyncio.create_task(self.error_handler.handle_error(
                e, context, ErrorSeverity.MEDIUM, ErrorCategory.VALIDATION
            ))
            
            # Return original results if validation fails
            self.logger.warning("Validation failed, returning original results")
            return results

    def _extract_price(self, price_text: str) -> float:
        """
        Extract numeric price from text with error handling.

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
            context = self._create_error_context(
                "extract_price",
                {"price_text": price_text, "cleaned_text": cleaned if 'cleaned' in locals() else None}
            )
            
            # This is a low-severity error, log but don't stop processing
            asyncio.create_task(self.error_handler.handle_error(
                e, context, ErrorSeverity.LOW, ErrorCategory.PARSING
            ))
            
            self.logger.warning(f"Failed to extract price from '{price_text}': {e}")
            return 0.0

    @error_handler_decorator(
        operation_name="safe_crawl",
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def _safe_crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Safely execute crawling with comprehensive error handling and monitoring.

        Args:
            search_params: Search parameters

        Returns:
            List of flight data dictionaries
        """
        start_time = datetime.now()
        
        try:
            # Store current context
            self.current_context = self._create_error_context(
                "safe_crawl",
                {"search_params": search_params, "start_time": start_time.isoformat()}
            )
            
            # Validate parameters
            self._validate_search_params(search_params)

            # Execute crawling
            results = await self.crawl(search_params)

            # Validate results
            validated_results = self._validate_flight_data(results)

            # Record success metrics
            duration = (datetime.now() - start_time).total_seconds()
            self.monitoring.record_success()
            
            self.logger.info(
                f"Safe crawl completed successfully in {duration:.2f}s, "
                f"found {len(validated_results)} valid flights"
            )

            return validated_results

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            context = self._create_error_context(
                "safe_crawl",
                {
                    "search_params": search_params,
                    "duration": duration,
                    "start_time": start_time.isoformat()
                }
            )
            
            should_retry, strategy = await self.error_handler.handle_error(
                e, context, ErrorSeverity.HIGH, ErrorCategory.UNKNOWN
            )
            
            self.monitoring.record_error()
            
            if should_retry:
                self.logger.warning(f"Safe crawl failed, retrying with strategy: {strategy}")
                raise  # Let decorator handle retry
            else:
                self.logger.error(f"Safe crawl failed permanently: {e}")
                raise

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the crawler including error statistics.
        
        Returns:
            Dictionary containing health metrics
        """
        try:
            error_stats = self.error_handler.get_error_statistics()
            
            return {
                "adapter_name": self.adapter_name,
                "session_id": self.session_id,
                "is_healthy": True,
                "error_statistics": error_stats,
                "base_url": self.base_url,
                "search_url": self.search_url,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get health status: {e}")
            return {
                "adapter_name": self.adapter_name,
                "session_id": self.session_id,
                "is_healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def reset_error_state(self) -> None:
        """Reset error state and circuit breakers for this adapter"""
        try:
            await self.error_handler.reset_circuit_breaker(self.adapter_name)
            self.logger.info(f"Reset error state for {self.adapter_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to reset error state: {e}")

    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'logger'):
            self.logger.debug(f"BaseCrawler {self.adapter_name} destroyed")
