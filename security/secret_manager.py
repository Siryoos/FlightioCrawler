"""
Security module for managing secrets and sensitive data
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class SecretManager:
    """Secure secrets management with encryption and environment variable support"""
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize SecretManager with optional master key"""
        self.master_key = master_key or os.environ.get('MASTER_KEY')
        self._fernet = None
        self._secrets_cache = {}
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption with master key"""
        if not self.master_key:
            logger.warning("No master key provided. Encryption will be disabled.")
            return
            
        try:
            # Generate key from master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'flightio_salt',  # In production, use random salt
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
            self._fernet = Fernet(key)
            logger.info("Encryption initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            
    def encrypt_secret(self, secret: str) -> str:
        """Encrypt a secret value"""
        if not self._fernet:
            return secret  # Return unencrypted if encryption not available
            
        try:
            encrypted_data = self._fernet.encrypt(secret.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            return secret
    
    def decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt a secret value"""
        if not self._fernet:
            return encrypted_secret  # Return as-is if encryption not available
            
        try:
            encrypted_data = base64.urlsafe_b64decode(encrypted_secret.encode())
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return encrypted_secret
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret from environment variables with caching"""
        if key in self._secrets_cache:
            return self._secrets_cache[key]
            
        # Try environment variable first
        value = os.environ.get(key, default)
        
        if value:
            # Check if it's an encrypted value (starts with 'encrypted:')
            if value.startswith('encrypted:'):
                value = self.decrypt_secret(value[10:])  # Remove 'encrypted:' prefix
            
            self._secrets_cache[key] = value
            return value
        
        return default
    
    def set_secret(self, key: str, value: str, encrypt: bool = True) -> bool:
        """Set a secret value (for runtime configuration)"""
        try:
            if encrypt and self._fernet:
                encrypted_value = self.encrypt_secret(value)
                self._secrets_cache[key] = value
                # In production, this could be stored in a secure store
                logger.info(f"Secret '{key}' set with encryption")
            else:
                self._secrets_cache[key] = value
                logger.info(f"Secret '{key}' set without encryption")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set secret '{key}': {e}")
            return False
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration with secrets"""
        return {
            'host': self.get_secret('DB_HOST', 'localhost'),
            'port': int(self.get_secret('DB_PORT', '5432')),
            'name': self.get_secret('DB_NAME', 'flight_data'),
            'user': self.get_secret('DB_USER', 'postgres'),
            'password': self.get_secret('DB_PASSWORD', ''),
            'ssl_mode': self.get_secret('DB_SSL_MODE', 'disable'),
            'pool_size': int(self.get_secret('DB_POOL_SIZE', '5')),
            'max_overflow': int(self.get_secret('DB_MAX_OVERFLOW', '10')),
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration with secrets"""
        return {
            'host': self.get_secret('REDIS_HOST', 'localhost'),
            'port': int(self.get_secret('REDIS_PORT', '6379')),
            'db': int(self.get_secret('REDIS_DB', '0')),
            'password': self.get_secret('REDIS_PASSWORD'),
            'ssl': self.get_secret('REDIS_SSL', 'false').lower() == 'true',
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration with secrets"""
        return {
            'secret_key': self.get_secret('SECRET_KEY'),
            'jwt_secret': self.get_secret('JWT_SECRET_KEY'),
            'jwt_expiration': int(self.get_secret('JWT_EXPIRATION_HOURS', '24')),
            'allowed_hosts': self.get_secret('ALLOWED_HOSTS', 'localhost').split(','),
            'cors_origins': self.get_secret('CORS_ORIGINS', 'http://localhost:3000').split(','),
        }
    
    def get_external_api_config(self) -> Dict[str, Any]:
        """Get external API configuration with secrets"""
        return {
            'amadeus_api_key': self.get_secret('AMADEUS_API_KEY'),
            'amadeus_api_secret': self.get_secret('AMADEUS_API_SECRET'),
            'slack_webhook_url': self.get_secret('SLACK_WEBHOOK_URL'),
            'alert_email': self.get_secret('ALERT_EMAIL'),
        }
    
    def validate_secrets(self) -> Dict[str, bool]:
        """Validate that required secrets are available"""
        required_secrets = [
            'DB_PASSWORD',
            'SECRET_KEY',
            'JWT_SECRET_KEY',
        ]
        
        validation_results = {}
        for secret_key in required_secrets:
            value = self.get_secret(secret_key)
            validation_results[secret_key] = bool(value and len(value) > 0)
        
        return validation_results
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret value"""
        try:
            # In production, this would include proper rotation logic
            # with rollback capability
            old_value = self.get_secret(key)
            if old_value:
                logger.info(f"Rotating secret '{key}'")
                self.set_secret(key, new_value)
                return True
            else:
                logger.warning(f"No existing secret found for '{key}'")
                return False
        except Exception as e:
            logger.error(f"Failed to rotate secret '{key}': {e}")
            return False
    
    def clear_cache(self):
        """Clear the secrets cache"""
        self._secrets_cache.clear()
        logger.info("Secrets cache cleared")
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for SecretManager"""
        return {
            'encryption_enabled': bool(self._fernet),
            'secrets_cached': len(self._secrets_cache),
            'validation_results': self.validate_secrets(),
        }


# Global instance
secret_manager = SecretManager()


def get_secret_manager() -> SecretManager:
    """Get the global SecretManager instance"""
    return secret_manager


def init_secret_manager(master_key: Optional[str] = None) -> SecretManager:
    """Initialize the global SecretManager with a master key"""
    global secret_manager
    secret_manager = SecretManager(master_key)
    return secret_manager 