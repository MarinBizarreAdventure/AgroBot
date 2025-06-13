# AgroBot Raspberry Pi Controller Dockerfile
FROM arm32v7/python:3.8-slim

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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data config/local \
    && chown -R nobody:nogroup /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER nobody

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Alternative commands for different use cases:
# Development: docker run --env ENVIRONMENT=development agrobot-rpi
# Debug: docker run -it --entrypoint /bin/bash agrobot-rpi
# Custom config: docker run -v /host/config:/app/config agrobot-rpi