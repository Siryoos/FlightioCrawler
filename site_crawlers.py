import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from crawl4ai import AsyncCrawler
from persian_text import PersianTextProcessor

class BaseSiteCrawler:
    """Base class for site-specific crawlers"""
    
    def __init__(self, rate_limiter, text_processor: PersianTextProcessor):
        self.rate_limiter = rate_limiter
        self.text_processor = text_processor
        self.crawler = AsyncCrawler()
    
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
        raise NotImplementedError

class FlytodayCrawler(BaseSiteCrawler):
    """Crawler for Flytoday.ir"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "flytoday.ir"
        self.base_url = "https://www.flytoday.ir"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Flytoday"""
        if not await self.check_rate_limit():
            wait_time = await self.get_wait_time()
            if wait_time:
                await asyncio.sleep(wait_time)
        
        # Implement Flytoday-specific crawling logic
        # This is a placeholder - actual implementation would use the site's structure
        search_url = f"{self.base_url}/search"
        params = {
            "origin": search_params["origin"],
            "destination": search_params["destination"],
            "departure_date": search_params["departure_date"],
            "passengers": search_params["passengers"],
            "class": search_params["seat_class"]
        }
        
        try:
            response = await self.crawler.get(search_url, params=params)
            # Parse response and extract flight data
            # This is where you'd implement the actual parsing logic
            return []
        except Exception as e:
            print(f"Error crawling Flytoday: {e}")
            return []

class AlibabaCrawler(BaseSiteCrawler):
    """Crawler for Alibaba.ir"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "alibaba.ir"
        self.base_url = "https://www.alibaba.ir"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Alibaba"""
        if not await self.check_rate_limit():
            wait_time = await self.get_wait_time()
            if wait_time:
                await asyncio.sleep(wait_time)
        
        # Implement Alibaba-specific crawling logic
        search_url = f"{self.base_url}/flight/search"
        params = {
            "origin": search_params["origin"],
            "destination": search_params["destination"],
            "departure_date": search_params["departure_date"],
            "adult": search_params["passengers"],
            "cabin_class": search_params["seat_class"]
        }
        
        try:
            response = await self.crawler.get(search_url, params=params)
            # Parse response and extract flight data
            return []
        except Exception as e:
            print(f"Error crawling Alibaba: {e}")
            return []

class SafarmarketCrawler(BaseSiteCrawler):
    """Crawler for Safarmarket.com"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = "safarmarket.com"
        self.base_url = "https://www.safarmarket.com"
    
    async def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search flights on Safarmarket"""
        if not await self.check_rate_limit():
            wait_time = await self.get_wait_time()
            if wait_time:
                await asyncio.sleep(wait_time)
        
        # Implement Safarmarket-specific crawling logic
        search_url = f"{self.base_url}/flight/search"
        params = {
            "from": search_params["origin"],
            "to": search_params["destination"],
            "date": search_params["departure_date"],
            "passengers": search_params["passengers"],
            "class": search_params["seat_class"]
        }
        
        try:
            response = await self.crawler.get(search_url, params=params)
            # Parse response and extract flight data
            return []
        except Exception as e:
            print(f"Error crawling Safarmarket: {e}")
            return [] 