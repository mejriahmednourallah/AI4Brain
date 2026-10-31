"""Profile assembly helpers shared by selection and planning."""
from __future__ import annotations
from typing import Any
from .battery_scoring import score_battery
from .scoring import score_reasoning

PLANNING_REASSESSMENT_IDS={f"planning-reassessment-{i:02d}" for i in range(1,4)}

def _coherent_planning_reassessment(events: list[dict[str,Any]]) -> list[dict[str,Any]]:
    groups: dict[tuple[str,str],list[dict[str,Any]]]={}
    for event in events:
        p=event.get("payload",{})
        if p.get("phase")!="reassessment" or p.get("exercise_id")!="EX-05" or p.get("exercise_version")!="reassessment-v1":continue
        groups.setdefault((event.get("session_id") or p.get("session_id",""),p.get("exercise_version","")),[]).append(event)
    if not groups:return []
    # The newest session that started a planning reassessment owns this evidence window.
    latest=max(groups,key=lambda key:max((e.get("session_started_at") or e.get("created_at") or e.get("payload",{}).get("recorded_at","") for e in groups[key]),default=""))
    rows=groups[latest]; by_item={}
    for event in rows:
        p=event.get("payload",{}); interaction=p.get("interaction",{})
        if p.get("item_id") not in PLANNING_REASSESSMENT_IDS or interaction.get("visibility_interrupted") or interaction.get("hint_count",0):continue
        by_item.setdefault(p["item_id"],event)
    if set(by_item)!=PLANNING_REASSESSMENT_IDS:return []
    return [by_item[item_id] for item_id in sorted(PLANNING_REASSESSMENT_IDS)]

def build_profile(events: list[dict[str,Any]]) -> dict[str,Any]:
    reasoning=score_reasoning(events)
    dims={"reasoning":{**reasoning,"status":"ASSESSED" if reasoning["completed"] else ("IN_PROGRESS" if reasoning["evidence_count"] else "NOT_ASSESSED")}}
    for name,data in score_battery(events).items():
        dims[name]={**data,"status":"ASSESSED" if data["completed"] else ("IN_PROGRESS" if data["evidence_count"] else "NOT_ASSESSED")}
    supplemental=_coherent_planning_reassessment(events)
    efficiencies=[float(e["payload"].get("evaluation",{}).get("efficiency_0_100")) for e in supplemental]
    planning=dims["planning"]
    planning["reassessment_evidence_count"]=len(efficiencies)
    planning["reassessment_evidence_ids"]=[e.get("event_id") or e.get("payload",{}).get("event_id") for e in supplemental]
    planning["reassessment_efficiencies"]=efficiencies
    planning["reassessment_session_id"]=(supplemental[0].get("session_id") or supplemental[0].get("payload",{}).get("session_id")) if supplemental else None
    baseline=planning.get("index_0_100")
    planning["selection_index_0_100"]=round((float(baseline)*3+sum(efficiencies))/(3+len(efficiencies)),2) if baseline is not None and efficiencies else baseline
    return {"dimensions":dims}

def dimension_history(events: list[dict[str,Any]]) -> dict[str,list[dict[str,Any]]]:
    history={d:[] for d in ("working_memory","reasoning","attention_inhibition","flexibility","planning")}
    for event in events:
        payload=event.get("payload",{})
        dimension=payload.get("dimension")
        if dimension in history and payload.get("phase") in {"training","practice"}:
            history[dimension].append(event)
    return history
