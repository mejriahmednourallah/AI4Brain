"""Isolated R4 probes: balanced verification claims, adjudicating context, coach actions.

No primary learner database, provider or graph is used. Every record is created in a
temporary SQLite file that is removed at the end.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
fixture = ROOT / "output" / "verification" / f".r4-{uuid.uuid4().hex}.sqlite3"
os.environ["AI4BRAIN_DB"] = str(fixture)
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient

from backend.app.collaboration_v2 import _derive_claim
from backend.app.main import app, store
from backend.app.storage import utc_now


def record_claim_for(payload: dict, evidence_event_id: str) -> dict:
    return _derive_claim(store, {
        "session_id": payload["session_id"],
        "opportunity_context": {"inspectable_evidence_ids": [evidence_event_id]},
    }) or {}


try:
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]

        def add_attempt(interaction: dict, evaluation: dict, item: str) -> str:
            event_id = str(uuid.uuid4())
            store.add_event(event_id, sid, "assessment_trial_completed", {
                "event_id": event_id, "session_id": sid, "learner_id": "demo-user",
                "event_type": "assessment_trial_completed", "phase": "baseline",
                "exercise_id": "EX-02", "item_id": item, "scored": True,
                "response": {"choice": "A"}, "evaluation": evaluation,
                "interaction": interaction, "sample_data": False, "recorded_at": utc_now(),
            })
            return event_id

        cases = {
            "interrupted": (add_attempt({"visibility_interrupted": True}, {"correct": True}, "r4-i"), "contradicted"),
            "assisted": (add_attempt({"hint_count": 1}, {"correct": True}, "r4-a"), "supported"),
            "correct": (add_attempt({}, {"correct": True}, "r4-c"), "contradicted"),
            "incorrect": (add_attempt({}, {"correct": False, "error_type": "incorrect_pattern"}, "r4-w"), "supported"),
            "unevaluated": (add_attempt({}, {}, "r4-u"), "insufficient_evidence"),
        }
        verdicts = {}
        for name, (event_id, expected) in cases.items():
            claim = record_claim_for({"session_id": sid}, event_id)
            assert claim, f"no claim derived for {name}"
            assert claim["expected_verdict"] == expected, (name, claim)
            assert claim["claim_text"] and claim["explanation"], claim
            verdicts[name] = claim["expected_verdict"]
        # Balance: the set is not a constant answer.
        assert set(verdicts.values()) == {"supported", "contradicted", "insufficient_evidence"}, verdicts

        # The learner-facing view exposes adjudicating fields but never the expected verdict.
        opportunity_id = str(uuid.uuid4())
        assisted_event = cases["assisted"][0]
        store.add_event(opportunity_id, sid, "collaboration_opportunity_issued", {
            "event_id": opportunity_id, "session_id": sid, "learner_id": "demo-user",
            "event_type": "collaboration_opportunity_issued", "phase": "collaboration",
            "opportunity_id": opportunity_id, "dimension": "critical_verification",
            "source_event_id": assisted_event, "evidence_ids": [assisted_event],
            "opportunity_context": {"inspectable_evidence_ids": [assisted_event]},
            "prompt": "Verify the cited attempt.", "sample_data": False, "recorded_at": utc_now(),
        })
        prepared = client.post("/api/collaboration/v2/prepare",
                               json={"session_id": sid, "source_event_id": assisted_event})
        assert prepared.status_code == 200, prepared.text
        claim_view = client.get("/api/collaboration/v2/claim",
                                params={"opportunity_id": opportunity_id, "session_id": sid})
        assert claim_view.status_code == 200, claim_view.text
        view = claim_view.json()
        assert "expected_verdict" not in view and "explanation" not in view, view
        context = view["context"]
        assert context["assisted"] is True and context["correct"] is True, context
        assert context["exercise_id"] == "EX-02" and context["scored"] is True, context
        assert context["item_id"] == "r4-a", context

        # A correct verdict on the assisted claim earns full credit; a wrong one partial.
        matched = client.post("/api/collaboration/v2/actions", json={
            "session_id": sid, "opportunity_id": opportunity_id,
            "evidence": {"verdict": "supported", "inspected_event_id": assisted_event}})
        assert matched.status_code == 200, matched.text
        assert matched.json()["evaluation"]["credit_percent"] == 100, matched.json()["evaluation"]

        # R3: a coach action can only be recorded when the saved turn offered it.
        coach = client.post("/api/coach", json={"session_id": sid, "message": "What should I do next?"})
        assert coach.status_code == 200, coach.text
        answer = coach.json()
        offered = answer["response"]["actions"]
        assert offered, answer["response"]
        chosen = next(action for action in offered if action["id"] == "change_focus")
        recorded = client.post("/api/coach/actions", json={
            "session_id": sid, "request_id": answer["request_id"], "action_id": "change_focus",
            "target": chosen["target"], "exercise_id": chosen.get("exercise_id"),
        })
        assert recorded.status_code == 200, recorded.text
        assert recorded.json()["replayed"] is False, recorded.json()
        again = client.post("/api/coach/actions", json={
            "session_id": sid, "request_id": answer["request_id"], "action_id": "change_focus",
            "target": chosen["target"], "exercise_id": chosen.get("exercise_id"),
        })
        assert again.status_code == 200 and again.json()["replayed"] is True, again.json()
        tampered = client.post("/api/coach/actions", json={
            "session_id": sid, "request_id": answer["request_id"], "action_id": "change_focus",
            "target": "/elsewhere"})
        assert tampered.status_code == 409, tampered.text
        not_offered = client.post("/api/coach/actions", json={
            "session_id": sid, "request_id": answer["request_id"], "action_id": "open_practice",
            "target": "/practice?family=reasoning"})
        assert not_offered.status_code in {200, 409}, not_offered.text

        with closing(store.connect()) as db:
            actions = db.execute(
                "SELECT COUNT(*) FROM events WHERE type='coach_action_selected' AND session_id=?",
                (sid,)).fetchone()[0]
        assert actions == 1, actions

        receipt = {
            "status": "PASS",
            "batch": "R3/R4",
            "requirements": ["RJ-05 action recording", "RJ-08 balanced claims", "RJ-08 adjudicating context"],
            "claim_verdicts": verdicts,
            "coach_action_events": actions,
            "browser": "not exercised",
            "live_tts": "not exercised",
        }
        (ROOT / "output" / "verification" / "r4-collaboration-claims.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
finally:
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{fixture}{suffix}")
        if path.exists():
            path.unlink()
