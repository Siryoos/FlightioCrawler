from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from provider_insights import get_provider_insights, validate_provider_insights

app = FastAPI()


@app.get("/api/v1/provider-insights")
async def provider_insights_route(provider_type: str | None = None):
    data = get_provider_insights(provider_type)
    if provider_type and not data:
        raise HTTPException(status_code=404, detail="Provider type not found")
    return {"insights": data}


client = TestClient(app)


def test_provider_insights_api():
    resp = client.get("/api/v1/provider-insights?provider_type=flights")
    assert resp.status_code == 200
    data = resp.json()["insights"]
    assert "AirlineA" in data


def test_validate_provider_insights():
    data = get_provider_insights()
    errors = validate_provider_insights(data)
    assert errors == []
