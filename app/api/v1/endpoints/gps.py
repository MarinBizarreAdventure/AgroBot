"""
GPS data API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional
import logging
import time
import math
from datetime import datetime, timedelta

from app.core.mavlink.connection import MAVLinkManager
from app.models.gps import (
    GPSPosition, GPSStatus, GPSHistory, GPSAccuracy,
    CoordinateRequest, DistanceResponse, GeofenceStatus
)
from config.settings import get_settings
from main import get_mavlink_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Store GPS history (in production, consider using a database)
gps_history: List[Dict[str, Any]] = []


@router.get("/current", response_model=GPSPosition)
async def get_current_position(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> GPSPosition:
    """
    Get current GPS position
    
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
        
        return GPSPosition(
            latitude=gps.lat / 1e7,  # Convert from degrees * 1e7
            longitude=gps.lon / 1e7,
            altitude=gps.alt / 1000.0,  # Convert from mm to meters
            relative_altitude=gps.relative_alt / 1000.0,
            ground_speed=gps.vel / 100.0,  # Convert from cm/s to m/s
            heading=gps.cog / 100.0,  # Convert from degrees * 100
            timestamp=gps.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current GPS position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS error: {str(e)}"
        )


@router.get("/status", response_model=GPSStatus)
async def get_gps_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> GPSStatus:
    """
    Get GPS receiver status and accuracy information
    
    Returns detailed GPS status including fix type, satellite count,
    accuracy metrics, and overall health assessment.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        if not mavlink.latest_gps:
            return GPSStatus(
                available=False,
                fix_type=0,
                satellites_visible=0,
                hdop=99.9,
                vdop=99.9,
                accuracy_estimate=999.9,
                has_good_fix=False,
                ready_for_navigation=False,
                last_update=None
            )
        
        gps = mavlink.latest_gps
        settings = get_settings()
        
        # Calculate accuracy estimate from HDOP
        accuracy_estimate = gps.hdop * 5.0  # Rough estimate in meters
        
        # Determine if GPS is ready for navigation
        has_good_fix = (
            gps.fix_type >= 3 and
            gps.satellites_visible >= settings.GPS_MIN_SATELLITES and
            gps.hdop <= settings.GPS_MAX_HDOP
        )
        
        return GPSStatus(
            available=True,
            fix_type=gps.fix_type,
            satellites_visible=gps.satellites_visible,
            hdop=gps.hdop,
            vdop=gps.vdop,
            accuracy_estimate=accuracy_estimate,
            has_good_fix=has_good_fix,
            ready_for_navigation=has_good_fix,
            last_update=gps.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GPS status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS status error: {str(e)}"
        )


@router.get("/accuracy", response_model=GPSAccuracy)
async def get_gps_accuracy(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> GPSAccuracy:
    """
    Get detailed GPS accuracy metrics
    
    Returns comprehensive accuracy information including dilution of precision,
    estimated position error, and accuracy classification.
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
        
        # Calculate position error estimates
        horizontal_error = gps.hdop * 5.0  # Rough estimate
        vertical_error = gps.vdop * 5.0
        
        # Classify accuracy
        if gps.hdop <= 1.0:
            accuracy_class = "excellent"
        elif gps.hdop <= 2.0:
            accuracy_class = "good"
        elif gps.hdop <= 5.0:
            accuracy_class = "moderate"
        else:
            accuracy_class = "poor"
        
        return GPSAccuracy(
            hdop=gps.hdop,
            vdop=gps.vdop,
            pdop=math.sqrt(gps.hdop**2 + gps.vdop**2),
            horizontal_error_estimate=horizontal_error,
            vertical_error_estimate=vertical_error,
            accuracy_class=accuracy_class,
            suitable_for_navigation=gps.hdop <= get_settings().GPS_MAX_HDOP
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GPS accuracy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS accuracy error: {str(e)}"
        )


@router.get("/history", response_model=GPSHistory)
async def get_gps_history(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    start_time: Optional[float] = Query(None, description="Start timestamp (Unix time)"),
    end_time: Optional[float] = Query(None, description="End timestamp (Unix time)")
) -> GPSHistory:
    """
    Get GPS position history
    
    Returns historical GPS positions with optional time filtering.
    Useful for tracking movement and creating flight paths.
    """
    try:
        global gps_history
        
        filtered_history = gps_history
        
        # Apply time filters
        if start_time:
            filtered_history = [h for h in filtered_history if h["timestamp"] >= start_time]
        if end_time:
            filtered_history = [h for h in filtered_history if h["timestamp"] <= end_time]
        
        # Apply limit
        filtered_history = filtered_history[-limit:]
        
        # Calculate total distance if we have multiple points
        total_distance = 0.0
        if len(filtered_history) > 1:
            for i in range(1, len(filtered_history)):
                prev = filtered_history[i-1]
                curr = filtered_history[i]
                distance = calculate_distance(
                    prev["latitude"], prev["longitude"],
                    curr["latitude"], curr["longitude"]
                )
                total_distance += distance
        
        return GPSHistory(
            positions=filtered_history,
            count=len(filtered_history),
            total_distance_meters=total_distance,
            time_span_seconds=filtered_history[-1]["timestamp"] - filtered_history[0]["timestamp"] if filtered_history else 0
        )
        
    except Exception as e:
        logger.error(f"Error getting GPS history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS history error: {str(e)}"
        )


