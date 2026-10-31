"""SQLite-derived two-brain graph. A Neo4j mirror is explicitly optional.

This module starts no service/container and never owns canonical observations.
"""
from __future__ import annotations
import json
import os
import hashlib
import threading
import time
from collections import OrderedDict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from typing import Any

GRAPH_VERSION = 'graph-v2'
FAMILIES = {
    'working_memory': ('EX-01', 'Working memory'),
    'reasoning': ('EX-02', 'Reasoning'),
    'attention_inhibition': ('EX-03', 'Attention and inhibition'),
    'flexibility': ('EX-04', 'Cognitive flexibility'),
    'planning': ('EX-05', 'Planning'),
}
# Share exact strategy identities with the deterministic personalization engine.
from .strategy import STRATEGIES as POLICY_STRATEGIES, strategy_for_error
STRATEGIES = {value['id']:(value['dimension'],value['title'],[error])
              for error,value in POLICY_STRATEGIES.items()}

LABELS = {'Learner','CognitiveDimension','ExerciseType','ExerciseItem','TrainingStrategy','MisconceptionPattern','DimensionEstimate','ProfileSnapshot','EvidenceSummary','PracticeGoal','DashboardStyle',
          'TrainingPlan','PlanStep','PlanLaunch','CoreTrainingBlock','HybridActivity','HybridAttempt','HybridOutcome','CrystalActivity','CrystalAttempt','CrystalOutcome','CanonicalEvidence'}
RELATIONSHIPS = {'ASSESSES','INSTANCE_OF','TARGETS','ADDRESSES','HAS_ESTIMATE','FOR_DIMENSION','CAPTURES','SUPPORTED_BY','PREFERS_DASHBOARD','HAS_GOAL',
                 'HAS_PLAN','INCLUDES_STEP','USES_ACTIVITY','LINKED_LAUNCH','LAUNCHED_AS','HAS_OUTCOME'}

MAX_SNAPSHOT_ENTRIES = 8
MAX_SNAPSHOT_WEIGHT = 40000
MAX_PAGE_LIMIT = 5000
MAX_LOCAL_DEPTH = 4

_MIRROR_LOCKS_GUARD = threading.Lock()
_MIRROR_LOCKS: dict[str, threading.RLock] = {}


def canonical_store_scope(store: Any) -> str:
    """Private cache namespace for one canonical SQLite database file."""
    path = getattr(store, "path", None)
    if path is None:
        return f"store-object:{id(store)}"
    resolved = os.path.normcase(os.path.realpath(os.fspath(path)))
    try:
        stat = os.stat(resolved)
        identity = f"{stat.st_dev}:{stat.st_ino}"
    except OSError:
        identity = "missing"
    return hashlib.sha256(f"{resolved}|{identity}".encode("utf-8")).hexdigest()[:24]


def _mirror_lock(learner_id: str) -> threading.RLock:
    # Neo4j learner IDs are global across local SQLite source databases.
    with _MIRROR_LOCKS_GUARD:
        return _MIRROR_LOCKS.setdefault(learner_id, threading.RLock())

def _payload(event: dict) -> dict:
    return event.get('payload', event)

