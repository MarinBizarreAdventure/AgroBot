# AgroBot Wiring Documentation

## Overview
This document details the hardware connections between the Raspberry Pi, Pixhawk 6C, and other components.

## Components
- Raspberry Pi 4
- Pixhawk 6C Flight Controller
- RadioMaster Zorro Transmitter
- RC Receiver (connected to TELEM1)
- M9N GPS Module (connected to GPS1)
- Power Distribution Board
- Motors and ESCs (8x3 connectors)
- Telemetry Radio

## Connection Diagram
```
Raspberry Pi 4 <--USB--> Pixhawk 6C <--GPS1--> M9N GPS
                              ^
                              |
                        TELEM1 Port
                              ^
                              |
                        RC Receiver
                              ^
                              |
                        RadioMaster Zorro

Pixhawk 6C <--I/O PWM OUT [MAIN]--> 8x3 Motor Connector
        ^
        |
<--FMU PWM OUT [AUX]--> 8x3 Motor Connector
```

## Detailed Connections

### Pixhawk 6C to Raspberry Pi
- Connect Pixhawk 6C USB-C port to Raspberry Pi USB port using USB Type-C to USB Type-A cable
- The Pixhawk will be recognized as `/dev/ttyACM0`

### RC Receiver to Pixhawk
- Connect RC Receiver to Pixhawk's TELEM1 port
- This port is used for both telemetry and RC input
- The RC receiver will be automatically detected by the Pixhawk

### M9N GPS Module to Pixhawk
- Connect M9N GPS module to Pixhawk's GPS1 port
- The GPS module will be automatically detected and configured
- Ensure clear view of the sky for optimal GPS reception

### Motor Connections
1. Main Output (I/O PWM OUT [MAIN]):
   - 8x3 connector for main motor outputs
   - Connect motors in the following order:
     - Output 1: Front Left
     - Output 2: Front Right
     - Output 3: Rear Left
     - Output 4: Rear Right
     - Output 5: Left Middle
     - Output 6: Right Middle
     - Output 7: Left Aux
     - Output 8: Right Aux

2. Aux Output (FMU PWM OUT [AUX]):
   - 8x3 connector for auxiliary motor outputs
   - Connect additional motors or servos as needed
   - Follow the same pinout as the main outputs

### Power Distribution
- Connect main battery to Power Distribution Board
- Connect Power Distribution Board to:
  - Pixhawk 6C
  - ESCs for motors
  - Raspberry Pi (if needed)

## Pin Assignments

### Pixhawk 6C Ports
- USB-C: Connection to Raspberry Pi
- GPS1: M9N GPS Module
- TELEM1: RC Receiver
- I/O PWM OUT [MAIN]: 8x3 Motor Connector
- FMU PWM OUT [AUX]: 8x3 Motor Connector

### Motor Connector Pinout (8x3)
```
[Signal] [Power] [Ground]
   1       2       3
   4       5       6
   7       8       9
  10      11      12
  13      14      15
  16      17      18
  19      20      21
  22      23      24
```

## Power Requirements
- Pixhawk 6C: 5V from USB or Power Distribution Board
- M9N GPS: 5V from Pixhawk
- RC Receiver: 5V from Pixhawk
- Motors: Voltage depends on your specific motors (typically 3S-6S LiPo)

## Safety Considerations
1. Power Safety:
   - Always disconnect battery before making connections
   - Use appropriate voltage regulators
   - Check polarity before connecting

2. Signal Safety:
   - Ensure proper signal ground connections
   - Use appropriate signal voltage levels
   - Check for signal interference

3. Physical Protection:
   - Secure all connections
   - Protect GPS antenna
   - Ensure proper motor mounting

## Testing Procedures
1. Power Testing:
   - Test each component individually
   - Verify voltage levels
   - Check for proper power distribution

2. Communication Testing:
   - Verify GPS connection
   - Test RC receiver connection
   - Check motor signal outputs

3. Integration Testing:
   - Test complete system
   - Verify all components work together
   - Check for interference

## Maintenance
1. Regular Checks:
   - Inspect all connections
   - Check for loose wires
   - Verify GPS antenna condition

2. Troubleshooting:
   - Use Pixhawk logs
   - Check component status
   - Verify signal integrity

3. Upgrades:
   - Keep firmware updated
   - Check for component updates
   - Maintain documentation
