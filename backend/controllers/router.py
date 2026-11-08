"""Central API router mounting all controllers."""
from fastapi import APIRouter
from controllers import (
    health_controller,
    video_controller,
    zone_controller,
    event_controller,
    pipeline_controller,
)

api_router = APIRouter()
api_router.include_router(health_controller.router)
api_router.include_router(video_controller.router)
api_router.include_router(zone_controller.router)
api_router.include_router(event_controller.router)
api_router.include_router(pipeline_controller.router)

