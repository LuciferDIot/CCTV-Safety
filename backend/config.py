"""Application configuration with root directory resolution."""
from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables or .env file."""
    app_name: str = "AURA-Traffic: CCTV Safety Analyzer"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]
    model_name: str = "YOLO11m + ByteTrack + Temporal FSM"
    model_weights: str = "models/yolo11m.pt"
    config_file: str = "configs/zones.json"
    videos_dir: str = "data/videos"
    output_dir: str = "data/output"
    events_dir: str = "data/output/events"
    evidence_cards_dir: str = "data/output/evidence_cards"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        """Root directory of the project."""
        curr = Path(__file__).resolve().parent  # backend/
        for p in [curr.parent, curr]:
            if (p / "data").exists() or (p / "configs").exists():
                return p
        return curr.parent

    def resolve(self, relative_path: str) -> Path:
        """Resolve a relative project path against monorepo root."""
        p = Path(relative_path)
        return p if p.is_absolute() else self.project_root / p


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

