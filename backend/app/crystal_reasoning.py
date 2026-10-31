"""Separate, versioned visual matrix form. Never contributes to hybrid or EX scores."""
from __future__ import annotations
import hashlib, json, uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .storage import Store

FORM_VERSION = "crystal-reasoning-v1"
GENERATOR_VERSION = "crystal-cyclic-count-v1"
EVALUATION_VERSION = "crystal-count-eval-v1"

CAPABILITY_METADATA = {
    "activity_id": "CRYSTAL",
    "activity_version": FORM_VERSION,
    "form_version": FORM_VERSION,
    "config_version": GENERATOR_VERSION,
    "generator_version": GENERATOR_VERSION,
    "evaluation_version": EVALUATION_VERSION,
    "title": "Crystal Reasoning",
    "status": "playable",
    "family_relevance": ["reasoning"],
    "relevance_scope": "task_mechanics_only_not_assessment",
    "estimated_duration_minutes": 3,
    "duration_estimate_status": "provisional_unmeasured",
    "duration_estimate_basis": "initial_plan_budget_guess_not_observed",
    "supported_modes": ["single_prompt"],
    "assistance_windows": [],
    "supported_lifecycle": {
        "attempt_states": ["active", "completed"],
        "outcome_states": ["completed"],
        "recoverable_states": ["active"],
        "exact_start_retry": True,
        "exact_answer_retry": True,
        "exact_completion_retry": True,
        "interruption_recorded": False,
    },
    "contributions": {
        "baseline_indices": False,
        "ex_difficulty_tiers": False,
        "participation_xp": False,
    },
    "personalized_plan_status": "not_integrated",
}

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
class Start(Strict):
    event_id: str
    session_id: str
    learner_id: str = "demo-user"
    seed: str | None = None
class Answer(Strict):
    event_id: str
    choice_id: str
    response_time_ms: int | None = Field(default=None, ge=0)

def _now(): return datetime.now(timezone.utc).isoformat()
def _config(seed: str) -> dict[str, Any]:
    # The approved plate uses a cyclic crystal-count matrix. Keep counts small
    # enough to render as actual crystal sprites rather than numeric proxies.
    digest = hashlib.sha256(seed.encode()).digest()
    cycle = [1, 2, 3] if digest[0] % 2 == 0 else [3, 2, 1]
    offset = digest[1] % 3
    cycle = cycle[offset:] + cycle[:offset]
    grid = [[cycle[(row + col) % 3] for col in range(3)] for row in range(3)]
    values = [1, 2, 3, 4]
    offset = digest[2] % 4
    values = values[offset:] + values[:offset]
    return {"form_version": FORM_VERSION, "generator_version": GENERATOR_VERSION,
            "prompt": "The crystal counts shift one place along each row. Which piece completes the pattern?",
            "grid": [[grid[r][c] if (r,c)!=(2,2) else None for c in range(3)] for r in range(3)],
            "choices": [{"choice_id": f"choice-{i+1}", "value": value} for i,value in enumerate(values)]}

