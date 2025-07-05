"""
Enhanced Metrics API Endpoint for FlightIO Crawler
Provides comprehensive metrics exposure and aggregation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
import json
import time

from monitoring.enhanced_prometheus_metrics import get_metrics_instance, export_metrics
from monitoring.enhanced_monitoring_system import EnhancedMonitoringSystem
from security.authentication_middleware import get_current_user, require_permissions
from security.authorization_system import UserRole
from config import config

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/metrics", tags=["metrics"])

# Get metrics instance
metrics = get_metrics_instance()

# Initialize monitoring system
monitoring_system = EnhancedMonitoringSystem()


class MetricsResponse(BaseModel):
    """Response model for metrics data"""
    timestamp: datetime = Field(default_factory=datetime.now)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricsFilter(BaseModel):
    """Filter model for metrics queries"""
    component: Optional[str] = None
    site: Optional[str] = None
    time_range: Optional[str] = "1h"  # 1h, 6h, 24h, 7d
    metric_types: Optional[List[str]] = None
    severity: Optional[str] = None


class BusinessMetrics(BaseModel):
    """Business metrics model"""
    total_searches: int = 0
    successful_searches: int = 0
    total_results: int = 0
    average_search_duration: float = 0.0
    popular_routes: List[Dict[str, Any]] = Field(default_factory=list)
    price_trends: Dict[str, Any] = Field(default_factory=dict)
    booking_conversion_rate: float = 0.0


class SystemMetrics(BaseModel):
    """System metrics model"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_io: Dict[str, int] = Field(default_factory=dict)
    open_files: int = 0
    active_connections: int = 0
    uptime_seconds: float = 0.0


class ErrorMetrics(BaseModel):
    """Error metrics model"""
    total_errors: int = 0
    errors_by_type: Dict[str, int] = Field(default_factory=dict)
    errors_by_severity: Dict[str, int] = Field(default_factory=dict)
    error_rate: float = 0.0
    circuit_breaker_states: Dict[str, str] = Field(default_factory=dict)


class CacheMetrics(BaseModel):
    """Cache metrics model"""
    hit_ratio: float = 0.0
    size_bytes: int = 0
    entries_count: int = 0
    evictions_count: int = 0
    operations_per_second: float = 0.0


