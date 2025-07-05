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
        self.session_expiration_hours = self.config.get('session_expiration_hours', 168)  # 7 days
        
        # Storage
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.redis_client: Optional[aioredis.Redis] = None
        
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
        
        self.logger.info(f"User authenticated: {username}")
        
        return {
            "access_token": token,
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

    async def logout_user(self, session_id: str) -> bool:
        """Logout user by invalidating session"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.is_active = False
        
        # Remove from Redis if available
        if self.redis_client:
            await self.redis_client.delete(f"session:{session_id}")
        
        self.logger.info(f"User logged out: {session_id}")
        return True

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

    async def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        return {
            "total_users": len(self.users),
            "active_users": len([u for u in self.users.values() if u.is_active]),
            "active_sessions": len([s for s in self.sessions.values() if s.is_active]),
            "active_api_keys": len([k for k in self.api_keys.values() if k.is_active]),
            "failed_attempts": {
                username: len(attempts)
                for username, attempts in self.failed_attempts.items()
            },
            "locked_accounts": [
                username for username in self.failed_attempts.keys()
                if await self._is_account_locked(username)
            ]
        }


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