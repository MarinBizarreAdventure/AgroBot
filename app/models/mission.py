"""
Pydantic models for mission planning API endpoints
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class WaypointRequest(BaseModel):
    """Individual waypoint definition"""
    sequence: int = Field(..., description="Waypoint sequence number", ge=0)
    latitude: float = Field(..., description="Waypoint latitude", ge=-90, le=90)
    longitude: float = Field(..., description="Waypoint longitude", ge=-180, le=180)
    altitude: float = Field(..., description="Waypoint altitude in meters", ge=0, le=500)
    hold_time: float = Field(0.0, description="Hold time at waypoint in seconds", ge=0)
    acceptance_radius: float = Field(2.0, description="Acceptance radius in meters", ge=0.5, le=10)
    pass_through: bool = Field(False, description="Pass through waypoint without stopping")
    desired_yaw: Optional[float] = Field(None, description="Desired yaw angle in degrees")
    
    class Config:
        schema_extra = {
            "example": {
                "sequence": 0,
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 10.0,
                "hold_time": 0.0,
                "acceptance_radius": 2.0,
                "pass_through": False,
                "desired_yaw": None
            }
        }


class MissionRequest(BaseModel):
    """Request to create a new mission"""
    name: str = Field(..., description="Mission name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Mission description", max_length=500)
    waypoints: List[WaypointRequest] = Field(..., description="List of waypoints")
    default_speed: Optional[float] = Field(None, description="Default speed in m/s", gt=0, le=20)
    auto_continue: bool = Field(True, description="Automatically continue to next waypoint")
    return_to_launch: bool = Field(False, description="Return to launch after mission completion")
    
    @validator('waypoints')
    def validate_waypoints(cls, v):
        if len(v) == 0:
            raise ValueError('Mission must have at least one waypoint')
        if len(v) > 100:
            raise ValueError('Mission cannot have more than 100 waypoints')
        
        # Check sequence numbers
        sequences = [wp.sequence for wp in v]
        if len(set(sequences)) != len(sequences):
            raise ValueError('Waypoint sequence numbers must be unique')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Survey Mission",
                "description": "Agricultural field survey mission",
                "waypoints": [
                    {
                        "sequence": 0,
                        "latitude": 47.641468,
                        "longitude": -122.140165,
                        "altitude": 10.0,
                        "hold_time": 0.0,
                        "acceptance_radius": 2.0,
                        "pass_through": False,
                        "desired_yaw": None
                    }
                ],
                "default_speed": 5.0,
                "auto_continue": True,
                "return_to_launch": True
            }
        }


class PatternRequest(BaseModel):
    """Base class for pattern generation requests"""
    altitude: float = Field(..., description="Flight altitude in meters", gt=0, le=500)
    speed: float = Field(5.0, description="Flight speed in m/s", gt=0, le=20)
    include_waypoints: bool = Field(False, description="Include waypoint details in response")


# Response Models
class WaypointResponse(BaseModel):
    """Waypoint information in response"""
    sequence: int = Field(..., description="Waypoint sequence number")
    latitude: float = Field(..., description="Waypoint latitude")
    longitude: float = Field(..., description="Waypoint longitude") 
    altitude: float = Field(..., description="Waypoint altitude")
    command: int = Field(..., description="MAVLink command ID")
    parameters: List[float] = Field(..., description="Command parameters")
    
    class Config:
        schema_extra = {
            "example": {
                "sequence": 0,
                "latitude": 47.641468,
                "longitude": -122.140165,
                "altitude": 10.0,
                "command": 16,
                "parameters": [0.0, 2.0, 0.0, 0.0]
            }
        }


class MissionResponse(BaseModel):
    """Response for mission operations"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    mission_id: str = Field(..., description="Unique mission identifier")
    waypoint_count: int = Field(..., description="Number of waypoints in mission")
    total_distance_meters: float = Field(..., description="Total mission distance")
    estimated_duration_seconds: float = Field(..., description="Estimated mission duration")
    mission_data: Optional[Dict[str, Any]] = Field(None, description="Complete mission data")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Mission created successfully",
                "mission_id": "mission_1_1640995200",
                "waypoint_count": 4,
                "total_distance_meters": 200.0,
                "estimated_duration_seconds": 120.0,
                "mission_data": None
            }
        }


