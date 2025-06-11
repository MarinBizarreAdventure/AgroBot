"""
General helper functions and utilities
"""

import math
import time
import json
import hashlib
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone
from pathlib import Path
import re

from app.utils.constants import Units, EarthConstants

logger = logging.getLogger(__name__)


# Mathematical Utilities
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula
    
    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)
    
    Returns:
        Distance in meters
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) * math.sin(delta_lon / 2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EarthConstants.RADIUS_METERS * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing from point 1 to point 2
    
    Args:
        lat1, lon1: Start point coordinates (degrees)
        lat2, lon2: End point coordinates (degrees)
    
    Returns:
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360  # Normalize to 0-360
    
    return bearing


def calculate_destination_point(lat: float, lon: float, bearing: float, distance: float) -> Tuple[float, float]:
    """
    Calculate destination point given start point, bearing, and distance
    
    Args:
        lat, lon: Start point coordinates (degrees)
        bearing: Bearing in degrees
        distance: Distance in meters
    
    Returns:
        Tuple of (latitude, longitude) in degrees
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)
    
    # Angular distance
    angular_distance = distance / EarthConstants.RADIUS_METERS
    
    # Calculate destination
    dest_lat = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance) +
        math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    
    dest_lon = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(dest_lat)
    )
    
    return math.degrees(dest_lat), math.degrees(dest_lon)


def calculate_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """
    Calculate midpoint between two GPS coordinates
    
    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)
    
    Returns:
        Tuple of (latitude, longitude) in degrees
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    bx = math.cos(lat2_rad) * math.cos(delta_lon)
    by = math.cos(lat2_rad) * math.sin(delta_lon)
    
    lat3 = math.atan2(
        math.sin(lat1_rad) + math.sin(lat2_rad),
        math.sqrt((math.cos(lat1_rad) + bx) * (math.cos(lat1_rad) + bx) + by * by)
    )
    
    lon3 = math.radians(lon1) + math.atan2(by, math.cos(lat1_rad) + bx)
    
    return math.degrees(lat3), math.degrees(lon3)


def point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm
    
    Args:
        lat, lon: Point coordinates (degrees)
        polygon: List of (lat, lon) tuples defining polygon vertices
    
    Returns:
        True if point is inside polygon
    """
    x, y = lon, lat
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


# Unit Conversion Utilities
def degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians"""
    return degrees * Units.DEGREES_TO_RADIANS


def radians_to_degrees(radians: float) -> float:
    """Convert radians to degrees"""
    return radians * Units.RADIANS_TO_DEGREES


def knots_to_ms(knots: float) -> float:
    """Convert knots to meters per second"""
    return knots * Units.KNOTS_TO_MS


def ms_to_knots(ms: float) -> float:
    """Convert meters per second to knots"""
    return ms / Units.KNOTS_TO_MS


def feet_to_meters(feet: float) -> float:
    """Convert feet to meters"""
    return feet * Units.FEET_TO_METERS


def meters_to_feet(meters: float) -> float:
    """Convert meters to feet"""
    return meters * Units.METERS_TO_FEET


# Time Utilities
def get_current_timestamp() -> float:
    """Get current timestamp in seconds"""
    return time.time()


def get_current_utc_timestamp() -> float:
    """Get current UTC timestamp"""
    return datetime.now(timezone.utc).timestamp()


def timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert timestamp to datetime object"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> float:
    """Convert datetime to timestamp"""
    return dt.timestamp()


