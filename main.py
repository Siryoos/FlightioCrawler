import logging
import asyncio
import os
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Header, Query, Depends, Security
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

# Configure logging
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

# Create FastAPI app
app = FastAPI(
    title="Iranian Flight Crawler",
    description="API for crawling Iranian flight websites",
    version="1.0.0",
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
app.add_middleware(RateLimitMiddleware, enable_ip_whitelist=True, enable_user_type_limits=True)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount UI static files
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

# Dependency to get the crawler instance
async def get_crawler() -> IranianFlightCrawler:
    if not hasattr(app.state, 'crawler') or not app.state.crawler:
        raise HTTPException(status_code=503, detail="Crawler is not available")
    return app.state.crawler

async def get_monitor() -> CrawlerMonitor:
    if not hasattr(app.state, 'monitor') or not app.state.monitor:
        raise HTTPException(status_code=503, detail="Monitor is not available")
    return app.state.monitor

# Request models
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


class PriceAlertRequest(BaseModel):
    user_id: str
    route: str
    target_price: float
    alert_type: str = "below"
    notification_methods: List[str] = ["websocket"]


class MonitorRequest(BaseModel):
    routes: List[str]
    interval_minutes: int = 5


class StopMonitorRequest(BaseModel):
    routes: Optional[List[str]] = None


class RouteRequest(BaseModel):
    origin: str
    destination: str


class CrawlRequest(BaseModel):
    origin: str
    destination: str
    dates: List[str]
    passengers: int = 1
    seat_class: str = "economy"


class RateLimitConfigRequest(BaseModel):
    endpoint_type: str
    requests_per_minute: int
    requests_per_hour: int
    burst_limit: int


class WhitelistRequest(BaseModel):
    ip: str
    duration_seconds: int = 3600


class RateLimitResetRequest(BaseModel):
    client_ip: str
    endpoint_type: Optional[str] = None


class CacheClearRequest(BaseModel):
    pattern: str = Query("*", description="The key pattern to clear (e.g., 'airports:*'). Defaults to all keys.")


# API endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Iranian Flight Crawler API"}


@app.post("/search", response_model=SearchResponse)
async def search_flights(request: SearchRequest, accept_language: str = Header("en"), crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Search flights endpoint"""
    try:
        # Search flights
        flights = await crawler.crawl_all_sites(
            {
                "origin": request.origin,
                "destination": request.destination,
                "departure_date": request.date,
                "passengers": request.passengers,
                "seat_class": request.seat_class,
            }
        )

        if accept_language != "en":
            flights = await crawler.multilingual.translate_flight_data(
                flights, accept_language
            )

        return {"flights": flights, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error searching flights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check(crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Health check endpoint"""
    try:
        # Get health status
        health = crawler.get_health_status()

        return {
            "status": "healthy",
            "metrics": health.get("crawler_metrics", {}),
            "error_stats": health.get("error_stats", {}),
            "rate_limit_stats": health.get("rate_limits", {}),
            "timestamp": health.get("timestamp", datetime.now().isoformat()),
        }

    except Exception as e:
        logger.error(f"Error checking health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics(monitor: CrawlerMonitor = Depends(get_monitor)):
    """Get metrics endpoint"""
    try:
        # Get all metrics
        metrics = monitor.get_all_metrics()

        return {"metrics": metrics, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats(crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Get stats endpoint"""
    try:
        # Use available stats methods
        flight_stats = crawler.data_manager.get_flight_stats()
        health = crawler.get_health_status()
        return {
            "flight_stats": flight_stats,
            "health": health,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset")
async def reset_stats(crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Reset stats endpoint"""
    try:
        # Reset all stats
        crawler.reset_stats()

        return {
            "message": "Stats reset successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error resetting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/flights/recent")
async def recent_flights(limit: int = 100, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Return recently crawled flights"""
    try:
        flights = crawler.data_manager.get_recent_flights(limit)
        return {"flights": flights, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error retrieving recent flights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerts")
async def add_price_alert(alert: PriceAlertRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    alert_id = await crawler.price_monitor.add_price_alert(PriceAlert(**alert.dict()))
    return {"message": "Alert added successfully", "alert_id": alert_id}


@app.delete("/alerts/{alert_id}")
async def delete_price_alert(alert_id: str, crawler: IranianFlightCrawler = Depends(get_crawler)):
    success = await crawler.price_monitor.delete_price_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted successfully"}


@app.get("/alerts")
async def list_price_alerts(crawler: IranianFlightCrawler = Depends(get_crawler)):
    alerts = await crawler.price_monitor.get_all_alerts()
    return {"alerts": alerts}


@app.post("/monitor/start")
async def start_monitoring(req: MonitorRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    await crawler.price_monitor.start_monitoring(req.routes, req.interval_minutes)
    return {"message": "Monitoring started"}


@app.post("/monitor/stop")
async def stop_monitoring(req: StopMonitorRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    await crawler.price_monitor.stop_monitoring(req.routes)
    return {"message": "Monitoring stopped"}


@app.get("/monitor/status")
async def monitor_status(crawler: IranianFlightCrawler = Depends(get_crawler)):
    status = crawler.price_monitor.get_monitoring_status()
    return {"status": status}


@app.post("/routes")
async def add_route(req: RouteRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    route_id = await crawler.data_manager.add_crawl_route(req.origin, req.destination)
    return {"message": "Route added successfully", "route_id": route_id}


@app.get("/routes")
async def list_routes(crawler: IranianFlightCrawler = Depends(get_crawler)):
    routes = await crawler.data_manager.get_active_routes()
    return {"routes": routes}


@app.get("/airports")
async def list_airports(q: str = "", country: str = "", limit: int = 1000, crawler: IranianFlightCrawler = Depends(get_crawler)):
    airports = await crawler.data_manager.get_airports(q, country, limit)
    return {"airports": airports}


@app.get("/airports/countries")
async def list_countries(crawler: IranianFlightCrawler = Depends(get_crawler)):
    countries = await crawler.data_manager.get_countries()
    return {"countries": countries}


@app.delete("/routes/{route_id}")
async def delete_route(route_id: int, crawler: IranianFlightCrawler = Depends(get_crawler)):
    success = await crawler.data_manager.delete_crawl_route(route_id)
    if not success:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"message": "Route deleted successfully"}


@app.post("/crawl")
async def manual_crawl(req: CrawlRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    all_flights = []
    for date in req.dates:
        flights = await crawler.crawl_all_sites({
            "origin": req.origin,
            "destination": req.destination,
            "departure_date": date,
            "passengers": req.passengers,
            "seat_class": req.seat_class,
        })
        all_flights.extend(flights)
    return {"flights": all_flights}


@app.get("/trend/{route}")
async def price_trend(route: str, days: int = 30, crawler: IranianFlightCrawler = Depends(get_crawler)):
    trend = await crawler.data_manager.get_historical_prices(route, days)
    return {"trend": trend}


@app.websocket("/ws/prices/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # This needs access to the PriceMonitor's WebSocketManager
    # which is part of the crawler. We can't use Depends in WebSockets.
    crawler: IranianFlightCrawler = app.state.crawler
    await crawler.price_monitor.websocket_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        crawler.price_monitor.websocket_manager.disconnect(user_id)


@app.post("/predict")
async def predict_prices(route: str, dates: List[str], crawler: IranianFlightCrawler = Depends(get_crawler)):
    predictions = await crawler.ml_predictor.predict_prices(route, dates)
    return {"predictions": predictions}


@app.post("/search/intelligent")
async def intelligent_search(
    crawler: IranianFlightCrawler = Depends(get_crawler),
    origin: str = Query(...),
    destination: str = Query(...),
    date: str = Query(...),
    enable_multi_route: bool = Query(True),
    enable_date_range: bool = Query(True),
    date_range_days: int = Query(3),
):
    """Intelligent search endpoint"""
    optimization = SearchOptimization(
        enable_multi_route=enable_multi_route,
        enable_date_range=enable_date_range,
        date_range_days=date_range_days,
    )
    results = await crawler.intelligent_search_flights({
        "origin": origin,
        "destination": destination,
        "departure_date": date,
    }, optimization)
    return results


@app.get("/api/v1/sites/status")
async def get_all_sites_status(crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Get status for all configured sites"""
    status_data = {}
    for site_name in crawler.get_available_adapters():
        try:
            adapter_info = crawler.get_adapter_info(site_name)
            error_stats = crawler.error_handler.get_stats(site_name)
            status_data[site_name] = {
                "enabled": crawler.is_site_enabled(site_name),
                "circuit_breaker_open": crawler.error_handler.is_circuit_open(site_name),
                "error_rate": error_stats.get("error_rate", 0),
                "success_rate": error_stats.get("success_rate", 1),
                "total_requests": error_stats.get("total_requests", 0),
                "last_error_time": error_stats.get("last_error_time"),
                "config": adapter_info
            }
        except Exception as e:
            status_data[site_name] = {"error": str(e)}
    return status_data


@app.get("/modules/{module_name}", response_class=PlainTextResponse)
async def get_module_source(module_name: str):
    """Return source code of key modules"""
    module_paths = {
        "main_crawler": "main_crawler.py",
        "site_crawlers": "site_crawlers.py",
        "monitoring": "monitoring/README.md",
        "data_manager": "data_manager.py",
        "intelligent_search": "intelligent_search.py",
        "price_monitor": "price_monitor.py",
        "flight_monitor": "flight_monitor.py",
        "ml_predictor": "ml_predictor.py",
        "multilingual_processor": "multilingual_processor.py",
    }
    path = module_paths.get(module_name)
    if not path:
        raise HTTPException(status_code=404, detail="Module not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading module {module_name}: {e}")
        raise HTTPException(status_code=500, detail="Could not read module")


@app.post("/api/v1/sites/{site_name}/test")
async def test_individual_site(site_name: str, search_request: SearchRequest, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Test a single site adapter with a given search request"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    start_time = datetime.now()
    try:
        site_crawler = crawler.crawlers[site_name]
        results = await site_crawler.search_flights(
            {
                "origin": search_request.origin,
                "destination": search_request.destination,
                "departure_date": search_request.date,
                "passengers": search_request.passengers,
                "seat_class": search_request.seat_class,
            }
        )
        execution_time = (datetime.now() - start_time).total_seconds()
        return {
            "site": site_name,
            "success": True,
            "execution_time": execution_time,
            "results_count": len(results),
            "results": results[:5],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        return {
            "site": site_name,
            "success": False,
            "execution_time": execution_time,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/api/v1/sites/{site_name}/health")
async def check_site_health(site_name: str, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Comprehensive health check for individual site"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    site_crawler = crawler.crawlers[site_name]
    base_url = getattr(site_crawler, "base_url", "")
    health_data = {
        "site": site_name,
        "base_url": base_url,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            async with session.get(base_url, timeout=10) as response:
                response_time = (datetime.now() - start_time).total_seconds()
                health_data.update(
                    {
                        "url_accessible": True,
                        "http_status": response.status,
                        "response_time": response_time,
                        "content_length": len(await response.text()),
                    }
                )
    except Exception as e:
        health_data.update(
            {"url_accessible": False, "error": str(e), "response_time": None}
        )
    health_data.update(
        {
            "circuit_breaker_open": not await crawler.error_handler.can_make_request(
                site_name
            ),
            "rate_limited": crawler.rate_limiter.is_rate_limited(site_name),
            "error_count_last_hour": monitor.get_error_count(site_name, hours=1),
            "success_count_last_hour": monitor.get_success_count(site_name, hours=1),
        }
    )
    return health_data


@app.post("/api/v1/sites/{site_name}/reset")
async def reset_site_errors(site_name: str, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Reset error state and circuit breaker for a site"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    await crawler.error_handler.reset_circuit_breaker(site_name)
    await monitor.reset_metrics_async(site_name)
    return {"site": site_name, "reset": True, "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/sites/{site_name}/enable")
async def enable_site_api(site_name: str, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Enable crawling for a site"""
    if crawler.enable_site(site_name):
        return {"site": site_name, "enabled": True}
    raise HTTPException(status_code=404, detail=f"Site {site_name} not found")


@app.post("/api/v1/sites/{site_name}/disable")
async def disable_site_api(site_name: str, crawler: IranianFlightCrawler = Depends(get_crawler)):
    """Disable crawling for a site"""
    if crawler.disable_site(site_name):
        return {"site": site_name, "enabled": False}
    raise HTTPException(status_code=404, detail=f"Site {site_name} not found")


@app.get("/api/v1/provider-insights")
async def provider_insights_api(provider_type: Optional[str] = None):
    """Return business intelligence metrics for providers"""
    data = get_provider_insights(provider_type)
    if provider_type and not data:
        raise HTTPException(status_code=404, detail="Provider type not found")
    return {"insights": data, "timestamp": datetime.now().isoformat()}


@app.websocket("/ws/sites/{site_name}/logs")
async def stream_site_logs(websocket: WebSocket, site_name: str):
    """Stream real-time logs for a specific site"""
    await websocket.accept()
    import logging

    class WebSocketLogHandler(logging.Handler):
        def emit(self, record):
            if site_name in record.getMessage():
                log_entry = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                }
                try:
                    asyncio.create_task(websocket.send_json(log_entry))
                except Exception:
                    pass

    handler = WebSocketLogHandler()
    logger.addHandler(handler)
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        logger.removeHandler(handler)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@app.websocket("/ws/dashboard")
async def dashboard_updates(websocket: WebSocket):
    """Real-time dashboard updates for all sites"""
    await websocket.accept()
    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            dashboard_data = {
                "timestamp": datetime.now().isoformat(),
                "sites": {},
                "system_metrics": {
                    "total_active_crawlers": len(
                        [
                            s
                            for s in crawler.crawlers
                            if await crawler.error_handler.can_make_request(s)
                        ]
                    ),
                    "total_errors_last_hour": sum(
                        monitor.get_error_count(s, hours=1) for s in crawler.crawlers
                    ),
                    "avg_system_response_time": monitor.get_system_avg_response_time(),
                },
            }
            for site_name in crawler.crawlers:
                dashboard_data["sites"][site_name] = {
                    "enabled": site_name in crawler.enabled_sites,
                    "active": await crawler.error_handler.can_make_request(site_name),
                    "rate_limited": crawler.rate_limiter.is_rate_limited(site_name),
                    "last_error": crawler.error_handler.get_last_error(site_name),
                    "requests_per_minute": monitor.get_rpm(site_name),
                }
            await websocket.send_json(dashboard_data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


# Rate Limiting Management Endpoints
@app.get("/api/v1/rate-limits/stats")
async def get_rate_limit_stats(
    endpoint_type: Optional[str] = Query(
        None, description="Specific endpoint type to get stats for"
    ),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """دریافت آمار rate limiting"""
    try:
        stats = await rate_limit_manager.get_rate_limit_stats(endpoint_type)
        return {"rate_limit_stats": stats, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rate-limits/config")
async def get_rate_limit_config():
    """دریافت تنظیمات rate limiting فعلی"""
    from rate_limiter import RATE_LIMIT_CONFIGS, USER_TYPE_LIMITS

    return {
        "endpoint_configs": RATE_LIMIT_CONFIGS,
        "user_type_multipliers": USER_TYPE_LIMITS,
        "timestamp": datetime.now().isoformat(),
    }


@app.put("/api/v1/rate-limits/config")
async def update_rate_limit_config(
    config_request: RateLimitConfigRequest,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """بروزرسانی تنظیمات rate limiting"""
    try:
        result = await rate_limit_manager.update_rate_limit_config(
            config_request.endpoint_type,
            {
                "requests_per_minute": config_request.requests_per_minute,
                "requests_per_hour": config_request.requests_per_hour,
                "burst_limit": config_request.burst_limit,
            },
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rate limit config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rate-limits/client/{client_ip}")
async def get_client_rate_limit_status(
    client_ip: str,
    endpoint_type: str = Query(..., description="Endpoint type to check"),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """دریافت وضعیت rate limiting برای کلاینت خاص"""
    try:
        status = await rate_limit_manager.get_client_rate_limit_status(
            client_ip, endpoint_type
        )

        if "error" in status:
            raise HTTPException(status_code=500, detail=status["error"])

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client rate limit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/rate-limits/reset")
async def reset_client_rate_limits(
    reset_request: RateLimitResetRequest,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """ریست کردن rate limits برای کلاینت خاص"""
    try:
        result = await rate_limit_manager.reset_client_rate_limits(
            reset_request.client_ip, reset_request.endpoint_type
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting client rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rate-limits/blocked")
async def get_blocked_clients(
    limit: int = Query(100, description="Maximum number of blocked clients to return"),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """دریافت لیست کلاینت‌های مسدود شده"""
    try:
        blocked = await rate_limit_manager.get_blocked_clients(limit)

        if "error" in blocked:
            raise HTTPException(status_code=500, detail=blocked["error"])

        return blocked

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting blocked clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/rate-limits/whitelist")
async def whitelist_ip(
    whitelist_request: WhitelistRequest,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """اضافه کردن IP به whitelist موقت"""
    try:
        result = await rate_limit_manager.whitelist_ip(
            whitelist_request.ip, whitelist_request.duration_seconds
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error whitelisting IP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rate-limits/whitelist/{ip}")
async def check_ip_whitelist_status(
    ip: str, rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager)
):
    """بررسی وضعیت whitelist برای IP خاص"""
    try:
        is_whitelisted = await rate_limit_manager.is_ip_whitelisted(ip)

        return {
            "ip": ip,
            "is_whitelisted": is_whitelisted,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking IP whitelist status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
async def clear_cache_endpoint(
    request: CacheClearRequest,
    crawler: IranianFlightCrawler = Depends(get_crawler),
    api_key: str = Depends(get_api_key)
):
    """
    Clear cache entries in Redis based on a pattern.
    Requires a valid API key.
    """
    deleted_count = await crawler.data_manager.clear_cache(request.pattern)
    return {
        "message": f"Cache clear command executed for pattern: '{request.pattern}'.",
        "keys_deleted": deleted_count
    }


# Run app
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        workers=config.API_WORKERS,
        reload=debug_mode,
    )
