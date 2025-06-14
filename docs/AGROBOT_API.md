# AgroBot Raspberry Pi Controller API Documentation

This document provides a comprehensive overview of the AgroBot Raspberry Pi Controller's API endpoints, designed for seamless integration with the central AgroBot Backend Server. It outlines available functionalities, required request formats, and expected response structures to enable full control and telemetry exchange.

## Base URL

The base URL for all API endpoints is typically `http://<RASPBERRY_PI_IP_ADDRESS>:8000/api/v1`.
The specific IP address of the Raspberry Pi will be sent to the backend during robot registration.

## Authentication

Currently, API endpoints do not require explicit authentication headers for local network communication. However, for backend communication, an `AGROBOT_API_KEY` can be configured in the `.env` file for secure interactions with the central server.

## Backend Communication (Automatic)

The AgroBot controller automatically communicates with the central backend server to register, send heartbeats, report telemetry, and poll for commands. These processes are managed by the `BackendService` and are initiated automatically upon the controller's startup.

### Robot Registration

Upon startup, the robot attempts to register itself with the backend server. This provides the backend with essential information about the robot's identity, capabilities, and network address for bidirectional communication.

**Endpoint (Backend Server):** `/api/v1/robot/register` (This is the endpoint on the **backend server** that the Raspberry Pi will send a POST request to.)
**Method:** `POST`
**Request Body (sent by Raspberry Pi):** `RegisterRequest`

```json
{
  "robot_id": "string",            // Unique ID of the Raspberry Pi robot (e.g., "agrobot-rpi-001")
  "robot_name": "string",          // Name of the robot (e.g., "AgroBot Raspberry Pi")
  "version": "string",             // Current software version of the controller (e.g., "1.0.0")
  "robot_ip_address": "string",    // Robot's current local IP address (e.g., "192.168.1.100")
  "robot_port": "integer",         // Robot's port (e.g., 8000)
  "capabilities": [                // List of capabilities supported by the robot
    {
      "name": "string",            // Capability name (e.g., "GPS", "Arming", "Movement")
      "supported": "boolean",      // True if supported, False otherwise
      "details": {}                // Optional: specific details about the capability
    }
  ],
  "location": {                    // Optional: Current location of the robot if GPS fix is available
    "latitude": "number",
    "longitude": "number",
    "altitude": "number",
    "timestamp": "string (datetime)"
  },
  "software_version": "string",    // Current software version of the controller
  "metadata": {}                   // Optional: Additional metadata
}
```

**Expected Response (from Backend Server):** `RegisterResponse`

```json
{
  "success": "boolean",            // True if registration was successful
  "message": "string",             // Status message
  "robot_config": {}               // Optional: Backend-provided configuration for the robot
}
```

### Heartbeat

The robot sends periodic heartbeats to the backend to indicate its online status and provide quick health metrics.

**Endpoint (Backend Server):** `/api/v1/robot/heartbeat`
**Method:** `POST`
**Request Body (sent by Raspberry Pi):** `HeartbeatRequest`

```json
{
  "robot_id": "string",            // Unique ID of the robot
  "status": "string",              // Current operational status (e.g., "active", "idle", "error")
  "timestamp": "string (datetime)",// Timestamp of the heartbeat
  "quick_health": {                // Quick overview of system health
    "cpu_percent": "number",       // Current CPU usage (0-100)
    "memory_percent": "number",    // Current memory usage (0-100)
    "disk_percent": "number",      // Current disk usage (0-100)
    "mavlink_connected": "boolean",// True if MAVLink is connected
    "gps_fix": "boolean"           // True if GPS has a fix
  }
}
```

**Expected Response (from Backend Server):** `HeartbeatResponse`

```json
{
  "success": "boolean",            // True if heartbeat was received successfully
  "message": "string",             // Status message
  "commands_pending": "boolean"    // True if there are commands pending for the robot
}
```

### Telemetry Reporting

The robot buffers telemetry data and sends it in batches to the backend.

**Endpoint (Backend Server):** `/api/v1/robot/telemetry`
**Method:** `POST`
**Request Body (sent by Raspberry Pi):** `TelemetryBatchRequest`

```json
{
  "robot_id": "string",            // Unique ID of the robot
  "data": [                        // Array of telemetry data points
    {
      "timestamp": "string (datetime)",
      "gps": {
        "latitude": "number",
        "longitude": "number",
        "altitude": "number"
      },
      "attitude": {
        "roll": "number",
        "pitch": "number",
        "yaw": "number"
      },
      "battery": {
        "voltage": "number",
        "current": "number",
        "level": "number"
      },
      "sensors": {
        "temperature": "number",
        "pressure": "number"
      }
    }
  ]
}
```

**Expected Response (from Backend Server):** `TelemetryBatchResponse`

