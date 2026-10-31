"""plan-v2: evidence-triggered, ranked and budget-aware short plans.

``plan-v1`` plans stay readable and unmodified. This module adds:

* reconciliation after a baseline family completes, a canonical training decision,
  a goal/budget change or a planned activity completing;
* an explicit step lifecycle (recommended, in progress, completed, deferred,
  superseded) with the launch tier and completion references;
* deliberate ranking of every family instead of a fixed later-family order;
* activity-specific duration estimates improved from comparable active records;
* transparent budget accounting that never silently overbooks.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from .policy import PLAN_POLICY_VERSION
from .strategy import latest_strategy
from .difficulty import current_tier, TIERS

PLAN_VERSION = "plan-v2"
RANKING_POLICY_VERSION = "plan-ranking-v1"

# Activity-specific defaults: the block size differs by family, so a single
# two-minute default misreported every activity.
DEFAULT_DURATION_MINUTES = {"EX-01": 3, "EX-02": 4, "EX-03": 5, "EX-04": 4, "EX-05": 4}
TRAINING_DURATION_MINUTES = {"EX-01": 3, "EX-02": 3, "EX-03": 4, "EX-04": 3, "EX-05": 3}
MIN_ESTIMATE_SAMPLES = 5
RANK_WEIGHTS = {"missing_evidence": 0.40, "goal_alignment": 0.22, "error_severity": 0.18,
                "recency": 0.12, "uncertainty": 0.08}
STEP_STATUSES = ("recommended", "in_progress", "completed", "deferred", "superseded")
LIFECYCLE_VERSION = "plan-step-lifecycle-v1"
TIER_POLICY_VERSION = "difficulty-policy-authoritative-v1"


def authoritative_training_tier(events: list[dict[str, Any]], dimension: str,
                                *, baseline_completed: bool) -> str | None:
    """Resolve the only launch tier allowed for a completed family."""
    if not baseline_completed:
        return None
    tier = current_tier(events, dimension)
    if tier not in TIERS:
        raise ValueError(f"difficulty policy returned an invalid tier for {dimension}")
    return tier


def _active_duration_records(store: Any, events: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Median-able active durations per exercise, excluding idle/interrupted/QA data."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for event in events:
        payload = event.get("payload", {}) or {}
        if payload.get("sample_data") is True:
            continue
        if payload.get("phase") not in {"baseline", "training", "practice"}:
            continue
        interaction = payload.get("interaction", {}) or {}
        if interaction.get("visibility_interrupted"):
            continue
        grouped.setdefault(str(payload.get("exercise_id")), {}).setdefault(
            str(event.get("session_id") or payload.get("session_id")), []).append(event)
    durations: dict[str, list[float]] = {}
    for exercise_id, sessions in grouped.items():
        values = []
        for rows in sessions.values():
            active_ms = 0.0
            usable = True
            for event in rows:
                payload = event.get("payload", {}) or {}
                interaction = payload.get("interaction", {}) or {}
                timing = payload.get("timing", {}) or {}
                if interaction.get("hint_count", 0) or interaction.get("replay_count", 0):
                    usable = False
                    break
                response_ms = timing.get("response_time_ms")
                if response_ms is None:
                    response_ms = (payload.get("evaluation", {}) or {}).get("response_time_ms")
                if not isinstance(response_ms, (int, float)) or response_ms < 0:
                    continue
                active_ms += float(response_ms)
            if usable and active_ms > 0:
                values.append(active_ms / 60000.0)
        if values:
            durations[exercise_id] = values
    return durations


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def estimate_durations(store: Any, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records = _active_duration_records(store, events)
    estimates: dict[str, dict[str, Any]] = {}
    for exercise_id, default in DEFAULT_DURATION_MINUTES.items():
        samples = records.get(exercise_id, [])
        if len(samples) >= MIN_ESTIMATE_SAMPLES:
            improved = max(1, min(30, int(round(_median(samples)))))
            estimates[exercise_id] = {"minutes": improved, "source": "comparable_active_duration_median",
                                      "sample_size": len(samples),
                                      "basis": "completed attempts with no interruption or assistance"}
        else:
            estimates[exercise_id] = {"minutes": default, "source": "activity_default",
                                      "sample_size": len(samples),
                                      "basis": f"fewer than {MIN_ESTIMATE_SAMPLES} comparable active records"}
    return estimates


def _days_since(value: str | None) -> float:
    if not value:
        return 365.0
    from datetime import datetime, timezone
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return 365.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 86400.0)


def _family_error_rate(family: dict[str, Any]) -> float:
    """0..1 recorded error share for a family, from canonical counters only."""
    error = family.get("error_summary", {})
    if family.get("exercise_id") == "EX-01":
        total = error.get("total_positions") or 0
        correct = error.get("correct_positions")
        return 1 - (correct / total) if total and correct is not None else 0.0
    if family.get("exercise_id") == "EX-02":
        count = error.get("evidence_count") or 0
        correct = error.get("correct")
        return 1 - (correct / count) if count and correct is not None else 0.0
    if family.get("exercise_id") == "EX-03":
        go = (error.get("go_hits") or 0) + (error.get("go_omissions") or 0)
        no_go = (error.get("no_go_correct_rejections") or 0) + (error.get("no_go_commissions") or 0)
        total = go + no_go
        good = (error.get("go_hits") or 0) + (error.get("no_go_correct_rejections") or 0)
        return 1 - (good / total) if total else 0.0
    if family.get("exercise_id") == "EX-04":
        total = (error.get("switch_trials") or 0) + (error.get("repeat_trials") or 0)
        good = (error.get("switch_correct") or 0) + (error.get("repeat_correct") or 0)
        return 1 - (good / total) if total else 0.0
    if family.get("exercise_id") == "EX-05":
        completed = error.get("completed_puzzles") or 0
        return 1 - (completed / 3.0) if completed else 1.0
    return 0.0


def rank_families(context: dict[str, Any], events: list[dict[str, Any]],
                  goal_dimension: str | None,
                  available_dimensions: list[str] | None = None) -> list[dict[str, Any]]:
    """Score every family deliberately; no fixed later-family ordering."""
    allowed = None if available_dimensions is None else set(available_dimensions)
    last_practised: dict[str, str] = {}
    for event in events:
        payload = event.get("payload", {}) or {}
        if payload.get("phase") not in {"baseline", "training", "practice", "reassessment"}:
            continue
        dimension = payload.get("dimension")
        if dimension:
            stamped = str(event.get("created_at") or payload.get("recorded_at") or "")
            if stamped > last_practised.get(dimension, ""):
                last_practised[dimension] = stamped
    ranked = []
    for dimension, family in context["families"].items():
        if allowed is not None and dimension not in allowed:
            continue
        exercise_id = family["exercise_id"]
        missing = 0.0 if family["completed"] else 1.0
        goal = 1.0 if goal_dimension and dimension == goal_dimension else 0.0
        severity = _family_error_rate(family)
        recency = min(1.0, _days_since(last_practised.get(dimension)) / 14.0)
        uncertainty = 0.0 if family["completed"] else 1.0
        if family["completed"] and family["uncertainty_status"] != "PRELIMINARY_HIGH_UNCERTAINTY":
            uncertainty = 0.0
        elif family["completed"]:
            uncertainty = 0.6
        factors = {"missing_evidence": round(missing, 4), "goal_alignment": goal,
                   "error_severity": round(severity, 4), "recency": round(recency, 4),
                   "uncertainty": round(uncertainty, 4)}
        score = sum(RANK_WEIGHTS[name] * value for name, value in factors.items())
        ranked.append({"dimension": dimension, "exercise_id": exercise_id,
                       "label": family["label"], "completed": family["completed"],
                       "tier": None, "score": round(score, 4), "factors": factors,
                       "last_practised_at": last_practised.get(dimension)})
    ranked.sort(key=lambda row: (-row["score"], row["exercise_id"]))
    return ranked


def _plan_step(ranked: dict[str, Any], *, status: str, action: str, tier: str | None,
               strategy_id: str | None, reason: str, evidence_ids: list[str],
               minutes: int, estimate: dict[str, Any], position: int) -> dict[str, Any]:
    return {"step_id": f"step-{position}", "dimension_id": ranked["dimension"],
            "exercise_type_id": ranked["exercise_id"], "label": ranked["label"],
            "action": action, "difficulty_tier": tier, "strategy_id": strategy_id,
            "selection_reason": reason, "ranking_score": ranked["score"],
            "ranking_factors": ranked["factors"], "source_evidence_ids": evidence_ids,
            "estimated_time_minutes": minutes, "estimate_source": estimate["source"],
            "estimate_sample_size": estimate["sample_size"],
            "status": status, "policy_version": PLAN_POLICY_VERSION,
            "launch_tier": tier, "tier_source": TIER_POLICY_VERSION,
            "completion_references": [], "superseded_by": None,
            "lifecycle_version": LIFECYCLE_VERSION}


def build_plan_v2(context: dict[str, Any], events: list[dict[str, Any]], store: Any, *,
                  goal_dimension: str | None = None, budget_minutes: int | None = None,
                  selection_count: int = 0, previous: dict[str, Any] | None = None,
                  available_dimensions: list[str] | None = None,
                  resolved_next: dict[str, Any] | None = None) -> dict[str, Any]:
    budget = max(2, int(budget_minutes or 20))
    estimates = estimate_durations(store, events)
    ranked = rank_families(context, events, goal_dimension, available_dimensions)
    # One resolved decision governs recommendation, plan order and launch.
    resolved_dimension = (resolved_next or {}).get("dimension")
    # A completed family that was already selected for targeted work remains
    # visible across a refresh.  Otherwise a newly completed assessment can be
    # pushed outside the four-step budget by every still-unassessed family,
    # leaving the saved plan unable to launch its own active work.
    previous_core = _core_plan_history(previous)
    retained_dimensions = {
        step["dimension_id"] for step in (previous_core or {}).get("steps", [])
        if step.get("status") in {"recommended", "in_progress"}
        and step.get("action") in {"additional_assessment", "targeted_training"}
        and context["families"].get(step.get("dimension_id"), {}).get("completed")
    }
    selection_ranked = sorted(
        ranked, key=lambda row: (0 if row["dimension"] in retained_dimensions else 1,
                                 -row["score"], row["exercise_id"]),
    )
    # The resolved family leads the schedule so the advice and the plan agree; if it cannot be
    # funded inside the budget the returned plan says so and offers the budget change.
    if resolved_dimension:
        selection_ranked = sorted(
            selection_ranked,
            key=lambda row: (0 if row["dimension"] == resolved_dimension else 1,
                             0 if row["dimension"] in retained_dimensions else 1,
                             -row["score"], row["exercise_id"]),
        )
    steps: list[dict[str, Any]] = []
    remaining = budget
    for row in selection_ranked:
        if len(steps) >= 4:
            break
        action = "additional_assessment" if not row["completed"] else "targeted_training"
        tier = authoritative_training_tier(
            events, row["dimension"], baseline_completed=row["completed"],
        ) if action == "targeted_training" else None
        estimate = estimates[row["exercise_id"]]
        minutes = estimate["minutes"] if action == "additional_assessment" else TRAINING_DURATION_MINUTES.get(
            row["exercise_id"], 3)
        if minutes > remaining:
            continue
        family = context["families"][row["dimension"]]
        strategy = latest_strategy(events, row["exercise_id"]) if action == "targeted_training" else None
        reason = ("unassessed_baseline" if not row["completed"]
                  else "recorded_error_pattern" if row["factors"]["error_severity"] > 0
                  else "maintenance_and_goal_alignment")
        steps.append(_plan_step(row, status="recommended", action=action, tier=tier,
                                strategy_id=strategy.get("id") if strategy else None, reason=reason,
                                evidence_ids=list(family.get("evidence_ids", [])), minutes=minutes,
                                estimate=estimate, position=len(steps) + 1))
        remaining -= minutes
    planned = sum(step["estimated_time_minutes"] for step in steps)
    adjustment = None
    if len(steps) < 2 and ranked:
        # Never silently overbook: offer a budget change instead of adding an unfunded step.
        cheapest = min(ranked, key=lambda row: estimates[row["exercise_id"]]["minutes"])
        needed = planned + estimates[cheapest["exercise_id"]]["minutes"]
        adjustment = {"suggested_budget_minutes": needed,
                      "reason": "The remaining budget cannot fund a second meaningful activity.",
                      "cheapest_activity": cheapest["label"]}
    lifecycle = _apply_lifecycle(previous_core, steps, events)
    fingerprint = _fingerprint(steps, goal_dimension, budget)
    changed = not previous_core or previous_core.get("decision_fingerprint") != fingerprint
    constrained = available_dimensions is not None
    availability = ({"applied": True, "requested": list(dict.fromkeys(available_dimensions or [])),
                     "excluded": [dimension for dimension in context["families"]
                                  if dimension not in set(available_dimensions or [])]}
                    if constrained else {"applied": False})
    first_step = steps[0] if steps else None
    resolved = None
    resolved_unscheduled = None
    if resolved_next:
        resolved = {"exercise_id": resolved_next.get("exercise_id"),
                    "dimension": resolved_next.get("dimension"),
                    "action": resolved_next.get("action"),
                    "tier": resolved_next.get("tier"),
                    "policy_version": resolved_next.get("policy_version"),
                    "rationale": resolved_next.get("rationale"),
                    "source": "select_next_resolution"}
    if first_step and resolved and first_step["dimension_id"] != resolved["dimension"]:
        scheduled = {"exercise_id": first_step["exercise_type_id"],
                     "dimension": first_step["dimension_id"],
                     "reason": "the resolved family did not fit the remaining budget"}
        resolved["scheduled_first_step"] = scheduled
        resolved_unscheduled = resolved["exercise_id"]
        family = context["families"].get(resolved["dimension"] or "", {})
        needed_minutes = (estimates.get(resolved["exercise_id"] or "", {}).get("minutes")
                          or TRAINING_DURATION_MINUTES.get(resolved["exercise_id"] or "", 3))
        adjustment = {"suggested_budget_minutes": planned + int(needed_minutes),
                      "reason": (f"The resolved next activity ({family.get('label', resolved['exercise_id'])}) "
                                 f"needs about {int(needed_minutes)} minutes, which the current budget cannot fund."),
                      "resolved_activity": family.get("label", resolved["exercise_id"])}
    return {
        "plan_id": None, "learner_id": "demo-user", "profile_snapshot_id": None,
        "plan_version": PLAN_VERSION, "policy_version": PLAN_POLICY_VERSION,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "selection_policy_version": (resolved or {}).get("policy_version"), "goal": goal_dimension, "created_at": None,
        "budget_minutes": budget, "planned_minutes": planned, "estimated_time_minutes": planned,
        "unused_minutes": budget - planned,
        "budget_note": (f"{planned} of {budget} minutes are planned; {budget - planned} remain unused "
                        f"because no further activity fits the remaining time."),
        "budget_adjustment": adjustment,
        "reason_codes": (["availability_constraint_excludes_every_family"] if constrained and not ranked
                         else ["resolved_family_over_budget", "evidence_triggered_ranked_plan"] if resolved_unscheduled
                         else ["evidence_triggered_ranked_plan"] if changed else
                         ["no_meaningful_new_evidence_or_preference_change", "retained_current_plan"]),
        "rationale": ("Steps are ranked from baseline coverage, the declared goal, recorded error share, "
                      "practice recency and evidence uncertainty. Missing baseline evidence is ranked first."
                      if ranked else
                      "The supplied availability constraint excludes every task family, so no step is scheduled."),
        "steps": steps, "status": "active", "changed": changed,
        "availability": availability, "resolved_next_step": resolved,
        "ranking": [{key: row[key] for key in ("label", "score", "factors", "completed")} for row in ranked],
        "features": {"ranked_families": len(ranked), "budget_minutes": budget,
                     "tier_policy_version": TIER_POLICY_VERSION},
        "alternatives": [{"dimension": row["dimension"], "score": row["score"]}
                         for row in ranked[len(steps):]],
        "evidence_ids": [evidence for step in steps for evidence in step["source_evidence_ids"]],
        "decision_fingerprint": fingerprint,
        "superseded_steps": lifecycle,
    }


def _fingerprint(steps: list[dict[str, Any]], goal: str | None, budget: int) -> str:
    return json.dumps([goal, budget,
                       [[step["dimension_id"], step["action"], step["difficulty_tier"], step["strategy_id"],
                         step["estimated_time_minutes"], step["source_evidence_ids"]] for step in steps]],
                      separators=(",", ":"))


def _core_plan_history(previous: dict[str, Any] | None) -> dict[str, Any] | None:
    """Project a v3 history row back to its v2 core fingerprint and core steps."""
    if not previous or previous.get("plan_version") != "plan-v3":
        return previous
    fingerprint = previous.get("decision_fingerprint")
    try:
        fingerprint = json.loads(fingerprint) if isinstance(fingerprint, str) else fingerprint
    except (TypeError, ValueError):
        fingerprint = None
    core_steps = [step for step in previous.get("steps", [])
                  if (step.get("activity_ref") or {}).get("kind") == "core"]
    return {**previous, "decision_fingerprint": (fingerprint or {}).get("plan_v2"),
            "steps": core_steps, "plan_version": "plan-v2"}


def _apply_lifecycle(previous: dict[str, Any] | None, steps: list[dict[str, Any]],
                     events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Carry forward completed/superseded history so it is never silently dropped."""
    if not previous:
        return []
    carried: list[dict[str, Any]] = []
    new_dimensions = {step["dimension_id"] for step in steps}
    for step in previous.get("steps", []):
        status = step.get("status", "recommended")
        if status in {"completed", "superseded", "deferred"}:
            carried.append({**step, "carried_from_plan_id": previous.get("plan_id")})
            continue
        if step["dimension_id"] in new_dimensions:
            continue
        carried.append({**step, "status": "superseded", "superseded_by": "reconciled_plan",
                        "carried_from_plan_id": previous.get("plan_id")})
    return carried


