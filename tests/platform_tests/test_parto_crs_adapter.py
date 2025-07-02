import pytest
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from adapters.site_adapters.iranian_airlines.parto_crs_adapter import PartoCRSAdapter

@pytest.fixture
def sample_config():
    return {
        'site_id': 'parto_crs',
        'name': 'Parto CRS',
        'search_url': 'https://www.partocrs.com/b2b/flight-search',
        'b2b_credentials': {
            'username': 'test_user',
            'password': 'test_pass'
        },
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
                'class_field': 'select[name="cabin_class"]',
                'agency_code_field': 'input[name="agency_code"]',
                'commission_rate_field': 'input[name="commission_rate"]'
            },
            'results_parsing': {
                'container': '.flight-result',
                'price': '.price',
                'airline': '.airline-name',
                'duration': '.duration',
                'departure_time': '.departure-time',
                'arrival_time': '.arrival-time',
                'flight_number': '.flight-number',
                'seat_class': '.seat-class',
                'commission_info': '.commission-info',
                'fare_rules': '.fare-rules',
                'booking_class': '.booking-class',
                'available_seats': '.available-seats',
                'fare_basis': '.fare-basis',
                'ticket_validity': '.ticket-validity'
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
                'duration_minutes',
                'commission',
                'fare_rules',
                'booking_class'
            ],
            'price_range': {
                'min': 1000000,
                'max': 100000000
            },
            'duration_range': {
                'min': 30,
                'max': 1440
            },
            'commission_range': {
                'min': 0,
                'max': 100
            }
        }
    }

@pytest.fixture
def sample_search_params():
    return {
        'origin': 'THR',
        'destination': 'DXB',
        'departure_date': '2024-07-01',
        'passengers': 1,
        'seat_class': 'economy',
        'agency_code': 'TEST123',
        'commission_rate': 5
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
        <div class="commission-info">
            <div class="rate">۵ درصد</div>
            <div class="amount">۱۲۵,۰۰۰ ریال</div>
        </div>
        <div class="fare-rules">
            <div class="cancellation">قابل کنسلی با جریمه</div>
            <div class="changes">قابل تغییر با جریمه</div>
            <div class="refund">قابل استرداد با کسر ۲۰ درصد</div>
            <div class="baggage">۲۰ کیلوگرم</div>
        </div>
        <div class="booking-class">Y</div>
        <div class="available-seats">۱۲ صندلی</div>
        <div class="fare-basis">YEE5M</div>
        <div class="ticket-validity">۳ ماه</div>
    </div>
    """

class TestPartoCRSAdapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params):
        """Test the complete crawl flow"""
        adapter = PartoCRSAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)
        
        assert isinstance(results, list)
        if results:  # If any results were found
            assert all(isinstance(flight, dict) for flight in results)
            assert all('airline' in flight for flight in results)
            assert all('flight_number' in flight for flight in results)
            assert all('commission' in flight for flight in results)
    
    def test_persian_text_processing(self, sample_config, sample_flight_html):
        """Test Persian text processing functionality"""
        adapter = PartoCRSAdapter(sample_config)
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
    
    def test_commission_extraction(self, sample_config, sample_flight_html):
        """Test commission information extraction"""
        adapter = PartoCRSAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        b2b_data = adapter._extract_b2b_data(flight_elem)
        assert 'commission' in b2b_data
        assert b2b_data['commission']['rate'] == 5
        assert b2b_data['commission']['amount'] == 125000
    
    def test_fare_rules_extraction(self, sample_config, sample_flight_html):
        """Test fare rules extraction"""
        adapter = PartoCRSAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        b2b_data = adapter._extract_b2b_data(flight_elem)
        assert 'fare_rules' in b2b_data
        assert 'cancellation' in b2b_data['fare_rules']
        assert 'changes' in b2b_data['fare_rules']
        assert 'refund' in b2b_data['fare_rules']
        assert 'baggage' in b2b_data['fare_rules']
    
    def test_booking_class_extraction(self, sample_config, sample_flight_html):
        """Test booking class extraction"""
        adapter = PartoCRSAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        b2b_data = adapter._extract_b2b_data(flight_elem)
        assert 'booking_class' in b2b_data
        assert b2b_data['booking_class'] == 'Y'
    
    def test_fare_basis_extraction(self, sample_config, sample_flight_html):
        """Test fare basis extraction"""
        adapter = PartoCRSAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        b2b_data = adapter._extract_b2b_data(flight_elem)
        assert 'fare_basis' in b2b_data
        assert b2b_data['fare_basis'] == 'YEE5M'
    
    def test_ticket_validity_extraction(self, sample_config, sample_flight_html):
        """Test ticket validity extraction"""
        adapter = PartoCRSAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, 'html.parser')
        flight_elem = soup.select_one('.flight-result')
        
        b2b_data = adapter._extract_b2b_data(flight_elem)
        assert 'ticket_validity' in b2b_data
        assert b2b_data['ticket_validity'] == '۳ ماه'
    
    def test_data_validation(self, sample_config, sample_flight_html):
        """Test flight data validation"""
        adapter = PartoCRSAdapter(sample_config)
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
        
        # Test with invalid commission
        invalid_flight = flight.copy()
        invalid_flight['commission']['rate'] = 150  # Above maximum
        assert adapter._validate_flight_data(invalid_flight) is False
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params):
        """Test error handling in crawl process"""
        adapter = PartoCRSAdapter(sample_config)
        
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
        
        # Test with invalid B2B credentials
        invalid_config = sample_config.copy()
        invalid_config['b2b_credentials']['username'] = 'invalid'
        adapter = PartoCRSAdapter(invalid_config)
        with pytest.raises(Exception):
            await adapter.crawl(sample_search_params) 
