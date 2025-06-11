"""
Data validation utilities for AgroBot application
"""

import re
import math
from typing import Dict, Any, List, Optional, Union, Tuple
from ipaddress import ip_address, AddressValueError

from app.utils.constants import SafetyLimits, GPSFixTypes
from app.utils.exceptions import (
    InvalidConfigurationException, SafetyViolationException,
    GeofenceViolationException, InvalidWaypointException
)


class ValidationResult:
    """Validation result container"""
    
    def __init__(self, valid: bool, message: str = "", details: Optional[Dict[str, Any]] = None):
        self.valid = valid
        self.message = message
        self.details = details or {}
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __str__(self) -> str:
        return self.message


# Coordinate Validation
def validate_coordinates(latitude: float, longitude: float) -> ValidationResult:
    """
    Validate GPS coordinates
    
    Args:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
    
    Returns:
        ValidationResult indicating if coordinates are valid
    """
    if not isinstance(latitude, (int, float)):
        return ValidationResult(False, "Latitude must be a number")
    
    if not isinstance(longitude, (int, float)):
        return ValidationResult(False, "Longitude must be a number")
    
    if not (-90 <= latitude <= 90):
        return ValidationResult(
            False, 
            f"Latitude {latitude} out of range (-90 to 90)",
            {"latitude": latitude, "valid_range": (-90, 90)}
        )
    
    if not (-180 <= longitude <= 180):
        return ValidationResult(
            False,
            f"Longitude {longitude} out of range (-180 to 180)",
            {"longitude": longitude, "valid_range": (-180, 180)}
        )
    
    return ValidationResult(True, "Coordinates are valid")


def validate_altitude(altitude: float, max_altitude: float = SafetyLimits.MAX_ALTITUDE) -> ValidationResult:
    """
    Validate altitude value
    
    Args:
        altitude: Altitude in meters
        max_altitude: Maximum allowed altitude
    
    Returns:
        ValidationResult indicating if altitude is valid
    """
    if not isinstance(altitude, (int, float)):
        return ValidationResult(False, "Altitude must be a number")
    
    if altitude < 0:
        return ValidationResult(
            False,
            f"Altitude {altitude}m cannot be negative",
            {"altitude": altitude}
        )
    
    if altitude > max_altitude:
        return ValidationResult(
            False,
            f"Altitude {altitude}m exceeds maximum {max_altitude}m",
            {"altitude": altitude, "max_altitude": max_altitude}
        )
    
    return ValidationResult(True, "Altitude is valid")


def validate_speed(speed: float, max_speed: float = SafetyLimits.MAX_SPEED) -> ValidationResult:
    """
    Validate speed value
    
    Args:
        speed: Speed in m/s
        max_speed: Maximum allowed speed
    
    Returns:
        ValidationResult indicating if speed is valid
    """
    if not isinstance(speed, (int, float)):
        return ValidationResult(False, "Speed must be a number")
    
    if speed < 0:
        return ValidationResult(
            False,
            f"Speed {speed}m/s cannot be negative",
            {"speed": speed}
        )
    
    if speed > max_speed:
        return ValidationResult(
            False,
            f"Speed {speed}m/s exceeds maximum {max_speed}m/s",
            {"speed": speed, "max_speed": max_speed}
        )
    
    return ValidationResult(True, "Speed is valid")


def validate_heading(heading: float) -> ValidationResult:
    """
    Validate heading value
    
    Args:
        heading: Heading in degrees (0-360)
    
    Returns:
        ValidationResult indicating if heading is valid
    """
    if not isinstance(heading, (int, float)):
        return ValidationResult(False, "Heading must be a number")
    
    if not (0 <= heading < 360):
        return ValidationResult(
            False,
            f"Heading {heading}° out of range (0-360)",
            {"heading": heading, "valid_range": (0, 360)}
        )
    
    return ValidationResult(True, "Heading is valid")


# Mission Validation
def validate_waypoint(waypoint: Dict[str, Any]) -> ValidationResult:
    """
    Validate waypoint data
    
    Args:
        waypoint: Waypoint dictionary with lat, lon, alt, etc.
    
    Returns:
        ValidationResult indicating if waypoint is valid
    """
    required_fields = ['latitude', 'longitude', 'altitude']
    
    # Check required fields
    for field in required_fields:
        if field not in waypoint:
            return ValidationResult(
                False,
                f"Missing required field: {field}",
                {"missing_field": field}
            )
    
    # Validate coordinates
    coord_result = validate_coordinates(waypoint['latitude'], waypoint['longitude'])
    if not coord_result:
        return coord_result
    
    # Validate altitude
    alt_result = validate_altitude(waypoint['altitude'])
    if not alt_result:
        return alt_result
    
    # Validate optional fields
    if 'hold_time' in waypoint and waypoint['hold_time'] < 0:
        return ValidationResult(
            False,
            "Hold time cannot be negative",
            {"hold_time": waypoint['hold_time']}
        )
    
    if 'acceptance_radius' in waypoint and waypoint['acceptance_radius'] <= 0:
        return ValidationResult(
            False,
            "Acceptance radius must be positive",
            {"acceptance_radius": waypoint['acceptance_radius']}
        )
    
    return ValidationResult(True, "Waypoint is valid")


