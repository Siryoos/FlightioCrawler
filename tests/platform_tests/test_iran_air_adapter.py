import pytest
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
from persian_text import PersianTextProcessor


@pytest.fixture
def sample_config():
    return {
        "site_id": "iran_air",
        "name": "ایران ایر",
        "search_url": "https://www.iranair.com/flight-search",
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
                "miles_earned": ".miles-earned",
                "miles_required": ".miles-required",
                "promotion_code": ".promotion-code",
                "special_offers": ".special-offers",
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
                "miles_earned",
                "miles_required",
            ],
            "price_range": {"min": 1000000, "max": 100000000},
            "duration_range": {"min": 30, "max": 1440},
        },
        "rate_limiting": {
            "requests_per_second": 2,
            "burst_limit": 5,
            "cooldown_period": 60,
        },
        "error_handling": {
            "max_retries": 3,
            "retry_delay": 5,
            "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 300},
        },
        "monitoring": {
            "metrics": [
                "request_success_rate",
                "average_response_time",
                "error_rate",
                "data_quality_score",
            ],
            "alert_thresholds": {"error_rate": 0.1, "response_time": 5000},
        },
    }


@pytest.fixture
def sample_search_params():
    return {
        "origin": "تهران",
        "destination": "دبی",
        "departure_date": "2024-03-20",
        "passengers": 1,
        "seat_class": "اقتصادی",
        "trip_type": "رفت",
    }


@pytest.fixture
def sample_flight_html():
    return """
    <div class="flight-result">
        <div class="airline-name">ایران ایر</div>
        <div class="flight-number">IR ۷۲۱</div>
        <div class="departure-time">۰۸:۳۰</div>
        <div class="arrival-time">۱۰:۰۰</div>
        <div class="duration">۱ ساعت و ۳۰ دقیقه</div>
        <div class="price">۲,۵۰۰,۰۰۰ تومان</div>
        <div class="seat-class">اقتصادی</div>
        <div class="fare-conditions">
            <div class="refund-policy">قابل استرداد با کسر ۲۰ درصد</div>
            <div class="change-policy">قابل تغییر با کسر ۱۰ درصد</div>
            <div class="baggage-allowance">۲۰ کیلوگرم</div>
        </div>
        <div class="available-seats">۵ صندلی</div>
        <div class="aircraft-type">بوئینگ ۷۳۷</div>
        <div class="meal_service">صبحانه</div>
        <div class="special-services">ویلچر در دسترس</div>
        <div class="fare-rules">قوانین نرخ</div>
        <div class="booking-class">Y</div>
        <div class="fare-basis">YEE</div>
        <div class="ticket-validity">۳ ماه</div>
        <div class="miles-earned">۵۰۰ مایل</div>
        <div class="miles-required">۲۵,۰۰۰ مایل</div>
        <div class="promotion-code">IRAN۲۰</div>
        <div class="special-offers">تخفیف ویژه</div>
    </div>
    """


