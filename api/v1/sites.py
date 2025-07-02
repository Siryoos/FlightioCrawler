"""
API v1 - Sites Router

Contains site management endpoints for v1 API including site status, testing, and control
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, Request, Response
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from pydantic import BaseModel
import logging

from main_crawler import IranianFlightCrawler
from api_versioning import APIVersion, api_versioned, add_api_version_headers

router = APIRouter(prefix="/api/v1/sites", tags=["sites-v1"])

# Request/Response Models
class SiteTestRequest(BaseModel):
    """Site test request model"""
    origin: str
    destination: str
    date: str
    passengers: int = 1
    seat_class: str = "economy"

class SiteStatusResponse(BaseModel):
    """Site status response model"""
    site_name: str
    status: str
    health: str
    last_check: str
    error_count: int
    success_rate: float
    average_response_time: float
    enabled: bool

# Dependency functions
async def get_crawler() -> IranianFlightCrawler:
    """Get crawler instance"""
    from main import app
    if not hasattr(app.state, 'crawler') or not app.state.crawler:
        raise HTTPException(status_code=503, detail="Crawler is not available")
    return app.state.crawler

@router.get("/status")
@api_versioned(APIVersion.V1)
async def get_all_sites_status(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get status of all sites
    
    Returns comprehensive status information for all supported sites
    including health, performance metrics, and error statistics.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        sites_status = await crawler.get_all_sites_status()
        
        # Format response
        sites_list = []
        for site_name, status_data in sites_status.items():
            site_info = SiteStatusResponse(
                site_name=site_name,
                status=status_data.get("status", "unknown"),
                health=status_data.get("health", "unknown"),
                last_check=status_data.get("last_check", ""),
                error_count=status_data.get("error_count", 0),
                success_rate=status_data.get("success_rate", 0.0),
                average_response_time=status_data.get("avg_response_time", 0.0),
                enabled=status_data.get("enabled", False)
            )
            sites_list.append(site_info.dict())
        
        return {
            "sites": sites_list,
            "total_sites": len(sites_list),
            "healthy_sites": len([s for s in sites_list if s["health"] == "healthy"]),
            "enabled_sites": len([s for s in sites_list if s["enabled"]]),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sites status: {str(e)}")

@router.get("/{site_name}/status")
@api_versioned(APIVersion.V1)
async def get_site_status(
    site_name: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get status of a specific site
    
    Returns detailed status information for the specified site.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        site_status = await crawler.get_site_status(site_name)
        
        if not site_status:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        
        return {
            "site_name": site_name,
            "status": site_status,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get site status: {str(e)}")

@router.post("/{site_name}/test")
@api_versioned(APIVersion.V1)
async def test_site(
    site_name: str,
    test_data: SiteTestRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Test a specific site
    
    Performs a test crawl on the specified site with the provided parameters
    to verify functionality and performance.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        # Perform site test
        test_result = await crawler.test_site(
            site_name=site_name,
            origin=test_data.origin,
            destination=test_data.destination,
            date=test_data.date,
            passengers=test_data.passengers,
            seat_class=test_data.seat_class
        )
        
        return {
            "site_name": site_name,
            "test_parameters": {
                "origin": test_data.origin,
                "destination": test_data.destination,
                "date": test_data.date,
                "passengers": test_data.passengers,
                "seat_class": test_data.seat_class
            },
            "test_result": test_result,
            "test_timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Site test failed: {str(e)}")

@router.get("/{site_name}/health")
@api_versioned(APIVersion.V1)
async def check_site_health(
    site_name: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Check health of a specific site
    
    Performs a health check on the specified site to verify
    connectivity and basic functionality.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        health_result = await crawler.check_site_health(site_name)
        
        return {
            "site_name": site_name,
            "health_status": health_result.get("status", "unknown"),
            "response_time": health_result.get("response_time", 0),
            "error_details": health_result.get("error_details"),
            "checked_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.post("/{site_name}/enable")
@api_versioned(APIVersion.V1)
async def enable_site(
    site_name: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Enable a site
    
    Enables the specified site for crawling operations.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await crawler.enable_site(site_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        
        return {
            "message": f"Site '{site_name}' enabled successfully",
            "site_name": site_name,
            "enabled": True,
            "enabled_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable site: {str(e)}")

@router.post("/{site_name}/disable")
@api_versioned(APIVersion.V1)
async def disable_site(
    site_name: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Disable a site
    
    Disables the specified site from crawling operations.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await crawler.disable_site(site_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        
        return {
            "message": f"Site '{site_name}' disabled successfully",
            "site_name": site_name,
            "enabled": False,
            "disabled_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable site: {str(e)}")

@router.post("/{site_name}/reset")
@api_versioned(APIVersion.V1)
async def reset_site_errors(
    site_name: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Reset site error statistics
    
    Clears error statistics and counters for the specified site.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await crawler.reset_site_errors(site_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        
        return {
            "message": f"Error statistics reset for site '{site_name}'",
            "site_name": site_name,
            "reset_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset site errors: {str(e)}")

@router.get("/{site_name}/metrics")
@api_versioned(APIVersion.V1)
async def get_site_metrics(
    site_name: str,
    request: Request,
    response: Response,
    days: int = 7,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get site performance metrics
    
    Returns detailed performance metrics for the specified site
    over the given time period.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        metrics = await crawler.get_site_metrics(site_name, days=days)
        
        return {
            "site_name": site_name,
            "metrics": metrics,
            "period_days": days,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get site metrics: {str(e)}")

@router.websocket("/ws/{site_name}/logs")
async def stream_site_logs(websocket: WebSocket, site_name: str):
    """
    WebSocket endpoint for streaming site logs
    
    Provides real-time log streaming for the specified site.
    """
    await websocket.accept()
    
    class WebSocketLogHandler(logging.Handler):
        def emit(self, record):
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "site": site_name,
                        "level": record.levelname,
                        "message": record.getMessage(),
                        "version": "v1"
                    }
                    import asyncio
                    asyncio.create_task(websocket.send_json(log_entry))
            except Exception:
                pass
    
    # Add websocket handler to the logger
    logger = logging.getLogger(f"site.{site_name}")
    handler = WebSocketLogHandler()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        logger.removeHandler(handler) 