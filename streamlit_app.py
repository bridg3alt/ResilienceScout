"""
ResilienceOS — demo dashboard.

Run:  streamlit run streamlit_app.py
Optional: set GROQ_API_KEY for natural-language copilot answers.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Load .env (e.g. GROQ_API_KEY) into the process environment, if present.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ModuleNotFoundError:
    pass

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from resilienceos.building import Building, WALL_U, ROOF_U, GLAZING, MASS_CLASS
from resilienceos import weather as wx
from resilienceos.hazard import analyze_heatwave, analyze_outage, HI_CAUTION, HI_DANGER
from resilienceos.engine import resilience_score, operational_plan, outage_sequence
from resilienceos.scenarios import compare, budget_optimizer, RETROFITS
from resilienceos.copilot.context import build_context
from resilienceos.copilot.rag import answer as copilot_answer
from resilienceos.copilot.agents import answer_multiagent
from resilienceos.copilot.llm import has_llm
from resilienceos.optimizer import optimize_day
from resilienceos import validation as valid
from resilienceos.report import render_report

st.set_page_config(page_title="ResilienceOS", page_icon="🌡️", layout="wide")

# ---- styling (theme-aware: works in both light and dark) ----------------------
st.markdown("""
<style>
  .block-container{padding-top:1.2rem;max-width:1280px}
  .hero{background:linear-gradient(120deg,#0c4a6e,#0ea5e9);color:#fff;border-radius:16px;
        padding:1.1rem 1.4rem;margin-bottom:1rem}
  .hero h1{color:#fff;margin:0;font-size:1.5rem}
  .hero p{margin:.2rem 0 0;opacity:.92;font-size:.9rem}
  .tile{background:linear-gradient(180deg,#f8fafc,#eef2f7);border:1px solid #dbe3ec;
        border-radius:12px;padding:.7rem .95rem;height:100%}
  .tile .k{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em}
  .tile .v{font-size:1.45rem;font-weight:750;color:#0f172a;line-height:1.15}
  .tile .s{font-size:.72rem;color:#94a3b8}
  .stTabs [data-baseweb="tab"]{font-size:.95rem;padding:.35rem .7rem}
  [data-testid="stMetricValue"]{font-size:1.35rem}
  section[data-testid="stSidebar"] .stButton button{width:100%}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_day(lat, lon):
    fc = wx.fetch_forecast(lat, lon, days=3)
    return wx.hottest_day(fc)


def score_color(s):
    return "#16a34a" if s >= 75 else "#ca8a04" if s >= 50 else "#ea580c" if s >= 30 else "#dc2626"


# ---- sidebar: building onboarding --------------------------------------------
# One-click starting points so a non-technical operator isn't faced with 18 raw fields.
PRESETS = {
    "— Custom —": None,
    "🏫 School block": dict(name="Govt. School Block", area=1800, floors=2, wwr=0.30,
                            wall="brick_plaster", roof="rcc_bare", glaz="single_clear",
                            mass="heavy", occ=400, solar=25.0, batt=20.0, crit=6.0),
    "🏥 Health clinic": dict(name="Primary Health Centre", area=900, floors=2, wwr=0.20,
                             wall="rcc_solid", roof="rcc_bare", glaz="single_clear",
                             mass="heavy", occ=80, solar=15.0, batt=40.0, crit=12.0),
    "🏘️ Community centre": dict(name="Community Centre", area=1200, floors=1, wwr=0.25,
                                wall="aac_block", roof="rcc_tiled", glaz="single_tinted",
                                mass="medium", occ=150, solar=30.0, batt=15.0, crit=4.0),
}
_DEFAULTS = dict(name="Decennial Block", lat=12.9716, lon=77.5946, area=1200, floors=3,
                 wwr=0.25, wall="brick_plaster", roof="rcc_bare", glaz="single_clear",
                 mass="heavy", occ=120, solar=20.0, batt=20.0, crit=5.0, gen=False,
                 o_start=14, o_dur=6)
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def _apply_preset():
    p = PRESETS.get(st.session_state.get("preset"))
    if p:
        for k, v in p.items():
            st.session_state[k] = v


st.sidebar.header("🏢 Building onboarding")
st.sidebar.caption("Minimal inputs — no BMS or sensors required.")
st.sidebar.selectbox("Start from a preset", list(PRESETS), key="preset",
                     on_change=_apply_preset,
                     help="Pick a building type to auto-fill typical values, then tweak.")

st.sidebar.text_input("Building name", key="name")
c1, c2 = st.sidebar.columns(2)
c1.number_input("Latitude", format="%.4f", key="lat")
c2.number_input("Longitude", format="%.4f", key="lon")
st.sidebar.caption("📍 Weather is pulled live from these coordinates (Open-Meteo).")

st.sidebar.subheader("📐 Size & occupancy")
c3, c4 = st.sidebar.columns(2)
c3.number_input("Floor area (m²)", 100, 100000, step=100, key="area")
c4.number_input("Floors", 1, 30, key="floors")
st.sidebar.number_input("Peak occupancy", 1, 5000, key="occ")

with st.sidebar.expander("🧱 Construction (advanced)"):
    st.slider("Window-to-wall ratio", 0.05, 0.6, step=0.05, key="wwr")
    st.selectbox("Wall material", list(WALL_U), key="wall")
    st.selectbox("Roof material", list(ROOF_U), key="roof")
    st.selectbox("Glazing", list(GLAZING), key="glaz")
    st.selectbox("Thermal mass", list(MASS_CLASS), key="mass")
    st.caption("Defaults suit typical Indian public buildings; adjust if you know better.")

st.sidebar.subheader("🔋 Energy resources")
c5, c6 = st.sidebar.columns(2)
c5.number_input("Solar (kWp)", 0.0, 1000.0, step=5.0, key="solar")
c6.number_input("Battery (kWh)", 0.0, 2000.0, step=10.0, key="batt")
st.sidebar.number_input("Critical load (kW)", 0.0, 500.0, step=1.0, key="crit",
                        help="Loads that must stay powered in an outage (e.g. vaccine fridge, lights).")
st.sidebar.checkbox("Diesel generator on site", key="gen")

st.sidebar.subheader("🔌 Outage scenario")
c7, c8 = st.sidebar.columns(2)
c7.slider("Start hour", 0, 23, key="o_start")
c8.slider("Duration (h)", 1, 18, key="o_dur")

ss = st.session_state
name, lat, lon = ss.name, ss.lat, ss.lon
o_start, o_dur = ss.o_start, ss.o_dur
b = Building(
    name=ss.name, latitude=ss.lat, longitude=ss.lon, floor_area_m2=ss.area,
    num_floors=ss.floors, window_to_wall_ratio=ss.wwr, wall_material=ss.wall,
    roof_material=ss.roof, glazing=ss.glaz, mass_class=ss.mass, occupancy_peak=ss.occ,
    solar_kwp=ss.solar, battery_kwh=ss.batt, critical_load_kw=ss.crit, has_generator=ss.gen,
)

# ---- run engine ---------------------------------------------------------------
try:
    day = get_day(lat, lon)
except Exception as e:
    st.error(f"Could not fetch weather from Open-Meteo: {e}")
    st.stop()

hw = analyze_heatwave(b, day, hvac_active=False)     # passive survivability
hw_ac = analyze_heatwave(b, day, hvac_active=True)   # operational (AC on)
out = analyze_outage(b, day, o_start, o_dur)
score = resilience_score(hw, out)
plan = operational_plan(b, day, hw)
seq = outage_sequence(b, out)

# ---- hero + score -------------------------------------------------------------
st.markdown(
    f"<div class='hero'><h1>🌡️ ResilienceOS — {b.name}</h1>"
    f"<p>AI energy-resilience OS for under-instrumented public buildings · "
    f"forecast heatwave {pd.to_datetime(day['time'].iloc[0]).date()} · outdoor peak "
    f"{hw.peak_outdoor:.0f}°C</p></div>", unsafe_allow_html=True)

left, right = st.columns([1, 2])
with left:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score["score"],
        title={"text": f"Resilience — {score['band']}"},
        gauge={"axis": {"range": [0, 100]},
               "bar": {"color": score_color(score["score"])},
               "steps": [{"range": [0, 30], "color": "#fee2e2"},
                         {"range": [30, 50], "color": "#ffedd5"},
                         {"range": [50, 75], "color": "#fef9c3"},
                         {"range": [75, 100], "color": "#dcfce7"}]}))
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=40, b=0))
    st.plotly_chart(fig, width='stretch')
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=11, size=60)

