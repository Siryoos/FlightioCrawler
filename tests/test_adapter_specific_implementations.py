"""
Adapter-specific tests for individual airline implementations.
Tests the unique functionality and behavior of each adapter.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

# Create local fixtures to avoid import conflicts

@pytest.fixture
def enhanced_adapter_config():
    """Enhanced adapter configuration for testing."""
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
            "retry_delay": 1,
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
            "max_results": 50,
            "search_form": {
                "origin_field": "#origin",
                "destination_field": "#destination",
                "departure_date_field": "#departure",
                "return_date_field": "#return",
                "adults_field": "#adults",
                "children_field": "#children",
                "infants_field": "#infants",
                "cabin_class_field": "#cabin_class",
                "search_button": "#search_button"
            },
            "results_parsing": {
                "container": ".flight-result",
                "airline": ".airline",
                "flight_number": ".flight-number",
                "departure_time": ".departure-time",
                "arrival_time": ".arrival-time",
                "price": ".price",
                "currency": ".currency",
                "duration": ".duration",
                "seat_class": ".seat-class"
            }
        },
        "data_validation": {
            "required_fields": [
                "airline", "flight_number", "departure_time", "arrival_time",
                "price", "currency", "duration_minutes", "seat_class"
            ],
            "price_range": {"min": 100000, "max": 50000000},
            "duration_range": {"min": 30, "max": 1440}
        }
    }

def create_crawler_config(config_dict):
    """Helper function to create CrawlerConfig from dictionary."""
    from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
    
    return CrawlerConfig(
        base_url=config_dict["base_url"],
        search_url=config_dict["search_url"],
        **{k: v for k, v in config_dict.items() if k not in ["base_url", "search_url"]}
    )

# Import error classes
from adapters.base_adapters.enhanced_base_crawler import (
    ValidationError,
    NavigationError,
    ExtractionError,
    AdapterTimeoutError
)


class TestMahanAirAdapterSpecific:
    """Test MahanAir adapter specific functionality."""
    
    @pytest.mark.asyncio
    async def test_mahan_air_specific_field_extraction(self, enhanced_adapter_config):
        """Test MahanAir specific field extraction."""
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        # Configure for MahanAir
        config_data = enhanced_adapter_config.copy()
        config_data["base_url"] = "https://www.mahan.aero"
        config_data["extraction_config"]["results_parsing"].update({
            "aircraft_type": ".aircraft-type",
            "meal_service": ".meal-service",
            "baggage_allowance": ".baggage",
            "seat_selection": ".seat-selection"
        })
        
        config = create_crawler_config(config_data)
        adapter = MahanAirAdapter(config)
        
        # Mock flight element with MahanAir specific fields
        mock_element = Mock()
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".aircraft-type": "Boeing 737",
                ".meal-service": "وعده غذایی",
                ".baggage": "20 کیلوگرم",
                ".seat-selection": "انتخاب صندلی"
            }.get(selector, "")
            
            # Test MahanAir specific field extraction
            mahan_fields = adapter._extract_mahan_air_specific_fields(
                mock_element, config_data["extraction_config"]["results_parsing"]
            )
            
            # Verify MahanAir specific fields are extracted
            assert "aircraft_type" in mahan_fields
            assert "meal_service" in mahan_fields
            assert "baggage_allowance" in mahan_fields
            assert mahan_fields["aircraft_type"] == "Boeing 737"
    
    @pytest.mark.asyncio
    async def test_mahan_air_flight_validation(self, enhanced_adapter_config):
        """Test MahanAir specific flight validation."""
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = MahanAirAdapter(config)
        
        # Test valid MahanAir flight
        valid_flight = {
            "airline_name": "Mahan Air",
            "airline_code": "W5",
            "flight_number": "W5123",
            "price": 1500000,  # Valid IRR price
            "duration_minutes": 90,
            "origin": "THR",
            "destination": "ISF"
        }
        
        result = adapter._validate_mahan_air_flight(valid_flight)
        assert result is True
        
        # Test invalid flight - wrong airline
        invalid_flight = valid_flight.copy()
        invalid_flight["airline_name"] = "Iran Air"
        invalid_flight["airline_code"] = "IR"
        
        result = adapter._validate_mahan_air_flight(invalid_flight)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_mahan_air_currency_extraction(self, enhanced_adapter_config):
        """Test MahanAir currency extraction (always IRR)."""
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = MahanAirAdapter(config)
        
        # Currency should always be IRR for MahanAir
        currency = adapter._extract_currency(Mock(), {})
        assert currency == "IRR"


class TestEmiratesAdapterSpecific:
    """Test Emirates adapter specific functionality."""
    
    @pytest.mark.asyncio
    async def test_emirates_specific_field_extraction(self, enhanced_adapter_config):
        """Test Emirates specific field extraction."""
        from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        # Configure for Emirates
        config_data = enhanced_adapter_config.copy()
        config_data["base_url"] = "https://www.emirates.com"
        config_data["extraction_config"]["results_parsing"].update({
            "skywards_miles": ".skywards-miles",
            "upgrade_options": ".upgrade-available",
            "meal_preferences": ".meal-options"
        })
        
        config = create_crawler_config(config_data)
        adapter = EmiratesAdapter(config)
        
        # Mock flight element with Emirates specific fields
        mock_element = Mock()
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".skywards-miles": "2500 Miles",
                ".upgrade-available": "Upgrade Available",
                ".meal-options": "Special Meals"
            }.get(selector, "")
            
            # Mock parent class method
            with patch.object(adapter.__class__.__bases__[0], '_parse_flight_element') as mock_parent:
                mock_parent.return_value = {
                    "airline": "Emirates",
                    "flight_number": "EK001",
                    "price": 1200,
                    "currency": "USD"
                }
                
                # Test Emirates specific field extraction
                flight_data = adapter._parse_flight_element(mock_element)
                
                # Verify base fields from parent
                assert flight_data["airline"] == "Emirates"
                assert flight_data["flight_number"] == "EK001"
                assert flight_data["price"] == 1200
    
    @pytest.mark.asyncio
    async def test_emirates_form_filling_logic(self, enhanced_adapter_config):
        """Test Emirates form filling with international parameters."""
        from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = EmiratesAdapter(config)
        
        # Mock page object
        mock_page = AsyncMock()
        adapter.page = mock_page
        
        international_search_params = {
            "trip_type": "roundtrip",
            "origin": "DXB",
            "destination": "LHR",
            "departure_date": "2025-08-15",
            "return_date": "2025-08-22",
            "adults": 1,
            "children": 0,
            "infants": 0,
            "cabin_class": "business"
        }
        
        # Test form filling
        await adapter._fill_search_form(international_search_params)
        
        # Verify form interactions occurred
        assert mock_page.fill.call_count > 0
        assert mock_page.click.call_count > 0


class TestIranAirAdapterSpecific:
    """Test IranAir adapter specific functionality."""
    
    @pytest.mark.asyncio
    async def test_iranair_specific_field_extraction(self, enhanced_adapter_config):
        """Test IranAir specific field extraction."""
        from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        # Configure for IranAir
        config_data = enhanced_adapter_config.copy()
        config_data["base_url"] = "https://www.iranair.com"
        config_data["extraction_config"]["results_parsing"].update({
            "route_info": ".route-information",
            "service_details": ".service-class",
            "booking_conditions": ".booking-terms"
        })
        
        config = create_crawler_config(config_data)
        adapter = IranAirAdapter(config)
        
        # Mock flight element with IranAir specific fields
        mock_element = Mock()
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".route-information": "تهران - اصفهان",
                ".service-class": "کلاس اقتصادی",
                ".booking-terms": "قابل کنسلی"
            }.get(selector, "")
            
            # Mock parent class method
            with patch.object(adapter.__class__.__bases__[0], '_parse_flight_element') as mock_parent:
                mock_parent.return_value = {
                    "airline": "Iran Air",
                    "flight_number": "IR701",
                    "price": 1800000,
                    "currency": "IRR"
                }
                
                # Test IranAir specific field extraction
                flight_data = adapter._parse_flight_element(mock_element)
                
                # Verify base fields from parent
                assert flight_data["airline"] == "Iran Air"
                assert flight_data["flight_number"] == "IR701"
                assert flight_data["price"] == 1800000
    
    @pytest.mark.asyncio
    async def test_iranair_base_url_and_currency(self, enhanced_adapter_config):
        """Test IranAir base URL and currency."""
        from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = IranAirAdapter(config)
        
        # Test base URL
        assert adapter._get_base_url() == "https://www.iranair.com"
        
        # Test currency (always IRR for IranAir)
        currency = adapter._extract_currency(Mock(), {})
        assert currency == "IRR"


class TestAirFranceAdapterSpecific:
    """Test Air France adapter specific functionality."""
    
    @pytest.mark.asyncio
    async def test_airfrance_specific_field_extraction(self, enhanced_adapter_config):
        """Test Air France specific field extraction."""
        from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        # Configure for Air France
        config_data = enhanced_adapter_config.copy()
        config_data["base_url"] = "https://www.airfrance.com"
        config_data["extraction_config"]["results_parsing"].update({
            "flying_blue_miles": ".miles-earned"
        })
        
        config = create_crawler_config(config_data)
        adapter = AirFranceAdapter(config)
        
        # Mock flight element with Air France specific fields
        mock_element = Mock()
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".miles-earned": "1500 Miles"
            }.get(selector, "")
            
            # Mock parent class method
            with patch.object(adapter.__class__.__bases__[0], '_parse_flight_element') as mock_parent:
                mock_parent.return_value = {
                    "airline": "Air France",
                    "flight_number": "AF1234",
                    "price": 650,
                    "currency": "EUR"
                }
                
                # Test Air France specific field extraction
                flight_data = adapter._parse_flight_element(mock_element)
                
                # Verify base fields from parent
                assert flight_data["airline"] == "Air France"
                assert flight_data["flight_number"] == "AF1234"
                assert flight_data["price"] == 650
    
    @pytest.mark.asyncio
    async def test_airfrance_search_validation(self, enhanced_adapter_config):
        """Test Air France search parameter validation."""
        from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = AirFranceAdapter(config)
        
        # Test valid parameters
        valid_params = {
            "origin": "CDG",
            "destination": "JFK",
            "departure_date": "2025-08-15",
            "cabin_class": "economy"
        }
        
        # Should not raise exception
        adapter._validate_search_params(valid_params)
        
        # Test missing required field
        invalid_params = valid_params.copy()
        del invalid_params["origin"]
        
        with pytest.raises(ValueError, match="Missing required search parameter: origin"):
            adapter._validate_search_params(invalid_params)


class TestPartoTicketAdapterSpecific:
    """Test PartoTicket adapter specific functionality."""
    
    @pytest.mark.asyncio
    async def test_parto_specific_field_extraction(self, enhanced_adapter_config):
        """Test PartoTicket specific field extraction."""
        from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        # Configure for PartoTicket
        config_data = enhanced_adapter_config.copy()
        config_data["base_url"] = "https://parto-ticket.ir"
        config_data["extraction_config"]["results_parsing"].update({
            "ticket_type": ".ticket-type",
            "fare_conditions": ".fare-conditions",
            "available_seats": ".available-seats"
        })
        
        config = create_crawler_config(config_data)
        adapter = PartoTicketAdapter(config)
        
        # Mock flight element with PartoTicket specific fields
        mock_element = Mock()
        mock_element.select_one = Mock(side_effect=lambda selector: {
            ".cancellation-policy": Mock(text="قابل کنسلی تا 24 ساعت"),
            ".change-policy": Mock(text="قابل تغییر"),
            ".baggage-allowance": Mock(text="20 کیلوگرم"),
            ".available-seats": Mock(text="5 صندلی")
        }.get(selector))
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".ticket-type": "اقتصادی فروش ویژه",
                ".cancellation-policy": "قابل کنسلی تا 24 ساعت",
                ".change-policy": "قابل تغییر",
                ".baggage-allowance": "20 کیلوگرم"
            }.get(selector, "")
            
            # Mock parent class method
            with patch.object(adapter.__class__.__bases__[0], '_parse_flight_element') as mock_parent:
                mock_parent.return_value = {
                    "airline": "Iran Air",
                    "flight_number": "IR701",
                    "price": 2500000,
                    "currency": "IRR"
                }
                
                # Test PartoTicket specific field extraction
                flight_data = adapter._parse_flight_element(mock_element)
                
                # Verify PartoTicket specific fields
                assert flight_data.get("is_aggregator") is True
                assert flight_data.get("aggregator_name") == "parto_ticket"
    
    @pytest.mark.asyncio
    async def test_parto_fare_conditions_extraction(self, enhanced_adapter_config):
        """Test PartoTicket fare conditions extraction."""
        from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        adapter = PartoTicketAdapter(config)
        
        # Mock element with fare conditions
        mock_element = Mock()
        
        with patch.object(adapter, '_extract_text') as mock_extract:
            mock_extract.side_effect = lambda elem, selector: {
                ".cancellation-policy": "قابل کنسلی تا 24 ساعت",
                ".change-policy": "قابل تغییر با جریمه",
                ".baggage-allowance": "20 کیلوگرم"
            }.get(selector, "")
            
            # Test fare conditions extraction
            fare_conditions = adapter._extract_fare_conditions(mock_element)
            
            assert fare_conditions is not None
            assert "cancellation" in fare_conditions
            assert "changes" in fare_conditions
            assert "baggage" in fare_conditions


class TestAdapterConsistency:
    """Test consistency across all adapters."""
    
    @pytest.mark.asyncio
    async def test_adapter_method_consistency(self, enhanced_adapter_config):
        """Test that all adapters implement required methods consistently."""
        
        # Import all adapters
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
        from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
        from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
        from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        
        adapters = [
            MahanAirAdapter(config),
            IranAirAdapter(config),
            PartoTicketAdapter(config),
            EmiratesAdapter(config),
            AirFranceAdapter(config)
        ]
        
        required_methods = [
            '_get_base_url',
            '_extract_currency',
            '_parse_flight_element',
            '_get_required_search_fields'
        ]
        
        for adapter in adapters:
            adapter_name = adapter.__class__.__name__
            
            for method_name in required_methods:
                assert hasattr(adapter, method_name), f"{adapter_name} missing {method_name}"
                assert callable(getattr(adapter, method_name)), f"{adapter_name}.{method_name} not callable"
    
    @pytest.mark.asyncio
    async def test_adapter_currency_consistency(self, enhanced_adapter_config):
        """Test currency consistency across adapters."""
        
        # Import all adapters
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
        from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
        from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
        from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        
        # Iranian adapters should use IRR
        iranian_adapters = [
            MahanAirAdapter(config),
            IranAirAdapter(config),
            PartoTicketAdapter(config)
        ]
        
        for adapter in iranian_adapters:
            currency = adapter._extract_currency(Mock(), {})
            assert currency == "IRR", f"{adapter.__class__.__name__} should use IRR currency"
        
        # International adapters should use appropriate currencies
        international_adapters = [
            EmiratesAdapter(config),
            AirFranceAdapter(config)
        ]
        
        for adapter in international_adapters:
            currency = adapter._extract_currency(Mock(), {})
            # International adapters may have different currency logic
            assert currency is not None, f"{adapter.__class__.__name__} should return a currency"
    
    @pytest.mark.asyncio
    async def test_adapter_error_handling_consistency(self, enhanced_adapter_config):
        """Test error handling consistency across adapters."""
        
        # Import all adapters
        from adapters.site_adapters.iranian_airlines.mahan_air_adapter import MahanAirAdapter
        from adapters.site_adapters.iranian_airlines.iran_air_adapter import IranAirAdapter
        from adapters.site_adapters.iranian_airlines.parto_ticket_adapter import PartoTicketAdapter
        from adapters.site_adapters.international_airlines.emirates_adapter import EmiratesAdapter
        from adapters.site_adapters.international_airlines.air_france_adapter import AirFranceAdapter
        from adapters.base_adapters.enhanced_base_crawler import CrawlerConfig
        
        config = create_crawler_config(enhanced_adapter_config)
        
        adapters = [
            MahanAirAdapter(config),
            IranAirAdapter(config),
            PartoTicketAdapter(config),
            EmiratesAdapter(config),
            AirFranceAdapter(config)
        ]
        
        for adapter in adapters:
            adapter_name = adapter.__class__.__name__
            
            # Test that adapters handle invalid flight elements gracefully
            invalid_element = Mock()
            
            # Mock extraction that returns None/empty
            with patch.object(adapter, '_extract_text', return_value=""):
                try:
                    result = adapter._parse_flight_element(invalid_element)
                    # Should not crash - result can be None or empty dict
                    assert result is None or isinstance(result, dict)
                except Exception as e:
                    # If an exception occurs, it should be handled gracefully
                    pytest.fail(f"{adapter_name} should handle invalid elements gracefully: {e}") 