import asyncio
from typing import List, Dict

from rate_limiter import RateLimiter
from persian_text import PersianTextProcessor
from monitoring import CrawlerMonitor, ErrorHandler
from site_crawlers import (
    SafarmarketCrawler,
    Mz724Crawler,
    FlytodayCrawler,
    FlightioCrawler,
    AlibabaCrawler,
)


class FlightMonitoringSystem:
    """Continuously monitor multiple sites at platform-specific intervals."""

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.text_processor = PersianTextProcessor()
        self.monitor = CrawlerMonitor()
        self.error_handler = ErrorHandler()

        self.crawlers = {
            'safarmarket.com': SafarmarketCrawler(
                self.rate_limiter, self.text_processor, self.monitor, self.error_handler, interval=900
            ),
            'mz724.ir': Mz724Crawler(
                self.rate_limiter, self.text_processor, self.monitor, self.error_handler, interval=1800
            ),
            'flightio.com': FlightioCrawler(
                self.rate_limiter, self.text_processor, self.monitor, self.error_handler, interval=2700
            ),
            'flytoday.ir': FlytodayCrawler(
                self.rate_limiter, self.text_processor, self.monitor, self.error_handler, interval=2700
            ),
            'alibaba.ir': AlibabaCrawler(
                self.rate_limiter, self.text_processor, self.monitor, self.error_handler, interval=900
            ),
        }
        self.monitor_tasks: Dict[str, asyncio.Task] = {}

    async def _monitor_crawler(self, crawler, routes: List[Dict]):
        while True:
            for params in routes:
                await crawler.search_flights(params)
            await asyncio.sleep(crawler.interval)

    def start_monitoring(self, routes: List[Dict]):
        for name, crawler in self.crawlers.items():
            if name not in self.monitor_tasks:
                self.monitor_tasks[name] = asyncio.create_task(
                    self._monitor_crawler(crawler, routes)
                )

    async def stop_monitoring(self):
        for task in self.monitor_tasks.values():
            task.cancel()
        self.monitor_tasks.clear()
