"""
WebSocket connection manager for real-time communication
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    TELEMETRY = "telemetry"
    STATUS = "status"
    GPS = "gps"
    COMMAND = "command"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class WebSocketConnection:
    """WebSocket connection information"""
    websocket: WebSocket
    client_id: str
    connected_at: float
    last_ping: float
    subscriptions: Set[str]
    client_info: Dict[str, Any]


class WebSocketManager:
    """Manages WebSocket connections and real-time communication"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Connection management
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.connection_count = 0
        
        # Message handling
        self.message_handlers: Dict[str, List[callable]] = {}
        
        # Broadcasting
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()
        self.broadcast_task: Optional[asyncio.Task] = None
        
        # Heartbeat monitoring
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.heartbeat_interval = self.settings.WEBSOCKET_PING_INTERVAL
        
        # Statistics
        self.total_connections = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.connection_errors = 0
        
        # Start background tasks
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background tasks for WebSocket management"""
        self.broadcast_task = asyncio.create_task(self._broadcast_worker())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_worker())
    
    async def shutdown(self):
        """Shutdown WebSocket manager and close all connections"""
        logger.info("Shutting down WebSocket manager")
        
        # Cancel background tasks
        if self.broadcast_task:
            self.broadcast_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        # Close all connections
        for connection in list(self.active_connections.values()):
            try:
                await connection.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        self.active_connections.clear()
        logger.info("WebSocket manager shutdown complete")
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        
        # Generate client ID if not provided
        if not client_id:
            client_id = f"client_{int(time.time())}_{len(self.active_connections)}"
        
        # Check connection limit
        if len(self.active_connections) >= self.settings.WEBSOCKET_MAX_CONNECTIONS:
            await websocket.close(code=1008, reason="Connection limit exceeded")
            raise Exception("WebSocket connection limit exceeded")
        
        # Create connection record
        connection = WebSocketConnection(
            websocket=websocket,
            client_id=client_id,
            connected_at=time.time(),
            last_ping=time.time(),
            subscriptions=set(),
            client_info={}
        )
        
        self.active_connections[client_id] = connection
        self.total_connections += 1
        self.connection_count += 1
        
        logger.info(f"WebSocket client connected: {client_id}")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "client_id": client_id,
            "server_time": time.time(),
            "message": "Connected to AgroBot WebSocket"
        }, websocket)
        
        return client_id
    
    def disconnect(self, client_id: str):
        """Disconnect and unregister a WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.connection_count -= 1
            logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to a specific WebSocket connection"""
        try:
            if isinstance(message, dict):
                message_str = json.dumps(message)
            else:
                message_str = str(message)
            
            await websocket.send_text(message_str)
            self.total_messages_sent += 1
            
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.connection_errors += 1
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to a specific client by ID"""
        if client_id in self.active_connections:
            connection = self.active_connections[client_id]
            await self.send_personal_message(message, connection.websocket)
        else:
            logger.warning(f"Client {client_id} not found for message delivery")
    
    async def broadcast(self, message: Dict[str, Any], subscription_filter: Optional[str] = None):
        """Broadcast message to all connected clients or filtered by subscription"""
        try:
            # Add to broadcast queue for processing
            await self.broadcast_queue.put({
                "message": message,
                "filter": subscription_filter,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.error(f"Error queueing broadcast message: {e}")
    
    async def _broadcast_worker(self):
        """Background worker for processing broadcast messages"""
        while True:
            try:
                # Get message from queue
                broadcast_item = await self.broadcast_queue.get()
                message = broadcast_item["message"]
                subscription_filter = broadcast_item["filter"]
                
                # Prepare message
                if isinstance(message, dict):
                    message_str = json.dumps(message)
                else:
                    message_str = str(message)
                
                # Send to appropriate clients
                disconnected_clients = []
                
                for client_id, connection in self.active_connections.items():
                    try:
                        # Check subscription filter
                        if subscription_filter and subscription_filter not in connection.subscriptions:
                            continue
                        
                        await connection.websocket.send_text(message_str)
                        self.total_messages_sent += 1
                        
                    except WebSocketDisconnect:
                        disconnected_clients.append(client_id)
                    except Exception as e:
                        logger.error(f"Error broadcasting to client {client_id}: {e}")
                        disconnected_clients.append(client_id)
                        self.connection_errors += 1
                
                # Clean up disconnected clients
                for client_id in disconnected_clients:
                    self.disconnect(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast worker: {e}")
                await asyncio.sleep(1)
    
    async def _heartbeat_worker(self):
        """Background worker for sending heartbeat pings"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                current_time = time.time()
                disconnected_clients = []
                
                for client_id, connection in self.active_connections.items():
                    try:
                        # Check if client is still responsive
                        if current_time - connection.last_ping > self.heartbeat_interval * 2:
                            # Send ping
                            await connection.websocket.ping()
                            connection.last_ping = current_time
                        
                    except Exception as e:
                        logger.warning(f"Heartbeat failed for client {client_id}: {e}")
                        disconnected_clients.append(client_id)
                
                # Clean up unresponsive clients
                for client_id in disconnected_clients:
                    self.disconnect(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat worker: {e}")
                await asyncio.sleep(10)
    
    async def handle_message(self, websocket: WebSocket, message: str, client_id: str):
        """Handle incoming WebSocket message"""
        try:
            self.total_messages_received += 1
            
            # Parse message
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await self.send_personal_message({
                    "type": "error",
                    "message": "Invalid JSON format"
                }, websocket)
                return
            
            message_type = data.get("type")
            if not message_type:
                await self.send_personal_message({
                    "type": "error",
                    "message": "Message type required"
                }, websocket)
                return
            
            # Handle different message types
            if message_type == "subscribe":
                await self._handle_subscribe(client_id, data, websocket)
            elif message_type == "unsubscribe":
                await self._handle_unsubscribe(client_id, data, websocket)
            elif message_type == "ping":
                await self._handle_ping(client_id, websocket)
            elif message_type == "client_info":
                await self._handle_client_info(client_id, data)
            else:
                # Forward to registered handlers
                await self._forward_to_handlers(message_type, data, client_id, websocket)
            
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_personal_message({
                "type": "error",
                "message": f"Message handling error: {str(e)}"
            }, websocket)
    
    async def _handle_subscribe(self, client_id: str, data: Dict[str, Any], websocket: WebSocket):
        """Handle subscription request"""
        topics = data.get("topics", [])
        if not isinstance(topics, list):
            topics = [topics]
        
        if client_id in self.active_connections:
            connection = self.active_connections[client_id]
            connection.subscriptions.update(topics)
            
            await self.send_personal_message({
                "type": "subscription_confirmed",
                "topics": topics,
                "all_subscriptions": list(connection.subscriptions)
            }, websocket)
            
            logger.info(f"Client {client_id} subscribed to: {topics}")
    
    async def _handle_unsubscribe(self, client_id: str, data: Dict[str, Any], websocket: WebSocket):
        """Handle unsubscription request"""
        topics = data.get("topics", [])
        if not isinstance(topics, list):
            topics = [topics]
        
        if client_id in self.active_connections:
            connection = self.active_connections[client_id]
            for topic in topics:
                connection.subscriptions.discard(topic)
            
            await self.send_personal_message({
                "type": "unsubscription_confirmed",
                "topics": topics,
                "remaining_subscriptions": list(connection.subscriptions)
            }, websocket)
            
            logger.info(f"Client {client_id} unsubscribed from: {topics}")
    
    async def _handle_ping(self, client_id: str, websocket: WebSocket):
        """Handle ping message"""
        if client_id in self.active_connections:
            self.active_connections[client_id].last_ping = time.time()
        
        await self.send_personal_message({
            "type": "pong",
            "timestamp": time.time()
        }, websocket)
    
    async def _handle_client_info(self, client_id: str, data: Dict[str, Any]):
        """Handle client information update"""
        if client_id in self.active_connections:
            connection = self.active_connections[client_id]
            connection.client_info.update(data.get("info", {}))
            logger.info(f"Updated client info for {client_id}: {connection.client_info}")
    
    async def _forward_to_handlers(self, message_type: str, data: Dict[str, Any], 
                                  client_id: str, websocket: WebSocket):
        """Forward message to registered handlers"""
        handlers = self.message_handlers.get(message_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data, client_id, websocket)
                else:
                    handler(data, client_id, websocket)
            except Exception as e:
                logger.error(f"Error in message handler for {message_type}: {e}")
    
    def register_message_handler(self, message_type: str, handler: callable):
        """Register a handler for specific message type"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        
        self.message_handlers[message_type].append(handler)
        logger.info(f"Registered handler for message type: {message_type}")
    
    def unregister_message_handler(self, message_type: str, handler: callable):
        """Unregister a message handler"""
        if message_type in self.message_handlers:
            try:
                self.message_handlers[message_type].remove(handler)
                logger.info(f"Unregistered handler for message type: {message_type}")
            except ValueError:
                logger.warning(f"Handler not found for message type: {message_type}")
    
    async def send_telemetry_update(self, telemetry_data: Dict[str, Any]):
        """Send telemetry update to subscribed clients"""
        message = {
            "type": "telemetry_update",
            "timestamp": time.time(),
            "data": telemetry_data
        }
        await self.broadcast(message, "telemetry")
    
    async def send_status_update(self, status_data: Dict[str, Any]):
        """Send status update to subscribed clients"""
        message = {
            "type": "status_update",
            "timestamp": time.time(),
            "data": status_data
        }
        await self.broadcast(message, "status")
    
    async def send_gps_update(self, gps_data: Dict[str, Any]):
        """Send GPS update to subscribed clients"""
        message = {
            "type": "gps_update",
            "timestamp": time.time(),
            "data": gps_data
        }
        await self.broadcast(message, "gps")
    
    async def send_alert(self, alert_data: Dict[str, Any]):
        """Send alert to all connected clients"""
        message = {
            "type": "alert",
            "timestamp": time.time(),
            "data": alert_data
        }
        await self.broadcast(message)  # No filter - send to all
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about active connections"""
        connections_info = []
        
        for client_id, connection in self.active_connections.items():
            connections_info.append({
                "client_id": client_id,
                "connected_at": connection.connected_at,
                "last_ping": connection.last_ping,
                "subscriptions": list(connection.subscriptions),
                "client_info": connection.client_info,
                "connection_age": time.time() - connection.connected_at
            })
        
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "max_connections": self.settings.WEBSOCKET_MAX_CONNECTIONS,
            "messages_sent": self.total_messages_sent,
            "messages_received": self.total_messages_received,
            "connection_errors": self.connection_errors,
            "connections": connections_info
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "messages_sent": self.total_messages_sent,
            "messages_received": self.total_messages_received,
            "connection_errors": self.connection_errors,
            "broadcast_queue_size": self.broadcast_queue.qsize(),
            "heartbeat_interval": self.heartbeat_interval,
            "max_connections": self.settings.WEBSOCKET_MAX_CONNECTIONS
        }
    
    async def cleanup_inactive_connections(self):
        """Clean up inactive connections"""
        current_time = time.time()
        inactive_clients = []
        
        for client_id, connection in self.active_connections.items():
            # Consider connection inactive if no ping for 2x heartbeat interval
            if current_time - connection.last_ping > self.heartbeat_interval * 2:
                inactive_clients.append(client_id)
        
        for client_id in inactive_clients:
            logger.info(f"Cleaning up inactive connection: {client_id}")
            self.disconnect(client_id)
        
        return len(inactive_clients)