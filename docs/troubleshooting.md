# AgroBot Troubleshooting Guide

## Common Issues and Solutions

### 1. Pixhawk Connection Issues

#### Symptoms:
- Cannot connect to Pixhawk
- Connection drops frequently
- No heartbeat received
- Serial port access denied

#### Solutions:
1. **Serial Port Access**
   ```bash
   # Check if user is in dialout group
   groups $USER
   
   # Add user to dialout group if needed
   sudo usermod -a -G dialout $USER
   
   # Verify serial port permissions
   ls -l /dev/ttyACM0
   ```

2. **Baud Rate Mismatch**
   - Verify Pixhawk baud rate in QGroundControl
   - Ensure API is using matching baud rate (default: 57600)
   - Try different baud rates if connection fails

3. **USB Connection**
   - Try different USB ports
   - Use powered USB hub if available
   - Check USB cable integrity
   - Verify USB power supply

### 2. Radio Control Issues

#### Symptoms:
- No RC input detected
- Erratic channel values
- Signal loss warnings
- Channel mapping incorrect

#### Solutions:
1. **RC Receiver Connection**
   - Verify physical connections
   - Check receiver power LED
   - Ensure correct channel mapping
   - Calibrate channels using `/radio/calibrate` endpoint

2. **Signal Loss**
   - Check transmitter battery
   - Verify antenna orientation
   - Test failsafe settings
   - Increase failsafe threshold if needed

3. **Channel Mapping**
   ```python
   # Default channel mapping
   CHANNEL_MAP = {
       1: "roll",      # Aileron
       2: "pitch",     # Elevator
       3: "throttle",  # Throttle
       4: "yaw",       # Rudder
       5: "mode",      # Flight mode
       6: "aux1"       # Auxiliary
   }
   ```

### 3. GPS Issues

#### Symptoms:
- No GPS fix
- Poor GPS accuracy
- GPS data not updating
- Incorrect coordinates

#### Solutions:
1. **GPS Fix**
   - Ensure clear sky view
   - Wait for cold start (up to 5 minutes)
   - Check GPS module connections
   - Verify GPS module power

2. **GPS Accuracy**
   - Check HDOP value (should be < 2.0)
   - Verify number of satellites (minimum 6)
   - Ensure GPS module is properly mounted
   - Check for electromagnetic interference

### 4. Mission Planning Issues

#### Symptoms:
- Mission upload fails
- Waypoints not reached
- Mission execution stops
- Incorrect mission parameters

#### Solutions:
1. **Mission Upload**
   - Verify waypoint format
   - Check mission parameters
   - Ensure sufficient memory
   - Clear existing mission first

2. **Mission Execution**
   - Check vehicle mode
   - Verify GPS accuracy
   - Ensure proper arming
   - Monitor battery level

### 5. Backend Communication Issues

#### Symptoms:
- Sync failures
- Data upload errors
- Connection timeouts
- Authentication errors

#### Solutions:
1. **Network Issues**
   - Check internet connection
   - Verify backend server status
   - Test network latency
   - Check firewall settings

2. **Data Sync**
   - Verify data format
   - Check timestamp synchronization
   - Monitor queue size
   - Implement retry mechanism

### 6. WebSocket Issues

#### Symptoms:
- Connection drops
- No real-time updates
- High latency
- Connection refused

#### Solutions:
1. **Connection Issues**
   - Check WebSocket URL
   - Verify port availability
   - Monitor connection state
   - Implement reconnection logic

2. **Performance**
   - Reduce update frequency
   - Optimize message size
   - Check network bandwidth
   - Monitor server load

## Diagnostic Tools

### 1. Logging
```python
# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Check specific component logs
tail -f /var/log/agrobot/pixhawk.log
tail -f /var/log/agrobot/radio.log
tail -f /var/log/agrobot/mission.log
```

### 2. System Status
```bash
# Check system resources
htop
df -h
free -m

# Check USB devices
lsusb
dmesg | grep tty

# Check network status
ifconfig
ping backend-server
```

### 3. API Testing
```bash
# Test API endpoints
curl http://localhost:8000/api/v1/pixhawk/status
curl http://localhost:8000/api/v1/radio/status
curl http://localhost:8000/api/v1/mission/list

# Test WebSocket
wscat -c ws://localhost:8000/ws
```

## Emergency Procedures

### 1. Immediate Stop
```bash
# Emergency stop endpoint
curl -X POST http://localhost:8000/api/v1/pixhawk/emergency_stop

# Manual emergency stop
python3 scripts/emergency_stop.py
```

### 2. Manual Control
```bash
# Switch to manual mode
curl -X POST http://localhost:8000/api/v1/pixhawk/mode -d '{"mode": "MANUAL"}'

# Disarm motors
curl -X POST http://localhost:8000/api/v1/pixhawk/arm -d '{"arm": false}'
```

### 3. System Recovery
```bash
# Restart services
sudo systemctl restart agrobot-api
sudo systemctl restart agrobot-core

# Clear mission data
curl -X DELETE http://localhost:8000/api/v1/mission/clear

# Reset failsafe
curl -X POST http://localhost:8000/api/v1/radio/failsafe/reset
```

## Maintenance

### 1. Regular Checks
- Verify all connections
- Check battery levels
- Update firmware
- Calibrate sensors
- Test failsafe systems

### 2. Software Updates
```bash
# Update system
git pull origin main
pip install -r requirements.txt
sudo systemctl restart agrobot-api
```

### 3. Configuration Backup
```bash
# Backup configuration
cp config/settings.py config/settings.py.backup
cp config/channels.py config/channels.py.backup

# Restore configuration
cp config/settings.py.backup config/settings.py
cp config/channels.py.backup config/channels.py
```
