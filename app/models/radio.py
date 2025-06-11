"""
Pydantic models for radio control API endpoints
"""

from typing import Optional, Dict, Any, List, Set
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Response Models
class RadioStatus(BaseModel):
    """Radio control system status"""
    connected: bool = Field(..., description="Whether RC signal is present")
    signal_strength: float = Field(..., description="Signal strength percentage (0-100)")
    channels_active: int = Field(..., description="Number of active channels")
    failsafe_active: bool = Field(..., description="Whether failsafe is currently active")
    last_update: Optional[float] = Field(None, description="Last RC data update timestamp")
    rssi: int = Field(..., description="Received Signal Strength Indicator")
    link_quality: float = Field(..., description="Link quality percentage (0-100)")
    
    class Config:
        schema_extra = {
            "example": {
                "connected": True,
                "signal_strength": 85.0,
                "channels_active": 8,
                "failsafe_active": False,
                "last_update": 1640995200.0,
                "rssi": -45,
                "link_quality": 85.0
            }
        }


class ChannelData(BaseModel):
    """Individual RC channel data"""
    channel: int = Field(..., description="Channel number (1-based)")
    name: str = Field(..., description="Channel name/function")
    pwm_value: int = Field(..., description="Raw PWM value (µs)")
    normalized_value: float = Field(..., description="Normalized value (-1.0 to 1.0)")
    percentage: float = Field(..., description="Percentage value (0-100%)")
    active: bool = Field(..., description="Whether channel is receiving valid signal")
    
    @validator('channel')
    def validate_channel(cls, v):
        if not (1 <= v <= 18):
            raise ValueError('Channel must be between 1 and 18')
        return v
    
    @validator('pwm_value')
    def validate_pwm(cls, v):
        if not (800 <= v <= 2200):
            raise ValueError('PWM value must be between 800 and 2200 µs')
        return v
    
    @validator('normalized_value')
    def validate_normalized(cls, v):
        if not (-1.0 <= v <= 1.0):
            raise ValueError('Normalized value must be between -1.0 and 1.0')
        return v
    
    @validator('percentage')
    def validate_percentage(cls, v):
        if not (0.0 <= v <= 100.0):
            raise ValueError('Percentage must be between 0 and 100')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "channel": 1,
                "name": "Roll",
                "pwm_value": 1500,
                "normalized_value": 0.0,
                "percentage": 50.0,
                "active": True
            }
        }


class ChannelMapping(BaseModel):
    """RC channel mapping configuration"""
    roll_channel: int = Field(..., description="Roll control channel")
    pitch_channel: int = Field(..., description="Pitch control channel")
    throttle_channel: int = Field(..., description="Throttle control channel")
    yaw_channel: int = Field(..., description="Yaw control channel")
    mode_channel: int = Field(..., description="Flight mode channel")
    aux_channels: Dict[int, str] = Field(..., description="Auxiliary channel mappings")
    channel_names: Dict[int, str] = Field(..., description="All channel names")
    pwm_ranges: Dict[str, int] = Field(..., description="PWM range configuration")
    
    class Config:
        schema_extra = {
            "example": {
                "roll_channel": 1,
                "pitch_channel": 2,
                "throttle_channel": 3,
                "yaw_channel": 4,
                "mode_channel": 5,
                "aux_channels": {
                    6: "Aux1",
                    7: "Aux2",
                    8: "Aux3"
                },
                "channel_names": {
                    1: "Roll",
                    2: "Pitch",
                    3: "Throttle",
                    4: "Yaw",
                    5: "Flight Mode"
                },
                "pwm_ranges": {
                    "min": 1000,
                    "mid": 1500,
                    "max": 2000
                }
            }
        }


