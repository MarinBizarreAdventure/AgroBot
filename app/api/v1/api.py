"""
API v1 router aggregation
Combines all endpoint routers into a single API router
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    pixhawk,
    gps,
    movement,
    mission,
    radio,
    status,
    backend
)

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health Check"]
)

api_router.include_router(
    pixhawk.router,
    prefix="/pixhawk",
    tags=["Pixhawk Control"]
)

api_router.include_router(
    gps.router,
    prefix="/gps",
    tags=["GPS"]
)

api_router.include_router(
    movement.router,
    prefix="/movement",
    tags=["Movement Control"]
)

api_router.include_router(
    mission.router,
    prefix="/mission",
    tags=["Mission Planning"]
)

api_router.include_router(
    radio.router,
    prefix="/radio",
    tags=["Radio Control"]
)

api_router.include_router(
    status.router,
    prefix="/status",
    tags=["Status & Diagnostics"]
)

api_router.include_router(
    backend.router,
    prefix="/backend",
    tags=["Backend Communication"]
)