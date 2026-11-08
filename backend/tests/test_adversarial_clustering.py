"""Adversarial stress tests for clustering.py: polygon clipping, polar sorting, and auto-clustering."""
import numpy as np
from services.safety.clustering import (
    safe_norm, sort_convex, compute_pca_axis, clip_polygon_by_axis, LaneAutoDetector
)


def test_safe_norm_zero_tiny_nan():
    """Test safe_norm fallback on zero vectors, sub-epsilon vectors, and NaNs."""
    assert np.allclose(safe_norm(np.array([0.0, 0.0])), [0.0, -1.0])
    assert np.allclose(safe_norm(np.array([1e-12, -1e-12])), [0.0, -1.0])
    assert np.allclose(safe_norm(np.array([float("nan"), 0.0])), [0.0, -1.0])
    assert np.allclose(safe_norm(np.array([3.0, 4.0])), [0.6, 0.8])


def test_sort_convex_edge_cases():
    """Test polar angle sorting on empty, small, duplicate, and collinear sets."""
    assert len(sort_convex(np.zeros((0, 2)))) == 0
    p1 = np.array([[5.0, 10.0]])
    assert np.allclose(sort_convex(p1), p1)
    p2 = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert np.allclose(sort_convex(p2), p2)

    dups = np.array([[10.0, 10.0]] * 5)
    res_dups = sort_convex(dups)
    assert len(res_dups) == 5 and not np.isnan(res_dups).any()

    collinear = np.array([[0.0, 0.0], [10.0, 10.0], [20.0, 20.0], [30.0, 30.0]])
    res_collinear = sort_convex(collinear)
    assert len(res_collinear) == 4 and not np.isnan(res_collinear).any()


def test_clip_polygon_by_axis_symmetric_and_diamond():
    """Test Sutherland-Hodgman polygon clipping on square, diamond through vertices, and collinear."""
    square = np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]])
    p_a, p_b = clip_polygon_by_axis(square, np.array([0.0, 1.0]))
    assert len(p_a) >= 3 and len(p_b) >= 3
    assert not np.isnan(p_a).any() and not np.isnan(p_b).any()

    diamond = np.array([[50.0, 0.0], [100.0, 50.0], [50.0, 100.0], [0.0, 50.0]])
    d_a, d_b = clip_polygon_by_axis(diamond, np.array([0.0, 1.0]))
    assert len(d_a) + len(d_b) > 0
    assert not np.isnan(d_a).any() and not np.isnan(d_b).any()


def test_compute_pca_axis_stability():
    """Test PCA dominant axis estimation for opposing flows and collinear flow vectors."""
    opposing = np.array([[0.0, 1.0], [0.0, -1.0]] * 10)
    axis = compute_pca_axis(opposing)
    assert not np.isnan(axis).any()
    assert abs(axis[1]) > 0.99


def test_lane_auto_detector_thresholds_and_clustering():
    """Test LaneAutoDetector observation gating, buffer capping, and directional clustering."""
    road = [[0.0, 0.0], [1000.0, 0.0], [1000.0, 1000.0], [0.0, 1000.0]]
    det = LaneAutoDetector(road, min_speed_px=3.0, min_observations=15)
    for _ in range(14):
        det.observe(500.0, 500.0, 0.0, 10.0)
    assert det.detect_lanes() == []

    # Below speed threshold
    for _ in range(20):
        det.observe(500.0, 500.0, 1.0, 1.0)  # speed < 3.0 px
    assert det.detect_lanes() == []

    # Unidirectional flow (resultant norm >= 0.75)
    det_uni = LaneAutoDetector(road, min_speed_px=3.0, min_observations=15)
    for _ in range(20):
        det_uni.observe(500.0, 500.0, 0.0, -10.0)
    uni_lanes = det_uni.detect_lanes()
    assert len(uni_lanes) == 1 and uni_lanes[0].id == "auto_lane_oneway"

    # Bidirectional opposing flow
    det_bi = LaneAutoDetector(road, min_speed_px=3.0, min_observations=15)
    for i in range(20):
        det_bi.observe(200.0 + i, 500.0, 0.0, 10.0)
        det_bi.observe(800.0 + i, 500.0, 0.0, -10.0)
    bi_lanes = det_bi.detect_lanes()
    assert len(bi_lanes) == 2
    assert {"auto_lane_a", "auto_lane_b"} == {l.id for l in bi_lanes}
