"""Pytest test session configuration and workspace artifact isolation fixture."""
import pytest
from pathlib import Path
from config import get_settings


@pytest.fixture(autouse=True, scope="session")
def preserve_tracked_artifacts():
    """Preserves tracked repository files (e.g. data/output/detected_events.json) from test mutation."""
    settings = get_settings()
    out_dir = settings.resolve(settings.output_dir)
    ev_path = out_dir / "detected_events.json"
    original_content = ev_path.read_text(encoding="utf-8") if ev_path.exists() else None
    yield
    if original_content is not None:
        ev_path.write_text(original_content, encoding="utf-8")
