"""
Comprehensive tests for enhanced base classes and refactored adapters.

This test suite covers:
- EnhancedBaseCrawler functionality
- EnhancedPersianAdapter functionality  
- EnhancedInternationalAdapter functionality
- CommonErrorHandler functionality
- AdapterFactory functionality
- All refactored adapters
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any

from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter
from adapters.base_adapters.enhanced_international_adapter import EnhancedInternationalAdapter
from adapters.base_adapters.common_error_handler import CommonErrorHandler, error_handler, safe_extract
from adapters.factories.adapter_factory import AdapterFactory

# Import all refactored adapters
from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter
from adapters.site_adapters.iranian_airlines.flytoday_adapter import FlytodayAdapter
from adapters.site_adapters.iranian_airlines.book_charter_adapter import BookCharterAdapter
from adapters.site_adapters.iranian_airlines.book_charter_724_adapter import BookCharter724Adapter
from adapters.site_adapters.iranian_airlines.iranair_aseman_adapter import IranAirAsemanAdapter
from adapters.site_adapters.iranian_airlines.iran_air_tour_adapter import IranAirTourAdapter
from adapters.site_adapters.iranian_airlines.mz724_adapter import Mz724Adapter
from adapters.site_adapters.iranian_airlines.parto_crs_adapter import PartoCRSAdapter
from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
from adapters.site_adapters.iranian_airlines.safarmarket_adapter import SafarmarketAdapter
from adapters.site_adapters.iranian_airlines.iran_aseman_air_adapter import IranAsemanAirAdapter

# Import international adapters
from adapters.site_adapters.international_airlines.lufthansa_adapter import LufthansaAdapter
from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
from adapters.site_adapters.international_airlines.british_airways_adapter import BritishAirwaysAdapter
from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
from adapters.site_adapters.international_airlines.etihad_airways_adapter import EtihadAirwaysAdapter
from adapters.site_adapters.international_airlines.klm_adapter import KLMAdapter
from adapters.site_adapters.international_airlines.pegasus_adapter import PegasusAdapter
from adapters.site_adapters.international_airlines.qatar_airways_adapter import QatarAirwaysAdapter
from adapters.site_adapters.international_airlines.turkish_airlines_adapter import TurkishAirlinesAdapter


class TestEnhancedBaseCrawler:
    """Test the enhanced base crawler functionality."""
    
    @pytest.fixture
    def mock_config(self):
        return {
            "base_url": "https://example.com",
            "search_url": "https://example.com/search",
            "rate_limiting": {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 1,
                "circuit_breaker": {
                    "failure_threshold": 5,
                    "recovery_timeout": 30
                }
            },
            "monitoring": {
                "enabled": True,
                "metrics_endpoint": "http://localhost:9090"
            },
            "extraction_config": {
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
            }
        }
    
    @pytest.fixture
    def enhanced_crawler(self, mock_config):
        return EnhancedBaseCrawler(mock_config)
    
    def test_initialization(self, enhanced_crawler, mock_config):
        """Test that enhanced crawler initializes correctly."""
        assert enhanced_crawler.config == mock_config
        assert enhanced_crawler.logger is not None
        assert enhanced_crawler.error_handler is not None
        assert enhanced_crawler.rate_limiter is not None
        assert enhanced_crawler.monitoring is not None
    
    def test_get_base_url_abstract(self, enhanced_crawler):
        """Test that _get_base_url is abstract."""
        with pytest.raises(NotImplementedError):
            enhanced_crawler._get_base_url()
    
    def test_extract_currency_abstract(self, enhanced_crawler):
        """Test that _extract_currency is abstract."""
        with pytest.raises(NotImplementedError):
            enhanced_crawler._extract_currency(None, {})
    
    @pytest.mark.asyncio
    async def test_crawl_template_method(self, enhanced_crawler, mock_config):
        """Test the template method pattern in crawl."""
        # Mock the abstract methods
        enhanced_crawler._get_base_url = Mock(return_value="https://example.com")
        enhanced_crawler._extract_currency = Mock(return_value="USD")
        enhanced_crawler._navigate_to_search_page = AsyncMock()
        enhanced_crawler._fill_search_form = AsyncMock()
        enhanced_crawler._extract_flight_results = AsyncMock(return_value=[])
        enhanced_crawler._validate_search_params = Mock()
        enhanced_crawler._validate_flight_data = Mock(return_value=[])
        
        search_params = {
            "origin": "NYC",
            "destination": "LAX",
            "departure_date": "2024-06-01"
        }
        
        result = await enhanced_crawler.crawl(search_params)
        
        # Verify template method calls
        enhanced_crawler._validate_search_params.assert_called_once_with(search_params)
        enhanced_crawler._navigate_to_search_page.assert_called_once()
        enhanced_crawler._fill_search_form.assert_called_once_with(search_params)
        enhanced_crawler._extract_flight_results.assert_called_once()
        enhanced_crawler._validate_flight_data.assert_called_once()


class TestEnhancedPersianAdapter:
    """Test the enhanced Persian adapter functionality."""
    
    @pytest.fixture
    def mock_config(self):
        return {
            "base_url": "https://example.ir",
            "extraction_config": {
                "search_form": {
                    "origin_field": "#origin",
                    "destination_field": "#destination"
                },
                "results_parsing": {
                    "container": ".flight-result",
                    "airline": ".airline",
                    "price": ".price"
                }
            },
            "rate_limiting": {"requests_per_second": 1},
            "error_handling": {"max_retries": 2},
            "monitoring": {"enabled": True}
        }
    
    @pytest.fixture
    def persian_adapter(self, mock_config):
        return EnhancedPersianAdapter(mock_config)
    
    def test_persian_initialization(self, persian_adapter):
        """Test Persian adapter specific initialization."""
        assert persian_adapter.default_currency == "IRR"
        assert persian_adapter.persian_processor is not None
        assert "فروردین" in persian_adapter.persian_months
        assert "۰" in persian_adapter.persian_to_english_numbers
        assert "ایران ایر" in persian_adapter.airline_name_mappings
    
    def test_convert_persian_numbers(self, persian_adapter):
        """Test Persian number conversion."""
        persian_text = "قیمت: ۱۲۳۴۵۶۷۸۹۰ تومان"
        result = persian_adapter._convert_persian_numbers(persian_text)
        assert "1234567890" in result
    
    def test_normalize_persian_text(self, persian_adapter):
        """Test Persian text normalization."""
        text = "  متن  فارسی  با  فاصله  زیاد  "
        result = persian_adapter._normalize_persian_text(text)
        assert result == "متن فارسی با فاصله زیاد"
    
    def test_extract_persian_price(self, persian_adapter):
        """Test Persian price extraction."""
        price_text = "۱۲۳,۴۵۶ تومان"
        result = persian_adapter._extract_persian_price(price_text)
        assert result == 123456.0
    
    def test_classify_persian_flight(self, persian_adapter):
        """Test Persian flight classification."""
        # Test charter flight
        charter_flight = {"charter_info": "پرواز چارتری"}
        assert persian_adapter._classify_persian_flight(charter_flight) == "charter"
        
        # Test domestic flight
        domestic_flight = {"is_domestic": True}
        assert persian_adapter._classify_persian_flight(domestic_flight) == "domestic"
        
        # Test by duration
        long_flight = {"duration_minutes": 600}  # 10 hours
        assert persian_adapter._classify_persian_flight(long_flight) == "international"


class TestEnhancedInternationalAdapter:
    """Test the enhanced international adapter functionality."""
    
    @pytest.fixture
    def mock_config(self):
        return {
            "base_url": "https://example.com",
            "currency": "EUR",
            "extraction_config": {
                "search_form": {},
                "results_parsing": {}
            },
            "rate_limiting": {"requests_per_second": 1},
            "error_handling": {"max_retries": 2},
            "monitoring": {"enabled": True}
        }
    
    @pytest.fixture
    def international_adapter(self, mock_config):
        return EnhancedInternationalAdapter(mock_config)
    
    def test_international_initialization(self, international_adapter):
        """Test international adapter specific initialization."""
        assert international_adapter.default_currency == "EUR"
        assert "USD" in international_adapter.currency_symbols
        assert "$" in international_adapter.currency_symbols["USD"]
    
    def test_detect_currency_from_text(self, international_adapter):
        """Test currency detection from text."""
        assert international_adapter._detect_currency_from_text("$299") == "USD"
        assert international_adapter._detect_currency_from_text("€199") == "EUR"
        assert international_adapter._detect_currency_from_text("£149") == "GBP"
    
    def test_normalize_international_time(self, international_adapter):
        """Test international time normalization."""
        result = international_adapter._normalize_international_time("2:30 PM")
        assert result == "14:30"
    
    def test_extract_international_duration(self, international_adapter):
        """Test international duration extraction."""
        assert international_adapter._extract_international_duration("2h 30m") == 150
        assert international_adapter._extract_international_duration("1h 45min") == 105


class TestCommonErrorHandler:
    """Test the common error handler functionality."""
    
    @pytest.fixture
    def error_handler(self):
        return CommonErrorHandler()
    
    def test_error_handler_decorator(self, error_handler):
        """Test the error handler decorator."""
        @error_handler
        def failing_function():
            raise ValueError("Test error")
        
        result = failing_function()
        assert result is None  # Should return None on error
    
    def test_safe_extract_decorator(self, error_handler):
        """Test the safe extract decorator."""
        @safe_extract
        def extract_function(element, selector):
            if selector == ".valid":
                return "extracted_value"
            else:
                raise AttributeError("Element not found")
        
        # Should return value for valid selector
        assert extract_function(None, ".valid") == "extracted_value"
        
        # Should return None for invalid selector
        assert extract_function(None, ".invalid") is None
    
    def test_retry_logic(self, error_handler):
        """Test retry logic with exponential backoff."""
        call_count = 0
        
        @error_handler
        def sometimes_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        result = sometimes_failing_function()
        assert result == "success"
        assert call_count == 3


class TestAdapterFactory:
    """Test the enhanced adapter factory."""
    
    @pytest.fixture
    def factory(self):
        return AdapterFactory()
    
    def test_create_persian_adapter(self, factory):
        """Test creating Persian adapters."""
        adapter = factory.create_adapter("mahan_air")
        assert isinstance(adapter, MahanAirAdapter)
        assert adapter.default_currency == "IRR"
    
    def test_create_international_adapter(self, factory):
        """Test creating international adapters."""
        adapter = factory.create_adapter("lufthansa")
        assert isinstance(adapter, LufthansaAdapter)
    
    def test_list_available_adapters(self, factory):
        """Test listing available adapters."""
        adapters = factory.list_available_adapters()
        assert "mahan_air" in adapters
        assert "lufthansa" in adapters
        assert len(adapters) > 10  # Should have many adapters
    
    def test_search_adapters(self, factory):
        """Test searching adapters."""
        iranian_adapters = factory.search_adapters(country="iran")
        assert all("iran" in adapter.lower() or "persian" in adapter.lower() 
                  for adapter in iranian_adapters)
    
    def test_get_adapter_metadata(self, factory):
        """Test getting adapter metadata."""
        metadata = factory.get_adapter_metadata("mahan_air")
        assert metadata["type"] == "persian"
        assert metadata["currency"] == "IRR"


class TestRefactoredPersianAdapters:
    """Test all refactored Persian adapters."""
    
    @pytest.fixture
    def mock_config(self):
        return {
            "extraction_config": {
                "search_form": {},
                "results_parsing": {}
            },
            "rate_limiting": {"requests_per_second": 1},
            "error_handling": {"max_retries": 2},
            "monitoring": {"enabled": True}
        }
    
    @pytest.mark.parametrize("adapter_class,expected_url", [
        (MahanAirAdapter, "https://www.mahan.aero"),
        (IranAirAdapter, "https://www.iranair.com"),
        (AlibabaAdapter, "https://www.alibaba.ir"),
        (FlytodayAdapter, "https://www.flytoday.ir"),
        (BookCharterAdapter, "https://bookcharter.ir"),
        (BookCharter724Adapter, "https://bookcharter724.ir"),
        (IranAirAsemanAdapter, "https://www.iranairlines.com"),
        (IranAirTourAdapter, "https://www.iranairtour.ir"),
        (Mz724Adapter, "https://www.mz724.ir"),
        (PartoCRSAdapter, "https://www.partocrs.com"),
        (SafarmarketAdapter, "https://www.safarmarket.com"),
        (IranAsemanAirAdapter, "https://www.iaa.ir"),
    ])
    def test_persian_adapter_initialization(self, adapter_class, expected_url, mock_config):
        """Test that all Persian adapters initialize correctly."""
        adapter = adapter_class(mock_config)
        assert isinstance(adapter, EnhancedPersianAdapter)
        assert adapter._get_base_url() == expected_url
        assert adapter._extract_currency(None, {}) == "IRR"
        assert adapter.default_currency == "IRR"
    
    def test_persian_adapters_required_fields(self, mock_config):
        """Test that all Persian adapters have required search fields."""
        adapters = [
            MahanAirAdapter(mock_config),
            IranAirAdapter(mock_config),
            AlibabaAdapter(mock_config),
            FlytodayAdapter(mock_config)
        ]
        
        for adapter in adapters:
            required_fields = adapter._get_required_search_fields()
            assert "origin" in required_fields
            assert "destination" in required_fields
            assert "departure_date" in required_fields


class TestRefactoredInternationalAdapters:
    """Test all refactored international adapters."""
    
    @pytest.fixture
    def mock_config(self):
        return {
            "extraction_config": {
                "search_form": {},
                "results_parsing": {}
            },
            "rate_limiting": {"requests_per_second": 1},
            "error_handling": {"max_retries": 2},
            "monitoring": {"enabled": True}
        }
    
    @pytest.mark.parametrize("adapter_class,expected_url,expected_currency", [
        (LufthansaAdapter, "https://www.lufthansa.com", "EUR"),
        (AirFranceAdapter, "https://www.airfrance.com", "EUR"),
        (BritishAirwaysAdapter, "https://www.britishairways.com", "GBP"),
        (EmiratesAdapter, "https://www.emirates.com", "AED"),
        (EtihadAirwaysAdapter, "https://www.etihad.com", "AED"),
        (KLMAdapter, "https://www.klm.com", "EUR"),
        (PegasusAdapter, "https://www.flypgs.com", "TRY"),
        (QatarAirwaysAdapter, "https://www.qatarairways.com", "QAR"),
        (TurkishAirlinesAdapter, "https://www.turkishairlines.com", "TRY"),
    ])
    def test_international_adapter_initialization(self, adapter_class, expected_url, 
                                                expected_currency, mock_config):
        """Test that all international adapters initialize correctly."""
        adapter = adapter_class(mock_config)
        assert isinstance(adapter, EnhancedInternationalAdapter)
        assert adapter._get_base_url() == expected_url
        assert adapter._extract_currency(None, {}) == expected_currency


class TestIntegrationScenarios:
    """Test integration scenarios across the system."""
    
    @pytest.fixture
    def factory(self):
        return AdapterFactory()
    
    @pytest.mark.asyncio
    async def test_end_to_end_persian_flight_search(self, factory):
        """Test end-to-end Persian flight search."""
        adapter = factory.create_adapter("mahan_air")
        
        # Mock the necessary methods
        adapter._navigate_to_search_page = AsyncMock()
        adapter._fill_search_form = AsyncMock()
        adapter._extract_flight_results = AsyncMock(return_value=[
            {
                "airline": "ماهان",
                "flight_number": "W5 1001",
                "price": 1500000,
                "currency": "IRR"
            }
        ])
        
        search_params = {
            "origin": "تهران",
            "destination": "مشهد", 
            "departure_date": "1404-03-15",
            "passengers": 1
        }
        
        results = await adapter.crawl(search_params)
        
        assert len(results) == 1
        assert results[0]["airline"] == "ماهان"
        assert results[0]["currency"] == "IRR"
    
    @pytest.mark.asyncio
    async def test_end_to_end_international_flight_search(self, factory):
        """Test end-to-end international flight search."""
        adapter = factory.create_adapter("lufthansa")
        
        # Mock the necessary methods
        adapter._navigate_to_search_page = AsyncMock()
        adapter._fill_search_form = AsyncMock()
        adapter._extract_flight_results = AsyncMock(return_value=[
            {
                "airline": "Lufthansa",
                "flight_number": "LH 441",
                "price": 599.99,
                "currency": "EUR"
            }
        ])
        
        search_params = {
            "origin": "FRA",
            "destination": "JFK",
            "departure_date": "2024-06-15",
            "passengers": 1
        }
        
        results = await adapter.crawl(search_params)
        
        assert len(results) == 1
        assert results[0]["airline"] == "Lufthansa"
        assert results[0]["currency"] == "EUR"
    
    def test_error_handling_across_adapters(self, factory):
        """Test that error handling works consistently across adapters."""
        # Test Persian adapter error handling
        persian_adapter = factory.create_adapter("mahan_air")
        assert hasattr(persian_adapter, 'error_handler')
        assert hasattr(persian_adapter, 'common_error_handler')
        
        # Test international adapter error handling
        intl_adapter = factory.create_adapter("lufthansa")
        assert hasattr(intl_adapter, 'error_handler')
        assert hasattr(intl_adapter, 'common_error_handler')
    
    def test_performance_monitoring_integration(self, factory):
        """Test that performance monitoring is integrated across adapters."""
        adapters = [
            factory.create_adapter("mahan_air"),
            factory.create_adapter("lufthansa"),
            factory.create_adapter("alibaba")
        ]
        
        for adapter in adapters:
            assert hasattr(adapter, 'monitoring')
            assert adapter.monitoring is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"]) 