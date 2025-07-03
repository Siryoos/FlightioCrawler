"""
Observer Pattern Implementation for GUI-Controller Communication.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional
from enum import Enum
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime


class EventType(Enum):
    """Enumeration of all possible GUI events."""
    
    # URL and Input Events
    URL_CHANGED = "url_changed"
    URL_FOCUS_OUT = "url_focus_out"
    URL_SELECTED = "url_selected"
    URL_ERROR = "url_error"
    
    # Configuration Events
    CONFIG_CHANGED = "config_changed"
    SUGGESTIONS_REQUESTED = "suggestions_requested"
    SUGGESTIONS_RECEIVED = "suggestions_received"
    
    # Crawling Events
    CRAWL_REQUESTED = "crawl_requested"
    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETED = "crawl_completed"
    CRAWL_FAILED = "crawl_failed"
    CRAWL_ERROR = "crawl_error"
    CRAWL_STOPPING = "crawl_stopping"
    STOP_REQUESTED = "stop_requested"
    
    # Progress Events
    PROGRESS_UPDATE = "progress_update"
    PROGRESS_STARTED = "progress_started"
    PROGRESS_COMPLETED = "progress_completed"
    
    # Results Events
    RESULTS_UPDATED = "results_updated"
    RESULTS_CLEARED = "results_cleared"
    RESULTS_EXPORTED = "results_exported"
    
    # State Events
    STATE_CHANGED = "state_changed"
    VIEW_UPDATED = "view_updated"
    
    # History Events
    HISTORY_CLEARED = "history_cleared"
    HISTORY_UPDATED = "history_updated"


@dataclass
class Event:
    """
    Event data structure for observer pattern.
    """
    
    event_type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    target: Optional[str] = None
    priority: int = 0  # 0=normal, 1=high, 2=critical
    
    def __post_init__(self):
        """Post-initialization processing."""
        if isinstance(self.event_type, str):
            # Convert string to EventType if needed
            try:
                self.event_type = EventType(self.event_type)
            except ValueError:
                # If not a valid EventType, keep as string for custom events
                pass


class Observer(ABC):
    """
    Abstract base class for all observers.
    """
    
    def __init__(self, name: str = None):
        """Initialize observer with optional name."""
        self.name = name or self.__class__.__name__
        self.is_active = True
        self.event_filter = None  # Optional filter function
        self.subscribed_events = set()  # Specific events to listen to
    
    @abstractmethod
    def update(self, event: Event) -> None:
        """
        Handle event notification.
        
        Args:
            event: Event object containing event data
        """
        pass
    
    def set_event_filter(self, filter_func: Callable[[Event], bool]) -> None:
        """
        Set a filter function to selectively process events.
        
        Args:
            filter_func: Function that returns True if event should be processed
        """
        self.event_filter = filter_func
    
    def subscribe_to_events(self, event_types: List[EventType]) -> None:
        """
        Subscribe to specific event types.
        
        Args:
            event_types: List of event types to subscribe to
        """
        self.subscribed_events.update(event_types)
    
    def unsubscribe_from_events(self, event_types: List[EventType]) -> None:
        """
        Unsubscribe from specific event types.
        
        Args:
            event_types: List of event types to unsubscribe from
        """
        self.subscribed_events.difference_update(event_types)
    
    def should_process_event(self, event: Event) -> bool:
        """
        Check if this observer should process the given event.
        
        Args:
            event: Event to check
            
        Returns:
            True if event should be processed
        """
        if not self.is_active:
            return False
        
        # Check subscription filter
        if self.subscribed_events and event.event_type not in self.subscribed_events:
            return False
        
        # Check custom filter
        if self.event_filter and not self.event_filter(event):
            return False
        
        return True
    
    def activate(self) -> None:
        """Activate this observer."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate this observer."""
        self.is_active = False


