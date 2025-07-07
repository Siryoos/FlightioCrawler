"""
Observer Pattern implementation for monitoring crawler events.

This module implements the Observer pattern to provide a flexible event
monitoring system that can notify multiple observers about various crawler events.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import logging
import json
import threading
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can be observed."""

    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETED = "crawl_completed"
    CRAWL_FAILED = "crawl_failed"
    FLIGHT_EXTRACTED = "flight_extracted"
    RATE_LIMIT_HIT = "rate_limit_hit"
    ERROR_OCCURRED = "error_occurred"
    PAGE_LOADED = "page_loaded"
    SEARCH_SUBMITTED = "search_submitted"
    RESULTS_FOUND = "results_found"
    ADAPTER_CREATED = "adapter_created"
    VALIDATION_FAILED = "validation_failed"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    PERFORMANCE_WARNING = "performance_warning"


class EventSeverity(Enum):
    """Severity levels for events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CrawlerEvent:
    """Event data structure for crawler events."""

    event_type: EventType
    timestamp: datetime
    source: str  # Which component generated the event
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    severity: EventSeverity = EventSeverity.INFO


class EventObserver(ABC):
    """Abstract base class for event observers."""

    def __init__(self, name: str):
        self.name = name
        self.is_active = True
        self.observed_events: Set[EventType] = set()

    @abstractmethod
    async def on_event(self, event: CrawlerEvent) -> None:
        """Handle an observed event."""
        pass

    def subscribe_to(self, event_type: EventType) -> None:
        """Subscribe to a specific event type."""
        self.observed_events.add(event_type)

    def subscribe_to_all(self) -> None:
        """Subscribe to all event types."""
        self.observed_events = set(EventType)

    def is_interested_in(self, event_type: EventType) -> bool:
        """Check if observer is interested in this event type."""
        return self.is_active and (
            not self.observed_events or event_type in self.observed_events
        )


class LoggingObserver(EventObserver):
    """Observer that logs events to a logger."""

    def __init__(
        self, name: str = "LoggingObserver", logger_name: Optional[str] = None
    ):
        super().__init__(name)
        self.logger = logging.getLogger(logger_name or __name__)
        self.subscribe_to_all()

    async def on_event(self, event: CrawlerEvent) -> None:
        """Log the event with appropriate level."""
        message = f"[{event.source}] {event.event_type.value}"

        if event.data:
            message += f" - Data: {event.data}"

        if event.correlation_id:
            message += f" - CorrelationID: {event.correlation_id}"

        # Log with appropriate level based on severity
        if event.severity == EventSeverity.ERROR:
            self.logger.error(message)
        elif event.severity == EventSeverity.WARNING:
            self.logger.warning(message)
        elif event.severity == EventSeverity.CRITICAL:
            self.logger.critical(message)
        else:
            self.logger.info(message)


class MetricsObserver(EventObserver):
    """Observer that collects metrics from events."""

    def __init__(self, name: str = "MetricsObserver"):
        super().__init__(name)
        self.metrics: Dict[str, Any] = {
            "event_counts": {},
            "crawl_stats": {
                "total_crawls": 0,
                "successful_crawls": 0,
                "failed_crawls": 0,
                "total_flights": 0,
            },
            "error_stats": {},
            "performance_stats": {
                "avg_crawl_duration": 0.0,
                "max_crawl_duration": 0.0,
                "min_crawl_duration": float("inf"),
            },
        }
        self.subscribe_to_all()
        self._lock = threading.Lock()

    async def on_event(self, event: CrawlerEvent) -> None:
        """Update metrics based on event."""
        with self._lock:
            # Update event counts
            event_name = event.event_type.value
            self.metrics["event_counts"][event_name] = (
                self.metrics["event_counts"].get(event_name, 0) + 1
            )

            # Update specific metrics based on event type
            if event.event_type == EventType.CRAWL_STARTED:
                self.metrics["crawl_stats"]["total_crawls"] += 1

            elif event.event_type == EventType.CRAWL_COMPLETED:
                self.metrics["crawl_stats"]["successful_crawls"] += 1

                # Update performance stats if duration is available
                duration = event.data.get("duration")
                if duration:
                    current_avg = self.metrics["performance_stats"][
                        "avg_crawl_duration"
                    ]
                    total_crawls = self.metrics["crawl_stats"]["successful_crawls"]
                    new_avg = (
                        (current_avg * (total_crawls - 1)) + duration
                    ) / total_crawls
                    self.metrics["performance_stats"]["avg_crawl_duration"] = new_avg

                    self.metrics["performance_stats"]["max_crawl_duration"] = max(
                        self.metrics["performance_stats"]["max_crawl_duration"],
                        duration,
                    )

                    if self.metrics["performance_stats"]["min_crawl_duration"] != float(
                        "inf"
                    ):
                        self.metrics["performance_stats"]["min_crawl_duration"] = min(
                            self.metrics["performance_stats"]["min_crawl_duration"],
                            duration,
                        )
                    else:
                        self.metrics["performance_stats"][
                            "min_crawl_duration"
                        ] = duration

            elif event.event_type == EventType.CRAWL_FAILED:
                self.metrics["crawl_stats"]["failed_crawls"] += 1

            elif event.event_type == EventType.FLIGHT_EXTRACTED:
                flights_count = event.data.get("count", 1)
                self.metrics["crawl_stats"]["total_flights"] += flights_count

            elif event.event_type == EventType.ERROR_OCCURRED:
                error_type = event.data.get("error_type", "unknown")
                self.metrics["error_stats"][error_type] = (
                    self.metrics["error_stats"].get(error_type, 0) + 1
                )

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            return json.loads(json.dumps(self.metrics))  # Deep copy


class DatabaseObserver(EventObserver):
    """Observer that stores events in database."""

    def __init__(
        self, name: str = "DatabaseObserver", connection_string: Optional[str] = None
    ):
        super().__init__(name)
        self.connection_string = connection_string
        self.event_buffer: List[CrawlerEvent] = []
        self.buffer_size = 100
        self.flush_interval = 60  # seconds
        self._lock = threading.Lock()
        self._last_flush = datetime.now()

        # Subscribe to important events only
        self.subscribe_to(EventType.CRAWL_COMPLETED)
        self.subscribe_to(EventType.CRAWL_FAILED)
        self.subscribe_to(EventType.ERROR_OCCURRED)
        self.subscribe_to(EventType.CIRCUIT_BREAKER_OPENED)

    async def on_event(self, event: CrawlerEvent) -> None:
        """Buffer event for database storage."""
        with self._lock:
            self.event_buffer.append(event)

            # Flush if buffer is full or time threshold reached
            now = datetime.now()
            time_to_flush = (now - self._last_flush).seconds >= self.flush_interval
            buffer_full = len(self.event_buffer) >= self.buffer_size

            if time_to_flush or buffer_full:
                asyncio.create_task(self._flush_events())

    async def _flush_events(self) -> None:
        """Flush events to database."""
        try:
            with self._lock:
                events_to_flush = self.event_buffer.copy()
                self.event_buffer.clear()
                self._last_flush = datetime.now()

            if events_to_flush:
                await self._store_events(events_to_flush)

        except Exception as e:
            logger.error(f"Error flushing events to database: {e}")

    async def _store_events(self, events: List[CrawlerEvent]) -> None:
        """Store events in database (implement based on your database)."""
        # This is a placeholder - implement actual database storage
        logger.info(f"Storing {len(events)} events to database")


class AlertObserver(EventObserver):
    """Observer that sends alerts for critical events."""

    def __init__(
        self, name: str = "AlertObserver", alert_callback: Optional[Callable] = None
    ):
        super().__init__(name)
        self.alert_callback = alert_callback
        self.alert_thresholds = {
            "error_rate": 0.1,  # 10% error rate
            "crawl_duration": 300,  # 5 minutes
            "consecutive_failures": 5,
        }
        self.consecutive_failures = 0

        # Subscribe to critical events
        self.subscribe_to(EventType.CRAWL_FAILED)
        self.subscribe_to(EventType.ERROR_OCCURRED)
        self.subscribe_to(EventType.CIRCUIT_BREAKER_OPENED)
        self.subscribe_to(EventType.PERFORMANCE_WARNING)

    async def on_event(self, event: CrawlerEvent) -> None:
        """Check if event requires alerting."""
        should_alert = False
        alert_message = ""

        if event.event_type == EventType.CRAWL_FAILED:
            self.consecutive_failures += 1
            if (
                self.consecutive_failures
                >= self.alert_thresholds["consecutive_failures"]
            ):
                should_alert = True
                alert_message = f"Consecutive failures reached threshold: {self.consecutive_failures}"

        elif event.event_type == EventType.CRAWL_COMPLETED:
            self.consecutive_failures = 0  # Reset on success

        elif event.event_type == EventType.CIRCUIT_BREAKER_OPENED:
            should_alert = True
            alert_message = f"Circuit breaker opened for {event.source}"

        elif event.event_type == EventType.PERFORMANCE_WARNING:
            duration = event.data.get("duration", 0)
            if duration > self.alert_thresholds["crawl_duration"]:
                should_alert = True
                alert_message = f"Crawl duration exceeded threshold: {duration}s > {self.alert_thresholds['crawl_duration']}s"

        if should_alert and self.alert_callback:
            try:
                await self._send_alert(alert_message, event)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")

    async def _send_alert(self, message: str, event: CrawlerEvent) -> None:
        """Send alert using configured callback."""
        alert_data = {
            "message": message,
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "severity": event.severity,
        }

        if asyncio.iscoroutinefunction(self.alert_callback):
            await self.alert_callback(alert_data)
        else:
            self.alert_callback(alert_data)


class EventSubject:
    """Subject that manages observers and notifies them of events."""

    def __init__(self, name: str = "CrawlerEventSubject"):
        self.name = name
        self.observers: List[EventObserver] = []
        self._lock = threading.Lock()
        self.event_history: List[CrawlerEvent] = []
        self.max_history_size = 1000
        self.executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="event_notify"
        )

    def attach(self, observer: EventObserver) -> None:
        """Attach an observer."""
        with self._lock:
            if observer not in self.observers:
                self.observers.append(observer)
                logger.info(f"Observer {observer.name} attached to {self.name}")

    def detach(self, observer: EventObserver) -> None:
        """Detach an observer."""
        with self._lock:
            if observer in self.observers:
                self.observers.remove(observer)
                logger.info(f"Observer {observer.name} detached from {self.name}")

    async def notify(self, event: CrawlerEvent) -> None:
        """Notify all interested observers of an event."""
        # Add to history
        with self._lock:
            self.event_history.append(event)
            if len(self.event_history) > self.max_history_size:
                self.event_history.pop(0)

            # Get copy of observers to avoid locking during notification
            current_observers = [
                obs for obs in self.observers if obs.is_interested_in(event.event_type)
            ]

        # Notify observers concurrently
        if current_observers:
            tasks = []
            for observer in current_observers:
                try:
                    task = asyncio.create_task(observer.on_event(event))
                    tasks.append(task)
                except Exception as e:
                    logger.error(
                        f"Error creating task for observer {observer.name}: {e}"
                    )

            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error notifying observers: {e}")

    def get_event_history(
        self, event_type: Optional[EventType] = None, limit: Optional[int] = None
    ) -> List[CrawlerEvent]:
        """Get event history, optionally filtered by type."""
        with self._lock:
            events = self.event_history.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if limit:
            events = events[-limit:]

        return events


class CrawlerEventSystem:
    """Main event system for crawler monitoring."""

    def __init__(self):
        self.subject = EventSubject("MainCrawlerEventSystem")
        self._default_observers_attached = False

    def attach_default_observers(self) -> None:
        """Attach default observers (logging, metrics)."""
        if not self._default_observers_attached:
            # Logging observer
            logging_observer = LoggingObserver()
            self.subject.attach(logging_observer)

            # Metrics observer
            metrics_observer = MetricsObserver()
            self.subject.attach(metrics_observer)

            self._default_observers_attached = True
            logger.info("Default observers attached to crawler event system")

    def attach_observer(self, observer: EventObserver) -> None:
        """Attach a custom observer."""
        self.subject.attach(observer)

    async def emit_event(
        self,
        event_type: EventType,
        source: str,
        data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        severity: EventSeverity = EventSeverity.INFO,
    ) -> None:
        """Emit an event to all observers."""
        event = CrawlerEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            source=source,
            data=data or {},
            correlation_id=correlation_id,
            severity=severity,
        )

        await self.subject.notify(event)

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics from metrics observer if attached."""
        for observer in self.subject.observers:
            if isinstance(observer, MetricsObserver):
                return observer.get_metrics()
        return None


