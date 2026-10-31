import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, ArrowRight, BookOpen, Brain, Compass, FileSearch, History, Info, Layers, LayoutDashboard, Lightbulb, Network, RefreshCw, Target, User } from 'lucide-react';
import { useReducedMotion } from 'motion/react';
import { adventureWorlds } from '../../adventure-worlds';
import { EvidenceGraphCanvas } from './EvidenceGraphCanvas';
import './evidence-page.css';

export type EvidenceGraphNode = {
  id: string; type: string; label: string; brain?: string; properties?: Record<string, unknown>;
};
export type EvidenceGraphEdge = { source: string; target: string; type: string };
export type EvidenceRecordRef = { kind: string; id: string; version?: string | null };
export type EvidenceResolvedRecord = {
  learner_id?: string; record_ref?: EvidenceRecordRef; record?: Record<string, unknown>;
  evidence?: Array<{ id?: string; event_id?: string; source_table?: string; resolvable?: boolean; type?: string; created_at?: string; payload?: unknown }>;
};
export type EvidenceGraphQuery = {
  dimension?: string; q?: string; node_types?: string[]; scope: 'global' | 'local';
  center_id?: string; depth?: number; limit?: number; offset?: number;
};
export type EvidenceMirrorStatus = {
  enabled?: boolean; connected?: boolean; status?: string; message?: string; source?: string;
};
export type EvidenceGraph = {
  graph_version?: string; source?: string; learner_id?: string; nodes?: EvidenceGraphNode[]; edges?: EvidenceGraphEdge[];
  interpretation?: string; mirror_status?: EvidenceMirrorStatus | null;
  revision?: string; requested_revision?: string | null; revision_changed?: boolean; snapshot_status?: string;
  total_node_count?: number; filtered_node_count?: number; visible_node_count?: number;
  total_edge_count?: number; filtered_edge_count?: number; visible_edge_count?: number;
  has_more?: boolean; offset?: number; limit?: number;
};
export type EvidencePageProps = {
  graph: EvidenceGraph | null; dimension: string; loading: boolean; error: string | null;
  selectedStrategyId?: string | null; onSelectDimension: (dimension: string) => void; onRefresh: () => void;
  /** Legacy callback for explicitly stored `evidence_ids` references. */
  onOpenEvidenceRecord?: (eventId: string) => void;
  /** Debounced query callback. Parent should include these fields in `/api/graph/{learner_id}` and guard stale responses. */
  onQueryGraph?: (query: EvidenceGraphQuery) => void;
  /** Resolve the selected node's stored `record_ref` through the canonical graph record endpoint. */
  onResolveRecord?: (ref: EvidenceRecordRef, learnerId: string) => Promise<EvidenceResolvedRecord | null>;
  /** Optional navigation hook for opening a resolved canonical record elsewhere in the app. */
  onOpenRecord?: (ref: EvidenceRecordRef, learnerId: string) => void;
};

