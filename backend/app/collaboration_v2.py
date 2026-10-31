"""collaboration-v2: separate participation from demonstrated reasoning quality.

``collaboration-v1`` records stay readable and unmodified. Version 2 keeps the
accepted 20/25/20/20/15 weights but replaces "structurally valid action earns 100"
with credit derived from what the backend can actually check:

* a verification verdict is compared with canonical ground truth held server-side and
  never sent to the browser before the learner answers;
* recorded revisions must differ from the original suggestion;
* an independent decision must cite a real recorded constraint;
* free-text length or punctuation never earns credit on its own;
* where quality cannot be checked, the dimension is reported **unassessed**.
"""
from __future__ import annotations

import json
import uuid
from contextlib import closing
from typing import Any

COLLABORATION_V2 = "collaboration-v2"
WEIGHTS = {"clarification": 20, "critical_verification": 25, "iteration": 20, "autonomy": 20, "responsible_use": 15}
RUBRIC_NOTE = ("Descriptive, unvalidated practice rubric. It describes recorded collaboration actions and does not "
               "measure validated AI literacy.")
VERDICTS = ("supported", "contradicted", "insufficient_evidence")


class CollaborationV2Error(ValueError):
    """The structured action cannot be evaluated honestly."""


def _events(store: Any, learner_id: str = "demo-user", session_id: str | None = None) -> list[dict[str, Any]]:
    return store.events(learner_id=learner_id, session_id=session_id) if session_id else store.events(learner_id=learner_id)


def _find(store: Any, event_id: str, learner_id: str = "demo-user",
          session_id: str | None = None) -> dict[str, Any]:
    for event in _events(store, learner_id, session_id):
        if event["event_id"] == event_id:
            return event
    raise CollaborationV2Error("referenced record is not saved for this learner")


def claim_for(store: Any, opportunity_id: str) -> dict[str, Any] | None:
    with closing(store.connect()) as db:
        row = db.execute("SELECT * FROM collaboration_claims WHERE opportunity_id=?", (opportunity_id,)).fetchone()
    return dict(row) if row else None


def _derive_claim(store: Any, opportunity: dict[str, Any]) -> dict[str, Any] | None:
    """Build a checkable claim about one cited record, keeping the truth server-side.

    The claim is chosen from the record's own canonical fields so the expected verdict
    genuinely varies: a recorded truth can support the claim, refute it, or leave it
    undeterminable. A constant verdict across records would let a guesser score.
    """
    inspectable = (opportunity.get("opportunity_context") or {}).get("inspectable_evidence_ids") or []
    for evidence_id in inspectable:
        try:
            event = _find(store, evidence_id, session_id=opportunity.get("session_id"))
        except CollaborationV2Error:
            continue
        payload = event.get("payload", {}) or {}
        interaction = payload.get("interaction", {}) or {}
        evaluation = payload.get("evaluation", {}) or {}
        assisted = bool(interaction.get("hint_count") or interaction.get("replay_count"))
        if interaction.get("visibility_interrupted"):
            return {"evidence_event_id": evidence_id,
                    "claim_text": "This saved attempt should count as full unassisted evidence.",
                    "expected_verdict": "contradicted",
                    "explanation": "The attempt is recorded as interrupted, so it is excluded from unassisted evidence."}
        if assisted:
            return {"evidence_event_id": evidence_id,
                    "claim_text": "This saved attempt was recorded with assistance.",
                    "expected_verdict": "supported",
                    "explanation": "The saved record carries a hint or replay count, so it is recorded as assisted."}
        if evaluation.get("correct") is True:
            return {"evidence_event_id": evidence_id,
                    "claim_text": "This saved attempt shows an incorrect response.",
                    "expected_verdict": "contradicted",
                    "explanation": "The server evaluation records this attempt as correct."}
        if evaluation.get("correct") is False:
            return {"evidence_event_id": evidence_id,
                    "claim_text": "This saved attempt shows an incorrect response.",
                    "expected_verdict": "supported",
                    "explanation": "The server evaluation records this attempt as incorrect."}
        return {"evidence_event_id": evidence_id,
                "claim_text": "This saved record alone proves whether the response was correct.",
                "expected_verdict": "insufficient_evidence",
                "explanation": "The saved record carries no server evaluation, so this record alone cannot settle correctness."}
    return None


