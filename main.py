import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from config import config
from main_crawler import IranianFlightCrawler
from monitoring import CrawlerMonitor
from intelligent_search import SearchOptimization
from price_monitor import PriceMonitor, WebSocketManager, PriceAlert
from ml_predictor import FlightPricePredictor
from multilingual_processor import MultilingualProcessor

# Configure logging
logging.basicConfig(
    level=config.MONITORING.LOG_LEVEL,
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

# Run app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        workers=config.API_WORKERS,
        reload=True
    ) 