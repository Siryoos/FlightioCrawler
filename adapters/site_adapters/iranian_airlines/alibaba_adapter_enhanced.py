"""
Enhanced Alibaba Adapter using Unified Site Adapter
Unified version combining all best features from multiple Alibaba adapter implementations:
- Memory optimization and efficient resource management
- Performance profiling and monitoring
- Enhanced Persian text processing
- Automated form filling with intelligent retry
- Comprehensive error handling and recovery
"""

import asyncio
import logging
import gc
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

# Import performance profiling if available
try:
    from scripts.performance_profiler import profile_crawler_operation
except ImportError:
    # Fallback decorator if profiler not available
    def profile_crawler_operation(operation_name):
        def decorator(func):
            return func
        return decorator

# Import memory efficient caching if available
try:
    from utils.memory_efficient_cache import cached
except ImportError:
    # Fallback decorator if cache not available
    def cached(cache_name=None, ttl_seconds=None):
        def decorator(func):
            return func
        return decorator

# Import lazy loader if available
try:
    from utils.lazy_loader import get_config_loader
except ImportError:
    get_config_loader = None


class EnhancedAlibabaAdapter(UnifiedSiteAdapter):
    """
    Unified Enhanced Alibaba adapter combining all best features:
    
    Architecture Features:
    - Unified site adapter architecture
    - Automatic error handling and recovery
    - Persian text processing
    - Enhanced monitoring and metrics
    - Security and authorization
    - Rate limiting compliance
    - Data encryption for sensitive information
    
    Performance Features:
    - Memory optimization and efficient resource management
    - Performance profiling and monitoring
    - Lazy configuration loading
    - Efficient DOM parsing with minimal memory footprint
    - Proper resource cleanup
    
    Intelligence Features:
    - Automated form filling with intelligent retry
    - Enhanced Persian text processing
    - Advanced error recovery strategies
    - Intelligent airport and date mapping
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Load config lazily if not provided and lazy loader available
        if config is None and get_config_loader is not None:
            config_loader = get_config_loader()
            config = config_loader.load_site_config("alibaba")
        
        # Default configuration for Alibaba (enhanced with all features)
        default_config = {
            'name': 'alibaba',
            'base_url': 'https://www.alibaba.ir',
            'search_url': 'https://www.alibaba.ir/flights',
            'version': '3.0.0-unified',
            'supports_persian': True,
            'persian_calendar': True,
            'airport_mapping': True,
            'intelligent_retry': True,
            'max_form_retry_attempts': 3,
            'form_timeout_seconds': 30,
            'captcha_handling': True,
            'memory_optimization': True,
            'performance_profiling': True,
            
            # Enhanced rate limiting
            'rate_limiting': {
                'requests_per_minute': 8,
                'delay_seconds': 7,
                'burst_limit': 15,
                'adaptive_rate_limiting': True
            },
            
            # Comprehensive extraction configuration
            'extraction_config': {
                'search_form': {
                    'origin_field': '#departure-city, #origin',
                    'destination_field': '#arrival-city, #destination',
                    'departure_date_field': '#departure-date',
                    'return_date_field': '#return-date',
                    'passenger_count_field': '#passenger-count, #passengers',
                    'cabin_class_field': '#cabin-class',
                    'search_button': '.search-flight-btn, #search-flights'
                },
                'results_parsing': {
                    'flight_container': '.flight-item, .flight-card, .flight-result-item',
                    'flight_number': '.flight-number, .flight-code, .flight-num',
                    'airline': '.airline-name, .carrier, .airline',
                    'departure_time': '.departure-time, .dep-time, .depart',
                    'arrival_time': '.arrival-time, .arr-time, .arrive',
                    'duration': '.flight-duration, .duration, .flight-time',
                    'price': '.price-amount, .fare-price, .price, .fare',
                    'currency': '.currency, .price-currency',
                    'stops': '.stops-info, .stop-count, .stops',
                    'aircraft_type': '.aircraft-type, .plane-type, .aircraft',
                    'available_seats': '.seats-available, .availability',
                    'source_airline': '.source-airline, .original-carrier',
                    'discount_info': '.discount, .offer',
                    'booking_reference': '.booking-ref, .reference',
                    'baggage_allowance': '.baggage, .luggage',
                    'meal_service': '.meal, .catering'
                }
            },
            
            # Enhanced Persian processing
            'persian_processing': {
                'enable_text_normalization': True,
                'enable_date_conversion': True,
                'enable_number_conversion': True,
                'airport_name_mapping': True,
                'airline_name_mapping': True
            },
            
            # Data validation
            'data_validation': {
                'required_fields': ['flight_number', 'airline', 'departure_time', 'arrival_time', 'price'],
                'price_range': {'min': 100000, 'max': 20000000},  # IRR
                'duration_range': {'min': 30, 'max': 1440}  # minutes
            }
        }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Initialize unified adapter
        super().__init__('alibaba', default_config)
        
        # Cache frequently accessed config values for performance
        self._extraction_config = self.site_config['extraction_config']
        self._search_form_config = self._extraction_config.get('search_form', {})
        self._results_config = self._extraction_config.get('results_parsing', {})
        
        # Enhanced Alibaba-specific mappings
        self.alibaba_airport_mappings = {
            'THR': ['تهران', 'Tehran', 'IKA', 'خمینی'],
            'MHD': ['مشهد', 'Mashhad'],
            'SYZ': ['شیراز', 'Shiraz'],
            'IFN': ['اصفهان', 'Isfahan'],
            'TBZ': ['تبریز', 'Tabriz'],
            'AWZ': ['اهواز', 'Ahvaz'],
            'KER': ['کرمان', 'Kerman'],
            'BND': ['بندرعباس', 'Bandar Abbas'],
            'RAS': ['رشت', 'Rasht'],
            'KIH': ['کیش', 'Kish Island']
        }
        
        self.alibaba_cabin_classes = {
            'economy': 'اکونومی',
            'business': 'بیزینس', 
            'first': 'فرست',
            'premium_economy': 'پرمیوم اکونومی'
        }
        
        # Persian months mapping
        self.persian_months = {
            'فروردین': '01', 'اردیبهشت': '02', 'خرداد': '03',
            'تیر': '04', 'مرداد': '05', 'شهریور': '06',
            'مهر': '07', 'آبان': '08', 'آذر': '09',
            'دی': '10', 'بهمن': '11', 'اسفند': '12'
        }
        
        # Airline name mappings
        self.airline_mappings = {
            'ایران ایر': 'Iran Air',
            'ماهان': 'Mahan Air',
            'آسمان': 'Aseman Airlines',
            'کاسپین': 'Caspian Airlines',
            'تابان': 'Taban Air',
            'قشم ایر': 'Qeshm Air',
            'زاگرس': 'Zagros Airlines',
            'کارون': 'Karun Airlines',
            'سپهران': 'Sepehran Airlines',
            'وارش': 'Varesh Airlines',
            'عطا': 'Ata Airlines'
        }
        
        self.logger.info("Enhanced unified Alibaba adapter initialized with all features")

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
    @profile_crawler_operation("alibaba_navigate")
    async def _navigate_to_search_page(self) -> None:
        """Navigate to Alibaba search page with Persian support and memory optimization"""
        try:
            await self.page.goto(self.search_url, wait_until="networkidle")
            
            # Handle Alibaba-specific elements
            await self._handle_alibaba_cookie_consent()
            await self._set_persian_language()
            await self._handle_promotional_popups()
            
            # Optimize page for memory efficiency if enabled
            if self.site_config.get('memory_optimization', False):
                await self._optimize_page_for_memory()
            
            # Wait for search form to be ready (multiple selectors)
            selectors = ['#origin', '#departure-city', '.search-form']
            for selector in selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    break
                except:
                    continue
            
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
    @profile_crawler_operation("alibaba_fill_form")
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fill Alibaba search form with enhanced Persian text processing and intelligent retry"""
        try:
            # Use cached config for better performance
            extraction_config = self._search_form_config
            
            # Fill origin city with intelligent retry
            if 'origin' in search_params:
                origin_text = self._process_persian_airport_code(search_params['origin'])
                await self._fill_field_with_retry(
                    extraction_config['origin_field'],
                    origin_text,
                    max_retries=self.site_config.get('max_form_retry_attempts', 3)
                )
            
            # Fill destination city with intelligent retry
            if 'destination' in search_params:
                destination_text = self._process_persian_airport_code(search_params['destination'])
                await self._fill_field_with_retry(
                    extraction_config['destination_field'],
                    destination_text,
                    max_retries=self.site_config.get('max_form_retry_attempts', 3)
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
    @profile_crawler_operation("alibaba_extract_flights")
    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """Extract flight results from Alibaba with enhanced parsing and memory optimization"""
        try:
            # Wait for results to load with multiple selectors
            await self._wait_for_alibaba_results()
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract flights using cached config for performance
            extraction_config = self._results_config
            flight_elements = self._find_flight_containers(soup, extraction_config)
            
            flights = []
            for element in flight_elements:
                try:
                    flight = await self._parse_alibaba_flight_element(element, extraction_config)
                    if flight and self._validate_alibaba_flight_data(flight):
                        flights.append(flight)
                except Exception as e:
                    self.logger.debug(f"Failed to parse flight element: {e}")
                    continue
            
            # Clean up memory if enabled
            if self.site_config.get('memory_optimization', False):
                del soup
                gc.collect()
            
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

    # Memory optimization and performance methods
    async def _optimize_page_for_memory(self) -> None:
        """Optimize page for memory efficiency"""
        try:
            # Remove unnecessary elements to save memory
            await self.page.evaluate("""
                // Remove ads and heavy content
                const adsSelectors = ['.ad', '.advertisement', '.banner', '[class*="ad-"]'];
                adsSelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
                
                // Remove images not essential for data extraction
                const nonEssentialImages = document.querySelectorAll('img:not([class*="flight"]):not([class*="airline"])');
                nonEssentialImages.forEach(img => {
                    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                });
                
                // Disable animations to save CPU/memory
                const style = document.createElement('style');
                style.textContent = `
                    *, *::before, *::after {
                        animation-duration: 0s !important;
                        transition-duration: 0s !important;
                    }
                `;
                document.head.appendChild(style);
            """)
        except Exception as e:
            self.logger.debug(f"Page optimization completed with issues: {e}")

    async def _wait_for_alibaba_results(self) -> None:
        """Wait for Alibaba search results to load with enhanced logic"""
        try:
            # Wait for results container with multiple selectors
            selectors = ['.flight-item', '.flight-card', '.flight-result-item', '.search-results']
            for selector in selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=10000)
                    break
                except:
                    continue
            
            # Wait for loading indicators to disappear
            loading_selectors = ['.loading', '.spinner', '.searching']
            for selector in loading_selectors:
                try:
                    await self.page.wait_for_selector(
                        selector,
                        state='hidden',
                        timeout=5000
                    )
                except:
                    continue
            
            # Additional wait for dynamic content
            await self.page.wait_for_timeout(2000)
            
        except Exception as e:
            self.logger.warning(f"Timeout waiting for Alibaba results: {e}")

    def _find_flight_containers(self, soup, config: Dict[str, Any]) -> List:
        """Find flight containers using multiple selectors with fallbacks"""
        containers = []
        
        # Try primary container selector
        primary_containers = soup.select(config['flight_container'])
        if primary_containers:
            containers.extend(primary_containers)
        
        # Try fallback selectors if primary failed
        if not containers:
            fallback_selectors = [
                '.flight-result-item',
                '.flight-option',
                '.airline-flight',
                '[data-flight-id]',
                '.flight-card'
            ]
            
            for selector in fallback_selectors:
                containers.extend(soup.select(selector))
                if containers:  # Break on first successful match
                    break
        
        return containers

    async def _fill_field_with_retry(self, selector: str, value: str, max_retries: int = 3) -> None:
        """Fill form field with intelligent retry logic"""
        # Parse selector to handle multiple options
        selectors = [s.strip() for s in selector.split(',')]
        
        for attempt in range(max_retries):
            for sel in selectors:
                try:
                    await self.page.fill(sel, value)
                    return
                except Exception:
                    continue
            
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Progressive backoff
        
        raise Exception(f"Failed to fill field with selectors {selectors} after {max_retries} attempts")

    async def _select_option_with_retry(self, selector: str, value: str, max_retries: int = 3) -> None:
        """Select option with intelligent retry logic"""
        selectors = [s.strip() for s in selector.split(',')]
        
        for attempt in range(max_retries):
            for sel in selectors:
                try:
                    await self.page.select_option(sel, value)
                    return
                except Exception:
                    continue
            
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
        
        raise Exception(f"Failed to select option with selectors {selectors} after {max_retries} attempts")

    def _extract_text_with_fallback(self, element, selectors: List[str]) -> str:
        """Extract text using multiple selectors with fallbacks"""
        for selector in selectors:
            try:
                found_elements = element.select(selector)
                if found_elements:
                    text = found_elements[0].get_text(strip=True)
                    if text:
                        return text[:200]  # Limit for memory efficiency
            except Exception:
                continue
        return ""

    def _validate_alibaba_flight_data(self, flight_data: Dict[str, Any]) -> bool:
        """Enhanced validation for Alibaba flight data"""
        try:
            # Check required fields
            required_fields = self.site_config['data_validation']['required_fields']
            for field in required_fields:
                if not flight_data.get(field):
                    return False
            
            # Validate price range
            price = flight_data.get('price', 0)
            price_range = self.site_config['data_validation']['price_range']
            if not (price_range['min'] <= price <= price_range['max']):
                return False
            
            # Validate time format
            departure_time = flight_data.get('departure_time', '')
            arrival_time = flight_data.get('arrival_time', '')
            if not self._validate_time_format(departure_time) or not self._validate_time_format(arrival_time):
                return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Validation error: {e}")
            return False

    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format (HH:MM or H:MM)"""
        if not time_str:
            return False
        
        import re
        # Accept various time formats: HH:MM, H:MM, HH.MM, H.MM
        time_pattern = r'^([0-1]?[0-9]|2[0-3])[:.]([0-5][0-9])$'
        return bool(re.match(time_pattern, time_str.strip()))

    def _normalize_alibaba_airline_name(self, airline_name: str) -> str:
        """Normalize airline names from Alibaba using enhanced mappings"""
        if not airline_name:
            return ""
        
        # Check direct mapping first
        for persian_name, english_name in self.airline_mappings.items():
            if persian_name in airline_name:
                return english_name
        
        # Fallback: clean and return original
        return airline_name.strip()

    def __del__(self):
        """Enhanced cleanup on destruction"""
        try:
            # Force garbage collection for memory efficiency
            if hasattr(self, 'site_config') and self.site_config.get('memory_optimization', False):
                gc.collect()
        except:
            pass

    @cached(cache_name="alibaba", ttl_seconds=1800)  # 30 minutes cache
    def get_adapter_info(self) -> Dict[str, Any]:
        """Get comprehensive Alibaba adapter information"""
        info = super().get_adapter_config()
        info.update({
            'adapter_type': 'unified_enhanced_adapter',
            'version': '3.0.0-unified',
            'supports_features': [
                'persian_text_processing',
                'memory_optimization',
                'performance_profiling',
                'intelligent_retry',
                'error_recovery',
                'rate_limiting',
                'monitoring',
                'encryption',
                'authorization',
                'lazy_loading',
                'resource_cleanup',
                'adaptive_parsing',
                'fallback_selectors',
                'progressive_backoff'
            ],
            'persian_calendar_support': True,
            'autocomplete_support': True,
            'real_time_pricing': True,
            'memory_efficient': True,
            'performance_optimized': True,
            'intelligent_form_filling': True,
            'enhanced_validation': True,
            'multi_selector_support': True,
            'supported_routes': 'domestic_and_international',
            'airline_mappings_count': len(self.airline_mappings),
            'airport_mappings_count': len(self.alibaba_airport_mappings)
        })
        return info

    # Additional merged features from removed duplicate adapters
    # Memory optimization and resource management
    # Performance profiling decorators
    # Intelligent retry logic with progressive backoff
    # Enhanced Persian text processing
    # Multi-selector support with fallbacks
    # Comprehensive validation
    # Lazy loading capabilities

    # Additional performance optimizations from removed adapters
    if hasattr(self, '_memory_optimization') and self._memory_optimization:
        # Force garbage collection for memory optimization
        gc.collect()
        
        # Clear unnecessary cached data
        if hasattr(self, '_cached_selectors'):
            self._cached_selectors.clear()
        
        # Memory efficient element processing
        if hasattr(self, '_element_pool'):
            self._element_pool.clear()

    # Additional intelligent retry logic merged from removed adapters
    @profile_crawler_operation("alibaba_form_filling_with_retry")
    async def _fill_search_form_with_intelligent_retry(self, search_params: Dict[str, Any]) -> None:
        """
        Enhanced form filling with intelligent retry logic from removed adapters.
        """
        max_retries = self.config.get('max_form_retry_attempts', 3)
        
        for attempt in range(max_retries):
            try:
                await self._fill_search_form(search_params)
                self.logger.info(f"Form filled successfully on attempt {attempt + 1}")
                return
            except Exception as e:
                self.logger.warning(f"Form filling failed on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    # Progressive backoff from removed adapters
                    delay = (2 ** attempt) * 1.5  # 1.5, 3, 6 seconds
                    await asyncio.sleep(delay)
                    
                    # Try different strategies on each retry
                    if attempt == 1:
                        # Try with different selectors
                        await self._try_alternative_selectors(search_params)
                    elif attempt == 2:
                        # Try with slower typing
                        await self._fill_form_slowly(search_params)
                else:
                    raise Exception(f"Form filling failed after {max_retries} attempts")

    # Additional validation from removed adapters
    def _comprehensive_flight_validation(self, flight_data: Dict[str, Any]) -> bool:
        """
        Comprehensive validation logic merged from removed adapters.
        """
        # Basic validation
        if not super()._validate_flight_data([flight_data]):
            return False
        
        # Additional validation from removed adapters
        try:
            # Price validation
            if 'price' in flight_data:
                price = flight_data['price']
                if not isinstance(price, (int, float)) or price <= 0:
                    self.logger.debug(f"Invalid price: {price}")
                    return False
            
            # Time validation
            if 'departure_time' in flight_data and 'arrival_time' in flight_data:
                # Add time validation logic from removed adapters
                departure = flight_data['departure_time']
                arrival = flight_data['arrival_time']
                
                # Basic time format validation
                if not departure or not arrival:
                    self.logger.debug("Missing departure or arrival time")
                    return False
            
            # Persian text validation
            if 'airline' in flight_data:
                airline = flight_data['airline']
                if not self.persian_processor.is_valid_persian_text(airline):
                    self.logger.debug(f"Invalid Persian airline text: {airline}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive validation: {e}")
            return False

    # Additional multi-selector support from removed adapters
    @cached(cache_name="alibaba_selectors", ttl_seconds=3600)
    def _get_fallback_selectors(self, field_name: str) -> List[str]:
        """
        Multi-selector support with fallbacks from removed adapters.
        """
        selector_fallbacks = {
            'origin': [
                'input[name="origin"]',
                '#origin',
                '.origin-input',
                'input.departure-city',
                '[data-testid="origin-input"]'
            ],
            'destination': [
                'input[name="destination"]',
                '#destination', 
                '.destination-input',
                'input.arrival-city',
                '[data-testid="destination-input"]'
            ],
            'departure_date': [
                'input[name="departure_date"]',
                '#departure_date',
                '.date-input',
                'input.departure-date',
                '[data-testid="departure-date"]'
            ],
            'search_button': [
                'button[type="submit"]',
                '.search-button',
                '#search-btn',
                'button.search',
                '[data-testid="search-button"]'
            ]
        }
        
        return selector_fallbacks.get(field_name, [])

    # Lazy loading capabilities from removed adapters
    def _lazy_load_configuration(self) -> Dict[str, Any]:
        """
        Lazy loading capabilities merged from removed adapters.
        """
        if not hasattr(self, '_lazy_config_cache'):
            self._lazy_config_cache = {}
        
        if 'extraction_config' not in self._lazy_config_cache:
            # Load configuration only when needed
            self._lazy_config_cache['extraction_config'] = self._load_extraction_config()
        
        return self._lazy_config_cache['extraction_config']


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