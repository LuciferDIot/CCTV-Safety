"""Stress and boundary tests for CV engine, HUD progress bar, and resolution scaling."""
import numpy as np
import pytest
from pathlib import Path
from services.cv.hud import draw_render_progress_bar
from services.cv.engine import IntersectionSafetyPipeline
from config import Settings


@pytest.mark.parametrize("w,h", [(1280, 720), (1920, 1080), (3840, 2160), (7680, 4320), (320, 240), (100, 100), (50, 50)])
def test_hud_resolution_scaling_and_dimensions(w: int, h: int):
    """Verifies HUD progress bar rendering across 720p, 1080p, 4K, 8K, and tiny frames."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    rendered = draw_render_progress_bar(frame, current_frame=50, total_frames=100)
    assert rendered.shape == (h, w, 3)
    assert rendered.dtype == np.uint8


@pytest.mark.parametrize("cur,tot", [(0, 100), (100, 100), (-25, 100), (250, 100), (0, 0), (15, -10), (-5, -5)])
def test_hud_progress_percentage_edge_cases(cur: int, tot: int):
    """Verifies HUD clamping on negative, overshooting, and degenerate frame counts."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    rendered = draw_render_progress_bar(frame.copy(), current_frame=cur, total_frames=tot)
    assert rendered.shape == frame.shape
    if tot <= 0:
        # Should return unaltered frame on zero or negative total frames
        assert np.array_equal(rendered, frame)


def test_cv_engine_record_deduplication_and_finalize():
    """Verifies event deduplication, timestamp calculation, and finalize state clearance."""
    settings = Settings()
    pipeline = IntersectionSafetyPipeline(
        config_path=settings.resolve(settings.config_file),
        model_path=settings.resolve(settings.model_weights),
        output_dir=settings.resolve(settings.output_dir),
        device="cpu", imgsz=320
    )
    # First detection of track 10
    pipeline._record(tid=10, etype="WRONG_WAY", frame_idx=0, conf=0.91, detail="Initial", zone="lane")
    assert len(pipeline.active_events) == 1
    ev = pipeline.active_events[(10, "WRONG_WAY")]
    assert ev.id == "EV-01" and ev.start_frame == 0 and ev.end_frame == 0

    # Continuous tracking across frame 15 (0.5s at 30 FPS)
    pipeline._record(tid=10, etype="WRONG_WAY", frame_idx=15, conf=0.91, detail="Update", zone="lane")
    assert len(pipeline.active_events) == 1
    assert ev.end_frame == 15 and ev.end_ts == 0.50

    # Finalize pipeline
    events, summary = pipeline.finalize()
    assert len(events) == 1
    assert summary["total_events"] == 1
    assert len(pipeline.active_events) == 0


def test_cv_engine_blank_frame_handling():
    """Verifies engine processes blank frame with zero detections without crashing."""
    settings = Settings()
    pipeline = IntersectionSafetyPipeline(
        config_path=settings.resolve(settings.config_file),
        model_path=settings.resolve(settings.model_weights),
        output_dir=settings.resolve(settings.output_dir),
        device="cpu", imgsz=320
    )
    blank = np.zeros((720, 1280, 3), dtype=np.uint8)
    rendered = pipeline.process_frame(blank, frame_idx=0, total_frames=10)
    assert rendered.shape == blank.shape
