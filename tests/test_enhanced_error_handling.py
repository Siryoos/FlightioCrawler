"""
Tests for enhanced error handling in EnhancedBaseCrawler.

This test suite verifies the centralized error handling, retry mechanisms,
error categorization, and recovery strategies.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any, List

from adapters.base_adapters.enhanced_base_crawler import (
    EnhancedBaseCrawler,
    ErrorCategory,
    RetryConfig,
    CrawlerConfig,
)
from adapters.base_adapters.enhanced_error_handler import (
    ErrorCategory,
    ErrorSeverity,
    ErrorAction,
    ErrorContext,
    EnhancedErrorHandler,
    error_handler_decorator,
    safe_extract,
    AdapterError,
    NavigationError,
    FormFillingError,
    ExtractionError,
    ValidationError,
    TimeoutError,
    AdapterTimeoutError,
    AdapterNetworkError,
    AdapterValidationError,
    AdapterRateLimitError,
    AdapterAuthenticationError,
    AdapterResourceError,
    AdapterParsingError,
)


class TestEnhancedBaseCrawler(EnhancedBaseCrawler):
    """Test implementation of EnhancedBaseCrawler for testing purposes."""
    
    def _get_base_url(self) -> str:
        return "https://test-airline.com"
    
    async def _handle_page_setup(self) -> None:
        """Mock implementation for testing."""
        pass
    
    async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
        """Mock implementation for testing."""
        if search_params.get("simulate_form_error"):
            raise FormFillingError("Simulated form filling error")
        pass
    
    def _parse_flight_element(self, element) -> Dict[str, Any]:
        """Mock implementation for testing."""
        if hasattr(element, 'simulate_parse_error'):
            raise ExtractionError("Simulated parsing error")
        return {
            "flight_number": "TEST123",
            "price": 299.99,
            "departure_time": "10:00",
            "arrival_time": "12:00"
        }


@pytest.fixture
def crawler_config():
    """Create test crawler configuration."""
    return {
        "base_url": "https://test-airline.com",
        "search_url": "https://test-airline.com/search",
        "error_handling": {
            "max_retries": 2,
            "retry_delay": 0.1,
            "enable_recovery": True,
        },
        "retry_config": {
            "max_retries": 2,
            "base_delay": 0.1,
            "max_delay": 1.0,
            "exponential_base": 2.0,
            "jitter": False,  # Disable jitter for predictable tests
        },
        "extraction_config": {
            "results_parsing": {
                "container": ".flight-results"
            }
        }
    }


@pytest.fixture
def test_crawler(crawler_config):
    """Create test crawler instance."""
    return TestEnhancedBaseCrawler(crawler_config)


class TestErrorCategorization:
    """Test error categorization functionality."""
    
    def test_categorize_timeout_error(self, test_crawler):
        """Test timeout error categorization."""
        error = TimeoutError("Connection timeout")
        category = test_crawler._categorize_error(error)
        assert category == ErrorCategory.TIMEOUT
    
    def test_categorize_network_error(self, test_crawler):
        """Test network error categorization."""
        error = ConnectionError("Network connection failed")
        category = test_crawler._categorize_error(error)
        assert category == ErrorCategory.NETWORK
    
    def test_categorize_rate_limit_error(self, test_crawler):
        """Test rate limit error categorization."""
        error = Exception("Rate limit exceeded - 429")
        category = test_crawler._categorize_error(error)
        assert category == ErrorCategory.RATE_LIMIT
    
    def test_categorize_validation_error(self, test_crawler):
        """Test validation error categorization."""
        error = ValidationError("Invalid data format")
        category = test_crawler._categorize_error(error)
        assert category == ErrorCategory.VALIDATION
    
    def test_categorize_unknown_error(self, test_crawler):
        """Test unknown error categorization."""
        error = Exception("Some unknown error")
        category = test_crawler._categorize_error(error)
        assert category == ErrorCategory.UNKNOWN


class TestRetryMechanism:
    """Test retry mechanism functionality."""
    
    def test_is_retryable_error(self, test_crawler):
        """Test retryable error detection."""
        # Retryable errors
        assert test_crawler._is_retryable_error(
            TimeoutError("timeout"), ErrorCategory.TIMEOUT
        )
        assert test_crawler._is_retryable_error(
            ConnectionError("network"), ErrorCategory.NETWORK
        )
        
        # Non-retryable errors
        assert not test_crawler._is_retryable_error(
            ValidationError("validation"), ErrorCategory.VALIDATION
        )
    
    @pytest.mark.asyncio
    async def test_calculate_retry_delay(self, test_crawler):
        """Test retry delay calculation."""
        # Test exponential backoff
        delay_0 = await test_crawler._calculate_retry_delay(0)
        delay_1 = await test_crawler._calculate_retry_delay(1)
        delay_2 = await test_crawler._calculate_retry_delay(2)
        
        assert delay_0 == 0.1  # base_delay
        assert delay_1 == 0.2  # base_delay * 2^1
        assert delay_2 == 0.4  # base_delay * 2^2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, test_crawler):
        """Test successful operation with retry mechanism."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_crawler._execute_with_retry(
            mock_operation, "test_operation"
        )
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_eventual_success(self, test_crawler):
        """Test operation that succeeds after retries."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Temporary timeout")
            return "success"
        
        result = await test_crawler._execute_with_retry(
            mock_operation, "test_operation"
        )
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_max_retries_exceeded(self, test_crawler):
        """Test operation that fails after max retries."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Persistent timeout")
        
        with pytest.raises(TimeoutError):
            await test_crawler._execute_with_retry(
                mock_operation, "test_operation"
            )
        
        assert call_count == 3  # Initial attempt + 2 retries


