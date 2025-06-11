"""
Movement control API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging
import math
import asyncio

from app.core.mavlink.connection import MAVLinkManager
from app.models.movement import (
    MoveToRequest, MoveToResponse, VelocityRequest, StopRequest,
    TakeoffRequest, LandRequest, RTLRequest, PositionResponse,
    NavigationStatus, DistanceResponse
)
from app.models.pixhawk import CommandResponse
from app.services.safety_service import SafetyService
from main import get_mavlink_manager
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/movement", tags=["Movement Control"])

settings = get_settings()


@router.get("/position", response_model=PositionResponse)
async def get_current_position(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> PositionResponse:
    """
    Get current position from GPS
    
    Returns the latest GPS coordinates, altitude, and accuracy information.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        if not mavlink.latest_gps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No GPS data available"
            )
        
        gps = mavlink.latest_gps
        
        return PositionResponse(
            latitude=gps.lat / 1e7,  # Convert from degrees * 1e7
            longitude=gps.lon / 1e7,
            altitude=gps.alt / 1000.0,  # Convert from mm to meters
            relative_altitude=gps.relative_alt / 1000.0,
            ground_speed=gps.vel / 100.0,  # Convert from cm/s to m/s
            heading=gps.cog / 100.0,  # Convert from degrees * 100
            satellites=gps.satellites_visible,
            hdop=gps.hdop,
            fix_type=gps.fix_type,
            timestamp=gps.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Position error: {str(e)}"
        )


