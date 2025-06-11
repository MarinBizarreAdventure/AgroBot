"""
Pydantic models for Pixhawk-related API endpoints
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime


class FlightMode(str, Enum):
    """Available flight modes"""
    MANUAL = "MANUAL"
    STABILIZE = "STABILIZE"
    GUIDED = "GUIDED"
    AUTO = "AUTO"
    RTL = "RTL"
    LOITER = "LOITER"


class ConnectionState(str, Enum):
    """MAVLink connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class GPSFixType(int, Enum):
    """GPS fix types"""
    NO_GPS = 0
    NO_FIX = 1
    FIX_2D = 2
    FIX_3D = 3
    DGPS = 4
    RTK_FLOAT = 5
    RTK_FIXED = 6


# Request Models
class ArmRequest(BaseModel):
    """Request to arm/disarm motors"""
    arm: bool = Field(..., description="True to arm, False to disarm motors")
    force_arm: bool = Field(False, description="Force arming even with safety warnings")
    
    class Config:
        schema_extra = {
            "example": {
                "arm": True,
                "force_arm": False
            }
        }


class ModeRequest(BaseModel):
    """Request to change flight mode"""
    mode: FlightMode = Field(..., description="Flight mode to set")
    
    class Config:
        schema_extra = {
            "example": {
                "mode": "GUIDED"
            }
        }


class CommandRequest(BaseModel):
    """Request to send custom MAVLink command"""
    command: int = Field(..., description="MAVLink command ID")
    param1: float = Field(0.0, description="Parameter 1")
    param2: float = Field(0.0, description="Parameter 2")
    param3: float = Field(0.0, description="Parameter 3")
    param4: float = Field(0.0, description="Parameter 4")
    param5: float = Field(0.0, description="Parameter 5")
    param6: float = Field(0.0, description="Parameter 6")
    param7: float = Field(0.0, description="Parameter 7")
    
    class Config:
        schema_extra = {
            "example": {
                "command": 400,  # MAV_CMD_COMPONENT_ARM_DISARM
                "param1": 1.0,
                "param2": 0.0,
                "param3": 0.0,
                "param4": 0.0,
                "param5": 0.0,
                "param6": 0.0,
                "param7": 0.0
            }
        }


class ParameterRequest(BaseModel):
    """Request to get/set parameter"""
    param_id: str = Field(..., description="Parameter ID")
    value: Optional[float] = Field(None, description="Value to set (omit for get)")
    
    class Config:
        schema_extra = {
            "example": {
                "param_id": "WPNAV_SPEED",
                "value": 500.0
            }
        }


