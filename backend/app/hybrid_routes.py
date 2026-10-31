"""HTTP surface for hybrid-v1 activities.

These routes are additive: they never touch EX scoring, baselines, difficulty tiers,
recommendations or participation XP.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import closing

from fastapi import FastAPI, HTTPException

from . import hybrid_store as hs
from .hybrid_activities import CATALOG, capability_metadata, generate, evaluate, is_implemented, limitations_for
from .hybrid_activities_modules import tidekeeper, harbor_dispatch, shifting_market
from .hybrid_contracts import (
    ASSISTANCE_EXPOSURES,
    ASSISTANCE_WINDOWS,
    HYBRID_SCHEMA_VERSION,
    HybridActionRecord,
    HybridAssistanceRecord,
    HybridAttemptStart,
    HybridCompletionRecord,
)
from .storage import Store

# Windows that only make sense before the player has acted.
PRE_ACTION_WINDOWS = {"pre_play", "pre_encoding", "pre_block", "pre_wave"}
# Windows that only make sense once the attempt is finished.
POST_COMPLETION_WINDOWS = {"post_completion", "post_window"}
# Post-checkpoint help is valid only after its named boundary action. This keeps a
# syntactically allowed assistance window from being exposed at the wrong phase.
POST_ACTION_REQUIREMENTS = {
    ("HY-05", "post_commit"): "commit",
    ("HY-06", "post_commit"): "commit",
}

def _assistance_checkpoint_open(activity_id: str, checkpoint: str, config: dict, actions: list[dict]) -> bool:
    kinds = [e["payload"].get("action_type") for e in actions]
    if activity_id == "HY-03" and checkpoint == "boundary":
        boundary = int(config["switch"]["after_step"])
        return len(kinds) == boundary and all(kind == "select" for kind in kinds)
    if activity_id == "HY-06" and checkpoint == "advice_checkpoint":
        return any(e["payload"].get("action_type") == "commit" and e["payload"].get("action", {}).get("stage") == "proposal" for e in actions)
    if activity_id == "HY-06" and checkpoint == "post_commit":
        return any(e["payload"].get("action_type") == "commit" and e["payload"].get("action", {}).get("stage") == "resolution" for e in actions)
    if activity_id == "HY-04" and checkpoint == "between_waves":
        count=len(actions); width=int(config["arrivals_per_wave"]); total=int(config["wave_count"])*width
        return count>0 and count<total and count%width==0
    return True


def _seed_for(body: HybridAttemptStart) -> str:
    if body.seed:
        return body.seed
    digest = hashlib.sha256(f"{body.session_id}|{body.activity_id}|{body.event_id}".encode("utf-8")).hexdigest()
    return digest[:16]

def _public_activity_config(activity_id: str, config: dict):
    if activity_id == "HY-03": return shifting_market.public_config(config)
    if activity_id == "HY-02": return tidekeeper.public_config(config)
    if activity_id == "HY-04": return harbor_dispatch.public_config(config)
    return config


def _is_saved_hy01_v1_start(store: Store, event_id: str) -> bool:
    """Allow only replay of an already-persisted pre-v2 HY-01 start identity."""
    with closing(store.connect()) as db:
        row = db.execute("SELECT type,payload_json FROM hybrid_events WHERE event_id=?", (event_id,)).fetchone()
    if not row or row["type"] != "hybrid_attempt_started":
        return False
    payload = json.loads(row["payload_json"])
    return payload.get("activity_id") == "HY-01" and payload.get("activity_version") == "hy-01-v1"


def register_hybrid_routes(app: FastAPI, store: Store) -> None:
    @app.get("/api/hybrid/catalog")
    def hybrid_catalog():
        return {
            "hybrid_schema_version": HYBRID_SCHEMA_VERSION,
            "note": "Hybrid activities are separate from the five fixed baseline indices and carry no cognitive score.",
            "activities": [capability_metadata(activity_id)
                           for activity_id in CATALOG if is_implemented(activity_id)],
        }

    @app.post("/api/hybrid/attempts", status_code=201)
    def start_attempt(body: HybridAttemptStart):
        if not is_implemented(body.activity_id):
            raise HTTPException(status_code=501, detail=f"{body.activity_id} is not implemented yet")
        legacy_hy01_replay = (body.activity_id == "HY-01" and body.activity_version == "hy-01-v1"
                              and body.config_version == "1" and _is_saved_hy01_v1_start(store, body.event_id))
        if body.activity_version != CATALOG[body.activity_id]["activity_version"] and not legacy_hy01_replay:
            raise HTTPException(status_code=409, detail="unknown activity_version for this activity")
        if body.config_version != CATALOG[body.activity_id]["config_version"] and not legacy_hy01_replay:
            raise HTTPException(status_code=409, detail="unknown config_version for this activity")
        if body.difficulty_tier not in {"tutorial", "tier-1", "tier-2", "tier-3"}:
            raise HTTPException(status_code=422, detail="difficulty_tier must be tutorial or tier-1 through tier-3")
        session = store.get_session(body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        if session["learner_id"] != body.learner_id:
            raise HTTPException(status_code=403, detail="learner does not own session")
        seed = _seed_for(body)
        config = generate(body.activity_id, seed, body.mode, body.difficulty_tier, body.activity_version)
        attempt_id = str(uuid.uuid4())
        payload = {
            "event_type": "hybrid_attempt_started",
            "attempt_id": attempt_id,
            "session_id": body.session_id,
            "learner_id": body.learner_id,
            "activity_id": body.activity_id,
            "activity_version": body.activity_version,
            "mode": body.mode,
            "config_version": body.config_version,
            "difficulty_tier": body.difficulty_tier,
            "seed": seed,
            "hybrid_schema_version": HYBRID_SCHEMA_VERSION,
        }
        attempt = {
            "attempt_id": attempt_id,
            "learner_id": body.learner_id,
            "session_id": body.session_id,
            "activity_id": body.activity_id,
            "activity_version": body.activity_version,
            "mode": body.mode,
            "config_version": body.config_version,
            "difficulty_tier": body.difficulty_tier,
            "seed": seed,
            "config": config,
            "event_id": body.event_id,
            "event_payload": payload,
        }
        try:
            stored = hs.create_attempt(store, attempt)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except hs.HybridConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        import json as _json
        return {
            "attempt_id": stored["attempt_id"],
            "event_id": body.event_id,
            "session_id": stored["session_id"],
            "learner_id": stored["learner_id"],
            "activity_id": stored["activity_id"],
            "activity_version": stored["activity_version"],
            "mode": stored["mode"],
            "config_version": stored["config_version"],
            "seed": stored["seed"],
            "difficulty_tier": stored["difficulty_tier"],
            "hybrid_schema_version": HYBRID_SCHEMA_VERSION,
            "config": _public_activity_config(stored["activity_id"], _json.loads(stored["config_json"])),
            "capabilities": capability_metadata(stored["activity_id"]),
            "assistance": {
                "windows": list(ASSISTANCE_WINDOWS[stored["activity_id"]]),
                "exposures": list(ASSISTANCE_EXPOSURES),
                "policy": "Any revealed intention, replayed hidden cue, hint or oracle route marks the attempt assisted and excludes it from unassisted summaries.",
            },
            "created_at": stored["started_at"],
        }

    @app.get("/api/hybrid/attempts/{attempt_id}")
    def read_attempt(attempt_id: str):
        attempt = hs.get_attempt(store, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="hybrid attempt not found")
        import json as _json
        return {
            "attempt_id": attempt["attempt_id"],
            "session_id": attempt["session_id"],
            "learner_id": attempt["learner_id"],
            "activity_id": attempt["activity_id"],
            "activity_version": attempt["activity_version"],
            "mode": attempt["mode"],
            "config_version": attempt["config_version"],
            "difficulty_tier": attempt["difficulty_tier"],
            "seed": attempt["seed"],
            "status": attempt["status"],
            "started_at": attempt["started_at"],
            "completed_at": attempt["completed_at"],
            "config": _public_activity_config(attempt["activity_id"], _json.loads(attempt["config_json"])),
            "events": [{"event_id": e["event_id"], "sequence": e["sequence"], "type": e["type"], "payload": e["payload"]}
                       for e in hs.attempt_events(store, attempt_id)],
            "assistance": hs.assistance_records(store, attempt_id),
            "outcome": hs.get_outcome(store, attempt_id),
            "capabilities": capability_metadata(attempt["activity_id"]),
        }

    @app.get("/api/hybrid/attempts/{attempt_id}/review-history")
    def read_hy02_review_history(attempt_id: str, session_id: str, assistance_event_id: str):
        """Return only already-played HY-02 cues after completion and recorded replay assistance.

        The persisted oracle stream is the historical source of truth. Never regenerate
        from a seed here: older generator implementations may not remain available.
        """
        attempt = hs.get_attempt(store, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="hybrid attempt not found")
        if attempt["session_id"] != session_id:
            raise HTTPException(status_code=403, detail="session does not own attempt")
        if attempt["activity_id"] != "HY-02":
            raise HTTPException(status_code=409, detail="review history is only available for HY-02")

        try:
            outcome = hs.get_outcome(store, attempt_id)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=409, detail="stored review outcome is malformed")
        if (attempt["status"] != "completed" or not outcome
                or outcome.get("completion_state") != "completed"):
            raise HTTPException(status_code=409, detail="review history requires a completed, non-interrupted attempt")

        try:
            events = hs.attempt_events(store, attempt_id)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=409, detail="stored response events are malformed")
        completion_event = next((event for event in events if event.get("type") == "hybrid_attempt_completed"), None)
        replay_event = next((event for event in events if event.get("event_id") == assistance_event_id), None)
        replay_row = next((row for row in hs.assistance_records(store, attempt_id)
                           if row["event_id"] == assistance_event_id), None)
        replay_payload = replay_event.get("payload") if isinstance(replay_event, dict) else None
        if (not isinstance(completion_event, dict) or not isinstance(replay_event, dict)
                or replay_event.get("type") != "hybrid_assistance_exposed"
                or not isinstance(replay_payload, dict) or replay_row is None
                or replay_payload.get("exposure_kind") != "cue_replay"
                or replay_payload.get("checkpoint") != "post_window"
                or replay_payload.get("source_event_id") != completion_event.get("event_id")
                or type(replay_event.get("sequence")) is not int
                or type(completion_event.get("sequence")) is not int
                or replay_event.get("sequence", -1) <= completion_event.get("sequence", -1)
                or replay_row.get("exposure_kind") != "cue_replay"
                or replay_row.get("checkpoint") != "post_window"
                or replay_row.get("source_event_id") != completion_event.get("event_id")
                or replay_row.get("sequence", -1) != replay_event.get("sequence")):
            raise HTTPException(status_code=409, detail="a recorded post_window cue_replay exposure tied to completion is required")

        try:
            config = json.loads(attempt["config_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=409, detail="stored cue history is unavailable or malformed")
        if not isinstance(config, dict):
            raise HTTPException(status_code=409, detail="stored cue history is unavailable or malformed")
        stream = config.get("_oracle_stream")
        trial_count = config.get("trial_count")
        n_back = config.get("n_back")
        if (type(trial_count) is not int or trial_count <= 0 or type(n_back) is not int or n_back < 1
                or not isinstance(stream, list) or len(stream) != trial_count):
            raise HTTPException(status_code=409, detail="stored cue history is unavailable or incomplete")

        def cue_is_valid(cue: object) -> bool:
            return (isinstance(cue, dict)
                    and isinstance(cue.get("cue_id"), str)
                    and type(cue.get("position")) is int and 0 <= cue["position"] < 9
                    and isinstance(cue.get("symbol"), str) and bool(cue["symbol"]))

        if not all(cue_is_valid(cue) for cue in stream) or len({cue["cue_id"] for cue in stream}) != trial_count:
            raise HTTPException(status_code=409, detail="stored cue history is unavailable or incomplete")

        action_events = [event for event in events if event.get("type") == "hybrid_action_recorded"
                         and isinstance(event.get("payload"), dict)
                         and event["payload"].get("action_type") == "respond"]
        outcome_body = outcome.get("outcomes")
        rows = outcome_body.get("responses") if isinstance(outcome_body, dict) else None
        if (not isinstance(rows, list) or len(rows) != trial_count or len(action_events) != trial_count
                or any(not isinstance(row, dict) for row in rows)):
            raise HTTPException(status_code=409, detail="review history requires a full aligned response sequence")

        trials = []
        for index, (action_event, response) in enumerate(zip(action_events, rows)):
            payload = action_event["payload"].get("action")
            cue = stream[index]
            if not isinstance(payload, dict):
                raise HTTPException(status_code=409, detail="stored response events are malformed")
            expected_prior = stream[index - n_back] if index >= n_back else None
            if (type(payload.get("trial_index")) is not int or payload.get("trial_index") != index
                    or action_event["payload"].get("cue_event_id") != cue["cue_id"]
                    or action_event["payload"].get("action_sequence") != index + 1
                    or type(response.get("trial_index")) is not int or response.get("trial_index") != index
                    or response.get("cue_event_id") != cue["cue_id"]
                    or type(payload.get("position_match")) is not bool
                    or type(payload.get("symbol_match")) is not bool
                    or type(response.get("position_match_expected")) is not bool
                    or type(response.get("symbol_match_expected")) is not bool
                    or type(response.get("position_match_response")) is not bool
                    or type(response.get("symbol_match_response")) is not bool
                    or type(response.get("position_correct")) is not bool
                    or type(response.get("symbol_correct")) is not bool
                    or response.get("position_match_response") is not payload["position_match"]
                    or response.get("symbol_match_response") is not payload["symbol_match"]
                    or response.get("response_time_ms") != action_event["payload"].get("elapsed_ms")):
                raise HTTPException(status_code=409, detail="stored cue history does not align with canonical responses")

            def public_cue(item: dict) -> dict:
                return {"cue_id": item["cue_id"], "position": item["position"], "symbol": item["symbol"]}

            history_start = max(0, index - n_back)
            trials.append({
                "trial_index": index,
                "cue_event_id": cue["cue_id"],
                "history_cues": [public_cue(item) for item in stream[history_start:index]],
                "current_cue": public_cue(cue),
                "comparison_cue": public_cue(expected_prior) if expected_prior is not None else None,
                "response_time_ms": response["response_time_ms"],
                "position_match_expected": response["position_match_expected"],
                "position_match_response": response["position_match_response"],
                "position_correct": response["position_correct"],
                "symbol_match_expected": response["symbol_match_expected"],
                "symbol_match_response": response["symbol_match_response"],
                "symbol_correct": response["symbol_correct"],
            })

        return {
            "attempt_id": attempt_id,
            "activity_id": "HY-02",
            "activity_version": attempt["activity_version"],
            "config_version": attempt["config_version"],
            "n_back": n_back,
            "stream_count": trial_count,
            "assistance_event_id": assistance_event_id,
            "trials": trials,
        }

    @app.get("/api/hybrid/attempts/{attempt_id}/stimulus")
    def current_stimulus(attempt_id: str):
        attempt=hs.get_attempt(store,attempt_id)
        if not attempt: raise HTTPException(status_code=404,detail="hybrid attempt not found")
        if attempt["activity_id"] not in {"HY-02","HY-04"}: raise HTTPException(status_code=409,detail="activity has no streamed stimulus")
        import json as _json
        config=_json.loads(attempt["config_json"]);events=hs.attempt_events(store,attempt_id)
        index=len([e for e in events if e["type"]=="hybrid_action_recorded" and e["payload"].get("action_type")=="respond"])
        stimulus=tidekeeper.stimulus(config,index) if attempt["activity_id"]=="HY-02" else harbor_dispatch.stimulus(config,index)
        return {"complete":True,"index":index} if stimulus is None else {"complete":False,**stimulus}

    @app.post("/api/hybrid/attempts/{attempt_id}/actions", status_code=201)
    def record_action(attempt_id: str, body: HybridActionRecord):
        attempt = hs.get_attempt(store, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="hybrid attempt not found")
        if body.attempt_id != attempt_id:
            raise HTTPException(status_code=409, detail="action attempt_id does not match the route")
        events = hs.attempt_events(store, attempt_id)
        action_events = [e for e in events if e["type"] == "hybrid_action_recorded"]
        existing = next((e for e in events if e["event_id"] == body.event_id), None)
        payload = {
            "event_type": "hybrid_action_recorded",
            "attempt_id": attempt_id,
            "session_id": attempt["session_id"],
            "learner_id": attempt["learner_id"],
            "activity_id": attempt["activity_id"],
            "activity_version": attempt["activity_version"],
            "action_sequence": body.sequence,
            "action_type": body.action_type,
            "action": body.payload,
            "elapsed_ms": body.elapsed_ms,
            "cue_event_id": body.cue_event_id,
            "visibility_interrupted": body.visibility_interrupted,
        }
        if existing is None and attempt["status"] == "completed":
            raise HTTPException(status_code=409,detail="completed attempts do not accept new actions")
        if existing is None and attempt["activity_id"] in {"HY-02","HY-04"} and body.action_type!="respond":
            raise HTTPException(status_code=409,detail="stream activities accept one response per current stimulus")
        if existing is None and attempt["activity_id"] in {"HY-02", "HY-04"} and body.action_type == "respond":
            import json as _json
            config=_json.loads(attempt["config_json"])
            index_key="trial_index" if attempt["activity_id"]=="HY-02" else "arrival_index"
            raw_index=body.payload.get(index_key)
            if type(raw_index) is not int:
                raise HTTPException(status_code=422,detail=f"{index_key} must be an integer")
            index=raw_index
            if attempt["activity_id"]=="HY-02":
                if type(body.payload.get("position_match")) is not bool or type(body.payload.get("symbol_match")) is not bool:
                    raise HTTPException(status_code=422,detail="HY-02 requires boolean position_match and symbol_match responses")
            else:
                destination=body.payload.get("destination_id")
                ignore=body.payload.get("ignore")
                if type(ignore) is not bool or (destination is not None and destination not in harbor_dispatch.DESTINATIONS) or ignore != (destination is None):
                    raise HTTPException(status_code=422,detail="HY-04 requires a known destination or an explicit ignore decision")
            current=sum(1 for e in action_events if e["payload"].get("action_type")=="respond")
            stimulus=tidekeeper.stimulus(config,index) if attempt["activity_id"]=="HY-02" else harbor_dispatch.stimulus(config,index)
            if index!=current or stimulus is None or body.cue_event_id!=stimulus["cue_id"]:
                raise HTTPException(status_code=409,detail="response must match the current recorded stimulus")
        if existing is None and attempt["activity_id"] == "HY-03" and body.action_type == "select":
            import json as _json
            config=_json.loads(attempt["config_json"])
            cargo_id=body.payload.get("cargo_id")
            if not isinstance(cargo_id,str) or cargo_id not in {item["cargo_id"] for item in config["cargo"]}:
                raise HTTPException(status_code=422,detail="HY-03 selection must name a configured cargo item")
            bin_id=body.payload.get("bin_id")
            if not isinstance(bin_id,str) or bin_id not in set(config["rules"]["color_bins"].values()) | set(config["rules"]["shape_bins"].values()):
                raise HTTPException(status_code=422,detail="HY-03 selection must name a configured destination bin")
            selected=[e["payload"].get("action",{}).get("cargo_id") for e in action_events if e["payload"].get("action_type")=="select"]
            if cargo_id in selected:
                raise HTTPException(status_code=409,detail="HY-03 cargo items may only be selected once")
            if len(selected)>=len(config["cargo"]):
                raise HTTPException(status_code=409,detail="HY-03 has no remaining cargo selections")
        if existing is None and attempt["activity_id"] == "HY-06" and body.action_type == "advise":
            import json as _json
            config=_json.loads(attempt["config_json"])
            allowed={item["constraint_id"] for item in config["constraints"]}
            allowed.update(edge["edge_id"] for edge in config["edges"])
            refs=body.payload.get("inspected_refs", [])
            if not isinstance(refs,list) or any(not isinstance(ref,str) or ref not in allowed for ref in refs):
                raise HTTPException(status_code=422,detail="HY-06 inspected_refs must cite configured evidence identifiers")
            constraint=body.payload.get("constraint_id", "")
            if constraint is not None and constraint != "" and (not isinstance(constraint,str) or constraint not in allowed):
                raise HTTPException(status_code=422,detail="HY-06 constraint_id must cite a configured evidence identifier")
            decision=body.payload.get("decision")
            if not isinstance(decision,str) or decision not in {"accept","reject","hold","modify"}:
                raise HTTPException(status_code=422,detail="HY-06 decision must be accept, reject, hold or modify")
        # An exact retry of an already recorded action is idempotent; a different payload
        # for the same event id is rejected by the store.
        storage_sequence = int(existing["sequence"]) if existing else hs.next_sequence(store, attempt_id)
        if not existing and body.sequence != len(action_events) + 1:
            raise HTTPException(status_code=409, detail=f"action sequence must be {len(action_events) + 1}")
        try:
            event, replayed = hs.append_event(store, attempt_id, attempt["session_id"], storage_sequence,
                                              "hybrid_action_recorded", payload, body.event_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except hs.HybridConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"accepted": True, "replayed": replayed, "event_id": event["event_id"], "sequence": body.sequence}

    @app.post("/api/hybrid/attempts/{attempt_id}/assistance", status_code=201)
    def record_assistance(attempt_id: str, body: HybridAssistanceRecord):
        attempt = hs.get_attempt(store, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="hybrid attempt not found")
        if body.attempt_id != attempt_id:
            raise HTTPException(status_code=409, detail="assistance attempt_id does not match the route")
        if body.exposure_kind not in ASSISTANCE_EXPOSURES:
            raise HTTPException(status_code=422, detail="unknown assistance exposure kind")
        windows = ASSISTANCE_WINDOWS.get(attempt["activity_id"], ())
        if body.checkpoint not in windows:
            raise HTTPException(status_code=409, detail=f"{body.checkpoint} is not an assistance window for {attempt['activity_id']}")
        events = hs.attempt_events(store, attempt_id)
        prior_event = next((event for event in events if event["event_id"] == body.event_id), None)
        if prior_event:
            try:
                event = hs.record_assistance(store, attempt, body.event_id, body.exposure_kind, body.checkpoint,
                                             body.checkpoint_version, body.source_event_id)
            except hs.HybridConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return {"accepted": True, "replayed": True, "event_id": event["event_id"],
                    "sequence": event["sequence"], "exposure_kind": body.exposure_kind,
                    "checkpoint": body.checkpoint}
        if body.source_event_id and not any(event["event_id"] == body.source_event_id for event in events):
            raise HTTPException(status_code=422, detail="source_event_id must reference an event from this attempt")
        actions = [e for e in events if e["type"] == "hybrid_action_recorded"]
        import json as _json
        config = _json.loads(attempt["config_json"])
        completed = attempt["status"] == "completed"
        if body.checkpoint in PRE_ACTION_WINDOWS and (actions or completed):
            raise HTTPException(status_code=409, detail="this assistance window has already closed")
        if not _assistance_checkpoint_open(attempt["activity_id"], body.checkpoint, config, actions):
            raise HTTPException(status_code=409, detail=f"{body.checkpoint} is not open at the recorded checkpoint")
        if body.checkpoint in POST_COMPLETION_WINDOWS and not completed:
            raise HTTPException(status_code=409, detail="assistance after completion requires a completed attempt")
        required_action = POST_ACTION_REQUIREMENTS.get((attempt["activity_id"], body.checkpoint))
        if required_action and not any(e["payload"].get("action_type") == required_action for e in actions):
            raise HTTPException(status_code=409, detail=f"{body.checkpoint} assistance requires a recorded {required_action} action")
        try:
            event = hs.record_assistance(store, attempt, body.event_id, body.exposure_kind, body.checkpoint,
                                         body.checkpoint_version, body.source_event_id)
        except hs.HybridConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"accepted": True, "replayed": False, "event_id": event["event_id"], "sequence": event["sequence"],
                "exposure_kind": body.exposure_kind, "checkpoint": body.checkpoint}

    @app.post("/api/hybrid/attempts/{attempt_id}/complete")
    def complete_attempt(attempt_id: str, body: HybridCompletionRecord):
        attempt = hs.get_attempt(store, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="hybrid attempt not found")
        if body.attempt_id != attempt_id:
            raise HTTPException(status_code=409, detail="completion attempt_id does not match the route")
        existing = hs.get_outcome(store, attempt_id)
        if existing:
            completion = next((event for event in hs.attempt_events(store, attempt_id)
                               if event["type"] == "hybrid_attempt_completed"), None)
            # A completed attempt may only be replayed with the same immutable
            # completion event identity and request fields. Returning an outcome
            # for a different event (or changed interruption state) would hide a
            # conflicting canonical record from a client retry.
            if completion is None or completion["event_id"] != body.event_id:
                raise HTTPException(status_code=409, detail="attempt already has a different completion event")
            recorded = completion["payload"]
            if (bool(recorded.get("interrupted")) != body.interrupted
                    or bool(recorded.get("visibility_interrupted")) != body.visibility_interrupted
                    or recorded.get("response_time_ms") != body.response_time_ms):
                raise HTTPException(status_code=409, detail="completion event retry does not match its recorded payload")
            return existing
        import json as _json
        config = _json.loads(attempt["config_json"])
        events = hs.attempt_events(store, attempt_id)
        actions = [{
            "event_id": e["event_id"],
            "sequence": e["payload"].get("action_sequence", e["sequence"]),
            "action_type": e["payload"].get("action_type"),
            "payload": e["payload"].get("action") or {},
            "elapsed_ms": e["payload"].get("elapsed_ms"),
            "cue_event_id": e["payload"].get("cue_event_id"),
            "visibility_interrupted": bool(e["payload"].get("visibility_interrupted")),
        } for e in events if e["type"] == "hybrid_action_recorded"]
        assistance = hs.assistance_records(store, attempt_id)
        interrupted = bool(body.interrupted or body.visibility_interrupted)
        if attempt["activity_id"] == "HY-05" and not interrupted:
            preview = evaluate(attempt["activity_id"], config, actions)
            committed = any(action.get("action_type") == "commit" for action in actions)
            if not committed and not preview.get("valid_arrangement"):
                raise HTTPException(status_code=409, detail="HY-05 requires a commit or a complete valid arrangement")
        if attempt["activity_id"] in {"HY-02","HY-04"} and not interrupted:
            expected=int(config["trial_count"]) if attempt["activity_id"]=="HY-02" else int(config["wave_count"])*int(config["arrivals_per_wave"])
            actual=sum(1 for action in actions if action["action_type"]=="respond")
            if actual<expected: raise HTTPException(status_code=409,detail=f"activity requires {expected} recorded responses; received {actual}")
        if attempt["activity_id"] == "HY-03" and not interrupted:
            cargo_ids={item["cargo_id"] for item in config["cargo"]}
            selected=[action.get("payload",{}).get("cargo_id") for action in actions if action["action_type"]=="select"]
            valid_selection=[cargo_id for cargo_id in selected if cargo_id in cargo_ids]
            if len(valid_selection)<len(cargo_ids) or len(set(valid_selection))<len(cargo_ids):
                raise HTTPException(status_code=409,detail=f"HY-03 requires one recorded choice for each of {len(cargo_ids)} cargo items")
        try:
            hs.complete_attempt(store, attempt_id, body.event_id, attempt["session_id"], {
                "event_type": "hybrid_attempt_completed",
                "attempt_id": attempt_id,
                "session_id": attempt["session_id"],
                "learner_id": attempt["learner_id"],
                "activity_id": attempt["activity_id"],
                "activity_version": attempt["activity_version"],
                "interrupted": body.interrupted,
                "visibility_interrupted": body.visibility_interrupted,
                "response_time_ms": body.response_time_ms,
                "action_count": len(actions),
                "assistance_count": len(assistance),
            })
        except hs.HybridConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        outcome_body = evaluate(attempt["activity_id"], config, actions)
        assisted = bool(assistance)
        evidence = [e["event_id"] for e in hs.attempt_events(store, attempt_id)]
        outcome = {
            "attempt_id": attempt_id,
            "session_id": attempt["session_id"],
            "learner_id": attempt["learner_id"],
            "activity_id": attempt["activity_id"],
            "activity_version": attempt["activity_version"],
            "evaluation_version": outcome_body.get("evaluation_version", "hybrid-eval-v1"),
            "completion_state": "interrupted" if interrupted else "completed",
            "assisted": assisted,
            "excluded_from_unassisted": bool(assisted or interrupted),
            "outcomes": outcome_body,
            "evidence_ids": evidence,
            "limitations": limitations_for(attempt["activity_id"]),
        }
        return hs.save_outcome(store, outcome)

    @app.get("/api/hybrid/summary/{learner_id}")
    def hybrid_summary(learner_id: str):
        activities = []
        for activity_id, meta in CATALOG.items():
            if not is_implemented(activity_id):
                continue
            outcomes = hs.learner_outcomes(store, learner_id, activity_id)
            unassisted = [o for o in outcomes if not o["excluded_from_unassisted"]]
            activities.append({
                **capability_metadata(activity_id),
                "attempts": len(outcomes),
                "unassisted_attempts": len(unassisted),
                "assisted_attempts": len(outcomes) - len(unassisted),
                "latest": outcomes[-1] if outcomes else None,
                "limitations": limitations_for(activity_id),
            })
        return {
            "learner_id": learner_id,
            "hybrid_schema_version": HYBRID_SCHEMA_VERSION,
            "note": "Hybrid outcomes are descriptive and separate from the five fixed baseline indices.",
            "activities": activities,
        }
