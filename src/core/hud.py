"""HUD on-screen render progress bar."""
import cv2
import numpy as np


def draw_render_progress_bar(
    frame: np.ndarray,
    current_frame: int,
    total_frames: int,
    bar_height: int = 24,
    margin_bottom: int = 25,
) -> np.ndarray:
    """Render an on-screen semi-transparent HUD percentage progress bar."""
    if total_frames <= 0:
        return frame

    h, w = frame.shape[:2]
    progress = np.clip(current_frame / float(total_frames), 0.0, 1.0)
    pct = progress * 100.0

    y_start = h - margin_bottom - bar_height - 35
    y_end = h - margin_bottom + 5
    x_start, x_end = 60, w - 60

    overlay = frame.copy()
    cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    bx1, by1 = x_start + 18, y_start + 34
    bx2, by2 = x_end - 18, by1 + bar_height
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (70, 70, 70), 2)

    fill_w = int((bx2 - bx1) * progress)
    if fill_w > 0:
        cv2.rectangle(frame, (bx1, by1), (bx1 + fill_w, by2), (255, 229, 0), -1)

    label = f"Safety Pipeline: Frame {current_frame:04d}/{total_frames:04d} ({pct:5.1f}%)"
    cv2.putText(
        frame, label, (bx1, y_start + 25),
        cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA
    )
    return frame