with right:
    cols = st.columns(3)
    tiles = [
        ("Peak indoor (passive)", f"{hw.peak_indoor:.1f}°C"),
        ("Peak heat index", f"{hw.peak_heat_index:.0f}°C"),
        ("Safe occupied hrs", f"{hw.safe_occupancy_hours}/{hw.occupied_hours}"),
        ("Hrs to unsafe (outage)", f"{out.hours_until_unsafe:.0f} h" if out.hours_until_unsafe is not None else "safe"),
        ("Critical-load backup", f"{out.backup_hours:.1f} h"),
        ("AC cooling peak", f"{max(r['cooling_kw'] for r in hw_ac.profile):.0f} kW"),
    ]
    for i, (k, v) in enumerate(tiles):
        cols[i % 3].markdown(f"<div class='tile'><div class='k'>{k}</div><div class='v'>{v}</div></div>",
                             unsafe_allow_html=True)
    st.caption(f"Sub-scores — habitability {score['components']['habitability']}, "
               f"thermal exceedance {score['components']['thermal_exceedance']} "
               f"({hw.exceedance_degh:.0f} °C·h above caution), "
               f"backup {score['components']['backup']}")

st.divider()
tabs = st.tabs(["🌡️ Heatwave", "🔌 Outage", "⚡ Plan", "🛠️ Retrofits",
                "🤖 Copilot", "📏 Validate"])

