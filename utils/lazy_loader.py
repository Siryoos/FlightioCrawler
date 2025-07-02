"""
Lazy Loading System for Flight Crawler
Memory-efficient on-demand loading of airport data, configurations, and large datasets
"""

import asyncio
import csv
import json
import logging
import threading
import weakref
from pathlib import Path
from typing import Dict, List, Any, Optional, Generator, Iterator, Callable, Union
from dataclasses import dataclass, field
from functools import wraps, lru_cache
from datetime import datetime, timedelta
import gc

from utils.memory_efficient_cache import get_cache, cached


@dataclass
class LazyLoadConfig:
    """Configuration for lazy loading"""
    chunk_size: int = 1000
    cache_ttl_seconds: int = 3600
    enable_caching: bool = True
    preload_size: int = 100
    memory_threshold_mb: int = 500
    auto_cleanup: bool = True


class LazyDataLoader:
    """Base class for lazy data loading"""
    
    def __init__(self, config: LazyLoadConfig = None):
        self.config = config or LazyLoadConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache = get_cache("lazy_loader", max_size_mb=64) if self.config.enable_caching else None
        self._loaded_chunks: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
        # Weak references for automatic cleanup
        self._weak_refs: List[weakref.ref] = []

    def _generate_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key for data"""
        key_parts = [str(arg) for arg in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return f"{self.__class__.__name__}::{':'.join(key_parts)}"

    def _should_use_cache(self) -> bool:
        """Check if caching should be used"""
        return self.config.enable_caching and self._cache is not None

    def _cleanup_memory(self):
        """Cleanup loaded chunks if memory threshold exceeded"""
        if not self.config.auto_cleanup:
            return
        
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb > self.config.memory_threshold_mb:
                with self._lock:
                    # Clear half of loaded chunks
                    chunks_to_clear = list(self._loaded_chunks.keys())[:len(self._loaded_chunks)//2]
                    for chunk_key in chunks_to_clear:
                        del self._loaded_chunks[chunk_key]
                
                gc.collect()
                self.logger.debug(f"Cleaned up {len(chunks_to_clear)} chunks due to memory pressure")
                
        except Exception as e:
            self.logger.error(f"Memory cleanup error: {e}")


class AirportDataLoader(LazyDataLoader):
    """Lazy loader for airport data"""
    
    def __init__(self, csv_path: str = "data/statics/airports.csv", config: LazyLoadConfig = None):
        super().__init__(config)
        self.csv_path = Path(csv_path)
        self._total_count: Optional[int] = None
        self._headers: Optional[List[str]] = None
        
    @cached(cache_name="airports", ttl_seconds=7200)  # 2 hours cache
    def get_airport_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get airport by IATA/ICAO code"""
        code = code.upper()
        
        # Check cache first
        if self._should_use_cache():
            cache_key = self._generate_cache_key("airport", code)
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        # Search through file
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get('iata_code', '').upper() == code or 
                        row.get('icao_code', '').upper() == code):
                        result = dict(row)
                        
                        # Cache result
                        if self._should_use_cache():
                            self._cache.set(cache_key, result, self.config.cache_ttl_seconds)
                        
                        return result
        except Exception as e:
            self.logger.error(f"Error loading airport {code}: {e}")
        
        return None

    def get_airports_by_country(self, country_code: str) -> Generator[Dict[str, Any], None, None]:
        """Get airports by country code (generator for memory efficiency)"""
        country_code = country_code.upper()
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                
                for row in reader:
                    if row.get('iso_country', '').upper() == country_code:
                        yield dict(row)
                        count += 1
                        
                        # Periodic cleanup check
                        if count % self.config.chunk_size == 0:
                            self._cleanup_memory()
                            
        except Exception as e:
            self.logger.error(f"Error loading airports for country {country_code}: {e}")

    def get_airports_chunked(self, chunk_size: Optional[int] = None) -> Generator[List[Dict[str, Any]], None, None]:
        """Get airports in chunks for memory-efficient processing"""
        chunk_size = chunk_size or self.config.chunk_size
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                chunk = []
                
                for row in reader:
                    chunk.append(dict(row))
                    
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
                        
                        # Memory cleanup check
                        self._cleanup_memory()
                
                # Yield remaining items
                if chunk:
                    yield chunk
                    
        except Exception as e:
            self.logger.error(f"Error loading airports in chunks: {e}")

    def search_airports(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search airports by name, city, or code"""
        query = query.lower()
        results = []
        
        # Check cache first
        if self._should_use_cache():
            cache_key = self._generate_cache_key("search", query, limit)
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    if len(results) >= limit:
                        break
                    
                    # Search in multiple fields
                    search_fields = [
                        row.get('name', ''),
                        row.get('municipality', ''),
                        row.get('iata_code', ''),
                        row.get('icao_code', '')
                    ]
                    
                    if any(query in field.lower() for field in search_fields if field):
                        results.append(dict(row))
            
            # Cache results
            if self._should_use_cache():
                self._cache.set(cache_key, results, self.config.cache_ttl_seconds)
            
        except Exception as e:
            self.logger.error(f"Error searching airports with query '{query}': {e}")
        
        return results

    @cached(cache_name="airports", ttl_seconds=3600)
    def get_airport_count(self) -> int:
        """Get total number of airports"""
        if self._total_count is not None:
            return self._total_count
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                self._total_count = sum(1 for _ in f) - 1  # Subtract header
            return self._total_count
        except Exception as e:
            self.logger.error(f"Error counting airports: {e}")
            return 0

    def get_popular_airports(self, country_code: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get popular airports (those with IATA codes) for quick access"""
        cache_key = self._generate_cache_key("popular", country_code or "all", limit)
        
        if self._should_use_cache():
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        results = []
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    if len(results) >= limit:
                        break
                    
                    # Only airports with IATA codes (usually major airports)
                    if not row.get('iata_code'):
                        continue
                    
                    # Filter by country if specified
                    if country_code and row.get('iso_country', '').upper() != country_code.upper():
                        continue
                    
                    results.append(dict(row))
            
            # Cache results
            if self._should_use_cache():
                self._cache.set(cache_key, results, self.config.cache_ttl_seconds)
            
        except Exception as e:
            self.logger.error(f"Error loading popular airports: {e}")
        
        return results


class ConfigurationLoader(LazyDataLoader):
    """Lazy loader for configuration files"""
    
    def __init__(self, config_dir: str = "config", config: LazyLoadConfig = None):
        super().__init__(config)
        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Dict[str, Any]] = {}

    @cached(cache_name="config", ttl_seconds=1800)  # 30 minutes cache
    def load_site_config(self, site_name: str) -> Dict[str, Any]:
        """Load site-specific configuration"""
        config_file = self.config_dir / "site_configs" / f"{site_name}.json"
        
        if not config_file.exists():
            self.logger.warning(f"Config file not found: {config_file}")
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Process and validate config if needed
            return self._process_site_config(config_data)
            
        except Exception as e:
            self.logger.error(f"Error loading config for {site_name}: {e}")
            return {}

    def _process_site_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate site configuration"""
        # Add default values if missing
        defaults = {
            "rate_limiting": {
                "requests_per_second": 2,
                "burst_limit": 5,
                "cooldown_period": 60
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 5,
                "circuit_breaker": {}
            },
            "resource_limits": {
                "max_memory_mb": 512,
                "max_processing_time": 300,
                "enable_memory_monitoring": True
            }
        }
        
        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
            elif isinstance(default_value, dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in config[key]:
                        config[key][sub_key] = sub_default
        
        return config

    def load_all_site_configs(self) -> Generator[tuple[str, Dict[str, Any]], None, None]:
        """Load all site configurations (generator for memory efficiency)"""
        site_configs_dir = self.config_dir / "site_configs"
        
        if not site_configs_dir.exists():
            self.logger.warning(f"Site configs directory not found: {site_configs_dir}")
            return
        
        for config_file in site_configs_dir.glob("*.json"):
            site_name = config_file.stem
            try:
                config = self.load_site_config(site_name)
                yield site_name, config
            except Exception as e:
                self.logger.error(f"Error loading config for {site_name}: {e}")
                continue

    @cached(cache_name="config", ttl_seconds=3600)
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Load rate limiting configuration"""
        config_file = self.config_dir / "rate_limit_config.json"
        
        if not config_file.exists():
            return {
                "default": {
                    "requests_per_second": 2,
                    "burst_limit": 5,
                    "cooldown_period": 60
                }
            }
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading rate limit config: {e}")
            return {}


