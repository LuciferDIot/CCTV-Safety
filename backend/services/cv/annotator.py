"""Supervision annotator wrappers for translucent overlays, vehicle badges, and pedestrian alerts."""
from typing import NamedTuple, Any, Set, Dict
import numpy as np
import cv2
import supervision as sv
from services.safety.vehicles import classify_vehicle_type


class TranslucentZoneAnnotator:
    """Renders whole polygon zones with semi-transparent fill and clear outline."""
    def __init__(self, polygon: Any, bgr_color: tuple, fill_alpha: float = 0.12, border_alpha: float = 0.45, thickness: int = 2):
        raw = getattr(polygon, "polygon", polygon)
        self.polygon = np.array(raw, dtype=np.int32)
        self.bgr_color = bgr_color
        self.fill_alpha = fill_alpha
        self.border_alpha = border_alpha
        self.thickness = thickness
        self._zone = sv.PolygonZone(polygon=self.polygon) if len(self.polygon) >= 3 else None

    def trigger(self, detections: Any) -> np.ndarray:
        if self._zone is not None:
            return self._zone.trigger(detections=detections)
        return np.zeros(len(detections), dtype=bool)

    def annotate(self, scene: np.ndarray) -> np.ndarray:
        if len(self.polygon) < 3:
            return scene
        overlay, border = scene.copy(), scene.copy()
        cv2.fillPoly(overlay, [self.polygon], self.bgr_color)
        cv2.addWeighted(overlay, self.fill_alpha, scene, 1.0 - self.fill_alpha, 0, scene)
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
    def _box(hex_c: str, th: int = 3): return sv.BoxAnnotator(color=sv.ColorPalette.from_hex([hex_c]), thickness=th)
    def _lbl(hex_c: str, tc=sv.Color.WHITE, sc=0.55): return sv.LabelAnnotator(color=sv.ColorPalette.from_hex([hex_c]), text_color=tc, text_scale=sc, text_padding=5)
    z_annotators = [
        TranslucentZoneAnnotator(p, (248, 189, 56), fill_alpha=0.12, border_alpha=0.45, thickness=2) for p in lane_polys
    ] + [
        TranslucentZoneAnnotator(p, (36, 191, 251), fill_alpha=0.18, border_alpha=0.55, thickness=3) for p in crosswalk_polys
    ]
    return PipelineAnnotators(
        alert_box=_box("#FF0000"), alert_label=_lbl("#FF0000"),
        warn_box=_box("#FF8C00"), warn_label=_lbl("#FF8C00", sv.Color.BLACK),
        cyan_box=_box("#00E5FF"), cyan_label=_lbl("#00E5FF", sv.Color.BLACK),
        normal_box=_box("#00FF00", 2), normal_label=_lbl("#00FF00", sv.Color.WHITE, 0.50),
        zone_annotators=z_annotators
    )


def draw_pedestrians(scene: np.ndarray, hazard_dets: Any, safe_dets: Any, ann: PipelineAnnotators) -> np.ndarray:
    if len(hazard_dets) > 0:
        scene = ann.alert_box.annotate(scene=scene, detections=hazard_dets)
        scene = ann.alert_label.annotate(scene=scene, detections=hazard_dets, labels=[f"[!] #{t} Ped in Lane" for t in hazard_dets.tracker_id])
    if len(safe_dets) > 0:
        scene = ann.cyan_box.annotate(scene=scene, detections=safe_dets)
        scene = ann.cyan_label.annotate(scene=scene, detections=safe_dets, labels=[f"#{t} Ped (Safe)" for t in safe_dets.tracker_id])
    return scene


def draw_vehicles(scene: np.ndarray, vehicle_dets: Any, wrong_tids: Set[int], cw_results: Dict[int, str], ann: PipelineAnnotators) -> np.ndarray:
    if len(vehicle_dets) == 0:
        return scene
    wrong_m = np.isin(vehicle_dets.tracker_id, list(wrong_tids))
    cw_ride_m = np.array([cw_results.get(t) == "CROSSWALK_RIDING" for t in vehicle_dets.tracker_id], dtype=bool)
    cw_walk_m = np.array([cw_results.get(t) == "EXEMPT_WALKING" for t in vehicle_dets.tracker_id], dtype=bool)
    layers = [
        (wrong_m, ann.alert_box, ann.alert_label, lambda d: [f"[!] #{t} Wrong Way" for t in d.tracker_id]),
        (cw_ride_m & ~wrong_m, ann.warn_box, ann.warn_label, lambda d: [f"[!] #{t} CW Riding" for t in d.tracker_id]),
        (cw_walk_m & ~wrong_m & ~cw_ride_m, ann.cyan_box, ann.cyan_label, lambda d: [f"#{t} Walking (Exempt)" for t in d.tracker_id]),
        (~(wrong_m | cw_ride_m | cw_walk_m), ann.normal_box, ann.normal_label, lambda d: [f"#{t} {classify_vehicle_type(c, b)}" for c, t, b in zip(d.class_id, d.tracker_id, d.xyxy)])
    ]
    for mask, box_ann, lbl_ann, lbl_fn in layers:
        if np.any(mask):
            sub = vehicle_dets[mask]
            scene = lbl_ann.annotate(scene=box_ann.annotate(scene=scene, detections=sub), detections=sub, labels=lbl_fn(sub))
    return scene
