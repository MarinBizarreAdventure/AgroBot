# AgroBot Raspberry Pi API Documentation

## Overview
The AgroBot Raspberry Pi API provides a RESTful interface for controlling and monitoring the agro bot system. It uses FastAPI and provides Swagger documentation at `/docs`.

## Base URL
```
http://<raspberry-pi-ip>:8000/api/v1
```

## Authentication
Currently, the API does not require authentication. Future versions will implement JWT-based authentication.

## Endpoints

### Pixhawk Control
#### GET /pixhawk/status
Get current Pixhawk flight controller status.

**Response:**
```json
{
    "connected": true,
    "state": "connected",
    "system_id": 1,
    "component_id": 1,
    "heartbeat_age": 0.5,
    "heartbeat": {
        "timestamp": 1234567890.123,
        "system_id": 1,
        "component_id": 1,
        "type": 1,
        "autopilot": 12,
        "base_mode": 129,
        "custom_mode": 4,
        "system_status": 3,
        "mavlink_version": 3
    },
    "gps": {
        "timestamp": 1234567890.123,
        "lat": 1234567890,
        "lon": 1234567890,
        "alt": 1000,
        "relative_alt": 1000,
        "hdop": 1.5,
        "vdop": 1.5,
        "vel": 100,
        "cog": 18000,
        "satellites_visible": 8,
        "fix_type": 3
    },
    "attitude": {
        "timestamp": 1234567890.123,
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": 0.0,
        "rollspeed": 0.0,
        "pitchspeed": 0.0,
        "yawspeed": 0.0
    }
}
```

#### POST /pixhawk/connect
Establish connection to Pixhawk.

**Response:**
```json
{
    "success": true,
    "message": "Successfully connected to Pixhawk",
    "data": {
        "state": "connected"
    }
}
```

#### POST /pixhawk/arm
Arm the motors.

**Request:**
```json
{
    "arm": true,
    "force_arm": false
}
```

**Response:**
```json
{
    "success": true,
    "message": "Successfully armed motors",
    "data": {
        "armed": true
    }
}
```

### Movement Control
#### POST /movement/goto
Move to specific GPS coordinates.

**Request:**
```json
{
    "latitude": 45.123456,
    "longitude": -122.123456,
    "altitude": 10.0,
    "acceptance_radius": 2.0,
    "max_speed": 2.0,
    "force": false
}
```

**Response:**
```json
{
    "success": true,
    "message": "Moving to position (45.123456, -122.123456)",
    "target_latitude": 45.123456,
    "target_longitude": -122.123456,
    "target_altitude": 10.0,
    "distance_to_target": 15.5,
    "estimated_time_seconds": 7.75,
    "max_speed": 2.0
}
```

### Mission Planning
#### POST /mission/create
Create a new mission with waypoints.

**Request:**
```json
{
    "name": "Test Mission",
    "description": "Test mission with multiple waypoints",
    "waypoints": [
        {
            "latitude": 45.123456,
            "longitude": -122.123456,
            "altitude": 10.0
        },
        {
            "latitude": 45.123789,
            "longitude": -122.123789,
            "altitude": 10.0
        }
    ],
    "default_speed": 2.0,
    "auto_continue": true,
    "return_to_launch": true
}
```

**Response:**
```json
{
    "success": true,
    "message": "Mission 'Test Mission' created successfully",
    "mission_id": "mission_1_1234567890",
    "waypoint_count": 2,
    "total_distance_meters": 15.5,
    "estimated_duration_seconds": 7.75,
    "mission_data": {
        "id": "mission_1_1234567890",
        "name": "Test Mission",
        "description": "Test mission with multiple waypoints",
        "waypoints": [...],
        "default_speed": 2.0,
        "auto_continue": true,
        "return_to_launch": true,
        "total_distance": 15.5,
        "estimated_time": 7.75,
        "created_at": 1234567890.123,
        "status": "created"
    }
}
```

### Radio Control
#### GET /radio/status
Get current radio control status.

**Response:**
```json
{
    "status": "connected",
    "channels": {
        "1": 1500,
        "2": 1500,
        "3": 1500,
        "4": 1500,
        "5": 1500,
        "6": 1500
    },
    "signal_lost": false
}
```

### Backend Communication
#### POST /backend/sync
Sync data with the backend.

**Request:**
```json
{
    "telemetry": {
        "gps": {...},
        "attitude": {...},
        "battery": {...}
    },
    "status": "active",
    "timestamp": 1234567890.123
}
```

**Response:**
```json
{
    "status": "synced",
    "result": {
        "success": true,
        "timestamp": 1234567890.123
    }
}
```

## WebSocket Interface
The API also provides a WebSocket interface for real-time updates.

### WebSocket Endpoint
```
ws://<raspberry-pi-ip>:8000/ws
```

### Message Types
1. Telemetry Updates:
```json
{
    "type": "telemetry",
    "data": {
        "gps": {...},
        "attitude": {...},
        "battery": {...}
    }
}
```

2. Status Updates:
```json
{
    "type": "status",
    "data": {
        "status": "active",
        "mode": "GUIDED",
        "armed": true
    }
}
```

## Error Handling
The API uses standard HTTP status codes and returns error messages in the following format:

```json
{
    "detail": "Error message description"
}
```

Common status codes:
- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error
- 503: Service Unavailable
