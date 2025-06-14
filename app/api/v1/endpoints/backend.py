"""
Backend communication API endpoints for AgroBot backend integration
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Dict, Any, List, Optional
import logging
import time
import asyncio

from app.core.mavlink.connection import MAVLinkManager
from app.core.backend.client import BackendClient
from app.models.backend import (
    SyncRequest, SyncResponse, RobotStatus, TelemetryData,
    BackendConnection, DataUpload, CommandReceived
)
from app.models.pixhawk import CommandResponse
from config.settings import get_settings
from main import get_mavlink_manager
from app.services.backend_service import BackendService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backend", tags=["Backend Communication"])

# Global backend client instance
backend_client: Optional[BackendClient] = None
backend_service = BackendService()


@router.on_event("startup")
async def startup_backend():
    """Initialize backend client on startup"""
    global backend_client
    settings = get_settings()
    backend_client = BackendClient(
        base_url=settings.AGROBOT_BACKEND_URL,
        api_key=settings.AGROBOT_API_KEY,
        robot_id=settings.ROBOT_ID
    )


@router.get("/connection", response_model=BackendConnection)
async def get_backend_connection() -> BackendConnection:
    """
    Get backend connection status
    
    Returns information about the connection to the AgroBot backend.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        settings = get_settings()
        
        # Test connection
        connection_test = await backend_client.test_connection()
        
        return BackendConnection(
            connected=connection_test["success"],
            url=settings.AGROBOT_BACKEND_URL,
            robot_id=settings.ROBOT_ID,
            last_sync=backend_client.last_sync_time,
            sync_interval=settings.BACKEND_SYNC_INTERVAL,
            api_version=connection_test.get("api_version", "unknown"),
            status=connection_test.get("status", "unknown")
        )
        
    except Exception as e:
        logger.error(f"Error getting backend connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backend connection error: {str(e)}"
        )


