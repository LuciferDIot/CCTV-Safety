"""Video catalog, file upload, and partial-content byte streaming endpoints."""
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Header, HTTPException
from starlette.responses import StreamingResponse
from app.dependencies import get_video_service
from app.services.video_service import VideoService
from app.schemas.video import VideoMetadata, VideoUploadResponse

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=List[VideoMetadata])
def list_videos(svc: VideoService = Depends(get_video_service)):
    return svc.list_videos()


@router.get("/{name}/metadata", response_model=VideoMetadata)
def get_video_metadata(name: str, svc: VideoService = Depends(get_video_service)):
    path = svc.get_video_path(name)
    meta = svc.probe_video(path)
    if not meta:
        raise HTTPException(status_code=500, detail="Failed to probe video file")
    return meta


@router.post("/upload", response_model=VideoUploadResponse)
def upload_video(file: UploadFile = File(...), svc: VideoService = Depends(get_video_service)):
    if not file.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(status_code=400, detail="Only MP4, AVI, or MOV video files supported")
    dest = svc.videos_dir / file.filename
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    meta = svc.probe_video(dest)
    size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
    return VideoUploadResponse(message="Video uploaded successfully", filename=file.filename, size_mb=size_mb, metadata=meta)


@router.get("/{name}/stream")
def stream_video(name: str, range: str = Header(None), svc: VideoService = Depends(get_video_service)):
    path = svc.get_video_path(name)
    total_size = path.stat().st_size
    start, end = svc.parse_byte_range(range, total_size)
    content_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{total_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(svc.stream_file_chunk(path, start, end), status_code=206, headers=headers)

