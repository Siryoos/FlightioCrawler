"""
Unified Adapter Factory - Complete Solution

This factory combines the best features from both previous factory implementations:
- Comprehensive error handling and monitoring from adapter_factory.py
- Clean design patterns and architecture from enhanced_adapter_factory.py
- Unified creation strategies and lifecycle management
- Advanced configuration management and validation
- Performance optimization and resource management
"""

from typing import Dict, Any, Type, Optional, List, Union, Protocol, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import importlib
import logging
import json
import os
from pathlib import Path
import uuid
from datetime import datetime
import asyncio
import threading

from adapters.base_adapters import (
    EnhancedBaseCrawler,
    UnifiedSiteAdapter,
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


# Enums and Data Classes
class AdapterType(Enum):
    """Enumeration of adapter types."""
    PERSIAN = "persian"
    INTERNATIONAL = "international"
    AGGREGATOR = "aggregator"


class CreationStrategy(Enum):
    """Adapter creation strategies."""
    DIRECT = "direct"
    MODULE = "module"
    DYNAMIC = "dynamic"
    REGISTRY = "registry"


@dataclass
class AdapterMetadata:
    """Enhanced metadata for adapter registration."""
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
    creation_strategy: CreationStrategy = CreationStrategy.DIRECT
    module_path: Optional[str] = None
    class_name: Optional[str] = None
    priority: int = 0
    health_check_url: Optional[str] = None
    rate_limit_config: Optional[Dict[str, Any]] = None


@dataclass
class FactoryMetrics:
    """Factory performance and usage metrics."""
    total_created: int = 0
    successful_creations: int = 0
    failed_creations: int = 0
    creation_errors: List[str] = field(default_factory=list)
    last_creation_time: Optional[datetime] = None
    most_requested_adapters: Dict[str, int] = field(default_factory=dict)
    average_creation_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


# Strategy Protocols
class AdapterCreationStrategy(Protocol):
    """Protocol for adapter creation strategies."""
    
    def create_adapter(
        self, 
        name: str, 
        config: Dict[str, Any], 
        metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create an adapter instance."""
        ...


class ConfigurationBuilder:
    """Enhanced configuration builder with validation and optimization."""
    
    def __init__(self):
        self.reset()
    
    def reset(self) -> "ConfigurationBuilder":
        """Reset builder to initial state."""
        self._config = {}
        return self
    
    def with_base_config(self, base_config: Dict[str, Any]) -> "ConfigurationBuilder":
        """Add base configuration."""
        self._config.update(base_config)
        return self
    
    def with_metadata(self, metadata: AdapterMetadata) -> "ConfigurationBuilder":
        """Add metadata-based configuration."""
        self._config.update({
            'name': metadata.name,
            'base_url': metadata.base_url,
            'currency': metadata.currency,
            'airline_name': metadata.airline_name,
            'adapter_type': metadata.adapter_type.value,
            'features': metadata.features,
            'supported_routes': metadata.supported_routes
        })
        return self
    
    def with_rate_limiting(
        self,
        requests_per_second: float = 2.0,
        burst_limit: int = 5,
        cooldown_period: int = 60
    ) -> "ConfigurationBuilder":
        """Add rate limiting configuration."""
        self._config['rate_limiting'] = {
            'requests_per_second': requests_per_second,
            'burst_limit': burst_limit,
            'cooldown_period': cooldown_period
        }
        return self
    
    def with_error_handling(
        self,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        circuit_breaker: Optional[Dict[str, Any]] = None
    ) -> "ConfigurationBuilder":
        """Add error handling configuration."""
        self._config['error_handling'] = {
            'max_retries': max_retries,
            'retry_delay': retry_delay,
            'circuit_breaker': circuit_breaker or {}
        }
        return self
    
    def with_custom_config(self, key: str, value: Any) -> "ConfigurationBuilder":
        """Add custom configuration."""
        self._config[key] = value
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build and validate final configuration."""
        # Validate configuration
        errors = ConfigurationHelper.validate_config(self._config)
        if errors:
            logger.warning(f"Configuration validation issues: {errors}")
        
        return self._config.copy()


# Creation Strategy Implementations
class DirectCreationStrategy:
    """Strategy for creating adapters directly from classes."""
    
    def create_adapter(
        self, 
        name: str, 
        config: Dict[str, Any], 
        metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create adapter using direct class instantiation."""
        try:
            # Determine base class based on adapter type
            base_class_map = {
                AdapterType.PERSIAN: EnhancedPersianAdapter,
                AdapterType.INTERNATIONAL: EnhancedInternationalAdapter,
                AdapterType.AGGREGATOR: UnifiedSiteAdapter
            }
            
            base_class = base_class_map.get(metadata.adapter_type, UnifiedSiteAdapter)
            
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
        """Create a dynamic adapter class with enhanced features."""
        
        class DynamicAdapter(base_class):
            def get_adapter_name(self) -> str:
                return metadata.name
            
            def _get_base_url(self) -> str:
                return metadata.base_url
            
            def _extract_currency(self, element, config: Dict[str, Any]) -> str:
                return metadata.currency
            
            def get_adapter_specific_config(self) -> Dict[str, Any]:
                return config
            
            def get_adapter_info(self) -> Dict[str, Any]:
                return {
                    'name': metadata.name,
                    'type': metadata.adapter_type.value,
                    'airline': metadata.airline_name,
                    'currency': metadata.currency,
                    'features': metadata.features,
                    'description': metadata.description
                }
        
        DynamicAdapter.__name__ = f"Dynamic{name.title()}Adapter"
        return DynamicAdapter


class ModuleCreationStrategy:
    """Strategy for creating adapters from modules."""
    
    def create_adapter(
        self, 
        name: str, 
        config: Dict[str, Any], 
        metadata: AdapterMetadata
    ) -> EnhancedBaseCrawler:
        """Create adapter from module and class name."""
        try:
            if not metadata.module_path or not metadata.class_name:
                raise ValueError(f"Module path and class name required for {name}")
            
            # Import module
            module = importlib.import_module(metadata.module_path)
            adapter_class = getattr(module, metadata.class_name)
            
            return adapter_class(config)
            
        except Exception as e:
            logger.error(f"Error creating adapter {name} from module: {e}")
            raise


# Registry and Factory Implementation
class AdapterRegistry:
    """Enhanced thread-safe adapter registry with comprehensive management."""
    
    def __init__(self):
        self._adapters: Dict[str, AdapterMetadata] = {}
        self._adapter_classes: Dict[str, Type[EnhancedBaseCrawler]] = {}
        self._lock = threading.RLock()
        self.error_handler = get_global_error_handler()
    
    def register(
        self,
        metadata: AdapterMetadata,
        adapter_class: Optional[Type[EnhancedBaseCrawler]] = None
    ) -> None:
        """Register an adapter with metadata and optional class."""
        with self._lock:
            normalized_name = self._normalize_name(metadata.name)
            self._adapters[normalized_name] = metadata
            
            if adapter_class:
                self._adapter_classes[normalized_name] = adapter_class
            
            logger.debug(f"Registered adapter: {metadata.name}")
    
    def get_metadata(self, name: str) -> Optional[AdapterMetadata]:
        """Get adapter metadata."""
        with self._lock:
            normalized_name = self._normalize_name(name)
            return self._adapters.get(normalized_name)
    
    def get_adapter_class(self, name: str) -> Optional[Type[EnhancedBaseCrawler]]:
        """Get adapter class if directly registered."""
        with self._lock:
            normalized_name = self._normalize_name(name)
            return self._adapter_classes.get(normalized_name)
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter names."""
        with self._lock:
            return list(self._adapters.keys())
    
    def list_by_type(self, adapter_type: AdapterType) -> List[str]:
        """List adapters by type."""
        with self._lock:
            return [
                name for name, metadata in self._adapters.items()
                if metadata.adapter_type == adapter_type
            ]
    
    def search_adapters(self, query: str) -> List[str]:
        """Search adapters by name, description, or features."""
        with self._lock:
            query_lower = query.lower()
            results = []
            
            for name, metadata in self._adapters.items():
                if (query_lower in name.lower() or
                    query_lower in metadata.description.lower() or
                    any(query_lower in feature.lower() for feature in metadata.features)):
                    results.append(name)
            
            return results
    
    def _normalize_name(self, name: str) -> str:
        """Normalize adapter name."""
        return name.lower().replace("-", "_").replace(" ", "_")


class ConfigurationManager:
    """Enhanced configuration manager with caching and validation."""
    
    def __init__(self, config_dir: str = "config/site_configs"):
        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self.cache_ttl = 300  # 5 minutes
    
    @error_handler_decorator(
        operation_name="load_config",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.MEDIUM,
        max_retries=2
    )
    def load_config(self, adapter_name: str) -> Dict[str, Any]:
        """Load configuration with caching and validation."""
        # Check cache first
        if self._is_cache_valid(adapter_name):
            return self._config_cache[adapter_name].copy()
        
        # Load from file
        config_file = self.config_dir / f"{adapter_name}.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Validate configuration
                errors = ConfigurationHelper.validate_config(config)
                if errors:
                    logger.warning(f"Configuration issues for {adapter_name}: {errors}")
                
                # Cache the config
                self._config_cache[adapter_name] = config
                self._cache_timestamps[adapter_name] = datetime.now()
                
                return config.copy()
                
            except Exception as e:
                logger.error(f"Error loading config for {adapter_name}: {e}")
                return {}
        
        # Return default config if file doesn't exist
        return self._get_default_config(adapter_name)
    
    def _is_cache_valid(self, adapter_name: str) -> bool:
        """Check if cached config is still valid."""
        if adapter_name not in self._config_cache:
            return False
        
        cache_time = self._cache_timestamps.get(adapter_name)
        if not cache_time:
            return False
        
        return (datetime.now() - cache_time).total_seconds() < self.cache_ttl
    
    def _get_default_config(self, adapter_name: str) -> Dict[str, Any]:
        """Get default configuration for adapter."""
        return {
            'name': adapter_name,
            'rate_limiting': {
                'requests_per_second': 2.0,
                'burst_limit': 5,
                'cooldown_period': 60
            },
            'error_handling': {
                'max_retries': 3,
                'retry_delay': 5.0
            },
            'monitoring': {
                'enabled': True,
                'log_level': 'INFO'
            }
        }


# Main Unified Factory
class UnifiedAdapterFactory:
    """
    Unified Adapter Factory combining all best practices and features.
    
    Features:
    - Multiple creation strategies
    - Comprehensive error handling
    - Configuration management
    - Performance monitoring
    - Thread safety
    - Caching and optimization
    - Health monitoring
    - Lifecycle management
    """
    
    def __init__(
        self, 
        config_dir: str = "config/site_configs",
        default_strategy: CreationStrategy = CreationStrategy.DIRECT
    ):
        self.factory_id = str(uuid.uuid4())
        self.registry = AdapterRegistry()
        self.config_manager = ConfigurationManager(config_dir)
        self.error_handler = get_global_error_handler()
        self.metrics = FactoryMetrics()
        
        # Creation strategies
        self._strategies = {
            CreationStrategy.DIRECT: DirectCreationStrategy(),
            CreationStrategy.MODULE: ModuleCreationStrategy()
        }
        self.default_strategy = default_strategy
        
        # Adapter cache
        self._adapter_cache: Dict[str, EnhancedBaseCrawler] = {}
        self._cache_lock = threading.RLock()
        
        # Initialize built-in adapters
        self._initialize_builtin_adapters()
        
        logger.info(f"Unified adapter factory initialized with ID: {self.factory_id}")
    
    def _initialize_builtin_adapters(self) -> None:
        """Initialize built-in adapters with comprehensive metadata."""
        
        # Persian/Iranian adapters
        persian_adapters = [
            {
                'name': 'alibaba',
                'base_url': 'https://www.alibaba.ir',
                'currency': 'IRR',
                'airline_name': 'Alibaba.ir',
                'description': 'Iranian flight booking aggregator with enhanced features',
                'features': ['aggregator', 'persian_text', 'memory_optimized', 'intelligent_retry'],
                'adapter_type': AdapterType.AGGREGATOR,
                'module_path': 'adapters.site_adapters.iranian_airlines.alibaba_adapter_enhanced',
                'class_name': 'EnhancedAlibabaAdapter',
                'creation_strategy': CreationStrategy.MODULE
            },
            {
                'name': 'iran_air',
                'base_url': 'https://www.iranair.com',
                'currency': 'IRR',
                'airline_name': 'Iran Air',
                'description': 'Iranian flag carrier airline',
                'features': ['flag_carrier', 'domestic_routes', 'international_routes'],
                'adapter_type': AdapterType.PERSIAN
            },
            {
                'name': 'mahan_air',
                'base_url': 'https://www.mahan.aero',
                'currency': 'IRR',
                'airline_name': 'Mahan Air',
                'description': 'Iranian private airline',
                'features': ['domestic_routes', 'charter_flights', 'loyalty_program'],
                'adapter_type': AdapterType.PERSIAN
            }
        ]
        
        # International adapters
        international_adapters = [
            {
                'name': 'lufthansa',
                'base_url': 'https://www.lufthansa.com',
                'currency': 'EUR',
                'airline_name': 'Lufthansa',
                'description': 'German flag carrier airline',
                'features': ['star_alliance', 'premium_service', 'global_network'],
                'adapter_type': AdapterType.INTERNATIONAL
            },
            {
                'name': 'emirates',
                'base_url': 'https://www.emirates.com',
                'currency': 'AED',
                'airline_name': 'Emirates',
                'description': 'Dubai-based international airline',
                'features': ['luxury_service', 'global_network', 'premium_fleet'],
                'adapter_type': AdapterType.INTERNATIONAL
            }
        ]
        
        # Register all adapters
        all_adapters = persian_adapters + international_adapters
        
        for adapter_info in all_adapters:
            metadata = AdapterMetadata(
                name=adapter_info['name'],
                adapter_type=adapter_info['adapter_type'],
                base_url=adapter_info['base_url'],
                currency=adapter_info['currency'],
                airline_name=adapter_info['airline_name'],
                description=adapter_info['description'],
                features=adapter_info['features'],
                creation_strategy=adapter_info.get('creation_strategy', CreationStrategy.DIRECT),
                module_path=adapter_info.get('module_path'),
                class_name=adapter_info.get('class_name')
            )
            
            self.registry.register(metadata)
    
    @error_handler_decorator(
        operation_name="create_adapter",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    def create_adapter(
        self, 
        name: str, 
        config: Optional[Dict[str, Any]] = None,
        force_new: bool = False
    ) -> EnhancedBaseCrawler:
        """
        Create an adapter instance with comprehensive error handling and caching.
        
        Args:
            name: Adapter name
            config: Optional configuration override
            force_new: Force creation of new instance (bypass cache)
            
        Returns:
            Adapter instance
        """
        start_time = datetime.now()
        
        try:
            normalized_name = self.registry._normalize_name(name)
            
            # Check cache first (if not forcing new)
            if not force_new:
                cached_adapter = self._get_cached_adapter(normalized_name)
                if cached_adapter:
                    self.metrics.cache_hits += 1
                    return cached_adapter
            
            self.metrics.cache_misses += 1
            
            # Get adapter metadata
            metadata = self.registry.get_metadata(normalized_name)
            if not metadata:
                similar = self._find_similar_adapters(normalized_name)
                error_msg = f"Adapter '{name}' not found."
                if similar:
                    error_msg += f" Did you mean: {', '.join(similar)}?"
                raise ValueError(error_msg)
            
            # Load and merge configuration
            base_config = self.config_manager.load_config(normalized_name)
            final_config = ConfigurationHelper.merge_configs(base_config, config or {})
            
            # Select creation strategy
            strategy = self._strategies.get(
                metadata.creation_strategy, 
                self._strategies[self.default_strategy]
            )
            
            # Create adapter
            adapter = strategy.create_adapter(normalized_name, final_config, metadata)
            
            # Cache the adapter
            self._cache_adapter(normalized_name, adapter)
            
            # Update metrics
            self._update_creation_metrics(normalized_name, start_time, True)
            
            logger.info(f"Successfully created adapter: {name}")
            return adapter
            
        except Exception as e:
            self._update_creation_metrics(name, start_time, False, str(e))
            logger.error(f"Failed to create adapter {name}: {e}")
            raise
    
    def _get_cached_adapter(self, name: str) -> Optional[EnhancedBaseCrawler]:
        """Get adapter from cache if available."""
        with self._cache_lock:
            return self._adapter_cache.get(name)
    
    def _cache_adapter(self, name: str, adapter: EnhancedBaseCrawler) -> None:
        """Cache adapter instance."""
        with self._cache_lock:
            self._adapter_cache[name] = adapter
    
    def _find_similar_adapters(self, name: str) -> List[str]:
        """Find similar adapter names using fuzzy matching."""
        all_adapters = self.registry.list_adapters()
        similar = []
        
        for adapter_name in all_adapters:
            # Simple similarity check
            if (name in adapter_name or 
                adapter_name in name or
                abs(len(name) - len(adapter_name)) <= 2):
                similar.append(adapter_name)
        
        return similar[:3]  # Return top 3 matches
    
    def _update_creation_metrics(
        self, 
        name: str, 
        start_time: datetime, 
        success: bool, 
        error: Optional[str] = None
    ) -> None:
        """Update factory metrics."""
        execution_time = (datetime.now() - start_time).total_seconds()
        
        self.metrics.total_created += 1
        self.metrics.last_creation_time = datetime.now()
        
        if success:
            self.metrics.successful_creations += 1
            # Update most requested
            if name not in self.metrics.most_requested_adapters:
                self.metrics.most_requested_adapters[name] = 0
            self.metrics.most_requested_adapters[name] += 1
        else:
            self.metrics.failed_creations += 1
            if error:
                self.metrics.creation_errors.append(f"{name}: {error}")
                # Keep only last 50 errors
                if len(self.metrics.creation_errors) > 50:
                    self.metrics.creation_errors = self.metrics.creation_errors[-50:]
        
        # Update average creation time
        if self.metrics.total_created > 0:
            total_time = self.metrics.average_creation_time * (self.metrics.total_created - 1)
            self.metrics.average_creation_time = (total_time + execution_time) / self.metrics.total_created
    
    # Public API methods
    def list_adapters(self) -> List[str]:
        """List all available adapters."""
        return self.registry.list_adapters()
    
    def list_adapters_by_type(self, adapter_type: AdapterType) -> List[str]:
        """List adapters by type."""
        return self.registry.list_by_type(adapter_type)
    
    def search_adapters(self, query: str) -> List[str]:
        """Search adapters by query."""
        return self.registry.search_adapters(query)
    
    def get_adapter_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive adapter information."""
        metadata = self.registry.get_metadata(name)
        if not metadata:
            return None
        
        return {
            'name': metadata.name,
            'type': metadata.adapter_type.value,
            'base_url': metadata.base_url,
            'currency': metadata.currency,
            'airline_name': metadata.airline_name,
            'description': metadata.description,
            'features': metadata.features,
            'supported_routes': metadata.supported_routes,
            'is_active': metadata.is_active,
            'creation_strategy': metadata.creation_strategy.value
        }
    
    def get_factory_health_status(self) -> Dict[str, Any]:
        """Get comprehensive factory health status."""
        return {
            'factory_id': self.factory_id,
            'status': 'healthy' if self.metrics.failed_creations < self.metrics.successful_creations else 'degraded',
            'metrics': {
                'total_adapters': len(self.registry.list_adapters()),
                'total_created': self.metrics.total_created,
                'success_rate': (
                    self.metrics.successful_creations / max(self.metrics.total_created, 1) * 100
                ),
                'average_creation_time': self.metrics.average_creation_time,
                'cache_hit_rate': (
                    self.metrics.cache_hits / max(self.metrics.cache_hits + self.metrics.cache_misses, 1) * 100
                ),
                'last_creation': self.metrics.last_creation_time.isoformat() if self.metrics.last_creation_time else None
            },
            'most_requested': dict(sorted(
                self.metrics.most_requested_adapters.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            'recent_errors': self.metrics.creation_errors[-10:] if self.metrics.creation_errors else []
        }
    
    def register_adapter(
        self, 
        metadata: AdapterMetadata,
        adapter_class: Optional[Type[EnhancedBaseCrawler]] = None
    ) -> None:
        """Register a new adapter."""
        self.registry.register(metadata, adapter_class)
    
    def clear_cache(self) -> None:
        """Clear adapter cache."""
        with self._cache_lock:
            self._adapter_cache.clear()
        logger.info("Adapter cache cleared")


# Singleton instance management
_factory_instance: Optional[UnifiedAdapterFactory] = None
_factory_lock = threading.Lock()


def get_unified_factory() -> UnifiedAdapterFactory:
    """Get singleton instance of the unified factory."""
    global _factory_instance
    
    if _factory_instance is None:
        with _factory_lock:
            if _factory_instance is None:
                _factory_instance = UnifiedAdapterFactory()
    
    return _factory_instance


# Convenience functions
def create_adapter(
    name: str, 
    config: Optional[Dict[str, Any]] = None,
    force_new: bool = False
) -> EnhancedBaseCrawler:
    """Create an adapter using the unified factory."""
    factory = get_unified_factory()
    return factory.create_adapter(name, config, force_new)


def list_adapters() -> List[str]:
    """List all available adapters."""
    factory = get_unified_factory()
    return factory.list_adapters()


def search_adapters(query: str) -> List[str]:
    """Search adapters by query."""
    factory = get_unified_factory()
    return factory.search_adapters(query)


def get_adapter_info(name: str) -> Optional[Dict[str, Any]]:
    """Get adapter information."""
    factory = get_unified_factory()
    return factory.get_adapter_info(name)


def get_factory_health() -> Dict[str, Any]:
    """Get factory health status."""
    factory = get_unified_factory()
    return factory.get_factory_health_status()


def reset_factory() -> None:
    """Reset factory instance (mainly for testing)."""
    global _factory_instance
    with _factory_lock:
        _factory_instance = None


# Additional configuration management from other factories
class ConfigurationHelper:
    """Enhanced configuration helper with features from other factories."""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """Validate configuration with comprehensive rules."""
        errors = []
        
        # Basic validation from adapter_factory.py
        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return errors
        
        # Required fields validation
        required_fields = ['base_url', 'search_url']
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # URL validation
        if 'base_url' in config:
            base_url = config['base_url']
            if not isinstance(base_url, str) or not base_url.startswith(('http://', 'https://')):
                errors.append("base_url must be a valid URL starting with http:// or https://")
        
        # Rate limiting validation
        if 'rate_limiting' in config:
            rate_config = config['rate_limiting']
            if not isinstance(rate_config, dict):
                errors.append("rate_limiting must be a dictionary")
            else:
                if 'requests_per_minute' in rate_config:
                    rpm = rate_config['requests_per_minute']
                    if not isinstance(rpm, int) or rpm <= 0:
                        errors.append("requests_per_minute must be a positive integer")
        
        # Error handling validation
        if 'error_handling' in config:
            error_config = config['error_handling']
            if not isinstance(error_config, dict):
                errors.append("error_handling must be a dictionary")
            else:
                if 'max_retries' in error_config:
                    max_retries = error_config['max_retries']
                    if not isinstance(max_retries, int) or max_retries < 0:
                        errors.append("max_retries must be a non-negative integer")
        
        return errors
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration with deep merge support."""
        result = base_config.copy()
        
        for key, value in override_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigurationHelper.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Get default configuration template."""
        return {
            'rate_limiting': {
                'requests_per_minute': 10,
                'delay_seconds': 6,
                'burst_limit': 20
            },
            'error_handling': {
                'max_retries': 3,
                'retry_delay': 2,
                'circuit_breaker': {
                    'failure_threshold': 5,
                    'recovery_timeout': 60
                }
            },
            'monitoring': {
                'enable_metrics': True,
                'enable_health_checks': True,
                'log_level': 'INFO'
            },
            'extraction_config': {
                'timeout_seconds': 30,
                'wait_for_load': True,
                'enable_screenshots': False
            }
        } 