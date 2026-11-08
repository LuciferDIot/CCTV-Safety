"""CV Safety pipeline execution and live telemetry controller."""
from fastapi import APIRouter, Depends, HTTPException
from controllers.deps import get_pipeline_service
from services.pipeline_service import PipelineService
from views.pipeline_views import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/start", response_model=PipelineStatusResponse)
def start_pipeline(req: PipelineRunRequest, svc: PipelineService = Depends(get_pipeline_service)):
    task_id = svc.start_job(req)
    status = svc.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=500, detail="Failed to initialize task")
    return status


@router.get("/status/{task_id}", response_model=PipelineStatusResponse)
def get_status(task_id: str, svc: PipelineService = Depends(get_pipeline_service)):
    status = svc.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return status


@router.post("/cancel/{task_id}", response_model=PipelineStatusResponse)
def cancel_pipeline(task_id: str, svc: PipelineService = Depends(get_pipeline_service)):
    status = svc.cancel_job(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return status


@router.get("/telemetry", response_model=TelemetryHUD)
def get_telemetry(svc: PipelineService = Depends(get_pipeline_service)):
    return svc.get_live_telemetry()

