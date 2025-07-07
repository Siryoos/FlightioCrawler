"""
Unified Crawler Monitor

This module provides a comprehensive monitoring system that integrates monitoring
capabilities from all three systems (adapters, requests, crawlers) into a single
unified monitor. It supports:

- All crawler types (adapters, requests, crawlers)
- Comprehensive metrics collection
- Event-driven monitoring
- Health checks
- Performance analytics
- Alerting system
- Bridge monitoring
- System integration monitoring
"""

import asyncio
import logging
import time
import json
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable, Union, TYPE_CHECKING
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import uuid
import weakref
from concurrent.futures import ThreadPoolExecutor

# Type checking imports
if TYPE_CHECKING:
    from .unified_crawler_interface import UnifiedCrawlerInterface
    from .requests_to_adapters_bridge import RequestsToAdaptersBridge
    from .crawlers_to_adapters_bridge import CrawlersToAdaptersBridge

# Import monitoring components from different systems
try:
    from monitoring.enhanced_monitoring_system import EnhancedMonitoringSystem, get_global_monitoring
    from monitoring.production_memory_monitor import ProductionMemoryMonitor
    from monitoring.health_checks import HealthChecker, HealthCheckResult, HealthStatus
    from monitoring.enhanced_prometheus_metrics import EnhancedPrometheusMetrics
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    EnhancedMonitoringSystem = None
    ProductionMemoryMonitor = None
    HealthChecker = None
    EnhancedPrometheusMetrics = None

# Import GUI observers for requests system
try:
    from requests.crawler_gui_observer import EventBus, Event, EventType
    from requests.async_gui_observer import AsyncEventManager, AsyncEvent, AsyncEventType
    GUI_OBSERVERS_AVAILABLE = True
except ImportError:
    GUI_OBSERVERS_AVAILABLE = False
    EventBus = None
    AsyncEventManager = None

# Import patterns for adapters system
try:
    from .patterns.observer_pattern import Subject, Observer, EventType as AdapterEventType
    ADAPTER_PATTERNS_AVAILABLE = True
except ImportError:
    ADAPTER_PATTERNS_AVAILABLE = False
    Subject = None
    Observer = None

logger = logging.getLogger(__name__)


class UnifiedMonitoringLevel(Enum):
    """Unified monitoring levels across all systems."""
    MINIMAL = "minimal"
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    DEBUG = "debug"


class UnifiedEventType(Enum):
    """Unified event types across all systems."""
    # Crawler events
    CRAWLER_STARTED = "crawler_started"
    CRAWLER_COMPLETED = "crawler_completed"
    CRAWLER_FAILED = "crawler_failed"
    CRAWLER_STOPPED = "crawler_stopped"
    
    # Bridge events
    BRIDGE_CREATED = "bridge_created"
    BRIDGE_ERROR = "bridge_error"
    BRIDGE_CONVERSION = "bridge_conversion"
    
    # System events
    SYSTEM_HEALTH_CHECK = "system_health_check"
    SYSTEM_ALERT = "system_alert"
    SYSTEM_PERFORMANCE = "system_performance"
    
    # Data events
    DATA_EXTRACTED = "data_extracted"
    DATA_VALIDATED = "data_validated"
    DATA_PROCESSED = "data_processed"
    
    # Error events
    ERROR_OCCURRED = "error_occurred"
    ERROR_RECOVERED = "error_recovered"
    ERROR_ESCALATED = "error_escalated"


