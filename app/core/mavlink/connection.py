"""
MAVLink Connection Manager for Pixhawk communication
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

try:
    from pymavlink import mavutil
    from pymavlink.dialects.v20 import common as mavlink
except ImportError:
    raise ImportError("pymavlink is required. Install with: pip install pymavlink")

from config.settings import get_settings

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """MAVLink connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class HeartbeatData:
    """Heartbeat message data"""
    timestamp: float
    system_id: int
    component_id: int
    type: int
    autopilot: int
    base_mode: int
    custom_mode: int
    system_status: int
    mavlink_version: int


@dataclass
class GPSData:
    """GPS data structure"""
    timestamp: float
    lat: float  # degrees * 1e7
    lon: float  # degrees * 1e7
    alt: float  # mm above sea level
    relative_alt: float  # mm above ground
    hdop: float
    vdop: float
    vel: float  # ground speed cm/s
    cog: int  # course over ground degrees * 100
    satellites_visible: int
    fix_type: int


@dataclass
class AttitudeData:
    """Attitude data structure"""
    timestamp: float
    roll: float  # radians
    pitch: float  # radians
    yaw: float  # radians
    rollspeed: float  # rad/s
    pitchspeed: float  # rad/s
    yawspeed: float  # rad/s


class MAVLinkManager:
    """Manages MAVLink connection to Pixhawk flight controller"""
    
    def __init__(self, connection_string: str, baud_rate: int = 57600):
        self.connection_string = connection_string
        self.baud_rate = baud_rate
        self.settings = get_settings()
        
        self.connection: Optional[mavutil.mavlink_connection] = None
        self.state = ConnectionState.DISCONNECTED
        self.last_heartbeat = 0
        self.system_id = 1
        self.component_id = 1
        
        # Message callbacks
        self.message_callbacks: Dict[str, list] = {}
        
        # Latest data
        self.latest_heartbeat: Optional[HeartbeatData] = None
        self.latest_gps: Optional[GPSData] = None
        self.latest_attitude: Optional[AttitudeData] = None
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_task: Optional[asyncio.Task] = None
        
        # Connection monitoring
        self.connection_timeout = self.settings.MAVLINK_TIMEOUT
        self.heartbeat_timeout = 5.0  # seconds
    
    async def connect(self) -> bool:
        """Establish MAVLink connection"""
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected to MAVLink")
            return True
        
        logger.info(f"Connecting to MAVLink at {self.connection_string}")
        self.state = ConnectionState.CONNECTING
        
        try:
            # Create MAVLink connection
            if self.connection_string.startswith("/dev/"):
                # Serial connection
                self.connection = mavutil.mavlink_connection(
                    self.connection_string,
                    baud=self.baud_rate,
                    timeout=self.connection_timeout
                )
            else:
                # Network connection (TCP/UDP)
                self.connection = mavutil.mavlink_connection(
                    self.connection_string,
                    timeout=self.connection_timeout
                )
            
            # Wait for first heartbeat
            logger.info("Waiting for heartbeat...")
            heartbeat_received = await self._wait_for_heartbeat()
            
            if heartbeat_received:
                self.state = ConnectionState.CONNECTED
                logger.info(f"Connected to MAVLink system {self.system_id}")
                
                # Start background tasks
                await self._start_background_tasks()
                return True
            else:
                self.state = ConnectionState.ERROR
                logger.error("Failed to receive heartbeat")
                return False
                
        except Exception as e:
            self.state = ConnectionState.ERROR
            logger.error(f"Failed to connect to MAVLink: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from MAVLink"""
        logger.info("Disconnecting from MAVLink")
        
        # Stop background tasks
        await self._stop_background_tasks()
        
        if self.connection:
            self.connection.close()
            self.connection = None
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from MAVLink")
    
    def is_connected(self) -> bool:
        """Check if connected to MAVLink"""
        return self.state == ConnectionState.CONNECTED
    
    async def _wait_for_heartbeat(self, timeout: float = 10.0) -> bool:
        """Wait for heartbeat message"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                msg = self.connection.recv_match(type='HEARTBEAT', blocking=False, timeout=1.0)
                if msg:
                    self._process_heartbeat(msg)
                    return True
            except Exception as e:
                logger.warning(f"Error waiting for heartbeat: {e}")
            
            await asyncio.sleep(0.1)
        
        return False
    
    async def _start_background_tasks(self):
        """Start background message processing tasks"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        self._message_task = asyncio.create_task(self._message_processor())
    
    async def _stop_background_tasks(self):
        """Stop background tasks"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
    
    async def _heartbeat_monitor(self):
        """Monitor heartbeat messages and connection health"""
        while self.state == ConnectionState.CONNECTED:
            try:
                current_time = time.time()
                if current_time - self.last_heartbeat > self.heartbeat_timeout:
                    logger.warning("Heartbeat timeout - connection may be lost")
                    self.state = ConnectionState.ERROR
                    break
                
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    async def _message_processor(self):
        """Process incoming MAVLink messages"""
        while self.state == ConnectionState.CONNECTED:
            try:
                msg = self.connection.recv_match(blocking=False, timeout=0.1)
                if msg:
                    await self._process_message(msg)
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_message(self, msg):
        """Process individual MAVLink message"""
        msg_type = msg.get_type()
        
        # Process specific message types
        if msg_type == 'HEARTBEAT':
            self._process_heartbeat(msg)
        elif msg_type == 'GLOBAL_POSITION_INT':
            self._process_gps_data(msg)
        elif msg_type == 'ATTITUDE':
            self._process_attitude_data(msg)
        
        # Call registered callbacks
        if msg_type in self.message_callbacks:
            for callback in self.message_callbacks[msg_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(msg)
                    else:
                        callback(msg)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")
    
    def _process_heartbeat(self, msg):
        """Process heartbeat message"""
        self.last_heartbeat = time.time()
        self.system_id = msg.get_srcSystem()
        self.component_id = msg.get_srcComponent()
        
        self.latest_heartbeat = HeartbeatData(
            timestamp=self.last_heartbeat,
            system_id=self.system_id,
            component_id=self.component_id,
            type=msg.type,
            autopilot=msg.autopilot,
            base_mode=msg.base_mode,
            custom_mode=msg.custom_mode,
            system_status=msg.system_status,
            mavlink_version=msg.mavlink_version
        )
    
    def _process_gps_data(self, msg):
        """Process GPS data message"""
        self.latest_gps = GPSData(
            timestamp=time.time(),
            lat=msg.lat,
            lon=msg.lon,
            alt=msg.alt,
            relative_alt=msg.relative_alt,
            hdop=msg.hdop / 100.0,  # Convert from cm to m
            vdop=msg.vdop / 100.0,  # Convert from cm to m
            vel=msg.vel,
            cog=msg.cog,
            satellites_visible=getattr(msg, 'satellites_visible', 0),
            fix_type=getattr(msg, 'fix_type', 0)
        )
    
    def _process_attitude_data(self, msg):
        """Process attitude data message"""
        self.latest_attitude = AttitudeData(
            timestamp=time.time(),
            roll=msg.roll,
            pitch=msg.pitch,
            yaw=msg.yaw,
            rollspeed=msg.rollspeed,
            pitchspeed=msg.pitchspeed,
            yawspeed=msg.yawspeed
        )
    
    def register_message_callback(self, message_type: str, callback: Callable):
        """Register callback for specific message type"""
        if message_type not in self.message_callbacks:
            self.message_callbacks[message_type] = []
        self.message_callbacks[message_type].append(callback)
    
    def unregister_message_callback(self, message_type: str, callback: Callable):
        """Unregister message callback"""
        if message_type in self.message_callbacks:
            try:
                self.message_callbacks[message_type].remove(callback)
            except ValueError:
                pass
    
    async def send_command_long(self, command: int, param1: float = 0, param2: float = 0,
                               param3: float = 0, param4: float = 0, param5: float = 0,
                               param6: float = 0, param7: float = 0) -> bool:
        """Send MAVLink command_long message"""
        if not self.is_connected():
            logger.error("Cannot send command: not connected")
            return False
        
        try:
            self.connection.mav.command_long_send(
                self.system_id, self.component_id,
                command, 0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            logger.debug(f"Sent command {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command {command}: {e}")
            return False
    
    async def set_mode(self, mode: str) -> bool:
        """Set flight mode"""
        mode_mapping = {
            'MANUAL': 0,
            'STABILIZE': 0,
            'GUIDED': 4,
            'AUTO': 3,
            'RTL': 6,
            'LOITER': 5
        }
        
        if mode.upper() not in mode_mapping:
            logger.error(f"Unknown mode: {mode}")
            return False
        
        mode_id = mode_mapping[mode.upper()]
        return await self.send_command_long(
            mavlink.MAV_CMD_DO_SET_MODE,
            mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
    
    async def arm_motors(self, arm: bool = True) -> bool:
        """Arm or disarm motors"""
        param1 = 1.0 if arm else 0.0
        return await self.send_command_long(
            mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current MAVLink connection status"""
        return {
            "state": self.state.value,
            "connected": self.is_connected(),
            "connection_string": self.connection_string,
            "system_id": self.system_id,
            "component_id": self.component_id,
            "last_heartbeat": self.last_heartbeat,
            "heartbeat_age": time.time() - self.last_heartbeat if self.last_heartbeat else None,
            "latest_heartbeat": self.latest_heartbeat.__dict__ if self.latest_heartbeat else None,
            "latest_gps": self.latest_gps.__dict__ if self.latest_gps else None,
            "latest_attitude": self.latest_attitude.__dict__ if self.latest_attitude else None
        }