def build_graph(profile: dict, events: list[dict] | None = None,
                snapshots: list[dict] | None = None, item_catalog: list[dict] | None = None,
                goal: dict | None = None, dashboard_mode: str = 'analytics') -> dict:
    """Construct inspectable nodes/typed edges only from the supplied evidence.

    The caller supplies its SQLite-derived profile/history and optional real
    exercise catalog. An empty profile has no fabricated evidence or estimate.
    """
    learner_id = profile.get('learner_id', 'demo-user')
    nodes: dict[str, dict] = {}
    edges: dict[tuple[str,str,str], dict] = {}
    def node(id: str, kind: str, label: str, brain: str, **properties: Any) -> str:
        if kind not in LABELS: raise ValueError('unsupported graph node kind')
        nodes[id] = {'id': id, 'type': kind, 'label': label, 'brain': brain, 'properties': properties}
        return id
    def edge(source: str, target: str, relationship: str) -> None:
        if relationship not in RELATIONSHIPS: raise ValueError('unsupported graph relation')
        edges[(source,target,relationship)] = {'source': source, 'target': target, 'type': relationship}
    learner = node(f'learner:{learner_id}', 'Learner', 'Anonymous learner', 'cognitive', learner_id=learner_id)
    for dimension, (exercise, label) in FAMILIES.items():
        did = node(f'dimension:{dimension}', 'CognitiveDimension', label, 'knowledge', dimension_id=dimension)
        xid = node(f'exercise:{exercise}', 'ExerciseType', exercise, 'knowledge', exercise_id=exercise, dimension=dimension)
        edge(xid, did, 'ASSESSES')
    for strategy_id, (dimension, label, errors) in STRATEGIES.items():
        sid = node(f'strategy:{strategy_id}', 'TrainingStrategy', label, 'knowledge', strategy_id=strategy_id, dimension=dimension)
        edge(sid, f'dimension:{dimension}', 'TARGETS')
        for error in errors:
            mid = node(f'error:{error}', 'MisconceptionPattern', error.replace('_',' '), 'knowledge', error_type=error, dimension=dimension)
            edge(sid, mid, 'ADDRESSES')
    catalog = list(item_catalog or [])
    for event in events or []:
        p = _payload(event)
        if p.get('item_id') and p.get('exercise_id'):
            catalog.append({'item_id':p['item_id'], 'exercise_id':p['exercise_id'], 'exercise_version':p.get('exercise_version')})
        evaluation=p.get('evaluation',{})
        if evaluation.get('error_type') and not p.get('interaction',{}).get('visibility_interrupted'):
            selected=strategy_for_error(p.get('exercise_id',''),evaluation['error_type'])
            if selected:
                error=evaluation['error_type'];dimension=selected['dimension']
                mid=node(f'error:{error}', 'MisconceptionPattern',error.replace('_',' '),'knowledge',error_type=error,dimension=dimension)
                sid=f"strategy:{selected['id']}"
                if sid in nodes:edge(sid,mid,'ADDRESSES')

    for item in catalog:
        exercise = item.get('exercise_id')
        item_id = item.get('item_id')
        if not item_id or f'exercise:{exercise}' not in nodes: continue
        iid = node(f'item:{item_id}', 'ExerciseItem', item_id, 'knowledge', item_id=item_id,
                   exercise_id=exercise, exercise_version=item.get('exercise_version'),
                   dimension=next((d for d,(ex,_) in FAMILIES.items() if ex==exercise),None))
        edge(iid, f'exercise:{exercise}', 'INSTANCE_OF')
    for dimension, estimate in profile.get('dimensions', {}).items():
        if dimension not in FAMILIES or not estimate.get('evidence_count', 0): continue
        eid = node(f'estimate:{learner_id}:{dimension}', 'DimensionEstimate', FAMILIES[dimension][1], 'cognitive',
            learner_id=learner_id, dimension=dimension, index_0_100=estimate.get('index_0_100'),
            evidence_count=estimate.get('evidence_count',0), uncertainty_status=estimate.get('uncertainty_status','INCOMPLETE_BASELINE'),
            evidence_ids=estimate.get('evidence_ids',[]), completed=bool(estimate.get('completed',False)))
        edge(learner,eid,'HAS_ESTIMATE'); edge(eid,f'dimension:{dimension}','FOR_DIMENSION')
        evidence = node(f'evidence:current:{learner_id}:{dimension}', 'EvidenceSummary', 'Supporting recorded attempts', 'cognitive',
            learner_id=learner_id, dimension=dimension, evidence_ids=estimate.get('evidence_ids',[]), evidence_count=estimate.get('evidence_count',0))
        edge(eid,evidence,'SUPPORTED_BY')
    history = snapshots if snapshots is not None else profile.get('snapshots', [])
    for snapshot in history:
        dimension = snapshot.get('dimension')
        if dimension not in FAMILIES: continue
        snapshot_id = snapshot.get('id')
        if not snapshot_id: continue
        sid = node(f'snapshot:{snapshot_id}', 'ProfileSnapshot', 'Historical task snapshot', 'cognitive',
            learner_id=learner_id, snapshot_id=snapshot_id, dimension=dimension,
            index_0_100=snapshot.get('index_0_100'), evidence_count=snapshot.get('evidence_count',0),
            uncertainty_status=snapshot.get('uncertainty_status'), created_at=str(snapshot.get('created_at','')),
            scoring_version=snapshot.get('scoring_version'))
        estimate_id = f'estimate:{learner_id}:{dimension}'
        if estimate_id in nodes: edge(sid,estimate_id,'CAPTURES')
        evidence_ids = snapshot.get('evidence_ids',[])
        ev = node(f'evidence:snapshot:{snapshot_id}', 'EvidenceSummary', 'Snapshot attempt references', 'cognitive',
            learner_id=learner_id, dimension=dimension, evidence_ids=evidence_ids, evidence_count=len(evidence_ids))
        edge(sid,ev,'SUPPORTED_BY')
    if dashboard_mode not in {'analytics','rpg'}: raise ValueError('unknown dashboard mode')
    dashboard = node(f'dashboard:{dashboard_mode}', 'DashboardStyle', dashboard_mode.title(), 'preference', style=dashboard_mode)
    edge(learner,dashboard,'PREFERS_DASHBOARD')
    if goal and goal.get('dimension') in FAMILIES:
        gid = node(f'goal:{learner_id}', 'PracticeGoal', 'Declared practice goal', 'cognitive',
            learner_id=learner_id, dimension=goal['dimension'], description=goal.get('description',''))
        edge(learner,gid,'HAS_GOAL'); edge(gid,f"dimension:{goal['dimension']}",'TARGETS')
    return {'graph_version':GRAPH_VERSION, 'source':'sqlite-derived', 'learner_id':learner_id,
            'nodes':list(nodes.values()), 'edges':list(edges.values()),
            'interpretation':'Relationships describe task observations and candidate strategies, not clinical traits.'}

