"""
Design Patterns Package for FlightioCrawler

This package contains implementation of various design patterns to improve
the architecture and maintainability of the flight crawler system.

Available Patterns:
- Observer Pattern: Event management and monitoring
- Builder Pattern: Complex configuration building
- Singleton Pattern: Shared resource management
- Command Pattern: Operation encapsulation and workflow management

Usage Examples:
    # Observer Pattern
    from adapters.patterns import CrawlerEventSystem, LoggingObserver

    # Builder Pattern
    from adapters.patterns import create_adapter_config

    # Singleton Pattern
    from adapters.patterns import get_database_manager, get_cache_manager

    # Command Pattern
    from adapters.patterns import CrawlSiteCommand, CommandInvoker
"""

# Observer Pattern exports
from .observer_pattern import (
    # Core classes
    CrawlerEventSystem,
    EventSubject,
    EventObserver,
    CrawlerEvent,
    EventType,
    EventSeverity,
    # Observer implementations
    LoggingObserver,
    MetricsObserver,
    DatabaseObserver,
    AlertObserver,
    # Utility functions and context managers
    event_context,
    emit_crawl_started,
    emit_crawl_completed,
    emit_crawl_failed,
    emit_data_extracted,
    emit_error,
    emit_warning,
    emit_performance_warning,
)

# Builder Pattern exports
from .builder_pattern import (
    # Core builders
    AdapterConfigBuilder,
    RateLimitingConfigBuilder,
    ErrorHandlingConfigBuilder,
    MonitoringConfigBuilder,
    ExtractionConfigBuilder,
    ConfigurationDirector,
    # Configuration data classes
    AdapterConfig,
    RateLimitingConfig,
    ErrorHandlingConfig,
    MonitoringConfig,
    ExtractionConfig,
    ValidationConfig,
    # Utility functions
    create_adapter_config,
    create_rate_limiting_config,
    create_error_handling_config,
    create_monitoring_config,
    create_extraction_config,
    get_configuration_director,
)

# Singleton Pattern exports
from .singleton_pattern import (
    # Singleton managers
    DatabaseManager,
    ConfigurationManager,
    CacheManager,
    LoggingManager,
    ResourcePool,
    # Data classes
    DatabaseConnectionInfo,
    # Utility functions
    get_database_manager,
    get_configuration_manager,
    get_cache_manager,
    get_logging_manager,
    get_resource_pool,
    # Context managers
    managed_resources,
    # Decorators
    singleton,
)

# Command Pattern exports
from .command_pattern import (
    # Core command classes
    Command,
    CommandInvoker,
    CommandResult,
    CommandContext,
    MacroCommand,
    # Specific command implementations
    CrawlSiteCommand,
    ValidateDataCommand,
    SaveDataCommand,
    # Enums
    CommandStatus,
    CommandPriority,
    # Workflow utilities
    create_crawl_and_save_workflow,
    create_validation_workflow,
    # Context managers and utilities
    command_invoker_context,
    get_command_invoker,
)

# Package metadata
__version__ = "1.0.0"
__author__ = "FlightioCrawler Development Team"
__all__ = [
    # Observer Pattern
    "CrawlerEventSystem",
    "EventSubject",
    "EventObserver",
    "CrawlerEvent",
    "EventType",
    "EventSeverity",
    "LoggingObserver",
    "MetricsObserver",
    "DatabaseObserver",
    "AlertObserver",
    "event_context",
    "emit_crawl_started",
    "emit_crawl_completed",
    "emit_crawl_failed",
    "emit_data_extracted",
    "emit_error",
    "emit_warning",
    "emit_performance_warning",
    # Builder Pattern
    "AdapterConfigBuilder",
    "RateLimitingConfigBuilder",
    "ErrorHandlingConfigBuilder",
    "MonitoringConfigBuilder",
    "ExtractionConfigBuilder",
    "ConfigurationDirector",
    "AdapterConfig",
    "RateLimitingConfig",
    "ErrorHandlingConfig",
    "MonitoringConfig",
    "ExtractionConfig",
    "ValidationConfig",
    "create_adapter_config",
    "create_rate_limiting_config",
    "create_error_handling_config",
    "create_monitoring_config",
    "create_extraction_config",
    "get_configuration_director",
    # Singleton Pattern
    "DatabaseManager",
    "ConfigurationManager",
    "CacheManager",
    "LoggingManager",
    "ResourcePool",
    "DatabaseConnectionInfo",
    "get_database_manager",
    "get_configuration_manager",
    "get_cache_manager",
    "get_logging_manager",
    "get_resource_pool",
    "managed_resources",
    "singleton",
    # Command Pattern
    "Command",
    "CommandInvoker",
    "CommandResult",
    "CommandContext",
    "MacroCommand",
    "CrawlSiteCommand",
    "ValidateDataCommand",
    "SaveDataCommand",
    "CommandStatus",
    "CommandPriority",
    "create_crawl_and_save_workflow",
    "create_validation_workflow",
    "command_invoker_context",
    "get_command_invoker",
]


