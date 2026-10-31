from __future__ import annotations

import os
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

ROOT_DIR=Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)

from .contracts import (EXERCISE_VERSION, LEGACY_TRAINING_EXERCISE_VERSION, POLICY_VERSION, SCORING_VERSION, TRAINING_EXERCISE_VERSION,
    Recommendation, SessionCreate, TrainingBlockCreate, TrialSubmission, TrialResult, NextRecommendationRequest, PlanNextRequest)
from .difficulty import RULE_VERSION, decide_difficulty
from .battery_exercises import (DIMENSIONS, VERSIONS, LEGACY_TRAINING_VERSIONS, TRAINING_VERSIONS, exercise_items as battery_items,
    training_items as battery_training_items, battery_training_exercise, battery_reassessment_exercise, REASSESSMENT_VERSION, evaluate_attention, evaluate_memory,
    evaluate_switch, public_exercise as battery_exercise, replay_planning)
from .battery_scoring import score_battery, score_family
from .exercises import BASELINE_ITEM_IDS, ITEM_BANK, evaluate, make_training_bank, public_exercise
from .scoring import score_reasoning
from .storage import Store
from .profile_service import build_profile
from .selector import select_next
from .strategy import latest_strategy
from .plan_service import build_plan
from .policy import DIMENSION_TO_EXERCISE, EXERCISE_TO_DIMENSION
from .dashboard_service import build_dashboard

