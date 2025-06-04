from error_handler import ErrorHandler


def test_get_all_error_stats_timestamp_extraction():
    handler = ErrorHandler()
    handler.circuit_breakers = {
        "example.com": {"timestamp": "2023-01-01T00:00:00", "error_count": 1}
    }
    stats = handler.get_all_error_stats()
    assert stats["circuit_breaker"]["example.com"] == "2023-01-01T00:00:00"
