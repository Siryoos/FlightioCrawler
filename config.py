import os
from typing import Dict, List, Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flightio")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "flightio")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    
    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Crawler settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CRAWLER_CONCURRENCY: int = int(os.getenv("CRAWLER_CONCURRENCY", "3"))
    CRAWLER_TIMEOUT: int = int(os.getenv("CRAWLER_TIMEOUT", "30"))
    CRAWLER_RETRY_ATTEMPTS: int = int(os.getenv("CRAWLER_RETRY_ATTEMPTS", "3"))
    
    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_WORKERS: int = int(os.getenv("API_WORKERS", "4"))
    
    # Proxy settings
    PROXIES: List[str] = [
        "http://proxy1.example.com:8080",
        "http://proxy2.example.com:8080",
        "http://proxy3.example.com:8080"
    ]
    
    # Rate limiting settings
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "3600"))
    
    # Cache settings
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    
    # Site settings
    SITES: Dict[str, Dict] = {
        "flytoday.ir": {
            "name": "FlyToday",
            "url": "https://www.flytoday.ir",
            "rate_limit": 100,
            "rate_period": 3600
        },
        "alibaba.ir": {
            "name": "Alibaba",
            "url": "https://www.alibaba.ir",
            "rate_limit": 100,
            "rate_period": 3600
        },
        "safarmarket.com": {
            "name": "SafarMarket",
            "url": "https://www.safarmarket.com",
            "rate_limit": 100,
            "rate_period": 3600
        }
    }
    
    # Browser settings
    BROWSER: Dict = {
        "headless": True,
        "timeout": 30000,
        "viewport_width": 1920,
        "viewport_height": 1080,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Error handling settings
    ERROR: Dict = {
        "retry_delay": 5,
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_timeout": 300
    }
    
    # Monitoring settings
    MONITORING: Dict = {
        "enabled": True,
        "interval": 60
    }
    
    class Config:
        env_file = ".env"

# Create settings instance
config = Settings() 