def claim_context(opportunity: dict[str, Any], evidence_event_id: str, store: Any) -> dict[str, Any] | None:
    """Safe completed-task fields a learner needs to adjudicate one claim.

    Only already-recorded, completed attempts are exposed here; no answer key, no
    unseen or active scored item, and the expected verdict is never included.
    """
    try:
        event = _find(store, evidence_event_id, session_id=opportunity.get("session_id"))
    except CollaborationV2Error:
        return None
    payload = event.get("payload", {}) or {}
    interaction = payload.get("interaction", {}) or {}
    evaluation = payload.get("evaluation", {}) or {}
    return {
        "event_id": event["event_id"],
        "recorded_at": payload.get("recorded_at") or event["created_at"],
        "phase": payload.get("phase"),
        "exercise_id": payload.get("exercise_id"),
        "item_id": payload.get("item_id"),
        "scored": bool(payload.get("scored")),
        "correct": evaluation.get("correct"),
        "error_type": evaluation.get("error_type"),
        "assisted": bool(interaction.get("hint_count") or interaction.get("replay_count")),
        "interrupted": bool(interaction.get("visibility_interrupted")),
        "response_recorded": bool(payload.get("response") or payload.get("response_data")),
        "evaluation_recorded": bool(evaluation),
    }


def issue_claim(store: Any, opportunity: dict[str, Any]) -> dict[str, Any] | None:
    """Persist one claim truth for a critical-verification opportunity."""
    if opportunity.get("dimension") != "critical_verification":
        return None
    source_event_id = opportunity.get("source_event_id")
    existing = claim_for(store, opportunity["opportunity_id"])
    if existing:
        return {key: existing[key] for key in ("claim_id", "claim_text", "evidence_event_id")}
    claim = _derive_claim(store, opportunity)
    if not claim:
        return None
    claim_id = str(uuid.uuid5(uuid.UUID("6ea4bd45-1b1f-4b8f-9d3d-4f7d17f9a0d0"), f"claim:{opportunity['opportunity_id']}"))
    from .storage import utc_now
    with closing(store.connect()) as db:
        db.execute("INSERT OR REPLACE INTO collaboration_claims(claim_id,opportunity_id,source_event_id,session_id,"
                   "evidence_event_id,claim_text,expected_verdict,explanation,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (claim_id, opportunity["opportunity_id"], source_event_id, opportunity.get("session_id"),
                    claim["evidence_event_id"], claim["claim_text"], claim["expected_verdict"],
                    claim["explanation"], utc_now()))
        db.commit()
    return {"claim_id": claim_id, "claim_text": claim["claim_text"], "evidence_event_id": claim["evidence_event_id"]}


def _credit(points: int | None, reasons: list[str], checked: list[str]) -> dict[str, Any]:
    return {"status": "unassessed" if points is None else ("credited" if points >= 100 else "partial"),
            "credit_percent": points, "reasons": reasons, "checked_references": checked}


