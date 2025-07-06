"""
Async GUI Observer

This module provides async-compatible GUI observers that work with the
unified crawler interface and adapters system. It handles:
- Async event handling
- Unified interface integration
- Progress reporting
- Error handling
- View updates
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Union, Awaitable
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

# Import from existing observer module
from .crawler_gui_observer import EventType, Event, Observer

logger = logging.getLogger(__name__)


class AsyncEventType(Enum):
    """Extended event types for async operations."""
    ASYNC_CRAWL_STARTED = "async_crawl_started"
    ASYNC_CRAWL_COMPLETED = "async_crawl_completed"
    ASYNC_CRAWL_FAILED = "async_crawl_failed"
    ASYNC_CRAWL_ERROR = "async_crawl_error"
    ASYNC_PROGRESS_UPDATE = "async_progress_update"
    ASYNC_STATE_CHANGED = "async_state_changed"
    UNIFIED_INTERFACE_EVENT = "unified_interface_event"
    BRIDGE_EVENT = "bridge_event"
    ADAPTER_EVENT = "adapter_event"


@dataclass
class AsyncEvent:
    """Enhanced event for async operations."""
    event_type: Union[EventType, AsyncEventType]
    data: Dict[str, Any]
    source: str = "async_gui"
    timestamp: datetime = None
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AsyncObserver(ABC):
    """
    Abstract base class for async observers.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.is_active = True
        self.event_handlers: Dict[Union[EventType, AsyncEventType], Callable] = {}
        
    @abstractmethod
    async def handle_event_async(self, event: AsyncEvent) -> None:
        """Handle event asynchronously."""
        pass
    
    def handle_event_sync(self, event: AsyncEvent) -> None:
        """Handle event synchronously (fallback)."""
        try:
            asyncio.create_task(self.handle_event_async(event))
        except Exception as e:
            logger.error(f"Error creating async task for event handling: {e}")
    
    def add_event_handler(self, event_type: Union[EventType, AsyncEventType], handler: Callable) -> None:
        """Add event handler for specific event type."""
        self.event_handlers[event_type] = handler
    
    def remove_event_handler(self, event_type: Union[EventType, AsyncEventType]) -> None:
        """Remove event handler."""
        if event_type in self.event_handlers:
            del self.event_handlers[event_type]
    
    def set_active(self, active: bool) -> None:
        """Set observer active state."""
        self.is_active = active


