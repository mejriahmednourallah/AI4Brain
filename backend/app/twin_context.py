"""SQLite-derived Brain Twin context shared by coaching, planning and dashboards.

The context deliberately separates three things that must never be merged:

* ``observed`` - recorded, server-evaluated task behaviour. Only this may carry a
  measured value.
* ``learner_reported`` - statements the learner made about their experience.
* ``suggested`` - strategies and explanations the coach proposes.

Every context carries an ``evidence_revision`` over the canonical events it was
built from, so a stored answer can be traced to the exact evidence it described.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .battery_exercises import DIMENSIONS, VERSIONS
from .profile_service import build_profile
from .selector import select_next
from .strategy import latest_strategy

CONTEXT_VERSION = "twin-context-v1"

FAMILIES: dict[str, dict[str, str]] = {
    "EX-01": {"label": "Memory", "dimension": "working_memory", "world": "Lantern Grove"},
    "EX-02": {"label": "Reasoning", "dimension": "reasoning", "world": "Pattern Atelier"},
    "EX-03": {"label": "Attention", "dimension": "attention_inhibition", "world": "Signal Observatory"},
    "EX-04": {"label": "Flexibility", "dimension": "flexibility", "world": "Shifting Gallery"},
    "EX-05": {"label": "Planning", "dimension": "planning", "world": "Wayfinder's Garden"},
}
DIMENSION_TO_EXERCISE = {family["dimension"]: exercise_id for exercise_id, family in FAMILIES.items()}

# Aliases are ordered strongest first. A phrase that appears in several families is
# intentionally omitted here so ambiguity is reported instead of guessed.
ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("EX-01", ("memory", "working memory", "remember", "recall", "lantern grove", "lantern")),
    ("EX-02", ("reasoning", "pattern atelier", "atelier", "matrix", "matrices", "visual pattern")),
    ("EX-03", ("attention", "signal observatory", "observatory", "go/no-go", "go no go", "no-go", "no go", "impulse")),
    ("EX-04", ("flexibility", "shifting gallery", "gallery", "rule switch", "rule-switch", "switching rule", "switch rule")),
    ("EX-05", ("planning", "wayfinder", "maze", "shortest path", "route planning")),
)
NEXT_STEP_HINTS = ("what should i do next", "what next", "what now", "next activity", "what would you recommend",
                   "should i practise", "should i practice", "what do i start", "where do i start")

CAVEAT = ("These are preliminary task-specific observations with high uncertainty, not a clinical "
          "assessment or IQ score.")


def _iso(value: Any) -> str:
    return str(value or "")


def _revision(events: list[dict[str, Any]]) -> str:
    material = [[event.get("event_id"), event.get("type"), _iso(event.get("created_at"))] for event in events]
    return hashlib.sha256(json.dumps(material, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def _family_error_summary(exercise_id: str, dimension: dict[str, Any]) -> dict[str, Any]:
    """Reduce a scored family to the recorded error facts a learner can be shown."""
    if exercise_id == "EX-01":
        return {
            "correct_positions": dimension.get("correct_positions"),
            "total_positions": dimension.get("total_positions"),
            "longest_fully_correct_span": dimension.get("longest_fully_correct_span"),
            "interrupted_count": dimension.get("interrupted_count", 0),
            "pattern": "recall_order" if dimension.get("correct_positions") not in (None, 24) else None,
        }
    if exercise_id == "EX-02":
        return {"correct": dimension.get("correct"), "evidence_count": dimension.get("evidence_count"),
                "pattern": "incorrect_pattern" if (dimension.get("correct") or 0) < (dimension.get("evidence_count") or 0) else None}
    if exercise_id == "EX-03":
        return {"go_hits": dimension.get("go_hits"), "go_omissions": dimension.get("go_omissions"),
                "no_go_correct_rejections": dimension.get("no_go_correct_rejections"),
                "no_go_commissions": dimension.get("no_go_commissions"),
                "early_responses": dimension.get("early_responses"), "late_responses": dimension.get("late_responses"),
                "pattern": ("attention_commission" if (dimension.get("no_go_commissions") or 0) > 0
                            else ("attention_omission" if (dimension.get("go_omissions") or 0) > 0 else None))}
    if exercise_id == "EX-04":
        return {"switch_correct": dimension.get("switch_correct"), "switch_trials": dimension.get("switch_trials"),
                "repeat_correct": dimension.get("repeat_correct"), "repeat_trials": dimension.get("repeat_trials"),
                "error_previous_rule": dimension.get("error_previous_rule"),
                "pattern": ("switch_previous_rule" if (dimension.get("error_previous_rule") or 0) > 0 else
                            ("switch_incorrect_rule" if (dimension.get("switch_correct") or 0) < (dimension.get("switch_trials") or 0) else None))}
    if exercise_id == "EX-05":
        return {"completed_puzzles": dimension.get("completed_puzzles"), "excess_moves": dimension.get("excess_moves"),
                "illegal_moves": dimension.get("illegal_moves"), "undo_count": dimension.get("undo_count"),
                "restart_count": dimension.get("restart_count"),
                "pattern": ("planning_inefficient" if (dimension.get("excess_moves") or 0) > 0 else
                            ("planning_incomplete" if (dimension.get("completed_puzzles") or 0) < 3 else None))}
    return {}


def _attempt_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {}) or {}
    evaluation = payload.get("evaluation", {}) or {}
    return {
        "evidence_id": event.get("event_id"),
        "exercise_id": payload.get("exercise_id"),
        "phase": payload.get("phase"),
        "item_id": payload.get("item_id"),
        "correct": evaluation.get("correct"),
        "response_time_ms": evaluation.get("response_time_ms", payload.get("response_time_ms")),
        "error_type": evaluation.get("error_type"),
        "interrupted": bool(payload.get("interaction", {}).get("visibility_interrupted")),
        "assisted": bool(payload.get("interaction", {}).get("hint_count", 0)),
        "recorded_at": event.get("created_at") or payload.get("recorded_at"),
    }


def _decision_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {}) or {}
    return {
        "decision_event_id": event.get("event_id"),
        "exercise_id": payload.get("exercise_id"),
        "action": payload.get("action"),
        "old_tier": payload.get("old_tier"),
        "new_tier": payload.get("new_tier"),
        "reason_codes": payload.get("reason_codes"),
        "evidence_ids": payload.get("evidence_ids"),
        "recorded_at": payload.get("recorded_at") or event.get("created_at"),
    }


def build_twin_context(
    store: Any,
    learner_id: str = "demo-user",
    *,
    focus_exercise_id: str | None = None,
    conversation_subject: str | None = None,
    conversation_turns: list[dict[str, Any]] | None = None,
    learner_reports: list[dict[str, Any]] | None = None,
    canonical_events: list[dict[str, Any]] | None = None,
    max_attempts: int = 8,
    max_decisions: int = 3,
) -> dict[str, Any]:
    # Callers that already loaded the canonical learner snapshot can reuse it,
    # keeping the profile, revision, and recommendations on the same evidence view.
    events = canonical_events if canonical_events is not None else store.events(learner_id=learner_id)
    profile = build_profile(events)
    preferences = store.current_preferences(learner_id, canonical_events=events)
    recommendations = store.recommendations(learner_id)
    recommendation = (dict(recommendations[-1]) if recommendations else select_next(
        profile, events, goal_dimension=preferences.get("goal_dimension"), selection_count=len(recommendations)))
    gate = select_next(profile, events, goal_dimension=preferences.get("goal_dimension"),
                       selection_count=len(recommendations))
    if gate["action"] in {"complete_baseline", "additional_assessment"}:
        recommendation = gate

    families: dict[str, dict[str, Any]] = {}
    for exercise_id, family in FAMILIES.items():
        dimension = profile["dimensions"].get(family["dimension"], {})
        families[family["dimension"]] = {
            "exercise_id": exercise_id,
            "label": family["label"],
            "world": family["world"],
            "status": dimension.get("status"),
            "completed": bool(dimension.get("completed")),
            "index_0_100": dimension.get("index_0_100"),
            "evidence_count": dimension.get("evidence_count", 0),
            "required_evidence_count": dimension.get("required_evidence_count"),
            "uncertainty_status": dimension.get("uncertainty_status"),
            "evidence_ids": list(dimension.get("evidence_ids", [])),
            "assessed_version": VERSIONS.get(exercise_id) or ("reasoning-v1" if exercise_id == "EX-02" else None),
            "error_summary": _family_error_summary(exercise_id, dimension),
            "not_comparable_with": [other for other in FAMILIES if other != exercise_id],
        }

    scored_attempts = [event for event in events
                       if event.get("type", "").endswith("_completed")
                       and (event.get("payload", {}) or {}).get("phase") in {"baseline", "training", "practice", "reassessment"}]
    if focus_exercise_id:
        focused = [event for event in scored_attempts
                   if (event.get("payload", {}) or {}).get("exercise_id") == focus_exercise_id]
        attempts = (focused or scored_attempts)[-max_attempts:]
    else:
        attempts = scored_attempts[-max_attempts:]

    decisions = [_decision_summary(event) for event in events if event.get("type") == "difficulty_changed"][-max_decisions:]
    plans = store.plans(learner_id) if hasattr(store, "plans") else []
    latest_plan = plans[-1] if plans else None

    strategies = []
    for exercise_id in FAMILIES:
        candidate = latest_strategy(events, exercise_id)
        if candidate:
            strategies.append({**candidate, "exercise_id": exercise_id, "kind": "suggested"})

    limitations = [CAVEAT,
                   "Indices are task-specific percentages, not a general ability score, and are not comparable across families.",
                   "Interrupted attempts and assisted attempts are excluded from unassisted eligibility."]
    if any(not family["completed"] for family in families.values()):
        missing = [family["label"] for family in families.values() if not family["completed"]]
        limitations.append("Missing baseline evidence stays unassessed: " + ", ".join(missing) + ".")

    return {
        "context_version": CONTEXT_VERSION,
        "evidence_revision": _revision(events),
        "generated_at": events[-1].get("created_at") if events else None,
        "families": families,
        "observed": {
            "attempts": [_attempt_summary(event) for event in attempts],
            "decisions": decisions,
            "baseline_records": sum(family["evidence_count"] for family in families.values()),
        },
        "learner_reported": list(learner_reports or []),
        "suggested": strategies,
        "retained": {
            "goal_dimension": preferences.get("goal_dimension"),
            "dashboard_mode": preferences.get("mode"),
            "plan": {"plan_id": latest_plan.get("plan_id"), "policy_version": latest_plan.get("policy_version"),
                     "budget_minutes": latest_plan.get("budget_minutes"),
                     "steps": latest_plan.get("steps")} if latest_plan else None,
            "plan_revision_count": sum(1 for event in events if event.get("type") in {"training_plan_revised", "training_plan_unrevised"}),
            "plan_versions": len(plans),
        },
        "next_step": {
            "action": recommendation.get("action"),
            "dimension": recommendation.get("dimension") or recommendation.get("dimension_id"),
            "exercise_id": recommendation.get("exercise_id"),
            "tier": recommendation.get("tier") or recommendation.get("difficulty_tier"),
            "reason_codes": recommendation.get("reason_codes"),
            "evidence_ids": list(dict.fromkeys(str(x) for x in recommendation.get("evidence_ids", []) if x)),
        },
        "conversation": {"subject": conversation_subject, "turns": list(conversation_turns or [])[-6:]},
        "limitations": limitations,
    }


def _alias_hits(message: str) -> list[tuple[int, str, int]]:
    text = message.casefold()
    hits: list[tuple[int, str, int]] = []
    for order, (exercise_id, aliases) in enumerate(ALIASES):
        matched = sum(1 for alias in aliases if alias in text)
        if matched:
            hits.append((matched, exercise_id, order))
    return hits


def resolve_subject(
    message: str,
    *,
    focus_exercise_id: str | None = None,
    conversation_subject: str | None = None,
    next_exercise_id: str | None = None,
    has_conversation: bool = False,
) -> dict[str, Any]:
    """Resolve which family the question is about, in the documented order."""
    hits = _alias_hits(message)
    if hits:
        best = max(hits, key=lambda row: (row[0], -row[2]))
        ties = [row for row in hits if row[0] == best[0]]
        if len(ties) > 1 and not has_conversation and not focus_exercise_id:
            labels = sorted({FAMILIES[row[1]]["label"] for row in ties})
            return {"exercise_id": None, "dimension": None, "source": "ambiguous", "candidates": labels,
                    "clarification": f"Which family do you mean: {', '.join(labels)}?"}
        return {"exercise_id": best[1], "dimension": FAMILIES[best[1]]["dimension"], "source": "explicit", "candidates": []}

    asks_next = any(hint in message.casefold() for hint in NEXT_STEP_HINTS)
    if focus_exercise_id in FAMILIES:
        return {"exercise_id": focus_exercise_id, "dimension": FAMILIES[focus_exercise_id]["dimension"],
                "source": "current_activity", "candidates": []}
    if conversation_subject in FAMILIES and not asks_next:
        return {"exercise_id": conversation_subject, "dimension": FAMILIES[conversation_subject]["dimension"],
                "source": "conversation_subject", "candidates": []}
    if next_exercise_id in FAMILIES:
        return {"exercise_id": next_exercise_id, "dimension": FAMILIES[next_exercise_id]["dimension"],
                "source": "next_step" if asks_next else "recommendation", "candidates": []}
    return {"exercise_id": None, "dimension": None, "source": "unresolved", "candidates": [],
            "clarification": "Which task family should I look at: Memory, Reasoning, Attention, Flexibility or Planning?"}


def subject_family(context: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any] | None:
    dimension = subject.get("dimension")
    if not dimension:
        return None
    return context["families"].get(dimension)


def provider_payload(context: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    """Bounded provider context: summary, relevant attempts, decisions, plan, turns."""
    family = subject_family(context, subject)
    relevant = [attempt for attempt in context["observed"]["attempts"]
                if not subject.get("exercise_id") or attempt.get("exercise_id") == subject["exercise_id"]]
    return {
        "subject": {"label": family["label"] if family else None, "dimension": subject.get("dimension"),
                    "resolved_from": subject.get("source"), "status": family["status"] if family else None},
        "subject_observed": {"index_0_100": family["index_0_100"], "evidence_count": family["evidence_count"],
                             "required_evidence_count": family["required_evidence_count"],
                             "uncertainty_status": family["uncertainty_status"],
                             "error_summary": family["error_summary"]} if family else None,
        "families": {dimension: {"label": row["label"], "status": row["status"], "index_0_100": row["index_0_100"],
                                 "evidence_count": row["evidence_count"]}
                     for dimension, row in context["families"].items()},
        "relevant_attempts": relevant[:8],
        "recent_decisions": context["observed"]["decisions"][:3],
        "suggested_strategies": [{"id": row.get("id"), "title": row.get("title"), "dimension": row.get("dimension")}
                                 for row in context["suggested"]],
        "retained": {"goal_dimension": context["retained"]["goal_dimension"], "plan": context["retained"]["plan"]},
        "next_step": context["next_step"],
        "prior_turns": context["conversation"]["turns"][-6:],
        "limitations": context["limitations"],
    }
