"""
Pydantic models for backend communication API endpoints
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class SyncRequest(BaseModel):
    """Request to sync data with backend"""
    include_status: bool = Field(True, description="Include robot status in sync")
    include_telemetry: bool = Field(True, description="Include telemetry data in sync")
    include_gps: bool = Field(True, description="Include GPS data in sync")
    include_logs: bool = Field(False, description="Include recent logs in sync")
    force_sync: bool = Field(False, description="Force sync even if recent sync exists")
    
    class Config:
        schema_extra = {
            "example": {
                "include_status": True,
                "include_telemetry": True,
                "include_gps": True,
                "include_logs": False,
                "force_sync": False
            }
        }


class TelemetryData(BaseModel):
    """Telemetry data for upload"""
    robot_id: str = Field(..., description="Robot identifier")
    start_time: float = Field(..., description="Data collection start timestamp")
    end_time: float = Field(..., description="Data collection end timestamp")
    data_points: List[Dict[str, Any]] = Field(..., description="Telemetry data points")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    @validator('data_points')
    def validate_data_points(cls, v):
        if len(v) == 0:
            raise ValueError('At least one data point must be provided')
        if len(v) > 10000:
            raise ValueError('Too many data points (max 10000)')
        return v
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "robot_id": "agrobot-rpi-001",
                "start_time": 1640995200.0,
                "end_time": 1640995260.0,
                "data_points": [
                    {
                        "timestamp": 1640995200.0,
                        "gps": {"lat": 47.641468, "lon": -122.140165},
                        "attitude": {"roll": 0.1, "pitch": 0.05, "yaw": 1.57}
                    }
                ],
                "metadata": {"collection_rate": 1.0}
            }
        }


class CommandReceived(BaseModel):
    """Command execution result for acknowledgment"""
    success: bool = Field(..., description="Whether command executed successfully")
    message: str = Field(..., description="Execution result message")
    execution_time: float = Field(..., description="Command execution time in seconds")
    error_code: Optional[str] = Field(None, description="Error code if command failed")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Additional result data")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Command executed successfully",
                "execution_time": 2.5,
                "error_code": None,
                "additional_data": {"new_mode": "GUIDED"}
            }
        }


# Response Models
class SyncResponse(BaseModel):
    """Response from backend sync operation"""
    success: bool = Field(..., description="Whether sync was successful")
    message: str = Field(..., description="Sync result message")
    timestamp: float = Field(..., description="Sync completion timestamp")
    data_sent: int = Field(..., description="Number of data items sent")
    commands_received: int = Field(..., description="Number of commands received")
    next_sync: float = Field(..., description="Next scheduled sync timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Sync completed successfully",
                "timestamp": 1640995200.0,
                "data_sent": 5,
                "commands_received": 2,
                "next_sync": 1640995230.0
            }
        }


class BackendConnection(BaseModel):
    """Backend connection status"""
    connected: bool = Field(..., description="Whether connected to backend")
    url: str = Field(..., description="Backend URL")
    robot_id: str = Field(..., description="Robot identifier")
    last_sync: Optional[float] = Field(None, description="Last successful sync timestamp")
    sync_interval: float = Field(..., description="Sync interval in seconds")
    api_version: str = Field(..., description="Backend API version")
    status: str = Field(..., description="Connection status")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["connected", "disconnected", "error", "authenticating"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "connected": True,
                "url": "http://localhost:5000",
                "robot_id": "agrobot-rpi-001",
                "last_sync": 1640995200.0,
                "sync_interval": 30.0,
                "api_version": "1.0.0",
                "status": "connected"
            }
        }


class DataUpload(BaseModel):
    """Data upload response"""
    success: bool = Field(..., description="Whether upload was successful")
    message: str = Field(..., description="Upload result message")
    records_uploaded: int = Field(..., description="Number of records uploaded")
    upload_size_bytes: int = Field(..., description="Upload size in bytes")
    timestamp: float = Field(..., description="Upload completion timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Data uploaded successfully",
                "records_uploaded": 100,
                "upload_size_bytes": 15360,
                "timestamp": 1640995200.0
            }
        }


class RobotStatus(BaseModel):
    """Robot status for backend reporting"""
    robot_id: str = Field(..., description="Robot identifier")
    timestamp: float = Field(..., description="Status timestamp")
    online: bool = Field(..., description="Whether robot is online")
    mode: str = Field(..., description="Current flight mode")
    armed: bool = Field(..., description="Whether motors are armed")
    battery_voltage: Optional[float] = Field(None, description="Battery voltage")
    battery_percentage: Optional[float] = Field(None, description="Battery percentage")
    location: Optional[Dict[str, float]] = Field(None, description="Current GPS location")
    altitude: Optional[float] = Field(None, description="Current altitude")
    speed: Optional[float] = Field(None, description="Current ground speed")
    heading: Optional[float] = Field(None, description="Current heading")
    mission_active: bool = Field(False, description="Whether a mission is active")
    mission_id: Optional[str] = Field(None, description="Active mission ID")
    errors: List[str] = Field(default=[], description="Current error messages")
    warnings: List[str] = Field(default=[], description="Current warning messages")
    
    class Config:
        schema_extra = {
            "example": {
                "robot_id": "agrobot-rpi-001",
                "timestamp": 1640995200.0,
                "online": True,
                "mode": "GUIDED",
                "armed": True,
                "battery_voltage": 12.6,
                "battery_percentage": 85.0,
                "location": {
                    "latitude": 47.641468,
                    "longitude": -122.140165
                },
                "altitude": 10.5,
                "speed": 2.5,
                "heading": 45.0,
                "mission_active": False,
                "mission_id": None,
                "errors": [],
                "warnings": []
            }
        }


# Command Models
class BackendCommand(BaseModel):
    """Command received from backend"""
    id: str = Field(..., description="Command unique identifier")
    type: str = Field(..., description="Command type")
    priority: int = Field(1, description="Command priority (1=low, 5=high)", ge=1, le=5)
    parameters: Dict[str, Any] = Field(..., description="Command parameters")
    timeout: Optional[float] = Field(None, description="Command timeout in seconds")
    retry_count: int = Field(0, description="Number of retries allowed", ge=0, le=5)
    created_at: float = Field(..., description="Command creation timestamp")
    expires_at: Optional[float] = Field(None, description="Command expiration timestamp")
    
    @validator('type')
    def validate_command_type(cls, v):
        valid_types = [
            "set_mode", "arm_motors", "disarm_motors", "takeoff", "land", "rtl",
            "goto_position", "set_speed", "emergency_stop", "start_mission",
            "stop_mission", "update_config", "reboot", "diagnostics"
        ]
        if v not in valid_types:
            raise ValueError(f"Command type must be one of: {valid_types}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "id": "cmd_001_1640995200",
                "type": "goto_position",
                "priority": 3,
                "parameters": {
                    "latitude": 47.641468,
                    "longitude": -122.140165,
                    "altitude": 10.0
                },
                "timeout": 30.0,
                "retry_count": 2,
                "created_at": 1640995200.0,
                "expires_at": 1640995500.0
            }
        }


class CommandQueue(BaseModel):
    """Command queue status"""
    pending_commands: List[BackendCommand] = Field(..., description="Pending commands")
    executing_command: Optional[BackendCommand] = Field(None, description="Currently executing command")
    completed_commands: int = Field(..., description="Number of completed commands")
    failed_commands: int = Field(..., description="Number of failed commands")
    queue_size: int = Field(..., description="Current queue size")
    last_execution: Optional[float] = Field(None, description="Last command execution timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "pending_commands": [],
                "executing_command": None,
                "completed_commands": 15,
                "failed_commands": 2,
                "queue_size": 0,
                "last_execution": 1640995200.0
            }
        }


# Advanced Models
class BackendMetrics(BaseModel):
    """Backend communication metrics"""
    total_requests: int = Field(..., description="Total requests sent")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    average_response_time: float = Field(..., description="Average response time in seconds")
    last_request_time: Optional[float] = Field(None, description="Last request timestamp")
    uptime_seconds: float = Field(..., description="Backend connection uptime")
    data_uploaded_bytes: int = Field(..., description="Total data uploaded in bytes")
    data_downloaded_bytes: int = Field(..., description="Total data downloaded in bytes")
    sync_count: int = Field(..., description="Number of sync operations")
    command_count: int = Field(..., description="Number of commands received")
    
    @property
    def success_rate(self) -> float:
        """Calculate request success rate"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    class Config:
        schema_extra = {
            "example": {
                "total_requests": 1000,
                "successful_requests": 985,
                "failed_requests": 15,
                "average_response_time": 0.25,
                "last_request_time": 1640995200.0,
                "uptime_seconds": 86400.0,
                "data_uploaded_bytes": 1048576,
                "data_downloaded_bytes": 524288,
                "sync_count": 120,
                "command_count": 25
            }
        }


