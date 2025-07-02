"""
Common error handling utilities for all adapters.

This module provides centralized error handling to eliminate
code duplication across different adapters.
"""

from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass
import logging
import asyncio
from datetime import datetime, timedelta
import traceback
from functools import wraps


@dataclass
class ErrorContext:
    """Context information for error reporting."""
    adapter_name: str
    operation: str
    search_params: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    element_index: Optional[int] = None
    retry_count: int = 0
    additional_info: Optional[Dict[str, Any]] = None


class AdapterError(Exception):
    """Base exception for adapter errors."""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context
        self.timestamp = datetime.now()


class NavigationError(AdapterError):
    """Error during page navigation."""
    pass


class FormFillingError(AdapterError):
    """Error during form filling."""
    pass


class ExtractionError(AdapterError):
    """Error during data extraction."""
    pass


class ValidationError(AdapterError):
    """Error during data validation."""
    pass


class TimeoutError(AdapterError):
    """Timeout error."""
    pass


class CommonErrorHandler:
    """
    Common error handler for all adapters.
    
    This class provides centralized error handling, logging,
    and recovery mechanisms.
    """
    
    def __init__(self, adapter_name: str, config: Dict[str, Any] = None):
        self.adapter_name = adapter_name
        self.config = config or {}
        self.logger = self._setup_logger()
        
        # Error statistics
        self.error_stats = {
            'total_errors': 0,
            'navigation_errors': 0,
            'form_errors': 0,
            'extraction_errors': 0,
            'validation_errors': 0,
            'timeout_errors': 0,
            'last_error_time': None
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger for error handling."""
        logger = logging.getLogger(f"{self.adapter_name}_errors")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        should_retry: bool = True
    ) -> bool:
        """
        Handle error with appropriate logging and recovery.
        
        Args:
            error: Exception that occurred
            context: Error context information
            should_retry: Whether to attempt retry
            
        Returns:
            True if operation should be retried, False otherwise
        """
        # Update error statistics
        self._update_error_stats(error)
        
        # Create detailed error report
        error_report = self._create_error_report(error, context)
        
        # Log error with appropriate level
        self._log_error(error_report)
        
        # Determine if retry should be attempted
        if should_retry and self._should_retry(error, context):
            self.logger.info(f"Retrying operation after error: {context.operation}")
            return True
        
        return False
    
    def _update_error_stats(self, error: Exception) -> None:
        """Update error statistics."""
        self.error_stats['total_errors'] += 1
        self.error_stats['last_error_time'] = datetime.now()
        
        # Update specific error type counters
        if isinstance(error, NavigationError):
            self.error_stats['navigation_errors'] += 1
        elif isinstance(error, FormFillingError):
            self.error_stats['form_errors'] += 1
        elif isinstance(error, ExtractionError):
            self.error_stats['extraction_errors'] += 1
        elif isinstance(error, ValidationError):
            self.error_stats['validation_errors'] += 1
        elif isinstance(error, TimeoutError):
            self.error_stats['timeout_errors'] += 1
    
    def _create_error_report(self, error: Exception, context: ErrorContext) -> Dict[str, Any]:
        """Create detailed error report."""
        report = {
            'adapter': self.adapter_name,
            'operation': context.operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'retry_count': context.retry_count,
            'stack_trace': traceback.format_exc()
        }
        
        # Add context information
        if context.search_params:
            report['search_params'] = context.search_params
        if context.url:
            report['url'] = context.url
        if context.element_index is not None:
            report['element_index'] = context.element_index
        if context.additional_info:
            report['additional_info'] = context.additional_info
        
        return report
    
    def _log_error(self, error_report: Dict[str, Any]) -> None:
        """Log error with appropriate level and format."""
        operation = error_report['operation']
        error_type = error_report['error_type']
        error_message = error_report['error_message']
        retry_count = error_report['retry_count']
        
        # Create main error message
        main_msg = f"[{operation}] {error_type}: {error_message}"
        
        if retry_count > 0:
            main_msg += f" (Retry {retry_count})"
        
        # Log with appropriate level based on error type
        if error_type in ['TimeoutError', 'NavigationError']:
            self.logger.warning(main_msg)
        else:
            self.logger.error(main_msg)
        
        # Log additional context at debug level
        if error_report.get('search_params'):
            self.logger.debug(f"Search params: {error_report['search_params']}")
        
        if error_report.get('url'):
            self.logger.debug(f"URL: {error_report['url']}")
        
        # Log stack trace at debug level for non-timeout errors
        if error_type != 'TimeoutError' and error_report.get('stack_trace'):
            self.logger.debug(f"Stack trace: {error_report['stack_trace']}")
    
    def _should_retry(self, error: Exception, context: ErrorContext) -> bool:
        """Determine if operation should be retried."""
        max_retries = self.config.get('error_handling', {}).get('max_retries', 3)
        
        # Don't retry if max retries exceeded
        if context.retry_count >= max_retries:
            return False
        
        # Don't retry validation errors (usually permanent)
        if isinstance(error, ValidationError):
            return False
        
        # Retry timeouts and navigation errors
        if isinstance(error, (TimeoutError, NavigationError)):
            return True
        
        # Retry form filling errors (might be temporary)
        if isinstance(error, FormFillingError):
            return True
        
        # Retry extraction errors (page might not be fully loaded)
        if isinstance(error, ExtractionError):
            return True
        
        # Don't retry unknown errors by default
        return False
    
    async def retry_with_backoff(
        self,
        operation: Callable,
        context: ErrorContext,
        *args,
        **kwargs
    ) -> Any:
        """
        Retry operation with exponential backoff.
        
        Args:
            operation: Async function to retry
            context: Error context
            *args: Arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result of successful operation
            
        Raises:
            Last exception if all retries fail
        """
        max_retries = self.config.get('error_handling', {}).get('max_retries', 3)
        base_delay = self.config.get('error_handling', {}).get('retry_delay', 2)
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                context.retry_count = attempt
                return await operation(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Handle error and determine if retry should be attempted
                should_retry = self.handle_error(e, context, should_retry=(attempt < max_retries))
                
                if not should_retry or attempt >= max_retries:
                    break
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** attempt)
                self.logger.info(f"Waiting {delay}s before retry {attempt + 1}")
                await asyncio.sleep(delay)
        
        # All retries failed
        raise last_exception
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        return self.error_stats.copy()
    
    def reset_error_statistics(self) -> None:
        """Reset error statistics."""
        self.error_stats = {
            'total_errors': 0,
            'navigation_errors': 0,
            'form_errors': 0,
            'extraction_errors': 0,
            'validation_errors': 0,
            'timeout_errors': 0,
            'last_error_time': None
        }


def error_handler(operation_name: str):
    """
    Decorator for automatic error handling.
    
    Args:
        operation_name: Name of the operation for error context
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get error handler from adapter instance
            if not hasattr(self, 'error_handler'):
                # Fallback to basic error handling
                return await func(self, *args, **kwargs)
            
            # Create error context
            context = ErrorContext(
                adapter_name=getattr(self, 'adapter_name', self.__class__.__name__),
                operation=operation_name,
                search_params=kwargs.get('search_params'),
                url=getattr(self, 'current_url', None)
            )
            
            # Execute with retry logic
            return await self.error_handler.retry_with_backoff(
                func, context, self, *args, **kwargs
            )
        
        return wrapper
    return decorator


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
                if len(args) > 0 and hasattr(args[0], 'logger'):
                    args[0].logger.debug(f"Extraction failed in {func.__name__}: {e}")
                return default_value
        return wrapper
    return decorator


class ErrorRecoveryStrategies:
    """
    Common error recovery strategies.
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
            await page.set_extra_http_headers({
                'User-Agent': user_agent
            })
        except Exception as e:
            raise NavigationError(f"Failed to switch user agent: {e}") 