"""G0: build the frozen generalisation manifest.

Seventy-two named scenarios across the three human-selected tracks, each with a
development or reserved split label and an expectation expressed as a specification rule
that the evaluator re-derives independently of the application under test.

The file is written once and frozen by SHA-256 in tests/generalisation/FREEZE.json. Re-running
this builder overwrites the manifest, so only run it while the manifest is still development
material; the evaluator refuses a reserved run whose hash differs from the freeze record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "generalisation" / "manifest.json"
FREEZE = ROOT / "tests" / "generalisation" / "FREEZE.json"

FAMILIES = [
    ("EX-01", "working_memory", "Memory"),
    ("EX-02", "reasoning", "Reasoning"),
    ("EX-03", "attention_inhibition", "Attention"),
    ("EX-04", "flexibility", "Flexibility"),
    ("EX-05", "planning", "Planning"),
]
BUDGETS = [4, 5, 8, 20]


def cases() -> list[dict]:
    out: list[dict] = []
    index = 0

    def add(track: str, kind: str, scenario: dict, expectation: dict, note: str) -> None:
        nonlocal index
        index += 1
        out.append({
            "id": f"G{index:03d}",
            "track": track,
            "kind": kind,
            "split": "reserved" if index % 3 == 0 else "development",
            "scenario": scenario,
            "expectation": expectation,
            "note": note,
        })

    # Track 1: task variations â€” response correctness must follow the documented formula.
    for exercise_id, dimension, label in FAMILIES:
        for correct in (True, False):
            for item_index in (0, 1):
                add("variations", "trial_scoring",
                    {"exercise_id": exercise_id, "dimension": dimension, "phase": "baseline",
                     "correct": correct, "item_index": item_index},
                    {"kind": "trial_matches_response", "correct": correct},
                    f"{label} baseline trial {item_index} answered "
                    f"{'correctly' if correct else 'incorrectly'} must be evaluated as "
                    f"{'correct' if correct else 'incorrect'} by the server.")
        for variant, perturbation in (("interrupted", "visibility_interrupted"), ("assisted", "hint")):
            add("variations", "exclusion",
                {"exercise_id": exercise_id, "dimension": dimension, "phase": "baseline",
                 "perturbation": perturbation, "correct": True},
                {"kind": "event_not_unassisted_valid", "perturbation": perturbation},
                f"A correct {label} baseline response recorded with {variant} context must stay "
                f"excluded from valid unassisted evidence.")

    # Track 2: learner situations â€” one scenario per evidence state the brief describes.
    situations = [
        ("empty", {"memory_trials": 0}, {"kind": "recommendation_action", "action": "complete_baseline"},
         "With no saved evidence the policy must request assessment, not training."),
        ("partial", {"memory_trials": 2}, {"kind": "recommendation_action", "action": "complete_baseline"},
         "Two of six Memory trials must still request assessment."),
        ("interrupted_only", {"memory_trials": 6, "interrupted": True},
         {"kind": "recommendation_action", "action": "complete_baseline"},
         "Interrupted trials cannot complete a baseline, so assessment is still required."),
        ("assisted_baseline", {"memory_trials": 6, "hinted": True},
         {"kind": "assisted_baseline_refused"},
         "A hint cannot be attached to a scored baseline trial, so an assisted baseline attempt is "
         "refused and the uncoached baseline stays intact."),
        ("complete_low", {"all_trials": 6, "family_ratios": {"working_memory": 0.25}, "correct_ratio": 0.5},
         {"kind": "recommendation_action", "action": "targeted_training"},
         "A completed baseline enables targeted training and the result must stay provisional."),
        ("complete_moderate", {"all_trials": 6, "family_ratios": {"working_memory": 0.5}, "correct_ratio": 0.5},
         {"kind": "recommendation_action", "action": "targeted_training"},
         "A completed mid-range baseline enables targeted training."),
        ("complete_high", {"all_trials": 6, "family_ratios": {"working_memory": 1.0}, "correct_ratio": 0.5},
         {"kind": "recommendation_action", "action": "targeted_training"},
         "A completed strong baseline still schedules the weakest remaining family."),
        ("goal_planning", {"memory_trials": 6, "correct_ratio": 0.5, "goal": "planning"},
         {"kind": "goal_present_in_decision"},
         "A declared goal must appear in the recorded decision rather than being discarded."),
        ("all_unassessed_two", {"memory_trials": 0, "reasoning_trials": 0},
         {"kind": "single_next_family"},
         "With several unassessed families the policy still resolves exactly one next family."),
        ("all_complete_equal", {"all_trials": 6, "correct_ratio": 0.5},
         {"kind": "single_next_family"},
         "With every family complete the policy still resolves exactly one next family."),
        ("unassessed_not_zero", {"memory_trials": 0},
         {"kind": "profile_unassessed_not_scored"},
         "An unassessed family must be reported as unassessed, never as a zero index."),
        ("baseline_immutable", {"memory_trials": 6, "correct_ratio": 0.5, "then_training": True},
         {"kind": "baseline_index_unchanged"},
         "A subsequent training block must not change the fixed baseline index."),
    ]
    for name, scenario, expectation, note in situations:
        add("situations", name, scenario, expectation, note)

    # Track 3: constraints â€” budget, availability, idempotency and stale-plan guards.
    for budget in BUDGETS:
        add("constraints", "budget_bounds",
            {"budget_minutes": budget, "all_trials": 6, "correct_ratio": 0.5},
            {"kind": "plan_within_budget", "budget_minutes": budget},
            f"A {budget}-minute budget must be respected: planned minutes never exceed it.")
        for exercise_id, dimension, label in FAMILIES[:2]:
            add("constraints", "availability_subset",
                {"budget_minutes": budget, "available_dimensions": [dimension], "all_trials": 6,
                 "correct_ratio": 0.5},
                {"kind": "decision_within_availability", "available_dimensions": [dimension]},
                f"With only {label} available the resolved activity and plan must stay inside that "
                f"constraint at a {budget}-minute budget.")
    add("constraints", "availability_empty",
        {"budget_minutes": 20, "available_dimensions": [], "all_trials": 6, "correct_ratio": 0.5},
        {"kind": "explicit_no_fit"},
        "An explicit empty availability constraint must produce an explicit no-fit, never a silent "
        "reinstatement of every family.")
    add("constraints", "availability_unknown",
        {"budget_minutes": 20, "available_dimensions": ["telepathy"], "all_trials": 6,
         "correct_ratio": 0.5},
        {"kind": "unknown_availability_rejected"},
        "An unsupported availability identifier must be rejected, not ignored.")
    add("constraints", "duplicate_submission",
        {"all_trials": 6, "correct_ratio": 0.5, "duplicate": True},
        {"kind": "single_canonical_event"},
        "Retrying the identical response must leave exactly one canonical trial event.")
    add("constraints", "stale_plan_launch",
        {"all_trials": 6, "correct_ratio": 0.5, "decision_injected": True, "goal": "working_memory"},
        {"kind": "stale_plan_refused"},
        "A decision recorded outside the plan must make the saved plan stale, so the launch is "
        "refused until the plan is reconciled.")
    add("constraints", "tier_ceiling",
        {"all_trials": 6, "correct_ratio": 0.5, "requested_tier": "tier-3"},
        {"kind": "unsupported_tier_refused"},
        "A launch tier above the recorded decision must be refused, never silently promoted.")
    add("constraints", "quiet_scored_phase",
        {"all_trials": 6, "correct_ratio": 0.5},
        {"kind": "coach_refused_in_scored_phase"},
        "The coach must refuse a scored baseline phase instead of narrating hints.")

    # Fill to seventy-two with the remaining budget/availability combinations.
    while len(out) < 72:
        position = len(out) + 1
        family = FAMILIES[position % len(FAMILIES)]
        budget = BUDGETS[position % len(BUDGETS)]
        add("constraints", "budget_family_matrix",
            {"budget_minutes": budget, "available_dimensions": [family[1]], "all_trials": 6,
             "correct_ratio": (position % 4) / 4},
            {"kind": "plan_within_budget", "budget_minutes": budget},
            f"{family[2]}-only schedule at a {budget}-minute budget must stay inside the budget.")
    return out


def main() -> int:
    manifest = {
        "manifest_version": "generalisation-manifest-v1",
        "created_for": "AI4BRAIN generalisation workstream (G0)",
        "tracks": ["variations", "situations", "constraints"],
        "counts": {},
        "split_policy": ("Every third case is reserved. The reserved pool is not executed until the "
                         "candidate source hash matches FREEZE.json."),
        "cases": cases(),
    }
    ids = [case["id"] for case in manifest["cases"]]
    assert len(ids) == len(set(ids)) == 72, (len(ids), len(set(ids)))
    for track in manifest["tracks"]:
        rows = [case for case in manifest["cases"] if case["track"] == track]
        manifest["counts"][track] = {
            "total": len(rows),
            "development": len([row for row in rows if row["split"] == "development"]),
            "reserved": len([row for row in rows if row["split"] == "reserved"]),
        }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(TARGET), "cases": len(ids), "counts": manifest["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


