# AgroBot Hardware Wiring Guide

## Overview
This document details the hardware connections between the Raspberry Pi, Pixhawk 6C, and RadioMaster Zorro components of the AgroBot system.

## Components
1. Raspberry Pi 4
2. Pixhawk 6C Flight Controller
3. RadioMaster Zorro Transmitter
4. RC Receiver
5. GPS Module
6. Power Distribution Board
7. Motors and ESCs
8. Telemetry Radio

## Connection Diagram
```
[RadioMaster Zorro] <---> [RC Receiver] <---> [Pixhawk 6C] <---> [Raspberry Pi]
                                                                    |
                                                                    v
                                                              [GPS Module]
                                                                    |
                                                                    v
                                                              [Telemetry Radio]
```

## Detailed Connections

### 1. Pixhawk 6C to Raspberry Pi
```
Pixhawk 6C USB-C Port <---> Raspberry Pi USB Port
- Use a USB Type-C to USB Type-A cable
- Connect to any USB port on the Raspberry Pi
- The Pixhawk will be recognized as /dev/ttyACM0
```

### 2. RC Receiver to Pixhawk
```
RC Receiver <---> Pixhawk RCIN Port
- CH1 (Roll) -> RCIN 1
- CH2 (Pitch) -> RCIN 2
- CH3 (Throttle) -> RCIN 3
- CH4 (Yaw) -> RCIN 4
- CH5 (Mode) -> RCIN 5
- CH6 (Aux1) -> RCIN 6
- GND -> GND
- 5V -> 5V
```

### 3. GPS Module to Pixhawk
```
GPS Module <---> Pixhawk GPS Port
- GPS TX -> GPS RX
- GPS RX -> GPS TX
- GND -> GND
- 5V -> 5V
```

### 4. Telemetry Radio to Raspberry Pi
```
Telemetry Radio <---> Raspberry Pi UART
- TX -> GPIO 14 (RXD)
- RX -> GPIO 15 (TXD)
- GND -> GND
- 5V -> 5V
```

### 5. Power Distribution
```
Power Distribution Board
- Main Battery -> PDB Input
- PDB Output 1 -> Pixhawk Power Module
- PDB Output 2 -> Raspberry Pi (via 5V BEC)
- PDB Output 3 -> RC Receiver
- PDB Output 4 -> GPS Module
- PDB Output 5 -> Telemetry Radio
```

## Pin Assignments

### Raspberry Pi USB Ports
```
USB Port 1: Pixhawk 6C (USB Type-C to Type-A)
USB Port 2: Optional: Telemetry Radio
USB Port 3: Optional: GPS Module
USB Port 4: Optional: Other peripherals
```

### Pixhawk 6C Ports
```
USB-C: Raspberry Pi Connection
- This port provides both power and data
- Baud rate: 57600 (default)

RCIN: Radio Control Input
- Pin 1: CH1 (Roll)
- Pin 2: CH2 (Pitch)
- Pin 3: CH3 (Throttle)
- Pin 4: CH4 (Yaw)
- Pin 5: CH5 (Mode)
- Pin 6: CH6 (Aux1)
- Pin 7: GND
- Pin 8: 5V

GPS: GPS Module
- Pin 1: TX
- Pin 2: RX
- Pin 3: GND
- Pin 4: 5V
```

## Power Requirements

### Voltage Levels
- Main Battery: 3S LiPo (11.1V)
- Pixhawk: 5V (via USB or Power Module)
- Raspberry Pi: 5V (via USB or BEC)
- RC Receiver: 5V
- GPS Module: 5V
- Telemetry Radio: 5V

### Current Requirements
- Raspberry Pi: 2.5A @ 5V
- Pixhawk: 0.5A @ 5V
- RC Receiver: 0.1A @ 5V
- GPS Module: 0.1A @ 5V
- Telemetry Radio: 0.2A @ 5V
- Total: ~3.4A @ 5V

## Safety Considerations

### 1. Power Protection
- Use appropriate fuses for each power line
- Implement reverse polarity protection
- Add power filtering capacitors
- Use quality BEC for voltage regulation

### 2. Signal Protection
- Add level shifters if needed
- Implement signal filtering
- Use shielded cables for long runs
- Add pull-up/pull-down resistors

### 3. Physical Protection
- Secure all connections with strain relief
- Use heat shrink tubing for insulation
- Implement cable management
- Protect against vibration

## Testing Procedures

### 1. Power Testing
```bash
# Check voltage levels
multimeter -v 5V
multimeter -v 3.3V

# Check current draw
multimeter -a 5V
```

### 2. Communication Testing
```bash
# Test USB connection
lsusb | grep Pixhawk

# Test serial communication
python3 scripts/test_uart.py

# Test RC input
python3 scripts/test_rc.py

# Test GPS
python3 scripts/test_gps.py
```

### 3. Integration Testing
```bash
# Test full system
python3 scripts/test_system.py

# Verify failsafe
python3 scripts/test_failsafe.py
```

## Maintenance

### 1. Regular Checks
- Inspect all connections
- Check for loose wires
- Verify power levels
- Test communication

### 2. Troubleshooting
- Use multimeter for voltage checks
- Use oscilloscope for signal analysis
- Check continuity of connections
- Verify ground connections

### 3. Upgrades
- Document any wiring changes
- Update pin assignments
- Test new connections
- Verify compatibility
