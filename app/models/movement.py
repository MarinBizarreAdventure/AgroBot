"""
Pydantic models for movement control API endpoints
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class MoveToRequest(BaseModel):
    """Request to move to specific GPS coordinates"""
    latitude: float = Field(..., description="Target latitude in degrees", ge=-90, le=90)
    longitude: float = Field(..., description="Target longitude in degrees", ge=-180, le=180)
    altitude: float = Field(..., description="Target altitude in meters above ground", ge=0, le=500)
    max_speed: Optional[float] = Field(None, description="Maximum speed in m/s", ge=0.1, le=20)
    acceptance_radius: float = Field(2.0, description="Acceptance radius in meters", ge=0.5, le=10)
    force: bool = Field(False, description="Force movement even with safety warnings")
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 10.0,
                "max_speed": 5.0,
                "acceptance_radius": 2.0,
                "force": False
            }
        }


class VelocityRequest(BaseModel):
    """Request to set velocity in body frame"""
    forward: float = Field(..., description="Forward velocity in m/s (positive=forward)", ge=-10, le=10)
    right: float = Field(..., description="Right velocity in m/s (positive=right)", ge=-10, le=10)
    down: float = Field(..., description="Down velocity in m/s (positive=down)", ge=-5, le=5)
    yaw_rate: float = Field(0.0, description="Yaw rate in degrees/second", ge=-180, le=180)
    duration: Optional[float] = Field(None, description="Duration to maintain velocity in seconds", ge=0.1, le=60)
    
    class Config:
        schema_extra = {
            "example": {
                "forward": 2.0,
                "right": 0.0,
                "down": 0.0,
                "yaw_rate": 0.0,
                "duration": 5.0
            }
        }


class StopRequest(BaseModel):
    """Request to stop movement"""
    emergency: bool = Field(False, description="Emergency stop (disarms motors)")
    hold_position: bool = Field(True, description="Hold current position after stop")
    
    class Config:
        schema_extra = {
            "example": {
                "emergency": False,
                "hold_position": True
            }
        }


class TakeoffRequest(BaseModel):
    """Request to takeoff"""
    altitude: float = Field(..., description="Takeoff altitude in meters", gt=0, le=500)
    force: bool = Field(False, description="Force takeoff even with safety warnings")
    auto_arm: bool = Field(True, description="Automatically arm motors before takeoff")
    
    @validator('altitude')
    def validate_altitude(cls, v):
        if v <= 0:
            raise ValueError('Takeoff altitude must be positive')
        if v > 120:  # FAA drone altitude limit
            raise ValueError('Altitude exceeds maximum allowed (120m)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "altitude": 10.0,
                "force": False,
                "auto_arm": True
            }
        }


class LandRequest(BaseModel):
    """Request to land"""
    latitude: Optional[float] = Field(None, description="Landing latitude (current position if not specified)", ge=-90, le=90)
    longitude: Optional[float] = Field(None, description="Landing longitude (current position if not specified)", ge=-180, le=180)
    precision: bool = Field(False, description="Use precision landing if available")
    auto_disarm: bool = Field(True, description="Automatically disarm after landing")
    
    @validator('longitude')
    def validate_coordinates(cls, v, values):
        if v is not None and 'latitude' in values and values['latitude'] is None:
            raise ValueError('If longitude is specified, latitude must also be specified')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": None,
                "longitude": None,
                "precision": False,
                "auto_disarm": True
            }
        }


class RTLRequest(BaseModel):
    """Request to Return to Launch"""
    rtl_altitude: Optional[float] = Field(None, description="RTL altitude in meters (use default if not specified)", ge=5, le=500)
    auto_land: bool = Field(True, description="Automatically land at launch position")
    
    class Config:
        schema_extra = {
            "example": {
                "rtl_altitude": 20.0,
                "auto_land": True
            }
        }


# Response Models
class MoveToResponse(BaseModel):
    """Response for move to command"""
    success: bool = Field(..., description="Whether the command was successful")
    message: str = Field(..., description="Response message")
    target_latitude: float = Field(..., description="Target latitude")
    target_longitude: float = Field(..., description="Target longitude")
    target_altitude: float = Field(..., description="Target altitude")
    distance_to_target: float = Field(..., description="Distance to target in meters")
    estimated_time_seconds: float = Field(..., description="Estimated time to reach target")
    max_speed: float = Field(..., description="Maximum speed setting")
    timestamp: datetime = Field(default_factory=datetime.now, description="Command timestamp")


class PositionResponse(BaseModel):
    """Current position response"""
    latitude: float = Field(..., description="Current latitude in degrees")
    longitude: float = Field(..., description="Current longitude in degrees")
    altitude: float = Field(..., description="Current altitude above sea level in meters")
    relative_altitude: float = Field(..., description="Current altitude above ground in meters")
    ground_speed: float = Field(..., description="Current ground speed in m/s")
    heading: float = Field(..., description="Current heading in degrees")
    satellites: int = Field(..., description="Number of visible GPS satellites")
    hdop: float = Field(..., description="Horizontal dilution of precision")
    fix_type: int = Field(..., description="GPS fix type (0=No GPS, 1=No Fix, 2=2D, 3=3D)")
    timestamp: float = Field(..., description="GPS data timestamp")
    
    @property
    def has_good_fix(self) -> bool:
        """Check if GPS has good fix for navigation"""
        return self.fix_type >= 3 and self.satellites >= 6 and self.hdop < 2.0
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 156.3,
                "relative_altitude": 10.5,
                "ground_speed": 2.5,
                "heading": 45.0,
                "satellites": 12,
                "hdop": 0.8,
                "fix_type": 3,
                "timestamp": 1640995200.0
            }
        }


class NavigationStatus(BaseModel):
    """Navigation status response"""
    connected: bool = Field(..., description="Connection to flight controller")
    armed: bool = Field(..., description="Whether motors are armed")
    mode: str = Field(..., description="Current flight mode")
    current_position: Optional[Dict[str, float]] = Field(None, description="Current GPS position")
    ground_speed: float = Field(..., description="Current ground speed in m/s")
    target_position: Optional[Dict[str, float]] = Field(None, description="Target position if navigating")
    distance_to_target: Optional[float] = Field(None, description="Distance to target in meters")
    estimated_time_to_target: Optional[float] = Field(None, description="Estimated time to target in seconds")
    navigation_active: bool = Field(..., description="Whether actively navigating")
    
    class Config:
        schema_extra = {
            "example": {
                "connected": True,
                "armed": True,
                "mode": "GUIDED",
                "current_position": {
                    "latitude": 47.641468,
                    "longitude": -122.140165,
                    "altitude": 10.5
                },
                "ground_speed": 2.5,
                "target_position": {
                    "latitude": 47.641500,
                    "longitude": -122.140200,
                    "altitude": 10.0
                },
                "distance_to_target": 45.2,
                "estimated_time_to_target": 18.1,
                "navigation_active": True
            }
        }


class DistanceResponse(BaseModel):
    """Distance calculation response"""
    distance_meters: float = Field(..., description="Distance in meters")
    bearing_degrees: float = Field(..., description="Bearing in degrees (0-360)")
    estimated_flight_time_seconds: Optional[float] = Field(None, description="Estimated flight time at current speed")
    current_position: Dict[str, float] = Field(..., description="Current position")
    target_position: Dict[str, float] = Field(..., description="Target position")
    
    class Config:
        schema_extra = {
            "example": {
                "distance_meters": 45.2,
                "bearing_degrees": 135.5,
                "estimated_flight_time_seconds": 18.1,
                "current_position": {
                    "latitude": 47.641468,
                    "longitude": -122.140165
                },
                "target_position": {
                    "latitude": 47.641500,
                    "longitude": -122.140200
                }
            }
        }


# Pattern-specific models
class SquarePatternRequest(BaseModel):
    """Request to execute square pattern"""
    side_length: float = Field(..., description="Side length in meters", gt=0, le=1000)
    altitude: float = Field(..., description="Flight altitude in meters", gt=0, le=500)
    center_latitude: Optional[float] = Field(None, description="Center latitude (current position if not specified)")
    center_longitude: Optional[float] = Field(None, description="Center longitude (current position if not specified)")
    clockwise: bool = Field(True, description="Fly clockwise pattern")
    speed: float = Field(5.0, description="Flight speed in m/s", gt=0, le=20)
    
    @validator('side_length')
    def validate_side_length(cls, v):
        if v <= 0:
            raise ValueError('Side length must be positive')
        if v > 1000:
            raise ValueError('Side length too large (max 1000m)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "side_length": 50.0,
                "altitude": 10.0,
                "center_latitude": None,
                "center_longitude": None,
                "clockwise": True,
                "speed": 5.0
            }
        }


class CirclePatternRequest(BaseModel):
    """Request to execute circle pattern"""
    radius: float = Field(..., description="Circle radius in meters", gt=0, le=500)
    altitude: float = Field(..., description="Flight altitude in meters", gt=0, le=500)
    center_latitude: Optional[float] = Field(None, description="Center latitude (current position if not specified)")
    center_longitude: Optional[float] = Field(None, description="Center longitude (current position if not specified)")
    clockwise: bool = Field(True, description="Fly clockwise pattern")
    speed: float = Field(5.0, description="Flight speed in m/s", gt=0, le=20)
    turns: int = Field(1, description="Number of complete turns", ge=1, le=10)
    
    @validator('radius')
    def validate_radius(cls, v):
        if v <= 0:
            raise ValueError('Radius must be positive')
        if v > 500:
            raise ValueError('Radius too large (max 500m)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "radius": 25.0,
                "altitude": 10.0,
                "center_latitude": None,
                "center_longitude": None,
                "clockwise": True,
                "speed": 5.0,
                "turns": 1
            }
        }


class GridPatternRequest(BaseModel):
    """Request to execute grid survey pattern"""
    width: float = Field(..., description="Grid width in meters", gt=0, le=1000)
    height: float = Field(..., description="Grid height in meters", gt=0, le=1000)
    spacing: float = Field(..., description="Line spacing in meters", gt=0, le=100)
    altitude: float = Field(..., description="Flight altitude in meters", gt=0, le=500)
    start_latitude: Optional[float] = Field(None, description="Start latitude (current position if not specified)")
    start_longitude: Optional[float] = Field(None, description="Start longitude (current position if not specified)")
    orientation: float = Field(0.0, description="Grid orientation in degrees", ge=0, lt=360)
    speed: float = Field(5.0, description="Flight speed in m/s", gt=0, le=20)
    
    @validator('spacing')
    def validate_spacing(cls, v, values):
        if 'width' in values and v > values['width'] / 2:
            raise ValueError('Spacing too large for grid width')
        if 'height' in values and v > values['height'] / 2:
            raise ValueError('Spacing too large for grid height')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "width": 100.0,
                "height": 80.0,
                "spacing": 10.0,
                "altitude": 15.0,
                "start_latitude": None,
                "start_longitude": None,
                "orientation": 0.0,
                "speed": 5.0
            }
        }


class PatternResponse(BaseModel):
    """Pattern execution response"""
    success: bool = Field(..., description="Whether pattern was started successfully")
    message: str = Field(..., description="Response message")
    pattern_type: str = Field(..., description="Type of pattern")
    waypoint_count: int = Field(..., description="Number of waypoints generated")
    estimated_duration: float = Field(..., description="Estimated pattern duration in seconds")
    total_distance: float = Field(..., description="Total pattern distance in meters")
    waypoints: Optional[list] = Field(None, description="Generated waypoints (if requested)")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Square pattern started successfully",
                "pattern_type": "square",
                "waypoint_count": 4,
                "estimated_duration": 120.0,
                "total_distance": 200.0,
                "waypoints": None
            }
        }