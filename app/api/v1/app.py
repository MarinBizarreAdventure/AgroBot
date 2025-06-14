from fastapi import FastAPI
from app.api.v1.api import api_router

v1_app = FastAPI(
    title="AgroBot API v1",
    description="API for controlling and monitoring the AgroBot system (v1)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

v1_app.include_router(api_router) 