"""Focused full-battery acceptance fixtures, using disposable SQLite and no graph network."""
from __future__ import annotations
import os,sys,tempfile,uuid
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='ai4brain-battery-') as folder:
    os.environ['AI4BRAIN_DB']=str(Path(folder)/'battery.sqlite3');os.environ['NEO4J_ENABLED']='false'
    from fastapi.testclient import TestClient
    from backend.app.main import app,store
    from backend.app.battery_exercises import exercise_items,shortest_path,PLANNING_BOARDS,evaluate_attention,evaluate_memory
    with TestClient(app) as client:
        def session():return client.post('/api/sessions',json={'consent_accepted':True}).json()['id']
        sid=session()
        def config(exercise,phase='baseline',session_id=sid):
            response=client.get(f'/api/exercises/{exercise}',params={'phase':phase,'session_id':session_id})
            assert response.status_code==200,response.text
            return response.json()
        def submit(conf,item,data=None,session_id=sid,**extra):
            body={'session_id':session_id,'event_id':str(uuid.uuid4()),'exercise_id':conf['exercise_id'],'exercise_version':conf['exercise_version'],'phase':conf['phase'],'item_id':item['item_id'],'response_data':data,**extra}
            response=client.post('/api/trials',json=body)
            assert response.status_code==200,response.text
            return body,response.json()
        memory=config('EX-01');assert memory['exercise_version']=='memory-v2'
        lengths=[i['stimulus']['length'] for i in memory['items']]
        assert sorted(lengths)==[3,3,4,4,5,5] and sorted(lengths[:3])==[3,4,5]
        assert all(i['stimulus']['rows']==3 and i['stimulus']['columns']==3 for i in memory['items'])
        assert all(all(a!=b for a,b in zip(i['stimulus']['sequence'],i['stimulus']['sequence'][1:])) for i in memory['items'])
        first=memory['items'][0]
        submit(memory,first,visibility_interrupted=True)
        partial=client.get('/api/profile/demo-user').json()['dimensions']['working_memory']
        assert partial['evidence_count']==0 and partial['index_0_100'] is None
        for item in memory['items']:
            seq=list(item['stimulus']['sequence']);seq[0]=(seq[0]+1)%9
            body,result=submit(memory,item,{'selected_sequence':seq},response_time_ms=1100)
            assert not result['correct']
        assert client.post('/api/trials',json=body).json()['replayed']
        mem=client.get('/api/profile/demo-user').json()['dimensions']['working_memory']
        assert mem['correct_positions']==18 and mem['index_0_100']==75 and mem['longest_fully_correct_span']==0,mem
        assert mem['interrupted_count']==1
        assert client.post('/api/trials',json={**body,'event_id':str(uuid.uuid4())}).status_code==409
        assert client.post('/api/trials',json={**body,'event_id':str(uuid.uuid4()),'response_data':{'selected_sequence':[],'correct':True}}).status_code==422
        assert client.post('/api/trials',json={**body,'event_id':str(uuid.uuid4()),'exercise_id':'EX-05'}).status_code==422
        # This hand fixture is a partially right five-position sequence, never a full span.
        five=next(i for i in memory['items'] if i['stimulus']['length']==5)
        answer=five['stimulus']['sequence'][:4]+[(five['stimulus']['sequence'][4]+1)%9]
        assert evaluate_memory(five,{'selected_sequence':answer})['fully_correct_span']==0
        attention=config('EX-03');signals=[i['stimulus']['signal'] for i in attention['items']]
        assert len(signals)==40 and signals.count('go')==30 and signals.count('no_go')==10
        assert all(signals[i:i+3]!=['no_go']*3 for i in range(38))
        assert len(config('EX-03','practice')['items'])==6
        assert attention==config('EX-03')
        for index,item in enumerate(attention['items']):
            submit(attention,item,{'responded':True},response_time_ms=300,**({'stimulus_onset_ms':2000} if index==0 else {}))
        timed_event=next(e for e in store.events(session_id=sid) if e['payload'].get('item_id')==attention['items'][0]['item_id'])
        assert timed_event['payload']['timing']['stimulus_onset_ms']==2000
        assert timed_event['payload']['timing']['response_time_ms']==300 and timed_event['payload']['timing']['response_ms']==2300
        att=client.get('/api/profile/demo-user').json()['dimensions']['attention_inhibition']
        assert att['index_0_100']==50 and att['go_hits']==30 and att['no_go_commissions']==10 and att['median_response_time_ms']==300,att
        go=next(i for i in attention['items'] if i['stimulus']['signal']=='go')
        assert evaluate_attention(go,{'responded':True,'response_time_ms':1600})['result']=='omission'
        assert evaluate_attention(go,{'responded':True,'response_time_ms':40})['early']
        second=session();attention2=config('EX-03',session_id=second)
        no_response_body,no_response_result=submit(attention2,attention2['items'][0],{'responded':False},session_id=second)
        no_response_event=next(e for e in store.events(session_id=second) if e['event_id']==no_response_body['event_id'])
        assert no_response_event['payload']['timing']['response_time_ms'] is None and no_response_event['payload']['timing']['response_ms'] is None
        partial=client.get('/api/profile/demo-user').json()['dimensions']['attention_inhibition']
        assert partial['evidence_count']==1 and partial['index_0_100'] is None
        for item in attention2['items'][1:]:submit(attention2,item,{'responded':False},session_id=second)
        att=client.get('/api/profile/demo-user').json()['dimensions']['attention_inhibition']
        assert att['index_0_100']==50 and att['no_go_correct_rejections']==10 and att['go_hits']==0
        switching=config('EX-04');assert len(switching['items'])==24
        assert sum(i['stimulus']['switch'] for i in switching['items'])==8
        assert {i['stimulus']['active_rule'] for i in config('EX-04','practice')['items']}=={'color','shape'}
        for item in switching['items']:
            stimulus=item['stimulus'];rule=stimulus['active_rule'];matches=[o for o in stimulus['options'] if o[rule]==stimulus['target'][rule]]
            assert len(matches)==1
            assert all((o['color']==stimulus['target']['color'])!=(o['shape']==stimulus['target']['shape']) for o in stimulus['options'])
            choice=next(o['id'] for o in stimulus['options'] if (o['id']==matches[0]['id'])!=stimulus['switch'])
            submit(switching,item,{'choice':choice},response_time_ms=500)
        switch=client.get('/api/profile/demo-user').json()['dimensions']['flexibility']
        assert switch['index_0_100']==50 and switch['switch_accuracy']==0 and switch['repeat_accuracy']==100 and switch['error_previous_rule']==8,switch
        planning=config('EX-05');assert len(planning['items'])==3
        assert all('optimal_moves' not in i['stimulus'] for i in planning['items'])
        paths=[['right','right','down','down'],['up','right','right','right','down'],['down','down','down','right','right','right']]
        assert [len(shortest_path(b)) for b in PLANNING_BOARDS]==[4,5,6]
        for index,item in enumerate(planning['items']):
            route=paths[index] if index==0 else (['up','down']+paths[index] if index==1 else [])
            submit(planning,item,{'actions':[{'action':'move','direction':direction} for direction in route]})
        plan=client.get('/api/profile/demo-user').json()['dimensions']['planning']
        assert plan['puzzle_efficiencies']==[100,71.43,0] and plan['index_0_100']==57.14 and plan['completed_puzzles']==2,plan
        observations=plan['puzzle_observations']
        assert [row['item_id'] for row in observations]==[item['item_id'] for item in planning['items']]
        assert all(row['event_id'] in plan['evidence_ids'] for row in observations)
        assert [row['completed'] for row in observations]==[True,True,False]
        assert [row['optimal_moves'] for row in observations]==[4,5,6]
        assert [row['excess_moves'] for row in observations]==[0,2,None] and plan['excess_moves']==2
        assert observations[0]['legal_moves']==4 and observations[1]['legal_moves']==7 and observations[2]['efficiency_0_100']==0
        before_get=len(store.events(learner_id='demo-user'))
        client.get('/api/profile/demo-user')
        assert len(store.events(learner_id='demo-user'))==before_get
        before=client.get('/api/profile/demo-user').json()
        pref=client.post('/api/preferences',json={'session_id':sid,'dashboard_mode':'rpg','goal_dimension':'reasoning'})
        assert pref.status_code==200,pref.text
        after=client.get('/api/profile/demo-user').json()
        assert before['dimensions']==after['dimensions'] and before['snapshots']==after['snapshots']
        assert len(after['snapshots'])>5
        graph=client.get('/api/graph/demo-user?dimension=working_memory').json()
        assert graph['mirror_status']['status']=='disabled'
        assert any(n['type']=='DimensionEstimate' and n['properties']['index_0_100']==75 for n in graph['nodes'])
        assert all(e['source'] in {n['id'] for n in graph['nodes']} and e['target'] in {n['id'] for n in graph['nodes']} for e in graph['edges'])
        # A private canonical rule label is saved, but hidden from event readers until the six-item baseline closes.
        reasoning_sid=session();reasoning=config('EX-02',session_id=reasoning_sid);first_reasoning=reasoning['items'][0]
        reasoning_body,reasoning_result=submit(reasoning,first_reasoning,session_id=reasoning_sid,choice='A')
        private_reasoning=next(e for e in store.events(session_id=reasoning_sid) if e['payload']['event_id']==reasoning_body['event_id'])
        assert private_reasoning['payload']['trial_index']==1 and private_reasoning['payload']['stimulus_config']['rule_type']
        visible=next(e for e in client.get(f"/api/sessions/{reasoning_sid}/events").json()['events'] if e['event_id']==reasoning_body['event_id'])
        assert visible['payload']['trial_index']==1 and 'rule_type' not in visible['payload']['stimulus_config']
        exported=client.get('/api/data/demo-user/export').json()
        exported_event=next(e for e in exported['events'] if e['event_id']==reasoning_body['event_id'])
        assert exported_event['payload']['stimulus_config']['rule_type']==private_reasoning['payload']['stimulus_config']['rule_type']
        forged=client.post('/api/trials',json={**reasoning_body,'event_id':str(uuid.uuid4()),'trial_index':99,'rule_type':'forged'})
        assert forged.status_code==422
        for item in reasoning['items'][1:]:
            submit(reasoning,item,session_id=reasoning_sid,choice='A')
        visible=next(e for e in client.get(f"/api/sessions/{reasoning_sid}/events").json()['events'] if e['event_id']==reasoning_body['event_id'])
        assert visible['payload']['stimulus_config']['rule_type']==private_reasoning['payload']['stimulus_config']['rule_type']
        assert visible['payload']['trial_index']==1
        # With no completed planning items, per-item evidence exists but completed-only excess remains unavailable.
        partial_sid=session();partial_planning=config('EX-05',session_id=partial_sid);partial_item=partial_planning['items'][0]
        submit(partial_planning,partial_item,{'actions':[]},session_id=partial_sid)
        partial_plan=client.get('/api/profile/demo-user').json()['dimensions']['planning']
        assert partial_plan['excess_moves'] is None and len(partial_plan['puzzle_observations'])==1
        assert partial_plan['puzzle_observations'][0]['completed'] is False and partial_plan['puzzle_observations'][0]['excess_moves'] is None
print('PASS battery: spatial3x3 lengths/18of24=75%; interruption/replay; attention always/neverpress=50%; timing;8switch/16repeat=50%; BFS4/5/6 and planning57.14%; coherent sessions; retained history; dashboard invariance; graph evidence')
