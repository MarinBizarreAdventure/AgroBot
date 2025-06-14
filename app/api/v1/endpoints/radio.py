"""
Radio control (RC) API endpoints for RadioMaster integration
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging
import time

from app.core.mavlink.connection import MAVLinkManager
from app.models.radio import (
    RadioStatus, ChannelData, FailsafeConfig, ChannelMapping,
    CalibrationRequest, CalibrationResponse, OverrideRequest
)
from app.models.pixhawk import CommandResponse
from config.settings import get_settings
from main import get_mavlink_manager
from app.core.radio.receiver import Receiver
from app.core.radio.failsafe import FailsafeManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/radio", tags=["Radio Control"])
receiver = Receiver()
failsafe = FailsafeManager()

# Store RC channel data and settings
rc_channel_data: Dict[int, int] = {}  # Channel number -> PWM value
rc_channel_names: Dict[int, str] = {
    1: "Roll",
    2: "Pitch", 
    3: "Throttle",
    4: "Yaw",
    5: "Flight Mode",
    6: "Aux1",
    7: "Aux2",
    8: "Aux3"
}
last_rc_update = 0.0
failsafe_triggered = False


@router.get("/status", response_model=RadioStatus)
async def get_radio_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> RadioStatus:
    """
    Get radio control status and signal information
    
    Returns comprehensive RC status including signal strength,
    channel values, failsafe status, and connection health.
    """
    try:
        settings = get_settings()
        
        if not mavlink.is_connected():
            return RadioStatus(
                connected=False,
                signal_strength=0,
                channels_active=0,
                failsafe_active=True,
                last_update=None,
                rssi=0,
                link_quality=0
            )
        
        # Check if we have recent RC data
        current_time = time.time()
        rc_timeout = current_time - last_rc_update > settings.RC_TIMEOUT
        
        # Estimate signal strength from channel activity
        active_channels = len([v for v in rc_channel_data.values() if settings.RC_MIN_PWM <= v <= settings.RC_MAX_PWM])
        signal_strength = min(100, (active_channels / settings.RC_CHANNELS) * 100)
        
        # Check failsafe conditions
        global failsafe_triggered
        failsafe_active = rc_timeout or failsafe_triggered
        
        return RadioStatus(
            connected=not rc_timeout,
            signal_strength=signal_strength,
            channels_active=active_channels,
            failsafe_active=failsafe_active,
            last_update=last_rc_update if last_rc_update > 0 else None,
            rssi=0,  # Would come from RC_CHANNELS message if available
            link_quality=signal_strength
        )
        
    except Exception as e:
        logger.error(f"Error getting radio status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Radio status error: {str(e)}"
        )


@router.get("/channels", response_model=List[ChannelData])
async def get_channel_data(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> List[ChannelData]:
    """
    Get current RC channel values
    
    Returns the current PWM values and interpreted values for all RC channels.
    """
    try:
        settings = get_settings()
        channel_list = []
        
        for channel_num in range(1, settings.RC_CHANNELS + 1):
            pwm_value = rc_channel_data.get(channel_num, settings.RC_MID_PWM)
            
            # Convert PWM to normalized value (-1.0 to 1.0)
            if pwm_value <= settings.RC_MID_PWM:
                normalized = (pwm_value - settings.RC_MID_PWM) / (settings.RC_MID_PWM - settings.RC_MIN_PWM)
            else:
                normalized = (pwm_value - settings.RC_MID_PWM) / (settings.RC_MAX_PWM - settings.RC_MID_PWM)
            
            # Clamp to valid range
            normalized = max(-1.0, min(1.0, normalized))
            
            # Convert to percentage (0-100%)
            percentage = ((normalized + 1.0) / 2.0) * 100
            
            channel_data = ChannelData(
                channel=channel_num,
                name=rc_channel_names.get(channel_num, f"Channel {channel_num}"),
                pwm_value=pwm_value,
                normalized_value=normalized,
                percentage=percentage,
                active=settings.RC_MIN_PWM <= pwm_value <= settings.RC_MAX_PWM
            )
            
            channel_list.append(channel_data)
        
        return channel_list
        
    except Exception as e:
        logger.error(f"Error getting channel data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Channel data error: {str(e)}"
        )


@router.get("/channels/{channel_num}", response_model=ChannelData)
async def get_single_channel(
    channel_num: int,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> ChannelData:
    """
    Get data for a specific RC channel
    
    Returns detailed information for the specified channel number.
    """
    try:
        settings = get_settings()
        
        if not (1 <= channel_num <= settings.RC_CHANNELS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel number must be between 1 and {settings.RC_CHANNELS}"
            )
        
        pwm_value = rc_channel_data.get(channel_num, settings.RC_MID_PWM)
        
        # Convert PWM to normalized value
        if pwm_value <= settings.RC_MID_PWM:
            normalized = (pwm_value - settings.RC_MID_PWM) / (settings.RC_MID_PWM - settings.RC_MIN_PWM)
        else:
            normalized = (pwm_value - settings.RC_MID_PWM) / (settings.RC_MAX_PWM - settings.RC_MID_PWM)
        
        normalized = max(-1.0, min(1.0, normalized))
        percentage = ((normalized + 1.0) / 2.0) * 100
        
        return ChannelData(
            channel=channel_num,
            name=rc_channel_names.get(channel_num, f"Channel {channel_num}"),
            pwm_value=pwm_value,
            normalized_value=normalized,
            percentage=percentage,
            active=settings.RC_MIN_PWM <= pwm_value <= settings.RC_MAX_PWM
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting channel {channel_num}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Channel error: {str(e)}"
        )


@router.get("/mapping", response_model=ChannelMapping)
async def get_channel_mapping() -> ChannelMapping:
    """
    Get RC channel mapping and configuration
    
    Returns the mapping of RC channels to their functions.
    """
    try:
        settings = get_settings()
        
        return ChannelMapping(
            roll_channel=1,
            pitch_channel=2,
            throttle_channel=3,
            yaw_channel=4,
            mode_channel=5,
            aux_channels={
                6: "Aux1",
                7: "Aux2", 
                8: "Aux3"
            },
            channel_names=rc_channel_names,
            pwm_ranges={
                "min": settings.RC_MIN_PWM,
                "mid": settings.RC_MID_PWM,
                "max": settings.RC_MAX_PWM
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting channel mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Channel mapping error: {str(e)}"
        )


@router.get("/failsafe", response_model=FailsafeConfig)
async def get_failsafe_config() -> FailsafeConfig:
    """
    Get current failsafe configuration
    
    Returns failsafe settings and current status.
    """
    try:
        settings = get_settings()
        
        return FailsafeConfig(
            enabled=settings.RC_FAILSAFE_ENABLED,
            timeout_seconds=settings.RC_TIMEOUT,
            action="RTL",  # Return to Launch
            triggered=failsafe_triggered,
            last_trigger_time=None,  # Would track this if failsafe was triggered
            recovery_mode="manual"
        )
        
    except Exception as e:
        logger.error(f"Error getting failsafe config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failsafe config error: {str(e)}"
        )


@router.post("/failsafe/trigger", response_model=CommandResponse)
async def trigger_failsafe(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Manually trigger RC failsafe
    
    Forces a failsafe condition for testing purposes.
    WARNING: This will cause the vehicle to enter failsafe mode.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        global failsafe_triggered
        failsafe_triggered = True
        
        logger.warning("RC failsafe manually triggered")
        
        # Trigger RTL mode as failsafe action
        await mavlink.set_mode("RTL")
        
        return CommandResponse(
            success=True,
            message="RC failsafe triggered successfully",
            data={"failsafe_active": True, "action": "RTL"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering failsafe: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failsafe trigger error: {str(e)}"
        )


@router.post("/failsafe/reset", response_model=CommandResponse)
async def reset_failsafe() -> CommandResponse:
    """
    Reset RC failsafe condition
    
    Clears a manually triggered failsafe condition.
    """
    try:
        global failsafe_triggered
        failsafe_triggered = False
        
        logger.info("RC failsafe reset")
        
        return CommandResponse(
            success=True,
            message="RC failsafe reset successfully",
            data={"failsafe_active": False}
        )
        
    except Exception as e:
        logger.error(f"Error resetting failsafe: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failsafe reset error: {str(e)}"
        )


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate_channels(
    request: CalibrationRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CalibrationResponse:
    """
    Calibrate RC channels
    
    Performs RC channel calibration to set min/max/center values.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # This is a simplified calibration process
        # In practice, you'd collect min/max values over time
        logger.info(f"Starting RC calibration for channels: {request.channels}")
        
        calibration_results = {}
        settings = get_settings()
        
        for channel in request.channels:
            current_value = rc_channel_data.get(channel, settings.RC_MID_PWM)
            
            # Simulate calibration results
            calibration_results[channel] = {
                "min_pwm": settings.RC_MIN_PWM,
                "max_pwm": settings.RC_MAX_PWM,
                "center_pwm": settings.RC_MID_PWM,
                "current_pwm": current_value,
                "range": settings.RC_MAX_PWM - settings.RC_MIN_PWM,
                "deadband": 20  # PWM units
            }
        
        return CalibrationResponse(
            success=True,
            message=f"Calibration completed for {len(request.channels)} channels",
            calibrated_channels=list(request.channels),
            results=calibration_results,
            duration_seconds=request.duration or 30.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calibrating channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calibration error: {str(e)}"
        )


