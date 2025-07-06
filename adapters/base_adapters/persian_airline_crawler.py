"""
Base Persian airline crawler class for Iranian airlines.
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Any
import logging
from playwright.async_api import Page

from .enhanced_base_crawler import EnhancedBaseCrawler
from persian_text import PersianTextProcessor
from adapters.strategies.parsing_strategies import (
    ParsingStrategyFactory,
    FlightParsingStrategy
)


class PersianAirlineCrawler(EnhancedBaseCrawler):
    """
    Base class for Persian airline crawlers.

    Provides common functionality for crawling Iranian airline websites
    that require Persian text processing.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.persian_processor = PersianTextProcessor()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method for Persian airline websites.

        Args:
            search_params: Search parameters for flight search

        Returns:
            List of flight data dictionaries
        """
        return await self._safe_crawl(search_params)

    async def _fill_search_form(
        self, page: Page, search_params: Dict[str, Any]
    ) -> None:
        """
        Fill the search form with parameters for Persian airlines.

        Args:
            page: Playwright page object
            search_params: Search parameters
        """
        try:
            form_config = self.config["extraction_config"]["search_form"]

            # Fill origin with Persian text processing
            if "origin_field" in form_config:
                processed_origin = self.persian_processor.process_text(
                    search_params["origin"]
                )
                await page.fill(form_config["origin_field"], processed_origin)

            # Fill destination with Persian text processing
            if "destination_field" in form_config:
                processed_destination = self.persian_processor.process_text(
                    search_params["destination"]
                )
                await page.fill(form_config["destination_field"], processed_destination)

            # Fill date with Persian date processing
            if "date_field" in form_config:
                processed_date = self.persian_processor.process_date(
                    search_params["departure_date"]
                )
                await page.fill(form_config["date_field"], processed_date)

            # Handle passengers
            if "passengers" in search_params and "passengers_field" in form_config:
                await page.select_option(
                    form_config["passengers_field"], str(search_params["passengers"])
                )

            # Handle seat class with Persian text processing
            if "seat_class" in search_params and "class_field" in form_config:
                processed_class = self.persian_processor.process_text(
                    search_params["seat_class"]
                )
                await page.select_option(form_config["class_field"], processed_class)

            # Handle trip type with Persian text processing
            if "trip_type" in search_params and "trip_type_field" in form_config:
                processed_trip_type = self.persian_processor.process_text(
                    search_params["trip_type"]
                )
                await page.select_option(
                    form_config["trip_type_field"], processed_trip_type
                )

            # Submit form
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")

        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    def _get_parsing_strategy(self) -> FlightParsingStrategy:
        """
        Get Persian parsing strategy for this adapter.
        
        Override the base class to force Persian strategy.
        """
        try:
            return ParsingStrategyFactory.create_strategy("persian", self.config)
        except Exception as e:
            self.logger.warning(f"Failed to create Persian strategy, using auto-detection: {e}")
            return super()._get_parsing_strategy()

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Parse Persian flight element.
        
        This method is deprecated in favor of centralized parsing strategies.
        Use _parse_flight_data() which uses PersianParsingStrategy from parsing_strategies.py.
        """
        import warnings
        warnings.warn(
            "Persian adapter _parse_flight_element is deprecated. Use centralized PersianParsingStrategy.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Call parent's deprecated method for backward compatibility
        return super()._parse_flight_element(element)

    async def _post_process_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Persian-specific post-processing to flight data.
        
        This adds Persian airline specific metadata and validation.
        """
        # Apply base post-processing first
        flight_data = await super()._post_process_flight_data(flight_data)
        
        # Add Persian-specific metadata
        flight_data.update({
            'adapter_type': 'persian',
            'currency': flight_data.get('currency', 'IRR'),
            'country': 'iran',
            'language': 'persian'
        })
        
        # Persian-specific validation and normalization
        if 'airline' in flight_data and flight_data['airline']:
            # Normalize Persian airline names
            airline_mappings = {
                "ایران ایر": "Iran Air",
                "ماهان": "Mahan Air", 
                "آسمان": "Aseman Airlines",
                "کاسپین": "Caspian Airlines",
                "قشم ایر": "Qeshm Air",
                "کارون": "Karun Airlines",
                "سپهران": "Sepehran Airlines",
                "وارش": "Varesh Airlines",
                "تابان": "Taban Air",
                "عطا": "Ata Airlines"
            }
            
            airline_name = flight_data['airline']
            flight_data['airline_english'] = airline_mappings.get(airline_name, airline_name)
        
        # Ensure price is in IRR and reasonable range
        if 'price' in flight_data and flight_data['price']:
            try:
                price = float(flight_data['price'])
                if price < 1000000:  # Likely missing some zeros for IRR
                    flight_data['price_warning'] = 'Price seems low for IRR, please verify'
                elif price > 100000000:  # Very expensive for domestic Iranian flight
                    flight_data['price_warning'] = 'Price seems high, please verify'
            except (ValueError, TypeError):
                pass
        
        return flight_data

    # Implementation of new abstract methods from EnhancedBaseCrawler
    def _get_base_url(self) -> str:
        """Get the base URL for this adapter."""
        return self.base_url

    def _get_required_fields(self) -> List[str]:
        """Get required fields for this adapter."""
        return ["origin", "destination", "departure_date"]
    
    async def _validate_specific_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate adapter-specific parameters."""
        # Persian airline specific validation
        if "seat_class" in search_params:
            valid_classes = ["اکونومی", "بیزینس", "فرست کلاس", "economy", "business", "first"]
            if search_params["seat_class"] not in valid_classes:
                raise ValueError(f"Invalid seat class. Must be one of: {valid_classes}")
        
        # Validate Persian text fields
        persian_fields = ["origin", "destination"]
        for field in persian_fields:
            if field in search_params:
                # Ensure text is properly encoded for Persian
                text = search_params[field]
                if isinstance(text, str) and not self.persian_processor.is_persian_text(text):
                    self.logger.warning(f"Field {field} may not contain proper Persian text")
    
    async def _handle_popups(self) -> None:
        """Handle popups specific to this adapter."""
        # Handle common Persian airline popups
        try:
            popup_selectors = [
                ".popup-close",
                ".modal-close", 
                ".overlay-close",
                '[data-testid="close-popup"]',
                '.fa-times',  # Persian sites often use FontAwesome
                '.close-btn'
            ]
            for selector in popup_selectors:
                try:
                    await self.page.click(selector, timeout=1000)
                    break
                except:
                    continue
        except Exception:
            pass  # Popups are optional
    
    async def _handle_localization(self) -> None:
        """Handle localization specific to this adapter."""
        # Set to Persian/Farsi for Persian airlines
        try:
            language_selectors = [
                'select[name="language"]',
                '.language-selector',
                '[data-lang="fa"]',
                '[data-lang="persian"]',
                '.fa-lang'
            ]
            for selector in language_selectors:
                try:
                    await self.page.click(selector, timeout=1000)
                    break
                except:
                    continue
        except Exception:
            pass  # Language selection is optional
    
    async def _submit_search(self) -> None:
        """Submit search form."""
        try:
            submit_selectors = [
                'button[type="submit"]',
                '.search-button',
                '#search-submit', 
                '.btn-search',
                '.search-btn',
                'input[type="submit"]',
                '[data-action="search"]'
            ]
            for selector in submit_selectors:
                try:
                    await self.page.click(selector)
                    break
                except:
                    continue
        except Exception as e:
            raise ValueError(f"Failed to submit search form: {e}")
    
    async def _parse_flight_data(self, content: str) -> List[Dict[str, Any]]:
        """Parse flight data from content."""
        # This will be called by the extraction process
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        
        parsing_config = self.config["extraction_config"]["results_parsing"]
        container_selector = parsing_config.get("container")
        
        flight_elements = soup.select(container_selector)
        results = []
        
        for element in flight_elements:
            flight_data = self._parse_flight_element(element)
            if flight_data:
                results.append(flight_data)
        
        return results
    
    async def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate individual result."""
        required_fields = ["airline", "price", "departure_time", "arrival_time"]
        return all(field in result and result[field] for field in required_fields)
    
    async def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize result to standard format."""
        # Ensure consistent field names and formats with Persian text processing
        normalized = result.copy()
        
        # Normalize price using Persian text processor
        if "price" in normalized:
            price_text = str(normalized["price"])
            if hasattr(self.persian_processor, 'process_price'):
                normalized["price"] = self.persian_processor.process_price(price_text)
            else:
                # Fallback to basic price extraction
                normalized["price"] = self._extract_price(price_text)
        
        # Process Persian text fields
        text_fields = ["airline", "departure_time", "arrival_time", "duration", "seat_class"]
        for field in text_fields:
            if field in normalized and normalized[field]:
                normalized[field] = self.persian_processor.process_text(str(normalized[field]))
        
        # Add metadata
        normalized.update({
            "source": "persian_airline",
            "adapter_type": "PersianAirlineCrawler",
            "language": "persian",
            "extracted_at": self.config.get("extracted_at"),
        })
        
        return normalized
    
    async def _initialize_adapter_specific(self) -> None:
        """Initialize adapter-specific components."""
        # Initialize Persian airline specific components
        self.logger.info("Initializing Persian airline adapter components")
        
        # Ensure Persian text processor is properly initialized
        if not hasattr(self, 'persian_processor') or not self.persian_processor:
            self.persian_processor = PersianTextProcessor()
        
        # Add any Persian-specific initialization here
