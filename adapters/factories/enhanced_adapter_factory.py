"""
Enhanced Adapter Factory implementing multiple design patterns.

This factory combines:
- Abstract Factory Pattern: Different factories for different adapter types
- Factory Method Pattern: Specific creation methods for each type
- Strategy Pattern: Different creation strategies
- Builder Pattern: Complex configuration building
- Registry Pattern: Centralized adapter registration
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional, List, Union, Protocol
from dataclasses import dataclass, field
from enum import Enum
import importlib
import logging
import json
import os
from pathlib import Path

from adapters.base_adapters import (
    EnhancedBaseCrawler,
    EnhancedInternationalAdapter,
    EnhancedPersianAdapter,
    ConfigurationHelper,
    ErrorReportingHelper,
)

logger = logging.getLogger(__name__)


class AdapterType(Enum):
    """Enumeration of adapter types."""

    PERSIAN = "persian"
    INTERNATIONAL = "international"
    AGGREGATOR = "aggregator"


@dataclass
class AdapterMetadata:
    """Metadata for adapter registration."""

    name: str
    adapter_type: AdapterType
    base_url: str
    currency: str
    airline_name: str
    description: str
    features: List[str] = field(default_factory=list)
    supported_routes: List[str] = field(default_factory=list)
    config_template: Optional[Dict[str, Any]] = None
    is_active: bool = True


class AdapterCreationStrategy(Protocol):
    """Protocol for adapter creation strategies."""

    def create_adapter(
        self, name: str, config: Dict[str, Any], metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create an adapter instance."""
        ...


class ConfigurationBuilder:
    """Builder for adapter configurations following Builder Pattern."""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._metadata: Optional[AdapterMetadata] = None

    def with_base_config(self, base_config: Dict[str, Any]) -> "ConfigurationBuilder":
        """Set base configuration."""
        self._config.update(base_config)
        return self

    def with_rate_limiting(
        self,
        requests_per_second: int = 2,
        burst_limit: int = 5,
        cooldown_period: int = 60,
    ) -> "ConfigurationBuilder":
        """Configure rate limiting."""
        self._config["rate_limiting"] = {
            "requests_per_second": requests_per_second,
            "burst_limit": burst_limit,
            "cooldown_period": cooldown_period,
        }
        return self

    def with_error_handling(
        self,
        max_retries: int = 3,
        retry_delay: int = 5,
        circuit_breaker: Optional[Dict[str, Any]] = None,
    ) -> "ConfigurationBuilder":
        """Configure error handling."""
        self._config["error_handling"] = {
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "circuit_breaker": circuit_breaker or {},
        }
        return self

    def with_extraction_config(
        self, extraction_config: Dict[str, Any]
    ) -> "ConfigurationBuilder":
        """Configure data extraction."""
        self._config["extraction_config"] = extraction_config
        return self

    def with_monitoring(
        self, monitoring_config: Dict[str, Any]
    ) -> "ConfigurationBuilder":
        """Configure monitoring."""
        self._config["monitoring"] = monitoring_config
        return self

    def with_metadata(self, metadata: AdapterMetadata) -> "ConfigurationBuilder":
        """Set adapter metadata."""
        self._metadata = metadata
        return self

    def with_custom_config(self, key: str, value: Any) -> "ConfigurationBuilder":
        """Add custom configuration."""
        self._config[key] = value
        return self

    def build(self) -> Dict[str, Any]:
        """Build the final configuration."""
        if self._metadata:
            self._config.update(
                {
                    "base_url": self._metadata.base_url,
                    "currency": self._metadata.currency,
                    "adapter_type": self._metadata.adapter_type.value,
                    "airline_name": self._metadata.airline_name,
                }
            )

        # Set defaults if not provided
        if "rate_limiting" not in self._config:
            self.with_rate_limiting()

        if "error_handling" not in self._config:
            self.with_error_handling()

        return self._config.copy()


