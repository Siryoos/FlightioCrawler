"""
Refactored Iran Air adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import re
import json
import logging
from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError

from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from utils.persian_text_processor import PersianTextProcessor
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring

class IranAirAdapter(EnhancedPersianAdapter):
    """
    Iran Air adapter with minimal code duplication.
    
    Uses EnhancedPersianAdapter for all common functionality.
    Only implements airline-specific logic.
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.persian_processor = PersianTextProcessor()
        self.rate_limiter = RateLimiter(
            requests_per_second=config["rate_limiting"]["requests_per_second"],
            burst_limit=config["rate_limiting"]["burst_limit"],
            cooldown_period=config["rate_limiting"]["cooldown_period"]
        )
        self.error_handler = ErrorHandler(
            max_retries=config["error_handling"]["max_retries"],
            retry_delay=config["error_handling"]["retry_delay"],
            circuit_breaker_config=config["error_handling"]["circuit_breaker"]
        )
        self.monitoring = Monitoring(config["monitoring"])
        self.logger = logging.getLogger(__name__)

    async def crawl(self, search_params: Dict) -> List[Dict]:
        """
        Main crawling method for IranAir flights
        """
        try:
            # Validate search parameters
            self._validate_search_params(search_params)
            
            # Navigate to search page
            await self._navigate_to_search_page()
            
            # Fill search form
            await self._fill_search_form(search_params)
            
            # Extract flight results
            results = await self._extract_flight_results()
            
            # Validate results
            validated_results = self._validate_flight_data(results)
            
            # Record success metrics
            self.monitoring.record_success()
            
            return validated_results
            
        except Exception as e:
            self.logger.error(f"Error crawling IranAir: {str(e)}")
            self.monitoring.record_error()
            raise

    async def _navigate_to_search_page(self):
        """Navigate to the flight search page"""
        try:
            await self.page.navigate(self._get_base_url())
            await self.page.wait_for_load_state("networkidle")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise

    async def _fill_search_form(self, search_params: Dict):
        """Fill out the search form with Persian text handling"""
        try:
            # Origin
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["origin_field"],
                self.persian_processor.process_text(search_params["origin"])
            )
            
            # Destination
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["destination_field"],
                self.persian_processor.process_text(search_params["destination"])
            )
            
            # Date
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["date_field"],
                self.persian_processor.process_date(search_params["departure_date"])
            )
            
            # Passengers
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["passengers_field"],
                str(search_params["passengers"])
            )
            
            # Class
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["class_field"],
                self.persian_processor.process_text(search_params["seat_class"])
            )
            
            # Trip type
            if "trip_type" in search_params:
                await self.page.select_option(
                    self.config["extraction_config"]["search_form"]["trip_type_field"],
                    self.persian_processor.process_text(search_params["trip_type"])
                )
            
            # Submit form
            await self.page.click("button[type='submit']")
            await self.page.wait_for_load_state("networkidle")
            
        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    async def _extract_flight_results(self) -> List[Dict]:
        """Extract flight results from the page"""
        try:
            # Wait for results to load
            await self.page.wait_for_selector(
                self.config["extraction_config"]["results_parsing"]["container"]
            )
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            # Find all flight results
            flight_elements = soup.select(
                self.config["extraction_config"]["results_parsing"]["container"]
            )
            
            results = []
            for element in flight_elements:
                flight_data = self._parse_flight_element(element)
                if flight_data:
                    results.append(flight_data)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error extracting flight results: {str(e)}")
            raise

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Iran Air specific flight element structure.
        
        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)
        
        if flight_data:
            # Add Iran Air specific fields
            config = self.config["extraction_config"]["results_parsing"]
            
            # Iran Air specific: route information
            route_info = self._extract_text(element, config.get("route_info"))
            if route_info:
                flight_data["route_info"] = self.persian_processor.process_text(route_info)
            
            # Iran Air specific: service class details
            service_details = self._extract_text(element, config.get("service_details"))
            if service_details:
                flight_data["service_details"] = self.persian_processor.process_text(service_details)
            
            # Iran Air specific: booking conditions
            booking_conditions = self._extract_text(element, config.get("booking_conditions"))
            if booking_conditions:
                flight_data["booking_conditions"] = self.persian_processor.process_text(booking_conditions)
        
        return flight_data

    def _get_base_url(self) -> str:
        """Get Iran Air base URL."""
        return "https://www.iranair.com"
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - always IRR for Iran Air."""
        return "IRR"

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Iran Air search."""
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]

    def _validate_search_params(self, search_params: Dict):
        """Validate search parameters"""
        required_fields = self._get_required_search_fields()
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

    def _validate_flight_data(self, results: List[Dict]) -> List[Dict]:
        """Validate flight data against specified rules"""
        validated_results = []
        for result in results:
            # Check required fields
            if all(field in result for field in self.config["data_validation"]["required_fields"]):
                # Validate price range
                if (self.config["data_validation"]["price_range"]["min"] <= result["price"] <= 
                    self.config["data_validation"]["price_range"]["max"]):
                    # Validate duration range
                    if (self.config["data_validation"]["duration_range"]["min"] <= result["duration_minutes"] <= 
                        self.config["data_validation"]["duration_range"]["max"]):
                        validated_results.append(result)
        return validated_results 