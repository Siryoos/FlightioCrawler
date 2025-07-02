"""
Enhanced base crawler with automatic initialization and common crawling logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
from dataclasses import dataclass, field
import logging
from datetime import datetime
import asyncio

# Make playwright imports optional
try:
    from playwright.async_api import Page, TimeoutError, async_playwright, Browser, BrowserContext
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
    
    def __post_init__(self):
        # Set defaults if not provided
        if not self.rate_limiting:
            self.rate_limiting = {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60
            }
        if not self.error_handling:
            self.error_handling = {
                "max_retries": 3,
                "retry_delay": 5,
                "circuit_breaker": {}
            }


T = TypeVar('T', bound='EnhancedBaseCrawler')


class EnhancedBaseCrawler(ABC, Generic[T]):
    """
    Enhanced base crawler that eliminates code duplication.
    
    This class automatically handles:
    - Component initialization (rate limiter, error handler, monitoring)
    - Browser and page management
    - Common crawling workflow
    - Error handling and logging
    - Validation
    - Template method pattern implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize crawler with automatic component setup.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.base_url = self._get_base_url()
        self.search_url = config.get("search_url", self.base_url)
        
        # Browser and page management
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Automatic component initialization
        self.rate_limiter = self._create_rate_limiter()
        self.error_handler = self._create_error_handler()
        self.monitoring = self._create_monitoring()
        self.logger = self._create_logger()
        
        # Initialize adapter-specific components
        self._initialize_adapter()
    
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
    
    async def _setup_browser(self) -> None:
        """Setup browser and page for crawling with enhanced options."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
            # Enhanced browser options
            browser_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            }
            
            self.browser = await self.playwright.chromium.launch(**browser_options)
            
            # Enhanced context options
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extra_http_headers': {
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                },
                'java_script_enabled': True,
                'bypass_csp': True
            }
            
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
            
            # Set additional page options
            await self.page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache'
            })
    
    async def _cleanup_browser(self) -> None:
        """Cleanup browser resources with enhanced error handling."""
        cleanup_tasks = []
        
        try:
            if self.page:
                cleanup_tasks.append(self.page.close())
            if self.context:
                cleanup_tasks.append(self.context.close())
            if self.browser:
                cleanup_tasks.append(self.browser.close())
            
            # Run cleanup tasks concurrently
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                
            if self.playwright:
                await self.playwright.stop()
                
        except Exception as e:
            self.logger.warning(f"Error during browser cleanup: {e}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
    
    def _create_rate_limiter(self) -> RateLimiter:
        """Create rate limiter from config with enhanced defaults."""
        rate_config = self.config.get("rate_limiting", {})
        return RateLimiter(
            requests_per_second=rate_config.get("requests_per_second", 2),
            burst_limit=rate_config.get("burst_limit", 5),
            cooldown_period=rate_config.get("cooldown_period", 60)
        )
    
    def _create_error_handler(self) -> ErrorHandler:
        """Create error handler from config with enhanced defaults."""
        error_config = self.config.get("error_handling", {})
        return ErrorHandler(
            max_retries=error_config.get("max_retries", 3),
            retry_delay=error_config.get("retry_delay", 5),
            circuit_breaker_config=error_config.get("circuit_breaker", {})
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
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method with enhanced workflow and error handling.
        
        This method implements the Template Method pattern:
        1. Setup browser
        2. Apply rate limiting
        3. Validate search parameters
        4. Navigate to search page
        5. Handle cookie consent and language selection
        6. Fill search form
        7. Wait for results to load
        8. Extract results
        9. Validate results
        10. Record metrics
        11. Cleanup browser
        
        Args:
            search_params: Search parameters
            
        Returns:
            List of validated flight data
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Setup browser
            await self._setup_browser()
            
            # Step 2: Apply rate limiting
            await self.rate_limiter.acquire()
            
            # Step 3: Validate parameters
            self._validate_search_params(search_params)
            
            # Step 4: Navigate to search page
            await self._navigate_to_search_page()
            
            # Step 5: Handle cookie consent and language selection
            await self._handle_page_setup()
            
            # Step 6: Fill search form
            await self._fill_search_form(search_params)
            
            # Step 7: Wait for results to load
            await self._wait_for_results()
            
            # Step 8: Extract results
            results = await self._extract_flight_results()
            
            # Step 9: Validate results
            validated_results = self._validate_flight_data(results)
            
            # Step 10: Record success metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            self.monitoring.record_success()
            self.monitoring.record_metric('processing_time', processing_time)
            self.monitoring.record_metric('results_count', len(validated_results))
            
            self.logger.info(f"Successfully crawled {len(validated_results)} flights in {processing_time:.2f}s")
            
            return validated_results
            
        except Exception as e:
            # Enhanced error handling with context
            processing_time = (datetime.now() - start_time).total_seconds()
            adapter_name = self.__class__.__name__.replace('Adapter', '')
            
            self.logger.error(f"Error crawling {adapter_name}: {str(e)} (after {processing_time:.2f}s)")
            self.monitoring.record_error()
            self.monitoring.record_metric('error_processing_time', processing_time)
            
            # Re-raise with enhanced context
            raise RuntimeError(f"Crawling failed for {adapter_name}: {str(e)}") from e
            
        finally:
            # Step 11: Cleanup browser
            await self._cleanup_browser()
    
    async def _handle_page_setup(self) -> None:
        """
        Handle common page setup tasks like cookie consent and language selection.
        
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
        """Handle cookie consent dialogs."""
        try:
            cookie_selectors = [
                'button[data-testid="cookie-accept"]',
                '.cookie-accept',
                '#cookie-accept',
                'button:has-text("Accept")',
                'button:has-text("I Accept")',
                'button:has-text("Accept All")'
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
            container_selector = self.config.get("extraction_config", {}).get("results_parsing", {}).get("container")
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
            'passengers': lambda x: isinstance(x, int) and x > 0,
            'adults': lambda x: isinstance(x, int) and x > 0,
            'children': lambda x: isinstance(x, int) and x >= 0,
            'infants': lambda x: isinstance(x, int) and x >= 0,
            'departure_date': lambda x: isinstance(x, str) and len(x) >= 8,
            'return_date': lambda x: isinstance(x, str) and len(x) >= 8,
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
                    raise RuntimeError("Page not initialized. Call _setup_browser() first.")
                
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
                    self.logger.warning(f"Navigation timeout (attempt {attempt + 1}), retrying...")
                    await asyncio.sleep(2)
                    continue
                else:
                    self.logger.error("Final navigation timeout")
                    raise RuntimeError("Timeout while loading search page") from e
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Navigation error (attempt {attempt + 1}): {e}")
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
        """Extract flight results with enhanced error handling and logging."""
        try:
            # Get container selector from config
            extraction_config = self.config.get("extraction_config", {})
            results_config = extraction_config.get("results_parsing", {})
            container_selector = results_config.get("container")
            
            if not container_selector:
                raise ValueError("No container selector configured for results extraction")
            
            # Wait for container to be present
            await self.page.wait_for_selector(container_selector, timeout=10000)
            
            # Get page content
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Find flight elements
            flight_elements = soup.select(container_selector)
            
            if not flight_elements:
                self.logger.warning("No flight elements found with configured selector")
                return []
            
            # Parse each element
            results = []
            for i, element in enumerate(flight_elements):
                try:
                    flight_data = self._parse_flight_element(element)
                    if flight_data:
                        # Add metadata
                        flight_data.update({
                            'scraped_at': datetime.now().isoformat(),
                            'source_url': self.base_url,
                            'element_index': i
                        })
                        results.append(flight_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing flight element {i}: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(results)} flight results from {len(flight_elements)} elements")
            return results
            
        except Exception as e:
            self.logger.error(f"Error extracting flight results: {str(e)}")
            raise
    
    @abstractmethod
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse individual flight element.
        
        Must be implemented by subclasses.
        This is part of the Template Method pattern.
        """
        pass
    
    def _validate_flight_data(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        price_range = validation_config.get("price_range", {"min": 0, "max": float('inf')})
        duration_range = validation_config.get("duration_range", {"min": 0, "max": 24 * 60})  # max 24 hours
        
        validation_stats = {
            'total': len(results),
            'missing_fields': 0,
            'invalid_price': 0,
            'invalid_duration': 0,
            'valid': 0
        }
        
        for result in results:
            # Check required fields
            if not all(field in result and result[field] for field in required_fields):
                validation_stats['missing_fields'] += 1
                continue
            
            # Check price range
            if "price" in result:
                try:
                    price = float(result["price"])
                    if not (price_range["min"] <= price <= price_range["max"]):
                        validation_stats['invalid_price'] += 1
                        continue
                except (ValueError, TypeError):
                    validation_stats['invalid_price'] += 1
                    continue
            
            # Check duration range
            if "duration_minutes" in result:
                try:
                    duration = int(result["duration_minutes"])
                    if not (duration_range["min"] <= duration <= duration_range["max"]):
                        validation_stats['invalid_duration'] += 1
                        continue
                except (ValueError, TypeError):
                    validation_stats['invalid_duration'] += 1
                    continue
            
            # Additional custom validation
            if self._custom_flight_validation(result):
                validated.append(result)
                validation_stats['valid'] += 1
        
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
                selector.replace(' ', ''),  # Remove spaces
                selector.replace('.', ' .'),  # Add space before classes
                selector.split()[0] if ' ' in selector else selector  # Use first part only
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
            cleaned = re.sub(r'[^\d.,]', '', price_text)
            
            # Handle different decimal separators
            if ',' in cleaned and '.' in cleaned:
                # Assume comma is thousands separator if both present
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned and cleaned.count(',') == 1 and len(cleaned.split(',')[1]) <= 2:
                # Comma as decimal separator
                cleaned = cleaned.replace(',', '.')
            else:
                # Remove commas (thousands separator)
                cleaned = cleaned.replace(',', '')
            
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
            hours_match = re.search(r'(\d+)\s*(?:h|hour|hours)', duration_text)
            minutes_match = re.search(r'(\d+)\s*(?:m|min|minute|minutes)', duration_text)
            
            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(minutes_match.group(1)) if minutes_match else 0
            
            if hours or minutes:
                return hours * 60 + minutes
            
            # Pattern 2: "2:30" format
            time_match = re.search(r'(\d+):(\d+)', duration_text)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                return hours * 60 + minutes
            
            # Pattern 3: Just minutes "150 min"
            minutes_only = re.search(r'(\d+)', duration_text)
            if minutes_only:
                return int(minutes_only.group(1))
            
            return 0
            
        except Exception as e:
            self.logger.debug(f"Error extracting duration from '{duration_text}': {e}")
            return 0
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get information about this adapter.
        
        Returns:
            Dictionary containing adapter metadata
        """
        return {
            'adapter_name': self.__class__.__name__,
            'base_url': self.base_url,
            'search_url': self.search_url,
            'required_fields': self._get_required_search_fields(),
            'config_keys': list(self.config.keys()),
            'has_rate_limiter': self.rate_limiter is not None,
            'has_error_handler': self.error_handler is not None,
            'has_monitoring': self.monitoring is not None
        } 