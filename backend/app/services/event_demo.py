"""Pre-populated rich demo scenarios matching UI specification."""
from typing import List, Dict, Any


def get_demo_scenarios() -> List[Dict[str, Any]]:
    return [
        {
            "event_id": "EV-101", "status": "CONFIRMED", "event_type": "WRONG_WAY",
            "track_ids": [12, 19], "stitched": True, "start_frame": 426, "end_frame": 534,
            "time_start": 14.2, "time_end": 17.8, "duration_sec": 3.6, "confidence": 0.94,
            "metrics": {"counter_flow_frames": 42, "angle_deg": 164.2, "opposing_ratio": 0.92},
            "posture_metrics": {"posture": "mounted", "speed_px_per_frame": 8.4},
            "explanation": "Vehicle traveled against permitted lane direction vector continuously for 42 frames."
        },
        {
            "event_id": "EV-102", "status": "CONFIRMED", "event_type": "CROSSWALK_RIDING",
            "track_ids": [27], "stitched": False, "start_frame": 870, "end_frame": 963,
            "time_start": 29.0, "time_end": 32.1, "duration_sec": 3.1, "confidence": 0.91,
            "metrics": {"traversal_pct": 0.68, "crosswalk_id": "cw_01", "dwell_frames": 93},
            "posture_metrics": {"posture": "mounted", "vertical_clearance": 0.38, "speed_px_per_frame": 7.1},
            "explanation": "Mounted rider traversed 68% of pedestrian crosswalk polygon without dismounting."
        },
        {
            "event_id": "EV-103", "status": "EXEMPT", "event_type": "WALKING_MOTORCYCLE",
            "track_ids": [34], "stitched": False, "start_frame": 1365, "end_frame": 1530,
            "time_start": 45.5, "time_end": 51.0, "duration_sec": 5.5, "confidence": 0.88,
            "metrics": {"lateral_offset_px": 54.0, "speed_px_per_frame": 1.6},
            "posture_metrics": {"posture": "dismounted", "lateral_offset_px": 54.0, "speed_px_per_frame": 1.6},
            "explanation": "Dismounted person walking alongside motorcycle detected (speed < 2 px/frame, lateral offset)."
        },
        {
            "event_id": "EV-104", "status": "INSUFFICIENT_EVIDENCE", "event_type": "WRONG_WAY",
            "track_ids": [41], "stitched": False, "start_frame": 1890, "end_frame": 1923,
            "time_start": 63.0, "time_end": 64.1, "duration_sec": 1.1, "confidence": 0.41,
            "metrics": {"occlusion_pct": 0.70, "track_frames": 6},
            "posture_metrics": {"posture": "unknown", "speed_px_per_frame": 5.2},
            "explanation": "Target 70% occluded behind bus with only 6 tracking frames observed; flagged for review."
        },
        {
            "event_id": "EV-105", "status": "IGNORED", "event_type": "LEGITIMATE_TURN",
            "track_ids": [52], "stitched": False, "start_frame": 2352, "end_frame": 2430,
            "time_start": 78.4, "time_end": 81.0, "duration_sec": 2.6, "confidence": 0.82,
            "metrics": {"turn_angle_deg": 88.0, "curvature": 0.045},
            "posture_metrics": {"posture": "mounted", "speed_px_per_frame": 6.8},
            "explanation": "Vehicle executed legal cross-lane turn arc without sustained counter-flow."
        }
    ]

