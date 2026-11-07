"""Video storage catalog, metadata probing, and partial byte-range streaming."""
import os
from pathlib import Path
from typing import List, Tuple, Generator, Optional
import cv2
from fastapi import HTTPException
from app.config import Settings
from app.schemas.video import VideoMetadata


class VideoService:
    """Manages CCTV video assets and streaming."""

    def __init__(self, settings: Settings):
        self.videos_dir = settings.resolve(settings.videos_dir)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = settings.resolve(settings.output_dir)

    def list_videos(self) -> List[VideoMetadata]:
        videos = []
        for path in sorted(list(self.videos_dir.glob("*.mp4")) + list(self.output_dir.glob("*.mp4"))):
            meta = self.probe_video(path)
            if meta:
                videos.append(meta)
        return videos

    def probe_video(self, path: Path) -> Optional[VideoMetadata]:
        if not path.exists():
            return None
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        size_mb = round(path.stat().st_size / (1024 * 1024), 2)
        dur = round(total / fps, 2) if fps > 0 else 0.0
        return VideoMetadata(
            name=path.name, fps=round(fps, 2), total_frames=total,
            duration_seconds=dur, width=w, height=h, size_mb=size_mb,
            stream_url=f"/api/videos/{path.name}/stream"
        )

    def get_video_path(self, name: str) -> Path:
        cand1 = self.videos_dir / name
        cand2 = self.output_dir / name
        if cand1.exists():
            return cand1
        if cand2.exists():
            return cand2
        raise HTTPException(status_code=404, detail=f"Video '{name}' not found")

    @staticmethod
    def parse_byte_range(range_header: Optional[str], file_size: int) -> Tuple[int, int]:
        if not range_header or not range_header.startswith("bytes="):
            return 0, file_size - 1
        parts = range_header.replace("bytes=", "").split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        return start, min(end, file_size - 1)

    @staticmethod
    def stream_file_chunk(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(remaining, chunk_size))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

