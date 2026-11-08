"""Stress and boundary tests for PipelineService, EventService, and ZoneService."""
import threading, time, unittest.mock as mock
import cv2, pytest
from fastapi import HTTPException
from config import Settings
from services.pipeline_service import PipelineService
from services.event_service import EventService
from services.zone_service import ZoneService
from views.pipeline_views import PipelineRunRequest
from views.zone_views import IntersectionZonesConfig


def test_pipeline_service_error_and_querying():
    """Verifies error handling on missing video and querying non-existent tasks."""
    ps = PipelineService(Settings())
    assert ps.get_task_status("invalid_id") is None and ps.cancel_job("invalid_id") is None
    assert ps.get_live_telemetry().active_model == "yolo11m.pt"

    req = PipelineRunRequest(video_name="missing_video_99.mp4", max_frames=20)
    tid = ps.start_job(req)
    time.sleep(0.4)
    st = ps.get_task_status(tid)
    assert st.status == "failed" and "Video not found" in st.error


def test_pipeline_service_mock_capture_failure():
    """Verifies pipeline terminates cleanly when cv2.VideoCapture read fails on frame 0."""
    settings = Settings()
    dummy = settings.resolve("data/uploads") / "mock_cap_fail_temp.mp4"
    dummy.write_bytes(b"temp_video_bytes")
    ps = PipelineService(settings)
    class MockCap:
        def __init__(self, *a, **kw): pass
        def get(self, prop): return 100 if prop == cv2.CAP_PROP_FRAME_COUNT else 30.0
        def read(self): return False, None
        def release(self): pass

    try:
        with mock.patch("cv2.VideoCapture", MockCap):
            tid = ps.start_job(PipelineRunRequest(video_name="mock_cap_fail_temp.mp4", max_frames=10))
            for _ in range(25):
                st = ps.get_task_status(tid)
                if st.status in ("completed", "failed"): break
                time.sleep(0.1)
            assert st.status == "completed" and st.current_frame == 0
    finally:
        dummy.unlink(missing_ok=True)
        (settings.resolve("data/output") / "mock_cap_fail_temp_annotated.mp4").unlink(missing_ok=True)


@pytest.mark.parametrize("eid,ft,expect_400", [
    ("..", "start", True), (".", "mid", True), ("", "end", True),
    ("../../etc/passwd", "..", True), ("../../etc/passwd", "", True),
    ("../../etc/passwd", "start", False), ("C:\\Windows\\System32", "mid", False)
])
def test_event_service_path_traversal_sanitization(eid: str, ft: str, expect_400: bool):
    """Verifies path traversal attempts are rejected or sanitized without directory breakout."""
    es = EventService(Settings())
    if expect_400:
        with pytest.raises(HTTPException) as exc: es.get_evidence_frame(eid, ft)
        assert exc.value.status_code == 400
    else:
        try:
            res = es.get_evidence_frame(eid, ft)
            assert "reference_frames" in str(res) or "evidence_cards" in str(res)
        except HTTPException as exc: assert exc.status_code == 404


def test_event_service_to_schema_fallback_robustness():
    """Verifies key fallback across missing start_ts, end_ts, duration_s, and track_ids."""
    es = EventService(Settings())
    ev1 = es._to_schema({"id": "EV-99", "start_time": 4.5, "end_time": 9.5, "tracking_id": 7})
    assert ev1.event_id == "EV-99" and ev1.start_time == 4.5 and ev1.duration_seconds == 5.0 and ev1.tracking_id == 7
    ev2 = es._to_schema({"track_ids": [15, 16], "duration_sec": 3.2, "verdict": "EXEMPT"})
    assert ev2.tracking_id == 15 and ev2.track_ids == [15, 16] and ev2.status == "EXEMPT"
    ev3 = es._to_schema({})
    assert ev3.event_id == "EV-00" and ev3.start_time == 0.0 and ev3.tracking_id == 0


def test_zone_service_singleton_override_and_restoration():
    """Verifies class-level override propagation, concurrency, and reset restoration."""
    zs1, zs2 = ZoneService(Settings()), ZoneService(Settings())
    mod_cfg = IntersectionZonesConfig(**{**zs1.get_config().model_dump(), "camera_id": "cam_calibrated"})
    errors = []

    def writer():
        for _ in range(30): zs1.update_config(mod_cfg); time.sleep(0.001)
    def reader():
        for _ in range(30):
            if zs2.get_config().camera_id not in ("cam_01", "cam_calibrated"): errors.append("mismatch")
            time.sleep(0.001)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader), threading.Thread(target=reader)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(errors) == 0
    restored = zs1.reset_config()
    assert restored.camera_id == "cam_01" and ZoneService._shared_override is None
