"""Application service coordinating background video analysis jobs and live HUD telemetry."""
import uuid, time, threading, json, cv2
from pathlib import Path
from typing import Dict, Any, Optional
from config import Settings
from views.pipeline_views import PipelineRunRequest, PipelineStatusResponse, TelemetryHUD
from services.cv.engine import IntersectionSafetyPipeline
from services.cv.remux import remux_h264
from services.zone_service import ZoneService

class PipelineService:
    """Coordinates asynchronous video processing jobs and real-time execution telemetry."""
    def __init__(self, settings: Settings):
        self.settings, self.tasks, self.cancel_events = settings, {}, {}
        self.telemetry = TelemetryHUD(active_model=settings.model_name)

    def _save_task(self, t: Dict[str, Any]) -> None:
        try:
            p = self.settings.resolve(self.settings.output_dir) / "tasks"; p.mkdir(parents=True, exist_ok=True); (p / f"{t['task_id']}.json").write_text(json.dumps({k: v for k, v in t.items() if k != "cancel_evt"}), encoding="utf-8")
        except Exception: pass

    def start_job(self, req: PipelineRunRequest) -> str:
        task_id, cancel_evt = str(uuid.uuid4())[:8], threading.Event()
        self.cancel_events[task_id] = cancel_evt
        t: Dict[str, Any] = {"task_id": task_id, "status": "running", "progress_pct": 0.0, "current_frame": 0, "total_frames": req.max_frames or 300, "start_time": time.time(), "elapsed_seconds": 0.0, "fps": 0.0, "eta_seconds": None, "events_detected": 0, "output_video": None, "error": None}
        self.tasks[task_id] = t
        self._save_task(t)
        threading.Thread(target=self._run_job, args=(t, cancel_evt, req), daemon=True).start()
        return task_id

    def cancel_job(self, task_id: str) -> Optional[PipelineStatusResponse]:
        if self.cancel_events.get(task_id): self.cancel_events[task_id].set()
        return self.get_task_status(task_id)

    def get_task_status(self, task_id: str) -> Optional[PipelineStatusResponse]:
        t, p = self.tasks.get(task_id), self.settings.resolve(self.settings.output_dir) / "tasks" / f"{task_id}.json"
        if not t and p.exists():
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
                if t.get("status") == "running" and task_id not in self.cancel_events: t["status"], t["error"] = "failed", "Server process reloaded"
                self.tasks[task_id] = t
            except Exception: pass
        return PipelineStatusResponse(task_id=task_id, status=t["status"], progress_pct=t["progress_pct"], current_frame=t["current_frame"], total_frames=t["total_frames"], fps=t.get("fps", 0.0), elapsed_seconds=t["elapsed_seconds"], eta_seconds=t.get("eta_seconds"), events_detected=t["events_detected"], output_video=t.get("output_video"), error=t["error"]) if t else None

    def get_live_telemetry(self) -> TelemetryHUD: return self.telemetry

    def _prepare_zones(self, req_zones: Optional[Dict[str, Any]], safe_name: str, safe_stem: str, w: int, h: int, fps: float) -> Dict[str, Any]:
        ovr = ZoneService._shared_override; ovr_stem = Path(ovr.video_file).stem.replace("_annotated", "").replace("annotated_", "") if (ovr and ovr.video_file) else ""
        cfg = dict(req_zones) if req_zones else (ovr.model_dump() if (ovr and (ovr_stem == safe_stem or not ovr_stem)) else {})
        d_cfg = ZoneService.create_default_zones(safe_name, w, h).model_dump()
        if not cfg: return d_cfg
        if not cfg.get("road") or not isinstance(cfg.get("road"), dict) or len(cfg["road"].get("polygon") or []) < 3: cfg["road"] = d_cfg["road"]
        if not cfg.get("crosswalks") or not isinstance(cfg.get("crosswalks"), list) or len(cfg["crosswalks"]) == 0 or any(len(c.get("polygon") or []) < 3 for c in cfg["crosswalks"] if isinstance(c, dict)): cfg["crosswalks"] = d_cfg["crosswalks"]
        cfg.setdefault("camera_id", f"cam_{safe_stem}"); cfg.setdefault("video_file", safe_name); cfg.setdefault("fps", fps); cfg.setdefault("perspective_scale_by_y", {"y_top": 0.1, "y_bottom": 1.0, "weight_top": 0.35, "weight_bottom": 1.0})
        return cfg

    def _run_job(self, task: Dict[str, Any], cancel_evt: threading.Event, req: PipelineRunRequest) -> None:
        raw_tmp, writer = None, None
        try:
            v_dir, u_dir, out_dir = self.settings.resolve(self.settings.videos_dir), self.settings.resolve("data/uploads"), self.settings.resolve(self.settings.output_dir)
            safe_name = Path(req.video_name).name if req.video_name else ""
            if not safe_name or safe_name in (".", ".."): raise FileNotFoundError(f"Video not found: '{req.video_name}'")
            v_p = next((c for c in [u_dir / safe_name, v_dir / safe_name, out_dir / safe_name] if c.is_file()), None) or next((f for d in [u_dir, v_dir, out_dir] if d.exists() for f in d.iterdir() if f.is_file() and f.name.lower() == safe_name.lower()), None)
            if not v_p: raise FileNotFoundError(f"Video not found: {req.video_name}")
            cap = cv2.VideoCapture(str(v_p))
            if hasattr(cap, "isOpened") and not cap.isOpened(): raise RuntimeError(f"Could not open video file: {v_p}")
            tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 300); frames_to_run = min(tot, req.max_frames) if (req.max_frames and req.max_frames > 0) else tot
            safe_stem = Path(safe_name).stem.replace("_annotated", "").replace("annotated_", ""); out_vid, raw_tmp, task["total_frames"] = f"{safe_stem}_annotated.mp4", out_dir / f"{safe_stem}.tmp.mp4", frames_to_run
            w, h, fps = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080), float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            writer = cv2.VideoWriter(str(raw_tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            zones_cfg = self._prepare_zones(req.zones, safe_name, safe_stem, w, h, fps)
            pipeline = IntersectionSafetyPipeline(self.settings.resolve(self.settings.config_file), self.settings.resolve(self.settings.model_weights), out_dir, req.device, req.imgsz, zones_cfg, frame_height=float(h))
            for f_idx in range(frames_to_run):
                if cancel_evt.is_set(): task["status"] = "cancelled"; break
                ret, frame = cap.read()
                if not ret or frame is None: break
                annotated = pipeline.process_frame(frame, f_idx, frames_to_run)
                if writer.isOpened(): writer.write(annotated)
                elapsed = round(time.time() - task["start_time"], 1)
                task.update({"current_frame": f_idx + 1, "progress_pct": round(((f_idx + 1) / max(1, frames_to_run)) * 100, 1), "elapsed_seconds": elapsed, "fps": round((f_idx + 1) / elapsed, 1) if elapsed > 0 else 30.0})
            cap.release(); (writer.release() if writer else None); writer = None
            if not cancel_evt.is_set():
                remux_h264(raw_tmp, out_dir / out_vid)
                events, _ = pipeline.finalize(); task["events_detected"], task["output_video"] = len(events), out_vid
                ev_str = json.dumps({"version": "1.0", "video": safe_name, "total_events": len(events), "events": [e.to_dict() if hasattr(e, "to_dict") else e for e in events]}, indent=2)
                (out_dir / f"events_{safe_stem}.json").write_text(ev_str, encoding="utf-8")
                task["status"], task["progress_pct"] = "completed", 100.0
        except Exception as e: task["status"], task["error"] = "failed", str(e)
        finally:
            if writer:
                try: writer.release()
                except Exception: pass
            if raw_tmp:
                for _ in range(5):
                    try:
                        if raw_tmp.exists(): raw_tmp.unlink(); break
                    except OSError: time.sleep(0.05)
            self._save_task(task)
