"""FastAPI dependency injection providers."""
from fastapi import Depends
from app.config import Settings, get_settings
from app.services.video_service import VideoService
from app.services.zone_service import ZoneService
from app.services.event_service import EventService
from app.services.pipeline_service import PipelineService


def get_video_service(settings: Settings = Depends(get_settings)) -> VideoService:
    return VideoService(settings)


def get_zone_service(settings: Settings = Depends(get_settings)) -> ZoneService:
    return ZoneService(settings)


def get_event_service(settings: Settings = Depends(get_settings)) -> EventService:
    return EventService(settings)


def get_pipeline_service(settings: Settings = Depends(get_settings)) -> PipelineService:
    return PipelineService(settings)
