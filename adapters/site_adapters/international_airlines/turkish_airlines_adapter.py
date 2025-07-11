"""
Refactored Turkish Airlines adapter using EnhancedInternationalAdapter.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.enhanced_international_adapter import (
    EnhancedInternationalAdapter,
)
from rate_limiter import RateLimiter
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler
from monitoring import Monitoring


class TurkishAirlinesAdapter(EnhancedInternationalAdapter):
    """Turkish Airlines adapter with minimal code duplication."""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.turkishairlines.com"
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
            self.logger.error(f"Error crawling Turkish Airlines: {str(e)}")
            self.monitoring.record_error()
            raise

    async def _navigate_to_search_page(self):
        try:
            await self.page.navigate(self.search_url)
            await self.page.wait_for_load_state("networkidle")
            # Handle cookie consent if present
            try:
                await self.page.click(
                    self.config["extraction_config"]["cookie_consent_button"]
                )
            except:
                self.logger.info("No cookie consent dialog found")
            # Handle language selection if needed
            try:
                await self.page.click(
                    self.config["extraction_config"]["language_selector"]
                )
                await self.page.select_option(
                    self.config["extraction_config"]["language_selector"], "en"
                )
            except:
                self.logger.info("No language selector found or already in English")
        except TimeoutError:
            self.logger.error("Timeout while loading search page")
            raise

    async def _fill_search_form(self, search_params: Dict):
        try:
            # Handle trip type
            if "trip_type" in search_params:
                await self.page.click(
                    self.config["extraction_config"]["search_form"]["trip_type_field"]
                )
                await self.page.select_option(
                    self.config["extraction_config"]["search_form"]["trip_type_field"],
                    search_params["trip_type"],
                )

            # Handle origin
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["origin_field"],
                search_params["origin"],
            )
            await self.page.wait_for_selector(
                self.config["extraction_config"]["search_form"]["origin_suggestion"]
            )
            await self.page.click(
                self.config["extraction_config"]["search_form"]["origin_suggestion"]
            )

            # Handle destination
            await self.page.fill(
                self.config["extraction_config"]["search_form"]["destination_field"],
                search_params["destination"],
            )
            await self.page.wait_for_selector(
                self.config["extraction_config"]["search_form"][
                    "destination_suggestion"
                ]
            )
            await self.page.click(
                self.config["extraction_config"]["search_form"][
                    "destination_suggestion"
                ]
            )

            # Handle dates
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

            # Handle passengers
            await self.page.click(
                self.config["extraction_config"]["search_form"]["passengers_field"]
            )
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["adults_field"],
                str(search_params["adults"]),
            )
            if "children" in search_params:
                await self.page.select_option(
                    self.config["extraction_config"]["search_form"]["children_field"],
                    str(search_params["children"]),
                )
            if "infants" in search_params:
                await self.page.select_option(
                    self.config["extraction_config"]["search_form"]["infants_field"],
                    str(search_params["infants"]),
                )

            # Handle cabin class
            await self.page.select_option(
                self.config["extraction_config"]["search_form"]["cabin_class_field"],
                search_params["cabin_class"],
            )

            # Submit form
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

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse Turkish Airlines specific flight element structure."""
        flight_data = super()._parse_flight_element(element)

        if flight_data:
            config = self.config["extraction_config"]["results_parsing"]

            # Turkish Airlines specific: Miles&Smiles points
            miles_smiles = self._extract_text(element, config.get("miles_smiles"))
            if miles_smiles:
                flight_data["miles_smiles"] = miles_smiles

        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        return ["origin", "destination", "departure_date", "cabin_class"]

    def _validate_search_params(self, search_params: Dict):
        required_fields = [
            "origin",
            "destination",
            "departure_date",
            "adults",
            "cabin_class",
        ]
        for field in required_fields:
            if field not in search_params:
                raise ValueError(f"Missing required search parameter: {field}")

    def _validate_flight_data(self, results: List[Dict]) -> List[Dict]:
        validated_results = []
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
                    if (
                        self.config["data_validation"]["duration_range"]["min"]
                        <= result["duration_minutes"]
                        <= self.config["data_validation"]["duration_range"]["max"]
                    ):
                        validated_results.append(result)
        return validated_results
