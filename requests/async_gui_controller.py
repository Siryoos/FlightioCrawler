"""
Async GUI Controller

This module provides an async version of the GUI controller that integrates
with the unified crawler interface and adapters system. It handles:
- Async crawler operations
- Unified interface integration
- Progress reporting
- Error handling
- State management
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Import unified crawler interface
from adapters.unified_crawler_interface import (
    UnifiedCrawlerInterface,
    SearchParameters,
    CrawlerResult,
    CrawlerSystemType
)
from adapters.meta_crawler_factory import get_meta_factory, MetaCrawlerFactory
from adapters.requests_to_adapters_bridge import RequestsToAdaptersBridge

logger = logging.getLogger(__name__)


@dataclass
class AsyncCrawlState:
    """State information for async crawling operations."""
    is_crawling: bool = False
    current_url: str = ""
    start_time: Optional[datetime] = None
    task: Optional[asyncio.Task] = None
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None


class AsyncCrawlerGUIController:
    """
    Async GUI Controller that integrates with the unified crawler interface.
    
    This controller provides:
    - Async crawler operations
    - Unified interface integration
    - Progress reporting
    - Error handling
    - State management
    """
    
    def __init__(self, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Initialize the async GUI controller.
        
        Args:
            event_loop: Optional event loop to use
        """
        self.event_loop = event_loop or asyncio.new_event_loop()
        self.meta_factory = get_meta_factory()
        self.current_crawler: Optional[UnifiedCrawlerInterface] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # State management
        self.crawl_state = AsyncCrawlState()
        self.current_config = {
            "prefer_javascript": True,
            "timeout": 60,
            "headless": True,
            "save_dir": "./crawled_pages",
            "max_retries": 3,
            "min_delay": 1
        }
        
        # Observers and callbacks
        self.view_observers: List[Callable] = []
        self.progress_observers: List[Callable] = []
        self.state_observers: List[Callable] = []
        
        # Statistics
        self.crawl_statistics = {
            "total_crawls": 0,
            "successful_crawls": 0,
            "failed_crawls": 0,
            "average_crawl_time": 0.0,
            "total_crawl_time": 0.0
        }
        
        # Command history
        self.command_history: List[Dict[str, Any]] = []
        
        # Results storage
        self.crawl_results: Optional[Dict[str, Any]] = None
        
        logger.info("AsyncCrawlerGUIController initialized")
    
    def set_event_loop(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async operations."""
        self.event_loop = event_loop
    
    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the current event loop."""
        return self.event_loop
    
    # Observer Management
    
    def add_view_observer(self, observer: Callable) -> None:
        """Add a view observer."""
        if observer not in self.view_observers:
            self.view_observers.append(observer)
    
    def remove_view_observer(self, observer: Callable) -> None:
        """Remove a view observer."""
        if observer in self.view_observers:
            self.view_observers.remove(observer)
    
    def add_progress_observer(self, observer: Callable) -> None:
        """Add a progress observer."""
        if observer not in self.progress_observers:
            self.progress_observers.append(observer)
    
    def add_state_observer(self, observer: Callable) -> None:
        """Add a state observer."""
        if observer not in self.state_observers:
            self.state_observers.append(observer)
    
    def notify_view_observers(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all view observers."""
        for observer in self.view_observers:
            try:
                observer(event_type, data)
            except Exception as e:
                logger.error(f"Error notifying view observer: {e}")
    
    def notify_progress_observers(self, message: str, percentage: float = 0.0) -> None:
        """Notify all progress observers."""
        for observer in self.progress_observers:
            try:
                observer(message, percentage)
            except Exception as e:
                logger.error(f"Error notifying progress observer: {e}")
    
    def notify_state_observers(self, new_state: str, old_state: str) -> None:
        """Notify all state observers."""
        for observer in self.state_observers:
            try:
                observer(new_state, old_state)
            except Exception as e:
                logger.error(f"Error notifying state observer: {e}")
    
    # State Management
    
    def get_state(self) -> str:
        """Get current crawling state."""
        if self.crawl_state.is_crawling:
            return "crawling"
        elif self.crawl_state.error:
            return "error"
        elif self.crawl_results:
            return "completed"
        else:
            return "ready"
    
    def is_crawling(self) -> bool:
        """Check if currently crawling."""
        return self.crawl_state.is_crawling
    
    # Configuration Management
    
    def set_crawler_config(self, config: Dict[str, Any]) -> None:
        """Set crawler configuration."""
        self.current_config.update(config)
        self.notify_view_observers("config_changed", {"config": self.current_config})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """Get current crawler configuration."""
        return self.current_config.copy()
    
    # URL Management
    
    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            
            if not parsed.scheme:
                return False, "URL must include protocol (http:// or https://)"
            
            if not parsed.netloc:
                return False, "URL must include domain name"
            
            if parsed.scheme not in ["http", "https"]:
                return False, "URL must use http or https protocol"
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"
    
    def set_url(self, url: str) -> bool:
        """Set and validate URL."""
        is_valid, error = self.validate_url(url)
        if is_valid:
            # Normalize URL
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            self.crawl_state.current_url = url
            self.notify_view_observers("url_changed", {"url": url})
            return True
        else:
            self.notify_view_observers("url_error", {"error": error})
            return False
    
    def get_url(self) -> str:
        """Get current URL."""
        return self.crawl_state.current_url
    
    # Crawler Management
    
    async def create_crawler(self, crawler_name: str = "default", config: Optional[Dict[str, Any]] = None) -> UnifiedCrawlerInterface:
        """
        Create a unified crawler instance.
        
        Args:
            crawler_name: Name of the crawler to create
            config: Optional configuration override
            
        Returns:
            UnifiedCrawlerInterface instance
        """
        try:
            # Merge configuration
            final_config = self.current_config.copy()
            if config:
                final_config.update(config)
            
            # Create crawler using meta factory
            crawler = self.meta_factory.create_crawler(crawler_name, final_config)
            
            # Set up progress callbacks
            crawler.add_progress_callback(self._crawler_progress_callback)
            
            self.current_crawler = crawler
            logger.info(f"Created crawler: {crawler_name}")
            
            return crawler
            
        except Exception as e:
            logger.error(f"Failed to create crawler: {e}")
            raise
    
    def _crawler_progress_callback(self, message: str) -> None:
        """Internal callback for crawler progress updates."""
        self.crawl_state.message = message
        self.notify_progress_observers(message)
    
    async def get_crawler_suggestions(self, url: str) -> Dict[str, Any]:
        """Get crawler configuration suggestions for a URL."""
        try:
            # For now, provide basic suggestions
            # This could be enhanced with actual URL analysis
            return {
                "recommended_strategy": "javascript_heavy",
                "javascript_required": True,
                "suggested_config": {
                    "prefer_javascript": True,
                    "timeout": 60,
                    "headless": True,
                    "max_retries": 3
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get crawler suggestions: {e}")
            return {"error": str(e)}
    
    # Crawling Operations
    
    async def start_crawl_async(self, url: str = None, config: Dict[str, Any] = None) -> bool:
        """
        Start async crawling operation.
        
        Args:
            url: URL to crawl (optional, uses current URL if not provided)
            config: Configuration override (optional)
            
        Returns:
            True if crawl started successfully
        """
        if self.crawl_state.is_crawling:
            self.notify_view_observers("crawl_error", {"error": "Already crawling"})
            return False
        
        # Use provided URL or current URL
        target_url = url or self.crawl_state.current_url
        if not target_url:
            self.notify_view_observers("crawl_error", {"error": "No URL specified"})
            return False
        
        # Validate URL
        is_valid, error = self.validate_url(target_url)
        if not is_valid:
            self.notify_view_observers("crawl_error", {"error": error})
            return False
        
        # Set crawling state
        self.crawl_state.is_crawling = True
        self.crawl_state.current_url = target_url
        self.crawl_state.start_time = datetime.now()
        self.crawl_state.error = None
        self.crawl_state.progress = 0.0
        
        # Notify observers
        self.notify_view_observers("crawl_started", {"url": target_url})
        
        # Create and start crawl task
        try:
            self.crawl_state.task = asyncio.create_task(
                self._crawl_worker_async(target_url, config)
            )
            return True
            
        except Exception as e:
            self.crawl_state.is_crawling = False
            self.crawl_state.error = str(e)
            self.notify_view_observers("crawl_error", {"error": str(e)})
            return False
    
    async def _crawl_worker_async(self, url: str, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Async worker for crawling operations.
        
        Args:
            url: URL to crawl
            config: Optional configuration
        """
        start_time = datetime.now()
        
        try:
            # Update statistics
            self.crawl_statistics["total_crawls"] += 1
            
            # Create crawler
            crawler = await self.create_crawler(config=config)
            
            # Create search parameters
            search_params = SearchParameters(
                url=url,
                timeout=self.current_config.get("timeout", 60),
                enable_javascript=self.current_config.get("prefer_javascript", True)
            )
            
            # Perform crawl
            result = await crawler.crawl_async(search_params)
            
            crawl_time = (datetime.now() - start_time).total_seconds()
            
            if result.success:
                # Update statistics
                self.crawl_statistics["successful_crawls"] += 1
                self._update_average_crawl_time(crawl_time)
                
                # Store results
                self.crawl_results = {
                    "url": url,
                    "flights": [flight.to_dict() for flight in result.flights],
                    "metadata": result.metadata,
                    "crawl_time": crawl_time,
                    "system_used": result.system_used.value
                }
                
                # Add to command history
                self.command_history.append({
                    "type": "crawl",
                    "url": url,
                    "timestamp": time.time(),
                    "success": True,
                    "data": self.crawl_results
                })
                
                # Notify observers
                self.notify_view_observers("crawl_completed", {
                    "url": url,
                    "data": self.crawl_results,
                    "crawl_time": crawl_time
                })
                
            else:
                # Update statistics
                self.crawl_statistics["failed_crawls"] += 1
                
                # Add to command history
                self.command_history.append({
                    "type": "crawl",
                    "url": url,
                    "timestamp": time.time(),
                    "success": False,
                    "error": result.error
                })
                
                # Set error state
                self.crawl_state.error = result.error
                
                # Notify observers
                self.notify_view_observers("crawl_failed", {
                    "url": url,
                    "error": result.error,
                    "crawl_time": crawl_time
                })
                
        except Exception as e:
            # Update statistics
            self.crawl_statistics["failed_crawls"] += 1
            
            # Set error state
            self.crawl_state.error = str(e)
            
            # Notify observers
            self.notify_view_observers("crawl_error", {
                "url": url,
                "error": str(e),
                "crawl_time": (datetime.now() - start_time).total_seconds()
            })
            
        finally:
            # Reset crawling state
            self.crawl_state.is_crawling = False
            self.crawl_state.task = None
            
            # Cleanup crawler
            if self.current_crawler:
                try:
                    await self.current_crawler.cleanup_async()
                except Exception as e:
                    logger.error(f"Error cleaning up crawler: {e}")
    
    def start_crawl(self, url: str = None, config: Dict[str, Any] = None) -> bool:
        """
        Start crawling operation (sync wrapper for async operation).
        
        Args:
            url: URL to crawl
            config: Configuration override
            
        Returns:
            True if crawl started successfully
        """
        try:
            # Run async operation in event loop
            if self.event_loop.is_running():
                # Create task
                task = asyncio.create_task(self.start_crawl_async(url, config))
                return True
            else:
                # Run in event loop
                return self.event_loop.run_until_complete(self.start_crawl_async(url, config))
                
        except Exception as e:
            logger.error(f"Failed to start crawl: {e}")
            self.notify_view_observers("crawl_error", {"error": str(e)})
            return False
    
    async def stop_crawl_async(self) -> bool:
        """
        Stop current crawling operation.
        
        Returns:
            True if stopped successfully
        """
        if not self.crawl_state.is_crawling:
            return False
        
        try:
            # Cancel task if running
            if self.crawl_state.task and not self.crawl_state.task.done():
                self.crawl_state.task.cancel()
                try:
                    await self.crawl_state.task
                except asyncio.CancelledError:
                    pass
            
            # Reset state
            self.crawl_state.is_crawling = False
            self.crawl_state.task = None
            
            # Notify observers
            self.notify_view_observers("crawl_stopped", {})
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping crawl: {e}")
            return False
    
    def stop_crawl(self) -> bool:
        """
        Stop current crawling operation (sync wrapper).
        
        Returns:
            True if stopped successfully
        """
        try:
            if self.event_loop.is_running():
                asyncio.create_task(self.stop_crawl_async())
                return True
            else:
                return self.event_loop.run_until_complete(self.stop_crawl_async())
                
        except Exception as e:
            logger.error(f"Failed to stop crawl: {e}")
            return False
    
    # Statistics and Results
    
    def _update_average_crawl_time(self, crawl_time: float) -> None:
        """Update average crawl time statistics."""
        self.crawl_statistics["total_crawl_time"] += crawl_time
        self.crawl_statistics["average_crawl_time"] = (
            self.crawl_statistics["total_crawl_time"] / self.crawl_statistics["successful_crawls"]
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get crawling statistics."""
        return self.crawl_statistics.copy()
    
    def get_results(self) -> Optional[Dict[str, Any]]:
        """Get current crawl results."""
        return self.crawl_results
    
    def get_command_history(self) -> List[Dict[str, Any]]:
        """Get command history."""
        return self.command_history.copy()
    
    # Cleanup
    
    async def cleanup_async(self) -> None:
        """Cleanup resources."""
        try:
            # Stop any running crawls
            if self.crawl_state.is_crawling:
                await self.stop_crawl_async()
            
            # Cleanup current crawler
            if self.current_crawler:
                await self.current_crawler.cleanup_async()
            
            # Shutdown executor
            self.executor.shutdown(wait=False)
            
            # Clear observers
            self.view_observers.clear()
            self.progress_observers.clear()
            self.state_observers.clear()
            
            logger.info("AsyncCrawlerGUIController cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def cleanup(self) -> None:
        """Cleanup resources (sync wrapper)."""
        try:
            if self.event_loop.is_running():
                asyncio.create_task(self.cleanup_async())
            else:
                self.event_loop.run_until_complete(self.cleanup_async())
                
        except Exception as e:
            logger.error(f"Failed to cleanup: {e}")


# Thread-safe wrapper for GUI integration
class ThreadSafeAsyncController:
    """
    Thread-safe wrapper for AsyncCrawlerGUIController.
    
    This wrapper handles the integration between the GUI thread
    and the async event loop thread.
    """
    
    def __init__(self):
        self.controller = None
        self.event_loop = None
        self.loop_thread = None
        self._start_event_loop()
    
    def _start_event_loop(self) -> None:
        """Start the event loop in a separate thread."""
        def run_event_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.controller = AsyncCrawlerGUIController(self.event_loop)
            self.event_loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        self.loop_thread.start()
        
        # Wait for controller to be ready
        while self.controller is None:
            time.sleep(0.01)
    
    def run_async(self, coro):
        """Run async coroutine in the event loop."""
        if self.event_loop:
            future = asyncio.run_coroutine_threadsafe(coro, self.event_loop)
            return future.result()
        else:
            raise RuntimeError("Event loop not available")
    
    def start_crawl(self, url: str = None, config: Dict[str, Any] = None) -> bool:
        """Start crawling operation."""
        return self.run_async(self.controller.start_crawl_async(url, config))
    
    def stop_crawl(self) -> bool:
        """Stop crawling operation."""
        return self.run_async(self.controller.stop_crawl_async())
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.controller:
            self.run_async(self.controller.cleanup_async())
        
        if self.event_loop:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        
        if self.loop_thread:
            self.loop_thread.join(timeout=5)
    
    def __getattr__(self, name):
        """Delegate attribute access to the controller."""
        return getattr(self.controller, name) 