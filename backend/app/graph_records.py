"""Read-only graph record resolvers over canonical SQLite stores."""
from __future__ import annotations

import json
from contextlib import closing
from typing import Any


SUPPORTED_RECORD_KINDS = {
    "plan", "plan_step", "plan_launch", "core_training_block",
    "hybrid_attempt", "hybrid_outcome", "crystal_attempt", "crystal_outcome",
    "canonical_event",
}


def _decode_json(value: Any, fallback: Any) -> Any:
    return json.loads(value) if value else fallback


def _canonical_event(store: Any, learner_id: str, event_id: str,
                    source_table: str | None = None) -> dict[str, Any] | None:
    with closing(store.connect()) as db:
        if source_table in (None, "events"):
            row = db.execute("SELECT e.event_id,e.type AS event_type,e.created_at,e.payload_json,'events' AS source_table "
                "FROM events e JOIN sessions s ON s.id=e.session_id WHERE s.learner_id=? AND e.event_id=?",
                (learner_id, event_id)).fetchone()
            if row:
                data = dict(row)
                data["payload"] = _decode_json(data.pop("payload_json"), {})
                return data
        if source_table in (None, "hybrid_events"):
            row = db.execute("SELECT e.event_id,e.type AS event_type,e.created_at,e.payload_json,'hybrid_events' AS source_table "
                "FROM hybrid_events e JOIN hybrid_attempts a USING(attempt_id) "
                "WHERE a.learner_id=? AND e.event_id=?", (learner_id, event_id)).fetchone()
            if row:
                data = dict(row)
                data["payload"] = _decode_json(data.pop("payload_json"), {})
                return data
        if source_table in (None, "crystal_events"):
            row = db.execute("SELECT e.event_id,e.event_type,e.created_at,e.payload_json,'crystal_events' AS source_table "
                "FROM crystal_events e JOIN crystal_attempts a USING(attempt_id) "
                "WHERE a.learner_id=? AND e.event_id=?", (learner_id, event_id)).fetchone()
            if row:
                data = dict(row)
                data["payload"] = _decode_json(data.pop("payload_json"), {})
                return data
    return None


def _evidence_links(store: Any, learner_id: str, ids: list[str]) -> list[dict[str, Any]]:
    links = []
    for event_id in dict.fromkeys(str(value) for value in ids if value):
        event = _canonical_event(store, learner_id, event_id)
        links.append({"id": event_id, "kind": "canonical_event",
                      "source_table": event["source_table"] if event else None,
                      "event_type": event["event_type"] if event else None,
                      "created_at": event["created_at"] if event else None,
                      "resolvable": event is not None})
    return links


