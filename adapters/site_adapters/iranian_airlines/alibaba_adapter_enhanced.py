"""
Enhanced Alibaba Adapter using Unified Site Adapter
Demonstrates migration to standardized adapter architecture with enhanced features
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError

from adapters.base_adapters.unified_site_adapter import UnifiedSiteAdapter
from adapters.base_adapters.enhanced_error_handler import (
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    error_handler_decorator
)


class EnhancedAlibabaAdapter(UnifiedSiteAdapter):
    """
    Enhanced Alibaba adapter with unified architecture and comprehensive features:
    
    - Automatic error handling and recovery
    - Persian text processing
    - Enhanced monitoring and metrics
    - Security and authorization
    - Rate limiting compliance
    - Data encryption for sensitive information
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Default configuration for Alibaba
        default_config = {
            'name': 'alibaba',
            'base_url': 'https://www.alibaba.ir',
            'search_url': 'https://www.alibaba.ir/flights',
            'version': '2.0.0',
            'supports_persian': True,
            'rate_limiting': {
                'requests_per_minute': 10,
                'delay_seconds': 6,
                'burst_limit': 20
            },
            'extraction_config': {
                'search_form': {
                    'origin_field': '#origin',
                    'destination_field': '#destination',
                    'departure_date_field': '#departure-date',
                    'return_date_field': '#return-date',
                    'passenger_count_field': '#passengers',
                    'cabin_class_field': '#cabin-class',
                    'search_button': '#search-flights'
                },
                'results_parsing': {
                    'flight_container': '.flight-item',
                    'flight_number': '.flight-number',
                    'airline': '.airline-name',
                    'departure_time': '.departure-time',
                    'arrival_time': '.arrival-time',
                    'duration': '.flight-duration',
                    'price': '.price-amount',
                    'stops': '.stops-info'
                }
            },
            'persian_processing': {
                'enable_text_normalization': True,
                'enable_date_conversion': True,
                'enable_number_conversion': True
            }
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Initialize unified adapter
        super().__init__('alibaba', default_config)
        
        # Alibaba-specific properties
        self.persian_months = {
            'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03',
            'تیر': '04', 'مرداد': '05', 'شهریور': '06',
            'مهر': '07', 'آبان': '08', 'آذر': '09',
            'دی': '10', 'بهمن': '11', 'اسفند': '12'
        }
        
        self.logger.info("Enhanced Alibaba adapter initialized with unified architecture")

    # Implement abstract methods from UnifiedSiteAdapter
    async def _validate_site_specific_params(self, params: Dict[str, Any]):
        """Validate Alibaba-specific parameters"""
        try:
            # Validate Persian airport codes
            if 'origin' in params:
                await self._validate_persian_airport_code(params['origin'])
            
            if 'destination' in params:
                await self._validate_persian_airport_code(params['destination'])
            
            # Validate Persian date format if provided
            if 'departure_date' in params:
                await self._validate_persian_date(params['departure_date'])
            
            if 'return_date' in params:
                await self._validate_persian_date(params['return_date'])
            
            # Validate passenger count
            if 'passengers' in params:
                passenger_count = int(params['passengers'])
                if passenger_count < 1 or passenger_count > 9:
                    raise ValueError("Passenger count must be between 1 and 9")
            
        except Exception as e:
            self.logger.error(f"Alibaba parameter validation failed: {e}")
            raise

    async def _apply_site_specific_standardization(self, standardized: Dict[str, Any], raw: Dict[str, Any]):
        """Apply Alibaba-specific data standardization"""
        try:
            # Convert Persian numbers to English
            if 'price' in raw:
                standardized['price'] = self._persian_to_english_numbers(str(raw['price']))
            
            # Standardize Persian time format
            if 'departure_time' in raw:
                standardized['departure_time'] = self._standardize_persian_time(raw['departure_time'])
            
            if 'arrival_time' in raw:
                standardized['arrival_time'] = self._standardize_persian_time(raw['arrival_time'])
            
            # Convert Persian duration to minutes
            if 'duration' in raw:
                standardized['duration_minutes'] = self._parse_persian_duration(raw['duration'])
            
            # Add Alibaba-specific metadata
            standardized['booking_url'] = raw.get('booking_url', '')
            standardized['refundable'] = raw.get('refundable', False)
            standardized['baggage_info'] = raw.get('baggage_info', '')
            
        except Exception as e:
            self.logger.error(f"Alibaba standardization failed: {e}")

    # Override methods from base classes for Alibaba-specific behavior
    @error_handler_decorator(
        operation_name="navigate_to_search",
        category=ErrorCategory.NAVIGATION,
        severity=ErrorSeverity.MEDIUM,
        max_retries=3
    )
    async def _navigate_to_search_page(self) -> None:
        """Navigate to Alibaba search page with Persian support"""
        try:
            await self.page.goto(self.search_url, wait_until="networkidle")
            
            # Handle Alibaba-specific elements
            await self._handle_alibaba_cookie_consent()
            await self._set_persian_language()
            await self._handle_promotional_popups()
            
            # Wait for search form to be ready
            await self.page.wait_for_selector('#origin', timeout=10000)
            
            self.logger.debug("Successfully navigated to Alibaba search page")
            
        except Exception as e:
            self.logger.error(f"Navigation to Alibaba search page failed: {e}")
            raise

    @error_handler_decorator(
        operation_name="fill_search_form",
        category=ErrorCategory.FORM_FILLING,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fill Alibaba search form with Persian text processing"""
        try:
            extraction_config = self.site_config['extraction_config']['search_form']
            
            # Fill origin city
            if 'origin' in search_params:
                origin_text = self._process_persian_airport_code(search_params['origin'])
                await self._fill_autocomplete_field(
                    extraction_config['origin_field'],
                    origin_text,
                    '.origin-suggestions'
                )
            
            # Fill destination city
            if 'destination' in search_params:
                destination_text = self._process_persian_airport_code(search_params['destination'])
                await self._fill_autocomplete_field(
                    extraction_config['destination_field'],
                    destination_text,
                    '.destination-suggestions'
                )
            
            # Fill departure date
            if 'departure_date' in search_params:
                persian_date = self._convert_to_persian_date(search_params['departure_date'])
                await self._fill_date_field(
                    extraction_config['departure_date_field'],
                    persian_date
                )
            
            # Fill return date if provided
            if search_params.get('return_date'):
                persian_return_date = self._convert_to_persian_date(search_params['return_date'])
                await self._fill_date_field(
                    extraction_config['return_date_field'],
                    persian_return_date
                )
            
            # Set passenger count
            if 'passengers' in search_params:
                await self._set_passenger_count(search_params['passengers'])
            
            # Set cabin class
            if 'cabin_class' in search_params:
                await self._set_cabin_class(search_params['cabin_class'])
            
            # Submit search
            await self.page.click(extraction_config['search_button'])
            
            self.logger.debug("Search form filled successfully")
            
        except Exception as e:
            self.logger.error(f"Form filling failed: {e}")
            raise

    @error_handler_decorator(
        operation_name="extract_flight_results",
        category=ErrorCategory.PARSING,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """Extract flight results from Alibaba with Persian text processing"""
        try:
            # Wait for results to load
            await self.page.wait_for_selector('.flight-item', timeout=30000)
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract flights
            extraction_config = self.site_config['extraction_config']['results_parsing']
            flight_elements = soup.select(extraction_config['flight_container'])
            
            flights = []
            for element in flight_elements:
                try:
                    flight = await self._parse_alibaba_flight_element(element, extraction_config)
                    if flight and self._validate_flight_data(flight):
                        flights.append(flight)
                except Exception as e:
                    self.logger.warning(f"Failed to parse flight element: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(flights)} flights from Alibaba")
            return flights
            
        except Exception as e:
            self.logger.error(f"Flight extraction failed: {e}")
            raise

    async def _parse_alibaba_flight_element(self, element, config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse individual flight element from Alibaba"""
        try:
            flight = {}
            
            # Extract basic flight information
            flight['flight_number'] = self._extract_text_safe(element, config['flight_number'])
            flight['airline'] = self._extract_text_safe(element, config['airline'])
            flight['departure_time'] = self._extract_text_safe(element, config['departure_time'])
            flight['arrival_time'] = self._extract_text_safe(element, config['arrival_time'])
            flight['duration'] = self._extract_text_safe(element, config['duration'])
            flight['stops'] = self._parse_stops_info(self._extract_text_safe(element, config['stops']))
            
            # Extract and process price
            price_text = self._extract_text_safe(element, config['price'])
            flight['price'] = self._extract_persian_price(price_text)
            flight['currency'] = 'IRR'  # Iranian Rial
            
            # Extract additional Alibaba-specific information
            flight['booking_url'] = self._extract_booking_url(element)
            flight['refundable'] = self._check_refundable_status(element)
            flight['baggage_info'] = self._extract_baggage_info(element)
            flight['meal_service'] = self._check_meal_service(element)
            
            # Add extraction metadata
            flight['extracted_at'] = datetime.now().isoformat()
            flight['extraction_method'] = 'enhanced_persian_parsing'
            
            return flight
            
        except Exception as e:
            self.logger.error(f"Flight element parsing failed: {e}")
            return {}

    # Alibaba-specific helper methods
    async def _handle_alibaba_cookie_consent(self):
        """Handle Alibaba cookie consent dialog"""
        try:
            cookie_selectors = [
                'button[data-testid="cookie-accept"]',
                '.cookie-consent-accept',
                'button:has-text("قبول")',
                'button:has-text("موافقم")'
            ]
            
            for selector in cookie_selectors:
                try:
                    await self.page.click(selector, timeout=2000)
                    self.logger.debug("Cookie consent handled")
                    return
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Cookie consent handling: {e}")

    async def _set_persian_language(self):
        """Set interface language to Persian"""
        try:
            language_selector = '.language-selector'
            persian_option = 'option[value="fa"]'
            
            if await self.page.is_visible(language_selector):
                await self.page.select_option(language_selector, 'fa')
                await self.page.wait_for_timeout(1000)
                
        except Exception as e:
            self.logger.debug(f"Language setting: {e}")

    async def _handle_promotional_popups(self):
        """Handle promotional popups and overlays"""
        try:
            popup_selectors = [
                '.popup-close',
                '.modal-close',
                '.overlay-close',
                'button:has-text("بستن")',
                'button:has-text("متوجه شدم")'
            ]
            
            for selector in popup_selectors:
                try:
                    if await self.page.is_visible(selector):
                        await self.page.click(selector, timeout=1000)
                        await self.page.wait_for_timeout(500)
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Popup handling: {e}")

    async def _fill_autocomplete_field(self, selector: str, text: str, suggestions_selector: str):
        """Fill autocomplete field and select suggestion"""
        try:
            # Clear and type text
            await self.page.fill(selector, text)
            await self.page.wait_for_timeout(1000)
            
            # Wait for suggestions and select first one
            await self.page.wait_for_selector(suggestions_selector, timeout=5000)
            suggestions = await self.page.query_selector_all(f"{suggestions_selector} li")
            
            if suggestions:
                await suggestions[0].click()
                await self.page.wait_for_timeout(500)
                
        except Exception as e:
            self.logger.warning(f"Autocomplete field filling failed: {e}")

    async def _fill_date_field(self, selector: str, date_text: str):
        """Fill Persian date field"""
        try:
            await self.page.click(selector)
            await self.page.wait_for_timeout(500)
            
            # Clear existing value and enter new date
            await self.page.fill(selector, date_text)
            await self.page.press(selector, 'Enter')
            await self.page.wait_for_timeout(500)
            
        except Exception as e:
            self.logger.warning(f"Date field filling failed: {e}")

    async def _set_passenger_count(self, count: int):
        """Set passenger count"""
        try:
            passenger_selector = '#passengers'
            await self.page.click(passenger_selector)
            
            # Adjust passenger count
            for i in range(count - 1):  # Default is usually 1
                increase_button = '.passenger-increase'
                if await self.page.is_visible(increase_button):
                    await self.page.click(increase_button)
                    await self.page.wait_for_timeout(200)
                    
        except Exception as e:
            self.logger.warning(f"Passenger count setting failed: {e}")

    async def _set_cabin_class(self, cabin_class: str):
        """Set cabin class"""
        try:
            cabin_selector = '#cabin-class'
            class_mapping = {
                'economy': 'اکونومی',
                'business': 'بیزینس',
                'first': 'فرست کلاس'
            }
            
            persian_class = class_mapping.get(cabin_class.lower(), 'اکونومی')
            await self.page.select_option(cabin_selector, label=persian_class)
            
        except Exception as e:
            self.logger.warning(f"Cabin class setting failed: {e}")

    # Persian text processing methods
    def _process_persian_airport_code(self, code: str) -> str:
        """Process airport code for Persian interface"""
        # Mapping of common airport codes to Persian names
        airport_mapping = {
            'THR': 'تهران',
            'IFN': 'اصفهان',
            'SYZ': 'شیراز',
            'MHD': 'مشهد',
            'AWZ': 'اهواز',
            'TBZ': 'تبریز',
            'KER': 'کرمان',
            'BND': 'بندرعباس'
        }
        
        return airport_mapping.get(code.upper(), code)

    def _convert_to_persian_date(self, date_str: str) -> str:
        """Convert Gregorian date to Persian calendar"""
        try:
            # This is a simplified conversion
            # In a real implementation, you'd use a proper Persian calendar library
            from datetime import datetime
            import jdatetime
            
            gregorian_date = datetime.strptime(date_str, '%Y-%m-%d')
            persian_date = jdatetime.date.fromgregorian(date=gregorian_date.date())
            
            return persian_date.strftime('%Y/%m/%d')
            
        except Exception as e:
            self.logger.warning(f"Persian date conversion failed: {e}")
            return date_str

    def _persian_to_english_numbers(self, text: str) -> str:
        """Convert Persian numbers to English"""
        persian_to_english = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        
        for persian, english in persian_to_english.items():
            text = text.replace(persian, english)
        
        return text

    def _standardize_persian_time(self, time_str: str) -> str:
        """Standardize Persian time format"""
        try:
            # Convert Persian numbers to English
            time_str = self._persian_to_english_numbers(time_str)
            
            # Handle common Persian time formats
            if ':' in time_str:
                return time_str
            elif 'ساعت' in time_str:
                # Extract time from Persian text
                import re
                time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
                if time_match:
                    return f"{time_match.group(1)}:{time_match.group(2)}"
            
            return time_str
            
        except Exception as e:
            self.logger.warning(f"Time standardization failed: {e}")
            return time_str

    def _parse_persian_duration(self, duration_str: str) -> int:
        """Parse Persian duration string to minutes"""
        try:
            # Convert Persian numbers
            duration_str = self._persian_to_english_numbers(duration_str)
            
            import re
            
            # Look for hour and minute patterns
            hour_match = re.search(r'(\d+)\s*ساعت', duration_str)
            minute_match = re.search(r'(\d+)\s*دقیقه', duration_str)
            
            hours = int(hour_match.group(1)) if hour_match else 0
            minutes = int(minute_match.group(1)) if minute_match else 0
            
            return hours * 60 + minutes
            
        except Exception as e:
            self.logger.warning(f"Duration parsing failed: {e}")
            return 0

    def _extract_persian_price(self, price_text: str) -> float:
        """Extract price from Persian text"""
        try:
            # Convert Persian numbers to English
            price_text = self._persian_to_english_numbers(price_text)
            
            # Remove Persian currency symbols and separators
            import re
            price_text = re.sub(r'[ریال|تومان|,|\s]', '', price_text)
            
            # Extract numeric value
            price_match = re.search(r'(\d+)', price_text)
            if price_match:
                return float(price_match.group(1))
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"Price extraction failed: {e}")
            return 0.0

    def _extract_text_safe(self, element, selector: str) -> str:
        """Safely extract text from element"""
        try:
            found_element = element.select_one(selector)
            return found_element.get_text(strip=True) if found_element else ''
        except Exception:
            return ''

    def _parse_stops_info(self, stops_text: str) -> int:
        """Parse stops information"""
        try:
            if 'مستقیم' in stops_text or 'direct' in stops_text.lower():
                return 0
            elif '۱' in stops_text or '1' in stops_text:
                return 1
            elif '۲' in stops_text or '2' in stops_text:
                return 2
            else:
                return 0
        except Exception:
            return 0

    def _extract_booking_url(self, element) -> str:
        """Extract booking URL from flight element"""
        try:
            booking_link = element.select_one('a.booking-link, .book-now')
            if booking_link and booking_link.get('href'):
                return booking_link['href']
            return ''
        except Exception:
            return ''

    def _check_refundable_status(self, element) -> bool:
        """Check if flight is refundable"""
        try:
            refund_text = element.get_text()
            return 'قابل استرداد' in refund_text or 'refundable' in refund_text.lower()
        except Exception:
            return False

    def _extract_baggage_info(self, element) -> str:
        """Extract baggage information"""
        try:
            baggage_element = element.select_one('.baggage-info, .luggage-info')
            return baggage_element.get_text(strip=True) if baggage_element else ''
        except Exception:
            return ''

    def _check_meal_service(self, element) -> bool:
        """Check if meal service is included"""
        try:
            meal_text = element.get_text()
            return 'سرویس غذا' in meal_text or 'meal' in meal_text.lower()
        except Exception:
            return False

    # Validation methods
    async def _validate_persian_airport_code(self, code: str):
        """Validate Persian airport code"""
        if len(code) != 3:
            raise ValueError(f"Invalid airport code format: {code}")

    async def _validate_persian_date(self, date_str: str):
        """Validate Persian date format"""
        try:
            # Simple validation - in practice you'd use proper Persian date validation
            if not date_str or len(date_str) < 8:
                raise ValueError(f"Invalid date format: {date_str}")
        except Exception as e:
            raise ValueError(f"Date validation failed: {e}")

    def _get_required_search_fields(self) -> List[str]:
        """Get required search fields for Alibaba"""
        return ['origin', 'destination', 'departure_date']

    def get_adapter_info(self) -> Dict[str, Any]:
        """Get Alibaba adapter information"""
        info = super().get_adapter_config()
        info.update({
            'adapter_type': 'enhanced_persian_adapter',
            'supports_features': [
                'persian_text_processing',
                'error_recovery',
                'rate_limiting',
                'monitoring',
                'encryption',
                'authorization'
            ],
            'persian_calendar_support': True,
            'autocomplete_support': True,
            'real_time_pricing': True
        })
        return info


# Factory function for creating enhanced Alibaba adapter
def create_enhanced_alibaba_adapter(config: Optional[Dict[str, Any]] = None) -> EnhancedAlibabaAdapter:
    """
    Create enhanced Alibaba adapter with unified architecture
    """
    return EnhancedAlibabaAdapter(config)


# Usage example
async def example_usage():
    """Example of using the enhanced Alibaba adapter"""
    try:
        # Create adapter
        adapter = create_enhanced_alibaba_adapter()
        
        # Search parameters
        search_params = {
            'origin': 'THR',
            'destination': 'MHD',
            'departure_date': '2024-02-15',
            'passengers': 1,
            'cabin_class': 'economy'
        }
        
        # User context for authorization
        user_context = {
            'user': None,  # Would contain actual user object
            'session_id': 'example_session'
        }
        
        # Perform search
        async with adapter:
            results = await adapter.crawl_flights(search_params, user_context)
            
            print(f"Found {len(results)} flights")
            for flight in results[:3]:  # Show first 3 results
                print(f"Flight: {flight['flight_number']} - {flight['airline']}")
                print(f"Price: {flight['price']} {flight['currency']}")
                print(f"Duration: {flight.get('duration_minutes', 0)} minutes")
                print("---")
        
        # Get adapter health
        health = await adapter.get_adapter_health()
        print(f"Adapter health: {health['status']}")
        
    except Exception as e:
        print(f"Example usage failed: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage()) 