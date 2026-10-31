"""Isolated API smoke for the remembered-order and bridge-council activities."""
from __future__ import annotations
import os, sys, tempfile, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));os.environ["NEO4J_ENABLED"]="false"

def main():
 with tempfile.TemporaryDirectory(prefix="luna-hybrid-03-06-") as tmp:
  os.environ["AI4BRAIN_DB"]=str(Path(tmp)/"qa.sqlite3")
  from fastapi.testclient import TestClient
  from backend.app.main import app,store
  from backend.app.hybrid_activities_modules import bridge_council,shifting_market
  with TestClient(app) as c:
   s=c.post('/api/sessions',json={"learner_id":"demo-user","consent_accepted":True});assert s.status_code==201,s.text
   sid=s.json()['id']; catalog=c.get('/api/hybrid/catalog').json(); activities={a['activity_id']:a for a in catalog['activities']}
   assert {'HY-03','HY-06'}<=set(activities)
   market=c.post('/api/hybrid/attempts',json={"event_id":str(uuid.uuid4()),"session_id":sid,"activity_id":"HY-03","activity_version":activities['HY-03']['activity_version'],"seed":"market","difficulty_tier":"tier-2"}).json()
   aid=market['attempt_id']; cfg=market['config']; assert cfg['activity_version']==shifting_market.VERSION and len(cfg['cargo'])==5 and 'shipment_order' not in cfg
   oracle=shifting_market.generate('market','training','tier-2')['_oracle_order'];assert 'study_sequence' in cfg
   assert c.post(f'/api/hybrid/attempts/{aid}/assistance',json={"attempt_id":aid,"event_id":"early-help","exposure_kind":"strategy_prompt","checkpoint":"boundary"}).status_code==409
   # The action route rejects repeating a valid cargo ID before it can distort counts.
   duplicate=c.post('/api/hybrid/attempts',json={"event_id":str(uuid.uuid4()),"session_id":sid,"activity_id":"HY-03","activity_version":activities['HY-03']['activity_version'],"seed":"duplicate-gate","difficulty_tier":"tier-2"}).json()
   dup_id=duplicate['attempt_id'];dup_cargo=duplicate['config']['cargo'][0]['cargo_id']
   accepted=c.post(f'/api/hybrid/attempts/{dup_id}/actions',json={"attempt_id":dup_id,"event_id":str(uuid.uuid4()),"sequence":1,"action_type":"select","payload":{"cargo_id":dup_cargo,"bin_id":"amber-tray"}});assert accepted.status_code==201,accepted.text
   rejected=c.post(f'/api/hybrid/attempts/{dup_id}/actions',json={"attempt_id":dup_id,"event_id":str(uuid.uuid4()),"sequence":2,"action_type":"select","payload":{"cargo_id":dup_cargo,"bin_id":"amber-tray"}});assert rejected.status_code==409,rejected.text
   for i,cargo in enumerate(oracle[:cfg['switch']['after_step']],1):
    parcel=next(p for p in cfg['cargo'] if p['cargo_id']==cargo);bin_id=cfg['rules']['color_bins'][parcel['color']]
    r=c.post(f'/api/hybrid/attempts/{aid}/actions',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"sequence":i,"action_type":"select","payload":{"cargo_id":cargo,"bin_id":bin_id}});assert r.status_code==201,r.text
   boundary={"attempt_id":aid,"event_id":"market-help","exposure_kind":"strategy_prompt","checkpoint":"boundary"}
   assert c.post(f'/api/hybrid/attempts/{aid}/assistance',json=boundary).status_code==201
   for i,cargo in enumerate(oracle[cfg['switch']['after_step']:],cfg['switch']['after_step']+1):
    parcel=next(p for p in cfg['cargo'] if p['cargo_id']==cargo);bin_id=cfg['rules']['shape_bins'][parcel['shape']]
    r=c.post(f'/api/hybrid/attempts/{aid}/actions',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"sequence":i,"action_type":"select","payload":{"cargo_id":cargo,"bin_id":bin_id}});assert r.status_code==201,r.text
   result=c.post(f'/api/hybrid/attempts/{aid}/complete',json={"attempt_id":aid,"event_id":str(uuid.uuid4())});assert result.status_code==200,result.text
   assert result.json()['outcomes']['routing_matches']==len(cfg['cargo']) and result.json()['excluded_from_unassisted']
   seen=set()
   for n in range(100):
    seed=f"council-{n}";kind=bridge_council.generate(seed,'training','tier-1')['advice']['kind']
    if kind in seen: continue
    seen.add(kind)
    started=c.post('/api/hybrid/attempts',json={"event_id":str(uuid.uuid4()),"session_id":sid,"activity_id":"HY-06","activity_version":activities['HY-06']['activity_version'],"seed":seed,"difficulty_tier":"tier-1"})
    assert started.status_code==201,started.text
    a=started.json();aid=a['attempt_id'];g=a['config'];seq=1
    route=['harbor','key-island','old-bridge','lighthouse']
    def act(kind,payload):
     nonlocal seq
     response=c.post(f'/api/hybrid/attempts/{aid}/actions',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"sequence":seq,"action_type":kind,"payload":payload});seq+=1;assert response.status_code==201,response.text
    for node in route[1:]: act('select',{"stage":"proposal","node_id":node})
    act('commit',{"stage":"proposal"})
    assert c.post(f'/api/hybrid/attempts/{aid}/assistance',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"exposure_kind":"oracle_route_suggestion","checkpoint":"advice_checkpoint"}).status_code==201
    decision={'correct':'accept','incorrect':'reject','uncertain':'hold'}[g['advice']['kind']]
    constraint='constraint-key-before-gate' if decision=='reject' else ''
    forged=c.post(f'/api/hybrid/attempts/{aid}/actions',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"sequence":seq,"action_type":"advise","payload":{"decision":decision,"inspected_refs":["invented-evidence"]}});assert forged.status_code==422,forged.text
    act('advise',{"decision":decision,"constraint_id":constraint,"inspected_refs":g['advice']['evidence_refs']})
    for node in route[1:]: act('select',{"stage":"resolution","node_id":node})
    act('commit',{"stage":"resolution"})
    assert c.post(f'/api/hybrid/attempts/{aid}/assistance',json={"attempt_id":aid,"event_id":str(uuid.uuid4()),"exposure_kind":"strategy_prompt","checkpoint":"post_commit"}).status_code==201
    out=c.post(f'/api/hybrid/attempts/{aid}/complete',json={"attempt_id":aid,"event_id":str(uuid.uuid4())});assert out.status_code==200,out.text
    assert out.json()['outcomes']['decision_justified_by_recorded_evidence'] and out.json()['excluded_from_unassisted']
    stored=c.get(f'/api/hybrid/attempts/{aid}').json()
    evidence_removed=[{"action_type":e['payload'].get('action_type'),"payload":{**e['payload'].get('action',{}),**({"inspected_refs":[]} if e['payload'].get('action_type')=='advise' else {})}} for e in stored['events'] if e['type']=='hybrid_action_recorded']
    assert not bridge_council.evaluate(g,evidence_removed)['decision_justified_by_recorded_evidence']
   assert seen=={'correct','incorrect','uncertain'}
   print('luna_hy03_hy06_smoke: PASS; switch checkpoint, correct routing, all advice scenarios, evidence decisions, assistance gates, completed outcomes.')
if __name__=='__main__':main()
