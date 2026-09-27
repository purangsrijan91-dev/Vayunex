"""Unit tests for Gemini 3.7 Flash reasoner & deterministic fallback engine."""
import xml.etree.ElementTree as ET
import pytest

from app.core.gee_engine import generate_surrogate_inundation_raster
from app.core.gemini_brain import (
    reason_cyclone_impact,
    run_deterministic_fallback_engine
)
from app.schemas.alerts import IncidentCommandSOP, ThreatPosture


def test_deterministic_fallback_engine_schema(sample_telemetry, sample_assets):
    """Verify fallback engine generates 100% compliant IncidentCommandSOP."""
    bbox = (20.15, 86.50, 20.45, 86.85)
    inundation = generate_surrogate_inundation_raster(sample_telemetry, bbox)

    sop = run_deterministic_fallback_engine(sample_telemetry, inundation, sample_assets)

    assert isinstance(sop, IncidentCommandSOP)
    assert sop.threat_posture in [ThreatPosture.RED, ThreatPosture.ORANGE, ThreatPosture.YELLOW]
    assert len(sop.asset_breaches) == len(sample_assets)

    # Verify breach fields
    for b in sop.asset_breaches:
        assert 0.0 <= b.breach_probability <= 1.0
        assert b.time_to_cutoff_hours >= 0.0
        assert len(b.cascade_risk) > 10
        assert len(b.mitigation_action) > 10

    # Verify Evacuation Corridors
    assert len(sop.evacuation_corridor_status.severed_routes) > 0
    assert len(sop.evacuation_corridor_status.clear_routes) > 0
    assert len(sop.evacuation_corridor_status.alternate_waypoints) > 0

    # Verify Vernacular Dispatches
    assert len(sop.vernacular_dispatches.odia) > 20
    assert len(sop.vernacular_dispatches.bengali) > 20
    assert len(sop.vernacular_dispatches.english) > 20


def test_oasis_cap_xml_conformance(sample_telemetry, sample_assets):
    """Verify OASIS CAP v1.2 XML string parses and satisfies emergency schema."""
    bbox = (20.15, 86.50, 20.45, 86.85)
    inundation = generate_surrogate_inundation_raster(sample_telemetry, bbox)
    sop = run_deterministic_fallback_engine(sample_telemetry, inundation, sample_assets)

    xml_str = sop.cap_alert_xml
    assert isinstance(xml_str, str)
    assert "urn:oasis:names:tc:emergency:cap:1.2" in xml_str

    # Parse XML
    root = ET.fromstring(xml_str)
    assert root.tag.endswith("alert")
    
    # Check mandatory CAP children
    child_tags = [c.tag.split("}")[-1] for c in root]
    for mandatory in ["identifier", "sender", "sent", "status", "msgType", "scope", "info"]:
        assert mandatory in child_tags


def test_cascade_failure_deduction(sample_telemetry, sample_assets):
    """Verify cascading graph failure reasoning (substation inundation -> hospital power loss)."""
    # Force high TWSE (> 3.0m) to inundate 1.8m elevation substation
    sample_telemetry.max_wind_speed_kmh = 240.0
    sample_telemetry.central_pressure_hpa = 920.0
    sample_telemetry.astronomical_tide_m = 2.0

    bbox = (20.15, 86.50, 20.45, 86.85)
    inundation = generate_surrogate_inundation_raster(sample_telemetry, bbox)
    sop = run_deterministic_fallback_engine(sample_telemetry, inundation, sample_assets)

    assert sop.threat_posture == ThreatPosture.RED

    # Check substation breach
    subst_breach = next(b for b in sop.asset_breaches if b.asset_id == "SUBST_01")
    assert subst_breach.breach_probability >= 0.5
    assert "CASCADE" in subst_breach.cascade_risk.upper()

    # Check hospital breach reflects power failure
    hosp_breach = next(b for b in sop.asset_breaches if b.asset_id == "HOSP_01")
    assert "GRID POWER" in hosp_breach.cascade_risk.upper() or "SUBSTATION" in hosp_breach.cascade_risk.upper()


def test_ics201_summary_formatting(sample_telemetry, sample_assets):
    """Verify ICS-201 summary formatting."""
    bbox = (20.15, 86.50, 20.45, 86.85)
    inundation = generate_surrogate_inundation_raster(sample_telemetry, bbox)
    sop = run_deterministic_fallback_engine(sample_telemetry, inundation, sample_assets)

    summary = sop.to_ics201_summary()
    assert "ICS-201" in summary
    assert "SITUATION SUMMARY" in summary
    assert "PARAMETRIC LIQUIDITY" in summary
    assert "CRITICAL ASSET ACTION MATRIX" in summary
    assert "VERNACULAR EMERGENCY BROADCAST" in summary
