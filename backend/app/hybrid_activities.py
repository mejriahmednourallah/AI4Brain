"""Deterministic, versioned generators and evaluators for hybrid activities.

All ground truth is produced here on the server from the stored seed and
configuration. The client only sends ordered actions; it never sends correctness,
scores or an answer key. Hybrid outcomes are descriptive for the activity and are
never averaged into the five fixed EX baseline indices.
"""
from __future__ import annotations

import hashlib
import random
from collections import deque
from typing import Any
from .hybrid_activities_modules import living_archive
from .hybrid_activities_modules import courier_v2
from .hybrid_activities_modules import shifting_market, bridge_council
from .hybrid_activities_modules import tidekeeper, harbor_dispatch
from .hybrid_contracts import ASSISTANCE_EXPOSURES, ASSISTANCE_WINDOWS

HYBRID_EVALUATION_VERSION = "hybrid-eval-v1"

# These estimates are for early plan budgeting only. They are not measured
# durations and must be replaced or calibrated from reviewed activity samples.
_PLAN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "HY-01": {"family_relevance": ["working_memory", "planning"], "estimated_duration_minutes": 5},
    "HY-02": {"family_relevance": ["working_memory", "attention_inhibition"], "estimated_duration_minutes": 3},
    "HY-03": {"family_relevance": ["working_memory", "flexibility"], "estimated_duration_minutes": 4},
    "HY-04": {"family_relevance": ["working_memory", "attention_inhibition", "flexibility"], "estimated_duration_minutes": 5},
    "HY-05": {"family_relevance": ["working_memory", "reasoning"], "estimated_duration_minutes": 5},
    "HY-06": {"family_relevance": ["planning", "reasoning"], "estimated_duration_minutes": 6},
}


def capability_metadata(activity_id: str) -> dict[str, Any]:
    """Add truthful planning/runtime capabilities without changing hybrid-v1 records."""
    meta = CATALOG.get(activity_id)
    if not meta or not is_implemented(activity_id):
        raise KeyError(f"{activity_id} is not implemented")
    planning = _PLAN_CAPABILITIES[activity_id]
    return {
        **meta,
        **planning,
        "relevance_scope": "task_mechanics_only_not_assessment",
        "duration_estimate_status": "provisional_unmeasured",
        "duration_estimate_basis": "initial_plan_budget_guess_not_observed",
        "activity_version": meta["activity_version"],
        "config_version": meta["config_version"],
        "supported_modes": ["tutorial", "training", "challenge"],
        "assistance_windows": list(ASSISTANCE_WINDOWS[activity_id]),
        "assistance_exposures": list(ASSISTANCE_EXPOSURES),
        "supported_lifecycle": {
            "attempt_states": ["started", "completed"],
            "outcome_states": ["completed", "interrupted"],
            "recoverable_states": ["started"],
            "exact_start_retry": True,
            "exact_action_retry": True,
            "exact_completion_retry": True,
            "interruption_recorded": True,
        },
        "contributions": {
            "baseline_indices": False,
            "ex_difficulty_tiers": False,
            "participation_xp": False,
        },
        "personalized_plan_status": "not_integrated",
    }

DIRECTIONS: dict[str, tuple[int, int]] = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

# Only activities with a working generator, evaluator and playable slice are listed.
CATALOG: dict[str, dict[str, Any]] = {
    "HY-01": {
        "activity_id": "HY-01",
        "activity_version": courier_v2.VERSION,
        "config_version": "2",
        "title": "The Courier's Promise",
        "world": "Wayfinder's Garden",
        "summary": "Remember delivery promises, walk the garden and deliver when each promise's cue is true.",
        "scenarios": "Prospective memory, route planning and event-based timing.",
        "status": "playable",
    },
    "HY-05": {
        "activity_id": "HY-05",
        "activity_version": living_archive.VERSION,
        "config_version": "1",
        "title": "The Living Archive",
        "world": "Pattern Atelier",
        "summary": "Remember relational clues, arrange the relics and inspect the exact relation that conflicts.",
        "scenarios": "Relational memory and spatial reconstruction.",
        "status": "playable",
    },
    "HY-03": {"activity_id":"HY-03", "activity_version":shifting_market.VERSION, "config_version":"1", "title":"Shifting Market", "world":"Market of Many Colors", "summary":"Remember a delivery sequence, then route each parcel as the sorting rule changes.", "scenarios":"Remembered order and rule switching.", "status":"playable"},
    "HY-06": {"activity_id":"HY-06", "activity_version":bridge_council.VERSION, "config_version":"1", "title":"Bridge Council", "world":"The Archipelago", "summary":"Plan a feasible route, inspect advice and justify whether to accept, reject or hold it.", "scenarios":"Constraint planning and evidence-based advice review.", "status":"playable"},
    "HY-02": {"activity_id":"HY-02", "activity_version":tidekeeper.VERSION, "config_version":"1", "title":"Tidekeeper", "world":"The Harbor Clock", "summary":"Track a rolling sequence and make separate position and symbol match decisions.", "scenarios":"Working-memory updating and selective attention.", "status":"playable"},
    "HY-04": {"activity_id":"HY-04", "activity_version":harbor_dispatch.VERSION, "config_version":"1", "title":"Harbor Dispatch", "world":"Harbor Lanes", "summary":"Recall a cargo manifest, route arrivals and adapt to a new wave rule.", "scenarios":"Attention, working memory and rule shifts.", "status":"playable"},
}

