"""
Event Verifier & Lifecycle Manager for CCTV Intersection Safety
Produces timestamped suspected/confirmed events linked to tracks,
avoids duplicate alerts, flags INSUFFICIENT_EVIDENCE for ambiguous tracks,
and evaluates against ground-truth benchmarks.
"""
from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

class EventRecord:
    def __init__(
        self,
        event_id: str,
        event_type: str,
        start_frame: int,
        start_ts: float,
        track_id: int,
        confidence: float = 0.88,
        details: str = "",
        lane_or_zone: str = ""
    ):
        self.id = event_id
        self.event_type = event_type
        self.start_frame = start_frame
        self.end_frame = start_frame
        self.start_ts = round(start_ts, 2)
        self.end_ts = round(start_ts, 2)
        self.track_id = track_id
        self.confidence = confidence
        self.details = details
        self.lane_or_zone = lane_or_zone
        self.status = "ACTIVE"
        self.frame_indices: List[int] = [start_frame]
        self.bounding_boxes: List[np.ndarray] = []
        self.positions: List[Tuple[float, float]] = []

    def update(self, frame_idx: int, timestamp: float, xyxy: Optional[np.ndarray] = None, pos: Optional[Tuple[float, float]] = None):
        self.end_frame = frame_idx
        self.end_ts = round(timestamp, 2)
        self.frame_indices.append(frame_idx)
        if xyxy is not None:
            self.bounding_boxes.append(xyxy.copy())
        if pos is not None:
            self.positions.append(pos)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "event_type": str(self.event_type),
            "start_ts": float(self.start_ts),
            "end_ts": float(self.end_ts),
            "track_id": int(self.track_id),
            "confidence": round(float(self.confidence), 3),
            "lane_or_zone": str(self.lane_or_zone),
            "details": str(self.details),
            "duration_s": round(float(self.end_ts - self.start_ts), 2)
        }

