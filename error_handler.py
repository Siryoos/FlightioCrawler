import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config import config

# Configure logging
logger = logging.getLogger(__name__)

class ErrorHandler:
    """Error handler for crawler"""
    
    def __init__(self):
        # Initialize error tracking
        self.errors: Dict[str, List[Dict]] = {}
        self.circuit_breakers: Dict[str, Dict] = {}
        self.error_counts = {}
        self.max_errors = 5
        self.circuit_timeout = 300  # 5 minutes
    
    def handle_error(self, domain: str, error: str) -> None:
        """Handle error for domain"""
        try:
            # Get current time
            now = datetime.now()
            
            # Initialize domain errors if not exists
            if domain not in self.errors:
                self.errors[domain] = []
            
            # Add error
            self.errors[domain].append({
                'error': error,
                'timestamp': now.isoformat()
            })
            
            # Clean old errors
            self._clean_old_errors(domain)
            
            # Check circuit breaker
            self._check_circuit_breaker(domain)
            
        except Exception as e:
            logger.error(f"Error handling error: {e}")
    
    def _clean_old_errors(self, domain: str) -> None:
        """Clean old errors for domain"""
        try:
            # Get current time
            now = datetime.now()
            
            # Get error window
            window = timedelta(seconds=config.ERROR.circuit_breaker_timeout)
            
            # Filter errors
            self.errors[domain] = [
                error for error in self.errors[domain]
                if now - datetime.fromisoformat(error['timestamp']) <= window
            ]
            
        except Exception as e:
            logger.error(f"Error cleaning old errors: {e}")
    
    def _check_circuit_breaker(self, domain: str) -> None:
        """Check circuit breaker for domain"""
        try:
            # Get error count
            error_count = len(self.errors[domain])
            
            # Get threshold
            threshold = config.ERROR.circuit_breaker_threshold
            
            # Check if threshold exceeded
            if error_count >= threshold:
                # Set circuit breaker
                self.circuit_breakers[domain] = {
                    'timestamp': datetime.now().isoformat(),
                    'error_count': error_count
                }
                
                logger.warning(f"Circuit breaker opened for {domain}")
            
        except Exception as e:
            logger.error(f"Error checking circuit breaker: {e}")
    
    def is_circuit_open(self, domain: str) -> bool:
        """Check if circuit breaker is open for domain"""
        try:
            # Check if circuit breaker exists
            if domain not in self.circuit_breakers:
                return False
            
            # Get circuit breaker
            circuit = self.circuit_breakers[domain]
            
            # Get timestamp
            timestamp = datetime.fromisoformat(circuit['timestamp'])
            
            # Get timeout
            timeout = timedelta(seconds=config.ERROR.circuit_breaker_timeout)
            
            # Check if timeout exceeded
            if datetime.now() - timestamp > timeout:
                # Reset circuit breaker
                del self.circuit_breakers[domain]
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking circuit breaker status: {e}")
            return False
    
    def get_error_stats(self, domain: str) -> Dict:
        """Get error statistics for domain"""
        try:
            # Get error count
            error_count = len(self.errors.get(domain, []))
            
            # Get circuit breaker status
            circuit_open = self.is_circuit_open(domain)
            
            # Get circuit breaker info
            circuit_info = self.circuit_breakers.get(domain, {})
            
            return {
                'domain': domain,
                'error_count': error_count,
                'circuit_open': circuit_open,
                'circuit_info': circuit_info,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting error stats: {e}")
            return {}
    
    def get_all_error_stats(self) -> Dict:
        """Get error statistics for all domains"""
        try:
            return {
                "error_counts": self.error_counts,
                "circuit_breaker": {
                    domain: cb["timestamp"]
                    for domain, cb in self.circuit_breakers.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting all error stats: {e}")
            return {}
    
    def reset_circuit(self, domain: str) -> None:
        """Reset circuit breaker for domain"""
        try:
            # Delete circuit breaker
            if domain in self.circuit_breakers:
                del self.circuit_breakers[domain]
            
            # Clear errors
            if domain in self.errors:
                self.errors[domain] = []
            
        except Exception as e:
            logger.error(f"Error resetting circuit breaker: {e}")
    
    def reset_all_circuits(self) -> None:
        """Reset all circuit breakers"""
        try:
            # Clear circuit breakers
            self.circuit_breakers.clear()
            
            # Clear errors
            self.errors.clear()
            
        except Exception as e:
            logger.error(f"Error resetting all circuit breakers: {e}")
    
    def clear_errors(self, domain: str) -> None:
        """Clear errors for domain"""
        try:
            # Clear errors
            if domain in self.errors:
                self.errors[domain] = []
            
        except Exception as e:
            logger.error(f"Error clearing errors: {e}")
    
    def clear_all_errors(self) -> None:
        """Clear all errors"""
        try:
            # Clear errors
            self.errors.clear()
            
        except Exception as e:
            logger.error(f"Error clearing all errors: {e}")
    
    def get_error_types(self, domain: str) -> Dict[str, int]:
        """Get error types for domain"""
        try:
            # Initialize error types
            error_types = {}
            
            # Count error types
            for error in self.errors.get(domain, []):
                error_type = error['error']
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return error_types
            
        except Exception as e:
            logger.error(f"Error getting error types: {e}")
            return {}
    
    def get_all_error_types(self) -> Dict[str, Dict[str, int]]:
        """Get error types for all domains"""
        try:
            return {
                domain: self.get_error_types(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all error types: {e}")
            return {}
    
    def get_error_timeline(self, domain: str) -> List[Dict]:
        """Get error timeline for domain"""
        try:
            # Get errors
            errors = self.errors.get(domain, [])
            
            # Sort by timestamp
            errors.sort(key=lambda x: x['timestamp'])
            
            return errors
            
        except Exception as e:
            logger.error(f"Error getting error timeline: {e}")
            return []
    
    def get_all_error_timelines(self) -> Dict[str, List[Dict]]:
        """Get error timelines for all domains"""
        try:
            return {
                domain: self.get_error_timeline(domain)
                for domain in config.SITES.keys()
            }
            
        except Exception as e:
            logger.error(f"Error getting all error timelines: {e}")
            return {}
    
    async def can_make_request(self, domain: str) -> bool:
        """Check if we can make a request to domain"""
        return not self.is_circuit_open(domain)
