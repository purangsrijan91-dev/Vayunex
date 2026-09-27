"""Automated Test Suite for INCOIS Tidal Harmonic Engine, Holland Wind, and Sensing APIs."""
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from app.core.incois_engine import (
    BAY_OF_BENGAL_TIDAL_STATIONS,
    compute_holland_wind_field,
    generate_tidal_forecast,
    get_active_cyclone_track,
    predict_astronomical_tide_at
)
from app.main import app

client = TestClient(app)


def test_tidal_harmonic_prediction_paradip():
    """Verify astronomical tidal prediction for Paradip observatory."""
    test_dt = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    pt = predict_astronomical_tide_at("Paradip_Odisha", test_dt)

    assert pt.phase in ["HIGH_TIDE", "LOW_TIDE", "FLOODING", "EBBING"]
    # Tidal height relative to MSL should stay within realistic Bay of Bengal bounds (~ -1.5m to +1.5m)
    assert -2.0 <= pt.tide_height_above_msl_m <= 2.0
    # Chart datum height should be positive
    assert pt.tide_height_above_cd_m > 0.0


def test_tidal_forecast_summary_24h():
    """Verify 24-hour tidal curve generation and extrema detection."""
    summary = generate_tidal_forecast("Dhamra_Odisha", hours=24)

    assert summary.station_key == "Dhamra_Odisha"
    assert summary.regime in ["Semidiurnal", "Mixed Semidiurnal"]
    assert len(summary.hourly_curve_24h) == 24
    assert summary.nearest_high_tide is not None
    assert summary.nearest_low_tide is not None
    assert summary.nearest_high_tide.tide_height_above_msl_m >= summary.nearest_low_tide.tide_height_above_msl_m


def test_holland_wind_field_decay():
    """Verify Holland (1980) parametric vortex radial decay."""
    profile = compute_holland_wind_field(
        central_pressure_hpa=935.0,
        radius_max_winds_km=35.0,
        latitude_deg=20.2
    )

    assert 1.0 <= profile.holland_b_parameter <= 2.5
    assert profile.max_gradient_wind_kmh > 150.0  # Intense cyclone

    # Wind speed at RMW should be near maximum, and decay towards outer radii
    radial_winds = {p["radius_km"]: p["wind_speed_kmh"] for p in profile.radial_wind_profile}
    wind_at_rmw = radial_winds.get(35.0, 0.0)
    wind_at_200km = radial_winds.get(200.0, 0.0)

    assert wind_at_rmw > wind_at_200km
    assert wind_at_200km > 0.0


def test_historical_and_forecast_tracks():
    """Verify cyclone track retrieval for both historical benchmarks and operational forecasts."""
    # Historical Benchmark: Cyclone Fani (2019)
    fani = get_active_cyclone_track(storm_id="CYCLONE_FANI_2019")
    assert len(fani.waypoints) == 4
    assert fani.storm_name == "Cyclone Fani 2019"

    # Operational Forward Forecast
    forecast = get_active_cyclone_track(storm_id="AGNI-2026-05B", sector_key="Paradip_Odisha", hours_to_landfall=8.0)
    assert len(forecast.waypoints) == 4
    assert forecast.projected_landfall_sector == "Paradip_Odisha"
    assert forecast.waypoints[-1].hours_to_landfall == 0.0


def test_api_sensing_tide_endpoint():
    """Verify REST API GET /api/v1/sensing/tide."""
    response = client.get("/api/v1/sensing/tide?sector=Paradip_Odisha&hours=12")
    assert response.status_code == 200
    data = response.json()
    assert data["station_key"] == "Paradip_Odisha"
    assert len(data["hourly_curve_24h"]) == 12


def test_api_sensing_track_endpoint():
    """Verify REST API GET /api/v1/sensing/track."""
    response = client.get("/api/v1/sensing/track?storm_id=CYCLONE_FANI_2019")
    assert response.status_code == 200
    data = response.json()
    assert "Fani" in data["storm_name"]
    assert len(data["waypoints"]) > 0


def test_api_sensing_wind_profile_endpoint():
    """Verify REST API GET /api/v1/sensing/wind-profile."""
    response = client.get("/api/v1/sensing/wind-profile?pressure=940&rmw=30&lat=20.5")
    assert response.status_code == 200
    data = response.json()
    assert "holland_b_parameter" in data
    assert len(data["radial_wind_profile"]) > 0


def test_api_financial_loss_report_endpoint(sample_telemetry):
    """Verify REST API POST /api/v1/financial/loss-report with role authorization."""
    payload = sample_telemetry.model_dump()
    headers = {"X-Aegis-Role": "INSURANCE_UNDERWRITER"}

    response = client.post("/api/v1/financial/loss-report", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert "total_assets_evaluated" in data
    assert "total_estimated_damage_usd" in data
    assert "portfolio_loss_ratio_percent" in data
    assert len(data["asset_loss_breakdown"]) > 0
