"""
Shared dependency injection for API modules.

This module provides centralized dependency injection to eliminate 
circular imports between main.py and API v1 modules.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException
import logging

from main_crawler import IranianFlightCrawler
from monitoring import CrawlerMonitor
from rate_limiter import RateLimitManager

logger = logging.getLogger(__name__)


class DependencyProvider:
    """
    Centralized dependency provider to eliminate circular imports.
    
    This class holds references to core application dependencies
    and provides them to API modules without importing main.py.
    """
    
    def __init__(self):
        self._crawler: Optional[IranianFlightCrawler] = None
        self._monitor: Optional[CrawlerMonitor] = None
        self._rate_limit_manager: Optional[RateLimitManager] = None
        self._http_session = None
        self._is_initialized = False
        
    def initialize(
        self,
        crawler: IranianFlightCrawler,
        monitor: CrawlerMonitor,
        rate_limit_manager: Optional[RateLimitManager] = None,
        http_session = None
    ) -> None:
        """Initialize the dependency provider with core dependencies."""
        self._crawler = crawler
        self._monitor = monitor
        self._rate_limit_manager = rate_limit_manager
        self._http_session = http_session
        self._is_initialized = True
        logger.info("Dependency provider initialized")
    
    def is_initialized(self) -> bool:
        """Check if the dependency provider is initialized."""
        return self._is_initialized
    
    def get_crawler(self) -> IranianFlightCrawler:
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
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of all dependencies."""
        status = {
            "dependency_provider": "healthy" if self._is_initialized else "unhealthy",
            "crawler": "healthy" if self._crawler else "unhealthy",
            "monitor": "healthy" if self._monitor else "unhealthy",
            "rate_limit_manager": "healthy" if self._rate_limit_manager else "unknown",
            "http_session": "healthy" if self._http_session and not self._http_session.closed else "unhealthy"
        }
        
        overall_healthy = all(s in ["healthy", "unknown"] for s in status.values())
        status["overall"] = "healthy" if overall_healthy else "degraded"
        
        return status
    
    def shutdown(self) -> None:
        """Shutdown and cleanup dependencies."""
        logger.info("Shutting down dependency provider")
        self._is_initialized = False
        self._crawler = None
        self._monitor = None
        self._rate_limit_manager = None
        self._http_session = None


# Global dependency provider instance
_dependency_provider = DependencyProvider()


def get_dependency_provider() -> DependencyProvider:
    """Get the global dependency provider instance."""
    return _dependency_provider


def initialize_dependencies(
    crawler: IranianFlightCrawler,
    monitor: CrawlerMonitor,
    rate_limit_manager: Optional[RateLimitManager] = None,
    http_session = None
) -> None:
    """Initialize global dependencies."""
    _dependency_provider.initialize(crawler, monitor, rate_limit_manager, http_session)


def shutdown_dependencies() -> None:
    """Shutdown global dependencies."""
    _dependency_provider.shutdown()


# Dependency functions for FastAPI
async def get_crawler() -> IranianFlightCrawler:
    """FastAPI dependency to get crawler instance."""
    return _dependency_provider.get_crawler()


async def get_monitor() -> CrawlerMonitor:
    """FastAPI dependency to get monitor instance."""
    return _dependency_provider.get_monitor()


async def get_rate_limit_manager() -> RateLimitManager:
    """FastAPI dependency to get rate limit manager instance."""
    return _dependency_provider.get_rate_limit_manager()


def get_http_session():
    """Get HTTP session instance."""
    return _dependency_provider.get_http_session()


# Health check dependency
async def check_dependencies_health() -> Dict[str, Any]:
    """Check health of all dependencies."""
    return _dependency_provider.get_health_status() 