"""HAZUS-MH Inundation Depth-Damage Matrix & Infrastructure Loss Engine.

Implements FEMA HAZUS-MH stage-damage curves per critical infrastructure class
(Hospitals, Substations, Arterial Highways, Drainage Pumps, Cyclone Shelters)
to compute quantitative physical damage percentages, replacement losses in USD/INR,
and estimated downtime days for pre-landfall financial resilience modeling.
"""
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.schemas.assets import AssetType, CriticalAsset, CriticalityTier


class AssetLossEstimate(BaseModel):
    """Detailed financial loss and structural damage prediction for an individual asset."""
    asset_id: str
    asset_name: str
    asset_type: str
    ground_elevation_m: float
    water_depth_above_ground_m: float
    structural_damage_percent: float
    equipment_loss_percent: float
    baseline_replacement_value_usd: float
    estimated_damage_usd: float
    estimated_downtime_days: int
    damage_state: str  # NONE, SLIGHT, MODERATE, EXTENSIVE, COMPLETE


class PortfolioLossSummary(BaseModel):
    """Aggregate financial and structural exposure report across all monitored assets."""
    total_assets_evaluated: int
    total_portfolio_value_usd: float
    total_estimated_damage_usd: float
    portfolio_loss_ratio_percent: float
    assets_severely_damaged_count: int  # Damage > 50%
    critical_infrastructure_downtime_days_max: int
    hazus_methodology: str = "FEMA HAZUS-MH Coastal Flood Stage-Damage Function (Calibrated for Indian Coastal Norms)"
    asset_loss_breakdown: List[AssetLossEstimate]


# Baseline capital valuation (replacement cost in USD) by asset type and tier
ASSET_VALUATION_MAP: Dict[Tuple[AssetType, CriticalityTier], float] = {
    (AssetType.HOSPITAL, CriticalityTier.TIER_1): 25_000_000.0,   # Super-specialty regional trauma hospital
    (AssetType.HOSPITAL, CriticalityTier.TIER_2): 10_000_000.0,   # Sub-divisional hospital / clinic
    (AssetType.HOSPITAL, CriticalityTier.TIER_3): 3_000_000.0,    # Primary health center
    (AssetType.SUBSTATION, CriticalityTier.TIER_1): 18_000_000.0, # 220/132kV primary transmission grid
    (AssetType.SUBSTATION, CriticalityTier.TIER_2): 7_500_000.0,  # 33/11kV industrial feeder
    (AssetType.SUBSTATION, CriticalityTier.TIER_3): 2_500_000.0,  # Local distribution substation
    (AssetType.HIGHWAY, CriticalityTier.TIER_1): 12_000_000.0,    # 4-lane arterial coastal highway (per 10km)
    (AssetType.HIGHWAY, CriticalityTier.TIER_2): 5_000_000.0,     # 2-lane state highway bypass
    (AssetType.HIGHWAY, CriticalityTier.TIER_3): 2_000_000.0,     # Rural connecting corridor
    (AssetType.PUMP_STATION, CriticalityTier.TIER_1): 6_000_000.0,# High-capacity municipal storm drainage
    (AssetType.PUMP_STATION, CriticalityTier.TIER_2): 2_500_000.0,
    (AssetType.SHELTER, CriticalityTier.TIER_1): 2_500_000.0,     # Multi-purpose cyclone shelter
    (AssetType.SHELTER, CriticalityTier.TIER_2): 1_200_000.0
}


