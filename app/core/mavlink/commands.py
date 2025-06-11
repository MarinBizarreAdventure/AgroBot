"""
MAVLink command wrappers and high-level command interface
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass

from app.utils.constants import MAVLinkCommands, FlightModes
from app.utils.exceptions import MAVLinkConnectionException, SafetyViolationException

logger = logging.getLogger(__name__)


class CommandResult(Enum):
    """Command execution results"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"


@dataclass
class CommandResponse:
    """Command response data structure"""
    command_id: int
    result: CommandResult
    message: str
    execution_time: float
    data: Optional[Dict[str, Any]] = None


class MAVLinkCommandInterface:
    """High-level MAVLink command interface"""
    
    def __init__(self, mavlink_connection):
        self.connection = mavlink_connection
        self.command_timeout = 30.0
        self.retry_attempts = 3
        self.command_sequence = 0
        
        # Command tracking
        self.pending_commands: Dict[int, Dict[str, Any]] = {}
        self.command_history: List[CommandResponse] = []
        
        # Statistics
        self.commands_sent = 0
        self.commands_successful = 0
        self.commands_failed = 0
    
    async def send_command_long(self, command: int, param1: float = 0, param2: float = 0,
                               param3: float = 0, param4: float = 0, param5: float = 0,
                               param6: float = 0, param7: float = 0,
                               timeout: float = None) -> CommandResponse:
        """
        Send MAVLink COMMAND_LONG message with response tracking
        
        Args:
            command: MAVLink command ID
            param1-param7: Command parameters
            timeout: Command timeout in seconds
            
        Returns:
            CommandResponse with execution result
        """
        start_time = time.time()
        timeout = timeout or self.command_timeout
        self.command_sequence += 1
        
        try:
            # Send command
            success = await self.connection.send_command_long(
                command, param1, param2, param3, param4, param5, param6, param7
            )
            
            self.commands_sent += 1
            
            if success:
                self.commands_successful += 1
                execution_time = time.time() - start_time
                
                response = CommandResponse(
                    command_id=command,
                    result=CommandResult.SUCCESS,
                    message=f"Command {command} executed successfully",
                    execution_time=execution_time,
                    data={"parameters": [param1, param2, param3, param4, param5, param6, param7]}
                )
            else:
                self.commands_failed += 1
                execution_time = time.time() - start_time
                
                response = CommandResponse(
                    command_id=command,
                    result=CommandResult.FAILED,
                    message=f"Command {command} failed to send",
                    execution_time=execution_time
                )
            
            self.command_history.append(response)
            return response
            
        except Exception as e:
            self.commands_failed += 1
            execution_time = time.time() - start_time
            
            response = CommandResponse(
                command_id=command,
                result=CommandResult.FAILED,
                message=f"Command {command} error: {str(e)}",
                execution_time=execution_time
            )
            
            self.command_history.append(response)
            return response
    
    async def arm_disarm(self, arm: bool, force: bool = False) -> CommandResponse:
        """
        Arm or disarm motors
        
        Args:
            arm: True to arm, False to disarm
            force: Force arm/disarm even with pre-arm checks
            
        Returns:
            CommandResponse with result
        """
        param1 = 1.0 if arm else 0.0
        param2 = 21196.0 if force else 0.0  # Force parameter
        
        return await self.send_command_long(
            MAVLinkCommands.COMPONENT_ARM_DISARM,
            param1, param2
        )
    
    async def set_mode(self, mode: str) -> CommandResponse:
        """
        Set flight mode
        
        Args:
            mode: Flight mode name (MANUAL, GUIDED, AUTO, etc.)
            
        Returns:
            CommandResponse with result
        """
        mode_mapping = {
            'MANUAL': FlightModes.STABILIZE,
            'STABILIZE': FlightModes.STABILIZE,
            'GUIDED': FlightModes.GUIDED,
            'AUTO': FlightModes.AUTO,
            'RTL': FlightModes.RTL,
            'LOITER': FlightModes.LOITER,
            'LAND': FlightModes.LAND
        }
        
        if mode.upper() not in mode_mapping:
            return CommandResponse(
                command_id=MAVLinkCommands.DO_SET_MODE,
                result=CommandResult.FAILED,
                message=f"Unknown flight mode: {mode}",
                execution_time=0.0
            )
        
        mode_id = mode_mapping[mode.upper()]
        
        return await self.send_command_long(
            MAVLinkCommands.DO_SET_MODE,
            1,  # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            mode_id
        )
    
    async def takeoff(self, altitude: float, latitude: float = 0, longitude: float = 0) -> CommandResponse:
        """
        Command takeoff to specified altitude
        
        Args:
            altitude: Target altitude in meters
            latitude: Takeoff latitude (0 for current position)
            longitude: Takeoff longitude (0 for current position)
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.NAV_TAKEOFF,
            0,  # Minimum pitch
            0,  # Empty
            0,  # Empty
            0,  # Yaw angle
            latitude,
            longitude,
            altitude
        )
    
    async def land(self, latitude: float = 0, longitude: float = 0, altitude: float = 0) -> CommandResponse:
        """
        Command land at specified location
        
        Args:
            latitude: Landing latitude (0 for current position)
            longitude: Landing longitude (0 for current position)
            altitude: Landing altitude (0 for ground level)
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.NAV_LAND,
            0,  # Abort altitude
            0,  # Precision land mode
            0,  # Empty
            0,  # Desired yaw angle
            latitude,
            longitude,
            altitude
        )
    
    async def return_to_launch(self) -> CommandResponse:
        """
        Command return to launch position
        
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(MAVLinkCommands.NAV_RETURN_TO_LAUNCH)
    
    async def goto_position(self, latitude: float, longitude: float, altitude: float,
                           hold_time: float = 0, acceptance_radius: float = 2.0) -> CommandResponse:
        """
        Command vehicle to go to specific position
        
        Args:
            latitude: Target latitude
            longitude: Target longitude
            altitude: Target altitude
            hold_time: Hold time at waypoint in seconds
            acceptance_radius: Acceptance radius in meters
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.NAV_WAYPOINT,
            hold_time,
            acceptance_radius,
            0,  # Pass through
            0,  # Desired yaw
            latitude,
            longitude,
            altitude
        )
    
    async def change_speed(self, speed: float, speed_type: int = 0) -> CommandResponse:
        """
        Change vehicle speed
        
        Args:
            speed: Target speed in m/s
            speed_type: 0=Ground Speed, 1=Climb Speed
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.DO_CHANGE_SPEED,
            speed_type,
            speed,
            -1,  # Throttle (-1 = no change)
            0, 0, 0, 0
        )
    
    async def set_home_position(self, latitude: float = 0, longitude: float = 0,
                               altitude: float = 0) -> CommandResponse:
        """
        Set home position
        
        Args:
            latitude: Home latitude (0 for current position)
            longitude: Home longitude (0 for current position)
            altitude: Home altitude (0 for current altitude)
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.DO_SET_HOME,
            1,  # Use current position
            0, 0, 0,
            latitude,
            longitude,
            altitude
        )
    
    async def set_servo(self, servo_number: int, pwm_value: int) -> CommandResponse:
        """
        Set servo output
        
        Args:
            servo_number: Servo number (1-8)
            pwm_value: PWM value (typically 1000-2000)
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.DO_SET_SERVO,
            servo_number,
            pwm_value,
            0, 0, 0, 0, 0
        )
    
    async def set_relay(self, relay_number: int, state: bool) -> CommandResponse:
        """
        Set relay state
        
        Args:
            relay_number: Relay number (0-3)
            state: True for on, False for off
            
        Returns:
            CommandResponse with result
        """
        return await self.send_command_long(
            MAVLinkCommands.DO_SET_RELAY,
            relay_number,
            1 if state else 0,
            0, 0, 0, 0, 0
        )
    
    async def mission_start(self) -> CommandResponse:
        """
        Start mission execution
        
        Returns:
            CommandResponse with result
        """
        return await self.set_mode("AUTO")
    
    async def mission_pause(self) -> CommandResponse:
        """
        Pause mission execution
        
        Returns:
            CommandResponse with result
        """
        return await self.set_mode("LOITER")
    
    async def emergency_stop(self) -> CommandResponse:
        """
        Emergency stop - immediately disarm motors
        
        Returns:
            CommandResponse with result
        """
        return await self.arm_disarm(False, force=True)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get command interface statistics"""
        success_rate = 0.0
        if self.commands_sent > 0:
            success_rate = (self.commands_successful / self.commands_sent) * 100
        
        return {
            "commands_sent": self.commands_sent,
            "commands_successful": self.commands_successful,
            "commands_failed": self.commands_failed,
            "success_rate": success_rate,
            "command_sequence": self.command_sequence,
            "pending_commands": len(self.pending_commands),
            "history_length": len(self.command_history)
        }
    
    def get_command_history(self, limit: int = 50) -> List[CommandResponse]:
        """Get recent command history"""
        return self.command_history[-limit:]
    
    def clear_history(self):
        """Clear command history"""
        self.command_history.clear()


