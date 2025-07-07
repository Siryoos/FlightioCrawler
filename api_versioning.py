"""
API Versioning Strategy and Utilities for FlightioCrawler

This module provides:
1. API version management
2. Content negotiation
3. Deprecation warnings
4. Backward compatibility helpers
"""

import warnings
from enum import Enum
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
from fastapi import Request, Response, HTTPException, Header
from fastapi.routing import APIRoute
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class APIVersion(str, Enum):
    """API Version enumeration"""
    V1 = "v1"
    V2 = "v2"  # For future use
    
    @classmethod
    def get_latest(cls) -> "APIVersion":
        """Get the latest API version"""
        return cls.V1
    
    @classmethod
    def get_supported_versions(cls) -> list["APIVersion"]:
        """Get all supported API versions"""
        return [cls.V1]
    
    def is_deprecated(self) -> bool:
        """Check if this version is deprecated"""
        # V1 is not deprecated yet
        return False

class ContentType(str, Enum):
    """Supported content types for API responses"""
    JSON = "application/json"
    XML = "application/xml"
    YAML = "application/yaml"
    
class DeprecationLevel(str, Enum):
    """Deprecation warning levels"""
    INFO = "info"       # Version will be deprecated in future
    WARNING = "warning" # Version is deprecated
    CRITICAL = "critical" # Version will be removed soon

class APIVersioningConfig:
    """Configuration for API versioning"""
    
    # Default version when none specified
    DEFAULT_VERSION = APIVersion.V1
    
    # Version detection methods (in order of priority)
    VERSION_DETECTION_METHODS = [
        "header",      # X-API-Version header
        "accept",      # Accept header with version
        "query",       # ?version=v1 query parameter
        "path"         # /api/v1/ path prefix
    ]
    
    # Deprecation settings
    DEPRECATION_WARNINGS = {
        # APIVersion.V0: DeprecationLevel.CRITICAL  # Example for future
    }
    
    # Content type mapping
    CONTENT_TYPE_MAPPING = {
        "application/json": ContentType.JSON,
        "application/xml": ContentType.XML,
        "application/yaml": ContentType.YAML,
        "text/yaml": ContentType.YAML,
    }

class DeprecationWarning:
    """Handles deprecation warnings for API endpoints"""
    
    def __init__(self, version: APIVersion, level: DeprecationLevel, 
                 message: str, sunset_date: Optional[datetime] = None):
        self.version = version
        self.level = level
        self.message = message
        self.sunset_date = sunset_date
    
    def to_header_dict(self) -> Dict[str, str]:
        """Convert to HTTP headers"""
        headers = {
            "Deprecation": "true",
            "X-API-Deprecation-Level": self.level.value,
            "X-API-Deprecation-Message": self.message,
        }
        
        if self.sunset_date:
            headers["Sunset"] = self.sunset_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        return headers

class APIVersionExtractor:
    """Extracts API version from various sources"""
    
    @staticmethod
    def from_header(request: Request) -> Optional[APIVersion]:
        """Extract version from X-API-Version header"""
        version_header = request.headers.get("X-API-Version")
        if version_header:
            try:
                return APIVersion(version_header.lower())
            except ValueError:
                pass
        return None
    
    @staticmethod
    def from_accept_header(request: Request) -> Optional[APIVersion]:
        """Extract version from Accept header"""
        accept_header = request.headers.get("Accept", "")
        # Look for application/vnd.flightio.v1+json pattern
        if "vnd.flightio" in accept_header:
            for version in APIVersion:
                if f"vnd.flightio.{version.value}" in accept_header:
                    return version
        return None
    
    @staticmethod
    def from_query_param(request: Request) -> Optional[APIVersion]:
        """Extract version from query parameter"""
        version_param = request.query_params.get("version")
        if version_param:
            try:
                return APIVersion(version_param.lower())
            except ValueError:
                pass
        return None
    
    @staticmethod
    def from_path(request: Request) -> Optional[APIVersion]:
        """Extract version from URL path"""
        path = request.url.path
        for version in APIVersion:
            if f"/api/{version.value}/" in path or f"/{version.value}/" in path:
                return version
        return None
    
    @classmethod
    def extract_version(cls, request: Request) -> APIVersion:
        """Extract API version using configured methods"""
        for method in APIVersioningConfig.VERSION_DETECTION_METHODS:
            version = None
            
            if method == "header":
                version = cls.from_header(request)
            elif method == "accept":
                version = cls.from_accept_header(request)
            elif method == "query":
                version = cls.from_query_param(request)
            elif method == "path":
                version = cls.from_path(request)
            
            if version and version in APIVersion.get_supported_versions():
                return version
        
        return APIVersioningConfig.DEFAULT_VERSION

