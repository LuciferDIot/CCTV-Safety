"""Application service coordinating background video analysis jobs and live HUD telemetry."""
import uuid, time, threading, json
from typing import Dict, Any, Optional
from pathlib import Path
import cv2
from config import Settings
from views.pipeline_views import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD
from services.cv.engine import IntersectionSafetyPipeline


class PipelineService:
    """Coordinates asynchronous video processing jobs and real-time execution telemetry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.cancel_events: Dict[str, threading.Event] = {}
        self.telemetry = TelemetryHUD(active_model=settings.model_name)

    def _save_task(self, t: Dict[str, Any]) -> None:
        try:
            p = self.settings.resolve(self.settings.output_dir) / "tasks"
            p.mkdir(parents=True, exist_ok=True)
            with open(p / f"{t['task_id']}.json", "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in t.items() if k != "cancel_evt"}, f)
        except Exception: pass

    def start_job(self, req: PipelineRunRequest) -> str:
        """Launches video analysis in a daemon background thread and returns task ID."""
        task_id, cancel_evt = str(uuid.uuid4())[:8], threading.Event()
        self.cancel_events[task_id] = cancel_evt
        t: Dict[str, Any] = {
            "task_id": task_id, "status": "running", "progress_pct": 0.0,
            "current_frame": 0, "total_frames": req.max_frames or 300,
            "start_time": time.time(), "elapsed_seconds": 0.0, "fps": 0.0,
            "eta_seconds": None, "events_detected": 0, "output_video": None, "error": None
        }
        self.tasks[task_id] = t
        self._save_task(t)
        threading.Thread(target=self._run_job, args=(t, cancel_evt, req), daemon=True).start()
        return task_id

    def cancel_job(self, task_id: str) -> Optional[PipelineStatusResponse]:
        if self.cancel_events.get(task_id): self.cancel_events[task_id].set()
        return self.get_task_status(task_id)

    def get_task_status(self, task_id: str) -> Optional[PipelineStatusResponse]:
        t = self.tasks.get(task_id)
        if not t:
            p = self.settings.resolve(self.settings.output_dir) / "tasks" / f"{task_id}.json"
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f: t = json.load(f)
                    if t.get("status") == "running" and task_id not in self.cancel_events:
                        t["status"], t["error"] = "failed", "Server process reloaded"
                    self.tasks[task_id] = t
                except Exception: pass
        if not t: return None
        return PipelineStatusResponse(
            task_id=task_id, status=t["status"], progress_pct=t["progress_pct"],
            current_frame=t["current_frame"], total_frames=t["total_frames"], fps=t.get("fps", 0.0),
            elapsed_seconds=t["elapsed_seconds"], eta_seconds=t.get("eta_seconds"),
            events_detected=t["events_detected"], output_video=t.get("output_video"), error=t["error"]
        )

    def get_live_telemetry(self) -> TelemetryHUD:
        return self.telemetry

    def _run_job(self, task: Dict[str, Any], cancel_evt: threading.Event, req: PipelineRunRequest) -> None:
        """Executes frame-by-frame analysis pipeline with periodic telemetry updates."""
        try:
            v_dir, out_dir = self.settings.resolve(self.settings.videos_dir), self.settings.resolve(self.settings.output_dir)
            safe_name = Path(req.video_name).name
            video_path = v_dir / safe_name if (v_dir / safe_name).exists() else out_dir / safe_name
            if not video_path.exists(): raise FileNotFoundError(f"Video not found: {req.video_name}")

            cap = cv2.VideoCapture(str(video_path))
            frames_to_run = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 300), req.max_frames or 300)
            task["total_frames"], out_vid = frames_to_run, f"annotated_{safe_name}"
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            writer = cv2.VideoWriter(str(out_dir / out_vid), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

            pipeline = IntersectionSafetyPipeline(
                config_path=self.settings.resolve(self.settings.config_file),
                model_path=self.settings.resolve(self.settings.model_weights),
                output_dir=out_dir, device=req.device, imgsz=req.imgsz, override_zones=req.zones
            )
            for f_idx in range(frames_to_run):
                if cancel_evt.is_set():
                    task["status"] = "cancelled"; break
                ret, frame = cap.read()
                if not ret: break
                annotated = pipeline.process_frame(frame, f_idx, frames_to_run)
                if writer.isOpened(): writer.write(annotated)
                elapsed = round(time.time() - task["start_time"], 1)
                task.update({"current_frame": f_idx + 1, "progress_pct": round(((f_idx + 1) / frames_to_run) * 100, 1),
                             "elapsed_seconds": elapsed, "fps": round((f_idx + 1) / elapsed, 1) if elapsed > 0 else 30.0})
            cap.release(); writer.release()
            events, _ = pipeline.finalize()
            task["events_detected"], task["output_video"] = len(events), out_vid
            if events or not (out_dir / "detected_events.json").exists():
                ev_data = {"version": "1.0", "total_events": len(events), "events": [e.to_dict() if hasattr(e, "to_dict") else e for e in events]}
                with open(out_dir / "detected_events.json", "w", encoding="utf-8") as f: json.dump(ev_data, f, indent=2)
            if not cancel_evt.is_set(): task["status"], task["progress_pct"] = "completed", 100.0
        except Exception as e:
            task["status"], task["error"] = "failed", str(e)
        finally:
            self._save_task(task)
