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
