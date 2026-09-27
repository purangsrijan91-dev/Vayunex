"""OpenStreetMap (OSM) Infrastructure Ingestion & Spatial Cache.

Extracts critical hospitals, electrical substations, and arterial highways via
Overpass API with multi-mirror exponential backoff and offline GeoJSON fallback.
"""
import time
from typing import Dict, List, Optional, Tuple
import requests
from app.config import settings
from app.fixtures import load_bundled_coastal_assets
from app.schemas.assets import (
    AssetType,
    CriticalAsset,
    CriticalityTier
)

# In-memory spatial query cache: key -> (timestamp, List[CriticalAsset])
_SPATIAL_CACHE: Dict[str, Tuple[float, List[CriticalAsset]]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _build_overpass_query(bbox: Tuple[float, float, float, float]) -> str:
    """Construct an Overpass QL query string for critical infrastructure."""
    min_lat, min_lon, max_lat, max_lon = bbox
    return f"""
    [out:json][timeout:{settings.OVERPASS_TIMEOUT_SECONDS}];
    (
      node["amenity"="hospital"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"="hospital"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["power"="substation"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["power"="substation"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["highway"~"^(motorway|trunk|primary)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center tags;
    """


def _sample_dem_elevation(lat: float, lon: float, sector_name: str) -> float:
    """Sample approximate ground elevation in meters.

    Uses sector baseline elevation with micro-topographical gradient towards coast.
    """
    sector = settings.COASTAL_SECTORS.get(sector_name)
    base_elev = sector["default_elevation_m"] if sector else 3.5
    # Simulate gentle coastal slope: lower elevation towards higher longitude (coast)
    gradient = (lon - 86.5) * 0.8
    elevation = max(1.2, round(base_elev - gradient, 1))
    return elevation


def query_overpass_mirrors(bbox: Tuple[float, float, float, float]) -> Optional[dict]:
    """Execute Overpass QL query against mirror endpoints with exponential backoff."""
    ql = _build_overpass_query(bbox)
    headers = {"User-Agent": "AegisCyclone-DisasterForecaster/1.0 (ops@aegis-cyclone.gov.in)"}

    for mirror in settings.OVERPASS_MIRRORS:
        backoff = 1.0
        for attempt in range(2):
            try:
                response = requests.post(
                    mirror,
                    data={"data": ql},
                    headers=headers,
                    timeout=settings.OVERPASS_TIMEOUT_SECONDS
                )
                if response.status_code == 200:
                    data = response.json()
                    if "elements" in data and len(data["elements"]) > 0:
                        return data
                elif response.status_code == 429:
                    # Rate limit encountered; back off briefly
                    time.sleep(backoff)
                    backoff *= 2
            except (requests.RequestException, ValueError):
                time.sleep(0.5)
                break  # Try next mirror
    return None


def _parse_overpass_elements(
    elements: List[dict],
    sector_name: str
) -> List[CriticalAsset]:
    """Normalize raw Overpass JSON elements into CriticalAsset models."""
    assets: List[CriticalAsset] = []
    seen_ids = set()

    for el in elements:
        tags = el.get("tags", {})
        osm_id = f"{el.get('type')}/{el.get('id')}"
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)

        # Coordinate extraction
        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"].get("lat"), el["center"].get("lon")
        else:
            continue

        name = tags.get("name") or tags.get("name:en")
        amenity = tags.get("amenity")
        power = tags.get("power")
        highway = tags.get("highway")

        if amenity == "hospital":
            asset_type = AssetType.HOSPITAL
            crit = CriticalityTier.TIER_1 if "super" in (name or "").lower() or tags.get("emergency") == "yes" else CriticalityTier.TIER_2
            cap = int(tags.get("beds", 150))
            name = name or f"Community Hospital ({osm_id})"
        elif power == "substation":
            asset_type = AssetType.SUBSTATION
            crit = CriticalityTier.TIER_1 if any(v in tags.get("voltage", "") for v in ["220", "132", "400"]) else CriticalityTier.TIER_2
            cap = int(tags.get("rating:mva", 100))
            name = name or f"Grid Substation ({osm_id})"
        elif highway in ["motorway", "trunk", "primary"]:
            asset_type = AssetType.HIGHWAY
            crit = CriticalityTier.TIER_1 if highway in ["motorway", "trunk"] else CriticalityTier.TIER_2
            cap = 10000
            name = name or f"{tags.get('ref', 'Arterial Highway')} ({osm_id})"
        else:
            continue

        elev = _sample_dem_elevation(lat, lon, sector_name)

        assets.append(CriticalAsset(
            asset_id=f"OSM_{el.get('id')}",
            name=name,
            asset_type=asset_type,
            latitude=lat,
            longitude=lon,
            elevation_m=elev,
            criticality=crit,
            service_capacity=cap,
            district=tags.get("addr:district") or tags.get("district"),
            osm_id=osm_id
        ))

    return assets


