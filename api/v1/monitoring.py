"""
API v1 - Monitoring Router

Contains monitoring-related endpoints for v1 API including price alerts and route monitoring
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, Request, Response
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from pydantic import BaseModel

from main_crawler import IranianFlightCrawler
from price_monitor import PriceMonitor, WebSocketManager, PriceAlert
from provider_insights import get_provider_insights
from api_versioning import APIVersion, api_versioned, add_api_version_headers

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring-v1"])

# Request/Response Models
class PriceAlertRequest(BaseModel):
    """Price alert request model"""
    user_id: str
    route: str
    target_price: float
    alert_type: str = "below"
    notification_methods: List[str] = ["websocket"]

class MonitorRequest(BaseModel):
    """Monitor request model"""
    routes: List[str]
    interval_minutes: int = 5

class StopMonitorRequest(BaseModel):
    """Stop monitor request model"""
    routes: Optional[List[str]] = None

# Dependency functions
async def get_crawler() -> IranianFlightCrawler:
    """Get crawler instance"""
    from main import app
    if not hasattr(app.state, 'crawler') or not app.state.crawler:
        raise HTTPException(status_code=503, detail="Crawler is not available")
    return app.state.crawler

@router.post("/alerts")
@api_versioned(APIVersion.V1)
async def add_price_alert(
    alert_data: PriceAlertRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Create a new price alert
    
    Creates a price alert that will notify when flight prices
    meet the specified criteria.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        alert_id = await crawler.add_price_alert(
            user_id=alert_data.user_id,
            route=alert_data.route,
            target_price=alert_data.target_price,
            alert_type=alert_data.alert_type,
            notification_methods=alert_data.notification_methods
        )
        
        return {
            "alert_id": alert_id,
            "user_id": alert_data.user_id,
            "route": alert_data.route,
            "target_price": alert_data.target_price,
            "alert_type": alert_data.alert_type,
            "notification_methods": alert_data.notification_methods,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create price alert: {str(e)}")

@router.get("/alerts")
@api_versioned(APIVersion.V1)
async def list_price_alerts(
    request: Request,
    response: Response,
    user_id: Optional[str] = None,
    route: Optional[str] = None,
    status: Optional[str] = None,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    List price alerts
    
    Returns list of price alerts with optional filtering by user, route, or status.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        alerts = await crawler.get_price_alerts(
            user_id=user_id,
            route=route,
            status=status
        )
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "filters": {
                "user_id": user_id,
                "route": route,
                "status": status
            },
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list price alerts: {str(e)}")

@router.delete("/alerts/{alert_id}")
@api_versioned(APIVersion.V1)
async def delete_price_alert(
    alert_id: str,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Delete a price alert
    
    Removes a price alert from the monitoring system.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await crawler.delete_price_alert(alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Price alert not found")
        
        return {
            "message": "Price alert deleted successfully",
            "alert_id": alert_id,
            "deleted_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete price alert: {str(e)}")

@router.post("/start")
@api_versioned(APIVersion.V1)
async def start_monitoring(
    monitor_request: MonitorRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Start monitoring routes
    
    Begins active monitoring of specified routes at the given interval.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        monitoring_id = await crawler.start_monitoring(
            routes=monitor_request.routes,
            interval_minutes=monitor_request.interval_minutes
        )
        
        return {
            "monitoring_id": monitoring_id,
            "routes": monitor_request.routes,
            "interval_minutes": monitor_request.interval_minutes,
            "status": "started",
            "started_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@router.post("/stop")
@api_versioned(APIVersion.V1)
async def stop_monitoring(
    stop_request: StopMonitorRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Stop monitoring routes
    
    Stops active monitoring for specified routes or all routes if none specified.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        stopped_routes = await crawler.stop_monitoring(routes=stop_request.routes)
        
        return {
            "message": "Monitoring stopped successfully",
            "stopped_routes": stopped_routes,
            "stopped_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")

@router.get("/status")
@api_versioned(APIVersion.V1)
async def get_monitoring_status(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get monitoring status
    
    Returns current status of all active monitoring tasks.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        status = await crawler.get_monitoring_status()
        
        return {
            "monitoring_status": status,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring status: {str(e)}")

@router.get("/insights")
@api_versioned(APIVersion.V1)
async def get_provider_insights_endpoint(
    request: Request,
    response: Response,
    provider_type: Optional[str] = None
):
    """
    Get provider insights
    
    Returns insights and analytics about flight providers.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        insights = await get_provider_insights(provider_type=provider_type)
        
        return {
            "insights": insights,
            "provider_type": provider_type,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider insights: {str(e)}")

@router.websocket("/ws/prices/{user_id}")
async def websocket_price_alerts(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time price alerts
    
    Provides real-time price alert notifications via WebSocket connection.
    """
    await websocket.accept()
    
    # Get WebSocket manager from the crawler
    try:
        from main import app
        if hasattr(app.state, 'crawler') and app.state.crawler:
            websocket_manager = WebSocketManager()
            await websocket_manager.connect(websocket, user_id)
            
            try:
                while websocket.client_state == WebSocketState.CONNECTED:
                    # Keep connection alive
                    await websocket.receive_text()
                    
            except WebSocketDisconnect:
                pass
            finally:
                await websocket_manager.disconnect(websocket, user_id)
        else:
            await websocket.close(code=1003, reason="Service unavailable")
            
    except Exception as e:
        await websocket.close(code=1011, reason=f"Internal error: {str(e)}")

@router.websocket("/ws/dashboard")
async def websocket_dashboard_updates(websocket: WebSocket):
    """
    WebSocket endpoint for dashboard updates
    
    Provides real-time dashboard updates including metrics and system status.
    """
    await websocket.accept()
    
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            # Send periodic dashboard updates
            from main import app
            if hasattr(app.state, 'crawler') and app.state.crawler:
                crawler = app.state.crawler
                
                # Get dashboard data
                dashboard_data = {
                    "timestamp": datetime.now().isoformat(),
                    "stats": await crawler.get_statistics(),
                    "monitoring_status": await crawler.get_monitoring_status(),
                    "recent_flights": await crawler.get_recent_flights(limit=10),
                    "version": "v1"
                }
                
                await websocket.send_json(dashboard_data)
            
            # Wait before next update
            import asyncio
            await asyncio.sleep(30)  # Update every 30 seconds
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=f"Internal error: {str(e)}") 