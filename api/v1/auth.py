"""
Authentication API Endpoints
Provides comprehensive authentication and user management endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime, timedelta
import logging
from ipaddress import ip_address

from security.authentication_system import (
    AuthenticationSystem,
    User,
    UserRole,
    Session,
    APIKey,
    get_auth_system
)
from security.authentication_middleware import create_auth_dependencies


# Pydantic models for request/response validation
class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool = False


class RegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    role: Optional[UserRole] = UserRole.VIEWER
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('New passwords do not match')
        return v


class CreateAPIKeyRequest(BaseModel):
    """Create API key request"""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class UpdateUserRequest(BaseModel):
    """Update user request"""
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None


class UpdateProfileRequest(BaseModel):
    """Update profile request for self-updates"""
    email: Optional[EmailStr] = None
    current_password: Optional[str] = Field(None, min_length=8, max_length=128)
    
    @validator('email')
    def email_requires_password(cls, v, values):
        if v and not values.get('current_password'):
            raise ValueError('Current password is required when updating email')
        return v


class AuthResponse(BaseModel):
    """Authentication response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: Dict[str, Any]


class UserResponse(BaseModel):
    """User response"""
    user_id: str
    username: str
    email: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    """API key response"""
    key_id: str
    name: str
    api_key: str
    permissions: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime


