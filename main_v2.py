import logging
import logging.config
import json
import asyncio
import os
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Header, Query, Depends, Security, Request, Response
from starlette.websockets import WebSocketDisconnect, WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from config import config
from main_crawler import IranianFlightCrawler
from monitoring import CrawlerMonitor
from intelligent_search import SearchOptimization
from price_monitor import PriceMonitor, WebSocketManager, PriceAlert
from ml_predictor import FlightPricePredictor
from multilingual_processor import MultilingualProcessor
from provider_insights import get_provider_insights
from rate_limiter import RateLimitMiddleware, RateLimitManager, get_rate_limit_manager
import aiohttp
from fastapi.security import APIKeyHeader

# Import versioning utilities
from api_versioning import (
    APIVersion, APIVersionExtractor, ContentNegotiator, DeprecationWarning, 
    DeprecationLevel, add_api_version_headers, create_alias_endpoint
)

# Import v1 routers
from api.v1 import (
    flights_router, monitoring_router, sites_router, 
    rate_limits_router, system_router
)

# Configure logging
if os.path.exists("config/logging_config.json"):
    with open("config/logging_config.json", "rt") as f:
        config_data = json.load(f)
    logging.config.dictConfig(config_data)
else:
    debug_mode = os.getenv("DEBUG_MODE", "0").lower() in ("1", "true", "yes")
    log_level = (
        logging.DEBUG
        if debug_mode
        else getattr(logging, config.MONITORING.LOG_LEVEL.upper(), logging.INFO)
    )
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

logger = logging.getLogger(__name__)

# Create FastAPI app with versioning
app = FastAPI(
    title="Iranian Flight Crawler API",
    description="Versioned API for crawling Iranian flight websites with backward compatibility",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "flights-v1",
            "description": "Flight search and management operations (v1)"
        },
        {
            "name": "monitoring-v1", 
            "description": "Price monitoring and alerts (v1)"
        },
        {
            "name": "sites-v1",
            "description": "Site management and testing (v1)"
        },
        {
            "name": "rate-limits-v1",
            "description": "Rate limiting management (v1)"
        },
        {
            "name": "system-v1",
            "description": "System health and information (v1)"
        },
        {
            "name": "legacy",
            "description": "Legacy endpoints (deprecated)"
        }
    ]
)

# For simplicity, API_KEY is stored here. In production, use environment variables.
API_KEY = os.getenv("ADMIN_API_KEY", "your-secret-api-key")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    """Dependency to validate the API key."""
    if api_key == API_KEY:
        return api_key
    else:
        raise HTTPException(
            status_code=403, detail="Could not validate credentials"
        )

@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    # Create a single aiohttp.ClientSession for the application
    app.state.http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60)
    )
    # Create crawler instance and pass the session
    app.state.crawler = IranianFlightCrawler(http_session=app.state.http_session)
    app.state.monitor = CrawlerMonitor()
    
    # Start background tasks
    asyncio.create_task(app.state.monitor.log_memory_usage_periodically(interval_seconds=60))
    
    logger.info("Application startup complete. Crawler and HTTP session initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Application shutting down...")
    # Gracefully close the crawler's active tasks
    if hasattr(app.state, 'crawler') and app.state.crawler:
        await app.state.crawler.shutdown()
    # Close the shared aiohttp session
    if hasattr(app.state, 'http_session') and not app.state.http_session.closed:
        await app.state.http_session.close()
    logger.info("Shutdown complete.")

