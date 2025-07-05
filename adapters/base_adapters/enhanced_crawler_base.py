"""
Enhanced Base Crawler with Integrated Error Handling
Provides a robust foundation for all site adapters with comprehensive error management
"""

import logging
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Browser, Page, TimeoutError
from abc import ABC, abstractmethod
from pathlib import Path
import uuid

from .enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    error_handler_decorator,
    get_global_error_handler
)


class EnhancedCrawlerBase(ABC):
    """
    Enhanced base crawler with integrated error handling and monitoring
    
    This class provides:
    - Comprehensive error handling with correlation
    - Circuit breaker pattern implementation
    - Automatic recovery strategies
    - Performance monitoring
    - Resource management
    - Standardized adapter interface
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.adapter_name = config.get('name', self.__class__.__name__)
        self.logger = logging.getLogger(f"crawler.{self.adapter_name}")
        
        # Initialize error handling
        self.error_handler = get_global_error_handler()
        
        # Browser and page management
        self.playwright_context = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        # Session management
        self.session_id = str(uuid.uuid4())
        self.current_url = None
        self.is_initialized = False
        
        # Performance tracking
        self.start_time = None
        self.operation_times = {}
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0,
            'last_success_time': None,
            'last_failure_time': None
        }
        
        # Current operation context
        self.current_context: Optional[ErrorContext] = None
        
        self.logger.info(f"Enhanced {self.adapter_name} crawler initialized")

    @error_handler_decorator(
        operation_name="initialize",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def initialize(self) -> None:
        """Initialize the crawler with comprehensive error handling"""
        try:
            self.logger.info(f"Initializing {self.adapter_name} crawler")
            
            # Setup browser environment
            await self._setup_browser()
            await self._create_page()
            await self._configure_page()
            
            # Initialize adapter-specific components
            await self._initialize_adapter_specific()
            
            # Verify initialization
            await self._verify_initialization()
            
            self.is_initialized = True
            self.logger.info(f"{self.adapter_name} crawler initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.adapter_name}: {e}")
            await self._cleanup_on_failure()
            raise

    @error_handler_decorator(
        operation_name="setup_browser",
        category=ErrorCategory.BROWSER,
        severity=ErrorSeverity.HIGH
    )
    async def _setup_browser(self) -> None:
        """Setup browser with optimized configuration"""
        try:
            self.playwright_context = await async_playwright().start()
            
            # Configure browser options based on adapter requirements
            browser_options = self._get_browser_options()
            
            # Launch browser with retry logic
            self.browser = await self.playwright_context.chromium.launch(**browser_options)
            
            self.logger.debug("Browser setup completed successfully")
            
        except Exception as e:
            self.logger.error(f"Browser setup failed: {e}")
            raise

    def _get_browser_options(self) -> Dict[str, Any]:
        """Get browser configuration options"""
        return {
            'headless': self.config.get('headless', True),
            'slow_mo': self.config.get('slow_mo', 0),
            'timeout': self.config.get('browser_timeout', 30000),
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
            ] + self.config.get('browser_args', [])
        }

    @error_handler_decorator(
        operation_name="create_page",
        category=ErrorCategory.BROWSER,
        severity=ErrorSeverity.HIGH
    )
    async def _create_page(self) -> None:
        """Create and configure browser page"""
        try:
            # Create context with specific settings
            context_options = self._get_context_options()
            context = await self.browser.new_context(**context_options)
            
            # Create page
            self.page = await context.new_page()
            
            self.logger.debug("Page created successfully")
            
        except Exception as e:
            self.logger.error(f"Page creation failed: {e}")
            raise

    def _get_context_options(self) -> Dict[str, Any]:
        """Get browser context configuration"""
        options = {
            'viewport': self.config.get('viewport', {'width': 1920, 'height': 1080}),
            'user_agent': self.config.get('user_agent'),
            'locale': self.config.get('locale', 'en-US'),
            'timezone_id': self.config.get('timezone', 'UTC'),
            'ignore_https_errors': self.config.get('ignore_https_errors', False),
            'java_script_enabled': self.config.get('javascript_enabled', True)
        }
        
        # Add extra headers if specified
        if self.config.get('extra_headers'):
            options['extra_http_headers'] = self.config['extra_headers']
        
        # Remove None values
        return {k: v for k, v in options.items() if v is not None}

    @error_handler_decorator(
        operation_name="configure_page",
        category=ErrorCategory.BROWSER,
        severity=ErrorSeverity.MEDIUM
    )
    async def _configure_page(self) -> None:
        """Configure page settings and event handlers"""
        try:
            # Set timeouts
            self.page.set_default_timeout(self.config.get('page_timeout', 30000))
            self.page.set_default_navigation_timeout(self.config.get('navigation_timeout', 30000))
            
            # Setup resource blocking for performance
            if self.config.get('block_resources', True):
                await self.page.route("**/*", self._handle_route)
            
            # Setup event handlers
            self.page.on('pageerror', self._handle_page_error)
            self.page.on('dialog', self._handle_dialog)
            
            if self.config.get('log_requests', False):
                self.page.on('request', self._log_request)
                self.page.on('response', self._log_response)
            
            self.logger.debug("Page configured successfully")
            
        except Exception as e:
            self.logger.error(f"Page configuration failed: {e}")
            raise

    async def _handle_route(self, route, request):
        """Handle routing for resource optimization"""
        try:
            resource_type = request.resource_type
            blocked_types = self.config.get('blocked_resources', ['image', 'stylesheet', 'font', 'media'])
            
            if resource_type in blocked_types:
                await route.abort()
            else:
                await route.continue_()
                
        except Exception as e:
            self.logger.debug(f"Route handling error: {e}")
            await route.continue_()

    def _handle_page_error(self, error):
        """Handle page JavaScript errors"""
        self.logger.warning(f"Page JavaScript error: {error}")

    async def _handle_dialog(self, dialog):
        """Handle browser dialogs (alerts, confirms, etc.)"""
        try:
            self.logger.info(f"Dialog detected: {dialog.type} - {dialog.message}")
            await dialog.accept()
        except Exception as e:
            self.logger.warning(f"Dialog handling failed: {e}")

    def _log_request(self, request):
        """Log HTTP requests"""
        self.logger.debug(f"→ {request.method} {request.url}")

    def _log_response(self, response):
        """Log HTTP responses"""
        self.logger.debug(f"← {response.status} {response.url}")

    @abstractmethod
    async def _initialize_adapter_specific(self) -> None:
        """Initialize adapter-specific components - must be implemented by subclasses"""
        pass

    async def _verify_initialization(self) -> None:
        """Verify that initialization was successful"""
        if not self.browser:
            raise RuntimeError("Browser not initialized")
        if not self.page:
            raise RuntimeError("Page not initialized")

    @error_handler_decorator(
        operation_name="crawl",
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method with comprehensive error handling
        
        Args:
            search_params: Dictionary containing search parameters
            
        Returns:
            List of flight data dictionaries
        """
        if not self.is_initialized:
            await self.initialize()
        
        # Start timing
        self.start_time = time.time()
        self.metrics['total_requests'] += 1
        
        # Create context for this crawl operation
        self.current_context = ErrorContext(
            adapter_name=self.adapter_name,
            operation="crawl",
            search_params=search_params,
            session_id=self.session_id,
            url=self.current_url
        )
        
        try:
            self.logger.info(f"Starting crawl for {self.adapter_name} with params: {search_params}")
            
            # Phase 1: Validation
            await self._validate_search_parameters(search_params)
            
            # Phase 2: Navigation
            await self._navigate_to_search_page()
            
            # Phase 3: Page Setup
            await self._handle_initial_page_setup()
            
            # Phase 4: Form Interaction
            await self._perform_search(search_params)
            
            # Phase 5: Results Extraction
            results = await self._extract_results()
            
            # Phase 6: Data Processing
            processed_results = await self._process_results(results)
            
            # Record success
            self._record_success(processed_results)
            
            return processed_results
            
        except Exception as e:
            self._record_failure(e)
            raise
        finally:
            await self._cleanup_session()

    @error_handler_decorator(
        operation_name="validate_search_parameters",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM
    )
    async def _validate_search_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate search parameters"""
        required_fields = self._get_required_fields()
        
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required field: {field}")
            if not search_params[field]:
                raise ValueError(f"Empty value for required field: {field}")
        
        # Perform specific validations
        await self._validate_specific_parameters(search_params)

    @error_handler_decorator(
        operation_name="navigate_to_search_page",
        category=ErrorCategory.NAVIGATION,
        severity=ErrorSeverity.HIGH
    )
    async def _navigate_to_search_page(self) -> None:
        """Navigate to the search page"""
        try:
            url = self._get_search_url()
            self.current_url = url
            
            await self.page.goto(url, timeout=30000, wait_until='domcontentloaded')
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            self.logger.info(f"Successfully navigated to {url}")
            
        except TimeoutError as e:
            raise TimeoutError(f"Navigation timeout for {self.current_url}: {e}")
        except Exception as e:
            raise RuntimeError(f"Navigation failed for {self.current_url}: {e}")

    @error_handler_decorator(
        operation_name="handle_initial_page_setup",
        category=ErrorCategory.BROWSER,
        severity=ErrorSeverity.MEDIUM
    )
    async def _handle_initial_page_setup(self) -> None:
        """Handle initial page setup (cookies, popups, etc.)"""
        try:
            # Handle cookie consent
            await self._handle_cookie_consent()
            
            # Handle popups and overlays
            await self._handle_popups()
            
            # Handle language/region selection
            await self._handle_localization()
            
            # Wait for page to stabilize
            await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.warning(f"Page setup issues (non-critical): {e}")

    @error_handler_decorator(
        operation_name="perform_search",
        category=ErrorCategory.FORM_FILLING,
        severity=ErrorSeverity.HIGH
    )
    async def _perform_search(self, search_params: Dict[str, Any]) -> None:
        """Perform the search operation"""
        try:
            # Fill search form
            await self._fill_search_form(search_params)
            
            # Submit search
            await self._submit_search()
            
            # Wait for results
            await self._wait_for_results()
            
        except Exception as e:
            raise RuntimeError(f"Search operation failed: {e}")

    @error_handler_decorator(
        operation_name="extract_results",
        category=ErrorCategory.PARSING,
        severity=ErrorSeverity.HIGH
    )
    async def _extract_results(self) -> List[Dict[str, Any]]:
        """Extract flight results from the page"""
        try:
            # Get page content
            content = await self.page.content()
            
            # Parse results using adapter-specific logic
            results = await self._parse_flight_data(content)
            
            self.logger.info(f"Extracted {len(results)} raw results")
            return results
            
        except Exception as e:
            raise RuntimeError(f"Results extraction failed: {e}")

    @error_handler_decorator(
        operation_name="process_results",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM
    )
    async def _process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate extracted results"""
        processed_results = []
        
        for result in results:
            try:
                # Validate result
                if await self._validate_result(result):
                    # Process and normalize
                    processed_result = await self._normalize_result(result)
                    processed_results.append(processed_result)
                else:
                    self.logger.debug(f"Skipping invalid result: {result}")
            except Exception as e:
                self.logger.warning(f"Error processing result: {e}")
        
        self.logger.info(f"Processed {len(processed_results)} valid results from {len(results)} raw results")
        return processed_results

    def _record_success(self, results: List[Dict[str, Any]]) -> None:
        """Record successful operation metrics"""
        duration = time.time() - self.start_time
        self.metrics['successful_requests'] += 1
        self.metrics['last_success_time'] = datetime.now()
        self.metrics['average_response_time'] = (
            (self.metrics['average_response_time'] * (self.metrics['successful_requests'] - 1) + duration) /
            self.metrics['successful_requests']
        )
        
        self.logger.info(f"Crawl completed successfully in {duration:.2f}s with {len(results)} results")

    def _record_failure(self, error: Exception) -> None:
        """Record failed operation metrics"""
        duration = time.time() - self.start_time if self.start_time else 0
        self.metrics['failed_requests'] += 1
        self.metrics['last_failure_time'] = datetime.now()
        
        self.logger.error(f"Crawl failed after {duration:.2f}s: {error}")

    async def _cleanup_session(self) -> None:
        """Cleanup after crawl session"""
        try:
            self.current_context = None
            self.start_time = None
            
            # Clear browser state if configured
            if self.config.get('clear_state_after_crawl', False):
                await self._clear_browser_state()
                
        except Exception as e:
            self.logger.debug(f"Session cleanup error: {e}")

    async def _clear_browser_state(self) -> None:
        """Clear browser state (cookies, storage, etc.)"""
        try:
            if self.page:
                await self.page.evaluate('localStorage.clear()')
                await self.page.evaluate('sessionStorage.clear()')
                
                # Clear cookies
                context = self.page.context
                await context.clear_cookies()
                
        except Exception as e:
            self.logger.debug(f"Browser state clearing failed: {e}")

    async def _cleanup_on_failure(self) -> None:
        """Cleanup resources when initialization fails"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright_context:
                await self.playwright_context.stop()
        except Exception as e:
            self.logger.debug(f"Cleanup on failure error: {e}")

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def _get_search_url(self) -> str:
        """Get the search URL for this adapter"""
        pass

    @abstractmethod
    def _get_required_fields(self) -> List[str]:
        """Get list of required search parameter fields"""
        pass

    @abstractmethod
    async def _validate_specific_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate adapter-specific parameters"""
        pass

    @abstractmethod
    async def _handle_cookie_consent(self) -> None:
        """Handle cookie consent dialog"""
        pass

    @abstractmethod
    async def _handle_popups(self) -> None:
        """Handle popups and overlays"""
        pass

    @abstractmethod
    async def _handle_localization(self) -> None:
        """Handle language/region selection"""
        pass

    @abstractmethod
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fill the search form with parameters"""
        pass

    @abstractmethod
    async def _submit_search(self) -> None:
        """Submit the search form"""
        pass

    @abstractmethod
    async def _wait_for_results(self) -> None:
        """Wait for search results to load"""
        pass

    @abstractmethod
    async def _parse_flight_data(self, content: str) -> List[Dict[str, Any]]:
        """Parse flight data from page content"""
        pass

    @abstractmethod
    async def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate a single flight result"""
        pass

    @abstractmethod
    async def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and standardize a flight result"""
        pass

    # Utility methods
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the crawler"""
        circuit_stats = {}
        try:
            error_stats = self.error_handler.get_error_statistics()
            circuit_stats = error_stats.get('circuit_breakers', {})
        except Exception:
            pass
        
        return {
            'adapter_name': self.adapter_name,
            'session_id': self.session_id,
            'is_initialized': self.is_initialized,
            'browser_active': self.browser is not None,
            'page_active': self.page is not None,
            'current_url': self.current_url,
            'metrics': self.metrics,
            'circuit_breakers': circuit_stats
        }

    async def reset_statistics(self) -> None:
        """Reset all statistics"""
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0,
            'last_success_time': None,
            'last_failure_time': None
        }

    async def close(self) -> None:
        """Close the crawler and cleanup all resources"""
        try:
            self.logger.info(f"Closing {self.adapter_name} crawler")
            
            if self.page:
                await self.page.close()
                self.page = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if self.playwright_context:
                await self.playwright_context.stop()
                self.playwright_context = None
            
            self.is_initialized = False
            self.logger.info(f"{self.adapter_name} crawler closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing {self.adapter_name} crawler: {e}")

    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            if hasattr(self, 'browser') and self.browser:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.close())
                except Exception:
                    pass
        except Exception:
            pass 