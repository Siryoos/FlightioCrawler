"""
API v1 - Flights Router

Contains all flight-related endpoints for v1 API
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, Response
from pydantic import BaseModel

from main_crawler import IranianFlightCrawler
from ml_predictor import FlightPricePredictor
from intelligent_search import SearchOptimization
from api_versioning import APIVersion, api_versioned, add_api_version_headers

router = APIRouter(prefix="/api/v1/flights", tags=["flights-v1"])

# Request/Response Models
class FlightSearchRequest(BaseModel):
    """Flight search request model"""
    origin: str
    destination: str
    date: str
    passengers: int = 1
    seat_class: str = "economy"

class FlightSearchResponse(BaseModel):
    """Flight search response model"""
    flights: List[Dict]
    timestamp: str
    version: str = "v1"
    search_metadata: Dict = {}

class RouteRequest(BaseModel):
    """Route request model"""
    origin: str
    destination: str

class CrawlRequest(BaseModel):
    """Manual crawl request model"""
    origin: str
    destination: str
    dates: List[str]
    passengers: int = 1
    seat_class: str = "economy"

class IntelligentSearchRequest(BaseModel):
    """Intelligent search request model"""
    origin: str
    destination: str
    date: str
    enable_multi_route: bool = True
    enable_date_range: bool = True
    date_range_days: int = 3
    passengers: int = 1
    seat_class: str = "economy"

# Import shared dependencies to eliminate circular imports
from api.dependencies import get_crawler
from adapters.unified_crawler_interface import UnifiedCrawlerInterface

@router.post("/search", response_model=FlightSearchResponse)
@api_versioned(APIVersion.V1)
async def search_flights(
    request_data: FlightSearchRequest, 
    request: Request,
    response: Response,
    accept_language: str = Header("en"),
    crawler: UnifiedCrawlerInterface = Depends(get_crawler)
):
    """
    Search for flights across all supported sites
    
    This endpoint searches for flights based on the provided criteria
    and returns results from all available airline sites.
    """
    try:
        # Add version headers
        add_api_version_headers(response, APIVersion.V1)
        
        # Create search parameters
        from adapters.unified_crawler_interface import SearchParameters
        search_params = SearchParameters(
            origin=request_data.origin,
            destination=request_data.destination,
            departure_date=request_data.date,
            passengers=request_data.passengers,
            seat_class=request_data.seat_class,
            language=accept_language
        )
        
        # Search flights using unified interface
        result = await crawler.crawl_async(search_params)
        
        # Convert to response format
        flights = [flight.to_dict() for flight in result.flights]
        
        # Format response
        return FlightSearchResponse(
            flights=flights,
            timestamp=datetime.now().isoformat(),
            search_metadata={
                "origin": request_data.origin,
                "destination": request_data.destination,
                "date": request_data.date,
                "passengers": request_data.passengers,
                "seat_class": request_data.seat_class,
                "results_count": len(flights),
                "execution_time": result.execution_time,
                "success": result.success
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/recent")
@api_versioned(APIVersion.V1)
async def get_recent_flights(
    request: Request,
    response: Response,
    limit: int = Query(100, ge=1, le=1000),
    crawler: UnifiedCrawlerInterface = Depends(get_crawler)
):
    """
    Get recently found flights
    
    Returns the most recently crawled flight data.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        # For unified interface, we need to implement a way to get recent flights
        # This might require extending the interface or using metadata
        recent_flights = []
        
        # For now, return empty list with a message
        return {
            "flights": recent_flights,
            "count": len(recent_flights),
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
            "version": "v1",
            "message": "Recent flights functionality being migrated to unified interface"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent flights: {str(e)}")

@router.post("/crawl")
@api_versioned(APIVersion.V1)
async def manual_crawl(
    request_data: CrawlRequest,
    request: Request,
    response: Response,
    crawler: UnifiedCrawlerInterface = Depends(get_crawler)
):
    """
    Manually trigger a crawl for specific routes and dates
    
    This endpoint allows manual triggering of crawling for specific
    origin-destination pairs and dates.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        from adapters.unified_crawler_interface import SearchParameters
        results = []
        
        for date in request_data.dates:
            search_params = SearchParameters(
                origin=request_data.origin,
                destination=request_data.destination,
                departure_date=date,
                passengers=request_data.passengers,
                seat_class=request_data.seat_class
            )
            
            # Crawl using unified interface
            result = await crawler.crawl_async(search_params)
            
            flights = [flight.to_dict() for flight in result.flights]
            results.append({
                "date": date,
                "flights": flights,
                "count": len(flights),
                "success": result.success,
                "execution_time": result.execution_time
            })
        
        return {
            "results": results,
            "total_flights": sum(r["count"] for r in results),
            "crawl_timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual crawl failed: {str(e)}")

@router.post("/search/intelligent")
@api_versioned(APIVersion.V1)
async def intelligent_search(
    request_data: IntelligentSearchRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Intelligent flight search with optimization
    
    This endpoint provides enhanced search capabilities including
    multi-route optimization and date range flexibility.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        search_optimizer = SearchOptimization(crawler)
        
        # Build search parameters
        search_params = {
            "origin": request_data.origin,
            "destination": request_data.destination,
            "date": request_data.date,
            "passengers": request_data.passengers,
            "seat_class": request_data.seat_class,
        }
        
        # Perform intelligent search
        optimized_results = await search_optimizer.optimize_search(
            search_params,
            enable_multi_route=request_data.enable_multi_route,
            enable_date_range=request_data.enable_date_range,
            date_range_days=request_data.date_range_days
        )
        
        return {
            "flights": optimized_results.get("flights", []),
            "optimization_info": optimized_results.get("optimization_info", {}),
            "alternatives": optimized_results.get("alternatives", []),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intelligent search failed: {str(e)}")

@router.get("/predict")
@api_versioned(APIVersion.V1)
async def predict_prices(
    request: Request,
    response: Response,
    route: str = Query(..., description="Route in format ORIGIN-DESTINATION"),
    dates: List[str] = Query(..., description="List of dates to predict prices for"),
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Predict flight prices for given route and dates
    
    Uses machine learning models to predict flight prices
    based on historical data.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        predictor = FlightPricePredictor()
        
        predictions = []
        for date in dates:
            try:
                prediction = await predictor.predict_price(route, date)
                predictions.append({
                    "date": date,
                    "predicted_price": prediction.get("price"),
                    "confidence": prediction.get("confidence"),
                    "price_range": prediction.get("price_range")
                })
            except Exception as e:
                predictions.append({
                    "date": date,
                    "error": str(e),
                    "predicted_price": None
                })
        
        return {
            "route": route,
            "predictions": predictions,
            "model_info": predictor.get_model_info(),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price prediction failed: {str(e)}")

@router.get("/trend/{route}")
@api_versioned(APIVersion.V1)
async def get_price_trend(
    route: str,
    request: Request,
    response: Response,
    days: int = Query(30, ge=1, le=365),
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Get price trend for a specific route
    
    Returns historical price trends for the specified route
    over the given time period.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        trend_data = await crawler.get_price_trend(route, days=days)
        
        return {
            "route": route,
            "trend_data": trend_data,
            "period_days": days,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get price trend: {str(e)}")

@router.post("/routes")
@api_versioned(APIVersion.V1)
async def add_route(
    request_data: RouteRequest,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Add a route for monitoring
    
    Adds a new origin-destination pair to the monitoring system.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        route_id = await crawler.add_route(request_data.origin, request_data.destination)
        
        return {
            "route_id": route_id,
            "origin": request_data.origin,
            "destination": request_data.destination,
            "added_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add route: {str(e)}")

@router.get("/routes")
@api_versioned(APIVersion.V1)
async def list_routes(
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    List all monitored routes
    
    Returns all routes currently being monitored by the system.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        routes = await crawler.get_routes()
        
        return {
            "routes": routes,
            "count": len(routes),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list routes: {str(e)}")

@router.delete("/routes/{route_id}")
@api_versioned(APIVersion.V1)
async def delete_route(
    route_id: int,
    request: Request,
    response: Response,
    crawler: IranianFlightCrawler = Depends(get_crawler)
):
    """
    Delete a monitored route
    
    Removes a route from the monitoring system.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await crawler.delete_route(route_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Route not found")
        
        return {
            "message": "Route deleted successfully",
            "route_id": route_id,
            "deleted_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete route: {str(e)}") 