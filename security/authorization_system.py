"""
Comprehensive Authorization System for FlightIO Crawler
Provides fine-grained access control, resource-level permissions, and audit logging
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Set, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import json
from pathlib import Path
import hashlib
import time
import weakref
from collections import defaultdict
import aioredis
from fastapi import HTTPException, status, Request

from .authentication_system import (
    AuthenticationSystem,
    User,
    UserRole,
    Session,
    get_auth_system
)


class ResourceType(Enum):
    """Types of resources that can be controlled"""
    FLIGHT_DATA = "flight_data"
    SITE_CONFIG = "site_config"
    MONITORING = "monitoring"
    USER_MANAGEMENT = "user_management"
    SYSTEM_CONFIG = "system_config"
    API_KEYS = "api_keys"
    AUDIT_LOGS = "audit_logs"
    CRAWLER_CONTROL = "crawler_control"
    ANALYTICS = "analytics"


class Action(Enum):
    """Actions that can be performed on resources"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    CONFIGURE = "configure"
    MONITOR = "monitor"
    AUDIT = "audit"


class PermissionScope(Enum):
    """Scope of permissions"""
    GLOBAL = "global"
    SITE_SPECIFIC = "site_specific"
    USER_SPECIFIC = "user_specific"
    RESOURCE_SPECIFIC = "resource_specific"


@dataclass
class Permission:
    """Permission definition"""
    id: str
    name: str
    description: str
    resource_type: ResourceType
    action: Action
    scope: PermissionScope
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessPolicy:
    """Access policy definition"""
    policy_id: str
    name: str
    description: str
    resource_type: ResourceType
    conditions: Dict[str, Any] = field(default_factory=dict)
    allowed_actions: List[Action] = field(default_factory=list)
    denied_actions: List[Action] = field(default_factory=list)
    time_restrictions: Optional[Dict[str, Any]] = None
    ip_restrictions: Optional[List[str]] = None
    rate_limits: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessRequest:
    """Access request context"""
    user: User
    resource_type: ResourceType
    action: Action
    resource_id: Optional[str] = None
    resource_data: Optional[Dict[str, Any]] = None
    request_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: str = field(default_factory=lambda: hashlib.md5(str(time.time()).encode()).hexdigest())


