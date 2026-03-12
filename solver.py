"""
solver.py — CP-SAT scheduling core for tower crane optimisation.

Dual objective:
    min  α · Cmax  +  β · Σ penalty_i · W_i

    Cmax      = makespan (last task finish)  →  proxy for crane idle time
    W_i       = s_i − ready_i               →  brigade wait for lift i
    penalty_i = priority_i × cost_pm_i  →  penalty weight ($/min × priority)


Constraints:
    (C1) ready_i ≤ s_i,  s_i + dur_i ≤ t_max_i
    (C2) Cmax ≥ s_i + dur_i  ∀ i
    (C3) W_i ≥ s_i − ready_i,  W_i ≥ 0
    (C4) NoOverlap — crane handles exactly one lift at a time
"""

import time
from dataclasses import dataclass
from typing import List, Dict

from ortools.sat.python import cp_model

# Scale factor: convert float objective coefficients to integers for CP-SAT
_SCALE = 1000


@dataclass
class Lift:
    id: int
    name: str
    brigade: str
    dur: int
    weight: float
    ready: int
    t_max: int
    priority: int
    cost_pm: float

    @property
    def penalty(self) -> float:
        return self.priority * self.cost_pm


@dataclass
class ScheduledLift:
    lift: Lift
    start: float
    finish: float
    wait: float


@dataclass
class SolverResult:
    schedule: List[ScheduledLift]
    cmax: float
    total_idle: float
    total_wait: float
    total_penalty: float
    obj_value: float
    ku: float
    status: int
    elapsed: float
    gaps: List[float]
    total_work: int = 0


def solve(
    lifts: List[Lift],
    shift: int = 480,
    alpha: float = 1.0,
    beta: float = 1.0,
    time_limit: float = 90.0,
    mip_gap: float = 0.01,
) -> SolverResult:
    N = len(lifts)
    if N == 0:
        return SolverResult([], 0, 0, 0, 0, 0, 0, -1, 0, [], 0)

    total_work = sum(lft.dur for lft in lifts)

    model = cp_model.CpModel()

    # ── Variables ───────────────────────────────────────────────────────────
    starts = []
    ends = []
    intervals = []
    waits = []

    for k, lft in enumerate(lifts):
        s_lo = lft.ready
        s_hi = max(lft.ready, lft.t_max - lft.dur)
        s = model.new_int_var(s_lo, s_hi, f"s_{k}")
        e = model.new_int_var(s_lo + lft.dur, lft.t_max, f"e_{k}")
        iv = model.new_interval_var(s, lft.dur, e, f"iv_{k}")
        w = model.new_int_var(0, shift, f"w_{k}")
        starts.append(s)
        ends.append(e)
        intervals.append(iv)
        waits.append(w)

    cmax = model.new_int_var(total_work, shift, "cmax")

    # ── Constraints ─────────────────────────────────────────────────────────
    # One lift at a time (replaces all Big-M disjunctive pairs)
    model.add_no_overlap(intervals)

    for k, lft in enumerate(lifts):
        # Cmax ≥ finish_i
        model.add(cmax >= ends[k])
        # W_i ≥ s_i − ready_i
        model.add(waits[k] >= starts[k] - lft.ready)

    # ── Objective ───────────────────────────────────────────────────────────
    # Scale float coefficients to integers
    a = int(round(alpha * _SCALE))
    obj_terms = [a * cmax]
    for k, lft in enumerate(lifts):
        b = int(round(beta * lft.penalty * _SCALE))
        if b != 0:
            obj_terms.append(b * waits[k])

    model.minimize(sum(obj_terms))

    # ── Solver ──────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.relative_gap_limit = mip_gap
    solver.parameters.log_search_progress = False

    t0 = time.time()
    status = solver.solve(model)
    elapsed = time.time() - t0

    ok_statuses = {cp_model.OPTIMAL, cp_model.FEASIBLE}
    if status not in ok_statuses:
        return SolverResult(
            [], 0, 0, 0, 0, 0, 0, status, round(
                elapsed, 2), [], total_work)

    # ── Extract solution ────────────────────────────────────────────────────
    scheduled = []
    for k, lft in enumerate(lifts):
        s = float(solver.value(starts[k]))
        w = float(solver.value(waits[k]))
        scheduled.append(ScheduledLift(
            lift=lft,
            start=round(s, 1),
            finish=round(s + lft.dur, 1),
            wait=round(max(0.0, w), 1),
        ))
    scheduled.sort(key=lambda r: r.start)

    cmax_val = float(solver.value(cmax))
    gaps = [round(max(0.0, scheduled[k + 1].start - scheduled[k].finish), 1)
            for k in range(len(scheduled) - 1)]
    tw = sum(s.wait for s in scheduled)
    tp = sum(s.wait * s.lift.penalty for s in scheduled)

    return SolverResult(
        schedule=scheduled,
        cmax=round(cmax_val, 1),
        total_idle=round(cmax_val - total_work, 1),
        total_wait=round(tw, 1),
        total_penalty=round(tp, 1),
        obj_value=round(solver.objective_value / _SCALE, 1),
        ku=round(total_work / cmax_val * 100, 1) if cmax_val > 0 else 0.0,
        status=status,
        elapsed=round(elapsed, 2),
        gaps=gaps,
        total_work=total_work,
    )


