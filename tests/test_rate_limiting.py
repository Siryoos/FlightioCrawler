"""
تست‌های جامع برای سیستم rate limiting
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request
from starlette.responses import Response
import redis
from datetime import datetime

from rate_limiter import (
    RateLimitMiddleware, 
    RateLimitManager, 
    RATE_LIMIT_CONFIGS,
    USER_TYPE_LIMITS
)

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock_redis = Mock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.pipeline = Mock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.keys = AsyncMock(return_value=[])
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.hincrby = AsyncMock(return_value=1)
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.ttl = AsyncMock(return_value=60)
    
    # Mock pipeline
    pipeline_mock = Mock()
    pipeline_mock.get = Mock(return_value=pipeline_mock)
    pipeline_mock.incr = Mock(return_value=pipeline_mock)
    pipeline_mock.expire = Mock(return_value=pipeline_mock)
    pipeline_mock.hincrby = Mock(return_value=pipeline_mock)
    pipeline_mock.execute = AsyncMock(return_value=[0, 0, 0])
    mock_redis.pipeline.return_value = pipeline_mock
    
    return mock_redis

@pytest.fixture
def test_app():
    """Create test FastAPI app with rate limiting"""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "test successful"}
    
    @app.get("/search")
    async def search_endpoint():
        return {"results": []}
    
    @app.post("/crawl")
    async def crawl_endpoint():
        return {"status": "started"}
    
    return app

@pytest.fixture
def rate_limit_middleware(mock_redis):
    """Create rate limit middleware with mock Redis"""
    return RateLimitMiddleware(
        app=None,
        redis_client=mock_redis,
        enable_ip_whitelist=True,
        enable_user_type_limits=True
    )

@pytest.fixture
def rate_limit_manager(mock_redis):
    """Create rate limit manager with mock Redis"""
    return RateLimitManager(redis_client=mock_redis)

class TestRateLimitMiddleware:
    """تست‌های middleware rate limiting"""
    
    async def test_middleware_initialization(self, rate_limit_middleware):
        """تست initialization middleware"""
        assert rate_limit_middleware.redis is not None
        assert rate_limit_middleware.enable_ip_whitelist is True
        assert rate_limit_middleware.enable_user_type_limits is True
        assert "127.0.0.1" in rate_limit_middleware.ip_whitelist
    
    async def test_get_client_ip_from_headers(self, rate_limit_middleware):
        """تست استخراج IP از headers"""
        # Mock request with X-Forwarded-For
        request_mock = Mock()
        request_mock.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
        request_mock.client = Mock()
        request_mock.client.host = "127.0.0.1"
        
        ip = rate_limit_middleware._get_client_ip(request_mock)
        assert ip == "192.168.1.100"
        
        # Mock request with X-Real-IP
        request_mock.headers = {"X-Real-IP": "192.168.1.200"}
        ip = rate_limit_middleware._get_client_ip(request_mock)
        assert ip == "192.168.1.200"
        
        # Mock request without headers
        request_mock.headers = {}
        ip = rate_limit_middleware._get_client_ip(request_mock)
        assert ip == "127.0.0.1"
    
    async def test_ip_whitelist_check(self, rate_limit_middleware):
        """تست بررسی IP whitelist"""
        # Test localhost
        assert rate_limit_middleware._is_whitelisted_ip("127.0.0.1") is True
        assert rate_limit_middleware._is_whitelisted_ip("::1") is True
        assert rate_limit_middleware._is_whitelisted_ip("localhost") is True
        
        # Test private IP ranges
        assert rate_limit_middleware._is_whitelisted_ip("192.168.1.1") is True
        assert rate_limit_middleware._is_whitelisted_ip("10.0.0.1") is True
        assert rate_limit_middleware._is_whitelisted_ip("172.16.0.1") is True
        
        # Test public IP
        assert rate_limit_middleware._is_whitelisted_ip("8.8.8.8") is False
    
    async def test_endpoint_type_detection(self, rate_limit_middleware):
        """تست تشخیص نوع endpoint"""
        assert rate_limit_middleware._get_endpoint_type("/search") == "search"
        assert rate_limit_middleware._get_endpoint_type("/search/intelligent") == "search"
        assert rate_limit_middleware._get_endpoint_type("/crawl") == "crawl"
        assert rate_limit_middleware._get_endpoint_type("/health") == "health"
        assert rate_limit_middleware._get_endpoint_type("/metrics") == "metrics"
        assert rate_limit_middleware._get_endpoint_type("/api/v1/something") == "admin"
        assert rate_limit_middleware._get_endpoint_type("/unknown") == "default"
    
    async def test_user_type_multiplier(self, rate_limit_middleware):
        """تست محاسبه multiplier بر اساس نوع کاربر"""
        # Anonymous user
        request_mock = Mock()
        request_mock.headers = {}
        multiplier = await rate_limit_middleware._get_user_type_multiplier(request_mock)
        assert multiplier == USER_TYPE_LIMITS["anonymous"]
        
        # User with API key
        request_mock.headers = {"X-API-Key": "test-key"}
        rate_limit_middleware.redis.hget = AsyncMock(return_value="premium")
        multiplier = await rate_limit_middleware._get_user_type_multiplier(request_mock)
        assert multiplier == USER_TYPE_LIMITS["premium"]
    
    async def test_redis_rate_limit_check(self, rate_limit_middleware):
        """تست بررسی rate limit با Redis"""
        config = RATE_LIMIT_CONFIGS["default"]
        
        # Test within limits
        rate_limit_middleware.redis.pipeline().execute = AsyncMock(return_value=[5, 50, 2])
        result = await rate_limit_middleware._check_redis_rate_limits(
            "test:minute", "test:hour", "test:burst", config
        )
        assert result["allowed"] is True
        assert "minute_remaining" in result
        
        # Test minute limit exceeded
        rate_limit_middleware.redis.pipeline().execute = AsyncMock(return_value=[60, 50, 2])
        result = await rate_limit_middleware._check_redis_rate_limits(
            "test:minute", "test:hour", "test:burst", config
        )
        assert result["allowed"] is False
        assert result["limit_type"] == "minute"
    
    async def test_local_rate_limit_fallback(self, rate_limit_middleware):
        """تست fallback به local cache"""
        config = RATE_LIMIT_CONFIGS["default"]
        client_ip = "192.168.1.100"
        endpoint_type = "search"
        
        # Test first request
        result = await rate_limit_middleware._check_local_rate_limits(client_ip, endpoint_type, config)
        assert result["allowed"] is True
        
        # Test within limits
        for i in range(5):
            result = await rate_limit_middleware._check_local_rate_limits(client_ip, endpoint_type, config)
            assert result["allowed"] is True
        
        # Test exceeding limits
        for i in range(config["requests_per_minute"]):
            await rate_limit_middleware._check_local_rate_limits(client_ip, endpoint_type, config)
        
        result = await rate_limit_middleware._check_local_rate_limits(client_ip, endpoint_type, config)
        assert result["allowed"] is False

class TestRateLimitManager:
    """تست‌های rate limit manager"""
    
    async def test_manager_initialization(self, rate_limit_manager):
        """تست initialization manager"""
        assert rate_limit_manager.redis is not None
    
    async def test_get_rate_limit_stats(self, rate_limit_manager):
        """تست دریافت آمار rate limiting"""
        # Mock Redis response
        rate_limit_manager.redis.hgetall = AsyncMock(return_value={
            "requests_success": "100",
            "requests_error": "5",
            "total_requests": "105"
        })
        
        stats = await rate_limit_manager.get_rate_limit_stats("search")
        assert "search" in stats
        assert stats["search"]["total_requests"] == "105"
    
    async def test_get_client_status(self, rate_limit_manager):
        """تست دریافت وضعیت کلاینت"""
        rate_limit_manager.redis.pipeline().execute = AsyncMock(return_value=[
            5, 50, 2, 55, 3550, 58
        ])
        
        status = await rate_limit_manager.get_client_rate_limit_status("192.168.1.100", "search")
        assert status["client_ip"] == "192.168.1.100"
        assert status["endpoint_type"] == "search"
        assert status["minute_requests"] == 5
        assert status["hour_requests"] == 50
        assert "minute_remaining" in status
    
    async def test_reset_client_limits(self, rate_limit_manager):
        """تست ریست کردن محدودیت‌های کلاینت"""
        rate_limit_manager.redis.keys = AsyncMock(return_value=["key1", "key2"])
        rate_limit_manager.redis.delete = AsyncMock(return_value=2)
        rate_limit_manager.redis.exists = AsyncMock(return_value=True)
        
        result = await rate_limit_manager.reset_client_rate_limits("192.168.1.100", "search")
        assert "message" in result
        assert result["client_ip"] == "192.168.1.100"
        assert result["reset_count"] > 0
    
    async def test_update_config(self, rate_limit_manager):
        """تست بروزرسانی تنظیمات"""
        new_config = {
            "requests_per_minute": 30,
            "requests_per_hour": 300,
            "burst_limit": 5
        }
        
        result = await rate_limit_manager.update_rate_limit_config("search", new_config)
        assert "message" in result
        assert result["endpoint_type"] == "search"
        assert result["new_config"]["requests_per_minute"] == 30
    
    async def test_whitelist_operations(self, rate_limit_manager):
        """تست عملیات whitelist"""
        # Test whitelisting IP
        result = await rate_limit_manager.whitelist_ip("192.168.1.100", 3600)
        assert result["ip"] == "192.168.1.100"
        assert result["duration"] == 3600
        
        # Test checking whitelist status
        rate_limit_manager.redis.exists = AsyncMock(return_value=1)
        is_whitelisted = await rate_limit_manager.is_ip_whitelisted("192.168.1.100")
        assert is_whitelisted is True
    
    async def test_get_blocked_clients(self, rate_limit_manager):
        """تست دریافت کلاینت‌های مسدود"""
        rate_limit_manager.redis.keys = AsyncMock(return_value=[
            "rate_limit:192.168.1.100:search:minute:123456",
            "rate_limit:192.168.1.101:crawl:hour:123456"
        ])
        rate_limit_manager.redis.get = AsyncMock(return_value="100")
        rate_limit_manager.redis.ttl = AsyncMock(return_value=30)
        
        result = await rate_limit_manager.get_blocked_clients(10)
        assert "blocked_clients" in result
        assert "total_found" in result

class TestIntegration:
    """تست‌های integration"""
    
    @pytest.mark.asyncio
    async def test_full_middleware_flow(self, test_app, mock_redis):
        """تست کامل جریان middleware"""
        # Add middleware to test app
        middleware = RateLimitMiddleware(
            app=test_app,
            redis_client=mock_redis,
            enable_ip_whitelist=True,
            enable_user_type_limits=True
        )
        test_app.add_middleware(RateLimitMiddleware)
        
        client = TestClient(test_app)
        
        # Test successful request
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Remaining-Minute" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_response(self, test_app, mock_redis):
        """تست پاسخ در صورت تجاوز از محدودیت"""
        # Mock Redis to return high count (exceeded limit)
        pipeline_mock = Mock()
        pipeline_mock.get = Mock(return_value=pipeline_mock)
        pipeline_mock.execute = AsyncMock(return_value=[100, 50, 2])  # Minute limit exceeded
        mock_redis.pipeline.return_value = pipeline_mock
        
        middleware = RateLimitMiddleware(
            app=test_app,
            redis_client=mock_redis,
            enable_ip_whitelist=False,  # Disable whitelist for testing
            enable_user_type_limits=True
        )
        
        # Create mock request
        request_mock = Mock()
        request_mock.client = Mock()
        request_mock.client.host = "192.168.1.100"
        request_mock.url = Mock()
        request_mock.url.path = "/search"
        request_mock.headers = {}
        
        # Mock call_next
        call_next_mock = AsyncMock()
        
        # Test middleware dispatch
        result = await middleware.dispatch(request_mock, call_next_mock)
        
        # Should return rate limit response
        assert hasattr(result, 'status_code')
        # call_next should not be called when rate limited
        call_next_mock.assert_not_called()

@pytest.mark.asyncio
async def test_rate_limit_config_validation():
    """تست اعتبارسنجی تنظیمات rate limit"""
    manager = RateLimitManager()
    
    # Test valid config
    valid_config = {
        "requests_per_minute": 30,
        "requests_per_hour": 300,
        "burst_limit": 5
    }
    result = await manager.update_rate_limit_config("search", valid_config)
    assert "error" not in result
    
    # Test invalid config - missing field
    invalid_config = {
        "requests_per_minute": 30,
        "requests_per_hour": 300
        # missing burst_limit
    }
    result = await manager.update_rate_limit_config("search", invalid_config)
    assert "error" in result
    
    # Test invalid config - negative value
    invalid_config = {
        "requests_per_minute": -10,
        "requests_per_hour": 300,
        "burst_limit": 5
    }
    result = await manager.update_rate_limit_config("search", invalid_config)
    assert "error" in result

@pytest.mark.asyncio
async def test_concurrent_requests():
    """تست درخواست‌های همزمان"""
    middleware = RateLimitMiddleware(
        app=None,
        redis_client=None,  # Use local fallback
        enable_ip_whitelist=False,
        enable_user_type_limits=False
    )
    
    client_ip = "192.168.1.100"
    endpoint_type = "search"
    config = RATE_LIMIT_CONFIGS[endpoint_type]
    
    # Simulate concurrent requests
    tasks = []
    for i in range(10):
        task = middleware._check_local_rate_limits(client_ip, endpoint_type, config)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # All should be allowed initially
    for result in results:
        assert result["allowed"] is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 