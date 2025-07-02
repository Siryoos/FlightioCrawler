"""
Health Check System for Flight Crawler
Comprehensive monitoring of memory usage, performance metrics, and system health
"""

import asyncio
import psutil
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import gc
from enum import Enum

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None

try:
    from scripts.performance_profiler import get_profiler
    from scripts.memory_leak_detector import get_leak_detector
    from utils.memory_efficient_cache import _cache_manager
    from utils.lazy_loader import _loader_manager
    COMPONENTS_AVAILABLE = True
except ImportError:
    COMPONENTS_AVAILABLE = False


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """Individual health metric"""
    name: str
    value: float
    unit: str
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def check_thresholds(self) -> HealthStatus:
        """Check metric against thresholds"""
        if self.threshold_critical is not None and self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.threshold_warning is not None and self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    check_name: str
    status: HealthStatus
    metrics: List[HealthMetric]
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    
    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY
    
    @property
    def needs_attention(self) -> bool:
        return self.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]


class HealthChecker:
    """
    Comprehensive health checker for the crawler system
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process(os.getpid())
        
        # Health check registry
        self.health_checks: Dict[str, Callable] = {}
        self.check_intervals: Dict[str, int] = {}  # seconds
        self.last_check_times: Dict[str, datetime] = {}
        self.cached_results: Dict[str, HealthCheckResult] = {}
        
        # Monitoring thread
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.is_monitoring = False
        
        # Alerting
        self.alert_callbacks: List[Callable[[HealthCheckResult], None]] = []
        
        # Default thresholds
        self.default_thresholds = {
            "memory_usage_mb": {"warning": 1024, "critical": 2048},
            "memory_percent": {"warning": 80, "critical": 90},
            "cpu_percent": {"warning": 80, "critical": 95},
            "disk_usage_percent": {"warning": 85, "critical": 95},
            "response_time_ms": {"warning": 5000, "critical": 10000},
            "error_rate_percent": {"warning": 5, "critical": 10},
            "memory_growth_rate": {"warning": 50, "critical": 100}  # MB per hour
        }
        
        # Register default health checks
        self._register_default_checks()

    def register_health_check(
        self, 
        name: str, 
        check_func: Callable[[], HealthCheckResult],
        interval_seconds: int = 60
    ):
        """Register a health check function"""
        self.health_checks[name] = check_func
        self.check_intervals[name] = interval_seconds
        self.logger.info(f"Registered health check: {name} (interval: {interval_seconds}s)")

    def add_alert_callback(self, callback: Callable[[HealthCheckResult], None]):
        """Add alert callback for health check failures"""
        self.alert_callbacks.append(callback)

    async def run_health_check(self, check_name: str) -> HealthCheckResult:
        """Run specific health check"""
        if check_name not in self.health_checks:
            raise ValueError(f"Health check '{check_name}' not found")
        
        start_time = time.time()
        
        try:
            check_func = self.health_checks[check_name]
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            result.duration_ms = (time.time() - start_time) * 1000
            self.last_check_times[check_name] = datetime.now()
            self.cached_results[check_name] = result
            
            # Trigger alerts if needed
            if result.needs_attention:
                self._trigger_alerts(result)
            
            return result
            
        except Exception as e:
            error_result = HealthCheckResult(
                check_name=check_name,
                status=HealthStatus.CRITICAL,
                metrics=[],
                message=f"Health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000
            )
            
            self.cached_results[check_name] = error_result
            self._trigger_alerts(error_result)
            return error_result

    async def run_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks"""
        results = {}
        
        for check_name in self.health_checks:
            try:
                result = await self.run_health_check(check_name)
                results[check_name] = result
            except Exception as e:
                self.logger.error(f"Error running health check {check_name}: {e}")
                results[check_name] = HealthCheckResult(
                    check_name=check_name,
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Check execution failed: {str(e)}"
                )
        
        return results

    def get_overall_health(self) -> HealthCheckResult:
        """Get overall system health status"""
        if not self.cached_results:
            return HealthCheckResult(
                check_name="overall",
                status=HealthStatus.UNKNOWN,
                metrics=[],
                message="No health checks have been run"
            )
        
        # Determine overall status
        statuses = [result.status for result in self.cached_results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
            message = "Critical issues detected"
        elif HealthStatus.WARNING in statuses:
            overall_status = HealthStatus.WARNING
            message = "Some components need attention"
        elif HealthStatus.UNKNOWN in statuses:
            overall_status = HealthStatus.WARNING
            message = "Some checks have unknown status"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All systems healthy"
        
        # Aggregate metrics
        all_metrics = []
        for result in self.cached_results.values():
            all_metrics.extend(result.metrics)
        
        return HealthCheckResult(
            check_name="overall",
            status=overall_status,
            metrics=all_metrics,
            message=message
        )

    def start_background_monitoring(self):
        """Start background health monitoring"""
        if self.is_monitoring:
            self.logger.warning("Health monitoring already started")
            return
        
        self.is_monitoring = True
        self.stop_monitoring.clear()
        
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.logger.info("Background health monitoring started")

    def stop_background_monitoring(self):
        """Stop background health monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_monitoring.set()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        self.logger.info("Background health monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while not self.stop_monitoring.is_set():
            try:
                current_time = datetime.now()
                
                # Check which health checks need to be run
                for check_name, interval in self.check_intervals.items():
                    last_check = self.last_check_times.get(check_name)
                    
                    if (not last_check or 
                        (current_time - last_check).total_seconds() >= interval):
                        
                        # Run health check asynchronously
                        try:
                            asyncio.run(self.run_health_check(check_name))
                        except Exception as e:
                            self.logger.error(f"Error in background health check {check_name}: {e}")
                
                # Sleep for a short interval
                self.stop_monitoring.wait(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                self.stop_monitoring.wait(30)  # Wait longer on error

    def _trigger_alerts(self, result: HealthCheckResult):
        """Trigger alerts for health check results"""
        for callback in self.alert_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")

    def _register_default_checks(self):
        """Register default health checks"""
        
        def check_memory_usage() -> HealthCheckResult:
            """Check memory usage"""
            try:
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                memory_percent = self.process.memory_percent()
                virtual_memory = psutil.virtual_memory()
                
                metrics = [
                    HealthMetric(
                        name="memory_usage_mb",
                        value=memory_mb,
                        unit="MB",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=self.default_thresholds["memory_usage_mb"]["warning"],
                        threshold_critical=self.default_thresholds["memory_usage_mb"]["critical"]
                    ),
                    HealthMetric(
                        name="memory_percent",
                        value=memory_percent,
                        unit="%",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=self.default_thresholds["memory_percent"]["warning"],
                        threshold_critical=self.default_thresholds["memory_percent"]["critical"]
                    ),
                    HealthMetric(
                        name="available_memory_mb",
                        value=virtual_memory.available / 1024 / 1024,
                        unit="MB",
                        status=HealthStatus.HEALTHY
                    )
                ]
                
                # Determine overall status
                status = HealthStatus.HEALTHY
                for metric in metrics:
                    metric_status = metric.check_thresholds()
                    if metric_status == HealthStatus.CRITICAL:
                        status = HealthStatus.CRITICAL
                    elif metric_status == HealthStatus.WARNING and status != HealthStatus.CRITICAL:
                        status = HealthStatus.WARNING
                
                message = f"Memory usage: {memory_mb:.1f}MB ({memory_percent:.1f}%)"
                
                return HealthCheckResult(
                    check_name="memory_usage",
                    status=status,
                    metrics=metrics,
                    message=message
                )
                
            except Exception as e:
                return HealthCheckResult(
                    check_name="memory_usage",
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Failed to check memory usage: {str(e)}"
                )
        
        def check_cpu_usage() -> HealthCheckResult:
            """Check CPU usage"""
            try:
                cpu_percent = self.process.cpu_percent(interval=1)
                system_cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                
                metrics = [
                    HealthMetric(
                        name="process_cpu_percent",
                        value=cpu_percent,
                        unit="%",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=self.default_thresholds["cpu_percent"]["warning"],
                        threshold_critical=self.default_thresholds["cpu_percent"]["critical"]
                    ),
                    HealthMetric(
                        name="system_cpu_percent",
                        value=system_cpu_percent,
                        unit="%",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=self.default_thresholds["cpu_percent"]["warning"],
                        threshold_critical=self.default_thresholds["cpu_percent"]["critical"]
                    ),
                    HealthMetric(
                        name="cpu_count",
                        value=cpu_count,
                        unit="cores",
                        status=HealthStatus.HEALTHY
                    )
                ]
                
                # Determine status
                status = HealthStatus.HEALTHY
                for metric in metrics:
                    metric_status = metric.check_thresholds()
                    if metric_status == HealthStatus.CRITICAL:
                        status = HealthStatus.CRITICAL
                    elif metric_status == HealthStatus.WARNING and status != HealthStatus.CRITICAL:
                        status = HealthStatus.WARNING
                
                message = f"CPU usage: Process {cpu_percent:.1f}%, System {system_cpu_percent:.1f}%"
                
                return HealthCheckResult(
                    check_name="cpu_usage",
                    status=status,
                    metrics=metrics,
                    message=message
                )
                
            except Exception as e:
                return HealthCheckResult(
                    check_name="cpu_usage",
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Failed to check CPU usage: {str(e)}"
                )
        
        def check_disk_usage() -> HealthCheckResult:
            """Check disk usage"""
            try:
                disk_usage = psutil.disk_usage('/')
                usage_percent = (disk_usage.used / disk_usage.total) * 100
                
                metrics = [
                    HealthMetric(
                        name="disk_usage_percent",
                        value=usage_percent,
                        unit="%",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=self.default_thresholds["disk_usage_percent"]["warning"],
                        threshold_critical=self.default_thresholds["disk_usage_percent"]["critical"]
                    ),
                    HealthMetric(
                        name="disk_free_gb",
                        value=disk_usage.free / 1024 / 1024 / 1024,
                        unit="GB",
                        status=HealthStatus.HEALTHY
                    ),
                    HealthMetric(
                        name="disk_total_gb",
                        value=disk_usage.total / 1024 / 1024 / 1024,
                        unit="GB",
                        status=HealthStatus.HEALTHY
                    )
                ]
                
                status = metrics[0].check_thresholds()
                message = f"Disk usage: {usage_percent:.1f}% ({disk_usage.free / 1024**3:.1f}GB free)"
                
                return HealthCheckResult(
                    check_name="disk_usage",
                    status=status,
                    metrics=metrics,
                    message=message
                )
                
            except Exception as e:
                return HealthCheckResult(
                    check_name="disk_usage",
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Failed to check disk usage: {str(e)}"
                )
        
        def check_crawler_components() -> HealthCheckResult:
            """Check crawler component health"""
            try:
                metrics = []
                status = HealthStatus.HEALTHY
                issues = []
                
                # Check profiler if available
                if COMPONENTS_AVAILABLE:
                    try:
                        profiler = get_profiler()
                        profiler_stats = profiler.generate_performance_report()
                        
                        if "error" not in profiler_stats:
                            avg_duration = profiler_stats.get("performance_metrics", {}).get("avg_duration_seconds", 0)
                            success_rate = profiler_stats.get("summary", {}).get("success_rate", 100)
                            
                            metrics.append(HealthMetric(
                                name="avg_response_time_ms",
                                value=avg_duration * 1000,
                                unit="ms",
                                status=HealthStatus.HEALTHY,
                                threshold_warning=self.default_thresholds["response_time_ms"]["warning"],
                                threshold_critical=self.default_thresholds["response_time_ms"]["critical"]
                            ))
                            
                            metrics.append(HealthMetric(
                                name="success_rate_percent",
                                value=success_rate,
                                unit="%",
                                status=HealthStatus.HEALTHY,
                                threshold_warning=95,  # Warning if success rate < 95%
                                threshold_critical=90   # Critical if success rate < 90%
                            ))
                    except Exception as e:
                        issues.append(f"Profiler check failed: {str(e)}")
                
                # Check cache manager
                try:
                    cache_stats = _cache_manager.get_all_stats()
                    total_cache_size_mb = sum(
                        stats.get("total_size_mb", 0) 
                        for stats in cache_stats.values()
                    )
                    
                    metrics.append(HealthMetric(
                        name="cache_size_mb",
                        value=total_cache_size_mb,
                        unit="MB",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=256,
                        threshold_critical=512
                    ))
                except Exception as e:
                    issues.append(f"Cache check failed: {str(e)}")
                
                # Check lazy loader manager
                try:
                    loader_stats = _loader_manager.get_memory_usage()
                    loader_memory = loader_stats.get("total_memory_mb", 0)
                    
                    metrics.append(HealthMetric(
                        name="loader_memory_mb",
                        value=loader_memory,
                        unit="MB",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=128,
                        threshold_critical=256
                    ))
                except Exception as e:
                    issues.append(f"Loader check failed: {str(e)}")
                
                # Determine overall status
                for metric in metrics:
                    metric_status = metric.check_thresholds()
                    if metric_status == HealthStatus.CRITICAL:
                        status = HealthStatus.CRITICAL
                    elif metric_status == HealthStatus.WARNING and status != HealthStatus.CRITICAL:
                        status = HealthStatus.WARNING
                
                if issues and status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                
                message = f"Components checked: {len(metrics)} metrics"
                if issues:
                    message += f", {len(issues)} issues"
                
                return HealthCheckResult(
                    check_name="crawler_components",
                    status=status,
                    metrics=metrics,
                    message=message
                )
                
            except Exception as e:
                return HealthCheckResult(
                    check_name="crawler_components",
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Failed to check crawler components: {str(e)}"
                )
        
        def check_garbage_collection() -> HealthCheckResult:
            """Check garbage collection status"""
            try:
                gc_counts = gc.get_count()
                gc_stats = gc.get_stats()
                
                metrics = [
                    HealthMetric(
                        name="gc_generation_0",
                        value=gc_counts[0],
                        unit="objects",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=1000,
                        threshold_critical=5000
                    ),
                    HealthMetric(
                        name="gc_generation_1",
                        value=gc_counts[1],
                        unit="objects",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=100,
                        threshold_critical=500
                    ),
                    HealthMetric(
                        name="gc_generation_2",
                        value=gc_counts[2],
                        unit="objects",
                        status=HealthStatus.HEALTHY,
                        threshold_warning=50,
                        threshold_critical=200
                    )
                ]
                
                # Check if GC is enabled
                gc_enabled = gc.isenabled()
                if not gc_enabled:
                    status = HealthStatus.WARNING
                    message = "Garbage collection is disabled"
                else:
                    status = HealthStatus.HEALTHY
                    for metric in metrics:
                        metric_status = metric.check_thresholds()
                        if metric_status == HealthStatus.CRITICAL:
                            status = HealthStatus.CRITICAL
                        elif metric_status == HealthStatus.WARNING and status != HealthStatus.CRITICAL:
                            status = HealthStatus.WARNING
                    
                    message = f"GC enabled, generations: {gc_counts}"
                
                return HealthCheckResult(
                    check_name="garbage_collection",
                    status=status,
                    metrics=metrics,
                    message=message
                )
                
            except Exception as e:
                return HealthCheckResult(
                    check_name="garbage_collection",
                    status=HealthStatus.CRITICAL,
                    metrics=[],
                    message=f"Failed to check garbage collection: {str(e)}"
                )
        
        # Register all default checks
        self.register_health_check("memory_usage", check_memory_usage, 30)
        self.register_health_check("cpu_usage", check_cpu_usage, 30)
        self.register_health_check("disk_usage", check_disk_usage, 300)  # 5 minutes
        self.register_health_check("crawler_components", check_crawler_components, 60)
        self.register_health_check("garbage_collection", check_garbage_collection, 60)

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for API responses"""
        overall_health = self.get_overall_health()
        
        return {
            "status": overall_health.status.value,
            "message": overall_health.message,
            "timestamp": overall_health.timestamp.isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "metrics": [
                        {
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "status": metric.status.value
                        }
                        for metric in result.metrics
                    ]
                }
                for name, result in self.cached_results.items()
            }
        }


