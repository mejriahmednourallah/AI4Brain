"""Version 2 of HY-01 Courier, kept separate for historical replay safety.

The public config contains the ordinary board and promise data only. Generation
uses a private deterministic route scaffold to guarantee that every configured
promise can be fulfilled in order; that scaffold is never returned.
"""
from __future__ import annotations

import hashlib
import random
from collections import deque
from typing import Any

VERSION = "hy-01-v2"
EVALUATION_VERSION = "hy-01-eval-v2"
DIRECTIONS: dict[str, tuple[int, int]] = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
}
TIER_SHAPES: dict[str, tuple[int, int, int]] = {
    "tutorial": (3, 4, 1), "tier-1": (4, 5, 2), "tier-2": (4, 6, 3), "tier-3": (5, 6, 4),
}


def _rng(seed: str, *parts: str) -> random.Random:
    digest = hashlib.sha256("|".join([seed, *parts]).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _snake(rows: int, cols: int) -> list[tuple[int, int]]:
    """Hamiltonian walk beginning at the v1-compatible lower-left start."""
    cells: list[tuple[int, int]] = []
    for row in range(rows - 1, -1, -1):
        xs = range(cols) if (rows - 1 - row) % 2 == 0 else range(cols - 1, -1, -1)
        cells.extend((x, row) for x in xs)
    return cells


def _promise_text(destination_id: str, cue: str) -> str:
    plot = destination_id.split("-")[1]
    if cue == "after_gate_a":
        return f"Deliver to plot {plot} after you pass the first garden gate."
    if cue == "after_bell":
        return f"Deliver to plot {plot} after the bell rings."
    return f"Deliver to plot {plot} before the bell rings."


def generate(seed: str, mode: str, tier: str) -> dict[str, Any]:
    if tier not in TIER_SHAPES:
        raise ValueError(f"unsupported Courier tier: {tier}")
    rows, cols, intentions = TIER_SHAPES[tier]
    if mode == "tutorial":
        rows, cols, intentions = TIER_SHAPES["tutorial"]
        tier = "tutorial"
    rng = _rng(seed, VERSION, tier, mode)
    scaffold = _snake(rows, cols)
    start = scaffold[0]
    # Select a seed-dependent, increasing set of route milestones. This keeps
    # the private Hamiltonian scaffold as a feasibility witness while moving
    # pickups and plots across the whole board instead of teaching fixed cells.
    # Gate A is before parcel 1; each later pickup follows the prior delivery.
    # Thus a learner can walk the scaffold in order without accidentally
    # collecting a future parcel while carrying another.
    milestone_count = intentions * 2 + (1 if intentions > 1 else 0)
    wall_count = max(1, (rows * cols) // 10)
    max_index = min(len(scaffold) - wall_count - 3, 3 * milestone_count + 2)
    candidates = list(range(1, max_index + 1))
    rng.shuffle(candidates)
    selected = sorted(candidates[:milestone_count])
    if intentions > 1:
        gate_a_index = selected[0]
        parcel_indices = selected[1::2]
        destination_indices = selected[2::2]
    else:
        gate_a_index = None
        parcel_indices, destination_indices = selected[:1], selected[1:2]
    assert len(parcel_indices) == intentions and len(destination_indices) == intentions
    route_indices = {0, *parcel_indices, *destination_indices}
    if gate_a_index is not None:
        route_indices.add(gate_a_index)
    assert max(route_indices) < len(scaffold)
    route_cells = {scaffold[index] for index in route_indices}

    # Put scenery hazards beyond the last required waypoint so the public
    # board always contains the complete private witness route unobstructed.
    available = scaffold[max(route_indices) + 1:]
    rng.shuffle(available)
    gate_a = scaffold[gate_a_index] if gate_a_index is not None else available.pop()
    gate_b = available.pop()
    walls = available[:wall_count]

    cues = ["after_gate_a", "before_bell", "after_bell"]
    plans: list[dict[str, Any]] = []
    parcels: list[dict[str, Any]] = []
    destinations: list[dict[str, Any]] = []
    for index in range(intentions):
        parcel_id = f"parcel-{index + 1}"
        destination_id = f"plot-{chr(ord('A') + index)}"
        cue = cues[index % len(cues)] if intentions > 1 else "before_bell"
        if intentions > 1 and index == intentions - 1 and index % len(cues) == 0:
            cue = "after_gate_a"
        plans.append({"order": index + 1, "parcel_id": parcel_id,
                      "destination_id": destination_id, "cue": cue,
                      "promise": _promise_text(destination_id, cue)})
        parcels.append({"parcel_id": parcel_id, "cell": list(scaffold[parcel_indices[index]])})
        destinations.append({"destination_id": destination_id,
                             "cell": list(scaffold[destination_indices[index]])})

    # Place the bell strictly after plan 2's destination and no later than the
    # plan 3 destination when one exists. Earlier plans retain their cue order.
    plan2_destination_index = destination_indices[min(1, intentions - 1)]
    if intentions >= 3:
        plan3_destination_index = destination_indices[2]
        bell_after = rng.randint(plan2_destination_index + 1, plan3_destination_index)
    else:
        bell_after = plan2_destination_index + rng.randint(1, 2)
    return {
        "activity_id": "HY-01", "activity_version": VERSION, "config_version": "2",
        "evaluation_version": EVALUATION_VERSION, "mode": mode, "tier": tier, "seed": seed,
        "board": {"cols": cols, "rows": rows, "start": list(start), "walls": [list(cell) for cell in walls]},
        "destinations": destinations, "parcels": parcels,
        "gates": [{"gate_id": "gate-a", "cell": list(gate_a)}, {"gate_id": "gate-b", "cell": list(gate_b)}],
        "bell": {"after_moves": bell_after}, "plans": plans,
        "encode_ms": 9000 if mode == "tutorial" else 6000,
        "assistance_windows": ["pre_play", "safe_checkpoint", "post_completion"],
    }


def _distances(cols: int, rows: int, walls: set[tuple[int, int]], start: tuple[int, int]) -> dict[tuple[int, int], int]:
    seen = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS.values():
            nxt = (x + dx, y + dy)
            if 0 <= nxt[0] < cols and 0 <= nxt[1] < rows and nxt not in walls and nxt not in seen:
                seen[nxt] = seen[(x, y)] + 1
                queue.append(nxt)
    return seen


def evaluate(config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    if config.get("activity_version") != VERSION:
        raise ValueError(f"{VERSION} evaluator cannot evaluate {config.get('activity_version')!r}")
    board = config["board"]
    cols, rows = int(board["cols"]), int(board["rows"])
    walls = {tuple(wall) for wall in board["walls"]}
    gates = {tuple(gate["cell"]): gate["gate_id"] for gate in config["gates"]}
    parcels = {tuple(parcel["cell"]): parcel["parcel_id"] for parcel in config["parcels"]}
    destination_cells = {destination["destination_id"]: tuple(destination["cell"])
                         for destination in config["destinations"]}
    cell_destination = {tuple(destination["cell"]): destination["destination_id"]
                        for destination in config["destinations"]}
    bell_after = int(config["bell"]["after_moves"])
    x, y = board["start"]
    moves = blocked = 0
    carrying: str | None = None
    picked: set[str] = set()
    delivered: set[str] = set()
    gates_seen: list[str] = []
    bell_fired = False
    pickups: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = []

    for action in actions:
        kind = action.get("action_type")
        payload = action.get("payload") or {}
        if kind == "move":
            delta = DIRECTIONS.get(str(payload.get("direction", "")))
            if delta is None:
                blocked += 1
                continue
            nx, ny = x + delta[0], y + delta[1]
            if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in walls:
                blocked += 1
                continue
            x, y = nx, ny
            moves += 1
            gate_id = gates.get((x, y))
            if gate_id and gate_id not in gates_seen:
                gates_seen.append(gate_id)
            if not bell_fired and moves >= bell_after:
                bell_fired = True
            parcel_id = parcels.get((x, y))
            if carrying is None and parcel_id and parcel_id not in picked and parcel_id not in delivered:
                carrying = parcel_id
                picked.add(parcel_id)
                pickups.append({"parcel_id": parcel_id, "at": [x, y], "moves": moves})
        elif kind == "deliver":
            destination_id = cell_destination.get((x, y))
            valid = carrying is not None and destination_id is not None
            delivery = {"parcel_id": carrying, "at": [x, y], "destination_id": destination_id,
                        "moves": moves, "gates_seen": list(gates_seen), "bell_fired": bell_fired,
                        "action_index": action.get("sequence"), "valid": valid}
            deliveries.append(delivery)
            if valid and carrying is not None:
                delivered.add(carrying)
                carrying = None

    def cue_result(cue: str, delivery: dict[str, Any]) -> tuple[bool, str]:
        if cue == "after_gate_a":
            ok = "gate-a" in delivery["gates_seen"]
            return ok, "first gate passed before delivery" if ok else "the first gate was not passed before delivery"
        if cue == "after_bell":
            ok = bool(delivery["bell_fired"])
            return ok, "bell had rung" if ok else "the bell had not rung yet"
        ok = not delivery["bell_fired"]
        return ok, "delivered before the bell" if ok else "the bell had already rung"

    plans = sorted(config["plans"], key=lambda plan: plan["order"])
    used: set[int] = set()
    promise_results: list[dict[str, Any]] = []
    for plan in plans:
        delivery_index = next((i for i, delivery in enumerate(deliveries)
                               if i not in used and delivery["parcel_id"] == plan["parcel_id"] and delivery["valid"]), None)
        if delivery_index is None:
            promise_results.append({"order": plan["order"], "parcel_id": plan["parcel_id"],
                "destination_id": plan["destination_id"], "cue": plan["cue"], "promise": plan["promise"],
                "satisfied": False, "reason": "parcel was not delivered to a destination",
                "cue_met": False, "wrong_destination": False})
            continue
        used.add(delivery_index)
        delivery = deliveries[delivery_index]
        at_right_place = delivery["destination_id"] == plan["destination_id"]
        cue_met, cue_reason = cue_result(plan["cue"], delivery)
        promise_results.append({"order": plan["order"], "parcel_id": plan["parcel_id"],
            "destination_id": plan["destination_id"], "cue": plan["cue"], "promise": plan["promise"],
            "satisfied": bool(at_right_place and cue_met),
            "reason": cue_reason if at_right_place else f"delivered to {delivery['destination_id']} instead of {plan['destination_id']}",
            "cue_met": cue_met, "delivered_at": delivery["destination_id"],
            "wrong_destination": not at_right_place, "moves_at_delivery": delivery["moves"]})

    # Sum shortest distances between ordered pickup/destination milestones.
    # This is a guaranteed lower bound: it deliberately omits gate constraints
    # and possible bell-waiting steps, which can only add moves. In particular,
    # do not add a gate detour that may already have happened on a prior leg.
    current = tuple(board["start"])
    optimal = 0
    pickup_cells = {parcel["parcel_id"]: tuple(parcel["cell"]) for parcel in config["parcels"]}
    for plan in plans:
        for target in (pickup_cells[plan["parcel_id"]],):
            dist = _distances(cols, rows, walls, current)
            optimal += dist[target]
            current = target
        target = destination_cells[plan["destination_id"]]
        dist = _distances(cols, rows, walls, current)
        optimal += dist[target]
        current = target

    satisfied = sum(bool(result["satisfied"]) for result in promise_results)
    actual_order = [delivery["parcel_id"] for delivery in deliveries if delivery["valid"]]
    planned_order = [plan["parcel_id"] for plan in plans]
    return {
        "activity_id": "HY-01", "activity_version": VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "promise_count": len(planned_order), "promises_satisfied": satisfied,
        "promises_total": len(planned_order),
        "cue_misses": sum(not row["cue_met"] and not row["wrong_destination"] for row in promise_results),
        "wrong_destination_deliveries": sum(bool(row["wrong_destination"]) for row in promise_results),
        "order_deviations": sum(1 for i, parcel_id in enumerate(actual_order[:len(planned_order)])
                                if planned_order[i] != parcel_id),
        "moves": moves, "optimal_moves": optimal, "path_overhead": max(0, moves - optimal),
        "blocked_moves": blocked,
        "unused_parcels": sorted(set(parcels.values()) - delivered),
        "bell": {"after_moves": bell_after, "rang": bell_fired, "moves_at_completion": moves},
        "promises": promise_results, "deliveries": deliveries, "pickups": pickups,
        "gates_visited": gates_seen,
    }
