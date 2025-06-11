"""
Telemetry collection and management service
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from dataclasses import dataclass
import json

from app.core.mavlink.connection import MAVLinkManager
from app.websocket.manager import WebSocketManager
from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TelemetryDataPoint:
    """Single telemetry data point"""
    timestamp: float
    data_type: str
    data: Dict[str, Any]
    source: str = "mavlink"


class TelemetryService:
    """Service for collecting, storing, and streaming telemetry data"""
    
    def __init__(self, mavlink_manager: MAVLinkManager, websocket_manager: WebSocketManager):
        self.mavlink = mavlink_manager
        self.websocket = websocket_manager
        self.settings = get_settings()
        
        # Service state
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None
        self._streaming_task: Optional[asyncio.Task] = None
        
        # Data storage
        self.data_buffer = deque(maxlen=self.settings.TELEMETRY_BUFFER_SIZE)
        self.last_collection_time = 0.0
        
        # Statistics
        self.total_data_points = 0
        self.collection_errors = 0
        self.streaming_errors = 0
        
        # Callbacks for data processing
        self.data_callbacks: List[Callable[[TelemetryDataPoint], None]] = []
        
        # Collection configuration
        self.collection_interval = self.settings.TELEMETRY_INTERVAL
        self.enabled_data_types = {
            "gps": True,
            "attitude": True,
            "heartbeat": True,
            "system_status": True,
            "battery": True,
            "rc_channels": True
        }
    
    async def start(self):
        """Start telemetry collection service"""
        if self._running:
            logger.warning("Telemetry service is already running")
            return
        
        if not self.settings.TELEMETRY_ENABLED:
            logger.info("Telemetry collection is disabled in settings")
            return
        
        logger.info("Starting telemetry collection service")
        self._running = True
        
        # Start collection task
        self._collection_task = asyncio.create_task(self._collection_loop())
        
        # Start streaming task
        self._streaming_task = asyncio.create_task(self._streaming_loop())
        
        logger.info(f"Telemetry service started with {self.collection_interval}s interval")
    
    async def stop(self):
        """Stop telemetry collection service"""
        if not self._running:
            return
        
        logger.info("Stopping telemetry collection service")
        self._running = False
        
        # Cancel tasks
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Telemetry service stopped")
    
    def is_running(self) -> bool:
        """Check if telemetry service is running"""
        return self._running
    
    async def _collection_loop(self):
        """Main telemetry collection loop"""
        logger.info("Telemetry collection loop started")
        
        while self._running:
            try:
                await self._collect_telemetry()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.collection_errors += 1
                logger.error(f"Error in telemetry collection: {e}")
                await asyncio.sleep(1.0)  # Brief pause before retry
    
    async def _streaming_loop(self):
        """WebSocket streaming loop"""
        logger.info("Telemetry streaming loop started")
        
        while self._running:
            try:
                await self._stream_latest_data()
                await asyncio.sleep(1.0)  # Stream at 1Hz
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.streaming_errors += 1
                logger.error(f"Error in telemetry streaming: {e}")
                await asyncio.sleep(1.0)
    
    async def _collect_telemetry(self):
        """Collect telemetry data from all sources"""
        current_time = time.time()
        
        try:
            # Collect GPS data
            if self.enabled_data_types.get("gps", False) and self.mavlink.latest_gps:
                gps_data = self._format_gps_data(self.mavlink.latest_gps)
                data_point = TelemetryDataPoint(
                    timestamp=current_time,
                    data_type="gps",
                    data=gps_data
                )
                await self._store_data_point(data_point)
            
            # Collect attitude data
            if self.enabled_data_types.get("attitude", False) and self.mavlink.latest_attitude:
                attitude_data = self._format_attitude_data(self.mavlink.latest_attitude)
                data_point = TelemetryDataPoint(
                    timestamp=current_time,
                    data_type="attitude",
                    data=attitude_data
                )
                await self._store_data_point(data_point)
            
            # Collect heartbeat data
            if self.enabled_data_types.get("heartbeat", False) and self.mavlink.latest_heartbeat:
                heartbeat_data = self._format_heartbeat_data(self.mavlink.latest_heartbeat)
                data_point = TelemetryDataPoint(
                    timestamp=current_time,
                    data_type="heartbeat",
                    data=heartbeat_data
                )
                await self._store_data_point(data_point)
            
            # Collect system status
            if self.enabled_data_types.get("system_status", False):
                system_data = self._collect_system_status()
                data_point = TelemetryDataPoint(
                    timestamp=current_time,
                    data_type="system_status",
                    data=system_data
                )
                await self._store_data_point(data_point)
            
            self.last_collection_time = current_time
            
        except Exception as e:
            logger.error(f"Error collecting telemetry data: {e}")
            raise
    
    async def _store_data_point(self, data_point: TelemetryDataPoint):
        """Store telemetry data point"""
        # Add to buffer
        self.data_buffer.append(data_point)
        self.total_data_points += 1
        
        # Call registered callbacks
        for callback in self.data_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data_point)
                else:
                    callback(data_point)
            except Exception as e:
                logger.error(f"Error in telemetry callback: {e}")
    
    async def _stream_latest_data(self):
        """Stream latest telemetry data via WebSocket"""
        if not self.data_buffer:
            return
        
        try:
            # Get latest data points (last 10)
            latest_data = list(self.data_buffer)[-10:]
            
            # Format for WebSocket transmission
            stream_data = {
                "type": "telemetry_update",
                "timestamp": time.time(),
                "data_points": [
                    {
                        "timestamp": dp.timestamp,
                        "data_type": dp.data_type,
                        "data": dp.data,
                        "source": dp.source
                    }
                    for dp in latest_data
                ]
            }
            
            # Send to all connected WebSocket clients
            await self.websocket.broadcast(json.dumps(stream_data))
            
        except Exception as e:
            logger.error(f"Error streaming telemetry data: {e}")
            raise
    
    def _format_gps_data(self, gps_data) -> Dict[str, Any]:
        """Format GPS data for telemetry"""
        return {
            "latitude": gps_data.lat / 1e7,
            "longitude": gps_data.lon / 1e7,
            "altitude": gps_data.alt / 1000.0,
            "relative_altitude": gps_data.relative_alt / 1000.0,
            "ground_speed": gps_data.vel / 100.0,
            "heading": gps_data.cog / 100.0,
            "satellites": gps_data.satellites_visible,
            "hdop": gps_data.hdop,
            "vdop": gps_data.vdop,
            "fix_type": gps_data.fix_type
        }
    
    def _format_attitude_data(self, attitude_data) -> Dict[str, Any]:
        """Format attitude data for telemetry"""
        return {
            "roll": attitude_data.roll,
            "pitch": attitude_data.pitch,
            "yaw": attitude_data.yaw,
            "roll_speed": attitude_data.rollspeed,
            "pitch_speed": attitude_data.pitchspeed,
            "yaw_speed": attitude_data.yawspeed,
            "roll_degrees": attitude_data.roll * 180.0 / 3.14159,
            "pitch_degrees": attitude_data.pitch * 180.0 / 3.14159,
            "yaw_degrees": attitude_data.yaw * 180.0 / 3.14159
        }
    
    def _format_heartbeat_data(self, heartbeat_data) -> Dict[str, Any]:
        """Format heartbeat data for telemetry"""
        return {
            "system_id": heartbeat_data.system_id,
            "component_id": heartbeat_data.component_id,
            "type": heartbeat_data.type,
            "autopilot": heartbeat_data.autopilot,
            "base_mode": heartbeat_data.base_mode,
            "custom_mode": heartbeat_data.custom_mode,
            "system_status": heartbeat_data.system_status,
            "armed": bool(heartbeat_data.base_mode & 128),
            "mavlink_version": heartbeat_data.mavlink_version
        }
    
    def _collect_system_status(self) -> Dict[str, Any]:
        """Collect system status information"""
        import psutil
        
        # Get basic system metrics
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "timestamp": time.time(),
            "mavlink_connected": self.mavlink.is_connected(),
            "telemetry_running": self._running
        }
    
    def add_data_callback(self, callback: Callable[[TelemetryDataPoint], None]):
        """Add callback for telemetry data processing"""
        self.data_callbacks.append(callback)
    
    def remove_data_callback(self, callback: Callable[[TelemetryDataPoint], None]):
        """Remove telemetry data callback"""
        if callback in self.data_callbacks:
            self.data_callbacks.remove(callback)
    
    def get_latest_data(self, data_type: Optional[str] = None, count: int = 100) -> List[TelemetryDataPoint]:
        """Get latest telemetry data points"""
        data_points = list(self.data_buffer)
        
        if data_type:
            data_points = [dp for dp in data_points if dp.data_type == data_type]
        
        return data_points[-count:]
    
    def get_data_range(self, start_time: float, end_time: float, data_type: Optional[str] = None) -> List[TelemetryDataPoint]:
        """Get telemetry data within time range"""
        data_points = []
        
        for dp in self.data_buffer:
            if start_time <= dp.timestamp <= end_time:
                if data_type is None or dp.data_type == data_type:
                    data_points.append(dp)
        
        return data_points
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get telemetry service statistics"""
        return {
            "running": self._running,
            "total_data_points": self.total_data_points,
            "buffer_size": len(self.data_buffer),
            "max_buffer_size": self.data_buffer.maxlen,
            "collection_errors": self.collection_errors,
            "streaming_errors": self.streaming_errors,
            "last_collection": self.last_collection_time,
            "collection_interval": self.collection_interval,
            "enabled_data_types": self.enabled_data_types,
            "data_types_summary": self._get_data_types_summary()
        }
    
    def _get_data_types_summary(self) -> Dict[str, int]:
        """Get summary of data types in buffer"""
        summary = {}
        for dp in self.data_buffer:
            summary[dp.data_type] = summary.get(dp.data_type, 0) + 1
        return summary
    
    def configure_data_types(self, data_type_config: Dict[str, bool]):
        """Configure which data types to collect"""
        self.enabled_data_types.update(data_type_config)
        logger.info(f"Telemetry data types configured: {self.enabled_data_types}")
    
    def set_collection_interval(self, interval: float):
        """Set telemetry collection interval"""
        if interval < 0.1:
            raise ValueError("Collection interval cannot be less than 0.1 seconds")
        
        self.collection_interval = interval
        logger.info(f"Telemetry collection interval set to {interval}s")
    
    def clear_buffer(self):
        """Clear telemetry data buffer"""
        self.data_buffer.clear()
        logger.info("Telemetry data buffer cleared")
    
    def export_data(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """Export telemetry data for external use"""
        data_points = list(self.data_buffer)
        
        if start_time is not None:
            data_points = [dp for dp in data_points if dp.timestamp >= start_time]
        
        if end_time is not None:
            data_points = [dp for dp in data_points if dp.timestamp <= end_time]
        
        return [
            {
                "timestamp": dp.timestamp,
                "data_type": dp.data_type,
                "data": dp.data,
                "source": dp.source
            }
            for dp in data_points
        ]
    
    async def force_collection(self):
        """Force immediate telemetry collection"""
        logger.info("Forcing immediate telemetry collection")
        await self._collect_telemetry()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform telemetry service health check"""
        current_time = time.time()
        
        # Check if collection is working
        collection_healthy = (
            self._running and
            (current_time - self.last_collection_time) < (self.collection_interval * 2)
        )
        
        # Check buffer utilization
        buffer_utilization = len(self.data_buffer) / self.data_buffer.maxlen * 100
        
        # Check error rates
        total_operations = self.total_data_points + self.collection_errors
        error_rate = (self.collection_errors / total_operations * 100) if total_operations > 0 else 0
        
        return {
            "healthy": collection_healthy and error_rate < 10,
            "running": self._running,
            "collection_healthy": collection_healthy,
            "buffer_utilization": buffer_utilization,
            "error_rate": error_rate,
            "last_collection_age": current_time - self.last_collection_time,
            "data_types_active": len([dt for dt, enabled in self.enabled_data_types.items() if enabled])
        }
    