class GraphMirror:
    """A short-lived connection; disabled mode never attempts a network call."""
    def __init__(self, enabled: bool | None = None):
        self.enabled = enabled if enabled is not None else os.getenv('NEO4J_ENABLED','false').lower() == 'true'
    @staticmethod
    def _properties(node: dict) -> dict:
        props = {'label':node['label'], 'brain':node['brain'], 'graph_version':GRAPH_VERSION, **node.get('properties',{})}
        return {k:(json.dumps(v,sort_keys=True) if isinstance(v,dict) else v) for k,v in props.items()}
    def sync(self, graph: dict) -> dict:
        with _mirror_lock(str(graph.get("learner_id", ""))):
            return self._sync_locked(graph)

    def _sync_locked(self, graph: dict) -> dict:
        if not self.enabled:
            return {'enabled':False, 'connected':False, 'status':'disabled', 'message':'Neo4j is disabled. This view derives from local SQLite evidence.'}
        password = os.getenv('NEO4J_PASSWORD')
        if not password:
            return {'enabled':True, 'connected':False, 'status':'unconfigured', 'message':'Neo4j credentials are not configured.'}
        try:
            from neo4j import GraphDatabase
            with GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),
                    auth=(os.getenv('NEO4J_USER','neo4j'),password), connection_timeout=2,
                    connection_acquisition_timeout=3, max_transaction_retry_time=0) as driver:
                driver.verify_connectivity()
                with driver.session() as session:
                    session.execute_write(self._write_graph,graph)
            return {'enabled':True,'connected':True,'status':'synced','graph_version':GRAPH_VERSION,'source':'sqlite-derived'}
        except Exception:
            return {'enabled':True,'connected':False,'status':'unavailable','message':'Neo4j mirror unavailable. Local evidence and the derived view remain usable.'}
    def _write_graph(self, tx: Any, graph: dict) -> None:
        grouped: dict[str,list[dict]] = defaultdict(list)
        for n in graph['nodes']:
            if n['type'] not in LABELS: raise ValueError('unsupported graph node kind')
            grouped[n['type']].append({'id':n['id'],'properties':self._properties(n)})
        for label, rows in grouped.items():
            tx.run(f'UNWIND $rows AS row MERGE (n:AI4BRAIN:{label} {{id:row.id}}) SET n += row.properties',rows=rows).consume()
        # Replace the learner-derived view as one unit inside the mirror transaction.
        # Shared curated knowledge nodes and other learners' relationships are untouched.
        tx.run('MATCH (n:AI4BRAIN) WHERE n.learner_id=$learner OPTIONAL MATCH (n)-[r]-() DELETE r',
               learner=graph['learner_id']).consume()
        # This one preference is mutable presentation state, never score evidence.
        tx.run('MATCH (n:AI4BRAIN:Learner {id:$id})-[r:PREFERS_DASHBOARD]->() DELETE r',id=f"learner:{graph['learner_id']}").consume()
        # Remove personal nodes no longer present in canonical SQLite state; never
        # prune another learner or unlabelled graph data.
        tx.run('MATCH (n:AI4BRAIN) WHERE n.learner_id=$learner AND NOT n.id IN $ids DETACH DELETE n',
               learner=graph['learner_id'],ids=[n['id'] for n in graph['nodes']]).consume()
        # Curated schema migrations remove only this app's obsolete knowledge.
        tx.run('MATCH (n:AI4BRAIN) WHERE n.brain="knowledge" AND n.graph_version<>$version DETACH DELETE n',
               version=GRAPH_VERSION).consume()
        for relationship in sorted(RELATIONSHIPS):
            rows=[e for e in graph['edges'] if e['type']==relationship]
            if rows:
                tx.run(f'UNWIND $rows AS row MATCH (a:AI4BRAIN {{id:row.source}}), (b:AI4BRAIN {{id:row.target}}) MERGE (a)-[:{relationship}]->(b)',rows=rows).consume()
    def erase_learner(self, learner_id: str) -> dict:
        with _mirror_lock(learner_id):
            return self._erase_learner_locked(learner_id)

    def _erase_learner_locked(self, learner_id: str) -> dict:
        if not self.enabled:
            return {'status':'disabled','erasure_verified':False,'message':'Mirror erasure must be reconciled when Neo4j is enabled if it previously contained this learner.'}
        try:
            from neo4j import GraphDatabase
            with GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'),
                    auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD','')),
                    connection_timeout=2,connection_acquisition_timeout=3,max_transaction_retry_time=0) as driver:
                with driver.session() as session:
                    session.run('MATCH (n:AI4BRAIN) WHERE n.learner_id=$id DETACH DELETE n',id=learner_id).consume()
                    remaining=session.run('MATCH (n:AI4BRAIN) WHERE n.learner_id=$id RETURN count(n) AS n',id=learner_id).single()['n']
            return {'status':'deleted','erasure_verified':remaining==0}
        except Exception:
            return {'status':'unavailable','erasure_verified':False,'message':'Mirror erasure is pending reconciliation.'}


def graph_source_revision(store: Any, learner_id: str) -> str:
    """Cheap append/update revision over canonical graph inputs plus lifecycle generation."""
    with closing(store.connect()) as db:
        lifecycle = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                               (learner_id,)).fetchone()
        generation = (int(lifecycle["generation"]), int(lifecycle["deleting"])) if lifecycle else (0, 0)
        signatures: list[tuple[Any, ...]] = []
        specs = [
            ("events", "SELECT COALESCE(MAX(rowid),0) FROM events WHERE session_id IN "
                       "(SELECT id FROM sessions WHERE learner_id=?)", (learner_id,)),
            ("profile_snapshots", "SELECT COALESCE(MAX(rowid),0) FROM profile_snapshots WHERE learner_id=?", (learner_id,)),
            ("training_plans", "SELECT COALESCE(MAX(rowid),0) FROM training_plans WHERE learner_id=?", (learner_id,)),
            ("training_blocks", "SELECT COALESCE(MAX(rowid),0) FROM training_blocks WHERE learner_id=?", (learner_id,)),
            ("difficulty_decisions", "SELECT COALESCE(MAX(rowid),0) FROM difficulty_decisions WHERE learner_id=?", (learner_id,)),
            ("hybrid_attempts", "SELECT COALESCE(MAX(rowid),0) FROM hybrid_attempts WHERE learner_id=?", (learner_id,)),
            ("hybrid_events", "SELECT COALESCE(MAX(e.rowid),0) FROM hybrid_events e JOIN hybrid_attempts a USING(attempt_id) WHERE a.learner_id=?", (learner_id,)),
            ("hybrid_outcomes", "SELECT COALESCE(MAX(rowid),0) FROM hybrid_outcomes WHERE learner_id=?", (learner_id,)),
            ("crystal_attempts", "SELECT COALESCE(MAX(rowid),0) FROM crystal_attempts WHERE learner_id=?", (learner_id,)),
            ("crystal_events", "SELECT COALESCE(MAX(e.rowid),0) FROM crystal_events e JOIN crystal_attempts a USING(attempt_id) WHERE a.learner_id=?", (learner_id,)),
            ("crystal_outcomes", "SELECT COALESCE(MAX(rowid),0) FROM crystal_outcomes WHERE learner_id=?", (learner_id,)),
            ("plan_step_launches", "SELECT COALESCE(MAX(rowid),0) FROM plan_step_launches WHERE learner_id=?", (learner_id,)),
        ]
        for name, sql, params in specs:
            # Some optional activity tables are created with their route module.
            present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            if not present:
                signatures.append((name, 0))
                continue
            row = db.execute(sql, params).fetchone()
            signatures.append((name, row[0]))
    material = json.dumps([GRAPH_VERSION, canonical_store_scope(store), learner_id, generation, signatures], separators=(",", ":"), default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def graph_lifecycle_generation(store: Any, learner_id: str) -> int:
    with closing(store.connect()) as db:
        row = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?",
                         (learner_id,)).fetchone()
    if row and row["deleting"]:
        raise ValueError("learner graph is unavailable during deletion")
    return int(row["generation"]) if row else 0


