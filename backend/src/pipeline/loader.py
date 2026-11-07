"""YOLO model resolution and initialization helper."""
from pathlib import Path
from typing import Optional
from ultralytics import YOLO
import torch


def load_detection_model(
    model_path: Optional[Path], base_dir: Path, device: str
) -> YOLO:
    """Resolve and load YOLO weights, downloading fallback if required."""
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
        clean_name = str(model_path).replace("yolov11", "yolo11")
        p_name = Path(clean_name).name
        target = models_dir / p_name
        model_path = target if target.exists() else _download_weights(p_name, models_dir)

    model = YOLO(str(model_path))
    model.to(device)
    return model


def _download_weights(name: str, models_dir: Path) -> Path:
    print(f"Downloading {name} to {models_dir}...")
    _ = YOLO(name)
    cwd_file = Path.cwd() / name
    target = models_dir / name
    if cwd_file.exists() and not target.exists():
        import shutil
        shutil.move(str(cwd_file), str(target))
    return target if target.exists() else cwd_file
