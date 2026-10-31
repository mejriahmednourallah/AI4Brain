import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, ChevronDown, Clock3, Compass, FileText, Info, Sparkles } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { adventureWorlds } from '../../adventure-worlds';
import './plan-page.css';

export type PlanDimension = 'working_memory' | 'reasoning' | 'attention_inhibition' | 'flexibility' | 'planning';

export type CoreActivityId = 'EX-01' | 'EX-02' | 'EX-03' | 'EX-04' | 'EX-05';
export type ActivityRef =
  | { kind: 'core'; id: CoreActivityId; version: string; exerciseId?: CoreActivityId; phase?: 'baseline' | 'training' }
  | { kind: 'hybrid'; id: `HY-0${1|2|3|4|5|6}`; version: string; config_version?: string }
  | { kind: 'crystal'; id: 'CRYSTAL'; version: string; config_version?: string };

export interface PlanStep {
  step_id?: string | null;
  dimension_id?: string | null;
  exercise_type_id?: string | null;
  action?: string | null;
  difficulty_tier?: string | null;
  tier?: string | null;
  strategy_id?: string | null;
  selection_reason?: string | null;
  source_evidence_ids?: string[] | null;
  estimated_time_minutes?: number | null;
  status?: string | null;
  activity_ref?: ActivityRef | null;
  label?: string | null;
  mode?: string | null;
  launch_tier?: string | null;
  estimate_source?: string | null;
  duration_estimate?: { minutes?: number | null; confidence?: string | null; source?: string | null } | null;
  estimate_sample_size?: number | null;
  execution_status?: string | null;
  launch_ref?: { attempt_id?: string; kind?: string; version?: string } | null;
  contributions?: { baseline_indices?: boolean; ex_difficulty_tiers?: boolean; participation_xp?: boolean } | null;
  family_relevance?: string[] | null;
  assistance_windows?: string[] | null;
}

export interface SavedPlanVersion {
  plan?: SavedPlanVersion | null;
  plan_id?: string | null;
  plan_version?: string | null;
  created_at?: string | null;
  policy_version?: string | null;
  version?: string | null;
  estimated_time_minutes?: number | null;
  budget_minutes?: number | null;
  goal?: string | null;
  rationale?: string | null;
  reason_codes?: string[] | null;
  evidence_ids?: string[] | null;
  steps?: PlanStep[] | null;
}

export interface PlanHistoryDTO extends SavedPlanVersion {
  learner_id?: string;
  latest?: SavedPlanVersion | null;
  plan?: SavedPlanVersion | null;
  history?: SavedPlanVersion[] | null;
}

export interface PlanRecommendationDTO {
  id?: string;
  event_id?: string | null;
  created_at?: string | null;
  action: 'complete_baseline' | 'additional_assessment' | 'targeted_training' | 'reasoning_training' | string;
  exercise_id?: string | null;
  tier?: string | null;
  reason_codes?: string[] | null;
  evidence_ids?: string[] | null;
  policy_version?: string | null;
  rationale?: string | null;
  selected_strategy_id?: string | null;
  features?: Record<string, unknown> | null;
  alternatives?: Array<{ strategy_id?: string | null; exercise_id?: string | null; dimension_id?: string | null; action?: string | null; rationale?: string | null }> | null;
  budget_minutes?: number | null;
}

export interface PlanSampleScenario {
  sample_id?: string | null;
  label?: string | null;
  selected_dimension?: string | null;
  decision?: {
    action?: string | null;
    tier?: string | null;
    exercise_id?: string | null;
    rationale?: string | null;
    reason_codes?: string[] | null;
    evidence_ids?: string[] | null;
    policy_version?: string | null;
  } | null;
}

export interface PlanSamplesDTO {
  sample_data?: boolean;
  persisted?: boolean;
  scenarios?: PlanSampleScenario[] | null;
}

export interface PlanPageProps {
  budget: number;
  setBudget: (minutes: number) => void;
  goal: string;
  setGoal: (dimension: string) => void;
  loading: boolean;
  error: string | null;
  plan: PlanHistoryDTO | null;
  recommendation: PlanRecommendationDTO | null;
  samples: PlanSamplesDTO | null;
  goalSaved: boolean;
  actionBusy?: boolean;
  onSaveGoal: () => void;
  onRefresh: () => void;
  onAction: () => void | Promise<void>;
  onLaunchStep?: (step: PlanStep) => void | Promise<void>;
  onExploreActivities?: () => void;
  launchingStepId?: string | null;
}

