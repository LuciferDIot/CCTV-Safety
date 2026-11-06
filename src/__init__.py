"""
CCTV Intersection Safety & Motorcycle Violation Analysis Package
Modular engine for real-time video analytics, tracking, safety violation detection, and event verification.
"""
from src.config import load_intersection_config, IntersectionConfig
from src.pipeline import IntersectionSafetyPipeline

__version__ = "1.0.0"

__all__ = [
    "IntersectionSafetyPipeline",
    "load_intersection_config",
    "IntersectionConfig",
]
