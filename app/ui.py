"""Aegis-Cyclone Command Operations Center (Streamlit UI).

Implements the Dark Ops Command Interface, interactive dual-pane Folium map,
real-time Gemini 3.7 Flash Intelligence Feed, WCAG 2.1 AA color-blind toggles,
Low-Bandwidth Field Mode (<5KB), and browser Web Speech audio synthesis.
"""
import base64
import html
from typing import List, Tuple
import folium
from folium import plugins
import streamlit as st
from streamlit_folium import st_folium

from app.config import settings
from app.core.gee_engine import InundationResult, run_inundation_model
from app.core.gemini_brain import reason_cyclone_impact
from app.core.hazus_engine import estimate_infrastructure_losses, PortfolioLossSummary
from app.core.incois_engine import (
    compute_holland_wind_field,
    generate_tidal_forecast,
    get_active_cyclone_track
)
from app.core.osm_engine import extract_critical_infrastructure
from app.schemas.alerts import AssetBreach, IncidentCommandSOP, ThreatPosture
from app.schemas.assets import AssetType, CriticalAsset
from app.schemas.telemetry import CycloneTelemetry

# Page Configuration
st.set_page_config(
    page_title="Aegis-Cyclone | Command Operations Center",
    page_icon="🌪️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Ops UI Custom Styling (WCAG 2.1 AA Compliant)
DARK_OPS_CSS = """
<style>
    /* Dark Ops Theme Overrides */
    .stApp {
        background-color: #0B1120;
        color: #F8FAFC;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    header, footer { visibility: hidden; }
    
    /* Status Cards */
    .metric-card {
        background: #1E293B;
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid #334155;
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        margin-top: 4px;
    }
    
    /* Badges */
    .badge-red {
        background: #7F1D1D;
        color: #FECACA;
        border: 1px solid #DC2626;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-orange {
        background: #78350F;
        color: #FEF3C7;
        border: 1px solid #D97706;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-yellow {
        background: #713F12;
        color: #FEF9C3;
        border: 1px solid #CA8A04;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    
    /* Cascade Alert Box */
    .cascade-box {
        background: #111827;
        border-left: 4px solid #EF4444;
        padding: 10px 14px;
        margin: 8px 0;
        border-radius: 4px;
        font-size: 0.88rem;
    }
    
    /* Parametric Banner */
    .parametric-banner {
        background: linear-gradient(90deg, #1E1B4B 0%, #172554 100%);
        border: 1px solid #6366F1;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 14px;
    }
</style>
"""
st.markdown(DARK_OPS_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_inundation_model(telemetry_dict: dict) -> InundationResult:
    """Cache hydrodynamic calculations to avoid redundant raster rendering."""
    t = CycloneTelemetry.model_validate(telemetry_dict)
    return run_inundation_model(t)


@st.cache_data(show_spinner=False)
def cached_infrastructure_extraction(sector_name: str) -> List[dict]:
    """Cache critical infrastructure extractions."""
    assets = extract_critical_infrastructure(sector_name)
    return [a.model_dump() for a in assets]


# ==============================================================================
# 1. SIDEBAR CONTROLS (TACTICAL TELEMETRY & ACCESSIBILITY)
# ==============================================================================
with st.sidebar:
    st.image("https://img.shields.io/badge/AEGIS--CYCLONE-OPS%20LEVEL%205-0055FF?style=for-the-badge&logo=target", use_container_width=True)
    st.markdown("### 🎯 Coastal Threat Parameterizer")

    sector_choice = st.selectbox(
        "Coastal Target Sector",
        options=list(settings.COASTAL_SECTORS.keys()),
        index=0,
        help="Select coastal area under active cyclone threat"
    )

    col_p, col_w = st.columns(2)
    with col_p:
        pressure_hpa = st.slider(
            "P_central (hPa)",
            min_value=900.0,
            max_value=1005.0,
            value=940.0,
            step=1.0,
            help="Central barometric pressure at eye"
        )
    with col_w:
        wind_kmh = st.slider(
            "Wind (km/h)",
            min_value=80.0,
            max_value=280.0,
            value=195.0,
            step=5.0,
            help="Maximum sustained surface wind speed"
        )

    col_t, col_e = st.columns(2)
    with col_t:
        tide_m = st.slider(
            "Tide Height (m)",
            min_value=0.0,
            max_value=4.0,
            value=1.5,
            step=0.1,
            help="Astronomical tide at landfall hour"
        )
    with col_e:
        eta_hours = st.slider(
            "Landfall ETA (h)",
            min_value=1.0,
            max_value=48.0,
            value=8.0,
            step=1.0,
            help="Estimated hours until eye reaches coast"
        )

    st.markdown("---")
    st.markdown("### ♿ Accessibility & Field Mode")
    
    color_blind_mode = st.toggle(
        "Color-Blind High-Contrast Mode",
        value=False,
        help="Switches map markers to Wong/Tol deuteranopia-safe palette (Sky Blue / Amber / Vermilion)"
    )

    low_bandwidth_mode = st.toggle(
        "Low-Bandwidth Field Mode (<5KB)",
        value=False,
        help="Drops heavy visual raster and map components for degraded 2G/EDGE field deployment"
    )

    role_persona = st.selectbox(
        "Active Operator Role",
        options=["DISASTER_COMMANDER", "INSURANCE_UNDERWRITER", "FIELD_OPERATOR"],
        index=0
    )


# ==============================================================================
# 2. HYDRODYNAMIC & REASONING PIPELINE EXECUTION
# ==============================================================================
telemetry = CycloneTelemetry(
    storm_id="AGNI-2026-05B",
    storm_name="Cyclone Agni",
    central_pressure_hpa=pressure_hpa,
    max_wind_speed_kmh=wind_kmh,
    astronomical_tide_m=tide_m,
    landfall_eta_hours=eta_hours,
    coastal_sector=sector_choice
)

# Compute or load cached results
inundation = cached_inundation_model(telemetry.model_dump())
raw_assets = cached_infrastructure_extraction(sector_choice)
assets = [CriticalAsset.model_validate(a) for a in raw_assets]

# Execute Multimodal Reasoner (Gemini 3.7 Flash or Deterministic Fallback)
with st.spinner("Executing Gemini 3.7 Flash Spatial Cascade Reasoner..."):
    sop: IncidentCommandSOP = reason_cyclone_impact(telemetry, inundation, assets)


# ==============================================================================
# 3. TOP TACTICAL TELEMETRY KPI BANNER
# ==============================================================================
st.markdown(f"## 🌪️ AEGIS-CYCLONE: {telemetry.storm_name} | Sector: {sector_choice}")

kpi_cols = st.columns(5)
with kpi_cols[0]:
    posture_class = f"badge-{sop.threat_posture.value.lower()}"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Threat Posture</div>
        <div class="metric-value"><span class="{posture_class}">[{sop.threat_posture.value}]</span></div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[1]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Water Surge (TWSE)</div>
        <div class="metric-value" style="color: #38BDF8;">{inundation.twse_m} m</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[2]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Max Winds / Category</div>
        <div class="metric-value" style="color: #FBBF24;">{telemetry.max_wind_speed_kmh} <span style="font-size:0.9rem;">km/h</span></div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[3]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Landfall ETA</div>
        <div class="metric-value" style="color: #F472B6;">{telemetry.landfall_eta_hours} h</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_cols[4]:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Projected Surge Inundation</div>
        <div class="metric-value" style="color: #A78BFA;">{inundation.inundated_area_sqkm} <span style="font-size:0.9rem;">km²</span></div>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 4. CONDITIONAL VIEW: LOW-BANDWIDTH FIELD MODE VS SPLIT-SCREEN OPS
# ==============================================================================
if low_bandwidth_mode:
    st.warning("⚡ **LOW-BANDWIDTH FIELD MODE ACTIVE (<5KB Payload)**: Heavy satellite imagery and interactive maps suspended for degraded 2G/EDGE networks.")
    
    col_field_1, col_field_2 = st.columns(2)
    with col_field_1:
        st.markdown("### 📋 Tactical Incident Command Briefing (ICS-201)")
        st.text_area("Terminal Dispatch Text", value=sop.to_ics201_summary(), height=420)
        
        st.download_button(
            "⬇️ Download ICS-201 Text Dispatch",
            data=sop.to_ics201_summary(),
            file_name=f"ICS201_{telemetry.storm_id}.txt",
            mime="text/plain"
        )
    
    with col_field_2:
        st.markdown("### 📡 OASIS CAP v1.2 Standard Alert XML")
        st.text_area("CAP v1.2 XML Payload", value=sop.cap_alert_xml, height=420)
        
        st.download_button(
            "⬇️ Download OASIS CAP v1.2 XML",
            data=sop.cap_alert_xml,
            file_name=f"CAP_v12_{telemetry.storm_id}.xml",
            mime="application/xml"
        )

else:
    # Standard Full Operations Center View with Modular Tabs
    tab_ops, tab_hazus, tab_sensing, tab_broadcast = st.tabs([
        "🗺️ Geospatial & Cascade Ops",
        "📊 Financial Resilience (FEMA HAZUS-MH)",
        "🌊 Ocean & Atmospheric Sensing (INCOIS / IMD)",
        "📻 Emergency Dispatches & CAP v1.2"
    ])

    # ==========================================================================
    # TAB 1: GEOSPATIAL & CASCADE OPS
    # ==========================================================================
    with tab_ops:
        col_map, col_intel = st.columns([1.1, 0.9])

        # ----------------------------------------------------------------------
        # LEFT COLUMN: SATELLITE MAP & EXPOSURE OVERLAY
        # ----------------------------------------------------------------------
        with col_map:
            st.markdown("### 🗺️ Geospatial Inundation & Asset Vulnerability")

            sector_info = settings.COASTAL_SECTORS.get(sector_choice, settings.COASTAL_SECTORS["Paradip_Odisha"])
            center_lat, center_lon = sector_info["center"]
            min_lat, min_lon, max_lat, max_lon = sector_info["bbox"]

            # Color palette selection (Standard vs Color-Blind Safe)
            if color_blind_mode:
                COLOR_SAFE = "#56B4E9"       # Sky Blue
                COLOR_AT_RISK = "#F0E442"    # Yellow
                COLOR_INUNDATED = "#D55E00"  # Vermilion
            else:
                COLOR_SAFE = "#10B981"       # Green
                COLOR_AT_RISK = "#F59E0B"    # Amber
                COLOR_INUNDATED = "#EF4444"  # Red

            # Initialize Folium Map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=11,
                tiles="CartoDB dark_matter",
                control_scale=True
            )

            # Inundation Raster Overlay
            img_b64 = inundation.image_base64
            data_url = f"data:image/png;base64,{img_b64}"

            folium.raster_layers.ImageOverlay(
                image=data_url,
                bounds=[[min_lat, min_lon], [max_lat, max_lon]],
                opacity=0.65,
                name="Storm Surge Inundation Raster"
            ).add_to(m)

            # Map Asset Breach Lookup
            breach_map = {b.asset_id: b for b in sop.asset_breaches}

            # Vector Asset Markers
            for asset in assets:
                b_info = breach_map.get(asset.asset_id)
                prob = b_info.breach_probability if b_info else 0.0

                if prob >= 0.5:
                    marker_color = COLOR_INUNDATED
                    status_label = "INUNDATION BREACH (>50%)"
                elif prob >= 0.25:
                    marker_color = COLOR_AT_RISK
                    status_label = "AT-RISK / SURGE REACH"
                else:
                    marker_color = COLOR_SAFE
                    status_label = "SAFE (HIGH ELEVATION)"

                popup_html = f"""
                <div style="font-family: sans-serif; font-size: 12px; width: 230px;">
                    <b>{asset.name}</b><br/>
                    <b>Type:</b> {asset.asset_type.value.upper()} | <b>Tier:</b> {asset.criticality.value}<br/>
                    <b>Elevation:</b> {asset.elevation_m}m | <b>TWSE:</b> {inundation.twse_m}m<br/>
                    <b>Status:</b> <span style="color:{marker_color}; font-weight:bold;">{status_label}</span><br/>
                    <b>Breach Prob:</b> {int(prob*100)}%<br/>
                    <b>Cascade:</b> {b_info.cascade_risk if b_info else 'N/A'}<br/>
                    <b>Action:</b> {b_info.mitigation_action if b_info else 'N/A'}
                </div>
                """

                folium.CircleMarker(
                    location=[asset.latitude, asset.longitude],
                    radius=8,
                    color=marker_color,
                    fill=True,
                    fill_color=marker_color,
                    fill_opacity=0.85,
                    weight=2,
                    popup=folium.Popup(popup_html, max_width=260),
                    tooltip=f"{asset.name} ({status_label})"
                ).add_to(m)

            # Render Map in Streamlit
            st_folium(m, width=None, height=520)

            # Transport & Evacuation Status Pill Box
            st.markdown("#### 🛣️ Evacuation Corridor Triage")
            corridor = sop.evacuation_corridor_status
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.markdown(f"**Severed Routes ({len(corridor.severed_routes)}):**")
                for r in corridor.severed_routes:
                    st.markdown(f"🔴 `{r}`")
            with col_c2:
                st.markdown(f"**Open High-Ridge Corridors ({len(corridor.clear_routes)}):**")
                for r in corridor.clear_routes:
                    st.markdown(f"🟢 `{r}`")

        # ----------------------------------------------------------------------
        # RIGHT COLUMN: GEMINI 3.7 FLASH INTELLIGENCE & CASCADE FEED
        # ----------------------------------------------------------------------
        with col_intel:
            st.markdown("### 🧠 Gemini 3.7 Flash Cascade Intelligence")

            # Parametric Insurance Banner
            param = sop.parametric_insurance
            if param.trigger_status:
                st.markdown(f"""
                <div class="parametric-banner">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: #A5B4FC; font-weight:700;">
                        ⚡ Automated Parametric Liquidity Trigger: ACTIVATED
                    </div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #FFFFFF; margin: 4px 0;">
                        Payout Tier: {param.payout_tier_percent}%
                    </div>
                    <div style="font-size: 0.85rem; color: #C7D2FE;">
                        <b>Trigger Metric:</b> {param.triggered_metric}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("💳 Pre-Landfall Disbursement Routing Breakdown"):
                    for wallet, amount in param.disbursement_routing.items():
                        st.write(f"• **{wallet.replace('_', ' ')}:** `{amount}`")
                    if param.settlement_proof_hash:
                        st.caption(f"SHA-256 State Seal: `{param.settlement_proof_hash}`")
            else:
                st.info("ℹ️ Parametric Trigger Standby: Empirical telemetry currently below insurance trigger thresholds.")

            # Visual Cascade Failure Topology Diagram
            st.markdown(f"""
            <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:12px 14px; margin:10px 0;">
                <div style="font-weight:700; color:#38BDF8; font-size:0.8rem; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.06em;">
                    ⚡ Second-Order Cascade Failure Chain
                </div>
                <div style="display:flex; flex-direction:column; gap:6px; font-family:ui-monospace,monospace; font-size:0.8rem;">
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        <span style="background:#7F1D1D; color:#FECACA; padding:2px 7px; border-radius:4px; font-weight:600;">Surge ({inundation.twse_m}m)</span>
                        <span style="color:#94A3B8;">──►</span>
                        <span style="background:#78350F; color:#FEF3C7; padding:2px 7px; border-radius:4px; font-weight:600;">Road Severed</span>
                        <span style="color:#94A3B8;">──►</span>
                        <span style="background:#713F12; color:#FEF9C3; padding:2px 7px; border-radius:4px; font-weight:600;">Fuel Convoy Halted</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-left:14px;">
                        <span style="color:#94A3B8;">└──►</span>
                        <span style="background:#4C1D95; color:#DDD6FE; padding:2px 7px; border-radius:4px; font-weight:600;">220kV Grid Substation Tripped</span>
                        <span style="color:#94A3B8;">──►</span>
                        <span style="background:#831843; color:#FCE7F3; padding:2px 7px; border-radius:4px; font-weight:600;">Hospital Diesel Dies</span>
                        <span style="color:#94A3B8;">──►</span>
                        <span style="background:#500724; border:1px solid #F43F5E; color:#FFE4E6; padding:2px 7px; border-radius:4px; font-weight:700;">ICU O2 Failure</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Chain-of-Thought Rationale Summary
            if sop.chain_of_thought_summary:
                with st.expander("🧐 Deliberate Thinking & Spatial Graph Rationale", expanded=True):
                    st.markdown(f"*{sop.chain_of_thought_summary}*")

            # Critical Asset Breaches Accordion
            st.markdown("#### ⚡ Critical Asset Vulnerability Matrix")
            for b in sop.asset_breaches:
                flag_emoji = "🚨" if b.breach_probability >= 0.5 else "⚠️"
                with st.expander(f"{flag_emoji} {b.asset_name} ({int(b.breach_probability*100)}% Breach Prob)"):
                    st.write(f"• **Elevation:** {b.elevation_m}m | **Time to Cutoff:** {b.time_to_cutoff_hours} hours")
                    st.markdown(f"""
                    <div class="cascade-box">
                        <b>Cascade Risk:</b> {b.cascade_risk}<br/>
                        <b>Mitigation Action:</b> {b.mitigation_action}
                    </div>
                    """, unsafe_allow_html=True)

    # ==========================================================================
    # TAB 2: FINANCIAL RESILIENCE (FEMA HAZUS-MH)
    # ==========================================================================
    with tab_hazus:
        st.markdown("### 📊 Pre-Landfall Infrastructure Loss Estimation (FEMA HAZUS-MH)")
        st.caption("Quantitative physical damage modeling calibrated for Bay of Bengal coastal infrastructure under storm surge immersion.")

        loss_report: PortfolioLossSummary = estimate_infrastructure_losses(assets, inundation.twse_m)

        hl_col1, hl_col2, hl_col3, hl_col4, hl_col5 = st.columns(5)
        with hl_col1:
            st.metric("Total Portfolio Value", f"${loss_report.total_portfolio_value_usd:,.0f}")
        with hl_col2:
            st.metric("Estimated Damage", f"${loss_report.total_estimated_damage_usd:,.0f}")
        with hl_col3:
            st.metric("Portfolio Loss Ratio", f"{loss_report.portfolio_loss_ratio_percent}%")
        with hl_col4:
            st.metric("Max Downtime", f"{loss_report.critical_infrastructure_downtime_days_max} Days")
        with hl_col5:
            st.metric("Severe Damage (>50%)", f"{loss_report.assets_severely_damaged_count} Assets")

        st.markdown("#### 📋 Asset-by-Asset Physical Damage & Downtime Breakdown")
        table_rows = []
        for a in loss_report.asset_loss_breakdown:
            table_rows.append({
                "Asset Name": a.asset_name,
                "Type": a.asset_type.upper(),
                "Ground Elev (m)": a.ground_elevation_m,
                "Water Depth (m)": a.water_depth_above_ground_m,
                "Structural Damage": f"{a.structural_damage_percent}%",
                "Equipment Loss": f"{a.equipment_loss_percent}%",
                "Asset Value": f"${a.baseline_replacement_value_usd:,.0f}",
                "Estimated Loss": f"${a.estimated_damage_usd:,.0f}",
                "Downtime": f"{a.estimated_downtime_days} days",
                "Damage State": a.damage_state
            })
        st.dataframe(table_rows, use_container_width=True)

        st.markdown("#### 🔬 HAZUS-MH Depth-Damage Vulnerability Curves")
        st.markdown("""
        - **Electrical Substations:** High fragility to saltwater immersion. 0.3m depth causes 35% equipment loss; >1.2m causes 90%+ switchgear failure and ~60-120 days downtime.
        - **Trauma Hospitals:** Vulnerable ground floor emergency power generators, diagnostic scanners, and liquid oxygen evaporators.
        - **Arterial Highways:** Embankment scour and asphalt peeling initiated above 0.3m flow depth, severing vehicle passage.
        - **Cyclone Shelters:** Stilted concrete reinforced structures designed to withstand up to 1.8m surge with <20% structural impact.
        """)

    # ==========================================================================
    # TAB 3: MARINE & ATMOSPHERIC SENSING (INCOIS / IMD)
    # ==========================================================================
    with tab_sensing:
        st.markdown("### 🌊 Marine & Atmospheric Sensing Center")
        st.caption("Coupled INCOIS astronomical tidal harmonics and IMD/JTWC parametric cyclone tracking.")

        sens_col1, sens_col2 = st.columns(2)

        with sens_col1:
            st.markdown("#### 🌊 INCOIS Astronomical Tidal Harmonic Forecast")
            tidal_data = generate_tidal_forecast(telemetry.coastal_sector, hours=24)

            st.write(f"**Observatory:** {tidal_data.station_name}")
            st.write(f"**Tidal Regime:** {tidal_data.regime} (Form Factor: `{tidal_data.form_factor}`)")
            st.write(f"**Astronomical Phase:** `{tidal_data.spring_neap_phase}`")

            t_colA, t_colB = st.columns(2)
            with t_colA:
                st.metric("Nearest High Tide", f"+{tidal_data.nearest_high_tide.tide_height_above_msl_m}m MSL", f"{tidal_data.nearest_high_tide.tide_height_above_cd_m}m CD")
            with t_colB:
                st.metric("Nearest Low Tide", f"{tidal_data.nearest_low_tide.tide_height_above_msl_m}m MSL", f"{tidal_data.nearest_low_tide.tide_height_above_cd_m}m CD")

            tide_chart_data = {
                "Hour": [f"+{i}h" for i in range(len(tidal_data.hourly_curve_24h))],
                "Tide Height MSL (m)": [p.tide_height_above_msl_m for p in tidal_data.hourly_curve_24h]
            }
            st.line_chart(tide_chart_data, x="Hour", y="Tide Height MSL (m)")

        with sens_col2:
            st.markdown("#### 🌀 Holland (1980) Parametric Wind Field Profile")
            holland = compute_holland_wind_field(telemetry.central_pressure_hpa, telemetry.radius_max_winds_km)

            st.write(f"**Holland B-Parameter:** `{holland.holland_b_parameter}`")
            st.write(f"**Max Gradient Wind:** `{holland.max_gradient_wind_kmh} km/h` at RMW ({holland.radius_max_winds_km} km)")

            wind_chart_data = {
                "Radius (km)": [p["radius_km"] for p in holland.radial_wind_profile],
                "Wind Speed (km/h)": [p["wind_speed_kmh"] for p in holland.radial_wind_profile]
            }
            st.line_chart(wind_chart_data, x="Radius (km)", y="Wind Speed (km/h)")

        st.markdown("#### 🛰️ Operational IMD / JTWC Track Waypoints & Landfall Guidance")
        track_data = get_active_cyclone_track(telemetry.storm_id, telemetry.coastal_sector, telemetry.landfall_eta_hours)
        st.write(f"**Storm Identification:** `{track_data.storm_name}` | **Translation Speed:** `{track_data.current_translation_speed_kmh} km/h` | **Bearing:** `{track_data.current_bearing_deg}°`")

        waypoint_rows = []
        for wp in track_data.waypoints:
            waypoint_rows.append({
                "Timestamp (UTC)": wp.timestamp,
                "Position": f"{wp.latitude}°N, {wp.longitude}°E",
                "Pressure (hPa)": wp.central_pressure_hpa,
                "Max Wind (km/h)": wp.max_wind_speed_kmh,
                "RMW (km)": wp.radius_max_winds_km,
                "Category": wp.category,
                "Hours to Landfall": f"{wp.hours_to_landfall}h"
            })
        st.dataframe(waypoint_rows, use_container_width=True)

    # ==========================================================================
    # TAB 4: EMERGENCY DISPATCHES & CAP V1.2
    # ==========================================================================
    with tab_broadcast:
        st.markdown("### 📻 Civil Defense Dispatches & Alert Broadcasting")

        # Multilingual Voice Dispatches
        st.markdown("#### 📢 Multilingual Voice & SMS Dispatches")
        vtabs = st.tabs(["🇮🇳 Odia", "🇮🇳 Bengali", "🌐 English"])

        with vtabs[0]:
            odia_text = sop.vernacular_dispatches.odia
            st.write(odia_text)
            odia_escaped = html.escape(odia_text).replace("'", "\\'")
            st.components.v1.html(f"""
            <button onclick="speakOdia()" style="background:#0F766E; color:#FFFFFF; border:none; padding:6px 14px; border-radius:6px; font-weight:600; cursor:pointer;">
                🔊 Listen in Odia (Audio Synthesis)
            </button>
            <script>
            function speakOdia() {{
                if ('speechSynthesis' in window) {{
                    window.speechSynthesis.cancel();
                    var msg = new SpeechSynthesisUtterance('{odia_escaped}');
                    msg.lang = 'or-IN';
                    window.speechSynthesis.speak(msg);
                }} else {{
                    alert('Web Speech API not supported in this browser.');
                }}
            }}
            </script>
            """, height=45)

        with vtabs[1]:
            bengali_text = sop.vernacular_dispatches.bengali
            st.write(bengali_text)
            bengali_escaped = html.escape(bengali_text).replace("'", "\\'")
            st.components.v1.html(f"""
            <button onclick="speakBengali()" style="background:#0F766E; color:#FFFFFF; border:none; padding:6px 14px; border-radius:6px; font-weight:600; cursor:pointer;">
                🔊 Listen in Bengali (Audio Synthesis)
            </button>
            <script>
            function speakBengali() {{
                if ('speechSynthesis' in window) {{
                    window.speechSynthesis.cancel();
                    var msg = new SpeechSynthesisUtterance('{bengali_escaped}');
                    msg.lang = 'bn-IN';
                    window.speechSynthesis.speak(msg);
                }} else {{
                    alert('Web Speech API not supported in this browser.');
                }}
            }}
            </script>
            """, height=45)

        with vtabs[2]:
            eng_text = sop.vernacular_dispatches.english
            st.write(eng_text)
            eng_escaped = html.escape(eng_text).replace("'", "\\'")
            st.components.v1.html(f"""
            <button onclick="speakEnglish()" style="background:#0F766E; color:#FFFFFF; border:none; padding:6px 14px; border-radius:6px; font-weight:600; cursor:pointer;">
                🔊 Listen in English (Audio Synthesis)
            </button>
            <script>
            function speakEnglish() {{
                if ('speechSynthesis' in window) {{
                    window.speechSynthesis.cancel();
                    var msg = new SpeechSynthesisUtterance('{eng_escaped}');
                    msg.lang = 'en-IN';
                    window.speechSynthesis.speak(msg);
                }} else {{
                    alert('Web Speech API not supported in this browser.');
                }}
            }}
            </script>
            """, height=45)

        st.divider()

        bcol1, bcol2 = st.columns(2)
        with bcol1:
            st.markdown("#### 📋 Tactical Incident Command Briefing (ICS-201)")
            st.text_area("ICS-201 Terminal Briefing (<5KB)", value=sop.to_ics201_summary(), height=320)
            st.download_button(
                "⬇️ Download ICS-201 Text Dispatch",
                data=sop.to_ics201_summary(),
                file_name=f"ICS201_{telemetry.storm_id}.txt",
                mime="text/plain"
            )

        with bcol2:
            st.markdown("#### 📡 OASIS CAP v1.2 Standard Alert XML")
            st.text_area("CAP v1.2 XML Document", value=sop.cap_alert_xml, height=320)
            st.download_button(
                "⬇️ Download OASIS CAP v1.2 XML",
                data=sop.cap_alert_xml,
                file_name=f"CAP_v12_{telemetry.storm_id}.xml",
                mime="application/xml"
            )

