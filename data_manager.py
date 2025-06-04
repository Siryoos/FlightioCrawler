import psycopg2
import redis
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class FlightDataManager:
    """Manages flight data storage and retrieval"""
    
    def __init__(self, db_config: Dict, redis_config: Dict):
        self.db_config = db_config
        self.redis_client = redis.Redis(**redis_config, decode_responses=True)
        self.setup_database()
    
    def setup_database(self):
        """Initialize database with proper Persian text handling"""
        schema_sql = """
        -- Enable UTF-8 support
        SET client_encoding = 'UTF8';
        
        -- Main flights table
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
            source_url TEXT,
            raw_data JSONB
        );
        
        -- Indexes for efficient querying
        CREATE INDEX IF NOT EXISTS idx_flights_route_date 
        ON flights (origin, destination, departure_time);
        
        CREATE INDEX IF NOT EXISTS idx_flights_airline 
        ON flights (airline);
        
        CREATE INDEX IF NOT EXISTS idx_flights_price 
        ON flights (price);
        
        CREATE INDEX IF NOT EXISTS idx_flights_scraped 
        ON flights (scraped_at);
        
        -- Price history for tracking fluctuations
        CREATE TABLE IF NOT EXISTS flight_price_history (
            id BIGSERIAL PRIMARY KEY,
            flight_id VARCHAR(100) REFERENCES flights(flight_id),
            price DECIMAL(12,2),
            currency VARCHAR(3),
            scraped_at TIMESTAMPTZ DEFAULT NOW(),
            source VARCHAR(50)
        );
        
        -- Search queries log
        CREATE TABLE IF NOT EXISTS search_queries (
            id BIGSERIAL PRIMARY KEY,
            origin VARCHAR(10),
            destination VARCHAR(10),
            departure_date DATE,
            return_date DATE,
            passengers INTEGER,
            query_time TIMESTAMPTZ DEFAULT NOW(),
            results_count INTEGER
        );
        """
        
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                conn.commit()
    
    async def store_flights(self, flights: List[FlightData]) -> int:
        """Store flight data with deduplication"""
        stored_count = 0
        
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                for flight in flights:
                    try:
                        # Check if flight already exists
                        cur.execute(
                            "SELECT id FROM flights WHERE flight_id = %s",
                            (flight.flight_id,)
                        )
                        
                        if cur.fetchone():
                            # Update existing flight
                            cur.execute("""
                                UPDATE flights SET
                                    price = %s,
                                    scraped_at = %s
                                WHERE flight_id = %s
                            """, (flight.price, flight.scraped_at, flight.flight_id))
                        else:
                            # Insert new flight
                            cur.execute("""
                                INSERT INTO flights (
                                    flight_id, airline, flight_number, origin, destination,
                                    departure_time, arrival_time, price, currency, seat_class,
                                    aircraft_type, duration_minutes, flight_type, scraped_at, source_url
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                flight.flight_id, flight.airline, flight.flight_number,
                                flight.origin, flight.destination, flight.departure_time,
                                flight.arrival_time, flight.price, flight.currency, flight.seat_class,
                                flight.aircraft_type, flight.duration_minutes, flight.flight_type,
                                flight.scraped_at, flight.source_url
                            ))
                            stored_count += 1
                        
                        # Store price history
                        cur.execute("""
                            INSERT INTO flight_price_history (flight_id, price, currency, source)
                            VALUES (%s, %s, %s, %s)
                        """, (flight.flight_id, flight.price, flight.currency, flight.source_url))
                        
                    except Exception as e:
                        print(f"Error storing flight {flight.flight_id}: {e}")
                        continue
                
                conn.commit()
        
        return stored_count
    
    def search_flights(self, search_params: Dict) -> List[Dict]:
        """Search stored flight data"""
        query = """
        SELECT flight_id, airline, flight_number, origin, destination,
               departure_time, arrival_time, price, currency, seat_class,
               duration_minutes, flight_type, source_url
        FROM flights
        WHERE origin = %s AND destination = %s
        """
        params = [search_params['origin'], search_params['destination']]
        
        # Add date filter if provided
        if 'departure_date' in search_params:
            query += " AND DATE(departure_time) = %s"
            params.append(search_params['departure_date'])
        
        # Add price range filter
        if 'max_price' in search_params:
            query += " AND price <= %s"
            params.append(search_params['max_price'])
        
        # Order by price
        query += " ORDER BY price ASC, departure_time ASC"
        
        with psycopg2.connect(**self.db_config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                columns = [desc[0] for desc in cur.description]
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        return results
    
    def cache_search_results(self, search_key: str, results: List[Dict], ttl: int = 3600):
        """Cache search results in Redis"""
        self.redis_client.setex(
            f"search:{search_key}",
            ttl,
            json.dumps(results, default=str)
        )
    
    def get_cached_search(self, search_key: str) -> Optional[List[Dict]]:
        """Retrieve cached search results"""
        cached_data = self.redis_client.get(f"search:{search_key}")
        if cached_data:
            return json.loads(cached_data)
        return None 