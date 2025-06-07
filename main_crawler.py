import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import redis
import psycopg2
from local_crawler import BrowserConfig, CrawlerRunConfig
from hazm import Normalizer
from persian_tools import digits
import jdatetime
from monitoring import CrawlerMonitor, ErrorHandler
from data_manager import DataManager
from site_crawlers import (
    FlytodayCrawler,
    AlibabaCrawler,
    SafarmarketCrawler,
    Mz724Crawler,
    PartoCRSCrawler,
    PartoTicketCrawler,
    BookCharter724Crawler,
    BookCharterCrawler,
)
try:
    from crawl4ai.cache_mode import CacheMode
except Exception:  # pragma: no cover - optional dependency
    from enum import Enum

    class CacheMode(Enum):
        BYPASS = 0
from rate_limiter import RateLimiter
from persian_text import PersianTextProcessor
from config import config
from intelligent_search import IntelligentSearchEngine, SearchOptimization
from price_monitor import PriceMonitor, WebSocketManager
from ml_predictor import FlightPricePredictor
from multilingual_processor import MultilingualProcessor

logger = logging.getLogger(__name__)

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
    flight_type: str
    scraped_at: datetime
    source_url: str

class IranianFlightCrawler:
    """Main crawler orchestrator for Iranian flight booking sites"""
    
    def __init__(self):
        # Initialize core components
        self.monitor = CrawlerMonitor()
        self.error_handler = ErrorHandler()
        self.data_manager = DataManager()
        self.rate_limiter = RateLimiter()
        self.text_processor = PersianTextProcessor()
        
        # Initialize advanced features
        self.intelligent_search = IntelligentSearchEngine(self, self.data_manager)
        self.price_monitor = PriceMonitor(self.data_manager, self.data_manager.redis)
        self.price_monitor.websocket_manager = WebSocketManager()
        self.ml_predictor = FlightPricePredictor(self.data_manager, self.data_manager.redis)
        self.multilingual = MultilingualProcessor()
        
        # Initialize site crawlers
        self.crawlers = {
            "flytoday.ir": FlytodayCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "alibaba.ir": AlibabaCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "safarmarket.com": SafarmarketCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "mz724.ir": Mz724Crawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "partocrs.com": PartoCRSCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "parto-ticket.ir": PartoTicketCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "bookcharter724.ir": BookCharter724Crawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            ),
            "bookcharter.ir": BookCharterCrawler(
                self.rate_limiter, self.text_processor,
                self.monitor, self.error_handler
            )
        }
        
        logger.info("Iranian Flight Crawler initialized successfully")
    
    async def crawl_all_sites(self, search_params: Dict) -> List[Dict]:
        """Orchestrate crawling across all three sites"""
        try:
            # Check cache first
            cached_results = self.data_manager.get_cached_results(search_params)
            if cached_results:
                logger.info("Returning cached results")
                return cached_results
            
            # Start crawling all sites concurrently
            tasks = []
            for site_name, crawler in self.crawlers.items():
                task = asyncio.create_task(
                    self._crawl_site_safely(site_name, crawler, search_params),
                    name=f"crawl_{site_name}"
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            all_flights = []
            for site_name, result in zip(self.crawlers.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"Error crawling {site_name}: {result}")
                    continue
                all_flights.extend(result)
            
            # Store results
            if all_flights:
                await self.data_manager.store_flights({"all": all_flights})
                await self.data_manager.cache_search_results(search_params, {"all": all_flights})
            
            return all_flights
            
        except Exception as e:
            logger.error(f"Error in crawl_all_sites: {e}")
            return []
    
    async def _crawl_site_safely(self, site_name: str, crawler, search_params: Dict) -> List[Dict]:
        """Safely crawl a single site with error handling"""
        try:
            if self.error_handler.is_circuit_open(site_name):
                logger.warning(f"Circuit breaker open for {site_name}")
                return []
            
            start_time = datetime.now()
            flights = await crawler.search_flights(search_params)
            
            # Record metrics
            duration = (datetime.now() - start_time).total_seconds()
            self.monitor.record_request(site_name, duration)
            self.monitor.record_flights(site_name, len(flights))
            
            return flights
            
        except Exception as e:
            logger.error(f"Error crawling {site_name}: {e}")
            await self.error_handler.handle_error(site_name, str(e))
            return []
    

    
    def get_health_status(self) -> Dict:
        """Get comprehensive crawler health status"""
        return {
            "crawler_metrics": self.monitor.get_all_metrics(),
            "error_stats": self.error_handler.get_all_error_stats(),
            "rate_limits": self.rate_limiter.get_all_rate_limit_stats(),
            "timestamp": datetime.now().isoformat()
        }


    async def intelligent_search_flights(self, search_params: Dict, optimization: SearchOptimization) -> Dict:
        """Run intelligent search using the optimization engine."""
        return await self.intelligent_search.optimize_search_strategy(search_params, optimization)

    def _generate_search_key(self, search_params: Dict) -> str:
        """Generate cache key for search"""
        return f"{search_params['origin']}_{search_params['destination']}_{search_params['departure_date']}"

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