class BackendHealth(BaseModel):
    """Backend service health status"""
    api_available: bool = Field(..., description="Whether API is available")
    database_connected: bool = Field(..., description="Whether database is connected")
    authentication_working: bool = Field(..., description="Whether authentication is working")
    response_time_ms: float = Field(..., description="Average response time in milliseconds")
    error_rate: float = Field(..., description="Error rate percentage")
    last_health_check: float = Field(..., description="Last health check timestamp")
    version: str = Field(..., description="Backend service version")
    status: str = Field(..., description="Overall backend health status")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["healthy", "degraded", "unhealthy", "unreachable"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "api_available": True,
                "database_connected": True,
                "authentication_working": True,
                "response_time_ms": 250.0,
                "error_rate": 1.5,
                "last_health_check": 1640995200.0,
                "version": "1.0.0",
                "status": "healthy"
            }
        }


class SyncHistory(BaseModel):
    """Sync operation history"""
    sync_id: str = Field(..., description="Sync operation identifier")
    timestamp: float = Field(..., description="Sync timestamp")
    duration_seconds: float = Field(..., description="Sync duration")
    data_sent: int = Field(..., description="Data items sent")
    data_received: int = Field(..., description="Data items received")
    success: bool = Field(..., description="Whether sync was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, description="Number of retries")
    
    class Config:
        schema_extra = {
            "example": {
                "sync_id": "sync_001_1640995200",
                "timestamp": 1640995200.0,
                "duration_seconds": 2.5,
                "data_sent": 10,
                "data_received": 2,
                "success": True,
                "error_message": None,
                "retry_count": 0
            }
        }


class DataStream(BaseModel):
    """Real-time data stream configuration"""
    stream_id: str = Field(..., description="Stream identifier")
    data_type: str = Field(..., description="Type of data being streamed")
    enabled: bool = Field(..., description="Whether stream is enabled")
    interval_seconds: float = Field(..., description="Stream interval in seconds")
    last_update: Optional[float] = Field(None, description="Last update timestamp")
    buffer_size: int = Field(..., description="Stream buffer size")
    compression_enabled: bool = Field(False, description="Whether compression is enabled")
    encryption_enabled: bool = Field(False, description="Whether encryption is enabled")
    
    @validator('data_type')
    def validate_data_type(cls, v):
        valid_types = ["gps", "telemetry", "status", "logs", "camera", "sensors"]
        if v not in valid_types:
            raise ValueError(f"Data type must be one of: {valid_types}")
        return v
    
    @validator('interval_seconds')
    def validate_interval(cls, v):
        if not (0.1 <= v <= 3600):
            raise ValueError("Interval must be between 0.1 and 3600 seconds")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "stream_id": "gps_stream_001",
                "data_type": "gps",
                "enabled": True,
                "interval_seconds": 1.0,
                "last_update": 1640995200.0,
                "buffer_size": 100,
                "compression_enabled": True,
                "encryption_enabled": False
            }
        }