# ---- heatwave tab -------------------------------------------------------------
with tabs[0]:
    st.caption("How hot the building gets on the forecast heatwave day — with cooling vs "
               "without (passive survivability when the grid is stressed).")
    dfp = pd.DataFrame(hw.profile)
    dfa = pd.DataFrame(hw_ac.profile)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dfp["hour"], y=dfp["t_out"], name="Outdoor", line=dict(color="#94a3b8", dash="dot")))
    fig.add_trace(go.Scatter(x=dfp["hour"], y=dfp["indoor_temp"], name="Indoor (no cooling)", line=dict(color="#dc2626", width=3)))
    fig.add_trace(go.Scatter(x=dfp["hour"], y=dfp["heat_index"], name="Heat index (no cooling)", line=dict(color="#ea580c", dash="dash")))
    fig.add_trace(go.Scatter(x=dfa["hour"], y=dfa["indoor_temp"], name="Indoor (AC on)", line=dict(color="#0ea5e9", width=2)))
    fig.add_hline(y=HI_CAUTION, line=dict(color="#f59e0b"), annotation_text="Caution 32°C")
    fig.add_hline(y=HI_DANGER, line=dict(color="#dc2626"), annotation_text="Danger 39°C")
    fig.update_layout(height=430, xaxis_title="Hour of day", yaxis_title="°C",
                      legend=dict(orientation="h", y=1.12), margin=dict(t=30))
    st.plotly_chart(fig, width='stretch')
    st.info(f"Without cooling, indoor peaks at **{hw.peak_indoor:.1f}°C** "
            f"(heat index {hw.peak_heat_index:.0f}°C) — {hw.hours_above_caution}h above caution, "
            f"{hw.hours_above_danger}h above danger. This is the building's passive survivability "
            f"when the grid is stressed.")

# ---- outage tab ---------------------------------------------------------------
with tabs[1]:
    st.caption("What happens to indoor temperature and how long backup power lasts during a "
               "power cut. Adjust the outage window in the sidebar.")
    dfo = pd.DataFrame(out.profile)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dfo["hour"], y=dfo["indoor_temp"], name="Indoor", line=dict(color="#dc2626", width=3)))
    fig.add_trace(go.Scatter(x=dfo["hour"], y=dfo["heat_index"], name="Heat index", line=dict(color="#ea580c", dash="dash")))
    fig.add_vrect(x0=o_start, x1=o_start + o_dur, fillcolor="#fca5a5", opacity=0.25,
                  annotation_text="OUTAGE", line_width=0)
    fig.add_hline(y=HI_CAUTION, line=dict(color="#f59e0b"))
    fig.update_layout(height=380, xaxis_title="Hour of day", yaxis_title="°C",
                      legend=dict(orientation="h", y=1.12), margin=dict(t=30))
    st.plotly_chart(fig, width='stretch')
    m = st.columns(3)
    m[0].metric("Peak indoor during outage", f"{out.peak_indoor_during:.1f}°C")
    m[1].metric("Hours until unsafe", f"{out.hours_until_unsafe:.0f} h" if out.hours_until_unsafe is not None else "safe")
    m[2].metric("Critical-load backup", f"{out.backup_hours:.1f} h")
    st.subheader("Response sequence")
    st.dataframe(pd.DataFrame(seq), width='stretch', hide_index=True)

