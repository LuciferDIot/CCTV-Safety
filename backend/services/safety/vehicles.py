"""Vehicle taxonomy refinement rules (3-wheel tuk-tuk, bike, ped, car).

COCO object detector models classify road users into standard categories:
- Class 0: Person (Pedestrian)
- Class 1: Bicycle
- Class 2: Car
- Class 3: Motorcycle
- Class 5: Bus
- Class 7: Truck

Standard COCO models frequently misclassify 3-wheel auto-rickshaws (tuk-tuks)
as cars or small trucks. We use spatial bounding box dimensions on the 4K CCTV
camera perspective to isolate tuk-tuks from standard passenger cars and trucks.
"""
import numpy as np
from services.safety.geometry import get_box_geometry


def classify_vehicle_type(class_id: int, bbox: np.ndarray) -> str:
    """Refine standard COCO object categories into fine-grained roadway vehicle types."""
    box_width, box_height, area, aspect_ratio = get_box_geometry(bbox)

    # Class 0: Pedestrian
    if class_id == 0:
        return "Ped"

    # Class 1 (Bicycle) and Class 3 (Motorcycle): Two-wheelers
    if class_id in [1, 3]:
        return "Bike"

    # Class 2 (Car) and Class 7 (Truck): Motor vehicles requiring 3-wheeler disambiguation
    if class_id in [2, 7]:
        # Tuk-tuks (auto-rickshaws) have characteristic compact dimensions on 4K perspective:
        # - Width: 120px to 340px (narrower than full-size passenger cars)
        # - Height: 160px to 460px (upright cabin structure)
        # - Area: under 120,000 pixels (smaller ground footprint)
        # - Aspect ratio (H/W): 0.75 to 1.70 (boxy, upright silhouette)
        is_tuk_tuk = (
            120 <= box_width <= 340
            and 160 <= box_height <= 460
            and area < 120000
            and 0.75 <= aspect_ratio <= 1.70
        )
        if is_tuk_tuk:
            return "3-Wheel"
        return "Car" if class_id == 2 else "Truck"

    # Class 5: Large transit bus
    if class_id == 5:
        return "Bus"

    # Fallback for unrecognized classes
    return "Veh"