def simulate_greedy(lifts: List[Lift], order: List[int], shift: int = 480,
                    alpha: float = 1.0, beta: float = 1.0) -> SolverResult:
    clock = 0.0
    scheduled = []
    for i in order:
        lft = lifts[i]
        start = max(clock, float(lft.ready))
        fin = start + lft.dur
        if fin > lft.t_max or fin > shift:
            continue
        scheduled.append(ScheduledLift(
            lift=lft,
            start=round(start, 1),
            finish=round(fin, 1),
            wait=round(max(0.0, start - lft.ready), 1),
        ))
        clock = fin

    if not scheduled:
        return SolverResult([], 0, 0, 0, 0, 0, 0, -1, 0, [],
                            sum(lft.dur for lft in lifts))

    cmax = max(s.finish for s in scheduled)
    tw = sum(lft.dur for lft in lifts)
    gaps = [round(max(0.0, scheduled[k + 1].start - scheduled[k].finish), 1)
            for k in range(len(scheduled) - 1)]
    wait = sum(s.wait for s in scheduled)
    pen = sum(s.wait * s.lift.penalty for s in scheduled)

    return SolverResult(
        schedule=scheduled, cmax=round(cmax, 1),
        total_idle=round(cmax - sum(s.lift.dur for s in scheduled), 1),
        total_wait=round(wait, 1), total_penalty=round(pen, 1),
        obj_value=round(alpha * cmax + beta * pen, 1),
        ku=round(
            sum(s.lift.dur for s in scheduled) / cmax * 100, 1
        ) if cmax > 0 else 0,
        status=0, elapsed=0.0, gaps=gaps, total_work=tw,
    )


def run_baselines(lifts: List[Lift],
                  shift: int = 480,
                  alpha: float = 1.0,
                  beta: float = 1.0) -> Dict[str,
                                             SolverResult]:
    N = len(lifts)
    return {
        "FIFO": simulate_greedy(
            lifts,
            sorted(
                range(N),
                key=lambda i: lifts[i].ready),
            shift,
            alpha,
            beta),
        "By Priority": simulate_greedy(
            lifts,
            sorted(
                range(N),
                key=lambda i: (
                    -lifts[i].priority,
                    lifts[i].ready)),
            shift,
            alpha,
            beta),
        "SPT": simulate_greedy(
            lifts,
            sorted(
                range(N),
                key=lambda i: lifts[i].dur),
            shift,
            alpha,
            beta),
        "EDD": simulate_greedy(
            lifts,
            sorted(
                range(N),
                key=lambda i: lifts[i].t_max),
            shift,
            alpha,
            beta),
    }
