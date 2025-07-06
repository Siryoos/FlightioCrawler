"""
Unified Configuration Schema

This module provides a unified configuration schema that supports all three
crawler systems (requests, adapters, crawlers) with backward compatibility
and system-specific configurations.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Union, Type
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Configuration-related errors."""
    pass

class BrowserType(Enum):
    """Supported browser types."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"
    SAFARI = "safari"
    HEADLESS_CHROME = "headless_chrome"
    HEADLESS_FIREFOX = "headless_firefox"

class CrawlerMode(Enum):
    """Crawler operation modes."""
    SYNC = "sync"
    ASYNC = "async"
    HYBRID = "hybrid"
    AUTO = "auto"

class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    CUSTOM = "custom"

class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class BrowserConfig:
    """Browser-specific configuration."""
    type: BrowserType = BrowserType.CHROME
    headless: bool = True
    user_agent: Optional[str] = None
    window_size: tuple = (1920, 1080)
    page_load_timeout: int = 30
    implicit_wait: int = 10
    explicit_wait: int = 30
    
    # Chrome-specific options
    chrome_options: List[str] = field(default_factory=lambda: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-images"
    ])
    
    # Firefox-specific options
    firefox_options: List[str] = field(default_factory=list)
    
    # Driver paths
    driver_path: Optional[str] = None
    auto_download_driver: bool = True
    
    # Proxy configuration
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    def to_selenium_options(self) -> Dict[str, Any]:
        """Convert to Selenium options format."""
        options = {
            "headless": self.headless,
            "window_size": self.window_size,
            "page_load_timeout": self.page_load_timeout,
            "implicit_wait": self.implicit_wait,
            "explicit_wait": self.explicit_wait
        }
        
        if self.user_agent:
            options["user_agent"] = self.user_agent
        
        if self.driver_path:
            options["driver_path"] = self.driver_path
        
        if self.proxy_host:
            options["proxy"] = {
                "host": self.proxy_host,
                "port": self.proxy_port,
                "username": self.proxy_username,
                "password": self.proxy_password
            }
        
        return options

@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    
    # Adaptive rate limiting
    adaptive: bool = True
    min_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    # Burst protection
    burst_limit: int = 10
    burst_window: int = 60
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "delay": self.min_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "jitter": self.jitter
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "adaptive": self.adaptive,
            "min_delay": self.min_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor
        }

@dataclass
class RetryConfig:
    """Retry configuration."""
    enabled: bool = True
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    # Retry conditions
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True
    retry_on_http_error: bool = True
    retry_on_rate_limit: bool = True
    retry_http_codes: List[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "max_retries": self.max_retries,
            "backoff_factor": self.backoff_factor,
            "retry_on_timeout": self.retry_on_timeout,
            "retry_on_connection_error": self.retry_on_connection_error
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "max_retries": self.max_retries,
            "strategy": self.strategy.value,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "jitter": self.jitter,
            "retry_http_codes": self.retry_http_codes
        }

@dataclass
class SessionConfig:
    """Session management configuration."""
    # HTTP session settings
    session_timeout: int = 300
    connection_timeout: int = 30
    read_timeout: int = 30
    max_connections: int = 100
    max_connections_per_host: int = 10
    
    # Cookie and session persistence
    enable_cookies: bool = True
    cookie_jar_path: Optional[str] = None
    session_persistence: bool = False
    session_file_path: Optional[str] = None
    
    # Headers
    default_headers: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    
    # SSL/TLS settings
    verify_ssl: bool = True
    ssl_context: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "timeout": self.connection_timeout,
            "headers": self.default_headers,
            "verify": self.verify_ssl,
            "cookies": self.enable_cookies
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "session_timeout": self.session_timeout,
            "connection_timeout": self.connection_timeout,
            "read_timeout": self.read_timeout,
            "max_connections": self.max_connections,
            "default_headers": self.default_headers,
            "verify_ssl": self.verify_ssl
        }

@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration."""
    enabled: bool = True
    log_level: LogLevel = LogLevel.INFO
    log_file: Optional[str] = None
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Performance monitoring
    track_performance: bool = True
    performance_log_file: Optional[str] = None
    
    # Memory monitoring
    track_memory: bool = True
    memory_threshold_mb: int = 1000
    memory_warning_threshold_mb: int = 500
    
    # Health checks
    health_check_enabled: bool = True
    health_check_interval: int = 300
    health_check_timeout: int = 10
    
    # Metrics collection
    collect_metrics: bool = True
    metrics_file: Optional[str] = None
    metrics_format: str = "json"
    
    # Error tracking
    track_errors: bool = True
    error_log_file: Optional[str] = None
    error_threshold: int = 10
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "log_level": self.log_level.value,
            "log_file": self.log_file,
            "track_performance": self.track_performance
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "enabled": self.enabled,
            "log_level": self.log_level.value,
            "track_performance": self.track_performance,
            "track_memory": self.track_memory,
            "memory_threshold_mb": self.memory_threshold_mb,
            "health_check_enabled": self.health_check_enabled,
            "collect_metrics": self.collect_metrics
        }

