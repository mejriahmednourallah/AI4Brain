import { ArrowRight, Check, ChevronRight, Clock3, FileText, Info, Lightbulb, Play, RefreshCw, Sparkles, Target } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { adventureWorlds } from '../../adventure-worlds';
import './practice-pages.css';

export type PracticeDecision = {
  action: 'up' | 'down' | 'hold' | string;
  old_tier?: string | null;
  new_tier?: string | null;
  successes?: number | null;
  trial_count?: number | null;
  valid_trial_count?: number | null;
  rationale?: string | null;
  reason_codes?: string[] | null;
  evidence_ids?: string[] | null;
  success_definition?: string | null;
  assisted_trial_count?: number | null;
  sample_data?: boolean;
};

export type PracticeStrategy = { id: string; label?: string | null; description?: string | null };

export type PracticeEntryPageProps = {
  dimension: string;
  tier?: string | null;
  timeMinutes?: number | null;
  strategy?: PracticeStrategy | null;
  rationale?: string | null;
  evidenceCount?: number | null;
  policyVersion?: string | null;
  sampleData?: boolean;
  loading?: boolean;
  error?: string | null;
  onEnter: () => void;
  onRetry?: () => void;
  onPlan?: () => void;
  onAskCoach?: () => void;
};

export type PracticeCompletePageProps = {
  dimension: string;
  decision: PracticeDecision | null;
  loading?: boolean;
  error?: string | null;
  onReturnInsights: () => void;
  onNextBlock?: () => void;
  onInspectEvidence?: () => void;
  onRetryDecision?: () => void;
};

