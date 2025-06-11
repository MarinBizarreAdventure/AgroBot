"""
Application constants and enumerations
"""

from enum import Enum


# MAVLink Constants
class MAVLinkCommands:
    """MAVLink command IDs"""
    NAV_WAYPOINT = 16
    NAV_LOITER_UNLIM = 17
    NAV_LOITER_TURNS = 18
    NAV_LOITER_TIME = 19
    NAV_RETURN_TO_LAUNCH = 20
    NAV_LAND = 21
    NAV_TAKEOFF = 22
    
    COMPONENT_ARM_DISARM = 400
    DO_SET_MODE = 176
    DO_CHANGE_SPEED = 178
    DO_SET_HOME = 179
    DO_SET_PARAMETER = 180
    DO_SET_RELAY = 181
    DO_REPEAT_RELAY = 182
    DO_SET_SERVO = 183
    DO_REPEAT_SERVO = 184


class FlightModes:
    """ArduPilot flight modes"""
    STABILIZE = 0
    ACRO = 1
    ALT_HOLD = 2
    AUTO = 3
    GUIDED = 4
    LOITER = 5
    RTL = 6
    CIRCLE = 7
    LAND = 9
    GUIDED_NOGPS = 20
    SMART_RTL = 21
    FLOWHOLD = 22
    FOLLOW = 23


class MAVTypes:
    """MAVLink vehicle types"""
    GENERIC = 0
    FIXED_WING = 1
    QUADROTOR = 2
    COAXIAL = 3
    HELICOPTER = 4
    ANTENNA_TRACKER = 5
    GCS = 6
    AIRSHIP = 7
    FREE_BALLOON = 8
    ROCKET = 9
    GROUND_ROVER = 10
    SURFACE_BOAT = 11
    SUBMARINE = 12
    HEXAROTOR = 13
    OCTOROTOR = 14
    TRICOPTER = 15
    FLAPPING_WING = 16
    KITE = 17
    ONBOARD_CONTROLLER = 18
    VTOL_DUOROTOR = 19
    VTOL_QUADROTOR = 20


# GPS Constants
class GPSFixTypes:
    """GPS fix type constants"""
    NO_GPS = 0
    NO_FIX = 1
    FIX_2D = 2
    FIX_3D = 3
    DGPS = 4
    RTK_FLOAT = 5
    RTK_FIXED = 6


