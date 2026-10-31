"""Coach routes: coach-v2 conversation, provider status and replay-safe turns.

Stored ``coach-v1`` events remain readable. New turns use ``coach-v2`` and persist a
``request_id`` plus a canonical payload hash so an exact retry reconciles the same
turn instead of generating a second answer.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import threading
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .coach_v2 import COACH_VERSION, provider_statuses, reply_v2
from .storage import CoachRequestInvalidated, utc_now
from .twin_context import FAMILIES, build_twin_context, resolve_subject

_REMOTE_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="coach-explanation")
_REMOTE_SLOTS = threading.BoundedSemaphore(2)
REMOTE_DEADLINE_SECONDS = 8.0


class CoachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str
    message: str = Field(min_length=3, max_length=2000)
    allow_remote: bool = False
    phase: Literal["overview", "training", "baseline", "reassessment", "practice"] = "overview"
    training_block_id: str | None = None
    item_id: str | None = None
    request_id: str | None = None
    provider: Literal["local", "groq", "gemini"] = "local"
    focus_exercise_id: str | None = None
    subject_exercise_id: str | None = None
    provider_consent_recorded: bool = False


class CoachActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str
    request_id: str = Field(min_length=1, max_length=120)
    action_id: Literal["inspect_evidence", "try_strategy", "open_practice", "change_focus"]
    target: str | None = Field(default=None, max_length=240)
    strategy_id: str | None = Field(default=None, max_length=120)
    exercise_id: str | None = Field(default=None, max_length=40)


def _payload_hash(body: CoachRequest) -> str:
    material = {
        "session_id": body.session_id, "message": body.message, "phase": body.phase,
        "provider": body.provider, "allow_remote": body.allow_remote,
        "focus_exercise_id": body.focus_exercise_id, "subject_exercise_id": body.subject_exercise_id,
        "training_block_id": body.training_block_id, "item_id": body.item_id,
        "provider_consent_recorded": body.provider_consent_recorded,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_block(store: Any, body: CoachRequest) -> dict[str, Any] | None:
    if not body.training_block_id:
        if body.phase == "training":
            raise HTTPException(422, "Training coaching needs a block and current item")
        return None
    block = store.get_training_block(body.training_block_id)
    if not block or block["session_id"] != body.session_id or block["status"] != "active":
        raise HTTPException(409, "An active training block belonging to this session is required")
    if not body.item_id:
        raise HTTPException(422, "The current training item is required to record assistance")
    from .battery_exercises import training_items
    from .exercises import TRAINING_EXERCISE_VERSION, make_training_bank
    block_version = block.get("exercise_version") or TRAINING_EXERCISE_VERSION
    if block["exercise_id"] == "EX-02":
        items = make_training_bank(block["tier"], block["block_id"], block_version)
    else:
        items = training_items(block["exercise_id"], block["tier"], block_id=block["block_id"], version=block_version)
    if body.item_id not in {item["item_id"] for item in items}:
        raise HTTPException(422, "Item does not belong to this training block")
    return block


def _training_context(store: Any, body: CoachRequest, block: dict[str, Any] | None) -> dict[str, Any]:
    context = {"clarification_follow_up": "What would you like me to clarify about this evidence or strategy?",
               "verification_evidence_ids": [], "responsible_use_notice_shown": True}
    # Only this session's immutable consent event is needed here. Restricting the
    # read keeps the lifecycle-locked finalization path from decoding the learner's
    # full cross-session history for a session-scoped lookup.
    events = store.events(session_id=body.session_id)
    consent = next((event for event in events
                    if event["type"] == "consent_recorded" and event["session_id"] == body.session_id), None)
    if consent:
        context["consent_event_id"] = consent["event_id"]
    if block:
        context["training_block_id"] = block["block_id"]
    return context


def _resolve_provider(body: CoachRequest, conversation: dict[str, Any]) -> tuple[str, bool]:
    """Choose one provider for this turn and report whether consent is still missing.

    Local-only requests never reach this. A remote request without an explicit provider
    uses the configured conversation provider, else the first configured adapter.
    """
    if not body.allow_remote:
        return "local", False
    from .provider_adapters import ADAPTERS
    if body.provider != "local":
        chosen = body.provider
    elif conversation.get("provider") in ADAPTERS and ADAPTERS[conversation["provider"]].configured():
        chosen = conversation["provider"]
    else:
        chosen = next((name for name, adapter in ADAPTERS.items() if adapter.configured()), "groq")
    adapter = ADAPTERS.get(chosen)
    if adapter is None or not adapter.configured():
        # Not configured: reply_v2 reports `not_configured` and nothing is sent.
        return chosen, False
    return chosen, not body.provider_consent_recorded


def _validated_history(store: Any, session_id: str, current_request_id: str | None) -> list[dict[str, Any]]:
    """Return bounded, ordered learner/validated-assistant history for this session."""
    rows = [
        turn for turn in store.coach_turns(session_id, limit=50)
        if turn["request_id"] != current_request_id
        and turn.get("status") == "completed"
        and isinstance(turn.get("response"), dict)
    ]
    rows.sort(key=lambda turn: (turn.get("created_at") or "", turn["request_id"]))
    history: list[dict[str, Any]] = []
    for turn in rows[-3:]:
        response = turn["response"]
        response_body = response.get("response") or {}
        history.append({
            "role": "learner", "text": turn["message"], "request_id": turn["request_id"],
            "evidence_revision": turn.get("evidence_revision"),
            "provenance": "learner_request", "status": "completed",
        })
        history.append({
            "role": "assistant", "text": response_body.get("explanation", ""),
            "request_id": turn["request_id"], "evidence_revision": turn.get("evidence_revision"),
            "evidence_ids": list(response_body.get("evidence_ids") or []),
            "subject": response.get("subject"), "provider_status": response.get("provider_status"),
            "provenance": "validated_assistant_turn", "status": "completed",
        })
    return history[-6:]


def _build_answer(store: Any, body: CoachRequest) -> dict[str, Any]:
    block = _validate_block(store, body)
    conversation = store.coach_conversation(body.session_id) or {}
    turns = _validated_history(store, body.session_id, body.request_id)
    canonical_events = store.events(learner_id="demo-user")
    session_events = [event for event in canonical_events if event.get("session_id") == body.session_id]
    context = build_twin_context(store, "demo-user", focus_exercise_id=body.focus_exercise_id,
                                 conversation_subject=conversation.get("subject_exercise_id"),
                                 conversation_turns=turns,
                                 learner_reports=[{"text": body.message[:500], "kind": "learner_report",
                                                   "session_id": body.session_id}],
                                 canonical_events=canonical_events)
    context["assisted_training"] = bool(block)
    consent_event = (next((event for event in session_events
                           if event["type"] == "consent_recorded"
                           and (event["payload"].get("consent") or {}).get("accepted") is True), None)
                     if body.allow_remote else None)
    subject = resolve_subject(body.message, focus_exercise_id=body.focus_exercise_id,
                              conversation_subject=conversation.get("subject_exercise_id"),
                              next_exercise_id=context["next_step"].get("exercise_id"),
                              has_conversation=bool(turns))
    if body.subject_exercise_id in FAMILIES:
        subject = {"exercise_id": body.subject_exercise_id,
                   "dimension": FAMILIES[body.subject_exercise_id]["dimension"],
                   "source": "explicit_selection", "candidates": []}
    provider, consent_required = _resolve_provider(body, conversation)
    if body.allow_remote and consent_event is None:
        consent_required = True
    answer = reply_v2(context, subject, body.message, allow_remote=False, provider=provider)
    if consent_required:
        # Nothing leaves the machine without an explicit provider-specific consent.
        answer.update(source="local_fallback", provider_status="consent_required",
                      provider_used="local", model=None, fallback_reason="provider_consent_missing")
    elif body.allow_remote and provider != "local":
        from .provider_adapters import ADAPTERS
        adapter = ADAPTERS.get(provider)
        answer.update(source="server_grounded_local", provider_status=(
            "explanation_pending" if adapter and adapter.configured() else "not_configured"),
            provider_used="local", model=None,
            fallback_reason=None if adapter and adapter.configured() else "credentials_missing")
    answer["assisted_training"] = bool(block)
    answer["relevant_evidence_ids"] = list(dict.fromkeys(
        [*answer["response"]["evidence_ids"], *context["next_step"].get("evidence_ids", [])]))
    answer["context_limitations"] = context["limitations"]
    # A saved recommendation from this session can be cited, so the collaboration
    # opportunities for iteration/autonomy point at a real saved policy event.
    saved_recommendation = next((event for event in reversed(session_events)
                                 if event["type"] == "exercise_recommended"
                                 and (event["payload"] or {}).get("alternatives")), None)
    if saved_recommendation:
        answer["response"]["evidence_ids"] = list(dict.fromkeys(
            [*answer["response"]["evidence_ids"], saved_recommendation["event_id"]]))
        answer["relevant_evidence_ids"] = list(dict.fromkeys(
            [*answer["relevant_evidence_ids"], saved_recommendation["event_id"]]))
        answer["_suggestion_event_id"] = saved_recommendation["event_id"]
    return {"answer": answer, "context": context, "subject": subject, "block": block,
            "provider": provider, "consent_required": consent_required}


def _local_progress(body: CoachRequest, built: dict[str, Any]) -> dict[str, Any]:
    answer = built["answer"]
    pending = answer["provider_status"] == "explanation_pending"
    return {
        "request_id": body.request_id,
        "status": "explanation_pending" if pending else "local_only",
        "label": "Local answer; explanation pending." if pending else "Local answer.",
        "source": "server_grounded_local",
        "provider_status": answer["provider_status"],
        "provider_requested": answer["provider_requested"],
        "provider_used": "local",
        "model": None,
        "evidence_revision": answer["evidence_revision"],
        "spoken_summary": answer.get("spoken_summary"),
        "subject": answer["subject"],
        "response": answer["response"],
        "assisted_training": answer["assisted_training"],
        "relevant_evidence_ids": answer["relevant_evidence_ids"],
        "context_limitations": answer["context_limitations"],
        "provider_requested_opt_in": bool(body.allow_remote),
    }


def _apply_optional_explanation(store: Any, body: CoachRequest, built: dict[str, Any]) -> None:
    """Replace only the explanatory prose with a strictly validated provider result."""
    answer = built["answer"]
    if answer["provider_status"] != "explanation_pending":
        return
    if not _REMOTE_SLOTS.acquire(blocking=False):
        answer.update(provider_status="busy", fallback_reason="provider_capacity_exhausted",
                      source="local_fallback")
        return
    from .provider_adapters import ADAPTERS
    try:
        future = _REMOTE_EXECUTOR.submit(
            reply_v2, built["context"], built["subject"], body.message,
            allow_remote=True, provider=built["provider"],
        )
    except Exception:
        _REMOTE_SLOTS.release()
        answer.update(provider_status="unavailable_or_invalid", fallback_reason="provider_unavailable",
                      source="local_fallback")
        return
    future.add_done_callback(lambda _future: _REMOTE_SLOTS.release())
    try:
        remote = future.result(timeout=REMOTE_DEADLINE_SECONDS)
    except FutureTimeout:
        future.cancel()
        answer.update(provider_status="timeout", fallback_reason="provider_timeout", source="local_fallback")
        return
    adapter = ADAPTERS.get(built["provider"])
    if remote.get("provider_status") == "validated":
        from .twin_context import _revision
        current_revision = _revision(store.events(learner_id="demo-user"))
        if current_revision != answer["evidence_revision"]:
            answer.update(source="local_fallback", provider_status="stale_context", provider_used="local",
                          model=None, fallback_reason="evidence_revision_changed")
            return
        answer.update(source=remote["source"], provider_status=remote["provider_status"],
                      provider_used=remote["provider_used"], model=remote["model"], fallback_reason=None)
        answer["response"] = remote["response"]
    else:
        answer.update(source="local_fallback", provider_status=remote["provider_status"],
                      provider_used="local", model=None,
                      fallback_reason=remote.get("fallback_reason") or "provider_unavailable")
        if remote.get("review_note"):
            answer["review_note"] = remote["review_note"]
    answer["provider_requested"] = built["provider"] or (adapter.name if adapter else "local")


def _record(store: Any, body: CoachRequest, built: dict[str, Any],
            lifecycle_generation: int) -> dict[str, Any]:
    answer = built["answer"]
    subject = built["subject"]
    block = built["block"]
    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai4brain:coach:{body.request_id}"))
    collaboration_context = _training_context(store, body, block)
    collaboration_context["clarification_follow_up"] = answer["response"]["follow_up"]
    collaboration_context["verification_evidence_ids"] = list(answer["response"]["evidence_ids"])
    if answer.get("_suggestion_event_id"):
        collaboration_context["suggestion_event_id"] = answer["_suggestion_event_id"]
        collaboration_context["autonomy_recommendation_event_id"] = answer["_suggestion_event_id"]
    payload = {"event_id": event_id, "session_id": body.session_id, "learner_id": "demo-user",
               "event_type": "coaching_message_sent", "phase": "coach", "message": body.message,
               "coach_response": answer["response"], "coach_version": COACH_VERSION,
               "provider_status": answer["provider_status"], "source": answer["source"],
               "provider_requested": answer["provider_requested"], "provider_used": answer["provider_used"],
               "model": answer["model"], "fallback_reason": answer["fallback_reason"],
               "remote_opt_in": bool(body.allow_remote), "training_block_id": body.training_block_id,
               "item_id": body.item_id, "hint_requested": bool(block),
               "subject": answer["subject"], "subject_source": subject.get("source"),
               "evidence_revision": answer["evidence_revision"], "request_id": body.request_id,
               "collaboration_context": collaboration_context, "sample_data": False, "recorded_at": utc_now()}
    store.record_coach_event(
        request_id=body.request_id, learner_id="demo-user", session_id=body.session_id,
        lifecycle_generation=lifecycle_generation, event_id=event_id, payload=payload,
        provider=answer["provider_requested"], consent_recorded=body.provider_consent_recorded,
        subject_exercise_id=subject.get("exercise_id") or built["context"]["next_step"].get("exercise_id"),
    )
    opportunities = []
    try:
        from .collaboration_service import issue_opportunities
        opportunities = issue_opportunities(store, event_id, session_id=body.session_id)
    except (ImportError, ValueError):
        pass
    answer["event_id"] = event_id
    answer["opportunities"] = opportunities
    return answer


def _reserve(store: Any, body: CoachRequest) -> tuple[CoachRequest, str, dict[str, Any]]:
    """Reserve a request before context construction or provider generation."""
    session = store.get_session(body.session_id)
    if not session or session["learner_id"] != "demo-user":
        raise HTTPException(404, "session not found")
    if body.phase in {"baseline", "reassessment"}:
        raise HTTPException(409, "The coach is quiet during scored assessments. Review evidence afterwards.")
    request_id = body.request_id or str(uuid.uuid4())
    if body.request_id != request_id:
        body = body.model_copy(update={"request_id": request_id})
    request_hash = _payload_hash(body)
    try:
        turn, owner = store.reserve_coach_turn({
            "request_id": request_id, "learner_id": "demo-user", "session_id": body.session_id,
            "coach_version": COACH_VERSION, "payload_hash": request_hash, "message": body.message,
            "request": body.model_dump(),
        })
    except (ValueError, CoachRequestInvalidated) as exc:
        raise HTTPException(409, str(exc)) from exc
    if not owner:
        if turn["status"] == "completed" and turn.get("response") is not None:
            return body, "replay", turn
        if turn.get("progress") is not None:
            return body, "progress", turn
        raise HTTPException(409, "This request is already in progress; retry it after completion.")
    return body, "owner", turn


def _finish_reserved(store: Any, body: CoachRequest, built: dict[str, Any],
                     turn: dict[str, Any]) -> dict[str, Any]:
    assert body.request_id
    with store.coach_lifecycle_lock:
        answer = _record(store, body, built, int(turn["lifecycle_generation"]))
        answer["request_id"] = body.request_id
        store.complete_coach_turn(body.request_id, response=answer, status="completed",
                                  provider_used=answer["provider_used"], model=answer["model"],
                                  error_code=answer["fallback_reason"],
                                  lifecycle_generation=int(turn["lifecycle_generation"]))
        return answer


def _run_reserved(store: Any, body: CoachRequest, turn: dict[str, Any]) -> dict[str, Any]:
    """Run the one shared generation, event, and completion lifecycle."""
    assert body.request_id
    try:
        built = _build_answer(store, body)
        progress = _local_progress(body, built)
        store.save_coach_progress(body.request_id, progress,
                                  lifecycle_generation=int(turn["lifecycle_generation"]))
        _apply_optional_explanation(store, body, built)
        built["answer"]["local_response"] = progress
        return _finish_reserved(store, body, built, turn)
    except CoachRequestInvalidated as exc:
        reason = str(exc).casefold()
        if "delet" in reason:
            detail = "The learner data was deleted while this coaching request was running; no reply was saved."
        else:
            detail = ("This request reservation changed before it finished, so nothing was saved. "
                      "Retry the same request id.")
        raise HTTPException(409, detail) from exc
    except HTTPException as exc:
        store.fail_coach_turn(body.request_id, f"http_{exc.status_code}")
        raise
    except Exception as exc:
        store.fail_coach_turn(body.request_id, type(exc).__name__)
        raise HTTPException(500, "The coaching request failed before completion; retry the same request_id.") from exc


def create_coach_router(store: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/recommendations/current")
    def current_recommendation():
        records = [event for event in store.events(learner_id="demo-user") if event["type"] == "exercise_recommended"]
        current = {**records[-1]["payload"], "event_id": records[-1]["event_id"]} if records else None
        return {"recommendation": current, "preferences": store.current_preferences("demo-user")}

    @router.get("/api/coach/providers")
    def providers():
        return {"providers": provider_statuses(), "default": "local",
                "note": "Hosted providers are optional. Local coaching stays available and never sends learner text."}

    @router.get("/api/coach/conversation")
    def conversation(session_id: str):
        session = store.get_session(session_id)
        if not session or session["learner_id"] != "demo-user":
            raise HTTPException(404, "session not found")
        record = store.coach_conversation(session_id) or {}
        turns = [{"request_id": turn["request_id"], "message": turn["message"], "status": turn["status"],
                  "provider_used": turn["provider_used"], "subject": turn["subject_exercise_id"],
                  "evidence_revision": turn["evidence_revision"], "created_at": turn["created_at"],
                  "response": turn["response"]}
                 for turn in store.coach_turns(session_id)
                 if turn["status"] == "completed" and turn.get("response") is not None]
        return {"session_id": session_id, "subject_exercise_id": record.get("subject_exercise_id"),
                "provider": record.get("provider", "local"),
                "consent_recorded": bool(record.get("consent_recorded")), "turns": turns}

    @router.post("/api/coach")
    def coach(body: CoachRequest):
        body, state, turn = _reserve(store, body)
        if state == "replay":
            return {**turn["response"], "replayed": True}
        if state == "progress":
            return {**turn["progress"], "replayed": True}
        return _run_reserved(store, body, turn)

    @router.post("/api/coach/actions")
    def coach_action(body: CoachActionRequest):
        session = store.get_session(body.session_id)
        if not session or session["learner_id"] != "demo-user":
            raise HTTPException(404, "session not found")
        source = next((event for event in store.events(session_id=body.session_id)
                       if event["type"] == "coaching_message_sent"
                       and event["payload"].get("request_id") == body.request_id), None)
        if not source:
            raise HTTPException(404, "completed coaching turn not found")
        response = source["payload"].get("coach_response") or {}
        action = next((item for item in response.get("actions", [])
                       if item.get("id") == body.action_id), None)
        if not action:
            raise HTTPException(409, "That action was not offered by the saved coaching turn.")
        expected = {
            "target": action.get("target"),
            "strategy_id": action.get("strategy_id"),
            "exercise_id": action.get("exercise_id"),
        }
        supplied = {
            "target": body.target,
            "strategy_id": body.strategy_id,
            "exercise_id": body.exercise_id,
        }
        if supplied != expected:
            raise HTTPException(409, "The selected action does not match the saved coaching action.")
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai4brain:coach-action:{body.request_id}:{body.action_id}"))
        payload = {
            "event_id": event_id,
            "learner_id": "demo-user",
            "session_id": body.session_id,
            "event_type": "coach_action_selected",
            "phase": "coach",
            "request_id": body.request_id,
            "action_id": body.action_id,
            "target": body.target,
            "strategy_id": body.strategy_id,
            "exercise_id": body.exercise_id,
            "source_event_id": source["event_id"],
            "sample_data": False,
            "recorded_at": utc_now(),
        }
        existing = next((event for event in store.events(session_id=body.session_id)
                         if event["event_id"] == event_id), None)
        if existing:
            return {"action": existing, "replayed": True}
        try:
            saved, replayed = store.add_event(event_id, body.session_id, "coach_action_selected", payload)
        except ValueError as exc:
            raise HTTPException(409, "That coaching action conflicts with an existing saved event.") from exc
        return {"action": saved, "replayed": replayed}

    @router.post("/api/coach/stream")
    def coach_stream(body: CoachRequest):
        """Server-sent events: acknowledgement and evidence first, then the validated answer.

        Only backend-rendered structure is streamed before validation, so no unvalidated
        generated token reaches the client.
        """
        body, state, turn = _reserve(store, body)

        def events():
            yield "event: acknowledged\ndata: " + json.dumps(
                {"request_id": body.request_id, "started_at": utc_now()}) + "\n\n"
            if state == "replay":
                answer = turn["response"]
                yield "event: evidence\ndata: " + json.dumps({
                    "subject": answer["subject"], "evidence_ids": answer["relevant_evidence_ids"],
                    "evidence_revision": answer["evidence_revision"],
                }, separators=(",", ":")) + "\n\n"
                yield "event: answer\ndata: " + json.dumps(answer, separators=(",", ":")) + "\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            if state == "progress":
                progress = turn["progress"]
                yield "event: local_response\ndata: " + json.dumps(progress, separators=(",", ":")) + "\n\n"
                yield "event: answer\ndata: " + json.dumps({**progress, "replayed": True}, separators=(",", ":")) + "\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            try:
                built = _build_answer(store, body)
            except HTTPException as exc:
                store.fail_coach_turn(body.request_id, f"http_{exc.status_code}")
                raise
            except Exception as exc:
                store.fail_coach_turn(body.request_id, type(exc).__name__)
                raise
            yield "event: evidence\ndata: " + json.dumps({
                "subject": built["answer"]["subject"],
                "evidence_ids": built["answer"]["relevant_evidence_ids"],
                "evidence_revision": built["context"]["evidence_revision"],
                "limitations": built["context"]["limitations"],
            }, separators=(",", ":")) + "\n\n"
            progress = _local_progress(body, built)
            try:
                store.save_coach_progress(body.request_id, progress,
                                          lifecycle_generation=int(turn["lifecycle_generation"]))
            except CoachRequestInvalidated:
                yield "event: error\ndata: " + json.dumps({
                    "status": 409, "code": "learner_data_deleted",
                    "message": "The learner data was deleted while this coaching request was running; no reply was saved.",
                }, separators=(",", ":")) + "\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            yield "event: local_response\ndata: " + json.dumps(progress, separators=(",", ":")) + "\n\n"
            _apply_optional_explanation(store, body, built)
            built["answer"]["local_response"] = progress
            try:
                answer = _finish_reserved(store, body, built, turn)
            except CoachRequestInvalidated as exc:
                yield "event: error\ndata: " + json.dumps({
                    "status": 409, "code": "learner_data_deleted",
                    "message": "The learner data was deleted while this coaching request was running; no reply was saved.",
                }, separators=(",", ":")) + "\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            except HTTPException as exc:
                store.fail_coach_turn(body.request_id, f"http_{exc.status_code}")
                raise
            except Exception as exc:
                store.fail_coach_turn(body.request_id, type(exc).__name__)
                raise
            yield "event: answer\ndata: " + json.dumps(answer, separators=(",", ":")) + "\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
