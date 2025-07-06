import asyncio
from production_safety_crawler import ProductionSafetyCrawler
from real_data_crawler import RealDataCrawler
from rate_limiter import RateLimiter
from persian_text import PersianTextProcessor
from monitoring import CrawlerMonitor
from adapters.base_adapters.enhanced_error_handler import EnhancedErrorHandler

sample_params = {
    "origin": "THR",
    "destination": "SYZ",
    "departure_date": "2025-06-10",
    "passengers": 1,
    "seat_class": "economy",
}


async def main():
    safety = ProductionSafetyCrawler()
    rate_limiter = RateLimiter()
    text_proc = PersianTextProcessor()
    monitor = CrawlerMonitor()
    error_handler = EnhancedErrorHandler()
    crawler = RealDataCrawler(rate_limiter, text_proc, monitor, error_handler)
    flights = await safety.safe_crawl_with_verification(
        "flytoday", crawler, sample_params
    )
    for f in flights:
        print(f)


if __name__ == "__main__":
    asyncio.run(main())
