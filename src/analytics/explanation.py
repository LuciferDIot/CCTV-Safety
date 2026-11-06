"""Explanation Engine: Generates Supporting Video Evidence Frames."""
from pathlib import Path
from typing import List, Tuple, Optional, Any
import cv2
import numpy as np


class ExplanationEngine:
    """Produces high-resolution explanation cards with breadcrumb trails."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _draw_breadcrumbs(
        self, canvas: np.ndarray, trajectory: List[Tuple[float, float]], color: Tuple[int, int, int]
    ) -> None:
        if len(trajectory) < 2:
            return
        pts = np.array(trajectory, dtype=np.int32).reshape((-1, 1, 2))
        for i in range(len(pts) - 1):
            p1, p2 = tuple(pts[i][0]), tuple(pts[i + 1][0])
            alpha = (i + 1) / float(len(pts))
            cv2.line(canvas, p1, p2, color, max(2, int(4 * alpha)), cv2.LINE_AA)
            cv2.circle(canvas, p2, max(3, int(6 * alpha)), color, -1)
        cv2.circle(canvas, tuple(pts[0][0]), 8, (0, 255, 0), -1)
        cv2.putText(canvas, "START", (pts[0][0][0] + 12, pts[0][0][1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    def _build_banner(self, w: int, event: Any, color: Tuple[int, int, int], rationale: str) -> np.ndarray:
        banner = np.zeros((130, w, 3), dtype=np.uint8)
        banner[:] = (24, 24, 24)
        t_title = f"EVENT EVIDENCE: {event.id} [{event.event_type}] - TRACK #{int(event.track_id)}"
        dur = float(event.end_ts - event.start_ts)
        t_time = f"Time: {float(event.start_ts):.2f}s - {float(event.end_ts):.2f}s ({dur:.2f}s) | Conf: {float(event.confidence):.2f}"
        t_met = f"Zone: {getattr(event, 'lane_or_zone', 'N/A')} | Info: {rationale or getattr(event, 'details', 'N/A')}"
        cv2.putText(banner, t_title, (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.90, color, 2, cv2.LINE_AA)
        cv2.putText(banner, t_time, (25, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (220, 220, 220), 2, cv2.LINE_AA)
        cv2.putText(banner, t_met, (25, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 240, 255), 2, cv2.LINE_AA)
        return banner

    def generate_event_evidence(
        self,
        event: Any,
        peak_frame: np.ndarray,
        trajectory: List[Tuple[float, float]],
        bbox: Optional[np.ndarray] = None,
        crop_image: Optional[np.ndarray] = None,
        rationale: str = ""
    ) -> Path:
        """Create a visual audit card for a reported safety event."""
        h, w = peak_frame.shape[:2]
        canvas = peak_frame.copy()
        color = self._get_event_bgr_color(event.event_type)

        self._draw_breadcrumbs(canvas, trajectory, color)
        if bbox is not None:
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 4)
            badge = f"#{int(event.track_id)} {event.event_type}"
            (tw, th), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
            cv2.rectangle(canvas, (x1, max(0, y1 - th - 10)), (x1 + tw + 10, y1), color, -1)
            cv2.putText(canvas, badge, (x1 + 5, max(th + 5, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

        banner = self._build_banner(w, event, color, rationale)
        full_card = np.vstack([banner, canvas])
        out_path = self.output_dir / f"{event.id}_{event.event_type}_tid{int(event.track_id)}.jpg"
        cv2.imwrite(str(out_path), full_card)
        return out_path

    def _get_event_bgr_color(self, event_type: str) -> Tuple[int, int, int]:
        colors = {
            "WRONG_WAY": (0, 0, 255),
            "CROSSWALK_RIDING": (0, 140, 255),
            "EXEMPT_WALKING": (255, 220, 0),
            "INSUFFICIENT_EVIDENCE": (0, 215, 255)
        }
        return colors.get(event_type, (0, 255, 0))
