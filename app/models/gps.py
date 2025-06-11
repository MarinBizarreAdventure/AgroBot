"""
Pydantic models for GPS data API endpoints
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class CoordinateRequest(BaseModel):
    """Request to calculate distance to coordinates"""
    latitude: float = Field(..., description="Target latitude in degrees", ge=-90, le=90)
    longitude: float = Field(..., description="Target longitude in degrees", ge=-180, le=180)
    altitude: Optional[float] = Field(None, description="Target altitude in meters", ge=0)
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 10.0
            }
        }


# Response Models
class GPSPosition(BaseModel):
    """Current GPS position data"""
    latitude: float = Field(..., description="Latitude in degrees")
    longitude: float = Field(..., description="Longitude in degrees")
    altitude: float = Field(..., description="Altitude above sea level in meters")
    relative_altitude: float = Field(..., description="Altitude above ground in meters")
    ground_speed: float = Field(..., description="Ground speed in m/s")
    heading: float = Field(..., description="Heading in degrees (0-360)")
    timestamp: float = Field(..., description="GPS data timestamp (Unix time)")
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 156.3,
                "relative_altitude": 10.5,
                "ground_speed": 2.5,
                "heading": 45.0,
                "timestamp": 1640995200.0
            }
        }


class GPSStatus(BaseModel):
    """GPS receiver status and health"""
    available: bool = Field(..., description="Whether GPS data is available")
    fix_type: int = Field(..., description="GPS fix type (0=No GPS, 1=No Fix, 2=2D, 3=3D)")
    satellites_visible: int = Field(..., description="Number of visible satellites")
    hdop: float = Field(..., description="Horizontal dilution of precision")
    vdop: float = Field(..., description="Vertical dilution of precision")
    accuracy_estimate: float = Field(..., description="Position accuracy estimate in meters")
    has_good_fix: bool = Field(..., description="Whether GPS has a good fix for navigation")
    ready_for_navigation: bool = Field(..., description="Whether GPS is ready for navigation")
    last_update: Optional[float] = Field(None, description="Last GPS update timestamp")
    
    @property
    def fix_type_description(self) -> str:
        """Human-readable fix type description"""
        fix_types = {
            0: "No GPS",
            1: "No Fix",
            2: "2D Fix",
            3: "3D Fix",
            4: "DGPS",
            5: "RTK Float",
            6: "RTK Fixed"
        }
        return fix_types.get(self.fix_type, "Unknown")
    
    class Config:
        schema_extra = {
            "example": {
                "available": True,
                "fix_type": 3,
                "satellites_visible": 12,
                "hdop": 0.8,
                "vdop": 1.2,
                "accuracy_estimate": 4.0,
                "has_good_fix": True,
                "ready_for_navigation": True,
                "last_update": 1640995200.0
            }
        }


class GPSAccuracy(BaseModel):
    """Detailed GPS accuracy metrics"""
    hdop: float = Field(..., description="Horizontal dilution of precision")
    vdop: float = Field(..., description="Vertical dilution of precision")
    pdop: float = Field(..., description="Position dilution of precision")
    horizontal_error_estimate: float = Field(..., description="Estimated horizontal error in meters")
    vertical_error_estimate: float = Field(..., description="Estimated vertical error in meters")
    accuracy_class: str = Field(..., description="Accuracy classification (excellent/good/moderate/poor)")
    suitable_for_navigation: bool = Field(..., description="Whether accuracy is suitable for navigation")
    
    @validator('accuracy_class')
    def validate_accuracy_class(cls, v):
        valid_classes = ["excellent", "good", "moderate", "poor"]
        if v not in valid_classes:
            raise ValueError(f"Accuracy class must be one of: {valid_classes}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "hdop": 0.8,
                "vdop": 1.2,
                "pdop": 1.44,
                "horizontal_error_estimate": 4.0,
                "vertical_error_estimate": 6.0,
                "accuracy_class": "good",
                "suitable_for_navigation": True
            }
        }


class GPSHistory(BaseModel):
    """GPS position history"""
    positions: List[Dict[str, Any]] = Field(..., description="List of GPS positions")
    count: int = Field(..., description="Number of positions in history")
    total_distance_meters: float = Field(..., description="Total distance traveled")
    time_span_seconds: float = Field(..., description="Time span of history data")
    
    class Config:
        schema_extra = {
            "example": {
                "positions": [
                    {
                        "timestamp": 1640995200.0,
                        "latitude": 47.641468,
                        "longitude": -122.140165,
                        "altitude": 156.3,
                        "relative_altitude": 10.5,
                        "ground_speed": 2.5,
                        "heading": 45.0,
                        "satellites": 12,
                        "hdop": 0.8,
                        "fix_type": 3
                    }
                ],
                "count": 1,
                "total_distance_meters": 0.0,
                "time_span_seconds": 0.0
            }
        }


class DistanceResponse(BaseModel):
    """Distance calculation response"""
    distance_meters: float = Field(..., description="Distance in meters")
    bearing_degrees: float = Field(..., description="Bearing in degrees (0-360)")
    estimated_travel_time_seconds: Optional[float] = Field(None, description="Estimated travel time at current speed")
    current_position: Dict[str, float] = Field(..., description="Current GPS position")
    target_position: Dict[str, float] = Field(..., description="Target coordinates")
    
    class Config:
        schema_extra = {
            "example": {
                "distance_meters": 45.2,
                "bearing_degrees": 135.5,
                "estimated_travel_time_seconds": 18.1,
                "current_position": {
                    "latitude": 47.641468,
                    "longitude": -122.140165,
                    "altitude": 10.5
                },
                "target_position": {
                    "latitude": 47.641500,
                    "longitude": -122.140200,
                    "altitude": 10.0
                }
            }
        }


class GeofenceStatus(BaseModel):
    """Geofence status information"""
    enabled: bool = Field(..., description="Whether geofence is enabled")
    inside_fence: bool = Field(..., description="Whether currently inside geofence")
    distance_to_fence: Optional[float] = Field(None, description="Distance to fence boundary (negative if outside)")
    fence_radius: float = Field(..., description="Geofence radius in meters")
    fence_center: Optional[Dict[str, float]] = Field(None, description="Geofence center coordinates")
    
    class Config:
        schema_extra = {
            "example": {
                "enabled": True,
                "inside_fence": True,
                "distance_to_fence": 25.5,
                "fence_radius": 100.0,
                "fence_center": {
                    "latitude": 47.641468,
                    "longitude": -122.140165
                }
            }
        }


# Waypoint and path models
class GPSWaypoint(BaseModel):
    """GPS waypoint definition"""
    latitude: float = Field(..., description="Waypoint latitude", ge=-90, le=90)
    longitude: float = Field(..., description="Waypoint longitude", ge=-180, le=180)
    altitude: float = Field(..., description="Waypoint altitude in meters", ge=0)
    sequence: int = Field(..., description="Waypoint sequence number", ge=0)
    name: Optional[str] = Field(None, description="Optional waypoint name")
    
    class Config:
        schema_extra = {
            "example": {
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 10.0,
                "sequence": 1,
                "name": "Waypoint 1"
            }
        }


class GPSPath(BaseModel):
    """GPS path definition"""
    name: str = Field(..., description="Path name")
    waypoints: List[GPSWaypoint] = Field(..., description="List of waypoints")
    total_distance: Optional[float] = Field(None, description="Total path distance in meters")
    estimated_time: Optional[float] = Field(None, description="Estimated time to complete path")
    
    @validator('waypoints')
    def validate_waypoints(cls, v):
        if len(v) < 2:
            raise ValueError('Path must have at least 2 waypoints')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Survey Path",
                "waypoints": [
                    {
                        "latitude": 47.641468,
                        "longitude": -122.140165,
                        "altitude": 10.0,
                        "sequence": 0,
                        "name": "Start"
                    },
                    {
                        "latitude": 47.641500,
                        "longitude": -122.140200,
                        "altitude": 10.0,
                        "sequence": 1,
                        "name": "End"
                    }
                ],
                "total_distance": 45.2,
                "estimated_time": 18.1
            }
        }


# Statistics and analysis models
class GPSStatistics(BaseModel):
    """GPS data statistics"""
    total_positions: int = Field(..., description="Total number of GPS positions recorded")
    time_span_hours: float = Field(..., description="Time span of data in hours")
    total_distance_km: float = Field(..., description="Total distance traveled in kilometers")
    average_speed_ms: float = Field(..., description="Average speed in m/s")
    max_speed_ms: float = Field(..., description="Maximum speed recorded in m/s")
    average_altitude_m: float = Field(..., description="Average altitude in meters")
    max_altitude_m: float = Field(..., description="Maximum altitude in meters")
    min_altitude_m: float = Field(..., description="Minimum altitude in meters")
    
    class Config:
        schema_extra = {
            "example": {
                "total_positions": 1500,
                "time_span_hours": 2.5,
                "total_distance_km": 5.2,
                "average_speed_ms": 3.5,
                "max_speed_ms": 8.0,
                "average_altitude_m": 12.5,
                "max_altitude_m": 25.0,
                "min_altitude_m": 8.0
            }
        }


class GPSQuality(BaseModel):
    """GPS signal quality assessment"""
    signal_strength: str = Field(..., description="Signal strength assessment (excellent/good/poor)")
    stability: str = Field(..., description="Signal stability (stable/unstable)")
    accuracy_trend: str = Field(..., description="Accuracy trend (improving/stable/degrading)")
    satellite_count_avg: float = Field(..., description="Average satellite count")
    hdop_avg: float = Field(..., description="Average HDOP")
    fix_rate_percent: float = Field(..., description="Percentage of time with 3D fix")
    recommendations: List[str] = Field(default=[], description="Recommendations for improvement")
    
    class Config:
        schema_extra = {
            "example": {
                "signal_strength": "good",
                "stability": "stable",
                "accuracy_trend": "stable",
                "satellite_count_avg": 11.5,
                "hdop_avg": 1.2,
                "fix_rate_percent": 98.5,
                "recommendations": []
            }
        }