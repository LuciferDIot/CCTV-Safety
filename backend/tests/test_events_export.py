"""Tests for event schema serialization and CSV/JSON export formatting."""
from app.config import Settings
from app.services.event_service import EventService


def test_demo_scenarios_presence():
    svc = EventService(Settings())
    events = svc.get_events()
    event_ids = [e.event_id for e in events]

    assert "EV-101" in event_ids
    assert "EV-102" in event_ids
    assert "EV-103" in event_ids
    assert "EV-104" in event_ids
    assert "EV-105" in event_ids

    ev101 = svc.get_event_by_id("EV-101")
    assert ev101.status == "CONFIRMED"
    assert ev101.event_type == "WRONG_WAY"
    assert ev101.stitched is True
    assert ev101.confidence >= 0.90

    ev103 = svc.get_event_by_id("EV-103")
    assert ev103.status == "EXEMPT"
    assert ev103.posture_metrics.posture == "dismounted"


def test_csv_export_format():
    svc = EventService(Settings())
    csv_text = svc.export_csv()
    lines = csv_text.strip().split("\n")
    assert len(lines) >= 6
    header = lines[0].strip().split(",")
    assert "event_id" in header
    assert "status" in header
    assert "confidence" in header

