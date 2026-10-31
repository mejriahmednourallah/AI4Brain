"""Task-specific four-eligible-trial difficulty policy."""
from __future__ import annotations
from .policy import DIFFICULTY_POLICY_VERSION
RULE_VERSION=DIFFICULTY_POLICY_VERSION
TIERS=("tier-1","tier-2","tier-3")
# Distinct uninterrupted trials that make up one tier decision window.
DECISION_TRIAL_COUNT=4

def current_tier(events:list[dict],dimension:str,default:str="tier-1")->str:
    """Canonical current tier for one family, from its latest recorded decision.

    Difficulty decisions are immutable and each writes a `difficulty_changed` event, so
    replaying the newest one for the family is authoritative. Automatic recommendation
    gating is deliberately separate: it must not reset a completed family's progression.
    """
    tier=default
    for event in events:
        payload=event.get("payload",event)
        if event.get("type")!="difficulty_changed" and payload.get("event_type")!="difficulty_changed":continue
        if payload.get("dimension")!=dimension:continue
        if payload.get("new_tier") in TIERS:tier=payload["new_tier"]
    return tier

def _success(exercise_id:str,payload:dict)->bool:
    evaluation=payload.get("evaluation",{})
    if exercise_id=="EX-05":
        # A completed route counts only at 80% or better of the BFS shortest-path efficiency.
        return bool(evaluation.get("completed")) and float(evaluation.get("efficiency_0_100") or 0)>=80
    return bool(evaluation.get("correct"))

def decide_difficulty(block_id:str,learner_id:str,tier:str,events:list[dict])->dict|None:
    if tier not in TIERS:return None
    block=next((e.get("payload",{}) for e in events if e.get("payload",{}).get("training_block_id")==block_id),{})
    exercise_id=block.get("exercise_id","EX-02")
    attempts=[];seen=set()
    for event in events:
        p=event.get("payload",{});i=p.get("interaction",{})
        item=p.get("item_id")
        if p.get("training_block_id")!=block_id or p.get("phase")!="training" or i.get("visibility_interrupted") or not item or item in seen:continue
        if p.get("exercise_id")!=exercise_id or p.get("item_difficulty")!=tier:continue
        seen.add(item);attempts.append(event)
    if len(attempts)<DECISION_TRIAL_COUNT:return None
    attempted=attempts[:DECISION_TRIAL_COUNT]
    eligible=[e for e in attempted if not e["payload"].get("interaction",{}).get("hint_count",0) and not e["payload"].get("interaction",{}).get("replay_count",0)]
    successes=sum(_success(exercise_id,e["payload"]) for e in eligible)
    index=TIERS.index(tier)
    if len(eligible)<DECISION_TRIAL_COUNT:
        ni=index;action="hold"
    elif successes>=3:
        ni=min(index+1,len(TIERS)-1);action="up" if ni>index else "hold"
    elif successes<=1:
        ni=max(index-1,0);action="down" if ni<index else "hold"
    else:ni=index;action="hold"
    success_definition="BFS-optimal-route completion efficiency >=80" if exercise_id=="EX-05" else {
        "EX-01":"exact ordered sequence recall","EX-02":"correct matrix rule response","EX-03":"task-specific go hit or no-go correct rejection",
        "EX-04":"correct response under active rule"}[exercise_id]
    if len(eligible)<DECISION_TRIAL_COUNT:
        rationale=f"Four distinct uninterrupted items were attempted, but only {len(eligible)} were unassisted. The tier is held, assisted attempts (hints or replayed cues) remain excluded, and gather more evidence in a new block with unassisted attempts."
        reason_codes=["insufficient_unassisted_evidence","hinted_trials_excluded","assisted_trials_excluded","hold_and_gather_more_evidence"]
    else:
        rationale=f"{successes} of {DECISION_TRIAL_COUNT} eligible, unassisted, uninterrupted {exercise_id} trials met its task-specific success rule ({success_definition}); the same-family tier {action} rule was applied."
        reason_codes=[f"{successes}_of_4_task_successes",f"{action}_rule_applied","same_family_same_tier_window"]
    return {"block_id":block_id,"learner_id":learner_id,"exercise_id":exercise_id,"dimension":block.get("dimension"),
        "old_tier":tier,"new_tier":TIERS[ni],"action":action,"rule_version":RULE_VERSION,"successes":successes,
        "trial_count":DECISION_TRIAL_COUNT,"valid_trial_count":len(eligible),"success_definition":success_definition,"rationale":rationale,
        "reason_codes":reason_codes,"evidence_ids":[e["event_id"] for e in attempted]}
