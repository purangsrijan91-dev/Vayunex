"""FastAPI Production Entrypoint for Aegis-Cyclone.

Exposes operational REST endpoints for anticipatory cyclone forecasting,
multimodal cascade vulnerability reasoning, OASIS CAP v1.2 broadcasting,
and automated parametric liquidity triggers.
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, Response, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.gee_engine import run_inundation_model
from app.core.gemini_brain import reason_cyclone_impact
from app.core.hazus_engine import estimate_infrastructure_losses, PortfolioLossSummary
from app.core.incois_engine import (
    generate_tidal_forecast,
    predict_astronomical_tide_at,
    get_active_cyclone_track,
    compute_holland_wind_field,
    TidalForecastSummary,
    CycloneTrackForecast,
    HollandWindProfile
)
from app.core.osm_engine import extract_critical_infrastructure
from app.core.parametric_engine import generate_audit_receipt, ParametricAuditReceipt
from app.schemas.alerts import IncidentCommandSOP
from app.schemas.telemetry import CycloneTelemetry
from app.security.auth import AegisRole, require_roles
from app.security.sanitizer import (
    sanitize_text_input,
    validate_coastal_coordinates,
    validate_sector_bounds,
    SpatialBoundaryError,
    PromptInjectionError
)

# Setup Structured Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aegis.main")

# Initialize FastAPI App
app = FastAPI(
    title="Aegis-Cyclone API",
    description="Anticipatory Exposure & Geospatial Intelligence System for Coastal Cyclones",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active CAP alerts
_ACTIVE_CAP_ALERTS: Dict[str, str] = {}


class ConnectionManager:
    """Manages full-duplex WebSocket connections for live civil defense telemetry streaming."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@app.get("/")
def root_info():
    """Service landing page and operational metadata."""
    return {
        "system": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "OPERATIONAL",
        "docs": "/docs",
        "websocket_endpoint": "/ws/telemetry",
        "protocols": ["REST (HTTP/1.1)", "WebSocket (WS)"],
        "active_coastal_sectors": list(settings.COASTAL_SECTORS.keys()),
        "architecture": "FastAPI Backend + GEE DEM/SAR Inundation + OSM Overpass + Gemini 3.7 Flash + Parametric Triggers"
    }


@app.get("/api/v1/health")
def health_check():
    """System health check and subsystem status."""
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_key_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here"),
        "coastal_sectors_loaded": len(settings.COASTAL_SECTORS),
        "overpass_mirrors_count": len(settings.OVERPASS_MIRRORS)
    }


@app.get("/api/v1/sectors")
def list_coastal_sectors():
    """List all supported coastal risk sectors and bounding boxes."""
    return {
        "envelope": settings.EAST_COAST_ENVELOPE,
        "sectors": settings.COASTAL_SECTORS
    }


