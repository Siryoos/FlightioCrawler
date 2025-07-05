"""
Adaptive Rate Limiting System for FlightIO Crawler
Dynamically adjusts rate limits based on server response, error rates, and system performance
"""

import asyncio
import logging
import time
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import json
import statistics
from pathlib import Path
import threading

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import config


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    PERFORMANCE_BASED = "performance_based"


class SystemState(Enum):
    """System performance states"""
    OPTIMAL = "optimal"
    GOOD = "good"
    DEGRADED = "degraded"
    OVERLOADED = "overloaded"
    CRITICAL = "critical"


@dataclass
class RateLimit:
    """Rate limit configuration"""
    requests_per_second: float
    requests_per_minute: int
    burst_limit: int
    backoff_seconds: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceMetrics:
    """Performance metrics for adaptive rate limiting"""
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rates: deque = field(default_factory=lambda: deque(maxlen=50))
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    last_request_time: Optional[datetime] = None
    consecutive_errors: int = 0
    consecutive_successes: int = 0
    avg_response_time: float = 0.0
    error_rate_percent: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive rate limiting"""
    base_rate_per_second: float = 1.0
    max_rate_per_second: float = 10.0
    min_rate_per_second: float = 0.1
    target_response_time_ms: float = 1000.0
    max_error_rate_percent: float = 5.0
    adjustment_factor: float = 0.1
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 300.0
    recovery_factor: float = 0.05
    window_size_seconds: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


class AdaptiveRateLimiter:
    """Adaptive rate limiter with dynamic adjustment based on performance metrics"""
    
    def __init__(self, site_id: str, config: AdaptiveConfig = None, redis_client=None):
        self.site_id = site_id
        self.config = config or AdaptiveConfig()
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Current rate limits
        self.current_limits = RateLimit(
            requests_per_second=self.config.base_rate_per_second,
            requests_per_minute=int(self.config.base_rate_per_second * 60),
            burst_limit=max(5, int(self.config.base_rate_per_second * 2))
        )
        
        # Performance tracking
        self.metrics = PerformanceMetrics()
        self.system_state = SystemState.OPTIMAL
        
        # Request tracking
        self.request_timestamps = deque(maxlen=1000)
        self.last_adjustment = datetime.now()
        self.adjustment_lock = threading.RLock()
        
        # Circuit breaker state
        self.circuit_open = False
        self.circuit_open_time = None
        self.half_open_attempts = 0
        
        # Rate adjustment history
        self.adjustment_history = deque(maxlen=100)
        
        self.logger.info(f"Adaptive rate limiter initialized for {site_id}")
    
    async def can_make_request(self) -> Tuple[bool, str, float]:
        """
        Check if a request can be made
        Returns: (can_proceed, reason, wait_time_seconds)
        """
        current_time = time.time()
        
        # Check circuit breaker
        if self.circuit_open:
            if self._should_attempt_recovery(current_time):
                self.circuit_open = False
                self.half_open_attempts = 0
                self.logger.info(f"Circuit breaker opening for {self.site_id}")
            else:
                remaining_time = self.config.circuit_breaker_timeout - (current_time - self.circuit_open_time.timestamp())
                return False, "circuit_breaker_open", max(0, remaining_time)
        
        # Check rate limits
        if not self._check_rate_limits(current_time):
            wait_time = self._calculate_wait_time(current_time)
            return False, "rate_limit_exceeded", wait_time
        
        # Check if we need to apply backoff
        if self.current_limits.backoff_seconds > 0:
            if current_time < self.current_limits.last_updated.timestamp() + self.current_limits.backoff_seconds:
                remaining_backoff = (self.current_limits.last_updated.timestamp() + self.current_limits.backoff_seconds) - current_time
                return False, "backoff_period", remaining_backoff
        
        return True, "allowed", 0.0
    
    def _check_rate_limits(self, current_time: float) -> bool:
        """Check if current request rate is within limits"""
        # Clean old timestamps
        cutoff_time = current_time - 1.0  # 1 second window
        while self.request_timestamps and self.request_timestamps[0] < cutoff_time:
            self.request_timestamps.popleft()
        
        # Check requests per second
        if len(self.request_timestamps) >= self.current_limits.requests_per_second:
            return False
        
        # Check burst limit
        burst_window = current_time - 10.0  # 10 second burst window
        burst_requests = sum(1 for ts in self.request_timestamps if ts > burst_window)
        if burst_requests >= self.current_limits.burst_limit:
            return False
        
        return True
    
    def _calculate_wait_time(self, current_time: float) -> float:
        """Calculate how long to wait before next request"""
        if not self.request_timestamps:
            return 0.0
        
        # Calculate time until we can make next request
        oldest_request = self.request_timestamps[0]
        time_since_oldest = current_time - oldest_request
        
        if time_since_oldest < 1.0:
            return 1.0 - time_since_oldest
        
        return 1.0 / self.current_limits.requests_per_second
    
    async def record_request(self, response_time_ms: float, success: bool, error_type: str = None):
        """Record request metrics and potentially adjust rate limits"""
        current_time = time.time()
        self.request_timestamps.append(current_time)
        
        # Update metrics
        self.metrics.response_times.append(response_time_ms)
        self.metrics.total_requests += 1
        self.metrics.last_request_time = datetime.now()
        
        if success:
            self.metrics.success_count += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_errors = 0
            
            # If we were in half-open state, consider closing circuit
            if self.circuit_open and self.half_open_attempts > 0:
                self.half_open_attempts += 1
                if self.half_open_attempts >= 3:  # Successful attempts in half-open
                    self.circuit_open = False
                    self.logger.info(f"Circuit breaker closed for {self.site_id}")
        else:
            self.metrics.error_count += 1
            self.metrics.consecutive_errors += 1
            self.metrics.consecutive_successes = 0
            
            # Check circuit breaker
            if self.metrics.consecutive_errors >= self.config.circuit_breaker_threshold:
                self._open_circuit_breaker()
        
        # Update calculated metrics
        self._update_calculated_metrics()
        
        # Check if we need to adjust rate limits
        await self._maybe_adjust_rate_limits()
        
        # Store metrics in Redis if available
        if self.redis_client:
            await self._store_metrics_in_redis()
    
    def _update_calculated_metrics(self):
        """Update calculated performance metrics"""
        if self.metrics.response_times:
            self.metrics.avg_response_time = statistics.mean(self.metrics.response_times)
        
        if self.metrics.total_requests > 0:
            self.metrics.error_rate_percent = (self.metrics.error_count / self.metrics.total_requests) * 100
        
        # Update system state based on metrics
        self._update_system_state()
    
    def _update_system_state(self):
        """Update system state based on current metrics"""
        old_state = self.system_state
        
        if self.circuit_open:
            self.system_state = SystemState.CRITICAL
        elif self.metrics.error_rate_percent > self.config.max_error_rate_percent * 2:
            self.system_state = SystemState.OVERLOADED
        elif (self.metrics.error_rate_percent > self.config.max_error_rate_percent or
              self.metrics.avg_response_time > self.config.target_response_time_ms * 1.5):
            self.system_state = SystemState.DEGRADED
        elif self.metrics.avg_response_time > self.config.target_response_time_ms:
            self.system_state = SystemState.GOOD
        else:
            self.system_state = SystemState.OPTIMAL
        
        if old_state != self.system_state:
            self.logger.info(f"System state changed for {self.site_id}: {old_state.value} -> {self.system_state.value}")
    
    async def _maybe_adjust_rate_limits(self):
        """Adjust rate limits based on current performance metrics"""
        current_time = datetime.now()
        
        # Don't adjust too frequently
        if (current_time - self.last_adjustment).total_seconds() < 30:
            return
        
        with self.adjustment_lock:
            old_rate = self.current_limits.requests_per_second
            new_rate = self._calculate_new_rate()
            
            if abs(new_rate - old_rate) > 0.01:  # Only adjust if significant change
                self._apply_rate_adjustment(new_rate)
                self.last_adjustment = current_time
                
                # Record adjustment
                self.adjustment_history.append({
                    "timestamp": current_time.isoformat(),
                    "old_rate": old_rate,
                    "new_rate": new_rate,
                    "reason": self._get_adjustment_reason(),
                    "system_state": self.system_state.value,
                    "response_time": self.metrics.avg_response_time,
                    "error_rate": self.metrics.error_rate_percent
                })
                
                self.logger.info(
                    f"Rate limit adjusted for {self.site_id}: "
                    f"{old_rate:.2f} -> {new_rate:.2f} RPS "
                    f"(reason: {self._get_adjustment_reason()})"
                )
    
    def _calculate_new_rate(self) -> float:
        """Calculate new rate limit based on current performance"""
        current_rate = self.current_limits.requests_per_second
        
        # Base adjustment on system state
        if self.system_state == SystemState.CRITICAL:
            # Dramatic decrease
            new_rate = current_rate * 0.1
        elif self.system_state == SystemState.OVERLOADED:
            # Significant decrease
            new_rate = current_rate * 0.5
        elif self.system_state == SystemState.DEGRADED:
            # Moderate decrease
            new_rate = current_rate * 0.8
        elif self.system_state == SystemState.GOOD:
            # Slight adjustment based on response time
            if self.metrics.avg_response_time > self.config.target_response_time_ms:
                new_rate = current_rate * 0.95
            else:
                new_rate = current_rate * 1.02
        else:  # OPTIMAL
            # Gradual increase
            new_rate = current_rate * 1.05
        
        # Apply bounds
        new_rate = max(self.config.min_rate_per_second, 
                      min(self.config.max_rate_per_second, new_rate))
        
        # Apply smoothing to prevent oscillation
        adjustment_factor = min(self.config.adjustment_factor, 
                              abs(new_rate - current_rate) / current_rate)
        new_rate = current_rate + (new_rate - current_rate) * adjustment_factor
        
        return new_rate
    
    def _apply_rate_adjustment(self, new_rate: float):
        """Apply new rate limit"""
        self.current_limits.requests_per_second = new_rate
        self.current_limits.requests_per_minute = int(new_rate * 60)
        self.current_limits.burst_limit = max(2, int(new_rate * 3))
        self.current_limits.last_updated = datetime.now()
        
        # Calculate backoff if needed
        if self.system_state in [SystemState.DEGRADED, SystemState.OVERLOADED, SystemState.CRITICAL]:
            backoff_factor = {
                SystemState.DEGRADED: 1.0,
                SystemState.OVERLOADED: 2.0,
                SystemState.CRITICAL: 5.0
            }[self.system_state]
            
            self.current_limits.backoff_seconds = min(
                self.config.max_backoff_seconds,
                backoff_factor * self.config.backoff_multiplier
            )
        else:
            self.current_limits.backoff_seconds = 0.0
    
    def _get_adjustment_reason(self) -> str:
        """Get reason for rate adjustment"""
        if self.circuit_open:
            return "circuit_breaker_open"
        elif self.metrics.error_rate_percent > self.config.max_error_rate_percent:
            return "high_error_rate"
        elif self.metrics.avg_response_time > self.config.target_response_time_ms * 1.5:
            return "high_response_time"
        elif self.metrics.consecutive_errors > 3:
            return "consecutive_errors"
        elif self.system_state == SystemState.OPTIMAL:
            return "performance_optimization"
        else:
            return "performance_adjustment"
    
    def _open_circuit_breaker(self):
        """Open circuit breaker"""
        if not self.circuit_open:
            self.circuit_open = True
            self.circuit_open_time = datetime.now()
            self.half_open_attempts = 0
            self.logger.warning(f"Circuit breaker opened for {self.site_id}")
    
    def _should_attempt_recovery(self, current_time: float) -> bool:
        """Check if we should attempt recovery from circuit breaker"""
        if not self.circuit_open or not self.circuit_open_time:
            return False
        
        time_since_open = current_time - self.circuit_open_time.timestamp()
        return time_since_open >= self.config.circuit_breaker_timeout
    
    async def _store_metrics_in_redis(self):
        """Store metrics in Redis for persistence and analysis"""
        try:
            if not self.redis_client:
                return
            
            metrics_data = {
                "site_id": self.site_id,
                "current_rate": self.current_limits.requests_per_second,
                "system_state": self.system_state.value,
                "avg_response_time": self.metrics.avg_response_time,
                "error_rate_percent": self.metrics.error_rate_percent,
                "circuit_open": self.circuit_open,
                "total_requests": self.metrics.total_requests,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store with 1 hour TTL
            await self.redis_client.setex(
                f"adaptive_rate_limiter:{self.site_id}",
                3600,
                json.dumps(metrics_data)
            )
            
        except Exception as e:
            self.logger.error(f"Error storing metrics in Redis: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status and metrics"""
        return {
            "site_id": self.site_id,
            "current_limits": {
                "requests_per_second": self.current_limits.requests_per_second,
                "requests_per_minute": self.current_limits.requests_per_minute,
                "burst_limit": self.current_limits.burst_limit,
                "backoff_seconds": self.current_limits.backoff_seconds
            },
            "metrics": {
                "avg_response_time_ms": self.metrics.avg_response_time,
                "error_rate_percent": self.metrics.error_rate_percent,
                "total_requests": self.metrics.total_requests,
                "success_count": self.metrics.success_count,
                "error_count": self.metrics.error_count,
                "consecutive_errors": self.metrics.consecutive_errors,
                "consecutive_successes": self.metrics.consecutive_successes
            },
            "system_state": self.system_state.value,
            "circuit_breaker": {
                "open": self.circuit_open,
                "open_time": self.circuit_open_time.isoformat() if self.circuit_open_time else None,
                "half_open_attempts": self.half_open_attempts
            },
            "recent_adjustments": list(self.adjustment_history)[-5:],  # Last 5 adjustments
            "timestamp": datetime.now().isoformat()
        }
    
    def reset_metrics(self):
        """Reset all metrics and state"""
        self.metrics = PerformanceMetrics()
        self.request_timestamps.clear()
        self.circuit_open = False
        self.circuit_open_time = None
        self.half_open_attempts = 0
        self.system_state = SystemState.OPTIMAL
        self.adjustment_history.clear()
        
        # Reset to base rate
        self.current_limits = RateLimit(
            requests_per_second=self.config.base_rate_per_second,
            requests_per_minute=int(self.config.base_rate_per_second * 60),
            burst_limit=max(5, int(self.config.base_rate_per_second * 2))
        )
        
        self.logger.info(f"Metrics reset for {self.site_id}")


