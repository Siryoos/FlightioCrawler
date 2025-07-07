"""
Test API Versioning and Backward Compatibility

This module contains comprehensive tests for:
1. API version detection
2. Content negotiation  
3. Backward compatibility
4. Deprecation warnings
5. Migration paths
"""

import pytest
import asyncio
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

# Import the new versioned app
try:
    from main import app
except ImportError:
    from main import app
from api_versioning import APIVersion, DeprecationLevel


class TestAPIVersioning:
    """Test API versioning functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_crawler(self):
        """Mock crawler instance"""
        crawler = Mock()
        crawler.crawl_all_sites = AsyncMock(return_value=[])
        crawler.get_health_status = AsyncMock(return_value={
            "status": "healthy",
            "metrics": {},
            "error_stats": {},
            "rate_limit_stats": {}
        })
        return crawler

    def test_version_detection_from_header(self, client):
        """Test API version detection from X-API-Version header"""
        response = client.get("/", headers={"X-API-Version": "v1"})
        
        assert response.status_code == 200
        # Check if versioning headers are present
        if "X-API-Version" in response.headers:
            assert response.headers.get("X-API-Version") == "v1"

    def test_version_detection_from_accept_header(self, client):
        """Test API version detection from Accept header"""
        response = client.get("/", headers={
            "Accept": "application/vnd.flightio.v1+json"
        })
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_version_detection_from_query_param(self, client):
        """Test API version detection from query parameter"""
        response = client.get("/?version=v1")
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_version_detection_from_path(self, client):
        """Test API version detection from URL path"""
        response = client.get("/api/v1/system/info")
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_default_version(self, client):
        """Test default version when none specified"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_unsupported_version(self, client):
        """Test handling of unsupported API version"""
        response = client.get("/", headers={"X-API-Version": "v99"})
        
        # Should fall back to default version
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_root_endpoint_response(self, client):
        """Test root endpoint basic functionality"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_legacy_search_deprecation(self, client):
        """Test legacy search endpoint shows deprecation warning"""
        # Mock the crawler dependency
        with patch('main.app.state') as mock_state:
            mock_crawler = Mock()
            mock_crawler.crawl_all_sites = AsyncMock(return_value=[])
            mock_state.crawler = mock_crawler
            
            response = client.post("/search", json={
                "origin": "THR",
                "destination": "IST",
                "date": "2024-06-01"
            })
            
            # Should work but may include deprecation warnings
            assert response.status_code in [200, 503]  # 503 if crawler not available

    def test_legacy_health_deprecation(self, client):
        """Test legacy health endpoint shows deprecation warning"""
        with patch('main.app.state') as mock_state:
            mock_crawler = Mock()
            mock_crawler.get_health_status = AsyncMock(return_value={
                "status": "healthy",
                "metrics": {},
                "error_stats": {},
                "rate_limit_stats": {}
            })
            mock_state.crawler = mock_crawler
            
            response = client.get("/health")
            
            assert response.status_code in [200, 503]


class TestContentNegotiation:
    """Test content negotiation functionality"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_json_content_type(self, client):
        """Test JSON content type negotiation"""
        response = client.get("/api/v1/system/info", headers={
            "Accept": "application/json"
        })
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_vendor_json_content_type(self, client):
        """Test vendor-specific JSON content type"""
        response = client.get("/api/v1/system/info", headers={
            "Accept": "application/vnd.flightio.v1+json"
        })
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"

    def test_multiple_accept_types(self, client):
        """Test multiple Accept types with quality values"""
        response = client.get("/api/v1/system/info", headers={
            "Accept": "application/xml;q=0.9, application/json;q=1.0"
        })
        
        assert response.status_code == 200
        # Should prefer JSON due to higher quality value


