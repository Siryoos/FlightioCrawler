import asyncio
import logging
import ssl
import os
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
from monitoring import CrawlerMonitor
from adapters.base_adapters.enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
)
from config import config
from playwright.async_api import async_playwright, Browser, Page
from rate_limiter import RateLimiter
from stealth_crawler import StealthCrawler
from adapters.base_adapters import BaseSiteCrawler

# SSL Configuration
from security.ssl_manager import get_ssl_manager

# Configure logging
logger = logging.getLogger(__name__)




class FlytodayCrawler(BaseSiteCrawler):
    """Crawler for Flytoday.ir"""
    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 2700):
        super().__init__("flytoday.ir", "https://www.flytoday.ir", rate_limiter, text_processor, monitor, error_handler, interval=interval)
        self.domain = "flytoday.ir"
        self.base_url = "https://www.flytoday.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Flytoday by parsing the results page."""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/search?origin={search_params.get('origin')}"
                f"&destination={search_params.get('destination')}"
                f"&departDate={search_params.get('departure_date')}"
                f"&adult={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling Flytoday: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            fallback = await self._api_fallback(search_params)
            return fallback


class FlightioCrawler(BaseSiteCrawler):
    """Crawler for Flightio.com"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 2700):
        super().__init__("flightio.com", "https://flightio.com", rate_limiter, text_processor, monitor, error_handler, interval=interval)

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Flightio by parsing the results page."""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/{search_params.get('origin')}-"
                f"{search_params.get('destination')}?depart={search_params.get('departure_date')}"
                f"&adult={search_params.get('passengers', 1)}&child=0&infant=0&flightType=1&cabinType=1"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling Flightio: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class AlibabaCrawler(BaseSiteCrawler):
    """Crawler for Alibaba.ir"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 900):
        super().__init__("alibaba.ir", "https://www.alibaba.ir", rate_limiter, text_processor, monitor, error_handler, interval=interval)

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Alibaba"""
        start_time = datetime.now()

        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            # Navigate to search page
            await self.crawler.navigate(f"{self.base_url}/flight/search")

            # Fill search form
            await self._execute_js(
                """
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
                search_params["seat_class"],
            )

            # Submit form
            await self._execute_js(
                """
                document.querySelector('form').submit();
            """
            )

            # Wait for results
            if not await self._wait_for_element(".flight-list", timeout=30):
                raise Exception("Flight results not found")

            # Take screenshot for debugging
            await self._take_screenshot("search_results")

            # Extract flight data
            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")

            flights = []
            for flight_elem in soup.select(".flight-item"):
                try:
                    flight = {
                        "airline": self.process_text(
                            flight_elem.select_one(".airline-name").text
                        ),
                        "flight_number": flight_elem.select_one(
                            ".flight-number"
                        ).text.strip(),
                        "origin": search_params["origin"],
                        "destination": search_params["destination"],
                        "departure_time": self.text_processor.parse_time(
                            flight_elem.select_one(".departure-time").text
                        ),
                        "arrival_time": self.text_processor.parse_time(
                            flight_elem.select_one(".arrival-time").text
                        ),
                        "price": self.text_processor.extract_price(
                            flight_elem.select_one(".price").text
                        )[0],
                        "currency": "IRR",
                        "seat_class": self.text_processor.normalize_seat_class(
                            flight_elem.select_one(".seat-class").text
                        ),
                        "duration": self.text_processor.extract_duration(
                            flight_elem.select_one(".duration").text
                        ),
                        "source_url": self.base_url,
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
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class SnapptripCrawler(BaseSiteCrawler):
    """Crawler for Snapptrip.com"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 900):
        super().__init__("snapptrip.com", "https://www.snapptrip.com", rate_limiter, text_processor, monitor, error_handler, interval=interval)

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Snapptrip"""
        start_time = datetime.now()

        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flights/{search_params.get('origin')}-"
                f"{search_params.get('destination')}?depart={search_params.get('departure_date')}"
                f"&adult={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".flight-item", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")

            flights = []
            for item in soup.select(".flight-item"):
                try:
                    flights.append(
                        {
                            "airline": (
                                self.process_text(item.select_one(".airline-name").text)
                                if item.select_one(".airline-name")
                                else ""
                            ),
                            "flight_number": (
                                item.select_one(".flight-number").text.strip()
                                if item.select_one(".flight-number")
                                else ""
                            ),
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": (
                                self.text_processor.parse_time(
                                    item.select_one(".departure-time").text
                                )
                                if item.select_one(".departure-time")
                                else None
                            ),
                            "arrival_time": (
                                self.text_processor.parse_time(
                                    item.select_one(".arrival-time").text
                                )
                                if item.select_one(".arrival-time")
                                else None
                            ),
                            "price": (
                                self.text_processor.extract_price(
                                    item.select_one(".price").text
                                )[0]
                                if item.select_one(".price")
                                else 0
                            ),
                            "currency": "IRR",
                            "seat_class": (
                                self.text_processor.normalize_seat_class(
                                    item.select_one(".seat-class").text
                                )
                                if item.select_one(".seat-class")
                                else ""
                            ),
                            "duration": (
                                self.text_processor.extract_duration(
                                    item.select_one(".duration").text
                                )
                                if item.select_one(".duration")
                                else 0
                            ),
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())

            return flights

        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class SafarmarketCrawler(BaseSiteCrawler):
    """Crawler for Safarmarket.com"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 900):
        super().__init__("safarmarket.com", "https://www.safarmarket.com", rate_limiter, text_processor, monitor, error_handler, interval=interval)

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
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = f"{self.base_url}/api/flight/v3/search"
            payload = await self._build_api_payload(search_params)

            headers = await self.randomize_request_headers()
            headers.update(
                {
                    "Content-Type": "application/json;charset=utf-8",
                    "X-Auth-Token": "",
                }
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=config.CRAWLER.REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    data = await resp.json()

            flights: List[Dict] = []
            for flight in data.get("result", {}).get("flights", []):
                try:
                    provider = flight.get("providers", [{}])[0]
                    flights.append(
                        {
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
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())

            return flights

        except Exception as e:
            self.logger.error(f"Error crawling Safarmarket: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class Mz724Crawler(BaseSiteCrawler):
    """Crawler for mz724.ir"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 1800):
        super().__init__("mz724.ir", "https://mz724.ir", rate_limiter, text_processor, monitor, error_handler, interval=interval)

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on mz724.ir and return real results."""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            # Build search URL based on provided parameters
            origin_slug = search_params.get(
                "origin_slug", search_params.get("origin", "")
            )
            dest_slug = search_params.get(
                "destination_slug", search_params.get("destination", "")
            )
            date = search_params.get("departure_date")
            url = f"{self.base_url}/Ticket-{origin_slug}-{dest_slug}.html?t={date}"

            await self.crawler.navigate(url)

            # Wait for search results
            await self._wait_for_element(".resu", timeout=30)

            # Extract flight data
            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                if item.select_one(".advertise"):
                    continue

                price_el = item.select_one("div.price span")
                if not price_el:
                    continue

                try:
                    price = self.text_processor.extract_price(price_el.text)[0]
                except Exception:
                    continue

                dep_el = item.select_one("div.date")
                departure_time = (
                    self.text_processor.parse_time(dep_el.text) if dep_el else None
                )

                airline_el = item.select_one("strong.airline_name")
                airline = (
                    self.text_processor.normalize_airline_name(airline_el.text)
                    if airline_el
                    else ""
                )

                flight_no_el = item.select_one("span.code_inn")
                flight_number = (
                    self.text_processor.process(flight_no_el.text)
                    if flight_no_el
                    else ""
                )

                seat_class = item.select_one("div.price").get("rel", "")

                flights.append(
                    {
                        "airline": airline,
                        "flight_number": flight_number,
                        "origin": search_params.get("origin"),
                        "destination": search_params.get("destination"),
                        "departure_time": departure_time,
                        "arrival_time": None,
                        "price": price,
                        "currency": "IRR",
                        "seat_class": seat_class,
                        "duration": 0,
                        "source_url": url,
                    }
                )

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class PartoCRSCrawler(BaseSiteCrawler):
    """Crawler for partocrs.com"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler):
        super().__init__("partocrs.com", "https://www.partocrs.com", rate_limiter, text_processor, monitor, error_handler)
        self.domain = "partocrs.com"
        self.base_url = "https://www.partocrs.com"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Parto CRS"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/search?origin={search_params.get('origin')}"
                f"&destination={search_params.get('destination')}"
                f"&date={search_params.get('departure_date')}"
                f"&passengers={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class PartoTicketCrawler(BaseSiteCrawler):
    """Crawler for parto-ticket.ir"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler):
        super().__init__("parto-ticket.ir", "https://parto-ticket.ir", rate_limiter, text_processor, monitor, error_handler)
        self.domain = "parto-ticket.ir"
        self.base_url = "https://parto-ticket.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Parto Ticket"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/search?origin={search_params.get('origin')}"
                f"&destination={search_params.get('destination')}"
                f"&date={search_params.get('departure_date')}"
                f"&passengers={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class BookCharter724Crawler(BaseSiteCrawler):
    """Crawler for bookcharter724.ir"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler):
        super().__init__("bookcharter724.ir", "https://bookcharter724.ir", rate_limiter, text_processor, monitor, error_handler)
        self.domain = "bookcharter724.ir"
        self.base_url = "https://bookcharter724.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on BookCharter724"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/search?origin={search_params.get('origin')}"
                f"&destination={search_params.get('destination')}"
                f"&date={search_params.get('departure_date')}"
                f"&passengers={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class BookCharterCrawler(BaseSiteCrawler):
    """Crawler for bookcharter.ir"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler):
        super().__init__("bookcharter.ir", "https://bookcharter.ir", rate_limiter, text_processor, monitor, error_handler)
        self.domain = "bookcharter.ir"
        self.base_url = "https://bookcharter.ir"

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on BookCharter"""
        start_time = datetime.now()
        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []
            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = (
                f"{self.base_url}/flight/search?origin={search_params.get('origin')}"
                f"&destination={search_params.get('destination')}"
                f"&date={search_params.get('departure_date')}"
                f"&passengers={search_params.get('passengers', 1)}"
            )
            await self.crawler.navigate(url)

            if not await self._wait_for_element(".resu", timeout=30):
                raise Exception("Flight results not found")

            html = await self.crawler.content()
            soup = BeautifulSoup(html, "html.parser")
            flights: List[Dict] = []

            for item in soup.select("div.resu"):
                try:
                    price_el = item.select_one("div.price span")
                    if not price_el:
                        continue

                    dep_el = item.select_one("div.date")
                    departure_time = (
                        self.text_processor.parse_time(dep_el.text) if dep_el else None
                    )

                    airline_el = item.select_one("strong.airline_name")
                    airline = (
                        self.text_processor.normalize_airline_name(airline_el.text)
                        if airline_el
                        else ""
                    )

                    flight_no_el = item.select_one("span.code_inn")
                    flight_number = (
                        self.text_processor.process(flight_no_el.text)
                        if flight_no_el
                        else ""
                    )

                    seat_class = item.select_one("div.price").get("rel", "")

                    flights.append(
                        {
                            "airline": airline,
                            "flight_number": flight_number,
                            "origin": search_params.get("origin"),
                            "destination": search_params.get("destination"),
                            "departure_time": departure_time,
                            "arrival_time": None,
                            "price": self.text_processor.extract_price(price_el.text)[
                                0
                            ],
                            "currency": "IRR",
                            "seat_class": seat_class,
                            "duration": 0,
                            "source_url": url,
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self._take_screenshot("search_results")
            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)


class MrbilitCrawler(BaseSiteCrawler):
    """Crawler for mrbilit.com"""

    def __init__(self, rate_limiter, text_processor: PersianTextProcessor, monitor: CrawlerMonitor, error_handler: EnhancedErrorHandler, interval: int = 900):
        super().__init__("mrbilit.com", "https://mrbilit.com", rate_limiter, text_processor, monitor, error_handler, interval=interval)

        self.domain = "mrbilit.com"
        self.base_url = "https://mrbilit.com"
    async def _build_api_payload(self, search_params: Dict) -> Dict:
        return {
            "sourceAirportCode": search_params.get("origin"),
            "targetAirportCode": search_params.get("destination"),
            "leaveDate": search_params.get("departure_date"),
            "returnDate": search_params.get("return_date", ""),
            "adultCount": search_params.get("passengers", 1),
            "childCount": search_params.get("children", 0),
            "infantCount": search_params.get("infants", 0),
            "economy": True,
            "business": True,
        }

    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Mrbilit using its JSON API."""
        start_time = datetime.now()

        try:
            if not await self.error_handler.can_make_request_async(self.domain):
                self.logger.warning(f"Circuit breaker open for {self.domain}")
                return []

            if not await self.check_rate_limit():
                wait_time = await self.get_wait_time()
                if wait_time:
                    await asyncio.sleep(wait_time)

            url = "https://flight.atighgasht.com/api/Flights"
            payload = await self._build_api_payload(search_params)

            headers = await self.randomize_request_headers()
            headers.update(
                {
                    "Content-Type": "application/json;charset=utf-8",
                }
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=config.CRAWLER.REQUEST_TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    data = await resp.json()

            flights: List[Dict] = []
            for flight in data.get("flights", []):
                try:
                    provider = flight.get("providers", [{}])[0]
                    flights.append(
                        {
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
                        }
                    )
                except Exception as parse_err:
                    self.logger.error(f"Error parsing flight: {parse_err}")
                    continue

            await self.monitor.track_request(self.domain, start_time.timestamp())
            return flights
        except Exception as e:
            self.logger.error(f"Error crawling {self.domain}: {e}")
            context = ErrorContext(adapter_name=self.domain, operation="search_flights")
            await self.error_handler.handle_error(e, context)
            return await self._api_fallback(search_params)
