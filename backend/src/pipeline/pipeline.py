"""Intersection Safety Pipeline: Orchestrates detection, tracking, safety checks and HUD."""
from pathlib import Path
from typing import Optional, Any, Tuple, List, Dict
import json
import numpy as np
import torch

from src.config.zones import load_intersection_config, parse_intersection_config
from src.core.hud import draw_render_progress_bar
from src.pipeline.drawer import draw_pedestrians, draw_vehicles
from src.pipeline.safety_eval import log_candidates_for_crosswalk, check_lane_violations, log_candidates_for_pedestrians
from src.pipeline.builder import build_pipeline_components, render_evidence_cards
from src.pipeline.tracker_step import detect_and_track_step
from src.pipeline.loader import load_detection_model
from src.pipeline.warmup import step_auto_calibration


class IntersectionSafetyPipeline:
    """End-to-end safety monitoring pipeline for intersections and crosswalks."""

    def __init__(
        self, config_path: Path, model_path: Optional[Path] = None,
        output_dir: Optional[Path] = None, device: Optional[str] = None, imgsz: int = 960,
        override_zones: Optional[Dict[str, Any]] = None
    ):
        self.config_path = Path(config_path)
        self.config = parse_intersection_config(override_zones) if override_zones else load_intersection_config(self.config_path)
        self.imgsz = imgsz
        base = self.config_path.parent.parent
        self.output_dir = Path(output_dir or base / "data" / "output")
        self.events_dir = self.output_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = load_detection_model(model_path, base, self.device)
        comps = build_pipeline_components(self.config, self.events_dir)
        (self.tracker, self.lane_detector, self.direction_checker,
         self.crosswalk_checker, self.pedestrian_checker,
         self.event_verifier, self.explanation_engine, self.ann) = comps

        self.road_poly = np.array(self.config.road.polygon, dtype=np.int32)
        self.track_peak_frames: Dict[int, np.ndarray] = {}
        self.track_peak_bboxes: Dict[int, np.ndarray] = {}
        self._auto_mode = not bool(self.config.lanes)
        self._warmup_frames = getattr(self.config.road, "warmup_frames", 40)

    @property
    def lane_vectors(self) -> List[Tuple[float, float]]:
        return [tuple(getattr(l, "permitted_unit_vector", (0.0, 1.0))) for l in self.lane_detector.lanes]

    def process_frame(self, frame: np.ndarray, frame_idx: int, total_frames: int = 0) -> np.ndarray:
        annotated = frame.copy()
        dets, raw_hist = detect_and_track_step(
            self.model, self.tracker, frame, self.road_poly, self.crosswalk_checker.crosswalk_polygons,
            self.lane_detector.lane_zones, self.crosswalk_checker.crosswalk_zones, frame_idx, self.imgsz, self.device
        )
        if self._auto_mode:
            new_ann = step_auto_calibration(
                self.lane_detector, self.road_poly, raw_hist, frame_idx,
                self._warmup_frames, self.crosswalk_checker.crosswalk_zones
            )
            if new_ann is not None:
                self.ann = new_ann

        for za in self.ann.zone_annotators:
            annotated = za.annotate(scene=annotated)
        for box, tid in zip(dets.xyxy, dets.tracker_id):
            if tid is not None and (tid not in self.track_peak_frames or frame_idx % 10 == 0):
                self.track_peak_frames[tid], self.track_peak_bboxes[tid] = frame.copy(), box.copy()

        h_peds, s_peds = self.pedestrian_checker.check_safety(
            dets, self.lane_detector.lane_zones, self.crosswalk_checker.crosswalk_zones, raw_hist, frame_idx
        )
        log_candidates_for_pedestrians(self.event_verifier, h_peds, raw_hist, frame_idx)
        annotated = draw_pedestrians(annotated, h_peds, s_peds, self.ann)

        veh_dets = dets[dets.class_id != 0]
        if len(veh_dets) > 0 and self.lane_detector.is_calibrated:
            cw_res = self.crosswalk_checker.check_motorcycles(veh_dets, raw_hist, frame_idx, self.lane_vectors)
            log_candidates_for_crosswalk(self.event_verifier, cw_res, raw_hist, frame_idx)
            wrong_tids = check_lane_violations(
                self.lane_detector.lanes, self.lane_detector.lane_zones, self.direction_checker,
                self.lane_detector, veh_dets, raw_hist, frame_idx, self.event_verifier
            )
            annotated = draw_vehicles(annotated, veh_dets, wrong_tids, cw_res, self.ann)

        self.event_verifier.step(frame_idx)
        return draw_render_progress_bar(annotated, frame_idx + 1, total_frames) if total_frames > 0 else annotated

    def finalize(self) -> Tuple[List[Any], Dict[str, Any]]:
        final_events = self.event_verifier.finalize()
        self.event_verifier.export_json(self.output_dir / "detected_events.json")
        render_evidence_cards(
            final_events, self.tracker.tracks, self.track_peak_frames,
            self.track_peak_bboxes, self.explanation_engine
        )
        eval_metrics = self.event_verifier.evaluate_against_ground_truth(self.config_path.parents[1] / "data" / "eval_gt.json")
        with open(self.output_dir / "evaluation_summary.json", "w", encoding="utf-8") as f:
            json.dump(eval_metrics, f, indent=2)
        return (final_events, eval_metrics)
