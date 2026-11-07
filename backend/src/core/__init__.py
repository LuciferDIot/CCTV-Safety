"""Core geometry, perspective foreshortening, motion kinematics, and HUD utilities."""
from src.core.anchors import get_box_geometry, get_ground_anchor
from src.core.perspective import compute_perspective_scale
from src.core.motion import get_motion_metrics, point_to_polygon_dist
from src.core.hud import draw_render_progress_bar

__all__ = [
    "get_box_geometry",
    "get_ground_anchor",
    "compute_perspective_scale",
    "get_motion_metrics",
    "point_to_polygon_dist",
    "draw_render_progress_bar",
]
