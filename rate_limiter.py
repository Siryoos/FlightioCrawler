import asyncio
import random
import time
import math
import threading
from typing import Dict, List, Optional, Union, Callable, Tuple, Any
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import requests
from urllib.robotparser import RobotFileParser
import redis
import logging
import json
from redis import Redis
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import ipaddress
import statistics

from config import config

# Import integrated circuit breaker
try:
    from adapters.strategies.circuit_breaker_integration import (
        get_integrated_circuit_breaker,
        IntegratedCircuitBreakerConfig,
        IntegrationFailureType,
        record_rate_limiter_failure,
        record_success as cb_record_success,
        can_make_request as cb_can_make_request
    )
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# UNIFIED RATE LIMITER - Single Source of Truth
# ============================================================================

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
class UnifiedRateConfig:
    """Unified rate limiting configuration"""
    # Basic rate limits
    requests_per_second: float = 1.0
    requests_per_minute: int = 60
    requests_per_hour: int = 3600
    burst_limit: int = 5
    
    # Adaptive features
    strategy: RateLimitStrategy = RateLimitStrategy.ADAPTIVE
    target_response_time_ms: float = 1000.0
    max_error_rate_percent: float = 5.0
    min_rate_per_second: float = 0.1
    max_rate_per_second: float = 10.0
    
    # Backoff and recovery
    backoff_factor: float = 2.0
    max_backoff_seconds: float = 300.0
    recovery_factor: float = 0.05
    cooldown_seconds: int = 300
    
    # Circuit breaker
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    
    # Advanced features
    use_jitter: bool = True
    use_penalties: bool = True
    store_metrics: bool = True
    
    # Database integration
    load_from_db: bool = False
    site_id: Optional[str] = None


@dataclass
class RateMetrics:
    """Comprehensive rate limiting metrics"""
    # Request tracking
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    
    # Performance metrics
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rates: deque = field(default_factory=lambda: deque(maxlen=50))
    consecutive_errors: int = 0
    consecutive_successes: int = 0
    
    # Rate adjustment history
    current_rate: float = 1.0
    adjustment_history: deque = field(default_factory=lambda: deque(maxlen=50))
    last_adjustment: datetime = field(default_factory=datetime.now)
    
    # System state
    system_state: SystemState = SystemState.OPTIMAL
    circuit_open: bool = False
    circuit_open_time: Optional[datetime] = None
    penalty_until: Optional[datetime] = None
    
    # Timestamps
    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_request_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


