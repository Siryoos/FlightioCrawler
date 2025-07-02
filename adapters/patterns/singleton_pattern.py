"""
Singleton Pattern implementation for shared resources management.

This module provides different singleton implementations for:
- Database connection management
- Configuration management
- Cache management
- Logging management
- Resource pooling

Includes thread-safe implementations and different singleton variations.
"""

import threading
import logging
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, Union, List
from pathlib import Path
from dataclasses import dataclass
from functools import wraps
from contextlib import contextmanager
import weakref


logger = logging.getLogger(__name__)


def singleton(cls):
    """
    Thread-safe singleton decorator using double-checked locking pattern.
    """
    instances = {}
    lock = threading.Lock()

    def get_instance(*args, **kwargs):
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


class SingletonMeta(type):
    """
    Thread-safe singleton metaclass implementation.
    """

    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class ResourceManager(ABC):
    """Abstract base class for resource managers."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the resource."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up the resource."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if resource is available."""
        pass


@dataclass
class DatabaseConnectionInfo:
    """Database connection information."""

    database_path: str
    timeout: int = 30
    check_same_thread: bool = False
    isolation_level: Optional[str] = None


class DatabaseManager(ResourceManager, metaclass=SingletonMeta):
    """
    Singleton database connection manager.
    Manages SQLite connections with connection pooling.
    """

    def __init__(self):
        self._connections: Dict[threading.Thread, sqlite3.Connection] = {}
        self._lock = threading.Lock()
        self._initialized = False
        self._connection_info: Optional[DatabaseConnectionInfo] = None
        self._cleanup_refs = weakref.WeakSet()

    def initialize(self, connection_info: DatabaseConnectionInfo) -> None:
        """Initialize database manager with connection info."""
        if self._initialized:
            logger.warning("DatabaseManager already initialized")
            return

        self._connection_info = connection_info
        self._initialized = True
        logger.info(
            f"DatabaseManager initialized with database: {connection_info.database_path}"
        )

    def get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not self._initialized:
            raise RuntimeError(
                "DatabaseManager not initialized. Call initialize() first."
            )

        current_thread = threading.current_thread()

        with self._lock:
            if current_thread not in self._connections:
                try:
                    conn = sqlite3.connect(
                        self._connection_info.database_path,
                        timeout=self._connection_info.timeout,
                        check_same_thread=self._connection_info.check_same_thread,
                        isolation_level=self._connection_info.isolation_level,
                    )
                    conn.row_factory = sqlite3.Row  # Enable dict-like access
                    self._connections[current_thread] = conn
                    self._cleanup_refs.add(current_thread)
                    logger.debug(
                        f"Created new database connection for thread {current_thread.name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create database connection: {e}")
                    raise

        return self._connections[current_thread]

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cursor.close()

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_non_query(self, query: str, params: tuple = ()) -> int:
        """Execute a non-query and return affected rows."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def cleanup(self) -> None:
        """Clean up all connections."""
        with self._lock:
            for thread, conn in self._connections.items():
                try:
                    conn.close()
                    logger.debug(f"Closed database connection for thread {thread.name}")
                except Exception as e:
                    logger.error(
                        f"Error closing connection for thread {thread.name}: {e}"
                    )

            self._connections.clear()
            self._initialized = False
            logger.info("DatabaseManager cleanup completed")

    def is_available(self) -> bool:
        """Check if database manager is available."""
        return self._initialized and self._connection_info is not None


class ConfigurationManager(ResourceManager, metaclass=SingletonMeta):
    """
    Singleton configuration manager.
    Manages application configurations with hot-reloading support.
    """

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._config_files: List[Path] = []
        self._lock = threading.RLock()
        self._initialized = False
        self._watchers: Dict[str, threading.Timer] = {}
        self._last_modified: Dict[Path, float] = {}

    def initialize(
        self, config_files: Union[str, Path, List[Union[str, Path]]]
    ) -> None:
        """Initialize configuration manager with config files."""
        if self._initialized:
            logger.warning("ConfigurationManager already initialized")
            return

        if isinstance(config_files, (str, Path)):
            config_files = [config_files]

        self._config_files = [Path(f) for f in config_files]

        with self._lock:
            self._load_configurations()
            self._initialized = True

        logger.info(
            f"ConfigurationManager initialized with {len(self._config_files)} config files"
        )

    def _load_configurations(self) -> None:
        """Load all configuration files."""
        for config_file in self._config_files:
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                        self._config.update(config_data)
                        self._last_modified[config_file] = config_file.stat().st_mtime
                        logger.debug(f"Loaded config from {config_file}")
                except Exception as e:
                    logger.error(f"Error loading config from {config_file}: {e}")
            else:
                logger.warning(f"Config file not found: {config_file}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        if not self._initialized:
            raise RuntimeError("ConfigurationManager not initialized")

        with self._lock:
            keys = key.split(".")
            value = self._config

            try:
                for k in keys:
                    value = value[k]
                return value
            except (KeyError, TypeError):
                return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value (runtime only)."""
        if not self._initialized:
            raise RuntimeError("ConfigurationManager not initialized")

        with self._lock:
            keys = key.split(".")
            config = self._config

            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value
            logger.debug(f"Set config {key} = {value}")

    def reload_if_changed(self) -> bool:
        """Check and reload configurations if files have changed."""
        if not self._initialized:
            return False

        changed = False
        for config_file in self._config_files:
            if config_file.exists():
                current_mtime = config_file.stat().st_mtime
                last_mtime = self._last_modified.get(config_file, 0)

                if current_mtime > last_mtime:
                    logger.info(f"Config file changed, reloading: {config_file}")
                    with self._lock:
                        self._load_configurations()
                    changed = True

        return changed

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration as dictionary."""
        if not self._initialized:
            raise RuntimeError("ConfigurationManager not initialized")

        with self._lock:
            return self._config.copy()

    def cleanup(self) -> None:
        """Clean up configuration manager."""
        with self._lock:
            # Stop any file watchers
            for watcher in self._watchers.values():
                watcher.cancel()

            self._watchers.clear()
            self._config.clear()
            self._config_files.clear()
            self._last_modified.clear()
            self._initialized = False

        logger.info("ConfigurationManager cleanup completed")

    def is_available(self) -> bool:
        """Check if configuration manager is available."""
        return self._initialized


class CacheManager(ResourceManager, metaclass=SingletonMeta):
    """
    Singleton cache manager with TTL support.
    Thread-safe in-memory cache for frequently accessed data.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self._cleanup_timer: Optional[threading.Timer] = None
        self._default_ttl = 3600  # 1 hour
        self._max_size = 1000

    def initialize(self, default_ttl: int = 3600, max_size: int = 1000) -> None:
        """Initialize cache manager."""
        if self._initialized:
            logger.warning("CacheManager already initialized")
            return

        self._default_ttl = default_ttl
        self._max_size = max_size
        self._initialized = True

        # Start cleanup timer
        self._schedule_cleanup()

        logger.info(
            f"CacheManager initialized with TTL={default_ttl}s, max_size={max_size}"
        )

    def _schedule_cleanup(self) -> None:
        """Schedule periodic cleanup of expired items."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()

        self._cleanup_timer = threading.Timer(
            300, self._cleanup_expired
        )  # Every 5 minutes
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_expired(self) -> None:
        """Remove expired items from cache."""
        current_time = time.time()
        expired_keys = []

        with self._lock:
            for key, item in self._cache.items():
                if current_time > item["expires_at"]:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache items")

        # Schedule next cleanup
        if self._initialized:
            self._schedule_cleanup()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache item with TTL."""
        if not self._initialized:
            raise RuntimeError("CacheManager not initialized")

        if ttl is None:
            ttl = self._default_ttl

        expires_at = time.time() + ttl

        with self._lock:
            # Check cache size limit
            if len(self._cache) >= self._max_size:
                # Remove oldest item
                oldest_key = min(
                    self._cache.keys(), key=lambda k: self._cache[k]["created_at"]
                )
                del self._cache[oldest_key]
                logger.debug(f"Cache full, removed oldest item: {oldest_key}")

            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at,
                "access_count": 0,
            }

            logger.debug(f"Cached item: {key} (TTL={ttl}s)")

    def get(self, key: str, default: Any = None) -> Any:
        """Get cache item."""
        if not self._initialized:
            raise RuntimeError("CacheManager not initialized")

        with self._lock:
            if key not in self._cache:
                return default

            item = self._cache[key]

            # Check if expired
            if time.time() > item["expires_at"]:
                del self._cache[key]
                logger.debug(f"Cache item expired: {key}")
                return default

            # Update access count
            item["access_count"] += 1
            return item["value"]

    def delete(self, key: str) -> bool:
        """Delete cache item."""
        if not self._initialized:
            return False

        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Deleted cache item: {key}")
                return True
            return False

    def clear(self) -> None:
        """Clear all cache items."""
        if not self._initialized:
            return

        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cache items")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._initialized:
            return {}

        with self._lock:
            total_items = len(self._cache)
            current_time = time.time()
            expired_items = sum(
                1 for item in self._cache.values() if current_time > item["expires_at"]
            )

            return {
                "total_items": total_items,
                "expired_items": expired_items,
                "valid_items": total_items - expired_items,
                "max_size": self._max_size,
                "usage_percentage": (total_items / self._max_size) * 100,
            }

    def cleanup(self) -> None:
        """Clean up cache manager."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None

        with self._lock:
            self._cache.clear()
            self._initialized = False

        logger.info("CacheManager cleanup completed")

    def is_available(self) -> bool:
        """Check if cache manager is available."""
        return self._initialized


@singleton
class LoggingManager(ResourceManager):
    """
    Singleton logging manager.
    Centralized logging configuration and management.
    """

    def __init__(self):
        self._initialized = False
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: List[logging.Handler] = []
        self._default_level = logging.INFO

    def initialize(
        self, log_level: str = "INFO", log_file: Optional[str] = None
    ) -> None:
        """Initialize logging manager."""
        if self._initialized:
            logger.warning("LoggingManager already initialized")
            return

        self._default_level = getattr(logging, log_level.upper())

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self._default_level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._default_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        self._handlers.append(console_handler)

        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(self._default_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        self._initialized = True
        logger.info(f"LoggingManager initialized with level {log_level}")

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a named logger."""
        if not self._initialized:
            raise RuntimeError("LoggingManager not initialized")

        if name not in self._loggers:
            logger_instance = logging.getLogger(name)
            logger_instance.setLevel(self._default_level)
            self._loggers[name] = logger_instance

        return self._loggers[name]

    def set_level(self, level: str) -> None:
        """Set logging level for all loggers."""
        if not self._initialized:
            return

        new_level = getattr(logging, level.upper())
        self._default_level = new_level

        # Update root logger
        logging.getLogger().setLevel(new_level)

        # Update all handlers
        for handler in self._handlers:
            handler.setLevel(new_level)

        # Update managed loggers
        for logger_instance in self._loggers.values():
            logger_instance.setLevel(new_level)

        logger.info(f"Logging level changed to {level}")

    def cleanup(self) -> None:
        """Clean up logging manager."""
        # Remove handlers
        root_logger = logging.getLogger()
        for handler in self._handlers:
            root_logger.removeHandler(handler)
            handler.close()

        self._handlers.clear()
        self._loggers.clear()
        self._initialized = False

        logger.info("LoggingManager cleanup completed")

    def is_available(self) -> bool:
        """Check if logging manager is available."""
        return self._initialized


