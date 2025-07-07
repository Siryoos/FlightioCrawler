"""
Refactored Flightio adapter using EnhancedPersianAdapter.
"""

from typing import Dict, List, Optional, Any
import logging
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.airline_crawler import AirlineCrawler
from rate_limiter import RateLimiter
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler
from monitoring import Monitoring
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


class FlightioAdapter(EnhancedPersianAdapter):
    """
    Flightio.com adapter with minimal code duplication.

    Uses EnhancedPersianAdapter for all common functionality.
    Only implements aggregator-specific logic.
    """

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://flightio.com"
        self.search_url = config["search_url"]
        self.rate_limiter = RateLimiter(
            requests_per_second=config["rate_limiting"]["requests_per_second"],
            burst_limit=config["rate_limiting"]["burst_limit"],
            cooldown_period=config["rate_limiting"]["cooldown_period"],
        )
        self.error_handler = EnhancedErrorHandler(
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
            self.logger.error(f"Error crawling Flightio: {e}")
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
                    self.config["extraction_config"]["search_form"][
                        "return_date_field"
                    ],
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
        """
        Parse Flightio specific flight element structure.

        Uses parent class for common parsing with Iranian text processing.
        """
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            # Add Flightio specific fields
            config = self.config["extraction_config"]["results_parsing"]

            # Flightio specific: provider information
            provider_info = self._extract_text(element, config.get("provider_info"))
            if provider_info:
                flight_data["provider_info"] = self.persian_processor.process_text(
                    provider_info
                )

            # Mark as aggregator result
            flight_data["is_aggregator"] = True
            flight_data["aggregator_name"] = "flightio"

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Flightio search."""
        return ["origin", "destination", "departure_date", "passengers"]

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
