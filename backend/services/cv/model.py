"""YOLO object detection model loader and weight management.

Model Resolution Ladder:
1. High-Accuracy: `yolo11m.pt` (YOLOv11 medium) for fine-grained motorcycle/pedestrian detection.
2. Lightweight Fallback: `yolov8s.pt` (YOLOv8 small) for resource-constrained or CPU systems.
3. Hub Auto-Download: Fetches missing weights from Ultralytics official hub repository.

Name Normalization & Weight Relocation:
- Ultralytics naming: Uses `yolo11` rather than `yolov11` in official model hub identifiers.
- CWD interception: Ultralytics downloads weights to Path.cwd(); this module intercepts
  and moves downloaded files into `models/` for clean directory hygiene.
"""
import shutil
from pathlib import Path
from typing import Optional
from ultralytics import YOLO


def load_detection_model(model_path: Optional[Path], base_dir: Path, device: str) -> YOLO:
    """Loads and initializes YOLO model on target accelerator device (CUDA or CPU).

    Implements fallback resolution ladder:
    yolo11m.pt (preferred) -> yolov8s.pt (fallback) -> automatic hub download.
    """
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    if model_path is None:
        m11, m8 = models_dir / "yolo11m.pt", models_dir / "yolov8s.pt"
        if m11.exists():
            model_path = m11
        elif m8.exists():
            model_path = m8
        else:
            model_path = _download_weights("yolo11m.pt", models_dir)
    elif not Path(model_path).exists():
        # Normalize name: Ultralytics hub registers "yolo11" instead of "yolov11"
        clean_name = str(model_path).replace("yolov11", "yolo11")
        p_name = Path(clean_name).name
        target = models_dir / p_name
        model_path = target if target.exists() else _download_weights(p_name, models_dir)

    model = YOLO(str(model_path))
    model.to(device)
    return model


def _download_weights(name: str, models_dir: Path) -> Path:
    """Downloads weights from Ultralytics hub and relocates them to models_dir."""
    print(f"Downloading {name} to {models_dir}...")
    _ = YOLO(name)
    cwd_file, target = Path.cwd() / name, models_dir / name
    if cwd_file.exists() and not target.exists():
        shutil.move(str(cwd_file), str(target))
    return target if target.exists() else cwd_file