```json
{
  "success": "boolean",
  "message": "string",
  "records_received": "integer"    // Number of telemetry records successfully processed
}
```

### Command Result Reporting

After executing a command received from the backend, the robot reports the result.

**Endpoint (Backend Server):** `/api/v1/robot/command_result`
**Method:** `POST`
**Request Body (sent by Raspberry Pi):** `CommandResultRequest`

```json
{
  "command_id": "string",          // Unique ID of the command (received from backend)
  "status": "string",              // "completed", "failed", "in_progress"
  "result": {},                    // Optional: JSON object with command-specific results
  "error": "string",               // Optional: Error message if status is "failed"
  "execution_time": "number"       // Optional: Time taken to execute the command in seconds
}
```

**Expected Response (from Backend Server):** `CommandResultResponse`

```json
{
  "success": "boolean",
  "message": "string"
}
```

### Alert Reporting

The robot can send alerts to the backend for critical events (e.g., low battery, connection loss).

**Endpoint (Backend Server):** `/api/v1/robot/alert`
**Method:** `POST`
**Request Body (sent by Raspberry Pi):** `AlertRequest`

```json
{
  "robot_id": "string",
  "severity": "string",            // "info", "warning", "error", "critical"
  "message": "string",             // Short description of the alert
  "timestamp": "string (datetime)",
  "details": {}                    // Optional: Additional details about the alert
}
```

**Expected Response (from Backend Server):** `AlertResponse`

```json
{
  "success": "boolean",
  "message": "string"
}
```

## Backend to Robot Communication (Commands)

The central backend server can send commands to the AgroBot Raspberry Pi controller. These commands are typically polled by the robot at regular intervals.

### Polling for Pending Commands

The robot periodically requests pending commands from the backend.

**Endpoint (Backend Server):** `/api/v1/robot/commands`
**Method:** `GET`
**Query Parameters:**
*   `robot_id`: `string` (Unique ID of the robot)

**Expected Response (from Backend Server):** `PollCommandsResponse`

```json
{
  "success": "boolean",
  "message": "string",
  "commands": [                    // Array of pending commands for the robot
    {
      "command_id": "string",      // Unique ID for this specific command instance
      "command_type": "string",    // Type of command (e.g., "arm", "goto", "set_mode", "create_mission")
      "parameters": {}             // JSON object with command-specific parameters
    }
  ]
}
```

---

## AgroBot Raspberry Pi API Endpoints (For Direct Interaction/Local Testing)

These are the endpoints exposed by the AgroBot Raspberry Pi Controller itself. The backend can also call these endpoints directly if it has the robot's IP address and port.

### Health Check

**Endpoint:** `/health`
**Method:** `GET`
**Description:** Simple endpoint to check the operational status of the controller.
**Response:**

```json
{
  "status": "healthy",
  "mavlink_connected": true,
  "telemetry_active": true,
  "websocket_connections": 1
}
```

### Root Endpoint

**Endpoint:** `/`
**Method:** `GET`
**Description:** Provides basic information about the running application.
**Response:**

```json
{
  "name": "AgroBot Raspberry Pi Controller",
  "version": "1.0.0",
  "description": "FastAPI application for agro robot control",
  "docs": "/docs",
  "health": "/health"
}
```

### System Status

**Endpoint:** `/api/v1/status`
**Method:** `GET`
**Description:** Provides a comprehensive overview of the robot's system health, MAVLink status, GPS, and backend communication status.
**Response:**

```json
{
  "overall_health": "healthy",  // "healthy", "degraded", or "unhealthy"
  "timestamp": "string (datetime)",
  "mavlink": {
    "connected": "boolean",
    "armed": "boolean",
    "mode": "string"            // Current flight mode
  },
  "gps": {
    "fix_type": "integer",      // GPS fix type (0: no fix, 1: no fix, 2: 2D fix, 3: 3D fix, etc.)
    "satellites_visible": "integer",
    "hdop": "number",           // Horizontal Dilution of Precision
    "vdop": "number"            // Vertical Dilution of Precision
  },
  "system": {
    "cpu_percent": "number",    // CPU usage (0-100)
    "memory_percent": "number", // Memory usage (0-100)
    "disk_percent": "number"    // Disk usage (0-100)
  },
  "backend": {
    "registered": "boolean",          // True if registered with backend
    "heartbeat_active": "boolean",    // True if heartbeat task is running
    "telemetry_active": "boolean",    // True if telemetry task is running
    "command_polling_active": "boolean", // True if command polling task is running
    "telemetry_buffer_size": "integer" // Number of telemetry points buffered
  },
  "websocket": {
    "active_connections": "integer",
    "telemetry_active": "boolean"
  }
}
```

### Pixhawk Status

**Endpoint:** `/api/v1/pixhawk/status`
**Method:** `GET`
**Description:** Get the current status of the Pixhawk flight controller.
**Response:**

