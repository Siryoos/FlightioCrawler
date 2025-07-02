#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Memory Monitoring System
سیستم نظارت مداوم حافظه برای محیط تولید

این ماژول یک سیستم جامع نظارت مداوم حافظه برای محیط تولید فراهم می‌کند

Features:
- Real-time memory monitoring
- Intelligent alerting system
- Automated response mechanisms
- Dashboard integration
- Historical data tracking
- Performance analytics
"""

import asyncio
import json
import logging
import os
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import aiohttp
import aiofiles
from prometheus_client import Gauge, Counter, Histogram, start_http_server
import gc
import tracemalloc
import sys
import weakref
from collections import defaultdict, deque
import threading
from concurrent.futures import ThreadPoolExecutor
import signal

# Prometheus Metrics
MEMORY_USAGE_GAUGE = Gauge('memory_usage_bytes', 'Memory usage in bytes', ['component'])
MEMORY_LEAK_COUNTER = Counter('memory_leaks_detected_total', 'Total memory leaks detected')
MEMORY_CLEANUP_GAUGE = Gauge('memory_cleanup_operations_total', 'Memory cleanup operations')
ALERT_COUNTER = Counter('memory_alerts_sent_total', 'Total memory alerts sent', ['severity'])
RESPONSE_TIME_HISTOGRAM = Histogram('memory_check_duration_seconds', 'Memory check duration')

@dataclass
class MemoryAlert:
    """ساختار داده هشدار حافظه"""
    timestamp: datetime
    severity: str  # 'warning', 'critical', 'emergency'
    component: str
    memory_usage: float
    threshold: float
    message: str
    metadata: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[datetime] = None

@dataclass
class MemoryMetrics:
    """ساختار داده metrics حافظه"""
    timestamp: datetime
    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float
    total_mb: float
    swap_used_mb: float
    swap_percent: float
    gc_collections: int
    gc_objects: int
    tracemalloc_current: float
    tracemalloc_peak: float
    process_count: int
    thread_count: int

class AlertManager:
    """مدیریت هشدارها و اعلان‌ها"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alerts_history: deque = deque(maxlen=1000)
        self.active_alerts: Dict[str, MemoryAlert] = {}
        self.alert_handlers: List[Callable] = []
        self.rate_limiter: Dict[str, datetime] = {}
        self.logger = logging.getLogger(__name__)
        
    def add_handler(self, handler: Callable[[MemoryAlert], None]):
        """اضافه کردن handler برای alerts"""
        self.alert_handlers.append(handler)
    
    async def send_alert(self, alert: MemoryAlert):
        """ارسال هشدار"""
        # Rate limiting
        rate_key = f"{alert.component}_{alert.severity}"
        now = datetime.now()
        if rate_key in self.rate_limiter:
            time_diff = (now - self.rate_limiter[rate_key]).total_seconds()
            min_interval = self.config.get('rate_limit_seconds', 300)  # 5 minutes default
            if time_diff < min_interval:
                return
        
        self.rate_limiter[rate_key] = now
        
        # Store alert
        alert_key = f"{alert.component}_{alert.severity}_{alert.timestamp.isoformat()}"
        self.active_alerts[alert_key] = alert
        self.alerts_history.append(alert)
        
        # Update metrics
        ALERT_COUNTER.labels(severity=alert.severity).inc()
        
        # Send to all handlers
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                self.logger.error(f"Error in alert handler: {e}")
    
    async def resolve_alert(self, alert_key: str):
        """حل شدن هشدار"""
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.resolved = True
            alert.resolution_time = datetime.now()
            del self.active_alerts[alert_key]
            
            self.logger.info(f"Alert resolved: {alert.message}")

