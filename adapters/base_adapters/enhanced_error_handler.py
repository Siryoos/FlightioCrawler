"""
Enhanced Error Handling System for FlightIO Crawler
Provides comprehensive error handling, correlation, and recovery mechanisms.
"""

import logging
import time
import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from functools import wraps
import traceback
import uuid
import psutil
import threading
from pathlib import Path
import math
import statistics

try:
    from ..strategies.circuit_breaker_integration import (
        get_integrated_circuit_breaker,
        IntegratedCircuitBreakerConfig,
        IntegrationFailureType,
        record_error_handler_failure,
        record_success as cb_record_success,
        can_make_request as cb_can_make_request
    )
    CIRCUIT_BREAKER_INTEGRATION_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_INTEGRATION_AVAILABLE = False


class ErrorSeverity(Enum):
    """Standardized error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ErrorCategory(Enum):
    """Standardized error categories"""
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


class ErrorAction(Enum):
    """Actions to take when errors occur"""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    ESCALATE = "escalate"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# Unified Exception Classes
class AdapterError(Exception):
    """Base exception for all adapter errors"""
    
    def __init__(self, message: str, context: Optional['ErrorContext'] = None):
        super().__init__(message)
        self.context = context
        self.timestamp = datetime.now()


class NavigationError(AdapterError):
    """Exception for navigation-related errors"""
    pass


class FormFillingError(AdapterError):
    """Exception for form filling errors"""
    pass


class ExtractionError(AdapterError):
    """Exception for data extraction errors"""
    pass


class ValidationError(AdapterError):
    """Exception for data validation errors"""
    pass


class TimeoutError(AdapterError):
    """Exception for timeout errors"""
    pass


class AdapterTimeoutError(TimeoutError):
    """Specific timeout error for adapters"""
    pass


class AdapterNetworkError(AdapterError):
    """Exception for network-related errors"""
    pass


class AdapterValidationError(ValidationError):
    """Specific validation error for adapters"""
    pass


class AdapterRateLimitError(AdapterError):
    """Exception for rate limit errors"""
    pass


class AdapterAuthenticationError(AdapterError):
    """Exception for authentication errors"""
    pass


class AdapterResourceError(AdapterError):
    """Exception for resource errors"""
    pass


class AdapterParsingError(AdapterError):
    """Exception for parsing errors"""
    pass


@dataclass
class ErrorContext:
    """Comprehensive error context information"""
    adapter_name: str
    operation: str
    timestamp: datetime = field(default_factory=datetime.now)
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: Optional[str] = None
    search_params: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    additional_info: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    browser_info: Optional[Dict[str, Any]] = None
    system_info: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    element_index: Optional[int] = None  # For backward compatibility


@dataclass
class ErrorRecord:
    """Enhanced error record with correlation support"""
    error_id: str
    timestamp: datetime
    adapter_name: str
    operation: str
    error_message: str
    error_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    action_taken: ErrorAction
    context: ErrorContext
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_method: Optional[str] = None
    related_errors: List[str] = field(default_factory=list)
    pattern_hash: Optional[str] = None
    frequency: int = 1
    

@dataclass
class ErrorPattern:
    """Pattern matching for error correlation"""
    pattern_id: str
    pattern_hash: str
    error_signature: str
    occurrences: int = 1
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    affected_adapters: List[str] = field(default_factory=list)
    severity_trend: List[ErrorSeverity] = field(default_factory=list)
    resolution_suggestions: List[str] = field(default_factory=list)


@dataclass
class RecoveryStrategy:
    """Recovery strategy configuration"""
    strategy_id: str
    name: str
    description: str
    applicable_errors: List[ErrorCategory]
    max_attempts: int = 3
    delay_seconds: float = 1.0
    exponential_backoff: bool = True
    success_rate: float = 0.0
    last_success: Optional[datetime] = None
    handler: Optional[Callable] = None


class EnhancedErrorHandler:
    """
    Comprehensive error handling system with correlation and recovery
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Error storage
        self.error_records: Dict[str, ErrorRecord] = {}
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Configuration
        self.circuit_config = self._load_circuit_config()
        self.max_records = self.config.get('max_records', 10000)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.8)
        
        # Recovery strategies
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self._initialize_recovery_strategies()
        
        # Metrics
        self.metrics = defaultdict(int)
        
        # Alert callbacks
        self.alert_callbacks: List[Callable] = []
        
        # Background tasks
        self._cleanup_task = None
        self._pattern_detection_task = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initialize integrated circuit breaker
        self._init_integrated_circuit_breaker()
        
        # Start background tasks
        self._start_background_tasks()
        
        self.logger.info("Enhanced error handler initialized")

    def _load_circuit_config(self) -> Dict[str, Any]:
        """Load circuit breaker configuration"""
        return {
            'failure_threshold': self.config.get('circuit_breaker', {}).get('failure_threshold', 5),
            'recovery_timeout': self.config.get('circuit_breaker', {}).get('recovery_timeout', 300),
            'half_open_max_calls': self.config.get('circuit_breaker', {}).get('half_open_max_calls', 3),
            'monitor_interval': self.config.get('circuit_breaker', {}).get('monitor_interval', 60)
        }

    def _initialize_recovery_strategies(self):
        """Initialize built-in recovery strategies"""
        strategies = [
            RecoveryStrategy(
                strategy_id="retry_with_backoff",
                name="Retry with Exponential Backoff",
                description="Retry operation with exponential backoff",
                applicable_errors=[ErrorCategory.NETWORK, ErrorCategory.TIMEOUT],
                max_attempts=3,
                delay_seconds=1.0,
                exponential_backoff=True
            ),
            RecoveryStrategy(
                strategy_id="refresh_page",
                name="Refresh Page",
                description="Refresh the current page and retry",
                applicable_errors=[ErrorCategory.BROWSER, ErrorCategory.NAVIGATION],
                max_attempts=2,
                delay_seconds=2.0
            ),
            RecoveryStrategy(
                strategy_id="clear_cache",
                name="Clear Cache and Retry",
                description="Clear browser cache and retry operation",
                applicable_errors=[ErrorCategory.BROWSER, ErrorCategory.RESOURCE],
                max_attempts=1,
                delay_seconds=5.0
            ),
            RecoveryStrategy(
                strategy_id="change_user_agent",
                name="Change User Agent",
                description="Change browser user agent and retry",
                applicable_errors=[ErrorCategory.AUTHENTICATION, ErrorCategory.CAPTCHA],
                max_attempts=2,
                delay_seconds=3.0
            ),
            RecoveryStrategy(
                strategy_id="fallback_extraction",
                name="Fallback Extraction Method",
                description="Use alternative extraction method",
                applicable_errors=[ErrorCategory.PARSING, ErrorCategory.VALIDATION],
                max_attempts=1,
                delay_seconds=0.5
            )
        ]
        
        for strategy in strategies:
            self.recovery_strategies[strategy.strategy_id] = strategy

    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        suggested_action: ErrorAction = ErrorAction.RETRY
    ) -> Tuple[bool, Optional[str]]:
        """
        Enhanced error handling with correlation and recovery
        
        Returns:
            Tuple of (should_retry, recovery_strategy_id)
        """
        try:
            # Create error record
            error_record = await self._create_error_record(
                error, context, severity, category, suggested_action
            )
            
            # Store and correlate error
            await self._store_and_correlate_error(error_record)
            
            # Update metrics
            self._update_metrics(error_record)
            
            # Check circuit breaker
            circuit_action = await self._check_circuit_breaker(
                context.adapter_name, error_record
            )
            
            if circuit_action == "block":
                self.logger.warning(f"Circuit breaker open for {context.adapter_name}")
                return False, None
            
            # Determine recovery strategy
            recovery_strategy = await self._select_recovery_strategy(
                error_record, context
            )
            
            # Execute recovery if applicable
            if recovery_strategy and context.retry_count < context.max_retries:
                success = await self._execute_recovery_strategy(
                    recovery_strategy, error_record, context
                )
                
                if success:
                    self.logger.info(
                        f"Recovery successful for {context.adapter_name} using {recovery_strategy.name}"
                    )
                    # Record success in integrated circuit breaker if error was handled successfully
                    if self.integrated_circuit_breaker and CIRCUIT_BREAKER_INTEGRATION_AVAILABLE:
                        try:
                            await self.integrated_circuit_breaker.record_success("error_handler")
                        except Exception as e:
                            self.logger.error(f"Failed to record success in integrated circuit breaker: {e}")
                    return True, recovery_strategy.strategy_id
                else:
                    self.logger.warning(
                        f"Recovery failed for {context.adapter_name} using {recovery_strategy.name}"
                    )
            
            # Send alerts for critical errors
            if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.EMERGENCY]:
                await self._send_alert(error_record)
            
            # Log error
            self._log_error(error_record)
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")
            return False, None

    async def _create_error_record(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
        category: ErrorCategory,
        suggested_action: ErrorAction
    ) -> ErrorRecord:
        """Create comprehensive error record"""
        
        # Generate pattern hash for correlation
        pattern_hash = self._generate_pattern_hash(error, context)
        
        # Collect system information
        system_info = {
            'memory_usage': psutil.virtual_memory().percent,
            'cpu_usage': psutil.cpu_percent(),
            'disk_usage': psutil.disk_usage('/').percent,
            'process_count': len(psutil.pids())
        }
        
        # Update context with system info
        context.system_info = system_info
        context.stack_trace = traceback.format_exc()
        
        error_record = ErrorRecord(
            error_id=context.error_id,
            timestamp=context.timestamp,
            adapter_name=context.adapter_name,
            operation=context.operation,
            error_message=str(error),
            error_type=type(error).__name__,
            severity=severity,
            category=category,
            action_taken=suggested_action,
            context=context,
            pattern_hash=pattern_hash
        )
        
        return error_record

    def _generate_pattern_hash(self, error: Exception, context: ErrorContext) -> str:
        """Generate hash for error pattern detection"""
        pattern_elements = [
            type(error).__name__,
            context.adapter_name,
            context.operation,
            str(error)[:100]  # First 100 chars of error message
        ]
        
        pattern_string = "|".join(pattern_elements)
        return hashlib.md5(pattern_string.encode()).hexdigest()

    async def _store_and_correlate_error(self, error_record: ErrorRecord):
        """Store error and perform correlation analysis"""
        # Store error record
        self.error_records[error_record.error_id] = error_record
        self.error_timeline.append(error_record)
        
        # Update or create pattern
        pattern_hash = error_record.pattern_hash
        if pattern_hash in self.error_patterns:
            pattern = self.error_patterns[pattern_hash]
            pattern.occurrences += 1
            pattern.last_seen = datetime.now()
            pattern.affected_adapters.append(error_record.adapter_name)
            pattern.severity_trend.append(error_record.severity)
        else:
            pattern = ErrorPattern(
                pattern_id=str(uuid.uuid4()),
                pattern_hash=pattern_hash,
                error_signature=f"{error_record.error_type}:{error_record.adapter_name}:{error_record.operation}",
                affected_adapters=[error_record.adapter_name],
                severity_trend=[error_record.severity]
            )
            self.error_patterns[pattern_hash] = pattern
            self.metrics['patterns_detected'] += 1
        
        # Correlate with recent errors
        await self._correlate_with_recent_errors(error_record)

    async def _correlate_with_recent_errors(self, error_record: ErrorRecord):
        """Correlate error with recent errors to find patterns"""
        recent_window = datetime.now() - self.pattern_detection_window
        recent_errors = [
            err for err in self.error_timeline 
            if err.timestamp >= recent_window and err.error_id != error_record.error_id
        ]
        
        for recent_error in recent_errors:
            correlation_score = self._calculate_correlation_score(
                error_record, recent_error
            )
            
            if correlation_score >= self.correlation_threshold:
                # Add to correlation map
                correlation_id = f"{error_record.error_id}:{recent_error.error_id}"
                self.correlation_map[correlation_id].extend([
                    error_record.error_id, recent_error.error_id
                ])
                
                # Update related errors
                error_record.related_errors.append(recent_error.error_id)
                recent_error.related_errors.append(error_record.error_id)

    def _calculate_correlation_score(
        self, error1: ErrorRecord, error2: ErrorRecord
    ) -> float:
        """Calculate correlation score between two errors"""
        score = 0.0
        
        # Same adapter
        if error1.adapter_name == error2.adapter_name:
            score += 0.3
        
        # Same operation
        if error1.operation == error2.operation:
            score += 0.2
        
        # Same error type
        if error1.error_type == error2.error_type:
            score += 0.2
        
        # Same category
        if error1.category == error2.category:
            score += 0.1
        
        # Time proximity (within 10 minutes)
        time_diff = abs((error1.timestamp - error2.timestamp).total_seconds())
        if time_diff <= 600:  # 10 minutes
            score += 0.2
        
        return score

    def _update_metrics(self, error_record: ErrorRecord):
        """Update error metrics"""
        self.metrics['total_errors'] += 1
        self.metrics['errors_by_severity'][error_record.severity.value] += 1
        self.metrics['errors_by_category'][error_record.category.value] += 1
        self.metrics['errors_by_adapter'][error_record.adapter_name] += 1

    async def _check_circuit_breaker(
        self, adapter_name: str, error_record: ErrorRecord
    ) -> str:
        """Check and update circuit breaker state"""
        # Use integrated circuit breaker if available
        if self.integrated_circuit_breaker and CIRCUIT_BREAKER_INTEGRATION_AVAILABLE:
            try:
                # Check if requests are allowed
                can_proceed = await self.integrated_circuit_breaker.can_make_request("error_handler")
                
                if not can_proceed:
                    self.metrics['circuit_breaker_trips'] += 1
                    self.logger.warning(f"Integrated circuit breaker blocking requests for {adapter_name}")
                    return "block"
                
                # Record the error in the integrated circuit breaker
                failure_type = self._map_error_category_to_failure_type(error_record.category)
                await self.integrated_circuit_breaker.record_error_handler_failure(
                    failure_type, 
                    f"Error in {adapter_name}: {error_record.error_message}"
                )
                
                return "allow"
                
            except Exception as e:
                self.logger.error(f"Integrated circuit breaker check failed: {e}")
                # Fall back to legacy circuit breaker logic
                return await self._legacy_circuit_breaker_check(adapter_name, error_record)
        else:
            # Use legacy circuit breaker logic
            return await self._legacy_circuit_breaker_check(adapter_name, error_record)
    
    def _map_error_category_to_failure_type(self, category: ErrorCategory) -> 'IntegrationFailureType':
        """Map error category to integration failure type"""
        if not CIRCUIT_BREAKER_INTEGRATION_AVAILABLE:
            return None
        
        # Map using category values to avoid import circular dependencies
        category_value = category.value if hasattr(category, 'value') else str(category)
        
        mapping = {
            "rate_limit": IntegrationFailureType.RATE_LIMIT_EXCEEDED,
            "timeout": IntegrationFailureType.TIMEOUT,
            "network": IntegrationFailureType.NETWORK_ERROR,
            "validation": IntegrationFailureType.VALIDATION_ERROR,
            "authentication": IntegrationFailureType.ERROR_HANDLER_FAILURE,
            "parsing": IntegrationFailureType.ERROR_HANDLER_FAILURE,
            "browser": IntegrationFailureType.ADAPTER_FAILURE,
            "form_filling": IntegrationFailureType.ADAPTER_FAILURE,
            "navigation": IntegrationFailureType.ADAPTER_FAILURE,
            "captcha": IntegrationFailureType.ADAPTER_FAILURE,
            "resource": IntegrationFailureType.ERROR_HANDLER_FAILURE
        }
        
        return mapping.get(category_value, IntegrationFailureType.ERROR_HANDLER_FAILURE)
    
    async def _legacy_circuit_breaker_check(
        self, adapter_name: str, error_record: ErrorRecord
    ) -> str:
        """Legacy circuit breaker check logic"""
        circuit_key = f"{adapter_name}:{error_record.category.value}"
        
        if circuit_key not in self.circuit_breakers:
            self.circuit_breakers[circuit_key] = {
                'state': CircuitState.CLOSED,
                'failure_count': 0,
                'last_failure': None,
                'last_success': None,
                'half_open_calls': 0
            }
        
        circuit = self.circuit_breakers[circuit_key]
        current_state = CircuitState(circuit['state'])
        
        if current_state == CircuitState.CLOSED:
            circuit['failure_count'] += 1
            circuit['last_failure'] = datetime.now()
            
            if circuit['failure_count'] >= self.circuit_config['failure_threshold']:
                circuit['state'] = CircuitState.OPEN.value
                self.metrics['circuit_breaker_trips'] += 1
                self.logger.warning(f"Circuit breaker opened for {circuit_key}")
                return "block"
        
        elif current_state == CircuitState.OPEN:
            if circuit['last_failure']:
                time_since_failure = (datetime.now() - circuit['last_failure']).total_seconds()
                if time_since_failure >= self.circuit_config['recovery_timeout']:
                    circuit['state'] = CircuitState.HALF_OPEN.value
                    circuit['half_open_calls'] = 0
                    self.logger.info(f"Circuit breaker half-open for {circuit_key}")
                    return "allow"
            return "block"
        
        elif current_state == CircuitState.HALF_OPEN:
            circuit['half_open_calls'] += 1
            if circuit['half_open_calls'] >= self.circuit_config['half_open_max_calls']:
                circuit['state'] = CircuitState.OPEN.value
                self.logger.warning(f"Circuit breaker re-opened for {circuit_key}")
                return "block"
        
        return "allow"

    async def _select_recovery_strategy(
        self, error_record: ErrorRecord, context: ErrorContext
    ) -> Optional[RecoveryStrategy]:
        """Select appropriate recovery strategy"""
        applicable_strategies = [
            strategy for strategy in self.recovery_strategies.values()
            if error_record.category in strategy.applicable_errors
        ]
        
        if not applicable_strategies:
            return None
        
        # Sort by success rate and select best
        applicable_strategies.sort(key=lambda s: s.success_rate, reverse=True)
        return applicable_strategies[0]

    async def _execute_recovery_strategy(
        self, strategy: RecoveryStrategy, error_record: ErrorRecord, context: ErrorContext
    ) -> bool:
        """Execute recovery strategy"""
        try:
            self.metrics['recovery_attempts'] += 1
            
            if strategy.handler:
                await strategy.handler(error_record, context)
            else:
                # Default recovery based on strategy ID
                if strategy.strategy_id == "retry_with_backoff":
                    delay = strategy.delay_seconds
                    if strategy.exponential_backoff:
                        delay *= (2 ** context.retry_count)
                    await asyncio.sleep(delay)
                
                elif strategy.strategy_id == "refresh_page":
                    if hasattr(context, 'page') and context.page:
                        await context.page.reload()
                        await asyncio.sleep(strategy.delay_seconds)
                
                # Add more recovery implementations as needed
            
            # Update success metrics
            strategy.success_rate = (
                (strategy.success_rate * (strategy.occurrences - 1) + 1.0) / strategy.occurrences
            )
            strategy.last_success = datetime.now()
            self.metrics['recovery_successes'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Recovery strategy {strategy.name} failed: {e}")
            return False

    async def _send_alert(self, error_record: ErrorRecord):
        """Send alert for critical errors"""
        alert_data = {
            'error_id': error_record.error_id,
            'adapter_name': error_record.adapter_name,
            'operation': error_record.operation,
            'error_message': error_record.error_message,
            'severity': error_record.severity.value,
            'category': error_record.category.value,
            'timestamp': error_record.timestamp.isoformat(),
            'related_errors': error_record.related_errors
        }
        
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                self.logger.error(f"Alert callback failed: {e}")

    def _log_error(self, error_record: ErrorRecord):
        """Log error with appropriate level"""
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.EMERGENCY: logging.CRITICAL
        }.get(error_record.severity, logging.ERROR)
        
        self.logger.log(
            log_level,
            f"[{error_record.error_id}] {error_record.adapter_name}.{error_record.operation}: "
            f"{error_record.error_message} (Category: {error_record.category.value}, "
            f"Severity: {error_record.severity.value})"
        )

    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_old_errors())
        self._pattern_detection_task = asyncio.create_task(self._detect_error_patterns())

    async def _cleanup_old_errors(self):
        """Cleanup old error records"""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                # Remove old error records
                old_errors = [
                    error_id for error_id, error_record in self.error_records.items()
                    if error_record.timestamp < cutoff_time
                ]
                
                for error_id in old_errors:
                    del self.error_records[error_id]
                
                # Remove old patterns
                old_patterns = [
                    pattern_hash for pattern_hash, pattern in self.error_patterns.items()
                    if pattern.last_seen < cutoff_time
                ]
                
                for pattern_hash in old_patterns:
                    del self.error_patterns[pattern_hash]
                
                self.logger.debug(f"Cleaned up {len(old_errors)} old errors and {len(old_patterns)} old patterns")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
            
            await asyncio.sleep(3600)  # Run every hour

    async def _detect_error_patterns(self):
        """Detect error patterns and generate insights"""
        while True:
            try:
                # Analyze patterns for insights
                for pattern in self.error_patterns.values():
                    if pattern.occurrences >= 5:  # Pattern threshold
                        # Generate resolution suggestions
                        await self._generate_resolution_suggestions(pattern)
                
                await asyncio.sleep(1800)  # Run every 30 minutes
                
            except Exception as e:
                self.logger.error(f"Error in pattern detection: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _generate_resolution_suggestions(self, pattern: ErrorPattern):
        """Generate resolution suggestions for error patterns"""
        suggestions = []
        
        # Analyze pattern characteristics
        if "network" in pattern.error_signature.lower():
            suggestions.append("Check network connectivity and firewall settings")
            suggestions.append("Implement retry logic with exponential backoff")
        
        if "timeout" in pattern.error_signature.lower():
            suggestions.append("Increase timeout values")
            suggestions.append("Optimize page load performance")
        
        if "parsing" in pattern.error_signature.lower():
            suggestions.append("Update CSS selectors")
            suggestions.append("Implement fallback parsing methods")
        
        if len(pattern.affected_adapters) > 1:
            suggestions.append("Consider system-wide optimization")
        
        pattern.resolution_suggestions = suggestions

    # Public API methods
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        return {
            'metrics': dict(self.metrics),
            'total_patterns': len(self.error_patterns),
            'circuit_breakers': {
                key: {
                    'state': breaker['state'],
                    'failure_count': breaker['failure_count'],
                    'last_failure': breaker['last_failure'].isoformat() if breaker['last_failure'] else None
                }
                for key, breaker in self.circuit_breakers.items()
            },
            'recovery_strategies': {
                key: {
                    'success_rate': strategy.success_rate,
                    'last_success': strategy.last_success.isoformat() if strategy.last_success else None
                }
                for key, strategy in self.recovery_strategies.items()
            }
        }

    def get_error_patterns(self) -> List[Dict[str, Any]]:
        """Get detected error patterns"""
        return [
            {
                'pattern_id': pattern.pattern_id,
                'error_signature': pattern.error_signature,
                'occurrences': pattern.occurrences,
                'affected_adapters': pattern.affected_adapters,
                'first_seen': pattern.first_seen.isoformat(),
                'last_seen': pattern.last_seen.isoformat(),
                'resolution_suggestions': pattern.resolution_suggestions
            }
            for pattern in self.error_patterns.values()
        ]

    def add_alert_callback(self, callback: Callable):
        """Add alert callback function"""
        self.alert_callbacks.append(callback)

    def add_recovery_strategy(self, strategy: RecoveryStrategy):
        """Add custom recovery strategy"""
        self.recovery_strategies[strategy.strategy_id] = strategy

    async def reset_circuit_breaker(self, adapter_name: str, category: str = None):
        """Reset circuit breaker for adapter"""
        if category:
            circuit_key = f"{adapter_name}:{category}"
            if circuit_key in self.circuit_breakers:
                self.circuit_breakers[circuit_key]['state'] = CircuitState.CLOSED.value
                self.circuit_breakers[circuit_key]['failure_count'] = 0
        else:
            # Reset all circuit breakers for adapter
            for key in list(self.circuit_breakers.keys()):
                if key.startswith(f"{adapter_name}:"):
                    self.circuit_breakers[key]['state'] = CircuitState.CLOSED.value
                    self.circuit_breakers[key]['failure_count'] = 0

    async def close(self):
        """Cleanup resources"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._pattern_detection_task:
            self._pattern_detection_task.cancel()
        
        self.logger.info("Enhanced Error Handler closed")

    def _init_integrated_circuit_breaker(self):
        """Initialize integrated circuit breaker"""
        if CIRCUIT_BREAKER_INTEGRATION_AVAILABLE:
            try:
                # Create circuit breaker configuration
                cb_config = IntegratedCircuitBreakerConfig(
                    error_handler_failure_threshold=self.circuit_config.get('failure_threshold', 5),
                    error_handler_recovery_timeout=float(self.circuit_config.get('recovery_timeout', 300)),
                    enable_adaptive_thresholds=True
                )
                
                # Get integrated circuit breaker
                self.integrated_circuit_breaker = get_integrated_circuit_breaker(
                    "error_handler", 
                    cb_config,
                    error_handler_callback=self._health_check
                )
                self.logger.info("Integrated circuit breaker initialized for error handler")
            except Exception as e:
                self.logger.error(f"Failed to initialize integrated circuit breaker: {e}")
                self.integrated_circuit_breaker = None
        else:
            self.integrated_circuit_breaker = None
            self.logger.warning("Circuit breaker integration not available")
    
    async def _health_check(self) -> bool:
        """Health check callback for integrated circuit breaker"""
        try:
            with self._lock:
                # Check if error handler is healthy
                current_time = datetime.now()
                recent_errors = [
                    error for error in self.error_records.values()
                    if (current_time - error.timestamp).total_seconds() < 300  # Last 5 minutes
                ]
                
                # Check error rate
                if len(recent_errors) > 20:  # Too many errors in 5 minutes
                    return False
                
                # Check for critical errors
                critical_errors = [
                    error for error in recent_errors
                    if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.EMERGENCY]
                ]
                
                if len(critical_errors) > 3:  # Too many critical errors
                    return False
                
                return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


class CommonErrorHandler:
    """
    Legacy compatibility wrapper for CommonErrorHandler.
    
    This wrapper provides backward compatibility for existing code
    that depends on the old CommonErrorHandler interface.
    """
    
    def __init__(self, adapter_name: str, config: Dict[str, Any] = None):
        self.adapter_name = adapter_name
        self.config = config or {}
        self.enhanced_handler = get_global_error_handler()
        self.logger = logging.getLogger(f"{adapter_name}_errors")
        
        # Legacy error statistics - maintained for compatibility
        self.error_stats = {
            "total_errors": 0,
            "navigation_errors": 0,
            "form_errors": 0,
            "extraction_errors": 0,
            "validation_errors": 0,
            "timeout_errors": 0,
            "last_error_time": None,
        }
    
    def handle_error(
        self, error: Exception, context: ErrorContext, should_retry: bool = True
    ) -> bool:
        """
        Handle error with appropriate logging and recovery (legacy interface).
        
        Args:
            error: Exception that occurred
            context: Error context information
            should_retry: Whether to attempt retry
            
        Returns:
            True if operation should be retried, False otherwise
        """
        # Update legacy error statistics
        self._update_error_stats(error)
        
        # Map legacy context to enhanced context if needed
        if not hasattr(context, 'error_id'):
            enhanced_context = ErrorContext(
                adapter_name=context.adapter_name,
                operation=context.operation,
                url=context.url,
                search_params=context.search_params,
                retry_count=context.retry_count,
                additional_info=context.additional_info,
                element_index=getattr(context, 'element_index', None)
            )
        else:
            enhanced_context = context
        
        # Determine severity and category
        severity = self._determine_severity(error)
        category = self._categorize_error(error)
        
        # Use enhanced error handler
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            should_retry_enhanced, strategy_id = loop.run_until_complete(
                self.enhanced_handler.handle_error(
                    error, enhanced_context, severity, category
                )
            )
            return should_retry_enhanced and should_retry
        except Exception as e:
            # Fallback to simple logging if enhanced handler fails
            self.logger.error(f"Error handling failed: {e}")
            self._log_error_simple(error, enhanced_context)
            return should_retry and isinstance(error, (NavigationError, TimeoutError, AdapterNetworkError))
    
    def _update_error_stats(self, error: Exception) -> None:
        """Update legacy error statistics."""
        self.error_stats["total_errors"] += 1
        self.error_stats["last_error_time"] = datetime.now()
        
        # Update specific error type counters
        if isinstance(error, NavigationError):
            self.error_stats["navigation_errors"] += 1
        elif isinstance(error, FormFillingError):
            self.error_stats["form_errors"] += 1
        elif isinstance(error, ExtractionError):
            self.error_stats["extraction_errors"] += 1
        elif isinstance(error, ValidationError):
            self.error_stats["validation_errors"] += 1
        elif isinstance(error, TimeoutError):
            self.error_stats["timeout_errors"] += 1
    
    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on exception type."""
        if isinstance(error, (AdapterTimeoutError, AdapterNetworkError)):
            return ErrorSeverity.HIGH
        elif isinstance(error, (NavigationError, FormFillingError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(error, (ExtractionError, ValidationError)):
            return ErrorSeverity.LOW
        else:
            return ErrorSeverity.MEDIUM
    
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error for enhanced handling."""
        if isinstance(error, AdapterNetworkError):
            return ErrorCategory.NETWORK
        elif isinstance(error, AdapterTimeoutError):
            return ErrorCategory.TIMEOUT
        elif isinstance(error, NavigationError):
            return ErrorCategory.NAVIGATION
        elif isinstance(error, FormFillingError):
            return ErrorCategory.FORM_FILLING
        elif isinstance(error, ExtractionError):
            return ErrorCategory.PARSING
        elif isinstance(error, ValidationError):
            return ErrorCategory.VALIDATION
        elif isinstance(error, AdapterRateLimitError):
            return ErrorCategory.RATE_LIMIT
        elif isinstance(error, AdapterAuthenticationError):
            return ErrorCategory.AUTHENTICATION
        elif isinstance(error, AdapterResourceError):
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.UNKNOWN
    
    def _log_error_simple(self, error: Exception, context: ErrorContext):
        """Simple error logging fallback."""
        self.logger.error(
            f"[{context.operation}] {type(error).__name__}: {str(error)}"
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get legacy error statistics."""
        return self.error_stats.copy()
    
    def reset_error_statistics(self) -> None:
        """Reset legacy error statistics."""
        self.error_stats = {
            "total_errors": 0,
            "navigation_errors": 0,
            "form_errors": 0,
            "extraction_errors": 0,
            "validation_errors": 0,
            "timeout_errors": 0,
            "last_error_time": None,
        }
    
    async def retry_with_backoff(
        self, operation: Callable, context: ErrorContext, *args, **kwargs
    ) -> Any:
        """Legacy retry with backoff method."""
        max_retries = context.max_retries
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                context.retry_count = attempt
                return await operation(*args, **kwargs)
            except Exception as e:
                if attempt >= max_retries:
                    raise
                
                # Use exponential backoff
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                
                # Log retry attempt
                self.logger.info(f"Retrying {context.operation} after {delay}s (attempt {attempt + 1})")


def error_handler_decorator(
    operation_name: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    max_retries: int = 3
):
    """Decorator for automatic error handling"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'error_handler'):
                return await func(self, *args, **kwargs)
            
            adapter_name = getattr(self, 'adapter_name', self.__class__.__name__)
            context = ErrorContext(
                adapter_name=adapter_name,
                operation=operation_name,
                max_retries=max_retries,
                additional_info={'args': str(args), 'kwargs': str(kwargs)}
            )
            
            for attempt in range(max_retries + 1):
                try:
                    context.retry_count = attempt
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    should_retry, strategy_id = await self.error_handler.handle_error(
                        e, context, severity, category
                    )
                    
                    if not should_retry or attempt >= max_retries:
                        raise
                    
                    # Add delay before retry
                    await asyncio.sleep(1.0 * (2 ** attempt))
            
            return None
        return wrapper
    return decorator


# Global error handler instance
_global_error_handler = None


def get_global_error_handler() -> EnhancedErrorHandler:
    """Get global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = EnhancedErrorHandler()
    return _global_error_handler


def initialize_global_error_handler(config: Dict[str, Any]) -> EnhancedErrorHandler:
    """Initialize global error handler with configuration"""
    global _global_error_handler
    _global_error_handler = EnhancedErrorHandler(config)
    return _global_error_handler


# Legacy compatibility decorator
def error_handler(operation_name: str):
    """
    Legacy decorator for automatic error handling (DEPRECATED).
    
    Use error_handler_decorator instead for enhanced functionality.
    
    Args:
        operation_name: Name of the operation for error context
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get error handler from adapter instance
            if not hasattr(self, "error_handler"):
                # Fallback to basic error handling
                return await func(self, *args, **kwargs)
            
            # Create error context
            context = ErrorContext(
                adapter_name=getattr(self, "adapter_name", self.__class__.__name__),
                operation=operation_name,
                search_params=kwargs.get("search_params"),
                url=getattr(self, "current_url", None),
            )
            
            # Execute with retry logic using enhanced handler if available
            if hasattr(self.error_handler, 'retry_with_backoff'):
                return await self.error_handler.retry_with_backoff(
                    func, context, self, *args, **kwargs
                )
            else:
                # Fallback to basic execution
                return await func(self, *args, **kwargs)
        
        return wrapper
    return decorator


# Safe extraction decorator for backward compatibility
def safe_extract(default_value: Any = None):
    """
    Decorator for safe data extraction.
    
    Args:
        default_value: Value to return if extraction fails
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log extraction error
                if len(args) > 0 and hasattr(args[0], "logger"):
                    args[0].logger.debug(f"Extraction failed in {func.__name__}: {e}")
                return default_value
        return wrapper
    return decorator


# Recovery strategies for backward compatibility
class ErrorRecoveryStrategies:
    """
    Common error recovery strategies (for backward compatibility).
    """
    
    @staticmethod
    async def refresh_page(page) -> None:
        """Refresh page as recovery strategy."""
        try:
            await page.reload()
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            raise NavigationError(f"Failed to refresh page: {e}")
    
    @staticmethod
    async def clear_cookies_and_retry(page) -> None:
        """Clear cookies and retry as recovery strategy."""
        try:
            await page.context.clear_cookies()
            await page.reload()
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            raise NavigationError(f"Failed to clear cookies and retry: {e}")
    
    @staticmethod
    async def wait_and_retry(delay: float = 5.0) -> None:
        """Wait for specified time before retry."""
        await asyncio.sleep(delay)
    
    @staticmethod
    async def switch_user_agent(page, user_agent: str) -> None:
        """Switch user agent as recovery strategy."""
        try:
            await page.set_extra_http_headers({"User-Agent": user_agent})
        except Exception as e:
            raise NavigationError(f"Failed to switch user agent: {e}") 