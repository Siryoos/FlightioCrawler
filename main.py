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
from api.dependencies import initialize_dependencies, shutdown_dependencies

# Import versioning utilities
from api_versioning import (
    APIVersion, APIVersionExtractor, ContentNegotiator, add_api_version_headers
)

# Import v1 routers
from api.v1 import (
    flights_router, monitoring_router, sites_router, 
    rate_limits_router, system_router, websocket_router
)
from api.v1.health import router as health_router

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
    
    initialize_dependencies(crawler=app.state.crawler, monitor=app.state.monitor, rate_limit_manager=get_rate_limit_manager(), http_session=app.state.http_session)
    # Start background tasks
    asyncio.create_task(app.state.monitor.log_memory_usage_periodically(interval_seconds=60))
    
    logger.info("Application startup complete. Crawler and HTTP session initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Application shutting down...")
    await shutdown_dependencies()
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
app.include_router(websocket_router)
app.include_router(health_router)


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
