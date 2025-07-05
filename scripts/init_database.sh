#!/bin/bash

# Database Initialization Script for FlightIO Crawler
# This script initializes the database with all required schemas and migrations

set -e

# Configuration
DEFAULT_CONFIG="development"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MIGRATIONS_DIR="${PROJECT_ROOT}/migrations"
LOG_FILE="${PROJECT_ROOT}/database_init.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")
            echo -e "${GREEN}[INFO]${NC} $message"
            ;;
        "WARN")
            echo -e "${YELLOW}[WARN]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
        "DEBUG")
            echo -e "${BLUE}[DEBUG]${NC} $message"
            ;;
    esac
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Help function
show_help() {
    cat << EOF
Database Initialization Script for FlightIO Crawler

Usage: $0 [OPTIONS]

Options:
    -c, --config ENV        Configuration environment (development, staging, production)
    -f, --force             Force initialization even if database exists
    -v, --verbose           Enable verbose logging
    -h, --help              Show this help message

Examples:
    $0 --config development
    $0 --config production --force
    $0 -c staging -v

EOF
}

# Load database configuration
load_db_config() {
    local config_name="$1"
    local config_file="${PROJECT_ROOT}/config/${config_name}.env"
    
    if [[ -f "$config_file" ]]; then
        log "INFO" "Loading configuration from $config_file"
        source "$config_file"
    else
        log "WARN" "Configuration file not found: $config_file"
        log "INFO" "Using environment variables as fallback"
    fi
    
    # Set defaults if not specified
    export DB_HOST="${DB_HOST:-localhost}"
    export DB_PORT="${DB_PORT:-5432}"
    export DB_NAME="${DB_NAME:-flightio_crawler}"
    export DB_USER="${DB_USER:-postgres}"
    export DB_PASSWORD="${DB_PASSWORD:-postgres}"
    export DB_SSLMODE="${DB_SSLMODE:-prefer}"
    
    log "INFO" "Database configuration:"
    log "INFO" "  Host: $DB_HOST"
    log "INFO" "  Port: $DB_PORT"
    log "INFO" "  Database: $DB_NAME"
    log "INFO" "  User: $DB_USER"
    log "INFO" "  SSL Mode: $DB_SSLMODE"
}

# Check if database exists
database_exists() {
    local db_name="$1"
    
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$db_name'" 2>/dev/null | grep -q 1
}

# Create database
create_database() {
    local db_name="$1"
    
    if database_exists "$db_name"; then
        log "INFO" "Database '$db_name' already exists"
        return 0
    fi
    
    log "INFO" "Creating database '$db_name'..."
    
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
        "CREATE DATABASE \"$db_name\"" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "Database '$db_name' created successfully"
        return 0
    else
        log "ERROR" "Failed to create database '$db_name'"
        return 1
    fi
}

# Execute SQL file
execute_sql_file() {
    local sql_file="$1"
    local description="$2"
    
    log "INFO" "Executing $description: $(basename "$sql_file")"
    
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -f "$sql_file" 2>/dev/null
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "$description completed successfully"
        return 0
    else
        log "ERROR" "$description failed"
        return 1
    fi
}

# Check if migration is applied
is_migration_applied() {
    local version="$1"
    
    local result=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT migration_system.is_migration_applied('$version')" 2>/dev/null)
    
    [[ "$result" == "t" ]]
}

# Run base initialization
run_base_initialization() {
    log "INFO" "Running base database initialization..."
    
    # Try full init.sql first, then fallback to init_simple.sql
    for init_file in "init.sql" "init_simple.sql"; do
        local full_path="${PROJECT_ROOT}/${init_file}"
        
        if [[ -f "$full_path" ]]; then
            log "INFO" "Using initialization file: $init_file"
            execute_sql_file "$full_path" "Base initialization"
            return $?
        fi
    done
    
    log "ERROR" "No initialization files found (init.sql or init_simple.sql)"
    return 1
}

