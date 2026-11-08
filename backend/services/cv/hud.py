"""OpenCV on-screen HUD render progress bar.

Coordinate System:
OpenCV frames use a top-left origin (0, 0), where X increases rightward
and Y increases downward.

Color Convention:
OpenCV images use Blue-Green-Red (BGR) channel order rather than RGB.
For instance, the progress bar fill color (255, 229, 0) is vibrant electric
cyan/sky blue (Blue=255, Green=229, Red=0), not yellow.
"""
import cv2
import numpy as np

# Layout geometry offsets (pixels)
PANEL_MARGIN_X = 60         # Horizontal inset from frame left/right edges
PANEL_TOP_HEADROOM = 35     # Vertical headroom above progress bar for text banner
PANEL_BOTTOM_PADDING = 5    # Padding below progress bar
BAR_INSET_X = 18            # Horizontal inset of progress track within panel
BAR_OFFSET_Y = 34           # Vertical offset of progress bar below panel top
ELECTRIC_CYAN_BGR = (255, 229, 0)  # High-visibility cyan fill in BGR space


def draw_render_progress_bar(
    frame: np.ndarray, current_frame: int, total_frames: int,
    bar_height: int = 24, margin_bottom: int = 25
) -> np.ndarray:
    """Renders a semi-transparent on-screen HUD progress bar and status banner.

    Args:
        frame: OpenCV image array (BGR format).
        current_frame: Current processing frame index (1-based).
        total_frames: Total frames in video to process.
        bar_height: Height in pixels of progress track.
        margin_bottom: Bottom margin offset from frame boundary.
    """
    if total_frames <= 0:
        return frame

    h, w = frame.shape[:2]
    progress = np.clip(current_frame / float(total_frames), 0.0, 1.0)
    pct = progress * 100.0

    # Calculate panel bounding box in OpenCV coordinates (X right, Y down)
    y_start = h - margin_bottom - bar_height - PANEL_TOP_HEADROOM
    y_end = h - margin_bottom + PANEL_BOTTOM_PADDING
    x_start, x_end = PANEL_MARGIN_X, w - PANEL_MARGIN_X

    # Render translucent dark slate backdrop container
    overlay = frame.copy()
    cv2.rectangle(overlay, (x_start, y_start), (x_end, y_end), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    # Render progress track container outline
    bx1, by1 = x_start + BAR_INSET_X, y_start + BAR_OFFSET_Y
    bx2, by2 = x_end - BAR_INSET_X, by1 + bar_height
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (70, 70, 70), 2)

    # Render proportional progress fill using electric cyan (BGR)
    fill_w = int((bx2 - bx1) * progress)
    if fill_w > 0:
        cv2.rectangle(frame, (bx1, by1), (bx1 + fill_w, by2), ELECTRIC_CYAN_BGR, -1)

    # Render status label with frame counter and percentage
    label = f"Safety Pipeline: Frame {current_frame:04d}/{total_frames:04d} ({pct:5.1f}%)"
    cv2.putText(frame, label, (bx1, y_start + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA)
    return frame