@dataclass
class CacheConfig:
    """Caching configuration."""
    enabled: bool = True
    cache_dir: str = "./cache"
    cache_size_mb: int = 1000
    cache_ttl_hours: int = 24
    
    # Cache strategies
    cache_responses: bool = True
    cache_parsed_data: bool = True
    cache_images: bool = False
    cache_static_assets: bool = False
    
    # Cache invalidation
    auto_cleanup: bool = True
    cleanup_interval_hours: int = 6
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "enabled": self.enabled,
            "cache_dir": self.cache_dir,
            "cache_responses": self.cache_responses
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "enabled": self.enabled,
            "cache_dir": self.cache_dir,
            "cache_size_mb": self.cache_size_mb,
            "cache_ttl_hours": self.cache_ttl_hours,
            "cache_responses": self.cache_responses,
            "cache_parsed_data": self.cache_parsed_data
        }

@dataclass
class SiteSpecificConfig:
    """Site-specific configuration."""
    site_name: str
    base_url: str
    enabled: bool = True
    
    # Site-specific settings
    custom_headers: Dict[str, str] = field(default_factory=dict)
    custom_cookies: Dict[str, str] = field(default_factory=dict)
    custom_user_agent: Optional[str] = None
    
    # Parsing configuration
    parsing_rules: Dict[str, Any] = field(default_factory=dict)
    data_extraction_rules: Dict[str, Any] = field(default_factory=dict)
    
    # Rate limiting override
    rate_limit_override: Optional[RateLimitConfig] = None
    
    # Retry configuration override
    retry_override: Optional[RetryConfig] = None
    
    # Browser configuration override
    browser_override: Optional[BrowserConfig] = None
    
    def merge_with_global(self, global_config: 'UnifiedConfig') -> 'UnifiedConfig':
        """Merge site-specific config with global config."""
        merged_config = UnifiedConfig()
        
        # Start with global config
        merged_config.__dict__.update(global_config.__dict__)
        
        # Override with site-specific settings
        if self.rate_limit_override:
            merged_config.rate_limit = self.rate_limit_override
        
        if self.retry_override:
            merged_config.retry = self.retry_override
        
        if self.browser_override:
            merged_config.browser = self.browser_override
        
        # Merge headers
        merged_config.session.default_headers.update(self.custom_headers)
        
        # Set site-specific values
        merged_config.site_name = self.site_name
        merged_config.base_url = self.base_url
        
        return merged_config

