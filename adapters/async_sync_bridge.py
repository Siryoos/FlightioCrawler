"""
Async/Sync Compatibility Bridge

This module provides bridges and adapters to handle compatibility between
synchronous operations (requests folder) and asynchronous operations (adapters folder).
It allows seamless integration between different execution models.
"""

import asyncio
import threading
import time
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps
import inspect
from contextlib import contextmanager

from .unified_crawler_interface import (
    UnifiedCrawlerInterface,
    SearchParameters, 
    CrawlerResult,
    FlightData,
    CrawlerSystemType
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

class AsyncSyncBridge:
    """
    Bridge class to handle async/sync compatibility.
    Provides utilities to convert between async and sync operations.
    """
    
    def __init__(self, max_workers: int = 4):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._loop_registry: Dict[int, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()
    
    def run_async_in_sync(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Run an async coroutine in a synchronous context.
        Handles both cases where event loop exists or not.
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we have a running loop, we need to run in a thread
            if loop.is_running():
                return self._run_in_thread(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(coro)
    
    def _run_in_thread(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run coroutine in a separate thread with its own event loop."""
        future = Future()
        
        def run_in_new_loop():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                    future.set_result(result)
                finally:
                    new_loop.close()
            except Exception as e:
                future.set_exception(e)
        
        thread = threading.Thread(target=run_in_new_loop, daemon=True)
        thread.start()
        return future.result()
    
    async def run_sync_in_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run a synchronous function in an async context."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
    
    def sync_to_async(self, func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
        """Decorator to convert sync function to async."""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.run_sync_in_async(func, *args, **kwargs)
        return async_wrapper
    
    def async_to_sync(self, func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., T]:
        """Decorator to convert async function to sync."""
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            coro = func(*args, **kwargs)
            return self.run_async_in_sync(coro)
        return sync_wrapper
    
    def cleanup(self):
        """Cleanup resources."""
        self.thread_pool.shutdown(wait=True)

# Global bridge instance
_global_bridge = AsyncSyncBridge()

def get_bridge() -> AsyncSyncBridge:
    """Get the global async/sync bridge instance."""
    return _global_bridge

class SyncToAsyncCrawlerAdapter(UnifiedCrawlerInterface):
    """
    Adapter that wraps a synchronous crawler to provide async interface.
    Used to make requests folder crawlers work with async systems.
    """
    
    def __init__(self, sync_crawler, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.sync_crawler = sync_crawler
        self.bridge = get_bridge()
        self.metadata.system_type = CrawlerSystemType.REQUESTS
        
        # Extract metadata from sync crawler if available
        if hasattr(sync_crawler, 'get_config'):
            self.config.update(sync_crawler.get_config())
        
        logger.info(f"Created sync-to-async adapter for {type(sync_crawler).__name__}")
    
    def _get_system_type(self) -> CrawlerSystemType:
        return CrawlerSystemType.REQUESTS
    
    async def _async_crawl_implementation(self, params: SearchParameters) -> CrawlerResult:
        """Convert sync crawl to async using bridge."""
        try:
            # Convert unified params to requests format
            url = params.url or self._get_base_url()
            kwargs = params.to_requests_format()
            
            # Run sync crawl in async context
            success, data, message = await self.bridge.run_sync_in_async(
                self.sync_crawler.crawl, url, **kwargs
            )
            
            # Convert result to unified format
            flights = []
            if success and isinstance(data, dict) and "flights" in data:
                for flight_dict in data["flights"]:
                    flights.append(FlightData(
                        airline=flight_dict.get("airline", ""),
                        flight_number=flight_dict.get("flight_number", ""),
                        origin=flight_dict.get("origin", params.origin),
                        destination=flight_dict.get("destination", params.destination),
                        departure_time=flight_dict.get("departure_time", ""),
                        arrival_time=flight_dict.get("arrival_time", ""),
                        price=float(flight_dict.get("price", 0)),
                        currency=flight_dict.get("currency", params.currency),
                        duration_minutes=flight_dict.get("duration_minutes"),
                        seat_class=flight_dict.get("seat_class", params.seat_class),
                        stops=flight_dict.get("stops", 0),
                        source_system=CrawlerSystemType.REQUESTS,
                        raw_data=flight_dict
                    ))
            
            return CrawlerResult(
                success=success,
                flights=flights,
                message=message,
                metadata=data.get("metadata", {}) if isinstance(data, dict) else {}
            )
            
        except Exception as e:
            logger.error(f"Sync-to-async crawl failed: {e}")
            return CrawlerResult(
                success=False,
                error=str(e)
            )
    
    async def cleanup_async(self) -> None:
        """Cleanup sync crawler using bridge."""
        try:
            if hasattr(self.sync_crawler, 'cleanup'):
                await self.bridge.run_sync_in_async(self.sync_crawler.cleanup)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

class AsyncToSyncCrawlerAdapter:
    """
    Adapter that wraps an async crawler to provide sync interface.
    Used to make adapters folder crawlers work with sync systems.
    """
    
    def __init__(self, async_crawler, config: Optional[Dict[str, Any]] = None):
        self.async_crawler = async_crawler
        self.config = config or {}
        self.bridge = get_bridge()
        
        logger.info(f"Created async-to-sync adapter for {type(async_crawler).__name__}")
    
    def crawl(self, url: str, **kwargs) -> tuple:
        """Sync crawl method that wraps async crawler."""
        try:
            # Convert to SearchParameters
            params = SearchParameters(
                origin=kwargs.get("origin", ""),
                destination=kwargs.get("destination", ""),
                departure_date=kwargs.get("departure_date", ""),
                return_date=kwargs.get("return_date"),
                passengers=kwargs.get("passengers", 1),
                seat_class=kwargs.get("seat_class", "economy"),
                url=url
            )
            
            # Run async crawl in sync context
            result = self.bridge.run_async_in_sync(
                self.async_crawler.crawl_async(params)
            )
            
            return result.to_requests_format()
            
        except Exception as e:
            logger.error(f"Async-to-sync crawl failed: {e}")
            return False, {}, str(e)
    
    def validate_url(self, url: str) -> bool:
        """Validate URL."""
        if hasattr(self.async_crawler, 'validate_url'):
            if inspect.iscoroutinefunction(self.async_crawler.validate_url):
                return self.bridge.run_async_in_sync(
                    self.async_crawler.validate_url(url)
                )
            else:
                return self.async_crawler.validate_url(url)
        
        # Default validation
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def cleanup(self) -> None:
        """Cleanup async crawler."""
        try:
            if hasattr(self.async_crawler, 'cleanup_async'):
                self.bridge.run_async_in_sync(self.async_crawler.cleanup_async())
            elif hasattr(self.async_crawler, 'cleanup'):
                if inspect.iscoroutinefunction(self.async_crawler.cleanup):
                    self.bridge.run_async_in_sync(self.async_crawler.cleanup())
                else:
                    self.async_crawler.cleanup()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

class ProgressCallbackBridge:
    """
    Bridge for progress callbacks between sync and async contexts.
    """
    
    def __init__(self):
        self.sync_callbacks: List[Callable[[str], None]] = []
        self.async_callbacks: List[Callable[[str], Coroutine]] = []
        self.bridge = get_bridge()
    
    def add_sync_callback(self, callback: Callable[[str], None]):
        """Add synchronous progress callback."""
        self.sync_callbacks.append(callback)
    
    def add_async_callback(self, callback: Callable[[str], Coroutine]):
        """Add asynchronous progress callback."""
        self.async_callbacks.append(callback)
    
    def notify_sync(self, message: str):
        """Notify all callbacks from sync context."""
        # Call sync callbacks directly
        for callback in self.sync_callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.warning(f"Sync progress callback failed: {e}")
        
        # Call async callbacks via bridge
        if self.async_callbacks:
            try:
                self.bridge.run_async_in_sync(self._notify_async_callbacks(message))
            except Exception as e:
                logger.warning(f"Async progress callbacks failed: {e}")
    
    async def notify_async(self, message: str):
        """Notify all callbacks from async context."""
        # Call async callbacks directly
        for callback in self.async_callbacks:
            try:
                await callback(message)
            except Exception as e:
                logger.warning(f"Async progress callback failed: {e}")
        
        # Call sync callbacks via bridge
        for callback in self.sync_callbacks:
            try:
                await self.bridge.run_sync_in_async(callback, message)
            except Exception as e:
                logger.warning(f"Sync progress callback failed: {e}")
    
    async def _notify_async_callbacks(self, message: str):
        """Helper to notify async callbacks."""
        for callback in self.async_callbacks:
            try:
                await callback(message)
            except Exception as e:
                logger.warning(f"Async progress callback failed: {e}")

class CrawlerMethodBridge:
    """
    Bridge that provides method-level async/sync compatibility.
    Automatically detects and converts method calls.
    """
    
    def __init__(self, crawler_instance):
        self.crawler = crawler_instance
        self.bridge = get_bridge()
        self._method_cache = {}
    
    def __getattr__(self, name):
        """Dynamically provide sync/async versions of methods."""
        if name.startswith('_'):
            return getattr(self.crawler, name)
        
        if name in self._method_cache:
            return self._method_cache[name]
        
        original_method = getattr(self.crawler, name)
        
        if inspect.iscoroutinefunction(original_method):
            # Async method - provide sync wrapper
            sync_method = self.bridge.async_to_sync(original_method)
            async_method = original_method
        else:
            # Sync method - provide async wrapper  
            async_method = self.bridge.sync_to_async(original_method)
            sync_method = original_method
        
        # Create a dual-mode method
        def dual_mode_method(*args, **kwargs):
            # Try to detect context
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # We're in async context, return coroutine
                    return async_method(*args, **kwargs)
            except RuntimeError:
                pass
            
            # Default to sync
            return sync_method(*args, **kwargs)
        
        # Add async version explicitly
        dual_mode_method.async_version = async_method
        dual_mode_method.sync_version = sync_method
        
        self._method_cache[name] = dual_mode_method
        return dual_mode_method

# Utility functions and decorators

def ensure_async(func_or_coro):
    """
    Ensure the result is a coroutine.
    If it's already a coroutine, return as-is.
    If it's a function, convert to async.
    """
    if inspect.iscoroutine(func_or_coro):
        return func_or_coro
    elif inspect.iscoroutinefunction(func_or_coro):
        return func_or_coro
    elif callable(func_or_coro):
        return get_bridge().sync_to_async(func_or_coro)
    else:
        # It's a value, wrap in async function
        async def async_value():
            return func_or_coro
        return async_value()

def ensure_sync(func_or_coro):
    """
    Ensure the result is synchronous.
    If it's a coroutine, run it synchronously.
    If it's a function, return as-is.
    """
    if inspect.iscoroutine(func_or_coro):
        return get_bridge().run_async_in_sync(func_or_coro)
    elif inspect.iscoroutinefunction(func_or_coro):
        return get_bridge().async_to_sync(func_or_coro)
    else:
        return func_or_coro

def adaptive_call(func, *args, **kwargs):
    """
    Adaptively call a function in the appropriate context.
    Automatically handles async/sync based on current context.
    """
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            # Async context
            if inspect.iscoroutinefunction(func):
                return func(*args, **kwargs)  # Returns coroutine
            else:
                return get_bridge().run_sync_in_async(func, *args, **kwargs)
    except RuntimeError:
        # Sync context
        if inspect.iscoroutinefunction(func):
            return get_bridge().run_async_in_sync(func(*args, **kwargs))
        else:
            return func(*args, **kwargs)

def dual_mode(func):
    """
    Decorator that makes a function work in both async and sync contexts.
    """
    if inspect.iscoroutinefunction(func):
        # Already async, add sync version
        sync_version = get_bridge().async_to_sync(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    return func(*args, **kwargs)
            except RuntimeError:
                pass
            return sync_version(*args, **kwargs)
        
        wrapper.async_version = func
        wrapper.sync_version = sync_version
        return wrapper
    else:
        # Sync function, add async version
        async_version = get_bridge().sync_to_async(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    return async_version(*args, **kwargs)
            except RuntimeError:
                pass
            return func(*args, **kwargs)
        
        wrapper.async_version = async_version
        wrapper.sync_version = func
        return wrapper

@contextmanager
def async_context_manager(async_cm):
    """Convert async context manager to sync context manager."""
    bridge = get_bridge()
    
    # Enter
    resource = bridge.run_async_in_sync(async_cm.__aenter__())
    
    try:
        yield resource
    finally:
        # Exit
        bridge.run_async_in_sync(async_cm.__aexit__(None, None, None))

class EventLoopManager:
    """
    Manages event loops across different contexts.
    Ensures proper cleanup and prevents loop conflicts.
    """
    
    def __init__(self):
        self._loops: Dict[int, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()
    
    def get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get existing loop or create new one for current thread."""
        thread_id = threading.get_ident()
        
        with self._lock:
            if thread_id not in self._loops:
                try:
                    loop = asyncio.get_running_loop()
                    self._loops[thread_id] = loop
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._loops[thread_id] = loop
            
            return self._loops[thread_id]
    
    def cleanup_thread_loop(self, thread_id: Optional[int] = None):
        """Cleanup loop for specific thread."""
        if thread_id is None:
            thread_id = threading.get_ident()
        
        with self._lock:
            if thread_id in self._loops:
                loop = self._loops[thread_id]
                if not loop.is_closed():
                    loop.close()
                del self._loops[thread_id]
    
    def cleanup_all(self):
        """Cleanup all managed loops."""
        with self._lock:
            for thread_id, loop in self._loops.items():
                if not loop.is_closed():
                    loop.close()
            self._loops.clear()

# Global event loop manager
_loop_manager = EventLoopManager()

def get_loop_manager() -> EventLoopManager:
    """Get the global event loop manager."""
    return _loop_manager

# Cleanup function
def cleanup_bridge_resources():
    """Cleanup all bridge resources."""
    get_bridge().cleanup()
    get_loop_manager().cleanup_all() 