logger = logging.getLogger(__name__)
app=FastAPI(title="AI4BRAIN API",version="1.0.0",description="Evidence-based, non-clinical cognitive task POC")
origins=os.getenv("AI4BRAIN_CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in origins.split(",")],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])
store=Store()

def now_dt():return datetime.now(timezone.utc)
def public_event(event:dict)->dict:
    result=dict(event); payload=dict(event["payload"]); evaluation=dict(payload.get("evaluation",{}))
    if payload.get("phase")=="baseline" and payload.get("exercise_id")=="EX-02" and not score_reasoning(store.events(learner_id=payload.get("learner_id","demo-user")))["completed"]:
        if evaluation.get("error_type"):evaluation["error_type"]="incorrect_pattern"
        config=dict(payload.get("stimulus_config",{}));config.pop("rule_type",None);payload["stimulus_config"]=config
    payload["evaluation"]=evaluation; result["payload"]=payload; result.pop("payload_json",None); return result

def _snapshot(learner_id:str, exercise_id:str="EX-02")->dict:
    events=store.events(learner_id=learner_id)
    if exercise_id=="EX-02":
        result=score_reasoning(events); dimension="reasoning"
    else:
        result=score_family(events,exercise_id); dimension=DIMENSIONS[exercise_id]
    row={"id":str(uuid.uuid4()),"learner_id":learner_id,"scoring_version":SCORING_VERSION,"dimension":dimension,
        "index_0_100":result["index_0_100"],"uncertainty_status":result["uncertainty_status"],"evidence_count":result["evidence_count"],
        "completed":result["completed"],"evidence_ids":result["evidence_ids"],"interrupted_count":result["interrupted_count"],"created_at":now_dt().isoformat()}
    store.save_snapshot(row); return row

def _persist_difficulty(block_id:str)->dict|None:
    block=store.get_training_block(block_id)
    if not block:return None
    proposed=decide_difficulty(block_id,block["learner_id"],block["tier"],store.block_events(block_id))
    if not proposed:return store.get_decision(block_id)
    proposed["created_at"]=now_dt().isoformat(); proposed["session_id"]=block["session_id"]; proposed["event_id"]=str(uuid.uuid4())
    store.save_decision_once(proposed)
    return store.get_decision(block_id)
def _decision_view(block_id:str)->dict|None:
    """Decision plus explicit eligible/assisted/interrupted counts and what each label means."""
    decision=store.get_decision(block_id)
    if not decision:return None
    events=store.block_events(block_id)
    assisted=sum(1 for e in events if (e["payload"].get("interaction",{}) or {}).get("hint_count",0) or (e["payload"].get("interaction",{}) or {}).get("replay_count",0))
    interrupted=sum(1 for e in events if (e["payload"].get("interaction",{}) or {}).get("visibility_interrupted"))
    return {**decision,"assisted_trial_count":assisted,"interrupted_trial_count":interrupted,
            "total_recorded_trials":len(events),
            "count_note":"Eligible trials exclude assisted and interrupted attempts; recorded trials include them."}

def _persist_plan_after_decision(block_id:str,decision:dict)->dict|None:
    from .plan_v2 import reconcile_plan
    block=store.get_training_block(block_id)
    if not block:return None
    events=store.events(learner_id="demo-user")
    decision_event_id=next((e["event_id"] for e in events if e["type"]=="difficulty_changed" and e["payload"].get("training_block_id")==block_id),None)
    return reconcile_plan(store,{"kind":"training_decision","event_id":decision_event_id,"training_block_id":block_id,
        "action":decision.get("action"),"tier":decision.get("new_tier")},session_id=decision.get("session_id") or block["session_id"])

def _reconcile_plan_after_baseline(learner_id:str,session_id:str,exercise_id:str,snapshot:dict)->dict|None:
    """Refresh the active plan when a baseline family becomes complete."""
    if not snapshot.get("completed"):return None
    from .plan_v2 import reconcile_plan
    return reconcile_plan(store,{"kind":"baseline_completed","event_id":snapshot.get("id"),
        "exercise_id":exercise_id,"dimension":snapshot.get("dimension")},session_id=session_id)

@app.get("/health")
def health():return {"status":"ok","application":"AI4BRAIN","schema_version":"1.0.0"}

@app.post("/api/sessions",status_code=201)
def create_session(body:SessionCreate):
    if body.learner_id!="demo-user":raise HTTPException(400,"Only the anonymous demo-user is supported in this POC")
    if not body.consent_accepted:raise HTTPException(400,"Consent and the local-data notice must be accepted to start")
    return store.create_session(str(uuid.uuid4()),body.learner_id,body.dashboard_mode)

@app.get("/api/sessions/{session_id}")
def resume_session(session_id:str):
    session=store.get_session(session_id)
    if session is None:raise HTTPException(404,"session not found")
    events=store.events(session_id=session_id)
    return {**session,"events":[public_event(e) for e in events],"event_count":len(events)}

@app.get("/api/sessions/{session_id}/events")
def session_events(session_id:str):
    if store.get_session(session_id) is None:raise HTTPException(404,"session not found")
    return {"session_id":session_id,"events":[public_event(e) for e in store.events(session_id=session_id)]}

@app.get("/api/exercises/EX-02")
def get_exercise(phase:str="baseline",tier:str|None=None,training_block_id:str|None=None):
    if phase=="training":
        if not training_block_id:raise HTTPException(422,"training_block_id is required")
        block=store.get_training_block(training_block_id)
        if not block or block["tier"]!=tier:raise HTTPException(404,"training block and tier not found")
    elif phase not in {"practice","baseline"}:raise HTTPException(422,"phase must be practice, baseline, or an active training block")
    try:
        version=store.get_training_block(training_block_id)["exercise_version"] if phase=="training" else None
        return public_exercise(phase,tier,training_block_id,version).model_dump(mode="json")
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.post("/api/training/blocks",status_code=201)
def create_training_block(body:TrainingBlockCreate):
    session=store.get_session(body.session_id)
    if not session:raise HTTPException(404,"session not found")
    if session["learner_id"]!="demo-user":raise HTTPException(403,"learner does not own session")
    if body.exercise_id=="EX-02":
        baseline=score_reasoning(store.events(learner_id=session["learner_id"]))
        version=TRAINING_EXERCISE_VERSION; dimension="reasoning"
    else:
        baseline=score_family(store.events(learner_id=session["learner_id"]),body.exercise_id)
        version=TRAINING_VERSIONS[body.exercise_id]; dimension=DIMENSIONS[body.exercise_id]
    if not baseline["completed"]:raise HTTPException(409,"complete this family's valid baseline before targeted training")
    # The explicit world choice owns its tier: resolve the family's canonical current
    # tier instead of trusting a client value or another family's gate.
    from .difficulty import TIERS, current_tier
    canonical_tier=current_tier(store.events(learner_id=session["learner_id"]),dimension)
    latest_plan = store.latest_plan(session["learner_id"])
    plan_step = next((step for step in (latest_plan or {}).get("steps", [])
                      if step.get("exercise_type_id") == body.exercise_id
                      and step.get("status") in {"recommended", "in_progress"}), None)
    planned_tier = (plan_step or {}).get("launch_tier") or (plan_step or {}).get("difficulty_tier")
    if planned_tier and planned_tier != canonical_tier:
        raise HTTPException(409, "saved plan tier is stale; refresh the plan before launching this activity")
    if body.tier is None:tier=planned_tier or canonical_tier
    elif TIERS.index(body.tier)>TIERS.index(canonical_tier):
        raise HTTPException(422,"supplied tier exceeds this family's recorded difficulty decision")
    elif planned_tier and body.tier != planned_tier and TIERS.index(body.tier) >= TIERS.index(planned_tier):
        raise HTTPException(409,"training launch tier does not match the current saved plan")
    else:tier=body.tier
    block_id=str(uuid.uuid4())
    block=store.create_training_block(block_id,session["learner_id"],body.session_id,tier,version,body.exercise_id,dimension)
    if body.exercise_id=="EX-02":
        config=public_exercise("training",tier,block_id,version).model_dump(mode="json")
        item_ids=[item["item_id"] for item in make_training_bank(tier,block_id,version)]
    else:
        config=battery_training_exercise(body.exercise_id,tier,block_id,version)
        item_ids=[item["item_id"] for item in config["items"]]
    event_id=str(uuid.uuid4()); payload={"event_id":event_id,"session_id":body.session_id,"learner_id":session["learner_id"],
        "event_type":"training_block_started","phase":"training","training_block_id":block_id,"exercise_id":body.exercise_id,
        "dimension":dimension,"exercise_version":version,"challenge_seed":block_id,"item_difficulty":tier,"item_ids":item_ids,
        "policy_version":RULE_VERSION,"sample_data":False,"recorded_at":now_dt().isoformat()}
    store.add_event(event_id,body.session_id,"training_block_started",payload)
    return {"block":block,"exercise":config,"difficulty_decision":None,
            "plan_alignment": {"plan_id": (latest_plan or {}).get("plan_id"),
                               "plan_step_id": (plan_step or {}).get("step_id"),
                               "launch_tier": tier,
                               "authoritative_tier": canonical_tier,
                               "matched": bool(plan_step and planned_tier == tier)}}


def create_plan_training_block(session_id:str,exercise_id:str,tier:str,block_id:str):
    """Idempotent plan-v3 adapter to the canonical core training-block start."""
    session=store.get_session(session_id)
    if not session:raise HTTPException(404,"session not found")
    learner_id=session["learner_id"]
    existing=store.get_training_block(block_id)
    if exercise_id=="EX-02":version=TRAINING_EXERCISE_VERSION
    elif exercise_id in TRAINING_VERSIONS:version=TRAINING_VERSIONS[exercise_id]
    else:raise HTTPException(422,"unknown core exercise")
    if existing:
        if (existing["learner_id"]!=learner_id or existing["session_id"]!=session_id
                or existing["exercise_id"]!=exercise_id or existing["tier"]!=tier
                or existing["exercise_version"]!=version):
            raise HTTPException(409,"deterministic training block id conflicts with another block")
        dimension=existing["dimension"]
        latest_plan=store.latest_plan(learner_id)
        plan_step=next((step for step in (latest_plan or {}).get("steps",[])
                        if step.get("exercise_type_id")==exercise_id
                        and step.get("status") in {"recommended","in_progress"}),None)
        planned_tier=(plan_step or {}).get("launch_tier") or (plan_step or {}).get("difficulty_tier")
    else:
        if exercise_id=="EX-02":
            baseline=score_reasoning(store.events(learner_id=learner_id))
            dimension="reasoning"
        else:
            baseline=score_family(store.events(learner_id=learner_id),exercise_id)
            dimension=DIMENSIONS[exercise_id]
        if not baseline["completed"]:raise HTTPException(409,"complete this family's valid baseline before targeted training")
        from .difficulty import current_tier
        canonical_tier=current_tier(store.events(learner_id=learner_id),dimension)
        latest_plan=store.latest_plan(learner_id)
        plan_step=next((step for step in (latest_plan or {}).get("steps",[])
                        if step.get("exercise_type_id")==exercise_id
                        and step.get("status") in {"recommended","in_progress"}),None)
        planned_tier=(plan_step or {}).get("launch_tier") or (plan_step or {}).get("difficulty_tier")
        if planned_tier!=tier or tier!=canonical_tier:
            raise HTTPException(409,"saved plan tier is stale; refresh the plan before launching this activity")
        if not plan_step or not (latest_plan or {}).get("plan_id"):
            raise HTTPException(409,"there is no current plan step for this core activity")
        try:store.create_training_block(block_id,learner_id,session_id,tier,version,exercise_id,dimension)
        except sqlite3.IntegrityError:
            existing=store.get_training_block(block_id)
            if not existing or (existing["learner_id"]!=learner_id or existing["session_id"]!=session_id
                    or existing["exercise_id"]!=exercise_id or existing["tier"]!=tier
                    or existing["exercise_version"]!=version):
                raise HTTPException(409,"deterministic training block id conflicts with another block")
    block=store.get_training_block(block_id)
    if exercise_id=="EX-02":
        config=public_exercise("training",tier,block_id,version).model_dump(mode="json")
        item_ids=[item["item_id"] for item in make_training_bank(tier,block_id,version)]
    else:
        config=battery_training_exercise(exercise_id,tier,block_id,version)
        item_ids=[item["item_id"] for item in config["items"]]
    event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,"ai4brain-plan-training-start:"+block_id))
    payload={"event_id":event_id,"session_id":session_id,"learner_id":learner_id,
        "event_type":"training_block_started","phase":"training","training_block_id":block_id,
        "exercise_id":exercise_id,"dimension":dimension,"exercise_version":version,
        "challenge_seed":block_id,"item_difficulty":tier,"item_ids":item_ids,
        "policy_version":RULE_VERSION,"sample_data":False,"recorded_at":now_dt().isoformat()}
    try:store.add_event(event_id,session_id,"training_block_started",payload)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    return {"block":block,"exercise":config,
            "plan_alignment":{"plan_id":(latest_plan or {}).get("plan_id"),
                              "plan_step_id":(plan_step or {}).get("step_id"),
                              "launch_tier":tier,"authoritative_tier":tier,
                              "matched":bool(plan_step and planned_tier==tier)}}

