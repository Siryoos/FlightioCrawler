import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import redis
import psycopg2
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from hazm import Normalizer
from persian_tools import digits
import jdatetime
# Add these imports at the top
from monitoring import CrawlerMonitor, ErrorHandler
from data_manager import FlightDataManager, DataManager
from site_crawlers import FlytodayCrawler, AlibabaCrawler, SafarmarketCrawler
from crawl4ai.cache_mode import CacheMode  # Missing import
from rate_limiter import RateLimiter
from persian_text import PersianTextProcessor
from config import config

class IranianFlightCrawler:
    """Main crawler class for Iranian flight booking sites"""
    
    def __init__(
        self,
        monitor: CrawlerMonitor,
        error_handler: ErrorHandler,
        data_manager: DataManager
    ):
        self.monitor = monitor
        self.error_handler = error_handler
        self.data_manager = data_manager
        
        # Initialize components
        self.rate_limiter = RateLimiter(monitor.redis)
        self.text_processor = PersianTextProcessor()
        
        # Initialize site crawlers
        self.crawlers = {
            "flytoday.ir": FlytodayCrawler(
                self.rate_limiter,
                self.text_processor,
                self.monitor,
                self.error_handler
            ),
            "alibaba.ir": AlibabaCrawler(
                self.rate_limiter,
                self.text_processor,
                self.monitor,
                self.error_handler
            ),
            "safarmarket.com": SafarmarketCrawler(
                self.rate_limiter,
                self.text_processor,
                self.monitor,
                self.error_handler
            )
        }
    
    async def crawl_all_sites(self, search_params: Dict) -> List[Dict]:
        """Crawl all sites for flights"""
        try:
            # Check cache first
            search_key = self._generate_search_key(search_params)
            cached_results = await self.data_manager.get_cached_search(search_key)
            
            if cached_results:
                logger.info(f"Returning cached results for {search_key}")
                return cached_results
            
            # Start time for response time calculation
            start_time = datetime.now()
            
            # Crawl all sites concurrently
            tasks = [
                self._crawl_site(domain, crawler, search_params)
                for domain, crawler in self.crawlers.items()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            flights = []
            for domain, result in zip(self.crawlers.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"Error crawling {domain}: {result}")
                    continue
                
                flights.extend(result)
            
            # Store results
            if flights:
                await self.data_manager.store_flights(flights)
                
                # Cache results
                await self.data_manager.cache_search_results(
                    search_key,
                    flights,
                    config.CRAWLER.CACHE_TTL
                )
            
            # Store search query
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            await self.data_manager.store_search_query(
                search_params,
                len(flights),
                int(response_time)
            )
            
            return flights
            
        except Exception as e:
            logger.error(f"Error crawling sites: {e}")
            return []
    
    async def _crawl_site(
        self,
        domain: str,
        crawler: BaseSiteCrawler,
        search_params: Dict
    ) -> List[Dict]:
        """Crawl a single site"""
        try:
            # Check if we can make request
            if not await self.error_handler.can_make_request(domain):
                logger.warning(f"Circuit breaker open for {domain}")
                return []
            
            # Check rate limit
            if not await self.rate_limiter.check_rate_limit(domain):
                wait_time = await self.rate_limiter.get_wait_time(domain)
                if wait_time:
                    logger.info(f"Rate limit reached for {domain}, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
            
            # Crawl site
            flights = await crawler.search_flights(search_params)
            
            # Add domain to flights
            for flight in flights:
                flight["domain"] = domain
            
            return flights
            
        except Exception as e:
            logger.error(f"Error crawling {domain}: {e}")
            await self.error_handler.handle_error(domain, e)
            return []
    
    def _generate_search_key(self, search_params: Dict) -> str:
        """Generate cache key for search"""
        return f"{search_params['origin']}_{search_params['destination']}_{search_params['departure_date']}"
    
    async def get_health_status(self) -> Dict:
        """Get crawler health status"""
        try:
            # Get metrics
            metrics = await self.monitor.get_all_metrics()
            
            # Get error stats
            error_stats = await self.error_handler.get_all_error_stats()
            
            # Get rate limit stats
            rate_limit_stats = await self.rate_limiter.get_all_rate_limit_stats()
            
            # Calculate overall status
            status = "healthy"
            for domain, stats in error_stats.items():
                if stats.get("circuit_open"):
                    status = "degraded"
                    break
            
            return {
                "status": status,
                "domains": {
                    domain: {
                        "metrics": metrics.get(domain, {}),
                        "errors": error_stats.get(domain, {}),
                        "rate_limit": rate_limit_stats.get(domain, {})
                    }
                    for domain in config.CRAWLER.DOMAINS
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

@dataclass
class FlightData:
    """Normalized flight data structure"""
    flight_id: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    price: float
    currency: str
    seat_class: str
    aircraft_type: Optional[str]
    duration_minutes: int
    flight_type: str  # domestic/international
    scraped_at: datetime
    source_url: str

class IranianFlightCrawler:
    """Main crawler orchestrator for Iranian flight booking sites"""
    
    def __init__(self):
        self.setup_logging()
        self.setup_persian_processing()
        self.setup_database()
        self.setup_redis()
        self.setup_crawl4ai()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('flight_crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_persian_processing(self):
        """Initialize Persian text processing tools"""
        self.normalizer = Normalizer()
        
    def setup_database(self):
        """Initialize PostgreSQL connection with UTF-8 support"""
        self.db_config = {
            'host': 'localhost',
            'database': 'flight_data',
            'user': 'crawler',
            'password': 'secure_password',
            'options': '-c timezone=Asia/Tehran'
        }
        self.init_database_schema()
        
    def setup_redis(self):
        """Initialize Redis for task queue and caching"""
        self.redis_client = redis.Redis(
            host='localhost', 
            port=6379, 
            db=0,
            decode_responses=True
        )
        
    def setup_crawl4ai(self):
        """Configure Crawl4AI for Iranian sites"""
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            extra_headers={
                "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            use_persistent_context=True,
            user_data_dir="/tmp/crawl4ai_persian_profile"
        )
        
        self.run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            timeout=30000,
            wait_for_timeout=15000,
            js_only=False,
            screenshot=False,
            verbose=False
        )
    
    def init_database_schema(self):
        """Create database tables with Persian text support"""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS flights (
            id BIGSERIAL PRIMARY KEY,
            flight_id VARCHAR(100) UNIQUE,
            airline VARCHAR(100),
            flight_number VARCHAR(20),
            origin VARCHAR(10),
            destination VARCHAR(10),
            departure_time TIMESTAMPTZ,
            arrival_time TIMESTAMPTZ,
            price DECIMAL(12,2),
            currency VARCHAR(3),
            seat_class VARCHAR(50),
            aircraft_type VARCHAR(50),
            duration_minutes INTEGER,
            flight_type VARCHAR(20),
            scraped_at TIMESTAMPTZ DEFAULT NOW(),
            source_url TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_flights_route_date 
        ON flights (origin, destination, departure_time);
        
        CREATE INDEX IF NOT EXISTS idx_flights_scraped 
        ON flights (scraped_at);
        """
        
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                conn.commit()

    async def crawl_all_sites(self, search_params: Dict):
        """Orchestrate crawling across all three sites"""
        sites = {
            'flytoday': FlytodayCrawler(self),
            'alibaba': AlibabaCrawler(self), 
            'safarmarket': SafarmarketCrawler(self)
        }
        
        tasks = []
        for site_name, crawler in sites.items():
            task = asyncio.create_task(
                crawler.search_flights(search_params),
                name=f"crawl_{site_name}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process and store results
        all_flights = []
        for site_name, result in zip(sites.keys(), results):
            if isinstance(result, Exception):
                self.logger.error(f"Error crawling {site_name}: {result}")
            else:
                all_flights.extend(result)
        
        await self.store_flights(all_flights)
        return all_flights 