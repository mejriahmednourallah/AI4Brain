"""Versioned remembered-order and visible-rule switching activity (HY-03)."""
from __future__ import annotations

import hashlib
import random
from typing import Any

VERSION = "hy-03-v1"
EVALUATION_VERSION = "hy-03-eval-v1"
LIMITATIONS = [
    "Descriptive activity outcomes only; this activity is not one of the five fixed baseline indices.",
    "Order and routing are evaluated from the recorded sequence of committed token choices.",
]
def public_config(config:dict[str,Any])->dict[str,Any]:return {k:v for k,v in config.items() if not k.startswith("_")}
COUNTS = {"tutorial": (4, 9000), "tier-1": (4, 7000), "tier-2": (5, 6000), "tier-3": (6, 5000)}
TOKEN_VALUES = [(c, s) for c in ("amber", "teal", "violet") for s in ("circle", "square", "triangle")]


def generate(seed: str, mode: str, tier: str) -> dict[str, Any]:
    count, encode_ms = COUNTS.get("tutorial" if mode == "tutorial" else tier, COUNTS["tier-1"])
    rng = random.Random(int(hashlib.sha256(f"{seed}|{VERSION}|{mode}|{tier}".encode()).hexdigest()[:16], 16))
    values = TOKEN_VALUES[:]
    rng.shuffle(values)
    cargo = [{"cargo_id": f"cargo-{i + 1}", "color": values[i][0], "shape": values[i][1],
              "label": f"{values[i][0].title()} {values[i][1]}"} for i in range(count)]
    order = [item["cargo_id"] for item in cargo]
    rng.shuffle(order)
    switch_after = max(2, count // 2)
    return {
        "activity_id": "HY-03", "activity_version": VERSION, "config_version": "1",
        "mode": mode, "tier": tier, "seed": seed, "encode_ms": encode_ms,
        "cargo": cargo, "study_sequence": order, "_oracle_order": order,
        "switch": {"after_step": switch_after, "from_rule": "color", "to_rule": "shape",
                   "cue": f"After {switch_after} deliveries, switch from color to shape."},
        "rules": {"color_bins": {"amber": "amber-tray", "teal": "teal-tray", "violet": "violet-tray"},
                  "shape_bins": {"circle": "circle-bin", "square": "square-bin", "triangle": "triangle-bin"}},
        "assistance_windows": ["pre_play", "boundary"],
    }


def evaluate(config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    cargo = {item["cargo_id"]: item for item in config["cargo"]}
    target = config["_oracle_order"]
    threshold = int(config["switch"]["after_step"])
    routed: list[dict[str, Any]] = []
    for action in actions:
        if action.get("action_type") != "select":
            continue
        payload = action.get("payload") or {}
        cargo_id = payload.get("cargo_id")
        if cargo_id not in cargo:
            continue
        index = len(routed)
        rule = "color" if index < threshold else "shape"
        item = cargo[cargo_id]
        value = item["color"] if rule == "color" else item["shape"]
        bins = config["rules"][f"{rule}_bins"]
        expected = bins[value]
        routed.append({"event_id": action.get("event_id"), "step": index + 1, "cargo_id": cargo_id,
                       "selected_bin": payload.get("bin_id"), "expected_bin": expected,
                       "active_rule": rule, "order_correct": index < len(target) and cargo_id == target[index],
                       "route_correct": payload.get("bin_id") == expected})
    order_errors = [{"step": row["step"], "expected": target[row["step"] - 1], "selected": row["cargo_id"]}
                    for row in routed if not row["order_correct"]]
    route_errors = [{"step": row["step"], "cargo_id": row["cargo_id"], "rule": row["active_rule"],
                     "expected_bin": row["expected_bin"], "selected_bin": row["selected_bin"]}
                    for row in routed if not row["route_correct"]]
    used = [row["cargo_id"] for row in routed]
    return {
        "activity_id": "HY-03", "evaluation_version": EVALUATION_VERSION,
        "deliveries": len(routed), "expected_deliveries": len(target),
        "shipment_order_matches": sum(row["order_correct"] for row in routed),
        "shipment_order_total": len(target), "routing_matches": sum(row["route_correct"] for row in routed),
        "routing_total": len(routed), "switch_after_step": threshold,
        "rule_before_switch": "color", "rule_after_switch": "shape",
        "order_errors": order_errors, "routing_errors": route_errors,
        "omitted_cargo": [cargo_id for cargo_id in target if cargo_id not in used],
        "duplicate_deliveries": len(used) - len(set(used)), "delivery_history": routed,
        "first_conflict": (order_errors[0] if order_errors else (route_errors[0] if route_errors else None)),
    }
