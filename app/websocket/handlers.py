from fastapi import WebSocket

async def handle_telemetry(websocket: WebSocket, telemetry_data):
    await websocket.send_json({"type": "telemetry", "data": telemetry_data})

async def handle_status(websocket: WebSocket, status):
    await websocket.send_json({"type": "status", "data": status})
