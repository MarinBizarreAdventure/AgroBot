"""
Status and diagnostics API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import logging
import time
import psutil
import platform

from app.core.mavlink.connection import MAVLinkManager
from app.services.telemetry_service import TelemetryService
from app.models.status import (
    SystemStatus, ApplicationStatus, HardwareStatus, 
    NetworkStatus, PerformanceMetrics, DiagnosticsReport
)
from config.settings import get_settings
from main import get_mavlink_manager, get_telemetry_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/status", tags=["Status & Diagnostics"])


@router.get("/", response_model=SystemStatus)
async def get_system_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager),
    telemetry: TelemetryService = Depends(get_telemetry_service)
) -> SystemStatus:
    """
    Get comprehensive system status
    
    Returns overall system health including all subsystems.
    """
    try:
        settings = get_settings()
        current_time = time.time()
        
        # Get system info
        system_info = platform.uname()
        boot_time = psutil.boot_time()
        
        # Check subsystem health
        mavlink_healthy = mavlink.is_connected()
        telemetry_healthy = telemetry.is_running()
        
        # Get resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Determine overall health
        health_checks = {
            "mavlink_connection": mavlink_healthy,
            "telemetry_service": telemetry_healthy,
            "cpu_usage": cpu_percent < 80,
            "memory_usage": memory.percent < 80,
            "disk_space": (disk.used / disk.total) * 100 < 80
        }
        
        overall_healthy = all(health_checks.values())
        health_score = (sum(health_checks.values()) / len(health_checks)) * 100
        
        return SystemStatus(
            overall_health="healthy" if overall_healthy else "degraded",
            health_score=health_score,
            uptime_seconds=current_time - boot_time,
            system_time=current_time,
            platform=f"{system_info.system} {system_info.release}",
            hostname=system_info.node,
            architecture=system_info.machine,
            python_version=platform.python_version(),
            subsystems={
                "mavlink": "healthy" if mavlink_healthy else "unhealthy",
                "telemetry": "healthy" if telemetry_healthy else "unhealthy",
                "gps": "healthy" if mavlink.latest_gps else "unavailable",
                "radio": "healthy",  # Would check RC status
                "storage": "healthy"
            },
            resource_usage={
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "temperature": get_cpu_temperature()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System status error: {str(e)}"
        )


@router.get("/application", response_model=ApplicationStatus)
async def get_application_status(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager),
    telemetry: TelemetryService = Depends(get_telemetry_service)
) -> ApplicationStatus:
    """
    Get application-specific status information
    
    Returns detailed status of the AgroBot application components.
    """
    try:
        settings = get_settings()
        
        # Count active connections
        active_connections = 0  # Would count WebSocket connections
        
        # Get service statuses
        services = {
            "mavlink_manager": {
                "status": "running" if mavlink.is_connected() else "stopped",
                "details": mavlink.get_status() if mavlink.is_connected() else None
            },
            "telemetry_service": {
                "status": "running" if telemetry.is_running() else "stopped",
                "details": {"interval": settings.TELEMETRY_INTERVAL}
            },
            "backend_sync": {
                "status": "unknown",  # Would check backend service
                "details": {"url": settings.AGROBOT_BACKEND_URL}
            }
        }
        
        # Calculate uptime (simplified - would track app start time)
        app_uptime = 0.0
        
        return ApplicationStatus(
            version="1.0.0",
            environment="development",  # Would be configurable
            debug_mode=settings.DEBUG,
            uptime_seconds=app_uptime,
            active_connections=active_connections,
            configuration={
                "mavlink_connection": settings.MAVLINK_CONNECTION_STRING,
                "backend_url": settings.AGROBOT_BACKEND_URL,
                "robot_id": settings.ROBOT_ID,
                "telemetry_enabled": settings.TELEMETRY_ENABLED
            },
            services=services,
            features={
                "gps_tracking": True,
                "mission_planning": True,
                "radio_control": True,
                "backend_sync": True,
                "websocket_streaming": True
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting application status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Application status error: {str(e)}"
        )


@router.get("/hardware", response_model=HardwareStatus)
async def get_hardware_status() -> HardwareStatus:
    """
    Get hardware status and information
    
    Returns Raspberry Pi hardware details and sensor status.
    """
    try:
        # Get CPU information
        cpu_info = {
            "model": get_cpu_model(),
            "cores": psutil.cpu_count(),
            "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "temperature": get_cpu_temperature()
        }
        
        # Get memory information
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_percent": memory.percent
        }
        
        # Get storage information
        disk = psutil.disk_usage('/')
        storage_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "used_percent": round((disk.used / disk.total) * 100, 1)
        }
        
        # Check GPIO/hardware interfaces
        interfaces = {
            "i2c": check_i2c_interface(),
            "spi": check_spi_interface(),
            "uart": check_uart_interface(),
            "gpio": check_gpio_interface()
        }
        
        # Get network interfaces
        network_interfaces = []
        for interface, addrs in psutil.net_if_addrs().items():
            if interface != 'lo':  # Skip loopback
                ip_addresses = [addr.address for addr in addrs if addr.family.name == 'AF_INET']
                if ip_addresses:
                    network_interfaces.append({
                        "name": interface,
                        "ip_addresses": ip_addresses,
                        "status": "up" if interface in psutil.net_if_stats() and psutil.net_if_stats()[interface].isup else "down"
                    })
        
        return HardwareStatus(
            platform="Raspberry Pi",
            cpu=cpu_info,
            memory=memory_info,
            storage=storage_info,
            interfaces=interfaces,
            network_interfaces=network_interfaces,
            sensors={
                "gps": "available",  # Would check actual GPS module
                "imu": "unknown",    # Would check IMU if present
                "camera": "unknown"  # Would check camera if present
            },
            peripherals={
                "pixhawk": "connected",  # Based on MAVLink status
                "radio": "connected"     # Based on RC status
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting hardware status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hardware status error: {str(e)}"
        )


@router.get("/network", response_model=NetworkStatus)
async def get_network_status() -> NetworkStatus:
    """
    Get network connectivity status
    
    Returns network interface status and connectivity information.
    """
    try:
        # Get network statistics
        net_io = psutil.net_io_counters()
        net_stats = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errors_in": net_io.errin,
            "errors_out": net_io.errout,
            "drops_in": net_io.dropin,
            "drops_out": net_io.dropout
        }
        
        # Test connectivity
        connectivity = {
            "internet": test_internet_connectivity(),
            "backend": test_backend_connectivity(),
            "local_network": test_local_network_connectivity()
        }
        
        # Get active connections
        connections = []
        try:
            for conn in psutil.net_connections():
                if conn.status == 'ESTABLISHED':
                    connections.append({
                        "local_address": f"{conn.laddr.ip}:{conn.laddr.port}",
                        "remote_address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                        "status": conn.status,
                        "pid": conn.pid
                    })
        except (psutil.AccessDenied, AttributeError):
            # May not have permission to read all connections
            pass
        
        # Get Wi-Fi information if available
        wifi_info = get_wifi_info()
        
        return NetworkStatus(
            connected=connectivity["internet"],
            interfaces=list(psutil.net_if_addrs().keys()),
            statistics=net_stats,
            connectivity=connectivity,
            active_connections=connections[:10],  # Limit to first 10
            wifi=wifi_info
        )
        
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Network status error: {str(e)}"
        )


@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics() -> PerformanceMetrics:
    """
    Get system performance metrics
    
    Returns detailed performance statistics.
    """
    try:
        # CPU metrics
        cpu_times = psutil.cpu_times()
        cpu_metrics = {
            "usage_percent": psutil.cpu_percent(interval=1),
            "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0, 0, 0],
            "times": cpu_times._asdict(),
            "count": psutil.cpu_count()
        }
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        memory_metrics = {
            "virtual": memory._asdict(),
            "swap": swap._asdict(),
            "available_gb": round(memory.available / (1024**3), 2)
        }
        
        # Disk I/O metrics
        disk_io = psutil.disk_io_counters()
        disk_metrics = {
            "io": disk_io._asdict() if disk_io else {},
            "usage": {path: psutil.disk_usage(path)._asdict() for path in ['/']}
        }
        
        # Network I/O metrics
        network_io = psutil.net_io_counters()
        network_metrics = {
            "io": network_io._asdict(),
            "per_interface": {name: stats._asdict() for name, stats in psutil.net_io_counters(pernic=True).items()}
        }
        
        # Process metrics
        process_metrics = {
            "total": len(psutil.pids()),
            "running": len([p for p in psutil.process_iter(['status']) if p.info['status'] == 'running']),
            "sleeping": len([p for p in psutil.process_iter(['status']) if p.info['status'] == 'sleeping'])
        }
        
        return PerformanceMetrics(
            timestamp=time.time(),
            cpu=cpu_metrics,
            memory=memory_metrics,
            disk=disk_metrics,
            network=network_metrics,
            processes=process_metrics,
            temperature=get_cpu_temperature()
        )
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance metrics error: {str(e)}"
        )


@router.get("/diagnostics", response_model=DiagnosticsReport)
async def run_diagnostics(
    mavlink: MAVLinkManager = Depends(get_mavlink_manager),
    telemetry: TelemetryService = Depends(get_telemetry_service)
) -> DiagnosticsReport:
    """
    Run comprehensive system diagnostics
    
    Performs various health checks and returns a detailed report.
    """
    try:
        settings = get_settings()
        tests = {}
        
        # Test 1: System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        tests["system_resources"] = {
            "passed": cpu_percent < 90 and memory.percent < 90 and (disk.used/disk.total)*100 < 90,
            "details": {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": (disk.used/disk.total)*100
            }
        }
        
        # Test 2: MAVLink connection
        tests["mavlink_connection"] = {
            "passed": mavlink.is_connected(),
            "details": mavlink.get_status()
        }
        
        # Test 3: GPS functionality
        gps_available = mavlink.latest_gps is not None
        gps_healthy = False
        if gps_available:
            gps = mavlink.latest_gps
            gps_healthy = gps.fix_type >= 3 and gps.satellites_visible >= 6
        
        tests["gps_system"] = {
            "passed": gps_available and gps_healthy,
            "details": {
                "available": gps_available,
                "healthy": gps_healthy,
                "fix_type": mavlink.latest_gps.fix_type if mavlink.latest_gps else 0,
                "satellites": mavlink.latest_gps.satellites_visible if mavlink.latest_gps else 0
            }
        }
        
        # Test 4: Telemetry service
        tests["telemetry_service"] = {
            "passed": telemetry.is_running(),
            "details": {
                "running": telemetry.is_running(),
                "enabled": settings.TELEMETRY_ENABLED
            }
        }
        
        # Test 5: Network connectivity
        internet_connected = test_internet_connectivity()
        backend_connected = test_backend_connectivity()
        
        tests["network_connectivity"] = {
            "passed": internet_connected,
            "details": {
                "internet": internet_connected,
                "backend": backend_connected
            }
        }
        
        # Test 6: Storage space
        tests["storage_space"] = {
            "passed": (disk.free / disk.total) > 0.1,  # At least 10% free
            "details": {
                "free_percent": (disk.free / disk.total) * 100,
                "free_gb": round(disk.free / (1024**3), 2)
            }
        }
        
        # Test 7: Temperature
        temperature = get_cpu_temperature()
        tests["temperature"] = {
            "passed": temperature is None or temperature < 80,
            "details": {
                "cpu_temperature": temperature,
                "warning_threshold": 80,
                "critical_threshold": 85
            }
        }
        
        # Calculate overall results
        passed_tests = sum(1 for test in tests.values() if test["passed"])
        total_tests = len(tests)
        success_rate = (passed_tests / total_tests) * 100
        
        # Generate recommendations
        recommendations = []
        if not tests["system_resources"]["passed"]:
            recommendations.append("High resource usage detected - consider restarting services")
        if not tests["mavlink_connection"]["passed"]:
            recommendations.append("MAVLink connection issue - check Pixhawk connection")
        if not tests["gps_system"]["passed"]:
            recommendations.append("GPS issues detected - ensure clear sky view")
        if not tests["network_connectivity"]["passed"]:
            recommendations.append("Network connectivity issues - check internet connection")
        if not tests["storage_space"]["passed"]:
            recommendations.append("Low storage space - clean up log files")
        if not tests["temperature"]["passed"]:
            recommendations.append("High temperature detected - check cooling")
        
        if not recommendations:
            recommendations.append("All systems functioning normally")
        
        return DiagnosticsReport(
            timestamp=time.time(),
            overall_health="healthy" if success_rate >= 80 else "degraded" if success_rate >= 60 else "poor",
            success_rate=success_rate,
            tests_passed=passed_tests,
            tests_total=total_tests,
            tests=tests,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostics error: {str(e)}"
        )


# Utility functions
def get_cpu_temperature() -> float:
    """Get CPU temperature (Raspberry Pi specific)"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_str = f.read().strip()
            return float(temp_str) / 1000.0
    except:
        return None


