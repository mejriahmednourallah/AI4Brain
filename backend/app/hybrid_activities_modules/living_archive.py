"""Deterministic generator and oracle for HY-05 The Living Archive."""
from __future__ import annotations

from itertools import permutations
import hashlib
import random
from typing import Any

VERSION = "hy-05-v1"
EVALUATION_VERSION = "hy-05-eval-v1"
TIERS = {"tutorial": (4, 9000), "tier-1": (4, 7000), "tier-2": (5, 6000), "tier-3": (6, 5000)}
NAMES = ["Amber", "Cobalt", "Jade", "Ivory", "Violet", "Saffron"]
LIMITATIONS = [
    "Descriptive activity outcomes only; this activity is not one of the five fixed baseline indices.",
    "The first reported conflict follows the stored clue order and does not infer why a placement was made.",
]


def generate(seed: str, mode: str, tier: str) -> dict[str, Any]:
    count, encode_ms = TIERS.get("tutorial" if mode == "tutorial" else tier, TIERS["tier-1"])
    rng = random.Random(int(hashlib.sha256(f"{seed}|HY-05|{mode}|{tier}".encode()).hexdigest()[:16], 16))
    objects = NAMES[:count]
    target = list(objects)
    rng.shuffle(target)
    # A complete adjacent chain has exactly one satisfying ordering. The clue
    # order is separately shuffled so review order is deterministic but not spatial.
    constraints = [
        {"clue_id": f"archive-clue-{i + 1}", "left": target[i], "right": target[i + 1],
         "relation": "immediately_left_of",
         "text": f"{target[i]} is immediately to the left of {target[i + 1]}."}
        for i in range(count - 1)
    ]
    rng.shuffle(constraints)
    solutions = [list(order) for order in permutations(objects) if _satisfies(order, constraints)]
    if len(solutions) != 1:
        raise RuntimeError("HY-05 generator did not produce one unique arrangement")
    return {
        "activity_id": "HY-05", "activity_version": VERSION, "config_version": "1",
        "mode": mode, "tier": tier, "seed": seed, "encode_ms": encode_ms,
        "objects": [{"object_id": name, "label": name} for name in objects],
        "slots": list(range(count)), "clues": constraints,
        "assistance_windows": ["pre_encoding", "post_commit"],
    }


def _satisfies(order: list[str], clues: list[dict[str, Any]]) -> bool:
    positions = {name: index for index, name in enumerate(order)}
    return all(positions[c["right"]] == positions[c["left"]] + 1 for c in clues)


def _solutions(config: dict[str, Any]) -> list[list[str]]:
    objects = [item["object_id"] for item in config["objects"]]
    return [list(order) for order in permutations(objects) if _satisfies(list(order), config["clues"])]


def evaluate(config: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    objects = [item["object_id"] for item in config["objects"]]
    placement: list[str | None] = [None] * len(objects)
    placement_history: list[dict[str, Any]] = []
    committed = False
    for action in actions:
        kind = action.get("action_type")
        payload = action.get("payload") or {}
        if kind == "select" and not committed:
            object_id, slot = payload.get("object_id"), payload.get("slot_index")
            if object_id not in objects or not isinstance(slot, int) or not 0 <= slot < len(placement):
                continue
            old_index = placement.index(object_id) if object_id in placement else None
            displaced = placement[slot]
            if old_index is not None:
                placement[old_index] = displaced
            placement[slot] = object_id
            placement_history.append({"event_id": action.get("event_id"), "sequence": action.get("sequence"),
                                      "object_id": object_id, "slot_index": slot,
                                      "displaced_object_id": displaced})
        elif kind == "commit":
            committed = True
            break
    placed = [value if value is not None else "" for value in placement]
    complete = all(placement)
    conflicts = []
    positions = {name: index for index, name in enumerate(placed) if name}
    for clue in config["clues"]:
        left, right = clue["left"], clue["right"]
        valid = left in positions and right in positions and positions[right] == positions[left] + 1
        conflicts.append({"clue_id": clue["clue_id"], "relation": clue["relation"],
                          "left": left, "right": right, "satisfied": bool(valid),
                          "recorded_clue": clue["text"]})
    first = next((item for item in conflicts if not item["satisfied"]), None)
    matches = complete and first is None
    return {
        "activity_id": "HY-05", "evaluation_version": EVALUATION_VERSION,
        "committed": committed, "complete_placement": bool(complete), "valid_arrangement": bool(matches),
        "objects_placed": sum(1 for value in placement if value), "object_count": len(objects),
        "relations_satisfied": sum(1 for item in conflicts if item["satisfied"]),
        "relations_total": len(conflicts), "placement": placement,
        "first_conflict": first, "conflicts": conflicts,
        "placement_history": placement_history,
        "valid_alternatives": _solutions(config),
    }
