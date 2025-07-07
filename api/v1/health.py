"""
Health Check Module for FlightIO API
Comprehensive health monitoring for all system components
Enhanced with deep health monitoring and circuit breaker integration
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
import psutil
import redis
import psycopg2
from psycopg2 import sql
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import aiohttp
import logging
from dataclasses import dataclass
from enum import Enum
import os

from monitoring.comprehensive_health_checks import (
    get_health_checker, check_system_health, check_component_health, 
    HealthStatus as ComprehensiveHealthStatus
)
from security.authentication_middleware import get_current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Initialize comprehensive health checker
comprehensive_health_checker = get_health_checker()


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    name: str
    status: HealthStatus
    response_time_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthChecker:
    """Comprehensive health checker for all system components"""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
        self.start_time = time.time()
    
    async def check_database(self) -> HealthCheck:
        """Check PostgreSQL database connectivity and performance"""
        start_time = time.time()
        try:
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'flight_data'),
                'user': os.getenv('DB_USER', 'crawler'),
                'password': os.getenv('DB_PASSWORD', 'secure_password')
            }
            
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            
            # Test basic connectivity
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            # Check database size
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as size
            """)
            db_size = cursor.fetchone()[0]
            
            # Check active connections
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity 
                WHERE state = 'active'
            """)
            active_connections = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY if response_time < 1000 else HealthStatus.DEGRADED,
                response_time_ms=response_time,
                details={
                    "database_size": db_size,
                    "active_connections": active_connections,
                    "host": db_config['host'],
                    "port": db_config['port']
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database health check failed: {str(e)}")
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e)
            )
    
    async def check_redis(self) -> HealthCheck:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        try:
            redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                socket_timeout=5
            )
            
            # Test connectivity
            redis_client.ping()
            
            # Get Redis info
            info = redis_client.info()
            memory_usage = info.get('used_memory_human', 'N/A')
            connected_clients = info.get('connected_clients', 0)
            
            # Test read/write operations
            test_key = "health_check_test"
            redis_client.set(test_key, "test_value", ex=10)
            test_value = redis_client.get(test_key)
            redis_client.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY if response_time < 500 else HealthStatus.DEGRADED,
                response_time_ms=response_time,
                details={
                    "memory_usage": memory_usage,
                    "connected_clients": connected_clients,
                    "redis_version": info.get('redis_version', 'unknown'),
                    "read_write_test": "passed" if test_value == b"test_value" else "failed"
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Redis health check failed: {str(e)}")
            return HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e)
            )
    
    async def check_system_resources(self) -> HealthCheck:
        """Check system resource utilization"""
        start_time = time.time()
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Load average (Unix systems)
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                load_avg = None
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on resource usage
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 95:
                status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70 or memory_percent > 80 or disk_percent > 85:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheck(
                name="system_resources",
                status=status,
                response_time_ms=response_time,
                details={
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_percent": round(memory_percent, 2),
                    "disk_percent": round(disk_percent, 2),
                    "load_average": load_avg,
                    "uptime_seconds": time.time() - self.start_time
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"System resources health check failed: {str(e)}")
            return HealthCheck(
                name="system_resources",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e)
            )
    
    async def check_external_services(self) -> HealthCheck:
        """Check external service dependencies"""
        start_time = time.time()
        try:
            external_checks = []
            
            # Test external API endpoints if any
            test_urls = [
                "https://httpbin.org/status/200",  # Test external connectivity
            ]
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for url in test_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                external_checks.append({"url": url, "status": "healthy"})
                            else:
                                external_checks.append({"url": url, "status": "degraded", "http_status": response.status})
                    except Exception as e:
                        external_checks.append({"url": url, "status": "unhealthy", "error": str(e)})
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine overall status
            unhealthy_count = sum(1 for check in external_checks if check.get('status') == 'unhealthy')
            if unhealthy_count > 0:
                status = HealthStatus.DEGRADED  # External services are not critical
            else:
                status = HealthStatus.HEALTHY
            
            return HealthCheck(
                name="external_services",
                status=status,
                response_time_ms=response_time,
                details={
                    "checks": external_checks,
                    "total_checks": len(external_checks),
                    "healthy_count": sum(1 for check in external_checks if check.get('status') == 'healthy')
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"External services health check failed: {str(e)}")
            return HealthCheck(
                name="external_services",
                status=HealthStatus.DEGRADED,  # Not critical
                response_time_ms=response_time,
                error=str(e)
            )
    
    async def run_all_checks(self) -> List[HealthCheck]:
        """Run all health checks concurrently"""
        tasks = [
            self.check_database(),
            self.check_redis(),
            self.check_system_resources(),
            self.check_external_services()
        ]
        
        self.checks = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        for i, check in enumerate(self.checks):
            if isinstance(check, Exception):
                logger.error(f"Health check {i} failed with exception: {check}")
                self.checks[i] = HealthCheck(
                    name=f"check_{i}",
                    status=HealthStatus.UNHEALTHY,
                    error=str(check)
                )
        
        return self.checks


# API Routes
@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """
    Basic health check endpoint
    Returns overall system health status
    """
    checker = HealthChecker()
    checks = await checker.run_all_checks()
    
    # Calculate overall status
    unhealthy_count = sum(1 for check in checks if check.status == HealthStatus.UNHEALTHY)
    degraded_count = sum(1 for check in checks if check.status == HealthStatus.DEGRADED)
    
    if unhealthy_count > 0:
        overall_status = HealthStatus.UNHEALTHY
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif degraded_count > 0:
        overall_status = HealthStatus.DEGRADED
        http_status = status.HTTP_200_OK
    else:
        overall_status = HealthStatus.HEALTHY
        http_status = status.HTTP_200_OK
    
    response_data = {
        "status": overall_status,
        "timestamp": time.time(),
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                "error": check.error
            }
            for check in checks
        ],
        "summary": {
            "total_checks": len(checks),
            "healthy": sum(1 for check in checks if check.status == HealthStatus.HEALTHY),
            "degraded": degraded_count,
            "unhealthy": unhealthy_count
        }
    }
    
    return JSONResponse(content=response_data, status_code=http_status)


@router.get("/live", response_model=Dict[str, str])
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint
    Simple check to see if the application is running
    """
    return {"status": "alive", "timestamp": time.time()}


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint
    Checks if the application is ready to serve traffic
    """
    checker = HealthChecker()
    
    # Only check critical services for readiness
    db_check = await checker.check_database()
    redis_check = await checker.check_redis()
    
    critical_checks = [db_check, redis_check]
    unhealthy_critical = sum(1 for check in critical_checks if check.status == HealthStatus.UNHEALTHY)
    
    if unhealthy_critical > 0:
        return JSONResponse(
            content={
                "status": "not_ready",
                "timestamp": time.time(),
                "critical_checks": [
                    {"name": check.name, "status": check.status, "error": check.error}
                    for check in critical_checks
                ]
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    return {
        "status": "ready",
        "timestamp": time.time(),
        "critical_services": "healthy"
    }


# Enhanced comprehensive health check endpoints
@router.get("/comprehensive", response_model=Dict[str, Any])
async def comprehensive_health_check(
    current_user=Depends(get_current_user)
):
    """Enhanced comprehensive health check with deep system monitoring"""
    try:
        # Get comprehensive health status
        health_status = await check_system_health()
        
        # Determine HTTP status code based on health
        status_code = status.HTTP_200_OK
        if health_status["status"] == "unhealthy":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_status["status"] == "degraded":
            status_code = status.HTTP_206_PARTIAL_CONTENT
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/component/{component_name}", response_model=Dict[str, Any])
async def component_health_check(
    component_name: str,
    current_user=Depends(get_current_user)
):
    """Check health of specific system component"""
    try:
        result = await check_component_health(component_name)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component '{component_name}' not found"
            )
        
        # Determine HTTP status code
        status_code = status.HTTP_200_OK
        if result.status == ComprehensiveHealthStatus.UNHEALTHY:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif result.status == ComprehensiveHealthStatus.DEGRADED:
            status_code = status.HTTP_206_PARTIAL_CONTENT
        
        return JSONResponse(
            status_code=status_code,
            content=result.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component health check failed for {component_name}: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "name": component_name,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/dependencies", response_model=Dict[str, Any])
async def dependencies_health_check(
    current_user=Depends(get_current_user)
):
    """Check health of all external dependencies with circuit breaker status"""
    try:
        dependencies = ["database", "redis", "network_connectivity", "circuit_breakers"]
        dependency_results = {}
        
        for dep in dependencies:
            result = await check_component_health(dep)
            if result:
                dependency_results[dep] = {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "details": result.details
                }
        
        # Overall dependency health
        all_healthy = all(
            result.get("status") == "healthy" 
            for result in dependency_results.values()
        )
        
        any_unhealthy = any(
            result.get("status") == "unhealthy" 
            for result in dependency_results.values()
        )
        
        overall_status = "healthy"
        status_code = status.HTTP_200_OK
        
        if any_unhealthy:
            overall_status = "unhealthy"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif not all_healthy:
            overall_status = "degraded"
            status_code = status.HTTP_206_PARTIAL_CONTENT
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": overall_status,
                "timestamp": time.time(),
                "dependencies": dependency_results,
                "summary": {
                    "total": len(dependency_results),
                    "healthy": len([r for r in dependency_results.values() if r.get("status") == "healthy"]),
                    "degraded": len([r for r in dependency_results.values() if r.get("status") == "degraded"]),
                    "unhealthy": len([r for r in dependency_results.values() if r.get("status") == "unhealthy"])
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Dependencies check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/circuit-breakers", response_model=Dict[str, Any])
async def circuit_breakers_status(
    current_user=Depends(get_current_user)
):
    """Get circuit breaker status for all monitored services"""
    try:
        result = await check_component_health("circuit_breakers")
        
        if not result:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "Circuit breaker monitoring not available"}
            )
        
        status_code = status.HTTP_200_OK
        if result.status == ComprehensiveHealthStatus.UNHEALTHY:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif result.status == ComprehensiveHealthStatus.DEGRADED:
            status_code = status.HTTP_206_PARTIAL_CONTENT
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": result.status.value,
                "timestamp": time.time(),
                "circuit_breakers": result.details,
                "message": result.message
            }
        )
        
    except Exception as e:
        logger.error(f"Circuit breaker status check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.post("/monitoring/start", response_model=Dict[str, Any])
async def start_health_monitoring(
    current_user=Depends(get_current_user)
):
    """Start continuous health monitoring"""
    try:
        await comprehensive_health_checker.start_periodic_checks()
        
        return {
            "status": "started",
            "timestamp": time.time(),
            "message": "Continuous health monitoring started",
            "monitoring_interval": comprehensive_health_checker.config.get("check_interval", 60)
        }
        
    except Exception as e:
        logger.error(f"Failed to start health monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start health monitoring"
        )


@router.post("/monitoring/stop", response_model=Dict[str, Any])
async def stop_health_monitoring(
    current_user=Depends(get_current_user)
):
    """Stop continuous health monitoring"""
    try:
        await comprehensive_health_checker.stop_periodic_checks()
        
        return {
            "status": "stopped",
            "timestamp": time.time(),
            "message": "Continuous health monitoring stopped"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop health monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop health monitoring"
        ) 