@app.get("/api/training/blocks/{block_id}")
def get_training_block(block_id:str):
    block=store.get_training_block(block_id)
    if not block:raise HTTPException(404,"training block not found")
    config=(public_exercise("training",block["tier"],block_id,block["exercise_version"]).model_dump(mode="json") if block["exercise_id"]=="EX-02"
            else battery_training_exercise(block["exercise_id"],block["tier"],block_id,block["exercise_version"]))
    events=store.block_events(block_id)
    valid=sum(not e["payload"]["interaction"]["visibility_interrupted"] and e["payload"]["interaction"]["hint_count"]==0 and e["payload"]["interaction"].get("replay_count",0)==0 for e in events)
    return {"block":block,"exercise":config,"valid_trial_count":valid,"assisted_trial_count":sum(1 for e in events if (e["payload"].get("interaction",{}) or {}).get("hint_count",0) or (e["payload"].get("interaction",{}) or {}).get("replay_count",0)),"interrupted_trial_count":sum(1 for e in events if (e["payload"].get("interaction",{}) or {}).get("visibility_interrupted")),"total_recorded_trials":len(events),"count_note":"Eligible trials exclude assisted and interrupted attempts; recorded trials include them.","difficulty_decision":_decision_view(block_id)}

@app.post("/api/trials")
def submit_trial(body:TrialSubmission):
    if body.phase in {"baseline","reassessment"} and body.hint_count>0:raise HTTPException(422,"hints are not permitted on scored assessment trials")
    if body.phase in {"baseline","reassessment"} and body.replay_count>0:raise HTTPException(422,"replayed cues are not permitted on scored assessment trials")
    session=store.get_session(body.session_id)
    if not session:raise HTTPException(404,"session not found")
    if session["learner_id"]!=body.learner_id:raise HTTPException(403,"learner does not own session")
    event_type={"baseline":"assessment_trial_completed","reassessment":"reassessment_trial_completed","practice":"practice_trial_completed","training":"training_trial_completed"}[body.phase]
    try:prior=store.replay_submission(body.event_id,body.session_id,event_type,body.model_dump(mode="json"))
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    if prior is not None:
        ev=prior["evaluation"]
        decision=_decision_view(body.training_block_id) if body.training_block_id else None
        return TrialResult(event_id=body.event_id,session_id=body.session_id,item_id=body.item_id,phase=body.phase,
            correct=ev.get("correct"),error_type="incorrect_pattern" if ev.get("error_type") else None,scoring_version=ev["scoring_version"],
            visibility_interrupted=prior["interaction"]["visibility_interrupted"],scored=prior["scored"],replayed=True,
            difficulty_decision=decision,valid_training_count=sum(1 for e in store.block_events(body.training_block_id) if not e["payload"]["interaction"]["visibility_interrupted"] and e["payload"]["interaction"]["hint_count"]==0 and e["payload"]["interaction"].get("replay_count",0)==0) if body.training_block_id else None)
    block=None
    if body.phase=="training":
        if not body.training_block_id:raise HTTPException(422,"training_block_id is required")
        block=store.get_training_block(body.training_block_id)
        if not block or block["session_id"]!=body.session_id or block["exercise_id"]!=body.exercise_id:
            raise HTTPException(404,"training block not found for session and exercise family")
        already_saved=any(e["event_id"]==body.event_id for e in store.events(session_id=body.session_id))
        if block["status"]!="active" and not already_saved:raise HTTPException(409,"training block already has its four-trial decision")
    elif body.training_block_id:
        raise HTTPException(422,"training_block_id is only valid for training trials")
    phase_item_ids:list[str]
    if body.exercise_id=="EX-02":
        if body.phase=="training":
            if body.exercise_version not in {LEGACY_TRAINING_EXERCISE_VERSION,TRAINING_EXERCISE_VERSION} or block["exercise_version"]!=body.exercise_version:raise HTTPException(422,"unsupported training exercise version")
            source=make_training_bank(block["tier"],body.training_block_id,body.exercise_version); item=next((x for x in source if x["item_id"]==body.item_id),None)
            if item is None:raise HTTPException(422,"item does not belong to this training tier")
            phase_item_ids=[x["item_id"] for x in source]
        else:
            if body.phase=="reassessment":raise HTTPException(422,"reasoning reassessment is not configured")
            if body.exercise_version!=EXERCISE_VERSION:raise HTTPException(422,"unsupported exercise version")
            item=ITEM_BANK.get(body.item_id)
            if item is None:raise HTTPException(422,"unknown item")
            is_practice=item["item_id"].endswith("practice-001")
            if (body.phase=="practice")!=is_practice:raise HTTPException(422,"item does not belong to phase")
            phase_item_ids=[body.item_id] if body.phase=="practice" else BASELINE_ITEM_IDS
        if body.response_data is not None:raise HTTPException(422,"response_data is not used by EX-02")
        if not body.choice and not body.visibility_interrupted:raise HTTPException(422,"choice is required unless the trial was interrupted")
        try:correct,error_type=evaluate(body.item_id,body.choice,item_data=item) if body.choice else (None,None)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
        evaluation={"correct":correct,"error_type":error_type};response={"choice":body.choice}
        stimulus=item["pattern"];choices=item["choices"];dimension="reasoning"
        item_difficulty=block["tier"] if block else item["difficulty"]
        version=body.exercise_version
    else:
        if body.exercise_id not in DIMENSIONS:raise HTTPException(422,"unsupported exercise_id")
        if body.phase=="training":
            if body.exercise_version not in {TRAINING_VERSIONS[body.exercise_id],LEGACY_TRAINING_VERSIONS[body.exercise_id]} or block["exercise_version"]!=body.exercise_version:raise HTTPException(422,"unsupported family training exercise version")
            config=battery_training_exercise(body.exercise_id,block["tier"],body.training_block_id,body.exercise_version)
        else:
            if body.phase=="reassessment":
                if body.exercise_id=="EX-02" or body.exercise_version!=REASSESSMENT_VERSION:raise HTTPException(422,"unsupported reassessment version for exercise family")
                config=battery_reassessment_exercise(body.exercise_id,body.session_id)
            else:
                if body.exercise_version!=VERSIONS[body.exercise_id]:raise HTTPException(422,"unsupported exercise version for exercise family")
                config=battery_exercise(body.exercise_id,body.phase,body.session_id)
        item=next((x for x in config["items"] if x["item_id"]==body.item_id),None)
        if item is None:raise HTTPException(422,"item does not belong to this exercise family and phase")
        phase_item_ids=[x["item_id"] for x in config["items"]]
        data=body.response_data or {}
        def has_forbidden(value):
            if isinstance(value,dict):return any(k.lower() in {"correct","score","completed","optimal_moves","efficiency_0_100","evaluation"} or has_forbidden(v) for k,v in value.items())
            if isinstance(value,list):return any(has_forbidden(x) for x in value)
            return False
        if has_forbidden(data):raise HTTPException(422,"response_data cannot contain correctness, score, completion, or answer-key claims")
        if body.visibility_interrupted:evaluation={"correct":None,"interrupted":True};response={}
        else:
            try:
                if body.exercise_id=="EX-01":
                    evaluation=evaluate_memory(item,data);response={"selected_sequence":data["selected_sequence"]}
                elif body.exercise_id=="EX-03":
                    evaluation=evaluate_attention(item,{"responded":data.get("responded"),"response_time_ms":body.response_time_ms});response={"responded":data["responded"]}
                elif body.exercise_id=="EX-04":
                    evaluation=evaluate_switch(item,data);response={"choice":data["choice"]}
                else:
                    evaluation=replay_planning(item,data);response={"actions":data["actions"]}
            except (ValueError,KeyError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
        dimension=DIMENSIONS[body.exercise_id];stimulus=item["stimulus"];choices=None
        item_difficulty=block["tier"] if block else "baseline"
        version=body.exercise_version
    effective_hint_count=body.hint_count
    if body.phase=="training" and body.training_block_id:
        block_events=store.events(session_id=body.session_id)
        coach_hint=any(e["type"]=="coaching_message_sent" and e["payload"].get("training_block_id")==body.training_block_id
            and e["payload"].get("item_id")==body.item_id and e["payload"].get("hint_requested") for e in block_events)
        if coach_hint:effective_hint_count=max(1,effective_hint_count)
    # A replayed cue is assistance: the attempt is recorded but never counts as
    # unassisted evidence, exactly like a coach hint.
    assisted=effective_hint_count>0 or body.replay_count>0
    scored=body.phase in {"baseline","reassessment","training"} and not body.visibility_interrupted and not assisted
    stimulus_config={"exercise_version":version,"item_id":body.item_id,"stimulus":stimulus}
    if body.phase=="training":stimulus_config["challenge_seed"]=body.training_block_id
    if body.exercise_id=="EX-02":stimulus_config.update({"layout":"2x2","choices":choices,"rule_type":item["rule_type"]})
    payload={"schema_version":"1.0.0","event_id":body.event_id,"learner_id":body.learner_id,"session_id":body.session_id,
        "event_type":event_type,"phase":body.phase,"dimension":dimension,"exercise_id":body.exercise_id,"exercise_version":version,
        "item_id":body.item_id,"trial_index":phase_item_ids.index(body.item_id)+1,"item_difficulty":item_difficulty,"stimulus_config":stimulus_config,"sample_data":False,
        "response":response,"evaluation":{**evaluation,"scoring_version":SCORING_VERSION},
        "timing":{"stimulus_onset_ms":body.stimulus_onset_ms,"response_time_ms":body.response_time_ms,"response_ms":(body.stimulus_onset_ms+body.response_time_ms) if body.stimulus_onset_ms is not None and body.response_time_ms is not None else None,"timing_note":"Client-reported approximate browser timing."},
        "interaction":{"hint_count":effective_hint_count,"restart_count":body.restart_count,"replay_count":body.replay_count,"visibility_interrupted":body.visibility_interrupted},
        "scored":scored,"training_block_id":body.training_block_id,"recorded_at":now_dt().isoformat()}
    try:saved,replayed=store.add_event(body.event_id,body.session_id,event_type,payload,
        unique_baseline_item_id=body.item_id if body.phase=="baseline" and not body.visibility_interrupted else None,
        training_block_id=body.training_block_id if body.phase=="training" and not body.visibility_interrupted else None,
        unique_assessment_item=body.phase=="reassessment" and not body.visibility_interrupted,submission=body.model_dump(mode="json"))
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    if body.phase=="baseline" and not replayed:
        snapshot_before=_snapshot(body.learner_id,body.exercise_id)
        _reconcile_plan_after_baseline(body.learner_id,body.session_id,body.exercise_id,snapshot_before)
    decision=_persist_difficulty(body.training_block_id) if body.phase=="training" else None
    if decision:_persist_plan_after_decision(body.training_block_id,decision)
    ev=saved["evaluation"]
    return TrialResult(event_id=body.event_id,session_id=body.session_id,item_id=body.item_id,phase=body.phase,
        correct=ev.get("correct"),error_type="incorrect_pattern" if ev.get("error_type") else None,scoring_version=ev["scoring_version"],
        visibility_interrupted=saved["interaction"]["visibility_interrupted"],scored=saved["scored"],replayed=replayed,
        difficulty_decision=decision,valid_training_count=sum(1 for e in store.block_events(body.training_block_id) if not e["payload"]["interaction"]["visibility_interrupted"] and e["payload"]["interaction"]["hint_count"]==0 and e["payload"]["interaction"].get("replay_count",0)==0) if body.training_block_id else None)

@app.get("/api/profile/{learner_id}")
def profile(learner_id:str):
    if learner_id!="demo-user":raise HTTPException(404,"learner not found")
    events=store.events(learner_id=learner_id); result=score_reasoning(events); battery=score_battery(events)
    latest_by_dim={"reasoning":store.latest_snapshot(learner_id,"reasoning")}
    dimensions={"reasoning":{**result,"task_performance_label":"EX-02 task-performance index","status":"ASSESSED" if result["completed"] else ("IN_PROGRESS" if result["evidence_count"] else "NOT_ASSESSED")}}
    for name,data in battery.items():
        snap=store.latest_snapshot(learner_id,name); latest_by_dim[name]=snap
        dimensions[name]={**data,"status":"ASSESSED" if data["completed"] else ("IN_PROGRESS" if data["evidence_count"] else "NOT_ASSESSED"),"latest_snapshot_id":snap["id"] if snap else None}
    from .profile_service import build_profile
    supplemental=build_profile(events)["dimensions"]["planning"]
    for key in ("reassessment_evidence_count","reassessment_evidence_ids","reassessment_efficiencies","reassessment_session_id","selection_index_0_100"):
        dimensions["planning"][key]=supplemental[key]
    latest=latest_by_dim["reasoning"]
    times=sorted(result["response_times_ms"]); n=len(times); median_time=times[n//2] if n%2 else ((times[n//2-1]+times[n//2])/2 if n else None)
    dimensions["reasoning"]["median_response_time_ms"]=median_time; dimensions["reasoning"]["latest_snapshot_id"]=latest["id"] if latest else None
    return {"learner_id":learner_id,"dimensions":dimensions,"snapshots":store.snapshots(learner_id),
        "evidence":[{"event_id":p["event_id"],"session_id":p["session_id"],"event_type":p["type"],"created_at":p["created_at"],**p["payload"]} for p in [public_event(e) for e in events]],
        "interpretation":"These are preliminary task-performance observations, not IQ, percentiles, diagnosis, or comparable cross-task abilities."}

@app.get("/api/dashboard/{learner_id}")
def dashboard(learner_id:str):
    if learner_id!="demo-user":raise HTTPException(404,"learner not found")
    return build_dashboard(learner_id,store,profile,public_event)

@app.post("/api/recommendations/next")
def next_recommendation(body:NextRecommendationRequest|None=None):
    legacy_empty_body=body is None
    body=body or NextRecommendationRequest()
    learner_id="demo-user"
    session=store.get_session(body.session_id) if body.session_id else None
    if body.session_id and not session:raise HTTPException(404,"session not found")
    events=store.events(learner_id=learner_id)
    profile_data=build_profile(events)
    prefs=store.current_preferences(learner_id)
    goal=body.goal_dimension if body.goal_dimension is not None else (session.get("goal_dimension") if session else None) or prefs.get("goal_dimension")
    selection=select_next(profile_data,events,goal_dimension=goal,budget_minutes=body.budget_minutes,
                          selection_count=len(store.recommendations(learner_id)),
                          available_dimensions=body.available_dimensions)
    if selection["action"]=="no_available_activity":
        item={"id":str(uuid.uuid4()),"learner_id":learner_id,"action":"no_available_activity",
            "exercise_id":None,"tier":None,"reason_codes":selection["reason_codes"],"evidence_ids":[],
            "policy_version":selection["policy_version"],"created_at":now_dt().isoformat(),"dimension":None,
            "features":selection["features"],"alternatives":selection["alternatives"],
            "rationale":selection["rationale"],"selected_strategy_id":None,
            "budget_minutes":selection["budget_minutes"],"availability":selection.get("availability")}
        return Recommendation(**item)
    if legacy_empty_body:
        legacy_reasoning=score_reasoning(events)
        if not legacy_reasoning["completed"]:
            selection={"action":"complete_baseline","exercise_id":"EX-02","dimension":"reasoning","tier":"baseline",
                "selected_strategy_id":None,"reason_codes":["baseline_evidence_incomplete","interrupted_trials_are_retryable"],
                "evidence_ids":legacy_reasoning["evidence_ids"],"features":{"assessment_gate":True,
                    "evidence_count":legacy_reasoning["evidence_count"],"required_evidence_count":6},
                "alternatives":[],"rationale":"Complete the fixed reasoning baseline to replace this legacy recommendation.",
                "policy_version":"recommendation-v1","budget_minutes":body.budget_minutes or 12}
    exercise_id=selection["exercise_id"];dimension=selection["dimension"]
    strategy=latest_strategy(events,exercise_id) if selection["action"]=="targeted_training" else None
    # Preserve the old empty-body contract for callers that still expect complete_baseline.
    action="complete_baseline" if legacy_empty_body and selection["action"]=="complete_baseline" else selection["action"]
    item={"id":str(uuid.uuid4()),"learner_id":learner_id,"action":action,"exercise_id":exercise_id,
        "tier":selection["tier"],"reason_codes":selection["reason_codes"],"evidence_ids":selection["evidence_ids"],
        "policy_version":selection["policy_version"],"created_at":now_dt().isoformat(),"dimension":dimension,
        "features":selection["features"],"alternatives":selection["alternatives"],"rationale":selection["rationale"],
        "selected_strategy_id":strategy["id"] if strategy else None,"budget_minutes":selection["budget_minutes"],
        "availability":selection.get("availability")}
    snapshot=store.latest_snapshot(learner_id,dimension)
    store.save_recommendation({k:item[k] for k in ("id","learner_id","action","exercise_id","tier","reason_codes","evidence_ids","policy_version","created_at")},snapshot["id"] if snapshot else None)
    session_id=body.session_id or (session["id"] if session else None) or (events[-1]["session_id"] if events else None)
    if session_id:
        event_id=str(uuid.uuid4())
        event_payload={"event_id":event_id,"learner_id":learner_id,"session_id":session_id,"event_type":"exercise_recommended",
            "phase":"policy","exercise_id":exercise_id,"dimension":dimension,"tier":selection["tier"],"action":action,
            "policy_version":selection["policy_version"],"features":selection["features"],"observed_features":selection["features"],"alternatives":selection["alternatives"],
            "reason_codes":selection["reason_codes"],"evidence_ids":selection["evidence_ids"],"selected_strategy_id":item["selected_strategy_id"],
            "rationale":selection["rationale"],"goal_dimension":goal,"budget_minutes":selection["budget_minutes"],"sample_data":False,
            "recorded_at":now_dt().isoformat()}
        store.add_event(event_id,session_id,"exercise_recommended",event_payload)
        if strategy:
            intervention_id=str(uuid.uuid4())
            intervention={"event_id":intervention_id,"learner_id":learner_id,"session_id":session_id,"event_type":"intervention_selected",
                "phase":"policy","exercise_id":exercise_id,"dimension":dimension,"strategy_id":strategy["id"],
                "policy_version":selection["policy_version"],"reason_codes":["recorded_error_targeted_strategy"],
                "evidence_ids":strategy.get("source_evidence_ids",[]),"sample_data":False,"recorded_at":now_dt().isoformat()}
            store.add_event(intervention_id,session_id,"intervention_selected",intervention)
    return Recommendation(**item)

@app.get("/api/personalization/sample-scenarios")
def personalization_sample_scenarios():
    from .selector import sample_profile_scenarios
    return {"sample_data":True,"persisted":False,"scenarios":sample_profile_scenarios()}

@app.get("/api/profile/{learner_id}/evidence")
def evidence(learner_id:str):
    if learner_id!="demo-user":raise HTTPException(404,"learner not found")
    return {"learner_id":learner_id,"events":[public_event(e) for e in store.events(learner_id=learner_id)],"recommendations":store.recommendations(learner_id)}


@app.post("/api/plans/next")
def next_plan(body:PlanNextRequest|None=None):
    body=body or PlanNextRequest()
    session=store.get_session(body.session_id) if body.session_id else None
    if body.session_id and not session:raise HTTPException(404,"session not found")
    from .plan_v2 import build_plan_v2
    from .twin_context import build_twin_context
    events=store.events(learner_id="demo-user")
    prefs=store.current_preferences("demo-user")
    goal=body.goal_dimension if body.goal_dimension is not None else (session.get("goal_dimension") if session else None) or prefs.get("goal_dimension")
    history=store.plans("demo-user");previous=history[-1] if history else None
    context=build_twin_context(store,"demo-user")
    from .profile_service import build_profile
    from .selector import select_next
    resolved_next=select_next(build_profile(events),events,goal_dimension=goal,budget_minutes=body.budget_minutes,
        selection_count=len(store.recommendations("demo-user")),available_dimensions=body.available_dimensions)
    plan=build_plan_v2(context,events,store,goal_dimension=goal,budget_minutes=body.budget_minutes,
        selection_count=len(store.recommendations("demo-user")),previous=previous,
        available_dimensions=body.available_dimensions,resolved_next=resolved_next)
    plan["plan_id"]=str(uuid.uuid4());plan["created_at"]=now_dt().isoformat()
    from .plan_v3 import enrich_plan_v3
    plan=enrich_plan_v3(plan,context,events,store,available_activities=body.available_activities,previous_plan=previous)
    primary=plan["steps"][0] if plan["steps"] else None
    snapshot=store.latest_snapshot("demo-user",primary["dimension_id"]) if primary else None
    plan["profile_snapshot_id"]=snapshot["id"] if snapshot else None
    store.save_plan(plan)
    plan_session_id=body.session_id or (session["id"] if session else None) or (events[-1]["session_id"] if events else None)
    if plan_session_id:
        event_id=str(uuid.uuid4())
        event={"event_id":event_id,"learner_id":"demo-user","session_id":plan_session_id,"event_type":"training_plan_generated" if plan["changed"] else "training_plan_unchanged",
            "phase":"policy","plan_id":plan["plan_id"],"policy_version":plan["policy_version"],"reason_codes":plan["reason_codes"],
            "evidence_ids":plan["evidence_ids"],"features":plan["features"],"alternatives":plan["alternatives"],"changed":plan["changed"],
            "sample_data":False,"recorded_at":plan["created_at"]}
        store.add_event(event_id,plan_session_id,event["event_type"],event)
    return plan

@app.get("/api/plans/{learner_id}")
def plan_history(learner_id:str):
    if learner_id!="demo-user":raise HTTPException(404,"learner not found")
    from .plan_v3 import refresh_plan_execution_status
    history=[refresh_plan_execution_status(store,plan,learner_id) for plan in store.plans(learner_id)]
    return {"learner_id":learner_id,"latest":history[-1] if history else None,"history":history}

@app.get("/api/exercises/{exercise_id}")
def get_battery_exercise(exercise_id: str, session_id: str, phase: str = "baseline", training_block_id: str | None = None):
    if exercise_id not in DIMENSIONS:
        raise HTTPException(404, "exercise not found")
    if store.get_session(session_id) is None:
        raise HTTPException(404, "session not found")
    try:
        if phase=="training":
            if not training_block_id:raise HTTPException(422,"training_block_id is required")
            block=store.get_training_block(training_block_id)
            if not block or block["session_id"]!=session_id or block["exercise_id"]!=exercise_id:raise HTTPException(404,"training block not found")
            return battery_training_exercise(exercise_id,block["tier"],training_block_id,block["exercise_version"])
        return battery_reassessment_exercise(exercise_id,session_id) if phase=="reassessment" else battery_exercise(exercise_id,phase,session_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/graph/{learner_id}")
def graph_view(learner_id: str, dimension: str | None = None, q: str | None = None,
               node_types: str | None = None, scope: str = "global", center_id: str | None = None,
               depth: int = 1, limit: int = 5000, offset: int = 0, revision: str | None = None):
    from .graph_service import (FAMILIES, GRAPH_VERSION, MIRROR_COORDINATOR, build_graph,
                                filter_graph_snapshot, get_cached_graph, graph_lifecycle_generation)
    if learner_id != "demo-user":
        raise HTTPException(404, "learner not found")
    if dimension is not None and dimension not in FAMILIES:
        raise HTTPException(422, "unknown dimension")

    def build_source():
        preferences = store.current_preferences(learner_id)
        events = store.events(learner_id=learner_id)
        catalog = [{"item_id": item_id, "exercise_id": "EX-02", "exercise_version": EXERCISE_VERSION}
                   for item_id in BASELINE_ITEM_IDS]
        for exercise_id in DIMENSIONS:
            catalog.extend({"item_id": item["item_id"], "exercise_id": exercise_id,
                            "exercise_version": VERSIONS[exercise_id]}
                           for item in battery_items(exercise_id, "knowledge-bank"))
        current = profile(learner_id)
        return build_graph(current, events=events, item_catalog=catalog,
            goal={"dimension": preferences["goal_dimension"]} if preferences.get("goal_dimension") else None,
            dashboard_mode=preferences["dashboard_mode"])

    try:
        snapshot, snapshot_status = get_cached_graph(store, learner_id, build_source)
        selected_types = [item.strip() for item in (node_types or "").split(",") if item.strip()] or None
        result = filter_graph_snapshot(snapshot, dimension=dimension, node_types=selected_types,
            query=q, scope=scope, center_id=center_id, depth=depth, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if snapshot.get("snapshot_consistent") is False:
        mirror_status = {"enabled": True, "connected": False, "status": "pending",
                         "message": "The SQLite graph changed during snapshot construction; mirror work was deferred."}
    else:
        generation = graph_lifecycle_generation(store, learner_id)
        mirror_status = MIRROR_COORDINATOR.enqueue(store, learner_id, snapshot,
            snapshot["revision"], generation)
    return {**result, "graph_version": GRAPH_VERSION,
            "snapshot_status": snapshot_status,
            "requested_revision": revision,
            "revision_changed": bool(revision and revision != snapshot.get("revision")),
            "mirror_status": mirror_status}


@app.get("/api/graph/{learner_id}/record")
def graph_record_view(learner_id: str, kind: str, id: str):
    from .graph_records import resolve_graph_record
    if learner_id != "demo-user":
        raise HTTPException(404, "learner not found")
    try:
        record = resolve_graph_record(store, learner_id, kind, id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if record is None:
        raise HTTPException(404, "canonical graph record not found")
    return record


@app.post("/api/preferences")
def update_preferences(body: dict):
    from .contracts import PreferenceUpdate
    from pydantic import ValidationError
    try:
        request = PreferenceUpdate.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(422, "invalid preference payload") from exc
    session = store.get_session(request.session_id)
    if not session:
        raise HTTPException(404, "session not found")
    goal = request.goal_dimension if "goal_dimension" in request.model_fields_set else session.get("goal_dimension")
    updated = store.set_preferences(request.session_id, request.dashboard_mode, goal)
    if goal != session.get("goal_dimension"):
        # A goal change is a documented plan refresh trigger; a dashboard-mode change is
        # presentational only and must leave the plan and event history untouched.
        try:
            from .plan_v2 import reconcile_plan
            reconcile_plan(store, {"kind": "goal_changed",
                                   "reference": f"{request.session_id}:{updated.get('goal_dimension')}",
                                   "goal_dimension": updated.get("goal_dimension")},
                           session_id=request.session_id, goal_dimension=updated.get("goal_dimension"))
        except (sqlite3.Error, KeyError, TypeError, ValueError):
            # Preferences are canonical and remain successful even if the optional
            # derived plan refresh cannot be reconciled in this request.
            logger.exception("plan reconciliation failed after goal change",
                             extra={"session_id": request.session_id,
                                    "goal_dimension": updated.get("goal_dimension")})
    return updated
# Auxiliary presentation and data-management surfaces share the canonical store.
from .coach_routes import create_coach_router
from .lifecycle_routes import create_lifecycle_router
app.include_router(create_coach_router(store))
app.include_router(create_lifecycle_router(store))
from .collaboration_routes import create_collaboration_router
app.include_router(create_collaboration_router(store, public_event,
    regenerate_plan=lambda session_id, goal: next_plan(PlanNextRequest(session_id=session_id, goal_dimension=goal))))
from .collaboration_v2_routes import create_collaboration_v2_router
app.include_router(create_collaboration_v2_router(store))

# Hybrid activities keep their own versioned contracts and never touch EX scoring.
from .hybrid_routes import register_hybrid_routes
register_hybrid_routes(app, store)

# Crystal matrices are a separate practice form, never a replacement baseline.
from .crystal_reasoning import register_crystal_routes
register_crystal_routes(app, store)

from .plan_v3 import register_plan_v3_routes
register_plan_v3_routes(app, store, core_launcher=create_plan_training_block)

# Local companion speech (KittenTTS). Off by default in the UI; local-only synthesis.
from .speech_service import register_speech_routes
register_speech_routes(app, store)
