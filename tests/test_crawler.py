import importlib.util
import pytest

if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
import inspect
from site_crawlers import (
    FlytodayCrawler,
    FlightioCrawler,
    AlibabaCrawler,
    SafarmarketCrawler,
    Mz724Crawler,
    PartoCRSCrawler,
    PartoTicketCrawler,
    BookCharter724Crawler,
    BookCharterCrawler,
    MrbilitCrawler,
)
from adapters.base_adapters import BaseSiteCrawler


def test_crawler_classes_exist():
    for cls in [
        FlytodayCrawler,
        FlightioCrawler,
        AlibabaCrawler,
        SafarmarketCrawler,
        Mz724Crawler,
        PartoCRSCrawler,
        PartoTicketCrawler,
        BookCharter724Crawler,
        BookCharterCrawler,
        MrbilitCrawler,
    ]:
        assert issubclass(cls, BaseSiteCrawler)
        assert inspect.iscoroutinefunction(cls.search_flights)
