"""Views (DTOs) for pipeline execution requests and progress telemetry."""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    video_name: str = "intersection_01.mp4"
    max_frames: Optional[int] = 300
    device: Optional[str] = "cpu"
    imgsz: int = 960
    zones: Optional[Dict[str, Any]] = None


class PipelineStatusResponse(BaseModel):
    task_id: str
    status: str = Field(description="running | completed | failed | cancelled")
    progress_pct: float
    current_frame: int
    total_frames: int
    fps: float
    elapsed_seconds: float
    eta_seconds: Optional[float] = None
    events_detected: int = 0
    output_video: Optional[str] = None
    error: Optional[str] = None


class TelemetryHUD(BaseModel):
    fps: float = 0.0
    active_tracks: int = 0
    stitched_ids: int = 0
    latency_ms: float = 0.0
    active_model: str = "YOLO11m + ByteTrack + Temporal FSM"

