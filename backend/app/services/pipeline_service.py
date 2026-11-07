"""Pipeline task execution manager and real-time telemetry HUD provider."""
import uuid
import time
import threading
from typing import Dict, Any, Optional
from app.config import Settings
from app.schemas.pipeline import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD
from app.services.pipeline_runner import run_pipeline_inference


class PipelineService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.telemetry = TelemetryHUD(active_model=settings.model_name)

    def start_job(self, req: PipelineRunRequest) -> str:
        task_id = str(uuid.uuid4())[:8]
        cancel_evt = threading.Event()
        self.cancel_events[task_id] = cancel_evt
        task_dict: Dict[str, Any] = {
            "task_id": task_id, "status": "running", "progress_pct": 0.0,
            "current_frame": 0, "total_frames": req.max_frames or 300,
            "start_time": time.time(), "elapsed_seconds": 0.0, "fps": 0.0,
            "eta_seconds": None, "events_detected": 0, "output_video": None, "error": None
        }
        self.tasks[task_id] = task_dict

        thread = threading.Thread(
            target=run_pipeline_inference,
            args=(task_dict, cancel_evt, self.settings, req, self.telemetry),
            daemon=True
        )
        thread.start()
        return task_id

    def cancel_job(self, task_id: str) -> Optional[PipelineStatusResponse]:
        evt = self.cancel_events.get(task_id)
        if evt:
            evt.set()
        return self.get_task_status(task_id)

    def get_task_status(self, task_id: str) -> Optional[PipelineStatusResponse]:
        t = self.tasks.get(task_id)
        if not t:
            return None
        return PipelineStatusResponse(
            task_id=task_id, status=t["status"], progress_pct=t["progress_pct"],
            current_frame=t["current_frame"], total_frames=t["total_frames"],
            fps=t.get("fps", 0.0), elapsed_seconds=t["elapsed_seconds"],
            eta_seconds=t.get("eta_seconds"), events_detected=t["events_detected"],
            output_video=t.get("output_video"), error=t["error"]
        )

    def get_live_telemetry(self) -> TelemetryHUD:
        return self.telemetry
