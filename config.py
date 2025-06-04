import os
from dataclasses import dataclass, field
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
    DOMAINS: List[str] = field(default_factory=lambda: [
        'flytoday.ir',
        'alibaba.ir',
        'safarmarket.com',
        'mz724.ir',
        'partocrs.com',
        'parto-ticket.ir',
        'bookcharter724.ir',
        'bookcharter.ir'
    ])
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RATE_LIMIT: Dict[str, int] = field(default_factory=lambda: {
        'flytoday.ir': 2,  # requests per second
        'alibaba.ir': 2,
        'safarmarket.com': 2,
        'mz724.ir': 2,
        'partocrs.com': 2,
        'parto-ticket.ir': 2,
        'bookcharter724.ir': 2,
        'bookcharter.ir': 2
    })
    USER_AGENTS: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
    ])

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
    FEATURE_COLUMNS: List[str] = field(default_factory=lambda: [
        'departure_time',
        'arrival_time',
        'duration_minutes',
        'airline',
        'seat_class'
    ])
    TARGET_COLUMN: str = 'price'

@dataclass
class Config:
    DATABASE: DatabaseConfig = field(default_factory=DatabaseConfig)
    REDIS: RedisConfig = field(default_factory=RedisConfig)
    CRAWLER: CrawlerConfig = field(default_factory=CrawlerConfig)
    MONITORING: MonitoringConfig = field(default_factory=MonitoringConfig)
    ML: MLConfig = field(default_factory=MLConfig)
    
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