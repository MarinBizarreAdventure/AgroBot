from pydantic import BaseModel

class TelemetryData(BaseModel):
    gps: dict
    attitude: dict
    battery: dict

class RobotStatus(BaseModel):
    status: str
    timestamp: str
