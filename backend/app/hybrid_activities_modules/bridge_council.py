"""Deterministic graph, constraints, advice and route evaluator for HY-06."""
from __future__ import annotations

import hashlib
import random
from typing import Any

VERSION = "hy-06-v1"
EVALUATION_VERSION = "hy-06-eval-v1"
LIMITATIONS = [
    "Descriptive activity outcomes only; this activity is not one of the five fixed baseline indices.",
    "Route feasibility and shortest cost are evaluated against this attempt's recorded graph and constraints.",
    "Challenge advice scenarios are generated stimuli, not evidence that an external AI system made a claim.",
]

BASE_NODES = [
    {"node_id": "harbor", "label": "Harbor", "kind": "start"},
    {"node_id": "key-island", "label": "Key Island", "kind": "key"},
    {"node_id": "old-bridge", "label": "Old Bridge", "kind": "crossing"},
    {"node_id": "northbank", "label": "Northbank", "kind": "island"},
    {"node_id": "lighthouse", "label": "Lighthouse", "kind": "goal"},
]
BASE_EDGES = [
    ("harbor-key", "harbor", "key-island", False, False),
    ("key-old", "key-island", "old-bridge", False, False),
    ("old-light", "old-bridge", "lighthouse", False, True),
    ("harbor-old", "harbor", "old-bridge", False, False),
    ("key-north", "key-island", "northbank", False, False),
    ("north-light", "northbank", "lighthouse", False, False),
    ("old-north", "old-bridge", "northbank", False, False),
    ("short-closed", "harbor", "lighthouse", True, False),
]


def generate(seed: str, mode: str, tier: str) -> dict[str, Any]:
    rng = random.Random(int(hashlib.sha256(f"{seed}|{VERSION}|{mode}|{tier}".encode()).hexdigest()[:16], 16))
    edges = [{"edge_id": edge_id, "from_node": a, "to_node": b, "closed": closed,
              "requires_key": needs_key, "weight": rng.randint(1, 4)}
             for edge_id, a, b, closed, needs_key in BASE_EDGES]
    nodes = [dict(node) for node in BASE_NODES]
    scenario_roll = int(hashlib.sha256(f"{seed}|advice".encode()).hexdigest()[:4], 16) % 3
    advice_kind = ("correct", "incorrect", "uncertain")[scenario_roll]
    if advice_kind == "correct":
        suggested = shortest_route(nodes, edges)
        advice = {"advice_id": "council-advice-1", "kind": advice_kind, "confidence": "supported",
                  "suggested_route": suggested["route"], "text": "This route reaches the Lighthouse using the open bridges and the key before the gated crossing.",
                  "evidence_refs": ["constraint-key-before-gate", "edge-short-closed"]}
    elif advice_kind == "incorrect":
        advice = {"advice_id": "council-advice-1", "kind": advice_kind, "confidence": "asserted",
                  "suggested_route": ["harbor", "old-bridge", "lighthouse"],
                  "text": "Take the Old Bridge straight to the Lighthouse; no key is needed.",
                  "evidence_refs": ["constraint-key-before-gate"]}
    else:
        advice = {"advice_id": "council-advice-1", "kind": advice_kind, "confidence": "uncertain",
                  "suggested_route": None,
                  "text": "I cannot verify whether the Old Bridge has a key restriction from the available note.",
                  "evidence_refs": ["constraint-key-before-gate"]}
    return {
        "activity_id": "HY-06", "activity_version": VERSION, "config_version": "1", "mode": mode,
        "tier": tier, "seed": seed, "nodes": nodes, "edges": edges,
        "start_node": "harbor", "goal_node": "lighthouse", "key_node": "key-island",
        "constraints": [
            {"constraint_id": "constraint-key-before-gate", "kind": "key_before_gate", "text": "Visit Key Island before crossing any bridge marked as requiring the key."},
            {"constraint_id": "edge-short-closed", "kind": "closed_edge", "edge_id": "short-closed", "text": "The direct Harbor–Lighthouse bridge is closed."},
        ],
        "advice": advice, "assistance_windows": ["advice_checkpoint", "post_commit"],
    }


