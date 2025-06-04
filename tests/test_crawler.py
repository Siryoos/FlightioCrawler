import importlib.util
import pytest
if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
import inspect
from site_crawlers import (
    FlytodayCrawler,
    AlibabaCrawler,
    SafarmarketCrawler,
    Mz724Crawler,
    PartoCRSCrawler,
    PartoTicketCrawler,
    BookCharter724Crawler,
    BookCharterCrawler,
    BaseSiteCrawler,
)


def test_crawler_classes_exist():
    for cls in [
        FlytodayCrawler,
        AlibabaCrawler,
        SafarmarketCrawler,
        Mz724Crawler,
        PartoCRSCrawler,
        PartoTicketCrawler,
        BookCharter724Crawler,
        BookCharterCrawler,
    ]:
        assert issubclass(cls, BaseSiteCrawler)
        assert inspect.iscoroutinefunction(cls.search_flights)
