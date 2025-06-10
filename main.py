import logging
import asyncio
import os
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Header, Query
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

# Configure logging
debug_mode = os.getenv("DEBUG_MODE", "0").lower() in ("1", "true", "yes")
log_level = logging.DEBUG if debug_mode else getattr(
    logging, config.MONITORING.LOG_LEVEL.upper(), logging.INFO
)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Iranian Flight Crawler",
    description="API for crawling Iranian flight websites",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount UI static files
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")

# Create crawler instance
crawler = IranianFlightCrawler()

# Create monitor instance
monitor = CrawlerMonitor()

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

class CrawlRequest(BaseModel):
    origin: str
    destination: str
    dates: List[str]
    passengers: int = 1
    seat_class: str = "economy"

# API endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Iranian Flight Crawler API"}

@app.post("/search", response_model=SearchResponse)
async def search_flights(request: SearchRequest, accept_language: str = Header("en")):
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
            flights = await crawler.multilingual.translate_flight_data(flights, accept_language)
        
        return {
            "flights": flights,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching flights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Get health status
        health = crawler.get_health_status()
        
        return {
            "status": "healthy",
            "metrics": health.get("crawler_metrics", {}),
            "error_stats": health.get("error_stats", {}),
            "rate_limit_stats": health.get("rate_limits", {}),
            "timestamp": health.get("timestamp", datetime.now().isoformat())
        }
        
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Get metrics endpoint"""
    try:
        # Get all metrics
        metrics = monitor.get_all_metrics()
        
        return {
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get stats endpoint"""
    try:
        # Use available stats methods
        flight_stats = crawler.data_manager.get_flight_stats()
        health = crawler.get_health_status()
        return {
            "flight_stats": flight_stats,
            "health": health,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset")
async def reset_stats():
    """Reset stats endpoint"""
    try:
        # Reset all stats
        crawler.reset_stats()
        
        return {
            "message": "Stats reset successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/flights/recent")
async def recent_flights(limit: int = 100):
    """Return recently crawled flights"""
    try:
        flights = crawler.data_manager.get_recent_flights(limit)
        return {"flights": flights, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error retrieving recent flights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts")
async def add_price_alert(alert: PriceAlertRequest):
    alert_id = await crawler.price_monitor.add_price_alert(PriceAlert(**alert.dict()))
    return {"alert_id": alert_id}

@app.delete("/alerts/{alert_id}")
async def delete_price_alert(alert_id: str):
    removed = await crawler.price_monitor.remove_price_alert(alert_id)
    return {"removed": removed}

@app.get("/alerts")
async def list_price_alerts():
    alerts = await crawler.price_monitor.get_active_alerts()
    return {"alerts": alerts}

@app.post("/monitor/start")
async def start_monitoring(req: MonitorRequest):
    await crawler.price_monitor.start_monitoring(req.routes, req.interval_minutes)
    routes = await crawler.price_monitor.get_monitored_routes()
    return {"monitoring": routes}

@app.post("/monitor/stop")
async def stop_monitoring(req: StopMonitorRequest):
    await crawler.price_monitor.stop_monitoring(req.routes)
    routes = await crawler.price_monitor.get_monitored_routes()
    return {"monitoring": routes}

@app.get("/monitor/status")
async def monitor_status():
    routes = await crawler.price_monitor.get_monitored_routes()
    return {"monitoring": routes}


@app.post("/crawl")
async def manual_crawl(req: CrawlRequest):
    """Manually crawl selected routes and dates"""
    results = {}
    for d in req.dates:
        flights = await crawler.crawl_all_sites({
            "origin": req.origin,
            "destination": req.destination,
            "departure_date": d,
            "passengers": req.passengers,
            "seat_class": req.seat_class,
        })
        results[d] = flights
    return {"results": results, "timestamp": datetime.now().isoformat()}

@app.get("/trend/{route}")
async def price_trend(route: str, days: int = 30):
    return await crawler.price_monitor.generate_price_trend_chart(route, days)

@app.websocket("/ws/prices/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await crawler.price_monitor.websocket_manager.connect(websocket, user_id)

@app.post("/predict")
async def predict_prices(route: str, dates: List[str]):
    return await crawler.ml_predictor.predict_future_prices(route, dates)

@app.post("/search/intelligent")
async def intelligent_search(
    origin: str = Query(...),
    destination: str = Query(...),
    date: str = Query(...),
    enable_multi_route: bool = Query(True),
    enable_date_range: bool = Query(True),
    date_range_days: int = Query(3)
):
    """Intelligent search endpoint"""
    try:
        search_params = {
            "origin": origin,
            "destination": destination,
            "departure_date": date,
        }
        optimization = SearchOptimization(
            enable_multi_route=enable_multi_route,
            enable_date_range=enable_date_range,
            date_range_days=date_range_days
        )
        results = await crawler.intelligent_search_flights(search_params, optimization)
        return {
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in intelligent search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sites/status")
async def get_all_sites_status():
    """Get detailed status for all configured sites"""
    sites_status = {}
    for site_name, crawler_instance in crawler.crawlers.items():
        sites_status[site_name] = {
            "domain": site_name,
            "base_url": getattr(crawler_instance, 'base_url', ''),
            "enabled": site_name in crawler.enabled_sites,
            "is_active": await crawler.error_handler.can_make_request(site_name),
            "circuit_breaker_state": crawler.error_handler.get_circuit_state(site_name),
            "rate_limit_status": {
                "can_request": not crawler.rate_limiter.is_rate_limited(site_name),
                "requests_remaining": crawler.rate_limiter.get_remaining_requests(site_name),
                "reset_time": crawler.rate_limiter.get_reset_time(site_name)
            },
            "last_error": crawler.error_handler.get_last_error(site_name),
            "last_successful_crawl": monitor.get_last_success(site_name),
            "total_requests_today": monitor.get_request_count(site_name),
            "success_rate_24h": monitor.get_success_rate(site_name),
            "avg_response_time": monitor.get_avg_response_time(site_name)
        }
    return {"sites": sites_status, "timestamp": datetime.now().isoformat()}


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
async def test_individual_site(site_name: str, search_request: SearchRequest):
    """Test a specific site crawler with given parameters"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    start_time = datetime.now()
    try:
        site_crawler = crawler.crawlers[site_name]
        results = await site_crawler.search_flights({
            "origin": search_request.origin,
            "destination": search_request.destination,
            "departure_date": search_request.date,
            "passengers": search_request.passengers,
            "seat_class": search_request.seat_class
        })
        execution_time = (datetime.now() - start_time).total_seconds()
        return {
            "site": site_name,
            "success": True,
            "execution_time": execution_time,
            "results_count": len(results),
            "results": results[:5],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        return {
            "site": site_name,
            "success": False,
            "execution_time": execution_time,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/v1/sites/{site_name}/health")
async def check_site_health(site_name: str):
    """Comprehensive health check for individual site"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    site_crawler = crawler.crawlers[site_name]
    base_url = getattr(site_crawler, 'base_url', '')
    health_data = {"site": site_name, "base_url": base_url, "timestamp": datetime.now().isoformat()}
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            start_time = datetime.now()
            async with session.get(base_url, timeout=10) as response:
                response_time = (datetime.now() - start_time).total_seconds()
                health_data.update({
                    "url_accessible": True,
                    "http_status": response.status,
                    "response_time": response_time,
                    "content_length": len(await response.text())
                })
    except Exception as e:
        health_data.update({"url_accessible": False, "error": str(e), "response_time": None})
    health_data.update({
        "circuit_breaker_open": not await crawler.error_handler.can_make_request(site_name),
        "rate_limited": crawler.rate_limiter.is_rate_limited(site_name),
        "error_count_last_hour": monitor.get_error_count(site_name, hours=1),
        "success_count_last_hour": monitor.get_success_count(site_name, hours=1)
    })
    return health_data


@app.post("/api/v1/sites/{site_name}/reset")
async def reset_site_errors(site_name: str):
    """Reset error state and circuit breaker for a site"""
    if site_name not in crawler.crawlers:
        raise HTTPException(status_code=404, detail=f"Site {site_name} not found")
    await crawler.error_handler.reset_circuit_breaker(site_name)
    await monitor.reset_metrics_async(site_name)
    return {"site": site_name, "reset": True, "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/sites/{site_name}/enable")
async def enable_site_api(site_name: str):
    """Enable crawling for a site"""
    if crawler.enable_site(site_name):
        return {"site": site_name, "enabled": True}
    raise HTTPException(status_code=404, detail=f"Site {site_name} not found")


@app.post("/api/v1/sites/{site_name}/disable")
async def disable_site_api(site_name: str):
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
                    "module": record.module
                }
                try:
                    asyncio.create_task(websocket.send_json(log_entry))
                except Exception:
                    pass
    handler = WebSocketLogHandler()
    logger.addHandler(handler)
    try:
        while True:
            await asyncio.sleep(1)
    except Exception:
        logger.removeHandler(handler)
        await websocket.close()


@app.websocket("/ws/dashboard")
async def dashboard_updates(websocket: WebSocket):
    """Real-time dashboard updates for all sites"""
    await websocket.accept()
    try:
        while True:
            dashboard_data = {
                "timestamp": datetime.now().isoformat(),
                "sites": {},
                "system_metrics": {
                    "total_active_crawlers": len([s for s in crawler.crawlers if await crawler.error_handler.can_make_request(s)]),
                    "total_errors_last_hour": sum(monitor.get_error_count(s, hours=1) for s in crawler.crawlers),
                    "avg_system_response_time": monitor.get_system_avg_response_time()
                }
            }
            for site_name in crawler.crawlers:
                dashboard_data["sites"][site_name] = {
                    "enabled": site_name in crawler.enabled_sites,
                    "active": await crawler.error_handler.can_make_request(site_name),
                    "rate_limited": crawler.rate_limiter.is_rate_limited(site_name),
                    "last_error": crawler.error_handler.get_last_error(site_name),
                    "requests_per_minute": monitor.get_rpm(site_name)
                }
            await websocket.send_json(dashboard_data)
            await asyncio.sleep(5)
    except Exception:
        await websocket.close()

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
