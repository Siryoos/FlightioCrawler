# monitoring.py - Complete implementation
import logging
import time
from typing import Dict, List, Optional, Any, Union
from collections import defaultdict, deque
from datetime import datetime, timedelta
import redis
import asyncio
from dataclasses import dataclass
from config import config
from error_handler import ErrorHandler
import psutil
import gc
import os

# Configure logging
logger = logging.getLogger(__name__)


class Monitoring:
    """Minimal monitoring interface used by site adapters."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = config or {}

    def record_success(self) -> None:
        """Record a successful crawl event."""
        # Placeholder for future integration
        logger.debug("Monitoring.record_success called")

    def record_error(self) -> None:
        """Record an error during crawling."""
        # Placeholder for future integration
        logger.debug("Monitoring.record_error called")


@dataclass
class CrawlerMetrics:
    """Metrics for a single crawler instance"""

    domain: str
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    total_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_error: Optional[datetime] = None
    last_error_type: Optional[str] = None
    circuit_open: bool = False
    circuit_open_time: Optional[datetime] = None


class CrawlerMonitor:
    """Monitor crawler performance"""

    def __init__(self) -> None:
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.request_history: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.error_handler: ErrorHandler = ErrorHandler()
        try:
            self.redis: Optional[redis.Redis] = redis.Redis(
                host=config.REDIS.HOST, port=config.REDIS.PORT, db=config.REDIS.DB
            )
        except Exception:
            self.redis = None
        
        # Memory monitoring setup
        self.process = psutil.Process(os.getpid())

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage of the application."""
        mem_info = self.process.memory_info()
        return {
            "rss_mb": mem_info.rss / (1024 * 1024),
            "vms_mb": mem_info.vms / (1024 * 1024),
            "percent": self.process.memory_percent(),
            "gc_stats": gc.get_stats(),
            "gc_objects": len(gc.get_objects()),
        }

    async def log_memory_usage_periodically(self, interval_seconds: int = 60):
        """Periodically log memory usage metrics."""
        while True:
            try:
                memory_usage = self.get_memory_usage()
                logger.info(f"Memory Usage: RSS {memory_usage['rss_mb']:.2f} MB, "
                            f"VMS {memory_usage['vms_mb']:.2f} MB, "
                            f"GC Objects: {memory_usage['gc_objects']}")
                # Here you could also send these metrics to a monitoring system like Prometheus
            except Exception as e:
                logger.error(f"Failed to log memory usage: {e}")
            
            await asyncio.sleep(interval_seconds)

    def record_request(self, domain: str, duration: float) -> None:
        """Record request metrics"""
        try:
            # Initialize domain metrics if not exists
            if domain not in self.metrics:
                self.metrics[domain] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_duration": 0,
                    "min_duration": float("inf"),
                    "max_duration": 0,
                    "last_request": None,
                    "flights_scraped": 0,
                }

            # Get metrics
            metrics = self.metrics[domain]

            # Update metrics
            metrics["total_requests"] += 1
            metrics["successful_requests"] += 1
            metrics["total_duration"] += duration
            metrics["min_duration"] = min(metrics["min_duration"], duration)
            metrics["max_duration"] = max(metrics["max_duration"], duration)
            metrics["last_request"] = datetime.now().isoformat()
            self.request_history[domain].append(time.time())

        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")

    def record_flights(self, domain: str, count: int) -> None:
        """Record flights scraped"""
        try:
            # Initialize domain metrics if not exists
            if domain not in self.metrics:
                self.metrics[domain] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_duration": 0,
                    "min_duration": float("inf"),
                    "max_duration": 0,
                    "last_request": None,
                    "flights_scraped": 0,
                }

            # Get metrics
            metrics = self.metrics[domain]

            # Update metrics
            metrics["flights_scraped"] += count

        except Exception as e:
            logger.error(f"Error recording flights: {e}")

    def get_metrics(self, domain: str) -> Dict[str, Any]:
        """Get metrics for domain"""
        try:
            # Get metrics
            metrics = self.metrics.get(domain, {})

            # Calculate averages
            if metrics.get("total_requests", 0) > 0:
                metrics["avg_duration"] = (
                    metrics["total_duration"] / metrics["total_requests"]
                )
                metrics["success_rate"] = (
                    metrics["successful_requests"] / metrics["total_requests"]
                )
            else:
                metrics["avg_duration"] = 0
                metrics["success_rate"] = 0

            # Get error stats
            error_stats = self.error_handler.get_error_stats(domain)

            return {
                "domain": domain,
                "metrics": metrics,
                "error_stats": error_stats,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all domains"""
        try:
            return {domain: self.get_metrics(domain) for domain in config.SITES.keys()}

        except Exception as e:
            logger.error(f"Error getting all metrics: {e}")
            return {}

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        try:
            # Get all metrics
            metrics = self.get_all_metrics()

            # Get error stats
            error_stats = self.error_handler.get_all_error_stats()

            # Calculate overall success rate
            total_requests = sum(
                m["metrics"]["total_requests"] for m in metrics.values()
            )
            successful_requests = sum(
                m["metrics"]["successful_requests"] for m in metrics.values()
            )
            success_rate = (
                successful_requests / total_requests if total_requests > 0 else 0
            )

            # Check circuit breakers
            circuit_breakers = {
                domain: self.error_handler.is_circuit_open(domain)
                for domain in config.SITES.keys()
            }

            # Determine overall status
            status = "healthy"
            if success_rate < 0.8:
                status = "degraded"
            if any(circuit_breakers.values()):
                status = "unhealthy"

            return {
                "status": status,
                "success_rate": success_rate,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "circuit_breakers": circuit_breakers,
                "metrics": metrics,
                "error_stats": error_stats,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {}

    def reset_metrics(self, domain: str) -> None:
        """Reset metrics for domain"""
        try:
            # Reset metrics
            if domain in self.metrics:
                self.metrics[domain] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_duration": 0,
                    "min_duration": float("inf"),
                    "max_duration": 0,
                    "last_request": None,
                    "flights_scraped": 0,
                }

            # Reset request history
            if domain in self.request_history:
                self.request_history[domain].clear()

        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")

    def reset_all_metrics(self) -> None:
        """Reset all metrics"""
        try:
            # Reset metrics
            self.metrics.clear()

            # Reset request history
            self.request_history.clear()

        except Exception as e:
            logger.error(f"Error resetting all metrics: {e}")

    def clean_old_metrics(self) -> None:
        """Clean old metrics data"""
        try:
            # Get current time
            now = time.time()

            # Clean request history older than 24 hours
            for domain in self.request_history:
                self.request_history[domain] = deque(
                    [t for t in self.request_history[domain] if now - t < 86400],
                    maxlen=1000,
                )

        except Exception as e:
            logger.error(f"Error cleaning old metrics: {e}")

    def get_request_timeline(self, domain: str) -> List[Dict[str, Any]]:
        """Get request timeline for domain"""
        try:
            # Get request history
            history = list(self.request_history.get(domain, []))

            # Convert to timeline
            timeline = [
                {"timestamp": datetime.fromtimestamp(t).isoformat(), "type": "request"}
                for t in history
            ]

            # Sort by timestamp
            timeline.sort(key=lambda x: x["timestamp"])

            return timeline

        except Exception as e:
            logger.error(f"Error getting request timeline: {e}")
            return []

    def get_all_request_timelines(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get request timelines for all domains"""
        try:
            return {
                domain: self.get_request_timeline(domain)
                for domain in config.SITES.keys()
            }

        except Exception as e:
            logger.error(f"Error getting all request timelines: {e}")
            return {}

    def get_flight_timeline(self, domain: str) -> List[Dict[str, Any]]:
        """Get flight scraping timeline for domain"""
        try:
            # Get metrics
            metrics = self.metrics.get(domain, {})

            # Create timeline entry if we have data
            timeline = []
            if metrics.get("last_request"):
                timeline.append(
                    {
                        "timestamp": metrics["last_request"],
                        "flights_scraped": metrics.get("flights_scraped", 0),
                        "type": "flight_scrape",
                    }
                )

            return timeline

        except Exception as e:
            logger.error(f"Error getting flight timeline: {e}")
            return []

    def get_all_flight_timelines(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get flight timelines for all domains"""
        try:
            return {
                domain: self.get_flight_timeline(domain)
                for domain in config.SITES.keys()
            }

        except Exception as e:
            logger.error(f"Error getting all flight timelines: {e}")
            return {}

    def setup_logging(self) -> None:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def setup_metrics(self) -> None:
        """Setup metrics collection"""
        # Initialize metrics for all configured sites
        for domain in config.SITES.keys():
            if domain not in self.metrics:
                self.metrics[domain] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_duration": 0,
                    "min_duration": float("inf"),
                    "max_duration": 0,
                    "last_request": None,
                    "flights_scraped": 0,
                }

    def log_request(
        self,
        domain: str,
        success: bool,
        response_time: float,
        error: Optional[str] = None,
    ) -> None:
        """Log request details"""
        try:
            status = "SUCCESS" if success else "ERROR"
            error_msg = f" - {error}" if error else ""
            logger.info(f"[{domain}] {status} - {response_time:.2f}s{error_msg}")

            if success:
                self.record_request(domain, response_time)
            else:
                # Record failed request
                if domain not in self.metrics:
                    self.metrics[domain] = {
                        "total_requests": 0,
                        "successful_requests": 0,
                        "failed_requests": 0,
                        "total_duration": 0,
                        "min_duration": float("inf"),
                        "max_duration": 0,
                        "last_request": None,
                        "flights_scraped": 0,
                    }
                self.metrics[domain]["total_requests"] += 1
                self.metrics[domain]["failed_requests"] += 1

        except Exception as e:
            logger.error(f"Error logging request: {e}")

    def log_flights_scraped(self, domain: str, count: int) -> None:
        """Log flights scraped"""
        logger.info(f"[{domain}] Scraped {count} flights")
        self.record_flights(domain, count)

    async def track_request(self, domain: str, start_time: float) -> None:
        """Track request completion"""
        try:
            duration = time.time() - start_time
            self.record_request(domain, duration)

        except Exception as e:
            logger.error(f"Error tracking request: {e}")

    async def track_error(self, domain: str, error: Exception) -> None:
        """Track error occurrence"""
        try:
            await self.error_handler.handle_error(domain, error)

        except Exception as e:
            logger.error(f"Error tracking error: {e}")

    def get_metrics(self, domain: str) -> CrawlerMetrics:
        """Get metrics for domain as CrawlerMetrics object"""
        try:
            # Get raw metrics
            raw_metrics = self.metrics.get(domain, {})

            # Get error stats
            error_stats = self.error_handler.get_error_stats(domain)

            # Create CrawlerMetrics object
            return CrawlerMetrics(
                domain=domain,
                success_count=raw_metrics.get("successful_requests", 0),
                error_count=raw_metrics.get("failed_requests", 0),
                total_requests=raw_metrics.get("total_requests", 0),
                total_response_time=raw_metrics.get("total_duration", 0.0),
                last_success=(
                    datetime.fromisoformat(raw_metrics["last_request"])
                    if raw_metrics.get("last_request")
                    else None
                ),
                circuit_open=error_stats.get("circuit_open", False),
            )

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return CrawlerMetrics(domain=domain)

    async def update_metrics(self, domain: str, metrics: CrawlerMetrics) -> None:
        """Update metrics for domain"""
        try:
            # Update internal metrics
            self.metrics[domain] = {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.success_count,
                "failed_requests": metrics.error_count,
                "total_duration": metrics.total_response_time,
                "min_duration": 0,  # Not tracked in CrawlerMetrics
                "max_duration": 0,  # Not tracked in CrawlerMetrics
                "last_request": (
                    metrics.last_success.isoformat() if metrics.last_success else None
                ),
                "flights_scraped": 0,  # Not tracked in CrawlerMetrics
            }

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def get_domain_health_status(self, domain: str) -> Dict[str, Any]:
        """Get health status for specific domain"""
        try:
            # Get metrics
            metrics = self.get_metrics(domain)

            # Get error stats
            error_stats = self.error_handler.get_error_stats(domain)

            # Calculate success rate
            success_rate = (
                metrics.success_count / metrics.total_requests
                if metrics.total_requests > 0
                else 0
            )

            # Determine status
            status = "healthy"
            if success_rate < 0.8:
                status = "degraded"
            if error_stats.get("circuit_open", False):
                status = "unhealthy"

            return {
                "domain": domain,
                "status": status,
                "success_rate": success_rate,
                "total_requests": metrics.total_requests,
                "circuit_open": error_stats.get("circuit_open", False),
                "last_success": (
                    metrics.last_success.isoformat() if metrics.last_success else None
                ),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting domain health status: {e}")
            return {}

    def get_all_domain_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all domains"""
        return {
            domain: self.get_domain_health_status(domain)
            for domain in config.SITES.keys()
        }

    def get_last_success(self, domain: str) -> Optional[str]:
        """Get timestamp of last successful request"""
        try:
            metrics = self.metrics.get(domain, {})
            return metrics.get("last_request")
        except Exception as e:
            logger.error(f"Error getting last success: {e}")
            return None

    def get_request_count(self, domain: str, hours: int = 24) -> int:
        """Get request count for domain in last N hours"""
        return len(self.request_history.get(domain, []))

    def get_success_rate(self, domain: str, hours: int = 24) -> float:
        """Get success rate for domain"""
        try:
            metrics = self.metrics.get(domain, {})
            total = metrics.get("total_requests", 0)
            successful = metrics.get("successful_requests", 0)
            return successful / total if total > 0 else 0.0
        except Exception as e:
            logger.error(f"Error getting success rate: {e}")
            return 0.0

    def get_avg_response_time(self, domain: str) -> float:
        """Get average response time for domain"""
        try:
            metrics = self.metrics.get(domain, {})
            total_duration = metrics.get("total_duration", 0)
            total_requests = metrics.get("total_requests", 0)
            return total_duration / total_requests if total_requests > 0 else 0.0
        except Exception as e:
            logger.error(f"Error getting avg response time: {e}")
            return 0.0

    def get_error_count(self, domain: str, hours: int = 1) -> int:
        """Get error count for domain in last N hours"""
        return len(self.error_handler.errors.get(domain, []))

    def get_success_count(self, domain: str, hours: int = 1) -> int:
        """Get success count for domain in last N hours"""
        return self.metrics.get(domain, {}).get("successful_requests", 0)

    def get_system_avg_response_time(self) -> float:
        """Get system-wide average response time"""
        try:
            total_duration = sum(
                m.get("total_duration", 0) for m in self.metrics.values()
            )
            total_requests = sum(
                m.get("total_requests", 0) for m in self.metrics.values()
            )
            return total_duration / total_requests if total_requests > 0 else 0.0
        except Exception as e:
            logger.error(f"Error getting system avg response time: {e}")
            return 0.0

    def get_rpm(self, domain: str) -> int:
        """Get requests per minute for domain"""
        return len(self.request_history.get(domain, []))

    async def reset_metrics_async(self, domain: str) -> None:
        self.reset_metrics(domain)

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Redis"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Format datetime for Redis storage"""
        if not dt:
            return None
        return dt.isoformat()
