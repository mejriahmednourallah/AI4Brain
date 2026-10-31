"""Grounded, deterministic strategy selection from recorded task errors."""
from __future__ import annotations
from typing import Any

STRATEGIES={
    "memory_order_mismatch":{"id":"memory-chunk-sequence","dimension":"working_memory","title":"Chunk the sequence","guidance":"Group the positions into short chunks, then replay the chunks in order."},
    "attention_commission":{"id":"attention-target-reminder","dimension":"attention_inhibition","title":"Pause on no-go cues","guidance":"Use a slower training pace and check for the no-go cue before responding."},
    "attention_omission":{"id":"attention-targeting","dimension":"attention_inhibition","title":"Recheck the go target","guidance":"Keep the go target in view and respond when that target appears."},
    "switch_previous_rule":{"id":"switch-transition-cue","dimension":"flexibility","title":"Mark the rule change","guidance":"Pause at each transition cue and name the active rule before choosing."},
    "switch_incorrect_rule":{"id":"switch-rule-check","dimension":"flexibility","title":"Check the active rule","guidance":"Identify the active rule first, then compare both options using that rule."},
    "planning_inefficient":{"id":"planning-subgoals","dimension":"planning","title":"Plan with subgoals","guidance":"Break the route into small subgoals and compare the next move with the shortest path."},
    "planning_incomplete":{"id":"planning-legal-moves","dimension":"planning","title":"Check legal moves","guidance":"Trace one legal move at a time, checking walls and board edges."},
    "reasoning_count":{"id":"reasoning-compare-count","dimension":"reasoning","title":"Compare the count rule","guidance":"Compare counts across rows and test the same change on both rows."},
    "reasoning_rotation":{"id":"reasoning-compare-rotation","dimension":"reasoning","title":"Compare rotations","guidance":"Track the rotation step across both rows before selecting a tile."},
    "reasoning_other":{"id":"reasoning-contrast-example","dimension":"reasoning","title":"Use a contrasting example","guidance":"Compare the candidate rule with one contrasting example and test it in both rows."},
}

def strategy_for_error(exercise_id: str, error_type: str|None) -> dict[str,Any]|None:
    if not error_type: return None
    key=None; kind=str(error_type).lower()
    if exercise_id=="EX-01" and ("order" in kind or "position" in kind): key="memory_order_mismatch"
    elif exercise_id=="EX-03" and ("commission" in kind or "no_go" in kind): key="attention_commission"
    elif exercise_id=="EX-03" and ("omission" in kind or "go" in kind): key="attention_omission"
    elif exercise_id=="EX-04" and ("previous_rule" in kind): key="switch_previous_rule"
    elif exercise_id=="EX-04": key="switch_incorrect_rule"
    elif exercise_id=="EX-05" and ("inefficient" in kind or "move" in kind): key="planning_inefficient"
    elif exercise_id=="EX-05": key="planning_incomplete"
    elif exercise_id=="EX-02" and "count" in kind: key="reasoning_count"
    elif exercise_id=="EX-02" and "rotation" in kind: key="reasoning_rotation"
    elif exercise_id=="EX-02": key="reasoning_other"
    return {**STRATEGIES[key],"error_type":error_type,"source":"recorded_server_evaluation"} if key else None

def latest_strategy(events: list[dict[str,Any]], exercise_id: str) -> dict[str,Any]|None:
    candidates=[]
    for event in events:
        p=event.get("payload",{})
        if p.get("exercise_id")!=exercise_id or p.get("phase") not in {"baseline","training"}: continue
        interaction=p.get("interaction",{})
        if interaction.get("visibility_interrupted") or interaction.get("hint_count",0): continue
        evaluation=p.get("evaluation",{})
        error_type=evaluation.get("error_type")
        # Planning can be completed/correct while still inefficient; its explicit server error
        # remains actionable even when the binary completion flag is true.
        actionable=bool(error_type) and (evaluation.get("correct") is False or
            (exercise_id=="EX-05" and "inefficient" in str(error_type).lower()))
        if actionable:
            strategy=strategy_for_error(exercise_id,error_type)
            if strategy:
                strategy["source_evidence_ids"]=[event.get("event_id") or p.get("event_id")]
                strategy["event_at"]=event.get("created_at") or p.get("recorded_at")
                candidates.append(strategy)
    return candidates[-1] if candidates else None
