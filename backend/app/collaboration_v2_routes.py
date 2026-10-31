"""HTTP routes for the collaboration-v2 descriptive rubric."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .collaboration_v2 import (CollaborationV2Error, claim_context, claim_for, issue_claim,
                               record_action_v2, score_v2)


class V2Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["pass"] | None = None
    question: str | None = Field(default=None, max_length=2000)
    about_evidence_id: str | None = Field(default=None, max_length=120)
    understanding_applied_event_id: str | None = Field(default=None, max_length=120)
    verdict: Literal["supported", "contradicted", "insufficient_evidence"] | None = None
    inspected_event_id: str | None = Field(default=None, max_length=120)
    after_choice: Literal["accept_modified", "choose_alternative", "decline"] | None = None
    changed_choice_event_id: str | None = Field(default=None, max_length=120)
    decision: Literal["accept", "modify", "decline"] | None = None
    constraint_reference_id: str | None = Field(default=None, max_length=120)
    choice: Literal["keep_local", "decline_remote", "proceed_after_notice", "pause_for_uncertainty"] | None = None
    notice_event_id: str | None = Field(default=None, max_length=120)
    consequence_acknowledged: bool | None = None


class V2ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, max_length=120)
    opportunity_id: str = Field(min_length=1, max_length=120)
    evidence: V2Evidence


def _session_ok(store: Any, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if not session or session.get("learner_id") != "demo-user":
        raise HTTPException(404, "session not found")
    return session


def create_collaboration_v2_router(store: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/collaboration/v2/claim")
    def claim(opportunity_id: str, session_id: str):
        _session_ok(store, session_id)
        row = claim_for(store, opportunity_id)
        if not row:
            raise HTTPException(404, "no verifiable claim for this opportunity")
        if row.get("session_id") != session_id:
            raise HTTPException(404, "no verifiable claim for this session")
        opportunity_event = next((event for event in store.events(session_id=session_id)
                                  if event["type"] == "collaboration_opportunity_issued"
                                  and (event["payload"] or {}).get("opportunity_id") == opportunity_id), None)
        context = (claim_context(opportunity_event["payload"], row["evidence_event_id"], store)
                   if opportunity_event else None)
        # The expected verdict and its explanation stay server-side until the learner answers.
        # Only completed-task fields needed to adjudicate the claim are returned.
        return {"claim_id": row["claim_id"], "claim_text": row["claim_text"],
                "about_evidence_id": row["evidence_event_id"], "context": context,
                "note": "Judge whether this claim is supported, contradicted, or not determinable."}

    @router.post("/api/collaboration/v2/prepare")
    def prepare(body: dict):
        session_id = str(body.get("session_id") or "")
        _session_ok(store, session_id)
        source_event_id = str(body.get("source_event_id") or "")
        prepared = []
        for event in store.events(session_id=session_id):
            payload = event.get("payload", {}) or {}
            if (event["type"] == "collaboration_opportunity_issued"
                    and payload.get("source_event_id") == source_event_id
                    and payload.get("dimension") == "critical_verification"):
                row = issue_claim(store, payload)
                if row:
                    prepared.append(row)
        return {"prepared": prepared}

    @router.post("/api/collaboration/v2/actions")
    def record(body: V2ActionRequest):
        _session_ok(store, body.session_id)
        try:
            return record_action_v2(store, body.session_id, body.opportunity_id,
                                    body.evidence.model_dump(exclude_none=True))
        except CollaborationV2Error as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/api/collaboration/v2/score/{learner_id}")
    def score(learner_id: str, session_id: str | None = None):
        if learner_id != "demo-user":
            raise HTTPException(404, "learner not found")
        if session_id:
            _session_ok(store, session_id)
        return score_v2(store, learner_id, session_id)

    return router
