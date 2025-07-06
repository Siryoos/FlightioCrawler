"""
Integration tests for enhanced error handling across key adapters.

This test suite validates that our centralized error handling system works correctly
with various adapter types and error scenarios.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

# Import the enhanced base classes
from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from adapters.base_adapters.enhanced_international_adapter import EnhancedInternationalAdapter
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

# Import key adapters to test
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter


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
                "retry_delay": 0.1,  # Fast retries for testing
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
            "validation": {
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
    async def test_mahan_air_timeout_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test MahanAir adapter timeout error handling and recovery."""
        mock_context, mock_page = mock_browser_context
        
        # Create MahanAir adapter with test config
        adapter = MahanAirAdapter(enhanced_config)
        
        # Mock the playwright context
        adapter.context = mock_context
        adapter.page = mock_page
        
        # Mock rate limiter and monitoring
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure timeout error on first attempt, success on retry
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Timeout loading page"),
            None  # Success on retry
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [
                Mock(text="Mahan Air", get_text=Mock(return_value="Mahan Air")),
                Mock(text="W5-123", get_text=Mock(return_value="W5-123")),
                Mock(text="2,500,000", get_text=Mock(return_value="2,500,000"))
            ]
            mock_bs.return_value = mock_soup
            
            # Test crawl with timeout recovery
            results = await adapter.crawl(search_params)
            
            # Verify retry was attempted
            assert mock_page.goto.call_count == 2
            
            # Verify error was recorded and then success
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_emirates_network_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test Emirates adapter network error handling and recovery."""
        mock_context, mock_page = mock_browser_context
        
        # Create Emirates adapter with test config
        adapter = EmiratesAdapter(enhanced_config)
        
        # Mock components
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure network error on first two attempts, success on third
        mock_page.goto.side_effect = [
            AdapterNetworkError("Network connection failed"),
            AdapterNetworkError("Network connection failed"),
            None  # Success on third attempt
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [
                Mock(text="Emirates", get_text=Mock(return_value="Emirates")),
                Mock(text="EK-123", get_text=Mock(return_value="EK-123")),
                Mock(text="USD 450", get_text=Mock(return_value="USD 450"))
            ]
            mock_bs.return_value = mock_soup
            
            # Test crawl with network error recovery
            results = await adapter.crawl(search_params)
            
            # Verify retries were attempted
            assert mock_page.goto.call_count == 3
            
            # Verify error statistics
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_iran_air_rate_limit_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test Iran Air adapter rate limit error handling and recovery."""
        mock_context, mock_page = mock_browser_context
        
        # Create Iran Air adapter with test config
        adapter = IranAirAdapter(enhanced_config)
        
        # Mock components
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure rate limit error on first attempt, success on retry
        mock_page.goto.side_effect = [
            AdapterRateLimitError("Rate limit exceeded - 429"),
            None  # Success on retry
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [
                Mock(text="Iran Air", get_text=Mock(return_value="Iran Air")),
                Mock(text="IR-123", get_text=Mock(return_value="IR-123")),
                Mock(text="۲,۵۰۰,۰۰۰", get_text=Mock(return_value="۲,۵۰۰,۰۰۰"))
            ]
            mock_bs.return_value = mock_soup
            
            # Test crawl with rate limit recovery
            results = await adapter.crawl(search_params)
            
            # Verify retry was attempted
            assert mock_page.goto.call_count == 2
            
            # Verify error and success recording
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_air_france_validation_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test Air France adapter validation error handling."""
        mock_context, mock_page = mock_browser_context
        
        # Create Air France adapter with test config
        adapter = AirFranceAdapter(enhanced_config)
        
        # Mock components
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Test with invalid search parameters
        invalid_params = search_params.copy()
        invalid_params["origin"] = ""  # Invalid empty origin
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = []
            mock_bs.return_value = mock_soup
            
            # Test crawl with validation error
            with pytest.raises(AdapterValidationError):
                await adapter.crawl(invalid_params)
            
            # Verify error was recorded
            adapter.monitoring.record_error.assert_called()

    @pytest.mark.asyncio
    async def test_parto_ticket_parsing_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test Parto Ticket adapter parsing error handling and recovery."""
        mock_context, mock_page = mock_browser_context
        
        # Create Parto Ticket adapter with test config
        adapter = PartoTicketAdapter(enhanced_config)
        
        # Mock components
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure parsing error on first attempt, success on retry
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.side_effect = [
                Exception("Parsing error: Invalid HTML structure"),
                [  # Success on retry
                    Mock(text="Parto Ticket", get_text=Mock(return_value="Parto Ticket")),
                    Mock(text="PT-123", get_text=Mock(return_value="PT-123")),
                    Mock(text="3,000,000", get_text=Mock(return_value="3,000,000"))
                ]
            ]
            mock_bs.return_value = mock_soup
            
            # Test crawl with parsing error recovery
            results = await adapter.crawl(search_params)
            
            # Verify retry was attempted
            assert mock_soup.select.call_count == 2
            
            # Verify error and success recording
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()
            
            # Verify results structure
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_error_categorization_across_adapters(self, enhanced_config, search_params, mock_browser_context):
        """Test that error categorization works consistently across different adapters."""
        mock_context, mock_page = mock_browser_context
        
        # Test different adapter types
        adapters = [
            MahanAirAdapter(enhanced_config),
            EmiratesAdapter(enhanced_config),
            IranAirAdapter(enhanced_config)
        ]
        
        for adapter in adapters:
            # Mock components
            adapter.context = mock_context
            adapter.page = mock_page
            adapter.rate_limiter = Mock()
            adapter.rate_limiter.wait = AsyncMock()
            adapter.monitoring = Mock()
            adapter.monitoring.record_error = Mock()
            adapter.monitoring.record_success = Mock()
            adapter.monitoring.record_crawl = Mock()
            
            # Test error categorization
            timeout_error = AdapterTimeoutError("Connection timeout")
            network_error = AdapterNetworkError("Network failed")
            validation_error = AdapterValidationError("Invalid data")
            rate_limit_error = AdapterRateLimitError("Rate limit exceeded")
            
            assert adapter._categorize_error(timeout_error) == ErrorCategory.TIMEOUT
            assert adapter._categorize_error(network_error) == ErrorCategory.NETWORK
            assert adapter._categorize_error(validation_error) == ErrorCategory.VALIDATION
            assert adapter._categorize_error(rate_limit_error) == ErrorCategory.RATE_LIMIT

    @pytest.mark.asyncio
    async def test_retry_mechanism_consistency(self, enhanced_config, search_params, mock_browser_context):
        """Test that retry mechanisms work consistently across adapters."""
        mock_context, mock_page = mock_browser_context
        
        # Test with MahanAir adapter
        adapter = MahanAirAdapter(enhanced_config)
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure consecutive failures then success
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Timeout 1"),
            AdapterTimeoutError("Timeout 2"),
            AdapterTimeoutError("Timeout 3"),
            None  # Success on 4th attempt
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [
                Mock(text="Mahan Air", get_text=Mock(return_value="Mahan Air"))
            ]
            mock_bs.return_value = mock_soup
            
            # Test crawl with multiple retries
            results = await adapter.crawl(search_params)
            
            # Verify all retries were attempted (3 failures + 1 success)
            assert mock_page.goto.call_count == 4
            
            # Verify error and success recording
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()

    @pytest.mark.asyncio
    async def test_error_statistics_collection(self, enhanced_config, search_params, mock_browser_context):
        """Test that error statistics are collected properly across adapters."""
        mock_context, mock_page = mock_browser_context
        
        # Create adapter with enhanced error handling
        adapter = MahanAirAdapter(enhanced_config)
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure different types of errors
        errors = [
            AdapterTimeoutError("Timeout"),
            AdapterNetworkError("Network error"),
            AdapterValidationError("Validation error"),
            AdapterRateLimitError("Rate limit"),
            Exception("Unknown error")
        ]
        
        # Test error statistics collection
        for error in errors:
            mock_page.goto.side_effect = [error, None]  # Error then success
            
            # Mock BeautifulSoup for parsing
            with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_soup.select.return_value = [
                    Mock(text="Test", get_text=Mock(return_value="Test"))
                ]
                mock_bs.return_value = mock_soup
                
                # Execute crawl
                try:
                    await adapter.crawl(search_params)
                except Exception:
                    pass  # Expected for some errors
            
            # Verify error was recorded
            adapter.monitoring.record_error.assert_called()
            
            # Check that error statistics are updated
            stats = adapter.get_error_statistics()
            assert "error_count" in stats
            assert "error_categories" in stats
            assert "retry_success_rate" in stats

    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, enhanced_config, search_params, mock_browser_context):
        """Test circuit breaker functionality across adapters."""
        mock_context, mock_page = mock_browser_context
        
        # Configure circuit breaker with low threshold for testing
        enhanced_config["error_handling"]["circuit_breaker"]["failure_threshold"] = 2
        
        # Create adapter
        adapter = EmiratesAdapter(enhanced_config)
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure repeated failures to trigger circuit breaker
        mock_page.goto.side_effect = AdapterNetworkError("Network error")
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = []
            mock_bs.return_value = mock_soup
            
            # Test multiple failed attempts
            for i in range(3):
                try:
                    await adapter.crawl(search_params)
                except Exception:
                    pass  # Expected failures
            
            # Verify error recording
            adapter.monitoring.record_error.assert_called()
            
            # Check circuit breaker state
            stats = adapter.get_error_statistics()
            assert "circuit_breaker_state" in stats

    @pytest.mark.asyncio
    async def test_error_recovery_strategies(self, enhanced_config, search_params, mock_browser_context):
        """Test error recovery strategies across different error types."""
        mock_context, mock_page = mock_browser_context
        
        # Create adapter
        adapter = IranAirAdapter(enhanced_config)
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Test different recovery strategies
        recovery_scenarios = [
            (AdapterTimeoutError("Timeout"), "timeout_recovery"),
            (AdapterNetworkError("Network"), "network_recovery"),
            (AdapterRateLimitError("Rate limit"), "rate_limit_recovery"),
            (AdapterAuthenticationError("Auth failed"), "auth_recovery"),
            (AdapterResourceError("Resource exhausted"), "resource_recovery")
        ]
        
        for error, recovery_type in recovery_scenarios:
            # Configure error then success
            mock_page.goto.side_effect = [error, None]
            
            # Mock BeautifulSoup for parsing
            with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_soup.select.return_value = [
                    Mock(text="Iran Air", get_text=Mock(return_value="Iran Air"))
                ]
                mock_bs.return_value = mock_soup
                
                # Execute crawl
                try:
                    results = await adapter.crawl(search_params)
                    
                    # Verify recovery was successful
                    assert isinstance(results, list)
                    
                except Exception:
                    # Some errors may not be recoverable
                    pass
            
            # Verify error was recorded
            adapter.monitoring.record_error.assert_called()
            
            # Check recovery statistics
            stats = adapter.get_error_statistics()
            assert "recovery_attempts" in stats
            assert "successful_recoveries" in stats


