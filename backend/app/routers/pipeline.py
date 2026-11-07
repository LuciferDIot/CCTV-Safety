"""Pipeline execution triggers, progress status, and live telemetry HUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_pipeline_service
from app.services.pipeline_service import PipelineService
from app.schemas.pipeline import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/start", response_model=PipelineStatusResponse)
def start_pipeline(req: PipelineRunRequest, svc: PipelineService = Depends(get_pipeline_service)):
    """Trigger asynchronous video processing pipeline."""
    task_id = svc.start_job(req)
    status = svc.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=500, detail="Failed to initialize task")
    return status


@router.get("/status/{task_id}", response_model=PipelineStatusResponse)
def get_status(task_id: str, svc: PipelineService = Depends(get_pipeline_service)):
    """Query progress and frame metrics for an ongoing or completed job."""
    status = svc.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return status


@router.get("/telemetry", response_model=TelemetryHUD)
def get_telemetry(svc: PipelineService = Depends(get_pipeline_service)):
    """Live telemetry HUD pills for the top dashboard bar."""
    return svc.get_live_telemetry()

