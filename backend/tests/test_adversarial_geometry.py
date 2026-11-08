"""Adversarial stress tests for geometry.py edge cases, boundaries, and precision."""
import math
import numpy as np
from services.safety.geometry import (
    point_to_segment_dist, compute_perspective_scale, get_box_geometry, get_ground_anchor
)


def test_point_to_segment_endpoints_and_collinear():
    """Test point on endpoints, collinear along segment, and collinear beyond endpoints."""
    a, b = (10.0, 20.0), (30.0, 20.0)
    assert math.isclose(point_to_segment_dist(a, a, b), 0.0)
    assert math.isclose(point_to_segment_dist(b, a, b), 0.0)
    assert math.isclose(point_to_segment_dist((20.0, 20.0), a, b), 0.0)
    assert math.isclose(point_to_segment_dist((5.0, 20.0), a, b), 5.0)
    assert math.isclose(point_to_segment_dist((40.0, 20.0), a, b), 10.0)
    assert math.isclose(point_to_segment_dist((20.0, 30.0), a, b), 10.0)


def test_point_to_segment_degenerate_zero_length():
    """Test degenerate segments where start == end."""
    p_zero = (15.0, 25.0)
    assert math.isclose(point_to_segment_dist((18.0, 29.0), p_zero, p_zero), 5.0)
    assert math.isclose(point_to_segment_dist(p_zero, p_zero, p_zero), 0.0)


def test_point_to_segment_extreme_scales_and_negatives():
    """Test large, tiny, and negative coordinates for numerical precision and no overflow."""
    large_a, large_b = (1e7, 1e7), (1e7 + 100.0, 1e7)
    assert math.isclose(point_to_segment_dist((1e7 + 50.0, 1e7 + 25.0), large_a, large_b), 25.0)
    tiny_a, tiny_b = (1e-7, 1e-7), (2e-7, 1e-7)
    assert math.isclose(point_to_segment_dist((1.5e-7, 1e-7), tiny_a, tiny_b), 0.0, abs_tol=1e-12)
    neg_a, neg_b = (-50.0, -100.0), (-50.0, 0.0)
    assert math.isclose(point_to_segment_dist((-30.0, -50.0), neg_a, neg_b), 20.0)


def test_perspective_scale_boundaries_and_clamping():
    """Test w(y) perspective scaling at frame boundaries, negative values, and overshoots."""
    class MockConfig:
        axis = "y"
        y_top = 0.2
        y_bottom = 0.8
        weight_top = 0.35
        weight_bottom = 1.0

    cfg = MockConfig()
    h = 2160.0
    assert math.isclose(compute_perspective_scale(0.0, h, cfg), 0.35)
    assert math.isclose(compute_perspective_scale(-200.0, h, cfg), 0.35)
    assert math.isclose(compute_perspective_scale(h, h, cfg), 1.0)
    assert math.isclose(compute_perspective_scale(h + 500.0, h, cfg), 1.0)
    assert math.isclose(compute_perspective_scale(0.2 * h, h, cfg), 0.35)
    assert math.isclose(compute_perspective_scale(0.8 * h, h, cfg), 1.0)
    assert math.isclose(compute_perspective_scale(0.5 * h, h, cfg), 0.675)


def test_perspective_scale_degenerate_configs_and_x_axis():
    """Test w(y) with degenerate frame dimensions, equal bounds, axis x, and input formats."""
    class MockConfigX:
        axis = "x"
        x_left, x_right = 0.1, 0.9
        weight_left, weight_right = 0.25, 1.0

    cfg_x = MockConfigX()
    assert math.isclose(compute_perspective_scale((0.1 * 1920.0, 500.0), 1080.0, cfg_x, frame_width=1920.0), 0.25)
    assert math.isclose(compute_perspective_scale([0.9 * 1920.0, 500.0], 1080.0, cfg_x, frame_width=1920.0), 1.0)
    assert math.isclose(compute_perspective_scale(np.array([0.0, 500.0]), 1080.0, cfg_x, frame_width=1920.0), 0.25)
    assert compute_perspective_scale(500.0, 0.0, cfg_x) == 1.0
    assert compute_perspective_scale(500.0, -100.0, cfg_x) == 1.0
    assert compute_perspective_scale(500.0, 1080.0, None) == 1.0

    cfg_degen = MockConfigX()
    cfg_degen.x_left, cfg_degen.x_right = 0.5, 0.5
    assert compute_perspective_scale((500.0, 500.0), 1080.0, cfg_degen, frame_width=1920.0) == 1.0


def test_box_geometry_and_ground_anchor():
    """Test box geometry clamping on inverted/zero-sized boxes and ground anchor precision."""
    inverted_box = np.array([200.0, 300.0, 100.0, 200.0])
    w, h, area, aspect = get_box_geometry(inverted_box)
    assert w == 1.0 and h == 1.0 and area == 1.0 and aspect == 1.0

    anchor = get_ground_anchor(np.array([100.0, 200.0, 200.0, 350.0]))
    assert anchor == (150.0, 350.0)