class AdaptiveRateLimitManager:
    """Manager for multiple adaptive rate limiters"""
    
    def __init__(self, redis_client=None):
        self.limiters: Dict[str, AdaptiveRateLimiter] = {}
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        self.global_config = AdaptiveConfig()
    
    def get_limiter(self, site_id: str, config: AdaptiveConfig = None) -> AdaptiveRateLimiter:
        """Get or create rate limiter for site"""
        if site_id not in self.limiters:
            self.limiters[site_id] = AdaptiveRateLimiter(
                site_id, config or self.global_config, self.redis_client
            )
        return self.limiters[site_id]
    
    async def can_make_request(self, site_id: str) -> Tuple[bool, str, float]:
        """Check if request can be made for site"""
        limiter = self.get_limiter(site_id)
        return await limiter.can_make_request()
    
    async def record_request(self, site_id: str, response_time_ms: float, 
                           success: bool, error_type: str = None):
        """Record request for site"""
        limiter = self.get_limiter(site_id)
        await limiter.record_request(response_time_ms, success, error_type)
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status for all rate limiters"""
        return {
            site_id: limiter.get_status() 
            for site_id, limiter in self.limiters.items()
        }
    
    def reset_all_metrics(self):
        """Reset metrics for all limiters"""
        for limiter in self.limiters.values():
            limiter.reset_metrics()
        self.logger.info("All rate limiter metrics reset")


# Global instance
adaptive_rate_limit_manager = AdaptiveRateLimitManager()

# Convenience functions
async def can_make_request(site_id: str) -> Tuple[bool, str, float]:
    """Check if request can be made"""
    return await adaptive_rate_limit_manager.can_make_request(site_id)

async def record_request(site_id: str, response_time_ms: float, success: bool, error_type: str = None):
    """Record request metrics"""
    await adaptive_rate_limit_manager.record_request(site_id, response_time_ms, success, error_type)

def get_rate_limit_status(site_id: str = None) -> Dict[str, Any]:
    """Get rate limiting status"""
    if site_id:
        limiter = adaptive_rate_limit_manager.limiters.get(site_id)
        return limiter.get_status() if limiter else {}
    return adaptive_rate_limit_manager.get_all_status() 