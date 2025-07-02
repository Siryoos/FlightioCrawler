from celery import Celery
from celery.schedules import crontab
from typing import Dict, List
import logging
from datetime import datetime, timedelta

from config import config
from main_crawler import IranianFlightCrawler
from data_manager import DataManager
from monitoring import CrawlerMonitor

# Configure Celery
celery_app = Celery(
    "flight_crawler",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=["tasks"],
)

# Configure Celery settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    "crawl-all-routes": {
        "task": "tasks.crawl_all_routes",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "update-price-predictions": {
        "task": "tasks.update_price_predictions",
        "schedule": crontab(hour="*/1"),  # Every hour
    },
    "cleanup-old-data": {
        "task": "tasks.cleanup_old_data",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
}

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
async def crawl_route(self, route: str, search_params: Dict) -> Dict:
    """Crawl a specific route"""
    try:
        crawler = IranianFlightCrawler()
        results = await crawler.crawl_all_sites(search_params)

        # Store results
        data_manager = DataManager()
        await data_manager.store_flights({route: results})

        return {
            "route": route,
            "flights_found": len(results),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error crawling route {route}: {e}")
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes


@celery_app.task
async def crawl_all_routes():
    """Crawl all configured routes"""
    try:
        data_manager = DataManager()
        routes = await data_manager.get_active_routes()

        tasks = []
        for route in routes:
            search_params = {
                "origin": route["origin"],
                "destination": route["destination"],
                "departure_date": datetime.now().strftime("%Y-%m-%d"),
                "passengers": 1,
                "seat_class": "economy",
            }
            tasks.append(crawl_route.delay(route["id"], search_params))

        return {"routes_crawled": len(tasks), "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error in crawl_all_routes: {e}")
        return {"error": str(e)}


@celery_app.task
async def update_price_predictions():
    """Update price predictions for all routes"""
    try:
        crawler = IranianFlightCrawler()
        data_manager = DataManager()
        routes = await data_manager.get_active_routes()

        for route in routes:
            # Train model
            await crawler.ml_predictor.train_price_model(route["id"])

            # Generate predictions
            future_dates = [
                (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, 31)  # 30 days ahead
            ]
            predictions = await crawler.ml_predictor.predict_future_prices(
                route["id"], future_dates
            )

            # Store predictions
            await data_manager.store_price_predictions(route["id"], predictions)

        return {"routes_updated": len(routes), "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error updating price predictions: {e}")
        return {"error": str(e)}


@celery_app.task
async def cleanup_old_data():
    """Clean up old data from database"""
    try:
        data_manager = DataManager()

        # Clean up old flights
        cutoff_date = datetime.now() - timedelta(days=30)
        await data_manager.delete_old_flights(cutoff_date)

        # Clean up old predictions
        await data_manager.delete_old_predictions(cutoff_date)

        return {"cleanup_completed": True, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        return {"error": str(e)}


@celery_app.task
async def process_price_alerts():
    """Process price alerts and send notifications"""
    try:
        crawler = IranianFlightCrawler()
        alerts = await crawler.price_monitor.get_active_alerts()

        for alert in alerts:
            current_price = await crawler.data_manager.get_current_price(alert["route"])

            if current_price <= alert["target_price"]:
                await crawler.price_monitor.send_price_alert(alert, current_price)

        return {
            "alerts_processed": len(alerts),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error processing price alerts: {e}")
        return {"error": str(e)}


@celery_app.task
def refresh_snapshots():
    """Run replay_requests script to validate archived pages."""
    from scripts.replay_requests import replay_all

    return replay_all()
