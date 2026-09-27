"""Alerts and Incident Command Schemas (OASIS CAP v1.2 and ICS-201).

Defines the core Pydantic V2 response schema for the Gemini 3.7 Flash
multimodal reasoner and deterministic fallback engine.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field


class ThreatPosture(str, Enum):
    RED = "RED"       # Imminent inundation of Tier-1 life-safety or energy backbone (<6h)
    ORANGE = "ORANGE" # Moderate breach probability; anticipatory evacuations active (6-18h)
    YELLOW = "YELLOW" # Pre-landfall surveillance; peripheral storm surge hazard (>18h)


class AssetBreach(BaseModel):
    """Detailed vulnerability and breach forecast for an individual asset."""
    asset_id: str = Field(..., description="Unique asset identifier")
    asset_name: str = Field(..., description="Human-readable asset label")
    elevation_m: float = Field(..., description="Ground elevation of asset")
    breach_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calculated probability of surge penetration over elevation"
    )
    time_to_cutoff_hours: float = Field(
        ...,
        description="Estimated hours until water surface overtakes access or asset perimeter"
    )
    cascade_risk: str = Field(
        ...,
        description="Secondary and tertiary system cascade implications (power/health/transport)"
    )
    mitigation_action: str = Field(
        ...,
        description="Prescriptive tactical countermeasure for Incident Command"
    )


class Waypoint(BaseModel):
    """Geographic detour or alternate evacuation node."""
    name: str
    latitude: float
    longitude: float
    advisory: str


class EvacuationCorridorStatus(BaseModel):
    """Arterial transport and evacuation corridor status."""
    severed_routes: List[str] = Field(
        default_factory=list,
        description="Highways or bridges compromised by storm surge cutoffs"
    )
    clear_routes: List[str] = Field(
        default_factory=list,
        description="High-elevation alternate corridors verified safe for transit"
    )
    alternate_waypoints: List[Waypoint] = Field(
        default_factory=list,
        description="List of vetted navigation waypoints for evacuation convoys"
    )


class ParametricInsuranceTrigger(BaseModel):
    """Parametric smart-contract disaster liquidity trigger status."""
    trigger_status: bool = Field(
        ...,
        description="True if empirical atmospheric telemetry breaches pre-agreed contract tiers"
    )
    triggered_metric: str = Field(
        ...,
        description="Primary telemetry metric causing the trigger event"
    )
    payout_tier_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Disbursement tier: 100%, 50%, or 20%"
    )
    disbursement_routing: Dict[str, str] = Field(
        default_factory=dict,
        description="Designated public relief wallets and agencies mapped to allocated USD/INR values"
    )
    settlement_proof_hash: Optional[str] = Field(
        default=None,
        description="Cryptographic SHA-256 state seal of the parametric execution"
    )


class VernacularDispatches(BaseModel):
    """Localized, zero-jargon public emergency advisories in regional tongues."""
    odia: str = Field(..., description="Emergency advisory in Odia script")
    bengali: str = Field(..., description="Emergency advisory in Bengali script")
    english: str = Field(..., description="Tactical advisory in Plain English")


class IncidentCommandSOP(BaseModel):
    """Comprehensive Incident Command System (ICS-201) operational briefing.

    Enforced as response_schema on Gemini 3.7 Flash structured generation.
    """
    threat_posture: ThreatPosture = Field(
        ...,
        description="Overall regional threat posture classification"
    )
    asset_breaches: List[AssetBreach] = Field(
        default_factory=list,
        description="Evaluated breaches across all monitored infrastructure"
    )
    evacuation_corridor_status: EvacuationCorridorStatus = Field(
        ...,
        description="Transport network readiness and corridor status"
    )
    parametric_insurance: ParametricInsuranceTrigger = Field(
        ...,
        description="Automated parametric liquidity assessment"
    )
    cap_alert_xml: str = Field(
        ...,
        description="Complete OASIS Common Alerting Protocol (CAP v1.2) XML payload"
    )
    vernacular_dispatches: VernacularDispatches = Field(
        ...,
        description="Targeted public broadcasts in Odia, Bengali, and English"
    )
    chain_of_thought_summary: Optional[str] = Field(
        default=None,
        description="High-level summary of the spatial cascade deductive reasoning"
    )

    def to_ics201_summary(self, max_display_assets: int = 10) -> str:
        """Format an operational ICS-201 Incident Briefing document.

        Prioritizes high-risk breached assets and limits display count to ensure
        the payload strictly adheres to low-bandwidth 5KB transmission budgets over 2G/EDGE.
        """
        breached_count = sum(1 for b in self.asset_breaches if b.breach_probability >= 0.5)
        severed = list(dict.fromkeys(self.evacuation_corridor_status.severed_routes))[:5]
        clear = list(dict.fromkeys(self.evacuation_corridor_status.clear_routes))[:5]

        # Prioritize highest breach probability assets
        sorted_breaches = sorted(self.asset_breaches, key=lambda x: x.breach_probability, reverse=True)[:max_display_assets]

        lines = [
            "==================================================================",
            f"   AEGIS-CYCLONE INCIDENT COMMAND BRIEFING (ICS-201)   ",
            f"   POSTURE: [{self.threat_posture.value}] | GENERATED: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
            "==================================================================",
            "",
            f"1. SITUATION SUMMARY:",
            f"   Critical Assets Monitored: {len(self.asset_breaches)}",
            f"   Assets at High Breach Risk: {breached_count}",
            f"   Severed Corridors: {', '.join(severed) or 'None'}",
            f"   Open Arteries: {', '.join(clear) or 'None'}",
            "",
            "2. PARAMETRIC LIQUIDITY TRIGGER:",
            f"   Triggered: {'YES' if self.parametric_insurance.trigger_status else 'NO'}",
            f"   Payout Tier: {self.parametric_insurance.payout_tier_percent}%",
            f"   Metric: {self.parametric_insurance.triggered_metric}",
            "",
            f"3. CRITICAL ASSET ACTION MATRIX (TOP {len(sorted_breaches)} HIGH-PRIORITY):"
        ]
        for b in sorted_breaches:
            flag = "[CRITICAL BREACH]" if b.breach_probability >= 0.5 else "[MONITORED]"
            lines.append(f"   {flag} {b.asset_name} (Elev: {b.elevation_m}m | Prob: {int(b.breach_probability*100)}% | Cutoff: {b.time_to_cutoff_hours}h)")
            lines.append(f"      -> Cascade: {b.cascade_risk}")
            lines.append(f"      -> Action:  {b.mitigation_action}")
        lines.append("")
        lines.append("4. VERNACULAR EMERGENCY BROADCAST (ODIA):")
        lines.append(f"   {self.vernacular_dispatches.odia}")
        lines.append("")
        lines.append("==================================================================")
        return "\n".join(lines)


def generate_oasis_cap_v12(
    sender: str,
    event: str,
    urgency: str,
    severity: str,
    certainty: str,
    headline: str,
    description: str,
    instruction: str,
    area_desc: str,
    polygon_coords: str = ""
) -> str:
    """Construct an OASIS CAP v1.2 compliant XML string."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    identifier = f"AEGIS-CAP-{int(datetime.now(timezone.utc).timestamp())}"

    root = ET.Element("alert", xmlns="urn:oasis:names:tc:emergency:cap:1.2")
    ET.SubElement(root, "identifier").text = identifier
    ET.SubElement(root, "sender").text = sender
    ET.SubElement(root, "sent").text = now_iso
    ET.SubElement(root, "status").text = "Actual"
    ET.SubElement(root, "msgType").text = "Alert"
    ET.SubElement(root, "scope").text = "Public"

    info = ET.SubElement(root, "info")
    ET.SubElement(info, "language").text = "en-US"
    ET.SubElement(info, "category").text = "Met"
    ET.SubElement(info, "event").text = event
    ET.SubElement(info, "urgency").text = urgency
    ET.SubElement(info, "severity").text = severity
    ET.SubElement(info, "certainty").text = certainty
    ET.SubElement(info, "headline").text = headline
    ET.SubElement(info, "description").text = description
    ET.SubElement(info, "instruction").text = instruction

    area = ET.SubElement(info, "area")
    ET.SubElement(area, "areaDesc").text = area_desc
    if polygon_coords:
        ET.SubElement(area, "polygon").text = polygon_coords

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
