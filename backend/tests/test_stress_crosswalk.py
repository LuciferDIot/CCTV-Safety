"""Empirical stress tests for crosswalk safety rules and lane transit suppression."""
import numpy as np
import supervision as sv
from services.safety.crosswalk import (
    CrosswalkSafetyChecker, is_normal_lane_transit, classify_crosswalk_motion
)


def test_normal_lane_transit_suppression():
    lanes = [(0.0, 1.0)]
    assert is_normal_lane_transit(0.0, 10.0, lanes) is True
    assert is_normal_lane_transit(4.0, 10.0, lanes) is True
    assert is_normal_lane_transit(10.0, 0.0, lanes) is False
    assert is_normal_lane_transit(0.0, -10.0, lanes) is False
    assert is_normal_lane_transit(0.1, 0.2, lanes) is False
    assert is_normal_lane_transit(0.0, 10.0, []) is False
    assert is_normal_lane_transit(0.0, 10.0, None) is False
    assert is_normal_lane_transit(0.0, 10.0, [(0.0, 0.0)]) is False


def test_walking_speed_boundary_conditions():
    # Exactly at and below walking threshold 3.8 px/frame
    assert classify_crosswalk_motion(3.8, 50.0, 40.0, 3.8, 4.8) == "EXEMPT_WALKING"
    assert classify_crosswalk_motion(3.7999, 50.0, 40.0, 3.8, 4.8) == "EXEMPT_WALKING"
    assert classify_crosswalk_motion(0.0, 50.0, 40.0, 3.8, 4.8) == "EXEMPT_WALKING"

    # Just above walking threshold 3.8 px/frame
    assert classify_crosswalk_motion(3.8001, 50.0, 40.0, 3.8, 4.8) == "CROSSWALK_RIDING"
    assert classify_crosswalk_motion(3.8001, 20.0, 40.0, 3.8, 4.8) == "TRAVERSING_PRELIMINARY"

    # At or above min riding speed 4.8 px/frame
    assert classify_crosswalk_motion(4.8, 5.0, 40.0, 3.8, 4.8) == "CROSSWALK_RIDING"
    assert classify_crosswalk_motion(6.0, 5.0, 40.0, 3.8, 4.8) == "CROSSWALK_RIDING"


def test_crosswalk_checker_state_and_spatial_transitions():
    cw_poly = np.array([[100, 100], [500, 100], [500, 300], [100, 300]])
    checker = CrosswalkSafetyChecker([cw_poly], min_passage_dist_px=40.0, max_walking_speed=3.8, min_riding_speed=4.8, min_traversal_frames=5)
    lanes = [(0.0, 1.0)]

    # 1. Normal lane transit across paint is suppressed (returns None)
    bbox_start = np.array([150, 150, 200, 250])
    hist_lane = [(175.0, 150.0 + i * 20.0) for i in range(5)]
    assert checker._eval_bike(1, bbox_start, hist_lane, lanes) is None

    # 2. Stopped near crosswalk (speed < 1.5 or dist < 15)
    hist_stopped = [(175.0, 200.0 + i * 0.5) for i in range(5)]
    assert checker._eval_bike(2, bbox_start, hist_stopped, None) == "STOPPED_NEAR_CROSSWALK"

    # 3. Riding across crosswalk: frame 1 preliminary, frame 5 (> 40 px displacement) riding
    hist_cross = [(100.0 + i * 15.0, 200.0) for i in range(5)]
    for step in range(5):
        box_step = np.array([100 + step * 15, 150, 150 + step * 15, 250])
        res = checker._eval_bike(3, box_step, hist_cross, lanes)
    assert res == "CROSSWALK_RIDING"

    # 4. Dismounted walking across crosswalk (speed <= 3.8, dist >= 15.0)
    hist_walk = [(100.0 + i * 2.5, 200.0) for i in range(10)]
    for step in range(5):
        box_walk = np.array([100 + step * 10, 150, 150 + step * 10, 250])
        res_walk = checker._eval_bike(4, box_walk, hist_walk, lanes)
    assert res_walk == "EXEMPT_WALKING"

    # 5. Outside crosswalk polygon
    bbox_outside = np.array([600, 600, 650, 700])
    assert checker._eval_bike(5, bbox_outside, hist_cross, lanes) is None
    assert checker.frames_in_cw[5] == 0

    # 6. check_motorcycles API and cache pruning
    dets = sv.Detections(xyxy=np.array([[160, 150, 210, 250]]), class_id=np.array([3]), tracker_id=np.array([3]))
    for tid in range(100, 420):
        checker.frames_in_cw[tid] = 1
    out = checker.check_motorcycles(dets, {3: hist_cross}, frame_idx=10, lane_vectors=lanes)
    assert 3 in out
    assert len(checker.frames_in_cw) <= 2
