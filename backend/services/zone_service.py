"""Application service for reading, updating, and resetting in-memory zones.

In-Memory Override Pattern:
When operators adjust or calibrate intersection zone polygons via the web UI,
updates are preserved in-memory using `ZoneService._shared_override`.
This allows real-time interactive tuning without corrupting or overwriting
the git-versioned configuration files on disk. Calling `reset_config()`
clears the override and restores default coordinates from disk.
"""
import json
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from config import Settings
from views.zone_views import IntersectionZonesConfig, RoadZoneConfig, CrosswalkZoneConfig, PerspectiveScale


class ZoneService:
    """Manages intersection zone configurations with safe in-memory overrides."""
    _shared_override: Optional[IntersectionZonesConfig] = None

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_path = settings.resolve(settings.config_file)

    @staticmethod
    def create_default_zones(video_file: Optional[str] = "video.mp4", width: int = 1920, height: int = 1080) -> IntersectionZonesConfig:
        safe_name = str(video_file or "video.mp4")
        safe_stem = Path(safe_name).stem.replace("_annotated", "").replace("annotated_", "")
        w, h = max(100, int(width or 1920)), max(100, int(height or 1080))
        road_poly = [
            [int(0.18 * w), int(0.15 * h)],
            [int(0.82 * w), int(0.15 * h)],
            [int(0.88 * w), int(0.85 * h)],
            [int(0.12 * w), int(0.85 * h)],
        ]
        cw_poly = [
            [int(0.75 * w), int(0.35 * h)],
            [int(0.25 * w), int(0.35 * h)],
            [int(0.25 * w), int(0.55 * h)],
            [int(0.75 * w), int(0.55 * h)],
        ]
        return IntersectionZonesConfig(
            camera_id=f"cam_{safe_stem}" if safe_stem else "cam_01",
            video_file=safe_name,
            fps=30.0,
            perspective_scale_by_y=PerspectiveScale(y_top=0.1, y_bottom=1.0, weight_top=0.35, weight_bottom=1.0),
            road=RoadZoneConfig(id="road", polygon=road_poly, warmup_frames=40),
            crosswalks=[CrosswalkZoneConfig(id="crosswalk_zone", polygon=cw_poly)],
            lanes=[],
            metadata={},
        )

    @property
    def in_memory_override(self) -> Optional[IntersectionZonesConfig]:
        """Class-level shared override active across all service instances."""
        return ZoneService._shared_override

    @in_memory_override.setter
    def in_memory_override(self, val: Optional[IntersectionZonesConfig]) -> None:
        ZoneService._shared_override = val

    def get_config(self, video_file: Optional[str] = None, width: int = 1920, height: int = 1080) -> IntersectionZonesConfig:
        """Returns the in-memory override if present, or scaled defaults for video, else base JSON from disk."""
        w, h = max(100, int(width or 1920)), max(100, int(height or 1080))
        if video_file:
            stem = Path(video_file).stem.replace("_annotated", "").replace("annotated_", "")
            if self.in_memory_override:
                ovr_stem = Path(self.in_memory_override.video_file).stem.replace("_annotated", "").replace("annotated_", "")
                if ovr_stem == stem:
                    return self.in_memory_override
            cfg = self.create_default_zones(video_file, w, h)
            self.in_memory_override = cfg
            return cfg
        if self.in_memory_override:
            return self.in_memory_override
        if not self.config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("video_file") and (Path(data["video_file"]).stem in {"intersection_01", "intersection_02", "intersection_03"} or Path(data["video_file"]).stem.startswith("intersection_")):
            data["video_file"] = ""
        return IntersectionZonesConfig(**data)

    def update_config(self, new_config: IntersectionZonesConfig) -> IntersectionZonesConfig:
        """Stores calibrated zones in-memory without modifying disk configuration."""
        self.in_memory_override = new_config
        return new_config

    def reset_config(self, video_file: Optional[str] = None, width: int = 1920, height: int = 1080) -> IntersectionZonesConfig:
        """Clears in-memory overrides and restores default configuration scaled to video."""
        w, h = max(100, int(width or 1920)), max(100, int(height or 1080))
        if video_file:
            cfg = self.create_default_zones(video_file, w, h)
            self.in_memory_override = cfg
            return cfg
        self.in_memory_override = None
        return self.get_config()