class TestErrorRecovery:
    """Test error recovery strategies."""
    
    @pytest.mark.asyncio
    async def test_network_error_recovery(self, test_crawler):
        """Test network error recovery."""
        error = ConnectionError("Network failed")
        context = ErrorContext(
            adapter_name="TestCrawler",
            operation="test_operation",
            retry_count=1
        )
        
        # Mock page for recovery
        test_crawler.page = Mock()
        test_crawler.page.is_closed.return_value = False
        
        with patch('adapters.base_adapters.common_error_handler.ErrorRecoveryStrategies.refresh_page') as mock_refresh:
            mock_refresh.return_value = None
            
            result = await test_crawler._recover_from_network_error(error, context)
            mock_refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_timeout_error_recovery(self, test_crawler):
        """Test timeout error recovery."""
        error = TimeoutError("Request timeout")
        context = ErrorContext(
            adapter_name="TestCrawler",
            operation="test_operation",
            retry_count=1
        )
        
        # Mock page for recovery
        test_crawler.page = Mock()
        test_crawler.page.is_closed.return_value = False
        test_crawler.page.evaluate = AsyncMock()
        
        await test_crawler._recover_from_timeout_error(error, context)
        test_crawler.page.evaluate.assert_called_once_with("window.stop()")
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_recovery(self, test_crawler):
        """Test rate limit error recovery."""
        error = Exception("Rate limit exceeded")
        context = ErrorContext(
            adapter_name="TestCrawler",
            operation="test_operation",
            retry_count=1
        )
        
        # Mock page and user agent switching
        test_crawler.page = Mock()
        test_crawler.page.is_closed.return_value = False
        
        with patch('adapters.base_adapters.common_error_handler.ErrorRecoveryStrategies.switch_user_agent') as mock_switch:
            mock_switch.return_value = None
            
            await test_crawler._recover_from_rate_limit_error(error, context)
            mock_switch.assert_called_once()


class TestErrorStatistics:
    """Test error statistics tracking."""
    
    def test_update_error_stats(self, test_crawler):
        """Test error statistics updates."""
        error = TimeoutError("Test timeout")
        category = ErrorCategory.TIMEOUT
        operation = "test_operation"
        
        initial_total = test_crawler.error_stats["total_errors"]
        
        test_crawler._update_error_stats(error, category, operation)
        
        assert test_crawler.error_stats["total_errors"] == initial_total + 1
        assert test_crawler.error_stats["errors_by_category"]["timeout"] == 1
        assert test_crawler.error_stats["errors_by_operation"]["test_operation"] == 1
        assert test_crawler.error_stats["last_error_time"] is not None
    
    def test_get_error_statistics(self, test_crawler):
        """Test error statistics retrieval."""
        stats = test_crawler.get_error_statistics()
        
        assert "total_errors" in stats
        assert "errors_by_category" in stats
        assert "errors_by_operation" in stats
        assert "retry_config" in stats
        assert "common_error_stats" in stats
    
    def test_reset_error_statistics(self, test_crawler):
        """Test error statistics reset."""
        # Add some errors first
        test_crawler._update_error_stats(
            TimeoutError("test"), ErrorCategory.TIMEOUT, "test_op"
        )
        
        # Reset statistics
        test_crawler.reset_error_statistics()
        
        assert test_crawler.error_stats["total_errors"] == 0
        assert test_crawler.error_stats["errors_by_category"] == {}
        assert test_crawler.error_stats["errors_by_operation"] == {}


class TestEnhancedCrawlWorkflow:
    """Test the enhanced crawl workflow with error handling."""
    
    @pytest.mark.asyncio
    async def test_navigation_error_handling(self, test_crawler):
        """Test navigation error handling with proper error types."""
        # Mock page setup
        test_crawler.page = Mock()
        test_crawler.page.goto = AsyncMock(side_effect=TimeoutError("Navigation timeout"))
        
        with pytest.raises(AdapterTimeoutError) as exc_info:
            await test_crawler._navigate_to_search_page()
        
        assert "Timeout while loading search page" in str(exc_info.value)
        assert exc_info.value.context.operation == "navigation"
    
    @pytest.mark.asyncio
    async def test_extraction_error_handling(self, test_crawler):
        """Test extraction error handling with proper error types."""
        # Mock page without required selector configuration
        test_crawler.config.extraction_config = {}
        
        with pytest.raises(ExtractionError) as exc_info:
            await test_crawler._extract_flight_results()
        
        assert "No container selector configured" in str(exc_info.value)
        assert exc_info.value.context.operation == "extract_flight_results"


@pytest.mark.asyncio
async def test_complete_workflow_with_error_handling(crawler_config):
    """Test complete crawl workflow with centralized error handling."""
    crawler = TestEnhancedBaseCrawler(crawler_config)
    
    # Mock all necessary components
    crawler.page = Mock()
    crawler.page.goto = AsyncMock()
    crawler.page.wait_for_load_state = AsyncMock()
    crawler.page.title = AsyncMock(return_value="Test Airline Search")
    crawler.page.wait_for_selector = AsyncMock()
    crawler.page.content = AsyncMock(return_value="<div class='flight-results'></div>")
    
    crawler.rate_limiter = Mock()
    crawler.rate_limiter.wait = AsyncMock()
    
    crawler.monitoring = Mock()
    crawler.monitoring.record_success = Mock()
    crawler.monitoring.record_crawl = Mock()
    
    # Mock BeautifulSoup
    with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
        mock_soup = Mock()
        mock_soup.select.return_value = []
        mock_bs.return_value = mock_soup
        
        search_params = {
            "origin": "NYC",
            "destination": "LAX",
            "departure_date": "2024-01-01"
        }
        
        results = await crawler._execute_crawling_workflow(search_params)
        
        assert isinstance(results, list)
        crawler.monitoring.record_success.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 