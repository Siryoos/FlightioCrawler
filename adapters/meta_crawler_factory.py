"""
MetaCrawlerFactory

This module provides a unified factory that consolidates:
- SiteCrawlerFactory (crawlers folder)
- UnifiedAdapterFactory (adapters folder)
- Request system crawler creation

The MetaCrawlerFactory can create crawlers from all three systems
and provides a unified interface for crawler instantiation.
"""

import logging
import importlib
from typing import Dict, Any, Optional, List, Type, Union
from abc import ABC, abstractmethod
from pathlib import Path
import inspect

from .unified_crawler_interface import UnifiedCrawlerInterface, CrawlerSystemType
from .unified_config_schema import UnifiedConfig, load_config
from .async_sync_bridge import (
    SyncToAsyncCrawlerAdapter, 
    AsyncToSyncCrawlerAdapter,
    get_bridge
)

logger = logging.getLogger(__name__)

class CrawlerCreationError(Exception):
    """Errors related to crawler creation."""
    pass

class CrawlerRegistrationError(Exception):
    """Errors related to crawler registration."""
    pass

class CrawlerInfo:
    """Information about a registered crawler."""
    
    def __init__(self, name: str, crawler_class: Type, 
                 system_type: CrawlerSystemType, 
                 config: Optional[Dict[str, Any]] = None,
                 description: Optional[str] = None):
        self.name = name
        self.crawler_class = crawler_class
        self.system_type = system_type
        self.config = config or {}
        self.description = description or f"{name} crawler"
        self.module_path = crawler_class.__module__
        self.creation_count = 0
        self.last_created = None
    
    def __str__(self):
        return f"CrawlerInfo(name={self.name}, type={self.system_type.value}, class={self.crawler_class.__name__})"

class CrawlerRegistry:
    """Registry for managing crawler classes and their metadata."""
    
    def __init__(self):
        self._crawlers: Dict[str, CrawlerInfo] = {}
        self._system_crawlers: Dict[CrawlerSystemType, Dict[str, CrawlerInfo]] = {
            CrawlerSystemType.REQUESTS: {},
            CrawlerSystemType.ADAPTERS: {},
            CrawlerSystemType.CRAWLERS: {},
            CrawlerSystemType.UNIFIED: {}
        }
        self._aliases: Dict[str, str] = {}
    
    def register_crawler(self, name: str, crawler_class: Type, 
                        system_type: CrawlerSystemType,
                        config: Optional[Dict[str, Any]] = None,
                        description: Optional[str] = None,
                        aliases: Optional[List[str]] = None) -> None:
        """Register a crawler class."""
        if name in self._crawlers:
            raise CrawlerRegistrationError(f"Crawler '{name}' already registered")
        
        crawler_info = CrawlerInfo(name, crawler_class, system_type, config, description)
        
        self._crawlers[name] = crawler_info
        self._system_crawlers[system_type][name] = crawler_info
        
        # Register aliases
        if aliases:
            for alias in aliases:
                if alias in self._aliases:
                    raise CrawlerRegistrationError(f"Alias '{alias}' already registered")
                self._aliases[alias] = name
        
        logger.info(f"Registered crawler: {crawler_info}")
    
    def get_crawler_info(self, name: str) -> Optional[CrawlerInfo]:
        """Get crawler information by name or alias."""
        # Check direct name
        if name in self._crawlers:
            return self._crawlers[name]
        
        # Check aliases
        if name in self._aliases:
            return self._crawlers[self._aliases[name]]
        
        return None
    
    def list_crawlers(self, system_type: Optional[CrawlerSystemType] = None) -> List[CrawlerInfo]:
        """List all registered crawlers, optionally filtered by system type."""
        if system_type:
            return list(self._system_crawlers[system_type].values())
        return list(self._crawlers.values())
    
    def get_crawler_names(self, system_type: Optional[CrawlerSystemType] = None) -> List[str]:
        """Get list of crawler names, optionally filtered by system type."""
        crawlers = self.list_crawlers(system_type)
        return [crawler.name for crawler in crawlers]
    
    def unregister_crawler(self, name: str) -> bool:
        """Unregister a crawler."""
        if name not in self._crawlers:
            return False
        
        crawler_info = self._crawlers[name]
        
        # Remove from main registry
        del self._crawlers[name]
        
        # Remove from system registry
        if name in self._system_crawlers[crawler_info.system_type]:
            del self._system_crawlers[crawler_info.system_type][name]
        
        # Remove aliases
        aliases_to_remove = [alias for alias, target in self._aliases.items() if target == name]
        for alias in aliases_to_remove:
            del self._aliases[alias]
        
        logger.info(f"Unregistered crawler: {name}")
        return True
    
    def clear_registry(self) -> None:
        """Clear all registered crawlers."""
        self._crawlers.clear()
        for system_crawlers in self._system_crawlers.values():
            system_crawlers.clear()
        self._aliases.clear()
        logger.info("Cleared crawler registry")