class PatternResponse(BaseModel):
    """Response for pattern generation"""
    success: bool = Field(..., description="Whether pattern was generated successfully")
    message: str = Field(..., description="Response message")
    pattern_type: str = Field(..., description="Type of pattern generated")
    waypoint_count: int = Field(..., description="Number of waypoints generated")
    estimated_duration: float = Field(..., description="Estimated pattern duration in seconds")
    total_distance: float = Field(..., description="Total pattern distance in meters")
    mission_id: Optional[str] = Field(None, description="Generated mission ID if created")
    waypoints: Optional[List[Dict[str, Any]]] = Field(None, description="Generated waypoints")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Square pattern generated successfully",
                "pattern_type": "square",
                "waypoint_count": 4,
                "estimated_duration": 120.0,
                "total_distance": 200.0,
                "mission_id": "square_pattern_1640995200",
                "waypoints": None
            }
        }


# Status Models
class MissionStatus(BaseModel):
    """Mission status information"""
    mission_id: str = Field(..., description="Mission identifier")
    name: str = Field(..., description="Mission name")
    status: str = Field(..., description="Mission status")
    created_at: float = Field(..., description="Creation timestamp")
    waypoint_count: int = Field(..., description="Number of waypoints")
    total_distance: float = Field(..., description="Total distance in meters")
    estimated_time: float = Field(..., description="Estimated time in seconds")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["created", "executing", "completed", "stopped", "error"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "mission_id": "mission_1_1640995200",
                "name": "Survey Mission",
                "status": "created",
                "created_at": 1640995200.0,
                "waypoint_count": 4,
                "total_distance": 200.0,
                "estimated_time": 120.0
            }
        }


class MissionExecutionStatus(BaseModel):
    """Current mission execution status"""
    active: bool = Field(..., description="Whether a mission is currently executing")
    mission_id: Optional[str] = Field(None, description="ID of executing mission")
    current_waypoint: int = Field(..., description="Current waypoint index")
    total_waypoints: int = Field(..., description="Total number of waypoints")
    progress_percent: float = Field(..., description="Mission progress percentage")
    elapsed_time_seconds: float = Field(..., description="Elapsed execution time")
    estimated_remaining_seconds: Optional[float] = Field(None, description="Estimated remaining time")
    status: str = Field(..., description="Execution status")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["idle", "executing", "completed", "stopped", "error"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "active": True,
                "mission_id": "mission_1_1640995200",
                "current_waypoint": 2,
                "total_waypoints": 4,
                "progress_percent": 50.0,
                "elapsed_time_seconds": 60.0,
                "estimated_remaining_seconds": 60.0,
                "status": "executing"
            }
        }


# Advanced Mission Models
class MissionTemplate(BaseModel):
    """Mission template for reusable mission patterns"""
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(..., description="Template category (survey, patrol, etc.)")
    parameters: Dict[str, Any] = Field(..., description="Template parameters")
    waypoint_template: List[Dict[str, Any]] = Field(..., description="Waypoint template")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Basic Survey",
                "description": "Simple rectangular survey pattern",
                "category": "survey",
                "parameters": {
                    "width": 100,
                    "height": 80,
                    "altitude": 15,
                    "overlap": 20
                },
                "waypoint_template": []
            }
        }


class MissionValidation(BaseModel):
    """Mission validation results"""
    valid: bool = Field(..., description="Whether mission is valid")
    warnings: List[str] = Field(default=[], description="Validation warnings")
    errors: List[str] = Field(default=[], description="Validation errors")
    estimated_flight_time: Optional[float] = Field(None, description="Estimated flight time")
    estimated_battery_usage: Optional[float] = Field(None, description="Estimated battery usage")
    safety_checks: Dict[str, bool] = Field(..., description="Safety check results")
    
    class Config:
        schema_extra = {
            "example": {
                "valid": True,
                "warnings": ["Mission exceeds 30 minutes flight time"],
                "errors": [],
                "estimated_flight_time": 1800.0,
                "estimated_battery_usage": 65.0,
                "safety_checks": {
                    "geofence": True,
                    "altitude_limits": True,
                    "no_fly_zones": True,
                    "battery_sufficient": False
                }
            }
        }


