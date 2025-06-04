import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
from datetime import datetime, timedelta, date
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class PredictionResult:
    """ML prediction result"""
    route: str
    predicted_price: float
    confidence_interval: Tuple[float, float]
    confidence_score: float
    prediction_date: datetime
    model_version: str

@dataclass
class ModelMetrics:
    """Model performance metrics"""
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    mape: float  # Mean Absolute Percentage Error
    r2_score: float
    last_updated: datetime

class FlightPricePredictor:
    def __init__(self, db_manager, redis_client):
        """Initialize the flight price predictor."""
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.model_manager = ModelManager("models")

    async def prepare_training_data(self, route: str, days_back: int = 365) -> pd.DataFrame:
        """Prepare training data for the given route."""
        historical_data = await self.db_manager.get_historical_prices(route, days_back)
        df = pd.DataFrame(historical_data)
        return df

    async def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer features from the raw data."""
        df = self.extract_seasonal_features(df)
        df = self.extract_demand_indicators(df)
        df = self.extract_external_factors(df)
        return df

    async def train_price_model(self, route: str, model_type: str = 'random_forest') -> str:
        """Train a price prediction model for the given route."""
        df = await self.prepare_training_data(route)
        df = await self.engineer_features(df)
        X = df.drop('price', axis=1)
        y = df['price']
        model = RandomForestRegressor()
        model.fit(X, y)
        model_path = await self.model_manager.save_model(model, route, "latest")
        return model_path

    async def predict_future_prices(self, route: str, prediction_dates: List[date]) -> List[PredictionResult]:
        """Predict future prices for the given route and dates."""
        model = await self.model_manager.load_model(route)
        df = await self.prepare_training_data(route)
        df = await self.engineer_features(df)
        X = df.drop('price', axis=1)
        predictions = model.predict(X)
        confidence_intervals = await self.calculate_confidence_intervals(predictions, 0.1)
        return [PredictionResult(
            route=route,
            predicted_price=pred,
            confidence_interval=interval,
            confidence_score=0.8,  # Placeholder
            prediction_date=datetime.now(),
            model_version="latest"
        ) for pred, interval in zip(predictions, confidence_intervals)]

    async def calculate_confidence_intervals(self, predictions: np.array, model_uncertainty: float) -> List[Tuple[float, float]]:
        """Calculate confidence intervals for predictions."""
        return [(pred - model_uncertainty, pred + model_uncertainty) for pred in predictions]

    async def evaluate_model_performance(self, route: str) -> ModelMetrics:
        """Evaluate the performance of the model for a route."""
        df = await self.prepare_training_data(route)
        df = await self.engineer_features(df)
        X = df.drop('price', axis=1)
        y = df['price']
        model = await self.model_manager.load_model(route)
        y_pred = model.predict(X)
        mae = np.mean(np.abs(y - y_pred))
        rmse = np.sqrt(np.mean((y - y_pred) ** 2))
        mape = np.mean(np.abs((y - y_pred) / y)) * 100
        r2_score = model.score(X, y)
        return ModelMetrics(mae=mae, rmse=rmse, mape=mape, r2_score=r2_score, last_updated=datetime.now())

    async def retrain_model_if_needed(self, route: str, performance_threshold: float = 0.8) -> bool:
        """Retrain the model if performance falls below the threshold."""
        metrics = await self.evaluate_model_performance(route)
        if metrics.r2_score < performance_threshold:
            await self.train_price_model(route)
            return True
        return False

    async def get_feature_importance(self, route: str) -> Dict[str, float]:
        """Get feature importance for the model of a route."""
        model = await self.model_manager.load_model(route)
        return dict(zip(model.feature_names_in_, model.feature_importances_))

    async def detect_price_patterns(self, route: str) -> Dict[str, Any]:
        """Detect price patterns for a route."""
        df = await self.prepare_training_data(route)
        return {"patterns": df.describe().to_dict()}

    def extract_seasonal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract seasonal features from the data."""
        df['month'] = pd.to_datetime(df['date']).dt.month
        df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
        return df

    def extract_demand_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract demand indicators from the data."""
        df['demand'] = df['price'].rolling(window=7).mean()
        return df

    def extract_external_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract external factors such as fuel prices and holidays."""
        # Placeholder for external factors
        return df

class ModelManager:
    def __init__(self, model_storage_path: str):
        """Initialize the model manager."""
        self.model_storage_path = model_storage_path

    async def save_model(self, model: Any, route: str, version: str) -> str:
        """Save a trained model for a route and version."""
        model_path = f"{self.model_storage_path}/{route}_{version}.joblib"
        joblib.dump(model, model_path)
        return model_path

    async def load_model(self, route: str, version: str = 'latest'):
        """Load a model for a route and version."""
        model_path = f"{self.model_storage_path}/{route}_{version}.joblib"
        return joblib.load(model_path)

    async def list_model_versions(self, route: str) -> List[str]:
        """List all model versions for a route."""
        # Placeholder for listing model versions
        return ["latest"]

    async def schedule_retraining(self, route: str, schedule: str):
        """Schedule model retraining using a cron format."""
        # Placeholder for scheduling retraining
        pass

    async def compare_model_versions(self, route: str, versions: List[str]) -> Dict:
        """Compare different model versions for a route."""
        # Placeholder for comparing model versions
        return {"latest": 0.8} 