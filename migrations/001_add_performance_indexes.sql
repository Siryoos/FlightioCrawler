-- Migration: Add Performance Indexes
-- Description: اضافه کردن indexes برای بهبود عملکرد کوئری‌ها
-- Created: 2024-01-01
-- Author: FlightioCrawler Team

-- شروع transaction
BEGIN;

-- اضافه کردن extension های مورد نیاز
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- بررسی وجود جداول
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'flights') THEN
        RAISE EXCEPTION 'Table flights does not exist. Please run base migration first.';
    END IF;
END $$;

-- اضافه کردن indexes جدید برای flights table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_route_date_optimized 
ON flights (origin, destination, departure_time DESC, price);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_price_range 
ON flights (price, departure_time DESC) WHERE price > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_airline_date 
ON flights (airline, departure_time DESC, origin, destination);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_scraped_at 
ON flights (scraped_at DESC);

-- اضافه کردن partial index برای پروازهای فعال
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_active_recent 
ON flights (departure_time DESC, price) 
WHERE departure_time > NOW() - INTERVAL '7 days' AND price > 0;

-- اضافه کردن BRIN index برای timestamp fields (برای جداول بزرگ)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_departure_brin 
ON flights USING BRIN (departure_time);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flights_scraped_brin 
ON flights USING BRIN (scraped_at);

-- اضافه کردن indexes برای flight_price_history table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_history_flight_recorded 
ON flight_price_history (flight_id, recorded_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_history_price_range 
ON flight_price_history (price, recorded_at DESC) WHERE price > 0;

-- اضافه کردن indexes برای search_queries table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_queries_route_date 
ON search_queries (origin, destination, query_time DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_queries_performance 
ON search_queries (query_time DESC, search_duration, cached);

-- اضافه کردن indexes برای airports table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_airports_country_city 
ON airports (country, city);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_airports_search 
ON airports USING gin (to_tsvector('english', name || ' ' || city || ' ' || country));

-- اضافه کردن statistics collection
-- تنظیم statistics برای بهبود query planning
ALTER TABLE flights ALTER COLUMN origin SET STATISTICS 500;
ALTER TABLE flights ALTER COLUMN destination SET STATISTICS 500;
ALTER TABLE flights ALTER COLUMN departure_time SET STATISTICS 500;
ALTER TABLE flights ALTER COLUMN price SET STATISTICS 500;
ALTER TABLE flights ALTER COLUMN airline SET STATISTICS 300;

-- ایجاد view برای monitoring index usage
CREATE OR REPLACE VIEW index_usage_stats AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan,
    CASE 
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'RARELY_USED'
        WHEN idx_scan < 1000 THEN 'MODERATELY_USED'
        ELSE 'HEAVILY_USED'
    END as usage_category
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- ایجاد function برای analyze tables
CREATE OR REPLACE FUNCTION analyze_flight_tables()
RETURNS void AS $$
BEGIN
    -- Analyze all flight-related tables
    ANALYZE flights;
    ANALYZE flight_price_history;
    ANALYZE search_queries;
    ANALYZE airports;
    
    -- Log completion
    RAISE NOTICE 'Table analysis completed at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- اضافه کردن triggers برای automatic statistics update
CREATE OR REPLACE FUNCTION trigger_analyze_after_bulk_insert()
RETURNS trigger AS $$
BEGIN
    -- اگر تعداد رکوردهای جدید زیاد باشد، analyze کن
    IF TG_OP = 'INSERT' THEN
        -- Check if we need to analyze (rough estimation)
        IF random() < 0.01 THEN -- 1% chance
            PERFORM analyze_flight_tables();
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- اضافه کردن trigger به flights table
DROP TRIGGER IF EXISTS trigger_analyze_flights ON flights;
CREATE TRIGGER trigger_analyze_flights
    AFTER INSERT ON flights
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analyze_after_bulk_insert();

-- ایجاد stored procedure برای index maintenance
CREATE OR REPLACE FUNCTION maintain_flight_indexes()
RETURNS void AS $$
DECLARE
    rec RECORD;
BEGIN
    -- Reindex heavily used indexes
    FOR rec IN 
        SELECT indexname 
        FROM pg_stat_user_indexes 
        WHERE schemaname = 'public' 
        AND tablename IN ('flights', 'flight_price_history')
        AND idx_scan > 10000
    LOOP
        EXECUTE format('REINDEX INDEX CONCURRENTLY %I', rec.indexname);
        RAISE NOTICE 'Reindexed %', rec.indexname;
    END LOOP;
    
    -- Update statistics
    PERFORM analyze_flight_tables();
    
    RAISE NOTICE 'Index maintenance completed at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- اضافه کردن check constraints برای data quality
ALTER TABLE flights ADD CONSTRAINT check_positive_price 
CHECK (price IS NULL OR price >= 0);

ALTER TABLE flights ADD CONSTRAINT check_valid_departure_time 
CHECK (departure_time > '2020-01-01' AND departure_time < '2030-01-01');

ALTER TABLE flights ADD CONSTRAINT check_arrival_after_departure 
CHECK (arrival_time IS NULL OR arrival_time > departure_time);

-- اضافه کردن default values برای performance
ALTER TABLE flights ALTER COLUMN scraped_at SET DEFAULT NOW();
ALTER TABLE search_queries ALTER COLUMN query_time SET DEFAULT NOW();

-- Commit transaction
COMMIT;

-- Analyze tables after index creation
SELECT analyze_flight_tables();

-- نمایش گزارش نهایی
SELECT 
    'Migration completed successfully' as status,
    NOW() as completion_time,
    (SELECT count(*) FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'flights') as flights_indexes_count,
    (SELECT count(*) FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'flight_price_history') as price_history_indexes_count; 