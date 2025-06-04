import pytest
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
from data.transformers.persian_text_processor import PersianTextProcessor

@pytest.fixture
def sample_config():
    return {
        'site_id': 'iran_air',
        'name': 'Iran Air',
        'search_url': 'https://www.iranair.com/flight-search',
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
                'price': '.price-persian',
                'airline': '.airline-persian',
                'duration': '.duration-persian',
                'departure_time': '.departure-time',
                'arrival_time': '.arrival-time',
                'flight_number': '.flight-number',
                'seat_class': '.seat-class'
            }
        },
        'data_validation': {
            'required_fields': [
                'airline_code',
                'flight_number',
                'origin_airport',
                'destination_airport',
                'departure_time',
                'arrival_time',
                'price',
                'currency'
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
        'destination': 'IST',
        'departure_date': '2024-07-01',
        'passengers': 1,
        'seat_class': 'economy'
    }

@pytest.fixture
def sample_flight_html():
    return """
    <div class="flight-result">
        <div class="airline-persian">ایران ایر</div>
        <div class="flight-number">IR ۷۲۵</div>
        <div class="departure-time">۰۸:۳۰</div>
        <div class="arrival-time">۱۰:۴۵</div>
        <div class="duration-persian">۲ ساعت و ۱۵ دقیقه</div>
        <div class="price-persian">۲,۵۰۰,۰۰۰ ریال</div>
        <div class="seat-class">اکونومی</div>
        <div class="fare-conditions">
            <div class="cancellation">قابل کنسلی با جریمه</div>
            <div class="changes">قابل تغییر با جریمه</div>
            <div class="baggage">۲۰ کیلوگرم</div>
        </div>
        <div class="available-seats">۱۲ صندلی</div>
    </div>
    """

class TestIranAirAdapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params):
        """Test the complete crawl flow"""
        adapter = IranAirAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)
        
        assert isinstance(results, list)
        if results:  # If any results were found
            assert all(isinstance(flight, dict) for flight in results)
            assert all('airline_code' in flight for flight in results)
            assert all('flight_number' in flight for flight in results)
            
    def test_persian_text_processing(self, sample_config, sample_flight_html):
        """Test Persian text processing functionality"""
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        # Test flight number extraction
        flight_number = adapter._extract_flight_number(flight_elem)
        assert flight_number == 'IR725'
        
        # Test price extraction
        price = adapter._extract_price(flight_elem)
        assert price == 2500000
        
        # Test currency extraction
        currency = adapter._extract_currency(flight_elem)
        assert currency == 'IRR'
        
        # Test duration extraction
        duration = adapter._extract_duration(flight_elem)
        assert duration == 135  # 2 hours and 15 minutes
        
        # Test fare class extraction
        fare_class = adapter._extract_fare_class(flight_elem)
        assert fare_class == 'economy'
        
    def test_date_conversion(self, sample_config, sample_search_params):
        """Test Jalali date conversion"""
        adapter = IranAirAdapter(sample_config)
        
        # Test Gregorian to Jalali conversion
        gregorian_date = datetime.strptime(sample_search_params['departure_date'], '%Y-%m-%d')
        jalali_date = adapter.text_processor.convert_gregorian_to_jalali(gregorian_date)
        assert isinstance(jalali_date, str)
        assert '/' in jalali_date
        
        # Test Jalali to Gregorian conversion
        gregorian_date = adapter.text_processor.convert_jalali_date(jalali_date)
        assert isinstance(gregorian_date, datetime)
        
    def test_data_validation(self, sample_config, sample_flight_html):
        """Test flight data validation"""
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        # Create a valid flight object
        flight = {
            'airline_code': 'IRA',
            'flight_number': 'IR725',
            'origin_airport': 'THR',
            'destination_airport': 'IST',
            'departure_time': datetime.strptime('08:30', '%H:%M'),
            'arrival_time': datetime.strptime('10:45', '%H:%M'),
            'duration_minutes': 135,
            'price': 2500000,
            'currency': 'IRR',
            'fare_class': 'economy'
        }
        
        # Test validation
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
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        conditions = adapter._extract_fare_conditions(flight_elem)
        assert isinstance(conditions, dict)
        assert 'cancellation' in conditions
        assert 'changes' in conditions
        assert 'baggage' in conditions
        
    def test_available_seats_extraction(self, sample_config, sample_flight_html):
        """Test available seats extraction"""
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        seats = adapter._extract_available_seats(flight_elem)
        assert isinstance(seats, int)
        assert seats == 12
        
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params):
        """Test error handling in crawl process"""
        adapter = IranAirAdapter(sample_config)
        
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