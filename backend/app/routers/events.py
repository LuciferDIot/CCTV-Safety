"""Traffic safety events, evidence frame serving, and machine-readable exports."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from app.dependencies import get_event_service
from app.services.event_service import EventService
from app.schemas.events import TrafficEvent

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=List[TrafficEvent])
def list_events(
    status: Optional[str] = Query(None, description="Filter: CONFIRMED, EXEMPT, INSUFFICIENT_EVIDENCE, IGNORED"),
    event_type: Optional[str] = Query(None, description="Filter: WRONG_WAY, CROSSWALK_RIDING, WALKING_MOTORCYCLE, etc."),
    track_id: Optional[int] = Query(None, description="Filter by motorcycle tracking ID"),
    svc: EventService = Depends(get_event_service)
):
    """Retrieve safety events with filterable parameters."""
    return svc.get_events(status=status, event_type=event_type, track_id=track_id)


@router.get("/export/csv")
def export_csv(svc: EventService = Depends(get_event_service)):
    """Machine-readable CSV export conforming to Technical Deliverable #4."""
    csv_data = svc.export_csv()
    return Response(
        content=csv_data, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=detected_events.csv"}
    )


@router.get("/export/json", response_model=List[TrafficEvent])
def export_json(svc: EventService = Depends(get_event_service)):
    """Machine-readable JSON export conforming to Technical Deliverable #4."""
    return svc.get_events()


@router.get("/{event_id}", response_model=TrafficEvent)
def get_event(event_id: str, svc: EventService = Depends(get_event_service)):
    """Retrieve detailed telemetry, displacement alignment, and posture metrics for an event."""
    return svc.get_event_by_id(event_id)


@router.get("/{event_id}/frames/{frame_type}")
def get_evidence_frame(event_id: str, frame_type: str, svc: EventService = Depends(get_event_service)):
    """Serve temporal evidence strip images (entry, midpoint, exit, card)."""
    frame_path = svc.get_evidence_frame(event_id, frame_type)
    return FileResponse(frame_path, media_type="image/jpeg")

