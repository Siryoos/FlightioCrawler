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

from adapters.base_adapters import EnhancedPersianAdapter, AdapterUtils
from utils.persian_text_processor import PersianTextProcessor
from rate_limiter import RateLimiter
from error_handler import ErrorHandler
from monitoring import Monitoring
from adapters.base_adapters.common_error_handler import error_handler, safe_extract

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
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.mahan.aero"
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
            self.logger.error(f"Error crawling Mahan Air: {str(e)}")
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

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse Mahan Air flight element with airline-specific fields.
        
        Uses parent class for standard Persian parsing,
        then adds Mahan Air specific fields.
        """
        # Get standard flight data from parent class
        flight_data = super()._parse_flight_element(element)
        
        if not flight_data:
            return None
        
        # Add Mahan Air specific fields
        config = self.config.get("extraction_config", {}).get("results_parsing", {})
        mahan_specific = self._extract_mahan_air_specific_fields(element, config)
        
        # Merge with standard flight data
        flight_data.update(mahan_specific)
        
        # Add Mahan Air metadata
        flight_data["airline_code"] = "W5"  # Mahan Air IATA code
        flight_data["airline_name"] = "Mahan Air"
        flight_data["source_adapter"] = "MahanAir"
        
        # Mahan Air specific validation
        if not self._validate_mahan_air_flight(flight_data):
            self.logger.debug("Flight data failed Mahan Air specific validation")
            return None
        
        return flight_data

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

    def _get_base_url(self) -> str:
        """Get Mahan Air base URL."""
        return "https://www.mahan.aero"
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """Extract currency - always IRR for Mahan Air."""
        return "IRR"
    
    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Mahan Air search."""
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]

    @error_handler("mahan_air_specific_form_handling")
    async def _handle_mahan_air_specific_fields(self, search_params: Dict[str, Any]) -> None:
        """
        Handle Mahan Air specific form fields.
        
        This method handles any fields that are unique to Mahan Air
        and not covered by the standard Persian form filling.
        """
        try:
            # Mahan Air specific: Loyalty program member
            if search_params.get("loyalty_member"):
                loyalty_checkbox = ".loyalty-member-checkbox"
                if await self.page.query_selector(loyalty_checkbox):
                    await self.page.check(loyalty_checkbox)
                    self.logger.debug("Loyalty member option selected")
            
            # Mahan Air specific: Preferred departure time
            if search_params.get("preferred_time"):
                time_selector = "#preferred-time-select"
                if await self.page.query_selector(time_selector):
                    await self.page.select_option(time_selector, search_params["preferred_time"])
                    self.logger.debug(f"Preferred time set to: {search_params['preferred_time']}")
            
            # Mahan Air specific: Charter flight preference
            if search_params.get("charter_only"):
                charter_checkbox = ".charter-only-checkbox"
                if await self.page.query_selector(charter_checkbox):
                    await self.page.check(charter_checkbox)
                    self.logger.debug("Charter only option selected")
                    
        except Exception as e:
            self.logger.warning(f"Could not set Mahan Air specific fields: {e}")
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill search form with Mahan Air specific handling.
        
        Uses parent class for standard Persian form filling,
        then adds Mahan Air specific fields.
        """
        # Use parent class for standard form filling
        await super()._fill_search_form(search_params)
        
        # Add Mahan Air specific form handling
        await self._handle_mahan_air_specific_fields(search_params)
    
    @safe_extract(default_value={})
    def _extract_mahan_air_specific_fields(self, element, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Mahan Air specific fields from flight element.
        
        Args:
            element: BeautifulSoup element containing flight data
            config: Extraction configuration
            
        Returns:
            Dictionary with Mahan Air specific fields
        """
        mahan_specific = {}
        
        # Mahan Miles (loyalty program points)
        loyalty_points_selector = config.get("mahan_miles")
        if loyalty_points_selector:
            loyalty_points = self._extract_text(element, loyalty_points_selector)
            if loyalty_points:
                # Extract numeric value from Persian text
                points_value = AdapterUtils.extract_numeric_value(
                    self.persian_processor.process_text(loyalty_points)
                )
                mahan_specific["mahan_miles"] = int(points_value) if points_value > 0 else 0
        
        # Charter flight information
        charter_selector = config.get("charter_indicator")
        if charter_selector:
            charter_info = self._extract_text(element, charter_selector)
            if charter_info:
                charter_text = self.persian_processor.process_text(charter_info)
                mahan_specific["is_charter"] = "چارتر" in charter_text or "charter" in charter_text.lower()
                mahan_specific["charter_info"] = charter_text
        
        # Aircraft type (Mahan Air specific)
        aircraft_selector = config.get("aircraft_type")
        if aircraft_selector:
            aircraft_info = self._extract_text(element, aircraft_selector)
            if aircraft_info:
                aircraft_text = self.persian_processor.process_text(aircraft_info)
                mahan_specific["aircraft_type"] = aircraft_text
        
        # Meal service information
        meal_selector = config.get("meal_service")
        if meal_selector:
            meal_info = self._extract_text(element, meal_selector)
            if meal_info:
                meal_text = self.persian_processor.process_text(meal_info)
                mahan_specific["meal_service"] = meal_text
                mahan_specific["has_meal"] = "وعده" in meal_text or "غذا" in meal_text
        
        # Baggage allowance
        baggage_selector = config.get("baggage_allowance")
        if baggage_selector:
            baggage_info = self._extract_text(element, baggage_selector)
            if baggage_info:
                baggage_text = self.persian_processor.process_text(baggage_info)
                mahan_specific["baggage_allowance"] = baggage_text
                
                # Extract baggage weight if present
                baggage_weight = AdapterUtils.extract_numeric_value(baggage_text)
                if baggage_weight > 0:
                    mahan_specific["baggage_weight_kg"] = int(baggage_weight)
        
        # Special offers or promotions
        promotion_selector = config.get("promotion_info")
        if promotion_selector:
            promotion_info = self._extract_text(element, promotion_selector)
            if promotion_info:
                promotion_text = self.persian_processor.process_text(promotion_info)
                mahan_specific["promotion_info"] = promotion_text
                mahan_specific["has_promotion"] = bool(promotion_text.strip())
        
        return mahan_specific
    
    def _validate_mahan_air_flight(self, flight_data: Dict[str, Any]) -> bool:
        """
        Validate flight data with Mahan Air specific rules.
        
        Args:
            flight_data: Flight data to validate
            
        Returns:
            True if flight data is valid for Mahan Air
        """
        try:
            # Check if flight number follows Mahan Air pattern (W5xxx)
            flight_number = flight_data.get("flight_number", "")
            if flight_number and not flight_number.startswith("W5"):
                # Log warning but don't reject (might be codeshare)
                self.logger.debug(f"Unusual flight number for Mahan Air: {flight_number}")
            
            # Validate Mahan Miles if present
            mahan_miles = flight_data.get("mahan_miles", 0)
            if mahan_miles < 0 or mahan_miles > 50000:  # Reasonable range
                self.logger.debug(f"Invalid Mahan Miles value: {mahan_miles}")
                flight_data["mahan_miles"] = 0
            
            # Validate baggage weight if present
            baggage_weight = flight_data.get("baggage_weight_kg", 0)
            if baggage_weight < 0 or baggage_weight > 50:  # Reasonable range
                self.logger.debug(f"Invalid baggage weight: {baggage_weight}")
                flight_data.pop("baggage_weight_kg", None)
            
            # Use parent class validation
            return super()._custom_flight_validation(flight_data)
            
        except Exception as e:
            self.logger.error(f"Error in Mahan Air flight validation: {e}")
            return False
    
    @error_handler("mahan_air_post_processing")
    async def _post_process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-process results with Mahan Air specific logic.
        
        Args:
            results: Raw flight results
            
        Returns:
            Processed results
        """
        processed_results = []
        
        for flight in results:
            try:
                # Add calculated fields
                flight["flight_id"] = AdapterUtils.create_flight_id(flight)
                
                # Standardize time format
                if "departure_time" in flight:
                    flight["departure_time"] = AdapterUtils.standardize_time_format(
                        flight["departure_time"]
                    )
                
                if "arrival_time" in flight:
                    flight["arrival_time"] = AdapterUtils.standardize_time_format(
                        flight["arrival_time"]
                    )
                
                # Calculate duration if not present
                if ("departure_time" in flight and "arrival_time" in flight and 
                    "duration_minutes" not in flight):
                    duration = AdapterUtils.calculate_duration_minutes(
                        flight["departure_time"], flight["arrival_time"]
                    )
                    if duration > 0:
                        flight["duration_minutes"] = duration
                
                # Format price for display
                if "price" in flight and "currency" in flight:
                    flight["price_formatted"] = AdapterUtils.format_currency(
                        flight["price"], flight["currency"]
                    )
                
                # Add extraction timestamp
                flight["extracted_at"] = self.current_timestamp.isoformat()
                
                processed_results.append(flight)
                
            except Exception as e:
                self.logger.warning(f"Error post-processing flight: {e}")
                # Still include the flight even if post-processing fails
                processed_results.append(flight)
        
        return processed_results
    
    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """
        Extract flight results with Mahan Air specific post-processing.
        
        Uses parent class for standard extraction,
        then applies Mahan Air specific post-processing.
        """
        # Use parent class for standard extraction
        results = await super()._extract_flight_results()
        
        # Apply Mahan Air specific post-processing
        processed_results = await self._post_process_results(results)
        
        self.logger.info(f"Extracted {len(processed_results)} flights from Mahan Air")
        
        return processed_results
    
    def _get_adapter_specific_config(self) -> Dict[str, Any]:
        """
        Get Mahan Air specific configuration.
        
        Returns:
            Configuration specific to Mahan Air
        """
        return {
            "supports_charter": True,
            "supports_loyalty_program": True,
            "loyalty_program_name": "Mahan Miles",
            "domestic_routes_only": True,
            "typical_aircraft_types": ["A310", "A340", "A300", "ATR"],
            "meal_service_available": True,
            "baggage_included": True
        } 