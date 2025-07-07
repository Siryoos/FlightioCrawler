-- Migration: Add Authentication and Security Tables
-- Description: Add comprehensive authentication, authorization, and security tracking tables
-- Created: 2025-07-05
-- Author: FlightioCrawler Team
-- Dependencies: 000_create_migration_system, 001_add_performance_indexes

-- Start transaction
BEGIN;

-- Log migration start
SELECT migration_system.log_migration_start('002_add_authentication_tables', 'apply');

-- Create authentication schema
CREATE SCHEMA IF NOT EXISTS auth;

-- Users table
CREATE TABLE IF NOT EXISTS auth.users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User roles table
CREATE TABLE IF NOT EXISTS auth.roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User role assignments
CREATE TABLE IF NOT EXISTS auth.user_roles (
    user_role_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES auth.roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_by UUID REFERENCES auth.users(user_id),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, role_id)
);

-- API keys table
CREATE TABLE IF NOT EXISTS auth.api_keys (
    api_key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    permissions JSONB DEFAULT '[]',
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 3600,
    rate_limit_per_day INTEGER DEFAULT 86400,
    allowed_ips JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS auth.sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),
    location_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS auth.password_reset_tokens (
    token_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Email verification tokens
CREATE TABLE IF NOT EXISTS auth.email_verification_tokens (
    token_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Security events table
CREATE TABLE IF NOT EXISTS auth.security_events (
    event_id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    event_data JSONB,
    risk_score INTEGER DEFAULT 0,
    blocked BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    notes TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Login analytics table
CREATE TABLE IF NOT EXISTS auth.login_analytics (
    analytics_id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE CASCADE,
    login_successful BOOLEAN NOT NULL,
    ip_address INET,
    country VARCHAR(2),
    city VARCHAR(100),
    user_agent TEXT,
    device_type VARCHAR(50),
    browser VARCHAR(50),
    os VARCHAR(50),
    is_mobile BOOLEAN DEFAULT FALSE,
    is_bot BOOLEAN DEFAULT FALSE,
    risk_indicators JSONB,
    session_duration INTEGER,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rate limiting table
CREATE TABLE IF NOT EXISTS auth.rate_limits (
    limit_id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) NOT NULL, -- IP, user_id, api_key, etc.
    limit_type VARCHAR(50) NOT NULL,  -- 'login', 'api', 'password_reset', etc.
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_size_seconds INTEGER NOT NULL,
    request_count INTEGER DEFAULT 0,
    limit_exceeded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(identifier, limit_type, window_start)
);

-- Audit log table
CREATE TABLE IF NOT EXISTS auth.audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(user_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users (email);
CREATE INDEX IF NOT EXISTS idx_users_username ON auth.users (username);
CREATE INDEX IF NOT EXISTS idx_users_active ON auth.users (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_last_login ON auth.users (last_login);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON auth.user_roles (user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON auth.user_roles (role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_active ON auth.user_roles (is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON auth.api_keys (user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON auth.api_keys (key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON auth.api_keys (is_active) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON auth.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON auth.sessions (session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON auth.sessions (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON auth.sessions (expires_at);

CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON auth.security_events (user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON auth.security_events (event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_occurred_at ON auth.security_events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_security_events_severity ON auth.security_events (severity);

CREATE INDEX IF NOT EXISTS idx_login_analytics_user_id ON auth.login_analytics (user_id);
CREATE INDEX IF NOT EXISTS idx_login_analytics_occurred_at ON auth.login_analytics (occurred_at);
CREATE INDEX IF NOT EXISTS idx_login_analytics_ip ON auth.login_analytics (ip_address);

CREATE INDEX IF NOT EXISTS idx_rate_limits_identifier ON auth.rate_limits (identifier, limit_type);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON auth.rate_limits (window_start, window_size_seconds);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON auth.audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON auth.audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_log_occurred_at ON auth.audit_log (occurred_at);

-- Insert default roles
INSERT INTO auth.roles (role_name, description, is_system_role) VALUES
('admin', 'System Administrator', TRUE),
('user', 'Regular User', TRUE),
('api_user', 'API Access User', TRUE),
('crawler_operator', 'Crawler Operator', TRUE),
('analytics_viewer', 'Analytics Viewer', TRUE)
ON CONFLICT (role_name) DO NOTHING;

-- Create functions for security
CREATE OR REPLACE FUNCTION auth.hash_password(password TEXT)
RETURNS TEXT AS $$
BEGIN
    -- In production, use proper password hashing library
    RETURN crypt(password, gen_salt('bf', 12));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION auth.verify_password(password TEXT, hash TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN hash = crypt(password, hash);
END;
$$ LANGUAGE plpgsql;

-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION auth.cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM auth.sessions 
    WHERE expires_at < NOW() OR last_activity < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to log security events
CREATE OR REPLACE FUNCTION auth.log_security_event(
    p_user_id UUID,
    p_event_type VARCHAR(50),
    p_event_category VARCHAR(50),
    p_severity VARCHAR(20),
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_event_data JSONB DEFAULT NULL,
    p_risk_score INTEGER DEFAULT 0
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO auth.security_events (
        user_id, event_type, event_category, severity, 
        ip_address, user_agent, event_data, risk_score
    ) VALUES (
        p_user_id, p_event_type, p_event_category, p_severity,
        p_ip_address, p_user_agent, p_event_data, p_risk_score
    );
END;
$$ LANGUAGE plpgsql;

-- Function to check rate limits
CREATE OR REPLACE FUNCTION auth.check_rate_limit(
    p_identifier VARCHAR(255),
    p_limit_type VARCHAR(50),
    p_window_seconds INTEGER,
    p_max_requests INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    current_window_start TIMESTAMP WITH TIME ZONE;
    current_count INTEGER;
BEGIN
    -- Calculate current window start
    current_window_start := date_trunc('minute', NOW()) - 
                           (EXTRACT(EPOCH FROM date_trunc('minute', NOW())) % p_window_seconds) * INTERVAL '1 second';
    
    -- Get current count for this window
    SELECT COALESCE(request_count, 0) INTO current_count
    FROM auth.rate_limits
    WHERE identifier = p_identifier
      AND limit_type = p_limit_type
      AND window_start = current_window_start;
    
    -- Check if limit exceeded
    IF current_count >= p_max_requests THEN
        RETURN FALSE;
    END IF;
    
    -- Increment counter
    INSERT INTO auth.rate_limits (identifier, limit_type, window_start, window_size_seconds, request_count)
    VALUES (p_identifier, p_limit_type, current_window_start, p_window_seconds, 1)
    ON CONFLICT (identifier, limit_type, window_start)
    DO UPDATE SET 
        request_count = auth.rate_limits.request_count + 1,
        updated_at = NOW();
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updating timestamps
CREATE OR REPLACE FUNCTION auth.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION auth.update_timestamp();

CREATE TRIGGER update_api_keys_timestamp
    BEFORE UPDATE ON auth.api_keys
    FOR EACH ROW
    EXECUTE FUNCTION auth.update_timestamp();

CREATE TRIGGER update_rate_limits_timestamp
    BEFORE UPDATE ON auth.rate_limits
    FOR EACH ROW
    EXECUTE FUNCTION auth.update_timestamp();

-- Create views for common queries
CREATE OR REPLACE VIEW auth.user_summary AS
SELECT 
    u.user_id,
    u.username,
    u.email,
    u.first_name,
    u.last_name,
    u.is_active,
    u.email_verified,
    u.last_login,
    u.created_at,
    array_agg(r.role_name) FILTER (WHERE ur.is_active = TRUE) as roles,
    COUNT(s.session_id) as active_sessions,
    COUNT(ak.api_key_id) FILTER (WHERE ak.is_active = TRUE) as active_api_keys
FROM auth.users u
LEFT JOIN auth.user_roles ur ON u.user_id = ur.user_id AND ur.is_active = TRUE
LEFT JOIN auth.roles r ON ur.role_id = r.role_id
LEFT JOIN auth.sessions s ON u.user_id = s.user_id AND s.is_active = TRUE
LEFT JOIN auth.api_keys ak ON u.user_id = ak.user_id AND ak.is_active = TRUE
GROUP BY u.user_id, u.username, u.email, u.first_name, u.last_name, 
         u.is_active, u.email_verified, u.last_login, u.created_at;

-- Grant permissions
GRANT USAGE ON SCHEMA auth TO public;
GRANT SELECT ON auth.user_summary TO public;

-- Create auth admin role
CREATE ROLE auth_admin;
GRANT ALL PRIVILEGES ON SCHEMA auth TO auth_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth TO auth_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA auth TO auth_admin;

-- Apply migration
SELECT migration_system.apply_migration(
    '002_add_authentication_tables',
    'Add comprehensive authentication, authorization, and security tracking tables',
    NULL
);

COMMIT;

-- Display success message
SELECT 'Authentication tables created successfully' as status;
SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'auth'; 