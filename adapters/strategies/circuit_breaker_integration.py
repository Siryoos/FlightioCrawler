"""
Circuit Breaker Integration Module
Unified integration of enhanced circuit breaker with rate limiter and error handler systems
"""

import asyncio
import logging
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .enhanced_circuit_breaker import (
    EnhancedCircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitState,
    FailureType,
    RecoveryStrategy,
    get_circuit_breaker
)

# Define error categories locally to avoid import chain issues
class ErrorCategory(Enum):
    """Error categories for circuit breaker integration"""
    NETWORK = "network"
    PARSING = "parsing"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    RESOURCE = "resource"
    BROWSER = "browser"
    FORM_FILLING = "form_filling"
    NAVIGATION = "navigation"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"

class ErrorSeverity(Enum):
    """Error severity levels for circuit breaker integration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class IntegrationFailureType(Enum):
    """Integration-specific failure types"""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ERROR_HANDLER_FAILURE = "error_handler_failure"
    ADAPTER_FAILURE = "adapter_failure"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"


@dataclass
class IntegratedCircuitBreakerConfig:
    """Configuration for integrated circuit breaker"""
    # Rate limiter integration
    rate_limiter_failure_threshold: int = 3
    rate_limiter_recovery_timeout: float = 30.0
    
    # Error handler integration
    error_handler_failure_threshold: int = 5
    error_handler_recovery_timeout: float = 60.0
    
    # Adapter integration
    adapter_failure_threshold: int = 5
    adapter_recovery_timeout: float = 120.0
    
    # Global settings
    global_failure_threshold: int = 10
    global_recovery_timeout: float = 300.0
    enable_adaptive_thresholds: bool = True
    
    # Failure type weights
    failure_type_weights: Dict[IntegrationFailureType, float] = None
    
    def __post_init__(self):
        if self.failure_type_weights is None:
            self.failure_type_weights = {
                IntegrationFailureType.RATE_LIMIT_EXCEEDED: 0.5,
                IntegrationFailureType.ERROR_HANDLER_FAILURE: 1.0,
                IntegrationFailureType.ADAPTER_FAILURE: 1.0,
                IntegrationFailureType.TIMEOUT: 0.8,
                IntegrationFailureType.NETWORK_ERROR: 0.9,
                IntegrationFailureType.VALIDATION_ERROR: 0.3
            }


class IntegratedCircuitBreaker:
    """Integrated circuit breaker for rate limiter and error handler"""
    
    def __init__(self, 
                 name: str, 
                 config: IntegratedCircuitBreakerConfig = None,
                 rate_limiter_callback: Optional[Callable] = None,
                 error_handler_callback: Optional[Callable] = None):
        self.name = name
        self.config = config or IntegratedCircuitBreakerConfig()
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # Create enhanced circuit breaker instances for different contexts
        self.rate_limiter_circuit = self._create_rate_limiter_circuit()
        self.error_handler_circuit = self._create_error_handler_circuit()
        self.adapter_circuit = self._create_adapter_circuit()
        self.global_circuit = self._create_global_circuit()
        
        # Integration callbacks
        self.rate_limiter_callback = rate_limiter_callback
        self.error_handler_callback = error_handler_callback
        
        # Statistics
        self.integration_stats = {
            'rate_limiter_triggers': 0,
            'error_handler_triggers': 0,
            'adapter_triggers': 0,
            'global_triggers': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0
        }
        
        self.logger.info(f"Integrated circuit breaker '{name}' initialized")
    
    def _create_rate_limiter_circuit(self) -> EnhancedCircuitBreaker:
        """Create circuit breaker for rate limiter integration"""
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.rate_limiter_failure_threshold,
            recovery_timeout=self.config.rate_limiter_recovery_timeout,
            recovery_strategy=RecoveryStrategy.GRADUAL,
            enabled_failure_types=[FailureType.RATE_LIMIT, FailureType.TIMEOUT]
        )
        
        circuit = EnhancedCircuitBreaker(f"{self.name}_rate_limiter", circuit_config)
        circuit.set_health_check_callback(self._rate_limiter_health_check)
        return circuit
    
    def _create_error_handler_circuit(self) -> EnhancedCircuitBreaker:
        """Create circuit breaker for error handler integration"""
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.error_handler_failure_threshold,
            recovery_timeout=self.config.error_handler_recovery_timeout,
            recovery_strategy=RecoveryStrategy.EXPONENTIAL,
            enabled_failure_types=[FailureType.UNKNOWN, FailureType.TIMEOUT, FailureType.NETWORK_ERROR]
        )
        
        circuit = EnhancedCircuitBreaker(f"{self.name}_error_handler", circuit_config)
        circuit.set_health_check_callback(self._error_handler_health_check)
        return circuit
    
    def _create_adapter_circuit(self) -> EnhancedCircuitBreaker:
        """Create circuit breaker for adapter integration"""
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.adapter_failure_threshold,
            recovery_timeout=self.config.adapter_recovery_timeout,
            recovery_strategy=RecoveryStrategy.ADAPTIVE,
            enabled_failure_types=[FailureType.UNKNOWN, FailureType.NETWORK_ERROR, FailureType.TIMEOUT]
        )
        
        circuit = EnhancedCircuitBreaker(f"{self.name}_adapter", circuit_config)
        return circuit
    
    def _create_global_circuit(self) -> EnhancedCircuitBreaker:
        """Create global circuit breaker"""
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.global_failure_threshold,
            recovery_timeout=self.config.global_recovery_timeout,
            recovery_strategy=RecoveryStrategy.EXPONENTIAL,
            enabled_failure_types=list(FailureType)
        )
        
        circuit = EnhancedCircuitBreaker(f"{self.name}_global", circuit_config)
        return circuit
    
    async def _rate_limiter_health_check(self) -> bool:
        """Health check for rate limiter circuit"""
        if self.rate_limiter_callback:
            try:
                return await self.rate_limiter_callback()
            except Exception as e:
                self.logger.error(f"Rate limiter health check failed: {e}")
                return False
        return True
    
    async def _error_handler_health_check(self) -> bool:
        """Health check for error handler circuit"""
        if self.error_handler_callback:
            try:
                return await self.error_handler_callback()
            except Exception as e:
                self.logger.error(f"Error handler health check failed: {e}")
                return False
        return True
    
    async def can_make_request(self, context: str = "general") -> bool:
        """Check if request can be made based on all circuit breaker states"""
        # Check global circuit first
        if not await self.global_circuit._can_execute():
            return False
        
        # Check context-specific circuits
        if context == "rate_limiter":
            return await self.rate_limiter_circuit._can_execute()
        elif context == "error_handler":
            return await self.error_handler_circuit._can_execute()
        elif context == "adapter":
            return await self.adapter_circuit._can_execute()
        
        # Check all circuits for general context
        return (await self.rate_limiter_circuit._can_execute() and 
                await self.error_handler_circuit._can_execute() and 
                await self.adapter_circuit._can_execute())
    
    async def record_rate_limiter_failure(self, failure_type: IntegrationFailureType, error_message: str):
        """Record failure in rate limiter circuit"""
        self.integration_stats['rate_limiter_triggers'] += 1
        
        # Map integration failure type to circuit breaker failure type
        cb_failure_type = self._map_failure_type(failure_type)
        
        # Record in rate limiter circuit
        await self.rate_limiter_circuit._record_failure(cb_failure_type, error_message, 0)
        
        # Record in global circuit with weighted impact
        weight = self.config.failure_type_weights.get(failure_type, 1.0)
        if weight >= 0.8:  # Only significant failures affect global circuit
            await self.global_circuit._record_failure(cb_failure_type, error_message, 0)
    
    async def record_error_handler_failure(self, failure_type: IntegrationFailureType, error_message: str):
        """Record failure in error handler circuit"""
        self.integration_stats['error_handler_triggers'] += 1
        
        cb_failure_type = self._map_failure_type(failure_type)
        
        # Record in error handler circuit
        await self.error_handler_circuit._record_failure(cb_failure_type, error_message, 0)
        
        # Record in global circuit
        weight = self.config.failure_type_weights.get(failure_type, 1.0)
        if weight >= 0.8:
            await self.global_circuit._record_failure(cb_failure_type, error_message, 0)
    
    async def record_adapter_failure(self, failure_type: IntegrationFailureType, error_message: str):
        """Record failure in adapter circuit"""
        self.integration_stats['adapter_triggers'] += 1
        
        cb_failure_type = self._map_failure_type(failure_type)
        
        # Record in adapter circuit
        await self.adapter_circuit._record_failure(cb_failure_type, error_message, 0)
        
        # Record in global circuit
        weight = self.config.failure_type_weights.get(failure_type, 1.0)
        if weight >= 0.8:
            await self.global_circuit._record_failure(cb_failure_type, error_message, 0)
    
    async def record_success(self, context: str = "general"):
        """Record success in appropriate circuits"""
        if context == "rate_limiter":
            await self.rate_limiter_circuit._record_success(0)
        elif context == "error_handler":
            await self.error_handler_circuit._record_success(0)
        elif context == "adapter":
            await self.adapter_circuit._record_success(0)
        else:
            # Record success in all circuits
            await self.rate_limiter_circuit._record_success(0)
            await self.error_handler_circuit._record_success(0)
            await self.adapter_circuit._record_success(0)
        
        # Always record in global circuit
        await self.global_circuit._record_success(0)
    
    def _map_failure_type(self, failure_type: IntegrationFailureType) -> FailureType:
        """Map integration failure type to circuit breaker failure type"""
        mapping = {
            IntegrationFailureType.RATE_LIMIT_EXCEEDED: FailureType.RATE_LIMIT,
            IntegrationFailureType.ERROR_HANDLER_FAILURE: FailureType.UNKNOWN,
            IntegrationFailureType.ADAPTER_FAILURE: FailureType.UNKNOWN,
            IntegrationFailureType.TIMEOUT: FailureType.TIMEOUT,
            IntegrationFailureType.NETWORK_ERROR: FailureType.NETWORK_ERROR,
            IntegrationFailureType.VALIDATION_ERROR: FailureType.PARSING_ERROR
        }
        return mapping.get(failure_type, FailureType.UNKNOWN)
    
    async def record_error_category_failure(self, error_category: ErrorCategory, error_message: str):
        """Record failure based on error category"""
        # Map error category to integration failure type
        category_mapping = {
            ErrorCategory.RATE_LIMIT: IntegrationFailureType.RATE_LIMIT_EXCEEDED,
            ErrorCategory.TIMEOUT: IntegrationFailureType.TIMEOUT,
            ErrorCategory.NETWORK: IntegrationFailureType.NETWORK_ERROR,
            ErrorCategory.VALIDATION: IntegrationFailureType.VALIDATION_ERROR
        }
        
        failure_type = category_mapping.get(error_category, IntegrationFailureType.ERROR_HANDLER_FAILURE)
        await self.record_error_handler_failure(failure_type, error_message)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all circuits"""
        return {
            "name": self.name,
            "timestamp": datetime.now().isoformat(),
            "integration_stats": self.integration_stats,
            "circuits": {
                "rate_limiter": self.rate_limiter_circuit.get_status(),
                "error_handler": self.error_handler_circuit.get_status(),
                "adapter": self.adapter_circuit.get_status(),
                "global": self.global_circuit.get_status()
            },
            "overall_health": self._calculate_overall_health()
        }
    
    def _calculate_overall_health(self) -> Dict[str, Any]:
        """Calculate overall health score"""
        circuits_status = [
            self.rate_limiter_circuit.get_status(),
            self.error_handler_circuit.get_status(),
            self.adapter_circuit.get_status(),
            self.global_circuit.get_status()
        ]
        
        open_circuits = sum(1 for status in circuits_status if status["state"] == "open")
        half_open_circuits = sum(1 for status in circuits_status if status["state"] == "half_open")
        
        health_score = 100 - (open_circuits * 25) - (half_open_circuits * 10)
        
        return {
            "health_score": max(0, health_score),
            "open_circuits": open_circuits,
            "half_open_circuits": half_open_circuits,
            "total_circuits": len(circuits_status),
            "recommendation": self._get_health_recommendation(health_score)
        }
    
    def _get_health_recommendation(self, health_score: int) -> str:
        """Get health recommendation based on score"""
        if health_score >= 90:
            return "System is healthy"
        elif health_score >= 70:
            return "Minor issues detected, monitor closely"
        elif health_score >= 50:
            return "Moderate issues, consider reducing load"
        elif health_score >= 30:
            return "Significant issues, implement recovery strategies"
        else:
            return "Critical issues, immediate attention required"
    
    async def reset_all_circuits(self):
        """Reset all circuit breakers"""
        self.rate_limiter_circuit.reset()
        self.error_handler_circuit.reset()
        self.adapter_circuit.reset()
        self.global_circuit.reset()
        
        # Reset stats
        self.integration_stats = {
            'rate_limiter_triggers': 0,
            'error_handler_triggers': 0,
            'adapter_triggers': 0,
            'global_triggers': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0
        }
        
        self.logger.info(f"All circuits reset for {self.name}")


