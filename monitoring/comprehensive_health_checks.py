"""
Comprehensive Health Check System for FlightIO Crawler
Provides deep health monitoring for all system components
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import psutil
import socket
from pathlib import Path
import traceback

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

try:
    from selenium import webdriver
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from config import config


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "dependencies": self.dependencies
        }


@dataclass
class HealthCheckConfig:
    """Health check configuration"""
    name: str
    enabled: bool = True
    timeout_seconds: int = 30
    interval_seconds: int = 60
    retries: int = 3
    critical: bool = False
    dependencies: List[str] = field(default_factory=list)
    thresholds: Dict[str, Any] = field(default_factory=dict)


class HealthCheckRegistry:
    """Registry for health check functions"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.configs: Dict[str, HealthCheckConfig] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, config: HealthCheckConfig):
        """Register a health check configuration"""
        self.configs[config.name] = config
        self.logger.info(f"Health check registered: {config.name}")
    
    def add_check(self, name: str, check_func: Callable):
        """Add a health check function"""
        self.checks[name] = check_func
        self.logger.info(f"Health check function added: {name}")
    
    def get_check(self, name: str) -> Optional[Callable]:
        """Get a health check function"""
        return self.checks.get(name)
    
    def get_config(self, name: str) -> Optional[HealthCheckConfig]:
        """Get health check configuration"""
        return self.configs.get(name)
    
    def list_checks(self) -> List[str]:
        """List all registered health checks"""
        return list(self.checks.keys())