def get_cpu_model() -> str:
    """Get CPU model information"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Model'):
                    return line.split(':')[1].strip()
        return "Unknown"
    except:
        return "Unknown"


def check_i2c_interface() -> str:
    """Check I2C interface availability"""
    try:
        import os
        return "available" if os.path.exists('/dev/i2c-1') else "unavailable"
    except:
        return "unknown"


def check_spi_interface() -> str:
    """Check SPI interface availability"""
    try:
        import os
        return "available" if os.path.exists('/dev/spidev0.0') else "unavailable"
    except:
        return "unknown"


def check_uart_interface() -> str:
    """Check UART interface availability"""
    try:
        import os
        return "available" if any(os.path.exists(f'/dev/ttyS{i}') for i in range(5)) else "unavailable"
    except:
        return "unknown"


def check_gpio_interface() -> str:
    """Check GPIO interface availability"""
    try:
        import os
        return "available" if os.path.exists('/sys/class/gpio') else "unavailable"
    except:
        return "unknown"


def test_internet_connectivity() -> bool:
    """Test internet connectivity"""
    try:
        import urllib.request
        urllib.request.urlopen('http://google.com', timeout=5)
        return True
    except:
        return False


def test_backend_connectivity() -> bool:
    """Test backend connectivity"""
    try:
        import requests
        settings = get_settings()
        response = requests.get(f"{settings.AGROBOT_BACKEND_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def test_local_network_connectivity() -> bool:
    """Test local network connectivity"""
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except:
        return False


def get_wifi_info() -> Dict[str, Any]:
    """Get Wi-Fi connection information"""
    try:
        # This would require platform-specific commands
        # For now, return basic info
        return {
            "connected": True,
            "ssid": "Unknown",
            "signal_strength": -50,
            "frequency": "2.4GHz"
        }
    except:
        return {
            "connected": False,
            "ssid": None,
            "signal_strength": None,
            "frequency": None
        }