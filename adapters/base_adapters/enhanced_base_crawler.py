"""
Enhanced base crawler with automatic initialization and common crawling logic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TypeVar, Generic
from dataclasses import dataclass, field
import logging
from datetime import datetime

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
        """Setup browser and page for crawling."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = await self.context.new_page()
    
    async def _cleanup_browser(self) -> None:
        """Cleanup browser resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
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
        """Create rate limiter from config."""
        rate_config = self.config.get("rate_limiting", {})
        return RateLimiter(
            requests_per_second=rate_config.get("requests_per_second", 2),
            burst_limit=rate_config.get("burst_limit", 5),
            cooldown_period=rate_config.get("cooldown_period", 60)
        )
    
    def _create_error_handler(self) -> ErrorHandler:
        """Create error handler from config."""
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
        """Create logger for this adapter."""
        return logging.getLogger(self.__class__.__name__)
    
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method with common workflow.
        
        This method implements the standard crawling workflow:
        1. Setup browser
        2. Validate search parameters
        3. Navigate to search page
        4. Fill search form
        5. Extract results
        6. Validate results
        7. Handle monitoring
        8. Cleanup browser
        
        Args:
            search_params: Search parameters
            
        Returns:
            List of validated flight data
        """
        try:
            # Step 1: Setup browser
            await self._setup_browser()
            
            # Step 2: Validate parameters
            self._validate_search_params(search_params)
            
            # Step 3: Navigate to search page
            await self._navigate_to_search_page()
            
            # Step 4: Fill search form
            await self._fill_search_form(search_params)
            
            # Step 5: Extract results
            results = await self._extract_flight_results()
            
            # Step 6: Validate results
            validated_results = self._validate_flight_data(results)
            
            # Step 7: Record success
            self.monitoring.record_success()
            
            return validated_results
            
        except Exception as e:
            # Use adapter name for error message
            adapter_name = self.__class__.__name__.replace('Adapter', '')
            self.logger.error(f"Error crawling {adapter_name}: {str(e)}")
            self.monitoring.record_error()
            raise
        finally:
            # Step 8: Cleanup browser
            await self._cleanup_browser()
    
    def _validate_search_params(self, search_params: Dict[str, Any]) -> None:
        """
        Validate search parameters.
        
        Default implementation checks for required fields.
        Override for custom validation.
        """
        required_fields = self._get_required_search_fields()
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")
    
    def _get_required_search_fields(self) -> List[str]:
        """
        Get required search fields.
        
        Override in subclasses to customize.
        """
        return ["origin", "destination", "departure_date"]
    
    async def _navigate_to_search_page(self) -> None:
        """Navigate to search page with error handling."""
        try:
            if not self.page:
                raise RuntimeError("Page not initialized. Call _setup_browser() first.")
            await self.page.goto(self.search_url or self.base_url)
            await self.page.wait_for_load_state("networkidle")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise
    
    @abstractmethod
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill the search form.
        
        Must be implemented by subclasses.
        """
        pass
    
    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """Extract flight results with common logic."""
        try:
            # Wait for results container
            container_selector = self.config["extraction_config"]["results_parsing"]["container"]
            await self.page.wait_for_selector(container_selector)
            
            # Get page content
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # Find flight elements
            flight_elements = soup.select(container_selector)
            
            # Parse each element
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
        Parse individual flight element.
        
        Must be implemented by subclasses.
        """
        pass
    
    def _validate_flight_data(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate flight data with common logic.
        
        Can be overridden for custom validation.
        """
        validated = []
        validation_config = self.config.get("data_validation", {})
        required_fields = validation_config.get("required_fields", [])
        price_range = validation_config.get("price_range", {"min": 0, "max": float('inf')})
        
        for result in results:
            # Check required fields
            if not all(field in result for field in required_fields):
                continue
            
            # Check price range
            if "price" in result:
                price = result["price"]
                if not (price_range["min"] <= price <= price_range["max"]):
                    continue
            
            validated.append(result)
        
        return validated
    
    def _extract_text(self, element, selector: str) -> str:
        """
        Extract text from element using selector.
        
        Common utility method.
        """
        try:
            if not selector:
                return ""
            found_element = element.select_one(selector)
            return found_element.text.strip() if found_element else ""
        except Exception:
            return ""
    
    def _extract_price(self, price_text: str) -> float:
        """
        Extract price from text.
        
        Override for custom price extraction logic.
        """
        try:
            # Remove common currency symbols and separators
            cleaned = price_text.replace("$", "").replace("€", "").replace(",", "")
            cleaned = cleaned.replace("USD", "").replace("EUR", "").strip()
            return float(cleaned)
        except Exception:
            return 0.0 