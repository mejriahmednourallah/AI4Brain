"""Connect to the requested local Neo4j and mirror real recorded SQLite evidence."""
from __future__ import annotations
import json
import os
import sqlite3
import sys
from pathlib import Path
from contextlib import closing
from dotenv import load_dotenv
from neo4j import GraphDatabase
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env',override=False)
from backend.app.graph_service import GraphMirror,build_graph
path=Path(os.environ.get('AI4BRAIN_DB','data/ai4brain.sqlite3'))
if not path.is_absolute(): path=ROOT/path
with closing(sqlite3.connect(path)) as db:
    db.row_factory=sqlite3.Row
    rows=db.execute('SELECT * FROM profile_snapshots WHERE learner_id=? ORDER BY rowid',('demo-user',)).fetchall()
    snapshots=[]
    dimensions={}
    for row in rows:
        s=dict(row);s['evidence_ids']=json.loads(s.pop('evidence_ids_json'));s['completed']=bool(s['completed']);snapshots.append(s);dimensions[s['dimension']]=s
    events=[{'payload':json.loads(row['payload_json'])} for row in db.execute('SELECT payload_json FROM events ORDER BY created_at')]
profile={'learner_id':'demo-user','dimensions':dimensions,'snapshots':snapshots}
graph=build_graph(profile,events=events)
status=GraphMirror(enabled=True).sync(graph)
if not status.get('connected'):raise RuntimeError('Neo4j did not sync: '+str(status))
with GraphDatabase.driver(os.environ.get('NEO4J_URI','bolt://127.0.0.1:7687'),auth=(os.environ.get('NEO4J_USER','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=3) as driver:
    driver.verify_connectivity()
    with driver.session() as session:
        assert session.run('RETURN 1 AS ok').single()['ok']==1
        version=session.run('CALL dbms.components() YIELD versions RETURN versions[0] AS version').single()['version']
        counts=session.run('MATCH (n:AI4BRAIN) RETURN count(n) AS count').single()['count']
        edges=session.run('MATCH (:AI4BRAIN)-[r]->(:AI4BRAIN) RETURN count(r) AS count').single()['count']
        evidence=[dict(row) for row in session.run('MATCH (l:Learner {learner_id:$learner})-[:HAS_ESTIMATE]->(d:DimensionEstimate)-[:FOR_DIMENSION]->(c:CognitiveDimension) MATCH (d)-[:SUPPORTED_BY]->(e:EvidenceSummary) RETURN c.dimension_id AS dimension,d.index_0_100 AS index,e.evidence_count AS count,e.evidence_ids AS evidence_ids',learner='demo-user')]
        assert evidence and all(row['evidence_ids']==dimensions[row['dimension']]['evidence_ids'] for row in evidence)
        assert session.run("MATCH (:ExerciseType {exercise_id:'EX-02'})-[:ASSESSES]->(:CognitiveDimension {dimension_id:'reasoning'}) RETURN count(*) AS n").single()['n']==1
        # A second mirror must not duplicate nodes, edges, or learner preference.
        before=(counts,edges)
        second=GraphMirror(enabled=True).sync(graph)
        assert second['connected']
        after=(session.run('MATCH (n:AI4BRAIN) RETURN count(n) AS n').single()['n'],session.run('MATCH (:AI4BRAIN)-[r]->(:AI4BRAIN) RETURN count(r) AS n').single()['n'])
        assert before==after,(before,after)
result={'status':'PASS','neo4j_version':version,'nodes':counts,'relationships':edges,'mirror_source':'actual SQLite automated QA attempts','evidence':[{'dimension':e['dimension'],'index':e['index'],'count':e['count']} for e in evidence],'idempotent_sync':True,'browser_url':'http://127.0.0.1:7474','bolt_uri':'bolt://127.0.0.1:7687'}
(ROOT/'output'/'verification'/'neo4j-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
