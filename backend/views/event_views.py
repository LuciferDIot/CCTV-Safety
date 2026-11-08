"""Views (DTOs) for traffic safety events, telemetry, and evidence cards."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class PostureMetrics(BaseModel):
    aspect_ratio: float = 1.45
    vertical_extent_px: float = 210.0
    posture: str = "mounted"


class EvidenceFrames(BaseModel):
    entry_frame_idx: int = 0
    midpoint_frame_idx: int = 1
    exit_frame_idx: int = 2
    entry_frame_url: str = ""
    midpoint_frame_url: str = ""
    exit_frame_url: str = ""
    evidence_card_url: str = ""


class TrafficEvent(BaseModel):
    event_id: str
    status: str = Field(description="CONFIRMED | EXEMPT | INSUFFICIENT_EVIDENCE | IGNORED")
    event_type: str = Field(description="WRONG_WAY | CROSSWALK_RIDING | PEDESTRIAN_IN_LANE | etc.")
    start_time: float
    end_time: float
    duration_seconds: float
    tracking_id: int
    confidence: float
    displacement_vector: List[float] = Field(default_factory=lambda: [0.0, 1.0])
    alignment_dot_product: float = -0.85
    permitted_flow_vector: List[float] = Field(default_factory=lambda: [0.0, 1.0])
    posture_metrics: PostureMetrics = Field(default_factory=PostureMetrics)
    evidence_frames: Optional[EvidenceFrames] = None
    natural_language_explanation: str = ""
    stitched: bool = False

    track_ids: List[int] = Field(default_factory=list)
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    duration_sec: Optional[float] = None
    explanation: Optional[str] = None
    evidence: Optional[EvidenceFrames] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    raw_json: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def populate_from_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "event_id" not in data and "id" in data:
                data["event_id"] = str(data["id"])
            if "tracking_id" not in data and "track_id" in data:
                data["tracking_id"] = data["track_id"]
            elif "tracking_id" not in data and "track_ids" in data and len(data["track_ids"]) > 0:
                data["tracking_id"] = data["track_ids"][0]
            if "start_time" not in data and "time_start" in data:
                data["start_time"] = data["time_start"]
            if "end_time" not in data and "time_end" in data:
                data["end_time"] = data["time_end"]
            if "duration_seconds" not in data and "duration_sec" in data:
                data["duration_seconds"] = data["duration_sec"]
            if "natural_language_explanation" not in data and "explanation" in data:
                data["natural_language_explanation"] = data["explanation"]
        return data

    @model_validator(mode="after")
    def populate_frontend_aliases(self) -> "TrafficEvent":
        if not self.track_ids:
            self.track_ids = [self.tracking_id]
        if self.time_start is None:
            self.time_start = self.start_time
        if self.time_end is None:
            self.time_end = self.end_time
        if self.duration_sec is None:
            self.duration_sec = self.duration_seconds
        if self.explanation is None:
            self.explanation = self.natural_language_explanation
        if self.evidence_frames is None:
            self.evidence_frames = EvidenceFrames(
                entry_frame_url=f"/api/events/{self.event_id}/evidence/entry",
                midpoint_frame_url=f"/api/events/{self.event_id}/evidence/midpoint",
                exit_frame_url=f"/api/events/{self.event_id}/evidence/exit",
                evidence_card_url=f"/api/events/{self.event_id}/evidence/card"
            )
        if self.evidence is None:
            self.evidence = self.evidence_frames
        if not self.metrics:
            self.metrics = {"angle_deg": 180.0, "alignment": self.alignment_dot_product, "speed_px": 5.0}
        return self
