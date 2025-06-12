# AgroBot Setup Guide

## Prerequisites

### Hardware Requirements
- Raspberry Pi 4 (4GB RAM recommended)
- Pixhawk 6C Flight Controller
- RadioMaster Zorro Transmitter
- RC Receiver (compatible with RadioMaster)
- GPS Module
- Power Distribution Board
- 3S LiPo Battery (11.1V)
- USB Type-C to Type-A cable (for Pixhawk connection)
- MicroSD card (32GB+ recommended)

### Software Requirements
- Raspberry Pi OS (64-bit)
- Docker
- Docker Compose
- Git

## Installation Steps

### 1. Raspberry Pi Setup

#### 1.1 Install Raspberry Pi OS
```bash
# Download Raspberry Pi Imager
# Flash Raspberry Pi OS (64-bit) to SD card
# Enable SSH and set up WiFi during imaging
```

#### 1.2 Install Docker and Docker Compose
```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install -y docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### 1.3 Clone Repository
```bash
# Clone the repository
git clone https://github.com/your-username/agrobot.git
cd agrobot
```

### 2. Hardware Setup

#### 2.1 Physical Connections
1. Connect Pixhawk to Raspberry Pi:
   ```bash
   # Connect Pixhawk 6C USB-C port to Raspberry Pi USB port
   # Use a USB Type-C to Type-A cable
   # The Pixhawk will be recognized as /dev/ttyACM0
   ```

2. Connect RC Receiver:
   ```bash
   # Connect receiver to Pixhawk RCIN port
   # Verify channel mapping
   ```

3. Connect GPS Module:
   ```bash
   # Connect GPS to Pixhawk GPS port
   # Ensure clear sky view
   ```

4. Power Distribution:
   ```bash
   # Connect main battery to PDB
   # Connect all components to PDB outputs
   # Verify voltage levels
   ```

#### 2.2 Verify Connections
```bash
# Check USB devices
lsusb | grep Pixhawk

# Check serial ports
ls -l /dev/ttyACM0

# Test USB communication
python3 scripts/test_connection.py
```

### 3. Docker Configuration

#### 3.1 Environment Setup
```bash
# Create .env file
cp .env.example .env

# Edit configuration
nano .env

# Required environment variables:
MAVLINK_CONNECTION=/dev/ttyACM0
MAVLINK_BAUD=57600
GPS_ENABLED=true
RC_ENABLED=true
BACKEND_URL=http://your-backend-url
```

#### 3.2 Start the Application
```bash
# Build and start the containers
docker-compose up -d

# Check container status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Accessing the API

#### 4.1 Swagger Documentation
- Open your web browser and navigate to:
  ```
  http://<raspberry-pi-ip>:8000/docs
  ```
- This will show the interactive Swagger UI where you can:
  - View all available endpoints
  - Test API calls directly
  - View request/response schemas
  - Download OpenAPI specification

#### 4.2 ReDoc Documentation
- For an alternative documentation view, visit:
  ```
  http://<raspberry-pi-ip>:8000/redoc
  ```

### 5. Initial Testing

#### 5.1 API Tests
```bash
# Test Pixhawk status
curl http://localhost:8000/api/v1/pixhawk/status

# Test radio status
curl http://localhost:8000/api/v1/radio/status

# Test mission list
curl http://localhost:8000/api/v1/mission/list
```

#### 5.2 WebSocket Tests
```bash
# Install wscat
npm install -g wscat

# Test WebSocket connection
wscat -c ws://localhost:8000/ws
```

### 6. Calibration

#### 6.1 RC Calibration
```bash
# Run RC calibration script
docker-compose exec agrobot python3 scripts/calibrate_radio.py

# Verify channel mapping
curl http://localhost:8000/api/v1/radio/channels
```

#### 6.2 GPS Calibration
```bash
# Wait for GPS fix
# Verify satellite count
curl http://localhost:8000/api/v1/pixhawk/status | grep satellites_visible
```

#### 6.3 Compass Calibration
```bash
# Follow QGroundControl compass calibration
# Verify calibration in API
curl http://localhost:8000/api/v1/pixhawk/status | grep compass
```

### 7. Safety Setup

#### 7.1 Failsafe Configuration
```bash
# Configure failsafe settings
curl -X POST http://localhost:8000/api/v1/radio/failsafe \
  -H "Content-Type: application/json" \
  -d '{"threshold": 0.5}'
```

#### 7.2 Emergency Stop
```bash
# Test emergency stop
curl -X POST http://localhost:8000/api/v1/pixhawk/emergency_stop
```

### 8. Mission Planning Setup

#### 8.1 Create Test Mission
```bash
# Create simple test mission
curl -X POST http://localhost:8000/api/v1/mission/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Mission",
    "waypoints": [
      {
        "latitude": 45.123456,
        "longitude": -122.123456,
        "altitude": 10.0
      }
    ]
  }'
```

#### 8.2 Verify Mission
```bash
# List missions
curl http://localhost:8000/api/v1/mission/list
```

### 9. Backend Integration

#### 9.1 Configure Backend
```bash
# Set backend URL in .env file
nano .env
BACKEND_URL=http://your-backend-url

# Restart the container to apply changes
docker-compose restart

# Test backend connection
curl http://localhost:8000/api/v1/backend/test
```

#### 9.2 Test Data Sync
```bash
# Test data sync
curl -X POST http://localhost:8000/api/v1/backend/sync \
  -H "Content-Type: application/json" \
  -d '{
    "telemetry": {
      "gps": {},
      "attitude": {},
      "battery": {}
    }
  }'
```

## Post-Setup Verification

### 1. System Health Check
```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs -f

# Check resource usage
docker stats
```

### 2. Component Verification
```bash
# Verify all components
docker-compose exec agrobot python3 scripts/verify_system.py
```

### 3. Documentation
```bash
# Review documentation
cat docs/api.md
cat docs/troubleshooting.md
cat docs/wiring.md
```

## Next Steps

1. **Testing**
   - Run full system tests
   - Test failsafe systems
   - Verify mission execution

2. **Monitoring**
   - Set up monitoring tools
   - Configure alerts
   - Set up logging

3. **Backup**
   - Backup configuration
   - Document setup
   - Create recovery plan

## Troubleshooting

If you encounter issues during setup:
1. Check the troubleshooting guide in `docs/troubleshooting.md`
2. Verify all connections
3. Check container logs: `docker-compose logs -f`
4. Test individual components
5. Review error messages

## Docker Commands Reference

### Basic Commands
```bash
# Start the application
docker-compose up -d

# Stop the application
docker-compose down

# View logs
docker-compose logs -f

# Restart the application
docker-compose restart

# Rebuild the application
docker-compose up -d --build
```

### Container Management
```bash
# Enter the container shell
docker-compose exec agrobot bash

# Run a specific script
docker-compose exec agrobot python3 scripts/test_connection.py

# View container resource usage
docker stats
```

### Troubleshooting Commands
```bash
# Check container status
docker-compose ps

# View detailed container info
docker inspect agrobot

# Check container logs
docker-compose logs -f agrobot

# Restart specific service
docker-compose restart agrobot
```
