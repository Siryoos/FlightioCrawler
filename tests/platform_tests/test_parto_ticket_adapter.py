import pytest
from datetime import datetime
from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import (
    PartoTicketAdapter,
)
from utils.persian_text_processor import PersianTextProcessor


@pytest.fixture
def sample_config():
    return {
        "site_id": "parto_ticket",
        "name": "Parto Ticket",
        "search_url": "https://www.parto-ticket.ir/flight-search",
        "enable_crs_integration": True,
        "crs_config": {
            "site_id": "parto_crs",
            "b2b_credentials": {"username": "test_user", "password": "test_pass"},
        },
        "crs_agency_code": "TEST123",
        "crs_commission_rate": 5,
        "persian_processing": {
            "rtl_support": True,
            "jalali_calendar": True,
            "persian_numerals": True,
        },
        "extraction_config": {
            "search_form": {
                "origin_field": 'input[name="origin"]',
                "destination_field": 'input[name="destination"]',
                "date_field": 'input[name="departure_date"]',
                "passengers_field": 'select[name="passengers"]',
                "class_field": 'select[name="cabin_class"]',
            },
            "results_parsing": {
                "container": ".flight-result",
                "price": ".price",
                "airline": ".airline-name",
                "duration": ".duration",
                "departure_time": ".departure-time",
                "arrival_time": ".arrival-time",
                "flight_number": ".flight-number",
                "seat_class": ".seat-class",
                "fare_conditions": ".fare-conditions",
                "available_seats": ".available-seats",
                "aircraft_type": ".aircraft-type",
                "ticket_type": ".ticket-type",
            },
        },
        "data_validation": {
            "required_fields": [
                "airline",
                "flight_number",
                "departure_time",
                "arrival_time",
                "price",
                "currency",
                "seat_class",
                "duration_minutes",
            ],
            "price_range": {"min": 1000000, "max": 100000000},
            "duration_range": {"min": 30, "max": 1440},
        },
    }


@pytest.fixture
def sample_search_params():
    return {
        "origin": "تهران",
        "destination": "مشهد",
        "departure_date": "1403-01-01",
        "passengers": 1,
        "seat_class": "اقتصادی",
        "agency_code": "TEST123",
        "commission_rate": 5,
    }


@pytest.fixture
def sample_flight_html():
    return """
    <div class="flight-result">
        <div class="airline-name">ایران ایر</div>
        <div class="flight-number">IR-123</div>
        <div class="departure-time">08:00</div>
        <div class="arrival-time">09:30</div>
        <div class="duration">1:30</div>
        <div class="price">2,500,000 تومان</div>
        <div class="seat-class">اقتصادی</div>
        <div class="fare-conditions">
            <div class="cancellation">قابل کنسلی با جریمه</div>
            <div class="change">قابل تغییر با جریمه</div>
            <div class="refund">قابل استرداد</div>
        </div>
        <div class="available-seats">5 صندلی باقیمانده</div>
        <div class="aircraft-type">بوئینگ 737</div>
        <div class="ticket-type">بلیط سیستمی</div>
    </div>
    """


class TestPartoTicketAdapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params):
        adapter = PartoTicketAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(flight, dict) for flight in results)
        assert all("airline" in flight for flight in results)
        assert all("flight_number" in flight for flight in results)
        assert all("price" in flight for flight in results)
        assert all("commission" in flight for flight in results)

    @pytest.mark.asyncio
    async def test_persian_text_processing(self, sample_config, sample_flight_html):
        adapter = PartoTicketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert flight_data["airline"] == "ایران ایر"
        assert flight_data["flight_number"] == "IR-123"
        assert flight_data["price"] == 2500000
        assert flight_data["currency"] == "تومان"
        assert flight_data["duration_minutes"] == 90
        assert flight_data["seat_class"] == "اقتصادی"

    @pytest.mark.asyncio
    async def test_crs_integration(self, sample_config, sample_search_params):
        adapter = PartoTicketAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)

        assert all("commission" in flight for flight in results)
        assert all("fare_rules" in flight for flight in results)
        assert all("booking_class" in flight for flight in results)
        assert all("fare_basis" in flight for flight in results)
        assert all("ticket_validity" in flight for flight in results)

    @pytest.mark.asyncio
    async def test_fare_conditions_extraction(self, sample_config, sample_flight_html):
        adapter = PartoTicketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "fare_conditions" in flight_data
        assert flight_data["fare_conditions"]["cancellation"] == "قابل کنسلی با جریمه"
        assert flight_data["fare_conditions"]["change"] == "قابل تغییر با جریمه"
        assert flight_data["fare_conditions"]["refund"] == "قابل استرداد"

    @pytest.mark.asyncio
    async def test_available_seats_extraction(self, sample_config, sample_flight_html):
        adapter = PartoTicketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "available_seats" in flight_data
        assert flight_data["available_seats"] == 5

    @pytest.mark.asyncio
    async def test_aircraft_type_extraction(self, sample_config, sample_flight_html):
        adapter = PartoTicketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "aircraft_type" in flight_data
        assert flight_data["aircraft_type"] == "بوئینگ 737"

    @pytest.mark.asyncio
    async def test_ticket_type_extraction(self, sample_config, sample_flight_html):
        adapter = PartoTicketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "ticket_type" in flight_data
        assert flight_data["ticket_type"] == "بلیط سیستمی"

    @pytest.mark.asyncio
    async def test_data_validation(self, sample_config, sample_search_params):
        adapter = PartoTicketAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)

        for flight in results:
            assert all(
                field in flight
                for field in sample_config["data_validation"]["required_fields"]
            )
            assert (
                sample_config["data_validation"]["price_range"]["min"]
                <= flight["price"]
                <= sample_config["data_validation"]["price_range"]["max"]
            )
            assert (
                sample_config["data_validation"]["duration_range"]["min"]
                <= flight["duration_minutes"]
                <= sample_config["data_validation"]["duration_range"]["max"]
            )
            assert 0 <= flight["commission"] <= 100

    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params):
        adapter = PartoTicketAdapter(sample_config)

        # Test with invalid search parameters
        invalid_params = sample_search_params.copy()
        invalid_params["origin"] = "invalid_city"
        results = await adapter.crawl(invalid_params)
        assert isinstance(results, list)
        assert len(results) == 0

        # Test with missing required fields
        invalid_params = sample_search_params.copy()
        del invalid_params["origin"]
        with pytest.raises(ValueError):
            await adapter.crawl(invalid_params)
