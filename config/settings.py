"""
Configuration settings for AgroBot Raspberry Pi application
"""

import os
from typing import List, Optional, Any
from pydantic import BaseSettings, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application settings
    APP_NAME: str = "AgroBot Raspberry Pi Controller"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS settings
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # MAVLink/Pixhawk connection settings
    MAVLINK_CONNECTION_STRING: str = "/dev/ttyUSB0"  # or "udp:127.0.0.1:14550"
    MAVLINK_BAUD_RATE: int = 57600
    MAVLINK_TIMEOUT: float = 5.0
    AUTO_CONNECT_MAVLINK: bool = True
    
    # GPS settings
    GPS_MIN_SATELLITES: int = 6
    GPS_MAX_HDOP: float = 2.0
    GPS_COORDINATE_PRECISION: int = 7
    
    # Movement settings
    MAX_SPEED: float = 5.0  # m/s
    MAX_ACCELERATION: float = 2.0  # m/s²
    SAFETY_DISTANCE: float = 1.0  # meters
    HOME_ALTITUDE: float = 10.0  # meters above ground
    
    # Radio Control settings
    RC_CHANNELS: int = 8
    RC_TIMEOUT: float = 2.0  # seconds
    RC_FAILSAFE_ENABLED: bool = True
    RC_MIN_PWM: int = 1000
    RC_MAX_PWM: int = 2000
    RC_MID_PWM: int = 1500
    
    # Safety settings
    GEOFENCE_ENABLED: bool = True
    GEOFENCE_RADIUS: float = 100.0  # meters
    BATTERY_LOW_THRESHOLD: float = 20.0  # percentage
    AUTO_RTL_ENABLED: bool = True  # Return to Launch
    
    # Mission settings
    WAYPOINT_RADIUS: float = 2.0  # meters
    MISSION_TIMEOUT: float = 3600.0  # seconds (1 hour)
    MAX_WAYPOINTS: int = 100
    
    # AgroBot Backend settings
    AGROBOT_BACKEND_URL: str = "http://localhost:5000"
    AGROBOT_API_KEY: Optional[str] = None
    BACKEND_TIMEOUT: float = 10.0
    BACKEND_RETRY_ATTEMPTS: int = 3
    BACKEND_SYNC_INTERVAL: float = 30.0  # seconds
    MAX_RECONNECT_ATTEMPTS: int = 10
    RECONNECT_DELAY: int = 5
    
    # Robot identification
    ROBOT_ID: str = "agrobot-rpi-001"
    ROBOT_NAME: str = "AgroBot Raspberry Pi"
    
    # Telemetry settings
    TELEMETRY_ENABLED: bool = True
    TELEMETRY_INTERVAL: float = 5.0  # seconds
    TELEMETRY_BUFFER_SIZE: int = 1000
    TELEMETRY_BATCH_SIZE: int = 100
    HEARTBEAT_INTERVAL: float = 10.0 # seconds

    COMMAND_POLLING_INTERVAL: float = 5.0 # seconds
    
    # WebSocket settings
    WEBSOCKET_MAX_CONNECTIONS: int = 10
    WEBSOCKET_PING_INTERVAL: float = 30.0
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Hardware-specific settings
    I2C_BUS: int = 1
    SPI_BUS: int = 0
    GPIO_PINS: dict = {
        "led_status": 18,
        "led_error": 19,
        "buzzer": 20,
        "emergency_stop": 21
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name == "ALLOWED_HOSTS":
                if raw_val is None or raw_val.strip() == "":
                    return []
                # Attempt to parse as comma-separated list
                return [host.strip() for host in raw_val.split(",")]
            # For other fields, use Pydantic's default parsing
            return cls.json_loads(raw_val) if raw_val else raw_val # Pydantic's default json_loads might be called here for other list types, or raw_val itself
    
    @validator("ALLOWED_HOSTS", pre=True)
    def validate_allowed_hosts(cls, v):
        # This validator might still be called, but the parsing should be handled by parse_env_var now
        if isinstance(v, str):
            if v == "":
                return []
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("MAVLINK_CONNECTION_STRING")
    def validate_mavlink_connection(cls, v):
        if not v:
            raise ValueError("MAVLink connection string cannot be empty")
        # Basic validation for common connection types
        valid_prefixes = ("/dev/", "tcp:", "udp:", "serial:")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"Invalid MAVLink connection string: {v}")
        return v
    
    @validator("AGROBOT_BACKEND_URL")
    def validate_backend_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Backend URL must start with http:// or https://")
        return v.rstrip("/")  # Remove trailing slash
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @property
    def mavlink_connection_params(self) -> dict:
        """Get MAVLink connection parameters as a dictionary"""
        return {
            "connection_string": self.MAVLINK_CONNECTION_STRING,
            "baud": self.MAVLINK_BAUD_RATE,
            "timeout": self.MAVLINK_TIMEOUT
        }
    
    @property
    def safety_params(self) -> dict:
        """Get safety parameters as a dictionary"""
        return {
            "geofence_enabled": self.GEOFENCE_ENABLED,
            "geofence_radius": self.GEOFENCE_RADIUS,
            "battery_low_threshold": self.BATTERY_LOW_THRESHOLD,
            "auto_rtl_enabled": self.AUTO_RTL_ENABLED,
            "safety_distance": self.SAFETY_DISTANCE
        }
    
    @property
    def movement_params(self) -> dict:
        """Get movement parameters as a dictionary"""
        return {
            "max_speed": self.MAX_SPEED,
            "max_acceleration": self.MAX_ACCELERATION,
            "waypoint_radius": self.WAYPOINT_RADIUS,
            "home_altitude": self.HOME_ALTITUDE
        }
    
    @property
    def backend_headers(self) -> dict:
        """Get headers for backend API requests"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"{self.APP_NAME}/{self.VERSION}"
        }
        if self.AGROBOT_API_KEY:
            headers["Authorization"] = f"Bearer {self.AGROBOT_API_KEY}"
        return headers


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)"""
    return Settings()


# Environment-specific settings
class DevelopmentSettings(Settings):
    """Development environment settings"""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    AUTO_CONNECT_MAVLINK: bool = False  # Safer for development


class ProductionSettings(Settings):
    """Production environment settings"""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]


class TestingSettings(Settings):
    """Testing environment settings"""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    AUTO_CONNECT_MAVLINK: bool = False
    TELEMETRY_ENABLED: bool = False


def get_settings_for_environment(env: str = None) -> Settings:
    """Get settings for specific environment"""
    env = env or os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()