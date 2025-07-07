import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any
from datetime import datetime, timedelta

from site_crawlers import (
    FlytodayCrawler,
    FlightioCrawler,
    AlibabaCrawler,
    SafarmarketCrawler,
    Mz724Crawler,
    PartoCRSCrawler,
    PartoTicketCrawler,
    BookCharter724Crawler,
    BookCharterCrawler,
    MrbilitCrawler,
    BaseSiteCrawler,
)


class TestCrawlerComprehensive:
    """Comprehensive tests for all crawler classes"""

    @pytest.fixture
    def sample_flight_data(self) -> Dict[str, Any]:
        """Sample flight data for testing"""
        return {
            "origin": "THR",
            "destination": "MHD",
            "departure_date": "2025-06-15",
            "return_date": "2025-06-20",
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin_class": "economy",
        }

    @pytest.fixture
    def mock_response(self) -> Dict[str, Any]:
        """Mock response data"""
        return {
            "flights": [
                {
                    "airline": "Iran Air",
                    "flight_number": "IR123",
                    "departure_time": "10:30",
                    "arrival_time": "12:00",
                    "price": 1500000,
                    "currency": "IRR",
                    "cabin_class": "economy",
                    "stops": 0,
                }
            ],
            "total_count": 1,
            "search_timestamp": datetime.now().isoformat(),
        }

    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    def test_crawler_inheritance(self, crawler_class):
        """Test that all crawlers inherit from BaseSiteCrawler"""
        assert issubclass(crawler_class, BaseSiteCrawler)

    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    def test_crawler_has_required_methods(self, crawler_class):
        """Test that all crawlers have required methods"""
        crawler = crawler_class()

        # Check required methods exist
        assert hasattr(crawler, "search_flights")
        assert hasattr(crawler, "get_site_name")
        assert hasattr(crawler, "get_base_url")

        # Check methods are callable
        assert callable(crawler.search_flights)
        assert callable(crawler.get_site_name)
        assert callable(crawler.get_base_url)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    async def test_crawler_search_flights_signature(
        self, crawler_class, sample_flight_data
    ):
        """Test that search_flights method has correct signature and returns list"""
        crawler = crawler_class()

        # Test method signature
        result = await crawler.search_flights(**sample_flight_data)

        # Should return a list
        assert isinstance(result, list)

        # Each item should be a dictionary with flight data
        for flight in result:
            assert isinstance(flight, dict)
            # Check for required flight fields
            assert "airline" in flight
            assert "price" in flight

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    async def test_crawler_error_handling(self, crawler_class, sample_flight_data):
        """Test error handling in crawlers"""
        crawler = crawler_class()

        # Test with invalid data
        invalid_data = sample_flight_data.copy()
        invalid_data["origin"] = "INVALID"
        invalid_data["destination"] = "INVALID"

        try:
            result = await crawler.search_flights(**invalid_data)
            # Should return empty list or handle gracefully
            assert isinstance(result, list)
        except Exception as e:
            # Should not raise unexpected exceptions
            assert isinstance(e, (ValueError, ConnectionError, TimeoutError))

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    async def test_crawler_timeout_handling(self, crawler_class, sample_flight_data):
        """Test timeout handling in crawlers"""
        crawler = crawler_class()

        # Mock slow response
        with patch.object(
            crawler, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()

            result = await crawler.search_flights(**sample_flight_data)

            # Should handle timeout gracefully
            assert isinstance(result, list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    async def test_crawler_connection_error_handling(
        self, crawler_class, sample_flight_data
    ):
        """Test connection error handling in crawlers"""
        crawler = crawler_class()

        # Mock connection error
        with patch.object(
            crawler, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = ConnectionError("Connection failed")

            result = await crawler.search_flights(**sample_flight_data)

            # Should handle connection error gracefully
            assert isinstance(result, list)

    def test_crawler_site_names(self):
        """Test that all crawlers have unique and valid site names"""
        crawlers = [
            FlytodayCrawler(),
            FlightioCrawler(),
            AlibabaCrawler(),
            SafarmarketCrawler(),
            Mz724Crawler(),
            PartoCRSCrawler(),
            PartoTicketCrawler(),
            BookCharter724Crawler(),
            BookCharterCrawler(),
            MrbilitCrawler(),
        ]

        site_names = [crawler.get_site_name() for crawler in crawlers]

        # All site names should be unique
        assert len(site_names) == len(set(site_names))

        # All site names should be non-empty strings
        for name in site_names:
            assert isinstance(name, str)
            assert len(name.strip()) > 0

    def test_crawler_base_urls(self):
        """Test that all crawlers have valid base URLs"""
        crawlers = [
            FlytodayCrawler(),
            FlightioCrawler(),
            AlibabaCrawler(),
            SafarmarketCrawler(),
            Mz724Crawler(),
            PartoCRSCrawler(),
            PartoTicketCrawler(),
            BookCharter724Crawler(),
            BookCharterCrawler(),
            MrbilitCrawler(),
        ]

        base_urls = [crawler.get_base_url() for crawler in crawlers]

        # All base URLs should be valid
        for url in base_urls:
            assert isinstance(url, str)
            assert url.startswith(("http://", "https://"))
            assert len(url.strip()) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_crawler_integration_with_real_data(self, sample_flight_data):
        """Integration test with real data (marked as slow)"""
        # This test would run against real APIs
        # Should be run separately and marked as integration test
        pass

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "crawler_class",
        [
            FlytodayCrawler,
            FlightioCrawler,
            AlibabaCrawler,
            SafarmarketCrawler,
            Mz724Crawler,
            PartoCRSCrawler,
            PartoTicketCrawler,
            BookCharter724Crawler,
            BookCharterCrawler,
            MrbilitCrawler,
        ],
    )
    async def test_crawler_data_validation(
        self, crawler_class, sample_flight_data, mock_response
    ):
        """Test data validation in crawlers"""
        crawler = crawler_class()

        # Mock successful response
        with patch.object(
            crawler, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            result = await crawler.search_flights(**sample_flight_data)

            # Validate result structure
            assert isinstance(result, list)

            for flight in result:
                # Check required fields
                assert "airline" in flight
                assert "price" in flight
                assert "departure_time" in flight
                assert "arrival_time" in flight

                # Check data types
                assert isinstance(flight["airline"], str)
                assert isinstance(flight["price"], (int, float))
                assert isinstance(flight["departure_time"], str)
                assert isinstance(flight["arrival_time"], str)

                # Check value ranges
                assert flight["price"] > 0
                assert len(flight["airline"]) > 0