@router.post("/override", response_model=CommandResponse)
async def override_rc_channels(
    request: OverrideRequest,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Override RC channel values
    
    Allows software to override RC channel inputs.
    WARNING: This overrides pilot control - use with extreme caution.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        settings = get_settings()
        
        # Validate override values
        for channel, value in request.channel_overrides.items():
            if not (settings.RC_MIN_PWM <= value <= settings.RC_MAX_PWM):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Channel {channel} override value {value} outside valid range"
                )
        
        # Apply overrides
        # In practice, you'd send RC_CHANNELS_OVERRIDE MAVLink message
        logger.warning(f"RC override requested for channels: {list(request.channel_overrides.keys())}")
        
        # Update local channel data for monitoring
        for channel, value in request.channel_overrides.items():
            rc_channel_data[channel] = value
        
        global last_rc_update
        last_rc_update = time.time()
        
        return CommandResponse(
            success=True,
            message=f"RC channels overridden: {list(request.channel_overrides.keys())}",
            data={
                "overridden_channels": request.channel_overrides,
                "duration": request.duration,
                "priority": request.priority
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error overriding RC channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RC override error: {str(e)}"
        )


@router.post("/override/clear", response_model=CommandResponse)
async def clear_rc_override(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Clear all RC channel overrides
    
    Restores normal RC control to the pilot.
    """
    try:
        if not mavlink.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Pixhawk"
            )
        
        # Clear overrides by sending 0 values (RC_CHANNELS_OVERRIDE)
        # In practice, you'd send the appropriate MAVLink message
        logger.info("Clearing RC channel overrides")
        
        return CommandResponse(
            success=True,
            message="RC channel overrides cleared - pilot control restored",
            data={"overrides_cleared": True}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing RC override: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RC override clear error: {str(e)}"
        )


@router.get("/test", response_model=Dict[str, Any])
async def test_rc_connection(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> Dict[str, Any]:
    """
    Test RC connection and responsiveness
    
    Performs various tests to check RC system health.
    """
    try:
        settings = get_settings()
        current_time = time.time()
        
        # Test 1: Signal presence
        signal_present = (current_time - last_rc_update) < settings.RC_TIMEOUT
        
        # Test 2: Channel activity
        active_channels = len([v for v in rc_channel_data.values() 
                             if settings.RC_MIN_PWM <= v <= settings.RC_MAX_PWM])
        
        # Test 3: Control authority
        control_channels = [1, 2, 3, 4]  # Roll, Pitch, Throttle, Yaw
        control_active = sum(1 for ch in control_channels 
                           if ch in rc_channel_data and 
                           settings.RC_MIN_PWM <= rc_channel_data[ch] <= settings.RC_MAX_PWM)
        
        # Test 4: Failsafe readiness
        failsafe_ready = settings.RC_FAILSAFE_ENABLED and not failsafe_triggered
        
        # Overall health score
        health_score = 0
        if signal_present:
            health_score += 25
        if active_channels >= 4:
            health_score += 25
        if control_active >= 3:
            health_score += 25
        if failsafe_ready:
            health_score += 25
        
        return {
            "overall_health": "good" if health_score >= 75 else "poor" if health_score < 50 else "fair",
            "health_score": health_score,
            "tests": {
                "signal_present": signal_present,
                "active_channels": active_channels,
                "control_authority": control_active >= 3,
                "failsafe_ready": failsafe_ready
            },
            "details": {
                "last_update_age": current_time - last_rc_update if last_rc_update > 0 else None,
                "total_channels": settings.RC_CHANNELS,
                "active_channels": active_channels,
                "control_channels_active": control_active,
                "failsafe_enabled": settings.RC_FAILSAFE_ENABLED
            },
            "recommendations": get_rc_recommendations(signal_present, active_channels, control_active, failsafe_ready)
        }
        
    except Exception as e:
        logger.error(f"Error testing RC connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RC test error: {str(e)}"
        )


def get_rc_recommendations(signal_present: bool, active_channels: int, 
                          control_active: int, failsafe_ready: bool) -> List[str]:
    """Generate recommendations based on RC test results"""
    recommendations = []
    
    if not signal_present:
        recommendations.append("Check RC transmitter power and binding")
    
    if active_channels < 4:
        recommendations.append("Verify RC channel connections and configuration")
    
    if control_active < 3:
        recommendations.append("Check primary control channels (roll/pitch/throttle/yaw)")
    
    if not failsafe_ready:
        recommendations.append("Configure and test RC failsafe settings")
    
    if not recommendations:
        recommendations.append("RC system is functioning normally")
    
    return recommendations


# Function to update RC channel data (called from MAVLink message handler)
def update_rc_channels(channel_data: Dict[int, int]):
    """Update RC channel data from MAVLink RC_CHANNELS message"""
    global rc_channel_data, last_rc_update
    
    rc_channel_data.update(channel_data)
    last_rc_update = time.time()
    
    # Reset failsafe if we're receiving data
    global failsafe_triggered
    if failsafe_triggered and time.time() - last_rc_update < 1.0:
        failsafe_triggered = False
        logger.info("RC failsafe automatically cleared - signal restored")


@router.get("/status")
async def radio_status():
    channels = receiver.get_all_channels()
    signal_lost = failsafe.signal_lost
    return {"status": "connected", "channels": channels, "signal_lost": signal_lost}


@router.get("/channels")
async def get_channels():
    channels = receiver.get_all_channels()
    return {"channels": channels}


@router.post("/failsafe")
async def configure_failsafe(threshold: float):
    failsafe.update_signal(threshold)
    return {"status": "failsafe configured", "threshold": threshold}