"""Tests for in-memory zone override retention and degenerate polygon resilience."""
import time
from fastapi.testclient import TestClient
from main import app
from config import get_settings
from tests.test_dynamic_upload_and_zones import create_synthetic_test_video

client = TestClient(app)


def test_pipeline_in_memory_override_stem_matching_without_request_zones(tmp_path):
    """Verify in-memory override is preserved during pipeline run even when zones payload is omitted."""
    settings = get_settings()
    out_dir = settings.resolve(settings.output_dir)
    uploads_dir = settings.resolve("data/uploads")
    test_video_path = tmp_path / "stem_match_test.mp4"
    create_synthetic_test_video(test_video_path, width=640, height=480, frames=5)

    try:
        with open(test_video_path, "rb") as f:
            assert client.post("/api/videos/upload", files={"file": ("stem_match_test.mp4", f, "video/mp4")}).status_code == 200

        custom_cfg = client.get("/api/config/zones?video_file=stem_match_test.mp4&width=640&height=480").json()
        custom_cfg["camera_id"] = "cam_custom_calibrated"
        custom_cfg["road"]["polygon"] = [[50, 50], [550, 50], [550, 400], [50, 400]]
        assert client.put("/api/config/zones", json=custom_cfg).status_code == 200

        start_res = client.post("/api/pipeline/start", json={"video_name": "stem_match_test.mp4", "max_frames": 2})
        assert start_res.status_code == 200
        task_id = start_res.json()["task_id"]

        for _ in range(40):
            st = client.get(f"/api/pipeline/status/{task_id}").json()["status"]
            if st in ("completed", "failed", "cancelled"): break
            time.sleep(0.15)
        assert st == "completed"
    finally:
        (uploads_dir / "stem_match_test.mp4").unlink(missing_ok=True)
        (out_dir / "stem_match_test_annotated.mp4").unlink(missing_ok=True)
        (out_dir / "events_stem_match_test.json").unlink(missing_ok=True)


def test_degenerate_polygon_fallback_robustness(tmp_path):
    """Verify degenerate/incomplete polygons (fewer than 3 vertices) fall back safely to defaults."""
    settings = get_settings()
    out_dir = settings.resolve(settings.output_dir)
    uploads_dir = settings.resolve("data/uploads")
    test_video_path = tmp_path / "degen_poly_test.mp4"
    create_synthetic_test_video(test_video_path, width=640, height=480, frames=4)

    try:
        with open(test_video_path, "rb") as f:
            assert client.post("/api/videos/upload", files={"file": ("degen_poly_test.mp4", f, "video/mp4")}).status_code == 200

        degen_zones = {
            "camera_id": "cam_degen",
            "video_file": "degen_poly_test.mp4",
            "road": {"polygon": [[10, 10], [50, 50]]},
            "crosswalks": [{"id": "cw", "polygon": [[5, 5]]}]
        }
        start_res = client.post("/api/pipeline/start", json={"video_name": "degen_poly_test.mp4", "max_frames": 2, "zones": degen_zones})
        assert start_res.status_code == 200
        task_id = start_res.json()["task_id"]

        for _ in range(40):
            st = client.get(f"/api/pipeline/status/{task_id}").json()["status"]
            if st in ("completed", "failed", "cancelled"): break
            time.sleep(0.15)
        assert st == "completed"
    finally:
        (uploads_dir / "degen_poly_test.mp4").unlink(missing_ok=True)
        (out_dir / "degen_poly_test_annotated.mp4").unlink(missing_ok=True)
        (out_dir / "events_degen_poly_test.json").unlink(missing_ok=True)