@dataclass
class UnifiedMetric:
    """Unified metric data structure."""
    timestamp: datetime
    metric_name: str
    value: Union[int, float, str]
    labels: Dict[str, str] = field(default_factory=dict)
    source_system: str = "unknown"
    component: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedEvent:
    """Unified event data structure."""
    event_id: str
    event_type: UnifiedEventType
    timestamp: datetime
    source_system: str
    component: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedHealthStatus:
    """Unified health status across all systems."""
    component: str
    system_type: str
    status: HealthStatus
    timestamp: datetime
    message: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedAlert:
    """Unified alert structure."""
    alert_id: str
    severity: str
    component: str
    system_type: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedCrawlerMonitor:
    """
    Unified monitoring system that integrates all monitoring capabilities
    from adapters, requests, and crawlers systems.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.monitor_id = str(uuid.uuid4())
        
        # State management
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.monitoring_level = UnifiedMonitoringLevel(
            self.config.get('monitoring_level', 'standard')
        )
        
        # Component registries
        self.registered_crawlers: Dict[str, 'UnifiedCrawlerInterface'] = {}
        self.registered_bridges: Dict[str, Union['RequestsToAdaptersBridge', 'CrawlersToAdaptersBridge']] = {}
        self.registered_components: Dict[str, Any] = {}
        
        # Metrics and events storage
        self.metrics_history: deque = deque(maxlen=self.config.get('metrics_history_size', 10000))
        self.events_history: deque = deque(maxlen=self.config.get('events_history_size', 5000))
        self.health_status: Dict[str, UnifiedHealthStatus] = {}
        self.active_alerts: Dict[str, UnifiedAlert] = {}
        
        # Performance tracking
        self.performance_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.system_metrics: Dict[str, Any] = {}
        
        # Monitoring components
        self.enhanced_monitoring: Optional[EnhancedMonitoringSystem] = None
        self.memory_monitor: Optional[ProductionMemoryMonitor] = None
        self.health_checker: Optional[HealthChecker] = None
        self.prometheus_metrics: Optional[EnhancedPrometheusMetrics] = None
        
        # Event management
        self.event_handlers: Dict[UnifiedEventType, List[Callable]] = defaultdict(list)
        self.alert_handlers: List[Callable[[UnifiedAlert], None]] = []
        
        # Background tasks
        self.monitoring_tasks: List[asyncio.Task] = []
        self.monitoring_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="unified-monitor")
        
        # Initialize monitoring components
        self._initialize_monitoring_components()
        
        self.logger.info(f"Unified Crawler Monitor initialized with ID: {self.monitor_id}")

    def _initialize_monitoring_components(self):
        """Initialize monitoring components from different systems."""
        try:
            # Initialize enhanced monitoring system
            if MONITORING_AVAILABLE and self.monitoring_level in [
                UnifiedMonitoringLevel.COMPREHENSIVE, 
                UnifiedMonitoringLevel.DEBUG
            ]:
                self.enhanced_monitoring = get_global_monitoring()
                self.memory_monitor = ProductionMemoryMonitor(
                    self.config.get('memory_monitor_config')
                )
                self.health_checker = HealthChecker()
                self.prometheus_metrics = EnhancedPrometheusMetrics(
                    namespace="unified_crawler"
                )
                self.logger.info("Enhanced monitoring components initialized")
            
            # Initialize GUI observers for requests system integration
            if GUI_OBSERVERS_AVAILABLE and self.config.get('enable_gui_monitoring', False):
                self._setup_gui_observers()
            
            # Initialize adapter patterns for adapters system integration
            if ADAPTER_PATTERNS_AVAILABLE:
                self._setup_adapter_observers()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring components: {e}")
            # Continue with basic monitoring

    def _setup_gui_observers(self):
        """Set up GUI observers for requests system integration."""
        try:
            # Connect to event bus
            if EventBus:
                self.event_bus = EventBus()
                self.event_bus.attach(self._handle_gui_event)
            
            # Connect to async event manager
            if AsyncEventManager:
                self.async_event_manager = AsyncEventManager()
                self.async_event_manager.add_handler(
                    AsyncEventType.ASYNC_CRAWL_STARTED,
                    self._handle_async_gui_event
                )
                self.async_event_manager.add_handler(
                    AsyncEventType.ASYNC_CRAWL_COMPLETED,
                    self._handle_async_gui_event
                )
                self.async_event_manager.add_handler(
                    AsyncEventType.ASYNC_CRAWL_FAILED,
                    self._handle_async_gui_event
                )
                
        except Exception as e:
            self.logger.error(f"Failed to setup GUI observers: {e}")

    def _setup_adapter_observers(self):
        """Set up observers for adapters system integration."""
        try:
            # Set up adapter pattern observers
            # This would be implemented when adapters support observer pattern
            pass
        except Exception as e:
            self.logger.error(f"Failed to setup adapter observers: {e}")

    # Registration methods
    
    def register_crawler(self, crawler: 'UnifiedCrawlerInterface', name: str = None) -> str:
        """Register a crawler for monitoring."""
        crawler_id = name or f"crawler_{len(self.registered_crawlers)}"
        self.registered_crawlers[crawler_id] = crawler
        
        # Initialize health status
        self.health_status[crawler_id] = UnifiedHealthStatus(
            component=crawler_id,
            system_type=crawler.get_system_type().value,
            status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            message="Crawler registered"
        )
        
        # Record registration event
        self._record_event(
            UnifiedEventType.CRAWLER_STARTED,
            crawler_id,
            crawler.get_system_type().value,
            {"crawler_type": type(crawler).__name__}
        )
        
        self.logger.info(f"Registered crawler: {crawler_id} (type: {type(crawler).__name__})")
        return crawler_id

    def register_bridge(self, bridge: Union['RequestsToAdaptersBridge', 'CrawlersToAdaptersBridge'], name: str = None) -> str:
        """Register a bridge for monitoring."""
        bridge_id = name or f"bridge_{len(self.registered_bridges)}"
        self.registered_bridges[bridge_id] = bridge
        
        # Initialize health status
        self.health_status[bridge_id] = UnifiedHealthStatus(
            component=bridge_id,
            system_type="bridge",
            status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            message="Bridge registered"
        )
        
        # Record registration event
        self._record_event(
            UnifiedEventType.BRIDGE_CREATED,
            bridge_id,
            "bridge",
            {"bridge_type": type(bridge).__name__}
        )
        
        self.logger.info(f"Registered bridge: {bridge_id} (type: {type(bridge).__name__})")
        return bridge_id

    def register_component(self, component: Any, name: str, system_type: str = "unknown") -> str:
        """Register any component for monitoring."""
        component_id = name
        self.registered_components[component_id] = component
        
        # Initialize health status
        self.health_status[component_id] = UnifiedHealthStatus(
            component=component_id,
            system_type=system_type,
            status=HealthStatus.HEALTHY,
            timestamp=datetime.now(),
            message="Component registered"
        )
        
        self.logger.info(f"Registered component: {component_id} (system: {system_type})")
        return component_id

    # Monitoring methods
    
    async def start_monitoring(self):
        """Start the unified monitoring system."""
        if self.is_running:
            self.logger.warning("Monitoring system already running")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start enhanced monitoring components
        if self.enhanced_monitoring:
            await self.enhanced_monitoring.start_monitoring()
        
        if self.memory_monitor:
            await self.memory_monitor.start_monitoring()
        
        # Start background monitoring tasks
        await self._start_monitoring_tasks()
        
        self.logger.info("Unified monitoring system started")

    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks."""
        tasks = [
            self._unified_metrics_loop(),
            self._health_check_loop(),
            self._performance_analysis_loop(),
            self._alert_processing_loop()
        ]
        
        for task_func in tasks:
            task = asyncio.create_task(task_func)
            self.monitoring_tasks.append(task)

    async def _unified_metrics_loop(self):
        """Unified metrics collection loop."""
        while self.is_running:
            try:
                await self._collect_unified_metrics()
                await asyncio.sleep(self.config.get('metrics_interval', 30))
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(10)

    async def _collect_unified_metrics(self):
        """Collect metrics from all registered components."""
        timestamp = datetime.now()
        
        # Collect system metrics
        await self._collect_system_metrics(timestamp)
        
        # Collect crawler metrics
        await self._collect_crawler_metrics(timestamp)
        
        # Collect bridge metrics
        await self._collect_bridge_metrics(timestamp)
        
        # Update Prometheus metrics
        if self.prometheus_metrics:
            await self._update_prometheus_metrics()

    async def _collect_system_metrics(self, timestamp: datetime):
        """Collect system-level metrics."""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            self._record_metric(
                timestamp, "system_memory_percent", memory.percent,
                {"type": "memory"}, "system", "system"
            )
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self._record_metric(
                timestamp, "system_cpu_percent", cpu_percent,
                {"type": "cpu"}, "system", "system"
            )
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            self._record_metric(
                timestamp, "process_memory_mb", process_memory,
                {"type": "process"}, "system", "process"
            )
            
        except Exception as e:
            self.logger.error(f"System metrics collection failed: {e}")

    async def _collect_crawler_metrics(self, timestamp: datetime):
        """Collect metrics from registered crawlers."""
        for crawler_id, crawler in self.registered_crawlers.items():
            try:
                # Get health status
                if hasattr(crawler, 'get_health_status'):
                    health = await crawler.get_health_status()
                    self._update_health_status(crawler_id, health)
                
                # Get performance metrics if available
                if hasattr(crawler, 'get_performance_metrics'):
                    metrics = await crawler.get_performance_metrics()
                    for metric_name, value in metrics.items():
                        self._record_metric(
                            timestamp, metric_name, value,
                            {"crawler_id": crawler_id}, crawler.get_system_type().value, crawler_id
                        )
                        
            except Exception as e:
                self.logger.error(f"Error collecting metrics for crawler {crawler_id}: {e}")

    async def _collect_bridge_metrics(self, timestamp: datetime):
        """Collect metrics from registered bridges."""
        for bridge_id, bridge in self.registered_bridges.items():
            try:
                # Get health status
                if hasattr(bridge, 'get_health_status'):
                    health = await bridge.get_health_status()
                    self._update_health_status(bridge_id, health)
                
                # Get bridge-specific metrics
                if hasattr(bridge, 'get_bridge_metrics'):
                    metrics = await bridge.get_bridge_metrics()
                    for metric_name, value in metrics.items():
                        self._record_metric(
                            timestamp, metric_name, value,
                            {"bridge_id": bridge_id}, "bridge", bridge_id
                        )
                        
            except Exception as e:
                self.logger.error(f"Error collecting metrics for bridge {bridge_id}: {e}")

    async def _health_check_loop(self):
        """Health check loop."""
        while self.is_running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.get('health_check_interval', 60))
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)

    async def _perform_health_checks(self):
        """Perform health checks on all components."""
        timestamp = datetime.now()
        
        # Check registered crawlers
        for crawler_id, crawler in self.registered_crawlers.items():
            try:
                health = await self._check_component_health(crawler)
                self._update_health_status(crawler_id, health, timestamp)
            except Exception as e:
                self.logger.error(f"Health check failed for crawler {crawler_id}: {e}")
                self._update_health_status(
                    crawler_id, 
                    {"status": "unhealthy", "error": str(e)}, 
                    timestamp
                )
        
        # Check registered bridges
        for bridge_id, bridge in self.registered_bridges.items():
            try:
                health = await self._check_component_health(bridge)
                self._update_health_status(bridge_id, health, timestamp)
            except Exception as e:
                self.logger.error(f"Health check failed for bridge {bridge_id}: {e}")
                self._update_health_status(
                    bridge_id, 
                    {"status": "unhealthy", "error": str(e)}, 
                    timestamp
                )

    async def _check_component_health(self, component: Any) -> Dict[str, Any]:
        """Check health of a component."""
        if hasattr(component, 'get_health_status'):
            if asyncio.iscoroutinefunction(component.get_health_status):
                return await component.get_health_status()
            else:
                return component.get_health_status()
        else:
            return {"status": "healthy", "message": "Component accessible"}

    async def _performance_analysis_loop(self):
        """Performance analysis loop."""
        while self.is_running:
            try:
                await self._analyze_performance()
                await asyncio.sleep(self.config.get('performance_analysis_interval', 300))
            except Exception as e:
                self.logger.error(f"Error in performance analysis: {e}")
                await asyncio.sleep(60)

    async def _analyze_performance(self):
        """Analyze performance metrics and generate insights."""
        # Analyze recent metrics
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= datetime.now() - timedelta(minutes=10)
        ]
        
        if not recent_metrics:
            return
        
        # Group metrics by component
        component_metrics = defaultdict(list)
        for metric in recent_metrics:
            component_metrics[metric.component].append(metric)
        
        # Analyze each component
        for component, metrics in component_metrics.items():
            try:
                analysis = self._analyze_component_performance(component, metrics)
                if analysis.get('alerts'):
                    for alert in analysis['alerts']:
                        await self._create_alert(alert)
                        
            except Exception as e:
                self.logger.error(f"Performance analysis failed for {component}: {e}")

    def _analyze_component_performance(self, component: str, metrics: List[UnifiedMetric]) -> Dict[str, Any]:
        """Analyze performance for a specific component."""
        analysis = {
            'component': component,
            'metrics_count': len(metrics),
            'time_range': {
                'start': min(m.timestamp for m in metrics),
                'end': max(m.timestamp for m in metrics)
            },
            'alerts': []
        }
        
        # Analyze response times
        response_times = [m.value for m in metrics if m.metric_name.endswith('_response_time')]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            if avg_response_time > self.config.get('response_time_threshold', 5000):
                analysis['alerts'].append({
                    'severity': 'warning',
                    'message': f'High average response time: {avg_response_time:.2f}ms',
                    'component': component
                })
        
        # Analyze error rates
        error_metrics = [m for m in metrics if 'error' in m.metric_name.lower()]
        if error_metrics:
            error_rate = len(error_metrics) / len(metrics) * 100
            if error_rate > self.config.get('error_rate_threshold', 5):
                analysis['alerts'].append({
                    'severity': 'critical',
                    'message': f'High error rate: {error_rate:.2f}%',
                    'component': component
                })
        
        return analysis

    async def _alert_processing_loop(self):
        """Alert processing loop."""
        while self.is_running:
            try:
                await self._process_alerts()
                await asyncio.sleep(self.config.get('alert_processing_interval', 30))
            except Exception as e:
                self.logger.error(f"Error in alert processing: {e}")
                await asyncio.sleep(10)

    async def _process_alerts(self):
        """Process and manage alerts."""
        # Check for alert resolution
        resolved_alerts = []
        for alert_id, alert in self.active_alerts.items():
            if await self._check_alert_resolution(alert):
                alert.resolved = True
                alert.resolution_time = datetime.now()
                resolved_alerts.append(alert_id)
        
        # Remove resolved alerts
        for alert_id in resolved_alerts:
            del self.active_alerts[alert_id]
            self.logger.info(f"Alert resolved: {alert_id}")

    async def _check_alert_resolution(self, alert: UnifiedAlert) -> bool:
        """Check if an alert condition has been resolved."""
        # This is a simplified check - in reality, you'd check the specific condition
        component_health = self.health_status.get(alert.component)
        if component_health and component_health.status == HealthStatus.HEALTHY:
            return True
        return False

    async def _create_alert(self, alert_data: Dict[str, Any]):
        """Create and process an alert."""
        alert = UnifiedAlert(
            alert_id=str(uuid.uuid4()),
            severity=alert_data['severity'],
            component=alert_data['component'],
            system_type=alert_data.get('system_type', 'unknown'),
            message=alert_data['message'],
            timestamp=datetime.now(),
            metadata=alert_data.get('metadata', {})
        )
        
        self.active_alerts[alert.alert_id] = alert
        
        # Notify alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")
        
        self.logger.warning(f"Alert created: {alert.message} (severity: {alert.severity})")

    # Event handling methods
    
    def _record_event(self, event_type: UnifiedEventType, component: str, system_type: str, data: Dict[str, Any]):
        """Record a unified event."""
        event = UnifiedEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(),
            source_system=system_type,
            component=component,
            data=data
        )
        
        self.events_history.append(event)
        
        # Notify event handlers
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                self.logger.error(f"Event handler failed: {e}")

    def _record_metric(self, timestamp: datetime, metric_name: str, value: Union[int, float], 
                      labels: Dict[str, str], source_system: str, component: str):
        """Record a unified metric."""
        metric = UnifiedMetric(
            timestamp=timestamp,
            metric_name=metric_name,
            value=value,
            labels=labels,
            source_system=source_system,
            component=component
        )
        
        self.metrics_history.append(metric)

    def _update_health_status(self, component: str, health_data: Dict[str, Any], timestamp: datetime = None):
        """Update health status for a component."""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Determine status
        status_str = health_data.get('status', 'unknown').lower()
        if status_str == 'healthy':
            status = HealthStatus.HEALTHY
        elif status_str == 'warning':
            status = HealthStatus.WARNING
        elif status_str == 'critical':
            status = HealthStatus.CRITICAL
        else:
            status = HealthStatus.UNKNOWN
        
        # Update health status
        self.health_status[component] = UnifiedHealthStatus(
            component=component,
            system_type=health_data.get('system_type', 'unknown'),
            status=status,
            timestamp=timestamp,
            message=health_data.get('message', ''),
            metrics=health_data.get('metrics', {}),
            details=health_data.get('details', {})
        )

    # Event handlers for different systems
    
    def _handle_gui_event(self, event):
        """Handle GUI events from requests system."""
        try:
            # Convert GUI event to unified event
            unified_event_type = self._convert_gui_event_type(event.event_type)
            if unified_event_type:
                self._record_event(
                    unified_event_type,
                    event.data.get('component', 'gui'),
                    'requests',
                    event.data
                )
        except Exception as e:
            self.logger.error(f"GUI event handling failed: {e}")

    async def _handle_async_gui_event(self, event):
        """Handle async GUI events from requests system."""
        try:
            # Convert async GUI event to unified event
            unified_event_type = self._convert_async_gui_event_type(event.event_type)
            if unified_event_type:
                self._record_event(
                    unified_event_type,
                    event.data.get('component', 'async_gui'),
                    'requests',
                    event.data
                )
        except Exception as e:
            self.logger.error(f"Async GUI event handling failed: {e}")

    def _convert_gui_event_type(self, gui_event_type) -> Optional[UnifiedEventType]:
        """Convert GUI event type to unified event type."""
        conversion_map = {
            'crawl_started': UnifiedEventType.CRAWLER_STARTED,
            'crawl_completed': UnifiedEventType.CRAWLER_COMPLETED,
            'crawl_failed': UnifiedEventType.CRAWLER_FAILED,
            'crawl_error': UnifiedEventType.ERROR_OCCURRED,
        }
        return conversion_map.get(gui_event_type.value if hasattr(gui_event_type, 'value') else gui_event_type)

    def _convert_async_gui_event_type(self, async_event_type) -> Optional[UnifiedEventType]:
        """Convert async GUI event type to unified event type."""
        conversion_map = {
            'async_crawl_started': UnifiedEventType.CRAWLER_STARTED,
            'async_crawl_completed': UnifiedEventType.CRAWLER_COMPLETED,
            'async_crawl_failed': UnifiedEventType.CRAWLER_FAILED,
        }
        return conversion_map.get(async_event_type.value if hasattr(async_event_type, 'value') else async_event_type)

    # Utility methods
    
    async def _update_prometheus_metrics(self):
        """Update Prometheus metrics."""
        if not self.prometheus_metrics:
            return
        
        try:
            # Update component health metrics
            for component, health in self.health_status.items():
                health_value = 1 if health.status == HealthStatus.HEALTHY else 0
                # Note: This would need to be implemented based on the actual Prometheus metrics structure
                # self.prometheus_metrics.update_component_health(component, health_value)
                
        except Exception as e:
            self.logger.error(f"Prometheus metrics update failed: {e}")

    # Public API methods
    
    def add_event_handler(self, event_type: UnifiedEventType, handler: Callable):
        """Add an event handler for a specific event type."""
        self.event_handlers[event_type].append(handler)

    def add_alert_handler(self, handler: Callable[[UnifiedAlert], None]):
        """Add an alert handler."""
        self.alert_handlers.append(handler)

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        return {
            'monitor_id': self.monitor_id,
            'is_running': self.is_running,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'monitoring_level': self.monitoring_level.value,
            'registered_components': {
                'crawlers': len(self.registered_crawlers),
                'bridges': len(self.registered_bridges),
                'components': len(self.registered_components)
            },
            'metrics': {
                'total_metrics': len(self.metrics_history),
                'recent_metrics': len([
                    m for m in self.metrics_history 
                    if m.timestamp >= datetime.now() - timedelta(minutes=5)
                ])
            },
            'events': {
                'total_events': len(self.events_history),
                'recent_events': len([
                    e for e in self.events_history 
                    if e.timestamp >= datetime.now() - timedelta(minutes=5)
                ])
            },
            'health_status': {
                component: status.status.value 
                for component, status in self.health_status.items()
            },
            'active_alerts': len(self.active_alerts),
            'system_integration': {
                'enhanced_monitoring': self.enhanced_monitoring is not None,
                'memory_monitor': self.memory_monitor is not None,
                'health_checker': self.health_checker is not None,
                'prometheus_metrics': self.prometheus_metrics is not None
            }
        }

    def get_component_health(self, component: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific component."""
        health = self.health_status.get(component)
        if health:
            return {
                'component': health.component,
                'system_type': health.system_type,
                'status': health.status.value,
                'timestamp': health.timestamp.isoformat(),
                'message': health.message,
                'metrics': health.metrics,
                'details': health.details
            }
        return None

    def get_recent_metrics(self, component: str = None, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get recent metrics for a component or all components."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp >= cutoff_time and (component is None or m.component == component)
        ]
        
        return [
            {
                'timestamp': m.timestamp.isoformat(),
                'metric_name': m.metric_name,
                'value': m.value,
                'labels': m.labels,
                'source_system': m.source_system,
                'component': m.component
            }
            for m in recent_metrics
        ]

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return [
            {
                'alert_id': alert.alert_id,
                'severity': alert.severity,
                'component': alert.component,
                'system_type': alert.system_type,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'metadata': alert.metadata
            }
            for alert in self.active_alerts.values()
        ]

    async def stop_monitoring(self):
        """Stop the unified monitoring system."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel background tasks
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        
        # Stop monitoring components
        if self.enhanced_monitoring:
            await self.enhanced_monitoring.stop_monitoring()
        
        if self.memory_monitor:
            await self.memory_monitor.stop_monitoring()
        
        # Cleanup
        self.monitoring_executor.shutdown(wait=True)
        
        self.logger.info("Unified monitoring system stopped")

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'monitoring_executor'):
            self.monitoring_executor.shutdown(wait=False)


# Global unified monitor instance
_global_unified_monitor: Optional[UnifiedCrawlerMonitor] = None


def get_unified_monitor(config: Dict[str, Any] = None) -> UnifiedCrawlerMonitor:
    """Get the global unified monitor instance."""
    global _global_unified_monitor
    if _global_unified_monitor is None:
        _global_unified_monitor = UnifiedCrawlerMonitor(config)
    return _global_unified_monitor


def initialize_unified_monitor(config: Dict[str, Any]) -> UnifiedCrawlerMonitor:
    """Initialize the global unified monitor with configuration."""
    global _global_unified_monitor
    _global_unified_monitor = UnifiedCrawlerMonitor(config)
    return _global_unified_monitor 