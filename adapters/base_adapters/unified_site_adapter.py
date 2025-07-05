"""
Unified Site Adapter Base Class
Standardizes all site adapters with enhanced features and consistent interface
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from abc import abstractmethod
from pathlib import Path
import json

from .enhanced_crawler_base import EnhancedCrawlerBase
from .enhanced_error_handler import (
    EnhancedErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorAction,
    ErrorContext,
    error_handler_decorator,
    get_global_error_handler
)
from ..patterns.builder_pattern import AdapterConfigBuilder
from monitoring.enhanced_monitoring_system import EnhancedMonitoringSystem
from security.data_encryption import DataEncryptionSystem, DataClassification
from security.authorization_system import AuthorizationSystem, ResourceType, Action
from enhanced_rate_limiter import EnhancedRateLimiter


class UnifiedSiteAdapter(EnhancedCrawlerBase):
    """
    Unified base class for all site adapters with standardized features:
    
    - Enhanced error handling with automatic recovery
    - Comprehensive monitoring and metrics
    - Data encryption for sensitive information
    - Authorization and access control
    - Rate limiting integration
    - Standardized configuration management
    - Performance optimization
    - Audit logging
    """
    
    def __init__(self, site_name: str, config: Dict[str, Any]):
        # Initialize with enhanced base crawler
        super().__init__(config)
        
        self.site_name = site_name
        self.adapter_name = f"{site_name}_adapter"
        self.logger = logging.getLogger(f"adapter.{site_name}")
        
        # Enhanced components
        self.error_handler = get_global_error_handler()
        self.monitoring_system: Optional[EnhancedMonitoringSystem] = None
        self.encryption_system: Optional[DataEncryptionSystem] = None
        self.authorization_system: Optional[AuthorizationSystem] = None
        self.rate_limiter: Optional[EnhancedRateLimiter] = None
        
        # Site-specific configuration
        self.site_config = config
        self.base_url = config.get('base_url', '')
        self.search_url = config.get('search_url', '')
        
        # Performance metrics
        self.performance_metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'average_response_time': 0.0,
            'last_request_time': None,
            'total_flights_extracted': 0,
            'extraction_rate': 0.0
        }
        
        # Security and compliance
        self.data_classification = DataClassification.CONFIDENTIAL
        self.required_permissions = [f"read_{site_name}", f"execute_crawler"]
        
        # Initialize components
        self._initialize_enhanced_components()
        
        self.logger.info(f"Unified {site_name} adapter initialized")

    def _initialize_enhanced_components(self):
        """Initialize enhanced components"""
        try:
            # Initialize monitoring
            from monitoring.enhanced_monitoring_system import get_global_monitoring
            self.monitoring_system = get_global_monitoring()
            
            # Initialize encryption
            from security.data_encryption import get_encryption_system
            self.encryption_system = get_encryption_system()
            
            # Initialize authorization
            from security.authorization_system import get_authorization_system
            self.authorization_system = get_authorization_system()
            
            # Initialize rate limiter
            self.rate_limiter = EnhancedRateLimiter()
            
            # Register with monitoring
            if self.monitoring_system:
                self.monitoring_system.register_component(
                    self.adapter_name,
                    self
                )
            
            self.logger.debug("Enhanced components initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced components: {e}")

    @error_handler_decorator(
        operation_name="crawl_flights",
        category=ErrorCategory.CRAWLER_CONTROL,
        severity=ErrorSeverity.HIGH,
        max_retries=3
    )
    async def crawl_flights(self, search_params: Dict[str, Any], 
                           user_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Enhanced flight crawling with comprehensive error handling and monitoring
        """
        start_time = datetime.now()
        
        try:
            # Validate authorization
            if user_context and self.authorization_system:
                await self._check_authorization(user_context, Action.EXECUTE)
            
            # Apply rate limiting
            if self.rate_limiter:
                await self._apply_rate_limiting()
            
            # Validate search parameters
            validated_params = await self._validate_and_sanitize_params(search_params)
            
            # Execute crawling with monitoring
            results = await self._execute_crawling_with_monitoring(validated_params)
            
            # Process and validate results
            processed_results = await self._process_and_validate_results(results)
            
            # Update performance metrics
            await self._update_performance_metrics(start_time, len(processed_results), True)
            
            # Log successful operation
            self.logger.info(
                f"Successfully crawled {len(processed_results)} flights from {self.site_name} "
                f"in {(datetime.now() - start_time).total_seconds():.2f}s"
            )
            
            return processed_results
            
        except Exception as e:
            # Update failure metrics
            await self._update_performance_metrics(start_time, 0, False)
            
            # Enhanced error context
            error_context = ErrorContext(
                adapter_name=self.adapter_name,
                operation="crawl_flights",
                url=self.search_url,
                search_params=search_params,
                additional_info={
                    "site_name": self.site_name,
                    "user_context": user_context
                }
            )
            
            # Let enhanced error handler manage the error
            await self.error_handler.handle_error(
                e, error_context, ErrorSeverity.HIGH, ErrorCategory.CRAWLER_CONTROL
            )
            
            raise

    async def _check_authorization(self, user_context: Dict[str, Any], action: Action):
        """Check user authorization for the operation"""
        try:
            if not self.authorization_system:
                return  # Skip if authorization not configured
            
            from security.authorization_system import AccessRequest, ResourceType
            from security.authentication_system import User
            
            # Create user from context (simplified)
            user = user_context.get('user')
            if not user:
                raise PermissionError("User context required for authorization")
            
            # Create access request
            access_request = AccessRequest(
                user=user,
                resource_type=ResourceType.CRAWLER_CONTROL,
                action=action,
                resource_id=self.site_name
            )
            
            # Check access
            result = await self.authorization_system.check_access(access_request)
            if not result.granted:
                raise PermissionError(f"Access denied: {result.reason}")
                
        except Exception as e:
            self.logger.error(f"Authorization check failed: {e}")
            raise

    async def _apply_rate_limiting(self):
        """Apply rate limiting for the site"""
        try:
            if not self.rate_limiter:
                return
            
            site_id = self.rate_limiter.get_site_id_from_url(self.base_url)
            can_proceed, reason = self.rate_limiter.can_make_request(site_id)
            
            if not can_proceed:
                wait_time = self.rate_limiter.wait_for_rate_limit(site_id)
                self.logger.info(f"Rate limit applied for {self.site_name}: waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            
            # Record the request
            self.rate_limiter.record_request(site_id, True)
            
        except Exception as e:
            self.logger.error(f"Rate limiting failed: {e}")

    async def _validate_and_sanitize_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize search parameters"""
        try:
            # Basic validation
            required_fields = self._get_required_search_fields()
            for field in required_fields:
                if field not in search_params:
                    raise ValueError(f"Required field missing: {field}")
            
            # Sanitize parameters
            sanitized_params = {}
            for key, value in search_params.items():
                if isinstance(value, str):
                    # Basic sanitization
                    sanitized_value = value.strip()
                    if key in ['origin', 'destination']:
                        sanitized_value = sanitized_value.upper()[:3]  # Airport codes
                    elif key in ['departure_date', 'return_date']:
                        # Validate date format
                        try:
                            datetime.strptime(sanitized_value, '%Y-%m-%d')
                        except ValueError:
                            raise ValueError(f"Invalid date format for {key}: {sanitized_value}")
                    sanitized_params[key] = sanitized_value
                else:
                    sanitized_params[key] = value
            
            # Site-specific validation
            await self._validate_site_specific_params(sanitized_params)
            
            return sanitized_params
            
        except Exception as e:
            self.logger.error(f"Parameter validation failed: {e}")
            raise

    async def _execute_crawling_with_monitoring(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute crawling with comprehensive monitoring"""
        try:
            # Record crawling start
            if self.monitoring_system:
                await self.monitoring_system.record_metric(
                    f"{self.adapter_name}_crawl_start",
                    1,
                    labels={"site": self.site_name, "status": "started"}
                )
            
            # Execute the actual crawling
            results = await self._perform_site_crawling(search_params)
            
            # Record success
            if self.monitoring_system:
                await self.monitoring_system.record_crawl_metrics(
                    self.adapter_name,
                    (datetime.now() - datetime.now()).total_seconds(),  # This would be calculated properly
                    True,
                    len(results)
                )
            
            return results
            
        except Exception as e:
            # Record failure
            if self.monitoring_system:
                await self.monitoring_system.record_crawl_metrics(
                    self.adapter_name,
                    0,
                    False,
                    0,
                    type(e).__name__
                )
            raise

    async def _perform_site_crawling(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform the actual site crawling - calls the existing crawl method"""
        return await super().crawl(search_params)

    async def _process_and_validate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate crawling results"""
        try:
            processed_results = []
            
            for result in results:
                # Validate flight data
                if self._validate_flight_data(result):
                    # Standardize fields
                    standardized_result = await self._standardize_flight_data(result)
                    
                    # Encrypt sensitive data if needed
                    encrypted_result = await self._encrypt_sensitive_data(standardized_result)
                    
                    processed_results.append(encrypted_result)
                else:
                    self.logger.warning(f"Invalid flight data discarded: {result}")
            
            self.logger.info(f"Processed {len(processed_results)} valid flights from {len(results)} raw results")
            return processed_results
            
        except Exception as e:
            self.logger.error(f"Result processing failed: {e}")
            raise

    async def _standardize_flight_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize flight data format"""
        try:
            standardized = {
                # Required fields with defaults
                'flight_number': flight_data.get('flight_number', ''),
                'airline': flight_data.get('airline', ''),
                'origin': flight_data.get('origin', ''),
                'destination': flight_data.get('destination', ''),
                'departure_time': flight_data.get('departure_time', ''),
                'arrival_time': flight_data.get('arrival_time', ''),
                'price': flight_data.get('price', 0.0),
                'currency': flight_data.get('currency', 'USD'),
                'duration': flight_data.get('duration', ''),
                'stops': flight_data.get('stops', 0),
                'aircraft': flight_data.get('aircraft', ''),
                'cabin_class': flight_data.get('cabin_class', 'Economy'),
                
                # Metadata
                'source_site': self.site_name,
                'extracted_at': datetime.now().isoformat(),
                'adapter_version': self._get_adapter_version(),
                
                # Raw data for debugging
                'raw_data': flight_data if self.config.get('include_raw_data', False) else None
            }
            
            # Site-specific standardization
            await self._apply_site_specific_standardization(standardized, flight_data)
            
            return standardized
            
        except Exception as e:
            self.logger.error(f"Data standardization failed: {e}")
            return flight_data  # Return original data on failure

    async def _encrypt_sensitive_data(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive data fields"""
        try:
            if not self.encryption_system:
                return flight_data
            
            # Fields that might contain sensitive information
            sensitive_fields = ['passenger_details', 'payment_info', 'personal_data']
            
            for field in sensitive_fields:
                if field in flight_data and flight_data[field]:
                    encrypted_data = await self.encryption_system.encrypt_json(
                        flight_data[field],
                        self.data_classification
                    )
                    flight_data[f"{field}_encrypted"] = encrypted_data
                    del flight_data[field]  # Remove original data
            
            return flight_data
            
        except Exception as e:
            self.logger.error(f"Data encryption failed: {e}")
            return flight_data  # Return original data on failure

    async def _update_performance_metrics(self, start_time: datetime, results_count: int, success: bool):
        """Update performance metrics"""
        try:
            duration = (datetime.now() - start_time).total_seconds()
            
            self.performance_metrics['total_requests'] += 1
            if success:
                self.performance_metrics['successful_requests'] += 1
                self.performance_metrics['total_flights_extracted'] += results_count
            else:
                self.performance_metrics['failed_requests'] += 1
            
            # Update average response time
            total_requests = self.performance_metrics['total_requests']
            current_avg = self.performance_metrics['average_response_time']
            self.performance_metrics['average_response_time'] = (
                (current_avg * (total_requests - 1) + duration) / total_requests
            )
            
            # Update extraction rate
            if self.performance_metrics['total_requests'] > 0:
                self.performance_metrics['extraction_rate'] = (
                    self.performance_metrics['total_flights_extracted'] / 
                    self.performance_metrics['total_requests']
                )
            
            self.performance_metrics['last_request_time'] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"Metrics update failed: {e}")

    # Abstract methods that must be implemented by site-specific adapters
    @abstractmethod
    async def _validate_site_specific_params(self, params: Dict[str, Any]):
        """Validate site-specific parameters"""
        pass

    @abstractmethod
    async def _apply_site_specific_standardization(self, standardized: Dict[str, Any], raw: Dict[str, Any]):
        """Apply site-specific data standardization"""
        pass

    def _get_adapter_version(self) -> str:
        """Get adapter version"""
        return self.config.get('version', '1.0.0')

    # Missing utility methods implementation
    def _validate_flight_data(self, flight_data: Dict[str, Any]) -> bool:
        """Validate individual flight data"""
        try:
            # Check required fields
            required_fields = self.config.get('data_validation', {}).get('required_fields', [
                'airline', 'price', 'departure_time', 'arrival_time'
            ])
            
            for field in required_fields:
                if field not in flight_data or not flight_data[field]:
                    self.logger.debug(f"Missing required field: {field}")
                    return False
            
            # Check price range
            if 'price' in flight_data:
                try:
                    price = float(flight_data['price'])
                    price_range = self.config.get('data_validation', {}).get('price_range', {
                        'min': 0, 'max': 100000
                    })
                    if not (price_range['min'] <= price <= price_range['max']):
                        self.logger.debug(f"Price out of range: {price}")
                        return False
                except (ValueError, TypeError):
                    self.logger.debug(f"Invalid price format: {flight_data['price']}")
                    return False
            
            # Check duration range
            if 'duration_minutes' in flight_data:
                try:
                    duration = int(flight_data['duration_minutes'])
                    duration_range = self.config.get('data_validation', {}).get('duration_range', {
                        'min': 0, 'max': 24 * 60  # 24 hours max
                    })
                    if not (duration_range['min'] <= duration <= duration_range['max']):
                        self.logger.debug(f"Duration out of range: {duration}")
                        return False
                except (ValueError, TypeError):
                    self.logger.debug(f"Invalid duration format: {flight_data['duration_minutes']}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Flight data validation error: {e}")
            return False

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics from the error handler"""
        try:
            if hasattr(self, 'error_handler') and self.error_handler:
                return self.error_handler.get_error_statistics()
            return {
                'total_errors': 0,
                'error_by_category': {},
                'error_by_severity': {},
                'recent_errors': [],
                'circuit_breakers': {}
            }
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    def reset_error_statistics(self):
        """Reset error statistics"""
        try:
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.reset_error_statistics()
            self.logger.info(f"Error statistics reset for {self.adapter_name}")
        except Exception as e:
            self.logger.error(f"Error resetting statistics: {e}")

    def _get_required_search_fields(self) -> List[str]:
        """Get required search fields for this adapter"""
        return self.config.get('required_search_fields', [
            'origin', 'destination', 'departure_date', 'passengers'
        ])

    # Enhanced utility methods
    async def get_adapter_health(self) -> Dict[str, Any]:
        """Get comprehensive adapter health status"""
        try:
            health_status = {
                'adapter_name': self.adapter_name,
                'site_name': self.site_name,
                'status': 'healthy',
                'last_check': datetime.now().isoformat(),
                'performance_metrics': self.performance_metrics.copy(),
                'error_statistics': self.get_error_statistics(),
                'components': {
                    'error_handler': self.error_handler is not None,
                    'monitoring_system': self.monitoring_system is not None,
                    'encryption_system': self.encryption_system is not None,
                    'authorization_system': self.authorization_system is not None,
                    'rate_limiter': self.rate_limiter is not None
                }
            }
            
            # Check component health
            if self.monitoring_system:
                health_status['monitoring_status'] = await self.monitoring_system.get_monitoring_summary()
            
            # Check rate limiting status
            if self.rate_limiter:
                site_id = self.rate_limiter.get_site_id_from_url(self.base_url)
                health_status['rate_limit_status'] = self.rate_limiter.get_rate_limit_info(site_id)
            
            # Determine overall health
            success_rate = (
                self.performance_metrics['successful_requests'] / 
                max(self.performance_metrics['total_requests'], 1)
            )
            
            if success_rate < 0.5:
                health_status['status'] = 'unhealthy'
            elif success_rate < 0.8:
                health_status['status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                'adapter_name': self.adapter_name,
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }

    async def reset_adapter_metrics(self):
        """Reset adapter performance metrics"""
        try:
            self.performance_metrics = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'average_response_time': 0.0,
                'last_request_time': None,
                'total_flights_extracted': 0,
                'extraction_rate': 0.0
            }
            
            # Reset error statistics
            self.reset_error_statistics()
            
            self.logger.info(f"Metrics reset for {self.adapter_name}")
            
        except Exception as e:
            self.logger.error(f"Metrics reset failed: {e}")

    def get_adapter_config(self) -> Dict[str, Any]:
        """Get sanitized adapter configuration"""
        try:
            # Return configuration without sensitive data
            sanitized_config = self.site_config.copy()
            
            # Remove sensitive fields
            sensitive_fields = ['api_key', 'password', 'secret', 'token']
            for field in sensitive_fields:
                if field in sanitized_config:
                    sanitized_config[field] = '[ENCRYPTED]'
            
            return sanitized_config
            
        except Exception as e:
            self.logger.error(f"Config retrieval failed: {e}")
            return {}

    async def update_adapter_config(self, new_config: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None):
        """Update adapter configuration with authorization check"""
        try:
            # Check authorization
            if user_context and self.authorization_system:
                await self._check_authorization(user_context, Action.CONFIGURE)
            
            # Validate configuration
            validated_config = await self._validate_config_update(new_config)
            
            # Update configuration
            self.site_config.update(validated_config)
            
            # Reinitialize components if needed
            if 'rate_limiting' in validated_config:
                self._initialize_enhanced_components()
            
            self.logger.info(f"Configuration updated for {self.adapter_name}")
            
        except Exception as e:
            self.logger.error(f"Configuration update failed: {e}")
            raise

    async def _validate_config_update(self, config_update: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration update"""
        # This would implement proper configuration validation
        # For now, just return the update
        return config_update

    async def cleanup(self):
        """Clean up adapter resources"""
        try:
            await super().close()
            
            # Additional cleanup for enhanced components
            if self.rate_limiter:
                self.rate_limiter.cleanup()
            
            self.logger.info(f"Adapter {self.adapter_name} cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Factory function for creating unified adapters
def create_unified_adapter(site_name: str, config: Dict[str, Any]) -> UnifiedSiteAdapter:
    """
    Factory function to create unified site adapters
    """
    # Load site-specific configuration
    config_path = Path(f"config/site_configs/{site_name}.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            site_config = json.load(f)
        config.update(site_config)
    
    return UnifiedSiteAdapter(site_name, config) 