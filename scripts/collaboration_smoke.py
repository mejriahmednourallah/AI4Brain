"""Temporary-SQLite smoke for genuine collaboration evidence and weighted score."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["NEO4J_ENABLED"] = "false"

from backend.app.collaboration_service import (  # noqa: E402
    CollaborationEvidenceError, WEIGHTS, collaboration_score, issue_opportunities, record_action,
)
from backend.app.storage import Store  # noqa: E402


def add(store: Store, session_id: str, event_type: str, **fields):
    event_id = fields.pop("event_id", str(uuid.uuid4()))
    payload = {
        "event_id": event_id, "session_id": session_id, "learner_id": "demo-user",
        "event_type": event_type, "sample_data": False, "recorded_at": "2026-10-18T00:00:00+00:00",
        **fields,
    }
    return store.add_event(event_id, session_id, event_type, payload)[0]


def must_reject(fn):
    try:
        fn()
    except (CollaborationEvidenceError, ValueError):
        return
    raise AssertionError("expected backend evidence gate to reject the action")


def main():
    with tempfile.TemporaryDirectory(prefix="ai4brain-collaboration-") as tmp:
        store = Store(Path(tmp) / "collaboration.sqlite3")
        session_id = "collab-session"
        store.create_session("collab-prior-session", "demo-user")
        prior_evidence = add(store, "collab-prior-session", "assessment_trial_completed", phase="baseline",
                             exercise_id="EX-02", evaluation={"correct": True})
        store.create_session(session_id, "demo-user")
        consent_id = f"consent-{session_id}"
        evidence = add(store, session_id, "training_trial_completed", phase="training", exercise_id="EX-02",
                       evaluation={"correct": True}, interaction={"hint_count": 0, "visibility_interrupted": False})
        recommendation = add(store, session_id, "exercise_recommended", phase="policy", exercise_id="EX-02",
                             action="targeted_training", alternatives=[{"exercise_id": "EX-01", "reason": "goal fit"}],
                             evidence_ids=[evidence["event_id"]], rationale="A saved recommendation grounded in this practice event.")
        coach = add(store, session_id, "coaching_message_sent", phase="coach",
                    evidence_ids=[prior_evidence["event_id"], evidence["event_id"], recommendation["event_id"]],
                    coach_response={
                        "evidence_ids": [prior_evidence["event_id"], evidence["event_id"], recommendation["event_id"]],
                        "rationale": "The saved practice events support this bounded suggestion.",
                        "follow_up": "Which part of this recommendation is unclear, and would you like to inspect the cited evidence?",
                        "caveat": "Preliminary, high uncertainty, and not a clinical assessment.",
                    },
                    collaboration_context={
                         "clarification_follow_up": "Which part of this recommendation is unclear, and would you like to inspect the cited evidence?",
                        "verification_evidence_ids": [prior_evidence["event_id"]],
                        "suggestion_event_id": recommendation["event_id"],
                        "autonomy_recommendation_event_id": recommendation["event_id"],
                        "consent_event_id": consent_id,
                        "responsible_use_notice_shown": True,
                    })
        must_reject(lambda: issue_opportunities(store, "client-invented-opportunity", session_id=session_id))
        must_reject(lambda: issue_opportunities(store, evidence["event_id"], session_id=session_id))

        issued = issue_opportunities(store, coach["event_id"], session_id=session_id)
        assert {item["opportunity"]["dimension"] for item in issued} == set(WEIGHTS)
        count_after_first_issue = len(store.events(session_id=session_id))
        repeated = issue_opportunities(store, coach["event_id"], session_id=session_id)
        assert len(store.events(session_id=session_id)) == count_after_first_issue
        assert all(item["replayed"] for item in repeated), "opportunity issuance retry must not add events"

        before_actions = collaboration_score(store)
        assert before_actions["score_0_100"] is None
        assert all(before_actions["dimensions"][name]["status"] == "NOT_ASSESSED" for name in WEIGHTS)

        by_dimension = {item["opportunity"]["dimension"]: item["opportunity"]["event_id"] for item in issued}
        inspection = add(store, session_id, "collaboration_evidence_inspected",
                         opportunity_id=by_dimension["critical_verification"],
                         inspected_event_id=prior_evidence["event_id"])
        changed = add(store, session_id, "suggestion_revised", suggestion_event_id=recommendation["event_id"],
                      revision="chose a different task after comparing the goal and evidence")
        choice = add(store, session_id, "independent_choice_made", recommendation_event_id=recommendation["event_id"],
                     choice="decline", reason="I prefer to complete the other task first.")
        responsible = add(store, session_id, "responsible_use_choice", consent_event_id=consent_id,
                          choice="keep_local", reason="I want this practice data to stay on this device.")

        evidence_by_dimension = {
            "clarification": {"action": "pass", "reason": "I will continue without a clarification question."},
             "critical_verification": {"checked_evidence_ids": [prior_evidence["event_id"]],
                                      "inspection_event_ids": [inspection["event_id"]],
                                      "verification_note": "This saved training event supports the narrow task observation only."},
            "iteration": {"suggestion_event_id": recommendation["event_id"], "changed_choice_event_id": changed["event_id"],
                          "revision_summary": "I changed the selected exercise after checking how it matched my goal."},
            "autonomy": {"choice_event_id": choice["event_id"], "choice": "decline",
                         "reason": "I chose another practice task because it better fits my current goal."},
            "responsible_use": {"consent_event_id": consent_id, "choice_event_id": responsible["event_id"],
                                "choice": "keep_local", "reason": "I considered the notice and prefer local-only practice."},
        }
        for dimension, action_data in evidence_by_dimension.items():
            action = record_action(store, session_id, by_dimension[dimension], action_data)
            retry = record_action(store, session_id, by_dimension[dimension], action_data)
            assert retry["replayed"] is True
            changed_data = dict(action_data)
            changed_key = "reason" if "reason" in changed_data else (
                "verification_note" if "verification_note" in changed_data else (
                    "revision_summary" if "revision_summary" in changed_data else "question"))
            changed_data[changed_key] = "A materially different explanation of the action and its evidence."
            must_reject(lambda oid=by_dimension[dimension], data=changed_data: record_action(
                store, session_id, oid, data))

        result = collaboration_score(store)
        assert result["score_0_100"] == 80.0, result
        assert result["dimensions"]["clarification"]["score_0_100"] == 0
        assert result["dimensions"]["critical_verification"]["score_0_100"] == 100
        assert result["evaluated_opportunity_count"] == 5
        assert result["weights_percent"] == WEIGHTS and result["message_count_used"] is False
        print("collaboration smoke passed: genuine opportunity gate, all five weights, linked action evidence, repeat-safe issuance/actions, no message-count scoring")


if __name__ == "__main__":
    main()