class FailsafeConfig(BaseModel):
    """RC failsafe configuration"""
    enabled: bool = Field(..., description="Whether failsafe is enabled")
    timeout_seconds: float = Field(..., description="Failsafe timeout in seconds")
    action: str = Field(..., description="Failsafe action (RTL/LAND/HOLD)")
    triggered: bool = Field(..., description="Whether failsafe is currently triggered")
    last_trigger_time: Optional[float] = Field(None, description="Last failsafe trigger timestamp")
    recovery_mode: str = Field(..., description="How to recover from failsafe")
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ["RTL", "LAND", "HOLD", "STABILIZE"]
        if v.upper() not in valid_actions:
            raise ValueError(f"Action must be one of: {valid_actions}")
        return v.upper()
    
    @validator('recovery_mode')
    def validate_recovery_mode(cls, v):
        valid_modes = ["manual", "automatic", "hybrid"]
        if v.lower() not in valid_modes:
            raise ValueError(f"Recovery mode must be one of: {valid_modes}")
        return v.lower()
    
    class Config:
        schema_extra = {
            "example": {
                "enabled": True,
                "timeout_seconds": 2.0,
                "action": "RTL",
                "triggered": False,
                "last_trigger_time": None,
                "recovery_mode": "manual"
            }
        }


# Request Models
class CalibrationRequest(BaseModel):
    """RC channel calibration request"""
    channels: Set[int] = Field(..., description="Channels to calibrate")
    duration: Optional[float] = Field(30.0, description="Calibration duration in seconds", gt=0, le=300)
    auto_detect: bool = Field(True, description="Auto-detect min/max values")
    save_settings: bool = Field(True, description="Save calibration to flight controller")
    
    @validator('channels')
    def validate_channels(cls, v):
        if not v:
            raise ValueError('At least one channel must be specified')
        for ch in v:
            if not (1 <= ch <= 18):
                raise ValueError(f'Channel {ch} must be between 1 and 18')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "channels": [1, 2, 3, 4],
                "duration": 30.0,
                "auto_detect": True,
                "save_settings": True
            }
        }


class CalibrationResponse(BaseModel):
    """RC channel calibration response"""
    success: bool = Field(..., description="Whether calibration completed successfully")
    message: str = Field(..., description="Calibration result message")
    calibrated_channels: List[int] = Field(..., description="Successfully calibrated channels")
    results: Dict[int, Dict[str, Any]] = Field(..., description="Calibration results per channel")
    duration_seconds: float = Field(..., description="Actual calibration duration")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Calibration completed successfully",
                "calibrated_channels": [1, 2, 3, 4],
                "results": {
                    1: {
                        "min_pwm": 1000,
                        "max_pwm": 2000,
                        "center_pwm": 1500,
                        "current_pwm": 1500,
                        "range": 1000,
                        "deadband": 20
                    }
                },
                "duration_seconds": 30.0
            }
        }


class OverrideRequest(BaseModel):
    """RC channel override request"""
    channel_overrides: Dict[int, int] = Field(..., description="Channel overrides (channel -> PWM value)")
    duration: Optional[float] = Field(None, description="Override duration in seconds (None = indefinite)")
    priority: int = Field(1, description="Override priority (1=low, 5=high)", ge=1, le=5)
    
    @validator('channel_overrides')
    def validate_overrides(cls, v):
        if not v:
            raise ValueError('At least one channel override must be specified')
        
        for channel, pwm in v.items():
            if not (1 <= channel <= 18):
                raise ValueError(f'Channel {channel} must be between 1 and 18')
            if not (800 <= pwm <= 2200):
                raise ValueError(f'PWM value {pwm} for channel {channel} must be between 800 and 2200')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "channel_overrides": {
                    1: 1500,
                    2: 1500,
                    3: 1000,
                    4: 1500
                },
                "duration": 10.0,
                "priority": 3
            }
        }


