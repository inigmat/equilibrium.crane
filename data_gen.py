"""
data_gen.py — Realistic data generator for a construction site.
"""
import random
from typing import List
from solver import Lift

BRIGADE_CATALOG = {
    "Monolithic": [
        {"name": "Assembly", "priority": 5, "cost_pm": 25.0},
        {"name": "Concrete", "priority": 5, "cost_pm": 30.0},
        {"name": "Rebar", "priority": 4, "cost_pm": 20.0},
        {"name": "Formwork", "priority": 4, "cost_pm": 18.0},
        {"name": "MEP", "priority": 4, "cost_pm": 18.0},
        {"name": "Masonry", "priority": 3, "cost_pm": 12.0},
        {"name": "Facade", "priority": 2, "cost_pm": 8.0},
        {"name": "Scaffold", "priority": 1, "cost_pm": 5.0},
    ],
    "Brick": [
        {"name": "Masonry-1", "priority": 5, "cost_pm": 20.0},
        {"name": "Masonry-2", "priority": 5, "cost_pm": 20.0},
        {"name": "Masonry-3", "priority": 4, "cost_pm": 16.0},
        {"name": "Slab", "priority": 5, "cost_pm": 25.0},
        {"name": "MEP", "priority": 4, "cost_pm": 18.0},
        {"name": "Facade", "priority": 2, "cost_pm": 8.0},
        {"name": "Scaffold", "priority": 1, "cost_pm": 5.0},
    ],
    "Industrial": [
        {"name": "Steel", "priority": 5, "cost_pm": 30.0},
        {"name": "Welders", "priority": 5, "cost_pm": 28.0},
        {"name": "Concrete", "priority": 4, "cost_pm": 22.0},
        {"name": "MEP", "priority": 4, "cost_pm": 20.0},
        {"name": "Roofing", "priority": 3, "cost_pm": 14.0},
        {"name": "Facade", "priority": 2, "cost_pm": 8.0},
    ],
}

LOAD_CATALOG = {
    "Assembly": [("RC columns", 30, 7.0), ("Floor slab", 45, 9.0),
                 ("Steel struct.", 50, 8.0), ("Floor beams", 35, 6.0)],
    "Concrete": [("Concrete pump A", 20, 2.0), ("Concrete pump B", 20, 2.0),
                 ("Concrete trough", 25, 3.0)],
    "Rebar": [("Column rebar", 30, 5.0), ("Wall rebar", 25, 4.5),
              ("Beam rebar", 20, 3.5)],
    "Formwork": [("Slab formwork", 35, 3.5), ("Formwork panels", 30, 4.0)],
    "MEP": [("Vent blocks", 25, 4.0), ("Window units", 20, 2.8),
            ("Vent pipes", 20, 2.0)],
    "Masonry": [("Brick pallet", 20, 1.8), ("AAC block pallet", 20, 1.6)],
    "Masonry-1": [("Brick #1", 20, 1.8), ("Brick #2", 20, 1.8)],
    "Masonry-2": [("Brick #3", 20, 1.8), ("Brick #4", 20, 1.8)],
    "Masonry-3": [("Brick #5", 20, 1.8)],
    "Slab": [("HC slab", 40, 8.5), ("Ribbed slab", 40, 8.0)],
    "Steel": [("HEA300 beam", 50, 9.0), ("Roof truss", 60, 10.0),
              ("Column 12m", 45, 8.0)],
    "Welders": [("Steel struct.", 40, 7.5), ("Base plates", 30, 5.0)],
    "Facade": [("Sandwich panels", 40, 6.5), ("Glazing units", 25, 3.0)],
    "Roofing": [("Profiled sheet", 35, 4.0), ("Insulation packs", 30, 2.5)],
    "Scaffold": [("Scaffold tier 5", 15, 1.2), ("Scaffold tier 6", 15, 1.2),
                 ("Scaffold tier 7", 15, 1.2)],
}


def generate_lifts(
    scenario: str = "Monolithic",
    n_lifts: int = 15,
    shift: int = 480,
    q_max: float = 12.0,
    seed: int = 42,
    density: float = 0.85,
) -> List[Lift]:
    rng = random.Random(seed)
    brigades = BRIGADE_CATALOG.get(scenario, BRIGADE_CATALOG["Monolithic"])
    lifts = []
    lift_id = 0
    dur_sum = 0
    budget = int(shift * density)

    for _ in range(n_lifts * 4):
        if lift_id >= n_lifts or dur_sum >= budget:
            break

        weights = [b["priority"] for b in brigades]
        brigade = rng.choices(brigades, weights=weights, k=1)[0]
        bname = brigade["name"]

        catalog = LOAD_CATALOG.get(bname, [("Load", 30, 5.0)])
        load_name, bd, bw = rng.choice(catalog)

        dur = max(10, bd + rng.randint(-5, 10))
        weight = round(min(q_max * 0.95, bw + rng.uniform(-0.5, 0.5)), 1)

        earliest = rng.randint(0, max(0, shift - dur - 60))
        win_size = rng.randint(dur + 30, min(dur + 180, shift - earliest))
        t_max = min(shift, earliest + win_size)
        if rng.random() < 0.2:
            t_max = min(shift, earliest + dur + rng.randint(20, 60))
        if t_max - earliest < dur:
            continue

        same = sum(1 for lft in lifts if lft.brigade == bname)
        suffix = f" #{same+1}" if same > 0 else ""

        lifts.append(Lift(
            id=lift_id, name=load_name + suffix, brigade=bname,
            dur=dur, weight=weight, ready=earliest, t_max=t_max,
            priority=brigade["priority"], cost_pm=brigade["cost_pm"],
        ))
        dur_sum += dur
        lift_id += 1

    return lifts


DEMO_LIFTS = [
    Lift(0, "Column rebar Fl.7", "Assembly", 30, 5.2, 0, 150, 5, 25.0),
    Lift(1, "Slab formwork Fl.7", "Assembly", 35, 3.5, 30, 240, 5, 25.0),
    Lift(2, "Concrete — section A", "Concrete", 20, 2.0, 70, 200, 5, 30.0),
    Lift(3, "Wall rebar Fl.8", "Assembly", 30, 4.8, 90, 300, 5, 25.0),
    Lift(4, "Floor slab B", "Assembly", 45, 9.0, 60, 310, 5, 25.0),
    Lift(5, "Brick — pallet #1", "Masonry", 20, 1.8, 0, 320, 3, 12.0),
    Lift(6, "Brick — pallet #2", "Masonry", 20, 1.8, 40, 360, 3, 12.0),
    Lift(7, "Brick — pallet #3", "Masonry", 20, 1.8, 100, 400, 3, 12.0),
    Lift(8, "Partition brick C", "Masonry", 20, 1.5, 30, 400, 3, 12.0),
    Lift(9, "Vent blocks shaft C", "MEP", 25, 4.0, 0, 280, 4, 18.0),
    Lift(10, "Window units C Fl.4", "MEP", 20, 2.8, 120, 420, 4, 18.0),
    Lift(11, "Sandwich panels facade", "Facade", 40, 6.5, 200, 480, 2, 8.0),
    Lift(12, "Scaffold — tier 5", "Scaffold", 15, 1.2, 150, 480, 1, 5.0),
    Lift(13, "Steel structure Fl.8", "Assembly", 50, 7.5, 200, 480, 5, 25.0),
    Lift(14, "Concrete — section B", "Concrete", 20, 2.0, 180, 380, 5, 30.0),
]
