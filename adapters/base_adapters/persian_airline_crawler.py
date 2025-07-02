"""
Base Persian airline crawler class for Iranian airlines.
"""

from abc import abstractmethod
from typing import Dict, List, Optional, Any
import logging
from playwright.async_api import Page

from .base_crawler import BaseCrawler
from utils.persian_text_processor import PersianTextProcessor


class PersianAirlineCrawler(BaseCrawler):
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
    
    async def _fill_search_form(self, page: Page, search_params: Dict[str, Any]) -> None:
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
                processed_origin = self.persian_processor.process_text(search_params["origin"])
                await page.fill(form_config["origin_field"], processed_origin)
            
            # Fill destination with Persian text processing
            if "destination_field" in form_config:
                processed_destination = self.persian_processor.process_text(search_params["destination"])
                await page.fill(form_config["destination_field"], processed_destination)
            
            # Fill date with Persian date processing
            if "date_field" in form_config:
                processed_date = self.persian_processor.process_date(search_params["departure_date"])
                await page.fill(form_config["date_field"], processed_date)
            
            # Handle passengers
            if "passengers" in search_params and "passengers_field" in form_config:
                await page.select_option(form_config["passengers_field"], str(search_params["passengers"]))
            
            # Handle seat class with Persian text processing
            if "seat_class" in search_params and "class_field" in form_config:
                processed_class = self.persian_processor.process_text(search_params["seat_class"])
                await page.select_option(form_config["class_field"], processed_class)
            
            # Handle trip type with Persian text processing
            if "trip_type" in search_params and "trip_type_field" in form_config:
                processed_trip_type = self.persian_processor.process_text(search_params["trip_type"])
                await page.select_option(form_config["trip_type_field"], processed_trip_type)
            
            # Submit form
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            
        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for Persian airlines with text processing.
        
        Args:
            element: BeautifulSoup element containing flight data
            
        Returns:
            Dictionary containing parsed flight data or None if parsing fails
        """
        try:
            parsing_config = self.config["extraction_config"]["results_parsing"]
            
            flight_data = {
                "airline": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("airline"))
                ),
                "flight_number": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("flight_number"))
                ),
                "departure_time": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("departure_time"))
                ),
                "arrival_time": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("arrival_time"))
                ),
                "duration": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("duration"))
                ),
                "price": self.persian_processor.process_price(
                    self._extract_text(element, parsing_config.get("price"))
                ),
                "seat_class": self.persian_processor.process_text(
                    self._extract_text(element, parsing_config.get("seat_class"))
                )
            }
            
            # Extract additional fields with Persian text processing
            additional_fields = [
                "fare_conditions", "available_seats", "aircraft_type",
                "baggage_allowance", "meal_service", "special_services",
                "refund_policy", "change_policy", "fare_rules",
                "booking_class", "fare_basis", "ticket_validity",
                "miles_earned", "miles_required", "promotion_code",
                "special_offers"
            ]
            
            for field in additional_fields:
                if field in parsing_config:
                    raw_text = self._extract_text(element, parsing_config[field])
                    if raw_text:
                        processed_text = self.persian_processor.process_text(raw_text)
                        flight_data[field] = processed_text
            
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