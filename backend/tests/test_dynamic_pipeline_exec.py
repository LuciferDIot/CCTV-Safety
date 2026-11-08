"""Tests for dynamic pipeline execution and video upload with special characters."""
import time
from fastapi.testclient import TestClient
from main import app
from config import get_settings
from tests.test_dynamic_upload_and_zones import create_synthetic_test_video

client = TestClient(app)


def test_uppercase_and_spaces_in_video_name(tmp_path):
    """Verify that video files with uppercase extensions (.MOV) and spaces in filenames work dynamically."""
    settings = get_settings()
    out_dir, uploads_dir = settings.resolve(settings.output_dir), settings.resolve("data/uploads")
    test_video_path = tmp_path / "custom traffic clip.MOV"
    create_synthetic_test_video(test_video_path, width=800, height=600, frames=5)

    try:
        with open(test_video_path, "rb") as f:
            up = client.post("/api/videos/upload", files={"file": ("custom traffic clip.MOV", f, "video/quicktime")})
        assert up.status_code == 200 and up.json()["metadata"]["width"] == 800

        z_res = client.get("/api/config/zones?video_file=custom traffic clip_annotated.mp4&width=800&height=600")
        assert z_res.status_code == 200 and z_res.json()["camera_id"] == "cam_custom traffic clip"

        stream_res = client.get("/api/videos/custom%20traffic%20clip.MOV/stream", headers={"Range": "bytes=0-100"})
        assert stream_res.status_code in (200, 206)
    finally:
        (uploads_dir / "custom traffic clip.MOV").unlink(missing_ok=True)
        (out_dir / "custom traffic clip_annotated.mp4").unlink(missing_ok=True)
        (out_dir / "events_custom traffic clip.json").unlink(missing_ok=True)


def test_dynamic_video_upload_and_pipeline_execution(tmp_path):
    """End-to-end test: upload video, verify zones, run pipeline, verify output."""
    settings = get_settings()
    out_dir, uploads_dir = settings.resolve(settings.output_dir), settings.resolve("data/uploads")
    ev_json_path = out_dir / "detected_events.json"
    backup_ev = ev_json_path.read_text(encoding="utf-8") if ev_json_path.exists() else None

    test_video_path = tmp_path / "dynamic_cctv_test.mp4"
    create_synthetic_test_video(test_video_path, width=640, height=480, frames=10)

    try:
        with open(test_video_path, "rb") as f:
            assert client.post("/api/videos/upload", files={"file": ("dynamic_cctv_test.mp4", f, "video/mp4")}).status_code == 200

        list_res = client.get("/api/videos")
        assert list_res.status_code == 200 and "dynamic_cctv_test.mp4" in [v["name"] for v in list_res.json()]

        zones_cfg = client.get("/api/config/zones?video_file=dynamic_cctv_test.mp4&width=640&height=480").json()
        assert len(zones_cfg["crosswalks"]) > 0

        start_res = client.post("/api/pipeline/start", json={"video_name": "dynamic_cctv_test.mp4", "max_frames": 5, "zones": zones_cfg})
        assert start_res.status_code == 200
        task_id = start_res.json()["task_id"]

        status = "running"
        for _ in range(60):
            stat_res = client.get(f"/api/pipeline/status/{task_id}")
            status = stat_res.json()["status"]
            if status in ("completed", "failed", "cancelled"): break
            time.sleep(0.2)

        assert status == "completed" and stat_res.json()["output_video"] == "dynamic_cctv_test_annotated.mp4"
        annotated_path = out_dir / stat_res.json()["output_video"]
        assert annotated_path.exists() and annotated_path.stat().st_size > 0

        ev_res = client.get("/api/events?video_name=dynamic_cctv_test.mp4")
        assert ev_res.status_code == 200 and not any(e["event_id"] == "EV-101" for e in ev_res.json())
        assert client.get("/api/events/export/csv?video_name=dynamic_cctv_test.mp4").status_code == 200
    finally:
        (uploads_dir / "dynamic_cctv_test.mp4").unlink(missing_ok=True)
        (out_dir / "dynamic_cctv_test_annotated.mp4").unlink(missing_ok=True)
        (out_dir / "events_dynamic_cctv_test.json").unlink(missing_ok=True)
        if backup_ev is not None: ev_json_path.write_text(backup_ev, encoding="utf-8")

