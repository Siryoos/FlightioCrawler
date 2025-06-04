import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from crawl4ai import AsyncWebCrawler, BrowserConfig
from crawl4ai.cache_mode import CacheMode
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
    
    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: ErrorHandler):
        super().__init__()
        self.rate_limiter = rate_limiter
        self.text_processor = text_processor
        self.monitor = monitor
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        
        # Configure browser
        self.browser_config = BrowserConfig(
            headless=True,
            timeout=config.CRAWLER_TIMEOUT,
            viewport_width=1920,
            viewport_height=1080
        )
        
        self.crawler = AsyncWebCrawler(config=self.browser_config)
    
    async def check_rate_limit(self) -> bool:
        """Check rate limit for the site"""
        return await self.rate_limiter.check_rate_limit(self.domain)
    
    async def get_wait_time(self) -> Optional[int]:
        """Get time to wait before next request"""
        return await self.rate_limiter.get_wait_time(self.domain)
    
    def process_text(self, text: str) -> str:
        """Process Persian text"""
        return self.text_processor.process(text)
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on the site"""
        raise NotImplementedError("Subclasses must implement search_flights")
    
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
            await self.crawler.screenshot(f"debug_{self.domain}_{name}.png")
        except Exception as e:
            self.logger.error(f"Screenshot error: {e}")

class FlytodayCrawler(BaseSiteCrawler):
    """Crawler for Flytoday.ir"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "flytoday.ir"
        self.base_url = "https://www.flytoday.ir"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Flytoday"""
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
            await self.crawler.goto(f"{self.base_url}/search")
            
            # Fill search form
            await self._execute_js("""
                document.querySelector('input[name="origin"]').value = arguments[0];
                document.querySelector('input[name="destination"]').value = arguments[1];
                document.querySelector('input[name="departure_date"]').value = arguments[2];
                document.querySelector('select[name="passengers"]').value = arguments[3];
                document.querySelector('select[name="class"]').value = arguments[4];
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
            self.logger.error(f"Error crawling Flytoday: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []

class AlibabaCrawler(BaseSiteCrawler):
    """Crawler for Alibaba.ir"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            await self.crawler.goto(f"{self.base_url}/flight/search")
            
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "safarmarket.com"
        self.base_url = "https://www.safarmarket.com"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Safarmarket"""
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
            await self.crawler.goto(f"{self.base_url}/flight/search")
            
            # Fill search form
            await self._execute_js("""
                document.querySelector('#from').value = arguments[0];
                document.querySelector('#to').value = arguments[1];
                document.querySelector('#date').value = arguments[2];
                document.querySelector('#passengers').value = arguments[3];
                document.querySelector('#class').value = arguments[4];
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
            self.logger.error(f"Error crawling Safarmarket: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return [] 

class Mz724Crawler(BaseSiteCrawler):
    """Crawler for mz724.ir"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            await self.crawler.goto(self.base_url)
            # TODO: implement form submission and parsing
            await self._take_screenshot("search_results")
            return []
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
            await self.crawler.goto(self.base_url)
            # TODO: implement form submission and parsing
            await self._take_screenshot("search_results")
            return []
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
            await self.crawler.goto(self.base_url)
            # TODO: implement form submission and parsing
            await self._take_screenshot("search_results")
            return []
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
            await self.crawler.goto(self.base_url)
            # TODO: implement form submission and parsing
            await self._take_screenshot("search_results")
            return []
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
            await self.crawler.goto(self.base_url)
            # TODO: implement form submission and parsing
            await self._take_screenshot("search_results")
            return []
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            await self.error_handler.handle_error(self.domain, e)
            return []
