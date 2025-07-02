"""
Enhanced base crawler with automatic initialization and common crawling logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
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
from error_handler import ErrorHandler
from monitoring import Monitoring
from utils.request_batcher import RequestBatcher, RequestSpec


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
            }
        if not self.resource_limits:
            self.resource_limits = {
                "max_memory_mb": 1024,
                "max_processing_time": 300,
                "max_concurrent_sessions": 3,
                "enable_memory_monitoring": True
            }


T = TypeVar("T", bound="EnhancedBaseCrawler")


class EnhancedBaseCrawler(ABC, Generic[T]):
    """
    Enhanced base crawler that eliminates code duplication.

    This class automatically handles:
    - Component initialization (rate limiter, error handler, monitoring)
    - Browser and page management with memory optimization
    - Common crawling workflow
    - Error handling and logging
    - Validation
    - Resource cleanup and memory monitoring
    - Template method pattern implementation
    """

    def __init__(self, config: Dict[str, Any], http_session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize crawler with automatic component setup.

        Args:
            config: Configuration dictionary
            http_session: Optional shared aiohttp session
        """
        self.config = config
        self.base_url = self._get_base_url()
        self.search_url = config.get("search_url", self.base_url)

        # Browser and page management
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.http_session = http_session
        self._own_http_session = False
        
        # Request batching
        self.request_batcher: Optional[RequestBatcher] = None
        self._own_request_batcher = False
        
        # Resource tracking
        self._cleanup_tasks: List[asyncio.Task] = []
        self._is_closed = False
        
        # Memory monitoring
        self.resource_limits = config.get("resource_limits", {})
        self.enable_memory_monitoring = self.resource_limits.get("enable_memory_monitoring", True)
        
        # Register for cleanup tracking
        if self.enable_memory_monitoring:
            weakref.finalize(self, self._cleanup_warning)

        # Automatic component initialization
        self.rate_limiter = self._create_rate_limiter()
        self.error_handler = self._create_error_handler()
        self.monitoring = self._create_monitoring()
        self.logger = self._create_logger()

        # Initialize adapter-specific components
        self._initialize_adapter()

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

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self._cleanup_all_resources()

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get the base URL for this adapter."""
        pass

    def _initialize_adapter(self) -> None:
        """
        Hook for adapter-specific initialization.
        Override in subclasses if needed.
        """
        pass

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
            
            self.http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )
            self._own_http_session = True
            _resource_tracker.http_session_count += 1

    async def _setup_request_batcher(self) -> None:
        """Setup request batcher for batching HTTP requests"""
        if not self.request_batcher:
            # Use existing HTTP session if available
            session = self.http_session if self.http_session else None
            
            # Configure batching parameters
            batch_config = self.config.get("request_batching", {})
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
        """Setup browser and page for crawling with enhanced memory optimization."""
        if not self.playwright:
            self.playwright = await async_playwright().start()

            # Memory-optimized browser options
            browser_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    # Memory optimization flags
                    "--memory-pressure-off",
                    "--max_old_space_size=512",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-ipc-flooding-protection",
                    # Disable unnecessary features for memory saving
                    "--disable-extensions",
                    "--disable-plugins",
                    "--disable-images",  # Disable image loading
                    "--disable-javascript-harmony-shipping",
                    "--disable-webgl",
                    "--disable-3d-apis",
                    "--disable-accelerated-2d-canvas",
                    "--disable-accelerated-jpeg-decoding",
                    "--disable-accelerated-mjpeg-decode",
                    "--disable-accelerated-video-decode",
                    "--disable-gpu-memory-buffer-compositor-resources",
                    "--disable-gpu-memory-buffer-video-frames",
                    "--disable-software-rasterizer",
                    # Network optimizations
                    "--aggressive-cache-discard",
                    "--enable-low-res-tiling",
                    "--disable-background-networking"
                ],
            }

            self.browser = await self.playwright.chromium.launch(**browser_options)
            _resource_tracker.browser_count += 1

            # Memory-optimized context options
            context_options = {
                "viewport": {"width": 1366, "height": 768},  # Smaller viewport
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extra_http_headers": {
                    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                "java_script_enabled": True,
                "bypass_csp": True,
                # Memory optimization settings
                "ignore_https_errors": True,
                "color_scheme": "light",
                "reduced_motion": "reduce",  # Disable animations
            }

            self.context = await self.browser.new_context(**context_options)
            _resource_tracker.context_count += 1
            
            # Block resource-heavy content types for memory optimization
            await self.context.route("**/*", self._route_handler)
            
            self.page = await self.context.new_page()
            _resource_tracker.page_count += 1

            # Additional page optimizations
            await self.page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8", 
                "Cache-Control": "no-cache"
            })
            
            # Disable resource-heavy features
            await self.page.evaluate("""
                // Disable animations and transitions
                const style = document.createElement('style');
                style.textContent = `
                    *, *::before, *::after {
                        animation-duration: 0.01ms !important;
                        animation-delay: -0.01ms !important;
                        transition-duration: 0.01ms !important;
                        transition-delay: -0.01ms !important;
                    }
                `;
                document.head.appendChild(style);
            """)
            
    async def _route_handler(self, route):
        """Handle routing to block unnecessary resources"""
        # Block images, fonts, and other heavy resources to save memory
        resource_type = route.request.resource_type
        if resource_type in ['image', 'media', 'font', 'stylesheet']:
            await route.abort()
        else:
            await route.continue_()

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
        rate_config = self.config.get("rate_limiting", {})
        return RateLimiter(
            requests_per_second=rate_config.get("requests_per_second", 2),
            burst_limit=rate_config.get("burst_limit", 5),
            cooldown_period=rate_config.get("cooldown_period", 60),
        )

    def _create_error_handler(self) -> ErrorHandler:
        """Create error handler from config with enhanced defaults."""
        error_config = self.config.get("error_handling", {})
        return ErrorHandler(
            max_retries=error_config.get("max_retries", 3),
            retry_delay=error_config.get("retry_delay", 5),
            circuit_breaker_config=error_config.get("circuit_breaker", {}),
        )

    def _create_monitoring(self) -> Monitoring:
        """Create monitoring from config."""
        return Monitoring(self.config.get("monitoring", {}))

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
        Main crawling method with enhanced workflow and error handling.

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
        validated_results = []
        
        # Check memory limits before starting
        self._check_memory_limits()
        
        try:
            # Main crawling logic
            await self._run_crawling_logic(search_params)
            validated_results = await self._extract_and_validate_results()
            
            # Check memory usage during processing
            self._check_memory_limits()

        except Exception as e:
            self.logger.error(f"Crawling failed: {e}")
            self.error_handler.handle_error(e)
            # Potentially re-raise or handle as per strategy
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
                success=not self.error_handler.has_critical_error(),
                memory_usage_mb=resource_usage["memory_usage_mb"],
                peak_memory_mb=resource_usage["peak_memory_mb"]
            )
        return validated_results

    async def _run_crawling_logic(self, search_params: Dict[str, Any]) -> None:
        """Encapsulates the core crawling steps."""
        await self.rate_limiter.wait()
        self._validate_search_params(search_params)
        await self._navigate_to_search_page()
        await self._handle_page_setup()
        await self._fill_search_form(search_params)
        await self._wait_for_results()

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
                self.config.get("extraction_config", {})
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
        Get required search fields with enhanced defaults.

        Override in subclasses to customize.
        """
        return ["origin", "destination", "departure_date"]

    async def _navigate_to_search_page(self) -> None:
        """Navigate to search page with enhanced error handling and retries."""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if not self.page:
                    raise RuntimeError(
                        "Page not initialized. Call _setup_browser() first."
                    )

                await self.page.goto(self.search_url or self.base_url, timeout=30000)
                await self.page.wait_for_load_state("networkidle", timeout=15000)

                # Verify page loaded correctly
                title = await self.page.title()
                if not title or "error" in title.lower():
                    raise RuntimeError(f"Page may not have loaded correctly: {title}")

                self.logger.debug(f"Successfully navigated to search page: {title}")
                return

            except TimeoutError as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"Navigation timeout (attempt {attempt + 1}), retrying..."
                    )
                    await asyncio.sleep(2)
                    continue
                else:
                    self.logger.error("Final navigation timeout")
                    raise RuntimeError("Timeout while loading search page") from e
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"Navigation error (attempt {attempt + 1}): {e}"
                    )
                    await asyncio.sleep(2)
                    continue
                else:
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
            extraction_config = self.config.get("extraction_config", {})
            results_config = extraction_config.get("results_parsing", {})
            container_selector = results_config.get("container")

            if not container_selector:
                raise ValueError(
                    "No container selector configured for results extraction"
                )

            # Wait for container to be present
            await self.page.wait_for_selector(container_selector, timeout=10000)

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

        except Exception as e:
            self.logger.error(f"Error extracting flight results: {str(e)}")
            # Force cleanup on error
            if self.enable_memory_monitoring:
                gc.collect()
            raise

    @abstractmethod
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse individual flight element.

        Must be implemented by subclasses.
        This is part of the Template Method pattern.
        """
        pass

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
        validation_config = self.config.get("data_validation", {})

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

    def _extract_price(self, price_text: str) -> float:
        """
        Enhanced price extraction with multiple currency support.

        Override for custom price extraction logic.

        Args:
            price_text: Price text to extract from

        Returns:
            Extracted price as float
        """
        if not price_text:
            return 0.0

        try:
            import re

            # Remove common currency symbols and separators
            cleaned = re.sub(r"[^\d.,]", "", price_text)

            # Handle different decimal separators
            if "," in cleaned and "." in cleaned:
                # Assume comma is thousands separator if both present
                cleaned = cleaned.replace(",", "")
            elif (
                "," in cleaned
                and cleaned.count(",") == 1
                and len(cleaned.split(",")[1]) <= 2
            ):
                # Comma as decimal separator
                cleaned = cleaned.replace(",", ".")
            else:
                # Remove commas (thousands separator)
                cleaned = cleaned.replace(",", "")

            return float(cleaned) if cleaned else 0.0

        except Exception as e:
            self.logger.debug(f"Error extracting price from '{price_text}': {e}")
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
            import re

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
