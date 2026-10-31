"""Local export and scoped deletion for canonical AI4BRAIN demo-user data."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

LIFECYCLE_VERSION = "local-data-lifecycle-v1"
EXPORT_SCHEMA_VERSION = "ai4brain-export-v1"
IMMUTABILITY_TRIGGERS = (
    "events_no_update", "events_no_delete", "snapshots_no_update", "snapshots_no_delete",
    "decisions_no_update", "decisions_no_delete", "hybrid_events_no_update", "hybrid_events_no_delete",
    "hybrid_assistance_no_update", "hybrid_assistance_no_delete", "hybrid_outcomes_no_update", "hybrid_outcomes_no_delete",
)
DELETE_GUARD_TRIGGERS = (
    "events_no_delete", "snapshots_no_delete", "decisions_no_delete",
    "hybrid_events_no_delete", "hybrid_assistance_no_delete", "hybrid_outcomes_no_delete",
)
RETENTION_NOTICE = (
    "Data remains in the local AI4BRAIN SQLite store until the learner requests deletion. "
    "The POC has no automatic retention expiry."
)
UNCERTAINTY_NOTICE = (
    "Scores and recommendations are preliminary, task-specific, and high uncertainty. "
    "Missing evidence remains unassessed; this export is not a clinical assessment."
)
REMOTE_NOTICE = (
    "Remote coaching is optional and requires explicit per-request opt-in. Camera and microphone are not required."
)


class LifecycleError(ValueError):
    """Lifecycle operation cannot safely meet its scope."""


def _decode_rows(rows: list[sqlite3.Row], json_fields: dict[str, tuple[str, ...]] | None = None) -> list[dict[str, Any]]:
    json_fields = json_fields or {}
    result = []
    for row in rows:
        item = dict(row)
        for column, keys in json_fields.items():
            if column in item:
                raw = item.pop(column)
                item[keys[0]] = json.loads(raw) if raw is not None else None
                if len(keys) > 1:
                    item[keys[1]] = raw
        result.append(item)
    return result


def _preferences(sessions: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    if sessions:
        latest = max(sessions, key=lambda row: (row["started_at"], row["id"]))
        prefs = {"dashboard_mode": latest["dashboard_mode"], "goal_dimension": latest.get("goal_dimension")}
    else:
        prefs = {"dashboard_mode": "analytics", "goal_dimension": None}
    # Match Store.current_preferences: explicit preference events outlive a later default session.
    for event in events:
        payload = event["payload"]
        if event["type"] == "dashboard_mode_changed" and payload.get("dashboard_mode") in {"analytics", "rpg"}:
            prefs["dashboard_mode"] = payload["dashboard_mode"]
        elif event["type"] == "user_goal_updated" and "goal_dimension" in payload:
            prefs["goal_dimension"] = payload["goal_dimension"]
    return prefs


def _original_activity_records(db: sqlite3.Connection, learner_id: str) -> dict[str, list[dict[str, Any]]]:
    """Scope original-activity records through the authoritative session owner."""
    result = {}
    available = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ("hybrid_attempts", "hybrid_events", "hybrid_assistance", "hybrid_outcomes",
                  "crystal_attempts", "crystal_events", "crystal_outcomes"):
        if table not in available:
            continue
        attempts = table.split("_", 1)[0] + "_attempts"
        is_attempt = table == attempts
        alias = "h" if is_attempt else "r"
        join = "" if is_attempt else f"{table} r JOIN "
        on = "" if is_attempt else " ON r.attempt_id=h.attempt_id"
        rows = db.execute(
            f"SELECT {alias}.* FROM {join}{attempts} h{on} JOIN sessions s ON s.id=h.session_id "
            "WHERE s.learner_id=? ORDER BY h.started_at,h.attempt_id", (learner_id,),
        ).fetchall()
        decoded = []
        for row in rows:
            item = dict(row)
            for key in tuple(item):
                if key.endswith("_json"):
                    item[key[:-5]] = json.loads(item.pop(key))
            for key in ("assisted", "excluded_from_unassisted", "correct"):
                if key in item:
                    item[key] = bool(item[key])
            decoded.append(item)
        result[table] = decoded
    return result


def _learner_claim_rows(db: sqlite3.Connection, learner_id: str) -> list[sqlite3.Row]:
    """Resolve claims through learner-owned sessions and canonical evidence."""
    return db.execute(
        "SELECT c.* FROM collaboration_claims c WHERE "
        "(c.session_id IS NOT NULL AND c.session_id IN (SELECT id FROM sessions WHERE learner_id=?)) "
        "OR (c.session_id IS NULL AND c.source_event_id IS NOT NULL AND c.source_event_id IN "
        "(SELECT e.event_id FROM events e JOIN sessions s ON s.id=e.session_id WHERE s.learner_id=?)) "
        "OR (c.session_id IS NULL AND c.source_event_id IS NULL AND c.evidence_event_id IS NOT NULL "
        "AND c.evidence_event_id IN (SELECT e.event_id FROM events e JOIN sessions s ON s.id=e.session_id WHERE s.learner_id=?)) "
        "OR (c.session_id IS NULL AND c.source_event_id IS NULL AND c.evidence_event_id IS NULL "
        "AND EXISTS (SELECT 1 FROM events e JOIN sessions s ON s.id=e.session_id "
        "WHERE s.learner_id=? AND json_extract(e.payload_json,'$.opportunity_id')=c.opportunity_id)) "
        "ORDER BY c.created_at,c.claim_id",
        (learner_id, learner_id, learner_id, learner_id),
    ).fetchall()


def export_learner_data(store: Any, learner_id: str = "demo-user") -> dict[str, Any]:
    """Return a consistent snapshot of the learner's canonical and derived local records."""
    if not isinstance(learner_id, str) or not learner_id.strip():
        raise LifecycleError("learner_id is required")
    from .plan_v3 import _ensure_launch_table, plan_launches_for_export, plan_launch_aliases_for_export
    _ensure_launch_table(store)
    with closing(store.connect()) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        sessions = [dict(row) for row in db.execute(
            "SELECT id,learner_id,started_at,status,dashboard_mode,goal_dimension FROM sessions WHERE learner_id=? ORDER BY started_at,id",
            (learner_id,),
        ).fetchall()]
        ids = [row["id"] for row in sessions]
        if ids:
            marks = ",".join("?" for _ in ids)
            raw_events = db.execute(
                f"SELECT e.event_id,e.session_id,e.type,e.payload_json,e.created_at FROM events e "
                f"WHERE e.session_id IN ({marks}) ORDER BY e.created_at,e.event_id", ids,
            ).fetchall()
        else:
            raw_events = []
        events = []
        for row in raw_events:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            events.append(item)
        if ids:
            marks = ",".join("?" for _ in ids)
            raw_submissions = db.execute(
                f"SELECT s.event_id,s.submission_json FROM event_submissions s "
                f"JOIN events e ON e.event_id=s.event_id WHERE e.session_id IN ({marks}) ORDER BY e.created_at,s.event_id", ids,
            ).fetchall()
        else:
            raw_submissions = []
        event_submissions = [{"event_id": row["event_id"], "submission": json.loads(row["submission_json"])}
                             for row in raw_submissions]
        snapshots = [dict(row) for row in db.execute(
            "SELECT id,learner_id,scoring_version,dimension,index_0_100,uncertainty_status,evidence_count,completed,"
            "evidence_ids_json,interrupted_count,created_at FROM profile_snapshots WHERE learner_id=? ORDER BY rowid",
            (learner_id,),
        ).fetchall()]
        for item in snapshots:
            item["completed"] = bool(item["completed"])
            item["evidence_ids"] = json.loads(item.pop("evidence_ids_json"))
        recommendations = _decode_rows(db.execute(
            "SELECT id,learner_id,snapshot_id,policy_version,action,exercise_id,tier,reason_codes_json,evidence_ids_json,created_at "
            "FROM recommendations WHERE learner_id=? ORDER BY rowid", (learner_id,),
        ).fetchall(), {"reason_codes_json": ("reason_codes",), "evidence_ids_json": ("evidence_ids",)})
        blocks = [dict(row) for row in db.execute(
            "SELECT block_id,learner_id,session_id,tier,exercise_version,status,started_at,exercise_id,dimension "
            "FROM training_blocks WHERE learner_id=? ORDER BY rowid", (learner_id,),
        ).fetchall()]
        decisions = _decode_rows(db.execute(
            "SELECT block_id,learner_id,session_id,old_tier,new_tier,action,rule_version,successes,trial_count,valid_trial_count,"
            "rationale,reason_codes_json,evidence_ids_json,created_at FROM difficulty_decisions WHERE learner_id=? ORDER BY rowid",
            (learner_id,),
        ).fetchall(), {"reason_codes_json": ("reason_codes",), "evidence_ids_json": ("evidence_ids",)})
        plans = _decode_rows(db.execute(
            "SELECT plan_id,learner_id,profile_snapshot_id,policy_version,goal,budget_minutes,estimated_time_minutes,"
            "reason_codes_json,rationale,steps_json,evidence_ids_json,features_json,alternatives_json,decision_fingerprint,"
            "status,created_at,plan_extra_json FROM training_plans WHERE learner_id=? ORDER BY rowid", (learner_id,),
        ).fetchall(), {
            "reason_codes_json": ("reason_codes",), "steps_json": ("steps",), "evidence_ids_json": ("evidence_ids",),
            "features_json": ("features",), "alternatives_json": ("alternatives",),
            "decision_fingerprint": ("decision_fingerprint",),
            "plan_extra_json": ("plan_extra", "plan_extra_json"),
        })
        coach_turns = _decode_rows(db.execute(
            "SELECT request_id,learner_id,session_id,subject_exercise_id,subject_dimension,subject_source,"
            "provider_requested,provider_used,model,coach_version,payload_hash,status,message,evidence_revision,"
            "request_json,response_json,progress_json,error_code,created_at,updated_at FROM coach_turns "
            "WHERE learner_id=? ORDER BY created_at,request_id", (learner_id,),
        ).fetchall(), {"request_json": ("request",), "response_json": ("response",), "progress_json": ("progress",)})
        coach_conversations = [dict(row) for row in db.execute(
            "SELECT session_id,learner_id,subject_exercise_id,provider,consent_recorded,updated_at "
            "FROM coach_conversations WHERE learner_id=? ORDER BY updated_at,session_id", (learner_id,),
        ).fetchall()]
        collaboration_claims = [dict(row) for row in _learner_claim_rows(db, learner_id)]
        plan_step_launches = plan_launches_for_export(db, learner_id)
        plan_step_launch_request_aliases = plan_launch_aliases_for_export(db, learner_id)
        original_activities = _original_activity_records(db, learner_id)
        db.commit()
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "lifecycle_version": LIFECYCLE_VERSION,
        "learner_id": learner_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "notices": {
            "retention": RETENTION_NOTICE,
            "uncertainty": UNCERTAINTY_NOTICE,
            "remote_processing": REMOTE_NOTICE,
        },
        "sessions": sessions,
        "events": events,
        "event_submissions": event_submissions,
        "profile_snapshots": snapshots,
        "recommendations": recommendations,
        "training_blocks": blocks,
        "difficulty_decisions": decisions,
        "training_plans": plans,
        "plan_step_launches": plan_step_launches,
        "plan_step_launch_request_aliases": plan_step_launch_request_aliases,
        "coach_turns": coach_turns,
        "coach_conversations": coach_conversations,
        "collaboration_claims": collaboration_claims,
        **original_activities,
        "preferences": _preferences(sessions, events),
    }


