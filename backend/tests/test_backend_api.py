"""FastAPI endpoint integration tests."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_videos_endpoints():
    res = client.get("/api/videos")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_zones_crud():
    res = client.get("/api/config/zones")
    assert res.status_code == 200
    data = res.json()
    assert "road" in data
    assert "polygon" in data["road"]

    put_res = client.put("/api/config/zones", json=data)
    assert put_res.status_code == 200


def test_events_filtering():
    res = client.get("/api/events?status=CONFIRMED")
    assert res.status_code == 200
    events = res.json()
    assert all(e["status"] == "CONFIRMED" for e in events)

    res_json = client.get("/api/events/export/json")
    assert res_json.status_code == 200

    res_csv = client.get("/api/events/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]


def test_pipeline_telemetry_and_cancel():
    res = client.get("/api/pipeline/telemetry")
    assert res.status_code == 200
    assert "fps" in res.json()

    cancel_res = client.post("/api/pipeline/cancel/nonexistent")
    assert cancel_res.status_code == 404


def test_pipeline_start_and_status():
    start_res = client.post("/api/pipeline/start", json={"video_name": "intersection_01.mp4", "max_frames": 2})
    assert start_res.status_code == 200
    task_id = start_res.json()["task_id"]

    stat_res = client.get(f"/api/pipeline/status/{task_id}")
    assert stat_res.status_code == 200
    assert stat_res.json()["task_id"] == task_id
