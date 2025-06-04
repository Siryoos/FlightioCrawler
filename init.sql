-- Enable UTF-8 support
SET client_encoding = 'UTF8';

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS crawler;

-- Set search path
SET search_path TO crawler, public;

-- Create tables
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_flights_route_date 
ON flights (origin, destination, departure_time);

CREATE INDEX IF NOT EXISTS idx_flights_airline 
ON flights (airline);

CREATE INDEX IF NOT EXISTS idx_flights_price 
ON flights (price);

CREATE INDEX IF NOT EXISTS idx_flights_scraped 
ON flights (scraped_at);

-- Price history table
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

-- Crawler metrics
CREATE TABLE IF NOT EXISTS crawler_metrics (
    id BIGSERIAL PRIMARY KEY,
    domain VARCHAR(100),
    timestamp TIMESTAMPTZ,
    total_requests INTEGER,
    success_rate DECIMAL(5,2),
    flights_scraped INTEGER,
    avg_response_time DECIMAL(10,3)
);

-- Create indexes for metrics
CREATE INDEX IF NOT EXISTS idx_metrics_domain_time 
ON crawler_metrics (domain, timestamp);

-- Create views
CREATE OR REPLACE VIEW flight_price_trends AS
SELECT 
    f.flight_id,
    f.airline,
    f.flight_number,
    f.origin,
    f.destination,
    f.departure_time,
    MIN(h.price) as min_price,
    MAX(h.price) as max_price,
    AVG(h.price) as avg_price,
    COUNT(*) as price_updates
FROM flights f
JOIN flight_price_history h ON f.flight_id = h.flight_id
GROUP BY f.flight_id, f.airline, f.flight_number, f.origin, f.destination, f.departure_time;

-- Create functions
CREATE OR REPLACE FUNCTION update_flight_price()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.price != OLD.price THEN
        INSERT INTO flight_price_history (flight_id, price, currency, source)
        VALUES (NEW.flight_id, NEW.price, NEW.currency, NEW.source_url);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER flight_price_update
    AFTER UPDATE ON flights
    FOR EACH ROW
    EXECUTE FUNCTION update_flight_price();

-- Create roles and permissions
CREATE ROLE crawler WITH LOGIN PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crawler TO crawler;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crawler TO crawler; 