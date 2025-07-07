"""
FastAPI Authentication Middleware Integration
Provides seamless authentication and authorization for API endpoints
"""

from fastapi import FastAPI, Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any, Callable
import logging
import time
from datetime import datetime
import jwt
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
import aioredis

from .authentication_system import (
    AuthenticationSystem,
    User,
    UserRole,
    PermissionLevel,
    get_auth_system,
    get_current_user,
    require_role,
    require_permission
)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for handling authentication and authorization
    """
    
    def __init__(self, app: FastAPI, auth_system: AuthenticationSystem):
        super().__init__(app)
        self.auth_system = auth_system
        self.logger = logging.getLogger(__name__)
        
        # Public endpoints that don't require authentication
        self.public_endpoints = {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/favicon.ico"
        }
        
        # API endpoints that require API key authentication
        self.api_key_endpoints = {
            "/api/v1/flights/search",
            "/api/v1/flights/batch",
            "/api/v1/sites/status"
        }
        
        # Admin endpoints that require admin role
        self.admin_endpoints = {
            "/api/v1/admin/users",
            "/api/v1/admin/system",
            "/api/v1/admin/monitoring",
            "/api/v1/admin/config"
        }
        
        self.logger.info("Authentication middleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication and authorization"""
        start_time = time.time()
        
        try:
            # Check if endpoint is public
            if self._is_public_endpoint(request.url.path):
                response = await call_next(request)
                return response
            
            # Extract and validate authentication
            auth_result = await self._authenticate_request(request)
            
            if not auth_result["success"]:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": auth_result["error"],
                        "error_code": "AUTHENTICATION_FAILED"
                    }
                )
            
            # Add user to request state
            request.state.user = auth_result["user"]
            request.state.auth_method = auth_result["auth_method"]
            
            # Check authorization
            if not await self._authorize_request(request):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "Insufficient permissions",
                        "error_code": "AUTHORIZATION_FAILED"
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            processing_time = time.time() - start_time
            self.logger.info(
                f"Request processed - User: {auth_result['user'].username}, "
                f"Method: {request.method}, Path: {request.url.path}, "
                f"Time: {processing_time:.3f}s"
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal authentication error",
                    "error_code": "AUTHENTICATION_ERROR"
                }
            )

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        return any(path.startswith(endpoint) for endpoint in self.public_endpoints)

    async def _authenticate_request(self, request: Request) -> Dict[str, Any]:
        """Authenticate request using JWT token or API key"""
        try:
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return {"success": False, "error": "Missing authorization header"}
            
            # Handle Bearer token
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    # Verify JWT token
                    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
                    user = await self.auth_system.verify_token(credentials)
                    return {
                        "success": True,
                        "user": user,
                        "auth_method": "jwt_token"
                    }
                except HTTPException as e:
                    return {"success": False, "error": str(e.detail)}
            
            # Handle API key
            elif auth_header.startswith("ApiKey "):
                api_key = auth_header.split(" ")[1]
                try:
                    user = await self.auth_system.authenticate_api_key(api_key)
                    return {
                        "success": True,
                        "user": user,
                        "auth_method": "api_key"
                    }
                except HTTPException as e:
                    return {"success": False, "error": str(e.detail)}
            
            return {"success": False, "error": "Invalid authorization format"}
            
        except Exception as e:
            return {"success": False, "error": f"Authentication failed: {str(e)}"}

    async def _authorize_request(self, request: Request) -> bool:
        """Check if user has permission to access endpoint"""
        try:
            user: User = request.state.user
            path = request.url.path
            method = request.method
            
            # Admin endpoints require admin role
            if self._is_admin_endpoint(path):
                return user.role == UserRole.ADMIN
            
            # API key endpoints have specific permissions
            if self._is_api_key_endpoint(path):
                required_permissions = self._get_required_permissions(path, method)
                return all(
                    self.auth_system.check_permission(user, perm) 
                    for perm in required_permissions
                )
            
            # Default access control
            return self._check_default_access(user, path, method)
            
        except Exception as e:
            self.logger.error(f"Authorization check failed: {e}")
            return False

    def _is_admin_endpoint(self, path: str) -> bool:
        """Check if endpoint requires admin access"""
        return any(path.startswith(endpoint) for endpoint in self.admin_endpoints)

    def _is_api_key_endpoint(self, path: str) -> bool:
        """Check if endpoint is API key accessible"""
        return any(path.startswith(endpoint) for endpoint in self.api_key_endpoints)

    def _get_required_permissions(self, path: str, method: str) -> List[str]:
        """Get required permissions for endpoint"""
        permissions = []
        
        if "/flights/" in path:
            if method == "GET":
                permissions.append("read:flights")
            elif method == "POST":
                permissions.append("write:crawl")
        
        if "/sites/" in path:
            if method == "GET":
                permissions.append("read:monitoring")
            elif method in ["POST", "PUT", "PATCH"]:
                permissions.append("write:config")
        
        if "/admin/" in path:
            permissions.append("admin:system")
        
        return permissions

    def _check_default_access(self, user: User, path: str, method: str) -> bool:
        """Check default access permissions"""
        # Viewers can read most endpoints
        if method == "GET" and user.role in [UserRole.VIEWER, UserRole.OPERATOR, UserRole.ADMIN]:
            return True
        
        # Operators can write to crawler endpoints
        if method in ["POST", "PUT", "PATCH"] and user.role in [UserRole.OPERATOR, UserRole.ADMIN]:
            if "/crawl" in path or "/monitoring" in path:
                return True
        
        # Admins have full access
        if user.role == UserRole.ADMIN:
            return True
        
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware integrated with authentication
    """
    
    def __init__(self, app: FastAPI, auth_system: AuthenticationSystem):
        super().__init__(app)
        self.auth_system = auth_system
        self.logger = logging.getLogger(__name__)
        
        # Rate limits per user role
        self.rate_limits = {
            UserRole.VIEWER: {"requests_per_minute": 60, "burst_limit": 10},
            UserRole.API_USER: {"requests_per_minute": 300, "burst_limit": 50},
            UserRole.OPERATOR: {"requests_per_minute": 600, "burst_limit": 100},
            UserRole.ADMIN: {"requests_per_minute": 1200, "burst_limit": 200},
            UserRole.SYSTEM: {"requests_per_minute": 2400, "burst_limit": 400}
        }
        
        # Request tracking
        self.request_counts = {}
        self.last_reset = datetime.now()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting based on user role"""
        try:
            # Skip rate limiting for public endpoints
            if self._is_public_endpoint(request.url.path):
                return await call_next(request)
            
            # Get user from request state (set by auth middleware)
            user = getattr(request.state, 'user', None)
            if not user:
                return await call_next(request)
            
            # Check rate limits
            if not await self._check_rate_limit(user):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded",
                        "error_code": "RATE_LIMIT_EXCEEDED"
                    }
                )
            
            # Record request
            await self._record_request(user)
            
            return await call_next(request)
            
        except Exception as e:
            self.logger.error(f"Rate limit middleware error: {e}")
            return await call_next(request)

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        public_endpoints = {"/docs", "/redoc", "/openapi.json", "/api/v1/health"}
        return any(path.startswith(endpoint) for endpoint in public_endpoints)

    async def _check_rate_limit(self, user: User) -> bool:
        """Check if user has exceeded rate limits"""
        try:
            current_time = datetime.now()
            
            # Reset counts every minute
            if (current_time - self.last_reset).total_seconds() > 60:
                self.request_counts = {}
                self.last_reset = current_time
            
            # Get user's rate limit
            rate_limit = self.rate_limits.get(user.role, self.rate_limits[UserRole.VIEWER])
            
            # Check current count
            user_key = f"{user.user_id}:{user.role.value}"
            current_count = self.request_counts.get(user_key, 0)
            
            return current_count < rate_limit["requests_per_minute"]
            
        except Exception as e:
            self.logger.error(f"Rate limit check failed: {e}")
            return True  # Allow request on error

    async def _record_request(self, user: User) -> None:
        """Record request for rate limiting"""
        try:
            user_key = f"{user.user_id}:{user.role.value}"
            self.request_counts[user_key] = self.request_counts.get(user_key, 0) + 1
        except Exception as e:
            self.logger.error(f"Request recording failed: {e}")


