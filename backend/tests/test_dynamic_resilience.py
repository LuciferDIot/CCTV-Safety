"""Tests for events querying across uploads, case insensitivity, and unlink resilience."""
import json, time
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from config import get_settings
from services.pipeline_service import PipelineService
from views.pipeline_views import PipelineRunRequest
from tests.test_dynamic_upload_and_zones import create_synthetic_test_video

client = TestClient(app)


def test_events_service_scans_dynamic_uploads_and_get_by_id():
    """Verify GET /api/events and GET /api/events/{id} find events from dynamic uploaded videos."""
    settings = get_settings()
    out_dir = settings.resolve(settings.output_dir)
    ev_file = out_dir / "events_test_dyn_clip.json"
    mock_payload = {
        "version": "1.0", "video": "test_dyn_clip.mp4", "total_events": 1,
        "events": [{
            "id": "EV-DYNAMIC-77", "event_type": "CROSSWALK_RIDING",
            "start_time": 2.5, "end_time": 4.5, "tracking_id": 42,
            "confidence": 0.94, "details": "Motorcycle on crosswalk", "verdict": "CONFIRMED"
        }]
    }
    try:
        ev_file.write_text(json.dumps(mock_payload), encoding="utf-8")
        all_res = client.get("/api/events")
        assert all_res.status_code == 200 and "EV-DYNAMIC-77" in [e["event_id"] for e in all_res.json()]
        single_res = client.get("/api/events/EV-DYNAMIC-77")
        assert single_res.status_code == 200 and single_res.json()["tracking_id"] == 42
    finally:
        ev_file.unlink(missing_ok=True)


def test_case_insensitive_video_resolution(tmp_path):
    """Verify video path resolution handles case mismatches gracefully."""
    settings = get_settings()
    uploads_dir = settings.resolve("data/uploads")
    test_video_path = tmp_path / "case_test_vid.mp4"
    create_synthetic_test_video(test_video_path, width=400, height=300, frames=3)
    try:
        with open(test_video_path, "rb") as f:
            assert client.post("/api/videos/upload", files={"file": ("case_test_vid.mp4", f, "video/mp4")}).status_code == 200
        meta_res = client.get("/api/videos/CASE_TEST_VID.MP4/metadata")
        assert meta_res.status_code == 200 and meta_res.json()["width"] == 400
    finally:
        (uploads_dir / "case_test_vid.mp4").unlink(missing_ok=True)


def test_pipeline_raw_tmp_permission_error_resilience(tmp_path):
    """Verify that PermissionError during tmp video unlink does not crash worker."""
    settings = get_settings()
    uploads_dir = settings.resolve("data/uploads")
    test_video_path = tmp_path / "lock_resilience_test.mp4"
    create_synthetic_test_video(test_video_path, width=320, height=240, frames=5)
    with open(test_video_path, "rb") as f:
        assert client.post("/api/videos/upload", files={"file": ("lock_resilience_test.mp4", f, "video/mp4")}).status_code == 200

    ps = PipelineService(settings)
    orig_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if str(self).endswith(".tmp.mp4"): raise PermissionError("[WinError 32] Locked")
        return orig_unlink(self, *args, **kwargs)

    try:
        with patch.object(Path, "unlink", mock_unlink):
            tid = ps.start_job(PipelineRunRequest(video_name="lock_resilience_test.mp4", max_frames=5))
            for _ in range(30):
                st = ps.get_task_status(tid)
                if st and st.status in ("completed", "failed"): break
                time.sleep(0.1)
            assert st is not None and st.status == "completed"
    finally:
        (uploads_dir / "lock_resilience_test.mp4").unlink(missing_ok=True)
        out_dir = settings.resolve(settings.output_dir)
        (out_dir / "lock_resilience_test_annotated.mp4").unlink(missing_ok=True)
        (out_dir / "events_lock_resilience_test.json").unlink(missing_ok=True)
        (out_dir / "lock_resilience_test.tmp.mp4").unlink(missing_ok=True)

