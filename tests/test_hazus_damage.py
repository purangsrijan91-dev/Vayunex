"""Automated Test Suite for FEMA HAZUS-MH Coastal Depth-Damage Engine."""
import pytest
from app.core.hazus_engine import (
    compute_hazus_damage_curve,
    estimate_infrastructure_losses,
    PortfolioLossSummary,
    AssetLossEstimate
)
from app.schemas.assets import AssetType, CriticalAsset, CriticalityTier


def test_zero_water_depth_damage():
    """Verify zero damage when water level is below ground elevation."""
    for asset_type in [AssetType.HOSPITAL, AssetType.SUBSTATION, AssetType.HIGHWAY, AssetType.PUMP_STATION, AssetType.SHELTER]:
        struct_pct, equip_pct, downtime, state = compute_hazus_damage_curve(asset_type, 0.0)
        assert struct_pct == 0.0
        assert equip_pct == 0.0
        assert downtime == 0
        assert state == "NONE"


def test_substation_saltwater_sensitivity():
    """Verify substation switchgear incurs severe damage at moderate saltwater immersion."""
    # At 0.5m depth, substation should be MODERATE damage state with significant equipment loss
    struct_pct, equip_pct, downtime, state = compute_hazus_damage_curve(AssetType.SUBSTATION, 0.5)
    assert struct_pct == 45.0
    assert equip_pct == 65.0
    assert downtime == 21
    assert state == "MODERATE"

    # At 2.0m depth, complete substation failure
    struct_pct, equip_pct, downtime, state = compute_hazus_damage_curve(AssetType.SUBSTATION, 2.0)
    assert struct_pct == 95.0
    assert equip_pct == 100.0
    assert downtime == 120
    assert state == "COMPLETE"


def test_hospital_progressive_damage():
    """Verify hospital depth-damage curve scales appropriately with immersion."""
    # 0.2m depth: slight basement/ground infiltration
    s1, e1, d1, st1 = compute_hazus_damage_curve(AssetType.HOSPITAL, 0.2)
    assert st1 == "SLIGHT"
    assert s1 == 8.0
    assert d1 == 3

    # 1.5m depth: extensive damage to ground floor diagnostic and generator equipment
    s2, e2, d2, st2 = compute_hazus_damage_curve(AssetType.HOSPITAL, 1.5)
    assert st2 == "EXTENSIVE"
    assert s2 == 55.0
    assert e2 == 75.0
    assert d2 == 45


def test_cyclone_shelter_resilience():
    """Verify engineered cyclone shelters demonstrate higher threshold tolerance."""
    # Shelters should withstand up to 0.8m with minimal structural loss
    s, e, d, st = compute_hazus_damage_curve(AssetType.SHELTER, 0.6)
    assert s == 4.0
    assert st == "SLIGHT"


def test_portfolio_loss_summary_calculation(sample_assets):
    """Verify aggregate portfolio valuation, loss estimation, and downtime."""
    # Assets elevations: HOSP_01 (2.2m), SUBST_01 (1.8m), HWY_01 (2.0m)
    # With TWSE = 3.5m:
    # HOSP depth = 1.3m
    # SUBST depth = 1.7m (Extreme damage)
    # HWY depth = 1.5m (Extensive damage)
    twse_m = 3.5
    summary: PortfolioLossSummary = estimate_infrastructure_losses(sample_assets, twse_m)

    assert summary.total_assets_evaluated == len(sample_assets)
    assert summary.total_portfolio_value_usd > 0.0
    assert summary.total_estimated_damage_usd > 0.0
    assert 0.0 <= summary.portfolio_loss_ratio_percent <= 100.0
    assert summary.assets_severely_damaged_count >= 1
    assert summary.critical_infrastructure_downtime_days_max > 0
    assert len(summary.asset_loss_breakdown) == len(sample_assets)

    # Substation should be at complete damage with high downtime
    subst_loss = next(a for a in summary.asset_loss_breakdown if a.asset_id == "SUBST_01")
    assert subst_loss.damage_state == "COMPLETE"
    assert subst_loss.estimated_downtime_days == 120
