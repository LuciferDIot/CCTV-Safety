"""Supervision annotator wrappers for translucent overlays, vehicle badges, and pedestrian alerts."""
from typing import NamedTuple, Any, Set, Dict, List
import numpy as np, cv2, supervision as sv
from services.safety.vehicles import classify_vehicle_type


class TranslucentZoneAnnotator:
    """Renders whole polygon zones with semi-transparent fill and clear outline."""
    def __init__(self, polygon: Any, bgr_color: tuple, fill_alpha: float = 0.12, border_alpha: float = 0.45, thickness: int = 2):
        raw = getattr(polygon, "polygon", polygon)
        self.polygon = np.array(raw, dtype=np.int32)
        self.bgr_color = bgr_color
        self.fill_alpha, self.border_alpha, self.thickness = fill_alpha, border_alpha, thickness
        self._zone = sv.PolygonZone(polygon=self.polygon) if len(self.polygon) >= 3 else None

    def trigger(self, detections: Any) -> np.ndarray:
        return self._zone.trigger(detections=detections) if self._zone is not None else np.zeros(len(detections), dtype=bool)

    def annotate(self, scene: np.ndarray) -> np.ndarray:
        if len(self.polygon) < 3: return scene
        # OpenCV frames have no native alpha channel for fillPoly; blend fill via offscreen overlay:
        # output = scene * (1 - alpha) + overlay * alpha
        overlay = scene.copy()
        cv2.fillPoly(overlay, [self.polygon], self.bgr_color)
        cv2.addWeighted(overlay, self.fill_alpha, scene, 1.0 - self.fill_alpha, 0, scene)
        # Draw crisp boundary border directly onto scene (eliminates redundant frame copy)
        cv2.polylines(scene, [self.polygon], isClosed=True, color=self.bgr_color, thickness=self.thickness)
        return scene


class PipelineAnnotators(NamedTuple):
    alert_box: sv.BoxAnnotator; alert_label: sv.LabelAnnotator
    warn_box: sv.BoxAnnotator; warn_label: sv.LabelAnnotator
    cyan_box: sv.BoxAnnotator; cyan_label: sv.LabelAnnotator
    normal_box: sv.BoxAnnotator; normal_label: sv.LabelAnnotator
    zone_annotators: list


def create_annotators(lane_polys: list, crosswalk_polys: list) -> PipelineAnnotators:
    """Creates annotators. Colors use OpenCV BGR channel order: (Blue, Green, Red)."""
    def _box(c: str, th: int = 3): return sv.BoxAnnotator(color=sv.ColorPalette.from_hex([c]), thickness=th)
    def _lbl(c: str, tc=sv.Color.WHITE, sc=0.55): return sv.LabelAnnotator(color=sv.ColorPalette.from_hex([c]), text_color=tc, text_scale=sc, text_padding=5)
    # Lanes: amber BGR (248, 189, 56); Crosswalks: cyan/yellow BGR (36, 191, 251)
    z_anns = [TranslucentZoneAnnotator(p, (248, 189, 56), 0.12, 0.45, 2) for p in lane_polys] + \
             [TranslucentZoneAnnotator(p, (36, 191, 251), 0.18, 0.55, 3) for p in crosswalk_polys]
    return PipelineAnnotators(
        alert_box=_box("#FF0000"), alert_label=_lbl("#FF0000"),
        warn_box=_box("#FF8C00"), warn_label=_lbl("#FF8C00", sv.Color.BLACK),
        cyan_box=_box("#00E5FF"), cyan_label=_lbl("#00E5FF", sv.Color.BLACK),
        normal_box=_box("#00FF00", 2), normal_label=_lbl("#00FF00", sv.Color.WHITE, 0.50),
        zone_annotators=z_anns
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
    """Renders vehicles by alert hierarchy: Red (Wrong-Way) > Orange (CW Riding) > Cyan (Walking) > Green (Normal)."""
    if len(vehicle_dets) == 0: return scene
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
            # Step 1: Draw bounding box outline around vehicle
            scene = box_ann.annotate(scene=scene, detections=sub)
            # Step 2: Draw badge label above vehicle bounding box
            scene = lbl_ann.annotate(scene=scene, detections=sub, labels=lbl_fn(sub))
    return scene
