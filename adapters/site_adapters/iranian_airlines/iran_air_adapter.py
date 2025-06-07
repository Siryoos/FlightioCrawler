from typing import Dict, List, Optional
from datetime import datetime
import re
import json
import logging
from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError

from adapters.base_adapters.persian_airline_crawler import PersianAirlineCrawler
from utils.persian_text_processor import PersianTextProcessor
from utils.rate_limiter import RateLimiter
from utils.error_handler import ErrorHandler
from utils.monitoring import Monitoring

class IranAirAdapter(PersianAirlineCrawler):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.iranair.com"
        self.search_url = config["search_url"]
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
            await self.page.navigate(self.search_url)
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

    def _parse_flight_element(self, element) -> Optional[Dict]:
        """Parse individual flight element into structured data"""
        try:
            # Extract basic flight information
            flight_data = {
                "airline": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["airline"]
                    ).text
                ),
                "flight_number": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["flight_number"]
                    ).text
                ),
                "departure_time": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["departure_time"]
                    ).text
                ),
                "arrival_time": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["arrival_time"]
                    ).text
                ),
                "duration": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["duration"]
                    ).text
                ),
                "price": self.persian_processor.process_price(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["price"]
                    ).text
                ),
                "seat_class": self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["seat_class"]
                    ).text
                )
            }
            
            # Extract additional flight details
            if element.select_one(self.config["extraction_config"]["results_parsing"]["fare_conditions"]):
                flight_data["fare_conditions"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["fare_conditions"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["available_seats"]):
                flight_data["available_seats"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["available_seats"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["aircraft_type"]):
                flight_data["aircraft_type"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["aircraft_type"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["baggage_allowance"]):
                flight_data["baggage_allowance"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["baggage_allowance"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["meal_service"]):
                flight_data["meal_service"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["meal_service"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["special_services"]):
                flight_data["special_services"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["special_services"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["refund_policy"]):
                flight_data["refund_policy"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["refund_policy"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["change_policy"]):
                flight_data["change_policy"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["change_policy"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["fare_rules"]):
                flight_data["fare_rules"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["fare_rules"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["booking_class"]):
                flight_data["booking_class"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["booking_class"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["fare_basis"]):
                flight_data["fare_basis"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["fare_basis"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["ticket_validity"]):
                flight_data["ticket_validity"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["ticket_validity"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["miles_earned"]):
                flight_data["miles_earned"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["miles_earned"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["miles_required"]):
                flight_data["miles_required"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["miles_required"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["promotion_code"]):
                flight_data["promotion_code"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["promotion_code"]
                    ).text
                )
            
            if element.select_one(self.config["extraction_config"]["results_parsing"]["special_offers"]):
                flight_data["special_offers"] = self.persian_processor.process_text(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["special_offers"]
                    ).text
                )
            
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None

    def _validate_search_params(self, search_params: Dict):
        """Validate search parameters"""
        required_fields = ["origin", "destination", "departure_date", "passengers", "seat_class"]
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