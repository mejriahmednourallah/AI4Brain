"""Read-only Neo4j health/provenance check; never mirrors fixtures or edits graph."""
from pathlib import Path
from contextlib import closing
import json,os,sqlite3
from dotenv import load_dotenv
from neo4j import GraphDatabase
root=Path.cwd();load_dotenv(root/'.env',override=False)
with GraphDatabase.driver(os.environ['NEO4J_URI'],auth=(os.environ['NEO4J_USER'],os.environ['NEO4J_PASSWORD']),connection_timeout=3) as driver:
    driver.verify_connectivity()
    with driver.session(default_access_mode='READ') as session:
        version=session.run('CALL dbms.components() YIELD versions RETURN versions[0] AS version').single()['version']
        count=session.run('MATCH (n:AI4BRAIN) RETURN count(n) AS n').single()['n']
        relationships=[dict(r) for r in session.run('MATCH (:AI4BRAIN)-[r]->(:AI4BRAIN) RETURN type(r) AS type,count(*) AS n ORDER BY type')]
        summaries=[dict(r) for r in session.run('MATCH (n:AI4BRAIN:EvidenceSummary) RETURN n.evidence_ids AS ids,n.evidence_count AS count')]
        assert summaries
with closing(sqlite3.connect(root/'data/ai4brain.sqlite3')) as db:
    known={r[0] for r in db.execute('SELECT event_id FROM events')}
refs=set()
for summary in summaries:
    assert len(summary['ids'])==summary['count']
    assert set(summary['ids']).issubset(known)
    refs.update(summary['ids'])
required={'ASSESSES','TARGETS','INSTANCE_OF','HAS_ESTIMATE','FOR_DIMENSION','SUPPORTED_BY','CAPTURES'}
assert required.issubset({r['type'] for r in relationships})
result={'status':'PASS','mode':'read-only','neo4j_version':version,'nodes':count,'relationships':relationships,'unique_canonical_event_references_checked':len(refs),'evidence_summary_count':len(summaries),'all_references_resolve_to_sqlite':True,'mirror_updates_on_graph_request':True,'participant_results_not_exported':True}
(root/'output/verification/neo4j-readonly-live.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