def _activity_node_id(kind: str, activity_id: str) -> str:
    return f"{kind}-activity:{activity_id}"


def add_canonical_activity_records(graph: dict[str, Any], store: Any, learner_id: str) -> dict[str, Any]:
    """Extend graph-v2 with namespaced plan and actual activity records, never inferred links."""
    from .plan_v3 import _ensure_launch_table
    from .hybrid_activities import capability_metadata
    from .crystal_reasoning import CAPABILITY_METADATA as CRYSTAL_CAPABILITIES
    _ensure_launch_table(store)
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {(edge["source"], edge["target"], edge["type"]): edge for edge in graph["edges"]}

    def add_node(node_id: str, kind: str, label: str, brain: str, **properties: Any) -> str:
        if kind not in LABELS:
            raise ValueError(f"unsupported graph node kind: {kind}")
        nodes.setdefault(node_id, {"id": node_id, "type": kind, "label": label, "brain": brain,
                                   "properties": properties})
        return node_id

    def add_edge(source: str, target: str, relation: str) -> None:
        if source not in nodes or target not in nodes:
            return
        if relation not in RELATIONSHIPS:
            raise ValueError(f"unsupported graph relation: {relation}")
        edges.setdefault((source, target, relation), {"source": source, "target": target, "type": relation})

    plans = store.plans(learner_id)
    launch_rows: list[dict[str, Any]] = []
    with closing(store.connect()) as db:
        launch_rows = [dict(row) for row in db.execute(
            "SELECT * FROM plan_step_launches WHERE learner_id=? ORDER BY created_at,request_id", (learner_id,)
        ).fetchall()]
        training_rows = [dict(row) for row in db.execute(
            "SELECT * FROM training_blocks WHERE learner_id=? ORDER BY started_at,block_id", (learner_id,)
        ).fetchall()]
        hybrid_rows = [dict(row) for row in db.execute(
            "SELECT * FROM hybrid_attempts WHERE learner_id=? ORDER BY started_at,attempt_id", (learner_id,)
        ).fetchall()]
        hybrid_outcomes = [dict(row) for row in db.execute(
            "SELECT * FROM hybrid_outcomes WHERE learner_id=? ORDER BY created_at,attempt_id", (learner_id,)
        ).fetchall()]
        hybrid_events = [dict(row) for row in db.execute(
            "SELECT e.* FROM hybrid_events e JOIN hybrid_attempts a USING(attempt_id) "
            "WHERE a.learner_id=? ORDER BY e.created_at,e.event_id", (learner_id,)
        ).fetchall()]
        crystal_rows = [dict(row) for row in db.execute(
            "SELECT * FROM crystal_attempts WHERE learner_id=? ORDER BY started_at,attempt_id", (learner_id,)
        ).fetchall()]
        crystal_outcomes = [dict(row) for row in db.execute(
            "SELECT * FROM crystal_outcomes WHERE learner_id=? ORDER BY created_at,attempt_id", (learner_id,)
        ).fetchall()]
        crystal_events = [dict(row) for row in db.execute(
            "SELECT e.* FROM crystal_events e JOIN crystal_attempts a USING(attempt_id) "
            "WHERE a.learner_id=? ORDER BY e.created_at,e.event_id", (learner_id,)
        ).fetchall()]

    def unpack(value: str | None, fallback: Any) -> Any:
        return json.loads(value) if value else fallback

    for plan in plans:
        plan_id = plan["plan_id"]
        plan_node = add_node(f"plan:{plan_id}", "TrainingPlan", f"Plan {plan_id[:8]}", "cognitive",
            learner_id=learner_id, plan_id=plan_id, plan_version=plan.get("plan_version"),
            schema_version=plan.get("schema_version"), policy_version=plan.get("policy_version"),
            status=plan.get("status"), budget_minutes=plan.get("budget_minutes"),
            estimated_time_minutes=plan.get("estimated_time_minutes", plan.get("planned_minutes")),
            evidence_ids=list(plan.get("evidence_ids", [])),
            record_ref={"kind": "plan", "id": plan_id, "version": plan.get("plan_version")})
        add_edge(f"learner:{learner_id}", plan_node, "HAS_PLAN")
        for step in plan.get("steps", []):
            step_id = str(step.get("step_id") or "")
            if not step_id:
                continue
            dimension = step.get("dimension_id")
            ref = step.get("activity_ref") or {}
            evidence_ids = list(dict.fromkeys([*(step.get("evidence_ids") or []),
                                                *((step.get("completion_references") or []))]))
            step_node = add_node(f"plan-step:{plan_id}:{step_id}", "PlanStep", str(step.get("title") or step.get("exercise_type_id") or step_id), "cognitive",
                learner_id=learner_id, plan_id=plan_id, step_id=step_id, dimension=dimension,
                action=step.get("action"), status=step.get("status"), estimated_time_minutes=step.get("estimated_time_minutes"),
                reason_codes=list(step.get("reason_codes") or []), evidence_ids=evidence_ids,
                activity_ref=ref, launch_mode=step.get("mode"), launch_tier=step.get("launch_tier") or step.get("difficulty_tier"),
                record_ref={"kind": "plan_step", "id": f"{plan_id}::{step_id}",
                            "version": ref.get("version") or plan.get("plan_version")})
            add_edge(plan_node, step_node, "INCLUDES_STEP")
            activity_id = str(ref.get("id") or step.get("exercise_type_id") or "")
            activity_kind = ref.get("kind")
            if activity_kind in {"hybrid", "crystal"} and activity_id:
                capability = capability_metadata(activity_id) if activity_kind == "hybrid" else CRYSTAL_CAPABILITIES
                static_node = add_node(_activity_node_id(activity_kind, activity_id),
                    "HybridActivity" if activity_kind == "hybrid" else "CrystalActivity",
                    activity_id, "knowledge", activity_id=activity_id,
                    activity_version=ref.get("version"), family_relevance=list(capability["family_relevance"]),
                    relevance_scope="task_mechanics_only_not_assessment",
                    record_ref=None)
                add_edge(step_node, static_node, "USES_ACTIVITY")
            elif activity_kind == "core" and activity_id:
                add_edge(step_node, f"exercise:{activity_id}", "USES_ACTIVITY")

    canonical_events = store.events(learner_id=learner_id)
    core_events_by_block: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in canonical_events:
        block_id = (event.get("payload") or {}).get("training_block_id")
        if block_id:
            core_events_by_block[str(block_id)].append(event)
    hybrid_events_by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in hybrid_events:
        hybrid_events_by_attempt[event["attempt_id"]].append(event)
    crystal_events_by_attempt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in crystal_events:
        crystal_events_by_attempt[event["attempt_id"]].append(event)

    event_index: dict[str, dict[str, Any]] = {}
    for event in canonical_events:
        event_index.setdefault(event["event_id"], {"source": "events", "event_type": event["type"],
            "created_at": event.get("created_at"), "record_ref": {"kind": "canonical_event", "id": event["event_id"],
                "version": None, "source_table": "events"}})
    for row in hybrid_events:
        event_index.setdefault(row["event_id"], {"source": "hybrid_events", "event_type": row["type"],
            "created_at": row.get("created_at"), "record_ref": {"kind": "canonical_event", "id": row["event_id"],
                "version": None, "source_table": "hybrid_events"}})
    for row in crystal_events:
        event_index.setdefault(row["event_id"], {"source": "crystal_events", "event_type": row["event_type"],
            "created_at": row.get("created_at"), "record_ref": {"kind": "canonical_event", "id": row["event_id"],
                "version": None, "source_table": "crystal_events"}})

    record_evidence: dict[str, list[str]] = {}
    for row in training_rows:
        block_id = row["block_id"]
        block_events = [event for event in core_events_by_block.get(block_id, [])
                        if event["type"] == "training_trial_completed"]
        start = next((event for event in core_events_by_block.get(block_id, [])
                      if event["type"] == "training_block_started"), None)
        evidence_ids = [*( [start["event_id"]] if start else []), *[event["event_id"] for event in block_events]]
        node_id = add_node(f"training-block:{block_id}", "CoreTrainingBlock", f"{row['exercise_id']} practice block", "cognitive",
            learner_id=learner_id, session_id=row["session_id"], block_id=block_id, exercise_id=row["exercise_id"],
            dimension=row["dimension"], tier=row["tier"], exercise_version=row["exercise_version"],
            status=row["status"], evidence_ids=evidence_ids,
            record_ref={"kind": "core_training_block", "id": block_id, "version": row["exercise_version"]})
        add_edge(f"exercise:{row['exercise_id']}", node_id, "INSTANCE_OF")
        record_evidence[node_id] = evidence_ids

    for row in hybrid_rows:
        attempt_id = row["attempt_id"]
        family_relevance = list(capability_metadata(row["activity_id"])["family_relevance"])
        evidence_ids = [event["event_id"] for event in hybrid_events_by_attempt.get(attempt_id, [])]
        activity_node = add_node(_activity_node_id("hybrid", row["activity_id"]), "HybridActivity", row["activity_id"],
            "knowledge", activity_id=row["activity_id"], activity_version=row["activity_version"],
            family_relevance=family_relevance, relevance_scope="task_mechanics_only_not_assessment", record_ref=None)
        attempt_node = add_node(f"hybrid-attempt:{attempt_id}", "HybridAttempt", f"{row['activity_id']} attempt", "cognitive",
            learner_id=learner_id, session_id=row["session_id"], attempt_id=attempt_id,
            activity_id=row["activity_id"], activity_version=row["activity_version"],
            family_relevance=family_relevance, relevance_scope="task_mechanics_only_not_assessment",
            config_version=row["config_version"], mode=row["mode"], difficulty_tier=row["difficulty_tier"],
            status=row["status"], started_at=row["started_at"], completed_at=row["completed_at"],
            evidence_ids=evidence_ids,
            record_ref={"kind": "hybrid_attempt", "id": attempt_id, "version": row["activity_version"]})
        add_edge(attempt_node, activity_node, "INSTANCE_OF")
        record_evidence[attempt_node] = evidence_ids
    for row in hybrid_outcomes:
        attempt_id = row["attempt_id"]
        family_relevance = list(capability_metadata(row["activity_id"])["family_relevance"])
        evidence_ids = unpack(row.get("evidence_ids_json"), [])
        outcome_node = add_node(f"hybrid-outcome:{attempt_id}", "HybridOutcome", f"{row['activity_id']} outcome", "cognitive",
            learner_id=learner_id, attempt_id=attempt_id, activity_id=row["activity_id"],
            family_relevance=family_relevance, relevance_scope="task_mechanics_only_not_assessment",
            activity_version=row["activity_version"], evaluation_version=row["evaluation_version"],
            completion_state=row["completion_state"], assisted=bool(row["assisted"]),
            excluded_from_unassisted=bool(row["excluded_from_unassisted"]),
            outcomes=unpack(row.get("outcomes_json"), {}), limitations=unpack(row.get("limitations_json"), []),
            evidence_ids=evidence_ids,
            record_ref={"kind": "hybrid_outcome", "id": attempt_id, "version": row["activity_version"]})
        attempt_node = f"hybrid-attempt:{attempt_id}"
        add_edge(attempt_node, outcome_node, "HAS_OUTCOME")
        record_evidence[outcome_node] = evidence_ids

    for row in crystal_rows:
        attempt_id = row["attempt_id"]
        evidence_ids = [event["event_id"] for event in crystal_events_by_attempt.get(attempt_id, [])]
        activity_node = add_node(_activity_node_id("crystal", "CRYSTAL"), "CrystalActivity", "Crystal matrices", "knowledge",
            activity_id="CRYSTAL", form_version=row["form_version"],
            family_relevance=list(CRYSTAL_CAPABILITIES["family_relevance"]),
            relevance_scope="task_mechanics_only_not_assessment",
            record_ref=None)
        attempt_node = add_node(f"crystal-attempt:{attempt_id}", "CrystalAttempt", "Crystal attempt", "cognitive",
            learner_id=learner_id, session_id=row["session_id"], attempt_id=attempt_id,
            form_version=row["form_version"], generator_version=row["generator_version"],
            family_relevance=list(CRYSTAL_CAPABILITIES["family_relevance"]),
            relevance_scope="task_mechanics_only_not_assessment", status=row["status"],
            started_at=row["started_at"], evidence_ids=evidence_ids,
            record_ref={"kind": "crystal_attempt", "id": attempt_id, "version": row["form_version"]})
        add_edge(attempt_node, activity_node, "INSTANCE_OF")
        record_evidence[attempt_node] = evidence_ids
    for row in crystal_outcomes:
        attempt_id = row["attempt_id"]
        evidence_ids = unpack(row.get("evidence_ids_json"), [])
        outcome_node = add_node(f"crystal-outcome:{attempt_id}", "CrystalOutcome", "Crystal answer outcome", "cognitive",
            learner_id=learner_id, attempt_id=attempt_id, form_version=row["form_version"],
            generator_version=row["generator_version"], evaluation_version=row["evaluation_version"],
            family_relevance=list(CRYSTAL_CAPABILITIES["family_relevance"]),
            relevance_scope="task_mechanics_only_not_assessment",
            correct=bool(row["correct"]), response_time_ms=row["response_time_ms"], evidence_ids=evidence_ids,
            record_ref={"kind": "crystal_outcome", "id": attempt_id, "version": row["form_version"]})
        add_edge(f"crystal-attempt:{attempt_id}", outcome_node, "HAS_OUTCOME")
        record_evidence[outcome_node] = evidence_ids

    attempt_node_by_kind = {"core": lambda aid: f"training-block:{aid}",
                            "hybrid": lambda aid: f"hybrid-attempt:{aid}",
                            "crystal": lambda aid: f"crystal-attempt:{aid}"}
    for row in launch_rows:
        launch_node = add_node(f"plan-launch:{row['request_id']}", "PlanLaunch", "Plan activity launch", "cognitive",
            learner_id=learner_id, session_id=row["session_id"], request_id=row["request_id"],
            plan_id=row["plan_id"], step_id=row["step_id"], activity_kind=row["activity_kind"],
            activity_id=row["activity_id"], activity_version=row["activity_version"],
            status=row["status"], attempt_id=row["attempt_id"], evidence_ids=[row["start_event_id"]],
            record_ref={"kind": "plan_launch", "id": row["request_id"], "version": row["activity_version"]})
        add_edge(f"plan-step:{row['plan_id']}:{row['step_id']}", launch_node, "LINKED_LAUNCH")
        target = attempt_node_by_kind.get(row["activity_kind"])
        if target:
            attempt_node = target(row["attempt_id"])
            if attempt_node in nodes:
                add_edge(launch_node, attempt_node, "LAUNCHED_AS")
        record_evidence[launch_node] = [row["start_event_id"]]

    for node_id, graph_node in nodes.items():
        refs = (graph_node.get("properties") or {}).get("evidence_ids")
        if refs:
            record_evidence.setdefault(node_id, list(refs))

    # Evidence refs stay ids in their canonical store. These lightweight nodes only
    # make valid refs openable; payloads are fetched by the read-only inspector API.
    for source_node, evidence_ids in record_evidence.items():
        for event_id in evidence_ids:
            metadata = event_index.get(str(event_id))
            if not metadata:
                continue
            evidence_node = add_node(f"canonical-evidence:{metadata['source']}:{event_id}",
                "CanonicalEvidence", str(metadata["event_type"]), "cognitive", learner_id=learner_id,
                event_id=str(event_id), source_table=metadata["source"], created_at=metadata["created_at"],
                record_ref=metadata["record_ref"])
            add_edge(source_node, evidence_node, "SUPPORTED_BY")

    graph["nodes"] = list(nodes.values())
    graph["edges"] = list(edges.values())
    return graph


