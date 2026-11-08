"""Vehicle taxonomy refinement rules (3-wheel tuk-tuk, bike, ped, car)."""
import numpy as np
from services.safety.geometry import get_box_geometry


def classify_vehicle_type(class_id: int, bbox: np.ndarray) -> str:
    """Refine COCO object categories into fine-grained roadway vehicle types."""
    w, h, area, aspect_ratio = get_box_geometry(bbox)

    if class_id == 0:
        return "Ped"
    if class_id in [1, 3]:
        return "Bike"
    if class_id in [2, 7]:
        # 3-Wheeler (Tuk-tuk) aspect and dimension gating on 4K perspective
        is_tuk_tuk = (
            120 <= w <= 340
            and 160 <= h <= 460
            and area < 120000
            and 0.75 <= aspect_ratio <= 1.70
        )
        if is_tuk_tuk:
            return "3-Wheel"
        return "Car" if class_id == 2 else "Truck"
    if class_id == 5:
        return "Bus"
    return "Veh"

