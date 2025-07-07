"""
Unified Crawler Interface

This module provides a unified interface that bridges all three crawler systems:
- Requests folder (HybridCrawlerInterface)
- Adapters folder (EnhancedBaseCrawler) 
- Crawlers folder (BaseSiteCrawler)

The unified interface supports both synchronous and asynchronous operations,
standardized configuration, and consistent data formats.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, TypeVar, Generic
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger(__name__)

# Type variables for generic support
T = TypeVar('T')
CrawlerResultType = Union[List[Dict[str, Any]], Tuple[bool, Dict[str, Any], str]]

class CrawlerSystemType(Enum):
    """Types of crawler systems"""
    REQUESTS = "requests"
    ADAPTERS = "adapters"
    CRAWLERS = "crawlers"
    UNIFIED = "unified"

class OperationMode(Enum):
    """Operation modes for crawler execution"""
    SYNC = "sync"
    ASYNC = "async" 
    AUTO = "auto"

@dataclass
class CrawlerMetadata:
    """Metadata for crawler instances"""
    crawler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_type: CrawlerSystemType = CrawlerSystemType.UNIFIED
    operation_mode: OperationMode = OperationMode.AUTO
    created_at: datetime = field(default_factory=datetime.now)
    adapter_name: Optional[str] = None
    site_name: Optional[str] = None
    base_url: Optional[str] = None

@dataclass 
class SearchParameters:
    """Standardized search parameters across all systems"""
    # Core flight search parameters
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    seat_class: str = "economy"
    
    # Additional parameters
    trip_type: str = "one_way"  # one_way, round_trip
    currency: str = "IRR"
    language: str = "fa"
    
    # System-specific parameters
    url: Optional[str] = None  # For requests system
    site_config: Optional[Dict[str, Any]] = None  # For crawlers system
    extraction_config: Optional[Dict[str, Any]] = None  # For adapters system
    
    # Execution parameters
    timeout: int = 30
    max_retries: int = 3
    enable_javascript: bool = True
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format"""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "passengers": self.passengers,
            "seat_class": self.seat_class,
            "timeout": self.timeout,
            "enable_javascript": self.enable_javascript
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format"""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "passengers": self.passengers,
            "seat_class": self.seat_class,
            "trip_type": self.trip_type,
            "currency": self.currency,
            "language": self.language
        }
    
    def to_crawlers_format(self) -> dict:
        """Convert to crawlers system format"""
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "passengers": self.passengers,
            "seat_class": self.seat_class,
            "trip_type": self.trip_type
        }

@dataclass
class FlightData:
    """Standardized flight data structure"""
    # Core flight information
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: float
    currency: str
    
    # Additional information
    duration_minutes: Optional[int] = None
    seat_class: Optional[str] = None
    aircraft_type: Optional[str] = None
    stops: int = 0
    
    # Booking information
    booking_url: Optional[str] = None
    available_seats: Optional[int] = None
    is_refundable: bool = False
    
    # System metadata
    extracted_at: datetime = field(default_factory=datetime.now)
    source_system: CrawlerSystemType = CrawlerSystemType.UNIFIED
    adapter_name: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "airline": self.airline,
            "flight_number": self.flight_number,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "price": self.price,
            "currency": self.currency,
            "duration_minutes": self.duration_minutes,
            "seat_class": self.seat_class,
            "aircraft_type": self.aircraft_type,
            "stops": self.stops,
            "booking_url": self.booking_url,
            "available_seats": self.available_seats,
            "is_refundable": self.is_refundable,
            "extracted_at": self.extracted_at.isoformat(),
            "source_system": self.source_system.value,
            "adapter_name": self.adapter_name
        }

@dataclass
class CrawlerResult:
    """Standardized crawler result structure"""
    success: bool
    flights: List[FlightData] = field(default_factory=list)
    message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    system_used: CrawlerSystemType = CrawlerSystemType.UNIFIED
    
    def to_requests_format(self) -> Tuple[bool, Dict[str, Any], str]:
        """Convert to requests system format"""
        data = {
            "flights": [flight.to_dict() for flight in self.flights],
            "metadata": self.metadata,
            "execution_time": self.execution_time
        }
        return self.success, data, self.message or self.error or ""
    
    def to_adapters_format(self) -> List[Dict[str, Any]]:
        """Convert to adapters system format"""
        return [flight.to_dict() for flight in self.flights]
    
    def to_crawlers_format(self) -> list:
        """Convert to crawlers system format"""
        return [flight.to_dict() for flight in self.flights]

class UnifiedCrawlerInterface(ABC):
    """
    Unified interface that supports all three crawler systems.
    
    This interface provides both synchronous and asynchronous methods,
    standardized parameters, and consistent return formats.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.metadata = CrawlerMetadata()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._progress_callbacks: List[Callable] = []
    
    # Core abstract methods that must be implemented
    @abstractmethod
    async def _async_crawl_implementation(self, params: SearchParameters) -> CrawlerResult:
        """Async implementation of crawling logic"""
        pass
    
    @abstractmethod
    def _get_system_type(self) -> CrawlerSystemType:
        """Get the underlying system type"""
        pass
    
    # Unified crawl methods supporting all interfaces
    async def crawl_async(self, params: SearchParameters) -> CrawlerResult:
        """Async crawl method - primary interface"""
        start_time = datetime.now()
        
        try:
            self._notify_progress("Starting crawl...")
            result = await self._async_crawl_implementation(params)
            
            # Set execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            result.system_used = self._get_system_type()
            
            self._notify_progress("Crawl completed")
            return result
            
        except Exception as e:
            self.logger.error(f"Crawl failed: {e}")
            return CrawlerResult(
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
                system_used=self._get_system_type()
            )
    
    def crawl_sync(self, params: SearchParameters) -> CrawlerResult:
        """Sync crawl method for backwards compatibility"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.crawl_async(params))
                    return future.result()
            else:
                return asyncio.run(self.crawl_async(params))
        except Exception as e:
            self.logger.error(f"Sync crawl failed: {e}")
            return CrawlerResult(
                success=False,
                error=str(e),
                system_used=self._get_system_type()
            )
    
    # Compatibility methods for different systems
    
    # Requests system compatibility
    def crawl(self, url: str, **kwargs) -> Tuple[bool, Dict[str, Any], str]:
        """Requests system compatibility method"""
        # Convert requests format to unified format
        params = SearchParameters(
            origin=kwargs.get("origin", ""),
            destination=kwargs.get("destination", ""),
            departure_date=kwargs.get("departure_date", ""),
            return_date=kwargs.get("return_date"),
            passengers=kwargs.get("passengers", 1),
            seat_class=kwargs.get("seat_class", "economy"),
            url=url,
            timeout=kwargs.get("timeout", 30),
            enable_javascript=kwargs.get("enable_javascript", True)
        )
        
        result = self.crawl_sync(params)
        return result.to_requests_format()
    
    def validate_url(self, url: str) -> bool:
        """Requests system URL validation"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def cleanup(self) -> None:
        """Requests system cleanup method"""
        asyncio.create_task(self.cleanup_async())
    
    # Adapters system compatibility  
    async def crawl(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Adapters system compatibility method"""
        # Convert adapters format to unified format
        params = SearchParameters(
            origin=search_params.get("origin", ""),
            destination=search_params.get("destination", ""),
            departure_date=search_params.get("departure_date", ""),
            return_date=search_params.get("return_date"),
            passengers=search_params.get("passengers", 1),
            seat_class=search_params.get("seat_class", "economy"),
            trip_type=search_params.get("trip_type", "one_way"),
            currency=search_params.get("currency", "IRR"),
            language=search_params.get("language", "fa")
        )
        
        result = await self.crawl_async(params)
        return result.to_adapters_format()
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Adapters system health check"""
        return {
            "status": "healthy",
            "crawler_id": self.metadata.crawler_id,
            "system_type": self._get_system_type().value,
            "created_at": self.metadata.created_at.isoformat(),
            "adapter_name": self.metadata.adapter_name,
            "site_name": self.metadata.site_name
        }
    
    def _get_base_url(self) -> str:
        """Adapters system base URL method"""
        return self.metadata.base_url or self.config.get("base_url", "")
    
    # Crawlers system compatibility
    async def crawl(self, search_params: dict) -> list:
        """Crawlers system compatibility method"""
        # Convert crawlers format to unified format
        params = SearchParameters(
            origin=search_params.get("origin", ""),
            destination=search_params.get("destination", ""),
            departure_date=search_params.get("departure_date", ""),
            return_date=search_params.get("return_date"),
            passengers=search_params.get("passengers", 1),
            seat_class=search_params.get("seat_class", "economy"),
            trip_type=search_params.get("trip_type", "one_way"),
            site_config=search_params.get("site_config")
        )
        
        result = await self.crawl_async(params)
        return result.to_crawlers_format()
    
    # Additional unified methods
    async def cleanup_async(self) -> None:
        """Async cleanup method"""
        try:
            # Override in subclasses for specific cleanup logic
            self.logger.info("Crawler cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
    
    def add_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Add progress callback"""
        self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Remove progress callback"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    def _notify_progress(self, message: str) -> None:
        """Notify progress to all callbacks"""
        for callback in self._progress_callbacks:
            try:
                callback(message)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")
    
    def get_metadata(self) -> CrawlerMetadata:
        """Get crawler metadata"""
        return self.metadata
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update crawler configuration"""
        self.config.update(config)
        self.logger.info("Configuration updated")

# Utility functions for system detection and conversion
def detect_system_type(crawler_instance) -> CrawlerSystemType:
    """Detect which system type a crawler instance belongs to"""
    class_name = crawler_instance.__class__.__name__
    module_name = crawler_instance.__class__.__module__
    
    if "requests" in module_name or "HybridCrawlerInterface" in str(type(crawler_instance)):
        return CrawlerSystemType.REQUESTS
    elif "adapters" in module_name or "EnhancedBaseCrawler" in str(type(crawler_instance)):
        return CrawlerSystemType.ADAPTERS
    elif "crawlers" in module_name or "BaseSiteCrawler" in str(type(crawler_instance)):
        return CrawlerSystemType.CRAWLERS
    else:
        return CrawlerSystemType.UNIFIED

def convert_search_params(params: Any, target_system: CrawlerSystemType) -> Any:
    """Convert search parameters between different system formats"""
    if isinstance(params, SearchParameters):
        if target_system == CrawlerSystemType.REQUESTS:
            return params.to_requests_format()
        elif target_system == CrawlerSystemType.ADAPTERS:
            return params.to_adapters_format()
        elif target_system == CrawlerSystemType.CRAWLERS:
            return params.to_crawlers_format()
    
    # Convert from other formats to SearchParameters first
    if isinstance(params, dict):
        return SearchParameters(
            origin=params.get("origin", ""),
            destination=params.get("destination", ""),
            departure_date=params.get("departure_date", ""),
            return_date=params.get("return_date"),
            passengers=params.get("passengers", 1),
            seat_class=params.get("seat_class", "economy"),
            trip_type=params.get("trip_type", "one_way"),
            currency=params.get("currency", "IRR"),
            language=params.get("language", "fa"),
            url=params.get("url"),
            timeout=params.get("timeout", 30),
            enable_javascript=params.get("enable_javascript", True)
        )
    
    return params

def standardize_flight_data(raw_data: Any, source_system: CrawlerSystemType) -> List[FlightData]:
    """Standardize flight data from any system into unified format"""
    flights = []
    
    if isinstance(raw_data, tuple) and len(raw_data) == 3:
        # Requests system format: (success, data, message)
        success, data, message = raw_data
        if success and isinstance(data, dict) and "flights" in data:
            for flight_dict in data["flights"]:
                flights.append(_dict_to_flight_data(flight_dict, source_system))
    
    elif isinstance(raw_data, list):
        # Adapters/Crawlers system format: List[Dict]
        for flight_dict in raw_data:
            if isinstance(flight_dict, dict):
                flights.append(_dict_to_flight_data(flight_dict, source_system))
    
    elif isinstance(raw_data, dict):
        # Single flight data
        flights.append(_dict_to_flight_data(raw_data, source_system))
    
    return flights

def _dict_to_flight_data(data: Dict[str, Any], source_system: CrawlerSystemType) -> FlightData:
    """Convert dictionary to FlightData object"""
    return FlightData(
        airline=data.get("airline", ""),
        flight_number=data.get("flight_number", ""),
        origin=data.get("origin", ""),
        destination=data.get("destination", ""),
        departure_time=data.get("departure_time", ""),
        arrival_time=data.get("arrival_time", ""),
        price=float(data.get("price", 0)),
        currency=data.get("currency", "IRR"),
        duration_minutes=data.get("duration_minutes"),
        seat_class=data.get("seat_class"),
        aircraft_type=data.get("aircraft_type"),
        stops=data.get("stops", 0),
        booking_url=data.get("booking_url"),
        available_seats=data.get("available_seats"),
        is_refundable=data.get("is_refundable", False),
        source_system=source_system,
        adapter_name=data.get("adapter_name"),
        raw_data=data
    ) 