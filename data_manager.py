import logging
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    func,
    Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from redis import Redis
from config import config
import copy
import datetime as dt
import re
from html import escape
from urllib.parse import quote

# Configure logging
logger = logging.getLogger(__name__)


# Security utilities for input validation and sanitization
class InputValidator:
    """Utility class for input validation and sanitization"""

    @staticmethod
    def validate_airport_code(code: str) -> str:
        """Validate and sanitize airport code (IATA/ICAO)"""
        if not code or not isinstance(code, str):
            raise ValueError("Airport code must be a non-empty string")

        # Remove any special characters and convert to uppercase
        sanitized = re.sub(r"[^A-Z0-9]", "", code.upper())

        # IATA codes are 3 characters, ICAO are 4
        if len(sanitized) not in [3, 4]:
            raise ValueError("Airport code must be 3 or 4 characters")

        return sanitized

    @staticmethod
    def validate_route_string(route: str) -> Tuple[str, str]:
        """Validate and parse route string (e.g., 'THR-IST')"""
        if not route or not isinstance(route, str):
            raise ValueError("Route must be a non-empty string")

        # Sanitize and split
        sanitized = re.sub(r"[^A-Z0-9-]", "", route.upper())
        parts = sanitized.split("-")

        if len(parts) != 2:
            raise ValueError("Route must be in format 'ORIGIN-DESTINATION'")

        origin = InputValidator.validate_airport_code(parts[0])
        destination = InputValidator.validate_airport_code(parts[1])

        return origin, destination

    @staticmethod
    def sanitize_string(text: str, max_length: int = 255) -> str:
        """Sanitize string input to prevent injection"""
        if not text:
            return ""

        # Convert to string and escape HTML
        sanitized = escape(str(text))

        # Remove any potentially dangerous characters
        sanitized = re.sub(r'[<>"\';\\]', "", sanitized)

        # Truncate to max length
        return sanitized[:max_length]

    @staticmethod
    def validate_positive_integer(
        value: Any, min_value: int = 1, max_value: int = 1000
    ) -> int:
        """Validate positive integer within bounds"""
        try:
            int_value = int(value)
            if int_value < min_value or int_value > max_value:
                raise ValueError(f"Value must be between {min_value} and {max_value}")
            return int_value
        except (ValueError, TypeError):
            raise ValueError(f"Invalid integer value: {value}")

    @staticmethod
    def validate_flight_id(
        airline: str,
        flight_number: str,
        origin: str,
        destination: str,
        departure_time: datetime,
    ) -> str:
        """Generate secure flight ID with validated inputs"""
        # Sanitize all inputs
        airline = InputValidator.sanitize_string(airline, 50)
        flight_number = InputValidator.sanitize_string(flight_number, 20)
        origin = InputValidator.validate_airport_code(origin)
        destination = InputValidator.validate_airport_code(destination)

        # Generate secure ID
        time_str = departure_time.strftime("%Y%m%d%H%M")
        return f"{airline}_{flight_number}_{origin}_{destination}_{time_str}"


# Create SQLAlchemy base
Base = declarative_base()


# Database models
class Flight(Base):
    """Flight model"""

    __tablename__ = "flights"

    id = Column(Integer, primary_key=True)
    flight_id = Column(String, unique=True)
    airline = Column(String)
    flight_number = Column(String)
    origin = Column(String)
    destination = Column(String)
    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    price = Column(Float)
    currency = Column(String)
    seat_class = Column(String)
    aircraft_type = Column(String)
    duration_minutes = Column(Integer)
    flight_type = Column(String)
    scraped_at = Column(DateTime)
    source_url = Column(String)
    raw_data = Column(JSON)

    # Relationships
    price_history = relationship("FlightPriceHistory", back_populates="flight")


class FlightPriceHistory(Base):
    """Flight price history model"""

    __tablename__ = "flight_price_history"

    id = Column(Integer, primary_key=True)
    flight_id = Column(String, ForeignKey("flights.flight_id"))
    price = Column(Float)
    currency = Column(String)
    recorded_at = Column(DateTime)

    # Relationships
    flight = relationship("Flight", back_populates="price_history")


class SearchQuery(Base):
    """Search query model"""

    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    departure_date = Column(String)
    passengers = Column(Integer)
    seat_class = Column(String)
    query_time = Column(DateTime)
    result_count = Column(Integer)
    search_duration = Column(Float)
    cached = Column(Integer)