# Global event system instance
_event_system: Optional[CrawlerEventSystem] = None


def get_event_system() -> CrawlerEventSystem:
    """Get global event system instance."""
    global _event_system
    if _event_system is None:
        _event_system = CrawlerEventSystem()
        _event_system.attach_default_observers()
    return _event_system


# Convenience functions
async def emit_crawl_started(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit crawl started event."""
    await get_event_system().emit_event(
        EventType.CRAWL_STARTED, source, data, correlation_id
    )


async def emit_crawl_completed(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit crawl completed event."""
    await get_event_system().emit_event(
        EventType.CRAWL_COMPLETED, source, data, correlation_id
    )


async def emit_crawl_failed(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit crawl failed event."""
    await get_event_system().emit_event(
        EventType.CRAWL_FAILED, source, data, correlation_id, EventSeverity.ERROR
    )


async def emit_flight_extracted(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit flight extracted event."""
    await get_event_system().emit_event(
        EventType.FLIGHT_EXTRACTED, source, data, correlation_id
    )


async def emit_error_occurred(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit error occurred event."""
    await get_event_system().emit_event(
        EventType.ERROR_OCCURRED, source, data, correlation_id, EventSeverity.ERROR
    )


async def emit_data_extracted(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit data extracted event."""
    await get_event_system().emit_event(
        EventType.FLIGHT_EXTRACTED, source, data, correlation_id
    )


async def emit_error(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit error event."""
    await get_event_system().emit_event(
        EventType.ERROR_OCCURRED, source, data, correlation_id, EventSeverity.ERROR
    )


async def emit_warning(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit warning event."""
    await get_event_system().emit_event(
        EventType.ERROR_OCCURRED, source, data, correlation_id, EventSeverity.WARNING
    )


async def emit_performance_warning(
    source: str,
    data: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Emit performance warning event."""
    await get_event_system().emit_event(
        EventType.PERFORMANCE_WARNING, source, data, correlation_id, EventSeverity.WARNING
    )


class EventContext:
    """Context manager for event correlation."""
    
    def __init__(self, source: str, correlation_id: Optional[str] = None):
        self.source = source
        self.correlation_id = correlation_id or f"ctx_{datetime.now().timestamp()}"
        self.start_time = None
        
    async def __aenter__(self):
        self.start_time = datetime.now()
        await emit_crawl_started(self.source, correlation_id=self.correlation_id)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await emit_crawl_failed(
                self.source, 
                data={"error": str(exc_val), "duration": (datetime.now() - self.start_time).total_seconds()},
                correlation_id=self.correlation_id
            )
        else:
            await emit_crawl_completed(
                self.source,
                data={"duration": (datetime.now() - self.start_time).total_seconds()},
                correlation_id=self.correlation_id
            )


def event_context(source: str, correlation_id: Optional[str] = None) -> EventContext:
    """Create an event context manager for automatic event emission."""
    return EventContext(source, correlation_id)
