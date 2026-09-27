"""Aegis-Cyclone Configuration Module.

Loads environment variables, defines operational thresholds, Overpass mirror lists,
and geographic coastal boundary boxes for anticipatory cyclone modeling.
"""
from typing import Dict, List, Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoastalSector(BaseSettings):
    """Geographic sector bounding box and metadata."""
    name: str
    state: str
    bbox: Tuple[float, float, float, float]  # min_lat, min_lon, max_lat, max_lon
    center: Tuple[float, float]             # center_lat, center_lon
    default_elevation_m: float = 3.5


class Settings(BaseSettings):
    """Global operational settings loaded from environment or defaults."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Identifiers
    APP_NAME: str = "Aegis-Cyclone"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"

    # AI & Google GenAI SDK
    GEMINI_API_KEY: str = Field(default="", alias="GEMINI_API_KEY")
    GEMINI_MODEL: str = "gemini-3.7-flash"
    THINKING_LEVEL: str = "high"

    # Google Cloud & Earth Engine
    GCP_PROJECT_ID: str = "aegis-cyclone-ops"
    GEE_SERVICE_ACCOUNT: str = ""
    GEE_PRIVATE_KEY_PATH: str = ""

    # Security & RBAC Secrets
    JWT_SECRET_KEY: str = "aegis_cyclone_super_secret_jwt_key_change_in_production_2026"
    JWT_ALGORITHM: str = "HS256"
    API_KEY_DISASTER_COMMANDER: str = "cmd_live_984712039482"
    API_KEY_INSURANCE_UNDERWRITER: str = "und_live_120938472918"
    API_KEY_FIELD_OPERATOR: str = "ops_live_837462819382"

    # Overpass OSM Mirrors with automatic fallback
    OVERPASS_MIRRORS: List[str] = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    OVERPASS_TIMEOUT_SECONDS: int = 25

    # Hydrodynamic & Physics Parameters
    STANDARD_ATMOSPHERIC_PRESSURE_HPA: float = 1013.25
    INVERSE_BAROMETER_FACTOR: float = 0.0101   # meters per hPa depression
    DYNAMIC_WIND_SETUP_FACTOR: float = 0.00002 # meters per (km/h)^2

    # Parametric Insurance Liquidity Triggers
    PARAMETRIC_WIND_THRESHOLD_TIER1_KMH: float = 210.0  # Category 4/Super Cyclone
    PARAMETRIC_WIND_THRESHOLD_TIER2_KMH: float = 160.0  # Very Severe Cyclone
    PARAMETRIC_WIND_THRESHOLD_TIER3_KMH: float = 120.0  # Severe Cyclone

    PARAMETRIC_SURGE_THRESHOLD_TIER1_M: float = 3.0
    PARAMETRIC_SURGE_THRESHOLD_TIER2_M: float = 2.0
    PARAMETRIC_SURGE_THRESHOLD_TIER3_M: float = 1.2

    PARAMETRIC_PRESSURE_THRESHOLD_TIER1_HPA: float = 930.0
    PARAMETRIC_PRESSURE_THRESHOLD_TIER2_HPA: float = 950.0
    PARAMETRIC_PRESSURE_THRESHOLD_TIER3_HPA: float = 970.0

    # Coastal Sectors Definitions
    COASTAL_SECTORS: Dict[str, Dict] = {
        "Paradip_Odisha": {
            "name": "Paradip Port & Industrial Hub",
            "state": "Odisha",
            "bbox": (20.15, 86.50, 20.45, 86.85),
            "center": (20.30, 86.68),
            "default_elevation_m": 3.0,
            "district": "Jagatsinghpur"
        },
        "Dhamra_Odisha": {
            "name": "Dhamra Port & Mangrove Delta",
            "state": "Odisha",
            "bbox": (20.65, 86.80, 20.95, 87.15),
            "center": (20.80, 86.95),
            "default_elevation_m": 2.5,
            "district": "Bhadrak"
        },
        "Puri_Odisha": {
            "name": "Puri Coastal Urban Sector",
            "state": "Odisha",
            "bbox": (19.70, 85.70, 19.95, 86.00),
            "center": (19.81, 85.83),
            "default_elevation_m": 4.5,
            "district": "Puri"
        },
        "Balasore_Odisha": {
            "name": "Balasore & Chandipur Sector",
            "state": "Odisha",
            "bbox": (21.35, 86.85, 21.65, 87.15),
            "center": (21.48, 87.00),
            "default_elevation_m": 3.8,
            "district": "Balasore"
        },
        "Digha_WestBengal": {
            "name": "Digha-Shankarpur Coastal Strip",
            "state": "West Bengal",
            "bbox": (21.55, 87.40, 21.75, 87.70),
            "center": (21.63, 87.52),
            "default_elevation_m": 2.8,
            "district": "Purba Medinipur"
        },
        "Haldia_WestBengal": {
            "name": "Haldia Industrial & Refining Port",
            "state": "West Bengal",
            "bbox": (21.95, 87.95, 22.15, 88.25),
            "center": (22.05, 88.08),
            "default_elevation_m": 3.2,
            "district": "Purba Medinipur"
        }
    }

    # East Coast Boundary Envelope for Physical Sanitization
    EAST_COAST_ENVELOPE: Tuple[float, float, float, float] = (
        17.5, 83.5, 23.5, 89.5 # min_lat, min_lon, max_lat, max_lon
    )


settings = Settings()