# ---- plan tab -----------------------------------------------------------------
with tabs[2]:
    st.caption("What to actually do, hour by hour: a rule-based checklist plus a cost-"
               "optimising battery/solar/cooling schedule from the MILP optimizer.")
    st.subheader("Operational energy schedule — forecast heatwave day")
    for a in plan:
        st.markdown(f"**{a['time']}** &nbsp; `{a['category']}` &nbsp; {a['action']}  \n"
                    f"<span style='color:#64748b'>↳ {a['reason']}</span>", unsafe_allow_html=True)
    # solar curve
    from resilienceos.solar import add_solar
    sdf = add_solar(day.rename(columns={"temp": "temp"}), b.solar_kwp)
    fig = go.Figure(go.Bar(x=sdf["hour"], y=sdf["solar_kw"], marker_color="#f59e0b"))
    fig.update_layout(height=240, title="Estimated rooftop solar generation (kW)",
                      xaxis_title="Hour", margin=dict(t=40))
    st.plotly_chart(fig, width='stretch')

    # ---- MILP optimized dispatch ----------------------------------------------
    st.divider()
    st.subheader("🔧 Optimized energy dispatch (MILP)")
    st.caption("Schedules grid draw, rooftop solar, battery, and cooling to minimise "
               "energy cost + thermal discomfort under real constraints — vs a naive "
               "grid-only, cool-on-demand baseline facing the same outage.")
    opt = optimize_day(b, day, o_start, o_dur)
    if opt.get("schedule") is None:
        st.warning(f"Optimizer unavailable ({opt.get('method')}); showing rule-based plan above. "
                   f"{opt.get('reason','')}")
    else:
        sch = opt["schedule"]
        m = st.columns(3)
        m[0].metric("Energy cost", f"₹{opt['cost_inr']:.0f}",
                    delta=f"−₹{opt['cost_saved_inr']:.0f} vs baseline", delta_color="inverse")
        m[1].metric("Discomfort (°C·h)", f"{opt['comfort_degh']:.1f}",
                    delta=f"−{opt['comfort_gain_degh']:.1f} vs baseline", delta_color="inverse")
        m[2].metric("Baseline cost", f"₹{opt['baseline']['cost_inr']:.0f}")

        efig = go.Figure()
        efig.add_trace(go.Bar(x=sch["hour"], y=sch["pv_used_kw"], name="Solar used", marker_color="#f59e0b"))
        efig.add_trace(go.Bar(x=sch["hour"], y=sch["batt_discharge_kw"], name="Battery discharge", marker_color="#22c55e"))
        efig.add_trace(go.Bar(x=sch["hour"], y=sch["grid_kw"], name="Grid import", marker_color="#94a3b8"))
        efig.add_trace(go.Bar(x=sch["hour"], y=-sch["batt_charge_kw"], name="Battery charge", marker_color="#3b82f6"))
        for h in opt["outage_hours"]:
            efig.add_vrect(x0=h - 0.5, x1=h + 0.5, fillcolor="#fca5a5", opacity=0.18, line_width=0)
        efig.update_layout(barmode="relative", height=300, xaxis_title="Hour",
                           yaxis_title="kW", legend=dict(orientation="h", y=1.15),
                           margin=dict(t=30), title="Dispatch (shaded = outage, islanded)")
        st.plotly_chart(efig, width='stretch')

        tfig = go.Figure()
        tfig.add_trace(go.Scatter(x=sch["hour"], y=sch["indoor_temp"], name="Indoor (optimized)",
                                  line=dict(color="#0ea5e9", width=3)))
        tfig.add_hline(y=opt["comfort_c"], line=dict(color="#16a34a", dash="dash"),
                       annotation_text=f"Comfort {opt['comfort_c']:.0f}°C")
        tfig.update_layout(height=240, xaxis_title="Hour", yaxis_title="°C",
                           margin=dict(t=30), legend=dict(orientation="h", y=1.2))
        st.plotly_chart(tfig, width='stretch')
        st.caption(f"Method: {opt['method']} · linear thermal surrogate "
                   f"(k≈{opt['surrogate_k']:.2f} °C per kWh cooling) of the 5R1C twin — "
                   "genuine optimization, approximate thermal coupling.")

