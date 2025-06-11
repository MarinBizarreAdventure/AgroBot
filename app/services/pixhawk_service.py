"""
Pixhawk control service for high-level flight operations
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

from app.core.mavlink.connection import MAVLinkManager
from app.utils.constants import FlightModes, MAVLinkCommands, SafetyLimits
from app.utils.exceptions import (
    SafetyViolationException, MAVLinkConnectionException,
    InvalidConfigurationException
)
from app.utils.helpers import calculate_distance
from config.settings import get_settings

logger = logging.getLogger(__name__)


class FlightState(Enum):
    """Flight state enumeration"""
    UNKNOWN = "unknown"
    DISARMED = "disarmed"
    ARMED = "armed"
    TAKING_OFF = "taking_off"
    AIRBORNE = "airborne"
    LANDING = "landing"
    EMERGENCY = "emergency"


@dataclass
class FlightStatus:
    """Flight status information"""
    state: FlightState
    mode: str
    armed: bool
    altitude: float
    ground_speed: float
    battery_voltage: Optional[float]
    gps_fix: bool
    last_update: float


class PixhawkService:
    """High-level Pixhawk control service"""
    
    def __init__(self, mavlink_manager: MAVLinkManager):
        self.mavlink = mavlink_manager
        self.settings = get_settings()
        
        # Service state
        self._running = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Flight state tracking
        self.current_state = FlightState.UNKNOWN
        self.flight_status = FlightStatus(
            state=FlightState.UNKNOWN,
            mode="UNKNOWN",
            armed=False,
            altitude=0.0,
            ground_speed=0.0,
            battery_voltage=None,
            gps_fix=False,
            last_update=0.0
        )
        
        # Safety monitoring
        self.safety_callbacks: List[Callable[[FlightStatus], None]] = []
        self.safety_violations: List[str] = []
        
        # Operation tracking
        self.home_position: Optional[Dict[str, float]] = None
        self.takeoff_altitude: float = 0.0
        self.last_command_time = 0.0
        
        # Statistics
        self.total_flight_time = 0.0
        self.total_distance = 0.0
        self.command_count = 0
        self.safety_events = 0
    
    async def start(self):
        """Start the Pixhawk service"""
        if self._running:
            logger.warning("Pixhawk service is already running")
            return
        
        if not self.mavlink.is_connected():
            raise MAVLinkConnectionException("MAVLink not connected")
        
        logger.info("Starting Pixhawk service")
        self._running = True
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Set initial home position
        await self._update_home_position()
        
        logger.info("Pixhawk service started")
    
    async def stop(self):
        """Stop the Pixhawk service"""
        if not self._running:
            return
        
        logger.info("Stopping Pixhawk service")
        self._running = False
        
        # Cancel monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Pixhawk service stopped")
    
    def is_running(self) -> bool:
        """Check if service is running"""
        return self._running
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        logger.info("Pixhawk monitoring loop started")
        
        while self._running:
            try:
                await self._update_flight_status()
                await self._check_safety_conditions()
                await asyncio.sleep(1.0)  # Update at 1Hz
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _update_flight_status(self):
        """Update current flight status"""
        try:
            current_time = time.time()
            
            # Get MAVLink data
            if self.mavlink.latest_heartbeat:
                hb = self.mavlink.latest_heartbeat
                self.flight_status.armed = bool(hb.base_mode & 128)
                self.flight_status.mode = self._decode_flight_mode(hb.custom_mode)
            
            if self.mavlink.latest_gps:
                gps = self.mavlink.latest_gps
                self.flight_status.altitude = gps.relative_alt / 1000.0
                self.flight_status.ground_speed = gps.vel / 100.0
                self.flight_status.gps_fix = gps.fix_type >= 3
            
            # Update flight state
            self._update_flight_state()
            
            self.flight_status.last_update = current_time
            
        except Exception as e:
            logger.error(f"Error updating flight status: {e}")
    
    def _update_flight_state(self):
        """Update flight state based on current conditions"""
        if not self.flight_status.armed:
            self.current_state = FlightState.DISARMED
        elif self.flight_status.altitude < 1.0:
            if self.flight_status.armed:
                self.current_state = FlightState.ARMED
        elif self.flight_status.ground_speed < 0.5 and self.flight_status.altitude > 1.0:
            self.current_state = FlightState.AIRBORNE
        else:
            self.current_state = FlightState.AIRBORNE
        
        self.flight_status.state = self.current_state
    
    def _decode_flight_mode(self, custom_mode: int) -> str:
        """Decode flight mode from custom mode value"""
        # ArduPilot mode mapping (simplified)
        mode_map = {
            0: "STABILIZE",
            1: "ACRO",
            2: "ALT_HOLD",
            3: "AUTO",
            4: "GUIDED",
            5: "LOITER",
            6: "RTL",
            7: "CIRCLE",
            9: "LAND"
        }
        return mode_map.get(custom_mode, f"MODE_{custom_mode}")
    
    async def _check_safety_conditions(self):
        """Check for safety violations"""
        violations = []
        
        try:
            # Check altitude limits
            if self.flight_status.altitude > SafetyLimits.MAX_ALTITUDE:
                violations.append(f"Altitude {self.flight_status.altitude}m exceeds limit {SafetyLimits.MAX_ALTITUDE}m")
            
            # Check speed limits
            if self.flight_status.ground_speed > SafetyLimits.MAX_SPEED:
                violations.append(f"Speed {self.flight_status.ground_speed}m/s exceeds limit {SafetyLimits.MAX_SPEED}m/s")
            
            # Check GPS accuracy
            if self.mavlink.latest_gps and self.flight_status.armed:
                if not self.flight_status.gps_fix:
                    violations.append("GPS fix lost during flight")
                elif self.mavlink.latest_gps.hdop > 2.0:
                    violations.append(f"GPS accuracy poor (HDOP: {self.mavlink.latest_gps.hdop})")
            
            # Check battery (if available)
            if self.flight_status.battery_voltage and self.flight_status.battery_voltage < SafetyLimits.MIN_BATTERY_VOLTAGE:
                violations.append(f"Battery voltage low: {self.flight_status.battery_voltage}V")
            
            # Check geofence (if enabled)
            if self.settings.GEOFENCE_ENABLED and self.home_position:
                await self._check_geofence_violation(violations)
            
            # Update violations list
            if violations != self.safety_violations:
                self.safety_violations = violations
                
                if violations:
                    self.safety_events += 1
                    logger.warning(f"Safety violations detected: {violations}")
                    
                    # Notify safety callbacks
                    for callback in self.safety_callbacks:
                        try:
                            callback(self.flight_status)
                        except Exception as e:
                            logger.error(f"Error in safety callback: {e}")
        
        except Exception as e:
            logger.error(f"Error checking safety conditions: {e}")
    
    async def _check_geofence_violation(self, violations: List[str]):
        """Check for geofence violations"""
        if not self.mavlink.latest_gps or not self.home_position:
            return
        
        current_lat = self.mavlink.latest_gps.lat / 1e7
        current_lon = self.mavlink.latest_gps.lon / 1e7
        
        distance = calculate_distance(
            current_lat, current_lon,
            self.home_position["latitude"], self.home_position["longitude"]
        )
        
        if distance > self.settings.GEOFENCE_RADIUS:
            violations.append(f"Outside geofence: {distance:.1f}m > {self.settings.GEOFENCE_RADIUS}m")
    
    async def _update_home_position(self):
        """Update home position from current GPS location"""
        if self.mavlink.latest_gps and self.mavlink.latest_gps.fix_type >= 3:
            self.home_position = {
                "latitude": self.mavlink.latest_gps.lat / 1e7,
                "longitude": self.mavlink.latest_gps.lon / 1e7,
                "altitude": self.mavlink.latest_gps.alt / 1000.0
            }
            logger.info(f"Home position set: {self.home_position}")
    
    # High-level flight operations
    async def arm_vehicle(self, force: bool = False) -> bool:
        """
        Arm the vehicle with safety checks
        
        Args:
            force: Skip some safety checks
            
        Returns:
            True if successfully armed
        """
        if self.flight_status.armed:
            logger.warning("Vehicle is already armed")
            return True
        
        # Pre-arm safety checks
        if not force:
            if not self.flight_status.gps_fix:
                raise SafetyViolationException("GPS fix required for arming")
            
            if self.mavlink.latest_gps and self.mavlink.latest_gps.satellites_visible < 6:
                raise SafetyViolationException("Insufficient GPS satellites for arming")
        
        logger.info("Arming vehicle")
        success = await self.mavlink.arm_motors(True)
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            
            # Wait for arm confirmation
            await asyncio.sleep(2.0)
            await self._update_flight_status()
            
            if self.flight_status.armed:
                logger.info("Vehicle armed successfully")
                return True
            else:
                logger.error("Vehicle failed to arm")
                return False
        
        return success
    
    async def disarm_vehicle(self, force: bool = False) -> bool:
        """
        Disarm the vehicle
        
        Args:
            force: Force disarm even in flight
            
        Returns:
            True if successfully disarmed
        """
        if not self.flight_status.armed:
            logger.warning("Vehicle is already disarmed")
            return True
        
        # Safety check - don't disarm in flight unless forced
        if not force and self.flight_status.altitude > 1.0:
            raise SafetyViolationException("Cannot disarm while airborne (use force=True to override)")
        
        logger.info("Disarming vehicle")
        success = await self.mavlink.arm_motors(False)
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info("Vehicle disarmed successfully")
        
        return success
    
    async def takeoff(self, altitude: float, force: bool = False) -> bool:
        """
        Perform takeoff to specified altitude
        
        Args:
            altitude: Target altitude in meters
            force: Skip some safety checks
            
        Returns:
            True if takeoff command sent successfully
        """
        # Validate altitude
        if altitude <= 0:
            raise InvalidConfigurationException("Takeoff altitude must be positive")
        
        if altitude > SafetyLimits.MAX_ALTITUDE and not force:
            raise SafetyViolationException(f"Takeoff altitude {altitude}m exceeds limit {SafetyLimits.MAX_ALTITUDE}m")
        
        # Pre-takeoff checks
        if not force:
            if not self.flight_status.gps_fix:
                raise SafetyViolationException("GPS fix required for takeoff")
            
            if not self.flight_status.armed:
                logger.info("Vehicle not armed, arming first")
                await self.arm_vehicle()
        
        # Switch to GUIDED mode
        await self.mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        logger.info(f"Taking off to {altitude}m")
        success = await self.mavlink.send_command_long(
            MAVLinkCommands.NAV_TAKEOFF,
            0,  # Minimum pitch
            0,  # Empty
            0,  # Empty
            0,  # Yaw angle
            0,  # Latitude (current)
            0,  # Longitude (current)
            altitude
        )
        
        if success:
            self.takeoff_altitude = altitude
            self.current_state = FlightState.TAKING_OFF
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info(f"Takeoff command sent - climbing to {altitude}m")
        
        return success
    
    async def land(self, latitude: Optional[float] = None, longitude: Optional[float] = None) -> bool:
        """
        Land at current position or specified coordinates
        
        Args:
            latitude: Landing latitude (current position if None)
            longitude: Landing longitude (current position if None)
            
        Returns:
            True if land command sent successfully
        """
        logger.info("Initiating landing")
        
        if latitude is not None and longitude is not None:
            # Land at specific coordinates
            lat_int = int(latitude * 1e7)
            lon_int = int(longitude * 1e7)
            
            success = await self.mavlink.send_command_long(
                MAVLinkCommands.NAV_LAND,
                0,  # Abort altitude
                0,  # Precision land mode
                0,  # Empty
                0,  # Desired yaw
                lat_int,
                lon_int,
                0  # Altitude (ground level)
            )
        else:
            # Land at current position
            success = await self.mavlink.set_mode("LAND")
        
        if success:
            self.current_state = FlightState.LANDING
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info("Landing command sent")
        
        return success
    
    async def return_to_launch(self) -> bool:
        """
        Return to launch position and land
        
        Returns:
            True if RTL command sent successfully
        """
        logger.info("Returning to launch")
        
        success = await self.mavlink.set_mode("RTL")
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info("RTL command sent")
        
        return success
    
    async def emergency_stop(self) -> bool:
        """
        Emergency stop - immediately disarm motors
        
        Returns:
            True if emergency stop executed
        """
        logger.warning("EMERGENCY STOP TRIGGERED")
        self.current_state = FlightState.EMERGENCY
        self.safety_events += 1
        
        success = await self.mavlink.arm_motors(False)
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            logger.warning("Emergency stop executed - motors disarmed")
        
        return success
    
    async def goto_position(self, latitude: float, longitude: float, altitude: float) -> bool:
        """
        Go to specific GPS coordinates
        
        Args:
            latitude: Target latitude
            longitude: Target longitude
            altitude: Target altitude
            
        Returns:
            True if goto command sent successfully
        """
        # Switch to GUIDED mode
        await self.mavlink.set_mode("GUIDED")
        await asyncio.sleep(0.5)
        
        # Send goto command
        lat_int = int(latitude * 1e7)
        lon_int = int(longitude * 1e7)
        alt_int = int(altitude * 1000)
        
        success = await self.mavlink.send_command_long(
            MAVLinkCommands.NAV_WAYPOINT,
            0,  # Hold time
            2.0,  # Acceptance radius
            0,  # Pass through
            0,  # Desired yaw
            lat_int,
            lon_int,
            alt_int
        )
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info(f"Goto command sent: {latitude}, {longitude}, {altitude}m")
        
        return success
    
    async def set_speed(self, speed: float) -> bool:
        """
        Set vehicle speed
        
        Args:
            speed: Speed in m/s
            
        Returns:
            True if speed command sent successfully
        """
        if speed > SafetyLimits.MAX_SPEED:
            raise SafetyViolationException(f"Speed {speed}m/s exceeds limit {SafetyLimits.MAX_SPEED}m/s")
        
        success = await self.mavlink.send_command_long(
            MAVLinkCommands.DO_CHANGE_SPEED,
            0,  # Speed type (0=Airspeed)
            speed,
            -1,  # Throttle (-1 = no change)
            0, 0, 0, 0
        )
        
        if success:
            self.command_count += 1
            self.last_command_time = time.time()
            logger.info(f"Speed set to {speed}m/s")
        
        return success
    
    # Service management
    def add_safety_callback(self, callback: Callable[[FlightStatus], None]):
        """Add safety violation callback"""
        self.safety_callbacks.append(callback)
    
    def remove_safety_callback(self, callback: Callable[[FlightStatus], None]):
        """Remove safety violation callback"""
        if callback in self.safety_callbacks:
            self.safety_callbacks.remove(callback)
    
    def get_flight_status(self) -> FlightStatus:
        """Get current flight status"""
        return self.flight_status
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "running": self._running,
            "current_state": self.current_state.value,
            "total_flight_time": self.total_flight_time,
            "total_distance": self.total_distance,
            "command_count": self.command_count,
            "safety_events": self.safety_events,
            "safety_violations": len(self.safety_violations),
            "last_command_time": self.last_command_time,
            "home_position": self.home_position
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform service health check"""
        return {
            "healthy": self._running and self.mavlink.is_connected(),
            "running": self._running,
            "mavlink_connected": self.mavlink.is_connected(),
            "flight_state": self.current_state.value,
            "safety_violations": len(self.safety_violations),
            "last_update_age": time.time() - self.flight_status.last_update
        }