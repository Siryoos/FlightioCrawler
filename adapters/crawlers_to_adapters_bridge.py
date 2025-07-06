"""
Crawlers to Adapters Bridge

This module provides a bridge that allows crawlers folder implementations to work
seamlessly with the adapters system. It handles:
- Interface conversion between crawlers and adapters patterns
- Async/sync compatibility
- Data format standardization
- Configuration mapping
- Error handling unification
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from datetime import datetime
import traceback
import importlib.util
import os
from pathlib import Path

from .unified_crawler_interface import (
    UnifiedCrawlerInterface,
    SearchParameters,
    CrawlerResult,
    FlightData,
    CrawlerSystemType,
    CrawlerMetadata
)
from .unified_config_schema import UnifiedConfig
from .unified_persian_text_bridge import get_persian_bridge, integrate_persian_with_crawler
from .async_sync_bridge import get_bridge, AsyncSyncBridge
from .base_adapters.enhanced_error_handler import EnhancedErrorHandler

logger = logging.getLogger(__name__)

class CrawlersToAdaptersBridge(UnifiedCrawlerInterface):
    """
    Bridge that wraps crawlers folder implementations to work with adapters system.
    
    This bridge:
    - Converts crawlers interface to adapters interface
    - Handles async/sync conversion
    - Standardizes data formats
    - Provides unified error handling
    - Maintains compatibility with both systems
    """
    
    def __init__(self, crawler_instance, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the bridge with a crawlers folder crawler.
        
        Args:
            crawler_instance: Instance of a crawlers folder crawler (BaseSiteCrawler)
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        self.crawler_instance = crawler_instance
        self.bridge = get_bridge()
        self.error_handler = EnhancedErrorHandler()
        
        # Set metadata
        self.metadata = CrawlerMetadata(
            system_type=CrawlerSystemType.CRAWLERS,
            adapter_name=f"crawlers_bridge_{type(crawler_instance).__name__}",
            site_name=getattr(crawler_instance, 'site_name', None),
            base_url=getattr(crawler_instance, 'base_url', None)
        )
        
        # Configuration mapping
        self._map_crawlers_config()
        
        # Initialize progress tracking
        self._progress_callbacks = []
        self._last_progress_time = None
        
        # Integrate Persian text processing
        self._integrate_persian_text_processing()
        
        logger.info(f"CrawlersToAdaptersBridge initialized for {type(crawler_instance).__name__}")
    
    def _get_system_type(self) -> CrawlerSystemType:
        """Get the system type."""
        return CrawlerSystemType.CRAWLERS
    
    def _map_crawlers_config(self) -> None:
        """Map configuration from adapters format to crawlers format."""
        try:
            # Get crawler config if available
            if hasattr(self.crawler_instance, 'config'):
                crawler_config = self.crawler_instance.config
                
                # Extract site information
                if 'site_name' in crawler_config:
                    self.metadata.site_name = crawler_config['site_name']
                if 'base_url' in crawler_config:
                    self.metadata.base_url = crawler_config['base_url']
                
                # Map common configuration
                self.config.update({
                    'connection_timeout': crawler_config.get('timeout', 30),
                    'max_retries': crawler_config.get('max_retries', 3),
                    'min_delay': crawler_config.get('min_delay', 1),
                    'headless': crawler_config.get('headless', True),
                    'javascript_enabled': crawler_config.get('javascript_enabled', True),
                    'user_agent': crawler_config.get('user_agent', 'Mozilla/5.0 (compatible; FlightCrawler/1.0)')
                })
                
        except Exception as e:
            logger.warning(f"Failed to map crawler config: {e}")

    def _integrate_persian_text_processing(self) -> None:
        """Integrate Persian text processing with the crawler."""
        try:
            # Get the Persian text bridge
            persian_bridge = get_persian_bridge()
            
            # Integrate with the crawler
            success = integrate_persian_with_crawler(self.crawler_instance, 'crawlers')
            
            if success:
                # Also add Persian processing to the bridge itself
                self.persian_bridge = persian_bridge
                
                # Add convenience methods to the bridge
                self.process_persian_text = lambda text: persian_bridge.process_text(text, 'crawlers').processed_text
                self.parse_persian_airport = lambda text: persian_bridge.process_airport_code(text).value
                self.parse_persian_airline = lambda text: persian_bridge.process_airline_name(text).value
                self.parse_persian_price = lambda text: persian_bridge.parse_persian_price(text).value
                self.parse_persian_duration = lambda text: persian_bridge.parse_persian_duration(text).value
                self.parse_persian_time = lambda text: persian_bridge.parse_persian_time(text).value
                self.convert_jalali_date = lambda text: persian_bridge.convert_jalali_date(text).value
                
                logger.info("Persian text processing integrated with crawler bridge")
            else:
                logger.warning("Failed to integrate Persian text processing with crawler")
                
        except Exception as e:
            logger.warning(f"Persian text integration failed: {e}")
            # Continue without Persian processing
    
    async def _async_crawl_implementation(self, params: SearchParameters) -> CrawlerResult:
        """
        Async implementation that wraps the crawlers folder crawler.
        
        Args:
            params: Unified search parameters
            
        Returns:
            CrawlerResult with standardized data
        """
        start_time = datetime.now()
        
        try:
            self._notify_progress("Starting crawlers folder bridge...")
            
            # Convert unified parameters to crawlers format
            crawlers_params = self._convert_params_to_crawlers_format(params)
            
            self._notify_progress("Converted parameters to crawlers format")
            
            # Execute crawlers folder crawler in async context
            result = await self._execute_crawlers_crawler(crawlers_params)
            
            self._notify_progress("Crawlers folder crawler execution completed")
            
            # Convert result to unified format
            unified_result = self._convert_result_to_unified_format(result, params)
            
            # Set execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            unified_result.execution_time = execution_time
            
            self._notify_progress(f"Bridge completed in {execution_time:.2f} seconds")
            
            return unified_result
            
        except Exception as e:
            logger.error(f"Crawlers bridge error: {e}")
            logger.error(traceback.format_exc())
            
            # Handle error through enhanced error handler
            error_response = await self.error_handler.handle_error(
                error=e,
                context={
                    'bridge_type': 'crawlers_to_adapters',
                    'crawler_class': type(self.crawler_instance).__name__,
                    'params': params.__dict__,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            )
            
            return CrawlerResult(
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
                system_used=CrawlerSystemType.CRAWLERS,
                metadata=error_response
            )
    
    def _convert_params_to_crawlers_format(self, params: SearchParameters) -> Dict[str, Any]:
        """Convert unified parameters to crawlers format."""
        crawlers_params = {
            'origin': params.origin,
            'destination': params.destination,
            'departure_date': params.departure_date,
            'passengers': params.passengers,
            'seat_class': params.seat_class,
            'trip_type': params.trip_type,
        }
        
        # Add return date if available
        if params.return_date:
            crawlers_params['return_date'] = params.return_date
        
        # Add site configuration if available
        if params.site_config:
            crawlers_params['site_config'] = params.site_config
        elif hasattr(self.crawler_instance, 'config'):
            crawlers_params['site_config'] = self.crawler_instance.config
        
        # Add additional parameters
        crawlers_params.update({
            'language': params.language,
            'currency': params.currency,
            'timeout': params.timeout,
            'enable_javascript': params.enable_javascript
        })
        
        return crawlers_params
    
    async def _execute_crawlers_crawler(self, crawlers_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the crawlers folder crawler in async context."""
        try:
            # Check if crawler has async crawl method
            if hasattr(self.crawler_instance, 'crawl') and asyncio.iscoroutinefunction(self.crawler_instance.crawl):
                # Direct async call
                self._notify_progress("Executing async crawl...")
                result = await self.crawler_instance.crawl(crawlers_params)
                return result
            else:
                # Sync crawler - run in executor
                self._notify_progress("Executing sync crawl in executor...")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._execute_sync_crawl,
                    crawlers_params
                )
                return result
                
        except Exception as e:
            logger.error(f"Error executing crawlers crawler: {e}")
            raise
    
    def _execute_sync_crawl(self, crawlers_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute synchronous crawl method."""
        try:
            if hasattr(self.crawler_instance, 'crawl'):
                # If crawl method exists, call it
                if asyncio.iscoroutinefunction(self.crawler_instance.crawl):
                    # Should not happen in this context, but handle it
                    return asyncio.run(self.crawler_instance.crawl(crawlers_params))
                else:
                    return self.crawler_instance.crawl(crawlers_params)
            else:
                # Fallback: try to find a suitable method
                logger.warning("No crawl method found, attempting fallback")
                return []
                
        except Exception as e:
            logger.error(f"Error in sync crawl execution: {e}")
            raise
    
    def _convert_result_to_unified_format(self, result: List[Dict[str, Any]], params: SearchParameters) -> CrawlerResult:
        """Convert crawlers result to unified format."""
        try:
            flights = []
            
            # Convert each flight result to FlightData
            for flight_data in result:
                try:
                    flight = FlightData(
                        airline=flight_data.get('airline', ''),
                        flight_number=flight_data.get('flight_number', ''),
                        origin=flight_data.get('origin', params.origin),
                        destination=flight_data.get('destination', params.destination),
                        departure_date=flight_data.get('departure_date', params.departure_date),
                        departure_time=flight_data.get('departure_time', ''),
                        arrival_date=flight_data.get('arrival_date', ''),
                        arrival_time=flight_data.get('arrival_time', ''),
                        price=flight_data.get('price', 0.0),
                        currency=flight_data.get('currency', params.currency),
                        seat_class=flight_data.get('seat_class', params.seat_class),
                        availability=flight_data.get('availability', 'unknown'),
                        duration=flight_data.get('duration', ''),
                        stops=flight_data.get('stops', 0),
                        aircraft=flight_data.get('aircraft', ''),
                        source_site=self.metadata.site_name or 'unknown',
                        crawl_timestamp=datetime.now(),
                        raw_data=flight_data
                    )
                    flights.append(flight)
                except Exception as e:
                    logger.warning(f"Failed to convert flight data: {e}")
                    continue
            
            return CrawlerResult(
                success=True,
                flights=flights,
                message=f"Successfully retrieved {len(flights)} flights",
                system_used=CrawlerSystemType.CRAWLERS,
                metadata={
                    'total_flights': len(flights),
                    'source_system': 'crawlers',
                    'crawler_class': type(self.crawler_instance).__name__,
                    'site_name': self.metadata.site_name,
                    'search_params': params.__dict__
                }
            )
            
        except Exception as e:
            logger.error(f"Error converting result to unified format: {e}")
            return CrawlerResult(
                success=False,
                error=f"Failed to convert result: {str(e)}",
                system_used=CrawlerSystemType.CRAWLERS
            )
    
    def _notify_progress(self, message: str) -> None:
        """Notify progress to all callbacks."""
        current_time = datetime.now()
        
        # Throttle progress notifications
        if (self._last_progress_time and 
            (current_time - self._last_progress_time).total_seconds() < 0.5):
            return
        
        self._last_progress_time = current_time
        
        for callback in self._progress_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    # Compatibility methods for different systems
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the bridged crawler."""
        try:
            # Check if crawler has health check method
            if hasattr(self.crawler_instance, 'get_health_status'):
                if asyncio.iscoroutinefunction(self.crawler_instance.get_health_status):
                    health = await self.crawler_instance.get_health_status()
                else:
                    health = self.crawler_instance.get_health_status()
            else:
                # Basic health check
                health = {
                    'status': 'healthy',
                    'message': 'Crawler instance available'
                }
            
            # Add bridge-specific information
            health.update({
                'bridge_type': 'crawlers_to_adapters',
                'system_type': self._get_system_type().value,
                'crawler_class': type(self.crawler_instance).__name__,
                'site_name': self.metadata.site_name,
                'created_at': self.metadata.created_at.isoformat()
            })
            
            return health
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'bridge_type': 'crawlers_to_adapters'
            }
    
    async def cleanup_async(self) -> None:
        """Cleanup the bridged crawler."""
        try:
            # Call crawler cleanup if available
            if hasattr(self.crawler_instance, 'cleanup'):
                if asyncio.iscoroutinefunction(self.crawler_instance.cleanup):
                    await self.crawler_instance.cleanup()
                else:
                    self.crawler_instance.cleanup()
            
            # Clear progress callbacks
            self._progress_callbacks.clear()
            
            logger.info("Crawlers bridge cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during crawler bridge cleanup: {e}")
    
    def add_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Add progress callback."""
        if callback not in self._progress_callbacks:
            self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Remove progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    def get_crawler_info(self) -> Dict[str, Any]:
        """Get information about the bridged crawler."""
        return {
            'bridge_type': 'crawlers_to_adapters',
            'original_system': 'crawlers',
            'crawler_class': type(self.crawler_instance).__name__,
            'adapter_name': self.metadata.adapter_name,
            'site_name': self.metadata.site_name,
            'base_url': self.metadata.base_url,
            'created_at': self.metadata.created_at.isoformat(),
            'system_type': self.metadata.system_type.value,
            'config': self.config
        }


class CrawlersSystemWrapper(UnifiedCrawlerInterface):
    """
    Wrapper that makes crawlers system components look like unified adapters.
    
    This wrapper handles:
    - Dynamic loading of crawler classes
    - Factory pattern integration
    - Configuration management
    - Error handling
    """
    
    def __init__(self, crawler_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize wrapper with crawler name and configuration.
        
        Args:
            crawler_name: Name of the crawler to wrap
            config: Configuration dictionary
        """
        super().__init__(config)
        
        self.crawler_name = crawler_name
        self.crawler_instance = None
        self.crawler_factory = None
        
        # Set metadata
        self.metadata = CrawlerMetadata(
            system_type=CrawlerSystemType.CRAWLERS,
            adapter_name=f"crawlers_wrapper_{crawler_name}",
            site_name=crawler_name
        )
        
        # Initialize crawler
        self._initialize_crawler()
    
    def _initialize_crawler(self) -> None:
        """Initialize the crawler instance."""
        try:
            # Import crawler factory
            from crawlers.factories.crawler_factory import SiteCrawlerFactory
            
            # Create site configuration
            site_config = self.config.copy()
            site_config['crawler_name'] = self.crawler_name
            
            # Create crawler instance
            self.crawler_factory = SiteCrawlerFactory()
            self.crawler_instance = self.crawler_factory.create_crawler(site_config)
            
            logger.info(f"Initialized crawler wrapper for {self.crawler_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize crawler wrapper: {e}")
            raise
    
    def _get_system_type(self) -> CrawlerSystemType:
        """Get the system type."""
        return CrawlerSystemType.CRAWLERS
    
    async def _async_crawl_implementation(self, params: SearchParameters) -> CrawlerResult:
        """Async implementation using the crawler instance."""
        if not self.crawler_instance:
            raise RuntimeError("Crawler instance not initialized")
        
        # Create bridge for the crawler instance
        bridge = CrawlersToAdaptersBridge(self.crawler_instance, self.config)
        
        # Use the bridge to perform the crawl
        return await bridge._async_crawl_implementation(params)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status."""
        if not self.crawler_instance:
            return {
                'status': 'unhealthy',
                'error': 'Crawler instance not initialized',
                'wrapper_type': 'crawlers_system'
            }
        
        # Create bridge and get health status
        bridge = CrawlersToAdaptersBridge(self.crawler_instance, self.config)
        health = await bridge.get_health_status()
        health['wrapper_type'] = 'crawlers_system'
        return health
    
    async def cleanup_async(self) -> None:
        """Cleanup the wrapper."""
        if self.crawler_instance:
            bridge = CrawlersToAdaptersBridge(self.crawler_instance, self.config)
            await bridge.cleanup_async()
        
        self.crawler_instance = None
        self.crawler_factory = None
        
        logger.info("Crawler wrapper cleanup completed")


# Factory functions
def create_crawlers_bridge(crawler_instance, config: Optional[Dict[str, Any]] = None) -> CrawlersToAdaptersBridge:
    """
    Create a bridge for a crawlers folder crawler instance.
    
    Args:
        crawler_instance: Instance of a crawlers folder crawler
        config: Optional configuration
        
    Returns:
        CrawlersToAdaptersBridge instance
    """
    return CrawlersToAdaptersBridge(crawler_instance, config)


def create_crawlers_wrapper(crawler_name: str, config: Optional[Dict[str, Any]] = None) -> CrawlersSystemWrapper:
    """
    Create a wrapper for a crawlers system component.
    
    Args:
        crawler_name: Name of the crawler
        config: Configuration dictionary
        
    Returns:
        CrawlersSystemWrapper instance
    """
    return CrawlersSystemWrapper(crawler_name, config)


# Integration with meta factory
def register_crawlers_with_meta_factory(meta_factory) -> None:
    """
    Register crawlers folder implementations with the meta factory.
    
    Args:
        meta_factory: MetaCrawlerFactory instance
    """
    try:
        # Import crawler factory
        from crawlers.factories.crawler_factory import SiteCrawlerFactory
        
        # Get available crawlers
        crawler_factory = SiteCrawlerFactory()
        
        # Register common crawler types
        crawler_types = [
            'javascript_heavy',
            'api_based',
            'form_submission',
            'persian_airline',
            'international_aggregator'
        ]
        
        for crawler_type in crawler_types:
            try:
                # Create wrapper class
                wrapper_class = lambda config, ct=crawler_type: CrawlersSystemWrapper(ct, config)
                
                # Register with meta factory
                meta_factory.register_crawler(
                    name=f"crawlers_{crawler_type}",
                    crawler_class=wrapper_class,
                    system_type=CrawlerSystemType.CRAWLERS,
                    description=f"Crawlers folder {crawler_type} implementation",
                    aliases=[crawler_type]
                )
                
            except Exception as e:
                logger.warning(f"Failed to register crawler type {crawler_type}: {e}")
        
        logger.info("Registered crawlers folder implementations with meta factory")
        
    except Exception as e:
        logger.error(f"Failed to register crawlers with meta factory: {e}") 