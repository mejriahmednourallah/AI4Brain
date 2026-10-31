"""Versioned short adaptive plan builder; plans retain before/after snapshots."""
from __future__ import annotations
import json
from typing import Any
from .policy import DISPLAY_NAMES, PLAN_POLICY_VERSION
from .selector import select_next

DURATION={"EX-01":2,"EX-02":2,"EX-03":2,"EX-04":2,"EX-05":2}
def build_plan(profile:dict[str,Any],events:list[dict[str,Any]],goal_dimension:str|None=None,
               budget_minutes:int|None=None,selection_count:int=0,previous:dict[str,Any]|None=None,
               strategies:dict[str,dict[str,Any]]|None=None)->dict[str,Any]:
    budget=max(1,int(budget_minutes or 12)); chosen=select_next(profile,events,goal_dimension,budget,selection_count)
    dimension=chosen["dimension"]; ex=chosen["exercise_id"]; action=chosen["action"]
    steps=[]; remaining=budget
    ordering=[dimension]+[d for d in ("working_memory","reasoning","attention_inhibition","flexibility","planning") if d!=dimension]
    for d in ordering:
        if len(steps)>=4: break
        eid={"working_memory":"EX-01","reasoning":"EX-02","attention_inhibition":"EX-03","flexibility":"EX-04","planning":"EX-05"}[d]
        duration=DURATION[eid]
        if steps and remaining<duration: continue
        candidate=chosen if d==dimension else select_next(profile,events,goal_dimension=d,budget_minutes=budget,selection_count=selection_count,available_dimensions=[d])
        strategy=(strategies or {}).get(d) if candidate["action"]=="targeted_training" else None
        reason="; ".join(candidate["reason_codes"])
        if d!=dimension and candidate["action"]=="targeted_training": reason="optional_goal_or_maintenance_practice"
        steps.append({"step_id":f"step-{len(steps)+1}","dimension_id":d,"exercise_type_id":eid,
            "action":candidate["action"],"difficulty_tier":candidate["tier"],"strategy_id":strategy.get("id") if strategy else None,
            "selection_reason":reason,"source_evidence_ids":candidate["evidence_ids"],
            "estimated_time_minutes":duration,"status":"recommended"})
        remaining-=duration
    if len(steps)<2:
        # Short budgets still produce a coherent two-step plan, transparently marking the second estimate.
        d=next(d for d in ordering if d!=dimension)
        eid={"working_memory":"EX-01","reasoning":"EX-02","attention_inhibition":"EX-03","flexibility":"EX-04","planning":"EX-05"}[d]
        steps.append({"step_id":"step-2","dimension_id":d,"exercise_type_id":eid,"action":"additional_assessment",
            "difficulty_tier":"baseline","strategy_id":None,"selection_reason":"minimum_two_step_plan",
            "source_evidence_ids":profile.get("dimensions",{}).get(d,{}).get("evidence_ids",[]),
            "estimated_time_minutes":DURATION[eid],"status":"recommended"})
    meaningful=not previous or previous.get("decision_fingerprint")!=_fingerprint(chosen,steps,goal_dimension,budget)
    reason_codes=chosen["reason_codes"][:] if meaningful else ["no_meaningful_new_evidence_or_preference_change","retained_current_plan"]
    return {"plan_id":None,"learner_id":"demo-user","profile_snapshot_id":None,"policy_version":PLAN_POLICY_VERSION,
        "selection_policy_version":chosen["policy_version"],"goal":goal_dimension,"created_at":None,
        "estimated_time_minutes":sum(s["estimated_time_minutes"] for s in steps),"budget_minutes":budget,
        "reason_codes":reason_codes,"rationale":chosen["rationale"] if meaningful else "No material evidence or preference change since the prior plan; retaining the current recommendations.",
        "steps":steps,"status":"active","changed":meaningful,"features":chosen["features"],"alternatives":chosen["alternatives"],
        "evidence_ids":chosen["evidence_ids"],"decision_fingerprint":_fingerprint(chosen,steps,goal_dimension,budget)}
def _fingerprint(chosen,steps,goal,budget):
    return json.dumps([chosen["action"],chosen["dimension"],goal,budget,
        [[s["dimension_id"],s["action"],s["difficulty_tier"],s["strategy_id"],s.get("source_evidence_ids",[])] for s in steps],
        chosen["evidence_ids"]],separators=(",",":"))
