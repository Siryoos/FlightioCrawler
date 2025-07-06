"""
Enhanced international airline adapter with minimal code duplication.
"""

from typing import Dict, List, Optional, Any
from .enhanced_base_crawler import EnhancedBaseCrawler
from adapters.strategies.parsing_strategies import (
    ParsingStrategyFactory,
    FlightParsingStrategy
)


class EnhancedInternationalAdapter(EnhancedBaseCrawler):
    """
    Enhanced base class for international airline adapters.

    This class eliminates all initialization duplication and provides
    a clean interface for international airline crawlers with:
    - Automatic component initialization
    - Standard form filling for international sites
    - Common parsing logic
    - Enhanced error handling
    - Multi-currency support
    """

    def _initialize_adapter(self) -> None:
        """Initialize international adapter specific components."""
        # Set default currency if not specified
        self.default_currency = self.config.get("currency", "USD")

        # Initialize currency mapping for multi-currency support
        self.currency_symbols = {
            "USD": ["$", "USD", "US$"],
            "EUR": ["€", "EUR", "Euro"],
            "GBP": ["£", "GBP", "Pound"],
            "AED": ["AED", "د.إ"],
            "TRY": ["TRY", "₺", "TL"],
            "QAR": ["QAR", "ر.ق"],
            "CAD": ["CAD", "C$"],
            "AUD": ["AUD", "A$"],
            "JPY": ["JPY", "¥", "Yen"],
            "CHF": ["CHF", "Fr."],
            "SEK": ["SEK", "kr"],
            "NOK": ["NOK", "kr"],
            "DKK": ["DKK", "kr"],
        }

    async def _handle_language_selection(self) -> None:
        """Handle language selection for international sites."""
        try:
            language_config = self.config.get("extraction_config", {}).get(
                "language", {}
            )

            if language_config.get("selector"):
                # Try to set language to English
                await self.page.click(language_config["selector"], timeout=5000)

                if language_config.get("english_option"):
                    await self.page.click(
                        language_config["english_option"], timeout=5000
                    )
                    self.logger.debug("Language set to English")

        except Exception as e:
            self.logger.debug(f"Language selection not available or failed: {e}")

    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill search form for international airlines with enhanced error handling.

        Standard implementation that works for most international airlines.
        Override only if needed.
        """
        try:
            form_config = self.config.get("extraction_config", {}).get(
                "search_form", {}
            )

            if not form_config:
                raise ValueError("No search form configuration found")

            # Trip type with enhanced handling
            if "trip_type" in search_params and "trip_type_field" in form_config:
                await self._fill_trip_type(search_params["trip_type"], form_config)

            # Origin and destination with autocomplete handling
            await self._fill_airport_fields(search_params, form_config)

            # Dates with format validation
            await self._fill_date_fields(search_params, form_config)

            # Passengers with detailed breakdown
            await self._fill_passenger_fields(search_params, form_config)

            # Cabin class
            if "cabin_class" in search_params and "cabin_class_field" in form_config:
                await self._fill_cabin_class(search_params["cabin_class"], form_config)

            # Additional fields (flexible tickets, etc.)
            await self._fill_additional_fields(search_params, form_config)

            # Submit form with verification
            await self._submit_search_form(form_config)

        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    async def _fill_trip_type(
        self, trip_type: str, form_config: Dict[str, Any]
    ) -> None:
        """Fill trip type field with enhanced handling."""
        try:
            trip_type_field = form_config["trip_type_field"]

            # Handle different trip type input methods
            if trip_type_field.startswith("select"):
                await self.page.select_option(trip_type_field, trip_type)
            else:
                # Handle radio buttons or other input types
                trip_type_value = self._map_trip_type(trip_type)
                await self.page.click(f"{trip_type_field}[value='{trip_type_value}']")

        except Exception as e:
            self.logger.warning(f"Could not set trip type: {e}")

    def _map_trip_type(self, trip_type: str) -> str:
        """Map trip type to site-specific values."""
        mapping = {
            "oneway": ["oneway", "one-way", "ow", "1"],
            "roundtrip": ["roundtrip", "round-trip", "rt", "2"],
            "multicity": ["multicity", "multi-city", "mc", "3"],
        }

        trip_type_lower = trip_type.lower()
        for key, values in mapping.items():
            if trip_type_lower in values:
                return key

        return trip_type  # Return original if no mapping found

    async def _fill_airport_fields(
        self, search_params: Dict[str, Any], form_config: Dict[str, Any]
    ) -> None:
        """Fill origin and destination with autocomplete handling."""
        # Fill origin
        if "origin_field" in form_config:
            await self._fill_airport_field(
                form_config["origin_field"],
                search_params["origin"],
                form_config.get("origin_suggestion"),
                "origin",
            )

        # Fill destination
        if "destination_field" in form_config:
            await self._fill_airport_field(
                form_config["destination_field"],
                search_params["destination"],
                form_config.get("destination_suggestion"),
                "destination",
            )

    async def _fill_airport_field(
        self,
        field_selector: str,
        airport_code: str,
        suggestion_selector: Optional[str],
        field_type: str,
    ) -> None:
        """Fill individual airport field with autocomplete handling."""
        try:
            # Clear field first
            await self.page.fill(field_selector, "")

            # Type airport code
            await self.page.type(field_selector, airport_code, delay=100)

            # Handle autocomplete suggestions
            if suggestion_selector:
                try:
                    # Wait for suggestions to appear
                    await self.page.wait_for_selector(suggestion_selector, timeout=5000)

                    # Click first suggestion or exact match
                    suggestions = await self.page.query_selector_all(
                        suggestion_selector
                    )
                    if suggestions:
                        # Try to find exact match first
                        for suggestion in suggestions:
                            text = await suggestion.text_content()
                            if airport_code.upper() in text.upper():
                                await suggestion.click()
                                break
                        else:
                            # Click first suggestion if no exact match
                            await suggestions[0].click()

                except Exception as e:
                    self.logger.debug(
                        f"Autocomplete handling failed for {field_type}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Error filling {field_type} field: {e}")
            raise

    async def _fill_date_fields(
        self, search_params: Dict[str, Any], form_config: Dict[str, Any]
    ) -> None:
        """Fill date fields with format validation."""
        # Departure date
        if "departure_date_field" in form_config:
            departure_date = self._format_date(search_params["departure_date"])
            await self.page.fill(form_config["departure_date_field"], departure_date)

        # Return date (if applicable)
        if "return_date" in search_params and "return_date_field" in form_config:
            return_date = self._format_date(search_params["return_date"])
            await self.page.fill(form_config["return_date_field"], return_date)

    def _format_date(self, date_str: str) -> str:
        """Format date string for international sites."""
        try:
            from datetime import datetime

            # Try to parse different date formats
            formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]

            for fmt in formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    # Return in ISO format (most widely accepted)
                    return date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If no format matches, return original
            return date_str

        except Exception:
            return date_str

    async def _fill_passenger_fields(
        self, search_params: Dict[str, Any], form_config: Dict[str, Any]
    ) -> None:
        """Fill passenger fields with detailed breakdown."""
        try:
            # Handle total passengers field
            if "passengers" in search_params and "passengers_field" in form_config:
                await self.page.select_option(
                    form_config["passengers_field"], str(search_params["passengers"])
                )

            # Handle detailed passenger breakdown
            passenger_fields = {
                "adults": "adults_field",
                "children": "children_field",
                "infants": "infants_field",
            }

            for passenger_type, field_key in passenger_fields.items():
                if passenger_type in search_params and field_key in form_config:
                    await self.page.select_option(
                        form_config[field_key], str(search_params[passenger_type])
                    )

        except Exception as e:
            self.logger.warning(f"Could not set passenger information: {e}")

    async def _fill_cabin_class(
        self, cabin_class: str, form_config: Dict[str, Any]
    ) -> None:
        """Fill cabin class with mapping."""
        try:
            cabin_class_field = form_config["cabin_class_field"]
            mapped_class = self._map_cabin_class(cabin_class)

            await self.page.select_option(cabin_class_field, mapped_class)

        except Exception as e:
            self.logger.warning(f"Could not set cabin class: {e}")

    def _map_cabin_class(self, cabin_class: str) -> str:
        """Map cabin class to site-specific values."""
        mapping = {
            "economy": ["economy", "eco", "e", "coach"],
            "premium_economy": ["premium_economy", "premium", "pe", "premium_eco"],
            "business": ["business", "biz", "b", "business_class"],
            "first": ["first", "f", "first_class", "firstclass"],
        }

        cabin_lower = cabin_class.lower()
        for key, values in mapping.items():
            if cabin_lower in values:
                return key

        return cabin_class  # Return original if no mapping found

    async def _fill_additional_fields(
        self, search_params: Dict[str, Any], form_config: Dict[str, Any]
    ) -> None:
        """Fill additional optional fields."""
        try:
            # Flexible dates
            if (
                search_params.get("flexible_dates")
                and "flexible_dates_field" in form_config
            ):
                await self.page.check(form_config["flexible_dates_field"])

            # Direct flights only
            if (
                search_params.get("direct_only")
                and "direct_flights_field" in form_config
            ):
                await self.page.check(form_config["direct_flights_field"])

            # Preferred airline
            if (
                search_params.get("preferred_airline")
                and "preferred_airline_field" in form_config
            ):
                await self.page.select_option(
                    form_config["preferred_airline_field"],
                    search_params["preferred_airline"],
                )

        except Exception as e:
            self.logger.debug(f"Could not set additional fields: {e}")

    async def _submit_search_form(self, form_config: Dict[str, Any]) -> None:
        """Submit search form with verification."""
        try:
            # Get submit button selector
            submit_selector = form_config.get("submit_button", "button[type='submit']")

            # Click submit button
            await self.page.click(submit_selector)

            # Wait for navigation or results
            await self.page.wait_for_load_state("networkidle", timeout=30000)

            # Verify we're on results page
            current_url = self.page.url
            if (
                "search" in current_url
                or "results" in current_url
                or "flights" in current_url
            ):
                self.logger.debug("Successfully navigated to results page")
            else:
                self.logger.warning(f"May not be on results page: {current_url}")

        except Exception as e:
            self.logger.error(f"Error submitting search form: {e}")
            raise

    def _get_parsing_strategy(self) -> FlightParsingStrategy:
        """
        Get international parsing strategy for this adapter.
        
        Override the base class to force international strategy.
        """
        try:
            return ParsingStrategyFactory.create_strategy("international", self.config)
        except Exception as e:
            self.logger.warning(f"Failed to create international strategy, using auto-detection: {e}")
            return super()._get_parsing_strategy()

    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        DEPRECATED: Parse international flight element.
        
        This method is deprecated in favor of centralized parsing strategies.
        Use _parse_flight_data() which uses InternationalParsingStrategy from parsing_strategies.py.
        """
        import warnings
        warnings.warn(
            "International adapter _parse_flight_element is deprecated. Use centralized InternationalParsingStrategy.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Call parent's deprecated method for backward compatibility
        return super()._parse_flight_element(element)

    async def _post_process_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply international-specific post-processing to flight data.
        
        This adds international airline specific metadata and validation.
        """
        # Apply base post-processing first
        flight_data = await super()._post_process_flight_data(flight_data)
        
        # Add international-specific metadata
        flight_data.update({
            'adapter_type': 'international',
            'currency': flight_data.get('currency', 'USD'),
            'country': 'international',
            'language': 'english'
        })
        
        # International-specific validation
        if 'price' in flight_data and flight_data['price']:
            try:
                price = float(flight_data['price'])
                currency = flight_data.get('currency', 'USD')
                
                # Currency-specific price validation
                if currency == 'USD' and (price < 50 or price > 10000):
                    flight_data['price_warning'] = f'Price {price} {currency} seems unusual for international flight'
                elif currency == 'EUR' and (price < 45 or price > 9000):
                    flight_data['price_warning'] = f'Price {price} {currency} seems unusual for international flight'
                elif currency == 'GBP' and (price < 40 or price > 8000):
                    flight_data['price_warning'] = f'Price {price} {currency} seems unusual for international flight'
            except (ValueError, TypeError):
                pass
        
        # Normalize airline codes
        if 'airline' in flight_data and flight_data['airline']:
            airline_name = flight_data['airline']
            # Common airline code mappings
            airline_code_mappings = {
                'Emirates': 'EK',
                'Lufthansa': 'LH', 
                'British Airways': 'BA',
                'Air France': 'AF',
                'KLM': 'KL',
                'Turkish Airlines': 'TK',
                'Qatar Airways': 'QR',
                'Etihad Airways': 'EY'
            }
            
            if airline_name in airline_code_mappings:
                flight_data['airline_code'] = airline_code_mappings[airline_name]
        
        return flight_data

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for international flights with enhanced defaults."""
        return ["origin", "destination", "departure_date", "cabin_class"]

    def _validate_param_values(self, search_params: Dict[str, Any]) -> None:
        """Validate parameter values for international flights."""
        super()._validate_param_values(search_params)

        # Validate airport codes (should be 3 letters)
        for field in ["origin", "destination"]:
            if field in search_params:
                airport_code = search_params[field]
                if not isinstance(airport_code, str) or len(airport_code) != 3:
                    raise ValueError(
                        f"Invalid airport code format for {field}: {airport_code}"
                    )

        # Validate cabin class
        if "cabin_class" in search_params:
            valid_classes = ["economy", "premium_economy", "business", "first"]
            if search_params["cabin_class"].lower() not in valid_classes:
                raise ValueError(f"Invalid cabin class: {search_params['cabin_class']}")

    def _custom_flight_validation(self, flight_data: Dict[str, Any]) -> bool:
        """Custom validation for international flights."""
        # Check if price is reasonable for international flights
        if "price" in flight_data:
            price = flight_data["price"]
            if (
                price < 50 or price > 50000
            ):  # Reasonable range for international flights
                return False

        # Check if duration is reasonable
        if "duration_minutes" in flight_data:
            duration = flight_data["duration_minutes"]
            if duration < 30 or duration > 24 * 60:  # 30 minutes to 24 hours
                return False

        return True
