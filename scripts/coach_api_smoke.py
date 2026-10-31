"""Independent integrated API coach checks; disposable SQLite and no provider/graph calls."""
from __future__ import annotations
import os,sys,tempfile,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='ai4brain-coach-api-') as folder:
    os.environ['AI4BRAIN_DB']=str(Path(folder)/'coach.sqlite3');os.environ['NEO4J_ENABLED']='false'
    os.environ['LLM_API_KEY']='';os.environ['LLM_MODEL']=''
    # Pin provider credentials empty so this check is deterministic even when a local
    # .env configures a hosted provider; the fallback path is what is under test here.
    os.environ['GROQ_API_KEY']='';os.environ['GEMINI_API_KEY']=''
    from fastapi.testclient import TestClient
    from backend.app.main import app,store
    from backend.app.exercises import evaluate
    with TestClient(app) as client:
        sid=client.post('/api/sessions',json={'consent_accepted':True}).json()['id']
        def ask(**more):return client.post('/api/coach',json={'session_id':sid,'message':'Explain the saved evidence and uncertainty.',**more})
        incomplete=ask();assert incomplete.status_code==200,incomplete.text
        assert incomplete.json()['source']=='local_fallback' and incomplete.json()['opportunities']==[]
        assert 'unassessed' in incomplete.json()['response']['observation']
        assert ask(phase='baseline').status_code==409 and ask(phase='reassessment').status_code==409
        assert ask(allow_remote=True).json()['provider_status']=='not_configured'
        paths=[['right','right','down','down'],['up','right','right','right','down'],['down','down','down','right','right','right']]
        def body(conf,item,data=None,**more):return {'event_id':str(uuid.uuid4()),'session_id':sid,'exercise_id':conf['exercise_id'],'exercise_version':conf['exercise_version'],'phase':conf['phase'],'item_id':item['item_id'],**({'response_data':data} if data is not None else {}),**more}
        for ex in ['EX-01','EX-02','EX-03','EX-04','EX-05']:
            conf=client.get('/api/exercises/'+ex,params={'session_id':sid}).json()
            for i,item in enumerate(conf['items']):
                data=None;extra={}
                if ex=='EX-02':extra={'choice':next(c['choice_id'] for c in item['choices'] if evaluate(item['item_id'],c['choice_id'])[0])}
                elif ex=='EX-01':data={'selected_sequence':item['stimulus']['sequence']}
                elif ex=='EX-03':data={'responded':item['stimulus']['signal']=='go'};extra={'response_time_ms':300} if data['responded'] else {}
                elif ex=='EX-04':s=item['stimulus'];data={'choice':next(o['id'] for o in s['options'] if o[s['active_rule']]==s['target'][s['active_rule']])}
                else:data={'actions':[{'action':'move','direction':d} for d in paths[i]]}
                response=client.post('/api/trials',json=body(conf,item,data,**extra));assert response.status_code==200,response.text
        before=client.get('/api/profile/demo-user').json()
        rec=client.post('/api/recommendations/next',json={'session_id':sid}).json()
        assert client.get('/api/recommendations/current').json()['recommendation']['exercise_id']==rec['exercise_id']
        grounded=ask();assert grounded.status_code==200,grounded.text
        output=grounded.json();assert output['response']['recommended_exercise_id']==rec['exercise_id']
        assert len(output['opportunities'])==5,output
        assert all(x in {e['event_id'] for e in store.events(learner_id='demo-user')} for x in output['response']['evidence_ids'])
        assert client.get('/api/profile/demo-user').json()['dimensions']==before['dimensions']
        assert client.get('/api/profile/demo-user').json()['snapshots']==before['snapshots']
        created=client.post('/api/training/blocks',json={'session_id':sid,'exercise_id':'EX-02','tier':'tier-1'}).json()
        conf=created['exercise'];block=created['block']['block_id'];item=conf['items'][0]
        help_response=ask(phase='training',training_block_id=block,item_id=item['item_id'])
        assert help_response.status_code==200 and help_response.json()['assisted_training'],help_response.text
        for i,item in enumerate(conf['items'][:4]):
            choice=next(c['choice_id'] for c in item['choices'] if evaluate(item['item_id'],c['choice_id'])[0])
            trial=body(conf,item,choice=choice,training_block_id=block)
            saved=client.post('/api/trials',json=trial);assert saved.status_code==200,saved.text
            if i==0:assert saved.json()['scored'] is False
        decision=saved.json()['difficulty_decision'];assert decision['action']=='hold' and decision['valid_trial_count']==3,decision
        assert client.post('/api/trials',json=trial).json()['replayed']
        assert client.get('/api/profile/demo-user').json()['dimensions']==before['dimensions']
        notice=client.get('/api/data/demo-user/notice');assert notice.status_code==200 and 'no automatic' in notice.json()['retention']
        export=client.get('/api/data/demo-user/export');assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
        assert client.post('/api/data/demo-user/delete',json={'confirmation':'no'}).status_code==422
print('PASS integrated coach: no-key fallback, scored-phase quiet, canonical facts/5 genuine invitations, immutable baseline, server-recorded assistance hold, replay, local notice/export; no live provider calls')