# ---- retrofits tab ------------------------------------------------------------
with tabs[3]:
    st.caption("Which upgrades buy the most resilience per rupee, and what fits your budget. "
               "Drag the slider to set the budget.")
    budget = st.slider("Retrofit budget (₹ lakh)", 0.5, 20.0, 5.0, 0.5) * 100000
    opt = budget_optimizer(b, day, budget, o_start, o_dur)
    rank = pd.DataFrame(opt["ranked"])
    rank_disp = rank.rename(columns={
        "label": "Retrofit", "cost_inr": "Cost ₹", "score_gain": "Score +",
        "gain_per_lakh": "Gain / lakh", "backup_gain_h": "Backup +h", "heat_index_drop": "HI drop °C"})
    st.dataframe(rank_disp[["Retrofit", "Cost ₹", "Score +", "Gain / lakh", "HI drop °C", "Backup +h"]],
                 width='stretch', hide_index=True)
    chosen = [RETROFITS[k]["label"] for k in opt["recommended"]]
    st.success(f"**Recommended within ₹{budget/100000:.1f} lakh:** "
               + (", ".join(chosen) if chosen else "none add resilience within this budget")
               + f"  ·  baseline score {opt['baseline_score']}")

# ---- copilot tab --------------------------------------------------------------
with tabs[4]:
    st.caption("Ask in plain language. Answers are grounded in this building's live simulation "
               "numbers + retrieved guidelines — the copilot never answers from memory.")
    ctx = build_context(b, hw, out, score)
    if not has_llm():
        st.warning("No GROQ_API_KEY set — copilot runs in offline mode (shows grounded evidence). "
                   "Set the key for natural-language answers.")

    EXAMPLES = [
        "What should this building do before tomorrow's heatwave, and why?",
        "Can we stay safely occupied through the outage?",
        "How should we use the rooftop solar and battery?",
        "Which single retrofit helps most?",
    ]
    st.session_state.setdefault("copilot_q", EXAMPLES[0])
    st.write("**Try an example:**")
    ex_cols = st.columns(len(EXAMPLES))
    for i, ex in enumerate(EXAMPLES):
        if ex_cols[i].button(ex, key=f"ex{i}", use_container_width=True):
            st.session_state.copilot_q = ex

    multiagent = st.toggle("Multi-agent reasoning",
                           help="Weather Analyst → Building Physicist → Energy Optimizer → "
                                "Facility Manager, synthesised by a Supervisor agent.")
    q = st.text_input("Ask the copilot", key="copilot_q")
    if st.button("Ask", type="primary"):
        with st.spinner("Retrieving guidelines + reasoning over live simulation…"):
            res = answer_multiagent(q, ctx) if multiagent else copilot_answer(q, ctx)
        if multiagent and res.get("mode") == "multi-agent":
            for role, note in res["agent_notes"].items():
                with st.expander(f"🧑‍🔬 {role}"):
                    st.markdown(note)
            st.markdown("#### 🧭 Supervisor")
        st.markdown(res["answer"])
        st.caption(f"Grounded in: {', '.join(res['sources'])}  ·  engine: {res['llm']}"
                   + (f"  ·  mode: {res.get('mode')}" if multiagent else ""))
    with st.expander("Live simulation context passed to the copilot"):
        st.code(ctx)

