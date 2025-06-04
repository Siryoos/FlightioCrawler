import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from adapters.site_adapters.base_crawler import BaseSiteCrawler
from data.transformers.persian_text_processor import PersianTextProcessor
from utils.logger import get_logger

logger = get_logger(__name__)

class Mz724Adapter(BaseSiteCrawler):
    """Adapter for crawling mz724.ir (مجمع زمزم)"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://www.mz724.ir"
        self.search_url = f"{self.base_url}/flight-search"
        self.text_processor = PersianTextProcessor()
        
    async def crawl(self, search_params: Dict) -> List[Dict]:
        """Main crawl method for Mz724"""
        start_time = datetime.now()
        try:
            # Circuit breaker check
            if not await self.error_handler.can_make_request(self.domain):
                return []
            
            # Rate limiting check
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            
            # Navigate to search page
            await self._navigate_to_search_page()
            
            # Fill search form
            await self._fill_search_form(search_params)
            
            # Wait for results and extract data
            flights = await self._extract_flight_results()
            
            # Track successful request
            await self.monitor.track_request(
                domain=self.domain,
                duration=(datetime.now() - start_time).total_seconds(),
                success=True
            )
            
            return flights
            
        except Exception as e:
            logger.error(f"Error crawling Mz724: {str(e)}")
            await self.error_handler.handle_error(self.domain, e)
            await self.monitor.track_request(
                domain=self.domain,
                duration=(datetime.now() - start_time).total_seconds(),
                success=False,
                error=str(e)
            )
            return []
    
    async def _navigate_to_search_page(self):
        """Navigate to the flight search page"""
        try:
            await self.crawler.goto(self.search_url)
            await self.crawler.wait_for_selector('.flight-search-form', timeout=10)
        except TimeoutException:
            raise Exception("Failed to load search page")
    
    async def _fill_search_form(self, search_params: Dict):
        """Fill the search form with Persian text handling"""
        try:
            # Origin
            origin_field = await self.crawler.wait_for_selector('input[name="origin"]')
            await origin_field.type(search_params["origin"])
            
            # Destination
            dest_field = await self.crawler.wait_for_selector('input[name="destination"]')
            await dest_field.type(search_params["destination"])
            
            # Convert Gregorian to Jalali date
            jalali_date = self.text_processor.convert_gregorian_to_jalali(
                datetime.strptime(search_params["departure_date"], '%Y-%m-%d')
            )
            
            # Date
            date_field = await self.crawler.wait_for_selector('input[name="departure_date"]')
            await date_field.type(jalali_date)
            
            # Passengers
            if "passengers" in search_params:
                passengers_field = await self.crawler.wait_for_selector('select[name="passengers"]')
                await passengers_field.select(str(search_params["passengers"]))
            
            # Seat class
            if "seat_class" in search_params:
                class_field = await self.crawler.wait_for_selector('select[name="cabin_class"]')
                persian_class = self.text_processor.normalize_seat_class(search_params["seat_class"])
                await class_field.select(persian_class)
            
            # Submit form
            submit_button = await self.crawler.wait_for_selector('button[type="submit"]')
            await submit_button.click()
            
        except Exception as e:
            logger.error(f"Error filling search form: {str(e)}")
            raise
    
    async def _extract_flight_results(self) -> List[Dict]:
        """Extract flight results with Persian text processing"""
        try:
            # Wait for results to load
            await self.crawler.wait_for_selector('.flight-result', timeout=15)
            
            # Get page content
            content = await self.crawler.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            flights = []
            for flight_elem in soup.select('.flight-result'):
                try:
                    flight = self._parse_flight_element(flight_elem)
                    if flight and self._validate_flight_data(flight):
                        flights.append(flight)
                except Exception as e:
                    logger.error(f"Error parsing flight element: {str(e)}")
                    continue
            
            return flights
            
        except TimeoutException:
            logger.error("Timeout waiting for flight results")
            return []
        except Exception as e:
            logger.error(f"Error extracting flight results: {str(e)}")
            return []
    
    def _parse_flight_element(self, flight_elem) -> Optional[Dict]:
        """Parse individual flight element with Persian text handling"""
        try:
            # Extract raw data
            raw_airline = flight_elem.select_one('.airline-name').text.strip()
            raw_flight_number = flight_elem.select_one('.flight-number').text.strip()
            raw_departure = flight_elem.select_one('.departure-time').text.strip()
            raw_arrival = flight_elem.select_one('.arrival-time').text.strip()
            raw_price = flight_elem.select_one('.price').text.strip()
            raw_class = flight_elem.select_one('.seat-class').text.strip()
            raw_duration = flight_elem.select_one('.duration').text.strip()
            
            # Process Persian text
            flight = {
                'airline': self.text_processor.normalize_airline_name(raw_airline),
                'flight_number': self.text_processor.clean_flight_number(raw_flight_number),
                'departure_time': self.text_processor.parse_time(raw_departure),
                'arrival_time': self.text_processor.parse_time(raw_arrival),
                'price': self.text_processor.extract_price(raw_price)[0],
                'currency': 'IRR',
                'seat_class': self.text_processor.normalize_seat_class(raw_class),
                'duration_minutes': self.text_processor.extract_duration(raw_duration),
                'flight_type': 'domestic' if self._is_domestic_flight(raw_flight_number) else 'international',
                'scraped_at': datetime.now(),
                'source_url': self.base_url
            }
            
            # Extract additional data
            flight.update(self._extract_additional_data(flight_elem))
            
            return flight
            
        except Exception as e:
            logger.error(f"Error parsing flight element: {str(e)}")
            return None
    
    def _extract_additional_data(self, flight_elem) -> Dict:
        """Extract additional flight data"""
        additional_data = {}
        
        try:
            # Fare conditions
            fare_conditions = flight_elem.select_one('.fare-conditions')
            if fare_conditions:
                additional_data['fare_conditions'] = {
                    'cancellation': fare_conditions.select_one('.cancellation').text.strip(),
                    'changes': fare_conditions.select_one('.changes').text.strip(),
                    'baggage': fare_conditions.select_one('.baggage').text.strip()
                }
            
            # Available seats
            seats_elem = flight_elem.select_one('.available-seats')
            if seats_elem:
                seats_text = seats_elem.text.strip()
                additional_data['available_seats'] = self.text_processor.extract_number(seats_text)
            
            # Aircraft type
            aircraft_elem = flight_elem.select_one('.aircraft-type')
            if aircraft_elem:
                additional_data['aircraft_type'] = aircraft_elem.text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting additional data: {str(e)}")
        
        return additional_data
    
    def _is_domestic_flight(self, flight_number: str) -> bool:
        """Determine if flight is domestic based on flight number"""
        # Mz724 uses specific patterns for domestic flights
        domestic_patterns = ['IR', 'W5', 'EP', 'ZV', 'QB', 'B9']
        return any(pattern in flight_number for pattern in domestic_patterns)
    
    def _validate_flight_data(self, flight: Dict) -> bool:
        """Validate extracted flight data"""
        try:
            # Check required fields
            required_fields = self.config.get('data_validation', {}).get('required_fields', [])
            if not all(field in flight for field in required_fields):
                return False
            
            # Validate price range
            price_range = self.config.get('data_validation', {}).get('price_range', {})
            if not (price_range.get('min', 0) <= flight['price'] <= price_range.get('max', float('inf'))):
                return False
            
            # Validate duration range
            duration_range = self.config.get('data_validation', {}).get('duration_range', {})
            if not (duration_range.get('min', 0) <= flight['duration_minutes'] <= duration_range.get('max', float('inf'))):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating flight data: {str(e)}")
            return False 