# System Constants
class SystemStatus:
    """System status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class LogLevels:
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Hardware Constants
class GPIOPins:
    """GPIO pin assignments"""
    LED_STATUS = 18
    LED_ERROR = 19
    BUZZER = 20
    EMERGENCY_STOP = 21


class I2CAddresses:
    """Common I2C device addresses"""
    COMPASS_HMC5883L = 0x1E
    BAROMETER_BMP280 = 0x76
    IMU_MPU6050 = 0x68
    ADC_ADS1115 = 0x48


# Communication Constants
class SerialPorts:
    """Serial port definitions"""
    PIXHAWK_USB = "/dev/ttyUSB0"
    PIXHAWK_UART = "/dev/ttyAMA0"
    GPS_MODULE = "/dev/ttyUSB1"


class NetworkPorts:
    """Network port assignments"""
    HTTP_API = 8000
    WEBSOCKET = 8001
    MAVLINK_UDP = 14550
    MAVLINK_TCP = 5760


# Safety Constants
class SafetyLimits:
    """Safety limit constants"""
    MAX_ALTITUDE = 120  # meters (FAA limit)
    MAX_SPEED = 20      # m/s
    MAX_ACCELERATION = 5 # m/s²
    MIN_BATTERY_VOLTAGE = 10.5  # volts
    MAX_TEMPERATURE = 85  # Celsius
    MAX_WIND_SPEED = 15   # m/s


class GeofenceLimits:
    """Geofence constants"""
    DEFAULT_RADIUS = 100    # meters
    MAX_RADIUS = 1000      # meters
    MIN_RADIUS = 10        # meters


# Mission Constants
class MissionTypes:
    """Mission type constants"""
    SURVEY = "survey"
    PATROL = "patrol"
    WAYPOINT = "waypoint"
    SEARCH = "search"
    DELIVERY = "delivery"
    MAPPING = "mapping"


class PatternTypes:
    """Flight pattern types"""
    SQUARE = "square"
    CIRCLE = "circle"
    GRID = "grid"
    SPIRAL = "spiral"
    LAWNMOWER = "lawnmower"
    ZIGZAG = "zigzag"


# Error Codes
class ErrorCodes:
    """Application error codes"""
    # Connection errors (1000-1099)
    MAVLINK_CONNECTION_FAILED = 1001
    BACKEND_CONNECTION_FAILED = 1002
    GPS_CONNECTION_FAILED = 1003
    RADIO_CONNECTION_FAILED = 1004
    
    # Configuration errors (1100-1199)
    INVALID_CONFIGURATION = 1101
    MISSING_PARAMETER = 1102
    INVALID_PARAMETER = 1103
    
    # Safety errors (1200-1299)
    SAFETY_VIOLATION = 1201
    GEOFENCE_VIOLATION = 1202
    ALTITUDE_VIOLATION = 1203
    SPEED_VIOLATION = 1204
    BATTERY_LOW = 1205
    GPS_ACCURACY_POOR = 1206
    
    # Mission errors (1300-1399)
    MISSION_INVALID = 1301
    WAYPOINT_INVALID = 1302
    MISSION_TIMEOUT = 1303
    MISSION_ABORTED = 1304
    
    # Hardware errors (1400-1499)
    SENSOR_FAILURE = 1401
    ACTUATOR_FAILURE = 1402
    COMMUNICATION_FAILURE = 1403
    POWER_FAILURE = 1404
    
    # Software errors (1500-1599)
    INTERNAL_ERROR = 1501
    MEMORY_ERROR = 1502
    TIMEOUT_ERROR = 1503
    PERMISSION_ERROR = 1504


# Status Messages
class StatusMessages:
    """Standard status messages"""
    STARTUP_COMPLETE = "System startup completed successfully"
    SHUTDOWN_INITIATED = "System shutdown initiated"
    CONNECTION_ESTABLISHED = "Connection established"
    CONNECTION_LOST = "Connection lost"
    MISSION_STARTED = "Mission execution started"
    MISSION_COMPLETED = "Mission completed successfully"
    EMERGENCY_STOP = "Emergency stop activated"
    SAFETY_VIOLATION = "Safety violation detected"
    BATTERY_LOW = "Low battery warning"
    GPS_LOST = "GPS signal lost"
    GEOFENCE_BREACH = "Geofence boundary breached"


# Units and Conversions
class Units:
    """Unit conversion constants"""
    DEGREES_TO_RADIANS = 3.14159 / 180.0
    RADIANS_TO_DEGREES = 180.0 / 3.14159
    KNOTS_TO_MS = 0.514444
    MPH_TO_MS = 0.44704
    FEET_TO_METERS = 0.3048
    METERS_TO_FEET = 3.28084


class EarthConstants:
    """Earth-related constants"""
    RADIUS_METERS = 6371000    # Earth's radius in meters
    GRAVITY = 9.80665          # Standard gravity in m/s²
    MAGNETIC_DECLINATION = 0   # Local magnetic declination (to be configured)


# File Paths
class FilePaths:
    """Application file paths"""
    CONFIG_DIR = "config"
    LOG_DIR = "logs"
    DATA_DIR = "data"
    MISSION_DIR = "missions"
    BACKUP_DIR = "backups"
    TEMP_DIR = "temp"


# Time Constants
class TimeConstants:
    """Time-related constants"""
    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_DAY = 86400
    MILLISECONDS_PER_SECOND = 1000
    MICROSECONDS_PER_SECOND = 1000000


# API Constants
class APIConstants:
    """API-related constants"""
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 1000
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60  # seconds


# WebSocket Constants
class WebSocketConstants:
    """WebSocket-related constants"""
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    PING_INTERVAL = 30              # seconds
    PONG_TIMEOUT = 10               # seconds
    RECONNECT_DELAY = 5             # seconds
    MAX_RECONNECT_ATTEMPTS = 5


# Database Constants (if using local database)
class DatabaseConstants:
    """Database-related constants"""
    MAX_CONNECTIONS = 10
    CONNECTION_TIMEOUT = 30
    QUERY_TIMEOUT = 60
    BATCH_SIZE = 100
    RETENTION_DAYS = 30


# Hardware Specifications
class HardwareSpecs:
    """Hardware specification constants"""
    # Raspberry Pi 4 specifications
    MAX_CPU_TEMP = 85      # Celsius
    THROTTLE_TEMP = 80     # Celsius
    MIN_SD_SPACE_MB = 1000 # Minimum SD card space
    
    # Power consumption estimates (mA)
    RPI_IDLE = 600
    RPI_ACTIVE = 1200
    PIXHAWK = 100
    GPS_MODULE = 50
    RADIO_MODULE = 30