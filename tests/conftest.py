import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Global Test Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_flight_data():
    """Sample flight data for testing."""
    return {
        "airline": "Iran Air",
        "flight_number": "IR-123",
        "departure_time": "08:30",
        "arrival_time": "12:45",
        "departure_date": "2024-06-01",
        "arrival_date": "2024-06-01",
        "price": 2500000,
        "currency": "IRR",
        "duration_minutes": 255,
        "seat_class": "economy",
        "aircraft_type": "Airbus A320",
        "baggage_allowance": "20kg",
        "is_direct": True,
        "stops": 0,
        "route": "THR-IST",
        "booking_class": "Y",
        "fare_basis": "YIF",
        "refundable": True,
        "changeable": True,
        "source": "test_adapter"
    }


@pytest.fixture
def sample_search_params():
    """Sample search parameters for testing."""
    return {
        "origin": "THR",
        "destination": "IST",
        "departure_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "return_date": (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d"),
        "adults": 1,
        "children": 0,
        "infants": 0,
        "cabin_class": "economy",
        "trip_type": "round_trip"
    }


@pytest.fixture
def enhanced_adapter_config():
    """Enhanced adapter configuration for testing."""
    return {
        "base_url": "https://test-airline.com",
        "search_url": "https://test-airline.com/search",
        "rate_limiting": {
            "requests_per_second": 2.0,
            "burst_limit": 5,
            "cooldown_period": 60
        },
        "error_handling": {
            "max_retries": 3,
            "retry_delay": 1,
            "circuit_breaker": {
                "failure_threshold": 5,
                "recovery_timeout": 30
            }
        },
        "monitoring": {
            "enabled": True,
            "collect_metrics": True,
            "log_performance": True
        },
        "extraction_config": {
            "timeout": 30,
            "wait_for_results": 10,
            "max_results": 50,
            "search_form": {
                "origin_field": "#origin",
                "destination_field": "#destination",
                "departure_date_field": "#departure",
                "return_date_field": "#return",
                "adults_field": "#adults",
                "children_field": "#children",
                "infants_field": "#infants",
                "cabin_class_field": "#cabin_class",
                "search_button": "#search_button"
            },
            "results_parsing": {
                "container": ".flight-result",
                "airline": ".airline",
                "flight_number": ".flight-number",
                "departure_time": ".departure-time",
                "arrival_time": ".arrival-time",
                "price": ".price",
                "currency": ".currency",
                "duration": ".duration",
                "seat_class": ".seat-class"
            }
        },
        "validation": {
            "required_fields": [
                "airline", "flight_number", "departure_time", "arrival_time",
                "price", "currency", "duration_minutes", "seat_class"
            ],
            "price_range": {"min": 100000, "max": 50000000},
            "duration_range": {"min": 30, "max": 1440}
        }
    }


@pytest.fixture
def mock_browser_session():
    """Mock browser session for testing."""
    mock_session = AsyncMock()
    mock_page = AsyncMock()
    
    # Configure mock page
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(return_value=True)
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.select_option = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Mock content</body></html>")
    mock_page.screenshot = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=[])
    
    # Configure mock session
    mock_session.new_page = AsyncMock(return_value=mock_page)
    mock_session.close = AsyncMock()
    
    return mock_session, mock_page


