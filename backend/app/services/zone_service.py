"""Zone configuration service for reading, updating, and resetting zones.json."""
import json
import shutil
from pathlib import Path
from fastapi import HTTPException
from app.config import Settings
from app.schemas.zones import IntersectionZonesConfig


class ZoneService:
    """Manages road polygon, crosswalks, and lane vector configuration."""

    def __init__(self, settings: Settings):
        self.config_path = settings.resolve(settings.config_file)
        self.backup_path = self.config_path.with_suffix(".default.json")
        self._ensure_backup()

    def _ensure_backup(self) -> None:
        if self.config_path.exists() and not self.backup_path.exists():
            shutil.copy(self.config_path, self.backup_path)

    def get_config(self) -> IntersectionZonesConfig:
        if not self.config_path.exists():
            raise HTTPException(status_code=404, detail="Configuration file zones.json not found")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return IntersectionZonesConfig(**data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load zones configuration: {e}")

    def update_config(self, new_config: IntersectionZonesConfig) -> IntersectionZonesConfig:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config.model_dump(), f, indent=2)
            return new_config
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save zones configuration: {e}")

    def reset_config(self) -> IntersectionZonesConfig:
        if self.backup_path.exists():
            shutil.copy(self.backup_path, self.config_path)
            return self.get_config()
        raise HTTPException(status_code=404, detail="No default backup configuration exists to reset to")

