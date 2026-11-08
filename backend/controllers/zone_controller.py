"""Intersection zone geometry and traffic corridor controller."""
from fastapi import APIRouter, Depends
from controllers.deps import get_zone_service
from services.zone_service import ZoneService
from views.zone_views import IntersectionZonesConfig

router = APIRouter(prefix="/config/zones", tags=["zones"])


@router.get("", response_model=IntersectionZonesConfig)
def get_zones(svc: ZoneService = Depends(get_zone_service)):
    return svc.get_config()


@router.put("", response_model=IntersectionZonesConfig)
def update_zones(cfg: IntersectionZonesConfig, svc: ZoneService = Depends(get_zone_service)):
    return svc.update_config(cfg)


@router.post("/reset", response_model=IntersectionZonesConfig)
def reset_zones(svc: ZoneService = Depends(get_zone_service)):
    return svc.reset_config()

