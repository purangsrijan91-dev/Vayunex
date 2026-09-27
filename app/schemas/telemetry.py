"""Atmospheric and Marine Telemetry Schemas.

Models incoming cyclone tracking observations, barometric sensor feeds,
and tidal forecasts for hydrodynamic surge modeling.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class CycloneTelemetry(BaseModel):
    """Real-time or forecast atmospheric cyclone parameters."""
    storm_id: str = Field(default="AGNI-2026-05B", description="Cyclone identifier code")
    storm_name: str = Field(default="Cyclone Agni", description="Designated cyclone name")
    central_pressure_hpa: float = Field(
        ...,
        ge=870.0,
        le=1020.0,
        description="Central barometric pressure in hectopascals (hPa)"
    )
    max_wind_speed_kmh: float = Field(
        ...,
        ge=30.0,
        le=340.0,
        description="Maximum 1-minute sustained wind speed in km/h"
    )
    radius_max_winds_km: float = Field(
        default=35.0,
        ge=5.0,
        le=150.0,
        description="Radius of maximum winds (RMW) in kilometers"
    )
    landfall_eta_hours: float = Field(
        ...,
        ge=0.0,
        le=120.0,
        description="Estimated time to coastal landfall in hours"
    )
    astronomical_tide_m: float = Field(
        default=1.2,
        ge=0.0,
        le=6.0,
        description="Forecast astronomical tide level at landfall hour in meters"
    )
    coastal_sector: str = Field(
        default="Paradip_Odisha",
        description="Key of the target coastal sector under threat"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Observation timestamp (UTC ISO format)"
    )

    @computed_field
    @property
    def static_surge_m(self) -> float:
        """Inverse Barometer Effect: max(0, 1013.25 - P_central) * 0.0101 meters."""
        depression = max(0.0, 1013.25 - self.central_pressure_hpa)
        return round(depression * 0.0101, 3)

    @computed_field
    @property
    def dynamic_surge_m(self) -> float:
        """Dynamic wind setup: 0.00002 * (V_wind_kmh)^2 meters."""
        return round(0.00002 * (self.max_wind_speed_kmh ** 2), 3)

    @computed_field
    @property
    def total_water_surface_elevation_m(self) -> float:
        """Total Water Surface Elevation (TWSE) = Static Surge + Dynamic Surge + Tide."""
        return round(self.static_surge_m + self.dynamic_surge_m + self.astronomical_tide_m, 3)

    @computed_field
    @property
    def imd_category(self) -> str:
        """Categorize cyclone severity per IMD classification scale."""
        w = self.max_wind_speed_kmh
        if w >= 222:
            return "Super Cyclonic Storm (SuCS)"
        elif w >= 166:
            return "Extremely Severe Cyclonic Storm (ESCS)"
        elif w >= 118:
            return "Very Severe Cyclonic Storm (VSCS)"
        elif w >= 88:
            return "Severe Cyclonic Storm (SCS)"
        elif w >= 62:
            return "Cyclonic Storm (CS)"
        return "Deep Depression (DD)"
