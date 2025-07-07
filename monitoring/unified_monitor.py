"""
Unified Monitoring System for FlightIO
Consolidates all monitoring functionality into a single, efficient module
"""

import asyncio
import time
import psutil
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

from prometheus_client import Counter, Gauge, Histogram, generate_latest
import aiohttp
from aiohttp import web


logger = logging.getLogger(__name__)


class UnifiedMonitor:
    """
    Single monitoring class that handles:
    - Performance metrics
    - Memory monitoring
    - Health checks
    - Error tracking
    - Prometheus metrics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.start_time = time.time()
        
        # Metrics storage
        self.metrics = defaultdict(lambda: defaultdict(float))
        self.errors = defaultdict(list)
        self.performance_history = deque(maxlen=1000)
        
        # Prometheus metrics
        self.setup_prometheus_metrics()
        
        # Health check server
        self.health_server = None
        self.health_runner = None
        
    def setup_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        # Request metrics
        self.request_counter = Counter(
            'flightio_requests_total',
            'Total number of requests',
            ['site', 'status']
        )
        self.request_duration = Histogram(
            'flightio_request_duration_seconds',
            'Request duration in seconds',
            ['site']
        )
        
        # System metrics
        self.memory_gauge = Gauge(
            'flightio_memory_usage_bytes',
            'Memory usage in bytes'
        )
        self.cpu_gauge = Gauge(
            'flightio_cpu_usage_percent',
            'CPU usage percentage'
        )
        
        # Business metrics
        self.flights_found = Counter(
            'flightio_flights_found_total',
            'Total flights found',
            ['site', 'route']
        )
        self.error_counter = Counter(
            'flightio_errors_total',
            'Total errors',
            ['site', 'error_type']
        )
        
    async def start(self, port: int = 8080):
        """Start monitoring services"""
        # Start health check server
        app = web.Application()
        app.router.add_get('/health', self.health_check_handler)
        app.router.add_get('/metrics', self.prometheus_metrics_handler)
        app.router.add_get('/status', self.status_handler)
        
        self.health_runner = web.AppRunner(app)
        await self.health_runner.setup()
        
        site = web.TCPSite(self.health_runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Monitoring server started on port {port}")
        
        # Start background monitoring tasks
        asyncio.create_task(self.monitor_system_resources())
        
    async def stop(self):
        """Stop monitoring services"""
        if self.health_runner:
            await self.health_runner.cleanup()
            
    async def monitor_system_resources(self):
        """Background task to monitor system resources"""
        while True:
            try:
                # Update system metrics
                process = psutil.Process()
                
                # Memory metrics
                memory_info = process.memory_info()
                self.memory_gauge.set(memory_info.rss)
                self.metrics['system']['memory_mb'] = memory_info.rss / 1024 / 1024
                
                # CPU metrics
                cpu_percent = process.cpu_percent(interval=1)
                self.cpu_gauge.set(cpu_percent)
                self.metrics['system']['cpu_percent'] = cpu_percent
                
                # Disk I/O
                io_counters = process.io_counters()
                self.metrics['system']['disk_read_mb'] = io_counters.read_bytes / 1024 / 1024
                self.metrics['system']['disk_write_mb'] = io_counters.write_bytes / 1024 / 1024
                
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(60)
                
    def record_request(self, site: str, duration: float, success: bool, 
                      response_size: int = 0):
        """Record HTTP request metrics"""
        status = 'success' if success else 'failure'
        
        # Prometheus metrics
        self.request_counter.labels(site=site, status=status).inc()
        self.request_duration.labels(site=site).observe(duration)
        
        # Internal metrics
        self.metrics[site]['total_requests'] += 1
        self.metrics[site]['total_duration'] += duration
        self.metrics[site]['total_bytes'] += response_size
        
        if success:
            self.metrics[site]['successful_requests'] += 1
        else:
            self.metrics[site]['failed_requests'] += 1
            
        # Performance history
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'site': site,
            'duration': duration,
            'success': success,
            'size': response_size
        })
        
    def record_error(self, site: str, error_type: str, error_message: str):
        """Record error metrics"""
        # Prometheus metrics
        self.error_counter.labels(site=site, error_type=error_type).inc()
        
        # Internal tracking
        self.errors[site].append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message
        })
        
        # Keep only recent errors
        if len(self.errors[site]) > 100:
            self.errors[site] = self.errors[site][-100:]
            
    def record_flights_found(self, site: str, count: int, route: str):
        """Record business metrics"""
        self.flights_found.labels(site=site, route=route).inc(count)
        self.metrics[site]['total_flights'] += count
        
    def get_metrics(self, site: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific site or all sites"""
        if site:
            site_metrics = dict(self.metrics[site])
            
            # Calculate averages
            total_requests = site_metrics.get('total_requests', 0)
            if total_requests > 0:
                site_metrics['avg_duration'] = site_metrics.get('total_duration', 0) / total_requests
                site_metrics['success_rate'] = site_metrics.get('successful_requests', 0) / total_requests
                
            return site_metrics
        else:
            return dict(self.metrics)
            
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        uptime = time.time() - self.start_time
        
        # Calculate overall metrics
        total_requests = sum(m.get('total_requests', 0) for m in self.metrics.values())
        total_errors = sum(len(errors) for errors in self.errors.values())
        
        # System health
        memory_mb = self.metrics['system'].get('memory_mb', 0)
        cpu_percent = self.metrics['system'].get('cpu_percent', 0)
        
        health_status = {
            'status': 'healthy',
            'uptime_seconds': uptime,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'total_requests': total_requests,
                'total_errors': total_errors,
                'memory_mb': round(memory_mb, 2),
                'cpu_percent': round(cpu_percent, 2),
            }
        }
        
        # Determine health status
        if memory_mb > 1000:  # More than 1GB
            health_status['status'] = 'warning'
            health_status['warnings'] = health_status.get('warnings', [])
            health_status['warnings'].append('High memory usage')
            
        if cpu_percent > 80:
            health_status['status'] = 'warning'
            health_status['warnings'] = health_status.get('warnings', [])
            health_status['warnings'].append('High CPU usage')
            
        if total_errors > 100:
            health_status['status'] = 'unhealthy'
            health_status['errors'] = health_status.get('errors', [])
            health_status['errors'].append('Too many errors')
            
        return health_status
        
    async def health_check_handler(self, request):
        """Health check endpoint handler"""
        health = self.get_health_status()
        
        status_code = 200
        if health['status'] == 'unhealthy':
            status_code = 503
        elif health['status'] == 'warning':
            status_code = 200  # Still healthy, just with warnings
            
        return web.json_response(health, status=status_code)
        
    async def prometheus_metrics_handler(self, request):
        """Prometheus metrics endpoint handler"""
        metrics = generate_latest()
        return web.Response(text=metrics.decode('utf-8'),
                          content_type='text/plain')
                          
    async def status_handler(self, request):
        """Detailed status endpoint handler"""
        status = {
            'health': self.get_health_status(),
            'metrics': self.get_metrics(),
            'recent_errors': dict(self.errors),
            'performance': {
                'last_100_requests': list(self.performance_history)[-100:]
            }
        }
        
        return web.json_response(status)
        
    def __enter__(self):
        """Context manager support"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        asyncio.create_task(self.stop()) 