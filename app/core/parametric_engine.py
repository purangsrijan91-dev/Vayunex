"""Parametric Insurance & Automated Liquidity Verification Engine.

Evaluates empirical cyclone telemetry against pre-agreed parametric trigger tiers,
generates SHA-256 cryptographic settlement proofs, and computes automated multi-agency
liquidity disbursement routing for anticipatory disaster response.
"""
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings
from app.schemas.alerts import ParametricInsuranceTrigger
from app.schemas.telemetry import CycloneTelemetry


class ParametricAuditReceipt(BaseModel):
    """Cryptographically verifiable parametric liquidity execution receipt."""
    contract_id: str = "AEGIS-PARAMETRIC-ODISHA-2026-T5"
    storm_id: str
    storm_name: str
    evaluation_timestamp: str
    trigger_status: bool
    triggered_metric: str
    payout_tier_percent: float
    total_liquidity_usd: float
    disbursement_routing: Dict[str, str]
    cryptographic_state_hash: str
    underwriter_verification_status: str = "VERIFIED_VALID"


def evaluate_parametric_triggers(
    telemetry: CycloneTelemetry
) -> Tuple[bool, str, float, Dict[str, str], str]:
    """Evaluate atmospheric and surge metrics against smart contract criteria.

    Returns:
        (trigger_status, triggered_metric, payout_tier_percent, disbursement_routing, state_hash)
    """
    wind = telemetry.max_wind_speed_kmh
    pressure = telemetry.central_pressure_hpa
    twse = telemetry.total_water_surface_elevation_m

    tier1_wind = settings.PARAMETRIC_WIND_THRESHOLD_TIER1_KMH
    tier1_surge = settings.PARAMETRIC_SURGE_THRESHOLD_TIER1_M
    tier1_press = settings.PARAMETRIC_PRESSURE_THRESHOLD_TIER1_HPA

    tier2_wind = settings.PARAMETRIC_WIND_THRESHOLD_TIER2_KMH
    tier2_surge = settings.PARAMETRIC_SURGE_THRESHOLD_TIER2_M
    tier2_press = settings.PARAMETRIC_PRESSURE_THRESHOLD_TIER2_HPA

    tier3_wind = settings.PARAMETRIC_WIND_THRESHOLD_TIER3_KMH
    tier3_surge = settings.PARAMETRIC_SURGE_THRESHOLD_TIER3_M
    tier3_press = settings.PARAMETRIC_PRESSURE_THRESHOLD_TIER3_HPA

    triggered = False
    metric_str = "Telemetry within normal seasonal tolerance; no threshold breached."
    tier_percent = 0.0

    # Tier 1 Assessment: 100% Payout
    if wind >= tier1_wind or twse >= tier1_surge or pressure <= tier1_press:
        triggered = True
        tier_percent = 100.0
        reasons = []
        if wind >= tier1_wind:
            reasons.append(f"Wind Speed {wind} km/h >= {tier1_wind} km/h (Tier-1)")
        if twse >= tier1_surge:
            reasons.append(f"Surge TWSE {twse}m >= {tier1_surge}m (Tier-1)")
        if pressure <= tier1_press:
            reasons.append(f"Central Pressure {pressure} hPa <= {tier1_press} hPa (Tier-1)")
        metric_str = " | ".join(reasons)

    # Tier 2 Assessment: 50% Payout
    elif wind >= tier2_wind or twse >= tier2_surge or pressure <= tier2_press:
        triggered = True
        tier_percent = 50.0
        reasons = []
        if wind >= tier2_wind:
            reasons.append(f"Wind Speed {wind} km/h >= {tier2_wind} km/h (Tier-2)")
        if twse >= tier2_surge:
            reasons.append(f"Surge TWSE {twse}m >= {tier2_surge}m (Tier-2)")
        if pressure <= tier2_press:
            reasons.append(f"Central Pressure {pressure} hPa <= {tier2_press} hPa (Tier-2)")
        metric_str = " | ".join(reasons)

    # Tier 3 Assessment: 20% Payout
    elif wind >= tier3_wind or twse >= tier3_surge or pressure <= tier3_press:
        triggered = True
        tier_percent = 20.0
        reasons = []
        if wind >= tier3_wind:
            reasons.append(f"Wind Speed {wind} km/h >= {tier3_wind} km/h (Tier-3)")
        if twse >= tier3_surge:
            reasons.append(f"Surge TWSE {twse}m >= {tier3_surge}m (Tier-3)")
        if pressure <= tier3_press:
            reasons.append(f"Central Pressure {pressure} hPa <= {tier3_press} hPa (Tier-3)")
        metric_str = " | ".join(reasons)

    # Base facility pool: $25 Million USD maximum
    max_liquidity_usd = 25_000_000.0
    liquidity_allocated = (tier_percent / 100.0) * max_liquidity_usd

    if triggered:
        disbursement = {
            "OSDMA_State_Disaster_Relief_Account": f"${(liquidity_allocated * 0.45):,.2f}",
            "DEOC_District_Prepositioning_Vault": f"${(liquidity_allocated * 0.30):,.2f}",
            "Public_Health_Backup_Energy_Reserves": f"${(liquidity_allocated * 0.15):,.2f}",
            "Panchayat_Level_Evacuation_Logistics": f"${(liquidity_allocated * 0.10):,.2f}"
        }
    else:
        disbursement = {
            "Status": "Liquidity escrow locked; awaiting telemetry threshold confirmation"
        }

    # Generate SHA-256 cryptographic state hash
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_payload = f"{telemetry.storm_id}:{telemetry.central_pressure_hpa}:{telemetry.max_wind_speed_kmh}:{twse}:{tier_percent}:{now_iso}"
    state_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    return triggered, metric_str, tier_percent, disbursement, state_hash


def build_parametric_trigger_model(
    telemetry: CycloneTelemetry
) -> ParametricInsuranceTrigger:
    """Construct the Pydantic ParametricInsuranceTrigger object."""
    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(telemetry)
    return ParametricInsuranceTrigger(
        trigger_status=triggered,
        triggered_metric=metric,
        payout_tier_percent=tier,
        disbursement_routing=routing,
        settlement_proof_hash=state_hash
    )


def generate_audit_receipt(telemetry: CycloneTelemetry) -> ParametricAuditReceipt:
    """Generate a formal underwriter audit receipt for smart contract execution."""
    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(telemetry)
    max_liquidity = 25_000_000.0
    allocated = (tier / 100.0) * max_liquidity

    return ParametricAuditReceipt(
        storm_id=telemetry.storm_id,
        storm_name=telemetry.storm_name,
        evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
        trigger_status=triggered,
        triggered_metric=metric,
        payout_tier_percent=tier,
        total_liquidity_usd=allocated,
        disbursement_routing=routing,
        cryptographic_state_hash=state_hash,
        underwriter_verification_status="VERIFIED_VALID" if triggered else "STANDBY"
    )
