"""
Pedestrian Safety, Vehicle Type Refinement & Rider Resolution
Refines YOLO classes into Ped, Bike, 3-Wheel, Car, Bus, Truck.
Strictly distinguishes genuine pedestrians on foot from mounted two-wheeler riders.
"""
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import supervision as sv

from src.geometry_utils import get_box_geometry, get_motion_metrics, point_to_polygon_dist

def classify_vehicle_type(class_id: int, bbox: np.ndarray) -> str:
    """
    Refines YOLO COCO classes into distinct traffic vehicle types:
    - Ped (0: Person on foot)
    - Bike (1: Bicycle, 3: Motorcycle/Scooter)
    - 3-Wheel (Auto-rickshaws / Tuk-tuks)
    - Car (2: Standard passenger cars / SUVs)
    - Bus (5: Transit buses)
    - Truck (7: Commercial trucks)
    """
    w, h, area, aspect_ratio = get_box_geometry(bbox)

    if class_id == 0:
        return "Ped"
    elif class_id in [1, 3]:
        return "Bike"
    elif class_id in [2, 7]:
        # In 4K CCTV (3840x2160), Auto-rickshaws (Tuk-tuks) are compact, boxy vehicles:
        # Width: 120-340px, Height: 160-460px, Area < 120,000 px^2, Aspect Ratio: 0.75 - 1.70
        # Standard cars/SUVs are wider (W > 340px) or larger (Area >= 120,000 px^2)
        if 120 <= w <= 340 and 160 <= h <= 460 and area < 120000 and 0.75 <= aspect_ratio <= 1.70:
            return "3-Wheel"
        return "Car" if class_id == 2 else "Truck"
    elif class_id == 5:
        return "Bus"
    return "Veh"

def resolve_riders_and_pedestrians(
    detections: sv.Detections,
    lane_zones: list,
    crosswalk_zones: list,
    track_history: Optional[dict] = None
) -> sv.Detections:
    """
    Robust Rider-to-Bike Resolution:
    1. Fuses overlapping / vertically stacked person + motorcycle detections into a single 'Bike' box everywhere (including crosswalks).
    2. Reclassifies lone riders in active traffic lanes into 'Bike' (class 3).
    3. Strictly ensures no mounted two-wheeler rider is ever misidentified as a pedestrian.
    """
    if len(detections) == 0:
        return detections

    person_mask = (detections.class_id == 0)
    bike_mask = np.isin(detections.class_id, [1, 3])

    p_indices = np.where(person_mask)[0]
    b_indices = np.where(bike_mask)[0]
    suppress_persons = []

    # Step 1: Direct geometric stacking (person riding on a detected bike chassis)
    for p_idx in p_indices:
        pb = detections.xyxy[p_idx]
        pcx = (pb[0] + pb[2]) / 2.0
        pcy = (pb[1] + pb[3]) / 2.0
        pw = pb[2] - pb[0]
        ph = pb[3] - pb[1]

        matched_bike = False
        for b_idx in b_indices:
            bb = detections.xyxy[b_idx]
            bcx = (bb[0] + bb[2]) / 2.0
            bw = bb[2] - bb[0]
            bh = bb[3] - bb[1]

            dx = abs(pcx - bcx)
            # Stacked vertically (rider sits on bike: feet/wheels at bottom, head at top)
            y_overlap = (pb[3] >= bb[1] - 50.0 and pb[1] <= bb[3])

            if dx <= max(75.0, 0.75 * max(pw, bw)) and y_overlap:
                matched_bike = True
                suppress_persons.append(p_idx)
                # Expand bike bbox to encompass rider helmet down to wheels
                detections.xyxy[b_idx][0] = min(detections.xyxy[b_idx][0], pb[0])
                detections.xyxy[b_idx][1] = min(detections.xyxy[b_idx][1], pb[1])
                detections.xyxy[b_idx][2] = max(detections.xyxy[b_idx][2], pb[2])
                detections.xyxy[b_idx][3] = max(detections.xyxy[b_idx][3], pb[3])
                break

        # Step 2: Lone Rider vs Pedestrian Crossing the Road
        if not matched_bike:
            # Check if this person is inside an active traffic lane or crosswalk
            in_crosswalk = False
            for cw_zone in crosswalk_zones:
                if point_to_polygon_dist((pcx, pb[3]), cw_zone.polygon) >= -10:
                    in_crosswalk = True
                    break

            in_vehicle_lane = False
            for l_zone in lane_zones:
                if point_to_polygon_dist((pcx, pb[3]), l_zone.polygon) >= -10:
                    in_vehicle_lane = True
                    break

            # If inside crosswalk, this is a genuine pedestrian crossing the street - NEVER convert to Bike!
            if in_crosswalk:
                continue

            # If inside traffic lane:
            # Distinguish a mounted rider from a pedestrian walking across the road:
            # - Pedestrians walking on foot have tall aspect ratio (AR >= 1.90) and slow walking motion.
            # - Mounted riders on motorcycles have low/wide aspect ratio (AR <= 1.80) and vehicle-speed motion.
            if in_vehicle_lane:
                aspect_ratio = ph / max(1.0, pw)
                # Check motion kinematics if track history is available
                is_walking_ped = False
                if track_history is not None and detections.tracker_id is not None and p_idx < len(detections.tracker_id):
                    tid = detections.tracker_id[p_idx]
                    if tid is not None and tid in track_history and len(track_history[tid]) >= 3:
                        hist = track_history[tid]
                        dx = hist[-1][0] - hist[0][0]
                        dy = hist[-1][1] - hist[0][1]
                        speed = np.hypot(dx, dy) / max(1, len(hist) - 1)
                        # Pedestrian walking across lane: lateral displacement (|dx| >= |dy|) or walking speed <= 4.0
                        if speed <= 4.0 or abs(dx) >= 0.8 * abs(dy):
                            is_walking_ped = True

                # If tall pedestrian silhouette or walking kinematics, keep as genuine pedestrian (class 0)
                if aspect_ratio >= 1.85 or is_walking_ped:
                    continue  # Keep as Pedestrian (class 0) - will be flagged as Ped in Lane!

                # Only convert if low aspect ratio (seated rider) and not walking
                if aspect_ratio < 1.80 and not is_walking_ped:
                    detections.class_id[p_idx] = 3  # Convert to Bike

    # Suppress redundant person detections that were merged into bikes
    keep = np.ones(len(detections), dtype=bool)
    keep[suppress_persons] = False
    return detections[keep]

