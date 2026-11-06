"""Vehicle type refinement: separates 3-wheelers (tuk-tuks), bikes, peds, and cars."""
import numpy as np
from src.core.anchors import get_box_geometry


def classify_vehicle_type(class_id: int, bbox: np.ndarray) -> str:
    """
    Refines YOLO COCO classes into distinct traffic vehicle types:
    - Ped (0: Person on foot)
    - Bike (1: Bicycle, 3: Motorcycle/Scooter)
    - 3-Wheel (Auto-rickshaws / Tuk-tuks)
    - Car (2: Standard passenger cars / SUVs)
    - Bus (5: Transit buses)
    - Truck (7: Commercial trucks)
    """
    w, h, area, aspect_ratio = get_box_geometry(bbox)

    if class_id == 0:
        return "Ped"
    if class_id in [1, 3]:
        return "Bike"
    if class_id in [2, 7]:
        # In 4K CCTV (3840x2160), Auto-rickshaws (Tuk-tuks) are compact, boxy:
        # Width: 120-340px, Height: 160-460px, Area < 120,000 px^2, Aspect: 0.75-1.70
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