# Placeholder for HardwareInfo (if not defined elsewhere)
class HardwareInfo(BaseModel):
    cpu_model: str = Field(..., description="CPU model of the Raspberry Pi")
    ram_gb: float = Field(..., description="Total RAM in GB")
    disk_gb: float = Field(..., description="Total disk space in GB")
    serial_number: Optional[str] = Field(None, description="Raspberry Pi serial number")
    camera_present: bool = False
    # Add other relevant hardware details


# Placeholder for Capabilities (if not defined elsewhere)
class Capability(BaseModel):
    name: str = Field(..., description="Name of the capability (e.g., 'GPS', 'Arming', 'MissionPlanning')")
    supported: bool = Field(..., description="Whether the capability is supported by this robot")
    version: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# Placeholder for Robot Location
class Location(BaseModel):
    latitude: float = Field(..., description="Robot's current latitude")
    longitude: float = Field(..., description="Robot's current longitude")
    altitude: Optional[float] = Field(None, description="Robot's current altitude")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the location data")


# Registration Models
class RegisterRequest(BaseModel):
    robot_id: str = Field(..., description="Unique ID of the Raspberry Pi robot")
    robot_name: str = Field(..., description="Name of the robot")
    version: str = Field(..., description="Current software version of the controller")
    robot_ip_address: str = Field(..., description="Robot's IP address")
    robot_port: int = Field(..., description="Robot's port")
    capabilities: List[Capability] = Field(..., description="List of capabilities supported by the robot")
    location: Optional[Location] = Field(None, description="Current location of the robot")
    software_version: str = Field(..., description="Current software version of the controller")
    metadata: dict = {}
    
    class Config:
        schema_extra = {
            "example": {
                "robot_id": "agrobot-rpi-001",
                "robot_name": "AG Robot",
                "version": "1.0.0",
                "robot_ip_address": "192.168.1.100",
                "robot_port": 5000,
                "capabilities": [
                    {"name": "GPS", "supported": True},
                    {"name": "Arming", "supported": True},
                    {"name": "MissionPlanning", "supported": False}
                ],
                "location": {"latitude": 45.123, "longitude": -122.456, "altitude": 10.0},
                "software_version": "1.0.0",
                "metadata": {}
            }
        }


