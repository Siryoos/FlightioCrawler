#!/usr/bin/env python3
"""
Enhanced Stealth Crawler for FlightioCrawler
Implements advanced anti-bot detection evasion mechanisms
"""

import asyncio
import random
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import os
import ssl
from urllib.parse import urlparse, urljoin

# HTTP and Browser imports
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, WebDriverException
from playwright.async_api import async_playwright, Browser, Page
from fake_useragent import UserAgent

# Data processing
from bs4 import BeautifulSoup
import lxml
from lxml import html

# Environment and logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CrawlerConfig:
    """Configuration for the stealth crawler"""
    # Basic settings
    headless: bool = True
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 5
    
    # Anti-detection settings
    enable_stealth: bool = True
    random_delays: bool = True
    min_delay: float = 1.0
    max_delay: float = 5.0
    user_agent_rotation: bool = True
    
    # Browser settings
    browser_type: str = 'chromium'  # 'chromium', 'firefox', 'webkit'
    window_size: Tuple[int, int] = (1920, 1080)
    viewport_size: Tuple[int, int] = (1920, 1080)
    
    # Performance settings
    disable_images: bool = True
    disable_css: bool = False
    disable_javascript: bool = False
    
    # Screenshot and debugging
    take_screenshots: bool = True
    screenshot_dir: str = './screenshots'
    save_html: bool = False
    html_dir: str = './html_dumps'
    
    # Proxy settings
    enable_proxy: bool = False
    proxy_list: List[str] = field(default_factory=list)
    proxy_rotation: bool = False
    
    # SSL settings
    ssl_verify: bool = False
    ssl_context: Optional[ssl.SSLContext] = None

