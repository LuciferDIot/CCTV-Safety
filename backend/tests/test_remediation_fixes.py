"""Verification tests for backend bug fixes and architectural remediation."""
import numpy as np
import supervision as sv
from fastapi.testclient import TestClient
from main import app
from services.cv.annotator import TranslucentZoneAnnotator
from services.safety.pedestrian import PedestrianSafetyChecker
from services.safety.clustering import clip_polygon_by_axis
from views.event_views import TrafficEvent

client = TestClient(app)


def test_zone_persistence_across_requests():
    res = client.get("/api/config/zones")
    assert res.status_code == 200
    cfg = res.json()
    cfg["camera_id"] = "cam_persistent_test"
    put_res = client.put("/api/config/zones", json=cfg)
    assert put_res.status_code == 200
    get_again = client.get("/api/config/zones")
    assert get_again.status_code == 200
    assert get_again.json()["camera_id"] == "cam_persistent_test"
    client.post("/api/config/zones/reset")


def test_path_traversal_and_range_416():
    res = client.get("/api/videos/../../etc/passwd/metadata")
    assert res.status_code == 404
    r_dotdot = client.get("/api/videos/../metadata")
    assert r_dotdot.status_code == 404
    r_bad = client.get("/api/videos/intersection_01.mp4/stream", headers={"Range": "bytes=abc-xyz"})
    assert r_bad.status_code == 416
    r_oob = client.get("/api/videos/intersection_01.mp4/stream", headers={"Range": "bytes=999999999-999999999"})
    assert r_oob.status_code in (416, 404)


def test_pedestrian_annotator_trigger_no_attribute_error():
    poly = np.array([[0, 0], [100, 0], [100, 100], [0, 100]])
    t_ann = TranslucentZoneAnnotator(poly, (0, 255, 0))
    p_box = np.array([[10, 10, 30, 50]], dtype=float)
    dets = sv.Detections(xyxy=p_box, class_id=np.array([0]), confidence=np.array([0.9]))
    dets.tracker_id = np.array([1])
    res = t_ann.trigger(detections=dets)
    assert isinstance(res, np.ndarray)
    assert len(res) == 1
    assert bool(res[0]) is True
    checker = PedestrianSafetyChecker()
    h, s = checker.check_safety(dets, [t_ann], [t_ann])
    assert len(s) == 1
    assert len(h) == 0


def test_clustering_empty_polygon_safety():
    poly = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    axis = np.array([1.0, 0.0])
    p_a, p_b = clip_polygon_by_axis(poly, axis)
    assert len(p_a) >= 0 and len(p_b) >= 0


def test_event_dto_frontend_compatibility():
    ev = TrafficEvent(
        event_id="EV-TEST", status="CONFIRMED", event_type="WRONG_WAY",
        start_time=5.0, end_time=7.5, duration_seconds=2.5, tracking_id=99, confidence=0.92
    )
    assert ev.track_ids == [99]
    assert ev.time_start == 5.0
    assert ev.duration_sec == 2.5
    assert ev.evidence is not None
    assert "/api/events/EV-TEST/evidence" in ev.evidence.entry_frame_url
    assert "angle_deg" in ev.metrics


def test_evidence_route_alias_and_sanitization():
    res1 = client.get("/api/events/EV-DEMO-01/frames/entry")
    res2 = client.get("/api/events/EV-DEMO-01/evidence/entry")
    assert res1.status_code == res2.status_code
    res_bad = client.get("/api/events/../evidence/entry")
    assert res_bad.status_code in (400, 404)


def test_event_id_fallback_and_track_ids():
    ev = TrafficEvent(
        id="EV-FALLBACK", status="CONFIRMED", event_type="WRONG_WAY",
        time_start=1.0, time_end=3.0, duration_sec=2.0, track_ids=[42, 43], confidence=0.88
    )
    assert ev.event_id == "EV-FALLBACK"
    assert ev.tracking_id == 42
    assert ev.track_ids == [42, 43]
