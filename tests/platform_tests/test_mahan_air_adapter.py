import types
import sys
import pytest

# Stub external dependencies so the adapter module can be imported without the real packages
sys.modules['bs4'] = types.ModuleType('bs4')
sys.modules['bs4'].BeautifulSoup = lambda *a, **k: None
sys.modules['playwright'] = types.ModuleType('playwright')
sys.modules['playwright.async_api'] = types.ModuleType('playwright.async_api')
sys.modules['playwright.async_api'].TimeoutError = Exception

utils_ptp = types.ModuleType('utils.persian_text_processor')
class DummyPersianProcessor:
    def process_text(self, text):
        return text
    def process_date(self, text):
        return text
    def process_price(self, text):
        return 100000
utils_ptp.PersianTextProcessor = DummyPersianProcessor
sys.modules['utils.persian_text_processor'] = utils_ptp
base_mod = types.ModuleType('adapters.base_adapters.persian_airline_crawler')
class PersianAirlineCrawler:
    def __init__(self, config):
        self.config = config
        self.page = None
base_mod.PersianAirlineCrawler = PersianAirlineCrawler
sys.modules['adapters.base_adapters.persian_airline_crawler'] = base_mod

from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter

@pytest.fixture
def sample_config():
    fields = {
        'airline': '.airline',
        'flight_number': '.number',
        'departure_time': '.dep',
        'arrival_time': '.arr',
        'duration': '.dur',
        'price': '.price',
        'seat_class': '.seat',
        'fare_conditions': '.unused',
        'available_seats': '.unused',
        'aircraft_type': '.unused',
        'baggage_allowance': '.unused',
        'meal_service': '.unused',
        'special_services': '.unused',
        'refund_policy': '.unused',
        'change_policy': '.unused',
        'fare_rules': '.unused',
        'booking_class': '.unused',
        'fare_basis': '.unused',
        'ticket_validity': '.unused',
        'miles_earned': '.unused',
        'miles_required': '.unused',
        'promotion_code': '.unused',
        'special_offers': '.unused'
    }
    return {
        'search_url': 'https://example.com',
        'extraction_config': {
            'search_form': {},
            'results_parsing': fields
        },
        'data_validation': {
            'required_fields': ['airline','flight_number','departure_time','arrival_time','price','currency','seat_class','duration_minutes'],
            'price_range': {'min': 1, 'max': 1000000},
            'duration_range': {'min': 30, 'max': 600}
        },
        'rate_limiting': {'requests_per_second': 1, 'burst_limit': 1, 'cooldown_period': 1},
        'error_handling': {'max_retries': 1, 'retry_delay': 1, 'circuit_breaker': {}},
        'monitoring': {}
    }

@pytest.fixture
def adapter(sample_config):
    return MahanAirAdapter(sample_config)

def test_validate_search_params(adapter):
    params = {
        'origin': 'THR',
        'destination': 'MHD',
        'departure_date': '2024-01-01',
        'passengers': 1,
        'seat_class': 'economy'
    }
    # Should not raise
    adapter._validate_search_params(params)
    params.pop('origin')
    with pytest.raises(ValueError):
        adapter._validate_search_params(params)

def test_validate_flight_data(adapter):
    flight = {
        'airline': 'Mahan',
        'flight_number': 'W5123',
        'departure_time': '08:00',
        'arrival_time': '09:00',
        'price': 200000,
        'currency': 'IRR',
        'seat_class': 'economy',
        'duration_minutes': 60
    }
    results = adapter._validate_flight_data([flight])
    assert results == [flight]
    flight['price'] = 0
    assert adapter._validate_flight_data([flight]) == []
