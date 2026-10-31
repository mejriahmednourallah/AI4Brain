"""HTTP routes for transparent, saved-evidence AI collaboration."""
from __future__ import annotations

import uuid
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .collaboration_service import (
    CollaborationEvidenceError,
    collaboration_score,
    issue_opportunities,
    record_action,
)
from .policy import DIMENSION_TO_EXERCISE, EXERCISE_TO_DIMENSION
from .storage import utc_now

_NAMESPACE = uuid.UUID("29c31283-3498-4b87-a313-dd1ec024e3d2")
_VALID_GOALS = frozenset(DIMENSION_TO_EXERCISE)


class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, max_length=120)
    event_id: str = Field(min_length=1, max_length=120)
    opportunity_id: str | None = Field(default=None, min_length=1, max_length=120)


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, max_length=120)
    opportunity_id: str = Field(min_length=1, max_length=120)
    action: Literal["pass"] | None = None
    question: str | None = Field(default=None, min_length=15, max_length=2000)
    checked_evidence_ids: list[str] | None = None
    verification_note: str | None = Field(default=None, min_length=25, max_length=2000)
    revision_summary: str | None = Field(default=None, min_length=25, max_length=2000)
    new_goal_dimension: str | None = None
    choice: Literal[
        "accept", "modify", "decline",
        "keep_local", "decline_remote", "pause_for_uncertainty",
    ] | None = None
    reason: str | None = Field(default=None, min_length=20, max_length=2000)


