"""
Base airline crawler class for international airlines.
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Any
import logging
from playwright.async_api import Page

from .enhanced_base_crawler import EnhancedBaseCrawler


class AirlineCrawler(EnhancedBaseCrawler):
    """
    Base class for international airline crawlers.

    Provides common functionality for crawling international airline websites
    that don't require Persian text processing.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main crawling method for airline websites.

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
        Fill the search form with parameters for international airlines.

        Args:
            page: Playwright page object
            search_params: Search parameters
        """
        try:
            form_config = self.config["extraction_config"]["search_form"]

            # Handle trip type if specified
            if "trip_type" in search_params and "trip_type_field" in form_config:
                await page.select_option(
                    form_config["trip_type_field"], search_params["trip_type"]
                )

            # Fill origin
            if "origin_field" in form_config:
                await page.fill(form_config["origin_field"], search_params["origin"])

            # Fill destination
            if "destination_field" in form_config:
                await page.fill(
                    form_config["destination_field"], search_params["destination"]
                )

            # Fill departure date
            if "departure_date_field" in form_config:
                await page.fill(
                    form_config["departure_date_field"], search_params["departure_date"]
                )

            # Fill return date if specified
            if "return_date" in search_params and "return_date_field" in form_config:
                await page.fill(
                    form_config["return_date_field"], search_params["return_date"]
                )

            # Handle passengers
            if "passengers" in search_params and "passengers_field" in form_config:
                await page.select_option(
                    form_config["passengers_field"], str(search_params["passengers"])
                )

            # Handle cabin class
            if "cabin_class" in search_params and "cabin_class_field" in form_config:
                await page.select_option(
                    form_config["cabin_class_field"], search_params["cabin_class"]
                )

            # Submit form
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")

        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for international airlines.

        Args:
            element: BeautifulSoup element containing flight data

        Returns:
            Dictionary containing parsed flight data or None if parsing fails
        """
        try:
            parsing_config = self.config["extraction_config"]["results_parsing"]

            flight_data = {
                "airline": self._extract_text(element, parsing_config.get("airline")),
                "flight_number": self._extract_text(
                    element, parsing_config.get("flight_number")
                ),
                "departure_time": self._extract_text(
                    element, parsing_config.get("departure_time")
                ),
                "arrival_time": self._extract_text(
                    element, parsing_config.get("arrival_time")
                ),
                "duration": self._extract_text(element, parsing_config.get("duration")),
                "price": self._extract_price(
                    self._extract_text(element, parsing_config.get("price"))
                ),
                "cabin_class": self._extract_text(
                    element, parsing_config.get("cabin_class")
                ),
            }

            # Extract additional fields if available
            additional_fields = [
                "fare_conditions",
                "available_seats",
                "aircraft_type",
                "baggage_allowance",
                "meal_service",
                "special_services",
                "refund_policy",
                "change_policy",
                "fare_rules",
                "booking_class",
                "fare_basis",
                "ticket_validity",
                "miles_earned",
                "miles_required",
                "promotion_code",
                "special_offers",
            ]

            for field in additional_fields:
                if field in parsing_config:
                    value = self._extract_text(element, parsing_config[field])
                    if value:
                        flight_data[field] = value

            return flight_data

        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None

    def _extract_text(self, element, selector: str) -> str:
        """
        Extract text from element using selector.

        Args:
            element: BeautifulSoup element
            selector: CSS selector

        Returns:
            Extracted text or empty string
        """
        try:
            if not selector:
                return ""
            found_element = element.select_one(selector)
            return found_element.text.strip() if found_element else ""
        except Exception:
            return ""

    # Implementation of new abstract methods from EnhancedBaseCrawler
    def _get_base_url(self) -> str:
        """Get the base URL for this adapter."""
        return self.base_url

    def _get_required_fields(self) -> List[str]:
        """Get required fields for this adapter."""
        return ["origin", "destination", "departure_date"]
    
    async def _validate_specific_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate adapter-specific parameters."""
        # International airline specific validation
        if "cabin_class" in search_params:
            valid_classes = ["economy", "business", "first"]
            if search_params["cabin_class"].lower() not in valid_classes:
                raise ValueError(f"Invalid cabin class. Must be one of: {valid_classes}")
    
    async def _handle_popups(self) -> None:
        """Handle popups specific to this adapter."""
        # Handle common international airline popups
        try:
            popup_selectors = [
                ".popup-close",
                ".modal-close",
                ".overlay-close",
                '[data-testid="close-popup"]'
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
        # Set to English for international airlines
        try:
            language_selectors = [
                'select[name="language"]',
                '.language-selector',
                '[data-lang="en"]'
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
                '.btn-search'
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
        # Ensure consistent field names and formats
        normalized = result.copy()
        
        # Normalize price to float
        if "price" in normalized:
            normalized["price"] = self._extract_price(str(normalized["price"]))
        
        # Add metadata
        normalized.update({
            "source": "international_airline",
            "adapter_type": "AirlineCrawler",
            "extracted_at": self.config.get("extracted_at"),
        })
        
        return normalized
    
    async def _initialize_adapter_specific(self) -> None:
        """Initialize adapter-specific components."""
        # Initialize international airline specific components
        self.logger.info("Initializing international airline adapter components")
        # Add any airline-specific initialization here
