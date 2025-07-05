"""
Enhanced Monitoring System for FlightIO Crawler
Comprehensive monitoring with error correlation, performance tracking, and intelligent alerting
"""

import asyncio
import logging
import time
import json
import psutil
import aiohttp
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path
import threading
import uuid
from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server
import aiofiles
import weakref


class MonitoringLevel(Enum):
    """Monitoring detail levels"""
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"
    DEBUG = "debug"


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MetricDataPoint:
    """Individual metric data point"""
    timestamp: datetime
    metric_name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert data structure"""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    component: str
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    correlation_id: Optional[str] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    escalation_level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    requests_per_minute: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class EnhancedMonitoringSystem:
    """
    Comprehensive monitoring system with intelligent alerting and correlation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Monitoring state
        self.is_running = False
        self.start_time = datetime.now()
        self.component_registry: Dict[str, Any] = {}
        
        # Metrics storage
        self.metrics_history: deque = deque(maxlen=100000)
        self.aggregated_metrics: Dict[str, Dict] = defaultdict(dict)
        self.performance_metrics: Dict[str, PerformanceMetrics] = {}
        
        # Alerting system
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.alert_callbacks: List[Callable] = []
        self.alert_rules: Dict[str, Dict] = {}
        
        # Correlation and analysis
        self.correlation_engine = CorrelationEngine()
        self.trend_analyzer = TrendAnalyzer()
        self.anomaly_detector = AnomalyDetector()
        
        # Background tasks
        self.monitoring_tasks: List[asyncio.Task] = []
        
        # Prometheus metrics
        self._init_prometheus_metrics()
        
        # Health checks
        self.health_checks: Dict[str, Callable] = {}
        self.health_status: Dict[str, Dict] = {}
        
        self.logger.info("Enhanced Monitoring System initialized")

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        self.prometheus_metrics = {
            'crawler_requests_total': Counter(
                'crawler_requests_total',
                'Total crawler requests',
                ['adapter', 'status']
            ),
            'crawler_duration_seconds': Histogram(
                'crawler_duration_seconds',
                'Crawler request duration',
                ['adapter'],
                buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float('inf')]
            ),
            'crawler_memory_usage_bytes': Gauge(
                'crawler_memory_usage_bytes',
                'Crawler memory usage',
                ['component']
            ),
            'crawler_cpu_usage_percent': Gauge(
                'crawler_cpu_usage_percent',
                'Crawler CPU usage percentage',
                ['component']
            ),
            'crawler_active_connections': Gauge(
                'crawler_active_connections',
                'Active browser connections',
                ['adapter']
            ),
            'crawler_error_rate': Gauge(
                'crawler_error_rate',
                'Error rate percentage',
                ['adapter', 'error_type']
            ),
            'crawler_alert_total': Counter(
                'crawler_alert_total',
                'Total alerts generated',
                ['severity', 'component']
            ),
            'crawler_health_status': Gauge(
                'crawler_health_status',
                'Component health status (1=healthy, 0=unhealthy)',
                ['component']
            )
        }

    async def start_monitoring(self, port: int = 9091):
        """Start the monitoring system"""
        if self.is_running:
            self.logger.warning("Monitoring system already running")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start Prometheus metrics server
        if self.config.get('prometheus_enabled', True):
            start_http_server(port)
            self.logger.info(f"Prometheus metrics server started on port {port}")
        
        # Initialize alert rules
        await self._load_alert_rules()
        
        # Start background monitoring tasks
        await self._start_background_tasks()
        
        self.logger.info("Enhanced monitoring system started")

    async def _load_alert_rules(self):
        """Load alert rules from configuration"""
        try:
            rules_file = self.config.get('alert_rules_file', 'config/alert_rules.json')
            if Path(rules_file).exists():
                async with aiofiles.open(rules_file, 'r') as f:
                    content = await f.read()
                    self.alert_rules = json.loads(content)
                    self.logger.info(f"Loaded {len(self.alert_rules)} alert rules")
            else:
                self._create_default_alert_rules()
        except Exception as e:
            self.logger.error(f"Failed to load alert rules: {e}")
            self._create_default_alert_rules()

    def _create_default_alert_rules(self):
        """Create default alert rules"""
        self.alert_rules = {
            'high_error_rate': {
                'metric': 'error_rate',
                'threshold': 10.0,
                'severity': AlertSeverity.WARNING.value,
                'duration_minutes': 5
            },
            'critical_error_rate': {
                'metric': 'error_rate',
                'threshold': 25.0,
                'severity': AlertSeverity.CRITICAL.value,
                'duration_minutes': 2
            },
            'high_response_time': {
                'metric': 'response_time_ms',
                'threshold': 30000,
                'severity': AlertSeverity.WARNING.value,
                'duration_minutes': 3
            },
            'memory_usage_high': {
                'metric': 'memory_usage_mb',
                'threshold': 1024,
                'severity': AlertSeverity.WARNING.value,
                'duration_minutes': 5
            },
            'memory_usage_critical': {
                'metric': 'memory_usage_mb',
                'threshold': 2048,
                'severity': AlertSeverity.CRITICAL.value,
                'duration_minutes': 1
            },
            'component_down': {
                'metric': 'health_status',
                'threshold': 0,
                'severity': AlertSeverity.CRITICAL.value,
                'duration_minutes': 1
            }
        }

    async def _start_background_tasks(self):
        """Start background monitoring tasks"""
        tasks = [
            self._metrics_collection_loop(),
            self._alert_evaluation_loop(),
            self._health_check_loop(),
            self._correlation_analysis_loop(),
            self._cleanup_loop()
        ]
        
        for task_func in tasks:
            task = asyncio.create_task(task_func)
            self.monitoring_tasks.append(task)

    async def _metrics_collection_loop(self):
        """Background metrics collection"""
        while self.is_running:
            try:
                await self._collect_system_metrics()
                await self._update_prometheus_metrics()
                
                interval = self.config.get('metrics_interval_seconds', 30)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(10)

    async def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            # System metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Record metrics
            timestamp = datetime.now()
            
            system_metrics = [
                MetricDataPoint(timestamp, 'system_memory_percent', memory.percent),
                MetricDataPoint(timestamp, 'system_cpu_percent', cpu_percent),
                MetricDataPoint(timestamp, 'process_memory_mb', process_memory),
                MetricDataPoint(timestamp, 'process_cpu_percent', process.cpu_percent())
            ]
            
            for metric in system_metrics:
                self.metrics_history.append(metric)
                
        except Exception as e:
            self.logger.error(f"System metrics collection failed: {e}")

    async def _update_prometheus_metrics(self):
        """Update Prometheus metrics"""
        try:
            # Update system metrics
            memory = psutil.virtual_memory()
            self.prometheus_metrics['crawler_memory_usage_bytes'].labels(
                component='system'
            ).set(memory.used)
            
            self.prometheus_metrics['crawler_cpu_usage_percent'].labels(
                component='system'
            ).set(psutil.cpu_percent())
            
            # Update component health status
            for component, status in self.health_status.items():
                health_value = 1 if status.get('healthy', False) else 0
                self.prometheus_metrics['crawler_health_status'].labels(
                    component=component
                ).set(health_value)
                
        except Exception as e:
            self.logger.error(f"Prometheus metrics update failed: {e}")

    async def _alert_evaluation_loop(self):
        """Background alert evaluation"""
        while self.is_running:
            try:
                await self._evaluate_alert_rules()
                await self._process_alert_escalations()
                
                interval = self.config.get('alert_evaluation_seconds', 60)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in alert evaluation: {e}")
                await asyncio.sleep(30)

    async def _evaluate_alert_rules(self):
        """Evaluate alert rules against current metrics"""
        for rule_name, rule in self.alert_rules.items():
            try:
                await self._evaluate_single_rule(rule_name, rule)
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule_name}: {e}")

    async def _evaluate_single_rule(self, rule_name: str, rule: Dict):
        """Evaluate a single alert rule"""
        metric_name = rule['metric']
        threshold = rule['threshold']
        severity = AlertSeverity(rule['severity'])
        duration_minutes = rule.get('duration_minutes', 5)
        
        # Get recent metrics for the specified duration
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.metric_name == metric_name and m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return
        
        # Check if threshold is consistently breached
        breached_count = sum(1 for m in recent_metrics if m.value > threshold)
        breach_percentage = breached_count / len(recent_metrics) if recent_metrics else 0
        
        # Trigger alert if threshold is breached consistently
        if breach_percentage >= 0.8:  # 80% of the time
            await self._trigger_alert(
                rule_name=rule_name,
                severity=severity,
                metric_name=metric_name,
                metric_value=recent_metrics[-1].value,
                threshold=threshold,
                message=f"{metric_name} exceeded threshold {threshold} for {duration_minutes} minutes"
            )

    async def _trigger_alert(self, rule_name: str, severity: AlertSeverity, 
                           metric_name: str, metric_value: float, 
                           threshold: float, message: str):
        """Trigger a new alert"""
        alert_id = f"{rule_name}_{int(time.time())}"
        
        # Check if similar alert already exists
        existing_alert = self._find_similar_active_alert(rule_name, metric_name)
        if existing_alert:
            return  # Don't duplicate alerts
        
        alert = Alert(
            alert_id=alert_id,
            timestamp=datetime.now(),
            severity=severity,
            component=metric_name,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold
        )
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        # Update Prometheus metrics
        self.prometheus_metrics['crawler_alert_total'].labels(
            severity=severity.value,
            component=metric_name
        ).inc()
        
        # Send alert notifications
        await self._send_alert_notifications(alert)
        
        self.logger.warning(f"Alert triggered: {alert.message}")

    def _find_similar_active_alert(self, rule_name: str, metric_name: str) -> Optional[Alert]:
        """Find similar active alert to avoid duplicates"""
        for alert in self.active_alerts.values():
            if (alert.metric_name == metric_name and 
                not alert.resolved and
                rule_name in alert.alert_id):
                return alert
        return None

    async def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications through configured channels"""
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback failed: {e}")

    async def _process_alert_escalations(self):
        """Process alert escalations based on time and severity"""
        for alert in list(self.active_alerts.values()):
            if alert.resolved:
                continue
            
            time_since_alert = (datetime.now() - alert.timestamp).total_seconds()
            escalation_config = self.config.get('alert_escalation', {})
            
            # Check escalation thresholds
            for level, config in escalation_config.items():
                threshold_seconds = config.get('threshold_minutes', 15) * 60
                
                if (time_since_alert > threshold_seconds and 
                    alert.escalation_level < int(level.replace('level', ''))):
                    
                    await self._escalate_alert(alert, int(level.replace('level', '')))

    async def _escalate_alert(self, alert: Alert, new_level: int):
        """Escalate alert to higher level"""
        alert.escalation_level = new_level
        
        escalation_message = f"Alert escalated to level {new_level}: {alert.message}"
        self.logger.critical(escalation_message)
        
        # Create escalation alert
        escalation_alert = Alert(
            alert_id=f"{alert.alert_id}_escalation_{new_level}",
            timestamp=datetime.now(),
            severity=AlertSeverity.CRITICAL,
            component=alert.component,
            message=escalation_message,
            metric_name=alert.metric_name,
            metric_value=alert.metric_value,
            threshold=alert.threshold,
            correlation_id=alert.alert_id
        )
        
        await self._send_alert_notifications(escalation_alert)

    async def _health_check_loop(self):
        """Background health checks"""
        while self.is_running:
            try:
                await self._run_health_checks()
                
                interval = self.config.get('health_check_interval_seconds', 60)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in health checks: {e}")
                await asyncio.sleep(30)

    async def _run_health_checks(self):
        """Run all registered health checks"""
        for component, check_func in self.health_checks.items():
            try:
                is_healthy = await check_func()
                self.health_status[component] = {
                    'healthy': is_healthy,
                    'last_check': datetime.now(),
                    'status': 'healthy' if is_healthy else 'unhealthy'
                }
            except Exception as e:
                self.health_status[component] = {
                    'healthy': False,
                    'last_check': datetime.now(),
                    'status': 'error',
                    'error': str(e)
                }
                self.logger.error(f"Health check failed for {component}: {e}")

    async def _correlation_analysis_loop(self):
        """Background correlation analysis"""
        while self.is_running:
            try:
                await self.correlation_engine.analyze_correlations(self.metrics_history)
                await self.trend_analyzer.analyze_trends(self.metrics_history)
                await self.anomaly_detector.detect_anomalies(self.metrics_history)
                
                interval = self.config.get('correlation_interval_seconds', 300)
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in correlation analysis: {e}")
                await asyncio.sleep(60)

    async def _cleanup_loop(self):
        """Background cleanup of old data"""
        while self.is_running:
            try:
                await self._cleanup_old_data()
                
                # Run cleanup every hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(300)

    async def _cleanup_old_data(self):
        """Cleanup old metrics and alerts"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Clean up resolved alerts older than 24 hours
        old_alerts = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if alert.resolved and alert.resolution_time and alert.resolution_time < cutoff_time
        ]
        
        for alert_id in old_alerts:
            del self.active_alerts[alert_id]
        
        self.logger.debug(f"Cleaned up {len(old_alerts)} old alerts")

    # Public API methods
    def register_component(self, component_name: str, component_instance: Any):
        """Register a component for monitoring"""
        self.component_registry[component_name] = weakref.ref(component_instance)
        self.logger.info(f"Registered component: {component_name}")

    def register_health_check(self, component_name: str, check_function: Callable):
        """Register a health check function"""
        self.health_checks[component_name] = check_function
        self.logger.info(f"Registered health check for: {component_name}")

    def add_alert_callback(self, callback: Callable):
        """Add alert notification callback"""
        self.alert_callbacks.append(callback)

    async def record_metric(self, metric_name: str, value: float, 
                          labels: Optional[Dict[str, str]] = None,
                          metadata: Optional[Dict[str, Any]] = None):
        """Record a custom metric"""
        metric = MetricDataPoint(
            timestamp=datetime.now(),
            metric_name=metric_name,
            value=value,
            labels=labels or {},
            metadata=metadata or {}
        )
        
        self.metrics_history.append(metric)
        
        # Update aggregated metrics
        self._update_aggregated_metrics(metric)

    def _update_aggregated_metrics(self, metric: MetricDataPoint):
        """Update aggregated metrics for quick access"""
        key = f"{metric.metric_name}:{':'.join(f'{k}={v}' for k, v in metric.labels.items())}"
        
        if key not in self.aggregated_metrics:
            self.aggregated_metrics[key] = {
                'count': 0,
                'sum': 0,
                'avg': 0,
                'min': float('inf'),
                'max': float('-inf'),
                'last_value': 0,
                'last_update': None
            }
        
        agg = self.aggregated_metrics[key]
        agg['count'] += 1
        agg['sum'] += metric.value
        agg['avg'] = agg['sum'] / agg['count']
        agg['min'] = min(agg['min'], metric.value)
        agg['max'] = max(agg['max'], metric.value)
        agg['last_value'] = metric.value
        agg['last_update'] = metric.timestamp

    async def record_crawl_metrics(self, adapter_name: str, duration: float, 
                                 success: bool, results_count: int = 0,
                                 error_type: Optional[str] = None):
        """Record crawler-specific metrics"""
        # Record basic metrics
        status = 'success' if success else 'error'
        self.prometheus_metrics['crawler_requests_total'].labels(
            adapter=adapter_name, status=status
        ).inc()
        
        self.prometheus_metrics['crawler_duration_seconds'].labels(
            adapter=adapter_name
        ).observe(duration)
        
        # Record custom metrics
        await self.record_metric(
            f'crawler_duration_ms',
            duration * 1000,
            labels={'adapter': adapter_name, 'status': status}
        )
        
        if success:
            await self.record_metric(
                'crawler_results_count',
                results_count,
                labels={'adapter': adapter_name}
            )
        else:
            if error_type:
                self.prometheus_metrics['crawler_error_rate'].labels(
                    adapter=adapter_name, error_type=error_type
                ).inc()

    async def resolve_alert(self, alert_id: str, resolution_method: str = "manual"):
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolution_time = datetime.now()
            alert.metadata['resolution_method'] = resolution_method
            
            self.logger.info(f"Alert resolved: {alert_id} ({resolution_method})")

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary"""
        return {
            'system_status': {
                'is_running': self.is_running,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'registered_components': len(self.component_registry),
                'health_checks': len(self.health_checks)
            },
            'metrics': {
                'total_metrics': len(self.metrics_history),
                'aggregated_metrics': len(self.aggregated_metrics),
                'recent_metrics_count': len([
                    m for m in self.metrics_history 
                    if m.timestamp >= datetime.now() - timedelta(minutes=5)
                ])
            },
            'alerts': {
                'active_alerts': len(self.active_alerts),
                'total_alerts': len(self.alert_history),
                'alert_rules': len(self.alert_rules)
            },
            'health_status': dict(self.health_status),
            'background_tasks': len(self.monitoring_tasks)
        }

    async def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_running = False
        
        # Cancel background tasks
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        
        self.logger.info("Enhanced monitoring system stopped")


class CorrelationEngine:
    """Engine for analyzing metric correlations"""
    
    def __init__(self):
        self.correlations: Dict[str, Dict] = {}
    
    async def analyze_correlations(self, metrics: deque):
        """Analyze correlations between metrics"""
        # Implementation for correlation analysis
        pass


class TrendAnalyzer:
    """Analyzer for detecting trends in metrics"""
    
    def __init__(self):
        self.trends: Dict[str, Dict] = {}
    
    async def analyze_trends(self, metrics: deque):
        """Analyze trends in metrics"""
        # Implementation for trend analysis
        pass


class AnomalyDetector:
    """Detector for metric anomalies"""
    
    def __init__(self):
        self.anomalies: List[Dict] = []
    
    async def detect_anomalies(self, metrics: deque):
        """Detect anomalies in metrics"""
        # Implementation for anomaly detection
        pass


# Global monitoring instance
_global_monitoring = None


def get_global_monitoring() -> EnhancedMonitoringSystem:
    """Get global monitoring system instance"""
    global _global_monitoring
    if _global_monitoring is None:
        _global_monitoring = EnhancedMonitoringSystem()
    return _global_monitoring


def initialize_global_monitoring(config: Dict[str, Any]) -> EnhancedMonitoringSystem:
    """Initialize global monitoring system with configuration"""
    global _global_monitoring
    _global_monitoring = EnhancedMonitoringSystem(config)
    return _global_monitoring 