class MissionStatistics(BaseModel):
    """Mission execution statistics"""
    mission_id: str = Field(..., description="Mission identifier")
    total_time_seconds: float = Field(..., description="Total execution time")
    total_distance_meters: float = Field(..., description="Total distance traveled")
    average_speed_ms: float = Field(..., description="Average speed in m/s")
    max_speed_ms: float = Field(..., description="Maximum speed reached")
    waypoints_completed: int = Field(..., description="Number of waypoints completed")
    waypoints_skipped: int = Field(..., description="Number of waypoints skipped")
    battery_used_percent: Optional[float] = Field(None, description="Battery usage percentage")
    gps_accuracy_avg: Optional[float] = Field(None, description="Average GPS accuracy")
    completion_status: str = Field(..., description="How the mission was completed")
    
    class Config:
        schema_extra = {
            "example": {
                "mission_id": "mission_1_1640995200",
                "total_time_seconds": 1850.0,
                "total_distance_meters": 1250.0,
                "average_speed_ms": 3.2,
                "max_speed_ms": 5.5,
                "waypoints_completed": 4,
                "waypoints_skipped": 0,
                "battery_used_percent": 68.5,
                "gps_accuracy_avg": 1.2,
                "completion_status": "completed_successfully"
            }
        }


# Pattern-specific request models (extending the base PatternRequest)
class RectanglePatternRequest(PatternRequest):
    """Rectangle survey pattern request"""
    width: float = Field(..., description="Rectangle width in meters", gt=0, le=1000)
    height: float = Field(..., description="Rectangle height in meters", gt=0, le=1000)
    center_latitude: Optional[float] = Field(None, description="Center latitude", ge=-90, le=90)
    center_longitude: Optional[float] = Field(None, description="Center longitude", ge=-180, le=180)
    orientation: float = Field(0.0, description="Rectangle orientation in degrees", ge=0, lt=360)
    
    class Config:
        schema_extra = {
            "example": {
                "width": 100.0,
                "height": 80.0,
                "altitude": 15.0,
                "center_latitude": None,
                "center_longitude": None,
                "orientation": 0.0,
                "speed": 5.0,
                "include_waypoints": False
            }
        }


class PolygonPatternRequest(PatternRequest):
    """Polygon survey pattern request"""
    vertices: List[Dict[str, float]] = Field(..., description="Polygon vertices as lat/lon pairs")
    line_spacing: float = Field(..., description="Line spacing in meters", gt=0, le=50)
    orientation: float = Field(0.0, description="Survey line orientation in degrees", ge=0, lt=360)
    
    @validator('vertices')
    def validate_vertices(cls, v):
        if len(v) < 3:
            raise ValueError('Polygon must have at least 3 vertices')
        if len(v) > 20:
            raise ValueError('Polygon cannot have more than 20 vertices')
        
        for vertex in v:
            if 'latitude' not in vertex or 'longitude' not in vertex:
                raise ValueError('Each vertex must have latitude and longitude')
            if not (-90 <= vertex['latitude'] <= 90):
                raise ValueError('Latitude must be between -90 and 90 degrees')
            if not (-180 <= vertex['longitude'] <= 180):
                raise ValueError('Longitude must be between -180 and 180 degrees')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "vertices": [
                    {"latitude": 47.641468, "longitude": -122.140165},
                    {"latitude": 47.641500, "longitude": -122.140200},
                    {"latitude": 47.641450, "longitude": -122.140250},
                    {"latitude": 47.641420, "longitude": -122.140200}
                ],
                "line_spacing": 10.0,
                "altitude": 15.0,
                "orientation": 0.0,
                "speed": 5.0,
                "include_waypoints": False
            }
        }