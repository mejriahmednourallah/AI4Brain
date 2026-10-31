"""Temporary-SQLite smoke for lifecycle export, atomic deletion, and trigger safety."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["NEO4J_ENABLED"] = "false"

from backend.app.lifecycle_service import delete_learner_data, export_learner_data  # noqa: E402
from backend.app.storage import Store, utc_now  # noqa: E402


def add(store: Store, session_id: str, event_type: str, learner_id: str = "demo-user", submission: dict | None = None, **fields):
    event_id = fields.pop("event_id", str(uuid.uuid4()))
    payload = {
        "event_id": event_id, "session_id": session_id, "learner_id": learner_id,
        "event_type": event_type, "sample_data": False, "recorded_at": utc_now(), **fields,
    }
    return store.add_event(event_id, session_id, event_type, payload, submission=submission)[0]


def trigger_sql(store: Store):
    with closing(store.connect()) as db:
        return {r["name"]: r["sql"] for r in db.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN "
            "('events_no_update','events_no_delete','snapshots_no_update','snapshots_no_delete','decisions_no_update','decisions_no_delete') ORDER BY name"
        ).fetchall()}


def row_counts(store: Store, learner_id: str):
    with closing(store.connect()) as db:
        counts = {}
        for table in ("sessions", "profile_snapshots", "recommendations", "training_blocks",
                      "difficulty_decisions", "training_plans"):
            counts[table] = db.execute(f"SELECT COUNT(*) FROM {table} WHERE learner_id=?", (learner_id,)).fetchone()[0]
        counts["events"] = db.execute(
            "SELECT COUNT(*) FROM events e JOIN sessions s ON s.id=e.session_id WHERE s.learner_id=?", (learner_id,)
        ).fetchone()[0]
        counts["event_submissions"] = db.execute(
            "SELECT COUNT(*) FROM event_submissions es JOIN events e ON e.event_id=es.event_id "
            "JOIN sessions s ON s.id=e.session_id WHERE s.learner_id=?", (learner_id,)
        ).fetchone()[0]
        return counts


def main():
    with tempfile.TemporaryDirectory(prefix="ai4brain-lifecycle-") as tmp:
        store = Store(Path(tmp) / "lifecycle.sqlite3")
        learner = store.create_session("demo-session", "demo-user")
        other = store.create_session("other-session", "other-learner")
        store.set_preferences(learner["id"], "rpg", "planning")
        store.set_preferences(other["id"], "analytics", "reasoning")

        demo_evidence = add(store, learner["id"], "assessment_trial_completed",
                            submission={"item_id": "baseline-item-01", "answer": "choice-a", "interaction": {"hint_count": 0}},
                            phase="baseline", exercise_id="EX-02")
        other_evidence = add(store, other["id"], "assessment_trial_completed", learner_id="other-learner",
                             submission={"item_id": "other-item-01", "answer": "choice-b"},
                             phase="baseline", exercise_id="EX-02")
        snapshot = {
            "id": "demo-snapshot", "learner_id": "demo-user", "scoring_version": "score-v1",
            "dimension": "reasoning", "index_0_100": 50.0, "uncertainty_status": "PRELIMINARY_HIGH_UNCERTAINTY",
            "evidence_count": 1, "completed": False, "evidence_ids": [demo_evidence["event_id"]],
            "interrupted_count": 0, "created_at": utc_now(),
        }
        other_snapshot = {**snapshot, "id": "other-snapshot", "learner_id": "other-learner",
                          "evidence_ids": [other_evidence["event_id"]]}
        store.save_snapshot(snapshot)
        store.save_snapshot(other_snapshot)
        store.save_recommendation({
            "id": "demo-rec", "learner_id": "demo-user", "action": "targeted_training",
            "exercise_id": "EX-02", "tier": "tier-1", "reason_codes": ["evidence-backed"],
            "evidence_ids": [demo_evidence["event_id"]], "policy_version": "recommendation-v1",
            "created_at": utc_now(),
        }, snapshot["id"])
        store.save_recommendation({
            "id": "other-rec", "learner_id": "other-learner", "action": "targeted_training",
            "exercise_id": "EX-02", "tier": "tier-1", "reason_codes": ["other"],
            "evidence_ids": [other_evidence["event_id"]], "policy_version": "recommendation-v1",
            "created_at": utc_now(),
        }, other_snapshot["id"])
        store.create_training_block("demo-block", "demo-user", learner["id"], "tier-1", "training-v1")
        store.create_training_block("other-block", "other-learner", other["id"], "tier-1", "training-v1")
        store.save_decision_once({
            "block_id": "demo-block", "learner_id": "demo-user", "session_id": learner["id"],
            "old_tier": "tier-1", "new_tier": "tier-2", "action": "promote", "rule_version": "difficulty-v1",
            "successes": 4, "trial_count": 4, "valid_trial_count": 4, "rationale": "Four eligible trials.",
            "reason_codes": ["four_valid_trials"], "evidence_ids": [demo_evidence["event_id"]],
            "created_at": utc_now(), "event_id": "demo-difficulty-event", "dimension": "reasoning",
            "exercise_id": "EX-02", "success_definition": "correct",
        })
        store.save_plan({
            "plan_id": "demo-plan", "learner_id": "demo-user", "profile_snapshot_id": snapshot["id"],
            "policy_version": "training-plan-v1", "goal": "planning", "budget_minutes": 10,
            "estimated_time_minutes": 8, "reason_codes": ["saved-evidence"], "rationale": "A local plan.",
            "steps": [{"dimension_id": "reasoning", "exercise_id": "EX-02"}],
            "evidence_ids": [demo_evidence["event_id"]], "features": {"uncertainty": "high"},
            "alternatives": [], "decision_fingerprint": ["a", "b"], "status": "active", "created_at": utc_now(),
        })
        store.save_plan({
            "plan_id": "other-plan", "learner_id": "other-learner", "profile_snapshot_id": other_snapshot["id"],
            "policy_version": "training-plan-v1", "goal": "reasoning", "budget_minutes": 10,
            "estimated_time_minutes": 8, "reason_codes": ["other"], "rationale": "Other learner plan.",
            "steps": [], "evidence_ids": [other_evidence["event_id"]], "features": {},
            "alternatives": [], "decision_fingerprint": [], "status": "active", "created_at": utc_now(),
        })

        exported = export_learner_data(store, "demo-user")
        assert exported["export_schema_version"] == "ai4brain-export-v1"
        assert exported["notices"]["retention"] and exported["notices"]["uncertainty"]
        assert exported["preferences"] == {"dashboard_mode": "rpg", "goal_dimension": "planning"}
        assert len(exported["events"]) >= 4 and len(exported["profile_snapshots"]) == 1
        assert exported["event_submissions"] == [{"event_id": demo_evidence["event_id"],
                                                    "submission": {"item_id": "baseline-item-01", "answer": "choice-a", "interaction": {"hint_count": 0}}}]
        assert len(exported["recommendations"]) == len(exported["training_blocks"]) == 1
        assert len(exported["difficulty_decisions"]) == len(exported["training_plans"]) == 1
        assert exported["events"][1]["payload"]["event_id"] == exported["events"][1]["event_id"]

        triggers_before = trigger_sql(store)
        assert set(triggers_before) == {"events_no_update", "events_no_delete", "snapshots_no_update", "snapshots_no_delete", "decisions_no_update", "decisions_no_delete"}
        # Inject a late failure after earlier deletes have run. SQLite must roll back rows and DDL.
        with closing(store.connect()) as db:
            db.execute("CREATE TRIGGER smoke_abort_training_block_delete BEFORE DELETE ON training_blocks "
                       "BEGIN SELECT RAISE(ABORT,'intentional smoke failure'); END")
        counts_before_failure = row_counts(store, "demo-user")
        try:
            delete_learner_data(store, "demo-user")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected injected late failure")
        assert row_counts(store, "demo-user") == counts_before_failure, "failed deletion must be atomic"
        assert trigger_sql(store) == triggers_before, "failure must preserve exact immutable trigger definitions"
        with closing(store.connect()) as db:
            db.execute("DROP TRIGGER smoke_abort_training_block_delete")

        result = delete_learner_data(store, "demo-user")
        assert result["deleted"] and result["immutability_triggers_preserved"] and result["database_file_preserved"]
        assert trigger_sql(store) == triggers_before, "successful deletion must restore exact trigger SQL"
        assert all(value == 0 for value in row_counts(store, "demo-user").values())
        assert result["deleted_row_counts"]["event_submissions"] == 1
        other_counts = row_counts(store, "other-learner")
        assert all(other_counts[key] > 0 for key in ("sessions", "events", "event_submissions", "profile_snapshots", "recommendations", "training_blocks", "training_plans")), "unrelated learner rows must survive"
        assert store.path.exists(), "deletion must not unlink the SQLite file"
        print("lifecycle smoke passed: exact local export, uncertainty/retention notices, atomic scoped deletion, immutable triggers preserved, unrelated learner retained")


if __name__ == "__main__":
    main()


