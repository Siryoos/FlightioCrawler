import logging
import time
import asyncio
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
from config import config


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ErrorRecord:
    """Error record with metadata"""

    error: str
    timestamp: datetime
    severity: ErrorSeverity
    domain: str
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes
    expected_exception: type = Exception
    monitor_interval: int = 60  # 1 minute


class EnhancedErrorHandler:
    """Enhanced error handler with advanced features"""

    def __init__(self):
        self.errors: Dict[str, List[ErrorRecord]] = {}
        self.circuit_breakers: Dict[str, Dict] = {}
        self.dead_letter_queue: List[ErrorRecord] = []
        self.retry_strategies: Dict[str, Callable] = {}
        self.error_callbacks: Dict[str, Callable] = {}

        # Configure logging
        self.logger = logging.getLogger(__name__)

        # Default circuit breaker config
        self.default_circuit_config = CircuitBreakerConfig()

    async def handle_error(
        self,
        domain: str,
        error: Any,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        retry_strategy: Optional[Callable] = None,
    ) -> None:
        """Handle error with enhanced features"""
        try:
            # Create error record
            error_record = ErrorRecord(
                error=str(error),
                timestamp=datetime.now(),
                severity=severity,
                domain=domain,
                context=context or {},
                max_retries=3,
            )

            # Initialize domain errors if not exists
            if domain not in self.errors:
                self.errors[domain] = []

            # Add error record
            self.errors[domain].append(error_record)

            # Clean old errors
            await self._clean_old_errors(domain)

            # Check circuit breaker
            await self._check_circuit_breaker(domain)

            # Handle retry logic
            if retry_strategy and error_record.retry_count < error_record.max_retries:
                await self._handle_retry(domain, error_record, retry_strategy)

            # Execute error callbacks
            await self._execute_error_callbacks(domain, error_record)

            # Log error
            self.logger.error(
                f"Error in {domain}: {error} (Severity: {severity.value})",
                extra={
                    "domain": domain,
                    "severity": severity.value,
                    "context": context,
                    "retry_count": error_record.retry_count,
                },
            )

        except Exception as e:
            self.logger.error(f"Error handling error: {e}")

    async def _clean_old_errors(self, domain: str) -> None:
        """Clean old errors for domain"""
        try:
            now = datetime.now()
            window = timedelta(seconds=config.ERROR.circuit_breaker_timeout)

            # Filter errors within window
            self.errors[domain] = [
                error
                for error in self.errors[domain]
                if now - error.timestamp <= window
            ]

        except Exception as e:
            self.logger.error(f"Error cleaning old errors: {e}")

    async def _check_circuit_breaker(self, domain: str) -> None:
        """Check and update circuit breaker state"""
        try:
            if domain not in self.errors:
                return

            # Get circuit config
            circuit_config = self.retry_strategies.get(
                domain, self.default_circuit_config
            )

            # Count recent errors
            recent_errors = [
                error
                for error in self.errors[domain]
                if isinstance(error.error, circuit_config.expected_exception)
            ]

            error_count = len(recent_errors)

            # Get current circuit state
            current_state = self._get_circuit_state(domain)

            if current_state == CircuitState.CLOSED:
                if error_count >= circuit_config.failure_threshold:
                    # Open circuit
                    self.circuit_breakers[domain] = {
                        "state": CircuitState.OPEN.value,
                        "timestamp": datetime.now().isoformat(),
                        "error_count": error_count,
                        "last_error": (
                            recent_errors[-1].error if recent_errors else None
                        ),
                    }
                    self.logger.warning(f"Circuit breaker opened for {domain}")

            elif current_state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                circuit = self.circuit_breakers[domain]
                open_time = datetime.fromisoformat(circuit["timestamp"])

                if datetime.now() - open_time >= timedelta(
                    seconds=circuit_config.recovery_timeout
                ):
                    # Move to half-open state
                    circuit["state"] = CircuitState.HALF_OPEN.value
                    circuit["timestamp"] = datetime.now().isoformat()
                    self.logger.info(f"Circuit breaker half-open for {domain}")

        except Exception as e:
            self.logger.error(f"Error checking circuit breaker: {e}")

    def _get_circuit_state(self, domain: str) -> CircuitState:
        """Get current circuit breaker state"""
        if domain not in self.circuit_breakers:
            return CircuitState.CLOSED

        return CircuitState(self.circuit_breakers[domain]["state"])

    async def _handle_retry(
        self, domain: str, error_record: ErrorRecord, retry_strategy: Callable
    ) -> None:
        """Handle retry logic with exponential backoff"""
        try:
            # Calculate delay with exponential backoff
            delay = min(2**error_record.retry_count, 60)  # Max 60 seconds

            self.logger.info(
                f"Retrying {domain} in {delay} seconds (attempt {error_record.retry_count + 1})"
            )

            # Wait before retry
            await asyncio.sleep(delay)

            # Execute retry strategy
            try:
                await retry_strategy()
                # If successful, remove from errors
                self.errors[domain] = [
                    error for error in self.errors[domain] if error != error_record
                ]
                self.logger.info(f"Retry successful for {domain}")

            except Exception as retry_error:
                # Increment retry count
                error_record.retry_count += 1

                if error_record.retry_count >= error_record.max_retries:
                    # Move to dead letter queue
                    await self._add_to_dead_letter_queue(error_record)
                    self.logger.error(
                        f"Max retries exceeded for {domain}, moved to DLQ"
                    )
                else:
                    # Schedule next retry
                    await self._handle_retry(domain, error_record, retry_strategy)

        except Exception as e:
            self.logger.error(f"Error in retry handling: {e}")

    async def _add_to_dead_letter_queue(self, error_record: ErrorRecord) -> None:
        """Add error to dead letter queue"""
        try:
            self.dead_letter_queue.append(error_record)

            # Keep only last 1000 items
            if len(self.dead_letter_queue) > 1000:
                self.dead_letter_queue = self.dead_letter_queue[-1000:]

        except Exception as e:
            self.logger.error(f"Error adding to DLQ: {e}")

    async def _execute_error_callbacks(
        self, domain: str, error_record: ErrorRecord
    ) -> None:
        """Execute registered error callbacks"""
        try:
            if domain in self.error_callbacks:
                callback = self.error_callbacks[domain]
                await callback(error_record)

        except Exception as e:
            self.logger.error(f"Error executing callback for {domain}: {e}")

    def register_retry_strategy(self, domain: str, strategy: Callable) -> None:
        """Register retry strategy for domain"""
        self.retry_strategies[domain] = strategy

    def register_error_callback(self, domain: str, callback: Callable) -> None:
        """Register error callback for domain"""
        self.error_callbacks[domain] = callback

    def is_circuit_open(self, domain: str) -> bool:
        """Check if circuit breaker is open for domain"""
        return self._get_circuit_state(domain) == CircuitState.OPEN

    def can_make_request(self, domain: str) -> bool:
        """Check if request can be made to domain"""
        state = self._get_circuit_state(domain)

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.HALF_OPEN:
            # Allow one request to test recovery
            return True
        else:  # OPEN
            return False

    async def reset_circuit(self, domain: str) -> None:
        """Reset circuit breaker for domain"""
        try:
            if domain in self.circuit_breakers:
                del self.circuit_breakers[domain]

            if domain in self.errors:
                self.errors[domain] = []

            self.logger.info(f"Circuit breaker reset for {domain}")

        except Exception as e:
            self.logger.error(f"Error resetting circuit breaker: {e}")

    def get_error_stats(self, domain: str) -> Dict[str, Any]:
        """Get comprehensive error statistics for domain"""
        try:
            if domain not in self.errors:
                return {
                    "domain": domain,
                    "error_count": 0,
                    "circuit_state": CircuitState.CLOSED.value,
                    "last_error": None,
                    "severity_distribution": {},
                    "timestamp": datetime.now().isoformat(),
                }

            errors = self.errors[domain]
            error_count = len(errors)

            # Calculate severity distribution
            severity_dist = {}
            for error in errors:
                severity = error.severity.value
                severity_dist[severity] = severity_dist.get(severity, 0) + 1

            # Get circuit state
            circuit_state = self._get_circuit_state(domain).value

            # Get last error
            last_error = errors[-1].error if errors else None

            return {
                "domain": domain,
                "error_count": error_count,
                "circuit_state": circuit_state,
                "last_error": last_error,
                "severity_distribution": severity_dist,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting error stats: {e}")
            return {}

    def get_dead_letter_queue_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics"""
        try:
            return {
                "total_items": len(self.dead_letter_queue),
                "domains": list(set(error.domain for error in self.dead_letter_queue)),
                "severity_distribution": {},
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error getting DLQ stats: {e}")
            return {}

    async def process_dead_letter_queue(self, processor: Callable) -> None:
        """Process items in dead letter queue"""
        try:
            items_to_process = self.dead_letter_queue.copy()
            self.dead_letter_queue.clear()

            for error_record in items_to_process:
                try:
                    await processor(error_record)
                except Exception as e:
                    self.logger.error(f"Error processing DLQ item: {e}")
                    # Re-add to DLQ if processing fails
                    self.dead_letter_queue.append(error_record)

        except Exception as e:
            self.logger.error(f"Error processing DLQ: {e}")

    def export_error_data(self, domain: str) -> str:
        """Export error data as JSON"""
        try:
            if domain not in self.errors:
                return json.dumps([])

            # Convert to serializable format
            export_data = []
            for error in self.errors[domain]:
                export_data.append(
                    {
                        "error": error.error,
                        "timestamp": error.timestamp.isoformat(),
                        "severity": error.severity.value,
                        "domain": error.domain,
                        "context": error.context,
                        "retry_count": error.retry_count,
                    }
                )

            return json.dumps(export_data, indent=2)

        except Exception as e:
            self.logger.error(f"Error exporting error data: {e}")
            return json.dumps([])
