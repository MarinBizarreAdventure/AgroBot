from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging
from app.core.mavlink.connection import MavlinkConnection
from app.core.radio.receiver import Receiver
from app.core.mission.waypoints import WaypointManager
from app.services.mission_service import MissionService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize components
mavlink = MavlinkConnection()
receiver = Receiver()
mission_service = MissionService()

@router.get("/system")
async def test_system() -> Dict[str, Any]:
    """Test all system components and return their status"""
    try:
        # Test MAVLink connection
        mavlink_status = mavlink.is_connected()
        
        # Test RC receiver
        rc_status = receiver.is_connected()
        channels = receiver.get_all_channels()
        
        # Test mission service
        mission_status = mission_service.get_current_mission()
        
        return {
            "status": "success",
            "components": {
                "mavlink": {
                    "connected": mavlink_status,
                    "port": mavlink.port,
                    "baud_rate": mavlink.baud_rate
                },
                "radio": {
                    "connected": rc_status,
                    "channels": channels,
                    "signal_lost": receiver.is_signal_lost()
                },
                "mission": {
                    "active": bool(mission_status),
                    "waypoints": len(mission_status.waypoints) if mission_status else 0
                }
            }
        }
    except Exception as e:
        logger.error(f"System test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mavlink")
async def test_mavlink() -> Dict[str, Any]:
    """Test MAVLink connection and communication"""
    try:
        # Test connection
        connected = mavlink.connect()
        if not connected:
            raise HTTPException(status_code=500, detail="Failed to connect to Pixhawk")
        
        # Get telemetry
        telemetry = mavlink.read_telemetry()
        
        return {
            "status": "success",
            "connected": True,
            "telemetry": telemetry
        }
    except Exception as e:
        logger.error(f"MAVLink test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/radio")
async def test_radio() -> Dict[str, Any]:
    """Test radio control connection and channels"""
    try:
        # Test receiver
        channels = receiver.get_all_channels()
        signal_lost = receiver.is_signal_lost()
        
        return {
            "status": "success",
            "channels": channels,
            "signal_lost": signal_lost,
            "channel_mapping": receiver.get_channel_mapping()
        }
    except Exception as e:
        logger.error(f"Radio test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mission")
async def test_mission() -> Dict[str, Any]:
    """Test mission planning and execution"""
    try:
        # Create test mission
        test_waypoints = [
            {"latitude": 45.123456, "longitude": -122.123456, "altitude": 10.0},
            {"latitude": 45.123789, "longitude": -122.123789, "altitude": 10.0}
        ]
        
        mission = mission_service.create_mission(
            name="Test Mission",
            waypoints=test_waypoints
        )
        
        return {
            "status": "success",
            "mission": {
                "id": mission.id,
                "name": mission.name,
                "waypoints": len(mission.waypoints),
                "total_distance": mission.total_distance,
                "estimated_time": mission.estimated_time
            }
        }
    except Exception as e:
        logger.error(f"Mission test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate")
async def simulate_radio_commands() -> Dict[str, Any]:
    """Simulate radio commands for testing without actual radio"""
    try:
        # Simulate channel values
        simulated_channels = {
            "1": 1500,  # Roll
            "2": 1500,  # Pitch
            "3": 1000,  # Throttle
            "4": 1500,  # Yaw
            "5": 1500,  # Mode
            "6": 1500   # Aux1
        }
        
        # Update receiver with simulated values
        receiver.update_channels(simulated_channels)
        
        return {
            "status": "success",
            "simulated_channels": simulated_channels,
            "message": "Radio commands simulated successfully"
        }
    except Exception as e:
        logger.error(f"Simulation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    try:
        return {
            "status": "success",
            "system": {
                "mavlink": {
                    "connected": mavlink.is_connected(),
                    "telemetry": mavlink.read_telemetry() if mavlink.is_connected() else None
                },
                "radio": {
                    "connected": receiver.is_connected(),
                    "channels": receiver.get_all_channels(),
                    "signal_lost": receiver.is_signal_lost()
                },
                "mission": {
                    "current": mission_service.get_current_mission(),
                    "executing": mission_service.is_executing()
                }
            }
        }
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 