@app.post("/api/v1/forecast")
def run_cyclone_forecast(
    telemetry: CycloneTelemetry,
    current_role: AegisRole = Depends(require_roles([
        AegisRole.DISASTER_COMMANDER,
        AegisRole.INSURANCE_UNDERWRITER,
        AegisRole.FIELD_OPERATOR
    ]))
):
    """Execute end-to-end anticipatory cyclone vulnerability & cascade reasoning pipeline.

    1. Validates physical coastal boundaries & sanitizes strings.
    2. Runs hydrodynamic surge modeling (GEE / calibrated surrogate raster).
    3. Ingests critical OSM infrastructure (hospitals, substations, highways).
    4. Triggers Gemini 3.7 Flash multimodal reasoning (or deterministic fallback engine).
    """
    logger.info(f"Forecast requested by role [{current_role.value}] for sector [{telemetry.coastal_sector}]")

    # 1. Spatial Boundary and Input Sanitization
    try:
        telemetry.storm_name = sanitize_text_input(telemetry.storm_name)
        telemetry.storm_id = sanitize_text_input(telemetry.storm_id)
        sector_info = settings.COASTAL_SECTORS.get(telemetry.coastal_sector)
        if sector_info:
            c_lat, c_lon = sector_info["center"]
            validate_coastal_coordinates(c_lat, c_lon)
    except (SpatialBoundaryError, PromptInjectionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Run Hydrodynamic Surge Modeling
    inundation = run_inundation_model(telemetry)

    # 3. Ingest Critical Infrastructure Exposure
    assets = extract_critical_infrastructure(telemetry.coastal_sector)

    # 4. Multimodal Reasoning Agent
    sop: IncidentCommandSOP = reason_cyclone_impact(telemetry, inundation, assets)

    # Cache CAP Alert XML for direct broadcast URL retrieval
    alert_key = f"alert_{telemetry.storm_id}_{int(datetime.now(timezone.utc).timestamp())}"
    _ACTIVE_CAP_ALERTS[alert_key] = sop.cap_alert_xml

    return {
        "alert_id": alert_key,
        "caller_role": current_role.value,
        "telemetry_summary": {
            "storm_name": telemetry.storm_name,
            "storm_id": telemetry.storm_id,
            "central_pressure_hpa": telemetry.central_pressure_hpa,
            "max_wind_speed_kmh": telemetry.max_wind_speed_kmh,
            "imd_category": telemetry.imd_category,
            "twse_m": inundation.twse_m,
            "inundated_area_sqkm": inundation.inundated_area_sqkm
        },
        "incident_command_sop": sop,
        "inundation_raster": {
            "dimensions": "1024x1024",
            "bounds": inundation.bounds,
            "is_surrogate": inundation.is_mock_surrogate,
            "image_base64_thumbnail": inundation.image_base64[:500] + "... [TRUNCATED FOR SPEED]"
        }
    }


@app.post("/api/v1/parametric/verify", response_model=ParametricAuditReceipt)
def verify_parametric_insurance(
    telemetry: CycloneTelemetry,
    current_role: AegisRole = Depends(require_roles([
        AegisRole.DISASTER_COMMANDER,
        AegisRole.INSURANCE_UNDERWRITER
    ]))
):
    """Underwriter smart-contract verification endpoint with SHA-256 audit seal."""
    receipt = generate_audit_receipt(telemetry)
    logger.info(f"Parametric verification generated state hash: {receipt.cryptographic_state_hash}")
    return receipt


@app.get("/api/v1/cap/{alert_id}")
def export_cap_xml(alert_id: str):
    """Export OASIS CAP v1.2 XML document for direct meteorological broadcasting."""
    xml_content = _ACTIVE_CAP_ALERTS.get(alert_id)
    if not xml_content:
        # Generate on-demand fallback XML if not found
        xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>AEGIS-CAP-FALLBACK-{alert_id}</identifier>
  <sender>ops@aegis-cyclone.gov.in</sender>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Severe Cyclonic Storm Threat</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Observed</certainty>
    <headline>Aegis-Cyclone Operational Pre-Landfall Advisory</headline>
  </info>
</alert>"""

    return Response(content=xml_content, media_type="application/xml")


@app.get("/api/v1/field/dispatch", response_class=PlainTextResponse)
def get_low_bandwidth_field_dispatch(
    sector: str = "Paradip_Odisha",
    wind: float = 185.0,
    pressure: float = 945.0,
    tide: float = 1.2,
    current_role: AegisRole = Depends(require_roles([
        AegisRole.DISASTER_COMMANDER,
        AegisRole.FIELD_OPERATOR
    ]))
):
    """Generate compressed plaintext terminal dispatch (<5KB payload) for degraded 2G networks."""
    telemetry = CycloneTelemetry(
        central_pressure_hpa=pressure,
        max_wind_speed_kmh=wind,
        astronomical_tide_m=tide,
        coastal_sector=sector,
        landfall_eta_hours=6.0
    )
    inundation = run_inundation_model(telemetry)
    assets = extract_critical_infrastructure(sector)
    sop = reason_cyclone_impact(telemetry, inundation, assets)

    return sop.to_ics201_summary()


@app.get("/api/v1/sensing/tide", response_model=TidalForecastSummary)
def get_tidal_harmonic_forecast(sector: str = "Paradip_Odisha", hours: int = 24):
    """Predict astronomical tide levels using INCOIS harmonic constituent modeling (M2, S2, K1, O1)."""
    return generate_tidal_forecast(station_key=sector, hours=hours)


@app.get("/api/v1/sensing/track", response_model=CycloneTrackForecast)
def get_cyclone_track(
    storm_id: str = "AGNI-2026-05B",
    sector: str = "Paradip_Odisha",
    hours_to_landfall: float = 6.0
):
    """Retrieve operational IMD/JTWC cyclone trajectory and forward landfall extrapolation."""
    return get_active_cyclone_track(
        storm_id=storm_id,
        sector_key=sector,
        hours_to_landfall=hours_to_landfall
    )


@app.get("/api/v1/sensing/wind-profile", response_model=HollandWindProfile)
def get_holland_wind_profile(
    pressure: float = 940.0,
    rmw: float = 35.0,
    lat: float = 20.0
):
    """Compute Holland (1980) parametric cyclone wind field and radial velocity decay."""
    return compute_holland_wind_field(
        central_pressure_hpa=pressure,
        radius_max_winds_km=rmw,
        latitude_deg=lat
    )


@app.post("/api/v1/financial/loss-report", response_model=PortfolioLossSummary)
def generate_financial_loss_report(
    telemetry: CycloneTelemetry,
    current_role: AegisRole = Depends(require_roles([
        AegisRole.DISASTER_COMMANDER,
        AegisRole.INSURANCE_UNDERWRITER
    ]))
):
    """Pre-landfall quantitative infrastructure loss estimation report based on FEMA HAZUS-MH depth-damage curves."""
    inundation = run_inundation_model(telemetry)
    assets = extract_critical_infrastructure(telemetry.coastal_sector)
    report = estimate_infrastructure_losses(assets, inundation.twse_m)
    return report


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Full-duplex WebSocket endpoint for real-time telemetry streaming and cascade broadcast feeds."""
    await manager.connect(websocket)
    try:
        # Handshake
        await websocket.send_json({
            "event": "CONNECTED",
            "system": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "OPERATIONAL"
        })
        while True:
            data = await websocket.receive_json()
            # Process received telemetry
            telemetry = CycloneTelemetry(**data)
            inundation = run_inundation_model(telemetry)
            assets = extract_critical_infrastructure(telemetry.coastal_sector)
            sop = reason_cyclone_impact(telemetry, inundation, assets)

            response_payload = {
                "event": "TELEMETRY_UPDATE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "telemetry": {
                    "storm_name": telemetry.storm_name,
                    "storm_id": telemetry.storm_id,
                    "central_pressure_hpa": telemetry.central_pressure_hpa,
                    "max_wind_speed_kmh": telemetry.max_wind_speed_kmh,
                    "twse_m": inundation.twse_m,
                    "inundated_area_sqkm": inundation.inundated_area_sqkm,
                    "imd_category": telemetry.imd_category,
                },
                "incident_command_sop": sop.model_dump(),
                "parametric_status": sop.parametric_insurance.model_dump()
            }
            await websocket.send_json(response_payload)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket telemetry session error: {e}")
        manager.disconnect(websocket)


