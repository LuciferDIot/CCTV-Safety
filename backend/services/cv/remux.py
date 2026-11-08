"""H.264 video remuxing helper using system or bundled imageio ffmpeg."""
import shutil, subprocess
from pathlib import Path
from typing import Optional


def remux_h264(src: Optional[Path], dst: Path) -> None:
    if not src or not src.exists(): return
    if src.stat().st_size == 0:
        try:
            if src.resolve() != dst.resolve():
                shutil.copyfile(str(src), str(dst)); src.unlink(missing_ok=True)
        except OSError: pass
        return
    try:
        ff = shutil.which("ffmpeg") or getattr(__import__("imageio_ffmpeg", fromlist=["get_ffmpeg_exe"]), "get_ffmpeg_exe", lambda: None)()
        if ff:
            rmx = dst.with_suffix(".remux.mp4")
            cmd = [str(ff), "-y", "-i", str(src.resolve()), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-loglevel", "error", str(rmx.resolve())]
            res = subprocess.run(cmd, capture_output=True, timeout=180)
            if res.returncode == 0 and rmx.exists() and rmx.stat().st_size > 1000:
                is_same = (src.resolve() == dst.resolve())
                try: rmx.replace(dst)
                except OSError: shutil.copyfile(str(rmx), str(dst)); rmx.unlink(missing_ok=True)
                if not is_same: src.unlink(missing_ok=True)
                return
    except Exception: pass
    try:
        if src.exists() and src.resolve() != dst.resolve():
            try: src.replace(dst)
            except OSError: shutil.copyfile(str(src), str(dst)); src.unlink(missing_ok=True)
    except OSError: pass


def ensure_h264(video_path: Path) -> Path:
    if not video_path.exists() or video_path.stat().st_size < 1000: return video_path
    if video_path.suffix.lower() in (".avi", ".mov"):
        mp4_dst = video_path.with_suffix(".mp4")
        remux_h264(video_path, mp4_dst)
        return mp4_dst if mp4_dst.exists() else video_path
    if video_path.suffix.lower() == ".mp4":
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).lower()
        cap.release()
        if fourcc_str in ("fmp4", "mp4v", "xvid", "divx", "none", "\x00\x00\x00\x00"):
            remux_h264(video_path, video_path)
    return video_path


