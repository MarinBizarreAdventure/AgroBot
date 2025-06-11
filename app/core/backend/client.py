"""
HTTP client for communicating with AgroBot backend
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import httpx
import json

from config.settings import get_settings

logger = logging.getLogger(__name__)


class BackendClient:
    """HTTP client for AgroBot backend communication"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, robot_id: str = "unknown"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.robot_id = robot_id
        self.settings = get_settings()
        
        # Client configuration
        self.timeout = httpx.Timeout(self.settings.BACKEND_TIMEOUT)
        self.retry_attempts = self.settings.BACKEND_RETRY_ATTEMPTS
        
        # Connection tracking
        self.last_sync_time: Optional[float] = None
        self.connection_errors = 0
        self.total_requests = 0
        self.successful_requests = 0
        
        # Create HTTP client
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            headers = {
                "User-Agent": f"AgroBot-RPI/{self.settings.VERSION}",
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout
            )
        
        return self._client
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        client = await self._get_client()
        url = f"{endpoint}"
        
        for attempt in range(self.retry_attempts + 1):
            try:
                self.total_requests += 1
                
                if method.upper() == "GET":
                    response = await client.get(url, params=data)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Check response status
                if response.status_code == 200:
                    self.successful_requests += 1
                    self.connection_errors = 0
                    return response.json()
                elif response.status_code == 401:
                    raise Exception("Authentication failed - check API key")
                elif response.status_code == 404:
                    raise Exception(f"Endpoint not found: {endpoint}")
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
            except httpx.RequestError as e:
                self.connection_errors += 1
                logger.warning(f"Request error (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Request failed after {self.retry_attempts + 1} attempts: {e}")
            
            except Exception as e:
                self.connection_errors += 1
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to backend"""
        try:
            response = await self._make_request("GET", "/api/health")
            return {
                "success": True,
                "status": "connected",
                "api_version": response.get("version", "unknown"),
                "response_time": response.get("response_time", 0)
            }
        except Exception as e:
            logger.error(f"Backend connection test failed: {e}")
            return {
                "success": False,
                "status": "disconnected",
                "error": str(e)
            }
    
    async def test_authentication(self) -> Dict[str, Any]:
        """Test API authentication"""
        try:
            response = await self._make_request("GET", "/api/auth/verify")
            return {
                "success": True,
                "authenticated": True,
                "robot_id": response.get("robot_id"),
                "permissions": response.get("permissions", [])
            }
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return {
                "success": False,
                "authenticated": False,
                "error": str(e)
            }
    
    async def test_api_endpoints(self) -> Dict[str, Any]:
        """Test availability of key API endpoints"""
        endpoints_to_test = [
            "/api/robots",
            "/api/telemetry",
            "/api/commands",
            "/api/missions"
        ]
        
        results = {}
        for endpoint in endpoints_to_test:
            try:
                await self._make_request("GET", endpoint)
                results[endpoint] = {"available": True}
            except Exception as e:
                results[endpoint] = {"available": False, "error": str(e)}
        
        all_available = all(result["available"] for result in results.values())
        
        return {
            "success": all_available,
            "endpoints": results
        }
    
    async def test_data_upload(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test data upload functionality"""
        try:
            response = await self._make_request("POST", "/api/test/upload", test_data)
            return {
                "success": True,
                "uploaded": True,
                "response": response
            }
        except Exception as e:
            logger.error(f"Data upload test failed: {e}")
            return {
                "success": False,
                "uploaded": False,
                "error": str(e)
            }
    
    async def sync_data(self, sync_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize data with backend"""
        try:
            payload = {
                "robot_id": self.robot_id,
                "timestamp": time.time(),
                "data": sync_data
            }
            
            response = await self._make_request("POST", "/api/robots/sync", payload)
            self.last_sync_time = time.time()
            
            return {
                "success": True,
                "message": "Sync completed successfully",
                "commands": response.get("commands", []),
                "next_sync": response.get("next_sync")
            }
            
        except Exception as e:
            logger.error(f"Data sync failed: {e}")
            return {
                "success": False,
                "message": f"Sync failed: {str(e)}",
                "commands": []
            }
    
    async def update_robot_status(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update robot status in backend"""
        try:
            response = await self._make_request("PUT", f"/api/robots/{self.robot_id}/status", status_data)
            return {
                "success": True,
                "message": "Status updated successfully",
                "response": response
            }
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            return {
                "success": False,
                "message": f"Status update failed: {str(e)}"
            }
    
    async def upload_telemetry(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upload telemetry data to backend"""
        try:
            response = await self._make_request("POST", "/api/telemetry", telemetry_data)
            return {
                "success": True,
                "message": "Telemetry uploaded successfully",
                "records_processed": response.get("records_processed", 0)
            }
        except Exception as e:
            logger.error(f"Telemetry upload failed: {e}")
            return {
                "success": False,
                "message": f"Telemetry upload failed: {str(e)}"
            }
    
    async def get_pending_commands(self) -> List[Dict[str, Any]]:
        """Get pending commands from backend"""
        try:
            response = await self._make_request("GET", f"/api/robots/{self.robot_id}/commands/pending")
            return response.get("commands", [])
        except Exception as e:
            logger.error(f"Failed to get pending commands: {e}")
            return []
    
    async def acknowledge_command(self, command_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Acknowledge command execution result"""
        try:
            payload = {
                "robot_id": self.robot_id,
                "command_id": command_id,
                "result": result_data,
                "timestamp": time.time()
            }
            
            response = await self._make_request("POST", f"/api/commands/{command_id}/acknowledge", payload)
            return {
                "success": True,
                "message": "Command acknowledged successfully"
            }
        except Exception as e:
            logger.error(f"Command acknowledgment failed: {e}")
            return {
                "success": False,
                "message": f"Command acknowledgment failed: {str(e)}"
            }
    
    async def send_heartbeat(self, heartbeat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send heartbeat to backend"""
        try:
            response = await self._make_request("POST", f"/api/robots/{self.robot_id}/heartbeat", heartbeat_data)
            return {
                "success": True,
                "message": "Heartbeat sent successfully",
                "server_time": response.get("server_time")
            }
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return {
                "success": False,
                "message": f"Heartbeat failed: {str(e)}"
            }
    
    async def upload_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upload log entries to backend"""
        try:
            payload = {
                "robot_id": self.robot_id,
                "logs": logs,
                "timestamp": time.time()
            }
            
            response = await self._make_request("POST", "/api/logs", payload)
            return {
                "success": True,
                "message": "Logs uploaded successfully",
                "entries_processed": response.get("entries_processed", 0)
            }
        except Exception as e:
            logger.error(f"Log upload failed: {e}")
            return {
                "success": False,
                "message": f"Log upload failed: {str(e)}"
            }
    
    async def confirm_config_update(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Confirm configuration update with backend"""
        try:
            payload = {
                "robot_id": self.robot_id,
                "config": config_data,
                "timestamp": time.time(),
                "status": "applied"
            }
            
            response = await self._make_request("POST", f"/api/robots/{self.robot_id}/config/confirm", payload)
            return {
                "success": True,
                "message": "Configuration update confirmed"
            }
        except Exception as e:
            logger.error(f"Config confirmation failed: {e}")
            return {
                "success": False,
                "message": f"Config confirmation failed: {str(e)}"
            }
    
    async def get_robot_info(self) -> Dict[str, Any]:
        """Get robot information from backend"""
        try:
            response = await self._make_request("GET", f"/api/robots/{self.robot_id}")
            return {
                "success": True,
                "robot_info": response
            }
        except Exception as e:
            logger.error(f"Failed to get robot info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def register_robot(self, robot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register robot with backend"""
        try:
            response = await self._make_request("POST", "/api/robots/register", robot_data)
            return {
                "success": True,
                "message": "Robot registered successfully",
                "robot_id": response.get("robot_id"),
                "api_key": response.get("api_key")
            }
        except Exception as e:
            logger.error(f"Robot registration failed: {e}")
            return {
                "success": False,
                "message": f"Robot registration failed: {str(e)}"
            }
    
    async def get_missions(self) -> Dict[str, Any]:
        """Get available missions from backend"""
        try:
            response = await self._make_request("GET", f"/api/robots/{self.robot_id}/missions")
            return {
                "success": True,
                "missions": response.get("missions", [])
            }
        except Exception as e:
            logger.error(f"Failed to get missions: {e}")
            return {
                "success": False,
                "missions": [],
                "error": str(e)
            }
    
    async def update_mission_status(self, mission_id: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update mission execution status"""
        try:
            payload = {
                "robot_id": self.robot_id,
                "mission_id": mission_id,
                "status": status_data,
                "timestamp": time.time()
            }
            
            response = await self._make_request("PUT", f"/api/missions/{mission_id}/status", payload)
            return {
                "success": True,
                "message": "Mission status updated successfully"
            }
        except Exception as e:
            logger.error(f"Mission status update failed: {e}")
            return {
                "success": False,
                "message": f"Mission status update failed: {str(e)}"
            }
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Get robot configuration from backend"""
        try:
            response = await self._make_request("GET", f"/api/robots/{self.robot_id}/config")
            return {
                "success": True,
                "configuration": response.get("configuration", {})
            }
        except Exception as e:
            logger.error(f"Failed to get configuration: {e}")
            return {
                "success": False,
                "configuration": {},
                "error": str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics"""
        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.total_requests - self.successful_requests,
            "success_rate": success_rate,
            "connection_errors": self.connection_errors,
            "last_sync_time": self.last_sync_time,
            "base_url": self.base_url,
            "robot_id": self.robot_id
        }


class BackendClientManager:
    """Manager for backend client lifecycle"""
    
    def __init__(self):
        self.client: Optional[BackendClient] = None
        self.auto_sync_task: Optional[asyncio.Task] = None
        self.settings = get_settings()
    
    async def initialize(self):
        """Initialize backend client"""
        self.client = BackendClient(
            base_url=self.settings.AGROBOT_BACKEND_URL,
            api_key=self.settings.AGROBOT_API_KEY,
            robot_id=self.settings.ROBOT_ID
        )
        
        # Test initial connection
        test_result = await self.client.test_connection()
        if test_result["success"]:
            logger.info("Backend client initialized successfully")
            # Start auto-sync if enabled
            if self.settings.BACKEND_SYNC_INTERVAL > 0:
                self.auto_sync_task = asyncio.create_task(self._auto_sync_loop())
        else:
            logger.warning(f"Backend connection test failed: {test_result.get('error')}")
    
    async def shutdown(self):
        """Shutdown backend client"""
        if self.auto_sync_task:
            self.auto_sync_task.cancel()
            try:
                await self.auto_sync_task
            except asyncio.CancelledError:
                pass
        
        if self.client:
            await self.client.close()
            self.client = None
        
        logger.info("Backend client shutdown complete")
    
    async def _auto_sync_loop(self):
        """Automatic sync loop"""
        logger.info(f"Starting auto-sync with {self.settings.BACKEND_SYNC_INTERVAL}s interval")
        
        while True:
            try:
                await asyncio.sleep(self.settings.BACKEND_SYNC_INTERVAL)
                
                if self.client:
                    # Perform automatic sync
                    sync_data = {
                        "timestamp": time.time(),
                        "auto_sync": True
                    }
                    
                    result = await self.client.sync_data(sync_data)
                    if result["success"]:
                        logger.debug("Auto-sync completed successfully")
                    else:
                        logger.warning(f"Auto-sync failed: {result['message']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-sync loop: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    def get_client(self) -> Optional[BackendClient]:
        """Get backend client instance"""
        return self.client