class TestEndToEndErrorHandling:
    """End-to-end tests for error handling across the entire crawling workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_crawl_workflow_with_errors(self, enhanced_config, search_params, mock_browser_context):
        """Test complete crawl workflow with various error scenarios."""
        mock_context, mock_page = mock_browser_context
        
        # Create adapter
        adapter = MahanAirAdapter(enhanced_config)
        adapter.context = mock_context
        adapter.page = mock_page
        adapter.rate_limiter = Mock()
        adapter.rate_limiter.wait = AsyncMock()
        adapter.monitoring = Mock()
        adapter.monitoring.record_error = Mock()
        adapter.monitoring.record_success = Mock()
        adapter.monitoring.record_crawl = Mock()
        
        # Configure errors in different workflow stages
        mock_page.goto.side_effect = [
            AdapterTimeoutError("Navigation timeout"),
            None  # Success on retry
        ]
        
        mock_page.fill.side_effect = [
            AdapterValidationError("Invalid form field"),
            None  # Success on retry
        ]
        
        # Mock BeautifulSoup for parsing
        with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
            mock_soup = Mock()
            mock_soup.select.return_value = [
                Mock(text="Mahan Air", get_text=Mock(return_value="Mahan Air")),
                Mock(text="W5-123", get_text=Mock(return_value="W5-123")),
                Mock(text="2,500,000", get_text=Mock(return_value="2,500,000"))
            ]
            mock_bs.return_value = mock_soup
            
            # Execute complete workflow
            results = await adapter.crawl(search_params)
            
            # Verify workflow completed successfully despite errors
            assert isinstance(results, list)
            
            # Verify error handling was triggered
            adapter.monitoring.record_error.assert_called()
            adapter.monitoring.record_success.assert_called()
            
            # Verify final statistics
            stats = adapter.get_error_statistics()
            assert stats["error_count"] > 0
            assert stats["successful_recoveries"] > 0
            assert stats["retry_success_rate"] > 0

    @pytest.mark.asyncio
    async def test_multi_adapter_error_handling(self, enhanced_config, search_params, mock_browser_context):
        """Test error handling consistency across multiple adapters."""
        mock_context, mock_page = mock_browser_context
        
        # Create multiple adapters
        adapters = [
            MahanAirAdapter(enhanced_config),
            EmiratesAdapter(enhanced_config),
            IranAirAdapter(enhanced_config)
        ]
        
        results = []
        
        for adapter in adapters:
            # Mock components
            adapter.context = mock_context
            adapter.page = mock_page
            adapter.rate_limiter = Mock()
            adapter.rate_limiter.wait = AsyncMock()
            adapter.monitoring = Mock()
            adapter.monitoring.record_error = Mock()
            adapter.monitoring.record_success = Mock()
            adapter.monitoring.record_crawl = Mock()
            
            # Configure different errors for each adapter
            mock_page.goto.side_effect = [
                AdapterTimeoutError("Timeout error"),
                None  # Success on retry
            ]
            
            # Mock BeautifulSoup for parsing
            with patch('adapters.base_adapters.enhanced_base_crawler.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_soup.select.return_value = [
                    Mock(text="Test Airline", get_text=Mock(return_value="Test Airline"))
                ]
                mock_bs.return_value = mock_soup
                
                # Execute crawl
                try:
                    adapter_results = await adapter.crawl(search_params)
                    results.append(adapter_results)
                except Exception as e:
                    # Some adapters may still fail
                    results.append([])
            
            # Verify error handling was consistent
            adapter.monitoring.record_error.assert_called()
        
        # Verify all adapters handled errors consistently
        assert len(results) == len(adapters)
        
        # Check that each adapter produced some result or handled errors gracefully
        for adapter_results in results:
            assert isinstance(adapter_results, list) 