"""Application service for video catalog, metadata probing, and chunked streaming."""
from pathlib import Path
from typing import List, Tuple, Generator, Optional
import cv2
from fastapi import HTTPException
from config import Settings
from views.video_views import VideoMetadata


class VideoService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.videos_dir, self.uploads_dir, self.output_dir = settings.resolve(settings.videos_dir), settings.resolve("data/uploads"), settings.resolve(settings.output_dir)
        for d in (self.videos_dir, self.uploads_dir, self.output_dir): d.mkdir(parents=True, exist_ok=True)

    def list_videos(self) -> List[VideoMetadata]:
        all_files = []
        for d in [self.uploads_dir, self.output_dir]:
            if d.exists():
                for p in d.iterdir():
                    if p.is_file() and p.suffix.lower() in (".mp4", ".avi", ".mov"):
                        all_files.append(p)
        seen, metas = set(), []
        for p in all_files:
            if p.name not in seen and not p.name.endswith(".tmp.mp4") and not p.name.endswith(".remux.mp4"):
                seen.add(p.name)
                m = self.probe_video(p)
                if m: metas.append(m)
        return metas

    def probe_video(self, video_path: Path) -> Optional[VideoMetadata]:
        if not video_path.exists() or video_path.stat().st_size < 1000: return None
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened(): return None
        raw_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = raw_fps if raw_fps > 0 else 30.0
        total_frames = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
        raw_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        width = raw_w if raw_w > 0 else 1920
        raw_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        height = raw_h if raw_h > 0 else 1080
        duration = round(total_frames / fps, 2) if fps > 0 else 0.0
        size_mb = round(video_path.stat().st_size / (1024 * 1024), 2)
        cap.release()
        return VideoMetadata(
            name=video_path.name, fps=fps, total_frames=total_frames,
            duration_seconds=duration, width=width, height=height,
            size_mb=size_mb, stream_url=f"/api/videos/{video_path.name}/stream"
        )

    def get_video_path(self, name: str) -> Path:
        safe_name = Path(name).name
        if safe_name in ("", ".", ".."):
            raise HTTPException(status_code=404, detail=f"Video '{name}' not found")
        for d in [self.uploads_dir, self.videos_dir, self.output_dir]:
            p = d / safe_name
            if p.is_file(): return p
        for d in [self.uploads_dir, self.videos_dir, self.output_dir]:
            if d.exists():
                m = next((f for f in d.iterdir() if f.is_file() and f.name.lower() == safe_name.lower()), None)
                if m: return m
        raise HTTPException(status_code=404, detail=f"Video '{name}' not found")

    def parse_byte_range(self, range_header: Optional[str], file_size: int) -> Tuple[int, int]:
        if not range_header or "=" not in range_header:
            return (0, file_size - 1)
        r_type, r_val = range_header.strip().split("=", 1)
        if r_type != "bytes":
            return (0, file_size - 1)
        parts = r_val.split("-")
        try:
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else min(start + 1024 * 1024 * 2 - 1, file_size - 1)
            if start < 0 or start >= file_size or end < start:
                raise HTTPException(status_code=416, detail="Range Not Satisfiable")
            return (start, min(end, file_size - 1))
        except (ValueError, IndexError):
            raise HTTPException(status_code=416, detail="Invalid Range Header")

    def stream_file_chunk(self, path: Path, start: int, end: int, chunk_size: int = 128 * 1024) -> Generator[bytes, None, None]:
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                n = min(remaining, chunk_size)
                data = f.read(n)
                if not data: break
                remaining -= len(data)
                yield data
