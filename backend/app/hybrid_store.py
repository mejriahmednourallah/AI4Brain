"""Persistence for hybrid-v1 attempts, events, assistance and outcomes.

Hybrid records live in their own append-only tables. They are never written to the
EX `events` table, so baseline indices, participation XP and dashboards are untouched.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from typing import Any

from .storage import Store, utc_now


class HybridConflict(ValueError):
    """Raised when an event id is reused with a different payload or ordering."""


def _identity(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("recorded_at", None)
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def create_attempt(store: Store, attempt: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM sessions WHERE id=?", (attempt["session_id"],)).fetchone():
            db.rollback()
            raise KeyError("session not found")
        # The client retries a start with the same event_id after an ambiguous
        # response. Resolve that identity before generating/inserting a new UUID.
        prior_start = db.execute("SELECT * FROM hybrid_events WHERE event_id=?", (attempt["event_id"],)).fetchone()
        if prior_start:
            prior_payload = json.loads(prior_start["payload_json"])
            prior_attempt = db.execute("SELECT * FROM hybrid_attempts WHERE attempt_id=?",
                                       (prior_payload.get("attempt_id"),)).fetchone()
            wanted_payload = dict(attempt["event_payload"])
            prior_identity = dict(prior_payload)
            wanted_identity = dict(wanted_payload)
            prior_identity.pop("attempt_id", None)
            wanted_identity.pop("attempt_id", None)
            same_attempt = bool(prior_attempt) and all(
                prior_attempt[key] == attempt[key]
                for key in ("learner_id", "session_id", "activity_id", "activity_version", "mode",
                            "config_version", "difficulty_tier", "seed")
            ) and prior_attempt["config_json"] == json.dumps(attempt["config"], sort_keys=True, separators=(",", ":"))
            if (prior_start["type"] != "hybrid_attempt_started" or not same_attempt
                    or _identity(prior_identity) != _identity(wanted_identity)):
                db.rollback()
                raise HybridConflict("start event_id already exists with a different configuration")
            db.commit()
            return dict(prior_attempt)
        existing = db.execute("SELECT * FROM hybrid_attempts WHERE attempt_id=?", (attempt["attempt_id"],)).fetchone()
        if existing:
            db.rollback()
            stored = dict(existing)
            if (any(stored[key] != attempt[key] for key in
                    ("learner_id", "session_id", "activity_id", "activity_version", "mode", "config_version",
                     "difficulty_tier", "seed"))
                    or stored["config_json"] != json.dumps(attempt["config"], sort_keys=True, separators=(",", ":"))):
                raise HybridConflict("attempt already exists with a different configuration")
            return stored
        db.execute(
            "INSERT INTO hybrid_attempts(attempt_id,learner_id,session_id,activity_id,activity_version,mode,"
            "config_version,difficulty_tier,seed,config_json,status,started_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'started', ?)",
            (attempt["attempt_id"], attempt["learner_id"], attempt["session_id"], attempt["activity_id"],
             attempt["activity_version"], attempt["mode"], attempt["config_version"], attempt["difficulty_tier"],
             attempt["seed"], json.dumps(attempt["config"], sort_keys=True, separators=(",", ":")), now))
        db.execute(
            "INSERT INTO hybrid_events(event_id,attempt_id,session_id,sequence,type,payload_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (attempt["event_id"], attempt["attempt_id"], attempt["session_id"], 0, "hybrid_attempt_started",
             json.dumps(attempt["event_payload"], sort_keys=True, separators=(",", ":")), now))
        db.commit()
    return get_attempt(store, attempt["attempt_id"])  # type: ignore[return-value]


def get_attempt(store: Store, attempt_id: str) -> dict[str, Any] | None:
    with closing(store.connect()) as db:
        row = db.execute("SELECT * FROM hybrid_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
    return dict(row) if row else None


def attempt_events(store: Store, attempt_id: str) -> list[dict[str, Any]]:
    with closing(store.connect()) as db:
        rows = db.execute("SELECT * FROM hybrid_events WHERE attempt_id=? ORDER BY sequence, event_id", (attempt_id,)).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]


def next_sequence(store: Store, attempt_id: str) -> int:
    with closing(store.connect()) as db:
        row = db.execute("SELECT COALESCE(MAX(sequence), -1) AS s FROM hybrid_events WHERE attempt_id=?", (attempt_id,)).fetchone()
    return int(row["s"]) + 1


def append_event(store: Store, attempt_id: str, session_id: str, sequence: int, event_type: str,
                 payload: dict[str, Any], event_id: str) -> tuple[dict[str, Any], bool]:
    """Append an immutable hybrid event. An exact retry returns the stored event."""
    body = dict(payload)
    body.setdefault("recorded_at", utc_now())
    identity = _identity(body)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    now = utc_now()
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT payload_json,session_id,type,sequence FROM hybrid_events WHERE event_id=?", (event_id,)).fetchone()
        if old:
            stored_payload = json.loads(old["payload_json"])
            if _identity(stored_payload) != identity or old["session_id"] != session_id or old["type"] != event_type:
                db.rollback()
                raise HybridConflict("event_id already exists with a different payload")
            db.commit()
            return {**stored_payload, "event_id": event_id, "sequence": int(old["sequence"]), "type": event_type}, True
        attempt = db.execute("SELECT session_id,status FROM hybrid_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if not attempt or attempt["session_id"] != session_id:
            db.rollback()
            raise KeyError("hybrid attempt not found for session")
        if attempt["status"] != "started":
            db.rollback()
            raise HybridConflict("hybrid attempt is already completed")
        taken = db.execute("SELECT event_id FROM hybrid_events WHERE attempt_id=? AND sequence=?", (attempt_id, sequence)).fetchone()
        if taken:
            db.rollback()
            raise HybridConflict("hybrid event sequence already recorded")
        try:
            db.execute("INSERT INTO hybrid_events(event_id,attempt_id,session_id,sequence,type,payload_json,created_at) VALUES (?,?,?,?,?,?,?)",
                       (event_id, attempt_id, session_id, sequence, event_type, canonical, now))
        except sqlite3.IntegrityError as error:
            db.rollback()
            raise HybridConflict("hybrid event id or sequence is already recorded") from error
        db.commit()
    return {**body, "event_id": event_id, "sequence": sequence, "type": event_type}, False


def record_assistance(store: Store, attempt: dict[str, Any], event_id: str, exposure_kind: str, checkpoint: str,
                      checkpoint_version: str, source_event_id: str | None) -> dict[str, Any]:
    payload = {
        "event_type": "hybrid_assistance_exposed",
        "attempt_id": attempt["attempt_id"],
        "session_id": attempt["session_id"],
        "learner_id": attempt["learner_id"],
        "activity_id": attempt["activity_id"],
        "activity_version": attempt["activity_version"],
        "exposure_kind": exposure_kind,
        "checkpoint": checkpoint,
        "checkpoint_version": checkpoint_version,
        "source_event_id": source_event_id,
    }
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        stored_attempt = db.execute("SELECT session_id,status FROM hybrid_attempts WHERE attempt_id=?",
                                    (attempt["attempt_id"],)).fetchone()
        if not stored_attempt or stored_attempt["session_id"] != attempt["session_id"]:
            db.rollback()
            raise KeyError("hybrid attempt not found for session")
        prior = db.execute("SELECT * FROM hybrid_events WHERE event_id=?", (event_id,)).fetchone()
        if prior:
            sequence = int(prior["sequence"])
            payload["sequence"] = sequence
            prior_payload = json.loads(prior["payload_json"])
            if (prior["type"] != "hybrid_assistance_exposed" or prior["session_id"] != attempt["session_id"]
                    or _identity(prior_payload) != _identity(payload)):
                db.rollback()
                raise HybridConflict("event_id already exists with a different payload")
            # Repair a legacy partial write on an exact retry, and keep both rows atomic.
            assistance = db.execute("SELECT * FROM hybrid_assistance WHERE event_id=?", (event_id,)).fetchone()
            if assistance and (assistance["exposure_kind"] != exposure_kind or assistance["checkpoint"] != checkpoint
                               or assistance["checkpoint_version"] != checkpoint_version
                               or assistance["source_event_id"] != source_event_id):
                db.rollback()
                raise HybridConflict("assistance event_id already exists with different exposure details")
        else:
            sequence = int(db.execute("SELECT COALESCE(MAX(sequence),-1)+1 AS s FROM hybrid_events WHERE attempt_id=?",
                                      (attempt["attempt_id"],)).fetchone()["s"])
            payload["sequence"] = sequence
            db.execute("INSERT INTO hybrid_events(event_id,attempt_id,session_id,sequence,type,payload_json,created_at) VALUES (?,?,?,?,?,?,?)",
                       (event_id, attempt["attempt_id"], attempt["session_id"], sequence,
                        "hybrid_assistance_exposed", json.dumps(payload, sort_keys=True, separators=(",", ":")), utc_now()))
        if not db.execute("SELECT 1 FROM hybrid_assistance WHERE event_id=?", (event_id,)).fetchone():
            db.execute("INSERT INTO hybrid_assistance(event_id,attempt_id,session_id,learner_id,exposure_kind,checkpoint,"
                       "checkpoint_version,source_event_id,sequence,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (event_id, attempt["attempt_id"], attempt["session_id"], attempt["learner_id"], exposure_kind,
                        checkpoint, checkpoint_version, source_event_id, sequence, utc_now()))
        db.commit()
    payload["sequence"] = sequence
    return {**payload, "event_id": event_id, "sequence": sequence, "type": "hybrid_assistance_exposed"}


def assistance_records(store: Store, attempt_id: str) -> list[dict[str, Any]]:
    with closing(store.connect()) as db:
        rows = db.execute("SELECT * FROM hybrid_assistance WHERE attempt_id=? ORDER BY sequence", (attempt_id,)).fetchall()
    return [dict(r) for r in rows]


def save_outcome(store: Store, outcome: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM hybrid_outcomes WHERE attempt_id=?", (outcome["attempt_id"],)).fetchone()
        if existing:
            db.rollback()
            return _outcome_row(dict(existing))
        db.execute("INSERT INTO hybrid_outcomes(attempt_id,session_id,learner_id,activity_id,activity_version,"
                   "evaluation_version,completion_state,assisted,excluded_from_unassisted,outcomes_json,evidence_ids_json,"
                   "limitations_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (outcome["attempt_id"], outcome["session_id"], outcome["learner_id"], outcome["activity_id"],
                    outcome["activity_version"], outcome["evaluation_version"], outcome["completion_state"],
                    int(outcome["assisted"]), int(outcome["excluded_from_unassisted"]),
                    json.dumps(outcome["outcomes"], sort_keys=True, separators=(",", ":")),
                    json.dumps(outcome["evidence_ids"], sort_keys=True, separators=(",", ":")),
                    json.dumps(outcome["limitations"], sort_keys=True, separators=(",", ":")), now))
        db.execute("UPDATE hybrid_attempts SET status='completed', completed_at=? WHERE attempt_id=?",
                   (now, outcome["attempt_id"]))
        db.commit()
    stored = get_outcome(store, outcome["attempt_id"])
    assert stored is not None
    return stored


def _outcome_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt_id": row["attempt_id"], "session_id": row["session_id"], "learner_id": row["learner_id"],
        "activity_id": row["activity_id"], "activity_version": row["activity_version"],
        "evaluation_version": row["evaluation_version"], "completion_state": row["completion_state"],
        "assisted": bool(row["assisted"]), "excluded_from_unassisted": bool(row["excluded_from_unassisted"]),
        "outcomes": json.loads(row["outcomes_json"]), "evidence_ids": json.loads(row["evidence_ids_json"]),
        "limitations": json.loads(row["limitations_json"]), "created_at": row["created_at"],
    }


def get_outcome(store: Store, attempt_id: str) -> dict[str, Any] | None:
    with closing(store.connect()) as db:
        row = db.execute("SELECT * FROM hybrid_outcomes WHERE attempt_id=?", (attempt_id,)).fetchone()
    return _outcome_row(dict(row)) if row else None


def learner_outcomes(store: Store, learner_id: str, activity_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM hybrid_outcomes WHERE learner_id=?"; params: list[Any] = [learner_id]
    if activity_id:
        sql += " AND activity_id=?"; params.append(activity_id)
    sql += " ORDER BY created_at"
    with closing(store.connect()) as db:
        rows = db.execute(sql, params).fetchall()
    return [_outcome_row(dict(r)) for r in rows]


def complete_attempt(store: Store, attempt_id: str, event_id: str, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    sequence = next_sequence(store, attempt_id)
    event, _ = append_event(store, attempt_id, session_id, sequence, "hybrid_attempt_completed", payload, event_id)
    return event