@pytest.fixture
def mock_http_session():
    """Mock HTTP session for testing."""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    
    # Configure mock response
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<html><body>Mock HTTP response</body></html>")
    mock_response.json = AsyncMock(return_value={"status": "success", "data": []})
    mock_response.headers = {"Content-Type": "text/html"}
    
    # Configure mock session
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.put = AsyncMock(return_value=mock_response)
    mock_session.delete = AsyncMock(return_value=mock_response)
    mock_session.close = AsyncMock()
    
    return mock_session, mock_response


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter for testing."""
    mock_limiter = Mock()
    mock_limiter.wait_for_domain = AsyncMock()
    mock_limiter.check_rate_limit = Mock(return_value=True)
    mock_limiter.get_wait_time = Mock(return_value=0)
    mock_limiter.is_rate_limited = Mock(return_value=False)
    mock_limiter.reset_limits = Mock()
    
    return mock_limiter


@pytest.fixture
def mock_error_handler():
    """Mock error handler for testing."""
    mock_handler = Mock()
    mock_handler.handle_error = AsyncMock()
    mock_handler.should_retry = Mock(return_value=True)
    mock_handler.get_retry_delay = Mock(return_value=1)
    mock_handler.circuit_breaker_open = Mock(return_value=False)
    mock_handler.reset_circuit_breaker = Mock()
    
    return mock_handler


@pytest.fixture
def mock_monitoring():
    """Mock monitoring system for testing."""
    mock_monitor = Mock()
    mock_monitor.start_crawl = AsyncMock()
    mock_monitor.end_crawl = AsyncMock()
    mock_monitor.log_error = AsyncMock()
    mock_monitor.log_performance = AsyncMock()
    mock_monitor.get_metrics = Mock(return_value={})
    mock_monitor.reset_metrics = Mock()
    
    return mock_monitor


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing parsing."""
    return """
    <html>
    <body>
        <div class="flight-result">
            <div class="airline">Iran Air</div>
            <div class="flight-number">IR-123</div>
            <div class="departure-time">08:30</div>
            <div class="arrival-time">12:45</div>
            <div class="price">2,500,000 تومان</div>
            <div class="currency">IRR</div>
            <div class="duration">4 ساعت 15 دقیقه</div>
            <div class="seat-class">اقتصادی</div>
            <div class="aircraft-type">Airbus A320</div>
            <div class="baggage">20 کیلو</div>
        </div>
        <div class="flight-result">
            <div class="airline">Mahan Air</div>
            <div class="flight-number">W5-456</div>
            <div class="departure-time">14:15</div>
            <div class="arrival-time">18:30</div>
            <div class="price">3,200,000 تومان</div>
            <div class="currency">IRR</div>
            <div class="duration">4 ساعت 15 دقیقه</div>
            <div class="seat-class">اقتصادی</div>
            <div class="aircraft-type">Boeing 737</div>
            <div class="baggage">20 کیلو</div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_json_response():
    """Sample JSON response for testing API adapters."""
    return {
        "status": "success",
        "data": {
            "flights": [
                {
                    "airline": "Iran Air",
                    "flight_number": "IR-123",
                    "departure": {
                        "time": "08:30",
                        "date": "2024-06-01",
                        "airport": "THR"
                    },
                    "arrival": {
                        "time": "12:45",
                        "date": "2024-06-01",
                        "airport": "IST"
                    },
                    "price": {
                        "amount": 2500000,
                        "currency": "IRR"
                    },
                    "duration": 255,
                    "seat_class": "economy",
                    "aircraft": "Airbus A320",
                    "baggage": "20kg",
                    "stops": 0
                }
            ]
        },
        "metadata": {
            "total_results": 1,
            "search_time": 1.5,
            "timestamp": "2024-06-01T10:00:00Z"
        }
    }


@pytest.fixture
def performance_test_data():
    """Large dataset for performance testing."""
    flights = []
    airlines = ["Iran Air", "Mahan Air", "Aseman Airlines", "Kish Air", "Zagros Airlines"]
    
    for i in range(100):
        flights.append({
            "airline": airlines[i % len(airlines)],
            "flight_number": f"FL{1000 + i}",
            "departure_time": f"{8 + (i % 12):02d}:30",
            "arrival_time": f"{10 + (i % 12):02d}:45",
            "price": 2000000 + (i * 10000),
            "currency": "IRR",
            "duration_minutes": 120 + (i % 60),
            "seat_class": "economy",
            "aircraft_type": f"Aircraft {i % 5}",
            "route": f"Route {i % 20}",
            "stops": i % 3
        })
    
    return flights


@pytest.fixture
def security_test_payloads():
    """Security test payloads for testing input validation."""
    return {
        "sql_injection": [
            "'; DROP TABLE flights; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "'; INSERT INTO flights VALUES ('malicious'); --"
        ],
        "xss_payloads": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>"
        ],
        "command_injection": [
            "; rm -rf /",
            "| cat /etc/passwd",
            "& net user hacker password /add",
            "`rm -rf /`"
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd"
        ]
    }


@pytest.fixture
def mock_database():
    """Mock database for testing data persistence."""
    mock_db = Mock()
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.fetch_all = AsyncMock(return_value=[])
    mock_db.fetch_one = AsyncMock(return_value=None)
    mock_db.insert = AsyncMock()
    mock_db.update = AsyncMock()
    mock_db.delete = AsyncMock()
    
    return mock_db


@pytest.fixture
def mock_cache():
    """Mock cache for testing caching functionality."""
    mock_cache = Mock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    mock_cache.delete = AsyncMock()
    mock_cache.clear = AsyncMock()
    mock_cache.exists = AsyncMock(return_value=False)
    mock_cache.expire = AsyncMock()
    
    return mock_cache


# Test Utilities
@pytest.fixture
def test_helpers():
    """Test helper functions."""
    class TestHelpers:
        @staticmethod
        def create_mock_flight(airline="Test Air", price=1000000, currency="IRR"):
            """Create a mock flight result."""
            return {
                "airline": airline,
                "flight_number": f"TA{hash(airline) % 1000}",
                "departure_time": "08:30",
                "arrival_time": "12:45",
                "price": price,
                "currency": currency,
                "duration_minutes": 255,
                "seat_class": "economy"
            }
        
        @staticmethod
        def validate_flight_structure(flight_data):
            """Validate flight data structure."""
            required_fields = ["airline", "flight_number", "price", "currency"]
            return all(field in flight_data for field in required_fields)
        
        @staticmethod
        def compare_flights(flight1, flight2):
            """Compare two flight results."""
            return (
                flight1.get("airline") == flight2.get("airline") and
                flight1.get("flight_number") == flight2.get("flight_number") and
                flight1.get("price") == flight2.get("price")
            )
    
    return TestHelpers()


# Environment-specific fixtures
@pytest.fixture
def test_environment():
    """Test environment configuration."""
    return {
        "is_ci": os.getenv("CI", "false").lower() == "true",
        "test_timeout": int(os.getenv("TEST_TIMEOUT", "30")),
        "skip_slow_tests": os.getenv("SKIP_SLOW_TESTS", "false").lower() == "true",
        "mock_external_services": os.getenv("MOCK_EXTERNAL_SERVICES", "true").lower() == "true"
    }


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Cleanup code here if needed
    pass