class AsyncGUIObserver(AsyncObserver):
    """
    Async GUI observer for unified crawler interface integration.
    
    This observer handles:
    - Async crawler events
    - Unified interface events
    - Bridge events
    - View updates
    """
    
    def __init__(self, name: str, view_component: object, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Initialize async GUI observer.
        
        Args:
            name: Observer name
            view_component: GUI component to update
            event_loop: Optional event loop to use
        """
        super().__init__(name)
        self.view_component = view_component
        self.event_loop = event_loop or asyncio.get_event_loop()
        
        # Set up default event handlers
        self.setup_default_handlers()
        
        logger.info(f"AsyncGUIObserver '{name}' initialized")
    
    def setup_default_handlers(self) -> None:
        """Set up default event handlers."""
        # Standard event handlers
        self.event_handlers.update({
            EventType.CRAWL_STARTED: self.handle_crawl_started,
            EventType.CRAWL_COMPLETED: self.handle_crawl_completed,
            EventType.CRAWL_FAILED: self.handle_crawl_failed,
            EventType.CRAWL_ERROR: self.handle_crawl_error,
            EventType.PROGRESS_UPDATE: self.handle_progress_update,
            EventType.STATE_CHANGED: self.handle_state_changed,
            EventType.CONFIG_CHANGED: self.handle_config_changed,
            EventType.RESULTS_UPDATED: self.handle_results_updated,
        })
        
        # Async event handlers
        self.event_handlers.update({
            AsyncEventType.ASYNC_CRAWL_STARTED: self.handle_async_crawl_started,
            AsyncEventType.ASYNC_CRAWL_COMPLETED: self.handle_async_crawl_completed,
            AsyncEventType.ASYNC_CRAWL_FAILED: self.handle_async_crawl_failed,
            AsyncEventType.ASYNC_CRAWL_ERROR: self.handle_async_crawl_error,
            AsyncEventType.ASYNC_PROGRESS_UPDATE: self.handle_async_progress_update,
            AsyncEventType.ASYNC_STATE_CHANGED: self.handle_async_state_changed,
            AsyncEventType.UNIFIED_INTERFACE_EVENT: self.handle_unified_interface_event,
            AsyncEventType.BRIDGE_EVENT: self.handle_bridge_event,
            AsyncEventType.ADAPTER_EVENT: self.handle_adapter_event,
        })
    
    async def handle_event_async(self, event: AsyncEvent) -> None:
        """Handle event asynchronously."""
        if not self.is_active:
            return
        
        handler = self.event_handlers.get(event.event_type)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error handling event {event.event_type} in {self.name}: {e}")
        else:
            # Generic handler
            await self.handle_generic_event(event)
    
    # Standard event handlers (sync)
    
    def handle_crawl_started(self, event: AsyncEvent) -> None:
        """Handle crawl started event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(True)
    
    def handle_crawl_completed(self, event: AsyncEvent) -> None:
        """Handle crawl completed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'display_results'):
            self.view_component.display_results(event.data.get("data", {}))
    
    def handle_crawl_failed(self, event: AsyncEvent) -> None:
        """Handle crawl failed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'show_error'):
            self.view_component.show_error(event.data.get("error", "Unknown error"))
    
    def handle_crawl_error(self, event: AsyncEvent) -> None:
        """Handle crawl error event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'show_error'):
            self.view_component.show_error(event.data.get("error", "Unknown error"))
    
    def handle_progress_update(self, event: AsyncEvent) -> None:
        """Handle progress update event."""
        if hasattr(self.view_component, 'update_progress'):
            message = event.data.get("message", "")
            percentage = event.data.get("percentage", 0)
            self.view_component.update_progress(message, percentage)
    
    def handle_state_changed(self, event: AsyncEvent) -> None:
        """Handle state change event."""
        if hasattr(self.view_component, 'update_state'):
            new_state = event.data.get("new_state", "")
            old_state = event.data.get("old_state", "")
            self.view_component.update_state(new_state, old_state)
    
    def handle_config_changed(self, event: AsyncEvent) -> None:
        """Handle configuration change event."""
        if hasattr(self.view_component, 'update_config'):
            config = event.data.get("config", {})
            self.view_component.update_config(config)
    
    def handle_results_updated(self, event: AsyncEvent) -> None:
        """Handle results update event."""
        if hasattr(self.view_component, 'update_results'):
            results = event.data.get("results", {})
            self.view_component.update_results(results)
    
    # Async event handlers
    
    async def handle_async_crawl_started(self, event: AsyncEvent) -> None:
        """Handle async crawl started event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            if asyncio.iscoroutinefunction(self.view_component.set_crawling_state):
                await self.view_component.set_crawling_state(True)
            else:
                self.view_component.set_crawling_state(True)
        
        # Update status with unified interface information
        if hasattr(self.view_component, 'update_status'):
            status = f"Starting async crawl using {event.data.get('system_type', 'unified')} interface..."
            if asyncio.iscoroutinefunction(self.view_component.update_status):
                await self.view_component.update_status(status)
            else:
                self.view_component.update_status(status)
    
    async def handle_async_crawl_completed(self, event: AsyncEvent) -> None:
        """Handle async crawl completed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            if asyncio.iscoroutinefunction(self.view_component.set_crawling_state):
                await self.view_component.set_crawling_state(False)
            else:
                self.view_component.set_crawling_state(False)
        
        # Display results with enhanced information
        if hasattr(self.view_component, 'display_results'):
            results = event.data.get("data", {})
            
            # Add async-specific metadata
            results["async_metadata"] = {
                "execution_time": event.data.get("crawl_time", 0),
                "system_used": event.data.get("system_used", "unified"),
                "timestamp": event.timestamp.isoformat()
            }
            
            if asyncio.iscoroutinefunction(self.view_component.display_results):
                await self.view_component.display_results(results)
            else:
                self.view_component.display_results(results)
    
    async def handle_async_crawl_failed(self, event: AsyncEvent) -> None:
        """Handle async crawl failed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            if asyncio.iscoroutinefunction(self.view_component.set_crawling_state):
                await self.view_component.set_crawling_state(False)
            else:
                self.view_component.set_crawling_state(False)
        
        # Show enhanced error information
        if hasattr(self.view_component, 'show_error'):
            error_msg = f"Async crawl failed: {event.data.get('error', 'Unknown error')}"
            if event.data.get('system_used'):
                error_msg += f" (System: {event.data['system_used']})"
            
            if asyncio.iscoroutinefunction(self.view_component.show_error):
                await self.view_component.show_error(error_msg)
            else:
                self.view_component.show_error(error_msg)
    
    async def handle_async_crawl_error(self, event: AsyncEvent) -> None:
        """Handle async crawl error event."""
        await self.handle_async_crawl_failed(event)
    
    async def handle_async_progress_update(self, event: AsyncEvent) -> None:
        """Handle async progress update event."""
        if hasattr(self.view_component, 'update_progress'):
            message = event.data.get("message", "")
            percentage = event.data.get("percentage", 0)
            
            # Add async context to message
            if event.data.get("bridge_type"):
                message = f"[{event.data['bridge_type']}] {message}"
            
            if asyncio.iscoroutinefunction(self.view_component.update_progress):
                await self.view_component.update_progress(message, percentage)
            else:
                self.view_component.update_progress(message, percentage)
    
    async def handle_async_state_changed(self, event: AsyncEvent) -> None:
        """Handle async state change event."""
        if hasattr(self.view_component, 'update_state'):
            new_state = event.data.get("new_state", "")
            old_state = event.data.get("old_state", "")
            
            if asyncio.iscoroutinefunction(self.view_component.update_state):
                await self.view_component.update_state(new_state, old_state)
            else:
                self.view_component.update_state(new_state, old_state)
    
    async def handle_unified_interface_event(self, event: AsyncEvent) -> None:
        """Handle unified interface specific events."""
        if hasattr(self.view_component, 'update_interface_status'):
            interface_info = {
                "system_type": event.data.get("system_type", "unknown"),
                "crawler_id": event.data.get("crawler_id", ""),
                "adapter_name": event.data.get("adapter_name", ""),
                "timestamp": event.timestamp.isoformat()
            }
            
            if asyncio.iscoroutinefunction(self.view_component.update_interface_status):
                await self.view_component.update_interface_status(interface_info)
            else:
                self.view_component.update_interface_status(interface_info)
    
    async def handle_bridge_event(self, event: AsyncEvent) -> None:
        """Handle bridge-specific events."""
        if hasattr(self.view_component, 'update_bridge_status'):
            bridge_info = {
                "bridge_type": event.data.get("bridge_type", "unknown"),
                "source_system": event.data.get("source_system", "unknown"),
                "target_system": event.data.get("target_system", "unified"),
                "message": event.data.get("message", ""),
                "timestamp": event.timestamp.isoformat()
            }
            
            if asyncio.iscoroutinefunction(self.view_component.update_bridge_status):
                await self.view_component.update_bridge_status(bridge_info)
            else:
                self.view_component.update_bridge_status(bridge_info)
    
    async def handle_adapter_event(self, event: AsyncEvent) -> None:
        """Handle adapter-specific events."""
        if hasattr(self.view_component, 'update_adapter_status'):
            adapter_info = {
                "adapter_name": event.data.get("adapter_name", "unknown"),
                "site_name": event.data.get("site_name", ""),
                "status": event.data.get("status", "unknown"),
                "message": event.data.get("message", ""),
                "timestamp": event.timestamp.isoformat()
            }
            
            if asyncio.iscoroutinefunction(self.view_component.update_adapter_status):
                await self.view_component.update_adapter_status(adapter_info)
            else:
                self.view_component.update_adapter_status(adapter_info)
    
    async def handle_generic_event(self, event: AsyncEvent) -> None:
        """Handle generic events."""
        if hasattr(self.view_component, 'update_view'):
            event_type_value = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
            
            if asyncio.iscoroutinefunction(self.view_component.update_view):
                await self.view_component.update_view(event_type_value, event.data)
            else:
                self.view_component.update_view(event_type_value, event.data)


