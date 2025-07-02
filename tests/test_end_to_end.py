import importlib.util
import pytest

if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
import pytest
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


@pytest.mark.asyncio
async def test_end_to_end(monkeypatch):
    # Mock crawler method to avoid external calls
    async def fake_crawl(params):
        return [{"flight_number": "E2E"}]

    monkeypatch.setattr(main.crawler, "crawl_all_sites", fake_crawl)
    response = client.post(
        "/search", json={"origin": "THR", "destination": "MHD", "date": "2024-01-01"}
    )
    assert response.status_code == 200
    assert response.json()["flights"][0]["flight_number"] == "E2E"
