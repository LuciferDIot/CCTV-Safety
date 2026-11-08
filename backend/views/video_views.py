"""Views (DTOs) for video catalog and file upload contracts."""
from typing import Optional
from pydantic import BaseModel


class VideoMetadata(BaseModel):
    name: str
    fps: float
    total_frames: int
    duration_seconds: float
    width: int
    height: int
    size_mb: float
    stream_url: str


class VideoUploadResponse(BaseModel):
    message: str
    filename: str
    size_mb: float
    metadata: Optional[VideoMetadata] = None

