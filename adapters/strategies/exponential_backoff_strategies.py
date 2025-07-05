"""
Comprehensive Exponential Backoff Strategies for FlightIO Crawler
Features: Multiple backoff algorithms, jitter, circuit breaker integration, adaptive timing
"""

import asyncio
import random
import time
import math
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import logging
from contextlib import asynccontextmanager
import statistics
from collections import deque, defaultdict
import psutil
import gc

try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class BackoffStrategy(Enum):
    """Available backoff strategies"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    FIBONACCI = "fibonacci"
    ADAPTIVE = "adaptive"
    CIRCUIT_BREAKER = "circuit_breaker"
    JITTERED_EXPONENTIAL = "jittered_exponential"
    INTELLIGENT = "intelligent"


class JitterType(Enum):
    """Jitter types to prevent thundering herd"""
    FULL = "full"
    EQUAL = "equal"
    DECORRELATED = "decorrelated"
    NONE = "none"


@dataclass
class BackoffConfig:
    """Configuration for backoff strategies"""
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 300.0
    multiplier: float = 2.0
    max_retries: int = 5
    jitter_type: JitterType = JitterType.FULL
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    adaptive_factors: Dict[str, float] = field(default_factory=lambda: {
        'system_load_factor': 0.3,
        'error_rate_factor': 0.4,
        'response_time_factor': 0.3
    })
    intelligent_learning_rate: float = 0.1


@dataclass
class BackoffAttempt:
    """Information about a backoff attempt"""
    attempt_number: int
    delay: float
    strategy_used: BackoffStrategy
    jitter_applied: float
    timestamp: datetime
    system_load: float
    error_rate: float
    response_time: float
    circuit_breaker_state: str
    success: bool = False
    error_type: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class BackoffMetrics:
    """Metrics for backoff performance"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    average_delay: float = 0.0
    max_delay_used: float = 0.0
    circuit_breaker_trips: int = 0
    jitter_effectiveness: float = 0.0
    adaptive_improvements: float = 0.0
    strategy_performance: Dict[BackoffStrategy, float] = field(default_factory=dict)
    last_reset: datetime = field(default_factory=datetime.now)


class BackoffStrategyInterface(ABC):
    """Interface for backoff strategies"""
    
    @abstractmethod
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate delay for given attempt"""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get strategy name"""
        pass


class ExponentialBackoffStrategy(BackoffStrategyInterface):
    """Exponential backoff strategy"""
    
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate exponential backoff delay"""
        delay = config.base_delay * (config.multiplier ** attempt)
        return min(delay, config.max_delay)
    
    def get_strategy_name(self) -> str:
        return "exponential"


class LinearBackoffStrategy(BackoffStrategyInterface):
    """Linear backoff strategy"""
    
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate linear backoff delay"""
        delay = config.base_delay + (config.multiplier * attempt)
        return min(delay, config.max_delay)
    
    def get_strategy_name(self) -> str:
        return "linear"


class FibonacciBackoffStrategy(BackoffStrategyInterface):
    """Fibonacci backoff strategy"""
    
    def __init__(self):
        self.fib_cache = {0: 0, 1: 1}
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number with caching"""
        if n not in self.fib_cache:
            self.fib_cache[n] = self._fibonacci(n-1) + self._fibonacci(n-2)
        return self.fib_cache[n]
    
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate fibonacci backoff delay"""
        fib_multiplier = self._fibonacci(attempt + 1)
        delay = config.base_delay * fib_multiplier
        return min(delay, config.max_delay)
    
    def get_strategy_name(self) -> str:
        return "fibonacci"


