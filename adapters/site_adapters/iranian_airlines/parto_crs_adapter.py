from typing import Dict, List, Optional
import logging
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.airline_crawler import AirlineCrawler
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring


class PartoCRSAdapter(AirlineCrawler):
    """Crawler adapter for Parto CRS."""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.partocrs.com"
        self.search_url = config["search_url"]
        self.rate_limiter = RateLimiter(
            requests_per_second=config["rate_limiting"]["requests_per_second"],
            burst_limit=config["rate_limiting"]["burst_limit"],
            cooldown_period=config["rate_limiting"]["cooldown_period"],
        )
        self.error_handler = ErrorHandler(
            max_retries=config["error_handling"]["max_retries"],
            retry_delay=config["error_handling"]["retry_delay"],
            circuit_breaker_config=config["error_handling"]["circuit_breaker"],
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
            self.logger.error(f"Error crawling Air France: {e}")
            self.monitoring.record_error()
            raise

    async def _navigate_to_search_page(self) -> None:
        try:
            await self.page.navigate(self.search_url)
            await self.page.wait_for_load_state("networkidle")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise

    async def _fill_search_form(self, search_params: Dict) -> None:
        try:
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["origin_field"],
                search_params["origin"],
            )
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["destination_field"],
                search_params["destination"],
            )
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["departure_date_field"],
                search_params["departure_date"],
            )
            if "return_date" in search_params:
                await self.page.fill(
                    self.config["extraction_config"]["search_form"]["return_date_field"],
                    search_params["return_date"],
                )
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["cabin_class_field"],
                search_params["cabin_class"],
            )
            await self.page.click("button[type='submit']")
            await self.page.wait_for_load_state("networkidle")
        except Exception as e:
            self.logger.error(f"Error filling search form: {e}")
            raise

    async def _extract_flight_results(self) -> List[Dict]:
        try:
            await self.page.wait_for_selector(
                self.config["extraction_config"]["results_parsing"]["container"]
            )
            html = await self.page.content()
            soup = BeautifulSoup(html, "html.parser")
            flight_elements = soup.select(
                self.config["extraction_config"]["results_parsing"]["container"]
            )
            results: List[Dict] = []
            for element in flight_elements:
                flight = self._parse_flight_element(element)
                if flight:
                    results.append(flight)
            return results
        except Exception as e:
            self.logger.error(f"Error extracting flight results: {e}")
            raise

    def _parse_flight_element(self, element) -> Optional[Dict]:
        try:
            flight = {
                "airline": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["airline"]
                ).text.strip(),
                "flight_number": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["flight_number"]
                ).text.strip(),
                "departure_time": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["departure_time"]
                ).text.strip(),
                "arrival_time": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["arrival_time"]
                ).text.strip(),
                "duration": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["duration"]
                ).text.strip(),
                "price": self._extract_price(
                    element.select_one(
                        self.config["extraction_config"]["results_parsing"]["price"]
                    ).text.strip()
                ),
                "cabin_class": element.select_one(
                    self.config["extraction_config"]["results_parsing"]["cabin_class"]
                ).text.strip(),
            }
            return flight
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {e}")
            return None

    def _extract_price(self, price_text: str) -> float:
        try:
            cleaned = (
                price_text.replace("IRR", "")
                .replace("تومان", "")
                .replace(",", "")
                .strip()
            )
            return float(cleaned)
        except Exception as e:
            self.logger.error(f"Error extracting price: {e}")
            return 0.0

    def _validate_search_params(self, search_params: Dict) -> None:
        required = ["origin", "destination", "departure_date", "cabin_class"]
        for field in required:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

    def _validate_flight_data(self, results: List[Dict]) -> List[Dict]:
        validated: List[Dict] = []
        for result in results:
            if all(
                field in result
                for field in self.config["data_validation"]["required_fields"]
            ):
                if (
                    self.config["data_validation"]["price_range"]["min"]
                    <= result["price"]
                    <= self.config["data_validation"]["price_range"]["max"]
                ):
                    validated.append(result)
        return validated
