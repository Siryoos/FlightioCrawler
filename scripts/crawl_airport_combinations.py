import asyncio
from datetime import datetime, timedelta

from main_crawler import IranianFlightCrawler

AIRPORTS = [
    "IKA",
    "THR",
    "MHD",
    "IFN",
    "SYZ",
    "TBZ",
    "KER",
    "BND",
    "AWZ",
    "BUZ",
    "ABD",
    "AEU",
    "ADU",
    "PGU",
    "BDH",
    "XBJ",
    "BJB",
    "ACP",
    "ZBR",
    "DEF",
    "GCH",
    "GBT",
    "IIL",
    "IHR",
    "JSK",
    "JYR",
    "KKS",
    "KSH",
    "KHD",
    "KIH",
    "LRR",
    "IMQ",
    "GSM",
    "RAS",
    "AFZ",
    "SDG",
    "SRY",
    "CQD",
    "SYJ",
    "TCX",
    "OMH",
    "YES",
    "AZD",
    "ACZ",
    "ZAH",
    "JWN",
    "BXR",
    "FAZ",
    "HDM",
    "KHK",
    "KHY",
    "LFM",
    "MRX",
    "PFQ",
    "RZR",
    "CKT",
]

CONCURRENCY = 5


async def crawl_single(
    crawler: IranianFlightCrawler, sem: asyncio.Semaphore, params: dict
) -> None:
    async with sem:
        await crawler.crawl_all_sites(params)


async def main() -> None:
    crawler = IranianFlightCrawler()
    sem = asyncio.Semaphore(CONCURRENCY)
    today = datetime.now().date()
    end_date = today + timedelta(days=14)
    tasks = []
    for i in range((end_date - today).days + 1):
        date_str = (today + timedelta(days=i)).isoformat()
        for origin in AIRPORTS:
            for destination in AIRPORTS:
                if origin == destination:
                    continue
                params = {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": date_str,
                }
                tasks.append(asyncio.create_task(crawl_single(crawler, sem, params)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
