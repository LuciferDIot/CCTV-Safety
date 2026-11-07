"""API route controllers."""
from app.routers.health import router as health_router
from app.routers.videos import router as videos_router
from app.routers.zones import router as zones_router
from app.routers.events import router as events_router
from app.routers.pipeline import router as pipeline_router

__all__ = ["health_router", "videos_router", "zones_router", "events_router", "pipeline_router"]