class RegisterResponse(BaseModel):
    success: bool = Field(..., description="True if registration was successful")
    message: str = Field(..., description="Human-readable message")
    robot_id: str = Field(..., description="Registered robot ID")
    backend_status: Optional[str] = Field(None, description="Status from backend after registration")


# Heartbeat Models
class QuickHealth(BaseModel):
    cpu_percent: float = Field(..., description="Current CPU usage percentage")
    memory_percent: float = Field(..., description="Current memory usage percentage")
    disk_percent: float = Field(..., description="Current disk usage percentage")
    mavlink_connected: bool = Field(..., description="Is MAVLink connected?")
    gps_fix: bool = Field(..., description="Does GPS have a fix?")


class HeartbeatRequest(BaseModel):
    robot_id: str = Field(..., description="Unique ID of the Raspberry Pi robot")
    status: str = Field(..., description="Current operational status (e.g., 'active', 'idle', 'error')")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the heartbeat")
    quick_health: QuickHealth = Field(..., description="Quick snapshot of system health")


class HeartbeatResponse(BaseModel):
    success: bool = Field(..., description="True if heartbeat was processed")
    message: str = Field(..., description="Human-readable message from backend")
    server_time: datetime = Field(default_factory=datetime.now, description="Backend server timestamp")
    commands_pending: int = Field(0, description="Number of commands pending for this robot")


# Command Management Models
class PendingCommandsResponse(BaseModel):
    success: bool = Field(..., description="True if commands were retrieved")
    message: str = Field(..., description="Human-readable message")
    commands: List[BackendCommand] = Field(..., description="List of pending commands for this robot")


class CommandResultRequest(BaseModel):
    command_id: str = Field(..., description="Unique ID of the command")
    status: str = Field(..., description="Execution status ('completed', 'failed', 'in_progress', 'rejected')")
    result: Optional[Dict[str, Any]] = Field(None, description="Result data if command completed successfully")
    error: Optional[str] = Field(None, description="Error message if command failed")
    execution_time: Optional[float] = Field(None, description="Time taken to execute command in seconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the result report")


class CommandResultResponse(BaseModel):
    success: bool = Field(..., description="True if result was received by backend")
    message: str = Field(..., description="Human-readable message from backend")


# Data Transmission Models
class TelemetryDataPoint(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of this telemetry point")
    gps: Optional[Dict[str, Any]] = None # Use Dict as GPSData and other models may not be directly JSON serializable without .dict()
    attitude: Optional[Dict[str, Any]] = None
    battery: Optional[Dict[str, Any]] = None
    sensors: Optional[Dict[str, Any]] = None # Placeholder for other sensor data


class TelemetryBatchRequest(BaseModel):
    robot_id: str = Field(..., description="Unique ID of the Raspberry Pi robot")
    data: List[TelemetryDataPoint] = Field(..., description="List of telemetry data points")
    
    class Config:
        schema_extra = {
            "example": {
                "robot_id": "agrobot-rpi-001",
                "data": [
                    {
                        "timestamp": "2024-01-01T12:00:00Z",
                        "gps": {"latitude": 45.1, "longitude": -122.1},
                        "battery": {"voltage": 12.5, "remaining": 90}
                    }
                ]
            }
        }


class TelemetryBatchResponse(BaseModel):
    success: bool = Field(..., description="True if telemetry batch was received")
    message: str = Field(..., description="Human-readable message from backend")
    records_received: int = Field(..., description="Number of telemetry records processed")


class AlertRequest(BaseModel):
    robot_id: str = Field(..., description="Unique ID of the Raspberry Pi robot")
    severity: str = Field(..., description="Severity level ('critical', 'warning', 'info')")
    message: str = Field(..., description="Alert message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the alert")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional alert details")


class AlertResponse(BaseModel):
    success: bool = Field(..., description="True if alert was received by backend")
    message: str = Field(..., description="Human-readable message from backend")