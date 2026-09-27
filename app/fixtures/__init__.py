"""Offline GeoJSON fixtures for coastal exposure infrastructure."""
from pathlib import Path
import json

FIXTURES_DIR = Path(__file__).parent
COASTAL_ASSETS_PATH = FIXTURES_DIR / "coastal_assets_odisha_bengal.json"

def load_bundled_coastal_assets() -> dict:
    """Load the bundled offline GeoJSON fixture."""
    with open(COASTAL_ASSETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
