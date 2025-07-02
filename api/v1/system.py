"""
API v1 - System Router

Contains system-related endpoints for v1 API including health checks, metrics, and statistics
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from main_crawler import IranianFlightCrawler
from monitoring import CrawlerMonitor
from api_versioning import APIVersion, api_versioned, add_api_version_headers

router = APIRouter(prefix="/api/v1/system", tags=["system-v1"])

# Response Models
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    metrics: Dict
    error_stats: Dict
    rate_limit_stats: Dict
    timestamp: str
    version: str = "v1"

class MetricsResponse(BaseModel):
    """Metrics response model"""
    metrics: Dict
    timestamp: str
    version: str = "v1"

class StatsResponse(BaseModel):
    """Statistics response model"""
    stats: Dict
    timestamp: str
    version: str = "v1"

class CacheClearRequest(BaseModel):
    """Cache clear request model"""
    pattern: str = "*"

# Dependency functions
async def get_crawler() -> IranianFlightCrawler:
    """Get crawler instance"""
    from main import app
    if not hasattr(app.state, 'crawler') or not app.state.crawler:
        raise HTTPException(status_code=503, detail="Crawler is not available")
    return app.state.crawler

async def get_monitor() -> CrawlerMonitor:
    """Get monitor instance"""
    from main import app
    if not hasattr(app.state, 'monitor') or not app.state.monitor:
        raise HTTPException(status_code=503, detail="Monitor is not available")
    return app.state.monitor

@router.get("/health", response_model=HealthResponse)
@api_versioned(APIVersion.V1)
async def health_check(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    System health check
    
    Returns comprehensive health information including:
    - System status
    - Performance metrics
    - Error statistics
    - Rate limiting status
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        # Get health information
        health_info = await crawler.get_health_status()
        
        return HealthResponse(
            status=health_info.get("status", "unknown"),
            metrics=health_info.get("metrics", {}),
            error_stats=health_info.get("error_stats", {}),
            rate_limit_stats=health_info.get("rate_limit_stats", {}),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        # Return degraded health status on error
        return HealthResponse(
            status="degraded",
            metrics={},
            error_stats={"health_check_error": str(e)},
            rate_limit_stats={},
            timestamp=datetime.now().isoformat()
        )

@router.get("/metrics", response_model=MetricsResponse)
@api_versioned(APIVersion.V1)
async def get_metrics(
    request: Request,
    response: Response,
    monitor: CrawlerMonitor = Depends(get_monitor)
):
    """
    Get system metrics
    
    Returns detailed system metrics including:
    - Performance counters
    - Memory usage
    - Request statistics
    - Site-specific metrics
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        metrics = await monitor.get_all_metrics()
        
        return MetricsResponse(
            metrics=metrics,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.get("/metrics/prometheus", response_class=PlainTextResponse)
@api_versioned(APIVersion.V1)
async def get_prometheus_metrics(
    request: Request,
    monitor: CrawlerMonitor = Depends(get_monitor)
):
    """
    Get system metrics in Prometheus format.
    
    Returns a text-based exposition format that can be scraped by a Prometheus server.
    """
    try:
        return PlainTextResponse(content=monitor.get_prometheus_metrics(), media_type="text/plain; version=0.0.4")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Prometheus metrics: {str(e)}")

@router.get("/stats", response_model=StatsResponse)
@api_versioned(APIVersion.V1)
async def get_stats(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get system statistics
    
    Returns comprehensive system statistics including:
    - Crawling statistics
    - Success/failure rates
    - Site performance
    - Historical data
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        stats = await crawler.get_statistics()
        
        return StatsResponse(
            stats=stats,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.post("/reset")
@api_versioned(APIVersion.V1)
async def reset_stats(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Reset system statistics
    
    Resets all collected statistics and counters.
    This action cannot be undone.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        await crawler.reset_statistics()
        
        return {
            "message": "Statistics reset successfully",
            "reset_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset stats: {str(e)}")

@router.get("/info")
@api_versioned(APIVersion.V1)
async def get_system_info(
    request: Request,
    response: Response
):
    """
    Get system information
    
    Returns basic system information including:
    - API version
    - Supported features
    - System configuration
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        return {
            "api_version": "v1",
            "supported_versions": [v.value for v in APIVersion.get_supported_versions()],
            "features": {
                "flight_search": True,
                "intelligent_search": True,
                "price_prediction": True,
                "monitoring": True,
                "rate_limiting": True,
                "websockets": True
            },
            "endpoints": {
                "flights": "/api/v1/flights",
                "monitoring": "/api/v1/monitoring", 
                "sites": "/api/v1/sites",
                "rate_limits": "/api/v1/rate-limits",
                "system": "/api/v1/system"
            },
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")

@router.get("/airports")
@api_versioned(APIVersion.V1)
async def list_airports(
    request: Request,
    response: Response,
    q: str = Query("", description="Search query for airport name or code"),
    country: str = Query("", description="Filter by country"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of results"),
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    List available airports
    
    Returns list of supported airports with optional filtering.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        airports = await crawler.get_airports(query=q, country=country, limit=limit)
        
        return {
            "airports": airports,
            "count": len(airports),
            "query": q,
            "country_filter": country,
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list airports: {str(e)}")

@router.get("/airports/countries")
@api_versioned(APIVersion.V1)
async def list_countries(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    List available countries
    
    Returns list of countries with available airports.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        countries = await crawler.get_countries()
        
        return {
            "countries": countries,
            "count": len(countries),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list countries: {str(e)}")

@router.post("/cache/clear")
@api_versioned(APIVersion.V1)
async def clear_cache(
    request_data: CacheClearRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Clear system cache
    
    Clears cached data based on the provided pattern.
    Use with caution as this may impact performance.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        cleared_count = await crawler.clear_cache(pattern=request_data.pattern)
        
        return {
            "message": "Cache cleared successfully",
            "pattern": request_data.pattern,
            "cleared_items": cleared_count,
            "cleared_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@router.get("/version")
@api_versioned(APIVersion.V1)
async def get_version_info(
    request: Request,
    response: Response
):
    """
    Get API version information
    
    Returns detailed version information and supported features.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        return {
            "current_version": APIVersion.V1.value,
            "latest_version": APIVersion.get_latest().value,
            "supported_versions": [v.value for v in APIVersion.get_supported_versions()],
            "version_info": {
                "v1": {
                    "status": "active",
                    "deprecated": False,
                    "features": [
                        "flight_search",
                        "intelligent_search", 
                        "price_prediction",
                        "monitoring",
                        "rate_limiting",
                        "websockets"
                    ]
                }
            },
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get version info: {str(e)}") 