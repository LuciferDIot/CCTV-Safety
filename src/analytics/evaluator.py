"""Evaluation of detected safety events against benchmark ground truth."""
from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, List, Any


def evaluate_ground_truth(completed_events: list, gt_path: Path) -> Dict[str, Any]:
    """Compare detected events against ground truth JSON dataset."""
    if not gt_path.exists():
        return {"error": f"Ground truth not found at {gt_path}"}

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    gt_events = gt_data.get("events", [])
    pred_events = [ev.to_dict() if hasattr(ev, "to_dict") else ev for ev in completed_events]

    metrics = {
        "total_gt": len(gt_events),
        "total_pred": len(pred_events),
        "categories": defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0}),
        "matches": []
    }
    matched_gt, matched_pred = set(), set()

    for p_idx, pred in enumerate(pred_events):
        p_tid, p_type = pred["track_id"], pred["event_type"]
        p_start, p_end = pred["start_ts"], pred["end_ts"]

        best_g_idx = None
        for g_idx, gt in enumerate(gt_events):
            if g_idx in matched_gt or gt["event_type"] != p_type:
                continue
            time_overlap = max(0.0, min(p_end, gt["end_ts"]) - max(p_start, gt["start_ts"]))
            if p_tid == gt["track_id"] or time_overlap > 0.4:
                best_g_idx = g_idx
                break

        if best_g_idx is not None:
            matched_gt.add(best_g_idx)
            matched_pred.add(p_idx)
            metrics["categories"][p_type]["TP"] += 1
            metrics["matches"].append({
                "gt_id": gt_events[best_g_idx]["id"],
                "pred_id": pred["id"],
                "event_type": p_type,
                "status": "TP"
            })
        else:
            metrics["categories"][p_type]["FP"] += 1

    for g_idx, gt in enumerate(gt_events):
        if g_idx not in matched_gt:
            metrics["categories"][gt["event_type"]]["FN"] += 1

    tp = sum(c["TP"] for c in metrics["categories"].values())
    fp = sum(c["FP"] for c in metrics["categories"].values())
    fn = sum(c["FN"] for c in metrics["categories"].values())

    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-6, prec + rec)

    metrics["overall"] = {
        "precision": round(prec, 3),
        "recall": round(rec, 3),
        "f1_score": round(f1, 3)
    }
    return metrics