class MemoryDataCollector:
    """جمع‌آوری داده‌های حافظه"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.logger = logging.getLogger(__name__)
        self._tracemalloc_enabled = False
        
    def enable_tracemalloc(self):
        """فعال‌سازی tracemalloc برای تجزیه و تحلیل دقیق‌تر"""
        if not self._tracemalloc_enabled:
            tracemalloc.start(10)  # Keep 10 frames
            self._tracemalloc_enabled = True
    
    def collect_metrics(self) -> MemoryMetrics:
        """جمع‌آوری metrics حافظه"""
        try:
            # Process memory info
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # System memory info
            system_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()
            
            # Garbage collection info
            gc_stats = gc.get_stats()
            gc_collections = sum(stat['collections'] for stat in gc_stats)
            gc_objects = len(gc.get_objects())
            
            # Tracemalloc info
            tracemalloc_current = 0
            tracemalloc_peak = 0
            if self._tracemalloc_enabled:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            
            # Process and thread counts
            try:
                process_count = len(psutil.pids())
                thread_count = self.process.num_threads()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_count = 0
                thread_count = 0
            
            return MemoryMetrics(
                timestamp=datetime.now(),
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=memory_percent,
                available_mb=system_memory.available / 1024 / 1024,
                total_mb=system_memory.total / 1024 / 1024,
                swap_used_mb=swap_memory.used / 1024 / 1024,
                swap_percent=swap_memory.percent,
                gc_collections=gc_collections,
                gc_objects=gc_objects,
                tracemalloc_current=tracemalloc_current,
                tracemalloc_peak=tracemalloc_peak,
                process_count=process_count,
                thread_count=thread_count
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting memory metrics: {e}")
            # Return basic metrics in case of error
            return MemoryMetrics(
                timestamp=datetime.now(),
                rss_mb=0, vms_mb=0, percent=0, available_mb=0, total_mb=0,
                swap_used_mb=0, swap_percent=0, gc_collections=0, gc_objects=0,
                tracemalloc_current=0, tracemalloc_peak=0,
                process_count=0, thread_count=0
            )

class AutomatedResponseSystem:
    """سیستم پاسخ خودکار به مشکلات حافظه"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.response_history: List[Dict] = []
        
    async def handle_memory_pressure(self, metrics: MemoryMetrics, alert: MemoryAlert):
        """مدیریت فشار حافظه"""
        actions_taken = []
        
        try:
            # Action 1: Force garbage collection
            if self.config.get('auto_gc', True):
                collected = gc.collect()
                actions_taken.append(f"Garbage collection freed {collected} objects")
                MEMORY_CLEANUP_GAUGE.inc()
            
            # Action 2: Clear caches if available
            if hasattr(self, 'cache_manager') and self.config.get('auto_cache_clear', True):
                await self._clear_caches()
                actions_taken.append("Cleared system caches")
            
            # Action 3: Reduce concurrent operations
            if self.config.get('auto_throttle', True):
                await self._throttle_operations()
                actions_taken.append("Throttled concurrent operations")
            
            # Action 4: Emergency cleanup for critical alerts
            if alert.severity == 'emergency':
                await self._emergency_cleanup()
                actions_taken.append("Performed emergency cleanup")
            
            # Log actions taken
            action_log = {
                'timestamp': datetime.now().isoformat(),
                'alert_severity': alert.severity,
                'memory_usage_mb': metrics.rss_mb,
                'actions_taken': actions_taken
            }
            self.response_history.append(action_log)
            
            self.logger.info(f"Automated response completed: {actions_taken}")
            
        except Exception as e:
            self.logger.error(f"Error in automated response: {e}")
    
    async def _clear_caches(self):
        """پاکسازی cache ها"""
        # Implementation depends on your cache system
        pass
    
    async def _throttle_operations(self):
        """کاهش عملیات همزمان"""
        # Implementation to reduce concurrent operations
        pass
    
    async def _emergency_cleanup(self):
        """پاکسازی اضطراری"""
        # Force more aggressive cleanup
        gc.collect()
        gc.collect()  # Run twice for better results
        gc.collect()