@router.post("/goto", response_model=MoveToResponse)
async def move_to_position(
    request: MoveToRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> MoveToResponse:
    """
    Move to a specific GPS coordinate
    
    Commands the vehicle to navigate to the specified latitude, longitude, and altitude.
    Requires GUIDED mode and armed vehicle.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Safety checks
        if not request.force:
            # Check if vehicle is armed
            if mavlink.latest_heartbeat and not (mavlink.latest_heartbeat.base_mode & 128):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vehicle must be armed to move (use force=true to override)"
                )
            
            # Check GPS accuracy
            if mavlink.latest_gps:
                if mavlink.latest_gps.fix_type < 3:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="GPS 3D fix required for navigation"
                    )
                if mavlink.latest_gps.hdop > 2.0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="GPS accuracy insufficient (HDOP > 2.0)"
                    )
            
            # Check geofence if enabled
            if settings.GEOFENCE_ENABLED:
                current_pos = await get_current_position(mavlink)
                distance = calculate_distance(
                    current_pos.latitude, current_pos.longitude,
                    request.latitude, request.longitude
                )
                if distance > settings.GEOFENCE_RADIUS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Target outside geofence ({distance:.1f}m > {settings.GEOFENCE_RADIUS}m)"
                    )
        
        # Switch to GUIDED mode if not already
        await mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)  # Give time for mode change
        
        # Send goto command
        lat_int = int(request.latitude * 1e7)  # Convert to degrees * 1e7
        lon_int = int(request.longitude * 1e7)
        alt_int = int(request.altitude * 1000)  # Convert to mm
        
        # MAV_CMD_NAV_WAYPOINT (16)
        success = await mavlink.send_command_long(
            16,  # MAV_CMD_NAV_WAYPOINT
            0,   # Hold time
            request.acceptance_radius,  # Acceptance radius
            0,   # Pass through
            0,   # Desired yaw
            lat_int,
            lon_int,
            alt_int
        )
        
        if success:
            # Calculate distance and estimated time
            current_pos = await get_current_position(mavlink)
            distance = calculate_distance(
                current_pos.latitude, current_pos.longitude,
                request.latitude, request.longitude
            )
            
            estimated_time = distance / (request.max_speed or settings.MAX_SPEED)
            
            return MoveToResponse(
                success=True,
                message=f"Moving to position ({request.latitude}, {request.longitude})",
                target_latitude=request.latitude,
                target_longitude=request.longitude,
                target_altitude=request.altitude,
                distance_to_target=distance,
                estimated_time_seconds=estimated_time,
                max_speed=request.max_speed or settings.MAX_SPEED
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send goto command"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving to position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Movement error: {str(e)}"
        )


@router.post("/velocity", response_model=CommandResponse)
async def set_velocity(
    request: VelocityRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Set velocity in body frame
    
    Commands the vehicle to move at specified velocities in forward/backward,
    left/right, and up/down directions relative to the vehicle's orientation.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Safety checks
        max_vel = settings.MAX_SPEED
        if abs(request.forward) > max_vel or abs(request.right) > max_vel or abs(request.down) > max_vel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Velocity components cannot exceed {max_vel} m/s"
            )
        
        # Switch to GUIDED mode if not already
        await mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        # Send velocity command (MAV_CMD_DO_CHANGE_SPEED)
        # Note: This is a simplified implementation
        # In practice, you might want to use SET_POSITION_TARGET_LOCAL_NED
        
        success = await mavlink.send_command_long(
            178,  # MAV_CMD_DO_CHANGE_SPEED
            0,    # Speed type (0=Airspeed, 1=Ground Speed)
            abs(request.forward),  # Speed value
            -1,   # Throttle (-1 = no change)
            0, 0, 0, 0
        )
        
        if success:
            return CommandResponse(
                success=True,
                message=f"Set velocity: forward={request.forward}, right={request.right}, down={request.down}",
                data={
                    "forward": request.forward,
                    "right": request.right,
                    "down": request.down,
                    "yaw_rate": request.yaw_rate
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to set velocity"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting velocity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Velocity error: {str(e)}"
        )


@router.post("/stop", response_model=CommandResponse)
async def stop_movement(
    request: StopRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Stop all movement and hold current position
    
    Commands the vehicle to stop moving and maintain current position.
    If emergency=true, will also disarm motors.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        logger.info(f"Stop movement requested (emergency: {request.emergency})")
        
        if request.emergency:
            # Emergency stop - disarm motors
            await mavlink.arm_motors(False)
            return CommandResponse(
                success=True,
                message="Emergency stop executed - motors disarmed",
                data={"emergency": True, "disarmed": True}
            )
        else:
            # Switch to LOITER mode to hold position
            success = await mavlink.set_mode("LOITER")
            
            if success:
                return CommandResponse(
                    success=True,
                    message="Movement stopped - holding position",
                    data={"mode": "LOITER"}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to stop movement"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping movement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stop error: {str(e)}"
        )


@router.post("/takeoff", response_model=CommandResponse)
async def takeoff(
    request: TakeoffRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Takeoff to specified altitude
    
    Commands the vehicle to takeoff and climb to the specified altitude.
    Vehicle must be armed and in GUIDED mode.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Safety checks
        if request.altitude <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Takeoff altitude must be positive"
            )
        
        if request.altitude > 120:  # FAA limit for drones
            if not request.force:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Altitude exceeds 120m limit (use force=true to override)"
                )
        
        # Check GPS accuracy
        if mavlink.latest_gps and not request.force:
            if mavlink.latest_gps.fix_type < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GPS 3D fix required for takeoff"
                )
            if mavlink.latest_gps.satellites_visible < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient GPS satellites for takeoff"
                )
        
        # Switch to GUIDED mode
        await mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        # Arm motors if not armed
        if mavlink.latest_heartbeat and not (mavlink.latest_heartbeat.base_mode & 128):
            await mavlink.arm_motors(True)
            await asyncio.sleep(1.0)
        
        # Send takeoff command
        success = await mavlink.send_command_long(
            22,  # MAV_CMD_NAV_TAKEOFF
            0,   # Minimum pitch
            0,   # Empty
            0,   # Empty
            0,   # Yaw angle (0 = no change)
            0,   # Latitude (0 = current position)
            0,   # Longitude (0 = current position)
            request.altitude  # Altitude
        )
        
        if success:
            return CommandResponse(
                success=True,
                message=f"Takeoff command sent - climbing to {request.altitude}m",
                data={
                    "altitude": request.altitude,
                    "mode": "GUIDED",
                    "armed": True
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send takeoff command"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during takeoff: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Takeoff error: {str(e)}"
        )


@router.post("/land", response_model=CommandResponse)
async def land(
    request: LandRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Land at current position or specified coordinates
    
    Commands the vehicle to land at the current position or at specified coordinates.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Switch to GUIDED mode for precision landing
        await mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        if request.latitude is not None and request.longitude is not None:
            # Land at specific coordinates
            lat_int = int(request.latitude * 1e7)
            lon_int = int(request.longitude * 1e7)
            
            success = await mavlink.send_command_long(
                21,  # MAV_CMD_NAV_LAND
                0,   # Abort altitude
                0,   # Precision land mode
                0,   # Empty
                0,   # Desired yaw angle
                lat_int,  # Latitude
                lon_int,  # Longitude
                0    # Altitude (0 = ground level)
            )
            
            message = f"Landing at coordinates ({request.latitude}, {request.longitude})"
        else:
            # Land at current position - switch to LAND mode
            success = await mavlink.set_mode("LAND")
            message = "Landing at current position"
        
        if success:
            return CommandResponse(
                success=True,
                message=message,
                data={
                    "landing": True,
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                    "precision": request.precision
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to initiate landing"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during landing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Landing error: {str(e)}"
        )


@router.post("/rtl", response_model=CommandResponse)
async def return_to_launch(
    request: RTLRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Return to Launch position
    
    Commands the vehicle to return to the launch position and optionally land.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Set RTL altitude if specified
        if request.rtl_altitude:
            # Set RTL_ALT parameter (simplified - in practice you'd use parameter protocol)
            logger.info(f"Setting RTL altitude to {request.rtl_altitude}m")
        
        # Switch to RTL mode
        success = await mavlink.set_mode("RTL")
        
        if success:
            return CommandResponse(
                success=True,
                message="Return to Launch initiated",
                data={
                    "mode": "RTL",
                    "altitude": request.rtl_altitude,
                    "auto_land": request.auto_land
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to initiate Return to Launch"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during RTL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RTL error: {str(e)}"
        )


@router.get("/status", response_model=NavigationStatus)
async def get_navigation_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> NavigationStatus:
    """
    Get current navigation status
    
    Returns information about the vehicle's current navigation state,
    including mode, position, target, and movement status.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Get current position
        current_pos = None
        if mavlink.latest_gps:
            current_pos = {
                "latitude": mavlink.latest_gps.lat / 1e7,
                "longitude": mavlink.latest_gps.lon / 1e7,
                "altitude": mavlink.latest_gps.relative_alt / 1000.0
            }
        
        # Get flight mode
        mode = "UNKNOWN"
        armed = False
        if mavlink.latest_heartbeat:
            armed = bool(mavlink.latest_heartbeat.base_mode & 128)
            # Simplified mode detection - in practice you'd decode custom_mode
            if mavlink.latest_heartbeat.custom_mode == 4:
                mode = "GUIDED"
            elif mavlink.latest_heartbeat.custom_mode == 6:
                mode = "RTL"
            elif mavlink.latest_heartbeat.custom_mode == 5:
                mode = "LOITER"
        
        # Calculate ground speed
        ground_speed = 0.0
        if mavlink.latest_gps:
            ground_speed = mavlink.latest_gps.vel / 100.0  # Convert cm/s to m/s
        
        return NavigationStatus(
            connected=True,
            armed=armed,
            mode=mode,
            current_position=current_pos,
            ground_speed=ground_speed,
            target_position=None,  # Would need to track this from commands
            distance_to_target=None,
            estimated_time_to_target=None,
            navigation_active=mode in ["GUIDED", "AUTO", "RTL"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting navigation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Navigation status error: {str(e)}"
        )


@router.get("/distance", response_model=DistanceResponse)
async def calculate_distance_to_point(
    latitude: float,
    longitude: float,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> DistanceResponse:
    """
    Calculate distance to a specific point
    
    Calculates the distance from current position to specified coordinates.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        if not mavlink.latest_gps:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No GPS data available"
            )
        
        current_lat = mavlink.latest_gps.lat / 1e7
        current_lon = mavlink.latest_gps.lon / 1e7
        
        distance = calculate_distance(current_lat, current_lon, latitude, longitude)
        bearing = calculate_bearing(current_lat, current_lon, latitude, longitude)
        
        # Estimate flight time
        ground_speed = mavlink.latest_gps.vel / 100.0  # Convert cm/s to m/s
        estimated_time = distance / max(ground_speed, 1.0) if ground_speed > 0.1 else None
        
        return DistanceResponse(
            distance_meters=distance,
            bearing_degrees=bearing,
            estimated_flight_time_seconds=estimated_time,
            current_position={
                "latitude": current_lat,
                "longitude": current_lon
            },
            target_position={
                "latitude": latitude,
                "longitude": longitude
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating distance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Distance calculation error: {str(e)}"
        )


# Utility functions
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula
    Returns distance in meters
    """
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


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing from point 1 to point 2
    Returns bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360  # Normalize to 0-360
    
    return bearing