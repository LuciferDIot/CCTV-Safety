"""Schemas for pipeline execution control and real-time HUD telemetry."""
from typing import Optional
from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    """Parameters for running the video analysis pipeline."""
    video_name: str = "intersection_01.mp4"
    model_name: Optional[str] = None
    device: Optional[str] = None  # cpu or cuda
    imgsz: int = Field(default=960, ge=320, le=1920)
    save_annotated_video: bool = True


class PipelineStatusResponse(BaseModel):
    """Current execution status of an active analysis job."""
    task_id: str
    status: str  # idle, running, completed, failed
    progress_pct: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    elapsed_seconds: float = 0.0
    events_detected: int = 0
    error: Optional[str] = None


class TelemetryHUD(BaseModel):
    """Live telemetry HUD metrics matching the dashboard pills."""
    fps: float = 28.4
    active_tracks: int = 14
    stitched_ids: int = 2
    latency_ms: float = 31.0
    active_model: str = "YOLO11m + ByteTrack + Temporal FSM"

