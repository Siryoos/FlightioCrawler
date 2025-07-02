import importlib.util
import pytest

if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)

from site_crawlers import FlytodayCrawler


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
    def __init__(self, html=""):
        self._html = html

    async def goto(self, url):
        self.url = url

    async def wait_for_selector(self, selector, timeout=10):
        return True

    async def content(self):
        return self._html

    async def execute_js(self, script, *args, **kwargs):
        pass

    async def screenshot(self, *args, **kwargs):
        pass


@pytest.fixture
def sample_html():
    return """
    <div class='flight-result'>
        <span class='airline-name'>TestAir</span>
        <span class='flight-number'>TA456</span>
        <span class='departure-time'>08:00</span>
        <span class='arrival-time'>10:00</span>
        <span class='price'>2,000,000 ریال</span>
        <span class='seat-class'>اکونومی</span>
        <span class='duration'>120</span>
    </div>
    """


@pytest.fixture
def crawler(monkeypatch, sample_html):
    monkeypatch.setattr(
        "site_crawlers.AsyncWebCrawler", lambda config=None: DummyCrawler(sample_html)
    )
    monkeypatch.setattr("site_crawlers.BrowserConfig", lambda *a, **k: None)
    crawler = FlytodayCrawler(
        DummyRateLimiter(), None, DummyMonitor(), DummyErrorHandler()
    )
    crawler.crawler = DummyCrawler(sample_html)
    return crawler


@pytest.mark.asyncio
async def test_parse_search_results(crawler):
    params = {
        "origin": "THR",
        "destination": "MHD",
        "departure_date": "2024-01-01",
        "passengers": 1,
        "seat_class": "economy",
    }
    results = await crawler.search_flights(params)
    assert isinstance(results, list)
    assert results[0]["airline"] == "TestAir"
    assert results[0]["flight_number"] == "TA456"
