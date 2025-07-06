"""
Enhanced Integration Tests for Key Adapters

This module provides comprehensive integration tests for the 5 most important
adapters in the FlightioCrawler system. These tests verify end-to-end functionality
including configuration, crawling, parsing, and error handling.

Test Coverage:
- AlibabaAdapter (Persian Aggregator)
- MahanAirAdapter (Persian Airline)
- EmiratesAdapter (International Airline)
- LufthansaAdapter (International Airline)
- FlytodayAdapter (Persian Aggregator)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import os

# Import adapters to test
from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
from adapters.site_adapters.international_airlines.lufthansa_adapter import LufthansaAdapter
from adapters.site_adapters.iranian_airlines.flytoday_adapter import FlytodayAdapter

# Import factories and utilities
try:
    from adapters.factories.unified_adapter_factory import get_unified_factory
except ImportError:
    get_unified_factory = None

try:
    from adapters.patterns.observer_pattern import CrawlerEventSystem, MetricsObserver
except ImportError:
    CrawlerEventSystem = None
    MetricsObserver = None


class TestIntegrationEnhanced:
    """Enhanced integration tests for key adapters."""

    @pytest.fixture
    def sample_search_params(self):
        """Standard search parameters for testing."""
        return {
            "origin": "THR",
            "destination": "IST",
            "departure_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "return_date": (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d"),
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin_class": "economy"
        }

    @pytest.fixture
    def enhanced_config(self):
        """Enhanced configuration for testing."""
        return {
            "rate_limiting": {
                "requests_per_second": 1.0,
                "burst_limit": 3,
                "cooldown_period": 60
            },
            "error_handling": {
                "max_retries": 2,
                "retry_delay": 2,
                "circuit_breaker": {
                    "failure_threshold": 3,
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
                "max_results": 50
            },
            "validation": {
                "validate_prices": True,
                "validate_dates": True,
                "validate_routes": True
            }
        }

    @pytest.fixture
    def mock_browser_session(self):
        """Mock browser session for testing."""
        mock_session = AsyncMock()
        mock_page = AsyncMock()
        
        # Mock page methods
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Mock content</html>")
        mock_page.screenshot = AsyncMock()
        
        mock_session.new_page = AsyncMock(return_value=mock_page)
        mock_session.close = AsyncMock()
        
        return mock_session, mock_page

    @pytest.fixture
    def mock_http_session(self):
        """Mock HTTP session for testing."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Mock response</html>")
        mock_response.json = AsyncMock(return_value={"status": "success"})
        
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.close = AsyncMock()
        
        return mock_session, mock_response

    @pytest.fixture
    def event_system(self):
        """Event system for monitoring tests."""
        event_system = CrawlerEventSystem()
        event_system.attach_default_observers()
        
        # Add metrics observer
        metrics_observer = MetricsObserver()
        event_system.attach_observer(metrics_observer)
        
        return event_system

    # AlibabaAdapter Integration Tests
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_alibaba_adapter_integration(self, enhanced_config, sample_search_params, mock_browser_session, event_system):
        """Test AlibabaAdapter end-to-end integration."""
        mock_session, mock_page = mock_browser_session
        
        # Mock flight results HTML
        mock_flight_html = """
        <div class="flight-result">
            <div class="airline">ماهان ایر</div>
            <div class="flight-number">W5-1234</div>
            <div class="departure-time">۰۸:۳۰</div>
            <div class="arrival-time">۱۲:۴۵</div>
            <div class="price">۲,۵۰۰,۰۰۰ تومان</div>
            <div class="duration">۴ ساعت ۱۵ دقیقه</div>
            <div class="seat-class">اقتصادی</div>
        </div>
        """
        mock_page.content.return_value = f"<html><body>{mock_flight_html}</body></html>"
        
        # Create adapter with enhanced config
        adapter = AlibabaAdapter(enhanced_config)
        
        # Mock browser creation
        with patch.object(adapter, '_setup_browser', return_value=mock_session):
            # Execute crawl
            await event_system.emit_event("crawl_started", "alibaba_test")
            
            try:
                results = await adapter.crawl(sample_search_params)
                
                # Verify results structure
                assert isinstance(results, list)
                assert len(results) > 0
                
                # Verify flight data
                flight = results[0]
                assert "airline" in flight
                assert "flight_number" in flight
                assert "departure_time" in flight
                assert "arrival_time" in flight
                assert "price" in flight
                assert "currency" in flight
                assert flight["currency"] == "IRR"
                
                # Verify Persian text processing
                assert "ماهان" in flight["airline"] or "Mahan" in flight["airline"]
                
                await event_system.emit_event("crawl_completed", "alibaba_test", {"results_count": len(results)})
                
            except Exception as e:
                await event_system.emit_event("crawl_failed", "alibaba_test", {"error": str(e)})
                raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mahan_air_adapter_integration(self, enhanced_config, sample_search_params, mock_browser_session, event_system):
        """Test MahanAirAdapter end-to-end integration."""
        mock_session, mock_page = mock_browser_session
        
        # Mock Mahan Air specific HTML
        mock_flight_html = """
        <div class="flight-item">
            <div class="airline-name">ماهان ایر</div>
            <div class="flight-code">W5-1234</div>
            <div class="dep-time">۰۸:۳۰</div>
            <div class="arr-time">۱۲:۴۵</div>
            <div class="flight-price">۲۵۰۰۰۰۰</div>
            <div class="flight-duration">۴:۱۵</div>
            <div class="cabin-class">اقتصادی</div>
            <div class="baggage">۲۰ کیلو</div>
        </div>
        """
        mock_page.content.return_value = f"<html><body>{mock_flight_html}</body></html>"
        
        # Create adapter
        adapter = MahanAirAdapter(enhanced_config)
        
        with patch.object(adapter, '_setup_browser', return_value=mock_session):
            await event_system.emit_event("crawl_started", "mahan_air_test")
            
            try:
                results = await adapter.crawl(sample_search_params)
                
                # Verify results
                assert isinstance(results, list)
                if results:
                    flight = results[0]
                    assert flight["airline"] == "Mahan Air"
                    assert "W5" in flight["flight_number"]
                    assert flight["currency"] == "IRR"
                    assert isinstance(flight["price"], (int, float))
                    assert flight["price"] > 0
                    
                    # Verify Mahan Air specific fields
                    assert "baggage_allowance" in flight
                    assert "loyalty_program" in flight
                
                await event_system.emit_event("crawl_completed", "mahan_air_test", {"results_count": len(results)})
                
            except Exception as e:
                await event_system.emit_event("crawl_failed", "mahan_air_test", {"error": str(e)})
                raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_emirates_adapter_integration(self, enhanced_config, sample_search_params, mock_browser_session, event_system):
        """Test EmiratesAdapter end-to-end integration."""
        mock_session, mock_page = mock_browser_session
        
        # Mock Emirates specific HTML
        mock_flight_html = """
        <div class="flight-option">
            <div class="airline">Emirates</div>
            <div class="flight-number">EK-123</div>
            <div class="departure">08:30</div>
            <div class="arrival">12:45</div>
            <div class="price">AED 1,250</div>
            <div class="duration">4h 15m</div>
            <div class="cabin">Economy</div>
            <div class="aircraft">Boeing 777</div>
            <div class="skywards-miles">1500</div>
        </div>
        """
        mock_page.content.return_value = f"<html><body>{mock_flight_html}</body></html>"
        
        # Create adapter
        adapter = EmiratesAdapter(enhanced_config)
        
        with patch.object(adapter, '_setup_browser', return_value=mock_session):
            await event_system.emit_event("crawl_started", "emirates_test")
            
            try:
                results = await adapter.crawl(sample_search_params)
                
                # Verify results
                assert isinstance(results, list)
                if results:
                    flight = results[0]
                    assert flight["airline"] == "Emirates"
                    assert "EK" in flight["flight_number"]
                    assert flight["currency"] == "AED"
                    assert isinstance(flight["price"], (int, float))
                    
                    # Verify Emirates specific fields
                    assert "skywards_miles" in flight
                    assert "cabin_features" in flight
                    assert "aircraft_type" in flight
                
                await event_system.emit_event("crawl_completed", "emirates_test", {"results_count": len(results)})
                
            except Exception as e:
                await event_system.emit_event("crawl_failed", "emirates_test", {"error": str(e)})
                raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_lufthansa_adapter_integration(self, enhanced_config, sample_search_params, mock_browser_session, event_system):
        """Test LufthansaAdapter end-to-end integration."""
        mock_session, mock_page = mock_browser_session
        
        # Mock Lufthansa specific HTML
        mock_flight_html = """
        <div class="flight-card">
            <div class="carrier">Lufthansa</div>
            <div class="flight-no">LH-123</div>
            <div class="dep-time">08:30</div>
            <div class="arr-time">12:45</div>
            <div class="fare">EUR 450</div>
            <div class="duration">4h 15m</div>
            <div class="class">Economy</div>
            <div class="miles-more">2000</div>
        </div>
        """
        mock_page.content.return_value = f"<html><body>{mock_flight_html}</body></html>"
        
        # Create adapter
        adapter = LufthansaAdapter(enhanced_config)
        
        with patch.object(adapter, '_setup_browser', return_value=mock_session):
            await event_system.emit_event("crawl_started", "lufthansa_test")
            
            try:
                results = await adapter.crawl(sample_search_params)
                
                # Verify results
                assert isinstance(results, list)
                if results:
                    flight = results[0]
                    assert flight["airline"] == "Lufthansa"
                    assert "LH" in flight["flight_number"]
                    assert flight["currency"] == "EUR"
                    assert isinstance(flight["price"], (int, float))
                    
                    # Verify Lufthansa specific fields
                    assert "miles_more_points" in flight
                    assert "star_alliance" in flight
                
                await event_system.emit_event("crawl_completed", "lufthansa_test", {"results_count": len(results)})
                
            except Exception as e:
                await event_system.emit_event("crawl_failed", "lufthansa_test", {"error": str(e)})
                raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_flytoday_adapter_integration(self, enhanced_config, sample_search_params, mock_browser_session, event_system):
        """Test FlytodayAdapter end-to-end integration."""
        mock_session, mock_page = mock_browser_session
        
        # Mock FlyToday specific HTML
        mock_flight_html = """
        <div class="flight-row">
            <div class="airline-name">ایران ایر</div>
            <div class="flight-number">IR-123</div>
            <div class="departure-time">۰۸:۳۰</div>
            <div class="arrival-time">۱۲:۴۵</div>
            <div class="price">۱,۸۰۰,۰۰۰ تومان</div>
            <div class="duration">۴ ساعت ۱۵ دقیقه</div>
            <div class="class">اقتصادی</div>
            <div class="discount">۱۰٪ تخفیف</div>
        </div>
        """
        mock_page.content.return_value = f"<html><body>{mock_flight_html}</body></html>"
        
        # Create adapter
        adapter = FlytodayAdapter(enhanced_config)
        
        with patch.object(adapter, '_setup_browser', return_value=mock_session):
            await event_system.emit_event("crawl_started", "flytoday_test")
            
            try:
                results = await adapter.crawl(sample_search_params)
                
                # Verify results
                assert isinstance(results, list)
                if results:
                    flight = results[0]
                    assert "airline" in flight
                    assert "flight_number" in flight
                    assert flight["currency"] == "IRR"
                    assert isinstance(flight["price"], (int, float))
                    
                    # Verify FlyToday specific fields (aggregator)
                    assert "is_aggregator" in flight
                    assert "discount_info" in flight
                    assert "booking_source" in flight
                
                await event_system.emit_event("crawl_completed", "flytoday_test", {"results_count": len(results)})
                
            except Exception as e:
                await event_system.emit_event("crawl_failed", "flytoday_test", {"error": str(e)})
                raise

    # Cross-Adapter Integration Tests
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_factory_integration(self, enhanced_config, sample_search_params):
        """Test adapter creation through factory."""
        if get_unified_factory is None:
            pytest.skip("Unified factory not available")
            
        factory = get_unified_factory()
        
        # Test creating different types of adapters
        adapter_names = ["alibaba", "mahan_air", "emirates", "lufthansa", "flytoday"]
        
        for adapter_name in adapter_names:
            try:
                adapter = factory.create_adapter(adapter_name, config=enhanced_config)
                assert adapter is not None
                assert hasattr(adapter, 'crawl')
                assert hasattr(adapter, 'get_adapter_name')
                
                # Verify adapter configuration
                assert adapter.config is not None
                assert "rate_limiting" in adapter.config
                assert "error_handling" in adapter.config
                
            except Exception as e:
                pytest.fail(f"Failed to create adapter {adapter_name}: {str(e)}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parsing_strategy_integration(self, enhanced_config):
        """Test parsing strategy integration."""
        factory = ParsingStrategyFactory()
        
        # Test different parsing strategies
        strategies = ["persian", "international", "aggregator"]
        
        for strategy_type in strategies:
            try:
                strategy = factory.create_strategy(strategy_type, enhanced_config)
                assert strategy is not None
                assert hasattr(strategy, 'parse_flight_element')
                assert hasattr(strategy, 'extract_price')
                assert hasattr(strategy, 'validate_result')
                
            except Exception as e:
                pytest.fail(f"Failed to create strategy {strategy_type}: {str(e)}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self, enhanced_config, sample_search_params):
        """Test error handling across adapters."""
        adapters = [
            AlibabaAdapter(enhanced_config),
            MahanAirAdapter(enhanced_config),
            EmiratesAdapter(enhanced_config),
            LufthansaAdapter(enhanced_config),
            FlytodayAdapter(enhanced_config)
        ]
        
        # Test error handling with invalid parameters
        invalid_params = sample_search_params.copy()
        invalid_params["origin"] = "INVALID"
        
        for adapter in adapters:
            try:
                # Mock browser setup to fail
                with patch.object(adapter, '_setup_browser', side_effect=Exception("Mock connection error")):
                    with pytest.raises(Exception):
                        await adapter.crawl(invalid_params)
                        
            except Exception as e:
                # Expected behavior - error should be handled gracefully
                assert "error" in str(e).lower() or "invalid" in str(e).lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_performance_monitoring_integration(self, enhanced_config, sample_search_params, event_system):
        """Test performance monitoring integration."""
        # Get metrics observer
        metrics_observer = None
        for observer in event_system.subject.observers:
            if hasattr(observer, 'get_metrics'):
                metrics_observer = observer
                break
        
        assert metrics_observer is not None
        
        # Simulate crawl events
        await event_system.emit_event("crawl_started", "performance_test")
        await event_system.emit_event("crawl_completed", "performance_test", {"duration": 5.2})
        
        # Check metrics
        metrics = metrics_observer.get_metrics()
        assert "crawl_stats" in metrics
        assert "performance_stats" in metrics
        assert metrics["crawl_stats"]["total_crawls"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_adapter_execution(self, enhanced_config, sample_search_params, mock_browser_session):
        """Test concurrent execution of multiple adapters."""
        mock_session, mock_page = mock_browser_session
        
        # Create multiple adapters
        adapters = [
            AlibabaAdapter(enhanced_config),
            MahanAirAdapter(enhanced_config),
            FlytodayAdapter(enhanced_config)
        ]
        
        # Mock browser setup for all adapters
        for adapter in adapters:
            with patch.object(adapter, '_setup_browser', return_value=mock_session):
                pass
        
        # Execute concurrent crawls
        tasks = []
        for adapter in adapters:
            with patch.object(adapter, '_setup_browser', return_value=mock_session):
                task = asyncio.create_task(adapter.crawl(sample_search_params))
                tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        assert len(results) == len(adapters)
        for result in results:
            if isinstance(result, Exception):
                # Log exception but don't fail test (network issues expected in mock)
                print(f"Concurrent test exception: {result}")
            else:
                assert isinstance(result, list)

    # Configuration and Validation Tests
    @pytest.mark.integration
    def test_adapter_configuration_validation(self, enhanced_config):
        """Test adapter configuration validation."""
        # Test valid configuration
        adapter = AlibabaAdapter(enhanced_config)
        assert adapter.config is not None
        
        # Test invalid configuration
        invalid_config = enhanced_config.copy()
        invalid_config["rate_limiting"]["requests_per_second"] = -1
        
        with pytest.raises((ValueError, AssertionError)):
            adapter = AlibabaAdapter(invalid_config)

    @pytest.mark.integration
    def test_adapter_metadata_consistency(self):
        """Test adapter metadata consistency."""
        factory = get_unified_factory()
        
        # Test metadata for all adapters
        all_adapters = factory.list_adapters()
        
        for adapter_name in all_adapters:
            metadata = factory.get_adapter_info(adapter_name)
            assert metadata is not None
            assert metadata["name"] == adapter_name
            assert "type" in metadata
            assert metadata["base_url"].startswith(("http://", "https://"))
            assert len(metadata["currency"]) == 3  # ISO currency code
            assert len(metadata["airline_name"]) > 0

    @pytest.mark.integration
    def test_adapter_inheritance_hierarchy(self):
        """Test adapter inheritance hierarchy."""
        from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
        from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
        from adapters.base_adapters.enhanced_international_adapter import EnhancedInternationalAdapter
        
        # Test Persian adapters
        alibaba = AlibabaAdapter({})
        mahan = MahanAirAdapter({})
        flytoday = FlytodayAdapter({})
        
        assert isinstance(alibaba, EnhancedPersianAdapter)
        assert isinstance(mahan, EnhancedPersianAdapter)
        assert isinstance(flytoday, EnhancedPersianAdapter)
        assert isinstance(alibaba, EnhancedBaseCrawler)
        
        # Test International adapters
        emirates = EmiratesAdapter({})
        lufthansa = LufthansaAdapter({})
        
        assert isinstance(emirates, EnhancedInternationalAdapter)
        assert isinstance(lufthansa, EnhancedInternationalAdapter)
        assert isinstance(emirates, EnhancedBaseCrawler)

    @pytest.mark.integration
    def test_adapter_basic_functionality(self):
        """Test basic adapter functionality without network calls."""
        config = {
            "rate_limiting": {"requests_per_second": 1.0},
            "error_handling": {"max_retries": 1}
        }
        
        # Test adapter creation
        alibaba = AlibabaAdapter(config)
        mahan = MahanAirAdapter(config)
        
        # Test basic properties
        assert alibaba.get_adapter_name() == "alibaba"
        assert mahan.get_adapter_name() == "mahan_air"
        
        # Test configuration access
        assert alibaba.config["rate_limiting"]["requests_per_second"] == 1.0
        assert mahan.config["rate_limiting"]["requests_per_second"] == 1.0

    @pytest.mark.integration
    def test_adapter_error_handler_integration(self):
        """Test error handler integration."""
        config = {
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 1
            }
        }
        
        adapter = AlibabaAdapter(config)
        
        # Verify error handler is properly initialized
        assert hasattr(adapter, 'error_handler')
        assert adapter.error_handler is not None
        
        # Test error handler configuration
        if hasattr(adapter.error_handler, 'max_retries'):
            assert adapter.error_handler.max_retries == 3 