"""
Enhanced Adapter Factory for creating flight crawling adapters.

This factory provides a clean interface for creating adapters with
automatic configuration management and comprehensive error handling.
"""

from typing import Dict, Any, Type, Optional, List, Union
from abc import ABC
import importlib
import logging
import json
import os
from pathlib import Path
import uuid
from datetime import datetime
import asyncio

from adapters.base_adapters import (
    EnhancedBaseCrawler,
    EnhancedInternationalAdapter,
    EnhancedPersianAdapter,
    ConfigurationHelper,
    ErrorReportingHelper,
)
from adapters.base_adapters.enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    error_handler_decorator,
    get_global_error_handler
)


logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Enhanced registry for adapter classes with configuration management and error handling.
    """

    def __init__(self):
        self._adapters: Dict[str, Type[EnhancedBaseCrawler]] = {}
        self._adapter_configs: Dict[str, Dict[str, Any]] = {}
        self._adapter_metadata: Dict[str, Dict[str, Any]] = {}
        self.error_handler = get_global_error_handler()

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
        try:
            normalized_name = name.lower().replace("-", "_").replace(" ", "_")

            self._adapters[normalized_name] = adapter_class

            if config:
                # Validate configuration before storing
                errors = ConfigurationHelper.validate_config(config)
                if errors:
                    logger.warning(f"Configuration issues for {name}: {errors}")
                    
                    # Create error context for configuration issues
                    error_context = ErrorContext(
                        adapter_name=normalized_name,
                        operation="register_adapter_config",
                        additional_info={
                            "config_errors": errors,
                            "config_keys": list(config.keys())
                        }
                    )
                    
                    # Report configuration errors (non-blocking)
                    asyncio.create_task(self.error_handler.handle_error(
                        ValueError(f"Configuration validation errors: {errors}"),
                        error_context,
                        ErrorSeverity.MEDIUM,
                        ErrorCategory.VALIDATION,
                        ErrorAction.SKIP
                    ))
                    
                self._adapter_configs[normalized_name] = config

            if metadata:
                self._adapter_metadata[normalized_name] = metadata
                
            logger.debug(f"Successfully registered adapter: {name}")
            
        except Exception as e:
            error_context = ErrorContext(
                adapter_name=name,
                operation="register_adapter",
                additional_info={
                    "adapter_class": str(adapter_class),
                    "config_provided": config is not None,
                    "metadata_provided": metadata is not None
                }
            )
            
            # Report registration error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Failed to register adapter {name}: {e}")
            raise

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

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the registry."""
        return {
            "total_adapters": len(self._adapters),
            "adapters_with_config": len(self._adapter_configs),
            "adapters_with_metadata": len(self._adapter_metadata),
            "adapter_types": self._get_adapter_type_counts(),
            "timestamp": datetime.now().isoformat()
        }

    def _get_adapter_type_counts(self) -> Dict[str, int]:
        """Get count of adapters by type."""
        type_counts = {}
        for name in self._adapters.keys():
            metadata = self.get_metadata(name)
            adapter_type = metadata.get("type", "unknown")
            type_counts[adapter_type] = type_counts.get(adapter_type, 0) + 1
        return type_counts


