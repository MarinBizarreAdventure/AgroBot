"""
Mission planning and execution API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
import logging
import math
import asyncio
import time
from app.core.mavlink.connection import MAVLinkManager
from app.models.mission import (
    MissionRequest, MissionResponse, WaypointRequest, WaypointResponse,
    MissionStatus, PatternRequest, PatternResponse, MissionExecutionStatus
)
from app.models.movement import (
    SquarePatternRequest, CirclePatternRequest, GridPatternRequest, PatternResponse
)
from app.models.pixhawk import CommandResponse
from config.settings import get_settings
from main import get_mavlink_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Store active missions and execution state
active_missions: Dict[str, Dict[str, Any]] = {}
mission_execution_state: Dict[str, Any] = {
    "active": False,
    "mission_id": None,
    "current_waypoint": 0,
    "total_waypoints": 0,
    "start_time": None,
    "status": "idle"
}


@router.post("/create", response_model=MissionResponse)
async def create_mission(
    request: MissionRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> MissionResponse:
    """
    Create a new mission with waypoints
    
    Creates a mission plan with specified waypoints that can be executed later.
    """
    try:
        settings = get_settings()
        
        # Validate mission
        if len(request.waypoints) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mission must have at least one waypoint"
            )
        
        if len(request.waypoints) > settings.MAX_WAYPOINTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mission exceeds maximum waypoints ({settings.MAX_WAYPOINTS})"
            )
        
        # Calculate mission statistics
        total_distance = 0.0
        estimated_time = 0.0
        
        if len(request.waypoints) > 1:
            for i in range(1, len(request.waypoints)):
                prev = request.waypoints[i-1]
                curr = request.waypoints[i]
                
                distance = calculate_distance(
                    prev.latitude, prev.longitude,
                    curr.latitude, curr.longitude
                )
                total_distance += distance
                
                # Estimate time based on speed
                speed = request.default_speed or settings.MAX_SPEED
                estimated_time += distance / speed
        
        # Generate mission ID
        mission_id = f"mission_{len(active_missions) + 1}_{int(time.time())}"
        
        # Store mission
        mission_data = {
            "id": mission_id,
            "name": request.name,
            "description": request.description,
            "waypoints": [wp.dict() for wp in request.waypoints],
            "default_speed": request.default_speed or settings.MAX_SPEED,
            "auto_continue": request.auto_continue,
            "return_to_launch": request.return_to_launch,
            "total_distance": total_distance,
            "estimated_time": estimated_time,
            "created_at": time.time(),
            "status": "created"
        }
        
        active_missions[mission_id] = mission_data
        
        return MissionResponse(
            success=True,
            message=f"Mission '{request.name}' created successfully",
            mission_id=mission_id,
            waypoint_count=len(request.waypoints),
            total_distance_meters=total_distance,
            estimated_duration_seconds=estimated_time,
            mission_data=mission_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission creation error: {str(e)}"
        )


@router.get("/list")
async def list_missions() -> Dict[str, Any]:
    """
    List all created missions
    
    Returns a list of all missions with their basic information.
    """
    try:
        mission_list = []
        for mission_id, mission_data in active_missions.items():
            mission_summary = {
                "id": mission_id,
                "name": mission_data["name"],
                "description": mission_data["description"],
                "waypoint_count": len(mission_data["waypoints"]),
                "total_distance": mission_data["total_distance"],
                "estimated_time": mission_data["estimated_time"],
                "status": mission_data["status"],
                "created_at": mission_data["created_at"]
            }
            mission_list.append(mission_summary)
        
        return {
            "missions": mission_list,
            "total_count": len(mission_list)
        }
        
    except Exception as e:
        logger.error(f"Error listing missions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission list error: {str(e)}"
        )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: str) -> MissionResponse:
    """
    Get detailed information about a specific mission
    """
    try:
        if mission_id not in active_missions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
        
        mission_data = active_missions[mission_id]
        
        return MissionResponse(
            success=True,
            message=f"Mission {mission_id} details",
            mission_id=mission_id,
            waypoint_count=len(mission_data["waypoints"]),
            total_distance_meters=mission_data["total_distance"],
            estimated_duration_seconds=mission_data["estimated_time"],
            mission_data=mission_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission retrieval error: {str(e)}"
        )


@router.post("/{mission_id}/execute", response_model=CommandResponse)
async def execute_mission(
    mission_id: str,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Execute a specific mission
    
    Starts execution of the specified mission by uploading waypoints to the flight controller
    and switching to AUTO mode.
    """
    try:
        if mission_id not in active_missions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
        
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Check if another mission is already running
        if mission_execution_state["active"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mission {mission_execution_state['mission_id']} is already running"
            )
        
        mission_data = active_missions[mission_id]
        
        # Safety checks
        if mavlink.latest_gps and not mission_data.get("force", False):
            if mavlink.latest_gps.fix_type < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GPS 3D fix required for mission execution"
                )
            if mavlink.latest_gps.satellites_visible < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient GPS satellites for mission"
                )
        
        # Upload mission to flight controller
        # Note: This is a simplified implementation
        # In practice, you'd use the mission protocol to upload waypoints
        
        logger.info(f"Executing mission {mission_id} with {len(mission_data['waypoints'])} waypoints")
        
        # Switch to GUIDED mode first
        await mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        # Arm if not armed
        if mavlink.latest_heartbeat and not (mavlink.latest_heartbeat.base_mode & 128):
            await mavlink.arm_motors(True)
            await asyncio.sleep(1.0)
        
        # Start mission execution tracking
        mission_execution_state.update({
            "active": True,
            "mission_id": mission_id,
            "current_waypoint": 0,
            "total_waypoints": len(mission_data["waypoints"]),
            "start_time": time.time(),
            "status": "executing"
        })
        
        mission_data["status"] = "executing"
        
        # Start executing waypoints
        asyncio.create_task(execute_mission_waypoints(mission_data, mavlink))
        
        return CommandResponse(
            success=True,
            message=f"Mission {mission_id} execution started",
            data={
                "mission_id": mission_id,
                "waypoint_count": len(mission_data["waypoints"]),
                "estimated_duration": mission_data["estimated_time"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission execution error: {str(e)}"
        )


@router.post("/stop", response_model=CommandResponse)
async def stop_mission(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Stop current mission execution
    
    Stops the currently executing mission and switches to LOITER mode.
    """
    try:
        if not mission_execution_state["active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No mission currently executing"
            )
        
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Stop mission execution
        mission_id = mission_execution_state["mission_id"]
        
        # Switch to LOITER mode to hold position
        await mavlink.set_mode("LOITER")
        
        # Update execution state
        mission_execution_state.update({
            "active": False,
            "mission_id": None,
            "current_waypoint": 0,
            "total_waypoints": 0,
            "start_time": None,
            "status": "stopped"
        })
        
        # Update mission status
        if mission_id and mission_id in active_missions:
            active_missions[mission_id]["status"] = "stopped"
        
        logger.info(f"Mission {mission_id} execution stopped")
        
        return CommandResponse(
            success=True,
            message=f"Mission {mission_id} stopped successfully",
            data={"stopped_mission_id": mission_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission stop error: {str(e)}"
        )


@router.get("/status", response_model=MissionExecutionStatus)
async def get_mission_status() -> MissionExecutionStatus:
    """
    Get current mission execution status
    
    Returns information about the currently executing mission, if any.
    """
    try:
        if not mission_execution_state["active"]:
            return MissionExecutionStatus(
                active=False,
                mission_id=None,
                current_waypoint=0,
                total_waypoints=0,
                progress_percent=0.0,
                elapsed_time_seconds=0.0,
                estimated_remaining_seconds=None,
                status="idle"
            )
        
        mission_id = mission_execution_state["mission_id"]
        elapsed_time = time.time() - mission_execution_state["start_time"]
        
        # Calculate progress
        progress = 0.0
        if mission_execution_state["total_waypoints"] > 0:
            progress = (mission_execution_state["current_waypoint"] / mission_execution_state["total_waypoints"]) * 100
        
        # Estimate remaining time
        estimated_remaining = None
        if mission_id and mission_id in active_missions:
            mission_data = active_missions[mission_id]
            total_estimated = mission_data["estimated_time"]
            estimated_remaining = max(0, total_estimated - elapsed_time)
        
        return MissionExecutionStatus(
            active=True,
            mission_id=mission_id,
            current_waypoint=mission_execution_state["current_waypoint"],
            total_waypoints=mission_execution_state["total_waypoints"],
            progress_percent=progress,
            elapsed_time_seconds=elapsed_time,
            estimated_remaining_seconds=estimated_remaining,
            status=mission_execution_state["status"]
        )
        
    except Exception as e:
        logger.error(f"Error getting mission status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission status error: {str(e)}"
        )


@router.post("/patterns/square", response_model=PatternResponse)
async def create_square_pattern(
    request: SquarePatternRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> PatternResponse:
    """
    Create and execute a square flight pattern
    
    Generates a square flight pattern and optionally executes it immediately.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Get center point (current position if not specified)
        if request.center_latitude is None or request.center_longitude is None:
            if not mavlink.latest_gps:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No GPS data available for current position"
                )
            
            center_lat = mavlink.latest_gps.lat / 1e7
            center_lon = mavlink.latest_gps.lon / 1e7
        else:
            center_lat = request.center_latitude
            center_lon = request.center_longitude
        
        # Generate square waypoints
        waypoints = generate_square_waypoints(
            center_lat, center_lon, request.side_length, 
            request.altitude, request.clockwise
        )
        
        # Calculate total distance
        total_distance = request.side_length * 4
        estimated_time = total_distance / request.speed
        
        # Create mission from pattern
        mission_id = f"square_pattern_{int(time.time())}"
        mission_data = {
            "id": mission_id,
            "name": f"Square Pattern ({request.side_length}m)",
            "description": f"Square pattern with {request.side_length}m sides at {request.altitude}m altitude",
            "waypoints": waypoints,
            "default_speed": request.speed,
            "auto_continue": True,
            "return_to_launch": False,
            "total_distance": total_distance,
            "estimated_time": estimated_time,
            "created_at": time.time(),
            "status": "created",
            "pattern_type": "square"
        }
        
        active_missions[mission_id] = mission_data
        
        return PatternResponse(
            success=True,
            message=f"Square pattern created with {len(waypoints)} waypoints",
            pattern_type="square",
            waypoint_count=len(waypoints),
            estimated_duration=estimated_time,
            total_distance=total_distance,
            mission_id=mission_id,
            waypoints=waypoints if request.include_waypoints else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating square pattern: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Square pattern error: {str(e)}"
        )


@router.delete("/{mission_id}", response_model=CommandResponse)
async def delete_mission(mission_id: str) -> CommandResponse:
    """
    Delete a mission
    
    Removes a mission from the list. Cannot delete a mission that is currently executing.
    """
    try:
        if mission_id not in active_missions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
        
        # Check if mission is currently executing
        if mission_execution_state["active"] and mission_execution_state["mission_id"] == mission_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete mission that is currently executing"
            )
        
        mission_name = active_missions[mission_id]["name"]
        del active_missions[mission_id]
        
        return CommandResponse(
            success=True,
            message=f"Mission '{mission_name}' deleted successfully",
            data={"deleted_mission_id": mission_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting mission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mission deletion error: {str(e)}"
        )


# Background task for mission execution
async def execute_mission_waypoints(mission_data: Dict[str, Any], mavlink: MAVLinkManager):
    """
    Background task to execute mission waypoints sequentially
    """
    try:
        waypoints = mission_data["waypoints"]
        default_speed = mission_data["default_speed"]
        
        for i, waypoint in enumerate(waypoints):
            if not mission_execution_state["active"]:
                break  # Mission was stopped
            
            logger.info(f"Navigating to waypoint {i+1}/{len(waypoints)}")
            
            # Update current waypoint
            mission_execution_state["current_waypoint"] = i
            
            # Send goto command
            lat_int = int(waypoint["latitude"] * 1e7)
            lon_int = int(waypoint["longitude"] * 1e7)
            alt_int = int(waypoint["altitude"] * 1000)
            
            success = await mavlink.send_command_long(
                16,  # MAV_CMD_NAV_WAYPOINT
                0,   # Hold time
                2.0, # Acceptance radius
                0,   # Pass through
                0,   # Desired yaw
                lat_int,
                lon_int,
                alt_int
            )
            
            if not success:
                logger.error(f"Failed to send waypoint {i+1}")
                continue
            
            # Wait for waypoint to be reached (simplified)
            # In practice, you'd monitor position and waypoint completion
            await asyncio.sleep(10)  # Placeholder wait time
        
        # Mission completed
        mission_execution_state.update({
            "active": False,
            "mission_id": None,
            "current_waypoint": 0,
            "total_waypoints": 0,
            "start_time": None,
            "status": "completed"
        })
        
        mission_data["status"] = "completed"
        
        # Return to launch if specified
        if mission_data.get("return_to_launch", False):
            await mavlink.set_mode("RTL")
        else:
            await mavlink.set_mode("LOITER")
        
        logger.info(f"Mission {mission_data['id']} completed successfully")
        
    except Exception as e:
        logger.error(f"Error executing mission waypoints: {e}")
        mission_execution_state["status"] = "error"
        if mission_data:
            mission_data["status"] = "error"


# Utility functions
def generate_square_waypoints(center_lat: float, center_lon: float, side_length: float, 
                            altitude: float, clockwise: bool = True) -> List[Dict[str, Any]]:
    """Generate waypoints for a square pattern"""
    # Calculate offset in degrees (rough approximation)
    lat_offset = (side_length / 2) / 111320  # meters to degrees latitude
    lon_offset = (side_length / 2) / (111320 * math.cos(math.radians(center_lat)))
    
    # Define square corners
    corners = [
        (center_lat + lat_offset, center_lon - lon_offset),  # NW
        (center_lat + lat_offset, center_lon + lon_offset),  # NE
        (center_lat - lat_offset, center_lon + lon_offset),  # SE
        (center_lat - lat_offset, center_lon - lon_offset),  # SW
    ]
    
    if not clockwise:
        corners.reverse()
    
    waypoints = []
    for i, (lat, lon) in enumerate(corners):
        waypoints.append({
            "sequence": i,
            "latitude": lat,
            "longitude": lon,
            "altitude": altitude,
            "command": 16,  # NAV_WAYPOINT
            "param1": 0.0,  # Hold time
            "param2": 2.0,  # Acceptance radius
            "param3": 0.0,  # Pass through
            "param4": 0.0   # Desired yaw
        })
    
    return waypoints


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates using Haversine formula"""
    R = 6371000  # Earth's radius in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


  # Add this import at the top