```json
{
  "armed": "boolean",
  "mode": "string",
  "battery_voltage": "number",
  "ground_speed": "number",
  "heading": "number",
  "last_heartbeat": "float",
  "system_status": "string"
}
```

### Connect to Pixhawk

**Endpoint:** `/api/v1/pixhawk/connect`
**Method:** `POST`
**Description:** Attempt to establish a MAVLink connection to the Pixhawk.
**Response:**

```json
{
  "success": "boolean",
  "message": "string"
}
```

### Arm/Disarm Pixhawk

**Endpoint:** `/api/v1/pixhawk/arm`
**Method:** `POST`
**Description:** Arm or disarm the Pixhawk motors.
**Request Body:**

```json
{
  "arm": "boolean"  // true to arm, false to disarm
}
```
**Response:**

```json
{
  "success": "boolean",
  "armed": "boolean",
  "error": "string" // Optional: error message if failed
}
```

### Set Flight Mode

**Endpoint:** `/api/v1/pixhawk/mode`
**Method:** `POST`
**Description:** Set the flight mode of the Pixhawk.
**Request Body:**

```json
{
  "mode": "string"  // e.g., "GUIDED", "AUTO", "RTL", "LOITER", "LAND", "STABILIZE"
}
```
**Response:**

```json
{
  "success": "boolean",
  "mode": "string",
  "error": "string" // Optional: error message if failed
}
```

### GPS Current Data

**Endpoint:** `/api/v1/gps/current`
**Method:** `GET`
**Description:** Get the current GPS coordinates and altitude.
**Response:**

```json
{
  "latitude": "number",
  "longitude": "number",
  "altitude": "number",
  "ground_speed": "number",
  "heading": "number",
  "timestamp": "string (datetime)"
}
```

### GPS Status

**Endpoint:** `/api/v1/gps/status`
**Method:** `GET`
**Description:** Get detailed GPS fix status.
**Response:**

```json
{
  "fix_type": "integer",
  "satellites_visible": "integer",
  "hdop": "number",
  "vdop": "number",
  "timestamp": "string (datetime)"
}
```

### Movement - Go To

**Endpoint:** `/api/v1/movement/goto`
**Method:** `POST`
**Description:** Command the robot to move to a specific GPS coordinate.
**Request Body:**

```json
{
  "latitude": "number",
  "longitude": "number",
  "altitude": "number"
}
```
**Response:**

```json
{
  "success": "boolean",
  "message": "string",
  "target": {
    "latitude": "number",
    "longitude": "number",
    "altitude": "number"
  },
  "current_position": { // Optional: Current position if movement starts
    "latitude": "number",
    "longitude": "number",
    "altitude": "number"
  },
  "error": "string" // Optional: error message if failed
}
```

### Mission - Create

**Endpoint:** `/api/v1/mission/create`
**Method:** `POST`
**Description:** Create and upload a new mission with a series of waypoints.
**Request Body:**

```json
{
  "name": "string",
  "description": "string (optional)",
  "waypoints": [
    {
      "latitude": "number",
      "longitude": "number",
      "altitude": "number"
    }
  ]
}
```
**Response:**

```json
{
  "success": "boolean",
  "message": "string",
  "mission_name": "string",
  "waypoint_count": "integer",
  "error": "string" // Optional: error message if failed
}
```

### Radio Control Status

**Endpoint:** `/api/v1/radio/status`
**Method:** `GET`
**Description:** Get the current status of radio control inputs.
**Response:**

```json
{
  "connected": "boolean",
  "channels": {
    "channel1": "integer",
    "channel2": "integer"
    // ... up to RC_CHANNELS configured in settings
  },
  "last_update": "string (datetime)"
}
```

### WebSocket for Real-time Telemetry

**Endpoint:** `/ws`
**Method:** `GET` (WebSocket connection)
**Description:** Establish a WebSocket connection to receive real-time telemetry updates.
**Connection URL:** `ws://<RASPBERRY_PI_IP_ADDRESS>:8000/ws`

**Data Format (received by Backend/Client):** Messages are JSON strings containing various telemetry data points.

```json
{
  "type": "telemetry",
  "timestamp": "string (datetime)",
  "gps": {
    "latitude": "number",
    "longitude": "number",
    "altitude": "number",
    "ground_speed": "number",
    "heading": "number",
    "fix_type": "integer",
    "satellites_visible": "integer",
    "hdop": "number",
    "vdop": "number"
  },
  "attitude": {
    "roll": "number",
    "pitch": "number",
    "yaw": "number",
    "rollspeed": "number",
    "pitchspeed": "number",
    "yawspeed": "number"
  },
  "battery": {
    "voltage": "number",
    "current": "number",
    "level": "number"
  },
  "system": {
    "cpu_percent": "number",
    "memory_percent": "number",
    "disk_percent": "number"
  }
}
```
```