@dataclass
class UnifiedConfig:
    """
    Unified configuration that supports all three crawler systems.
    Provides backward compatibility and system-specific configurations.
    """
    # System identification
    system_type: str = "unified"
    crawler_mode: CrawlerMode = CrawlerMode.AUTO
    
    # Site information
    site_name: Optional[str] = None
    base_url: Optional[str] = None
    
    # Core configurations
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    # Site-specific configurations
    site_configs: Dict[str, SiteSpecificConfig] = field(default_factory=dict)
    
    # Advanced settings
    debug_mode: bool = False
    test_mode: bool = False
    dry_run: bool = False
    
    # Threading and concurrency
    max_workers: int = 4
    max_concurrent_requests: int = 10
    
    # Data processing
    data_format: str = "json"
    output_file: Optional[str] = None
    
    # Persian text processing
    persian_text_processing: bool = True
    normalize_persian: bool = True
    
    # Error handling
    continue_on_error: bool = True
    error_threshold: int = 10
    
    # Progress reporting
    progress_reporting: bool = True
    progress_callback: Optional[str] = None
    
    def get_site_config(self, site_name: str) -> Optional[SiteSpecificConfig]:
        """Get configuration for a specific site."""
        return self.site_configs.get(site_name)
    
    def add_site_config(self, config: SiteSpecificConfig):
        """Add site-specific configuration."""
        self.site_configs[config.site_name] = config
    
    def to_requests_format(self) -> Dict[str, Any]:
        """Convert to requests system format."""
        return {
            "browser": self.browser.to_selenium_options(),
            "rate_limit": self.rate_limit.to_requests_format(),
            "retry": self.retry.to_requests_format(),
            "session": self.session.to_requests_format(),
            "monitoring": self.monitoring.to_requests_format(),
            "cache": self.cache.to_requests_format(),
            "debug_mode": self.debug_mode,
            "max_workers": self.max_workers,
            "output_file": self.output_file,
            "continue_on_error": self.continue_on_error,
            "progress_reporting": self.progress_reporting
        }
    
    def to_adapters_format(self) -> Dict[str, Any]:
        """Convert to adapters system format."""
        return {
            "system_type": self.system_type,
            "crawler_mode": self.crawler_mode.value,
            "site_name": self.site_name,
            "base_url": self.base_url,
            "rate_limit": self.rate_limit.to_adapters_format(),
            "retry": self.retry.to_adapters_format(),
            "session": self.session.to_adapters_format(),
            "monitoring": self.monitoring.to_adapters_format(),
            "cache": self.cache.to_adapters_format(),
            "debug_mode": self.debug_mode,
            "test_mode": self.test_mode,
            "max_concurrent_requests": self.max_concurrent_requests,
            "data_format": self.data_format,
            "persian_text_processing": self.persian_text_processing,
            "normalize_persian": self.normalize_persian,
            "continue_on_error": self.continue_on_error,
            "error_threshold": self.error_threshold
        }
    
    def to_crawlers_format(self) -> dict:
        """Convert to crawlers system format."""
        return {
            "site_name": self.site_name,
            "base_url": self.base_url,
            "browser_config": asdict(self.browser),
            "rate_limit_config": asdict(self.rate_limit),
            "retry_config": asdict(self.retry),
            "session_config": asdict(self.session),
            "debug_mode": self.debug_mode,
            "max_workers": self.max_workers,
            "data_format": self.data_format,
            "output_file": self.output_file
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def save_to_file(self, filepath: str):
        """Save configuration to file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedConfig':
        """Create configuration from dictionary."""
        config = cls()
        
        # Handle nested configurations
        if 'browser' in data:
            config.browser = BrowserConfig(**data['browser'])
        if 'rate_limit' in data:
            config.rate_limit = RateLimitConfig(**data['rate_limit'])
        if 'retry' in data:
            config.retry = RetryConfig(**data['retry'])
        if 'session' in data:
            config.session = SessionConfig(**data['session'])
        if 'monitoring' in data:
            config.monitoring = MonitoringConfig(**data['monitoring'])
        if 'cache' in data:
            config.cache = CacheConfig(**data['cache'])
        
        # Handle site-specific configurations
        if 'site_configs' in data:
            for site_name, site_data in data['site_configs'].items():
                config.site_configs[site_name] = SiteSpecificConfig(**site_data)
        
        # Handle other fields
        for key, value in data.items():
            if key not in ['browser', 'rate_limit', 'retry', 'session', 'monitoring', 'cache', 'site_configs']:
                if hasattr(config, key):
                    setattr(config, key, value)
        
        return config
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UnifiedConfig':
        """Create configuration from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_file(cls, filepath: str) -> 'UnifiedConfig':
        """Load configuration from file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Validate browser configuration
        if self.browser.type == BrowserType.CHROME and not self.browser.chrome_options:
            errors.append("Chrome browser requires chrome_options")
        
        # Validate rate limiting
        if self.rate_limit.enabled and self.rate_limit.requests_per_minute <= 0:
            errors.append("Rate limit requests_per_minute must be positive")
        
        # Validate retry configuration
        if self.retry.enabled and self.retry.max_retries < 0:
            errors.append("Retry max_retries must be non-negative")
        
        # Validate session configuration
        if self.session.connection_timeout <= 0:
            errors.append("Session connection_timeout must be positive")
        
        # Validate monitoring configuration
        if self.monitoring.enabled and self.monitoring.memory_threshold_mb <= 0:
            errors.append("Monitoring memory_threshold_mb must be positive")
        
        # Validate cache configuration
        if self.cache.enabled and self.cache.cache_size_mb <= 0:
            errors.append("Cache cache_size_mb must be positive")
        
        # Validate concurrency settings
        if self.max_workers <= 0:
            errors.append("max_workers must be positive")
        
        if self.max_concurrent_requests <= 0:
            errors.append("max_concurrent_requests must be positive")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

class ConfigurationManager:
    """
    Manages configuration loading, validation, and conversion between systems.
    """
    
    def __init__(self, config_dir: str = "./config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._cache: Dict[str, UnifiedConfig] = {}
        
    def load_config(self, config_name: str = "default") -> UnifiedConfig:
        """Load configuration by name."""
        if config_name in self._cache:
            return self._cache[config_name]
        
        config_file = self.config_dir / f"{config_name}.json"
        
        if config_file.exists():
            try:
                config = UnifiedConfig.from_file(str(config_file))
                self._cache[config_name] = config
                return config
            except Exception as e:
                logger.error(f"Failed to load config {config_name}: {e}")
                raise ConfigurationError(f"Failed to load config {config_name}: {e}")
        else:
            # Create default configuration
            config = UnifiedConfig()
            self.save_config(config, config_name)
            self._cache[config_name] = config
            return config
    
    def save_config(self, config: UnifiedConfig, config_name: str = "default"):
        """Save configuration by name."""
        config_file = self.config_dir / f"{config_name}.json"
        
        try:
            config.save_to_file(str(config_file))
            self._cache[config_name] = config
            logger.info(f"Configuration saved: {config_name}")
        except Exception as e:
            logger.error(f"Failed to save config {config_name}: {e}")
            raise ConfigurationError(f"Failed to save config {config_name}: {e}")
    
    def get_site_config(self, site_name: str, base_config: str = "default") -> UnifiedConfig:
        """Get configuration for a specific site."""
        base = self.load_config(base_config)
        
        if site_name in base.site_configs:
            return base.site_configs[site_name].merge_with_global(base)
        
        return base
    
    def create_site_config(self, site_name: str, base_url: str, 
                          custom_settings: Optional[Dict[str, Any]] = None) -> SiteSpecificConfig:
        """Create site-specific configuration."""
        site_config = SiteSpecificConfig(
            site_name=site_name,
            base_url=base_url
        )
        
        if custom_settings:
            for key, value in custom_settings.items():
                if hasattr(site_config, key):
                    setattr(site_config, key, value)
        
        return site_config
    
    def validate_config(self, config: UnifiedConfig) -> bool:
        """Validate configuration."""
        errors = config.validate()
        if errors:
            for error in errors:
                logger.error(f"Configuration validation error: {error}")
            return False
        return True
    
    def convert_legacy_config(self, legacy_config: Dict[str, Any], 
                            system_type: str) -> UnifiedConfig:
        """Convert legacy configuration to unified format."""
        config = UnifiedConfig()
        
        if system_type == "requests":
            # Convert requests system config
            if "browser" in legacy_config:
                config.browser = BrowserConfig(**legacy_config["browser"])
            if "rate_limit" in legacy_config:
                config.rate_limit = RateLimitConfig(**legacy_config["rate_limit"])
            # Add more conversions as needed
        
        elif system_type == "adapters":
            # Convert adapters system config
            if "site_name" in legacy_config:
                config.site_name = legacy_config["site_name"]
            if "base_url" in legacy_config:
                config.base_url = legacy_config["base_url"]
            # Add more conversions as needed
        
        elif system_type == "crawlers":
            # Convert crawlers system config
            if "site_name" in legacy_config:
                config.site_name = legacy_config["site_name"]
            if "browser_config" in legacy_config:
                config.browser = BrowserConfig(**legacy_config["browser_config"])
            # Add more conversions as needed
        
        return config
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get configuration from environment variables."""
        env_config = {}
        
        # Browser settings
        if os.getenv("CRAWLER_BROWSER_TYPE"):
            env_config["browser_type"] = os.getenv("CRAWLER_BROWSER_TYPE")
        if os.getenv("CRAWLER_HEADLESS"):
            env_config["headless"] = os.getenv("CRAWLER_HEADLESS").lower() == "true"
        
        # Rate limiting
        if os.getenv("CRAWLER_RATE_LIMIT_RPM"):
            env_config["requests_per_minute"] = int(os.getenv("CRAWLER_RATE_LIMIT_RPM"))
        
        # Retry settings
        if os.getenv("CRAWLER_MAX_RETRIES"):
            env_config["max_retries"] = int(os.getenv("CRAWLER_MAX_RETRIES"))
        
        # Monitoring
        if os.getenv("CRAWLER_LOG_LEVEL"):
            env_config["log_level"] = os.getenv("CRAWLER_LOG_LEVEL")
        
        # Debug mode
        if os.getenv("CRAWLER_DEBUG"):
            env_config["debug_mode"] = os.getenv("CRAWLER_DEBUG").lower() == "true"
        
        return env_config
    
    def merge_configs(self, base_config: UnifiedConfig, 
                     override_config: Dict[str, Any]) -> UnifiedConfig:
        """Merge base configuration with override values."""
        merged_dict = base_config.to_dict()
        
        # Deep merge override values
        def deep_merge(base: Dict, override: Dict) -> Dict:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    base[key] = deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        merged_dict = deep_merge(merged_dict, override_config)
        return UnifiedConfig.from_dict(merged_dict)

# Global configuration manager
_config_manager = ConfigurationManager()

def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager."""
    return _config_manager

def load_config(config_name: str = "default") -> UnifiedConfig:
    """Load configuration by name."""
    return get_config_manager().load_config(config_name)

def get_site_config(site_name: str, base_config: str = "default") -> UnifiedConfig:
    """Get configuration for a specific site."""
    return get_config_manager().get_site_config(site_name, base_config) 