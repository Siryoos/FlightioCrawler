"""
API v1 - Rate Limits Router

Contains rate limiting management endpoints for v1 API
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from rate_limiter import RateLimitManager, get_rate_limit_manager
from api_versioning import APIVersion, api_versioned, add_api_version_headers

router = APIRouter(prefix="/api/v1/rate-limits", tags=["rate-limits-v1"])

# Request/Response Models
class RateLimitConfigRequest(BaseModel):
    """Rate limit configuration request model"""
    endpoint_type: str
    requests_per_minute: int
    requests_per_hour: int
    burst_limit: int

class WhitelistRequest(BaseModel):
    """Whitelist request model"""
    ip: str
    duration_seconds: int = 3600

class RateLimitResetRequest(BaseModel):
    """Rate limit reset request model"""
    client_ip: str
    endpoint_type: Optional[str] = None

@router.get("/stats")
@api_versioned(APIVersion.V1)
async def get_rate_limit_stats(
    request: Request,
    response: Response,
    endpoint_type: Optional[str] = Query(
        None, description="Specific endpoint type to get stats for"
    ),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Get rate limiting statistics
    
    Returns comprehensive rate limiting statistics including:
    - Request counts per endpoint type
    - Blocked requests
    - Current rate limit status
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        if endpoint_type:
            stats = await rate_limit_manager.get_endpoint_stats(endpoint_type)
            return {
                "endpoint_type": endpoint_type,
                "stats": stats,
                "timestamp": datetime.now().isoformat(),
                "version": "v1"
            }
        else:
            all_stats = await rate_limit_manager.get_all_stats()
            return {
                "stats": all_stats,
                "timestamp": datetime.now().isoformat(),
                "version": "v1"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rate limit stats: {str(e)}")

@router.get("/config")
@api_versioned(APIVersion.V1)
async def get_rate_limit_config(
    request: Request,
    response: Response
):
    """
    Get current rate limiting configuration
    
    Returns the current rate limiting configuration for all endpoint types.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        # Get rate limit configuration
        config = {
            "default": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "burst_limit": 10
            },
            "search": {
                "requests_per_minute": 30,
                "requests_per_hour": 500,
                "burst_limit": 5
            },
            "admin": {
                "requests_per_minute": 120,
                "requests_per_hour": 2000,
                "burst_limit": 20
            }
        }
        
        return {
            "config": config,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rate limit config: {str(e)}")

@router.put("/config")
@api_versioned(APIVersion.V1)
async def update_rate_limit_config(
    config_request: RateLimitConfigRequest,
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Update rate limiting configuration
    
    Updates the rate limiting configuration for a specific endpoint type.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await rate_limit_manager.update_config(
            endpoint_type=config_request.endpoint_type,
            requests_per_minute=config_request.requests_per_minute,
            requests_per_hour=config_request.requests_per_hour,
            burst_limit=config_request.burst_limit
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update rate limit configuration")
        
        return {
            "message": "Rate limit configuration updated successfully",
            "endpoint_type": config_request.endpoint_type,
            "config": {
                "requests_per_minute": config_request.requests_per_minute,
                "requests_per_hour": config_request.requests_per_hour,
                "burst_limit": config_request.burst_limit
            },
            "updated_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rate limit config: {str(e)}")

@router.get("/client/{client_ip}")
@api_versioned(APIVersion.V1)
async def get_client_rate_limit_status(
    client_ip: str,
    request: Request,
    response: Response,
    endpoint_type: str = Query(..., description="Endpoint type to check"),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Get rate limit status for a specific client
    
    Returns the current rate limit status for the specified client IP
    and endpoint type.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        status = await rate_limit_manager.get_client_status(client_ip, endpoint_type)
        
        return {
            "client_ip": client_ip,
            "endpoint_type": endpoint_type,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client status: {str(e)}")

@router.post("/reset")
@api_versioned(APIVersion.V1)
async def reset_client_rate_limits(
    reset_request: RateLimitResetRequest,
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Reset rate limits for a specific client
    
    Resets the rate limit counters for the specified client IP.
    Optionally reset only for a specific endpoint type.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await rate_limit_manager.reset_client_limits(
            client_ip=reset_request.client_ip,
            endpoint_type=reset_request.endpoint_type
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Client not found or no limits to reset")
        
        return {
            "message": "Rate limits reset successfully",
            "client_ip": reset_request.client_ip,
            "endpoint_type": reset_request.endpoint_type,
            "reset_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset rate limits: {str(e)}")

@router.get("/blocked")
@api_versioned(APIVersion.V1)
async def get_blocked_clients(
    request: Request,
    response: Response,
    limit: int = Query(100, description="Maximum number of blocked clients to return"),
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Get list of currently blocked clients
    
    Returns a list of client IPs that are currently blocked due to
    rate limit violations.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        blocked_clients = await rate_limit_manager.get_blocked_clients(limit=limit)
        
        return {
            "blocked_clients": blocked_clients,
            "count": len(blocked_clients),
            "limit": limit,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get blocked clients: {str(e)}")

@router.post("/whitelist")
@api_versioned(APIVersion.V1)
async def whitelist_ip(
    whitelist_request: WhitelistRequest,
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager),
):
    """
    Add IP to whitelist
    
    Adds the specified IP address to the rate limit whitelist,
    exempting it from rate limiting for the specified duration.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await rate_limit_manager.add_to_whitelist(
            ip=whitelist_request.ip,
            duration_seconds=whitelist_request.duration_seconds
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add IP to whitelist")
        
        expiry_time = datetime.now().timestamp() + whitelist_request.duration_seconds
        
        return {
            "message": "IP added to whitelist successfully",
            "ip": whitelist_request.ip,
            "duration_seconds": whitelist_request.duration_seconds,
            "expires_at": datetime.fromtimestamp(expiry_time).isoformat(),
            "whitelisted_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to whitelist IP: {str(e)}")

@router.get("/whitelist/{ip}")
@api_versioned(APIVersion.V1)
async def check_ip_whitelist_status(
    ip: str,
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager)
):
    """
    Check IP whitelist status
    
    Checks if the specified IP address is currently whitelisted
    and returns whitelist information.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        whitelist_info = await rate_limit_manager.check_whitelist_status(ip)
        
        return {
            "ip": ip,
            "whitelisted": whitelist_info.get("whitelisted", False),
            "expires_at": whitelist_info.get("expires_at"),
            "added_at": whitelist_info.get("added_at"),
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check whitelist status: {str(e)}")

@router.delete("/whitelist/{ip}")
@api_versioned(APIVersion.V1)
async def remove_from_whitelist(
    ip: str,
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager)
):
    """
    Remove IP from whitelist
    
    Removes the specified IP address from the rate limit whitelist.
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        success = await rate_limit_manager.remove_from_whitelist(ip)
        
        if not success:
            raise HTTPException(status_code=404, detail="IP not found in whitelist")
        
        return {
            "message": "IP removed from whitelist successfully",
            "ip": ip,
            "removed_at": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove IP from whitelist: {str(e)}")

@router.get("/metrics")
@api_versioned(APIVersion.V1)
async def get_rate_limit_metrics(
    request: Request,
    response: Response,
    rate_limit_manager: RateLimitManager = Depends(get_rate_limit_manager)
):
    """
    Get comprehensive rate limiting metrics
    
    Returns detailed metrics about rate limiting performance including:
    - Request volume by endpoint type
    - Blocking statistics
    - Response time impact
    - Top clients by request volume
    """
    try:
        add_api_version_headers(response, APIVersion.V1)
        
        metrics = await rate_limit_manager.get_comprehensive_metrics()
        
        return {
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
            "version": "v1"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rate limit metrics: {str(e)}") 