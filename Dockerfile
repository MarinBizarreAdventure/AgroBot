# AgroBot Raspberry Pi Controller Dockerfile
FROM arm64v8/python:3.8-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-serial \
    python3-gpiozero \
    python3-rpi.gpio \
    python3-pigpio \
    python3-spidev \
    python3-smbus \
    i2c-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set Python path
ENV PYTHONPATH=/app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data config/local

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Default command
CMD ["python3", "-m", "uvicorn", "test_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Alternative commands for different use cases:
# Development: docker run --env ENVIRONMENT=development agrobot-rpi
# Debug: docker run -it --entrypoint /bin/bash agrobot-rpi
# Custom config: docker run -v /host/config:/app/config agrobot-rpi