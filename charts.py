"""
charts.py — Plotly visualisations.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict
from solver import SolverResult

SHIFT_H = 8

BRIGADE_COLORS = {
    "Assembly": "#2563EB", "Concrete": "#7C3AED",
    "Rebar": "#1D4ED8", "Formwork": "#3B82F6",
    "MEP": "#0891B2", "Masonry": "#D97706",
    "Masonry-1": "#F59E0B", "Masonry-2": "#FBBF24",
    "Masonry-3": "#FCD34D", "Slab": "#92400E",
    "Steel": "#1E3A5F", "Welders": "#374151",
    "Facade": "#059669", "Roofing": "#10B981",
    "Scaffold": "#6B7280",
}

STRAT_COLORS = {
    "FIFO": "#9CA3AF", "Priority": "#60A5FA",
    "SPT": "#34D399", "EDD": "#A78BFA",
    "MILP ✦": "#EF4444",
}


def _bc(name): return BRIGADE_COLORS.get(name, "#9CA3AF")


def _ft(m):
    m = max(0, int(round(m)))
    return f"{SHIFT_H + m//60:02d}:{m%60:02d}"


def _ticks(shift):
    vals = list(range(0, shift + 1, 60))
    return vals, [_ft(t) for t in vals]


# ── 1. GANTT CHART ──────────────────────────────────────────────────────

def gantt_chart(result: SolverResult, shift: int = 480) -> go.Figure:
    sched = result.schedule
    gaps = result.gaps
    if not sched:
        return go.Figure()

    y_labels = [f"#{i+1}  {s.lift.name}" for i, s in enumerate(sched)]
    fig = go.Figure()

    seen_brigades = {}
    for i, s in enumerate(sched):
        col = _bc(s.lift.brigade)
        seen_brigades.setdefault(s.lift.brigade, col)

        # Task bar
        fig.add_trace(go.Bar(
            x=[s.lift.dur], y=[y_labels[i]], base=[s.start],
            orientation="h",
            marker=dict(
                color=col,
                line=dict(color="rgba(255,255,255,0.6)", width=1)),
            hovertemplate=(
                f"<b>{s.lift.name}</b><br>"
                f"Brigade: {s.lift.brigade}  (★{'●'*s.lift.priority})<br>"
                f"Start: {_ft(s.start)}  →  End: {_ft(s.finish)}<br>"
                f"Duration: {s.lift.dur} min  |  Weight: {s.lift.weight} t<br>"
                f"Brigade wait: {s.wait:.0f} min<br>"
                f"Penalty: {s.wait*s.lift.penalty:.0f} $·min<extra></extra>"
            ),
            showlegend=False,
            text=f"  {s.lift.brigade}" if s.lift.dur >= 20 else "",
            textposition="inside", insidetextanchor="start",
            textfont=dict(color="white", size=11),
        ))

        # Brigade wait (hatched red zone)
        if s.wait > 0.5:
            fig.add_trace(go.Bar(
                x=[s.wait], y=[y_labels[i]], base=[s.lift.ready],
                orientation="h",
                marker=dict(color="rgba(239,68,68,0.18)",
                            line=dict(color="rgba(239,68,68,0.5)", width=1),
                            pattern=dict(shape="/", solidity=0.4)),
                hovertemplate=f"Brigade wait: {s.wait:.0f} min<extra></extra>",
                showlegend=False,
            ))

        # Crane idle before this task
        if i > 0 and gaps[i - 1] > 0.4:
            gs = sched[i - 1].finish
            fig.add_trace(go.Bar(
                x=[gaps[i - 1]], y=[y_labels[i]], base=[gs],
                orientation="h",
                marker=dict(color="rgba(107,114,128,0.15)",
                            line=dict(color="rgba(107,114,128,0.4)", width=1)),
                hovertemplate=(
                    f"Crane idle: {gaps[i-1]:.0f} min<extra></extra>"),
                showlegend=False,
            ))

    # Cmax line
    if result.cmax > 0:
        fig.add_vline(
            x=result.cmax,
            line_dash="dot",
            line_color="#F97316",
            line_width=2,
            annotation_text=f"Cmax = {_ft(result.cmax)}",
            annotation_font_color="#F97316",
            annotation_position="top left")

    # Shift end line
    fig.add_vline(
        x=shift,
        line_dash="dash",
        line_color="#EF4444",
        line_width=1.5,
        annotation_text="Shift end",
        annotation_font_color="#EF4444",
        annotation_position="top right")

    tv, tt = _ticks(shift)
    fig.update_layout(
        title=dict(
            text="Gantt Chart — lift schedule",
            font=dict(
                size=16,
                color="#111827")),
        xaxis=dict(
            title="Shift time",
            tickvals=tv,
            ticktext=tt,
            range=[
                0,
                shift],
            gridcolor="#F3F4F6",
            zeroline=False),
        yaxis=dict(
            autorange="reversed",
            gridcolor="#F3F4F6"),
        barmode="overlay",
        height=max(
            420,
            44 * len(sched) + 100),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
            family="Inter, Arial",
            size=12,
            color="#374151"),
        margin=dict(
            l=10,
            r=20,
            t=70,
            b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1),
    )

    # Brigade legend
    for bname, color in seen_brigades.items():
        fig.add_trace(go.Bar(x=[None], y=[None], orientation="h",
                             marker_color=color, name=bname, showlegend=True))
    fig.add_trace(go.Bar(x=[None], y=[None], orientation="h",
                         marker=dict(color="rgba(239,68,68,0.3)"),
                         name="Brigade wait", showlegend=True))
    fig.add_trace(go.Bar(x=[None], y=[None], orientation="h",
                         marker=dict(color="rgba(107,114,128,0.2)"),
                         name="Crane idle", showlegend=True))
    return fig


# ── 1b. SIMPLE ENGINEER GANTT ───────────────────────────────────────────

def simple_gantt(result: SolverResult, shift: int = 480) -> go.Figure:
    """Clean Gantt for field engineers — no scientific overlays."""
    sched = result.schedule
    if not sched:
        return go.Figure()

    fig = go.Figure()
    seen_brigades = {}

    for i, s in enumerate(sched):
        col = _bc(s.lift.brigade)
        seen_brigades.setdefault(s.lift.brigade, col)
        label = f"#{i+1}  {s.lift.name}"

        fig.add_trace(go.Bar(
            x=[s.lift.dur],
            y=[label],
            base=[s.start],
            orientation="h",
            marker=dict(
                color=col,
                line=dict(color="rgba(255,255,255,0.7)", width=1.5),
            ),
            hovertemplate=(
                f"<b>{s.lift.name}</b><br>"
                f"Brigade: {s.lift.brigade}<br>"
                f"Start: {_ft(s.start)}  →  End: {_ft(s.finish)}<br>"
                f"Duration: {s.lift.dur} min  |  Weight: {s.lift.weight} t"
                "<extra></extra>"
            ),
            showlegend=False,
            text=(f"  {s.lift.name}" if s.lift.dur >= 25 else ""),
            textposition="inside",
            insidetextanchor="start",
            textfont=dict(color="white", size=11, family="Inter, Arial"),
        ))

    # Shift-end line
    fig.add_vline(
        x=shift,
        line_dash="dash", line_color="#EF4444", line_width=1.5,
        annotation_text="Shift end",
        annotation_font_color="#EF4444",
        annotation_position="top right",
    )

    # Brigade legend
    for bname, color in seen_brigades.items():
        fig.add_trace(go.Bar(
            x=[None], y=[None], orientation="h",
            marker_color=color, name=bname, showlegend=True,
        ))

    tv, tt = _ticks(shift)
    fig.update_layout(
        xaxis=dict(
            title="Time of day",
            tickvals=tv, ticktext=tt,
            range=[0, shift],
            gridcolor="#F3F4F6", zeroline=False,
        ),
        yaxis=dict(autorange="reversed", gridcolor="#F3F4F6"),
        barmode="overlay",
        height=max(380, 40 * len(sched) + 80),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, Arial", size=12, color="#374151"),
        margin=dict(l=10, r=20, t=20, b=50),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
        ),
    )
    return fig


# ── 2. STRATEGY COMPARISON ──────────────────────────────────────────────

def comparison_chart(milp: SolverResult,
                     baselines: Dict[str,
                                     SolverResult]) -> go.Figure:
    all_r = {**baselines, "MILP ✦": milp}

    metrics = [
        ("Cmax (min)", lambda r: r.cmax),
        ("Crane idle (min)", lambda r: r.total_idle),
        ("Brigade wait (min)", lambda r: r.total_wait),
        ("Penalty (×100 $·min)", lambda r: r.total_penalty / 100),
        ("Tasks done", lambda r: len(r.schedule)),
    ]

    fig = make_subplots(rows=1, cols=len(metrics),
                        subplot_titles=[m[0] for m in metrics],
                        horizontal_spacing=0.06)

    for col, (mname, mfn) in enumerate(metrics, 1):
        for sname, res in all_r.items():
            val = mfn(res) if res.schedule else 0
            is_milp = sname == "MILP ✦"
            fig.add_trace(
                go.Bar(
                    name=sname,
                    x=[sname],
                    y=[val],
                    marker_color=STRAT_COLORS.get(sname, "#6B7280"),
                    marker_line=dict(
                        color="#111" if is_milp else "rgba(0,0,0,0)",
                        width=2 if is_milp else 0,
                    ),
                    showlegend=(col == 1),
                    text=[f"{val:.0f}"],
                    textposition="outside",
                    textfont=dict(size=11, color="#374151"),
                ),
                row=1, col=col,
            )

    fig.update_layout(
        title=dict(
            text="Strategy comparison",
            font=dict(
                size=15)),
        barmode="group",
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
                family="Inter, Arial",
                size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="center",
            x=0.5),
        margin=dict(
            l=10,
            r=10,
            t=90,
            b=40),
    )
    fig.update_yaxes(gridcolor="#F3F4F6", zeroline=False)
    return fig


# ── 3. WATERFALL — objective function improvement ───────────────────────

def waterfall_chart(milp: SolverResult,
                    baselines: Dict[str,
                                    SolverResult]) -> go.Figure:
    names = list(baselines.keys()) + ["MILP ✦"]
    all_r = {**baselines, "MILP ✦": milp}
    vals = [all_r[n].obj_value for n in names if all_r[n].schedule]
    names = [n for n in names if all_r[n].schedule]

    if not vals:
        return go.Figure()

    deltas = [vals[0]] + [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    measures = ["absolute"] + ["relative"] * (len(deltas) - 1)

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=names,
        y=deltas,
        text=[f"{v:.0f}" for v in vals],
        textposition="outside",
        connector={"line": {"color": "#D1D5DB", "dash": "dot"}},
        decreasing={"marker": {
            "color": "#22C55E", "line": {"color": "#16A34A", "width": 1}}},
        increasing={"marker": {
            "color": "#EF4444", "line": {"color": "#DC2626", "width": 1}}},
        totals={"marker": {
            "color": "#3B82F6", "line": {"color": "#1D4ED8", "width": 2}}},
    ))

    fifo_val = vals[0]
    milp_val = vals[-1]
    gain = (fifo_val - milp_val) / fifo_val * 100 if fifo_val > 0 else 0
    fig.add_annotation(
        x=names[-1], y=milp_val,
        text=f"<b>−{gain:.1f}% vs FIFO</b>",
        showarrow=True, arrowhead=2, arrowcolor="#22C55E",
        font=dict(color="#16A34A", size=13), ay=-40,
    )

    fig.update_layout(
        title=dict(
            text="Objective reduction: α·Cmax + β·Σpenalty·W",
            font=dict(
                size=15)),
        yaxis_title="Objective value",
        height=380,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
            family="Inter, Arial",
            size=12),
        showlegend=False,
        margin=dict(
            l=10,
            r=10,
            t=60,
            b=40),
    )
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig


# ── 4. CRANE UTILISATION TIMELINE ───────────────────────────────────────

def crane_timeline(result: SolverResult, shift: int = 480) -> go.Figure:
    state = ["idle"] * shift
    for s in result.schedule:
        for t in range(int(s.start), min(shift, int(s.finish))):
            state[t] = s.lift.brigade
        for t in range(int(s.lift.ready), min(shift, int(s.start))):
            if state[t] == "idle":
                state[t] = "wait"

    # Build segments
    segs = []
    if state:
        cur, st = state[0], 0
        for t in range(1, len(state)):
            if state[t] != cur:
                segs.append((st, t, cur))
                cur, st = state[t], t
        segs.append((st, len(state), cur))

    fig = go.Figure()
    seen = set()
    for ss, se, sstate in segs:
        if sstate == "idle":
            col, lbl = "rgba(107,114,128,0.35)", "Crane idle"
        elif sstate == "wait":
            col, lbl = "rgba(239,68,68,0.25)", "Brigade wait"
        else:
            col, lbl = _bc(sstate), sstate

        show = lbl not in seen
        seen.add(lbl)
        fig.add_trace(go.Bar(
            x=[se - ss], y=["Crane"], base=[ss], orientation="h",
            marker=dict(color=col, line=dict(color="white", width=0.5)),
            name=lbl, showlegend=show,
            hovertemplate=(
                f"{lbl}: {_ft(ss)} – {_ft(se)}"
                f"  ({se-ss} min)<extra></extra>"),
        ))

    tv, tt = _ticks(shift)
    fig.update_layout(
        title=dict(
            text="Crane utilisation timeline",
            font=dict(
                size=14)),
        xaxis=dict(
            tickvals=tv,
            ticktext=tt,
            range=[
                0,
                shift],
            gridcolor="#F3F4F6"),
        yaxis=dict(
            visible=False),
        barmode="overlay",
        height=140,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(
            l=10,
            r=10,
            t=44,
            b=60),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="left",
            x=0),
        font=dict(
            family="Inter, Arial",
            size=11),
    )
    return fig


# ── 5. BRIGADE WAIT CHART ───────────────────────────────────────────────

def brigade_chart(result: SolverResult) -> go.Figure:
    if not result.schedule:
        return go.Figure()

    from collections import defaultdict
    agg = defaultdict(lambda: {"wait": 0, "penalty": 0, "priority": 1, "n": 0})
    for s in result.schedule:
        b = s.lift.brigade
        agg[b]["wait"] += s.wait
        agg[b]["penalty"] += s.wait * s.lift.penalty
        agg[b]["priority"] = s.lift.priority
        agg[b]["n"] += 1

    rows = sorted(agg.items(), key=lambda x: -x[1]["priority"])
    brigades = [r[0] for r in rows]
    waits = [r[1]["wait"] for r in rows]
    pens = [r[1]["penalty"] for r in rows]
    cols = [_bc(b) for b in brigades]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=brigades, y=waits, name="Wait (min)",
        marker=dict(color=cols, line=dict(color="white", width=1)),
        text=[f"{w:.0f}" for w in waits], textposition="outside",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=brigades, y=[p / 100 for p in pens],
        name="Penalty (×100 $·min)",
        mode="markers+lines",
        marker=dict(size=10, color="#EF4444", symbol="diamond"),
        line=dict(color="#EF4444", width=2, dash="dot"),
    ), secondary_y=True)

    fig.update_layout(
        title=dict(text="Brigade wait time & penalty", font=dict(size=14)),
        height=360, plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, Arial", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=60, b=40),
    )
    fig.update_yaxes(
        title_text="Wait (min)",
        gridcolor="#F3F4F6",
        secondary_y=False)
    fig.update_yaxes(title_text="Penalty ×100 $·min", secondary_y=True)
    return fig


# ── 6. RADAR CHART ──────────────────────────────────────────────────────

def radar_chart(milp: SolverResult, baselines: Dict[str, SolverResult],
                shift: int = 480, n_total: int = 15) -> go.Figure:
    def scores(r):
        if not r.schedule:
            return [0] * 5
        n = len(r.schedule)
        return [
            r.ku / 100,
            max(0, 1 - r.total_idle / shift),
            max(0, 1 - r.total_wait / max(1, n * 60)),
            sum(1 for s in r.schedule if s.finish <= s.lift.t_max) / n,
            min(1, n / n_total),
        ]

    cats = ["Utilisation", "No idle", "No wait", "On time", "Tasks"]
    all_r = {**baselines, "MILP ✦": milp}
    widths = {k: (3 if k == "MILP ✦" else 1.5) for k in all_r}

    fig = go.Figure()
    for name, res in all_r.items():
        sc = scores(res) + [scores(res)[0]]
        fig.add_trace(go.Scatterpolar(
            r=sc, theta=cats + [cats[0]],
            name=name,
            fill="toself" if name == "MILP ✦" else "none",
            fillcolor="rgba(239,68,68,0.10)" if name == "MILP ✦" else None,
            line=dict(
                color=STRAT_COLORS.get(name, "#999"),
                width=widths[name]),
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[
                    0,
                    1],
                tickformat=".0%",
                gridcolor="#E5E7EB",
                tickfont=dict(
                    size=10)),
            angularaxis=dict(
                gridcolor="#E5E7EB"),
            bgcolor="white",
        ),
        title=dict(
            text="Strategy efficiency profile",
            font=dict(
                size=14)),
        height=400,
        paper_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5),
        margin=dict(
            l=40,
            r=40,
            t=60,
            b=60),
        font=dict(
            family="Inter, Arial",
            size=12),
    )
    return fig


# ── 7. IDLE GAP DISTRIBUTION ─────────────────────────────────────────────────

def idle_distribution(milp: SolverResult,
                      baselines: Dict[str,
                                      SolverResult]) -> go.Figure:
    """Box plots of crane idle gap sizes between tasks."""
    fig = go.Figure()
    all_r = {**baselines, "MILP ✦": milp}

    for name, res in all_r.items():
        gaps = [g for g in res.gaps if g > 0.4]
        if not gaps:
            continue
        fig.add_trace(go.Box(
            y=gaps, name=name,
            marker_color=STRAT_COLORS.get(name, "#999"),
            boxmean=True,
            line=dict(width=2 if name == "MILP ✦" else 1),
        ))

    fig.update_layout(
        title=dict(
            text="Crane idle gap distribution between tasks",
            font=dict(size=14)),
        yaxis_title="Gap duration (min)",
        height=340,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(
            family="Inter, Arial",
            size=12),
        showlegend=False,
        margin=dict(
            l=10,
            r=10,
            t=60,
            b=40),
    )
    fig.update_yaxes(gridcolor="#F3F4F6")
    return fig