def _stable_event_id(opportunity_id: str, kind: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{opportunity_id}:{kind}"))


def _find_event(store: Any, event_id: str, *, session_id: str | None = None,
                learner_id: str = "demo-user") -> dict[str, Any] | None:
    events = store.events(session_id=session_id) if session_id else store.events(learner_id=learner_id)
    return next((event for event in events if event["event_id"] == event_id), None)


def _session(store: Any, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if not session or session.get("learner_id") != "demo-user":
        raise HTTPException(404, "session not found")
    return session


def _opportunity(store: Any, session_id: str, opportunity_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    event = _find_event(store, opportunity_id, session_id=session_id)
    if not event or event["type"] != "collaboration_opportunity_issued":
        raise HTTPException(404, "collaboration opportunity not found in this session")
    payload = event["payload"]
    if payload.get("learner_id") != "demo-user" or payload.get("opportunity_id") != opportunity_id:
        raise HTTPException(404, "collaboration opportunity not found in this session")
    return event, payload


def _saved_event(store: Any, event_id: str, session_id: str | None = None) -> dict[str, Any]:
    event = _find_event(store, event_id, session_id=session_id)
    if not event:
        raise HTTPException(404, "evidence event not found for this learner")
    return event


def _raise_evidence(exc: Exception) -> None:
    if isinstance(exc, CollaborationEvidenceError):
        raise HTTPException(422, str(exc)) from exc
    raise HTTPException(409, "The saved collaboration event conflicts with a prior request.") from exc


def _plan_id(result: Any, goal: str) -> str:
    if not isinstance(result, dict):
        raise HTTPException(409, "Plan regeneration did not return a saved plan.")
    plan = result.get("latest") or result.get("plan") or result
    if not isinstance(plan, dict) or not plan.get("plan_id") or plan.get("goal") != goal:
        raise HTTPException(409, "Plan regeneration did not save a plan for the selected goal.")
    return str(plan["plan_id"])


def _ensure_plan(regenerate_plan: Callable[[str, str], Any] | None, session_id: str, goal: str) -> str:
    if regenerate_plan is None:
        raise HTTPException(409, "Plan regeneration is unavailable; the goal change was not recorded.")
    try:
        result = regenerate_plan(session_id, goal)
    except Exception as exc:
        # Keep provider errors, paths, and implementation details out of the API.
        raise HTTPException(409, "The plan could not be regenerated for this goal.") from exc
    return _plan_id(result, goal)


def _issue_side_event(store: Any, session_id: str, opportunity: dict[str, Any], kind: str,
                      payload_fields: dict[str, Any]) -> dict[str, Any]:
    event_id = _stable_event_id(opportunity["opportunity_id"], kind)
    payload = {
        "event_id": event_id, "learner_id": opportunity["learner_id"], "session_id": session_id,
        "event_type": kind, "phase": "collaboration", "collaboration_version": "collaboration-v1",
        "opportunity_id": opportunity["opportunity_id"], "source_event_id": opportunity["source_event_id"],
        "evidence_ids": list(dict.fromkeys([opportunity["source_event_id"], *opportunity.get("evidence_ids", [])])),
        "sample_data": False, "recorded_at": utc_now(), **payload_fields,
    }
    try:
        saved, replayed = store.add_event(event_id, session_id, kind, payload)
    except KeyError as exc:
        raise HTTPException(404, "session not found") from exc
    except ValueError as exc:
        raise HTTPException(409, "This opportunity already has a different saved action.") from exc
    return {"event": saved, "replayed": replayed}


def _require_text(value: str | None, minimum: int, label: str) -> str:
    if not isinstance(value, str) or len(" ".join(value.split())) < minimum:
        raise HTTPException(422, f"{label} must contain at least {minimum} meaningful characters.")
    return " ".join(value.split())


def _only_fields(body: ActionRequest, allowed: set[str]) -> None:
    supplied = {name for name in body.model_fields_set if name not in {"session_id", "opportunity_id"}}
    extra = supplied - allowed
    if extra:
        raise HTTPException(422, "Fields do not match this collaboration opportunity.")


def _suggestion(store: Any, opportunity: dict[str, Any]) -> tuple[dict[str, Any], str]:
    context = opportunity.get("opportunity_context", {})
    suggestion_id = context.get("suggestion_event_id") or context.get("recommendation_event_id")
    if not suggestion_id:
        raise HTTPException(409, "The opportunity has no linked saved suggestion.")
    suggestion = _find_event(store, suggestion_id, learner_id=opportunity["learner_id"])
    if not suggestion or suggestion["type"] not in {"exercise_recommended", "intervention_selected"}:
        raise HTTPException(409, "The linked suggestion is no longer available.")
    dimension = suggestion["payload"].get("dimension") or suggestion["payload"].get("dimension_id")
    if dimension not in _VALID_GOALS and suggestion["payload"].get("exercise_id") in EXERCISE_TO_DIMENSION:
        dimension = EXERCISE_TO_DIMENSION[suggestion["payload"]["exercise_id"]]
    if dimension not in _VALID_GOALS:
        raise HTTPException(409, "The saved suggestion has no supported task dimension.")
    return suggestion, dimension


def _request_action_data(store: Any, body: ActionRequest, opportunity: dict[str, Any],
                         regenerate_plan: Callable[[str, str], Any] | None) -> dict[str, Any]:
    dimension = opportunity.get("dimension")
    if body.action == "pass":
        _only_fields(body, {"action", "reason"})
        return {"action": "pass", "reason": _require_text(body.reason, 20, "Pass reason")}

    if dimension == "clarification":
        _only_fields(body, {"question"})
        question = _require_text(body.question, 15, "Question")
        if len(question.split()) < 4 or "?" not in question:
            raise HTTPException(422, "Clarification must be a specific question of at least four words.")
        return {"question": question}

    if dimension == "critical_verification":
        _only_fields(body, {"checked_evidence_ids", "verification_note"})
        checked = body.checked_evidence_ids or []
        if not checked or len(set(checked)) != len(checked):
            raise HTTPException(422, "Select at least one distinct cited event that you inspected.")
        offered = set(opportunity.get("opportunity_context", {}).get("inspectable_evidence_ids", []))
        if any(event_id not in offered for event_id in checked):
            raise HTTPException(422, "The checked event was not cited in this verification opportunity.")
        history = store.events(session_id=body.session_id)
        inspections = []
        for event_id in checked:
            matching = [e for e in history if e["type"] == "collaboration_evidence_inspected"
                        and e["payload"].get("opportunity_id") == opportunity["opportunity_id"]
                        and e["payload"].get("inspected_event_id") == event_id]
            if not matching:
                raise HTTPException(409, "Inspect the cited evidence before recording critical verification.")
            inspections.append(matching[-1]["event_id"])
        note = _require_text(body.verification_note, 25, "Verification note")
        return {"checked_evidence_ids": checked, "inspection_event_ids": inspections,
                "verification_note": note}

    if dimension == "iteration":
        _only_fields(body, {"revision_summary", "new_goal_dimension", "reason"})
        suggestion, suggested_dimension = _suggestion(store, opportunity)
        _require_text(body.revision_summary, 25, "Revision summary")
        goal = body.new_goal_dimension
        if goal not in _VALID_GOALS:
            raise HTTPException(422, "Choose a supported cognitive-task goal.")
        if goal == suggested_dimension:
            raise HTTPException(422, "Iteration must select a goal different from the linked suggestion.")
        event_id = _stable_event_id(opportunity["opportunity_id"], "suggestion_revised")
        existing = _find_event(store, event_id, session_id=body.session_id)
        if existing:
            event = existing["payload"]
            if event.get("new_goal_dimension") != goal or event.get("suggestion_event_id") != suggestion["event_id"]:
                raise HTTPException(409, "This opportunity already records a different iteration.")
            plan_id = event.get("plan_id")
        else:
            plan_id = _ensure_plan(regenerate_plan, body.session_id, goal)
            current = _session(store, body.session_id)
            store.set_preferences(body.session_id, current["dashboard_mode"], goal)
            _issue_side_event(store, body.session_id, opportunity, "suggestion_revised", {
                "suggestion_event_id": suggestion["event_id"], "old_goal_dimension": suggested_dimension,
                "new_goal_dimension": goal, "revision_summary": body.revision_summary,
                "reason": body.reason, "plan_id": plan_id,
            })
        if not plan_id:
            raise HTTPException(409, "This saved iteration has no revised plan.")
        return {"suggestion_event_id": suggestion["event_id"], "changed_choice_event_id": event_id,
                "revision_summary": body.revision_summary or body.reason or f"Changed goal to {goal}."}

    if dimension == "autonomy":
        _only_fields(body, {"choice", "new_goal_dimension", "reason"})
        if body.choice not in {"accept", "modify", "decline"}:
            raise HTTPException(422, "Choose accept, modify, or decline.")
        _require_text(body.reason, 20, "Choice reason")
        suggestion, suggested_dimension = _suggestion(store, opportunity)
        choice_event_id = _stable_event_id(opportunity["opportunity_id"], "independent_choice_made")
        existing = _find_event(store, choice_event_id, session_id=body.session_id)
        if body.choice == "modify":
            selected_dimension = body.new_goal_dimension
            alternatives = suggestion["payload"].get("alternatives") or opportunity.get("opportunity_context", {}).get("available_alternatives", [])
            allowed = set()
            for alternative in alternatives:
                candidate = alternative.get("dimension") if isinstance(alternative, dict) else None
                exercise = alternative.get("exercise_id") if isinstance(alternative, dict) else None
                if candidate in _VALID_GOALS:
                    allowed.add(candidate)
                elif exercise in EXERCISE_TO_DIMENSION:
                    allowed.add(EXERCISE_TO_DIMENSION[exercise])
            if selected_dimension not in allowed or selected_dimension == suggested_dimension:
                raise HTTPException(422, "Modify must choose a different dimension from a saved recommendation alternative.")
        else:
            if body.new_goal_dimension is not None:
                raise HTTPException(422, "Only a modified choice can select another goal.")
            selected_dimension = suggested_dimension if body.choice == "accept" else None
        if existing:
            saved = existing["payload"]
            if saved.get("choice") != body.choice or saved.get("selected_goal_dimension") != selected_dimension:
                raise HTTPException(409, "This opportunity already records a different independent choice.")
            if body.choice == "modify" and saved.get("plan_id") is None:
                raise HTTPException(409, "The saved modified choice has no revised plan.")
        else:
            plan_id = None
            if body.choice == "modify":
                plan_id = _ensure_plan(regenerate_plan, body.session_id, selected_dimension)
                current = _session(store, body.session_id)
                store.set_preferences(body.session_id, current["dashboard_mode"], selected_dimension)
            _issue_side_event(store, body.session_id, opportunity, "independent_choice_made", {
                "recommendation_event_id": suggestion["event_id"], "choice": body.choice,
                "selected_goal_dimension": selected_dimension, "reason": body.reason,
                "plan_id": plan_id,
            })
        return {"choice_event_id": choice_event_id, "choice": body.choice, "reason": body.reason}

    if dimension == "responsible_use":
        _only_fields(body, {"choice", "reason"})
        if body.choice not in {"keep_local", "decline_remote", "pause_for_uncertainty"}:
            raise HTTPException(422, "Choose keep local, decline remote, or pause for uncertainty.")
        _require_text(body.reason, 20, "Choice reason")
        consent_id = opportunity.get("opportunity_context", {}).get("consent_event_id")
        consent = _find_event(store, consent_id, learner_id=opportunity["learner_id"]) if consent_id else None
        if not consent or consent["type"] != "consent_recorded" or not consent["payload"].get("consent", {}).get("local_data_notice_acknowledged"):
            raise HTTPException(409, "The saved local-data notice is unavailable for this opportunity.")
        choice_event_id = _stable_event_id(opportunity["opportunity_id"], "responsible_use_choice")
        existing = _find_event(store, choice_event_id, session_id=body.session_id)
        if existing:
            if existing["payload"].get("choice") != body.choice:
                raise HTTPException(409, "This opportunity already records a different data-use choice.")
        else:
            _issue_side_event(store, body.session_id, opportunity, "responsible_use_choice", {
                "consent_event_id": consent_id, "choice": body.choice, "reason": body.reason,
            })
        return {"consent_event_id": consent_id, "choice_event_id": choice_event_id,
                "choice": body.choice, "reason": body.reason}

    raise HTTPException(409, "This opportunity dimension is unsupported.")


def create_collaboration_router(store: Any, public_event: Callable[[dict[str, Any]], dict[str, Any]],
                                regenerate_plan: Callable[[str, str], Any] | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/collaboration/demo-user")
    def collaboration(session_id: str | None = None):
        if session_id is not None:
            _session(store, session_id)
        score = collaboration_score(store, "demo-user")
        events = store.events(learner_id="demo-user")
        if session_id is not None:
            events = [event for event in events if event["session_id"] == session_id]
        opportunity_events = [event for event in events if event["type"] == "collaboration_opportunity_issued"]
        actions = {event["payload"].get("opportunity_id"): event for event in events
                   if event["type"] == "collaboration_action_recorded"}
        opportunities = []
        for event in opportunity_events:
            payload = event["payload"]
            action = actions.get(payload.get("opportunity_id"))
            opportunities.append({
                "opportunity_id": payload["opportunity_id"], "dimension": payload["dimension"],
                "session_id": event["session_id"],
                "prompt": payload["prompt"], "status": "evaluated" if action else "open",
                "source_event_id": payload["source_event_id"], "evidence_ids": payload.get("evidence_ids", []),
                "inspectable_evidence_ids": payload.get("opportunity_context", {}).get("inspectable_evidence_ids", [])
                if payload.get("dimension") == "critical_verification" else [],
                "action_event_id": action["event_id"] if action else None,
                "action_type": action["payload"].get("action_type") if action else None,
                "score_0_100": action["payload"].get("rubric_points") if action else None,
                "weight_percent": score["dimensions"][payload["dimension"]]["weight_percent"],
            })
        open_items = [item for item in opportunities if item["status"] == "open"]
        return {"score": score, "opportunities": opportunities, "open_opportunities": open_items}

    @router.get("/api/collaboration/evidence/{event_id}")
    def read_cited_evidence(event_id: str, session_id: str, opportunity_id: str):
        _session(store, session_id)
        _, opportunity = _opportunity(store, session_id, opportunity_id)
        cited_ids = {opportunity.get("source_event_id"), *opportunity.get("evidence_ids", [])}
        if event_id not in cited_ids:
            raise HTTPException(409, "This event is not cited by the requested collaboration opportunity.")
        cited = _saved_event(store, event_id)
        return {"source_event": public_event(cited), "inspection_recorded": False}

    @router.post("/api/collaboration/inspect")
    def inspect(body: InspectRequest):
        _session(store, body.session_id)
        cited = _saved_event(store, body.event_id)
        if body.opportunity_id:
            opportunity_event, opportunity = _opportunity(store, body.session_id, body.opportunity_id)
            offered = opportunity.get("opportunity_context", {}).get("inspectable_evidence_ids", [])
            if opportunity.get("dimension") != "critical_verification" or body.event_id not in offered:
                raise HTTPException(409, "This event is not inspectable evidence in the requested verification opportunity.")
        else:
            opportunities = [event for event in store.events(session_id=body.session_id)
                            if event["type"] == "collaboration_opportunity_issued"
                            and event["payload"].get("dimension") == "critical_verification"
                            and body.event_id in event["payload"].get("opportunity_context", {}).get("inspectable_evidence_ids", [])]
            if not opportunities:
                raise HTTPException(409, "This event is not inspectable evidence in one of your verification opportunities.")
            opportunity_event = opportunities[-1]
            opportunity = opportunity_event["payload"]
        event_id = _stable_event_id(opportunity["opportunity_id"], f"inspection:{body.event_id}")
        payload = {
            "event_id": event_id, "learner_id": "demo-user", "session_id": body.session_id,
            "event_type": "collaboration_evidence_inspected", "phase": "collaboration",
            "collaboration_version": "collaboration-v1", "opportunity_id": opportunity["opportunity_id"],
            "source_event_id": opportunity["source_event_id"], "inspected_event_id": body.event_id,
            "evidence_ids": [opportunity["source_event_id"], opportunity["opportunity_id"], body.event_id],
            "sample_data": False, "recorded_at": utc_now(),
        }
        try:
            _, replayed = store.add_event(event_id, body.session_id, "collaboration_evidence_inspected", payload)
        except ValueError as exc:
            raise HTTPException(409, "This evidence inspection conflicts with a prior request.") from exc
        saved = _find_event(store, event_id, session_id=body.session_id)
        return {"inspection": public_event(saved), "source_event": public_event(cited), "replayed": replayed}

    @router.post("/api/collaboration/actions")
    def act(body: ActionRequest):
        _session(store, body.session_id)
        _, opportunity = _opportunity(store, body.session_id, body.opportunity_id)
        # Collaboration service uses its own stable namespace. Find an already
        # recorded action through the opportunity rather than guessing its UUID.
        existing_action = next((event for event in store.events(session_id=body.session_id)
                                if event["type"] == "collaboration_action_recorded"
                                and event["payload"].get("opportunity_id") == body.opportunity_id), None)
        if existing_action:
            data = _request_action_data(store, body, opportunity, regenerate_plan)
            try:
                result = record_action(store, body.session_id, body.opportunity_id, data)
            except (CollaborationEvidenceError, ValueError) as exc:
                _raise_evidence(exc)
            return {"action": public_event({"event_id": result["event"]["event_id"], "session_id": body.session_id,
                                            "type": "collaboration_action_recorded", "payload": result["event"],
                                            "created_at": existing_action["created_at"]}),
                    "replayed": True}

        data = _request_action_data(store, body, opportunity, regenerate_plan)
        try:
            result = record_action(store, body.session_id, body.opportunity_id, data)
        except CollaborationEvidenceError as exc:
            _raise_evidence(exc)
        except ValueError as exc:
            raise HTTPException(409, "This opportunity already has a different saved action.") from exc
        action = _find_event(store, result["event"]["event_id"], session_id=body.session_id)
        return {"action": public_event(action), "replayed": result["replayed"]}

    return router
