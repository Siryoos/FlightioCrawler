import importlib.util
import pytest

if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)

from site_crawlers import BookCharterCrawler

class DummyRateLimiter:
    async def wait_for_domain(self, domain):
        pass
    def check_rate_limit(self, domain):
        return True
    def get_wait_time(self, domain):
        return 0

class DummyMonitor:
    async def track_request(self, domain, timestamp, success=True, error=None):
        self.called = True

class DummyErrorHandler:
    async def can_make_request(self, domain):
        return True
    async def handle_error(self, domain, error):
        self.error = error

class DummyCrawler:
    async def goto(self, url):
        self.url = url
    async def wait_for_selector(self, selector, timeout=10):
        return True
    async def execute_js(self, script, *args, **kwargs):
        pass
    async def screenshot(self, *args, **kwargs):
        pass

@pytest.fixture
def crawler(monkeypatch):
    monkeypatch.setattr('site_crawlers.AsyncWebCrawler', lambda config=None: DummyCrawler())
    monkeypatch.setattr('site_crawlers.BrowserConfig', lambda *a, **k: None)
    crawler = BookCharterCrawler(DummyRateLimiter(), None, DummyMonitor(), DummyErrorHandler())
    crawler.crawler = DummyCrawler()
    return crawler

@pytest.mark.asyncio
async def test_returns_empty_list(crawler):
    params = {
        'origin': 'THR',
        'destination': 'MHD',
        'departure_date': '2024-01-01',
        'passengers': 1,
        'seat_class': 'economy'
    }
    results = await crawler.search_flights(params)
    assert results == []