# Response Models
class CommandResponse(BaseModel):
    """Standard command response"""
    success: bool = Field(..., description="Whether the command succeeded")
    message: str = Field(..., description="Human-readable message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Command executed successfully",
                "data": {"parameter": "value"},
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class ParameterResponse(BaseModel):
    """Parameter get/set response"""
    param_id: str = Field(..., description="Parameter ID")
    value: float = Field(..., description="Parameter value")
    type: str = Field(..., description="Parameter type")
    success: bool = Field(..., description="Whether operation succeeded")
    
    class Config:
        schema_extra = {
            "example": {
                "param_id": "WPNAV_SPEED",
                "value": 500.0,
                "type": "REAL32",
                "success": True
            }
        }


# Data Models
class HeartbeatData(BaseModel):
    """Heartbeat message data"""
    timestamp: float = Field(..., description="Unix timestamp")
    system_id: int = Field(..., description="MAVLink system ID")
    component_id: int = Field(..., description="MAVLink component ID")
    type: int = Field(..., description="Vehicle type")
    autopilot: int = Field(..., description="Autopilot type")
    base_mode: int = Field(..., description="Base mode flags")
    custom_mode: int = Field(..., description="Custom mode")
    system_status: int = Field(..., description="System status")
    mavlink_version: int = Field(..., description="MAVLink version")


class GPSData(BaseModel):
    """GPS data structure"""
    timestamp: float = Field(..., description="Unix timestamp")
    latitude: float = Field(..., description="Latitude in degrees")
    longitude: float = Field(..., description="Longitude in degrees")
    altitude: float = Field(..., description="Altitude above sea level (m)")
    relative_altitude: float = Field(..., description="Altitude above ground (m)")
    hdop: float = Field(..., description="Horizontal dilution of precision")
    vdop: float = Field(..., description="Vertical dilution of precision")
    ground_speed: float = Field(..., description="Ground speed (m/s)")
    course: float = Field(..., description="Course over ground (degrees)")
    satellites_visible: int = Field(..., description="Number of visible satellites")
    fix_type: GPSFixType = Field(..., description="GPS fix type")
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return v
    
    @property
    def has_valid_fix(self) -> bool:
        """Check if GPS has a valid fix"""
        return self.fix_type >= GPSFixType.FIX_3D and self.satellites_visible >= 6
    
    @property
    def position_accurate(self) -> bool:
        """Check if position is accurate enough for navigation"""
        return self.hdop < 2.0 and self.has_valid_fix


class AttitudeData(BaseModel):
    """Attitude data structure"""
    timestamp: float = Field(..., description="Unix timestamp")
    roll: float = Field(..., description="Roll angle (radians)")
    pitch: float = Field(..., description="Pitch angle (radians)")
    yaw: float = Field(..., description="Yaw angle (radians)")
    roll_speed: float = Field(..., description="Roll angular velocity (rad/s)")
    pitch_speed: float = Field(..., description="Pitch angular velocity (rad/s)")
    yaw_speed: float = Field(..., description="Yaw angular velocity (rad/s)")
    
    @property
    def roll_degrees(self) -> float:
        """Roll in degrees"""
        return self.roll * 180.0 / 3.14159
    
    @property
    def pitch_degrees(self) -> float:
        """Pitch in degrees"""
        return self.pitch * 180.0 / 3.14159
    
    @property
    def yaw_degrees(self) -> float:
        """Yaw in degrees"""
        return self.yaw * 180.0 / 3.14159


class BatteryData(BaseModel):
    """Battery status data"""
    voltage: float = Field(..., description="Battery voltage (V)")
    current: float = Field(..., description="Battery current (A)")
    remaining: float = Field(..., description="Remaining capacity (0-100%)")
    consumed: float = Field(..., description="Consumed capacity (mAh)")
    
    @property
    def is_low(self) -> bool:
        """Check if battery is low"""
        return self.remaining < 20.0
    
    @property
    def is_critical(self) -> bool:
        """Check if battery is critically low"""
        return self.remaining < 10.0


class SystemStatus(BaseModel):
    """System status information"""
    armed: bool = Field(..., description="Whether motors are armed")
    mode: str = Field(..., description="Current flight mode")
    system_status: str = Field(..., description="System status text")
    errors: List[str] = Field(default=[], description="Current error messages")
    warnings: List[str] = Field(default=[], description="Current warning messages")


# Main Status Model
class PixhawkStatus(BaseModel):
    """Complete Pixhawk status"""
    connected: bool = Field(..., description="MAVLink connection status")
    state: ConnectionState = Field(..., description="Connection state")
    system_id: int = Field(..., description="MAVLink system ID")
    component_id: int = Field(..., description="MAVLink component ID")
    heartbeat_age: Optional[float] = Field(None, description="Age of last heartbeat (seconds)")
    
    # Optional detailed data
    heartbeat: Optional[HeartbeatData] = Field(None, description="Latest heartbeat data")
    gps: Optional[GPSData] = Field(None, description="Latest GPS data")
    attitude: Optional[AttitudeData] = Field(None, description="Latest attitude data")
    battery: Optional[BatteryData] = Field(None, description="Battery status")
    system: Optional[SystemStatus] = Field(None, description="System status")
    
    class Config:
        schema_extra = {
            "example": {
                "connected": True,
                "state": "connected",
                "system_id": 1,
                "component_id": 1,
                "heartbeat_age": 0.5,
                "heartbeat": {
                    "timestamp": 1640995200.0,
                    "system_id": 1,
                    "component_id": 1,
                    "type": 2,
                    "autopilot": 3,
                    "base_mode": 81,
                    "custom_mode": 0,
                    "system_status": 4,
                    "mavlink_version": 3
                },
                "gps": {
                    "timestamp": 1640995200.0,
                    "latitude": 47.641468,
                    "longitude": -122.140165,
                    "altitude": 156.3,
                    "relative_altitude": 10.5,
                    "hdop": 0.8,
                    "vdop": 1.2,
                    "ground_speed": 2.5,
                    "course": 45.0,
                    "satellites_visible": 12,
                    "fix_type": 3
                }
            }
        }


# Mission-related models
class Waypoint(BaseModel):
    """Waypoint definition"""
    sequence: int = Field(..., description="Waypoint sequence number")
    latitude: float = Field(..., description="Latitude (degrees)")
    longitude: float = Field(..., description="Longitude (degrees)")
    altitude: float = Field(..., description="Altitude (meters)")
    command: int = Field(16, description="MAVLink command (default: NAV_WAYPOINT)")
    param1: float = Field(0.0, description="Hold time (seconds)")
    param2: float = Field(2.0, description="Acceptance radius (meters)")
    param3: float = Field(0.0, description="Pass through waypoint")
    param4: float = Field(0.0, description="Desired yaw angle")
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return v


class Mission(BaseModel):
    """Mission definition"""
    name: str = Field(..., description="Mission name")
    waypoints: List[Waypoint] = Field(..., description="List of waypoints")
    auto_continue: bool = Field(True, description="Auto continue to next waypoint")
    
    @validator('waypoints')
    def validate_waypoints(cls, v):
        if len(v) == 0:
            raise ValueError('Mission must have at least one waypoint')
        if len(v) > 100:
            raise ValueError('Mission cannot have more than 100 waypoints')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Field Survey",
                "waypoints": [
                    {
                        "sequence": 0,
                        "latitude": 47.641468,
                        "longitude": -122.140165,
                        "altitude": 10.0,
                        "command": 16,
                        "param1": 0.0,
                        "param2": 2.0,
                        "param3": 0.0,
                        "param4": 0.0
                    }
                ],
                "auto_continue": True
            }
        }