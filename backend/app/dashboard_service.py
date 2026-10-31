"""Read-only, shared Analytics/RPG dashboard projection over canonical SQLite evidence."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from .collaboration_service import collaboration_score

_DIMENSIONS = (
    ("working_memory", 6),
    ("reasoning", 6),
    ("attention_inhibition", 40),
    ("flexibility", 24),
    ("planning", 3),
)

# Activity uses only persisted completed-trial event types and their matching
# phases. Baseline and reassessment trials count as activity; XP is participation
# only and is awarded for valid practice/training trials, never policy events.
_TRIAL_PHASES = {
    "assessment_trial_completed": "baseline",
    "practice_trial_completed": "practice",
    "training_trial_completed": "training",
    "reassessment_trial_completed": "reassessment",
}
_PREFERENCE_EVENTS = {"dashboard_mode_changed", "user_goal_updated"}
_DIMENSION_EXERCISES = {
    "working_memory": "EX-01",
    "reasoning": "EX-02",
    "attention_inhibition": "EX-03",
    "flexibility": "EX-04",
    "planning": "EX-05",
}
_COLLABORATION_DIMENSIONS = (
    "clarification", "critical_verification", "iteration", "autonomy", "responsible_use",
)


def _eligible_trial(event: dict[str, Any]) -> bool:
    if event.get("type") not in _TRIAL_PHASES:
        return False
    payload = event.get("payload") or {}
    interaction = payload.get("interaction") or {}
    return (
        payload.get("phase") == _TRIAL_PHASES[event["type"]]
        and not interaction.get("visibility_interrupted", payload.get("visibility_interrupted", False))
        and payload.get("sample_data") is not True
    )


def _activity(events: list[dict[str, Any]], today: date | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    day = today or datetime.now(timezone.utc).date()
    start = day - timedelta(days=34)
    buckets = {start + timedelta(days=index): 0 for index in range(35)}
    activity_count = 0
    practice_count = 0
    training_count = 0
    assisted_count = 0
    xp = 0
    for event in events:
        if not _eligible_trial(event):
            continue
        payload = event.get("payload") or {}
        created = event.get("created_at") or payload.get("recorded_at")
        try:
            event_day = date.fromisoformat(str(created)[:10])
        except (TypeError, ValueError):
            continue
        activity_count += 1
        if event_day in buckets:
            buckets[event_day] += 1
        event_type = event["type"]
        if event_type == "practice_trial_completed":
            practice_count += 1
            xp += 10
        elif event_type == "training_trial_completed":
            training_count += 1
            xp += 10
            interaction = payload.get("interaction") or {}
            if interaction.get("hint_count", payload.get("hint_count", 0)) > 0:
                assisted_count += 1

    activity = {
        "window_days": 35,
        "start_date": start.isoformat(),
        "end_date": day.isoformat(),
        "buckets": [{"date": key.isoformat(), "count": count} for key, count in buckets.items()],
        "total_valid_trials": activity_count,
    }
    participation = {
        "practice_trial_count": practice_count,
        "training_trial_count": training_count,
        "assisted_training_trial_count": assisted_count,
        "xp_per_valid_practice_or_training_trial": 10,
        "xp": xp,
        "level": xp // 100 + 1,
        "xp_into_level": xp % 100,
        "xp_to_next_level": 100 - (xp % 100),
        "interpretation": "XP records valid practice participation, not cognitive performance or task scores.",
    }
    return activity, participation


def _coverage(profile: dict[str, Any]) -> dict[str, Any]:
    dimensions = profile.get("dimensions") or {}
    rows = []
    for name, required in _DIMENSIONS:
        result = dimensions.get(name) or {}
        rows.append({
            "dimension": name,
            "status": result.get("status", "NOT_ASSESSED"),
            "index_0_100": result.get("index_0_100"),
            "evidence_count": result.get("evidence_count", 0),
            "required_evidence_count": required,
            "uncertainty_status": result.get("uncertainty_status"),
            "latest_snapshot_id": result.get("latest_snapshot_id"),
            "evidence_ids": result.get("evidence_ids", []),
        })
    return {
        "assessed_count": sum(row["status"] == "ASSESSED" for row in rows),
        "total_count": len(_DIMENSIONS),
        "dimensions": rows,
    }


def _collaboration(store: Any, learner_id: str) -> dict[str, Any]:
    score = collaboration_score(store, learner_id)
    events = store.events(learner_id=learner_id)
    opportunities = {
        event["payload"].get("opportunity_id", event["event_id"]): event["payload"].get("dimension")
        for event in events
        if event["type"] == "collaboration_opportunity_issued"
        and event["payload"].get("sample_data") is not True
    }
    evaluated = {
        event["payload"].get("opportunity_id")
        for event in events
        if event["type"] == "collaboration_action_recorded"
        and event["payload"].get("opportunity_id") in opportunities
        and event["payload"].get("dimension") == opportunities[event["payload"].get("opportunity_id")]
        and event["payload"].get("rubric_points") in {0, 100}
    }
    return {
        "score": score,
        "opportunity_count": len(opportunities),
        "evaluated_opportunity_count": len(evaluated),
        "open_opportunity_count": len(set(opportunities) - evaluated),
    }


def _milestone(
    milestone_id: str,
    title: str,
    description: str,
    achieved: bool,
    progress_current: int,
    progress_target: int,
    evidence_ids: list[str],
) -> dict[str, Any]:
    return {
        "id": milestone_id,
        "title": title,
        "description": description,
        "achieved": achieved,
        "progress_current": min(progress_target, max(0, progress_current)),
        "progress_target": progress_target,
        "evidence_ids": list(dict.fromkeys(evidence_ids)),
    }


def _milestones(profile: dict[str, Any], events: list[dict[str, Any]], store: Any) -> list[dict[str, Any]]:
    """Build evidence-backed Quest milestones from canonical learner events."""
    event_by_id = {event.get("event_id"): event for event in events if event.get("event_id")}

    practices = [
        event for event in events
        if _eligible_trial(event) and event.get("type") == "practice_trial_completed"
    ]
    practices.sort(key=lambda event: (event.get("created_at") or "", event.get("event_id") or ""))
    first_practice = practices[0] if practices else None

    valid_training_trials: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "training_trial_completed":
            continue
        payload = event.get("payload") or {}
        interaction = payload.get("interaction") or {}
        block_id = payload.get("training_block_id")
        item_id = payload.get("item_id")
        if (
            payload.get("phase") == "training"
            and payload.get("sample_data") is not True
            and not interaction.get("visibility_interrupted", payload.get("visibility_interrupted", False))
            and block_id and item_id
        ):
            valid_training_trials.setdefault((str(block_id), str(item_id)), event)

    decisions: list[tuple[dict[str, Any], list[str]]] = []
    for event in events:
        if event.get("type") != "difficulty_changed":
            continue
        payload = event.get("payload") or {}
        block_id = payload.get("training_block_id")
        references = payload.get("evidence_ids") or []
        if (
            payload.get("phase") != "training"
            or payload.get("sample_data") is True
            or payload.get("action") not in {"up", "down", "hold"}
            or not block_id
            or not isinstance(references, list)
        ):
            continue
        persisted_decision = store.get_decision(str(block_id))
        if (
            not persisted_decision
            or persisted_decision.get("action") != payload.get("action")
            or persisted_decision.get("trial_count") != 4
            or persisted_decision.get("session_id") != event.get("session_id")
            or persisted_decision.get("old_tier") != payload.get("old_tier")
            or persisted_decision.get("new_tier") != payload.get("new_tier")
            or persisted_decision.get("evidence_ids") != references
            or persisted_decision.get("created_at") != payload.get("recorded_at")
        ):
            continue
        if persisted_decision.get("event_id"):
            if persisted_decision["event_id"] != event.get("event_id"):
                continue
        else:
            # The current Store decision row has no event_id column. Its row and
            # linked event are written in one transaction; require that this is
            # the sole canonical event that exactly mirrors the saved decision.
            matching_decisions = [
                candidate for candidate in events
                if candidate.get("type") == "difficulty_changed"
                and (candidate.get("payload") or {}).get("training_block_id") == block_id
                and candidate.get("session_id") == persisted_decision.get("session_id")
                and (candidate.get("payload") or {}).get("action") == persisted_decision.get("action")
                and (candidate.get("payload") or {}).get("old_tier") == persisted_decision.get("old_tier")
                and (candidate.get("payload") or {}).get("new_tier") == persisted_decision.get("new_tier")
                and (candidate.get("payload") or {}).get("evidence_ids") == references
                and (candidate.get("payload") or {}).get("recorded_at") == persisted_decision.get("created_at")
                and ((candidate.get("payload") or {}).get("observed") or {}).get("trial_count") == 4
            ]
            if len(matching_decisions) != 1 or matching_decisions[0].get("event_id") != event.get("event_id"):
                continue
        valid_refs = []
        for event_id in references:
            trial = event_by_id.get(event_id)
            if not trial or trial.get("type") != "training_trial_completed":
                continue
            trial_payload = trial.get("payload") or {}
            key = (str(block_id), str(trial_payload.get("item_id") or ""))
            if (
                key in valid_training_trials
                and trial_payload.get("training_block_id") == block_id
                and trial_payload.get("phase") == "training"
                and trial_payload.get("sample_data") is not True
                and not (trial_payload.get("interaction") or {}).get(
                    "visibility_interrupted", trial_payload.get("visibility_interrupted", False)
                )
                and trial.get("session_id") == event.get("session_id")
                and trial.get("event_id") == event_id
            ):
                valid_refs.append(event_id)
        if (
            len(set(valid_refs)) >= 4
            and set(valid_refs) == set(persisted_decision.get("evidence_ids") or [])
        ):
            decisions.append((event, list(dict.fromkeys(valid_refs))))
    decisions.sort(key=lambda pair: (pair[0].get("created_at") or "", pair[0].get("event_id") or ""))
    first_decision, decision_trials = decisions[0] if decisions else (None, [])

    profile_dimensions = profile.get("dimensions") or {}
    assessed_dimensions = 0
    assessment_evidence: list[str] = []
    for dimension, required in _DIMENSIONS:
        exercise_id = _DIMENSION_EXERCISES[dimension]
        estimate = profile_dimensions.get(dimension) or {}
        raw_ids = estimate.get("evidence_ids") or []
        valid_ids = []
        for event_id in raw_ids:
            event = event_by_id.get(event_id)
            if not event or event.get("type") not in _TRIAL_PHASES:
                continue
            payload = event.get("payload") or {}
            interaction = payload.get("interaction") or {}
            if (
                payload.get("exercise_id") == exercise_id
                and payload.get("phase") == _TRIAL_PHASES.get(event.get("type"))
                and not interaction.get("visibility_interrupted", payload.get("visibility_interrupted", False))
                and not interaction.get("hint_count", payload.get("hint_count", 0))
                and payload.get("sample_data") is not True
            ):
                valid_ids.append(event_id)
        is_assessed = estimate.get("completed") is True and len(set(valid_ids)) >= required
        if is_assessed:
            assessed_dimensions += 1
            assessment_evidence.extend(valid_ids)

    opportunity_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "collaboration_opportunity_issued":
            continue
        payload = event.get("payload") or {}
        dimension = payload.get("dimension")
        if (
            payload.get("sample_data") is not True
            and dimension in _COLLABORATION_DIMENSIONS
            and payload.get("source_event_id") in event_by_id
        ):
            opportunity_by_id[event.get("event_id")] = payload
    evaluated: dict[str, list[str]] = {dimension: [] for dimension in _COLLABORATION_DIMENSIONS}
    for event in events:
        if event.get("type") != "collaboration_action_recorded":
            continue
        payload = event.get("payload") or {}
        opportunity_id = payload.get("opportunity_id")
        opportunity = opportunity_by_id.get(opportunity_id)
        dimension = payload.get("dimension")
        if (
            payload.get("sample_data") is True
            or opportunity is None
            or dimension not in evaluated
            or opportunity.get("dimension") != dimension
            or payload.get("rubric_points") not in {0, 100}
            or event.get("session_id") != event_by_id.get(opportunity_id, {}).get("session_id")
        ):
            continue
        source_id = opportunity.get("source_event_id")
        linked_ids = [event.get("event_id"), opportunity_id, source_id]
        linked_ids.extend(payload.get("evidence_ids") or [])
        evaluated[dimension] = list(dict.fromkeys(
            evaluated[dimension] + [event_id for event_id in linked_ids if event_id in event_by_id]
        ))
    collaboration_count = sum(bool(evaluated[dimension]) for dimension in _COLLABORATION_DIMENSIONS)
    collaboration_evidence = [
        event_id for dimension in _COLLABORATION_DIMENSIONS for event_id in evaluated[dimension]
    ]

    practice_ids = [first_practice.get("event_id")] if first_practice else []
    decision_ids = ([first_decision.get("event_id")] + decision_trials) if first_decision else []
    return [
        _milestone(
            "first_valid_practice", "First practice completed",
            "A valid, uninterrupted practice trial was saved.", bool(first_practice),
            1 if first_practice else 0, 1, practice_ids,
        ),
        _milestone(
            "first_completed_training_block", "First training block completed",
            "A training block saved its first evidence-backed difficulty decision, including a hold.",
            bool(first_decision), len(decision_trials) if first_decision else max(
                (sum(1 for (block, _item) in valid_training_trials if block == candidate)
                 for candidate in {block for block, _item in valid_training_trials}), default=0,
            ), 4, decision_ids,
        ),
        _milestone(
            "all_five_families_assessed", "All five task families assessed",
            "Each task family has its required fixed, unassisted evidence for a preliminary estimate.",
            assessed_dimensions == len(_DIMENSIONS), assessed_dimensions, len(_DIMENSIONS), assessment_evidence,
        ),
        _milestone(
            "all_collaboration_dimensions_evaluated", "Collaboration evidence across five areas",
            "A genuine, recorded opportunity has an evaluated action in each collaboration area.",
            collaboration_count == len(_COLLABORATION_DIMENSIONS), collaboration_count,
            len(_COLLABORATION_DIMENSIONS), collaboration_evidence,
        ),
    ]
def build_dashboard(
    learner_id: str,
    store: Any,
    profile_reader: Callable[[str], dict[str, Any]],
    event_serializer: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Assemble one non-mutating DTO consumed by both presentation modes."""
    profile_record = profile_reader(learner_id)
    source_events = store.events(learner_id=learner_id)
    serialized_events = [event_serializer(event) for event in source_events]
    # Theme and goal preference updates remain canonically recorded but are
    # presentation settings, not evidence, and must not enter the shared data view.
    evidence_events = [event for event in serialized_events if event.get("type") not in _PREFERENCE_EVENTS]
    for event in evidence_events:
        event.setdefault("type", event.get("event_type"))

    from .plan_v3 import refresh_plan_execution_status
    plans = [refresh_plan_execution_status(store, plan, learner_id) for plan in store.plans(learner_id)]
    latest_recommendation_event = next(
        (event for event in reversed(evidence_events) if event.get("type") == "exercise_recommended"), None,
    )
    latest_recommendation = None
    if latest_recommendation_event:
        latest_recommendation = {
            "event_id": latest_recommendation_event["event_id"],
            "created_at": latest_recommendation_event["created_at"],
            **latest_recommendation_event.get("payload", {}),
        }
    profile_view = {
        "learner_id": learner_id,
        "dimensions": profile_record.get("dimensions", {}),
        "snapshots": profile_record.get("snapshots", []),
        "interpretation": profile_record.get("interpretation"),
    }
    activity, participation = _activity(source_events)
    milestones = _milestones(profile_record, source_events, store)
    return {
        "learner_id": learner_id,
        "preferences": store.current_preferences(learner_id),
        "profile": profile_view,
        "events": evidence_events,
        "plan": {"latest": plans[-1] if plans else None, "history": plans},
        "recommendation": latest_recommendation,
        "activity": activity,
        "participation": participation,
        "task_coverage": _coverage(profile_view),
        "collaboration": _collaboration(store, learner_id),
        "milestones": milestones,
    }