def register_crystal_routes(app: FastAPI, store: Store) -> None:
    with closing(store.connect()) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS crystal_attempts(attempt_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), learner_id TEXT NOT NULL, form_version TEXT NOT NULL, generator_version TEXT NOT NULL, seed TEXT NOT NULL, config_json TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crystal_events(event_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES crystal_attempts(attempt_id), session_id TEXT NOT NULL REFERENCES sessions(id), sequence INTEGER NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(attempt_id, sequence));
        CREATE TABLE IF NOT EXISTS crystal_outcomes(attempt_id TEXT PRIMARY KEY REFERENCES crystal_attempts(attempt_id), session_id TEXT NOT NULL REFERENCES sessions(id), learner_id TEXT NOT NULL, form_version TEXT NOT NULL, generator_version TEXT NOT NULL, evaluation_version TEXT NOT NULL, choice_id TEXT NOT NULL, correct INTEGER NOT NULL, response_time_ms INTEGER, evidence_ids_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS crystal_events_no_update BEFORE UPDATE ON crystal_events BEGIN SELECT RAISE(ABORT,'crystal events are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS crystal_events_no_delete BEFORE DELETE ON crystal_events BEGIN SELECT RAISE(ABORT,'crystal events are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS crystal_outcomes_no_update BEFORE UPDATE ON crystal_outcomes BEGIN SELECT RAISE(ABORT,'crystal outcomes are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS crystal_outcomes_no_delete BEFORE DELETE ON crystal_outcomes BEGIN SELECT RAISE(ABORT,'crystal outcomes are immutable'); END;
        """)

    @app.get("/api/crystal/catalog")
    def crystal_catalog():
        return {**CAPABILITY_METADATA}

    @app.post("/api/crystal/attempts", status_code=201)
    def start(body: Start):
        session = store.get_session(body.session_id)
        if not session: raise HTTPException(404, "session not found")
        if session["learner_id"] != body.learner_id: raise HTTPException(403, "learner does not own session")
        seed = body.seed or hashlib.sha256(f"{body.session_id}|{body.event_id}".encode()).hexdigest()[:16]
        config = _config(seed); now = _now()
        with closing(store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            prev = db.execute("SELECT * FROM crystal_events WHERE event_id=?", (body.event_id,)).fetchone()
            if prev:
                expected={"session_id":body.session_id,"learner_id":body.learner_id,"seed":seed,"form_version":FORM_VERSION,"generator_version":GENERATOR_VERSION}
                if prev["event_type"] != "crystal_started" or json.loads(prev["payload_json"]) != expected: raise HTTPException(409, "event id conflicts")
                row = db.execute("SELECT * FROM crystal_attempts WHERE attempt_id=?", (prev["attempt_id"],)).fetchone()
                db.commit()
                return {"attempt_id":row["attempt_id"], "event_id":body.event_id,
                        "config":json.loads(row["config_json"]), "status":row["status"],
                        "form_version":row["form_version"], "generator_version":row["generator_version"],
                        "capabilities":CAPABILITY_METADATA, "replayed":True}
            aid = str(uuid.uuid4()); payload = {"session_id":body.session_id,"learner_id":body.learner_id,"seed":seed,"form_version":FORM_VERSION,"generator_version":GENERATOR_VERSION}
            db.execute("INSERT INTO crystal_attempts VALUES(?,?,?,?,?,?,?,?,?)",(aid,body.session_id,body.learner_id,FORM_VERSION,GENERATOR_VERSION,seed,json.dumps(config,sort_keys=True),"active",now))
            db.execute("INSERT INTO crystal_events VALUES(?,?,?,?,?,?,?)",(body.event_id,aid,body.session_id,1,"crystal_started",json.dumps(payload,sort_keys=True),now))
            db.commit()
        return {"attempt_id":aid,"event_id":body.event_id,"config":config,"status":"active",
                "form_version":FORM_VERSION,"generator_version":GENERATOR_VERSION,
                "capabilities":CAPABILITY_METADATA,"replayed":False}

    @app.post("/api/crystal/attempts/{attempt_id}/answer")
    def answer(attempt_id: str, body: Answer):
        with closing(store.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM crystal_attempts WHERE attempt_id=?",(attempt_id,)).fetchone()
            if not row: raise HTTPException(404,"crystal attempt not found")
            config=json.loads(row["config_json"]); choice=next((c for c in config["choices"] if c["choice_id"]==body.choice_id),None)
            if not choice: raise HTTPException(422,"unknown choice_id")
            prior = db.execute("SELECT * FROM crystal_events WHERE event_id=?",(body.event_id,)).fetchone()
            if prior:
                payload=json.loads(prior["payload_json"])
                if (prior["attempt_id"]!=attempt_id or prior["event_type"]!="crystal_answered" or
                    payload.get("choice_id")!=body.choice_id or payload.get("response_time_ms")!=body.response_time_ms):
                    raise HTTPException(409,"event id conflicts")
                outcome=db.execute("SELECT * FROM crystal_outcomes WHERE attempt_id=?",(attempt_id,)).fetchone()
                return {"accepted":True,"replayed":True,"sequence":int(prior["sequence"]),
                        "outcome":_public_outcome(outcome) if outcome else None}
            existing=db.execute("SELECT * FROM crystal_events WHERE attempt_id=? AND event_type='crystal_answered'",(attempt_id,)).fetchone()
            if existing: raise HTTPException(409,"attempt already answered")
            if config.get('generator_version') == 'crystal-additive-matrix-v1':
                grid = config['grid']
                expected = grid[0][0] + 2 * (grid[1][0] - grid[0][0]) + 2 * (grid[0][1] - grid[0][0])
                evaluation_version = 'crystal-eval-v1'
            else:
                expected = config['grid'][0][1]
                evaluation_version = EVALUATION_VERSION
            correct=choice["value"]==expected
            now=_now(); payload={"choice_id":body.choice_id,"value":choice["value"],"correct":bool(correct),"response_time_ms":body.response_time_ms}
            db.execute("INSERT INTO crystal_events VALUES(?,?,?,?,?,?,?)",(body.event_id,attempt_id,row["session_id"],2,"crystal_answered",json.dumps(payload,sort_keys=True),now))
            evidence=[r[0] for r in db.execute("SELECT event_id FROM crystal_events WHERE attempt_id=? ORDER BY sequence",(attempt_id,)).fetchall()]
            db.execute("INSERT INTO crystal_outcomes VALUES(?,?,?,?,?,?,?,?,?,?,?)",(attempt_id,row["session_id"],row["learner_id"],row['form_version'],row['generator_version'],evaluation_version,body.choice_id,int(correct),body.response_time_ms,json.dumps(evidence),now))
            db.execute("UPDATE crystal_attempts SET status='completed' WHERE attempt_id=?",(attempt_id,))
            db.commit()
        return {"accepted":True,"replayed":False,"sequence":2,"outcome":{"attempt_id":attempt_id,"form_version":row['form_version'],"generator_version":row['generator_version'],"evaluation_version":evaluation_version,"correct":bool(correct),"choice_id":body.choice_id,"response_time_ms":body.response_time_ms,"evidence_ids":evidence}}

    @app.get("/api/crystal/attempts/{attempt_id}")
    def get_attempt(attempt_id: str):
        with closing(store.connect()) as db:
            row=db.execute("SELECT * FROM crystal_attempts WHERE attempt_id=?",(attempt_id,)).fetchone()
            if not row: raise HTTPException(404,"crystal attempt not found")
            outcome=db.execute("SELECT * FROM crystal_outcomes WHERE attempt_id=?",(attempt_id,)).fetchone()
        with closing(store.connect()) as db:
            rows=db.execute("SELECT event_id,sequence,event_type,payload_json,created_at FROM crystal_events WHERE attempt_id=? ORDER BY sequence",(attempt_id,)).fetchall()
        return {"attempt_id":attempt_id,"session_id":row["session_id"],"learner_id":row["learner_id"],
                "status":row["status"],"form_version":row["form_version"],
                "generator_version":row["generator_version"],"seed":row["seed"],
                "config":json.loads(row["config_json"]),"outcome":_public_outcome(outcome) if outcome else None,
                "events":[{"event_id":event["event_id"],"sequence":event["sequence"],
                            "type":event["event_type"],"payload":json.loads(event["payload_json"]),
                            "created_at":event["created_at"]} for event in rows],
                "capabilities":CAPABILITY_METADATA}

def _public_outcome(row):
    return {"attempt_id":row["attempt_id"],"form_version":row["form_version"],"generator_version":row["generator_version"],"evaluation_version":row["evaluation_version"],"correct":bool(row["correct"]),"choice_id":row["choice_id"],"response_time_ms":row["response_time_ms"],"evidence_ids":json.loads(row["evidence_ids_json"])}
