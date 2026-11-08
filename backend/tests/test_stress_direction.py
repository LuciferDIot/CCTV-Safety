"""Empirical stress tests for direction vector alignment and streak logic."""
import math
import numpy as np
import supervision as sv
from services.safety.direction import DirectionChecker, get_motion_metrics


class MockPoint:
    def __init__(self, cx: float, cy: float):
        self.cx, self.cy = cx, cy


def test_direction_parallel_and_counterflow_alignment():
    checker = DirectionChecker(min_frames=3, min_sustained_frames=3, min_recent_speed=1.0, min_total_dist_px=5.0)
    perm = (0.0, 1.0)
    hist_parallel = [(100.0, 100.0 + i * 15.0) for i in range(5)]
    for f in range(5):
        c, s = checker._eval_vehicle(1, hist_parallel, perm, is_ambiguous=False, frame_idx=f)
        assert not c and not s

    hist_counter = [(100.0, 300.0 - i * 15.0) for i in range(5)]
    c1, s1 = checker._eval_vehicle(2, hist_counter, perm, is_ambiguous=False, frame_idx=1)
    assert not c1 and s1  # Streak 1
    c2, s2 = checker._eval_vehicle(2, hist_counter, perm, is_ambiguous=False, frame_idx=2)
    assert not c2 and s2  # Streak 2
    c3, s3 = checker._eval_vehicle(2, hist_counter, perm, is_ambiguous=False, frame_idx=3)
    assert c3 and s3  # Streak 3 -> Confirmed


def test_direction_perpendicular_and_lateral_maneuvers():
    checker = DirectionChecker(min_frames=3, min_sustained_frames=2, min_recent_speed=1.0, min_total_dist_px=5.0)
    perm = (0.0, 1.0)
    # Perpendicular motion
    hist_perp = [(100.0 + i * 15.0, 200.0) for i in range(5)]
    c, s = checker._eval_vehicle(3, hist_perp, perm, is_ambiguous=False, frame_idx=1)
    assert not c and not s

    # 120-degree angle (above -0.60 threshold)
    a120 = math.radians(120)
    h120 = [(100.0 + i * 15.0 * math.sin(a120), 200.0 + i * 15.0 * math.cos(a120)) for i in range(5)]
    assert not checker._eval_vehicle(4, h120, perm, False, 1)[1]

    # 150-degree angle (counterflow exceeds lateral)
    a150 = math.radians(150)
    h150 = [(100.0 + i * 15.0 * math.sin(a150), 200.0 + i * 15.0 * math.cos(a150)) for i in range(5)]
    assert checker._eval_vehicle(5, h150, perm, False, 1)[1]


def test_direction_stationary_and_streak_transitions():
    checker = DirectionChecker(min_frames=3, min_sustained_frames=2, min_recent_speed=2.0, min_total_dist_px=10.0)
    perm = (0.0, 1.0)
    # Stationary vehicle (streak remains 0)
    assert not checker._eval_vehicle(6, [(100.0, 100.0)] * 6, perm, False, 1)[1]
    assert checker.wrong_way_streaks[6] == 0

    # Streak increment then decay
    h_wrong = [(100.0, 200.0 - i * 15.0) for i in range(5)]
    checker._eval_vehicle(7, h_wrong, perm, False, 1)
    checker._eval_vehicle(7, h_wrong, perm, False, 2)
    assert checker.wrong_way_streaks[7] == 2
    h_legal = [(100.0, 100.0 + i * 15.0) for i in range(5)]
    checker._eval_vehicle(7, h_legal, perm, False, 3)
    assert checker.wrong_way_streaks[7] == 1
    checker._eval_vehicle(7, h_legal, perm, False, 4)
    assert checker.wrong_way_streaks[7] == 0
    checker._eval_vehicle(7, h_legal, perm, False, 5)
    assert checker.wrong_way_streaks[7] == 0


def test_direction_ambiguity_history_types_and_pruning():
    checker = DirectionChecker(min_frames=3, min_sustained_frames=2, min_recent_speed=1.0, min_total_dist_px=5.0)
    perm = (0.0, 1.0)
    hist = [(100.0, 200.0 - i * 15.0) for i in range(5)]
    checker._eval_vehicle(8, hist, perm, is_ambiguous=True, frame_idx=1)
    c2, s2 = checker._eval_vehicle(8, hist, perm, is_ambiguous=True, frame_idx=2)
    assert not c2 and s2
    c3, s3 = checker._eval_vehicle(8, hist, perm, is_ambiguous=False, frame_idx=3)
    assert c3 and s3

    # Object point representation and short history safety
    assert checker._eval_vehicle(9, [MockPoint(100.0, 200.0 - i * 15.0) for i in range(5)], perm, False, 1)[1]
    assert get_motion_metrics([]) == (0.0, 0.0, 0.0, 0.0, 0.0)

    # Cache pruning (> 300 tracks)
    for tid in range(100, 420):
        checker.last_detected_frame[tid] = 1
    active_history = {tid: hist for tid in range(350, 420)}
    dets = sv.Detections(xyxy=np.array([[0, 0, 10, 10]]), tracker_id=np.array([350]))
    checker.check_detections(dets, perm, active_history, frame_idx=2)
    assert len(checker.last_detected_frame) <= 71
