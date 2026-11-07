"""Safety event candidate logging and lane direction violation checking."""
from typing import Dict, Set, Any
import numpy as np
import supervision as sv


def log_candidates_for_lane(
    event_verifier: Any, confirmed_tids: Set[int], suspected_tids: Set[int],
    track_hist: dict, lane_id: str, frame_idx: int
) -> None:
    """Log confirmed and suspected wrong-way candidate events."""
    for tid in confirmed_tids:
        pos = track_hist[tid][-1] if tid in track_hist else None
        event_verifier.log_candidate(
            track_id=tid, event_type="WRONG_WAY", frame_idx=frame_idx,
            pos=pos, confidence=0.95, lane_or_zone=lane_id,
            details=f"Sustained wrong-way movement counter to flow in {lane_id}",
            is_ambiguous=False, track_len=len(track_hist.get(tid, []))
        )
    for tid in suspected_tids - confirmed_tids:
        pos = track_hist[tid][-1] if tid in track_hist else None
        event_verifier.log_candidate(
            track_id=tid, event_type="WRONG_WAY", frame_idx=frame_idx,
            pos=pos, confidence=0.60, lane_or_zone=lane_id,
            details="Brief counter-flow deviation near boundary or short track",
            is_ambiguous=True, track_len=len(track_hist.get(tid, []))
        )


def log_candidates_for_crosswalk(
    event_verifier: Any, cw_results: Dict[int, str], track_hist: dict, frame_idx: int
) -> None:
    """Log crosswalk riding and exempt walking candidates."""
    for tid, st in cw_results.items():
        if st in ["CROSSWALK_RIDING", "EXEMPT_WALKING"]:
            conf = 0.94 if st == "CROSSWALK_RIDING" else 0.88
            msg = "Riding motorcycle across pedestrian crosswalk" if st == "CROSSWALK_RIDING" else "Dismounted pedestrian walking bike"
            pos = track_hist[tid][-1] if tid in track_hist else None
            event_verifier.log_candidate(
                track_id=tid, event_type=st, frame_idx=frame_idx,
                pos=pos, confidence=conf, lane_or_zone="crosswalk",
                details=msg, track_len=len(track_hist.get(tid, []))
            )


def log_candidates_for_pedestrians(
    event_verifier: Any, h_peds: sv.Detections, track_hist: dict, frame_idx: int
) -> None:
    """Log pedestrian roadway incursion candidates outside crosswalk."""
    if len(h_peds) == 0 or h_peds.tracker_id is None:
        return
    for tid in h_peds.tracker_id:
        if tid is None:
            continue
        pos = track_hist[tid][-1] if tid in track_hist else None
        event_verifier.log_candidate(
            track_id=int(tid), event_type="PEDESTRIAN_IN_LANE", frame_idx=frame_idx,
            pos=pos, confidence=0.90, lane_or_zone="roadway",
            details="Pedestrian walking in active vehicle lane outside crosswalk",
            is_ambiguous=False, track_len=len(track_hist.get(tid, []))
        )


def check_lane_violations(
    lanes: list, lane_zones: list, dir_checker: Any,
    lane_detector: Any, veh_dets: sv.Detections,
    raw_hist: dict, frame_idx: int, event_verifier: Any
) -> Set[int]:
    """Check all lanes for wrong-way vehicles and log events to verifier."""
    all_conf_wrong = set()
    for lane, l_zone in zip(lanes, lane_zones):
        l_mask = l_zone.trigger(detections=veh_dets)
        if not np.any(l_mask):
            continue
        l_dets = veh_dets[l_mask]
        ambig_m = np.array([
            lane_detector.assign_lane(((b[0] + b[2]) / 2.0, b[3]))[1]
            for b in l_dets.xyxy
        ])
        u_vec = tuple(getattr(lane, "permitted_unit_vector", getattr(lane, "direction", (0.0, 1.0))))
        conf_w, susp_w = dir_checker.check_detections(
            l_dets, u_vec, raw_hist, lane.id, frame_idx, ambig_m
        )
        c_tids = set(l_dets.tracker_id[conf_w])
        s_tids = set(l_dets.tracker_id[susp_w])
        all_conf_wrong |= c_tids
        log_candidates_for_lane(event_verifier, c_tids, s_tids, raw_hist, lane.id, frame_idx)
    return all_conf_wrong
