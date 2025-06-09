import asyncio
from production_safety_crawler import ProductionSafetyCrawler
from real_data_crawler import RealDataCrawler

sample_params = {
    "origin": "THR",
    "destination": "SYZ",
    "departure_date": "2025-06-10",
    "passengers": 1,
    "seat_class": "economy",
}

async def main():
    safety = ProductionSafetyCrawler()
    crawler = RealDataCrawler()
    flights = await safety.safe_crawl_with_verification("flytoday", crawler, sample_params)
    for f in flights:
        print(f)

if __name__ == "__main__":
    asyncio.run(main())
