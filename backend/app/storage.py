from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT_DIR / "data" / "ai4brain.sqlite3"


def utc_now() -> str: return datetime.now(timezone.utc).isoformat()

# A reserved turn that produced nothing for this long is treated as abandoned so an
# exact retry is possible; a live generation is never reclaimed.
STALE_IN_PROGRESS_SECONDS = 90


def seconds_since(value: Any) -> float:
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return 0.0
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds()


class CoachRequestInvalidated(RuntimeError):
    """A reserved coaching request lost its learner lifecycle ownership."""


class Store:
    def __init__(self, path: str | Path | None = None):
        chosen = Path(path or os.environ.get("AI4BRAIN_DB", DEFAULT_DB))
        self.path = chosen if chosen.is_absolute() else ROOT_DIR / chosen
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.coach_lifecycle_lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        con=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        con.row_factory=sqlite3.Row; con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA busy_timeout=10000")
        return con

    def initialize(self) -> None:
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, started_at TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('active','completed')),
              dashboard_mode TEXT NOT NULL DEFAULT 'analytics'
            );
            CREATE TABLE IF NOT EXISTS events (
              event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
              type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_session_created ON events(session_id,created_at);
            CREATE TABLE IF NOT EXISTS event_submissions (
              event_id TEXT PRIMARY KEY REFERENCES events(event_id), submission_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS profile_snapshots (
              id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, scoring_version TEXT NOT NULL,
              dimension TEXT NOT NULL, index_0_100 REAL, uncertainty_status TEXT NOT NULL,
              evidence_count INTEGER NOT NULL, completed INTEGER NOT NULL,
              evidence_ids_json TEXT NOT NULL, interrupted_count INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS snapshots_learner_created ON profile_snapshots(learner_id,created_at);
            CREATE TABLE IF NOT EXISTS recommendations (
              id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, snapshot_id TEXT,
              policy_version TEXT NOT NULL, action TEXT NOT NULL, exercise_id TEXT NOT NULL,
              tier TEXT NOT NULL, reason_codes_json TEXT NOT NULL, evidence_ids_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS training_blocks (
              block_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id),
              tier TEXT NOT NULL, exercise_version TEXT NOT NULL, status TEXT NOT NULL,
              started_at TEXT NOT NULL, exercise_id TEXT NOT NULL DEFAULT 'EX-02', dimension TEXT NOT NULL DEFAULT 'reasoning'
            );
            CREATE TABLE IF NOT EXISTS difficulty_decisions (
              block_id TEXT PRIMARY KEY REFERENCES training_blocks(block_id), learner_id TEXT NOT NULL,
              session_id TEXT NOT NULL REFERENCES sessions(id), old_tier TEXT NOT NULL, new_tier TEXT NOT NULL,
              action TEXT NOT NULL, rule_version TEXT NOT NULL, successes INTEGER NOT NULL, trial_count INTEGER NOT NULL,
              valid_trial_count INTEGER NOT NULL, rationale TEXT NOT NULL, reason_codes_json TEXT NOT NULL,
              evidence_ids_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS training_plans (
              plan_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, profile_snapshot_id TEXT, policy_version TEXT NOT NULL,
              goal TEXT, budget_minutes INTEGER NOT NULL, estimated_time_minutes INTEGER NOT NULL, reason_codes_json TEXT NOT NULL,
              rationale TEXT NOT NULL, steps_json TEXT NOT NULL, evidence_ids_json TEXT NOT NULL, features_json TEXT NOT NULL,
              alternatives_json TEXT NOT NULL, decision_fingerprint TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS plans_learner_created ON training_plans(learner_id,created_at);
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON profile_snapshots BEGIN SELECT RAISE(ABORT,'profile snapshots are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON profile_snapshots BEGIN SELECT RAISE(ABORT,'profile snapshots are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON difficulty_decisions BEGIN SELECT RAISE(ABORT,'difficulty decisions are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON difficulty_decisions BEGIN SELECT RAISE(ABORT,'difficulty decisions are immutable'); END;
            CREATE TABLE IF NOT EXISTS hybrid_attempts (
              attempt_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id),
              activity_id TEXT NOT NULL, activity_version TEXT NOT NULL, mode TEXT NOT NULL,
              config_version TEXT NOT NULL, difficulty_tier TEXT NOT NULL, seed TEXT NOT NULL,
              config_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('started','completed')),
              started_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS hybrid_attempts_session ON hybrid_attempts(session_id, started_at);
            CREATE INDEX IF NOT EXISTS hybrid_attempts_learner ON hybrid_attempts(learner_id, activity_id);
            CREATE TABLE IF NOT EXISTS hybrid_events (
              event_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES hybrid_attempts(attempt_id),
              session_id TEXT NOT NULL, sequence INTEGER NOT NULL, type TEXT NOT NULL,
              payload_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(attempt_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS hybrid_assistance (
              event_id TEXT PRIMARY KEY REFERENCES hybrid_events(event_id), attempt_id TEXT NOT NULL,
              session_id TEXT NOT NULL, learner_id TEXT NOT NULL, exposure_kind TEXT NOT NULL,
              checkpoint TEXT NOT NULL, checkpoint_version TEXT NOT NULL, source_event_id TEXT,
              sequence INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hybrid_outcomes (
              attempt_id TEXT PRIMARY KEY REFERENCES hybrid_attempts(attempt_id), session_id TEXT NOT NULL,
              learner_id TEXT NOT NULL, activity_id TEXT NOT NULL, activity_version TEXT NOT NULL,
              evaluation_version TEXT NOT NULL, completion_state TEXT NOT NULL, assisted INTEGER NOT NULL,
              excluded_from_unassisted INTEGER NOT NULL, outcomes_json TEXT NOT NULL,
              evidence_ids_json TEXT NOT NULL, limitations_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS hybrid_outcomes_learner ON hybrid_outcomes(learner_id, activity_id);
            CREATE TRIGGER IF NOT EXISTS hybrid_events_no_update BEFORE UPDATE ON hybrid_events BEGIN SELECT RAISE(ABORT,'hybrid events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_events_no_delete BEFORE DELETE ON hybrid_events BEGIN SELECT RAISE(ABORT,'hybrid events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_assistance_no_update BEFORE UPDATE ON hybrid_assistance BEGIN SELECT RAISE(ABORT,'hybrid assistance is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_assistance_no_delete BEFORE DELETE ON hybrid_assistance BEGIN SELECT RAISE(ABORT,'hybrid assistance is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_outcomes_no_update BEFORE UPDATE ON hybrid_outcomes BEGIN SELECT RAISE(ABORT,'hybrid outcomes are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS hybrid_outcomes_no_delete BEFORE DELETE ON hybrid_outcomes BEGIN SELECT RAISE(ABORT,'hybrid outcomes are immutable'); END;
            CREATE TABLE IF NOT EXISTS coach_turns (
              request_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, session_id TEXT NOT NULL,
              subject_exercise_id TEXT, subject_dimension TEXT, subject_source TEXT,
              provider_requested TEXT, provider_used TEXT, model TEXT, coach_version TEXT NOT NULL,
              payload_hash TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL,
              evidence_revision TEXT, request_json TEXT NOT NULL, response_json TEXT, progress_json TEXT,
              error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS coach_turns_session ON coach_turns(session_id, created_at);
            CREATE INDEX IF NOT EXISTS coach_turns_learner ON coach_turns(learner_id, created_at);
            CREATE TABLE IF NOT EXISTS coach_conversations (
              session_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, subject_exercise_id TEXT,
              provider TEXT NOT NULL, consent_recorded INTEGER NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS collaboration_claims (
              claim_id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL, source_event_id TEXT,
              session_id TEXT, evidence_event_id TEXT NOT NULL, claim_text TEXT NOT NULL,
              expected_verdict TEXT NOT NULL, explanation TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS collaboration_claims_opportunity ON collaboration_claims(opportunity_id);
            CREATE TABLE IF NOT EXISTS learner_lifecycle (
              learner_id TEXT PRIMARY KEY, generation INTEGER NOT NULL DEFAULT 0,
              deleting INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
            );
            """)
            coach_columns={r["name"] for r in db.execute("PRAGMA table_info(coach_turns)").fetchall()}
            if "lifecycle_generation" not in coach_columns:
                db.execute("ALTER TABLE coach_turns ADD COLUMN lifecycle_generation INTEGER NOT NULL DEFAULT 0")
            if "progress_json" not in coach_columns:
                db.execute("ALTER TABLE coach_turns ADD COLUMN progress_json TEXT")
            columns={r["name"] for r in db.execute("PRAGMA table_info(sessions)").fetchall()}
            if "dashboard_mode" not in columns: db.execute("ALTER TABLE sessions ADD COLUMN dashboard_mode TEXT NOT NULL DEFAULT 'analytics'")
            if "goal_dimension" not in columns: db.execute("ALTER TABLE sessions ADD COLUMN goal_dimension TEXT")
            block_columns={r["name"] for r in db.execute("PRAGMA table_info(training_blocks)").fetchall()}
            if "exercise_id" not in block_columns: db.execute("ALTER TABLE training_blocks ADD COLUMN exercise_id TEXT NOT NULL DEFAULT 'EX-02'")
            if "dimension" not in block_columns: db.execute("ALTER TABLE training_blocks ADD COLUMN dimension TEXT NOT NULL DEFAULT 'reasoning'")
            plan_columns={r["name"] for r in db.execute("PRAGMA table_info(training_plans)").fetchall()}
            if "plan_extra_json" not in plan_columns: db.execute("ALTER TABLE training_plans ADD COLUMN plan_extra_json TEXT")

    @staticmethod
    def _event_identity(payload: dict[str, Any]) -> str:
        identity=dict(payload); identity.pop("recorded_at",None)
        return json.dumps(identity,sort_keys=True,separators=(",",":"))

    def create_session(self, session_id: str, learner_id: str, dashboard_mode: str = "analytics") -> dict[str, Any]:
        now=utc_now()
        with closing(self.connect()) as db:
            db.execute("INSERT INTO sessions(id,learner_id,started_at,status,dashboard_mode) VALUES (?,?,?,'active',?)",(session_id,learner_id,now,dashboard_mode))
        consent_id=f"consent-{session_id}"
        self.add_event(consent_id,session_id,"consent_recorded",{"event_id":consent_id,"learner_id":learner_id,"session_id":session_id,"event_type":"consent_recorded","consent":{"accepted":True,"local_data_notice_acknowledged":True},"dashboard_mode":dashboard_mode,"sample_data":False,"recorded_at":now})
        return {"id":session_id,"learner_id":learner_id,"started_at":now,"status":"active","dashboard_mode":dashboard_mode}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db: row=db.execute("SELECT * FROM sessions WHERE id=?",(session_id,)).fetchone()
        return dict(row) if row else None

    def replay_submission(self, event_id: str, session_id: str, event_type: str, submission: dict[str, Any]) -> dict[str, Any] | None:
        """Return an immutable canonical event for an exact API retry, before policy enrichment."""
        with closing(self.connect()) as db:
            row=db.execute("SELECT e.payload_json,e.session_id,e.type,s.submission_json FROM events e LEFT JOIN event_submissions s ON s.event_id=e.event_id WHERE e.event_id=?",(event_id,)).fetchone()
        if not row:return None
        if row["session_id"]!=session_id or row["type"]!=event_type:
            raise ValueError("event_id already exists with a different payload")
        if row["submission_json"] is None:return None
        if json.loads(row["submission_json"])!=submission:
            raise ValueError("event_id already exists with a different payload")
        return json.loads(row["payload_json"])

    def create_training_block(self, block_id: str, learner_id: str, session_id: str, tier: str, version: str,
                              exercise_id: str = "EX-02", dimension: str = "reasoning") -> dict[str, Any]:
        now=utc_now()
        with closing(self.connect()) as db:
            db.execute("INSERT INTO training_blocks(block_id,learner_id,session_id,tier,exercise_version,status,started_at,exercise_id,dimension) VALUES (?,?,?,?,?,'active',?,?,?)",
                       (block_id,learner_id,session_id,tier,version,now,exercise_id,dimension))
        return self.get_training_block(block_id)  # type: ignore[return-value]

    def get_training_block(self, block_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db: row=db.execute("SELECT * FROM training_blocks WHERE block_id=?",(block_id,)).fetchone()
        return dict(row) if row else None

    def add_event(self, event_id: str, session_id: str, event_type: str, payload: dict[str, Any], unique_baseline_item_id: str | None = None, training_block_id: str | None = None, unique_assessment_item: bool = False, submission: dict[str, Any] | None = None) -> tuple[dict[str, Any], bool]:
        identity=self._event_identity(payload); canonical=json.dumps(payload,sort_keys=True,separators=(",",":")); now=utc_now()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT payload_json,session_id,type FROM events WHERE event_id=?",(event_id,)).fetchone()
            if old:
                if self._event_identity(json.loads(old["payload_json"])) != identity or old["session_id"] != session_id or old["type"] != event_type: raise ValueError("event_id already exists with a different payload")
                db.commit(); return json.loads(old["payload_json"]),True
            if not db.execute("SELECT 1 FROM sessions WHERE id=?",(session_id,)).fetchone(): db.rollback(); raise KeyError("session not found")
            if unique_baseline_item_id is not None:
                old_rows=db.execute("SELECT payload_json FROM events WHERE session_id=? AND type='assessment_trial_completed'",(session_id,)).fetchall()
                for row in old_rows:
                    p=json.loads(row["payload_json"]); interaction=p.get("interaction",{})
                    if p.get("item_id")==unique_baseline_item_id and p.get("exercise_id")==payload.get("exercise_id") and not interaction.get("visibility_interrupted",False) and interaction.get("hint_count",0)==0:
                        db.rollback(); raise ValueError("a valid baseline response for this item already exists in this session")
            if unique_assessment_item:
                old_rows=db.execute("SELECT payload_json FROM events WHERE session_id=? AND type='reassessment_trial_completed'",(session_id,)).fetchall()
                for row in old_rows:
                    p=json.loads(row["payload_json"]); interaction=p.get("interaction",{})
                    if (p.get("phase")=="reassessment" and p.get("exercise_id")==payload.get("exercise_id")
                        and p.get("item_id")==payload.get("item_id") and not interaction.get("visibility_interrupted",False)
                        and interaction.get("hint_count",0)==0):
                        db.rollback(); raise ValueError("an eligible response for this reassessment item already exists in this session")
            if training_block_id is not None:
                block=db.execute("SELECT session_id FROM training_blocks WHERE block_id=?",(training_block_id,)).fetchone()
                if not block or block["session_id"] != session_id: db.rollback(); raise KeyError("training block not found for session")
                rows=db.execute("SELECT payload_json FROM events WHERE type='training_trial_completed'").fetchall()
                for row in rows:
                    p=json.loads(row["payload_json"]); interaction=p.get("interaction",{})
                    # Interrupted items remain retryable; a hinted response is retained as coached evidence.
                    if (p.get("training_block_id")==training_block_id and p.get("item_id")==payload.get("item_id")
                            and not interaction.get("visibility_interrupted",False)):
                        db.rollback(); raise ValueError("this item already has a non-interrupted response in the training block")
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)",(event_id,session_id,event_type,canonical,now))
            if submission is not None:
                db.execute("INSERT INTO event_submissions VALUES (?,?)",(event_id,json.dumps(submission,sort_keys=True,separators=(",",":"))))
            db.commit()
        return payload,False

    def events(self, learner_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        sql="SELECT e.*,s.started_at AS session_started_at FROM events e JOIN sessions s ON s.id=e.session_id WHERE 1=1"; params=[]
        if learner_id: sql+=" AND s.learner_id=?"; params.append(learner_id)
        if session_id: sql+=" AND e.session_id=?"; params.append(session_id)
        sql+=" ORDER BY e.created_at,e.event_id"
        with closing(self.connect()) as db: rows=db.execute(sql,params).fetchall()
        return [{**dict(r),"payload":json.loads(r["payload_json"])} for r in rows]

    def block_events(self, block_id: str) -> list[dict[str, Any]]:
        return [e for e in self.events() if e["payload"].get("training_block_id")==block_id and e["type"]=="training_trial_completed"]

    def save_decision_once(self, decision: dict[str, Any]) -> bool:
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM difficulty_decisions WHERE block_id=?",(decision["block_id"],)).fetchone(): db.rollback(); return False
            db.execute("INSERT INTO difficulty_decisions(block_id,learner_id,session_id,old_tier,new_tier,action,rule_version,successes,trial_count,valid_trial_count,rationale,reason_codes_json,evidence_ids_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(decision["block_id"],decision["learner_id"],decision["session_id"],decision["old_tier"],decision["new_tier"],decision["action"],decision["rule_version"],decision["successes"],decision["trial_count"],decision["valid_trial_count"],decision["rationale"],json.dumps(decision["reason_codes"]),json.dumps(decision["evidence_ids"]),decision["created_at"]))
            event={"event_id":decision["event_id"],"learner_id":decision["learner_id"],"session_id":decision["session_id"],"event_type":"difficulty_changed","phase":"training","dimension":decision.get("dimension","reasoning"),"exercise_id":decision.get("exercise_id","EX-02"),"training_block_id":decision["block_id"],"old_tier":decision["old_tier"],"new_tier":decision["new_tier"],"action":decision["action"],"policy_version":decision["rule_version"],"observed":{"successes":decision["successes"],"eligible_trial_count":decision["valid_trial_count"],"trial_count":decision["trial_count"],"success_definition":decision.get("success_definition")},"reason_codes":decision["reason_codes"],"evidence_ids":decision["evidence_ids"],"rationale":decision["rationale"],"sample_data":False,"recorded_at":decision["created_at"]}
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)",(decision["event_id"],decision["session_id"],"difficulty_changed",json.dumps(event,sort_keys=True,separators=(",",":")),decision["created_at"]))
            db.execute("UPDATE training_blocks SET status='completed' WHERE block_id=?",(decision["block_id"],))
            db.commit(); return True

    def get_decision(self, block_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db: row=db.execute("SELECT * FROM difficulty_decisions WHERE block_id=?",(block_id,)).fetchone()
        if not row: return None
        item=dict(row); item["reason_codes"]=json.loads(item.pop("reason_codes_json")); item["evidence_ids"]=json.loads(item.pop("evidence_ids_json")); return item

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        with closing(self.connect()) as db: db.execute("INSERT INTO profile_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)",(snapshot["id"],snapshot["learner_id"],snapshot["scoring_version"],snapshot["dimension"],snapshot["index_0_100"],snapshot["uncertainty_status"],snapshot["evidence_count"],int(snapshot["completed"]),json.dumps(snapshot["evidence_ids"]),snapshot["interrupted_count"],snapshot["created_at"]))

    def latest_snapshot(self, learner_id: str, dimension: str | None = None) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            if dimension: row=db.execute("SELECT * FROM profile_snapshots WHERE learner_id=? AND dimension=? ORDER BY rowid DESC LIMIT 1",(learner_id,dimension)).fetchone()
            else: row=db.execute("SELECT * FROM profile_snapshots WHERE learner_id=? ORDER BY rowid DESC LIMIT 1",(learner_id,)).fetchone()
        if not row:return None
        item=dict(row); item["evidence_ids"]=json.loads(item.pop("evidence_ids_json")); item["completed"]=bool(item["completed"]); return item

    def save_recommendation(self,item:dict[str,Any],snapshot_id:str|None)->None:
        with closing(self.connect()) as db: db.execute("INSERT INTO recommendations VALUES (?,?,?,?,?,?,?,?,?,?)",(item["id"],item["learner_id"],snapshot_id,item["policy_version"],item["action"],item["exercise_id"],item["tier"],json.dumps(item["reason_codes"]),json.dumps(item["evidence_ids"]),item["created_at"]))

    def recommendations(self,learner_id:str)->list[dict[str,Any]]:
        with closing(self.connect()) as db: rows=db.execute("SELECT * FROM recommendations WHERE learner_id=? ORDER BY rowid",(learner_id,)).fetchall()
        out=[]
        for row in rows:
            item=dict(row); item["reason_codes"]=json.loads(item.pop("reason_codes_json")); item["evidence_ids"]=json.loads(item.pop("evidence_ids_json")); out.append(item)
        return out





    def save_plan(self, plan: dict[str, Any]) -> None:
        extra = {key: plan[key] for key in ("plan_version", "ranking_policy_version", "planned_minutes",
                                            "unused_minutes", "budget_note", "budget_adjustment", "ranking",
                                            "superseded_steps", "trigger", "schema_version", "availability",
                                            "resolved_next_step", "resolved_snapshot", "personalized_practice",
                                            "deferred_core_steps")
                 if key in plan}
        with closing(self.connect()) as db:
            db.execute("INSERT INTO training_plans(plan_id,learner_id,profile_snapshot_id,policy_version,goal,"
                       "budget_minutes,estimated_time_minutes,reason_codes_json,rationale,steps_json,evidence_ids_json,"
                       "features_json,alternatives_json,decision_fingerprint,status,created_at,plan_extra_json) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan["plan_id"],plan["learner_id"],plan.get("profile_snapshot_id"),plan["policy_version"],plan.get("goal"),
                 plan["budget_minutes"],plan.get("estimated_time_minutes", plan.get("planned_minutes", 0)),
                 json.dumps(plan["reason_codes"]),plan["rationale"],
                 json.dumps(plan["steps"]),json.dumps(plan["evidence_ids"]),json.dumps(plan["features"]),
                 json.dumps(plan["alternatives"]),json.dumps(plan["decision_fingerprint"]),plan["status"],plan["created_at"],
                 json.dumps(extra, sort_keys=True, separators=(",", ":"))))

    def plans(self, learner_id: str) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows=db.execute("SELECT * FROM training_plans WHERE learner_id=? ORDER BY rowid",(learner_id,)).fetchall()
        result=[]
        for row in rows:
            item=dict(row)
            extra=item.pop("plan_extra_json",None)
            for key in ("reason_codes_json","steps_json","evidence_ids_json","features_json","alternatives_json"):
                value=item.pop(key)
                item[key.removesuffix("_json")]=json.loads(value)
            item["decision_fingerprint"]=json.loads(item["decision_fingerprint"])
            if extra:
                item.update(json.loads(extra))
            item.setdefault("plan_version","plan-v1")
            result.append(item)
        return result

    def latest_plan(self, learner_id: str) -> dict[str, Any] | None:
        rows=self.plans(learner_id)
        return rows[-1] if rows else None

    def snapshots(self, learner_id: str) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows = db.execute("SELECT * FROM profile_snapshots WHERE learner_id=? ORDER BY rowid", (learner_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["evidence_ids"] = json.loads(item.pop("evidence_ids_json"))
            item["completed"] = bool(item["completed"])
            result.append(item)
        return result

    def current_preferences(self, learner_id: str,
                            canonical_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with closing(self.connect()) as db:
            row = db.execute("SELECT dashboard_mode,goal_dimension FROM sessions WHERE learner_id=? ORDER BY started_at DESC,rowid DESC LIMIT 1", (learner_id,)).fetchone()
        preferences=dict(row) if row else {"dashboard_mode":"analytics","goal_dimension":None}
        # Explicit preference events survive a later anonymous session with defaults.
        # Callers that already loaded a canonical event snapshot can derive
        # event-backed preferences from that same revision without a second scan.
        events = canonical_events if canonical_events is not None else self.events(learner_id=learner_id)
        for event in events:
            payload=event["payload"]
            if event["type"]=="dashboard_mode_changed" and payload.get("dashboard_mode") in {"analytics","rpg"}:
                preferences["dashboard_mode"]=payload["dashboard_mode"]
            if event["type"]=="user_goal_updated" and "goal_dimension" in payload:
                preferences["goal_dimension"]=payload["goal_dimension"]
        return preferences

    def set_preferences(self, session_id: str, mode: str, goal: str | None) -> dict[str, Any]:
        session = self.get_session(session_id)
        with closing(self.connect()) as db:
            db.execute("UPDATE sessions SET dashboard_mode=?,goal_dimension=? WHERE id=?", (mode,goal,session_id))
        import uuid
        changes = []
        if session["dashboard_mode"] != mode:
            changes.append(("dashboard_mode_changed", {"old_mode": session["dashboard_mode"], "dashboard_mode": mode}))
        if session.get("goal_dimension") != goal:
            changes.append(("user_goal_updated", {"goal_dimension": goal, "source": "explicit_user_preference"}))
        for event_type, details in changes:
            event_id = str(uuid.uuid4())
            self.add_event(event_id, session_id, event_type, {"event_id": event_id, "session_id": session_id,
                "learner_id": session["learner_id"], "event_type": event_type, **details, "sample_data": False, "recorded_at": utc_now()})
        return {"dashboard_mode": mode, "goal_dimension": goal}

    # --- coach-v2 conversation persistence -------------------------------------------------
    def coach_turn(self, request_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM coach_turns WHERE request_id=?", (request_id,)).fetchone()
        return self._coach_row(row) if row else None

    @staticmethod
    def _coach_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["request"] = json.loads(item.pop("request_json"))
        item["response"] = json.loads(item.pop("response_json")) if item.get("response_json") else None
        item["progress"] = json.loads(item.pop("progress_json")) if item.get("progress_json") else None
        return item

    def save_coach_progress(self, request_id: str, progress: dict[str, Any], *,
                            lifecycle_generation: int) -> dict[str, Any]:
        """Persist the server-authored early answer while the original turn owns its reservation."""
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT t.status,t.learner_id,t.lifecycle_generation,l.generation,l.deleting "
                "FROM coach_turns t JOIN learner_lifecycle l ON l.learner_id=t.learner_id "
                "WHERE t.request_id=?", (request_id,),
            ).fetchone()
            if (not row or row["status"] != "in_progress" or row["deleting"]
                    or int(row["generation"]) != lifecycle_generation
                    or int(row["lifecycle_generation"]) != lifecycle_generation):
                db.rollback()
                raise CoachRequestInvalidated("reserved coaching request was invalidated")
            db.execute("UPDATE coach_turns SET progress_json=?,updated_at=? WHERE request_id=? AND status='in_progress'",
                       (json.dumps(progress, sort_keys=True, separators=(",", ":")), utc_now(), request_id))
            db.commit()
        return self.coach_turn(request_id)  # type: ignore[return-value]

    def reserve_coach_turn(self, turn: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Atomically claim a request before any coach/provider work starts.

        A completed request is replayable, an active request is owned by the
        first caller, and a failed request may be deliberately retried with the
        same canonical payload.  The payload hash is checked while holding the
        write lock so a conflicting retry cannot reach the provider.
        """
        now = utc_now()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            now = utc_now()
            db.execute(
                "INSERT INTO learner_lifecycle(learner_id,generation,deleting,updated_at) VALUES(?,?,0,?) "
                "ON CONFLICT(learner_id) DO NOTHING",
                (turn["learner_id"], 0, now),
            )
            lifecycle = db.execute(
                "SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                (turn["learner_id"],),
            ).fetchone()
            if lifecycle["deleting"]:
                db.rollback()
                raise CoachRequestInvalidated("learner deletion is in progress")
            generation = int(lifecycle["generation"])
            existing = db.execute("SELECT * FROM coach_turns WHERE request_id=?",
                                  (turn["request_id"],)).fetchone()
            if existing:
                if existing["payload_hash"] != turn["payload_hash"]:
                    db.rollback()
                    raise ValueError("request_id already exists with a different payload")
                if existing["status"] == "completed" and existing["response_json"]:
                    db.commit()
                    return self._coach_row(existing), False
                if existing["status"] == "in_progress":
                    if seconds_since(existing["updated_at"]) < STALE_IN_PROGRESS_SECONDS:
                        db.commit()
                        return self._coach_row(existing), False
                    db.execute(
                        "UPDATE coach_turns SET status='in_progress',response_json=NULL,progress_json=NULL,error_code=NULL,updated_at=? "
                        "WHERE request_id=? AND payload_hash=?",
                        (now, turn["request_id"], turn["payload_hash"]),
                    )
                    db.commit()
                    return self.coach_turn(turn["request_id"]), True  # type: ignore[return-value]
                db.execute(
                    "UPDATE coach_turns SET status='in_progress',response_json=NULL,progress_json=NULL,error_code=NULL,updated_at=? "
                    "WHERE request_id=? AND payload_hash=?",
                    (now, turn["request_id"], turn["payload_hash"]),
                )
                db.commit()
                return self.coach_turn(turn["request_id"]), True  # type: ignore[return-value]
            db.execute(
                "INSERT INTO coach_turns(request_id,learner_id,session_id,subject_exercise_id,subject_dimension,"
                "subject_source,provider_requested,provider_used,model,coach_version,payload_hash,status,message,"
                "evidence_revision,request_json,response_json,error_code,created_at,updated_at,lifecycle_generation) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (turn["request_id"], turn["learner_id"], turn["session_id"], turn.get("subject_exercise_id"),
                 turn.get("subject_dimension"), turn.get("subject_source"), turn.get("provider_requested"),
                 turn.get("provider_used"), turn.get("model"), turn["coach_version"], turn["payload_hash"],
                 "in_progress", turn["message"], turn.get("evidence_revision"),
                 json.dumps(turn["request"], sort_keys=True, separators=(",", ":")), None, None, now, now, generation),
            )
            db.commit()
        return self.coach_turn(turn["request_id"]), True  # type: ignore[return-value]

    def save_coach_turn(self, turn: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible insert helper for existing callers.

        New HTTP requests use :meth:`reserve_coach_turn` so reservation occurs
        before generation.  This helper remains for older integrations.
        """
        now = utc_now()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM coach_turns WHERE request_id=?", (turn["request_id"],)).fetchone()
            if existing:
                db.commit()
                if existing["payload_hash"] != turn["payload_hash"]:
                    raise ValueError("request_id already exists with a different payload")
                return self._coach_row(existing)
            db.execute("INSERT INTO coach_turns(request_id,learner_id,session_id,subject_exercise_id,subject_dimension,"
                       "subject_source,provider_requested,provider_used,model,coach_version,payload_hash,status,message,"
                       "evidence_revision,request_json,response_json,error_code,created_at,updated_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (turn["request_id"], turn["learner_id"], turn["session_id"], turn.get("subject_exercise_id"),
                        turn.get("subject_dimension"), turn.get("subject_source"), turn.get("provider_requested"),
                        turn.get("provider_used"), turn.get("model"), turn["coach_version"], turn["payload_hash"],
                        turn["status"], turn["message"], turn.get("evidence_revision"),
                        json.dumps(turn["request"], sort_keys=True, separators=(",", ":")), None,
                        turn.get("error_code"), now, now))
            db.commit()
        return self.coach_turn(turn["request_id"])  # type: ignore[return-value]

    def complete_coach_turn(self, request_id: str, *, response: dict[str, Any], status: str,
                            provider_used: str, model: str | None, error_code: str | None = None,
                            lifecycle_generation: int | None = None) -> dict[str, Any]:
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status, response_json FROM coach_turns WHERE request_id=?", (request_id,)).fetchone()
            if not row:
                db.rollback()
                raise CoachRequestInvalidated("reserved coaching request was deleted")
            if lifecycle_generation is not None:
                lifecycle = db.execute(
                    "SELECT generation,deleting FROM learner_lifecycle l "
                    "JOIN coach_turns t ON t.learner_id=l.learner_id WHERE t.request_id=?",
                    (request_id,),
                ).fetchone()
                if not lifecycle or lifecycle["deleting"] or int(lifecycle["generation"]) != lifecycle_generation:
                    db.rollback()
                    raise CoachRequestInvalidated("reserved coaching request was invalidated")
            if row["response_json"] is None:
                db.execute("UPDATE coach_turns SET status=?,response_json=?,progress_json=NULL,provider_used=?,model=?,error_code=?,updated_at=? "
                           "WHERE request_id=?", (status, json.dumps(response, sort_keys=True, separators=(",", ":")),
                                                  provider_used, model, error_code, utc_now(), request_id))
            db.commit()
        return self.coach_turn(request_id)  # type: ignore[return-value]

    def record_coach_event(self, *, request_id: str, learner_id: str, session_id: str,
                           lifecycle_generation: int, event_id: str, payload: dict[str, Any],
                           provider: str, consent_recorded: bool,
                           subject_exercise_id: str | None) -> tuple[dict[str, Any], bool]:
        """Record event and conversation only while the reservation still owns the learner."""
        canonical=json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            lifecycle = db.execute(
                "SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                (learner_id,),
            ).fetchone()
            reservation = db.execute(
                "SELECT status,lifecycle_generation FROM coach_turns WHERE request_id=? AND learner_id=? "
                "AND session_id=?", (request_id, learner_id, session_id),
            ).fetchone()
            if (not lifecycle or lifecycle["deleting"] or int(lifecycle["generation"]) != lifecycle_generation
                    or not reservation or reservation["status"] != "in_progress"
                    or int(reservation["lifecycle_generation"]) != lifecycle_generation):
                db.rollback()
                raise CoachRequestInvalidated("reserved coaching request was invalidated by learner deletion")
            existing = db.execute(
                "SELECT payload_json,session_id,type FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            replayed = False
            if existing:
                if (existing["session_id"] != session_id or existing["type"] != "coaching_message_sent"
                        or self._event_identity(json.loads(existing["payload_json"])) != self._event_identity(payload)):
                    db.rollback()
                    raise ValueError("event_id already exists with a different payload")
                replayed = True
            else:
                if not db.execute("SELECT 1 FROM sessions WHERE id=? AND learner_id=?",
                                  (session_id, learner_id)).fetchone():
                    db.rollback()
                    raise CoachRequestInvalidated("learner session was deleted")
                db.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                           (event_id, session_id, "coaching_message_sent", canonical, utc_now()))
            db.execute(
                "INSERT INTO coach_conversations(session_id,learner_id,subject_exercise_id,provider,consent_recorded,updated_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET subject_exercise_id=excluded.subject_exercise_id,"
                "provider=excluded.provider,consent_recorded=excluded.consent_recorded,updated_at=excluded.updated_at",
                (session_id, learner_id, subject_exercise_id, provider, int(consent_recorded), utc_now()),
            )
            db.commit()
        return payload, replayed

    def fail_coach_turn(self, request_id: str, error_code: str) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE coach_turns SET status='failed',error_code=?,updated_at=? "
                "WHERE request_id=? AND status!='completed'",
                (error_code[:200], utc_now(), request_id),
            )

    def coach_turns(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            rows = db.execute("SELECT * FROM coach_turns WHERE session_id=? ORDER BY rowid DESC LIMIT ?",
                              (session_id, limit)).fetchall()
        return [self._coach_row(row) for row in reversed(rows)]

    def coach_conversation(self, session_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM coach_conversations WHERE session_id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def set_coach_conversation(self, session_id: str, learner_id: str, provider: str,
                               consent_recorded: bool, subject_exercise_id: str | None = None) -> dict[str, Any]:
        with closing(self.connect()) as db:
            db.execute("INSERT INTO coach_conversations(session_id,learner_id,subject_exercise_id,provider,consent_recorded,updated_at) "
                       "VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET subject_exercise_id=excluded.subject_exercise_id,"
                       "provider=excluded.provider,consent_recorded=excluded.consent_recorded,updated_at=excluded.updated_at",
                       (session_id, learner_id, subject_exercise_id, provider, int(consent_recorded), utc_now()))
        return self.coach_conversation(session_id)  # type: ignore[return-value]
