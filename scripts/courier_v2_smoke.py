"""Independent HY-01 v2 route oracle, legacy witness and versioned-start smoke."""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"

from backend.app.hybrid_activities import DIRECTIONS, evaluate, generate  # noqa: E402
from backend.app.hybrid_activities_modules import courier_v2  # noqa: E402


def path(config: dict, source: tuple[int, int], target: tuple[int, int],
         forbidden: set[tuple[int, int]] | None = None) -> list[str]:
    board = config["board"]
    blocked = {tuple(cell) for cell in board["walls"]} | (forbidden or set())
    prior: dict[tuple[int, int], tuple[tuple[int, int], str] | None] = {source: None}
    queue = deque([source])
    while queue:
        cell = queue.popleft()
        if cell == target:
            break
        for direction, (dx, dy) in DIRECTIONS.items():
            nxt = (cell[0] + dx, cell[1] + dy)
            if (0 <= nxt[0] < board["cols"] and 0 <= nxt[1] < board["rows"]
                    and nxt not in blocked and nxt not in prior):
                prior[nxt] = (cell, direction)
                queue.append(nxt)
    assert target in prior, f"no legal path {source}->{target}"
    moves: list[str] = []
    current = target
    while prior[current] is not None:
        previous, direction = prior[current]
        moves.append(direction)
        current = previous
    return list(reversed(moves))


def route_actions(config: dict, *, revisit_first_pickup: bool = True) -> list[dict]:
    """Find a route independently from public waypoints, without generator helpers."""
    board = config["board"]
    pos = tuple(board["start"])
    pickups = {parcel["parcel_id"]: tuple(parcel["cell"]) for parcel in config["parcels"]}
    destinations = {dest["destination_id"]: tuple(dest["cell"]) for dest in config["destinations"]}
    parcels_by_cell = {cell: parcel_id for parcel_id, cell in pickups.items()}
    gate_a = next(tuple(gate["cell"]) for gate in config["gates"] if gate["gate_id"] == "gate-a")
    actions: list[dict] = []
    moves = 0
    gate_seen = False
    collected: set[str] = set()
    delivered: set[str] = set()
    carrying: str | None = None

    def walk(target: tuple[int, int], avoid: set[tuple[int, int]] | None = None) -> None:
        nonlocal pos, moves, gate_seen, carrying
        for direction in path(config, pos, target, avoid):
            actions.append({"sequence": len(actions) + 1, "action_type": "move", "payload": {"direction": direction}})
            dx, dy = DIRECTIONS[direction]
            pos = (pos[0] + dx, pos[1] + dy)
            moves += 1
            if pos == gate_a:
                gate_seen = True
            parcel_id = parcels_by_cell.get(pos)
            if carrying is None and parcel_id and parcel_id not in collected and parcel_id not in delivered:
                carrying = parcel_id
                collected.add(parcel_id)

    for plan in sorted(config["plans"], key=lambda row: row["order"]):
        target_parcel = plan["parcel_id"]
        avoid = {cell for parcel_id, cell in pickups.items()
                 if parcel_id != target_parcel and parcel_id not in collected and parcel_id not in delivered}
        if plan["cue"] == "after_gate_a" and not gate_seen:
            walk(gate_a, set(pickups.values()))
        walk(pickups[target_parcel], avoid)
        assert carrying == target_parcel, (target_parcel, carrying)
        destination = destinations[plan["destination_id"]]
        walk(destination)
        if plan["cue"] == "before_bell":
            assert moves < config["bell"]["after_moves"], (plan, moves, config["bell"])
        elif plan["cue"] == "after_bell":
            # Rack legal movement while carrying if a future config changes its
            # cutoff, using an adjacent edge and returning before delivery.
            while moves < config["bell"]["after_moves"]:
                board_walls = {tuple(cell) for cell in board["walls"]}
                neighbor = next((nxt for dx, dy in DIRECTIONS.values()
                                 if 0 <= (nxt := (pos[0] + dx, pos[1] + dy))[0] < board["cols"]
                                 and 0 <= nxt[1] < board["rows"] and nxt not in board_walls), None)
                assert neighbor is not None
                first_direction = next(direction for direction, delta in DIRECTIONS.items()
                                       if (pos[0] + delta[0], pos[1] + delta[1]) == neighbor)
                actions.append({"sequence": len(actions) + 1, "action_type": "move", "payload": {"direction": first_direction}})
                moves += 1
                if neighbor == gate_a:
                    gate_seen = True
                back_direction = next(direction for direction, delta in DIRECTIONS.items()
                                      if (neighbor[0] + delta[0], neighbor[1] + delta[1]) == pos)
                actions.append({"sequence": len(actions) + 1, "action_type": "move", "payload": {"direction": back_direction}})
                moves += 1
                if pos == gate_a:
                    gate_seen = True
        else:
            assert gate_seen
        actions.append({"sequence": len(actions) + 1, "action_type": "deliver", "payload": {"parcel_id": carrying}})
        delivered.add(carrying)
        carrying = None

    if revisit_first_pickup and config["plans"]:
        first_pickup = pickups[config["plans"][0]["parcel_id"]]
        walk(first_pickup)
    return actions


