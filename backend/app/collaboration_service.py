"""Evidence-gated, auditable AI-collaboration opportunities and score."""
from __future__ import annotations

import uuid
from typing import Any

COLLABORATION_VERSION = "collaboration-v1"
WEIGHTS = {"clarification": 20, "critical_verification": 25, "iteration": 20, "autonomy": 20, "responsible_use": 15}
_NAMESPACE = uuid.UUID("e3192447-5227-4f2a-ad22-ce2e189a38fb")


class CollaborationEvidenceError(ValueError):
    """The requested action lacks a genuine backend-issued opportunity/evidence."""


def _text(value: Any, minimum: int) -> str:
    if not isinstance(value, str):
        raise CollaborationEvidenceError("meaningful text evidence is required")
    text = " ".join(value.split())
    if len(text) < minimum:
        raise CollaborationEvidenceError(f"text evidence must contain at least {minimum} characters")
    return text[:2000]


def _read_saved_event(store: Any, event_id: str, session_id: str | None = None) -> dict[str, Any]:
    events = store.events(session_id=session_id) if session_id else store.events()
    for event in events:
        if event["event_id"] == event_id:
            return event
    raise CollaborationEvidenceError("source event was not found in canonical SQLite history")


def _coach_response(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("coach_response") or payload.get("response")
    return candidate if isinstance(candidate, dict) else {}


def _read_owned_event(store: Any, event_id: str, learner_id: str) -> dict[str, Any]:
    for event in store.events(learner_id=learner_id):
        if event["event_id"] == event_id:
            return event
    raise CollaborationEvidenceError("evidence reference is not saved for this learner")


def issue_opportunities(store: Any, source_event_id: str, *, session_id: str | None = None) -> list[dict[str, Any]]:
    """Issue only opportunities supported by a saved coach turn and linked records.

    Expected backend-derived collaboration_context keys are clarification_follow_up,
    verification_evidence_ids, suggestion_event_id, autonomy_recommendation_event_id,
    consent_event_id, responsible_use_notice_shown. IDs are always revalidated here.
    """
    source = _read_saved_event(store, source_event_id, session_id)
    payload = source["payload"]
    if source["type"] != "coaching_message_sent" or payload.get("sample_data") is True:
        raise CollaborationEvidenceError("only an actual, non-sample saved coaching event can issue opportunities")
    response = _coach_response(payload)
    evidence_ids = response.get("evidence_ids", payload.get("evidence_ids", []))
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise CollaborationEvidenceError("the coach event must cite saved canonical evidence")
    evidence_ids = list(dict.fromkeys(str(item) for item in evidence_ids if isinstance(item, str) and item))
    session = store.get_session(source["session_id"])
    if not session or payload.get("learner_id") != session["learner_id"]:
        raise CollaborationEvidenceError("coach source must match its canonical session owner")
    saved_events = store.events(learner_id=session["learner_id"])
    saved_by_id = {event["event_id"]: event for event in saved_events}
    if not evidence_ids or any(item not in saved_by_id for item in evidence_ids):
        raise CollaborationEvidenceError("coach evidence references must resolve to events owned by this learner")
    rationale = _text(response.get("rationale"), 20)
    follow_up = _text(response.get("follow_up"), 12)
    caveat = _text(response.get("caveat"), 20)
    if not any(token in caveat.casefold() for token in ("uncertain", "preliminary", "non-clinical", "not a clinical")):
        raise CollaborationEvidenceError("the coaching opportunity must display an uncertainty or non-clinical caveat")

    context = payload.get("collaboration_context") or {}
    candidates: dict[str, tuple[str, list[str], dict[str, Any]]] = {}
    clarification = context.get("clarification_follow_up")
    if isinstance(clarification, str) and clarification == follow_up and "?" in clarification and any(
        word in clarification.casefold() for word in ("unclear", "clarify", "question", "explain")
    ):
        candidates["clarification"] = (clarification, [source_event_id, *evidence_ids], {"coach_follow_up": clarification})

    verify_ids = context.get("verification_evidence_ids")
    if isinstance(verify_ids, list) and verify_ids and set(verify_ids).issubset(set(evidence_ids)):
        if any(word in follow_up.casefold() for word in ("inspect", "verify", "check", "evidence")):
            candidates["critical_verification"] = (
                "Inspect a cited event and explain what it supports or leaves uncertain.",
                [source_event_id, *verify_ids], {"inspectable_evidence_ids": list(dict.fromkeys(verify_ids)),
                                                  "follow_up": follow_up})

    suggestion_id = context.get("suggestion_event_id")
    suggestion = saved_by_id.get(suggestion_id)
    if suggestion and suggestion["type"] in {"exercise_recommended", "intervention_selected"}:
        if suggestion["payload"].get("sample_data") is not True and suggestion_id in {source_event_id, *evidence_ids}:
            candidates["iteration"] = (
                "Question or revise the linked saved suggestion and explain the change.",
                [source_event_id, suggestion_id, *evidence_ids], {"suggestion_event_id": suggestion_id})

    autonomy_id = context.get("autonomy_recommendation_event_id")
    autonomy_event = saved_by_id.get(autonomy_id)
    if autonomy_event and autonomy_event["type"] == "exercise_recommended" and autonomy_id in {source_event_id, *evidence_ids}:
        options = autonomy_event["payload"].get("alternatives")
        if isinstance(options, list) and options:
            candidates["autonomy"] = (
                "Choose whether to follow, modify, or decline the saved recommendation, and record why.",
                [source_event_id, autonomy_id, *evidence_ids],
                {"recommendation_event_id": autonomy_id, "available_alternatives": options})

    consent_id = context.get("consent_event_id")
    consent = saved_by_id.get(consent_id)
    if (consent and consent["type"] == "consent_recorded"
            and consent["payload"].get("consent", {}).get("accepted") is True
            and consent["payload"].get("consent", {}).get("local_data_notice_acknowledged") is True):
        if context.get("responsible_use_notice_shown") is True:
            candidates["responsible_use"] = (
                "Choose how to handle local or optional remote coaching after reviewing the saved notice.",
                [source_event_id, consent_id], {"consent_event_id": consent_id, "notice_shown": True})

    opportunities = []
    for dimension in WEIGHTS:
        if dimension not in candidates:
            continue
        prompt, refs, context_data = candidates[dimension]
        opportunity_id = str(uuid.uuid5(_NAMESPACE, f"opportunity:{source_event_id}:{dimension}"))
        opportunity = {
            "event_id": opportunity_id, "learner_id": payload.get("learner_id"),
            "session_id": source["session_id"], "event_type": "collaboration_opportunity_issued",
            "phase": "collaboration", "collaboration_version": COLLABORATION_VERSION,
            "opportunity_id": opportunity_id, "dimension": dimension, "source_event_id": source_event_id,
            "evidence_ids": list(dict.fromkeys(refs)), "opportunity_context": context_data,
            "prompt": prompt, "sample_data": False,
            "recorded_at": payload.get("recorded_at") or source["created_at"],
        }
        saved, replayed = store.add_event(opportunity_id, source["session_id"], "collaboration_opportunity_issued", opportunity)
        opportunities.append({"opportunity": saved, "replayed": replayed})
    return opportunities


def _action_result(dimension: str, evidence: dict[str, Any], opportunity: dict[str, Any]) -> tuple[str, dict[str, Any], int]:
    if evidence.get("action") == "pass":
        return "pass", {"action": "pass", "reason": _text(evidence.get("reason"), 20)}, 0
    if dimension == "clarification":
        question = _text(evidence.get("question"), 15)
        if len(question.split()) < 4 or "?" not in question:
            raise CollaborationEvidenceError("clarification must be a specific question of at least four words")
        return "asked_clarifying_question", {"question": question}, 100
    if dimension == "critical_verification":
        cited = evidence.get("checked_evidence_ids")
        inspections = evidence.get("inspection_event_ids")
        valid = set(opportunity.get("opportunity_context", {}).get("inspectable_evidence_ids", []))
        if not isinstance(cited, list) or not cited or any(ref not in valid for ref in cited):
            raise CollaborationEvidenceError("verification must name evidence IDs explicitly offered for inspection")
        if not isinstance(inspections, list) or not inspections:
            raise CollaborationEvidenceError("verification requires a prior canonical inspection event")
        note = _text(evidence.get("verification_note"), 25)
        return "checked_cited_evidence", {
            "checked_evidence_ids": sorted(set(cited)), "inspection_event_ids": sorted(set(inspections)),
            "verification_note": note,
        }, 100
    if dimension == "iteration":
        suggestion_id = evidence.get("suggestion_event_id")
        if suggestion_id != opportunity.get("opportunity_context", {}).get("suggestion_event_id"):
            raise CollaborationEvidenceError("iteration must refer to the actual linked suggestion")
        summary = _text(evidence.get("revision_summary"), 25)
        changed_id = evidence.get("changed_choice_event_id")
        if not isinstance(changed_id, str):
            raise CollaborationEvidenceError("iteration requires a canonical event for the changed choice or result")
        return "revised_or_questioned_suggestion", {
            "suggestion_event_id": suggestion_id, "changed_choice_event_id": changed_id,
            "revision_summary": summary}, 100
    if dimension == "autonomy":
        choice_id = evidence.get("choice_event_id")
        if not isinstance(choice_id, str):
            raise CollaborationEvidenceError("autonomy requires a saved independent choice/trial event")
        choice = evidence.get("choice")
        if choice not in {"accept", "modify", "decline"}:
            raise CollaborationEvidenceError("autonomy choice must be accept, modify, or decline")
        return "made_independent_choice", {
            "choice_event_id": choice_id, "choice": choice, "reason": _text(evidence.get("reason"), 20)}, 100
    if dimension == "responsible_use":
        consent_id = evidence.get("consent_event_id")
        if consent_id != opportunity.get("opportunity_context", {}).get("consent_event_id"):
            raise CollaborationEvidenceError("responsible-use action must link the saved consent/notice")
        choice_id = evidence.get("choice_event_id")
        if not isinstance(choice_id, str):
            raise CollaborationEvidenceError("responsible-use action requires a saved privacy/uncertainty choice")
        choice = evidence.get("choice")
        if choice not in {"keep_local", "decline_remote", "proceed_after_notice", "pause_for_uncertainty"}:
            raise CollaborationEvidenceError("responsible-use choice is outside the disclosed options")
        return "made_informed_data_or_uncertainty_choice", {
            "consent_event_id": consent_id, "choice_event_id": choice_id, "choice": choice,
            "reason": _text(evidence.get("reason"), 20)}, 100
    raise CollaborationEvidenceError("unknown collaboration dimension")


def _validate_referenced_event(store: Any, event_id: str, session_id: str, expected_types: set[str],
                               *, same_session: bool = True) -> dict[str, Any]:
    owner = store.get_session(session_id)
    if not owner:
        raise CollaborationEvidenceError("collaboration session no longer exists")
    event = (_read_saved_event(store, event_id, session_id) if same_session
             else _read_owned_event(store, event_id, owner["learner_id"]))
    if event["type"] not in expected_types or event["payload"].get("sample_data") is True:
        raise CollaborationEvidenceError("action evidence must reference the required real saved event type")
    return event


def record_action(store: Any, session_id: str, opportunity_id: str, action_evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate meaningful evidence and save one immutable action per opportunity."""
    opportunity_event = _read_saved_event(store, opportunity_id, session_id)
    opportunity = opportunity_event["payload"]
    if opportunity_event["type"] != "collaboration_opportunity_issued" or opportunity.get("opportunity_id") != opportunity_id:
        raise CollaborationEvidenceError("opportunity was not issued by the backend")
    dimension = opportunity.get("dimension")
    action_type, normalized, points = _action_result(dimension, action_evidence, opportunity)
    refs = []
    if action_type != "pass":
        if dimension == "clarification":
            refs = [opportunity_id]
        elif dimension == "critical_verification":
            for evidence_id in normalized["checked_evidence_ids"]:
                _read_owned_event(store, evidence_id, opportunity.get("learner_id"))
            for inspection_id in normalized["inspection_event_ids"]:
                inspection = _validate_referenced_event(store, inspection_id, session_id, {"collaboration_evidence_inspected"})
                if (inspection["payload"].get("opportunity_id") != opportunity_id
                        or inspection["payload"].get("inspected_event_id") not in normalized["checked_evidence_ids"]):
                    raise CollaborationEvidenceError("inspection record must match this opportunity and checked evidence")
                if inspection["created_at"] < opportunity_event["created_at"]:
                    raise CollaborationEvidenceError("inspection must follow its issued opportunity")
            refs = [*normalized["checked_evidence_ids"], *normalized["inspection_event_ids"]]
        elif dimension == "iteration":
            suggestion = _validate_referenced_event(store, normalized["suggestion_event_id"], session_id, {"exercise_recommended", "intervention_selected"}, same_session=False)
            changed = _validate_referenced_event(store, normalized["changed_choice_event_id"], session_id, {"exercise_recommended", "training_block_started", "suggestion_revised"})
            if suggestion["event_id"] not in opportunity.get("evidence_ids", []):
                raise CollaborationEvidenceError("iteration suggestion is not linked to this opportunity")
            if changed["payload"].get("suggestion_event_id") != suggestion["event_id"] and changed["payload"].get("source_event_id") != suggestion["event_id"]:
                raise CollaborationEvidenceError("iteration result must link back to the actual saved suggestion")
            refs = [suggestion["event_id"], changed["event_id"]]
        elif dimension == "autonomy":
            choice = _validate_referenced_event(store, normalized["choice_event_id"], session_id, {"training_block_started", "exercise_recommended", "independent_choice_made"})
            linked_recommendation = choice["payload"].get("recommendation_event_id") or choice["payload"].get("source_event_id")
            if choice["event_id"] not in opportunity.get("evidence_ids", []) and linked_recommendation != opportunity.get("opportunity_context", {}).get("recommendation_event_id"):
                raise CollaborationEvidenceError("independent choice event is not linked to this opportunity")
            refs = [choice["event_id"]]
        elif dimension == "responsible_use":
            consent = _validate_referenced_event(store, normalized["consent_event_id"], session_id, {"consent_recorded"}, same_session=False)
            choice = _validate_referenced_event(store, normalized["choice_event_id"], session_id, {"responsible_use_choice", "remote_coach_opt_in"})
            if consent["event_id"] not in opportunity.get("evidence_ids", []):
                raise CollaborationEvidenceError("consent event is not linked to this opportunity")
            if (choice["payload"].get("consent_event_id") != consent["event_id"]
                    and choice["payload"].get("source_event_id") != consent["event_id"]):
                raise CollaborationEvidenceError("privacy choice event must link back to the saved notice")
            refs = [consent["event_id"], choice["event_id"]]
    # Grounding evidence and the original suggestion precede the opportunity. The
    # changed choice/trial itself must occur after the opportunity was presented.
    post_opportunity_refs = []
    if dimension == "iteration" and action_type != "pass":
        post_opportunity_refs = [normalized["changed_choice_event_id"]]
    elif dimension == "autonomy" and action_type != "pass":
        post_opportunity_refs = [normalized["choice_event_id"]]
    elif dimension == "responsible_use" and action_type != "pass":
        post_opportunity_refs = [normalized["choice_event_id"]]
    for ref in post_opportunity_refs:
        referenced = _read_saved_event(store, ref, session_id)
        if referenced["created_at"] < opportunity_event["created_at"]:
            raise CollaborationEvidenceError("action evidence must be recorded after its opportunity")
    action_event_id = str(uuid.uuid5(_NAMESPACE, f"action:{opportunity_id}"))
    event = {
        "event_id": action_event_id, "learner_id": opportunity.get("learner_id"),
        "session_id": session_id, "event_type": "collaboration_action_recorded", "phase": "collaboration",
        "collaboration_version": COLLABORATION_VERSION, "opportunity_id": opportunity_id,
        "source_event_id": opportunity["source_event_id"], "dimension": dimension, "action_type": action_type,
        "action_evidence": normalized, "rubric_points": points,
        "evidence_ids": list(dict.fromkeys([opportunity_id, opportunity["source_event_id"], *opportunity.get("evidence_ids", []), *refs])),
        "sample_data": False, "recorded_at": opportunity.get("recorded_at"),
    }
    saved, replayed = store.add_event(action_event_id, session_id, "collaboration_action_recorded", event)
    return {"event": saved, "replayed": replayed}


def collaboration_score(store: Any, learner_id: str = "demo-user") -> dict[str, Any]:
    """Aggregate distinct evaluated opportunities with transparent weighted evidence."""
    events = store.events(learner_id=learner_id)
    opportunities = {e["event_id"]: e["payload"] for e in events if e["type"] == "collaboration_opportunity_issued"}
    by_dimension: dict[str, list[dict[str, Any]]] = {dimension: [] for dimension in WEIGHTS}
    seen: set[str] = set()
    for entry in events:
        if entry["type"] != "collaboration_action_recorded":
            continue
        action = entry["payload"]
        oid, dimension = action.get("opportunity_id"), action.get("dimension")
        opportunity = opportunities.get(oid)
        if not opportunity or dimension not in WEIGHTS or opportunity.get("dimension") != dimension or oid in seen:
            continue
        if action.get("rubric_points") not in {0, 100}:
            continue
        seen.add(oid)
        by_dimension[dimension].append({
            "score_0_100": action["rubric_points"], "opportunity_id": oid, "action_event_id": entry["event_id"],
            "source_event_id": opportunity["source_event_id"], "evidence_ids": action.get("evidence_ids", []),
            "action_type": action.get("action_type"),
        })
    dimensions = {}
    for dimension, weight in WEIGHTS.items():
        rows = by_dimension[dimension]
        dimensions[dimension] = {
            "status": "ASSESSED" if rows else "NOT_ASSESSED",
            "score_0_100": round(sum(row["score_0_100"] for row in rows) / len(rows), 2) if rows else None,
            "weight_percent": weight, "evaluated_opportunity_count": len(rows), "evidence": rows,
            "uncertainty_status": "PRELIMINARY_HIGH_UNCERTAINTY" if rows else "NOT_ENOUGH_COLLABORATION_EVIDENCE",
        }
    ready = all(dimensions[d]["evaluated_opportunity_count"] >= 1 for d in WEIGHTS)
    overall = round(sum(dimensions[d]["score_0_100"] * WEIGHTS[d] / 100 for d in WEIGHTS), 2) if ready else None
    return {
        "learner_id": learner_id, "collaboration_version": COLLABORATION_VERSION, "score_0_100": overall,
        "status": "PRELIMINARY_HIGH_UNCERTAINTY" if ready else "NOT_ENOUGH_COLLABORATION_EVIDENCE",
        "formula": "clarification*0.20 + critical_verification*0.25 + iteration*0.20 + autonomy*0.20 + responsible_use*0.15; each dimension is the mean of evaluated genuine opportunity rubrics (0 or 100).",
        "weights_percent": dict(WEIGHTS), "dimensions": dimensions,
        "evaluated_opportunity_count": sum(len(rows) for rows in by_dimension.values()), "message_count_used": False,
        "interpretation": "A preliminary interaction-evidence summary, not a measure of intelligence or a validated trait. Unanswered opportunities remain unassessed.",
    }




