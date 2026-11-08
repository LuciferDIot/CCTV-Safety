"""H.264 video remuxing helper using system or bundled imageio ffmpeg."""
import shutil, subprocess
from pathlib import Path
from typing import Optional


def remux_h264(src: Optional[Path], dst: Path) -> None:
    if not src or not src.exists(): return
    if src.stat().st_size == 0:
        try: shutil.copyfile(str(src), str(dst)); src.unlink(missing_ok=True)
        except OSError: pass
        return
    try:
        ff = shutil.which("ffmpeg") or getattr(__import__("imageio_ffmpeg", fromlist=["get_ffmpeg_exe"]), "get_ffmpeg_exe", lambda: None)()
        if ff:
            rmx = dst.with_suffix(".remux.mp4")
            cmd = [str(ff), "-y", "-i", str(src.resolve()), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-loglevel", "error", str(rmx.resolve())]
            res = subprocess.run(cmd, capture_output=True, timeout=180)
            if res.returncode == 0 and rmx.exists() and rmx.stat().st_size > 1000:
                try: rmx.replace(dst)
                except OSError: shutil.copyfile(str(rmx), str(dst)); rmx.unlink(missing_ok=True)
                src.unlink(missing_ok=True)
                return
    except Exception: pass
    try:
        if src.exists():
            try: src.replace(dst)
            except OSError: shutil.copyfile(str(src), str(dst)); src.unlink(missing_ok=True)
    except OSError: pass

