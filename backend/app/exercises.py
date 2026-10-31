from __future__ import annotations

from copy import deepcopy
import hashlib
import random
from typing import Any

from .difficulty import DECISION_TRIAL_COUNT
from .contracts import EXERCISE_VERSION, LEGACY_TRAINING_EXERCISE_VERSION, TRAINING_EXERCISE_VERSION, ExerciseConfig, ExerciseItem, PatternChoice, Tile

# Original, fixed 2x2 nonverbal templates. These do not reproduce commercial tests.
# All choices are structured tiles so clients can render each shape with SVG.

def tile(shape: str, count: int = 1, fill: str = "outline", rotation: int = 0) -> dict[str, Any]:
    return {"shape": shape, "count": count, "fill": fill, "rotation": rotation}

def item(item_id: str, rule: str, pattern: dict, choices: dict[str, dict], answer: str, difficulty: str) -> dict[str, Any]:
    return {"item_id": item_id, "rule_type": rule, "pattern": pattern, "choices": choices, "answer": answer, "difficulty": difficulty}

_ITEMS = [
    item("reasoning-pattern-001", "count_across_rows", {
        "top_left":tile("circle",1), "top_right":tile("circle",2), "bottom_left":tile("triangle",1), "bottom_right":None},
        {"A":tile("triangle",3),"B":tile("triangle",2),"C":tile("triangle",1),"D":tile("circle",2)}, "B", "baseline-medium"),
    item("reasoning-pattern-002", "clockwise_rotation", {
        "top_left":tile("arrow",rotation=0), "top_right":tile("arrow",rotation=90), "bottom_left":tile("arrow",rotation=180), "bottom_right":None},
        {"A":tile("arrow",rotation=270),"B":tile("arrow",rotation=90),"C":tile("arrow",rotation=180),"D":tile("arrow",rotation=0)}, "A", "baseline-medium"),
    item("reasoning-pattern-003", "alternating_fill", {
        "top_left":tile("circle",1,"outline"), "top_right":tile("circle",1,"solid"), "bottom_left":tile("circle",1,"solid"), "bottom_right":None},
        {"A":tile("circle",1,"solid"),"B":tile("triangle",1,"outline"),"C":tile("circle",1,"outline"),"D":tile("square",1,"outline")}, "C", "baseline-medium"),
    item("reasoning-pattern-004", "count_across_rows", {
        "top_left":tile("square",1), "top_right":tile("square",2), "bottom_left":tile("diamond",1), "bottom_right":None},
        {"A":tile("diamond",1),"B":tile("diamond",3),"C":tile("diamond",2),"D":tile("square",2)}, "C", "baseline-medium"),
    item("reasoning-pattern-005", "counterclockwise_rotation", {
        "top_left":tile("arrow",rotation=0), "top_right":tile("arrow",rotation=270), "bottom_left":tile("arrow",rotation=180), "bottom_right":None},
        {"A":tile("arrow",rotation=90),"B":tile("arrow",rotation=270),"C":tile("arrow",rotation=180),"D":tile("arrow",rotation=0)}, "A", "baseline-medium"),
    item("reasoning-pattern-006", "alternating_shape", {
        "top_left":tile("circle"), "top_right":tile("triangle"), "bottom_left":tile("triangle"), "bottom_right":None},
        {"A":tile("square"),"B":tile("circle"),"C":tile("triangle"),"D":tile("diamond")}, "B", "baseline-medium"),
]
_PRACTICE = item("reasoning-practice-001", "count_across_rows", {
    "top_left":tile("square",1), "top_right":tile("square",2), "bottom_left":tile("circle",1), "bottom_right":None},
    {"A":tile("circle",3),"B":tile("circle",2),"C":tile("circle",1),"D":tile("square",2)}, "B", "practice")
ANSWER_KEY = {row["item_id"]: row["answer"] for row in _ITEMS + [_PRACTICE]}
ITEM_BANK = {row["item_id"]: row for row in _ITEMS + [_PRACTICE]}
BASELINE_ITEM_IDS = [row["item_id"] for row in _ITEMS]


def expected_tile(item_data: dict[str, Any]) -> dict[str, Any]:
    rule = item_data["rule_type"]
    p = item_data["pattern"]
    tl, tr, bl = p["top_left"], p["top_right"], p["bottom_left"]
    if rule == "count_across_rows": return {**bl, "count": tr["count"]}
    if rule.startswith("count_step_"): return {**bl, "count": bl["count"] + int(rule.rsplit("_", 1)[1])}
    if rule == "clockwise_rotation": return {**bl, "rotation": (bl["rotation"] + 90) % 360}
    if rule.startswith("clockwise_step_"): return {**bl, "rotation": (bl["rotation"] + int(rule.rsplit("_", 1)[1])) % 360}
    if rule == "counterclockwise_rotation": return {**bl, "rotation": (bl["rotation"] - 90) % 360}
    if rule == "alternating_fill": return {**tr, "fill": tl["fill"]}
    if rule == "alternating_shape": return {**tr, "shape": tl["shape"]}
    if rule == "compound_shape_count": return {**bl, "count": tr["count"]}
    if rule == "compound_shape_fill": return {**bl, "fill": tr["fill"]}
    if rule == "compound_shape_rotation": return {**bl, "rotation": tr["rotation"]}
    if rule == "compound_count_rotation": return {**tr, "rotation": bl["rotation"]}
    if rule == "compound_shape_count_fill": return {**bl, "count": tr["count"], "fill": tr["fill"]}
    raise ValueError(f"unknown template rule {rule}")


