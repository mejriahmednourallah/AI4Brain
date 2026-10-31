import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BarChart3, Check, ChevronRight, Compass, Info, Network, RefreshCw, Sparkles, Target } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { adventureWorlds } from '../../adventure-worlds';
import './insights-page.css';

export type InsightMode = 'analytics' | 'quest';
export type InsightDimension = 'working_memory' | 'reasoning' | 'attention_inhibition' | 'flexibility' | 'planning';

export type InsightEvidenceEvent = {
  event_id: string;
  type?: string;
  created_at?: string;
  payload?: {
    exercise_id?: string;
    phase?: string;
    item_id?: string;
    interaction?: { visibility_interrupted?: boolean; hint_count?: number };
    evaluation?: Record<string, unknown>;
    [key: string]: unknown;
  };
};

export type InsightSnapshot = {
  id?: string;
  dimension: InsightDimension | string;
  index_0_100?: number | null;
  completed?: boolean;
  created_at?: string;
  evidence_count?: number;
};

export type InsightCoverageRow = {
  dimension: InsightDimension | string;
  status: string;
  index_0_100: number | null;
  evidence_count: number;
  required_evidence_count: number;
  uncertainty_status: string | null;
  evidence_ids?: string[];
};

export type InsightDimensionEstimate = {
  status?: string;
  index_0_100?: number | null;
  selection_index_0_100?: number | null;
  evidence_count?: number;
  required_evidence_count?: number;
  uncertainty_status?: string | null;
  evidence_ids?: string[];
  correct?: number;
  total_positions?: number;
  correct_positions?: number;
  longest_fully_correct_span?: number;
  go_hits?: number;
  go_omissions?: number;
  no_go_correct_rejections?: number;
  no_go_commissions?: number;
  median_response_time_ms?: number | null;
  switch_accuracy?: number | null;
  repeat_accuracy?: number | null;
  error_previous_rule?: number;
  completed_puzzles?: number;
  excess_moves?: number | null;
  legal_moves?: number;
  illegal_moves?: number;
  undo_count?: number;
  restart_count?: number;
  reassessment_evidence_count?: number;
  response_times_ms?: number[];
  [key: string]: unknown;
};

export type InsightPlanStep = {
  step_id?: string;
  dimension_id?: string;
  exercise_type_id?: string;
  status?: string;
  difficulty_tier?: string;
  tier?: string;
  estimated_time_minutes?: number | null;
  strategy_id?: string | null;
  selection_reason?: string | null;
  source_evidence_ids?: string[];
};

export type InsightDashboardSource = {
  learner_id?: string;
  preferences?: { dashboard_mode?: string; goal_dimension?: string | null } | null;
  profile?: {
    dimensions?: Record<string, InsightDimensionEstimate>;
    snapshots?: InsightSnapshot[];
    interpretation?: string;
  } | null;
  events?: InsightEvidenceEvent[];
  plan?: { latest?: { steps?: InsightPlanStep[]; plan?: { steps?: InsightPlanStep[] } } | null; history?: unknown[] } | null;
  activity?: {
    window_days?: number;
    start_date?: string;
    end_date?: string;
    buckets?: Array<{ date: string; count: number }>;
    total_valid_trials?: number;
  } | null;
  participation?: {
    practice_trial_count?: number;
    training_trial_count?: number;
    assisted_training_trial_count?: number;
    xp?: number;
    level?: number;
    xp_into_level?: number;
    xp_to_next_level?: number;
    interpretation?: string;
  } | null;
  task_coverage?: {
    assessed_count?: number;
    total_count?: number;
    dimensions?: InsightCoverageRow[];
  } | null;
  collaboration?: {
    score?: {
      score_0_100?: number | null;
      status?: string;
      interpretation?: string;
      dimensions?: Record<string, { score_0_100: number | null; weight_percent: number; evaluated_opportunity_count: number }>;
    };
    opportunity_count?: number;
    evaluated_opportunity_count?: number;
    open_opportunity_count?: number;
  } | null;
  milestones?: Array<{
    id: string;
    title: string;
    description: string;
    achieved: boolean;
    progress_current: number;
    progress_target: number;
    evidence_ids?: string[];
  }> | null;
};

export type InsightsPageProps = {
  dashboard: InsightDashboardSource | null;
  mode: InsightMode;
  loading: boolean;
  error: string | null;
  selectedDimension?: string;
  onSelectDimension?: (dimension: string) => void;
  onModeChange: (mode: InsightMode) => void;
  onRefresh: () => void;
  onPlan: () => void;
  onPractice: () => void;
  onBrain: () => void;
  onCollaboration: () => void;
};