class AdaptiveBackoffStrategy(BackoffStrategyInterface):
    """Adaptive backoff strategy based on system conditions"""
    
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate adaptive backoff delay"""
        base_delay = config.base_delay * (config.multiplier ** attempt)
        
        # Adapt based on system load
        system_load = context.get('system_load', 0.5)
        error_rate = context.get('error_rate', 0.1)
        response_time = context.get('response_time', 1.0)
        
        # Apply adaptive factors
        load_factor = 1.0 + (system_load * config.adaptive_factors.get('system_load_factor', 0.3))
        error_factor = 1.0 + (error_rate * config.adaptive_factors.get('error_rate_factor', 0.4))
        response_factor = 1.0 + (response_time * config.adaptive_factors.get('response_time_factor', 0.3))
        
        adaptive_delay = base_delay * load_factor * error_factor * response_factor
        return min(adaptive_delay, config.max_delay)
    
    def get_strategy_name(self) -> str:
        return "adaptive"


class IntelligentBackoffStrategy(BackoffStrategyInterface):
    """Intelligent backoff strategy using machine learning principles"""
    
    def __init__(self):
        self.success_history = deque(maxlen=100)
        self.delay_effectiveness = defaultdict(float)
        self.strategy_performance = defaultdict(list)
    
    async def calculate_delay(
        self, 
        attempt: int, 
        config: BackoffConfig,
        context: Dict[str, Any]
    ) -> float:
        """Calculate intelligent backoff delay using historical data"""
        # Base exponential delay
        base_delay = config.base_delay * (config.multiplier ** attempt)
        
        # Learn from historical performance
        if len(self.success_history) > 10:
            recent_success_rate = sum(self.success_history) / len(self.success_history)
            
            # Adjust based on recent success rate
            if recent_success_rate > 0.8:
                # High success rate - be more aggressive
                intelligent_factor = 0.7
            elif recent_success_rate > 0.5:
                # Medium success rate - normal backoff
                intelligent_factor = 1.0
            else:
                # Low success rate - be more conservative
                intelligent_factor = 1.5
        else:
            intelligent_factor = 1.0
        
        # Apply learning rate
        learning_adjustment = config.intelligent_learning_rate * intelligent_factor
        intelligent_delay = base_delay * (1.0 + learning_adjustment)
        
        return min(intelligent_delay, config.max_delay)
    
    def record_attempt(self, success: bool, delay: float):
        """Record attempt outcome for learning"""
        self.success_history.append(success)
        self.delay_effectiveness[delay] = success
    
    def get_strategy_name(self) -> str:
        return "intelligent"


class JitterCalculator:
    """Jitter calculation utilities"""
    
    @staticmethod
    def apply_jitter(delay: float, jitter_type: JitterType) -> Tuple[float, float]:
        """Apply jitter to delay and return (jittered_delay, jitter_amount)"""
        if jitter_type == JitterType.NONE:
            return delay, 0.0
        
        if jitter_type == JitterType.FULL:
            jitter_amount = random.uniform(0, delay)
            return jitter_amount, delay - jitter_amount
        
        elif jitter_type == JitterType.EQUAL:
            jitter_amount = delay / 2 + random.uniform(0, delay / 2)
            return jitter_amount, delay - jitter_amount
        
        elif jitter_type == JitterType.DECORRELATED:
            # Decorrelated jitter helps prevent synchronized retries
            prev_delay = delay
            jitter_amount = random.uniform(0, prev_delay * 3)
            return jitter_amount, abs(jitter_amount - delay)
        
        return delay, 0.0


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics"""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    success_count: int = 0
    test_request_count: int = 0


