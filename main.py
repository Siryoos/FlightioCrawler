import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from config import config
from main_crawler import IranianFlightCrawler
from monitoring import CrawlerMonitor
from intelligent_search import SearchOptimization
from price_monitor import PriceMonitor, WebSocketManager
from ml_predictor import FlightPricePredictor
from multilingual_processor import MultilingualProcessor

# Configure logging
logging.basicConfig(
    level=config.LOG_LEVEL,
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
            request.origin,
            request.destination,
            request.date
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
            "metrics": health["metrics"],
            "error_stats": health["error_stats"],
            "rate_limit_stats": health["rate_limit_stats"],
            "timestamp": health["timestamp"]
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
        # Get all stats
        site_stats = crawler.get_all_site_stats()
        search_stats = crawler.get_search_stats()
        flight_stats = crawler.get_flight_stats()
        
        return {
            "site_stats": site_stats,
            "search_stats": search_stats,
            "flight_stats": flight_stats,
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

@app.websocket("/ws/prices/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await crawler.price_monitor.websocket_manager.connect(websocket, user_id)

@app.post("/predict")
async def predict_prices(route: str, dates: List[str]):
    return await crawler.ml_predictor.predict_future_prices(route, dates)

@app.post("/search/intelligent")
async def intelligent_search(request: SearchRequest, optimization: SearchOptimization):
    return await crawler.intelligent_search_flights(request.dict(), optimization)

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