class UnifiedRateLimiter:
    """
    Unified rate limiter combining features from all previous implementations.
    
    Features:
    - Adaptive rate adjustment based on performance
    - Circuit breaker functionality
    - Database-backed configuration
    - Platform-specific rules
    - Penalty systems with recovery
    - Comprehensive metrics and monitoring
    - Redis support for distributed limiting
    """
    
    def __init__(self, 
                 site_id: str,
                 config: UnifiedRateConfig = None,
                 redis_client: Optional[Redis] = None,
                 db_conn=None):
        self.site_id = site_id
        self.config = config or UnifiedRateConfig()
        self.redis_client = redis_client
        self.db_conn = db_conn
        self.logger = logging.getLogger(f"{__name__}.{site_id}")
        
        # Initialize metrics
        self.metrics = RateMetrics()
        self.metrics.current_rate = self.config.requests_per_second
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initialize integrated circuit breaker
        self._init_circuit_breaker()
        
        # Load configuration from database if enabled
        if self.config.load_from_db and self.db_conn:
            self._load_config_from_db()
        
        self.logger.info(f"Unified rate limiter initialized for {site_id}")
    
    def _load_config_from_db(self):
        """Load configuration from database"""
        try:
            import psycopg2.extras
            with self.db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT rate_limit_config 
                    FROM crawler.platforms 
                    WHERE platform_code = %s AND is_active = true
                """, (self.site_id,))
                
                result = cursor.fetchone()
                if result and result['rate_limit_config']:
                    db_config = result['rate_limit_config']
                    
                    # Update config with database values
                    self.config.requests_per_second = db_config.get('requests_per_second', self.config.requests_per_second)
                    self.config.requests_per_minute = db_config.get('requests_per_minute', self.config.requests_per_minute)
                    self.config.burst_limit = db_config.get('burst_limit', self.config.burst_limit)
                    self.config.backoff_factor = db_config.get('backoff_factor', self.config.backoff_factor)
                    
                    self.logger.info(f"Loaded configuration from database for {self.site_id}")
        except Exception as e:
            self.logger.error(f"Failed to load config from database: {e}")
    
    def _init_circuit_breaker(self):
        """Initialize integrated circuit breaker"""
        if CIRCUIT_BREAKER_AVAILABLE:
            try:
                # Create circuit breaker configuration
                cb_config = IntegratedCircuitBreakerConfig(
                    rate_limiter_failure_threshold=self.config.circuit_breaker_threshold,
                    rate_limiter_recovery_timeout=float(self.config.circuit_breaker_timeout),
                    enable_adaptive_thresholds=True
                )
                
                # Get integrated circuit breaker
                self.circuit_breaker = get_integrated_circuit_breaker(
                    self.site_id, 
                    cb_config,
                    rate_limiter_callback=self._health_check
                )
                self.logger.info(f"Integrated circuit breaker initialized for {self.site_id}")
            except Exception as e:
                self.logger.error(f"Failed to initialize circuit breaker: {e}")
                self.circuit_breaker = None
        else:
            self.circuit_breaker = None
            self.logger.warning("Circuit breaker integration not available")
    
    async def _health_check(self) -> bool:
        """Health check callback for circuit breaker"""
        try:
            # Check if rate limiter is healthy
            with self._lock:
                # Basic health checks
                if self.metrics.penalty_until and datetime.now() < self.metrics.penalty_until:
                    return False
                
                # Check error rate
                if self.metrics.total_requests > 10:
                    error_rate = (self.metrics.failed_requests / self.metrics.total_requests) * 100
                    if error_rate > self.config.max_error_rate_percent:
                        return False
                
                return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def _map_error_to_failure_type(self, error_type: str) -> 'IntegrationFailureType':
        """Map error type to integration failure type"""
        if not CIRCUIT_BREAKER_AVAILABLE:
            return None
        
        mapping = {
            "rate_limit": IntegrationFailureType.RATE_LIMIT_EXCEEDED,
            "timeout": IntegrationFailureType.TIMEOUT,
            "network": IntegrationFailureType.NETWORK_ERROR,
            "validation": IntegrationFailureType.VALIDATION_ERROR,
            "adapter": IntegrationFailureType.ADAPTER_FAILURE,
            "error_handler": IntegrationFailureType.ERROR_HANDLER_FAILURE
        }
        
        return mapping.get(error_type, IntegrationFailureType.RATE_LIMIT_EXCEEDED)
    
    async def can_make_request(self) -> Tuple[bool, str, float]:
        """
        Check if a request can be made.
        Returns: (can_proceed, reason, wait_time_seconds)
        """
        current_time = time.time()
        
        with self._lock:
            # Check if in penalty period
            if self.metrics.penalty_until and datetime.now() < self.metrics.penalty_until:
                remaining = (self.metrics.penalty_until - datetime.now()).total_seconds()
                return False, "penalty_period", remaining
            
            # Check integrated circuit breaker
            if self.circuit_breaker and CIRCUIT_BREAKER_AVAILABLE:
                try:
                    can_proceed = await self.circuit_breaker.can_make_request("rate_limiter")
                    if not can_proceed:
                        return False, "circuit_breaker_open", 30.0  # Default wait time
                except Exception as e:
                    self.logger.error(f"Circuit breaker check failed: {e}")
                    # Fall back to legacy circuit breaker logic
                    if self.metrics.circuit_open:
                        if self._should_attempt_recovery(current_time):
                            self.metrics.circuit_open = False
                            self.logger.info(f"Circuit breaker reset for {self.site_id}")
                        else:
                            remaining = self.config.circuit_breaker_timeout - (current_time - self.metrics.circuit_open_time.timestamp())
                            return False, "circuit_breaker_open", max(0, remaining)
            else:
                # Legacy circuit breaker logic
                if self.metrics.circuit_open:
                    if self._should_attempt_recovery(current_time):
                        self.metrics.circuit_open = False
                        self.logger.info(f"Circuit breaker reset for {self.site_id}")
                    else:
                        remaining = self.config.circuit_breaker_timeout - (current_time - self.metrics.circuit_open_time.timestamp())
                        return False, "circuit_breaker_open", max(0, remaining)
            
            # Check rate limits
            if not self._check_rate_limits(current_time):
                wait_time = self._calculate_wait_time(current_time)
                return False, "rate_limit_exceeded", wait_time
            
            return True, "allowed", 0.0
    
    def _check_rate_limits(self, current_time: float) -> bool:
        """Check current rate against limits"""
        # Clean old timestamps
        cutoff_time = current_time - 1.0
        while self.metrics.request_timestamps and self.metrics.request_timestamps[0] < cutoff_time:
            self.metrics.request_timestamps.popleft()
        
        # Use adaptive rate if available
        current_rate = self.metrics.current_rate if self.config.strategy == RateLimitStrategy.ADAPTIVE else self.config.requests_per_second
        
        # Check requests per second
        if len(self.metrics.request_timestamps) >= current_rate:
            return False
        
        # Check burst limit
        burst_window = current_time - 10.0
        burst_requests = sum(1 for ts in self.metrics.request_timestamps if ts > burst_window)
        if burst_requests >= self.config.burst_limit:
            return False
        
        return True
    
    def _calculate_wait_time(self, current_time: float) -> float:
        """Calculate wait time before next request"""
        if not self.metrics.request_timestamps:
            return 0.0
        
        base_delay = 1.0 / self.metrics.current_rate
        
        # Add jitter if enabled
        if self.config.use_jitter:
            jitter_factor = random.uniform(0.8, 1.2)
            base_delay *= jitter_factor
        
        return base_delay
    
    async def record_request(self, response_time_ms: float, success: bool, error_type: str = None):
        """Record request metrics and adjust rate limits"""
        current_time = time.time()
        
        with self._lock:
            # Record basic metrics
            self.metrics.total_requests += 1
            self.metrics.request_timestamps.append(current_time)
            self.metrics.last_request_time = datetime.now()
            
            if success:
                self.metrics.successful_requests += 1
                self.metrics.consecutive_successes += 1
                self.metrics.consecutive_errors = 0
                
                # Handle success for penalty reduction
                if self.config.use_penalties:
                    await self._handle_success()
            else:
                self.metrics.failed_requests += 1
                self.metrics.consecutive_errors += 1
                self.metrics.consecutive_successes = 0
                
                # Handle failure
                if self.config.use_penalties:
                    await self._handle_failure(error_type)
            
            # Record performance metrics
            if response_time_ms > 0:
                self.metrics.response_times.append(response_time_ms)
            
            # Update error rate
            total_recent = self.metrics.successful_requests + self.metrics.failed_requests
            if total_recent > 0:
                error_rate = (self.metrics.failed_requests / total_recent) * 100
                self.metrics.error_rates.append(error_rate)
            
            # Adaptive rate adjustment
            if self.config.strategy == RateLimitStrategy.ADAPTIVE:
                await self._adjust_rate_adaptively()
            
            # Circuit breaker integration
            if self.circuit_breaker and CIRCUIT_BREAKER_AVAILABLE:
                try:
                    if success:
                        await self.circuit_breaker.record_success("rate_limiter")
                    else:
                        # Map error type to integration failure type
                        failure_type = self._map_error_to_failure_type(error_type)
                        await self.circuit_breaker.record_rate_limiter_failure(
                            failure_type, 
                            f"Rate limiter failure: {error_type or 'unknown'}"
                        )
                except Exception as e:
                    self.logger.error(f"Circuit breaker recording failed: {e}")
                    # Fall back to legacy circuit breaker logic
                    if (self.metrics.consecutive_errors >= self.config.circuit_breaker_threshold and 
                        not self.metrics.circuit_open):
                        self._open_circuit_breaker()
            else:
                # Legacy circuit breaker logic
                if (self.metrics.consecutive_errors >= self.config.circuit_breaker_threshold and 
                    not self.metrics.circuit_open):
                    self._open_circuit_breaker()
            
            # Store metrics in Redis if available
            if self.redis_client and self.config.store_metrics:
                await self._store_metrics_in_redis()
    
    async def _handle_success(self):
        """Handle successful request - reduce penalties"""
        if self.metrics.penalty_until:
            # Gradually reduce penalty
            remaining = (self.metrics.penalty_until - datetime.now()).total_seconds()
            if remaining > 60:
                new_remaining = max(remaining * 0.9, 60)
                self.metrics.penalty_until = datetime.now() + timedelta(seconds=new_remaining)
                self.logger.debug(f"Reduced penalty for {self.site_id}")
    
    async def _handle_failure(self, error_type: str = None):
        """Handle failed request - apply penalties"""
        if error_type == "rate_limit" or self.metrics.consecutive_errors >= 3:
            # Apply exponential backoff penalty
            current_penalty = 0
            if self.metrics.penalty_until and self.metrics.penalty_until > datetime.now():
                current_penalty = (self.metrics.penalty_until - datetime.now()).total_seconds()
            
            new_penalty = min(
                max(60, current_penalty * self.config.backoff_factor),
                self.config.max_backoff_seconds
            )
            
            self.metrics.penalty_until = datetime.now() + timedelta(seconds=new_penalty)
            self.logger.warning(f"Applied penalty to {self.site_id}: {new_penalty}s")
    
    async def _adjust_rate_adaptively(self):
        """Adjust rate based on performance metrics"""
        if len(self.metrics.response_times) < 10:
            return  # Need sufficient data
        
        current_time = datetime.now()
        if (current_time - self.metrics.last_adjustment).total_seconds() < 30:
            return  # Don't adjust too frequently
        
        # Calculate performance indicators
        avg_response_time = statistics.mean(self.metrics.response_times)
        recent_error_rate = statistics.mean(list(self.metrics.error_rates)[-10:]) if self.metrics.error_rates else 0
        
        # Determine adjustment direction
        adjustment_factor = 1.0
        
        if avg_response_time > self.config.target_response_time_ms * 1.5:
            # Response time too high - decrease rate
            adjustment_factor = 0.8
        elif recent_error_rate > self.config.max_error_rate_percent:
            # Error rate too high - decrease rate
            adjustment_factor = 0.7
        elif (avg_response_time < self.config.target_response_time_ms * 0.8 and 
              recent_error_rate < self.config.max_error_rate_percent * 0.5):
            # Performance good - increase rate
            adjustment_factor = 1.2
        
        # Apply adjustment
        if adjustment_factor != 1.0:
            old_rate = self.metrics.current_rate
            new_rate = max(
                self.config.min_rate_per_second,
                min(self.config.max_rate_per_second, old_rate * adjustment_factor)
            )
            
            if abs(new_rate - old_rate) > 0.1:  # Only adjust if significant change
                self.metrics.current_rate = new_rate
                self.metrics.adjustment_history.append({
                    'timestamp': current_time,
                    'old_rate': old_rate,
                    'new_rate': new_rate,
                    'reason': f'response_time={avg_response_time:.1f}ms, error_rate={recent_error_rate:.1f}%'
                })
                self.metrics.last_adjustment = current_time
                
                self.logger.info(f"Adjusted rate for {self.site_id}: {old_rate:.2f} -> {new_rate:.2f} req/s")
    
    def _open_circuit_breaker(self):
        """Open circuit breaker due to consecutive failures"""
        self.metrics.circuit_open = True
        self.metrics.circuit_open_time = datetime.now()
        self.logger.warning(f"Circuit breaker opened for {self.site_id}")
    
    def _should_attempt_recovery(self, current_time: float) -> bool:
        """Check if circuit breaker should attempt recovery"""
        if not self.metrics.circuit_open_time:
            return False
        
        elapsed = current_time - self.metrics.circuit_open_time.timestamp()
        return elapsed >= self.config.circuit_breaker_timeout
    
    async def _store_metrics_in_redis(self):
        """Store metrics in Redis for monitoring"""
        if not self.redis_client:
            return
        
        try:
            metrics_key = f"rate_limiter:metrics:{self.site_id}"
            metrics_data = {
                'total_requests': self.metrics.total_requests,
                'successful_requests': self.metrics.successful_requests,
                'failed_requests': self.metrics.failed_requests,
                'current_rate': self.metrics.current_rate,
                'system_state': self.metrics.system_state.value,
                'circuit_open': self.metrics.circuit_open,
                'last_updated': datetime.now().isoformat()
            }
            
            await self.redis_client.hset(metrics_key, mapping=metrics_data)
            await self.redis_client.expire(metrics_key, 3600)  # Expire after 1 hour
        except Exception as e:
            self.logger.error(f"Failed to store metrics in Redis: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        avg_response_time = statistics.mean(self.metrics.response_times) if self.metrics.response_times else 0
        error_rate = 0
        if self.metrics.total_requests > 0:
            error_rate = (self.metrics.failed_requests / self.metrics.total_requests) * 100
        
        return {
            'site_id': self.site_id,
            'current_rate': self.metrics.current_rate,
            'configured_rate': self.config.requests_per_second,
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'blocked_requests': self.metrics.blocked_requests,
            'error_rate_percent': error_rate,
            'avg_response_time_ms': avg_response_time,
            'consecutive_errors': self.metrics.consecutive_errors,
            'consecutive_successes': self.metrics.consecutive_successes,
            'system_state': self.metrics.system_state.value,
            'circuit_open': self.metrics.circuit_open,
            'in_penalty': self.metrics.penalty_until > datetime.now() if self.metrics.penalty_until else False,
            'strategy': self.config.strategy.value,
            'last_request': self.metrics.last_request_time.isoformat() if self.metrics.last_request_time else None,
            'created_at': self.metrics.created_at.isoformat()
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        with self._lock:
            self.metrics = RateMetrics()
            self.metrics.current_rate = self.config.requests_per_second
            self.logger.info(f"Reset metrics for {self.site_id}")


class UnifiedRateLimitManager:
    """Manager for multiple unified rate limiters"""
    
    def __init__(self, redis_client: Optional[Redis] = None, db_conn=None):
        self.limiters: Dict[str, UnifiedRateLimiter] = {}
        self.redis_client = redis_client
        self.db_conn = db_conn
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
    
    def get_limiter(self, site_id: str, config: UnifiedRateConfig = None) -> UnifiedRateLimiter:
        """Get or create rate limiter for site"""
        with self._lock:
            if site_id not in self.limiters:
                if not config:
                    config = UnifiedRateConfig(site_id=site_id, load_from_db=bool(self.db_conn))
                
                self.limiters[site_id] = UnifiedRateLimiter(
                    site_id=site_id,
                    config=config,
                    redis_client=self.redis_client,
                    db_conn=self.db_conn
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


# Global manager instance
_global_manager: Optional[UnifiedRateLimitManager] = None

def get_unified_rate_limiter(redis_client: Optional[Redis] = None, db_conn=None) -> UnifiedRateLimitManager:
    """Get the global unified rate limiter manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = UnifiedRateLimitManager(redis_client, db_conn)
    return _global_manager