class CircuitBreakerManager:
    """Circuit breaker management for backoff strategies"""
    
    def __init__(self, config: BackoffConfig):
        self.config = config
        self.metrics = CircuitBreakerMetrics()
        self.logger = logging.getLogger(__name__)
    
    async def should_allow_request(self) -> bool:
        """Check if request should be allowed based on circuit breaker state"""
        if self.metrics.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.metrics.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.metrics.state = CircuitBreakerState.HALF_OPEN
                self.metrics.test_request_count = 0
                return True
            return False
        
        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            return self.metrics.test_request_count < 3
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.metrics.last_failure_time:
            return False
        
        time_since_failure = datetime.now() - self.metrics.last_failure_time
        return time_since_failure.total_seconds() > self.config.circuit_breaker_timeout
    
    async def record_success(self):
        """Record successful request"""
        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            self.metrics.success_count += 1
            if self.metrics.success_count >= 3:
                self.metrics.state = CircuitBreakerState.CLOSED
                self.metrics.failure_count = 0
                self.logger.info("Circuit breaker reset to CLOSED state")
        
        self.metrics.success_count += 1
    
    async def record_failure(self):
        """Record failed request"""
        self.metrics.failure_count += 1
        self.metrics.last_failure_time = datetime.now()
        
        if self.metrics.state == CircuitBreakerState.HALF_OPEN:
            self.metrics.state = CircuitBreakerState.OPEN
            self.logger.warning("Circuit breaker opened from HALF_OPEN state")
        
        elif (self.metrics.state == CircuitBreakerState.CLOSED and 
              self.metrics.failure_count >= self.config.circuit_breaker_threshold):
            self.metrics.state = CircuitBreakerState.OPEN
            self.logger.warning(f"Circuit breaker opened after {self.metrics.failure_count} failures")
    
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state"""
        return self.metrics.state


class SystemMonitor:
    """System monitoring for adaptive backoff"""
    
    def __init__(self):
        self.response_times = deque(maxlen=100)
        self.error_counts = deque(maxlen=100)
        self.last_system_check = datetime.now()
    
    async def get_system_load(self) -> float:
        """Get current system load (0.0 to 1.0)"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Average load
            system_load = (cpu_percent + memory_percent) / 200.0
            return min(system_load, 1.0)
        except:
            return 0.5  # Default moderate load
    
    async def get_error_rate(self) -> float:
        """Get current error rate (0.0 to 1.0)"""
        if len(self.error_counts) == 0:
            return 0.0
        
        recent_errors = sum(self.error_counts[-20:])  # Last 20 attempts
        return min(recent_errors / 20.0, 1.0)
    
    async def get_average_response_time(self) -> float:
        """Get average response time (normalized to 0.0-1.0)"""
        if len(self.response_times) == 0:
            return 0.5
        
        avg_time = statistics.mean(self.response_times)
        # Normalize to 0-1 range (assuming 10 seconds is very slow)
        return min(avg_time / 10.0, 1.0)
    
    def record_response_time(self, response_time: float):
        """Record response time"""
        self.response_times.append(response_time)
    
    def record_error(self, has_error: bool):
        """Record error occurrence"""
        self.error_counts.append(1 if has_error else 0)


