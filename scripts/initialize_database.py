#!/usr/bin/env python3
"""
Database Initialization Script for FlightIO Crawler

This script initializes the database with all required schemas, migrations,
and initial data for the FlightIO Crawler system.

Usage:
    python3 scripts/initialize_database.py --config development
    python3 scripts/initialize_database.py --config production --force
"""

import sys
import os
import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('database_init.log')
    ]
)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    def __init__(self, config_name: str = 'development'):
        self.config_name = config_name
        self.project_root = Path(__file__).parent.parent
        self.migrations_dir = self.project_root / 'migrations'
        self.db_config = self._load_database_config()
        
    def _load_database_config(self) -> Dict:
        """Load database configuration from environment files"""
        config_file = self.project_root / 'config' / f'{self.config_name}.env'
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_file}")
            # Use environment variables as fallback
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'flightio_crawler'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres'),
                'sslmode': os.getenv('DB_SSLMODE', 'prefer')
            }
        
        # Parse .env file
        config = {}
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip().strip('"\'')
        
        return {
            'host': config.get('DB_HOST', 'localhost'),
            'port': int(config.get('DB_PORT', '5432')),
            'database': config.get('DB_NAME', 'flightio_crawler'),
            'user': config.get('DB_USER', 'postgres'),
            'password': config.get('DB_PASSWORD', 'postgres'),
            'sslmode': config.get('DB_SSLMODE', 'prefer')
        }
    
    def get_connection(self, database: Optional[str] = None) -> psycopg2.extensions.connection:
        """Get database connection"""
        config = self.db_config.copy()
        if database:
            config['database'] = database
        
        try:
            conn = psycopg2.connect(**config)
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def database_exists(self) -> bool:
        """Check if database exists"""
        try:
            conn = self.get_connection('postgres')
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (self.db_config['database'],)
                )
                exists = cur.fetchone() is not None
            
            conn.close()
            return exists
        except psycopg2.Error as e:
            logger.error(f"Error checking database existence: {e}")
            return False
    
    def create_database(self) -> bool:
        """Create database if it doesn't exist"""
        if self.database_exists():
            logger.info(f"Database '{self.db_config['database']}' already exists")
            return True
        
        try:
            conn = self.get_connection('postgres')
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            with conn.cursor() as cur:
                cur.execute(f'CREATE DATABASE "{self.db_config["database"]}"')
                logger.info(f"Created database '{self.db_config['database']}'")
            
            conn.close()
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to create database: {e}")
            return False
    
    def get_migration_files(self) -> List[Tuple[str, Path]]:
        """Get list of migration files sorted by version"""
        migrations = []
        
        if not self.migrations_dir.exists():
            logger.warning("Migrations directory not found")
            return migrations
        
        for file_path in self.migrations_dir.glob('*.sql'):
            # Extract version from filename (e.g., "001_migration_name.sql" -> "001")
            version = file_path.stem.split('_')[0]
            migrations.append((version, file_path))
        
        # Sort by version
        migrations.sort(key=lambda x: x[0])
        return migrations
    
    def is_migration_applied(self, version: str) -> bool:
        """Check if migration is already applied"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT migration_system.is_migration_applied(%s)",
                    (version,)
                )
                result = cur.fetchone()
                conn.close()
                return result[0] if result else False
        except psycopg2.Error:
            # Migration system doesn't exist yet
            return False
    
    def apply_migration(self, version: str, file_path: Path) -> bool:
        """Apply a single migration"""
        logger.info(f"Applying migration {version}: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            conn = self.get_connection()
            start_time = time.time()
            
            with conn.cursor() as cur:
                cur.execute(sql_content)
            
            conn.commit()
            execution_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Migration {version} applied successfully in {execution_time}ms")
            conn.close()
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False
    
    def run_base_initialization(self) -> bool:
        """Run base database initialization (init.sql or init_simple.sql)"""
        logger.info("Running base database initialization...")
        
        # Try full init.sql first, then fallback to init_simple.sql
        init_files = [
            self.project_root / 'init.sql',
            self.project_root / 'init_simple.sql'
        ]
        
        for init_file in init_files:
            if init_file.exists():
                logger.info(f"Using initialization file: {init_file.name}")
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    
                    conn = self.get_connection()
                    with conn.cursor() as cur:
                        cur.execute(sql_content)
                    
                    conn.commit()
                    conn.close()
                    logger.info("Base initialization completed successfully")
                    return True
                    
                except psycopg2.Error as e:
                    logger.error(f"Failed to run base initialization: {e}")
                    return False
        
        logger.error("No initialization files found (init.sql or init_simple.sql)")
        return False
    
    def populate_initial_data(self) -> bool:
        """Populate initial data (platforms, routes, etc.)"""
        logger.info("Populating initial data...")
        
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Insert default platforms
                platforms_sql = """
                INSERT INTO platforms (platform_code, platform_name, platform_type, 
                                     base_url, supports_api, requires_persian_processing, is_active)
                VALUES 
                    ('alibaba', 'Alibaba.ir', 'iranian_airline', 'https://www.alibaba.ir', false, true, true),
                    ('flytoday', 'FlyToday', 'iranian_airline', 'https://www.flytoday.ir', false, true, true),
                    ('mahan', 'Mahan Air', 'iranian_airline', 'https://www.mahan.aero', false, true, true),
                    ('iranair', 'Iran Air', 'iranian_airline', 'https://www.iranair.com', false, true, true),
                    ('safarmarket', 'SafarMarket', 'iranian_airline', 'https://www.safarmarket.com', false, true, true),
                    ('emirates', 'Emirates', 'international_airline', 'https://www.emirates.com', true, false, true),
                    ('lufthansa', 'Lufthansa', 'international_airline', 'https://www.lufthansa.com', true, false, true),
                    ('british_airways', 'British Airways', 'international_airline', 'https://www.britishairways.com', true, false, true)
                ON CONFLICT (platform_code) DO NOTHING;
                """
                
                # Insert popular routes
                routes_sql = """
                INSERT INTO crawl_routes (origin, destination, is_active)
                VALUES 
                    ('THR', 'IST', true),
                    ('THR', 'DXB', true),
                    ('THR', 'DOH', true),
                    ('MHD', 'IST', true),
                    ('MHD', 'DXB', true),
                    ('SYZ', 'IST', true),
                    ('SYZ', 'DXB', true),
                    ('IFN', 'IST', true),
                    ('TBZ', 'IST', true),
                    ('AWZ', 'IST', true)
                ON CONFLICT (origin, destination) DO NOTHING;
                """
                
                cur.execute(platforms_sql)
                cur.execute(routes_sql)
                
                logger.info("Initial data populated successfully")
            
            conn.commit()
            conn.close()
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Failed to populate initial data: {e}")
            return False
    
    def run_migrations(self) -> bool:
        """Run all pending migrations"""
        logger.info("Running database migrations...")
        
        migrations = self.get_migration_files()
        if not migrations:
            logger.warning("No migration files found")
            return True
        
        applied_count = 0
        for version, file_path in migrations:
            if self.is_migration_applied(version):
                logger.info(f"Migration {version} already applied, skipping")
                continue
            
            if not self.apply_migration(version, file_path):
                logger.error(f"Failed to apply migration {version}")
                return False
            
            applied_count += 1
        
        logger.info(f"Applied {applied_count} migrations successfully")
        return True
    
    def verify_database_health(self) -> bool:
        """Verify database health and structure"""
        logger.info("Verifying database health...")
        
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if migration system exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = 'migration_system' 
                        AND table_name = 'schema_migrations'
                    )
                """)
                migration_system_exists = cur.fetchone()[0]
                
                if migration_system_exists:
                    # Get migration status
                    cur.execute("SELECT * FROM migration_system.get_db_health_summary()")
                    health_summary = cur.fetchone()
                    
                    logger.info(f"Database Health Summary:")
                    logger.info(f"  Current Version: {health_summary['current_version']}")
                    logger.info(f"  Total Migrations: {health_summary['total_migrations']}")
                    logger.info(f"  Successful Migrations: {health_summary['successful_migrations']}")
                    logger.info(f"  Failed Migrations: {health_summary['failed_migrations']}")
                    logger.info(f"  Database Size: {health_summary['database_size_mb']} MB")
                    logger.info(f"  Tables: {health_summary['table_count']}")
                    logger.info(f"  Indexes: {health_summary['index_count']}")
                else:
                    logger.warning("Migration system not found")
                
                # Check core tables
                core_tables = ['platforms', 'flights', 'flight_prices']
                for table in core_tables:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    logger.info(f"  {table}: {count} records")
            
            conn.close()
            logger.info("Database health verification completed")
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def initialize(self, force: bool = False) -> bool:
        """Run complete database initialization"""
        logger.info(f"Initializing database for {self.config_name} environment...")
        
        if force:
            logger.warning("Force mode enabled - this may overwrite existing data")
        
        # Step 1: Create database if needed
        if not self.create_database():
            return False
        
        # Step 2: Run base initialization
        if not self.run_base_initialization():
            return False
        
        # Step 3: Run migrations
        if not self.run_migrations():
            return False
        
        # Step 4: Populate initial data
        if not self.populate_initial_data():
            return False
        
        # Step 5: Verify health
        if not self.verify_database_health():
            return False
        
        logger.info("Database initialization completed successfully!")
        return True

def main():
    parser = argparse.ArgumentParser(description='Initialize FlightIO Crawler Database')
    parser.add_argument('--config', default='development', 
                       choices=['development', 'staging', 'production'],
                       help='Configuration environment')
    parser.add_argument('--force', action='store_true', 
                       help='Force initialization even if database exists')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.config == 'production' and not args.force:
        response = input("Are you sure you want to initialize production database? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    initializer = DatabaseInitializer(args.config)
    
    try:
        success = initializer.initialize(args.force)
        if success:
            print("✅ Database initialization completed successfully!")
            sys.exit(0)
        else:
            print("❌ Database initialization failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Database initialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during initialization: {e}")
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 