def completed_steps(previous: dict[str, Any] | None, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Mark previously planned steps whose activity has since completed."""
    if not previous:
        return []
    rows = []
    for step in previous.get("steps", []):
        if step.get("status") in {"completed", "superseded"}:
            rows.append(step)
            continue
        family = context["families"].get(step["dimension_id"])
        if family and family["completed"] and step.get("action") == "additional_assessment":
            rows.append({**step, "status": "completed",
                         "completion_references": list(family.get("evidence_ids", []))})
        elif family and family["completed"] and step.get("status") == "in_progress":
            rows.append(step)
        else:
            rows.append(step)
    return rows


def _trigger_key(trigger: dict[str, Any]) -> str:
    return f"{trigger.get('kind')}:{trigger.get('event_id') or trigger.get('reference') or 'none'}"


def reconcile_plan(store: Any, trigger: dict[str, Any], *, session_id: str | None = None,
                   budget_minutes: int | None = None,
                   goal_dimension: str | None = None,
                   available_dimensions: list[str] | None = None,
                   available_activities: list[str] | None = None) -> dict[str, Any]:
    """Create at most one plan revision per meaningful trigger.

    Repeated calls for the same trigger are no-ops, so a retried request or a
    reload cannot append duplicate revisions. With no existing plan there is
    nothing to refresh, so an implicit plan is never fabricated here.
    """
    events = store.events(learner_id="demo-user")
    key = _trigger_key(trigger)
    if any(event.get("type") in {"training_plan_revised", "training_plan_unchanged"}
           and (event.get("payload", {}) or {}).get("plan_trigger_key") == key for event in events):
        return {"skipped": True, "reason": "duplicate_trigger", "plan_trigger_key": key}
    preferences = store.current_preferences("demo-user")
    goal = goal_dimension if goal_dimension is not None else preferences.get("goal_dimension")
    history = store.plans("demo-user")
    previous = history[-1] if history else None
    if previous is None:
        return {"skipped": True, "reason": "no_active_plan", "plan_trigger_key": key}
    previous_availability = previous.get("availability", {}) or {}
    if available_dimensions is None and previous_availability.get("applied"):
        available_dimensions = previous_availability.get("requested")
    if (available_activities is None
            and previous_availability.get("requested_activities_applied")):
        available_activities = previous_availability.get("requested_activities") or []
    context = _context_for_planning(store, events)
    effective_budget = budget_minutes or (previous.get("budget_minutes") if previous else None) or 20
    from .profile_service import build_profile
    from .selector import select_next
    resolved_next = select_next(build_profile(events), events, goal_dimension=goal,
                                budget_minutes=effective_budget,
                                selection_count=len(store.recommendations("demo-user")),
                                available_dimensions=available_dimensions)
    plan = build_plan_v2(context, events, store, goal_dimension=goal, budget_minutes=effective_budget,
                         selection_count=len(store.recommendations("demo-user")), previous=previous,
                         available_dimensions=available_dimensions, resolved_next=resolved_next)
    from .storage import utc_now
    plan["plan_id"] = str(uuid.uuid4())
    plan["created_at"] = utc_now()
    from .plan_v3 import enrich_plan_v3
    plan = enrich_plan_v3(plan, context, events, store, available_activities=available_activities,
                          previous_plan=previous)
    plan["changed"] = (previous.get("decision_fingerprint") != plan.get("decision_fingerprint"))
    primary = plan["steps"][0] if plan["steps"] else None
    snapshot = store.latest_snapshot("demo-user", primary["dimension_id"]) if primary else None
    if plan["changed"] or not previous:
        plan["profile_snapshot_id"] = snapshot["id"] if snapshot else None
        plan["trigger"] = {**trigger, "plan_trigger_key": key}
        store.save_plan(plan)
    else:
        plan = {**previous, "changed": False, "trigger": {**trigger, "plan_trigger_key": key}}
    if session_id:
        from .storage import utc_now
        event_id = str(uuid.uuid4())
        store.add_event(event_id, session_id,
                        "training_plan_revised" if plan.get("changed") else "training_plan_unchanged",
                        {"event_id": event_id, "learner_id": "demo-user", "session_id": session_id,
                         "event_type": "training_plan_revised" if plan.get("changed") else "training_plan_unchanged",
                         "phase": "policy", "plan_id": plan.get("plan_id"),
                         "before_plan_id": previous.get("plan_id"),
                         "training_block_id": trigger.get("training_block_id"),
                         "plan_version": PLAN_VERSION, "policy_version": PLAN_POLICY_VERSION,
                         "plan_trigger": trigger, "plan_trigger_key": key,
                         "reason_codes": plan.get("reason_codes", []),
                         "evidence_ids": plan.get("evidence_ids", []),
                         "features": plan.get("features", {}),
                         "alternatives": plan.get("alternatives", []),
                         "changed": bool(plan.get("changed")), "sample_data": False,
                         "recorded_at": utc_now()})
    return plan


def _context_for_planning(store: Any, events: list[dict[str, Any]]) -> dict[str, Any]:
    from .twin_context import build_twin_context
    return build_twin_context(store, "demo-user")
