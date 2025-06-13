#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting AgroBot build process...${NC}"

# Clean up
echo -e "${YELLOW}Cleaning up...${NC}"
docker-compose down
docker system prune -f

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p logs data config/local

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod -R 755 .
chmod -R 777 logs data config/local

# Build with cache
echo -e "${YELLOW}Building containers...${NC}"
docker-compose build --no-cache

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Check status
echo -e "${YELLOW}Checking service status...${NC}"
docker-compose ps

echo -e "${GREEN}Build process completed!${NC}"
echo -e "${YELLOW}You can check the logs with: docker-compose logs -f${NC}" 