def _delete_learner_data(store: Any, learner_id: str = "demo-user") -> dict[str, Any]:
    """Atomically delete one learner's local rows while restoring immutable triggers.

    No database/file is unlinked. The only temporarily removed triggers are the
    canonical DELETE guards, and their exact saved SQL is restored before
    commit. A failure rolls back both row changes and trigger DDL.
    """
    if not isinstance(learner_id, str) or not learner_id.strip():
        raise LifecycleError("learner_id is required")
    from .plan_v3 import _ensure_launch_table, delete_plan_launches
    _ensure_launch_table(store)
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO learner_lifecycle(learner_id,generation,deleting,updated_at) VALUES(?,?,1,?) "
            "ON CONFLICT(learner_id) DO UPDATE SET generation=generation+1,deleting=1,updated_at=excluded.updated_at",
            (learner_id, 0, datetime.now(timezone.utc).isoformat()),
        )
        required_triggers = IMMUTABILITY_TRIGGERS
        crystal_present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='crystal_attempts'").fetchone()
        if crystal_present:
            required_triggers += ("crystal_events_no_update", "crystal_events_no_delete",
                                  "crystal_outcomes_no_update", "crystal_outcomes_no_delete")
        delete_guards = tuple(name for name in required_triggers if name.endswith("_no_delete"))
        trigger_marks = ",".join("?" for _ in required_triggers)
        trigger_rows = db.execute(
            f"SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN ({trigger_marks}) ORDER BY name",
            required_triggers,
        ).fetchall()
        trigger_sql = {row["name"]: row["sql"] for row in trigger_rows}
        if set(trigger_sql) != set(required_triggers) or any(not sql for sql in trigger_sql.values()):
            db.rollback()
            raise LifecycleError("canonical immutability triggers are missing; deletion was not started")
        trigger_before = dict(trigger_sql)
        try:
            session_ids = [row["id"] for row in db.execute("SELECT id FROM sessions WHERE learner_id=?", (learner_id,)).fetchall()]
            counts = {}
            original_activities = _original_activity_records(db, learner_id)
            counts.update({table: len(rows) for table, rows in original_activities.items()})
            for table in ("difficulty_decisions", "events", "event_submissions", "recommendations", "training_plans",
                          "profile_snapshots", "training_blocks", "sessions", "coach_turns",
                          "coach_conversations"):
                if table == "events":
                    if session_ids:
                        marks = ",".join("?" for _ in session_ids)
                        counts[table] = db.execute(f"SELECT COUNT(*) FROM events WHERE session_id IN ({marks})", session_ids).fetchone()[0]
                    else:
                        counts[table] = 0
                elif table == "event_submissions":
                    if session_ids:
                        marks = ",".join("?" for _ in session_ids)
                        counts[table] = db.execute(
                            f"SELECT COUNT(*) FROM event_submissions s JOIN events e ON e.event_id=s.event_id "
                            f"WHERE e.session_id IN ({marks})", session_ids,
                        ).fetchone()[0]
                    else:
                        counts[table] = 0
                else:
                    counts[table] = db.execute(f"SELECT COUNT(*) FROM {table} WHERE learner_id=?", (learner_id,)).fetchone()[0]
            counts["collaboration_claims"] = len(_learner_claim_rows(db, learner_id))
            counts["plan_step_launches"] = db.execute(
                "SELECT COUNT(*) FROM plan_step_launches WHERE learner_id=?", (learner_id,)).fetchone()[0]
            counts["plan_step_launch_request_aliases"] = db.execute(
                "SELECT COUNT(*) FROM plan_step_launch_aliases WHERE learner_id=?", (learner_id,)).fetchone()[0]
            for name in delete_guards:
                db.execute(f'DROP TRIGGER "{name}"')
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                db.execute(
                    "DELETE FROM collaboration_claims WHERE claim_id IN "
                    "(SELECT c.claim_id FROM collaboration_claims c WHERE "
                    "(c.session_id IS NOT NULL AND c.session_id IN (" + marks + ")) OR "
                    "(c.session_id IS NULL AND c.source_event_id IS NOT NULL AND c.source_event_id IN "
                    "(SELECT e.event_id FROM events e WHERE e.session_id IN (" + marks + "))) OR "
                    "(c.session_id IS NULL AND c.source_event_id IS NULL AND c.evidence_event_id IS NOT NULL "
                    "AND c.evidence_event_id IN (SELECT e.event_id FROM events e WHERE e.session_id IN (" + marks + "))) OR "
                    "(c.session_id IS NULL AND c.source_event_id IS NULL AND c.evidence_event_id IS NULL "
                    "AND EXISTS (SELECT 1 FROM events e WHERE e.session_id IN (" + marks + ") "
                    "AND json_extract(e.payload_json,'$.opportunity_id')=c.opportunity_id)))",
                    [*session_ids, *session_ids, *session_ids, *session_ids],
                )
                for table in ("hybrid_assistance", "hybrid_outcomes", "hybrid_events"):
                    db.execute(f"DELETE FROM {table} WHERE attempt_id IN "
                               f"(SELECT attempt_id FROM hybrid_attempts WHERE session_id IN ({marks}))", session_ids)
                db.execute(f"DELETE FROM hybrid_attempts WHERE session_id IN ({marks})", session_ids)
                if crystal_present:
                    for table in ("crystal_outcomes", "crystal_events"):
                        db.execute(f"DELETE FROM {table} WHERE attempt_id IN "
                                   f"(SELECT attempt_id FROM crystal_attempts WHERE session_id IN ({marks}))", session_ids)
                    db.execute(f"DELETE FROM crystal_attempts WHERE session_id IN ({marks})", session_ids)
            db.execute("DELETE FROM difficulty_decisions WHERE learner_id=?", (learner_id,))
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                db.execute(f"DELETE FROM event_submissions WHERE event_id IN (SELECT event_id FROM events WHERE session_id IN ({marks}))", session_ids)
                db.execute(f"DELETE FROM events WHERE session_id IN ({marks})", session_ids)
            db.execute("DELETE FROM recommendations WHERE learner_id=?", (learner_id,))
            delete_plan_launches(store, db, learner_id)
            db.execute("DELETE FROM training_plans WHERE learner_id=?", (learner_id,))
            db.execute("DELETE FROM coach_turns WHERE learner_id=?", (learner_id,))
            db.execute("DELETE FROM coach_conversations WHERE learner_id=?", (learner_id,))
            db.execute("DELETE FROM profile_snapshots WHERE learner_id=?", (learner_id,))
            db.execute("DELETE FROM training_blocks WHERE learner_id=?", (learner_id,))
            db.execute("DELETE FROM sessions WHERE learner_id=?", (learner_id,))
            for name in delete_guards:
                db.execute(trigger_before[name])
            trigger_after = {
                row["name"]: row["sql"] for row in db.execute(
                    f"SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN ({trigger_marks})",
                    required_triggers,
                ).fetchall()
            }
            if trigger_after != trigger_before:
                raise LifecycleError("immutability trigger definitions did not restore exactly")
            db.execute(
                "UPDATE learner_lifecycle SET deleting=0,updated_at=? WHERE learner_id=?",
                (datetime.now(timezone.utc).isoformat(), learner_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {
        "learner_id": learner_id,
        "deleted": True,
        "deleted_row_counts": counts,
        "immutability_triggers_preserved": True,
        "database_file_preserved": True,
        "other_learners_included": False,
        "lifecycle_version": LIFECYCLE_VERSION,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def delete_learner_data(store: Any, learner_id: str = "demo-user") -> dict[str, Any]:
    """Delete one learner while serializing late coaching side effects."""
    lock = getattr(store, "coach_lifecycle_lock", None)
    if lock is None:
        result = _delete_learner_data(store, learner_id)
        from .graph_service import clear_graph_cache_for_learner
        result["graph_snapshots_cleared"] = clear_graph_cache_for_learner(learner_id, store)
    else:
        with lock:
            result = _delete_learner_data(store, learner_id)
            from .graph_service import clear_graph_cache_for_learner
            result["graph_snapshots_cleared"] = clear_graph_cache_for_learner(learner_id, store)
    from .speech_service import clear_speech_cache_for_learner
    result["speech_cache_entries_cleared"] = clear_speech_cache_for_learner(learner_id)
    return result
