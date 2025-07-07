"""
Enhanced Circuit Breaker System for FlightIO Crawler
Advanced circuit breaker with intelligent failure detection and recovery strategies
"""

import asyncio
import logging
import time
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import json
import statistics
import threading
from contextlib import asynccontextmanager

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import config


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


class FailureType(Enum):
    """Types of failures that can trigger circuit breaker"""
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PARSING_ERROR = "parsing_error"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Recovery strategies for circuit breaker"""
    IMMEDIATE = "immediate"          # Immediate retry after timeout
    GRADUAL = "gradual"             # Gradual increase in allowed requests
    EXPONENTIAL = "exponential"      # Exponential backoff
    ADAPTIVE = "adaptive"           # Based on success rate
    HEALTH_CHECK = "health_check"   # Based on health endpoint


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5                    # Failures to open circuit
    recovery_timeout: float = 60.0               # Seconds before attempting recovery
    success_threshold: int = 3                   # Successes to close circuit in half-open
    half_open_max_calls: int = 5                 # Max calls in half-open state
    failure_rate_threshold: float = 0.5          # Failure rate to open circuit (0-1)
    min_requests_for_rate: int = 10              # Min requests before considering rate
    sliding_window_size: int = 100               # Size of sliding window for metrics
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.GRADUAL
    enabled_failure_types: List[FailureType] = field(default_factory=lambda: list(FailureType))
    recovery_factor: float = 0.1                 # Factor for gradual recovery
    max_half_open_duration: float = 30.0         # Max time in half-open state
    health_check_interval: float = 10.0          # Health check interval
    exponential_base: float = 2.0                # Base for exponential backoff
    max_recovery_timeout: float = 3600.0         # Max recovery timeout


@dataclass
class FailureRecord:
    """Record of a failure"""
    timestamp: datetime
    failure_type: FailureType
    error_message: str
    response_time_ms: float = 0.0
    additional_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_rate: float = 0.0
    average_response_time: float = 0.0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0
    time_in_open: float = 0.0
    time_in_half_open: float = 0.0


class EnhancedCircuitBreaker:
    """Enhanced circuit breaker with intelligent failure detection and recovery"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.logger = logging.getLogger(__name__)
        
        # Circuit state
        self.state = CircuitState.CLOSED
        self.state_changed_time = datetime.now()
        self.last_state_change = datetime.now()
        
        # Metrics tracking
        self.metrics = CircuitMetrics()
        self.failure_history = deque(maxlen=self.config.sliding_window_size)
        self.request_history = deque(maxlen=self.config.sliding_window_size)
        
        # Half-open state management
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.half_open_start_time = None
        
        # Recovery management
        self.recovery_attempts = 0
        self.current_recovery_timeout = self.config.recovery_timeout
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Health check
        self.health_check_callback: Optional[Callable] = None
        self.last_health_check = None
        
        self.logger.info(f"Enhanced circuit breaker '{name}' initialized")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._request_context():
            if not await self._can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Next attempt in {self._time_until_next_attempt():.1f} seconds"
                )
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                response_time = (time.time() - start_time) * 1000
                await self._record_success(response_time)
                return result
                
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                failure_type = self._classify_failure(e)
                await self._record_failure(failure_type, str(e), response_time)
                raise
    
    @asynccontextmanager
    async def _request_context(self):
        """Context manager for request tracking"""
        request_start = datetime.now()
        try:
            yield
        finally:
            # Update request history regardless of outcome
            self.request_history.append(request_start)
    
    async def _can_execute(self) -> bool:
        """Check if request can be executed based on current circuit state"""
        with self.lock:
            current_time = datetime.now()
            
            if self.state == CircuitState.CLOSED:
                return True
            
            elif self.state == CircuitState.OPEN:
                # Check if enough time has passed to attempt recovery
                time_since_open = (current_time - self.state_changed_time).total_seconds()
                if time_since_open >= self.current_recovery_timeout:
                    await self._transition_to_half_open()
                    return True
                return False
            
            elif self.state == CircuitState.HALF_OPEN:
                # Check if we've been in half-open too long
                time_in_half_open = (current_time - self.state_changed_time).total_seconds()
                if time_in_half_open > self.config.max_half_open_duration:
                    await self._transition_to_open("Half-open timeout exceeded")
                    return False
                
                # Check if we've reached max attempts in half-open
                if self.half_open_attempts >= self.config.half_open_max_calls:
                    if self.half_open_successes >= self.config.success_threshold:
                        await self._transition_to_closed("Recovery successful")
                    else:
                        await self._transition_to_open("Half-open recovery failed")
                    return False
                
                return True
            
            return False
    
    def _classify_failure(self, exception: Exception) -> FailureType:
        """Classify the type of failure based on exception"""
        exception_str = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        
        if "timeout" in exception_str or "timeout" in exception_type:
            return FailureType.TIMEOUT
        elif "rate" in exception_str and "limit" in exception_str:
            return FailureType.RATE_LIMIT
        elif "auth" in exception_str or "401" in exception_str or "403" in exception_str:
            return FailureType.AUTHENTICATION
        elif "captcha" in exception_str:
            return FailureType.CAPTCHA
        elif "network" in exception_str or "connection" in exception_str:
            return FailureType.NETWORK_ERROR
        elif "parse" in exception_str or "json" in exception_str or "xml" in exception_str:
            return FailureType.PARSING_ERROR
        elif "http" in exception_str or any(code in exception_str for code in ["400", "500", "502", "503"]):
            return FailureType.HTTP_ERROR
        else:
            return FailureType.UNKNOWN
    
    async def _record_success(self, response_time_ms: float):
        """Record a successful request"""
        with self.lock:
            current_time = datetime.now()
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            self.metrics.last_success_time = current_time
            
            # Update average response time
            total_responses = self.metrics.successful_requests + self.metrics.failed_requests
            if total_responses > 0:
                self.metrics.average_response_time = (
                    (self.metrics.average_response_time * (total_responses - 1) + response_time_ms) / total_responses
                )
            
            # Update failure rate
            self._update_failure_rate()
            
            # Handle state-specific logic
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                
                # Check if we should transition to closed
                if self.half_open_successes >= self.config.success_threshold:
                    await self._transition_to_closed("Sufficient successes in half-open state")
    
    async def _record_failure(self, failure_type: FailureType, error_message: str, response_time_ms: float):
        """Record a failed request"""
        with self.lock:
            current_time = datetime.now()
            
            # Only count failures of enabled types
            if failure_type not in self.config.enabled_failure_types and self.config.enabled_failure_types:
                return
            
            # Create failure record
            failure_record = FailureRecord(
                timestamp=current_time,
                failure_type=failure_type,
                error_message=error_message,
                response_time_ms=response_time_ms
            )
            self.failure_history.append(failure_record)
            
            # Update metrics
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = current_time
            
            # Update failure rate
            self._update_failure_rate()
            
            # Check if we should open the circuit
            if self.state == CircuitState.CLOSED:
                if self._should_open_circuit():
                    await self._transition_to_open(f"Failure threshold exceeded: {failure_type.value}")
            
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state transitions back to open
                await self._transition_to_open(f"Failure in half-open state: {failure_type.value}")
    
    def _update_failure_rate(self):
        """Update the current failure rate"""
        if self.metrics.total_requests > 0:
            self.metrics.failure_rate = self.metrics.failed_requests / self.metrics.total_requests
    
    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened based on current metrics"""
        # Check consecutive failures threshold
        if self.metrics.consecutive_failures >= self.config.failure_threshold:
            return True
        
        # Check failure rate threshold (only if we have enough requests)
        if (self.metrics.total_requests >= self.config.min_requests_for_rate and
            self.metrics.failure_rate >= self.config.failure_rate_threshold):
            return True
        
        return False
    
    async def _transition_to_open(self, reason: str):
        """Transition circuit to open state"""
        if self.state != CircuitState.OPEN:
            old_state = self.state
            self.state = CircuitState.OPEN
            self.state_changed_time = datetime.now()
            self.metrics.state_changes += 1
            
            # Reset half-open state
            self.half_open_attempts = 0
            self.half_open_successes = 0
            self.half_open_start_time = None
            
            # Calculate next recovery timeout based on strategy
            self._calculate_recovery_timeout()
            
            self.logger.warning(
                f"Circuit breaker '{self.name}' opened: {reason} "
                f"(was {old_state.value}, recovery in {self.current_recovery_timeout}s)"
            )
    
    async def _transition_to_half_open(self):
        """Transition circuit to half-open state"""
        if self.state != CircuitState.HALF_OPEN:
            old_state = self.state
            self.state = CircuitState.HALF_OPEN
            self.state_changed_time = datetime.now()
            self.half_open_start_time = datetime.now()
            self.metrics.state_changes += 1
            
            # Reset half-open counters
            self.half_open_attempts = 0
            self.half_open_successes = 0
            
            self.logger.info(
                f"Circuit breaker '{self.name}' half-opened "
                f"(was {old_state.value}, attempting recovery)"
            )
    
    async def _transition_to_closed(self, reason: str):
        """Transition circuit to closed state"""
        if self.state != CircuitState.CLOSED:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.state_changed_time = datetime.now()
            self.metrics.state_changes += 1
            
            # Reset recovery state
            self.recovery_attempts = 0
            self.current_recovery_timeout = self.config.recovery_timeout
            
            # Reset half-open state
            self.half_open_attempts = 0
            self.half_open_successes = 0
            self.half_open_start_time = None
            
            self.logger.info(
                f"Circuit breaker '{self.name}' closed: {reason} "
                f"(was {old_state.value})"
            )
    
    def _calculate_recovery_timeout(self):
        """Calculate recovery timeout based on strategy"""
        if self.config.recovery_strategy == RecoveryStrategy.IMMEDIATE:
            self.current_recovery_timeout = self.config.recovery_timeout
        
        elif self.config.recovery_strategy == RecoveryStrategy.EXPONENTIAL:
            self.current_recovery_timeout = min(
                self.config.recovery_timeout * (self.config.exponential_base ** self.recovery_attempts),
                self.config.max_recovery_timeout
            )
            self.recovery_attempts += 1
        
        elif self.config.recovery_strategy == RecoveryStrategy.ADAPTIVE:
            # Adaptive timeout based on failure rate and recent performance
            base_timeout = self.config.recovery_timeout
            failure_factor = 1 + (self.metrics.failure_rate * 2)  # More failures = longer timeout
            response_factor = 1 + (self.metrics.average_response_time / 1000)  # Slower responses = longer timeout
            
            self.current_recovery_timeout = min(
                base_timeout * failure_factor * response_factor,
                self.config.max_recovery_timeout
            )
        
        else:  # GRADUAL or default
            self.current_recovery_timeout = self.config.recovery_timeout
    
    def _time_until_next_attempt(self) -> float:
        """Calculate time until next attempt is allowed"""
        if self.state != CircuitState.OPEN:
            return 0.0
        
        time_since_open = (datetime.now() - self.state_changed_time).total_seconds()
        return max(0.0, self.current_recovery_timeout - time_since_open)
    
    async def health_check(self) -> bool:
        """Perform health check if callback is configured"""
        if not self.health_check_callback:
            return True
        
        try:
            self.last_health_check = datetime.now()
            if asyncio.iscoroutinefunction(self.health_check_callback):
                return await self.health_check_callback()
            else:
                return self.health_check_callback()
        except Exception as e:
            self.logger.error(f"Health check failed for '{self.name}': {e}")
            return False
    
    def set_health_check_callback(self, callback: Callable):
        """Set health check callback function"""
        self.health_check_callback = callback
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        current_time = datetime.now()
        
        return {
            "name": self.name,
            "state": self.state.value,
            "state_changed_time": self.state_changed_time.isoformat(),
            "time_in_current_state": (current_time - self.state_changed_time).total_seconds(),
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "consecutive_failures": self.metrics.consecutive_failures,
                "consecutive_successes": self.metrics.consecutive_successes,
                "failure_rate": round(self.metrics.failure_rate, 4),
                "average_response_time_ms": round(self.metrics.average_response_time, 2),
                "state_changes": self.metrics.state_changes
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "current_recovery_timeout": self.current_recovery_timeout,
                "recovery_strategy": self.config.recovery_strategy.value,
                "failure_rate_threshold": self.config.failure_rate_threshold
            },
            "half_open_state": {
                "attempts": self.half_open_attempts,
                "successes": self.half_open_successes,
                "max_calls": self.config.half_open_max_calls,
                "success_threshold": self.config.success_threshold
            } if self.state == CircuitState.HALF_OPEN else None,
            "time_until_next_attempt": self._time_until_next_attempt(),
            "recent_failures": [
                {
                    "timestamp": f.timestamp.isoformat(),
                    "type": f.failure_type.value,
                    "message": f.error_message[:100],  # Truncate long messages
                    "response_time_ms": f.response_time_ms
                }
                for f in list(self.failure_history)[-5:]  # Last 5 failures
            ],
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
        }
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.state_changed_time = datetime.now()
            self.metrics = CircuitMetrics()
            self.failure_history.clear()
            self.request_history.clear()
            self.half_open_attempts = 0
            self.half_open_successes = 0
            self.half_open_start_time = None
            self.recovery_attempts = 0
            self.current_recovery_timeout = self.config.recovery_timeout
            
            self.logger.info(f"Circuit breaker '{self.name}' reset")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, EnhancedCircuitBreaker] = {}
        self.logger = logging.getLogger(__name__)
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> EnhancedCircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = EnhancedCircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    async def call_with_circuit_breaker(self, name: str, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(name)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        return {
            name: cb.get_status() 
            for name, cb in self.circuit_breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for cb in self.circuit_breakers.values():
            cb.reset()
        self.logger.info("All circuit breakers reset")


# Global instance
circuit_breaker_manager = CircuitBreakerManager()

# Convenience functions
def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> EnhancedCircuitBreaker:
    """Get circuit breaker instance"""
    return circuit_breaker_manager.get_circuit_breaker(name, config)

async def call_with_circuit_breaker(name: str, func: Callable, *args, **kwargs) -> Any:
    """Execute function with circuit breaker protection"""
    return await circuit_breaker_manager.call_with_circuit_breaker(name, func, *args, **kwargs)

def get_all_circuit_breaker_status() -> Dict[str, Any]:
    """Get status of all circuit breakers"""
    return circuit_breaker_manager.get_all_status() 