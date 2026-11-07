"""Worker function for running CV pipeline inference and saving H.264 video."""
import time
import threading
from typing import Dict, Any
from pathlib import Path
import cv2
import av
from app.config import Settings
from app.schemas.pipeline import PipelineRunRequest, TelemetryHUD
from src.pipeline.pipeline import IntersectionSafetyPipeline


def _resolve_video(settings: Settings, name: str) -> Path:
    p1 = settings.resolve(settings.videos_dir) / name
    p2 = settings.resolve(settings.output_dir) / name
    return p1 if p1.exists() else p2


def run_pipeline_inference(
    task: Dict[str, Any], cancel_event: threading.Event,
    settings: Settings, req: PipelineRunRequest, telemetry: TelemetryHUD
) -> None:
    try:
        video_path = _resolve_video(settings, req.video_name)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_in_vid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 300)
        frames_to_run = min(total_in_vid, req.max_frames) if req.max_frames else total_in_vid
        task["total_frames"] = frames_to_run

        out_dir = settings.resolve(settings.output_dir)
        out_name = f"{video_path.stem}_annotated.mp4"
        out_path = out_dir / out_name

        container = av.open(str(out_path), mode="w")
        stream = container.add_stream("h264", rate=int(fps))
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"

        pipeline = IntersectionSafetyPipeline(
            config_path=settings.resolve(settings.config_file),
            model_path=settings.resolve(settings.model_weights),
            output_dir=out_dir, device=req.device, imgsz=req.imgsz
        )

        for f_idx in range(frames_to_run):
            if cancel_event.is_set():
                task["status"] = "cancelled"
                break
            ret, frame = cap.read()
            if not ret:
                break
            annotated = pipeline.process_frame(frame, f_idx, frames_to_run)
            av_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
            for pkt in stream.encode(av_frame):
                container.mux(pkt)

            elapsed = round(time.time() - task["start_time"], 1)
            inst_fps = round((f_idx + 1) / elapsed, 1) if elapsed > 0 else fps
            task["current_frame"] = f_idx + 1
            task["progress_pct"] = round(((f_idx + 1) / frames_to_run) * 100, 1)
            task["elapsed_seconds"] = elapsed
            task["fps"] = inst_fps
            task["eta_seconds"] = round((frames_to_run - (f_idx + 1)) / inst_fps, 1) if inst_fps > 0 else 0.0
            task["events_detected"] = len(pipeline.event_verifier.confirmed_events)

        if not cancel_event.is_set():
            pipeline.finalize()
            task["status"] = "completed"
            task["progress_pct"] = 100.0
            task["output_video"] = out_name
            telemetry.fps = task["fps"]
            telemetry.active_tracks = len(pipeline.tracker.tracks)

        for pkt in stream.encode():
            container.mux(pkt)
        container.close()
        cap.release()
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
