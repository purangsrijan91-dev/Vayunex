"""Gemini 3.7 Flash Multimodal Reasoning Agent & Deterministic Fallback Engine.

Consumes 1024x1024 visual hydrodynamic inundation rasters, atmospheric telemetry,
and vector infrastructure metadata to calculate spatial cascade failures,
ICS-201 Incident Briefings, OASIS CAP v1.2 XML, and vernacular broadcasts.
"""
import json
import logging
from typing import List, Optional
from google import genai
from google.genai import types

from app.config import settings
from app.core.gee_engine import InundationResult, calculate_hydrodynamic_surge
from app.core.parametric_engine import build_parametric_trigger_model
from app.schemas.alerts import (
    AssetBreach,
    EvacuationCorridorStatus,
    IncidentCommandSOP,
    ThreatPosture,
    VernacularDispatches,
    Waypoint,
    generate_oasis_cap_v12
)
from app.schemas.assets import AssetType, CriticalAsset, CriticalityTier
from app.schemas.telemetry import CycloneTelemetry

logger = logging.getLogger("aegis.gemini_brain")


def _build_multimodal_prompt(
    telemetry: CycloneTelemetry,
    inundation: InundationResult,
    assets: List[CriticalAsset]
) -> str:
    """Construct structured instruction prompt for Gemini 3.7 Flash."""
    assets_summary = []
    for a in assets:
        assets_summary.append({
            "asset_id": a.asset_id,
            "name": a.name,
            "type": a.asset_type.value,
            "coordinates": [a.latitude, a.longitude],
            "ground_elevation_m": a.elevation_m,
            "criticality": a.criticality.value,
            "dependencies": a.downstream_dependencies
        })

    return f"""
You are the Chief Geospatial & AI Risk Officer for the National Disaster Management Authority (Aegis-Cyclone).
Analyze the attached 1024x1024 satellite visual inundation map and quantitative telemetry for {telemetry.storm_name} ({telemetry.storm_id}).

==================== 1. QUANTITATIVE TELEMETRY ====================
- Coastal Sector: {telemetry.coastal_sector}
- Central Atmospheric Pressure: {telemetry.central_pressure_hpa} hPa
- Maximum Sustained Winds: {telemetry.max_wind_speed_kmh} km/h ({telemetry.imd_category})
- Radius of Maximum Winds (RMW): {telemetry.radius_max_winds_km} km
- Landfall ETA: {telemetry.landfall_eta_hours} hours
- Astronomical Tide Level: {telemetry.astronomical_tide_m} m
- Total Water Surface Elevation (TWSE): {inundation.twse_m} m (Static Surge: {inundation.static_surge_m}m + Dynamic Setup: {inundation.dynamic_surge_m}m + Tide: {inundation.tide_m}m)
- Projected Inundated Coastal Area: {inundation.inundated_area_sqkm} sq km

==================== 2. VISUAL INUNDATION MAP GUIDE ====================
- The attached 1024x1024 RGB image is a hydrodynamic digital elevation surge model.
- BLUE PIXELS (#0055FF) represent projected storm surge penetration where ground elevation <= TWSE ({inundation.twse_m}m).
- Deep navy represents the open sea; dark slate represents dry land above surge level.
- Visually and mathematically inspect spatial intersections between blue surge plumes and critical asset coordinates.

==================== 3. EXPOSED CRITICAL INFRASTRUCTURE ====================
{json.dumps(assets_summary, indent=2)}

==================== 4. MANDATORY REASONING OBJECTIVES ====================
1. Physical Vulnerability & Breach Probability:
   - For each asset, evaluate if TWSE ({inundation.twse_m}m) > asset.ground_elevation_m.
   - Assign breach_probability between 0.0 and 1.0 based on physical water depth over ground.
   - Estimate time_to_cutoff_hours before storm surge penetration physically surrounds or breaches the asset.

2. Cascading Graph Impact Analysis:
   - Reason through secondary and tertiary system failures:
     * If an electrical grid substation is inundated, trace power collapse to connected Tier-1 hospitals, water drainage pump stations, and municipal telecom grids.
     * If an arterial highway (e.g. NH-53 or NH-116B) is breached, assess evacuation cutoff for coastal wards and formulate high-elevation bypass detours.

3. Threat Posture:
   - Classify as RED (imminent life-safety/energy backbone breach within 6h), ORANGE (high risk, anticipatory evacuation active), or YELLOW (monitoring).

4. Parametric Insurance Trigger:
   - Determine trigger status and payout tier (100% if wind >= 210 km/h or TWSE >= 3.0m; 50% if wind >= 160 km/h or TWSE >= 2.0m; 20% if wind >= 120 km/h or TWSE >= 1.2m).

5. OASIS CAP v1.2 XML:
   - Generate a complete, valid OASIS CAP v1.2 XML alert document string in cap_alert_xml.

6. Vernacular Advisories:
   - Provide clear, zero-jargon public broadcasts in authentic Odia script, Bengali script, and Plain English.

Generate the output strictly conforming to the IncidentCommandSOP JSON schema.
"""