def validate_mission(mission_data: Dict[str, Any]) -> ValidationResult:
    """
    Validate complete mission data
    
    Args:
        mission_data: Mission dictionary with waypoints, etc.
    
    Returns:
        ValidationResult indicating if mission is valid
    """
    # Check required fields
    if 'waypoints' not in mission_data:
        return ValidationResult(False, "Mission must have waypoints")
    
    waypoints = mission_data['waypoints']
    
    if not isinstance(waypoints, list):
        return ValidationResult(False, "Waypoints must be a list")
    
    if len(waypoints) == 0:
        return ValidationResult(False, "Mission must have at least one waypoint")
    
    if len(waypoints) > 100:  # Safety limit
        return ValidationResult(
            False,
            f"Too many waypoints ({len(waypoints)}), maximum is 100",
            {"waypoint_count": len(waypoints)}
        )
    
    # Validate each waypoint
    for i, waypoint in enumerate(waypoints):
        wp_result = validate_waypoint(waypoint)
        if not wp_result:
            return ValidationResult(
                False,
                f"Waypoint {i} invalid: {wp_result.message}",
                {"waypoint_index": i, "waypoint_error": wp_result.message}
            )
    
    # Check mission constraints
    total_distance = calculate_mission_distance(waypoints)
    if total_distance > 10000:  # 10km limit
        return ValidationResult(
            False,
            f"Mission too long ({total_distance:.1f}m), maximum is 10000m",
            {"total_distance": total_distance}
        )
    
    return ValidationResult(True, "Mission is valid")


def calculate_mission_distance(waypoints: List[Dict[str, Any]]) -> float:
    """Calculate total mission distance"""
    from app.utils.helpers import calculate_distance
    
    total_distance = 0.0
    
    for i in range(1, len(waypoints)):
        prev_wp = waypoints[i-1]
        curr_wp = waypoints[i]
        
        distance = calculate_distance(
            prev_wp['latitude'], prev_wp['longitude'],
            curr_wp['latitude'], curr_wp['longitude']
        )
        total_distance += distance
    
    return total_distance


# Geofence Validation
def validate_geofence_position(latitude: float, longitude: float, 
                              fence_center: Tuple[float, float], 
                              fence_radius: float) -> ValidationResult:
    """
    Validate position against geofence
    
    Args:
        latitude, longitude: Position to check
        fence_center: Geofence center (lat, lon)
        fence_radius: Geofence radius in meters
    
    Returns:
        ValidationResult indicating if position is within geofence
    """
    from app.utils.helpers import calculate_distance
    
    coord_result = validate_coordinates(latitude, longitude)
    if not coord_result:
        return coord_result
    
    distance = calculate_distance(
        latitude, longitude,
        fence_center[0], fence_center[1]
    )
    
    if distance > fence_radius:
        return ValidationResult(
            False,
            f"Position outside geofence ({distance:.1f}m > {fence_radius}m)",
            {
                "distance": distance,
                "fence_radius": fence_radius,
                "position": {"latitude": latitude, "longitude": longitude},
                "fence_center": {"latitude": fence_center[0], "longitude": fence_center[1]}
            }
        )
    
    return ValidationResult(True, "Position within geofence")


# Pattern Validation
def validate_square_pattern(center_lat: float, center_lon: float, side_length: float) -> ValidationResult:
    """
    Validate square pattern parameters
    
    Args:
        center_lat, center_lon: Pattern center coordinates
        side_length: Square side length in meters
    
    Returns:
        ValidationResult indicating if pattern is valid
    """
    coord_result = validate_coordinates(center_lat, center_lon)
    if not coord_result:
        return coord_result
    
    if side_length <= 0:
        return ValidationResult(
            False,
            "Side length must be positive",
            {"side_length": side_length}
        )
    
    if side_length > 1000:  # 1km limit
        return ValidationResult(
            False,
            f"Side length {side_length}m too large (max 1000m)",
            {"side_length": side_length}
        )
    
    return ValidationResult(True, "Square pattern is valid")


