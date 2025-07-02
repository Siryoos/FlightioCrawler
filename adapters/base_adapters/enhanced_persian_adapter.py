"""
Enhanced Persian airline adapter with minimal code duplication.
"""

from typing import Dict, List, Optional, Any
from .enhanced_base_crawler import EnhancedBaseCrawler

# Fix import path
try:
    from data.transformers.persian_text_processor import PersianTextProcessor
except ImportError:
    try:
        from utils.persian_text_processor import PersianTextProcessor
    except ImportError:
        # Fallback - create a dummy processor
        class PersianTextProcessor:
            def process_text(self, text): return text
            def process_date(self, date): return date
            def process_price(self, price): return price
            def extract_number(self, text): return text
            def convert_persian_numbers(self, text): return text
            def normalize_airline_name(self, text): return text
            def clean_flight_number(self, text): return text
            def parse_time(self, text): return text
            def normalize_seat_class(self, text): return text
            def extract_duration(self, text): return 0


class EnhancedPersianAdapter(EnhancedBaseCrawler):
    """
    Enhanced base class for Persian airline adapters.
    
    This class eliminates all initialization duplication and provides
    Persian text processing capabilities with:
    - Automatic Persian text processor initialization
    - Standard form filling for Persian sites
    - Persian date and number handling
    - Enhanced error handling for Persian content
    - Common validation for Iranian flights
    """
    
    def _initialize_adapter(self) -> None:
        """Initialize Persian text processor and Persian-specific components."""
        self.persian_processor = PersianTextProcessor()
        
        # Persian-specific configuration
        self.default_currency = "IRR"
        
        # Persian date format mappings
        self.persian_months = {
            'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03',
            'تیر': '04', 'مرداد': '05', 'شهریور': '06',
            'مهر': '07', 'آبان': '08', 'آذر': '09',
            'دی': '10', 'بهمن': '11', 'اسفند': '12'
        }
        
        # Persian number mappings
        self.persian_to_english_numbers = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        
        # Common Persian airline mappings
        self.airline_name_mappings = {
            'ایران ایر': 'Iran Air',
            'ماهان': 'Mahan Air',
            'آسمان': 'Aseman Airlines',
            'کاسپین': 'Caspian Airlines',
            'قشم ایر': 'Qeshm Air',
            'کیش ایر': 'Kish Air',
            'تابان': 'Taban Air',
            'وارش': 'Varesh Airlines',
            'کارون': 'Karun Airlines',
            'سپهران': 'Sepehran Airlines',
            'پویا ایر': 'Pouya Air',
            'عطا': 'Ata Airlines'
        }
    
    async def _handle_language_selection(self) -> None:
        """Handle language selection for Persian sites (usually already in Persian)."""
        try:
            # Most Persian sites are already in Persian, but some may have language options
            language_config = self.config.get("extraction_config", {}).get("language", {})
            
            if language_config.get("selector"):
                # Try to set language to Persian/Farsi
                await self.page.click(language_config["selector"], timeout=5000)
                
                if language_config.get("persian_option"):
                    await self.page.click(language_config["persian_option"], timeout=5000)
                    self.logger.debug("Language set to Persian")
                    
        except Exception as e:
            self.logger.debug(f"Language selection not needed or failed: {e}")
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """
        Fill search form for Persian airlines with enhanced text processing.
        
        Standard implementation with Persian text processing.
        Override only if needed.
        """
        try:
            form_config = self.config.get("extraction_config", {}).get("search_form", {})
            
            if not form_config:
                raise ValueError("No search form configuration found")
            
            # Origin with Persian processing
            if "origin_field" in form_config:
                await self._fill_airport_field_persian(
                    form_config["origin_field"],
                    search_params["origin"],
                    form_config.get("origin_suggestion"),
                    "origin"
                )
            
            # Destination with Persian processing
            if "destination_field" in form_config:
                await self._fill_airport_field_persian(
                    form_config["destination_field"],
                    search_params["destination"],
                    form_config.get("destination_suggestion"),
                    "destination"
                )
            
            # Date with Persian date processing
            if "date_field" in form_config:
                await self._fill_date_field_persian(search_params["departure_date"], form_config)
            
            # Return date if applicable
            if "return_date" in search_params and "return_date_field" in form_config:
                return_date = self._process_persian_date(search_params["return_date"])
                await self.page.fill(form_config["return_date_field"], return_date)
            
            # Passengers with Persian number processing
            await self._fill_passenger_fields_persian(search_params, form_config)
            
            # Seat class with Persian processing
            if "seat_class" in search_params and "class_field" in form_config:
                await self._fill_seat_class_persian(search_params["seat_class"], form_config)
            
            # Trip type with Persian processing
            if "trip_type" in search_params and "trip_type_field" in form_config:
                await self._fill_trip_type_persian(search_params["trip_type"], form_config)
            
            # Additional Persian-specific fields
            await self._fill_additional_fields_persian(search_params, form_config)
            
            # Submit form
            await self._submit_search_form_persian(form_config)
            
        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise
    
    async def _fill_airport_field_persian(
        self,
        field_selector: str,
        airport_code: str,
        suggestion_selector: Optional[str],
        field_type: str
    ) -> None:
        """Fill airport field with Persian text processing."""
        try:
            # Process airport code for Persian sites
            processed_airport = self._process_airport_code_persian(airport_code)
            
            # Clear field first
            await self.page.fill(field_selector, "")
            
            # Type processed airport code
            await self.page.type(field_selector, processed_airport, delay=150)
            
            # Handle Persian autocomplete suggestions
            if suggestion_selector:
                try:
                    await self.page.wait_for_selector(suggestion_selector, timeout=5000)
                    
                    # Click first suggestion or exact match
                    suggestions = await self.page.query_selector_all(suggestion_selector)
                    if suggestions:
                        # Try to find match with both Persian and English names
                        for suggestion in suggestions:
                            text = await suggestion.text_content()
                            if (airport_code.upper() in text.upper() or 
                                processed_airport in text):
                                await suggestion.click()
                                break
                        else:
                            # Click first suggestion if no exact match
                            await suggestions[0].click()
                            
                except Exception as e:
                    self.logger.debug(f"Persian autocomplete handling failed for {field_type}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error filling Persian {field_type} field: {e}")
            raise
    
    def _process_airport_code_persian(self, airport_code: str) -> str:
        """Process airport code for Persian sites."""
        # Map common airport codes to Persian names if needed
        persian_airport_mappings = {
            'THR': 'تهران',
            'IKA': 'امام خمینی',
            'MHD': 'مشهد',
            'ISF': 'اصفهان',
            'SYZ': 'شیراز',
            'TBZ': 'تبریز',
            'AWZ': 'اهواز',
            'KER': 'کرمان',
            'BND': 'بندرعباس',
            'ZAH': 'زاهدان',
            'KIH': 'کیش',
            'BUZ': 'بوشهر'
        }
        
        # Return Persian name if available, otherwise return original code
        return persian_airport_mappings.get(airport_code.upper(), airport_code)
    
    async def _fill_date_field_persian(self, date_str: str, form_config: Dict[str, Any]) -> None:
        """Fill date field with Persian date processing."""
        try:
            processed_date = self._process_persian_date(date_str)
            await self.page.fill(form_config["date_field"], processed_date)
        except Exception as e:
            self.logger.error(f"Error filling Persian date field: {e}")
            raise
    
    def _process_persian_date(self, date_str: str) -> str:
        """Process date for Persian sites."""
        try:
            # Convert Persian/Jalali date if needed
            processed_date = self.persian_processor.process_date(date_str)
            
            # Additional processing for common Persian date formats
            if processed_date:
                return processed_date
            
            # If processor fails, try manual conversion
            return self._manual_date_conversion(date_str)
            
        except Exception:
            return date_str
    
    def _manual_date_conversion(self, date_str: str) -> str:
        """Manual date conversion for Persian formats."""
        try:
            # Handle different input formats and convert to site-expected format
            # This is a simplified implementation - extend as needed
            
            # Convert Persian numbers to English
            converted = date_str
            for persian, english in self.persian_to_english_numbers.items():
                converted = converted.replace(persian, english)
            
            return converted
            
        except Exception:
            return date_str
    
    async def _fill_passenger_fields_persian(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
        """Fill passenger fields with Persian number processing."""
        try:
            # Handle passengers field
            if "passengers" in search_params and "passengers_field" in form_config:
                passenger_count = str(search_params["passengers"])
                # Convert to Persian numbers if site expects them
                persian_count = self._convert_to_persian_numbers(passenger_count)
                await self.page.select_option(form_config["passengers_field"], persian_count)
            
            # Handle detailed passenger breakdown
            passenger_fields = {
                "adults": "adults_field",
                "children": "children_field",
                "infants": "infants_field"
            }
            
            for passenger_type, field_key in passenger_fields.items():
                if passenger_type in search_params and field_key in form_config:
                    count = str(search_params[passenger_type])
                    persian_count = self._convert_to_persian_numbers(count)
                    await self.page.select_option(form_config[field_key], persian_count)
                    
        except Exception as e:
            self.logger.warning(f"Could not set Persian passenger information: {e}")
    
    def _convert_to_persian_numbers(self, text: str) -> str:
        """Convert English numbers to Persian numbers."""
        english_to_persian = {v: k for k, v in self.persian_to_english_numbers.items()}
        
        result = text
        for english, persian in english_to_persian.items():
            result = result.replace(english, persian)
        
        return result
    
    async def _fill_seat_class_persian(self, seat_class: str, form_config: Dict[str, Any]) -> None:
        """Fill seat class with Persian mapping."""
        try:
            processed_class = self._map_seat_class_persian(seat_class)
            await self.page.select_option(form_config["class_field"], processed_class)
        except Exception as e:
            self.logger.warning(f"Could not set Persian seat class: {e}")
    
    def _map_seat_class_persian(self, seat_class: str) -> str:
        """Map seat class to Persian equivalents."""
        persian_class_mappings = {
            'economy': 'اکونومی',
            'business': 'بیزینس', 
            'first': 'فرست کلاس',
            'premium_economy': 'اکونومی ممتاز'
        }
        
        # Try English to Persian mapping first
        if seat_class.lower() in persian_class_mappings:
            return persian_class_mappings[seat_class.lower()]
        
        # If already in Persian or unknown, return as-is
        return seat_class
    
    async def _fill_trip_type_persian(self, trip_type: str, form_config: Dict[str, Any]) -> None:
        """Fill trip type with Persian mapping."""
        try:
            processed_trip_type = self._map_trip_type_persian(trip_type)
            
            trip_type_field = form_config["trip_type_field"]
            if trip_type_field.startswith('select'):
                await self.page.select_option(trip_type_field, processed_trip_type)
            else:
                await self.page.click(f"{trip_type_field}[value='{processed_trip_type}']")
                
        except Exception as e:
            self.logger.warning(f"Could not set Persian trip type: {e}")
    
    def _map_trip_type_persian(self, trip_type: str) -> str:
        """Map trip type to Persian equivalents."""
        persian_trip_mappings = {
            'oneway': 'یک طرفه',
            'roundtrip': 'رفت و برگشت',
            'multicity': 'چند شهره'
        }
        
        if trip_type.lower() in persian_trip_mappings:
            return persian_trip_mappings[trip_type.lower()]
        
        return trip_type
    
    async def _fill_additional_fields_persian(self, search_params: Dict[str, Any], form_config: Dict[str, Any]) -> None:
        """Fill additional Persian-specific fields."""
        try:
            # Charter flight preference
            if search_params.get("charter_preferred") and "charter_field" in form_config:
                await self.page.check(form_config["charter_field"])
            
            # Domestic flight preference
            if search_params.get("domestic_only") and "domestic_field" in form_config:
                await self.page.check(form_config["domestic_field"])
            
            # Preferred Iranian airline
            if search_params.get("preferred_airline") and "preferred_airline_field" in form_config:
                airline = search_params["preferred_airline"]
                persian_airline = self._map_airline_to_persian(airline)
                await self.page.select_option(form_config["preferred_airline_field"], persian_airline)
                
        except Exception as e:
            self.logger.debug(f"Could not set additional Persian fields: {e}")
    
    def _map_airline_to_persian(self, airline: str) -> str:
        """Map airline name to Persian equivalent."""
        return self.airline_name_mappings.get(airline, airline)
    
    async def _submit_search_form_persian(self, form_config: Dict[str, Any]) -> None:
        """Submit search form with Persian site considerations."""
        try:
            # Get submit button selector
            submit_selector = form_config.get("submit_button", "button[type='submit']")
            
            # Look for Persian submit button text if no specific selector
            if submit_selector == "button[type='submit']":
                persian_submit_selectors = [
                    'button:has-text("جستجو")',
                    'button:has-text("یافتن پرواز")',
                    'input[value="جستجو"]',
                    '.search-button',
                    '#search-btn'
                ]
                
                for selector in persian_submit_selectors:
                    try:
                        await self.page.click(selector, timeout=2000)
                        break
                    except:
                        continue
                else:
                    # Fallback to original selector
                    await self.page.click(submit_selector)
            else:
                await self.page.click(submit_selector)
            
            # Wait for results with Persian site considerations
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            
            # Additional wait for Persian sites (often slower)
            import asyncio
            await asyncio.sleep(3)
            
        except Exception as e:
            self.logger.error(f"Error submitting Persian search form: {e}")
            raise
    
    def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse flight element for Persian airlines with enhanced text processing.
        
        Standard implementation with Persian text processing.
        Override to add airline-specific fields.
        """
        try:
            config = self.config.get("extraction_config", {}).get("results_parsing", {})
            
            if not config:
                raise ValueError("No results parsing configuration found")
            
            # Extract basic fields with Persian processing
            flight_data = {}
            
            # Core flight information with Persian text processing
            core_fields = {
                "airline": "airline",
                "flight_number": "flight_number",
                "departure_time": "departure_time", 
                "arrival_time": "arrival_time",
                "duration": "duration",
                "price": "price",
                "seat_class": "seat_class"
            }
            
            for field, selector_key in core_fields.items():
                if selector_key in config:
                    raw_value = self._extract_text(element, config[selector_key])
                    if raw_value:
                        if field == "price":
                            flight_data[field] = self._extract_price_persian(raw_value)
                        elif field == "duration":
                            flight_data[field] = self.persian_processor.process_text(raw_value)
                            flight_data["duration_minutes"] = self._parse_duration_persian(raw_value)
                        elif field in ["departure_time", "arrival_time"]:
                            flight_data[field] = self._process_time_persian(raw_value)
                        elif field == "airline":
                            flight_data[field] = self._process_airline_name_persian(raw_value)
                        else:
                            flight_data[field] = self.persian_processor.process_text(raw_value)
            
            # Always set currency to IRR for Persian flights
            flight_data["currency"] = "IRR"
            
            # Extract optional fields with Persian processing
            self._extract_optional_fields_persian(element, flight_data, config)
            
            # Add flight classification
            flight_data["flight_type"] = self._classify_persian_flight(flight_data)
            
            # Add metadata
            flight_data["is_domestic"] = self._is_domestic_flight_persian(flight_data)
            
            return flight_data if flight_data.get("airline") else None
            
        except Exception as e:
            self.logger.error(f"Error parsing Persian flight element: {str(e)}")
            return None
    
    def _extract_price_persian(self, price_text: str) -> float:
        """Extract price from Persian text with enhanced processing."""
        try:
            # Use Persian processor first
            processed_price = self.persian_processor.process_price(price_text)
            if processed_price and processed_price > 0:
                return processed_price
            
            # Fallback to manual processing
            return self._manual_price_extraction_persian(price_text)
            
        except Exception:
            return self._manual_price_extraction_persian(price_text)
    
    def _manual_price_extraction_persian(self, price_text: str) -> float:
        """Manual price extraction for Persian text."""
        try:
            import re
            
            # Convert Persian numbers to English
            converted = price_text
            for persian, english in self.persian_to_english_numbers.items():
                converted = converted.replace(persian, english)
            
            # Remove Persian currency symbols and text
            persian_currency_terms = ['ریال', 'تومان', 'درهم', 'IRR', 'IRT']
            for term in persian_currency_terms:
                converted = converted.replace(term, '')
            
            # Extract numbers
            numbers = re.findall(r'[\d,]+', converted)
            if numbers:
                # Take the largest number (likely the price)
                price_str = max(numbers, key=len).replace(',', '')
                price = float(price_str)
                
                # Convert Toman to Rial if needed (multiply by 10)
                if 'تومان' in price_text:
                    price *= 10
                
                return price
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _process_time_persian(self, time_text: str) -> str:
        """Process Persian time text."""
        try:
            # Use Persian processor
            processed = self.persian_processor.parse_time(time_text)
            if processed:
                return processed
            
            # Manual processing
            converted = time_text
            for persian, english in self.persian_to_english_numbers.items():
                converted = converted.replace(persian, english)
            
            return converted.strip()
            
        except Exception:
            return time_text
    
    def _process_airline_name_persian(self, airline_text: str) -> str:
        """Process Persian airline name."""
        try:
            # Normalize airline name using processor
            normalized = self.persian_processor.normalize_airline_name(airline_text)
            if normalized:
                return normalized
            
            # Manual mapping
            for persian, english in self.airline_name_mappings.items():
                if persian in airline_text:
                    return english
            
            return airline_text.strip()
            
        except Exception:
            return airline_text
    
    def _parse_duration_persian(self, duration_text: str) -> int:
        """
        Parse Persian duration text to minutes with enhanced processing.
        
        Override for custom duration parsing logic.
        """
        try:
            # Use Persian processor first
            duration_minutes = self.persian_processor.extract_duration(duration_text)
            if duration_minutes > 0:
                return duration_minutes
            
            # Manual parsing for Persian duration formats
            return self._manual_duration_parsing_persian(duration_text)
            
        except Exception:
            return 0
    
    def _manual_duration_parsing_persian(self, duration_text: str) -> int:
        """Manual Persian duration parsing."""
        try:
            import re
            
            # Convert Persian numbers to English
            converted = duration_text
            for persian, english in self.persian_to_english_numbers.items():
                converted = converted.replace(persian, english)
            
            hours = 0
            minutes = 0
            
            # Persian hour patterns
            if "ساعت" in duration_text:
                hours_match = re.search(r'(\d+)\s*ساعت', converted)
                hours = int(hours_match.group(1)) if hours_match else 0
            
            # Persian minute patterns  
            if "دقیقه" in duration_text:
                minutes_part = converted.split("ساعت")[-1] if "ساعت" in converted else converted
                minutes_match = re.search(r'(\d+)\s*دقیقه', minutes_part)
                minutes = int(minutes_match.group(1)) if minutes_match else 0
            
            # Handle "و" (and) connector
            if "و" in duration_text and not minutes:
                parts = converted.split("و")
                if len(parts) == 2:
                    minutes_match = re.search(r'(\d+)', parts[1])
                    minutes = int(minutes_match.group(1)) if minutes_match else 0
            
            return hours * 60 + minutes
            
        except Exception:
            return 0
    
    def _extract_optional_fields_persian(
        self, 
        element, 
        flight_data: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> None:
        """Extract optional fields with Persian text processing."""
        optional_fields = [
            "fare_conditions", "available_seats", "aircraft_type",
            "baggage_allowance", "meal_service", "special_services",
            "refund_policy", "change_policy", "fare_rules",
            "booking_class", "fare_basis", "ticket_validity",
            "miles_earned", "miles_required", "promotion_code",
            "special_offers", "charter_info", "domestic_info"
        ]
        
        for field in optional_fields:
            if field in config:
                raw_text = self._extract_text(element, config[field])
                if raw_text:
                    processed_text = self.persian_processor.process_text(raw_text)
                    flight_data[field] = processed_text
    
    def _classify_persian_flight(self, flight_data: Dict[str, Any]) -> str:
        """Classify Persian flight type."""
        try:
            # Check if explicitly marked as charter
            if "charter_info" in flight_data:
                return "charter"
            
            # Check if domestic
            if flight_data.get("is_domestic"):
                return "domestic"
            
            # Check duration for classification
            if "duration_minutes" in flight_data:
                duration = flight_data["duration_minutes"]
                if duration > 8 * 60:  # More than 8 hours likely international
                    return "international"
                elif duration > 2 * 60:  # More than 2 hours likely domestic long-haul
                    return "domestic_long"
                else:
                    return "domestic_short"
            
            return "unknown"
            
        except Exception:
            return "unknown"
    
    def _is_domestic_flight_persian(self, flight_data: Dict[str, Any]) -> bool:
        """Check if flight is domestic based on Persian flight data."""
        try:
            # Check flight number patterns for Iranian domestic flights
            flight_number = flight_data.get("flight_number", "")
            
            # Common Iranian domestic airline prefixes
            domestic_prefixes = ['IR', 'W5', 'EP', 'ZV', 'QB', 'B9', 'Y9', 'I3']
            
            for prefix in domestic_prefixes:
                if flight_number.startswith(prefix):
                    return True
            
            # Check duration (domestic flights in Iran are typically under 3 hours)
            duration = flight_data.get("duration_minutes", 0)
            if duration > 0 and duration < 180:  # Less than 3 hours
                return True
            
            return False
            
        except Exception:
            return False
    
    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Persian flights."""
        return ["origin", "destination", "departure_date", "passengers", "seat_class"]
    
    def _validate_param_values(self, search_params: Dict[str, Any]) -> None:
        """Validate parameter values for Persian flights."""
        super()._validate_param_values(search_params)
        
        # Validate Iranian airport codes or Persian names
        for field in ["origin", "destination"]:
            if field in search_params:
                airport = search_params[field]
                if not self._is_valid_iranian_airport(airport):
                    self.logger.warning(f"Airport {airport} may not be valid for Persian flights")
    
    def _is_valid_iranian_airport(self, airport: str) -> bool:
        """Check if airport is valid for Iranian flights."""
        # Common Iranian airports
        iranian_airports = [
            'THR', 'IKA', 'MHD', 'ISF', 'SYZ', 'TBZ', 'AWZ', 'KER', 
            'BND', 'ZAH', 'KIH', 'BUZ', 'RAS', 'ABD', 'DEF', 'GBT',
            'تهران', 'مشهد', 'اصفهان', 'شیراز', 'تبریز', 'اهواز'
        ]
        
        return airport.upper() in [a.upper() for a in iranian_airports] or any(a in airport for a in iranian_airports)
    
    def _custom_flight_validation(self, flight_data: Dict[str, Any]) -> bool:
        """Custom validation for Persian flights."""
        # Check if price is reasonable for Iranian flights
        if "price" in flight_data:
            price = flight_data["price"]
            # Iranian domestic flights typically 500,000 to 50,000,000 Rial
            if price < 500000 or price > 50000000:
                return False
        
        # Check if duration is reasonable for Iranian flights
        if "duration_minutes" in flight_data:
            duration = flight_data["duration_minutes"]
            # Iranian flights typically 30 minutes to 10 hours
            if duration < 30 or duration > 600:
                return False
        
        return True
    
    def _extract_price(self, price_text: str) -> float:
        """
        Extract price from Persian text.
        
        Uses Persian text processor for price extraction.
        """
        return self._extract_price_persian(price_text) 