class Subject(ABC):
    """
    Abstract base class for subjects that can be observed.
    """
    
    def __init__(self):
        """Initialize subject."""
        self.observers: List[Observer] = []
        self.event_queue: List[Event] = []
        self.is_notifying = False
        self.notification_lock = threading.Lock()
    
    def attach(self, observer: Observer) -> None:
        """
        Attach an observer to this subject.
        
        Args:
            observer: Observer to attach
        """
        if observer not in self.observers:
            self.observers.append(observer)
    
    def detach(self, observer: Observer) -> None:
        """
        Detach an observer from this subject.
        
        Args:
            observer: Observer to detach
        """
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify(self, event: Event) -> None:
        """
        Notify all observers of an event.
        
        Args:
            event: Event to notify observers about
        """
        with self.notification_lock:
            if self.is_notifying:
                # Avoid recursive notifications
                self.event_queue.append(event)
                return
            
            self.is_notifying = True
            
            try:
                # Process current event
                self._notify_observers(event)
                
                # Process queued events
                while self.event_queue:
                    queued_event = self.event_queue.pop(0)
                    self._notify_observers(queued_event)
                    
            finally:
                self.is_notifying = False
    
    def _notify_observers(self, event: Event) -> None:
        """
        Internal method to notify observers.
        
        Args:
            event: Event to notify observers about
        """
        for observer in self.observers[:]:  # Create a copy to avoid modification during iteration
            try:
                if observer.should_process_event(event):
                    observer.update(event)
            except Exception as e:
                print(f"Error notifying observer {observer.name}: {e}")
    
    def get_observer_count(self) -> int:
        """Get the number of attached observers."""
        return len(self.observers)
    
    def clear_observers(self) -> None:
        """Clear all observers."""
        self.observers.clear()


class EventBus(Subject):
    """
    Central event bus for managing all GUI events.
    Implements Singleton pattern and provides centralized event management.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the event bus."""
        if not hasattr(self, 'initialized'):
            super().__init__()
            self.event_history: List[Event] = []
            self.max_history_size = 1000
            self.event_statistics = {
                "total_events": 0,
                "events_by_type": {},
                "errors": 0
            }
            self.initialized = True
    
    def publish(self, event_type: EventType, data: Dict[str, Any] = None, 
                source: str = None, target: str = None, priority: int = 0) -> None:
        """
        Publish an event to the event bus.
        
        Args:
            event_type: Type of event
            data: Event data dictionary
            source: Source of the event
            target: Target of the event
            priority: Event priority (0=normal, 1=high, 2=critical)
        """
        event = Event(
            event_type=event_type,
            data=data or {},
            source=source,
            target=target,
            priority=priority
        )
        
        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history_size:
            self.event_history.pop(0)
        
        # Update statistics
        self.event_statistics["total_events"] += 1
        event_type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
        self.event_statistics["events_by_type"][event_type_str] = \
            self.event_statistics["events_by_type"].get(event_type_str, 0) + 1
        
        # Notify observers
        self.notify(event)
    
    def subscribe(self, observer: Observer, event_types: List[EventType] = None) -> None:
        """
        Subscribe an observer to specific event types.
        
        Args:
            observer: Observer to subscribe
            event_types: List of event types to subscribe to (None for all)
        """
        self.attach(observer)
        if event_types:
            observer.subscribe_to_events(event_types)
    
    def unsubscribe(self, observer: Observer) -> None:
        """
        Unsubscribe an observer from the event bus.
        
        Args:
            observer: Observer to unsubscribe
        """
        self.detach(observer)
    
    def get_event_history(self, event_type: EventType = None, 
                         limit: int = None) -> List[Event]:
        """
        Get event history with optional filtering.
        
        Args:
            event_type: Filter by event type (None for all)
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        history = self.event_history
        
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return self.event_statistics.copy()
    
    def clear_history(self) -> None:
        """Clear event history."""
        self.event_history.clear()
        self.event_statistics = {
            "total_events": 0,
            "events_by_type": {},
            "errors": 0
        }


class GUIObserver(Observer):
    """
    Observer for GUI components.
    """
    
    def __init__(self, name: str, view_component: object):
        """
        Initialize GUI observer.
        
        Args:
            name: Observer name
            view_component: GUI component to update
        """
        super().__init__(name)
        self.view_component = view_component
        self.update_handlers = {}
        
        # Set up default event handlers
        self.setup_default_handlers()
    
    def setup_default_handlers(self) -> None:
        """Set up default event handlers."""
        self.update_handlers.update({
            EventType.CRAWL_STARTED: self.handle_crawl_started,
            EventType.CRAWL_COMPLETED: self.handle_crawl_completed,
            EventType.CRAWL_FAILED: self.handle_crawl_failed,
            EventType.CRAWL_ERROR: self.handle_crawl_error,
            EventType.PROGRESS_UPDATE: self.handle_progress_update,
            EventType.STATE_CHANGED: self.handle_state_changed,
            EventType.CONFIG_CHANGED: self.handle_config_changed,
            EventType.RESULTS_UPDATED: self.handle_results_updated,
        })
    
    def update(self, event: Event) -> None:
        """
        Handle event notification.
        
        Args:
            event: Event object
        """
        handler = self.update_handlers.get(event.event_type)
        if handler:
            try:
                handler(event)
            except Exception as e:
                print(f"Error handling event {event.event_type} in {self.name}: {e}")
        else:
            # Generic handler
            self.handle_generic_event(event)
    
    def handle_crawl_started(self, event: Event) -> None:
        """Handle crawl started event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(True)
    
    def handle_crawl_completed(self, event: Event) -> None:
        """Handle crawl completed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'display_results'):
            self.view_component.display_results(event.data.get("data", {}))
    
    def handle_crawl_failed(self, event: Event) -> None:
        """Handle crawl failed event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'show_error'):
            self.view_component.show_error(event.data.get("error", "Unknown error"))
    
    def handle_crawl_error(self, event: Event) -> None:
        """Handle crawl error event."""
        if hasattr(self.view_component, 'set_crawling_state'):
            self.view_component.set_crawling_state(False)
        
        if hasattr(self.view_component, 'show_error'):
            self.view_component.show_error(event.data.get("error", "Unknown error"))
    
    def handle_progress_update(self, event: Event) -> None:
        """Handle progress update event."""
        if hasattr(self.view_component, 'update_progress'):
            message = event.data.get("message", "")
            percentage = event.data.get("percentage", 0)
            self.view_component.update_progress(message, percentage)
    
    def handle_state_changed(self, event: Event) -> None:
        """Handle state change event."""
        if hasattr(self.view_component, 'update_state'):
            new_state = event.data.get("new_state", "")
            old_state = event.data.get("old_state", "")
            self.view_component.update_state(new_state, old_state)
    
    def handle_config_changed(self, event: Event) -> None:
        """Handle configuration change event."""
        if hasattr(self.view_component, 'update_config'):
            config = event.data.get("config", {})
            self.view_component.update_config(config)
    
    def handle_results_updated(self, event: Event) -> None:
        """Handle results update event."""
        if hasattr(self.view_component, 'update_results'):
            results = event.data.get("results", {})
            self.view_component.update_results(results)
    
    def handle_generic_event(self, event: Event) -> None:
        """Handle generic events."""
        if hasattr(self.view_component, 'update_view'):
            self.view_component.update_view(event.event_type.value, event.data)
    
    def add_custom_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        Add a custom event handler.
        
        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        self.update_handlers[event_type] = handler


