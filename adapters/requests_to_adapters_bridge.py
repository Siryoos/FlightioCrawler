"""
Requests to Adapters Bridge

This module provides a bridge that allows requests folder crawlers to work
seamlessly with the adapters system. It handles:
- Interface conversion between requests and adapters patterns
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

from .unified_crawler_interface import (
    UnifiedCrawlerInterface,
    SearchParameters,
    CrawlerResult,
    FlightData,
    CrawlerSystemType,
    CrawlerMetadata
)
from .unified_config_schema import UnifiedConfig
from .async_sync_bridge import get_bridge, AsyncSyncBridge
from .base_adapters.enhanced_error_handler import EnhancedErrorHandler
from .unified_persian_text_bridge import get_persian_bridge, integrate_persian_with_crawler

logger = logging.getLogger(__name__)

class RequestsToAdaptersBridge(UnifiedCrawlerInterface):
    """
    Bridge that wraps requests folder crawlers to work with adapters system.
    
    This bridge:
    - Converts requests interface to adapters interface
    - Handles async/sync conversion
    - Standardizes data formats
    - Provides unified error handling
    - Maintains compatibility with both systems
    """
    
    def __init__(self, requests_crawler, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the bridge with a requests crawler.
        
        Args:
            requests_crawler: Instance of a requests folder crawler
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        self.requests_crawler = requests_crawler
        self.bridge = get_bridge()
        self.error_handler = EnhancedErrorHandler()
        
        # Set metadata
        self.metadata = CrawlerMetadata(
            system_type=CrawlerSystemType.REQUESTS,
            adapter_name=f"requests_bridge_{type(requests_crawler).__name__}",
            site_name=getattr(requests_crawler, 'site_name', None),
            base_url=getattr(requests_crawler, 'base_url', None)
        )
        
        # Configuration mapping
        self._map_requests_config()
        
        # Initialize progress tracking
        self._progress_callbacks = []
        self._last_progress_time = None
        
        # Integrate Persian text processing
        self._integrate_persian_text_processing()
        
        logger.info(f"RequestsToAdaptersBridge initialized for {type(requests_crawler).__name__}")
    
    def _get_system_type(self) -> CrawlerSystemType:
        """Get the system type."""
        return CrawlerSystemType.REQUESTS
    
    def _map_requests_config(self) -> None:
        """Map requests crawler configuration to adapters format."""
        try:
            # Extract configuration from requests crawler
            if hasattr(self.requests_crawler, 'config'):
                requests_config = self.requests_crawler.config
            elif hasattr(self.requests_crawler, 'get_config'):
                requests_config = self.requests_crawler.get_config()
            else:
                requests_config = {}
            
            # Map common configuration keys
            config_mapping = {
                'timeout': 'connection_timeout',
                'max_retries': 'max_retries',
                'delay': 'min_delay',
                'user_agent': 'user_agent',
                'headless': 'headless',
                'window_size': 'window_size',
                'enable_cookies': 'enable_cookies',
                'verify_ssl': 'verify_ssl'
            }
            
            for requests_key, adapters_key in config_mapping.items():
                if requests_key in requests_config:
                    self.config[adapters_key] = requests_config[requests_key]
            
            # Map browser options
            if 'browser_options' in requests_config:
                self.config['browser_options'] = requests_config['browser_options']
            
            # Map headers
            if 'headers' in requests_config:
                self.config['default_headers'] = requests_config['headers']
            
            logger.debug("Configuration mapped from requests to adapters format")
            
        except Exception as e:
            logger.warning(f"Failed to map requests configuration: {e}")

    def _integrate_persian_text_processing(self) -> None:
        """Integrate Persian text processing with the requests crawler."""
        try:
            # Get the Persian text bridge
            persian_bridge = get_persian_bridge()
            
            # Integrate with the requests crawler
            success = integrate_persian_with_crawler(self.requests_crawler, 'requests')
            
            if success:
                # Also add Persian processing to the bridge itself
                self.persian_bridge = persian_bridge
                
                # Add convenience methods to the bridge
                self.process_persian_text = lambda text: persian_bridge.process_text(text, 'requests').processed_text
                self.parse_persian_airline = lambda text: persian_bridge.process_airline_name(text).value
                self.parse_persian_price = lambda text: persian_bridge.parse_persian_price(text).value
                self.parse_persian_duration = lambda text: persian_bridge.parse_persian_duration(text).value
                self.parse_persian_time = lambda text: persian_bridge.parse_persian_time(text).value
                self.convert_jalali_date = lambda text: persian_bridge.convert_jalali_date(text).value
                
                logger.info("Persian text processing integrated with requests crawler bridge")
            else:
                logger.warning("Failed to integrate Persian text processing with requests crawler")
                
        except Exception as e:
            logger.warning(f"Persian text integration failed: {e}")
            # Continue without Persian processing
    
    async def _async_crawl_implementation(self, params: SearchParameters) -> CrawlerResult:
        """
        Async implementation that wraps the requests crawler.
        
        Args:
            params: Unified search parameters
            
        Returns:
            CrawlerResult with standardized data
        """
        start_time = datetime.now()
        
        try:
            self._notify_progress("Starting requests crawler bridge...")
            
            # Convert unified parameters to requests format
            url = params.url or self._get_base_url() or self._build_url_from_params(params)
            kwargs = self._convert_params_to_requests_format(params)
            
            self._notify_progress("Converted parameters to requests format")
            
            # Execute requests crawler in async context
            result = await self._execute_requests_crawler(url, kwargs)
            
            self._notify_progress("Requests crawler execution completed")
            
            # Convert result to unified format
            unified_result = self._convert_result_to_unified_format(result, params)
            
            # Set execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            unified_result.execution_time = execution_time
            
            self._notify_progress(f"Bridge completed in {execution_time:.2f} seconds")
            
            return unified_result
            
        except Exception as e:
            error_msg = f"RequestsToAdaptersBridge crawl failed: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            
            # Handle error with enhanced error handler
            error_info = self.error_handler.handle_error(e, context={
                'bridge': 'requests_to_adapters',
                'crawler': type(self.requests_crawler).__name__,
                'params': params.to_dict()
            })
            
            return CrawlerResult(
                success=False,
                error=error_msg,
                execution_time=(datetime.now() - start_time).total_seconds(),
                system_used=CrawlerSystemType.REQUESTS,
                metadata=error_info
            )
    
    def _convert_params_to_requests_format(self, params: SearchParameters) -> Dict[str, Any]:
        """Convert unified parameters to requests format."""
        kwargs = {
            'origin': params.origin,
            'destination': params.destination,
            'departure_date': params.departure_date,
            'passengers': params.passengers,
            'seat_class': params.seat_class,
            'timeout': params.timeout,
            'enable_javascript': params.enable_javascript
        }
        
        # Add optional parameters
        if params.return_date:
            kwargs['return_date'] = params.return_date
        
        # Add system-specific parameters
        if params.extraction_config:
            kwargs.update(params.extraction_config)
        
        return kwargs
    
    def _build_url_from_params(self, params: SearchParameters) -> str:
        """Build URL from search parameters if not provided."""
        base_url = self.metadata.base_url
        if not base_url:
            # Try to get base URL from requests crawler
            if hasattr(self.requests_crawler, 'base_url'):
                base_url = self.requests_crawler.base_url
            elif hasattr(self.requests_crawler, 'get_base_url'):
                base_url = self.requests_crawler.get_base_url()
            else:
                base_url = "https://example.com"  # Fallback
        
        return base_url
    
    async def _execute_requests_crawler(self, url: str, kwargs: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Execute the requests crawler in async context."""
        try:
            # Check if the crawler has an async crawl method
            if hasattr(self.requests_crawler, 'crawl_async'):
                return await self.requests_crawler.crawl_async(url, **kwargs)
            elif hasattr(self.requests_crawler, 'crawl'):
                # Run sync crawl in async context
                return await self.bridge.run_sync_in_async(
                    self.requests_crawler.crawl, url, **kwargs
                )
            else:
                raise AttributeError("Requests crawler has no crawl method")
                
        except Exception as e:
            logger.error(f"Failed to execute requests crawler: {e}")
            return False, {}, str(e)
    
    def _convert_result_to_unified_format(self, result: Tuple[bool, Dict[str, Any], str],
                                        params: SearchParameters) -> CrawlerResult:
        """Convert requests result to unified format."""
        success, data, message = result
        
        flights = []
        
        if success and isinstance(data, dict):
            # Extract flights from data
            flights_data = data.get('flights', [])
            if not flights_data and 'results' in data:
                flights_data = data['results']
            
            # Convert each flight to FlightData
            for flight_dict in flights_data:
                if isinstance(flight_dict, dict):
                    flight = self._convert_flight_dict_to_flight_data(flight_dict, params)
                    flights.append(flight)
        
        # Extract metadata
        metadata = data.get('metadata', {}) if isinstance(data, dict) else {}
        metadata.update({
            'bridge_type': 'requests_to_adapters',
            'original_system': 'requests',
            'crawler_class': type(self.requests_crawler).__name__
        })
        
        return CrawlerResult(
            success=success,
            flights=flights,
            message=message,
            metadata=metadata,
            system_used=CrawlerSystemType.REQUESTS
        )
    
    def _convert_flight_dict_to_flight_data(self, flight_dict: Dict[str, Any],
                                          params: SearchParameters) -> FlightData:
        """Convert flight dictionary to FlightData object."""
        return FlightData(
            airline=flight_dict.get('airline', ''),
            flight_number=flight_dict.get('flight_number', ''),
            origin=flight_dict.get('origin', params.origin),
            destination=flight_dict.get('destination', params.destination),
            departure_time=flight_dict.get('departure_time', ''),
            arrival_time=flight_dict.get('arrival_time', ''),
            price=float(flight_dict.get('price', 0)),
            currency=flight_dict.get('currency', params.currency),
            duration_minutes=flight_dict.get('duration_minutes'),
            seat_class=flight_dict.get('seat_class', params.seat_class),
            aircraft_type=flight_dict.get('aircraft_type'),
            stops=flight_dict.get('stops', 0),
            booking_url=flight_dict.get('booking_url'),
            available_seats=flight_dict.get('available_seats'),
            is_refundable=flight_dict.get('is_refundable', False),
            source_system=CrawlerSystemType.REQUESTS,
            adapter_name=self.metadata.adapter_name,
            raw_data=flight_dict
        )
    
    # Adapters system interface methods
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the bridged crawler."""
        try:
            # Check if requests crawler has health check
            if hasattr(self.requests_crawler, 'get_health_status'):
                if asyncio.iscoroutinefunction(self.requests_crawler.get_health_status):
                    health = await self.requests_crawler.get_health_status()
                else:
                    health = await self.bridge.run_sync_in_async(
                        self.requests_crawler.get_health_status
                    )
            else:
                # Basic health check
                health = {
                    'status': 'healthy',
                    'message': 'Requests crawler is accessible'
                }
            
            # Add bridge-specific information
            health.update({
                'bridge_type': 'requests_to_adapters',
                'original_system': 'requests',
                'crawler_class': type(self.requests_crawler).__name__,
                'adapter_name': self.metadata.adapter_name,
                'created_at': self.metadata.created_at.isoformat()
            })
            
            return health
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'bridge_type': 'requests_to_adapters',
                'crawler_class': type(self.requests_crawler).__name__
            }
    
    def _get_base_url(self) -> str:
        """Get base URL from requests crawler."""
        if self.metadata.base_url:
            return self.metadata.base_url
        
        # Try to get from requests crawler
        if hasattr(self.requests_crawler, 'base_url'):
            return self.requests_crawler.base_url
        elif hasattr(self.requests_crawler, 'get_base_url'):
            try:
                return self.requests_crawler.get_base_url()
            except Exception:
                pass
        
        return ""
    
    async def _validate_specific_parameters(self, search_params: Dict[str, Any]) -> None:
        """Validate search parameters specific to requests system."""
        # Check if requests crawler has validation
        if hasattr(self.requests_crawler, 'validate_parameters'):
            if asyncio.iscoroutinefunction(self.requests_crawler.validate_parameters):
                await self.requests_crawler.validate_parameters(search_params)
            else:
                await self.bridge.run_sync_in_async(
                    self.requests_crawler.validate_parameters, search_params
                )
        elif hasattr(self.requests_crawler, 'validate_url'):
            # Basic URL validation
            url = search_params.get('url') or self._get_base_url()
            if url:
                if asyncio.iscoroutinefunction(self.requests_crawler.validate_url):
                    is_valid = await self.requests_crawler.validate_url(url)
                else:
                    is_valid = await self.bridge.run_sync_in_async(
                        self.requests_crawler.validate_url, url
                    )
                
                if not is_valid:
                    raise ValueError(f"Invalid URL: {url}")
    
    # Requests system interface methods (for backward compatibility)
    
    def crawl(self, url: str, **kwargs) -> Tuple[bool, Dict[str, Any], str]:
        """Sync crawl method for requests system compatibility."""
        try:
            # Convert to SearchParameters
            params = SearchParameters(
                origin=kwargs.get('origin', ''),
                destination=kwargs.get('destination', ''),
                departure_date=kwargs.get('departure_date', ''),
                return_date=kwargs.get('return_date'),
                passengers=kwargs.get('passengers', 1),
                seat_class=kwargs.get('seat_class', 'economy'),
                url=url,
                timeout=kwargs.get('timeout', 30),
                enable_javascript=kwargs.get('enable_javascript', True)
            )
            
            # Run async crawl in sync context
            result = self.bridge.run_async_in_sync(self.crawl_async(params))
            
            return result.to_requests_format()
            
        except Exception as e:
            logger.error(f"Sync crawl failed: {e}")
            return False, {}, str(e)
    
    def validate_url(self, url: str) -> bool:
        """Validate URL using requests crawler."""
        try:
            if hasattr(self.requests_crawler, 'validate_url'):
                if asyncio.iscoroutinefunction(self.requests_crawler.validate_url):
                    return self.bridge.run_async_in_sync(
                        self.requests_crawler.validate_url(url)
                    )
                else:
                    return self.requests_crawler.validate_url(url)
            else:
                # Basic URL validation
                from urllib.parse import urlparse
                parsed = urlparse(url)
                return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    async def cleanup_async(self) -> None:
        """Cleanup resources."""
        try:
            # Cleanup requests crawler
            if hasattr(self.requests_crawler, 'cleanup_async'):
                await self.requests_crawler.cleanup_async()
            elif hasattr(self.requests_crawler, 'cleanup'):
                if asyncio.iscoroutinefunction(self.requests_crawler.cleanup):
                    await self.requests_crawler.cleanup()
                else:
                    await self.bridge.run_sync_in_async(self.requests_crawler.cleanup)
            
            # Cleanup bridge resources
            self._progress_callbacks.clear()
            
            logger.info("RequestsToAdaptersBridge cleanup completed")
            
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    def cleanup(self) -> None:
        """Sync cleanup method."""
        try:
            self.bridge.run_async_in_sync(self.cleanup_async())
        except Exception as e:
            logger.warning(f"Sync cleanup failed: {e}")
    
    # Progress tracking methods
    
    def _notify_progress(self, message: str) -> None:
        """Notify progress to callbacks."""
        try:
            current_time = datetime.now()
            if (self._last_progress_time is None or 
                (current_time - self._last_progress_time).total_seconds() > 0.5):
                
                for callback in self._progress_callbacks:
                    try:
                        callback(message)
                    except Exception as e:
                        logger.warning(f"Progress callback failed: {e}")
                
                self._last_progress_time = current_time
                
        except Exception as e:
            logger.warning(f"Progress notification failed: {e}")
    
    def add_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Add progress callback."""
        if callback not in self._progress_callbacks:
            self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Remove progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    # Configuration methods
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update bridge configuration."""
        super().update_config(config)
        
        # Update requests crawler config if possible
        if hasattr(self.requests_crawler, 'update_config'):
            try:
                requests_config = self._convert_config_to_requests_format(config)
                self.requests_crawler.update_config(requests_config)
            except Exception as e:
                logger.warning(f"Failed to update requests crawler config: {e}")
    
    def _convert_config_to_requests_format(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert adapters config to requests format."""
        requests_config = {}
        
        # Map common configuration keys
        config_mapping = {
            'connection_timeout': 'timeout',
            'max_retries': 'max_retries',
            'min_delay': 'delay',
            'user_agent': 'user_agent',
            'headless': 'headless',
            'window_size': 'window_size',
            'enable_cookies': 'enable_cookies',
            'verify_ssl': 'verify_ssl',
            'default_headers': 'headers'
        }
        
        for adapters_key, requests_key in config_mapping.items():
            if adapters_key in config:
                requests_config[requests_key] = config[adapters_key]
        
        return requests_config
    
    def get_crawler_info(self) -> Dict[str, Any]:
        """Get information about the bridged crawler."""
        return {
            'bridge_type': 'requests_to_adapters',
            'original_system': 'requests',
            'crawler_class': type(self.requests_crawler).__name__,
            'adapter_name': self.metadata.adapter_name,
            'site_name': self.metadata.site_name,
            'base_url': self.metadata.base_url,
            'created_at': self.metadata.created_at.isoformat(),
            'system_type': self.metadata.system_type.value
        }

