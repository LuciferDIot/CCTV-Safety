"""Intersection zone geometry and traffic corridor controller."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from controllers.deps import get_zone_service
from services.zone_service import ZoneService
from views.zone_views import IntersectionZonesConfig

router = APIRouter(prefix="/config/zones", tags=["zones"])


@router.get("", response_model=IntersectionZonesConfig)
def get_zones(
    video_file: Optional[str] = Query(None, description="Optional video file name"),
    width: int = Query(1920, description="Video width"),
    height: int = Query(1080, description="Video height"),
    svc: ZoneService = Depends(get_zone_service)
):
    return svc.get_config(video_file=video_file, width=width, height=height)


@router.put("", response_model=IntersectionZonesConfig)
def update_zones(cfg: IntersectionZonesConfig, svc: ZoneService = Depends(get_zone_service)):
    return svc.update_config(cfg)


@router.post("/reset", response_model=IntersectionZonesConfig)
def reset_zones(
    video_file: Optional[str] = Query(None, description="Optional video file name"),
    width: int = Query(1920, description="Video width"),
    height: int = Query(1080, description="Video height"),
    svc: ZoneService = Depends(get_zone_service)
):
    return svc.reset_config(video_file=video_file, width=width, height=height)

