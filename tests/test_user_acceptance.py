import importlib.util
import pytest
if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_search_user_flow(monkeypatch):
    async def fake_crawl(params):
        return [{"flight_number": "UA1"}]
    monkeypatch.setattr(main.crawler, "crawl_all_sites", fake_crawl)
    resp = client.post("/search", json={"origin":"THR","destination":"MHD","date":"2024-01-01"})
    assert resp.status_code == 200
    assert resp.json()["flights"][0]["flight_number"] == "UA1"
