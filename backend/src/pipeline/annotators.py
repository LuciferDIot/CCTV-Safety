"""Annotator initializers for bounding boxes, badges, and whole translucent zones."""
from typing import NamedTuple, Any
import numpy as np
import cv2
import supervision as sv


class TranslucentZoneAnnotator:
    """Renders whole polygon zones with semi-transparent fill and clear outline."""
    def __init__(
        self, polygon: Any, bgr_color: tuple,
        fill_alpha: float = 0.12, border_alpha: float = 0.45, thickness: int = 2
    ):
        raw = getattr(polygon, "polygon", polygon)
        self.polygon = np.array(raw, dtype=np.int32)
        self.bgr_color = bgr_color
        self.fill_alpha = fill_alpha
        self.border_alpha = border_alpha
        self.thickness = thickness

    def annotate(self, scene: np.ndarray) -> np.ndarray:
        if len(self.polygon) < 3:
            return scene
        overlay = scene.copy()
        cv2.fillPoly(overlay, [self.polygon], self.bgr_color)
        cv2.addWeighted(overlay, self.fill_alpha, scene, 1.0 - self.fill_alpha, 0, scene)
        border = scene.copy()
        cv2.polylines(border, [self.polygon], isClosed=True, color=self.bgr_color, thickness=self.thickness)
        cv2.addWeighted(border, self.border_alpha, scene, 1.0 - self.border_alpha, 0, scene)
        return scene


class PipelineAnnotators(NamedTuple):
    alert_box: sv.BoxAnnotator
    alert_label: sv.LabelAnnotator
    warn_box: sv.BoxAnnotator
    warn_label: sv.LabelAnnotator
    cyan_box: sv.BoxAnnotator
    cyan_label: sv.LabelAnnotator
    normal_box: sv.BoxAnnotator
    normal_label: sv.LabelAnnotator
    zone_annotators: list


def create_annotators(lane_polys: list, crosswalk_polys: list) -> PipelineAnnotators:
    """Create styled Supervision annotators with whole-zone translucent overlays."""
    red_palette = sv.ColorPalette.from_hex(["#FF0000"])
    orange_palette = sv.ColorPalette.from_hex(["#FF8C00"])
    cyan_palette = sv.ColorPalette.from_hex(["#00E5FF"])
    green_palette = sv.ColorPalette.from_hex(["#00FF00"])

    z_annotators = [
        TranslucentZoneAnnotator(p, bgr_color=(248, 189, 56), fill_alpha=0.12, border_alpha=0.45, thickness=2)
        for p in lane_polys
    ] + [
        TranslucentZoneAnnotator(p, bgr_color=(36, 191, 251), fill_alpha=0.18, border_alpha=0.55, thickness=3)
        for p in crosswalk_polys
    ]

    return PipelineAnnotators(
        alert_box=sv.BoxAnnotator(color=red_palette, thickness=3),
        alert_label=sv.LabelAnnotator(
            color=red_palette, text_color=sv.Color.WHITE, text_scale=0.55, text_padding=5
        ),
        warn_box=sv.BoxAnnotator(color=orange_palette, thickness=3),
        warn_label=sv.LabelAnnotator(
            color=orange_palette, text_color=sv.Color.BLACK, text_scale=0.55, text_padding=5
        ),
        cyan_box=sv.BoxAnnotator(color=cyan_palette, thickness=3),
        cyan_label=sv.LabelAnnotator(
            color=cyan_palette, text_color=sv.Color.BLACK, text_scale=0.55, text_padding=5
        ),
        normal_box=sv.BoxAnnotator(color=green_palette, thickness=2),
        normal_label=sv.LabelAnnotator(
            color=green_palette, text_color=sv.Color.WHITE, text_scale=0.50, text_padding=4
        ),
        zone_annotators=z_annotators
    )