const dimensionTitle: Record<string, string> = {
  working_memory: 'Working memory', reasoning: 'Reasoning', attention_inhibition: 'Attention & inhibition',
  flexibility: 'Cognitive flexibility', planning: 'Planning',
};
const exerciseForDimension: Record<string, string> = {
  working_memory: 'EX-01', reasoning: 'EX-02', attention_inhibition: 'EX-03', flexibility: 'EX-04', planning: 'EX-05',
};
const typeMeta: Record<string, { label: string; icon: typeof User }> = {
  Learner: { label: 'Learner', icon: User }, PracticeGoal: { label: 'Practice goal', icon: Compass },
  DashboardStyle: { label: 'Dashboard style', icon: LayoutDashboard }, DimensionEstimate: { label: 'Task estimate', icon: Target },
  CognitiveDimension: { label: 'Task dimension', icon: Brain }, ExerciseType: { label: 'Exercise', icon: BookOpen },
  EvidenceSummary: { label: 'Evidence summary', icon: FileSearch }, ProfileSnapshot: { label: 'Profile snapshot', icon: History },
  TrainingStrategy: { label: 'Strategy', icon: Lightbulb }, MisconceptionPattern: { label: 'Error pattern', icon: AlertCircle },
  ExerciseItem: { label: 'Exercise item', icon: Layers }, TrainingPlan: { label: 'Plan', icon: Compass },
  PlanStep: { label: 'Plan step', icon: ArrowRight }, PlanLaunch: { label: 'Plan launch', icon: ArrowRight },
  CoreTrainingBlock: { label: 'Core practice', icon: Brain }, HybridActivity: { label: 'Hybrid activity', icon: Layers },
  HybridAttempt: { label: 'Hybrid attempt', icon: Target }, HybridOutcome: { label: 'Hybrid outcome', icon: FileSearch },
  CrystalActivity: { label: 'Crystal activity', icon: Layers }, CrystalAttempt: { label: 'Crystal attempt', icon: Target },
  CrystalOutcome: { label: 'Crystal outcome', icon: FileSearch }, CanonicalEvidence: { label: 'Canonical evidence', icon: FileSearch },
};
function humanize(value: unknown): string {
  return String(value ?? '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/^\w/, letter => letter.toUpperCase());
}
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'Not recorded';
  if (Array.isArray(value)) return value.length ? value.map(item => typeof item === 'object' ? JSON.stringify(item) : String(item)).join(', ') : 'None';
  if (typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return /^[A-Z0-9_]+$/.test(String(value)) && String(value).includes('_')
    ? String(value).toLowerCase().replaceAll('_', ' ').replace(/^\w/, letter => letter.toUpperCase()) : String(value);
}
function getRecordRef(node: EvidenceGraphNode | null): EvidenceRecordRef | null {
  const ref = node?.properties?.record_ref;
  if (!ref || typeof ref !== 'object') return null;
  const value = ref as Record<string, unknown>;
  if (typeof value.kind !== 'string' || typeof value.id !== 'string') return null;
  return { kind: value.kind, id: value.id, version: typeof value.version === 'string' ? value.version : null };
}
function evidenceIds(node: EvidenceGraphNode | null): string[] {
  const value = node?.properties?.evidence_ids;
  return Array.isArray(value) ? value.map(String) : [];
}
function matchesDimension(node: EvidenceGraphNode, dimension: string): boolean {
  const props = node.properties ?? {};
  const relevance = Array.isArray(props.family_relevance) ? props.family_relevance.map(String) : [];
  return node.type === 'Learner' || node.type === 'DashboardStyle'
    || props.dimension === dimension || props.dimension_id === dimension
    || relevance.includes(dimension) || props.exercise_id === exerciseForDimension[dimension];
}

export function EvidencePage({ graph, dimension, loading, error, onSelectDimension, onRefresh,
  onOpenEvidenceRecord, onQueryGraph, onResolveRecord, onOpenRecord }: EvidencePageProps) {
  const reduceMotion = useReducedMotion();
  const nodes = graph?.nodes ?? []; const edges = graph?.edges ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState(''); const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [scope, setScope] = useState<'global' | 'local'>('global'); const [depth, setDepth] = useState(1);
  const [centerId, setCenterId] = useState<string | null>(null); const [listLimit, setListLimit] = useState(100);
  const [resolved, setResolved] = useState<EvidenceResolvedRecord | null>(null);
  const [resolveState, setResolveState] = useState<'idle' | 'loading' | 'error'>('idle');
  const selected = nodes.find(node => node.id === selectedId) ?? nodes[0] ?? null;
  const selectedRef = getRecordRef(selected);
  const learnerId = graph?.learner_id ?? '';
  const mirror = graph?.mirror_status;
  const queryCenter = scope === 'local' ? (selected?.id ?? centerId ?? undefined) : undefined;
  const world = adventureWorlds.find(item => item.dimension === dimension);
  const groupedTypes = useMemo(() => Array.from(new Set(nodes.map(node => node.type))).sort((a, b) =>
    (typeMeta[a]?.label ?? a).localeCompare(typeMeta[b]?.label ?? b)), [nodes]);

  useEffect(() => {
    if (selectedId && nodes.some(node => node.id === selectedId)) return;
    const preferred = nodes.find(node => node.type === 'DimensionEstimate') ?? nodes.find(node => node.type === 'Learner') ?? nodes[0];
    setSelectedId(preferred?.id ?? null); setCenterId(preferred?.id ?? null);
  }, [nodes, selectedId]);
  useEffect(() => { setListLimit(100); }, [search, selectedTypes, scope, dimension, graph?.revision]);
  useEffect(() => {
    if (!onQueryGraph) return;
    const timer = window.setTimeout(() => onQueryGraph({ dimension, q: search.trim() || undefined,
      node_types: selectedTypes.length ? selectedTypes : undefined, scope,
      center_id: queryCenter, depth, limit: 5000, offset: 0 }), 140);
    return () => window.clearTimeout(timer);
  }, [dimension, search, selectedTypes, scope, queryCenter, depth, onQueryGraph]);

  useEffect(() => {
    let live = true;
    setResolved(null); setResolveState('idle');
    if (!selectedRef || !onResolveRecord || !learnerId) return () => { live = false; };
    setResolveState('loading');
    onResolveRecord(selectedRef, learnerId).then(record => {
      if (!live) return; setResolved(record); setResolveState(record ? 'idle' : 'error');
    }).catch(() => { if (live) setResolveState('error'); });
    return () => { live = false; };
  }, [selectedRef?.kind, selectedRef?.id, selectedRef?.version, learnerId, onResolveRecord]);

  const activeCenter = scope === 'local' ? (selected?.id ?? centerId) : null;
  const filteredGraph = useMemo(() => {
    const lower = search.trim().toLocaleLowerCase();
    // Keep saved plan containers visible in a family view when one or more of
    // their canonical steps belongs to that family. The container itself has
    // no family field, so it cannot match matchesDimension directly.
    const dimensionNodeIds = new Set(nodes.filter(node => matchesDimension(node, dimension)).map(node => node.id));
    const planNodeIds = new Set(nodes.filter(node => node.type === 'TrainingPlan').map(node => node.id));
    const relevantPlanIds = new Set(edges.filter(edge => edge.type === 'INCLUDES_STEP' && dimensionNodeIds.has(edge.target))
      .map(edge => edge.source).filter(id => planNodeIds.has(id)));
    const relevantPlanStepIds = new Set(edges.filter(edge => edge.type === 'INCLUDES_STEP' && relevantPlanIds.has(edge.source))
      .map(edge => edge.target));
    // The server expands a local neighborhood from the dimension-filtered
    // center and may return related plan/evidence nodes from other families.
    // Keep those canonical neighbors when App owns the query; local-only mode
    // still applies the family filter before walking adjacency.
    const serverExpandedNeighborhood = scope === 'local' && Boolean(onQueryGraph);
    let filteredNodes = nodes.filter(node => (!selectedTypes.length || selectedTypes.includes(node.type))
      && (!lower || node.label.toLocaleLowerCase().includes(lower) || node.id.toLocaleLowerCase().includes(lower))
      && (serverExpandedNeighborhood || matchesDimension(node, dimension)
        || relevantPlanIds.has(node.id) || relevantPlanStepIds.has(node.id)));
    let filteredIds = new Set(filteredNodes.map(node => node.id));
    let filteredEdges = edges.filter(edge => filteredIds.has(edge.source) && filteredIds.has(edge.target));
    if (scope === 'local') {
      const center = activeCenter && filteredIds.has(activeCenter) ? activeCenter : centerId;
      if (center && filteredIds.has(center)) {
        const adjacency = new Map<string, Set<string>>();
        for (const edge of filteredEdges) {
          if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
          if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
          adjacency.get(edge.source)?.add(edge.target); adjacency.get(edge.target)?.add(edge.source);
        }
        const included = new Set([center]); let frontier = new Set([center]);
        for (let step = 0; step < depth; step += 1) {
          const next = new Set<string>();
          for (const id of frontier) for (const neighbor of adjacency.get(id) ?? []) if (!included.has(neighbor)) next.add(neighbor);
          next.forEach(id => included.add(id)); frontier = next;
        }
        filteredNodes = filteredNodes.filter(node => included.has(node.id));
        filteredIds = new Set(filteredNodes.map(node => node.id));
        filteredEdges = filteredEdges.filter(edge => filteredIds.has(edge.source) && filteredIds.has(edge.target));
      } else { filteredNodes = []; filteredEdges = []; }
    }
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [nodes, edges, search, selectedTypes, dimension, scope, activeCenter,
    // The saved center only influences the local traversal. Changing selection
    // in whole-graph mode should not rebuild every node/edge array or restart
    // the layout worker.
    scope === 'local' ? centerId : null, depth, onQueryGraph]);
  const visibleNodes = filteredGraph.nodes;
  const visibleEdges = filteredGraph.edges;
  const selectedVisibleIndex = visibleNodes.findIndex(node => node.id === selected?.id);
  const selectedOutsideCanvasIndex = visibleNodes.length > 5000 && selectedVisibleIndex >= 5000 ? selectedVisibleIndex : null;
  const canvasNodes = useMemo(() => {
    if (visibleNodes.length <= 5000) return visibleNodes;
    const firstPage = visibleNodes.slice(0, selectedOutsideCanvasIndex === null ? 5000 : 4999);
    return selectedOutsideCanvasIndex === null ? firstPage : [...firstPage, visibleNodes[selectedOutsideCanvasIndex]];
  }, [visibleNodes, selectedOutsideCanvasIndex]);
  const canvasNodeIds = useMemo(() => new Set(canvasNodes.map(node => node.id)), [canvasNodes]);
  const canvasEdges = useMemo(() => visibleEdges.filter(edge => canvasNodeIds.has(edge.source) && canvasNodeIds.has(edge.target)), [visibleEdges, canvasNodeIds]);
  const rendererNodeOmission = Math.max(0, visibleNodes.length - canvasNodes.length);
  const rendererEdgeLayoutCapped = canvasEdges.length > 30000;
  const selectedMeta = selected ? typeMeta[selected.type] : null;
  const SelectedIcon = selectedMeta?.icon ?? Network;
  const selectedRelationships = selected ? edges.filter(edge => edge.source === selected.id || edge.target === selected.id) : [];
  const evidence = evidenceIds(selected);
  const resolvedRecord = resolved?.record ?? null;
  const totalNodeCount = graph?.total_node_count ?? nodes.length;
  const totalEdgeCount = graph?.total_edge_count ?? edges.length;
  const hasGraph = nodes.length > 0;
  const listNodes = visibleNodes.slice(0, listLimit);
  const toggleType = (type: string) => setSelectedTypes(current => current.includes(type) ? current.filter(value => value !== type) : [...current, type]);
  const focusNeighborhood = () => { setCenterId(selected?.id ?? null); setScope(current => current === 'global' ? 'local' : 'global'); };
  const openRef = (ref: EvidenceRecordRef) => { onOpenRecord?.(ref, learnerId); };

  return <main className="evidence-rebuild" aria-labelledby="evidence-title">
    <section className="evidence-header"><div><p className="evidence-eyebrow">Your evidence graph</p><h1 id="evidence-title">Follow the evidence.</h1><p>A map of recorded tasks, estimates and strategies. Every relationship is derived from saved local evidence.</p></div>
      <button type="button" className="evidence-refresh" onClick={onRefresh} disabled={loading}><RefreshCw aria-hidden="true" /> {loading ? 'Refreshing…' : 'Refresh graph'}</button>
    </section>
    <nav className="evidence-worlds" aria-label="Evidence graph task family">{adventureWorlds.map(item => <button type="button" key={item.dimension} className={item.dimension === dimension ? 'is-selected' : ''} aria-pressed={item.dimension === dimension} onClick={() => onSelectDimension(item.dimension)}>
      <img src={item.image} alt="" loading="lazy" /><span><strong>{item.name}</strong><small>{item.place}</small></span></button>)}</nav>
    {error && <div className="evidence-alert" role="alert"><span>{error}</span><button type="button" onClick={onRefresh} disabled={loading}>Try again</button></div>}
    {graph?.revision_changed && <p className="evidence-revision" role="status">The graph changed since your last view. Showing revision {graph.revision ?? 'latest'}.</p>}
    {loading && !hasGraph && <p className="evidence-state" role="status"><RefreshCw aria-hidden="true" /> Loading the derived graph…</p>}
    {!hasGraph && !loading && !error && <section className="evidence-empty" role="status"><Network aria-hidden="true" /><div><h2>No graph records are available yet</h2><p>Saved task evidence will create estimates and relationship nodes. Nothing is fabricated for an empty profile.</p></div></section>}
    {hasGraph && <section className="evidence-layout">
      <div className="evidence-map-card">
        <div className="evidence-map-heading"><div><p className="evidence-eyebrow">Living map · {scope === 'local' ? 'Neighborhood view' : 'Whole graph'}</p><h2>{world ? `${world.name} · ${world.place}` : dimensionTitle[dimension] ?? dimension}</h2></div>
          <span>{canvasNodes.length.toLocaleString()} drawn · {visibleNodes.length.toLocaleString()} visible · {totalNodeCount.toLocaleString()} total nodes<br />{canvasEdges.length.toLocaleString()} drawn · {visibleEdges.length.toLocaleString()} visible · {totalEdgeCount.toLocaleString()} total links</span></div>
        <div className="evidence-graph-controls">
          <label className="evidence-search"><FileSearch aria-hidden="true" /><span className="evidence-sr-only">Search graph records</span><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a record…" /></label>
          <details className="evidence-type-filter"><summary>Types{selectedTypes.length ? ` · ${selectedTypes.length}` : ''}</summary><div role="group" aria-label="Filter by node type">{groupedTypes.map(type => <label key={type}><input type="checkbox" aria-label={`Show ${typeMeta[type]?.label ?? humanize(type)} nodes`} checked={selectedTypes.includes(type)} onChange={() => toggleType(type)} />{typeMeta[type]?.label ?? humanize(type)}<small>{nodes.filter(node => node.type === type).length}</small></label>)}</div></details>
          <button type="button" className={scope === 'local' ? 'is-active' : ''} onClick={focusNeighborhood} aria-pressed={scope === 'local'}><Network aria-hidden="true" /> {scope === 'local' ? 'Whole graph' : 'Focus nearby'}</button>
          {scope === 'local' && <label className="evidence-depth">Steps <select value={depth} onChange={event => setDepth(Number(event.target.value))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option><option value={4}>4</option></select></label>}
        </div>
        {Boolean(graph?.has_more) && <p className="evidence-graph-limit" role="status">The current server page contains {nodes.length.toLocaleString()} of {(graph?.filtered_node_count ?? nodes.length).toLocaleString()} matching nodes. The keyboard list includes this loaded page; search or filter to narrow the results.</p>}
        {rendererNodeOmission > 0 && <p className="evidence-graph-limit" role="status">{selectedOutsideCanvasIndex === null
          ? `The map lays out the first 5,000 of ${visibleNodes.length.toLocaleString()} visible records.`
          : `The map lays out the first 4,999 records plus the selected record from position ${(selectedOutsideCanvasIndex + 1).toLocaleString()}.`}
          {' '}{rendererNodeOmission === 1 ? 'One loaded record is' : `${rendererNodeOmission.toLocaleString()} loaded records are`} not drawn; the keyboard list can browse all {visibleNodes.length.toLocaleString()} loaded records.</p>}
        {rendererEdgeLayoutCapped && <p className="evidence-graph-limit" role="status">Node positioning uses the first 30,000 of {canvasEdges.length.toLocaleString()} relationships between drawn nodes; all of these visible relationships are still rendered.</p>}
        {visibleNodes.length ? <EvidenceGraphCanvas nodes={canvasNodes} edges={canvasEdges} selectedId={selected?.id ?? null} reduceMotion={Boolean(reduceMotion)} onSelect={id => { setSelectedId(id); setCenterId(id); }} />
          : <p className="evidence-filter-empty" role="status">No graph records match these filters. Clear a filter or search for another term.</p>}
        <p className="evidence-map-note"><Info aria-hidden="true" /> Drag empty space to pan, drag a node to pin and move it, scroll or use zoom controls. The keyboard list can browse all loaded records, including records beyond the map node limit.</p>
        <details className="evidence-accessible-list"><summary>Keyboard node list <b>{visibleNodes.length.toLocaleString()} loaded</b></summary><ul>{listNodes.map(node => <li key={node.id}><button type="button" className={selected?.id === node.id ? 'is-selected' : ''} onClick={() => { setSelectedId(node.id); setCenterId(node.id); }} aria-current={selected?.id === node.id ? 'true' : undefined}><strong>{node.label || node.id}</strong><small>{typeMeta[node.type]?.label ?? humanize(node.type)} · {node.id}</small></button></li>)}</ul>{listNodes.length < visibleNodes.length && <button type="button" className="evidence-more-nodes" onClick={() => setListLimit(value => Math.min(visibleNodes.length, value + 100))}>Show {Math.min(100, visibleNodes.length - listNodes.length)} more records</button>}</details>
      </div>
      <aside className="evidence-inspector" aria-labelledby="evidence-inspector-heading">
        <div className="evidence-inspector-heading"><span className="evidence-inspector-icon"><SelectedIcon aria-hidden="true" /></span><div><p className="evidence-eyebrow">Selected record</p><h2 id="evidence-inspector-heading">{selected ? selectedMeta?.label ?? humanize(selected.type) : 'No node selected'}</h2></div></div>
        {selected ? <>
          <p className="evidence-node-label">{selected.label}</p>
          <dl className="evidence-properties">{Object.entries(selected.properties ?? {}).filter(([key]) => key !== 'evidence_ids' && key !== 'record_ref').map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{formatValue(value)}</dd></div>)}</dl>
          {selectedRef && <section className="evidence-canonical-record" aria-labelledby="evidence-canonical-heading"><h3 id="evidence-canonical-heading">Canonical record</h3><p><strong>{humanize(selectedRef.kind)}</strong><code>{selectedRef.id}</code>{selectedRef.version && <small>Stored version: {selectedRef.version}</small>}</p>
            {resolveState === 'loading' && <p role="status">Loading saved record…</p>}{resolveState === 'error' && <p role="status">The saved record could not be resolved. Its graph reference is preserved.</p>}
            {resolvedRecord && <details className="evidence-record-details"><summary>View saved record fields</summary><dl className="evidence-properties evidence-record-properties">{Object.entries(resolvedRecord).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{formatValue(value)}</dd></div>)}</dl></details>}
            {onOpenRecord && <button type="button" onClick={() => openRef(selectedRef)}>Open canonical record <ArrowRight aria-hidden="true" /></button>}
          </section>}
          <details className="evidence-references"><summary>Evidence references · {evidence.length.toLocaleString()}</summary>{evidence.length ? <ul>{evidence.map(id => <li key={id}><code>{id}</code>{onOpenEvidenceRecord && <button type="button" onClick={() => onOpenEvidenceRecord(id)} aria-label={`Open evidence record ${id}`}><ArrowRight aria-hidden="true" /></button>}</li>)}</ul> : <p>No linked attempt references on this node.</p>}</details>
          <details className="evidence-relations"><summary>Relationships · {selectedRelationships.length.toLocaleString()}</summary>{selectedRelationships.length ? <ul>{selectedRelationships.map((edge, index) => {
            const outward = edge.source === selected.id; const otherId = outward ? edge.target : edge.source; const other = nodes.find(node => node.id === otherId);
            return <li key={`${edge.type}-${otherId}-${index}`}><span>{outward ? '→' : '←'} {humanize(edge.type)}</span><button type="button" onClick={() => other && (setSelectedId(other.id), setCenterId(other.id))} disabled={!other}>{other?.label ?? otherId}</button></li>;
          })}</ul> : <p>No recorded relationships for this node.</p>}</details>
        </> : <p className="evidence-empty-copy">Select a node in the map or keyboard list.</p>}
        <div className="evidence-mirror"><strong><Network aria-hidden="true" /> Graph source</strong><p>{mirror?.message ?? (mirror?.status === 'synced' ? 'Local graph mirror synced from SQLite evidence.' : 'The SQLite-derived graph remains canonical. The mirror is optional.')}</p><small>{mirror ? `Mirror ${humanize(mirror.status ?? (mirror.connected ? 'connected' : 'disabled'))}${mirror.source ? ` · ${mirror.source}` : ''}` : 'Mirror status not reported'}{graph?.snapshot_status ? ` · Snapshot ${humanize(graph.snapshot_status)}` : ''}</small></div>
      </aside>
    </section>}
    {hasGraph && <section className="evidence-groups" aria-labelledby="evidence-groups-heading"><div className="evidence-groups-heading"><div><p className="evidence-eyebrow">Complete recorded graph</p><h2 id="evidence-groups-heading">Nodes by type</h2></div><span>{graph?.interpretation ?? 'Relationships describe task observations and candidate strategies, not clinical traits.'}</span></div>
      <div className="evidence-group-grid">{groupedTypes.map(type => { const rows = visibleNodes.filter(node => node.type === type); if (!rows.length) return null;
        return <details key={type} className="evidence-group"><summary><span>{typeMeta[type]?.label ?? humanize(type)}</span><b>{rows.length}</b></summary><ul>{rows.slice(0, 50).map(node => <li key={node.id}><button type="button" className={selected?.id === node.id ? 'is-selected' : ''} onClick={() => setSelectedId(node.id)}><strong>{node.label || node.id}</strong><small>{node.id}</small></button></li>)}{rows.length > 50 && <li><span className="evidence-group-truncated">Showing 50 here; use the keyboard node list to browse all {rows.length} records.</span></li>}</ul></details>;
      })}</div>
    </section>}
    <p className="evidence-disclaimer">Derived from local SQLite evidence. A provisional task index is not a diagnosis, IQ score or percentile.</p>
  </main>;
}