def setup_authentication_middleware(app: FastAPI, auth_system: AuthenticationSystem) -> None:
    """Setup authentication and rate limiting middleware"""
    
    # Add authentication middleware
    app.add_middleware(AuthenticationMiddleware, auth_system=auth_system)
    
    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, auth_system=auth_system)
    
    # Add CORS middleware for security
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend origins
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )


def create_auth_dependencies(auth_system: AuthenticationSystem) -> Dict[str, Callable]:
    """Create authentication dependency functions"""
    
    async def get_current_user_dep(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> User:
        """Get current authenticated user"""
        return await auth_system.verify_token(credentials)
    
    def require_role_dep(required_role: UserRole) -> Callable:
        """Require specific user role"""
        def check_role(current_user: User = Depends(get_current_user_dep)):
            if current_user.role != required_role and current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role: {required_role.value}"
                )
            return current_user
        return check_role
    
    def require_permission_dep(permission: str) -> Callable:
        """Require specific permission"""
        def check_permission(current_user: User = Depends(get_current_user_dep)):
            if not auth_system.check_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required permission: {permission}"
                )
            return current_user
        return check_permission
    
    return {
        "get_current_user": get_current_user_dep,
        "require_role": require_role_dep,
        "require_permission": require_permission_dep,
        "require_admin": require_role_dep(UserRole.ADMIN),
        "require_operator": require_role_dep(UserRole.OPERATOR),
        "require_api_user": require_role_dep(UserRole.API_USER)
    }


@asynccontextmanager
async def setup_authentication_context(config: Dict[str, Any]):
    """Setup authentication context for the application"""
    auth_system = AuthenticationSystem(config)
    
    # Initialize Redis if configured
    redis_url = config.get('redis_url')
    if redis_url:
        await auth_system.initialize_storage(redis_url)
    
    try:
        yield auth_system
    finally:
        # Cleanup
        if auth_system.redis_client:
            await auth_system.redis_client.close() 