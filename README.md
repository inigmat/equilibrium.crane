# 🏗️ Tower Crane Schedule Optimiser

A Streamlit web application for optimal scheduling of tower crane lifts using
**CP-SAT** (OR-Tools). Minimises crane idle time and brigade waiting penalties
simultaneously.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red)
![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/inigmat/equilibrium.crane.git
cd equilibrium.crane

# 2. Create virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

The app opens automatically at `http://localhost:8501`.

---

## Project structure

```
crane_scheduler/
├── app.py           — Streamlit entry point (orchestration only)
├── solver.py        — CP-SAT model + greedy baselines
├── data_gen.py      — Realistic lift request generator
├── charts.py        — Plotly visualisations
├── ui.py            — All Streamlit UI components and tab renderers
├── requirements.txt
├── LICENSE
└── README.md
```

---

## How it works

### Optimisation model

**Type:** Constraint Programming (CP-SAT, Google OR-Tools)

**Objective — minimise two competing costs:**

```
min  α · Cmax  +  β · Σ penalty_i · W_i
```

| Symbol | Meaning |
|---|---|
| `Cmax` | Makespan — time of the last completed lift |
| `W_i` | Brigade wait for lift i (= start_i − ready_i) |
| `penalty_i` | priority_i × cost_per_min_i |
| `α, β` | Tunable weights (sidebar sliders) |

> **Key insight:** crane idle = Cmax − Σ dur_i. Since Σ dur_i is constant for
> a given lift set, minimising idle time is equivalent to minimising Cmax —
> one variable instead of N gap variables.

**Variables**

| Variable | Type | Description |
|---|---|---|
| `s_i` | Integer ≥ 0 | Start time of lift i (minutes from shift start) |
| `e_i = s_i + d_i` | Integer | End time of lift i |
| `W_i` | Integer ≥ 0 | Brigade wait time for lift i |
| `C` | Integer ≥ 0 | Makespan |

**Constraints**

| | |
|---|---|
| (C1) | `ready_i ≤ s_i ≤ t_max_i − dur_i` — time windows |
| (C2) | `C ≥ e_i ∀ i` — Cmax definition |
| (C3) | `W_i ≥ s_i − ready_i, W_i ≥ 0` — brigade wait |
| (C4) | NoOverlap([s_i, e_i)) — crane handles one lift at a time |
| (C5) | `w_i ≤ Q_max` — crane capacity constraint |

### Baseline strategies (for comparison)

| Strategy | Rule |
|---|---|
| **FIFO** | First In, First Out — earliest ready time first |
| **By Priority** | Greedy dispatch, highest priority brigade first |
| **SPT** | Shortest Processing Time — shortest lift first |
| **EDD** | Earliest Due Date — tightest deadline first |
| **MILP ✦** | CP-SAT optimal (minimises combined objective) |

---

## Features

### Data modes

- **Demo dataset** — 15 fixed lift requests (residential building, 3 sections)
- **Generator** — randomised realistic data for three building types:
  - Monolith (reinforced concrete frame)
  - Brick (masonry + floor slabs)
  - Industrial (steel structures)
- **Manual entry** — editable table directly in the browser

### Sidebar parameters

| Parameter | Description |
|---|---|
| Shift duration | 6 / 8 / 10 / 12 hours |
| α, β weights | Balance between makespan and brigade wait penalty |
| Crane capacity Q_max | Maximum lift weight (t) |
| Time limit | CP-SAT solver time budget (seconds) |
| MIP gap | Acceptable optimality gap (e.g. 1%) |
| Show baseline strategies | Compare MILP against greedy heuristics |
| Advanced analytics | Unlock Performance, Details and Model tabs |

### Dashboard (default view)

- **5 KPI cards** — tasks completed, crane utilisation, idle time,
  schedule end, deadline violations
- **Crane utilisation timeline** — full-shift colour-coded bar
  (working / brigade wait / idle)
- **Gantt chart** — clean lift schedule by brigade, no scientific overlays
- **Lift list table** — with late-task highlighting

### Advanced analytics (toggle in sidebar)

| Tab | Content |
|---|---|
| 📊 Overview | KPI comparison vs FIFO, timeline, waterfall loss reduction |
| 📅 Schedule | Scientific Gantt with wait/idle overlays, strategy selector |
| 📈 Performance | Bar comparison, radar profile, idle gap distribution, summary table |
| 🔬 Details | Brigade wait breakdown, shift utilisation pie, brigade statistics |
| 📐 Model | Full LaTeX formulation, constraint table, current run parameters |

---

## Requirements

| Package | Version |
|---|---|
| Python | ≥ 3.9 |
| streamlit | ≥ 1.32 |
| ortools | ≥ 9.8 (CP-SAT solver) |
| plotly | ≥ 5.19 |
| pandas | ≥ 2.0 |
| numpy | ≥ 1.26 |
| openpyxl | ≥ 3.1 |

---

## License

MIT — see [LICENSE](LICENSE).
