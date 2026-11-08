"""Adversarial challenge tests for Milestone 2 CV services (tracker, annotator, model)."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pytest, supervision as sv
from services.cv.tracker import suppress_duplicate_bikes, RobustTrackerManager
from services.cv.annotator import TranslucentZoneAnnotator
from services.cv.model import load_detection_model


def test_bike_suppression_adversarial_matrix():
    # Empty, single, non-bike
    assert len(suppress_duplicate_bikes(sv.Detections.empty())) == 0
    d1 = sv.Detections(xyxy=np.array([[0, 0, 10, 10]]), class_id=np.array([3]))
    assert len(suppress_duplicate_bikes(d1)) == 1
    d_cars = sv.Detections(xyxy=np.array([[0, 0, 50, 50], [0, 0, 50, 50]]), class_id=np.array([2, 2]))
    assert len(suppress_duplicate_bikes(d_cars)) == 2

    # High IoU overlap
    d_iou = sv.Detections(xyxy=np.array([[0, 0, 100, 100], [50, 0, 150, 100]]), class_id=np.array([3, 3]), confidence=np.array([0.9, 0.8]))
    assert len(suppress_duplicate_bikes(d_iou)) == 1 and suppress_duplicate_bikes(d_iou).confidence[0] == 0.9

    # Nested sub-box (IoU=0.04 < 0.25, IoA=1.0 >= 0.40) & reverse confidence
    d_nest = sv.Detections(xyxy=np.array([[0, 0, 100, 100], [40, 40, 60, 60]]), class_id=np.array([3, 1]), confidence=np.array([0.9, 0.5]))
    assert len(suppress_duplicate_bikes(d_nest)) == 1
    d_rev = sv.Detections(xyxy=np.array([[0, 0, 100, 100], [40, 40, 60, 60]]), class_id=np.array([3, 3]), confidence=np.array([0.5, 0.95]))
    assert len(suppress_duplicate_bikes(d_rev)) == 1 and suppress_duplicate_bikes(d_rev).confidence[0] == 0.95


def test_tracker_spatiotemporal_cost_and_prediction():
    mgr = RobustTrackerManager(max_reconnect_frames=25, max_reconnect_dist_px=180.0)
    # Init 2 tracks at f0: T1 at x=300, T2 at x=400
    mgr.update_tracks(sv.Detections(xyxy=np.array([[290, 480, 310, 500], [390, 480, 410, 500]]), class_id=np.array([3, 3]), tracker_id=np.array([1, 2])), 0)
    for f in range(1, 9):
        mgr.update_tracks(sv.Detections(xyxy=np.array([[390, 480, 410, 500]]), class_id=np.array([3]), tracker_id=np.array([2])), f)

    # Frame 10: T1 gap=10 (pos 300), T2 gap=2 (pos 400). Det at x=345:
    # T1 cost = 45 + 10*2 = 65; T2 cost = 55 + 2*2 = 59 -> T2 fresher wins!
    out10 = mgr.update_tracks(sv.Detections(xyxy=np.array([[335, 480, 355, 500]]), class_id=np.array([3]), tracker_id=np.array([99])), 10)
    assert out10.tracker_id[0] == 2

    # Kinematic prediction extrapolation
    mgr_p = RobustTrackerManager()
    mgr_p.update_tracks(sv.Detections(xyxy=np.array([[10, 50, 30, 70]]), class_id=np.array([3]), tracker_id=np.array([1])), 0)
    mgr_p.update_tracks(sv.Detections(xyxy=np.array([[30, 50, 50, 70]]), class_id=np.array([3]), tracker_id=np.array([1])), 1)
    px, py = mgr_p.tracks[1].predict_next()
    assert abs(px - 60.0) < 1e-3 and abs(py - 70.0) < 1e-3


def test_tracker_scale_and_memory_bounding():
    cfg = SimpleNamespace(axis="y", y_top=0.0, y_bottom=1.0, weight_top=0.2, weight_bottom=1.0)
    mgr = RobustTrackerManager(max_reconnect_frames=5, max_reconnect_dist_px=100.0, frame_height=2000.0, perspective_cfg=cfg)
    # Horizon (y=10, scale=0.2, max_dist=20px). Det at dist=30px rejected
    mgr.update_tracks(sv.Detections(xyxy=np.array([[50, 0, 70, 10]]), class_id=np.array([3]), tracker_id=np.array([1])), 0)
    out_top = mgr.update_tracks(sv.Detections(xyxy=np.array([[80, 0, 100, 10]]), class_id=np.array([3]), tracker_id=np.array([2])), 1)
    assert out_top.tracker_id[0] != 1

    # Memory bounding: 501 detections across frames -> raw_to_canonical pruned from 501 down to <= 15
    mgr_mem = RobustTrackerManager(max_reconnect_frames=5, max_reconnect_dist_px=50.0)
    for f in range(501):
        x = 1000 + f * 500
        mgr_mem.update_tracks(sv.Detections(xyxy=np.array([[x, 500, x + 20, 520]]), class_id=np.array([2]), tracker_id=np.array([f])), f)
    assert len(mgr_mem.raw_to_canonical) <= 15


def test_translucent_annotator_and_model_resolution():
    # Valid vs degenerate polygons
    p_valid = [(10, 10), (100, 10), (100, 100), (10, 100)]
    ann_valid = TranslucentZoneAnnotator(p_valid, bgr_color=(0, 255, 0))
    scene = np.zeros((200, 200, 3), dtype=np.uint8)
    assert not np.array_equal(ann_valid.annotate(scene.copy()), scene)

    # Degenerate: 0, 1, 2 points
    for degen in [[], [(10, 10)], [(10, 10), (20, 20)]]:
        ann = TranslucentZoneAnnotator(degen, bgr_color=(0, 0, 255))
        assert ann._zone is None
        assert np.array_equal(ann.annotate(scene.copy()), scene)
        trig = ann.trigger(sv.Detections(xyxy=np.array([[15, 15, 25, 25]]), class_id=np.array([1])))
        assert len(trig) == 1 and not trig[0]

    # Model resolution ladder and name normalization
    m_default = load_detection_model(None, Path("."), "cpu")
    assert m_default is not None
    m_norm = load_detection_model(Path("models/yolov11m.pt"), Path("."), "cpu")
    assert m_norm is not None
