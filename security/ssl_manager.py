"""
Comprehensive SSL Certificate Management System for FlightIO Crawler
Handles SSL context creation, certificate verification, and error handling
"""

import ssl
import os
import logging
import certifi
import urllib3
from typing import Optional, Dict, Any, Union
from enum import Enum
from pathlib import Path
import aiohttp
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json


class SSLMode(Enum):
    """SSL verification modes"""
    STRICT = "strict"  # Full SSL verification (production)
    PERMISSIVE = "permissive"  # Verify but allow some flexibility
    BYPASS = "bypass"  # No SSL verification (development only)
    AUTO = "auto"  # Auto-detect based on environment


@dataclass
class SSLConfig:
    """SSL configuration settings"""
    mode: SSLMode = SSLMode.AUTO
    verify_hostname: bool = True
    verify_certificates: bool = True
    ca_bundle_path: Optional[str] = None
    custom_ca_paths: list = None
    timeout: int = 30
    retry_attempts: int = 3
    allow_self_signed: bool = False
    cipher_suites: Optional[str] = None
    protocol_versions: tuple = (ssl.PROTOCOL_TLS_CLIENT,)
    
    def __post_init__(self):
        if self.custom_ca_paths is None:
            self.custom_ca_paths = []


class SSLManager:
    """Comprehensive SSL management system"""
    
    def __init__(self, config: Optional[SSLConfig] = None):
        self.config = config or SSLConfig()
        self.logger = logging.getLogger(__name__)
        self._ssl_contexts: Dict[str, ssl.SSLContext] = {}
        self._verification_cache: Dict[str, Dict[str, Any]] = {}
        self._failed_hosts: Dict[str, datetime] = {}
        
        # Initialize SSL environment
        self._initialize_ssl_environment()
        
        # Create default SSL context
        self._create_default_context()
        
        self.logger.info(f"SSL Manager initialized with mode: {self.config.mode.value}")
    
    def _initialize_ssl_environment(self):
        """Initialize SSL environment and certificate paths"""
        try:
            # Set up certificate bundle path
            if not self.config.ca_bundle_path:
                # Use certifi bundle as default
                self.config.ca_bundle_path = certifi.where()
                self.logger.info(f"Using certifi CA bundle: {self.config.ca_bundle_path}")
            
            # Verify certificate bundle exists
            if not os.path.exists(self.config.ca_bundle_path):
                self.logger.warning(f"CA bundle not found: {self.config.ca_bundle_path}")
                self.config.ca_bundle_path = None
            
            # Configure urllib3 warnings based on mode
            if self.config.mode == SSLMode.BYPASS:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                self.logger.info("SSL warnings disabled for bypass mode")
            
            # Auto-detect mode if needed
            if self.config.mode == SSLMode.AUTO:
                self.config.mode = self._auto_detect_mode()
                self.logger.info(f"Auto-detected SSL mode: {self.config.mode.value}")
            
        except Exception as e:
            self.logger.error(f"Error initializing SSL environment: {e}")
            # Fallback to bypass mode on initialization error
            self.config.mode = SSLMode.BYPASS
    
    def _auto_detect_mode(self) -> SSLMode:
        """Auto-detect appropriate SSL mode based on environment"""
        # Check environment variables
        env_mode = os.getenv('SSL_MODE', '').lower()
        if env_mode in ['strict', 'permissive', 'bypass']:
            return SSLMode(env_mode)
        
        # Check if in development environment
        if os.getenv('ENVIRONMENT', '').lower() in ['development', 'dev', 'local']:
            return SSLMode.BYPASS
        
        # Check if SSL verification is explicitly disabled
        if os.getenv('SSL_VERIFY', 'true').lower() == 'false':
            return SSLMode.BYPASS
        
        # Check if certificates are available
        if not self.config.ca_bundle_path:
            return SSLMode.BYPASS
        
        # Default to permissive for better compatibility
        return SSLMode.PERMISSIVE
    
    def _create_default_context(self):
        """Create default SSL context"""
        try:
            context = self._create_ssl_context("default")
            self._ssl_contexts["default"] = context
            self.logger.info("Default SSL context created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create default SSL context: {e}")
            # Create bypass context as fallback
            self._ssl_contexts["default"] = self._create_bypass_context()
    
    def _create_ssl_context(self, context_name: str) -> ssl.SSLContext:
        """Create SSL context based on configuration"""
        if self.config.mode == SSLMode.BYPASS:
            return self._create_bypass_context()
        elif self.config.mode == SSLMode.PERMISSIVE:
            return self._create_permissive_context()
        elif self.config.mode == SSLMode.STRICT:
            return self._create_strict_context()
        else:
            # Default to permissive
            return self._create_permissive_context()
    
    def _create_bypass_context(self) -> ssl.SSLContext:
        """Create SSL context that bypasses verification"""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Allow weak ciphers for compatibility
        context.set_ciphers('ALL:@SECLEVEL=0')
        
        self.logger.debug("Created bypass SSL context")
        return context
    
    def _create_permissive_context(self) -> ssl.SSLContext:
        """Create SSL context with permissive verification"""
        context = ssl.create_default_context()
        
        # Set CA bundle if available
        if self.config.ca_bundle_path:
            context.load_verify_locations(self.config.ca_bundle_path)
        
        # Load custom CA certificates
        for ca_path in self.config.custom_ca_paths:
            if os.path.exists(ca_path):
                try:
                    context.load_verify_locations(ca_path)
                    self.logger.debug(f"Loaded custom CA: {ca_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to load custom CA {ca_path}: {e}")
        
        # Permissive settings
        context.check_hostname = self.config.verify_hostname
        context.verify_mode = ssl.CERT_REQUIRED if self.config.verify_certificates else ssl.CERT_NONE
        
        # Allow self-signed certificates if configured
        if self.config.allow_self_signed:
            context.verify_mode = ssl.CERT_OPTIONAL
        
        # Set cipher suites
        if self.config.cipher_suites:
            context.set_ciphers(self.config.cipher_suites)
        
        self.logger.debug("Created permissive SSL context")
        return context
    
    def _create_strict_context(self) -> ssl.SSLContext:
        """Create SSL context with strict verification"""
        context = ssl.create_default_context()
        
        # Set CA bundle
        if self.config.ca_bundle_path:
            context.load_verify_locations(self.config.ca_bundle_path)
        else:
            raise ValueError("CA bundle path required for strict mode")
        
        # Load custom CA certificates
        for ca_path in self.config.custom_ca_paths:
            if os.path.exists(ca_path):
                context.load_verify_locations(ca_path)
                self.logger.debug(f"Loaded custom CA: {ca_path}")
        
        # Strict settings
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Strong cipher suites
        if not self.config.cipher_suites:
            context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        else:
            context.set_ciphers(self.config.cipher_suites)
        
        self.logger.debug("Created strict SSL context")
        return context
    
    def get_ssl_context(self, context_name: str = "default") -> ssl.SSLContext:
        """Get SSL context by name"""
        if context_name not in self._ssl_contexts:
            self._ssl_contexts[context_name] = self._create_ssl_context(context_name)
        
        return self._ssl_contexts[context_name]
    
    def create_aiohttp_connector(self, **kwargs) -> aiohttp.TCPConnector:
        """Create aiohttp connector with SSL context"""
        ssl_context = self.get_ssl_context()
        
        # Remove timeout from kwargs as it doesn't belong to TCPConnector
        connector_kwargs = {
            'ssl': ssl_context,
            'limit': kwargs.get('limit', 100),
            'limit_per_host': kwargs.get('limit_per_host', 30),
            'ttl_dns_cache': kwargs.get('ttl_dns_cache', 300),
            'use_dns_cache': kwargs.get('use_dns_cache', True),
        }
        
        # Add any additional valid TCPConnector arguments
        valid_tcp_connector_args = [
            'ssl', 'limit', 'limit_per_host', 'ttl_dns_cache', 'use_dns_cache',
            'local_addr', 'resolver', 'family', 'ssl_context', 'fingerprint',
            'enable_cleanup_closed', 'force_close', 'keepalive_timeout'
        ]
        
        for key, value in kwargs.items():
            if key in valid_tcp_connector_args:
                connector_kwargs[key] = value
        
        return aiohttp.TCPConnector(**connector_kwargs)
    
    async def verify_ssl_connection(self, url: str, timeout: int = None) -> Dict[str, Any]:
        """Verify SSL connection to a URL"""
        timeout = timeout or self.config.timeout
        
        # Check cache first
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self._verification_cache:
            cache_entry = self._verification_cache[url_hash]
            if datetime.now() - cache_entry['timestamp'] < timedelta(hours=1):
                return cache_entry['result']
        
        result = {
            'url': url,
            'ssl_verified': False,
            'error': None,
            'certificate_info': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            connector = self.create_aiohttp_connector()
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(url) as response:
                    result['ssl_verified'] = True
                    result['status_code'] = response.status
                    result['response_headers'] = dict(response.headers)
                    
                    # Get certificate information if available
                    if hasattr(response, 'connection') and hasattr(response.connection, 'transport'):
                        transport = response.connection.transport
                        if hasattr(transport, 'get_extra_info'):
                            cert_info = transport.get_extra_info('ssl_object')
                            if cert_info:
                                result['certificate_info'] = self._extract_cert_info(cert_info)
        
        except ssl.SSLError as e:
            result['error'] = f"SSL Error: {str(e)}"
            result['error_type'] = 'ssl_error'
        except aiohttp.ClientSSLError as e:
            result['error'] = f"SSL Connection Error: {str(e)}"
            result['error_type'] = 'ssl_connection_error'
        except Exception as e:
            result['error'] = f"General Error: {str(e)}"
            result['error_type'] = 'general_error'
        
        # Cache result
        self._verification_cache[url_hash] = {
            'result': result,
            'timestamp': datetime.now()
        }
        
        return result
    
    def _extract_cert_info(self, ssl_object) -> Dict[str, Any]:
        """Extract certificate information from SSL object"""
        try:
            cert_info = {}
            
            # Get peer certificate
            peer_cert = ssl_object.getpeercert()
            if peer_cert:
                cert_info['subject'] = dict(x[0] for x in peer_cert.get('subject', []))
                cert_info['issuer'] = dict(x[0] for x in peer_cert.get('issuer', []))
                cert_info['serial_number'] = peer_cert.get('serialNumber')
                cert_info['not_before'] = peer_cert.get('notBefore')
                cert_info['not_after'] = peer_cert.get('notAfter')
                cert_info['subject_alt_names'] = peer_cert.get('subjectAltName', [])
            
            # Get cipher information
            cipher_info = ssl_object.cipher()
            if cipher_info:
                cert_info['cipher'] = {
                    'name': cipher_info[0],
                    'version': cipher_info[1],
                    'bits': cipher_info[2]
                }
            
            # Get protocol version
            cert_info['protocol_version'] = ssl_object.version()
            
            return cert_info
        except Exception as e:
            self.logger.warning(f"Failed to extract certificate info: {e}")
            return {}
    
    async def test_ssl_connectivity(self, urls: list) -> Dict[str, Any]:
        """Test SSL connectivity to multiple URLs"""
        results = {}
        
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.verify_ssl_connection(url))
            tasks.append((url, task))
        
        for url, task in tasks:
            try:
                result = await task
                results[url] = result
            except Exception as e:
                results[url] = {
                    'url': url,
                    'ssl_verified': False,
                    'error': str(e),
                    'error_type': 'task_error',
                    'timestamp': datetime.now().isoformat()
                }
        
        return results
    
    def get_ssl_statistics(self) -> Dict[str, Any]:
        """Get SSL statistics and diagnostics"""
        stats = {
            'config': {
                'mode': self.config.mode.value,
                'verify_hostname': self.config.verify_hostname,
                'verify_certificates': self.config.verify_certificates,
                'ca_bundle_path': self.config.ca_bundle_path,
                'custom_ca_paths': self.config.custom_ca_paths,
                'allow_self_signed': self.config.allow_self_signed
            },
            'contexts': {
                'total_contexts': len(self._ssl_contexts),
                'context_names': list(self._ssl_contexts.keys())
            },
            'verification_cache': {
                'total_entries': len(self._verification_cache),
                'cache_hits': sum(1 for entry in self._verification_cache.values() 
                                if entry['result']['ssl_verified'])
            },
            'failed_hosts': {
                'total_failed': len(self._failed_hosts),
                'failed_hosts': list(self._failed_hosts.keys())
            }
        }
        
        return stats
    
    def clear_cache(self):
        """Clear verification cache"""
        self._verification_cache.clear()
        self._failed_hosts.clear()
        self.logger.info("SSL verification cache cleared")
    
    def export_diagnostics(self, filepath: str):
        """Export SSL diagnostics to file"""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'ssl_statistics': self.get_ssl_statistics(),
            'system_info': {
                'python_ssl_version': ssl.OPENSSL_VERSION,
                'ssl_context_available': hasattr(ssl, 'create_default_context'),
                'certifi_version': certifi.__version__ if hasattr(certifi, '__version__') else 'unknown'
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(diagnostics, f, indent=2)
        
        self.logger.info(f"SSL diagnostics exported to {filepath}")


# Global SSL manager instance
ssl_manager = SSLManager()


def get_ssl_manager() -> SSLManager:
    """Get global SSL manager instance"""
    return ssl_manager


def create_ssl_context(mode: Union[str, SSLMode] = None) -> ssl.SSLContext:
    """Create SSL context with specified mode"""
    if isinstance(mode, str):
        mode = SSLMode(mode)
    
    if mode:
        config = SSLConfig(mode=mode)
        manager = SSLManager(config)
        return manager.get_ssl_context()
    else:
        return ssl_manager.get_ssl_context()


def create_aiohttp_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create aiohttp connector with SSL context"""
    return ssl_manager.create_aiohttp_connector(**kwargs)


async def verify_ssl_connection(url: str, timeout: int = 30) -> Dict[str, Any]:
    """Verify SSL connection to URL"""
    return await ssl_manager.verify_ssl_connection(url, timeout)


# Convenience functions for backward compatibility
def create_bypass_ssl_context() -> ssl.SSLContext:
    """Create SSL context that bypasses verification"""
    return create_ssl_context(SSLMode.BYPASS)


def create_permissive_ssl_context() -> ssl.SSLContext:
    """Create SSL context with permissive verification"""
    return create_ssl_context(SSLMode.PERMISSIVE)


def create_strict_ssl_context() -> ssl.SSLContext:
    """Create SSL context with strict verification"""
    return create_ssl_context(SSLMode.STRICT) 