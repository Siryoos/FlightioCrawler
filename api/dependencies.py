"""
Shared dependency injection for API modules.

This module provides centralized dependency injection to eliminate 
circular imports between main.py and API v1 modules.
"""

from typing import Optional, Dict, Any, Union
from fastapi import HTTPException
import logging

# Import unified crawler interface
from adapters.unified_crawler_interface import UnifiedCrawlerInterface
from adapters.meta_crawler_factory import MetaCrawlerFactory, get_meta_factory
from monitoring import CrawlerMonitor
from rate_limiter import RateLimitManager

logger = logging.getLogger(__name__)


class DependencyProvider:
    """
    Centralized dependency provider to eliminate circular imports.
    
    This class holds references to core application dependencies
    and provides them to API modules without importing main.py.
    Now supports unified crawler interface for better compatibility.
    """
    
    def __init__(self):
        self._crawler: Optional[UnifiedCrawlerInterface] = None
        self._monitor: Optional[CrawlerMonitor] = None
        self._rate_limit_manager: Optional[RateLimitManager] = None
        self._http_session = None
        self._is_initialized = False
        self._meta_factory: Optional[MetaCrawlerFactory] = None
        
    def initialize(
        self,
        crawler: Union[UnifiedCrawlerInterface, Any],
        monitor: CrawlerMonitor,
        rate_limit_manager: Optional[RateLimitManager] = None,
        http_session = None
    ) -> None:
        """Initialize the dependency provider with core dependencies."""
        # Handle both unified and legacy crawler interfaces
        if isinstance(crawler, UnifiedCrawlerInterface):
            self._crawler = crawler
        else:
            # Legacy crawler - wrap it with unified interface
            self._crawler = self._wrap_legacy_crawler(crawler)
        
        self._monitor = monitor
        self._rate_limit_manager = rate_limit_manager
        self._http_session = http_session
        self._meta_factory = get_meta_factory()
        self._is_initialized = True
        logger.info("Dependency provider initialized with unified crawler interface")
    
    def _wrap_legacy_crawler(self, legacy_crawler) -> UnifiedCrawlerInterface:
        """Wrap a legacy crawler with unified interface."""
        try:
            # Try to detect the crawler type and wrap appropriately
            class_name = type(legacy_crawler).__name__
            
            if 'IranianFlightCrawler' in class_name:
                # This is the main crawler - create a wrapper
                from adapters.requests_to_adapters_bridge import RequestsToAdaptersBridge
                return RequestsToAdaptersBridge(legacy_crawler)
            else:
                # Unknown crawler type - try generic wrapping
                logger.warning(f"Unknown crawler type {class_name}, attempting generic wrapper")
                from adapters.requests_to_adapters_bridge import RequestsToAdaptersBridge
                return RequestsToAdaptersBridge(legacy_crawler)
                
        except Exception as e:
            logger.error(f"Failed to wrap legacy crawler: {e}")
            raise HTTPException(
                status_code=503,
                detail="Failed to initialize crawler interface"
            )
    
    def is_initialized(self) -> bool:
        """Check if the dependency provider is initialized."""
        return self._is_initialized
    
    def get_crawler(self) -> UnifiedCrawlerInterface:
        """Get the crawler instance."""
        if not self._is_initialized or not self._crawler:
            raise HTTPException(
                status_code=503, 
                detail="Crawler service is not available - dependency provider not initialized"
            )
        return self._crawler
    
    def get_monitor(self) -> CrawlerMonitor:
        """Get the monitor instance."""
        if not self._is_initialized or not self._monitor:
            raise HTTPException(
                status_code=503,
                detail="Monitor service is not available - dependency provider not initialized"
            )
        return self._monitor
    
    def get_rate_limit_manager(self) -> RateLimitManager:
        """Get the rate limit manager instance."""
        if not self._rate_limit_manager:
            # Import here to avoid circular imports
            from rate_limiter import get_rate_limit_manager
            self._rate_limit_manager = get_rate_limit_manager()
        return self._rate_limit_manager
    
    def get_http_session(self):
        """Get the HTTP session instance."""
        return self._http_session
    
    def get_meta_factory(self) -> MetaCrawlerFactory:
        """Get the meta crawler factory instance."""
        if not self._meta_factory:
            self._meta_factory = get_meta_factory()
        return self._meta_factory
    
    def create_crawler(self, crawler_name: str, config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
        """Create a new crawler instance using the meta factory."""
        if not self._meta_factory:
            self._meta_factory = get_meta_factory()
        
        return self._meta_factory.create_crawler(crawler_name, config)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of all dependencies."""
        status = {
            "dependency_provider": "healthy" if self._is_initialized else "unhealthy",
            "monitor": "healthy" if self._monitor else "unhealthy",
            "rate_limit_manager": "healthy" if self._rate_limit_manager else "unknown",
            "http_session": "healthy" if self._http_session and not self._http_session.closed else "unhealthy",
            "meta_factory": "healthy" if self._meta_factory else "unknown"
        }
        
        # Check crawler health
        if self._crawler:
            try:
                crawler_health = await self._crawler.get_health_status()
                status["crawler"] = crawler_health.get("status", "unknown")
                status["crawler_details"] = crawler_health
            except Exception as e:
                status["crawler"] = "unhealthy"
                status["crawler_error"] = str(e)
        else:
            status["crawler"] = "unhealthy"
        
        overall_healthy = all(s in ["healthy", "unknown"] for s in status.values() if not s.endswith("_details") and not s.endswith("_error"))
        status["overall"] = "healthy" if overall_healthy else "degraded"
        
        return status
    
    async def shutdown(self) -> None:
        """Shutdown and cleanup dependencies."""
        logger.info("Shutting down dependency provider")
        
        # Cleanup crawler
        if self._crawler:
            try:
                await self._crawler.cleanup_async()
            except Exception as e:
                logger.error(f"Error cleaning up crawler: {e}")
        
        self._is_initialized = False
        self._crawler = None
        self._monitor = None
        self._rate_limit_manager = None
        self._http_session = None
        self._meta_factory = None


# Global dependency provider instance
_dependency_provider = DependencyProvider()


def get_dependency_provider() -> DependencyProvider:
    """Get the global dependency provider instance."""
    return _dependency_provider


def initialize_dependencies(
    crawler: Union[UnifiedCrawlerInterface, Any],
    monitor: CrawlerMonitor,
    rate_limit_manager: Optional[RateLimitManager] = None,
    http_session = None
) -> None:
    """Initialize global dependencies."""
    _dependency_provider.initialize(crawler, monitor, rate_limit_manager, http_session)


async def shutdown_dependencies() -> None:
    """Shutdown global dependencies."""
    await _dependency_provider.shutdown()


# Dependency functions for FastAPI
async def get_crawler() -> UnifiedCrawlerInterface:
    """FastAPI dependency to get crawler instance."""
    return _dependency_provider.get_crawler()


async def get_monitor() -> CrawlerMonitor:
    """FastAPI dependency to get monitor instance."""
    return _dependency_provider.get_monitor()


async def get_rate_limit_manager() -> RateLimitManager:
    """FastAPI dependency to get rate limit manager instance."""
    return _dependency_provider.get_rate_limit_manager()


async def get_http_session():
    """FastAPI dependency to get HTTP session instance."""
    return _dependency_provider.get_http_session()


async def get_meta_factory() -> MetaCrawlerFactory:
    """FastAPI dependency to get meta crawler factory instance."""
    return _dependency_provider.get_meta_factory()


async def create_crawler(crawler_name: str, config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
    """FastAPI dependency to create a new crawler instance."""
    return _dependency_provider.create_crawler(crawler_name, config)


# Health check dependency
async def check_dependencies_health() -> Dict[str, Any]:
    """Check health of all dependencies."""
    return await _dependency_provider.get_health_status()


# Backward compatibility functions
async def get_iranian_flight_crawler() -> UnifiedCrawlerInterface:
    """
    Backward compatibility function for existing code.
    Returns the unified crawler interface.
    """
    return await get_crawler()