# Router setup
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    request_info: Request,
    background_tasks: BackgroundTasks,
    auth_system: AuthenticationSystem = Depends(get_auth_system)
):
    """
    Authenticate user and return access token
    """
    try:
        # Get client IP address
        client_ip = request_info.client.host
        
        # Authenticate user
        auth_result = await auth_system.authenticate_user(
            username=request.username,
            password=request.password,
            ip_address=client_ip
        )
        
        if not auth_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_result["message"],
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Log successful login
        logger.info(f"User {request.username} logged in successfully from {client_ip}")
        
        # Schedule background task for login analytics
        background_tasks.add_task(
            auth_system.log_login_analytics,
            auth_result["user"],
            client_ip,
            request_info.headers.get("user-agent"),
            True,  # success
            None   # no failure reason
        )
        
        return AuthResponse(
            access_token=auth_result["access_token"],
            expires_in=auth_result["expires_in"],
            refresh_token=auth_result.get("refresh_token"),
            user={
                "user_id": auth_result["user"].user_id,
                "username": auth_result["user"].username,
                "email": auth_result["user"].email,
                "role": auth_result["user"].role.value,
                "is_active": auth_result["user"].is_active,
                "permissions": auth_result["user"].permissions
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error"
        )


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    request_info: Request,
    background_tasks: BackgroundTasks,
    auth_system: AuthenticationSystem = Depends(get_auth_system)
):
    """
    Register a new user
    """
    try:
        # Create user
        user = await auth_system.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role
        )
        
        # Log registration
        client_ip = request_info.client.host
        logger.info(f"New user registered: {request.username} from {client_ip}")
        
        # Schedule background task for registration analytics
        background_tasks.add_task(
            auth_system.log_registration_analytics,
            user,
            client_ip,
            request_info.headers.get("user-agent")
        )
        
        return UserResponse(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: TokenRefreshRequest,
    auth_system: AuthenticationSystem = Depends(get_auth_system)
):
    """
    Refresh access token using refresh token
    """
    try:
        # Validate refresh token and generate new access token
        token_data = await auth_system.refresh_access_token(request.refresh_token)
        
        logger.info(f"Token refreshed successfully for user: {token_data['user']['username']}")
        
        return AuthResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_type=token_data["token_type"],
            expires_in=token_data["expires_in"],
            user=token_data["user"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_system: AuthenticationSystem = Depends(get_auth_system)
):
    """
    Logout user and invalidate token
    """
    try:
        # Verify token to get user and session
        user = await auth_system.verify_token(credentials)
        
        # Extract session ID from token (if stored)
        # This is a simplified approach - in practice, you'd extract from JWT payload
        session_id = user.session_data.get('current_session_id')
        
        if session_id:
            await auth_system.logout_user(session_id)
        
        logger.info(f"User {user.username} logged out successfully")
        
        return {"message": "Logged out successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Get current authenticated user information
    """
    try:
        return UserResponse(
            user_id=current_user.user_id,
            username=current_user.username,
            email=current_user.email,
            role=current_user.role,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            created_at=current_user.created_at,
            last_login=current_user.last_login
        )
        
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Change user password
    """
    try:
        success = await auth_system.change_password(
            user_id=current_user.user_id,
            old_password=request.current_password,
            new_password=request.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        logger.info(f"Password changed for user {current_user.username}")
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Create a new API key for the current user
    """
    try:
        api_key_data = await auth_system.create_api_key(
            user_id=current_user.user_id,
            name=request.name,
            permissions=request.permissions,
            expires_in_days=request.expires_in_days
        )
        
        logger.info(f"API key created for user {current_user.username}: {request.name}")
        
        return APIKeyResponse(
            key_id=api_key_data["key_id"],
            name=api_key_data["name"],
            api_key=api_key_data["api_key"],
            permissions=api_key_data["permissions"],
            expires_at=api_key_data.get("expires_at"),
            created_at=api_key_data["created_at"]
        )
        
    except Exception as e:
        logger.error(f"Create API key error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.get("/api-keys")
async def list_api_keys(
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    List user's API keys (without exposing the actual keys)
    """
    try:
        # Get user's API keys without exposing sensitive information
        api_keys = await auth_system.list_user_api_keys(current_user.user_id)
        
        logger.info(f"Listed {len(api_keys)} API keys for user: {current_user.username}")
        
        return {
            "api_keys": api_keys,
            "total_count": len(api_keys)
        }
        
    except Exception as e:
        logger.error(f"List API keys error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Revoke an API key
    """
    try:
        success = await auth_system.revoke_api_key(key_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        logger.info(f"API key revoked by user {current_user.username}: {key_id}")
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke API key error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@router.get("/api-keys/{key_id}")
async def get_api_key_details(
    key_id: str,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Get detailed information about a specific API key
    """
    try:
        api_key_details = await auth_system.get_api_key_details(key_id, current_user.user_id)
        
        if not api_key_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        return api_key_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get API key details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get API key details"
        )


@router.put("/api-keys/{key_id}")
async def update_api_key(
    key_id: str,
    name: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Update API key properties
    """
    try:
        success = await auth_system.update_api_key(
            key_id=key_id,
            user_id=current_user.user_id,
            name=name,
            permissions=permissions,
            is_active=is_active
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        logger.info(f"API key updated by user {current_user.username}: {key_id}")
        
        return {"message": "API key updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update API key error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key"
        )


@router.get("/sessions")
async def list_sessions(
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    List user's active sessions
    """
    try:
        sessions = await auth_system.get_user_sessions(current_user.user_id)
        return {"sessions": sessions}
        
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions"
        )


# Admin endpoints
@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    List all users (admin only)
    """
    try:
        users_data = await auth_system.list_users()
        return [
            UserResponse(
                user_id=user_data["user_id"],
                username=user_data["username"],
                email=user_data["email"],
                role=UserRole(user_data["role"]),
                is_active=user_data["is_active"],
                is_verified=user_data["is_verified"],
                created_at=user_data["created_at"],
                last_login=user_data.get("last_login")
            )
            for user_data in users_data
        ]
        
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Update user information (admin only)
    """
    try:
        # Update user using admin function
        success = await auth_system.admin_update_user(
            user_id=user_id,
            email=request.email,
            role=request.role,
            is_active=request.is_active,
            permissions=request.permissions
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get updated user data
        updated_user = await auth_system.get_user_by_id(user_id)
        
        logger.info(f"User {user_id} updated by admin {current_user.username}")
        
        return UserResponse(
            user_id=updated_user.user_id,
            username=updated_user.username,
            email=updated_user.email,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/admin/users/{user_id}")
async def deactivate_user(
    user_id: str,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Deactivate user (admin only)
    """
    try:
        success = await auth_system.deactivate_user(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User {user_id} deactivated by admin {current_user.username}")
        
        return {"message": "User deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


@router.get("/admin/stats")
async def get_security_stats(
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Get security statistics (admin only)
    """
    try:
        stats = await auth_system.get_security_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Get security stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get security statistics"
        )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["get_current_user"])
):
    """
    Update current user's profile
    """
    try:
        # Update user profile
        success = await auth_system.update_user_profile(
            user_id=current_user.user_id,
            email=request.email,
            current_password=request.current_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile update failed"
            )
        
        # Get updated user data
        updated_user = await auth_system.get_user_by_id(current_user.user_id)
        
        logger.info(f"Profile updated for user: {current_user.username}")
        
        return UserResponse(
            user_id=updated_user.user_id,
            username=updated_user.username,
            email=updated_user.email,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


# Analytics endpoints
@router.get("/admin/analytics/login")
async def get_login_analytics(
    hours: int = 24,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Get login analytics (admin only)
    """
    try:
        analytics = await auth_system.get_login_analytics(hours)
        return analytics
        
    except Exception as e:
        logger.error(f"Get login analytics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get login analytics"
        )


@router.get("/admin/analytics/registration")
async def get_registration_analytics(
    days: int = 30,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Get registration analytics (admin only)
    """
    try:
        analytics = await auth_system.get_registration_analytics(days)
        return analytics
        
    except Exception as e:
        logger.error(f"Get registration analytics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get registration analytics"
        )


@router.get("/admin/security/events")
async def get_security_events(
    hours: int = 24,
    auth_system: AuthenticationSystem = Depends(get_auth_system),
    current_user: User = Depends(create_auth_dependencies(get_auth_system())["require_admin"])
):
    """
    Get security events for monitoring (admin only)
    """
    try:
        events = await auth_system.get_security_events(hours)
        return {"events": events, "count": len(events)}
        
    except Exception as e:
        logger.error(f"Get security events error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get security events"
        )


# Health check endpoint
@router.get("/health")
async def auth_health_check(
    auth_system: AuthenticationSystem = Depends(get_auth_system)
):
    """
    Authentication system health check
    """
    try:
        # Check if authentication system is working
        stats = await auth_system.get_security_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "total_users": stats.get("total_users", 0),
            "active_sessions": stats.get("active_sessions", 0)
        }
        
    except Exception as e:
        logger.error(f"Auth health check error: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        } 