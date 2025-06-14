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

from config.settings import get_settings
from config.logging import setup_logging
from app.api.v1.api import api_router
from app.core.mavlink.connection import MAVLinkManager, MavlinkConnection
from app.services.telemetry_service import TelemetryService
from app.websocket.manager import WebSocketManager

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
mavlink_manager = None
telemetry_service = None
websocket_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting AgroBot Raspberry Pi Application")
    
    # Initialize MAVLink connection
    global mavlink_manager, telemetry_service
    settings = get_settings()
    
    try:
        mavlink_manager = MAVLinkManager(
            connection_string=settings.MAVLINK_CONNECTION_STRING,
            baud_rate=settings.MAVLINK_BAUD_RATE
        )
        
        # Initialize telemetry service
        telemetry_service = TelemetryService(mavlink_manager, websocket_manager)
        
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
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AgroBot Raspberry Pi Application")
    try:
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
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
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
            return {"success": success, "armed": arm}
        except Exception as e:
            logger.error(f"Pixhawk arm error: {e}")
            return {"error": str(e)}

    @app.post("/api/v1/pixhawk/mode")
    async def pixhawk_mode(mode: str):
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                return {"error": "Not connected to Pixhawk"}
            success = await mavlink_manager.set_mode(mode)
            return {"success": success, "mode": mode}
        except Exception as e:
            logger.error(f"Pixhawk mode error: {e}")
            return {"error": str(e)}

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
        try:
            if not mavlink_manager or not mavlink_manager.is_connected():
                return {"error": "Not connected to Pixhawk"}
            # This is a placeholder for actual movement logic
            return {"success": True, "message": f"Moving to {latitude}, {longitude}, {altitude}"}
        except Exception as e:
            logger.error(f"Movement goto error: {e}")
            return {"error": str(e)}

    # Mission endpoint
    @app.post("/api/v1/mission/create")
    async def mission_create(name: str, description: str = "", waypoints: list = []):
        try:
            # This is a placeholder for actual mission creation logic
            return {"success": True, "message": f"Mission '{name}' created", "waypoints": waypoints}
        except Exception as e:
            logger.error(f"Mission create error: {e}")
            return {"error": str(e)}

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
            # This is a placeholder for actual system status logic
            return {"overall_health": "healthy", "details": {}}
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
        workers=1  # Single worker for better stability
    )