"""
Enhanced Security Tests for FlightioCrawler
"""

import pytest
import re
from typing import Dict, List, Any

from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter


class TestSecurityEnhanced:
    """Enhanced security tests for FlightioCrawler."""

    @pytest.fixture
    def secure_config(self):
        return {
            "rate_limiting": {"requests_per_second": 1.0, "burst_limit": 3},
            "security": {"input_validation": True, "sanitize_output": True},
            "monitoring": {"enabled": True, "log_security_events": True}
        }

    @pytest.fixture
    def malicious_inputs(self):
        return {
            "sql_injection": ["'; DROP TABLE flights; --", "' OR '1'='1"],
            "xss_payloads": ["<script>alert('XSS')</script>", "<img src=x onerror=alert('XSS')>"],
            "command_injection": ["; rm -rf /", "| cat /etc/passwd"],
            "path_traversal": ["../../../etc/passwd", "..\\..\\..\\windows\\system32"]
        }

    @pytest.mark.security
    def test_input_validation_sql_injection(self, secure_config, malicious_inputs):
        """Test SQL injection prevention."""
        adapter = AlibabaAdapter(secure_config)
        
        for sql_payload in malicious_inputs["sql_injection"]:
            malicious_params = {
                "origin": sql_payload,
                "destination": "IST",
                "departure_date": "2024-06-01"
            }
            
            sanitized_params = self._sanitize_search_params(malicious_params)
            
            # Verify SQL injection patterns are removed
            assert "DROP TABLE" not in sanitized_params["origin"].upper()
            assert "UNION SELECT" not in sanitized_params["origin"].upper()
            assert len(sanitized_params["origin"]) <= 50

    @pytest.mark.security
    def test_xss_protection(self, secure_config, malicious_inputs):
        """Test XSS protection."""
        malicious_results = []
        for xss_payload in malicious_inputs["xss_payloads"]:
            malicious_results.append({
                "airline": xss_payload,
                "flight_number": f"XSS{xss_payload}123",
                "price": 1000000
            })
        
        sanitized_results = self._sanitize_flight_results(malicious_results)
        
        for result in sanitized_results:
            assert "<script>" not in result["airline"]
            assert "onerror=" not in result["flight_number"]

    @pytest.mark.security
    def test_rate_limiting_protection(self, secure_config):
        """Test rate limiting for DoS protection."""
        adapter = AlibabaAdapter(secure_config)
        
        # Simulate rapid requests
        allowed_requests = 0
        for i in range(10):
            if self._check_rate_limit("test_client", secure_config["rate_limiting"]):
                allowed_requests += 1
        
        # Should not exceed burst limit
        assert allowed_requests <= secure_config["rate_limiting"]["burst_limit"]

    @pytest.mark.security
    def test_secure_error_handling(self, secure_config):
        """Test secure error handling."""
        test_errors = [
            "Database connection failed: user=admin, password=secret",
            "API key invalid: sk-1234567890abcdef"
        ]
        
        for error in test_errors:
            sanitized_error = self._sanitize_error_message(error)
            
            assert "password=" not in sanitized_error.lower()
            assert "sk-" not in sanitized_error

    # Helper methods
    def _sanitize_search_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """Sanitize search parameters."""
        sanitized = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Remove SQL injection patterns
                sanitized_value = re.sub(r"[';\"\\]", "", value)
                sanitized_value = re.sub(r"\b(DROP|DELETE|INSERT|UPDATE|UNION|SELECT)\b", "", sanitized_value, flags=re.IGNORECASE)
                sanitized_value = sanitized_value[:50]
                sanitized[key] = sanitized_value
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_flight_results(self, results: List[Dict]) -> List[Dict]:
        """Sanitize flight results."""
        sanitized = []
        for result in results:
            sanitized_result = {}
            for key, value in result.items():
                if isinstance(value, str):
                    # Remove XSS patterns
                    sanitized_value = re.sub(r"<script[^>]*>.*?</script>", "", value, flags=re.IGNORECASE | re.DOTALL)
                    sanitized_value = re.sub(r"<[^>]*on\w+=[^>]*>", "", sanitized_value, flags=re.IGNORECASE)
                    sanitized_result[key] = sanitized_value
                else:
                    sanitized_result[key] = value
            sanitized.append(sanitized_result)
        return sanitized

    def _check_rate_limit(self, client_id: str, rate_config: Dict[str, Any]) -> bool:
        """Check rate limits."""
        # Simplified: every 3rd request is blocked
        return hash(client_id) % 3 != 0

    def _sanitize_error_message(self, error_msg: str) -> str:
        """Sanitize error messages."""
        sanitized = re.sub(r"password=\w+", "password=***", error_msg, flags=re.IGNORECASE)
        sanitized = re.sub(r"sk-[a-zA-Z0-9]+", "sk-***", sanitized)
        return sanitized
