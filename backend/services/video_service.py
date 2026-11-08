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
        self.videos_dir = settings.resolve(settings.videos_dir)
        self.output_dir = settings.resolve(settings.output_dir)
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_videos(self) -> List[VideoMetadata]:
        all_files = []
        for d in [self.videos_dir, self.output_dir]:
            if d.exists():
                all_files.extend(list(d.glob("*.mp4")) + list(d.glob("*.avi")) + list(d.glob("*.mov")))
        seen, metas = set(), []
        for p in all_files:
            if p.name not in seen and not p.name.endswith(".tmp.mp4"):
                seen.add(p.name)
                m = self.probe_video(p)
                if m: metas.append(m)
        return metas

    def probe_video(self, video_path: Path) -> Optional[VideoMetadata]:
        if not video_path.exists(): return None
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened(): return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
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
        for p in [self.videos_dir / safe_name, self.output_dir / safe_name]:
            if p.is_file(): return p
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