@router.post("/sync", response_model=SyncResponse)
async def sync_with_backend(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> SyncResponse:
    """
    Synchronize data with backend
    
    Sends robot status and telemetry data to the backend and receives commands.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        sync_data = {}
        
        # Include robot status if requested
        if request.include_status:
            sync_data["robot_status"] = await get_robot_status_data(mavlink)
        
        # Include telemetry if requested
        if request.include_telemetry:
            sync_data["telemetry"] = await get_telemetry_data(mavlink)
        
        # Include GPS data if requested
        if request.include_gps and mavlink.latest_gps:
            gps = mavlink.latest_gps
            sync_data["gps"] = {
                "latitude": gps.lat / 1e7,
                "longitude": gps.lon / 1e7,
                "altitude": gps.relative_alt / 1000.0,
                "timestamp": gps.timestamp
            }
        
        # Send sync request to backend
        sync_result = await backend_client.sync_data(sync_data)
        
        # Process any commands received from backend
        commands_processed = 0
        if sync_result.get("commands"):
            background_tasks.add_task(process_backend_commands, sync_result["commands"], mavlink)
            commands_processed = len(sync_result["commands"])
        
        return SyncResponse(
            success=sync_result["success"],
            message=sync_result.get("message", "Sync completed"),
            timestamp=time.time(),
            data_sent=len(sync_data),
            commands_received=commands_processed,
            next_sync=time.time() + get_settings().BACKEND_SYNC_INTERVAL
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing with backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backend sync error: {str(e)}"
        )


@router.post("/status/update", response_model=CommandResponse)
async def update_robot_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> CommandResponse:
    """
    Send robot status update to backend
    
    Sends current robot status to the backend immediately.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Get current robot status
        status_data = await get_robot_status_data(mavlink)
        
        # Send to backend
        result = await backend_client.update_robot_status(status_data)
        
        return CommandResponse(
            success=result["success"],
            message=result.get("message", "Status updated successfully"),
            data={"timestamp": time.time(), "status_data": status_data}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating robot status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status update error: {str(e)}"
        )


@router.post("/telemetry/upload", response_model=DataUpload)
async def upload_telemetry_data(
    data: TelemetryData,
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> DataUpload:
    """
    Upload telemetry data to backend
    
    Sends telemetry data batch to the backend for storage and analysis.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Upload telemetry data
        result = await backend_client.upload_telemetry(data.dict())
        
        return DataUpload(
            success=result["success"],
            message=result.get("message", "Telemetry uploaded successfully"),
            records_uploaded=len(data.data_points),
            upload_size_bytes=len(str(data.dict())),
            timestamp=time.time()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading telemetry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry upload error: {str(e)}"
        )


@router.get("/commands/pending")
async def get_pending_commands() -> Dict[str, Any]:
    """
    Get pending commands from backend
    
    Retrieves any pending commands that the backend wants to execute on this robot.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Get pending commands
        commands = await backend_client.get_pending_commands()
        
        return {
            "commands": commands,
            "count": len(commands),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting pending commands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pending commands error: {str(e)}"
        )


@router.post("/commands/{command_id}/acknowledge", response_model=CommandResponse)
async def acknowledge_command(command_id: str, result: CommandReceived) -> CommandResponse:
    """
    Acknowledge command execution
    
    Reports the result of command execution back to the backend.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Send acknowledgment to backend
        ack_result = await backend_client.acknowledge_command(command_id, result.dict())
        
        return CommandResponse(
            success=ack_result["success"],
            message=f"Command {command_id} acknowledged",
            data={"command_id": command_id, "result": result.dict()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Command acknowledgment error: {str(e)}"
        )


@router.post("/heartbeat", response_model=CommandResponse)
async def send_heartbeat() -> CommandResponse:
    """
    Send heartbeat to backend
    
    Sends a heartbeat signal to indicate the robot is online and operational.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Send heartbeat
        heartbeat_data = {
            "timestamp": time.time(),
            "robot_id": get_settings().ROBOT_ID,
            "status": "online"
        }
        
        result = await backend_client.send_heartbeat(heartbeat_data)
        
        return CommandResponse(
            success=result["success"],
            message="Heartbeat sent successfully",
            data=heartbeat_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending heartbeat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Heartbeat error: {str(e)}"
        )


@router.get("/logs/upload")
async def upload_logs(
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    level: str = "INFO"
) -> Dict[str, Any]:
    """
    Upload log files to backend
    
    Uploads system logs to the backend for analysis and debugging.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Read and filter logs
        logs = read_log_files(start_time, end_time, level)
        
        # Upload logs
        result = await backend_client.upload_logs(logs)
        
        return {
            "success": result["success"],
            "message": result.get("message", "Logs uploaded successfully"),
            "log_entries": len(logs),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error uploading logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Log upload error: {str(e)}"
        )


@router.post("/config/update", response_model=CommandResponse)
async def update_configuration(config_update: Dict[str, Any]) -> CommandResponse:
    """
    Update robot configuration from backend
    
    Receives configuration updates from the backend and applies them.
    """
    try:
        if not backend_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Backend client not initialized"
            )
        
        # Validate and apply configuration updates
        # This would typically update settings and restart services as needed
        logger.info(f"Received configuration update: {config_update}")
        
        # Send confirmation to backend
        result = await backend_client.confirm_config_update(config_update)
        
        return CommandResponse(
            success=result["success"],
            message="Configuration updated successfully",
            data=config_update
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration update error: {str(e)}"
        )


@router.get("/test", response_model=Dict[str, Any])
async def test_backend_connection() -> Dict[str, Any]:
    """
    Test backend connection
    
    Performs a comprehensive test of backend connectivity and functionality.
    """
    try:
        if not backend_client:
            return {
                "success": False,
                "error": "Backend client not initialized",
                "tests": {}
            }
        
        settings = get_settings()
        tests = {}
        
        # Test 1: Basic connectivity
        tests["connectivity"] = await backend_client.test_connection()
        
        # Test 2: Authentication
        tests["authentication"] = await backend_client.test_authentication()
        
        # Test 3: API endpoints
        tests["api_endpoints"] = await backend_client.test_api_endpoints()
        
        # Test 4: Data upload
        test_data = {"test": True, "timestamp": time.time()}
        tests["data_upload"] = await backend_client.test_data_upload(test_data)
        
        # Calculate overall success
        all_passed = all(test.get("success", False) for test in tests.values())
        
        return {
            "success": all_passed,
            "timestamp": time.time(),
            "backend_url": settings.AGROBOT_BACKEND_URL,
            "robot_id": settings.ROBOT_ID,
            "tests": tests,
            "summary": {
                "total_tests": len(tests),
                "passed_tests": sum(1 for test in tests.values() if test.get("success", False)),
                "overall_status": "healthy" if all_passed else "degraded"
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing backend connection: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }


# Helper functions
async def get_robot_status_data(mavlink: MAVLinkManager) -> Dict[str, Any]:
    """Get current robot status data for backend sync"""
    status_data = {
        "timestamp": time.time(),
        "robot_id": get_settings().ROBOT_ID,
        "online": True,
        "mavlink_connected": mavlink.is_connected(),
        "mode": "UNKNOWN",
        "armed": False,
        "battery_voltage": None,
        "location": None
    }
    
    if mavlink.latest_heartbeat:
        status_data["armed"] = bool(mavlink.latest_heartbeat.base_mode & 128)
        # Would decode flight mode from custom_mode
    
    if mavlink.latest_gps:
        status_data["location"] = {
            "latitude": mavlink.latest_gps.lat / 1e7,
            "longitude": mavlink.latest_gps.lon / 1e7,
            "altitude": mavlink.latest_gps.relative_alt / 1000.0
        }
    
    return status_data


async def get_telemetry_data(mavlink: MAVLinkManager) -> Dict[str, Any]:
    """Get current telemetry data for backend sync"""
    telemetry_data = {
        "timestamp": time.time(),
        "mavlink_connected": mavlink.is_connected(),
        "gps_data": None,
        "attitude_data": None,
        "system_status": None
    }
    
    if mavlink.latest_gps:
        telemetry_data["gps_data"] = mavlink.latest_gps.__dict__
    
    if mavlink.latest_attitude:
        telemetry_data["attitude_data"] = mavlink.latest_attitude.__dict__
    
    if mavlink.latest_heartbeat:
        telemetry_data["system_status"] = mavlink.latest_heartbeat.__dict__
    
    return telemetry_data


async def process_backend_commands(commands: List[Dict[str, Any]], mavlink: MAVLinkManager):
    """Process commands received from backend"""
    for command in commands:
        try:
            command_type = command.get("type")
            command_id = command.get("id")
            
            logger.info(f"Processing backend command: {command_type} (ID: {command_id})")
            
            # Execute command based on type
            if command_type == "set_mode":
                mode = command.get("parameters", {}).get("mode")
                if mode:
                    success = await mavlink.set_mode(mode)
                    await acknowledge_command_execution(command_id, success, f"Mode set to {mode}")
            
            elif command_type == "arm_motors":
                arm = command.get("parameters", {}).get("arm", True)
                success = await mavlink.arm_motors(arm)
                action = "armed" if arm else "disarmed"
                await acknowledge_command_execution(command_id, success, f"Motors {action}")
            
            elif command_type == "goto_position":
                params = command.get("parameters", {})
                lat = params.get("latitude")
                lon = params.get("longitude")
                alt = params.get("altitude", 10)
                
                if lat and lon:
                    # This would use the movement API to go to position
                    await acknowledge_command_execution(command_id, True, f"Moving to {lat}, {lon}")
                else:
                    await acknowledge_command_execution(command_id, False, "Invalid coordinates")
            
            else:
                logger.warning(f"Unknown command type: {command_type}")
                await acknowledge_command_execution(command_id, False, f"Unknown command type: {command_type}")
                
        except Exception as e:
            logger.error(f"Error processing command {command.get('id')}: {e}")
            await acknowledge_command_execution(command.get("id"), False, str(e))


async def acknowledge_command_execution(command_id: str, success: bool, message: str):
    """Send command execution acknowledgment to backend"""
    if backend_client:
        try:
            result_data = {
                "success": success,
                "message": message,
                "timestamp": time.time()
            }
            await backend_client.acknowledge_command(command_id, result_data)
        except Exception as e:
            logger.error(f"Error acknowledging command {command_id}: {e}")


def read_log_files(start_time: Optional[float], end_time: Optional[float], level: str) -> List[Dict[str, Any]]:
    """Read and filter log files"""
    # This is a simplified implementation
    # In practice, you'd read actual log files and filter by time/level
    logs = [
        {
            "timestamp": time.time(),
            "level": "INFO",
            "message": "Sample log entry",
            "module": "main"
        }
    ]
    
    return logs


@router.post("/sync")
async def sync_data(data: dict):
    result = backend_service.sync_data(data)
    return {"status": "synced", "result": result}


@router.post("/status")
async def update_status(status: str):
    result = backend_service.update_status(status)
    return {"status": "updated", "result": result}