class PedestrianSafetyChecker:
    def __init__(self, min_confirm_frames: int = 2):
        self.min_confirm_frames = min_confirm_frames
        self.hazard_frame_counts: Dict[int, int] = defaultdict(int)

    def check_safety(
        self,
        detections: sv.Detections,
        lane_zones: list,
        crosswalk_zones: list,
        track_history: Optional[dict] = None,
        frame_idx: int = 0
    ) -> Tuple[sv.Detections, sv.Detections]:
        """
        Evaluates genuine pedestrian safety on foot.
        Only genuine pedestrians (class_id == 0, NOT bikes or vehicles) are evaluated.
        Returns:
            hazard_pedestrians: Pedestrians walking/standing in active traffic lanes outside crosswalk (ALERT RED)
            safe_pedestrians: Pedestrians safely crossing inside crosswalk (CYAN)
        """
        if len(detections) == 0:
            return (detections[0:0], detections[0:0])

        # ONLY genuine pedestrians on foot
        persons = detections[detections.class_id == 0]
        if len(persons) == 0:
            return (persons[0:0], persons[0:0])

        in_any_lane_mask = np.zeros(len(persons), dtype=bool)
        for l_zone in lane_zones:
            in_any_lane_mask |= l_zone.trigger(detections=persons)

        in_crosswalk_mask = np.zeros(len(persons), dtype=bool)
        for cw_zone in crosswalk_zones:
            in_crosswalk_mask |= cw_zone.trigger(detections=persons)

        # Pedestrians inside crosswalk are safe
        safe_pedestrians = persons[in_crosswalk_mask]

        # Pedestrians in traffic lanes outside crosswalk are hazardous (jaywalking / lane intrusion)
        hazard_pedestrians = persons[in_any_lane_mask & ~in_crosswalk_mask]

        return (hazard_pedestrians, safe_pedestrians)
