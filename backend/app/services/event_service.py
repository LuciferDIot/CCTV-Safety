"""Event retrieval, demo scenario injection, filtering, and export formatting."""
import io, csv, json
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException
from app.config import Settings
from app.schemas.events import TrafficEvent, EvidenceFrames, PostureMetrics
from app.services.event_demo import get_demo_scenarios


class EventService:
    def __init__(self, settings: Settings):
        self.output_dir = settings.resolve(settings.output_dir)
        self.events_file = self.output_dir / "detected_events.json"
        self.evidence_cards_dir = settings.resolve(settings.evidence_cards_dir)
        self.events_dir = settings.resolve(settings.events_dir)

    def get_events(
        self, status: Optional[str] = None, event_type: Optional[str] = None,
        track_id: Optional[int] = None, include_demo: bool = False
    ) -> List[TrafficEvent]:
        events: List[TrafficEvent] = []
        if self.events_file.exists():
            try:
                with open(self.events_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_list = data if isinstance(data, list) else data.get("events", [])
                events.extend([self._to_traffic_event(item) for item in raw_list])
            except Exception:
                pass
        if include_demo:
            events.extend([self._to_traffic_event(d) for d in get_demo_scenarios()])

        if status:
            events = [e for e in events if e.status.upper() == status.upper()]
        if event_type:
            events = [e for e in events if e.event_type.upper() == event_type.upper()]
        if track_id is not None:
            events = [e for e in events if track_id in e.track_ids]
        return events

    def get_event_by_id(self, event_id: str) -> TrafficEvent:
        for ev in self.get_events(include_demo=True):
            if ev.event_id.upper() == event_id.upper():
                return ev
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    def export_csv(self, include_demo: bool = False) -> str:
        events = self.get_events(include_demo=include_demo)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["event_id", "status", "event_type", "track_ids", "time_start", "time_end", "confidence", "explanation"])
        for e in events:
            writer.writerow([e.event_id, e.status, e.event_type, ";".join(map(str, e.track_ids)), e.time_start, e.time_end, e.confidence, e.explanation or ""])
        return buf.getvalue()

    def get_evidence_frame(self, event_id: str, frame_type: str) -> Path:
        for p in [self.evidence_cards_dir / f"{event_id}_{frame_type}.jpg", self.events_dir / f"{event_id}_{frame_type}.jpg"]:
            if p.exists():
                return p
        cards = list(self.evidence_cards_dir.glob(f"{event_id}_*.jpg")) or list(self.evidence_cards_dir.glob(f"*{event_id}*.jpg"))
        if cards:
            return cards[0]
        all_cards = list(self.evidence_cards_dir.glob("*.jpg"))
        if all_cards:
            return all_cards[0]
        raise HTTPException(status_code=404, detail=f"Evidence frame '{frame_type}' for {event_id} not found")

    def _to_traffic_event(self, d: dict) -> TrafficEvent:
        e_id = d.get("event_id") or d.get("id") or f"EV-{d.get('track_id', 0)}"
        status_val = (d.get("status") or d.get("verdict") or "CONFIRMED").upper()
        if status_val in ["SUSPECTED", "CROSSWALK_RIDING", "WRONG_WAY"]:
            status_val = "CONFIRMED"
        elif status_val in ["EXEMPT_WALKING", "WALKING_MOTORCYCLE"]:
            status_val = "EXEMPT"

        return TrafficEvent(
            event_id=e_id, status=status_val,
            event_type=d.get("event_type", d.get("type", "UNKNOWN")),
            track_ids=d.get("track_ids") or ([d["track_id"]] if "track_id" in d else []),
            stitched=d.get("stitched", False), start_frame=d.get("start_frame", 0),
            end_frame=d.get("end_frame", 0),
            time_start=d.get("time_start", d.get("start_ts", 0.0)),
            time_end=d.get("time_end", d.get("end_ts", 0.0)),
            duration_sec=d.get("duration_sec", d.get("duration_s", 0.0)),
            confidence=d.get("confidence", 0.85),
            posture_metrics=PostureMetrics(**d.get("posture_metrics", {})),
            evidence=EvidenceFrames(
                entry_frame_url=f"/api/events/{e_id}/frames/entry",
                midpoint_peak_url=f"/api/events/{e_id}/frames/midpoint",
                exit_frame_url=f"/api/events/{e_id}/frames/exit"
            ),
            metrics=d.get("metrics", {}), explanation=d.get("explanation", d.get("reason")), raw_json=d
        )
