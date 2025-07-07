import importlib.util
import pytest

if importlib.util.find_spec("crawl4ai") is None:
    pytest.skip("crawl4ai not installed", allow_module_level=True)
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_route_crud():
    r = client.post("/routes", json={"origin": "THR", "destination": "MHD"})
    assert r.status_code == 200
    route_id = r.json()["id"]

    r = client.get("/routes")
    assert r.status_code == 200
    routes = r.json()["routes"]
    assert any(rt["id"] == route_id for rt in routes)

    r = client.delete(f"/routes/{route_id}")
    assert r.status_code == 200