class GraphSnapshotCache:
    """Small process-local LRU of immutable, revision-keyed derived graph snapshots."""
    def __init__(self, max_entries: int = MAX_SNAPSHOT_ENTRIES, max_weight: int = MAX_SNAPSHOT_WEIGHT):
        self.max_entries = max_entries
        self.max_weight = max_weight
        self._items: OrderedDict[tuple[str, str, str], tuple[dict[str, Any], int]] = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _weight(graph: dict[str, Any]) -> int:
        return len(graph.get("nodes", [])) + 2 * len(graph.get("edges", []))

    def get(self, store_scope: str, learner_id: str, revision: str) -> dict[str, Any] | None:
        key = (store_scope, learner_id, revision)
        with self._lock:
            value = self._items.get(key)
            if value is None:
                return None
            self._items.move_to_end(key)
            return value[0]

    def put(self, store_scope: str, learner_id: str, revision: str, graph: dict[str, Any]) -> bool:
        weight = self._weight(graph)
        if weight > self.max_weight:
            return False
        key = (store_scope, learner_id, revision)
        with self._lock:
            for old_key in [item for item in self._items if item[:2] == (store_scope, learner_id) and item != key]:
                self._items.pop(old_key, None)
            self._items.pop(key, None)
            self._items[key] = (graph, weight)
            while (len(self._items) > self.max_entries
                   or sum(item[1] for item in self._items.values()) > self.max_weight):
                self._items.popitem(last=False)
        return True

    def clear(self, learner_id: str | None = None, store_scope: str | None = None) -> int:
        with self._lock:
            keys = [key for key in self._items
                    if (learner_id is None or key[1] == learner_id)
                    and (store_scope is None or key[0] == store_scope)]
            for key in keys:
                self._items.pop(key, None)
            return len(keys)

    def entry_count(self) -> int:
        with self._lock:
            return len(self._items)