def resolve_graph_record(store: Any, learner_id: str, kind: str, record_id: str) -> dict[str, Any] | None:
    """Resolve a namespaced graph record to its canonical SQLite owner and evidence."""
    if kind not in SUPPORTED_RECORD_KINDS:
        raise ValueError("unsupported graph record kind")
    record: dict[str, Any] | None = None
    evidence_ids: list[str] = []
    version: str | None = None

    if kind == "canonical_event":
        event = _canonical_event(store, learner_id, record_id)
        if not event:
            return None
        return {"record_ref": {"kind": kind, "id": record_id, "version": None,
                               "source_table": event["source_table"]},
                "record": event, "evidence": []}

    if kind == "plan":
        record = next((item for item in store.plans(learner_id) if item.get("plan_id") == record_id), None)
        if record:
            evidence_ids = list(record.get("evidence_ids") or [])
            version = record.get("plan_version")
    elif kind == "plan_step":
        if "::" not in record_id:
            raise ValueError("plan_step id must be plan_id::step_id")
        plan_id, step_id = record_id.split("::", 1)
        plan = next((item for item in store.plans(learner_id) if item.get("plan_id") == plan_id), None)
        step = next((item for item in (plan or {}).get("steps", []) if item.get("step_id") == step_id), None)
        if step:
            record = {"plan_id": plan_id, "step": step}
            evidence_ids = list(dict.fromkeys([*(step.get("evidence_ids") or []),
                                                *(step.get("completion_references") or [])]))
            version = (step.get("activity_ref") or {}).get("version") or (plan or {}).get("plan_version")
    elif kind == "plan_launch":
        from .plan_v3 import _ensure_launch_table
        _ensure_launch_table(store)
        with closing(store.connect()) as db:
            row = db.execute("SELECT * FROM plan_step_launches WHERE learner_id=? AND request_id=?",
                             (learner_id, record_id)).fetchone()
            alias = False
            if not row:
                row = db.execute("SELECT l.* FROM plan_step_launch_aliases a JOIN plan_step_launches l "
                    "ON l.request_id=a.canonical_request_id WHERE a.learner_id=? AND a.request_id=?",
                    (learner_id, record_id)).fetchone()
                alias = bool(row)
        if row:
            record = dict(row)
            record["destination"] = _decode_json(record.pop("destination_json", None), {})
            record["requested_alias"] = alias
            evidence_ids = [record["start_event_id"]]
            version = record["activity_version"]
    elif kind == "core_training_block":
        block = store.get_training_block(record_id)
        if block and block.get("learner_id") == learner_id:
            events = [event for event in store.events(learner_id=learner_id)
                      if (event.get("payload") or {}).get("training_block_id") == record_id]
            start = next((event for event in events if event["type"] == "training_block_started"), None)
            decision = store.get_decision(record_id)
            evidence_ids = [event["event_id"] for event in events]
            if decision and decision.get("event_id"):
                evidence_ids.append(decision["event_id"])
            record = {"block": block, "decision": decision,
                      "event_summaries": [{"event_id": event["event_id"], "event_type": event["type"],
                                           "created_at": event.get("created_at")} for event in events],
                      "started": start is not None}
            version = block.get("exercise_version")
    elif kind in {"hybrid_attempt", "hybrid_outcome"}:
        with closing(store.connect()) as db:
            row = db.execute("SELECT * FROM hybrid_attempts WHERE learner_id=? AND attempt_id=?",
                             (learner_id, record_id)).fetchone()
            outcome = db.execute("SELECT * FROM hybrid_outcomes WHERE learner_id=? AND attempt_id=?",
                                 (learner_id, record_id)).fetchone()
            events = db.execute("SELECT event_id,type,sequence,created_at FROM hybrid_events "
                                "WHERE attempt_id=? ORDER BY sequence", (record_id,)).fetchall() if row else []
        if row and (kind == "hybrid_attempt" or outcome):
            if kind == "hybrid_attempt":
                record = {key: row[key] for key in ("attempt_id", "session_id", "activity_id", "activity_version",
                    "mode", "config_version", "difficulty_tier", "status", "started_at", "completed_at")}
                record["events"] = [dict(event) for event in events]
                evidence_ids = [event["event_id"] for event in events]
                version = row["activity_version"]
            else:
                record = {key: outcome[key] for key in ("attempt_id", "session_id", "activity_id", "activity_version",
                    "evaluation_version", "completion_state", "assisted", "excluded_from_unassisted", "created_at")}
                record["outcomes"] = _decode_json(outcome["outcomes_json"], {})
                record["limitations"] = _decode_json(outcome["limitations_json"], [])
                evidence_ids = _decode_json(outcome["evidence_ids_json"], [])
                version = outcome["activity_version"]
    elif kind in {"crystal_attempt", "crystal_outcome"}:
        with closing(store.connect()) as db:
            row = db.execute("SELECT * FROM crystal_attempts WHERE learner_id=? AND attempt_id=?",
                             (learner_id, record_id)).fetchone()
            outcome = db.execute("SELECT * FROM crystal_outcomes WHERE learner_id=? AND attempt_id=?",
                                 (learner_id, record_id)).fetchone()
            events = db.execute("SELECT event_id,event_type,sequence,created_at FROM crystal_events "
                                "WHERE attempt_id=? ORDER BY sequence", (record_id,)).fetchall() if row else []
        if row and (kind == "crystal_attempt" or outcome):
            if kind == "crystal_attempt":
                record = {key: row[key] for key in ("attempt_id", "session_id", "form_version", "generator_version",
                    "status", "started_at")}
                # Configuration is deliberately omitted; it contains answer-bearing puzzle data.
                record["events"] = [dict(event) for event in events]
                evidence_ids = [event["event_id"] for event in events]
                version = row["form_version"]
            else:
                record = {key: outcome[key] for key in ("attempt_id", "session_id", "form_version", "generator_version",
                    "evaluation_version", "choice_id", "correct", "response_time_ms", "created_at")}
                evidence_ids = _decode_json(outcome["evidence_ids_json"], [])
                version = outcome["form_version"]

    if record is None:
        return None
    return {"record_ref": {"kind": kind, "id": record_id, "version": version},
            "record": record, "evidence": _evidence_links(store, learner_id, evidence_ids)}