# Add rate limiting middleware
rate_limit_middleware = RateLimitMiddleware(
    app=app, enable_ip_whitelist=True, enable_user_type_limits=True
)
app.add_middleware(RateLimitMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add versioning middleware
@app.middleware("http")
async def versioning_middleware(request: Request, call_next):
    """Middleware to handle API versioning and content negotiation"""
    
    # Extract API version
    api_version = APIVersionExtractor.extract_version(request)
    
    # Add version info to request state
    request.state.api_version = api_version
    
    # Get preferred content type
    content_type = ContentNegotiator.get_preferred_content_type(request)
    request.state.preferred_content_type = content_type
    
    # Process request
    response = await call_next(request)
    
    # Add version headers to response
    add_api_version_headers(response, api_version)
    
    return response

# Mount UI static files
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

# Include v1 API routers
app.include_router(flights_router)
app.include_router(monitoring_router)
app.include_router(sites_router)
app.include_router(rate_limits_router)
app.include_router(system_router)

# Legacy request models (for backward compatibility)
class SearchRequest(BaseModel):
    origin: str
    destination: str
    date: str
    passengers: int = 1
    seat_class: str = "economy"

class SearchResponse(BaseModel):
    flights: List[Dict]
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    metrics: Dict
    error_stats: Dict
    rate_limit_stats: Dict
    timestamp: str

# Dependency functions
async def get_crawler() -> IranianFlightCrawler:
    if not hasattr(app.state, 'crawler') or not app.state.crawler:
        raise HTTPException(status_code=503, detail="Crawler is not available")
    return app.state.crawler

async def get_monitor() -> CrawlerMonitor:
    if not hasattr(app.state, 'monitor') or not app.state.monitor:
        raise HTTPException(status_code=503, detail="Monitor is not available")
    return app.state.monitor

# Root endpoint with version detection
@app.get("/")
async def root(request: Request, response: Response):
    """Root endpoint with API version information"""
    api_version = getattr(request.state, 'api_version', APIVersion.V1)
    add_api_version_headers(response, api_version)
    
    return {
        "message": "Iranian Flight Crawler API",
        "version": api_version.value,
        "available_versions": [v.value for v in APIVersion.get_supported_versions()],
        "documentation": "/docs",
        "openapi": "/openapi.json"
    }

# ====================
# BACKWARD COMPATIBILITY ENDPOINTS
# ====================

# Create deprecation warnings for legacy endpoints
legacy_deprecation = DeprecationWarning(
    version=APIVersion.V1,
    level=DeprecationLevel.WARNING,
    message="This endpoint is deprecated. Please use the versioned API endpoints (/api/v1/...)",
    sunset_date=datetime(2025, 12, 31)
)

@app.post("/search", response_model=SearchResponse, tags=["legacy"])
async def legacy_search_flights(
    request: SearchRequest, 
    http_request: Request,
    response: Response,
    accept_language: str = Header("en"), 
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Legacy flight search endpoint (DEPRECATED)
    
    This endpoint is deprecated. Please use /api/v1/flights/search instead.
    """
    # Add deprecation headers
    for key, value in legacy_deprecation.to_header_dict().items():
        response.headers[key] = value
    
    # Log deprecation usage
    logger.warning(f"Legacy endpoint /search accessed from {http_request.client.host}")
    
    try:
        # Use the new v1 endpoint logic
        flights = await crawler.crawl_all_sites(
            {
                "origin": request.origin,
                "destination": request.destination,
                "date": request.date,
                "passengers": request.passengers,
                "seat_class": request.seat_class,
            }
        )
        
        return SearchResponse(
            flights=flights,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/health", response_model=HealthResponse, tags=["legacy"])
async def legacy_health_check(
    http_request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Legacy health check endpoint (DEPRECATED)
    
    This endpoint is deprecated. Please use /api/v1/system/health instead.
    """
    # Add deprecation headers
    for key, value in legacy_deprecation.to_header_dict().items():
        response.headers[key] = value
    
    logger.warning(f"Legacy endpoint /health accessed from {http_request.client.host}")
    
    try:
        health_info = await crawler.get_health_status()
        
        return HealthResponse(
            status=health_info.get("status", "unknown"),
            metrics=health_info.get("metrics", {}),
            error_stats=health_info.get("error_stats", {}),
            rate_limit_stats=health_info.get("rate_limit_stats", {}),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        return HealthResponse(
            status="degraded",
            metrics={},
            error_stats={"health_check_error": str(e)},
            rate_limit_stats={},
            timestamp=datetime.now().isoformat()
        )

@app.get("/metrics", tags=["legacy"])
async def legacy_get_metrics(
    http_request: Request,
    response: Response,
    monitor: CrawlerMonitor = Depends(get_monitor)
):
    """
    Legacy metrics endpoint (DEPRECATED)
    
    This endpoint is deprecated. Please use /api/v1/system/metrics instead.
    """
    # Add deprecation headers
    for key, value in legacy_deprecation.to_header_dict().items():
        response.headers[key] = value
    
    logger.warning(f"Legacy endpoint /metrics accessed from {http_request.client.host}")
    
    try:
        metrics = await monitor.get_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

# Create redirect endpoints for other legacy endpoints
legacy_redirects = [
    ("/stats", "/api/v1/system/stats"),
    ("/reset", "/api/v1/system/reset"), 
    ("/flights/recent", "/api/v1/flights/recent"),
    ("/airports", "/api/v1/system/airports"),
    ("/routes", "/api/v1/flights/routes"),
    ("/crawl", "/api/v1/flights/crawl"),
    ("/predict", "/api/v1/flights/predict"),
    ("/alerts", "/api/v1/monitoring/alerts"),
    ("/monitor/start", "/api/v1/monitoring/start"),
    ("/monitor/stop", "/api/v1/monitoring/stop"),
    ("/monitor/status", "/api/v1/monitoring/status"),
]

for old_path, new_path in legacy_redirects:
    @app.get(old_path, tags=["legacy"])
    @app.post(old_path, tags=["legacy"])
    @app.put(old_path, tags=["legacy"])
    @app.delete(old_path, tags=["legacy"])
    async def legacy_redirect_endpoint(
        http_request: Request, 
        response: Response,
        old_path=old_path, 
        new_path=new_path
    ):
        """Legacy endpoint redirect (DEPRECATED)"""
        # Add deprecation headers
        for key, value in legacy_deprecation.to_header_dict().items():
            response.headers[key] = value
        
        logger.warning(f"Legacy endpoint {old_path} accessed, redirecting to {new_path}")
        
        response.status_code = 301
        response.headers["Location"] = new_path
        return {
            "message": f"This endpoint has moved to {new_path}",
            "deprecated": True,
            "new_endpoint": new_path
        }

# Special handling for WebSocket endpoints (cannot be easily redirected)
@app.websocket("/ws/prices/{user_id}")
async def legacy_websocket_prices(websocket: WebSocket, user_id: str):
    """Legacy WebSocket endpoint with deprecation warning"""
    await websocket.accept()
    
    # Send deprecation warning
    await websocket.send_json({
        "type": "deprecation_warning",
        "message": "This WebSocket endpoint is deprecated. Please use /api/v1/monitoring/ws/prices/{user_id}",
        "new_endpoint": f"/api/v1/monitoring/ws/prices/{user_id}",
        "sunset_date": "2025-12-31"
    })
    
    # Forward to new endpoint logic (simplified)
    try:
        websocket_manager = WebSocketManager()
        await websocket_manager.connect(websocket, user_id)
        
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await websocket_manager.disconnect(websocket, user_id)
    except Exception as e:
        await websocket.close(code=1011, reason=f"Internal error: {str(e)}")

# API documentation endpoint
@app.get("/api/v1/docs", tags=["system-v1"])
async def get_api_documentation(request: Request, response: Response):
    """
    Get API documentation and migration guide
    
    Returns comprehensive API documentation including migration information.
    """
    add_api_version_headers(response, APIVersion.V1)
    
    return {
        "api_version": "v1",
        "documentation": {
            "openapi_url": "/openapi.json",
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        },
        "migration_guide": {
            "legacy_to_v1": {
                "/search": "/api/v1/flights/search",
                "/health": "/api/v1/system/health", 
                "/metrics": "/api/v1/system/metrics",
                "/stats": "/api/v1/system/stats",
                "/airports": "/api/v1/system/airports",
                "/routes": "/api/v1/flights/routes",
                "/alerts": "/api/v1/monitoring/alerts"
            }
        },
        "deprecation_info": {
            "legacy_endpoints_sunset": "2025-12-31",
            "migration_deadline": "2025-06-30",
            "support_contact": "api-support@flightio.com"
        },
        "versioning_info": {
            "version_detection_methods": [
                "X-API-Version header",
                "Accept header (application/vnd.flightio.v1+json)",
                "Query parameter (?version=v1)",
                "URL path (/api/v1/...)"
            ],
            "supported_versions": [v.value for v in APIVersion.get_supported_versions()],
            "latest_version": APIVersion.get_latest().value
        },
        "timestamp": datetime.now().isoformat(),
        "version": "v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 