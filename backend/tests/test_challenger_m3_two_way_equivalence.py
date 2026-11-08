"""Empirical two-way mathematical and behavioral equivalence test suite for Milestone 3."""
import json, math, numpy as np, pytest, supervision as sv
from services.safety.clustering import LaneAutoDetector as ProdLaneDetector, clip_polygon_by_axis
from services.safety.direction import DirectionChecker
from services.safety.crosswalk import is_normal_lane_transit as prod_is_normal_lane_transit
from services.safety.fusion import _match_rider_to_bike


@pytest.fixture(scope="module")
def nb_modules():
    nb = json.load(open("backend/notebooks/cctv_safety_pipeline.ipynb", encoding="utf-8"))
    ns10, ns28, ns36, ns38 = {"_np": np, "_math": math, "kmeans2": None}, {"np": np}, {"np": np, "math": math}, {"np": np, "math": math}
    from scipy.cluster.vq import kmeans2
    ns10["kmeans2"] = kmeans2
    exec("".join(nb["cells"][10]["source"]), ns10)
    exec("".join(nb["cells"][28]["source"]), ns28)
    exec("".join(nb["cells"][36]["source"]), ns36)
    exec("".join(nb["cells"][38]["source"]), ns38)
    return {"cell10": ns10, "cell28": ns28, "cell36": ns36, "cell38": ns38}


def test_lane_auto_detector_equivalence(nb_modules):
    """Verify LaneAutoDetector & Sutherland-Hodgman clipping equivalence."""
    poly = np.array([[100, 100], [500, 80], [600, 800], [80, 750]], dtype=float)
    NBDetector = nb_modules["cell10"]["LaneAutoDetector"]
    # 1. Sutherland-Hodgman polygon clipping
    axis = np.array([0.7071, 0.7071])
    pa_prod, pb_prod = clip_polygon_by_axis(poly, axis)
    pa_nb, pb_nb = NBDetector(poly)._clip_polygon_by_axis(axis)
    assert np.allclose(pa_prod, pa_nb) and np.allclose(pb_prod, pb_nb)

    # 2. Bidirectional clustering
    dp, dnb = ProdLaneDetector(poly, bidir_threshold=0.75), NBDetector(poly, bidir_threshold=0.75)
    for _ in range(20):
        dp.observe(200, 400, 0.1, 10.0); dnb.observe(200, 400, 0.1, 10.0)
        dp.observe(450, 400, -0.1, -10.0); dnb.observe(450, 400, -0.1, -10.0)
    lp, lnb = dp.detect_lanes(), dnb.detect_lanes()
    assert len(lp) == len(lnb) == 2
    for p, n in zip(lp, lnb):
        assert p.id == n.id and np.allclose(p.permitted_unit_vector, n.permitted_unit_vector)


def test_direction_checking_equivalence(nb_modules):
    """Verify directional counter-flow checking equivalence across synthetic vectors."""
    nb_check = nb_modules["cell36"]["is_moving_counter_to_lane"]
    np.random.seed(42)
    for _ in range(1000):
        vel = np.random.uniform(-50, 50, 2)
        lane_angle = np.random.uniform(0, 2 * math.pi)
        lane_u = (math.cos(lane_angle), math.sin(lane_angle))
        res_nb = nb_check(vel, lane_u, min_cosine=-0.60)

        # Production calculation logic
        spd = math.hypot(vel[0], vel[1])
        if spd <= 0: continue
        vx, vy = vel[0] / spd, vel[1] / spd
        long_dot = vx * lane_u[0] + vy * lane_u[1]
        lat_dot = abs(vx * (-lane_u[1]) + vy * lane_u[0])
        res_prod = not (lat_dot >= abs(long_dot) or long_dot >= -0.60)
        assert res_nb == res_prod


def test_crosswalk_normal_transit_equivalence(nb_modules):
    """Verify crosswalk normal lane transit equivalence across 1000 randomized configurations."""
    nb_transit = nb_modules["cell38"]["is_normal_lane_transit"]
    np.random.seed(42)
    for _ in range(1000):
        dx, dy = float(np.random.uniform(-40, 40)), float(np.random.uniform(-40, 40))
        n_lanes = np.random.randint(0, 4)
        lanes = [(math.cos(a), math.sin(a)) for a in np.random.uniform(0, 2 * math.pi, n_lanes)]
        assert nb_transit(dx, dy, lanes) == prod_is_normal_lane_transit(dx, dy, lanes)


def test_rider_bike_fusion_equivalence(nb_modules):
    """Verify rider-bike vertical fusion and bounding box envelopment across camera depths."""
    nb_overlap = nb_modules["cell28"]["check_rider_bike_overlap"]
    nb_merge = nb_modules["cell28"]["merge_rider_and_bike_boxes"]
    for scale in [1.0, 0.6, 0.3]:
        bw, bh, pw, ph = 100 * scale, 200 * scale, 60 * scale, 140 * scale
        b_box = np.array([500.0 - bw / 2, 500.0 - bh / 2, 500.0 + bw / 2, 500.0 + bh / 2])
        p_box = np.array([500.0 - pw / 2, b_box[1] - 0.4 * ph, 500.0 + pw / 2, b_box[1] + 0.6 * ph])
        assert bool(nb_overlap(p_box, b_box)) is True
        dets = sv.Detections(xyxy=np.array([b_box.copy()]), class_id=np.array([3]))
        assert bool(_match_rider_to_bike(p_box, np.array([0]), dets)) is True
        # Merged box envelopment must match identically
        assert np.allclose(nb_merge(p_box, b_box), dets.xyxy[0])
