import asyncio

from flight_data_standardizer import FlightDataStandardizer
from flight_data_validator import FlightDataValidator
from adapters.unified_crawler_interface import CrawlerSystemType


def test_standardizer_and_validator():
    """
    Test the integration of flight data standardization and validation using sample requests-based input.
    
    This test verifies that a flight data tuple can be standardized into a single flight object and subsequently validated as a correct entry.
    """
    requests_data = (
        True,
        {
            "flights": [
                {
                    "airline": "TestAir",
                    "flight_number": "TA123",
                    "origin": "THR",
                    "destination": "IST",
                    "departure_time": "2025-01-01T10:00:00",
                    "arrival_time": "2025-01-01T12:00:00",
                    "price": 100,
                    "currency": "USD",
                }
            ]
        },
        "",
    )

    standardizer = FlightDataStandardizer(CrawlerSystemType.REQUESTS)
    flights = standardizer.standardize(requests_data)
    assert len(flights) == 1

    validator = FlightDataValidator()
    valid = validator.validate([f.to_dict() for f in flights])
    assert len(valid) == 1

