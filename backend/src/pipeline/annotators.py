"""Annotator initializers for bounding boxes, badges, and zone visualization."""
from typing import NamedTuple
import numpy as np
import cv2
import supervision as sv


class TranslucentZoneAnnotator:
    """Renders polygon zones with subtle lower opacity alpha blending."""
    def __init__(self, zone, bgr_color: tuple, thickness: int = 2, alpha: float = 0.35):
        self.zone = zone
        self.bgr_color = bgr_color
        self.thickness = thickness
        self.alpha = alpha

    def annotate(self, scene: np.ndarray) -> np.ndarray:
        poly = np.array(self.zone.polygon, dtype=np.int32)
        overlay = scene.copy()
        cv2.polylines(overlay, [poly], isClosed=True, color=self.bgr_color, thickness=self.thickness)
        cv2.addWeighted(overlay, self.alpha, scene, 1.0 - self.alpha, 0, scene)
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


def create_annotators(lane_zones: list, crosswalk_zones: list) -> PipelineAnnotators:
    """Create styled Supervision annotators for alerts, warnings, and translucent zones."""
    red_palette = sv.ColorPalette.from_hex(["#FF0000"])
    orange_palette = sv.ColorPalette.from_hex(["#FF8C00"])
    cyan_palette = sv.ColorPalette.from_hex(["#00E5FF"])
    green_palette = sv.ColorPalette.from_hex(["#00FF00"])

    z_annotators = [
        TranslucentZoneAnnotator(zone=z, bgr_color=(255, 128, 0), thickness=2, alpha=0.25)
        for z in lane_zones
    ] + [
        TranslucentZoneAnnotator(zone=z, bgr_color=(0, 229, 255), thickness=2, alpha=0.30)
        for z in crosswalk_zones
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
