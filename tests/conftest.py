"""Pytest configuration and shared fixtures for Aegis-Cyclone test suite."""
import pytest
from app.schemas.telemetry import CycloneTelemetry
from app.schemas.assets import CriticalAsset, AssetType, CriticalityTier


@pytest.fixture
def sample_telemetry() -> CycloneTelemetry:
    """Standard severe cyclonic storm test telemetry."""
    return CycloneTelemetry(
        storm_id="TEST-CYCLONE-01",
        storm_name="Test Cyclone Varun",
        central_pressure_hpa=940.0,
        max_wind_speed_kmh=195.0,
        radius_max_winds_km=35.0,
        landfall_eta_hours=8.0,
        astronomical_tide_m=1.5,
        coastal_sector="Paradip_Odisha"
    )


@pytest.fixture
def sample_assets() -> list[CriticalAsset]:
    """Representative set of coastal critical assets."""
    return [
        CriticalAsset(
            asset_id="HOSP_01",
            name="Paradip Port Hospital",
            asset_type=AssetType.HOSPITAL,
            latitude=20.292,
            longitude=86.668,
            elevation_m=2.2,
            criticality=CriticalityTier.TIER_1,
            downstream_dependencies=["ICU_WING"]
        ),
        CriticalAsset(
            asset_id="SUBST_01",
            name="Paradip 220kV Grid Substation",
            asset_type=AssetType.SUBSTATION,
            latitude=20.288,
            longitude=86.654,
            elevation_m=1.8,
            criticality=CriticalityTier.TIER_1,
            downstream_dependencies=["HOSP_01"]
        ),
        CriticalAsset(
            asset_id="HWY_01",
            name="NH-53 Coastal Arterial Corridor",
            asset_type=AssetType.HIGHWAY,
            latitude=20.295,
            longitude=86.620,
            elevation_m=2.0,
            criticality=CriticalityTier.TIER_1,
            downstream_dependencies=["EVACUATION_FLEET"]
        )
    ]
