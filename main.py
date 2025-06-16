#!/usr/bin/env python3
"""
AgroBot Raspberry Pi - FastAPI Application
Main entry point for the Raspberry Pi controller application
"""

import uvicorn
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import asyncio
from typing import Optional
import uuid
from datetime import datetime
import psutil

from config.settings import get_settings
from config.logging import setup_logging
from app.core.mavlink.connection import MAVLinkManager
from app.services.telemetry_service import TelemetryService
from app.websocket.manager import WebSocketManager
from app.services.backend_service import BackendService

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
mavlink_manager = None
telemetry_service = None
websocket_manager = WebSocketManager()
backend_service: Optional[BackendService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting AgroBot Raspberry Pi Application")
    
    # Initialize MAVLink connection
    global mavlink_manager, telemetry_service, backend_service
    settings = get_settings()
    
    try:
        mavlink_manager = MAVLinkManager(
            connection_string=settings.MAVLINK_CONNECTION_STRING,
            baud_rate=settings.MAVLINK_BAUD_RATE
        )
        
        # Initialize telemetry service
        telemetry_service = TelemetryService(mavlink_manager, websocket_manager)

        # Initialize backend service
        logger.info("Initializing BackendService...")
        backend_service = BackendService(mavlink_manager)
        logger.info("BackendService initialized.")
        
        # Start MAVLink connection
        if settings.AUTO_CONNECT_MAVLINK:
            try:
                await mavlink_manager.connect()
                logger.info("MAVLink connection established")
                
                # Start telemetry service
                await telemetry_service.start()
                logger.info("Telemetry service started")
            except Exception as e:
                logger.error(f"Failed to connect to Pixhawk: {e}")
        
        # Start backend service tasks (registration, heartbeat, etc.)
        logger.info("Calling BackendService startup...")
        await backend_service.startup()
        logger.info("Backend service startup call completed.")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AgroBot Raspberry Pi Application")
    try:
        if backend_service:
            await backend_service.shutdown()
        if telemetry_service:
            await telemetry_service.stop()
        if mavlink_manager:
            await mavlink_manager.disconnect()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    settings = get_settings()
    
    app = FastAPI(
        title="AgroBot API",
        description="API for controlling and monitoring the AgroBot system",
        version="1.0.0",
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc UI
        openapi_url="/openapi.json",  # OpenAPI schema
        lifespan=lifespan
    )
    
    # Configure CORS for local network access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
    
    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket_manager.connect(websocket)
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    # Handle incoming WebSocket messages if needed
                    await websocket_manager.send_personal_message(f"Echo: {data}", websocket)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    break
        finally:
            websocket_manager.disconnect(websocket)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Simple health check endpoint"""
        try:
            status = {
                "status": "healthy",
                "mavlink_connected": mavlink_manager.is_connected() if mavlink_manager else False,
                "telemetry_active": telemetry_service.is_running() if telemetry_service else False,
                "websocket_connections": len(websocket_manager.active_connections)
            }
            return status
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with application information"""
        return {
            "name": settings.APP_NAME,
            "version": settings.VERSION,
            "description": "FastAPI application for agro robot control",
            "docs": "/docs",
            "health": "/health"
        }
    
    # Pixhawk endpoints
    @app.get("/api/v1/pixhawk/status")
    async def pixhawk_status():
        try:
            if not mavlink_manager:
                return {"error": "MAVLink manager not initialized"}
            status_data = mavlink_manager.get_status()
            return status_data
        except Exception as e:
            logger.error(f"Pixhawk status error: {e}")
            return {"error": str(e)}

    @app.post("/api/v1/pixhawk/connect")
    async def pixhawk_connect():
        try:
            if not mavlink_manager:
                return {"error": "MAVLink manager not initialized"}
            if mavlink_manager.is_connected():
                return {"success": True, "message": "Already connected to Pixhawk"}
            success = await mavlink_manager.connect()
            return {"success": success, "message": "Connected to Pixhawk" if success else "Failed to connect"}
        except Exception as e:
            logger.error(f"Pixhawk connect error: {e}")
            return {"error": str(e)}

    @app.post("/api/v1/pixhawk/arm")
    async def pixhawk_arm(arm: bool = True):
        try:
            if not mavlink_manager:
                return {"error": "MAVLink manager not initialized"}
            if not mavlink_manager.is_connected():
                return {"error": "Not connected to Pixhawk"}
            
            success = await mavlink_manager.arm_motors(arm)
            
            # Report to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=str(uuid.uuid4()), # Generate a unique command ID
                    status="completed" if success else "failed",
                    result={"armed": arm} if success else None,
                    error="Failed to arm/disarm motors" if not success else None,
                    execution_time=None # You could measure this for more accuracy
                )
            
            return {"success": success, "armed": arm}
        except Exception as e:
            logger.error(f"Pixhawk arm error: {e}")
            
            # Report error to backend if service is available
            if backend_service:
                await backend_service.report_command_result(
                    command_id=str(uuid.uuid4()),
                    status="failed",
                    error=str(e),
                    execution_time=None
                )

            return {"error": str(e)}

    @app.post("/api/v1/pixhawk/mode")
    async def pixhawk_mode(mode: str):
        command_id = str(uuid.uuid4())
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                error_msg = "Not connected to Pixhawk"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            # Validate mode
            valid_modes = ["STABILIZE", "GUIDED", "AUTO", "RTL", "LOITER", "LAND"]
            if mode.upper() not in valid_modes:
                error_msg = f"Invalid mode. Must be one of: {', '.join(valid_modes)}"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            success = await mavlink_manager.set_mode(mode)
            
            # Report to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="completed" if success else "failed",
                    result={"mode": mode} if success else None,
                    error="Failed to set flight mode" if not success else None
                )

            return {
                "success": success,
                "command_id": command_id,
                "mode": mode
            }

        except Exception as e:
            logger.error(f"Pixhawk mode error: {e}")
            
            # Report error to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="failed",
                    error=str(e)
                )

            return {"error": str(e), "command_id": command_id}

    # GPS endpoints
    @app.get("/api/v1/gps/current")
    async def gps_current():
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                return {"error": "Not connected to Pixhawk"}
            gps = mavlink_manager.latest_gps
            if not gps:
                return {"error": "No GPS data available"}
            return {
                "latitude": gps.lat / 1e7,
                "longitude": gps.lon / 1e7,
                "altitude": gps.alt / 1000.0,
                "relative_altitude": gps.relative_alt / 1000.0,
                "ground_speed": gps.vel / 100.0,
                "heading": gps.cog / 100.0,
                "timestamp": gps.timestamp
            }
        except Exception as e:
            logger.error(f"GPS current error: {e}")
            return {"error": str(e)}

    @app.get("/api/v1/gps/status")
    async def gps_status():
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                return {"error": "Not connected to Pixhawk"}
            gps = mavlink_manager.latest_gps
            if not gps:
                return {"available": False}
            return {
                "available": True,
                "fix_type": gps.fix_type,
                "satellites_visible": gps.satellites_visible,
                "hdop": gps.hdop,
                "vdop": gps.vdop,
                "timestamp": gps.timestamp
            }
        except Exception as e:
            logger.error(f"GPS status error: {e}")
            return {"error": str(e)}

    # Movement endpoint
    @app.post("/api/v1/movement/goto")
    async def movement_goto(latitude: float, longitude: float, altitude: float):
        command_id = str(uuid.uuid4())
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                error_msg = "Not connected to Pixhawk"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            # Validate GPS fix
            gps_data = await mavlink_manager.get_gps_data()
            if not gps_data or gps_data.fix_type <= 0:
                error_msg = "No GPS fix available"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            # Validate coordinates
            settings = get_settings()
            if settings.GEOFENCE_ENABLED:
                # Calculate distance from current position to target
                current_lat = gps_data.lat / 1e7
                current_lon = gps_data.lon / 1e7
                # Simple distance calculation (you might want to use a more accurate method)
                distance = ((latitude - current_lat) ** 2 + (longitude - current_lon) ** 2) ** 0.5
                if distance > settings.GEOFENCE_RADIUS:
                    error_msg = f"Target location is outside geofence radius ({settings.GEOFENCE_RADIUS}m)"
                    if backend_service:
                        await backend_service.report_command_result(
                            command_id=command_id,
                            status="failed",
                            error=error_msg
                        )
                    return {"error": error_msg}

            # Execute movement command
            # This is where you would implement the actual movement logic
            # For now, we'll just simulate success
            success = True
            result = {
                "target": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "altitude": altitude
                },
                "current": {
                    "latitude": current_lat,
                    "longitude": current_lon,
                    "altitude": gps_data.alt / 1000.0
                }
            }

            # Report to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="completed" if success else "failed",
                    result=result if success else None,
                    error=None if success else "Failed to execute movement command"
                )

            return {
                "success": success,
                "command_id": command_id,
                "message": f"Moving to {latitude}, {longitude}, {altitude}",
                "result": result
            }

        except Exception as e:
            logger.error(f"Movement goto error: {e}")
            
            # Report error to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="failed",
                    error=str(e)
                )

            return {"error": str(e), "command_id": command_id}

    # Mission endpoint
    @app.post("/api/v1/mission/create")
    async def mission_create(name: str, description: str = "", waypoints: list = []):
        command_id = str(uuid.uuid4())
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                error_msg = "Not connected to Pixhawk"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            # Validate waypoints
            settings = get_settings()
            if len(waypoints) > settings.MAX_WAYPOINTS:
                error_msg = f"Too many waypoints. Maximum allowed: {settings.MAX_WAYPOINTS}"
                if backend_service:
                    await backend_service.report_command_result(
                        command_id=command_id,
                        status="failed",
                        error=error_msg
                    )
                return {"error": error_msg}

            # Validate each waypoint
            for i, wp in enumerate(waypoints):
                if not isinstance(wp, dict):
                    error_msg = f"Invalid waypoint format at index {i}"
                    if backend_service:
                        await backend_service.report_command_result(
                            command_id=command_id,
                            status="failed",
                            error=error_msg
                        )
                    return {"error": error_msg}
                
                required_fields = ["latitude", "longitude", "altitude"]
                missing_fields = [field for field in required_fields if field not in wp]
                if missing_fields:
                    error_msg = f"Missing required fields in waypoint {i}: {', '.join(missing_fields)}"
                    if backend_service:
                        await backend_service.report_command_result(
                            command_id=command_id,
                            status="failed",
                            error=error_msg
                        )
                    return {"error": error_msg}

                # Validate coordinates against geofence if enabled
                if settings.GEOFENCE_ENABLED:
                    # Get current position
                    gps_data = await mavlink_manager.get_gps_data()
                    if gps_data and gps_data.fix_type > 0:
                        current_lat = gps_data.lat / 1e7
                        current_lon = gps_data.lon / 1e7
                        # Calculate distance
                        distance = ((wp["latitude"] - current_lat) ** 2 + (wp["longitude"] - current_lon) ** 2) ** 0.5
                        if distance > settings.GEOFENCE_RADIUS:
                            error_msg = f"Waypoint {i} is outside geofence radius ({settings.GEOFENCE_RADIUS}m)"
                            if backend_service:
                                await backend_service.report_command_result(
                                    command_id=command_id,
                                    status="failed",
                                    error=error_msg
                                )
                            return {"error": error_msg}

            # Create mission (placeholder for actual implementation)
            success = True
            result = {
                "mission_name": name,
                "description": description,
                "waypoints": waypoints,
                "created_at": datetime.now().isoformat()
            }

            # Report to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="completed" if success else "failed",
                    result=result if success else None,
                    error="Failed to create mission" if not success else None
                )

            return {
                "success": success,
                "command_id": command_id,
                "message": f"Mission '{name}' created",
                "result": result
            }

        except Exception as e:
            logger.error(f"Mission create error: {e}")
            
            # Report error to backend
            if backend_service:
                await backend_service.report_command_result(
                    command_id=command_id,
                    status="failed",
                    error=str(e)
                )

            return {"error": str(e), "command_id": command_id}

    # Radio endpoint
    @app.get("/api/v1/radio/status")
    async def radio_status():
        try:
            # This is a placeholder for actual radio status logic
            return {"status": "connected", "channels": {"1": 1500, "2": 1500}, "signal_lost": False}
        except Exception as e:
            logger.error(f"Radio status error: {e}")
            return {"error": str(e)}

    # Status endpoint
    @app.get("/api/v1/status")
    async def system_status():
        try:
            # Get MAVLink status
            mavlink_status = {
                "connected": mavlink_manager.is_connected() if mavlink_manager else False,
                "armed": mavlink_manager.is_armed() if mavlink_manager else False,
                "mode": mavlink_manager.get_mode() if mavlink_manager else None
            }

            # Get GPS status
            gps_status = None
            if mavlink_manager and mavlink_manager.is_connected():
                gps_data = await mavlink_manager.get_gps_data()
                if gps_data:
                    gps_status = {
                        "fix_type": gps_data.fix_type,
                        "satellites_visible": gps_data.satellites_visible,
                        "hdop": gps_data.hdop,
                        "vdop": gps_data.vdop
                    }

            # Get system metrics
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }

            # Get backend status
            backend_status = {
                "registered": backend_service.registered if backend_service else False,
                "heartbeat_active": backend_service.heartbeat_task is not None if backend_service else False,
                "telemetry_active": backend_service.telemetry_task is not None if backend_service else False,
                "command_polling_active": backend_service.command_polling_task is not None if backend_service else False,
                "telemetry_buffer_size": len(backend_service.telemetry_buffer) if backend_service else 0
            }

            # Get WebSocket status
            websocket_status = {
                "active_connections": len(websocket_manager.active_connections),
                "telemetry_active": telemetry_service.is_running() if telemetry_service else False
            }

            # Determine overall health
            health_checks = [
                mavlink_status["connected"],
                backend_status["registered"],
                gps_status["fix_type"] > 0 if gps_status else False,
                system_metrics["cpu_percent"] < 90,
                system_metrics["memory_percent"] < 90,
                system_metrics["disk_percent"] < 90
            ]
            overall_health = "healthy" if all(health_checks) else "degraded" if any(health_checks) else "unhealthy"

            status = {
                "overall_health": overall_health,
                "timestamp": datetime.now().isoformat(),
                "mavlink": mavlink_status,
                "gps": gps_status,
                "system": system_metrics,
                "backend": backend_status,
                "websocket": websocket_status
            }

            return status

        except Exception as e:
            logger.error(f"System status error: {e}")
            return {"error": str(e)}

    # Backend endpoint
    @app.post("/api/v1/backend/sync")
    async def backend_sync():
        try:
            # This is a placeholder for actual backend sync logic
            return {"status": "synced", "result": {"success": True}}
        except Exception as e:
            logger.error(f"Backend sync error: {e}")
            return {"error": str(e)}
    
    return app


# Create the app instance
app = create_app()

# Dependency to get MAVLink manager
def get_mavlink_manager():
    global mavlink_manager
    if not mavlink_manager:
        raise RuntimeError("MAVLink manager not initialized")
    return mavlink_manager

# Dependency to get telemetry service
def get_telemetry_service():
    global telemetry_service
    if not telemetry_service:
        raise RuntimeError("Telemetry service not initialized")
    return telemetry_service

# Dependency to get WebSocket manager
def get_websocket_manager():
    return websocket_manager


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
        workers=1,  # Single worker for better stability
        access_log=True,  # Enable access logging
        proxy_headers=True,  # Enable proxy headers for local network access
        forwarded_allow_ips="*"  # Allow all forwarded IPs for local network access
    )