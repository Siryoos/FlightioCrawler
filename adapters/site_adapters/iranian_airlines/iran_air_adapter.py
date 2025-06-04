from typing import Dict, List, Optional
from datetime import datetime
import json
import logging
from bs4 import BeautifulSoup
from data.transformers.persian_text_processor import PersianTextProcessor
from crawlers.factories.crawler_factory import PersianAirlineCrawler

class IranAirAdapter(PersianAirlineCrawler):
    """Adapter for Iran Air with specialized Persian text handling"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.text_processor = PersianTextProcessor()
        
    async def _perform_crawl(self, search_params: dict) -> List[Dict]:
        """Perform the actual crawl for Iran Air"""
        try:
            # Navigate to search page
            await self.crawler.goto(self.config['search_url'])
            
            # Fill search form
            await self._fill_search_form(search_params)
            
            # Wait for results
            if not await self._wait_for_element(self.config['extraction_config']['results_parsing']['container']):
                raise Exception("Flight results not found")
            
            # Extract flight data
            html = await self.crawler.content()
            return self._parse_flight_results(html, search_params)
            
        except Exception as e:
            self.logger.error(f"Error crawling Iran Air: {e}")
            return []
            
    async def _fill_search_form(self, search_params: dict):
        """Fill the search form with proper Persian text handling"""
        try:
            # Convert dates to Jalali if needed
            if self.config['persian_processing']['jalali_calendar']:
                departure_date = self.text_processor.convert_gregorian_to_jalali(
                    datetime.strptime(search_params['departure_date'], '%Y-%m-%d')
                )
            else:
                departure_date = search_params['departure_date']
                
            # Execute form filling
            await self._execute_js("""
                document.querySelector(arguments[0]).value = arguments[1];
                document.querySelector(arguments[2]).value = arguments[3];
                document.querySelector(arguments[4]).value = arguments[5];
                document.querySelector(arguments[6]).value = arguments[7];
                document.querySelector(arguments[8]).value = arguments[9];
            """,
            self.config['extraction_config']['search_form']['origin_field'],
            search_params['origin'],
            self.config['extraction_config']['search_form']['destination_field'],
            search_params['destination'],
            self.config['extraction_config']['search_form']['date_field'],
            departure_date,
            self.config['extraction_config']['search_form']['passengers_field'],
            search_params['passengers'],
            self.config['extraction_config']['search_form']['class_field'],
            search_params['seat_class']
            )
            
            # Submit form
            await self._execute_js("document.querySelector('form').submit();")
            
        except Exception as e:
            self.logger.error(f"Error filling search form: {e}")
            raise
            
    def _parse_flight_results(self, html: str, search_params: dict) -> List[Dict]:
        """Parse flight results with Persian text processing"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            flights = []
            
            for flight_elem in soup.select(self.config['extraction_config']['results_parsing']['container']):
                try:
                    # Extract and process flight data
                    flight = {
                        'airline_code': 'IRA',  # Iran Air's IATA code
                        'flight_number': self._extract_flight_number(flight_elem),
                        'origin_airport': search_params['origin'],
                        'destination_airport': search_params['destination'],
                        'departure_time': self._extract_departure_time(flight_elem),
                        'arrival_time': self._extract_arrival_time(flight_elem),
                        'duration_minutes': self._extract_duration(flight_elem),
                        'price': self._extract_price(flight_elem),
                        'currency': self._extract_currency(flight_elem),
                        'fare_class': self._extract_fare_class(flight_elem),
                        'raw_data': self._extract_raw_data(flight_elem)
                    }
                    
                    # Validate flight data
                    if self._validate_flight_data(flight):
                        flights.append(flight)
                        
                except Exception as e:
                    self.logger.error(f"Error parsing flight element: {e}")
                    continue
                    
            return flights
            
        except Exception as e:
            self.logger.error(f"Error parsing flight results: {e}")
            return []
            
    def _extract_flight_number(self, flight_elem) -> str:
        """Extract and normalize flight number"""
        flight_number = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['flight_number']
        ).text.strip()
        return flight_number.replace(' ', '')
        
    def _extract_departure_time(self, flight_elem) -> datetime:
        """Extract and parse departure time"""
        time_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['departure_time']
        ).text.strip()
        return self.text_processor.parse_time(time_text)
        
    def _extract_arrival_time(self, flight_elem) -> datetime:
        """Extract and parse arrival time"""
        time_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['arrival_time']
        ).text.strip()
        return self.text_processor.parse_time(time_text)
        
    def _extract_duration(self, flight_elem) -> int:
        """Extract and parse flight duration"""
        duration_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['duration']
        ).text.strip()
        return self.text_processor.extract_flight_duration(duration_text)
        
    def _extract_price(self, flight_elem) -> float:
        """Extract and parse price"""
        price_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['price']
        ).text.strip()
        price_info = self.text_processor.parse_persian_price(price_text)
        return price_info['amount']
        
    def _extract_currency(self, flight_elem) -> str:
        """Extract and normalize currency"""
        price_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['price']
        ).text.strip()
        price_info = self.text_processor.parse_persian_price(price_text)
        return price_info['currency']
        
    def _extract_fare_class(self, flight_elem) -> str:
        """Extract and normalize fare class"""
        class_text = flight_elem.select_one(
            self.config['extraction_config']['results_parsing']['seat_class']
        ).text.strip()
        return self.text_processor.normalize_seat_class(class_text)
        
    def _extract_raw_data(self, flight_elem) -> Dict:
        """Extract additional raw data for storage"""
        return {
            'airline_name': self.text_processor.normalize_persian_text(
                flight_elem.select_one(
                    self.config['extraction_config']['results_parsing']['airline']
                ).text.strip()
            ),
            'fare_conditions': self._extract_fare_conditions(flight_elem),
            'available_seats': self._extract_available_seats(flight_elem)
        }
        
    def _extract_fare_conditions(self, flight_elem) -> Dict:
        """Extract fare conditions if available"""
        try:
            conditions_elem = flight_elem.select_one('.fare-conditions')
            if conditions_elem:
                return {
                    'cancellation': self._extract_cancellation_policy(conditions_elem),
                    'changes': self._extract_change_policy(conditions_elem),
                    'baggage': self._extract_baggage_policy(conditions_elem)
                }
        except Exception as e:
            self.logger.error(f"Error extracting fare conditions: {e}")
        return {}
        
    def _extract_available_seats(self, flight_elem) -> Optional[int]:
        """Extract number of available seats if shown"""
        try:
            seats_elem = flight_elem.select_one('.available-seats')
            if seats_elem:
                seats_text = seats_elem.text.strip()
                return int(self.text_processor.convert_persian_numerals(seats_text))
        except Exception as e:
            self.logger.error(f"Error extracting available seats: {e}")
        return None
        
    def _validate_flight_data(self, flight: Dict) -> bool:
        """Validate extracted flight data"""
        try:
            # Check required fields
            required_fields = self.config['data_validation']['required_fields']
            for field in required_fields:
                if field not in flight or flight[field] is None:
                    self.logger.error(f"Missing required field: {field}")
                    return False
                    
            # Validate price range
            price_range = self.config['data_validation']['price_range']
            if not (price_range['min'] <= flight['price'] <= price_range['max']):
                self.logger.error(f"Price {flight['price']} outside valid range")
                return False
                
            # Validate duration range
            if flight['duration_minutes']:
                duration_range = self.config['data_validation']['duration_range']
                if not (duration_range['min'] <= flight['duration_minutes'] <= duration_range['max']):
                    self.logger.error(f"Duration {flight['duration_minutes']} outside valid range")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating flight data: {e}")
            return False 