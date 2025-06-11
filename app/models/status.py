"""
Pydantic models for status and diagnostics API endpoints
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Main Status Models
class SystemStatus(BaseModel):
    """Overall system status"""
    overall_health: str = Field(..., description="Overall system health status")
    health_score: float = Field(..., description="Health score percentage (0-100)")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    system_time: float = Field(..., description="Current system timestamp")
    platform: str = Field(..., description="Platform information")
    hostname: str = Field(..., description="System hostname")
    architecture: str = Field(..., description="System architecture")
    python_version: str = Field(..., description="Python version")
    subsystems: Dict[str, str] = Field(..., description="Subsystem health status")
    resource_usage: Dict[str, float] = Field(..., description="Resource usage metrics")
    
    @validator('overall_health')
    def validate_health(cls, v):
        valid_statuses = ["healthy", "degraded", "unhealthy", "critical"]
        if v not in valid_statuses:
            raise ValueError(f"Health status must be one of: {valid_statuses}")
        return v
    
    @validator('health_score')
    def validate_score(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("Health score must be between 0 and 100")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "overall_health": "healthy",
                "health_score": 95.0,
                "uptime_seconds": 86400.0,
                "system_time": 1640995200.0,
                "platform": "Linux 5.15.0",
                "hostname": "agrobot-rpi",
                "architecture": "armv7l",
                "python_version": "3.9.2",
                "subsystems": {
                    "mavlink": "healthy",
                    "telemetry": "healthy",
                    "gps": "healthy",
                    "radio": "healthy"
                },
                "resource_usage": {
                    "cpu_percent": 25.5,
                    "memory_percent": 45.2,
                    "disk_percent": 60.1,
                    "temperature": 45.8
                }
            }
        }


class ApplicationStatus(BaseModel):
    """Application-specific status"""
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Runtime environment")
    debug_mode: bool = Field(..., description="Whether debug mode is enabled")
    uptime_seconds: float = Field(..., description="Application uptime")
    active_connections: int = Field(..., description="Number of active connections")
    configuration: Dict[str, Any] = Field(..., description="Key configuration settings")
    services: Dict[str, Dict[str, Any]] = Field(..., description="Service status details")
    features: Dict[str, bool] = Field(..., description="Feature availability")
    
    class Config:
        schema_extra = {
            "example": {
                "version": "1.0.0",
                "environment": "production",
                "debug_mode": False,
                "uptime_seconds": 3600.0,
                "active_connections": 2,
                "configuration": {
                    "mavlink_connection": "/dev/ttyUSB0",
                    "backend_url": "http://localhost:5000",
                    "robot_id": "agrobot-rpi-001"
                },
                "services": {
                    "mavlink_manager": {
                        "status": "running",
                        "details": {"connected": True}
                    }
                },
                "features": {
                    "gps_tracking": True,
                    "mission_planning": True,
                    "radio_control": True
                }
            }
        }


class HardwareStatus(BaseModel):
    """Hardware status information"""
    platform: str = Field(..., description="Hardware platform")
    cpu: Dict[str, Any] = Field(..., description="CPU information")
    memory: Dict[str, Any] = Field(..., description="Memory information")
    storage: Dict[str, Any] = Field(..., description="Storage information")
    interfaces: Dict[str, str] = Field(..., description="Hardware interface status")
    network_interfaces: List[Dict[str, Any]] = Field(..., description="Network interfaces")
    sensors: Dict[str, str] = Field(..., description="Sensor availability")
    peripherals: Dict[str, str] = Field(..., description="Connected peripherals")
    
    class Config:
        schema_extra = {
            "example": {
                "platform": "Raspberry Pi",
                "cpu": {
                    "model": "ARM Cortex-A72",
                    "cores": 4,
                    "frequency": {"current": 1500.0, "min": 600.0, "max": 1500.0},
                    "temperature": 45.8
                },
                "memory": {
                    "total_gb": 4.0,
                    "available_gb": 2.1,
                    "used_percent": 47.5
                },
                "storage": {
                    "total_gb": 32.0,
                    "free_gb": 12.8,
                    "used_percent": 60.0
                },
                "interfaces": {
                    "i2c": "available",
                    "spi": "available",
                    "uart": "available",
                    "gpio": "available"
                },
                "network_interfaces": [
                    {
                        "name": "wlan0",
                        "ip_addresses": ["192.168.1.100"],
                        "status": "up"
                    }
                ],
                "sensors": {
                    "gps": "available",
                    "imu": "unknown",
                    "camera": "unknown"
                },
                "peripherals": {
                    "pixhawk": "connected",
                    "radio": "connected"
                }
            }
        }


class NetworkStatus(BaseModel):
    """Network connectivity status"""
    connected: bool = Field(..., description="Whether internet is accessible")
    interfaces: List[str] = Field(..., description="Available network interfaces")
    statistics: Dict[str, int] = Field(..., description="Network I/O statistics")
    connectivity: Dict[str, bool] = Field(..., description="Connectivity test results")
    active_connections: List[Dict[str, Any]] = Field(..., description="Active network connections")
    wifi: Optional[Dict[str, Any]] = Field(None, description="Wi-Fi connection details")
    
    class Config:
        schema_extra = {
            "example": {
                "connected": True,
                "interfaces": ["lo", "eth0", "wlan0"],
                "statistics": {
                    "bytes_sent": 1048576,
                    "bytes_recv": 2097152,
                    "packets_sent": 1000,
                    "packets_recv": 1500
                },
                "connectivity": {
                    "internet": True,
                    "backend": True,
                    "local_network": True
                },
                "active_connections": [
                    {
                        "local_address": "192.168.1.100:8000",
                        "remote_address": "192.168.1.50:54321",
                        "status": "ESTABLISHED",
                        "pid": 1234
                    }
                ],
                "wifi": {
                    "connected": True,
                    "ssid": "AgroBot-Network",
                    "signal_strength": -45,
                    "frequency": "2.4GHz"
                }
            }
        }


class PerformanceMetrics(BaseModel):
    """Detailed performance metrics"""
    timestamp: float = Field(..., description="Metrics timestamp")
    cpu: Dict[str, Any] = Field(..., description="CPU performance metrics")
    memory: Dict[str, Any] = Field(..., description="Memory performance metrics")
    disk: Dict[str, Any] = Field(..., description="Disk I/O metrics")
    network: Dict[str, Any] = Field(..., description="Network I/O metrics")
    processes: Dict[str, int] = Field(..., description="Process statistics")
    temperature: Optional[float] = Field(None, description="System temperature")
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": 1640995200.0,
                "cpu": {
                    "usage_percent": 25.5,
                    "load_average": [0.5, 0.3, 0.2],
                    "count": 4
                },
                "memory": {
                    "virtual": {
                        "total": 4294967296,
                        "available": 2147483648,
                        "percent": 50.0
                    },
                    "swap": {
                        "total": 1073741824,
                        "used": 0,
                        "percent": 0.0
                    }
                },
                "disk": {
                    "io": {
                        "read_count": 1000,
                        "write_count": 500,
                        "read_bytes": 1048576,
                        "write_bytes": 524288
                    }
                },
                "network": {
                    "io": {
                        "bytes_sent": 1048576,
                        "bytes_recv": 2097152
                    }
                },
                "processes": {
                    "total": 150,
                    "running": 2,
                    "sleeping": 148
                },
                "temperature": 45.8
            }
        }


class DiagnosticsReport(BaseModel):
    """Comprehensive diagnostics report"""
    timestamp: float = Field(..., description="Diagnostics timestamp")
    overall_health: str = Field(..., description="Overall health assessment")
    success_rate: float = Field(..., description="Test success rate percentage")
    tests_passed: int = Field(..., description="Number of tests passed")
    tests_total: int = Field(..., description="Total number of tests")
    tests: Dict[str, Dict[str, Any]] = Field(..., description="Individual test results")
    recommendations: List[str] = Field(..., description="Improvement recommendations")
    
    @validator('overall_health')
    def validate_health(cls, v):
        valid_statuses = ["healthy", "degraded", "poor", "critical"]
        if v not in valid_statuses:
            raise ValueError(f"Health status must be one of: {valid_statuses}")
        return v
    
    @validator('success_rate')
    def validate_success_rate(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("Success rate must be between 0 and 100")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": 1640995200.0,
                "overall_health": "healthy",
                "success_rate": 85.7,
                "tests_passed": 6,
                "tests_total": 7,
                "tests": {
                    "system_resources": {
                        "passed": True,
                        "details": {
                            "cpu_usage": 25.5,
                            "memory_usage": 47.5,
                            "disk_usage": 60.0
                        }
                    },
                    "mavlink_connection": {
                        "passed": True,
                        "details": {"connected": True}
                    }
                },
                "recommendations": [
                    "All systems functioning normally"
                ]
            }
        }


# Specialized Status Models
class ServiceStatus(BaseModel):
    """Individual service status"""
    name: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    uptime_seconds: Optional[float] = Field(None, description="Service uptime")
    restart_count: int = Field(0, description="Number of restarts")
    last_restart: Optional[float] = Field(None, description="Last restart timestamp")
    health_check: Optional[Dict[str, Any]] = Field(None, description="Health check results")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Service configuration")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["running", "stopped", "starting", "stopping", "error", "unknown"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "mavlink_manager",
                "status": "running",
                "uptime_seconds": 3600.0,
                "restart_count": 0,
                "last_restart": None,
                "health_check": {
                    "connected": True,
                    "last_heartbeat": 1640995200.0
                },
                "configuration": {
                    "connection_string": "/dev/ttyUSB0",
                    "baud_rate": 57600
                }
            }
        }


class ResourceAlert(BaseModel):
    """Resource usage alert"""
    resource: str = Field(..., description="Resource type")
    current_value: float = Field(..., description="Current resource value")
    threshold: float = Field(..., description="Alert threshold")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    timestamp: float = Field(..., description="Alert timestamp")
    active: bool = Field(True, description="Whether alert is currently active")
    
    @validator('resource')
    def validate_resource(cls, v):
        valid_resources = ["cpu", "memory", "disk", "temperature", "network"]
        if v not in valid_resources:
            raise ValueError(f"Resource must be one of: {valid_resources}")
        return v
    
    @validator('severity')
    def validate_severity(cls, v):
        valid_severities = ["info", "warning", "error", "critical"]
        if v not in valid_severities:
            raise ValueError(f"Severity must be one of: {valid_severities}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "resource": "temperature",
                "current_value": 82.5,
                "threshold": 80.0,
                "severity": "warning",
                "message": "CPU temperature is above warning threshold",
                "timestamp": 1640995200.0,
                "active": True
            }
        }


class SecurityStatus(BaseModel):
    """Security status information"""
    firewall_enabled: bool = Field(..., description="Whether firewall is enabled")
    ssh_enabled: bool = Field(..., description="Whether SSH is enabled")
    failed_login_attempts: int = Field(..., description="Recent failed login attempts")
    open_ports: List[int] = Field(..., description="Open network ports")
    last_security_update: Optional[float] = Field(None, description="Last security update timestamp")
    vulnerabilities: List[Dict[str, Any]] = Field(default=[], description="Known vulnerabilities")
    security_score: float = Field(..., description="Security score (0-100)")
    
    @validator('security_score')
    def validate_security_score(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("Security score must be between 0 and 100")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "firewall_enabled": True,
                "ssh_enabled": True,
                "failed_login_attempts": 0,
                "open_ports": [22, 8000],
                "last_security_update": 1640995200.0,
                "vulnerabilities": [],
                "security_score": 85.0
            }
        }


class MaintenanceStatus(BaseModel):
    """System maintenance status"""
    last_maintenance: Optional[float] = Field(None, description="Last maintenance timestamp")
    next_scheduled: Optional[float] = Field(None, description="Next scheduled maintenance")
    maintenance_required: bool = Field(..., description="Whether maintenance is required")
    pending_updates: int = Field(..., description="Number of pending updates")
    log_rotation_status: str = Field(..., description="Log rotation status")
    backup_status: str = Field(..., description="Backup status")
    disk_cleanup_needed: bool = Field(..., description="Whether disk cleanup is needed")
    
    class Config:
        schema_extra = {
            "example": {
                "last_maintenance": 1640995200.0,
                "next_scheduled": 1641081600.0,
                "maintenance_required": False,
                "pending_updates": 0,
                "log_rotation_status": "healthy",
                "backup_status": "current",
                "disk_cleanup_needed": False
            }
        }