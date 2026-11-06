"""Event verifier and lifecycle manager."""
from typing import Dict, List, Optional, Any, Tuple
import json
from pathlib import Path
import numpy as np

from src.analytics.record import EventRecord
from src.analytics.evaluator import evaluate_ground_truth


class EventVerifier:
    """Manages event lifecycles, filters short tracks, and exports detected events."""

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
    ) -> None:
        """Log candidate detection and update lifecycle."""
        ts = frame_idx / self.fps
        ev_type = "INSUFFICIENT_EVIDENCE" if (is_ambiguous or track_len < 6) else event_type
        key = (track_id, ev_type)

        if key in self.active_events:
            ev = self.active_events[key]
            ev.update(frame_idx, ts, xyxy, pos)
        else:
            ev = EventRecord(
                f"EV-{self.event_counter:02d}", ev_type, frame_idx,
                ts, track_id, confidence, details, lane_or_zone
            )
            self.event_counter += 1
            ev.update(frame_idx, ts, xyxy, pos)
            self.active_events[key] = ev
        self.last_seen_frame_for_event[key] = frame_idx

    def step(self, current_frame_idx: int) -> None:
        """Close inactive events."""
        to_close = [
            k for k, last_f in self.last_seen_frame_for_event.items()
            if current_frame_idx - last_f > self.max_event_inactivity_frames
        ]
        for k in to_close:
            ev = self.active_events.pop(k)
            del self.last_seen_frame_for_event[k]
            if (ev.end_ts - ev.start_ts < 0.35) and ev.event_type not in ["EXEMPT_WALKING", "INSUFFICIENT_EVIDENCE"]:
                ev.event_type = "INSUFFICIENT_EVIDENCE"
            ev.status = "CLOSED"
            self.completed_events.append(ev)

    def finalize(self) -> List[EventRecord]:
        """Flush active events."""
        for ev in self.active_events.values():
            if (ev.end_ts - ev.start_ts < 0.35) and ev.event_type not in ["EXEMPT_WALKING", "INSUFFICIENT_EVIDENCE"]:
                ev.event_type = "INSUFFICIENT_EVIDENCE"
            ev.status = "CLOSED"
            self.completed_events.append(ev)
        self.active_events.clear()
        self.last_seen_frame_for_event.clear()
        return self.completed_events

    def export_json(self, output_path: Path) -> List[Dict[str, Any]]:
        """Export completed events to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = [ev.to_dict() for ev in self.completed_events]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "total_events": len(records), "events": records}, f, indent=2)
        return records

    def evaluate_against_ground_truth(self, gt_path: Path) -> Dict[str, Any]:
        """Evaluate against ground truth dataset."""
        return evaluate_ground_truth(self.completed_events, gt_path)

