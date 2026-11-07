"""Zone geometry and permitted lane direction vector endpoints."""
from fastapi import APIRouter, Depends
from app.dependencies import get_zone_service
from app.services.zone_service import ZoneService
from app.schemas.zones import IntersectionZonesConfig

router = APIRouter(prefix="/config/zones", tags=["zones"])


@router.get("", response_model=IntersectionZonesConfig)
def get_zones(svc: ZoneService = Depends(get_zone_service)):
    """Fetch active intersection road polygon, crosswalk polygons, and lane vectors."""
    return svc.get_config()


@router.put("", response_model=IntersectionZonesConfig)
def update_zones(cfg: IntersectionZonesConfig, svc: ZoneService = Depends(get_zone_service)):
    """Save modified zones configuration updated from the interactive SVG overlay canvas."""
    return svc.update_config(cfg)


@router.post("/reset", response_model=IntersectionZonesConfig)
def reset_zones(svc: ZoneService = Depends(get_zone_service)):
    """Reset intersection zones to initial calibrated reference coordinates."""
    return svc.reset_config()

