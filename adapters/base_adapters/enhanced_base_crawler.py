"""
Enhanced base crawler with automatic initialization and common crawling logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime
import asyncio
import gc
import psutil
import os
import weakref
from contextlib import asynccontextmanager
import aiohttp
import random
import traceback
from enum import Enum
import time
import json
from pathlib import Path
import uuid  # Added for UUID session management
import re
import warnings

# Make playwright imports optional
try:
    from playwright.async_api import (
        Page,
        TimeoutError,
        async_playwright,
        Browser,
        BrowserContext,
    )

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    # Playwright not available - create dummy classes for type hints
    Page = Any
    TimeoutError = Exception
    Browser = Any
    BrowserContext = Any
    PLAYWRIGHT_AVAILABLE = False

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BS4_AVAILABLE = False

from rate_limiter import RateLimiter
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler
from monitoring import Monitoring
from utils.request_batcher import RequestBatcher, RequestSpec
# All error handling unified in enhanced_error_handler.py
from .enhanced_error_handler import (
    EnhancedErrorHandler,
    CommonErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    ErrorContext,
    AdapterError,
    NavigationError,
    FormFillingError,
    ExtractionError,
    ValidationError,
    TimeoutError,
    AdapterTimeoutError,
    AdapterNetworkError,
    ErrorRecoveryStrategies,
    error_handler_decorator,
    get_global_error_handler
)
# Adapter configuration helpers
from ..patterns import AdapterConfigBuilder
from monitoring.enhanced_monitoring_system import EnhancedMonitoringSystem
from adapters.strategies.parsing_strategies import (
    ParsingStrategyFactory,
    ParseContext,
    FlightParsingStrategy
)


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_errors: List[str] = field(default_factory=lambda: [
        "TimeoutError", "NavigationError", "NetworkError", "ConnectionError"
    ])


@dataclass
class ResourceTracker:
    """Track resource usage for memory monitoring"""
    browser_count: int = 0
    context_count: int = 0
    page_count: int = 0
    http_session_count: int = 0
    memory_usage_mb: float = 0.0
    peak_memory_mb: float = 0.0
    
    def update_memory_usage(self):
        """Update current memory usage"""
        process = psutil.Process(os.getpid())
        self.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        if self.memory_usage_mb > self.peak_memory_mb:
            self.peak_memory_mb = self.memory_usage_mb


# Global resource tracker
_resource_tracker = ResourceTracker()


@dataclass
class CrawlerConfig:
    """Enhanced configuration with type safety"""

    base_url: str
    search_url: str
    rate_limiting: Dict[str, Any] = field(default_factory=dict)
    error_handling: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)
    extraction_config: Dict[str, Any] = field(default_factory=dict)
    data_validation: Dict[str, Any] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    retry_config: Dict[str, Any] = field(default_factory=dict)
    proxy: Optional[str] = None  # e.g. "http://user:pass@host:port"
    user_agents: List[str] = field(default_factory=list)
    default_headers: Dict[str, str] = field(default_factory=dict)
    # Added browser configuration options
    headless: bool = True
    slow_mo: int = 0
    browser_timeout: int = 30000
    page_timeout: int = 30000
    navigation_timeout: int = 30000
    viewport: Dict[str, int] = field(default_factory=lambda: {'width': 1920, 'height': 1080})
    locale: str = 'en-US'
    timezone: str = 'UTC'
    ignore_https_errors: bool = False
    javascript_enabled: bool = True
    extra_headers: Optional[Dict[str, str]] = None
    browser_args: List[str] = field(default_factory=list)
    block_resources: bool = True
    blocked_resources: List[str] = field(default_factory=lambda: ['image', 'stylesheet', 'font', 'media'])
    log_requests: bool = False

    def __post_init__(self):
        # Set defaults if not provided
        if not self.rate_limiting:
            self.rate_limiting = {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60,
            }
        if not self.error_handling:
            self.error_handling = {
                "max_retries": 3,
                "retry_delay": 5,
                "circuit_breaker": {},
                "enable_recovery": True,
            }
        if not self.resource_limits:
            self.resource_limits = {
                "max_memory_mb": 1024,
                "max_processing_time": 300,
                "max_concurrent_sessions": 3,
                "enable_memory_monitoring": True
            }
        if not self.retry_config:
            self.retry_config = {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "exponential_base": 2.0,
                "jitter": True,
            }
        if not self.user_agents:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        if not self.default_headers:
            self.default_headers = {
                'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }


T = TypeVar("T", bound="EnhancedBaseCrawler")


class EnhancedBaseCrawler(ABC, Generic[T]):
    """
    Enhanced base crawler that eliminates code duplication.

    This class automatically handles:
    - Component initialization (rate limiter, error handler, monitoring)
    - Browser and page management with memory optimization
    - Common crawling workflow with centralized error handling
    - Error categorization, retry mechanisms, and recovery strategies
    - Validation and resource cleanup
    - Template method pattern implementation
    - Performance metrics tracking
    - Session management with UUID correlation
    - Browser event handling and resource optimization
    """

    def __init__(self, config: Dict[str, Any], http_session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize crawler with automatic component setup.

        Args:
            config: Configuration dictionary
            http_session: Optional shared aiohttp session
        """
        # Convert dict config to CrawlerConfig object for type safety
        if isinstance(config, dict):
            # Preserve existing config while adding new fields
            self.config = CrawlerConfig(**{k: v for k, v in config.items() if k in CrawlerConfig.__annotations__})
            # Keep original config for backward compatibility
            self.original_config = config
        else:
            self.config = config
            self.original_config = config

        # Basic properties
        self.base_url = self.config.base_url
        self.search_url = self.config.search_url
        self.adapter_name = self.original_config.get("name", self.__class__.__name__)
        
        # UUID-based session management (added from BaseCrawler)
        self.session_id = str(uuid.uuid4())
        self.current_url = None
        
        # Error context template for consistent error reporting (added from BaseCrawler)
        self.error_context_template = {
            "adapter_name": self.adapter_name,
            "session_id": self.session_id,
            "base_url": self.base_url,
            "search_url": self.search_url
        }

        # Initialize components
        self.logger = self._create_logger()
        self.rate_limiter = self._create_rate_limiter()
        self.error_handler = self._create_error_handler()
        self.monitoring = self._create_monitoring()

        # Enhanced error handling with unified system
        self.common_error_handler = CommonErrorHandler(self.logger)
        self.enhanced_error_handler = get_global_error_handler()

        # Resource management
        self.http_session = http_session
        self.request_batcher: Optional[RequestBatcher] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self._is_closed = False

        # Performance metrics tracking (added from EnhancedCrawlerBase)
        self.start_time = None
        self.operation_times = {}
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0,
            'last_success_time': None,
            'last_failure_time': None,
            'page_load_times': [],
            'request_count_by_type': {},
            'error_count_by_type': {}
        }

        # Memory and resource tracking
        self.resource_tracker = ResourceTracker()
        self.retry_config = RetryConfig(**self.config.retry_config)
        self.error_stats = {
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_operation": {},
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "last_error_time": None,
        }
        
        # Resource limits and monitoring
        self.resource_limits = self.config.resource_limits
        self.enable_memory_monitoring = self.resource_limits.get("enable_memory_monitoring", True)
        
        # Resource tracking for cleanup
        self._cleanup_tasks: List[asyncio.Task] = []
        self._own_http_session = False
        self._own_request_batcher = False
        
        # Initialize adapter-specific components
        self._initialize_adapter()

        # Register for cleanup
        weakref.finalize(self, self._cleanup_warning)

        self.logger.info(f"Enhanced {self.adapter_name} crawler initialized with session ID: {self.session_id}")

    def _cleanup_warning(self):
        """Warning for cleanup not being called properly"""
        if not self._is_closed:
            self.logger.warning(f"Crawler {self.__class__.__name__} was not properly closed!")

    async def __aenter__(self: T) -> T:
        """Async context manager entry."""
        await self._setup_browser()
        await self._setup_http_session()
        await self._setup_request_batcher()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with enhanced error handling."""
        if exc_type:
            # Log the exception that caused context exit
            error_context = ErrorContext(
                adapter_name=self.__class__.__name__,
                operation="context_exit",
                additional_info={"exception_type": str(exc_type), "exception_value": str(exc_val)}
            )
            await self._handle_error_with_context(exc_val, error_context)
        
        await self._cleanup_all_resources()

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize errors for better handling"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Check for rate limit first (before timeout) for better categorization
        if "rate limit" in error_message or "429" in error_message:
            return ErrorCategory.RATE_LIMIT
        elif "timeout" in error_message or "timeout" in error_type.lower():
            return ErrorCategory.TIMEOUT
        elif "network" in error_message or "connection" in error_message:
            return ErrorCategory.NETWORK
        elif "auth" in error_message or "401" in error_message or "403" in error_message:
            return ErrorCategory.AUTHENTICATION
        elif "memory" in error_message or "resource" in error_message:
            return ErrorCategory.RESOURCE
        elif isinstance(error, (ExtractionError, ValidationError)):
            return ErrorCategory.VALIDATION
        elif "parse" in error_message or "json" in error_message:
            return ErrorCategory.PARSING
        else:
            return ErrorCategory.UNKNOWN

    def _is_retryable_error(self, error: Exception, category: ErrorCategory) -> bool:
        """Determine if an error is retryable"""
        error_type = type(error).__name__
        
        # Check if error type is in retryable list
        if error_type in self.retry_config.retryable_errors:
            return True
        
        # Check category-based retryability
        retryable_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
        ]
        
        return category in retryable_categories

    async def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay
        )
        
        if self.retry_config.jitter:
            # Add jitter to prevent thundering herd
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay

    async def _handle_error_with_context(
        self, 
        error: Exception, 
        context: ErrorContext,
        should_retry: bool = True
    ) -> bool:
        """
        Enhanced error handling with categorization and recovery
        
        Returns:
            True if operation should be retried, False otherwise
        """
        # Categorize error
        category = self._categorize_error(error)
        
        # Update error statistics
        self._update_error_stats(error, category, context.operation)
        
        # Create enhanced error context
        enhanced_context = ErrorContext(
            adapter_name=context.adapter_name,
            operation=context.operation,
            search_params=context.search_params,
            url=context.url,
            element_index=context.element_index,
            retry_count=context.retry_count,
            additional_info={
                **(context.additional_info or {}),
                "error_category": category.value,
                "error_type": type(error).__name__,
                "timestamp": datetime.now().isoformat(),
                "stack_trace": traceback.format_exc(),
            }
        )
        
        # Log error with enhanced context
        self._log_enhanced_error(error, enhanced_context, category)
        
        # Check if error should be retried
        if should_retry and self._is_retryable_error(error, category):
            if context.retry_count < self.retry_config.max_retries:
                # Attempt error recovery
                recovery_successful = await self._attempt_error_recovery(error, enhanced_context, category)
                
                if recovery_successful:
                    self.error_stats["successful_recoveries"] += 1
                    self.logger.info(f"Error recovery successful for {context.operation}")
                
                return True
        
        # Error is not retryable or max retries reached
        self.logger.error(f"Error handling failed for {context.operation}, not retrying")
        return False

    def _update_error_stats(self, error: Exception, category: ErrorCategory, operation: str):
        """Update comprehensive error statistics"""
        self.error_stats["total_errors"] += 1
        self.error_stats["last_error_time"] = datetime.now()
        
        # Update category stats
        if category.value not in self.error_stats["errors_by_category"]:
            self.error_stats["errors_by_category"][category.value] = 0
        self.error_stats["errors_by_category"][category.value] += 1
        
        # Update operation stats - ensure operation is a string
        operation_key = operation if isinstance(operation, str) else str(operation)
        if operation_key not in self.error_stats["errors_by_operation"]:
            self.error_stats["errors_by_operation"][operation_key] = 0
        self.error_stats["errors_by_operation"][operation_key] += 1

    def _log_enhanced_error(self, error: Exception, context: ErrorContext, category: ErrorCategory):
        """Log error with enhanced formatting and context"""
        operation = context.operation
        error_type = type(error).__name__
        error_message = str(error)
        retry_count = context.retry_count
        
        # Create structured log message
        log_msg = f"[{operation}] {category.value.upper()}: {error_type} - {error_message}"
        
        if retry_count > 0:
            log_msg += f" (Retry {retry_count}/{self.retry_config.max_retries})"
        
        # Log with appropriate level based on category
        if category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT]:
            self.logger.warning(log_msg)
        elif category == ErrorCategory.RATE_LIMIT:
            self.logger.info(log_msg)
        else:
            self.logger.error(log_msg)
        
        # Log additional context at debug level
        if context.additional_info:
            self.logger.debug(f"Error context: {context.additional_info}")

    async def _attempt_error_recovery(
        self, 
        error: Exception, 
        context: ErrorContext, 
        category: ErrorCategory
    ) -> bool:
        """
        Attempt error recovery based on error category
        
        Returns:
            True if recovery was attempted and might be successful
        """
        self.error_stats["recovery_attempts"] += 1
        
        try:
            if category == ErrorCategory.NETWORK:
                await self._recover_from_network_error(error, context)
                return True
            elif category == ErrorCategory.TIMEOUT:
                await self._recover_from_timeout_error(error, context)
                return True
            elif category == ErrorCategory.RATE_LIMIT:
                await self._recover_from_rate_limit_error(error, context)
                return True
            elif category == ErrorCategory.AUTHENTICATION:
                await self._recover_from_auth_error(error, context)
                return True
            elif category == ErrorCategory.RESOURCE:
                await self._recover_from_resource_error(error, context)
                return True
            else:
                # Generic recovery
                await self._generic_error_recovery(error, context)
                return True
        except Exception as recovery_error:
            self.logger.warning(f"Error recovery failed: {recovery_error}")
            return False

    async def _recover_from_network_error(self, error: Exception, context: ErrorContext):
        """Recover from network-related errors"""
        self.logger.info("Attempting network error recovery")
        
        # Wait before retry
        await asyncio.sleep(await self._calculate_retry_delay(context.retry_count))
        
        # Try to refresh page if available
        if self.page and not self.page.is_closed():
            try:
                await ErrorRecoveryStrategies.refresh_page(self.page)
            except Exception as e:
                self.logger.debug(f"Page refresh failed: {e}")

    async def _recover_from_timeout_error(self, error: Exception, context: ErrorContext):
        """Recover from timeout errors"""
        self.logger.info("Attempting timeout error recovery")
        
        # Increase wait time for timeout errors
        delay = await self._calculate_retry_delay(context.retry_count) * 2
        await asyncio.sleep(delay)
        
        # Clear any pending operations
        if self.page and not self.page.is_closed():
            try:
                await self.page.evaluate("window.stop()")
            except Exception as e:
                self.logger.debug(f"Page stop failed: {e}")

    async def _recover_from_rate_limit_error(self, error: Exception, context: ErrorContext):
        """Recover from rate limiting errors"""
        self.logger.info("Attempting rate limit error recovery")
        
        # Wait longer for rate limit errors
        delay = await self._calculate_retry_delay(context.retry_count) * 3
        await asyncio.sleep(delay)
        
        # Switch user agent if possible
        if self.page and not self.page.is_closed():
            try:
                new_user_agent = self._get_random_user_agent()
                await ErrorRecoveryStrategies.switch_user_agent(self.page, new_user_agent)
            except Exception as e:
                self.logger.debug(f"User agent switch failed: {e}")

    async def _recover_from_auth_error(self, error: Exception, context: ErrorContext):
        """Recover from authentication errors"""
        self.logger.info("Attempting authentication error recovery")
        
        # Clear cookies and retry
        if self.page and not self.page.is_closed():
            try:
                await ErrorRecoveryStrategies.clear_cookies_and_retry(self.page)
            except Exception as e:
                self.logger.debug(f"Cookie clearing failed: {e}")

    async def _recover_from_resource_error(self, error: Exception, context: ErrorContext):
        """Recover from resource-related errors"""
        self.logger.info("Attempting resource error recovery")
        
        # Force garbage collection
        gc.collect()
        
        # Check memory usage
        self._check_memory_limits()
        
        # Wait before retry
        await asyncio.sleep(await self._calculate_retry_delay(context.retry_count))

    async def _generic_error_recovery(self, error: Exception, context: ErrorContext):
        """Generic error recovery strategy"""
        self.logger.info("Attempting generic error recovery")
        
        # Basic wait and retry
        await ErrorRecoveryStrategies.wait_and_retry(
            await self._calculate_retry_delay(context.retry_count)
        )

    async def _execute_with_retry(
        self, 
        operation: Callable,
        operation_name: str,
        context_info: Optional[Dict[str, Any]] = None,
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute an operation with retry logic and error handling
        
        Args:
            operation: The async operation to execute
            operation_name: Name of the operation for logging
            context_info: Additional context information
            *args, **kwargs: Arguments to pass to the operation
            
        Returns:
            Result of the operation
            
        Raises:
            Exception: If operation fails after all retries
        """
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Execute the operation
                result = await operation(*args, **kwargs)
                
                # Log success if this was a retry
                if attempt > 0:
                    self.logger.info(f"Operation {operation_name} succeeded after {attempt} retries")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Create error context
                error_context = ErrorContext(
                    adapter_name=self.__class__.__name__,
                    operation=operation_name,
                    retry_count=attempt,
                    additional_info=context_info
                )
                
                # Handle error with context
                should_retry = await self._handle_error_with_context(e, error_context)
                
                if not should_retry or attempt >= self.retry_config.max_retries:
                    break
                
                # Wait before retry
                delay = await self._calculate_retry_delay(attempt)
                self.logger.info(f"Retrying {operation_name} in {delay:.2f} seconds (attempt {attempt + 1})")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        self.logger.error(f"Operation {operation_name} failed after {self.retry_config.max_retries} retries")
        raise last_exception

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        return {
            **self.error_stats,
            "retry_config": {
                "max_retries": self.retry_config.max_retries,
                "base_delay": self.retry_config.base_delay,
                "max_delay": self.retry_config.max_delay,
            },
            "common_error_stats": self.common_error_handler.get_error_statistics(),
        }

    def reset_error_statistics(self):
        """Reset error statistics"""
        self.error_stats = {
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_operation": {},
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "last_error_time": None,
        }
        self.common_error_handler.reset_error_statistics()

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get the base URL for this adapter."""
        pass

    # Additional abstract methods from EnhancedCrawlerBase for standardized interface
    @abstractmethod
    def _get_required_fields(self) -> List[str]:
        """Get required fields for this adapter."""
        pass
    
    @abstractmethod
    async def _validate_specific_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate adapter-specific parameters."""
        pass
    
    @abstractmethod
    async def _handle_popups(self) -> None:
        """Handle popups specific to this adapter."""
        pass
    
    @abstractmethod
    async def _handle_localization(self) -> None:
        """Handle localization specific to this adapter."""
        pass
    
    @abstractmethod
    async def _submit_search(self) -> None:
        """Submit search form."""
        pass
    
    async def _parse_flight_data(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse flight data using centralized parsing strategies.
        
        This method uses the strategy pattern from parsing_strategies.py
        to provide consistent parsing across all adapters.
        """
        try:
            soup = BeautifulSoup(content, 'html.parser')
            flights = []
            
            # Get parsing strategy based on adapter configuration
            parsing_strategy = self._get_parsing_strategy()
            
            # Get flight elements using extraction config
            extraction_config = self.config.get("extraction_config", {})
            results_config = extraction_config.get("results_parsing", {})
            
            # Find flight elements
            flight_selector = results_config.get("flight_element_selector", ".flight-item")
            flight_elements = soup.select(flight_selector)
            
            self.logger.info(f"Found {len(flight_elements)} flight elements to parse")
            
            for i, element in enumerate(flight_elements):
                try:
                    # Use centralized parsing strategy
                    parse_result = parsing_strategy.parse_flight_element(
                        element, ParseContext.FLIGHT_RESULTS
                    )
                    
                    if parse_result.success and parse_result.data:
                        # Add adapter metadata
                        flight_data = parse_result.data.copy()
                        flight_data.update({
                            'source_adapter': self.__class__.__name__,
                            'parsed_at': datetime.now().isoformat(),
                            'element_index': i
                        })
                        
                        # Apply adapter-specific post-processing if needed
                        flight_data = await self._post_process_flight_data(flight_data)
                        
                        flights.append(flight_data)
                        self.logger.debug(f"Successfully parsed flight {i+1}")
                    else:
                        if parse_result.errors:
                            self.logger.warning(f"Parse errors for element {i}: {parse_result.errors}")
                        if parse_result.warnings:
                            self.logger.debug(f"Parse warnings for element {i}: {parse_result.warnings}")
                
                except Exception as e:
                    self.logger.error(f"Error parsing flight element {i}: {e}")
                    continue
            
            self.logger.info(f"Successfully parsed {len(flights)} flights")
            return flights
            
        except Exception as e:
            self.logger.error(f"Error parsing flight data: {e}")
            return []
    
    @abstractmethod
    async def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate individual result."""
        pass
    
    @abstractmethod
    async def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize result to standard format."""
        pass
    
    @abstractmethod
    async def _initialize_adapter_specific(self) -> None:
        """Initialize adapter-specific components."""
        pass

    def _initialize_adapter(self) -> None:
        """
        Hook for adapter-specific initialization.
        Calls the abstract method for adapter-specific setup.
        """
        try:
            # This will call the abstract method implemented by subclasses
            asyncio.create_task(self._initialize_adapter_specific())
        except Exception as e:
            self.logger.warning(f"Error in adapter-specific initialization: {e}")
            # Continue with initialization even if adapter-specific setup fails

    def _get_random_user_agent(self) -> str:
        """Get a random user agent from the list"""
        if not self.config.user_agents:
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        return random.choice(self.config.user_agents)

    async def _setup_http_session(self) -> None:
        """Setup HTTP session if not provided"""
        if not self.http_session:
            # Optimized connector settings for memory efficiency
            connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=5,  # Per host limit
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=30, connect=10)

            headers = self.config.default_headers.copy()
            headers['User-Agent'] = self._get_random_user_agent()
            
            self.http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
            )
            self._own_http_session = True
            _resource_tracker.http_session_count += 1

    async def _setup_request_batcher(self) -> None:
        """Setup request batcher for batching HTTP requests"""
        if not self.request_batcher:
            # Use existing HTTP session if available
            session = self.http_session if self.http_session else None
            
            # Configure batching parameters
            batch_config = getattr(self.config, "request_batching", {})
            batch_size = batch_config.get("batch_size", 8)  # Smaller batches for crawlers
            batch_timeout = batch_config.get("batch_timeout", 0.3)  # Faster timeout for crawlers
            max_concurrent_batches = batch_config.get("max_concurrent_batches", 3)
            
            self.request_batcher = RequestBatcher(
                http_session=session,
                batch_size=batch_size,
                batch_timeout=batch_timeout,
                max_concurrent_batches=max_concurrent_batches,
                enable_compression=True,
                enable_memory_optimization=self.enable_memory_monitoring
            )
            self._own_request_batcher = True
            
            # Initialize the batcher
            await self.request_batcher._setup_session()
            
            self.logger.info(f"Request batcher initialized with batch_size={batch_size}, timeout={batch_timeout}s")

    async def _setup_browser(self) -> None:
        """
        Setup playwright browser and context with enhanced configuration.
        """
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.warning("Playwright is not installed. Skipping browser setup.")
            return

        try:
            self.playwright = await async_playwright().start()
            _resource_tracker.browser_count += 1

            # Use enhanced browser configuration
            browser_options = self._get_browser_options()
            # Add proxy configuration if specified
            if self.config.proxy:
                browser_options['proxy'] = {"server": self.config.proxy}
            
            # Add stability flags
            browser_options.update({
                'handle_sigint': False,
                'handle_sigterm': False,
                'handle_sighup': False
            })

            self.browser = await self.playwright.chromium.launch(**browser_options)
            _resource_tracker.update_memory_usage()

            # Create context with enhanced configuration
            context_options = self._get_context_options()
            # Set user agent if not already set
            if 'user_agent' not in context_options:
                context_options['user_agent'] = self._get_random_user_agent()
            
            self.context = await self.browser.new_context(**context_options)
            
            # Setup enhanced resource blocking
            if self.config.block_resources:
                await self.context.route("**/*", self._handle_route)
            _resource_tracker.context_count += 1
            
            # Create page with enhanced configuration
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.config.page_timeout)
            self.page.set_default_navigation_timeout(self.config.navigation_timeout)
            
            # Setup enhanced event handlers
            self.page.on('pageerror', self._handle_page_error)
            self.page.on('dialog', self._handle_dialog)
            
            # Optional request/response logging
            if self.config.log_requests:
                self.page.on('request', self._log_request)
                self.page.on('response', self._log_response)
            
            _resource_tracker.page_count += 1

            self.logger.info("Enhanced browser and page setup complete.")

        except Exception as e:
            self.logger.error(f"Failed to setup browser: {e}", exc_info=True)
            await self._cleanup_browser()
            raise



    async def _cleanup_browser(self) -> None:
        """Enhanced browser cleanup with memory optimization."""
        cleanup_errors = []
        
        try:
            # Force garbage collection before cleanup
            if self.enable_memory_monitoring:
                gc.collect()
                _resource_tracker.update_memory_usage()
            
            # Cleanup page
            if self.page:
                try:
                    # Clear page cache and memory
                    await self.page.evaluate("window.gc && window.gc()")
                    await self.page.close()
                    _resource_tracker.page_count -= 1
                except Exception as e:
                    cleanup_errors.append(f"Page cleanup error: {e}")
                finally:
                    self.page = None

            # Cleanup context
            if self.context:
                try:
                    await self.context.close()
                    _resource_tracker.context_count -= 1
                except Exception as e:
                    cleanup_errors.append(f"Context cleanup error: {e}")
                finally:
                    self.context = None

            # Cleanup browser
            if self.browser:
                try:
                    await self.browser.close()
                    _resource_tracker.browser_count -= 1
                except Exception as e:
                    cleanup_errors.append(f"Browser cleanup error: {e}")
                finally:
                    self.browser = None

            # Cleanup playwright
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    cleanup_errors.append(f"Playwright cleanup error: {e}")
                finally:
                    self.playwright = None

            # Log cleanup errors if any
            if cleanup_errors:
                self.logger.warning(f"Browser cleanup errors: {'; '.join(cleanup_errors)}")

        except Exception as e:
            self.logger.error(f"Critical error during browser cleanup: {e}")
        finally:
            # Force garbage collection after cleanup
            if self.enable_memory_monitoring:
                gc.collect()
                _resource_tracker.update_memory_usage()

    async def _cleanup_http_session(self) -> None:
        """Cleanup HTTP session"""
        if self.http_session and self._own_http_session:
            try:
                await self.http_session.close()
                _resource_tracker.http_session_count -= 1
            except Exception as e:
                self.logger.warning(f"Error closing HTTP session: {e}")
            finally:
                self.http_session = None
                self._own_http_session = False

    async def _cleanup_request_batcher(self) -> None:
        """Cleanup request batcher"""
        if self.request_batcher and self._own_request_batcher:
            try:
                await self.request_batcher.close()
                self.logger.info("Request batcher closed successfully")
            except Exception as e:
                self.logger.warning(f"Error closing request batcher: {e}")
            finally:
                self.request_batcher = None
                self._own_request_batcher = False

    async def _cleanup_all_resources(self) -> None:
        """Cleanup all resources in proper order"""
        if self._is_closed:
            return
            
        try:
            # Cancel any running tasks
            for task in self._cleanup_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Cleanup request batcher first (depends on HTTP session)
            await self._cleanup_request_batcher()
            
            # Cleanup browser resources
            await self._cleanup_browser()
            
            # Cleanup HTTP session
            await self._cleanup_http_session()
            
            # Force garbage collection
            if self.enable_memory_monitoring:
                gc.collect()
                _resource_tracker.update_memory_usage()
                
            self._is_closed = True
            
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {e}")

    def _check_memory_limits(self) -> None:
        """Check if memory usage exceeds limits"""
        if not self.enable_memory_monitoring:
            return
            
        _resource_tracker.update_memory_usage()
        max_memory = self.resource_limits.get("max_memory_mb", 1024)
        
        if _resource_tracker.memory_usage_mb > max_memory:
            self.logger.warning(
                f"Memory usage ({_resource_tracker.memory_usage_mb:.1f}MB) exceeds limit ({max_memory}MB)"
            )
            # Force garbage collection
            gc.collect()
            _resource_tracker.update_memory_usage()
            
            if _resource_tracker.memory_usage_mb > max_memory * 1.2:  # 20% tolerance
                raise MemoryError(f"Memory usage ({_resource_tracker.memory_usage_mb:.1f}MB) critically exceeds limit")

    def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage statistics"""
        _resource_tracker.update_memory_usage()
        return {
            "browser_count": _resource_tracker.browser_count,
            "context_count": _resource_tracker.context_count,
            "page_count": _resource_tracker.page_count,
            "http_session_count": _resource_tracker.http_session_count,
            "memory_usage_mb": _resource_tracker.memory_usage_mb,
            "peak_memory_mb": _resource_tracker.peak_memory_mb,
            "is_closed": self._is_closed
        }

    def _create_rate_limiter(self) -> RateLimiter:
        """Create rate limiter from config with enhanced defaults."""
        return RateLimiter()

    def _create_error_handler(self) -> EnhancedErrorHandler:
        """Create error handler from config with enhanced defaults."""
        return EnhancedErrorHandler()

    def _create_monitoring(self) -> Monitoring:
        """Create monitoring from config."""
        return Monitoring(self.config.monitoring)

    def _create_logger(self) -> logging.Logger:
        """Create logger for this adapter with enhanced formatting."""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method with enhanced workflow and centralized error handling.

        This method implements the Template Method pattern:
        1. Setup browser (handled by context manager)
        2. Apply rate limiting
        3. Validate search parameters
        4. Navigate to search page
        5. Handle cookie consent and language selection
        6. Fill search form
        7. Wait for results to load
        8. Extract results
        9. Validate results
        10. Record metrics
        11. Cleanup browser (handled by context manager)

        Args:
            search_params: Search parameters

        Returns:
            List of validated flight data
        """
        start_time = datetime.now()
        # Start timing and update metrics
        self.start_time = time.time()
        self.metrics['total_requests'] += 1
        validated_results = []
        
        # Check memory limits before starting
        self._check_memory_limits()
        
        try:
            # Execute main crawling logic with centralized error handling
            validated_results = await self._execute_with_retry(
                self._execute_crawling_workflow,
                "crawl_workflow",
                {"search_params": search_params},
                search_params
            )
            
            # Check memory usage during processing
            self._check_memory_limits()

            # Record successful crawl with enhanced metrics
            self._record_success(validated_results)
            self.monitoring.record_success()

        except Exception as e:
            # Record failure with enhanced metrics
            self._record_failure(e)
            self.monitoring.record_error()
            raise
        finally:
            # Force garbage collection
            if self.enable_memory_monitoring:
                gc.collect()
                _resource_tracker.update_memory_usage()
            
            # Record metrics including memory usage
            duration = (datetime.now() - start_time).total_seconds()
            resource_usage = self.get_resource_usage()
            
            self.monitoring.record_crawl(
                adapter_name=self.__class__.__name__,
                duration=duration,
                flights_found=len(validated_results),
                success=len(validated_results) > 0,
                memory_usage_mb=resource_usage["memory_usage_mb"],
                peak_memory_mb=resource_usage["peak_memory_mb"]
            )
        return validated_results

    async def _execute_crawling_workflow(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the complete crawling workflow with individual error handling for each step."""
        # Step 1: Rate limiting
        await self._execute_with_retry(
            self.rate_limiter.wait,
            "rate_limiting",
            {"search_params": search_params}
        )
        
        # Step 2: Parameter validation
        await self._execute_with_retry(
            self._validate_search_params_async,
            "parameter_validation",
            {"search_params": search_params},
            search_params
        )
        
        # Step 3: Navigation
        await self._execute_with_retry(
            self._navigate_to_search_page,
            "navigation",
            {"url": self.search_url}
        )
        
        # Step 4: Page setup
        await self._execute_with_retry(
            self._handle_page_setup,
            "page_setup",
            {"search_params": search_params}
        )
        
        # Step 5: Form filling
        await self._execute_with_retry(
            self._fill_search_form,
            "form_filling",
            {"search_params": search_params},
            search_params
        )
        
        # Step 6: Wait for results
        await self._execute_with_retry(
            self._wait_for_results,
            "wait_for_results",
            {"search_params": search_params}
        )
        
        # Step 7: Extract and validate results
        validated_results = await self._execute_with_retry(
            self._extract_and_validate_results,
            "extract_and_validate",
            {"search_params": search_params}
        )
        
        return validated_results

    async def _validate_search_params_async(self, search_params: Dict[str, Any]) -> None:
        """Async wrapper for search parameter validation."""
        self._validate_search_params(search_params)

    async def _extract_and_validate_results(self) -> List[Dict[str, Any]]:
        """Extracts and validates flight results."""
        raw_results = await self._extract_flight_results()
        return self._validate_flight_data(raw_results)

    @abstractmethod
    async def _handle_page_setup(self) -> None:
        """
        Hook for page setup tasks (e.g., cookie consent, language selection).

        This is a template method that can be overridden for site-specific setup.
        """
        try:
            # Handle cookie consent
            await self._handle_cookie_consent()

            # Handle language selection
            await self._handle_language_selection()

            # Wait for page to stabilize
            await self.page.wait_for_load_state("networkidle", timeout=10000)

        except Exception as e:
            self.logger.debug(f"Page setup completed with minor issues: {e}")

    async def _handle_cookie_consent(self) -> None:
        """
        Default implementation for cookie consent.
        Override in subclasses if needed.
        """
        try:
            cookie_selectors = [
                'button[data-testid="cookie-accept"]',
                ".cookie-accept",
                "#cookie-accept",
                'button:has-text("Accept")',
                'button:has-text("I Accept")',
                'button:has-text("Accept All")',
            ]

            for selector in cookie_selectors:
                try:
                    await self.page.click(selector, timeout=2000)
                    self.logger.debug("Cookie consent handled")
                    break
                except:
                    continue

        except Exception:
            pass  # Cookie consent is optional

    async def _handle_language_selection(self) -> None:
        """Handle language selection if needed."""
        try:
            # This is a hook for subclasses to implement language selection
            pass
        except Exception:
            pass  # Language selection is optional

    async def _wait_for_results(self) -> None:
        """
        Wait for search results to load with enhanced waiting strategy.

        This method implements multiple waiting strategies:
        1. Wait for specific selectors
        2. Wait for network idle
        3. Wait for JavaScript execution
        """
        try:
            # Strategy 1: Wait for results container
            container_selector = (
                self.config.extraction_config
                .get("results_parsing", {})
                .get("container")
            )
            if container_selector:
                await self.page.wait_for_selector(container_selector, timeout=30000)

            # Strategy 2: Wait for network idle
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            # Strategy 3: Additional wait for dynamic content
            await asyncio.sleep(2)

        except TimeoutError:
            self.logger.warning("Timeout waiting for results - proceeding anyway")
            # Don't raise exception, try to extract what's available

    def _validate_search_params(self, search_params: Dict[str, Any]) -> None:
        """
        Enhanced search parameter validation.

        Validates both required fields and data types/formats.
        """
        required_fields = self._get_required_search_fields()

        # Check required fields
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

        # Enhanced validation with type checking
        self._validate_param_types(search_params)
        self._validate_param_values(search_params)

    def _validate_param_types(self, search_params: Dict[str, Any]) -> None:
        """Validate parameter types."""
        type_validators = {
            "passengers": lambda x: isinstance(x, int) and x > 0,
            "adults": lambda x: isinstance(x, int) and x > 0,
            "children": lambda x: isinstance(x, int) and x >= 0,
            "infants": lambda x: isinstance(x, int) and x >= 0,
            "departure_date": lambda x: isinstance(x, str) and len(x) >= 8,
            "return_date": lambda x: isinstance(x, str) and len(x) >= 8,
        }

        for param, validator in type_validators.items():
            if param in search_params and not validator(search_params[param]):
                raise ValueError(f"Invalid type or value for parameter: {param}")

    def _validate_param_values(self, search_params: Dict[str, Any]) -> None:
        """Validate parameter values and ranges."""
        # This is a hook for subclasses to implement specific validation
        pass

    def _get_required_search_fields(self) -> List[str]:
        """
        Get required search fields from config and adapter.

        Combines config-based fields with adapter-specific requirements.
        """
        config_fields = self.config.data_validation.get("required_fields", ["origin", "destination", "departure_date"])
        try:
            adapter_fields = self._get_required_fields()
        except Exception as e:
            self.logger.warning(f"Error getting adapter-specific required fields: {e}")
            adapter_fields = []
        
        # Combine and deduplicate fields
        all_fields = set(config_fields + adapter_fields)
        return list(all_fields)

    async def _navigate_to_search_page(self) -> None:
        """Navigate to search page - centralized retry logic handled by caller."""
        if not self.page:
            raise NavigationError(
                "Page not initialized. Call _setup_browser() first.",
                ErrorContext(
                    adapter_name=self.__class__.__name__,
                    operation="navigation",
                    url=self.search_url or self.base_url
                )
            )

        try:
            await self.page.goto(self.search_url or self.base_url, timeout=30000)
            await self.page.wait_for_load_state("networkidle", timeout=15000)

            # Verify page loaded correctly
            title = await self.page.title()
            if not title or "error" in title.lower():
                raise NavigationError(
                    f"Page may not have loaded correctly: {title}",
                    ErrorContext(
                        adapter_name=self.__class__.__name__,
                        operation="navigation",
                        url=self.search_url or self.base_url,
                        additional_info={"page_title": title}
                    )
                )

            self.logger.debug(f"Successfully navigated to search page: {title}")

        except TimeoutError as e:
            raise AdapterTimeoutError(
                "Timeout while loading search page",
                ErrorContext(
                    adapter_name=self.__class__.__name__,
                    operation="navigation",
                    url=self.search_url or self.base_url
                )
            ) from e
        except Exception as e:
            # Re-raise as NavigationError for proper categorization
            if not isinstance(e, (NavigationError, AdapterTimeoutError)):
                raise NavigationError(
                    f"Navigation failed: {str(e)}",
                    ErrorContext(
                        adapter_name=self.__class__.__name__,
                        operation="navigation",
                        url=self.search_url or self.base_url
                    )
                ) from e
            raise

    @abstractmethod
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill the search form.

        Must be implemented by subclasses.
        This is part of the Template Method pattern.
        """
        pass

    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """Extract flight results with enhanced error handling and memory optimization."""
        try:
            # Get container selector from config
            extraction_config = self.config.extraction_config
            results_config = extraction_config.get("results_parsing", {})
            container_selector = results_config.get("container")

            if not container_selector:
                raise ExtractionError(
                    "No container selector configured for results extraction",
                    ErrorContext(
                        adapter_name=self.__class__.__name__,
                        operation="extract_flight_results",
                        additional_info={"extraction_config": extraction_config}
                    )
                )

            # Wait for container to be present
            try:
                await self.page.wait_for_selector(container_selector, timeout=10000)
            except TimeoutError as e:
                raise AdapterTimeoutError(
                    f"Timeout waiting for results container: {container_selector}",
                    ErrorContext(
                        adapter_name=self.__class__.__name__,
                        operation="extract_flight_results",
                        additional_info={"container_selector": container_selector}
                    )
                ) from e

            # Get page content
            html = await self.page.content()
            
            # Use generator for memory-efficient parsing
            def parse_flights_generator():
                soup = BeautifulSoup(html, "html.parser")
                flight_elements = soup.select(container_selector)
                
                if not flight_elements:
                    self.logger.warning("No flight elements found with configured selector")
                    return

                for i, element in enumerate(flight_elements):
                    try:
                        flight_data = self._parse_flight_element(element)
                        if flight_data:
                            # Add metadata
                            flight_data.update({
                                "scraped_at": datetime.now().isoformat(),
                                "source_url": self.base_url,
                                "element_index": i,
                            })
                            yield flight_data
                    except Exception as e:
                        self.logger.warning(f"Error parsing flight element {i}: {e}")
                        continue
                    
                    # Periodic memory check and cleanup during parsing
                    if i % 50 == 0:  # Check every 50 elements
                        if self.enable_memory_monitoring:
                            self._check_memory_limits()
                            if i % 100 == 0:  # Force GC every 100 elements
                                gc.collect()

            # Convert generator to list (can be optimized further with streaming)
            results = list(parse_flights_generator())
            
            # Clear HTML content from memory
            html = None
            
            # Force garbage collection after extraction
            if self.enable_memory_monitoring:
                gc.collect()
                _resource_tracker.update_memory_usage()

            self.logger.info(f"Extracted {len(results)} flight results")
            return results

        except (ExtractionError, AdapterTimeoutError):
            # Re-raise specific errors as-is
            raise
        except Exception as e:
            # Force cleanup on error
            if self.enable_memory_monitoring:
                gc.collect()
            # Wrap other exceptions as ExtractionError
            raise ExtractionError(
                f"Error extracting flight results: {str(e)}",
                ErrorContext(
                    adapter_name=self.__class__.__name__,
                    operation="extract_flight_results"
                )
            ) from e

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Parse individual flight element.
        
        This method is deprecated in favor of the centralized parsing strategies.
        Use _parse_flight_data() which leverages parsing_strategies.py instead.
        """
        warnings.warn(
            "_parse_flight_element is deprecated. Use centralized parsing strategies via _parse_flight_data.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Fallback implementation for backward compatibility
        try:
            extraction_config = self.config.get("extraction_config", {})
            results_config = extraction_config.get("results_parsing", {})
            
            # Basic fallback parsing
            flight_data = {
                "flight_number": self._extract_text_safe(element, results_config.get("flight_number")),
                "airline": self._extract_text_safe(element, results_config.get("airline")), 
                "departure_time": self._extract_text_safe(element, results_config.get("departure_time")),
                "arrival_time": self._extract_text_safe(element, results_config.get("arrival_time")),
                "price": self._extract_price(self._extract_text_safe(element, results_config.get("price"))),
                "currency": results_config.get("default_currency", "USD"),
                "source_adapter": self.__class__.__name__
            }
            
            # Basic validation
            if not any([flight_data["flight_number"], flight_data["airline"], flight_data["price"]]):
                return None
                
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error in deprecated _parse_flight_element: {e}")
            return None

    def _extract_price(self, price_text: str) -> float:
        """
        DEPRECATED: Extract price from text.
        
        This method is deprecated in favor of centralized parsing strategies.
        Use the parsing strategies which have more sophisticated price extraction.
        """
        warnings.warn(
            "_extract_price is deprecated. Use centralized parsing strategies instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if not price_text:
            return 0.0
        
        try:
            # Basic price extraction for backward compatibility
            cleaned = re.sub(r'[^\d,.]', '', price_text)
            cleaned = cleaned.replace(',', '')
            return float(cleaned) if cleaned else 0.0
        except Exception:
            return 0.0

    def _extract_duration_minutes(self, duration_text: str) -> int:
        """
        Enhanced duration extraction supporting multiple formats.

        Args:
            duration_text: Duration text (e.g., "2h 30m", "2:30", "150 min")

        Returns:
            Duration in minutes
        """
        if not duration_text:
            return 0

        try:
            duration_text = duration_text.lower().strip()

            # Pattern 1: "2h 30m" or "2 hours 30 minutes"
            hours_match = re.search(r"(\d+)\s*(?:h|hour|hours)", duration_text)
            minutes_match = re.search(
                r"(\d+)\s*(?:m|min|minute|minutes)", duration_text
            )

            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(minutes_match.group(1)) if minutes_match else 0

            if hours or minutes:
                return hours * 60 + minutes

            # Pattern 2: "2:30" format
            time_match = re.search(r"(\d+):(\d+)", duration_text)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                return hours * 60 + minutes

            # Pattern 3: Just minutes "150 min"
            minutes_only = re.search(r"(\d+)", duration_text)
            if minutes_only:
                return int(minutes_only.group(1))

            return 0

        except Exception as e:
            self.logger.debug(f"Error extracting duration from '{duration_text}': {e}")
            return 0

    def _validate_flight_data(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enhanced flight data validation with comprehensive checks.

        Can be overridden for custom validation.
        """
        if not results:
            return []

        validated = []
        validation_config = self.config.data_validation

        # Get validation rules
        required_fields = validation_config.get("required_fields", ["airline", "price"])
        price_range = validation_config.get(
            "price_range", {"min": 0, "max": float("inf")}
        )
        duration_range = validation_config.get(
            "duration_range", {"min": 0, "max": 24 * 60}
        )  # max 24 hours

        validation_stats = {
            "total": len(results),
            "missing_fields": 0,
            "invalid_price": 0,
            "invalid_duration": 0,
            "valid": 0,
        }

        for result in results:
            # Check required fields
            if not all(field in result and result[field] for field in required_fields):
                validation_stats["missing_fields"] += 1
                continue

            # Check price range
            if "price" in result:
                try:
                    price = float(result["price"])
                    if not (price_range["min"] <= price <= price_range["max"]):
                        validation_stats["invalid_price"] += 1
                        continue
                except (ValueError, TypeError):
                    validation_stats["invalid_price"] += 1
                    continue

            # Check duration range
            if "duration_minutes" in result:
                try:
                    duration = int(result["duration_minutes"])
                    if not (duration_range["min"] <= duration <= duration_range["max"]):
                        validation_stats["invalid_duration"] += 1
                        continue
                except (ValueError, TypeError):
                    validation_stats["invalid_duration"] += 1
                    continue

            # Additional custom validation
            if self._custom_flight_validation(result):
                validated.append(result)
                validation_stats["valid"] += 1

        # Log validation statistics
        self.logger.info(f"Validation stats: {validation_stats}")

        return validated

    def _custom_flight_validation(self, flight_data: Dict[str, Any]) -> bool:
        """
        Hook for custom flight validation logic.

        Override in subclasses for specific validation rules.

        Args:
            flight_data: Flight data dictionary

        Returns:
            True if flight data is valid, False otherwise
        """
        return True

    def _extract_text(self, element, selector: str) -> str:
        """
        Enhanced text extraction with multiple fallback strategies.

        Args:
            element: BeautifulSoup element
            selector: CSS selector

        Returns:
            Extracted text or empty string
        """
        if not selector or not element:
            return ""

        try:
            # Strategy 1: Direct selector
            found_element = element.select_one(selector)
            if found_element:
                return found_element.get_text(strip=True)

            # Strategy 2: Try with different selector variations
            variations = [
                selector.replace(" ", ""),  # Remove spaces
                selector.replace(".", " ."),  # Add space before classes
                (
                    selector.split()[0] if " " in selector else selector
                ),  # Use first part only
            ]

            for variation in variations:
                try:
                    found_element = element.select_one(variation)
                    if found_element:
                        return found_element.get_text(strip=True)
                except:
                    continue

            return ""
            
        except Exception as e:
            self.logger.debug(f"Error extracting text with selector '{selector}': {e}")
            return ""

    def _extract_text_safe(self, element, selector: str) -> str:
        """Safe wrapper around _extract_text that never raises exceptions."""
        try:
            return self._extract_text(element, selector)
        except Exception as e:
            self.logger.debug(f"Safe text extraction failed for selector '{selector}': {e}")
            return ""

    async def batch_http_requests(self, requests: List[RequestSpec]) -> List[Any]:
        """Make batched HTTP requests using the request batcher"""
        if not self.request_batcher:
            await self._setup_request_batcher()
        
        if not self.request_batcher:
            # Fallback to individual requests if batcher is not available
            self.logger.warning("Request batcher not available, falling back to individual requests")
            results = []
            for spec in requests:
                try:
                    # Make individual request using HTTP session
                    if not self.http_session:
                        await self._setup_http_session()
                    
                    method = spec.method.upper()
                    kwargs = {
                        'timeout': aiohttp.ClientTimeout(total=spec.timeout),
                        'headers': spec.headers or {}
                    }
                    
                    if spec.params:
                        kwargs['params'] = spec.params
                    if spec.json_data:
                        kwargs['json'] = spec.json_data
                    
                    async with getattr(self.http_session, method.lower())(spec.url, **kwargs) as response:
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            data = await response.json()
                        else:
                            data = await response.text()
                        
                        results.append({
                            'status': response.status,
                            'headers': dict(response.headers),
                            'data': data,
                            'url': str(response.url)
                        })
                except Exception as e:
                    self.logger.error(f"Individual request failed for {spec.url}: {e}")
                    results.append(e)
            return results
        
        # Use batched requests
        tasks = [self.request_batcher.add_request(spec) for spec in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def batch_get_urls(self, urls: List[str], **kwargs) -> List[Any]:
        """Convenience method for batching GET requests"""
        if not self.request_batcher:
            await self._setup_request_batcher()
        
        if self.request_batcher:
            return await self.request_batcher.batch_get_requests(urls, **kwargs)
        else:
            # Fallback
            specs = [RequestSpec(url=url, method="GET", **kwargs) for url in urls]
            return await self.batch_http_requests(specs)
    
    def get_batching_stats(self) -> Dict[str, Any]:
        """Get request batching statistics"""
        if self.request_batcher:
            return self.request_batcher.get_stats()
        return {"error": "Request batcher not initialized"}

    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get information about this adapter.

        Returns:
            Dictionary containing adapter metadata
        """
        resource_usage = self.get_resource_usage()
        batching_stats = self.get_batching_stats()
        
        return {
            "adapter_name": self.__class__.__name__,
            "base_url": self.base_url,
            "search_url": self.search_url,
            "required_fields": self._get_required_search_fields(),
            "config_keys": list(self.config.keys()),
            "has_rate_limiter": self.rate_limiter is not None,
            "has_error_handler": self.error_handler is not None,
            "has_monitoring": self.monitoring is not None,
            "has_request_batcher": self.request_batcher is not None,
            "resource_usage": resource_usage,
            "batching_stats": batching_stats,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the crawler"""
        return {
            'adapter_name': self.__class__.__name__,
            'session_id': self.session_id,
            'is_initialized': not self._is_closed,
            'browser_active': self.browser is not None,
            'page_active': self.page is not None,
            'current_url': self.current_url,
            'search_url': self.search_url,
            'error_stats': self.get_error_statistics(),
            'performance_metrics': self.metrics,
            'resource_usage': self.get_resource_usage(),
            'batching_stats': self.get_batching_stats(),
            'monitoring_stats': await self.monitoring.get_stats() if self.monitoring else None,
            'has_http_session': self.http_session is not None,
            'has_request_batcher': self.request_batcher is not None,
            'memory_monitoring_enabled': self.enable_memory_monitoring,
            'proxy_configured': self.config.proxy is not None,
            'resource_blocking_enabled': self.config.block_resources,
            'request_logging_enabled': self.config.log_requests
        }

    async def reset_statistics(self) -> None:
        """Reset all statistics"""
        if self.monitoring:
            await self.monitoring.reset_stats()

    async def close(self) -> None:
        """Close crawler and cleanup resources"""
        try:
            if self.page:
                await self.page.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            if self.monitoring:
                await self.monitoring.stop_monitoring()
            
            self.logger.info(f"{self.__class__.__name__} closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing {self.__class__.__name__}: {e}")

    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            if hasattr(self, 'browser') and self.browser:
                # Try to close browser if still open
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.close())
                except:
                    pass
        except:
            pass

    def _create_error_context(
        self, 
        operation: str, 
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """Create error context for current operation (added from BaseCrawler)"""
        context = ErrorContext(
            adapter_name=self.adapter_name,
            operation=operation,
            session_id=self.session_id,
            url=self.current_url,
            additional_info={**self.error_context_template, **(additional_info or {})}
        )
        return context

    def _get_browser_options(self) -> Dict[str, Any]:
        """Get browser configuration options (added from EnhancedCrawlerBase)"""
        return {
            'headless': self.config.headless,
            'slow_mo': self.config.slow_mo,
            'timeout': self.config.browser_timeout,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ] + self.config.browser_args
        }

    def _get_context_options(self) -> Dict[str, Any]:
        """Get browser context configuration (added from EnhancedCrawlerBase)"""
        options = {
            'viewport': self.config.viewport,
            'user_agent': self.config.extra_headers.get('User-Agent') if self.config.extra_headers else None,
            'locale': self.config.locale,
            'timezone_id': self.config.timezone,
            'ignore_https_errors': self.config.ignore_https_errors,
            'java_script_enabled': self.config.javascript_enabled
        }
        
        # Add extra headers if specified
        if self.config.extra_headers:
            options['extra_http_headers'] = self.config.extra_headers
        
        # Remove None values
        return {k: v for k, v in options.items() if v is not None}

    async def _handle_route(self, route, request):
        """Handle routing for resource optimization (added from EnhancedCrawlerBase)"""
        try:
            resource_type = request.resource_type
            
            # Track request types for metrics
            if resource_type not in self.metrics['request_count_by_type']:
                self.metrics['request_count_by_type'][resource_type] = 0
            self.metrics['request_count_by_type'][resource_type] += 1
            
            if resource_type in self.config.blocked_resources:
                await route.abort()
            else:
                await route.continue_()
                
        except Exception as e:
            self.logger.debug(f"Route handling error: {e}")
            await route.continue_()

    def _handle_page_error(self, error):
        """Handle page JavaScript errors (added from EnhancedCrawlerBase)"""
        self.logger.warning(f"Page JavaScript error: {error}")
        # Track JavaScript errors
        error_type = "javascript_error"
        if error_type not in self.metrics['error_count_by_type']:
            self.metrics['error_count_by_type'][error_type] = 0
        self.metrics['error_count_by_type'][error_type] += 1

    async def _handle_dialog(self, dialog):
        """Handle browser dialogs (added from EnhancedCrawlerBase)"""
        try:
            self.logger.info(f"Dialog detected: {dialog.type} - {dialog.message}")
            await dialog.accept()
        except Exception as e:
            self.logger.warning(f"Dialog handling failed: {e}")

    def _log_request(self, request):
        """Log HTTP requests (added from EnhancedCrawlerBase)"""
        self.logger.debug(f"→ {request.method} {request.url}")

    def _log_response(self, response):
        """Log HTTP responses (added from EnhancedCrawlerBase)"""
        self.logger.debug(f"← {response.status} {response.url}")

    def _record_success(self, results: List[Dict[str, Any]]) -> None:
        """Record successful crawl operation (added from EnhancedCrawlerBase)"""
        self.metrics['successful_requests'] += 1
        self.metrics['last_success_time'] = datetime.now()
        
        if self.start_time:
            operation_time = time.time() - self.start_time
            self.operation_times[self.session_id] = operation_time
            
            # Update average response time
            total_time = sum(self.operation_times.values())
            self.metrics['average_response_time'] = total_time / len(self.operation_times)
        
        self.logger.info(f"Crawl successful: {len(results)} results retrieved")

    def _record_failure(self, error: Exception) -> None:
        """Record failed crawl operation (added from EnhancedCrawlerBase)"""
        self.metrics['failed_requests'] += 1
        self.metrics['last_failure_time'] = datetime.now()
        
        error_type = type(error).__name__
        if error_type not in self.metrics['error_count_by_type']:
            self.metrics['error_count_by_type'][error_type] = 0
        self.metrics['error_count_by_type'][error_type] += 1
        
        self.logger.error(f"Crawl failed: {error}")

    async def _clear_browser_state(self) -> None:
        """Clear browser state for clean retry (added from EnhancedCrawlerBase)"""
        if self.page and not self.page.is_closed():
            try:
                # Clear cookies
                await self.page.context.clear_cookies()
                
                # Clear local storage
                await self.page.evaluate("localStorage.clear()")
                
                # Clear session storage
                await self.page.evaluate("sessionStorage.clear()")
                
                self.logger.debug("Browser state cleared successfully")
            except Exception as e:
                self.logger.warning(f"Failed to clear browser state: {e}")

    async def _cleanup_session(self) -> None:
        """Clean up session resources (added from EnhancedCrawlerBase)"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            self.logger.debug("Session cleanup completed")
        except Exception as e:
            self.logger.warning(f"Session cleanup failed: {e}")

    def _get_parsing_strategy(self) -> FlightParsingStrategy:
        """
        Get the appropriate parsing strategy for this adapter.
        
        Subclasses can override this to specify their strategy type,
        or it will be auto-detected based on configuration.
        """
        try:
            # Try to auto-detect strategy from config
            strategy = ParsingStrategyFactory.auto_detect_strategy(self.config)
            self.logger.debug(f"Auto-detected parsing strategy: {strategy.__class__.__name__}")
            return strategy
        except Exception as e:
            self.logger.warning(f"Failed to auto-detect strategy, using international: {e}")
            return ParsingStrategyFactory.create_strategy("international", self.config)
    
    async def _post_process_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply adapter-specific post-processing to flight data.
        
        This method can be overridden by subclasses to add adapter-specific
        processing while still using the centralized parsing strategies.
        """
        # Default implementation - no additional processing
        return flight_data