def public_item(item_data: dict[str, Any]) -> ExerciseItem:
    return ExerciseItem(item_id=item_data["item_id"], prompt="Select the tile that completes the 2x2 pattern.",
        pattern=item_data["pattern"], choices=[PatternChoice(choice_id=k, tile=v) for k,v in item_data["choices"].items()], difficulty=item_data["difficulty"])


def _make_training_bank_v1(tier: str) -> list[dict[str, Any]]:
    level = {"tier-1": 1, "tier-2": 2, "tier-3": 3}.get(tier)
    if level is None: raise ValueError("tier must be tier-1, tier-2, or tier-3")
    rows=[]
    for index, kind in enumerate(("count", "rotation", "fill", "shape"), start=1):
        item_id=f"reasoning-training-{tier}-{index:02d}"
        if kind == "count":
            start=1; finish=1+level
            pattern={"top_left":tile("circle",start),"top_right":tile("circle",finish),"bottom_left":tile("triangle",start),"bottom_right":None}
            rule=f"count_step_{level}"
        elif kind == "rotation":
            step=90*level
            pattern={"top_left":tile("arrow",rotation=0),"top_right":tile("arrow",rotation=step),"bottom_left":tile("arrow",rotation=180),"bottom_right":None}
            rule=f"clockwise_step_{step}"
        elif kind == "fill":
            pattern={"top_left":tile("circle",1,"outline"),"top_right":tile("circle",1,"solid"),"bottom_left":tile("circle",1,"solid"),"bottom_right":None}
            rule="alternating_fill"
        else:
            pattern={"top_left":tile("circle"),"top_right":tile("triangle"),"bottom_left":tile("triangle"),"bottom_right":None}
            rule="alternating_shape"
        provisional={"item_id":item_id,"rule_type":rule,"pattern":pattern,"difficulty":tier,"choices":{},"answer":""}
        expected=expected_tile(provisional)
        alternatives=[]
        for candidate in (
            {**expected,"shape":"diamond" if expected["shape"] != "diamond" else "square"},
            {**expected,"count":expected["count"] % 4 + 1},
            {**expected,"fill":"solid" if expected["fill"] == "outline" else "outline"},
            {**expected,"rotation":(expected["rotation"]+90)%360},
        ):
            if candidate != expected and candidate not in alternatives: alternatives.append(candidate)
        options=[expected,*alternatives[:3]]
        correct_index=(level+index-1)%4
        options[0],options[correct_index]=options[correct_index],options[0]
        choice_map={letter:value for letter,value in zip(("A","B","C","D"), options)}
        answer=("A","B","C","D")[correct_index]
        provisional["choices"]=choice_map; provisional["answer"]=answer
        if len({str(v) for v in choice_map.values()}) != 4: raise AssertionError(f"duplicate training choices: {item_id}")
        if sum(value == expected for value in choice_map.values()) != 1: raise AssertionError(f"ambiguous training item: {item_id}")
        rows.append(provisional)
    return rows


def _seed(block_id: str, tier: str) -> int:
    return int(hashlib.sha256(f"{block_id}:{tier}:EX-02-v2".encode()).hexdigest()[:16], 16)


