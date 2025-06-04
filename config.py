import os
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class DatabaseConfig:
    HOST: str = os.getenv('DB_HOST', 'localhost')
    NAME: str = os.getenv('DB_NAME', 'flight_data')
    USER: str = os.getenv('DB_USER', 'crawler')
    PASSWORD: str = os.getenv('DB_PASSWORD', 'secure_password')
    PORT: int = int(os.getenv('DB_PORT', '5432'))
    OPTIONS: str = '-c timezone=Asia/Tehran'

@dataclass
class RedisConfig:
    HOST: str = os.getenv('REDIS_HOST', 'localhost')
    PORT: int = int(os.getenv('REDIS_PORT', '6379'))
    DB: int = int(os.getenv('REDIS_DB', '0'))
    PASSWORD: str = os.getenv('REDIS_PASSWORD', '')

@dataclass
class CrawlerConfig:
    DOMAINS: List[str] = [
        'flytoday.ir',
        'alibaba.ir',
        'safarmarket.com'
    ]
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RATE_LIMIT: Dict[str, int] = {
        'flytoday.ir': 2,  # requests per second
        'alibaba.ir': 2,
        'safarmarket.com': 2
    }
    USER_AGENTS: List[str] = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
    ]

@dataclass
class MonitoringConfig:
    ENABLED: bool = True
    LOG_LEVEL: str = 'INFO'
    METRICS_PORT: int = 9090
    HEALTH_CHECK_PORT: int = 8000
    LOG_FILE: str = 'flight_crawler.log'

@dataclass
class MLConfig:
    MODEL_PATH: str = 'models/flight_price_predictor.pkl'
    TRAINING_DATA_PATH: str = 'data/training_data.csv'
    FEATURE_COLUMNS: List[str] = [
        'departure_time',
        'arrival_time',
        'duration_minutes',
        'airline',
        'seat_class'
    ]
    TARGET_COLUMN: str = 'price'

@dataclass
class Config:
    DATABASE: DatabaseConfig = DatabaseConfig()
    REDIS: RedisConfig = RedisConfig()
    CRAWLER: CrawlerConfig = CrawlerConfig()
    MONITORING: MonitoringConfig = MonitoringConfig()
    ML: MLConfig = MLConfig()
    
    # API Configuration
    API_VERSION: str = 'v1'
    API_PREFIX: str = f'/api/{API_VERSION}'
    
    # Security
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Cache Configuration
    CACHE_TTL: int = 3600  # 1 hour in seconds
    
    # Search Configuration
    MAX_SEARCH_RESULTS: int = 100
    DEFAULT_SORT_BY: str = 'price'
    DEFAULT_SORT_ORDER: str = 'asc'

# Create global config instance
config = Config()

# Export configuration
__all__ = ['config'] 