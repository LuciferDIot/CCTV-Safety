"""Schemas for traffic safety events, posture metrics, and temporal strips."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PostureMetrics(BaseModel):
    """Metrics distinguishing mounted vs dismounted walking behavior."""
    posture: str = "mounted"  # mounted, dismounted, unknown
    vertical_clearance: Optional[float] = None
    lateral_offset_px: Optional[float] = None
    speed_px_per_frame: Optional[float] = None


class EvidenceFrames(BaseModel):
    """URLs to 3-frame temporal strip explaining the event."""
    entry_frame_url: Optional[str] = None
    midpoint_peak_url: Optional[str] = None
    exit_frame_url: Optional[str] = None
    card_url: Optional[str] = None


class TrafficEvent(BaseModel):
    """Unified schema for confirmed, exempt, insufficient, and ignored events."""
    event_id: str
    status: str  # CONFIRMED, EXEMPT, INSUFFICIENT_EVIDENCE, IGNORED
    event_type: str  # WRONG_WAY, CROSSWALK_RIDING, WALKING_MOTORCYCLE, LEGITIMATE_TURN, etc.
    track_ids: List[int] = Field(default_factory=list)
    stitched: bool = False
    start_frame: int = 0
    end_frame: int = 0
    time_start: float = 0.0
    time_end: float = 0.0
    duration_sec: float = 0.0
    confidence: float = 0.0
    posture_metrics: PostureMetrics = Field(default_factory=PostureMetrics)
    evidence: EvidenceFrames = Field(default_factory=EvidenceFrames)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    raw_json: Dict[str, Any] = Field(default_factory=dict)

