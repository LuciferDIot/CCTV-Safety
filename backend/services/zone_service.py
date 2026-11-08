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
from views.zone_views import IntersectionZonesConfig


class ZoneService:
    """Manages intersection zone configurations with safe in-memory overrides."""
    _shared_override: Optional[IntersectionZonesConfig] = None

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_path = settings.resolve(settings.config_file)

    @property
    def in_memory_override(self) -> Optional[IntersectionZonesConfig]:
        """Class-level shared override active across all service instances."""
        return ZoneService._shared_override

    @in_memory_override.setter
    def in_memory_override(self, val: Optional[IntersectionZonesConfig]) -> None:
        ZoneService._shared_override = val

    def get_config(self) -> IntersectionZonesConfig:
        """Returns the in-memory override if present, else loads base JSON from disk."""
        if self.in_memory_override:
            return self.in_memory_override
        if not self.config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return IntersectionZonesConfig(**data)

    def update_config(self, new_config: IntersectionZonesConfig) -> IntersectionZonesConfig:
        """Stores calibrated zones in-memory without modifying disk configuration."""
        self.in_memory_override = new_config
        return new_config

    def reset_config(self) -> IntersectionZonesConfig:
        """Clears in-memory overrides and restores the default configuration from disk."""
        self.in_memory_override = None
        return self.get_config()