function worldFor(dimension: string) {
  return adventureWorlds.find(world => world.dimension === dimension || world.id === dimension);
}
function humanize(value: unknown): string {
  return String(value ?? '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/^\w/, letter => letter.toUpperCase());
}
function tierLabel(value: string | null | undefined): string {
  if (!value) return 'Tier unavailable';
  const match = String(value).match(/^(?:tier[\s_-]*)?(\d+)$/i);
  return match ? `Tier ${match[1]}` : humanize(value);
}
// backend/app/difficulty.py writes a HOLD after four distinct uninterrupted items
// even when fewer than four were unassisted. That is not the normal success rule,
// so the copy must not imply three eligible attempts established it.
function isAssistedHold(decision: PracticeDecision): boolean {
  if (decision.action !== 'hold') return false;
  const codes = decision.reason_codes ?? [];
  return codes.some(code => /insufficient_unassisted|hinted_trials_excluded/i.test(code))
    || (decision.valid_trial_count != null && decision.trial_count != null && decision.valid_trial_count < decision.trial_count)
    || (decision.assisted_trial_count ?? 0) > 0;
}
function actionCopy(decision: PracticeDecision | null): { title: string; lead: string } {
  if (!decision) return { title: 'Practice block complete.', lead: 'The saved attempts are recorded.' };
  if (decision.action === 'up') return { title: 'One tier up.', lead: 'The saved eligible attempts met the task-specific success rule for a higher tier.' };
  if (decision.action === 'down') return { title: 'A smaller step.', lead: 'The saved eligible attempts support a lower tier for the next block.' };
  if (decision.action === 'hold') {
    return isAssistedHold(decision)
      ? { title: 'Tier held — more unassisted evidence needed.', lead: 'Four uninterrupted items were recorded, but too few of them were unassisted to apply the normal tier rule. Hinted attempts remain excluded.' }
      : { title: 'Keeping the same tier.', lead: 'The saved eligible attempts support another block at this tier.' };
  }
  return { title: 'Practice block complete.', lead: 'The saved attempts are recorded. Review the tier decision below.' };
}

export function PracticeEntryPage({ dimension, tier, timeMinutes, strategy, rationale, evidenceCount, policyVersion, sampleData = false, loading = false, error = null, onEnter, onRetry, onPlan, onAskCoach }: PracticeEntryPageProps) {
  const reduceMotion = useReducedMotion();
  const world = worldFor(dimension);
  if (!world) return <main className="practice-rebuild practice-entry"><section className="practice-unavailable" aria-label="Practice unavailable"><Info aria-hidden="true" /><div><h1>This practice world is unavailable.</h1><p>The supplied task family is not in the saved world catalog.</p></div></section></main>;
  const hasTime = typeof timeMinutes === 'number' && Number.isFinite(timeMinutes) && timeMinutes > 0;
  return <main className="practice-rebuild practice-entry" aria-labelledby="practice-entry-title">
    <section className="practice-entry-shell">
      <div className="practice-entry-panel">
        <p className="practice-eyebrow">Guided training{sampleData ? ' · sample recommendation' : ''}</p>
        <h1 id="practice-entry-title">{world.place}</h1>
        <p className="practice-entry-lead">{world.description}</p>
        <dl className="practice-entry-meta">
          <div><dt><Clock3 aria-hidden="true" /> Time</dt><dd>{hasTime ? `About ${timeMinutes} minutes` : 'Time estimate unavailable'}</dd></div>
          <div><dt><Target aria-hidden="true" /> Tier</dt><dd>{tierLabel(tier)}</dd></div>
          <div><dt><FileText aria-hidden="true" /> Evidence</dt><dd>{evidenceCount == null ? 'Evidence count unavailable' : `${evidenceCount} saved reference${evidenceCount === 1 ? '' : 's'}`}</dd></div>
        </dl>
        {error && <div className="practice-alert" role="alert"><span>{error}</span>{onRetry && <button type="button" onClick={onRetry} disabled={loading}>{loading ? 'Retrying…' : 'Retry'}</button>}</div>}
        <button type="button" className="practice-primary" onClick={onEnter} disabled={loading}>
          <Play aria-hidden="true" /><span>{loading ? 'Preparing practice…' : 'Enter practice'}</span><ArrowRight aria-hidden="true" />
        </button>
        {onAskCoach && <button type="button" className="practice-text-action" onClick={onAskCoach}>Ask about this practice <ChevronRight aria-hidden="true" /></button>}
        <section className="practice-strategy" aria-labelledby="practice-strategy-heading">
          <h2 id="practice-strategy-heading"><Lightbulb aria-hidden="true" /> {strategy ? 'A helpful strategy' : 'Why this block'}</h2>
          {strategy
            ? <><strong>{strategy.label ?? humanize(strategy.id)}</strong><p>{strategy.description ?? 'This strategy is attached to the saved recommendation.'}</p></>
            : <p>{rationale ?? 'No strategy is attached to this practice block yet.'}</p>}
          {strategy && policyVersion && <small>Strategy source · {strategy.id} · {policyVersion}</small>}
        </section>
        {strategy && rationale && <section className="practice-why" aria-labelledby="practice-why-heading">
          <h2 id="practice-why-heading"><Sparkles aria-hidden="true" /> Why this block</h2>
          <p>{rationale}</p>
        </section>}
        <div className="practice-separation" aria-label="Baseline and training distinction">
          <span><i aria-hidden="true" /> Baseline<small>Uncoached observations</small></span>
          <span className="practice-separation-line" aria-hidden="true" />
          <span className="is-training"><i aria-hidden="true" /> Training<small>Guided practice</small></span>
        </div>
        <p className="practice-note"><Info aria-hidden="true" /> Training stays separate from your baseline estimate. Assisted attempts are recorded and excluded from unassisted tier eligibility.</p>
        {onPlan && <button type="button" className="practice-text-action" onClick={onPlan}>Review the plan behind this block <ChevronRight aria-hidden="true" /></button>}
      </div>
      <div className="practice-entry-art" aria-hidden="true">
        <img src="/art/adventure/game-landscape.webp" alt="" />
        <motion.img src={world.image} alt="" initial={false} animate={reduceMotion ? undefined : { y: [0, -5, 0] }} transition={reduceMotion ? undefined : { duration: 8, repeat: Infinity, ease: 'easeInOut' }} />
        <span className="practice-entry-art-label">{world.name} · {world.place}</span>
      </div>
    </section>
  </main>;
}

export function PracticeCompletePage({ dimension, decision, loading = false, error = null, onReturnInsights, onNextBlock, onInspectEvidence, onRetryDecision }: PracticeCompletePageProps) {
  const reduceMotion = useReducedMotion();
  const world = worldFor(dimension);
  const copy = actionCopy(decision);
  const valid = decision?.valid_trial_count ?? null;
  const attempted = decision?.trial_count ?? null;
  const successes = decision?.successes ?? null;
  const evidence = decision?.evidence_ids ?? [];
  return <main className="practice-rebuild practice-complete" aria-labelledby="practice-complete-title">
    <section className="practice-complete-shell">
      <div className="practice-complete-panel">
        <p className="practice-eyebrow">Practice block complete{decision?.sample_data ? ' · sample state' : ''}</p>
        <h1 id="practice-complete-title">{copy.title}</h1>
        <p className="practice-complete-lead">{copy.lead}</p>
        {error && <div className="practice-alert" role="alert"><span>{error}</span>{onRetryDecision && <button type="button" onClick={onRetryDecision} disabled={loading}>{loading ? 'Retrying…' : 'Retry decision'}</button>}</div>}
        {decision ? <>
          <motion.div className="practice-tier-transition" initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .35 }}>
            <span><small>Previous</small><strong>{tierLabel(decision.old_tier)}</strong></span>
            <ArrowRight aria-hidden="true" />
            <span className="is-current"><small>Next block</small><strong>{tierLabel(decision.new_tier)}</strong></span>
          </motion.div>
          <dl className="practice-decision-stats">
            <div><dt>Eligible trials</dt><dd>{valid == null || attempted == null ? 'Unavailable' : `${valid} of ${attempted} attempted`}</dd></div>
            <div><dt>Task successes</dt><dd>{successes == null || valid == null ? 'Unavailable' : `${successes} of ${valid} eligible`}</dd></div>
            <div><dt>Assisted trials</dt><dd>{decision.assisted_trial_count == null ? 'Not reported' : String(decision.assisted_trial_count)}</dd></div>
          </dl>
          <p className="practice-decision-rationale">{decision.rationale ?? 'The saved tier decision did not include a rationale.'}</p>
          {decision.success_definition && <p className="practice-decision-definition"><Info aria-hidden="true" /> Success rule · {decision.success_definition}</p>}
          {!!decision.reason_codes?.length && <div className="practice-reasons"><strong>Decision references</strong><div>{decision.reason_codes.map(code => <span key={code}>{humanize(code)}</span>)}</div></div>}
          {evidence.length > 0 && <details className="practice-evidence"><summary><FileText aria-hidden="true" /> Inspect supporting records ({evidence.length})</summary><ul>{evidence.map(id => <li key={id}><code>{id}</code></li>)}</ul></details>}
          <p className="practice-note"><Check aria-hidden="true" /> Training remains separate from your baseline estimate. A tier decision is not a cognitive score.</p>
        </> : loading ? <div className="practice-decision-pending" role="status"><RefreshCw aria-hidden="true" /><span>Loading the saved tier decision…</span></div>
          : <div className="practice-decision-pending" role="status"><Info aria-hidden="true" /><div><strong>No tier decision is saved yet</strong><p>A decision is written after four distinct uninterrupted attempts are recorded. Unassisted eligibility is reported with that decision.</p></div>{onRetryDecision && <button type="button" onClick={onRetryDecision}>Check again</button>}</div>}
        <div className="practice-complete-actions">
          <button type="button" className="practice-primary" onClick={onReturnInsights}>Return to insights <ArrowRight aria-hidden="true" /></button>
          {onNextBlock && <button type="button" className="practice-secondary" onClick={onNextBlock}>Start another block</button>}
          {onInspectEvidence && <button type="button" className="practice-text-action" onClick={onInspectEvidence}>Open the evidence graph <ChevronRight aria-hidden="true" /></button>}
        </div>
      </div>
      <div className="practice-complete-art" aria-hidden="true">
        <img src="/art/adventure/game-landscape.webp" alt="" />
        <img src={world?.image} alt="" />
        <span>{world?.place ?? 'Practice world'} <Sparkles /></span>
      </div>
    </section>
  </main>;
}