class DirectCreationStrategy:
    """Strategy for creating adapters directly from classes."""

    def create_adapter(
        self, name: str, config: Dict[str, Any], metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create adapter using direct class instantiation."""
        try:
            # Determine base class based on adapter type
            if metadata.adapter_type == AdapterType.PERSIAN:
                base_class = EnhancedPersianAdapter
            elif metadata.adapter_type == AdapterType.INTERNATIONAL:
                base_class = EnhancedInternationalAdapter
            else:
                base_class = EnhancedBaseCrawler

            # Create dynamic adapter class
            adapter_class = self._create_dynamic_adapter_class(
                name, base_class, metadata, config
            )

            return adapter_class(config)

        except Exception as e:
            logger.error(f"Error creating adapter {name}: {e}")
            raise

    def _create_dynamic_adapter_class(
        self,
        name: str,
        base_class: Type[EnhancedBaseCrawler],
        metadata: AdapterMetadata,
        config: Dict[str, Any],
    ) -> Type[EnhancedBaseCrawler]:
        """Create a dynamic adapter class."""

        class DynamicAdapter(base_class):
            def _get_base_url(self) -> str:
                return metadata.base_url

            def get_adapter_name(self) -> str:
                return metadata.name

            def get_adapter_specific_config(self) -> Dict[str, Any]:
                return config

        DynamicAdapter.__name__ = f"Dynamic{name.title()}Adapter"
        return DynamicAdapter


class ModuleCreationStrategy:
    """Strategy for creating adapters from modules."""

    def create_adapter(
        self, name: str, config: Dict[str, Any], metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create adapter by importing from module."""
        try:
            # Try to import the specific adapter
            module_path = self._get_module_path(name, metadata.adapter_type)
            module = importlib.import_module(module_path)

            # Get adapter class
            class_name = self._get_class_name(name)
            adapter_class = getattr(module, class_name)

            return adapter_class(config)

        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not import adapter {name}: {e}")
            # Fallback to direct creation
            fallback_strategy = DirectCreationStrategy()
            return fallback_strategy.create_adapter(name, config, metadata)

    def _get_module_path(self, name: str, adapter_type: AdapterType) -> str:
        """Get module path for adapter."""
        if adapter_type == AdapterType.PERSIAN:
            return f"adapters.site_adapters.iranian_airlines.{name}_adapter"
        elif adapter_type == AdapterType.INTERNATIONAL:
            return f"adapters.site_adapters.international_airlines.{name}_adapter"
        else:
            return f"adapters.site_adapters.aggregators.{name}_adapter"

    def _get_class_name(self, name: str) -> str:
        """Generate class name from adapter name."""
        words = name.replace("_", " ").replace("-", " ").split()
        return "".join(word.capitalize() for word in words) + "Adapter"


class AbstractAdapterFactory(ABC):
    """Abstract factory for creating adapters."""

    def __init__(self, creation_strategy: AdapterCreationStrategy):
        self.creation_strategy = creation_strategy
        self.config_builder = ConfigurationBuilder()

    @abstractmethod
    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """Create an adapter instance."""
        pass

    @abstractmethod
    def get_supported_adapters(self) -> List[str]:
        """Get list of supported adapter names."""
        pass

    def build_config(
        self, metadata: AdapterMetadata, custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build configuration using the builder pattern."""
        builder = self.config_builder.with_metadata(metadata).with_base_config(
            metadata.config_template or {}
        )

        if custom_config:
            for key, value in custom_config.items():
                builder = builder.with_custom_config(key, value)

        return builder.build()


class PersianAdapterFactory(AbstractAdapterFactory):
    """Factory for creating Persian airline adapters."""

    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._persian_adapters = self._initialize_persian_adapters()

    def _initialize_persian_adapters(self) -> Dict[str, AdapterMetadata]:
        """Initialize Persian adapter metadata."""
        return {
            "iran_air": AdapterMetadata(
                name="iran_air",
                adapter_type=AdapterType.PERSIAN,
                base_url="https://www.iranair.com",
                currency="IRR",
                airline_name="Iran Air",
                description="Iranian flag carrier airline",
                features=["domestic_routes", "international_routes", "flag_carrier"],
            ),
            "mahan_air": AdapterMetadata(
                name="mahan_air",
                adapter_type=AdapterType.PERSIAN,
                base_url="https://www.mahan.aero",
                currency="IRR",
                airline_name="Mahan Air",
                description="Iranian private airline",
                features=["domestic_routes", "charter_flights", "loyalty_program"],
            ),
            "aseman_airlines": AdapterMetadata(
                name="aseman_airlines",
                adapter_type=AdapterType.PERSIAN,
                base_url="https://www.iaa.ir",
                currency="IRR",
                airline_name="Iran Aseman Airlines",
                description="Iranian airline",
                features=["domestic_routes", "regional_routes"],
            ),
            "caspian_airlines": AdapterMetadata(
                name="caspian_airlines",
                adapter_type=AdapterType.PERSIAN,
                base_url="https://www.caspian.aero",
                currency="IRR",
                airline_name="Caspian Airlines",
                description="Iranian private airline",
                features=["domestic_routes", "charter_flights"],
            ),
        }

    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """Create a Persian adapter."""
        if name not in self._persian_adapters:
            raise ValueError(f"Persian adapter '{name}' not found")

        metadata = self._persian_adapters[name]
        final_config = self.build_config(metadata, config)

        return self.creation_strategy.create_adapter(name, final_config, metadata)

    def get_supported_adapters(self) -> List[str]:
        """Get list of supported Persian adapters."""
        return list(self._persian_adapters.keys())


class InternationalAdapterFactory(AbstractAdapterFactory):
    """Factory for creating international airline adapters."""

    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._international_adapters = self._initialize_international_adapters()

    def _initialize_international_adapters(self) -> Dict[str, AdapterMetadata]:
        """Initialize international adapter metadata."""
        return {
            "lufthansa": AdapterMetadata(
                name="lufthansa",
                adapter_type=AdapterType.INTERNATIONAL,
                base_url="https://www.lufthansa.com",
                currency="EUR",
                airline_name="Lufthansa",
                description="German flag carrier airline",
                features=["star_alliance", "premium_service", "global_network"],
            ),
            "emirates": AdapterMetadata(
                name="emirates",
                adapter_type=AdapterType.INTERNATIONAL,
                base_url="https://www.emirates.com",
                currency="AED",
                airline_name="Emirates",
                description="Dubai-based international airline",
                features=["luxury_service", "global_network", "premium_fleet"],
            ),
            "turkish_airlines": AdapterMetadata(
                name="turkish_airlines",
                adapter_type=AdapterType.INTERNATIONAL,
                base_url="https://www.turkishairlines.com",
                currency="TRY",
                airline_name="Turkish Airlines",
                description="Turkish flag carrier airline",
                features=["star_alliance", "extensive_network", "istanbul_hub"],
            ),
        }

    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """Create an international adapter."""
        if name not in self._international_adapters:
            raise ValueError(f"International adapter '{name}' not found")

        metadata = self._international_adapters[name]
        final_config = self.build_config(metadata, config)

        return self.creation_strategy.create_adapter(name, final_config, metadata)

    def get_supported_adapters(self) -> List[str]:
        """Get list of supported international adapters."""
        return list(self._international_adapters.keys())


class AggregatorAdapterFactory(AbstractAdapterFactory):
    """Factory for creating aggregator adapters."""

    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._aggregator_adapters = self._initialize_aggregator_adapters()

    def _initialize_aggregator_adapters(self) -> Dict[str, AdapterMetadata]:
        """Initialize aggregator adapter metadata."""
        return {
            "alibaba": AdapterMetadata(
                name="alibaba",
                adapter_type=AdapterType.AGGREGATOR,
                base_url="https://www.alibaba.ir",
                currency="IRR",
                airline_name="Alibaba.ir",
                description="Iranian flight booking aggregator",
                features=["aggregator", "domestic_flights", "international_flights"],
            ),
            "flightio": AdapterMetadata(
                name="flightio",
                adapter_type=AdapterType.AGGREGATOR,
                base_url="https://flightio.com",
                currency="IRR",
                airline_name="Flightio",
                description="Flight booking platform",
                features=["aggregator", "multiple_airlines", "comparison"],
            ),
            "flytoday": AdapterMetadata(
                name="flytoday",
                adapter_type=AdapterType.AGGREGATOR,
                base_url="https://www.flytoday.ir",
                currency="IRR",
                airline_name="FlyToday",
                description="Iranian flight booking platform",
                features=["aggregator", "domestic_flights", "user_friendly"],
            ),
        }

    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """Create an aggregator adapter."""
        if name not in self._aggregator_adapters:
            raise ValueError(f"Aggregator adapter '{name}' not found")

        metadata = self._aggregator_adapters[name]
        final_config = self.build_config(metadata, config)

        return self.creation_strategy.create_adapter(name, final_config, metadata)

    def get_supported_adapters(self) -> List[str]:
        """Get list of supported aggregator adapters."""
        return list(self._aggregator_adapters.keys())


class EnhancedAdapterFactory:
    """
    Main factory that coordinates all adapter creation.

    This implements the Abstract Factory pattern by delegating to
    specific factories based on adapter type.
    """

    def __init__(self, creation_strategy: Optional[AdapterCreationStrategy] = None):
        self.creation_strategy = creation_strategy or ModuleCreationStrategy()

        # Initialize specific factories
        self.persian_factory = PersianAdapterFactory(self.creation_strategy)
        self.international_factory = InternationalAdapterFactory(self.creation_strategy)
        self.aggregator_factory = AggregatorAdapterFactory(self.creation_strategy)

        # Factory registry
        self._factories = {
            AdapterType.PERSIAN: self.persian_factory,
            AdapterType.INTERNATIONAL: self.international_factory,
            AdapterType.AGGREGATOR: self.aggregator_factory,
        }

    def create_adapter(
        self,
        name: str,
        adapter_type: Optional[AdapterType] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EnhancedBaseCrawler:
        """
        Create an adapter using the appropriate factory.

        Args:
            name: Adapter name
            adapter_type: Type of adapter (if not provided, will be auto-detected)
            config: Custom configuration

        Returns:
            Adapter instance
        """
        # Auto-detect adapter type if not provided
        if adapter_type is None:
            adapter_type = self._detect_adapter_type(name)

        factory = self._factories.get(adapter_type)
        if not factory:
            raise ValueError(f"No factory found for adapter type: {adapter_type}")

        return factory.create_adapter(name, config)

    def _detect_adapter_type(self, name: str) -> AdapterType:
        """Auto-detect adapter type based on name."""
        # Check each factory for the adapter
        for adapter_type, factory in self._factories.items():
            if name in factory.get_supported_adapters():
                return adapter_type

        # Default to Persian if not found (most common)
        logger.warning(
            f"Could not detect type for adapter '{name}', defaulting to Persian"
        )
        return AdapterType.PERSIAN

    def list_all_adapters(self) -> Dict[AdapterType, List[str]]:
        """List all available adapters by type."""
        return {
            adapter_type: factory.get_supported_adapters()
            for adapter_type, factory in self._factories.items()
        }

    def get_adapter_info(self, name: str) -> Optional[AdapterMetadata]:
        """Get metadata for a specific adapter."""
        for factory in self._factories.values():
            if name in factory.get_supported_adapters():
                if hasattr(
                    factory,
                    f'_{factory.__class__.__name__.lower().replace("adapterfactory", "")}_adapters',
                ):
                    adapters_dict = getattr(
                        factory,
                        f'_{factory.__class__.__name__.lower().replace("adapterfactory", "")}_adapters',
                    )
                    return adapters_dict.get(name)
        return None

    def register_custom_adapter(
        self,
        metadata: AdapterMetadata,
        config_template: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a custom adapter."""
        factory = self._factories.get(metadata.adapter_type)
        if factory:
            adapters_attr = f"_{metadata.adapter_type.value}_adapters"
            if hasattr(factory, adapters_attr):
                adapters_dict = getattr(factory, adapters_attr)
                if config_template:
                    metadata.config_template = config_template
                adapters_dict[metadata.name] = metadata


# Singleton instance
_factory_instance: Optional[EnhancedAdapterFactory] = None


def get_enhanced_factory() -> EnhancedAdapterFactory:
    """Get singleton instance of the enhanced factory."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = EnhancedAdapterFactory()
    return _factory_instance


# Convenience functions
def create_adapter(
    name: str,
    adapter_type: Optional[AdapterType] = None,
    config: Optional[Dict[str, Any]] = None,
) -> EnhancedBaseCrawler:
    """Create an adapter using the enhanced factory."""
    factory = get_enhanced_factory()
    return factory.create_adapter(name, adapter_type, config)


def list_adapters() -> Dict[AdapterType, List[str]]:
    """List all available adapters."""
    factory = get_enhanced_factory()
    return factory.list_all_adapters()


def get_adapter_metadata(name: str) -> Optional[AdapterMetadata]:
    """Get metadata for an adapter."""
    factory = get_enhanced_factory()
    return factory.get_adapter_info(name)