# ============================================================================
# LEGACY IMPLEMENTATIONS - DEPRECATED - Use UnifiedRateLimiter instead
# ============================================================================

import warnings

# Rate limit configurations for different endpoint types
RATE_LIMIT_CONFIGS = {
    "default": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "burst_limit": 10,
    },
    "search": {"requests_per_minute": 20, "requests_per_hour": 200, "burst_limit": 5},
    "crawl": {"requests_per_minute": 5, "requests_per_hour": 50, "burst_limit": 2},
    "health": {
        "requests_per_minute": 120,
        "requests_per_hour": 2000,
        "burst_limit": 20,
    },
    "metrics": {"requests_per_minute": 30, "requests_per_hour": 500, "burst_limit": 10},
    "admin": {"requests_per_minute": 10, "requests_per_hour": 100, "burst_limit": 3},
}

# User type rate limits
USER_TYPE_LIMITS = {"anonymous": 1.0, "registered": 2.0, "premium": 5.0, "admin": 10.0}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Advanced FastAPI rate limiting middleware"""

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Optional[Redis] = None,
        enable_ip_whitelist: bool = True,
        enable_user_type_limits: bool = True,
    ):
        super().__init__(app)

        # Initialize Redis
        if redis_client:
            self.redis = redis_client
        else:
            try:
                redis_cfg = config.REDIS
                redis_url = f"redis://{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
                if redis_cfg.PASSWORD:
                    redis_url = f"redis://:{redis_cfg.PASSWORD}@{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Redis connection failed, using local fallback: {e}")
                self.redis = None

        self.enable_ip_whitelist = enable_ip_whitelist
        self.enable_user_type_limits = enable_user_type_limits

        # IP whitelist for admin/internal services
        self.ip_whitelist = {"127.0.0.1", "::1", "localhost"}

        # Local rate limit cache (fallback)
        self.local_cache = defaultdict(lambda: defaultdict(deque))

        # Endpoint pattern mapping
        self.endpoint_patterns = {
            "/search": "search",
            "/search/intelligent": "search",
            "/crawl": "crawl",
            "/health": "health",
            "/metrics": "metrics",
            "/stats": "metrics",
            "/api/v1": "admin",
            "/reset": "admin",
            "/monitor": "admin",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check if IP is whitelisted
        if self.enable_ip_whitelist and self._is_whitelisted_ip(client_ip):
            return await call_next(request)

        # Determine endpoint type and rate limit config
        endpoint_type = self._get_endpoint_type(request.url.path)
        rate_config = RATE_LIMIT_CONFIGS.get(
            endpoint_type, RATE_LIMIT_CONFIGS["default"]
        )

        # Get user type multiplier
        user_multiplier = await self._get_user_type_multiplier(request)

        # Apply user type multiplier to rate limits
        effective_config = {
            "requests_per_minute": int(
                rate_config["requests_per_minute"] * user_multiplier
            ),
            "requests_per_hour": int(
                rate_config["requests_per_hour"] * user_multiplier
            ),
            "burst_limit": int(rate_config["burst_limit"] * user_multiplier),
        }

        # Check rate limits
        rate_limit_result = await self._check_rate_limits(
            client_ip, endpoint_type, effective_config
        )

        if not rate_limit_result["allowed"]:
            return await self._create_rate_limit_response(rate_limit_result)

        # Process request
        try:
            response = await call_next(request)

            # Record successful request
            await self._record_request(client_ip, endpoint_type, "success")

            # Add rate limit headers
            self._add_rate_limit_headers(response, rate_limit_result)

            return response

        except Exception as e:
            # Record failed request
            await self._record_request(client_ip, endpoint_type, "error")
            raise e

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        return request.client.host if request.client else "unknown"

    def _is_whitelisted_ip(self, ip: str) -> bool:
        """Check if IP is in whitelist"""
        if ip in self.ip_whitelist:
            return True

        # Check for private IP ranges
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback:
                return True
        except ValueError:
            pass

        return False

    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type from path"""
        for pattern, endpoint_type in self.endpoint_patterns.items():
            if path.startswith(pattern):
                return endpoint_type
        return "default"

    async def _get_user_type_multiplier(self, request: Request) -> float:
        """Get rate limit multiplier based on user type"""
        if not self.enable_user_type_limits:
            return 1.0

        # Check for API key or authorization header
        api_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization")

        if api_key:
            # Look up user type from API key
            user_type = await self._get_user_type_from_api_key(api_key)
            return USER_TYPE_LIMITS.get(user_type, USER_TYPE_LIMITS["anonymous"])

        if auth_header:
            # Look up user type from auth token
            user_type = await self._get_user_type_from_auth(auth_header)
            return USER_TYPE_LIMITS.get(user_type, USER_TYPE_LIMITS["anonymous"])

        return USER_TYPE_LIMITS["anonymous"]

    async def _get_user_type_from_api_key(self, api_key: str) -> str:
        """Get user type from API key"""
        if not self.redis:
            return "anonymous"

        try:
            user_info = await self.redis.hget(f"api_key:{api_key}", "user_type")
            return user_info or "anonymous"
        except Exception:
            return "anonymous"

    async def _get_user_type_from_auth(self, auth_header: str) -> str:
        """Get user type from authorization header"""
        # This would typically decode JWT token and extract user type
        # For now, return anonymous
        return "anonymous"

    async def _check_rate_limits(
        self, client_ip: str, endpoint_type: str, config: Dict
    ) -> Dict:
        """Check all rate limits for client"""

        # Generate cache keys
        minute_key = (
            f"rate_limit:{client_ip}:{endpoint_type}:minute:{int(time.time() // 60)}"
        )
        hour_key = (
            f"rate_limit:{client_ip}:{endpoint_type}:hour:{int(time.time() // 3600)}"
        )
        burst_key = f"rate_limit:{client_ip}:{endpoint_type}:burst"

        if self.redis:
            return await self._check_redis_rate_limits(
                minute_key, hour_key, burst_key, config
            )
        else:
            return await self._check_local_rate_limits(client_ip, endpoint_type, config)

    async def _check_redis_rate_limits(
        self, minute_key: str, hour_key: str, burst_key: str, config: Dict
    ) -> Dict:
        """Check rate limits using Redis"""
        try:
            pipe = self.redis.pipeline()
            pipe.get(minute_key)
            pipe.get(hour_key)
            pipe.get(burst_key)
            results = pipe.execute()

            minute_count = int(results[0] or 0)
            hour_count = int(results[1] or 0)
            burst_count = int(results[2] or 0)

            # Check limits
            if minute_count >= config["requests_per_minute"]:
                return {
                    "allowed": False,
                    "limit_type": "minute",
                    "limit": config["requests_per_minute"],
                    "remaining": 0,
                    "reset_time": (int(time.time() // 60) + 1) * 60,
                }

            if hour_count >= config["requests_per_hour"]:
                return {
                    "allowed": False,
                    "limit_type": "hour",
                    "limit": config["requests_per_hour"],
                    "remaining": 0,
                    "reset_time": (int(time.time() // 3600) + 1) * 3600,
                }

            if burst_count >= config["burst_limit"]:
                return {
                    "allowed": False,
                    "limit_type": "burst",
                    "limit": config["burst_limit"],
                    "remaining": 0,
                    "reset_time": int(time.time()) + 60,
                }

            # Increment counters
            pipe = self.redis.pipeline()
            pipe.incr(minute_key, 1)
            pipe.expire(minute_key, 60)
            pipe.incr(hour_key, 1)
            pipe.expire(hour_key, 3600)
            pipe.incr(burst_key, 1)
            pipe.expire(burst_key, 60)
            pipe.execute()

            return {
                "allowed": True,
                "minute_remaining": config["requests_per_minute"] - minute_count - 1,
                "hour_remaining": config["requests_per_hour"] - hour_count - 1,
                "burst_remaining": config["burst_limit"] - burst_count - 1,
            }

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return {"allowed": True}  # Fail open

    async def _check_local_rate_limits(
        self, client_ip: str, endpoint_type: str, config: Dict
    ) -> Dict:
        """Check rate limits using local cache"""
        now = time.time()

        # Clean old entries
        minute_window = now - 60
        hour_window = now - 3600

        minute_requests = self.local_cache[f"{client_ip}:{endpoint_type}"]["minute"]
        hour_requests = self.local_cache[f"{client_ip}:{endpoint_type}"]["hour"]

        # Remove old requests
        while minute_requests and minute_requests[0] < minute_window:
            minute_requests.popleft()
        while hour_requests and hour_requests[0] < hour_window:
            hour_requests.popleft()

        # Check limits
        if len(minute_requests) >= config["requests_per_minute"]:
            return {
                "allowed": False,
                "limit_type": "minute",
                "limit": config["requests_per_minute"],
                "remaining": 0,
                "reset_time": minute_requests[0] + 60,
            }

        if len(hour_requests) >= config["requests_per_hour"]:
            return {
                "allowed": False,
                "limit_type": "hour",
                "limit": config["requests_per_hour"],
                "remaining": 0,
                "reset_time": hour_requests[0] + 3600,
            }

        # Add current request
        minute_requests.append(now)
        hour_requests.append(now)

        return {
            "allowed": True,
            "minute_remaining": config["requests_per_minute"] - len(minute_requests),
            "hour_remaining": config["requests_per_hour"] - len(hour_requests),
        }

    async def _record_request(self, client_ip: str, endpoint_type: str, status: str):
        """Record request for analytics"""
        if not self.redis:
            return

        try:
            stats_key = f"rate_limit_stats:{endpoint_type}:{int(time.time() // 3600)}"
            pipe = self.redis.pipeline()
            pipe.hincrby(stats_key, f"requests_{status}", 1)
            pipe.hincrby(stats_key, "total_requests", 1)
            pipe.expire(stats_key, 86400)  # Keep for 24 hours
            pipe.execute()
        except Exception as e:
            logger.error(f"Failed to record request stats: {e}")

    async def _create_rate_limit_response(
        self, rate_limit_result: Dict
    ) -> JSONResponse:
        """Create rate limit exceeded response"""

        headers = {
            "X-RateLimit-Limit": str(rate_limit_result["limit"]),
            "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
            "X-RateLimit-Reset": str(rate_limit_result["reset_time"]),
            "Retry-After": str(
                max(1, rate_limit_result["reset_time"] - int(time.time()))
            ),
        }

        response_data = {
            "error": "Rate limit exceeded",
            "message": f"Too many requests for {rate_limit_result['limit_type']} window",
            "limit": rate_limit_result["limit"],
            "remaining": rate_limit_result["remaining"],
            "reset_time": rate_limit_result["reset_time"],
            "retry_after": max(1, rate_limit_result["reset_time"] - int(time.time())),
        }

        return JSONResponse(status_code=429, content=response_data, headers=headers)

    def _add_rate_limit_headers(self, response: Response, rate_limit_result: Dict):
        """Add rate limit headers to successful response"""
        if rate_limit_result.get("allowed"):
            if "minute_remaining" in rate_limit_result:
                response.headers["X-RateLimit-Remaining-Minute"] = str(
                    rate_limit_result["minute_remaining"]
                )
            if "hour_remaining" in rate_limit_result:
                response.headers["X-RateLimit-Remaining-Hour"] = str(
                    rate_limit_result["hour_remaining"]
                )
            if "burst_remaining" in rate_limit_result:
                response.headers["X-RateLimit-Remaining-Burst"] = str(
                    rate_limit_result["burst_remaining"]
                )


class RespectfulRateLimiter:
    """Implements respectful rate limiting and anti-bot evasion"""

    def __init__(self):
        self.domain_delays = {
            "flytoday.ir": (3, 6),  # 3-6 seconds between requests
            "alibaba.ir": (2, 4),  # 2-4 seconds
            "safarmarket.com": (2, 5),  # 2-5 seconds
            "default": (1, 3),
        }

        self.last_request_time = defaultdict(float)
        self.request_counts = defaultdict(lambda: deque(maxlen=100))
        self.robots_cache = {}
        self.blocked_domains = set()

    async def wait_for_domain(self, domain: str):
        """Wait appropriate time before requesting from domain"""
        if domain in self.blocked_domains:
            raise Exception(f"Domain {domain} is temporarily blocked")

        min_delay, max_delay = self.domain_delays.get(
            domain, self.domain_delays["default"]
        )

        # Calculate delay since last request
        elapsed = time.time() - self.last_request_time[domain]
        base_delay = random.uniform(min_delay, max_delay)

        # Add extra delay if we've been making frequent requests
        recent_requests = len(
            [t for t in self.request_counts[domain] if time.time() - t < 300]
        )  # Last 5 minutes

        if recent_requests > 20:
            base_delay *= 2  # Double delay for frequent requests

        if elapsed < base_delay:
            await asyncio.sleep(base_delay - elapsed)

        # Record this request
        self.last_request_time[domain] = time.time()
        self.request_counts[domain].append(time.time())

    def check_robots_txt(
        self, domain: str, path: str = "/", user_agent: str = "*"
    ) -> bool:
        """Check if path is allowed by robots.txt"""
        if domain not in self.robots_cache:
            try:
                rp = RobotFileParser()
                rp.set_url(f"https://{domain}/robots.txt")
                rp.read()
                self.robots_cache[domain] = rp
            except:
                # If robots.txt not accessible, assume allowed
                return True

        return self.robots_cache[domain].can_fetch(user_agent, path)

    def handle_rate_limit_response(self, domain: str, status_code: int):
        """Handle rate limiting responses"""
        if status_code in [429, 503, 504]:
            # Temporarily block domain
            self.blocked_domains.add(domain)

            # Remove block after delay
            asyncio.create_task(self.unblock_domain_later(domain, 300))  # 5 minutes

    async def unblock_domain_later(self, domain: str, delay: int):
        """Remove domain from blocked list after delay"""
        await asyncio.sleep(delay)
        self.blocked_domains.discard(domain)


class ProxyRotator:
    """Manages proxy rotation for distributed requests"""

    def __init__(self, proxy_list: List[str] = None):
        self.proxies = proxy_list or []
        self.current_proxy_index = 0
        self.proxy_failures = defaultdict(int)
        self.max_failures = 3

    def get_next_proxy(self) -> Dict[str, str]:
        """Get next available proxy"""
        if not self.proxies:
            return {}

        # Find next working proxy
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_proxy_index]

            if self.proxy_failures[proxy] < self.max_failures:
                self.current_proxy_index = (self.current_proxy_index + 1) % len(
                    self.proxies
                )
                return {"http": f"http://{proxy}", "https": f"https://{proxy}"}

            self.current_proxy_index = (self.current_proxy_index + 1) % len(
                self.proxies
            )
            attempts += 1

        # All proxies failed, reset failures and try again
        self.proxy_failures.clear()
        return self.get_next_proxy()

    def report_proxy_failure(self, proxy: str):
        """Report proxy failure"""
        self.proxy_failures[proxy] += 1


class RateLimiter:
    """
    DEPRECATED: Rate limiter for crawler requests.
    
    Use UnifiedRateLimiter instead for better performance and more features.
    This class is kept for backward compatibility only.
    """

    def __init__(self):
        warnings.warn(
            "RateLimiter is deprecated. Use get_unified_rate_limiter() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Initialize Redis
        redis_cfg = config.REDIS
        redis_url = f"redis://{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
        if redis_cfg.PASSWORD:
            redis_url = (
                f"redis://:{redis_cfg.PASSWORD}@{redis_cfg.HOST}:{redis_cfg.PORT}/"
                f"{redis_cfg.DB}"
            )
        try:
            self.redis = Redis.from_url(redis_url)
        except Exception:
            self.redis = Redis.from_url("redis://localhost:6379/0")

    def check_rate_limit(self, domain: str) -> bool:
        """Check if request is allowed"""
        try:
            # Get rate limit settings
            rate_limit = config.SITES[domain]["rate_limit"]
            rate_period = config.SITES[domain]["rate_period"]

            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)

            # Check if limit exceeded
            if count >= rate_limit:
                return False

            # Increment count
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, rate_period)
            pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True

    def get_wait_time(self, domain: str) -> int:
        """Get time to wait before next request"""
        try:
            # Get key TTL
            key = f"rate_limit:{domain}"
            ttl = self.redis.ttl(key)

            return max(0, ttl)

        except Exception as e:
            logger.error(f"Error getting wait time: {e}")
            return 0

    def reset_rate_limit(self, domain: str) -> None:
        """Reset rate limit for domain"""
        try:
            # Delete key
            key = f"rate_limit:{domain}"
            self.redis.delete(key)

        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")

    def get_rate_limit_stats(self, domain: str) -> Dict:
        """Get rate limit statistics"""
        try:
            # Get rate limit settings
            rate_limit = config.SITES[domain]["rate_limit"]
            rate_period = config.SITES[domain]["rate_period"]

            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)

            # Get TTL
            ttl = self.redis.ttl(key)

            return {
                "domain": domain,
                "current_count": count,
                "max_requests": rate_limit,
                "period_seconds": rate_period,
                "time_to_reset": ttl,
            }

        except Exception as e:
            logger.error(f"Error getting rate limit stats: {e}")
            return {}

    def get_all_rate_limit_stats(self) -> Dict[str, Dict]:
        """Get rate limit statistics for all domains"""
        try:
            return {
                domain: self.get_rate_limit_stats(domain)
                for domain in config.SITES.keys()
            }

        except Exception as e:
            logger.error(f"Error getting all rate limit stats: {e}")
            return {}

    def is_rate_limited(self, domain: str) -> bool:
        """Check if domain is rate limited"""
        try:
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)

            # Get rate limit
            rate_limit = config.SITES[domain]["rate_limit"]

            return count >= rate_limit

        except Exception as e:
            logger.error(f"Error checking rate limit status: {e}")
            return False

    def get_remaining_requests(self, domain: str) -> int:
        """Get remaining requests for domain"""
        try:
            # Get current count
            key = f"rate_limit:{domain}"
            count = int(self.redis.get(key) or 0)

            # Get rate limit
            rate_limit = config.SITES[domain]["rate_limit"]

            return max(0, rate_limit - count)

        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return 0

    def get_reset_time(self, domain: str) -> Optional[datetime]:
        """Get time when rate limit resets"""
        try:
            # Get TTL
            key = f"rate_limit:{domain}"
            ttl = self.redis.ttl(key)

            if ttl > 0:
                return datetime.now() + timedelta(seconds=ttl)

            return None

        except Exception as e:
            logger.error(f"Error getting reset time: {e}")
            return None

    def get_all_reset_times(self) -> Dict[str, Optional[datetime]]:
        """Get reset times for all domains"""
        try:
            return {
                domain: self.get_reset_time(domain) for domain in config.SITES.keys()
            }

        except Exception as e:
            logger.error(f"Error getting all reset times: {e}")
            return {}

    def clear_rate_limits(self) -> None:
        """Clear all rate limits"""
        try:
            # Delete all rate limit keys
            for domain in config.SITES.keys():
                key = f"rate_limit:{domain}"
                self.redis.delete(key)

        except Exception as e:
            logger.error(f"Error clearing rate limits: {e}")

    def get_rate_limit_keys(self) -> Dict[str, str]:
        """Get rate limit keys for all domains"""
        try:
            return {domain: f"rate_limit:{domain}" for domain in config.SITES.keys()}

        except Exception as e:
            logger.error(f"Error getting rate limit keys: {e}")
            return {}


