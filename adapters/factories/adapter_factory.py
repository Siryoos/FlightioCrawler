"""
Compatibility wrapper for adapter_factory.py

This module maintains backward compatibility while delegating all operations 
to the unified adapter factory. This allows existing code to continue working
while moving to the unified architecture.

DEPRECATED: This module is deprecated in favor of unified_adapter_factory.py
All new code should use the unified factory directly.
"""

import warnings
from typing import Dict, Any, Type, Optional, List, Union

# Import the unified factory
from .unified_adapter_factory import (
    UnifiedAdapterFactory,
    get_unified_factory,
    AdapterMetadata,
    AdapterType,
    FactoryMetrics
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
    "adapter_factory.py is deprecated. Use unified_adapter_factory.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Compatibility aliases
class AdapterRegistry:
    """Compatibility wrapper for AdapterRegistry."""
    
    def __init__(self):
        self._unified_factory = get_unified_factory()
    
    def register(self, name: str, adapter_class: Type[EnhancedBaseCrawler], 
                 config: Optional[Dict[str, Any]] = None, 
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register adapter (compatibility method)."""
        # Create AdapterMetadata from the old format
        adapter_metadata = AdapterMetadata(
            name=name,
            adapter_type=AdapterType.PERSIAN,  # Default
            base_url=metadata.get('base_url', '') if metadata else '',
            currency=metadata.get('currency', 'IRR') if metadata else 'IRR',
            airline_name=metadata.get('airline_name', name) if metadata else name,
            description=metadata.get('description', f'{name} adapter') if metadata else f'{name} adapter',
            features=metadata.get('features', []) if metadata else [],
            config_template=config
        )
        self._unified_factory.register_adapter(adapter_metadata, adapter_class)
    
    def get(self, name: str) -> Optional[Type[EnhancedBaseCrawler]]:
        """Get adapter class (compatibility method)."""
        try:
            # Try to create an instance and return its class
            adapter = self._unified_factory.create_adapter(name)
            return adapter.__class__
        except:
            return None
    
    def list_adapters(self) -> List[str]:
        """List all adapters."""
        return self._unified_factory.list_adapters()
    
    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get adapter metadata."""
        info = self._unified_factory.get_adapter_info(name)
        return info if info else {}
    
    def get_config(self, name: str) -> Dict[str, Any]:
        """Get adapter configuration."""
        info = self._unified_factory.get_adapter_info(name)
        return info.get('config', {}) if info else {}
    
    def list_by_type(self, adapter_type: str) -> List[str]:
        """List adapters by type."""
        if adapter_type == 'persian':
            return self._unified_factory.list_adapters_by_type(AdapterType.PERSIAN)
        elif adapter_type == 'international':
            return self._unified_factory.list_adapters_by_type(AdapterType.INTERNATIONAL)
        elif adapter_type == 'aggregator':
            return self._unified_factory.list_adapters_by_type(AdapterType.AGGREGATOR)
        else:
            return []
    
    def search_adapters(self, query: str) -> List[str]:
        """Search adapters."""
        return self._unified_factory.search_adapters(query)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status."""
        return self._unified_factory.get_factory_health_status()


class ConfigurationManager:
    """Compatibility wrapper for ConfigurationManager."""
    
    def __init__(self, config_dir: str = "config/site_configs"):
        self._unified_factory = get_unified_factory()
        self.config_dir = config_dir
    
    def load_config(self, adapter_name: str) -> Dict[str, Any]:
        """Load configuration."""
        info = self._unified_factory.get_adapter_info(adapter_name)
        return info.get('config', {}) if info else {}
    
    def save_config(self, adapter_name: str, config: Dict[str, Any]) -> None:
        """Save configuration (not implemented in unified factory)."""
        pass
    
    def clear_cache(self) -> None:
        """Clear cache."""
        self._unified_factory.clear_cache()
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status."""
        return {"cache_size": 0, "cache_hits": 0, "cache_misses": 0}


class AdapterFactory:
    """Compatibility wrapper for AdapterFactory."""
    
    def __init__(self, http_session: Optional[Any] = None, config_dir: str = "config/site_configs"):
        self._unified_factory = get_unified_factory()
        self.registry = AdapterRegistry()
        self.config_manager = ConfigurationManager(config_dir)
        self.http_session = http_session
        self.factory_id = "compatibility_wrapper"
        self.creation_stats = {
            "total_created": 0,
            "successful_creations": 0,
            "failed_creations": 0,
            "creation_errors": [],
            "last_creation_time": None,
            "most_requested_adapters": {}
        }
    
    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
        """Create adapter instance."""
        return self._unified_factory.create_adapter(name, config)
    
    def list_available_adapters(self) -> List[str]:
        """List available adapters."""
        return self._unified_factory.list_adapters()
    
    def list_adapters_by_type(self, adapter_type: str) -> List[str]:
        """List adapters by type."""
        return self.registry.list_by_type(adapter_type)
    
    def search_adapters(self, query: str) -> List[str]:
        """Search adapters."""
        return self._unified_factory.search_adapters(query)
    
    def get_adapter_info(self, name: str) -> Dict[str, Any]:
        """Get adapter info."""
        return self._unified_factory.get_adapter_info(name) or {}
    
    def validate_adapter_config(self, name: str, config: Dict[str, Any]) -> List[str]:
        """Validate adapter configuration."""
        return ConfigurationHelper.validate_config(config)
    
    def save_adapter_config(self, name: str, config: Dict[str, Any]) -> None:
        """Save adapter configuration."""
        pass
    
    def reload_adapters(self) -> None:
        """Reload adapters."""
        self._unified_factory.clear_cache()
    
    def get_factory_health_status(self) -> Dict[str, Any]:
        """Get factory health status."""
        return self._unified_factory.get_factory_health_status()
    
    def reset_factory_errors(self) -> None:
        """Reset factory errors."""
        pass


# Global factory instance (compatibility)
_factory = None

def get_factory() -> AdapterFactory:
    """Get the global adapter factory instance."""
    global _factory
    if _factory is None:
        _factory = AdapterFactory()
    return _factory

def create_adapter(name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
    """Create an adapter instance using the global factory."""
    return get_unified_factory().create_adapter(name, config)

def list_adapters() -> List[str]:
    """List all available adapters."""
    return get_unified_factory().list_adapters()

def search_adapters(query: str) -> List[str]:
    """Search adapters by name or features."""
    return get_unified_factory().search_adapters(query)

def get_adapter_info(name: str) -> Dict[str, Any]:
    """Get detailed information about an adapter."""
    return get_unified_factory().get_adapter_info(name) or {}

def get_factory_health() -> Dict[str, Any]:
    """Get health status of the global factory."""
    return get_unified_factory().get_factory_health_status()

def reset_factory_errors() -> None:
    """Reset error state of the global factory."""
    pass