# Factory function for creating bridges
def create_requests_to_adapters_bridge(requests_crawler, 
                                     config: Optional[Dict[str, Any]] = None) -> RequestsToAdaptersBridge:
    """
    Create a RequestsToAdaptersBridge instance.
    
    Args:
        requests_crawler: Instance of a requests folder crawler
        config: Optional configuration dictionary
        
    Returns:
        RequestsToAdaptersBridge instance
    """
    return RequestsToAdaptersBridge(requests_crawler, config)

# Utility functions for batch operations
def create_multiple_bridges(crawlers: List[Any], 
                          config: Optional[Dict[str, Any]] = None) -> List[RequestsToAdaptersBridge]:
    """Create multiple bridges from a list of requests crawlers."""
    bridges = []
    
    for crawler in crawlers:
        try:
            bridge = create_requests_to_adapters_bridge(crawler, config)
            bridges.append(bridge)
        except Exception as e:
            logger.error(f"Failed to create bridge for {type(crawler).__name__}: {e}")
    
    return bridges

def validate_requests_crawler(crawler) -> bool:
    """Validate that a crawler is compatible with the bridge."""
    required_methods = ['crawl']
    
    for method in required_methods:
        if not hasattr(crawler, method):
            logger.error(f"Crawler missing required method: {method}")
            return False
    
    return True 