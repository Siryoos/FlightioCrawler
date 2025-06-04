from fastapi import WebSocket
import numpy as np
from typing import Set, Callable, List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import json

@dataclass
class PriceAlert:
    """Price alert configuration"""
    user_id: str
    route: str
    target_price: float
    alert_type: str  # 'below', 'above', 'change'
    notification_methods: List[str]  # ['email', 'websocket', 'sms']

@dataclass
class PriceAnomaly:
    """Detected price anomaly"""
    route: str
    current_price: float
    expected_price: float
    deviation_percent: float
    confidence_score: float
    detected_at: datetime

class PriceMonitor:
    def __init__(self, db_manager, redis_client):
        """Initialize the price monitor."""
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.monitoring_tasks = {}

    async def start_monitoring(self, routes: List[str], interval_minutes: int = 5):
        """Start monitoring prices for the given routes."""
        for route in routes:
            if route not in self.monitoring_tasks:
                self.monitoring_tasks[route] = asyncio.create_task(self._monitor_route(route, interval_minutes))

    async def stop_monitoring(self, routes: Optional[List[str]] = None):
        """Stop monitoring prices for the given routes or all if None."""
        if routes is None:
            routes = list(self.monitoring_tasks.keys())
        for route in routes:
            if route in self.monitoring_tasks:
                self.monitoring_tasks[route].cancel()
                del self.monitoring_tasks[route]

    async def add_price_alert(self, alert: PriceAlert) -> str:
        """Add a new price alert."""
        alert_id = f"alert:{alert.user_id}:{alert.route}"
        await self.redis_client.set(alert_id, json.dumps(alert.__dict__))
        return alert_id

    async def remove_price_alert(self, alert_id: str) -> bool:
        """Remove a price alert by ID."""
        return await self.redis_client.delete(alert_id) > 0

    async def detect_price_anomalies(self, route_prices: Dict[str, List[float]]) -> List[PriceAnomaly]:
        """Detect price anomalies for the given route prices."""
        anomalies = []
        for route, prices in route_prices.items():
            current_price = prices[-1]
            expected_price = np.mean(prices[:-1])  # Simple mean as expected price
            deviation = abs(current_price - expected_price) / expected_price * 100
            if deviation > 10:  # Threshold for anomaly
                anomalies.append(PriceAnomaly(
                    route=route,
                    current_price=current_price,
                    expected_price=expected_price,
                    deviation_percent=deviation,
                    confidence_score=0.8,  # Placeholder
                    detected_at=datetime.now()
                ))
        return anomalies

    async def send_websocket_update(self, websocket: WebSocket, price_data: Dict):
        """Send a price update via WebSocket."""
        await websocket.send_json(price_data)

    async def send_email_alert(self, user_email: str, alert_data: Dict):
        """Send a price alert via email."""
        # Placeholder for email sending logic
        print(f"Sending email to {user_email}: {alert_data}")

    async def generate_price_trend_chart(self, route: str, days: int = 30) -> Dict:
        """Generate a price trend chart for a route."""
        historical_data = await self.db_manager.get_historical_prices(route, days)
        return {"route": route, "chart_data": historical_data}

    async def calculate_price_statistics(self, route: str) -> Dict:
        """Calculate price statistics for a route."""
        historical_data = await self.db_manager.get_historical_prices(route)
        return {
            "mean": np.mean(historical_data),
            "std": np.std(historical_data),
            "min": np.min(historical_data),
            "max": np.max(historical_data)
        }

    async def _monitor_route(self, route: str, interval_minutes: int):
        """Background task to monitor prices for a route."""
        while True:
            try:
                current_price = await self.db_manager.get_current_price(route)
                await self.broadcast_price_update(route, {"price": current_price})
                await asyncio.sleep(interval_minutes * 60)
            except asyncio.CancelledError:
                break

class WebSocketManager:
    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Connect a user to the WebSocket manager."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Disconnect a user from the WebSocket manager."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_price_update(self, route: str, price_data: Dict):
        """Broadcast a price update to all connected users for a route."""
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                await websocket.send_json({"route": route, **price_data})

    async def send_personal_alert(self, user_id: str, alert_data: Dict):
        """Send a personal alert to a specific user."""
        if user_id in self.active_connections:
            for websocket in self.active_connections[user_id]:
                await websocket.send_json(alert_data) 