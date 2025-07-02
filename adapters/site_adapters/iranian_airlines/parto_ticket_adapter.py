import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from adapters.site_adapters.base_crawler import BaseSiteCrawler
from adapters.site_adapters.iranian_airlines.parto_crs_adapter import PartoCRSAdapter
from data.transformers.persian_text_processor import PersianTextProcessor
from utils.logger import get_logger
from utils.persian_text_processor import PersianTextProcessor
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring

logger = get_logger(__name__)

class PartoTicketAdapter(PersianAirlineCrawler):
    """Adapter for crawling parto-ticket.ir with Parto CRS integration"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.parto-ticket.ir"
        self.search_url = f"{self.base_url}/flight-search"
        self.persian_processor = PersianTextProcessor()
        self.rate_limiter = RateLimiter(
            requests_per_second=config.get("rate_limiting", {}).get("requests_per_second", 2),
            burst_limit=config.get("rate_limiting", {}).get("burst_limit", 5)
        )
        self.error_handler = ErrorHandler(
            max_retries=config.get("error_handling", {}).get("max_retries", 3),
            retry_delay=config.get("error_handling", {}).get("retry_delay", 5)
        )
        self.monitoring = Monitoring(config.get("monitoring", {}))
        self.enable_crs_integration = config.get("enable_crs_integration", False)
        self.crs_config = config.get("crs_config", {})
        self.crs_agency_code = config.get("crs_agency_code")
        self.crs_commission_rate = config.get("crs_commission_rate", 0)
        self.crs_adapter = PartoCRSAdapter(config.get('crs_config', {}))
        
    async def crawl(self, search_params: Dict) -> List[Dict]:
        """
        Main crawling method that orchestrates the entire process
        """
        try:
            self.monitoring.start_request()
            
            # Validate search parameters
            self._validate_search_params(search_params)
            
            # Initialize browser session
            async with self._create_browser_session() as session:
                # Navigate to search page
                await self._navigate_to_search_page(session)
                
                # Fill search form
                await self._fill_search_form(session, search_params)
                
                # Extract flight results
                results = await self._extract_flight_results(session)
                
                # Integrate with CRS if enabled
                if self.enable_crs_integration:
                    results = await self._integrate_with_crs(results, search_params)
                
                # Validate results
                validated_results = self._validate_results(results)
                
                self.monitoring.end_request(success=True)
                return validated_results
                
        except Exception as e:
            self.monitoring.end_request(success=False, error=str(e))
            logging.error(f"Error in Parto Ticket crawler: {str(e)}")
            return []
    
    async def _navigate_to_search_page(self, session) -> None:
        """
        Navigate to the flight search page
        """
        try:
            await self.rate_limiter.acquire()
            await session.navigate(self.search_url)
            await session.wait_for_selector(self.config["extraction_config"]["search_form"]["origin_field"])
        except Exception as e:
            logging.error(f"Error navigating to search page: {str(e)}")
            raise
    
    async def _fill_search_form(self, session, search_params: Dict) -> None:
        """
        Fill out the search form with the provided parameters
        """
        try:
            # Convert dates to Jalali if needed
            if self.config["persian_processing"]["jalali_calendar"]:
                departure_date = self.persian_processor.gregorian_to_jalali(search_params["departure_date"])
            else:
                departure_date = search_params["departure_date"]

            # Fill origin
            await session.fill(
                self.config["extraction_config"]["search_form"]["origin_field"],
                search_params["origin"]
            )

            # Fill destination
            await session.fill(
                self.config["extraction_config"]["search_form"]["destination_field"],
                search_params["destination"]
            )

            # Fill date
            await session.fill(
                self.config["extraction_config"]["search_form"]["date_field"],
                departure_date
            )

            # Fill passengers
            await session.select_option(
                self.config["extraction_config"]["search_form"]["passengers_field"],
                str(search_params["passengers"])
            )

            # Fill seat class
            await session.select_option(
                self.config["extraction_config"]["search_form"]["class_field"],
                search_params["seat_class"]
            )

            # Submit form
            await session.click("button[type='submit']")
            await session.wait_for_selector(self.config["extraction_config"]["results_parsing"]["container"])

        except Exception as e:
            logging.error(f"Error filling search form: {str(e)}")
            raise
    
    async def _extract_flight_results(self, session) -> List[Dict]:
        """
        Extract flight results from the search results page
        """
        try:
            results = []
            flight_elements = await session.query_selector_all(
                self.config["extraction_config"]["results_parsing"]["container"]
            )

            for element in flight_elements:
                flight_html = await element.inner_html()
                flight_data = await self._parse_flight_element(flight_html)
                if flight_data:
                    results.append(flight_data)

            return results

        except Exception as e:
            logging.error(f"Error extracting flight results: {str(e)}")
            raise
    
    async def _parse_flight_element(self, flight_html: str) -> Optional[Dict]:
        """
        Parse individual flight element HTML into structured data
        """
        try:
            # Extract basic flight information
            airline = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["airline"])
            flight_number = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["flight_number"])
            departure_time = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["departure_time"])
            arrival_time = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["arrival_time"])
            duration = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["duration"])
            price_text = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["price"])
            seat_class = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["seat_class"])

            # Extract additional information
            fare_conditions = await self._extract_fare_conditions(flight_html)
            available_seats = await self._extract_available_seats(flight_html)
            aircraft_type = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["aircraft_type"])
            ticket_type = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["ticket_type"])

            # Process price
            price, currency = self.persian_processor.extract_price_and_currency(price_text)

            # Process duration
            duration_minutes = self.persian_processor.parse_duration(duration)

            # Create flight data dictionary
            flight_data = {
                "airline": airline,
                "flight_number": flight_number,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "duration_minutes": duration_minutes,
                "price": price,
                "currency": currency,
                "seat_class": seat_class,
                "fare_conditions": fare_conditions,
                "available_seats": available_seats,
                "aircraft_type": aircraft_type,
                "ticket_type": ticket_type,
                "raw_data": flight_html
            }

            return flight_data

        except Exception as e:
            logging.error(f"Error parsing flight element: {str(e)}")
            return None
    
    async def _extract_fare_conditions(self, flight_html: str) -> Dict:
        """
        Extract fare conditions from flight HTML
        """
        try:
            fare_conditions = {}
            conditions_container = await self._extract_element(flight_html, self.config["extraction_config"]["results_parsing"]["fare_conditions"])
            
            if conditions_container:
                fare_conditions["cancellation"] = await self._extract_text(conditions_container, ".cancellation")
                fare_conditions["change"] = await self._extract_text(conditions_container, ".change")
                fare_conditions["refund"] = await self._extract_text(conditions_container, ".refund")

            return fare_conditions

        except Exception as e:
            logging.error(f"Error extracting fare conditions: {str(e)}")
            return {}
    
    async def _extract_available_seats(self, flight_html: str) -> int:
        """
        Extract number of available seats from flight HTML
        """
        try:
            seats_text = await self._extract_text(flight_html, self.config["extraction_config"]["results_parsing"]["available_seats"])
            if seats_text:
                return self.persian_processor.extract_number(seats_text)
            return 0

        except Exception as e:
            logging.error(f"Error extracting available seats: {str(e)}")
            return 0
    
    async def _integrate_with_crs(self, results: List[Dict], search_params: Dict) -> List[Dict]:
        """
        Integrate flight results with CRS data
        """
        try:
            if not self.enable_crs_integration or not self.crs_config:
                return results

            # Get CRS data for each flight
            for flight in results:
                crs_data = await self._get_crs_data(flight, search_params)
                if crs_data:
                    flight.update(crs_data)

            return results

        except Exception as e:
            logging.error(f"Error integrating with CRS: {str(e)}")
            return results
    
    async def _get_crs_data(self, flight: Dict, search_params: Dict) -> Optional[Dict]:
        """
        Get additional data from CRS for a specific flight
        """
        try:
            # Here you would implement the actual CRS integration
            # This is a placeholder implementation
            return {
                "commission": self.crs_commission_rate,
                "fare_rules": "Standard fare rules",
                "booking_class": "Y",
                "fare_basis": "YEE",
                "ticket_validity": "1 year"
            }

        except Exception as e:
            logging.error(f"Error getting CRS data: {str(e)}")
            return None
    
    def _validate_search_params(self, search_params: Dict) -> None:
        """
        Validate search parameters
        """
        required_fields = ["origin", "destination", "departure_date", "passengers", "seat_class"]
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")
    
    def _validate_results(self, results: List[Dict]) -> List[Dict]:
        """
        Validate flight results against configuration rules
        """
        validated_results = []
        for flight in results:
            if self._is_valid_flight(flight):
                validated_results.append(flight)
        return validated_results
    
    def _is_valid_flight(self, flight: Dict) -> bool:
        """
        Check if a flight result is valid according to configuration rules
        """
        try:
            # Check required fields
            for field in self.config["data_validation"]["required_fields"]:
                if field not in flight:
                    return False

            # Check price range
            price_range = self.config["data_validation"]["price_range"]
            if not (price_range["min"] <= flight["price"] <= price_range["max"]):
                return False

            # Check duration range
            duration_range = self.config["data_validation"]["duration_range"]
            if not (duration_range["min"] <= flight["duration_minutes"] <= duration_range["max"]):
                return False

            return True

        except Exception as e:
            logging.error(f"Error validating flight: {str(e)}")
            return False 