class AsyncEventManager:
    """
    Manager for async events and observers.
    
    This manager handles:
    - Event distribution
    - Observer management
    - Async event processing
    """
    
    def __init__(self, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        self.event_loop = event_loop or asyncio.get_event_loop()
        self.observers: List[AsyncObserver] = []
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_processing = False
        self.processing_task: Optional[asyncio.Task] = None
        
    def add_observer(self, observer: AsyncObserver) -> None:
        """Add an observer."""
        if observer not in self.observers:
            self.observers.append(observer)
            logger.info(f"Added observer: {observer.name}")
    
    def remove_observer(self, observer: AsyncObserver) -> None:
        """Remove an observer."""
        if observer in self.observers:
            self.observers.remove(observer)
            logger.info(f"Removed observer: {observer.name}")
    
    async def publish_event(self, event: AsyncEvent) -> None:
        """Publish an event to all observers."""
        await self.event_queue.put(event)
        
        if not self.is_processing:
            self.start_processing()
    
    def start_processing(self) -> None:
        """Start event processing."""
        if not self.is_processing:
            self.is_processing = True
            self.processing_task = asyncio.create_task(self._process_events())
    
    async def stop_processing(self) -> None:
        """Stop event processing."""
        self.is_processing = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
    
    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self.is_processing:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Distribute to all active observers
                tasks = []
                for observer in self.observers:
                    if observer.is_active:
                        tasks.append(observer.handle_event_async(event))
                
                # Wait for all observers to handle the event
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            except asyncio.TimeoutError:
                # Continue processing
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")


# Global async event manager
_async_event_manager: Optional[AsyncEventManager] = None


def get_async_event_manager() -> AsyncEventManager:
    """Get the global async event manager."""
    global _async_event_manager
    if _async_event_manager is None:
        _async_event_manager = AsyncEventManager()
    return _async_event_manager


# Factory functions
def create_async_gui_observer(name: str, view_component: object, event_loop: Optional[asyncio.AbstractEventLoop] = None) -> AsyncGUIObserver:
    """Create an async GUI observer."""
    return AsyncGUIObserver(name, view_component, event_loop)


def create_async_event(event_type: Union[EventType, AsyncEventType], data: Dict[str, Any], source: str = "async_gui") -> AsyncEvent:
    """Create an async event."""
    return AsyncEvent(event_type, data, source)


# Compatibility functions for existing sync observers
def wrap_sync_observer(sync_observer: Observer) -> AsyncObserver:
    """Wrap a sync observer to work with async events."""
    
    class SyncObserverWrapper(AsyncObserver):
        def __init__(self, sync_obs: Observer):
            super().__init__(sync_obs.name)
            self.sync_observer = sync_obs
        
        async def handle_event_async(self, event: AsyncEvent) -> None:
            # Convert async event to sync event
            sync_event = Event(event.event_type, event.data, event.source)
            
            # Call sync observer update method
            try:
                self.sync_observer.update(sync_event)
            except Exception as e:
                logger.error(f"Error in wrapped sync observer: {e}")
    
    return SyncObserverWrapper(sync_observer) 