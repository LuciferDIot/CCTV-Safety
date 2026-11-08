"""Application service for reading, updating, and resetting in-memory zones."""
import json
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from config import Settings
from views.zone_views import IntersectionZonesConfig


class ZoneService:
    _shared_override: Optional[IntersectionZonesConfig] = None

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_path = settings.resolve(settings.config_file)

    @property
    def in_memory_override(self) -> Optional[IntersectionZonesConfig]:
        return ZoneService._shared_override

    @in_memory_override.setter
    def in_memory_override(self, val: Optional[IntersectionZonesConfig]) -> None:
        ZoneService._shared_override = val

    def get_config(self) -> IntersectionZonesConfig:
        if self.in_memory_override:
            return self.in_memory_override
        if not self.config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return IntersectionZonesConfig(**data)

    def update_config(self, new_config: IntersectionZonesConfig) -> IntersectionZonesConfig:
        self.in_memory_override = new_config
        return new_config

    def reset_config(self) -> IntersectionZonesConfig:
        self.in_memory_override = None
        return self.get_config()
