"""
Comprehensive Authentication System for FlightIO Crawler
Provides secure authentication, session management, and access control
"""

import jwt
import bcrypt
import secrets
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import aioredis
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import hashlib
import uuid
from cryptography.fernet import Fernet


class UserRole(Enum):
    """User roles with different access levels"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API_USER = "api_user"
    SYSTEM = "system"


class PermissionLevel(Enum):
    """Permission levels for different operations"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class User:
    """User data structure"""
    user_id: str
    username: str
    email: str
    role: UserRole
    permissions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False
    password_hash: Optional[str] = None
    api_key: Optional[str] = None
    session_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """Session data structure"""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKey:
    """API Key data structure"""
    key_id: str
    user_id: str
    key_hash: str
    name: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    rate_limit: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefreshToken:
    """Refresh Token data structure"""
    token_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthenticationSystem:
    """
    Comprehensive authentication and authorization system
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Security configuration
        self.jwt_secret = self.config.get('jwt_secret') or secrets.token_urlsafe(32)
        self.jwt_algorithm = self.config.get('jwt_algorithm', 'HS256')
        self.jwt_expiration_hours = self.config.get('jwt_expiration_hours', 24)
        self.refresh_token_expiration_days = self.config.get('refresh_token_expiration_days', 30)
        self.session_expiration_hours = self.config.get('session_expiration_hours', 168)  # 7 days
        
        # Storage
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.refresh_tokens: Dict[str, RefreshToken] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        
        # Analytics storage
        self.analytics_events: List[Dict[str, Any]] = []
        self.security_events: List[Dict[str, Any]] = []
        self.max_analytics_events = self.config.get('max_analytics_events', 10000)
        
        # Security settings
        self.password_min_length = self.config.get('password_min_length', 8)
        self.max_login_attempts = self.config.get('max_login_attempts', 5)
        self.lockout_duration_minutes = self.config.get('lockout_duration_minutes', 30)
        self.failed_attempts: Dict[str, List[datetime]] = {}
        
        # Permission system
        self.role_permissions = self._initialize_role_permissions()
        
        # Encryption for sensitive data
        self.encryption_key = self.config.get('encryption_key')
        if self.encryption_key:
            self.cipher = Fernet(self.encryption_key.encode())
        else:
            self.cipher = None
        
        # Security bearer
        self.security = HTTPBearer()
        
        self.logger.info("Authentication system initialized")

    def _initialize_role_permissions(self) -> Dict[UserRole, List[str]]:
        """Initialize default role permissions"""
        return {
            UserRole.ADMIN: [
                "read:*", "write:*", "delete:*", "admin:*", "system:*"
            ],
            UserRole.OPERATOR: [
                "read:*", "write:crawl", "write:config", "write:monitoring"
            ],
            UserRole.VIEWER: [
                "read:*"
            ],
            UserRole.API_USER: [
                "read:flights", "read:monitoring", "write:crawl"
            ],
            UserRole.SYSTEM: [
                "read:*", "write:*", "system:*"
            ]
        }

    async def initialize_storage(self, redis_url: Optional[str] = None):
        """Initialize Redis storage for sessions and rate limiting"""
        if redis_url:
            try:
                self.redis_client = aioredis.from_url(redis_url)
                await self.redis_client.ping()
                self.logger.info("Redis storage initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Redis: {e}")

    async def create_user(self, username: str, email: str, password: str, 
                         role: UserRole = UserRole.VIEWER,
                         permissions: Optional[List[str]] = None) -> User:
        """Create a new user"""
        # Validate inputs
        if len(password) < self.password_min_length:
            raise ValueError(f"Password must be at least {self.password_min_length} characters")
        
        if username in [user.username for user in self.users.values()]:
            raise ValueError("Username already exists")
        
        if email in [user.email for user in self.users.values()]:
            raise ValueError("Email already exists")
        
        # Create user
        user_id = str(uuid.uuid4())
        password_hash = self._hash_password(password)
        
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            permissions=permissions or self.role_permissions.get(role, []),
            password_hash=password_hash
        )
        
        self.users[user_id] = user
        
        # Store in Redis if available
        if self.redis_client:
            await self._store_user_in_redis(user)
        
        self.logger.info(f"User created: {username} ({role.value})")
        return user

    async def authenticate_user(self, username: str, password: str, 
                              ip_address: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate user with username and password"""
        # Check for account lockout
        if await self._is_account_locked(username):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to failed login attempts"
            )
        
        # Find user
        user = self._find_user_by_username(username)
        if not user:
            await self._record_failed_attempt(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            await self._record_failed_attempt(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Clear failed attempts
        if username in self.failed_attempts:
            del self.failed_attempts[username]
        
        # Update last login
        user.last_login = datetime.now()
        
        # Create session
        session = await self._create_session(user, ip_address)
        
        # Generate JWT token
        token = self._generate_jwt_token(user, session.session_id)
        
        # Generate refresh token
        refresh_token = await self._generate_refresh_token(user)
        
        self.logger.info(f"User authenticated: {username}")
        
        return {
            "access_token": token,
            "refresh_token": refresh_token.token_id,
            "token_type": "bearer",
            "expires_in": self.jwt_expiration_hours * 3600,
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "permissions": user.permissions
            },
            "session_id": session.session_id
        }

    async def authenticate_api_key(self, api_key: str) -> User:
        """Authenticate using API key"""
        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find matching API key
        api_key_obj = None
        for key_obj in self.api_keys.values():
            if key_obj.key_hash == key_hash and key_obj.is_active:
                api_key_obj = key_obj
                break
        
        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Check expiration
        if api_key_obj.expires_at and datetime.now() > api_key_obj.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired"
            )
        
        # Update last used
        api_key_obj.last_used = datetime.now()
        
        # Get user
        user = self.users.get(api_key_obj.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        # Override user permissions with API key permissions
        user.permissions = api_key_obj.permissions
        
        return user

    async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        """Verify JWT token"""
        try:
            # Decode JWT token
            payload = jwt.decode(
                credentials.credentials,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            user_id = payload.get("user_id")
            session_id = payload.get("session_id")
            
            if not user_id or not session_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Get user
            user = self.users.get(user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or deactivated"
                )
            
            # Verify session
            session = self.sessions.get(session_id)
            if not session or not session.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid session"
                )
            
            # Check session expiration
            if datetime.now() > session.expires_at:
                session.is_active = False
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired"
                )
            
            # Update session activity
            session.last_activity = datetime.now()
            
            return user
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

    def check_permission(self, user: User, required_permission: str) -> bool:
        """Check if user has required permission"""
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Check exact match
        if required_permission in user.permissions:
            return True
        
        # Check wildcard permissions
        for permission in user.permissions:
            if permission.endswith("*"):
                permission_prefix = permission[:-1]
                if required_permission.startswith(permission_prefix):
                    return True
        
        return False

    def require_permission(self, required_permission: str):
        """Decorator for requiring specific permission"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get current user from context
                user = kwargs.get('current_user')
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                if not self.check_permission(user, required_permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission required: {required_permission}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    async def create_api_key(self, user_id: str, name: str, 
                           permissions: List[str],
                           expires_in_days: Optional[int] = None) -> Dict[str, Any]:
        """Create a new API key for user"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Generate API key
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Set expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        # Create API key object
        key_obj = APIKey(
            key_id=str(uuid.uuid4()),
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            permissions=permissions,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        
        self.api_keys[key_obj.key_id] = key_obj
        
        self.logger.info(f"API key created for user {user.username}: {name}")
        
        return {
            "key_id": key_obj.key_id,
            "api_key": api_key,  # Return only once
            "name": name,
            "permissions": permissions,
            "expires_at": expires_at.isoformat() if expires_at else None
        }

    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke an API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key or api_key.user_id != user_id:
            return False
        
        api_key.is_active = False
        self.logger.info(f"API key revoked: {key_id}")
        return True

    async def list_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List API keys for a user (without exposing the actual key values)"""
        user_api_keys = []
        
        for api_key in self.api_keys.values():
            if api_key.user_id == user_id:
                # Only include non-sensitive information
                key_info = {
                    "key_id": api_key.key_id,
                    "name": api_key.name,
                    "permissions": api_key.permissions,
                    "is_active": api_key.is_active,
                    "created_at": api_key.created_at.isoformat(),
                    "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                    "last_used": api_key.last_used.isoformat() if api_key.last_used else None
                }
                user_api_keys.append(key_info)
        
        # Sort by creation date (newest first)
        user_api_keys.sort(key=lambda x: x['created_at'], reverse=True)
        
        return user_api_keys

    async def get_api_key_details(self, key_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key or api_key.user_id != user_id:
            return None
        
        return {
            "key_id": api_key.key_id,
            "name": api_key.name,
            "permissions": api_key.permissions,
            "is_active": api_key.is_active,
            "created_at": api_key.created_at.isoformat(),
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
            "metadata": api_key.metadata
        }

    async def update_api_key(self, key_id: str, user_id: str, 
                           name: Optional[str] = None,
                           permissions: Optional[List[str]] = None,
                           is_active: Optional[bool] = None) -> bool:
        """Update API key properties"""
        api_key = self.api_keys.get(key_id)
        if not api_key or api_key.user_id != user_id:
            return False
        
        # Update fields if provided
        if name is not None:
            api_key.name = name
        if permissions is not None:
            api_key.permissions = permissions
        if is_active is not None:
            api_key.is_active = is_active
        
        self.logger.info(f"API key updated: {key_id}")
        return True

    async def cleanup_expired_api_keys(self):
        """Cleanup expired API keys"""
        now = datetime.now()
        expired_keys = []
        
        for key_id, api_key in self.api_keys.items():
            if api_key.expires_at and now > api_key.expires_at:
                expired_keys.append(key_id)
        
        # Remove expired keys
        for key_id in expired_keys:
            del self.api_keys[key_id]
        
        if expired_keys:
            self.logger.info(f"Cleaned up {len(expired_keys)} expired API keys")
        
        return len(expired_keys)

    async def logout_user(self, session_id: str) -> bool:
        """Logout user by invalidating session"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.is_active = False
        
        # Revoke all refresh tokens for this user
        await self._revoke_user_refresh_tokens(session.user_id)
        
        # Remove from Redis if available
        if self.redis_client:
            await self.redis_client.delete(f"session:{session_id}")
        
        self.logger.info(f"User logged out: {session_id}")
        return True

    async def _revoke_user_refresh_tokens(self, user_id: str):
        """Revoke all refresh tokens for a user"""
        for refresh_token in self.refresh_tokens.values():
            if refresh_token.user_id == user_id and refresh_token.is_active:
                refresh_token.is_active = False
                
                # Remove from Redis if available
                if self.redis_client:
                    await self.redis_client.delete(f"refresh_token:{refresh_token.token_id}")
        
        self.logger.info(f"All refresh tokens revoked for user: {user_id}")

    async def cleanup_expired_tokens(self):
        """Cleanup expired refresh tokens"""
        now = datetime.now()
        expired_tokens = []
        
        for token_id, refresh_token in self.refresh_tokens.items():
            if now > refresh_token.expires_at:
                expired_tokens.append(token_id)
        
        # Remove expired tokens
        for token_id in expired_tokens:
            del self.refresh_tokens[token_id]
            
            # Remove from Redis if available
            if self.redis_client:
                await self.redis_client.delete(f"refresh_token:{token_id}")
        
        if expired_tokens:
            self.logger.info(f"Cleaned up {len(expired_tokens)} expired refresh tokens")
        
        return len(expired_tokens)

    async def get_user_refresh_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active refresh tokens for a user"""
        tokens = []
        
        for refresh_token in self.refresh_tokens.values():
            if (refresh_token.user_id == user_id and 
                refresh_token.is_active and 
                datetime.now() <= refresh_token.expires_at):
                
                tokens.append({
                    "token_id": refresh_token.token_id,
                    "created_at": refresh_token.created_at.isoformat(),
                    "expires_at": refresh_token.expires_at.isoformat(),
                    "metadata": refresh_token.metadata
                })
        
        return tokens

    async def change_password(self, user_id: str, old_password: str, 
                            new_password: str) -> bool:
        """Change user password"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        # Verify old password
        if not self._verify_password(old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password
        if len(new_password) < self.password_min_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password must be at least {self.password_min_length} characters"
            )
        
        # Update password
        user.password_hash = self._hash_password(new_password)
        
        # Invalidate all sessions for this user
        await self._invalidate_user_sessions(user_id)
        
        self.logger.info(f"Password changed for user: {user.username}")
        return True

    async def refresh_access_token(self, refresh_token_id: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            # Validate refresh token
            refresh_token = self.refresh_tokens.get(refresh_token_id)
            if not refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Check if refresh token is active
            if not refresh_token.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token is deactivated"
                )
            
            # Check if refresh token is expired
            if datetime.now() > refresh_token.expires_at:
                # Cleanup expired token
                refresh_token.is_active = False
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expired"
                )
            
            # Get user
            user = self.users.get(refresh_token.user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or deactivated"
                )
            
            # Create new session
            session = await self._create_session(user)
            
            # Generate new access token
            new_access_token = self._generate_jwt_token(user, session.session_id)
            
            # Optional: Rotate refresh token (recommended for security)
            new_refresh_token = None
            if self.config.get('rotate_refresh_tokens', True):
                # Deactivate old refresh token
                refresh_token.is_active = False
                
                # Generate new refresh token
                new_refresh_token = await self._generate_refresh_token(user)
                
                self.logger.info(f"Refresh token rotated for user: {user.username}")
            
            self.logger.info(f"Access token refreshed for user: {user.username}")
            
            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token.token_id if new_refresh_token else refresh_token_id,
                "token_type": "bearer",
                "expires_in": self.jwt_expiration_hours * 3600,
                "user": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                    "permissions": user.permissions
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Token refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )

    async def revoke_refresh_token(self, refresh_token_id: str, user_id: str) -> bool:
        """Revoke a refresh token"""
        refresh_token = self.refresh_tokens.get(refresh_token_id)
        if not refresh_token or refresh_token.user_id != user_id:
            return False
        
        refresh_token.is_active = False
        
        # Remove from Redis if available
        if self.redis_client:
            await self.redis_client.delete(f"refresh_token:{refresh_token_id}")
        
        self.logger.info(f"Refresh token revoked: {refresh_token_id}")
        return True

    async def _generate_refresh_token(self, user: User) -> RefreshToken:
        """Generate a new refresh token"""
        token_id = secrets.token_urlsafe(32)
        
        refresh_token = RefreshToken(
            token_id=token_id,
            user_id=user.user_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=self.refresh_token_expiration_days),
            metadata={
                "user_agent": None,  # Could be set from request context
                "ip_address": None   # Could be set from request context
            }
        )
        
        self.refresh_tokens[token_id] = refresh_token
        
        # Store in Redis if available
        if self.redis_client:
            await self._store_refresh_token_in_redis(refresh_token)
        
        return refresh_token

    async def _store_refresh_token_in_redis(self, refresh_token: RefreshToken):
        """Store refresh token in Redis"""
        try:
            refresh_token_data = {
                "token_id": refresh_token.token_id,
                "user_id": refresh_token.user_id,
                "created_at": refresh_token.created_at.isoformat(),
                "expires_at": refresh_token.expires_at.isoformat(),
                "is_active": refresh_token.is_active,
                "metadata": refresh_token.metadata
            }
            
            ttl = int((refresh_token.expires_at - datetime.now()).total_seconds())
            await self.redis_client.setex(
                f"refresh_token:{refresh_token.token_id}",
                ttl,
                json.dumps(refresh_token_data)
            )
        except Exception as e:
            self.logger.error(f"Failed to store refresh token in Redis: {e}")

    # Private helper methods
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def _find_user_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def _generate_jwt_token(self, user: User, session_id: str) -> str:
        """Generate JWT token"""
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "session_id": session_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=self.jwt_expiration_hours)
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

    async def _create_session(self, user: User, ip_address: Optional[str] = None) -> Session:
        """Create a new session"""
        session_id = str(uuid.uuid4())
        
        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=self.session_expiration_hours),
            last_activity=datetime.now(),
            ip_address=ip_address
        )
        
        self.sessions[session_id] = session
        
        # Store in Redis if available
        if self.redis_client:
            await self._store_session_in_redis(session)
        
        return session

    async def _store_user_in_redis(self, user: User):
        """Store user data in Redis"""
        try:
            user_data = {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "permissions": user.permissions,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
            
            await self.redis_client.setex(
                f"user:{user.user_id}",
                timedelta(days=7),
                json.dumps(user_data)
            )
        except Exception as e:
            self.logger.error(f"Failed to store user in Redis: {e}")

    async def _store_session_in_redis(self, session: Session):
        """Store session data in Redis"""
        try:
            session_data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "ip_address": session.ip_address,
                "is_active": session.is_active
            }
            
            ttl = int((session.expires_at - datetime.now()).total_seconds())
            await self.redis_client.setex(
                f"session:{session.session_id}",
                ttl,
                json.dumps(session_data)
            )
        except Exception as e:
            self.logger.error(f"Failed to store session in Redis: {e}")

    async def _record_failed_attempt(self, username: str):
        """Record failed login attempt"""
        now = datetime.now()
        if username not in self.failed_attempts:
            self.failed_attempts[username] = []
        
        self.failed_attempts[username].append(now)
        
        # Clean old attempts
        cutoff = now - timedelta(minutes=self.lockout_duration_minutes)
        self.failed_attempts[username] = [
            attempt for attempt in self.failed_attempts[username]
            if attempt > cutoff
        ]

    async def _is_account_locked(self, username: str) -> bool:
        """Check if account is locked due to failed attempts"""
        if username not in self.failed_attempts:
            return False
        
        now = datetime.now()
        cutoff = now - timedelta(minutes=self.lockout_duration_minutes)
        
        recent_attempts = [
            attempt for attempt in self.failed_attempts[username]
            if attempt > cutoff
        ]
        
        return len(recent_attempts) >= self.max_login_attempts

    async def _invalidate_user_sessions(self, user_id: str):
        """Invalidate all sessions for a user"""
        for session in self.sessions.values():
            if session.user_id == user_id:
                session.is_active = False
        
        # Remove from Redis if available
        if self.redis_client:
            # This would require scanning Redis keys - implement as needed
            pass

    # Admin methods
    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users (admin only)"""
        return [
            {
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
            for user in self.users.values()
        ]

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        user.is_active = False
        await self._invalidate_user_sessions(user_id)
        
        self.logger.info(f"User deactivated: {user.username}")
        return True

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active sessions for a user"""
        sessions = [
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "ip_address": session.ip_address,
                "is_active": session.is_active
            }
            for session in self.sessions.values()
            if session.user_id == user_id and session.is_active
        ]
        
        return sessions

    async def update_user_profile(self, user_id: str, 
                                email: Optional[str] = None,
                                current_password: Optional[str] = None) -> bool:
        """Allow user to update their own profile"""
        user = self.users.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # If email is being updated, verify current password
        if email and current_password:
            if not self._verify_password(current_password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Check if email is already taken by another user
            for existing_user in self.users.values():
                if existing_user.user_id != user_id and existing_user.email == email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email is already taken"
                    )
            
            user.email = email
            self.logger.info(f"Email updated for user: {user.username}")
        
        return True

    async def admin_update_user(self, user_id: str,
                              email: Optional[str] = None,
                              role: Optional[UserRole] = None,
                              is_active: Optional[bool] = None,
                              permissions: Optional[List[str]] = None,
                              is_verified: Optional[bool] = None) -> bool:
        """Admin function to update any user"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        updates = []
        
        # Update email
        if email is not None:
            # Check if email is already taken by another user
            for existing_user in self.users.values():
                if existing_user.user_id != user_id and existing_user.email == email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email is already taken"
                    )
            user.email = email
            updates.append(f"email to {email}")
        
        # Update role
        if role is not None:
            old_role = user.role
            user.role = role
            # Update permissions based on new role
            user.permissions = permissions or self.role_permissions.get(role, [])
            updates.append(f"role from {old_role.value} to {role.value}")
        
        # Update active status
        if is_active is not None:
            user.is_active = is_active
            updates.append(f"active status to {is_active}")
            
            # If deactivating, invalidate all sessions
            if not is_active:
                await self._invalidate_user_sessions(user_id)
        
        # Update permissions (if not already updated by role change)
        if permissions is not None and role is None:
            user.permissions = permissions
            updates.append("permissions")
        
        # Update verification status
        if is_verified is not None:
            user.is_verified = is_verified
            updates.append(f"verification status to {is_verified}")
        
        if updates:
            self.logger.info(f"User {user.username} updated: {', '.join(updates)}")
        
        return True

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return self.users.get(user_id)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self._find_user_by_username(username)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics for monitoring"""
        now = datetime.now()
        
        # Count active sessions
        active_sessions = sum(
            1 for session in self.sessions.values() 
            if session.is_active and now <= session.expires_at
        )
        
        # Count users by role
        users_by_role = {}
        for user in self.users.values():
            role = user.role.value
            users_by_role[role] = users_by_role.get(role, 0) + 1
        
        # Count recent login attempts (last 24 hours)
        recent_failed_attempts = 0
        cutoff = now - timedelta(hours=24)
        for attempts in self.failed_attempts.values():
            recent_failed_attempts += len([
                attempt for attempt in attempts if attempt > cutoff
            ])
        
        # Count API keys
        active_api_keys = sum(
            1 for api_key in self.api_keys.values() 
            if api_key.is_active and (
                not api_key.expires_at or now <= api_key.expires_at
            )
        )
        
        return {
            "total_users": len(self.users),
            "active_users": sum(1 for user in self.users.values() if user.is_active),
            "users_by_role": users_by_role,
            "active_sessions": active_sessions,
            "total_sessions": len(self.sessions),
            "active_api_keys": active_api_keys,
            "total_api_keys": len(self.api_keys),
            "recent_failed_attempts": recent_failed_attempts,
            "total_refresh_tokens": len(self.refresh_tokens),
            "timestamp": now.isoformat()
        }

    async def log_login_analytics(self, user: User, ip_address: str, 
                                user_agent: Optional[str] = None,
                                success: bool = True,
                                failure_reason: Optional[str] = None):
        """Log login analytics for security monitoring"""
        try:
            event = {
                "event_type": "login_attempt",
                "user_id": user.user_id if user else None,
                "username": user.username if user else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "failure_reason": failure_reason,
                "timestamp": datetime.now().isoformat(),
                "session_id": None  # Will be set if login successful
            }
            
            # Add geolocation if available
            if ip_address:
                event["geolocation"] = await self._get_ip_geolocation(ip_address)
            
            # Analyze risk factors
            event["risk_factors"] = await self._analyze_login_risk(user, ip_address, user_agent)
            
            # Store analytics event
            self.analytics_events.append(event)
            
            # If this is a security event, also log to security events
            if not success or event["risk_factors"]["risk_level"] == "high":
                self.security_events.append(event)
            
            # Cleanup old events if needed
            await self._cleanup_old_analytics()
            
            # Store in Redis if available for real-time monitoring
            if self.redis_client:
                await self._store_analytics_in_redis(event)
            
            self.logger.info(f"Login analytics logged for user: {user.username if user else 'unknown'}")
            
        except Exception as e:
            self.logger.error(f"Failed to log login analytics: {e}")

    async def log_registration_analytics(self, user: User, ip_address: str, 
                                       user_agent: Optional[str] = None):
        """Log registration analytics for user insights"""
        try:
            event = {
                "event_type": "registration",
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp": datetime.now().isoformat(),
                "verification_status": user.is_verified
            }
            
            # Add geolocation if available
            if ip_address:
                event["geolocation"] = await self._get_ip_geolocation(ip_address)
            
            # Analyze registration patterns
            event["registration_analysis"] = await self._analyze_registration_patterns(user, ip_address)
            
            # Store analytics event
            self.analytics_events.append(event)
            
            # Cleanup old events if needed
            await self._cleanup_old_analytics()
            
            # Store in Redis if available
            if self.redis_client:
                await self._store_analytics_in_redis(event)
            
            self.logger.info(f"Registration analytics logged for user: {user.username}")
            
        except Exception as e:
            self.logger.error(f"Failed to log registration analytics: {e}")

    async def log_security_event(self, event_type: str, user_id: Optional[str] = None,
                                ip_address: Optional[str] = None,
                                details: Optional[Dict[str, Any]] = None):
        """Log security-related events"""
        try:
            event = {
                "event_type": event_type,
                "user_id": user_id,
                "ip_address": ip_address,
                "details": details or {},
                "timestamp": datetime.now().isoformat(),
                "severity": self._classify_security_event_severity(event_type)
            }
            
            self.security_events.append(event)
            
            # Alert on high-severity events
            if event["severity"] == "high":
                await self._send_security_alert(event)
            
            self.logger.warning(f"Security event logged: {event_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to log security event: {e}")

    async def get_login_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get login analytics for the specified time period"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            # Filter events within time period
            recent_events = [
                event for event in self.analytics_events
                if (event.get("event_type") == "login_attempt" and 
                    datetime.fromisoformat(event["timestamp"]) > cutoff)
            ]
            
            total_attempts = len(recent_events)
            successful_logins = len([e for e in recent_events if e.get("success")])
            failed_logins = total_attempts - successful_logins
            
            # Analyze patterns
            ip_addresses = {}
            user_agents = {}
            failure_reasons = {}
            
            for event in recent_events:
                # Count IP addresses
                ip = event.get("ip_address", "unknown")
                ip_addresses[ip] = ip_addresses.get(ip, 0) + 1
                
                # Count user agents
                ua = event.get("user_agent", "unknown")
                user_agents[ua] = user_agents.get(ua, 0) + 1
                
                # Count failure reasons
                if not event.get("success") and event.get("failure_reason"):
                    reason = event["failure_reason"]
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            return {
                "period_hours": hours,
                "total_login_attempts": total_attempts,
                "successful_logins": successful_logins,
                "failed_logins": failed_logins,
                "success_rate": (successful_logins / total_attempts * 100) if total_attempts > 0 else 0,
                "unique_ip_addresses": len(ip_addresses),
                "top_ip_addresses": sorted(ip_addresses.items(), key=lambda x: x[1], reverse=True)[:10],
                "unique_user_agents": len(user_agents),
                "failure_reasons": failure_reasons,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get login analytics: {e}")
            return {}

    async def get_registration_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get registration analytics for the specified time period"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            # Filter registration events
            recent_registrations = [
                event for event in self.analytics_events
                if (event.get("event_type") == "registration" and 
                    datetime.fromisoformat(event["timestamp"]) > cutoff)
            ]
            
            total_registrations = len(recent_registrations)
            
            # Analyze by role
            registrations_by_role = {}
            for event in recent_registrations:
                role = event.get("role", "unknown")
                registrations_by_role[role] = registrations_by_role.get(role, 0) + 1
            
            # Analyze by day
            daily_registrations = {}
            for event in recent_registrations:
                day = event["timestamp"][:10]  # YYYY-MM-DD
                daily_registrations[day] = daily_registrations.get(day, 0) + 1
            
            return {
                "period_days": days,
                "total_registrations": total_registrations,
                "registrations_by_role": registrations_by_role,
                "daily_registrations": daily_registrations,
                "average_per_day": total_registrations / days if days > 0 else 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get registration analytics: {e}")
            return {}

    async def get_security_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get security events for monitoring"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            recent_events = [
                event for event in self.security_events
                if datetime.fromisoformat(event["timestamp"]) > cutoff
            ]
            
            # Sort by timestamp (newest first)
            recent_events.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return recent_events
            
        except Exception as e:
            self.logger.error(f"Failed to get security events: {e}")
            return []

    # Private analytics methods
    async def _get_ip_geolocation(self, ip_address: str) -> Dict[str, Any]:
        """Get geolocation for IP address (placeholder implementation)"""
        # In a real implementation, this would use a geolocation service
        return {
            "country": "unknown",
            "region": "unknown",
            "city": "unknown",
            "is_private": ip_address.startswith(("192.168.", "10.", "172.16."))
        }

    async def _analyze_login_risk(self, user: Optional[User], ip_address: str, 
                                user_agent: Optional[str]) -> Dict[str, Any]:
        """Analyze risk factors for login attempt"""
        risk_factors = {
            "risk_level": "low",
            "factors": []
        }
        
        try:
            # Check for unusual IP
            if user and ip_address:
                recent_ips = [
                    event.get("ip_address") for event in self.analytics_events[-100:]
                    if (event.get("user_id") == user.user_id and 
                        event.get("success") and 
                        event.get("ip_address"))
                ]
                
                if recent_ips and ip_address not in recent_ips:
                    risk_factors["factors"].append("new_ip_address")
            
            # Check for suspicious user agent
            if user_agent and ("bot" in user_agent.lower() or "crawler" in user_agent.lower()):
                risk_factors["factors"].append("suspicious_user_agent")
            
            # Check for rapid attempts
            recent_attempts = [
                event for event in self.analytics_events[-50:]
                if (event.get("ip_address") == ip_address and 
                    datetime.fromisoformat(event["timestamp"]) > datetime.now() - timedelta(minutes=5))
            ]
            
            if len(recent_attempts) > 5:
                risk_factors["factors"].append("rapid_attempts")
            
            # Determine overall risk level
            if len(risk_factors["factors"]) >= 2:
                risk_factors["risk_level"] = "high"
            elif risk_factors["factors"]:
                risk_factors["risk_level"] = "medium"
                
        except Exception as e:
            self.logger.error(f"Risk analysis failed: {e}")
        
        return risk_factors

    async def _analyze_registration_patterns(self, user: User, ip_address: str) -> Dict[str, Any]:
        """Analyze registration patterns for fraud detection"""
        analysis = {
            "suspicious_patterns": []
        }
        
        try:
            # Check for multiple registrations from same IP
            recent_registrations = [
                event for event in self.analytics_events[-100:]
                if (event.get("event_type") == "registration" and 
                    event.get("ip_address") == ip_address and
                    datetime.fromisoformat(event["timestamp"]) > datetime.now() - timedelta(hours=24))
            ]
            
            if len(recent_registrations) > 3:
                analysis["suspicious_patterns"].append("multiple_registrations_same_ip")
            
            # Check for suspicious email patterns
            if user.email:
                email_domain = user.email.split('@')[1] if '@' in user.email else ""
                if email_domain in ["tempmail.com", "10minutemail.com"]:  # Common temp email domains
                    analysis["suspicious_patterns"].append("temporary_email_domain")
            
        except Exception as e:
            self.logger.error(f"Registration pattern analysis failed: {e}")
        
        return analysis

    def _classify_security_event_severity(self, event_type: str) -> str:
        """Classify security event severity"""
        high_severity_events = [
            "account_takeover_attempt",
            "privilege_escalation",
            "multiple_failed_logins",
            "suspicious_api_access"
        ]
        
        medium_severity_events = [
            "password_change",
            "email_change",
            "new_api_key_created"
        ]
        
        if event_type in high_severity_events:
            return "high"
        elif event_type in medium_severity_events:
            return "medium"
        else:
            return "low"

    async def _send_security_alert(self, event: Dict[str, Any]):
        """Send security alert for high-severity events"""
        # Placeholder for security alerting system
        # In a real implementation, this would send alerts via email, Slack, etc.
        self.logger.critical(f"SECURITY ALERT: {event['event_type']} - {event}")

    async def _cleanup_old_analytics(self):
        """Cleanup old analytics events to prevent memory buildup"""
        if len(self.analytics_events) > self.max_analytics_events:
            # Keep only the most recent events
            self.analytics_events = self.analytics_events[-self.max_analytics_events:]
        
        if len(self.security_events) > 1000:  # Keep more security events
            self.security_events = self.security_events[-1000:]

    async def _store_analytics_in_redis(self, event: Dict[str, Any]):
        """Store analytics event in Redis for real-time monitoring"""
        try:
            if self.redis_client:
                key = f"analytics:{event['event_type']}:{datetime.now().strftime('%Y%m%d')}"
                await self.redis_client.lpush(key, json.dumps(event))
                await self.redis_client.expire(key, timedelta(days=7))
        except Exception as e:
            self.logger.error(f"Failed to store analytics in Redis: {e}")


# Global authentication instance
_global_auth = None


def get_auth_system() -> AuthenticationSystem:
    """Get global authentication system instance"""
    global _global_auth
    if _global_auth is None:
        _global_auth = AuthenticationSystem()
    return _global_auth


def initialize_auth_system(config: Dict[str, Any]) -> AuthenticationSystem:
    """Initialize global authentication system with configuration"""
    global _global_auth
    _global_auth = AuthenticationSystem(config)
    return _global_auth


# FastAPI dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """FastAPI dependency to get current authenticated user"""
    auth_system = get_auth_system()
    return await auth_system.verify_token(credentials)


def require_role(required_role: UserRole):
    """FastAPI dependency to require specific role"""
    def check_role(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {required_role.value}"
            )
        return current_user
    return check_role


def require_permission(permission: str):
    """FastAPI dependency to require specific permission"""
    def check_permission(current_user: User = Depends(get_current_user)):
        auth_system = get_auth_system()
        if not auth_system.check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return check_permission 