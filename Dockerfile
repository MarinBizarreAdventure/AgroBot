# AgroBot Raspberry Pi Controller Dockerfile
FROM arm64v8/python:3.8-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    pkg-config \
    git \
    libffi-dev \
    libssl-dev \
    python3-dev \
    python3-serial \
    python3-gpiozero \
    python3-rpi.gpio \
    python3-pigpio \
    python3-spidev \
    python3-smbus \
    i2c-tools \
    curl \
    libjpeg-dev \
    zlib1g-dev \
    libopenjp2-7 \
    libtiff-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Verify installations
RUN python3 -c "import serial; print('pyserial installed')" \
    && python3 -c "import gpiozero; print('gpiozero installed')" \
    && python3 -c "import RPi.GPIO; print('RPi.GPIO installed')" \
    && python3 -c "import pigpio; print('pigpio installed')" \
    && python3 -c "import spidev; print('spidev installed')" \
    && python3 -c "import smbus; print('smbus installed')" \
    && i2cdetect -V \
    && curl --version

# Set working directory
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/data /app/config/local && \
    chown -R appuser:appuser /app

# Copy requirements first for better Docker layer caching
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip cache purge

# Verify Python package installations
RUN python3 -c "import fastapi; print('FastAPI installed')" \
    && python3 -c "import uvicorn; print('Uvicorn installed')" \
    && python3 -c "import pymavlink; print('pymavlink installed')" \
    && python3 -c "import redis; print('redis installed')" \
    && python3 -c "import psutil; print('psutil installed')" \
    && python3 -c "import structlog; print('structlog installed')"

# Copy application code
COPY --chown=appuser:appuser . .

# Set proper permissions
RUN chmod -R 755 /app && \
    chmod -R 777 /app/logs /app/data /app/config/local

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Alternative commands for different use cases:
# Development: docker run --env ENVIRONMENT=development agrobot-rpi
# Debug: docker run -it --entrypoint /bin/bash agrobot-rpi
# Custom config: docker run -v /host/config:/app/config agrobot-rpi