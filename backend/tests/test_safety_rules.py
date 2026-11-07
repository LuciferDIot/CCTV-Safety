"""Unit tests for direction analysis, vehicle classification, and crosswalk rules."""
import numpy as np
from src.safety.direction import DirectionChecker
from src.safety.classifier import classify_vehicle_type
from src.safety.crosswalk_rules import is_normal_lane_transit, classify_crosswalk_motion


def test_direction_checker_alignment():
    checker = DirectionChecker(min_frames=3, min_sustained_frames=2, min_recent_speed=1.0, min_total_dist_px=5.0)
    permitted = (0.0, 1.0)
    # Vehicle moving straight down (y increases) -> legal
    hist_legal = [(100, 100 + i * 10) for i in range(6)]
    conf_l, susp_l = checker._eval_vehicle(1, hist_legal, permitted, is_ambiguous=False, frame_idx=6)
    assert not conf_l
    assert not susp_l

    # Vehicle moving straight up (y decreases) against permitted (0, 1) -> wrong way
    hist_wrong = [(100, 200 - i * 10) for i in range(6)]
    # First frame suspect
    checker._eval_vehicle(2, hist_wrong, permitted, is_ambiguous=False, frame_idx=6)
    # Second frame confirmed sustained
    conf_w, susp_w = checker._eval_vehicle(2, hist_wrong, permitted, is_ambiguous=False, frame_idx=7)
    assert conf_w is True
    assert susp_w is True


def test_vehicle_type_classification():
    # Pedestrian
    assert classify_vehicle_type(0, np.array([100, 100, 150, 250])) == "Ped"
    # Bike / Motorcycle
    assert classify_vehicle_type(3, np.array([100, 100, 200, 250])) == "Bike"
    # Car
    assert classify_vehicle_type(2, np.array([100, 100, 600, 500])) == "Car"


def test_crosswalk_motion_rules():
    # Low speed -> exempt walking
    assert classify_crosswalk_motion(corr_speed=1.5, cw_dist_corr=10.0, min_passage_dist_px=80.0, max_walking_speed=2.5, min_riding_speed=5.0) == "EXEMPT_WALKING"
    # High speed -> crosswalk riding
    assert classify_crosswalk_motion(corr_speed=7.5, cw_dist_corr=100.0, min_passage_dist_px=80.0, max_walking_speed=2.5, min_riding_speed=5.0) == "CROSSWALK_RIDING"
    # Lane flow alignment
    assert is_normal_lane_transit(0.0, 10.0, [(0.0, 1.0)]) is True


def test_kmeans_lane_auto_clustering():
    from src.safety.lane_auto import LaneAutoDetector
    road = [[100, 100], [900, 100], [1000, 1000], [0, 1000]]
    detector = LaneAutoDetector(road_polygon=road, min_speed_px=2.0, min_observations=10)
    for i in range(15):
        detector.observe(200.0 + i, 500.0, 0.0, -10.0)
    for i in range(15):
        detector.observe(800.0 + i, 500.0, 0.0, 10.0)
    lanes = detector.detect_lanes()
    assert len(lanes) == 2
    flows = [l.permitted_unit_vector[1] for l in lanes]
    assert any(f < -0.8 for f in flows)
    assert any(f > 0.8 for f in flows)

