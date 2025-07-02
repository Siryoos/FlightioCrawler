"""
Enhanced Adapter Factory for creating flight crawling adapters.

This factory provides a clean interface for creating adapters with
automatic configuration management and error handling.
"""

from typing import Dict, Any, Type, Optional, List, Union
from abc import ABC
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


class AdapterRegistry:
    """
    Enhanced registry for adapter classes with configuration management.
    """

    def __init__(self):
        self._adapters: Dict[str, Type[EnhancedBaseCrawler]] = {}
        self._adapter_configs: Dict[str, Dict[str, Any]] = {}
        self._adapter_metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        adapter_class: Type[EnhancedBaseCrawler],
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register an adapter class with configuration and metadata.

        Args:
            name: Adapter name
            adapter_class: Adapter class
            config: Default configuration
            metadata: Adapter metadata (description, features, etc.)
        """
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")

        self._adapters[normalized_name] = adapter_class

        if config:
            # Validate configuration before storing
            errors = ConfigurationHelper.validate_config(config)
            if errors:
                logger.warning(f"Configuration issues for {name}: {errors}")
            self._adapter_configs[normalized_name] = config

        if metadata:
            self._adapter_metadata[normalized_name] = metadata

    def get(self, name: str) -> Optional[Type[EnhancedBaseCrawler]]:
        """Get adapter class by name."""
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return self._adapters.get(normalized_name)

    def get_config(self, name: str) -> Dict[str, Any]:
        """Get adapter config by name."""
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return self._adapter_configs.get(normalized_name, {})

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get adapter metadata by name."""
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return self._adapter_metadata.get(normalized_name, {})

    def list_adapters(self) -> List[str]:
        """List all registered adapter names."""
        return list(self._adapters.keys())

    def list_by_type(self, adapter_type: str) -> List[str]:
        """List adapters by type (international, persian, aggregator)."""
        result = []
        for name in self._adapters.keys():
            metadata = self.get_metadata(name)
            if metadata.get("type") == adapter_type:
                result.append(name)
        return result

    def search_adapters(self, query: str) -> List[str]:
        """Search adapters by name or metadata."""
        query_lower = query.lower()
        results = []

        for name in self._adapters.keys():
            # Search in name
            if query_lower in name:
                results.append(name)
                continue

            # Search in metadata
            metadata = self.get_metadata(name)
            if (
                query_lower in metadata.get("description", "").lower()
                or query_lower in metadata.get("airline_name", "").lower()
                or query_lower in str(metadata.get("features", [])).lower()
            ):
                results.append(name)

        return results


class ConfigurationManager:
    """
    Configuration manager for adapters.
    """

    def __init__(self, config_dir: str = "config/site_configs"):
        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Dict[str, Any]] = {}

    def load_config(self, adapter_name: str) -> Dict[str, Any]:
        """
        Load configuration for an adapter.

        Args:
            adapter_name: Name of the adapter

        Returns:
            Configuration dictionary
        """
        if adapter_name in self._config_cache:
            return self._config_cache[adapter_name]

        # Try to load from file
        config_file = self.config_dir / f"{adapter_name}.json"

        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)

                # Merge with default configuration
                default_config = ConfigurationHelper.get_default_config()
                merged_config = ConfigurationHelper.merge_config(default_config, config)

                self._config_cache[adapter_name] = merged_config
                return merged_config

            except Exception as e:
                logger.error(f"Error loading config for {adapter_name}: {e}")

        # Return default configuration if file not found
        default_config = ConfigurationHelper.get_default_config()
        self._config_cache[adapter_name] = default_config
        return default_config

    def save_config(self, adapter_name: str, config: Dict[str, Any]) -> None:
        """
        Save configuration for an adapter.

        Args:
            adapter_name: Name of the adapter
            config: Configuration to save
        """
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)

            config_file = self.config_dir / f"{adapter_name}.json"

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Update cache
            self._config_cache[adapter_name] = config

            logger.info(f"Configuration saved for {adapter_name}")

        except Exception as e:
            logger.error(f"Error saving config for {adapter_name}: {e}")

    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._config_cache.clear()