def run_deterministic_fallback_engine(
    telemetry: CycloneTelemetry,
    inundation: InundationResult,
    assets: List[CriticalAsset]
) -> IncidentCommandSOP:
    """Deterministic heuristic rule engine used when Gemini API is unavailable or offline.

    Compares asset elevation directly against TWSE, deduces graph cascade dependencies,
    computes parametric liquidity, and generates OASIS CAP v1.2 XML with vernacular dispatches.
    """
    twse = inundation.twse_m
    breaches: List[AssetBreach] = []
    severed_routes: List[str] = []
    clear_routes: List[str] = []
    substation_breaches: set = set()

    # Pass 1: Pre-identify all breached substations across the sector grid
    for a in assets:
        if a.asset_type == AssetType.SUBSTATION and (twse - a.elevation_m) > 0:
            substation_breaches.add(a.asset_id)

    # Pass 2: Primary physical elevation breach assessment & cascade formulation
    for asset in assets:
        elev = asset.elevation_m
        delta = twse - elev

        if delta > 0:
            # Water surface overtakes ground elevation
            ratio = min(1.0, delta / max(1.0, twse))
            breach_prob = round(min(1.0, 0.55 + (0.45 * ratio)), 2)
            cutoff_h = max(0.5, round(telemetry.landfall_eta_hours * max(0.1, (elev / max(0.1, twse))), 1))
            if asset.asset_type == AssetType.HIGHWAY:
                severed_routes.append(asset.name)
        elif abs(delta) <= 0.6:
            # Wave runup and tidal wash buffer zone
            breach_prob = 0.35
            cutoff_h = max(1.0, round(telemetry.landfall_eta_hours * 0.8, 1))
            if asset.asset_type == AssetType.HIGHWAY:
                severed_routes.append(asset.name)
        else:
            # High ground above surge reach
            breach_prob = 0.05
            cutoff_h = round(telemetry.landfall_eta_hours + 12.0, 1)
            if asset.asset_type == AssetType.HIGHWAY:
                clear_routes.append(asset.name)

        # Cascading risk formulation
        cascade_desc = []
        action_desc = []

        if asset.asset_type == AssetType.SUBSTATION:
            if breach_prob >= 0.5:
                cascade_desc.append(
                    f"CRITICAL POWER CASCADE: Inundation of {asset.name} drops grid power to "
                    f"{', '.join(asset.downstream_dependencies) or 'downstream feeders'}."
                )
                action_desc.append("De-energize substation before water ingress; isolate coastal feeders to protect grid.")
            else:
                cascade_desc.append("Peripheral surge risk; substation perimeter dykes holding.")
                action_desc.append("Deploy trailer-mounted suction pumps to switchyard perimeters.")

        elif asset.asset_type == AssetType.HOSPITAL:
            # Check if any parent substation feeding this hospital or regional grid is breached
            dep_breach = bool(substation_breaches)
            if breach_prob >= 0.5:
                cascade_desc.append(
                    "FACILITY INUNDATION: Ground-floor trauma ward and backup diesel generators threatened by storm surge. "
                    + ("CRITICAL CASCADE: GRID POWER COMPROMISED BY SUBSTATION BREACH." if dep_breach else "")
                )
                action_desc.append("Evacuate ground-floor ICU to vertical floors 2+; activate rooftop emergency generators.")
            elif dep_breach:
                cascade_desc.append(
                    "EXTERNAL POWER COLLAPSE: Hospital structure is dry, but feeding grid substation has breached. Facility on generator power."
                )
                action_desc.append("Transfer ICU to dedicated diesel generator; dispatch fuel tankers via inland routes.")
            else:
                cascade_desc.append("Facility secure on high elevation; designated regional medical triage point.")
                action_desc.append("Prepare 150 mass-casualty receiving beds and stockpile 72h potable water.")

        elif asset.asset_type == AssetType.HIGHWAY:
            if breach_prob >= 0.5:
                cascade_desc.append("ARTERY SEVERED: Coastal surge breach cuts primary civil evacuation and logistics transit.")
                action_desc.append("Erect roadblocks at km 14; re-route evacuation buses to inland high-ridge corridors.")
            else:
                cascade_desc.append("Corridor operational on elevated embankment.")
                action_desc.append("Deploy traffic police escort for heavy vehicle convoys.")

        elif asset.asset_type == AssetType.PUMP_STATION:
            if breach_prob >= 0.5:
                cascade_desc.append("PUMP FAILURE: Station submerged; backflow through estuarine canals flooding municipal wards.")
                action_desc.append("Drop gravity storm sluice gates to prevent sea water backflow.")
            else:
                cascade_desc.append("Pumps running at maximum drainage capacity.")
                action_desc.append("Maintain 24/7 operator shift with radio backup.")

        else:  # Shelters
            cascade_desc.append("Multi-purpose cyclone shelter structurally engineered for storm surges.")
            action_desc.append("Admit up to registered capacity; seal ground level flood barriers.")

        breaches.append(AssetBreach(
            asset_id=asset.asset_id,
            asset_name=asset.name,
            elevation_m=asset.elevation_m,
            breach_probability=breach_prob,
            time_to_cutoff_hours=cutoff_h,
            cascade_risk=" ".join(cascade_desc),
            mitigation_action=" ".join(action_desc)
        ))

    # Threat Posture determination
    high_breach_count = sum(1 for b in breaches if b.breach_probability >= 0.5)
    if high_breach_count >= 2 or twse >= 3.0 or telemetry.max_wind_speed_kmh >= 200:
        posture = ThreatPosture.RED
    elif high_breach_count >= 1 or twse >= 1.8 or telemetry.max_wind_speed_kmh >= 140:
        posture = ThreatPosture.ORANGE
    else:
        posture = ThreatPosture.YELLOW

    # Evacuation Corridors & Alternate Waypoints
    if not clear_routes:
        clear_routes.append("Inland High-Ridge State Bypass SH-12")
    if not severed_routes:
        severed_routes.append("No arterial routes currently severed")

    alternate_waypoints = [
        Waypoint(
            name="Kujang Inland Evacuation Relief Hub",
            latitude=20.320,
            longitude=86.560,
            advisory="Safe elevated assembly zone (Elev: 4.6m) for Paradip evacuees."
        ),
        Waypoint(
            name="Bhadrak High-Ridge Staging Ground",
            latitude=20.880,
            longitude=86.850,
            advisory="Safe transit point (Elev: 5.1m) connecting Jamujhadi corridor."
        )
    ]

    corridor_status = EvacuationCorridorStatus(
        severed_routes=severed_routes,
        clear_routes=clear_routes,
        alternate_waypoints=alternate_waypoints
    )

    # Parametric Liquidity
    parametric = build_parametric_trigger_model(telemetry)

    # OASIS CAP v1.2 XML
    cap_xml = generate_oasis_cap_v12(
        sender="Aegis-Cyclone-Automated-Forecast-System@ndma.gov.in",
        event=f"{telemetry.imd_category} - {telemetry.storm_name}",
        urgency="Immediate" if posture == ThreatPosture.RED else "Expected",
        severity="Extreme" if posture == ThreatPosture.RED else "Severe",
        certainty="Observed",
        headline=f"URGENT: Coastal Storm Surge Inundation Warning for {telemetry.coastal_sector}",
        description=(
            f"{telemetry.storm_name} is tracking towards {telemetry.coastal_sector} with sustained winds of {telemetry.max_wind_speed_kmh} km/h "
            f"and TWSE of {twse}m. Severe inundation forecast across low-lying coastal infrastructure within {telemetry.landfall_eta_hours} hours."
        ),
        instruction=(
            "Execute mandatory anticipatory evacuation for all persons within 5km of the coastline. "
            "Re-route traffic away from severed arteries. Activate hospital backup energy generators immediately."
        ),
        area_desc=f"{telemetry.coastal_sector} Coastal Risk Zone"
    )

    # Vernacular Advisories
    vernacular = VernacularDispatches(
        odia=(
            f"ଜରୁରୀ ସୂଚନା: ବାତ୍ୟା '{telemetry.storm_name}' ଯୋଗୁଁ {telemetry.coastal_sector} ଉପକୂଳରେ {twse} ମିଟର ଉଚ୍ଚ ଜୁଆର "
            f"ଓ {telemetry.max_wind_speed_kmh} କି.ମି./ଘଣ୍ଟା ବେଗରେ ପବନ ଆସୁଛି। ତଳିଆ ଅଞ୍ଚଳ ଲୋକମାନେ ତୁରନ୍ତ ବାତ୍ୟା ଆଶ୍ରୟସ୍ଥଳୀକୁ ଚାଲିଯାଆନ୍ତୁ।"
        ),
        bengali=(
            f"জরুরী সতর্কতা: ঘূর্ণিঝড় '{telemetry.storm_name}'-এর প্রভাবে {telemetry.coastal_sector} উপকূলে {twse} মিটার উচ্চ জলোচ্ছ্বাস "
            f"এবং ঘণ্টায় {telemetry.max_wind_speed_kmh} কিমি বেগে ঝড়ো হাওয়া বয়ে যাবে। নিচু এলাকার বাসিন্দাদের অবিলম্বে নিরাপদ আশ্রয়কেন্দ্রে যাওয়ার নির্দেশ দেওয়া হচ্ছে।"
        ),
        english=(
            f"CRITICAL DISASTER BROADCAST: Severe cyclone '{telemetry.storm_name}' approaching {telemetry.coastal_sector}. "
            f"Storm surge elevation {twse}m and winds of {telemetry.max_wind_speed_kmh} km/h. Mandatory evacuation ordered for all low-lying coastal zones."
        )
    )

    cot_summary = (
        f"Deterministic cascade reasoning executed against {len(assets)} assets. "
        f"Storm Surge TWSE of {twse}m breaches {high_breach_count} critical structures. "
        f"Substation failure propagates down to hospital life-support systems; severed routes isolated and rerouted to inland ridge."
    )

    return IncidentCommandSOP(
        threat_posture=posture,
        asset_breaches=breaches,
        evacuation_corridor_status=corridor_status,
        parametric_insurance=parametric,
        cap_alert_xml=cap_xml,
        vernacular_dispatches=vernacular,
        chain_of_thought_summary=cot_summary
    )