class IntegratedCircuitBreakerManager:
    """Manager for integrated circuit breakers"""
    
    def __init__(self):
        self.integrated_breakers: Dict[str, IntegratedCircuitBreaker] = {}
        self.logger = logging.getLogger(__name__)
    
    def get_integrated_circuit_breaker(self, 
                                     name: str, 
                                     config: IntegratedCircuitBreakerConfig = None,
                                     rate_limiter_callback: Optional[Callable] = None,
                                     error_handler_callback: Optional[Callable] = None) -> IntegratedCircuitBreaker:
        """Get or create integrated circuit breaker"""
        if name not in self.integrated_breakers:
            self.integrated_breakers[name] = IntegratedCircuitBreaker(
                name, config, rate_limiter_callback, error_handler_callback
            )
        return self.integrated_breakers[name]
    
    async def record_rate_limiter_failure_for_site(self, site_id: str, failure_type: IntegrationFailureType, error_message: str):
        """Record rate limiter failure for specific site"""
        circuit = self.get_integrated_circuit_breaker(site_id)
        await circuit.record_rate_limiter_failure(failure_type, error_message)
    
    async def record_error_handler_failure_for_site(self, site_id: str, failure_type: IntegrationFailureType, error_message: str):
        """Record error handler failure for specific site"""
        circuit = self.get_integrated_circuit_breaker(site_id)
        await circuit.record_error_handler_failure(failure_type, error_message)
    
    async def record_adapter_failure_for_site(self, site_id: str, failure_type: IntegrationFailureType, error_message: str):
        """Record adapter failure for specific site"""
        circuit = self.get_integrated_circuit_breaker(site_id)
        await circuit.record_adapter_failure(failure_type, error_message)
    
    async def can_make_request_for_site(self, site_id: str, context: str = "general") -> bool:
        """Check if site can make request"""
        circuit = self.get_integrated_circuit_breaker(site_id)
        return await circuit.can_make_request(context)
    
    async def record_success_for_site(self, site_id: str, context: str = "general"):
        """Record success for specific site"""
        circuit = self.get_integrated_circuit_breaker(site_id)
        await circuit.record_success(context)
    
    async def get_all_status(self) -> Dict[str, Any]:
        """Get status of all integrated circuit breakers"""
        sites_status = {}
        for name, breaker in self.integrated_breakers.items():
            sites_status[name] = await breaker.get_status()
        
        return {
            "total_sites": len(self.integrated_breakers),
            "sites": sites_status
        }
    
    async def reset_all(self):
        """Reset all integrated circuit breakers"""
        for breaker in self.integrated_breakers.values():
            await breaker.reset_all_circuits()
        self.logger.info("All integrated circuit breakers reset")


