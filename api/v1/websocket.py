"""
WebSocket API for Real-Time Communication
Supports live crawler status, flight updates, system monitoring, and event broadcasting
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import time
import weakref
from collections import defaultdict, deque

from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.routing import APIRouter
import redis
from pydantic import BaseModel, Field

from ..auth import get_current_user
from security.authentication_system import User
from monitoring import CrawlerMonitor
from data_manager import DataManager
from adapters.strategies.exponential_backoff_strategies import execute_with_exponential_backoff


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/websocket", tags=["websocket"])


class MessageType(Enum):
    """WebSocket message types"""
    CRAWLER_STATUS = "crawler_status"
    FLIGHT_UPDATE = "flight_update"
    SYSTEM_METRICS = "system_metrics"
    ERROR_ALERT = "error_alert"
    HEARTBEAT = "heartbeat"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"
    NOTIFICATION = "notification"
    BULK_DATA = "bulk_data"
    COMMAND = "command"
    RESPONSE = "response"


class SubscriptionTopic(Enum):
    """Available subscription topics"""
    CRAWLER_STATUS = "crawler_status"
    FLIGHT_UPDATES = "flight_updates"
    SYSTEM_METRICS = "system_metrics"
    ERROR_ALERTS = "error_alerts"
    SITE_SPECIFIC = "site_specific"
    USER_NOTIFICATIONS = "user_notifications"
    ALL = "all"


@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    type: MessageType
    topic: SubscriptionTopic
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(int(time.time() * 1000)))
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type.value,
            "topic": self.topic.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "user_id": self.user_id
        }


@dataclass
class ClientConnection:
    """WebSocket client connection information"""
    websocket: WebSocket
    user_id: str
    connection_id: str
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    subscriptions: Set[SubscriptionTopic] = field(default_factory=set)
    is_active: bool = True
    message_count: int = 0
    error_count: int = 0


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.connections: Dict[str, ClientConnection] = {}
        self.topic_subscribers: Dict[SubscriptionTopic, Set[str]] = defaultdict(set)
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
        
        # Message queue for handling backpressure
        self.message_queue: deque = deque(maxlen=10000)
        self.broadcast_lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'last_reset': datetime.now()
        }
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._message_processor_task: Optional[asyncio.Task] = None
        
        # Start background tasks
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background tasks for maintenance"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._message_processor_task = asyncio.create_task(self._message_processor_loop())
    
    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """Connect a new WebSocket client"""
        connection_id = f"{user_id}_{int(time.time() * 1000)}"
        
        try:
            await websocket.accept()
            
            connection = ClientConnection(
                websocket=websocket,
                user_id=user_id,
                connection_id=connection_id
            )
            
            self.connections[connection_id] = connection
            self.user_connections[user_id].add(connection_id)
            
            # Update statistics
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.connections)
            
            self.logger.info(f"WebSocket connected: {connection_id} for user {user_id}")
            
            # Send welcome message
            welcome_message = WebSocketMessage(
                type=MessageType.NOTIFICATION,
                topic=SubscriptionTopic.USER_NOTIFICATIONS,
                data={
                    "message": "Connected to FlightIO real-time updates",
                    "connection_id": connection_id,
                    "server_time": datetime.now().isoformat()
                },
                user_id=user_id
            )
            
            await self._send_to_connection(connection_id, welcome_message)
            
            return connection_id
            
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            raise
    
    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket client"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        try:
            # Remove from all subscriptions
            for topic in connection.subscriptions:
                self.topic_subscribers[topic].discard(connection_id)
            
            # Remove from user connections
            self.user_connections[connection.user_id].discard(connection_id)
            
            # Clean up empty sets
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
            
            # Remove connection
            del self.connections[connection_id]
            
            # Update statistics
            self.stats['active_connections'] = len(self.connections)
            
            self.logger.info(f"WebSocket disconnected: {connection_id}")
            
        except Exception as e:
            self.logger.error(f"Error during WebSocket disconnect: {e}")
    
    async def subscribe(self, connection_id: str, topic: SubscriptionTopic):
        """Subscribe a connection to a topic"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.subscriptions.add(topic)
        self.topic_subscribers[topic].add(connection_id)
        
        self.logger.info(f"Connection {connection_id} subscribed to {topic.value}")
        
        # Send subscription confirmation
        confirmation = WebSocketMessage(
            type=MessageType.SUBSCRIPTION,
            topic=topic,
            data={
                "status": "subscribed",
                "topic": topic.value,
                "message": f"Successfully subscribed to {topic.value}"
            },
            user_id=connection.user_id
        )
        
        await self._send_to_connection(connection_id, confirmation)
    
    async def unsubscribe(self, connection_id: str, topic: SubscriptionTopic):
        """Unsubscribe a connection from a topic"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.subscriptions.discard(topic)
        self.topic_subscribers[topic].discard(connection_id)
        
        self.logger.info(f"Connection {connection_id} unsubscribed from {topic.value}")
        
        # Send unsubscription confirmation
        confirmation = WebSocketMessage(
            type=MessageType.UNSUBSCRIPTION,
            topic=topic,
            data={
                "status": "unsubscribed",
                "topic": topic.value,
                "message": f"Successfully unsubscribed from {topic.value}"
            },
            user_id=connection.user_id
        )
        
        await self._send_to_connection(connection_id, confirmation)
    
    async def broadcast_to_topic(self, topic: SubscriptionTopic, message: WebSocketMessage):
        """Broadcast message to all subscribers of a topic"""
        if topic not in self.topic_subscribers:
            return
        
        subscribers = self.topic_subscribers[topic].copy()
        if not subscribers:
            return
        
        # Add to message queue for processing
        self.message_queue.append((topic, message, subscribers))
        
        self.logger.debug(f"Queued message for topic {topic.value} to {len(subscribers)} subscribers")
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Send message to all connections of a specific user"""
        if user_id not in self.user_connections:
            return
        
        user_connection_ids = self.user_connections[user_id].copy()
        
        for connection_id in user_connection_ids:
            await self._send_to_connection(connection_id, message)
    
    async def _send_to_connection(self, connection_id: str, message: WebSocketMessage):
        """Send message to a specific connection"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        try:
            message_data = message.to_dict()
            json_data = json.dumps(message_data)
            
            await connection.websocket.send_text(json_data)
            
            # Update statistics
            connection.message_count += 1
            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(json_data)
            
        except Exception as e:
            self.logger.error(f"Failed to send message to {connection_id}: {e}")
            connection.error_count += 1
            self.stats['messages_failed'] += 1
            
            # Disconnect if too many errors
            if connection.error_count > 5:
                await self.disconnect(connection_id)
    
    async def _heartbeat_loop(self):
        """Background task for heartbeat management"""
        while True:
            try:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
                current_time = datetime.now()
                expired_connections = []
                
                # Check for expired connections
                for connection_id, connection in self.connections.items():
                    if (current_time - connection.last_heartbeat).total_seconds() > 60:
                        expired_connections.append(connection_id)
                    else:
                        # Send heartbeat
                        heartbeat = WebSocketMessage(
                            type=MessageType.HEARTBEAT,
                            topic=SubscriptionTopic.USER_NOTIFICATIONS,
                            data={
                                "timestamp": current_time.isoformat(),
                                "server_status": "healthy"
                            },
                            user_id=connection.user_id
                        )
                        await self._send_to_connection(connection_id, heartbeat)
                
                # Clean up expired connections
                for connection_id in expired_connections:
                    self.logger.warning(f"Disconnecting expired connection: {connection_id}")
                    await self.disconnect(connection_id)
                    
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
    
    async def _cleanup_loop(self):
        """Background task for cleanup operations"""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                # Clean up empty topic subscriber sets
                empty_topics = [
                    topic for topic, subscribers in self.topic_subscribers.items()
                    if not subscribers
                ]
                
                for topic in empty_topics:
                    del self.topic_subscribers[topic]
                
                # Log statistics
                self.logger.info(f"WebSocket stats: {self.stats}")
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    async def _message_processor_loop(self):
        """Background task for processing message queue"""
        while True:
            try:
                if not self.message_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                async with self.broadcast_lock:
                    # Process messages in batches
                    batch_size = min(100, len(self.message_queue))
                    
                    for _ in range(batch_size):
                        if not self.message_queue:
                            break
                        
                        topic, message, subscribers = self.message_queue.popleft()
                        
                        # Send to all subscribers
                        tasks = []
                        for connection_id in subscribers:
                            if connection_id in self.connections:
                                tasks.append(self._send_to_connection(connection_id, message))
                        
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                self.logger.error(f"Error in message processor loop: {e}")
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            **self.stats,
            'active_connections': len(self.connections),
            'total_subscribers': sum(len(subscribers) for subscribers in self.topic_subscribers.values()),
            'topics_with_subscribers': len(self.topic_subscribers),
            'average_messages_per_connection': (
                self.stats['messages_sent'] / max(self.stats['total_connections'], 1)
            ),
            'queue_size': len(self.message_queue)
        }
    
    async def shutdown(self):
        """Shutdown WebSocket manager"""
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._message_processor_task:
            self._message_processor_task.cancel()
        
        # Close all connections
        for connection_id in list(self.connections.keys()):
            await self.disconnect(connection_id)
        
        self.logger.info("WebSocket manager shutdown complete")


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


class CrawlerStatusBroadcaster:
    """Broadcasts crawler status updates via WebSocket"""
    
    def __init__(self, manager: WebSocketManager, crawler_monitor: CrawlerMonitor):
        self.manager = manager
        self.crawler_monitor = crawler_monitor
        self.logger = logging.getLogger(__name__)
        
        # Status cache to avoid duplicate broadcasts
        self.status_cache: Dict[str, Dict[str, Any]] = {}
        
        # Start broadcasting task
        self._broadcasting_task = asyncio.create_task(self._broadcast_loop())
    
    async def _broadcast_loop(self):
        """Background task for broadcasting crawler status"""
        while True:
            try:
                await asyncio.sleep(5)  # Broadcast every 5 seconds
                
                # Get current status for all sites
                for site_name in self.crawler_monitor.get_monitored_sites():
                    current_status = await self._get_site_status(site_name)
                    
                    # Check if status changed
                    if self._status_changed(site_name, current_status):
                        self.status_cache[site_name] = current_status
                        
                        # Broadcast update
                        message = WebSocketMessage(
                            type=MessageType.CRAWLER_STATUS,
                            topic=SubscriptionTopic.CRAWLER_STATUS,
                            data={
                                "site": site_name,
                                "status": current_status,
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        
                        await self.manager.broadcast_to_topic(
                            SubscriptionTopic.CRAWLER_STATUS, message
                        )
                
            except Exception as e:
                self.logger.error(f"Error in crawler status broadcast loop: {e}")
    
    async def _get_site_status(self, site_name: str) -> Dict[str, Any]:
        """Get current status for a site"""
        try:
            status = self.crawler_monitor.get_site_status(site_name)
            return {
                "is_active": status.get("is_active", False),
                "success_rate": status.get("success_rate", 0.0),
                "last_crawl": status.get("last_crawl", ""),
                "error_count": status.get("error_count", 0),
                "response_time": status.get("response_time", 0.0)
            }
        except Exception as e:
            self.logger.error(f"Error getting status for {site_name}: {e}")
            return {"is_active": False, "error": str(e)}
    
    def _status_changed(self, site_name: str, current_status: Dict[str, Any]) -> bool:
        """Check if status has changed since last broadcast"""
        if site_name not in self.status_cache:
            return True
        
        previous_status = self.status_cache[site_name]
        
        # Check key status indicators
        key_fields = ["is_active", "success_rate", "error_count"]
        for field in key_fields:
            if current_status.get(field) != previous_status.get(field):
                return True
        
        return False


class FlightUpdateBroadcaster:
    """Broadcasts flight data updates via WebSocket"""
    
    def __init__(self, manager: WebSocketManager, data_manager: DataManager):
        self.manager = manager
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)
        
        # Track last broadcast time for each route
        self.last_broadcast: Dict[str, datetime] = {}
        
        # Start broadcasting task
        self._broadcasting_task = asyncio.create_task(self._broadcast_loop())
    
    async def _broadcast_loop(self):
        """Background task for broadcasting flight updates"""
        while True:
            try:
                await asyncio.sleep(10)  # Check for updates every 10 seconds
                
                # Get recent flight data
                recent_flights = await self._get_recent_flights()
                
                if recent_flights:
                    message = WebSocketMessage(
                        type=MessageType.FLIGHT_UPDATE,
                        topic=SubscriptionTopic.FLIGHT_UPDATES,
                        data={
                            "flights": recent_flights,
                            "count": len(recent_flights),
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    await self.manager.broadcast_to_topic(
                        SubscriptionTopic.FLIGHT_UPDATES, message
                    )
                
            except Exception as e:
                self.logger.error(f"Error in flight update broadcast loop: {e}")
    
    async def _get_recent_flights(self) -> List[Dict[str, Any]]:
        """Get recently updated flight data"""
        try:
            # Get flights updated in the last 30 seconds
            cutoff_time = datetime.now() - timedelta(seconds=30)
            
            # This would be implemented based on your data storage structure
            # For now, return empty list
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting recent flights: {e}")
            return []


class SystemMetricsBroadcaster:
    """Broadcasts system metrics via WebSocket"""
    
    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self.logger = logging.getLogger(__name__)
        
        # Start broadcasting task
        self._broadcasting_task = asyncio.create_task(self._broadcast_loop())
    
    async def _broadcast_loop(self):
        """Background task for broadcasting system metrics"""
        while True:
            try:
                await asyncio.sleep(30)  # Broadcast every 30 seconds
                
                metrics = await self._get_system_metrics()
                
                message = WebSocketMessage(
                    type=MessageType.SYSTEM_METRICS,
                    topic=SubscriptionTopic.SYSTEM_METRICS,
                    data={
                        "metrics": metrics,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                await self.manager.broadcast_to_topic(
                    SubscriptionTopic.SYSTEM_METRICS, message
                )
                
            except Exception as e:
                self.logger.error(f"Error in system metrics broadcast loop: {e}")
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            import psutil
            
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "active_connections": len(self.manager.connections),
                "messages_sent": self.manager.stats['messages_sent'],
                "uptime": (datetime.now() - self.manager.stats['last_reset']).total_seconds()
            }
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}


# Initialize broadcasters
crawler_monitor = CrawlerMonitor()  # This should be injected
data_manager = DataManager()  # This should be injected

crawler_status_broadcaster = CrawlerStatusBroadcaster(websocket_manager, crawler_monitor)
flight_update_broadcaster = FlightUpdateBroadcaster(websocket_manager, data_manager)
system_metrics_broadcaster = SystemMetricsBroadcaster(websocket_manager)


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """Main WebSocket endpoint for client connections"""
    connection_id = None
    
    try:
        # Connect client
        connection_id = await websocket_manager.connect(websocket, user_id)
        
        # Handle incoming messages
        while True:
            try:
                # Receive message with timeout
                message_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # 1 minute timeout
                )
                
                # Parse message
                message = json.loads(message_data)
                await handle_client_message(connection_id, message)
                
                # Update heartbeat
                if connection_id in websocket_manager.connections:
                    websocket_manager.connections[connection_id].last_heartbeat = datetime.now()
                
            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                if connection_id in websocket_manager.connections:
                    heartbeat = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        topic=SubscriptionTopic.USER_NOTIFICATIONS,
                        data={"status": "timeout_heartbeat"},
                        user_id=user_id
                    )
                    await websocket_manager._send_to_connection(connection_id, heartbeat)
                
            except WebSocketDisconnect:
                logger.info(f"Client {connection_id} disconnected")
                break
                
            except Exception as e:
                logger.error(f"Error handling message from {connection_id}: {e}")
                error_message = WebSocketMessage(
                    type=MessageType.ERROR_ALERT,
                    topic=SubscriptionTopic.USER_NOTIFICATIONS,
                    data={"error": str(e), "message": "Error processing your message"},
                    user_id=user_id
                )
                await websocket_manager._send_to_connection(connection_id, error_message)
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        
    finally:
        # Clean up connection
        if connection_id:
            await websocket_manager.disconnect(connection_id)


async def handle_client_message(connection_id: str, message: Dict[str, Any]):
    """Handle incoming client messages"""
    try:
        message_type = message.get("type")
        data = message.get("data", {})
        
        if message_type == "subscribe":
            topic_name = data.get("topic")
            if topic_name:
                try:
                    topic = SubscriptionTopic(topic_name)
                    await websocket_manager.subscribe(connection_id, topic)
                except ValueError:
                    logger.warning(f"Invalid subscription topic: {topic_name}")
        
        elif message_type == "unsubscribe":
            topic_name = data.get("topic")
            if topic_name:
                try:
                    topic = SubscriptionTopic(topic_name)
                    await websocket_manager.unsubscribe(connection_id, topic)
                except ValueError:
                    logger.warning(f"Invalid unsubscription topic: {topic_name}")
        
        elif message_type == "heartbeat":
            # Client heartbeat - just update timestamp
            if connection_id in websocket_manager.connections:
                websocket_manager.connections[connection_id].last_heartbeat = datetime.now()
        
        elif message_type == "command":
            # Handle client commands
            await handle_client_command(connection_id, data)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    except Exception as e:
        logger.error(f"Error handling client message: {e}")


async def handle_client_command(connection_id: str, command_data: Dict[str, Any]):
    """Handle client commands"""
    try:
        command = command_data.get("command")
        
        if command == "get_status":
            # Send current status
            status = await websocket_manager.get_connection_stats()
            
            response = WebSocketMessage(
                type=MessageType.RESPONSE,
                topic=SubscriptionTopic.USER_NOTIFICATIONS,
                data={"command": "get_status", "status": status}
            )
            
            await websocket_manager._send_to_connection(connection_id, response)
        
        elif command == "trigger_crawl":
            # Trigger a crawl operation
            site = command_data.get("site")
            params = command_data.get("params", {})
            
            # This would trigger actual crawling
            # For now, just send acknowledgment
            response = WebSocketMessage(
                type=MessageType.RESPONSE,
                topic=SubscriptionTopic.USER_NOTIFICATIONS,
                data={
                    "command": "trigger_crawl",
                    "site": site,
                    "status": "triggered",
                    "message": f"Crawl triggered for {site}"
                }
            )
            
            await websocket_manager._send_to_connection(connection_id, response)
        
        else:
            logger.warning(f"Unknown command: {command}")
    
    except Exception as e:
        logger.error(f"Error handling client command: {e}")


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return await websocket_manager.get_connection_stats()


@router.post("/broadcast")
async def broadcast_message(
    topic: str,
    message: str,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Broadcast a message to all subscribers of a topic"""
    try:
        # Validate topic
        subscription_topic = SubscriptionTopic(topic)
        
        # Create message
        ws_message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            topic=subscription_topic,
            data={
                "message": message,
                "from": current_user.username,
                "broadcast": True
            },
            user_id=user_id
        )
        
        # Broadcast
        await websocket_manager.broadcast_to_topic(subscription_topic, ws_message)
        
        return {"status": "success", "message": "Message broadcasted"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid topic: {topic}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Broadcast failed: {str(e)}")


# Health check endpoint
@router.get("/health")
async def websocket_health():
    """WebSocket service health check"""
    return {
        "status": "healthy",
        "active_connections": len(websocket_manager.connections),
        "total_messages": websocket_manager.stats['messages_sent'],
        "uptime": (datetime.now() - websocket_manager.stats['last_reset']).total_seconds()
    } 