GRAPH_SNAPSHOTS = GraphSnapshotCache()


def get_cached_graph(store: Any, learner_id: str, build_source: Any) -> tuple[dict[str, Any], str]:
    """Return a stable cached snapshot or rebuild once when the canonical revision races."""
    from .plan_v3 import _ensure_launch_table
    _ensure_launch_table(store)
    for _attempt in range(2):
        scope = canonical_store_scope(store)
        revision = graph_source_revision(store, learner_id)
        cached = GRAPH_SNAPSHOTS.get(scope, learner_id, revision)
        if cached is not None:
            return cached, "hit"
        graph = build_source()
        graph = add_canonical_activity_records(graph, store, learner_id)
        after = graph_source_revision(store, learner_id)
        if after == revision:
            graph["revision"] = revision
            GRAPH_SNAPSHOTS.put(scope, learner_id, revision, graph)
            return graph, "built"
        revision = after
    graph["revision"] = revision
    graph["snapshot_consistent"] = False
    return graph, "revision_raced"


def clear_graph_cache_for_learner(learner_id: str, store: Any | None = None) -> int:
    """Invalidate derived local snapshots during learner lifecycle deletion."""
    scope = canonical_store_scope(store) if store is not None else None
    cleared = GRAPH_SNAPSHOTS.clear(learner_id, scope)
    MIRROR_COORDINATOR.cancel_learner(learner_id, store)
    return cleared


