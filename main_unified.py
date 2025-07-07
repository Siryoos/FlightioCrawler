"""
FlightIO Unified Main Entry Point
Single entry point for all services based on SERVICE_TYPE environment variable
"""

import os
import sys
import asyncio
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_api():
    """Run the API service"""
    logger.info("Starting FlightIO API Service...")
    
    import uvicorn
    from fastapi import FastAPI
    from api.v1 import flights, health, sites, system
    
    app = FastAPI(
        title="FlightIO API",
        version="2.0.0",
        description="Unified Flight Search API"
    )
    
    # Include routers
    app.include_router(flights.router, prefix="/api/v1/flights", tags=["flights"])
    app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
    app.include_router(sites.router, prefix="/api/v1/sites", tags=["sites"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
    
    # Add monitoring
    from monitoring.unified_monitor import UnifiedMonitor
    monitor = UnifiedMonitor()
    
    @app.on_event("startup")
    async def startup_event():
        await monitor.start(port=8080)
        app.state.monitor = monitor
        logger.info("API service started successfully")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        await monitor.stop()
        logger.info("API service stopped")
    
    # Run the API
    uvicorn.run(
        app,
        host=os.getenv('API_HOST', '0.0.0.0'),
        port=int(os.getenv('API_PORT', '8000')),
        workers=int(os.getenv('API_WORKERS', '1')),
        reload=os.getenv('API_RELOAD', 'false').lower() == 'true'
    )


async def run_crawler():
    """Run the crawler service"""
    logger.info("Starting FlightIO Crawler Service...")
    
    from adapters.unified_base_adapter import UnifiedBaseAdapter
    from adapters.site_adapters.alibaba_unified import AlibabaAdapter
    from monitoring.unified_monitor import UnifiedMonitor
    from config import Config
    
    # Initialize components
    config = Config()
    monitor = UnifiedMonitor()
    await monitor.start(port=8081)
    
    # Initialize adapters
    adapters = {
        'alibaba': AlibabaAdapter(config),
        # Add more adapters here
    }
    
    logger.info(f"Initialized {len(adapters)} site adapters")
    
    try:
        # Main crawler loop
        while True:
            # This is a simplified example - in production you'd get tasks from a queue
            for site_name, adapter in adapters.items():
                try:
                    # Example search
                    results = await adapter.search_flights(
                        origin='THR',
                        destination='MHD',
                        date='2024-01-15'
                    )
                    
                    monitor.record_flights_found(
                        site=site_name,
                        count=len(results),
                        route='THR-MHD'
                    )
                    
                    logger.info(f"Found {len(results)} flights on {site_name}")
                    
                except Exception as e:
                    logger.error(f"Error crawling {site_name}: {e}")
                    monitor.record_error(
                        site=site_name,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                    
            # Wait before next iteration
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Crawler interrupted by user")
    finally:
        # Cleanup
        for adapter in adapters.values():
            await adapter.close()
        await monitor.stop()
        logger.info("Crawler stopped")


def run_worker():
    """Run the Celery worker service"""
    logger.info("Starting FlightIO Worker Service...")
    
    from celery import Celery
    from tasks import celery_app
    
    # Run Celery worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--pool=prefork'
    ])


def run_frontend():
    """Run the frontend development server"""
    logger.info("Starting FlightIO Frontend Service...")
    
    # Change to frontend directory
    os.chdir('frontend')
    
    # Run npm start
    import subprocess
    subprocess.run(['npm', 'start'], check=True)


def main():
    """Main entry point - determines which service to run"""
    service_type = os.getenv('SERVICE_TYPE', 'api').lower()
    
    logger.info(f"FlightIO Unified Application")
    logger.info(f"Service Type: {service_type}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    if service_type == 'api':
        run_api()
    elif service_type == 'crawler':
        asyncio.run(run_crawler())
    elif service_type == 'worker':
        run_worker()
    elif service_type == 'frontend':
        run_frontend()
    else:
        logger.error(f"Unknown service type: {service_type}")
        logger.info("Valid service types: api, crawler, worker, frontend")
        sys.exit(1)


if __name__ == "__main__":
    main() 