class ResourcePool:
    """
    Singleton resource pool manager.
    Manages shared resources with connection pooling.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._resources: Dict[str, ResourceManager] = {}
            self._lock = threading.RLock()
            self._initialized = True

    def register_resource(self, name: str, resource: ResourceManager) -> None:
        """Register a resource manager."""
        with self._lock:
            if name in self._resources:
                logger.warning(f"Resource {name} already registered, replacing")

            self._resources[name] = resource
            logger.info(f"Registered resource: {name}")

    def get_resource(self, name: str) -> Optional[ResourceManager]:
        """Get a resource manager by name."""
        with self._lock:
            return self._resources.get(name)

    def initialize_all(self) -> None:
        """Initialize all registered resources."""
        with self._lock:
            for name, resource in self._resources.items():
                try:
                    if not resource.is_available():
                        resource.initialize()
                        logger.info(f"Initialized resource: {name}")
                except Exception as e:
                    logger.error(f"Failed to initialize resource {name}: {e}")

    def cleanup_all(self) -> None:
        """Clean up all resources."""
        with self._lock:
            for name, resource in self._resources.items():
                try:
                    resource.cleanup()
                    logger.info(f"Cleaned up resource: {name}")
                except Exception as e:
                    logger.error(f"Error cleaning up resource {name}: {e}")

            self._resources.clear()


# Convenience functions for accessing singleton instances
def get_database_manager() -> DatabaseManager:
    """Get the singleton database manager instance."""
    return DatabaseManager()


def get_configuration_manager() -> ConfigurationManager:
    """Get the singleton configuration manager instance."""
    return ConfigurationManager()


def get_cache_manager() -> CacheManager:
    """Get the singleton cache manager instance."""
    return CacheManager()


def get_logging_manager() -> LoggingManager:
    """Get the singleton logging manager instance."""
    return LoggingManager()


def get_resource_pool() -> ResourcePool:
    """Get the singleton resource pool instance."""
    return ResourcePool()


# Context manager for resource lifecycle
@contextmanager
def managed_resources(*resource_names):
    """Context manager for managing multiple resources."""
    pool = get_resource_pool()
    resources = []

    try:
        # Initialize requested resources
        for name in resource_names:
            resource = pool.get_resource(name)
            if resource and not resource.is_available():
                resource.initialize()
                resources.append(resource)

        yield pool

    finally:
        # Cleanup resources
        for resource in resources:
            try:
                resource.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up resource: {e}")
