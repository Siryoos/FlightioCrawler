import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn
import time

# Initialize FastAPI app
app = FastAPI(title="Iranian Flight Crawler API", version="1.0.0")

# Initialize crawler
crawler = IranianFlightCrawler()

class SearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    seat_class: Optional[str] = "economy"

class FlightResponse(BaseModel):
    flights: List[Dict]
    total_count: int
    search_time_ms: int

@app.post("/search", response_model=FlightResponse)
async def search_flights(request: SearchRequest, background_tasks: BackgroundTasks):
    """Search for flights across all Iranian booking sites"""
    start_time = time.time()
    
    try:
        # Check cache first
        search_key = f"{request.origin}_{request.destination}_{request.departure_date}"
        cached_results = crawler.data_manager.get_cached_search(search_key)
        
        if cached_results:
            return FlightResponse(
                flights=cached_results,
                total_count=len(cached_results),
                search_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Perform live search
        search_params = {
            'origin': request.origin,
            'destination': request.destination,
            'departure_date': request.departure_date,
            'passengers': request.passengers,
            'seat_class': request.seat_class
        }
        
        flights = await crawler.crawl_all_sites(search_params)
        
        # Convert to response format
        flight_dicts = [
            {
                'flight_id': f.flight_id,
                'airline': f.airline,
                'flight_number': f.flight_number,
                'origin': f.origin,
                'destination': f.destination,
                'departure_time': f.departure_time.isoformat(),
                'arrival_time': f.arrival_time.isoformat(),
                'price': f.price,
                'currency': f.currency,
                'seat_class': f.seat_class,
                'duration_minutes': f.duration_minutes,
                'flight_type': f.flight_type
            }
            for f in flights
        ]
        
        # Cache results
        background_tasks.add_task(
            crawler.data_manager.cache_search_results,
            search_key, flight_dicts, 1800  # 30 minutes
        )
        
        return FlightResponse(
            flights=flight_dicts,
            total_count=len(flight_dicts),
            search_time_ms=int((time.time() - start_time) * 1000)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Get crawler health status"""
    return crawler.monitor.get_health_status()

@app.get("/metrics")
async def get_metrics():
    """Get crawler metrics"""
    return {
        'requests_total': dict(crawler.monitor.metrics['requests_total']),
        'success_rates': {
            domain: (crawler.monitor.metrics['requests_successful'][domain] / 
                    crawler.monitor.metrics['requests_total'][domain] * 100)
            if crawler.monitor.metrics['requests_total'][domain] > 0 else 0
            for domain in crawler.monitor.metrics['requests_total']
        },
        'flights_scraped': dict(crawler.monitor.metrics['flights_scraped'])
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 