"""FastAPI dependency injection providers."""
from typing import Optional
from fastapi import Depends
from app.config import Settings, get_settings
from app.services.video_service import VideoService
from app.services.zone_service import ZoneService
from app.services.event_service import EventService
from app.services.pipeline_service import PipelineService

_pipeline_svc: Optional[PipelineService] = None


def get_video_service(settings: Settings = Depends(get_settings)) -> VideoService:
    return VideoService(settings)


def get_zone_service(settings: Settings = Depends(get_settings)) -> ZoneService:
    return ZoneService(settings)


def get_event_service(settings: Settings = Depends(get_settings)) -> EventService:
    return EventService(settings)


def get_pipeline_service(settings: Settings = Depends(get_settings)) -> PipelineService:
    global _pipeline_svc
    if _pipeline_svc is None:
        _pipeline_svc = PipelineService(settings)
    return _pipeline_svc
