"""Unit tests for Parametric Insurance & Automated Liquidity Triggers."""
import pytest
from app.core.parametric_engine import (
    evaluate_parametric_triggers,
    build_parametric_trigger_model,
    generate_audit_receipt,
    ParametricAuditReceipt
)
from app.schemas.telemetry import CycloneTelemetry


def test_parametric_tier1_super_cyclone(sample_telemetry):
    """Verify 100% liquidity release on Tier-1 conditions (Wind >= 210 km/h)."""
    sample_telemetry.max_wind_speed_kmh = 225.0
    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(sample_telemetry)

    assert triggered is True
    assert tier == 100.0
    assert "Tier-1" in metric
    assert len(routing) >= 4
    assert len(state_hash) == 64  # SHA-256 hex length


def test_parametric_tier2_severe(sample_telemetry):
    """Verify 50% liquidity release on Tier-2 conditions (Wind >= 160 km/h)."""
    sample_telemetry.max_wind_speed_kmh = 175.0
    sample_telemetry.central_pressure_hpa = 960.0
    sample_telemetry.astronomical_tide_m = 0.5  # Keep TWSE < 3.0m

    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(sample_telemetry)

    assert triggered is True
    assert tier == 50.0
    assert "Tier-2" in metric


def test_parametric_tier3_moderate(sample_telemetry):
    """Verify 20% liquidity release on Tier-3 conditions (Wind >= 120 km/h)."""
    sample_telemetry.max_wind_speed_kmh = 135.0
    sample_telemetry.central_pressure_hpa = 980.0
    sample_telemetry.astronomical_tide_m = 0.5

    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(sample_telemetry)

    assert triggered is True
    assert tier == 20.0
    assert "Tier-3" in metric


def test_parametric_no_trigger():
    """Verify no payout when telemetry is within normal tropical depression range."""
    calm_telemetry = CycloneTelemetry(
        central_pressure_hpa=1002.0,
        max_wind_speed_kmh=55.0,
        astronomical_tide_m=0.3,
        landfall_eta_hours=48.0,
        coastal_sector="Paradip_Odisha"
    )
    triggered, metric, tier, routing, state_hash = evaluate_parametric_triggers(calm_telemetry)

    assert triggered is False
    assert tier == 0.0
    assert "no threshold breached" in metric


def test_audit_receipt_generation(sample_telemetry):
    """Verify formal underwriter audit receipt structure and verification status."""
    receipt: ParametricAuditReceipt = generate_audit_receipt(sample_telemetry)

    assert isinstance(receipt, ParametricAuditReceipt)
    assert receipt.storm_id == sample_telemetry.storm_id
    assert receipt.underwriter_verification_status in ["VERIFIED_VALID", "STANDBY"]
    assert receipt.total_liquidity_usd >= 0.0
    assert len(receipt.cryptographic_state_hash) == 64
