"""
Comprehensive Data Encryption System for FlightIO Crawler
Provides encryption for sensitive data including API keys, credentials, and user information
"""

import logging
import secrets
import base64
import hashlib
import json
import os
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import asyncio
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization, padding
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import aiofiles
import aioredis
from contextlib import asynccontextmanager


class EncryptionMethod(Enum):
    """Supported encryption methods"""
    AES_256_GCM = "aes_256_gcm"
    FERNET = "fernet"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"
    CHACHA20_POLY1305 = "chacha20_poly1305"


class DataClassification(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


@dataclass
class EncryptionConfig:
    """Encryption configuration"""
    method: EncryptionMethod
    key_size: int = 256
    use_salt: bool = True
    compression: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncryptedData:
    """Encrypted data container"""
    data: bytes
    method: EncryptionMethod
    key_id: str
    salt: Optional[bytes] = None
    nonce: Optional[bytes] = None
    tag: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class EncryptionKey:
    """Encryption key metadata"""
    key_id: str
    method: EncryptionMethod
    created_at: datetime
    expires_at: Optional[datetime] = None
    usage_count: int = 0
    max_usage: Optional[int] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataEncryptionSystem:
    """
    Comprehensive data encryption system with multiple encryption methods
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Key management
        self.encryption_keys: Dict[str, EncryptionKey] = {}
        self.key_data: Dict[str, bytes] = {}
        self.master_key: Optional[bytes] = None
        
        # Encryption configurations
        self.encryption_configs: Dict[DataClassification, EncryptionConfig] = {}
        
        # Security settings
        self.key_rotation_interval = self.config.get('key_rotation_interval', 86400)  # 24 hours
        self.max_key_usage = self.config.get('max_key_usage', 10000)
        self.enable_key_escrow = self.config.get('enable_key_escrow', False)
        
        # Storage
        self.key_storage_path = Path(self.config.get('key_storage_path', 'security/keys'))
        self.key_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Redis for key caching
        self.redis_client: Optional[aioredis.Redis] = None
        
        # Initialize system
        self._initialize_master_key()
        self._initialize_encryption_configs()
        
        self.logger.info("Data encryption system initialized")

    def _initialize_master_key(self):
        """Initialize or load master encryption key"""
        master_key_path = self.key_storage_path / "master.key"
        
        if master_key_path.exists():
            try:
                with open(master_key_path, 'rb') as f:
                    encrypted_master_key = f.read()
                
                # Decrypt master key using environment variable
                key_password = os.getenv('ENCRYPTION_MASTER_PASSWORD')
                if key_password:
                    self.master_key = self._decrypt_master_key(encrypted_master_key, key_password)
                    self.logger.info("Master key loaded successfully")
                else:
                    self.logger.warning("Master key password not found in environment")
            except Exception as e:
                self.logger.error(f"Failed to load master key: {e}")
                self._generate_master_key()
        else:
            self._generate_master_key()

    def _generate_master_key(self):
        """Generate new master key"""
        try:
            self.master_key = Fernet.generate_key()
            
            # Encrypt master key with password
            key_password = os.getenv('ENCRYPTION_MASTER_PASSWORD') or secrets.token_urlsafe(32)
            encrypted_master_key = self._encrypt_master_key(self.master_key, key_password)
            
            # Save encrypted master key
            master_key_path = self.key_storage_path / "master.key"
            with open(master_key_path, 'wb') as f:
                f.write(encrypted_master_key)
            
            # Set secure permissions
            os.chmod(master_key_path, 0o600)
            
            self.logger.info("New master key generated and saved")
            
            if not os.getenv('ENCRYPTION_MASTER_PASSWORD'):
                self.logger.warning(f"Set ENCRYPTION_MASTER_PASSWORD environment variable to: {key_password}")
        except Exception as e:
            self.logger.error(f"Failed to generate master key: {e}")
            raise

    def _encrypt_master_key(self, key: bytes, password: str) -> bytes:
        """Encrypt master key with password"""
        salt = secrets.token_bytes(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key_encryption_key = kdf.derive(password.encode())
        
        cipher = Cipher(algorithms.AES(key_encryption_key), modes.GCM(secrets.token_bytes(12)))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(key) + encryptor.finalize()
        
        return salt + encryptor.nonce + encryptor.tag + ciphertext

    def _decrypt_master_key(self, encrypted_key: bytes, password: str) -> bytes:
        """Decrypt master key with password"""
        salt = encrypted_key[:16]
        nonce = encrypted_key[16:28]
        tag = encrypted_key[28:44]
        ciphertext = encrypted_key[44:]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key_encryption_key = kdf.derive(password.encode())
        
        cipher = Cipher(algorithms.AES(key_encryption_key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def _initialize_encryption_configs(self):
        """Initialize encryption configurations for different data classifications"""
        self.encryption_configs = {
            DataClassification.PUBLIC: EncryptionConfig(
                method=EncryptionMethod.FERNET,
                key_size=256,
                use_salt=False,
                compression=True
            ),
            DataClassification.INTERNAL: EncryptionConfig(
                method=EncryptionMethod.AES_256_GCM,
                key_size=256,
                use_salt=True,
                compression=False
            ),
            DataClassification.CONFIDENTIAL: EncryptionConfig(
                method=EncryptionMethod.AES_256_GCM,
                key_size=256,
                use_salt=True,
                compression=False
            ),
            DataClassification.RESTRICTED: EncryptionConfig(
                method=EncryptionMethod.CHACHA20_POLY1305,
                key_size=256,
                use_salt=True,
                compression=False
            ),
            DataClassification.TOP_SECRET: EncryptionConfig(
                method=EncryptionMethod.RSA_4096,
                key_size=4096,
                use_salt=True,
                compression=False
            )
        }

    async def initialize_redis(self, redis_url: str):
        """Initialize Redis connection for key caching"""
        try:
            self.redis_client = aioredis.from_url(redis_url)
            await self.redis_client.ping()
            self.logger.info("Redis connection established for key caching")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")

    async def encrypt_data(self, data: Union[str, bytes, Dict[str, Any]], 
                          classification: DataClassification = DataClassification.CONFIDENTIAL,
                          key_id: Optional[str] = None) -> EncryptedData:
        """
        Encrypt data based on classification level
        """
        try:
            # Prepare data for encryption
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            elif isinstance(data, dict):
                data_bytes = json.dumps(data).encode('utf-8')
            else:
                data_bytes = data
            
            # Get encryption configuration
            config = self.encryption_configs.get(classification)
            if not config:
                raise ValueError(f"No encryption configuration for classification: {classification}")
            
            # Generate or get encryption key
            if not key_id:
                key_id = await self._generate_encryption_key(config.method)
            
            encryption_key = await self._get_encryption_key(key_id)
            if not encryption_key:
                raise ValueError(f"Encryption key not found: {key_id}")
            
            # Encrypt data based on method
            if config.method == EncryptionMethod.FERNET:
                encrypted_data = await self._encrypt_fernet(data_bytes, encryption_key)
            elif config.method == EncryptionMethod.AES_256_GCM:
                encrypted_data = await self._encrypt_aes_gcm(data_bytes, encryption_key, config.use_salt)
            elif config.method == EncryptionMethod.CHACHA20_POLY1305:
                encrypted_data = await self._encrypt_chacha20(data_bytes, encryption_key)
            elif config.method in [EncryptionMethod.RSA_2048, EncryptionMethod.RSA_4096]:
                encrypted_data = await self._encrypt_rsa(data_bytes, encryption_key)
            else:
                raise ValueError(f"Unsupported encryption method: {config.method}")
            
            # Update key usage
            await self._update_key_usage(key_id)
            
            self.logger.debug(f"Data encrypted with method {config.method.value}")
            return encrypted_data
            
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            raise

    async def decrypt_data(self, encrypted_data: EncryptedData) -> bytes:
        """
        Decrypt data using the specified method
        """
        try:
            # Get decryption key
            decryption_key = await self._get_encryption_key(encrypted_data.key_id)
            if not decryption_key:
                raise ValueError(f"Decryption key not found: {encrypted_data.key_id}")
            
            # Decrypt data based on method
            if encrypted_data.method == EncryptionMethod.FERNET:
                data = await self._decrypt_fernet(encrypted_data, decryption_key)
            elif encrypted_data.method == EncryptionMethod.AES_256_GCM:
                data = await self._decrypt_aes_gcm(encrypted_data, decryption_key)
            elif encrypted_data.method == EncryptionMethod.CHACHA20_POLY1305:
                data = await self._decrypt_chacha20(encrypted_data, decryption_key)
            elif encrypted_data.method in [EncryptionMethod.RSA_2048, EncryptionMethod.RSA_4096]:
                data = await self._decrypt_rsa(encrypted_data, decryption_key)
            else:
                raise ValueError(f"Unsupported decryption method: {encrypted_data.method}")
            
            self.logger.debug(f"Data decrypted with method {encrypted_data.method.value}")
            return data
            
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            raise

    async def _generate_encryption_key(self, method: EncryptionMethod) -> str:
        """Generate encryption key for specified method"""
        try:
            key_id = secrets.token_hex(16)
            
            if method == EncryptionMethod.FERNET:
                key = Fernet.generate_key()
            elif method == EncryptionMethod.AES_256_GCM:
                key = secrets.token_bytes(32)  # 256 bits
            elif method == EncryptionMethod.CHACHA20_POLY1305:
                key = secrets.token_bytes(32)  # 256 bits
            elif method == EncryptionMethod.RSA_2048:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=default_backend()
                )
                key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
            elif method == EncryptionMethod.RSA_4096:
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=4096,
                    backend=default_backend()
                )
                key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
            else:
                raise ValueError(f"Unsupported key generation method: {method}")
            
            # Store key metadata
            key_metadata = EncryptionKey(
                key_id=key_id,
                method=method,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=self.key_rotation_interval),
                max_usage=self.max_key_usage
            )
            
            self.encryption_keys[key_id] = key_metadata
            
            # Store encrypted key
            await self._store_encryption_key(key_id, key)
            
            self.logger.info(f"Generated new encryption key: {key_id} ({method.value})")
            return key_id
            
        except Exception as e:
            self.logger.error(f"Key generation failed: {e}")
            raise

    async def _store_encryption_key(self, key_id: str, key: bytes):
        """Store encryption key securely"""
        try:
            # Encrypt key with master key
            f = Fernet(self.master_key)
            encrypted_key = f.encrypt(key)
            
            # Store to file
            key_path = self.key_storage_path / f"{key_id}.key"
            with open(key_path, 'wb') as f:
                f.write(encrypted_key)
            
            # Set secure permissions
            os.chmod(key_path, 0o600)
            
            # Cache in Redis if available
            if self.redis_client:
                await self.redis_client.setex(
                    f"encryption_key:{key_id}",
                    self.key_rotation_interval,
                    base64.b64encode(encrypted_key)
                )
            
            self.logger.debug(f"Encryption key stored: {key_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to store encryption key: {e}")
            raise

    async def _get_encryption_key(self, key_id: str) -> Optional[bytes]:
        """Get encryption key from storage"""
        try:
            # Try Redis cache first
            if self.redis_client:
                cached_key = await self.redis_client.get(f"encryption_key:{key_id}")
                if cached_key:
                    encrypted_key = base64.b64decode(cached_key)
                    f = Fernet(self.master_key)
                    return f.decrypt(encrypted_key)
            
            # Try file storage
            key_path = self.key_storage_path / f"{key_id}.key"
            if key_path.exists():
                with open(key_path, 'rb') as f:
                    encrypted_key = f.read()
                
                f = Fernet(self.master_key)
                key = f.decrypt(encrypted_key)
                
                # Cache in Redis if available
                if self.redis_client:
                    await self.redis_client.setex(
                        f"encryption_key:{key_id}",
                        self.key_rotation_interval,
                        base64.b64encode(encrypted_key)
                    )
                
                return key
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get encryption key: {e}")
            return None

    async def _update_key_usage(self, key_id: str):
        """Update key usage counter"""
        try:
            key_metadata = self.encryption_keys.get(key_id)
            if key_metadata:
                key_metadata.usage_count += 1
                
                # Check if key needs rotation
                if (key_metadata.max_usage and key_metadata.usage_count >= key_metadata.max_usage) or \
                   (key_metadata.expires_at and datetime.now() >= key_metadata.expires_at):
                    await self._rotate_key(key_id)
                    
        except Exception as e:
            self.logger.error(f"Failed to update key usage: {e}")

    async def _rotate_key(self, key_id: str):
        """Rotate encryption key"""
        try:
            key_metadata = self.encryption_keys.get(key_id)
            if not key_metadata:
                return
            
            # Generate new key
            new_key_id = await self._generate_encryption_key(key_metadata.method)
            
            # Mark old key as inactive
            key_metadata.is_active = False
            
            self.logger.info(f"Key rotated: {key_id} -> {new_key_id}")
            
        except Exception as e:
            self.logger.error(f"Key rotation failed: {e}")

    # Encryption method implementations
    async def _encrypt_fernet(self, data: bytes, key: bytes) -> EncryptedData:
        """Encrypt data using Fernet"""
        f = Fernet(key)
        encrypted_data = f.encrypt(data)
        
        return EncryptedData(
            data=encrypted_data,
            method=EncryptionMethod.FERNET,
            key_id="",  # Will be set by caller
            metadata={"algorithm": "Fernet"}
        )

    async def _decrypt_fernet(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt data using Fernet"""
        f = Fernet(key)
        return f.decrypt(encrypted_data.data)

    async def _encrypt_aes_gcm(self, data: bytes, key: bytes, use_salt: bool = True) -> EncryptedData:
        """Encrypt data using AES-256-GCM"""
        nonce = secrets.token_bytes(12)
        salt = secrets.token_bytes(16) if use_salt else None
        
        # Derive key with salt if used
        if salt:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            derived_key = kdf.derive(key)
        else:
            derived_key = key
        
        cipher = Cipher(algorithms.AES(derived_key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            method=EncryptionMethod.AES_256_GCM,
            key_id="",  # Will be set by caller
            salt=salt,
            nonce=nonce,
            tag=encryptor.tag,
            metadata={"algorithm": "AES-256-GCM"}
        )

    async def _decrypt_aes_gcm(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt data using AES-256-GCM"""
        # Derive key with salt if used
        if encrypted_data.salt:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=encrypted_data.salt,
                iterations=100000,
                backend=default_backend()
            )
            derived_key = kdf.derive(key)
        else:
            derived_key = key
        
        cipher = Cipher(algorithms.AES(derived_key), modes.GCM(encrypted_data.nonce, encrypted_data.tag))
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()

    async def _encrypt_chacha20(self, data: bytes, key: bytes) -> EncryptedData:
        """Encrypt data using ChaCha20-Poly1305"""
        nonce = secrets.token_bytes(12)
        
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        return EncryptedData(
            data=ciphertext,
            method=EncryptionMethod.CHACHA20_POLY1305,
            key_id="",  # Will be set by caller
            nonce=nonce,
            metadata={"algorithm": "ChaCha20-Poly1305"}
        )

    async def _decrypt_chacha20(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt data using ChaCha20-Poly1305"""
        cipher = Cipher(algorithms.ChaCha20(key, encrypted_data.nonce), mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data.data) + decryptor.finalize()

    async def _encrypt_rsa(self, data: bytes, key: bytes) -> EncryptedData:
        """Encrypt data using RSA"""
        private_key = serialization.load_pem_private_key(key, password=None, backend=default_backend())
        public_key = private_key.public_key()
        
        # RSA has size limitations, so we may need to chunk large data
        max_chunk_size = (private_key.key_size // 8) - 2 * (hashes.SHA256().digest_size) - 2
        
        encrypted_chunks = []
        for i in range(0, len(data), max_chunk_size):
            chunk = data[i:i + max_chunk_size]
            encrypted_chunk = public_key.encrypt(
                chunk,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            encrypted_chunks.append(encrypted_chunk)
        
        return EncryptedData(
            data=b''.join(encrypted_chunks),
            method=EncryptionMethod.RSA_2048 if private_key.key_size == 2048 else EncryptionMethod.RSA_4096,
            key_id="",  # Will be set by caller
            metadata={"algorithm": "RSA-OAEP", "key_size": private_key.key_size, "chunks": len(encrypted_chunks)}
        )

    async def _decrypt_rsa(self, encrypted_data: EncryptedData, key: bytes) -> bytes:
        """Decrypt data using RSA"""
        private_key = serialization.load_pem_private_key(key, password=None, backend=default_backend())
        
        # Determine chunk size
        chunk_size = private_key.key_size // 8
        chunks = encrypted_data.metadata.get("chunks", 1)
        
        decrypted_chunks = []
        for i in range(chunks):
            start = i * chunk_size
            end = start + chunk_size
            encrypted_chunk = encrypted_data.data[start:end]
            
            decrypted_chunk = private_key.decrypt(
                encrypted_chunk,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            decrypted_chunks.append(decrypted_chunk)
        
        return b''.join(decrypted_chunks)

    # Utility methods
    async def encrypt_string(self, text: str, classification: DataClassification = DataClassification.CONFIDENTIAL) -> str:
        """Encrypt string and return base64 encoded result"""
        encrypted_data = await self.encrypt_data(text, classification)
        return base64.b64encode(self._serialize_encrypted_data(encrypted_data)).decode('utf-8')

    async def decrypt_string(self, encrypted_text: str) -> str:
        """Decrypt base64 encoded string"""
        encrypted_data = self._deserialize_encrypted_data(base64.b64decode(encrypted_text))
        decrypted_data = await self.decrypt_data(encrypted_data)
        return decrypted_data.decode('utf-8')

    async def encrypt_json(self, data: Dict[str, Any], classification: DataClassification = DataClassification.CONFIDENTIAL) -> str:
        """Encrypt JSON data and return base64 encoded result"""
        encrypted_data = await self.encrypt_data(data, classification)
        return base64.b64encode(self._serialize_encrypted_data(encrypted_data)).decode('utf-8')

    async def decrypt_json(self, encrypted_text: str) -> Dict[str, Any]:
        """Decrypt base64 encoded JSON data"""
        encrypted_data = self._deserialize_encrypted_data(base64.b64decode(encrypted_text))
        decrypted_data = await self.decrypt_data(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))

    def _serialize_encrypted_data(self, encrypted_data: EncryptedData) -> bytes:
        """Serialize encrypted data for storage"""
        data_dict = {
            "data": base64.b64encode(encrypted_data.data).decode('utf-8'),
            "method": encrypted_data.method.value,
            "key_id": encrypted_data.key_id,
            "salt": base64.b64encode(encrypted_data.salt).decode('utf-8') if encrypted_data.salt else None,
            "nonce": base64.b64encode(encrypted_data.nonce).decode('utf-8') if encrypted_data.nonce else None,
            "tag": base64.b64encode(encrypted_data.tag).decode('utf-8') if encrypted_data.tag else None,
            "metadata": encrypted_data.metadata,
            "created_at": encrypted_data.created_at.isoformat()
        }
        return json.dumps(data_dict).encode('utf-8')

    def _deserialize_encrypted_data(self, data: bytes) -> EncryptedData:
        """Deserialize encrypted data from storage"""
        data_dict = json.loads(data.decode('utf-8'))
        return EncryptedData(
            data=base64.b64decode(data_dict["data"]),
            method=EncryptionMethod(data_dict["method"]),
            key_id=data_dict["key_id"],
            salt=base64.b64decode(data_dict["salt"]) if data_dict["salt"] else None,
            nonce=base64.b64decode(data_dict["nonce"]) if data_dict["nonce"] else None,
            tag=base64.b64decode(data_dict["tag"]) if data_dict["tag"] else None,
            metadata=data_dict["metadata"],
            created_at=datetime.fromisoformat(data_dict["created_at"])
        )

    async def rotate_all_keys(self):
        """Rotate all encryption keys"""
        try:
            for key_id in list(self.encryption_keys.keys()):
                await self._rotate_key(key_id)
            self.logger.info("All encryption keys rotated")
        except Exception as e:
            self.logger.error(f"Failed to rotate all keys: {e}")

    def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption system statistics"""
        return {
            "total_keys": len(self.encryption_keys),
            "active_keys": len([k for k in self.encryption_keys.values() if k.is_active]),
            "key_methods": {method.value: len([k for k in self.encryption_keys.values() if k.method == method]) 
                          for method in EncryptionMethod},
            "total_usage": sum(k.usage_count for k in self.encryption_keys.values())
        }

    async def cleanup_expired_keys(self):
        """Clean up expired encryption keys"""
        try:
            current_time = datetime.now()
            expired_keys = [
                key_id for key_id, key_metadata in self.encryption_keys.items()
                if key_metadata.expires_at and current_time > key_metadata.expires_at
            ]
            
            for key_id in expired_keys:
                # Remove from memory
                del self.encryption_keys[key_id]
                
                # Remove from file storage
                key_path = self.key_storage_path / f"{key_id}.key"
                if key_path.exists():
                    key_path.unlink()
                
                # Remove from Redis cache
                if self.redis_client:
                    await self.redis_client.delete(f"encryption_key:{key_id}")
                
                self.logger.info(f"Expired key cleaned up: {key_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired keys: {e}")


# Global encryption system instance
_global_encryption_system = None


def get_encryption_system() -> DataEncryptionSystem:
    """Get global encryption system instance"""
    global _global_encryption_system
    if _global_encryption_system is None:
        _global_encryption_system = DataEncryptionSystem()
    return _global_encryption_system


def initialize_encryption_system(config: Dict[str, Any]) -> DataEncryptionSystem:
    """Initialize encryption system with configuration"""
    global _global_encryption_system
    _global_encryption_system = DataEncryptionSystem(config)
    return _global_encryption_system


@asynccontextmanager
async def encrypted_context():
    """Context manager for encryption operations"""
    encryption_system = get_encryption_system()
    try:
        yield encryption_system
    finally:
        await encryption_system.cleanup_expired_keys() 