class AdvancedRateLimiter:
    """
    DEPRECATED: Advanced rate limiter with adaptive delays and platform-specific configurations.
    
    Use UnifiedRateLimiter instead for better performance and more features.
    This class is kept for backward compatibility only.
    """

    def __init__(self, redis_client: Redis):
        warnings.warn(
            "AdvancedRateLimiter is deprecated. Use get_unified_rate_limiter() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        self.redis = redis_client
        self.platform_configs = {}
        self.logger = logging.getLogger(__name__)

    def configure_platform(self, platform_id: str, config: dict):
        """Configure rate limiting for specific platform"""
        self.platform_configs[platform_id] = {
            "requests_per_second": config.get("requests_per_second", 1),
            "burst_limit": config.get("burst_limit", 5),
            "backoff_factor": config.get("backoff_factor", 2),
            "max_delay": config.get("max_delay", 300),
            "jitter": config.get("jitter", True),
            "use_persian_ip": config.get("use_persian_ip", False),
        }

    async def wait(self, platform_id: str):
        """Intelligent rate limiting with adaptive delays"""
        config = self.platform_configs.get(platform_id, {})

        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)

        if penalty:
            delay = min(int(penalty), config.get("max_delay", 300))
            self.logger.info(
                f"Platform {platform_id} in penalty mode, waiting {delay}s"
            )
            await asyncio.sleep(delay)

        requests_per_second = config.get("requests_per_second", 1)
        base_delay = 1.0 / requests_per_second

        if config.get("jitter", True):
            jitter_factor = random.uniform(0.5, 1.5)
            delay = base_delay * jitter_factor
        else:
            delay = base_delay

        if config.get("use_persian_ip", False):
            delay *= 1.5

        await asyncio.sleep(delay)

    async def handle_rate_limit_exceeded(self, platform_id: str):
        """Handle rate limit exceeded scenario"""
        config = self.platform_configs.get(platform_id, {})

        penalty_key = f"rate_limit:penalty:{platform_id}"
        current_penalty = await self.redis.get(penalty_key)

        if current_penalty:
            new_penalty = min(
                int(current_penalty) * config.get("backoff_factor", 2),
                config.get("max_delay", 300),
            )
        else:
            new_penalty = config.get("initial_penalty", 60)

        await self.redis.setex(penalty_key, new_penalty * 2, new_penalty)
        self.logger.warning(
            f"Rate limit exceeded for {platform_id}, new penalty: {new_penalty}s"
        )

    async def handle_success(self, platform_id: str):
        """Handle successful request to potentially reduce penalties"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        current_penalty = await self.redis.get(penalty_key)

        if current_penalty and int(current_penalty) > 60:
            new_penalty = max(int(current_penalty) * 0.9, 60)
            await self.redis.setex(penalty_key, new_penalty * 2, new_penalty)
            self.logger.info(f"Reduced penalty for {platform_id} to {new_penalty}s")

    async def get_platform_health(self, platform_id: str) -> Dict[str, float]:
        """Get platform health metrics"""
        success_key = f"rate_limit:success:{platform_id}"
        failure_key = f"rate_limit:failure:{platform_id}"

        success_count = int(await self.redis.get(success_key) or 0)
        failure_count = int(await self.redis.get(failure_key) or 0)

        total_requests = success_count + failure_count
        if total_requests == 0:
            return {"success_rate": 1.0, "failure_rate": 0.0, "total_requests": 0}

        return {
            "success_rate": success_count / total_requests,
            "failure_rate": failure_count / total_requests,
            "total_requests": total_requests,
        }

    async def reset_platform_stats(self, platform_id: str):
        """Reset platform statistics"""
        keys = [
            f"rate_limit:success:{platform_id}",
            f"rate_limit:failure:{platform_id}",
            f"rate_limit:penalty:{platform_id}",
        ]

        await self.redis.delete(*keys)
        self.logger.info(f"Reset statistics for platform {platform_id}")

    async def get_wait_time(self, platform_id: str) -> Optional[int]:
        """Get current wait time for platform"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)

        if penalty:
            return int(penalty)

        config = self.platform_configs.get(platform_id, {})
        return int(1.0 / config.get("requests_per_second", 1))

    async def check_rate_limit(self, platform_id: str) -> bool:
        """Check if platform is within rate limits"""
        penalty_key = f"rate_limit:penalty:{platform_id}"
        penalty = await self.redis.get(penalty_key)

        return penalty is None


