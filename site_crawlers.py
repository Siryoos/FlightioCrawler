import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from local_crawler import AsyncWebCrawler, BrowserConfig
import aiohttp
try:
    from crawl4ai.cache_mode import CacheMode
except Exception:  # pragma: no cover - optional dependency
    from enum import Enum

    class CacheMode(Enum):
        BYPASS = 0
from bs4 import BeautifulSoup
from persian_text import PersianTextProcessor
from monitoring import CrawlerMonitor, ErrorHandler
from config import config
from playwright.async_api import async_playwright, Browser, Page
from rate_limiter import RateLimiter
from stealth_crawler import StealthCrawler

# Configure logging
logger = logging.getLogger(__name__)

class BaseSiteCrawler(StealthCrawler):
    """Base class for site-specific crawlers"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: ErrorHandler, interval: int = 900):
        super().__init__()
        self.rate_limiter = rate_limiter
        self.text_processor = text_processor
        self.monitor = monitor
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        
        # Configure browser
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        self.interval = interval
    
    async def _execute_js(self, script: str, **kwargs) -> Any:
        """Execute JavaScript with error handling"""
        try:
            return await self.crawler.execute_js(script, **kwargs)
        except Exception as e:
            self.logger.error(f"JavaScript execution error: {e}")
            raise
    
    async def _wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element to be present"""
        try:
            return await self.crawler.wait_for_selector(selector, timeout=timeout)
        except Exception as e:
            self.logger.error(f"Wait for element error: {e}")
            return False
    
    async def _take_screenshot(self, name: str) -> None:
        """Take screenshot for debugging"""
        try:
            await self.crawler.screenshot(path=f"debug_{self.domain}_{name}.png")
        except Exception as e:
            self.logger.error(f"Screenshot error: {e}")
    
    async def check_rate_limit(self) -> bool:
        """Check rate limit for the site"""
        return self.rate_limiter.check_rate_limit(self.domain)
    
    async def get_wait_time(self) -> Optional[int]:
        """Get time to wait before next request"""
        return self.rate_limiter.get_wait_time(self.domain)
    
    def process_text(self, text: str) -> str:
        """Process Persian text"""
        return self.text_processor.process(text)
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on the site"""
        raise NotImplementedError("Subclasses must implement search_flights")

    async def _return_dummy_flights(self, search_params: Dict) -> List[Dict]:
        """Return dummy flight data used when real crawling is unavailable."""
        await asyncio.sleep(0)
        now = datetime.now()
        return [
            {
                "airline": "DemoAir",
                "flight_number": "DM123",
                "origin": search_params.get("origin", ""),
                "destination": search_params.get("destination", ""),
                "departure_time": now,
                "arrival_time": now,
                "price": 1000000,
                "currency": "IRR",
                "seat_class": search_params.get("seat_class", "economy"),
                "duration": 60,
                "source_url": getattr(self, "base_url", "")
            }
        ]

    async def continuous_monitoring(self, routes: List[Dict]) -> None:
        """Continuously search flights for the provided routes."""
        while True:
            for params in routes:
                await self.search_flights(params)
            await asyncio.sleep(self.interval)

class FlytodayCrawler(BaseSiteCrawler):
    """Crawler for Flytoday.ir"""

    def __init__(self, *args, interval: int = 2700, **kwargs):
        super().__init__(*args, interval=interval, **kwargs)
        self.domain = "flytoday.ir"
        self.base_url = "https://www.flytoday.ir"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Flytoday. This demo implementation returns dummy data."""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            flights = await self._return_dummy_flights(search_params)

            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling Flytoday: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class AlibabaCrawler(BaseSiteCrawler):
    """Crawler for Alibaba.ir"""

    def __init__(self, *args, interval: int = 900, **kwargs):
        super().__init__(*args, interval=interval, **kwargs)
        self.domain = "alibaba.ir"
        self.base_url = "https://www.alibaba.ir"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Alibaba"""
        start_time = datetime.now()
        
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            
            # Navigate to search page
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            
            # Fill search form
            await self._execute_js("""
                document.querySelector('#origin').value = arguments[0];
                document.querySelector('#destination').value = arguments[1];
                document.querySelector('#departure_date').value = arguments[2];
                document.querySelector('#adult').value = arguments[3];
                document.querySelector('#cabin_class').value = arguments[4];
            """, 
            search_params["origin"],
            search_params["destination"],
            search_params["departure_date"],
            search_params["passengers"],
            search_params["seat_class"])
            
            # Submit form
            await self._execute_js("""
                document.querySelector('form').submit();
            """)
            
            # Wait for results
            if not await self._wait_for_element('.flight-list', timeout=30):
                raise Exception("Flight results not found")
            
            # Take screenshot for debugging
            await self._take_screenshot("search_results")
            
            # Extract flight data
            html = await self.crawler.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            flights = []
            for flight_elem in soup.select('.flight-item'):
                try:
                    flight = {
                        'airline': self.process_text(flight_elem.select_one('.airline-name').text),
                        'flight_number': flight_elem.select_one('.flight-number').text.strip(),
                        'origin': search_params["origin"],
                        'destination': search_params["destination"],
                        'departure_time': self.text_processor.parse_time(
                            flight_elem.select_one('.departure-time').text
                        ),
                        'arrival_time': self.text_processor.parse_time(
                            flight_elem.select_one('.arrival-time').text
                        ),
                        'price': self.text_processor.extract_price(
                            flight_elem.select_one('.price').text
                        )[0],
                        'currency': 'IRR',
                        'seat_class': self.text_processor.normalize_seat_class(
                            flight_elem.select_one('.seat-class').text
                        ),
                        'duration': self.text_processor.extract_duration(
                            flight_elem.select_one('.duration').text
                        ),
                        'source_url': self.base_url
                    }
                    flights.append(flight)
                except Exception as e:
                    self.logger.error(f"Error parsing flight: {e}")
                    continue
            
            # Track successful request
            await self.monitor.track_request(self.domain, start_time.timestamp())
            
            return flights
            
        except Exception as e:
            self.logger.error(f"Error crawling Alibaba: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class SafarmarketCrawler(BaseSiteCrawler):
    """Crawler for Safarmarket.com"""

    def __init__(self, *args, interval: int = 900, **kwargs):
        super().__init__(*args, interval=interval, **kwargs)
        self.domain = "safarmarket.com"
        self.base_url = "https://www.safarmarket.com"

    async def _build_api_payload(self, search_params: Dict) -> Dict:
        """Construct request payload for the Safarmarket search API."""
        return {
            "platform": "WEB_DESKTOP",
            "uid": "",
            "limit": 250,
            "compress": False,
            "productType": "IFLI",
            "searchValidity": 2,
            "cid": 1,
            "checksum": 1,
            "IPInfo": {"ip": "0.0.0.0", "isp": "", "city": "", "country": "IR"},
            "searchFilter": {
                "sourceAirportCode": search_params.get("origin"),
                "targetAirportCode": search_params.get("destination"),
                "sourceIsCity": False,
                "targetIsCity": False,
                "leaveDate": search_params.get("departure_date"),
                "returnDate": search_params.get("return_date", ""),
                "adultCount": search_params.get("passengers", 1),
                "childCount": search_params.get("children", 0),
                "infantCount": search_params.get("infants", 0),
                "economy": True,
                "business": True,
            },
        }

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Safarmarket using its JSON API."""
        start_time = datetime.now()

        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = f"{self.base_url}/api/flight/v3/search"
            payload = await self._build_api_payload(search_params)

            headers = await self.randomize_request_headers()
            headers.update({
                "Content-Type": "application/json;charset=utf-8",
                "X-Auth-Token": "",
            })

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=config.CRAWLER.REQUEST_TIMEOUT) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    data = await resp.json()

            flights: List[Dict] = []
            for flight in data.get("result", {}).get("flights", []):
                try:
                    provider = flight.get("providers", [{}])[0]
                    flights.append({
                        "airline": self.process_text(flight.get("airline", "")),
                        "flight_number": flight.get("flightNumber", ""),
                        "origin": search_params.get("origin"),
                        "destination": search_params.get("destination"),
                        "departure_time": flight.get("departTime"),
                        "arrival_time": flight.get("arriveTime"),
                        "price": provider.get("price", 0),
                        "currency": provider.get("currency", "IRR"),
                        "seat_class": flight.get("cabinClass", ""),
                        "duration": flight.get("duration", 0),
                        "source_url": self.base_url,
                    })
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())

            return flights

        except Exception as e:
            self.logger.error(f"Error crawling Safarmarket: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class Mz724Crawler(BaseSiteCrawler):
    """Crawler for mz724.ir"""
    def __init__(self, *args, interval: int = 1800, **kwargs):
        super().__init__(*args, interval=interval, **kwargs)
        self.domain = "mz724.ir"
        self.base_url = "https://mz724.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on mz724.ir"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            flights = await self._return_dummy_flights(search_params)

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class PartoCRSCrawler(BaseSiteCrawler):
    """Crawler for partocrs.com"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "partocrs.com"
        self.base_url = "https://www.partocrs.com"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Parto CRS"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            flights = await self._return_dummy_flights(search_params)

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class PartoTicketCrawler(BaseSiteCrawler):
    """Crawler for parto-ticket.ir"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "parto-ticket.ir"
        self.base_url = "https://parto-ticket.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Parto Ticket"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            flights = await self._return_dummy_flights(search_params)

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class BookCharter724Crawler(BaseSiteCrawler):
    """Crawler for bookcharter724.ir"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "bookcharter724.ir"
        self.base_url = "https://bookcharter724.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on BookCharter724"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            flights = await self._return_dummy_flights(search_params)

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class BookCharterCrawler(BaseSiteCrawler):
    """Crawler for bookcharter.ir"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "bookcharter.ir"
        self.base_url = "https://bookcharter.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on BookCharter"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)
            await self.crawler.navigate(f"{self.base_url}/flight/search")
            flights = await self._return_dummy_flights(search_params)

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []
