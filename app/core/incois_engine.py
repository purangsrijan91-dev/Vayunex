"""INCOIS & IMD Sensing Engine for Bay of Bengal Cyclones.

Provides:
1. Astronomical tidal harmonic constituent modeling (M2, S2, K1, O1) for Odisha & West Bengal
   coastal stations (Paradip, Dhamra, Puri, Balasore, Digha, Haldia).
2. Holland (1980) parametric cyclone wind field profile (radial wind decay & B-parameter).
3. IMD / JTWC / IBTrACS cyclone track repository and forward landfall extrapolation.
"""
from datetime import datetime, timezone, timedelta
import math
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings


# ============================================================================
# 1. ASTRONOMICAL TIDAL HARMONIC MODELING (INCOIS / Survey of India Calibrated)
# ============================================================================

class TidalConstituent(BaseModel):
    """Harmonic constituent parameter."""
    name: str
    speed_deg_per_hour: float  # Angular velocity
    amplitude_m: float         # Amplitude in meters
    phase_lag_deg: float       # Epoch phase lag in degrees


class TidalStationProfile(BaseModel):
    """Harmonic configuration for a coastal tidal gauge."""
    station_name: str
    latitude: float
    longitude: float
    mean_sea_level_datum_m: float  # Z0 above Chart Datum (CD)
    constituents: Dict[str, TidalConstituent]


# Calibrated harmonic constituents from INCOIS / Survey of India tidal tables
BAY_OF_BENGAL_TIDAL_STATIONS: Dict[str, TidalStationProfile] = {
    "Paradip_Odisha": TidalStationProfile(
        station_name="Paradip Port Tidal Observatory",
        latitude=20.2644,
        longitude=86.6744,
        mean_sea_level_datum_m=1.85,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=0.88, phase_lag_deg=102.5),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.38, phase_lag_deg=145.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.18, phase_lag_deg=315.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.09, phase_lag_deg=288.0),
        }
    ),
    "Dhamra_Odisha": TidalStationProfile(
        station_name="Dhamra Port Marine Gauge",
        latitude=20.8055,
        longitude=86.9722,
        mean_sea_level_datum_m=2.40,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=1.35, phase_lag_deg=118.0),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.55, phase_lag_deg=162.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.22, phase_lag_deg=322.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.11, phase_lag_deg=295.0),
        }
    ),
    "Puri_Odisha": TidalStationProfile(
        station_name="Puri Coastal Station",
        latitude=19.7983,
        longitude=85.8249,
        mean_sea_level_datum_m=1.65,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=0.72, phase_lag_deg=95.0),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.32, phase_lag_deg=138.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.16, phase_lag_deg=310.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.08, phase_lag_deg=282.0),
        }
    ),
    "Balasore_Odisha": TidalStationProfile(
        station_name="Balasore / Chandipur Gauge",
        latitude=21.4934,
        longitude=86.9328,
        mean_sea_level_datum_m=2.75,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=1.52, phase_lag_deg=125.0),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.62, phase_lag_deg=170.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.25, phase_lag_deg=328.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.13, phase_lag_deg=301.0),
        }
    ),
    "Digha_Bengal": TidalStationProfile(
        station_name="Digha Coastal Gauge",
        latitude=21.6266,
        longitude=87.5074,
        mean_sea_level_datum_m=2.60,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=1.45, phase_lag_deg=122.0),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.58, phase_lag_deg=168.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.24, phase_lag_deg=325.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.12, phase_lag_deg=298.0),
        }
    ),
    "Haldia_Bengal": TidalStationProfile(
        station_name="Haldia / Sagar Island Gauge",
        latitude=21.6500,
        longitude=88.0500,
        mean_sea_level_datum_m=3.10,
        constituents={
            "M2": TidalConstituent(name="Principal lunar semidiurnal", speed_deg_per_hour=28.984104, amplitude_m=1.82, phase_lag_deg=132.0),
            "S2": TidalConstituent(name="Principal solar semidiurnal", speed_deg_per_hour=30.000000, amplitude_m=0.74, phase_lag_deg=178.0),
            "K1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=15.041069, amplitude_m=0.28, phase_lag_deg=332.0),
            "O1": TidalConstituent(name="Lunar diurnal", speed_deg_per_hour=13.943036, amplitude_m=0.14, phase_lag_deg=305.0),
        }
    ),
}

# Fixed reference epoch: 2026-01-01 00:00:00 UTC
REFERENCE_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class TidalPredictionPoint(BaseModel):
    """Tide height prediction at a specific hour."""
    timestamp: str
    tide_height_above_msl_m: float
    tide_height_above_cd_m: float
    rate_of_change_m_per_hr: float
    phase: str  # "HIGH_TIDE", "LOW_TIDE", "FLOODING", "EBBING"


class TidalForecastSummary(BaseModel):
    """Comprehensive tidal prediction report for a coastal sector."""
    station_key: str
    station_name: str
    latitude: float
    longitude: float
    form_factor: float
    regime: str  # "Semidiurnal", "Mixed Semidiurnal", etc.
    current_prediction: TidalPredictionPoint
    nearest_high_tide: TidalPredictionPoint
    nearest_low_tide: TidalPredictionPoint
    spring_neap_phase: str
    hourly_curve_24h: List[TidalPredictionPoint]


def predict_astronomical_tide_at(
    station_key: str,
    target_dt: datetime
) -> TidalPredictionPoint:
    """Predict tidal elevation for a coastal station using harmonic constituent synthesis."""
    if station_key not in BAY_OF_BENGAL_TIDAL_STATIONS:
        station_key = "Paradip_Odisha"

    profile = BAY_OF_BENGAL_TIDAL_STATIONS[station_key]
    delta_hours = (target_dt - REFERENCE_EPOCH).total_seconds() / 3600.0

    # Calculate tidal deviation from MSL
    eta_msl = 0.0
    d_eta = 0.0  # Derivative for rate of change (m/hr)

    for c in profile.constituents.values():
        omega_rad = math.radians(c.speed_deg_per_hour)
        phase_rad = math.radians(c.phase_lag_deg)
        argument = (omega_rad * delta_hours) - phase_rad

        eta_msl += c.amplitude_m * math.cos(argument)
        d_eta -= c.amplitude_m * omega_rad * math.sin(argument)

    eta_msl = round(eta_msl, 3)
    eta_cd = round(profile.mean_sea_level_datum_m + eta_msl, 3)
    d_eta = round(d_eta, 3)

    # Determine tidal phase
    if abs(d_eta) < 0.05:
        phase = "HIGH_TIDE" if eta_msl > 0 else "LOW_TIDE"
    elif d_eta > 0:
        phase = "FLOODING"
    else:
        phase = "EBBING"

    return TidalPredictionPoint(
        timestamp=target_dt.isoformat(),
        tide_height_above_msl_m=eta_msl,
        tide_height_above_cd_m=eta_cd,
        rate_of_change_m_per_hr=d_eta,
        phase=phase
    )


def generate_tidal_forecast(
    station_key: str,
    start_dt: Optional[datetime] = None,
    hours: int = 24
) -> TidalForecastSummary:
    """Generate 24-hr / 48-hr hourly tidal sequence and find extreme astronomical tide events."""
    if station_key not in BAY_OF_BENGAL_TIDAL_STATIONS:
        station_key = "Paradip_Odisha"

    profile = BAY_OF_BENGAL_TIDAL_STATIONS[station_key]
    if start_dt is None:
        start_dt = datetime.now(timezone.utc)

    # Compute Form Factor: F = (K1 + O1) / (M2 + S2)
    k1 = profile.constituents["K1"].amplitude_m
    o1 = profile.constituents["O1"].amplitude_m
    m2 = profile.constituents["M2"].amplitude_m
    s2 = profile.constituents["S2"].amplitude_m
    form_factor = round((k1 + o1) / max(0.01, (m2 + s2)), 3)
    regime = "Semidiurnal" if form_factor < 0.25 else "Mixed Semidiurnal"

    hourly_curve: List[TidalPredictionPoint] = []
    highest_pt: Optional[TidalPredictionPoint] = None
    lowest_pt: Optional[TidalPredictionPoint] = None

    for h in range(hours):
        t = start_dt + timedelta(hours=h)
        pt = predict_astronomical_tide_at(station_key, t)
        hourly_curve.append(pt)

        if highest_pt is None or pt.tide_height_above_msl_m > highest_pt.tide_height_above_msl_m:
            highest_pt = pt
        if lowest_pt is None or pt.tide_height_above_msl_m < lowest_pt.tide_height_above_msl_m:
            lowest_pt = pt

    current_pt = hourly_curve[0]

    # Spring/Neap status: M2 and S2 cycle beating every ~14.77 days
    delta_days = (start_dt - REFERENCE_EPOCH).total_seconds() / 86400.0
    phase_diff = (delta_days % 14.77) / 14.77
    if phase_diff < 0.15 or phase_diff > 0.85:
        spring_neap = "SPRING TIDE (Enhanced Inundation Risk)"
    elif 0.35 <= phase_diff <= 0.65:
        spring_neap = "NEAP TIDE (Reduced Tidal Range)"
    else:
        spring_neap = "TRANSITIONAL TIDE"

    return TidalForecastSummary(
        station_key=station_key,
        station_name=profile.station_name,
        latitude=profile.latitude,
        longitude=profile.longitude,
        form_factor=form_factor,
        regime=regime,
        current_prediction=current_pt,
        nearest_high_tide=highest_pt,
        nearest_low_tide=lowest_pt,
        spring_neap_phase=spring_neap,
        hourly_curve_24h=hourly_curve
    )


# ============================================================================
# 2. HOLLAND (1980) PARAMETRIC WIND FIELD PROFILE & RADIAL VELOCITY
# ============================================================================

class HollandWindProfile(BaseModel):
    """Parametric Holland (1980) vortex parameters."""
    central_pressure_hpa: float
    ambient_pressure_hpa: float
    radius_max_winds_km: float
    holland_b_parameter: float
    max_gradient_wind_kmh: float
    coriolis_parameter_s1: float
    radial_wind_profile: List[Dict[str, float]]  # [{"radius_km": r, "wind_speed_kmh": v}]


def compute_holland_wind_field(
    central_pressure_hpa: float,
    radius_max_winds_km: float,
    latitude_deg: float = 20.0,
    ambient_pressure_hpa: float = 1013.25
) -> HollandWindProfile:
    """Compute the Holland (1980) parametric cyclone wind field profile.

    V(r) = sqrt( (RMW/r)^B * (B/rho) * (P_env - P_c) * exp(-(RMW/r)^B) + (r*f/2)^2 ) - (r*f/2)
    where:
      - B = 1.88 - 0.00557 * RMW + 0.0015 * (P_env - P_c)  [Bounded between 1.0 and 2.5]
      - rho = 1.15 kg/m^3 (air density)
      - f = 2 * Omega * sin(lat) (Coriolis parameter)
    """
    rho = 1.15  # kg/m^3
    dp_hpa = max(1.0, ambient_pressure_hpa - central_pressure_hpa)
    dp_pa = dp_hpa * 100.0  # Convert hPa to Pa

    # Holland B parameter formulation (Harper & Holland, 1999 calibrated)
    b_param = 1.88 - (0.00557 * radius_max_winds_km) + (0.0015 * dp_hpa)
    b_param = max(1.0, min(2.5, round(b_param, 3)))

    # Coriolis parameter: f = 2 * Omega * sin(phi)
    omega = 7.292115e-5  # rad/s
    f = 2.0 * omega * math.sin(math.radians(latitude_deg))

    # Evaluate radial velocities from 5 km to 250 km
    radii_km = [5, 10, 15, 20, 25, 30, radius_max_winds_km, 45, 60, 80, 100, 150, 200, 250]
    radii_km = sorted(list(set(radii_km)))

    radial_data: List[Dict[str, float]] = []
    max_wind_kmh = 0.0

    for r_km in radii_km:
        r_m = r_km * 1000.0
        ratio = radius_max_winds_km / r_km
        term_exp = math.exp(-(ratio ** b_param))

        # Core Holland wind equation in m/s
        core = (ratio ** b_param) * (b_param / rho) * dp_pa * term_exp
        coriolis_term = ((r_m * f) / 2.0) ** 2

        v_ms = math.sqrt(max(0.0, core + coriolis_term)) - ((r_m * f) / 2.0)
        v_kmh = max(0.0, round(v_ms * 3.6, 1))

        if v_kmh > max_wind_kmh:
            max_wind_kmh = v_kmh

        radial_data.append({
            "radius_km": float(r_km),
            "wind_speed_kmh": v_kmh
        })

    return HollandWindProfile(
        central_pressure_hpa=central_pressure_hpa,
        ambient_pressure_hpa=ambient_pressure_hpa,
        radius_max_winds_km=radius_max_winds_km,
        holland_b_parameter=b_param,
        max_gradient_wind_kmh=round(max_wind_kmh, 1),
        coriolis_parameter_s1=round(f, 7),
        radial_wind_profile=radial_data
    )


