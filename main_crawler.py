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