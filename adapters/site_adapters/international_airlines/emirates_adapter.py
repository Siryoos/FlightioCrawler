"""
Refactored Emirates adapter using EnhancedInternationalAdapter.
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
from error_handler import ErrorHandler
from monitoring import Monitoring


class EmiratesAdapter(EnhancedInternationalAdapter):
    """
    Emirates adapter with minimal code duplication.
    
    This adapter uses EnhancedInternationalAdapter for all common functionality
    and only implements Emirates specific logic.
    
    Key features:
    - Automatic initialization via parent class
    - International text processing built-in
    - Common error handling
    - Standard form filling and parsing
    - Only airline-specific logic implemented here
    """

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.emirates.com"
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
            self.logger.error(f"Error crawling Emirates: {str(e)}")
            self.monitoring.record_error()
            raise

    async def _navigate_to_search_page(self):
        try:
            await self.page.goto(self.search_url)
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
        """
        Parse Emirates flight element with airline-specific fields.

        Uses parent class for standard international parsing,
        then adds Emirates specific fields.
        """
        try:
            # Get standard flight data from parent class
            flight_data = super()._parse_flight_element(element)

            if not flight_data:
                return None

            # Add Emirates specific fields
            config = self.config["extraction_config"]["results_parsing"]
            emirates_specific = self._extract_emirates_specific_fields(element, config)

            # Merge with standard flight data
            flight_data.update(emirates_specific)

            # Add Emirates metadata
            flight_data["airline_code"] = "EK"
            flight_data["airline_name"] = "Emirates"
            flight_data["source_adapter"] = "Emirates"

            # Emirates specific validation
            if not self._validate_emirates_flight(flight_data):
                self.logger.debug("Flight data failed Emirates specific validation")
                return None

            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing Emirates flight element: {e}")
            return None

    def _extract_emirates_specific_fields(self, element, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract Emirates specific fields from flight element"""
        emirates_fields = {}

        try:
            # Extract Skywards miles
            skywards_selector = config.get("skywards_miles")
            if skywards_selector:
                skywards_text = self._extract_text(element, skywards_selector)
                if skywards_text:
                    miles = self._extract_miles(skywards_text)
                    if miles > 0:
                        emirates_fields["skywards_miles"] = miles

            # Extract cabin features
            cabin_features_selector = config.get("cabin_features")
            if cabin_features_selector:
                cabin_text = self._extract_text(element, cabin_features_selector)
                if cabin_text:
                    emirates_fields["cabin_features"] = cabin_text.strip()

            # Extract aircraft type
            aircraft_selector = config.get("aircraft_type")
            if aircraft_selector:
                aircraft_text = self._extract_text(element, aircraft_selector)
                if aircraft_text:
                    emirates_fields["aircraft_type"] = aircraft_text.strip()

            # Extract entertainment system info
            entertainment_selector = config.get("entertainment_system")
            if entertainment_selector:
                entertainment_text = self._extract_text(element, entertainment_selector)
                if entertainment_text:
                    emirates_fields["entertainment_system"] = entertainment_text.strip()

            # Extract meal service information
            meal_selector = config.get("meal_service")
            if meal_selector:
                meal_text = self._extract_text(element, meal_selector)
                if meal_text:
                    emirates_fields["meal_service"] = meal_text.strip()

            # Extract Wi-Fi availability
            wifi_selector = config.get("wifi_availability")
            if wifi_selector:
                wifi_text = self._extract_text(element, wifi_selector)
                if wifi_text:
                    emirates_fields["wifi_available"] = "wifi" in wifi_text.lower() or "wi-fi" in wifi_text.lower()

            # Extract seat configuration
            seat_config_selector = config.get("seat_configuration")
            if seat_config_selector:
                seat_config_text = self._extract_text(element, seat_config_selector)
                if seat_config_text:
                    emirates_fields["seat_configuration"] = seat_config_text.strip()

        except Exception as e:
            self.logger.debug(f"Error extracting Emirates specific fields: {e}")

        return emirates_fields

    def _validate_emirates_flight(self, flight_data: Dict[str, Any]) -> bool:
        """Validate Emirates specific flight data"""
        try:
            # Basic validation
            if not flight_data.get("price") or flight_data["price"] <= 0:
                return False

            # Emirates specific validations
            # Check if it's a valid Emirates flight
            airline_name = flight_data.get("airline_name", "").lower()
            if "emirates" not in airline_name and flight_data.get("airline_code") != "EK":
                return False

            # Validate flight number format (EK followed by numbers)
            flight_number = flight_data.get("flight_number", "")
            if flight_number and not flight_number.startswith("EK"):
                self.logger.debug(f"Invalid Emirates flight number format: {flight_number}")
                return False

            # Validate Skywards miles if present
            skywards_miles = flight_data.get("skywards_miles", 0)
            if skywards_miles < 0 or skywards_miles > 50000:  # Reasonable range
                self.logger.debug(f"Invalid Skywards miles value: {skywards_miles}")
                return False

            # Validate price range for Emirates (international flights)
            price = flight_data.get("price", 0)
            # Emirates is primarily international, so higher price ranges
            if price < 200 or price > 20000:  # $200 to $20,000 USD
                self.logger.debug(f"Price out of range for Emirates flight: ${price}")
                return False

            # Validate duration for international flights
            duration = flight_data.get("duration_minutes", 0)
            if duration < 60 or duration > 1200:  # 1 hour to 20 hours
                self.logger.debug(f"Invalid duration for Emirates flight: {duration} minutes")
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error validating Emirates flight: {e}")
            return False

    def _get_required_search_fields(self) -> List[str]:
        """Get required search fields for Emirates"""
        return ["origin", "destination", "departure_date", "adults", "cabin_class"]

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

    def _get_base_url(self) -> str:
        """Get Emirates base URL."""
        return "https://www.emirates.com"

    def _initialize_adapter(self) -> None:
        """Initialize Emirates specific components"""
        # Call parent initialization for international processing
        super()._initialize_adapter()
        
        # Emirates specific configurations
        self.airline_code = "EK"  # Emirates IATA code
        self.airline_name = "Emirates"
        
        # Emirates specific currency (usually USD for international bookings)
        self.default_currency = "USD"
        
        self.logger.info("Emirates adapter initialized with international text processing")

    async def _handle_page_setup(self) -> None:
        """Handle Emirates-specific page setup"""
        try:
            # Handle cookie consent efficiently
            await self._handle_emirates_cookie_consent()
            
            # Use parent's international language handling
            await self._handle_language_selection()
            
            # Wait for page stabilization
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            
        except Exception as e:
            self.logger.debug(f"Page setup completed with issues: {e}")

    async def _handle_emirates_cookie_consent(self) -> None:
        """Handle Emirates cookie consent dialog"""
        cookie_selectors = [
            'button[data-testid="cookie-accept"]',
            '.cookie-accept',
            '#cookie-accept',
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            '.btn-accept-cookies'
        ]
        
        for selector in cookie_selectors:
            try:
                await self.page.click(selector, timeout=2000)
                self.logger.debug("Cookie consent handled for Emirates")
                return
            except:
                continue

    async def _handle_emirates_specific_fields(self, search_params: Dict[str, Any]) -> None:
        """Handle Emirates specific form fields"""
        try:
            # Handle Skywards member number if provided
            if "skywards_number" in search_params:
                skywards_selector = ".skywards-number-input"
                try:
                    await self.page.fill(skywards_selector, search_params["skywards_number"])
                except Exception:
                    self.logger.debug("Skywards number field not available")

            # Handle flexible dates option
            if search_params.get("flexible_dates"):
                flexible_selector = ".flexible-dates-checkbox"
                try:
                    await self.page.check(flexible_selector)
                except Exception:
                    self.logger.debug("Flexible dates option not available")

            # Handle promotional code
            if "promo_code" in search_params:
                promo_selector = ".promo-code-input"
                try:
                    await self.page.fill(promo_selector, search_params["promo_code"])
                except Exception:
                    self.logger.debug("Promo code field not available")

        except Exception as e:
            self.logger.warning(f"Error handling Emirates specific fields: {e}")

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency for Emirates flights"""
        # Try to detect currency from the element first
        currency = super()._extract_currency(element, config)
        
        # If no currency detected, use USD as default for Emirates
        if not currency:
            currency = "USD"
            
        return currency

    def get_adapter_info(self) -> Dict[str, Any]:
        """Get Emirates specific adapter information"""
        base_info = super().get_adapter_info()
        
        emirates_info = {
            "airline_code": self.airline_code,
            "airline_name": self.airline_name,
            "supports_skywards": True,
            "supports_flexible_dates": True,
            "supports_promo_codes": True,
            "primary_currency": "USD",
            "hub_airports": ["DXB", "DWC"],
            "cabin_classes": ["Economy", "Premium Economy", "Business", "First"],
            "entertainment_system": "ice",
            "wifi_available": True,
        }
        
        base_info.update(emirates_info)
        return base_info