class MetaCrawlerFactory:
    """
    Unified factory for creating crawlers from all three systems.
    
    This factory consolidates:
    - SiteCrawlerFactory (crawlers folder)
    - UnifiedAdapterFactory (adapters folder)
    - Request system crawler creation
    
    Provides a single interface for creating any type of crawler.
    """
    
    def __init__(self, config: Optional[UnifiedConfig] = None):
        self.config = config or load_config()
        self.registry = CrawlerRegistry()
        self.bridge = get_bridge()
        self._auto_discovered = False
        
        # Initialize with default crawlers
        self._register_default_crawlers()
    
    def _register_default_crawlers(self) -> None:
        """Register default crawlers from all systems."""
        try:
            # Register requests system crawlers
            self._register_requests_crawlers()
            
            # Register adapters system crawlers
            self._register_adapters_crawlers()
            
            # Register crawlers system crawlers
            self._register_crawlers_system_crawlers()
            
            logger.info("Default crawlers registered successfully")
        except Exception as e:
            logger.error(f"Failed to register default crawlers: {e}")
    
    def _register_requests_crawlers(self) -> None:
        """Register crawlers from requests folder."""
        try:
            # Try to import and register AdvancedCrawlerRefactored
            from requests.advanced_crawler_refactored import AdvancedCrawlerRefactored
            self.registry.register_crawler(
                name="advanced_crawler_refactored",
                crawler_class=AdvancedCrawlerRefactored,
                system_type=CrawlerSystemType.REQUESTS,
                description="Advanced refactored crawler from requests system",
                aliases=["advanced_crawler", "requests_crawler"]
            )
        except ImportError as e:
            logger.warning(f"Could not import requests crawler: {e}")
    
    def _register_adapters_crawlers(self) -> None:
        """Register crawlers from adapters folder."""
        try:
            # Import and register adapters
            from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
            
            # Register base crawler
            self.registry.register_crawler(
                name="enhanced_base_crawler",
                crawler_class=EnhancedBaseCrawler,
                system_type=CrawlerSystemType.ADAPTERS,
                description="Enhanced base crawler from adapters system"
            )
            
            # Register specific adapters
            self._register_iranian_adapters()
            self._register_international_adapters()
            
        except ImportError as e:
            logger.warning(f"Could not import adapters: {e}")
    
    def _register_iranian_adapters(self) -> None:
        """Register Iranian airline adapters."""
        iranian_adapters = {
            "alibaba": "alibaba_adapter",
            "book_charter": "book_charter_adapter", 
            "book_charter_724": "book_charter_724_adapter",
            "flightio": "flightio_adapter",
            "flytoday": "flytoday_adapter",
            "iran_air_tour": "iran_air_tour_adapter",
            "iran_aseman_air": "iran_aseman_air_adapter",
            "mahan_air": "mahan_air_adapter",
            "mz724": "mz724_adapter",
            "parto_crs": "parto_crs_adapter",
            "parto_ticket": "parto_ticket_adapter",
            "safarmarket": "safarmarket_adapter"
        }
        
        for adapter_name, module_name in iranian_adapters.items():
            try:
                module = importlib.import_module(f"adapters.site_adapters.iranian_airlines.{module_name}")
                
                # Find the adapter class (usually ends with 'Adapter')
                adapter_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if name.endswith('Adapter') and name != 'BaseAdapter':
                        adapter_class = obj
                        break
                
                if adapter_class:
                    self.registry.register_crawler(
                        name=adapter_name,
                        crawler_class=adapter_class,
                        system_type=CrawlerSystemType.ADAPTERS,
                        description=f"Iranian airline adapter: {adapter_name}",
                        aliases=[f"{adapter_name}_adapter", f"iranian_{adapter_name}"]
                    )
                
            except ImportError as e:
                logger.warning(f"Could not import Iranian adapter {adapter_name}: {e}")
    
    def _register_international_adapters(self) -> None:
        """Register international airline adapters."""
        international_adapters = {
            "air_france": "air_france_adapter",
            "british_airways": "british_airways_adapter",
            "emirates": "emirates_adapter",
            "etihad_airways": "etihad_airways_adapter",
            "klm": "klm_adapter",
            "lufthansa": "lufthansa_adapter",
            "pegasus": "pegasus_adapter",
            "qatar_airways": "qatar_airways_adapter",
            "turkish_airlines": "turkish_airlines_adapter"
        }
        
        for adapter_name, module_name in international_adapters.items():
            try:
                module = importlib.import_module(f"adapters.site_adapters.international_airlines.{module_name}")
                
                # Find the adapter class
                adapter_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if name.endswith('Adapter') and name != 'BaseAdapter':
                        adapter_class = obj
                        break
                
                if adapter_class:
                    self.registry.register_crawler(
                        name=adapter_name,
                        crawler_class=adapter_class,
                        system_type=CrawlerSystemType.ADAPTERS,
                        description=f"International airline adapter: {adapter_name}",
                        aliases=[f"{adapter_name}_adapter", f"international_{adapter_name}"]
                    )
                
            except ImportError as e:
                logger.warning(f"Could not import international adapter {adapter_name}: {e}")
    
    def _register_crawlers_system_crawlers(self) -> None:
        """Register crawlers from crawlers folder."""
        try:
            # Try to import from crawlers system
            from crawlers.factories.crawler_factory import SiteCrawlerFactory
            
            # Get available crawler types from the factory
            factory = SiteCrawlerFactory()
            
            # Register each crawler type
            crawler_types = getattr(factory, 'get_available_types', lambda: [])()
            for crawler_type in crawler_types:
                try:
                    # Create a wrapper that uses the factory
                    crawler_class = self._create_crawlers_wrapper(factory, crawler_type)
                    
                    self.registry.register_crawler(
                        name=f"crawlers_{crawler_type}",
                        crawler_class=crawler_class,
                        system_type=CrawlerSystemType.CRAWLERS,
                        description=f"Crawler from crawlers system: {crawler_type}",
                        aliases=[f"site_{crawler_type}", f"legacy_{crawler_type}"]
                    )
                except Exception as e:
                    logger.warning(f"Could not register crawler type {crawler_type}: {e}")
            
        except ImportError as e:
            logger.warning(f"Could not import crawlers factory: {e}")
    
    def _create_crawlers_wrapper(self, factory, crawler_type: str) -> Type:
        """Create a wrapper class for crawlers system."""
        class CrawlerSystemWrapper(UnifiedCrawlerInterface):
            def __init__(self, config: Optional[Dict[str, Any]] = None):
                super().__init__(config)
                self.factory = factory
                self.crawler_type = crawler_type
                self.crawler_instance = None
                self.metadata.system_type = CrawlerSystemType.CRAWLERS
                self.metadata.adapter_name = crawler_type
            
            def _get_system_type(self) -> CrawlerSystemType:
                return CrawlerSystemType.CRAWLERS
            
            async def _async_crawl_implementation(self, params) -> 'CrawlerResult':
                from .unified_crawler_interface import CrawlerResult, FlightData
                
                try:
                    # Create crawler instance if needed
                    if not self.crawler_instance:
                        self.crawler_instance = self.factory.create_crawler(
                            self.crawler_type,
                            params.to_crawlers_format()
                        )
                    
                    # Run crawl
                    if hasattr(self.crawler_instance, 'crawl'):
                        if inspect.iscoroutinefunction(self.crawler_instance.crawl):
                            results = await self.crawler_instance.crawl(params.to_crawlers_format())
                        else:
                            results = await self.bridge.run_sync_in_async(
                                self.crawler_instance.crawl,
                                params.to_crawlers_format()
                            )
                    else:
                        raise CrawlerCreationError(f"Crawler {self.crawler_type} has no crawl method")
                    
                    # Convert results to unified format
                    flights = []
                    if isinstance(results, list):
                        for result in results:
                            if isinstance(result, dict):
                                flights.append(FlightData(
                                    airline=result.get("airline", ""),
                                    flight_number=result.get("flight_number", ""),
                                    origin=result.get("origin", params.origin),
                                    destination=result.get("destination", params.destination),
                                    departure_time=result.get("departure_time", ""),
                                    arrival_time=result.get("arrival_time", ""),
                                    price=float(result.get("price", 0)),
                                    currency=result.get("currency", params.currency),
                                    source_system=CrawlerSystemType.CRAWLERS,
                                    adapter_name=self.crawler_type,
                                    raw_data=result
                                ))
                    
                    return CrawlerResult(
                        success=True,
                        flights=flights,
                        message=f"Crawl completed using {self.crawler_type}"
                    )
                    
                except Exception as e:
                    logger.error(f"Crawlers system crawl failed: {e}")
                    return CrawlerResult(
                        success=False,
                        error=str(e)
                    )
        
        return CrawlerSystemWrapper
    
    def register_crawler(self, name: str, crawler_class: Type,
                        system_type: CrawlerSystemType,
                        config: Optional[Dict[str, Any]] = None,
                        description: Optional[str] = None,
                        aliases: Optional[List[str]] = None) -> None:
        """Register a new crawler class."""
        self.registry.register_crawler(name, crawler_class, system_type, config, description, aliases)
    
    def create_crawler(self, crawler_name: str, 
                      config: Optional[Dict[str, Any]] = None,
                      force_system_type: Optional[CrawlerSystemType] = None) -> UnifiedCrawlerInterface:
        """
        Create a crawler instance by name.
        
        Args:
            crawler_name: Name of the crawler to create
            config: Optional configuration override
            force_system_type: Force creation as specific system type
            
        Returns:
            UnifiedCrawlerInterface instance
        """
        crawler_info = self.registry.get_crawler_info(crawler_name)
        if not crawler_info:
            raise CrawlerCreationError(f"Crawler '{crawler_name}' not found")
        
        # Merge configuration
        merged_config = self.config.to_dict()
        if config:
            merged_config.update(config)
        if crawler_info.config:
            merged_config.update(crawler_info.config)
        
        try:
            # Create crawler instance
            crawler_instance = crawler_info.crawler_class(merged_config)
            
            # Wrap in compatibility adapter if needed
            if force_system_type and force_system_type != crawler_info.system_type:
                crawler_instance = self._create_compatibility_adapter(
                    crawler_instance, crawler_info.system_type, force_system_type
                )
            elif crawler_info.system_type != CrawlerSystemType.UNIFIED:
                # Auto-wrap for unified interface
                crawler_instance = self._create_unified_adapter(
                    crawler_instance, crawler_info.system_type
                )
            
            # Update statistics
            crawler_info.creation_count += 1
            crawler_info.last_created = crawler_instance
            
            logger.info(f"Created crawler: {crawler_name} (type: {crawler_info.system_type.value})")
            return crawler_instance
            
        except Exception as e:
            logger.error(f"Failed to create crawler {crawler_name}: {e}")
            raise CrawlerCreationError(f"Failed to create crawler {crawler_name}: {e}")
    
    def _create_compatibility_adapter(self, crawler_instance, 
                                    source_type: CrawlerSystemType,
                                    target_type: CrawlerSystemType) -> UnifiedCrawlerInterface:
        """Create compatibility adapter between different system types."""
        if source_type == CrawlerSystemType.REQUESTS and target_type == CrawlerSystemType.ADAPTERS:
            return SyncToAsyncCrawlerAdapter(crawler_instance, self.config.to_dict())
        elif source_type == CrawlerSystemType.ADAPTERS and target_type == CrawlerSystemType.REQUESTS:
            return AsyncToSyncCrawlerAdapter(crawler_instance, self.config.to_dict())
        else:
            # For now, just return the original instance
            return crawler_instance
    
    def _create_unified_adapter(self, crawler_instance,
                               source_type: CrawlerSystemType) -> UnifiedCrawlerInterface:
        """Create unified adapter for specific system type."""
        if source_type == CrawlerSystemType.REQUESTS:
            return SyncToAsyncCrawlerAdapter(crawler_instance, self.config.to_dict())
        elif source_type == CrawlerSystemType.ADAPTERS:
            # If it's already a UnifiedCrawlerInterface, return as-is
            if isinstance(crawler_instance, UnifiedCrawlerInterface):
                return crawler_instance
            else:
                # Create async adapter
                return AsyncToSyncCrawlerAdapter(crawler_instance, self.config.to_dict())
        else:
            # For crawlers system, should already be wrapped
            return crawler_instance
    
    def create_crawler_by_site(self, site_name: str,
                              config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
        """Create crawler for a specific site."""
        # Try to find site-specific crawler
        site_crawler_names = [
            site_name,
            f"{site_name}_adapter",
            f"iranian_{site_name}",
            f"international_{site_name}",
            f"crawlers_{site_name}"
        ]
        
        for crawler_name in site_crawler_names:
            crawler_info = self.registry.get_crawler_info(crawler_name)
            if crawler_info:
                return self.create_crawler(crawler_name, config)
        
        raise CrawlerCreationError(f"No crawler found for site: {site_name}")
    
    def list_available_crawlers(self) -> Dict[str, List[str]]:
        """List all available crawlers grouped by system type."""
        result = {}
        
        for system_type in CrawlerSystemType:
            crawlers = self.registry.get_crawler_names(system_type)
            if crawlers:
                result[system_type.value] = crawlers
        
        return result
    
    def get_crawler_info(self, crawler_name: str) -> Optional[CrawlerInfo]:
        """Get information about a specific crawler."""
        return self.registry.get_crawler_info(crawler_name)
    
    def auto_discover_crawlers(self) -> int:
        """Auto-discover and register crawlers from all systems."""
        if self._auto_discovered:
            return 0
        
        discovered_count = 0
        
        # Discover from requests folder
        discovered_count += self._discover_requests_crawlers()
        
        # Discover from adapters folder
        discovered_count += self._discover_adapters_crawlers()
        
        # Discover from crawlers folder
        discovered_count += self._discover_crawlers_system()
        
        self._auto_discovered = True
        logger.info(f"Auto-discovered {discovered_count} crawlers")
        
        return discovered_count
    
    def _discover_requests_crawlers(self) -> int:
        """Discover crawlers from requests folder."""
        # Implementation for discovering requests crawlers
        return 0
    
    def _discover_adapters_crawlers(self) -> int:
        """Discover crawlers from adapters folder."""
        # Implementation for discovering adapters crawlers
        return 0
    
    def _discover_crawlers_system(self) -> int:
        """Discover crawlers from crawlers system."""
        # Implementation for discovering crawlers system crawlers
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get factory statistics."""
        stats = {
            "total_crawlers": len(self.registry._crawlers),
            "crawlers_by_system": {},
            "creation_stats": {},
            "most_used_crawlers": []
        }
        
        # Count by system type
        for system_type in CrawlerSystemType:
            count = len(self.registry._system_crawlers[system_type])
            if count > 0:
                stats["crawlers_by_system"][system_type.value] = count
        
        # Creation statistics
        for name, crawler_info in self.registry._crawlers.items():
            if crawler_info.creation_count > 0:
                stats["creation_stats"][name] = crawler_info.creation_count
        
        # Most used crawlers
        most_used = sorted(
            self.registry._crawlers.items(),
            key=lambda x: x[1].creation_count,
            reverse=True
        )[:5]
        
        stats["most_used_crawlers"] = [
            {"name": name, "count": info.creation_count}
            for name, info in most_used if info.creation_count > 0
        ]
        
        return stats
    
    def cleanup(self) -> None:
        """Cleanup factory resources."""
        self.registry.clear_registry()
        self.bridge.cleanup()
        logger.info("MetaCrawlerFactory cleaned up")

# Global factory instance
_meta_factory = None

def get_meta_factory(config: Optional[UnifiedConfig] = None) -> MetaCrawlerFactory:
    """Get the global MetaCrawlerFactory instance."""
    global _meta_factory
    if _meta_factory is None:
        _meta_factory = MetaCrawlerFactory(config)
    return _meta_factory

def create_crawler(crawler_name: str, 
                  config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
    """Create a crawler using the global factory."""
    return get_meta_factory().create_crawler(crawler_name, config)

def list_available_crawlers() -> Dict[str, List[str]]:
    """List all available crawlers."""
    return get_meta_factory().list_available_crawlers()

def create_crawler_by_site(site_name: str,
                          config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
    """Create crawler for a specific site."""
    return get_meta_factory().create_crawler_by_site(site_name, config) 