const budgetChoices = [5, 10, 15, 20, 30, 45] as const;
const titleByDimension: Record<PlanDimension, string> = {
  working_memory: 'Memory',
  reasoning: 'Reasoning',
  attention_inhibition: 'Attention',
  flexibility: 'Flexibility',
  planning: 'Planning',
};
const dimensionByExercise: Record<string, PlanDimension> = {
  'EX-01': 'working_memory', 'EX-02': 'reasoning', 'EX-03': 'attention_inhibition', 'EX-04': 'flexibility', 'EX-05': 'planning',
};
const dimensions: readonly PlanDimension[] = ['working_memory', 'reasoning', 'attention_inhibition', 'flexibility', 'planning'];

function dimensionFor(step: PlanStep): PlanDimension | null {
  const dimension = step.dimension_id ?? (step.exercise_type_id ? dimensionByExercise[step.exercise_type_id] : undefined);
  return dimensions.includes(dimension as PlanDimension) ? dimension as PlanDimension : null;
}

function formatReason(reason: string | null | undefined): string {
  if (!reason) return 'Selected from recorded task evidence.';
  return reason.split(/[;,]/).map((part) => part.trim().replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase())).filter(Boolean).join(' · ');
}

function readableTime(value: string | null | undefined): string {
  if (!value) return 'Time unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Saved plan' : date.toLocaleString();
}

function versionName(value: SavedPlanVersion): string {
  return value.policy_version ?? value.version ?? value.plan_version ?? 'Version information unavailable';
}
function isCoreTraining(step: PlanStep): boolean {
  return step.activity_ref?.kind === 'core' && (step.mode === 'training' || step.action === 'targeted_training' || step.activity_ref.phase === 'training');
}