def compute_hazus_damage_curve(asset_type: AssetType, depth_m: float) -> Tuple[float, float, int, str]:
    """Calculate structural damage %, equipment loss %, downtime (days), and damage state.

    Curves derived from FEMA HAZUS-MH Coastal Flood Technical Manual.
    """
    if depth_m <= 0.0:
        return 0.0, 0.0, 0, "NONE"

    if asset_type == AssetType.SUBSTATION:
        # Electrical switchgear is hyper-sensitive to saltwater inundation
        if depth_m <= 0.3:
            return 20.0, 35.0, 7, "SLIGHT"
        elif depth_m <= 0.6:
            return 45.0, 65.0, 21, "MODERATE"
        elif depth_m <= 1.2:
            return 75.0, 90.0, 60, "EXTENSIVE"
        else:
            return 95.0, 100.0, 120, "COMPLETE"

    elif asset_type == AssetType.HOSPITAL:
        # Ground floor ICU, emergency power generators, diagnostics
        if depth_m <= 0.3:
            return 8.0, 15.0, 3, "SLIGHT"
        elif depth_m <= 0.8:
            return 25.0, 45.0, 14, "MODERATE"
        elif depth_m <= 1.8:
            return 55.0, 75.0, 45, "EXTENSIVE"
        else:
            return 80.0, 95.0, 90, "COMPLETE"

    elif asset_type == AssetType.HIGHWAY:
        # Embankment scour and asphalt peeling
        if depth_m <= 0.3:
            return 10.0, 0.0, 2, "SLIGHT"
        elif depth_m <= 0.8:
            return 35.0, 0.0, 7, "MODERATE"
        elif depth_m <= 1.5:
            return 70.0, 0.0, 28, "EXTENSIVE"
        else:
            return 90.0, 0.0, 60, "COMPLETE"

    elif asset_type == AssetType.PUMP_STATION:
        # Submersion of pump drive motors and gravity gates
        if depth_m <= 0.4:
            return 15.0, 25.0, 5, "SLIGHT"
        elif depth_m <= 1.0:
            return 50.0, 70.0, 25, "MODERATE"
        else:
            return 85.0, 95.0, 75, "COMPLETE"

    else:  # Shelters (Engineered for elevated surge survival)
        if depth_m <= 0.8:
            return 4.0, 5.0, 1, "SLIGHT"
        elif depth_m <= 1.8:
            return 18.0, 25.0, 7, "MODERATE"
        else:
            return 50.0, 60.0, 30, "EXTENSIVE"


def estimate_infrastructure_losses(
    assets: List[CriticalAsset],
    twse_m: float
) -> PortfolioLossSummary:
    """Generate comprehensive asset loss estimation report based on HAZUS-MH functions."""
    estimates: List[AssetLossEstimate] = []
    total_val = 0.0
    total_dmg = 0.0
    severely_damaged = 0
    max_downtime = 0

    for a in assets:
        water_depth = max(0.0, round(twse_m - a.elevation_m, 2))
        struct_pct, equip_pct, downtime, state = compute_hazus_damage_curve(a.asset_type, water_depth)

        # Baseline valuation
        val = ASSET_VALUATION_MAP.get(
            (a.asset_type, a.criticality),
            5_000_000.0  # Default $5M
        )

        # Weighted loss: 60% structure, 40% equipment/contents
        composite_pct = (0.6 * struct_pct) + (0.4 * equip_pct)
        dmg_usd = round(val * (composite_pct / 100.0), 2)

        total_val += val
        total_dmg += dmg_usd
        if composite_pct >= 50.0:
            severely_damaged += 1
        if downtime > max_downtime:
            max_downtime = downtime

        estimates.append(AssetLossEstimate(
            asset_id=a.asset_id,
            asset_name=a.name,
            asset_type=a.asset_type.value,
            ground_elevation_m=a.elevation_m,
            water_depth_above_ground_m=water_depth,
            structural_damage_percent=struct_pct,
            equipment_loss_percent=equip_pct,
            baseline_replacement_value_usd=val,
            estimated_damage_usd=dmg_usd,
            estimated_downtime_days=downtime,
            damage_state=state
        ))

    loss_ratio = round((total_dmg / max(1.0, total_val)) * 100.0, 2)

    return PortfolioLossSummary(
        total_assets_evaluated=len(assets),
        total_portfolio_value_usd=round(total_val, 2),
        total_estimated_damage_usd=round(total_dmg, 2),
        portfolio_loss_ratio_percent=loss_ratio,
        assets_severely_damaged_count=severely_damaged,
        critical_infrastructure_downtime_days_max=max_downtime,
        asset_loss_breakdown=estimates
    )
