"""
Custom exception classes for AgroBot application
"""

from typing import Optional, Dict, Any
from app.utils.constants import ErrorCodes


class AgroBotException(Exception):
    """Base exception class for AgroBot application"""
    
    def __init__(self, message: str, error_code: Optional[int] = None, 
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code or ErrorCodes.INTERNAL_ERROR
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": True,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "exception_type": self.__class__.__name__
        }


# Connection Exceptions
class ConnectionException(AgroBotException):
    """Base class for connection-related exceptions"""
    pass


class MAVLinkConnectionException(ConnectionException):
    """MAVLink connection related exceptions"""
    
    def __init__(self, message: str, connection_string: Optional[str] = None, 
                 timeout: Optional[float] = None):
        details = {}
        if connection_string:
            details["connection_string"] = connection_string
        if timeout:
            details["timeout"] = timeout
        
        super().__init__(message, ErrorCodes.MAVLINK_CONNECTION_FAILED, details)


class BackendConnectionException(ConnectionException):
    """Backend connection related exceptions"""
    
    def __init__(self, message: str, url: Optional[str] = None, 
                 status_code: Optional[int] = None):
        details = {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code
        
        super().__init__(message, ErrorCodes.BACKEND_CONNECTION_FAILED, details)


class GPSConnectionException(ConnectionException):
    """GPS connection related exceptions"""
    
    def __init__(self, message: str, fix_type: Optional[int] = None, 
                 satellites: Optional[int] = None):
        details = {}
        if fix_type is not None:
            details["fix_type"] = fix_type
        if satellites is not None:
            details["satellites"] = satellites
        
        super().__init__(message, ErrorCodes.GPS_CONNECTION_FAILED, details)


class RadioConnectionException(ConnectionException):
    """Radio control connection related exceptions"""
    
    def __init__(self, message: str, channels: Optional[int] = None, 
                 signal_strength: Optional[float] = None):
        details = {}
        if channels is not None:
            details["channels"] = channels
        if signal_strength is not None:
            details["signal_strength"] = signal_strength
        
        super().__init__(message, ErrorCodes.RADIO_CONNECTION_FAILED, details)


# Configuration Exceptions
class ConfigurationException(AgroBotException):
    """Base class for configuration-related exceptions"""
    pass


class InvalidConfigurationException(ConfigurationException):
    """Invalid configuration exceptions"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, 
                 config_value: Optional[Any] = None):
        details = {}
        if config_key:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)
        
        super().__init__(message, ErrorCodes.INVALID_CONFIGURATION, details)


class MissingParameterException(ConfigurationException):
    """Missing required parameter exceptions"""
    
    def __init__(self, parameter_name: str, context: Optional[str] = None):
        message = f"Missing required parameter: {parameter_name}"
        if context:
            message += f" in {context}"
        
        details = {"parameter_name": parameter_name}
        if context:
            details["context"] = context
        
        super().__init__(message, ErrorCodes.MISSING_PARAMETER, details)


# Safety Exceptions
class SafetyException(AgroBotException):
    """Base class for safety-related exceptions"""
    pass


class SafetyViolationException(SafetyException):
    """General safety violation exceptions"""
    
    def __init__(self, message: str, violation_type: Optional[str] = None, 
                 current_value: Optional[float] = None, limit_value: Optional[float] = None):
        details = {}
        if violation_type:
            details["violation_type"] = violation_type
        if current_value is not None:
            details["current_value"] = current_value
        if limit_value is not None:
            details["limit_value"] = limit_value
        
        super().__init__(message, ErrorCodes.SAFETY_VIOLATION, details)


class GeofenceViolationException(SafetyException):
    """Geofence boundary violation exceptions"""
    
    def __init__(self, message: str, current_position: Optional[Dict[str, float]] = None,
                 fence_center: Optional[Dict[str, float]] = None, fence_radius: Optional[float] = None):
        details = {}
        if current_position:
            details["current_position"] = current_position
        if fence_center:
            details["fence_center"] = fence_center
        if fence_radius:
            details["fence_radius"] = fence_radius
        
        super().__init__(message, ErrorCodes.GEOFENCE_VIOLATION, details)


class AltitudeViolationException(SafetyException):
    """Altitude limit violation exceptions"""
    
    def __init__(self, current_altitude: float, max_altitude: float):
        message = f"Altitude violation: {current_altitude}m exceeds limit of {max_altitude}m"
        details = {
            "current_altitude": current_altitude,
            "max_altitude": max_altitude
        }
        super().__init__(message, ErrorCodes.ALTITUDE_VIOLATION, details)


class SpeedViolationException(SafetyException):
    """Speed limit violation exceptions"""
    
    def __init__(self, current_speed: float, max_speed: float):
        message = f"Speed violation: {current_speed}m/s exceeds limit of {max_speed}m/s"
        details = {
            "current_speed": current_speed,
            "max_speed": max_speed
        }
        super().__init__(message, ErrorCodes.SPEED_VIOLATION, details)


class LowBatteryException(SafetyException):
    """Low battery exceptions"""
    
    def __init__(self, current_voltage: float, min_voltage: float, 
                 battery_percentage: Optional[float] = None):
        message = f"Low battery: {current_voltage}V below minimum {min_voltage}V"
        details = {
            "current_voltage": current_voltage,
            "min_voltage": min_voltage
        }
        if battery_percentage is not None:
            details["battery_percentage"] = battery_percentage
        
        super().__init__(message, ErrorCodes.BATTERY_LOW, details)


class GPSAccuracyException(SafetyException):
    """GPS accuracy insufficient exceptions"""
    
    def __init__(self, current_hdop: float, max_hdop: float, satellites: Optional[int] = None):
        message = f"GPS accuracy insufficient: HDOP {current_hdop} exceeds limit {max_hdop}"
        details = {
            "current_hdop": current_hdop,
            "max_hdop": max_hdop
        }
        if satellites is not None:
            details["satellites"] = satellites
        
        super().__init__(message, ErrorCodes.GPS_ACCURACY_POOR, details)


# Mission Exceptions
class MissionException(AgroBotException):
    """Base class for mission-related exceptions"""
    pass


class InvalidMissionException(MissionException):
    """Invalid mission exceptions"""
    
    def __init__(self, message: str, mission_id: Optional[str] = None, 
                 validation_errors: Optional[list] = None):
        details = {}
        if mission_id:
            details["mission_id"] = mission_id
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        super().__init__(message, ErrorCodes.MISSION_INVALID, details)


class InvalidWaypointException(MissionException):
    """Invalid waypoint exceptions"""
    
    def __init__(self, message: str, waypoint_index: Optional[int] = None, 
                 waypoint_data: Optional[Dict[str, Any]] = None):
        details = {}
        if waypoint_index is not None:
            details["waypoint_index"] = waypoint_index
        if waypoint_data:
            details["waypoint_data"] = waypoint_data
        
        super().__init__(message, ErrorCodes.WAYPOINT_INVALID, details)


class MissionTimeoutException(MissionException):
    """Mission timeout exceptions"""
    
    def __init__(self, mission_id: str, elapsed_time: float, timeout_limit: float):
        message = f"Mission {mission_id} timed out after {elapsed_time}s (limit: {timeout_limit}s)"
        details = {
            "mission_id": mission_id,
            "elapsed_time": elapsed_time,
            "timeout_limit": timeout_limit
        }
        super().__init__(message, ErrorCodes.MISSION_TIMEOUT, details)


class MissionAbortedException(MissionException):
    """Mission aborted exceptions"""
    
    def __init__(self, mission_id: str, reason: str, abort_code: Optional[int] = None):
        message = f"Mission {mission_id} aborted: {reason}"
        details = {
            "mission_id": mission_id,
            "reason": reason
        }
        if abort_code:
            details["abort_code"] = abort_code
        
        super().__init__(message, ErrorCodes.MISSION_ABORTED, details)


# Hardware Exceptions
class HardwareException(AgroBotException):
    """Base class for hardware-related exceptions"""
    pass


class SensorFailureException(HardwareException):
    """Sensor failure exceptions"""
    
    def __init__(self, sensor_name: str, error_details: Optional[str] = None):
        message = f"Sensor failure: {sensor_name}"
        if error_details:
            message += f" - {error_details}"
        
        details = {"sensor_name": sensor_name}
        if error_details:
            details["error_details"] = error_details
        
        super().__init__(message, ErrorCodes.SENSOR_FAILURE, details)


class ActuatorFailureException(HardwareException):
    """Actuator failure exceptions"""
    
    def __init__(self, actuator_name: str, command: Optional[str] = None, 
                 expected_response: Optional[Any] = None, actual_response: Optional[Any] = None):
        message = f"Actuator failure: {actuator_name}"
        details = {"actuator_name": actuator_name}
        
        if command:
            details["command"] = command
        if expected_response is not None:
            details["expected_response"] = str(expected_response)
        if actual_response is not None:
            details["actual_response"] = str(actual_response)
        
        super().__init__(message, ErrorCodes.ACTUATOR_FAILURE, details)


class CommunicationFailureException(HardwareException):
    """Communication failure exceptions"""
    
    def __init__(self, interface: str, error_details: Optional[str] = None, 
                 retry_count: Optional[int] = None):
        message = f"Communication failure: {interface}"
        details = {"interface": interface}
        
        if error_details:
            details["error_details"] = error_details
        if retry_count is not None:
            details["retry_count"] = retry_count
        
        super().__init__(message, ErrorCodes.COMMUNICATION_FAILURE, details)


class PowerFailureException(HardwareException):
    """Power system failure exceptions"""
    
    def __init__(self, component: str, voltage: Optional[float] = None, 
                 current: Optional[float] = None):
        message = f"Power failure: {component}"
        details = {"component": component}
        
        if voltage is not None:
            details["voltage"] = voltage
        if current is not None:
            details["current"] = current
        
        super().__init__(message, ErrorCodes.POWER_FAILURE, details)


# Software Exceptions
class InternalErrorException(AgroBotException):
    """Internal software error exceptions"""
    
    def __init__(self, message: str, module: Optional[str] = None, 
                 function: Optional[str] = None, stack_trace: Optional[str] = None):
        details = {}
        if module:
            details["module"] = module
        if function:
            details["function"] = function
        if stack_trace:
            details["stack_trace"] = stack_trace
        
        super().__init__(message, ErrorCodes.INTERNAL_ERROR, details)


class MemoryErrorException(AgroBotException):
    """Memory-related error exceptions"""
    
    def __init__(self, message: str, memory_usage: Optional[float] = None, 
                 available_memory: Optional[float] = None):
        details = {}
        if memory_usage is not None:
            details["memory_usage"] = memory_usage
        if available_memory is not None:
            details["available_memory"] = available_memory
        
        super().__init__(message, ErrorCodes.MEMORY_ERROR, details)


class TimeoutErrorException(AgroBotException):
    """Timeout-related error exceptions"""
    
    def __init__(self, operation: str, timeout_duration: float, elapsed_time: Optional[float] = None):
        message = f"Operation timeout: {operation} exceeded {timeout_duration}s"
        details = {
            "operation": operation,
            "timeout_duration": timeout_duration
        }
        if elapsed_time is not None:
            details["elapsed_time"] = elapsed_time
        
        super().__init__(message, ErrorCodes.TIMEOUT_ERROR, details)


class PermissionErrorException(AgroBotException):
    """Permission-related error exceptions"""
    
    def __init__(self, resource: str, required_permission: str, current_user: Optional[str] = None):
        message = f"Permission denied: {required_permission} required for {resource}"
        details = {
            "resource": resource,
            "required_permission": required_permission
        }
        if current_user:
            details["current_user"] = current_user
        
        super().__init__(message, ErrorCodes.PERMISSION_ERROR, details)


# Exception Handler Utilities
def handle_exception(exception: Exception) -> Dict[str, Any]:
    """Convert any exception to a standardized dictionary format"""
    if isinstance(exception, AgroBotException):
        return exception.to_dict()
    else:
        return {
            "error": True,
            "message": str(exception),
            "error_code": ErrorCodes.INTERNAL_ERROR,
            "details": {"original_exception": exception.__class__.__name__},
            "exception_type": "UnhandledException"
        }


def create_safety_exception(violation_type: str, current_value: float, 
                          limit_value: float, message: Optional[str] = None) -> SafetyViolationException:
    """Factory function to create appropriate safety exceptions"""
    if not message:
        message = f"{violation_type} violation: {current_value} exceeds limit {limit_value}"
    
    if violation_type.lower() == "altitude":
        return AltitudeViolationException(current_value, limit_value)
    elif violation_type.lower() == "speed":
        return SpeedViolationException(current_value, limit_value)
    elif violation_type.lower() == "battery":
        return LowBatteryException(current_value, limit_value)
    else:
        return SafetyViolationException(message, violation_type, current_value, limit_value)


def create_connection_exception(connection_type: str, message: str, 
                              **kwargs) -> ConnectionException:
    """Factory function to create appropriate connection exceptions"""
    if connection_type.lower() == "mavlink":
        return MAVLinkConnectionException(message, **kwargs)
    elif connection_type.lower() == "backend":
        return BackendConnectionException(message, **kwargs)
    elif connection_type.lower() == "gps":
        return GPSConnectionException(message, **kwargs)
    elif connection_type.lower() == "radio":
        return RadioConnectionException(message, **kwargs)
    else:
        return ConnectionException(message, **kwargs)