class DatasetLoader(LazyDataLoader):
    """Generic lazy loader for large datasets"""
    
    def __init__(self, data_path: str, config: LazyLoadConfig = None):
        super().__init__(config)
        self.data_path = Path(data_path)

    def load_json_lines(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """Load JSON lines file (one JSON object per line)"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                count = 0
                for line in f:
                    if limit and count >= limit:
                        break
                    
                    try:
                        yield json.loads(line.strip())
                        count += 1
                        
                        if count % self.config.chunk_size == 0:
                            self._cleanup_memory()
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON line {count}: {e}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"Error loading JSON lines from {self.data_path}: {e}")

    def load_csv_chunked(self, chunk_size: Optional[int] = None) -> Generator[List[Dict[str, Any]], None, None]:
        """Load CSV file in chunks"""
        chunk_size = chunk_size or self.config.chunk_size
        
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                chunk = []
                
                for row in reader:
                    chunk.append(dict(row))
                    
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
                        self._cleanup_memory()
                
                if chunk:
                    yield chunk
                    
        except Exception as e:
            self.logger.error(f"Error loading CSV chunks from {self.data_path}: {e}")


class LazyLoaderManager:
    """Manages multiple lazy loaders"""
    
    def __init__(self):
        self._loaders: Dict[str, LazyDataLoader] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_airport_loader(self, csv_path: str = "data/statics/airports.csv") -> AirportDataLoader:
        """Get or create airport data loader"""
        with self._lock:
            key = f"airports:{csv_path}"
            if key not in self._loaders:
                self._loaders[key] = AirportDataLoader(csv_path)
            return self._loaders[key]

    def get_config_loader(self, config_dir: str = "config") -> ConfigurationLoader:
        """Get or create configuration loader"""
        with self._lock:
            key = f"config:{config_dir}"
            if key not in self._loaders:
                self._loaders[key] = ConfigurationLoader(config_dir)
            return self._loaders[key]

    def get_dataset_loader(self, data_path: str) -> DatasetLoader:
        """Get or create dataset loader"""
        with self._lock:
            key = f"dataset:{data_path}"
            if key not in self._loaders:
                self._loaders[key] = DatasetLoader(data_path)
            return self._loaders[key]

    def cleanup_all(self):
        """Cleanup all loaders"""
        with self._lock:
            for loader in self._loaders.values():
                if hasattr(loader, '_cleanup_memory'):
                    loader._cleanup_memory()
            
            # Force garbage collection
            gc.collect()
            self.logger.info("Cleaned up all lazy loaders")

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics for all loaders"""
        stats = {}
        
        try:
            import psutil
            process = psutil.Process()
            stats["total_memory_mb"] = process.memory_info().rss / 1024 / 1024
            stats["loader_count"] = len(self._loaders)
            stats["active_loaders"] = list(self._loaders.keys())
        except Exception as e:
            self.logger.error(f"Error getting memory usage: {e}")
            stats["error"] = str(e)
        
        return stats


# Global lazy loader manager
_loader_manager = LazyLoaderManager()

def get_airport_loader() -> AirportDataLoader:
    """Get global airport data loader"""
    return _loader_manager.get_airport_loader()

def get_config_loader() -> ConfigurationLoader:
    """Get global configuration loader"""
    return _loader_manager.get_config_loader()

def get_dataset_loader(data_path: str) -> DatasetLoader:
    """Get dataset loader for specific path"""
    return _loader_manager.get_dataset_loader(data_path)


# Convenience functions
def lazy_load_airports_by_country(country_code: str) -> Generator[Dict[str, Any], None, None]:
    """Convenience function for loading airports by country"""
    loader = get_airport_loader()
    yield from loader.get_airports_by_country(country_code)

def lazy_load_site_configs() -> Generator[tuple[str, Dict[str, Any]], None, None]:
    """Convenience function for loading all site configs"""
    loader = get_config_loader()
    yield from loader.load_all_site_configs()


if __name__ == "__main__":
    # Example usage
    
    # Airport data loading
    airport_loader = get_airport_loader()
    
    # Load specific airport
    airport = airport_loader.get_airport_by_code("THR")
    print(f"Tehran airport: {airport}")
    
    # Search airports
    results = airport_loader.search_airports("tehran", limit=5)
    print(f"Search results for 'tehran': {len(results)} airports")
    
    # Load airports by country (memory efficient)
    iranian_airports = list(airport_loader.get_airports_by_country("IR"))
    print(f"Iranian airports: {len(iranian_airports)}")
    
    # Configuration loading
    config_loader = get_config_loader()
    alibaba_config = config_loader.load_site_config("alibaba")
    print(f"Alibaba config loaded: {bool(alibaba_config)}")
    
    # Memory usage
    memory_stats = _loader_manager.get_memory_usage()
    print(f"Memory usage: {memory_stats}")
    
    # Cleanup
    _loader_manager.cleanup_all() 