"""Deterministic evidence-gated next-activity selector."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .policy import BASELINE_REQUIRED, DEFAULT_BUDGET_MINUTES, DIMENSION_TO_EXERCISE, DISPLAY_NAMES, POLICY_VERSION, WEIGHTS

def _date(value: str | None):
    if not value: return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError): return None

def select_next(profile: dict[str,Any], events: list[dict[str,Any]], goal_dimension: str|None=None,
                budget_minutes: int|None=None, selection_count: int=0,
                available_dimensions: list[str]|None=None) -> dict[str,Any]:
    dimensions=profile.get("dimensions",{})
    all_dimensions=list(DIMENSION_TO_EXERCISE)
    constraint=None
    if available_dimensions is None:
        candidates=all_dimensions
    else:
        requested=list(dict.fromkeys(available_dimensions))
        unknown=[d for d in requested if d not in DIMENSION_TO_EXERCISE]
        candidates=[d for d in all_dimensions if d in requested]
        constraint={"applied":True,"requested":requested,"unknown":unknown}
        if not candidates:
            return {"action":"no_available_activity","exercise_id":None,"dimension":None,"tier":None,
                "selected_strategy_id":None,
                "reason_codes":["availability_constraint_excludes_every_family"],
                "evidence_ids":[],
                "features":{"availability_constraint_applied":True,"available_count":0,"unknown_count":len(unknown)},
                "alternatives":[],"availability":constraint,
                "rationale":"The supplied availability constraint excludes every task family, so no activity is scheduled.",
                "policy_version":POLICY_VERSION,"budget_minutes":budget_minutes or DEFAULT_BUDGET_MINUTES}

    latest_practice={}
    for event in events:
        p=event.get("payload",event)
        if p.get("phase") not in {"training","practice"}: continue
        interaction=p.get("interaction",{})
        if interaction.get("visibility_interrupted") or interaction.get("hint_count",0): continue
        d=p.get("dimension"); stamp=event.get("created_at") or p.get("recorded_at")
        if d in candidates and stamp and stamp>latest_practice.get(d,""): latest_practice[d]=stamp
    missing=[d for d in candidates if int(dimensions.get(d,{}).get("evidence_count",0))<BASELINE_REQUIRED[d] or not dimensions.get(d,{}).get("completed",False)]
    plan=dimensions.get("planning",{})
    planning_reassessments=[e for e in events if e.get("payload",{}).get("phase")=="reassessment" and e.get("payload",{}).get("exercise_id")=="EX-05" and not e.get("payload",{}).get("interaction",{}).get("visibility_interrupted") and not e.get("payload",{}).get("interaction",{}).get("hint_count",0)]
    planning_selection_index=plan.get("selection_index_0_100",plan.get("index_0_100"))
    planning_reassessment_count=int(plan.get("reassessment_evidence_count",len(planning_reassessments)))
    low_planning="planning" in candidates and plan.get("completed") and planning_selection_index is not None and float(planning_selection_index)<60 and int(plan.get("evidence_count",0))==3 and planning_reassessment_count<3
    if low_planning: missing.append("planning")
    missing=list(dict.fromkeys(missing))
    if missing:
        chosen=min(missing,key=lambda d:(int(dimensions.get(d,{}).get("evidence_count",0)),candidates.index(d)))
        observed=dimensions.get(chosen,{})
        reasons=["missing_or_insufficient_baseline_evidence","assess_before_targeted_training"]
        action="complete_baseline"
        if chosen=="planning" and observed.get("completed"):
            action="additional_assessment"
            reasons=["planning_has_only_three_low_efficiency_puzzles","additional_comparable_evidence_before_weakness_claim"]
            observed_ids=list(observed.get("evidence_ids",[]))+list(observed.get("reassessment_evidence_ids",[]))
        else:
            observed_ids=list(observed.get("evidence_ids",[]))
        return {"action":action,"exercise_id":DIMENSION_TO_EXERCISE[chosen],"dimension":chosen,"tier":"reassessment" if action=="additional_assessment" else "baseline",
            "selected_strategy_id":None,"reason_codes":reasons,"evidence_ids":observed_ids,
            "features":{"assessment_gate":True,"evidence_count":int(observed.get("evidence_count",0)),
                        "required_evidence_count":BASELINE_REQUIRED[chosen],"goal_weight":float(chosen==goal_dimension)},
            "alternatives":[{"dimension":d,"action":"additional_assessment"} for d in missing if d!=chosen],
            "rationale":f"{DISPLAY_NAMES[chosen]} needs more valid task-specific evidence before targeted training can be justified.",
            "availability":constraint,
            "policy_version":POLICY_VERSION,"budget_minutes":budget_minutes or DEFAULT_BUDGET_MINUTES}
    exploration=(selection_count+1)%4==0
    features_by_dimension={}
    tier_by_dimension={}
    for event in events:
        p=event.get("payload",event)
        if event.get("type")=="difficulty_changed" or p.get("event_type")=="difficulty_changed":
            dimension=p.get("dimension")
            if dimension in candidates and p.get("new_tier") in {"tier-1","tier-2","tier-3"}:
                tier_by_dimension[dimension]=p["new_tier"]
    if exploration:
        ranked=[(d,0.0) for d in candidates]
        chosen=min(candidates,key=lambda d:(latest_practice.get(d,""),candidates.index(d)))
        reasons=["scheduled_exploration_every_fourth_selection","least_recently_practiced_dimension"]
        features={"exploration":1.0,"practice_recency":1.0 if chosen not in latest_practice else 0.0}
    else:
        now=datetime.now(timezone.utc); scores={}
        for d in candidates:
            data=dimensions.get(d,{}); score=data.get("index_0_100")
            if d=="planning": score=data.get("selection_index_0_100",score)
            gap=max(0.0,min(1.0,1-float(score)/100)) if score is not None else 0.0
            goal=1.0 if d==goal_dimension else 0.0
            practiced=_date(latest_practice.get(d)); days=max(0,(now-practiced).total_seconds()/86400) if practiced else 30
            recency=min(1.0,days/30)
            status=str(data.get("uncertainty_status","")); uncertainty=1.0 if "HIGH" in status or "INCOMPLETE" in status else .5
            features_by_dimension[d]={"performance_gap":round(gap,4),"user_goal_weight":goal,"practice_recency":round(recency,4),"uncertainty_need":uncertainty}
            scores[d]=sum(WEIGHTS[k]*features_by_dimension[d][k] for k in WEIGHTS)
        ranked=sorted(scores.items(),key=lambda x:(-x[1],candidates.index(x[0])))
        chosen=ranked[0][0]; features=features_by_dimension[chosen]
        reasons=["weighted_personalization_heuristic","usable_baseline_evidence"]
        if goal_dimension==chosen: reasons.append("explicit_user_goal")
    data=dimensions.get(chosen,{})
    tier=tier_by_dimension.get(chosen,"tier-1")
    if chosen in tier_by_dimension: reasons.append("continue_from_latest_same_family_difficulty_decision")
    return {"action":"targeted_training","exercise_id":DIMENSION_TO_EXERCISE[chosen],"dimension":chosen,"tier":tier,
        "selected_strategy_id":None,"reason_codes":reasons,"evidence_ids":list(data.get("evidence_ids",[])),
        "features":features,"alternatives":[{"dimension":d,"priority":round(s,4)} for d,s in ranked if d!=chosen],
        "rationale":f"Selected {DISPLAY_NAMES[chosen]} using the versioned task-specific gap, goal, recency and uncertainty heuristic.",
        "availability":constraint,
        "policy_version":POLICY_VERSION,"budget_minutes":budget_minutes or DEFAULT_BUDGET_MINUTES}

def sample_profile_scenarios():
    """Synthetic policy fixtures only; they are never persisted as learner history."""
    out=[]
    fixtures=[
        ("sample-low-memory",{"working_memory":35,"reasoning":88,"attention_inhibition":80,"flexibility":75,"planning":70},None),
        ("sample-user-goal-planning",{"working_memory":90,"reasoning":90,"attention_inhibition":90,"flexibility":90,"planning":80},"planning")]
    for label,scores,goal in fixtures:
        profile={"dimensions":{d:{"index_0_100":v,"evidence_count":BASELINE_REQUIRED[d],"completed":True,
            "uncertainty_status":"PRELIMINARY_HIGH_UNCERTAINTY","evidence_ids":[f"sample-{label}-{d}"]} for d,v in scores.items()}}
        decision=select_next(profile,[],goal_dimension=goal)
        out.append({"label":label,"sample_data":True,"selected_dimension":decision["dimension"],"decision":decision})
    return out


