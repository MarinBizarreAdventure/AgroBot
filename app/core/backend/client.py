"""
BackendClient for communicating with the central AgroBot Backend Server.
"""

import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
import socket
import ipaddress

from app.models.backend import (
    RegisterRequest, RegisterResponse,
    HeartbeatRequest, HeartbeatResponse,
    PendingCommandsResponse, CommandResultRequest, CommandResultResponse,
    TelemetryBatchRequest, TelemetryBatchResponse,
    AlertRequest, AlertResponse
)
from config.settings import get_settings

logger = logging.getLogger(__name__)

class BackendClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=get_settings().BACKEND_TIMEOUT)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _post(self, endpoint: str, data: Dict[str, Any], response_model: Any):
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self.client.post(url, json=data, headers=self.headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            return response_model.parse_obj(response.json())
        except httpx.RequestError as exc:
            logger.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during POST to {url}: {e}")
            return None

    async def _get(self, endpoint: str, response_model: Any):
        url = f"{self.base_url}{endpoint}"
        try:
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            return response_model.parse_obj(response.json())
        except httpx.RequestError as exc:
            logger.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during GET to {url}: {e}")
            return None

    async def register_robot(self, request_data: RegisterRequest) -> Optional[RegisterResponse]:
        logger.info("Attempting to register robot...")
        response = await self._post("/api/v1/backend/register", request_data.dict(), RegisterResponse)
        if response and response.success:
            logger.info(f"Robot {request_data.robot_id} registered successfully.")
        else:
            logger.error(f"Robot registration failed: {response.message if response else 'No response'}")
        return response

    async def send_heartbeat(self, request_data: HeartbeatRequest) -> Optional[HeartbeatResponse]:
        logger.debug(f"Sending heartbeat for {request_data.robot_id}...")
        return await self._post("/api/v1/backend/heartbeat", request_data.dict(), HeartbeatResponse)

    async def poll_pending_commands(self) -> Optional[PendingCommandsResponse]:
        logger.debug("Polling for pending commands...")
        return await self._get("/api/v1/backend/commands/pending", PendingCommandsResponse)

    async def report_command_result(self, request_data: CommandResultRequest) -> Optional[CommandResultResponse]:
        logger.info(f"Reporting command {request_data.command_id} result: {request_data.status}")
        return await self._post(f"/api/v1/backend/commands/{request_data.command_id}/result", request_data.dict(), CommandResultResponse)

    async def send_telemetry_batch(self, request_data: TelemetryBatchRequest) -> Optional[TelemetryBatchResponse]:
        logger.debug(f"Sending telemetry batch for {request_data.robot_id} with {len(request_data.data)} points.")
        return await self._post("/api/v1/backend/telemetry/batch", request_data.dict(), TelemetryBatchResponse)

    async def send_alert(self, request_data: AlertRequest) -> Optional[AlertResponse]:
        logger.warning(f"Sending alert: {request_data.message}")
        return await self._post("/api/v1/backend/alerts", request_data.dict(), AlertResponse)

    async def close(self):
        await self.client.aclose()
        logger.info("BackendClient closed.")

    async def scan_for_backend(self, port: int = 5000, timeout: float = 0.5) -> Optional[str]:
        """Scans the local network for an active backend server on a given port.
        Prioritizes common local network ranges.
        """
        logger.info(f"Scanning local network for backend on port {port}...")
        
        # Get local IP address to determine the network range
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            network = ipaddress.ip_network(f'{local_ip}/24', strict=False)
            target_ips = [str(ip) for ip in network.hosts()]
            logger.debug(f"Scanning network {network} for backend.")
        except Exception as e:
            logger.warning(f"Could not determine local network: {e}. Falling back to common ranges.")
            target_ips = []

        # Add common private IP ranges if not already in target_ips or if network detection failed
        common_ranges = [
            "192.168.1.0/24",
            "192.168.0.0/24",
            "10.0.0.0/24",
            "172.16.0.0/24"
        ]
        for cidr in common_ranges:
            for ip in ipaddress.ip_network(cidr).hosts():
                if str(ip) not in target_ips:
                    target_ips.append(str(ip))

        # Add localhost as a prime candidate
        if "127.0.0.1" not in target_ips:
            target_ips.insert(0, "127.0.0.1")

        # Create tasks for parallel scanning
        async def check_host(ip: str):
            url = f"http://{ip}:{port}"
            try:
                # Attempt a simple GET request to the root or a health endpoint
                # This is more robust than just checking if the socket is open
                # and verifies it's a web server (likely Flask/FastAPI)
                response = await httpx.get(url, timeout=timeout)
                if response.status_code == 200:
                    logger.info(f"Backend found at {url}")
                    return url
            except httpx.ConnectError:
                pass # Host unreachable
            except httpx.TimeoutException:
                pass # Connection timed out
            except Exception as e:
                logger.debug(f"Error checking {url}: {e}")
            return None

        # Run checks concurrently
        tasks = [check_host(ip) for ip in target_ips]
        for task in asyncio.as_completed(tasks):
            found_url = await task
            if found_url:
                for t in tasks: t.cancel() # Cancel remaining tasks once found
                return found_url
        
        logger.warning(f"No backend found on port {port} in local network scan.")
        return None

# Example usage (for testing, not for production integration)
async def main_client_test():
    # Make sure your .env has BACKEND_URL and BACKEND_API_KEY
    # For testing, you might need a mock backend server or a real one running
    # from config.settings import settings
    # client = BackendClient(base_url=settings.BACKEND_URL, api_key=settings.BACKEND_API_KEY)
    
    # Dummy data for testing
    test_client = BackendClient(base_url="http://localhost:8000", api_key="test_api_key")
    
    # Test Registration
    from app.models.backend import HardwareInfo, Capability, Location
    register_req = RegisterRequest(
        robot_id="agrobot-rpi-test-001",
        hardware_info=HardwareInfo(cpu_model="Test CPU", ram_gb=2.0, disk_gb=16.0),
        capabilities=[
            Capability(name="GPS", supported=True),
            Capability(name="Arming", supported=True)
        ],
        location=Location(latitude=1.0, longitude=2.0),
        software_version="test-0.1.0"
    )
    reg_resp = await test_client.register_robot(register_req)
    print(f"Register Response: {reg_resp}")

    # Test Heartbeat
    from app.models.backend import QuickHealth
    heartbeat_req = HeartbeatRequest(
        robot_id="agrobot-rpi-test-001",
        status="active",
        quick_health=QuickHealth(cpu_percent=10.5, memory_percent=20.0, disk_percent=50.0, mavlink_connected=True, gps_fix=True)
    )
    hb_resp = await test_client.send_heartbeat(heartbeat_req)
    print(f"Heartbeat Response: {hb_resp}")
    
    await test_client.close()

if __name__ == "__main__":
    # To run this test, you'd need a mock backend server or a real one
    # logging.basicConfig(level=logging.INFO)
    # asyncio.run(main_client_test())
    pass