class UserAgentRotator:
    """Manages user agent rotation for stealth crawling"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.used_agents = set()
        self.custom_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
    
    def get_user_agent(self) -> str:
        """Get a random user agent"""
        try:
            # Use fake-useragent library
            return self.ua.random
        except:
            # Fallback to custom agents
            return random.choice(self.custom_agents)
    
    def get_headers(self) -> Dict[str, str]:
        """Get realistic headers with user agent"""
        return {
            'User-Agent': self.get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }

class DelayManager:
    """Manages random delays for stealth crawling"""
    
    def __init__(self, min_delay: float = 1.0, max_delay: float = 5.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
    
    def wait(self):
        """Wait for a random delay"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self.last_request_time = time.time()
    
    async def async_wait(self):
        """Async version of wait"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self.last_request_time = time.time()

class EnhancedStealthCrawler:
    """Enhanced stealth crawler with anti-bot detection evasion"""
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        self.config = config or CrawlerConfig()
        self.ua_rotator = UserAgentRotator()
        self.delay_manager = DelayManager(self.config.min_delay, self.config.max_delay)
        self.session = None
        self.browser = None
        self.page = None
        self.playwright = None
        self.browser_context = None
        
        # Create directories
        os.makedirs(self.config.screenshot_dir, exist_ok=True)
        os.makedirs(self.config.html_dir, exist_ok=True)
        
        # SSL configuration
        if not self.config.ssl_verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        logger.info(f"Enhanced Stealth Crawler initialized with config: {self.config}")
    
    def _setup_session(self) -> requests.Session:
        """Setup HTTP session with stealth configurations"""
        session = requests.Session()
        
        # Setup retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Configure SSL
        if not self.config.ssl_verify:
            session.verify = False
        
        return session
    
    def _get_chrome_options(self) -> ChromeOptions:
        """Get Chrome options with stealth configurations"""
        options = ChromeOptions()
        
        # Basic options
        if self.config.headless:
            options.add_argument('--headless')
        
        # Window size
        options.add_argument(f'--window-size={self.config.window_size[0]},{self.config.window_size[1]}')
        
        # Stealth options
        if self.config.enable_stealth:
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images') if self.config.disable_images else None
            options.add_argument('--disable-javascript') if self.config.disable_javascript else None
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Random user agent
            if self.config.user_agent_rotation:
                options.add_argument(f'--user-agent={self.ua_rotator.get_user_agent()}')
        
        # Performance options
        if self.config.disable_images:
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)
        
        return options
    
    async def _setup_playwright_browser(self) -> Browser:
        """Setup Playwright browser with stealth configurations"""
        self.playwright = await async_playwright().start()
        
        browser_args = []
        if self.config.enable_stealth:
            browser_args.extend([
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled'
            ])
        
        # Launch browser
        browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=browser_args
        )
        
        # Create context with stealth settings
        context = await browser.new_context(
            viewport={"width": self.config.viewport_size[0], "height": self.config.viewport_size[1]},
            user_agent=self.ua_rotator.get_user_agent() if self.config.user_agent_rotation else None,
            ignore_https_errors=not self.config.ssl_verify
        )
        
        # Add stealth script
        if self.config.enable_stealth:
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' }),
                    }),
                });
            """)
        
        self.browser_context = context
        self.page = await context.new_page()
        
        return browser
    
    async def fetch_with_playwright(self, url: str, wait_for_selector: Optional[str] = None) -> Dict[str, Any]:
        """Fetch URL using Playwright with stealth configurations"""
        if not self.browser:
            self.browser = await self._setup_playwright_browser()
        
        try:
            if self.config.random_delays:
                await self.delay_manager.async_wait()
            
            # Navigate to URL
            response = await self.page.goto(url, wait_until='networkidle', timeout=self.config.timeout * 1000)
            
            # Wait for specific selector if provided
            if wait_for_selector:
                await self.page.wait_for_selector(wait_for_selector, timeout=self.config.timeout * 1000)
            
            # Random delay after page load
            if self.config.random_delays:
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Get page content
            content = await self.page.content()
            
            # Take screenshot if enabled
            if self.config.take_screenshots:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                screenshot_path = os.path.join(self.config.screenshot_dir, f'{urlparse(url).netloc}_{timestamp}.png')
                await self.page.screenshot(path=screenshot_path)
            
            # Save HTML if enabled
            if self.config.save_html:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                html_path = os.path.join(self.config.html_dir, f'{urlparse(url).netloc}_{timestamp}.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return {
                'url': url,
                'status_code': response.status,
                'content': content,
                'headers': dict(response.headers),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Playwright fetch error for {url}: {e}")
            return {
                'url': url,
                'status_code': 0,
                'content': '',
                'headers': {},
                'success': False,
                'error': str(e)
            }
    
    def fetch_with_requests(self, url: str) -> Dict[str, Any]:
        """Fetch URL using requests session with stealth configurations"""
        if not self.session:
            self.session = self._setup_session()
        
        try:
            if self.config.random_delays:
                self.delay_manager.wait()
            
            headers = self.ua_rotator.get_headers()
            
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.config.timeout,
                verify=self.config.ssl_verify
            )
            
            return {
                'url': url,
                'status_code': response.status_code,
                'content': response.text,
                'headers': dict(response.headers),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Requests fetch error for {url}: {e}")
            return {
                'url': url,
                'status_code': 0,
                'content': '',
                'headers': {},
                'success': False,
                'error': str(e)
            }
    
    def fetch_with_selenium(self, url: str, wait_for_selector: Optional[str] = None) -> Dict[str, Any]:
        """Fetch URL using Selenium with stealth configurations"""
        driver = None
        try:
            if self.config.random_delays:
                self.delay_manager.wait()
            
            # Setup Chrome driver
            options = self._get_chrome_options()
            service = ChromeService()
            driver = webdriver.Chrome(service=service, options=options)
            
            # Execute stealth script
            if self.config.enable_stealth:
                driver.execute_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                """)
            
            # Navigate to URL
            driver.get(url)
            
            # Wait for specific selector if provided
            if wait_for_selector:
                WebDriverWait(driver, self.config.timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                )
            
            # Random delay after page load
            if self.config.random_delays:
                time.sleep(random.uniform(0.5, 2.0))
            
            # Get page content
            content = driver.page_source
            
            # Take screenshot if enabled
            if self.config.take_screenshots:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                screenshot_path = os.path.join(self.config.screenshot_dir, f'{urlparse(url).netloc}_{timestamp}.png')
                driver.save_screenshot(screenshot_path)
            
            return {
                'url': url,
                'status_code': 200,
                'content': content,
                'headers': {},
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Selenium fetch error for {url}: {e}")
            return {
                'url': url,
                'status_code': 0,
                'content': '',
                'headers': {},
                'success': False,
                'error': str(e)
            }
        finally:
            if driver:
                driver.quit()
    
    async def crawl_url(self, url: str, method: str = 'playwright', wait_for_selector: Optional[str] = None) -> Dict[str, Any]:
        """Crawl URL with specified method"""
        logger.info(f"Crawling {url} with method: {method}")
        
        if method == 'playwright':
            return await self.fetch_with_playwright(url, wait_for_selector)
        elif method == 'requests':
            return self.fetch_with_requests(url)
        elif method == 'selenium':
            return self.fetch_with_selenium(url, wait_for_selector)
        else:
            raise ValueError(f"Unknown crawling method: {method}")
    
    async def crawl_multiple_urls(self, urls: List[str], method: str = 'playwright', max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """Crawl multiple URLs concurrently"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.crawl_url(url, method)
        
        tasks = [crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if not isinstance(r, Exception)]
    
    def parse_flights(self, html_content: str, site_type: str = 'generic') -> List[Dict[str, Any]]:
        """Parse flight information from HTML content"""
        soup = BeautifulSoup(html_content, 'lxml')
        flights = []
        
        # This is a basic parser - should be customized for each site
        if site_type == 'flytoday':
            # FlyToday specific parsing
            flight_elements = soup.select('.flight-item, .flight-card, .flight-result')
            for element in flight_elements:
                airline_elem = element.select_one('.airline-name, .airline')
                flight_num_elem = element.select_one('.flight-number')
                dep_time_elem = element.select_one('.departure-time, .dep-time')
                arr_time_elem = element.select_one('.arrival-time, .arr-time')
                price_elem = element.select_one('.price, .fare')
                origin_elem = element.select_one('.origin, .from')
                dest_elem = element.select_one('.destination, .to')
                
                flight_data = {
                    'airline': airline_elem.text.strip() if airline_elem else None,
                    'flight_number': flight_num_elem.text.strip() if flight_num_elem else None,
                    'departure_time': dep_time_elem.text.strip() if dep_time_elem else None,
                    'arrival_time': arr_time_elem.text.strip() if arr_time_elem else None,
                    'price': price_elem.text.strip() if price_elem else None,
                    'origin': origin_elem.text.strip() if origin_elem else None,
                    'destination': dest_elem.text.strip() if dest_elem else None,
                }
                if any(flight_data.values()):
                    flights.append(flight_data)
        
        # Add more site-specific parsers as needed
        
        return flights
    
    async def cleanup(self):
        """Clean up resources"""
        if self.page:
            await self.page.close()
        if self.browser_context:
            await self.browser_context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.session:
            self.session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

# Example usage and testing
async def test_stealth_crawler():
    """Test the stealth crawler"""
    config = CrawlerConfig(
        headless=True,
        enable_stealth=True,
        random_delays=True,
        user_agent_rotation=True,
        take_screenshots=True,
        min_delay=1.0,
        max_delay=3.0
    )
    
    test_urls = [
        'https://www.flytoday.ir',
        'https://www.alibaba.ir',
        'https://www.safarmarket.com'
    ]
    
    async with EnhancedStealthCrawler(config) as crawler:
        results = await crawler.crawl_multiple_urls(test_urls, method='playwright')
        
        for result in results:
            print(f"URL: {result['url']}")
            print(f"Status: {result['status_code']}")
            print(f"Success: {result['success']}")
            print(f"Content length: {len(result['content'])} chars")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_stealth_crawler()) 