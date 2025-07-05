"""
Compatibility wrapper for enhanced_adapter_factory.py

This module maintains backward compatibility while delegating all operations 
to the unified adapter factory. This allows existing code to continue working
while moving to the unified architecture.

DEPRECATED: This module is deprecated in favor of unified_adapter_factory.py
All new code should use the unified factory directly.
"""

import warnings
from typing import Dict, Any, Type, Optional, List, Union, Protocol
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# Import the unified factory
from .unified_adapter_factory import (
    UnifiedAdapterFactory,
    get_unified_factory,
    AdapterMetadata as UnifiedAdapterMetadata,
    AdapterType as UnifiedAdapterType,
    CreationStrategy
)

# Import types for compatibility
from adapters.base_adapters import (
    EnhancedBaseCrawler,
    EnhancedInternationalAdapter,
    EnhancedPersianAdapter,
    ConfigurationHelper,
    ErrorReportingHelper,
)

# Show deprecation warning
warnings.warn(
    "enhanced_adapter_factory.py is deprecated. Use unified_adapter_factory.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Compatibility aliases
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
        pass

class ConfigurationBuilder:
    """Configuration builder (compatibility wrapper)."""
    
    def __init__(self):
        self._config = {}
    
    def with_base_config(self, base_config: Dict[str, Any]) -> "ConfigurationBuilder":
        """Add base configuration."""
        self._config.update(base_config)
        return self
    
    def with_rate_limiting(self, requests_per_second: int = 2, burst_limit: int = 5, 
                          cooldown_period: int = 60) -> "ConfigurationBuilder":
        """Add rate limiting configuration."""
        self._config['rate_limiting'] = {
            'requests_per_second': requests_per_second,
            'burst_limit': burst_limit,
            'cooldown_period': cooldown_period
        }
        return self
    
    def with_error_handling(self, max_retries: int = 3, retry_delay: int = 5, 
                           circuit_breaker: Optional[Dict[str, Any]] = None) -> "ConfigurationBuilder":
        """Add error handling configuration."""
        self._config['error_handling'] = {
            'max_retries': max_retries,
            'retry_delay': retry_delay,
            'circuit_breaker': circuit_breaker or {}
        }
        return self
    
    def with_extraction_config(self, extraction_config: Dict[str, Any]) -> "ConfigurationBuilder":
        """Add extraction configuration."""
        self._config['extraction_config'] = extraction_config
        return self
    
    def with_monitoring(self, monitoring_config: Dict[str, Any]) -> "ConfigurationBuilder":
        """Add monitoring configuration."""
        self._config['monitoring'] = monitoring_config
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
    
    def with_custom_config(self, key: str, value: Any) -> "ConfigurationBuilder":
        """Add custom configuration."""
        self._config[key] = value
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build configuration."""
        return self._config.copy()

class DirectCreationStrategy:
    """Direct creation strategy (compatibility wrapper)."""
    
    def create_adapter(self, name: str, config: Dict[str, Any], metadata: AdapterMetadata) -> EnhancedBaseCrawler:
        """Create adapter using direct instantiation."""
        return get_unified_factory().create_adapter(name, config)

class ModuleCreationStrategy:
    """Module creation strategy (compatibility wrapper)."""
    
    def create_adapter(self, name: str, config: Dict[str, Any], metadata: AdapterMetadata) -> EnhancedBaseCrawler:
        """Create adapter by importing from module."""
        return get_unified_factory().create_adapter(name, config)

class AbstractAdapterFactory(ABC):
    """Abstract adapter factory (compatibility wrapper)."""
    
    def __init__(self, creation_strategy: AdapterCreationStrategy):
        self.creation_strategy = creation_strategy
        self.config_builder = ConfigurationBuilder()
    
    @abstractmethod
    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create an adapter instance."""
        pass
    
    @abstractmethod
    def get_supported_adapters(self) -> List[str]:
        """Get list of supported adapter names."""
        pass
    
    def build_config(self, metadata: AdapterMetadata, custom_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build configuration."""
        builder = self.config_builder.with_metadata(metadata)
        if custom_config:
            for key, value in custom_config.items():
                builder = builder.with_custom_config(key, value)
        return builder.build()

class PersianAdapterFactory(AbstractAdapterFactory):
    """Persian adapter factory (compatibility wrapper)."""
    
    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._unified_factory = get_unified_factory()
    
    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create Persian adapter."""
        return self._unified_factory.create_adapter(name, config)
    
    def get_supported_adapters(self) -> List[str]:
        """Get supported Persian adapters."""
        return self._unified_factory.list_adapters_by_type(UnifiedAdapterType.PERSIAN)

class InternationalAdapterFactory(AbstractAdapterFactory):
    """International adapter factory (compatibility wrapper)."""
    
    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._unified_factory = get_unified_factory()
    
    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create international adapter."""
        return self._unified_factory.create_adapter(name, config)
    
    def get_supported_adapters(self) -> List[str]:
        """Get supported international adapters."""
        return self._unified_factory.list_adapters_by_type(UnifiedAdapterType.INTERNATIONAL)

class AggregatorAdapterFactory(AbstractAdapterFactory):
    """Aggregator adapter factory (compatibility wrapper)."""
    
    def __init__(self, creation_strategy: AdapterCreationStrategy):
        super().__init__(creation_strategy)
        self._unified_factory = get_unified_factory()
    
    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create aggregator adapter."""
        return self._unified_factory.create_adapter(name, config)
    
    def get_supported_adapters(self) -> List[str]:
        """Get supported aggregator adapters."""
        return self._unified_factory.list_adapters_by_type(UnifiedAdapterType.AGGREGATOR)

class EnhancedAdapterFactory:
    """Enhanced adapter factory (compatibility wrapper)."""
    
    def __init__(self, creation_strategy: Optional[AdapterCreationStrategy] = None):
        self.creation_strategy = creation_strategy or ModuleCreationStrategy()
        self._unified_factory = get_unified_factory()
        
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
    
    def create_adapter(self, name: str, adapter_type: Optional[AdapterType] = None,
                      config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create an adapter."""
        return self._unified_factory.create_adapter(name, config)
    
    def _detect_adapter_type(self, name: str) -> AdapterType:
        """Auto-detect adapter type."""
        return AdapterType.PERSIAN  # Default
    
    def list_all_adapters(self) -> Dict[AdapterType, List[str]]:
        """List all adapters by type."""
        return {
            AdapterType.PERSIAN: self._unified_factory.list_adapters_by_type(UnifiedAdapterType.PERSIAN),
            AdapterType.INTERNATIONAL: self._unified_factory.list_adapters_by_type(UnifiedAdapterType.INTERNATIONAL),
            AdapterType.AGGREGATOR: self._unified_factory.list_adapters_by_type(UnifiedAdapterType.AGGREGATOR),
        }
    
    def get_adapter_info(self, name: str) -> Optional[AdapterMetadata]:
        """Get adapter info."""
        info = self._unified_factory.get_adapter_info(name)
        if info:
            return AdapterMetadata(
                name=info.get('name', name),
                adapter_type=AdapterType.PERSIAN,  # Default
                base_url=info.get('base_url', ''),
                currency=info.get('currency', 'IRR'),
                airline_name=info.get('airline_name', name),
                description=info.get('description', ''),
                features=info.get('features', [])
            )
        return None
    
    def register_custom_adapter(self, metadata: AdapterMetadata, 
                               config_template: Optional[Dict[str, Any]] = None) -> None:
        """Register custom adapter."""
        # Convert to unified metadata
        unified_metadata = UnifiedAdapterMetadata(
            name=metadata.name,
            adapter_type=UnifiedAdapterType.PERSIAN,  # Default conversion
            base_url=metadata.base_url,
            currency=metadata.currency,
            airline_name=metadata.airline_name,
            description=metadata.description,
            features=metadata.features,
            supported_routes=metadata.supported_routes,
            config_template=config_template
        )
        self._unified_factory.register_adapter(unified_metadata)

# Singleton instance
_factory_instance: Optional[EnhancedAdapterFactory] = None

def get_enhanced_factory() -> EnhancedAdapterFactory:
    """Get singleton instance of the enhanced factory."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = EnhancedAdapterFactory()
    return _factory_instance

# Convenience functions
def create_adapter(name: str, adapter_type: Optional[AdapterType] = None,
                  config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
    """Create an adapter using the enhanced factory."""
    return get_unified_factory().create_adapter(name, config)

def list_adapters() -> Dict[AdapterType, List[str]]:
    """List all available adapters."""
    factory = get_enhanced_factory()
    return factory.list_all_adapters()

def get_adapter_metadata(name: str) -> Optional[AdapterMetadata]:
    """Get metadata for an adapter."""
    factory = get_enhanced_factory()
    return factory.get_adapter_info(name)
