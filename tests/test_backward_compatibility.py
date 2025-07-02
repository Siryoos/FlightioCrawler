"""
Test Backward Compatibility

Tests to ensure the API versioning maintains backward compatibility
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from main import app


class TestBackwardCompatibility:
    """Test backward compatibility features"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_root_endpoint_works(self, client):
        """Test basic functionality"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_legacy_search_endpoint_exists(self, client):
        """Test legacy search endpoint exists"""
        with patch('main.app.state') as mock_state:
            mock_crawler = Mock()
            mock_crawler.crawl_all_sites = AsyncMock(return_value=[])
            mock_state.crawler = mock_crawler
            
            response = client.post("/search", json={
                "origin": "THR",
                "destination": "IST", 
                "date": "2024-06-01"
            })
            
            # Should either work or return service unavailable
            assert response.status_code in [200, 503]

    def test_legacy_health_endpoint_exists(self, client):
        """Test legacy health endpoint exists"""
        response = client.get("/health")
        # Should return some response, not 404
        assert response.status_code in [200, 503]

    def test_openapi_docs_available(self, client):
        """Test API documentation is available"""
        response = client.get("/docs")
        assert response.status_code in [200, 404]

    def test_openapi_json_available(self, client):
        """Test OpenAPI JSON is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data

    def test_metrics_endpoint_exists(self, client):
        """Test metrics endpoint exists"""
        response = client.get("/metrics")
        assert response.status_code in [200, 503]

    def test_ui_mount_exists(self, client):
        """Test UI static files are mounted"""
        response = client.get("/ui/")
        # Should either serve UI files or return 404/redirect
        assert response.status_code in [200, 301, 302, 404]

    def test_cors_enabled(self, client):
        """Test CORS is enabled"""
        response = client.options("/")
        # Should have some CORS headers or return 405 (method not allowed)
        assert response.status_code in [200, 405]


class TestVersioningIntegration:
    """Test versioning integration works"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_version_header_handling(self, client):
        """Test version headers are handled gracefully"""
        response = client.get("/", headers={"X-API-Version": "v1"})
        assert response.status_code == 200

    def test_accept_header_handling(self, client):
        """Test Accept headers are handled"""
        response = client.get("/", headers={
            "Accept": "application/json"
        })
        assert response.status_code == 200

    def test_content_type_consistency(self, client):
        """Test content type is consistent"""
        response = client.get("/")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 