class CrawlRoute(Base):
    """Route configuration model"""

    __tablename__ = "crawl_routes"

    id = Column(Integer, primary_key=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# New Airport model for dropdowns and airport management
class Airport(Base):
    """Airport model"""

    __tablename__ = "airports"

    id = Column(Integer, primary_key=True)
    iata = Column(String, index=True)
    icao = Column(String, index=True)
    name = Column(String)
    city = Column(String)
    country = Column(String)
    type = Column(String)


class DataManager:
    """Manage data storage and retrieval"""

    def __init__(self) -> None:
        # Initialize database
        db = config.DATABASE
        db_url = f"postgresql://{db.USER}:{db.PASSWORD}@{db.HOST}:{db.PORT}/{db.NAME}"
        try:
            self.engine = create_engine(db_url, echo=False)
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )

            # Create tables
            Base.metadata.create_all(bind=self.engine)

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.engine = None
            self.SessionLocal = None

        # Initialize Redis
        try:
            self.redis: Optional[Redis] = Redis(
                host=config.REDIS.HOST,
                port=config.REDIS.PORT,
                db=config.REDIS.DB,
                password=config.REDIS.PASSWORD or None,
                decode_responses=True,
            )
            # Test connection
            self.redis.ping()
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis = None

    def get_session(self) -> Session:
        """Get database session"""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    def store_flights(self, flights_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Store flight data in database with security validation"""
        if not self.engine:
            logger.error("Database not available")
            return

        session = self.get_session()
        try:
            for site_name, flights in flights_data.items():
                for flight_data in flights:
                    try:
                        # Validate and sanitize input data
                        airline = InputValidator.sanitize_string(
                            flight_data.get("airline", ""), 100
                        )
                        flight_number = InputValidator.sanitize_string(
                            flight_data.get("flight_number", ""), 20
                        )
                        origin = InputValidator.validate_airport_code(
                            flight_data.get("origin", "")
                        )
                        destination = InputValidator.validate_airport_code(
                            flight_data.get("destination", "")
                        )

                        # Parse and validate price
                        price = float(flight_data.get("price", 0))
                        if price < 0 or price > 100000000:  # Reasonable bounds
                            logger.warning(f"Invalid price: {price}")
                            continue

                        # Generate secure flight ID
                        departure_time = flight_data.get("departure_time")
                        if isinstance(departure_time, str):
                            departure_time = datetime.fromisoformat(
                                departure_time.replace("Z", "+00:00")
                            )

                        flight_id = InputValidator.validate_flight_id(
                            airline, flight_number, origin, destination, departure_time
                        )

                        # Create flight object
                        flight = Flight(
                            flight_id=flight_id,
                            airline=airline,
                            flight_number=flight_number,
                            origin=origin,
                            destination=destination,
                            departure_time=departure_time,
                            arrival_time=flight_data.get("arrival_time"),
                            price=price,
                            currency=InputValidator.sanitize_string(
                                flight_data.get("currency", "IRR"), 3
                            ),
                            seat_class=InputValidator.sanitize_string(
                                flight_data.get("seat_class", ""), 50
                            ),
                            aircraft_type=InputValidator.sanitize_string(
                                flight_data.get("aircraft_type", ""), 50
                            ),
                            duration_minutes=InputValidator.validate_positive_integer(
                                flight_data.get("duration_minutes", 0), 0, 2000
                            ),
                            flight_type=InputValidator.sanitize_string(
                                flight_data.get("flight_type", ""), 20
                            ),
                            scraped_at=datetime.now(),
                            source_url=InputValidator.sanitize_string(
                                flight_data.get("source_url", ""), 500
                            ),
                            raw_data=flight_data,
                        )

                        # Use merge to handle duplicates
                        session.merge(flight)

                    except Exception as e:
                        logger.error(f"Error processing flight data: {e}")
                        continue

            session.commit()
            logger.info(f"Stored flights from {len(flights_data)} sites")

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing flights: {e}")
        finally:
            session.close()

    def store_search_query(
        self,
        params: Dict[str, Any],
        result_count: int,
        search_duration: float,
        cached: bool,
    ) -> None:
        """Store search query with input validation"""
        if not self.engine:
            return

        session = self.get_session()
        try:
            # Validate inputs
            origin = InputValidator.validate_airport_code(params.get("origin", ""))
            destination = InputValidator.validate_airport_code(
                params.get("destination", "")
            )
            passengers = InputValidator.validate_positive_integer(
                params.get("passengers", 1), 1, 20
            )

            query = SearchQuery(
                origin=origin,
                destination=destination,
                departure_date=InputValidator.sanitize_string(
                    params.get("departure_date", ""), 20
                ),
                passengers=passengers,
                seat_class=InputValidator.sanitize_string(
                    params.get("seat_class", "economy"), 50
                ),
                query_time=datetime.now(),
                result_count=max(0, int(result_count)),
                search_duration=max(0.0, float(search_duration)),
                cached=1 if cached else 0,
            )

            session.add(query)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error storing search query: {e}")
        finally:
            session.close()

    def get_flight_price_history(self, flight_id: str) -> List[Dict[str, Any]]:
        """Get price history for a flight with input validation"""
        if not self.engine:
            return []

        # Validate flight_id
        flight_id = InputValidator.sanitize_string(flight_id, 200)

        session = self.get_session()
        try:
            history = (
                session.query(FlightPriceHistory)
                .filter(FlightPriceHistory.flight_id == flight_id)
                .order_by(FlightPriceHistory.recorded_at.desc())
                .all()
            )

            return [
                {
                    "price": h.price,
                    "currency": h.currency,
                    "recorded_at": h.recorded_at.isoformat(),
                }
                for h in history
            ]

        except Exception as e:
            logger.error(f"Error getting price history: {e}")
            return []
        finally:
            session.close()

    def get_cached_results(
        self, params: Dict[str, Any]
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Get cached search results with input validation"""
        if not self.redis:
            return None

        try:
            # Generate secure cache key
            cache_key = self._generate_cache_key(params)
            cached_data = self.redis.get(cache_key)

            if cached_data:
                return json.loads(cached_data)

        except Exception as e:
            logger.error(f"Error getting cached results: {e}")

        return None

    def _generate_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate secure cache key"""
        try:
            origin = InputValidator.validate_airport_code(params.get("origin", ""))
            destination = InputValidator.validate_airport_code(
                params.get("destination", "")
            )
            date = InputValidator.sanitize_string(params.get("departure_date", ""), 20)
            passengers = InputValidator.validate_positive_integer(
                params.get("passengers", 1), 1, 20
            )
            seat_class = InputValidator.sanitize_string(
                params.get("seat_class", "economy"), 50
            )

            return f"search:{origin}:{destination}:{date}:{passengers}:{seat_class}"
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"search:invalid:{hash(str(params))}"

    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        if not self.engine:
            return {}

        session = self.get_session()
        try:
            # Get basic stats
            total_searches = session.query(SearchQuery).count()
            cached_searches = (
                session.query(SearchQuery).filter(SearchQuery.cached == 1).count()
            )

            # Get recent searches
            recent_searches = (
                session.query(SearchQuery)
                .filter(SearchQuery.query_time >= datetime.now() - timedelta(days=7))
                .count()
            )

            # Get popular routes
            popular_routes = (
                session.query(
                    SearchQuery.origin,
                    SearchQuery.destination,
                    func.count(SearchQuery.id).label("count"),
                )
                .group_by(SearchQuery.origin, SearchQuery.destination)
                .order_by(func.count(SearchQuery.id).desc())
                .limit(10)
                .all()
            )

            return {
                "total_searches": total_searches,
                "cached_searches": cached_searches,
                "cache_hit_rate": (
                    (cached_searches / total_searches * 100)
                    if total_searches > 0
                    else 0
                ),
                "recent_searches": recent_searches,
                "popular_routes": [
                    {"route": f"{r.origin}-{r.destination}", "count": r.count}
                    for r in popular_routes
                ],
            }

        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}
        finally:
            session.close()

    def get_flight_stats(self) -> Dict[str, Any]:
        """Get flight statistics"""
        if not self.engine:
            return {}

        session = self.get_session()
        try:
            # Basic counts
            total_flights = session.query(Flight).count()
            unique_airlines = session.query(Flight.airline).distinct().count()
            unique_routes = (
                session.query(Flight.origin, Flight.destination).distinct().count()
            )

            # Recent flights
            recent_flights = (
                session.query(Flight)
                .filter(Flight.scraped_at >= datetime.now() - timedelta(days=1))
                .count()
            )

            # Price statistics
            price_stats = session.query(
                func.min(Flight.price).label("min_price"),
                func.max(Flight.price).label("max_price"),
                func.avg(Flight.price).label("avg_price"),
            ).first()

            # Top airlines by flight count
            top_airlines = (
                session.query(Flight.airline, func.count(Flight.id).label("count"))
                .group_by(Flight.airline)
                .order_by(func.count(Flight.id).desc())
                .limit(10)
                .all()
            )

            return {
                "total_flights": total_flights,
                "unique_airlines": unique_airlines,
                "unique_routes": unique_routes,
                "recent_flights": recent_flights,
                "price_stats": {
                    "min_price": (
                        float(price_stats.min_price) if price_stats.min_price else 0
                    ),
                    "max_price": (
                        float(price_stats.max_price) if price_stats.max_price else 0
                    ),
                    "avg_price": (
                        float(price_stats.avg_price) if price_stats.avg_price else 0
                    ),
                },
                "top_airlines": [
                    {"airline": a.airline, "count": a.count} for a in top_airlines
                ],
            }

        except Exception as e:
            logger.error(f"Error getting flight stats: {e}")
            return {}
        finally:
            session.close()

    def get_recent_flights(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent flights with input validation"""
        if not self.engine:
            return []

        # Validate limit
        limit = InputValidator.validate_positive_integer(limit, 1, 1000)

        session = self.get_session()
        try:
            flights = (
                session.query(Flight)
                .order_by(Flight.scraped_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "flight_id": f.flight_id,
                    "airline": f.airline,
                    "flight_number": f.flight_number,
                    "origin": f.origin,
                    "destination": f.destination,
                    "departure_time": (
                        f.departure_time.isoformat() if f.departure_time else None
                    ),
                    "arrival_time": (
                        f.arrival_time.isoformat() if f.arrival_time else None
                    ),
                    "price": f.price,
                    "currency": f.currency,
                    "seat_class": f.seat_class,
                    "aircraft_type": f.aircraft_type,
                    "duration_minutes": f.duration_minutes,
                    "flight_type": f.flight_type,
                    "scraped_at": f.scraped_at.isoformat() if f.scraped_at else None,
                    "source_url": f.source_url,
                }
                for f in flights
            ]

        except Exception as e:
            logger.error(f"Error getting recent flights: {e}")
            return []
        finally:
            session.close()

    async def get_cached_search(self, search_key: str) -> Optional[Dict[str, Any]]:
        """Get cached search results asynchronously"""
        if not self.redis:
            return None

        try:
            # Validate search key
            search_key = InputValidator.sanitize_string(search_key, 200)

            cached_data = self.redis.get(f"search:{search_key}")
            if cached_data:
                return json.loads(cached_data)

        except Exception as e:
            logger.error(f"Error getting cached search: {e}")

        return None

    async def get_historical_prices(
        self, route: str, days_back: int = 365
    ) -> List[Dict[str, Any]]:
        """Get historical price data for a route"""
        if not self.engine:
            return []

        try:
            # Validate route
            origin, destination = InputValidator.validate_route_string(route)
            days_back = InputValidator.validate_positive_integer(
                days_back, 1, 3650
            )  # Max 10 years

            session = self.get_session()
            try:
                cutoff_date = datetime.now() - timedelta(days=days_back)

                flights = (
                    session.query(Flight)
                    .filter(
                        Flight.origin == origin,
                        Flight.destination == destination,
                        Flight.scraped_at >= cutoff_date,
                    )
                    .order_by(Flight.scraped_at.desc())
                    .all()
                )

                return [
                    {
                        "date": f.scraped_at.isoformat(),
                        "price": f.price,
                        "currency": f.currency,
                        "airline": f.airline,
                        "flight_number": f.flight_number,
                    }
                    for f in flights
                ]

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting historical prices: {e}")
            return []

    async def get_current_price(self, route: str) -> float:
        """Get current average price for a route"""
        if not self.engine:
            return 0.0

        try:
            # Validate route
            origin, destination = InputValidator.validate_route_string(route)

            session = self.get_session()
            try:
                # Get average price from last 24 hours
                cutoff_date = datetime.now() - timedelta(hours=24)

                avg_price = (
                    session.query(func.avg(Flight.price))
                    .filter(
                        Flight.origin == origin,
                        Flight.destination == destination,
                        Flight.scraped_at >= cutoff_date,
                    )
                    .scalar()
                )

                return float(avg_price) if avg_price else 0.0

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 0.0

    async def get_search_count(self, route: str) -> int:
        """Get search count for a route"""
        if not self.engine:
            return 0

        try:
            # Validate route
            origin, destination = InputValidator.validate_route_string(route)

            session = self.get_session()
            try:
                count = (
                    session.query(SearchQuery)
                    .filter(
                        SearchQuery.origin == origin,
                        SearchQuery.destination == destination,
                    )
                    .count()
                )

                return count

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting search count: {e}")
            return 0

    async def store_flights(self, flights: Dict[str, List[Dict[str, Any]]]) -> None:
        """Store flights asynchronously"""
        self.store_flights(flights)

    async def cache_search_results(
        self, search_params: Dict[str, Any], results: Dict[str, Any]
    ) -> None:
        """Cache search results with TTL"""
        if not self.redis:
            return

        try:
            cache_key = self._generate_cache_key(search_params)
            cache_data = json.dumps(results, default=self._json_serializer)

            # Cache for 1 hour
            self.redis.setex(cache_key, 3600, cache_data)

        except Exception as e:
            logger.error(f"Error caching search results: {e}")

    def _json_serializer(self, obj: Any) -> str:
        """JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _generate_search_key(self, search_params: Dict[str, Any]) -> str:
        """Generate search key for caching"""
        return self._generate_cache_key(search_params)

    async def add_crawl_route(self, origin: str, destination: str) -> int:
        """Add a new crawl route with validation"""
        if not self.engine:
            raise RuntimeError("Database not available")

        try:
            # Validate airport codes
            origin = InputValidator.validate_airport_code(origin)
            destination = InputValidator.validate_airport_code(destination)

            session = self.get_session()
            try:
                # Check if route already exists
                existing = (
                    session.query(CrawlRoute)
                    .filter(
                        CrawlRoute.origin == origin,
                        CrawlRoute.destination == destination,
                    )
                    .first()
                )

                if existing:
                    if not existing.is_active:
                        existing.is_active = True
                        session.commit()
                        return existing.id
                    else:
                        raise ValueError("Route already exists and is active")

                # Create new route
                route = CrawlRoute(
                    origin=origin,
                    destination=destination,
                    is_active=True,
                    created_at=datetime.now(),
                )

                session.add(route)
                session.commit()
                return route.id

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error adding crawl route: {e}")
            raise

    async def delete_crawl_route(self, route_id: int) -> bool:
        """Delete a crawl route"""
        if not self.engine:
            return False

        try:
            # Validate route_id
            route_id = InputValidator.validate_positive_integer(route_id, 1, 999999999)

            session = self.get_session()
            try:
                route = (
                    session.query(CrawlRoute).filter(CrawlRoute.id == route_id).first()
                )
                if route:
                    route.is_active = False
                    session.commit()
                    return True
                return False

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error deleting crawl route: {e}")
            return False

    async def get_active_routes(self) -> List[Dict[str, Any]]:
        """Get all active crawl routes"""
        if not self.engine:
            return []

        session = self.get_session()
        try:
            routes = (
                session.query(CrawlRoute).filter(CrawlRoute.is_active == True).all()
            )

            return [
                {
                    "id": r.id,
                    "origin": r.origin,
                    "destination": r.destination,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in routes
            ]

        except Exception as e:
            logger.error(f"Error getting active routes: {e}")
            return []
        finally:
            session.close()

    async def get_airports(
        self, search: str = "", country: Optional[str] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get airports with optional filtering"""
        if not self.engine:
            return []

        try:
            # Validate inputs
            search = InputValidator.sanitize_string(search, 100)
            if country:
                country = InputValidator.sanitize_string(country, 100)
            limit = InputValidator.validate_positive_integer(limit, 1, 10000)

            session = self.get_session()
            try:
                query = session.query(Airport)

                if search:
                    search_term = f"%{search}%"
                    query = query.filter(
                        (Airport.name.ilike(search_term))
                        | (Airport.city.ilike(search_term))
                        | (Airport.iata.ilike(search_term))
                        | (Airport.icao.ilike(search_term))
                    )

                if country:
                    query = query.filter(Airport.country.ilike(f"%{country}%"))

                airports = query.limit(limit).all()

                return [
                    {
                        "id": a.id,
                        "iata": a.iata,
                        "icao": a.icao,
                        "name": a.name,
                        "city": a.city,
                        "country": a.country,
                        "type": a.type,
                    }
                    for a in airports
                ]

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error getting airports: {e}")
            return []

    async def get_countries(self) -> List[str]:
        """Get list of countries from airports"""
        if not self.engine:
            return []

        session = self.get_session()
        try:
            countries = (
                session.query(Airport.country)
                .distinct()
                .filter(Airport.country.isnot(None))
                .order_by(Airport.country)
                .all()
            )

            return [c.country for c in countries if c.country]

        except Exception as e:
            logger.error(f"Error getting countries: {e}")
            return []
        finally:
            session.close()
