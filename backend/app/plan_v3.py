"""Typed, additive plan-v3 helpers for core, hybrid and Crystal activities.

The v3 projection is kept in ``training_plans.plan_extra_json`` so historical
plan-v1/v2 rows remain readable without a schema migration. Hybrid and Crystal
eligibility is deliberately gated on the five existing core family baselines;
their task outcomes never affect core scores or tiers.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
from typing import Any, Literal, TypedDict
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


PLAN_VERSION = "plan-v3"
PLAN_SCHEMA_VERSION = 3
HYBRID_PLAN_POLICY_VERSION = "hybrid-practice-eligibility-v1"
PLAN_STEP_STATUSES = ("recommended", "in_progress", "completed", "deferred", "superseded")


class ActivityRef(TypedDict):
    kind: Literal["core", "hybrid", "crystal"]
    id: str
    version: str


def activity_ref(kind: str, activity_id: str, version: str, **details: Any) -> ActivityRef:
    if kind not in {"core", "hybrid", "crystal"} or not activity_id or not version:
        raise ValueError("activity reference requires a supported kind, id and version")
    return {"kind": kind, "id": activity_id, "version": version, **details}  # type: ignore[return-value]


def core_version(exercise_id: str) -> str:
    from .battery_exercises import VERSIONS
    if exercise_id in VERSIONS:
        return VERSIONS[exercise_id]
    from .contracts import EXERCISE_VERSION
    return EXERCISE_VERSION


def _hybrid_catalog() -> list[dict[str, Any]]:
    from .hybrid_activities import CATALOG, capability_metadata, is_implemented
    return [capability_metadata(activity_id) for activity_id in CATALOG if is_implemented(activity_id)]


def _crystal_catalog() -> dict[str, Any]:
    from .crystal_reasoning import CAPABILITY_METADATA
    return dict(CAPABILITY_METADATA)


def _all_baselines_complete(context: dict[str, Any]) -> bool:
    families = context.get("families", {})
    return len(families) == 5 and all(bool(family.get("completed")) for family in families.values())


def _candidate_score(meta: dict[str, Any], core_ranks: dict[str, float], goal: str | None,
                     exposure_recency: float) -> float:
    # This is an explainable task-mechanics match, not an assessment inference.
    relevance = meta.get("family_relevance", [])
    values = [core_ranks.get(str(dimension), 0.0) for dimension in relevance]
    fit = max(values, default=0.0)
    if goal in relevance:
        fit += 0.1
    # Rotation is based only on complete, eligible, unassisted practice exposure.
    return round(fit + 0.15 * exposure_recency, 6)


def _eligible_exposure_recency(store: Any, learner_id: str) -> tuple[dict[str, str], dict[str, int]]:
    latest: dict[str, str] = {}
    counts: dict[str, int] = {}
    with closing(store.connect()) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "hybrid_outcomes" in tables:
            rows = db.execute("SELECT activity_id,completion_state,assisted,excluded_from_unassisted,created_at "
                              "FROM hybrid_outcomes WHERE learner_id=?", (learner_id,)).fetchall()
            for row in rows:
                if row["completion_state"] != "completed" or row["assisted"] or row["excluded_from_unassisted"]:
                    continue
                aid, stamped = str(row["activity_id"]), str(row["created_at"])
                latest[aid] = max(latest.get(aid, ""), stamped)
                counts[aid] = counts.get(aid, 0) + 1
        if "crystal_outcomes" in tables:
            rows = db.execute("SELECT created_at FROM crystal_outcomes WHERE learner_id=?", (learner_id,)).fetchall()
            if rows:
                latest["CRYSTAL"] = max(str(row["created_at"]) for row in rows)
                counts["CRYSTAL"] = len(rows)
    return latest, counts


def _recency_score(stamp: str | None) -> float:
    if not stamp:
        return 1.0
    try:
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    days = max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 86400.0)
    return round(min(1.0, days / (days + 14.0)), 6)


def enrich_plan_v3(plan: dict[str, Any], context: dict[str, Any], events: list[dict[str, Any]],
                   store: Any, *, available_activities: list[str] | None = None,
                   previous_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add typed refs and append affordable HY/Crystal practice after core work.

    ``available_activities=None`` means use every implemented catalog entry.
    An explicit empty list is preserved and produces no optional activities.
    Existing plan-v2 fields, IDs, steps and history are retained.
    """
    result = dict(plan)
    steps = [dict(step) for step in plan.get("steps", [])]
    for step in steps:
        step["activity_ref"] = activity_ref("core", step["exercise_type_id"], core_version(step["exercise_type_id"]))
        step["mode"] = "training" if step.get("action") == "targeted_training" else "baseline"

    explicit = available_activities is not None
    catalog = _hybrid_catalog()
    crystal = _crystal_catalog()
    all_ids = [str(item["activity_id"]) for item in catalog] + [str(crystal["activity_id"])]
    requested = list(dict.fromkeys(available_activities or [])) if explicit else list(all_ids)
    allowed = set(requested)
    unknown = sorted(allowed - set(all_ids))
    baseline_ready = _all_baselines_complete(context)
    core_constraint = plan.get("availability", {}) or {}
    constrained_dimensions = core_constraint.get("requested") if core_constraint.get("applied") else None
    core_constraint_empty = constrained_dimensions == []
    deferred_core: list[dict[str, Any]] = []
    core_ranks = {str(step.get("dimension_id")): float(step.get("ranking_score", 0))
                  for step in steps if step.get("dimension_id")}
    core_ranks.update({str(row.get("dimension")): float(row.get("score", 0))
                       for row in plan.get("alternatives", []) if row.get("dimension")})
    latest_exposure, exposure_counts = _eligible_exposure_recency(
        store, str(plan.get("learner_id", "demo-user")))
    candidates = [item for item in catalog if item["activity_id"] in allowed]
    if "CRYSTAL" in allowed:
        candidates.append(crystal)
    if constrained_dimensions is not None:
        candidates = [item for item in candidates
                      if set(item.get("family_relevance", [])) & set(constrained_dimensions)]
    scored_candidates = [(item, _recency_score(latest_exposure.get(str(item["activity_id"]))))
                         for item in candidates]
    scored_candidates.sort(key=lambda pair: (-_candidate_score(pair[0], core_ranks, plan.get("goal"), pair[1]),
                                             -pair[1], str(pair[0]["activity_id"])))

    if baseline_ready and not core_constraint_empty and scored_candidates and len(steps) > 1:
        resolved_id = (plan.get("resolved_next_step") or {}).get("exercise_id")
        resolved_index = next((i for i, step in enumerate(steps)
                               if step.get("activity_ref", {}).get("kind") == "core"
                               and step.get("exercise_type_id") == resolved_id), None)
        keep_index = resolved_index if resolved_index is not None else next(
            (i for i, step in enumerate(steps) if step.get("activity_ref", {}).get("kind") == "core"), 0)
        first_core_minutes = int(steps[keep_index].get("estimated_time_minutes", 0))
        can_fund_optional = any(int(meta["estimated_duration_minutes"])
                                <= max(0, int(plan.get("budget_minutes", 20)) - first_core_minutes)
                                for meta, _ in scored_candidates)
        if can_fund_optional:
            deferred_core = [step for i, step in enumerate(steps) if i != keep_index]
            steps = [steps[keep_index]]

    remaining = max(0, int(plan.get("budget_minutes", 20)) - sum(
        int(step.get("estimated_time_minutes", 0)) for step in steps))
    scheduled: list[dict[str, Any]] = []
    if baseline_ready and not core_constraint_empty:
        for meta, recency in scored_candidates:
            if len(steps) >= 4:
                break
            activity_id = str(meta["activity_id"])
            minutes = int(meta["estimated_duration_minutes"])
            if minutes > remaining:
                continue
            kind = "crystal" if activity_id == "CRYSTAL" else "hybrid"
            version = str(meta.get("activity_version") or meta.get("form_version"))
            ref = activity_ref(kind, activity_id, version,
                               config_version=str(meta.get("config_version", "1")))
            score = _candidate_score(meta, core_ranks, plan.get("goal"), recency)
            fit = max((core_ranks.get(str(dimension), 0.0)
                       for dimension in meta.get("family_relevance", [])), default=0.0)
            if plan.get("goal") in meta.get("family_relevance", []):
                fit += 0.1
            index = len(steps) + 1
            step = {
                "step_id": f"step-{index}", "dimension_id": None,
                "exercise_type_id": None, "activity_ref": ref,
                "label": str(meta.get("title") or meta.get("activity_id")),
                "action": "hybrid_practice" if kind == "hybrid" else "crystal_practice",
                "mode": "training" if kind == "hybrid" else "single_prompt",
                "difficulty_tier": "tier-1" if kind == "hybrid" else None,
                "strategy_id": None,
                "selection_reason": "mechanic_relevance_and_unassisted_exposure_recency",
                "ranking_score": score,
                "ranking_factors": {"task_mechanics_fit": round(fit, 6),
                                    "eligible_unassisted_exposure_recency": recency,
                                    "eligible_unassisted_exposure_count": exposure_counts.get(activity_id, 0)},
                "source_evidence_ids": [], "estimated_time_minutes": minutes,
                "estimate_source": "provisional_unmeasured_activity_metadata",
                "estimate_sample_size": 0,
                "duration_estimate": {"minutes": minutes, "confidence": "provisional",
                                      "source": "catalog_initial_budget_guess"},
                "status": "recommended", "policy_version": HYBRID_PLAN_POLICY_VERSION,
                "launch_tier": None, "tier_source": None,
                "completion_references": [], "superseded_by": None,
                "lifecycle_version": "plan-step-lifecycle-v1",
                "contributions": {"baseline_indices": False, "ex_difficulty_tiers": False,
                                  "participation_xp": False},
            }
            steps.append(step)
            scheduled.append(step)
            remaining -= minutes

    planned_total = sum(int(step.get("estimated_time_minutes", 0)) for step in steps)
    result.update({
        "plan_version": PLAN_VERSION,
        "schema_version": PLAN_SCHEMA_VERSION,
        "steps": steps,
        "planned_minutes": planned_total,
        "estimated_time_minutes": planned_total,
        "unused_minutes": remaining,
        "budget_note": (f"{planned_total} of {plan.get('budget_minutes', 20)} minutes are planned; "
                        f"{remaining} remain unused because no further activity fits the remaining time."),
        "budget_adjustment": None if len(steps) >= 2 else plan.get("budget_adjustment"),
        "availability": {
            "applied": explicit or bool(core_constraint.get("applied")),
            "requested": core_constraint.get("requested"),
            "requested_activities_applied": explicit,
            "requested_activities": requested if explicit else None,
            "excluded": sorted(set(all_ids) - allowed) if explicit else [],
            "excluded_dimensions": core_constraint.get("excluded", []),
            "unknown": unknown, "available": all_ids,
        },
        "resolved_snapshot": {
            "plan_id": plan.get("plan_id"), "decision_fingerprint": plan.get("decision_fingerprint"),
            "core_first_step_id": next((step.get("step_id") for step in steps
                                         if step.get("activity_ref", {}).get("kind") == "core"), None),
            "availability_applied": explicit,
        },
        "personalized_practice": {
            "eligible": baseline_ready, "gate": "all_five_core_baselines_completed",
            "scheduled_activity_ids": [step["activity_ref"]["id"] for step in scheduled],
            "provisional_duration_count": len(scheduled),
            "ranking_policy_version": HYBRID_PLAN_POLICY_VERSION,
        },
        "features": {**plan.get("features", {}), "typed_activity_refs": True,
                      "personalized_practice_eligible": baseline_ready,
                      "personalized_activity_count": len(scheduled)},
        "deferred_core_steps": [dict(step, deferral_reason="optional_later_practice_budget_slot")
                                for step in deferred_core],
    })
    result["decision_fingerprint"] = json.dumps({
        "plan_v2": plan.get("decision_fingerprint"),
        "availability_dimensions": core_constraint,
        "availability_activities_applied": explicit,
        "available_activities": requested,
        "typed_steps": [[step.get("activity_ref"), step.get("action"), step.get("estimated_time_minutes")]
                        for step in steps],
    }, sort_keys=True, separators=(",", ":"))
    if previous_plan is not None:
        result["changed"] = previous_plan.get("decision_fingerprint") != result["decision_fingerprint"]
    return result