class EventVerifier:
    def __init__(
        self,
        fps: float = 30.0,
        min_confirmed_duration_s: float = 0.5,
        max_event_inactivity_frames: int = 15,
    ):
        self.fps = fps
        self.min_confirmed_duration_s = min_confirmed_duration_s
        self.max_event_inactivity_frames = max_event_inactivity_frames

        self.event_counter = 1
        self.active_events: Dict[Tuple[int, str], EventRecord] = {}
        self.completed_events: List[EventRecord] = []
        self.last_seen_frame_for_event: Dict[Tuple[int, str], int] = {}

    def log_candidate(
        self,
        track_id: int,
        event_type: str,
        frame_idx: int,
        xyxy: Optional[np.ndarray] = None,
        pos: Optional[Tuple[float, float]] = None,
        confidence: float = 0.88,
        lane_or_zone: str = "",
        details: str = "",
        is_ambiguous: bool = False,
        track_len: int = 10
    ):
        """
        Logs a candidate detection for a track and manages its deduplicated lifecycle.
        Flags INSUFFICIENT_EVIDENCE if track is too short or ambiguous.
        """
        timestamp = frame_idx / self.fps
        effective_event_type = event_type
        if is_ambiguous or track_len < 6:
            effective_event_type = "INSUFFICIENT_EVIDENCE"

        key = (track_id, effective_event_type)

        if key in self.active_events:
            event = self.active_events[key]
            event.update(frame_idx, timestamp, xyxy, pos)
            self.last_seen_frame_for_event[key] = frame_idx
        else:
            event_id = f"EV-{self.event_counter:02d}"
            self.event_counter += 1
            event = EventRecord(
                event_id=event_id,
                event_type=effective_event_type,
                start_frame=frame_idx,
                start_ts=timestamp,
                track_id=track_id,
                confidence=confidence,
                details=details,
                lane_or_zone=lane_or_zone
            )
            event.update(frame_idx, timestamp, xyxy, pos)
            self.active_events[key] = event
            self.last_seen_frame_for_event[key] = frame_idx

    def step(self, current_frame_idx: int):
        """Closes events that have concluded after a period of inactivity."""
        keys_to_close = []
        for key, last_frame in self.last_seen_frame_for_event.items():
            if current_frame_idx - last_frame > self.max_event_inactivity_frames:
                keys_to_close.append(key)

        for key in keys_to_close:
            event = self.active_events.pop(key)
            del self.last_seen_frame_for_event[key]
            duration = event.end_ts - event.start_ts

            if duration < 0.35 and event.event_type not in ["EXEMPT_WALKING", "INSUFFICIENT_EVIDENCE"]:
                event.event_type = "INSUFFICIENT_EVIDENCE"
                event.details += " (Insufficient sustained duration)"

            event.status = "CLOSED"
            self.completed_events.append(event)

    def finalize(self) -> List[EventRecord]:
        """Flushes all remaining active events at end of video stream."""
        for key, event in list(self.active_events.items()):
            duration = event.end_ts - event.start_ts
            if duration < 0.35 and event.event_type not in ["EXEMPT_WALKING", "INSUFFICIENT_EVIDENCE"]:
                event.event_type = "INSUFFICIENT_EVIDENCE"
            event.status = "CLOSED"
            self.completed_events.append(event)
        self.active_events.clear()
        self.last_seen_frame_for_event.clear()
        return self.completed_events

    def export_json(self, output_path: Path) -> List[Dict[str, Any]]:
        """Exports all finalized events to JSON matching the evaluation schema."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = [ev.to_dict() for ev in self.completed_events]
        payload = {
            "version": "1.0",
            "total_events": len(records),
            "events": records
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return records

    def evaluate_against_ground_truth(self, gt_path: Path) -> Dict[str, Any]:
        """
        Evaluates detected events against ground truth JSON dataset.
        Computes TP, FP, FN, Precision, Recall, and F1 per event category.
        """
        if not gt_path.exists():
            return {"error": f"Ground truth not found at {gt_path}"}

        with open(gt_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        gt_events = gt_data.get("events", [])
        pred_events = [ev.to_dict() for ev in self.completed_events]

        metrics = {
            "total_gt": len(gt_events),
            "total_pred": len(pred_events),
            "categories": defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0}),
            "matches": []
        }

        matched_gt = set()
        matched_pred = set()

        for p_idx, pred in enumerate(pred_events):
            p_tid = pred["track_id"]
            p_type = pred["event_type"]
            p_start = pred["start_ts"]
            p_end = pred["end_ts"]

            best_gt_idx = None
            for g_idx, gt in enumerate(gt_events):
                if g_idx in matched_gt:
                    continue
                g_tid = gt["track_id"]
                g_type = gt["event_type"]
                g_start = gt["start_ts"]
                g_end = gt["end_ts"]

                time_overlap = max(0, min(p_end, g_end) - max(p_start, g_start))
                is_match = (p_tid == g_tid) or (time_overlap > 0.4 and p_type == g_type)

                if is_match and p_type == g_type:
                    best_gt_idx = g_idx
                    break

            if best_gt_idx is not None:
                matched_gt.add(best_gt_idx)
                matched_pred.add(p_idx)
                metrics["categories"][p_type]["TP"] += 1
                metrics["matches"].append({
                    "gt_id": gt_events[best_gt_idx]["id"],
                    "pred_id": pred["id"],
                    "event_type": p_type,
                    "status": "TP"
                })
            else:
                metrics["categories"][p_type]["FP"] += 1

        for g_idx, gt in enumerate(gt_events):
            if g_idx not in matched_gt:
                g_type = gt["event_type"]
                metrics["categories"][g_type]["FN"] += 1

        total_tp = sum(c["TP"] for c in metrics["categories"].values())
        total_fp = sum(c["FP"] for c in metrics["categories"].values())
        total_fn = sum(c["FN"] for c in metrics["categories"].values())

        prec = total_tp / max(1, total_tp + total_fp)
        rec = total_tp / max(1, total_tp + total_fn)
        f1 = 2 * prec * rec / max(1e-6, prec + rec)

        metrics["overall"] = {
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1_score": round(f1, 3)
        }
        return metrics
