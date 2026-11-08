"""Traffic safety violations and evidence card controller."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from controllers.deps import get_event_service
from services.event_service import EventService
from views.event_views import TrafficEvent

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=List[TrafficEvent])
def list_events(
    status: Optional[str] = Query(None, description="Filter: CONFIRMED, EXEMPT, INSUFFICIENT_EVIDENCE, IGNORED"),
    event_type: Optional[str] = Query(None, description="Filter: WRONG_WAY, CROSSWALK_RIDING, WALKING_MOTORCYCLE, etc."),
    track_id: Optional[int] = Query(None, description="Filter by motorcycle tracking ID"),
    video_name: Optional[str] = Query(None, description="Filter by video name"),
    include_demo: bool = Query(False, description="Include demo events"),
    svc: EventService = Depends(get_event_service)
):
    return svc.get_events(status=status, event_type=event_type, track_id=track_id, include_demo=include_demo, video_name=video_name)


@router.get("/export/csv")
def export_csv(
    video_name: Optional[str] = Query(None, description="Filter export by video name"),
    svc: EventService = Depends(get_event_service)
):
    csv_data = svc.export_csv(include_demo=False, video_name=video_name)
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=detected_events.csv"})


@router.get("/export/json", response_model=List[TrafficEvent])
def export_json(
    video_name: Optional[str] = Query(None, description="Filter export by video name"),
    svc: EventService = Depends(get_event_service)
):
    return svc.get_events(include_demo=False, video_name=video_name)


@router.get("/{event_id}", response_model=TrafficEvent)
def get_event(event_id: str, svc: EventService = Depends(get_event_service)):
    return svc.get_event_by_id(event_id)


@router.get("/{event_id}/frames/{frame_type}")
@router.get("/{event_id}/evidence/{frame_type}")
def get_evidence_frame(event_id: str, frame_type: str, svc: EventService = Depends(get_event_service)):
    frame_path = svc.get_evidence_frame(event_id, frame_type)
    return FileResponse(frame_path, media_type="image/jpeg")
