@echo off
echo Starting AgroBot build process...

echo Cleaning up...
docker-compose down
docker system prune -f

echo Creating directories...
if not exist logs mkdir logs
if not exist data mkdir data
if not exist config\local mkdir config\local

echo Building containers...
docker-compose build --no-cache

echo Starting services...
docker-compose up -d

echo Checking service status...
docker-compose ps

echo Build process completed!
echo You can check the logs with: docker-compose logs -f 