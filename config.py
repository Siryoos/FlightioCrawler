import os
from dataclasses import dataclass, field
from typing import List, Dict, Any
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Production site endpoints used for validation
PRODUCTION_SITES = {
    "flytoday": {
        "base_url": "https://www.flytoday.ir",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "alibaba": {
        "base_url": "https://www.alibaba.ir",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "safarmarket": {
        "base_url": "https://www.safarmarket.com",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "mz724": {
        "base_url": "https://www.mz724.com",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "partocrs": {
        "base_url": "https://www.partocrs.com",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "partoticket": {
        "base_url": "https://www.partoticket.com",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "bookcharter724": {
        "base_url": "https://www.bookcharter724.ir",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "bookcharter": {
        "base_url": "https://www.bookcharter.ir",
        "search_endpoint": "/flight/search",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        },
    },
    "pegasus": {
        "base_url": "https://www.flypgs.com",
        "search_endpoint": "/en",
        "crawler_type": "javascript_heavy",
        "rate_limit": 2.0,
        "max_retries": 3,
        "timeout": 30,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; FlightCrawler/1.0)",
            "Accept": "application/json, text/html",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
}

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
    URL: str = field(init=False)

    def __post_init__(self) -> None:
        """Construct the Redis connection URL from components."""
        auth = f":{self.PASSWORD}@" if self.PASSWORD else ""
        self.URL = f"redis://{auth}{self.HOST}:{self.PORT}/{self.DB}"

@dataclass
class CrawlerConfig:
    DOMAINS: List[str] = field(default_factory=lambda: [
        'flightio.com',
        'flytoday.ir',
        'alibaba.ir',
        'safarmarket.com',
        'mz724.ir',
        'partocrs.com',
        'parto-ticket.ir',
        'bookcharter724.ir',
        'bookcharter.ir',
        'mrbilit.com',
        'snapptrip.com'
    ])
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RATE_LIMIT: Dict[str, int] = field(default_factory=lambda: {
        'flytoday.ir': 2,  # requests per second
        'alibaba.ir': 2,
        'safarmarket.com': 2,
        'mz724.ir': 2,
        'flightio.com': 2,
        'partocrs.com': 2,
        'parto-ticket.ir': 2,
        'bookcharter724.ir': 2,
        'bookcharter.ir': 2,
        'mrbilit.com': 2,
        'snapptrip.com': 2
    })
    USER_AGENTS: List[str] = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
    ])

@dataclass
class MonitoringConfig:
    ENABLED: bool = True
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    METRICS_PORT: int = 9090
    HEALTH_CHECK_PORT: int = 8000
    LOG_FILE: str = 'flight_crawler.log'

@dataclass
class ErrorConfig:
    """Configuration for error handling and circuit breaker."""
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300  # seconds

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
    ERROR: ErrorConfig = field(default_factory=ErrorConfig)
    ML: MLConfig = field(default_factory=MLConfig)
    
    # API Configuration
    API_VERSION: str = 'v1'
    API_PREFIX: str = f'/api/{API_VERSION}'
    API_HOST: str = os.getenv('API_HOST', '0.0.0.0')
    API_PORT: int = int(os.getenv('API_PORT', '8000'))
    API_WORKERS: int = int(os.getenv('API_WORKERS', '1'))
    
    # Security
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Cache Configuration
    CACHE_TTL: int = 3600  # 1 hour in seconds
    
    # Search Configuration
    MAX_SEARCH_RESULTS: int = 100
    DEFAULT_SORT_BY: str = 'price'
    DEFAULT_SORT_ORDER: str = 'asc'

    # Misc settings
    CRAWLER_TIMEOUT: int = 30

    # Populated after initialization
    REDIS_URL: str = field(init=False, default="")

    # Will be populated after initialization
    SITES: Dict[str, Dict[str, Any]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.SITES = self._load_site_configs()
        self.REDIS_URL = self.REDIS.URL

    def _load_site_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load site configuration files and build rate limit settings."""
        sites: Dict[str, Dict[str, Any]] = {}
        base_dir = Path(__file__).parent / "config" / "site_configs"
        for domain in self.CRAWLER.DOMAINS:
            file_name = domain.replace('.', '_') + '.json'
            path = base_dir / file_name
            site_cfg: Dict[str, Any] = {}
            if path.exists() and path.stat().st_size > 2:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        site_cfg = json.load(f)
                except Exception:
                    site_cfg = {}
            rate_info = site_cfg.get('rate_limiting', {})
            rate_limit = rate_info.get('requests_per_second', self.CRAWLER.RATE_LIMIT.get(domain, 2))
            rate_period = rate_info.get('cooldown_period', 60)
            sites[domain] = {
                'rate_limit': rate_limit,
                'rate_period': rate_period,
                **site_cfg,
            }
        return sites

# Create global config instance
config = Config()
REDIS_URL = config.REDIS_URL

# Export configuration
__all__ = ['config', 'PRODUCTION_SITES', 'REDIS_URL']
