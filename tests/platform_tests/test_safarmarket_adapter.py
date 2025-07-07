import pytest
from datetime import datetime
from adapters.site_adapters.iranian_airlines.safarmarket_adapter import (
    SafarmarketAdapter,
)
from persian_text import PersianTextProcessor


@pytest.fixture
def sample_config():
    return {
        "site_id": "safarmarket",
        "name": "سفارمارکت",
        "search_url": "https://www.safarmarket.com/flight-search",
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
                "trip_type_field": 'select[name="trip_type"]',
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
                "baggage_allowance": ".baggage-allowance",
                "meal_service": ".meal-service",
                "special_services": ".special-services",
                "refund_policy": ".refund-policy",
                "change_policy": ".change-policy",
                "fare_rules": ".fare-rules",
                "booking_class": ".booking-class",
                "fare_basis": ".fare-basis",
                "ticket_validity": ".ticket-validity",
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
                "baggage_allowance",
                "refund_policy",
                "change_policy",
                "booking_class",
                "fare_basis",
                "ticket_validity",
            ],
            "price_range": {"min": 1000000, "max": 100000000},
            "duration_range": {"min": 30, "max": 1440},
        },
    }


@pytest.fixture
def sample_search_params():
    return {
        "origin": "تهران",
        "destination": "دبی",
        "departure_date": "1403-01-01",
        "passengers": 1,
        "seat_class": "اقتصادی",
        "trip_type": "یک طرفه",
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
        <div class="fare-conditions">قابل کنسلی با جریمه 20%</div>
        <div class="available-seats">5 صندلی باقیمانده</div>
        <div class="aircraft-type">بوئینگ 737</div>
        <div class="baggage-allowance">20 کیلوگرم</div>
        <div class="meal-service">صبحانه و نهار</div>
        <div class="special-services">
            <ul>
                <li>ترانسفر فرودگاهی</li>
                <li>خدمات ویژه مسافران</li>
                <li>پشتیبانی 24 ساعته</li>
            </ul>
        </div>
        <div class="refund-policy">قابل استرداد با کسر 20% تا 24 ساعت قبل از پرواز</div>
        <div class="change-policy">قابل تغییر با کسر 10% تا 48 ساعت قبل از پرواز</div>
        <div class="fare-rules">
            <ul>
                <li>حداقل اقامت: 2 شب</li>
                <li>حداکثر اقامت: 30 شب</li>
                <li>تغییر مسیر: مجاز با پرداخت تفاوت قیمت</li>
            </ul>
        </div>
        <div class="booking-class">Y</div>
        <div class="fare-basis">YEE3M</div>
        <div class="ticket-validity">3 ماه</div>
    </div>
    """


class TestSafarmarketAdapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params):
        adapter = SafarmarketAdapter(sample_config)
        results = await adapter.crawl(sample_search_params)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(flight, dict) for flight in results)
        assert all("airline" in flight for flight in results)
        assert all("flight_number" in flight for flight in results)
        assert all("price" in flight for flight in results)

    @pytest.mark.asyncio
    async def test_persian_text_processing(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert flight_data["airline"] == "ایران ایر"
        assert flight_data["flight_number"] == "IR-123"
        assert flight_data["price"] == 2500000
        assert flight_data["currency"] == "تومان"
        assert flight_data["duration_minutes"] == 90
        assert flight_data["seat_class"] == "اقتصادی"
        assert flight_data["baggage_allowance"] == "20 کیلوگرم"
        assert flight_data["meal_service"] == "صبحانه و نهار"

    @pytest.mark.asyncio
    async def test_fare_conditions_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "fare_conditions" in flight_data
        assert flight_data["fare_conditions"] == "قابل کنسلی با جریمه 20%"

    @pytest.mark.asyncio
    async def test_special_services_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "special_services" in flight_data
        assert isinstance(flight_data["special_services"], list)
        assert len(flight_data["special_services"]) == 3
        assert "ترانسفر فرودگاهی" in flight_data["special_services"]
        assert "خدمات ویژه مسافران" in flight_data["special_services"]
        assert "پشتیبانی 24 ساعته" in flight_data["special_services"]

    @pytest.mark.asyncio
    async def test_available_seats_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "available_seats" in flight_data
        assert flight_data["available_seats"] == 5

    @pytest.mark.asyncio
    async def test_aircraft_type_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "aircraft_type" in flight_data
        assert flight_data["aircraft_type"] == "بوئینگ 737"

    @pytest.mark.asyncio
    async def test_refund_policy_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "refund_policy" in flight_data
        assert (
            flight_data["refund_policy"]
            == "قابل استرداد با کسر 20% تا 24 ساعت قبل از پرواز"
        )

    @pytest.mark.asyncio
    async def test_change_policy_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "change_policy" in flight_data
        assert (
            flight_data["change_policy"]
            == "قابل تغییر با کسر 10% تا 48 ساعت قبل از پرواز"
        )

    @pytest.mark.asyncio
    async def test_fare_rules_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "fare_rules" in flight_data
        assert isinstance(flight_data["fare_rules"], list)
        assert len(flight_data["fare_rules"]) == 3
        assert "حداقل اقامت: 2 شب" in flight_data["fare_rules"]
        assert "حداکثر اقامت: 30 شب" in flight_data["fare_rules"]
        assert "تغییر مسیر: مجاز با پرداخت تفاوت قیمت" in flight_data["fare_rules"]

    @pytest.mark.asyncio
    async def test_booking_class_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "booking_class" in flight_data
        assert flight_data["booking_class"] == "Y"

    @pytest.mark.asyncio
    async def test_fare_basis_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "fare_basis" in flight_data
        assert flight_data["fare_basis"] == "YEE3M"

    @pytest.mark.asyncio
    async def test_ticket_validity_extraction(self, sample_config, sample_flight_html):
        adapter = SafarmarketAdapter(sample_config)
        flight_data = await adapter._parse_flight_element(sample_flight_html)

        assert "ticket_validity" in flight_data
        assert flight_data["ticket_validity"] == "3 ماه"

    @pytest.mark.asyncio
    async def test_data_validation(self, sample_config, sample_search_params):
        adapter = SafarmarketAdapter(sample_config)
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

    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params):
        adapter = SafarmarketAdapter(sample_config)

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