# High-level mission commands
class MissionCommands:
    """High-level mission command interface"""
    
    def __init__(self, command_interface: MAVLinkCommandInterface):
        self.cmd = command_interface
    
    async def upload_waypoint_mission(self, waypoints: List[Dict[str, Any]]) -> CommandResponse:
        """
        Upload waypoint mission to flight controller
        
        Args:
            waypoints: List of waypoint dictionaries
            
        Returns:
            CommandResponse with result
        """
        # This is a simplified implementation
        # In a full implementation, you would use the mission protocol
        
        if not waypoints:
            return CommandResponse(
                command_id=0,
                result=CommandResult.FAILED,
                message="No waypoints provided",
                execution_time=0.0
            )
        
        start_time = time.time()
        
        try:
            # Switch to GUIDED mode first
            mode_result = await self.cmd.set_mode("GUIDED")
            if mode_result.result != CommandResult.SUCCESS:
                return mode_result
            
            # Send each waypoint as a goto command (simplified)
            # In practice, you'd use proper mission upload protocol
            success_count = 0
            
            for i, waypoint in enumerate(waypoints):
                result = await self.cmd.goto_position(
                    waypoint['latitude'],
                    waypoint['longitude'],
                    waypoint['altitude'],
                    waypoint.get('hold_time', 0),
                    waypoint.get('acceptance_radius', 2.0)
                )
                
                if result.result == CommandResult.SUCCESS:
                    success_count += 1
                else:
                    break
            
            execution_time = time.time() - start_time
            
            if success_count == len(waypoints):
                return CommandResponse(
                    command_id=MAVLinkCommands.NAV_WAYPOINT,
                    result=CommandResult.SUCCESS,
                    message=f"Mission uploaded: {len(waypoints)} waypoints",
                    execution_time=execution_time,
                    data={"waypoints": len(waypoints), "uploaded": success_count}
                )
            else:
                return CommandResponse(
                    command_id=MAVLinkCommands.NAV_WAYPOINT,
                    result=CommandResult.FAILED,
                    message=f"Mission upload failed: {success_count}/{len(waypoints)} waypoints",
                    execution_time=execution_time,
                    data={"waypoints": len(waypoints), "uploaded": success_count}
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return CommandResponse(
                command_id=MAVLinkCommands.NAV_WAYPOINT,
                result=CommandResult.FAILED,
                message=f"Mission upload error: {str(e)}",
                execution_time=execution_time
            )
    
    async def execute_square_pattern(self, center_lat: float, center_lon: float,
                                   side_length: float, altitude: float) -> CommandResponse:
        """
        Execute square flight pattern
        
        Args:
            center_lat: Pattern center latitude
            center_lon: Pattern center longitude
            side_length: Square side length in meters
            altitude: Flight altitude
            
        Returns:
            CommandResponse with result
        """
        from app.utils.helpers import calculate_destination_point
        
        # Generate square waypoints
        half_side = side_length / 2
        waypoints = []
        
        # Calculate corner positions
        corners = [
            (0, half_side),    # North
            (90, half_side),   # East
            (180, half_side),  # South
            (270, half_side)   # West
        ]
        
        for i, (bearing, distance) in enumerate(corners):
            lat, lon = calculate_destination_point(center_lat, center_lon, bearing, distance)
            waypoints.append({
                'latitude': lat,
                'longitude': lon,
                'altitude': altitude,
                'hold_time': 0,
                'acceptance_radius': 2.0
            })
        
        return await self.upload_waypoint_mission(waypoints)


# Safety command wrappers
class SafetyCommands:
    """Safety-focused command wrappers"""
    
    def __init__(self, command_interface: MAVLinkCommandInterface):
        self.cmd = command_interface
        self.safety_checks_enabled = True
    
    async def safe_arm(self, gps_required: bool = True, min_satellites: int = 6) -> CommandResponse:
        """
        Safely arm motors with pre-arm checks
        
        Args:
            gps_required: Require GPS fix before arming
            min_satellites: Minimum satellites required
            
        Returns:
            CommandResponse with result
        """
        if self.safety_checks_enabled:
            # Perform safety checks
            if gps_required:
                # Check GPS status
                if not self.cmd.connection.latest_gps:
                    return CommandResponse(
                        command_id=MAVLinkCommands.COMPONENT_ARM_DISARM,
                        result=CommandResult.FAILED,
                        message="No GPS data available",
                        execution_time=0.0
                    )
                
                gps = self.cmd.connection.latest_gps
                if gps.fix_type < 3:
                    return CommandResponse(
                        command_id=MAVLinkCommands.COMPONENT_ARM_DISARM,
                        result=CommandResult.FAILED,
                        message=f"GPS fix insufficient (type={gps.fix_type})",
                        execution_time=0.0
                    )
                
                if gps.satellites_visible < min_satellites:
                    return CommandResponse(
                        command_id=MAVLinkCommands.COMPONENT_ARM_DISARM,
                        result=CommandResult.FAILED,
                        message=f"Insufficient satellites ({gps.satellites_visible}<{min_satellites})",
                        execution_time=0.0
                    )
        
        return await self.cmd.arm_disarm(True)
    
    async def emergency_land(self) -> CommandResponse:
        """
        Emergency landing procedure
        
        Returns:
            CommandResponse with result
        """
        # Switch to LAND mode immediately
        return await self.cmd.set_mode("LAND")
    
    async def safe_takeoff(self, altitude: float, max_altitude: float = 120.0) -> CommandResponse:
        """
        Safe takeoff with altitude validation
        
        Args:
            altitude: Target altitude
            max_altitude: Maximum allowed altitude
            
        Returns:
            CommandResponse with result
        """
        if altitude > max_altitude:
            return CommandResponse(
                command_id=MAVLinkCommands.NAV_TAKEOFF,
                result=CommandResult.FAILED,
                message=f"Altitude {altitude}m exceeds maximum {max_altitude}m",
                execution_time=0.0
            )
        
        if altitude <= 0:
            return CommandResponse(
                command_id=MAVLinkCommands.NAV_TAKEOFF,
                result=CommandResult.FAILED,
                message="Takeoff altitude must be positive",
                execution_time=0.0
            )
        
        return await self.cmd.takeoff(altitude)
    
    def enable_safety_checks(self, enabled: bool = True):
        """Enable or disable safety checks"""
        self.safety_checks_enabled = enabled
        logger.info(f"Safety checks {'enabled' if enabled else 'disabled'}")