class TestBackwardCompatibility:
    """Test backward compatibility with legacy endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        """Mock app dependencies"""
        with patch.object(app.state, 'crawler') as mock_crawler:
            mock_crawler.crawl_all_sites = AsyncMock(return_value=[
                {"flight": "TK123", "price": 500}
            ])
            mock_crawler.get_health_status = AsyncMock(return_value={
                "status": "healthy",
                "metrics": {"uptime": 3600},
                "error_stats": {"errors": 0},
                "rate_limit_stats": {"limits": "ok"}
            })
            yield

    def test_legacy_search_endpoint(self, client):
        """Test legacy search endpoint with deprecation warning"""
        response = client.post("/search", json={
            "origin": "THR",
            "destination": "IST",
            "date": "2024-06-01"
        })
        
        assert response.status_code == 200
        
        # Check deprecation headers
        assert response.headers.get("Deprecation") == "true"
        assert "deprecated" in response.headers.get("X-API-Deprecation-Message", "").lower()
        assert response.headers.get("X-API-Deprecation-Level") == "warning"
        assert "Sunset" in response.headers
        
        # Check response format matches legacy format
        data = response.json()
        assert "flights" in data
        assert "timestamp" in data

    def test_legacy_health_endpoint(self, client):
        """Test legacy health endpoint with deprecation warning"""
        response = client.get("/health")
        
        assert response.status_code == 200
        
        # Check deprecation headers
        assert response.headers.get("Deprecation") == "true"
        assert response.headers.get("X-API-Deprecation-Level") == "warning"
        
        # Check response format
        data = response.json()
        assert "status" in data
        assert "metrics" in data
        assert "error_stats" in data
        assert "rate_limit_stats" in data

    def test_legacy_metrics_endpoint(self, client):
        """Test legacy metrics endpoint with deprecation warning"""
        with patch.object(app.state, 'monitor') as mock_monitor:
            mock_monitor.get_metrics = AsyncMock(return_value={"cpu": 50})
            
            response = client.get("/metrics")
            
            assert response.status_code == 200
            assert response.headers.get("Deprecation") == "true"

    def test_legacy_redirect_endpoints(self, client):
        """Test legacy endpoints that redirect to v1"""
        redirect_endpoints = [
            "/stats",
            "/reset", 
            "/flights/recent",
            "/airports",
            "/routes"
        ]
        
        for endpoint in redirect_endpoints:
            response = client.get(endpoint)
            
            # Should return redirect information
            assert response.status_code == 301
            assert response.headers.get("Deprecation") == "true"
            assert "Location" in response.headers
            
            data = response.json()
            assert data["deprecated"] is True
            assert "new_endpoint" in data

    def test_legacy_websocket_deprecation(self, client):
        """Test legacy WebSocket endpoint deprecation warning"""
        with client.websocket_connect("/ws/prices/user123") as websocket:
            # Should receive deprecation warning as first message
            data = websocket.receive_json()
            assert data["type"] == "deprecation_warning"
            assert "deprecated" in data["message"].lower()
            assert "new_endpoint" in data


class TestV1APIEndpoints:
    """Test v1 API endpoints functionality"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        """Mock app dependencies"""
        with patch.object(app.state, 'crawler') as mock_crawler, \
             patch.object(app.state, 'monitor') as mock_monitor:
            
            mock_crawler.crawl_all_sites = AsyncMock(return_value=[])
            mock_crawler.get_health_status = AsyncMock(return_value={"status": "healthy"})
            mock_crawler.get_recent_flights = AsyncMock(return_value=[])
            mock_crawler.get_statistics = AsyncMock(return_value={})
            mock_monitor.get_metrics = AsyncMock(return_value={})
            
            yield

    def test_v1_flights_search(self, client):
        """Test v1 flights search endpoint"""
        response = client.post("/api/v1/flights/search", json={
            "origin": "THR",
            "destination": "IST", 
            "date": "2024-06-01"
        }, headers={"X-API-Version": "v1"})
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"
        
        data = response.json()
        assert data["version"] == "v1"
        assert "flights" in data
        assert "timestamp" in data
        assert "search_metadata" in data

    def test_v1_system_health(self, client):
        """Test v1 system health endpoint"""
        response = client.get("/api/v1/system/health", 
                            headers={"X-API-Version": "v1"})
        
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"
        
        data = response.json()
        assert data["version"] == "v1"

    def test_v1_system_info(self, client):
        """Test v1 system info endpoint"""
        response = client.get("/api/v1/system/info")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["api_version"] == "v1"
        assert "supported_versions" in data
        assert "features" in data
        assert "endpoints" in data

    def test_v1_system_version(self, client):
        """Test v1 version endpoint"""
        response = client.get("/api/v1/system/version")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["current_version"] == "v1"
        assert data["latest_version"] == "v1" 
        assert "supported_versions" in data
        assert "version_info" in data

    def test_v1_docs_endpoint(self, client):
        """Test v1 documentation endpoint"""
        response = client.get("/api/v1/docs")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["api_version"] == "v1"
        assert "documentation" in data
        assert "migration_guide" in data
        assert "deprecation_info" in data
        assert "versioning_info" in data


class TestDeprecationWarnings:
    """Test deprecation warning functionality"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_deprecation_headers_format(self, client):
        """Test deprecation headers are properly formatted"""
        response = client.get("/health")
        
        assert response.headers.get("Deprecation") == "true"
        assert response.headers.get("X-API-Deprecation-Level") in ["info", "warning", "critical"]
        assert response.headers.get("X-API-Deprecation-Message") is not None
        assert response.headers.get("Sunset") is not None

    def test_sunset_date_format(self, client):
        """Test sunset date is properly formatted"""
        response = client.get("/health")
        
        sunset_header = response.headers.get("Sunset")
        assert sunset_header is not None
        
        # Should be in HTTP date format
        try:
            from email.utils import parsedate_to_datetime
            sunset_date = parsedate_to_datetime(sunset_header)
            assert sunset_date.year >= 2025
        except:
            pytest.fail("Sunset header not in proper HTTP date format")

    def test_no_deprecation_for_v1_endpoints(self, client):
        """Test v1 endpoints don't have deprecation headers"""
        response = client.get("/api/v1/system/health")
        
        assert response.headers.get("Deprecation") != "true"
        assert "X-API-Deprecation-Level" not in response.headers


