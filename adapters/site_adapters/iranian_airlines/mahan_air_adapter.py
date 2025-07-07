"""
Refactored Mahan Air adapter using enhanced base classes.

This adapter demonstrates how to use the new enhanced base classes
to eliminate code duplication and provide a clean implementation.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from adapters.base_adapters.enhanced_error_handler import error_handler_decorator as error_handler, safe_extract


class MahanAirAdapter(EnhancedPersianAdapter):
    """
    Mahan Air adapter with minimal code duplication.

    This adapter uses EnhancedPersianAdapter for all common functionality
    and only implements Mahan Air specific logic.

    Key features:
    - Automatic initialization via parent class
    - Persian text processing built-in
    - Common error handling
    - Standard form filling and parsing
    - Only airline-specific logic implemented here
    """

    def _get_base_url(self) -> str:
        """Get Mahan Air base URL."""
        return "https://www.mahan.aero"

    def _initialize_adapter(self) -> None:
        """Initialize Mahan Air specific components"""
        # Call parent initialization for Persian processing
        super()._initialize_adapter()
        
        # Mahan Air specific configurations
        self.airline_code = "W5"  # Mahan Air IATA code
        self.airline_name = "Mahan Air"
        
        self.logger.info("Mahan Air adapter initialized with Persian text processing")

    @error_handler("mahan_air_specific_form_handling")
    async def _handle_mahan_air_specific_fields(
        self, search_params: Dict[str, Any]
    ) -> None:
        """Handle Mahan Air specific form fields"""
        try:
            # Handle frequent flyer number if provided
            if "frequent_flyer_number" in search_params:
                frequent_flyer_selector = ".frequent-flyer-input"
                try:
                    await self.page.fill(frequent_flyer_selector, search_params["frequent_flyer_number"])
                except Exception:
                    self.logger.debug("Frequent flyer field not available")

            # Handle special requests
            if "special_requests" in search_params:
                special_requests_selector = ".special-requests"
                try:
                    await self.page.check(special_requests_selector)
                except Exception:
                    self.logger.debug("Special requests field not available")

            # Handle meal preferences
            if "meal_preference" in search_params:
                meal_selector = ".meal-preference-select"
                try:
                    await self.page.select_option(meal_selector, search_params["meal_preference"])
                except Exception:
                    self.logger.debug("Meal preference field not available")

        except Exception as e:
            self.logger.warning(f"Error handling Mahan Air specific fields: {e}")

    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill Mahan Air search form using Persian adapter capabilities.
        
        This method leverages the Persian text processing from the parent class
        and adds Mahan Air specific handling.
        """
        try:
            # Use parent's Persian form filling capabilities
            await super()._fill_search_form(search_params)
            
            # Handle Mahan Air specific fields
            await self._handle_mahan_air_specific_fields(search_params)
            
        except Exception as e:
            self.logger.error(f"Error filling Mahan Air search form: {e}")
            raise

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Mahan Air flight element with airline-specific fields.

        Uses parent class for standard Persian parsing,
        then adds Mahan Air specific fields.
        """
        try:
            # Get standard flight data from parent class
            flight_data = super()._parse_flight_element(element)

            if not flight_data:
                return None

            # Add Mahan Air specific fields
            config = self.config.extraction_config.get("results_parsing", {})
            mahan_specific = self._extract_mahan_air_specific_fields(element, config)

            # Merge with standard flight data
            flight_data.update(mahan_specific)

            # Add Mahan Air metadata
            flight_data["airline_code"] = self.airline_code
            flight_data["airline_name"] = self.airline_name
            flight_data["source_adapter"] = "MahanAir"

            # Mahan Air specific validation
            if not self._validate_mahan_air_flight(flight_data):
                self.logger.debug("Flight data failed Mahan Air specific validation")
                return None

            return flight_data
            
        except Exception as e:
            self.logger.error(f"Error parsing Mahan Air flight element: {e}")
            return None

    @safe_extract(default_value={})
    def _extract_mahan_air_specific_fields(
        self, element, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract Mahan Air specific fields from flight element"""
        mahan_fields = {}

        try:
            # Extract aircraft type (Mahan Air often shows this)
            aircraft_selector = config.get("aircraft_type")
            if aircraft_selector:
                aircraft_text = self._extract_text(element, aircraft_selector)
                if aircraft_text:
                    mahan_fields["aircraft_type"] = self.persian_processor.process_text(aircraft_text)

            # Extract meal service information
            meal_selector = config.get("meal_service")
            if meal_selector:
                meal_text = self._extract_text(element, meal_selector)
                if meal_text:
                    mahan_fields["meal_service"] = self.persian_processor.process_text(meal_text)

            # Extract baggage allowance
            baggage_selector = config.get("baggage_allowance")
            if baggage_selector:
                baggage_text = self._extract_text(element, baggage_selector)
                if baggage_text:
                    mahan_fields["baggage_allowance"] = self.persian_processor.process_text(baggage_text)

            # Extract seat selection availability
            seat_selector = config.get("seat_selection")
            if seat_selector:
                seat_text = self._extract_text(element, seat_selector)
                if seat_text:
                    mahan_fields["seat_selection_available"] = "انتخاب صندلی" in seat_text

            # Extract frequent flyer miles
            miles_selector = config.get("frequent_flyer_miles")
            if miles_selector:
                miles_text = self._extract_text(element, miles_selector)
                if miles_text:
                    miles = self._extract_miles(miles_text)
                    if miles > 0:
                        mahan_fields["frequent_flyer_miles"] = miles

            # Extract refund policy
            refund_selector = config.get("refund_policy")
            if refund_selector:
                refund_text = self._extract_text(element, refund_selector)
                if refund_text:
                    mahan_fields["refund_policy"] = self.persian_processor.process_text(refund_text)

            # Extract change policy
            change_selector = config.get("change_policy")
            if change_selector:
                change_text = self._extract_text(element, change_selector)
                if change_text:
                    mahan_fields["change_policy"] = self.persian_processor.process_text(change_text)

            # Extract booking class
            booking_class_selector = config.get("booking_class")
            if booking_class_selector:
                booking_class_text = self._extract_text(element, booking_class_selector)
                if booking_class_text:
                    mahan_fields["booking_class"] = booking_class_text.strip()

        except Exception as e:
            self.logger.debug(f"Error extracting Mahan Air specific fields: {e}")

        return mahan_fields

    def _validate_mahan_air_flight(self, flight_data: Dict[str, Any]) -> bool:
        """Validate Mahan Air specific flight data"""
        try:
            # Basic validation
            if not flight_data.get("price") or flight_data["price"] <= 0:
                return False

            # Mahan Air specific validations
            # Check if it's a valid Mahan Air flight
            airline_name = flight_data.get("airline_name", "").lower()
            if "mahan" not in airline_name and flight_data.get("airline_code") != "W5":
                return False

            # Validate flight number format (W5 followed by numbers)
            flight_number = flight_data.get("flight_number", "")
            if flight_number and not (flight_number.startswith("W5") or flight_number.startswith("ماهان")):
                self.logger.debug(f"Invalid Mahan Air flight number format: {flight_number}")
                return False

            # Validate price range for Mahan Air (domestic flights)
            price = flight_data.get("price", 0)
            if self._is_domestic_flight_persian(flight_data):
                # Domestic flights should be within reasonable range
                if price < 500000 or price > 20000000:  # 500K to 20M IRR
                    self.logger.debug(f"Price out of range for domestic Mahan Air flight: {price}")
                    return False
            else:
                # International flights
                if price < 5000000 or price > 100000000:  # 5M to 100M IRR
                    self.logger.debug(f"Price out of range for international Mahan Air flight: {price}")
                    return False

            # Validate duration
            duration = flight_data.get("duration_minutes", 0)
            if duration < 30 or duration > 1440:  # 30 minutes to 24 hours
                self.logger.debug(f"Invalid duration for Mahan Air flight: {duration}")
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error validating Mahan Air flight: {e}")
            return False

    def _get_required_search_fields(self) -> List[str]:
        """Get required search fields for Mahan Air"""
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]

    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - always IRR for Mahan Air."""
        return "IRR"

    @error_handler("mahan_air_post_processing")
    async def _post_process_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Post-process Mahan Air results"""
        processed_results = []

        for result in results:
            try:
                # Normalize airline name
                result["airline_name"] = self.persian_processor.normalize_airline_name(
                    result.get("airline_name", "Mahan Air")
                )

                # Process flight number
                if "flight_number" in result:
                    result["flight_number"] = self.persian_processor.clean_flight_number(
                        result["flight_number"]
                    )

                # Convert Persian numbers to English
                for field in ["price", "duration_minutes"]:
                    if field in result and isinstance(result[field], str):
                        result[field] = self.persian_processor.convert_persian_numbers(result[field])

                # Add Mahan Air specific metadata
                result["is_domestic"] = self._is_domestic_flight_persian(result)
                result["flight_type"] = self._classify_persian_flight(result)

                processed_results.append(result)

            except Exception as e:
                self.logger.debug(f"Error post-processing Mahan Air result: {e}")
                continue

        return processed_results

    def _get_adapter_specific_config(self) -> Dict[str, Any]:
        """Get Mahan Air specific configuration"""
        return {
            "airline_code": self.airline_code,
            "airline_name": self.airline_name,
            "supports_seat_selection": True,
            "supports_meal_selection": True,
            "supports_frequent_flyer": True,
            "currency": "IRR",
            "domestic_routes": True,
            "international_routes": True,
        }
