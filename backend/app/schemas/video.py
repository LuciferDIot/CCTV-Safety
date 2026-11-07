"""Video catalog and metadata schemas."""
from typing import Optional
from pydantic import BaseModel


class VideoMetadata(BaseModel):
    """Metadata for an input or annotated CCTV video recording."""
    name: str
    fps: float
    total_frames: int
    duration_seconds: float
    width: int
    height: int
    size_mb: float
    stream_url: str


class VideoUploadResponse(BaseModel):
    """Response payload following video file upload."""
    message: str
    filename: str
    size_mb: float
    metadata: Optional[VideoMetadata] = None
