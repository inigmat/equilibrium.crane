"""
app.py — Streamlit application "Tower Crane Schedule Optimisation"

Run:
    streamlit run app.py
"""

import streamlit as st

from solver import Lift, solve, run_baselines
from data_gen import generate_lifts, DEMO_LIFTS
from ui import (
    APP_CSS,
    render_sidebar,
    manual_input_lifts,
    render_lifts_table,
    render_tab_dashboard,
    render_tab_overview,
    render_tab_schedule,
    render_tab_performance,
    render_tab_details,
    render_tab_model,
)

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Crane Schedule Optimiser",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(APP_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.markdown("""
    <div class="app-title">
      <h1>🏗️ Tower Crane Schedule Optimiser</h1>
      <p>CP-SAT · OR-Tools · minimise crane idle & brigade wait</p>
    </div>
    """, unsafe_allow_html=True)

    params = render_sidebar()

    # ── Get lifts ───────────────────────────────────────────────────────────
    shift = params["shift"]

    if params["data_mode"] == "Demo dataset (fixed)":
        lifts = [Lift(**vars(lft)) for lft in DEMO_LIFTS]
    elif params["data_mode"] == "Generator (random)":
        lifts = generate_lifts(
            scenario=params["scenario"],
            n_lifts=params["n_lifts"],
            shift=shift,
            q_max=params["q_max"],
            seed=params["seed"],
            density=params["density"],
        )
    else:  # manual entry
        lifts = manual_input_lifts(shift)

    if not lifts:
        st.warning("⚠️  No lifts. Add data or select another mode.")
        return

    # ── Lift table ──────────────────────────────────────────────────────────
    if params.get("show_raw", True):
        with st.expander(f"📋 Lift requests ({len(lifts)})", expanded=False):
            render_lifts_table(lifts)

    # ── Run button ──────────────────────────────────────────────────────────
    st.markdown("---")
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        run_clicked = st.button(
            "🚀 Run optimisation", type="primary", width="stretch")
    with col_info:
        st.info(
            f"**Model:** {len(lifts)} lifts  ·  "
            f"{2*len(lifts)+1 + len(lifts)*(len(lifts)-1)//2} variables  ·  "
            f"Limit: {params['time_limit']} s  ·  "
            f"MIP gap: {params['mip_gap']:.1%}")

    # ── Session state ───────────────────────────────────────────────────────
    if "milp_result" not in st.session_state:
        st.session_state.milp_result = None
    if "baselines" not in st.session_state:
        st.session_state.baselines = None

    if run_clicked:
        with st.spinner("⚙️  Solving CP-SAT..."):
            milp_result = solve(
                lifts,
                shift=shift,
                alpha=params["alpha"],
                beta=params["beta"],
                time_limit=params["time_limit"],
                mip_gap=params["mip_gap"],
            )
        baselines = run_baselines(
            lifts, shift=shift,
            alpha=params["alpha"], beta=params["beta"])
        st.session_state.milp_result = milp_result
        st.session_state.baselines = baselines

    milp_result = st.session_state.milp_result
    baselines = st.session_state.baselines

    if milp_result is None:
        st.markdown("""
        <div style="text-align:center; padding:3rem; color:#6B7280;">
          <div style="font-size:3rem;">🏗️</div>
          <h3>Configure parameters and click "Run optimisation"</h3>
          <p>The solver will find an optimal schedule in seconds</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Solver status ───────────────────────────────────────────────────────
    # CP-SAT status codes: 0=UNKNOWN, 1=MODEL_INVALID, 2=FEASIBLE,
    # 3=INFEASIBLE, 4=OPTIMAL
    status_map = {
        4: ("✅ Globally optimal solution found", "solver-ok"),
        2: ("✅ Feasible solution within MIP gap", "solver-ok"),
        3: ("❌ Problem is infeasible", "solver-err"),
        0: ("⚠️  No solution found (timeout)", "solver-warn"),
        1: ("⚠️  Invalid model", "solver-warn"),
    }
    smsg, scls = status_map.get(
        milp_result.status, (f"Status {milp_result.status}", "solver-warn"))
    st.markdown(
        f'<span class="{scls}">'
        f'{smsg}  ·  Time: {milp_result.elapsed:.1f} s</span>',
        unsafe_allow_html=True)

    if not milp_result.schedule:
        st.error("Empty schedule. Try increasing the time limit or MIP gap.")
        return

    fifo = baselines.get("FIFO") if baselines else milp_result

    # ── Tabs ────────────────────────────────────────────────────────────────
    show_advanced = params.get("show_advanced", False)

    if show_advanced:
        tab_labels = [
            "🏗️ Dashboard", "📊 Overview", "📅 Schedule",
            "📈 Performance", "🔬 Details", "📐 Model",
        ]
        tabs = st.tabs(tab_labels)
        with tabs[0]:
            render_tab_dashboard(milp_result, shift)
        with tabs[1]:
            render_tab_overview(milp_result, fifo, baselines, shift)
        with tabs[2]:
            render_tab_schedule(
                milp_result, baselines,
                params["show_baselines"], shift)
        with tabs[3]:
            render_tab_performance(milp_result, baselines, lifts, shift)
        with tabs[4]:
            render_tab_details(milp_result, shift)
        with tabs[5]:
            render_tab_model(milp_result, lifts, params)
    else:
        tabs = st.tabs(["🏗️ Dashboard", "📅 Schedule"])
        with tabs[0]:
            render_tab_dashboard(milp_result, shift)
        with tabs[1]:
            render_tab_schedule(
                milp_result, baselines,
                params["show_baselines"], shift)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
