"""
Unified Base Adapter for FlightIO Crawler
Consolidates all common functionality to minimize code duplication
"""

import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
from urllib.parse import urljoin
import json

from bs4 import BeautifulSoup
import jdatetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import Config
from rate_limiter import RateLimiter
from persian_text import PersianTextProcessor
from data_manager import DataManager


logger = logging.getLogger(__name__)


class UnifiedBaseAdapter(ABC):
    """
    Unified base adapter that provides all common functionality for site crawlers.
    Subclasses only need to implement site-specific parsing logic.
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.site_name = self.get_site_name()
        self.site_config = self.config.get_site_config(self.site_name)
        
        # Core components
        self.rate_limiter = RateLimiter(
            max_requests_per_minute=self.site_config.get('rate_limit', 30)
        )
        self.persian_processor = PersianTextProcessor()
        self.data_manager = DataManager()
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Selenium driver (lazy loaded)
        self._driver: Optional[webdriver.Chrome] = None
        
        # Common headers
        self.headers = {
            'User-Agent': self.site_config.get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fa,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
    @abstractmethod
    def get_site_name(self) -> str:
        """Return the site name for configuration lookup"""
        pass
        
    @abstractmethod
    async def parse_search_results(self, content: str, origin: str, destination: str, 
                                 date: str) -> List[Dict[str, Any]]:
        """Parse search results from HTML content"""
        pass
        
    async def initialize(self):
        """Initialize async components"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.site_config.get('timeout', 30))
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout
            )
            
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
            self.session = None
            
        if self._driver:
            self._driver.quit()
            self._driver = None
            
    async def search_flights(self, origin: str, destination: str, date: str,
                           return_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Main search method - handles rate limiting, retries, and error handling
        """
        await self.initialize()
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        try:
            # Build search URL
            search_url = self.build_search_url(origin, destination, date, return_date)
            
            # Fetch content
            content = await self.fetch_content(search_url)
            
            # Parse results
            flights = await self.parse_search_results(content, origin, destination, date)
            
            # Standardize and validate results
            standardized_flights = []
            for flight in flights:
                standardized = self.standardize_flight_data(flight)
                if self.validate_flight_data(standardized):
                    standardized_flights.append(standardized)
                    
            # Save to database
            if standardized_flights:
                await self.save_flights(standardized_flights)
                
            return standardized_flights
            
        except Exception as e:
            logger.error(f"Error searching flights on {self.site_name}: {e}")
            raise
            
    def build_search_url(self, origin: str, destination: str, date: str,
                        return_date: Optional[str] = None) -> str:
        """Build search URL based on site configuration"""
        base_url = self.site_config.get('base_url', '')
        search_path = self.site_config.get('search_path', '/flights/search')
        
        # Convert date format if needed
        formatted_date = self.format_date_for_site(date)
        
        # Build query parameters
        params = {
            'origin': origin,
            'destination': destination,
            'departure_date': formatted_date,
        }
        
        if return_date:
            params['return_date'] = self.format_date_for_site(return_date)
            
        # Construct URL
        url = urljoin(base_url, search_path)
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        
        return f"{url}?{query_string}"
        
    async def fetch_content(self, url: str) -> str:
        """Fetch content using appropriate method (requests or selenium)"""
        if self.site_config.get('requires_javascript', False):
            return await self.fetch_with_selenium(url)
        else:
            return await self.fetch_with_aiohttp(url)
            
    async def fetch_with_aiohttp(self, url: str) -> str:
        """Fetch content using aiohttp"""
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.text()
            
    async def fetch_with_selenium(self, url: str) -> str:
        """Fetch content using Selenium for JavaScript-heavy sites"""
        if not self._driver:
            self._driver = self.create_selenium_driver()
            
        self._driver.get(url)
        
        # Wait for content to load
        wait_selector = self.site_config.get('wait_selector', 'body')
        WebDriverWait(self._driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
        )
        
        # Additional wait if configured
        if self.site_config.get('additional_wait', 0) > 0:
            await asyncio.sleep(self.site_config['additional_wait'])
            
        return self._driver.page_source
        
    def create_selenium_driver(self) -> webdriver.Chrome:
        """Create Selenium driver with optimized settings"""
        options = webdriver.ChromeOptions()
        
        # Performance optimizations
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Headless mode for production
        if self.config.get('environment') == 'production':
            options.add_argument('--headless')
            
        return webdriver.Chrome(options=options)
        
    def standardize_flight_data(self, flight: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize flight data format"""
        return {
            'airline': flight.get('airline', ''),
            'flight_number': flight.get('flight_number', ''),
            'origin': flight.get('origin', ''),
            'destination': flight.get('destination', ''),
            'departure_time': flight.get('departure_time', ''),
            'arrival_time': flight.get('arrival_time', ''),
            'price': self.extract_price(flight.get('price', '')),
            'currency': flight.get('currency', 'IRR'),
            'available_seats': flight.get('available_seats', 0),
            'aircraft_type': flight.get('aircraft_type', ''),
            'flight_class': flight.get('flight_class', 'economy'),
            'site_name': self.site_name,
            'crawled_at': datetime.now().isoformat(),
            'raw_data': flight
        }
        
    def extract_price(self, price_str: Union[str, int, float]) -> float:
        """Extract numeric price from string"""
        if isinstance(price_str, (int, float)):
            return float(price_str)
            
        # Convert Persian numbers
        price_str = self.persian_processor.convert_persian_numbers(str(price_str))
        
        # Remove non-numeric characters
        import re
        price_str = re.sub(r'[^\d.]', '', price_str)
        
        try:
            return float(price_str)
        except ValueError:
            return 0.0
            
    def validate_flight_data(self, flight: Dict[str, Any]) -> bool:
        """Validate flight data"""
        required_fields = ['airline', 'origin', 'destination', 'departure_time', 'price']
        
        for field in required_fields:
            if not flight.get(field):
                return False
                
        # Price validation
        if flight['price'] <= 0:
            return False
            
        return True
        
    def format_date_for_site(self, date: str) -> str:
        """Format date according to site requirements"""
        # Override in subclasses if needed
        return date
        
    async def save_flights(self, flights: List[Dict[str, Any]]):
        """Save flights to database"""
        for flight in flights:
            await self.data_manager.save_flight(flight)
            
    def parse_persian_date(self, date_str: str) -> datetime:
        """Parse Persian date string to datetime"""
        try:
            # Convert Persian numbers first
            date_str = self.persian_processor.convert_persian_numbers(date_str)
            
            # Try to parse as Jalali date
            parts = date_str.split('/')
            if len(parts) == 3:
                year, month, day = map(int, parts)
                jalali_date = jdatetime.date(year, month, day)
                return jalali_date.togregorian()
        except:
            pass
            
        # Fallback to current date
        return datetime.now()
        
    def extract_text(self, element, selector: str, default: str = '') -> str:
        """Safely extract text from BeautifulSoup element"""
        try:
            found = element.select_one(selector)
            if found:
                return found.get_text(strip=True)
        except:
            pass
        return default 