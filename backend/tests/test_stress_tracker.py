"""Adversarial stress tests for tracker: duplicate suppression and trajectory stitching."""
import numpy as np, pytest, supervision as sv
from types import SimpleNamespace
from services.cv.tracker import suppress_duplicate_bikes, RobustTrackerManager


def test_suppress_duplicate_bikes_extreme_cases():
    # Disjoint & identical
    b_dis = np.array([[10, 10, 50, 50], [100, 100, 150, 150], [10, 10, 50, 50]])
    d_dis = sv.Detections(xyxy=b_dis, class_id=np.array([3, 3, 3]), confidence=np.array([0.9, 0.8, 0.5]))
    res_dis = suppress_duplicate_bikes(d_dis)
    assert len(res_dis) == 2  # duplicate 3rd box suppressed

    # Nested sub-box: rider/sub-box completely nested in bike box
    b_nest = np.array([[100, 100, 300, 300], [150, 150, 200, 200]])  # IoU=0.06 < 0.25, but IoA=1.0 >= 0.40
    d_nest = sv.Detections(xyxy=b_nest, class_id=np.array([3, 1]), confidence=np.array([0.95, 0.40]))
    res_nest = suppress_duplicate_bikes(d_nest)
    assert len(res_nest) == 1 and res_nest.confidence[0] == 0.95

    # Zero area & inverted coordinates (graceful handling without crashes)
    b_edge = np.array([[0, 0, 0, 0], [10, 10, 10, 50], [100, 100, 50, 50], [200, 200, 250, 250]])
    d_edge = sv.Detections(xyxy=b_edge, class_id=np.array([3, 3, 3, 3]), confidence=np.array([0.9, 0.8, 0.7, 0.6]))
    res_edge = suppress_duplicate_bikes(d_edge)
    assert len(res_edge) >= 2  # Does not crash or suppress valid disjoint box

    # Preservation of non-bike classes
    d_mix = sv.Detections(xyxy=np.array([[0, 0, 50, 50], [0, 0, 50, 50], [10, 10, 60, 60], [10, 10, 60, 60]]),
                          class_id=np.array([3, 3, 2, 0]), confidence=np.array([0.9, 0.8, 0.7, 0.6]))
    res_mix = suppress_duplicate_bikes(d_mix)
    assert len(res_mix) == 3 and np.sum(res_mix.class_id == 3) == 1  # 1 bike duplicate removed, car and ped kept


def test_trajectory_stitching_gaps_and_velocity():
    mgr = RobustTrackerManager(max_reconnect_frames=25, max_reconnect_dist_px=180.0)
    # Consecutive frame update
    d0 = sv.Detections(xyxy=np.array([[100, 500, 150, 600]]), class_id=np.array([2]), tracker_id=np.array([1]))
    out0 = mgr.update_tracks(d0, frame_idx=0)
    cid0 = out0.tracker_id[0]

    # Stitched across valid gap of 20 frames with new raw tracker ID
    d20 = sv.Detections(xyxy=np.array([[120, 510, 170, 610]]), class_id=np.array([2]), tracker_id=np.array([50]))
    out20 = mgr.update_tracks(d20, frame_idx=20)
    assert out20.tracker_id[0] == cid0

    # Beyond max_reconnect_frames (gap = 30 > 25): must not stitch
    d50 = sv.Detections(xyxy=np.array([[125, 515, 175, 615]]), class_id=np.array([2]), tracker_id=np.array([99]))
    out50 = mgr.update_tracks(d50, frame_idx=50)
    assert out50.tracker_id[0] != cid0


def test_tracker_rapid_turn_and_out_of_order():
    mgr = RobustTrackerManager()
    # Trajectory going east, then reversing abruptly west
    for f in range(5):
        d = sv.Detections(xyxy=np.array([[100 + f * 30, 400, 140 + f * 30, 480]]),
                          class_id=np.array([3]), tracker_id=np.array([1]))
        mgr.update_tracks(d, frame_idx=f)
    # Frame 6: raw tracker drop, vehicle reverses direction
    d_rev = sv.Detections(xyxy=np.array([[200, 400, 240, 480]]), class_id=np.array([3]), tracker_id=np.array([2]))
    out_rev = mgr.update_tracks(d_rev, frame_idx=6)
    assert out_rev.tracker_id[0] == 1  # Reconnected within distance threshold

    # Out-of-order frame (historical timestamp)
    d_past = sv.Detections(xyxy=np.array([[110, 400, 150, 480]]), class_id=np.array([3]), tracker_id=np.array([77]))
    out_past = mgr.update_tracks(d_past, frame_idx=2)
    assert out_past.tracker_id[0] > 0  # Gracefully handled without crash


def test_tracker_perspective_extremes_and_pruning():
    cfg = SimpleNamespace(axis="y", y_top=0.1, y_bottom=1.0, weight_top=0.35, weight_bottom=1.0)
    mgr = RobustTrackerManager(max_reconnect_frames=10, perspective_cfg=cfg, frame_height=2160.0)

    # Extreme positions (y=0 horizon, y=2160 foreground, negative, beyond height)
    boxes = np.array([[100, 0, 150, 10], [100, 2100, 150, 2160], [-50, -100, 0, -20], [200, 3000, 250, 3100]])
    d_ext = sv.Detections(xyxy=boxes, class_id=np.array([2, 2, 2, 2]), tracker_id=np.array([10, 11, 12, 13]))
    out_ext = mgr.update_tracks(d_ext, frame_idx=0)
    assert len(out_ext.tracker_id) == 4

    # Pruning: advance 30 frames without detections
    for f in range(1, 35):
        mgr.update_tracks(sv.Detections.empty(), frame_idx=f)
    # Old tracks pruned (missed_count > max_reconnect_frames * 2 = 20)
    assert len(mgr.tracks) == 0