@router.get("/", response_model=MetricsResponse)
async def get_metrics_overview(
    request: Request,
    filter_params: MetricsFilter = Depends(),
    current_user=Depends(get_current_user)
):
    """Get comprehensive metrics overview"""
    try:
        # Update system metrics
        metrics.update_system_metrics()
        
        # Get metrics summary
        summary = metrics.get_metrics_summary()
        
        # Get business metrics
        business_metrics = await _get_business_metrics(filter_params)
        
        # Get system metrics
        system_metrics = await _get_system_metrics()
        
        # Get error metrics
        error_metrics = await _get_error_metrics(filter_params)
        
        # Get cache metrics
        cache_metrics = await _get_cache_metrics()
        
        return MetricsResponse(
            metrics={
                "business": business_metrics.dict(),
                "system": system_metrics.dict(),
                "errors": error_metrics.dict(),
                "cache": cache_metrics.dict()
            },
            summary=summary,
            metadata={
                "filter": filter_params.dict(),
                "user": current_user.username if current_user else "anonymous",
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting metrics overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics(
    format_type: str = Query("prometheus", description="Format type: prometheus or openmetrics"),
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Get Prometheus formatted metrics"""
    try:
        # Update system metrics before export
        metrics.update_system_metrics()
        
        # Export metrics in requested format
        metrics_data = metrics.export_metrics(format_type)
        
        # Set appropriate content type
        if format_type == "openmetrics":
            response = PlainTextResponse(
                content=metrics_data,
                media_type="application/openmetrics-text"
            )
        else:
            response = PlainTextResponse(
                content=metrics_data,
                media_type="text/plain"
            )
        
        return response
    
    except Exception as e:
        logger.error(f"Error getting Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Prometheus metrics")


@router.get("/business", response_model=BusinessMetrics)
async def get_business_metrics(
    filter_params: MetricsFilter = Depends(),
    current_user=Depends(get_current_user)
):
    """Get business-specific metrics"""
    try:
        return await _get_business_metrics(filter_params)
    
    except Exception as e:
        logger.error(f"Error getting business metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business metrics")


@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics(
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Get system-level metrics"""
    try:
        return await _get_system_metrics()
    
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@router.get("/errors", response_model=ErrorMetrics)
async def get_error_metrics(
    filter_params: MetricsFilter = Depends(),
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Get error and reliability metrics"""
    try:
        return await _get_error_metrics(filter_params)
    
    except Exception as e:
        logger.error(f"Error getting error metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error metrics")


@router.get("/cache", response_model=CacheMetrics)
async def get_cache_metrics(
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Get cache performance metrics"""
    try:
        return await _get_cache_metrics()
    
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache metrics")


@router.get("/health")
async def get_health_metrics(
    current_user=Depends(get_current_user)
):
    """Get health check metrics"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "database": await _check_database_health(),
                "redis": await _check_redis_health(),
                "monitoring": await _check_monitoring_health(),
                "metrics": await _check_metrics_health()
            }
        }
        
        # Determine overall health
        all_healthy = all(check["status"] == "healthy" for check in health_status["checks"].values())
        health_status["status"] = "healthy" if all_healthy else "unhealthy"
        
        return health_status
    
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve health metrics")


@router.get("/alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Get active alerts"""
    try:
        alerts = await monitoring_system.get_active_alerts()
        
        if severity:
            alerts = [alert for alert in alerts if alert.get("severity") == severity]
        
        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.post("/reset")
async def reset_metrics(
    component: Optional[str] = Query(None, description="Component to reset (all if not specified)"),
    current_user=Depends(require_permissions([UserRole.ADMIN]))
):
    """Reset metrics (admin only)"""
    try:
        if component:
            # Reset specific component metrics
            await _reset_component_metrics(component)
        else:
            # Reset all metrics
            await _reset_all_metrics()
        
        return {
            "message": f"Metrics reset successful for {component or 'all components'}",
            "timestamp": datetime.now().isoformat(),
            "reset_by": current_user.username
        }
    
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")


@router.get("/export")
async def export_metrics_data(
    format_type: str = Query("json", description="Export format: json, csv, or prometheus"),
    time_range: str = Query("1h", description="Time range for export"),
    current_user=Depends(require_permissions([UserRole.OPERATOR, UserRole.ADMIN]))
):
    """Export metrics data"""
    try:
        if format_type == "prometheus":
            return PlainTextResponse(
                content=metrics.export_metrics(),
                media_type="text/plain"
            )
        
        # Get metrics data
        data = await _get_metrics_for_export(time_range)
        
        if format_type == "json":
            return data
        elif format_type == "csv":
            csv_data = await _convert_to_csv(data)
            return PlainTextResponse(
                content=csv_data,
                media_type="text/csv"
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported format type")
    
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export metrics")


# Helper functions
async def _get_business_metrics(filter_params: MetricsFilter) -> BusinessMetrics:
    """Get business metrics"""
    # This would typically query a database or metrics store
    # For now, we'll return mock data
    return BusinessMetrics(
        total_searches=1000,
        successful_searches=950,
        total_results=15000,
        average_search_duration=2.5,
        popular_routes=[
            {"route": "THR-IKA", "requests": 150},
            {"route": "THR-MHD", "requests": 120}
        ],
        price_trends={"trend": "increasing", "percentage": 5.2},
        booking_conversion_rate=0.15
    )


async def _get_system_metrics() -> SystemMetrics:
    """Get system metrics"""
    metrics.update_system_metrics()
    summary = metrics.get_metrics_summary()
    
    return SystemMetrics(
        cpu_usage=summary["system_info"]["cpu_percent"],
        memory_usage=summary["system_info"]["memory_usage_mb"],
        disk_usage=0.0,  # This would be calculated
        network_io={"bytes_sent": 0, "bytes_recv": 0},
        open_files=summary["system_info"]["open_files"],
        active_connections=0,  # This would be calculated
        uptime_seconds=summary["uptime_seconds"]
    )


async def _get_error_metrics(filter_params: MetricsFilter) -> ErrorMetrics:
    """Get error metrics"""
    # This would query actual error data
    return ErrorMetrics(
        total_errors=25,
        errors_by_type={"network": 10, "parsing": 8, "timeout": 7},
        errors_by_severity={"low": 15, "medium": 8, "high": 2},
        error_rate=0.025,
        circuit_breaker_states={"site1": "closed", "site2": "open"}
    )


async def _get_cache_metrics() -> CacheMetrics:
    """Get cache metrics"""
    return CacheMetrics(
        hit_ratio=0.85,
        size_bytes=1024 * 1024 * 50,  # 50MB
        entries_count=1000,
        evictions_count=25,
        operations_per_second=150.0
    )


async def _check_database_health() -> Dict[str, Any]:
    """Check database health"""
    # This would perform actual database health check
    return {"status": "healthy", "latency_ms": 5.2}


async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis health"""
    # This would perform actual Redis health check
    return {"status": "healthy", "latency_ms": 1.8}


async def _check_monitoring_health() -> Dict[str, Any]:
    """Check monitoring system health"""
    return {"status": "healthy", "active_checks": 15}


async def _check_metrics_health() -> Dict[str, Any]:
    """Check metrics system health"""
    return {"status": "healthy", "metrics_count": 250}


async def _reset_component_metrics(component: str):
    """Reset metrics for specific component"""
    # This would reset specific component metrics
    pass


async def _reset_all_metrics():
    """Reset all metrics"""
    # This would reset all metrics
    pass


async def _get_metrics_for_export(time_range: str) -> Dict[str, Any]:
    """Get metrics data for export"""
    # This would query historical metrics data
    return {
        "export_time": datetime.now().isoformat(),
        "time_range": time_range,
        "data": {}
    }


async def _convert_to_csv(data: Dict[str, Any]) -> str:
    """Convert metrics data to CSV format"""
    # This would convert the data to CSV format
    return "timestamp,metric,value\n"  # Placeholder 