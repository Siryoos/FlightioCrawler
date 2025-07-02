import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import redis
import psycopg2
from local_crawler import BrowserConfig, CrawlerRunConfig
from hazm import Normalizer
from persian_tools import digits
import jdatetime
from monitoring import CrawlerMonitor, ErrorHandler
from data_manager import DataManager

# Use AdapterFactory instead of manual imports
from adapters.factories.adapter_factory import AdapterFactory

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
    """Main crawler orchestrator using AdapterFactory for all flight booking sites"""

    def __init__(self, max_concurrent_crawls: int = 5) -> None:
        # Initialize core components
        self.monitor: CrawlerMonitor = CrawlerMonitor()
        self.error_handler: ErrorHandler = ErrorHandler()
        self.data_manager: DataManager = DataManager()
        self.rate_limiter: RateLimiter = RateLimiter()
        self.text_processor: PersianTextProcessor = PersianTextProcessor()

        # Initialize adapter factory
        self.adapter_factory: AdapterFactory = AdapterFactory()

        # Initialize advanced features
        self.intelligent_search: IntelligentSearchEngine = IntelligentSearchEngine(
            self, self.data_manager
        )
        self.price_monitor: PriceMonitor = PriceMonitor(
            self.data_manager, self.data_manager.redis
        )
        self.price_monitor.websocket_manager = WebSocketManager()
        self.ml_predictor: FlightPricePredictor = FlightPricePredictor(
            self.data_manager, self.data_manager.redis
        )
        self.multilingual: MultilingualProcessor = MultilingualProcessor()

        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_crawls)
        self.active_tasks: Set[asyncio.Task] = set()

        # Initialize adapters using factory
        self.adapters: Dict[str, Any] = self._initialize_adapters()

        # Track which sites are currently enabled for crawling
        self.enabled_sites: Set[str] = set(self.adapters.keys())

        logger.info(f"Flight Crawler initialized with {len(self.adapters)} adapters")

    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all adapters using AdapterFactory with their configurations."""
        adapters: Dict[str, Any] = {}

        # Get default configurations for each adapter
        adapter_configs = {
            "alibaba": self._get_adapter_config("alibaba"),
            "flightio": self._get_adapter_config("flightio"),
            "flytoday": self._get_adapter_config("flytoday"),
            "iran_air": self._get_adapter_config("iran_air"),
            "mahan_air": self._get_adapter_config("mahan_air"),
            "lufthansa": self._get_adapter_config("lufthansa"),
            "air_france": self._get_adapter_config("air_france"),
            "british_airways": self._get_adapter_config("british_airways"),
            "emirates": self._get_adapter_config("emirates"),
            "turkish_airlines": self._get_adapter_config("turkish_airlines"),
            "qatar_airways": self._get_adapter_config("qatar_airways"),
        }

        # Create adapters using factory
        for adapter_name, config in adapter_configs.items():
            try:
                adapter = self.adapter_factory.create_adapter(adapter_name, config)
                adapters[adapter_name] = adapter
                logger.info(f"✅ Initialized {adapter_name} adapter")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {adapter_name} adapter: {e}")

        return adapters

    def _get_adapter_config(self, adapter_name: str) -> Dict[str, Any]:
        """Get configuration for a specific adapter."""
        base_config: Dict[str, Any] = {
            "rate_limiting": {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60,
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 5,
                "circuit_breaker": {"failure_threshold": 5, "timeout": 300},
            },
            "monitoring": {"enabled": True, "log_level": "INFO"},
            "extraction_config": self._get_extraction_config(adapter_name),
            "data_validation": {
                "required_fields": [
                    "airline",
                    "flight_number",
                    "price",
                    "departure_time",
                ],
                "price_range": {"min": 0, "max": 50000000},  # IRR
            },
        }

        # Load adapter-specific configs if available
        try:
            if adapter_name in config.get("site_configs", {}):
                adapter_config = config["site_configs"][adapter_name]
                base_config.update(adapter_config)
        except Exception as e:
            logger.warning(f"Could not load config for {adapter_name}: {e}")

        return base_config

    def _get_extraction_config(self, adapter_name: str) -> Dict[str, Any]:
        """Get extraction configuration for adapter."""
        # Default extraction config - این باید از config files واقعی لود شود
        return {
            "search_form": {
                "origin_field": "[name='origin']",
                "destination_field": "[name='destination']",
                "departure_date_field": "[name='departure_date']",
                "passengers_field": "[name='passengers']",
                "class_field": "[name='seat_class']",
            },
            "results_parsing": {
                "container": ".flight-result",
                "airline": ".airline-name",
                "flight_number": ".flight-number",
                "departure_time": ".departure-time",
                "arrival_time": ".arrival-time",
                "duration": ".duration",
                "price": ".price",
                "seat_class": ".seat-class",
            },
        }

    async def crawl_all_sites(
        self, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Orchestrate crawling across all three sites"""
        try:
            # Ensure required parameters have defaults
            search_params.setdefault("passengers", 1)
            search_params.setdefault("seat_class", "economy")

            # Check cache first
            cached_results = self.data_manager.get_cached_results(search_params)
            if cached_results:
                logger.info("Returning cached results")
                return cached_results

            # Start crawling all enabled sites concurrently
            tasks = []
            for site_name, adapter in self.adapters.items():
                if site_name not in self.enabled_sites:
                    continue
                task = asyncio.create_task(
                    self._crawl_site_safely(site_name, adapter, search_params),
                    name=f"crawl_{site_name}",
                )
                tasks.append(task)
                self.active_tasks.add(task)
                task.add_done_callback(self.active_tasks.discard)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            all_flights: List[Dict[str, Any]] = []
            for i, result in enumerate(results):
                site_name = list(self.adapters.keys())[i]
                if isinstance(result, Exception):
                    logger.error(f"Error crawling {site_name}: {result}")
                elif isinstance(result, list):
                    all_flights.extend(result)
                    logger.info(f"✅ {site_name}: {len(result)} flights")

            # Store results in cache
            await self.data_manager.cache_search_results(
                search_params,
                {"flights": all_flights, "timestamp": datetime.now().isoformat()},
            )

            # Store individual flights in database
            if all_flights:
                await self.data_manager.store_flights({"all_sites": all_flights})

            logger.info(f"Total flights found: {len(all_flights)}")
            return all_flights

        except Exception as e:
            logger.error(f"Error in crawl_all_sites: {e}")
            await self.error_handler.handle_error("crawler", str(e))
            return []

    async def _crawl_site_safely(
        self, site_name: str, adapter: Any, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Safely crawl a single site with error handling"""
        try:
            async with self.semaphore:
                async with adapter:
                    await self.rate_limiter.wait_for_token(site_name)
                    logger.info(f"Starting crawl for {site_name}")
                    flights = await adapter.crawl(search_params)
                    self.monitor.log_success(site_name, len(flights))
                    return flights

        except Exception as e:
            logger.error(f"Error crawling {site_name}: {e}")
            self.error_handler.record_failure(site_name)
            await self.error_handler.handle_error(site_name, str(e))
            return []

    async def shutdown(self):
        """Gracefully cancel all active crawling tasks."""
        if not self.active_tasks:
            return

        logger.info(f"Cancelling {len(self.active_tasks)} active tasks...")
        for task in list(self.active_tasks):
            task.cancel()

        await asyncio.gather(*self.active_tasks, return_exceptions=True)
        self.active_tasks.clear()
        logger.info("All active tasks have been cancelled.")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the crawler and its components"""
        return {
            "status": "healthy",
            "enabled_sites": list(self.enabled_sites),
            "monitor": self.monitor.get_health_status(),
            "error_handler": self.error_handler.get_all_error_stats(),
            "timestamp": datetime.now().isoformat(),
        }

    async def intelligent_search_flights(
        self, search_params: Dict[str, Any], optimization: SearchOptimization
    ) -> Dict[str, Any]:
        """Perform intelligent search with optimization"""
        return await self.intelligent_search.search_with_optimization(
            search_params, optimization
        )

    def _generate_search_key(self, search_params: Dict[str, Any]) -> str:
        """Generate unique key for search parameters"""
        return f"{search_params['origin']}-{search_params['destination']}-{search_params['departure_date']}"

    async def crawl_site(
        self, site_name: str, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Crawl a single site by name"""
        if site_name not in self.adapters:
            raise ValueError(f"Adapter '{site_name}' not found.")
        adapter = self.adapters[site_name]
        # Use the safe crawl method to handle errors and circuit breaking
        return await self._crawl_site_safely(site_name, adapter, search_params)

    def enable_site(self, site_name: str) -> bool:
        """Enable crawling for a site."""
        if site_name in self.adapters:
            self.enabled_sites.add(site_name)
            return True
        return False

    def disable_site(self, site_name: str) -> bool:
        """Disable crawling for a site."""
        if site_name in self.enabled_sites:
            self.enabled_sites.remove(site_name)
            return True
        return False

    def get_available_adapters(self) -> List[str]:
        """Get list of all available adapter names."""
        return self.adapter_factory.list_available_adapters()

    def get_adapter_info(self, adapter_name: str) -> Dict[str, Any]:
        """Get information about a specific adapter."""
        return self.adapter_factory.get_adapter_info(adapter_name)

    def reset_stats(self) -> None:
        """Reset monitoring metrics, error states and rate limits."""
        try:
            self.monitor.reset_all_metrics()
            self.error_handler.reset_all_circuits()
            self.rate_limiter.clear_rate_limits()
            if hasattr(self.data_manager, "redis") and self.data_manager.redis:
                self.data_manager.redis.flushdb()
        except Exception as e:
            logger.error(f"Error resetting stats: {e}")

    def setup_logging(self) -> None:
        """Configure comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            handlers=[
                logging.FileHandler("crawler.log", encoding="utf-8"),
                logging.FileHandler(
                    "crawler_errors.log", level=logging.ERROR, encoding="utf-8"
                ),
                logging.StreamHandler(),
            ],
        )

        # Set specific logger levels
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("selenium").setLevel(logging.WARNING)

        # Persian text processing logger
        logging.getLogger("hazm").setLevel(logging.WARNING)
        logging.getLogger("persian_tools").setLevel(logging.WARNING)

        logger.info("Logging configured successfully")

    def setup_persian_processing(self) -> None:
        """Initialize Persian text processing components"""
        self.normalizer = Normalizer()
        logger.info("Persian text processing initialized")

    def setup_database(self) -> None:
        """Initialize database connection and create tables"""
        try:
            # Database setup is handled by DataManager
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def setup_redis(self) -> None:
        """Initialize Redis connection for caching"""
        try:
            # Redis setup is handled by DataManager
            logger.info("Redis initialized successfully")
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")

    def setup_crawl4ai(self) -> None:
        """Setup crawl4ai configuration"""
        try:
            # Import crawl4ai components
            from crawl4ai import AsyncWebCrawler as Crawl4aiCrawler
            from crawl4ai.extraction_strategy import LLMExtractionStrategy

            # Configure extraction strategy for flight data
            extraction_schema = {
                "type": "object",
                "properties": {
                    "flights": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "airline": {"type": "string"},
                                "flight_number": {"type": "string"},
                                "departure_time": {"type": "string"},
                                "arrival_time": {"type": "string"},
                                "price": {"type": "number"},
                                "currency": {"type": "string"},
                                "origin": {"type": "string"},
                                "destination": {"type": "string"},
                            },
                        },
                    }
                },
            }

            self.extraction_strategy = LLMExtractionStrategy(
                provider="ollama/llama2",
                schema=extraction_schema,
                extraction_type="schema",
                instruction="Extract flight information from the page",
            )

            logger.info("Crawl4AI configured successfully")

        except ImportError:
            logger.warning("Crawl4AI not available, using fallback extraction")
            self.extraction_strategy = None

    def init_database_schema(self) -> None:
        """Initialize database schema"""
        try:
            # Schema initialization is handled by DataManager
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Database schema initialization failed: {e}")
            raise