def evaluate_action(store: Any, session_id: str, opportunity: dict[str, Any],
                    evidence: dict[str, Any]) -> dict[str, Any]:
    """Score one structured action from checkable references only."""
    dimension = opportunity.get("dimension")
    context = opportunity.get("opportunity_context") or {}
    cited = list((opportunity.get("evidence_ids") or []))

    if dimension == "clarification":
        question = str(evidence.get("question") or "").strip()
        target_id = evidence.get("about_evidence_id")
        applied_id = evidence.get("understanding_applied_event_id")
        checked = [value for value in (target_id, applied_id) if value]
        reasons = []
        if not question or not target_id:
            return _credit(None, ["A question and the specific record it is about are required."], checked)
        if target_id not in cited:
            return _credit(None, ["The question must be about a record cited in this conversation."], checked)
        target = _find(store, target_id, session_id=session_id)
        if not applied_id:
            return _credit(50, ["Question recorded against a cited record; no later use of the answer is saved."], checked)
        applied = _find(store, applied_id, session_id=session_id)
        if applied["created_at"] <= target["created_at"]:
            return _credit(50, ["The linked follow-up predates the question, so it cannot show understanding."], checked)
        return _credit(100, ["Question linked to an unresolved record and followed by a later recorded use."], checked)

    if dimension == "critical_verification":
        verdict = evidence.get("verdict")
        inspected = evidence.get("inspected_event_id")
        if verdict not in VERDICTS:
            return _credit(None, ["A supported/contradicted/insufficient verdict is required."], [])
        if not inspected or inspected not in (context.get("inspectable_evidence_ids") or []):
            return _credit(None, ["Only records offered for inspection can be judged."], [str(inspected) if inspected else ""])
        truth = claim_for(store, opportunity["opportunity_id"])
        if not truth:
            return _credit(None, ["This opportunity has no verifiable claim, so the judgement stays unassessed."], [inspected])
        expected = truth["expected_verdict"]
        if verdict == expected:
            return _credit(100, [f"Verdict matched the canonical record: {truth['explanation']}"], [inspected])
        if verdict == "insufficient_evidence":
            return _credit(25, ["The record does determine the answer; the verdict was marked insufficient."], [inspected])
        return _credit(25, [f"Verdict did not match the canonical record: {truth['explanation']}"], [inspected])

    if dimension == "iteration":
        after = evidence.get("after_choice")
        before_id = context.get("suggestion_event_id")
        changed_id = evidence.get("changed_choice_event_id")
        if after not in {"accept_modified", "choose_alternative", "decline"}:
            return _credit(None, ["A recorded before/after choice is required."], [])
        if not changed_id:
            return _credit(50, ["A revised choice was stated but no canonical record changed."], [])
        changed = _find(store, changed_id, session_id=session_id)
        linked = changed["payload"].get("suggestion_event_id") or changed["payload"].get("source_event_id")
        if before_id and linked != before_id:
            return _credit(50, ["The changed record does not link back to the original suggestion."], [changed_id])
        return _credit(100, ["Recorded revision links to the original suggestion with a new choice."], [changed_id])

    if dimension == "autonomy":
        decision = evidence.get("decision")
        constraint_id = evidence.get("constraint_reference_id")
        if decision not in {"accept", "modify", "decline"}:
            return _credit(None, ["An explicit accept/modify/decline decision is required."], [])
        checked = [constraint_id] if constraint_id else []
        if not constraint_id:
            return _credit(50 if decision == "accept" else None,
                           ["A decision without a recorded constraint is participation, not demonstrated judgement."],
                           checked)
        constraint = _find(store, constraint_id, session_id=session_id)
        payload = constraint.get("payload", {}) or {}
        if payload.get("sample_data") is True:
            return _credit(None, ["The cited constraint is marked as sample data."], checked)
        if decision == "accept":
            return _credit(75, ["Following the recommendation is supported by a recorded constraint; "
                               "following advice is not inherently better than rejecting it."], checked)
        return _credit(100, ["Independent decision tied to a recorded constraint."], checked)

    if dimension == "responsible_use":
        choice = evidence.get("choice")
        acknowledged = evidence.get("consequence_acknowledged")
        notice_id = evidence.get("notice_event_id")
        allowed = {"keep_local", "decline_remote", "proceed_after_notice", "pause_for_uncertainty"}
        if choice not in allowed:
            return _credit(None, ["A disclosed privacy/uncertainty choice is required."], [])
        expected_notice = context.get("consent_event_id")
        checked = [notice_id] if notice_id else []
        if expected_notice and notice_id != expected_notice:
            return _credit(None, ["The choice must link the saved consent/notice for this conversation."], checked)
        if acknowledged is not True:
            return _credit(50, ["Choice recorded without an acknowledged consequence."], checked)
        return _credit(100, ["Choice linked to the saved notice with its consequence acknowledged."], checked)

    return _credit(None, ["Unknown collaboration dimension."], [])


