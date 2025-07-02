import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, 
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, multiprocess
)
import asyncio
import json
from config import config


@dataclass
class CrawlerMetrics:
    """Crawler performance metrics"""
    site_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration: float = 0.0
    avg_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    error_count: int = 0
    circuit_breaker_open: bool = False


class EnhancedMonitoring:
    """Enhanced monitoring with Prometheus metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize Prometheus metrics
        self._init_prometheus_metrics()
        
        # Crawler metrics storage
        self.crawler_metrics: Dict[str, CrawlerMetrics] = {}
        
        # Performance tracking
        self.performance_data: List[Dict[str, Any]] = []
        
        # Alert thresholds
        self.alert_thresholds = {
            'error_rate': 0.1,  # 10% error rate
            'response_time': 30.0,  # 30 seconds
            'circuit_breaker_open': True,
            'concurrent_requests': 100
        }
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        # Request metrics
        self.crawler_requests_total = Counter(
            'crawler_requests_total',
            'Total requests by crawler',
            ['site', 'status']
        )
        
        self.crawler_duration_seconds = Histogram(
            'crawler_duration_seconds',
            'Request duration by crawler',
            ['site'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.crawler_response_size_bytes = Histogram(
            'crawler_response_size_bytes',
            'Response size by crawler',
            ['site'],
            buckets=[100, 1000, 10000, 100000, 1000000]
        )
        
        # Error metrics
        self.crawler_errors_total = Counter(
            'crawler_errors_total',
            'Total errors by crawler',
            ['site', 'error_type']
        )
        
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'circuit_breaker_state',
            'Circuit breaker state by site',
            ['site']
        )
        
        # Performance metrics
        self.crawler_success_rate = Gauge(
            'crawler_success_rate',
            'Success rate by crawler',
            ['site']
        )
        
        self.crawler_avg_response_time = Gauge(
            'crawler_avg_response_time',
            'Average response time by crawler',
            ['site']
        )
        
        # Business metrics
        self.flights_found_total = Counter(
            'flights_found_total',
            'Total flights found by crawler',
            ['site', 'route']
        )
        
        self.price_changes_total = Counter(
            'price_changes_total',
            'Total price changes detected',
            ['site', 'direction']
        )
        
        # System metrics
        self.concurrent_requests = Gauge(
            'concurrent_requests',
            'Number of concurrent requests',
            ['site']
        )
        
        self.memory_usage_bytes = Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes'
        )
        
        self.cpu_usage_percent = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage'
        )
    
    def record_request_start(self, site: str) -> str:
        """Record start of request and return request ID"""
        request_id = f"{site}_{int(time.time() * 1000)}"
        
        # Update concurrent requests
        self.concurrent_requests.labels(site=site).inc()
        
        # Initialize metrics if not exists
        if site not in self.crawler_metrics:
            self.crawler_metrics[site] = CrawlerMetrics(site_name=site)
        
        # Update metrics
        self.crawler_metrics[site].total_requests += 1
        self.crawler_metrics[site].last_request_time = datetime.now()
        
        return request_id
    
    def record_request_success(
        self, 
        site: str, 
        duration: float, 
        response_size: int,
        flights_found: int = 0,
        route: str = "unknown"
    ):
        """Record successful request"""
        # Update counters
        self.crawler_requests_total.labels(site=site, status="success").inc()
        self.crawler_errors_total.labels(site=site, error_type="none").inc()
        
        # Update histograms
        self.crawler_duration_seconds.labels(site=site).observe(duration)
        self.crawler_response_size_bytes.labels(site=site).observe(response_size)
        
        # Update business metrics
        if flights_found > 0:
            self.flights_found_total.labels(site=site, route=route).inc(flights_found)
        
        # Update crawler metrics
        if site in self.crawler_metrics:
            metrics = self.crawler_metrics[site]
            metrics.successful_requests += 1
            metrics.total_duration += duration
            metrics.avg_response_time = metrics.total_duration / metrics.successful_requests
            
            # Update gauges
            self.crawler_success_rate.labels(site=site).set(
                metrics.successful_requests / metrics.total_requests
            )
            self.crawler_avg_response_time.labels(site=site).set(metrics.avg_response_time)
        
        # Decrease concurrent requests
        self.concurrent_requests.labels(site=site).dec()
    
    def record_request_error(
        self, 
        site: str, 
        error_type: str, 
        duration: float = 0.0,
        error_message: str = ""
    ):
        """Record failed request"""
        # Update counters
        self.crawler_requests_total.labels(site=site, status="error").inc()
        self.crawler_errors_total.labels(site=site, error_type=error_type).inc()
        
        # Update histograms if duration available
        if duration > 0:
            self.crawler_duration_seconds.labels(site=site).observe(duration)
        
        # Update crawler metrics
        if site in self.crawler_metrics:
            metrics = self.crawler_metrics[site]
            metrics.failed_requests += 1
            metrics.error_count += 1
            
            # Update success rate
            self.crawler_success_rate.labels(site=site).set(
                metrics.successful_requests / metrics.total_requests
            )
        
        # Log error
        self.logger.error(
            f"Request error for {site}: {error_type} - {error_message}",
            extra={
                "site": site,
                "error_type": error_type,
                "duration": duration,
                "error_message": error_message
            }
        )
        
        # Decrease concurrent requests
        self.concurrent_requests.labels(site=site).dec()
    
    def record_circuit_breaker_change(self, site: str, is_open: bool):
        """Record circuit breaker state change"""
        state_value = 1 if is_open else 0
        self.circuit_breaker_state.labels(site=site).set(state_value)
        
        if site in self.crawler_metrics:
            self.crawler_metrics[site].circuit_breaker_open = is_open
        
        self.logger.warning(
            f"Circuit breaker {'opened' if is_open else 'closed'} for {site}"
        )
    
    def record_price_change(
        self, 
        site: str, 
        old_price: float, 
        new_price: float,
        route: str = "unknown"
    ):
        """Record price change detection"""
        direction = "increase" if new_price > old_price else "decrease"
        self.price_changes_total.labels(site=site, direction=direction).inc()
        
        change_percentage = ((new_price - old_price) / old_price) * 100
        
        self.logger.info(
            f"Price change detected for {site}: {old_price} -> {new_price} ({change_percentage:.2f}%)",
            extra={
                "site": site,
                "old_price": old_price,
                "new_price": new_price,
                "change_percentage": change_percentage,
                "direction": direction,
                "route": route
            }
        )
    
    def record_system_metrics(self, memory_bytes: int, cpu_percent: float):
        """Record system-level metrics"""
        self.memory_usage_bytes.set(memory_bytes)
        self.cpu_usage_percent.set(cpu_percent)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "crawlers": {},
            "system": {
                "total_requests": sum(m.total_requests for m in self.crawler_metrics.values()),
                "total_errors": sum(m.error_count for m in self.crawler_metrics.values()),
                "active_crawlers": len([m for m in self.crawler_metrics.values() if m.last_request_time and 
                                      datetime.now() - m.last_request_time < timedelta(minutes=5)])
            },
            "alerts": []
        }
        
        # Per-crawler metrics
        for site, metrics in self.crawler_metrics.items():
            success_rate = (metrics.successful_requests / metrics.total_requests 
                           if metrics.total_requests > 0 else 0)
            
            summary["crawlers"][site] = {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": success_rate,
                "avg_response_time": metrics.avg_response_time,
                "error_count": metrics.error_count,
                "circuit_breaker_open": metrics.circuit_breaker_open,
                "last_request": metrics.last_request_time.isoformat() if metrics.last_request_time else None
            }
            
            # Check for alerts
            if success_rate < (1 - self.alert_thresholds['error_rate']):
                summary["alerts"].append({
                    "type": "high_error_rate",
                    "site": site,
                    "value": success_rate,
                    "threshold": 1 - self.alert_thresholds['error_rate']
                })
            
            if metrics.avg_response_time > self.alert_thresholds['response_time']:
                summary["alerts"].append({
                    "type": "slow_response_time",
                    "site": site,
                    "value": metrics.avg_response_time,
                    "threshold": self.alert_thresholds['response_time']
                })
            
            if metrics.circuit_breaker_open:
                summary["alerts"].append({
                    "type": "circuit_breaker_open",
                    "site": site,
                    "value": True
                })
        
        return summary
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest()
    
    def export_metrics_to_file(self, filename: str):
        """Export metrics to JSON file"""
        try:
            summary = self.get_metrics_summary()
            
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info(f"Metrics exported to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {e}")
    
    async def monitor_performance(self, interval: int = 60):
        """Continuous performance monitoring"""
        while True:
            try:
                # Get current metrics
                summary = self.get_metrics_summary()
                
                # Store performance data
                self.performance_data.append(summary)
                
                # Keep only last 1000 records
                if len(self.performance_data) > 1000:
                    self.performance_data = self.performance_data[-1000:]
                
                # Check for critical alerts
                critical_alerts = [
                    alert for alert in summary["alerts"]
                    if alert["type"] in ["circuit_breaker_open", "high_error_rate"]
                ]
                
                if critical_alerts:
                    self.logger.critical(
                        f"Critical alerts detected: {critical_alerts}",
                        extra={"alerts": critical_alerts}
                    )
                
                # Export metrics periodically
                if len(self.performance_data) % 10 == 0:  # Every 10 minutes
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self.export_metrics_to_file(f"metrics_{timestamp}.json")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(interval)
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over time"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Filter recent data
            recent_data = [
                record for record in self.performance_data
                if datetime.fromisoformat(record["timestamp"]) > cutoff_time
            ]
            
            if not recent_data:
                return {"error": "No data available for the specified time range"}
            
            trends = {
                "time_range": f"Last {hours} hours",
                "total_records": len(recent_data),
                "crawler_trends": {},
                "system_trends": {
                    "total_requests": [],
                    "total_errors": [],
                    "active_crawlers": []
                }
            }
            
            # Calculate trends for each crawler
            crawler_data = {}
            for record in recent_data:
                for site, metrics in record["crawlers"].items():
                    if site not in crawler_data:
                        crawler_data[site] = []
                    crawler_data[site].append(metrics)
                
                # System trends
                trends["system_trends"]["total_requests"].append(record["system"]["total_requests"])
                trends["system_trends"]["total_errors"].append(record["system"]["total_errors"])
                trends["system_trends"]["active_crawlers"].append(record["system"]["active_crawlers"])
            
            # Calculate averages for each crawler
            for site, data in crawler_data.items():
                if data:
                    avg_success_rate = sum(d["success_rate"] for d in data) / len(data)
                    avg_response_time = sum(d["avg_response_time"] for d in data) / len(data)
                    total_requests = sum(d["total_requests"] for d in data)
                    
                    trends["crawler_trends"][site] = {
                        "avg_success_rate": avg_success_rate,
                        "avg_response_time": avg_response_time,
                        "total_requests": total_requests,
                        "data_points": len(data)
                    }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error calculating performance trends: {e}")
            return {"error": str(e)} 