class ConfigurationManager:
    """
    Enhanced configuration manager for adapters with error handling.
    """

    def __init__(self, config_dir: str = "config/site_configs"):
        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self.error_handler = get_global_error_handler()

    @error_handler_decorator(
        operation_name="load_config",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.MEDIUM,
        max_retries=2
    )
    def load_config(self, adapter_name: str) -> Dict[str, Any]:
        """
        Load configuration for an adapter with enhanced error handling.

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
                logger.debug(f"Successfully loaded config for {adapter_name}")
                return merged_config

            except Exception as e:
                error_context = ErrorContext(
                    adapter_name=adapter_name,
                    operation="load_config_file",
                    additional_info={
                        "config_file": str(config_file),
                        "file_exists": config_file.exists(),
                        "file_size": config_file.stat().st_size if config_file.exists() else 0
                    }
                )
                
                # Report file loading error (non-blocking)
                asyncio.create_task(self.error_handler.handle_error(
                    e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
                ))
                
                logger.error(f"Error loading config for {adapter_name}: {e}")

        # Return default configuration if file not found or loading failed
        default_config = ConfigurationHelper.get_default_config()
        self._config_cache[adapter_name] = default_config
        logger.info(f"Using default config for {adapter_name}")
        return default_config

    @error_handler_decorator(
        operation_name="save_config",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.MEDIUM,
        max_retries=2
    )
    def save_config(self, adapter_name: str, config: Dict[str, Any]) -> None:
        """
        Save configuration for an adapter with enhanced error handling.

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
            error_context = ErrorContext(
                adapter_name=adapter_name,
                operation="save_config",
                additional_info={
                    "config_file": str(config_file) if 'config_file' in locals() else "unknown",
                    "config_size": len(str(config)),
                    "config_keys": list(config.keys())
                }
            )
            
            # Report save error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error saving config for {adapter_name}: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._config_cache.clear()
        logger.debug("Configuration cache cleared")

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information."""
        return {
            "cached_configs": len(self._config_cache),
            "cached_adapters": list(self._config_cache.keys()),
            "cache_memory_usage": sum(len(str(config)) for config in self._config_cache.values())
        }


class AdapterFactory:
    """
    Enhanced factory for creating flight crawling adapters.

    This factory provides:
    - Automatic adapter discovery and registration
    - Configuration management with error handling
    - Circuit breaker pattern for adapter creation
    - Comprehensive error reporting and recovery
    - Adapter validation and health monitoring
    """

    def __init__(self, http_session: Optional[Any] = None, config_dir: str = "config/site_configs"):
        self.registry = AdapterRegistry()
        self.config_manager = ConfigurationManager(config_dir)
        self.http_session = http_session
        self.error_handler = get_global_error_handler()
        self.factory_id = str(uuid.uuid4())
        
        # Adapter creation statistics
        self.creation_stats = {
            "total_created": 0,
            "successful_creations": 0,
            "failed_creations": 0,
            "creation_errors": [],
            "last_creation_time": None,
            "most_requested_adapters": {}
        }
        
        self._initialize_adapters()

    @error_handler_decorator(
        operation_name="initialize_adapters",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    def _initialize_adapters(self) -> None:
        """Initialize and register all available adapters with enhanced error handling."""
        try:
            # Register built-in adapters
            self._register_builtin_adapters()

            # Auto-discover adapters from modules
            self._discover_adapters()

            logger.info(f"Initialized {len(self.registry.list_adapters())} adapters")

        except Exception as e:
            error_context = ErrorContext(
                adapter_name="factory",
                operation="initialize_adapters",
                additional_info={
                    "factory_id": self.factory_id,
                    "adapters_registered": len(self.registry.list_adapters())
                }
            )
            
            # Report initialization error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error initializing adapters: {e}")
            raise

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
            try:
                self._register_international_adapter(adapter_info)
            except Exception as e:
                logger.warning(f"Failed to register international adapter {adapter_info['name']}: {e}")

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
            try:
                self._register_persian_adapter(adapter_info)
            except Exception as e:
                logger.warning(f"Failed to register Persian adapter {adapter_info['name']}: {e}")

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
                "description": "Iranian booking platform",
                "features": ["aggregator", "domestic_flights", "charter_flights"],
                "is_aggregator": True,
            },
            {
                "name": "parto_ticket",
                "base_url": "https://www.partoticket.com",
                "currency": "IRR",
                "airline_name": "Parto Ticket",
                "description": "Iranian travel booking platform",
                "features": ["aggregator", "domestic_flights", "travel_services"],
                "is_aggregator": True,
            },
            {
                "name": "parto_crs",
                "base_url": "https://www.partocrs.com",
                "currency": "IRR",
                "airline_name": "Parto CRS",
                "description": "Iranian CRS platform",
                "features": ["aggregator", "crs_system", "travel_agents"],
                "is_aggregator": True,
            },
            {
                "name": "book_charter",
                "base_url": "https://www.bookcharter.ir",
                "currency": "IRR",
                "airline_name": "Book Charter",
                "description": "Iranian charter booking platform",
                "features": ["aggregator", "charter_flights", "domestic_routes"],
                "is_aggregator": True,
            },
            {
                "name": "book_charter_724",
                "base_url": "https://www.bookcharter724.ir",
                "currency": "IRR",
                "airline_name": "Book Charter 724",
                "description": "Iranian charter booking platform",
                "features": ["aggregator", "charter_flights", "24_7_service"],
                "is_aggregator": True,
            },
            {
                "name": "snapptrip",
                "base_url": "https://www.snapptrip.com",
                "currency": "IRR",
                "airline_name": "Snapp Trip",
                "description": "Iranian travel booking platform",
                "features": ["aggregator", "domestic_flights", "hotels"],
                "is_aggregator": True,
            },
        ]

        for adapter_info in aggregator_adapters:
            try:
                self._register_aggregator_adapter(adapter_info)
            except Exception as e:
                logger.warning(f"Failed to register aggregator adapter {adapter_info['name']}: {e}")

    def _register_international_adapter(self, adapter_info: Dict[str, Any]) -> None:
        """Register an international adapter with error handling."""
        try:
            adapter_class = self._create_dynamic_adapter_class(
                adapter_info["name"], EnhancedInternationalAdapter, adapter_info
            )

            config = {
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"],
                "timeout": 30,
                "extraction_config": ConfigurationHelper.get_default_extraction_config(),
                "name": adapter_info["name"]
            }

            metadata = {
                "type": "international",
                "airline_name": adapter_info["airline_name"],
                "description": adapter_info["description"],
                "features": adapter_info["features"],
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"]
            }

            self.registry.register(adapter_info["name"], adapter_class, config, metadata)

        except Exception as e:
            error_context = ErrorContext(
                adapter_name=adapter_info["name"],
                operation="register_international_adapter",
                additional_info={
                    "adapter_info": adapter_info,
                    "adapter_type": "international"
                }
            )
            
            # Report registration error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Failed to register international adapter {adapter_info['name']}: {e}")
            raise

    def _register_persian_adapter(self, adapter_info: Dict[str, Any]) -> None:
        """Register a Persian adapter with error handling."""
        try:
            adapter_class = self._create_dynamic_adapter_class(
                adapter_info["name"], EnhancedPersianAdapter, adapter_info
            )

            config = {
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"],
                "timeout": 30,
                "extraction_config": ConfigurationHelper.get_default_extraction_config(),
                "name": adapter_info["name"]
            }

            metadata = {
                "type": "persian",
                "airline_name": adapter_info["airline_name"],
                "description": adapter_info["description"],
                "features": adapter_info["features"],
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"]
            }

            self.registry.register(adapter_info["name"], adapter_class, config, metadata)

        except Exception as e:
            error_context = ErrorContext(
                adapter_name=adapter_info["name"],
                operation="register_persian_adapter",
                additional_info={
                    "adapter_info": adapter_info,
                    "adapter_type": "persian"
                }
            )
            
            # Report registration error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Failed to register Persian adapter {adapter_info['name']}: {e}")
            raise

    def _register_aggregator_adapter(self, adapter_info: Dict[str, Any]) -> None:
        """Register an aggregator adapter with error handling."""
        try:
            adapter_class = self._create_dynamic_adapter_class(
                adapter_info["name"], EnhancedPersianAdapter, adapter_info
            )

            config = {
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"],
                "timeout": 30,
                "extraction_config": ConfigurationHelper.get_default_extraction_config(),
                "name": adapter_info["name"]
            }

            metadata = {
                "type": "aggregator",
                "airline_name": adapter_info["airline_name"],
                "description": adapter_info["description"],
                "features": adapter_info["features"],
                "base_url": adapter_info["base_url"],
                "currency": adapter_info["currency"],
                "is_aggregator": True
            }

            self.registry.register(adapter_info["name"], adapter_class, config, metadata)

        except Exception as e:
            error_context = ErrorContext(
                adapter_name=adapter_info["name"],
                operation="register_aggregator_adapter",
                additional_info={
                    "adapter_info": adapter_info,
                    "adapter_type": "aggregator"
                }
            )
            
            # Report registration error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Failed to register aggregator adapter {adapter_info['name']}: {e}")
            raise

    def _create_dynamic_adapter_class(
        self,
        name: str,
        base_class: Type[EnhancedBaseCrawler],
        adapter_info: Dict[str, Any],
    ) -> Type[EnhancedBaseCrawler]:
        """Create a dynamic adapter class."""

        class DynamicAdapter(base_class):
            def get_adapter_name(self) -> str:
                return name

            def get_base_url(self) -> str:
                return adapter_info["base_url"]

            def extract_currency(self, element, config: Dict[str, Any]) -> str:
                return adapter_info["currency"]

            def get_adapter_specific_config(self) -> Dict[str, Any]:
                return {
                    "airline_name": adapter_info["airline_name"],
                    "description": adapter_info["description"],
                    "features": adapter_info["features"]
                }

        DynamicAdapter.__name__ = f"Dynamic{name.title().replace('_', '')}Adapter"
        DynamicAdapter.__qualname__ = DynamicAdapter.__name__
        
        return DynamicAdapter

    def _discover_adapters(self) -> None:
        """Discover adapters from modules with error handling."""
        try:
            # Discover adapters in site_adapters modules
            self._discover_adapters_in_path("adapters.site_adapters.iranian_airlines")
            self._discover_adapters_in_path("adapters.site_adapters.international_airlines")
            self._discover_adapters_in_path("adapters.site_adapters.refactored")
            
            logger.debug("Adapter discovery completed")
            
        except Exception as e:
            error_context = ErrorContext(
                adapter_name="factory",
                operation="discover_adapters",
                additional_info={
                    "factory_id": self.factory_id,
                    "discovery_paths": [
                        "adapters.site_adapters.iranian_airlines",
                        "adapters.site_adapters.international_airlines",
                        "adapters.site_adapters.refactored"
                    ]
                }
            )
            
            # Report discovery error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.warning(f"Error during adapter discovery: {e}")

    def _discover_adapters_in_path(self, module_path: str) -> None:
        """Discover adapters in a specific module path."""
        try:
            # Try to import the module and discover adapters
            module = importlib.import_module(module_path)
            # Implementation would depend on the specific module structure
            logger.debug(f"Successfully discovered adapters in {module_path}")
            
        except ImportError:
            logger.debug(f"Module {module_path} not found, skipping discovery")
        except Exception as e:
            logger.debug(f"Could not discover adapters in {module_path}: {e}")

    @error_handler_decorator(
        operation_name="create_adapter",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    def create_adapter(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> EnhancedBaseCrawler:
        """
        Create an adapter instance with comprehensive error handling and monitoring.

        Args:
            name: Name of the adapter
            config: Optional override configuration

        Returns:
            An instance of the requested adapter.

        Raises:
            ValueError: If the adapter is not found.
        """
        creation_start_time = datetime.now()
        
        # Update statistics
        self.creation_stats["total_created"] += 1
        self.creation_stats["last_creation_time"] = creation_start_time
        
        # Track most requested adapters
        self.creation_stats["most_requested_adapters"][name] = (
            self.creation_stats["most_requested_adapters"].get(name, 0) + 1
        )
        
        try:
            normalized_name = name.lower().replace("-", "_").replace(" ", "_")

            # Load configuration
            adapter_class = self.registry.get(normalized_name)
            if not adapter_class:
                similar = self._find_similar_adapters(normalized_name)
                if similar:
                    error_msg = f"Adapter '{name}' not found. Did you mean one of: {', '.join(similar)}?"
                    raise ValueError(error_msg)
                raise ValueError(f"Adapter '{name}' not found.")

            # Merge configurations
            base_config = self.config_manager.load_config(normalized_name)
            final_config = ConfigurationHelper.merge_config(base_config, config or {})

            # Create error context for adapter creation
            error_context = ErrorContext(
                adapter_name=normalized_name,
                operation="create_adapter_instance",
                additional_info={
                    "factory_id": self.factory_id,
                    "adapter_class": str(adapter_class),
                    "config_keys": list(final_config.keys()),
                    "has_http_session": self.http_session is not None
                }
            )

            # Create adapter instance
            try:
                # Pass http_session to the adapter's constructor
                adapter = adapter_class(config=final_config, http_session=self.http_session)
                
                # Record successful creation
                self.creation_stats["successful_creations"] += 1
                creation_duration = (datetime.now() - creation_start_time).total_seconds()
                
                logger.info(f"Successfully created adapter '{name}' in {creation_duration:.2f}s")
                return adapter
                
            except TypeError:
                # Fallback for adapters that don't accept http_session
                logger.warning(f"Adapter '{name}' does not accept 'http_session' argument. "
                               f"Consider updating its constructor.")
                
                adapter = adapter_class(config=final_config)
                
                # Record successful creation
                self.creation_stats["successful_creations"] += 1
                creation_duration = (datetime.now() - creation_start_time).total_seconds()
                
                logger.info(f"Successfully created adapter '{name}' (fallback mode) in {creation_duration:.2f}s")
                return adapter
                
        except Exception as e:
            # Record failed creation
            self.creation_stats["failed_creations"] += 1
            error_info = {
                "adapter_name": name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.creation_stats["creation_errors"].append(error_info)
            
            # Keep only last 100 errors
            if len(self.creation_stats["creation_errors"]) > 100:
                self.creation_stats["creation_errors"] = self.creation_stats["creation_errors"][-100:]
            
            error_context = ErrorContext(
                adapter_name=name,
                operation="create_adapter",
                additional_info={
                    "factory_id": self.factory_id,
                    "config_provided": config is not None,
                    "creation_duration": (datetime.now() - creation_start_time).total_seconds()
                }
            )
            
            # Report creation error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Failed to create adapter '{name}': {e}")
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

    @error_handler_decorator(
        operation_name="create_adapter_from_module",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    def create_adapter_from_module(
        self, module_path: str, class_name: str, config: Dict[str, Any]
    ) -> EnhancedBaseCrawler:
        """
        Create adapter from a specific module with enhanced error handling.

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

            adapter = adapter_class(config)
            logger.info(f"Successfully created adapter from module {module_path}.{class_name}")
            return adapter

        except Exception as e:
            error_context = ErrorContext(
                adapter_name=class_name,
                operation="create_adapter_from_module",
                additional_info={
                    "module_path": module_path,
                    "class_name": class_name,
                    "config_keys": list(config.keys())
                }
            )
            
            # Report module creation error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.RESOURCE
            ))
            
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
        try:
            self.config_manager.clear_cache()
            self.registry = AdapterRegistry()
            self._initialize_adapters()
            logger.info("Successfully reloaded all adapters")
            
        except Exception as e:
            error_context = ErrorContext(
                adapter_name="factory",
                operation="reload_adapters",
                additional_info={
                    "factory_id": self.factory_id,
                    "previous_adapter_count": len(self.registry.list_adapters())
                }
            )
            
            # Report reload error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error reloading adapters: {e}")
            raise

    def get_factory_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the factory."""
        try:
            registry_status = self.registry.get_health_status()
            config_status = self.config_manager.get_cache_status()
            error_stats = self.error_handler.get_error_statistics()
            
            return {
                "factory_id": self.factory_id,
                "is_healthy": True,
                "registry_status": registry_status,
                "config_status": config_status,
                "creation_stats": self.creation_stats,
                "error_statistics": error_stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get factory health status: {e}")
            return {
                "factory_id": self.factory_id,
                "is_healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def reset_factory_errors(self) -> None:
        """Reset factory error state and statistics."""
        try:
            # Reset creation statistics
            self.creation_stats = {
                "total_created": 0,
                "successful_creations": 0,
                "failed_creations": 0,
                "creation_errors": [],
                "last_creation_time": None,
                "most_requested_adapters": {}
            }
            
            # Reset circuit breakers for all adapters
            for adapter_name in self.registry.list_adapters():
                asyncio.create_task(self.error_handler.reset_circuit_breaker(adapter_name))
                
            logger.info("Successfully reset factory error state")
            
        except Exception as e:
            logger.error(f"Failed to reset factory error state: {e}")
            raise


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
    """Get detailed information about an adapter."""
    return get_factory().get_adapter_info(name)


def get_factory_health() -> Dict[str, Any]:
    """Get health status of the global factory."""
    return get_factory().get_factory_health_status()


def reset_factory_errors() -> None:
    """Reset error state of the global factory."""
    get_factory().reset_factory_errors()