def legacy_witnesses() -> None:
    # Tutorial infeasible before-bell witness (kept stable as v1 history).
    tutorial = generate("HY-01", "courier-feasibility-4", "tutorial", "tutorial")
    first = tutorial["plans"][0]
    moves = path(tutorial, tuple(tutorial["board"]["start"]),
                 tuple(next(p["cell"] for p in tutorial["parcels"] if p["parcel_id"] == first["parcel_id"])))
    start = tuple(next(p["cell"] for p in tutorial["parcels"] if p["parcel_id"] == first["parcel_id"]))
    dest = tuple(next(d["cell"] for d in tutorial["destinations"] if d["destination_id"] == first["destination_id"]))
    moves += path(tutorial, start, dest)
    assert len(moves) == 7 and tutorial["bell"]["after_moves"] == 6

    # Tier-3 v1 has four plans but plot A and D alias. Delivering parcel-1 at
    # its declared cell is decoded as a plot-D delivery by the unchanged evaluator.
    tier3 = generate("HY-01", "courier-feasibility-0", "training", "tier-3")
    assert len(tier3["plans"]) == 4
    cells = [tuple(d["cell"]) for d in tier3["destinations"]]
    assert len(set(cells)) == 3
    p1 = tier3["plans"][0]
    pcell = tuple(next(p["cell"] for p in tier3["parcels"] if p["parcel_id"] == p1["parcel_id"]))
    dcell = tuple(next(d["cell"] for d in tier3["destinations"] if d["destination_id"] == p1["destination_id"]))
    other_pickups = {tuple(p["cell"]) for p in tier3["parcels"] if p["parcel_id"] != p1["parcel_id"]}
    acts: list[dict] = []
    position = tuple(tier3["board"]["start"])
    for target in (pcell, dcell):
        for direction in path(tier3, position, target, other_pickups):
            acts.append({"sequence": len(acts) + 1, "action_type": "move", "payload": {"direction": direction}})
            dx, dy = DIRECTIONS[direction]
            position = (position[0] + dx, position[1] + dy)
    acts.append({"sequence": len(acts) + 1, "action_type": "deliver", "payload": {"parcel_id": p1["parcel_id"]}})
    old_result = evaluate("HY-01", tier3, acts)
    assert next(row for row in old_result["promises"] if row["parcel_id"] == p1["parcel_id"])["delivered_at"] == "plot-D"

    # V1 permits a repeated pickup/delivery after revisiting the source cell.
    lifecycle = generate("HY-01", "courier-parcel-lifecycle-0", "training", "tier-1")
    p1 = lifecycle["plans"][0]
    pcell = tuple(next(p["cell"] for p in lifecycle["parcels"] if p["parcel_id"] == p1["parcel_id"]))
    dcell = tuple(next(d["cell"] for d in lifecycle["destinations"] if d["destination_id"] == p1["destination_id"]))
    other_pickups = {tuple(p["cell"]) for p in lifecycle["parcels"] if p["parcel_id"] != p1["parcel_id"]}
    acts = []
    position = tuple(lifecycle["board"]["start"])
    for target in (pcell, dcell, pcell, dcell):
        for direction in path(lifecycle, position, target, other_pickups):
            acts.append({"sequence": len(acts) + 1, "action_type": "move", "payload": {"direction": direction}})
            dx, dy = DIRECTIONS[direction]
            position = (position[0] + dx, position[1] + dy)
        if target == dcell:
            acts.append({"sequence": len(acts) + 1, "action_type": "deliver", "payload": {"parcel_id": p1["parcel_id"]}})
    old_result = evaluate("HY-01", lifecycle, acts)
    assert sum(row["parcel_id"] == p1["parcel_id"] and row["valid"] for row in old_result["deliveries"]) == 2


