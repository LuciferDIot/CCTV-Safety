"""
Explanation Engine: Generates Supporting Video Evidence Frames & Trajectory Visualizations
Produces high-resolution explanation cards for each detected safety event.
"""
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import cv2
import numpy as np

class ExplanationEngine:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_event_evidence(
        self,
        event: Any,
        peak_frame: np.ndarray,
        trajectory: List[Tuple[float, float]],
        bbox: Optional[np.ndarray] = None,
        crop_image: Optional[np.ndarray] = None,
        rationale: str = ""
    ) -> Path:
        """
        Creates a comprehensive multi-panel visual audit card for a reported event.
        Includes peak frame with trajectory breadcrumbs, crop of the vehicle, and decision metrics.
        """
        h, w = peak_frame.shape[:2]
        canvas = peak_frame.copy()

        # 1. Draw Trajectory Breadcrumbs
        if len(trajectory) >= 2:
            pts = np.array(trajectory, dtype=np.int32).reshape((-1, 1, 2))
            for i in range(len(pts) - 1):
                pt1 = tuple(pts[i][0])
                pt2 = tuple(pts[i + 1][0])
                alpha = (i + 1) / float(len(pts))
                color = self._get_event_bgr_color(event.event_type)
                thickness = max(2, int(4 * alpha))
                cv2.line(canvas, pt1, pt2, color, thickness, cv2.LINE_AA)
                cv2.circle(canvas, pt2, max(3, int(6 * alpha)), color, -1)

            cv2.circle(canvas, tuple(pts[0][0]), 8, (0, 255, 0), -1)
            cv2.putText(canvas, "START", (pts[0][0][0] + 12, pts[0][0][1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 2. Draw Target Bounding Box
        if bbox is not None:
            x1, y1, x2, y2 = map(int, bbox)
            box_color = self._get_event_bgr_color(event.event_type)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), box_color, 4)
            badge_text = f"#{int(event.track_id)} {event.event_type}"
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
            cv2.rectangle(canvas, (x1, max(0, y1 - th - 10)), (x1 + tw + 10, y1), box_color, -1)
            cv2.putText(canvas, badge_text, (x1 + 5, max(th + 5, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

        # 3. Add High-Level HUD Explanation Banner
        banner_h = 130
        banner = np.zeros((banner_h, w, 3), dtype=np.uint8)
        banner[:] = (24, 24, 24)

        title = f"EVENT EVIDENCE REPORT: {event.id} [{event.event_type}] - TRACK #{int(event.track_id)}"
        timing = f"Time: {float(event.start_ts):.2f}s - {float(event.end_ts):.2f}s (Duration: {float(event.end_ts - event.start_ts):.2f}s) | Conf: {float(event.confidence):.2f}"
        metrics = f"Zone: {getattr(event, 'lane_or_zone', 'N/A')} | Rationale: {rationale or getattr(event, 'details', 'N/A')}"

        cv2.putText(banner, title, (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.95, self._get_event_bgr_color(event.event_type), 2, cv2.LINE_AA)
        cv2.putText(banner, timing, (25, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (220, 220, 220), 2, cv2.LINE_AA)
        cv2.putText(banner, metrics, (25, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 240, 255), 2, cv2.LINE_AA)

        # Compose full evidence card
        full_card = np.vstack([banner, canvas])

        # Save to disk
        filename = f"{event.id}_{event.event_type}_tid{int(event.track_id)}.jpg"
        out_path = self.output_dir / filename
        cv2.imwrite(str(out_path), full_card)
        return out_path

    def _get_event_bgr_color(self, event_type: str) -> Tuple[int, int, int]:
        if event_type == "WRONG_WAY":
            return (0, 0, 255)       # Red
        elif event_type == "CROSSWALK_RIDING":
            return (0, 140, 255)     # Orange
        elif event_type == "EXEMPT_WALKING":
            return (255, 220, 0)     # Cyan
        elif event_type == "INSUFFICIENT_EVIDENCE":
            return (0, 215, 255)     # Amber/Yellow
        return (0, 255, 0)           # Green
