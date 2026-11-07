"""Pipeline task execution manager and real-time telemetry HUD provider."""
import uuid, time, asyncio
from typing import Dict, Any, Optional
from app.config import Settings
from app.schemas.pipeline import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD


class PipelineService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.telemetry = TelemetryHUD(active_model=settings.model_name)

    def start_job(self, req: PipelineRunRequest) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {
            "task_id": task_id, "status": "running", "progress_pct": 5.0,
            "current_frame": 15, "total_frames": 300, "start_time": time.time(),
            "elapsed_seconds": 0.5, "events_detected": 0, "error": None
        }
        asyncio.create_task(self._simulate_execution(task_id, req))
        return task_id

    async def _simulate_execution(self, task_id: str, req: PipelineRunRequest) -> None:
        task = self.tasks.get(task_id)
        if not task:
            return
        try:
            for step in range(1, 11):
                await asyncio.sleep(0.3)
                task["progress_pct"] = step * 10.0
                task["current_frame"] = step * 30
                task["elapsed_seconds"] = round(time.time() - task["start_time"], 2)
                task["events_detected"] = 2 if step > 5 else 1
            task["status"] = "completed"
            task["progress_pct"] = 100.0
        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)

    def get_task_status(self, task_id: str) -> Optional[PipelineStatusResponse]:
        t = self.tasks.get(task_id)
        if not t:
            return None
        return PipelineStatusResponse(
            task_id=task_id, status=t["status"], progress_pct=t["progress_pct"],
            current_frame=t["current_frame"], total_frames=t["total_frames"],
            elapsed_seconds=t["elapsed_seconds"], events_detected=t["events_detected"], error=t["error"]
        )

    def get_live_telemetry(self) -> TelemetryHUD:
        return self.telemetry

