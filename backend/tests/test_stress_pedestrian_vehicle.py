"""Empirical stress tests for pedestrian safety segregation and vehicle taxonomy."""
import numpy as np
import supervision as sv
from services.safety.pedestrian import PedestrianSafetyChecker
from services.safety.vehicles import classify_vehicle_type


def test_pedestrian_safety_segregation_and_boundaries():
    lane_poly = np.array([[0, 0], [400, 0], [400, 600], [0, 600]])
    cw_poly = np.array([[0, 200], [400, 200], [400, 300], [0, 300]])
    lane_zone = sv.PolygonZone(polygon=lane_poly)
    cw_zone = sv.PolygonZone(polygon=cw_poly)
    checker = PedestrianSafetyChecker()

    # 0: In crosswalk & lane -> SAFE
    # 1: In lane outside crosswalk -> HAZARD (jaywalker)
    # 2: Outside both -> Neither
    # 3: Vehicle in lane (class_id = 2) -> ignored
    xyxy = np.array([
        [100, 220, 120, 260],
        [100, 50, 120, 90],
        [500, 500, 520, 540],
        [100, 50, 180, 150],
    ])
    dets = sv.Detections(xyxy=xyxy, class_id=np.array([0, 0, 0, 2]))

    hazard, safe = checker.check_safety(dets, [lane_zone], [cw_zone], track_history={})
    assert len(safe) == 1 and np.array_equal(safe.xyxy[0], [100, 220, 120, 260])
    assert len(hazard) == 1 and np.array_equal(hazard.xyxy[0], [100, 50, 120, 90])

    # Empty detections and empty zones
    empty_h, empty_s = checker.check_safety(sv.Detections.empty(), [lane_zone], [cw_zone], None)
    assert len(empty_h) == 0 and len(empty_s) == 0
    no_zone_h, no_zone_s = checker.check_safety(dets, [], [], None)
    assert len(no_zone_h) == 0 and len(no_zone_s) == 0


def test_vehicle_taxonomy_and_tuktuk_boundaries():
    assert classify_vehicle_type(0, np.array([10, 10, 50, 100])) == "Ped"
    assert classify_vehicle_type(1, np.array([10, 10, 50, 100])) == "Bike"
    assert classify_vehicle_type(3, np.array([10, 10, 50, 100])) == "Bike"
    assert classify_vehicle_type(5, np.array([10, 10, 500, 300])) == "Bus"
    assert classify_vehicle_type(9, np.array([10, 10, 50, 100])) == "Veh"

    # Compliant 3-wheel: w=200, h=250, area=50000, AR=1.25
    assert classify_vehicle_type(2, np.array([0, 0, 200, 250])) == "3-Wheel"
    assert classify_vehicle_type(7, np.array([0, 0, 200, 250])) == "3-Wheel"

    # Width boundaries
    assert classify_vehicle_type(2, np.array([0, 0, 119, 200])) == "Car"
    assert classify_vehicle_type(2, np.array([0, 0, 120, 200])) == "3-Wheel"
    assert classify_vehicle_type(2, np.array([0, 0, 340, 340])) == "3-Wheel"
    assert classify_vehicle_type(2, np.array([0, 0, 341, 340])) == "Car"

    # Height boundaries
    assert classify_vehicle_type(2, np.array([0, 0, 200, 159])) == "Car"
    assert classify_vehicle_type(2, np.array([0, 0, 200, 160])) == "3-Wheel"
    assert classify_vehicle_type(2, np.array([0, 0, 260, 440])) == "3-Wheel"  # area=114.4k, AR=1.69
    assert classify_vehicle_type(2, np.array([0, 0, 300, 461])) == "Car"

    # Aspect ratio & Area boundaries
    assert classify_vehicle_type(2, np.array([0, 0, 320, 230])) == "Car"  # AR = 0.718 < 0.75
    assert classify_vehicle_type(2, np.array([0, 0, 150, 270])) == "Car"  # AR = 1.80 > 1.70


def test_vehicle_extreme_bbox_dimensions_and_stability():
    # Degenerate zero-area bbox (w=1, h=1 clamp, no ZeroDivisionError)
    assert classify_vehicle_type(2, np.array([100, 100, 100, 100])) == "Car"
    # Inverted bounding box
    assert classify_vehicle_type(7, np.array([200, 300, 100, 100])) == "Truck"
    # Gigantic bounding box (area >> 120k)
    assert classify_vehicle_type(2, np.array([0, 0, 5000, 4000])) == "Car"
    # Needle flat bbox (AR -> 0)
    assert classify_vehicle_type(2, np.array([0, 0, 1000, 1])) == "Car"
    # Needle tall bbox (AR -> 1000)
    assert classify_vehicle_type(7, np.array([0, 0, 1, 1000])) == "Truck"
    # Negative coordinate bboxes
    assert classify_vehicle_type(2, np.array([-300, -250, -100, 0])) == "3-Wheel"
