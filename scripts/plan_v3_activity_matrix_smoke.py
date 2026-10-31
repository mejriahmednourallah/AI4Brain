"""Disposable API acceptance matrix for plan-v3 HY-01..06 and Crystal mapping.

All baseline completions and game activity records are synthetic, created in a
temporary SQLite database through canonical API routes. This is backend contract
coverage, not a browser/gameplay acceptance claim.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"


def uid() -> str:
    return str(uuid.uuid4())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-plan-v3-activity-matrix-") as temp:
        os.environ["AI4BRAIN_DB"] = str(Path(temp) / "matrix.sqlite3")
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app.battery_exercises import shortest_path
        from backend.app.exercises import ITEM_BANK
        from backend.app.hybrid_activities import CATALOG as HYBRIDS
        from backend.app.plan_v3 import refresh_plan_execution_status
        from backend.app.profile_service import build_profile

        ids = [*(f"HY-{i:02d}" for i in range(1, 7)), "CRYSTAL"]
        launched = {}

        with TestClient(app) as client:
            session = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True})
            assert session.status_code == 201, session.text
            sid = session.json()["id"]

            # The default plan must not schedule later-practice activities before all five
            # fixed-family baseline gates are complete, even though activities are available.
            incomplete = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
            assert incomplete.status_code == 200, incomplete.text
            incomplete_plan = incomplete.json()
            assert incomplete_plan["personalized_practice"]["eligible"] is False
            assert incomplete_plan["personalized_practice"]["gate"] == "all_five_core_baselines_completed"
            assert not any(step.get("activity_ref", {}).get("kind") in {"hybrid", "crystal"}
                           for step in incomplete_plan["steps"])
            assert incomplete_plan["planned_minutes"] <= 30

            empty_incomplete = client.post("/api/plans/next", json={
                "session_id": sid, "budget_minutes": 4, "available_activities": [],
            })
            assert empty_incomplete.status_code == 200, empty_incomplete.text
            assert empty_incomplete.json()["availability"]["requested_activities_applied"] is True
            assert empty_incomplete.json()["availability"]["requested_activities"] == []
            assert not any(step.get("activity_ref", {}).get("kind") in {"hybrid", "crystal"}
                           for step in empty_incomplete.json()["steps"])
            assert empty_incomplete.json()["planned_minutes"] <= 4

            empty_core_filter = client.post("/api/plans/next", json={
                "session_id": sid, "budget_minutes": 30, "available_dimensions": [],
                "available_activities": ["HY-01"],
            })
            assert empty_core_filter.status_code == 200, empty_core_filter.text
            assert not any(step.get("activity_ref", {}).get("kind") in {"hybrid", "crystal"}
                           for step in empty_core_filter.json()["steps"])
            assert empty_core_filter.json()["planned_minutes"] <= 30

            # Complete each fixed baseline through its canonical scored-trial route.
            for exercise_id in ("EX-01", "EX-02", "EX-03", "EX-04", "EX-05"):
                if exercise_id == "EX-02":
                    config = client.get("/api/exercises/EX-02").json()
                else:
                    config_response = client.get(f"/api/exercises/{exercise_id}", params={"session_id": sid})
                    assert config_response.status_code == 200, (exercise_id, config_response.text)
                    config = config_response.json()
                for item in config["items"]:
                    stimulus = item.get("stimulus", {})
                    body = {
                        "event_id": uid(), "session_id": sid, "learner_id": "demo-user",
                        "exercise_id": exercise_id, "exercise_version": config["exercise_version"],
                        "phase": "baseline", "item_id": item["item_id"], "response_time_ms": 600,
                    }
                    if exercise_id == "EX-02":
                        # The canonical answer key is server-owned and intentionally not
                        # present in the public exercise DTO.
                        choice_id = ITEM_BANK[item["item_id"]]["answer"]
                        body["choice"] = choice_id
                    elif exercise_id == "EX-01":
                        body["response_data"] = {"selected_sequence": list(stimulus["sequence"])}
                    elif exercise_id == "EX-03":
                        body["response_data"] = {"responded": stimulus["signal"] == "go"}
                    elif exercise_id == "EX-04":
                        rule = stimulus["active_rule"]
                        choice = next(option["id"] for option in stimulus["options"]
                                      if option[rule] == stimulus["target"][rule])
                        body["response_data"] = {"choice": choice}
                    else:
                        moves = shortest_path(stimulus)
                        body["response_data"] = {"actions": [{"action": "move", "direction": move}
                                                               for move in moves]}
                    saved = client.post("/api/trials", json=body)
                    assert saved.status_code == 200, (exercise_id, item["item_id"], saved.text)

            profile = build_profile(store.events(learner_id="demo-user"))
            assert all(profile["dimensions"][dimension]["completed"] for dimension in
                       ("working_memory", "reasoning", "attention_inhibition", "flexibility", "planning")), \
                {dimension: row.get("completed") for dimension, row in profile["dimensions"].items()}

            # An explicit empty activity list is still empty after the later-practice gate;
            # a budget of four minutes is never overbooked for any single activity.
            empty_ready = client.post("/api/plans/next", json={
                "session_id": sid, "budget_minutes": 60, "available_activities": [],
            })
            assert empty_ready.status_code == 200, empty_ready.text
            empty_ready_plan = empty_ready.json()
            assert empty_ready_plan["personalized_practice"]["eligible"] is True
            assert empty_ready_plan["personalized_practice"]["scheduled_activity_ids"] == []
            assert empty_ready_plan["availability"]["requested_activities"] == []
            assert all(step.get("activity_ref", {}).get("kind") == "core"
                       for step in empty_ready_plan["steps"])
            assert empty_ready_plan["planned_minutes"] <= 60

            for activity_id in ids:
                budgeted = client.post("/api/plans/next", json={
                    "session_id": sid, "budget_minutes": 4,
                    "available_activities": [activity_id],
                })
                assert budgeted.status_code == 200, (activity_id, budgeted.text)
                budget_plan = budgeted.json()
                assert budget_plan["personalized_practice"]["eligible"] is True
                assert budget_plan["planned_minutes"] <= 4, (activity_id, budget_plan["planned_minutes"])
                assert all(step["estimated_time_minutes"] <= 4 for step in budget_plan["steps"])

                response = client.post("/api/plans/next", json={
                    "session_id": sid, "budget_minutes": 60,
                    "available_activities": [activity_id],
                })
                assert response.status_code == 200, (activity_id, response.text)
                plan = response.json()
                assert plan["plan_version"] == "plan-v3"
                assert plan["personalized_practice"]["eligible"] is True
                assert plan["personalized_practice"]["scheduled_activity_ids"] == [activity_id]
                assert plan["availability"]["requested_activities_applied"] is True
                assert plan["availability"]["requested_activities"] == [activity_id]
                assert plan["planned_minutes"] == sum(step["estimated_time_minutes"] for step in plan["steps"])
                assert plan["planned_minutes"] <= 60
                activity_step = next(step for step in plan["steps"]
                                     if step.get("activity_ref", {}).get("id") == activity_id)
                assert activity_step["duration_estimate"]["confidence"] == "provisional"
                assert activity_step["contributions"] == {
                    "baseline_indices": False, "ex_difficulty_tiers": False, "participation_xp": False,
                }
                core_steps = [step for step in plan["steps"]
                              if step.get("activity_ref", {}).get("kind") == "core"]
                assert not core_steps or plan["steps"][0]["activity_ref"]["kind"] == "core", activity_id

                step_id = activity_step["step_id"]
                launch_url = f"/api/plans/{plan['plan_id']}/steps/{step_id}/launch"
                request_id = uid()
                launch_body = {"request_id": request_id, "session_id": sid}
                launch = client.post(launch_url, json=launch_body)
                assert launch.status_code == 200, (activity_id, launch.text)
                started = launch.json()
                assert started["activity_ref"] == activity_step["activity_ref"]
                assert started["attempt_ref"]["kind"] == activity_step["activity_ref"]["kind"]
                assert started["attempt_ref"]["version"] == activity_step["activity_ref"]["version"]
                replay = client.post(launch_url, json=launch_body)
                assert replay.status_code == 200, (activity_id, replay.text)
                assert replay.json()["attempt_ref"] == started["attempt_ref"]
                assert replay.json()["idempotent_replay"] is True

                attempt_id = started["attempt_ref"]["id"]
                if activity_id == "CRYSTAL":
                    read_attempt = client.get(f"/api/crystal/attempts/{attempt_id}")
                    assert read_attempt.status_code == 200, read_attempt.text
                    crystal_config = read_attempt.json()["config"]
                    expected = crystal_config["grid"][0][1]
                    choice_id = next(choice["choice_id"] for choice in crystal_config["choices"]
                                     if choice["value"] == expected)
                    answer_body = {"event_id": uid(), "choice_id": choice_id, "response_time_ms": 500}
                    answer = client.post(f"/api/crystal/attempts/{attempt_id}/answer", json=answer_body)
                    assert answer.status_code == 200 and answer.json()["outcome"]["correct"] is True, answer.text
                    answer_replay = client.post(f"/api/crystal/attempts/{attempt_id}/answer", json=answer_body)
                    assert answer_replay.status_code == 200 and answer_replay.json()["replayed"] is True
                    starts = [event for event in read_attempt.json()["events"] if event["type"] == "crystal_started"]
                    assert len(starts) == 1
                else:
                    read_attempt = client.get(f"/api/hybrid/attempts/{attempt_id}")
                    assert read_attempt.status_code == 200, read_attempt.text
                    attempt = read_attempt.json()
                    assert attempt["activity_id"] == activity_id
                    assert attempt["mode"] == activity_step["mode"] == "training"
                    assert attempt["activity_version"] == activity_step["activity_ref"]["version"]
                    config = attempt["config"]
                    sequence = 1

                    def action(action_type: str, payload: dict, cue_event_id: str | None = None) -> None:
                        nonlocal sequence
                        posted = client.post(f"/api/hybrid/attempts/{attempt_id}/actions", json={
                            "event_id": uid(), "attempt_id": attempt_id, "sequence": sequence,
                            "action_type": action_type, "payload": payload,
                            "cue_event_id": cue_event_id,
                        })
                        assert posted.status_code == 201, (activity_id, posted.text)
                        sequence += 1

                    if activity_id == "HY-01":
                        action("move", {"direction": "right"})
                    elif activity_id == "HY-02":
                        observed = []
                        for index in range(int(config["trial_count"])):
                            cue = client.get(f"/api/hybrid/attempts/{attempt_id}/stimulus").json()
                            n_back = int(cue["n_back"])
                            prior = observed[index - n_back] if index >= n_back else None
                            action("respond", {
                                "trial_index": index,
                                "position_match": bool(prior and cue["position"] == prior["position"]),
                                "symbol_match": bool(prior and cue["symbol"] == prior["symbol"]),
                            }, cue["cue_id"])
                            observed.append({"position": cue["position"], "symbol": cue["symbol"]})
                    elif activity_id == "HY-03":
                        allowed_bins = sorted(set(config["rules"]["color_bins"].values()) |
                                               set(config["rules"]["shape_bins"].values()))
                        for cargo in config["cargo"]:
                            action("select", {"cargo_id": cargo["cargo_id"], "bin_id": allowed_bins[0]})
                    elif activity_id == "HY-04":
                        total = int(config["wave_count"]) * int(config["arrivals_per_wave"])
                        for index in range(total):
                            cue = client.get(f"/api/hybrid/attempts/{attempt_id}/stimulus").json()
                            if cue["distractor"]:
                                destination, ignore = None, True
                            else:
                                destination = cue.get("marked_destination") or config["manifest"][cue["cargo_id"]]
                                ignore = False
                            action("respond", {"arrival_index": index, "destination_id": destination,
                                               "ignore": ignore}, cue["cue_id"])
                    elif activity_id == "HY-05":
                        first_object = config["objects"][0]
                        action("select", {"object_id": first_object["object_id"], "slot_index": 0})
                        action("commit", {"stage": "proposal"})
                    else:
                        allowed_refs = [edge["edge_id"] for edge in config["edges"]]
                        action("advise", {"decision": "hold", "inspected_refs": allowed_refs[:1]})

                    completion_body = {"event_id": uid(), "attempt_id": attempt_id}
                    complete = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json=completion_body)
                    assert complete.status_code == 200, (activity_id, complete.text)
                    assert complete.json()["completion_state"] == "completed"
                    complete_replay = client.post(f"/api/hybrid/attempts/{attempt_id}/complete",
                                                  json=completion_body)
                    assert complete_replay.status_code == 200
                    assert complete_replay.json()["attempt_id"] == attempt_id
                    after_attempt = client.get(f"/api/hybrid/attempts/{attempt_id}").json()
                    assert after_attempt["status"] == "completed"
                    starts = [event for event in after_attempt["events"]
                              if event["type"] == "hybrid_attempt_started"]
                    assert len(starts) == 1

                # GET history derives step completion from its namespaced canonical outcome.
                history = client.get("/api/plans/demo-user")
                assert history.status_code == 200, history.text
                projected_plan = next(row for row in history.json()["history"]
                                      if row["plan_id"] == plan["plan_id"])
                projected_step = next(step for step in projected_plan["steps"]
                                       if step["step_id"] == step_id)
                expected_source = "crystal_outcomes" if activity_id == "CRYSTAL" else "hybrid_outcomes"
                assert projected_step["execution_status"] == "completed", (activity_id, projected_step)
                assert projected_step["completion_source"] == expected_source, (activity_id, projected_step)
                assert projected_step["completion_references"], (activity_id, projected_step)
                launched[activity_id] = {
                    "kind": started["attempt_ref"]["kind"],
                    "version": started["attempt_ref"]["version"],
                    "execution_status": projected_step["execution_status"],
                    "completion_source": projected_step["completion_source"],
                }

            assert set(launched) == set(ids), launched
            assert all(value["execution_status"] == "completed" for value in launched.values())
            assert store.plans("demo-user")

        print("PASS plan-v3 matrix: incomplete baseline gate; explicit empty activity/family availability; "
              "4-minute budget bound; eligible single-activity selection; plan launch/replay and "
              f"canonical outcome projection for {', '.join(ids)}")
        print({"activities": launched, "baseline_gates": 5, "launches": len(launched),
               "assessment_trials": len([e for e in store.events(learner_id="demo-user")
                                         if e["type"] == "assessment_trial_completed"]),
               "training_trials": len([e for e in store.events(learner_id="demo-user")
                                      if e["type"] == "training_trial_completed"])})


if __name__ == "__main__":
    main()
