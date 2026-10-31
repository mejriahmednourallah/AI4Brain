"""Versioned task-specific baseline summaries; training never fills baseline slots."""
from __future__ import annotations
from statistics import median
from typing import Any
from .battery_exercises import DIMENSIONS,VERSIONS,exercise_items

COUNTS={'EX-01':6,'EX-03':40,'EX-04':24,'EX-05':3}

def score_family(events: list[dict[str,Any]], exercise_id: str) -> dict[str,Any]:
    dimension=DIMENSIONS[exercise_id]
    rows=[e for e in events if e['payload'].get('phase')=='baseline' and e['payload'].get('exercise_id')==exercise_id and e['payload'].get('exercise_version')==VERSIONS[exercise_id]]
    latest=max(rows,key=lambda e:(e.get('session_started_at',''),e.get('created_at','')))['session_id'] if rows else None
    session=[e for e in rows if e['session_id']==latest]
    interrupted=[e for e in session if e['payload'].get('interaction',{}).get('visibility_interrupted')]
    valid={}
    for event in session:
        p=event['payload'];interaction=p.get('interaction',{})
        if not interaction.get('visibility_interrupted') and not interaction.get('hint_count',0):valid.setdefault(p['item_id'],event)
    bank=exercise_items(exercise_id,latest or '')
    ordered=[valid[item['item_id']] for item in bank if item['item_id'] in valid]
    expected=COUNTS[exercise_id];complete=len(ordered)==expected
    evaluations=[e['payload']['evaluation'] for e in ordered]
    base={'scoring_version':'score-v1','dimension':dimension,'exercise_id':exercise_id,'assessment_session_id':latest,'completed':complete,
          'evidence_count':len(ordered),'required_evidence_count':expected,'evidence_ids':[e['event_id'] for e in ordered],
          'interrupted_count':len(interrupted),'uncertainty_status':'PRELIMINARY_HIGH_UNCERTAINTY' if complete else 'INCOMPLETE_BASELINE',
          'uncertainty_note':'Brief task-specific sample. Insufficient evidence for a reliable trait estimate or narrow interval.'}
    if exercise_id=='EX-01':
        correct=sum(sum(e.get('position_correct',[])) for e in evaluations)
        longest=max((int(e.get('fully_correct_span',0)) for e in evaluations),default=0)
        base.update(index_0_100=round(100*correct/24,2) if complete else None,correct_positions=correct,total_positions=24,
                    longest_fully_correct_span=longest,longest_correct_span=longest)
    elif exercise_id=='EX-03':
        go=[e for e in ordered if e['payload']['stimulus_config'].get('stimulus',e['payload']['stimulus_config']).get('signal')=='go']
        no_go=[e for e in ordered if e['payload']['stimulus_config'].get('stimulus',e['payload']['stimulus_config']).get('signal')=='no_go']
        hits=sum(e['payload']['evaluation']['result']=='hit' for e in go)
        rejections=sum(e['payload']['evaluation']['result']=='correct_rejection' for e in no_go)
        hit_rate=hits/len(go) if go else None; rejection_rate=rejections/len(no_go) if no_go else None
        times=[e['payload']['evaluation']['response_time_ms'] for e in go if e['payload']['evaluation']['result']=='hit' and not e['payload']['evaluation'].get('outlier') and e['payload']['evaluation'].get('response_time_ms') is not None]
        base.update(index_0_100=round(50*(hit_rate+rejection_rate),2) if complete and hit_rate is not None and rejection_rate is not None else None,
                    go_hits=hits,go_omissions=len(go)-hits,no_go_correct_rejections=rejections,no_go_commissions=len(no_go)-rejections,
                    hit_rate=round(100*hit_rate,2) if hit_rate is not None else None,correct_rejection_rate=round(100*rejection_rate,2) if rejection_rate is not None else None,
                    median_response_time_ms=median(times) if times else None,early_responses=sum(bool(e.get('early')) for e in evaluations),
                    outlier_responses=sum(bool(e.get('outlier')) for e in evaluations),late_responses=sum(bool(e.get('late_response')) for e in evaluations))
    elif exercise_id=='EX-04':
        switch=[e for e in evaluations if e.get('component')=='switch'];repeat=[e for e in evaluations if e.get('component')=='repeat']
        sc=sum(bool(e['correct']) for e in switch);rc=sum(bool(e['correct']) for e in repeat)
        sr=sc/len(switch) if switch else None;rr=rc/len(repeat) if repeat else None
        base.update(index_0_100=round(50*(sr+rr),2) if complete and sr is not None and rr is not None else None,
                    switch_correct=sc,switch_trials=len(switch),repeat_correct=rc,repeat_trials=len(repeat),
                    switch_accuracy=round(100*sr,2) if sr is not None else None,repeat_accuracy=round(100*rr,2) if rr is not None else None,
                    error_previous_rule=sum(bool(e.get('error_previous_rule')) for e in evaluations))
    else:
        scores=[float(e.get('efficiency_0_100',0)) for e in evaluations]
        puzzle_observations=[]
        for event in ordered:
            payload=event['payload'];evaluation=payload['evaluation']
            puzzle_observations.append({
                'item_id':payload['item_id'],'event_id':event['event_id'],
                'completed':bool(evaluation.get('completed')),
                'optimal_moves':evaluation.get('optimal_moves'),
                'legal_moves':evaluation.get('legal_moves'),
                'illegal_moves':evaluation.get('illegal_moves'),
                'excess_moves':evaluation.get('excess_moves') if evaluation.get('completed') else None,
                'undo_count':evaluation.get('undo_count'),'restart_count':evaluation.get('restart_count'),
                'efficiency_0_100':evaluation.get('efficiency_0_100'),
            })
        completed_excess=[row['excess_moves'] for row in puzzle_observations if row['completed'] and row['excess_moves'] is not None]
        base.update(index_0_100=round(sum(scores)/3,2) if complete else None,puzzle_efficiencies=scores,
                    completed_puzzles=sum(bool(e.get('completed')) for e in evaluations),
                    puzzle_observations=puzzle_observations,
                    excess_moves=sum(completed_excess) if completed_excess else None,
                    **{key:sum(int(e.get(key,0)) for e in evaluations) for key in ('legal_moves','illegal_moves','undo_count','restart_count')})
    return base

def score_battery(events: list[dict[str,Any]]) -> dict[str,dict[str,Any]]:
    return {DIMENSIONS[exercise]:score_family(events,exercise) for exercise in DIMENSIONS}