# Advanced Models
class RCHealth(BaseModel):
    """RC system health assessment"""
    overall_health: str = Field(..., description="Overall health status")
    signal_quality: str = Field(..., description="Signal quality assessment")
    interference_level: str = Field(..., description="Interference level")
    connection_stability: str = Field(..., description="Connection stability")
    recommendations: List[str] = Field(default=[], description="Health improvement recommendations")
    last_assessment: float = Field(..., description="Last health assessment timestamp")
    
    @validator('overall_health', 'signal_quality', 'interference_level', 'connection_stability')
    def validate_health_status(cls, v):
        valid_statuses = ["excellent", "good", "fair", "poor", "critical"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v.lower()
    
    class Config:
        schema_extra = {
            "example": {
                "overall_health": "good",
                "signal_quality": "excellent",
                "interference_level": "low",
                "connection_stability": "stable",
                "recommendations": [],
                "last_assessment": 1640995200.0
            }
        }


class RCTelemetry(BaseModel):
    """RC telemetry data"""
    timestamp: float = Field(..., description="Telemetry timestamp")
    packet_rate: float = Field(..., description="Packets per second")
    packet_loss: float = Field(..., description="Packet loss percentage")
    latency_ms: float = Field(..., description="Signal latency in milliseconds")
    noise_floor: int = Field(..., description="Noise floor in dBm")
    snr: float = Field(..., description="Signal-to-noise ratio")
    frequency_mhz: float = Field(..., description="Operating frequency in MHz")
    power_dbm: int = Field(..., description="Transmit power in dBm")
    
    class Config:
        schema_extra = {
            "example": {
                "timestamp": 1640995200.0,
                "packet_rate": 50.0,
                "packet_loss": 0.1,
                "latency_ms": 15.0,
                "noise_floor": -95,
                "snr": 25.5,
                "frequency_mhz": 2437.0,
                "power_dbm": 20
            }
        }


class RCConfiguration(BaseModel):
    """RC system configuration"""
    protocol: str = Field(..., description="RC protocol (PPM/PWM/SBUS/etc.)")
    channels: int = Field(..., description="Number of channels")
    update_rate: int = Field(..., description="Update rate in Hz")
    inversion: bool = Field(False, description="Signal inversion enabled")
    failsafe_enabled: bool = Field(True, description="Failsafe enabled")
    range_check: bool = Field(True, description="Range check enabled")
    bind_mode: bool = Field(False, description="Currently in bind mode")
    
    @validator('protocol')
    def validate_protocol(cls, v):
        valid_protocols = ["PPM", "PWM", "SBUS", "IBUS", "SUMD", "DSM"]
        if v.upper() not in valid_protocols:
            raise ValueError(f"Protocol must be one of: {valid_protocols}")
        return v.upper()
    
    @validator('channels')
    def validate_channels(cls, v):
        if not (4 <= v <= 18):
            raise ValueError('Channel count must be between 4 and 18')
        return v
    
    @validator('update_rate')
    def validate_update_rate(cls, v):
        if not (10 <= v <= 500):
            raise ValueError('Update rate must be between 10 and 500 Hz')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "protocol": "SBUS",
                "channels": 8,
                "update_rate": 50,
                "inversion": False,
                "failsafe_enabled": True,
                "range_check": True,
                "bind_mode": False
            }
        }


class RCStatistics(BaseModel):
    """RC usage statistics"""
    total_packets: int = Field(..., description="Total packets received")
    lost_packets: int = Field(..., description="Total packets lost")
    error_packets: int = Field(..., description="Packets with errors")
    uptime_seconds: float = Field(..., description="RC system uptime")
    connection_count: int = Field(..., description="Number of connections")
    last_disconnect: Optional[float] = Field(None, description="Last disconnect timestamp")
    average_rssi: float = Field(..., description="Average RSSI")
    min_rssi: int = Field(..., description="Minimum RSSI recorded")
    max_rssi: int = Field(..., description="Maximum RSSI recorded")
    
    @property
    def packet_loss_rate(self) -> float:
        """Calculate packet loss rate"""
        if self.total_packets == 0:
            return 0.0
        return (self.lost_packets / self.total_packets) * 100
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate"""
        if self.total_packets == 0:
            return 0.0
        return (self.error_packets / self.total_packets) * 100
    
    class Config:
        schema_extra = {
            "example": {
                "total_packets": 50000,
                "lost_packets": 25,
                "error_packets": 5,
                "uptime_seconds": 3600.0,
                "connection_count": 3,
                "last_disconnect": 1640995100.0,
                "average_rssi": -45.5,
                "min_rssi": -65,
                "max_rssi": -35
            }
        }