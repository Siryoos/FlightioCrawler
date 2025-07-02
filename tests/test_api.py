import importlib.util
import pytest
if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Iranian Flight Crawler" in response.text


def test_recent_flights_endpoint():
    response = client.get("/flights/recent?limit=1")
    assert response.status_code == 200
    assert "flights" in response.json()


def test_sites_status_link():
    response = client.get("/api/v1/sites/status")
    assert response.status_code == 200
    data = response.json()
    assert "sites" in data
    for info in data["sites"].values():
        assert "link" in info
        assert info["link"] == info.get("base_url", "")
