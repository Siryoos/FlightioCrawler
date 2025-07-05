"""
Alibaba Adapter V3 - Enhanced with Automated Form Filling

This is the next-generation Alibaba adapter that uses the enhanced Iranian adapter
with intelligent form automation, Persian text processing, and advanced error recovery.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from adapters.base_adapters.enhanced_iranian_adapter import EnhancedIranianAdapter
from adapters.base_adapters.enhanced_error_handler import (
    ErrorCategory, 
    ErrorSeverity, 
    error_handler_decorator
)


class AlibabaAdapterV3(EnhancedIranianAdapter):
    """
    Enhanced Alibaba adapter with automated form filling and intelligent processing
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Alibaba-specific configuration
        alibaba_config = {
            'name': 'alibaba_v3',
            'base_url': 'https://www.alibaba.ir',
            'search_url': 'https://www.alibaba.ir/flights',
            'supports_persian': True,
            'persian_calendar': True,
            'airport_mapping': True,
            'intelligent_retry': True,
            'max_form_retry_attempts': 3,
            'form_timeout_seconds': 30,
            'captcha_handling': True,
            
            # Rate limiting specific to Alibaba
            'rate_limiting': {
                'requests_per_minute': 8,
                'delay_seconds': 7,
                'burst_limit': 15
            },
            
            # Alibaba-specific extraction configuration
            'extraction_config': {
                'search_form': {
                    'origin_field': '#departure-city',
                    'destination_field': '#arrival-city',
                    'departure_date_field': '#departure-date',
                    'return_date_field': '#return-date',
                    'passenger_count_field': '#passenger-count',
                    'cabin_class_field': '#cabin-class',
                    'search_button': '.search-flight-btn'
                },
                'results_parsing': {
                    'flight_container': '.flight-item, .flight-card',
                    'flight_number': '.flight-number, .flight-code',
                    'airline': '.airline-name, .carrier',
                    'departure_time': '.departure-time, .dep-time',
                    'arrival_time': '.arrival-time, .arr-time',
                    'duration': '.flight-duration, .duration',
                    'price': '.price-amount, .fare-price',
                    'currency': '.currency, .price-currency',
                    'stops': '.stops-info, .stop-count',
                    'aircraft_type': '.aircraft-type, .plane-type',
                    'available_seats': '.seats-available, .availability'
                }
            },
            
            # Data validation specific to Alibaba
            'data_validation': {
                'required_fields': ['flight_number', 'airline', 'departure_time', 'arrival_time', 'price'],
                'price_range': {'min': 100000, 'max': 20000000},  # IRR
                'duration_range': {'min': 30, 'max': 1440}  # minutes
            },
            
            # Persian processing configuration
            'persian_processing': {
                'enable_text_normalization': True,
                'enable_date_conversion': True,
                'enable_number_conversion': True,
                'airport_name_mapping': True,
                'airline_name_mapping': True
            }
        }
        
        # Merge with provided config
        if config:
            alibaba_config.update(config)
        
        super().__init__('alibaba_v3', alibaba_config)
        
        # Alibaba-specific mappings
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

    def _get_base_url(self) -> str:
        """Get Alibaba base URL"""
        return self.config['base_url']

    def _get_required_search_fields(self) -> List[str]:
        """Required fields for Alibaba search"""
        return ['origin', 'destination', 'departure_date']

    def _convert_airport_for_site(self, airport_code: str) -> str:
        """Convert airport code to Alibaba-specific format"""
        airport_code = airport_code.upper()
        
        if airport_code in self.alibaba_airport_mappings:
            # Return Persian name for Alibaba
            persian_names = self.alibaba_airport_mappings[airport_code]
            return persian_names[0]  # Return Persian name
        
        return airport_code

    @error_handler_decorator(
        operation_name="navigate_to_search_page",
        category=ErrorCategory.NAVIGATION,
        severity=ErrorSeverity.MEDIUM,
        max_retries=2
    )
    async def _navigate_to_search_page(self) -> None:
        """Navigate to Alibaba search page with enhanced handling"""
        if not self.page:
            raise RuntimeError("Page not initialized")
        
        try:
            # Navigate to search page
            await self.page.goto(self.config['search_url'])
            
            # Wait for page to load completely
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Handle any popups or modals
            await self._handle_alibaba_popups()
            
            # Verify search form is present
            await self._verify_search_form()
            
            self.logger.info("Successfully navigated to Alibaba search page")
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to Alibaba search page: {e}")
            raise

    async def _handle_alibaba_popups(self) -> None:
        """Handle Alibaba-specific popups and modals"""
        popup_selectors = [
            '.modal-close, .popup-close',
            '.cookie-accept, .accept-cookies',
            '.newsletter-close',
            '[data-dismiss="modal"]'
        ]
        
        for selector in popup_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await self.page.wait_for_timeout(500)
            except:
                continue

    async def _verify_search_form(self) -> None:
        """Verify that the search form is present and ready"""
        form_indicators = [
            '#departure-city, #origin',
            '#arrival-city, #destination', 
            '.search-flight-btn, button[type="submit"]'
        ]
        
        for selector in form_indicators:
            element = await self.page.query_selector(selector)
            if not element:
                raise RuntimeError(f"Search form element not found: {selector}")

    @error_handler_decorator(
        operation_name="extract_flight_results",
        category=ErrorCategory.PARSING,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def _extract_flight_results(self) -> List[Dict[str, Any]]:
        """Extract flight results from Alibaba with enhanced parsing"""
        try:
            # Wait for results to load
            await self._wait_for_alibaba_results()
            
            # Get page content
            content = await self.page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract flights using multiple selectors
            flights = []
            config = self.config['extraction_config']['results_parsing']
            
            # Try different container selectors
            flight_containers = self._find_flight_containers(soup, config)
            
            for container in flight_containers:
                try:
                    flight_data = await self._parse_alibaba_flight_element(container, config)
                    if flight_data:
                        flights.append(flight_data)
                except Exception as e:
                    self.logger.debug(f"Failed to parse flight container: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(flights)} flights from Alibaba")
            return flights
            
        except Exception as e:
            self.logger.error(f"Failed to extract Alibaba flight results: {e}")
            raise

    async def _wait_for_alibaba_results(self) -> None:
        """Wait for Alibaba search results to load"""
        try:
            # Wait for results container
            await self.page.wait_for_selector(
                '.flight-item, .flight-card, .search-results',
                timeout=30000
            )
            
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
        """Find flight containers using multiple selectors"""
        containers = []
        
        # Try primary container selector
        primary_containers = soup.select(config['flight_container'])
        if primary_containers:
            containers.extend(primary_containers)
        
        # Try fallback selectors
        fallback_selectors = [
            '.flight-result-item',
            '.flight-option',
            '.airline-flight',
            '[data-flight-id]'
        ]
        
        for selector in fallback_selectors:
            if not containers:  # Only use fallbacks if primary failed
                containers.extend(soup.select(selector))
        
        return containers

    async def _parse_alibaba_flight_element(self, element, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse individual flight element with Alibaba-specific logic"""
        try:
            flight_data = {}
            
            # Extract basic flight information
            flight_data['flight_number'] = self._extract_text_with_fallback(
                element, [config['flight_number'], '.flight-code', '.flight-num']
            )
            
            flight_data['airline'] = self._extract_text_with_fallback(
                element, [config['airline'], '.airline', '.carrier-name']
            )
            
            flight_data['departure_time'] = self._extract_text_with_fallback(
                element, [config['departure_time'], '.dep-time', '.depart']
            )
            
            flight_data['arrival_time'] = self._extract_text_with_fallback(
                element, [config['arrival_time'], '.arr-time', '.arrive']
            )
            
            flight_data['duration'] = self._extract_text_with_fallback(
                element, [config['duration'], '.duration', '.flight-time']
            )
            
            # Extract price with Persian number handling
            price_text = self._extract_text_with_fallback(
                element, [config['price'], '.price', '.fare']
            )
            flight_data['price'] = self._parse_alibaba_price(price_text)
            
            # Extract additional Alibaba-specific fields
            flight_data['stops'] = self._extract_text_with_fallback(
                element, [config.get('stops', ''), '.stops', '.stop-info']
            )
            
            flight_data['aircraft_type'] = self._extract_text_with_fallback(
                element, [config.get('aircraft_type', ''), '.aircraft', '.plane']
            )
            
            flight_data['available_seats'] = self._extract_text_with_fallback(
                element, [config.get('available_seats', ''), '.seats', '.availability']
            )
            
            # Set defaults
            flight_data['currency'] = 'IRR'
            flight_data['origin_airport'] = ''  # Will be filled from search params
            flight_data['destination_airport'] = ''  # Will be filled from search params
            
            # Process Persian text fields
            flight_data = await self._process_alibaba_persian_fields(flight_data)
            
            # Validate essential fields
            if self._validate_alibaba_flight_data(flight_data):
                return flight_data
            else:
                self.logger.debug("Flight data validation failed")
                return None
                
        except Exception as e:
            self.logger.error(f"Error parsing Alibaba flight element: {e}")
            return None

    def _extract_text_with_fallback(self, element, selectors: List[str]) -> str:
        """Extract text using multiple fallback selectors"""
        for selector in selectors:
            if not selector:
                continue
            try:
                found_element = element.select_one(selector)
                if found_element and found_element.text.strip():
                    return found_element.text.strip()
            except:
                continue
        return ''

    def _parse_alibaba_price(self, price_text: str) -> float:
        """Parse price from Alibaba with Persian number handling"""
        if not price_text:
            return 0.0
        
        try:
            # Remove Persian/Arabic digits and convert to English
            price_cleaned = self.persian_processor.convert_persian_numbers_to_english(price_text)
            
            # Remove currency symbols and separators
            price_cleaned = price_cleaned.replace(',', '').replace('ریال', '').replace('IRR', '')
            price_cleaned = ''.join(char for char in price_cleaned if char.isdigit() or char == '.')
            
            return float(price_cleaned) if price_cleaned else 0.0
            
        except Exception as e:
            self.logger.debug(f"Failed to parse price '{price_text}': {e}")
            return 0.0

    async def _process_alibaba_persian_fields(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Persian text fields specific to Alibaba"""
        persian_fields = ['airline', 'aircraft_type', 'stops']
        
        for field in persian_fields:
            if field in flight_data and flight_data[field]:
                flight_data[field] = self.persian_processor.normalize_text(flight_data[field])
        
        # Convert airline names to standard format
        if 'airline' in flight_data:
            flight_data['airline'] = self._normalize_alibaba_airline_name(flight_data['airline'])
        
        return flight_data

    def _normalize_alibaba_airline_name(self, airline_name: str) -> str:
        """Normalize airline names from Alibaba"""
        airline_mappings = {
            'ایران ایر': 'Iran Air',
            'ماهان': 'Mahan Air',
            'آسمان': 'Aseman Airlines',
            'کاسپین': 'Caspian Airlines',
            'تابان': 'Taban Air',
            'قشم ایر': 'Qeshm Air',
            'زاگرس': 'Zagros Airlines'
        }
        
        for persian_name, english_name in airline_mappings.items():
            if persian_name in airline_name:
                return english_name
        
        return airline_name

    def _validate_alibaba_flight_data(self, flight_data: Dict[str, Any]) -> bool:
        """Validate flight data specific to Alibaba"""
        required_fields = self.config['data_validation']['required_fields']
        
        # Check required fields
        for field in required_fields:
            if not flight_data.get(field):
                return False
        
        # Validate price range
        price = flight_data.get('price', 0)
        price_range = self.config['data_validation']['price_range']
        if not (price_range['min'] <= price <= price_range['max']):
            return False
        
        # Validate time format
        if not self._validate_time_format(flight_data.get('departure_time', '')):
            return False
        
        if not self._validate_time_format(flight_data.get('arrival_time', '')):
            return False
        
        return True

    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format"""
        if not time_str:
            return False
        
        # Common time patterns
        time_patterns = [
            r'\d{2}:\d{2}',  # HH:MM
            r'\d{1,2}:\d{2}',  # H:MM or HH:MM
            r'\d{2}:\d{2}:\d{2}'  # HH:MM:SS
        ]
        
        import re
        for pattern in time_patterns:
            if re.search(pattern, time_str):
                return True
        
        return False

    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Fallback form filling for backward compatibility"""
        # This is kept for compatibility but the enhanced adapter
        # will use the automated form strategy instead
        config = self.config['extraction_config']['search_form']
        
        try:
            # Fill basic fields
            if 'origin' in search_params:
                origin_value = self._convert_airport_for_site(search_params['origin'])
                await self.page.fill(config['origin_field'], origin_value)
            
            if 'destination' in search_params:
                dest_value = self._convert_airport_for_site(search_params['destination'])
                await self.page.fill(config['destination_field'], dest_value)
            
            if 'departure_date' in search_params:
                await self.page.fill(config['departure_date_field'], search_params['departure_date'])
            
            if 'return_date' in search_params:
                await self.page.fill(config['return_date_field'], search_params['return_date'])
            
            # Submit form
            await self.page.click(config['search_button'])
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            
        except Exception as e:
            self.logger.error(f"Fallback form filling failed: {e}")
            raise 