class ContentNegotiator:
    """Handles content type negotiation"""
    
    @staticmethod
    def get_preferred_content_type(request: Request) -> ContentType:
        """Determine preferred content type from Accept header"""
        accept_header = request.headers.get("Accept", "")
        
        # Parse Accept header priorities
        accept_types = []
        for item in accept_header.split(","):
            media_type = item.split(";")[0].strip()
            # Simple quality parsing (q=0.8)
            quality = 1.0
            if "q=" in item:
                try:
                    quality = float(item.split("q=")[1].split(";")[0].strip())
                except (ValueError, IndexError):
                    quality = 1.0
            accept_types.append((media_type, quality))
        
        # Sort by quality (highest first)
        accept_types.sort(key=lambda x: x[1], reverse=True)
        
        # Find best match
        for media_type, _ in accept_types:
            if media_type in APIVersioningConfig.CONTENT_TYPE_MAPPING:
                return APIVersioningConfig.CONTENT_TYPE_MAPPING[media_type]
        
        return ContentType.JSON  # Default

def add_api_version_headers(response: Response, version: APIVersion, 
                          deprecation: Optional[DeprecationWarning] = None):
    """Add versioning headers to response"""
    response.headers["X-API-Version"] = version.value
    response.headers["X-API-Supported-Versions"] = ",".join([v.value for v in APIVersion.get_supported_versions()])
    
    if deprecation:
        for key, value in deprecation.to_header_dict().items():
            response.headers[key] = value

def api_versioned(version: APIVersion, 
                 deprecation: Optional[DeprecationWarning] = None):
    """Decorator for versioned API endpoints"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request and response from kwargs if available
            request = kwargs.get('request')
            response = kwargs.get('response')
            
            # Add version info to response if available
            if response:
                add_api_version_headers(response, version, deprecation)
            
            # Log deprecation warning
            if deprecation:
                logger.warning(f"Deprecated API endpoint called: {func.__name__} "
                             f"(version {version.value}): {deprecation.message}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class VersionedAPIRoute(APIRoute):
    """Custom API route that handles versioning"""
    
    def __init__(self, *args, version: APIVersion = None, 
                 deprecation: Optional[DeprecationWarning] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version or APIVersioningConfig.DEFAULT_VERSION
        self.deprecation = deprecation
    
    def get_route_handler(self):
        original_handler = super().get_route_handler()
        
        async def versioned_handler(request: Request) -> Response:
            # Extract requested version
            requested_version = APIVersionExtractor.extract_version(request)
            
            # Check if this route supports the requested version
            if requested_version != self.version:
                # Try to find compatible version or redirect
                if requested_version in APIVersion.get_supported_versions():
                    # Version mismatch but supported - could redirect or handle differently
                    pass
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported API version: {requested_version}. "
                               f"Supported versions: {[v.value for v in APIVersion.get_supported_versions()]}"
                    )
            
            # Call original handler
            response = await original_handler(request)
            
            # Add versioning headers
            add_api_version_headers(response, self.version, self.deprecation)
            
            return response
        
        return versioned_handler

# Utility functions for migration
def create_alias_endpoint(old_path: str, new_path: str, 
                         deprecation_warning: DeprecationWarning):
    """Create an alias endpoint that redirects to new path with deprecation warning"""
    def alias_handler(request: Request, response: Response):
        # Add deprecation headers
        for key, value in deprecation_warning.to_header_dict().items():
            response.headers[key] = value
        
        # Log deprecation usage
        logger.warning(f"Deprecated endpoint accessed: {old_path} -> {new_path}")
        
        # Return redirect response
        response.status_code = 301
        response.headers["Location"] = new_path
        return {"message": f"This endpoint has moved to {new_path}", 
                "deprecated": True}
    
    return alias_handler 