def validate_circle_pattern(center_lat: float, center_lon: float, radius: float) -> ValidationResult:
    """
    Validate circle pattern parameters
    
    Args:
        center_lat, center_lon: Pattern center coordinates
        radius: Circle radius in meters
    
    Returns:
        ValidationResult indicating if pattern is valid
    """
    coord_result = validate_coordinates(center_lat, center_lon)
    if not coord_result:
        return coord_result
    
    if radius <= 0:
        return ValidationResult(
            False,
            "Radius must be positive",
            {"radius": radius}
        )
    
    if radius > 500:  # 500m limit
        return ValidationResult(
            False,
            f"Radius {radius}m too large (max 500m)",
            {"radius": radius}
        )
    
    return ValidationResult(True, "Circle pattern is valid")


# GPS Data Validation
def validate_gps_data(gps_data: Dict[str, Any]) -> ValidationResult:
    """
    Validate GPS data quality
    
    Args:
        gps_data: GPS data dictionary
    
    Returns:
        ValidationResult indicating if GPS data is sufficient
    """
    required_fields = ['fix_type', 'satellites_visible', 'hdop']
    
    for field in required_fields:
        if field not in gps_data:
            return ValidationResult(
                False,
                f"Missing GPS field: {field}",
                {"missing_field": field}
            )
    
    # Check fix type
    fix_type = gps_data['fix_type']
    if fix_type < GPSFixTypes.FIX_3D:
        return ValidationResult(
            False,
            f"GPS fix insufficient (fix_type={fix_type}, need ≥{GPSFixTypes.FIX_3D})",
            {"fix_type": fix_type, "required_fix_type": GPSFixTypes.FIX_3D}
        )
    
    # Check satellite count
    satellites = gps_data['satellites_visible']
    if satellites < 6:
        return ValidationResult(
            False,
            f"Insufficient GPS satellites ({satellites}, need ≥6)",
            {"satellites": satellites, "required_satellites": 6}
        )
    
    # Check HDOP
    hdop = gps_data['hdop']
    if hdop > 2.0:
        return ValidationResult(
            False,
            f"GPS accuracy poor (HDOP={hdop}, need ≤2.0)",
            {"hdop": hdop, "max_hdop": 2.0}
        )
    
    return ValidationResult(True, "GPS data is sufficient")


# Network Validation
def validate_ip_address(ip_str: str) -> ValidationResult:
    """
    Validate IP address
    
    Args:
        ip_str: IP address string
    
    Returns:
        ValidationResult indicating if IP is valid
    """
    try:
        ip_address(ip_str)
        return ValidationResult(True, "IP address is valid")
    except AddressValueError as e:
        return ValidationResult(
            False,
            f"Invalid IP address: {str(e)}",
            {"ip_address": ip_str}
        )


def validate_port(port: Union[int, str]) -> ValidationResult:
    """
    Validate network port number
    
    Args:
        port: Port number
    
    Returns:
        ValidationResult indicating if port is valid
    """
    try:
        port_int = int(port)
    except (ValueError, TypeError):
        return ValidationResult(
            False,
            "Port must be a number",
            {"port": port}
        )
    
    if not (1 <= port_int <= 65535):
        return ValidationResult(
            False,
            f"Port {port_int} out of range (1-65535)",
            {"port": port_int}
        )
    
    return ValidationResult(True, "Port is valid")