# Run migrations
run_migrations() {
    log "INFO" "Running database migrations..."
    
    if [[ ! -d "$MIGRATIONS_DIR" ]]; then
        log "WARN" "Migrations directory not found: $MIGRATIONS_DIR"
        return 0
    fi
    
    local applied_count=0
    
    # Get migration files sorted by version
    for migration_file in "$MIGRATIONS_DIR"/*.sql; do
        if [[ ! -f "$migration_file" ]]; then
            continue
        fi
        
        local filename=$(basename "$migration_file")
        local version=$(echo "$filename" | cut -d'_' -f1)
        
        # Check if migration is already applied
        if is_migration_applied "$version"; then
            log "INFO" "Migration $version already applied, skipping"
            continue
        fi
        
        log "INFO" "Applying migration $version: $filename"
        
        if execute_sql_file "$migration_file" "Migration $version"; then
            ((applied_count++))
        else
            log "ERROR" "Failed to apply migration $version"
            return 1
        fi
    done
    
    log "INFO" "Applied $applied_count migrations successfully"
    return 0
}

# Populate initial data
populate_initial_data() {
    log "INFO" "Populating initial data..."
    
    local populate_sql="${PROJECT_ROOT}/populate_platforms.sql"
    
    if [[ -f "$populate_sql" ]]; then
        execute_sql_file "$populate_sql" "Initial data population"
        return $?
    else
        log "WARN" "Initial data file not found: $populate_sql"
        log "INFO" "Skipping initial data population"
        return 0
    fi
}

# Verify database health
verify_database_health() {
    log "INFO" "Verifying database health..."
    
    local health_check=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -tAc "SELECT migration_system.get_current_version()" 2>/dev/null)
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "Current database version: $health_check"
        
        # Get table counts
        local table_count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog')" 2>/dev/null)
        
        log "INFO" "Total tables: $table_count"
        
        # Check core tables
        for table in "platforms" "flights" "flight_prices"; do
            local count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -tAc "SELECT COUNT(*) FROM $table" 2>/dev/null)
            
            if [[ $? -eq 0 ]]; then
                log "INFO" "  $table: $count records"
            else
                log "WARN" "  $table: table not found or inaccessible"
            fi
        done
        
        return 0
    else
        log "ERROR" "Database health check failed"
        return 1
    fi
}

# Main initialization function
initialize_database() {
    local config_name="$1"
    local force="$2"
    
    log "INFO" "Initializing database for $config_name environment..."
    
    if [[ "$force" == "true" ]]; then
        log "WARN" "Force mode enabled - this may overwrite existing data"
    fi
    
    # Load configuration
    load_db_config "$config_name"
    
    # Create database if needed
    if ! create_database "$DB_NAME"; then
        return 1
    fi
    
    # Run base initialization
    if ! run_base_initialization; then
        return 1
    fi
    
    # Run migrations
    if ! run_migrations; then
        return 1
    fi
    
    # Populate initial data
    if ! populate_initial_data; then
        return 1
    fi
    
    # Verify health
    if ! verify_database_health; then
        return 1
    fi
    
    log "INFO" "Database initialization completed successfully!"
    return 0
}

# Parse command line arguments
CONFIG_NAME="$DEFAULT_CONFIG"
FORCE="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_NAME="$2"
            shift 2
            ;;
        -f|--force)
            FORCE="true"
            shift
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate configuration
if [[ ! "$CONFIG_NAME" =~ ^(development|staging|production)$ ]]; then
    log "ERROR" "Invalid configuration: $CONFIG_NAME"
    log "ERROR" "Valid options: development, staging, production"
    exit 1
fi

# Production safety check
if [[ "$CONFIG_NAME" == "production" && "$FORCE" != "true" ]]; then
    echo -e "${YELLOW}WARNING: You are about to initialize the production database!${NC}"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log "INFO" "Aborted by user"
        exit 0
    fi
fi

# Check dependencies
if ! command -v psql &> /dev/null; then
    log "ERROR" "PostgreSQL client (psql) is not installed"
    exit 1
fi

# Initialize log file
echo "Database initialization started at $(date)" > "$LOG_FILE"

# Run initialization
if initialize_database "$CONFIG_NAME" "$FORCE"; then
    echo -e "${GREEN}✅ Database initialization completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}❌ Database initialization failed!${NC}"
    echo "Check the log file for details: $LOG_FILE"
    exit 1
fi 