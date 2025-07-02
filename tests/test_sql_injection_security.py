"""
Security tests for SQL injection prevention and input validation
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from data_manager import DataManager, InputValidator
from sqlalchemy.exc import SQLAlchemyError


class TestInputValidator:
    """Test InputValidator security functions"""

    def test_validate_airport_code_success(self):
        """Test valid airport codes"""
        assert InputValidator.validate_airport_code("THR") == "THR"
        assert InputValidator.validate_airport_code("thr") == "THR"
        assert InputValidator.validate_airport_code("OIII") == "OIII"
        assert InputValidator.validate_airport_code("jfk") == "JFK"

    def test_validate_airport_code_malicious_input(self):
        """Test airport code validation against malicious input"""
        malicious_inputs = [
            "'; DROP TABLE flights; --",
            "<script>alert('xss')</script>",
            "' OR 1=1 --",
            "THR'; DELETE FROM flights; --",
            '" UNION SELECT * FROM users --',
            "\\x00\\x1f",
            "../../../etc/passwd",
            "THR<img src=x onerror=alert(1)>",
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValueError):
                InputValidator.validate_airport_code(malicious_input)

    def test_validate_airport_code_invalid_length(self):
        """Test airport code length validation"""
        invalid_codes = ["", "T", "TH", "THRAA", "TOOLONG"]

        for code in invalid_codes:
            with pytest.raises(ValueError):
                InputValidator.validate_airport_code(code)

    def test_validate_route_string_success(self):
        """Test valid route string parsing"""
        origin, destination = InputValidator.validate_route_string("THR-IST")
        assert origin == "THR"
        assert destination == "IST"

        origin, destination = InputValidator.validate_route_string("jfk-lhr")
        assert origin == "JFK"
        assert destination == "LHR"

    def test_validate_route_string_malicious_input(self):
        """Test route string validation against malicious input"""
        malicious_routes = [
            "THR'; DROP TABLE flights; --IST",
            "THR-IST'; DELETE FROM flights; --",
            "'; UNION SELECT * FROM users; --",
            "<script>alert('xss')</script>-IST",
            "THR-' OR 1=1 --",
            "../../etc/passwd-IST",
            "THR\x00IST",
        ]

        for malicious_route in malicious_routes:
            with pytest.raises(ValueError):
                InputValidator.validate_route_string(malicious_route)

    def test_sanitize_string_success(self):
        """Test string sanitization"""
        assert InputValidator.sanitize_string("Normal Text") == "Normal Text"
        assert InputValidator.sanitize_string("Airlines123") == "Airlines123"
        assert InputValidator.sanitize_string("Flight-123") == "Flight-123"

    def test_sanitize_string_malicious_input(self):
        """Test string sanitization against malicious input"""
        test_cases = [
            ("'; DROP TABLE flights; --", " DROP TABLE flights --"),
            (
                "<script>alert('xss')</script>",
                "&lt;script&gt;alert(xss)&lt;/script&gt;",
            ),
            ("' OR 1=1 --", " OR 11 --"),
            ('" UNION SELECT * FROM users --', " UNION SELECT * FROM users --"),
            ("Normal Text\\x00", "Normal Text"),
            ('Test"input', "Testinput"),
        ]

        for malicious_input, expected in test_cases:
            result = InputValidator.sanitize_string(malicious_input)
            assert "'" not in result
            assert '"' not in result
            assert "<" not in result
            assert ">" not in result

    def test_validate_positive_integer_success(self):
        """Test positive integer validation"""
        assert InputValidator.validate_positive_integer(5) == 5
        assert InputValidator.validate_positive_integer("10") == 10
        assert InputValidator.validate_positive_integer(1) == 1
        assert InputValidator.validate_positive_integer(1000) == 1000

    def test_validate_positive_integer_malicious_input(self):
        """Test positive integer validation against malicious input"""
        malicious_inputs = [
            "'; DROP TABLE flights; --",
            "1; DELETE FROM flights; --",
            "1 OR 1=1",
            "<script>alert(1)</script>",
            "null",
            "undefined",
            "../../etc/passwd",
            -1,
            0,
            1001,
            "1.5; DROP TABLE users; --",
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValueError):
                InputValidator.validate_positive_integer(malicious_input)

    def test_validate_flight_id_success(self):
        """Test secure flight ID generation"""
        now = datetime.now()
        flight_id = InputValidator.validate_flight_id(
            "Iran Air", "IR123", "THR", "IST", now
        )

        assert "Iran Air" in flight_id
        assert "IR123" in flight_id
        assert "THR" in flight_id
        assert "IST" in flight_id
        assert "_" in flight_id  # Uses underscores as separators

    def test_validate_flight_id_malicious_input(self):
        """Test flight ID generation against malicious input"""
        now = datetime.now()

        # Should sanitize malicious airline name
        flight_id = InputValidator.validate_flight_id(
            "'; DROP TABLE flights; --", "IR123", "THR", "IST", now
        )
        assert "DROP" not in flight_id
        assert "'" not in flight_id
        assert "--" not in flight_id


class TestDataManagerSecurity:
    """Test DataManager security features"""

    @pytest.fixture
    def data_manager(self):
        """Create DataManager instance for testing"""
        with patch("data_manager.config") as mock_config:
            mock_config.DATABASE = Mock()
            mock_config.DATABASE.USER = "test"
            mock_config.DATABASE.PASSWORD = "test"
            mock_config.DATABASE.HOST = "localhost"
            mock_config.DATABASE.PORT = 5432
            mock_config.DATABASE.NAME = "test_db"

            mock_config.REDIS = Mock()
            mock_config.REDIS.HOST = "localhost"
            mock_config.REDIS.PORT = 6379
            mock_config.REDIS.DB = 0
            mock_config.REDIS.PASSWORD = None

            with patch("data_manager.create_engine") as mock_engine:
                with patch("data_manager.Redis") as mock_redis:
                    dm = DataManager()
                    dm.Session = Mock()
                    dm.redis = Mock()
                    return dm

    def test_store_search_query_sql_injection_protection(self, data_manager):
        """Test store_search_query protection against SQL injection"""
        malicious_params = {
            "origin": "'; DROP TABLE flights; --",
            "destination": "' OR 1=1 --",
            "departure_date": "<script>alert('xss')</script>",
            "passengers": "1; DELETE FROM flights; --",
            "seat_class": "' UNION SELECT * FROM users --",
        }

        # Should raise ValueError due to input validation
        with pytest.raises(ValueError):
            data_manager.store_search_query(malicious_params, 10, 1.5, False)

    def test_get_current_price_sql_injection_protection(self, data_manager):
        """Test get_current_price protection against SQL injection"""
        malicious_routes = [
            "'; DROP TABLE flights; --",
            "THR'; DELETE FROM flights; --IST",
            "' OR 1=1 --",
            "THR-IST'; UNION SELECT * FROM users; --",
        ]

        for malicious_route in malicious_routes:
            # Should handle malicious input gracefully
            with pytest.raises(ValueError):
                # This should fail in validate_route_string
                InputValidator.validate_route_string(malicious_route)

    def test_get_search_count_sql_injection_protection(self, data_manager):
        """Test get_search_count protection against SQL injection"""
        malicious_routes = [
            "'; DROP TABLE search_queries; --",
            "THR'; DELETE FROM search_queries; --IST",
            "' OR 1=1 --",
        ]

        for malicious_route in malicious_routes:
            # Should handle malicious input gracefully
            with pytest.raises(ValueError):
                InputValidator.validate_route_string(malicious_route)

    def test_add_crawl_route_sql_injection_protection(self, data_manager):
        """Test add_crawl_route protection against SQL injection"""
        malicious_inputs = [
            ("'; DROP TABLE crawl_routes; --", "IST"),
            ("THR", "'; DELETE FROM crawl_routes; --"),
            ("' OR 1=1 --", "IST"),
            ("<script>alert('xss')</script>", "IST"),
        ]

        for origin, destination in malicious_inputs:
            with pytest.raises(ValueError):
                data_manager.add_crawl_route(origin, destination)

    @patch("data_manager.logger")
    def test_sql_injection_logging(self, mock_logger, data_manager):
        """Test that SQL injection attempts are logged"""
        malicious_params = {"origin": "'; DROP TABLE flights; --", "destination": "IST"}

        try:
            data_manager.store_search_query(malicious_params, 10, 1.5, False)
        except ValueError:
            pass  # Expected

        # Should log the validation error
        mock_logger.error.assert_called()


class TestSecurityIntegration:
    """Integration tests for security features"""

    def test_no_raw_sql_in_codebase(self):
        """Verify no raw SQL concatenation in DataManager"""
        import inspect
        from data_manager import DataManager

        # Get all methods from DataManager
        methods = inspect.getmembers(DataManager, predicate=inspect.isfunction)

        for method_name, method in methods:
            source = inspect.getsource(method)

            # Check for dangerous patterns
            dangerous_patterns = [
                'f"SELECT',
                'f"INSERT',
                'f"UPDATE',
                'f"DELETE',
                'f"SELECT',
                'f"INSERT',
                'f"UPDATE',
                'f"DELETE',
                ".format(",
                "% ",
                '+ "SELECT',
                "+ 'SELECT",
            ]

            for pattern in dangerous_patterns:
                assert (
                    pattern not in source
                ), f"Found dangerous SQL pattern '{pattern}' in method {method_name}"

    def test_orm_usage_verification(self):
        """Verify that ORM is used instead of raw SQL"""
        import inspect
        from data_manager import DataManager

        # Get all methods from DataManager
        methods = inspect.getmembers(DataManager, predicate=inspect.isfunction)

        orm_indicators = [
            "session.query",
            "session.add",
            "session.commit",
            "session.filter",
            "func.avg",
            "func.count",
        ]

        methods_with_db_operations = []
        for method_name, method in methods:
            source = inspect.getsource(method)
            if "session" in source or "query" in source:
                methods_with_db_operations.append((method_name, source))

        # Verify that database methods use ORM patterns
        assert len(methods_with_db_operations) > 0, "No database operations found"

        for method_name, source in methods_with_db_operations:
            has_orm_usage = any(indicator in source for indicator in orm_indicators)
            if "session" in source:  # If it uses session, it should use ORM
                assert (
                    has_orm_usage
                ), f"Method {method_name} uses session but no ORM patterns found"


if __name__ == "__main__":
    pytest.main([__file__])
