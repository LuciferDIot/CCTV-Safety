"""
Complete End-to-End CCTV Intersection Safety & Motorcycle Violation Pipeline
Orchestrates Detection, Tracking, Trajectory Analysis, Wrong-Way Detection,
Crosswalk Riding / Exemption Verification, Event Lifecycle, and Visual Evidence Generation.
"""
from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import cv2
import numpy as np
import supervision as sv
from ultralytics import YOLO
import torch

from src.config_loader import load_intersection_config, IntersectionConfig
from src.geometry_utils import get_box_geometry, get_ground_anchor, draw_render_progress_bar
from src.tracker_manager import RobustTrackerManager
from src.auto_lane_detector import AutoLaneDetector
from src.direction_checker import DirectionChecker
from src.crosswalk_checker import CrosswalkSafetyChecker
from src.pedestrian_checker import classify_vehicle_type, resolve_riders_and_pedestrians, PedestrianSafetyChecker
from src.event_verifier import EventVerifier
from src.explanation_engine import ExplanationEngine

class IntersectionSafetyPipeline:
    def __init__(
        self,
        config_path: Path,
        model_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        device: Optional[str] = None,
        imgsz: int = 960
    ):
        self.config_path = Path(config_path)
        self.config = load_intersection_config(self.config_path)
        self.imgsz = imgsz

        if output_dir is None:
            self.output_dir = self.config_path.parent.parent / "data" / "output"
        else:
            self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir = self.output_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Prefer YOLO11m (Medium) if available for highest accuracy on occluded traffic & small bikes
        if model_path is None:
            yolo11m_path = self.config_path.parent.parent / "models" / "yolo11m.pt"
            yolo11s_path = self.config_path.parent.parent / "models" / "yolo11s.pt"
            if yolo11m_path.exists():
                model_path = yolo11m_path
            elif yolo11s_path.exists():
                model_path = yolo11s_path
            else:
                model_path = self.config_path.parent.parent / "models" / "yolov8s.pt"

        print(f"Loading Detection Model from: {model_path} on {self.device.upper()} (imgsz={self.imgsz})...")
        self.model = YOLO(str(model_path))
        self.model.to(self.device)

        # 1. Tracker Manager (Item 1)
        self.tracker = RobustTrackerManager(
            max_reconnect_frames=25,
            max_reconnect_dist_px=180.0,
            perspective_cfg=self.config.perspective_scale_by_y
        )

        # 2. Lane Detector & Ambiguity Handler (Item 2)
        self.lane_detector = AutoLaneDetector(
            road_polygon=np.array(self.config.road.polygon, dtype=np.int32),
            warmup_frames=self.config.road.warmup_frames,
            perspective_cfg=self.config.perspective_scale_by_y
        )
        self.lane_detector.calibrate(fallback_lanes=self.config.lanes)

        # 3. Direction Checker (Item 3)
        self.direction_checker = DirectionChecker(
            min_frames=5,
            min_sustained_frames=5,
            min_recent_speed=2.0,
            min_total_dist_px=20.0,
            wrong_way_threshold=-0.60,
            perspective_cfg=self.config.perspective_scale_by_y
        )

        # 4. Crosswalk Riding vs Walking Checker (Item 4)
        cw_polys = [np.array(cw.polygon, dtype=np.int32) for cw in self.config.crosswalks]
        self.crosswalk_checker = CrosswalkSafetyChecker(
            crosswalk_polygons=cw_polys,
            min_passage_dist_px=40.0,
            max_walking_speed=3.8,
            min_riding_speed=4.8,
            perspective_cfg=self.config.perspective_scale_by_y
        )

        # 5. Pedestrian Safety Checker
        self.ped_safety = PedestrianSafetyChecker(min_confirm_frames=4)

        # 6. Event Verifier & Lifecycle Manager (Item 5)
        self.event_verifier = EventVerifier(fps=self.config.fps)

        # 7. Explanation Engine (Item 6)
        self.explanation_engine = ExplanationEngine(output_dir=self.events_dir)

        # Visual Annotators
        self._init_annotators()

        # Cache of peak frames and trajectories for event explanation
        self.track_peak_frames: Dict[int, np.ndarray] = {}
        self.track_peak_bboxes: Dict[int, np.ndarray] = {}

    def _init_annotators(self):
        self.LANE_PALETTE = sv.ColorPalette([
            sv.Color.from_hex("#00C853"),  # Green
            sv.Color.from_hex("#2979FF"),  # Blue
        ])
        self.CW_COLOR = sv.Color.from_hex("#00E5FF")    # Cyan
        self.ALERT_COLOR = sv.Color.RED                # Red
        self.WARN_COLOR = sv.Color.from_hex("#FFA000") # Orange

        self.lane_annotators = [
            sv.PolygonZoneAnnotator(zone=z, color=self.LANE_PALETTE.by_idx(i), thickness=3)
            for i, z in enumerate(self.lane_detector.lane_zones)
        ]
        self.cw_annotators = [
            sv.PolygonZoneAnnotator(zone=z, color=self.CW_COLOR, thickness=3)
            for z in self.crosswalk_checker.crosswalk_zones
        ]
        self.normal_box = sv.BoxAnnotator(color=sv.Color.GREEN, thickness=2)
        self.normal_label = sv.LabelAnnotator(
            color=sv.Color.GREEN, text_color=sv.Color.WHITE, text_scale=0.55, text_padding=3
        )

        self.alert_box = sv.BoxAnnotator(color=self.ALERT_COLOR, thickness=4)
        self.alert_label = sv.LabelAnnotator(
            color=self.ALERT_COLOR, text_color=sv.Color.WHITE, text_scale=0.6, text_padding=3
        )

        self.warn_box = sv.BoxAnnotator(color=self.WARN_COLOR, thickness=3)
        self.warn_label = sv.LabelAnnotator(
            color=self.WARN_COLOR, text_color=sv.Color.BLACK, text_scale=0.55, text_padding=3
        )

        self.cyan_box = sv.BoxAnnotator(color=self.CW_COLOR, thickness=3)
        self.cyan_label = sv.LabelAnnotator(
            color=self.CW_COLOR, text_color=sv.Color.BLACK, text_scale=0.55, text_padding=3
        )

    def process_frame(
        self,
        frame: np.ndarray,
        frame_idx: int,
        total_frames: int = 0
    ) -> np.ndarray:
        """Processes a single video frame through the complete safety pipeline."""
        annotated_frame = frame.copy()

        # 1. Detection and Tracking with YOLO11 / YOLOv8 using ByteTrack
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0, 1, 2, 3, 5, 7],
            imgsz=self.imgsz,
            device=self.device,
            conf=0.20,
            verbose=False
        )[0]
        detections = sv.Detections.from_ultralytics(results)

        # 2. Filter out ALL objects outside the monitored road and crosswalk zones
        # Protects against annotating parked vehicles, off-road tuk-tuks, or background bystanders
        if len(detections) > 0:
            inside_zone_mask = np.zeros(len(detections), dtype=bool)
            road_poly = np.array(self.config.road.polygon, dtype=np.int32)
            for idx, xyxy in enumerate(detections.xyxy):
                cx, cy = get_ground_anchor(xyxy)
                pt = (float(cx), float(cy))
                # cv2.pointPolygonTest returns +1 (inside), 0 (on edge), -1 (outside)
                if cv2.pointPolygonTest(road_poly, pt, False) >= 0:
                    inside_zone_mask[idx] = True
                else:
                    for cw_poly in self.crosswalk_checker.crosswalk_polygons:
                        if cv2.pointPolygonTest(cw_poly, pt, False) >= 0:
                            inside_zone_mask[idx] = True
                            break
            detections = detections[inside_zone_mask]

        # Assign fallback tracker IDs if running isolated frames or tracker warmup
        if detections.tracker_id is None or len(detections.tracker_id) == 0:
            detections.tracker_id = np.arange(1, len(detections) + 1, dtype=int)
        else:
            tids = list(detections.tracker_id)
            for i in range(len(tids)):
                if tids[i] is None or tids[i] <= 0:
                    tids[i] = i + 1
            detections.tracker_id = np.array(tids, dtype=int)

        # 3. Suppress duplicate bike boxes first
        detections = self.tracker.suppress_duplicate_bikes(detections, iou_threshold=0.25)

        # 4. Build track history lookup before rider resolution
        raw_track_hist = {
            cid: [(p[1], p[2]) for p in trk.history]
            for cid, trk in self.tracker.tracks.items()
        }

        # 5. Rider-to-Bike Fusion: merge mounted riders into bikes; keep genuine pedestrians
        detections = resolve_riders_and_pedestrians(
            detections=detections,
            lane_zones=self.lane_detector.lane_zones,
            crosswalk_zones=self.crosswalk_checker.crosswalk_zones,
            track_history=raw_track_hist
        )

        # 6. Update track histories & resolve ID switching
        detections = self.tracker.update_tracks(detections, frame_idx)

        # Re-sync raw track history with newly updated tracks
        raw_track_hist = {
            cid: [(p[1], p[2]) for p in trk.history]
            for cid, trk in self.tracker.tracks.items()
        }

        # 7. Draw Crosswalk and Lane Polygons
        for cw_ann in self.cw_annotators:
            annotated_frame = cw_ann.annotate(scene=annotated_frame)
        for lane_ann in self.lane_annotators:
            annotated_frame = lane_ann.annotate(scene=annotated_frame)

        # 8. Check Genuine Pedestrian Safety on Foot
        # Hazard: Pedestrians walking/crossing active traffic lanes outside crosswalk (ALERT RED)
        # Safe: Pedestrians walking inside designated crosswalk (CYAN)
        hazard_peds, safe_peds = self.ped_safety.check_safety(
            detections, self.lane_detector.lane_zones, self.crosswalk_checker.crosswalk_zones, raw_track_hist, frame_idx
        )
        hazard_tids = set(hazard_peds.tracker_id) if len(hazard_peds) > 0 and hazard_peds.tracker_id is not None else set()
        safe_tids = set(safe_peds.tracker_id) if len(safe_peds) > 0 and safe_peds.tracker_id is not None else set()

        if len(safe_peds) > 0:
            annotated_frame = self.cyan_box.annotate(scene=annotated_frame, detections=safe_peds)
            labels = [f"#{tid} Ped (Safe)" for tid in safe_peds.tracker_id]
            annotated_frame = self.cyan_label.annotate(scene=annotated_frame, detections=safe_peds, labels=labels)

        if len(hazard_peds) > 0:
            annotated_frame = self.alert_box.annotate(scene=annotated_frame, detections=hazard_peds)
            labels = [f"[!] #{tid} Ped in Lane" for tid in hazard_peds.tracker_id]
            annotated_frame = self.alert_label.annotate(scene=annotated_frame, detections=hazard_peds, labels=labels)

        # 9. Check Crosswalk Traversal (Riding vs Walking a Motorcycle)
        # Normal motorcycles traveling down their traffic lane in permitted direction are exempted
        lane_vectors = [lane.permitted_unit_vector for lane in self.config.lanes]
        cw_results = self.crosswalk_checker.check_motorcycles(
            detections=detections,
            track_history=raw_track_hist,
            frame_idx=frame_idx,
            lane_vectors=lane_vectors
        )

        for tid, cw_status in cw_results.items():
            if cw_status == "CROSSWALK_RIDING":
                self.event_verifier.log_candidate(
                    track_id=tid,
                    event_type="CROSSWALK_RIDING",
                    frame_idx=frame_idx,
                    lane_or_zone="crosswalk",
                    details="Motorcycle traversed crosswalk above walking speed",
                    track_len=len(self.tracker.tracks[tid].history) if tid in self.tracker.tracks else 10
                )
                self.track_peak_frames[tid] = frame.copy()
            elif cw_status == "EXEMPT_WALKING":
                self.event_verifier.log_candidate(
                    track_id=tid,
                    event_type="EXEMPT_WALKING",
                    frame_idx=frame_idx,
                    lane_or_zone="crosswalk",
                    details="Rider dismounted walking motorcycle across crosswalk",
                    track_len=len(self.tracker.tracks[tid].history) if tid in self.tracker.tracks else 10
                )
                self.track_peak_frames[tid] = frame.copy()

        # 9. Process ALL Vehicles Across the Entire Road (No Unannotated Vehicles!)
        vehicle_dets = detections[detections.class_id != 0]
        if len(vehicle_dets) > 0:
            # Check lane assignments and lane divider ambiguity
            ambiguous_mask = np.zeros(len(vehicle_dets), dtype=bool)
            lane_assignment = [None] * len(vehicle_dets)

            for idx, xyxy in enumerate(vehicle_dets.xyxy):
                cx, cy = get_ground_anchor(xyxy)
                lane_idx, is_amb, _ = self.lane_detector.assign_lane((cx, cy))
                ambiguous_mask[idx] = is_amb
                lane_assignment[idx] = lane_idx

            # Track which vehicles are confirmed wrong-way
            confirmed_wrong_tids = set()

            for lane_idx, lane in enumerate(self.config.lanes):
                in_this_lane = np.array([l == lane_idx for l in lane_assignment], dtype=bool)
                if not np.any(in_this_lane):
                    continue

                lane_dets = vehicle_dets[in_this_lane]
                lane_amb_mask = ambiguous_mask[in_this_lane]

                confirmed_wrong, suspected_wrong = self.direction_checker.check_detections(
                    detections=lane_dets,
                    permitted_vector=lane.permitted_unit_vector,
                    track_history=raw_track_hist,
                    lane_id=lane.id,
                    frame_idx=frame_idx,
                    ambiguous_mask=lane_amb_mask
                )

                for idx, (tid, is_conf, is_susp) in enumerate(zip(lane_dets.tracker_id, confirmed_wrong, suspected_wrong)):
                    track_len = len(self.tracker.tracks[tid].history) if tid in self.tracker.tracks else 10
                    is_ambiguous = lane_amb_mask[idx]

                    if is_conf:
                        confirmed_wrong_tids.add(tid)
                        self.event_verifier.log_candidate(
                            track_id=tid,
                            event_type="WRONG_WAY",
                            frame_idx=frame_idx,
                            lane_or_zone=lane.id,
                            details=f"Sustained wrong-way movement counter to {lane.permitted_unit_vector}",
                            is_ambiguous=is_ambiguous,
                            track_len=track_len
                        )
                        self.track_peak_frames[tid] = frame.copy()
                        self.track_peak_bboxes[tid] = lane_dets.xyxy[idx].copy()
                    elif is_susp and (is_ambiguous or track_len < 6):
                        self.event_verifier.log_candidate(
                            track_id=tid,
                            event_type="INSUFFICIENT_EVIDENCE",
                            frame_idx=frame_idx,
                            lane_or_zone=lane.id,
                            details="Brief counter-flow deviation with ambiguous lane boundary or short track",
                            is_ambiguous=True,
                            track_len=track_len
                        )

            # Separate all vehicles into categories for clean annotation
            wrong_mask = np.isin(vehicle_dets.tracker_id, list(confirmed_wrong_tids))
            cw_riding_mask = np.array([cw_results.get(tid) == "CROSSWALK_RIDING" for tid in vehicle_dets.tracker_id], dtype=bool)
            cw_walking_mask = np.array([cw_results.get(tid) == "EXEMPT_WALKING" for tid in vehicle_dets.tracker_id], dtype=bool)

            # 9A. Confirmed Wrong-Way Vehicles (Alert Red)
            if np.any(wrong_mask):
                wrong_dets = vehicle_dets[wrong_mask]
                annotated_frame = self.alert_box.annotate(scene=annotated_frame, detections=wrong_dets)
                labels = [f"[!] #{tid} Wrong Way" for tid in wrong_dets.tracker_id]
                annotated_frame = self.alert_label.annotate(scene=annotated_frame, detections=wrong_dets, labels=labels)

            # 9B. Crosswalk Riding Violations (Alert Orange)
            if np.any(cw_riding_mask & ~wrong_mask):
                riding_dets = vehicle_dets[cw_riding_mask & ~wrong_mask]
                annotated_frame = self.warn_box.annotate(scene=annotated_frame, detections=riding_dets)
                labels = [f"[!] #{tid} CW Riding" for tid in riding_dets.tracker_id]
                annotated_frame = self.warn_label.annotate(scene=annotated_frame, detections=riding_dets, labels=labels)

            # 9C. Crosswalk Walking Exemption (Cyan)
            if np.any(cw_walking_mask & ~wrong_mask & ~cw_riding_mask):
                walking_dets = vehicle_dets[cw_walking_mask & ~wrong_mask & ~cw_riding_mask]
                annotated_frame = self.cyan_box.annotate(scene=annotated_frame, detections=walking_dets)
                labels = [f"#{tid} Walking (Exempt)" for tid in walking_dets.tracker_id]
                annotated_frame = self.cyan_label.annotate(scene=annotated_frame, detections=walking_dets, labels=labels)

            # 9D. All Normal Vehicles Everywhere on Road (Green)
            normal_mask = ~(wrong_mask | cw_riding_mask | cw_walking_mask)
            if np.any(normal_mask):
                normal_dets = vehicle_dets[normal_mask]
                annotated_frame = self.normal_box.annotate(scene=annotated_frame, detections=normal_dets)
                labels = [
                    f"#{tid} {classify_vehicle_type(cid, box)}"
                    for cid, tid, box in zip(normal_dets.class_id, normal_dets.tracker_id, normal_dets.xyxy)
                ]
                annotated_frame = self.normal_label.annotate(scene=annotated_frame, detections=normal_dets, labels=labels)

        # 10. Step Event Lifecycle
        self.event_verifier.step(frame_idx)

        # 11. Render HUD Progress Bar
        if total_frames > 0:
            annotated_frame = draw_render_progress_bar(annotated_frame, frame_idx + 1, total_frames)

        return annotated_frame

    def finalize(self) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Finalizes event logging, exports detected_events.json,
        generates supporting explanation images, and evaluates against eval_gt.json.
        """
        print("\nFinalizing safety event records...")
        final_events = self.event_verifier.finalize()

        # Export events JSON
        events_json_path = self.output_dir / "detected_events.json"
        self.event_verifier.export_json(events_json_path)
        print(f"Exported {len(final_events)} verified events to: {events_json_path}")

        # Generate visual evidence frames for each event
        print(f"Generating visual audit evidence frames in {self.events_dir}...")
        for event in final_events:
            tid = event.track_id
            peak_frame = self.track_peak_frames.get(tid)
            trajectory = []
            if tid in self.tracker.tracks:
                trajectory = [(p[1], p[2]) for p in self.tracker.tracks[tid].history]

            bbox = self.track_peak_bboxes.get(tid)
            if bbox is None and tid in self.tracker.tracks and len(self.tracker.tracks[tid].history) > 0:
                bbox = self.tracker.tracks[tid].history[-1][3]

            if peak_frame is not None and len(trajectory) > 0:
                self.explanation_engine.generate_event_evidence(
                    event=event,
                    peak_frame=peak_frame,
                    trajectory=trajectory,
                    bbox=bbox,
                    rationale=event.details
                )

        # Evaluate against Ground Truth
        gt_path = self.config_path.parent.parent / "data" / "eval_gt.json"
        eval_metrics = self.event_verifier.evaluate_against_ground_truth(gt_path)

        eval_summary_path = self.output_dir / "evaluation_summary.json"
        with open(eval_summary_path, "w", encoding="utf-8") as f:
            json.dump(eval_metrics, f, indent=2)
        print(f"Saved benchmark evaluation metrics to: {eval_summary_path}")

        return (final_events, eval_metrics)