def main() -> None:
    legacy_witnesses()
    all_tiers = ("tutorial", "tier-1", "tier-2", "tier-3")
    total = 0
    for tier in all_tiers:
        mode = "tutorial" if tier == "tutorial" else "training"
        layouts: set[tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]] = set()
        for seed_index in range(60):
            seed = f"courier-v2-oracle-{tier}-{seed_index}"
            config = courier_v2.generate(seed, mode, tier)
            assert courier_v2.generate(seed, mode, tier) == config
            assert config["activity_version"] == courier_v2.VERSION
            assert "solution" not in config and "witness" not in config and "oracle" not in config
            plan_ids = [plan["destination_id"] for plan in config["plans"]]
            destination_cells = [tuple(dest["cell"]) for dest in config["destinations"]]
            parcel_cells = [tuple(parcel["cell"]) for parcel in config["parcels"]]
            reserved = {tuple(config["board"]["start"]), *destination_cells, *parcel_cells}
            assert len(set(plan_ids)) == len(plan_ids) == len(destination_cells)
            assert len(set(destination_cells)) == len(destination_cells)
            assert len(set(parcel_cells)) == len(parcel_cells)
            assert not (set(parcel_cells) & set(destination_cells))
            if seed_index < 20:
                layouts.add((tuple(parcel_cells), tuple(destination_cells)))
            assert not (set(tuple(wall) for wall in config["board"]["walls"]) & reserved)
            actions = route_actions(config)
            result = courier_v2.evaluate(config, actions)
            assert result["promises_satisfied"] == result["promises_total"] == len(config["plans"]), (tier, seed, result)
            ids = [row["parcel_id"] for row in result["deliveries"] if row["valid"]]
            assert ids == [plan["parcel_id"] for plan in config["plans"]]
            assert len(result["pickups"]) == len(config["plans"])
            assert len({row["parcel_id"] for row in result["pickups"]}) == len(config["plans"])
            assert result["gates_visited"].count("gate-a") <= 1
            if any(plan["cue"] == "after_gate_a" for plan in config["plans"]):
                assert result["gates_visited"].count("gate-a") == 1
            actual_moves = sum(action["action_type"] == "move" for action in actions)
            assert 0 <= result["optimal_moves"] <= actual_moves, (tier, seed, result["optimal_moves"], actual_moves)
            total += 1
        assert len(layouts) >= 12, (tier, len(layouts))

    # Route-level integration and immutable legacy start replay on a disposable DB.
    with tempfile.TemporaryDirectory(prefix="courier-v2-") as temp:
        os.environ["AI4BRAIN_DB"] = str(Path(temp) / "courier.sqlite3")
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app import hybrid_store as hs
        with TestClient(app) as client:
            session = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True})
            assert session.status_code == 201, session.text
            sid = session.json()["id"]
            catalog = client.get("/api/hybrid/catalog").json()
            meta = next(row for row in catalog["activities"] if row["activity_id"] == "HY-01")
            assert meta["activity_version"] == courier_v2.VERSION and meta["config_version"] == "2"
            v2_body = {"event_id": str(uuid.uuid4()), "session_id": sid, "activity_id": "HY-01",
                       "activity_version": courier_v2.VERSION, "config_version": "2", "mode": "training",
                       "difficulty_tier": "tier-3", "seed": "api-tier3"}
            started = client.post("/api/hybrid/attempts", json=v2_body)
            assert started.status_code == 201, started.text
            assert started.json()["config"]["activity_version"] == courier_v2.VERSION
            assert "solution" not in started.json()["config"]
            api_attempt_id = started.json()["attempt_id"]
            api_actions = route_actions(started.json()["config"])
            for action_index, action in enumerate(api_actions):
                action_body = {
                    "attempt_id": api_attempt_id, "event_id": str(uuid.uuid4()),
                    "sequence": action["sequence"], "action_type": action["action_type"],
                    "payload": action["payload"],
                }
                response = client.post(f"/api/hybrid/attempts/{api_attempt_id}/actions", json=action_body)
                assert response.status_code == 201, response.text
                if action_index == 0:
                    # Model a lost response: retry the exact event body, then
                    # prove that a payload change under that identity is rejected.
                    replay = client.post(f"/api/hybrid/attempts/{api_attempt_id}/actions", json=action_body)
                    assert replay.status_code == 201 and replay.json()["replayed"] is True, replay.text
                    changed = {**action_body, "payload": {**action_body["payload"], "direction": "down"}}
                    if changed["payload"] == action_body["payload"]:
                        changed["payload"]["direction"] = "up"
                    assert client.post(f"/api/hybrid/attempts/{api_attempt_id}/actions", json=changed).status_code == 409
            completed = client.post(f"/api/hybrid/attempts/{api_attempt_id}/complete", json={
                "attempt_id": api_attempt_id, "event_id": str(uuid.uuid4()),
            })
            assert completed.status_code == 200, completed.text
            assert completed.json()["evaluation_version"] == courier_v2.EVALUATION_VERSION
            assert completed.json()["outcomes"]["promises_satisfied"] == completed.json()["outcomes"]["promises_total"] == 4
            assert client.post("/api/hybrid/attempts", json={**v2_body, "event_id": str(uuid.uuid4()),
                                                                "activity_version": "hy-01-v1", "config_version": "1"}).status_code == 409

            # Simulate an attempt persisted by the prior release. Only its exact
            # start-event retry may use v1 after v2 becomes catalog-current.
            old_body = {"event_id": str(uuid.uuid4()), "session_id": sid, "learner_id": "demo-user",
                        "activity_id": "HY-01", "activity_version": "hy-01-v1", "config_version": "1",
                        "mode": "training", "difficulty_tier": "tier-1", "seed": "legacy-start-seed"}
            old_config = generate("HY-01", old_body["seed"], old_body["mode"], old_body["difficulty_tier"])
            old_attempt_id = str(uuid.uuid4())
            old_payload = {"event_type": "hybrid_attempt_started", "attempt_id": old_attempt_id,
                           "session_id": sid, "learner_id": "demo-user", "activity_id": "HY-01",
                           "activity_version": "hy-01-v1", "mode": "training", "config_version": "1",
                           "difficulty_tier": "tier-1", "seed": old_body["seed"],
                           "hybrid_schema_version": "hybrid-v1"}
            hs.create_attempt(store, {"attempt_id": old_attempt_id, "learner_id": "demo-user", "session_id": sid,
                "activity_id": "HY-01", "activity_version": "hy-01-v1", "mode": "training", "config_version": "1",
                "difficulty_tier": "tier-1", "seed": old_body["seed"], "config": old_config,
                "event_id": old_body["event_id"], "event_payload": old_payload})
            replay = client.post("/api/hybrid/attempts", json=old_body)
            assert replay.status_code == 201 and replay.json()["attempt_id"] == old_attempt_id, replay.text
            assert client.post("/api/hybrid/attempts", json={**old_body, "difficulty_tier": "tier-2"}).status_code == 409
            assert client.post("/api/hybrid/attempts", json={**old_body, "event_id": str(uuid.uuid4())}).status_code == 409

    print(f"courier_v2_smoke: PASS; {total} independent solved-route cases across all tiers; uniqueness, lifecycle, cue windows, no-leak config; three v1 witness regressions; v1 exact-start replay and v2 route integration.")


if __name__ == "__main__":
    main()
