"""FastAPI controller dependencies (service & settings injection)."""
from typing import Optional
from fastapi import Depends
from config import Settings, get_settings
from services.video_service import VideoService
from services.zone_service import ZoneService
from services.event_service import EventService
from services.pipeline_service import PipelineService

_pipeline_svc: Optional[PipelineService] = None
_zone_svc: Optional[ZoneService] = None


def get_video_service(settings: Settings = Depends(get_settings)) -> VideoService:
    return VideoService(settings)


def get_zone_service(settings: Settings = Depends(get_settings)) -> ZoneService:
    global _zone_svc
    if _zone_svc is None:
        _zone_svc = ZoneService(settings)
    return _zone_svc


def get_event_service(settings: Settings = Depends(get_settings)) -> EventService:
    return EventService(settings)


def get_pipeline_service(settings: Settings = Depends(get_settings)) -> PipelineService:
    global _pipeline_svc
    if _pipeline_svc is None:
        _pipeline_svc = PipelineService(settings)
    return _pipeline_svc