# ============================================================================
# 3. IMD / JTWC / IBTrACS TRACK REPOSITORY & LANDFALL INGESTION
# ============================================================================

class CycloneTrackWaypoint(BaseModel):
    """Observation or forecast waypoint along cyclone trajectory."""
    timestamp: str
    latitude: float
    longitude: float
    central_pressure_hpa: float
    max_wind_speed_kmh: float
    radius_max_winds_km: float
    category: str
    hours_to_landfall: float


class CycloneTrackForecast(BaseModel):
    """Complete cyclone track package with meteorological guidance."""
    storm_id: str
    storm_name: str
    basin: str = "North Indian Ocean (Bay of Bengal)"
    projected_landfall_sector: str
    projected_landfall_time_utc: str
    current_translation_speed_kmh: float
    current_bearing_deg: float
    waypoints: List[CycloneTrackWaypoint]


# Benchmark historical tracks for validation and drills
HISTORICAL_CYCLONE_TRACKS: Dict[str, List[CycloneTrackWaypoint]] = {
    "CYCLONE_FANI_2019": [
        CycloneTrackWaypoint(timestamp="2019-05-02T00:00:00Z", latitude=15.8, longitude=84.8, central_pressure_hpa=932.0, max_wind_speed_kmh=215.0, radius_max_winds_km=30.0, category="Extremely Severe Cyclonic Storm", hours_to_landfall=28.0),
        CycloneTrackWaypoint(timestamp="2019-05-02T12:00:00Z", latitude=17.5, longitude=85.2, central_pressure_hpa=937.0, max_wind_speed_kmh=205.0, radius_max_winds_km=32.0, category="Extremely Severe Cyclonic Storm", hours_to_landfall=16.0),
        CycloneTrackWaypoint(timestamp="2019-05-03T00:00:00Z", latitude=19.3, longitude=85.7, central_pressure_hpa=942.0, max_wind_speed_kmh=195.0, radius_max_winds_km=35.0, category="Extremely Severe Cyclonic Storm", hours_to_landfall=4.0),
        CycloneTrackWaypoint(timestamp="2019-05-03T04:00:00Z", latitude=19.8, longitude=85.8, central_pressure_hpa=945.0, max_wind_speed_kmh=185.0, radius_max_winds_km=35.0, category="Extremely Severe Cyclonic Storm", hours_to_landfall=0.0),
    ],
    "CYCLONE_AMPHAN_2020": [
        CycloneTrackWaypoint(timestamp="2020-05-19T00:00:00Z", latitude=15.6, longitude=86.7, central_pressure_hpa=915.0, max_wind_speed_kmh=240.0, radius_max_winds_km=28.0, category="Super Cyclonic Storm", hours_to_landfall=34.0),
        CycloneTrackWaypoint(timestamp="2020-05-19T18:00:00Z", latitude=18.4, longitude=87.1, central_pressure_hpa=930.0, max_wind_speed_kmh=210.0, radius_max_winds_km=32.0, category="Extremely Severe Cyclonic Storm", hours_to_landfall=16.0),
        CycloneTrackWaypoint(timestamp="2020-05-20T10:00:00Z", latitude=21.6, longitude=88.3, central_pressure_hpa=950.0, max_wind_speed_kmh=165.0, radius_max_winds_km=38.0, category="Very Severe Cyclonic Storm", hours_to_landfall=0.0),
    ],
    "CYCLONE_YAAS_2021": [
        CycloneTrackWaypoint(timestamp="2021-05-25T06:00:00Z", latitude=18.2, longitude=88.5, central_pressure_hpa=982.0, max_wind_speed_kmh=110.0, radius_max_winds_km=45.0, category="Severe Cyclonic Storm", hours_to_landfall=24.0),
        CycloneTrackWaypoint(timestamp="2021-05-25T18:00:00Z", latitude=19.8, longitude=87.8, central_pressure_hpa=974.0, max_wind_speed_kmh=130.0, radius_max_winds_km=40.0, category="Very Severe Cyclonic Storm", hours_to_landfall=12.0),
        CycloneTrackWaypoint(timestamp="2021-05-26T04:00:00Z", latitude=21.3, longitude=87.0, central_pressure_hpa=968.0, max_wind_speed_kmh=140.0, radius_max_winds_km=38.0, category="Very Severe Cyclonic Storm", hours_to_landfall=0.0),
    ]
}


