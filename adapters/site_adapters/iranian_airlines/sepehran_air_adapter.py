from typing import Dict, List, Optional
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.persian_airline_crawler import PersianAirlineCrawler
from utils.persian_text_processor import PersianTextProcessor
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring

class SepehranAirAdapter(PersianAirlineCrawler):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.sepehran.aero"
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
        try:
            self._validate_search_params(search_params)
            await self._navigate_to_search_page()
            await self._fill_search_form(search_params)
            results = await self._extract_flight_results()
            validated_results = self._validate_flight_data(results)
            self.monitoring.record_success()
            return validated_results
        except Exception as e:
            self.logger.error(f"Error crawling Sepehran Air: {str(e)}")
            self.monitoring.record_error()
            raise

    async def _navigate_to_search_page(self):
        try:
            await self.page.navigate(self.search_url)
            await self.page.wait_for_load_state("networkidle")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise

    async def _fill_search_form(self, search_params: Dict):
        try:
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["origin_field"],
                self.persian_processor.process_text(search_params["origin"])
            )
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["destination_field"],
                self.persian_processor.process_text(search_params["destination"])
            )
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["date_field"],
                self.persian_processor.process_date(search_params["departure_date"])
            )
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["passengers_field"],
                str(search_params["passengers"])
            )
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["class_field"],
                self.persian_processor.process_text(search_params["seat_class"])
            )
            if "trip_type" in search_params:
                await self.page.select_option(
                    self.config["extraction_config"]["search_form"]["trip_type_field"],
                    self.persian_processor.process_text(search_params["trip_type"])
                )
            await self.page.click("button[type='submit']")
            await self.page.wait_for_load_state("networkidle")
        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    async def _extract_flight_results(self) -> List[Dict]:
        try:
            await self.page.wait_for_selector(
                self.config["extraction_config"]["results_parsing"]["container"]
            )
            content = await self.page.content()
            soup = BeautifulSoup(content, "html.parser")
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
        try:
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
            for field in [
                "fare_conditions", "available_seats", "aircraft_type",
                "baggage_allowance", "meal_service", "special_services",
                "refund_policy", "change_policy", "fare_rules",
                "booking_class", "fare_basis", "ticket_validity",
                "miles_earned", "miles_required", "promotion_code",
                "special_offers"
            ]:
                selector = self.config["extraction_config"]["results_parsing"][field]
                if element.select_one(selector):
                    flight_data[field] = self.persian_processor.process_text(
                        element.select_one(selector).text
                    )
            return flight_data
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None

    def _validate_search_params(self, search_params: Dict):
        required_fields = ["origin", "destination", "departure_date", "passengers", "seat_class"]
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

    def _validate_flight_data(self, results: List[Dict]) -> List[Dict]:
        validated_results = []
        for result in results:
            if all(field in result for field in self.config["data_validation"]["required_fields"]):
                if (self.config["data_validation"]["price_range"]["min"] <= result["price"] <= 
                    self.config["data_validation"]["price_range"]["max"]):
                    if (self.config["data_validation"]["duration_range"]["min"] <= result["duration_minutes"] <= 
                        self.config["data_validation"]["duration_range"]["max"]):
                        validated_results.append(result)
        return validated_results 