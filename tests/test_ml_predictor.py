import pytest
import pandas as pd
from ml_predictor import FlightPricePredictor

class DummyDB:
    async def get_historical_prices(self, route, days_back=365):
        return [{"date": "2023-11-06", "price": 100}]

class DummyRedis:
    pass
@pytest.mark.asyncio

async def test_extract_seasonal_features():
    predictor = FlightPricePredictor(DummyDB(), DummyRedis())
    df = pd.DataFrame({"date": ["2023-11-06"], "price": [100]})
    result = predictor.extract_seasonal_features(df)
    assert "month" in result.columns and "day_of_week" in result.columns
