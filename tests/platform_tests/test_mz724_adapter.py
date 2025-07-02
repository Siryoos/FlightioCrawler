import pytest
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from adapters.site_adapters.iranian_airlines.mz724_adapter import Mz724Adapter

@pytest.fixture
def sample_config():
    return {
        'site_id': 'mz724',
        'name': 'مجمع زمزم',
        'search_url': 'https://www.mz724.ir/flight-search',
        'persian_processing': {
            'rtl_support': True,
            'jalali_calendar': True,
            'persian_numerals': True
        },
        'extraction_config': {
            'search_form': {
                'origin_field': 'input[name="origin"]',
                'destination_field': 'input[name="destination"]',
                'date_field': 'input[name="departure_date"]',
                'passengers_field': 'select[name="passengers"]',
                'class_field': 'select[name="cabin_class"]'
            },
            'results_parsing': {
                'container': '.flight-result',
                'price': '.price',
                'airline': '.airline-name',
                'duration': '.duration',
                'departure_time': '.departure-time',
                'arrival_time': '.arrival-time',
                'flight_number': '.flight-number',
                'seat_class': '.seat-class'
            }
        },
        'data_validation': {
            'required_fields': [
                'airline',
                'flight_number',
                'departure_time',
                'arrival_time',
                'price',
                'currency',
                'seat_class',
                'duration_minutes'
            ],
            'price_range': {
                'min': 1000000,
                'max': 100000000
            },
            'duration_range': {
                'min': 30,
                'max': 1440
            }
        }
    }

@pytest.fixture
def sample_search_params():
    return {
        'origin': 'THR',
        'destination': 'MHD',
        'departure_date': '2024-07-01',
        'passengers': 1,
        'seat_class': 'economy'
    }

@pytest.fixture
def sample_flight_html():
    return """
    <div class="flight-result">
        <div class="airline-name">ایران ایر</div>
        <div class="flight-number">IR ۷۲۵</div>
        <div class="departure-time">۰۸:۳۰</div>
        <div class="arrival-time">۱۰:۴۵</div>
        <div class="duration">۲ ساعت و ۱۵ دقیقه</div>
        <div class="price">۲,۵۰۰,۰۰۰ ریال</div>
        <div class="seat-class">اکونومی</div>
        <div class="fare-conditions">
            <div class="cancellation">قابل کنسلی با جریمه</div>
            <div class="changes">قابل تغییر با جریمه</div>
            <div class="baggage">۲۰ کیلوگرم</div>
        </div>
        <div class="available-seats">۱۲ صندلی</div>
        <div class="aircraft-type">بوئینگ ۷۳۷</div>
    </div>
    """

class TestMz724Adapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params):
        """Test the complete crawl flow"""
        adapter = Mz724Adapter(sample_config)
        results = await adapter.crawl(sample_search_params)
        
        assert isinstance(results, list)
        if results:  # If any results were found
            assert all(isinstance(flight, dict) for flight in results)
            assert all('airline' in flight for flight in results)
            assert all('flight_number' in flight for flight in results)
    
    def test_persian_text_processing(self, sample_config, sample_flight_html):
        """Test Persian text processing functionality"""
        adapter = Mz724Adapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        # Test flight number extraction
        flight_number = adapter._parse_flight_element(flight_elem)['flight_number']
        assert flight_number == 'IR725'
        
        # Test price extraction
        price = adapter._parse_flight_element(flight_elem)['price']
        assert price == 2500000
        
        # Test duration extraction
        duration = adapter._parse_flight_element(flight_elem)['duration_minutes']
        assert duration == 135  # 2 hours and 15 minutes
        
        # Test fare class extraction
        fare_class = adapter._parse_flight_element(flight_elem)['seat_class']
        assert fare_class == 'economy'
    
    def test_date_conversion(self, sample_config, sample_search_params):
        """Test Jalali date conversion"""
        adapter = Mz724Adapter(sample_config)
        
        # Test Gregorian to Jalali conversion
        gregorian_date = datetime.strptime(sample_search_params['departure_date'], '%Y-%m-%d')
        jalali_date = adapter.text_processor.convert_gregorian_to_jalali(gregorian_date)
        assert isinstance(jalali_date, str)
        assert '/' in jalali_date
    
    def test_data_validation(self, sample_config, sample_flight_html):
        """Test flight data validation"""
        adapter = Mz724Adapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        # Create a valid flight object
        flight = adapter._parse_flight_element(flight_elem)
        assert adapter._validate_flight_data(flight) is True
        
        # Test with invalid price
        invalid_flight = flight.copy()
        invalid_flight['price'] = 500000  # Below minimum
        assert adapter._validate_flight_data(invalid_flight) is False
        
        # Test with invalid duration
        invalid_flight = flight.copy()
        invalid_flight['duration_minutes'] = 1500  # Above maximum
        assert adapter._validate_flight_data(invalid_flight) is False
    
    def test_fare_conditions_extraction(self, sample_config, sample_flight_html):
        """Test fare conditions extraction"""
        adapter = Mz724Adapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        additional_data = adapter._extract_additional_data(flight_elem)
        assert 'fare_conditions' in additional_data
        assert 'cancellation' in additional_data['fare_conditions']
        assert 'changes' in additional_data['fare_conditions']
        assert 'baggage' in additional_data['fare_conditions']
    
    def test_available_seats_extraction(self, sample_config, sample_flight_html):
        """Test available seats extraction"""
        adapter = Mz724Adapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        additional_data = adapter._extract_additional_data(flight_elem)
        assert 'available_seats' in additional_data
        assert additional_data['available_seats'] == 12
    
    def test_aircraft_type_extraction(self, sample_config, sample_flight_html):
        """Test aircraft type extraction"""
        adapter = Mz724Adapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        additional_data = adapter._extract_additional_data(flight_elem)
        assert 'aircraft_type' in additional_data
        assert additional_data['aircraft_type'] == 'بوئینگ ۷۳۷'
    
    def test_domestic_flight_detection(self, sample_config):
        """Test domestic flight detection"""
        adapter = Mz724Adapter(sample_config)
        
        # Test domestic flight numbers
        assert adapter._is_domestic_flight('IR725') is True
        assert adapter._is_domestic_flight('W5123') is True
        assert adapter._is_domestic_flight('EP456') is True
        
        # Test international flight numbers
        assert adapter._is_domestic_flight('TK123') is False
        assert adapter._is_domestic_flight('EK789') is False
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params):
        """Test error handling in crawl process"""
        adapter = Mz724Adapter(sample_config)
        
        # Test with invalid search parameters
        invalid_params = sample_search_params.copy()
        invalid_params['origin'] = 'INVALID'
        results = await adapter.crawl(invalid_params)
        assert isinstance(results, list)
        assert len(results) == 0
        
        # Test with missing required field
        invalid_params = sample_search_params.copy()
        del invalid_params['departure_date']
        with pytest.raises(Exception):
            await adapter.crawl(invalid_params) 