def _adjacency(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        result.setdefault(edge["from_node"], []).append({**edge, "next": edge["to_node"]})
        result.setdefault(edge["to_node"], []).append({**edge, "next": edge["from_node"]})
    return result


def route_check(config: dict[str, Any], route: list[str]) -> dict[str, Any]:
    nodes = {node["node_id"] for node in config["nodes"]}
    edges = {edge["edge_id"]: edge for edge in config["edges"]}
    adj = _adjacency(config["edges"])
    violations: list[dict[str, Any]] = []
    weight = 0
    if not route or route[0] != config["start_node"]:
        violations.append({"constraint_id": "route-start", "reason": "route must start at Harbor"})
    if not route or route[-1] != config["goal_node"]:
        violations.append({"constraint_id": "route-goal", "reason": "route must end at the Lighthouse"})
    if any(node not in nodes for node in route):
        violations.append({"constraint_id": "unknown-node", "reason": "route contains an unknown island"})
    visited_key = config["key_node"] in route
    used_edges = []
    for index, (source, target) in enumerate(zip(route, route[1:])):
        edge = next((e for e in adj.get(source, []) if e["next"] == target), None)
        if edge is None:
            violations.append({"constraint_id": "no-bridge", "reason": f"no bridge joins {source} and {target}"})
            continue
        used_edges.append(edge["edge_id"])
        weight += int(edge["weight"])
        if edge["closed"]:
            violations.append({"constraint_id": "edge-short-closed", "edge_id": edge["edge_id"], "reason": "the bridge is closed"})
        if edge["requires_key"] and config["key_node"] not in route[:index + 1]:
            violations.append({"constraint_id": "constraint-key-before-gate", "edge_id": edge["edge_id"], "reason": "the key was not collected before this bridge"})
    feasible = bool(route and route[0] == config["start_node"] and route[-1] == config["goal_node"]
                    and all(node in nodes for node in route) and not violations)
    return {"route": route, "feasible": feasible, "weight": weight, "used_edges": used_edges, "violations": violations}


def shortest_route(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    config = {"nodes": nodes, "edges": edges, "start_node": "harbor", "goal_node": "lighthouse", "key_node": "key-island"}
    adj = _adjacency(edges)
    best: dict[str, Any] | None = None

    def visit(route: list[str], cost: int) -> None:
        nonlocal best
        current = route[-1]
        if current == config["goal_node"]:
            checked = route_check(config, route)
            if checked["feasible"] and (best is None or cost < best["weight"]):
                best = {"route": route[:], "weight": cost}
            return
        for edge in adj.get(current, []):
            nxt = edge["next"]
            if nxt in route or edge["closed"]:
                continue
            if edge["requires_key"] and config["key_node"] not in route:
                continue
            visit(route + [nxt], cost + int(edge["weight"]))

    visit([config["start_node"]], 0)
    if best is None:
        raise RuntimeError("bridge council generator created no feasible route")
    return best


def evaluate(config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    proposal: list[str] = [config["start_node"]]
    resolution: list[str] = [config["start_node"]]
    stage = "proposal"
    decision: str | None = None
    decision_constraint: str | None = None
    inspected_refs: list[str] = []
    advised = False
    for action in actions:
        kind, payload = action.get("action_type"), action.get("payload") or {}
        action_stage = payload.get("stage", stage)
        if kind == "select" and payload.get("node_id"):
            target = proposal if action_stage == "proposal" else resolution
            target.append(str(payload["node_id"]))
        elif kind == "commit":
            if action_stage == "proposal": stage = "advice"
            elif action_stage == "resolution": stage = "complete"
        elif kind == "advise":
            advised = True
            decision = payload.get("decision")
            decision_constraint = payload.get("constraint_id")
            if payload.get("inspected_refs"):
                inspected_refs.extend(str(value) for value in payload["inspected_refs"])
    proposal_check = route_check(config, proposal)
    final_check = route_check(config, resolution if len(resolution) > 1 else proposal)
    scenario = config["advice"]["kind"]
    suggested = config["advice"].get("suggested_route")
    advice_check = route_check(config, suggested) if suggested else None
    required_refs = set(config["advice"].get("evidence_refs", []))
    inspected_set = set(inspected_refs)
    evidence_checked = bool(required_refs) and required_refs.issubset(inspected_set)
    if scenario == "correct":
        justified = decision in {"accept", "modify"} and final_check["feasible"] and evidence_checked
    elif scenario == "incorrect":
        actual_violation_ids = {v["constraint_id"] for v in (advice_check or {}).get("violations", [])}
        justified = decision == "reject" and decision_constraint in actual_violation_ids and decision_constraint in inspected_set and evidence_checked
    else:
        justified = decision == "hold" and config["advice"]["confidence"] == "uncertain" and evidence_checked
    optimum = shortest_route(config["nodes"], config["edges"])
    return {
        "activity_id": "HY-06", "evaluation_version": EVALUATION_VERSION,
        "proposal": proposal_check, "final_route": final_check,
        "proposal_committed": any(a.get("action_type") == "commit" and (a.get("payload") or {}).get("stage") == "proposal" for a in actions),
        "resolution_committed": any(a.get("action_type") == "commit" and (a.get("payload") or {}).get("stage") == "resolution" for a in actions),
        "advice_inspected": advised, "advice_kind": scenario, "advice_route_check": advice_check,
        "advice_decision": decision, "decision_constraint_id": decision_constraint,
        "inspected_evidence_refs": sorted(set(inspected_refs)), "decision_justified_by_recorded_evidence": bool(justified),
        "shortest_feasible_route": optimum["route"], "shortest_feasible_weight": optimum["weight"],
        "final_route_weight": final_check["weight"], "evidence_refs": [constraint["constraint_id"] for constraint in config["constraints"]],
    }
