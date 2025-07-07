-- Enable UTF-8 support
SET client_encoding = 'UTF8';

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS crawler;

-- Set search path
SET search_path TO crawler, public;

-- Routes configuration table
CREATE TABLE IF NOT EXISTS crawl_routes (
    route_id SERIAL PRIMARY KEY,
    origin VARCHAR(10) NOT NULL,
    destination VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Platform registry table
CREATE TABLE platforms (
    platform_id SERIAL PRIMARY KEY,
    platform_code VARCHAR(50) UNIQUE NOT NULL,
    platform_name VARCHAR(200) NOT NULL,
    platform_type VARCHAR(50) NOT NULL, -- 'iranian_airline', 'international_airline', 'aggregator'
    base_url VARCHAR(500),
    api_endpoint VARCHAR(500),
    supports_api BOOLEAN DEFAULT FALSE,
    requires_persian_processing BOOLEAN DEFAULT FALSE,
    rate_limit_config JSONB,
    anti_bot_measures JSONB,
    last_successful_crawl TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enhanced flights table with multi-platform support
CREATE TABLE flights (
    flight_id BIGSERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(platform_id),
    external_flight_id VARCHAR(200), -- Platform's internal ID
    airline_code VARCHAR(10) NOT NULL,
    flight_number VARCHAR(20) NOT NULL,
    origin_airport VARCHAR(10) NOT NULL,
    destination_airport VARCHAR(10) NOT NULL,
    departure_time TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER,
    aircraft_type VARCHAR(50),
    fare_class VARCHAR(50),
    available_seats INTEGER,
    raw_data JSONB, -- Store platform-specific raw data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Multi-platform price tracking (converted to hypertable for time-series optimization)
CREATE TABLE flight_prices (
    price_id BIGSERIAL,
    flight_id BIGINT REFERENCES flights(flight_id),
    platform_id INTEGER REFERENCES platforms(platform_id),
    price DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    price_type VARCHAR(50), -- 'base', 'total', 'with_tax'
    fare_conditions JSONB, -- Cancellation, changes, etc.
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (price_id, scraped_at)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('flight_prices', 'scraped_at');

-- Create compression policy for older price data
SELECT add_compression_policy('flight_prices', INTERVAL '7 days');

-- Enhanced indexing for multi-platform queries
CREATE INDEX idx_flights_route_date ON flights (origin_airport, destination_airport, departure_time);
CREATE INDEX idx_flights_platform ON flights (platform_id, departure_time);
CREATE INDEX idx_flights_airline ON flights (airline_code, departure_time);
CREATE INDEX idx_prices_flight_time ON flight_prices (flight_id, scraped_at DESC);
CREATE INDEX idx_prices_platform_time ON flight_prices (platform_id, scraped_at DESC);
CREATE INDEX idx_platforms_active ON platforms (is_active) WHERE is_active = TRUE;

-- Indexes for Persian text search (using GIN for JSONB)
CREATE INDEX idx_flights_raw_data_gin ON flights USING gin (raw_data);

-- Materialized view for popular routes with average prices
CREATE MATERIALIZED VIEW popular_routes_summary AS
SELECT 
    origin_airport,
    destination_airport,
    COUNT(DISTINCT flight_id) as flight_count,
    COUNT(DISTINCT platform_id) as platform_count,
    AVG(fp.price) as avg_price,
    MIN(fp.price) as min_price,
    MAX(fp.price) as max_price,
    MAX(fp.scraped_at) as last_updated
FROM flights f
JOIN flight_prices fp ON f.flight_id = fp.flight_id
WHERE fp.scraped_at > NOW() - INTERVAL '7 days'
GROUP BY origin_airport, destination_airport
HAVING COUNT(DISTINCT flight_id) >= 10;

-- Create index on materialized view
CREATE INDEX idx_popular_routes_route ON popular_routes_summary (origin_airport, destination_airport);

-- Refresh materialized view hourly
CREATE OR REPLACE FUNCTION refresh_popular_routes()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW popular_routes_summary;
END;
$$ LANGUAGE plpgsql;

-- Create function to update flight prices
CREATE OR REPLACE FUNCTION update_flight_price()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.price != OLD.price THEN
        INSERT INTO flight_prices (flight_id, platform_id, price, currency, price_type, fare_conditions)
        VALUES (NEW.flight_id, NEW.platform_id, NEW.price, NEW.currency, 'total', NEW.raw_data->'fare_conditions');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for price updates
CREATE TRIGGER flight_price_update
    AFTER UPDATE ON flights
    FOR EACH ROW
    EXECUTE FUNCTION update_flight_price();

-- Create function to validate flight data
CREATE OR REPLACE FUNCTION validate_flight_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate required fields
    IF NEW.airline_code IS NULL OR NEW.flight_number IS NULL OR 
       NEW.origin_airport IS NULL OR NEW.destination_airport IS NULL OR
       NEW.departure_time IS NULL OR NEW.arrival_time IS NULL THEN
        RAISE EXCEPTION 'Required flight fields cannot be null';
    END IF;
    
    -- Validate airport codes
    IF NOT (NEW.origin_airport ~ '^[A-Z]{3}$' AND NEW.destination_airport ~ '^[A-Z]{3}$') THEN
        RAISE EXCEPTION 'Invalid airport code format';
    END IF;
    
    -- Validate times
    IF NEW.arrival_time <= NEW.departure_time THEN
        RAISE EXCEPTION 'Arrival time must be after departure time';
    END IF;
    
    -- Validate duration if provided
    IF NEW.duration_minutes IS NOT NULL THEN
        IF NEW.duration_minutes <= 0 OR NEW.duration_minutes > 1440 THEN
            RAISE EXCEPTION 'Invalid flight duration';
        END IF;
        
        -- Cross-validate with departure/arrival times
        IF EXTRACT(EPOCH FROM (NEW.arrival_time - NEW.departure_time))/60 - NEW.duration_minutes > 60 THEN
            RAISE EXCEPTION 'Duration inconsistent with departure/arrival times';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for flight data validation
CREATE TRIGGER validate_flight
    BEFORE INSERT OR UPDATE ON flights
    FOR EACH ROW
    EXECUTE FUNCTION validate_flight_data();

-- Create roles and permissions
CREATE ROLE crawler WITH LOGIN PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crawler TO crawler;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crawler TO crawler; 