"""Application service for safety event querying and CSV/JSON export."""
import io, csv, json
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException
from config import Settings
from views.event_views import TrafficEvent
from services.event_demo import get_demo_scenarios


class EventService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.events_dir = settings.resolve(settings.events_dir)
        self.evidence_dir = settings.resolve(settings.evidence_cards_dir)
        self.output_dir = settings.resolve(settings.output_dir)

    def get_events(self, status: Optional[str] = None, event_type: Optional[str] = None, track_id: Optional[int] = None, include_demo: bool = True) -> List[TrafficEvent]:
        events: List[TrafficEvent] = []
        json_file = self.output_dir / "detected_events.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    events.extend([self._to_schema(item) for item in data.get("events", [])])
            except (json.JSONDecodeError, OSError): pass

        if include_demo or not events:
            existing_ids = {e.event_id for e in events}
            events.extend([TrafficEvent(**d) for d in get_demo_scenarios() if d["event_id"] not in existing_ids])

        if status: events = [e for e in events if e.status.upper() == status.upper()]
        if event_type: events = [e for e in events if e.event_type.upper() == event_type.upper()]
        if track_id is not None: events = [e for e in events if e.tracking_id == track_id or track_id in e.track_ids]
        return events

    def get_event_by_id(self, event_id: str) -> TrafficEvent:
        for ev in self.get_events(include_demo=True):
            if ev.event_id == event_id: return ev
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")

    def export_csv(self, include_demo: bool = True) -> str:
        events = self.get_events(include_demo=include_demo)
        output = io.StringIO()
        fieldnames = ["event_id", "status", "event_type", "start_time", "end_time", "duration_seconds", "tracking_id", "confidence", "alignment_dot_product", "posture", "stitched", "natural_language_explanation"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for e in events:
            writer.writerow({
                "event_id": e.event_id, "status": e.status, "event_type": e.event_type,
                "start_time": e.start_time, "end_time": e.end_time, "duration_seconds": e.duration_seconds,
                "tracking_id": e.tracking_id, "confidence": e.confidence,
                "alignment_dot_product": e.alignment_dot_product, "posture": e.posture_metrics.posture,
                "stitched": e.stitched, "natural_language_explanation": e.natural_language_explanation,
            })
        return output.getvalue()

    def get_evidence_frame(self, event_id: str, frame_type: str) -> Path:
        # Defensive path traversal sanitization: strip directories and reject dot traversal tokens
        safe_eid, safe_ft = Path(event_id).name, Path(frame_type).name
        if safe_eid in ("", ".", "..") or safe_ft in ("", ".", ".."):
            raise HTTPException(status_code=400, detail="Invalid frame request")
        p = self.evidence_dir / f"{safe_eid}_{safe_ft}.jpg"
        if not p.is_file():
            refs = list((self.settings.project_root / "data" / "reference_frames").glob("*.jpg"))
            if refs: return refs[0]
            raise HTTPException(status_code=404, detail=f"Evidence frame not found for {event_id}")
        return p

    def _to_schema(self, item: dict) -> TrafficEvent:
        """Normalizes multi-format dictionary keys across live detector output and eval_gt.json:
        start_ts / start_time, duration_s / duration_sec, details / explanation / reason."""
        st, et = float(item.get("start_ts", item.get("start_time", 0.0))), float(item.get("end_ts", item.get("end_time", 0.0)))
        dur = float(item.get("duration_s", item.get("duration_sec", et - st)))
        raw_tids = item.get("track_ids", [])
        tid = int(item.get("tracking_id") or (raw_tids[0] if raw_tids else item.get("track_id", 0)) or 0)
        tids = [int(x) for x in raw_tids] if raw_tids else ([tid] if tid else [])
        detail = str(item.get("details", item.get("explanation", item.get("reason", ""))))
        return TrafficEvent(
            event_id=str(item.get("id", item.get("event_id", "EV-00"))),
            status=item.get("status", item.get("verdict", "CONFIRMED")),
            event_type=item.get("event_type", "WRONG_WAY"),
            start_time=round(st, 2), end_time=round(et, 2), duration_seconds=round(dur, 2),
            tracking_id=tid, track_ids=tids, confidence=round(float(item.get("confidence", 0.88)), 2),
            natural_language_explanation=detail
        )