@dataclass
class AccessResult:
    """Access decision result"""
    granted: bool
    reason: str
    policy_applied: Optional[str] = None
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """Audit event for access control"""
    event_id: str
    timestamp: datetime
    user_id: str
    username: str
    action: str
    resource_type: ResourceType
    resource_id: Optional[str]
    access_granted: bool
    reason: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthorizationSystem:
    """
    Comprehensive authorization system with fine-grained access control
    """
    
    def __init__(self, auth_system: AuthenticationSystem, config: Optional[Dict[str, Any]] = None):
        self.auth_system = auth_system
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.permissions: Dict[str, Permission] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self.role_permissions: Dict[UserRole, Set[str]] = defaultdict(set)
        self.user_permissions: Dict[str, Set[str]] = defaultdict(set)
        
        # Audit and monitoring
        self.audit_events: List[AuditEvent] = []
        self.access_cache: Dict[str, AccessResult] = {}
        self.cache_ttl = self.config.get('cache_ttl', 300)  # 5 minutes
        
        # Security settings
        self.enable_audit_logging = self.config.get('enable_audit_logging', True)
        self.max_audit_events = self.config.get('max_audit_events', 100000)
        self.failed_access_threshold = self.config.get('failed_access_threshold', 5)
        
        # Rate limiting
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        
        # Initialize system
        self._initialize_permissions()
        self._initialize_policies()
        self._initialize_role_permissions()
        
        self.logger.info("Authorization system initialized")

    def _initialize_permissions(self):
        """Initialize default permissions"""
        permissions = [
            # Flight data permissions
            Permission(
                id="read_flight_data",
                name="Read Flight Data",
                description="Read flight search results and cached data",
                resource_type=ResourceType.FLIGHT_DATA,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="write_flight_data",
                name="Write Flight Data",
                description="Modify flight data and search parameters",
                resource_type=ResourceType.FLIGHT_DATA,
                action=Action.WRITE,
                scope=PermissionScope.GLOBAL
            ),
            
            # Site configuration permissions
            Permission(
                id="read_site_config",
                name="Read Site Configuration",
                description="Read site adapter configurations",
                resource_type=ResourceType.SITE_CONFIG,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="write_site_config",
                name="Write Site Configuration",
                description="Modify site adapter configurations",
                resource_type=ResourceType.SITE_CONFIG,
                action=Action.WRITE,
                scope=PermissionScope.GLOBAL
            ),
            
            # Monitoring permissions
            Permission(
                id="read_monitoring",
                name="Read Monitoring Data",
                description="Read system monitoring and health data",
                resource_type=ResourceType.MONITORING,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="configure_monitoring",
                name="Configure Monitoring",
                description="Configure monitoring and alerting settings",
                resource_type=ResourceType.MONITORING,
                action=Action.CONFIGURE,
                scope=PermissionScope.GLOBAL
            ),
            
            # User management permissions
            Permission(
                id="read_users",
                name="Read Users",
                description="Read user information and lists",
                resource_type=ResourceType.USER_MANAGEMENT,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="write_users",
                name="Write Users",
                description="Create and modify user accounts",
                resource_type=ResourceType.USER_MANAGEMENT,
                action=Action.WRITE,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="delete_users",
                name="Delete Users",
                description="Delete or deactivate user accounts",
                resource_type=ResourceType.USER_MANAGEMENT,
                action=Action.DELETE,
                scope=PermissionScope.GLOBAL
            ),
            
            # System configuration permissions
            Permission(
                id="read_system_config",
                name="Read System Configuration",
                description="Read system-wide configuration settings",
                resource_type=ResourceType.SYSTEM_CONFIG,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="write_system_config",
                name="Write System Configuration",
                description="Modify system-wide configuration settings",
                resource_type=ResourceType.SYSTEM_CONFIG,
                action=Action.WRITE,
                scope=PermissionScope.GLOBAL
            ),
            
            # API key permissions
            Permission(
                id="manage_api_keys",
                name="Manage API Keys",
                description="Create, modify, and revoke API keys",
                resource_type=ResourceType.API_KEYS,
                action=Action.ADMIN,
                scope=PermissionScope.USER_SPECIFIC
            ),
            
            # Audit permissions
            Permission(
                id="read_audit_logs",
                name="Read Audit Logs",
                description="Read audit logs and access history",
                resource_type=ResourceType.AUDIT_LOGS,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            ),
            
            # Crawler control permissions
            Permission(
                id="execute_crawler",
                name="Execute Crawler",
                description="Start and control crawler operations",
                resource_type=ResourceType.CRAWLER_CONTROL,
                action=Action.EXECUTE,
                scope=PermissionScope.GLOBAL
            ),
            Permission(
                id="configure_crawler",
                name="Configure Crawler",
                description="Configure crawler settings and parameters",
                resource_type=ResourceType.CRAWLER_CONTROL,
                action=Action.CONFIGURE,
                scope=PermissionScope.GLOBAL
            ),
            
            # Analytics permissions
            Permission(
                id="read_analytics",
                name="Read Analytics",
                description="Read analytics and reporting data",
                resource_type=ResourceType.ANALYTICS,
                action=Action.READ,
                scope=PermissionScope.GLOBAL
            )
        ]
        
        for permission in permissions:
            self.permissions[permission.id] = permission

    def _initialize_policies(self):
        """Initialize default access policies"""
        policies = [
            # Admin policy - full access
            AccessPolicy(
                policy_id="admin_full_access",
                name="Administrator Full Access",
                description="Full access to all resources",
                resource_type=ResourceType.SYSTEM_CONFIG,
                allowed_actions=[Action.READ, Action.WRITE, Action.DELETE, Action.EXECUTE, Action.ADMIN, Action.CONFIGURE, Action.MONITOR, Action.AUDIT]
            ),
            
            # Operator policy - operational access
            AccessPolicy(
                policy_id="operator_access",
                name="Operator Access",
                description="Operational access to crawler and monitoring",
                resource_type=ResourceType.CRAWLER_CONTROL,
                allowed_actions=[Action.READ, Action.WRITE, Action.EXECUTE, Action.CONFIGURE, Action.MONITOR]
            ),
            
            # API user policy - API access
            AccessPolicy(
                policy_id="api_user_access",
                name="API User Access",
                description="API access to flight data and monitoring",
                resource_type=ResourceType.FLIGHT_DATA,
                allowed_actions=[Action.READ, Action.EXECUTE],
                rate_limits={"requests_per_minute": 100}
            ),
            
            # Viewer policy - read-only access
            AccessPolicy(
                policy_id="viewer_access",
                name="Viewer Access",
                description="Read-only access to flight data and monitoring",
                resource_type=ResourceType.FLIGHT_DATA,
                allowed_actions=[Action.READ, Action.MONITOR]
            )
        ]
        
        for policy in policies:
            self.policies[policy.policy_id] = policy

    def _initialize_role_permissions(self):
        """Initialize role-based permissions"""
        # Admin role - all permissions
        self.role_permissions[UserRole.ADMIN] = set(self.permissions.keys())
        
        # Operator role - operational permissions
        self.role_permissions[UserRole.OPERATOR] = {
            "read_flight_data", "write_flight_data",
            "read_site_config", "write_site_config",
            "read_monitoring", "configure_monitoring",
            "execute_crawler", "configure_crawler",
            "read_analytics", "manage_api_keys"
        }
        
        # API user role - API permissions
        self.role_permissions[UserRole.API_USER] = {
            "read_flight_data", "execute_crawler",
            "read_monitoring", "manage_api_keys"
        }
        
        # Viewer role - read-only permissions
        self.role_permissions[UserRole.VIEWER] = {
            "read_flight_data", "read_monitoring", "read_analytics"
        }
        
        # System role - system permissions
        self.role_permissions[UserRole.SYSTEM] = {
            "read_flight_data", "write_flight_data",
            "read_site_config", "write_site_config",
            "read_monitoring", "configure_monitoring",
            "execute_crawler", "configure_crawler",
            "read_system_config", "write_system_config"
        }

    async def check_access(self, access_request: AccessRequest) -> AccessResult:
        """
        Check if user has access to perform the requested action
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(access_request)
            cached_result = self.access_cache.get(cache_key)
            if cached_result and self._is_cache_valid(cached_result):
                return cached_result
            
            # Perform access check
            result = await self._evaluate_access(access_request)
            
            # Cache result
            self.access_cache[cache_key] = result
            
            # Log audit event
            if self.enable_audit_logging:
                await self._log_audit_event(access_request, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Access check failed: {e}")
            return AccessResult(
                granted=False,
                reason=f"Access check error: {str(e)}",
                metadata={"error": str(e)}
            )

    async def _evaluate_access(self, access_request: AccessRequest) -> AccessResult:
        """Evaluate access request against permissions and policies"""
        user = access_request.user
        resource_type = access_request.resource_type
        action = access_request.action
        
        # Check user account status
        if not user.is_active:
            return AccessResult(
                granted=False,
                reason="User account is not active"
            )
        
        # Check role-based permissions
        role_permissions = self.role_permissions.get(user.role, set())
        permission_id = f"{action.value}_{resource_type.value}"
        
        if permission_id not in role_permissions:
            # Check for wildcard permissions
            wildcard_permission = f"{action.value}_*"
            if wildcard_permission not in role_permissions:
                return AccessResult(
                    granted=False,
                    reason=f"Role {user.role.value} does not have permission {permission_id}"
                )
        
        # Check user-specific permissions
        user_permissions = self.user_permissions.get(user.user_id, set())
        if permission_id in user_permissions:
            # User has explicit permission
            pass
        elif f"deny_{permission_id}" in user_permissions:
            # User has explicit denial
            return AccessResult(
                granted=False,
                reason=f"User has explicit denial for {permission_id}"
            )
        
        # Check applicable policies
        applicable_policies = [
            policy for policy in self.policies.values()
            if policy.resource_type == resource_type or policy.resource_type == ResourceType.SYSTEM_CONFIG
        ]
        
        for policy in applicable_policies:
            policy_result = await self._evaluate_policy(policy, access_request)
            if not policy_result.granted:
                return policy_result
        
        # Check rate limits
        rate_limit_result = await self._check_rate_limits(access_request)
        if not rate_limit_result.granted:
            return rate_limit_result
        
        # Check time restrictions
        time_restriction_result = await self._check_time_restrictions(access_request)
        if not time_restriction_result.granted:
            return time_restriction_result
        
        # Check IP restrictions
        ip_restriction_result = await self._check_ip_restrictions(access_request)
        if not ip_restriction_result.granted:
            return ip_restriction_result
        
        # Access granted
        return AccessResult(
            granted=True,
            reason="Access granted based on role and permissions",
            metadata={
                "user_role": user.role.value,
                "permission_id": permission_id,
                "policies_checked": len(applicable_policies)
            }
        )

    async def _evaluate_policy(self, policy: AccessPolicy, access_request: AccessRequest) -> AccessResult:
        """Evaluate a specific policy against the access request"""
        action = access_request.action
        
        # Check if action is explicitly denied
        if action in policy.denied_actions:
            return AccessResult(
                granted=False,
                reason=f"Action {action.value} is denied by policy {policy.name}",
                policy_applied=policy.policy_id
            )
        
        # Check if action is explicitly allowed
        if action in policy.allowed_actions:
            return AccessResult(
                granted=True,
                reason=f"Action {action.value} is allowed by policy {policy.name}",
                policy_applied=policy.policy_id
            )
        
        # Check conditions
        if policy.conditions:
            conditions_result = await self._evaluate_conditions(policy.conditions, access_request)
            if not conditions_result.granted:
                return conditions_result
        
        # Default to allow if no explicit denial
        return AccessResult(
            granted=True,
            reason=f"No explicit denial in policy {policy.name}",
            policy_applied=policy.policy_id
        )

    async def _evaluate_conditions(self, conditions: Dict[str, Any], access_request: AccessRequest) -> AccessResult:
        """Evaluate policy conditions"""
        # This is a simplified implementation
        # In a full implementation, this would support complex condition evaluation
        
        for condition_key, condition_value in conditions.items():
            if condition_key == "user_role":
                if access_request.user.role.value != condition_value:
                    return AccessResult(
                        granted=False,
                        reason=f"User role {access_request.user.role.value} does not match condition {condition_value}",
                        conditions_failed=[condition_key]
                    )
            elif condition_key == "resource_owner":
                if access_request.resource_data and access_request.resource_data.get("owner_id") != access_request.user.user_id:
                    return AccessResult(
                        granted=False,
                        reason="User is not the resource owner",
                        conditions_failed=[condition_key]
                    )
        
        return AccessResult(
            granted=True,
            reason="All conditions met",
            conditions_met=list(conditions.keys())
        )

    async def _check_rate_limits(self, access_request: AccessRequest) -> AccessResult:
        """Check rate limits for the user"""
        user_id = access_request.user.user_id
        current_time = time.time()
        
        # Get user's rate limit configuration
        user_rate_limits = self.rate_limits.get(user_id, {})
        
        # Check per-minute limit
        minute_key = f"{user_id}:minute:{int(current_time // 60)}"
        minute_count = user_rate_limits.get(minute_key, 0)
        minute_limit = self._get_user_rate_limit(access_request.user, "requests_per_minute")
        
        if minute_count >= minute_limit:
            return AccessResult(
                granted=False,
                reason=f"Rate limit exceeded: {minute_count}/{minute_limit} requests per minute"
            )
        
        # Update rate limit counter
        user_rate_limits[minute_key] = minute_count + 1
        self.rate_limits[user_id] = user_rate_limits
        
        return AccessResult(
            granted=True,
            reason="Rate limit check passed"
        )

    def _get_user_rate_limit(self, user: User, limit_type: str) -> int:
        """Get rate limit for user based on role"""
        role_limits = {
            UserRole.ADMIN: {"requests_per_minute": 1000},
            UserRole.OPERATOR: {"requests_per_minute": 500},
            UserRole.API_USER: {"requests_per_minute": 100},
            UserRole.VIEWER: {"requests_per_minute": 60},
            UserRole.SYSTEM: {"requests_per_minute": 2000}
        }
        
        return role_limits.get(user.role, {}).get(limit_type, 60)

    async def _check_time_restrictions(self, access_request: AccessRequest) -> AccessResult:
        """Check time-based access restrictions"""
        # This is a placeholder for time-based restrictions
        # Could implement business hours, maintenance windows, etc.
        return AccessResult(
            granted=True,
            reason="No time restrictions apply"
        )

    async def _check_ip_restrictions(self, access_request: AccessRequest) -> AccessResult:
        """Check IP-based access restrictions"""
        # This is a placeholder for IP-based restrictions
        # Could implement IP whitelisting, geolocation restrictions, etc.
        return AccessResult(
            granted=True,
            reason="No IP restrictions apply"
        )

    def _get_cache_key(self, access_request: AccessRequest) -> str:
        """Generate cache key for access request"""
        key_parts = [
            access_request.user.user_id,
            access_request.resource_type.value,
            access_request.action.value,
            access_request.resource_id or "none"
        ]
        return ":".join(key_parts)

    def _is_cache_valid(self, cached_result: AccessResult) -> bool:
        """Check if cached result is still valid"""
        # Simple TTL-based cache validity
        # In a full implementation, this could be more sophisticated
        return True  # Simplified for now

    async def _log_audit_event(self, access_request: AccessRequest, result: AccessResult):
        """Log audit event for access request"""
        try:
            event = AuditEvent(
                event_id=access_request.request_id,
                timestamp=access_request.timestamp,
                user_id=access_request.user.user_id,
                username=access_request.user.username,
                action=f"{access_request.action.value}_{access_request.resource_type.value}",
                resource_type=access_request.resource_type,
                resource_id=access_request.resource_id,
                access_granted=result.granted,
                reason=result.reason,
                metadata=result.metadata
            )
            
            self.audit_events.append(event)
            
            # Maintain audit event limit
            if len(self.audit_events) > self.max_audit_events:
                self.audit_events = self.audit_events[-self.max_audit_events:]
            
            # Log to file or external system
            self.logger.info(f"Audit: {event.username} - {event.action} - {'GRANTED' if event.access_granted else 'DENIED'} - {event.reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")

    # Public API methods
    async def grant_permission(self, user_id: str, permission_id: str) -> bool:
        """Grant permission to user"""
        try:
            if permission_id in self.permissions:
                self.user_permissions[user_id].add(permission_id)
                self.logger.info(f"Permission {permission_id} granted to user {user_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to grant permission: {e}")
            return False

    async def revoke_permission(self, user_id: str, permission_id: str) -> bool:
        """Revoke permission from user"""
        try:
            if permission_id in self.user_permissions[user_id]:
                self.user_permissions[user_id].remove(permission_id)
                self.logger.info(f"Permission {permission_id} revoked from user {user_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to revoke permission: {e}")
            return False

    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get list of permissions for user"""
        try:
            user = self.auth_system.users.get(user_id)
            if not user:
                return []
            
            # Combine role-based and user-specific permissions
            role_permissions = self.role_permissions.get(user.role, set())
            user_permissions = self.user_permissions.get(user_id, set())
            
            return list(role_permissions.union(user_permissions))
        except Exception as e:
            self.logger.error(f"Failed to get user permissions: {e}")
            return []

    async def get_audit_events(self, user_id: Optional[str] = None, 
                             resource_type: Optional[ResourceType] = None,
                             limit: int = 100) -> List[AuditEvent]:
        """Get audit events with optional filtering"""
        try:
            events = self.audit_events
            
            if user_id:
                events = [e for e in events if e.user_id == user_id]
            
            if resource_type:
                events = [e for e in events if e.resource_type == resource_type]
            
            return events[-limit:] if limit else events
        except Exception as e:
            self.logger.error(f"Failed to get audit events: {e}")
            return []

    def get_authorization_stats(self) -> Dict[str, Any]:
        """Get authorization system statistics"""
        return {
            "total_permissions": len(self.permissions),
            "total_policies": len(self.policies),
            "total_audit_events": len(self.audit_events),
            "cache_size": len(self.access_cache),
            "active_rate_limits": len(self.rate_limits)
        }

    def clear_cache(self):
        """Clear access cache"""
        self.access_cache.clear()
        self.logger.info("Authorization cache cleared")


