"""Graph adapter smoke; disabled mode must never contact/start Neo4j."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.graph_service import GraphMirror,build_graph
profile={'learner_id':'demo-user','dimensions':{'reasoning':{'evidence_count':6,'index_0_100':50,'completed':True,'uncertainty_status':'PRELIMINARY_HIGH_UNCERTAINTY','evidence_ids':['a','b','c','d','e','f']},'planning':{'evidence_count':0,'index_0_100':None}},'snapshots':[{'id':'snapshot-1','dimension':'reasoning','evidence_ids':['a','b','c','d','e','f'],'evidence_count':6,'index_0_100':50}]}
events=[{'payload':{'item_id':'reasoning-pattern-001','exercise_id':'EX-02','exercise_version':'1.0.0'}}]
graph=build_graph(profile,events=events)
nodes={n['id']:n for n in graph['nodes']}
assert 'estimate:demo-user:planning' not in nodes
assert nodes['estimate:demo-user:reasoning']['properties']['evidence_ids']==['a','b','c','d','e','f']
assert nodes['snapshot:snapshot-1']['properties']['index_0_100']==50
assert any(e['source']=='item:reasoning-pattern-001' and e['target']=='exercise:EX-02' and e['type']=='INSTANCE_OF' for e in graph['edges'])
assert any(e['source']=='learner:demo-user' and e['type']=='HAS_ESTIMATE' for e in graph['edges'])
assert all(e['source'] in nodes and e['target'] in nodes for e in graph['edges'])
with patch('neo4j.GraphDatabase.driver',side_effect=AssertionError('disabled graph attempted network')):
    status=GraphMirror(enabled=False).sync(graph)
assert status['status']=='disabled' and not status['connected']
with patch.dict('os.environ',{'NEO4J_PASSWORD':'mock-not-a-real-password'}):
    with patch('neo4j.GraphDatabase.driver',side_effect=ConnectionError('simulated graph outage')):
        unavailable=GraphMirror(enabled=True).sync(graph)
assert unavailable['status']=='unavailable' and not unavailable['connected']
assert graph['source']=='sqlite-derived' and nodes['estimate:demo-user:reasoning']['properties']['index_0_100']==50
blank=build_graph({'learner_id':'demo-user','dimensions':{}})
assert not any(n['type'] in {'DimensionEstimate','ProfileSnapshot','EvidenceSummary'} for n in blank['nodes'])
class Result:
    def consume(self): return None
class Tx:
    def __init__(self): self.calls=[]
    def run(self,query,**kwargs): self.calls.append((query,kwargs)); return Result()
tx=Tx(); GraphMirror(enabled=False)._write_graph(tx,graph)
assert any(':CognitiveDimension' in query for query,_ in tx.calls)
assert any(':SUPPORTED_BY' in query for query,_ in tx.calls)
assert any('PREFERS_DASHBOARD' in query and 'DELETE r' in query for query,_ in tx.calls)
print('PASS: SQLite-derived two-brain schema/evidence/empty profile/typed mirror queries; disabled mode performs no network; simulated outage preserves derived evidence. Live Neo4j intentionally not tested.')
