"""
Tests for Comprehensive Exponential Backoff Strategies
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from adapters.strategies.exponential_backoff_strategies import (
    BackoffStrategy,
    JitterType,
    BackoffConfig,
    BackoffAttempt,
    BackoffMetrics,
    ExponentialBackoffStrategy,
    LinearBackoffStrategy,
    FibonacciBackoffStrategy,
    AdaptiveBackoffStrategy,
    IntelligentBackoffStrategy,
    JitterCalculator,
    CircuitBreakerState,
    CircuitBreakerManager,
    SystemMonitor,
    ComprehensiveBackoffManager,
    execute_with_exponential_backoff,
    execute_with_adaptive_backoff,
    execute_with_intelligent_backoff,
    backoff_retry
)


class TestBackoffStrategies:
    """Test individual backoff strategies"""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_strategy(self):
        """Test exponential backoff calculation"""
        strategy = ExponentialBackoffStrategy()
        config = BackoffConfig(base_delay=1.0, multiplier=2.0, max_delay=60.0)
        
        # Test exponential growth
        delay_0 = await strategy.calculate_delay(0, config, {})
        delay_1 = await strategy.calculate_delay(1, config, {})
        delay_2 = await strategy.calculate_delay(2, config, {})
        
        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0
        
        # Test max delay cap
        delay_high = await strategy.calculate_delay(10, config, {})
        assert delay_high == 60.0
    
    @pytest.mark.asyncio
    async def test_linear_backoff_strategy(self):
        """Test linear backoff calculation"""
        strategy = LinearBackoffStrategy()
        config = BackoffConfig(base_delay=1.0, multiplier=2.0, max_delay=60.0)
        
        # Test linear growth
        delay_0 = await strategy.calculate_delay(0, config, {})
        delay_1 = await strategy.calculate_delay(1, config, {})
        delay_2 = await strategy.calculate_delay(2, config, {})
        
        assert delay_0 == 1.0
        assert delay_1 == 3.0  # 1 + 2*1
        assert delay_2 == 5.0  # 1 + 2*2
    
    @pytest.mark.asyncio
    async def test_fibonacci_backoff_strategy(self):
        """Test fibonacci backoff calculation"""
        strategy = FibonacciBackoffStrategy()
        config = BackoffConfig(base_delay=1.0, max_delay=60.0)
        
        # Test fibonacci sequence
        delay_0 = await strategy.calculate_delay(0, config, {})
        delay_1 = await strategy.calculate_delay(1, config, {})
        delay_2 = await strategy.calculate_delay(2, config, {})
        delay_3 = await strategy.calculate_delay(3, config, {})
        
        assert delay_0 == 1.0  # base_delay * fib(1) = 1 * 1
        assert delay_1 == 1.0  # base_delay * fib(2) = 1 * 1
        assert delay_2 == 2.0  # base_delay * fib(3) = 1 * 2
        assert delay_3 == 3.0  # base_delay * fib(4) = 1 * 3
    
    @pytest.mark.asyncio
    async def test_adaptive_backoff_strategy(self):
        """Test adaptive backoff calculation"""
        strategy = AdaptiveBackoffStrategy()
        config = BackoffConfig(base_delay=1.0, multiplier=2.0, max_delay=60.0)
        
        # Test normal conditions
        normal_context = {
            'system_load': 0.3,
            'error_rate': 0.1,
            'response_time': 0.5
        }
        delay_normal = await strategy.calculate_delay(1, config, normal_context)
        
        # Test high load conditions
        high_load_context = {
            'system_load': 0.8,
            'error_rate': 0.5,
            'response_time': 2.0
        }
        delay_high_load = await strategy.calculate_delay(1, config, high_load_context)
        
        # High load should result in longer delay
        assert delay_high_load > delay_normal
    
    @pytest.mark.asyncio
    async def test_intelligent_backoff_strategy(self):
        """Test intelligent backoff strategy"""
        strategy = IntelligentBackoffStrategy()
        config = BackoffConfig(base_delay=1.0, multiplier=2.0, max_delay=60.0)
        
        # Test with no history
        delay_initial = await strategy.calculate_delay(1, config, {})
        
        # Record some successful attempts
        for _ in range(10):
            strategy.record_attempt(True, 1.0)
        
        # Test with high success rate
        delay_high_success = await strategy.calculate_delay(1, config, {})
        
        # Record some failures
        for _ in range(10):
            strategy.record_attempt(False, 1.0)
        
        # Test with low success rate
        delay_low_success = await strategy.calculate_delay(1, config, {})
        
        # Low success rate should result in longer delay
        assert delay_low_success > delay_high_success


class TestJitterCalculator:
    """Test jitter calculation"""
    
    def test_no_jitter(self):
        """Test no jitter application"""
        delay = 5.0
        jittered_delay, jitter_amount = JitterCalculator.apply_jitter(delay, JitterType.NONE)
        
        assert jittered_delay == delay
        assert jitter_amount == 0.0
    
    def test_full_jitter(self):
        """Test full jitter application"""
        delay = 5.0
        jittered_delay, jitter_amount = JitterCalculator.apply_jitter(delay, JitterType.FULL)
        
        assert 0 <= jittered_delay <= delay
        assert jitter_amount >= 0
    
    def test_equal_jitter(self):
        """Test equal jitter application"""
        delay = 5.0
        jittered_delay, jitter_amount = JitterCalculator.apply_jitter(delay, JitterType.EQUAL)
        
        assert delay / 2 <= jittered_delay <= delay
        assert jitter_amount >= 0
    
    def test_decorrelated_jitter(self):
        """Test decorrelated jitter application"""
        delay = 5.0
        jittered_delay, jitter_amount = JitterCalculator.apply_jitter(delay, JitterType.DECORRELATED)
        
        assert jittered_delay >= 0
        assert jitter_amount >= 0


class TestCircuitBreakerManager:
    """Test circuit breaker functionality"""
    
    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions"""
        config = BackoffConfig(circuit_breaker_threshold=3)
        cb = CircuitBreakerManager(config)
        
        # Initially closed
        assert cb.get_state() == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opening(self):
        """Test circuit breaker opening on failures"""
        config = BackoffConfig(circuit_breaker_threshold=3)
        cb = CircuitBreakerManager(config)
        
        # Record failures
        for _ in range(3):
            await cb.record_failure()
            assert await cb.should_allow_request() is True
        
        # Should open after threshold
        await cb.record_failure()
        assert cb.get_state() == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery"""
        config = BackoffConfig(circuit_breaker_threshold=2, circuit_breaker_timeout=0.1)
        cb = CircuitBreakerManager(config)
        
        # Open circuit breaker
        await cb.record_failure()
        await cb.record_failure()
        assert cb.get_state() == CircuitBreakerState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should allow test request
        assert await cb.should_allow_request() is True
        assert cb.get_state() == CircuitBreakerState.HALF_OPEN
        
        # Record success to close
        await cb.record_success()
        await cb.record_success()
        await cb.record_success()
        assert cb.get_state() == CircuitBreakerState.CLOSED


class TestSystemMonitor:
    """Test system monitoring functionality"""
    
    @pytest.mark.asyncio
    async def test_system_load_calculation(self):
        """Test system load calculation"""
        monitor = SystemMonitor()
        
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 40.0
            
            load = await monitor.get_system_load()
            assert 0.0 <= load <= 1.0
    
    @pytest.mark.asyncio
    async def test_error_rate_calculation(self):
        """Test error rate calculation"""
        monitor = SystemMonitor()
        
        # Record some errors
        for _ in range(5):
            monitor.record_error(True)
        for _ in range(5):
            monitor.record_error(False)
        
        error_rate = await monitor.get_error_rate()
        assert 0.0 <= error_rate <= 1.0
    
    @pytest.mark.asyncio
    async def test_response_time_tracking(self):
        """Test response time tracking"""
        monitor = SystemMonitor()
        
        # Record some response times
        monitor.record_response_time(1.0)
        monitor.record_response_time(2.0)
        monitor.record_response_time(3.0)
        
        avg_time = await monitor.get_average_response_time()
        assert 0.0 <= avg_time <= 1.0


class TestComprehensiveBackoffManager:
    """Test comprehensive backoff manager"""
    
    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Test successful operation without retries"""
        config = BackoffConfig(max_retries=3)
        manager = ComprehensiveBackoffManager(config)
        
        async def successful_operation():
            return "success"
        
        result = await manager.execute_with_backoff(
            successful_operation, "test_operation"
        )
        
        assert result == "success"
        
        # Check metrics
        metrics = await manager.get_metrics()
        assert metrics['successful_attempts'] == 1
        assert metrics['failed_attempts'] == 0
    
    @pytest.mark.asyncio
    async def test_retries_with_eventual_success(self):
        """Test operation that succeeds after retries"""
        config = BackoffConfig(max_retries=3, base_delay=0.01)
        manager = ComprehensiveBackoffManager(config)
        
        call_count = 0
        
        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await manager.execute_with_backoff(
            eventually_successful_operation, "test_operation"
        )
        
        assert result == "success"
        assert call_count == 3
        
        # Check metrics
        metrics = await manager.get_metrics()
        assert metrics['successful_attempts'] == 1
        assert metrics['failed_attempts'] == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test operation that fails after max retries"""
        config = BackoffConfig(max_retries=2, base_delay=0.01)
        manager = ComprehensiveBackoffManager(config)
        
        async def always_failing_operation():
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await manager.execute_with_backoff(
                always_failing_operation, "test_operation"
            )
        
        # Check metrics
        metrics = await manager.get_metrics()
        assert metrics['successful_attempts'] == 0
        assert metrics['failed_attempts'] == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration"""
        config = BackoffConfig(
            max_retries=5,
            base_delay=0.01,
            circuit_breaker_threshold=2
        )
        manager = ComprehensiveBackoffManager(config)
        
        async def failing_operation():
            raise Exception("Circuit breaker test")
        
        # First operation should trigger circuit breaker
        with pytest.raises(Exception):
            await manager.execute_with_backoff(
                failing_operation, "test_operation"
            )
        
        # Circuit breaker should be open after threshold
        with pytest.raises(Exception, match="Circuit breaker open"):
            await manager.execute_with_backoff(
                failing_operation, "test_operation"
            )
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics collection"""
        config = BackoffConfig(max_retries=2, base_delay=0.01)
        manager = ComprehensiveBackoffManager(config)
        
        # Successful operation
        async def successful_operation():
            return "success"
        
        await manager.execute_with_backoff(
            successful_operation, "test_operation"
        )
        
        metrics = await manager.get_metrics()
        assert 'total_attempts' in metrics
        assert 'successful_attempts' in metrics
        assert 'failed_attempts' in metrics
        assert 'success_rate' in metrics
        assert 'average_delay' in metrics
        assert 'circuit_breaker_state' in metrics
        assert 'system_load' in metrics
        assert 'error_rate' in metrics
        assert 'response_time' in metrics
    
    @pytest.mark.asyncio
    async def test_strategy_optimization(self):
        """Test strategy optimization"""
        config = BackoffConfig(max_retries=1, base_delay=0.01)
        manager = ComprehensiveBackoffManager(config)
        
        # Execute some operations to build history
        async def test_operation():
            return "success"
        
        for _ in range(5):
            await manager.execute_with_backoff(
                test_operation, "test_operation"
            )
        
        # Test strategy optimization
        optimal_strategy = await manager.optimize_strategy()
        assert optimal_strategy in [strategy for strategy in BackoffStrategy]


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @pytest.mark.asyncio
    async def test_execute_with_exponential_backoff(self):
        """Test exponential backoff convenience function"""
        async def test_operation():
            return "exponential_success"
        
        result = await execute_with_exponential_backoff(
            test_operation, "test", max_retries=1, base_delay=0.01
        )
        
        assert result == "exponential_success"
    
    @pytest.mark.asyncio
    async def test_execute_with_adaptive_backoff(self):
        """Test adaptive backoff convenience function"""
        async def test_operation():
            return "adaptive_success"
        
        result = await execute_with_adaptive_backoff(
            test_operation, "test", max_retries=1, base_delay=0.01
        )
        
        assert result == "adaptive_success"
    
    @pytest.mark.asyncio
    async def test_execute_with_intelligent_backoff(self):
        """Test intelligent backoff convenience function"""
        async def test_operation():
            return "intelligent_success"
        
        result = await execute_with_intelligent_backoff(
            test_operation, "test", max_retries=1, base_delay=0.01
        )
        
        assert result == "intelligent_success"


class TestBackoffDecorator:
    """Test backoff decorator"""
    
    @pytest.mark.asyncio
    async def test_backoff_decorator_success(self):
        """Test backoff decorator with successful operation"""
        
        @backoff_retry(max_retries=2, base_delay=0.01)
        async def decorated_operation():
            return "decorated_success"
        
        result = await decorated_operation()
        assert result == "decorated_success"
    
    @pytest.mark.asyncio
    async def test_backoff_decorator_retries(self):
        """Test backoff decorator with retries"""
        call_count = 0
        
        @backoff_retry(max_retries=2, base_delay=0.01)
        async def decorated_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Decorator test failure")
            return "decorated_retry_success"
        
        result = await decorated_operation()
        assert result == "decorated_retry_success"
        assert call_count == 2


class TestBackoffConfig:
    """Test backoff configuration"""
    
    def test_default_config(self):
        """Test default backoff configuration"""
        config = BackoffConfig()
        
        assert config.strategy == BackoffStrategy.EXPONENTIAL
        assert config.base_delay == 1.0
        assert config.max_delay == 300.0
        assert config.multiplier == 2.0
        assert config.max_retries == 5
        assert config.jitter_type == JitterType.FULL
        assert config.enable_circuit_breaker is True
    
    def test_custom_config(self):
        """Test custom backoff configuration"""
        config = BackoffConfig(
            strategy=BackoffStrategy.LINEAR,
            base_delay=2.0,
            max_delay=60.0,
            multiplier=1.5,
            max_retries=3,
            jitter_type=JitterType.EQUAL,
            enable_circuit_breaker=False
        )
        
        assert config.strategy == BackoffStrategy.LINEAR
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0
        assert config.multiplier == 1.5
        assert config.max_retries == 3
        assert config.jitter_type == JitterType.EQUAL
        assert config.enable_circuit_breaker is False


class TestBackoffIntegration:
    """Test backoff integration with real scenarios"""
    
    @pytest.mark.asyncio
    async def test_network_timeout_scenario(self):
        """Test backoff with network timeout scenario"""
        config = BackoffConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            max_retries=3,
            base_delay=0.1,
            max_delay=2.0
        )
        manager = ComprehensiveBackoffManager(config)
        
        timeout_count = 0
        
        async def network_operation():
            nonlocal timeout_count
            timeout_count += 1
            if timeout_count <= 2:
                raise asyncio.TimeoutError("Network timeout")
            return "network_success"
        
        result = await manager.execute_with_backoff(
            network_operation, "network_operation"
        )
        
        assert result == "network_success"
        assert timeout_count == 3
    
    @pytest.mark.asyncio
    async def test_rate_limit_scenario(self):
        """Test backoff with rate limit scenario"""
        config = BackoffConfig(
            strategy=BackoffStrategy.ADAPTIVE,
            max_retries=3,
            base_delay=0.1,
            max_delay=2.0
        )
        manager = ComprehensiveBackoffManager(config)
        
        rate_limit_count = 0
        
        async def rate_limited_operation():
            nonlocal rate_limit_count
            rate_limit_count += 1
            if rate_limit_count <= 2:
                raise Exception("Rate limit exceeded")
            return "rate_limit_success"
        
        result = await manager.execute_with_backoff(
            rate_limited_operation, "rate_limited_operation"
        )
        
        assert result == "rate_limit_success"
        assert rate_limit_count == 3 