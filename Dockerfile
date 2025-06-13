# AgroBot Raspberry Pi Controller Dockerfile
# Multi-stage build for optimized production image

# Build stage
FROM python:3.8-slim as builder

# Install system dependencies for building
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
    python3-cups \
    cups \
    cups-client \
    python3-rpi.gpio \
    python3-pigpio \
    python3-spidev \
    python3-smbus \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.8-slim as production

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    # System utilities
    curl \
    wget \
    nano \
    htop \
    # Hardware access
    i2c-tools \
    python3-rpi.gpio \
    python3-pigpio \
    python3-spidev \
    python3-smbus \
    # Network utilities
    net-tools \
    iputils-ping \
    # Serial communication
    minicom \
    # GPS utilities
    gpsd \
    gpsd-clients \
    # Camera support (if needed)
    v4l-utils \
    # CUPS support
    python3-cups \
    cups \
    cups-client \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user for security
RUN groupadd -r agrobot && useradd -r -g agrobot agrobot

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data config/local backups temp \
    && chown -R agrobot:agrobot /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV MAVLINK_CONNECTION=/dev/ttyACM0
ENV MAVLINK_BAUD=57600
ENV GPS_ENABLED=true
ENV RC_ENABLED=true
ENV BACKEND_URL=http://your-backend-url

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER agrobot

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Alternative commands for different use cases:
# Development: docker run --env ENVIRONMENT=development agrobot-rpi
# Debug: docker run -it --entrypoint /bin/bash agrobot-rpi
# Custom config: docker run -v /host/config:/app/config agrobot-rpi