TIER_SHAPES: dict[str, tuple[int, int, int]] = {
    "tutorial": (3, 4, 1),
    "tier-1": (4, 5, 2),
    "tier-2": (4, 6, 3),
    "tier-3": (5, 6, 4),
}

HY01_LIMITATIONS = [
    "Descriptive activity outcomes only; this activity is not one of the five fixed baseline indices.",
    "Promptness of the bell cue depends on the recorded move count, not on reaction speed.",
    "Optimal move count is a lower bound from the stored board and promise order.",
]


def _rng(seed: str, *parts: str) -> random.Random:
    digest = hashlib.sha256("|".join([seed, *parts]).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _key(cell: tuple[int, int]) -> str:
    return f"{cell[0]},{cell[1]}"


def _bfs(cols: int, rows: int, walls: set[tuple[int, int]], start: tuple[int, int]) -> dict[tuple[int, int], int]:
    seen = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS.values():
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in walls and (nx, ny) not in seen:
                seen[(nx, ny)] = seen[(x, y)] + 1
                queue.append((nx, ny))
    return seen


def _generate_hy01(seed: str, mode: str, tier: str) -> dict[str, Any]:
    rows, cols, intentions = TIER_SHAPES.get(tier, TIER_SHAPES["tier-1"])
    if mode == "tutorial":
        rows, cols, intentions = TIER_SHAPES["tutorial"]
    rng = _rng(seed, "HY-01", tier, mode)
    start = (0, rows - 1)
    destinations = [(cols - 1, rows - 1), (0, 0), (cols - 1, 0)][: max(2, min(3, intentions))]
    open_cells = [(x, y) for x in range(cols) for y in range(rows) if (x, y) != start and (x, y) not in destinations]

    wall_count = max(1, len(open_cells) // 6)
    walls: list[tuple[int, int]] = []
    pool = list(open_cells)
    rng.shuffle(pool)
    for cell in pool:
        if len(walls) >= wall_count:
            break
        candidate = walls + [cell]
        reach = _bfs(cols, rows, set(candidate), start)
        if all(d in reach for d in destinations) and len(reach) >= cols * rows - len(candidate):
            walls.append(cell)
    wall_set = set(walls)

    free = [c for c in open_cells if c not in wall_set]
    rng.shuffle(free)
    pickups = free[:intentions]
    gates = free[intentions:intentions + 2]
    gate_ids = ["gate-a", "gate-b"]

    cue_options = ["after_gate_a", "before_bell", "after_bell"]
    plans: list[dict[str, Any]] = []
    for index in range(intentions):
        parcel_id = f"parcel-{index + 1}"
        destination_id = f"plot-{chr(ord('A') + index)}"
        cue = cue_options[index % len(cue_options)] if intentions > 1 else "before_bell"
        plans.append({
            "order": index + 1,
            "parcel_id": parcel_id,
            "destination_id": destination_id,
            "cue": cue,
            "promise": _promise_text(destination_id, cue),
        })

    config = {
        "activity_id": "HY-01",
        "activity_version": "hy-01-v1",
        "config_version": "1",
        "mode": mode,
        "tier": tier,
        "seed": seed,
        "board": {"cols": cols, "rows": rows, "start": list(start), "walls": [list(w) for w in walls]},
        "destinations": [{"destination_id": f"plot-{chr(ord('A') + i)}", "cell": list(destinations[i % len(destinations)])}
                         for i in range(intentions)],
        "parcels": [{"parcel_id": p["parcel_id"], "cell": list(pickups[i])} for i, p in enumerate(plans)],
        "gates": [{"gate_id": gate_ids[i], "cell": list(g)} for i, g in enumerate(gates)],
        "bell": {"after_moves": max(6, (cols * rows) // 3 + rng.randint(0, 2))},
        "plans": plans,
        "encode_ms": 6000 if mode != "tutorial" else 9000,
        "assistance_windows": ["pre_play", "safe_checkpoint", "post_completion"],
    }
    return config


def _promise_text(destination_id: str, cue: str) -> str:
    plot = destination_id.split("-")[1]
    if cue == "after_gate_a":
        return f"Deliver to plot {plot} after you pass the first garden gate."
    if cue == "after_bell":
        return f"Deliver to plot {plot} after the bell rings."
    return f"Deliver to plot {plot} before the bell rings."


def _evaluate_hy01(config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    board = config["board"]
    cols, rows = int(board["cols"]), int(board["rows"])
    walls = {tuple(w) for w in board["walls"]}
    gates = {tuple(g["cell"]): g["gate_id"] for g in config["gates"]}
    parcels = {tuple(p["cell"]): p["parcel_id"] for p in config["parcels"]}
    destination_cells = {d["destination_id"]: tuple(d["cell"]) for d in config["destinations"]}
    cell_destination = {tuple(d["cell"]): d["destination_id"] for d in config["destinations"]}
    bell_after = int(config["bell"]["after_moves"])

    x, y = board["start"]
    moves = 0
    carried: str | None = None
    visited_gates: list[str] = []
    bell_fired = False
    blocked = 0
    pickups: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = []

    for action in actions:
        kind = action["action_type"]
        if kind == "move":
            direction = str(action.get("payload", {}).get("direction", ""))
            delta = DIRECTIONS.get(direction)
            if delta is None:
                blocked += 1
                continue
            nx, ny = x + delta[0], y + delta[1]
            if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in walls:
                blocked += 1
                continue
            x, y = nx, ny
            moves += 1
            if (x, y) in gates and gates[(x, y)] not in visited_gates:
                visited_gates.append(gates[(x, y)])
            if not bell_fired and moves >= bell_after:
                bell_fired = True
            if carried is None and (x, y) in parcels:
                carried = parcels[(x, y)]
                pickups.append({"parcel_id": carried, "at": [x, y], "moves": moves})
        elif kind == "deliver":
            destination_id = cell_destination.get((x, y))
            deliveries.append({
                "parcel_id": carried,
                "at": [x, y],
                "destination_id": destination_id,
                "moves": moves,
                "gates_seen": list(visited_gates),
                "bell_fired": bell_fired,
                "action_index": action["sequence"],
                "valid": carried is not None and destination_id is not None,
            })
            if carried is not None and destination_id is not None:
                carried = None

    def cue_true(cue: str, delivery: dict[str, Any]) -> tuple[bool, str]:
        if cue == "after_gate_a":
            ok = "gate-a" in delivery["gates_seen"]
            return ok, "first gate passed before delivery" if ok else "the first gate was not passed before delivery"
        if cue == "after_bell":
            ok = bool(delivery["bell_fired"])
            return ok, "bell had rung" if ok else "the bell had not rung yet"
        ok = not delivery["bell_fired"]
        return ok, "delivered before the bell" if ok else "the bell had already rung"

    intended = sorted(config["plans"], key=lambda p: p["order"])
    used: set[int] = set()
    promise_results: list[dict[str, Any]] = []
    for plan in intended:
        delivery_index = next((i for i, d in enumerate(deliveries)
                               if i not in used and d["parcel_id"] == plan["parcel_id"] and d["valid"]), None)
        if delivery_index is None:
            promise_results.append({
                "order": plan["order"], "parcel_id": plan["parcel_id"], "destination_id": plan["destination_id"],
                "cue": plan["cue"], "promise": plan["promise"], "satisfied": False,
                "reason": "parcel was not delivered to a destination", "cue_met": False, "wrong_destination": False,
            })
            continue
        used.add(delivery_index)
        delivery = deliveries[delivery_index]
        at_right_place = delivery["destination_id"] == plan["destination_id"]
        cue_met, cue_reason = cue_true(plan["cue"], delivery)
        promise_results.append({
            "order": plan["order"], "parcel_id": plan["parcel_id"], "destination_id": plan["destination_id"],
            "cue": plan["cue"], "promise": plan["promise"], "satisfied": bool(at_right_place and cue_met),
            "reason": cue_reason if at_right_place else f"delivered to {delivery['destination_id']} instead of {plan['destination_id']}",
            "cue_met": cue_met, "delivered_at": delivery["destination_id"], "wrong_destination": not at_right_place,
            "moves_at_delivery": delivery["moves"],
        })

    planned_order = [p["parcel_id"] for p in intended]
    actual_order = [d["parcel_id"] for d in deliveries if d["valid"]]
    order_deviations = sum(1 for i, parcel in enumerate(actual_order[:len(planned_order)]) if planned_order[i] != parcel)

    # Lower bound on walking distance for the promised order, ignoring cue waits.
    start_cell = tuple(board["start"])
    pickup_cell = {p["parcel_id"]: tuple(p["cell"]) for p in config["parcels"]}
    route = [start_cell] + [c for plan in intended for c in (pickup_cell[plan["parcel_id"]], destination_cells[plan["destination_id"]])]
    optimal = 0
    for a, b in zip(route, route[1:]):
        distances = _bfs(cols, rows, walls, a)
        optimal += distances.get(b, 0)

    satisfied = sum(1 for r in promise_results if r["satisfied"])
    return {
        "activity_id": "HY-01",
        "evaluation_version": HYBRID_EVALUATION_VERSION,
        "promise_count": len(planned_order),
        "promises_satisfied": satisfied,
        "promises_total": len(planned_order),
        "cue_misses": sum(1 for r in promise_results if r["satisfied"] is False and r.get("cue_met") is False and not r.get("wrong_destination")),
        "wrong_destination_deliveries": sum(1 for r in promise_results if r.get("wrong_destination")),
        "order_deviations": order_deviations,
        "moves": moves,
        "optimal_moves": optimal,
        "path_overhead": max(0, moves - optimal),
        "blocked_moves": blocked,
        "unused_parcels": sorted({p for p in parcels.values()} - {d["parcel_id"] for d in deliveries if d["valid"]}),
        "bell": {"after_moves": bell_after, "rang": bell_fired, "moves_at_completion": moves},
        "promises": promise_results,
        "deliveries": deliveries,
        "pickups": pickups,
        "gates_visited": visited_gates,
    }


GENERATORS = {"HY-01": _generate_hy01, "HY-02": tidekeeper.generate, "HY-03": shifting_market.generate, "HY-04": harbor_dispatch.generate, "HY-05": living_archive.generate, "HY-06": bridge_council.generate}
EVALUATORS = {"HY-01": _evaluate_hy01, "HY-02": tidekeeper.evaluate, "HY-03": shifting_market.evaluate, "HY-04": harbor_dispatch.evaluate, "HY-05": living_archive.evaluate, "HY-06": bridge_council.evaluate}


def is_implemented(activity_id: str) -> bool:
    return activity_id in GENERATORS and activity_id in EVALUATORS


def generate(activity_id: str, seed: str, mode: str, tier: str,
             activity_version: str | None = None) -> dict[str, Any]:
    # The no-version helper remains v1 for compatibility with historical
    # fixtures. New attempts pass their catalog version explicitly.
    if activity_id == "HY-01" and activity_version == courier_v2.VERSION:
        return courier_v2.generate(seed, mode, tier)
    if activity_id == "HY-01" and activity_version not in (None, "hy-01-v1"):
        raise KeyError(f"unsupported HY-01 activity_version: {activity_version}")
    generator = GENERATORS.get(activity_id)
    if generator is None:
        raise KeyError(f"{activity_id} is not implemented")
    return generator(seed, mode, tier)


def evaluate(activity_id: str, config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    if activity_id == "HY-01" and config.get("activity_version") == courier_v2.VERSION:
        return courier_v2.evaluate(config, actions)
    evaluator = EVALUATORS.get(activity_id)
    if evaluator is None:
        raise KeyError(f"{activity_id} is not implemented")
    return evaluator(config, actions)


def limitations_for(activity_id: str) -> list[str]:
    if activity_id == "HY-02":
        return list(tidekeeper.LIMITATIONS)
    if activity_id == "HY-04":
        return list(harbor_dispatch.LIMITATIONS)
    if activity_id == "HY-01":
        return list(HY01_LIMITATIONS)
    if activity_id == "HY-05":
        return list(living_archive.LIMITATIONS)
    if activity_id == "HY-03":
        return list(shifting_market.LIMITATIONS)
    if activity_id == "HY-06":
        return list(bridge_council.LIMITATIONS)
    return ["Descriptive activity outcomes only; not part of the five fixed baseline indices."]