@router.post("/distance", response_model=DistanceResponse)
async def calculate_distance_to_coordinates(
    request: CoordinateRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> DistanceResponse:
    """
    Calculate distance to specified coordinates
    
    Calculates distance, bearing, and estimated travel time from current position
    to the specified coordinates.
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
        
        current_gps = mavlink.latest_gps
        current_lat = current_gps.lat / 1e7
        current_lon = current_gps.lon / 1e7
        
        # Calculate distance and bearing
        distance = calculate_distance(current_lat, current_lon, request.latitude, request.longitude)
        bearing = calculate_bearing(current_lat, current_lon, request.latitude, request.longitude)
        
        # Estimate travel time
        ground_speed = current_gps.vel / 100.0  # m/s
        estimated_time = distance / max(ground_speed, 1.0) if ground_speed > 0.1 else None
        
        return DistanceResponse(
            distance_meters=distance,
            bearing_degrees=bearing,
            estimated_travel_time_seconds=estimated_time,
            current_position={
                "latitude": current_lat,
                "longitude": current_lon,
                "altitude": current_gps.relative_alt / 1000.0
            },
            target_position={
                "latitude": request.latitude,
                "longitude": request.longitude,
                "altitude": request.altitude or 0
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


@router.get("/geofence", response_model=GeofenceStatus)
async def get_geofence_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> GeofenceStatus:
    """
    Get geofence status and position relative to boundaries
    
    Returns information about geofence settings and current position
    relative to the defined boundaries.
    """
    try:
        settings = get_settings()
        
        if not settings.GEOFENCE_ENABLED:
            return GeofenceStatus(
                enabled=False,
                inside_fence=True,
                distance_to_fence=None,
                fence_radius=settings.GEOFENCE_RADIUS,
                fence_center=None
            )
        
        if not mavlink.is_connected() or not mavlink.latest_gps:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GPS data required for geofence status"
            )
        
        current_gps = mavlink.latest_gps
        current_lat = current_gps.lat / 1e7
        current_lon = current_gps.lon / 1e7
        
        # For simplicity, assume geofence center is the home position
        # In practice, you'd store this when the system is armed/initialized
        fence_center_lat = current_lat  # This should be stored as home position
        fence_center_lon = current_lon
        
        # Calculate distance from fence center
        distance_from_center = calculate_distance(
            current_lat, current_lon,
            fence_center_lat, fence_center_lon
        )
        
        inside_fence = distance_from_center <= settings.GEOFENCE_RADIUS
        distance_to_fence = settings.GEOFENCE_RADIUS - distance_from_center
        
        return GeofenceStatus(
            enabled=True,
            inside_fence=inside_fence,
            distance_to_fence=distance_to_fence,
            fence_radius=settings.GEOFENCE_RADIUS,
            fence_center={
                "latitude": fence_center_lat,
                "longitude": fence_center_lon
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting geofence status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Geofence status error: {str(e)}"
        )


@router.post("/log", status_code=status.HTTP_201_CREATED)
async def log_gps_position(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> Dict[str, Any]:
    """
    Manually log current GPS position to history
    
    Adds the current GPS position to the history log.
    This happens automatically during normal operation.
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
        
        # Add to history
        global gps_history
        position_data = {
            "timestamp": gps.timestamp,
            "latitude": gps.lat / 1e7,
            "longitude": gps.lon / 1e7,
            "altitude": gps.alt / 1000.0,
            "relative_altitude": gps.relative_alt / 1000.0,
            "ground_speed": gps.vel / 100.0,
            "heading": gps.cog / 100.0,
            "satellites": gps.satellites_visible,
            "hdop": gps.hdop,
            "fix_type": gps.fix_type
        }
        
        gps_history.append(position_data)
        
        # Keep only last 1000 positions
        if len(gps_history) > 1000:
            gps_history = gps_history[-1000:]
        
        return {
            "success": True,
            "message": "GPS position logged",
            "position": position_data,
            "history_count": len(gps_history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging GPS position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS logging error: {str(e)}"
        )


@router.delete("/history", status_code=status.HTTP_200_OK)
async def clear_gps_history() -> Dict[str, Any]:
    """
    Clear GPS position history
    
    Removes all stored GPS history data.
    """
    try:
        global gps_history
        history_count = len(gps_history)
        gps_history.clear()
        
        return {
            "success": True,
            "message": f"Cleared {history_count} GPS history records",
            "remaining_count": len(gps_history)
        }
        
    except Exception as e:
        logger.error(f"Error clearing GPS history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPS history clear error: {str(e)}"
        )


# Background task to automatically log GPS positions
async def log_gps_position_automatically(mavlink: MAVLinkManager):
    """
    Background task to automatically log GPS positions
    This would be called by the telemetry service
    """
    try:
        if mavlink.is_connected() and mavlink.latest_gps:
            gps = mavlink.latest_gps
            
            global gps_history
            
            # Check if we should log (avoid duplicates)
            should_log = True
            if gps_history:
                last_entry = gps_history[-1]
                time_diff = gps.timestamp - last_entry["timestamp"]
                if time_diff < 1.0:  # Don't log more than once per second
                    should_log = False
            
            if should_log:
                position_data = {
                    "timestamp": gps.timestamp,
                    "latitude": gps.lat / 1e7,
                    "longitude": gps.lon / 1e7,
                    "altitude": gps.alt / 1000.0,
                    "relative_altitude": gps.relative_alt / 1000.0,
                    "ground_speed": gps.vel / 100.0,
                    "heading": gps.cog / 100.0,
                    "satellites": gps.satellites_visible,
                    "hdop": gps.hdop,
                    "fix_type": gps.fix_type
                }
                
                gps_history.append(position_data)
                
                # Keep only last 1000 positions
                if len(gps_history) > 1000:
                    gps_history = gps_history[-1000:]
    
    except Exception as e:
        logger.debug(f"Error in automatic GPS logging: {e}")


# Utility functions
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


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2"""
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