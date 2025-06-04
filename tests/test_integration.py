import importlib.util
import pytest
if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
import asyncio
import pytest
from main_crawler import IranianFlightCrawler

class DummyCrawler:
    async def search_flights(self, params):
        return [{"flight_number": "XX123"}]

@pytest.mark.asyncio
async def test_crawl_all_sites(monkeypatch):
    crawler = IranianFlightCrawler()
    for key in crawler.crawlers:
        crawler.crawlers[key] = DummyCrawler()
    results = await crawler.crawl_all_sites({"origin":"THR","destination":"MHD","departure_date":"2024-01-01","passengers":1,"seat_class":"economy"})
    assert isinstance(results, list)
    assert results[0]["flight_number"] == "XX123"
