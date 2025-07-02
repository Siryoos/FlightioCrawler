"""
Memory-Efficient Caching System for Flight Crawler
Features: TTL, LRU eviction, memory monitoring, lazy loading, cache invalidation
"""

import asyncio
import time
import weakref
import gc
import pickle
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import OrderedDict
from functools import wraps, lru_cache
import threading
import logging
import psutil
import os
from contextlib import contextmanager

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    is_persistent: bool = False
    
    def __post_init__(self):
        if self.size_bytes == 0:
            self.size_bytes = self._calculate_size()
    
    def _calculate_size(self) -> int:
        """Calculate approximate size of cached value"""
        try:
            if isinstance(self.value, (str, bytes)):
                return len(self.value)
            elif isinstance(self.value, (int, float, bool)):
                return 8  # Approximate
            elif isinstance(self.value, (list, tuple, dict)):
                return len(pickle.dumps(self.value))
            else:
                return len(str(self.value))
        except:
            return 100  # Default estimate
    
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds
    
    def update_access(self):
        """Update access statistics"""
        self.accessed_at = datetime.now()
        self.access_count += 1


@dataclass 
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expired_evictions: int = 0
    memory_evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    memory_usage_mb: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class MemoryEfficientCache:
    """
    Memory-efficient cache with TTL, LRU eviction, and monitoring
    """
    
    def __init__(
        self,
        max_size_mb: int = 128,
        max_entries: int = 10000,
        default_ttl_seconds: int = 3600,  # 1 hour
        cleanup_interval_seconds: int = 300,  # 5 minutes
        enable_persistence: bool = False,
        persistence_path: Optional[str] = None,
        redis_client: Optional[Any] = None
    ):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_entries = max_entries
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.enable_persistence = enable_persistence
        
        # Cache storage (OrderedDict for LRU behavior)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = CacheStats()
        
        # Persistence
        self.persistence_path = Path(persistence_path or "cache_data")
        if self.enable_persistence:
            self.persistence_path.mkdir(exist_ok=True)
        
        # Redis support for distributed caching
        self.redis_client = redis_client
        self.use_redis = redis_client is not None
        
        # Memory monitoring
        self.process = psutil.Process(os.getpid())
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Cleanup task
        self._cleanup_task = None
        self._stop_cleanup = False
        self._start_cleanup_task()
        
        # Weak references for automatic cleanup
        self._weak_refs: List[weakref.ref] = []

    def _start_cleanup_task(self):
        """Start background cleanup task"""
        def cleanup_loop():
            while not self._stop_cleanup:
                try:
                    self._cleanup_expired()
                    self._cleanup_memory_pressure()
                    time.sleep(self.cleanup_interval_seconds)
                except Exception as e:
                    self.logger.error(f"Cache cleanup error: {e}")
        
        self._cleanup_task = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_task.start()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        with self._lock:
            # Try local cache first
            if key in self._cache:
                entry = self._cache[key]
                
                if entry.is_expired():
                    del self._cache[key]
                    self.stats.expired_evictions += 1
                    self.stats.misses += 1
                    return self._get_from_redis(key, default)
                
                # Move to end (LRU)
                self._cache.move_to_end(key)
                entry.update_access()
                self.stats.hits += 1
                return entry.value
            
            # Try Redis if available
            if self.use_redis:
                value = self._get_from_redis(key, default)
                if value is not default:
                    self.stats.hits += 1
                    return value
            
            # Try persistent storage
            if self.enable_persistence:
                value = self._get_from_persistence(key, default)
                if value is not default:
                    self.stats.hits += 1
                    return value
            
            self.stats.misses += 1
            return default

    def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: Optional[int] = None,
        is_persistent: bool = False
    ) -> bool:
        """Set value in cache"""
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds
        
        with self._lock:
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                accessed_at=datetime.now(),
                ttl_seconds=ttl_seconds,
                is_persistent=is_persistent
            )
            
            # Check memory limits before adding
            if self._would_exceed_memory(entry):
                self._evict_lru_entries()
            
            # Add to local cache
            if key in self._cache:
                old_entry = self._cache[key]
                self.stats.total_size_bytes -= old_entry.size_bytes
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            self.stats.total_size_bytes += entry.size_bytes
            self.stats.entry_count = len(self._cache)
            
            # Add to Redis if available
            if self.use_redis:
                self._set_to_redis(key, value, ttl_seconds)
            
            # Add to persistent storage if requested
            if is_persistent and self.enable_persistence:
                self._set_to_persistence(key, value, ttl_seconds)
            
            return True

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            deleted = False
            
            # Delete from local cache
            if key in self._cache:
                entry = self._cache.pop(key)
                self.stats.total_size_bytes -= entry.size_bytes
                self.stats.entry_count = len(self._cache)
                deleted = True
            
            # Delete from Redis
            if self.use_redis:
                try:
                    self.redis_client.delete(key)
                    deleted = True
                except Exception as e:
                    self.logger.error(f"Redis delete error: {e}")
            
            # Delete from persistence
            if self.enable_persistence:
                self._delete_from_persistence(key)
                deleted = True
            
            return deleted

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self.stats = CacheStats()
            
            if self.use_redis:
                try:
                    # Clear only our keys (with prefix if implemented)
                    for key in self.redis_client.scan_iter():
                        self.redis_client.delete(key)
                except Exception as e:
                    self.logger.error(f"Redis clear error: {e}")
            
            if self.enable_persistence:
                self._clear_persistence()

    def get_or_set(
        self, 
        key: str, 
        factory: Callable[[], Any], 
        ttl_seconds: Optional[int] = None,
        is_persistent: bool = False
    ) -> Any:
        """Get value or set if not exists using factory function"""
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl_seconds, is_persistent)
        return value

    async def get_or_set_async(
        self,
        key: str,
        async_factory: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
        is_persistent: bool = False
    ) -> Any:
        """Async version of get_or_set"""
        value = self.get(key)
        if value is None:
            if asyncio.iscoroutinefunction(async_factory):
                value = await async_factory()
            else:
                value = async_factory()
            self.set(key, value, ttl_seconds, is_persistent)
        return value

    def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching pattern"""
        import fnmatch
        
        with self._lock:
            keys_to_delete = []
            for key in self._cache.keys():
                if fnmatch.fnmatch(key, pattern):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                self.delete(key)

    def _would_exceed_memory(self, entry: CacheEntry) -> bool:
        """Check if adding entry would exceed memory limits"""
        new_size = self.stats.total_size_bytes + entry.size_bytes
        return (
            new_size > self.max_size_bytes or 
            len(self._cache) >= self.max_entries
        )

    def _evict_lru_entries(self):
        """Evict least recently used entries"""
        evicted_count = 0
        evicted_size = 0
        
        # Calculate how much we need to free (25% of max size)
        target_free = self.max_size_bytes * 0.25
        
        while (
            self._cache and 
            (self.stats.total_size_bytes > self.max_size_bytes - target_free or
             len(self._cache) >= self.max_entries)
        ):
            # Remove least recently used (first item)
            key, entry = self._cache.popitem(last=False)
            evicted_size += entry.size_bytes
            evicted_count += 1
            
            # Don't evict persistent entries unless absolutely necessary
            if entry.is_persistent and len(self._cache) < self.max_entries * 0.9:
                # Re-add persistent entry to end
                self._cache[key] = entry
                self._cache.move_to_end(key)
                evicted_size -= entry.size_bytes
                evicted_count -= 1
                break
        
        self.stats.total_size_bytes -= evicted_size
        self.stats.evictions += evicted_count
        self.stats.memory_evictions += evicted_count
        self.stats.entry_count = len(self._cache)
        
        if evicted_count > 0:
            self.logger.debug(f"Evicted {evicted_count} entries ({evicted_size} bytes)")

    def _cleanup_expired(self):
        """Remove expired entries"""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self._cache.pop(key)
                self.stats.total_size_bytes -= entry.size_bytes
                self.stats.expired_evictions += 1
            
            self.stats.entry_count = len(self._cache)
            
            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

    def _cleanup_memory_pressure(self):
        """Cleanup when under memory pressure"""
        try:
            memory_percent = self.process.memory_percent()
            if memory_percent > 80:  # High memory usage
                self.logger.warning(f"High memory usage ({memory_percent:.1f}%), forcing cleanup")
                
                # Force garbage collection
                gc.collect()
                
                # Evict non-persistent entries aggressively
                with self._lock:
                    non_persistent_keys = [
                        key for key, entry in self._cache.items() 
                        if not entry.is_persistent
                    ]
                    
                    # Remove half of non-persistent entries
                    keys_to_remove = non_persistent_keys[:len(non_persistent_keys)//2]
                    for key in keys_to_remove:
                        entry = self._cache.pop(key)
                        self.stats.total_size_bytes -= entry.size_bytes
                        self.stats.memory_evictions += 1
                    
                    self.stats.entry_count = len(self._cache)
                    
                    if keys_to_remove:
                        self.logger.info(f"Emergency evicted {len(keys_to_remove)} entries due to memory pressure")
        
        except Exception as e:
            self.logger.error(f"Memory pressure cleanup error: {e}")

    def _get_from_redis(self, key: str, default: Any = None) -> Any:
        """Get value from Redis"""
        if not self.use_redis:
            return default
        
        try:
            data = self.redis_client.get(key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            self.logger.error(f"Redis get error for key {key}: {e}")
        
        return default

    def _set_to_redis(self, key: str, value: Any, ttl_seconds: int):
        """Set value to Redis"""
        if not self.use_redis:
            return
        
        try:
            data = pickle.dumps(value)
            self.redis_client.setex(key, ttl_seconds, data)
        except Exception as e:
            self.logger.error(f"Redis set error for key {key}: {e}")

    def _get_from_persistence(self, key: str, default: Any = None) -> Any:
        """Get value from persistent storage"""
        try:
            file_path = self.persistence_path / f"{self._hash_key(key)}.cache"
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
                    # Check if expired
                    if 'expires_at' in data and datetime.now() > data['expires_at']:
                        file_path.unlink()  # Delete expired file
                        return default
                    return data['value']
        except Exception as e:
            self.logger.error(f"Persistence get error for key {key}: {e}")
        
        return default

    def _set_to_persistence(self, key: str, value: Any, ttl_seconds: int):
        """Set value to persistent storage"""
        try:
            file_path = self.persistence_path / f"{self._hash_key(key)}.cache"
            data = {
                'value': value,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(seconds=ttl_seconds)
            }
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.logger.error(f"Persistence set error for key {key}: {e}")

    def _delete_from_persistence(self, key: str):
        """Delete from persistent storage"""
        try:
            file_path = self.persistence_path / f"{self._hash_key(key)}.cache"
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            self.logger.error(f"Persistence delete error for key {key}: {e}")

    def _clear_persistence(self):
        """Clear all persistent cache files"""
        try:
            for file_path in self.persistence_path.glob("*.cache"):
                file_path.unlink()
        except Exception as e:
            self.logger.error(f"Persistence clear error: {e}")

    def _hash_key(self, key: str) -> str:
        """Generate hash for file names"""
        return hashlib.md5(key.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self.stats.memory_usage_mb = self.process.memory_info().rss / 1024 / 1024
        
        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "hit_rate": self.stats.hit_rate,
            "evictions": self.stats.evictions,
            "expired_evictions": self.stats.expired_evictions,
            "memory_evictions": self.stats.memory_evictions,
            "total_size_mb": self.stats.total_size_bytes / 1024 / 1024,
            "entry_count": self.stats.entry_count,
            "memory_usage_mb": self.stats.memory_usage_mb,
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
            "utilization_percent": (self.stats.total_size_bytes / self.max_size_bytes) * 100
        }

    def shutdown(self):
        """Shutdown cache and cleanup resources"""
        self._stop_cleanup = True
        if self._cleanup_task and self._cleanup_task.is_alive():
            self._cleanup_task.join(timeout=5)
        
        if self.enable_persistence:
            # Save important entries to persistence
            with self._lock:
                for key, entry in self._cache.items():
                    if entry.is_persistent:
                        self._set_to_persistence(key, entry.value, entry.ttl_seconds or 3600)
        
        self.clear()

    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.shutdown()
        except:
            pass


class CacheManager:
    """Manages multiple named caches"""
    
    def __init__(self):
        self._caches: Dict[str, MemoryEfficientCache] = {}
        self._lock = threading.Lock()
    
    def get_cache(
        self, 
        name: str, 
        max_size_mb: int = 64,
        default_ttl_seconds: int = 3600
    ) -> MemoryEfficientCache:
        """Get or create named cache"""
        with self._lock:
            if name not in self._caches:
                self._caches[name] = MemoryEfficientCache(
                    max_size_mb=max_size_mb,
                    default_ttl_seconds=default_ttl_seconds,
                    enable_persistence=True,
                    persistence_path=f"cache_data/{name}"
                )
            return self._caches[name]
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {name: cache.get_stats() for name, cache in self._caches.items()}
    
    def shutdown_all(self):
        """Shutdown all caches"""
        with self._lock:
            for cache in self._caches.values():
                cache.shutdown()
            self._caches.clear()


# Global cache manager
_cache_manager = CacheManager()

def get_cache(name: str = "default", **kwargs) -> MemoryEfficientCache:
    """Get named cache instance"""
    return _cache_manager.get_cache(name, **kwargs)

def cached(
    cache_name: str = "default",
    ttl_seconds: int = 3600,
    key_func: Optional[Callable] = None
):
    """Decorator for caching function results"""
    def decorator(func):
        cache = get_cache(cache_name)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}_{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            cache.set(cache_key, result, ttl_seconds)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}_{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


if __name__ == "__main__":
    # Example usage
    cache = MemoryEfficientCache(max_size_mb=10, default_ttl_seconds=60)
    
    # Basic usage
    cache.set("key1", "value1", ttl_seconds=30)
    print(cache.get("key1"))  # "value1"
    
    # Using decorator
    @cached(cache_name="test", ttl_seconds=120)
    def expensive_operation(x: int) -> int:
        time.sleep(1)  # Simulate expensive operation
        return x * x
    
    start = time.time()
    result1 = expensive_operation(10)  # Takes ~1 second
    print(f"First call: {result1}, took {time.time() - start:.2f}s")
    
    start = time.time()
    result2 = expensive_operation(10)  # Should be instant (cached)
    print(f"Second call: {result2}, took {time.time() - start:.2f}s")
    
    # Statistics
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Cleanup
    cache.shutdown() 