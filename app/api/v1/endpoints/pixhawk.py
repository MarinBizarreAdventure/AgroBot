"""
Pixhawk control API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging

from app.core.mavlink.connection import MAVLinkManager
from app.models.pixhawk import (
    PixhawkStatus, FlightMode, ArmRequest, ModeRequest,
    CommandResponse, ParameterRequest, ParameterResponse
)
from main import get_mavlink_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pixhawk", tags=["Pixhawk Control"])


@router.get("/status", response_model=PixhawkStatus)
async def get_pixhawk_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> PixhawkStatus:
    """
    Get current Pixhawk flight controller status
    
    Returns comprehensive status information including:
    - Connection status
    - GPS data
    - Attitude information
    - Flight mode
    - Battery status
    - System health
    """
    try:
        status_data = mavlink.get_status()
        
        # Convert to response model
        pixhawk_status = PixhawkStatus(
            connected=status_data["connected"],
            state=status_data["state"],
            system_id=status_data["system_id"],
            component_id=status_data["component_id"],
            heartbeat_age=status_data.get("heartbeat_age"),
            heartbeat=status_data.get("latest_heartbeat"),
            gps=status_data.get("latest_gps"),
            attitude=status_data.get("latest_attitude")
        )
        
        return pixhawk_status
        
    except Exception as e:
        logger.error(f"Error getting Pixhawk status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Pixhawk status: {str(e)}"
        )


@router.post("/connect", response_model=CommandResponse)
async def connect_pixhawk(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Establish connection to Pixhawk flight controller
    
    Attempts to connect to the Pixhawk via MAVLink protocol.
    Will wait for heartbeat and establish communication.
    """
    try:
        if mavlink.is_connected():
            return CommandResponse(
                success=True,
                message="Already connected to Pixhawk",
                data={"state": "connected"}
            )
        
        logger.info("Attempting to connect to Pixhawk")
        success = await mavlink.connect()
        
        if success:
            return CommandResponse(
                success=True,
                message="Successfully connected to Pixhawk",
                data=mavlink.get_status()
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to Pixhawk"
            )
            
    except Exception as e:
        logger.error(f"Error connecting to Pixhawk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection error: {str(e)}"
        )


@router.post("/disconnect", response_model=CommandResponse)
async def disconnect_pixhawk(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Disconnect from Pixhawk flight controller
    
    Safely closes the MAVLink connection and stops all communication.
    """
    try:
        logger.info("Disconnecting from Pixhawk")
        await mavlink.disconnect()
        
        return CommandResponse(
            success=True,
            message="Successfully disconnected from Pixhawk",
            data={"state": "disconnected"}
        )
        
    except Exception as e:
        logger.error(f"Error disconnecting from Pixhawk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Disconnection error: {str(e)}"
        )


@router.post("/arm", response_model=CommandResponse)
async def arm_motors(
    request: ArmRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Arm or disarm motors
    
    SAFETY WARNING: Only arm motors when safe to do so.
    Ensure proper safety checks are performed before arming.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        action = "arm" if request.arm else "disarm"
        logger.info(f"Attempting to {action} motors")
        
        # Additional safety checks for arming
        if request.arm and request.force_arm is False:
            # Check GPS lock
            if mavlink.latest_gps:
                if mavlink.latest_gps.fix_type < 3:  # Require 3D fix
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="GPS fix required for arming (use force_arm=true to override)"
                    )
                if mavlink.latest_gps.satellites_visible < 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient GPS satellites for arming (use force_arm=true to override)"
                    )
        
        success = await mavlink.arm_motors(request.arm)
        
        if success:
            return CommandResponse(
                success=True,
                message=f"Successfully {action}ed motors",
                data={"armed": request.arm}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to {action} motors"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error arming/disarming motors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Motor control error: {str(e)}"
        )


@router.post("/mode", response_model=CommandResponse)
async def set_flight_mode(
    request: ModeRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Set flight mode
    
    Available modes:
    - MANUAL: Full manual control
    - STABILIZE: Attitude stabilization
    - GUIDED: Computer controlled flight
    - AUTO: Mission execution
    - RTL: Return to Launch
    - LOITER: Hold position
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        logger.info(f"Setting flight mode to {request.mode}")
        success = await mavlink.set_mode(request.mode.value)
        
        if success:
            return CommandResponse(
                success=True,
                message=f"Successfully set flight mode to {request.mode.value}",
                data={"mode": request.mode.value}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to set flight mode to {request.mode.value}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting flight mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flight mode error: {str(e)}"
        )


@router.post("/command", response_model=CommandResponse)
async def send_command(
    command_id: int,
    param1: float = 0.0,
    param2: float = 0.0,
    param3: float = 0.0,
    param4: float = 0.0,
    param5: float = 0.0,
    param6: float = 0.0,
    param7: float = 0.0,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Send custom MAVLink command
    
    Send a raw MAVLink command with up to 7 parameters.
    Use with caution - incorrect commands can cause unexpected behavior.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        logger.info(f"Sending MAVLink command {command_id}")
        success = await mavlink.send_command_long(
            command_id, param1, param2, param3, param4, param5, param6, param7
        )
        
        if success:
            return CommandResponse(
                success=True,
                message=f"Successfully sent command {command_id}",
                data={
                    "command": command_id,
                    "parameters": [param1, param2, param3, param4, param5, param6, param7]
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to send command {command_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command error: {str(e)}"
        )


@router.get("/heartbeat")
async def get_heartbeat(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> Dict[str, Any]:
    """
    Get latest heartbeat information
    
    Returns the most recent heartbeat data from the flight controller.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        if not mavlink.latest_heartbeat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No heartbeat data available"
            )
        
        return {
            "heartbeat": mavlink.latest_heartbeat.__dict__,
            "age_seconds": time.time() - mavlink.latest_heartbeat.timestamp
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting heartbeat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Heartbeat error: {str(e)}"
        )


@router.post("/emergency_stop", response_model=CommandResponse)
async def emergency_stop(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Emergency stop - immediately disarm motors
    
    EMERGENCY FUNCTION: Immediately disarms motors regardless of current state.
    Use only in emergency situations.
    """
    try:
        logger.warning("EMERGENCY STOP TRIGGERED")
        
        if not mavlink.is_connected():
            return CommandResponse(
                success=False,
                message="Cannot execute emergency stop: Not connected to Pixhawk",
                data={"emergency": True}
            )
        
        # Force disarm
        success = await mavlink.arm_motors(False)
        
        return CommandResponse(
            success=success,
            message="Emergency stop executed" if success else "Emergency stop failed",
            data={"emergency": True, "disarmed": success}
        )
        
    except Exception as e:
        logger.error(f"Error during emergency stop: {e}")
        return CommandResponse(
            success=False,
            message=f"Emergency stop error: {str(e)}",
            data={"emergency": True, "error": str(e)}
        )


@router.get("/capabilities")
async def get_capabilities() -> Dict[str, Any]:
    """
    Get Pixhawk capabilities and supported features
    
    Returns information about what the flight controller supports.
    """
    return {
        "supported_modes": [mode.value for mode in FlightMode],
        "mavlink_version": "2.0",
        "supported_commands": [
            "ARM/DISARM",
            "SET_MODE", 
            "COMMAND_LONG",
            "EMERGENCY_STOP"
        ],
        "features": {
            "gps": True,
            "attitude_control": True,
            "position_control": True,
            "mission_support": True,
            "failsafe": True,
            "geofencing": True
        }
    }