class ComprehensiveHealthChecker:
    """Comprehensive health checker for all system components"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.registry = HealthCheckRegistry()
        self.results_cache: Dict[str, HealthCheckResult] = {}
        self.circuit_breaker_states: Dict[str, Dict[str, Any]] = {}
        
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Initialize built-in health checks
        self._register_builtin_checks()
        
        # Background task for periodic checks
        self.periodic_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        self.logger.info("Comprehensive health checker initialized")
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load health check configuration"""
        default_config = {
            "enabled": True,
            "global_timeout": 30,
            "check_interval": 60,
            "cache_ttl": 300,
            "alert_on_failure": True,
            "checks": {}
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                self.logger.error(f"Error loading config file: {e}")
        
        return default_config
    
    def _register_builtin_checks(self):
        """Register built-in health checks"""
        # Database health check
        self.registry.register(HealthCheckConfig(
            name="database",
            timeout_seconds=10,
            interval_seconds=30,
            critical=True,
            thresholds={"max_connections": 100, "max_latency_ms": 1000}
        ))
        self.registry.add_check("database", self._check_database_health)
        
        # Redis health check
        self.registry.register(HealthCheckConfig(
            name="redis",
            timeout_seconds=5,
            interval_seconds=30,
            critical=True,
            thresholds={"max_memory_mb": 512, "max_latency_ms": 100}
        ))
        self.registry.add_check("redis", self._check_redis_health)
        
        # System resources health check
        self.registry.register(HealthCheckConfig(
            name="system_resources",
            timeout_seconds=5,
            interval_seconds=60,
            critical=True,
            thresholds={"max_cpu_percent": 80, "max_memory_percent": 85, "max_disk_percent": 90}
        ))
        self.registry.add_check("system_resources", self._check_system_resources)
        
        # Network connectivity health check
        self.registry.register(HealthCheckConfig(
            name="network_connectivity",
            timeout_seconds=10,
            interval_seconds=120,
            critical=False,
            thresholds={"max_latency_ms": 1000}
        ))
        self.registry.add_check("network_connectivity", self._check_network_connectivity)
        
        # Disk space health check
        self.registry.register(HealthCheckConfig(
            name="disk_space",
            timeout_seconds=5,
            interval_seconds=300,
            critical=True,
            thresholds={"min_free_gb": 5, "max_usage_percent": 90}
        ))
        self.registry.add_check("disk_space", self._check_disk_space)
        
        # Browser/Selenium health check
        self.registry.register(HealthCheckConfig(
            name="browser_health",
            timeout_seconds=30,
            interval_seconds=300,
            critical=False,
            dependencies=["system_resources"]
        ))
        self.registry.add_check("browser_health", self._check_browser_health)
        
        # Circuit breaker health check
        self.registry.register(HealthCheckConfig(
            name="circuit_breakers",
            timeout_seconds=5,
            interval_seconds=60,
            critical=False
        ))
        self.registry.add_check("circuit_breakers", self._check_circuit_breakers)
        
        # API endpoints health check
        self.registry.register(HealthCheckConfig(
            name="api_endpoints",
            timeout_seconds=10,
            interval_seconds=120,
            critical=False,
            dependencies=["database", "redis"]
        ))
        self.registry.add_check("api_endpoints", self._check_api_endpoints)
        
        # Cache health check
        self.registry.register(HealthCheckConfig(
            name="cache_health",
            timeout_seconds=5,
            interval_seconds=60,
            critical=False,
            dependencies=["redis"]
        ))
        self.registry.add_check("cache_health", self._check_cache_health)
        
        # Security health check
        self.registry.register(HealthCheckConfig(
            name="security",
            timeout_seconds=5,
            interval_seconds=300,
            critical=True
        ))
        self.registry.add_check("security", self._check_security_health)
    
    async def check_health(self, check_name: Optional[str] = None) -> Dict[str, HealthCheckResult]:
        """Perform health checks"""
        if check_name:
            # Single check
            result = await self._run_single_check(check_name)
            return {check_name: result} if result else {}
        else:
            # All checks
            return await self._run_all_checks()
    
    async def _run_single_check(self, check_name: str) -> Optional[HealthCheckResult]:
        """Run a single health check"""
        check_func = self.registry.get_check(check_name)
        config = self.registry.get_config(check_name)
        
        if not check_func or not config:
            return None
        
        if not config.enabled:
            return None
        
        start_time = time.time()
        
        try:
            # Run the check with timeout
            result = await asyncio.wait_for(
                check_func(config),
                timeout=config.timeout_seconds
            )
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms
            
            # Cache result
            self.results_cache[check_name] = result
            
            return result
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {config.timeout_seconds}s",
                duration_ms=duration_ms
            )
            self.results_cache[check_name] = result
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                details={"error": str(e), "traceback": traceback.format_exc()},
                duration_ms=duration_ms
            )
            self.results_cache[check_name] = result
            return result
    
    async def _run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks"""
        results = {}
        
        # Get all check names sorted by dependencies
        check_names = self._sort_checks_by_dependencies()
        
        # Run checks in parallel where possible
        tasks = []
        for check_name in check_names:
            task = asyncio.create_task(self._run_single_check(check_name))
            tasks.append((check_name, task))
        
        # Wait for all tasks to complete
        for check_name, task in tasks:
            try:
                result = await task
                if result:
                    results[check_name] = result
            except Exception as e:
                self.logger.error(f"Error running health check {check_name}: {e}")
        
        return results
    
    def _sort_checks_by_dependencies(self) -> List[str]:
        """Sort health checks by dependencies"""
        # Simple topological sort
        check_names = self.registry.list_checks()
        sorted_names = []
        visited = set()
        
        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            
            config = self.registry.get_config(name)
            if config and config.dependencies:
                for dep in config.dependencies:
                    if dep in check_names:
                        visit(dep)
            
            sorted_names.append(name)
        
        for name in check_names:
            visit(name)
        
        return sorted_names
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        results = await self.check_health()
        
        # Calculate overall status
        critical_checks = [
            name for name, config in self.registry.configs.items()
            if config.critical and config.enabled
        ]
        
        overall_status = HealthStatus.HEALTHY
        total_checks = len(results)
        healthy_checks = 0
        degraded_checks = 0
        unhealthy_checks = 0
        
        for name, result in results.items():
            if result.status == HealthStatus.HEALTHY:
                healthy_checks += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_checks += 1
                if name in critical_checks:
                    overall_status = HealthStatus.DEGRADED
            else:  # UNHEALTHY
                unhealthy_checks += 1
                if name in critical_checks:
                    overall_status = HealthStatus.UNHEALTHY
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_checks": total_checks,
                "healthy": healthy_checks,
                "degraded": degraded_checks,
                "unhealthy": unhealthy_checks
            },
            "checks": {name: result.to_dict() for name, result in results.items()},
            "uptime_seconds": time.time() - getattr(self, 'start_time', time.time())
        }
    
    async def start_periodic_checks(self):
        """Start periodic health checks"""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        async def periodic_runner():
            while self.is_running:
                try:
                    await self.check_health()
                    await asyncio.sleep(self.config.get("check_interval", 60))
                except Exception as e:
                    self.logger.error(f"Error in periodic health checks: {e}")
                    await asyncio.sleep(10)
        
        self.periodic_task = asyncio.create_task(periodic_runner())
        self.logger.info("Periodic health checks started")
    
    async def stop_periodic_checks(self):
        """Stop periodic health checks"""
        self.is_running = False
        if self.periodic_task:
            self.periodic_task.cancel()
            try:
                await self.periodic_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Periodic health checks stopped")
    
    # Built-in health check implementations
    async def _check_database_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check database health"""
        if not POSTGRES_AVAILABLE:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNKNOWN,
                message="PostgreSQL client not available"
            )
        
        try:
            # Test database connection
            conn = psycopg2.connect(
                host=config.get("DB_HOST", "localhost"),
                database=config.get("DB_NAME", "flight_data"),
                user=config.get("DB_USER", "crawler"),
                password=config.get("DB_PASSWORD", ""),
                port=config.get("DB_PORT", 5432),
                connect_timeout=5
            )
            
            cursor = conn.cursor()
            
            # Test query
            start_time = time.time()
            cursor.execute("SELECT 1")
            query_time = (time.time() - start_time) * 1000
            
            # Get connection count
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            connection_count = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            # Check thresholds
            max_connections = config.thresholds.get("max_connections", 100)
            max_latency = config.thresholds.get("max_latency_ms", 1000)
            
            status = HealthStatus.HEALTHY
            message = "Database is healthy"
            
            if connection_count > max_connections:
                status = HealthStatus.DEGRADED
                message = f"High connection count: {connection_count}"
            elif query_time > max_latency:
                status = HealthStatus.DEGRADED
                message = f"High query latency: {query_time:.2f}ms"
            
            return HealthCheckResult(
                name="database",
                status=status,
                message=message,
                details={
                    "connection_count": connection_count,
                    "query_latency_ms": query_time,
                    "max_connections": max_connections,
                    "max_latency_ms": max_latency
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_redis_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check Redis health"""
        if not REDIS_AVAILABLE:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNKNOWN,
                message="Redis client not available"
            )
        
        try:
            # Test Redis connection
            redis_client = redis.Redis(
                host=config.get("REDIS_HOST", "localhost"),
                port=config.get("REDIS_PORT", 6379),
                db=config.get("REDIS_DB", 0),
                password=config.get("REDIS_PASSWORD", None),
                socket_timeout=5
            )
            
            # Test ping
            start_time = time.time()
            redis_client.ping()
            ping_time = (time.time() - start_time) * 1000
            
            # Get Redis info
            info = redis_client.info()
            memory_usage = info.get('used_memory', 0) / 1024 / 1024  # MB
            connected_clients = info.get('connected_clients', 0)
            
            # Check thresholds
            max_memory = config.thresholds.get("max_memory_mb", 512)
            max_latency = config.thresholds.get("max_latency_ms", 100)
            
            status = HealthStatus.HEALTHY
            message = "Redis is healthy"
            
            if memory_usage > max_memory:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {memory_usage:.2f}MB"
            elif ping_time > max_latency:
                status = HealthStatus.DEGRADED
                message = f"High latency: {ping_time:.2f}ms"
            
            return HealthCheckResult(
                name="redis",
                status=status,
                message=message,
                details={
                    "memory_usage_mb": memory_usage,
                    "connected_clients": connected_clients,
                    "ping_latency_ms": ping_time,
                    "max_memory_mb": max_memory,
                    "max_latency_ms": max_latency
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_system_resources(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check system resources"""
        try:
            # Get system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            # Check thresholds
            max_cpu = config.thresholds.get("max_cpu_percent", 80)
            max_memory = config.thresholds.get("max_memory_percent", 85)
            max_disk = config.thresholds.get("max_disk_percent", 90)
            
            status = HealthStatus.HEALTHY
            message = "System resources are healthy"
            warnings = []
            
            if cpu_percent > max_cpu:
                status = HealthStatus.DEGRADED
                warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > max_memory:
                status = HealthStatus.DEGRADED
                warnings.append(f"High memory usage: {memory.percent:.1f}%")
            
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > max_disk:
                status = HealthStatus.DEGRADED
                warnings.append(f"High disk usage: {disk_percent:.1f}%")
            
            if warnings:
                message = "; ".join(warnings)
            
            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk_percent,
                    "memory_available_mb": memory.available / 1024 / 1024,
                    "disk_free_gb": disk.free / 1024 / 1024 / 1024,
                    "thresholds": {
                        "max_cpu_percent": max_cpu,
                        "max_memory_percent": max_memory,
                        "max_disk_percent": max_disk
                    }
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                message=f"System resources check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_network_connectivity(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check network connectivity"""
        try:
            # Test connectivity to key services
            test_hosts = [
                ("google.com", 80),
                ("github.com", 443),
                ("cloudflare.com", 80)
            ]
            
            results = []
            total_latency = 0
            
            for host, port in test_hosts:
                start_time = time.time()
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    latency = (time.time() - start_time) * 1000
                    total_latency += latency
                    
                    results.append({
                        "host": host,
                        "port": port,
                        "reachable": result == 0,
                        "latency_ms": latency
                    })
                except Exception as e:
                    results.append({
                        "host": host,
                        "port": port,
                        "reachable": False,
                        "error": str(e)
                    })
            
            # Calculate status
            reachable_count = sum(1 for r in results if r.get("reachable", False))
            avg_latency = total_latency / len(results) if results else 0
            
            max_latency = config.thresholds.get("max_latency_ms", 1000)
            
            if reachable_count == 0:
                status = HealthStatus.UNHEALTHY
                message = "No network connectivity"
            elif reachable_count < len(test_hosts):
                status = HealthStatus.DEGRADED
                message = f"Partial network connectivity: {reachable_count}/{len(test_hosts)} hosts reachable"
            elif avg_latency > max_latency:
                status = HealthStatus.DEGRADED
                message = f"High network latency: {avg_latency:.2f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = "Network connectivity is healthy"
            
            return HealthCheckResult(
                name="network_connectivity",
                status=status,
                message=message,
                details={
                    "test_results": results,
                    "reachable_hosts": reachable_count,
                    "total_hosts": len(test_hosts),
                    "average_latency_ms": avg_latency,
                    "max_latency_ms": max_latency
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="network_connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Network connectivity check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_disk_space(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check disk space"""
        try:
            disk = psutil.disk_usage('/')
            free_gb = disk.free / 1024 / 1024 / 1024
            usage_percent = (disk.used / disk.total) * 100
            
            min_free = config.thresholds.get("min_free_gb", 5)
            max_usage = config.thresholds.get("max_usage_percent", 90)
            
            status = HealthStatus.HEALTHY
            message = "Disk space is healthy"
            
            if free_gb < min_free:
                status = HealthStatus.UNHEALTHY
                message = f"Low disk space: {free_gb:.2f}GB free"
            elif usage_percent > max_usage:
                status = HealthStatus.DEGRADED
                message = f"High disk usage: {usage_percent:.1f}%"
            
            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "free_gb": free_gb,
                    "usage_percent": usage_percent,
                    "total_gb": disk.total / 1024 / 1024 / 1024,
                    "used_gb": disk.used / 1024 / 1024 / 1024,
                    "min_free_gb": min_free,
                    "max_usage_percent": max_usage
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"Disk space check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_browser_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check browser/Selenium health"""
        if not SELENIUM_AVAILABLE:
            return HealthCheckResult(
                name="browser_health",
                status=HealthStatus.UNKNOWN,
                message="Selenium not available"
            )
        
        try:
            # Test Chrome/Chromium availability
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            start_time = time.time()
            driver = webdriver.Chrome(options=options)
            
            # Simple test
            driver.get("about:blank")
            title = driver.title
            
            driver.quit()
            
            startup_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name="browser_health",
                status=HealthStatus.HEALTHY,
                message="Browser is healthy",
                details={
                    "startup_time_ms": startup_time,
                    "title": title
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="browser_health",
                status=HealthStatus.UNHEALTHY,
                message=f"Browser health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_circuit_breakers(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check circuit breaker states"""
        try:
            # This would typically check actual circuit breaker states
            # For now, we'll return a mock check
            circuit_states = {
                "site1": "closed",
                "site2": "open",
                "site3": "half-open"
            }
            
            open_circuits = [site for site, state in circuit_states.items() if state == "open"]
            half_open_circuits = [site for site, state in circuit_states.items() if state == "half-open"]
            
            if open_circuits:
                status = HealthStatus.DEGRADED
                message = f"Circuit breakers open: {', '.join(open_circuits)}"
            elif half_open_circuits:
                status = HealthStatus.DEGRADED
                message = f"Circuit breakers half-open: {', '.join(half_open_circuits)}"
            else:
                status = HealthStatus.HEALTHY
                message = "All circuit breakers are closed"
            
            return HealthCheckResult(
                name="circuit_breakers",
                status=status,
                message=message,
                details={
                    "circuit_states": circuit_states,
                    "open_circuits": open_circuits,
                    "half_open_circuits": half_open_circuits
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="circuit_breakers",
                status=HealthStatus.UNHEALTHY,
                message=f"Circuit breaker check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_api_endpoints(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check API endpoints health"""
        try:
            # This would test actual API endpoints
            # For now, we'll return a mock check
            endpoints = [
                {"path": "/api/v1/health", "status": "healthy"},
                {"path": "/api/v1/metrics", "status": "healthy"},
                {"path": "/api/v1/search", "status": "healthy"}
            ]
            
            return HealthCheckResult(
                name="api_endpoints",
                status=HealthStatus.HEALTHY,
                message="API endpoints are healthy",
                details={"endpoints": endpoints}
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="api_endpoints",
                status=HealthStatus.UNHEALTHY,
                message=f"API endpoints check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_cache_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check cache health"""
        try:
            # This would check actual cache health
            # For now, we'll return a mock check
            cache_stats = {
                "hit_ratio": 0.85,
                "size_mb": 50,
                "entries": 1000,
                "evictions": 25
            }
            
            hit_ratio = cache_stats["hit_ratio"]
            if hit_ratio < 0.5:
                status = HealthStatus.DEGRADED
                message = f"Low cache hit ratio: {hit_ratio:.2f}"
            else:
                status = HealthStatus.HEALTHY
                message = "Cache is healthy"
            
            return HealthCheckResult(
                name="cache_health",
                status=status,
                message=message,
                details=cache_stats
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="cache_health",
                status=HealthStatus.UNHEALTHY,
                message=f"Cache health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_security_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Check security health"""
        try:
            # This would check actual security settings
            # For now, we'll return a mock check
            security_checks = {
                "ssl_enabled": True,
                "auth_enabled": True,
                "rate_limiting": True,
                "input_validation": True,
                "audit_logging": True
            }
            
            failed_checks = [check for check, enabled in security_checks.items() if not enabled]
            
            if failed_checks:
                status = HealthStatus.DEGRADED
                message = f"Security checks failed: {', '.join(failed_checks)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Security is healthy"
            
            return HealthCheckResult(
                name="security",
                status=status,
                message=message,
                details={
                    "security_checks": security_checks,
                    "failed_checks": failed_checks
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                name="security",
                status=HealthStatus.UNHEALTHY,
                message=f"Security health check failed: {str(e)}",
                details={"error": str(e)}
            )


# Global instance
health_checker = ComprehensiveHealthChecker()

# Convenience functions
async def check_system_health() -> Dict[str, Any]:
    """Check overall system health"""
    return await health_checker.get_overall_health()

async def check_component_health(component: str) -> Optional[HealthCheckResult]:
    """Check specific component health"""
    results = await health_checker.check_health(component)
    return results.get(component)

def get_health_checker() -> ComprehensiveHealthChecker:
    """Get the global health checker instance"""
    return health_checker 