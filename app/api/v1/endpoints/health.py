"""
Health check API endpoints
"""

from fastapi import APIRouter, Depends, status
from typing import Dict, Any
import time
import psutil
import logging
from pathlib import Path

from app.core.mavlink.connection import MAVLinkManager
from app.services.telemetry_service import TelemetryService
from config.settings import get_settings
from main import get_mavlink_manager, get_telemetry_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    
    Returns basic application health status
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "AgroBot Raspberry Pi Controller",
        "version": "1.0.0"
    }


@router.get("/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager),
    telemetry: TelemetryService = Depends(get_telemetry_service)
) -> Dict[str, Any]:
    """
    Detailed health check with system information
    
    Returns comprehensive health status including:
    - Application status
    - MAVLink connection status
    - Telemetry service status
    - System resources
    - Hardware status
    """
    settings = get_settings()
    
    # Basic application status
    app_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "uptime_seconds": time.time() - psutil.boot_time(),
        "version": "1.0.0"
    }
    
    # MAVLink connection status
    mavlink_status = {
        "connected": mavlink.is_connected(),
        "state": mavlink.state.value,
        "connection_string": settings.MAVLINK_CONNECTION_STRING,
        "last_heartbeat_age": None
    }
    
    if mavlink.latest_heartbeat:
        mavlink_status["last_heartbeat_age"] = time.time() - mavlink.latest_heartbeat.timestamp
        mavlink_status["system_id"] = mavlink.latest_heartbeat.system_id
        mavlink_status["component_id"] = mavlink.latest_heartbeat.component_id
    
    # Telemetry service status
    telemetry_status = {
        "running": telemetry.is_running(),
        "enabled": settings.TELEMETRY_ENABLED,
        "interval": settings.TELEMETRY_INTERVAL
    }
    
    # System resources
    system_status = get_system_status()
    
    # GPS status
    gps_status = {
        "available": mavlink.latest_gps is not None,
        "fix_type": None,
        "satellites": None,
        "hdop": None
    }
    
    if mavlink.latest_gps:
        gps_status.update({
            "fix_type": mavlink.latest_gps.fix_type,
            "satellites": mavlink.latest_gps.satellites_visible,
            "hdop": mavlink.latest_gps.hdop,
            "has_good_fix": mavlink.latest_gps.fix_type >= 3 and mavlink.latest_gps.satellites_visible >= 6
        })
    
    # Overall health determination
    overall_healthy = all([
        system_status["cpu_percent"] < 90,
        system_status["memory_percent"] < 90,
        system_status["disk_percent"] < 90
    ])
    
    return {
        "overall_status": "healthy" if overall_healthy else "degraded",
        "timestamp": time.time(),
        "application": app_status,
        "mavlink": mavlink_status,
        "telemetry": telemetry_status,
        "gps": gps_status,
        "system": system_status,
        "checks": {
            "mavlink_connected": mavlink.is_connected(),
            "telemetry_running": telemetry.is_running(),
            "system_resources_ok": overall_healthy,
            "gps_available": gps_status["available"]
        }
    }


@router.get("/mavlink", status_code=status.HTTP_200_OK)
async def mavlink_health(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager)
) -> Dict[str, Any]:
    """
    MAVLink-specific health check
    
    Returns detailed MAVLink connection and communication status
    """
    if not mavlink.is_connected():
        return {
            "status": "disconnected",
            "connected": False,
            "state": mavlink.state.value,
            "error": "Not connected to Pixhawk"
        }
    
    status_data = mavlink.get_status()
    
    # Check heartbeat age
    heartbeat_healthy = True
    heartbeat_age = None
    if mavlink.latest_heartbeat:
        heartbeat_age = time.time() - mavlink.latest_heartbeat.timestamp
        heartbeat_healthy = heartbeat_age < 5.0  # Consider unhealthy if no heartbeat for 5 seconds
    
    # Check GPS data age
    gps_healthy = True
    gps_age = None
    if mavlink.latest_gps:
        gps_age = time.time() - mavlink.latest_gps.timestamp
        gps_healthy = gps_age < 2.0  # GPS data should be fresh
    
    return {
        "status": "healthy" if heartbeat_healthy and gps_healthy else "degraded",
        "connected": True,
        "state": mavlink.state.value,
        "heartbeat": {
            "available": mavlink.latest_heartbeat is not None,
            "age_seconds": heartbeat_age,
            "healthy": heartbeat_healthy
        },
        "gps": {
            "available": mavlink.latest_gps is not None,
            "age_seconds": gps_age,
            "healthy": gps_healthy
        },
        "communication": {
            "system_id": status_data["system_id"],
            "component_id": status_data["component_id"],
            "connection_string": status_data["connection_string"]
        }
    }