def validate_url(url: str) -> ValidationResult:
    """
    Validate URL format
    
    Args:
        url: URL string
    
    Returns:
        ValidationResult indicating if URL is valid
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return ValidationResult(
            False,
            "Invalid URL format",
            {"url": url}
        )
    
    return ValidationResult(True, "URL is valid")


# Configuration Validation
def validate_mavlink_connection_string(connection_string: str) -> ValidationResult:
    """
    Validate MAVLink connection string
    
    Args:
        connection_string: MAVLink connection string
    
    Returns:
        ValidationResult indicating if connection string is valid
    """
    if not connection_string:
        return ValidationResult(False, "Connection string cannot be empty")
    
    # Check for common patterns
    valid_patterns = [
        r'^/dev/tty[A-Z0-9]+$',  # Serial device
        r'^tcp:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+$',  # TCP
        r'^udp:[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+$',  # UDP
        r'^serial:[^:]+:[0-9]+$',  # Serial with baud
    ]
    
    for pattern in valid_patterns:
        if re.match(pattern, connection_string):
            return ValidationResult(True, "Connection string is valid")
    
    # Also accept localhost variants
    if 'localhost' in connection_string or '127.0.0.1' in connection_string:
        return ValidationResult(True, "Connection string is valid")
    
    return ValidationResult(
        False,
        "Invalid MAVLink connection string format",
        {"connection_string": connection_string, "valid_formats": [
            "/dev/ttyUSB0", "tcp:192.168.1.100:5760", "udp:127.0.0.1:14550"
        ]}
    )


def validate_baud_rate(baud_rate: int) -> ValidationResult:
    """
    Validate serial baud rate
    
    Args:
        baud_rate: Baud rate value
    
    Returns:
        ValidationResult indicating if baud rate is valid
    """
    valid_baud_rates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
    
    if baud_rate not in valid_baud_rates:
        return ValidationResult(
            False,
            f"Invalid baud rate {baud_rate}",
            {"baud_rate": baud_rate, "valid_baud_rates": valid_baud_rates}
        )
    
    return ValidationResult(True, "Baud rate is valid")


# Hardware Validation
def validate_pwm_value(pwm_value: int, min_pwm: int = 1000, max_pwm: int = 2000) -> ValidationResult:
    """
    Validate PWM value for RC channels
    
    Args:
        pwm_value: PWM value in microseconds
        min_pwm: Minimum PWM value
        max_pwm: Maximum PWM value
    
    Returns:
        ValidationResult indicating if PWM value is valid
    """
    if not isinstance(pwm_value, int):
        return ValidationResult(False, "PWM value must be an integer")
    
    if not (min_pwm <= pwm_value <= max_pwm):
        return ValidationResult(
            False,
            f"PWM value {pwm_value} out of range ({min_pwm}-{max_pwm})",
            {"pwm_value": pwm_value, "valid_range": (min_pwm, max_pwm)}
        )
    
    return ValidationResult(True, "PWM value is valid")


def validate_gpio_pin(pin_number: int) -> ValidationResult:
    """
    Validate GPIO pin number for Raspberry Pi
    
    Args:
        pin_number: GPIO pin number
    
    Returns:
        ValidationResult indicating if pin is valid
    """
    # Raspberry Pi GPIO pins (BCM numbering)
    valid_pins = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
    
    if pin_number not in valid_pins:
        return ValidationResult(
            False,
            f"Invalid GPIO pin {pin_number}",
            {"pin_number": pin_number, "valid_pins": valid_pins}
        )
    
    return ValidationResult(True, "GPIO pin is valid")


# Safety Validation Functions
def validate_safety_limits(data: Dict[str, float]) -> ValidationResult:
    """
    Validate multiple safety parameters at once
    
    Args:
        data: Dictionary with safety parameters
    
    Returns:
        ValidationResult indicating if all safety limits are within bounds
    """
    violations = []
    
    # Check altitude
    if 'altitude' in data:
        alt_result = validate_altitude(data['altitude'])
        if not alt_result:
            violations.append(alt_result.message)
    
    # Check speed
    if 'speed' in data:
        speed_result = validate_speed(data['speed'])
        if not speed_result:
            violations.append(speed_result.message)
    
    # Check battery
    if 'battery_voltage' in data:
        if data['battery_voltage'] < SafetyLimits.MIN_BATTERY_VOLTAGE:
            violations.append(f"Battery voltage {data['battery_voltage']}V below minimum {SafetyLimits.MIN_BATTERY_VOLTAGE}V")
    
    # Check temperature
    if 'temperature' in data:
        if data['temperature'] > SafetyLimits.MAX_TEMPERATURE:
            violations.append(f"Temperature {data['temperature']}°C exceeds maximum {SafetyLimits.MAX_TEMPERATURE}°C")
    
    if violations:
        return ValidationResult(
            False,
            f"Safety violations: {'; '.join(violations)}",
            {"violations": violations}
        )
    
    return ValidationResult(True, "All safety limits within bounds")


# Bulk Validation Functions
def validate_mission_batch(missions: List[Dict[str, Any]]) -> List[ValidationResult]:
    """Validate multiple missions"""
    return [validate_mission(mission) for mission in missions]


def validate_waypoint_batch(waypoints: List[Dict[str, Any]]) -> List[ValidationResult]:
    """Validate multiple waypoints"""
    return [validate_waypoint(waypoint) for waypoint in waypoints]


def get_validation_summary(results: List[ValidationResult]) -> Dict[str, Any]:
    """Get summary of validation results"""
    total = len(results)
    valid = sum(1 for result in results if result.valid)
    invalid = total - valid
    
    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "success_rate": (valid / total * 100) if total > 0 else 0,
        "errors": [result.message for result in results if not result.valid]
    }