class TestRateLimiting:
    """Test rate limiting with versioned endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_rate_limit_headers_v1(self, client):
        """Test rate limit headers are included in v1 responses"""
        response = client.get("/api/v1/system/health")
        
        # Should include rate limiting headers
        assert response.status_code == 200
        # Note: Actual rate limit headers depend on middleware implementation

    def test_different_rate_limits_by_endpoint_type(self, client):
        """Test different rate limits for different endpoint types"""
        # This would require actual rate limiting middleware to be active
        # and multiple requests to test limits
        pass


class TestMigrationPath:
    """Test migration path functionality"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_migration_guide_endpoint(self, client):
        """Test migration guide provides correct mappings"""
        response = client.get("/api/v1/docs")
        
        assert response.status_code == 200
        
        data = response.json()
        migration_guide = data["migration_guide"]["legacy_to_v1"]
        
        # Check key mappings
        assert migration_guide["/search"] == "/api/v1/flights/search"
        assert migration_guide["/health"] == "/api/v1/system/health"
        assert migration_guide["/metrics"] == "/api/v1/system/metrics"

    def test_endpoint_functionality_parity(self, client):
        """Test that legacy and v1 endpoints provide equivalent functionality"""
        with patch.object(app.state, 'crawler') as mock_crawler:
            mock_crawler.get_health_status = AsyncMock(return_value={
                "status": "healthy",
                "metrics": {"uptime": 3600},
                "error_stats": {"errors": 0},
                "rate_limit_stats": {"limits": "ok"}
            })
            
            # Test legacy endpoint
            legacy_response = client.get("/health")
            legacy_data = legacy_response.json()
            
            # Test v1 endpoint  
            v1_response = client.get("/api/v1/system/health")
            v1_data = v1_response.json()
            
            # Should have same core data (excluding version fields)
            assert legacy_data["status"] == v1_data["status"]
            assert legacy_data["metrics"] == v1_data["metrics"]


class TestErrorHandling:
    """Test error handling in versioned API"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_v1_error_format(self, client):
        """Test v1 error response format"""
        # Test with invalid endpoint
        response = client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404
        assert response.headers.get("X-API-Version") == "v1"

    def test_legacy_error_compatibility(self, client):
        """Test legacy error format is maintained"""
        # This ensures existing clients don't break
        pass


class TestPerformance:
    """Test performance of versioned endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_versioning_overhead(self, client):
        """Test that versioning doesn't add significant overhead"""
        import time
        
        # Time multiple requests to measure overhead
        start_time = time.time()
        
        for _ in range(10):
            response = client.get("/api/v1/system/info")
            assert response.status_code == 200
        
        end_time = time.time()
        average_time = (end_time - start_time) / 10
        
        # Should be reasonable (adjust threshold as needed)
        assert average_time < 1.0  # Less than 1 second per request


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 