def _ensure_launch_table(store: Any) -> None:
    with closing(store.connect()) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS plan_step_launches (
            request_id TEXT PRIMARY KEY,
            learner_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            activity_kind TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            activity_version TEXT NOT NULL,
            payload_fingerprint TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            start_event_id TEXT NOT NULL,
            status TEXT NOT NULL,
            lifecycle_generation INTEGER NOT NULL DEFAULT 0,
            destination_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(plan_id, step_id)
        );
        CREATE INDEX IF NOT EXISTS plan_launches_learner ON plan_step_launches(learner_id, created_at);
        CREATE TABLE IF NOT EXISTS plan_step_launch_aliases (
            request_id TEXT PRIMARY KEY,
            canonical_request_id TEXT NOT NULL,
            learner_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            payload_fingerprint TEXT NOT NULL,
            lifecycle_generation INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS plan_launch_aliases_learner ON plan_step_launch_aliases(learner_id, created_at);
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(plan_step_launches)").fetchall()}
        if "lifecycle_generation" not in columns:
            db.execute("ALTER TABLE plan_step_launches ADD COLUMN lifecycle_generation INTEGER NOT NULL DEFAULT 0")


def _reserve_launch(store: Any, record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Reserve one immutable launch mapping before canonical attempt creation."""
    _ensure_launch_table(store)
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        from .storage import utc_now
        db.execute("INSERT INTO learner_lifecycle(learner_id,generation,deleting,updated_at) VALUES(?,0,0,?) "
                   "ON CONFLICT(learner_id) DO NOTHING", (record["learner_id"], utc_now()))
        lifecycle = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                               (record["learner_id"],)).fetchone()
        if not lifecycle or lifecycle["deleting"]:
            db.rollback()
            raise PermissionError("learner deletion is in progress")
        prior = db.execute("SELECT * FROM plan_step_launches WHERE request_id=?", (record["request_id"],)).fetchone()
        if prior:
            row = dict(prior)
            if row["payload_fingerprint"] != record["payload_fingerprint"]:
                db.rollback()
                raise ValueError("request_id already exists with a different plan launch payload")
            db.commit()
            return row, False
        alias = db.execute("SELECT * FROM plan_step_launch_aliases WHERE request_id=?", (record["request_id"],)).fetchone()
        if alias:
            alias_row = dict(alias)
            if (alias_row["payload_fingerprint"] != record["payload_fingerprint"]
                    or alias_row["learner_id"] != record["learner_id"]
                    or alias_row["session_id"] != record["session_id"]
                    or alias_row["plan_id"] != record["plan_id"]
                    or alias_row["step_id"] != record["step_id"]):
                db.rollback()
                raise ValueError("request_id already exists with a different plan launch payload")
            canonical = db.execute("SELECT * FROM plan_step_launches WHERE request_id=?",
                                   (alias_row["canonical_request_id"],)).fetchone()
            if not canonical:
                db.rollback()
                raise ValueError("plan launch alias lost its canonical mapping")
            db.commit()
            return dict(canonical), False
        existing = db.execute("SELECT * FROM plan_step_launches WHERE plan_id=? AND step_id=?",
                              (record["plan_id"], record["step_id"])).fetchone()
        if existing:
            existing_row = dict(existing)
            if (existing_row["payload_fingerprint"] != record["payload_fingerprint"]
                    or existing_row["learner_id"] != record["learner_id"]
                    or existing_row["session_id"] != record["session_id"]):
                db.rollback()
                raise ValueError("plan step already has a different canonical launch")
            db.execute("INSERT INTO plan_step_launch_aliases(request_id,canonical_request_id,learner_id,session_id,"
                       "plan_id,step_id,payload_fingerprint,lifecycle_generation,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                       (record["request_id"], existing_row["request_id"], record["learner_id"], record["session_id"],
                        record["plan_id"], record["step_id"], record["payload_fingerprint"],
                        int(lifecycle["generation"]), record["created_at"]))
            db.commit()
            return existing_row, False
        db.execute("""INSERT INTO plan_step_launches
            (request_id,learner_id,session_id,plan_id,step_id,activity_kind,activity_id,activity_version,
             payload_fingerprint,attempt_id,start_event_id,status,lifecycle_generation,destination_json,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(record[key] for key in ("request_id", "learner_id", "session_id", "plan_id", "step_id",
                   "activity_kind", "activity_id", "activity_version", "payload_fingerprint", "attempt_id",
                   "start_event_id", "status")) + (int(lifecycle["generation"]),) +
            tuple(record[key] for key in ("destination_json", "created_at", "updated_at")))
        record["lifecycle_generation"] = int(lifecycle["generation"])
        db.commit()
        return record, True


def _create_activity_attempt(store: Any, mapping: dict[str, Any], *, mode: str, difficulty_tier: str) -> None:
    ref = {"kind": mapping["activity_kind"], "id": mapping["activity_id"], "version": mapping["activity_version"]}
    if ref["kind"] == "core":
        raise ValueError("core plan launch requires the canonical core launcher callback")
    if ref["kind"] == "hybrid":
        from .hybrid_activities import CATALOG, generate
        from .hybrid_contracts import HYBRID_SCHEMA_VERSION
        from .hybrid_store import create_attempt
        meta = CATALOG[ref["id"]]
        if ref["version"] != meta["activity_version"]:
            raise ValueError("plan activity version is no longer available")
        seed = hashlib.sha256((mapping["request_id"] + ":plan-v3").encode()).hexdigest()[:32]
        config = generate(ref["id"], seed, mode, difficulty_tier, ref["version"])
        payload = {"event_type": "hybrid_attempt_started", "attempt_id": mapping["attempt_id"],
                   "session_id": mapping["session_id"], "learner_id": mapping["learner_id"],
                   "activity_id": ref["id"], "activity_version": ref["version"], "mode": mode,
                   "config_version": meta["config_version"], "difficulty_tier": difficulty_tier,
                   "seed": seed, "hybrid_schema_version": HYBRID_SCHEMA_VERSION}
        create_attempt(store, {"attempt_id": mapping["attempt_id"], "learner_id": mapping["learner_id"],
            "session_id": mapping["session_id"], "activity_id": ref["id"], "activity_version": ref["version"],
            "mode": mode, "config_version": meta["config_version"], "difficulty_tier": difficulty_tier,
            "seed": seed, "config": config, "event_id": mapping["start_event_id"], "event_payload": payload})
    elif ref["kind"] == "crystal":
        from .crystal_reasoning import _config, _now, GENERATOR_VERSION, FORM_VERSION
        import json as _json
        if ref["version"] != FORM_VERSION:
            raise ValueError("Crystal form version is no longer available")
        seed = hashlib.sha256((mapping["request_id"] + ":plan-v3").encode()).hexdigest()[:32]
        config = _config(seed)
        now = _now()
        payload = {"event_type": "crystal_started", "attempt_id": mapping["attempt_id"],
                   "session_id": mapping["session_id"], "learner_id": mapping["learner_id"],
                   "form_version": ref["version"], "generator_version": GENERATOR_VERSION,
                   "seed": seed, "config": config}
        with closing(store.connect()) as db:
            prior = db.execute("SELECT * FROM crystal_events WHERE event_id=?", (mapping["start_event_id"],)).fetchone()
            if prior:
                if prior["attempt_id"] != mapping["attempt_id"] or prior["event_type"] != "crystal_started":
                    raise ValueError("Crystal launch event identity conflicts")
                return
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO crystal_attempts VALUES(?,?,?,?,?,?,?,?,?)",
                (mapping["attempt_id"], mapping["session_id"], mapping["learner_id"], ref["version"],
                 GENERATOR_VERSION, seed, _json.dumps(config, sort_keys=True), "active", now))
            db.execute("INSERT INTO crystal_events VALUES(?,?,?,?,?,?,?)",
                (mapping["start_event_id"], mapping["attempt_id"], mapping["session_id"], 1,
                 "crystal_started", _json.dumps(payload, sort_keys=True), now))
            db.commit()


def _launch_step_locked(store: Any, *, learner_id: str, plan_id: str, step_id: str, session_id: str,
                        request_id: str, mode: str | None = None, difficulty_tier: str | None = None,
                        core_launcher: Any = None) -> dict[str, Any]:
    """Idempotently link a plan step to its canonical core, HY or Crystal attempt."""
    plans = store.plans(learner_id)
    plan = next((row for row in plans if row["plan_id"] == plan_id), None)
    if not plan:
        raise KeyError("plan not found")
    step = next((row for row in plan.get("steps", []) if row.get("step_id") == step_id), None)
    if not step:
        raise KeyError("plan step not found")
    ref = step.get("activity_ref")
    if not isinstance(ref, dict) or ref.get("kind") not in {"core", "hybrid", "crystal"}:
        raise ValueError("plan step has no supported typed activity reference")
    if step.get("status") not in {"recommended", "in_progress"}:
        raise ValueError("plan step is not launchable")
    session = store.get_session(session_id)
    if not session:
        raise KeyError("session not found")
    if session.get("learner_id") != learner_id:
        raise PermissionError("learner does not own session")
    planned_mode = step.get("mode") or ("single_prompt" if ref["kind"] == "crystal" else "training")
    planned_tier = step.get("launch_tier") or step.get("difficulty_tier")
    if mode is not None and mode != planned_mode:
        raise ValueError("launch mode does not match the saved plan step")
    if difficulty_tier is not None and difficulty_tier != planned_tier:
        raise ValueError("launch tier does not match the saved plan step")
    mode = planned_mode
    difficulty_tier = planned_tier or "tier-1"
    if ref["kind"] == "core":
        if not core_launcher:
            raise ValueError("core plan launch requires the canonical core launcher")
        if step.get("action") != "targeted_training" or not step.get("launch_tier"):
            raise ValueError("core baseline steps must use their canonical assessment entry point")
        if ref["version"] != core_version(ref["id"]):
            raise ValueError("core activity version is no longer available")
    elif ref["kind"] == "hybrid":
        from .hybrid_activities import CATALOG
        if ref["id"] not in CATALOG or CATALOG[ref["id"]]["activity_version"] != ref["version"]:
            raise ValueError("plan activity version is no longer available")
    else:
        from .crystal_reasoning import FORM_VERSION
        if ref["id"] != "CRYSTAL" or ref["version"] != FORM_VERSION:
            raise ValueError("Crystal form version is no longer available")
    from .storage import utc_now
    payload = {"plan_id": plan_id, "step_id": step_id, "learner_id": learner_id,
               "session_id": session_id, "activity_ref": ref, "mode": mode,
               "difficulty_tier": difficulty_tier}
    mapping = {"request_id": request_id, "learner_id": learner_id, "session_id": session_id,
               "plan_id": plan_id, "step_id": step_id, "activity_kind": ref["kind"],
               "activity_id": ref["id"], "activity_version": ref["version"],
               "payload_fingerprint": launch_request_fingerprint(payload),
               "attempt_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "ai4brain-plan:" + plan_id + ":" + step_id)),
               "start_event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "ai4brain-plan-start:" + plan_id + ":" + step_id)),
               "status": "pending", "destination_json": json.dumps({"kind": ref["kind"], "id": ref["id"]}),
               "created_at": utc_now(), "updated_at": utc_now()}
    _ensure_launch_table(store)
    with closing(store.connect()) as db:
        existing = db.execute("SELECT * FROM plan_step_launches WHERE plan_id=? AND step_id=?",
                              (plan_id, step_id)).fetchone()
    if existing:
        existing = dict(existing)
        if (existing["payload_fingerprint"] != mapping["payload_fingerprint"]
                or existing["learner_id"] != learner_id or existing["session_id"] != session_id):
            raise ValueError("plan step already has a different canonical launch")
    elif not plans or plans[-1]["plan_id"] != plan_id:
        raise ValueError("plan is stale; refresh the plan before launching this step")
    stored, created = _reserve_launch(store, mapping)
    if stored["learner_id"] != learner_id or stored["session_id"] != session_id:
        raise PermissionError("launch mapping belongs to another learner or session")
    if stored["payload_fingerprint"] != mapping["payload_fingerprint"]:
        raise ValueError("plan step already has a different canonical launch")
    if ref["kind"] == "core" and (created or stored["status"] != "started"):
        launched = core_launcher(session_id, ref["id"], step["launch_tier"], stored["attempt_id"])
        actual_block_id = (launched.get("block") or {}).get("block_id")
        if actual_block_id != stored["attempt_id"]:
            raise ValueError("canonical core launcher returned a different block id")
    elif ref["kind"] != "core" and (created or stored["status"] != "started"):
        _create_activity_attempt(store, stored, mode=mode, difficulty_tier=difficulty_tier)
    with closing(store.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        lifecycle = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                               (learner_id,)).fetchone()
        if (not lifecycle or lifecycle["deleting"]
                or int(lifecycle["generation"]) != int(stored.get("lifecycle_generation", 0))):
            db.rollback()
            raise PermissionError("plan launch lost learner lifecycle ownership")
        db.execute("UPDATE plan_step_launches SET status='started',updated_at=? WHERE request_id=?",
                   (utc_now(), stored["request_id"]))
        db.commit()
    attempt_version = (store.get_training_block(stored["attempt_id"]) or {}).get("exercise_version", ref["version"])
    return {"plan_id": plan_id, "step_id": step_id, "activity_ref": ref,
            "attempt_ref": {"kind": ref["kind"], "id": stored["attempt_id"], "version": attempt_version},
            "destination": json.loads(stored["destination_json"]), "status": "started",
            "idempotent_replay": not created}


def launch_step(store: Any, **kwargs: Any) -> dict[str, Any]:
    """Serialize launch side effects with local export and deletion operations."""
    lock = getattr(store, "coach_lifecycle_lock", None)
    if lock is None:
        return _launch_step_locked(store, **kwargs)
    with lock:
        return _launch_step_locked(store, **kwargs)


def plan_launches_for_export(db: Any, learner_id: str) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM plan_step_launches WHERE learner_id=? ORDER BY created_at", (learner_id,)).fetchall()
    return [{**dict(row), "destination": json.loads(row["destination_json"])} for row in rows]


def plan_launch_aliases_for_export(db: Any, learner_id: str) -> list[dict[str, Any]]:
    rows = db.execute("SELECT * FROM plan_step_launch_aliases WHERE learner_id=? ORDER BY created_at,request_id",
                      (learner_id,)).fetchall()
    return [dict(row) for row in rows]


def delete_plan_launches(store: Any, db: Any, learner_id: str) -> int:
    """Delete launch mappings inside the lifecycle service's learner transaction."""
    db.execute("DELETE FROM plan_step_launch_aliases WHERE learner_id=?", (learner_id,))
    cursor = db.execute("DELETE FROM plan_step_launches WHERE learner_id=?", (learner_id,))
    return cursor.rowcount


def canonical_outcome_reference(store: Any, ref: dict[str, Any], attempt_id: str,
                                learner_id: str = "demo-user") -> dict[str, Any] | None:
    """Resolve completion only from the activity's canonical outcome table."""
    kind, activity_id = ref.get("kind"), ref.get("id")
    if kind == "hybrid":
        from .hybrid_store import get_outcome
        row = get_outcome(store, attempt_id)
        if (not row or row.get("learner_id") != learner_id or row.get("activity_id") != activity_id
                or row.get("activity_version") != ref.get("version")):
            return None
        assisted = bool(row.get("assisted"))
        excluded = bool(row.get("excluded_from_unassisted"))
        return {"kind": kind, "id": attempt_id, "status": row.get("completion_state"),
                "assisted": assisted, "excluded_from_unassisted": excluded,
                "interrupted": row.get("completion_state") == "interrupted",
                "adaptive_eligible": not assisted and not excluded and row.get("completion_state") == "completed",
                "evidence_ids": list(row.get("evidence_ids", [])), "source": "hybrid_outcomes"}
    if kind == "crystal":
        with closing(store.connect()) as db:
            row = db.execute("SELECT * FROM crystal_outcomes WHERE attempt_id=? AND learner_id=?",
                             (attempt_id, learner_id)).fetchone()
        if not row:
            return None
        if row["form_version"] != ref.get("version"):
            return None
        return {"kind": kind, "id": attempt_id, "status": "completed", "assisted": False,
                "excluded_from_unassisted": False, "interrupted": False, "adaptive_eligible": True,
                "evidence_ids": json.loads(row["evidence_ids_json"]), "source": "crystal_outcomes"}
    if kind == "core":
        block = store.get_training_block(attempt_id)
        if (not block or block.get("learner_id") != learner_id
                or block.get("exercise_id") != ref.get("id")):
            return None
        events = store.events(learner_id=learner_id)
        started = next((event for event in events if event["type"] == "training_block_started"
                        and (event.get("payload", {}) or {}).get("training_block_id") == attempt_id), None)
        if not started or (started.get("payload", {}) or {}).get("exercise_version") != block["exercise_version"]:
            return None
        required = set((started.get("payload", {}) or {}).get("item_ids", []))
        all_responses = store.block_events(attempt_id)
        responses = [event for event in all_responses
                     if not (event.get("payload", {}).get("interaction", {}) or {}).get("visibility_interrupted")]
        completed = {event.get("payload", {}).get("item_id") for event in responses}
        decision = store.get_decision(attempt_id)
        canonical_completed = bool(decision) or bool(required and required.issubset(completed))
        if not canonical_completed:
            if any((event.get("payload", {}).get("interaction", {}) or {}).get("visibility_interrupted")
                   for event in all_responses):
                return {"kind": kind, "id": attempt_id, "status": "interrupted", "assisted": False,
                        "excluded_from_unassisted": True, "interrupted": True, "adaptive_eligible": False,
                        "evidence_ids": [started["event_id"], *[event["event_id"] for event in all_responses]],
                        "source": "canonical_core_training_block"}
            return {"kind": kind, "id": attempt_id, "status": "in_progress", "assisted": False,
                    "excluded_from_unassisted": False, "interrupted": False, "adaptive_eligible": False,
                    "evidence_ids": [started["event_id"], *[event["event_id"] for event in all_responses]],
                    "source": "canonical_core_training_block"}
        assisted = any((event.get("payload", {}).get("interaction", {}) or {}).get("hint_count", 0)
                       or (event.get("payload", {}).get("interaction", {}) or {}).get("replay_count", 0)
                       for event in responses)
        interrupted = any((event.get("payload", {}).get("interaction", {}) or {}).get("visibility_interrupted")
                          for event in all_responses)
        excluded = bool(assisted or interrupted)
        decision_event_ids = [decision["event_id"]] if decision and decision.get("event_id") else []
        return {"kind": kind, "id": attempt_id, "status": "completed",
                "assisted": bool(assisted),
                "interrupted": bool(interrupted), "excluded_from_unassisted": excluded,
                "adaptive_eligible": not excluded,
                "evidence_ids": [started["event_id"], *[event["event_id"] for event in responses], *decision_event_ids],
                "source": "canonical_core_training_block"}
    raise ValueError("unknown activity reference kind")


def launch_request_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def refresh_plan_execution_status(store: Any, plan: dict[str, Any], learner_id: str = "demo-user") -> dict[str, Any]:
    """Return a read-time execution projection without mutating immutable plan history."""
    _ensure_launch_table(store)
    refreshed = dict(plan)
    steps = []
    with closing(store.connect()) as db:
        launches = {row["step_id"]: dict(row) for row in db.execute(
            "SELECT * FROM plan_step_launches WHERE learner_id=? AND plan_id=?", (learner_id, plan.get("plan_id"))
        ).fetchall()}
    core_context: dict[str, Any] | None = None
    for original in plan.get("steps", []):
        step = dict(original)
        mapping = launches.get(step.get("step_id"))
        ref = step.get("activity_ref") or {}
        if mapping and ref.get("kind") in {"core", "hybrid", "crystal"}:
            outcome = canonical_outcome_reference(store, ref, mapping["attempt_id"], learner_id)
            step["execution_status"] = ("completed" if outcome and outcome.get("status") == "completed"
                                         else "interrupted" if outcome and outcome.get("status") == "interrupted"
                                         else "in_progress" if outcome and outcome.get("status") == "in_progress"
                                         else mapping["status"])
            step["launch_ref"] = {"attempt_id": mapping["attempt_id"], "kind": mapping["activity_kind"],
                                  "version": mapping["activity_version"]}
            if outcome:
                step["assisted"] = bool(outcome.get("assisted"))
                step["excluded_from_unassisted"] = bool(outcome.get("excluded_from_unassisted"))
                step["adaptive_eligible"] = bool(outcome.get("adaptive_eligible"))
                step["interrupted"] = bool(outcome.get("interrupted"))
            if outcome and outcome.get("status") == "completed":
                step["completion_references"] = outcome["evidence_ids"]
                step["completion_source"] = outcome["source"]
        elif ref.get("kind") == "core" and step.get("action") == "additional_assessment":
            if core_context is None:
                from .twin_context import build_twin_context
                core_context = build_twin_context(store, learner_id)
            family = core_context.get("families", {}).get(step.get("dimension_id"), {})
            step["execution_status"] = "completed" if family.get("completed") else step.get("status", "recommended")
            if family.get("completed"):
                step["completion_references"] = list(family.get("evidence_ids", []))
                step["completion_source"] = "canonical_core_baseline_events"
        else:
            step["execution_status"] = step.get("status", "recommended")
        steps.append(step)
    refreshed["steps"] = steps
    refreshed["execution_projection"] = {"derived_at_read": True, "persisted_revision_unchanged": True}
    return refreshed


class PlanStepLaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    session_id: str = Field(min_length=1, max_length=160)
    mode: Literal["tutorial", "training", "challenge", "single_prompt"] | None = None
    difficulty_tier: Literal["tutorial", "tier-1", "tier-2", "tier-3"] | None = None


def register_plan_v3_routes(app: FastAPI, store: Any, core_launcher: Any = None) -> None:
    """Register typed activity launch; parent registers this router from main.py."""
    @app.post("/api/plans/{plan_id}/steps/{step_id}/launch")
    def launch_plan_step(plan_id: str, step_id: str, body: PlanStepLaunchRequest):
        try:
            return launch_step(store, learner_id="demo-user", plan_id=plan_id, step_id=step_id,
                               session_id=body.session_id, request_id=body.request_id,
                               mode=body.mode, difficulty_tier=body.difficulty_tier,
                               core_launcher=core_launcher)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
