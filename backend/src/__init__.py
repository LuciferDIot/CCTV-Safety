"""CCTV Intersection Safety & Motorcycle Violation Analysis Package."""
from src.config.zones import load_intersection_config, IntersectionConfig
from src.pipeline.pipeline import IntersectionSafetyPipeline

__version__ = "1.0.0"

__all__ = [
    "IntersectionSafetyPipeline",
    "load_intersection_config",
    "IntersectionConfig",
]