def _dimension_filtered(graph: dict[str, Any], dimension: str | None) -> dict[str, Any]:
    if dimension is None:
        return graph
    exercise_id = FAMILIES[dimension][0]
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = graph["edges"]
    allowed = set()
    for node in nodes.values():
        props = node.get("properties", {})
        if (node["type"] in {"Learner", "DashboardStyle"}
                    or props.get("dimension") == dimension or props.get("dimension_id") == dimension
                    or dimension in props.get("family_relevance", [])
                or props.get("exercise_id") == exercise_id):
            allowed.add(node["id"])
    for edge in edges:
        if edge["type"] == "TARGETS" and edge["target"] == f"dimension:{dimension}":
            allowed.add(edge["source"])
    # Expand only canonical structural/evidence relations from selected family nodes.
    expansion = {"ADDRESSES", "SUPPORTED_BY", "INCLUDES_STEP", "LINKED_LAUNCH", "LAUNCHED_AS",
                 "HAS_OUTCOME", "USES_ACTIVITY"}
    changed = True
    while changed:
        before = len(allowed)
        for edge in edges:
            if edge["type"] in expansion and edge["source"] in allowed:
                allowed.add(edge["target"])
            if edge["type"] == "INCLUDES_STEP" and edge["target"] in allowed:
                allowed.add(edge["source"])
        changed = len(allowed) != before
    selected_nodes = [node for node in graph["nodes"] if node["id"] in allowed]
    selected_ids = {node["id"] for node in selected_nodes}
    selected_edges = [edge for edge in edges if edge["source"] in selected_ids and edge["target"] in selected_ids]
    return {**graph, "nodes": selected_nodes, "edges": selected_edges}


def filter_graph_snapshot(graph: dict[str, Any], *, dimension: str | None = None,
                          node_types: list[str] | None = None, query: str | None = None,
                          scope: str = "global", center_id: str | None = None, depth: int = 1,
                          limit: int = MAX_PAGE_LIMIT, offset: int = 0) -> dict[str, Any]:
    """Filter and page a snapshot; every returned edge has both returned endpoints."""
    if dimension is not None and dimension not in FAMILIES:
        raise ValueError("unknown dimension")
    if scope not in {"global", "local"}:
        raise ValueError("scope must be global or local")
    if scope == "local" and not center_id:
        raise ValueError("local scope requires center_id")
    if depth < 1 or depth > MAX_LOCAL_DEPTH:
        raise ValueError(f"depth must be between 1 and {MAX_LOCAL_DEPTH}")
    if limit < 1 or limit > MAX_PAGE_LIMIT or offset < 0:
        raise ValueError(f"limit must be 1..{MAX_PAGE_LIMIT} and offset must be non-negative")
    unknown_types = sorted(set(node_types or []) - LABELS)
    if unknown_types:
        raise ValueError("unknown node type: " + ", ".join(unknown_types))

    filtered = _dimension_filtered(graph, dimension)
    lowered = (query or "").strip().casefold()
    nodes = [node for node in filtered["nodes"]
             if (not node_types or node["type"] in node_types)
             and (not lowered or lowered in str(node.get("label", "")).casefold()
                  or lowered in node["id"].casefold())]
    node_map = {node["id"]: node for node in nodes}
    edges = [edge for edge in filtered["edges"] if edge["source"] in node_map and edge["target"] in node_map]
    if scope == "local":
        if center_id not in node_map:
            raise ValueError("center_id is unknown or excluded by active filters")
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])
        included = {center_id}
        frontier = {center_id}
        for _ in range(depth):
            frontier = {neighbor for node_id in frontier for neighbor in adjacency.get(node_id, set())} - included
            included.update(frontier)
            if not frontier:
                break
        nodes = [node for node in nodes if node["id"] in included]
        node_map = {node["id"]: node for node in nodes}
        edges = [edge for edge in edges if edge["source"] in node_map and edge["target"] in node_map]

    filtered_node_count = len(nodes)
    filtered_edge_count = len(edges)
    page_nodes = nodes[offset:offset + limit]
    page_ids = {node["id"] for node in page_nodes}
    page_edges = [edge for edge in edges if edge["source"] in page_ids and edge["target"] in page_ids]
    return {**graph, "nodes": page_nodes, "edges": page_edges,
            "total_node_count": len(graph.get("nodes", [])),
            "filtered_node_count": filtered_node_count,
            "visible_node_count": len(page_nodes),
            "total_edge_count": len(graph.get("edges", [])),
            "filtered_edge_count": filtered_edge_count,
            "visible_edge_count": len(page_edges),
            "offset": offset, "limit": limit, "has_more": offset + len(page_nodes) < filtered_node_count}


