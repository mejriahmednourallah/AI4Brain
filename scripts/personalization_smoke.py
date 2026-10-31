"""Focused disposable-DB smoke for the versioned personalization backend batch."""
from __future__ import annotations
import os
import tempfile
import uuid
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

os.environ["NEO4J_ENABLED"]="false"
with tempfile.TemporaryDirectory(prefix="ai4brain-personalization-") as tmp:
    os.environ["AI4BRAIN_DB"]=str(Path(tmp)/"smoke.sqlite3")
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    from backend.app.battery_exercises import (DIMENSIONS, VERSIONS, LEGACY_TRAINING_VERSIONS, TRAINING_VERSIONS, REASSESSMENT_VERSION,
        shortest_path, battery_reassessment_exercise, evaluate_switch, replay_planning)
    from backend.app.exercises import EXERCISE_VERSION, LEGACY_TRAINING_EXERCISE_VERSION, TRAINING_EXERCISE_VERSION, ANSWER_KEY, make_training_bank
    from backend.app.policy import BASELINE_REQUIRED
    from backend.app.selector import select_next, sample_profile_scenarios
    from backend.app.strategy import strategy_for_error, latest_strategy
    from backend.app.difficulty import current_tier
    from backend.app.scoring import score_reasoning
    from backend.app.battery_scoring import score_battery

    client=TestClient(app)
    def new_session():
        response=client.post("/api/sessions",json={"learner_id":"demo-user","consent_accepted":True})
        assert response.status_code==201,response.text
        return response.json()["id"]

    def create_response(item,eid,correct=True,version=None,block_id=None):
        stimulus=item.get("stimulus",{})
        if eid=="EX-02":
            answer=ANSWER_KEY.get(item["item_id"])
            if answer is None:
                for tier_name in ("tier-1","tier-2","tier-3"):
                    answer=next((row["answer"] for row in make_training_bank(tier_name,block_id,version or "training-v1") if row["item_id"]==item["item_id"]),None)
                    if answer:break
            if correct:return {"choice":answer}
            return {"choice":next(k for k in "ABCD" if k!=answer)}
        if eid=="EX-01":
            seq=stimulus["sequence"]
            return {"response_data":{"selected_sequence":seq if correct else ([((seq[0]+1)%9)]+seq[1:])}}
        if eid=="EX-03":
            signal=stimulus["signal"]
            press=(signal=="go") if correct else (signal!="go")
            return {"response_data":{"responded":press},"response_time_ms":400 if press else None}
        if eid=="EX-04":
            options=stimulus["options"]
            right=next(o["id"] for o in options if o[stimulus["active_rule"]]==stimulus["target"][stimulus["active_rule"]])
            choice=right if correct else next(o["id"] for o in options if o["id"]!=right)
            return {"response_data":{"choice":choice}}
        if eid=="EX-05":
            path=shortest_path(stimulus)
            actions=[{"action":"move","direction":step} for step in path] if correct else []
            return {"response_data":{"actions":actions}}

    def post_trial(sid,eid,item,phase,version,answer=None,block_id=None,hint_count=0,interrupted=False):
        args=answer or create_response(item,eid,version=version,block_id=block_id)
        payload={"event_id":str(uuid.uuid4()),"session_id":sid,"learner_id":"demo-user","phase":phase,
            "exercise_id":eid,"exercise_version":version,"item_id":item["item_id"],"hint_count":hint_count,
            "visibility_interrupted":interrupted,"training_block_id":block_id,**args}
        response=client.post("/api/trials",json=payload)
        assert response.status_code==200,(eid,phase,response.status_code,response.text)
        return response.json()

    sid=new_session()
    baseline_items={}
    # Collect only explicit synthetic QA events in this disposable database.
    ex02=client.get("/api/exercises/EX-02?phase=baseline").json()["items"]
    for item in ex02:post_trial(sid,"EX-02",item,"baseline",EXERCISE_VERSION)
    for eid in DIMENSIONS:
        config=client.get(f"/api/exercises/{eid}",params={"session_id":sid,"phase":"baseline"})
        assert config.status_code==200,config.text
        rows=config.json()["items"];baseline_items[eid]=rows
        for item in rows:post_trial(sid,eid,item,"baseline",VERSIONS[eid])
    profile=client.get("/api/profile/demo-user").json()
    assert all(profile["dimensions"][name]["completed"] for name in BASELINE_REQUIRED)
    before={name:profile["dimensions"][name]["index_0_100"] for name in BASELINE_REQUIRED}
    assert all(profile["dimensions"][name]["evidence_count"]==BASELINE_REQUIRED[name] for name in BASELINE_REQUIRED)
    # A legacy battery block resolves the exact v1 stimulus through both GET routes and remains replayable.
    legacy_id=str(uuid.uuid4())
    store.create_training_block(legacy_id,"demo-user",sid,"tier-1",LEGACY_TRAINING_VERSIONS["EX-01"],"EX-01",DIMENSIONS["EX-01"])
    legacy_get=client.get(f"/api/training/blocks/{legacy_id}")
    legacy_family_get=client.get("/api/exercises/EX-01",params={"session_id":sid,"phase":"training","training_block_id":legacy_id})
    assert legacy_get.status_code==200 and legacy_family_get.status_code==200
    legacy_items=legacy_get.json()["exercise"]["items"]
    assert legacy_get.json()["exercise"]["exercise_version"]==LEGACY_TRAINING_VERSIONS["EX-01"]
    assert legacy_items==legacy_family_get.json()["items"]
    legacy_item=legacy_items[0];legacy_sequence=legacy_item["stimulus"]["sequence"];legacy_event=str(uuid.uuid4())
    legacy_body={"event_id":legacy_event,"session_id":sid,"learner_id":"demo-user","phase":"training","exercise_id":"EX-01",
        "exercise_version":LEGACY_TRAINING_VERSIONS["EX-01"],"training_block_id":legacy_id,"item_id":legacy_item["item_id"],
        "response_data":{"selected_sequence":legacy_sequence}}
    legacy_first=client.post("/api/trials",json=legacy_body);legacy_retry=client.post("/api/trials",json=legacy_body)
    assert legacy_first.status_code==200 and legacy_retry.status_code==200 and legacy_retry.json()["replayed"]
    changed_sequence=list(legacy_sequence);changed_sequence[0]=(changed_sequence[0]+1)%9
    assert client.post("/api/trials",json={**legacy_body,"response_data":{"selected_sequence":changed_sequence}}).status_code==409

    # Assessment gate, finite low-planning follow-up, and divergent synthetic-only profiles.
    gate=select_next({"dimensions":{}},[])
    assert gate["action"]=="complete_baseline" and gate["features"]["assessment_gate"]
    fixture={k:dict(v) for k,v in profile["dimensions"].items()}
    fixture["planning"]={**fixture["planning"],"index_0_100":45,"selection_index_0_100":45,"evidence_count":3,"completed":True,"reassessment_evidence_count":0}
    planning=select_next({"dimensions":fixture},[])
    assert planning["action"]=="additional_assessment" and planning["exercise_id"]=="EX-05"
    reassess=battery_reassessment_exercise("EX-05",sid)
    assert reassess["exercise_version"]==REASSESSMENT_VERSION and len(reassess["items"])==3
    assert not {x["item_id"] for x in reassess["items"]}&{x["item_id"] for x in baseline_items["EX-05"]}
    fixture["planning"]["reassessment_evidence_count"]=3
    fixture["planning"]["selection_index_0_100"]=55
    after_extra=select_next({"dimensions":fixture},[])
    assert after_extra["action"]=="targeted_training"
    scenarios=sample_profile_scenarios()
    assert all(x["sample_data"] for x in scenarios) and scenarios[0]["selected_dimension"]!=scenarios[1]["selected_dimension"]
    recently=[{"payload":{"dimension":d,"phase":"training","recorded_at":"2026-10-18T10:00:00+00:00"}} for d in BASELINE_REQUIRED if d!="planning"]
    recently.extend([
        {"payload":{"dimension":"planning","phase":"training","recorded_at":"2026-10-18T11:00:00+00:00","interaction":{"hint_count":1}}},
        {"payload":{"dimension":"planning","phase":"training","recorded_at":"2026-10-18T12:00:00+00:00","interaction":{"visibility_interrupted":True}}}])
    exploration=select_next({"dimensions":profile["dimensions"]},recently,selection_count=3)
    assert exploration["dimension"]=="planning" and "scheduled_exploration_every_fourth_selection" in exploration["reason_codes"]
    tier_profile={"dimensions":{**profile["dimensions"],"working_memory":{**profile["dimensions"]["working_memory"],"index_0_100":10}}}
    tier_choice=select_next(tier_profile,[{"type":"difficulty_changed","payload":{"dimension":"working_memory","new_tier":"tier-2"}}])
    assert tier_choice["dimension"]=="working_memory" and tier_choice["tier"]=="tier-2"

    # Legacy banks remain stable; v2 forms are stable per block seed and differ across blocks.
    from backend.app.battery_exercises import battery_training_exercise, exercise_items
    baseline_sequences={tuple(x["stimulus"]["sequence"]) for x in exercise_items("EX-01",sid)}
    for level,length in ((1,3),(2,4),(3,5)):
        tier=f"tier-{level}"
        memory=battery_training_exercise("EX-01",tier,f"mem-{tier}")["items"]
        assert len(memory)==8 and {x["stimulus"]["length"] for x in memory}=={length}
        assert len({x["item_id"] for x in memory})==8
        assert not any(tuple(x["stimulus"]["sequence"]) in baseline_sequences for x in memory)
        switches=battery_training_exercise("EX-04",tier,f"switch-{tier}")["items"]
        assert sum(bool(x["stimulus"]["switch"]) for x in switches[:4])==level
        assert all(sum(o["color"]==x["stimulus"]["target"]["color"] for o in x["stimulus"]["options"])==1
                   and sum(o["shape"]==x["stimulus"]["target"]["shape"] for o in x["stimulus"]["options"])==1 for x in switches)
    from backend.app.battery_exercises import LEGACY_TRAINING_VERSIONS
    from backend.app.exercises import LEGACY_TRAINING_EXERCISE_VERSION
    from backend.app.battery_exercises import training_items
    legacy_attention=battery_training_exercise("EX-03","tier-1","legacy-attention",LEGACY_TRAINING_VERSIONS["EX-03"])
    assert legacy_attention["instructions"]=="Respond to the blue GO circle. Withhold your response to the gray NO-GO square."
    from backend.app.exercises import expected_tile
    for level in (1,2,3):
        tier=f"tier-{level}"
        for eid in ("EX-01","EX-03","EX-04","EX-05"):
            version=TRAINING_VERSIONS[eid]
            first=training_items(eid,tier,f"stable-{eid}-{tier}",version)
            assert first==training_items(eid,tier,f"stable-{eid}-{tier}",version)
            assert first!=training_items(eid,tier,f"other-{eid}-{tier}",version)
            assert all(row["difficulty"]==tier for row in first) and len({row["item_id"] for row in first})==8
            if eid=="EX-01":
                lengths=[row["stimulus"]["length"] for row in first]
                assert min(lengths)==2*level+2 and max(lengths)==2*level+3
                assert all(len(row["stimulus"]["sequence"])==row["stimulus"]["length"] for row in first)
            elif eid=="EX-03":
                for half in (first[:4],first[4:]):
                    assert sum(row["stimulus"]["signal"]=="go" for row in half)==2
                assert all((row["stimulus"]["color"],row["stimulus"]["symbol"])==("blue","circle")
                           for row in first if row["stimulus"]["signal"]=="go")
                assert {row["stimulus"]["response_window_ms"] for row in first}=={1500-300*(level-1)}
            elif eid=="EX-04":
                for row in first:
                    stim=row["stimulus"]
                    assert len(stim["options"])==(4 if level==3 else 3)
                    assert sum(option[stim["active_rule"]]==stim["target"][stim["active_rule"]] for option in stim["options"])==1
                assert sum(row["stimulus"]["switch"] for row in first[:4])==level
            else:
                boards=[row["stimulus"] for row in first]
                assert {board["width"] for board in boards}=={{1:5,2:7,3:9}[level]}
                assert len({tuple(map(tuple,board["walls"])) for board in boards})==8
                assert all(len(shortest_path(board))>={1:8,2:12,3:16}[level] for board in boards)
                for board in boards:
                    walls={tuple(cell) for cell in board["walls"]}
                    branches=0
                    for y in range(board["height"]):
                        for x in range(board["width"]):
                            if (x,y) in walls:continue
                            branches+=sum((x+dx,y+dy) not in walls and 0<=x+dx<board["width"] and 0<=y+dy<board["height"]
                                          for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)))>=3
                    assert branches>=4
        reasoning=make_training_bank(tier,f"reasoning-{tier}",TRAINING_EXERCISE_VERSION)
        assert reasoning==make_training_bank(tier,f"reasoning-{tier}",TRAINING_EXERCISE_VERSION)
        assert reasoning!=make_training_bank(tier,f"reasoning-other-{tier}",TRAINING_EXERCISE_VERSION)
        for row in reasoning:
            expected=expected_tile(row)
            assert len(set(map(str,row["choices"].values())))==4
            assert sum(tile==expected for tile in row["choices"].values())==1

    # Planning reassessment evidence is a coherent same-session fixed set, never pooled fragments.
    from backend.app.profile_service import build_profile
    fragments=[]
    for item_index in range(2):
        partial_sid=new_session();item=reassess["items"][item_index]
        post_trial(partial_sid,"EX-05",item,"reassessment",REASSESSMENT_VERSION)
        fragments.extend(store.events(session_id=partial_sid))
    partial=build_profile(fragments)["dimensions"]["planning"]
    assert partial["reassessment_evidence_count"]==0 and partial["selection_index_0_100"] is None
    coherent_sid=new_session()
    for item in reassess["items"]:
        post_trial(coherent_sid,"EX-05",item,"reassessment",REASSESSMENT_VERSION)
    coherent=build_profile(store.events(learner_id="demo-user"))["dimensions"]["planning"]
    assert coherent["reassessment_evidence_count"]==3 and len(set(coherent["reassessment_evidence_ids"]))==3
    # Reassessment exact event replay is checked before transactional item uniqueness; changed payload conflicts.
    unique_sid=new_session();item=reassess["items"][0];event_id=str(uuid.uuid4())
    replay_body={"event_id":event_id,"session_id":unique_sid,"learner_id":"demo-user","phase":"reassessment","exercise_id":"EX-05",
        "exercise_version":REASSESSMENT_VERSION,"item_id":item["item_id"],**create_response(item,"EX-05")}
    first=client.post("/api/trials",json=replay_body);again=client.post("/api/trials",json=replay_body)
    assert first.status_code==200 and again.status_code==200 and again.json()["replayed"] is True
    duplicate={**replay_body,"event_id":str(uuid.uuid4())}
    assert client.post("/api/trials",json=duplicate).status_code==409
    assert client.post("/api/trials",json={**replay_body,"restart_count":1}).status_code==409
    assert client.post("/api/trials",json={**replay_body,"event_id":str(uuid.uuid4()),"exercise_id":"EX-02",
        "exercise_version":EXERCISE_VERSION,"item_id":ex02[0]["item_id"]}).status_code==422

    # Error strategies map recorded mistakes to separate stored policy strategies.
    assert strategy_for_error("EX-01","order_mismatch")["id"]=="memory-chunk-sequence"
    assert strategy_for_error("EX-02","count_across_rows")["id"]!=strategy_for_error("EX-02","clockwise_rotation")["id"]
    assert strategy_for_error("EX-03","commission_error")["id"]=="attention-target-reminder"
    assert strategy_for_error("EX-04","error_previous_rule")["id"]=="switch-transition-cue"
    assert strategy_for_error("EX-05","inefficient_moves")["id"]=="planning-subgoals"
    planning_item=baseline_items["EX-05"][0];optimal=shortest_path(planning_item["stimulus"])
    inefficient_actions=[{"action":"move","direction":x} for x in (["down","up"]+optimal)]
    inefficient_eval=replay_planning(planning_item,{"actions":inefficient_actions})
    incomplete_eval=replay_planning(planning_item,{"actions":[]})
    assert inefficient_eval["correct"] is True and inefficient_eval["error_type"]=="inefficient_moves"
    recorded=[{"event_id":"inefficient-proof","payload":{"exercise_id":"EX-05","phase":"baseline","evaluation":inefficient_eval}},
        {"event_id":"incomplete-proof","payload":{"exercise_id":"EX-05","phase":"baseline","evaluation":incomplete_eval}}]
    assert latest_strategy(recorded,"EX-05")["id"]=="planning-legal-moves"
    assert latest_strategy(recorded[:1],"EX-05")["id"]=="planning-subgoals"

    # Save an initial plan; a completed training decision should retain a before/after history event.
    initial_plan=client.post("/api/plans/next",json={"session_id":sid,"budget_minutes":8,"goal_dimension":"planning"}).json()

    # Each task family gets a tier-local, exactly-once four-eligible-trial decision.
    expected={"up":[True]*4,"down":[False]*4,"hold":[True,True,False,False]}
    for eid in ("EX-01","EX-02","EX-03","EX-04","EX-05"):
        # Exercise the canonical tier guard in a valid decision sequence. UP promotes
        # tier 1 to 2, HOLD checks tier 2 in place, then DOWN demotes it to 1.
        # Asking for tier 2 after the demotion would be an invalid fixture request.
        for outcome in ("up", "hold", "down"):
            values=expected[outcome]
            tier="tier-1" if outcome=="up" else "tier-2"
            created=client.post("/api/training/blocks",json={"session_id":sid,"exercise_id":eid,"tier":tier})
            assert created.status_code==201,(eid,created.text)
            block=created.json()["block"];config=created.json()["exercise"]
            version=TRAINING_EXERCISE_VERSION if eid=="EX-02" else TRAINING_VERSIONS[eid]
            assert config["exercise_version"]==version and len(config["items"])>=4
            if eid=="EX-03":
                assert config["instructions"]=="Respond only when the cue is a blue circle. Withhold your response to every other color and shape pairing."
            final=None
            for item,correct in zip(config["items"][:4],values):
                if eid=="EX-03" and outcome=="hold":
                    answer={"response_data":{"responded":True},"response_time_ms":400}
                else:
                    answer=create_response(item,eid,correct,version,block["block_id"])
                final=post_trial(sid,eid,item,"training",version,answer=answer,block_id=block["block_id"])
            decision=final["difficulty_decision"]
            assert decision and decision["action"]==outcome,(eid,outcome,decision)
            assert decision["valid_trial_count"]==4 and decision["trial_count"]==4
            assert decision["rule_version"]=="difficulty-v2"
            if eid=="EX-05":assert "efficiency >=80" in decision["rationale"]
            refreshed=client.get(f"/api/training/blocks/{block['block_id']}").json()
            assert refreshed["difficulty_decision"] and refreshed["block"]["status"]=="completed"
            if outcome=="up":assert decision["new_tier"]=="tier-2"
            if outcome=="down":assert decision["new_tier"]=="tier-1"
            if outcome=="hold":assert decision["new_tier"]=="tier-2"
    # Unassisted event identity stays exact after a later coach hint for that same item.
    replay_block=client.post("/api/training/blocks",json={"session_id":sid,"exercise_id":"EX-03","tier":"tier-1"}).json()
    rb=replay_block["block"];ri=replay_block["exercise"]["items"][0];rid=str(uuid.uuid4())
    replay_payload={"event_id":rid,"session_id":sid,"learner_id":"demo-user","phase":"training","exercise_id":"EX-03",
        "exercise_version":TRAINING_VERSIONS["EX-03"],"item_id":ri["item_id"],"training_block_id":rb["block_id"],
        **create_response(ri,"EX-03",True)}
    saved=client.post("/api/trials",json=replay_payload);assert saved.status_code==200 and saved.json()["scored"]
    coach_event_id=str(uuid.uuid4())
    store.add_event(coach_event_id,sid,"coaching_message_sent",{"event_id":coach_event_id,"learner_id":"demo-user","session_id":sid,
        "event_type":"coaching_message_sent","training_block_id":rb["block_id"],"item_id":ri["item_id"],"hint_requested":True,"recorded_at":"2026-10-18T13:30:00+00:00"})
    replayed=client.post("/api/trials",json=replay_payload)
    assert replayed.status_code==200 and replayed.json()["replayed"] and replayed.json()["scored"]
    changed_attention_response=not replay_payload["response_data"]["responded"]
    assert client.post("/api/trials",json={**replay_payload,"response_data":{"responded":changed_attention_response}}).status_code==409

    # A hinted attention attempt is excluded and retryable; the decision waits for four eligible trials.
    created=client.post("/api/training/blocks",json={"session_id":sid,"exercise_id":"EX-03","tier":"tier-1"}).json()
    block=created["block"];config=created["exercise"];items=config["items"]
    coach_event_id=str(uuid.uuid4())
    store.add_event(coach_event_id,sid,"coaching_message_sent",{"event_id":coach_event_id,"learner_id":"demo-user","session_id":sid,
        "event_type":"coaching_message_sent","training_block_id":block["block_id"],"item_id":items[0]["item_id"],
        "hint_requested":True,"recorded_at":"2026-10-18T13:00:00+00:00"})
    coached=post_trial(sid,"EX-03",items[0],"training",TRAINING_VERSIONS["EX-03"],
        answer=create_response(items[0],"EX-03",False),block_id=block["block_id"])
    assert coached["scored"] is False
    coached_event=next(e for e in store.block_events(block["block_id"]) if e["payload"]["item_id"]==items[0]["item_id"])
    assert coached_event["payload"]["interaction"]["hint_count"]==1
    for item in items[1:4]:
        result=post_trial(sid,"EX-03",item,"training",TRAINING_VERSIONS["EX-03"],
            answer=create_response(item,"EX-03",True),block_id=block["block_id"])
    assert result["difficulty_decision"]["action"]=="hold"
    assert result["difficulty_decision"]["valid_trial_count"]==3
    assert "hinted_trials_excluded" in result["difficulty_decision"]["reason_codes"]
    duplicate=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training",
        "exercise_id":"EX-03","exercise_version":TRAINING_VERSIONS["EX-03"],"training_block_id":block["block_id"],
        "item_id":items[0]["item_id"],"response_data":{"responded":True},"response_time_ms":400})
    assert duplicate.status_code==409
    assert score_reasoning(store.events(learner_id="demo-user"))["index_0_100"]==before["reasoning"]
    for dim,data in score_battery(store.events(learner_id="demo-user")).items():
        assert data["index_0_100"]==before[dim]

    # Recommendation fields and policy evidence persist; plans retain unchanged and revised snapshots.
    recommendation=client.post("/api/recommendations/next",json={"session_id":sid,"budget_minutes":8,"goal_dimension":"planning"})
    assert recommendation.status_code==200,recommendation.text
    rec=recommendation.json()
    assert rec["features"] and rec["policy_version"]=="personalization-v1" and "rationale" in rec
    history=client.get("/api/profile/demo-user/evidence").json()
    assert any(e["type"]=="exercise_recommended" and e["payload"]["features"] for e in history["events"])
    first=client.post("/api/plans/next",json={"session_id":sid,"budget_minutes":8,"goal_dimension":"planning"})
    second=client.post("/api/plans/next",json={"session_id":sid,"budget_minutes":8,"goal_dimension":"planning"})
    revised=client.post("/api/plans/next",json={"session_id":sid,"budget_minutes":8,"goal_dimension":"working_memory"})
    assert first.status_code==200 and len(first.json()["steps"]) in (2,3,4)
    latest_tier={}
    for event in store.events(learner_id="demo-user"):
        if event["type"]=="difficulty_changed":latest_tier[event["payload"]["dimension"]]=event["payload"]["new_tier"]
    assert all(step["difficulty_tier"]==latest_tier.get(step["dimension_id"],"tier-1")
               for step in first.json()["steps"] if step["action"]=="targeted_training")
    assert initial_plan["decision_fingerprint"]!=first.json()["decision_fingerprint"]
    assert second.json()["changed"] is False and "retained_current_plan" in second.json()["reason_codes"]
    assert revised.json()["changed"] is True
    plans=client.get("/api/plans/demo-user").json()
    assert len(plans["history"])>=3 and plans["latest"]["plan_id"]==revised.json()["plan_id"]
    assert any(e["type"] in {"training_plan_revised","training_plan_unchanged"} and e["payload"].get("before_plan_id")==initial_plan["plan_id"]
        for e in history["events"])
    assert len(plans["latest"]["steps"]) in (2,3,4)

    # Same frozen baseline item is valid in a separate session, proving no session leakage.
    sid2=new_session();item=ex02[0]
    isolated=post_trial(sid2,"EX-02",item,"baseline",EXERCISE_VERSION)
    assert isolated["scored"] and isolated["phase"]=="baseline"

    # Omitted tier resolves from canonical family history, and the creation event
    # must record that resolved value rather than the request's null field.
    tier_event_id=str(uuid.uuid4())
    store.add_event(tier_event_id,sid,"difficulty_changed",{"event_id":tier_event_id,"event_type":"difficulty_changed",
        "session_id":sid,"learner_id":"demo-user","dimension":"working_memory","new_tier":"tier-2",
        "recorded_at":"2026-10-21T03:00:00+00:00"})
    canonical=current_tier(store.events(learner_id="demo-user"),"working_memory")
    assert canonical=="tier-2"
    # The saved plan still carries the previous tier, so the launch guard refuses a stale
    # plan (R2 tests that guard directly). Reconcile the plan the way a recorded decision
    # does, then the omitted-tier launch still resolves from canonical family history.
    stale=client.post("/api/training/blocks",json={"session_id":sid,"exercise_id":"EX-01"})
    assert stale.status_code==409,stale.text
    assert "stale" in stale.json()["detail"].casefold(),stale.text
    reconciled=client.post("/api/plans/next",json={"session_id":sid,"budget_minutes":20})
    assert reconciled.status_code==200,reconciled.text
    omitted=client.post("/api/training/blocks",json={"session_id":sid,"exercise_id":"EX-01"})
    assert omitted.status_code==201,omitted.text
    resolved_block=omitted.json()["block"]
    started_event=next(event for event in store.events(session_id=sid)
        if event["type"]=="training_block_started" and event["payload"].get("training_block_id")==resolved_block["block_id"])
    assert resolved_block["tier"]==canonical
    assert started_event["payload"]["item_difficulty"]==canonical

print("PASS: coherent-session planning reassessment gate and uniqueness replay; real tier-specific memory/switching banks; evidence-gated divergent selection; five-family up/down/hold windows; coach-invariant exact replay; hint/interruption protections; strategy mapping; baseline invariance; persisted recommendations and tier/evidence-sensitive plan history; omitted-tier canonical event identity")