class AdapterFactory:
    """
    Enhanced factory for creating flight crawling adapters.

    This factory provides:
    - Automatic adapter discovery and registration
    - Configuration management
    - Error handling and reporting
    - Dynamic adapter creation
    - Adapter validation
    """

    def __init__(self, config_dir: str = "config/site_configs"):
        self.registry = AdapterRegistry()
        self.config_manager = ConfigurationManager(config_dir)
        self._initialize_adapters()

    def _initialize_adapters(self) -> None:
        """Initialize and register all available adapters."""
        try:
            # Register built-in adapters
            self._register_builtin_adapters()

            # Auto-discover adapters from modules
            self._discover_adapters()

            logger.info(f"Initialized {len(self.registry.list_adapters())} adapters")

        except Exception as e:
            logger.error(f"Error initializing adapters: {e}")

    def _register_builtin_adapters(self) -> None:
        """Register built-in adapters with enhanced metadata."""

        # International airlines
        international_adapters = [
            {
                "name": "lufthansa",
                "base_url": "https://www.lufthansa.com",
                "currency": "EUR",
                "airline_name": "Lufthansa",
                "description": "German flag carrier airline",
                "features": ["star_alliance", "premium_service", "global_network"],
            },
            {
                "name": "air_france",
                "base_url": "https://www.airfrance.com",
                "currency": "EUR",
                "airline_name": "Air France",
                "description": "French flag carrier airline",
                "features": ["skyteam", "premium_service", "global_network"],
            },
            {
                "name": "british_airways",
                "base_url": "https://www.britishairways.com",
                "currency": "GBP",
                "airline_name": "British Airways",
                "description": "British flag carrier airline",
                "features": ["oneworld", "premium_service", "global_network"],
            },
            {
                "name": "emirates",
                "base_url": "https://www.emirates.com",
                "currency": "AED",
                "airline_name": "Emirates",
                "description": "Dubai-based international airline",
                "features": ["luxury_service", "global_network", "premium_fleet"],
            },
            {
                "name": "turkish_airlines",
                "base_url": "https://www.turkishairlines.com",
                "currency": "TRY",
                "airline_name": "Turkish Airlines",
                "description": "Turkish flag carrier airline",
                "features": ["star_alliance", "extensive_network", "istanbul_hub"],
            },
            {
                "name": "qatar_airways",
                "base_url": "https://www.qatarairways.com",
                "currency": "QAR",
                "airline_name": "Qatar Airways",
                "description": "Qatar flag carrier airline",
                "features": ["oneworld", "luxury_service", "doha_hub"],
            },
            {
                "name": "etihad_airways",
                "base_url": "https://www.etihad.com",
                "currency": "AED",
                "airline_name": "Etihad Airways",
                "description": "UAE flag carrier airline",
                "features": ["luxury_service", "abu_dhabi_hub", "premium_fleet"],
            },
            {
                "name": "klm",
                "base_url": "https://www.klm.com",
                "currency": "EUR",
                "airline_name": "KLM",
                "description": "Dutch flag carrier airline",
                "features": ["skyteam", "amsterdam_hub", "global_network"],
            },
            {
                "name": "pegasus",
                "base_url": "https://www.flypgs.com",
                "currency": "TRY",
                "airline_name": "Pegasus Airlines",
                "description": "Turkish low-cost airline",
                "features": ["low_cost", "turkish_routes", "budget_friendly"],
            },
        ]

        for adapter_info in international_adapters:
            self._register_international_adapter(adapter_info)

        # Iranian airlines
        persian_adapters = [
            {
                "name": "iran_air",
                "base_url": "https://www.iranair.com",
                "currency": "IRR",
                "airline_name": "Iran Air",
                "description": "Iranian flag carrier airline",
                "features": ["domestic_routes", "international_routes", "flag_carrier"],
            },
            {
                "name": "mahan_air",
                "base_url": "https://www.mahan.aero",
                "currency": "IRR",
                "airline_name": "Mahan Air",
                "description": "Iranian private airline",
                "features": ["domestic_routes", "charter_flights", "loyalty_program"],
            },
            {
                "name": "aseman_airlines",
                "base_url": "https://www.iaa.ir",
                "currency": "IRR",
                "airline_name": "Iran Aseman Airlines",
                "description": "Iranian airline",
                "features": ["domestic_routes", "regional_routes"],
            },
            {
                "name": "caspian_airlines",
                "base_url": "https://www.caspian.aero",
                "currency": "IRR",
                "airline_name": "Caspian Airlines",
                "description": "Iranian private airline",
                "features": ["domestic_routes", "charter_flights"],
            },
            {
                "name": "qeshm_air",
                "base_url": "https://www.qeshmairlines.com",
                "currency": "IRR",
                "airline_name": "Qeshm Air",
                "description": "Iranian airline",
                "features": ["domestic_routes", "island_routes"],
            },
            {
                "name": "karun_air",
                "base_url": "https://www.karunair.com",
                "currency": "IRR",
                "airline_name": "Karun Air",
                "description": "Iranian regional airline",
                "features": ["domestic_routes", "regional_focus"],
            },
            {
                "name": "sepehran_air",
                "base_url": "https://www.sepehranair.ir",
                "currency": "IRR",
                "airline_name": "Sepehran Airlines",
                "description": "Iranian airline",
                "features": ["domestic_routes", "charter_flights"],
            },
        ]

        for adapter_info in persian_adapters:
            self._register_persian_adapter(adapter_info)

        # Aggregators
        aggregator_adapters = [
            {
                "name": "alibaba",
                "base_url": "https://www.alibaba.ir",
                "currency": "IRR",
                "airline_name": "Alibaba.ir",
                "description": "Iranian flight booking aggregator",
                "features": ["aggregator", "domestic_flights", "international_flights"],
                "is_aggregator": True,
            },
            {
                "name": "flightio",
                "base_url": "https://flightio.com",
                "currency": "IRR",
                "airline_name": "Flightio",
                "description": "Flight booking platform",
                "features": ["aggregator", "multiple_airlines", "comparison"],
                "is_aggregator": True,
            },
            {
                "name": "flytoday",
                "base_url": "https://www.flytoday.ir",
                "currency": "IRR",
                "airline_name": "FlyToday",
                "description": "Iranian flight booking platform",
                "features": ["aggregator", "domestic_flights", "user_friendly"],
                "is_aggregator": True,
            },
            {
                "name": "safarmarket",
                "base_url": "https://www.safarmarket.com",
                "currency": "IRR",
                "airline_name": "SafarMarket",
                "description": "Travel booking platform",
                "features": ["aggregator", "travel_packages", "flights_hotels"],
                "is_aggregator": True,
            },
            {
                "name": "mz724",
                "base_url": "https://www.mz724.ir",
                "currency": "IRR",
                "airline_name": "MZ724",
                "description": "Iranian flight booking platform",
                "features": ["aggregator", "domestic_flights", "charter_flights"],
                "is_aggregator": True,
            },
            {
                "name": "parto_ticket",
                "base_url": "https://parto-ticket.ir",
                "currency": "IRR",
                "airline_name": "Parto Ticket",
                "description": "Iranian ticketing platform",
                "features": ["aggregator", "domestic_flights", "multiple_airlines"],
                "is_aggregator": True,
            },
            {
                "name": "book_charter",
                "base_url": "https://bookcharter.ir",
                "currency": "IRR",
                "airline_name": "Book Charter",
                "description": "Charter flight booking platform",
                "features": ["aggregator", "charter_flights", "domestic_routes"],
                "is_aggregator": True,
            },
        ]

        for adapter_info in aggregator_adapters:
            self._register_persian_adapter(adapter_info)

    def _register_international_adapter(self, adapter_info: Dict[str, Any]) -> None:
        """Register an international adapter."""
        name = adapter_info["name"]

        # Load configuration
        config = self.config_manager.load_config(name)

        # Update config with adapter info
        config.update(
            {
                "base_url": adapter_info["base_url"],
                "default_currency": adapter_info["currency"],
            }
        )

        # Create metadata
        metadata = {
            "type": "international",
            "airline_name": adapter_info["airline_name"],
            "description": adapter_info["description"],
            "features": adapter_info["features"],
            "currency": adapter_info["currency"],
            "base_url": adapter_info["base_url"],
        }

        # Create dynamic adapter class
        adapter_class = self._create_dynamic_adapter_class(
            name, EnhancedInternationalAdapter, adapter_info
        )

        self.registry.register(name, adapter_class, config, metadata)

    def _register_persian_adapter(self, adapter_info: Dict[str, Any]) -> None:
        """Register a Persian adapter."""
        name = adapter_info["name"]

        # Load configuration
        config = self.config_manager.load_config(name)

        # Update config with adapter info
        config.update(
            {
                "base_url": adapter_info["base_url"],
                "default_currency": adapter_info["currency"],
            }
        )

        # Create metadata
        metadata = {
            "type": (
                "persian" if not adapter_info.get("is_aggregator") else "aggregator"
            ),
            "airline_name": adapter_info["airline_name"],
            "description": adapter_info["description"],
            "features": adapter_info["features"],
            "currency": adapter_info["currency"],
            "base_url": adapter_info["base_url"],
            "is_aggregator": adapter_info.get("is_aggregator", False),
        }

        # Create dynamic adapter class
        adapter_class = self._create_dynamic_adapter_class(
            name, EnhancedPersianAdapter, adapter_info
        )

        self.registry.register(name, adapter_class, config, metadata)

    def _create_dynamic_adapter_class(
        self,
        name: str,
        base_class: Type[EnhancedBaseCrawler],
        adapter_info: Dict[str, Any],
    ) -> Type[EnhancedBaseCrawler]:
        """Create a dynamic adapter class."""

        class_name = f"{name.title().replace('_', '')}Adapter"

        # Define methods for the dynamic class
        def get_adapter_name(self) -> str:
            return name.replace("_", " ").title()

        def get_base_url(self) -> str:
            return adapter_info["base_url"]

        def extract_currency(self, element, config: Dict[str, Any]) -> str:
            return adapter_info.get("currency", "USD")

        def get_adapter_specific_config(self) -> Dict[str, Any]:
            return {
                "airline_name": adapter_info["airline_name"],
                "features": adapter_info["features"],
                "is_aggregator": adapter_info.get("is_aggregator", False),
            }

        # Create the dynamic class
        adapter_class = type(
            class_name,
            (base_class,),
            {
                "_get_adapter_name": get_adapter_name,
                "_get_base_url": get_base_url,
                "_extract_currency": extract_currency,
                "_get_adapter_specific_config": get_adapter_specific_config,
                "__module__": "adapters.dynamic",
            },
        )

        return adapter_class

    def _discover_adapters(self) -> None:
        """Auto-discover adapters from adapter modules."""
        try:
            # Discover Iranian airline adapters
            self._discover_adapters_in_path("adapters.site_adapters.iranian_airlines")

            # Discover international airline adapters
            self._discover_adapters_in_path(
                "adapters.site_adapters.international_airlines"
            )

            # Discover aggregator adapters
            self._discover_adapters_in_path(
                "adapters.site_adapters.iranian_aggregators"
            )
            self._discover_adapters_in_path(
                "adapters.site_adapters.international_aggregators"
            )

        except Exception as e:
            logger.warning(f"Error during adapter discovery: {e}")

    def _discover_adapters_in_path(self, module_path: str) -> None:
        """Discover adapters in a specific module path."""
        try:
            # This would require implementing a module scanner
            # For now, we rely on manual registration
            pass
        except Exception as e:
            logger.debug(f"Could not discover adapters in {module_path}: {e}")

    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """
        Create an adapter instance by name.

        Args:
            name: Adapter name (e.g., 'lufthansa', 'iran_air')
            config: Optional configuration override

        Returns:
            Adapter instance

        Raises:
            ValueError: If adapter not found
        """
        try:
            adapter_class = self.registry.get(name)

            if not adapter_class:
                # Try to find similar adapter names
                similar = self._find_similar_adapters(name)
                if similar:
                    suggestion = f" Did you mean: {', '.join(similar[:3])}?"
                else:
                    suggestion = f" Available adapters: {', '.join(self.registry.list_adapters()[:5])}"

                raise ValueError(f"Adapter '{name}' not found.{suggestion}")

            # Get default configuration
            default_config = self.registry.get_config(name)

            # Merge with provided config
            if config:
                final_config = ConfigurationHelper.merge_config(default_config, config)
            else:
                final_config = default_config

            # Validate configuration
            errors = ConfigurationHelper.validate_config(final_config)
            if errors:
                logger.warning(f"Configuration issues for {name}: {errors}")

            # Create adapter instance
            adapter = adapter_class(final_config)

            logger.info(f"Created adapter: {name}")
            return adapter

        except Exception as e:
            error_report = ErrorReportingHelper.create_error_report(
                "AdapterFactory", e, {"adapter_name": name}
            )
            ErrorReportingHelper.log_error_report(error_report, logger)
            raise

    def _find_similar_adapters(self, name: str) -> List[str]:
        """Find adapters with similar names."""
        available = self.registry.list_adapters()
        similar = []

        for adapter_name in available:
            # Simple similarity check
            if name.lower() in adapter_name or adapter_name in name.lower():
                similar.append(adapter_name)

        return similar

    def create_adapter_from_module(
        self, module_path: str, class_name: str, config: Dict[str, Any]
    ) -> EnhancedBaseCrawler:
        """
        Create adapter from a specific module.

        Args:
            module_path: Full module path
            class_name: Class name in the module
            config: Configuration for the adapter

        Returns:
            Adapter instance
        """
        try:
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)

            if not issubclass(adapter_class, EnhancedBaseCrawler):
                raise ValueError(f"{class_name} is not a valid adapter class")

            return adapter_class(config)

        except Exception as e:
            logger.error(f"Error creating adapter from module {module_path}: {e}")
            raise

    def list_available_adapters(self) -> List[str]:
        """List all available adapter names."""
        return self.registry.list_adapters()

    def list_adapters_by_type(self, adapter_type: str) -> List[str]:
        """List adapters by type."""
        return self.registry.list_by_type(adapter_type)

    def search_adapters(self, query: str) -> List[str]:
        """Search adapters by name or features."""
        return self.registry.search_adapters(query)

    def get_adapter_info(self, name: str) -> Dict[str, Any]:
        """
        Get detailed information about an adapter.

        Args:
            name: Adapter name

        Returns:
            Dictionary with adapter information
        """
        if name not in self.registry.list_adapters():
            raise ValueError(f"Adapter '{name}' not found")

        metadata = self.registry.get_metadata(name)
        config = self.registry.get_config(name)

        return {
            "name": name,
            "metadata": metadata,
            "config_keys": list(config.keys()),
            "has_custom_implementation": self._has_custom_implementation(name),
        }

    def _has_custom_implementation(self, name: str) -> bool:
        """Check if adapter has custom implementation."""
        try:
            # Try to import custom implementation
            module_path = f"adapters.site_adapters.{name}_adapter"
            importlib.import_module(module_path)
            return True
        except ImportError:
            return False

    def validate_adapter_config(self, name: str, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration for a specific adapter.

        Args:
            name: Adapter name
            config: Configuration to validate

        Returns:
            List of validation errors
        """
        return ConfigurationHelper.validate_config(config)

    def save_adapter_config(self, name: str, config: Dict[str, Any]) -> None:
        """
        Save configuration for an adapter.

        Args:
            name: Adapter name
            config: Configuration to save
        """
        self.config_manager.save_config(name, config)

    def reload_adapters(self) -> None:
        """Reload all adapters and configurations."""
        self.config_manager.clear_cache()
        self.registry = AdapterRegistry()
        self._initialize_adapters()


# Global factory instance
_factory = None


def get_factory() -> AdapterFactory:
    """Get the global adapter factory instance."""
    global _factory
    if _factory is None:
        _factory = AdapterFactory()
    return _factory


def create_adapter(
    name: str, config: Optional[Dict[str, Any]] = None
) -> EnhancedBaseCrawler:
    """
    Create an adapter instance using the global factory.

    Args:
        name: Adapter name
        config: Optional configuration override

    Returns:
        Adapter instance
    """
    return get_factory().create_adapter(name, config)


def list_adapters() -> List[str]:
    """List all available adapters."""
    return get_factory().list_available_adapters()


def search_adapters(query: str) -> List[str]:
    """Search adapters by name or features."""
    return get_factory().search_adapters(query)


def get_adapter_info(name: str) -> Dict[str, Any]:
    """Get information about a specific adapter."""
    return get_factory().get_adapter_info(name)