# ---- validate tab -------------------------------------------------------------
with tabs[5]:
    st.subheader("📏 Tier-2 validation — twin vs real measurements")
    st.caption("Upload logged indoor-temperature readings from a room over a past date range. "
               "We fetch the matching historical weather, run the twin, quantify the error, and "
               "auto-calibrate the twin's low-data unknowns (thermal mass, infiltration, solar "
               "gain). This is what turns a plausible model into a validated one.")
    with st.expander("🎁 No logger data? Generate a realistic sample CSV to try this"):
        st.caption("Creates plausible logged readings for your location from a recent past "
                   "week (twin + sensor noise, hidden physical properties). Download it, then "
                   "upload it below to watch the calibration recover those properties.")
        if st.button("Generate sample CSV"):
            with st.spinner("Building sample from recent historical weather…"):
                st.session_state.sample_csv = valid.make_sample_csv(b)
        if st.session_state.get("sample_csv"):
            st.download_button("⬇️ Download sample_indoor_temps.csv",
                               data=st.session_state.sample_csv,
                               file_name="sample_indoor_temps.csv", mime="text/csv")

    up = st.file_uploader("Measured indoor temperatures (CSV: a timestamp column + an "
                          "indoor-temp column)", type=["csv"])
    hvac_during = st.checkbox("Room was air-conditioned during logging", value=False,
                              help="Leave off for passive rooms — that's what exercises the physics.")
    if up is None:
        st.info("No file yet. CSV needs a time column (e.g. `time`) and an indoor-temp column "
                "(e.g. `indoor_temp`). Uses the building's lat/lon from the sidebar.")
    else:
        try:
            measured = valid.load_measurements(up)
            st.success(f"Loaded {len(measured)} readings "
                       f"({measured['time'].min():%Y-%m-%d} → {measured['time'].max():%Y-%m-%d}).")
            with st.spinner("Fetching historical weather and calibrating the twin…"):
                cal = valid.calibrate(b, measured, hvac_active=hvac_during)
                wthr = cal["weather"]
                pred0 = valid._predict_with_weather(b, measured, wthr, hvac_during)
                pred1 = valid._predict_with_weather(cal["calibrated_building"], measured, wthr, hvac_during)

            c = st.columns(3)
            c[0].metric("RMSE (uncalibrated)", f"{cal['rmse_before']:.2f} °C")
            c[1].metric("RMSE (calibrated)", f"{cal['rmse_after']:.2f} °C",
                        delta=f"−{cal['rmse_before'] - cal['rmse_after']:.2f} °C", delta_color="inverse")
            c[2].metric("Peak-timing error", f"{cal['metrics_after']['peak_lag_err_h']} h")

            vfig = go.Figure()
            vfig.add_trace(go.Scatter(x=pred0["time"], y=pred0["indoor_measured"],
                                      name="Measured", line=dict(color="#0f172a", width=3)))
            vfig.add_trace(go.Scatter(x=pred0["time"], y=pred0["indoor_temp"],
                                      name="Twin (uncalibrated)", line=dict(color="#f59e0b", dash="dot")))
            vfig.add_trace(go.Scatter(x=pred1["time"], y=pred1["indoor_temp"],
                                      name="Twin (calibrated)", line=dict(color="#0ea5e9", width=2)))
            vfig.update_layout(height=380, xaxis_title="Time", yaxis_title="Indoor °C",
                               legend=dict(orientation="h", y=1.12), margin=dict(t=30))
            st.plotly_chart(vfig, width='stretch')

            p = cal["best_params"]
            st.success(f"**Calibrated physical properties** — thermal capacitance "
                       f"{p['capacitance_override']/1000:.0f} kJ/m²K, infiltration "
                       f"{p['infiltration_ach']:.2f} ACH, solar-gain scale "
                       f"{p['solar_aperture_scale']:.2f}. These are the twin's inferred "
                       "properties for THIS building, recovered from measurements.")
        except Exception as e:
            st.error(f"Could not validate: {e}")

# ---- report download ----------------------------------------------------------
st.divider()
html = render_report(b, hw, out, score, plan, seq)
st.download_button("⬇️ Download resilience report (HTML → print to PDF)",
                   data=html, file_name=f"resilience_report_{b.name.replace(' ', '_')}.html",
                   mime="text/html")
st.caption("Digital twin: 5R1C ISO-13790 (rcbsim, ETH Zürich) · Weather: Open-Meteo · "
           "Early prototype for decision support — not a substitute for on-site engineering.")
