"""
Unified Error Handler

This module provides a unified error handling system that merges approaches from:
- Requests folder error patterns
- Crawlers folder error handling
- Adapters system enhanced error handling

It provides consistent error handling across all three crawler systems.
"""

import asyncio
import logging
import traceback
from typing import Dict, Any, List, Optional, Union, Type, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import uuid

from .base_adapters.enhanced_error_handler import EnhancedErrorHandler
from .unified_crawler_interface import CrawlerSystemType

logger = logging.getLogger(__name__)


class UnifiedErrorType(Enum):
    """Unified error types across all systems."""
    # Network errors
    NETWORK_ERROR = "network_error"
    CONNECTION_TIMEOUT = "connection_timeout"
    CONNECTION_REFUSED = "connection_refused"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"
    
    # HTTP errors
    HTTP_ERROR = "http_error"
    HTTP_4XX_ERROR = "http_4xx_error"
    HTTP_5XX_ERROR = "http_5xx_error"
    HTTP_REDIRECT_ERROR = "http_redirect_error"
    
    # Browser/Selenium errors
    BROWSER_ERROR = "browser_error"
    SELENIUM_ERROR = "selenium_error"
    JAVASCRIPT_ERROR = "javascript_error"
    PAGE_LOAD_ERROR = "page_load_error"
    ELEMENT_NOT_FOUND = "element_not_found"
    
    # Parsing errors
    PARSING_ERROR = "parsing_error"
    DATA_EXTRACTION_ERROR = "data_extraction_error"
    VALIDATION_ERROR = "validation_error"
    FORMAT_ERROR = "format_error"
    
    # System errors
    SYSTEM_ERROR = "system_error"
    MEMORY_ERROR = "memory_error"
    DISK_ERROR = "disk_error"
    PERMISSION_ERROR = "permission_error"
    
    # Configuration errors
    CONFIG_ERROR = "config_error"
    INVALID_CONFIG = "invalid_config"
    MISSING_CONFIG = "missing_config"
    
    # Rate limiting and throttling
    RATE_LIMIT_ERROR = "rate_limit_error"
    THROTTLED_ERROR = "throttled_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    
    # Authentication and authorization
    AUTH_ERROR = "auth_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    TOKEN_EXPIRED = "token_expired"
    
    # Bridge and integration errors
    BRIDGE_ERROR = "bridge_error"
    INTERFACE_ERROR = "interface_error"
    COMPATIBILITY_ERROR = "compatibility_error"
    
    # Business logic errors
    NO_DATA_FOUND = "no_data_found"
    INVALID_INPUT = "invalid_input"
    BUSINESS_RULE_ERROR = "business_rule_error"
    
    # Unknown/other
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class UnifiedErrorContext:
    """Enhanced error context for unified error handling."""
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_type: CrawlerSystemType = CrawlerSystemType.UNIFIED
    error_type: UnifiedErrorType = UnifiedErrorType.UNKNOWN_ERROR
    error_message: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Request context
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # System context
    crawler_name: Optional[str] = None
    bridge_type: Optional[str] = None
    adapter_name: Optional[str] = None
    
    # Retry context
    attempt_count: int = 1
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Stack trace
    stack_trace: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedErrorHandler(EnhancedErrorHandler):
    """
    Unified error handler that merges error handling approaches from all systems.
    
    This handler provides:
    - Unified error classification
    - System-specific error handling
    - Enhanced retry mechanisms
    - Comprehensive error reporting
    - Error pattern learning
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the unified error handler."""
        super().__init__(config or {})
        
        # Error pattern mappings for different systems
        self.error_patterns = {
            CrawlerSystemType.REQUESTS: self._setup_requests_patterns(),
            CrawlerSystemType.CRAWLERS: self._setup_crawlers_patterns(),
            CrawlerSystemType.ADAPTERS: self._setup_adapters_patterns(),
            CrawlerSystemType.UNIFIED: self._setup_unified_patterns()
        }
        
        # Error statistics per system
        self.system_error_stats = {
            system: {
                "total_errors": 0,
                "error_types": {},
                "retry_success_rate": 0.0,
                "last_error": None
            } for system in CrawlerSystemType
        }
        
        # Recovery strategies
        self.recovery_strategies = {
            UnifiedErrorType.NETWORK_ERROR: self._recover_network_error,
            UnifiedErrorType.CONNECTION_TIMEOUT: self._recover_timeout_error,
            UnifiedErrorType.BROWSER_ERROR: self._recover_browser_error,
            UnifiedErrorType.PARSING_ERROR: self._recover_parsing_error,
            UnifiedErrorType.RATE_LIMIT_ERROR: self._recover_rate_limit_error,
            UnifiedErrorType.AUTH_ERROR: self._recover_auth_error,
            UnifiedErrorType.BRIDGE_ERROR: self._recover_bridge_error
        }
        
        logger.info("UnifiedErrorHandler initialized")
    
    def _setup_requests_patterns(self) -> Dict[str, UnifiedErrorType]:
        """Set up error patterns for requests system."""
        return {
            # Network errors
            "ConnectionError": UnifiedErrorType.NETWORK_ERROR,
            "ConnectTimeout": UnifiedErrorType.CONNECTION_TIMEOUT,
            "ReadTimeout": UnifiedErrorType.CONNECTION_TIMEOUT,
            "Timeout": UnifiedErrorType.CONNECTION_TIMEOUT,
            "ConnectionRefusedError": UnifiedErrorType.CONNECTION_REFUSED,
            "gaierror": UnifiedErrorType.DNS_ERROR,
            "SSLError": UnifiedErrorType.SSL_ERROR,
            
            # HTTP errors
            "HTTPError": UnifiedErrorType.HTTP_ERROR,
            "404": UnifiedErrorType.HTTP_4XX_ERROR,
            "403": UnifiedErrorType.FORBIDDEN,
            "401": UnifiedErrorType.UNAUTHORIZED,
            "500": UnifiedErrorType.HTTP_5XX_ERROR,
            "502": UnifiedErrorType.HTTP_5XX_ERROR,
            "503": UnifiedErrorType.HTTP_5XX_ERROR,
            
            # Selenium/Browser errors
            "WebDriverException": UnifiedErrorType.BROWSER_ERROR,
            "TimeoutException": UnifiedErrorType.PAGE_LOAD_ERROR,
            "NoSuchElementException": UnifiedErrorType.ELEMENT_NOT_FOUND,
            "ElementNotInteractableException": UnifiedErrorType.BROWSER_ERROR,
            "StaleElementReferenceException": UnifiedErrorType.BROWSER_ERROR,
            "JavascriptException": UnifiedErrorType.JAVASCRIPT_ERROR,
            
            # Parsing errors
            "JSONDecodeError": UnifiedErrorType.PARSING_ERROR,
            "BeautifulSoupError": UnifiedErrorType.PARSING_ERROR,
            "AttributeError": UnifiedErrorType.DATA_EXTRACTION_ERROR,
            "KeyError": UnifiedErrorType.DATA_EXTRACTION_ERROR,
            "IndexError": UnifiedErrorType.DATA_EXTRACTION_ERROR,
            
            # System errors
            "MemoryError": UnifiedErrorType.MEMORY_ERROR,
            "OSError": UnifiedErrorType.SYSTEM_ERROR,
            "PermissionError": UnifiedErrorType.PERMISSION_ERROR
        }
    
    def _setup_crawlers_patterns(self) -> Dict[str, UnifiedErrorType]:
        """Set up error patterns for crawlers system."""
        return {
            # Crawler-specific errors
            "CrawlerError": UnifiedErrorType.SYSTEM_ERROR,
            "RateLimitExceeded": UnifiedErrorType.RATE_LIMIT_ERROR,
            "SiteConfigError": UnifiedErrorType.CONFIG_ERROR,
            "DataExtractionError": UnifiedErrorType.DATA_EXTRACTION_ERROR,
            "NoFlightsFound": UnifiedErrorType.NO_DATA_FOUND,
            "InvalidSearchParams": UnifiedErrorType.INVALID_INPUT,
            
            # Browser automation errors
            "BrowserInitError": UnifiedErrorType.BROWSER_ERROR,
            "PageNavigationError": UnifiedErrorType.PAGE_LOAD_ERROR,
            "FormFillError": UnifiedErrorType.BROWSER_ERROR,
            "SearchFormError": UnifiedErrorType.ELEMENT_NOT_FOUND,
            
            # Configuration errors
            "MissingConfigKey": UnifiedErrorType.MISSING_CONFIG,
            "InvalidConfigValue": UnifiedErrorType.INVALID_CONFIG
        }
    
    def _setup_adapters_patterns(self) -> Dict[str, UnifiedErrorType]:
        """Set up error patterns for adapters system."""
        return {
            # Adapter-specific errors
            "AdapterError": UnifiedErrorType.SYSTEM_ERROR,
            "EnhancedAdapterError": UnifiedErrorType.SYSTEM_ERROR,
            "SiteAdapterError": UnifiedErrorType.SYSTEM_ERROR,
            "AuthenticationError": UnifiedErrorType.AUTH_ERROR,
            "AuthorizationError": UnifiedErrorType.FORBIDDEN,
            "RateLimitingError": UnifiedErrorType.RATE_LIMIT_ERROR,
            "CircuitBreakerError": UnifiedErrorType.THROTTLED_ERROR,
            
            # Data processing errors
            "DataEncryptionError": UnifiedErrorType.SYSTEM_ERROR,
            "DataValidationError": UnifiedErrorType.VALIDATION_ERROR,
            "FlightDataError": UnifiedErrorType.DATA_EXTRACTION_ERROR,
            
            # Monitoring errors
            "MonitoringError": UnifiedErrorType.SYSTEM_ERROR,
            "MetricsError": UnifiedErrorType.SYSTEM_ERROR
        }
    
    def _setup_unified_patterns(self) -> Dict[str, UnifiedErrorType]:
        """Set up error patterns for unified system."""
        return {
            # Bridge errors
            "BridgeError": UnifiedErrorType.BRIDGE_ERROR,
            "InterfaceError": UnifiedErrorType.INTERFACE_ERROR,
            "CompatibilityError": UnifiedErrorType.COMPATIBILITY_ERROR,
            "SystemIntegrationError": UnifiedErrorType.BRIDGE_ERROR,
            
            # Configuration errors
            "UnifiedConfigError": UnifiedErrorType.CONFIG_ERROR,
            "MetaFactoryError": UnifiedErrorType.SYSTEM_ERROR,
            "CrawlerCreationError": UnifiedErrorType.SYSTEM_ERROR
        }
    
    async def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle error with unified approach.
        
        Args:
            error: Exception to handle
            context: Additional context information
            
        Returns:
            Error response dictionary
        """
        # Create unified error context
        error_context = self._create_error_context(error, context or {})
        
        # Classify error
        error_context.error_type = self._classify_error(error, error_context.system_type)
        
        # Update statistics
        self._update_error_statistics(error_context)
        
        # Log error
        await self._log_error(error_context)
        
        # Attempt recovery if applicable
        recovery_result = await self._attempt_recovery(error_context)
        
        # Prepare response
        response = {
            "error_id": error_context.error_id,
            "error_type": error_context.error_type.value,
            "error_message": error_context.error_message,
            "system_type": error_context.system_type.value,
            "timestamp": error_context.timestamp.isoformat(),
            "recovery_attempted": recovery_result["attempted"],
            "recovery_successful": recovery_result["successful"],
            "recovery_message": recovery_result.get("message", ""),
            "retry_recommended": self._should_retry(error_context),
            "retry_delay": self._calculate_retry_delay(error_context),
            "context": {
                "url": error_context.url,
                "crawler_name": error_context.crawler_name,
                "bridge_type": error_context.bridge_type,
                "adapter_name": error_context.adapter_name,
                "attempt_count": error_context.attempt_count
            }
        }
        
        return response
    
    def _create_error_context(self, error: Exception, context: Dict[str, Any]) -> UnifiedErrorContext:
        """Create unified error context from error and context."""
        error_context = UnifiedErrorContext(
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            metadata=context
        )
        
        # Extract system type
        if "system_type" in context:
            error_context.system_type = context["system_type"]
        elif "bridge_type" in context:
            if "requests" in context["bridge_type"]:
                error_context.system_type = CrawlerSystemType.REQUESTS
            elif "crawlers" in context["bridge_type"]:
                error_context.system_type = CrawlerSystemType.CRAWLERS
            else:
                error_context.system_type = CrawlerSystemType.ADAPTERS
        
        # Extract context information
        error_context.url = context.get("url")
        error_context.crawler_name = context.get("crawler_name") or context.get("crawler_class")
        error_context.bridge_type = context.get("bridge_type")
        error_context.adapter_name = context.get("adapter_name")
        error_context.attempt_count = context.get("attempt_count", 1)
        error_context.max_retries = context.get("max_retries", 3)
        
        # Extract request details
        if "params" in context:
            error_context.params = context["params"]
        if "headers" in context:
            error_context.headers = context["headers"]
        if "method" in context:
            error_context.method = context["method"]
        
        return error_context
    
    def _classify_error(self, error: Exception, system_type: CrawlerSystemType) -> UnifiedErrorType:
        """Classify error based on type and system."""
        error_class_name = type(error).__name__
        error_message = str(error).lower()
        
        # Check system-specific patterns first
        patterns = self.error_patterns.get(system_type, {})
        
        # Direct class name match
        if error_class_name in patterns:
            return patterns[error_class_name]
        
        # Message pattern matching
        for pattern, error_type in patterns.items():
            if pattern.lower() in error_message:
                return error_type
        
        # Fallback to generic patterns
        generic_patterns = self.error_patterns[CrawlerSystemType.UNIFIED]
        for pattern, error_type in generic_patterns.items():
            if pattern.lower() in error_message or pattern.lower() in error_class_name.lower():
                return error_type
        
        # HTTP status code detection
        if "404" in error_message or "not found" in error_message:
            return UnifiedErrorType.HTTP_4XX_ERROR
        elif "500" in error_message or "internal server error" in error_message:
            return UnifiedErrorType.HTTP_5XX_ERROR
        elif "timeout" in error_message:
            return UnifiedErrorType.CONNECTION_TIMEOUT
        elif "connection" in error_message and "refused" in error_message:
            return UnifiedErrorType.CONNECTION_REFUSED
        elif "permission" in error_message or "denied" in error_message:
            return UnifiedErrorType.PERMISSION_ERROR
        
        return UnifiedErrorType.UNKNOWN_ERROR
    
    def _update_error_statistics(self, error_context: UnifiedErrorContext) -> None:
        """Update error statistics for the system."""
        stats = self.system_error_stats[error_context.system_type]
        stats["total_errors"] += 1
        
        error_type_key = error_context.error_type.value
        if error_type_key not in stats["error_types"]:
            stats["error_types"][error_type_key] = 0
        stats["error_types"][error_type_key] += 1
        
        stats["last_error"] = {
            "error_id": error_context.error_id,
            "error_type": error_type_key,
            "timestamp": error_context.timestamp.isoformat(),
            "message": error_context.error_message
        }
    
    async def _log_error(self, error_context: UnifiedErrorContext) -> None:
        """Log error with appropriate level and detail."""
        log_message = (
            f"[{error_context.system_type.value}] {error_context.error_type.value}: "
            f"{error_context.error_message}"
        )
        
        if error_context.url:
            log_message += f" | URL: {error_context.url}"
        
        if error_context.crawler_name:
            log_message += f" | Crawler: {error_context.crawler_name}"
        
        if error_context.bridge_type:
            log_message += f" | Bridge: {error_context.bridge_type}"
        
        # Determine log level based on error type
        if error_context.error_type in [
            UnifiedErrorType.NETWORK_ERROR,
            UnifiedErrorType.CONNECTION_TIMEOUT,
            UnifiedErrorType.RATE_LIMIT_ERROR,
            UnifiedErrorType.NO_DATA_FOUND
        ]:
            logger.warning(log_message)
        elif error_context.error_type in [
            UnifiedErrorType.SYSTEM_ERROR,
            UnifiedErrorType.MEMORY_ERROR,
            UnifiedErrorType.BRIDGE_ERROR,
            UnifiedErrorType.CONFIG_ERROR
        ]:
            logger.error(log_message)
            if error_context.stack_trace:
                logger.error(f"Stack trace: {error_context.stack_trace}")
        else:
            logger.info(log_message)
    
    async def _attempt_recovery(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Attempt error recovery based on error type."""
        recovery_strategy = self.recovery_strategies.get(error_context.error_type)
        
        if not recovery_strategy:
            return {"attempted": False, "successful": False}
        
        try:
            result = await recovery_strategy(error_context)
            return {
                "attempted": True,
                "successful": result["successful"],
                "message": result.get("message", "")
            }
        except Exception as e:
            logger.error(f"Recovery strategy failed: {e}")
            return {
                "attempted": True,
                "successful": False,
                "message": f"Recovery failed: {str(e)}"
            }
    
    # Recovery strategies
    
    async def _recover_network_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from network errors."""
        if error_context.attempt_count < error_context.max_retries:
            await asyncio.sleep(error_context.retry_delay * error_context.attempt_count)
            return {"successful": True, "message": "Network retry scheduled"}
        return {"successful": False, "message": "Max retries exceeded"}
    
    async def _recover_timeout_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from timeout errors."""
        # Increase timeout for next attempt
        new_timeout = error_context.metadata.get("timeout", 30) * 1.5
        error_context.metadata["suggested_timeout"] = min(new_timeout, 120)
        return {"successful": True, "message": f"Timeout increased to {new_timeout}s"}
    
    async def _recover_browser_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from browser errors."""
        # Suggest browser restart
        error_context.metadata["suggested_action"] = "restart_browser"
        return {"successful": True, "message": "Browser restart suggested"}
    
    async def _recover_parsing_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from parsing errors."""
        # Suggest alternative parsing strategy
        error_context.metadata["suggested_action"] = "try_alternative_parser"
        return {"successful": True, "message": "Alternative parsing strategy suggested"}
    
    async def _recover_rate_limit_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from rate limiting errors."""
        # Calculate backoff delay
        backoff_delay = min(error_context.retry_delay * (2 ** error_context.attempt_count), 300)
        error_context.metadata["suggested_delay"] = backoff_delay
        return {"successful": True, "message": f"Backoff delay: {backoff_delay}s"}
    
    async def _recover_auth_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from authentication errors."""
        # Suggest credential refresh
        error_context.metadata["suggested_action"] = "refresh_credentials"
        return {"successful": True, "message": "Credential refresh suggested"}
    
    async def _recover_bridge_error(self, error_context: UnifiedErrorContext) -> Dict[str, Any]:
        """Recover from bridge errors."""
        # Suggest alternative bridge or direct adapter
        error_context.metadata["suggested_action"] = "try_alternative_bridge"
        return {"successful": True, "message": "Alternative bridge suggested"}
    
    def _should_retry(self, error_context: UnifiedErrorContext) -> bool:
        """Determine if error should be retried."""
        # Don't retry if max attempts reached
        if error_context.attempt_count >= error_context.max_retries:
            return False
        
        # Retryable error types
        retryable_errors = {
            UnifiedErrorType.NETWORK_ERROR,
            UnifiedErrorType.CONNECTION_TIMEOUT,
            UnifiedErrorType.CONNECTION_REFUSED,
            UnifiedErrorType.HTTP_5XX_ERROR,
            UnifiedErrorType.BROWSER_ERROR,
            UnifiedErrorType.PAGE_LOAD_ERROR,
            UnifiedErrorType.RATE_LIMIT_ERROR,
            UnifiedErrorType.THROTTLED_ERROR
        }
        
        return error_context.error_type in retryable_errors
    
    def _calculate_retry_delay(self, error_context: UnifiedErrorContext) -> float:
        """Calculate retry delay based on error type and attempt count."""
        base_delay = error_context.retry_delay
        
        # Exponential backoff for certain error types
        if error_context.error_type in [
            UnifiedErrorType.RATE_LIMIT_ERROR,
            UnifiedErrorType.THROTTLED_ERROR,
            UnifiedErrorType.HTTP_5XX_ERROR
        ]:
            return min(base_delay * (2 ** error_context.attempt_count), 300)
        
        # Linear backoff for others
        return base_delay * error_context.attempt_count
    
    def get_error_statistics(self, system_type: Optional[CrawlerSystemType] = None) -> Dict[str, Any]:
        """Get error statistics for a specific system or all systems."""
        if system_type:
            return self.system_error_stats[system_type].copy()
        
        return {
            system.value: stats.copy()
            for system, stats in self.system_error_stats.items()
        }
    
    def reset_error_statistics(self, system_type: Optional[CrawlerSystemType] = None) -> None:
        """Reset error statistics for a specific system or all systems."""
        if system_type:
            self.system_error_stats[system_type] = {
                "total_errors": 0,
                "error_types": {},
                "retry_success_rate": 0.0,
                "last_error": None
            }
        else:
            for system in CrawlerSystemType:
                self.reset_error_statistics(system)


# Global unified error handler instance
_unified_error_handler: Optional[UnifiedErrorHandler] = None


def get_unified_error_handler(config: Optional[Dict[str, Any]] = None) -> UnifiedErrorHandler:
    """Get the global unified error handler instance."""
    global _unified_error_handler
    if _unified_error_handler is None:
        _unified_error_handler = UnifiedErrorHandler(config)
    return _unified_error_handler


# Convenience functions for different systems
async def handle_requests_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error from requests system."""
    context["system_type"] = CrawlerSystemType.REQUESTS
    handler = get_unified_error_handler()
    return await handler.handle_error(error, context)


async def handle_crawlers_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error from crawlers system."""
    context["system_type"] = CrawlerSystemType.CRAWLERS
    handler = get_unified_error_handler()
    return await handler.handle_error(error, context)


async def handle_adapters_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error from adapters system."""
    context["system_type"] = CrawlerSystemType.ADAPTERS
    handler = get_unified_error_handler()
    return await handler.handle_error(error, context)


async def handle_unified_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error from unified system."""
    context["system_type"] = CrawlerSystemType.UNIFIED
    handler = get_unified_error_handler()
    return await handler.handle_error(error, context) 