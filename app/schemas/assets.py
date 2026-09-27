"""Critical Infrastructure and Exposure Asset Schemas.

Models OpenStreetMap and disaster management assets including Tier-1 hospitals,
primary substations, arterial highways, and cyclone shelters with DEM elevations.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    HOSPITAL = "hospital"
    SUBSTATION = "substation"
    HIGHWAY = "highway"
    SHELTER = "shelter"
    PUMP_STATION = "pump_station"


class CriticalityTier(str, Enum):
    TIER_1 = "TIER_1" # Mission critical life-safety (ICU hospitals, 220kV primary feeds)
    TIER_2 = "TIER_2" # Secondary support (Sub-district hospitals, 33kV substations, relief hubs)
    TIER_3 = "TIER_3" # Community level (Primary clinics, local distribution feeders)


class CriticalAsset(BaseModel):
    """Normalized critical infrastructure asset."""
    asset_id: str = Field(..., description="Unique asset identifier")
    name: str = Field(..., description="Official asset name")
    asset_type: AssetType = Field(..., description="Infrastructure category")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    elevation_m: float = Field(..., description="Ground elevation from hydro-enforced DEM in meters")
    criticality: CriticalityTier = Field(default=CriticalityTier.TIER_2, description="Criticality ranking")
    service_capacity: Optional[int] = Field(default=None, description="Bed count, MVA rating, or throughput")
    downstream_dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of assets or services reliant on this node"
    )
    district: Optional[str] = Field(default=None, description="Administrative district")
    osm_id: Optional[str] = Field(default=None, description="Original OpenStreetMap node/way identifier")

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert asset into a standard GeoJSON Feature dictionary."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                "asset_id": self.asset_id,
                "name": self.name,
                "asset_type": self.asset_type.value,
                "elevation_m": self.elevation_m,
                "criticality": self.criticality.value,
                "service_capacity": self.service_capacity,
                "downstream_dependencies": self.downstream_dependencies,
                "district": self.district
            }
        }


class AssetFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection wrapper for critical assets."""
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
