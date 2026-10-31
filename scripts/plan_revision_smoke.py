"""plan-v2 acceptance: evidence-triggered refresh, idempotency, lifecycle, ranking, budgets."""
from __future__ import annotations

import os
import json
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

with tempfile.TemporaryDirectory(prefix="ai4brain-plan-v2-") as folder:
    os.environ["AI4BRAIN_DB"] = str(Path(folder) / "plan.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    from backend.app.exercises import evaluate, make_training_bank
    from backend.app.plan_v2 import reconcile_plan
    from backend.app.storage import utc_now

    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]

        # 1. With no plan there is nothing to refresh; no plan is fabricated implicitly.
        first = reconcile_plan(store, {"kind": "baseline_completed", "event_id": "none-yet"})
        assert first["skipped"] and first["reason"] == "no_active_plan", first
        assert store.plans("demo-user") == []

        # 2. Create a plan through the public route.
        created = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
        assert created.status_code == 200, created.text
        plan = created.json()
        assert plan["plan_version"] == "plan-v3", plan.get("plan_version")
        assert plan["schema_version"] == 3, plan.get("schema_version")
        assert 2 <= len(plan["steps"]) <= 4, plan["steps"]
        assert plan["planned_minutes"] == sum(step["estimated_time_minutes"] for step in plan["steps"])
        assert plan["planned_minutes"] <= plan["budget_minutes"], plan
        assert plan["unused_minutes"] == plan["budget_minutes"] - plan["planned_minutes"], plan
        assert plan["ranking"], plan
        # Activity-specific durations: not one repeated two-minute default.
        durations = {step["exercise_type_id"]: step["estimated_time_minutes"] for step in plan["steps"]}
        assert len(set(durations.values())) > 1, durations
        assert all(step["status"] in {"recommended", "in_progress"} for step in plan["steps"]), plan["steps"]
        assert all(step["launch_tier"] == step["difficulty_tier"] for step in plan["steps"]
                   if step["action"] == "targeted_training"), "plan must persist authoritative launch tier"
        assert all(step["launch_tier"] is None for step in plan["steps"]
                   if step["action"] == "additional_assessment"), "baseline gates have no training tier"
        assert plan["features"]["tier_policy_version"] == "difficulty-policy-authoritative-v1"
        initial_plan_id = plan["plan_id"]

        # 3. Completing a baseline family automatically revises the active plan.
        reasoning = client.get("/api/exercises/EX-02", params={"session_id": sid}).json()
        last_body = None
        for item in reasoning["items"]:
            choice = next(c["choice_id"] for c in item["choices"] if evaluate(item["item_id"], c["choice_id"])[0])
            last_body = {"session_id": sid, "event_id": str(uuid.uuid4()), "exercise_id": "EX-02",
                         "exercise_version": reasoning["exercise_version"], "phase": "baseline",
                         "item_id": item["item_id"], "choice": choice, "response_time_ms": 1500}
            saved = client.post("/api/trials", json=last_body)
            assert saved.status_code == 200, saved.text

        events = store.events(learner_id="demo-user")
        revisions = [e for e in events if e["type"] in {"training_plan_revised", "training_plan_unchanged"}
                     and (e["payload"] or {}).get("plan_trigger", {}).get("kind") == "baseline_completed"]
        assert revisions, "a completed baseline must reconcile the active plan"
        assert any((e["payload"] or {}).get("before_plan_id") == initial_plan_id for e in revisions), revisions
        latest = store.latest_plan("demo-user")
        assert latest["plan_id"] != initial_plan_id, "a meaningful change creates a new revision"
        # A completed family must not still be described as missing.
        reasoning_steps = [s for s in latest["steps"] if s["dimension_id"] == "reasoning"]
        assert all(s["selection_reason"] != "unassessed_baseline" for s in reasoning_steps), reasoning_steps
        assert all(s["action"] != "additional_assessment" for s in reasoning_steps), reasoning_steps

        # Canonical plan launch uses the exact saved family tier and stable block id.
        targeted = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 10,
            "goal_dimension": "reasoning", "available_dimensions": ["reasoning"],
            "available_activities": []})
        assert targeted.status_code == 200, targeted.text
        repeated_targeted = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 10,
            "goal_dimension": "reasoning", "available_dimensions": ["reasoning"],
            "available_activities": []})
        assert repeated_targeted.status_code == 200, repeated_targeted.text
        assert repeated_targeted.json()["changed"] is False, repeated_targeted.json()
        targeted_plan = repeated_targeted.json()
        assert targeted_plan["plan_version"] == "plan-v3"
        reasoning_step = next(step for step in targeted_plan["steps"]
                              if step["activity_ref"]["kind"] == "core"
                              and step["exercise_type_id"] == "EX-02")
        launch_body = {"request_id": str(uuid.uuid4()), "session_id": sid}
        launch_url = f"/api/plans/{targeted_plan['plan_id']}/steps/{reasoning_step['step_id']}/launch"
        core_launch = client.post(launch_url, json=launch_body)
        assert core_launch.status_code == 200, core_launch.text
        core_replay = client.post(launch_url, json=launch_body)
        assert core_replay.status_code == 200, core_replay.text
        block_id = core_launch.json()["attempt_ref"]["id"]
        assert core_launch.json()["attempt_ref"]["kind"] == "core"
        assert core_replay.json()["attempt_ref"]["id"] == block_id
        assert client.get(f"/api/training/blocks/{block_id}").status_code == 200
        assert sum(1 for event in store.events(learner_id="demo-user")
                   if event["type"] == "training_block_started"
                   and event["payload"].get("training_block_id") == block_id) == 1
        # Read-time core completion comes from the canonical training block and item events.
        block_view = client.get(f"/api/training/blocks/{block_id}").json()
        internal_items = {item["item_id"]: item for item in make_training_bank(
            block_view["block"]["tier"], block_id, block_view["block"]["exercise_version"])}
        for item in block_view["exercise"]["items"]:
            canonical_item = internal_items[item["item_id"]]
            correct_choice = next(choice for choice in canonical_item["choices"]
                                  if evaluate(item["item_id"], choice, item_data=canonical_item)[0])
            trial = client.post("/api/trials", json={
                "event_id": str(uuid.uuid4()), "session_id": sid, "phase": "training",
                "exercise_id": "EX-02", "exercise_version": block_view["block"]["exercise_version"],
                "item_id": item["item_id"], "choice": correct_choice, "training_block_id": block_id,
                "response_time_ms": 1200,
            })
            assert trial.status_code == 200, trial.text
            current_block = client.get(f"/api/training/blocks/{block_id}").json()["block"]
            if current_block["status"] == "completed":
                break
        from backend.app.plan_v3 import refresh_plan_execution_status, canonical_outcome_reference, core_version
        projected_core = refresh_plan_execution_status(store, targeted_plan)
        projected_step = next(step for step in projected_core["steps"] if step["step_id"] == reasoning_step["step_id"])
        assert projected_step["execution_status"] == "completed", projected_step
        assert projected_step["completion_source"] == "canonical_core_training_block", projected_step
        assert projected_step["completion_references"], projected_step

        def make_core_state(suffix, interactions):
            test_block = f"plan-test-{suffix}"
            version = core_version("EX-01")
            store.create_training_block(test_block, "demo-user", sid, "tier-1", version, "EX-01", "working_memory")
            start_id = str(uuid.uuid4())
            start_payload = {"event_id": start_id, "session_id": sid, "learner_id": "demo-user",
                             "training_block_id": test_block, "exercise_id": "EX-01",
                             "exercise_version": version, "item_ids": ["i1", "i2"]}
            store.add_event(start_id, sid, "training_block_started", start_payload)
            for index, item_id in enumerate(("i1", "i2")):
                if index not in interactions:
                    continue
                trial_id = str(uuid.uuid4())
                payload = {"event_id": trial_id, "session_id": sid, "learner_id": "demo-user",
                           "event_type": "training_trial_completed", "phase": "training",
                           "exercise_id": "EX-01", "training_block_id": test_block,
                           "item_id": item_id, "interaction": interactions[index]}
                store.add_event(trial_id, sid, "training_trial_completed", payload,
                                training_block_id=test_block)
            return canonical_outcome_reference(store,
                {"kind": "core", "id": "EX-01", "version": version}, test_block)

        eligible_core = make_core_state("eligible", {0: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": False},
                                                       1: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": False}})
        assisted_core = make_core_state("assisted", {0: {"hint_count": 1, "replay_count": 0, "visibility_interrupted": False},
                                                       1: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": False}})
        interrupted_core = make_core_state("interrupted", {0: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": False},
                                                             1: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": True}})
        in_progress_core = make_core_state("in-progress", {0: {"hint_count": 0, "replay_count": 0, "visibility_interrupted": False}})
        assert eligible_core["status"] == "completed" and eligible_core["adaptive_eligible"] is True
        assert assisted_core["status"] == "completed" and assisted_core["assisted"] is True
        assert assisted_core["excluded_from_unassisted"] is True and assisted_core["adaptive_eligible"] is False
        assert interrupted_core["status"] == "interrupted" and interrupted_core["adaptive_eligible"] is False
        assert in_progress_core["status"] == "in_progress"
        # Hybrid completion stays playable but keeps the canonical assisted/exclusion labels.
        from backend.app.hybrid_activities import CATALOG, HYBRID_EVALUATION_VERSION, generate
        from backend.app.hybrid_store import create_attempt, save_outcome
        from backend.app.plan_v3 import launch_request_fingerprint
        hybrid_id = "plan-hy-assisted"
        hybrid_version = CATALOG["HY-01"]["activity_version"]
        hybrid_seed = "plan-smoke-assisted"
        hybrid_event_id = str(uuid.uuid4())
        hybrid_config = generate("HY-01", hybrid_seed, "training", "tier-1", hybrid_version)
        hybrid_payload = {"event_type": "hybrid_attempt_started", "attempt_id": hybrid_id,
                          "session_id": sid, "learner_id": "demo-user", "activity_id": "HY-01",
                          "activity_version": hybrid_version, "mode": "training",
                          "config_version": CATALOG["HY-01"]["config_version"],
                          "difficulty_tier": "tier-1", "seed": hybrid_seed}
        create_attempt(store, {"attempt_id": hybrid_id, "learner_id": "demo-user", "session_id": sid,
            "activity_id": "HY-01", "activity_version": hybrid_version, "mode": "training",
            "config_version": CATALOG["HY-01"]["config_version"], "difficulty_tier": "tier-1",
            "seed": hybrid_seed, "config": hybrid_config, "event_id": hybrid_event_id,
            "event_payload": hybrid_payload})
        outcome_ids = [str(uuid.uuid4())]
        save_outcome(store, {"attempt_id": hybrid_id, "session_id": sid, "learner_id": "demo-user",
            "activity_id": "HY-01", "activity_version": hybrid_version,
            "evaluation_version": HYBRID_EVALUATION_VERSION, "completion_state": "completed",
            "assisted": True, "excluded_from_unassisted": True, "outcomes": {"complete": True},
            "evidence_ids": outcome_ids, "limitations": []})
        alias_for_projection = str(uuid.uuid4())
        hy_step_id = "hy-assisted-step"
        from backend.app.plan_v3 import _reserve_launch, refresh_plan_execution_status
        _reserve_launch(store, {"request_id": alias_for_projection, "learner_id": "demo-user", "session_id": sid,
            "plan_id": targeted_plan["plan_id"], "step_id": hy_step_id, "activity_kind": "hybrid",
            "activity_id": "HY-01", "activity_version": hybrid_version,
            "payload_fingerprint": launch_request_fingerprint({"step": hy_step_id}), "attempt_id": hybrid_id,
            "start_event_id": hybrid_event_id, "status": "started",
            "destination_json": json.dumps({"kind": "hybrid", "id": "HY-01"}),
            "created_at": utc_now(), "updated_at": utc_now()})
        hy_plan = {"plan_id": targeted_plan["plan_id"], "steps": [{"step_id": hy_step_id,
            "status": "in_progress", "activity_ref": {"kind": "hybrid", "id": "HY-01", "version": hybrid_version}}]}
        hy_projection = refresh_plan_execution_status(store, hy_plan)["steps"][0]
        assert hy_projection["execution_status"] == "completed", hy_projection
        assert hy_projection["assisted"] is True and hy_projection["excluded_from_unassisted"] is True, hy_projection
        assert hy_projection["adaptive_eligible"] is False, hy_projection
        assert hy_projection["completion_references"] == outcome_ids, hy_projection
        # A new client request id aliases the same immutable step mapping; it cannot be reused elsewhere.
        alias_id = str(uuid.uuid4())
        aliased = client.post(launch_url, json={"request_id": alias_id, "session_id": sid})
        assert aliased.status_code == 200 and aliased.json()["attempt_ref"]["id"] == block_id, aliased.text
        assert aliased.json()["idempotent_replay"] is True, aliased.json()
        from backend.app.plan_v3 import _reserve_launch
        from backend.app.storage import utc_now
        try:
            _reserve_launch(store, {
                "request_id": alias_id, "learner_id": "demo-user", "session_id": sid,
                "plan_id": targeted_plan["plan_id"], "step_id": "different-step",
                "activity_kind": "core", "activity_id": "EX-02", "activity_version": "other-version",
                "payload_fingerprint": "different-payload", "attempt_id": str(uuid.uuid4()),
                "start_event_id": str(uuid.uuid4()), "status": "pending",
                "destination_json": json.dumps({"kind": "core", "id": "EX-02"}),
                "created_at": utc_now(), "updated_at": utc_now(),
            })
            raise AssertionError("an alias request id must not be reusable for another step")
        except ValueError as error:
            assert "different" in str(error), error
        from backend.app.plan_v2 import reconcile_plan
        reconciled = reconcile_plan(store, {"kind": "budget_changed", "reference": "constraint-inheritance"},
                                    session_id=sid)
        assert reconciled["availability"]["requested"] == ["reasoning"], reconciled["availability"]
        assert reconciled["availability"]["requested_activities_applied"] is True
        assert reconciled["availability"]["requested_activities"] == []
        latest_after_reconcile = store.latest_plan("demo-user")
        assert latest_after_reconcile["availability"]["requested"] == ["reasoning"]
        assert latest_after_reconcile["availability"]["requested_activities"] == []

        # 4. An exact retry of the accepted trial must not append another revision.
        before_retry = len([e for e in store.events(learner_id="demo-user")
                            if e["type"] in {"training_plan_revised", "training_plan_unchanged"}])
        assert client.post("/api/trials", json=last_body).json()["replayed"] is True
        after_retry = len([e for e in store.events(learner_id="demo-user")
                           if e["type"] in {"training_plan_revised", "training_plan_unchanged"}])
        assert after_retry == before_retry, (before_retry, after_retry)

        # 5. Repeating one trigger is idempotent.
        trigger = {"kind": "budget_changed", "reference": "idempotency-probe"}
        once = reconcile_plan(store, trigger, session_id=sid)
        twice = reconcile_plan(store, trigger, session_id=sid)
        assert not once.get("skipped"), once
        assert twice["skipped"] and twice["reason"] == "duplicate_trigger", twice

        # 6. A tiny budget is never silently overbooked and offers a budget adjustment.
        tiny = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 4}).json()
        assert tiny["planned_minutes"] <= 4, tiny
        assert len(tiny["steps"]) <= 1, tiny["steps"]
        assert tiny["budget_adjustment"] is not None, tiny
        assert tiny["budget_adjustment"]["suggested_budget_minutes"] > 4, tiny["budget_adjustment"]

        # 7. Dropped steps are superseded rather than silently deleted.
        assert isinstance(latest.get("superseded_steps"), list), latest
        final = store.latest_plan("demo-user")
        history = client.get("/api/plans/demo-user").json()
        assert len(history["history"]) >= 3, len(history["history"])
        assert all(row.get("plan_version") == "plan-v3" for row in history["history"]), history["history"]

        # 8. A goal change also reconciles the active plan.
        goal = client.post("/api/preferences", json={"session_id": sid, "dashboard_mode": "analytics",
                                                     "goal_dimension": "working_memory"})
        assert goal.status_code == 200, goal.text
        goal_events = [e for e in store.events(learner_id="demo-user")
                       if e["type"] in {"training_plan_revised", "training_plan_unchanged"}
                       and (e["payload"] or {}).get("plan_trigger", {}).get("kind") == "goal_changed"]
        assert goal_events, "a goal change must reconcile the active plan"
        repeated_goal_plan_1 = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
        repeated_goal_plan_2 = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
        assert repeated_goal_plan_1.status_code == repeated_goal_plan_2.status_code == 200
        assert repeated_goal_plan_2.json()["changed"] is False, repeated_goal_plan_2.json()

        from backend.app.lifecycle_service import export_learner_data, delete_learner_data
        from backend.app import speech_service
        exported = export_learner_data(store)
        assert any(row["request_id"] == alias_id for row in exported["plan_step_launch_request_aliases"])
        speech_service._store_cached_audio(("demo-user", sid, 0, "smoke-revision", "EX-01", "smoke-hash",
                                            "Bella", 1.0, speech_service.SPEECH_CACHE_VERSION,
                                            speech_service.MODEL_ID), "demo-user", b"synthetic-wav")
        deletion = delete_learner_data(store)
        assert deletion["deleted_row_counts"]["plan_step_launch_request_aliases"] >= 1, deletion
        assert deletion["speech_cache_entries_cleared"] == 1, deletion
        db = store.connect()
        try:
            assert db.execute("SELECT COUNT(*) FROM plan_step_launch_aliases").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM plan_step_launches").fetchone()[0] == 0
        finally:
            db.close()

print("PASS plan-v2: automatic baseline/goal reconciliation, exact-retry and trigger idempotency, "
      "step lifecycle, activity-specific estimates, bounded budgets and explicit budget adjustment")
