"""Health check and accelerator diagnostic controller."""
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends
import torch
from config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["system"])
START_TIME = time.time()


@router.get("", response_model=Dict[str, Any])
def health_check(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    weights = settings.resolve(settings.model_weights)
    return {
        "status": "healthy",
        "app": settings.app_name,
        "device": dev,
        "model_loaded": weights.exists(),
        "model_path": str(weights),
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@router.get("/system-info", response_model=Dict[str, Any])
def system_info(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "root_dir": str(settings.project_root),
    }