class ControllerObserver(Observer):
    """
    Observer for controller components.
    """
    
    def __init__(self, name: str, controller: object):
        """
        Initialize controller observer.
        
        Args:
            name: Observer name
            controller: Controller object
        """
        super().__init__(name)
        self.controller = controller
        self.command_handlers = {}
        
        # Set up default command handlers
        self.setup_default_handlers()
    
    def setup_default_handlers(self) -> None:
        """Set up default command handlers."""
        self.command_handlers.update({
            EventType.CRAWL_REQUESTED: self.handle_crawl_requested,
            EventType.STOP_REQUESTED: self.handle_stop_requested,
            EventType.SUGGESTIONS_REQUESTED: self.handle_suggestions_requested,
            EventType.CONFIG_CHANGED: self.handle_config_changed,
            EventType.URL_CHANGED: self.handle_url_changed,
            EventType.RESULTS_CLEARED: self.handle_results_cleared,
        })
    
    def update(self, event: Event) -> None:
        """
        Handle event notification.
        
        Args:
            event: Event object
        """
        handler = self.command_handlers.get(event.event_type)
        if handler:
            try:
                handler(event)
            except Exception as e:
                print(f"Error handling command {event.event_type} in {self.name}: {e}")
    
    def handle_crawl_requested(self, event: Event) -> None:
        """Handle crawl request."""
        if hasattr(self.controller, 'start_crawl'):
            url = event.data.get("url", "")
            config = event.data.get("config", {})
            self.controller.start_crawl(url, config)
    
    def handle_stop_requested(self, event: Event) -> None:
        """Handle stop request."""
        if hasattr(self.controller, 'stop_crawl'):
            self.controller.stop_crawl()
    
    def handle_suggestions_requested(self, event: Event) -> None:
        """Handle suggestions request."""
        if hasattr(self.controller, 'get_crawler_suggestions'):
            url = event.data.get("url", "")
            suggestions = self.controller.get_crawler_suggestions(url)
            
            # Publish suggestions back to the event bus
            event_bus = EventBus()
            event_bus.publish(EventType.SUGGESTIONS_RECEIVED, 
                            {"suggestions": suggestions}, 
                            source=self.name)
    
    def handle_config_changed(self, event: Event) -> None:
        """Handle configuration change."""
        if hasattr(self.controller, 'set_crawler_config'):
            config = event.data.get("config", {})
            self.controller.set_crawler_config(config)
    
    def handle_url_changed(self, event: Event) -> None:
        """Handle URL change."""
        if hasattr(self.controller, 'set_url'):
            url = event.data.get("url", "")
            self.controller.set_url(url)
    
    def handle_results_cleared(self, event: Event) -> None:
        """Handle results cleared."""
        if hasattr(self.controller, 'clear_results'):
            self.controller.clear_results()
    
    def add_custom_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        Add a custom command handler.
        
        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        self.command_handlers[event_type] = handler


