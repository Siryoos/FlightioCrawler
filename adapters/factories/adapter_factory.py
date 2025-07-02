"""
Adapter Factory for creating flight crawling adapters.
"""

from typing import Dict, Any, Type, Optional, List
from abc import ABC
import importlib
import logging

from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
from adapters.base_adapters.enhanced_international_adapter import EnhancedInternationalAdapter
from adapters.base_adapters.enhanced_persian_adapter import EnhancedPersianAdapter


logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for adapter classes."""
    
    def __init__(self):
        self._adapters: Dict[str, Type[EnhancedBaseCrawler]] = {}
        self._adapter_configs: Dict[str, Dict[str, Any]] = {}
    
    def register(
        self, 
        name: str, 
        adapter_class: Type[EnhancedBaseCrawler],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register an adapter class."""
        self._adapters[name.lower()] = adapter_class
        if config:
            self._adapter_configs[name.lower()] = config
    
    def get(self, name: str) -> Optional[Type[EnhancedBaseCrawler]]:
        """Get adapter class by name."""
        return self._adapters.get(name.lower())
    
    def get_config(self, name: str) -> Dict[str, Any]:
        """Get adapter config by name."""
        return self._adapter_configs.get(name.lower(), {})
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter names."""
        return list(self._adapters.keys())


class AdapterFactory:
    """
    Factory for creating flight crawling adapters.
    
    This factory eliminates the need to import and instantiate
    adapters manually, providing a clean interface for adapter creation.
    """
    
    def __init__(self):
        self.registry = AdapterRegistry()
        self._register_default_adapters()
    
    def _register_default_adapters(self) -> None:
        """Register default adapters."""
        # International airlines
        self._register_adapter("lufthansa", "international", {
            "base_url": "https://www.lufthansa.com",
            "currency": "EUR"
        })
        self._register_adapter("air_france", "international", {
            "base_url": "https://www.airfrance.com",
            "currency": "EUR"
        })
        self._register_adapter("british_airways", "international", {
            "base_url": "https://www.britishairways.com",
            "currency": "GBP"
        })
        self._register_adapter("emirates", "international", {
            "base_url": "https://www.emirates.com",
            "currency": "AED"
        })
        self._register_adapter("turkish_airlines", "international", {
            "base_url": "https://www.turkishairlines.com",
            "currency": "TRY"
        })
        self._register_adapter("qatar_airways", "international", {
            "base_url": "https://www.qatarairways.com",
            "currency": "QAR"
        })
        
        # Iranian airlines
        self._register_adapter("iran_air", "persian", {
            "base_url": "https://www.iranair.com",
            "currency": "IRR"
        })
        self._register_adapter("mahan_air", "persian", {
            "base_url": "https://www.mahan.aero",
            "currency": "IRR"
        })
        self._register_adapter("aseman", "persian", {
            "base_url": "https://www.iaa.ir",
            "currency": "IRR"
        })
        self._register_adapter("caspian", "persian", {
            "base_url": "https://www.caspian.aero",
            "currency": "IRR"
        })
        self._register_adapter("qeshm_air", "persian", {
            "base_url": "https://www.qeshmairlines.com",
            "currency": "IRR"
        })
        
        # Aggregators
        self._register_adapter("alibaba", "persian", {
            "base_url": "https://www.alibaba.ir",
            "currency": "IRR",
            "is_aggregator": True
        })
        self._register_adapter("flightio", "persian", {
            "base_url": "https://flightio.com",
            "currency": "IRR",
            "is_aggregator": True
        })
        self._register_adapter("flytoday", "persian", {
            "base_url": "https://www.flytoday.ir",
            "currency": "IRR",
            "is_aggregator": True
        })
    
    def _register_adapter(
        self, 
        name: str, 
        adapter_type: str,
        default_config: Dict[str, Any]
    ) -> None:
        """Register an adapter with dynamic class creation."""
        
        # Create adapter class dynamically
        if adapter_type == "international":
            base_class = EnhancedInternationalAdapter
        elif adapter_type == "persian":
            base_class = EnhancedPersianAdapter
        else:
            base_class = EnhancedBaseCrawler
        
        # Create dynamic adapter class
        adapter_class = type(
            f"{name.title().replace('_', '')}Adapter",
            (base_class,),
            {
                "_get_base_url": lambda self: default_config["base_url"],
                "_extract_currency": lambda self, element, config: default_config.get("currency", "USD"),
                "__module__": "adapters.dynamic"
            }
        )
        
        self.registry.register(name, adapter_class, default_config)
    
    def create_adapter(
        self, 
        name: str, 
        config: Optional[Dict[str, Any]] = None
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
        adapter_class = self.registry.get(name)
        
        if not adapter_class:
            raise ValueError(f"Adapter '{name}' not found in registry")
        
        # Merge default config with provided config
        default_config = self.registry.get_config(name)
        final_config = {**default_config, **(config or {})}
        
        # Create and return adapter instance
        return adapter_class(final_config)
    
    def create_adapter_from_module(
        self, 
        module_path: str,
        class_name: str,
        config: Dict[str, Any]
    ) -> EnhancedBaseCrawler:
        """
        Create adapter from a specific module.
        
        This allows loading custom adapters not in the registry.
        
        Args:
            module_path: Full module path (e.g., 'adapters.custom.my_adapter')
            class_name: Class name in the module
            config: Adapter configuration
            
        Returns:
            Adapter instance
        """
        try:
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            
            if not issubclass(adapter_class, EnhancedBaseCrawler):
                raise ValueError(f"{class_name} must inherit from EnhancedBaseCrawler")
            
            return adapter_class(config)
            
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load adapter: {e}")
            raise
    
    def list_available_adapters(self) -> List[str]:
        """List all available adapter names."""
        return self.registry.list_adapters()
    
    def get_adapter_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific adapter."""
        adapter_class = self.registry.get(name)
        config = self.registry.get_config(name)
        
        if not adapter_class:
            return {}
        
        return {
            "name": name,
            "class": adapter_class.__name__,
            "base_class": adapter_class.__bases__[0].__name__,
            "config": config,
            "is_persian": issubclass(adapter_class, EnhancedPersianAdapter),
            "is_international": issubclass(adapter_class, EnhancedInternationalAdapter)
        }


# Global factory instance
adapter_factory = AdapterFactory()


# Convenience functions
def create_adapter(name: str, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseCrawler:
    """Create an adapter using the global factory."""
    return adapter_factory.create_adapter(name, config)


def list_adapters() -> List[str]:
    """List all available adapters."""
    return adapter_factory.list_available_adapters() 