"""Adversarial stress tests for fusion.py: rider-bike multimodal fusion and pedestrian rules."""
import numpy as np
import supervision as sv
from services.safety.fusion import resolve_riders_and_pedestrians


class MockZone:
    def __init__(self, polygon):
        self.polygon = np.array(polygon, dtype=float)


def test_fusion_empty_detections():
    """Test resolve_riders_and_pedestrians on empty supervision detections."""
    empty_dets = sv.Detections(xyxy=np.zeros((0, 4)), class_id=np.array([], dtype=int))
    res = resolve_riders_and_pedestrians(empty_dets, [], [])
    assert len(res) == 0


def test_fusion_rider_bike_boundary_matching():
    """Test exact boundary conditions for horizontal offset and vertical stacking."""
    # Bike at [100, 200, 150, 300]: width 50, center 125, top 200, bottom 300.
    # Max horizontal offset allowed is max(75.0, 0.75 * 50) = 75.0.
    # Case A: horizontal offset exactly 75.0 -> center = 200 -> [180, 120, 220, 220], feet=220 >= 150
    bike_box = [100.0, 200.0, 150.0, 300.0]
    rider_aligned = [180.0, 120.0, 220.0, 220.0]
    dets_a = sv.Detections(xyxy=np.array([bike_box, rider_aligned]), class_id=np.array([3, 0]))
    res_a = resolve_riders_and_pedestrians(dets_a, [], [])
    assert len(res_a) == 1 and res_a.class_id[0] == 3

    # Case B: horizontal offset 76.0 -> center = 201 -> [181, 120, 221, 220], should NOT merge
    rider_misaligned = [181.0, 120.0, 221.0, 220.0]
    dets_b = sv.Detections(xyxy=np.array([bike_box, rider_misaligned]), class_id=np.array([3, 0]))
    res_b = resolve_riders_and_pedestrians(dets_b, [], [])
    assert len(res_b) == 2

    # Case C: vertical overlap boundary (person bottom >= bike top - 50.0 = 150.0)
    rider_too_high = [105.0, 40.0, 145.0, 149.0]  # bottom 149 < 150
    dets_c = sv.Detections(xyxy=np.array([bike_box, rider_too_high]), class_id=np.array([3, 0]))
    res_c = resolve_riders_and_pedestrians(dets_c, [], [])
    assert len(res_c) == 2


def test_fusion_multiple_riders_single_bike():
    """Test multiple riders merged into one motorcycle with bounding box expansion."""
    bike = [100.0, 200.0, 160.0, 300.0]
    rider1 = [105.0, 100.0, 135.0, 210.0]
    rider2 = [125.0, 90.0, 155.0, 215.0]
    dets = sv.Detections(xyxy=np.array([bike, rider1, rider2]), class_id=np.array([3, 0, 0]))
    res = resolve_riders_and_pedestrians(dets, [], [])
    assert len(res) == 1 and res.class_id[0] == 3
    # Merged box must encompass rider1 and rider2
    assert res.xyxy[0][1] == 90.0 and res.xyxy[0][3] == 300.0


def test_fusion_aspect_ratio_and_speed_disambiguation():
    """Test pedestrian aspect ratio reclassification in traffic lanes and crosswalk protection."""
    lane = MockZone([[0, 0], [1000, 0], [1000, 1000], [0, 1000]])
    cw = MockZone([[400, 400], [600, 400], [600, 600], [400, 600]])

    # Squat ped (h=80, w=100, ratio=0.8 < 1.80) in lane with no history -> reclassified to class 3
    dets1 = sv.Detections(xyxy=np.array([[200.0, 200.0, 300.0, 280.0]]), class_id=np.array([0]))
    res1 = resolve_riders_and_pedestrians(dets1, [lane], [])
    assert res1.class_id[0] == 3

    # Squat ped in lane with walking history (speed 2.0 <= 4.0) -> preserved as ped class 0
    dets2 = sv.Detections(xyxy=np.array([[200.0, 200.0, 300.0, 280.0]]), class_id=np.array([0]))
    dets2.tracker_id = np.array([5])
    hist_walk = {5: [(200, 200), (202, 200), (204, 200)]}
    res2 = resolve_riders_and_pedestrians(dets2, [lane], [], track_history=hist_walk)
    assert res2.class_id[0] == 0

    # Squat ped in crosswalk -> protected regardless of speed
    dets3 = sv.Detections(xyxy=np.array([[450.0, 450.0, 550.0, 530.0]]), class_id=np.array([0]))
    dets3.tracker_id = np.array([6])
    hist_fast = {6: [(450, 450), (460, 450), (470, 450)]}
    res3 = resolve_riders_and_pedestrians(dets3, [lane], [cw], track_history=hist_fast)
    assert res3.class_id[0] == 0

    # Tall ped (h=150, w=50, ratio=3.0 >= 1.80) in lane -> preserved as class 0
    dets4 = sv.Detections(xyxy=np.array([[200.0, 200.0, 250.0, 350.0]]), class_id=np.array([0]))
    dets4.tracker_id = np.array([7])
    res4 = resolve_riders_and_pedestrians(dets4, [lane], [], track_history=hist_fast)
    assert res4.class_id[0] == 0
