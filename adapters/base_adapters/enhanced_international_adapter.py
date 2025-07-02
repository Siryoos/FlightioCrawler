"""
Enhanced international airline adapter with minimal code duplication.
"""

from typing import Dict, List, Optional, Any
from .enhanced_base_crawler import EnhancedBaseCrawler


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
            'USD': ['$', 'USD', 'US$'],
            'EUR': ['€', 'EUR', 'Euro'],
            'GBP': ['£', 'GBP', 'Pound'],
            'AED': ['AED', 'د.إ'],
            'TRY': ['TRY', '₺', 'TL'],
            'QAR': ['QAR', 'ر.ق'],
            'CAD': ['CAD', 'C$'],
            'AUD': ['AUD', 'A$'],
            'JPY': ['JPY', '¥', 'Yen'],
            'CHF': ['CHF', 'Fr.'],
            'SEK': ['SEK', 'kr'],
            'NOK': ['NOK', 'kr'],
            'DKK': ['DKK', 'kr']
        }
    
    async def _handle_language_selection(self) -> None:
        """Handle language selection for international sites."""
        try:
            language_config = self.config.get("extraction_config", {}).get("language", {})
            
            if language_config.get("selector"):
                # Try to set language to English
                await self.page.click(language_config["selector"], timeout=5000)
                
                if language_config.get("english_option"):
                    await self.page.click(language_config["english_option"], timeout=5000)
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
            form_config = self.config.get("extraction_config", {}).get("search_form", {})
            
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
    
    async def _fill_trip_type(self, trip_type: str, form_config: Dict[str, Any]) -> None:
        """Fill trip type field with enhanced handling."""
        try:
            trip_type_field = form_config["trip_type_field"]
            
            # Handle different trip type input methods
            if trip_type_field.startswith('select'):
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
            'oneway': ['oneway', 'one-way', 'ow', '1'],
            'roundtrip': ['roundtrip', 'round-trip', 'rt', '2'],
            'multicity': ['multicity', 'multi-city', 'mc', '3']
        }
        
        trip_type_lower = trip_type.lower()
        for key, values in mapping.items():
            if trip_type_lower in values:
                return key
        
        return trip_type  # Return original if no mapping found
    
    async def _fill_airport_fields(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
        """Fill origin and destination with autocomplete handling."""
        # Fill origin
        if "origin_field" in form_config:
            await self._fill_airport_field(
                form_config["origin_field"],
                search_params["origin"],
                form_config.get("origin_suggestion"),
                "origin"
            )
        
        # Fill destination
        if "destination_field" in form_config:
            await self._fill_airport_field(
                form_config["destination_field"],
                search_params["destination"],
                form_config.get("destination_suggestion"),
                "destination"
            )
    
    async def _fill_airport_field(
        self, 
        field_selector: str, 
        airport_code: str, 
        suggestion_selector: Optional[str],
        field_type: str
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
                    suggestions = await self.page.query_selector_all(suggestion_selector)
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
                    self.logger.debug(f"Autocomplete handling failed for {field_type}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error filling {field_type} field: {e}")
            raise
    
    async def _fill_date_fields(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
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
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
            
            for fmt in formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    # Return in ISO format (most widely accepted)
                    return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # If no format matches, return original
            return date_str
            
        except Exception:
            return date_str
    
    async def _fill_passenger_fields(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
        """Fill passenger fields with detailed breakdown."""
        try:
            # Handle total passengers field
            if "passengers" in search_params and "passengers_field" in form_config:
                await self.page.select_option(
                    form_config["passengers_field"],
                    str(search_params["passengers"])
                )
            
            # Handle detailed passenger breakdown
            passenger_fields = {
                "adults": "adults_field",
                "children": "children_field", 
                "infants": "infants_field"
            }
            
            for passenger_type, field_key in passenger_fields.items():
                if passenger_type in search_params and field_key in form_config:
                    await self.page.select_option(
                        form_config[field_key],
                        str(search_params[passenger_type])
                    )
                    
        except Exception as e:
            self.logger.warning(f"Could not set passenger information: {e}")
    
    async def _fill_cabin_class(self, cabin_class: str, form_config: Dict[str, Any]) -> None:
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
            'economy': ['economy', 'eco', 'e', 'coach'],
            'premium_economy': ['premium_economy', 'premium', 'pe', 'premium_eco'],
            'business': ['business', 'biz', 'b', 'business_class'],
            'first': ['first', 'f', 'first_class', 'firstclass']
        }
        
        cabin_lower = cabin_class.lower()
        for key, values in mapping.items():
            if cabin_lower in values:
                return key
        
        return cabin_class  # Return original if no mapping found
    
    async def _fill_additional_fields(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
        """Fill additional optional fields."""
        try:
            # Flexible dates
            if search_params.get("flexible_dates") and "flexible_dates_field" in form_config:
                await self.page.check(form_config["flexible_dates_field"])
            
            # Direct flights only
            if search_params.get("direct_only") and "direct_flights_field" in form_config:
                await self.page.check(form_config["direct_flights_field"])
            
            # Preferred airline
            if search_params.get("preferred_airline") and "preferred_airline_field" in form_config:
                await self.page.select_option(
                    form_config["preferred_airline_field"],
                    search_params["preferred_airline"]
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
            if "search" in current_url or "results" in current_url or "flights" in current_url:
                self.logger.debug("Successfully navigated to results page")
            else:
                self.logger.warning(f"May not be on results page: {current_url}")
                
        except Exception as e:
            self.logger.error(f"Error submitting search form: {e}")
            raise
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for international airlines with enhanced extraction.
        
        Standard implementation that extracts common fields.
        Override to add airline-specific fields.
        """
        try:
            config = self.config.get("extraction_config", {}).get("results_parsing", {})
            
            if not config:
                raise ValueError("No results parsing configuration found")
            
            # Extract basic fields with enhanced error handling
            flight_data = {}
            
            # Core flight information
            core_fields = {
                "airline": "airline",
                "flight_number": "flight_number", 
                "departure_time": "departure_time",
                "arrival_time": "arrival_time",
                "duration": "duration",
                "price": "price",
                "cabin_class": "cabin_class"
            }
            
            for field, selector_key in core_fields.items():
                if selector_key in config:
                    value = self._extract_text(element, config[selector_key])
                    if field == "price":
                        flight_data[field] = self._extract_price(value)
                    elif field == "duration":
                        flight_data[field] = value
                        flight_data["duration_minutes"] = self._extract_duration_minutes(value)
                    else:
                        flight_data[field] = value
            
            # Currency extraction
            flight_data["currency"] = self._extract_currency(element, config)
            
            # Extract optional fields
            self._extract_optional_fields_international(element, flight_data, config)
            
            # Add flight type classification
            flight_data["flight_type"] = self._classify_flight_type(flight_data)
            
            return flight_data if flight_data.get("airline") else None
            
        except Exception as e:
            self.logger.error(f"Error parsing flight element: {str(e)}")
            return None
    
    def _extract_currency(self, element, config: Dict[str, Any]) -> str:
        """
        Extract currency from element with enhanced detection.
        
        Override for specific currency extraction logic.
        """
        try:
            # Strategy 1: Use configured currency selector
            if "currency" in config:
                currency_text = self._extract_text(element, config["currency"])
                if currency_text:
                    detected_currency = self._detect_currency(currency_text)
                    if detected_currency:
                        return detected_currency
            
            # Strategy 2: Extract from price text
            price_text = self._extract_text(element, config.get("price", ""))
            if price_text:
                detected_currency = self._detect_currency(price_text)
                if detected_currency:
                    return detected_currency
            
            # Strategy 3: Use default currency
            return self.default_currency
            
        except Exception:
            return self.default_currency
    
    def _detect_currency(self, text: str) -> Optional[str]:
        """Detect currency from text using symbol mapping."""
        if not text:
            return None
        
        text_upper = text.upper()
        
        for currency, symbols in self.currency_symbols.items():
            for symbol in symbols:
                if symbol.upper() in text_upper:
                    return currency
        
        return None
    
    def _extract_optional_fields_international(
        self, 
        element, 
        flight_data: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> None:
        """Extract optional fields for international flights."""
        optional_fields = [
            "fare_conditions", "available_seats", "aircraft_type",
            "baggage_allowance", "meal_service", "special_services",
            "refund_policy", "change_policy", "fare_rules",
            "booking_class", "fare_basis", "ticket_validity",
            "miles_earned", "miles_required", "promotion_code",
            "special_offers", "layovers", "total_duration",
            "departure_airport", "arrival_airport", "departure_terminal",
            "arrival_terminal", "operating_airline", "codeshare_info"
        ]
        
        for field in optional_fields:
            if field in config:
                value = self._extract_text(element, config[field])
                if value:
                    # Special processing for specific fields
                    if field == "layovers":
                        flight_data[field] = self._parse_layovers(value)
                    elif field == "baggage_allowance":
                        flight_data[field] = self._parse_baggage_info(value)
                    elif field in ["miles_earned", "miles_required"]:
                        flight_data[field] = self._extract_miles(value)
                    else:
                        flight_data[field] = value
    
    def _parse_layovers(self, layover_text: str) -> Dict[str, Any]:
        """Parse layover information."""
        try:
            if "direct" in layover_text.lower() or "nonstop" in layover_text.lower():
                return {"type": "direct", "count": 0, "airports": []}
            
            # Extract number of stops
            import re
            stops_match = re.search(r'(\d+)\s*stop', layover_text.lower())
            stop_count = int(stops_match.group(1)) if stops_match else 1
            
            # Extract airport codes
            airport_codes = re.findall(r'\b[A-Z]{3}\b', layover_text)
            
            return {
                "type": "connecting",
                "count": stop_count,
                "airports": airport_codes,
                "raw_text": layover_text
            }
            
        except Exception:
            return {"type": "unknown", "raw_text": layover_text}
    
    def _parse_baggage_info(self, baggage_text: str) -> Dict[str, Any]:
        """Parse baggage allowance information."""
        try:
            import re
            
            # Extract weight limits
            weight_match = re.search(r'(\d+)\s*kg', baggage_text.lower())
            weight_limit = int(weight_match.group(1)) if weight_match else None
            
            # Extract piece limits
            piece_match = re.search(r'(\d+)\s*(?:piece|bag)', baggage_text.lower())
            piece_limit = int(piece_match.group(1)) if piece_match else None
            
            return {
                "weight_limit_kg": weight_limit,
                "piece_limit": piece_limit,
                "raw_text": baggage_text
            }
            
        except Exception:
            return {"raw_text": baggage_text}
    
    def _extract_miles(self, miles_text: str) -> int:
        """Extract miles/points from text."""
        try:
            import re
            miles_match = re.search(r'(\d+(?:,\d+)*)', miles_text.replace(',', ''))
            return int(miles_match.group(1)) if miles_match else 0
        except Exception:
            return 0
    
    def _classify_flight_type(self, flight_data: Dict[str, Any]) -> str:
        """Classify flight type based on available information."""
        try:
            # Check for layovers
            if "layovers" in flight_data:
                layover_info = flight_data["layovers"]
                if isinstance(layover_info, dict) and layover_info.get("type") == "direct":
                    return "direct"
                else:
                    return "connecting"
            
            # Check duration (rough estimate)
            if "duration_minutes" in flight_data:
                duration = flight_data["duration_minutes"]
                if duration > 12 * 60:  # More than 12 hours likely long-haul
                    return "long_haul"
                elif duration > 4 * 60:  # More than 4 hours likely medium-haul
                    return "medium_haul"
                else:
                    return "short_haul"
            
            return "unknown"
            
        except Exception:
            return "unknown"
    
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
                    raise ValueError(f"Invalid airport code format for {field}: {airport_code}")
        
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
            if price < 50 or price > 50000:  # Reasonable range for international flights
                return False
        
        # Check if duration is reasonable
        if "duration_minutes" in flight_data:
            duration = flight_data["duration_minutes"]
            if duration < 30 or duration > 24 * 60:  # 30 minutes to 24 hours
                return False
        
        return True 