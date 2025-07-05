-- Migration System for FlightIO Crawler
-- Description: Create migration tracking system
-- Created: 2025-07-05
-- Author: FlightioCrawler Team

-- Start transaction
BEGIN;

-- Create schema for migration tracking
CREATE SCHEMA IF NOT EXISTS migration_system;

-- Migration tracking table
CREATE TABLE IF NOT EXISTS migration_system.schema_migrations (
    migration_id SERIAL PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    applied_by VARCHAR(100) DEFAULT current_user,
    execution_time_ms INTEGER,
    checksum VARCHAR(64),
    success BOOLEAN DEFAULT TRUE
);

-- Migration files table
CREATE TABLE IF NOT EXISTS migration_system.migration_files (
    file_id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT,
    file_size INTEGER,
    file_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_modified TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Migration execution log
CREATE TABLE IF NOT EXISTS migration_system.migration_log (
    log_id BIGSERIAL PRIMARY KEY,
    migration_version VARCHAR(50) NOT NULL,
    operation VARCHAR(20) NOT NULL, -- 'apply', 'rollback', 'verify'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'completed', 'failed'
    error_message TEXT,
    executed_by VARCHAR(100) DEFAULT current_user,
    execution_details JSONB
);

-- Database schema version tracking
CREATE TABLE IF NOT EXISTS migration_system.schema_info (
    info_id SERIAL PRIMARY KEY,
    current_version VARCHAR(50) NOT NULL,
    target_version VARCHAR(50),
    last_migration_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    database_size_mb INTEGER,
    total_tables INTEGER,
    total_indexes INTEGER,
    health_status VARCHAR(20) DEFAULT 'healthy',
    notes TEXT
);

-- Migration dependencies table
CREATE TABLE IF NOT EXISTS migration_system.migration_dependencies (
    dependency_id SERIAL PRIMARY KEY,
    migration_version VARCHAR(50) NOT NULL,
    depends_on_version VARCHAR(50) NOT NULL,
    dependency_type VARCHAR(20) DEFAULT 'hard', -- 'hard', 'soft'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(migration_version, depends_on_version)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_schema_migrations_version ON migration_system.schema_migrations (version);
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON migration_system.schema_migrations (applied_at);
CREATE INDEX IF NOT EXISTS idx_migration_log_version ON migration_system.migration_log (migration_version);
CREATE INDEX IF NOT EXISTS idx_migration_log_status ON migration_system.migration_log (status);

-- Function to get current schema version
CREATE OR REPLACE FUNCTION migration_system.get_current_version()
RETURNS VARCHAR(50) AS $$
DECLARE
    current_ver VARCHAR(50);
BEGIN
    SELECT version INTO current_ver
    FROM migration_system.schema_migrations
    ORDER BY applied_at DESC
    LIMIT 1;
    
    RETURN COALESCE(current_ver, '000');
END;
$$ LANGUAGE plpgsql;

-- Function to check if migration is already applied
CREATE OR REPLACE FUNCTION migration_system.is_migration_applied(migration_version VARCHAR(50))
RETURNS BOOLEAN AS $$
DECLARE
    found BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM migration_system.schema_migrations 
        WHERE version = migration_version AND success = TRUE
    ) INTO found;
    
    RETURN found;
END;
$$ LANGUAGE plpgsql;

-- Function to log migration start
CREATE OR REPLACE FUNCTION migration_system.log_migration_start(
    migration_version VARCHAR(50),
    operation VARCHAR(20) DEFAULT 'apply'
)
RETURNS INTEGER AS $$
DECLARE
    log_id INTEGER;
BEGIN
    INSERT INTO migration_system.migration_log (migration_version, operation, started_at)
    VALUES (migration_version, operation, NOW())
    RETURNING migration_log.log_id INTO log_id;
    
    RETURN log_id;
END;
$$ LANGUAGE plpgsql;

-- Function to log migration completion
CREATE OR REPLACE FUNCTION migration_system.log_migration_complete(
    log_id INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_msg TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE migration_system.migration_log
    SET 
        completed_at = NOW(),
        status = CASE WHEN success THEN 'completed' ELSE 'failed' END,
        error_message = error_msg
    WHERE migration_log.log_id = log_migration_complete.log_id;
END;
$$ LANGUAGE plpgsql;

-- Function to apply migration
CREATE OR REPLACE FUNCTION migration_system.apply_migration(
    migration_version VARCHAR(50),
    migration_description TEXT,
    execution_time_ms INTEGER DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    log_id INTEGER;
    migration_exists BOOLEAN;
BEGIN
    -- Check if migration already applied
    SELECT migration_system.is_migration_applied(migration_version) INTO migration_exists;
    
    IF migration_exists THEN
        RAISE NOTICE 'Migration % already applied, skipping', migration_version;
        RETURN TRUE;
    END IF;
    
    -- Log migration start
    SELECT migration_system.log_migration_start(migration_version, 'apply') INTO log_id;
    
    BEGIN
        -- Insert migration record
        INSERT INTO migration_system.schema_migrations (version, description, execution_time_ms)
        VALUES (migration_version, migration_description, execution_time_ms);
        
        -- Update schema info
        INSERT INTO migration_system.schema_info (current_version, last_migration_at)
        VALUES (migration_version, NOW())
        ON CONFLICT (info_id) DO UPDATE SET
            current_version = migration_version,
            last_migration_at = NOW();
        
        -- Log success
        PERFORM migration_system.log_migration_complete(log_id, TRUE);
        
        RAISE NOTICE 'Migration % applied successfully', migration_version;
        RETURN TRUE;
        
    EXCEPTION WHEN others THEN
        -- Log failure
        PERFORM migration_system.log_migration_complete(log_id, FALSE, SQLERRM);
        RAISE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to get migration status
CREATE OR REPLACE FUNCTION migration_system.get_migration_status()
RETURNS TABLE(
    version VARCHAR(50),
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE,
    execution_time_ms INTEGER,
    success BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.version,
        m.description,
        m.applied_at,
        m.execution_time_ms,
        m.success
    FROM migration_system.schema_migrations m
    ORDER BY m.applied_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get database health summary
CREATE OR REPLACE FUNCTION migration_system.get_db_health_summary()
RETURNS TABLE(
    current_version VARCHAR(50),
    total_migrations INTEGER,
    successful_migrations INTEGER,
    failed_migrations INTEGER,
    last_migration_at TIMESTAMP WITH TIME ZONE,
    database_size_mb BIGINT,
    table_count INTEGER,
    index_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        migration_system.get_current_version(),
        COUNT(*)::INTEGER as total_migrations,
        COUNT(CASE WHEN success THEN 1 END)::INTEGER as successful_migrations,
        COUNT(CASE WHEN NOT success THEN 1 END)::INTEGER as failed_migrations,
        MAX(applied_at) as last_migration_at,
        pg_database_size(current_database()) / 1024 / 1024 as database_size_mb,
        (SELECT COUNT(*)::INTEGER FROM information_schema.tables 
         WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'migration_system')) as table_count,
        (SELECT COUNT(*)::INTEGER FROM pg_indexes 
         WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'migration_system')) as index_count
    FROM migration_system.schema_migrations;
END;
$$ LANGUAGE plpgsql;

-- Create initial migration record
SELECT migration_system.apply_migration(
    '000_create_migration_system',
    'Create migration tracking system',
    NULL
);

-- Grant permissions
GRANT USAGE ON SCHEMA migration_system TO public;
GRANT SELECT ON ALL TABLES IN SCHEMA migration_system TO public;

-- Create roles for migration management
CREATE ROLE migration_admin;
GRANT ALL PRIVILEGES ON SCHEMA migration_system TO migration_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA migration_system TO migration_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA migration_system TO migration_admin;

COMMIT;

-- Display migration system status
SELECT 'Migration system created successfully' as status;
SELECT * FROM migration_system.get_db_health_summary(); 