# Global health checker instance
_global_health_checker = None

def get_health_checker() -> HealthChecker:
    """Get global health checker instance"""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


# FastAPI integration
if FASTAPI_AVAILABLE:
    def create_health_api() -> FastAPI:
        """Create FastAPI app with health endpoints"""
        app = FastAPI(title="Crawler Health API", version="1.0.0")
        health_checker = get_health_checker()
        
        @app.get("/health")
        async def health_check():
            """Get overall health status"""
            return health_checker.get_health_summary()
        
        @app.get("/health/{check_name}")
        async def specific_health_check(check_name: str):
            """Get specific health check result"""
            try:
                result = await health_checker.run_health_check(check_name)
                return {
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms,
                    "metrics": [
                        {
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "status": metric.status.value
                        }
                        for metric in result.metrics
                    ]
                }
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
        
        @app.get("/health/checks/all")
        async def all_health_checks():
            """Run all health checks"""
            results = await health_checker.run_all_health_checks()
            return {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "timestamp": result.timestamp.isoformat(),
                    "duration_ms": result.duration_ms
                }
                for name, result in results.items()
            }
        
        @app.post("/health/gc")
        async def force_garbage_collection():
            """Force garbage collection"""
            before_count = sum(gc.get_count())
            collected = gc.collect()
            after_count = sum(gc.get_count())
            
            return {
                "objects_collected": collected,
                "objects_before": before_count,
                "objects_after": after_count,
                "timestamp": datetime.now().isoformat()
            }
        
        return app