class GraphMirrorCoordinator:
    """Single-worker coalesced mirror updater; canonical reads never wait on it."""
    def __init__(self, enabled: bool | None = None, mirror_factory: Any = None):
        self.enabled = enabled
        self.mirror_factory = mirror_factory or GraphMirror
        self._lock = threading.RLock()
        self._pending: dict[tuple[str, str], tuple[Any, dict[str, Any], str, int, int]] = {}
        self._status: dict[tuple[str, str], dict[str, Any]] = {}
        self._epoch: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="graph-mirror")

    def _enabled(self) -> bool:
        return self.enabled if self.enabled is not None else os.getenv("NEO4J_ENABLED", "false").lower() == "true"

    @staticmethod
    def _key(store_scope: str, learner_id: str) -> tuple[str, str]:
        return (store_scope, learner_id)

    def status(self, learner_id: str, store: Any | None = None) -> dict[str, Any]:
        if not self._enabled():
            return {"enabled": False, "connected": False, "status": "disabled",
                    "message": "Neo4j is disabled. This view derives from local SQLite evidence."}
        scope = canonical_store_scope(store) if store is not None else ""
        key = self._key(scope, learner_id)
        with self._lock:
            return dict(self._status.get(key, {"enabled": True, "connected": False,
                "status": "pending", "message": "Derived mirror update has not completed."}))

    def enqueue(self, store: Any, learner_id: str, graph: dict[str, Any], revision: str, lifecycle_generation: int) -> dict[str, Any]:
        if not self._enabled():
            return self.status(learner_id, store)
        key = self._key(canonical_store_scope(store), learner_id)
        with self._lock:
            epoch = self._epoch[key]
            self._pending[key] = (store, graph, revision, lifecycle_generation, epoch)
            self._status[key] = {"enabled": True, "connected": False, "status": "pending",
                "revision": revision, "message": "A coalesced derived mirror update is queued."}
            if not self._running:
                self._running = True
                self._executor.submit(self._drain)
            return dict(self._status[key])

    @staticmethod
    def _generation(store: Any, learner_id: str) -> int:
        with closing(store.connect()) as db:
            row = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?", (learner_id,)).fetchone()
        if row and row["deleting"]:
            return -1
        return int(row["generation"]) if row else 0

    def _drain(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    self._running = False
                    return
                key = next(iter(self._pending))
                pending = self._pending.pop(key)
                store, graph, revision, generation, epoch = pending
                learner_id = key[1]
            result: dict[str, Any]
            try:
                # This derived-work lock serializes mirror writes with mirror erasure,
                # but never blocks canonical plan/coach/lifecycle work on its lock.
                with _mirror_lock(learner_id):
                    with self._lock:
                        still_current = self._epoch[key] == epoch
                    current = self._generation(store, learner_id)
                    if not still_current or current != generation:
                        result = {"enabled": True, "connected": False, "status": "stale",
                                  "message": "Learner lifecycle changed before mirror update."}
                    else:
                        result = self.mirror_factory(enabled=self.enabled).sync(graph)
                        # If deletion raced with a slow write, erase its stale mirror
                        # before releasing the shared mirror lock. cancel_learner is
                        # deliberately nonblocking and changes the epoch immediately.
                        with self._lock:
                            invalidated = self._epoch[key] != epoch
                        latest_generation = self._generation(store, learner_id)
                        if invalidated or latest_generation != generation:
                            self.mirror_factory(enabled=self.enabled).erase_learner(learner_id)
                            result = {"enabled": True, "connected": False, "status": "stale",
                                      "message": "A lifecycle change invalidated the in-flight mirror write."}
                with self._lock:
                    if self._epoch[key] != epoch:
                        self._status.pop(key, None)
                        continue
                    if key in self._pending:
                        continue
                    normalized = dict(result)
                    normalized["revision"] = revision
                    if normalized.get("status") in {"unavailable", "unconfigured"}:
                        normalized["status"] = "degraded"
                    self._status[key] = normalized
            except Exception:
                with self._lock:
                    if self._epoch[key] == epoch and key not in self._pending:
                        self._status[key] = {"enabled": True, "connected": False, "status": "degraded",
                            "revision": revision, "message": "Derived mirror update failed; SQLite graph remains available."}

    def cancel_learner(self, learner_id: str, store: Any | None = None) -> None:
        scope = canonical_store_scope(store) if store is not None else ""
        key = self._key(scope, learner_id)
        with self._lock:
            self._epoch[key] += 1
            self._pending.pop(key, None)
            self._status.pop(key, None)

    def wait_idle(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._running and not self._pending:
                    return True
            time.sleep(0.005)
        return False


MIRROR_COORDINATOR = GraphMirrorCoordinator()