class ComprehensiveBackoffManager:
    """Comprehensive backoff management system"""
    
    def __init__(self, config: BackoffConfig, redis_client: Optional[Any] = None):
        self.config = config
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Initialize strategies
        self.strategies = {
            BackoffStrategy.EXPONENTIAL: ExponentialBackoffStrategy(),
            BackoffStrategy.LINEAR: LinearBackoffStrategy(),
            BackoffStrategy.FIBONACCI: FibonacciBackoffStrategy(),
            BackoffStrategy.ADAPTIVE: AdaptiveBackoffStrategy(),
            BackoffStrategy.INTELLIGENT: IntelligentBackoffStrategy(),
        }
        
        # Initialize components
        self.circuit_breaker = CircuitBreakerManager(config)
        self.system_monitor = SystemMonitor()
        self.jitter_calculator = JitterCalculator()
        
        # Metrics
        self.metrics = BackoffMetrics()
        self.attempt_history = deque(maxlen=1000)
        
        # Performance tracking
        self.strategy_performance = defaultdict(list)
        
    async def execute_with_backoff(
        self,
        operation: Callable,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with comprehensive backoff strategy"""
        context = context or {}
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            # Check circuit breaker
            if not await self.circuit_breaker.should_allow_request():
                self.logger.warning(f"Circuit breaker open for {operation_name}, skipping attempt")
                raise Exception("Circuit breaker open")
            
            try:
                start_time = time.time()
                
                # Execute operation
                result = await operation(*args, **kwargs)
                
                # Record success
                execution_time = time.time() - start_time
                await self._record_success(attempt, execution_time, operation_name)
                
                return result
                
            except Exception as e:
                last_exception = e
                execution_time = time.time() - start_time
                
                # Record failure
                await self._record_failure(attempt, execution_time, operation_name, e)
                
                # Don't retry on last attempt
                if attempt >= self.config.max_retries:
                    break
                
                # Calculate and apply backoff
                delay = await self._calculate_backoff_delay(attempt, context)
                
                self.logger.info(
                    f"Attempt {attempt + 1} failed for {operation_name}, "
                    f"retrying in {delay:.2f}s: {str(e)}"
                )
                
                await asyncio.sleep(delay)
        
        # All attempts failed
        self.logger.error(f"All {self.config.max_retries + 1} attempts failed for {operation_name}")
        raise last_exception
    
    async def _calculate_backoff_delay(
        self, 
        attempt: int, 
        context: Dict[str, Any]
    ) -> float:
        """Calculate backoff delay using configured strategy"""
        # Get system context
        system_context = await self._get_system_context()
        context.update(system_context)
        
        # Get strategy
        strategy = self.strategies.get(self.config.strategy)
        if not strategy:
            strategy = self.strategies[BackoffStrategy.EXPONENTIAL]
        
        # Calculate base delay
        base_delay = await strategy.calculate_delay(attempt, self.config, context)
        
        # Apply jitter
        jittered_delay, jitter_amount = self.jitter_calculator.apply_jitter(
            base_delay, self.config.jitter_type
        )
        
        # Record attempt
        attempt_info = BackoffAttempt(
            attempt_number=attempt,
            delay=jittered_delay,
            strategy_used=self.config.strategy,
            jitter_applied=jitter_amount,
            timestamp=datetime.now(),
            system_load=context.get('system_load', 0.0),
            error_rate=context.get('error_rate', 0.0),
            response_time=context.get('response_time', 0.0),
            circuit_breaker_state=self.circuit_breaker.get_state().value
        )
        
        self.attempt_history.append(attempt_info)
        
        return jittered_delay
    
    async def _get_system_context(self) -> Dict[str, Any]:
        """Get current system context for adaptive strategies"""
        return {
            'system_load': await self.system_monitor.get_system_load(),
            'error_rate': await self.system_monitor.get_error_rate(),
            'response_time': await self.system_monitor.get_average_response_time(),
            'circuit_breaker_state': self.circuit_breaker.get_state().value
        }
    
    async def _record_success(
        self, 
        attempt: int, 
        execution_time: float, 
        operation_name: str
    ):
        """Record successful operation"""
        await self.circuit_breaker.record_success()
        self.system_monitor.record_response_time(execution_time)
        self.system_monitor.record_error(False)
        
        # Update metrics
        self.metrics.total_attempts += 1
        self.metrics.successful_attempts += 1
        
        # Record for intelligent strategy
        if isinstance(self.strategies.get(self.config.strategy), IntelligentBackoffStrategy):
            self.strategies[self.config.strategy].record_attempt(True, execution_time)
        
        # Update attempt history
        if self.attempt_history:
            self.attempt_history[-1].success = True
            self.attempt_history[-1].execution_time = execution_time
    
    async def _record_failure(
        self, 
        attempt: int, 
        execution_time: float, 
        operation_name: str, 
        exception: Exception
    ):
        """Record failed operation"""
        await self.circuit_breaker.record_failure()
        self.system_monitor.record_response_time(execution_time)
        self.system_monitor.record_error(True)
        
        # Update metrics
        self.metrics.total_attempts += 1
        self.metrics.failed_attempts += 1
        
        # Record for intelligent strategy
        if isinstance(self.strategies.get(self.config.strategy), IntelligentBackoffStrategy):
            self.strategies[self.config.strategy].record_attempt(False, execution_time)
        
        # Update attempt history
        if self.attempt_history:
            self.attempt_history[-1].success = False
            self.attempt_history[-1].execution_time = execution_time
            self.attempt_history[-1].error_type = type(exception).__name__
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive backoff metrics"""
        # Calculate derived metrics
        total_attempts = self.metrics.total_attempts
        if total_attempts > 0:
            success_rate = self.metrics.successful_attempts / total_attempts
            
            # Calculate average delay
            delays = [attempt.delay for attempt in self.attempt_history]
            avg_delay = statistics.mean(delays) if delays else 0.0
            
            # Calculate jitter effectiveness
            jitter_amounts = [attempt.jitter_applied for attempt in self.attempt_history]
            jitter_effectiveness = statistics.mean(jitter_amounts) if jitter_amounts else 0.0
        else:
            success_rate = 0.0
            avg_delay = 0.0
            jitter_effectiveness = 0.0
        
        return {
            'total_attempts': total_attempts,
            'successful_attempts': self.metrics.successful_attempts,
            'failed_attempts': self.metrics.failed_attempts,
            'success_rate': success_rate,
            'average_delay': avg_delay,
            'max_delay_used': self.metrics.max_delay_used,
            'circuit_breaker_trips': self.metrics.circuit_breaker_trips,
            'jitter_effectiveness': jitter_effectiveness,
            'current_strategy': self.config.strategy.value,
            'circuit_breaker_state': self.circuit_breaker.get_state().value,
            'system_load': await self.system_monitor.get_system_load(),
            'error_rate': await self.system_monitor.get_error_rate(),
            'response_time': await self.system_monitor.get_average_response_time(),
            'recent_attempts': len(self.attempt_history),
            'last_reset': self.metrics.last_reset.isoformat()
        }
    
    async def reset_metrics(self):
        """Reset metrics and history"""
        self.metrics = BackoffMetrics()
        self.attempt_history.clear()
        self.system_monitor.response_times.clear()
        self.system_monitor.error_counts.clear()
        self.logger.info("Backoff metrics reset")
    
    async def optimize_strategy(self) -> BackoffStrategy:
        """Analyze performance and recommend optimal strategy"""
        if len(self.attempt_history) < 20:
            return self.config.strategy
        
        # Analyze recent performance
        recent_attempts = list(self.attempt_history)[-50:]
        
        # Calculate success rates by strategy
        strategy_success = defaultdict(list)
        for attempt in recent_attempts:
            strategy_success[attempt.strategy_used].append(attempt.success)
        
        # Find best performing strategy
        best_strategy = self.config.strategy
        best_success_rate = 0.0
        
        for strategy, successes in strategy_success.items():
            if len(successes) >= 5:  # Minimum sample size
                success_rate = sum(successes) / len(successes)
                if success_rate > best_success_rate:
                    best_success_rate = success_rate
                    best_strategy = strategy
        
        return best_strategy
    
    @asynccontextmanager
    async def backoff_context(self, operation_name: str):
        """Context manager for backoff operations"""
        start_time = time.time()
        try:
            yield self
        finally:
            execution_time = time.time() - start_time
            self.logger.debug(f"Backoff context for {operation_name} completed in {execution_time:.2f}s")


# Convenience functions for easy integration
async def execute_with_exponential_backoff(
    operation: Callable,
    operation_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    *args,
    **kwargs
) -> Any:
    """Execute operation with exponential backoff"""
    config = BackoffConfig(
        strategy=BackoffStrategy.EXPONENTIAL,
        base_delay=base_delay,
        max_delay=max_delay,
        max_retries=max_retries,
        jitter_type=JitterType.FULL if jitter else JitterType.NONE
    )
    
    manager = ComprehensiveBackoffManager(config)
    return await manager.execute_with_backoff(operation, operation_name, *args, **kwargs)


async def execute_with_adaptive_backoff(
    operation: Callable,
    operation_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    *args,
    **kwargs
) -> Any:
    """Execute operation with adaptive backoff"""
    config = BackoffConfig(
        strategy=BackoffStrategy.ADAPTIVE,
        base_delay=base_delay,
        max_delay=max_delay,
        max_retries=max_retries,
        jitter_type=JitterType.FULL
    )
    
    manager = ComprehensiveBackoffManager(config)
    return await manager.execute_with_backoff(operation, operation_name, *args, **kwargs)


async def execute_with_intelligent_backoff(
    operation: Callable,
    operation_name: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    *args,
    **kwargs
) -> Any:
    """Execute operation with intelligent backoff"""
    config = BackoffConfig(
        strategy=BackoffStrategy.INTELLIGENT,
        base_delay=base_delay,
        max_delay=max_delay,
        max_retries=max_retries,
        jitter_type=JitterType.DECORRELATED
    )
    
    manager = ComprehensiveBackoffManager(config)
    return await manager.execute_with_backoff(operation, operation_name, *args, **kwargs)


# Decorator for easy integration
def backoff_retry(
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
):
    """Decorator for automatic backoff retry"""
    def decorator(func):
        @asyncio.coroutine
        def wrapper(*args, **kwargs):
            config = BackoffConfig(
                strategy=strategy,
                base_delay=base_delay,
                max_delay=max_delay,
                max_retries=max_retries,
                jitter_type=JitterType.FULL if jitter else JitterType.NONE
            )
            
            manager = ComprehensiveBackoffManager(config)
            return manager.execute_with_backoff(func, func.__name__, *args, **kwargs)
        
        return wrapper
    return decorator 