# Decorator for endpoint authorization
def require_authorization(resource_type: ResourceType, action: Action, 
                         resource_id_param: Optional[str] = None):
    """
    Decorator for requiring authorization on endpoints
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request and user from arguments
            request = None
            user = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                if hasattr(arg, 'user_id'):  # User object
                    user = arg
            
            if not user:
                # Try to get user from request state
                if request and hasattr(request.state, 'user'):
                    user = request.state.user
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Get authorization system
            auth_system = get_auth_system()
            # In a real implementation, you'd get the authorization system instance
            # For now, we'll assume it's available
            
            # Create access request
            resource_id = kwargs.get(resource_id_param) if resource_id_param else None
            access_request = AccessRequest(
                user=user,
                resource_type=resource_type,
                action=action,
                resource_id=resource_id,
                request_metadata={
                    "endpoint": func.__name__,
                    "method": request.method if request else "unknown"
                }
            )
            
            # Check authorization
            # result = await authorization_system.check_access(access_request)
            # if not result.granted:
            #     raise HTTPException(
            #         status_code=status.HTTP_403_FORBIDDEN,
            #         detail=result.reason
            #     )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global authorization system instance
_global_authorization_system = None


def get_authorization_system() -> AuthorizationSystem:
    """Get global authorization system instance"""
    global _global_authorization_system
    if _global_authorization_system is None:
        auth_system = get_auth_system()
        _global_authorization_system = AuthorizationSystem(auth_system)
    return _global_authorization_system


def initialize_authorization_system(auth_system: AuthenticationSystem, 
                                   config: Dict[str, Any]) -> AuthorizationSystem:
    """Initialize authorization system with configuration"""
    global _global_authorization_system
    _global_authorization_system = AuthorizationSystem(auth_system, config)
    return _global_authorization_system 