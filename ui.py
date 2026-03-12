"""
ui.py — Streamlit UI components for the crane scheduler app.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
from typing import List

from solver import Lift, SolverResult
from data_gen import BRIGADE_CATALOG
from charts import (
    gantt_chart, simple_gantt, comparison_chart, waterfall_chart,
    crane_timeline, brigade_chart, radar_chart, idle_distribution,
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

APP_CSS = """
<style>
  html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", Arial, sans-serif; }

  .app-title {
    background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
    color: white; padding: 1.4rem 2rem; border-radius: 12px;
    margin-bottom: 1.2rem;
  }
  .app-title h1 { margin: 0; font-size: 1.7rem; font-weight: 700; }
  .app-title p  { margin: 0.3rem 0 0; font-size: 0.95rem; opacity: 0.85; }

  .kpi-card {
    background: white; border-radius: 10px; padding: 1rem 1.2rem;
    border: 1px solid #E5E7EB; box-shadow: 0 1px 4px rgba(0,0,0,.06);
    text-align: center;
  }
  .kpi-card .label { font-size: 0.78rem; color: #6B7280; font-weight: 500;
                     text-transform: uppercase; letter-spacing: .05em; }
  .kpi-card .value { font-size: 2rem; font-weight: 700; color: #111827;
                     line-height: 1.1; margin: .25rem 0; }
  .kpi-card .delta { font-size: 0.85rem; font-weight: 600; }
  .delta-good { color: #16A34A; }
  .delta-bad  { color: #DC2626; }
  .delta-neu  { color: #6B7280; }

  .section-header {
    font-size: 1.1rem; font-weight: 700; color: #1E3A5F;
    margin: 1.5rem 0 0.7rem; padding-bottom: 0.35rem;
    border-bottom: 2px solid #2563EB;
  }

  .lift-table th { background: #F8FAFC; font-weight: 600; }

  .solver-ok   { background:#DCFCE7; color:#15803D; padding:.5rem 1rem;
                 border-radius:8px; font-weight:600; display:inline-block; }
  .solver-warn { background:#FEF9C3; color:#854D0E; padding:.5rem 1rem;
                 border-radius:8px; font-weight:600; display:inline-block; }
  .solver-err  { background:#FEE2E2; color:#991B1B; padding:.5rem 1rem;
                 border-radius:8px; font-weight:600; display:inline-block; }

  section[data-testid="stSidebar"] { background: #F8FAFC; }

  .pill {
    display:inline-block; padding:2px 8px; border-radius:999px;
    font-size:0.75rem; font-weight:600; color:white;
  }
  .p5{background:#DC2626;} .p4{background:#EA580C;}
  .p3{background:#CA8A04;} .p2{background:#16A34A;} .p1{background:#6B7280;}

  div[data-testid="stHorizontalBlock"] > div { gap: 0.8rem; }
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────


def fmt_time(minutes: float) -> str:
    m = max(0, int(round(minutes)))
    return f"{8 + m//60:02d}:{m%60:02d}"


def priority_pill(p: int) -> str:
    labels = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}
    return f'<span class="pill p{p}">{labels.get(p,"?")}</span>'


def kpi_card(
        label: str,
        value: str,
        delta: str = "",
        good: bool = True) -> str:
    delta_cls = "delta-good" if (
        good and delta) else (
        "delta-bad" if delta else "delta-neu")
    delta_html = (
        f'<div class="delta {delta_cls}">{delta}</div>' if delta else ""
    )
    return f"""
    <div class="kpi-card">
      <div class="label">{label}</div>
      <div class="value">{value}</div>
      {delta_html}
    </div>"""


def delta_str(milp_val: float, base_val: float,
              lower_is_better: bool = True,
              fmt: str = ".0f") -> tuple:
    if base_val == 0:
        return "", True
    diff = milp_val - base_val
    pct = diff / base_val * 100
    good = (diff < 0) if lower_is_better else (diff > 0)
    sign = "↓" if diff < 0 else "↑"
    return f"{sign} {abs(pct):.1f}% vs FIFO", good


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> dict:
    st.sidebar.markdown("## 🏗️ Model Parameters")

    st.sidebar.markdown("### 📋 Data Source")
    data_mode = st.sidebar.radio(
        "Input mode",
        ["Demo dataset (fixed)", "Generator (random)", "Manual entry"],
        index=0,
    )

    params = {"data_mode": data_mode}

    if data_mode == "Generator (random)":
        params["scenario"] = st.sidebar.selectbox(
            "Site type", list(BRIGADE_CATALOG.keys()))
        params["n_lifts"] = st.sidebar.slider("Number of lifts", 5, 25, 15)
        params["density"] = st.sidebar.slider(
            "Load density", 0.4, 1.0, 0.85, 0.05,
            help="0.5 = sparse, 1.0 = overloaded")
        params["seed"] = st.sidebar.number_input(
            "Seed (reproducibility)", 0, 9999, 42)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Crane Parameters")
    params["shift"] = st.sidebar.slider(
        "Shift length (min)", 360, 600, 480, 30,
        help="480 min = 8-hour shift")
    params["q_max"] = st.sidebar.slider("Capacity (t)", 4.0, 20.0, 12.0, 0.5)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 Objective Weights")
    st.sidebar.caption("min  **α·Cmax**  +  **β·Σpenalty·W**")
    params["alpha"] = st.sidebar.slider(
        "α — crane idle weight", 0.0, 3.0, 1.0, 0.1)
    params["beta"] = st.sidebar.slider(
        "β — brigade wait weight", 0.0, 3.0, 1.0, 0.1)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 Solver Parameters")
    params["time_limit"] = st.sidebar.slider(
        "Time limit (s)", 10, 180, 90, 10)
    params["mip_gap"] = st.sidebar.select_slider(
        "MIP gap", [0.001, 0.005, 0.01, 0.02, 0.05], 0.01,
        format_func=lambda x: f"{x:.1%}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Display")
    params["show_baselines"] = st.sidebar.checkbox(
        "Show baseline strategies", True)
    params["show_raw"] = st.sidebar.checkbox("Show lift table", True)
    params["show_advanced"] = st.sidebar.checkbox(
        "Advanced analytics", False,
        help="Show scientific tabs: Performance, Details, Model")

    return params


# ─────────────────────────────────────────────────────────────────────────────
# Manual lift entry
# ─────────────────────────────────────────────────────────────────────────────

_MANUAL_COLS = [
    "Name", "Brigade", "Dur.(min)", "Weight(t)",
    "Ready", "Deadline", "Priority", "$/min",
]

_DEFAULT_ROWS = [
    {"Name": "Column rebar", "Brigade": "Assembly", "Dur.(min)": 30,
     "Weight(t)": 5.2, "Ready": 0, "Deadline": 150,
     "Priority": 5, "$/min": 25.0},
    {"Name": "Concrete pump", "Brigade": "Concrete", "Dur.(min)": 20,
     "Weight(t)": 2.0, "Ready": 60, "Deadline": 200,
     "Priority": 5, "$/min": 30.0},
    {"Name": "Brick pallet", "Brigade": "Masonry", "Dur.(min)": 20,
     "Weight(t)": 1.8, "Ready": 0, "Deadline": 300,
     "Priority": 3, "$/min": 12.0},
    {"Name": "Floor slab", "Brigade": "Assembly", "Dur.(min)": 45,
     "Weight(t)": 9.0, "Ready": 60, "Deadline": 310,
     "Priority": 5, "$/min": 25.0},
    {"Name": "Vent blocks", "Brigade": "MEP", "Dur.(min)": 25,
     "Weight(t)": 4.0, "Ready": 0, "Deadline": 280,
     "Priority": 4, "$/min": 18.0},
]


def manual_input_lifts(shift: int) -> List[Lift]:
    st.markdown(
        '<div class="section-header">✏️ Manual lift entry</div>',
        unsafe_allow_html=True)
    st.info(
        "Double-click a cell to edit. "
        "To **delete a row**: select it → press **Delete** "
        "(or use the 🗑 button in the row).")

    uploaded = st.file_uploader(
        "Load lifts from Excel (.xlsx / .xls)",
        type=["xlsx", "xls"],
        help=f"Expected columns: {', '.join(_MANUAL_COLS)}",
    )

    if uploaded is not None:
        try:
            xls_df = pd.read_excel(uploaded)
            missing = [c for c in _MANUAL_COLS if c not in xls_df.columns]
            if missing:
                st.error(f"Missing columns in file: {', '.join(missing)}")
                init_df = pd.DataFrame(_DEFAULT_ROWS)
            else:
                init_df = xls_df[_MANUAL_COLS].copy()
                st.success(f"Loaded {len(init_df)} rows from file.")
        except Exception as exc:
            st.error(f"Error reading file: {exc}")
            init_df = pd.DataFrame(_DEFAULT_ROWS)
    else:
        init_df = pd.DataFrame(_DEFAULT_ROWS)

    edited = st.data_editor(
        init_df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Priority": st.column_config.SelectboxColumn(
                options=[1, 2, 3, 4, 5]),
            "Dur.(min)": st.column_config.NumberColumn(
                min_value=5, max_value=120),
            "Ready": st.column_config.NumberColumn(
                min_value=0, max_value=shift),
            "Deadline": st.column_config.NumberColumn(
                min_value=10, max_value=shift),
        },
    )

    lifts = []
    for i, row in edited.iterrows():
        try:
            lifts.append(Lift(
                id=i, name=str(row["Name"]) or f"Load {i+1}",
                brigade=str(row["Brigade"]) or "Assembly",
                dur=int(row["Dur.(min)"]), weight=float(row["Weight(t)"]),
                ready=int(row["Ready"]), t_max=int(row["Deadline"]),
                priority=int(row["Priority"]), cost_pm=float(row["$/min"]),
            ))
        except Exception:
            continue

    return lifts


# ─────────────────────────────────────────────────────────────────────────────
# Lift table
# ─────────────────────────────────────────────────────────────────────────────

def render_lifts_table(lifts: List[Lift]):
    rows = []
    for lft in lifts:
        rows.append({
            "ID": lft.id,
            "Lift": lft.name,
            "Brigade": lft.brigade,
            "Pri.": "★" * lft.priority + "☆" * (5 - lft.priority),
            "Min": lft.dur,
            "t": lft.weight,
            "Ready": fmt_time(lft.ready),
            "Deadline": fmt_time(lft.t_max),
            "Penalty": f"{lft.penalty:.0f} $/min",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# KPI panel
# ─────────────────────────────────────────────────────────────────────────────

def render_kpi(milp: SolverResult, fifo: SolverResult, shift: int):
    metrics = [
        ("Cmax", fmt_time(milp.cmax), *delta_str(milp.cmax, fifo.cmax)),
        ("Crane idle", f"{milp.total_idle:.0f} min",
         *delta_str(milp.total_idle, fifo.total_idle)),
        ("Crane Ku", f"{milp.ku:.1f}%",
         *delta_str(milp.ku, fifo.ku, lower_is_better=False)),
        ("Brigade wait", f"{milp.total_wait:.0f} min",
         *delta_str(milp.total_wait, fifo.total_wait)),
        ("Penalty", f"{milp.total_penalty:.0f}",
         *delta_str(milp.total_penalty, fifo.total_penalty)),
        ("Objective", f"{milp.obj_value:.0f}",
         *delta_str(milp.obj_value, fifo.obj_value)),
        ("Tasks", f"{len(milp.schedule)}/{len(fifo.schedule)+1}", "", True),
        ("Solve time", f"{milp.elapsed:.1f} s", "", True),
    ]

    cols = st.columns(len(metrics))
    for col, (label, value, dstr, good) in zip(cols, metrics):
        with col:
            st.markdown(
                kpi_card(label, value, dstr, good),
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Schedule table
# ─────────────────────────────────────────────────────────────────────────────

def render_schedule_table(result: SolverResult):
    rows = []
    gaps = result.gaps
    for i, s in enumerate(result.schedule):
        gap = gaps[i - 1] if i > 0 else 0
        rows.append({
            "#": i + 1,
            "Lift": s.lift.name,
            "Brigade": s.lift.brigade,
            "Pri.": "★" * s.lift.priority + "☆" * (5 - s.lift.priority),
            "Start": fmt_time(s.start),
            "End": fmt_time(s.finish),
            "Dur.": s.lift.dur,
            "Wait": f"{s.wait:.0f} min" if s.wait > 0 else "—",
            "Idle↑": f"{gap:.0f} min" if gap > 0.4 else "—",
            "Penalty": f"{s.wait*s.lift.penalty:.0f}" if s.wait > 0 else "—",
        })
    df = pd.DataFrame(rows)

    def highlight_priority(row):
        p = result.schedule[int(row["#"]) - 1].lift.priority
        colors = {
            5: "#FEF2F2", 4: "#FFF7ED", 3: "#FEFCE8",
            2: "#F0FDF4", 1: "#F9FAFB",
        }
        return [f"background-color: {colors.get(p,'white')}"] * len(row)

    st.dataframe(
        df.style.apply(highlight_priority, axis=1),
        width="stretch", hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────

def render_tab_overview(milp_result: SolverResult, fifo: SolverResult,
                        baselines: dict, shift: int):
    st.markdown(
        '<div class="section-header">📊 Key metrics (MILP vs FIFO)</div>',
        unsafe_allow_html=True)
    render_kpi(milp_result, fifo, shift)

    st.markdown(
        '<div class="section-header">🏗️ Crane utilisation timeline</div>',
        unsafe_allow_html=True)
    st.plotly_chart(crane_timeline(milp_result, shift), width="stretch")

    st.markdown('<div class="section-header">📉 Loss reduction</div>',
                unsafe_allow_html=True)
    if baselines:
        st.plotly_chart(
            waterfall_chart(
                milp_result,
                baselines),
            width="stretch")


def render_tab_schedule(milp_result: SolverResult, baselines: dict,
                        show_baselines: bool, shift: int = 480):
    st.markdown('<div class="section-header">📅 Gantt Chart</div>',
                unsafe_allow_html=True)

    if baselines and show_baselines:
        strat_options = ["MILP ✦"] + list(baselines.keys())
        sel_strat = st.radio("Show strategy:", strat_options,
                             horizontal=True, index=0)
        all_r = {"MILP ✦": milp_result, **baselines}
        display_result = all_r[sel_strat]
    else:
        display_result = milp_result

    st.plotly_chart(gantt_chart(display_result, shift), width="stretch")

    st.markdown('<div class="section-header">📋 Schedule details</div>',
                unsafe_allow_html=True)
    render_schedule_table(display_result)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Idle gaps",
                  sum(1 for g in display_result.gaps if g > 0.4))
    with c2:
        st.metric("Max gap",
                  f"{max(display_result.gaps, default=0):.0f} min")
    with c3:
        non_zero = [g for g in display_result.gaps if g > 0.4]
        avg = sum(non_zero) / len(non_zero) if non_zero else 0
        st.metric("Avg gap", f"{avg:.0f} min")
    with c4:
        late = sum(
            1 for s in display_result.schedule if s.finish > s.lift.t_max)
        st.metric("Deadline violations", late,
                  delta="✓ all on time" if late == 0 else None,
                  delta_color="normal" if late == 0 else "inverse")


def render_tab_performance(milp_result: SolverResult, baselines: dict,
                           lifts: list, shift: int):
    if not baselines:
        st.info("Run optimisation to compare strategies.")
        return

    st.markdown(
        '<div class="section-header">📊 Strategy comparison</div>',
        unsafe_allow_html=True)
    st.plotly_chart(comparison_chart(milp_result, baselines), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="section-header">🕸️ Radar profile</div>',
            unsafe_allow_html=True)
        st.plotly_chart(
            radar_chart(milp_result, baselines, shift, len(lifts)),
            width="stretch")
    with c2:
        st.markdown(
            '<div class="section-header">📦 Idle gap distribution</div>',
            unsafe_allow_html=True)
        st.plotly_chart(
            idle_distribution(milp_result, baselines), width="stretch")

    st.markdown('<div class="section-header">📋 Summary table</div>',
                unsafe_allow_html=True)
    all_r = {**baselines, "MILP ✦": milp_result}
    rows = []
    fifo_obj = (baselines["FIFO"].obj_value
                if baselines.get("FIFO") and baselines["FIFO"].schedule else 0)
    for sname, res in all_r.items():
        if not res.schedule:
            continue
        gain = (fifo_obj - res.obj_value) / \
            fifo_obj * 100 if fifo_obj > 0 else 0
        rows.append({
            "Strategy": sname,
            "Tasks": len(res.schedule),
            "Cmax": fmt_time(res.cmax),
            "Idle (min)": f"{res.total_idle:.0f}",
            "Ku (%)": f"{res.ku:.1f}",
            "Wait (min)": f"{res.total_wait:.0f}",
            "Penalty ($·min)": f"{res.total_penalty:.0f}",
            "Objective": f"{res.obj_value:.0f}",
            "vs FIFO": f"{'-' if gain>=0 else '+'}{abs(gain):.1f}%",
        })

    def highlight_milp(row):
        if "MILP" in str(row["Strategy"]):
            return ["background-color: #DCFCE7; font-weight: bold"] * len(row)
        return [""] * len(row)

    st.dataframe(
        pd.DataFrame(rows).style.apply(highlight_milp, axis=1),
        width="stretch", hide_index=True)


def render_tab_details(milp_result: SolverResult, shift: int):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="section-header">🏢 Brigade wait breakdown</div>',
            unsafe_allow_html=True)
        st.plotly_chart(brigade_chart(milp_result), width="stretch")
    with c2:
        st.markdown(
            '<div class="section-header">📉 MILP loss structure</div>',
            unsafe_allow_html=True)
        tw = milp_result.total_work or sum(
            s.lift.dur for s in milp_result.schedule)
        idle = milp_result.total_idle
        rest = max(0, shift - milp_result.cmax)
        fig_pie = go.Figure(go.Pie(
            labels=["Working time", "Crane idle", "Shift remainder"],
            values=[tw, idle, rest],
            hole=0.5,
            marker=dict(
                colors=["#2563EB", "#EF4444", "#E5E7EB"],
                line=dict(color="white", width=2)),
            textinfo="label+percent",
            textfont=dict(size=12),
        ))
        fig_pie.add_annotation(
            text=f"Ku<br>{milp_result.ku:.0f}%",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#111827", family="Inter"))
        fig_pie.update_layout(
            title=dict(text="Shift utilisation", font=dict(size=14)),
            height=340, showlegend=True, paper_bgcolor="white",
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.1),
        )
        st.plotly_chart(fig_pie, width="stretch")

    st.markdown('<div class="section-header">📊 Brigade statistics</div>',
                unsafe_allow_html=True)
    agg = defaultdict(
        lambda: {"tasks": 0, "wait": 0, "penalty": 0, "priority": 1})
    for s in milp_result.schedule:
        b = s.lift.brigade
        agg[b]["tasks"] += 1
        agg[b]["wait"] += s.wait
        agg[b]["penalty"] += s.wait * s.lift.penalty
        agg[b]["priority"] = s.lift.priority

    rows_b = []
    for bname, d in sorted(agg.items(), key=lambda x: -x[1]["priority"]):
        rows_b.append({
            "Brigade": bname,
            "Priority": "★" * d["priority"] + "☆" * (5 - d["priority"]),
            "Tasks": d["tasks"],
            "Wait (min)": f"{d['wait']:.0f}",
            "Penalty $·min": f"{d['penalty']:.0f}",
            "Avg wait": (f"{d['wait']/d['tasks']:.0f} min"
                         if d["tasks"] else "—"),
        })
    st.dataframe(pd.DataFrame(rows_b), width="stretch", hide_index=True)


def render_tab_model(milp_result: SolverResult, lifts: list, params: dict):
    N = len(lifts)

    st.markdown('<div class="section-header">📐 Problem formulation</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"""
**Model type:** Constraint Programming – Scheduling (CP-SAT)
**Solver:** OR-Tools CP-SAT

#### Decision variables
| Variable | Type | Meaning |
|---|---|---|
| $s_i \\in \\mathbb{{Z}}_{{\\geq 0}}$ | Integer | Start time of lift $i$ |
| $e_i = s_i + d_i$ | Integer | End time of lift $i$ |
| $W_i \\in \\mathbb{{Z}}_{{\\geq 0}}$ | Integer | Brigade wait for lift $i$ |
| $C \\in \\mathbb{{Z}}_{{\\geq 0}}$ | Integer | Makespan (Cmax) |

**Total:** {N}×s + {N}×e + {N}×W + 1×C = **{4*N+1} variables**

#### Objective
$$\\min \\; \\alpha C + \\beta \\sum_i \\text{{penalty}}_i W_i$$

$$\\text{{penalty}}_i = \\text{{priority}}_i \\times \\text{{cost\\_pm}}_i$$

Current weights: **α = {params['alpha']}**, **β = {params['beta']}**

#### Constraints
| | |
|---|---|
| (C1) | $r_i \\leq s_i \\leq t_{{\\max,i}} - d_i$ — time windows |
| (C2) | $C \\geq e_i \\; \\forall i$ — Cmax definition |
| (C3) | $W_i \\geq s_i - \\text{{ready}}_i, \\; W_i \\geq 0$ — brigade wait |
| (C4) | NoOverlap($[s_i, e_i)$) — crane handles one lift at a time |
| (C5) | $w_i \\leq Q_{{\\max}}$ — crane capacity |
""")

    with col2:
        st.markdown("#### Current run parameters")
        model_info = {
            "Lifts (N)": N,
            "Variables": 4 * N + 1,
            "Shift length": f"{params['shift']} min",
            "Capacity": f"{params['q_max']} t",
            "MIP gap": f"{params['mip_gap']:.1%}",
            "Time limit": f"{params['time_limit']} s",
            "Solver status": f"{milp_result.status}",
            "Solve time": f"{milp_result.elapsed:.2f} s",
            "Objective value": f"{milp_result.obj_value:.1f}",
        }
        for k, v in model_info.items():
            st.markdown(f"**{k}:** `{v}`")

        st.markdown("---")
        st.markdown("#### Key model property")
        st.info(
            "**Crane idle = Cmax − Σdur_i**\n\n"
            "Since Σdur_i is constant for a given lift set, "
            "**minimising idle time is equivalent to minimising makespan**. "
            "This allows a single variable C instead of N gap variables.",
            icon="💡")


# ─────────────────────────────────────────────────────────────────────────────
# Engineer dashboard (simple, no scientific details)
# ─────────────────────────────────────────────────────────────────────────────

def _big_stat(
        label: str,
        value: str,
        sub: str = "",
        color: str = "#2563EB") -> str:
    sub_html = (
        f'<div style="font-size:.82rem;color:#6B7280;'
        f'margin-top:.15rem">{sub}</div>'
        if sub else ""
    )
    return f"""
    <div style="background:white;border-radius:12px;padding:1.1rem 1.4rem;
                border:1px solid #E5E7EB;box-shadow:0 1px 6px rgba(0,0,0,.06);
                text-align:center;">
      <div style="font-size:.75rem;text-transform:uppercase;
                  letter-spacing:.06em;color:#6B7280;
                  font-weight:600">{label}</div>
      <div style="font-size:2.1rem;font-weight:800;color:{color};
                  line-height:1.15;margin:.2rem 0">{value}</div>
      {sub_html}
    </div>"""


def render_tab_dashboard(milp_result: SolverResult, shift: int):
    sched = milp_result.schedule
    if not sched:
        st.warning("No schedule to display.")
        return

    n_tasks = len(sched)
    busy_min = sum(s.lift.dur for s in sched)
    idle_min = int(milp_result.total_idle)
    ku = milp_result.ku
    finish_time = fmt_time(milp_result.cmax)
    shift_end = fmt_time(shift)
    late = sum(1 for s in sched if s.finish > s.lift.t_max)

    # ── KPI row ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Tasks Completed", str(n_tasks),
         "out of shift plan", "#2563EB"),
        (c2, "Crane Utilisation", f"{ku:.0f}%",
         f"busy {busy_min} min", "#16A34A"),
        (c3, "Idle Time", f"{idle_min} min",
         "crane waiting", "#EF4444"),
        (c4, "Schedule End", finish_time,
         f"shift limit {shift_end}", "#F97316"),
        (c5, "Deadline Issues", str(late),
         "tasks late" if late else "all on time",
         "#DC2626" if late else "#16A34A"),
    ]
    for col, label, value, sub, color in cards:
        with col:
            st.markdown(_big_stat(label, value, sub, color),
                        unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Utilisation bar ──────────────────────────────────────────────────────
    st.plotly_chart(crane_timeline(milp_result, shift), width="stretch")

    # ── Gantt ────────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📅 Lift Schedule</div>',
                unsafe_allow_html=True)
    st.plotly_chart(simple_gantt(milp_result, shift), width="stretch")

    # ── Simple lift list ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Lift List</div>',
                unsafe_allow_html=True)
    rows = []
    for i, s in enumerate(sched):
        on_time = s.finish <= s.lift.t_max
        rows.append({
            "#": i + 1,
            "Lift": s.lift.name,
            "Brigade": s.lift.brigade,
            "Weight (t)": s.lift.weight,
            "Start": fmt_time(s.start),
            "End": fmt_time(s.finish),
            "Duration (min)": s.lift.dur,
            "Status": "✅ On time" if on_time else "⚠️ Late",
        })

    df = pd.DataFrame(rows)

    def row_color(row):
        return (
            ["background-color:#FEF2F2"] * len(row)
            if "Late" in str(row["Status"])
            else [""] * len(row)
        )

    st.dataframe(
        df.style.apply(row_color, axis=1),
        width="stretch",
        hide_index=True,
    )