def record_action_v2(store: Any, session_id: str, opportunity_id: str,
                     evidence: dict[str, Any]) -> dict[str, Any]:
    from .storage import utc_now
    opportunity_event = _find(store, opportunity_id)
    if opportunity_event["type"] != "collaboration_opportunity_issued":
        raise CollaborationV2Error("opportunity was not issued by the backend")
    opportunity = opportunity_event["payload"]
    if opportunity.get("session_id") != session_id:
        raise CollaborationV2Error("opportunity belongs to another session")
    if evidence.get("action") == "pass":
        result = _credit(0, ["Opportunity passed; no reasoning evidence recorded."], [])
    else:
        result = evaluate_action(store, session_id, opportunity, evidence)
    event_id = str(uuid.uuid5(uuid.UUID("3a54cbd1-8f1d-4b18-8c0e-8ea0c9d5c6bb"),
                             f"v2:{opportunity_id}:{json.dumps(evidence, sort_keys=True, default=str)[:160]}"))
    payload = {"event_id": event_id, "learner_id": "demo-user", "session_id": session_id,
               "event_type": "collaboration_action_recorded", "phase": "collaboration",
               "collaboration_version": COLLABORATION_V2, "opportunity_id": opportunity_id,
               "dimension": opportunity.get("dimension"), "structured_evidence": evidence,
               "evaluation": result, "rubric_note": RUBRIC_NOTE, "sample_data": False,
               "recorded_at": utc_now()}
    saved, replayed = store.add_event(event_id, session_id, "collaboration_action_recorded", payload)
    return {"action": saved, "replayed": replayed, "evaluation": result, "rubric_note": RUBRIC_NOTE}


def score_v2(store: Any, learner_id: str = "demo-user", session_id: str | None = None) -> dict[str, Any]:
    """Weighted descriptive score over assessed v2 dimensions only."""
    dims: dict[str, dict[str, Any]] = {}
    for dimension in WEIGHTS:
        rows = []
        for event in _events(store, learner_id, session_id):
            payload = event.get("payload", {}) or {}
            if (event["type"] == "collaboration_action_recorded"
                    and payload.get("collaboration_version") == COLLABORATION_V2
                    and payload.get("dimension") == dimension):
                rows.append(payload.get("evaluation") or {})
        credited = [row for row in rows if row.get("credit_percent") is not None]
        dims[dimension] = {
            "weight_percent": WEIGHTS[dimension],
            "evaluated_opportunity_count": len(rows),
            "assessed_count": len(credited),
            "score_0_100": round(sum(row["credit_percent"] for row in credited) / len(credited), 2) if credited else None,
            "status": "assessed" if credited else ("attempted_unassessable" if rows else "not_attempted"),
        }
    ready = all(dims[dimension]["score_0_100"] is not None for dimension in WEIGHTS)
    overall = round(sum(dims[d]["score_0_100"] * WEIGHTS[d] / 100 for d in WEIGHTS), 2) if ready else None
    return {"collaboration_version": COLLABORATION_V2, "weights_percent": dict(WEIGHTS),
            "dimensions": dims, "score_0_100": overall, "evaluated_opportunity_coverage":
            round(100 * sum(1 for d in WEIGHTS if dims[d]["score_0_100"] is not None) / len(WEIGHTS), 2),
            "rubric_note": RUBRIC_NOTE,
            "interpretation": ("This rubric records what the learner did with saved evidence. It is descriptive, "
                               "unvalidated practice feedback, not a measured AI-literacy ability.")}
