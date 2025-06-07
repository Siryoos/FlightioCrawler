from abc import ABC, abstractmethod
from typing import Dict, Any
import json
from local_crawler import AsyncWebCrawler, BrowserConfig
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page

class BaseSiteCrawler(ABC):
    """Abstract base class for all site crawlers"""
    
    def __init__(self, config: dict):
        self.config = config
        self.rate_limiter = self._create_rate_limiter()
        self.parser = self._create_parser()
        self.browser_config = self._create_browser_config()
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        
    @abstractmethod
    async def crawl(self, search_params: dict) -> list:
        """Main crawl method to be implemented by subclasses"""
        pass
        
    def _create_rate_limiter(self):
        """Create rate limiter based on config"""
        from core.rate_limiter import RateLimiter
        return RateLimiter(self.config.get('rate_limit', {}))
        
    def _create_parser(self):
        """Create parser based on config"""
        from data.transformers.persian_text_processor import PersianTextProcessor
        return PersianTextProcessor()
        
    def _create_browser_config(self) -> BrowserConfig:
        """Create browser configuration"""
        return BrowserConfig(
            headless=True,
            timeout=self.config.get('timeout', 30000),
            viewport_width=1920,
            viewport_height=1080
        )

class JavaScriptCrawler(BaseSiteCrawler):
    """Crawler for JavaScript-heavy sites"""
    
    async def crawl(self, search_params: dict) -> list:
        await self.rate_limiter.wait()
        
        try:
            # Navigate to search page
            await self.crawler.goto(self.config['search_url'])
            
            # Execute search form filling
            await self._execute_search_form(search_params)
            
            # Wait for results
            await self._wait_for_results()
            
            # Extract data
            return await self._extract_flight_data()
            
        except Exception as e:
            self.logger.error(f"Error in JavaScript crawler: {e}")
            return []

class APICrawler(BaseSiteCrawler):
    """Crawler for sites with API access"""
    
    async def crawl(self, search_params: dict) -> list:
        await self.rate_limiter.wait()
        
        try:
            # Make API request
            response = await self._make_api_request(search_params)
            
            # Parse response
            return self._parse_api_response(response)
            
        except Exception as e:
            self.logger.error(f"Error in API crawler: {e}")
            return []

class FormCrawler(BaseSiteCrawler):
    """Crawler for traditional form-based sites"""
    
    async def crawl(self, search_params: dict) -> list:
        await self.rate_limiter.wait()
        
        try:
            # Navigate to search page
            await self.crawler.goto(self.config['search_url'])
            
            # Fill and submit form
            await self._fill_form(search_params)
            await self._submit_form()
            
            # Extract results
            return await self._extract_results()
            
        except Exception as e:
            self.logger.error(f"Error in form crawler: {e}")
            return []

class PersianAirlineCrawler(BaseSiteCrawler):
    """Specialized crawler for Persian airlines"""
    
    async def crawl(self, search_params: dict) -> list:
        await self.rate_limiter.wait()
        
        try:
            # Convert dates to Jalali if needed
            if self.config.get('use_jalali_calendar', True):
                search_params = self._convert_dates_to_jalali(search_params)
            
            # Perform crawl
            results = await self._perform_crawl(search_params)
            
            # Process Persian text
            return self._process_persian_results(results)
            
        except Exception as e:
            self.logger.error(f"Error in Persian airline crawler: {e}")
            return []

class InternationalAggregatorCrawler(BaseSiteCrawler):
    """Crawler for international flight aggregators"""
    
    async def crawl(self, search_params: dict) -> list:
        await self.rate_limiter.wait()
        
        try:
            # Check for API access
            if self.config.get('api_access'):
                return await self._crawl_via_api(search_params)
            
            # Fall back to browser automation
            return await self._crawl_with_browser(search_params)
            
        except Exception as e:
            self.logger.error(f"Error in international aggregator crawler: {e}")
            return []

class SiteCrawlerFactory:
    """Factory for creating appropriate crawler instances"""
    
    @staticmethod
    def create_crawler(site_config: dict) -> BaseSiteCrawler:
        """Create crawler instance based on site configuration"""
        crawler_type = site_config.get('crawler_type', 'default')
        
        if crawler_type == 'javascript_heavy':
            return JavaScriptCrawler(site_config)
        elif crawler_type == 'api_based':
            return APICrawler(site_config)
        elif crawler_type == 'form_submission':
            return FormCrawler(site_config)
        elif crawler_type == 'persian_airline':
            return PersianAirlineCrawler(site_config)
        elif crawler_type == 'international_aggregator':
            return InternationalAggregatorCrawler(site_config)
        else:
            return JavaScriptCrawler(site_config)  # Default to JavaScript crawler 