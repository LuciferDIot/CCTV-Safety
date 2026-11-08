"""Orchestration of YOLO tracking, safety checks, and HUD generation."""
from pathlib import Path
from typing import Optional, Any, Tuple, List, Dict
import numpy as np, torch, cv2, supervision as sv
from views.zone_views import load_intersection_config, parse_intersection_config
from services.safety.direction import DirectionChecker; from services.safety.crosswalk import CrosswalkSafetyChecker
from services.safety.pedestrian import PedestrianSafetyChecker; from services.safety.fusion import resolve_riders_and_pedestrians
from services.safety.clustering import LaneAutoDetector; from models.event import EventRecord
from services.cv.model import load_detection_model; from services.cv.tracker import RobustTrackerManager
from services.cv.annotator import create_annotators, draw_pedestrians, draw_vehicles; from services.cv.hud import draw_render_progress_bar

# COCO target classes: 0: Person, 1: Bicycle, 2: Car, 3: Motorcycle, 5: Bus, 7: Truck
COCO_TARGET_CLASSES = [0, 1, 2, 3, 5, 7]
DEFAULT_VIDEO_FPS = 30.0  # Standard CCTV video framerate for timestamp estimation


class IntersectionSafetyPipeline:
    """Orchestrates 6-stage safety pipeline: (1) Detect/Track, (2) Stitch Trajectories,
    (3) Multimodal Fusion, (4) Safety Checks, (5) Event Lifecycle, (6) HUD & Annotation."""

    def __init__(self, config_path: Path, model_path: Optional[Path] = None, output_dir: Optional[Path] = None, device: Optional[str] = None, imgsz: int = 960, override_zones: Optional[Dict[str, Any]] = None, frame_height: Optional[float] = None):
        self.config_path, self.imgsz = Path(config_path), imgsz
        self.config = parse_intersection_config(override_zones) if override_zones else load_intersection_config(self.config_path)
        base = self.config_path.parent.parent
        self.output_dir, self.device = Path(output_dir or base / "data" / "output"), device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model = load_detection_model(model_path, base, self.device)
        persp = getattr(self.config, "perspective_scale_by_y", None)
        fh, raw_fps = float(frame_height or 2160.0), getattr(self.config, "fps", None) or (override_zones.get("fps") if override_zones else None)
        self.fps = float(raw_fps) if raw_fps and float(raw_fps) > 0 else DEFAULT_VIDEO_FPS
        self.tracker, self.direction_checker = RobustTrackerManager(frame_height=fh, perspective_cfg=persp), DirectionChecker(frame_height=fh, perspective_cfg=persp)
        self.crosswalk_checker = CrosswalkSafetyChecker([np.array(cw.polygon) for cw in self.config.crosswalks], frame_height=fh, perspective_cfg=persp)
        self.pedestrian_checker, self.lane_detector = PedestrianSafetyChecker(), LaneAutoDetector(self.config.road.polygon)
        self.detected_lanes = []
        self.road_poly = np.array(self.config.road.polygon, dtype=np.int32)
        cw_polys = [np.array(cw.polygon, dtype=np.int32) for cw in self.config.crosswalks]
        self.lane_zones, self.cw_zones = [sv.PolygonZone(polygon=self.road_poly)], [sv.PolygonZone(polygon=p) for p in cw_polys]
        self.ann = create_annotators([self.road_poly], cw_polys)
        self.active_events: Dict[Tuple[int, str], EventRecord] = {}
        self.completed_events: List[EventRecord] = []
        self.event_counter = 1

    @property
    def lane_vectors(self) -> List[Tuple[float, float]]:
        return [tuple(l.permitted_direction_vector) for l in self.config.lanes] or [tuple(l.permitted_unit_vector) for l in self.detected_lanes] or [(0.0, 1.0)]

    def _get_vehicle_vectors(self, veh_dets: sv.Detections) -> List[Tuple[float, float]]:
        active = self.config.lanes or self.detected_lanes
        if not active: return [self.lane_vectors[0]] * len(veh_dets)
        res = []
        for box in veh_dets.xyxy:
            ax, ay = (float(box[0]) + float(box[2])) / 2.0, float(box[3])
            m = next((l for l in active if cv2.pointPolygonTest(np.array(l.polygon, dtype=np.int32), (ax, ay), False) >= 0), None) or (min(active, key=lambda l: abs(cv2.pointPolygonTest(np.array(l.polygon, dtype=np.int32), (ax, ay), True))) if active else None)
            v = getattr(m, "permitted_direction_vector", None) or getattr(m, "permitted_unit_vector", None) if m else None
            res.append(tuple(v) if v else self.lane_vectors[0])
        return res

    def _record(self, tid: int, etype: str, frame_idx: int, conf: float, detail: str, zone: str) -> None:
        key, ts = (tid, etype), round(frame_idx / self.fps, 2)
        if key not in self.active_events:
            self.active_events[key] = EventRecord(f"EV-{self.event_counter:02d}", etype, frame_idx, ts, tid, conf, detail, zone); self.event_counter += 1
        else: self.active_events[key].update(frame_idx, ts)

    def process_frame(self, frame: np.ndarray, frame_idx: int, total_frames: int = 0) -> np.ndarray:
        res = self.model.track(frame, persist=True, tracker="bytetrack.yaml", classes=COCO_TARGET_CLASSES, imgsz=self.imgsz, device=self.device, conf=0.20, verbose=False)[0]
        dets = sv.Detections.from_ultralytics(res)
        if len(dets) == 0: return draw_render_progress_bar(frame, frame_idx + 1, total_frames) if total_frames > 0 else frame
        dets.tracker_id = np.arange(1, len(dets) + 1, dtype=int) if dets.tracker_id is None else dets.tracker_id
        dets = self.tracker.update_tracks(dets, frame_idx)
        raw_hist = {cid: [(p[1], p[2]) for p in t.history] for cid, t in self.tracker.tracks.items()}
        for trk in self.tracker.tracks.values():
            if len(trk.history) >= 4:
                p_c, p_p = trk.history[-1], trk.history[-4]
                self.lane_detector.observe(p_c[1], p_c[2], (p_c[1] - p_p[1]) / max(1, p_c[0] - p_p[0]), (p_c[2] - p_p[2]) / max(1, p_c[0] - p_p[0]))
        if not self.config.lanes and len(self.lane_detector._obs) >= 15:
            if not self.detected_lanes or len(self.detected_lanes) < 2 or (frame_idx % 20 == 0):
                new_l = self.lane_detector.detect_lanes()
                if new_l and (len(new_l) >= len(self.detected_lanes) or not self.detected_lanes):
                    self.detected_lanes = new_l
        dets = resolve_riders_and_pedestrians(dets, self.lane_zones, self.cw_zones, raw_hist)
        annotated = frame.copy()
        for za in self.ann.zone_annotators: annotated = za.annotate(scene=annotated)
        h_peds, s_peds = self.pedestrian_checker.check_safety(dets, self.lane_zones, self.cw_zones, raw_hist, frame_idx)
        annotated = draw_pedestrians(annotated, h_peds, s_peds, self.ann)
        if len(h_peds) > 0 and h_peds.tracker_id is not None:
            for tid in h_peds.tracker_id: self._record(int(tid), "PEDESTRIAN_IN_LANE", frame_idx, 0.90, "Pedestrian in traffic lane", "roadway")
        veh_dets = dets[dets.class_id != 0]
        if len(veh_dets) > 0:
            cw_res = self.crosswalk_checker.check_motorcycles(veh_dets, raw_hist, frame_idx, self.lane_vectors)
            for tid, status in cw_res.items():
                if status in ("CROSSWALK_RIDING", "EXEMPT_WALKING"): self._record(int(tid), status, frame_idx, 0.89 if status == "CROSSWALK_RIDING" else 0.95, f"Crosswalk {status}", "crosswalk")
            conf_w, _ = self.direction_checker.check_detections(veh_dets, self._get_vehicle_vectors(veh_dets), raw_hist, "lane", frame_idx)
            wrong_tids = set(veh_dets.tracker_id[conf_w]) if len(conf_w) > 0 else set()
            for tid in wrong_tids: self._record(int(tid), "WRONG_WAY", frame_idx, 0.92, "Wrong-way movement against permitted lane flow", "auto_lane")
            annotated = draw_vehicles(annotated, veh_dets, wrong_tids, cw_res, self.ann)
        return draw_render_progress_bar(annotated, frame_idx + 1, total_frames) if total_frames > 0 else annotated

    def finalize(self) -> Tuple[List[Any], Dict[str, Any]]:
        self.completed_events += [e for e in self.active_events.values() if e not in self.completed_events]; self.active_events.clear()
        return (self.completed_events, {"total_events": len(self.completed_events)})
