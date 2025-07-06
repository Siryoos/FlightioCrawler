import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import redis
import psycopg2
import uuid
from local_crawler import BrowserConfig, CrawlerRunConfig
from hazm import Normalizer
from persian_tools import digits
import jdatetime
from monitoring import CrawlerMonitor
from monitoring.production_memory_monitor import ProductionMemoryMonitor
from monitoring.memory_health_endpoint import MemoryHealthServer
from data_manager import DataManager

# Use unified factory instead of manual imports
from adapters.factories.unified_adapter_factory import get_unified_factory

# Enhanced Error Handler Integration
from adapters.base_adapters.enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    error_handler_decorator,
    get_global_error_handler
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
from utils.request_batcher import RequestBatcher, RequestSpec

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
    """Enhanced main crawler orchestrator with comprehensive error handling and monitoring"""

    def __init__(self, http_session: Optional[Any] = None, max_concurrent_crawls: int = 5, enable_memory_monitoring: bool = True) -> None:
        # Initialize core components
        self.monitor: CrawlerMonitor = CrawlerMonitor()
        self.error_handler: EnhancedErrorHandler = get_global_error_handler()
        self.data_manager: DataManager = DataManager()
        self.rate_limiter: RateLimiter = RateLimiter()
        self.text_processor: PersianTextProcessor = PersianTextProcessor()
        self.http_session = http_session
        
        # Crawler identification and session management
        self.crawler_id = str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self.current_operation = None

        # Initialize unified adapter factory
        self.adapter_factory = get_unified_factory()

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

        # Request batching for optimization
        self.request_batcher: Optional[RequestBatcher] = None

        # Memory monitoring for production
        self.memory_monitor: Optional[ProductionMemoryMonitor] = None
        self.memory_health_server: Optional[MemoryHealthServer] = None
        self.enable_memory_monitoring = enable_memory_monitoring
        
        # Crawler statistics and monitoring
        self.crawler_stats = {
            "total_crawls": 0,
            "successful_crawls": 0,
            "failed_crawls": 0,
            "crawls_by_site": {},
            "average_crawl_time": 0,
            "last_crawl_time": None,
            "uptime_start": datetime.now()
        }
        
        if self.enable_memory_monitoring:
            self._setup_memory_monitoring()

        logger.info(f"Enhanced Flight Crawler initialized with {len(self.adapters)} adapters (ID: {self.crawler_id})")

    def _create_error_context(
        self, 
        operation: str, 
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """Create error context for current operation"""
        context = ErrorContext(
            adapter_name="main_crawler",
            operation=operation,
            session_id=self.session_id,
            additional_info={
                "crawler_id": self.crawler_id,
                "enabled_sites": list(self.enabled_sites),
                "active_tasks": len(self.active_tasks),
                "current_operation": self.current_operation,
                **(additional_info or {})
            }
        )
        return context

    @error_handler_decorator(
        operation_name="initialize_adapters",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all adapters using AdapterFactory with enhanced error handling."""
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

        # Create adapters using factory with enhanced error handling
        for adapter_name, config in adapter_configs.items():
            try:
                adapter = self.adapter_factory.create_adapter(adapter_name, config)
                adapters[adapter_name] = adapter
                logger.info(f"✅ Initialized {adapter_name} adapter")
                
            except Exception as e:
                error_context = self._create_error_context(
                    "initialize_single_adapter",
                    {
                        "adapter_name": adapter_name,
                        "config_keys": list(config.keys()),
                        "total_adapters": len(adapter_configs),
                        "initialized_adapters": len(adapters)
                    }
                )
                
                # Report adapter initialization error (non-blocking)
                asyncio.create_task(self.error_handler.handle_error(
                    e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
                ))
                
                logger.error(f"❌ Failed to initialize {adapter_name} adapter: {e}")

        if not adapters:
            raise RuntimeError("No adapters could be initialized")

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
            "name": adapter_name,
            "session_id": self.session_id
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

    def _setup_memory_monitoring(self) -> None:
        """Set up memory monitoring for production use"""
        try:
            # Initialize memory monitor
            self.memory_monitor = ProductionMemoryMonitor(
                threshold_percent=85, check_interval=30
            )

            # Initialize memory health server
            self.memory_health_server = MemoryHealthServer(host="0.0.0.0", port=8081)

            logger.info("Memory monitoring initialized")

        except Exception as e:
            error_context = self._create_error_context(
                "setup_memory_monitoring",
                {"monitoring_enabled": self.enable_memory_monitoring}
            )
            
            # Report memory monitoring setup error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.warning(f"Failed to setup memory monitoring: {e}")

    async def start_memory_monitoring(self) -> None:
        """Start memory monitoring services"""
        try:
            if self.memory_monitor:
                await self.memory_monitor.start()
            if self.memory_health_server:
                await self.memory_health_server.start()
            logger.info("Memory monitoring started")
        except Exception as e:
            logger.error(f"Failed to start memory monitoring: {e}")

    async def stop_memory_monitoring(self) -> None:
        """Stop memory monitoring services"""
        try:
            if self.memory_monitor:
                await self.memory_monitor.stop()
            if self.memory_health_server:
                await self.memory_health_server.stop()
            logger.info("Memory monitoring stopped")
        except Exception as e:
            logger.error(f"Failed to stop memory monitoring: {e}")

    def get_memory_status(self) -> Dict[str, Any]:
        """Get current memory status"""
        if self.memory_monitor:
            return self.memory_monitor.get_status()
        return {"status": "not_available", "reason": "memory monitoring disabled"}

    @error_handler_decorator(
        operation_name="crawl_all_sites",
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.HIGH,
        max_retries=2
    )
    async def crawl_all_sites(
        self, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Orchestrate crawling across all sites with comprehensive error handling"""
        crawl_start_time = datetime.now()
        self.current_operation = "crawl_all_sites"
        
        # Update statistics
        self.crawler_stats["total_crawls"] += 1
        self.crawler_stats["last_crawl_time"] = crawl_start_time
        
        try:
            # Create error context for this crawl operation
            error_context = self._create_error_context(
                "crawl_all_sites",
                {
                    "search_params": search_params,
                    "enabled_sites_count": len(self.enabled_sites),
                    "crawl_start_time": crawl_start_time.isoformat()
                }
            )

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

            if not tasks:
                raise ValueError("No enabled sites available for crawling")

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with enhanced error tracking
            all_flights: List[Dict[str, Any]] = []
            successful_sites = 0
            failed_sites = 0
            
            for i, result in enumerate(results):
                site_name = list(self.adapters.keys())[i]
                
                # Update site-specific statistics
                if site_name not in self.crawler_stats["crawls_by_site"]:
                    self.crawler_stats["crawls_by_site"][site_name] = {
                        "total": 0, "successful": 0, "failed": 0
                    }
                
                self.crawler_stats["crawls_by_site"][site_name]["total"] += 1
                
                if isinstance(result, Exception):
                    failed_sites += 1
                    self.crawler_stats["crawls_by_site"][site_name]["failed"] += 1
                    
                    # Create specific error context for site failure
                    site_error_context = self._create_error_context(
                        "site_crawl_failed",
                        {
                            "site_name": site_name,
                            "error_type": type(result).__name__,
                            "error_message": str(result),
                            "crawl_duration": (datetime.now() - crawl_start_time).total_seconds()
                        }
                    )
                    
                    # Report site-specific error (non-blocking)
                    asyncio.create_task(self.error_handler.handle_error(
                        result, site_error_context, ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN
                    ))
                    
                    logger.error(f"Error crawling {site_name}: {result}")
                    
                elif isinstance(result, list):
                    successful_sites += 1
                    self.crawler_stats["crawls_by_site"][site_name]["successful"] += 1
                    all_flights.extend(result)
                    logger.info(f"✅ {site_name}: {len(result)} flights")

            # Update overall statistics
            crawl_duration = (datetime.now() - crawl_start_time).total_seconds()
            if successful_sites > 0:
                self.crawler_stats["successful_crawls"] += 1
            if failed_sites == len(tasks):  # All sites failed
                self.crawler_stats["failed_crawls"] += 1
                
            # Update average crawl time
            if self.crawler_stats["successful_crawls"] > 0:
                current_avg = self.crawler_stats["average_crawl_time"]
                total_successful = self.crawler_stats["successful_crawls"]
                self.crawler_stats["average_crawl_time"] = (
                    (current_avg * (total_successful - 1) + crawl_duration) / total_successful
                )

            # Store results in cache
            await self.data_manager.cache_search_results(
                search_params,
                {"flights": all_flights, "timestamp": datetime.now().isoformat()},
            )

            # Store individual flights in database
            if all_flights:
                await self.data_manager.store_flights({"all_sites": all_flights})

            logger.info(
                f"Crawl completed in {crawl_duration:.2f}s: "
                f"{len(all_flights)} flights from {successful_sites}/{len(tasks)} sites"
            )
            
            return all_flights

        except Exception as e:
            # Update failure statistics
            self.crawler_stats["failed_crawls"] += 1
            crawl_duration = (datetime.now() - crawl_start_time).total_seconds()
            
            error_context = self._create_error_context(
                "crawl_all_sites_failure",
                {
                    "search_params": search_params,
                    "crawl_duration": crawl_duration,
                    "enabled_sites": list(self.enabled_sites),
                    "total_crawls": self.crawler_stats["total_crawls"]
                }
            )
            
            # Report crawler-level error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.UNKNOWN
            ))
            
            logger.error(f"Error in crawl_all_sites: {e}")
            return []
            
        finally:
            self.current_operation = None

    @error_handler_decorator(
        operation_name="crawl_site_safely",
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.MEDIUM,
        max_retries=3
    )
    async def _crawl_site_safely(
        self, site_name: str, adapter: Any, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Safely crawl a single site with comprehensive error handling and monitoring"""
        site_start_time = datetime.now()
        
        try:
            # Create error context for site crawling
            error_context = self._create_error_context(
                "crawl_single_site",
                {
                    "site_name": site_name,
                    "search_params": search_params,
                    "adapter_type": type(adapter).__name__,
                    "site_start_time": site_start_time.isoformat()
                }
            )

            async with self.semaphore:
                async with adapter:
                    await self.rate_limiter.wait_for_token(site_name)
                    logger.info(f"Starting crawl for {site_name}")
                    
                    # Execute crawl with timeout protection
                    flights = await asyncio.wait_for(
                        adapter.crawl(search_params),
                        timeout=300  # 5 minute timeout per site
                    )
                    
                    site_duration = (datetime.now() - site_start_time).total_seconds()
                    self.monitor.log_success(site_name, len(flights))
                    
                    logger.info(
                        f"✅ {site_name} completed in {site_duration:.2f}s: {len(flights)} flights"
                    )
                    
                    return flights

        except asyncio.TimeoutError as e:
            site_duration = (datetime.now() - site_start_time).total_seconds()
            
            error_context = self._create_error_context(
                "site_crawl_timeout",
                {
                    "site_name": site_name,
                    "timeout_duration": 300,
                    "actual_duration": site_duration,
                    "search_params": search_params
                }
            )
            
            # Report timeout error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.TIMEOUT
            ))
            
            logger.error(f"Timeout crawling {site_name} after {site_duration:.2f}s")
            return []
            
        except Exception as e:
            site_duration = (datetime.now() - site_start_time).total_seconds()
            
            error_context = self._create_error_context(
                "site_crawl_error",
                {
                    "site_name": site_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "crawl_duration": site_duration,
                    "search_params": search_params
                }
            )
            
            # Report site crawling error (non-blocking)
            should_retry, strategy = await self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN
            )
            
            self.monitor.record_error()
            
            if should_retry:
                logger.warning(f"Retrying {site_name} with strategy: {strategy}")
                raise  # Let decorator handle retry
            else:
                logger.error(f"Permanently failed to crawl {site_name}: {e}")
                return []

    async def shutdown(self):
        """Gracefully cancel all active crawling tasks with enhanced monitoring."""
        if not self.active_tasks:
            return

        shutdown_start = datetime.now()
        self.current_operation = "shutdown"
        
        try:
            logger.info(f"Cancelling {len(self.active_tasks)} active tasks...")
            
            # Cancel all active tasks
            for task in list(self.active_tasks):
                task.cancel()

            # Wait for all tasks to complete with timeout
            await asyncio.wait_for(
                asyncio.gather(*self.active_tasks, return_exceptions=True),
                timeout=30  # 30 second shutdown timeout
            )
            
            self.active_tasks.clear()
            
            # Stop memory monitoring
            if self.enable_memory_monitoring:
                await self.stop_memory_monitoring()
            
            shutdown_duration = (datetime.now() - shutdown_start).total_seconds()
            logger.info(f"Graceful shutdown completed in {shutdown_duration:.2f}s")
            
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout reached, forcing task termination")
            self.active_tasks.clear()
            
        except Exception as e:
            error_context = self._create_error_context(
                "crawler_shutdown_error",
                {
                    "active_tasks_count": len(self.active_tasks),
                    "shutdown_duration": (datetime.now() - shutdown_start).total_seconds()
                }
            )
            
            # Report shutdown error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error during shutdown: {e}")
            
        finally:
            self.current_operation = None

    def is_site_enabled(self, site_name: str) -> bool:
        """Check if a site is enabled for crawling."""
        return site_name in self.enabled_sites

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the crawler and its components"""
        try:
            uptime = (datetime.now() - self.crawler_stats["uptime_start"]).total_seconds()
            error_stats = self.error_handler.get_error_statistics()
            factory_health = self.adapter_factory.get_factory_health_status()
            
            return {
                "status": "healthy",
                "crawler_id": self.crawler_id,
                "session_id": self.session_id,
                "current_operation": self.current_operation,
                "uptime_seconds": uptime,
                "enabled_sites": list(self.enabled_sites),
                "available_adapters": len(self.adapters),
                "active_tasks": len(self.active_tasks),
                "crawler_statistics": self.crawler_stats,
                "monitor": self.monitor.get_health_status(),
                "error_handler": error_stats,
                "adapter_factory": factory_health,
                "memory_status": self.get_memory_status() if self.enable_memory_monitoring else None,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "crawler_id": self.crawler_id,
                "timestamp": datetime.now().isoformat()
            }

    async def intelligent_search_flights(
        self, search_params: Dict[str, Any], optimization: SearchOptimization
    ) -> Dict[str, Any]:
        """Perform intelligent search with optimization and error handling"""
        try:
            self.current_operation = "intelligent_search"
            result = await self.intelligent_search.search_with_optimization(
                search_params, optimization
            )
            return result
            
        except Exception as e:
            error_context = self._create_error_context(
                "intelligent_search_error",
                {
                    "search_params": search_params,
                    "optimization": str(optimization)
                }
            )
            
            # Report intelligent search error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN
            ))
            
            logger.error(f"Error in intelligent search: {e}")
            raise
            
        finally:
            self.current_operation = None

    def _generate_search_key(self, search_params: Dict[str, Any]) -> str:
        """Generate unique key for search parameters"""
        return f"{search_params['origin']}-{search_params['destination']}-{search_params['departure_date']}"

    async def crawl_site(
        self, site_name: str, search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Crawl a single site by name with enhanced error handling"""
        if site_name not in self.adapters:
            error_context = self._create_error_context(
                "adapter_not_found",
                {
                    "requested_site": site_name,
                    "available_sites": list(self.adapters.keys())
                }
            )
            
            error = ValueError(f"Adapter '{site_name}' not found.")
            
            # Report adapter not found error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                error, error_context, ErrorSeverity.MEDIUM, ErrorCategory.VALIDATION
            ))
            
            raise error
            
        adapter = self.adapters[site_name]
        # Use the safe crawl method to handle errors and circuit breaking
        return await self._crawl_site_safely(site_name, adapter, search_params)

    def enable_site(self, site_name: str) -> bool:
        """Enable crawling for a site with logging."""
        if site_name in self.adapters:
            self.enabled_sites.add(site_name)
            logger.info(f"Enabled crawling for site: {site_name}")
            return True
        else:
            logger.warning(f"Cannot enable unknown site: {site_name}")
            return False

    def disable_site(self, site_name: str) -> bool:
        """Disable crawling for a site with logging."""
        if site_name in self.enabled_sites:
            self.enabled_sites.remove(site_name)
            logger.info(f"Disabled crawling for site: {site_name}")
            return True
        else:
            logger.warning(f"Site {site_name} was not enabled")
            return False

    def get_available_adapters(self) -> List[str]:
        """Get list of all available adapter names."""
        return self.adapter_factory.list_available_adapters()

    def get_adapter_info(self, adapter_name: str) -> Dict[str, Any]:
        """Get information about a specific adapter."""
        return self.adapter_factory.get_adapter_info(adapter_name)

    def reset_stats(self) -> None:
        """Reset monitoring metrics, error states and rate limits with enhanced error handling."""
        try:
            # Reset crawler statistics
            self.crawler_stats = {
                "total_crawls": 0,
                "successful_crawls": 0,
                "failed_crawls": 0,
                "crawls_by_site": {},
                "average_crawl_time": 0,
                "last_crawl_time": None,
                "uptime_start": datetime.now()
            }
            
            # Reset monitoring components
            self.monitor.reset_all_metrics()
            self.rate_limiter.clear_rate_limits()
            
            # Reset error handler circuit breakers
            for site_name in self.adapters.keys():
                asyncio.create_task(self.error_handler.reset_circuit_breaker(site_name))
            
            # Reset adapter factory errors
            self.adapter_factory.reset_factory_errors()
            
            # Clear cache
            if hasattr(self.data_manager, "redis") and self.data_manager.redis:
                self.data_manager.redis.flushdb()
                
            logger.info("All crawler statistics and error states reset successfully")
            
        except Exception as e:
            error_context = self._create_error_context(
                "reset_stats_error",
                {"components": ["crawler_stats", "monitor", "rate_limiter", "error_handler", "cache"]}
            )
            
            # Report reset error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
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
        """Initialize Redis connection for caching and rate limiting"""
        try:
            # Redis setup is handled by DataManager
            logger.info("Redis initialized successfully")
        except Exception as e:
            logger.error(f"Redis initialization failed: {e}")
            raise

    def setup_crawl4ai(self) -> None:
        """Initialize Crawl4AI components"""
        try:
            # Import and configure Crawl4AI
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.extraction_strategy import LLMExtractionStrategy
            from crawl4ai.content_scraping_strategy import WebScrapingStrategy

            # Configure crawler
            self.crawl4ai_config = {
                "headless": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "viewport": {"width": 1920, "height": 1080},
                "browser_type": "chromium",
                "page_timeout": 60000,
                "cache_mode": CacheMode.BYPASS,
            }

            # Initialize extraction strategies
            self.llm_strategy = LLMExtractionStrategy(
                provider="ollama/llama3",
                schema={
                    "flights": [
                        {
                            "airline": "string",
                            "flight_number": "string",
                            "departure_time": "string",
                            "arrival_time": "string",
                            "duration": "string",
                            "price": "number",
                            "currency": "string",
                            "aircraft_type": "string",
                            "seat_class": "string",
                        }
                    ]
                },
                instruction="Extract flight information from the airline website",
            )

            self.web_strategy = WebScrapingStrategy()

            logger.info("Crawl4AI initialized successfully")

        except ImportError:
            logger.warning("Crawl4AI not available - using fallback extraction")
            self.crawl4ai_config = None
            self.llm_strategy = None
            self.web_strategy = None

        except Exception as e:
            logger.error(f"Crawl4AI initialization failed: {e}")
            self.crawl4ai_config = None

    def init_database_schema(self) -> None:
        """Initialize database schema if not exists"""
        # This is handled by DataManager
        pass

    async def get_request_batcher(self) -> RequestBatcher:
        """Get or create request batcher for optimized requests"""
        if self.request_batcher is None:
            self.request_batcher = RequestBatcher(
                max_batch_size=10,
                max_wait_time=5.0,
                max_concurrent_batches=3
            )
            await self.request_batcher.start()
        return self.request_batcher

    async def batch_site_health_checks(self, site_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on multiple sites concurrently with enhanced error handling"""
        self.current_operation = "batch_health_checks"
        
        try:
            health_results = {}
            
            # Create health check tasks
            tasks = []
            for site_name in site_names:
                if site_name in self.adapters:
                    task = asyncio.create_task(
                        self._check_site_health(site_name),
                        name=f"health_check_{site_name}"
                    )
                    tasks.append((site_name, task))
                else:
                    health_results[site_name] = {
                        "status": "not_found",
                        "error": f"Adapter {site_name} not available"
                    }

            # Wait for all health checks to complete
            if tasks:
                for site_name, task in tasks:
                    try:
                        health_status = await asyncio.wait_for(task, timeout=30)
                        health_results[site_name] = health_status
                    except asyncio.TimeoutError:
                        health_results[site_name] = {
                            "status": "timeout",
                            "error": "Health check timed out"
                        }
                    except Exception as e:
                        health_results[site_name] = {
                            "status": "error",
                            "error": str(e)
                        }

            return health_results
            
        except Exception as e:
            error_context = self._create_error_context(
                "batch_health_checks_error",
                {
                    "site_names": site_names,
                    "available_sites": list(self.adapters.keys())
                }
            )
            
            # Report batch health check error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error in batch health checks: {e}")
            return {site: {"status": "error", "error": str(e)} for site in site_names}
            
        finally:
            self.current_operation = None

    async def _check_site_health(self, site_name: str) -> Dict[str, Any]:
        """Check health of a single site"""
        try:
            adapter = self.adapters[site_name]
            
            # Check if adapter has health check method
            if hasattr(adapter, 'get_health_status'):
                return await adapter.get_health_status()
            else:
                return {
                    "status": "unknown",
                    "message": "Health check not implemented"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def close(self):
        """Clean up resources and close connections with enhanced error handling"""
        try:
            # Stop all active operations
            await self.shutdown()
            
            # Close request batcher
            if self.request_batcher:
                await self.request_batcher.stop()
            
            # Close data manager connections
            if hasattr(self.data_manager, 'close'):
                await self.data_manager.close()
            
            logger.info("Enhanced Flight Crawler closed successfully")
            
        except Exception as e:
            error_context = self._create_error_context(
                "crawler_close_error",
                {"components": ["shutdown", "request_batcher", "data_manager"]}
            )
            
            # Report close error (non-blocking)
            asyncio.create_task(self.error_handler.handle_error(
                e, error_context, ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE
            ))
            
            logger.error(f"Error closing crawler: {e}")

    def get_crawler_metrics(self) -> Dict[str, Any]:
        """Get comprehensive crawler metrics"""
        try:
            uptime = (datetime.now() - self.crawler_stats["uptime_start"]).total_seconds()
            
            return {
                "crawler_id": self.crawler_id,
                "session_id": self.session_id,
                "uptime_seconds": uptime,
                "crawler_statistics": self.crawler_stats,
                "error_statistics": self.error_handler.get_error_statistics(),
                "adapter_factory_stats": self.adapter_factory.get_factory_health_status(),
                "memory_status": self.get_memory_status() if self.enable_memory_monitoring else None,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get crawler metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
