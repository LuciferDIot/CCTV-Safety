"""Pipeline component initialization and post-processing evidence generation."""
from pathlib import Path
from typing import Tuple, Dict, Any, List
import json
import numpy as np

from src.tracking.manager import RobustTrackerManager
from src.safety.lane import AutoLaneDetector
from src.safety.direction import DirectionChecker
from src.safety.crosswalk import CrosswalkSafetyChecker
from src.safety.pedestrian_checker import PedestrianSafetyChecker
from src.analytics.verifier import EventVerifier
from src.analytics.explanation import ExplanationEngine
from src.pipeline.annotators import create_annotators, PipelineAnnotators


def build_pipeline_components(
    config: Any, events_dir: Path
) -> Tuple[
    RobustTrackerManager, AutoLaneDetector, DirectionChecker,
    CrosswalkSafetyChecker, PedestrianSafetyChecker,
    EventVerifier, ExplanationEngine, PipelineAnnotators
]:
    """Instantiate and calibrate all safety pipeline submodules."""
    cam_h = getattr(config, "frame_height", 2160.0)
    persp = getattr(config, "perspective_scale_by_y", getattr(config, "perspective_scale", None))
    fps = getattr(config, "fps", 30.0)

    tracker = RobustTrackerManager(
        max_reconnect_frames=25, max_reconnect_dist_px=180.0,
        frame_height=cam_h, perspective_cfg=persp
    )
    lane_det = AutoLaneDetector(
        road_polygon=np.array(config.road.polygon),
        frame_height=cam_h, perspective_cfg=persp
    )
    fallback = config.lanes if config.lanes else None
    lane_det.calibrate(fallback_lanes=fallback)
    dir_chk = DirectionChecker(
        min_frames=5, min_sustained_frames=5, min_recent_speed=2.0,
        min_total_dist_px=20.0, wrong_way_threshold=-0.60,
        frame_height=cam_h, perspective_cfg=persp
    )
    cw_chk = CrosswalkSafetyChecker(
        crosswalk_polygons=[np.array(cw.polygon) for cw in config.crosswalks],
        min_passage_dist_px=40.0, max_walking_speed=3.8, min_riding_speed=4.8,
        frame_height=cam_h, perspective_cfg=persp
    )
    ped_chk = PedestrianSafetyChecker(min_confirm_frames=2)
    ev_ver = EventVerifier(fps=fps)
    expl_eng = ExplanationEngine(output_dir=events_dir)
    ann = create_annotators(lane_det.lane_zones, cw_chk.crosswalk_zones)
    return (tracker, lane_det, dir_chk, cw_chk, ped_chk, ev_ver, expl_eng, ann)


def render_evidence_cards(
    events: list, tracks: dict, peak_frames: dict, peak_boxes: dict, engine: ExplanationEngine
) -> None:
    """Generate visual breadcrumb cards for completed events."""
    for ev in events:
        tid = ev.track_id
        traj = [(p[1], p[2]) for p in tracks[tid].history] if tid in tracks else []
        pk_f = peak_frames.get(tid)
        bbox = peak_boxes.get(tid)
        if pk_f is not None and len(traj) > 0:
            engine.generate_event_evidence(
                event=ev, peak_frame=pk_f, trajectory=traj, bbox=bbox, rationale=ev.details
            )