@router.get("/system", status_code=status.HTTP_200_OK)
async def system_health() -> Dict[str, Any]:
    """
    System resource health check
    
    Returns CPU, memory, disk, and temperature information
    """
    system_status = get_system_status()
    
    # Determine overall system health
    healthy = all([
        system_status["cpu_percent"] < 90,
        system_status["memory_percent"] < 90,
        system_status["disk_percent"] < 90,
        system_status["temperature"] < 80 if system_status["temperature"] else True
    ])
    
    return {
        "status": "healthy" if healthy else "degraded",
        "timestamp": time.time(),
        **system_status,
        "thresholds": {
            "cpu_warning": 80,
            "cpu_critical": 90,
            "memory_warning": 80,
            "memory_critical": 90,
            "disk_warning": 80,
            "disk_critical": 90,
            "temperature_warning": 70,
            "temperature_critical": 80
        }
    }


@router.get("/services", status_code=status.HTTP_200_OK)
async def services_health(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager),
    telemetry: TelemetryService = Depends(get_telemetry_service)
) -> Dict[str, Any]:
    """
    Check health of all application services
    """
    services = {
        "mavlink": {
            "status": "running" if mavlink.is_connected() else "stopped",
            "healthy": mavlink.is_connected(),
            "details": mavlink.get_status()
        },
        "telemetry": {
            "status": "running" if telemetry.is_running() else "stopped",
            "healthy": telemetry.is_running(),
            "details": {
                "enabled": get_settings().TELEMETRY_ENABLED,
                "interval": get_settings().TELEMETRY_INTERVAL
            }
        }
    }
    
    all_healthy = all(service["healthy"] for service in services.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": time.time(),
        "services": services,
        "summary": {
            "total_services": len(services),
            "healthy_services": sum(1 for s in services.values() if s["healthy"]),
            "unhealthy_services": sum(1 for s in services.values() if not s["healthy"])
        }
    }


def get_system_status() -> Dict[str, Any]:
    """
    Get system resource status
    
    Returns:
        Dictionary with CPU, memory, disk, and temperature information
    """
    try:
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        
        # Memory information
        memory = psutil.virtual_memory()
        
        # Disk information (root filesystem)
        disk = psutil.disk_usage('/')
        
        # Network information
        network = psutil.net_io_counters()
        
        # Temperature (Raspberry Pi specific)
        temperature = get_cpu_temperature()
        
        # Uptime
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "load_average": load_avg
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": round((disk.used / disk.total) * 100, 1)
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            },
            "temperature": temperature,
            "uptime_seconds": uptime,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "error": str(e),
            "timestamp": time.time()
        }


def get_cpu_temperature() -> float:
    """
    Get CPU temperature (Raspberry Pi specific)
    
    Returns:
        CPU temperature in Celsius, or None if not available
    """
    try:
        # Try multiple temperature sources
        temp_files = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/devices/virtual/thermal/thermal_zone0/temp"
        ]
        
        for temp_file in temp_files:
            temp_path = Path(temp_file)
            if temp_path.exists():
                temp_str = temp_path.read_text().strip()
                # Temperature is usually in millidegrees
                temp_celsius = float(temp_str) / 1000.0
                return round(temp_celsius, 1)
        
        return None
        
    except Exception as e:
        logger.debug(f"Could not read CPU temperature: {e}")
        return None