"""
Enhanced Prometheus Metrics System for FlightIO Crawler
Provides comprehensive metrics collection, aggregation, and exposure
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from collections import defaultdict, deque
import json
import psutil
import os
from pathlib import Path

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info, Enum,
    generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    CollectorRegistry, multiprocess, start_http_server,
    push_to_gateway, pushadd_to_gateway
)
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST as OPENMETRICS_CONTENT_TYPE
from prometheus_client.openmetrics.exposition import generate_latest as openmetrics_generate_latest


@dataclass
class MetricConfig:
    """Configuration for a metric"""
    name: str
    help: str
    labels: List[str] = None
    buckets: List[float] = None
    quantiles: List[float] = None


class EnhancedPrometheusMetrics:
    """Enhanced Prometheus metrics collector with comprehensive business and system metrics"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None, namespace: str = "flightio"):
        self.registry = registry or REGISTRY
        self.namespace = namespace
        self.logger = logging.getLogger(__name__)
        
        # Internal state
        self.start_time = time.time()
        self.last_scrape_time = time.time()
        self.metrics_history = deque(maxlen=1000)
        
        # Process and system info
        self.process = psutil.Process()
        
        # Initialize all metrics
        self._init_crawler_metrics()
        self._init_business_metrics()
        self._init_system_metrics()
        self._init_performance_metrics()
        self._init_error_metrics()
        self._init_cache_metrics()
        self._init_security_metrics()
        
        # Custom collectors
        self._custom_collectors = {}
        
        self.logger.info(f"Enhanced Prometheus metrics initialized with namespace: {namespace}")
    
    def _init_crawler_metrics(self):
        """Initialize crawler-specific metrics"""
        # Request metrics
        self.crawler_requests_total = Counter(
            'crawler_requests_total',
            'Total HTTP requests made by crawlers',
            ['site', 'status', 'method'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.crawler_request_duration_seconds = Histogram(
            'crawler_request_duration_seconds',
            'Duration of HTTP requests in seconds',
            ['site', 'method'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.crawler_response_size_bytes = Histogram(
            'crawler_response_size_bytes',
            'Size of HTTP responses in bytes',
            ['site'],
            buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Crawler state metrics
        self.crawler_active_sessions = Gauge(
            'crawler_active_sessions',
            'Number of active crawler sessions',
            ['site'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.crawler_success_rate = Gauge(
            'crawler_success_rate',
            'Success rate of crawler requests (0-1)',
            ['site'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.crawler_avg_response_time_seconds = Gauge(
            'crawler_avg_response_time_seconds',
            'Average response time for crawler requests',
            ['site'],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_business_metrics(self):
        """Initialize business-specific metrics"""
        # Flight search metrics
        self.flight_searches_total = Counter(
            'flight_searches_total',
            'Total number of flight searches performed',
            ['site', 'route_type', 'cabin_class'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.flight_results_found_total = Counter(
            'flight_results_found_total',
            'Total number of flight results found',
            ['site', 'route_type'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.flight_search_duration_seconds = Histogram(
            'flight_search_duration_seconds',
            'Duration of flight search operations',
            ['site', 'route_type'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Price metrics
        self.flight_price_distribution = Histogram(
            'flight_price_distribution',
            'Distribution of flight prices',
            ['site', 'route_type', 'currency'],
            buckets=[50, 100, 200, 500, 1000, 2000, 5000, 10000, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.flight_price_changes_total = Counter(
            'flight_price_changes_total',
            'Total number of price changes detected',
            ['site', 'route', 'direction'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Route metrics
        self.popular_routes_requests = Counter(
            'popular_routes_requests',
            'Requests for popular routes',
            ['origin', 'destination', 'site'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Booking metrics
        self.booking_attempts_total = Counter(
            'booking_attempts_total',
            'Total booking attempts',
            ['site', 'status'],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_system_metrics(self):
        """Initialize system-level metrics"""
        # Memory metrics
        self.system_memory_usage_bytes = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes',
            ['type'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # CPU metrics
        self.system_cpu_usage_percent = Gauge(
            'system_cpu_usage_percent',
            'System CPU usage percentage',
            ['cpu'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Disk metrics
        self.system_disk_usage_bytes = Gauge(
            'system_disk_usage_bytes',
            'System disk usage in bytes',
            ['mount_point', 'type'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Network metrics
        self.system_network_io_bytes = Counter(
            'system_network_io_bytes',
            'System network I/O in bytes',
            ['interface', 'direction'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Process metrics
        self.process_open_files = Gauge(
            'process_open_files',
            'Number of open files by the process',
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.process_memory_rss_bytes = Gauge(
            'process_memory_rss_bytes',
            'Process RSS memory usage in bytes',
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.process_cpu_percent = Gauge(
            'process_cpu_percent',
            'Process CPU usage percentage',
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_performance_metrics(self):
        """Initialize performance metrics"""
        # Database metrics
        self.database_connections_active = Gauge(
            'database_connections_active',
            'Active database connections',
            ['database'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.database_query_duration_seconds = Histogram(
            'database_query_duration_seconds',
            'Database query duration in seconds',
            ['operation', 'table'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Queue metrics
        self.queue_size = Gauge(
            'queue_size',
            'Current queue size',
            ['queue_name'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.queue_processing_time_seconds = Histogram(
            'queue_processing_time_seconds',
            'Time spent processing queue items',
            ['queue_name'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.api_request_duration_seconds = Histogram(
            'api_request_duration_seconds',
            'API request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_error_metrics(self):
        """Initialize error tracking metrics"""
        # Error counters
        self.errors_total = Counter(
            'errors_total',
            'Total errors by type and severity',
            ['error_type', 'severity', 'component'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half-open)',
            ['service', 'method'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.circuit_breaker_failures = Counter(
            'circuit_breaker_failures',
            'Circuit breaker failure count',
            ['service', 'method'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Retry metrics
        self.retry_attempts_total = Counter(
            'retry_attempts_total',
            'Total retry attempts',
            ['operation', 'reason'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.retry_success_total = Counter(
            'retry_success_total',
            'Successful retries',
            ['operation'],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_cache_metrics(self):
        """Initialize cache metrics"""
        # Cache hits/misses
        self.cache_operations_total = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['cache_name', 'operation', 'result'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Cache size and memory
        self.cache_size_bytes = Gauge(
            'cache_size_bytes',
            'Cache size in bytes',
            ['cache_name'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.cache_entries_total = Gauge(
            'cache_entries_total',
            'Total cache entries',
            ['cache_name'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Cache performance
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio (0-1)',
            ['cache_name'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        self.cache_evictions_total = Counter(
            'cache_evictions_total',
            'Total cache evictions',
            ['cache_name', 'reason'],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def _init_security_metrics(self):
        """Initialize security metrics"""
        # Authentication metrics
        self.auth_attempts_total = Counter(
            'auth_attempts_total',
            'Total authentication attempts',
            ['method', 'result'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Rate limiting metrics
        self.rate_limit_hits_total = Counter(
            'rate_limit_hits_total',
            'Total rate limit hits',
            ['endpoint', 'client_type'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Security events
        self.security_events_total = Counter(
            'security_events_total',
            'Total security events',
            ['event_type', 'severity'],
            registry=self.registry,
            namespace=self.namespace
        )
        
        # Active sessions
        self.active_sessions_total = Gauge(
            'active_sessions_total',
            'Total active sessions',
            ['session_type'],
            registry=self.registry,
            namespace=self.namespace
        )
    
    def record_crawler_request(self, site: str, method: str, status: str, 
                             duration: float, response_size: int = 0):
        """Record a crawler request"""
        self.crawler_requests_total.labels(site=site, status=status, method=method).inc()
        self.crawler_request_duration_seconds.labels(site=site, method=method).observe(duration)
        
        if response_size > 0:
            self.crawler_response_size_bytes.labels(site=site).observe(response_size)
    
    def record_flight_search(self, site: str, route_type: str, cabin_class: str, 
                           duration: float, results_count: int):
        """Record a flight search operation"""
        self.flight_searches_total.labels(site=site, route_type=route_type, cabin_class=cabin_class).inc()
        self.flight_search_duration_seconds.labels(site=site, route_type=route_type).observe(duration)
        self.flight_results_found_total.labels(site=site, route_type=route_type).inc(results_count)
    
    def record_price_change(self, site: str, route: str, direction: str, 
                          old_price: float, new_price: float, currency: str):
        """Record a price change"""
        self.flight_price_changes_total.labels(site=site, route=route, direction=direction).inc()
        self.flight_price_distribution.labels(site=site, route_type="unknown", currency=currency).observe(new_price)
    
    def record_error(self, error_type: str, severity: str, component: str):
        """Record an error"""
        self.errors_total.labels(error_type=error_type, severity=severity, component=component).inc()
    
    def record_circuit_breaker_state(self, service: str, method: str, state: int):
        """Record circuit breaker state (0=closed, 1=open, 2=half-open)"""
        self.circuit_breaker_state.labels(service=service, method=method).set(state)
    
    def record_cache_operation(self, cache_name: str, operation: str, result: str):
        """Record a cache operation"""
        self.cache_operations_total.labels(cache_name=cache_name, operation=operation, result=result).inc()
    
    def record_auth_attempt(self, method: str, result: str):
        """Record an authentication attempt"""
        self.auth_attempts_total.labels(method=method, result=result).inc()
    
    def record_rate_limit_hit(self, endpoint: str, client_type: str):
        """Record a rate limit hit"""
        self.rate_limit_hits_total.labels(endpoint=endpoint, client_type=client_type).inc()
    
    def record_security_event(self, event_type: str, severity: str):
        """Record a security event"""
        self.security_events_total.labels(event_type=event_type, severity=severity).inc()
    
    def update_system_metrics(self):
        """Update system-level metrics"""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            self.system_memory_usage_bytes.labels(type='used').set(memory.used)
            self.system_memory_usage_bytes.labels(type='available').set(memory.available)
            self.system_memory_usage_bytes.labels(type='total').set(memory.total)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(percpu=True)
            for i, cpu in enumerate(cpu_percent):
                self.system_cpu_usage_percent.labels(cpu=f'cpu{i}').set(cpu)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.system_disk_usage_bytes.labels(mount_point='/', type='used').set(disk.used)
            self.system_disk_usage_bytes.labels(mount_point='/', type='free').set(disk.free)
            self.system_disk_usage_bytes.labels(mount_point='/', type='total').set(disk.total)
            
            # Process metrics
            self.process_memory_rss_bytes.set(self.process.memory_info().rss)
            self.process_cpu_percent.set(self.process.cpu_percent())
            
            try:
                self.process_open_files.set(len(self.process.open_files()))
            except psutil.AccessDenied:
                pass
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def update_cache_metrics(self, cache_stats: Dict[str, Any]):
        """Update cache metrics from cache statistics"""
        for cache_name, stats in cache_stats.items():
            if 'size_bytes' in stats:
                self.cache_size_bytes.labels(cache_name=cache_name).set(stats['size_bytes'])
            if 'entry_count' in stats:
                self.cache_entries_total.labels(cache_name=cache_name).set(stats['entry_count'])
            if 'hit_ratio' in stats:
                self.cache_hit_ratio.labels(cache_name=cache_name).set(stats['hit_ratio'])
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics"""
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': time.time() - self.start_time,
            'last_scrape_age_seconds': time.time() - self.last_scrape_time,
            'total_metrics_registered': len(list(self.registry._collector_to_names.keys())),
            'system_info': {
                'memory_usage_mb': self.process.memory_info().rss / 1024 / 1024,
                'cpu_percent': self.process.cpu_percent(),
                'open_files': len(self.process.open_files()) if hasattr(self.process, 'open_files') else 0
            }
        }
    
    def export_metrics(self, format_type: str = 'prometheus') -> str:
        """Export metrics in specified format"""
        self.last_scrape_time = time.time()
        
        if format_type == 'openmetrics':
            return openmetrics_generate_latest(self.registry)
        else:
            return generate_latest(self.registry)
    
    def export_metrics_to_file(self, filename: str, format_type: str = 'prometheus'):
        """Export metrics to file"""
        try:
            metrics_data = self.export_metrics(format_type)
            with open(filename, 'w') as f:
                f.write(metrics_data)
            self.logger.info(f"Metrics exported to {filename}")
        except Exception as e:
            self.logger.error(f"Error exporting metrics to file: {e}")
    
    def start_metrics_server(self, port: int = 9090, addr: str = '0.0.0.0'):
        """Start Prometheus metrics server"""
        try:
            start_http_server(port, addr, registry=self.registry)
            self.logger.info(f"Prometheus metrics server started on {addr}:{port}")
        except Exception as e:
            self.logger.error(f"Error starting metrics server: {e}")
    
    def push_metrics_to_gateway(self, gateway_url: str, job_name: str, grouping_key: Dict[str, str] = None):
        """Push metrics to Prometheus Pushgateway"""
        try:
            if grouping_key:
                pushadd_to_gateway(gateway_url, job=job_name, registry=self.registry, grouping_key=grouping_key)
            else:
                push_to_gateway(gateway_url, job=job_name, registry=self.registry)
            self.logger.info(f"Metrics pushed to gateway: {gateway_url}")
        except Exception as e:
            self.logger.error(f"Error pushing metrics to gateway: {e}")
    
    async def start_periodic_updates(self, interval: int = 30):
        """Start periodic metrics updates"""
        while True:
            try:
                self.update_system_metrics()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error in periodic metrics update: {e}")
                await asyncio.sleep(interval)


# Global instance
enhanced_metrics = EnhancedPrometheusMetrics()

# Convenience functions
def get_metrics_instance() -> EnhancedPrometheusMetrics:
    """Get the global metrics instance"""
    return enhanced_metrics

def record_crawler_request(site: str, method: str, status: str, duration: float, response_size: int = 0):
    """Record a crawler request"""
    enhanced_metrics.record_crawler_request(site, method, status, duration, response_size)

def record_flight_search(site: str, route_type: str, cabin_class: str, duration: float, results_count: int):
    """Record a flight search operation"""
    enhanced_metrics.record_flight_search(site, route_type, cabin_class, duration, results_count)

def record_error(error_type: str, severity: str, component: str):
    """Record an error"""
    enhanced_metrics.record_error(error_type, severity, component)

def export_metrics(format_type: str = 'prometheus') -> str:
    """Export metrics in specified format"""
    return enhanced_metrics.export_metrics(format_type) 