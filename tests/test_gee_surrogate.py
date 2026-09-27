"""Unit tests for Earth Engine & Hydrodynamic Surrogate Engine."""
import io
from PIL import Image
import pytest

from app.core.gee_engine import (
    calculate_hydrodynamic_surge,
    generate_surrogate_inundation_raster,
    run_inundation_model,
    InundationResult
)
from app.schemas.telemetry import CycloneTelemetry


def test_hydrodynamic_surge_physics():
    """Verify Inverse Barometer and Dynamic Wind Setup equations."""
    # Scenario: P_central = 940 hPa, Wind = 200 km/h, Tide = 1.5m
    static_s, dynamic_s, twse = calculate_hydrodynamic_surge(
        central_pressure_hpa=940.0,
        max_wind_speed_kmh=200.0,
        astronomical_tide_m=1.5
    )

    # Expected Inverse Barometer: (1013.25 - 940) * 0.0101 = 73.25 * 0.0101 = ~0.74m
    expected_static = round((1013.25 - 940.0) * 0.0101, 3)
    assert static_s == expected_static
    assert 0.70 <= static_s <= 0.80

    # Expected Dynamic Wind Setup: 0.00002 * (200^2) = 0.00002 * 40000 = 0.80m
    expected_dynamic = round(0.00002 * (200.0 ** 2), 3)
    assert dynamic_s == expected_dynamic
    assert dynamic_s == 0.80

    # Expected TWSE = 0.74 + 0.80 + 1.5 = 3.04m
    assert twse == round(static_s + dynamic_s + 1.5, 3)
    assert twse > 3.0


def test_inverse_barometer_clamping():
    """Verify static surge is 0 when pressure is above standard 1013.25 hPa."""
    static_s, _, _ = calculate_hydrodynamic_surge(1015.0, 50.0, 1.0)
    assert static_s == 0.0


def test_surrogate_inundation_raster_generation(sample_telemetry):
    """Verify 1024x1024 PNG raster output and metadata."""
    bbox = (20.15, 86.50, 20.45, 86.85)
    res: InundationResult = generate_surrogate_inundation_raster(sample_telemetry, bbox)

    assert isinstance(res, InundationResult)
    assert res.twse_m > 2.0
    assert res.bounds == bbox
    assert res.inundated_area_sqkm > 0.0

    # Verify PNG image dimensions and validity
    img = Image.open(io.BytesIO(res.image_bytes))
    assert img.size == (1024, 1024)
    assert img.mode == "RGBA"

    # Verify base64 property
    b64 = res.image_base64
    assert len(b64) > 1000
    assert isinstance(b64, str)


def test_run_inundation_model_dispatch(sample_telemetry):
    """Verify run_inundation_model dispatches and returns valid result."""
    result = run_inundation_model(sample_telemetry)
    assert result is not None
    assert result.twse_m > 0
    assert len(result.image_bytes) > 0