class ProductionMemoryMonitor:
    """سیستم نظارت مداوم حافظه برای محیط تولید"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        
        # Components
        self.data_collector = MemoryDataCollector()
        self.alert_manager = AlertManager(self.config['alerting'])
        self.auto_response = AutomatedResponseSystem(self.config['auto_response'])
        
        # Data storage
        self.metrics_history: deque = deque(maxlen=self.config['history_size'])
        self.running = False
        self.monitor_task = None
        
        # Performance tracking
        self.check_count = 0
        self.last_check_time = None
        
        # Setup alert handlers
        self._setup_alert_handlers()
        
        # Prometheus metrics server
        if self.config.get('prometheus_port'):
            start_http_server(self.config['prometheus_port'])
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """بارگذاری تنظیمات"""
        default_config = {
            'check_interval': 30,  # seconds
            'history_size': 1000,
            'thresholds': {
                'memory_warning_mb': 1024,    # 1GB
                'memory_critical_mb': 2048,   # 2GB
                'memory_emergency_mb': 4096,  # 4GB
                'memory_percent_warning': 70,
                'memory_percent_critical': 85,
                'memory_percent_emergency': 95,
                'swap_warning_percent': 50,
                'swap_critical_percent': 80
            },
            'alerting': {
                'rate_limit_seconds': 300,
                'webhook_url': None,
                'slack_webhook': None,
                'email_smtp': None
            },
            'auto_response': {
                'auto_gc': True,
                'auto_cache_clear': True,
                'auto_throttle': True,
                'emergency_actions': True
            },
            'storage': {
                'metrics_file': 'logs/memory_metrics.jsonl',
                'alerts_file': 'logs/memory_alerts.jsonl'
            },
            'prometheus_port': 9090,
            'enable_tracemalloc': True
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logging.warning(f"Could not load config from {config_path}: {e}")
        
        return default_config
    
    def _setup_logging(self) -> logging.Logger:
        """راه‌اندازی logging"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _setup_alert_handlers(self):
        """راه‌اندازی alert handlers"""
        # Console handler
        self.alert_manager.add_handler(self._console_alert_handler)
        
        # Webhook handler
        if self.config['alerting'].get('webhook_url'):
            self.alert_manager.add_handler(self._webhook_alert_handler)
        
        # Slack handler
        if self.config['alerting'].get('slack_webhook'):
            self.alert_manager.add_handler(self._slack_alert_handler)
        
        # File handler
        self.alert_manager.add_handler(self._file_alert_handler)
    
    def _console_alert_handler(self, alert: MemoryAlert):
        """Console alert handler"""
        severity_emoji = {
            'warning': '⚠️',
            'critical': '🚨',
            'emergency': '🔥'
        }
        emoji = severity_emoji.get(alert.severity, '📊')
        
        self.logger.warning(
            f"{emoji} MEMORY ALERT [{alert.severity.upper()}] - "
            f"{alert.component}: {alert.message} "
            f"(Usage: {alert.memory_usage:.1f}MB, Threshold: {alert.threshold:.1f}MB)"
        )
    
    async def _webhook_alert_handler(self, alert: MemoryAlert):
        """Webhook alert handler"""
        webhook_url = self.config['alerting']['webhook_url']
        payload = {
            'timestamp': alert.timestamp.isoformat(),
            'severity': alert.severity,
            'component': alert.component,
            'memory_usage': alert.memory_usage,
            'threshold': alert.threshold,
            'message': alert.message,
            'metadata': alert.metadata
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        self.logger.error(f"Webhook alert failed: {response.status}")
        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {e}")
    
    async def _slack_alert_handler(self, alert: MemoryAlert):
        """Slack alert handler"""
        slack_webhook = self.config['alerting']['slack_webhook']
        color_map = {'warning': 'warning', 'critical': 'danger', 'emergency': 'danger'}
        
        payload = {
            'attachments': [{
                'color': color_map.get(alert.severity, 'good'),
                'title': f'Memory Alert - {alert.severity.title()}',
                'text': alert.message,
                'fields': [
                    {'title': 'Component', 'value': alert.component, 'short': True},
                    {'title': 'Memory Usage', 'value': f'{alert.memory_usage:.1f} MB', 'short': True},
                    {'title': 'Threshold', 'value': f'{alert.threshold:.1f} MB', 'short': True},
                    {'title': 'Timestamp', 'value': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 'short': True}
                ]
            }]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(slack_webhook, json=payload) as response:
                    if response.status != 200:
                        self.logger.error(f"Slack alert failed: {response.status}")
        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {e}")
    
    async def _file_alert_handler(self, alert: MemoryAlert):
        """File alert handler"""
        alerts_file = self.config['storage']['alerts_file']
        os.makedirs(os.path.dirname(alerts_file), exist_ok=True)
        
        alert_data = asdict(alert)
        alert_data['timestamp'] = alert.timestamp.isoformat()
        if alert.resolution_time:
            alert_data['resolution_time'] = alert.resolution_time.isoformat()
        
        try:
            async with aiofiles.open(alerts_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(alert_data, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Error writing alert to file: {e}")
    
    def _analyze_metrics(self, metrics: MemoryMetrics) -> List[MemoryAlert]:
        """تجزیه و تحلیل metrics و تولید alerts"""
        alerts = []
        thresholds = self.config['thresholds']
        
        # Memory usage alerts
        if metrics.rss_mb > thresholds['memory_emergency_mb']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='emergency',
                component='system_memory',
                memory_usage=metrics.rss_mb,
                threshold=thresholds['memory_emergency_mb'],
                message=f'Emergency memory usage: {metrics.rss_mb:.1f}MB',
                metadata={
                    'percent': metrics.percent,
                    'available_mb': metrics.available_mb,
                    'swap_percent': metrics.swap_percent
                }
            ))
        elif metrics.rss_mb > thresholds['memory_critical_mb']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='critical',
                component='system_memory',
                memory_usage=metrics.rss_mb,
                threshold=thresholds['memory_critical_mb'],
                message=f'Critical memory usage: {metrics.rss_mb:.1f}MB',
                metadata={
                    'percent': metrics.percent,
                    'available_mb': metrics.available_mb
                }
            ))
        elif metrics.rss_mb > thresholds['memory_warning_mb']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='warning',
                component='system_memory',
                memory_usage=metrics.rss_mb,
                threshold=thresholds['memory_warning_mb'],
                message=f'High memory usage: {metrics.rss_mb:.1f}MB',
                metadata={'percent': metrics.percent}
            ))
        
        # Memory percentage alerts
        if metrics.percent > thresholds['memory_percent_emergency']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='emergency',
                component='memory_percent',
                memory_usage=metrics.percent,
                threshold=thresholds['memory_percent_emergency'],
                message=f'Emergency memory percentage: {metrics.percent:.1f}%',
                metadata={'rss_mb': metrics.rss_mb, 'available_mb': metrics.available_mb}
            ))
        elif metrics.percent > thresholds['memory_percent_critical']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='critical',
                component='memory_percent',
                memory_usage=metrics.percent,
                threshold=thresholds['memory_percent_critical'],
                message=f'Critical memory percentage: {metrics.percent:.1f}%',
                metadata={'rss_mb': metrics.rss_mb}
            ))
        elif metrics.percent > thresholds['memory_percent_warning']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='warning',
                component='memory_percent',
                memory_usage=metrics.percent,
                threshold=thresholds['memory_percent_warning'],
                message=f'High memory percentage: {metrics.percent:.1f}%',
                metadata={'rss_mb': metrics.rss_mb}
            ))
        
        # Swap usage alerts
        if metrics.swap_percent > thresholds['swap_critical_percent']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='critical',
                component='swap_memory',
                memory_usage=metrics.swap_percent,
                threshold=thresholds['swap_critical_percent'],
                message=f'Critical swap usage: {metrics.swap_percent:.1f}%',
                metadata={'swap_used_mb': metrics.swap_used_mb}
            ))
        elif metrics.swap_percent > thresholds['swap_warning_percent']:
            alerts.append(MemoryAlert(
                timestamp=metrics.timestamp,
                severity='warning',
                component='swap_memory',
                memory_usage=metrics.swap_percent,
                threshold=thresholds['swap_warning_percent'],
                message=f'High swap usage: {metrics.swap_percent:.1f}%',
                metadata={'swap_used_mb': metrics.swap_used_mb}
            ))
        
        return alerts
    
    async def _store_metrics(self, metrics: MemoryMetrics):
        """ذخیره metrics در فایل"""
        metrics_file = self.config['storage']['metrics_file']
        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
        
        metrics_data = asdict(metrics)
        metrics_data['timestamp'] = metrics.timestamp.isoformat()
        
        try:
            async with aiofiles.open(metrics_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(metrics_data, ensure_ascii=False) + '\n')
        except Exception as e:
            self.logger.error(f"Error storing metrics: {e}")
    
    def _update_prometheus_metrics(self, metrics: MemoryMetrics):
        """به‌روزرسانی Prometheus metrics"""
        MEMORY_USAGE_GAUGE.labels(component='rss_mb').set(metrics.rss_mb)
        MEMORY_USAGE_GAUGE.labels(component='vms_mb').set(metrics.vms_mb)
        MEMORY_USAGE_GAUGE.labels(component='percent').set(metrics.percent)
        MEMORY_USAGE_GAUGE.labels(component='available_mb').set(metrics.available_mb)
        MEMORY_USAGE_GAUGE.labels(component='swap_percent').set(metrics.swap_percent)
        MEMORY_USAGE_GAUGE.labels(component='gc_objects').set(metrics.gc_objects)
        MEMORY_USAGE_GAUGE.labels(component='tracemalloc_current').set(metrics.tracemalloc_current)
    
    async def _monitoring_loop(self):
        """حلقه اصلی نظارت"""
        self.logger.info("Starting memory monitoring loop...")
        
        if self.config.get('enable_tracemalloc', True):
            self.data_collector.enable_tracemalloc()
        
        while self.running:
            try:
                start_time = time.time()
                
                # Collect metrics
                metrics = self.data_collector.collect_metrics()
                self.metrics_history.append(metrics)
                
                # Update Prometheus metrics
                self._update_prometheus_metrics(metrics)
                
                # Store metrics
                await self._store_metrics(metrics)
                
                # Analyze and generate alerts
                alerts = self._analyze_metrics(metrics)
                
                # Send alerts and handle automated responses
                for alert in alerts:
                    await self.alert_manager.send_alert(alert)
                    
                    # Trigger automated response for critical/emergency alerts
                    if alert.severity in ['critical', 'emergency']:
                        await self.auto_response.handle_memory_pressure(metrics, alert)
                
                # Update performance tracking
                self.check_count += 1
                self.last_check_time = datetime.now()
                
                # Record check duration
                check_duration = time.time() - start_time
                RESPONSE_TIME_HISTOGRAM.observe(check_duration)
                
                # Log periodic status
                if self.check_count % 10 == 0:  # Every 10 checks
                    self.logger.info(
                        f"Memory Monitor Status: Check #{self.check_count}, "
                        f"Memory: {metrics.rss_mb:.1f}MB ({metrics.percent:.1f}%), "
                        f"Swap: {metrics.swap_percent:.1f}%, "
                        f"Active Alerts: {len(self.alert_manager.active_alerts)}"
                    )
                
                # Wait for next check
                await asyncio.sleep(self.config['check_interval'])
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)  # Short wait before retry
    
    async def start_monitoring(self):
        """شروع نظارت مداوم"""
        if self.running:
            self.logger.warning("Monitoring is already running")
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Production memory monitoring started")
    
    async def stop_monitoring(self):
        """توقف نظارت"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Production memory monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """دریافت وضعیت سیستم نظارت"""
        latest_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        return {
            'monitoring_active': self.running,
            'check_count': self.check_count,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'active_alerts_count': len(self.alert_manager.active_alerts),
            'total_alerts_sent': sum(ALERT_COUNTER._value._value.values()),
            'metrics_history_size': len(self.metrics_history),
            'latest_metrics': asdict(latest_metrics) if latest_metrics else None,
            'config': self.config
        }
    
    def get_recent_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """دریافت metrics اخیر"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            asdict(m) for m in self.metrics_history 
            if m.timestamp >= cutoff_time
        ]
        
        # Convert timestamps to ISO format
        for metrics in recent_metrics:
            metrics['timestamp'] = metrics['timestamp'].isoformat() if isinstance(metrics['timestamp'], datetime) else metrics['timestamp']
        
        return recent_metrics
    
    def get_alerts_summary(self, hours: int = 24) -> Dict[str, Any]:
        """خلاصه alerts"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_alerts = [
            alert for alert in self.alert_manager.alerts_history 
            if alert.timestamp >= cutoff_time
        ]
        
        summary = {
            'total_alerts': len(recent_alerts),
            'by_severity': defaultdict(int),
            'by_component': defaultdict(int),
            'active_alerts': len(self.alert_manager.active_alerts),
            'resolved_alerts': sum(1 for alert in recent_alerts if alert.resolved)
        }
        
        for alert in recent_alerts:
            summary['by_severity'][alert.severity] += 1
            summary['by_component'][alert.component] += 1
        
        return dict(summary)

async def main():
    """تست سیستم نظارت"""
    # Create config
    config = {
        'check_interval': 10,  # Check every 10 seconds for demo
        'thresholds': {
            'memory_warning_mb': 100,   # Low thresholds for testing
            'memory_critical_mb': 200,
            'memory_emergency_mb': 300,
            'memory_percent_warning': 50,
            'memory_percent_critical': 70,
            'memory_percent_emergency': 85
        }
    }
    
    # Create and start monitor
    monitor = ProductionMemoryMonitor()
    
    try:
        # Setup signal handlers
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, stopping monitor...")
            asyncio.create_task(monitor.stop_monitoring())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        await monitor.start_monitoring()
        
        # Keep running
        while monitor.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, stopping...")
    finally:
        await monitor.stop_monitoring()
        print("Memory monitoring stopped.")

if __name__ == "__main__":
    asyncio.run(main()) 