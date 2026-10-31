"""Isolated API smoke for collaboration evidence, choices, and idempotency."""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["NEO4J_ENABLED"] = "false"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.collaboration_routes import create_collaboration_router
from backend.app.collaboration_service import issue_opportunities
from backend.app.storage import Store, utc_now


def add(store, session_id, event_type, **fields):
    event_id = fields.pop("event_id", str(uuid.uuid4()))
    payload = {
        "event_id": event_id, "learner_id": "demo-user", "session_id": session_id,
        "event_type": event_type, "sample_data": False, "recorded_at": utc_now(), **fields,
    }
    return store.add_event(event_id, session_id, event_type, payload)[0]


def make_plan(store, session_id, goal):
    plan = {
        "plan_id": str(uuid.uuid4()), "learner_id": "demo-user", "profile_snapshot_id": None,
        "policy_version": "training-plan-v1", "goal": goal, "budget_minutes": 12,
        "estimated_time_minutes": 4, "reason_codes": ["explicit_user_goal"],
        "rationale": "Regenerated for the explicitly selected goal.", "steps": [
            {"step_id": "step-1", "dimension_id": goal, "exercise_type_id": "EX-05",
             "action": "additional_assessment", "difficulty_tier": "baseline", "strategy_id": None,
             "selection_reason": "explicit_user_goal", "source_evidence_ids": [],
             "estimated_time_minutes": 2, "status": "recommended"},
            {"step_id": "step-2", "dimension_id": "reasoning", "exercise_type_id": "EX-02",
             "action": "additional_assessment", "difficulty_tier": "baseline", "strategy_id": None,
             "selection_reason": "minimum_two_step_plan", "source_evidence_ids": [],
             "estimated_time_minutes": 2, "status": "recommended"},
        ],
        "evidence_ids": [], "features": {"goal": goal}, "alternatives": [],
        "decision_fingerprint": [goal, str(uuid.uuid4())], "status": "active", "created_at": utc_now(),
    }
    store.save_plan(plan)
    add(store, session_id, "training_plan_generated", plan_id=plan["plan_id"],
        goal=goal, evidence_ids=[], reason_codes=["explicit_user_goal"])
    return plan


def main():
    with tempfile.TemporaryDirectory(prefix="ai4brain-collaboration-api-") as tmp:
        store = Store(Path(tmp) / "api.sqlite3")
        sid = "interaction-session"
        store.create_session(sid, "demo-user")
        consent_id = f"consent-{sid}"
        evidence = add(store, sid, "assessment_trial_completed", phase="baseline", exercise_id="EX-02",
                       evaluation={"correct": True})
        uncited = add(store, sid, "practice_trial_completed", phase="practice", exercise_id="EX-01")
        recommendation = add(store, sid, "exercise_recommended", phase="policy", exercise_id="EX-02",
                             dimension="reasoning", action="targeted_training",
                             alternatives=[{"dimension": "planning"}, {"dimension": "attention_inhibition"}],
                             evidence_ids=[evidence["event_id"]],
                             rationale="A saved policy recommendation tied to baseline evidence.")
        coach_id = str(uuid.uuid4())
        coach_payload = {
            "event_id": coach_id, "learner_id": "demo-user", "session_id": sid,
            "event_type": "coaching_message_sent", "phase": "coach", "sample_data": False,
            "coach_response": {
                "evidence_ids": [evidence["event_id"], recommendation["event_id"]],
                "rationale": "This bounded suggestion is grounded in the saved task evidence.",
                "follow_up": "What would you like me to clarify after you inspect the supporting evidence?",
                "caveat": "Preliminary and high uncertainty; this is not a clinical assessment.",
            },
            "collaboration_context": {
                "clarification_follow_up": "What would you like me to clarify after you inspect the supporting evidence?",
                "verification_evidence_ids": [evidence["event_id"]],
                "suggestion_event_id": recommendation["event_id"],
                "autonomy_recommendation_event_id": recommendation["event_id"],
                "consent_event_id": consent_id, "responsible_use_notice_shown": True,
            },
            "recorded_at": utc_now(),
        }
        store.add_event(coach_id, sid, "coaching_message_sent", coach_payload)
        issued = issue_opportunities(store, coach_id, session_id=sid)
        assert len(issued) == 5

        # A second verification opportunity in the same session cites the same
        # record. Explicit inspection must bind to the selected card, regardless
        # of the legacy route's latest-matching-opportunity behavior.
        second_coach_id = str(uuid.uuid4())
        second_coach_payload = {
            "event_id": second_coach_id, "learner_id": "demo-user", "session_id": sid,
            "event_type": "coaching_message_sent", "phase": "coach", "sample_data": False,
            "coach_response": {
                "evidence_ids": [evidence["event_id"]],
                "rationale": "This second prompt refers to the same saved baseline event.",
                "follow_up": "Inspect the cited evidence before deciding what it supports.",
                "caveat": "Preliminary and high uncertainty; this is not a clinical assessment.",
            },
            "collaboration_context": {"verification_evidence_ids": [evidence["event_id"]]},
            "recorded_at": utc_now(),
        }
        store.add_event(second_coach_id, sid, "coaching_message_sent", second_coach_payload)
        second_verification = issue_opportunities(store, second_coach_id, session_id=sid)
        assert len(second_verification) == 1
        second_verification_id = second_verification[0]["opportunity"]["opportunity_id"]

        # Another local session verifies that scoped GETs do not leak cards and
        # cross-session action requests cannot append canonical events.
        sid2 = "interaction-session-2"
        store.create_session(sid2, "demo-user")
        evidence2 = add(store, sid2, "assessment_trial_completed", phase="baseline", exercise_id="EX-02",
                        evaluation={"correct": True})
        consent_id2 = f"consent-{sid2}"
        coach2_id = str(uuid.uuid4())
        coach2_payload = {
            "event_id": coach2_id, "learner_id": "demo-user", "session_id": sid2,
            "event_type": "coaching_message_sent", "phase": "coach", "sample_data": False,
            "coach_response": {
                "evidence_ids": [evidence2["event_id"]],
                "rationale": "This opportunity is grounded in the second session's saved event.",
                "follow_up": "Inspect the cited evidence before deciding what it supports.",
                "caveat": "Preliminary and high uncertainty; this is not a clinical assessment.",
            },
            "collaboration_context": {"verification_evidence_ids": [evidence2["event_id"]],
                                      "consent_event_id": consent_id2,
                                      "responsible_use_notice_shown": True},
            "recorded_at": utc_now(),
        }
        store.add_event(coach2_id, sid2, "coaching_message_sent", coach2_payload)
        issued2 = issue_opportunities(store, coach2_id, session_id=sid2)
        assert len(issued2) == 2

        callback_goals = []
        def regenerate_plan(session_id, goal):
            callback_goals.append((session_id, goal))
            return make_plan(store, session_id, goal)

        app = FastAPI()
        app.include_router(create_collaboration_router(store, lambda event: event, regenerate_plan))
        client = TestClient(app)

        initial = client.get("/api/collaboration/demo-user")
        assert initial.status_code == 200, initial.text
        assert initial.json()["score"]["score_0_100"] is None
        assert len(initial.json()["open_opportunities"]) == 8
        before_scoped_reads = len(store.events())
        scoped1 = client.get(f"/api/collaboration/demo-user?session_id={sid}")
        scoped2 = client.get(f"/api/collaboration/demo-user?session_id={sid2}")
        assert scoped1.status_code == scoped2.status_code == 200
        assert len(scoped1.json()["opportunities"]) == 6
        assert len(scoped2.json()["opportunities"]) == 2
        assert all(op["session_id"] == sid for op in scoped1.json()["opportunities"])
        assert all(op["session_id"] == sid2 for op in scoped2.json()["opportunities"])
        scoped1_by_id = {op["opportunity_id"]: op for op in scoped1.json()["opportunities"]}
        assert scoped1_by_id[issued[1]["opportunity"]["opportunity_id"]]["inspectable_evidence_ids"] == [evidence["event_id"]]
        assert all(not op["inspectable_evidence_ids"] for op in scoped1.json()["opportunities"]
                   if op["dimension"] != "critical_verification")
        assert scoped1.json()["score"] == scoped2.json()["score"] == initial.json()["score"]
        assert len(store.events()) == before_scoped_reads, "scoped GETs must not append canonical events"
        assert client.get("/api/collaboration/demo-user?session_id=missing-session").status_code == 404

        cross_session_before = len(store.events(session_id=sid2))
        cross_session = client.post("/api/collaboration/actions", json={
            "session_id": sid2, "opportunity_id": issued[0]["opportunity"]["opportunity_id"],
            "action": "pass", "reason": "This action must not cross into another session.",
        })
        assert cross_session.status_code == 404
        assert len(store.events(session_id=sid2)) == cross_session_before

        forged = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": "invented-opportunity", "action": "pass", "reason": "No genuine opportunity was issued."
        })
        assert forged.status_code == 404
        extra = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": issued[0]["opportunity"]["event_id"],
            "question": "What does this evidence mean for this task?", "unsupported": True,
        })
        assert extra.status_code == 422

        opportunities = {entry["opportunity"]["dimension"]: entry["opportunity"]["event_id"] for entry in issued}
        verification_body = {
            "session_id": sid, "opportunity_id": opportunities["critical_verification"],
            "checked_evidence_ids": [evidence["event_id"]],
            "verification_note": "The saved baseline event supports only this narrow task observation.",
        }
        before_evidence_reads = len(store.events())
        read_critical = client.get(
            f"/api/collaboration/evidence/{evidence['event_id']}",
            params={"session_id": sid, "opportunity_id": opportunities["critical_verification"]},
        )
        assert read_critical.status_code == 200, read_critical.text
        assert read_critical.json()["source_event"]["event_id"] == evidence["event_id"]
        assert read_critical.json()["inspection_recorded"] is False
        read_autonomy_source = client.get(
            f"/api/collaboration/evidence/{coach_id}",
            params={"session_id": sid, "opportunity_id": opportunities["autonomy"]},
        )
        assert read_autonomy_source.status_code == 200, read_autonomy_source.text
        assert read_autonomy_source.json()["source_event"]["event_id"] == coach_id
        uncited_read = client.get(
            f"/api/collaboration/evidence/{uncited['event_id']}",
            params={"session_id": sid, "opportunity_id": opportunities["critical_verification"]},
        )
        assert uncited_read.status_code == 409
        cross_session_read = client.get(
            f"/api/collaboration/evidence/{evidence['event_id']}",
            params={"session_id": sid2, "opportunity_id": opportunities["critical_verification"]},
        )
        assert cross_session_read.status_code == 404
        assert len(store.events()) == before_evidence_reads, "reading cited evidence must not append events"
        blocked = client.post("/api/collaboration/actions", json=verification_body)
        assert blocked.status_code == 409, blocked.text
        inspect = client.post("/api/collaboration/inspect", json={"session_id": sid, "event_id": evidence["event_id"]})
        assert inspect.status_code == 200, inspect.text
        assert inspect.json()["replayed"] is False
        assert inspect.json()["inspection"]["payload"]["opportunity_id"] == second_verification_id
        inspect_retry = client.post("/api/collaboration/inspect", json={"session_id": sid, "event_id": evidence["event_id"]})
        assert inspect_retry.status_code == 200 and inspect_retry.json()["replayed"] is True
        explicit_inspect = client.post("/api/collaboration/inspect", json={
            "session_id": sid, "event_id": evidence["event_id"], "opportunity_id": opportunities["critical_verification"],
        })
        assert explicit_inspect.status_code == 200, explicit_inspect.text
        assert explicit_inspect.json()["inspection"]["payload"]["opportunity_id"] == opportunities["critical_verification"]
        wrong_card = client.post("/api/collaboration/inspect", json={
            "session_id": sid, "event_id": evidence["event_id"], "opportunity_id": opportunities["clarification"],
        })
        assert wrong_card.status_code == 409
        not_cited = client.post("/api/collaboration/inspect", json={"session_id": sid, "event_id": uncited["event_id"]})
        assert not_cited.status_code == 409


        question = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": opportunities["clarification"],
            "question": "Which saved event supports this recommendation and why?",
        })
        assert question.status_code == 200, question.text
        verify = client.post("/api/collaboration/actions", json=verification_body)
        assert verify.status_code == 200, verify.text
        verify_retry = client.post("/api/collaboration/actions", json=verification_body)
        assert verify_retry.status_code == 200 and verify_retry.json()["replayed"] is True
        changed_verify = client.post("/api/collaboration/actions", json={
            **verification_body, "verification_note": "A different explanation for this evidence was submitted."
        })
        assert changed_verify.status_code == 409

        iteration_id = opportunities["iteration"]
        before_goal = store.get_session(sid)["goal_dimension"]
        invalid_goal = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": iteration_id, "new_goal_dimension": "reasoning",
            "revision_summary": "I keep the same suggestion, which is not an iteration.",
        })
        assert invalid_goal.status_code == 422 and store.get_session(sid)["goal_dimension"] == before_goal
        iteration_body = {
            "session_id": sid, "opportunity_id": iteration_id, "new_goal_dimension": "planning",
            "revision_summary": "I changed the goal after considering the linked recommendation and evidence.",
        }
        iteration = client.post("/api/collaboration/actions", json=iteration_body)
        assert iteration.status_code == 200, iteration.text
        assert store.get_session(sid)["goal_dimension"] == "planning"
        assert store.latest_plan("demo-user")["goal"] == "planning"
        assert callback_goals == [(sid, "planning")]
        iteration_retry = client.post("/api/collaboration/actions", json=iteration_body)
        assert iteration_retry.status_code == 200 and iteration_retry.json()["replayed"] is True
        assert callback_goals == [(sid, "planning")], "a replay must not regenerate/inflate the plan"

        autonomy_body = {
            "session_id": sid, "opportunity_id": opportunities["autonomy"], "choice": "modify",
            "new_goal_dimension": "working_memory", "reason": "I chose another real alternative that better fits my immediate goal.",
        }
        invalid_alternative = client.post("/api/collaboration/actions", json=autonomy_body)
        assert invalid_alternative.status_code == 422, invalid_alternative.text
        autonomy_body["new_goal_dimension"] = "attention_inhibition"
        autonomy = client.post("/api/collaboration/actions", json=autonomy_body)
        assert autonomy.status_code == 200, autonomy.text
        assert store.get_session(sid)["goal_dimension"] == "attention_inhibition"
        assert store.latest_plan("demo-user")["goal"] == "attention_inhibition"
        autonomy_retry = client.post("/api/collaboration/actions", json=autonomy_body)
        assert autonomy_retry.status_code == 200 and autonomy_retry.json()["replayed"] is True
        assert callback_goals == [(sid, "planning"), (sid, "attention_inhibition")]

        responsible = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": opportunities["responsible_use"],
            "choice": "keep_local", "reason": "I considered the saved notice and prefer data to remain on this device.",
        })
        assert responsible.status_code == 200, responsible.text
        remote = client.post("/api/collaboration/actions", json={
            "session_id": sid, "opportunity_id": opportunities["responsible_use"],
            "choice": "proceed_after_notice", "reason": "I opt in to a provider that the POC does not support.",
        })
        assert remote.status_code == 422

        final = client.get("/api/collaboration/demo-user").json()
        assert final["score"]["score_0_100"] is not None
        assert len(final["open_opportunities"]) == 3
        expected_open = {second_verification_id, *(row["opportunity"]["opportunity_id"] for row in issued2)}
        assert {item["opportunity_id"] for item in final["open_opportunities"]} == expected_open
        assert all(item["status"] == "evaluated" for item in final["opportunities"]
                   if item["opportunity_id"] in set(opportunities.values()))
        print("interaction API smoke passed: session-scoped opportunity lists, read-only cited evidence for multiple opportunity types, no verification credit from reading, cross-session rejection, exact inspection binding with legacy fallback, strict fields, meaningful action flow, real goal/plan changes, and no replay inflation")


if __name__ == "__main__":
    main()





