"""Isolated streaming-response and pacing contract checks for HY-02/HY-04."""
from __future__ import annotations
import os,sys,tempfile,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ['NEO4J_ENABLED']='false'
def main():
 with tempfile.TemporaryDirectory(prefix='luna-hy02-hy04-') as tmp:
  os.environ['AI4BRAIN_DB']=str(Path(tmp)/'qa.sqlite3')
  from fastapi.testclient import TestClient
  from backend.app.main import app
  from backend.app.hybrid_activities_modules import tidekeeper,harbor_dispatch
  with TestClient(app) as c:
   sid=c.post('/api/sessions',json={'learner_id':'demo-user','consent_accepted':True}).json()['id']
   cat={x['activity_id']:x for x in c.get('/api/hybrid/catalog').json()['activities']}
   def start(aid,seed,tier='tier-1'):
    r=c.post('/api/hybrid/attempts',json={'event_id':str(uuid.uuid4()),'session_id':sid,'activity_id':aid,'activity_version':cat[aid]['activity_version'],'mode':'training','difficulty_tier':tier,'seed':seed});assert r.status_code==201,r.text;return r.json()
   # HY-02 server-streams one cue at a time; the config never includes future oracle stream.
   a=start('HY-02','tide-smoke','tier-1');aid=a['attempt_id'];assert '_oracle_stream' not in a['config']
   private=tidekeeper.generate('tide-smoke','training','tier-1'); cue=c.get(f'/api/hybrid/attempts/{aid}/stimulus').json();assert cue['index']==0 and 'position_match_expected' not in cue
   malformed=c.post(f'/api/hybrid/attempts/{aid}/actions',json={'attempt_id':aid,'event_id':str(uuid.uuid4()),'sequence':1,'action_type':'respond','cue_event_id':cue['cue_id'],'payload':{'trial_index':'not-an-index','position_match':False,'symbol_match':False}});assert malformed.status_code==422,malformed.text
   first=private['_oracle_stream'][0];rbody={'attempt_id':aid,'event_id':'response-0','sequence':1,'action_type':'respond','cue_event_id':cue['cue_id'],'elapsed_ms':2100,'payload':{'trial_index':0,'position_match':False,'symbol_match':False}}
   r=c.post(f'/api/hybrid/attempts/{aid}/actions',json=rbody);assert r.status_code==201,r.text
   replay=c.post(f'/api/hybrid/attempts/{aid}/actions',json=rbody);assert replay.status_code==201 and replay.json()['replayed']
   assert c.post(f'/api/hybrid/attempts/{aid}/actions',json={**rbody,'elapsed_ms':1000}).status_code==409
   for index in range(1,len(private['_oracle_stream'])):
    cue=c.get(f'/api/hybrid/attempts/{aid}/stimulus').json();assert cue['index']==index
    row=private['_oracle_stream'][index];prev=private['_oracle_stream'][index-private['n_back']]
    payload={'trial_index':index,'position_match':row['position']==prev['position'],'symbol_match':row['symbol_index']==prev['symbol_index']}
    r=c.post(f'/api/hybrid/attempts/{aid}/actions',json={'attempt_id':aid,'event_id':str(uuid.uuid4()),'sequence':index+1,'action_type':'respond','cue_event_id':cue['cue_id'],'elapsed_ms':cue['response_window_ms'],'payload':payload});assert r.status_code==201,r.text
   completion={'attempt_id':aid,'event_id':str(uuid.uuid4())}
   result=c.post(f'/api/hybrid/attempts/{aid}/complete',json=completion);assert result.status_code==200,result.text
   assert c.post(f'/api/hybrid/attempts/{aid}/complete',json=completion).status_code==200
   assert c.post(f'/api/hybrid/attempts/{aid}/complete',json={**completion,'interrupted':True}).status_code==409
   assert c.post(f'/api/hybrid/attempts/{aid}/complete',json={**completion,'event_id':str(uuid.uuid4())}).status_code==409
   assert result.json()['outcomes']['position_correct']==result.json()['outcomes']['position_total']
   assert result.json()['outcomes']['symbol_correct']==result.json()['outcomes']['symbol_total']
   # HY-04 configuration exposes only the manifest. Arrivals are fetched per response.
   b=start('HY-04','dispatch-smoke','tier-1');bid=b['attempt_id'];assert '_oracle_arrivals' not in b['config']
   private=harbor_dispatch.generate('dispatch-smoke','training','tier-1');width=b['config']['arrivals_per_wave']
   cue=c.get(f'/api/hybrid/attempts/{bid}/stimulus').json()
   malformed=c.post(f'/api/hybrid/attempts/{bid}/actions',json={'attempt_id':bid,'event_id':str(uuid.uuid4()),'sequence':1,'action_type':'respond','cue_event_id':cue['cue_id'],'payload':{'arrival_index':0,'destination_id':'forged-port','ignore':False}});assert malformed.status_code==422,malformed.text
   assert c.post(f'/api/hybrid/attempts/{bid}/assistance',json={'attempt_id':bid,'event_id':'early-wave-help','exposure_kind':'strategy_prompt','checkpoint':'between_waves'}).status_code==409
   for index,truth in enumerate(private['_oracle_arrivals']):
    cue=c.get(f'/api/hybrid/attempts/{bid}/stimulus').json();assert cue['index']==index and cue['cue_id']==truth['arrival_id']
    destination=(private['manifest'].get(truth['cargo_id']) if truth['wave']==1 else truth['new_route']) if not truth['distractor'] else None
    payload={'arrival_index':index,'destination_id':destination,'ignore':destination is None}
    body={'attempt_id':bid,'event_id':f'dispatch-{index}','sequence':index+1,'action_type':'respond','cue_event_id':cue['cue_id'],'elapsed_ms':400,'payload':payload}
    r=c.post(f'/api/hybrid/attempts/{bid}/actions',json=body);assert r.status_code==201,r.text
    if index==0: assert c.post(f'/api/hybrid/attempts/{bid}/actions',json=body).status_code==201
    if index+1==width:
     help_body={'attempt_id':bid,'event_id':'wave-help','exposure_kind':'strategy_prompt','checkpoint':'between_waves'}
     assert c.post(f'/api/hybrid/attempts/{bid}/assistance',json=help_body).status_code==201
   result=c.post(f'/api/hybrid/attempts/{bid}/complete',json={'attempt_id':bid,'event_id':str(uuid.uuid4())});assert result.status_code==200,result.text
   assert result.json()['outcomes']['dispatch_total']==len(private['_oracle_arrivals']) and result.json()['excluded_from_unassisted']
   print('luna_hy02_hy04_smoke: PASS; hidden future stream, current-cue order, exact/conflicting response retries, response timing, complete coverage gate, between-wave assistance, separate outcomes.')
if __name__=='__main__':main()