# Global instance
integrated_circuit_breaker_manager = IntegratedCircuitBreakerManager()

# Convenience functions
def get_integrated_circuit_breaker(name: str, 
                                 config: IntegratedCircuitBreakerConfig = None,
                                 rate_limiter_callback: Optional[Callable] = None,
                                 error_handler_callback: Optional[Callable] = None) -> IntegratedCircuitBreaker:
    """Get integrated circuit breaker instance"""
    return integrated_circuit_breaker_manager.get_integrated_circuit_breaker(
        name, config, rate_limiter_callback, error_handler_callback
    )


async def record_rate_limiter_failure(site_id: str, failure_type: IntegrationFailureType, error_message: str):
    """Record rate limiter failure for site"""
    await integrated_circuit_breaker_manager.record_rate_limiter_failure_for_site(site_id, failure_type, error_message)


async def record_error_handler_failure(site_id: str, failure_type: IntegrationFailureType, error_message: str):
    """Record error handler failure for site"""
    await integrated_circuit_breaker_manager.record_error_handler_failure_for_site(site_id, failure_type, error_message)


async def record_adapter_failure(site_id: str, failure_type: IntegrationFailureType, error_message: str):
    """Record adapter failure for site"""
    await integrated_circuit_breaker_manager.record_adapter_failure_for_site(site_id, failure_type, error_message)


async def can_make_request(site_id: str, context: str = "general") -> bool:
    """Check if site can make request"""
    return await integrated_circuit_breaker_manager.can_make_request_for_site(site_id, context)


async def record_success(site_id: str, context: str = "general"):
    """Record success for site"""
    await integrated_circuit_breaker_manager.record_success_for_site(site_id, context) 