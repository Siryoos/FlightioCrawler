-- FlightioCrawler Database Initialization Script (Simplified)
-- Compatible with standard PostgreSQL 15+

-- Enable UTF-8 support
SET client_encoding = 'UTF8';

-- Enable available extensions
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
CREATE TABLE IF NOT EXISTS platforms (
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
CREATE TABLE IF NOT EXISTS flights (
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
    price DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'IRR',
    raw_data JSONB, -- Store platform-specific raw data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Price tracking table (standard table instead of hypertable)
CREATE TABLE IF NOT EXISTS flight_prices (
    price_id BIGSERIAL PRIMARY KEY,
    flight_id BIGINT REFERENCES flights(flight_id),
    platform_id INTEGER REFERENCES platforms(platform_id),
    price DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    price_type VARCHAR(50) DEFAULT 'total', -- 'base', 'total', 'with_tax'
    fare_conditions JSONB, -- Cancellation, changes, etc.
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE
);

-- Create partitioned table for better performance
CREATE TABLE IF NOT EXISTS flight_prices_partitioned (
    LIKE flight_prices INCLUDING ALL
) PARTITION BY RANGE (scraped_at);

-- Create partitions for current and future months
CREATE TABLE flight_prices_2025_07 PARTITION OF flight_prices_partitioned
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE flight_prices_2025_08 PARTITION OF flight_prices_partitioned
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE flight_prices_2025_09 PARTITION OF flight_prices_partitioned
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');

-- Monitoring and health check tables
CREATE TABLE IF NOT EXISTS crawler_status (
    status_id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(platform_id),
    status VARCHAR(50) NOT NULL, -- 'running', 'stopped', 'error', 'rate_limited'
    last_crawl_time TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    crawl_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Error logging table
CREATE TABLE IF NOT EXISTS crawler_errors (
    error_id BIGSERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(platform_id),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_details JSONB,
    url_attempted VARCHAR(1000),
    stack_trace TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS crawler_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(platform_id),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enhanced indexing for performance
CREATE INDEX IF NOT EXISTS idx_flights_route_date ON flights (origin_airport, destination_airport, departure_time);
CREATE INDEX IF NOT EXISTS idx_flights_platform ON flights (platform_id, departure_time);
CREATE INDEX IF NOT EXISTS idx_flights_airline ON flights (airline_code, departure_time);
CREATE INDEX IF NOT EXISTS idx_flights_price ON flights (price) WHERE price IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_prices_flight_time ON flight_prices (flight_id, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_prices_platform_time ON flight_prices (platform_id, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_platforms_active ON platforms (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_platforms_type ON platforms (platform_type);

-- Indexes for Persian text search (using GIN for JSONB)
CREATE INDEX IF NOT EXISTS idx_flights_raw_data_gin ON flights USING gin (raw_data);
CREATE INDEX IF NOT EXISTS idx_crawler_status_platform ON crawler_status (platform_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_crawler_errors_platform_time ON crawler_errors (platform_id, occurred_at);

-- View for latest flight prices
CREATE OR REPLACE VIEW latest_flight_prices AS
SELECT DISTINCT ON (f.flight_id) 
    f.flight_id,
    f.platform_id,
    f.airline_code,
    f.flight_number,
    f.origin_airport,
    f.destination_airport,
    f.departure_time,
    f.arrival_time,
    COALESCE(fp.price, f.price) as current_price,
    COALESCE(fp.currency, f.currency) as currency,
    COALESCE(fp.scraped_at, f.updated_at) as price_updated_at,
    p.platform_name
FROM flights f
LEFT JOIN flight_prices fp ON f.flight_id = fp.flight_id
LEFT JOIN platforms p ON f.platform_id = p.platform_id
WHERE f.departure_time > NOW()
ORDER BY f.flight_id, fp.scraped_at DESC NULLS LAST;

-- View for popular routes with statistics
CREATE OR REPLACE VIEW popular_routes_summary AS
SELECT 
    f.origin_airport,
    f.destination_airport,
    COUNT(DISTINCT f.flight_id) as flight_count,
    COUNT(DISTINCT f.platform_id) as platform_count,
    AVG(COALESCE(fp.price, f.price)) as avg_price,
    MIN(COALESCE(fp.price, f.price)) as min_price,
    MAX(COALESCE(fp.price, f.price)) as max_price,
    MAX(COALESCE(fp.scraped_at, f.updated_at)) as last_updated
FROM flights f
LEFT JOIN flight_prices fp ON f.flight_id = fp.flight_id
WHERE f.departure_time > NOW() - INTERVAL '7 days'
  AND f.departure_time < NOW() + INTERVAL '30 days'
GROUP BY f.origin_airport, f.destination_airport
HAVING COUNT(DISTINCT f.flight_id) >= 1;

-- Create function to update flight updated_at timestamp
CREATE OR REPLACE FUNCTION update_flight_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for flight updates
CREATE TRIGGER flight_update_timestamp
    BEFORE UPDATE ON flights
    FOR EACH ROW
    EXECUTE FUNCTION update_flight_timestamp();

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
    
    -- Validate airport codes (3 letter codes)
    IF NOT (NEW.origin_airport ~ '^[A-Z]{3}$' AND NEW.destination_airport ~ '^[A-Z]{3}$') THEN
        RAISE EXCEPTION 'Invalid airport code format: must be 3 uppercase letters';
    END IF;
    
    -- Validate times
    IF NEW.arrival_time <= NEW.departure_time THEN
        RAISE EXCEPTION 'Arrival time must be after departure time';
    END IF;
    
    -- Validate duration if provided
    IF NEW.duration_minutes IS NOT NULL THEN
        IF NEW.duration_minutes <= 0 OR NEW.duration_minutes > 1440 THEN
            RAISE EXCEPTION 'Invalid flight duration: must be between 1 and 1440 minutes';
        END IF;
    END IF;
    
    -- Validate price if provided
    IF NEW.price IS NOT NULL AND NEW.price <= 0 THEN
        RAISE EXCEPTION 'Price must be positive';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for flight data validation
CREATE TRIGGER validate_flight
    BEFORE INSERT OR UPDATE ON flights
    FOR EACH ROW
    EXECUTE FUNCTION validate_flight_data();

-- Create function to log crawler status
CREATE OR REPLACE FUNCTION update_crawler_status(
    p_platform_id INTEGER,
    p_status VARCHAR(50),
    p_error_message TEXT DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO crawler_status (platform_id, status, last_crawl_time, last_error, updated_at)
    VALUES (p_platform_id, p_status, NOW(), p_error_message, NOW())
    ON CONFLICT (platform_id) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        last_crawl_time = EXCLUDED.last_crawl_time,
        last_error = EXCLUDED.last_error,
        updated_at = EXCLUDED.updated_at,
        crawl_count = crawler_status.crawl_count + 1,
        success_count = CASE WHEN EXCLUDED.status = 'running' THEN crawler_status.success_count + 1 ELSE crawler_status.success_count END,
        error_count = CASE WHEN EXCLUDED.last_error IS NOT NULL THEN crawler_status.error_count + 1 ELSE crawler_status.error_count END;
END;
$$ LANGUAGE plpgsql;

-- Create unique constraint on crawler_status
ALTER TABLE crawler_status ADD CONSTRAINT unique_platform_status UNIQUE (platform_id);

-- Insert default crawl routes (major Iranian routes)
INSERT INTO crawl_routes (origin, destination) VALUES
('IKA', 'MHD'), -- Tehran to Mashhad
('IKA', 'SYZ'), -- Tehran to Shiraz
('IKA', 'ISF'), -- Tehran to Isfahan
('IKA', 'TBZ'), -- Tehran to Tabriz
('IKA', 'AWZ'), -- Tehran to Ahvaz
('IKA', 'KSH'), -- Tehran to Kermanshah
('MHD', 'IKA'), -- Mashhad to Tehran
('SYZ', 'IKA'), -- Shiraz to Tehran
('ISF', 'IKA'), -- Isfahan to Tehran
('TBZ', 'IKA'), -- Tabriz to Tehran
('AWZ', 'IKA'), -- Ahvaz to Tehran
('KSH', 'IKA'), -- Kermanshah to Tehran
('MHD', 'SYZ'), -- Mashhad to Shiraz
('SYZ', 'MHD'), -- Shiraz to Mashhad
('ISF', 'SYZ'), -- Isfahan to Shiraz
('SYZ', 'ISF'); -- Shiraz to Isfahan

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crawler TO crawler;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crawler TO crawler;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA crawler TO crawler;

-- Create read-only user for reporting
CREATE ROLE reporter WITH LOGIN PASSWORD 'report_password';
GRANT USAGE ON SCHEMA crawler TO reporter;
GRANT SELECT ON ALL TABLES IN SCHEMA crawler TO reporter;

-- Show created tables
\dt crawler.* 