def reason_cyclone_impact(
    telemetry: CycloneTelemetry,
    inundation: InundationResult,
    assets: List[CriticalAsset]
) -> IncidentCommandSOP:
    """Multimodal reasoning agent for cyclone impact and infrastructure cascade modeling.

    Executes Gemini 3.7 Flash with thinking_level='high' and Pydantic response enforcement.
    Gracefully drops to the deterministic heuristic rule engine on network timeouts,
    missing keys, or API quota limitations without crashing.
    """
    # Check if Gemini API Key is configured
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        logger.info("[GeminiBrain] No active Gemini API key configured. Executing deterministic fallback rule engine.")
        return run_deterministic_fallback_engine(telemetry, inundation, assets)

    try:
        # Initialize modern google-genai client
        client = genai.Client(api_key=api_key)

        # Build prompt and multimodal parts
        prompt_text = _build_multimodal_prompt(telemetry, inundation, assets)
        image_part = types.Part.from_bytes(
            data=inundation.image_bytes,
            mime_type="image/png"
        )

        # Enforce thinking_level='high' and structured JSON schema without conflicting sampling params
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=settings.THINKING_LEVEL),
            response_mime_type="application/json",
            response_schema=IncidentCommandSOP
        )

        logger.info(f"[GeminiBrain] Dispatching multimodal reasoning query to {settings.GEMINI_MODEL}...")
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[image_part, prompt_text],
            config=config
        )

        # Parse generated response
        if response.text:
            parsed_sop = IncidentCommandSOP.model_validate_json(response.text)
            logger.info(f"[GeminiBrain] Successfully parsed IncidentCommandSOP from {settings.GEMINI_MODEL}.")
            return parsed_sop
        else:
            logger.warning("[GeminiBrain] Empty response text from Gemini. Falling back to rule engine.")
            return run_deterministic_fallback_engine(telemetry, inundation, assets)

    except Exception as e:
        logger.warning(f"[GeminiBrain] Gemini API invocation error ({type(e).__name__}: {e}). Gracefully executing deterministic fallback rule engine.")
        return run_deterministic_fallback_engine(telemetry, inundation, assets)