const dimensions: readonly InsightDimension[] = ['working_memory', 'reasoning', 'attention_inhibition', 'flexibility', 'planning'];
const dimensionTitle: Record<string, string> = {
  working_memory: 'Working memory',
  reasoning: 'Reasoning',
  attention_inhibition: 'Attention & inhibition',
  flexibility: 'Cognitive flexibility',
  planning: 'Planning',
};
const exerciseByDimension: Record<string, string> = {
  working_memory: 'EX-01', reasoning: 'EX-02', attention_inhibition: 'EX-03', flexibility: 'EX-04', planning: 'EX-05',
};

// Only genuine finite numbers (or non-empty numeric strings) are measurements.
// Number(null) and Number('') are 0, which must never become a fabricated score.
function number(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
function rounded(value: unknown, suffix = '%'): string {
  const parsed = number(value);
  if (parsed === null) return 'Unavailable';
  return `${Number.isInteger(parsed) ? parsed : parsed.toFixed(1)}${suffix}`;
}
function evidenceProgress(row: InsightCoverageRow): string {
  const required = number(row.required_evidence_count);
  const count = number(row.evidence_count);
  if (required === null || required <= 0 || count === null) return 'Evidence unavailable';
  return `${count} / ${required} evidence items`;
}
function evidenceShort(row: InsightCoverageRow): string {
  const required = number(row.required_evidence_count);
  const count = number(row.evidence_count);
  if (required === null || required <= 0 || count === null) return 'Evidence unavailable';
  return `${count}/${required}`;
}
function humanize(value: unknown): string {
  return String(value ?? '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/^\w/, letter => letter.toUpperCase());
}
function uncertaintyLabel(value: string | null | undefined): string {
  if (!value) return 'Uncertainty unavailable';
  if (value === 'PRELIMINARY_HIGH_UNCERTAINTY') return 'Preliminary · high uncertainty';
  if (value === 'INCOMPLETE_BASELINE') return 'Incomplete baseline · unassessed';
  if (value.startsWith('NOT_')) return 'Not enough evidence';
  return humanize(value);
}
function statusLabel(row: InsightCoverageRow | undefined, mode: InsightMode): string {
  if (!row) return 'Coverage unavailable';
  if (row.status === 'ASSESSED') return mode === 'quest' ? 'Explored' : 'Assessed';
  if (row.status === 'IN_PROGRESS') return 'In progress';
  return 'Not assessed';
}
function dimensionForExercise(exerciseId: string | undefined): string | null {
  return Object.entries(exerciseByDimension).find(([, exercise]) => exercise === exerciseId)?.[0] ?? null;
}

function RadarChart({ rows }: { rows: InsightCoverageRow[] }) {
  const centerX = 210;
  const centerY = 175;
  const radius = 100;
  // Unassessed tasks must not be drawn at zero: they get no marker and no
  // connection, so missing evidence cannot read as a measured score.
  const axes = rows.map((row, index) => {
    const angle = -Math.PI / 2 + index * (Math.PI * 2 / 5);
    const value = row.status === 'ASSESSED' ? number(row.index_0_100) : null;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return {
      row, angle, value, cos, sin,
      axisX: centerX + cos * radius,
      axisY: centerY + sin * radius,
      x: centerX + cos * radius * (value === null ? 0 : Math.min(100, Math.max(0, value)) / 100),
      y: centerY + sin * radius * (value === null ? 0 : Math.min(100, Math.max(0, value)) / 100),
    };
  });
  const measured = axes.filter(axis => axis.value !== null);
  const path = measured.map(axis => `${axis.x},${axis.y}`).join(' ');
  const description = rows.map(row => `${dimensionTitle[row.dimension] ?? row.dimension}: ${row.status === 'ASSESSED' ? rounded(row.index_0_100) : 'not assessed'}`).join('; ');
  return <svg className="insights-radar" viewBox="0 0 420 340" role="img" aria-label={`Task-specific estimates. ${description}`}>
    {[25, 50, 75, 100].map(level => <polygon key={level} className="insights-radar-ring" points={rows.map((_, index) => {
      const angle = -Math.PI / 2 + index * (Math.PI * 2 / 5);
      return `${centerX + Math.cos(angle) * radius * level / 100},${centerY + Math.sin(angle) * radius * level / 100}`;
    }).join(' ')} />)}
    {axes.map(axis => <line key={axis.row.dimension} className={`insights-radar-axis${axis.value === null ? ' is-unassessed' : ''}`} x1={centerX} y1={centerY} x2={axis.axisX} y2={axis.axisY} />)}
    {measured.length >= 3 && <polygon className="insights-radar-area" points={path} />}
    {measured.length === 1 && <line className="insights-radar-area is-partial" x1={centerX} y1={centerY} x2={measured[0].x} y2={measured[0].y} />}
    {measured.length === 2 && <polyline className="insights-radar-area is-partial" points={path} />}
    {measured.map(axis => <circle key={`marker-${axis.row.dimension}`} className="insights-radar-marker is-assessed" cx={axis.x} cy={axis.y} r="5" />)}
    {axes.filter(axis => axis.value === null).map(axis => <circle key={`unassessed-${axis.row.dimension}`} className="insights-radar-unassessed-mark" cx={centerX + axis.cos * radius * .34} cy={centerY + axis.sin * radius * .34} r="3.5" />)}
    {axes.map(axis => <text key={`label-${axis.row.dimension}`} className={`insights-radar-label${axis.value === null ? ' is-unassessed' : ''}`} x={axis.axisX} y={axis.axisY} textAnchor={axis.axisX < centerX - 2 ? 'end' : axis.axisX > centerX + 2 ? 'start' : 'middle'} dominantBaseline={axis.axisY < centerY ? 'auto' : 'hanging'}>{dimensionTitle[axis.row.dimension] ?? axis.row.dimension}{axis.value === null ? ' · not assessed' : ''}</text>)}
    <text className="insights-radar-scale" x={centerX} y={centerY - 6} textAnchor="middle">100</text>
    <text className="insights-radar-scale" x={centerX} y={centerY + 14} textAnchor="middle">0</text>
    {measured.length === 0 && <text className="insights-radar-empty" x={centerX} y={centerY + 2} textAnchor="middle">No assessed task yet</text>}
  </svg>;
}

function HistorySparkline({ dimension, snapshots }: { dimension: string; snapshots: InsightSnapshot[] }) {
  const rows = snapshots.filter(snapshot => snapshot.dimension === dimension && snapshot.completed && number(snapshot.index_0_100) !== null)
    .sort((a, b) => String(a.created_at ?? '').localeCompare(String(b.created_at ?? '')));
  if (!rows.length) return <p className="insights-empty-copy">No completed task snapshots yet. Saved history will appear after a full baseline.</p>;
  const points = rows.map((row, index) => {
    const x = rows.length === 1 ? 260 : 20 + index * 480 / (rows.length - 1);
    const y = 120 - (number(row.index_0_100) ?? 0) * 0.9;
    return { x, y, value: number(row.index_0_100) ?? 0, date: row.created_at ?? '' };
  });
  const latest = points[points.length - 1];
  // A single saved snapshot has no line to draw. Show a compact value strip
  // instead of a full-height chart with one lonely dot.
  if (points.length === 1) {
    return <div className="insights-history is-single">
      <div className="insights-history-single">
        <span className="insights-history-single-dot" aria-hidden="true" />
        <div><strong>{rounded(latest.value)}</strong><span>First completed snapshot · {dimensionTitle[dimension] ?? dimension}</span></div>
      </div>
      <small className="insights-history-hint">A trend line appears after the next saved snapshot.</small>
    </div>;
  }
  return <div className="insights-history">
    <svg viewBox="0 0 520 150" role="img" aria-label={`${dimensionTitle[dimension]} saved snapshot history. Latest ${rounded(latest.value)} across ${rows.length} completed snapshots.`}>
      {[0, 50, 100].map(level => <line key={level} className="insights-history-grid" x1="20" y1={120 - level * .9} x2="500" y2={120 - level * .9} />)}
      <polyline className="insights-history-line" points={points.map(point => `${point.x},${point.y}`).join(' ')} />
      {points.map((point, index) => <circle key={index} className="insights-history-dot" cx={point.x} cy={point.y} r="4"><title>{`${point.date}: ${rounded(point.value)}`}</title></circle>)}
    </svg>
    <div className="insights-history-meta"><strong>{rounded(latest.value)}</strong><span>Latest of {rows.length} completed snapshots</span></div>
  </div>;
}

function observations(dimension: string, estimate: InsightDimensionEstimate): Array<{ label: string; value: string }> {
  if (dimension === 'working_memory') return [
    { label: 'Correct positions', value: estimate.correct_positions == null || estimate.total_positions == null ? 'Unavailable' : `${estimate.correct_positions} / ${estimate.total_positions}` },
    { label: 'Longest fully correct span', value: estimate.longest_fully_correct_span == null ? 'Unavailable' : String(estimate.longest_fully_correct_span) },
  ];
  if (dimension === 'attention_inhibition') return [
    { label: 'Go hits / omissions', value: `${estimate.go_hits ?? '—'} / ${estimate.go_omissions ?? '—'}` },
    { label: 'Correct rejections / commissions', value: `${estimate.no_go_correct_rejections ?? '—'} / ${estimate.no_go_commissions ?? '—'}` },
    { label: 'Median hit response time', value: estimate.median_response_time_ms == null ? 'Unavailable' : `${Math.round(Number(estimate.median_response_time_ms))} ms` },
  ];
  if (dimension === 'flexibility') return [
    { label: 'Switch accuracy', value: rounded(estimate.switch_accuracy) },
    { label: 'Repeat accuracy', value: rounded(estimate.repeat_accuracy) },
    { label: 'Previous-rule errors', value: estimate.error_previous_rule == null ? 'Unavailable' : String(estimate.error_previous_rule) },
  ];
  if (dimension === 'planning') return [
    { label: 'Puzzles completed', value: estimate.completed_puzzles == null ? 'Unavailable' : String(estimate.completed_puzzles) },
    { label: 'Excess moves', value: estimate.excess_moves == null ? 'Unavailable' : String(estimate.excess_moves) },
    { label: 'Legal / blocked moves', value: `${estimate.legal_moves ?? '—'} / ${estimate.illegal_moves ?? '—'}` },
    { label: 'Undo / restart', value: `${estimate.undo_count ?? '—'} / ${estimate.restart_count ?? '—'}` },
  ];
  const times = Array.isArray(estimate.response_times_ms) ? estimate.response_times_ms.map(Number).filter(Number.isFinite) : [];
  const median = times.length ? [...times].sort((a, b) => a - b)[Math.floor(times.length / 2)] : null;
  return [
    { label: 'Correct items', value: estimate.correct == null ? 'Unavailable' : `${estimate.correct} / 6` },
    { label: 'Median response time', value: median == null ? 'Unavailable' : `${Math.round(median)} ms` },
  ];
}

function planSteps(dashboard: InsightDashboardSource): InsightPlanStep[] {
  return dashboard.plan?.latest?.steps ?? dashboard.plan?.latest?.plan?.steps ?? [];
}

export function InsightsPage({ dashboard, mode, loading, error, selectedDimension, onSelectDimension, onModeChange, onRefresh, onPlan, onPractice, onBrain, onCollaboration }: InsightsPageProps) {
  const reduceMotion = useReducedMotion();
  const coverageRows = dashboard?.task_coverage?.dimensions ?? [];
  const byDimension = useMemo(() => Object.fromEntries(coverageRows.map(row => [row.dimension, row])), [coverageRows]);
  const preferred = selectedDimension && dimensions.includes(selectedDimension as InsightDimension) ? selectedDimension
    : dashboard?.preferences?.goal_dimension && dimensions.includes(dashboard.preferences.goal_dimension as InsightDimension) ? dashboard.preferences.goal_dimension
      : dimensions[0];
  const [internalSelected, setInternalSelected] = useState<string>(preferred);
  const selected = selectedDimension && dimensions.includes(selectedDimension as InsightDimension) ? selectedDimension : internalSelected;
  const select = (dimension: string) => {
    if (onSelectDimension) onSelectDimension(dimension);
    else setInternalSelected(dimension);
  };
  useEffect(() => {
    if (!selectedDimension) setInternalSelected(preferred);
    // Follow the saved goal when data first arrives; user selection still wins afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferred]);
  const rows = dimensions.map(dimension => {
    const row = byDimension[dimension];
    if (!row) return { dimension, status: 'NOT_ASSESSED', index_0_100: null, evidence_count: 0, required_evidence_count: 0, uncertainty_status: null };
    return { ...row, dimension: String(row.dimension) };
  });
  const selectedRow = rows.find(row => row.dimension === selected) ?? rows[0];
  const estimates = dashboard?.profile?.dimensions ?? {};
  const selectedEstimate = estimates[selectedRow.dimension] ?? {};
  const snapshots = dashboard?.profile?.snapshots ?? [];
  const steps = dashboard ? planSteps(dashboard) : [];
  const selectedStep = steps.find(step => (step.dimension_id ?? dimensionForExercise(step.exercise_type_id)) === selectedRow.dimension);
  const world = adventureWorlds.find(item => item.dimension === selectedRow.dimension);
  const activity = dashboard?.activity;
  const buckets = activity?.buckets ?? [];
  const activeDayCount = buckets.filter(bucket => (bucket.count ?? 0) > 0).length;
  const participation = dashboard?.participation;
  const collaboration = dashboard?.collaboration;
  const preferences = dashboard?.preferences;
  const goalRow = preferences?.goal_dimension ? byDimension[preferences.goal_dimension] : undefined;
  const milestones = Array.isArray(dashboard?.milestones) ? dashboard?.milestones ?? [] : [];
  const assessed = dashboard?.task_coverage?.assessed_count;
  const total = dashboard?.task_coverage?.total_count;
  const events = dashboard?.events ?? [];
  const hasDashboard = dashboard !== null;
  const retainedError = Boolean(error && hasDashboard);
  const title = mode === 'quest' ? 'Your practice path, grounded in evidence' : 'A clearer picture, one task at a time';
  const intro = mode === 'quest'
    ? 'Every branch reflects saved task evidence. Participation rewards show engagement, never cognitive ability.'
    : 'Five task-specific estimates with visible evidence, uncertainty and history. Unassessed tasks are never shown as zero.';

  return <main className={`insights-rebuild insights-rebuild-${mode}`} aria-labelledby="insights-title">
    <section className="insights-hero">
      <img className="insights-hero-art" src="/art/adventure/home-hero-plate.png" alt="" aria-hidden="true" />
      <div className="insights-hero-copy">
        <p className="insights-eyebrow">{mode === 'quest' ? 'Your learning quest' : 'Your learning profile'}</p>
        <h1 id="insights-title">{title}</h1>
        <p>{intro}</p>
        <div className="insights-mode-switch" role="group" aria-label="Insights presentation">
          <button type="button" className={mode === 'analytics' ? 'is-selected' : ''} aria-pressed={mode === 'analytics'} onClick={() => onModeChange('analytics')}><BarChart3 aria-hidden="true" /> Analytics</button>
          <button type="button" className={mode === 'quest' ? 'is-selected' : ''} aria-pressed={mode === 'quest'} onClick={() => onModeChange('quest')}><Compass aria-hidden="true" /> Quest</button>
        </div>
      </div>
      <div className="insights-summary" aria-label="Saved summary">
        <div><span>Task families</span><strong>{assessed == null || total == null ? 'Unavailable' : `${assessed} / ${total}`}</strong><small>assessed, not zero-filled</small></div>
        <div><span>Evidence records</span><strong>{hasDashboard ? events.length : 'Unavailable'}</strong><small>saved attempts</small></div>
        <div><span>{mode === 'quest' ? 'Participation XP' : 'Collaboration'}</span><strong>{mode === 'quest' ? (participation?.xp == null ? 'Unavailable' : participation.xp.toLocaleString()) : (collaboration?.score?.score_0_100 == null ? 'Not enough evidence' : rounded(collaboration.score.score_0_100, ' / 100'))}</strong><small>{mode === 'quest' ? 'engagement only' : 'interaction evidence'}</small></div>
      </div>
      {error && <div className={`insights-alert${retainedError ? ' is-retained' : ''}`} role="alert"><span>{retainedError ? 'Saved insights could not refresh. Showing the last loaded data.' : error}</span><button type="button" onClick={onRefresh} disabled={loading}>{loading ? 'Retrying…' : 'Try again'}</button></div>}
      {loading && <p className="insights-loading" role="status"><RefreshCw aria-hidden="true" /> {hasDashboard ? 'Refreshing saved insights…' : 'Loading saved insights…'}</p>}
      {!hasDashboard && !loading && !error && <div className="insights-unavailable" role="status"><Info aria-hidden="true" /><div><strong>Insights are not loaded yet</strong><p>Start a local session and complete task evidence to populate this view.</p></div><button type="button" onClick={onRefresh}>Load insights</button></div>}
    </section>

    {hasDashboard && <>
      <section className={`insights-world-strip insights-world-strip-${mode}`} aria-label={mode === 'quest' ? 'Practice quest worlds' : 'Task evidence across five worlds'}>
        {mode === 'quest' ? <div className="insights-quest-map" role="group" aria-label="Choose a world on your practice quest">
          <svg className="insights-quest-path" viewBox="0 0 1000 520" preserveAspectRatio="none" aria-hidden="true"><path d="M65 315 C145 330 150 175 245 155 S350 320 445 330 S565 190 650 190 S800 355 930 325" /></svg>
          {rows.map((row, index) => {
            const worldItem = adventureWorlds.find(item => item.dimension === row.dimension);
            if (!worldItem) return null;
            return <button type="button" key={row.dimension} className={`insights-quest-stop insights-quest-stop-${index + 1}${selected === row.dimension ? ' is-selected' : ''}`} aria-pressed={selected === row.dimension} onClick={() => select(row.dimension)} aria-label={`${worldItem.name}, ${statusLabel(row, mode)}, ${evidenceShort(row)}`}>
              <span className="insights-quest-art"><img src={worldItem.image} alt="" loading="lazy" /></span>
              <span className="insights-quest-node" aria-hidden="true">{row.status === 'ASSESSED' ? <Check /> : index + 1}</span>
              <span className="insights-quest-copy"><strong>{worldItem.name}</strong><small>{worldItem.place}</small><small>{statusLabel(row, mode)} · {evidenceShort(row)}</small></span>
            </button>;
          })}
        </div> : <div className="insights-world-track" role="group" aria-label="Choose a task family to inspect">
          {rows.map((row, index) => {
            const worldItem = adventureWorlds.find(item => item.dimension === row.dimension);
            if (!worldItem) return null;
            return <button type="button" key={row.dimension} className={`insights-world-stop${selected === row.dimension ? ' is-selected' : ''}`} aria-pressed={selected === row.dimension} onClick={() => select(row.dimension)} aria-label={`${worldItem.name}, ${statusLabel(row, mode)}, ${evidenceShort(row)}`}>
              <span className="insights-world-art"><img src={worldItem.image} alt="" loading="lazy" /></span>
              <span className="insights-world-node" aria-hidden="true">{index + 1}</span>
              <strong>{worldItem.name}</strong>
              <span className="insights-world-place">{worldItem.place}</span>
              <small>{statusLabel(row, mode)}</small>
              <small>{evidenceShort(row)}</small>
            </button>;
          })}
        </div>}
      </section>
      <section className="insights-profile" aria-labelledby="insights-profile-heading">
        <div className="insights-section-heading"><div><p className="insights-eyebrow">{mode === 'quest' ? 'The five branches' : 'Task-specific estimates'}</p><h2 id="insights-profile-heading">{mode === 'quest' ? 'Choose a branch to inspect' : 'Choose a task to inspect'}</h2></div><span className="insights-qualifier"><Info aria-hidden="true" /> Indices are not comparable across tasks</span></div>
        <div className="insights-profile-grid">
          <div className="insights-profile-visual">
            {mode === 'analytics' && <RadarChart rows={rows} />}
            <div className="insights-dimension-list" aria-label="Task families">
              {rows.map((row, index) => {
                const worldItem = adventureWorlds.find(item => item.dimension === row.dimension);
                const assessedRow = row.status === 'ASSESSED' && number(row.index_0_100) !== null;
                return <button type="button" key={row.dimension} className={`insights-dimension${selected === row.dimension ? ' is-selected' : ''}`} aria-pressed={selected === row.dimension}                 onClick={() => select(row.dimension)} aria-label={`${dimensionTitle[row.dimension] ?? row.dimension}: ${statusLabel(row, mode)}. ${evidenceProgress(row)}.`}>
                  <span className="insights-dimension-index">{index + 1}</span>
                  <img src={worldItem?.image} alt="" loading="lazy" />
                                  <span className="insights-dimension-copy"><strong>{dimensionTitle[row.dimension] ?? row.dimension}</strong><small>{statusLabel(row, mode)} · {evidenceShort(row)}</small></span>
                  <b>{assessedRow ? rounded(row.index_0_100) : '—'}</b>
                </button>;
              })}
            </div>
          </div>

          <aside className="insights-detail" aria-labelledby="insights-detail-heading">
            <div className="insights-detail-art" aria-hidden="true"><img src={world?.image} alt="" /></div>
            <div className="insights-detail-heading"><span className="insights-detail-kicker">{mode === 'quest' ? 'Selected branch' : 'Selected task'}</span><h2 id="insights-detail-heading">{dimensionTitle[selectedRow.dimension] ?? selectedRow.dimension}</h2><p>{world?.place}</p></div>
            <div className="insights-detail-score">
              <strong>{selectedRow.status === 'ASSESSED' ? rounded(selectedRow.index_0_100) : selectedRow.status === 'IN_PROGRESS' ? 'In progress' : 'Not assessed'}</strong>
              <span>{evidenceProgress(selectedRow)}</span>
              <small>{uncertaintyLabel(selectedRow.uncertainty_status)}</small>
            </div>
            {number(selectedRow.required_evidence_count) !== null && Number(selectedRow.required_evidence_count) > 0 && number(selectedRow.evidence_count) !== null
              ? <div className="insights-detail-bar" role="progressbar" aria-label={`${dimensionTitle[selectedRow.dimension] ?? selectedRow.dimension} evidence coverage`} aria-valuemin={0} aria-valuemax={Number(selectedRow.required_evidence_count)} aria-valuenow={Math.min(Number(selectedRow.evidence_count), Number(selectedRow.required_evidence_count))}><span style={{ width: `${Math.min(100, Number(selectedRow.evidence_count) / Number(selectedRow.required_evidence_count) * 100)}%` }} /></div>
              : <p className="insights-detail-unavailable" role="status">Evidence coverage unavailable.</p>}
            <div className="insights-detail-plan">
              <span><Target aria-hidden="true" /> Saved plan</span>
              <strong>{selectedStep ? `${humanize(selectedStep.status ?? 'planned')}${(selectedStep.difficulty_tier ?? selectedStep.tier) ? ` · ${humanize(selectedStep.difficulty_tier ?? selectedStep.tier)}` : ''}` : 'No saved step for this task'}</strong>
              {selectedStep?.estimated_time_minutes != null && <small>{selectedStep.estimated_time_minutes} min estimate</small>}
            </div>
            <section className="insights-observations" aria-labelledby="insights-observations-heading">
              <h3 id="insights-observations-heading">Saved observations</h3>
              <dl>{observations(selectedRow.dimension, selectedEstimate).map(row => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl>
            </section>
            <HistorySparkline dimension={selectedRow.dimension} snapshots={snapshots} />
            <div className="insights-detail-actions">
              <button type="button" className="insights-button insights-button-primary" onClick={onPractice}>Open practice <ArrowRight aria-hidden="true" /></button>
              <button type="button" className="insights-button insights-button-secondary" onClick={onBrain}><Network aria-hidden="true" /> Evidence graph</button>
            </div>
          </aside>
        </div>
      </section>

      <section className="insights-insights" aria-label={mode === 'quest' ? 'Participation and goals' : 'Saved focus and collaboration'}>
        <article className="insights-card insights-focus">
          <p className="insights-card-kicker">Saved focus</p>
          <h2>{preferences ? (preferences.goal_dimension ? dimensionTitle[preferences.goal_dimension] ?? 'Saved focus' : 'No focus chosen') : 'Preferences unavailable'}</h2>
          {preferences?.goal_dimension ? <>
            <p className="insights-card-lead">{goalRow ? `${statusLabel(goalRow, mode)} · ${evidenceProgress(goalRow)}` : 'Coverage unavailable'}</p>
            <p className="insights-card-copy">{goalRow ? uncertaintyLabel(goalRow.uncertainty_status) : 'Focus coverage is unavailable.'}</p>
          </> : <p className="insights-card-copy">{preferences ? 'Choose a focus area in your plan to prioritize it in recommendations.' : 'Saved preference data is unavailable.'}</p>}
          <button type="button" className="insights-link" onClick={onPlan}>{preferences?.goal_dimension ? 'Review focus' : 'Choose a focus'} <ChevronRight aria-hidden="true" /></button>
        </article>
        <article className="insights-card">
          <p className="insights-card-kicker">Collaboration</p>
          <h2>{collaboration?.score?.score_0_100 == null ? 'Not yet available' : `${rounded(collaboration.score.score_0_100, ' / 100')}`}</h2>
          <p className="insights-card-lead">{collaboration?.score?.status === 'PRELIMINARY_HIGH_UNCERTAINTY' ? 'Preliminary · high uncertainty' : collaboration ? 'Not enough collaboration evidence yet' : 'Collaboration summary unavailable'}</p>
          <p className="insights-card-copy">{collaboration?.score?.interpretation ?? 'Complete eligible collaboration actions to build this interaction summary.'}</p>
          {collaboration && <p className="insights-card-meta">{collaboration.opportunity_count ?? 0} opportunities · {collaboration.evaluated_opportunity_count ?? 0} evaluated · {collaboration.open_opportunity_count ?? 0} open</p>}
          <button type="button" className="insights-link" onClick={onCollaboration}>Review collaboration <ChevronRight aria-hidden="true" /></button>
        </article>
        <article className="insights-card insights-activity">
          <p className="insights-card-kicker">Recent activity</p>
          <h2>{activity ? `${activity.total_valid_trials ?? 0} valid trials` : 'Activity unavailable'}</h2>
          <p className="insights-card-copy">{activity ? `${activity.window_days ?? 35}-day window · ${activeDayCount} active day${activeDayCount === 1 ? '' : 's'} · interrupted and sample attempts excluded` : 'Daily activity is unavailable.'}</p>
          {buckets.length > 0 && <div className="insights-heatmap" role="img" aria-label={`Daily valid completed activity from ${activity?.start_date ?? ''} to ${activity?.end_date ?? ''}. ${activity?.total_valid_trials ?? 0} valid trials across ${activeDayCount} active days.`}>{buckets.map(bucket => <span key={bucket.date} title={`${bucket.date}: ${bucket.count} valid trials`} data-level={Math.min(4, bucket.count)} />)}</div>}
          {buckets.length > 0 && <div className="insights-heatmap-legend" aria-hidden="true"><span>Fewer trials</span><i data-level="0" /><i data-level="1" /><i data-level="2" /><i data-level="3" /><i data-level="4" /><span>More trials</span></div>}
          {activity && <div className="insights-heatmap-labels"><span>{activity.start_date}</span><span>{activity.end_date}</span></div>}
        </article>
      </section>

      <section className="insights-path" aria-labelledby="insights-path-heading">
        <div className="insights-section-heading"><div><p className="insights-eyebrow">{mode === 'quest' ? 'Next on your path' : 'Recommended next'}</p><h2 id="insights-path-heading">A plan grounded in saved evidence</h2></div><button type="button" className="insights-link" onClick={onPlan}>Review plan <ChevronRight aria-hidden="true" /></button></div>
        {steps.length ? <ol className="insights-step-list">{steps.slice(0, 4).map((step, index) => <li key={step.step_id ?? `${step.dimension_id}-${index}`}><span>{index + 1}</span><div><strong>{dimensionTitle[step.dimension_id ?? dimensionForExercise(step.exercise_type_id) ?? ''] ?? step.exercise_type_id ?? 'Planned activity'}</strong><small>{humanize(step.status ?? 'planned')} · {step.estimated_time_minutes ?? '—'} min · {step.difficulty_tier ?? step.tier ?? 'Tier unavailable'}</small>{step.selection_reason && <p>{humanize(step.selection_reason)}</p>}</div></li>)}</ol>
          : <p className="insights-empty-copy">No saved plan steps are available yet. Update your plan to request a policy selection.</p>}
        <div className="insights-path-actions"><button type="button" className="insights-button insights-button-primary" onClick={onPractice}>Open practice <ArrowRight aria-hidden="true" /></button><button type="button" className="insights-button insights-button-secondary" onClick={onPlan}>Plan and focus</button></div>
      </section>

      {mode === 'quest' && <section className="insights-milestones" aria-labelledby="insights-milestones-heading">
        <div className="insights-section-heading"><div><p className="insights-eyebrow">Participation milestones</p><h2 id="insights-milestones-heading">Evidence gathering, not a cognitive score</h2></div><span className="insights-xp"><Sparkles aria-hidden="true" /> {number(participation?.xp) === null ? 'XP unavailable' : `${participation?.xp} XP`}</span></div>
        {Array.isArray(dashboard.milestones) ? (milestones.length ? <div className="insights-milestone-list">{milestones.map(milestone => {
          const target = Math.max(0, number(milestone.progress_target) ?? 0);
          const current = Math.max(0, number(milestone.progress_current) ?? 0);
          const percent = target > 0 ? Math.min(100, current / target * 100) : 0;
          return <motion.article key={milestone.id} className={`insights-milestone${milestone.achieved ? ' is-achieved' : ''}`} initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .35 }}>
            <span className="insights-milestone-mark" aria-hidden="true">{milestone.achieved ? <Check /> : <Sparkles />}</span>
            <div><strong>{milestone.title}</strong><p>{milestone.description}</p><div className="insights-milestone-progress" role="progressbar" aria-label={`${milestone.title} progress`} aria-valuemin={0} aria-valuemax={Math.max(1, target)} aria-valuenow={Math.min(current, Math.max(1, target))}><span style={{ width: `${percent}%` }} /></div><small>{target > 0 ? `${current} / ${target}` : 'Progress unavailable'} · {milestone.achieved ? 'Recorded' : 'In progress'}</small>{milestone.evidence_ids?.length ? <details><summary>Evidence references ({milestone.evidence_ids.length})</summary><div>{milestone.evidence_ids.map(id => <code key={id}>{id.slice(0, 8)}</code>)}</div></details> : null}</div>
          </motion.article>;
        })}</div> : <p className="insights-empty-copy">No participation milestones are recorded yet.</p>) : <p className="insights-empty-copy">Milestones are unavailable from the saved dashboard.</p>}
      </section>}

      <p className="insights-disclaimer">{dashboard.profile?.interpretation ?? 'Task indices are preliminary, task-specific and not comparable across families. Participation XP is not a cognitive measure.'}</p>
    </>}
  </main>;
}
