"""Tests for dynamic video upload and auto-configured default zones scaling."""
import time, cv2, numpy as np
from fastapi.testclient import TestClient
from main import app
from pathlib import Path

client = TestClient(app)


def create_synthetic_test_video(path: Path, width: int = 640, height: int = 480, fps: int = 30, frames: int = 15):
    """Generates a small valid MP4 test video with synthetic frames."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height))
    for i in range(frames):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        x = int(50 + (i / frames) * (width - 100))
        cv2.rectangle(img, (x, int(height * 0.5)), (x + 30, int(height * 0.5) + 30), (0, 255, 0), -1)
        writer.write(img)
    writer.release()


def test_no_sample_videos_exposed():
    """Verify that sample videos from data/videos folder are not exposed in GET /api/videos or default zones."""
    res = client.get("/api/videos")
    assert res.status_code == 200
    assert "intersection_03.mp4" not in [v["name"] for v in res.json()]

    z_res = client.get("/api/config/zones")
    assert z_res.status_code == 200
    assert z_res.json().get("video_file") != "intersection_01.mp4"


def test_default_zones_scaling():
    """Verify default zones are automatically generated and scaled to video resolution."""
    res = client.post("/api/config/zones/reset?video_file=arbitrary_test.mp4&width=1280&height=720")
    assert res.status_code == 200
    data = res.json()
    assert data["video_file"] == "arbitrary_test.mp4"
    assert "road" in data and len(data["road"]["polygon"]) == 4
    assert "crosswalks" in data and len(data["crosswalks"]) > 0
    xs = [p[0] for p in data["road"]["polygon"]]
    ys = [p[1] for p in data["road"]["polygon"]]
    assert max(xs) <= 1280 and max(ys) <= 720 and max(xs) > 640

    get_res = client.get("/api/config/zones?video_file=cctv_4k.mp4&width=3840&height=2160")
    assert get_res.status_code == 200
    assert max(p[0] for p in get_res.json()["road"]["polygon"]) <= 3840


def test_empty_video_name_pipeline_rejected():
    """Verify empty video name fails cleanly rather than attempting to open directory."""
    res = client.post("/api/pipeline/start", json={"video_name": "", "max_frames": 5})
    assert res.status_code == 200
    task_id = res.json()["task_id"]
    time.sleep(0.3)
    status_res = client.get(f"/api/pipeline/status/{task_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "failed" and "Video not found" in status_res.json()["error"]


def test_arbitrary_aspect_ratios_scaling():
    """Verify default zones correctly bound within vertical (9:16) and ultrawide (21:9) frames."""
    v_data = client.post("/api/config/zones/reset?video_file=vertical_cctv.mp4&width=720&height=1280").json()
    for pt in v_data["road"]["polygon"] + v_data["crosswalks"][0]["polygon"]:
        assert 0 <= pt[0] <= 720 and 0 <= pt[1] <= 1280

    u_data = client.post("/api/config/zones/reset?video_file=ultrawide_cctv.mp4&width=2560&height=1080").json()
    for pt in u_data["road"]["polygon"] + u_data["crosswalks"][0]["polygon"]:
        assert 0 <= pt[0] <= 2560 and 0 <= pt[1] <= 1080
