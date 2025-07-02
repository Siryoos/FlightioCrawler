import types
import sys
import pytest

# Stub external dependencies
sys.modules["bs4"] = types.ModuleType("bs4")
sys.modules["bs4"].BeautifulSoup = lambda *a, **k: None
sys.modules["playwright"] = types.ModuleType("playwright")
sys.modules["playwright.async_api"] = types.ModuleType("playwright.async_api")
sys.modules["playwright.async_api"].TimeoutError = Exception


base_mod = types.ModuleType("adapters.base_adapters.airline_crawler")


class AirlineCrawler:
    def __init__(self, config):
        self.config = config
        self.page = None


base_mod.AirlineCrawler = AirlineCrawler
sys.modules["adapters.base_adapters.airline_crawler"] = base_mod

from adapters.site_adapters.international_airlines.pegasus_adapter import PegasusAdapter


@pytest.fixture
def sample_config():
    fields = {
        "airline": ".airline",
        "flight_number": ".number",
        "departure_time": ".dep",
        "arrival_time": ".arr",
        "duration": ".dur",
        "price": ".price",
        "cabin_class": ".seat",
    }
    return {
        "search_url": "https://example.com",
        "extraction_config": {"search_form": {}, "results_parsing": fields},
        "data_validation": {
            "required_fields": [
                "airline",
                "flight_number",
                "departure_time",
                "arrival_time",
                "price",
                "currency",
                "cabin_class",
                "duration_minutes",
            ],
            "price_range": {"min": 1, "max": 1000000},
            "duration_range": {"min": 30, "max": 600},
        },
        "rate_limiting": {
            "requests_per_second": 1,
            "burst_limit": 1,
            "cooldown_period": 1,
        },
        "error_handling": {"max_retries": 1, "retry_delay": 1, "circuit_breaker": {}},
        "monitoring": {},
    }


@pytest.fixture
def adapter(sample_config):
    return PegasusAdapter(sample_config)


def test_validate_search_params(adapter):
    params = {
        "origin": "IST",
        "destination": "DXB",
        "departure_date": "2024-01-01",
        "cabin_class": "economy",
    }
    adapter._validate_search_params(params)
    params.pop("origin")
    with pytest.raises(ValueError):
        adapter._validate_search_params(params)


def test_validate_flight_data(adapter):
    flight = {
        "airline": "Pegasus",
        "flight_number": "PC123",
        "departure_time": "08:00",
        "arrival_time": "10:00",
        "price": 200,
        "currency": "EUR",
        "cabin_class": "economy",
        "duration_minutes": 120,
    }
    results = adapter._validate_flight_data([flight])
    assert results == [flight]
    flight["price"] = 0
    assert adapter._validate_flight_data([flight]) == []
