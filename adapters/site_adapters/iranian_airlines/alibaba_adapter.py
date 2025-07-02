"""
Optimized Alibaba adapter using EnhancedBaseCrawler with memory efficiency.
"""

from typing import Dict, List, Optional, Any
import logging
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError
import gc

from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
from scripts.performance_profiler import profile_crawler_operation
from utils.memory_efficient_cache import cached
from utils.lazy_loader import get_config_loader


class AlibabaAdapter(EnhancedBaseCrawler):
    """
    Memory-optimized Alibaba.ir adapter with enhanced resource management.
    
    Features:
    - Automatic memory monitoring
    - Efficient DOM parsing with minimal memory footprint
    - Lazy configuration loading
    - Proper resource cleanup
    - Performance profiling integration
    """

    def __init__(self, config: Optional[Dict] = None):
        # Load config lazily if not provided
        if config is None:
            config_loader = get_config_loader()
            config = config_loader.load_site_config("alibaba")
        
        super().__init__(config)

    def _get_base_url(self) -> str:
        """Get the base URL for Alibaba"""
        return "https://www.alibaba.ir"

    def _initialize_adapter(self) -> None:
        """Initialize Alibaba-specific components"""
        # Cache frequently accessed config values for performance
        self._extraction_config = self.config.get("extraction_config", {})
        self._search_form_config = self._extraction_config.get("search_form", {})
        self._results_config = self._extraction_config.get("results_parsing", {})
        
        self.logger.info("Alibaba adapter initialized with memory optimizations")

    @profile_crawler_operation("alibaba_crawl")
    async def _handle_page_setup(self) -> None:
        """Handle Alibaba-specific page setup with memory optimization"""
        try:
            # Handle cookie consent efficiently
            await self._handle_alibaba_cookie_consent()
            
            # Handle language selection
            await self._handle_alibaba_language_selection()
            
            # Wait for page stabilization with timeout
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            
            # Optimize page for memory efficiency
            await self._optimize_page_for_memory()
            
        except Exception as e:
            self.logger.debug(f"Page setup completed with issues: {e}")

    async def _handle_alibaba_cookie_consent(self) -> None:
        """Handle Alibaba cookie consent dialog"""
        cookie_selectors = [
            'button[data-testid="cookie-accept"]',
            '.cookie-consent-accept',
            '#cookie-accept',
            'button:has-text("قبول")',
            'button:has-text("موافقم")',
            'button:has-text("Accept")'
        ]
        
        for selector in cookie_selectors:
            try:
                await self.page.click(selector, timeout=2000)
                self.logger.debug("Cookie consent handled for Alibaba")
                return
            except:
                continue

    async def _handle_alibaba_language_selection(self) -> None:
        """Handle Alibaba language selection if needed"""
        try:
            # Check if we need to switch to Persian
            current_lang = await self.page.evaluate("document.documentElement.lang")
            if current_lang and 'fa' not in current_lang.lower():
                # Try to find language selector
                lang_selectors = [
                    'button[data-lang="fa"]',
                    '.language-selector[data-value="fa"]',
                    'a[href*="lang=fa"]'
                ]
                
                for selector in lang_selectors:
                    try:
                        await self.page.click(selector, timeout=1000)
                        await self.page.wait_for_load_state("networkidle", timeout=5000)
                        break
                    except:
                        continue
        except Exception:
            pass  # Language selection is optional

    async def _optimize_page_for_memory(self) -> None:
        """Optimize page for memory efficiency"""
        try:
            # Remove unnecessary elements to save memory
            await self.page.evaluate("""
                // Remove ads and heavy content
                const adsSelectors = ['.ad', '.advertisement', '.banner', '[class*="ad-"]'];
                adsSelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
                
                // Remove images not essential for data extraction
                const nonEssentialImages = document.querySelectorAll('img:not([class*="flight"]):not([class*="airline"])');
                nonEssentialImages.forEach(img => {
                    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                });
                
                // Disable animations to save CPU/memory
                const style = document.createElement('style');
                style.textContent = `
                    *, *::before, *::after {
                        animation-duration: 0s !important;
                        transition-duration: 0s !important;
                    }
                `;
                document.head.appendChild(style);
            """)
        except Exception as e:
            self.logger.debug(f"Page optimization completed with issues: {e}")

    @profile_crawler_operation("alibaba_fill_form")
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fill Alibaba search form with optimized selectors"""
        try:
            # Pre-cache selectors for efficiency
            origin_selector = self._search_form_config.get("origin_field")
            destination_selector = self._search_form_config.get("destination_field")
            departure_selector = self._search_form_config.get("departure_date_field")
            return_selector = self._search_form_config.get("return_date_field")
            cabin_selector = self._search_form_config.get("cabin_class_field")
            
            # Fill form fields efficiently
            if origin_selector:
                await self._fill_field_with_retry(origin_selector, search_params.get("origin", ""))
            
            if destination_selector:
                await self._fill_field_with_retry(destination_selector, search_params.get("destination", ""))
            
            if departure_selector:
                await self._fill_field_with_retry(departure_selector, search_params.get("departure_date", ""))
            
            if search_params.get("return_date") and return_selector:
                await self._fill_field_with_retry(return_selector, search_params["return_date"])
            
            if search_params.get("cabin_class") and cabin_selector:
                await self._select_option_with_retry(cabin_selector, search_params["cabin_class"])
            
            # Set passenger count if needed
            if search_params.get("passengers"):
                await self._set_passenger_count(search_params["passengers"])
            
            # Submit form with optimized waiting
            await self._submit_search_form()
            
        except Exception as e:
            self.logger.error(f"Error filling Alibaba search form: {e}")
            raise

    async def _fill_field_with_retry(self, selector: str, value: str, max_retries: int = 3) -> None:
        """Fill form field with retry logic"""
        for attempt in range(max_retries):
            try:
                await self.page.fill(selector, value)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.5)

    async def _select_option_with_retry(self, selector: str, value: str, max_retries: int = 3) -> None:
        """Select option with retry logic"""
        for attempt in range(max_retries):
            try:
                await self.page.select_option(selector, value)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.5)

    async def _set_passenger_count(self, count: int) -> None:
        """Set passenger count efficiently"""
        try:
            passenger_selectors = [
                'input[name="passengers"]',
                'select[name="adult_count"]',
                '.passenger-count input',
                '[data-testid="passenger-input"]'
            ]
            
            for selector in passenger_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                        
                        if tag_name == 'select':
                            await element.select_option(str(count))
                        else:
                            await element.fill(str(count))
                        return
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Could not set passenger count: {e}")

    async def _submit_search_form(self) -> None:
        """Submit search form with optimized waiting"""
        submit_selectors = [
            'button[type="submit"]',
            'button[data-testid="search-submit"]',
            '.search-button',
            'input[type="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                await self.page.click(selector)
                break
            except:
                continue
        
        # Wait for results with optimized strategy
        await self._wait_for_search_results()

    async def _wait_for_search_results(self) -> None:
        """Wait for search results with memory-efficient strategy"""
        try:
            # Wait for results container
            results_selector = self._results_config.get("container")
            if results_selector:
                await self.page.wait_for_selector(results_selector, timeout=30000)
            
            # Wait for network idle
            await self.page.wait_for_load_state("networkidle", timeout=15000)
            
            # Additional wait for dynamic content
            await asyncio.sleep(2)
            
        except TimeoutError:
            self.logger.warning("Timeout waiting for Alibaba results - proceeding anyway")

    @profile_crawler_operation("alibaba_parse_flight")
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Alibaba flight element with memory optimization.
        
        Uses efficient text extraction and minimal DOM queries.
        """
        try:
            flight_data = {}
            
            # Pre-cache config for efficiency
            config = self._results_config
            
            # Extract basic flight information
            airline = self._extract_text_optimized(element, config.get("airline_selector"))
            if airline:
                flight_data["airline"] = airline
            
            # Extract price efficiently
            price_text = self._extract_text_optimized(element, config.get("price_selector"))
            if price_text:
                price = self._extract_price(price_text)
                if price > 0:
                    flight_data["price"] = price
                    flight_data["price_text"] = price_text
            
            # Extract departure time
            departure_time = self._extract_text_optimized(element, config.get("departure_time_selector"))
            if departure_time:
                flight_data["departure_time"] = departure_time
            
            # Extract arrival time
            arrival_time = self._extract_text_optimized(element, config.get("arrival_time_selector"))
            if arrival_time:
                flight_data["arrival_time"] = arrival_time
            
            # Extract duration
            duration_text = self._extract_text_optimized(element, config.get("duration_selector"))
            if duration_text:
                duration_minutes = self._extract_duration_minutes(duration_text)
                if duration_minutes > 0:
                    flight_data["duration_minutes"] = duration_minutes
                    flight_data["duration_text"] = duration_text
            
            # Extract flight number
            flight_number = self._extract_text_optimized(element, config.get("flight_number_selector"))
            if flight_number:
                flight_data["flight_number"] = flight_number
            
            # Alibaba-specific fields
            self._extract_alibaba_specific_fields(element, flight_data, config)
            
            # Add metadata
            flight_data.update({
                "source": "alibaba",
                "is_aggregator": True,
                "aggregator_name": "alibaba"
            })
            
            # Validate required fields before returning
            if self._validate_flight_data_minimal(flight_data):
                return flight_data
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Error parsing Alibaba flight element: {e}")
            return None

    def _extract_text_optimized(self, element, selector: str) -> str:
        """
        Optimized text extraction with minimal DOM traversal.
        """
        if not selector or not element:
            return ""
        
        try:
            # Use more efficient selection
            found_elements = element.select(selector)
            if found_elements:
                # Get first match and extract text efficiently
                text = found_elements[0].get_text(strip=True)
                return text[:200]  # Limit text length to save memory
            
            return ""
            
        except Exception:
            return ""

    def _extract_alibaba_specific_fields(self, element, flight_data: Dict[str, Any], config: Dict[str, Any]) -> None:
        """Extract Alibaba-specific fields efficiently"""
        try:
            # Source airline (for aggregator)
            source_airline = self._extract_text_optimized(element, config.get("source_airline_selector"))
            if source_airline:
                flight_data["source_airline"] = source_airline
            
            # Discount information
            discount_info = self._extract_text_optimized(element, config.get("discount_selector"))
            if discount_info:
                flight_data["discount_info"] = discount_info
            
            # Booking reference
            booking_ref = self._extract_text_optimized(element, config.get("booking_reference_selector"))
            if booking_ref:
                flight_data["booking_reference"] = booking_ref
            
            # Cabin class
            cabin_class = self._extract_text_optimized(element, config.get("cabin_class_selector"))
            if cabin_class:
                flight_data["cabin_class"] = cabin_class
            
        except Exception as e:
            self.logger.debug(f"Error extracting Alibaba-specific fields: {e}")

    def _validate_flight_data_minimal(self, flight_data: Dict[str, Any]) -> bool:
        """Minimal validation for flight data"""
        required_fields = ["airline", "price"]
        return all(field in flight_data and flight_data[field] for field in required_fields)

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Alibaba search"""
        return ["origin", "destination", "departure_date"]

    @cached(cache_name="alibaba", ttl_seconds=1800)  # 30 minutes cache
    def get_adapter_info(self) -> Dict[str, Any]:
        """Get adapter information with caching"""
        base_info = super().get_adapter_info()
        base_info.update({
            "adapter_type": "aggregator",
            "supported_routes": "international_and_domestic",
            "features": [
                "memory_optimized",
                "lazy_loading",
                "performance_profiling",
                "resource_monitoring"
            ],
            "version": "2.0_optimized"
        })
        return base_info

    def __del__(self):
        """Cleanup when adapter is destroyed"""
        try:
            # Force garbage collection
            gc.collect()
        except:
            pass


# Factory function for easy instantiation
def create_alibaba_adapter(config: Optional[Dict] = None) -> AlibabaAdapter:
    """Create optimized Alibaba adapter instance"""
    return AlibabaAdapter(config)


# Example usage with async context manager
async def example_usage():
    """Example of using the optimized Alibaba adapter"""
    async with AlibabaAdapter() as adapter:
        search_params = {
            "origin": "THR",
            "destination": "IST",
            "departure_date": "2024-06-15",
            "passengers": 1,
            "cabin_class": "economy"
        }
        
        try:
            results = await adapter.crawl(search_params)
            print(f"Found {len(results)} flights")
            
            # Get resource usage
            resource_usage = adapter.get_resource_usage()
            print(f"Memory usage: {resource_usage['memory_usage_mb']:.1f}MB")
            
        except Exception as e:
            print(f"Crawling failed: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