def format_timestamp(timestamp: float, format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """Format timestamp as string"""
    dt = timestamp_to_datetime(timestamp)
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> float:
    """Parse timestamp string to float"""
    dt = datetime.strptime(timestamp_str, format_str)
    return dt.timestamp()


def time_ago(timestamp: float) -> str:
    """Get human-readable time ago string"""
    now = time.time()
    diff = now - timestamp
    
    if diff < 60:
        return f"{int(diff)} seconds ago"
    elif diff < 3600:
        return f"{int(diff / 60)} minutes ago"
    elif diff < 86400:
        return f"{int(diff / 3600)} hours ago"
    else:
        return f"{int(diff / 86400)} days ago"


# Data Utilities
def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dictionary with dot notation support"""
    keys = key.split('.')
    current = data
    
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    
    return current


def safe_set(data: Dict[str, Any], key: str, value: Any) -> None:
    """Safely set value in dictionary with dot notation support"""
    keys = key.split('.')
    current = data
    
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    current[keys[-1]] = value


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(data: Dict[str, Any], prefix: str = '', separator: str = '.') -> Dict[str, Any]:
    """Flatten nested dictionary"""
    result = {}
    
    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key
        
        if isinstance(value, dict):
            result.update(flatten_dict(value, new_key, separator))
        else:
            result[new_key] = value
    
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def remove_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from dictionary"""
    return {k: v for k, v in data.items() if v is not None}


# String Utilities
def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system use"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    filename = filename[:255]
    return filename


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase"""
    components = name.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length with optional suffix"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def is_valid_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate unique ID string"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    if prefix:
        return f"{prefix}_{random_part}"
    else:
        return random_part


# File Utilities
def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if it doesn't"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes"""
    return Path(file_path).stat().st_size


def get_file_hash(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
    """Calculate file hash"""
    hash_func = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def read_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Read JSON file with error handling"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"JSON file not found: {file_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        return {}


def write_json_file(file_path: Union[str, Path], data: Dict[str, Any], indent: int = 2) -> bool:
    """Write data to JSON file with error handling"""
    try:
        ensure_directory(Path(file_path).parent)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=indent, default=str)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {e}")
        return False


# Async Utilities
async def retry_async(func, max_retries: int = 3, delay: float = 1.0, 
                     backoff_factor: float = 2.0, exceptions: Tuple = (Exception,)):
    """Retry async function with exponential backoff"""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = delay * (backoff_factor ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_exception


async def timeout_async(func, timeout_seconds: float):
    """Run async function with timeout"""
    return await asyncio.wait_for(func(), timeout=timeout_seconds)


def run_with_timeout(func, timeout_seconds: float):
    """Run function with timeout (for sync functions)"""
    return asyncio.run(timeout_async(func, timeout_seconds))


# Validation Utilities
def is_valid_coordinate(lat: float, lon: float) -> bool:
    """Validate GPS coordinates"""
    return -90 <= lat <= 90 and -180 <= lon <= 180


def is_valid_altitude(altitude: float, max_altitude: float = 500) -> bool:
    """Validate altitude value"""
    return 0 <= altitude <= max_altitude


def is_valid_speed(speed: float, max_speed: float = 50) -> bool:
    """Validate speed value"""
    return 0 <= speed <= max_speed


def is_valid_heading(heading: float) -> bool:
    """Validate heading value"""
    return 0 <= heading < 360


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp value between min and max"""
    return max(min_value, min(value, max_value))


def normalize_angle(angle: float) -> float:
    """Normalize angle to 0-360 degrees"""
    return angle % 360


def normalize_angle_180(angle: float) -> float:
    """Normalize angle to -180 to 180 degrees"""
    angle = angle % 360
    return angle if angle <= 180 else angle - 360


# Performance Utilities
def measure_time(func):
    """Decorator to measure function execution time"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper


async def measure_time_async(func):
    """Decorator to measure async function execution time"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper


def get_memory_usage() -> Dict[str, float]:
    """Get current memory usage statistics"""
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
        "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
        "percent": process.memory_percent()
    }


# Logging Utilities
def setup_function_logger(func_name: str) -> logging.Logger:
    """Set up logger for specific function"""
    return logging.getLogger(f"{__name__}.{func_name}")


def log_function_call(func):
    """Decorator to log function calls"""
    def wrapper(*args, **kwargs):
        func_logger = setup_function_logger(func.__name__)
        func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            func_logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            func_logger.error(f"{func.__name__} failed with error: {e}")
            raise
    return wrapper


# Configuration Utilities
def load_environment_config(prefix: str = "AGROBOT_") -> Dict[str, str]:
    """Load configuration from environment variables with prefix"""
    import os
    config = {}
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config_key = key[len(prefix):].lower()
            config[config_key] = value
    
    return config


def parse_config_value(value: str) -> Union[str, int, float, bool]:
    """Parse configuration value to appropriate type"""
    # Try boolean
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    
    # Try integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value)
    except ValueError:
        pass
    
    # Return as string
    return value