class RateLimitManager:
    """Manager for rate limiting operations and analytics"""

    def __init__(self, redis_client: Optional[Redis] = None):
        if redis_client:
            self.redis = redis_client
        else:
            try:
                redis_cfg = config.REDIS
                redis_url = f"redis://{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
                if redis_cfg.PASSWORD:
                    redis_url = f"redis://:{redis_cfg.PASSWORD}@{redis_cfg.HOST}:{redis_cfg.PORT}/{redis_cfg.DB}"
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.redis = None

    async def get_rate_limit_stats(self, endpoint_type: Optional[str] = None) -> Dict:
        """Get rate limiting statistics"""
        if not self.redis:
            return {"error": "Redis not available"}

        try:
            current_hour = int(time.time() // 3600)
            stats = {}

            if endpoint_type:
                # Get stats for specific endpoint
                stats_key = f"rate_limit_stats:{endpoint_type}:{current_hour}"
                endpoint_stats = await self.redis.hgetall(stats_key)
                stats[endpoint_type] = endpoint_stats
            else:
                # Get stats for all endpoints
                for ep_type in RATE_LIMIT_CONFIGS.keys():
                    stats_key = f"rate_limit_stats:{ep_type}:{current_hour}"
                    endpoint_stats = await self.redis.hgetall(stats_key)
                    if endpoint_stats:
                        stats[ep_type] = endpoint_stats

            return stats

        except Exception as e:
            logger.error(f"Failed to get rate limit stats: {e}")
            return {"error": str(e)}

    async def get_client_rate_limit_status(
        self, client_ip: str, endpoint_type: str
    ) -> Dict:
        """Get current rate limit status for a client"""
        if not self.redis:
            return {"error": "Redis not available"}

        try:
            minute_key = f"rate_limit:{client_ip}:{endpoint_type}:minute:{int(time.time() // 60)}"
            hour_key = f"rate_limit:{client_ip}:{endpoint_type}:hour:{int(time.time() // 3600)}"
            burst_key = f"rate_limit:{client_ip}:{endpoint_type}:burst"

            pipe = self.redis.pipeline()
            pipe.get(minute_key)
            pipe.get(hour_key)
            pipe.get(burst_key)
            pipe.ttl(minute_key)
            pipe.ttl(hour_key)
            pipe.ttl(burst_key)
            results = pipe.execute()

            config = RATE_LIMIT_CONFIGS.get(
                endpoint_type, RATE_LIMIT_CONFIGS["default"]
            )

            return {
                "client_ip": client_ip,
                "endpoint_type": endpoint_type,
                "minute_requests": int(results[0] or 0),
                "hour_requests": int(results[1] or 0),
                "burst_requests": int(results[2] or 0),
                "minute_limit": config["requests_per_minute"],
                "hour_limit": config["requests_per_hour"],
                "burst_limit": config["burst_limit"],
                "minute_remaining": config["requests_per_minute"]
                - int(results[0] or 0),
                "hour_remaining": config["requests_per_hour"] - int(results[1] or 0),
                "burst_remaining": config["burst_limit"] - int(results[2] or 0),
                "minute_reset_ttl": results[3] if results[3] > 0 else 0,
                "hour_reset_ttl": results[4] if results[4] > 0 else 0,
                "burst_reset_ttl": results[5] if results[5] > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get client rate limit status: {e}")
            return {"error": str(e)}

    async def reset_client_rate_limits(
        self, client_ip: str, endpoint_type: Optional[str] = None
    ) -> Dict:
        """Reset rate limits for a client"""
        if not self.redis:
            return {"error": "Redis not available"}

        try:
            if endpoint_type:
                endpoint_types = [endpoint_type]
            else:
                endpoint_types = list(RATE_LIMIT_CONFIGS.keys())

            reset_count = 0
            for ep_type in endpoint_types:
                minute_key = f"rate_limit:{client_ip}:{ep_type}:minute:*"
                hour_key = f"rate_limit:{client_ip}:{ep_type}:hour:*"
                burst_key = f"rate_limit:{client_ip}:{ep_type}:burst"

                # Delete all keys for this client and endpoint
                for pattern in [minute_key, hour_key]:
                    keys = await self.redis.keys(pattern)
                    if keys:
                        await self.redis.delete(*keys)
                        reset_count += len(keys)

                # Delete burst key
                if await self.redis.exists(burst_key):
                    await self.redis.delete(burst_key)
                    reset_count += 1

            return {
                "message": f"Reset {reset_count} rate limit keys for client {client_ip}",
                "client_ip": client_ip,
                "endpoint_types": endpoint_types,
                "reset_count": reset_count,
            }

        except Exception as e:
            logger.error(f"Failed to reset client rate limits: {e}")
            return {"error": str(e)}

    async def update_rate_limit_config(self, endpoint_type: str, config: Dict) -> Dict:
        """Update rate limit configuration (runtime)"""
        if endpoint_type not in RATE_LIMIT_CONFIGS:
            return {"error": f"Unknown endpoint type: {endpoint_type}"}

        # Validate config
        required_fields = ["requests_per_minute", "requests_per_hour", "burst_limit"]
        for field in required_fields:
            if field not in config:
                return {"error": f"Missing required field: {field}"}
            if not isinstance(config[field], int) or config[field] <= 0:
                return {"error": f"Invalid value for {field}: must be positive integer"}

        # Update configuration
        old_config = RATE_LIMIT_CONFIGS[endpoint_type].copy()
        RATE_LIMIT_CONFIGS[endpoint_type].update(config)

        logger.info(
            f"Updated rate limit config for {endpoint_type}: {old_config} -> {RATE_LIMIT_CONFIGS[endpoint_type]}"
        )

        return {
            "message": f"Updated rate limit configuration for {endpoint_type}",
            "endpoint_type": endpoint_type,
            "old_config": old_config,
            "new_config": RATE_LIMIT_CONFIGS[endpoint_type],
        }

    async def get_blocked_clients(self, limit: int = 100) -> Dict:
        """Get currently rate limited clients"""
        if not self.redis:
            return {"error": "Redis not available"}

        try:
            # Find all rate limit keys
            all_keys = await self.redis.keys("rate_limit:*")

            blocked_clients = []
            now = time.time()

            for key in all_keys:
                # Parse key format: rate_limit:IP:endpoint:type:timestamp
                parts = key.split(":")
                if len(parts) >= 4:
                    client_ip = parts[1]
                    endpoint_type = parts[2]
                    limit_type = parts[3]

                    # Get current count and limit
                    count = int(await self.redis.get(key) or 0)
                    ttl = await self.redis.ttl(key)

                    config = RATE_LIMIT_CONFIGS.get(
                        endpoint_type, RATE_LIMIT_CONFIGS["default"]
                    )

                    if (
                        limit_type == "minute"
                        and count >= config["requests_per_minute"]
                    ):
                        blocked_clients.append(
                            {
                                "client_ip": client_ip,
                                "endpoint_type": endpoint_type,
                                "limit_type": "minute",
                                "count": count,
                                "limit": config["requests_per_minute"],
                                "reset_in_seconds": ttl,
                            }
                        )
                    elif limit_type == "hour" and count >= config["requests_per_hour"]:
                        blocked_clients.append(
                            {
                                "client_ip": client_ip,
                                "endpoint_type": endpoint_type,
                                "limit_type": "hour",
                                "count": count,
                                "limit": config["requests_per_hour"],
                                "reset_in_seconds": ttl,
                            }
                        )
                    elif limit_type == "burst" and count >= config["burst_limit"]:
                        blocked_clients.append(
                            {
                                "client_ip": client_ip,
                                "endpoint_type": endpoint_type,
                                "limit_type": "burst",
                                "count": count,
                                "limit": config["burst_limit"],
                                "reset_in_seconds": ttl,
                            }
                        )

            return {
                "blocked_clients": blocked_clients[:limit],
                "total_found": len(blocked_clients),
                "timestamp": now,
            }

        except Exception as e:
            logger.error(f"Failed to get blocked clients: {e}")
            return {"error": str(e)}

    async def whitelist_ip(self, ip: str, duration_seconds: int = 3600) -> Dict:
        """Temporarily whitelist an IP address"""
        if not self.redis:
            return {"error": "Redis not available"}

        try:
            whitelist_key = f"rate_limit_whitelist:{ip}"
            await self.redis.setex(whitelist_key, duration_seconds, "1")

            return {
                "message": f"IP {ip} whitelisted for {duration_seconds} seconds",
                "ip": ip,
                "duration": duration_seconds,
                "expires_at": time.time() + duration_seconds,
            }

        except Exception as e:
            logger.error(f"Failed to whitelist IP: {e}")
            return {"error": str(e)}

    async def is_ip_whitelisted(self, ip: str) -> bool:
        """Check if IP is temporarily whitelisted"""
        if not self.redis:
            return False

        try:
            whitelist_key = f"rate_limit_whitelist:{ip}"
            return await self.redis.exists(whitelist_key) > 0
        except Exception:
            return False


# Utility functions
async def get_rate_limit_manager() -> RateLimitManager:
    """Get rate limit manager instance"""
    return RateLimitManager()


async def create_rate_limit_middleware(
    redis_client: Optional[Redis] = None,
    enable_ip_whitelist: bool = True,
    enable_user_type_limits: bool = True,
) -> RateLimitMiddleware:
    """Create rate limit middleware instance"""
    return RateLimitMiddleware(
        app=None,  # Will be set when added to FastAPI
        redis_client=redis_client,
        enable_ip_whitelist=enable_ip_whitelist,
        enable_user_type_limits=enable_user_type_limits,
    )


# Update the RateLimitMiddleware to check for temporary whitelist
def _update_middleware_whitelist_check():
    """Update middleware to check temporary whitelist"""
    original_is_whitelisted = RateLimitMiddleware._is_whitelisted_ip

    async def enhanced_is_whitelisted_ip(self, ip: str) -> bool:
        # Check original whitelist
        if original_is_whitelisted(self, ip):
            return True

        # Check temporary whitelist
        if self.redis:
            try:
                whitelist_key = f"rate_limit_whitelist:{ip}"
                return await self.redis.exists(whitelist_key) > 0
            except Exception:
                pass

        return False

    RateLimitMiddleware._is_whitelisted_ip = enhanced_is_whitelisted_ip


# Apply the enhancement
_update_middleware_whitelist_check()
