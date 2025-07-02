import logging
import json
from typing import Dict, List, Optional
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

# Configure logging
logger = logging.getLogger(__name__)

# Create SQLAlchemy base
Base = declarative_base()

# Database models
class Flight(Base):
    """Flight model"""
    __tablename__ = 'flights'
    
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
    __tablename__ = 'flight_price_history'
    
    id = Column(Integer, primary_key=True)
    flight_id = Column(String, ForeignKey('flights.flight_id'))
    price = Column(Float)
    currency = Column(String)
    recorded_at = Column(DateTime)
    
    # Relationships
    flight = relationship("Flight", back_populates="price_history")

class SearchQuery(Base):
    """Search query model"""
    __tablename__ = 'search_queries'
    
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
    
    def __init__(self):
        # Initialize database
        db = config.DATABASE
        db_url = (
            f"postgresql://{db.USER}:{db.PASSWORD}@{db.HOST}:{db.PORT}/{db.NAME}"
        )
        try:
            self.engine = create_engine(db_url)
            self.engine.connect()
        except Exception as e:
            logger.warning(
                f"PostgreSQL connection failed ({e}); using local SQLite database"
            )
            sqlite_path = Path("data") / "flight_data.sqlite"
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(f"sqlite:///{sqlite_path}")
        self.Session = sessionmaker(bind=self.engine)

        # Initialize Redis
        redis_cfg = config.REDIS
        redis_url = f"redis://{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
        if redis_cfg.PASSWORD:
            redis_url = (
                f"redis://:{redis_cfg.PASSWORD}@{redis_cfg.HOST}:{redis_cfg.PORT}/"
                f"{redis_cfg.DB}"
            )
        self.redis = Redis.from_url(redis_url)
        
        # Create tables
        Base.metadata.create_all(self.engine)
    
    
    def store_search_query(self, params: Dict, result_count: int, search_duration: float, cached: bool) -> None:
        """Store search query in database"""
        try:
            # Create session
            session = self.Session()
            
            # Create search query
            query = SearchQuery(
                origin=params.get('origin', ''),
                destination=params.get('destination', ''),
                departure_date=params.get('departure_date', ''),
                passengers=params.get('passengers', 1),
                seat_class=params.get('seat_class', 'economy'),
                query_time=datetime.now(),
                result_count=result_count,
                search_duration=search_duration,
                cached=1 if cached else 0
            )
            
            # Add and commit
            session.add(query)
            session.commit()
            
        except Exception as e:
            logger.error(f"Error storing search query: {e}")
            session.rollback()
            raise
        
        finally:
            session.close()
    
    def get_flight_price_history(self, flight_id: str) -> List[Dict]:
        """Get flight price history"""
        try:
            # Create session
            session = self.Session()
            
            # Get price history
            history = session.query(FlightPriceHistory).filter_by(flight_id=flight_id).order_by(FlightPriceHistory.recorded_at).all()
            
            return [
                {
                    'price': h.price,
                    'currency': h.currency,
                    'recorded_at': h.recorded_at.isoformat()
                }
                for h in history
            ]
            
        except Exception as e:
            logger.error(f"Error getting flight price history: {e}")
            return []
        
        finally:
            session.close()
    
    
    def get_cached_results(self, params: Dict) -> Optional[Dict[str, List[Dict]]]:
        """Get cached search results from Redis"""
        try:
            # Generate cache key
            key = self._generate_cache_key(params)
            
            # Get cached results
            cached = self.redis.get(key)
            
            if cached:
                return json.loads(cached)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached results: {e}")
            return None
    
    def _generate_cache_key(self, params: Dict) -> str:
        """Generate cache key for search parameters"""
        return f"search:{params.get('origin', '')}:{params.get('destination', '')}:{params.get('departure_date', '')}:{params.get('passengers', 1)}:{params.get('seat_class', 'economy')}"
    
    def get_search_stats(self) -> Dict:
        """Get search statistics"""
        try:
            # Create session
            session = self.Session()
            
            # Get total searches
            total_searches = session.query(SearchQuery).count()
            
            # Get cached searches
            cached_searches = session.query(SearchQuery).filter_by(cached=1).count()
            
            # Get average search duration
            avg_duration = session.query(func.avg(SearchQuery.search_duration)).scalar() or 0
            
            # Get average results
            avg_results = session.query(func.avg(SearchQuery.result_count)).scalar() or 0
            
            return {
                'total_searches': total_searches,
                'cached_searches': cached_searches,
                'cache_hit_rate': (cached_searches / total_searches * 100) if total_searches > 0 else 0,
                'avg_search_duration': avg_duration,
                'avg_results': avg_results
            }
            
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}
        
        finally:
            session.close()
    
    def get_flight_stats(self) -> Dict:
        """Get flight statistics"""
        try:
            # Create session
            session = self.Session()
            
            # Get total flights
            total_flights = session.query(Flight).count()
            
            # Get unique routes
            unique_routes = session.query(Flight.origin, Flight.destination).distinct().count()
            
            # Get unique airlines
            unique_airlines = session.query(Flight.airline).distinct().count()
            
            # Get average price
            avg_price = session.query(func.avg(Flight.price)).scalar() or 0
            
            return {
                'total_flights': total_flights,
                'unique_routes': unique_routes,
                'unique_airlines': unique_airlines,
                'avg_price': avg_price
            }
            
        except Exception as e:
            logger.error(f"Error getting flight stats: {e}")
            return {}
        
        finally:
            session.close()

    def get_recent_flights(self, limit: int = 100) -> List[Dict]:
        """Retrieve recently scraped flights."""
        try:
            session = self.Session()
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
                    "departure_time": f.departure_time.isoformat(),
                    "arrival_time": f.arrival_time.isoformat(),
                    "price": f.price,
                    "currency": f.currency,
                    "seat_class": f.seat_class,
                    "duration_minutes": f.duration_minutes,
                    "scraped_at": f.scraped_at.isoformat(),
                }
                for f in flights
            ]
        except Exception as e:
            logger.error(f"Error retrieving recent flights: {e}")
            return []
        finally:
            session.close()

    async def get_cached_search(self, search_key: str) -> Optional[Dict]:
        """Get cached search results"""
        try:
            cached = self.redis.get(f"search:{search_key}")
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting cached search: {e}")
            return None

    async def get_historical_prices(self, route: str, days_back: int = 365) -> List[Dict]:
        """Get historical price data for ML training"""
        try:
            session = self.Session()
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            results = session.query(FlightPriceHistory).join(Flight).filter(
                Flight.origin + '-' + Flight.destination == route,
                FlightPriceHistory.recorded_at >= cutoff_date
            ).all()
            
            return [
                {
                    'date': r.recorded_at.date(),
                    'price': float(r.price),
                    'currency': r.currency
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error getting historical prices: {e}")
            return []
        finally:
            session.close()

    async def get_current_price(self, route: str) -> float:
        """Get current average price for route"""
        try:
            session = self.Session()
            
            # Parse route
            origin, destination = route.split('-')
            
            # Get recent prices (last 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            
            result = session.query(func.avg(Flight.price)).filter(
                Flight.origin == origin,
                Flight.destination == destination,
                Flight.scraped_at >= cutoff
            ).scalar()
            
            return float(result) if result else 0.0
            
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 0.0
        finally:
            session.close()

    async def get_search_count(self, route: str) -> int:
        """Get search count for route popularity"""
        try:
            session = self.Session()
            
            # Parse route
            origin, destination = route.split('-')
            
            count = session.query(SearchQuery).filter(
                SearchQuery.origin == origin,
                SearchQuery.destination == destination
            ).count()
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting search count: {e}")
            return 0
        finally:
            session.close()

    async def store_flights(self, flights: Dict[str, List[Dict]]):
        """Store flight data in database."""
        try:
            session = self.Session()
            now = datetime.now()

            for _, site_flights in flights.items():
                for flight_data in site_flights:
                    # Calculate duration if not provided
                    if (
                        'duration_minutes' not in flight_data
                        and 'departure_time' in flight_data
                        and 'arrival_time' in flight_data
                    ):
                        duration = (
                            flight_data['arrival_time'] - flight_data['departure_time']
                        ).total_seconds() / 60
                        flight_data['duration_minutes'] = int(duration)

                    required_fields = (
                        'airline',
                        'flight_number',
                        'origin',
                        'destination',
                        'departure_time',
                        'arrival_time',
                        'price',
                        'currency',
                        'seat_class',
                        'duration_minutes',
                        'source_url',
                    )
                    if not all(k in flight_data for k in required_fields):
                        logger.error('Missing required flight fields')
                        continue

                    # Convert all datetime objects in raw_data to isoformat strings
                    def convert_dt(obj):
                        if isinstance(obj, dt.datetime):
                            return obj.isoformat()
                        if isinstance(obj, dict):
                            return {k: convert_dt(v) for k, v in obj.items()}
                        if isinstance(obj, list):
                            return [convert_dt(i) for i in obj]
                        return obj

                    raw_data_serializable = convert_dt(copy.deepcopy(flight_data))
                    flight_id = (
                        f"{flight_data.get('airline', '')}_{flight_data.get('flight_number', '')}"
                        f"_{flight_data.get('origin', '')}_{flight_data.get('destination', '')}"
                        f"_{flight_data.get('departure_time', now).isoformat()}"
                    )

                    existing = session.query(Flight).filter_by(flight_id=flight_id).first()

                    if existing:
                        if existing.price != flight_data.get('price', 0):
                            price_history = FlightPriceHistory(
                                flight_id=flight_id,
                                price=flight_data.get('price', 0),
                                currency=flight_data.get('currency', 'IRR'),
                                recorded_at=now,
                            )
                            session.add(price_history)

                        existing.price = flight_data.get('price', 0)
                        existing.currency = flight_data.get('currency', 'IRR')
                        existing.scraped_at = now
                        existing.raw_data = raw_data_serializable
                    else:
                        flight = Flight(
                            flight_id=flight_id,
                            airline=flight_data.get('airline', ''),
                            flight_number=flight_data.get('flight_number', ''),
                            origin=flight_data.get('origin', ''),
                            destination=flight_data.get('destination', ''),
                            departure_time=flight_data.get('departure_time', now),
                            arrival_time=flight_data.get('arrival_time', now),
                            price=flight_data.get('price', 0),
                            currency=flight_data.get('currency', 'IRR'),
                            seat_class=flight_data.get('seat_class', 'economy'),
                            aircraft_type=flight_data.get('aircraft_type'),
                            duration_minutes=flight_data.get('duration_minutes', 0),
                            flight_type=flight_data.get('flight_type', 'direct'),
                            scraped_at=now,
                            source_url=flight_data.get('source_url', ''),
                            raw_data=raw_data_serializable,
                        )
                        session.add(flight)

                        price_history = FlightPriceHistory(
                            flight_id=flight_id,
                            price=flight_data.get('price', 0),
                            currency=flight_data.get('currency', 'IRR'),
                            recorded_at=now,
                        )
                        session.add(price_history)

            session.commit()
        except Exception as e:
            logger.error(f"Error storing flights: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    async def cache_search_results(self, search_params: Dict, results: Dict):
        """Cache search results in Redis"""
        try:
            search_key = self._generate_search_key(search_params)
            self.redis.setex(
                f"search:{search_key}",
                timedelta(hours=1),  # Cache for 1 hour
                json.dumps(results, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching search results: {e}")

    def _generate_search_key(self, search_params: Dict) -> str:
        """Generate cache key for search"""
        return f"{search_params['origin']}_{search_params['destination']}_{search_params['departure_date']}"

    async def add_crawl_route(self, origin: str, destination: str) -> int:
        """Add a new crawl route and return its ID"""
        session = self.Session()
        try:
            route = CrawlRoute(origin=origin, destination=destination)
            session.add(route)
            session.commit()
            return route.id
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding crawl route: {e}")
            raise
        finally:
            session.close()

    async def delete_crawl_route(self, route_id: int) -> bool:
        """Delete a crawl route by ID"""
        session = self.Session()
        try:
            route = session.query(CrawlRoute).filter_by(id=route_id).first()
            if not route:
                return False
            session.delete(route)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting crawl route: {e}")
            return False
        finally:
            session.close()

    async def get_active_routes(self) -> List[Dict]:
        """Retrieve active crawl routes"""
        session = self.Session()
        try:
            routes = session.query(CrawlRoute).filter_by(is_active=True).all()
            return [
                {"id": r.id, "origin": r.origin, "destination": r.destination}
                for r in routes
            ]
        except Exception as e:
            logger.error(f"Error getting crawl routes: {e}")
            return []
        finally:
            session.close()

    async def get_airports(self, search: str = "", country: str | None = None, limit: int = 1000) -> List[Dict]:
        """Retrieve airports from the database with optional filtering."""
        session = self.Session()
        try:
            query = session.query(Airport)
            if search:
                like = f"%{search}%"
                query = query.filter(
                    (Airport.city.ilike(like))
                    | (Airport.name.ilike(like))
                    | (Airport.iata.ilike(like))
                    | (Airport.icao.ilike(like))
                )
            if country:
                query = query.filter(Airport.country == country)
            airports = query.order_by(Airport.name).limit(limit).all()
            return [
                {
                    "iata": a.iata,
                    "icao": a.icao,
                    "name": a.name,
                    "city": a.city,
                    "country": a.country,
                    "type": a.type,
                }
                for a in airports
            ]
        except Exception as e:
            logger.error(f"Error getting airports: {e}")
            return []
        finally:
            session.close()

    async def get_countries(self) -> List[str]:
        """Return list of distinct countries from airports table."""
        session = self.Session()
        try:
            rows = session.query(Airport.country).distinct().all()
            return [r[0] for r in rows if r[0]]
        except Exception as e:
            logger.error(f"Error getting countries: {e}")
            return []
        finally:
            session.close()
