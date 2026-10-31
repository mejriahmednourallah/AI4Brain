"""Temporary-SQLite acceptance smoke for the shared, read-only dashboard DTO."""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["NEO4J_ENABLED"] = "false"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-dashboard-") as folder:
        os.environ["AI4BRAIN_DB"] = str(Path(folder) / "dashboard.sqlite3")

        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app.exercises import ITEM_BANK, make_training_bank
        from backend.app.battery_exercises import shortest_path

        with TestClient(app) as client:
            def dashboard():
                response = client.get("/api/dashboard/demo-user")
                assert response.status_code == 200, response.text
                return response.json()

            initial = dashboard()
            assert initial["profile"]["learner_id"] == "demo-user"
            assert initial["task_coverage"]["total_count"] == 5
            assert initial["task_coverage"]["assessed_count"] == 0
            assert all(row["status"] == "NOT_ASSESSED" and row["index_0_100"] is None
                       for row in initial["task_coverage"]["dimensions"])
            assert initial["profile"]["snapshots"] == []
            assert initial["plan"] == {"latest": None, "history": []}
            assert initial["recommendation"] is None
            assert initial["participation"]["xp"] == 0
            assert initial["activity"]["total_valid_trials"] == 0
            assert initial["collaboration"]["score"]["score_0_100"] is None
            assert initial["collaboration"]["opportunity_count"] == 0
            assert {row["id"] for row in initial["milestones"]} == {
                "first_valid_practice", "first_completed_training_block",
                "all_five_families_assessed", "all_collaboration_dimensions_evaluated",
            }
            assert all(not row["achieved"] and row["progress_current"] == 0 and not row["evidence_ids"]
                       for row in initial["milestones"])
            assert client.get("/api/dashboard/other-user").status_code == 404

            session = client.post("/api/sessions", json={"consent_accepted": True, "dashboard_mode": "analytics"})
            assert session.status_code == 201, session.text
            session_id = session.json()["id"]
            baseline = client.get("/api/exercises/EX-02", params={"phase": "baseline"}).json()
            for item in baseline["items"]:
                body = {
                    "event_id": str(uuid.uuid4()), "session_id": session_id,
                    "phase": "baseline", "exercise_id": "EX-02",
                    "exercise_version": baseline["exercise_version"], "item_id": item["item_id"],
                    "choice": ITEM_BANK[item["item_id"]]["answer"],
                    "response_time_ms": 650, "stimulus_onset_ms": 100,
                }
                submitted = client.post("/api/trials", json=body)
                assert submitted.status_code == 200, submitted.text

            saved_recommendation = client.post("/api/recommendations/next", json={"session_id": session_id})
            assert saved_recommendation.status_code == 200, saved_recommendation.text
            saved_plan = client.post("/api/plans/next", json={"session_id": session_id})
            assert saved_plan.status_code == 200, saved_plan.text
            preference = client.post("/api/preferences", json={
                "session_id": session_id, "dashboard_mode": "analytics", "goal_dimension": "reasoning",
            })
            assert preference.status_code == 200, preference.text

            def add_event(event_type: str, **fields):
                event_id = fields.pop("event_id", str(uuid.uuid4()))
                payload = {
                    "event_id": event_id, "session_id": session_id, "learner_id": "demo-user",
                    "event_type": event_type, "sample_data": False,
                    "recorded_at": datetime.now(timezone.utc).isoformat(), **fields,
                }
                return store.add_event(event_id, session_id, event_type, payload)[0]

            add_event("training_block_started", phase="training", exercise_id="EX-02")
            add_event("difficulty_changed", phase="training", action="up", old_tier="tier-1", new_tier="tier-2")
            add_event("assessment_trial_completed", phase="baseline", exercise_id="EX-01",
                      item_id="memory-interrupted", interaction={"visibility_interrupted": True, "hint_count": 0})
            add_event("practice_trial_completed", phase="practice", exercise_id="EX-02",
                      item_id="reasoning-practice-1", interaction={"visibility_interrupted": False, "hint_count": 0})
            add_event("practice_trial_completed", phase="practice", exercise_id="EX-02",
                      item_id="reasoning-practice-2", interaction={"visibility_interrupted": True, "hint_count": 0})
            add_event("training_trial_completed", phase="training", exercise_id="EX-02",
                      item_id="reasoning-training-1", interaction={"visibility_interrupted": False, "hint_count": 1})
            add_event("training_trial_completed", phase="training", exercise_id="EX-02",
                      item_id="reasoning-training-2", interaction={"visibility_interrupted": True, "hint_count": 0})
            add_event("reassessment_trial_completed", phase="reassessment", exercise_id="EX-05",
                      item_id="planning-reassessment-01", interaction={"visibility_interrupted": False, "hint_count": 0})
            add_event("training_trial_completed", phase="policy", exercise_id="EX-02",
                      item_id="fake-policy-reward", interaction={"visibility_interrupted": False, "hint_count": 0})

            first = dashboard()
            assert first["preferences"] == {"dashboard_mode": "analytics", "goal_dimension": "reasoning"}
            assert first["profile"]["dimensions"]["reasoning"]["index_0_100"] == 100
            assert first["profile"]["dimensions"]["reasoning"]["evidence_count"] == 6
            assert first["profile"]["dimensions"]["reasoning"]["uncertainty_status"] == "PRELIMINARY_HIGH_UNCERTAINTY"
            assert len(first["profile"]["snapshots"]) >= 1
            assert first["profile"]["snapshots"][-1]["evidence_ids"] == first["profile"]["dimensions"]["reasoning"]["evidence_ids"]
            assert first["task_coverage"]["assessed_count"] == 1
            # The goal preference set above is a documented plan refresh trigger, so the active
            # plan is reconciled after it and the earlier manual plan stays in immutable history.
            latest_plan = first["plan"]["latest"]
            assert latest_plan["plan_version"] == "plan-v2", latest_plan.get("plan_version")
            assert latest_plan["plan_id"] != saved_plan.json()["plan_id"]
            plan_history = client.get("/api/plans/demo-user").json()["history"]
            assert any(row.get("plan_id") == saved_plan.json()["plan_id"] for row in plan_history)
            assert any((event.get("payload") or {}).get("plan_trigger", {}).get("kind") == "goal_changed"
                       for event in store.events(learner_id="demo-user")
                       if event["type"] in {"training_plan_revised", "training_plan_unchanged"})
            assert "evidence_ids" in latest_plan
            assert first["recommendation"]["event_type"] == "exercise_recommended"
            event_ids = {event["event_id"] for event in first["events"]}
            assert all(event_id in event_ids for event_id in latest_plan["evidence_ids"])
            assert all(event_id in event_ids for event_id in first["recommendation"]["evidence_ids"])
            assert first["activity"]["total_valid_trials"] == 9
            assert first["participation"]["practice_trial_count"] == 1
            assert first["participation"]["training_trial_count"] == 1
            assert first["participation"]["assisted_training_trial_count"] == 1
            assert first["participation"]["xp"] == 20
            assert first["participation"]["level"] == 1
            assert first["collaboration"]["score"]["score_0_100"] is None
            milestones = {row["id"]: row for row in first["milestones"]}
            assert milestones["first_valid_practice"]["achieved"]
            assert milestones["first_valid_practice"]["evidence_ids"] == [
                next(event["event_id"] for event in store.events(learner_id="demo-user")
                     if event["type"] == "practice_trial_completed"
                     and event["payload"].get("item_id") == "reasoning-practice-1")
            ]
            assert not milestones["first_completed_training_block"]["achieved"]
            assert milestones["first_completed_training_block"]["progress_current"] == 0
            assert not milestones["all_five_families_assessed"]["achieved"]
            assert milestones["all_five_families_assessed"]["progress_current"] == 1
            assert not milestones["all_collaboration_dimensions_evaluated"]["achieved"]
            assert milestones["all_collaboration_dimensions_evaluated"]["progress_current"] == 0

            forged_block_id = "unpersisted-training-block"
            forged_trial_ids = []
            for index in range(4):
                forged_trial_ids.append(add_event(
                    "training_trial_completed", phase="training", exercise_id="EX-02",
                    training_block_id=forged_block_id, item_id=f"forged-training-{index}",
                    interaction={"visibility_interrupted": False, "hint_count": 0},
                )["event_id"])
            add_event("difficulty_changed", phase="training", action="hold", old_tier="tier-1",
                      new_tier="tier-1", training_block_id=forged_block_id, evidence_ids=forged_trial_ids)
            forged_decision = next(row for row in dashboard()["milestones"]
                                   if row["id"] == "first_completed_training_block")
            assert not forged_decision["achieved"] and forged_decision["progress_current"] == 4

            def complete_baseline(exercise_id: str):
                response = client.get(f"/api/exercises/{exercise_id}", params={
                    "phase": "baseline", "session_id": session_id,
                })
                assert response.status_code == 200, response.text
                config = response.json()
                for item in config["items"]:
                    if exercise_id == "EX-01":
                        data = {"selected_sequence": item["stimulus"]["sequence"]}
                    elif exercise_id == "EX-03":
                        data = {"responded": item["stimulus"]["signal"] == "go"}
                    elif exercise_id == "EX-04":
                        stimulus = item["stimulus"]
                        match = next(option for option in stimulus["options"]
                                     if option[stimulus["active_rule"]] == stimulus["target"][stimulus["active_rule"]])
                        data = {"choice": match["id"]}
                    else:
                        data = {"actions": [{"action": "move", "direction": direction}
                                             for direction in shortest_path(item["stimulus"])]}
                    result = client.post("/api/trials", json={
                        "event_id": str(uuid.uuid4()), "session_id": session_id,
                        "phase": "baseline", "exercise_id": exercise_id,
                        "exercise_version": config["exercise_version"], "item_id": item["item_id"],
                        "response_data": data, "response_time_ms": 500,
                    })
                    assert result.status_code == 200, result.text

            for exercise_id in ("EX-01", "EX-03", "EX-04", "EX-05"):
                complete_baseline(exercise_id)
            all_assessed = dashboard()
            all_families = next(row for row in all_assessed["milestones"]
                                if row["id"] == "all_five_families_assessed")
            assert all_assessed["task_coverage"]["assessed_count"] == 5
            assert all_families["achieved"] and all_families["progress_current"] == 5
            all_assessment_ids = {event["event_id"] for event in store.events(learner_id="demo-user")
                                  if event["type"] in {"assessment_trial_completed", "reassessment_trial_completed"}}
            assert all(event_id in all_assessment_ids for event_id in all_families["evidence_ids"])
            assert len(all_families["evidence_ids"]) == 79

            # A completed training milestone requires a persisted decision and its actual four trials.
            block_response = client.post("/api/training/blocks", json={
                "session_id": session_id, "exercise_id": "EX-02", "tier": "tier-1",
            })
            assert block_response.status_code == 201, block_response.text
            block = block_response.json()["block"]
            block_id = block["block_id"]
            training = make_training_bank(block["tier"])
            for item in training:
                result = client.post("/api/trials", json={
                    "event_id": str(uuid.uuid4()), "session_id": session_id,
                    "phase": "training", "exercise_id": "EX-02",
                    "exercise_version": block["exercise_version"], "training_block_id": block_id,
                    "item_id": item["item_id"], "choice": item["answer"], "response_time_ms": 700,
                })
                assert result.status_code == 200, result.text
            completed_training = dashboard()
            training_milestone = next(row for row in completed_training["milestones"]
                                      if row["id"] == "first_completed_training_block")
            assert training_milestone["achieved"] and training_milestone["progress_current"] == 4, training_milestone
            training_event_ids = {event["event_id"] for event in store.block_events(block_id)}
            assert len(training_event_ids) == 4
            assert len(training_milestone["evidence_ids"]) == 5
            assert training_milestone["evidence_ids"][0] in {
                event["event_id"] for event in store.events(learner_id="demo-user")
                if event["type"] == "difficulty_changed"
            }
            assert set(training_milestone["evidence_ids"][1:]) == training_event_ids

            opportunity_id = str(uuid.uuid4())
            source_event_id = next(event["event_id"] for event in store.events(learner_id="demo-user")
                                   if event["type"] == "assessment_trial_completed")
            add_event("collaboration_opportunity_issued", event_id=opportunity_id,
                      opportunity_id=opportunity_id, dimension="clarification", prompt="Inspect this evidence.",
                      source_event_id=source_event_id, evidence_ids=[source_event_id])
            add_event("collaboration_action_recorded", opportunity_id=opportunity_id,
                      dimension="clarification", rubric_points=100)

            # Sample-only collaboration rows must not advance milestone progress.
            sample_id = str(uuid.uuid4())
            add_event("collaboration_opportunity_issued", event_id=sample_id,
                      opportunity_id=sample_id, dimension="responsible_use", source_event_id=source_event_id,
                      sample_data=True)
            add_event("collaboration_action_recorded", opportunity_id=sample_id,
                      dimension="responsible_use", rubric_points=100, sample_data=True)

            before_preferences = dashboard()
            assert before_preferences["collaboration"]["opportunity_count"] == 1
            assert before_preferences["collaboration"]["evaluated_opportunity_count"] == 1
            assert before_preferences["collaboration"]["open_opportunity_count"] == 0
            collaboration_milestone = next(row for row in before_preferences["milestones"]
                                           if row["id"] == "all_collaboration_dimensions_evaluated")
            assert not collaboration_milestone["achieved"]
            assert collaboration_milestone["progress_current"] == 1

            for dimension in ("critical_verification", "iteration", "autonomy", "responsible_use"):
                collab_id = str(uuid.uuid4())
                add_event("collaboration_opportunity_issued", event_id=collab_id,
                          opportunity_id=collab_id, dimension=dimension,
                          source_event_id=source_event_id, evidence_ids=[source_event_id], sample_data=False)
                add_event("collaboration_action_recorded", opportunity_id=collab_id,
                          dimension=dimension, rubric_points=100, evidence_ids=[source_event_id], sample_data=False)
            all_collaboration = dashboard()
            collaboration_milestone = next(row for row in all_collaboration["milestones"]
                                           if row["id"] == "all_collaboration_dimensions_evaluated")
            assert collaboration_milestone["achieved"] and collaboration_milestone["progress_current"] == 5
            canonical_ids = {event["event_id"] for event in store.events(learner_id="demo-user")}
            assert all(event_id in canonical_ids for event_id in collaboration_milestone["evidence_ids"])
            before_preferences = all_collaboration
            before_rows = len(store.events(learner_id="demo-user"))
            changed = client.post("/api/preferences", json={"session_id": session_id, "dashboard_mode": "rpg"})
            assert changed.status_code == 200, changed.text
            after_preferences = dashboard()
            assert after_preferences["preferences"]["dashboard_mode"] == "rpg"
            for key in ("profile", "events", "plan", "recommendation", "activity", "participation", "task_coverage", "collaboration", "milestones"):
                assert after_preferences[key] == before_preferences[key], f"dashboard mode changed {key}"

            event_count = len(store.events(learner_id="demo-user"))
            snapshot_count = len(store.snapshots("demo-user"))
            plan_count = len(store.plans("demo-user"))
            recommendation_count = len(store.recommendations("demo-user"))
            for _ in range(2):
                dashboard()
            assert len(store.events(learner_id="demo-user")) == event_count == before_rows + 1
            assert len(store.snapshots("demo-user")) == snapshot_count
            assert len(store.plans("demo-user")) == plan_count
            assert len(store.recommendations("demo-user")) == recommendation_count
            assert all("payload_json" not in event for event in after_preferences["events"])

    print("Dashboard smoke passed: null and achieved milestones, canonical evidence links, real trial/decision/collaboration eligibility, mode invariance and read-only GETs.")


if __name__ == "__main__":
    main()