def setup_logging_alerts():
    """Setup logging-based alerts"""
    health_checker = get_health_checker()
    
    def log_alert(result: HealthCheckResult):
        """Log health check alerts"""
        logger = logging.getLogger("HealthAlerts")
        
        if result.status == HealthStatus.CRITICAL:
            logger.critical(f"CRITICAL: {result.check_name} - {result.message}")
        elif result.status == HealthStatus.WARNING:
            logger.warning(f"WARNING: {result.check_name} - {result.message}")
    
    health_checker.add_alert_callback(log_alert)


if __name__ == "__main__":
    # Example usage
    async def main():
        health_checker = get_health_checker()
        
        # Setup logging alerts
        setup_logging_alerts()
        
        # Start background monitoring
        health_checker.start_background_monitoring()
        
        try:
            # Run health checks
            print("Running health checks...")
            results = await health_checker.run_all_health_checks()
            
            for name, result in results.items():
                print(f"{name}: {result.status.value} - {result.message}")
            
            # Get overall health
            overall = health_checker.get_overall_health()
            print(f"\nOverall Health: {overall.status.value} - {overall.message}")
            
            # Wait for background monitoring
            import time
            time.sleep(10)
            
        finally:
            health_checker.stop_background_monitoring()
    
    asyncio.run(main()) 