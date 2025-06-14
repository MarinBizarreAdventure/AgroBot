"""
BackendService for managing communication and coordination with the central AgroBot Backend Server.
"""

import asyncio
import logging
import platform
import psutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

from app.core.backend.client import BackendClient
from app.models.backend import (
    RegisterRequest, RegisterResponse,
    HeartbeatRequest, HeartbeatResponse,
    CommandResultRequest, CommandResultResponse,
    TelemetryBatchRequest, TelemetryDataPoint,
    AlertRequest, AlertResponse,
    HardwareInfo, Capability, Location, QuickHealth, BackendCommand
)
from config.settings import settings
from app.core.mavlink.connection import MAVLinkManager # Assuming this is the source of GPS and MAVLink status

logger = logging.getLogger(__name__)

class BackendService:
    def __init__(self, mavlink_manager: MAVLinkManager):
        self.backend_client = BackendClient(base_url=settings.BACKEND_URL, api_key=settings.BACKEND_API_KEY)
        self.mavlink_manager = mavlink_manager
        self.robot_id = settings.ROBOT_ID
        self.registered = False
        self.stop_event = asyncio.Event()
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.telemetry_task: Optional[asyncio.Task] = None
        self.command_polling_task: Optional[asyncio.Task] = None
        self.telemetry_buffer: List[TelemetryDataPoint] = []

    async def _get_hardware_info(self) -> HardwareInfo:
        # Placeholder implementation - ideally, this would gather real data
        cpu_info = platform.processor() or "Unknown CPU"
        ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        disk_gb = round(psutil.disk_usage('/').total / (1024**3), 2)
        # A more robust solution would query /proc/cpuinfo or specific commands for serial, camera, etc.
        return HardwareInfo(
            cpu_model=cpu_info,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            serial_number=None, # Replace with actual logic to get serial
            camera_present=False # Replace with actual logic to detect camera
        )

    async def _get_robot_capabilities(self) -> List[Capability]:
        # Placeholder: Define capabilities based on your robot's modules/functionality
        return [
            Capability(name="GPS", supported=True, details={"accuracy": "high"}),
            Capability(name="Arming", supported=True),
            Capability(name="Movement", supported=True, details={"modes": ["goto", "velocity"]}),
            Capability(name="MissionPlanning", supported=False), # Example of unsupported
            Capability(name="Telemetry", supported=True, details={"frequency": "configurable"})
        ]

    async def _get_current_location(self) -> Optional[Location]:
        gps_data = await self.mavlink_manager.get_gps_data()
        if gps_data and gps_data.fix_type > 0 and gps_data.latitude != 0 and gps_data.longitude != 0:
            return Location(
                latitude=gps_data.latitude,
                longitude=gps_data.longitude,
                altitude=gps_data.altitude,
                timestamp=datetime.now()
            )
        return None

    async def _get_quick_health(self) -> QuickHealth:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        mavlink_connected = self.mavlink_manager.is_connected()
        gps_data = await self.mavlink_manager.get_gps_data()
        gps_fix = gps_data.fix_type > 0 if gps_data else False
        return QuickHealth(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            mavlink_connected=mavlink_connected,
            gps_fix=gps_fix
        )

    async def register_robot_with_retry(self):
        attempt = 0
        max_attempts = settings.MAX_RECONNECT_ATTEMPTS # From .env
        base_delay = settings.RECONNECT_DELAY # From .env

        while not self.registered and not self.stop_event.is_set():
            attempt += 1
            delay = min(base_delay * (2 ** (attempt - 1)), 300) # Cap delay at 5 minutes
            logger.info(f"Attempting to register robot (Attempt {attempt}/{max_attempts})...")
            
            try:
                hardware_info = await self._get_hardware_info()
                capabilities = await self._get_robot_capabilities()
                current_location = await self._get_current_location()

                register_request = RegisterRequest(
                    robot_id=self.robot_id,
                    hardware_info=hardware_info,
                    capabilities=capabilities,
                    location=current_location,
                    software_version="1.0.0" # You might get this from __version__ or env var
                )
                response = await self.backend_client.register_robot(register_request)

                if response and response.success:
                    self.registered = True
                    logger.info(f"Robot {self.robot_id} successfully registered with backend.")
                    break
                else:
                    logger.warning(f"Registration failed: {response.message if response else 'No response from backend'}. Retrying in {delay}s...")
            except Exception as e:
                logger.error(f"Error during registration attempt {attempt}: {e}. Retrying in {delay}s...")
            
            if attempt >= max_attempts:
                logger.error(f"Max registration attempts ({max_attempts}) reached. Cannot connect to backend.")
                # Consider entering offline mode or alerting administrator here
                break
            
            await asyncio.sleep(delay)

    async def _heartbeat_loop(self):
        while not self.stop_event.is_set():
            if self.registered:
                try:
                    quick_health = await self._get_quick_health()
                    heartbeat_request = HeartbeatRequest(
                        robot_id=self.robot_id,
                        status="active",
                        timestamp=datetime.now(),
                        quick_health=quick_health
                    )
                    response = await self.backend_client.send_heartbeat(heartbeat_request)
                    if response and response.success:
                        logger.debug(f"Heartbeat sent. Backend commands pending: {response.commands_pending}")
                    else:
                        logger.warning(f"Heartbeat failed: {response.message if response else 'No response'}. Attempting to re-register.")
                        self.registered = False # Mark as not registered to trigger re-registration
                        # self.register_robot_with_retry() # This should be handled by the main lifespan or a separate watchdog task
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}. Attempting to re-register.")
                    self.registered = False
            
            await asyncio.sleep(settings.HEARTBEAT_INTERVAL)

    async def _telemetry_loop(self):
        while not self.stop_event.is_set():
            await asyncio.sleep(settings.TELEMETRY_INTERVAL)
            if self.registered and self.telemetry_buffer:
                batch_size = settings.TELEMETRY_BATCH_SIZE
                while self.telemetry_buffer:
                    batch = self.telemetry_buffer[:batch_size]
                    batch_request = TelemetryBatchRequest(
                        robot_id=self.robot_id,
                        data=batch
                    )
                    try:
                        response = await self.backend_client.send_telemetry_batch(batch_request)
                        if response and response.success:
                            logger.debug(f"Sent {response.records_received} telemetry records.")
                            self.telemetry_buffer = self.telemetry_buffer[response.records_received:]
                        else:
                            logger.warning(f"Failed to send telemetry batch: {response.message if response else 'No response'}. Data remains in buffer.")
                            break # Stop sending more batches if current one failed
                    except Exception as e:
                        logger.error(f"Error sending telemetry batch: {e}. Data remains in buffer.")
                        break
            elif not self.registered:
                logger.debug("Backend not registered, buffering telemetry.")

    async def _command_polling_loop(self):
        while not self.stop_event.is_set():
            if self.registered:
                try:
                    response = await self.backend_client.poll_pending_commands()
                    if response and response.success and response.commands:
                        logger.info(f"Received {len(response.commands)} pending commands.")
                        for command in response.commands:
                            logger.info(f"Processing command: {command.command_id} - {command.command_type}")
                            # Here you would integrate with a CommandExecutionService
                            # For now, just report success immediately
                            await self.report_command_result(
                                command_id=command.command_id,
                                status="completed",
                                result={"message": "Command processed by client placeholder"},
                                execution_time=0.1 # Placeholder
                            )
                    elif response and response.success:
                        logger.debug("No pending commands.")
                    else:
                        logger.warning(f"Failed to poll commands: {response.message if response else 'No response'}.")
                except Exception as e:
                    logger.error(f"Error polling commands: {e}.")
            
            await asyncio.sleep(settings.COMMAND_POLLING_INTERVAL) # Need to add this to settings

    async def report_command_result(self, command_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None, execution_time: Optional[float] = None):
        if not self.registered:
            logger.warning(f"Not registered with backend, cannot report command {command_id} result.")
            return
        request_data = CommandResultRequest(
            command_id=command_id,
            status=status,
            result=result,
            error=error,
            execution_time=execution_time
        )
        resp = await self.backend_client.report_command_result(request_data)
        if not resp or not resp.success:
            logger.error(f"Failed to report command {command_id} result: {resp.message if resp else 'No response'}")

    async def send_telemetry_data(self, gps_data: Optional[Dict[str, Any]] = None, attitude_data: Optional[Dict[str, Any]] = None, battery_data: Optional[Dict[str, Any]] = None, sensor_data: Optional[Dict[str, Any]] = None):
        telemetry_point = TelemetryDataPoint(
            timestamp=datetime.now(),
            gps=gps_data,
            attitude=attitude_data,
            battery=battery_data,
            sensors=sensor_data
        )
        self.telemetry_buffer.append(telemetry_point)
        logger.debug(f"Telemetry buffered. Buffer size: {len(self.telemetry_buffer)}")

    async def send_alert(self, severity: str, message: str, details: Optional[Dict[str, Any]] = None):
        if not self.registered:
            logger.warning(f"Not registered with backend, cannot send alert: {message}")
            return
        alert_request = AlertRequest(
            robot_id=self.robot_id,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
        resp = await self.backend_client.send_alert(alert_request)
        if not resp or not resp.success:
            logger.error(f"Failed to send alert: {message} - {resp.message if resp else 'No response'}")

    async def startup(self):
        logger.info("BackendService starting up...")
        # Start registration in background
        asyncio.create_task(self.register_robot_with_retry())
        # Start periodic tasks, they will check self.registered before acting
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.telemetry_task = asyncio.create_task(self._telemetry_loop())
        self.command_polling_task = asyncio.create_task(self._command_polling_loop())
        logger.info("BackendService startup complete.")

    async def shutdown(self):
        logger.info("BackendService shutting down...")
        self.stop_event.set() # Signal tasks to stop
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try: await self.heartbeat_task
            except asyncio.CancelledError: pass
        if self.telemetry_task:
            self.telemetry_task.cancel()
            try: await self.telemetry_task
            except asyncio.CancelledError: pass
        if self.command_polling_task:
            self.command_polling_task.cancel()
            try: await self.command_polling_task
            except asyncio.CancelledError: pass
        await self.backend_client.close()
        logger.info("BackendService shutdown complete.")

# Note: This BackendService requires MAVLinkManager to be initialized and passed in.
# For example, in main.py, you would do:
# from app.core.mavlink.connection import MAVLinkManager
# mavlink_manager = MAVLinkManager() # Or retrieve from dependency injection
# backend_service = BackendService(mavlink_manager)
# Then call backend_service.startup() in a FastAPI lifespan event.