def _make_training_bank_v2(tier: str, block_id: str) -> list[dict[str, Any]]:
    level = {"tier-1": 1, "tier-2": 2, "tier-3": 3}.get(tier)
    if level is None:
        raise ValueError("tier must be tier-1, tier-2, or tier-3")
    rng = random.Random(_seed(block_id, tier))
    families = {
        1: ["compound_shape_count", "compound_shape_fill"],
        2: ["compound_shape_count", "compound_shape_fill", "compound_shape_rotation", "compound_count_rotation"],
        3: ["compound_shape_count", "compound_shape_fill", "compound_shape_rotation", "compound_count_rotation", "compound_shape_count_fill"],
    }[level]
    rows = []
    for index in range(8):
        rule = families[index % len(families)]
        item_id = f"reasoning-training-{tier}-{index + 1:02d}"
        start_count = 1
        finish_count = min(4, level + 1)
        step = 90 * level
        if rule == "compound_shape_count":
            pattern = {"top_left": tile("circle", start_count), "top_right": tile("circle", finish_count),
                       "bottom_left": tile("triangle", start_count), "bottom_right": None}
        elif rule == "compound_shape_fill":
            pattern = {"top_left": tile("circle", 1, "outline"), "top_right": tile("circle", 1, "solid"),
                       "bottom_left": tile("diamond", 1, "outline"), "bottom_right": None}
        elif rule == "compound_shape_rotation":
            pattern = {"top_left": tile("square", rotation=0), "top_right": tile("square", rotation=step),
                       "bottom_left": tile("triangle", rotation=0), "bottom_right": None}
        elif rule == "compound_count_rotation":
            pattern = {"top_left": tile("arrow", start_count, rotation=0), "top_right": tile("arrow", finish_count, rotation=0),
                       "bottom_left": tile("arrow", start_count, rotation=step), "bottom_right": None}
        else:
            pattern = {"top_left": tile("circle", start_count, "outline"), "top_right": tile("circle", finish_count, "solid"),
                       "bottom_left": tile("diamond", start_count, "outline"), "bottom_right": None}
        provisional = {"item_id": item_id, "rule_type": rule, "pattern": pattern, "difficulty": tier, "choices": {}, "answer": ""}
        expected = expected_tile(provisional)
        tl, tr, bl = pattern["top_left"], pattern["top_right"], pattern["bottom_left"]
        # Plausible single-rule answers: copy the horizontal result, vertical result,
        # or original tile. The fourth is the only compound-rule completion.
        candidates = [dict(expected), dict(tr), dict(bl), dict(tl)]
        # The component alternatives are deliberately distinct even at tier 1.
        for candidate in candidates:
            candidate["count"] = max(1, min(4, candidate["count"]))
            candidate["rotation"] %= 360
        if len({str(row) for row in candidates}) != 4:
            # The shape-only family can collide with a copy distractor; create a
            # credible count-only distractor while keeping the correct tile unique.
            alternate = dict(expected)
            alternate["count"] = 4 if expected["count"] != 4 else 2
            candidates[-1] = alternate
        if len({str(row) for row in candidates}) != 4:
            raise AssertionError(f"compound reasoning choices are not unique: {item_id}")
        rng.shuffle(candidates)
        choice_map = {letter: value for letter, value in zip(("A", "B", "C", "D"), candidates)}
        answer = next(letter for letter, value in choice_map.items() if value == expected)
        provisional["choices"] = choice_map
        provisional["answer"] = answer
        rows.append(provisional)
    return rows


def make_training_bank(tier: str, block_id: str | None = None,
                       version: str = LEGACY_TRAINING_EXERCISE_VERSION) -> list[dict[str, Any]]:
    if version == LEGACY_TRAINING_EXERCISE_VERSION:
        return _make_training_bank_v1(tier)
    if version != TRAINING_EXERCISE_VERSION:
        raise ValueError("unsupported reasoning training exercise version")
    return _make_training_bank_v2(tier, block_id or f"preview:EX-02:{tier}")


def public_exercise(phase: str, tier: str | None = None, block_id: str | None = None,
                    version: str | None = None) -> ExerciseConfig:
    if phase == "practice": rows = [_PRACTICE]
    elif phase == "baseline": rows = _ITEMS
    elif phase == "training" and tier:
        resolved_version = version or LEGACY_TRAINING_EXERCISE_VERSION
        rows = make_training_bank(tier, block_id, resolved_version)
    else: raise ValueError("phase/tier combination is unavailable")
    resolved_version = (version or LEGACY_TRAINING_EXERCISE_VERSION) if phase == "training" else EXERCISE_VERSION
    return ExerciseConfig(phase=phase, exercise_version=resolved_version, items=[public_item(row) for row in rows],
        instructions="Look at the four-cell pattern. Choose the tile that completes it.",
        scoring=None if phase != "baseline" else "Preliminary task index is computed by the server from six valid baseline responses.",
        difficulty_tier=tier, training_block_id=block_id, challenge_seed=block_id,
        decision_trial_count=DECISION_TRIAL_COUNT if phase == "training" else None)


def evaluate(item_id: str, choice: str, item_data: dict[str, Any] | None = None) -> tuple[bool, str | None]:
    data = item_data or ITEM_BANK.get(item_id)
    if data is None:
        data = next((row for tier in ("tier-1","tier-2","tier-3") for row in _make_training_bank_v1(tier) if row["item_id"] == item_id), None)
    if data is None: raise KeyError("unknown item")
    if choice not in data["choices"]: raise ValueError("choice is not one of the item's options")
    correct = data["choices"][choice] == expected_tile(data)
    return correct, None if correct else data["rule_type"]


def verify_bank() -> None:
    for data in _ITEMS + [_PRACTICE]:
        if len(data["choices"]) != 4 or len({str(v) for v in data["choices"].values()}) != 4:
            raise AssertionError(f"invalid or duplicate choices: {data['item_id']}")
        expected = expected_tile(data)
        answers = [key for key, value in data["choices"].items() if value == expected]
        if len(answers) != 1 or answers[0] != data["answer"]:
            raise AssertionError(f"pattern does not have exactly one correct choice: {data['item_id']}")
        for key in data["choices"]:
            result, _ = evaluate(data["item_id"], key)
            if result != (key == data["answer"]):
                raise AssertionError(f"incorrect scorer mapping: {data['item_id']} {key}")

verify_bank()