def get_offline_fallback_assets(sector_name: str) -> List[CriticalAsset]:
    """Retrieve curated offline assets from the bundled GeoJSON fixture."""
    fixture_data = load_bundled_coastal_assets()
    features = fixture_data.get("features", [])
    assets: List[CriticalAsset] = []

    for f in features:
        props = f.get("properties", {})
        geom = f.get("geometry", {})
        coords = geom.get("coordinates", [0, 0])
        lon, lat = coords[0], coords[1]

        # Filter by sector if specified
        if sector_name and props.get("coastal_sector") != sector_name:
            # Check bounding box inclusion as alternate filter
            sector_info = settings.COASTAL_SECTORS.get(sector_name)
            if sector_info:
                min_lat, min_lon, max_lat, max_lon = sector_info["bbox"]
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    continue

        assets.append(CriticalAsset(
            asset_id=props["asset_id"],
            name=props["name"],
            asset_type=AssetType(props["asset_type"]),
            latitude=lat,
            longitude=lon,
            elevation_m=float(props["elevation_m"]),
            criticality=CriticalityTier(props.get("criticality", "TIER_2")),
            service_capacity=props.get("service_capacity"),
            downstream_dependencies=props.get("downstream_dependencies", []),
            district=props.get("district"),
            osm_id=props.get("osm_id")
        ))

    # If filtered set is empty, return all Paradip sector assets by default
    if not assets:
        return get_offline_fallback_assets("Paradip_Odisha")

    return assets


def extract_critical_infrastructure(
    sector_name: str = "Paradip_Odisha",
    force_refresh: bool = False
) -> List[CriticalAsset]:
    """Extract critical infrastructure for a given coastal sector.

    Implements a resilient 3-layer architecture:
    1. Fast in-memory spatial cache.
    2. Overpass API with multi-mirror exponential backoff.
    3. Bundled high-fidelity offline GeoJSON fixture.
    """
    now = time.time()
    cache_key = f"sector_{sector_name}"

    # 1. In-memory Cache check
    if not force_refresh and cache_key in _SPATIAL_CACHE:
        cached_time, cached_assets = _SPATIAL_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_assets

    sector_info = settings.COASTAL_SECTORS.get(
        sector_name,
        settings.COASTAL_SECTORS["Paradip_Odisha"]
    )
    bbox = sector_info["bbox"]

    # 2. Try Overpass API mirrors
    overpass_data = query_overpass_mirrors(bbox)
    if overpass_data and "elements" in overpass_data:
        live_assets = _parse_overpass_elements(overpass_data["elements"], sector_name)
        if len(live_assets) >= 3:
            _SPATIAL_CACHE[cache_key] = (now, live_assets)
            return live_assets

    # 3. Seamless offline fixture fallback
    fallback_assets = get_offline_fallback_assets(sector_name)
    _SPATIAL_CACHE[cache_key] = (now, fallback_assets)
    return fallback_assets