export function PlanPage({ budget, setBudget, goal, setGoal, loading, error, plan, recommendation, samples, goalSaved, actionBusy = false, onSaveGoal, onRefresh, onAction, onLaunchStep, onExploreActivities, launchingStepId = null }: PlanPageProps) {
  const [activityCatalog, setActivityCatalog] = useState<Record<string, { family_relevance?: string[]; relevance_scope?: string; assistance_windows?: string[] }>>({});
  useEffect(() => {
    let live = true;
    void Promise.all([
      fetch('/api/hybrid/catalog').then(response => response.ok ? response.json() : Promise.reject(new Error('Hybrid catalogue unavailable'))),
      fetch('/api/crystal/catalog').then(response => response.ok ? response.json() : Promise.reject(new Error('Crystal catalogue unavailable'))),
    ]).then(([hybrid, crystal]) => {
      if (!live) return;
      const items = [...(hybrid.activities ?? []), crystal.capabilities ?? crystal.activity ?? crystal];
      setActivityCatalog(Object.fromEntries(items.filter((item: any) => typeof item.activity_id === 'string').map((item: any) => [item.activity_id, item])));
    }).catch(() => { /* Saved plan cards remain usable if optional catalogue labels cannot load. */ });
    return () => { live = false; };
  }, []);
  const reduceMotion = useReducedMotion();
  const directPlan = plan && (plan.plan_id != null || plan.steps != null || plan.policy_version != null || plan.plan_version != null) ? plan : null;
  const saved = plan?.latest?.plan ?? plan?.latest ?? plan?.plan ?? directPlan;
  const steps = saved?.steps ?? plan?.latest?.plan?.steps ?? plan?.plan?.steps ?? plan?.steps ?? [];
  const history = plan?.history ?? [];
  const stepByDimension = useMemo(() => new Map(steps.flatMap((step) => {
    const dimension = dimensionFor(step);
    return dimension ? [[dimension, step] as const] : [];
  })), [steps]);
  const sampleScenarios = samples?.scenarios ?? [];
  const hasLoadedPlan = plan !== null;

  const getStepTitle = (step: PlanStep): string => {
    if (step.label) return step.label;
    if (step.activity_ref?.kind === 'crystal') return 'Crystal Reasoning';
    if (step.activity_ref?.kind === 'hybrid') return `Hybrid activity ${step.activity_ref.id}`;
    if (step.activity_ref?.kind === 'core') return titleByDimension[dimensionByExercise[step.activity_ref.id]] ?? step.activity_ref.id;
    const dimension = dimensionFor(step);
    return dimension ? titleByDimension[dimension] : step.exercise_type_id ?? step.dimension_id ?? 'Planned activity';
  };
  const recommendedTitle = recommendation?.exercise_id
    ? titleByDimension[dimensionByExercise[recommendation.exercise_id]] ?? recommendation.exercise_id
    : 'Recommended next activity';
  const actionLabel = recommendation?.action === 'complete_baseline'
    ? 'Continue assessment'
    : recommendation?.action === 'additional_assessment'
      ? 'Start a comparable task set'
      : 'Open recommended practice';

  return <main className="plan-rebuild" aria-labelledby="plan-title">
    <section className="plan-rebuild-hero">
      <div className="plan-rebuild-controls">
        <p className="plan-rebuild-eyebrow">Plan your practice</p>
        <h1 id="plan-title">Choose your next crossing.</h1>
        <p className="plan-rebuild-intro">Set a time budget, pick a focus or explore freely. Your route follows saved task evidence; practice remains separate from baseline estimates.</p>

        <fieldset className="plan-budget">
          <legend>Time budget</legend>
          <div className="plan-budget-options">
            {budgetChoices.map((minutes) => <button key={minutes} type="button" className={budget === minutes ? 'is-selected' : ''} aria-pressed={budget === minutes} onClick={() => setBudget(minutes)}>{minutes} min</button>)}
          </div>
        </fieldset>

        <fieldset className="plan-focus">
          <legend>Focus <span>(optional)</span></legend>
          <label className={`plan-focus-option${goal === '' ? ' is-selected' : ''}`}>
            <input type="radio" name="plan-focus" value="" checked={goal === ''} onChange={() => setGoal('')} />
            <span className="plan-focus-mark" aria-hidden="true"><Compass size={19} /></span>
            <span><strong>No preference</strong><small>Let the policy choose</small></span>
          </label>
          {adventureWorlds.map((world) => <label key={world.dimension} className={`plan-focus-option${goal === world.dimension ? ' is-selected' : ''}`}>
            <input type="radio" name="plan-focus" value={world.dimension} checked={goal === world.dimension} onChange={() => setGoal(world.dimension)} />
            <span className="plan-focus-mark"><img src={world.image} alt="" /></span>
            <span><strong>{world.name}</strong><small>{world.place}</small></span>
          </label>)}
        </fieldset>

        <div className="plan-settings-actions">
          <button className="plan-rebuild-button plan-rebuild-button-secondary" type="button" onClick={onSaveGoal} disabled={loading}>{goalSaved ? <><Check size={17} /> Focus saved</> : 'Save focus'}</button>
          <button className="plan-rebuild-button plan-rebuild-button-primary" type="button" onClick={onRefresh} disabled={loading}>{loading ? 'Updating…' : 'Update plan'} <ArrowRight size={17} /></button>
        </div>
        <p className="plan-action-note">Updating asks the policy for a new version. Changing these settings does not alter assessment results.</p>

        {error && <div className="plan-alert" role="alert"><strong>{hasLoadedPlan ? 'Plan action unavailable' : 'Saved plan unavailable'}</strong><span>{error}</span>{hasLoadedPlan && <small>Your last saved plan remains available below.</small>}</div>}

        {recommendation && <section className="plan-recommendation" aria-labelledby="plan-recommendation-title">
          <div className="plan-section-kicker"><Sparkles size={15} /> Recommended next activity</div>
          <h2 id="plan-recommendation-title">{recommendedTitle}</h2>
          {recommendation.event_id && <p className="plan-recommendation-saved" role="status"><Info size={14} /> <span>Saved suggestion{recommendation.created_at ? ` from ${readableTime(recommendation.created_at)}` : ''}. If your latest practice isn’t reflected, choose <strong>Update plan</strong> to recompute it from current evidence.</span></p>}
          <p>{recommendation.rationale || formatReason(recommendation.reason_codes?.join('; '))}</p>
          <div className="plan-recommendation-meta">
            {recommendation.tier && <span>{recommendation.tier}</span>}
            {recommendation.selected_strategy_id && <span>Strategy · {recommendation.selected_strategy_id}</span>}
            {recommendation.policy_version && <span>{recommendation.policy_version}</span>}
            {recommendation.created_at && !recommendation.event_id && <span>{readableTime(recommendation.created_at)}</span>}
          </div>
          <details className="plan-details">
            <summary>Why this was selected <ChevronDown size={16} /></summary>
            <p>{recommendation.rationale || 'The policy uses recorded task evidence, task-specific uncertainty and your selected focus.'}</p>
            {!!recommendation.reason_codes?.length && <PolicySignalList title="Policy reason codes" values={recommendation.reason_codes.map((code) => [code, code.replaceAll('_', ' ')] as const)} />}
            {!!recommendation.features && Object.keys(recommendation.features).length > 0 && <PolicySignalList title="Recorded policy signals" values={Object.entries(recommendation.features).map(([key, value]) => [key, readableFeature(value)] as const)} />}
            <EvidenceList ids={recommendation.evidence_ids ?? []} label="Recommendation evidence" />
            {!!recommendation.alternatives?.length && <div className="plan-alternatives"><strong>Other considered options</strong>{recommendation.alternatives.map((alternative, index) => <p key={alternative.strategy_id ?? alternative.exercise_id ?? index}>{alternative.exercise_id ? titleByDimension[dimensionByExercise[alternative.exercise_id]] ?? alternative.exercise_id : alternative.dimension_id ?? alternative.action ?? 'Alternative'}{alternative.strategy_id ? ` · ${alternative.strategy_id}` : ''}{alternative.rationale ? ` — ${alternative.rationale}` : ''}</p>)}</div>}
          </details>
          <button className="plan-rebuild-button plan-rebuild-button-primary plan-recommendation-action" type="button" onClick={() => void onAction()} disabled={loading || actionBusy}>{actionBusy ? 'Opening…' : actionLabel} <ArrowRight size={17} /></button>
        </section>}
        {!recommendation && !loading && hasLoadedPlan && <p className="plan-recommendation-unavailable" role="status">No current recommendation is available. Update the plan to request a policy selection based on the saved evidence.</p>}
      </div>

      <section className="plan-map" aria-label="Illustrated route through the learning worlds">
        <img className="plan-map-scenery" src="/art/adventure/home-hero-plate.png" alt="" aria-hidden="true" />
        <div className="plan-map-atmosphere" aria-hidden="true" />
        <svg className="plan-map-route" viewBox="0 0 1000 520" preserveAspectRatio="none" aria-hidden="true">
          <path d="M100 290 C200 190 270 380 385 290 S555 190 615 284 S805 365 900 220" />
          {[[100,290],[385,290],[615,284],[900,220]].map(([x,y]) => <circle key={x} cx={x} cy={y} r="7" />)}
        </svg>
        <div className="plan-map-heading"><span>{saved ? saved.budget_minutes == null ? 'Saved route' : `${saved.budget_minutes} minute route` : 'Your practice worlds'}</span><strong>{saved?.goal ? `Focused on ${titleByDimension[saved.goal as PlanDimension] ?? 'your saved goal'}` : steps.length ? 'A path through the islands' : 'A route is ready to explore'}</strong></div>
        <div className="plan-islands">
          {adventureWorlds.map((world, index) => {
            const step = stepByDimension.get(world.dimension as PlanDimension);
            const delay = reduceMotion ? 0 : index * .07;
            return <motion.article key={world.dimension} className={`plan-island plan-island-${index + 1}${step ? ' has-step' : ''}`} initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45, delay }}>
              <img className="plan-island-art" src={world.image} alt="" loading="lazy" />
              <div className="plan-island-card">
                {step ? <><span className="plan-island-order">{steps.indexOf(step) + 1}</span><strong>{world.name}</strong><small>{step.estimated_time_minutes == null ? 'Time unavailable' : `${step.estimated_time_minutes} min`}{step.difficulty_tier ? ` · ${step.difficulty_tier}` : ''}</small></> : <><span className="plan-island-order plan-island-open"><Compass size={14} /></span><strong>{world.name}</strong><small>{world.place}</small></>}
              </div>
            </motion.article>;
          })}
        </div>
        {!hasLoadedPlan && loading && <p className="plan-map-status" role="status">Loading your saved route…</p>}
        {hasLoadedPlan && steps.length === 0 && <p className="plan-map-status">No planned activities have been saved yet.</p>}
        {hasLoadedPlan && steps.length > 0 && <p className="plan-map-status">{steps.length} saved activities · {saved?.estimated_time_minutes == null ? 'total time unavailable' : `${saved.estimated_time_minutes} minutes estimated`}</p>}
      </section>
    </section>

    <section className="plan-saved-section" aria-labelledby="plan-saved-heading">
      <div className="plan-section-heading"><div><p className="plan-rebuild-eyebrow">Saved route</p><h2 id="plan-saved-heading">Planned activities</h2></div>{saved && <span className="plan-version-chip">{versionName(saved)}</span>}</div>
      {loading && !hasLoadedPlan && <p className="plan-state" role="status">Loading saved plan and history…</p>}
      {loading && hasLoadedPlan && <p className="plan-retained" role="status">Refreshing policy data. Your saved plan remains shown.</p>}
      {!loading && !hasLoadedPlan && error && <p className="plan-state" role="status">Saved plan and history could not be loaded.</p>}
      {!loading && !hasLoadedPlan && !error && <p className="plan-state">Saved plan data is not available yet.</p>}
      {hasLoadedPlan && steps.length === 0 && <p className="plan-state">No saved plan steps yet. Choose a time and focus, then update your plan to request a policy selection.</p>}
      {steps.length > 0 && <div className="plan-step-list">{steps.map((step, index) => <article className="plan-saved-step" key={step.step_id ?? `${step.dimension_id ?? step.exercise_type_id ?? 'step'}-${index}`}>
        <span className="plan-saved-number">{index + 1}</span>
        <div className="plan-saved-copy"><strong>{getStepTitle(step)}</strong><p>{formatReason(step.selection_reason)}</p><small>{step.estimated_time_minutes == null ? 'Time unavailable' : `${step.estimated_time_minutes} min${step.duration_estimate?.confidence === 'provisional' ? ' · provisional estimate' : ''}`} · {step.difficulty_tier ?? step.tier ?? (step.activity_ref?.kind === 'crystal' ? 'Separate form' : 'Tier unavailable')} · {step.execution_status ?? step.status ?? 'Status unavailable'}</small>
          {step.activity_ref && (step.activity_ref.kind === 'hybrid' || step.activity_ref.kind === 'crystal') && <p className="plan-activity-boundary">
            {step.activity_ref.kind === 'crystal' ? 'Separate versioned form' : 'Mechanic relevance only'}
            {activityCatalog[step.activity_ref.id]?.family_relevance?.length ? ` · Related task mechanics: ${activityCatalog[step.activity_ref.id].family_relevance!.map(value => value.replaceAll('_', ' ')).join(', ')}` : ''}
            {step.activity_ref.kind === 'hybrid' && (activityCatalog[step.activity_ref.id]?.assistance_windows?.length ?? 0) > 0 ? ` · Recorded help available at ${activityCatalog[step.activity_ref.id].assistance_windows!.map(value => value.replaceAll('_', ' ')).join(', ')}` : ''}
            . These activities do not update baseline indices, EX tiers or participation XP.
          </p>}
          {(step.selection_reason || step.source_evidence_ids?.length) && <details className="plan-details plan-step-evidence"><summary><FileText size={15} /> Why this step? <ChevronDown size={16} /></summary>{step.selection_reason && <p>Recorded policy reason: {step.selection_reason}</p>}{step.strategy_id && <p>Strategy: {step.strategy_id}</p>}<EvidenceList ids={step.source_evidence_ids ?? []} label="Supporting evidence" /></details>}
        </div>
        {step.strategy_id && <span className="plan-strategy">{step.strategy_id.replaceAll('_', ' ')}</span>}
        {step.activity_ref && onLaunchStep && <button type="button" className="plan-step-launch" disabled={Boolean(launchingStepId)} onClick={() => void onLaunchStep(step)}>{launchingStepId === step.step_id ? 'Opening…' : step.activity_ref.kind === 'core' && !isCoreTraining(step) ? 'Open assessment' : step.execution_status === 'completed' || step.launch_ref ? 'Resume or review' : 'Start activity'}</button>}
      </article>)}</div>}
      {onExploreActivities && <aside className="plan-explore-activities"><div><strong>Explore activities</strong><p>Open Hybrid Lab to choose any available game or the separate Crystal form. Manual exploration does not change this saved plan.</p></div><button type="button" className="plan-rebuild-button plan-rebuild-button-secondary" onClick={onExploreActivities}>Open Hybrid Lab</button></aside>}
      {!loading && error && hasLoadedPlan && <p className="plan-retained">A refresh failed. The saved versions above remain available.</p>}
    </section>

    <section className="plan-history-section" aria-labelledby="plan-history-heading">
      <details className="plan-history-disclosure" open={history.length > 0}>
        <summary><span><Clock3 size={20} /> <strong id="plan-history-heading">Previous plans</strong><small>{history.length ? `${history.length} saved version${history.length === 1 ? '' : 's'}` : hasLoadedPlan ? 'No previous versions' : 'History unavailable until loaded'}</small></span><ChevronDown size={19} /></summary>
        {history.length > 0 && <ol className="plan-history-list">{[...history].reverse().map((version, index) => <li key={version.plan_id ?? version.created_at ?? `history-${index}`}>
          <span><strong>{readableTime(version.created_at)}</strong><small>{version.steps?.length ?? 0} saved activities · {version.estimated_time_minutes == null ? 'total time unavailable' : `${version.estimated_time_minutes} min estimated`}</small></span>
          <code>{versionName(version)}</code>
          <EvidenceList ids={version.evidence_ids ?? []} label="Version evidence" />
        </li>)}</ol>}
        {hasLoadedPlan && history.length === 0 && <p className="plan-history-empty">No saved plan versions are available yet.</p>}
      </details>
    </section>

    {samples?.sample_data && sampleScenarios.length > 0 && <section className="plan-samples" aria-labelledby="plan-samples-heading">
      <div className="plan-section-heading"><div><p className="plan-rebuild-eyebrow">Separate from your saved data</p><h2 id="plan-samples-heading">Example policy profiles</h2></div><span className="plan-sample-badge">Sample only · not saved</span></div>
      <p>These isolated examples use no learner history and do not change your plan or evidence.</p>
      <div className="plan-sample-grid">{sampleScenarios.map((sample, index) => {
        const decision = sample.decision;
        const focus = sample.selected_dimension && dimensions.includes(sample.selected_dimension as PlanDimension) ? titleByDimension[sample.selected_dimension as PlanDimension] : sample.selected_dimension ?? 'No focus';
        const activity = decision?.exercise_id ? titleByDimension[dimensionByExercise[decision.exercise_id]] ?? decision.exercise_id : null;
        return <article key={sample.sample_id ?? sample.label ?? index}><span className="plan-sample-kicker">SAMPLE ONLY</span><h3>{sample.label ?? 'Example profile'}</h3><p>{focus} · {decision?.action ?? 'Policy decision'}{decision?.tier ? ` · ${decision.tier}` : ''}</p>{activity && <strong>{activity}</strong>}<p>{decision?.rationale ?? formatReason(decision?.reason_codes?.join('; '))}</p><small>{decision?.evidence_ids?.length ?? 0} sample evidence reference{(decision?.evidence_ids?.length ?? 0) === 1 ? '' : 's'}{decision?.policy_version ? ` · ${decision.policy_version}` : ''}</small></article>;
      })}</div>
    </section>}
    <p className="plan-disclaimer">Time values are planning estimates, not measured task duration. Evidence references remain attached to their saved policy decisions.</p>
  </main>;
}

function EvidenceList({ ids, label }: { ids: readonly string[]; label: string }) {
  if (!ids.length) return <p className="plan-evidence-empty">No linked evidence references are available.</p>;
  return <div className="plan-evidence-list" aria-label={label}><strong>{label}</strong><ul>{ids.map((id) => <li key={id}><code>{id}</code></li>)}</ul></div>;
}

function readableFeature(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean' ? String(item) : 'Structured value').join(', ');
  return value == null ? 'Not recorded' : 'Structured value recorded';
}

function PolicySignalList({ title, values }: { title: string; values: readonly (readonly [string, string])[] }) {
  return <div className="plan-policy-signals"><strong>{title}</strong><dl>{values.map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl></div>;
}