class ObserverManager:
    """
    Manager for coordinating observers and event flow.
    """
    
    def __init__(self):
        """Initialize observer manager."""
        self.event_bus = EventBus()
        self.observers = {}
        self.observer_groups = {}
    
    def register_observer(self, observer: Observer, group: str = "default") -> None:
        """
        Register an observer.
        
        Args:
            observer: Observer to register
            group: Observer group name
        """
        self.observers[observer.name] = observer
        
        if group not in self.observer_groups:
            self.observer_groups[group] = []
        self.observer_groups[group].append(observer)
        
        # Subscribe to event bus
        self.event_bus.subscribe(observer)
    
    def unregister_observer(self, observer_name: str) -> None:
        """
        Unregister an observer.
        
        Args:
            observer_name: Name of observer to unregister
        """
        if observer_name in self.observers:
            observer = self.observers[observer_name]
            self.event_bus.unsubscribe(observer)
            del self.observers[observer_name]
            
            # Remove from groups
            for group_observers in self.observer_groups.values():
                if observer in group_observers:
                    group_observers.remove(observer)
    
    def publish_event(self, event_type: EventType, data: Dict[str, Any] = None,
                     source: str = None, target: str = None, priority: int = 0) -> None:
        """
        Publish an event.
        
        Args:
            event_type: Event type
            data: Event data
            source: Event source
            target: Event target
            priority: Event priority
        """
        self.event_bus.publish(event_type, data, source, target, priority)
    
    def activate_observer_group(self, group: str) -> None:
        """
        Activate all observers in a group.
        
        Args:
            group: Group name
        """
        if group in self.observer_groups:
            for observer in self.observer_groups[group]:
                observer.activate()
    
    def deactivate_observer_group(self, group: str) -> None:
        """
        Deactivate all observers in a group.
        
        Args:
            group: Group name
        """
        if group in self.observer_groups:
            for observer in self.observer_groups[group]:
                observer.deactivate()
    
    def get_observer_count(self) -> int:
        """Get total number of registered observers."""
        return len(self.observers)
    
    def get_group_count(self) -> int:
        """Get number of observer groups."""
        return len(self.observer_groups)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get observer manager statistics."""
        return {
            "total_observers": self.get_observer_count(),
            "observer_groups": self.get_group_count(),
            "event_bus_stats": self.event_bus.get_statistics()
        }
    
    def cleanup(self) -> None:
        """Cleanup all observers and event bus."""
        # Deactivate all observers
        for observer in self.observers.values():
            observer.deactivate()
        
        # Clear event bus
        self.event_bus.clear_observers()
        self.event_bus.clear_history()
        
        # Clear local data
        self.observers.clear()
        self.observer_groups.clear()


# Factory functions for creating observers

def create_gui_observer(name: str, view_component: object) -> GUIObserver:
    """Create a GUI observer."""
    return GUIObserver(name, view_component)


def create_controller_observer(name: str, controller: object) -> ControllerObserver:
    """Create a controller observer."""
    return ControllerObserver(name, controller)


def create_observer_manager() -> ObserverManager:
    """Create an observer manager."""
    return ObserverManager()


# Global observer manager instance
observer_manager = ObserverManager() 