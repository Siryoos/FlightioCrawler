"""
Builder Pattern implementation for complex configuration management.

This module provides builders for creating complex configurations for:
- Crawler configurations
- Adapter configurations
- Monitoring configurations
- Rate limiting configurations
- Error handling configurations
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Type
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


class ConfigurationType(Enum):
    """Types of configurations that can be built."""

    CRAWLER = "crawler"
    ADAPTER = "adapter"
    MONITORING = "monitoring"
    RATE_LIMITING = "rate_limiting"
    ERROR_HANDLING = "error_handling"
    EXTRACTION = "extraction"
    VALIDATION = "validation"


@dataclass
class RateLimitingConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 2.0
    burst_limit: int = 5
    cooldown_period: int = 60
    backoff_factor: float = 1.5
    max_backoff_time: int = 300
    per_domain_limits: Dict[str, float] = field(default_factory=dict)
    enable_adaptive_rate_limiting: bool = True


@dataclass
class ErrorHandlingConfig:
    """Configuration for error handling."""

    max_retries: int = 3
    retry_delay: float = 5.0
    exponential_backoff: bool = True
    backoff_factor: float = 2.0
    max_retry_delay: float = 300.0
    circuit_breaker: Dict[str, Any] = field(default_factory=dict)
    timeout_settings: Dict[str, int] = field(default_factory=dict)
    ignored_errors: List[str] = field(default_factory=list)
    critical_errors: List[str] = field(default_factory=list)


@dataclass
class MonitoringConfig:
    """Configuration for monitoring."""

    enabled: bool = True
    log_level: str = "INFO"
    metrics_enabled: bool = True
    events_enabled: bool = True
    database_logging: bool = False
    alert_thresholds: Dict[str, float] = field(default_factory=dict)
    performance_monitoring: bool = True
    health_check_interval: int = 60
    metrics_retention_days: int = 30


@dataclass
class ExtractionConfig:
    """Configuration for data extraction."""

    search_form: Dict[str, str] = field(default_factory=dict)
    results_parsing: Dict[str, str] = field(default_factory=dict)
    wait_strategies: Dict[str, Any] = field(default_factory=dict)
    language_settings: Dict[str, str] = field(default_factory=dict)
    text_processing: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationConfig:
    """Configuration for data validation."""

    required_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, str] = field(default_factory=dict)
    value_ranges: Dict[str, Dict[str, float]] = field(default_factory=dict)
    regex_patterns: Dict[str, str] = field(default_factory=dict)
    custom_validators: List[str] = field(default_factory=list)
    strict_validation: bool = True
    allow_partial_data: bool = False


@dataclass
class AdapterConfig:
    """Complete adapter configuration."""

    base_url: str
    currency: str
    adapter_type: str
    airline_name: str
    features: List[str] = field(default_factory=list)
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)
    error_handling: ErrorHandlingConfig = field(default_factory=ErrorHandlingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    extraction_config: ExtractionConfig = field(default_factory=ExtractionConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    custom_settings: Dict[str, Any] = field(default_factory=dict)


class ConfigurationBuilder(ABC):
    """Abstract base class for configuration builders."""

    def __init__(self):
        self.reset()

    @abstractmethod
    def reset(self) -> "ConfigurationBuilder":
        """Reset the builder to initial state."""
        pass

    @abstractmethod
    def build(self) -> Dict[str, Any]:
        """Build and return the final configuration."""
        pass

    def from_dict(self, config_dict: Dict[str, Any]) -> "ConfigurationBuilder":
        """Load configuration from dictionary."""
        return self

    def from_file(self, file_path: Union[str, Path]) -> "ConfigurationBuilder":
        """Load configuration from file."""
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)
                self.from_dict(config_dict)
        except Exception as e:
            logger.error(f"Error loading config from file {file_path}: {e}")
        return self


class RateLimitingConfigBuilder(ConfigurationBuilder):
    """Builder for rate limiting configurations."""

    def reset(self) -> "RateLimitingConfigBuilder":
        """Reset to default rate limiting configuration."""
        self._config = RateLimitingConfig()
        return self

    def with_requests_per_second(self, rps: float) -> "RateLimitingConfigBuilder":
        """Set requests per second."""
        self._config.requests_per_second = rps
        return self

    def with_burst_limit(self, limit: int) -> "RateLimitingConfigBuilder":
        """Set burst limit."""
        self._config.burst_limit = limit
        return self

    def with_cooldown_period(self, period: int) -> "RateLimitingConfigBuilder":
        """Set cooldown period in seconds."""
        self._config.cooldown_period = period
        return self

    def with_backoff_settings(
        self, factor: float, max_time: int
    ) -> "RateLimitingConfigBuilder":
        """Set backoff settings."""
        self._config.backoff_factor = factor
        self._config.max_backoff_time = max_time
        return self

    def with_domain_limit(self, domain: str, rps: float) -> "RateLimitingConfigBuilder":
        """Set per-domain rate limit."""
        self._config.per_domain_limits[domain] = rps
        return self

    def with_adaptive_rate_limiting(
        self, enabled: bool = True
    ) -> "RateLimitingConfigBuilder":
        """Enable/disable adaptive rate limiting."""
        self._config.enable_adaptive_rate_limiting = enabled
        return self

    def for_persian_sites(self) -> "RateLimitingConfigBuilder":
        """Configure for Persian sites (conservative settings)."""
        return (
            self.with_requests_per_second(1.5)
            .with_burst_limit(3)
            .with_cooldown_period(90)
            .with_adaptive_rate_limiting(True)
        )

    def for_international_sites(self) -> "RateLimitingConfigBuilder":
        """Configure for international sites (standard settings)."""
        return (
            self.with_requests_per_second(2.0)
            .with_burst_limit(5)
            .with_cooldown_period(60)
            .with_adaptive_rate_limiting(True)
        )

    def for_aggregator_sites(self) -> "RateLimitingConfigBuilder":
        """Configure for aggregator sites (more aggressive settings)."""
        return (
            self.with_requests_per_second(3.0)
            .with_burst_limit(8)
            .with_cooldown_period(45)
            .with_adaptive_rate_limiting(True)
        )

    def build(self) -> Dict[str, Any]:
        """Build the rate limiting configuration."""
        return asdict(self._config)

    def from_dict(self, config_dict: Dict[str, Any]) -> "RateLimitingConfigBuilder":
        """Load from dictionary."""
        if "requests_per_second" in config_dict:
            self.with_requests_per_second(config_dict["requests_per_second"])
        if "burst_limit" in config_dict:
            self.with_burst_limit(config_dict["burst_limit"])
        if "cooldown_period" in config_dict:
            self.with_cooldown_period(config_dict["cooldown_period"])
        if "per_domain_limits" in config_dict:
            for domain, limit in config_dict["per_domain_limits"].items():
                self.with_domain_limit(domain, limit)
        return self


class ErrorHandlingConfigBuilder(ConfigurationBuilder):
    """Builder for error handling configurations."""

    def reset(self) -> "ErrorHandlingConfigBuilder":
        """Reset to default error handling configuration."""
        self._config = ErrorHandlingConfig()
        return self

    def with_max_retries(self, retries: int) -> "ErrorHandlingConfigBuilder":
        """Set maximum number of retries."""
        self._config.max_retries = retries
        return self

    def with_retry_delay(self, delay: float) -> "ErrorHandlingConfigBuilder":
        """Set initial retry delay."""
        self._config.retry_delay = delay
        return self

    def with_exponential_backoff(
        self, enabled: bool = True, factor: float = 2.0
    ) -> "ErrorHandlingConfigBuilder":
        """Configure exponential backoff."""
        self._config.exponential_backoff = enabled
        self._config.backoff_factor = factor
        return self

    def with_max_retry_delay(self, max_delay: float) -> "ErrorHandlingConfigBuilder":
        """Set maximum retry delay."""
        self._config.max_retry_delay = max_delay
        return self

    def with_circuit_breaker(
        self, failure_threshold: int = 5, recovery_timeout: int = 300
    ) -> "ErrorHandlingConfigBuilder":
        """Configure circuit breaker."""
        self._config.circuit_breaker = {
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "enabled": True,
        }
        return self

    def with_timeout(
        self, operation: str, timeout: int
    ) -> "ErrorHandlingConfigBuilder":
        """Set timeout for specific operation."""
        self._config.timeout_settings[operation] = timeout
        return self

    def with_ignored_error(self, error_type: str) -> "ErrorHandlingConfigBuilder":
        """Add error type to ignore list."""
        if error_type not in self._config.ignored_errors:
            self._config.ignored_errors.append(error_type)
        return self

    def with_critical_error(self, error_type: str) -> "ErrorHandlingConfigBuilder":
        """Add error type to critical list."""
        if error_type not in self._config.critical_errors:
            self._config.critical_errors.append(error_type)
        return self

    def for_production(self) -> "ErrorHandlingConfigBuilder":
        """Configure for production environment."""
        return (
            self.with_max_retries(5)
            .with_retry_delay(10.0)
            .with_exponential_backoff(True, 2.0)
            .with_max_retry_delay(600.0)
            .with_circuit_breaker(5, 300)
            .with_timeout("page_load", 30)
            .with_timeout("element_wait", 10)
            .with_timeout("request", 30)
        )

    def for_development(self) -> "ErrorHandlingConfigBuilder":
        """Configure for development environment."""
        return (
            self.with_max_retries(2)
            .with_retry_delay(5.0)
            .with_exponential_backoff(False)
            .with_max_retry_delay(60.0)
            .with_timeout("page_load", 15)
            .with_timeout("element_wait", 5)
        )

    def build(self) -> Dict[str, Any]:
        """Build the error handling configuration."""
        return asdict(self._config)

    def from_dict(self, config_dict: Dict[str, Any]) -> "ErrorHandlingConfigBuilder":
        """Load from dictionary."""
        if "max_retries" in config_dict:
            self.with_max_retries(config_dict["max_retries"])
        if "retry_delay" in config_dict:
            self.with_retry_delay(config_dict["retry_delay"])
        if "circuit_breaker" in config_dict:
            cb_config = config_dict["circuit_breaker"]
            self.with_circuit_breaker(
                cb_config.get("failure_threshold", 5),
                cb_config.get("recovery_timeout", 300),
            )
        return self


class MonitoringConfigBuilder(ConfigurationBuilder):
    """Builder for monitoring configurations."""

    def reset(self) -> "MonitoringConfigBuilder":
        """Reset to default monitoring configuration."""
        self._config = MonitoringConfig()
        return self

    def enable_monitoring(self, enabled: bool = True) -> "MonitoringConfigBuilder":
        """Enable/disable monitoring."""
        self._config.enabled = enabled
        return self

    def with_log_level(self, level: str) -> "MonitoringConfigBuilder":
        """Set log level."""
        self._config.log_level = level.upper()
        return self

    def enable_metrics(self, enabled: bool = True) -> "MonitoringConfigBuilder":
        """Enable/disable metrics collection."""
        self._config.metrics_enabled = enabled
        return self

    def enable_events(self, enabled: bool = True) -> "MonitoringConfigBuilder":
        """Enable/disable event monitoring."""
        self._config.events_enabled = enabled
        return self

    def enable_database_logging(
        self, enabled: bool = True
    ) -> "MonitoringConfigBuilder":
        """Enable/disable database logging."""
        self._config.database_logging = enabled
        return self

    def with_alert_threshold(
        self, metric: str, threshold: float
    ) -> "MonitoringConfigBuilder":
        """Set alert threshold for a metric."""
        self._config.alert_thresholds[metric] = threshold
        return self

    def enable_performance_monitoring(
        self, enabled: bool = True
    ) -> "MonitoringConfigBuilder":
        """Enable/disable performance monitoring."""
        self._config.performance_monitoring = enabled
        return self

    def with_health_check_interval(self, interval: int) -> "MonitoringConfigBuilder":
        """Set health check interval in seconds."""
        self._config.health_check_interval = interval
        return self

    def with_metrics_retention(self, days: int) -> "MonitoringConfigBuilder":
        """Set metrics retention period in days."""
        self._config.metrics_retention_days = days
        return self

    def for_production(self) -> "MonitoringConfigBuilder":
        """Configure for production monitoring."""
        return (
            self.enable_monitoring(True)
            .with_log_level("WARNING")
            .enable_metrics(True)
            .enable_events(True)
            .enable_database_logging(True)
            .enable_performance_monitoring(True)
            .with_health_check_interval(30)
            .with_metrics_retention(90)
            .with_alert_threshold("error_rate", 0.1)
            .with_alert_threshold("response_time", 30.0)
            .with_alert_threshold("success_rate", 0.8)
        )

    def for_development(self) -> "MonitoringConfigBuilder":
        """Configure for development monitoring."""
        return (
            self.enable_monitoring(True)
            .with_log_level("DEBUG")
            .enable_metrics(True)
            .enable_events(True)
            .enable_database_logging(False)
            .enable_performance_monitoring(False)
            .with_health_check_interval(60)
        )

    def build(self) -> Dict[str, Any]:
        """Build the monitoring configuration."""
        return asdict(self._config)

    def from_dict(self, config_dict: Dict[str, Any]) -> "MonitoringConfigBuilder":
        """Load from dictionary."""
        if "enabled" in config_dict:
            self.enable_monitoring(config_dict["enabled"])
        if "log_level" in config_dict:
            self.with_log_level(config_dict["log_level"])
        if "alert_thresholds" in config_dict:
            for metric, threshold in config_dict["alert_thresholds"].items():
                self.with_alert_threshold(metric, threshold)
        return self


class ExtractionConfigBuilder(ConfigurationBuilder):
    """Builder for extraction configurations."""

    def reset(self) -> "ExtractionConfigBuilder":
        """Reset to default extraction configuration."""
        self._config = ExtractionConfig()
        return self

    def with_form_field(
        self, field_name: str, selector: str
    ) -> "ExtractionConfigBuilder":
        """Add form field selector."""
        self._config.search_form[field_name] = selector
        return self

    def with_result_selector(
        self, field_name: str, selector: str
    ) -> "ExtractionConfigBuilder":
        """Add result parsing selector."""
        self._config.results_parsing[field_name] = selector
        return self

    def with_wait_strategy(
        self, element: str, strategy: Dict[str, Any]
    ) -> "ExtractionConfigBuilder":
        """Add wait strategy for element."""
        self._config.wait_strategies[element] = strategy
        return self

    def with_language_setting(
        self, setting: str, value: str
    ) -> "ExtractionConfigBuilder":
        """Add language setting."""
        self._config.language_settings[setting] = value
        return self

    def with_text_processing(
        self, processor: str, config: Dict[str, Any]
    ) -> "ExtractionConfigBuilder":
        """Add text processing configuration."""
        self._config.text_processing[processor] = config
        return self

    def for_persian_site(self) -> "ExtractionConfigBuilder":
        """Configure for Persian sites."""
        return (
            self.with_language_setting("primary", "persian")
            .with_language_setting("fallback", "english")
            .with_text_processing("persian_processor", {"enabled": True})
            .with_text_processing("number_conversion", {"persian_to_english": True})
            .with_wait_strategy("results", {"type": "presence", "timeout": 15000})
        )

    def for_international_site(self) -> "ExtractionConfigBuilder":
        """Configure for international sites."""
        return (
            self.with_language_setting("primary", "english")
            .with_text_processing("currency_detection", {"enabled": True})
            .with_text_processing("timezone_handling", {"enabled": True})
            .with_wait_strategy("results", {"type": "presence", "timeout": 10000})
        )

    def build(self) -> Dict[str, Any]:
        """Build the extraction configuration."""
        return asdict(self._config)

    def from_dict(self, config_dict: Dict[str, Any]) -> "ExtractionConfigBuilder":
        """Load from dictionary."""
        if "search_form" in config_dict:
            for field, selector in config_dict["search_form"].items():
                self.with_form_field(field, selector)
        if "results_parsing" in config_dict:
            for field, selector in config_dict["results_parsing"].items():
                self.with_result_selector(field, selector)
        return self


class AdapterConfigBuilder(ConfigurationBuilder):
    """Master builder for complete adapter configurations."""

    def reset(self) -> "AdapterConfigBuilder":
        """Reset to default adapter configuration."""
        self._config = AdapterConfig(
            base_url="", currency="USD", adapter_type="generic", airline_name=""
        )

        # Initialize sub-builders
        self._rate_limiting_builder = RateLimitingConfigBuilder()
        self._error_handling_builder = ErrorHandlingConfigBuilder()
        self._monitoring_builder = MonitoringConfigBuilder()
        self._extraction_builder = ExtractionConfigBuilder()

        return self

    def with_basic_info(
        self, base_url: str, currency: str, adapter_type: str, airline_name: str
    ) -> "AdapterConfigBuilder":
        """Set basic adapter information."""
        self._config.base_url = base_url
        self._config.currency = currency
        self._config.adapter_type = adapter_type
        self._config.airline_name = airline_name
        return self

    def with_features(self, features: List[str]) -> "AdapterConfigBuilder":
        """Set adapter features."""
        self._config.features = features.copy()
        return self

    def add_feature(self, feature: str) -> "AdapterConfigBuilder":
        """Add a single feature."""
        if feature not in self._config.features:
            self._config.features.append(feature)
        return self

    def with_custom_setting(self, key: str, value: Any) -> "AdapterConfigBuilder":
        """Add custom setting."""
        self._config.custom_settings[key] = value
        return self

    def configure_rate_limiting(self, configurator: callable) -> "AdapterConfigBuilder":
        """Configure rate limiting using a configurator function."""
        configurator(self._rate_limiting_builder)
        return self

    def configure_error_handling(
        self, configurator: callable
    ) -> "AdapterConfigBuilder":
        """Configure error handling using a configurator function."""
        configurator(self._error_handling_builder)
        return self

    def configure_monitoring(self, configurator: callable) -> "AdapterConfigBuilder":
        """Configure monitoring using a configurator function."""
        configurator(self._monitoring_builder)
        return self

    def configure_extraction(self, configurator: callable) -> "AdapterConfigBuilder":
        """Configure extraction using a configurator function."""
        configurator(self._extraction_builder)
        return self

    def for_persian_airline(
        self, base_url: str, airline_name: str
    ) -> "AdapterConfigBuilder":
        """Configure for Persian airline."""
        return (
            self.with_basic_info(base_url, "IRR", "persian", airline_name)
            .add_feature("persian_text_processing")
            .add_feature("domestic_routes")
            .configure_rate_limiting(lambda b: b.for_persian_sites())
            .configure_error_handling(lambda b: b.for_production())
            .configure_monitoring(lambda b: b.for_production())
            .configure_extraction(lambda b: b.for_persian_site())
        )

    def for_international_airline(
        self, base_url: str, airline_name: str, currency: str = "USD"
    ) -> "AdapterConfigBuilder":
        """Configure for international airline."""
        return (
            self.with_basic_info(base_url, currency, "international", airline_name)
            .add_feature("multi_currency")
            .add_feature("international_routes")
            .configure_rate_limiting(lambda b: b.for_international_sites())
            .configure_error_handling(lambda b: b.for_production())
            .configure_monitoring(lambda b: b.for_production())
            .configure_extraction(lambda b: b.for_international_site())
        )

    def for_aggregator(
        self, base_url: str, platform_name: str, currency: str = "IRR"
    ) -> "AdapterConfigBuilder":
        """Configure for aggregator platform."""
        return (
            self.with_basic_info(base_url, currency, "aggregator", platform_name)
            .add_feature("aggregator")
            .add_feature("multiple_sources")
            .add_feature("price_comparison")
            .configure_rate_limiting(lambda b: b.for_aggregator_sites())
            .configure_error_handling(lambda b: b.for_production())
            .configure_monitoring(lambda b: b.for_production())
        )

    def for_development(self) -> "AdapterConfigBuilder":
        """Configure for development environment."""
        self.configure_error_handling(lambda b: b.for_development())
        self.configure_monitoring(lambda b: b.for_development())
        return self

    def build(self) -> Dict[str, Any]:
        """Build the complete adapter configuration."""
        # Build sub-configurations
        self._config.rate_limiting = RateLimitingConfig(
            **self._rate_limiting_builder.build()
        )
        self._config.error_handling = ErrorHandlingConfig(
            **self._error_handling_builder.build()
        )
        self._config.monitoring = MonitoringConfig(**self._monitoring_builder.build())
        self._config.extraction_config = ExtractionConfig(
            **self._extraction_builder.build()
        )

        return asdict(self._config)

    def from_dict(self, config_dict: Dict[str, Any]) -> "AdapterConfigBuilder":
        """Load from dictionary."""
        if "base_url" in config_dict:
            self._config.base_url = config_dict["base_url"]
        if "currency" in config_dict:
            self._config.currency = config_dict["currency"]
        if "adapter_type" in config_dict:
            self._config.adapter_type = config_dict["adapter_type"]
        if "airline_name" in config_dict:
            self._config.airline_name = config_dict["airline_name"]
        if "features" in config_dict:
            self._config.features = config_dict["features"]

        # Load sub-configurations
        if "rate_limiting" in config_dict:
            self._rate_limiting_builder.from_dict(config_dict["rate_limiting"])
        if "error_handling" in config_dict:
            self._error_handling_builder.from_dict(config_dict["error_handling"])
        if "monitoring" in config_dict:
            self._monitoring_builder.from_dict(config_dict["monitoring"])
        if "extraction_config" in config_dict:
            self._extraction_builder.from_dict(config_dict["extraction_config"])

        return self


class ConfigurationDirector:
    """Director that orchestrates complex configuration building."""

    def __init__(self):
        self.builder = AdapterConfigBuilder()

    def build_mahan_air_config(self) -> Dict[str, Any]:
        """Build configuration for Mahan Air."""
        return (
            self.builder.reset()
            .for_persian_airline("https://www.mahan.aero", "Mahan Air")
            .add_feature("loyalty_program")
            .add_feature("charter_flights")
            .with_custom_setting("flight_number_prefix", "W5")
            .configure_extraction(
                lambda b: b.with_form_field("origin_field", "#origin-input")
                .with_form_field("destination_field", "#destination-input")
                .with_form_field("date_field", "#departure-date")
                .with_result_selector("flight_number", ".flight-number")
                .with_result_selector("price", ".price-amount")
                .with_result_selector("departure_time", ".departure-time")
            )
            .build()
        )

    def build_lufthansa_config(self) -> Dict[str, Any]:
        """Build configuration for Lufthansa."""
        return (
            self.builder.reset()
            .for_international_airline("https://www.lufthansa.com", "Lufthansa", "EUR")
            .add_feature("star_alliance")
            .add_feature("premium_service")
            .with_custom_setting("alliance", "Star Alliance")
            .configure_extraction(
                lambda b: b.with_form_field(
                    "origin_field", "[data-testid='origin-input']"
                )
                .with_form_field(
                    "destination_field", "[data-testid='destination-input']"
                )
                .with_form_field("date_field", "[data-testid='departure-date']")
                .with_result_selector("flight_number", "[data-testid='flight-number']")
                .with_result_selector("price", "[data-testid='price']")
            )
            .build()
        )

    def build_alibaba_config(self) -> Dict[str, Any]:
        """Build configuration for Alibaba aggregator."""
        return (
            self.builder.reset()
            .for_aggregator("https://www.alibaba.ir", "Alibaba.ir", "IRR")
            .add_feature("domestic_flights")
            .add_feature("international_flights")
            .add_feature("hotel_booking")
            .configure_extraction(
                lambda b: b.with_form_field("origin_field", ".origin-input")
                .with_form_field("destination_field", ".destination-input")
                .with_result_selector("source_airline", ".source-airline")
                .with_result_selector("booking_reference", ".booking-ref")
            )
            .build()
        )


# Convenience functions
def create_rate_limiting_config() -> RateLimitingConfigBuilder:
    """Create a rate limiting config builder."""
    return RateLimitingConfigBuilder()


def create_error_handling_config() -> ErrorHandlingConfigBuilder:
    """Create an error handling config builder."""
    return ErrorHandlingConfigBuilder()


def create_monitoring_config() -> MonitoringConfigBuilder:
    """Create a monitoring config builder."""
    return MonitoringConfigBuilder()


def create_extraction_config() -> ExtractionConfigBuilder:
    """Create an extraction config builder."""
    return ExtractionConfigBuilder()


def create_adapter_config() -> AdapterConfigBuilder:
    """Create an adapter config builder."""
    return AdapterConfigBuilder()


def get_configuration_director() -> ConfigurationDirector:
    """Get configuration director for pre-built configurations."""
    return ConfigurationDirector()
