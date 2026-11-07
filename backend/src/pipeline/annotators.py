"""Annotator initializers for bounding boxes, badges, and zone visualization."""
from typing import NamedTuple
import supervision as sv


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
    """Create styled Supervision annotators for alerts, warnings, and normal traffic."""
    red_palette = sv.ColorPalette.from_hex(["#FF0000"])
    orange_palette = sv.ColorPalette.from_hex(["#FF8C00"])
    cyan_palette = sv.ColorPalette.from_hex(["#00E5FF"])
    green_palette = sv.ColorPalette.from_hex(["#00FF00"])

    z_annotators = [
        sv.PolygonZoneAnnotator(
            zone=z, color=sv.Color(r=0, g=128, b=255), thickness=2, display_in_zone_count=False
        )
        for z in lane_zones
    ] + [
        sv.PolygonZoneAnnotator(
            zone=z, color=sv.Color(r=0, g=229, b=255), thickness=3, display_in_zone_count=False
        )
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