def get_pattern_info():
    """
    Get information about all available design patterns.

    Returns:
        dict: Dictionary containing pattern information
    """
    return {
        "observer_pattern": {
            "description": "Event management and monitoring system",
            "main_classes": [
                "CrawlerEventSystem",
                "LoggingObserver",
                "MetricsObserver",
            ],
            "use_cases": ["Event logging", "Performance monitoring", "Alert system"],
        },
        "builder_pattern": {
            "description": "Complex configuration building with fluent interface",
            "main_classes": ["AdapterConfigBuilder", "RateLimitingConfigBuilder"],
            "use_cases": [
                "Configuration management",
                "Settings composition",
                "Environment-specific configs",
            ],
        },
        "singleton_pattern": {
            "description": "Shared resource management with thread-safe implementations",
            "main_classes": ["DatabaseManager", "CacheManager", "ConfigurationManager"],
            "use_cases": ["Database connections", "Caching", "Global configuration"],
        },
        "command_pattern": {
            "description": "Operation encapsulation with queuing and undo capabilities",
            "main_classes": ["CrawlSiteCommand", "CommandInvoker", "MacroCommand"],
            "use_cases": [
                "Crawling operations",
                "Workflow management",
                "Operation queuing",
            ],
        },
    }


def create_integrated_crawler_system():
    """
    Create a fully integrated crawler system using all design patterns.

    This is a convenience function that sets up all the patterns to work together.

    Returns:
        dict: Dictionary containing all initialized components
    """
    from .observer_pattern import CrawlerEventSystem, LoggingObserver, MetricsObserver
    from .singleton_pattern import (
        get_database_manager,
        get_cache_manager,
        get_configuration_manager,
    )
    from .command_pattern import CommandInvoker
    from .builder_pattern import get_configuration_director

    # Initialize event system
    event_system = CrawlerEventSystem()
    event_system.add_observer(LoggingObserver())
    event_system.add_observer(MetricsObserver())

    # Initialize singleton resources
    db_manager = get_database_manager()
    cache_manager = get_cache_manager()
    config_manager = get_configuration_manager()

    # Initialize command system
    command_invoker = CommandInvoker(max_workers=4, enable_history=True)

    # Initialize configuration system
    config_director = get_configuration_director()

    return {
        "event_system": event_system,
        "database_manager": db_manager,
        "cache_manager": cache_manager,
        "configuration_manager": config_manager,
        "command_invoker": command_invoker,
        "configuration_director": config_director,
    }


# Quick setup function for common use cases
def quick_setup_patterns(config_files=None, database_path=None, log_level="INFO"):
    """
    Quick setup for all design patterns with sensible defaults.

    Args:
        config_files: List of configuration files to load
        database_path: Path to SQLite database file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        dict: Initialized pattern components
    """
    system = create_integrated_crawler_system()

    # Initialize database if path provided
    if database_path:
        from .singleton_pattern import DatabaseConnectionInfo

        system["database_manager"].initialize(
            DatabaseConnectionInfo(database_path=database_path)
        )

    # Initialize configuration if files provided
    if config_files:
        system["configuration_manager"].initialize(config_files)

    # Initialize cache with defaults
    system["cache_manager"].initialize(default_ttl=3600, max_size=1000)

    # Set up logging
    system["event_system"].emit_info(
        "system", "Pattern system initialized successfully"
    )

    return system