class TestIranAirAdapter:
    @pytest.mark.asyncio
    async def test_crawl_flow(self, sample_config, sample_search_params, mocker):
        # Mock page interactions
        mock_page = mocker.AsyncMock()
        mocker.patch("playwright.async_api.Page", return_value=mock_page)

        adapter = IranAirAdapter(sample_config)
        adapter.page = mock_page

        # Mock page content
        mock_page.content.return_value = sample_flight_html

        # Execute crawl
        results = await adapter.crawl(sample_search_params)

        # Verify results
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(result, dict) for result in results)
        assert all("airline" in result for result in results)
        assert all("flight_number" in result for result in results)
        assert all("price" in result for result in results)
        assert all("duration" in result for result in results)
        assert all("seat_class" in result for result in results)
        assert all("baggage_allowance" in result for result in results)
        assert all("refund_policy" in result for result in results)
        assert all("change_policy" in result for result in results)
        assert all("booking_class" in result for result in results)
        assert all("fare_basis" in result for result in results)
        assert all("ticket_validity" in result for result in results)
        assert all("miles_earned" in result for result in results)
        assert all("miles_required" in result for result in results)

    def test_persian_text_processing(self, sample_config, sample_flight_html):
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, "html.parser")
        flight_element = soup.select_one(".flight-result")

        flight_data = adapter._parse_flight_element(flight_element)

        assert flight_data["airline"] == "ایران ایر"
        assert flight_data["flight_number"] == "IR ۷۲۱"
        assert flight_data["price"] == 2500000
        assert flight_data["duration"] == "۱ ساعت و ۳۰ دقیقه"
        assert flight_data["seat_class"] == "اقتصادی"
        assert flight_data["baggage_allowance"] == "۲۰ کیلوگرم"
        assert flight_data["refund_policy"] == "قابل استرداد با کسر ۲۰ درصد"
        assert flight_data["change_policy"] == "قابل تغییر با کسر ۱۰ درصد"
        assert flight_data["booking_class"] == "Y"
        assert flight_data["fare_basis"] == "YEE"
        assert flight_data["ticket_validity"] == "۳ ماه"
        assert flight_data["miles_earned"] == "۵۰۰ مایل"
        assert flight_data["miles_required"] == "۲۵,۰۰۰ مایل"

    def test_fare_conditions_extraction(self, sample_config, sample_flight_html):
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, "html.parser")
        flight_element = soup.select_one(".flight-result")

        flight_data = adapter._parse_flight_element(flight_element)

        assert "fare_conditions" in flight_data
        assert "refund_policy" in flight_data
        assert "change_policy" in flight_data
        assert "baggage_allowance" in flight_data

    def test_special_services_extraction(self, sample_config, sample_flight_html):
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, "html.parser")
        flight_element = soup.select_one(".flight-result")

        flight_data = adapter._parse_flight_element(flight_element)

        assert "special_services" in flight_data
        assert flight_data["special_services"] == "ویلچر در دسترس"
        assert "meal_service" in flight_data
        assert flight_data["meal_service"] == "صبحانه"

    def test_miles_program_extraction(self, sample_config, sample_flight_html):
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, "html.parser")
        flight_element = soup.select_one(".flight-result")

        flight_data = adapter._parse_flight_element(flight_element)

        assert "miles_earned" in flight_data
        assert flight_data["miles_earned"] == "۵۰۰ مایل"
        assert "miles_required" in flight_data
        assert flight_data["miles_required"] == "۲۵,۰۰۰ مایل"

    def test_promotion_extraction(self, sample_config, sample_flight_html):
        adapter = IranAirAdapter(sample_config)
        soup = BeautifulSoup(sample_flight_html, "html.parser")
        flight_element = soup.select_one(".flight-result")

        flight_data = adapter._parse_flight_element(flight_element)

        assert "promotion_code" in flight_data
        assert flight_data["promotion_code"] == "IRAN۲۰"
        assert "special_offers" in flight_data
        assert flight_data["special_offers"] == "تخفیف ویژه"

    def test_data_validation(self, sample_config):
        adapter = IranAirAdapter(sample_config)

        # Test valid data
        valid_data = {
            "airline": "ایران ایر",
            "flight_number": "IR ۷۲۱",
            "departure_time": "۰۸:۳۰",
            "arrival_time": "۱۰:۰۰",
            "price": 2500000,
            "currency": "تومان",
            "seat_class": "اقتصادی",
            "duration_minutes": 90,
            "baggage_allowance": "۲۰ کیلوگرم",
            "refund_policy": "قابل استرداد",
            "change_policy": "قابل تغییر",
            "booking_class": "Y",
            "fare_basis": "YEE",
            "ticket_validity": "۳ ماه",
            "miles_earned": "۵۰۰ مایل",
            "miles_required": "۲۵,۰۰۰ مایل",
        }

        validated_results = adapter._validate_flight_data([valid_data])
        assert len(validated_results) == 1

        # Test invalid price
        invalid_price_data = valid_data.copy()
        invalid_price_data["price"] = 500000  # Below minimum
        validated_results = adapter._validate_flight_data([invalid_price_data])
        assert len(validated_results) == 0

        # Test invalid duration
        invalid_duration_data = valid_data.copy()
        invalid_duration_data["duration_minutes"] = 20  # Below minimum
        validated_results = adapter._validate_flight_data([invalid_duration_data])
        assert len(validated_results) == 0

        # Test missing required field
        missing_field_data = valid_data.copy()
        del missing_field_data["airline"]
        validated_results = adapter._validate_flight_data([missing_field_data])
        assert len(validated_results) == 0

    @pytest.mark.asyncio
    async def test_error_handling(self, sample_config, sample_search_params, mocker):
        adapter = IranAirAdapter(sample_config)

        # Mock page to simulate errors
        mock_page = mocker.AsyncMock()
        mock_page.goto.side_effect = Exception("Connection error")
        adapter.page = mock_page

        # Test error handling
        with pytest.raises(Exception) as exc_info:
            await adapter.crawl(sample_search_params)
        assert "Error crawling IranAir" in str(exc_info.value)

        # Test invalid search parameters
        invalid_params = sample_search_params.copy()
        del invalid_params["origin"]

        with pytest.raises(ValueError) as exc_info:
            await adapter.crawl(invalid_params)
