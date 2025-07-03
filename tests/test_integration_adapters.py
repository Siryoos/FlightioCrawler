"""
Integration tests for enhanced error handling across key adapters.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

# Import enhanced base classes
from adapters.base_adapters.enhanced_base_crawler import (
    EnhancedBaseCrawler,
    ErrorCategory,
)
from adapters.base_adapters.common_error_handler import (
    AdapterError,
    NavigationError,
    FormFillingError,
    ExtractionError,
    ValidationError,
    TimeoutError as AdapterTimeoutError,
)


class TestEnhancedErrorHandlingIntegration:
    """Integration tests for enhanced error handling across different adapter types."""
    
    @pytest.fixture
    def enhanced_config(self):
        """Enhanced configuration for testing."""
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
                "retry_delay": 0.1,
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
                "search_form": {
                    "origin_field": "#origin",
                    "destination_field": "#destination",
                    "departure_date_field": "#departure"
                },
                "results_parsing": {
                    "container": ".flight-result",
                    "airline": ".airline",
                    "flight_number": ".flight-number",
                    "price": ".price"
                }
            },
            "data_validation": {
                "required_fields": ["airline", "flight_number", "price", "currency"],
                "price_range": {"min": 100000, "max": 50000000}
            }
        }

    @pytest.fixture
    def search_params(self):
        """Common search parameters for testing."""
        return {
            "origin": "THR",
            "destination": "IST",
            "departure_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin_class": "economy"
        }

    @pytest.fixture
    def mock_browser_context(self):
        """Mock browser context for testing."""
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        # Configure mock page
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=True)
        mock_page.fill = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.content = AsyncMock(return_value="<div class='flight-results'></div>")
        mock_page.title = AsyncMock(return_value="Test Airline Search")
        
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()
        
        return mock_context, mock_page

    @pytest.mark.asyncio
    async def test_timeout_error_handling_and_retry(self, enhanced_config, search_params, mock_browser_context):
        """Test timeout error handling and retry mechanism."""
        mock_context, mock_page = mock_browser_context
        
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Mock components
        crawler.context = mock_context
        crawler.page = mock_page
        crawler.rate_limiter = Mock()
        crawler.rate_limiter.wait = AsyncMock()
        crawler.monitoring = Mock()
        crawler.monitoring.record_error = Mock()
        crawler.monitoring.record_success = Mock()
        crawler.monitoring.record_crawl = Mock()
        
        # Configure timeout error on first attempt, success on retry
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Timeout loading page"),
            None  # Success on retry
        ]
        
        # Create mock flight elements that will pass validation
        mock_flight_element = Mock()
        mock_flight_element.select.return_value = [
            Mock(get_text=Mock(return_value="Test Air")),
            Mock(get_text=Mock(return_value="TA-123")),
            Mock(get_text=Mock(return_value="450000"))  # Price in valid range
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [mock_flight_element]
            mock_bs.return_value = mock_soup
            
            # Test crawl with timeout recovery
            results = await crawler.crawl(search_params)
            
            # Verify retry was attempted
            assert mock_page.goto.call_count == 2
            
            # Verify error handling worked (check error stats instead of mock calls)
            error_stats = crawler.get_error_statistics()
            assert error_stats["total_errors"] > 0
            assert error_stats["successful_recoveries"] > 0
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_network_error_handling_and_retry(self, enhanced_config, search_params, mock_browser_context):
        """Test network error handling and retry mechanism."""
        mock_context, mock_page = mock_browser_context
        
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Mock components
        crawler.context = mock_context
        crawler.page = mock_page
        crawler.rate_limiter = Mock()
        crawler.rate_limiter.wait = AsyncMock()
        crawler.monitoring = Mock()
        crawler.monitoring.record_error = Mock()
        crawler.monitoring.record_success = Mock()
        crawler.monitoring.record_crawl = Mock()
        
        # Configure network error on first two attempts, success on third
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Network connection failed"),
            AdapterTimeoutError("Network connection failed"),
            None  # Success on third attempt
        ]
        
        # Create mock flight elements that will pass validation
        mock_flight_element = Mock()
        mock_flight_element.select.return_value = [
            Mock(get_text=Mock(return_value="Test Air")),
            Mock(get_text=Mock(return_value="TA-123")),
            Mock(get_text=Mock(return_value="450000"))  # Price in valid range
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [mock_flight_element]
            mock_bs.return_value = mock_soup
            
            # Test crawl with network error recovery
            results = await crawler.crawl(search_params)
            
            # Verify retries were attempted
            assert mock_page.goto.call_count == 3
            
            # Verify error handling worked (check error stats instead of mock calls)
            error_stats = crawler.get_error_statistics()
            assert error_stats["total_errors"] > 0
            assert error_stats["successful_recoveries"] > 0
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test rate limit error handling and recovery."""
        mock_context, mock_page = mock_browser_context
        
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Mock components
        crawler.context = mock_context
        crawler.page = mock_page
        crawler.rate_limiter = Mock()
        crawler.rate_limiter.wait = AsyncMock()
        crawler.monitoring = Mock()
        crawler.monitoring.record_error = Mock()
        crawler.monitoring.record_success = Mock()
        crawler.monitoring.record_crawl = Mock()
        
        # Configure rate limit error on first attempt, success on retry
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Rate limit exceeded - 429"),
            None  # Success on retry
        ]
        
        # Create mock flight elements that will pass validation
        mock_flight_element = Mock()
        mock_flight_element.select.return_value = [
            Mock(get_text=Mock(return_value="Test Air")),
            Mock(get_text=Mock(return_value="TA-123")),
            Mock(get_text=Mock(return_value="450000"))  # Price in valid range
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [mock_flight_element]
            mock_bs.return_value = mock_soup
            
            # Test crawl with rate limit recovery
            results = await crawler.crawl(search_params)
            
            # Verify retry was attempted
            assert mock_page.goto.call_count == 2
            
            # Verify error handling worked (check error stats instead of mock calls)
            error_stats = crawler.get_error_statistics()
            assert error_stats["total_errors"] > 0
            assert error_stats["successful_recoveries"] > 0
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test validation error handling."""
        mock_context, mock_page = mock_browser_context
        
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                # Raise validation error for empty origin
                if not search_params.get("origin"):
                    raise ValidationError("Origin is required")
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450000,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Mock components
        crawler.context = mock_context
        crawler.page = mock_page
        crawler.rate_limiter = Mock()
        crawler.rate_limiter.wait = AsyncMock()
        crawler.monitoring = Mock()
        crawler.monitoring.record_error = Mock()
        crawler.monitoring.record_success = Mock()
        crawler.monitoring.record_crawl = Mock()
        
        # Test with invalid search parameters
        invalid_params = search_params.copy()
        invalid_params["origin"] = ""  # Invalid empty origin
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = []
            mock_bs.return_value = mock_soup
            
            # Test crawl with validation error
            with pytest.raises(ValidationError):
                await crawler.crawl(invalid_params)
            
            # Verify error was recorded
            crawler.monitoring.record_error.assert_called()

    @pytest.mark.asyncio
    async def test_error_categorization(self, enhanced_config):
        """Test that error categorization works correctly."""
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Test error categorization
        timeout_error = AdapterTimeoutError("Connection timeout")
        network_error = Exception("Network connection failed")  # Use generic Exception for network
        validation_error = ValidationError("Invalid data")
        rate_limit_error = AdapterTimeoutError("Rate limit exceeded")
        
        assert crawler._categorize_error(timeout_error) == ErrorCategory.TIMEOUT
        assert crawler._categorize_error(network_error) == ErrorCategory.NETWORK
        assert crawler._categorize_error(validation_error) == ErrorCategory.VALIDATION
        assert crawler._categorize_error(rate_limit_error) == ErrorCategory.RATE_LIMIT

    @pytest.mark.asyncio
    async def test_error_statistics_collection(self, enhanced_config, search_params, mock_browser_context):
        """Test that error statistics are collected properly."""
        mock_context, mock_page = mock_browser_context
        
        # Create a test crawler class
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test-airline.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                """Mock implementation of form filling."""
                pass
            
            async def _handle_page_setup(self) -> None:
                """Mock implementation of page setup."""
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                """Mock implementation of flight element parsing."""
                return {
                    "airline": "Test Air",
                    "flight_number": "TA-123",
                    "price": 450000,
                    "currency": "USD"
                }
        
        crawler = TestCrawler(enhanced_config)
        
        # Mock components
        crawler.context = mock_context
        crawler.page = mock_page
        crawler.rate_limiter = Mock()
        crawler.rate_limiter.wait = AsyncMock()
        crawler.monitoring = Mock()
        crawler.monitoring.record_error = Mock()
        crawler.monitoring.record_success = Mock()
        crawler.monitoring.record_crawl = Mock()
        
        # Configure timeout error on first attempt, success on retry
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Timeout"),
            None  # Success on retry
        ]
        
        # Create mock flight elements that will pass validation
        mock_flight_element = Mock()
        mock_flight_element.select.return_value = [
            Mock(get_text=Mock(return_value="Test Air")),
            Mock(get_text=Mock(return_value="TA-123")),
            Mock(get_text=Mock(return_value="450000"))  # Price in valid range
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [mock_flight_element]
            mock_bs.return_value = mock_soup
            
            # Execute crawl
            results = await crawler.crawl(search_params)
            
            # Verify error statistics were collected
            error_stats = crawler.get_error_statistics()
            assert error_stats["total_errors"] > 0
            assert error_stats["successful_recoveries"] > 0
            assert "timeout" in error_stats["errors_by_category"]
            assert "navigation" in error_stats["errors_by_operation"]
            
            # Verify results structure
            assert isinstance(results, list) 