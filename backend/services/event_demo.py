"""Pre-seeded demo safety event scenarios for testing and demonstration."""
from typing import List, Dict, Any


def get_demo_scenarios() -> List[Dict[str, Any]]:
    return [
        {
            "event_id": "EV-101",
            "status": "CONFIRMED",
            "event_type": "WRONG_WAY",
            "start_time": 4.12,
            "end_time": 6.85,
            "duration_seconds": 2.73,
            "tracking_id": 14,
            "confidence": 0.94,
            "displacement_vector": [0.08, -0.99],
            "alignment_dot_product": -0.92,
            "permitted_flow_vector": [0.0, 1.0],
            "posture_metrics": {"aspect_ratio": 1.48, "vertical_extent_px": 215.0, "posture": "mounted"},
            "natural_language_explanation": "Vehicle #14 travelled northbound against southbound permitted lane flow for 2.73 seconds.",
            "stitched": True,
        },
        {
            "event_id": "EV-102",
            "status": "CONFIRMED",
            "event_type": "CROSSWALK_RIDING",
            "start_time": 8.40,
            "end_time": 10.60,
            "duration_seconds": 2.20,
            "tracking_id": 18,
            "confidence": 0.91,
            "displacement_vector": [0.95, 0.22],
            "alignment_dot_product": 0.12,
            "permitted_flow_vector": [0.0, 1.0],
            "posture_metrics": {"aspect_ratio": 1.42, "vertical_extent_px": 204.0, "posture": "mounted"},
            "natural_language_explanation": "Vehicle #18 traversed crosswalk at 8.2 px/frame while mounted.",
            "stitched": False,
        },
        {
            "event_id": "EV-103",
            "status": "EXEMPT",
            "event_type": "WALKING_MOTORCYCLE",
            "start_time": 14.10,
            "end_time": 19.30,
            "duration_seconds": 5.20,
            "tracking_id": 22,
            "confidence": 0.88,
            "displacement_vector": [0.88, 0.35],
            "alignment_dot_product": 0.25,
            "permitted_flow_vector": [0.0, 1.0],
            "posture_metrics": {"aspect_ratio": 2.15, "vertical_extent_px": 340.0, "posture": "dismounted"},
            "natural_language_explanation": "Individual #22 walking dismounted beside motorcycle at pedestrian pace (2.1 px/frame).",
            "stitched": False,
        },
    ]

