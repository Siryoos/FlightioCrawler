"""
Comprehensive test suite for enhanced_base_crawler.py to improve coverage.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Optional
from datetime import datetime

from adapters.base_adapters.enhanced_base_crawler import (
    EnhancedBaseCrawler,
    ErrorCategory,
)
from adapters.base_adapters.enhanced_error_handler import (
    ErrorCategory,
    ErrorSeverity,
    ErrorAction,
    ErrorContext,
    EnhancedErrorHandler,
    error_handler_decorator,
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


class TestEnhancedBaseCrawlerCoverage:
    """Test suite for enhanced base crawler coverage improvement"""
    
    @pytest.fixture
    def crawler_config(self):
        """Create test configuration"""
        return {
            "base_url": "https://test.com",
            "search_url": "https://test.com/search",
            "extraction_config": {
                "selectors": {
                    "flight_list": ".flight-item",
                    "price": ".price",
                    "airline": ".airline"
                }
            },
            "data_validation": {"enabled": True},
            "rate_limiting": {
                "requests_per_second": 2,
                "burst_limit": 5
            }
        }
    
    @pytest.fixture
    def test_crawler(self, crawler_config):
        """Create test crawler"""
        class TestCrawler(EnhancedBaseCrawler):
            def _get_base_url(self) -> str:
                return "https://test.com"
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return "USD"
            
            async def _fill_search_form(self, search_params: Dict[str, Any]) -> None:
                pass
            
            async def _handle_page_setup(self) -> None:
                pass
            
            def _parse_flight_element(self, element) -> Optional[Dict[str, Any]]:
                return {"airline": "Test", "price": 100}
        
        return TestCrawler(crawler_config)
    
    def test_error_categorization(self, test_crawler):
        """Test error categorization methods"""
        # Test rate limit error
        rate_limit_error = Exception("Rate limit exceeded - 429")
        assert test_crawler._categorize_error(rate_limit_error) == ErrorCategory.RATE_LIMIT
        
        # Test timeout error
        timeout_error = Exception("Connection timeout")
        assert test_crawler._categorize_error(timeout_error) == ErrorCategory.TIMEOUT
        
        # Test network error
        network_error = Exception("Network connection failed")
        assert test_crawler._categorize_error(network_error) == ErrorCategory.NETWORK
        
        # Test validation error
        validation_error = ValidationError("Invalid data")
        assert test_crawler._categorize_error(validation_error) == ErrorCategory.VALIDATION
        
        # Test unknown error
        unknown_error = Exception("Unknown error")
        assert test_crawler._categorize_error(unknown_error) == ErrorCategory.UNKNOWN
    
    def test_retryable_error_detection(self, test_crawler):
        """Test retryable error detection"""
        # Test retryable errors
        network_error = Exception("Network failed")
        assert test_crawler._is_retryable_error(network_error, ErrorCategory.NETWORK) is True
        
        timeout_error = Exception("Timeout")
        assert test_crawler._is_retryable_error(timeout_error, ErrorCategory.TIMEOUT) is True
        
        # Test non-retryable errors
        validation_error = ValidationError("Invalid")
        assert test_crawler._is_retryable_error(validation_error, ErrorCategory.VALIDATION) is False
    
    @pytest.mark.asyncio
    async def test_retry_delay_calculation(self, test_crawler):
        """Test retry delay calculation"""
        delay_0 = await test_crawler._calculate_retry_delay(0)
        delay_1 = await test_crawler._calculate_retry_delay(1)
        delay_2 = await test_crawler._calculate_retry_delay(2)
        
        # Should use exponential backoff
        assert delay_0 >= 0.5
        assert delay_1 >= 1.0
        assert delay_2 >= 2.0
    
    def test_error_stats_update(self, test_crawler):
        """Test error statistics update"""
        error = Exception("Test error")
        category = ErrorCategory.NETWORK
        operation = "test_operation"
        
        initial_total = test_crawler.error_stats["total_errors"]
        
        test_crawler._update_error_stats(error, category, operation)
        
        assert test_crawler.error_stats["total_errors"] == initial_total + 1
        assert test_crawler.error_stats["errors_by_category"]["network"] == 1
        assert test_crawler.error_stats["errors_by_operation"]["test_operation"] == 1
        assert test_crawler.error_stats["last_error_time"] is not None
    
    def test_error_logging(self, test_crawler):
        """Test error logging"""
        error = Exception("Test error")
        context = ErrorContext(
            adapter_name="test_adapter",
            operation="test_operation",
            retry_count=1
        )
        category = ErrorCategory.NETWORK
        
        # Should not raise any exceptions
        test_crawler._log_enhanced_error(error, context, category)
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, test_crawler):
        """Test error recovery attempts"""
        error = Exception("Test error")
        context = ErrorContext(
            adapter_name="test_adapter",
            operation="test_operation",
            retry_count=0
        )
        
        # Test different recovery strategies
        network_recovery = await test_crawler._attempt_error_recovery(error, context, ErrorCategory.NETWORK)
        timeout_recovery = await test_crawler._attempt_error_recovery(error, context, ErrorCategory.TIMEOUT)
        
        assert network_recovery is True
        assert timeout_recovery is True
    
    def test_get_error_statistics(self, test_crawler):
        """Test error statistics retrieval"""
        # Add some test errors
        test_crawler._update_error_stats(Exception("test1"), ErrorCategory.NETWORK, "op1")
        test_crawler._update_error_stats(Exception("test2"), ErrorCategory.TIMEOUT, "op2")
        
        stats = test_crawler.get_error_statistics()
        
        assert "total_errors" in stats
        assert "errors_by_category" in stats
        assert "errors_by_operation" in stats
        assert stats["total_errors"] >= 2
    
    def test_reset_error_statistics(self, test_crawler):
        """Test error statistics reset"""
        # Add error first
        test_crawler._update_error_stats(Exception("test"), ErrorCategory.NETWORK, "test_op")
        
        # Verify error was added
        assert test_crawler.error_stats["total_errors"] > 0
        
        # Reset statistics
        test_crawler.reset_error_statistics()
        
        # Verify reset
        assert test_crawler.error_stats["total_errors"] == 0
        assert test_crawler.error_stats["errors_by_category"] == {}
        assert test_crawler.error_stats["errors_by_operation"] == {}
    
    def test_retry_config_methods(self, test_crawler):
        """Test retry configuration methods"""
        # Test retry config attribute access
        retry_config = test_crawler.retry_config
        assert retry_config is not None
        assert hasattr(retry_config, 'max_retries')
        assert hasattr(retry_config, 'base_delay')
        
        # Test retry config values
        assert retry_config.max_retries >= 0
        assert retry_config.base_delay >= 0
    
    @pytest.mark.asyncio
    async def test_memory_management(self, test_crawler):
        """Test memory management methods"""
        # Test memory limits checking
        test_crawler._check_memory_limits()
        
        # Test resource tracking
        resource_usage = test_crawler.get_resource_usage()
        assert "browser_count" in resource_usage
        assert "memory_usage_mb" in resource_usage
        
        # Test cleanup resources
        await test_crawler._cleanup_all_resources()
    
    @pytest.mark.asyncio
    async def test_execute_with_retry(self, test_crawler):
        """Test execute with retry mechanism"""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise AdapterNetworkError("Network failed")
            return "success"
        
        result = await test_crawler._execute_with_retry(
            failing_operation, 
            "test_operation",
            {"retry_count": 0}
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_handle_error_with_context(self, test_crawler):
        """Test comprehensive error handling with context"""
        error = AdapterNetworkError("Network failed")
        context = ErrorContext(
            adapter_name="test_adapter",
            operation="navigation",
            retry_count=0
        )
        
        # Test retryable error
        should_retry = await test_crawler._handle_error_with_context(error, context, should_retry=True)
        assert should_retry is True
        
        # Test non-retryable error
        validation_error = ValidationError("Invalid data")
        should_retry = await test_crawler._handle_error_with_context(validation_error, context, should_retry=False)
        assert should_retry is False 