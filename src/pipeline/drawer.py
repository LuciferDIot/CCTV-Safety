"""Rendering of vehicle bounding boxes, pedestrian alerts, and status badges."""
from typing import Dict, Set
import numpy as np
import supervision as sv

from src.safety.classifier import classify_vehicle_type
from src.pipeline.annotators import PipelineAnnotators


def draw_pedestrians(
    scene: np.ndarray,
    hazard_dets: sv.Detections,
    safe_dets: sv.Detections,
    ann: PipelineAnnotators
) -> np.ndarray:
    """Draw hazard pedestrian alert badges (red) and safe crosswalk badges (cyan)."""
    if len(hazard_dets) > 0:
        scene = ann.alert_box.annotate(scene=scene, detections=hazard_dets)
        labels = [f"[!] #{tid} Ped in Lane" for tid in hazard_dets.tracker_id]
        scene = ann.alert_label.annotate(scene=scene, detections=hazard_dets, labels=labels)

    if len(safe_dets) > 0:
        scene = ann.cyan_box.annotate(scene=scene, detections=safe_dets)
        labels = [f"#{tid} Ped (Safe)" for tid in safe_dets.tracker_id]
        scene = ann.cyan_label.annotate(scene=scene, detections=safe_dets, labels=labels)
    return scene


def draw_vehicles(
    scene: np.ndarray,
    vehicle_dets: sv.Detections,
    confirmed_wrong_tids: Set[int],
    cw_results: Dict[int, str],
    ann: PipelineAnnotators
) -> np.ndarray:
    """Draw classified vehicles: Wrong-way (red), CW riding (orange), walking (cyan), normal (green)."""
    if len(vehicle_dets) == 0:
        return scene

    wrong_m = np.isin(vehicle_dets.tracker_id, list(confirmed_wrong_tids))
    cw_ride_m = np.array([cw_results.get(t) == "CROSSWALK_RIDING" for t in vehicle_dets.tracker_id], dtype=bool)
    cw_walk_m = np.array([cw_results.get(t) == "EXEMPT_WALKING" for t in vehicle_dets.tracker_id], dtype=bool)

    if np.any(wrong_m):
        dets = vehicle_dets[wrong_m]
        scene = ann.alert_box.annotate(scene=scene, detections=dets)
        scene = ann.alert_label.annotate(
            scene=scene, detections=dets, labels=[f"[!] #{t} Wrong Way" for t in dets.tracker_id]
        )

    ride_m = cw_ride_m & ~wrong_m
    if np.any(ride_m):
        dets = vehicle_dets[ride_m]
        scene = ann.warn_box.annotate(scene=scene, detections=dets)
        scene = ann.warn_label.annotate(
            scene=scene, detections=dets, labels=[f"[!] #{t} CW Riding" for t in dets.tracker_id]
        )

    walk_m = cw_walk_m & ~wrong_m & ~cw_ride_m
    if np.any(walk_m):
        dets = vehicle_dets[walk_m]
        scene = ann.cyan_box.annotate(scene=scene, detections=dets)
        scene = ann.cyan_label.annotate(
            scene=scene, detections=dets, labels=[f"#{t} Walking (Exempt)" for t in dets.tracker_id]
        )

    norm_m = ~(wrong_m | cw_ride_m | cw_walk_m)
    if np.any(norm_m):
        dets = vehicle_dets[norm_m]
        scene = ann.normal_box.annotate(scene=scene, detections=dets)
        labels = [
            f"#{t} {classify_vehicle_type(c, b)}"
            for c, t, b in zip(dets.class_id, dets.tracker_id, dets.xyxy)
        ]
        scene = ann.normal_label.annotate(scene=scene, detections=dets, labels=labels)

    return scene