def get_active_cyclone_track(
    storm_id: str = "AGNI-2026-05B",
    sector_key: str = "Paradip_Odisha",
    hours_to_landfall: float = 6.0
) -> CycloneTrackForecast:
    """Generate or retrieve operational cyclone track trajectory.

    Matches against benchmark database if historical ID provided, or synthesizes
    an IMD/JTWC compliant forward track approaching the targeted coastal sector.
    """
    if storm_id in HISTORICAL_CYCLONE_TRACKS:
        pts = HISTORICAL_CYCLONE_TRACKS[storm_id]
        return CycloneTrackForecast(
            storm_id=storm_id,
            storm_name=storm_id.replace("_", " ").title(),
            projected_landfall_sector="Dhamra_Odisha",
            projected_landfall_time_utc=pts[-1].timestamp,
            current_translation_speed_kmh=18.5,
            current_bearing_deg=28.0,
            waypoints=pts
        )

    # Sector target coordinate
    sector_info = settings.COASTAL_SECTORS.get(
        sector_key,
        settings.COASTAL_SECTORS["Paradip_Odisha"]
    )
    target_lat, target_lon = sector_info["center"]

    # Synthesize 4 approaching waypoints (-18h, -12h, -6h, 0h Landfall)
    now = datetime.now(timezone.utc)
    landfall_dt = now + timedelta(hours=hours_to_landfall)

    waypoints: List[CycloneTrackWaypoint] = []
    time_steps = [18.0, 12.0, 6.0, 0.0]

    for step_hrs in time_steps:
        # Cyclone approaching from South-East (azimuth ~ 145 deg)
        dist_km = step_hrs * 18.0  # Approx 18 km/h translation speed
        # 1 deg lat ~= 111 km, 1 deg lon ~= 104 km
        lat_offset = (dist_km * math.cos(math.radians(145))) / 111.0
        lon_offset = (dist_km * math.sin(math.radians(145))) / 104.0

        pt_lat = round(target_lat + lat_offset, 3)
        pt_lon = round(target_lon + lon_offset, 3)
        pt_dt = landfall_dt - timedelta(hours=step_hrs)

        # Intensification profile
        if step_hrs > 12.0:
            press = 970.0
            wind = 135.0
            cat = "Very Severe Cyclonic Storm"
        elif step_hrs > 4.0:
            press = 948.0
            wind = 175.0
            cat = "Extremely Severe Cyclonic Storm"
        else:
            press = 938.0
            wind = 195.0
            cat = "Extremely Severe Cyclonic Storm"

        waypoints.append(CycloneTrackWaypoint(
            timestamp=pt_dt.isoformat(),
            latitude=pt_lat,
            longitude=pt_lon,
            central_pressure_hpa=press,
            max_wind_speed_kmh=wind,
            radius_max_winds_km=35.0,
            category=cat,
            hours_to_landfall=step_hrs
        ))

    return CycloneTrackForecast(
        storm_id=storm_id,
        storm_name=f"Cyclone {storm_id.split('-')[0].capitalize()}",
        projected_landfall_sector=sector_key,
        projected_landfall_time_utc=landfall_dt.isoformat(),
        current_translation_speed_kmh=18.0,
        current_bearing_deg=325.0,  # Heading NW towards Odisha/Bengal coast
        waypoints=waypoints
    )
