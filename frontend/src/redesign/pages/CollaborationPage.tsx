import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { AlertCircle, ArrowRight, Check, CheckCircle2, ChevronRight, FileText, Info, Lightbulb, MessageCircleQuestion, RefreshCw, Scale, ShieldCheck, Sparkles, UserCheck, Users } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import './collaboration-page.css';

export type CollaborationDimension = 'clarification' | 'critical_verification' | 'iteration' | 'autonomy' | 'responsible_use';
export type CollaborationDimensionScore = {
  status?: string;
  score_0_100?: number | null;
  weight_percent?: number;
  evaluated_opportunity_count?: number;
  uncertainty_status?: string;
  evidence?: Array<{ score_0_100: number; opportunity_id: string; action_event_id: string; evidence_ids?: string[] }>;
};
export type CollaborationScore = {
  learner_id?: string;
  collaboration_version?: string;
  score_0_100?: number | null;
  status?: string;
  formula?: string;
  weights_percent?: Record<string, number>;
  dimensions?: Record<string, CollaborationDimensionScore>;
  evaluated_opportunity_count?: number;
  interpretation?: string;
};
export type CollaborationOpportunity = {
  opportunity_id: string;
  dimension: CollaborationDimension | string;
  session_id?: string;
  prompt: string;
  status: 'open' | 'evaluated' | string;
  source_event_id?: string;
  evidence_ids?: string[];
  inspectable_evidence_ids?: string[];
  action_event_id?: string | null;
  action_type?: string | null;
  score_0_100?: number | null;
  weight_percent?: number;
  alternatives?: Array<{ dimension?: string; exercise_id?: string }>;
  sample_data?: boolean;
};
export type CollaborationData = {
  score?: CollaborationScore;
  v2Score?: {
    collaboration_version?: string;
    score_0_100?: number | null;
    rubric_note?: string;
    dimensions?: Record<string, { score_0_100?: number | null; status?: string; evaluated_opportunity_count?: number }>;
  };
  opportunities?: CollaborationOpportunity[];
  open_opportunities?: CollaborationOpportunity[];
};

export type CollaborationActionBody = {
  action?: 'pass';
  question?: string;
  checked_evidence_ids?: string[];
  verification_note?: string;
  revision_summary?: string;
  new_goal_dimension?: string;
  choice?: 'accept' | 'modify' | 'decline' | 'keep_local' | 'decline_remote' | 'pause_for_uncertainty';
  reason?: string;
};

// Inspection must report an explicit canonical outcome. A handler that resolves
// void (for example because it swallowed an HTTP failure) is treated as failure.
// The cited record travels with a successful inspection so the learner sees what
// was actually verified instead of only a changed button label.
export type InspectedRecord = {
  event_id?: string;
  event_type?: string;
  type?: string;
  phase?: string;
  dimension?: string;
  exercise_id?: string;
  item_id?: string;
  recorded_at?: string;
  created_at?: string;
  scored?: boolean;
  response?: unknown;
  evaluation?: unknown;
  timing?: unknown;
  interaction?: unknown;
  evidence_ids?: string[];
  stimulus_config?: unknown;
};

export type InspectOutcome =
  | { inspected: true; eventId?: string; record?: InspectedRecord | null; inspectionEventId?: string | null }
  | { inspected: false; reason?: string };

/** Safe completed-task fields the backend exposes for adjudicating one claim. */
export type ClaimContext = {
  event_id?: string;
  recorded_at?: string;
  phase?: string | null;
  exercise_id?: string | null;
  item_id?: string | null;
  scored?: boolean;
  correct?: boolean | null;
  error_type?: string | null;
  assisted?: boolean;
  interrupted?: boolean;
  response_recorded?: boolean;
  evaluation_recorded?: boolean;
};

function ClaimContextView({ context }: { context: ClaimContext }) {
  const rows: Array<{ label: string; value: string }> = [
    { label: 'Task family', value: context.exercise_id ?? 'Not recorded' },
    { label: 'Phase', value: humanize(context.phase ?? 'not recorded') },
    { label: 'Recorded as scored', value: context.scored ? 'Yes' : 'No' },
    { label: 'Server evaluation', value: context.correct === true ? 'Correct' : context.correct === false ? 'Incorrect' : 'No correctness recorded' },
    { label: 'Error type', value: context.error_type ? humanize(context.error_type) : 'None recorded' },
    { label: 'Assistance', value: context.assisted ? 'Recorded with a hint or replay' : 'Recorded unassisted' },
    { label: 'Interruption', value: context.interrupted ? 'Recorded as interrupted' : 'Not interrupted' },
    { label: 'Response saved', value: context.response_recorded ? 'Yes' : 'No' },
    { label: 'Recorded', value: context.recorded_at ?? 'Not recorded' },
  ];
  return <div className="collab-v2-context" aria-label="Facts for this claim">
    <strong>Facts for this claim</strong>
    <dl>{rows.map(row => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl>
    <small>Only saved fields from this completed attempt are shown. The expected verdict stays on the server.</small>
  </div>;
}

export type CollaborationPageProps = {
  collaboration: CollaborationData | null;
  loading: boolean;
  error: string | null;
  busy?: boolean;
  onRefresh: () => void;
  onInspect: (opportunity: CollaborationOpportunity, eventId: string) => Promise<InspectOutcome> | InspectOutcome;
  onAction: (opportunity: CollaborationOpportunity, body: CollaborationActionBody) => Promise<void> | void;
  onPrepareV2?: (opportunity: CollaborationOpportunity) => Promise<{
    claimText: string;
    evidenceEventId: string;
    context?: ClaimContext | null;
  } | null>;
  onV2Action?: (opportunity: CollaborationOpportunity, evidence: {
    verdict: 'supported' | 'contradicted' | 'insufficient_evidence';
    inspected_event_id: string;
  }) => Promise<void>;
};

const rubric: Array<{ dimension: CollaborationDimension; title: string; weight: number; copy: string; icon: typeof Users }> = [
  { dimension: 'clarification', title: 'Clarification', weight: 20, copy: 'Understand the suggestion and what it means.', icon: MessageCircleQuestion },
  { dimension: 'critical_verification', title: 'Verification', weight: 25, copy: 'Check the source and the evidence behind it.', icon: Scale },
  { dimension: 'iteration', title: 'Iteration', weight: 20, copy: 'Consider alternatives and different perspectives.', icon: Lightbulb },
  { dimension: 'autonomy', title: 'Autonomy', weight: 20, copy: 'Make your own decision.', icon: UserCheck },
  { dimension: 'responsible_use', title: 'Responsible use', weight: 15, copy: 'Use ideas thoughtfully and ethically.', icon: ShieldCheck },
];
const goalChoices = ['working_memory', 'reasoning', 'attention_inhibition', 'flexibility', 'planning'];
const goalTitle: Record<string, string> = {
  working_memory: 'Working memory', reasoning: 'Reasoning', attention_inhibition: 'Attention & inhibition',
  flexibility: 'Cognitive flexibility', planning: 'Planning',
};

function humanize(value: unknown): string {
  return String(value ?? '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/^\w/, letter => letter.toUpperCase());
}
function scoreLabel(score: number | null | undefined): string {
  return score == null ? 'Not yet available' : `${Number.isInteger(score) ? score : score.toFixed(1)} / 100`;
}
function statusCopy(value: string | undefined): string {
  if (value === 'PRELIMINARY_HIGH_UNCERTAINTY') return 'Preliminary · high uncertainty';
  if (value === 'NOT_ENOUGH_COLLABORATION_EVIDENCE') return 'Not enough collaboration evidence yet';
  return value ? humanize(value) : 'Status unavailable';
}

function formatValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(formatValue).filter(Boolean).join(', ') || null;
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => { const text = formatValue(entry); return text === null ? null : `${humanize(key)} ${text}`; })
      .filter(Boolean);
    return entries.length ? entries.join(' · ') : null;
  }
  return String(value);
}

/** The cited record itself, so "Inspected" never stands in for reading it. */
function EvidenceRecordView({ record }: { record: InspectedRecord }) {
  const rows: Array<{ label: string; value: string | null }> = [
    { label: 'Record', value: record.event_type ?? record.type ?? null },
    { label: 'Phase', value: record.phase ?? null },
    { label: 'Task family', value: record.dimension ?? null },
    { label: 'Exercise', value: record.exercise_id ?? null },
    { label: 'Item', value: record.item_id ?? null },
    { label: 'Recorded', value: record.recorded_at ?? record.created_at ?? null },
    { label: 'Scored', value: record.scored === undefined ? null : record.scored ? 'Yes' : 'No' },
    { label: 'Response', value: formatValue(record.response) },
    { label: 'Evaluation', value: formatValue(record.evaluation) },
    { label: 'Timing', value: formatValue(record.timing) },
    { label: 'Interaction', value: formatValue(record.interaction) },
  ];
  const visible = rows.filter(row => row.value !== null);
  const evidenceIds = record.evidence_ids ?? [];
  return <div className="collab-record-detail" aria-label="Cited source record">
    <strong>Cited record</strong>
    <dl>
      {visible.map(row => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
    </dl>
    {record.event_id && <small>Event · <code>{record.event_id}</code></small>}
    {evidenceIds.length > 0 && <small>{evidenceIds.length} linked reference{evidenceIds.length === 1 ? '' : 's'}</small>}
    <p className="collab-record-caution">This is a recorded task observation with preliminary, high-uncertainty interpretation. It is not a clinical result and does not establish correctness of the suggestion.</p>
  </div>;
}

export function CollaborationPage({ collaboration, loading, error, busy = false, onRefresh, onInspect, onAction, onPrepareV2, onV2Action }: CollaborationPageProps) {
  const reduceMotion = useReducedMotion();
  const score = collaboration?.score;
  const opportunities = collaboration?.opportunities ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [note, setNote] = useState('');
  const [revision, setRevision] = useState('');
  const [goal, setGoal] = useState('');
  const [choice, setChoice] = useState('');
  const [reason, setReason] = useState('');
  const [checked, setChecked] = useState<string[]>([]);
  const [inspected, setInspected] = useState<Record<string, string[]>>({});
  const [records, setRecords] = useState<Record<string, InspectedRecord>>({});
  const [localBusy, setLocalBusy] = useState(false);
  const [passing, setPassing] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [v2Claim, setV2Claim] = useState<{ opportunityId: string; claimText: string; evidenceEventId: string; context?: ClaimContext | null } | null>(null);
  const [v2Loading, setV2Loading] = useState(false);
  const [v2Verdict, setV2Verdict] = useState<'supported' | 'contradicted' | 'insufficient_evidence' | ''>('');
  const evaluatedCount = rubric.filter(item => (score?.dimensions?.[item.dimension]?.evaluated_opportunity_count ?? 0) > 0).length;
  const v2Attempted = Object.values(collaboration?.v2Score?.dimensions ?? {}).filter(item => (item.evaluated_opportunity_count ?? 0) > 0).length;
  const open = useMemo(() => opportunities.filter(opportunity => opportunity.status === 'open'), [opportunities]);
  const selected = opportunities.find(opportunity => opportunity.opportunity_id === selectedId) ?? open[0] ?? opportunities[0] ?? null;
  const inspectedForSelected = selected ? inspected[selected.opportunity_id] ?? [] : [];
  const alternatives = (selected?.alternatives ?? []).flatMap(item => item.dimension && goalChoices.includes(item.dimension) ? [item.dimension] : []);
  const opportunitySignature = opportunities.map(opportunity => `${opportunity.opportunity_id}:${opportunity.status}`).join('|');

  useEffect(() => {
    setSelectedId(current => current && opportunities.some(opportunity => opportunity.opportunity_id === current) ? current : open[0]?.opportunity_id ?? opportunities[0]?.opportunity_id ?? null);
    setQuestion(''); setNote(''); setRevision(''); setGoal(''); setChoice(''); setReason(''); setChecked([]); setPassing(false);
    setV2Verdict('');
    // Reset form state when the opportunity set or session changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opportunitySignature]);
  useEffect(() => {
    setQuestion(''); setNote(''); setRevision(''); setGoal(''); setChoice(''); setReason(''); setChecked([]); setPassing(false);
    setV2Verdict('');
  }, [selected?.opportunity_id]);

  useEffect(() => {
    let live = true;
    setV2Claim(null);
    if (!selected || selected.dimension !== 'critical_verification' || selected.status === 'evaluated' || !onPrepareV2) return;
    setV2Loading(true);
    void onPrepareV2(selected).then(claim => {
      if (live && claim) setV2Claim({ opportunityId: selected.opportunity_id, ...claim });
    }).catch(caught => {
      if (live) setFormError(caught instanceof Error ? caught.message : 'The structured verification claim could not be prepared.');
    }).finally(() => { if (live) setV2Loading(false); });
    return () => { live = false; };
  }, [selected?.opportunity_id, selected?.dimension, selected?.status, onPrepareV2]);

  const inspect = async (eventId: string) => {
    if (!selected || inspectedForSelected.includes(eventId)) return;
    setLocalBusy(true);
    setFormError(null);
    try {
      const outcome = await Promise.resolve(onInspect(selected, eventId));
      if (!outcome || outcome.inspected !== true) {
        setFormError(outcome && outcome.inspected === false && outcome.reason ? outcome.reason : 'The evidence record could not be confirmed as inspected. Your selection is unchanged.');
        return;
      }
      if (outcome.record) setRecords(current => ({ ...current, [eventId]: outcome.record as InspectedRecord }));
      setInspected(current => ({ ...current, [selected.opportunity_id]: [...(current[selected.opportunity_id] ?? []), eventId] }));
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : 'Inspecting the cited evidence failed.');
    } finally {
      setLocalBusy(false);
    }
  };
  const submit = async (body: CollaborationActionBody) => {
    if (!selected) return;
    setLocalBusy(true);
    setFormError(null);
    try {
      await Promise.resolve(onAction(selected, body));
      setQuestion(''); setNote(''); setRevision(''); setGoal(''); setChoice(''); setReason(''); setChecked([]); setPassing(false);
    } catch (caught) {
      // Keep the learner's draft so a retry does not lose their words.
      setFormError(caught instanceof Error ? caught.message : 'The collaboration action could not be recorded.');
    } finally {
      setLocalBusy(false);
    }
  };
  const locked = busy || localBusy || loading;
  const selectedDimension = selected?.dimension as CollaborationDimension | undefined;
  useEffect(() => { setFormError(null); }, [selected?.opportunity_id]);
  const questionValid = question.trim().split(/\s+/).filter(Boolean).length >= 4 && question.includes('?') && question.trim().length >= 15;
  const verificationValid = checked.length > 0 && note.trim().length >= 25;
  const iterationValid = revision.trim().length >= 25 && goalChoices.includes(goal) && Boolean(goal);
  const autonomyValid = Boolean(choice) && reason.trim().length >= 20 && (choice !== 'modify' || Boolean(goal));
  const responsibleValid = Boolean(choice) && reason.trim().length >= 20;
  const passValid = reason.trim().length >= 20;

  const actionForm = () => {
    if (!selected) return null;
    if (selected.status === 'evaluated') return <div className="collab-recorded" role="status"><CheckCircle2 aria-hidden="true" /><div><strong>Recorded</strong><p>{selected.action_type ? humanize(selected.action_type) : 'This opportunity has a saved action.'} {selected.score_0_100 == null ? '' : `· Rubric ${scoreLabel(selected.score_0_100)}`}</p>{selected.action_event_id && <small>Action event · {selected.action_event_id}</small>}</div></div>;
    if (passing) return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (passValid) void submit({ action: 'pass', reason: reason.trim() }); }}>
      <label className="collab-field"><span>Why are you passing?</span><textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} maxLength={2000} placeholder="A short reason keeps the record honest." /></label>
      <div className="collab-form-actions"><button type="button" className="collab-button collab-button-secondary" onClick={() => setPassing(false)} disabled={locked}>Cancel</button><button type="submit" className="collab-button collab-button-primary" disabled={locked || !passValid}>Record pass <ArrowRight aria-hidden="true" /></button></div>
    </form>;
    if (selectedDimension === 'clarification') return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (questionValid) void submit({ question: question.trim() }); }}>
      <label className="collab-field"><span>What would you ask to understand it better?</span><textarea value={question} onChange={event => setQuestion(event.target.value)} rows={3} maxLength={2000} placeholder="Ask a specific question of at least four words." aria-describedby="collab-question-help" /></label><small id="collab-question-help">Include a question mark and enough detail to be answerable.</small>
      <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !questionValid}>Record clarification <ArrowRight aria-hidden="true" /></button></div>
    </form>;
    if (selectedDimension === 'critical_verification') {
      const inspectable = selected.inspectable_evidence_ids ?? [];
      const v2Ready = v2Claim?.opportunityId === selected.opportunity_id && Boolean(v2Claim.evidenceEventId);
      if (onV2Action && selected.status === 'open' && v2Ready) {
        const submitV2 = (event: FormEvent) => {
          event.preventDefault();
          if (!v2Verdict || !inspectedForSelected.includes(v2Claim.evidenceEventId)) return;
          setLocalBusy(true);
          setFormError(null);
          void onV2Action(selected, { verdict: v2Verdict, inspected_event_id: v2Claim.evidenceEventId })
            .then(() => { setV2Verdict(''); setChecked([]); })
            .catch(caught => setFormError(caught instanceof Error ? caught.message : 'The structured verification could not be recorded.'))
            .finally(() => setLocalBusy(false));
        };
        return <form className="collab-form" onSubmit={submitV2}>
          <div className="collab-v2-claim" aria-labelledby="collab-v2-claim-title">
            <p className="collab-eyebrow">Structured verification · collaboration-v2</p>
            <strong id="collab-v2-claim-title">{v2Claim.claimText}</strong>
            {v2Claim.context && <ClaimContextView context={v2Claim.context} />}
            <small>The expected answer stays on the server until you submit your judgement.</small>
          </div>
          <fieldset className="collab-choice"><legend>How does the cited record read?</legend>{[['supported', 'Supported by the record'], ['contradicted', 'Contradicted by the record'], ['insufficient_evidence', 'Not determinable from this record']].map(([value, label]) => <label key={value}><input type="radio" name="collab-v2-verdict" value={value} checked={v2Verdict === value} onChange={() => setV2Verdict(value as typeof v2Verdict)} /><span>{label}</span></label>)}</fieldset>
          <div className="collab-evidence-checks"><strong>Inspect before judging</strong>{inspectable.length ? inspectable.map(id => <div key={id} className="collab-evidence-row"><button type="button" className="collab-inspect" onClick={() => void inspect(id)} disabled={locked || inspectedForSelected.includes(id)}>{inspectedForSelected.includes(id) ? <><Check aria-hidden="true" /> Inspected</> : <><FileText aria-hidden="true" /> Inspect record</>}</button><code title={id}>{id}</code>{records[id] && <EvidenceRecordView record={records[id]} />}</div>) : <p>No inspectable evidence references were supplied for this opportunity.</p>}</div>
          <p className="collab-hint">A verdict is assessed against the canonical saved record. A free-text explanation alone does not earn credit.</p>
          <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !v2Verdict || !inspectedForSelected.includes(v2Claim.evidenceEventId)}>Record structured verdict <ArrowRight aria-hidden="true" /></button></div>
        </form>;
      }
      if (onV2Action && selected.status === 'open' && v2Loading) return <p className="collab-hint" role="status"><RefreshCw aria-hidden="true" /> Preparing the server-held verification claim…</p>;
      return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (verificationValid) void submit({ checked_evidence_ids: checked, verification_note: note.trim() }); }}>
        <fieldset className="collab-evidence-checks"><legend>Inspect the cited evidence</legend>{inspectable.length ? inspectable.map(id => <div key={id} className="collab-evidence-row"><button type="button" className="collab-inspect" onClick={() => void inspect(id)} disabled={locked || inspectedForSelected.includes(id)}>{inspectedForSelected.includes(id) ? <><Check aria-hidden="true" /> Inspected</> : <><FileText aria-hidden="true" /> Inspect record</>}</button><code title={id}>{id}</code><label><input type="checkbox" checked={checked.includes(id)} disabled={!inspectedForSelected.includes(id) || locked} onChange={event => setChecked(current => event.target.checked ? [...current, id] : current.filter(item => item !== id))} /><span>Checked</span></label>{records[id] && <EvidenceRecordView record={records[id]} />}</div>) : <p>No inspectable evidence references were supplied for this opportunity.</p>}</fieldset>
        <label className="collab-field"><span>What did you verify?</span><textarea value={note} onChange={event => setNote(event.target.value)} rows={3} maxLength={2000} placeholder="Describe what the cited record shows." /></label>
        <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !verificationValid}>Record verification <ArrowRight aria-hidden="true" /></button></div>
      </form>;
    }
    if (selectedDimension === 'iteration') return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (iterationValid) void submit({ revision_summary: revision.trim(), new_goal_dimension: goal, reason: reason.trim() || undefined }); }}>
      <label className="collab-field"><span>How would you revise the suggestion?</span><textarea value={revision} onChange={event => setRevision(event.target.value)} rows={3} maxLength={2000} placeholder="Describe a concrete revision." /></label>
      <label className="collab-field"><span>Revised focus</span><select value={goal} onChange={event => setGoal(event.target.value)}><option value="">Choose a task focus</option>{goalChoices.map(dimension => <option key={dimension} value={dimension}>{goalTitle[dimension]}</option>)}</select></label>
      <p className="collab-hint">The revised focus must differ from the linked suggestion.</p>
      <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !iterationValid}>Record revision <ArrowRight aria-hidden="true" /></button></div>
    </form>;
    if (selectedDimension === 'autonomy') return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (autonomyValid) void submit({ choice: choice as CollaborationActionBody['choice'], new_goal_dimension: choice === 'modify' ? goal : undefined, reason: reason.trim() }); }}>
      <fieldset className="collab-choice"><legend>What is your decision?</legend>{[['accept', 'Accept the suggestion'], ...(alternatives.length ? [['modify', 'Modify it']] : []), ['decline', 'Decline it']].map(([value, label]) => <label key={value}><input type="radio" name="collab-autonomy" value={value} checked={choice === value} onChange={() => setChoice(value)} /><span>{label}</span></label>)}</fieldset>
      {choice === 'modify' && <label className="collab-field"><span>Your alternative focus</span><select value={goal} onChange={event => setGoal(event.target.value)}><option value="">Choose a saved alternative</option>{alternatives.map(dimension => <option key={dimension} value={dimension}>{goalTitle[dimension] ?? humanize(dimension)}</option>)}</select></label>}
      {!alternatives.length && <p className="collab-hint"><Info aria-hidden="true" /> No saved alternative focus was returned for this suggestion, so modification is unavailable.</p>}
      <label className="collab-field"><span>Why is this your decision?</span><textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} maxLength={2000} placeholder="Explain your own reasoning." /></label>
      <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !autonomyValid}>Record decision <ArrowRight aria-hidden="true" /></button></div>
    </form>;
    if (selectedDimension === 'responsible_use') return <form className="collab-form" onSubmit={event => { event.preventDefault(); if (responsibleValid) void submit({ choice: choice as CollaborationActionBody['choice'], reason: reason.trim() }); }}>
      <fieldset className="collab-choice"><legend>How should this idea be used?</legend>{[['keep_local', 'Keep the work local'], ['decline_remote', 'Decline remote processing'], ['pause_for_uncertainty', 'Pause while uncertain']].map(([value, label]) => <label key={value}><input type="radio" name="collab-responsible" value={value} checked={choice === value} onChange={() => setChoice(value)} /><span>{label}</span></label>)}</fieldset>
      <label className="collab-field"><span>Why?</span><textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} maxLength={2000} placeholder="Explain the choice in your own words." /></label>
      <div className="collab-form-actions"><button type="submit" className="collab-button collab-button-primary" disabled={locked || !responsibleValid}>Record choice <ArrowRight aria-hidden="true" /></button></div>
    </form>;
    return <p className="collab-hint">This opportunity has no supported action form.</p>;
  };

  return <main className="collab-rebuild" aria-labelledby="collab-title">
    <section className="collab-hero">
      <img src="/art/adventure/home-hero-plate.png" alt="" aria-hidden="true" />
      <div className="collab-hero-copy"><p className="collab-eyebrow">Real ideas. Clear thinking.</p><h1 id="collab-title">Think together.<br />Decide for yourself.</h1><p>Inspect a suggestion, check its evidence, and keep your own judgment. Interaction evidence remains provisional and separate from task indices.</p></div>
      <div className="collab-hero-score"><span>Your collaboration summary</span><strong>{scoreLabel(score?.score_0_100)}</strong><small>{statusCopy(score?.status)}</small><em>{evaluatedCount} of 5 rubric areas evaluated</em>{score?.evaluated_opportunity_count != null && <small>{score.evaluated_opportunity_count} evaluated opportunities</small>}</div>
    </section>

    {error && <div className="collab-alert" role="alert"><span>{error}</span><button type="button" onClick={onRefresh} disabled={loading}>{loading ? 'Retrying…' : 'Retry'}</button></div>}
    {loading && !collaboration && <p className="collab-state" role="status"><RefreshCw aria-hidden="true" /> Loading collaboration opportunities…</p>}
    {!collaboration && !loading && !error && <section className="collab-empty" role="status"><Users aria-hidden="true" /><div><h2>No collaboration opportunities yet</h2><p>Opportunities are issued only from an actual saved coaching suggestion. Nothing is fabricated for an empty record.</p></div></section>}

    <section className="collab-journey" aria-labelledby="collab-journey-heading">
      <div className="collab-section-heading"><div><p className="collab-eyebrow">The collaboration journey</p><h2 id="collab-journey-heading">Five ways to work with an idea</h2></div><button type="button" className="collab-refresh" onClick={onRefresh} disabled={loading}><RefreshCw aria-hidden="true" /> Refresh</button></div>
      <ol className="collab-steps">{rubric.map((item, index) => {
        const estimate = score?.dimensions?.[item.dimension];
        const evaluated = (estimate?.evaluated_opportunity_count ?? 0) > 0;
        const Icon = item.icon;
        return <li key={item.dimension} className={evaluated ? 'is-evaluated' : ''}><span className="collab-step-index">{index + 1}</span><span className="collab-step-icon"><Icon aria-hidden="true" /></span><div><strong>{item.title}</strong><small>{evaluated ? scoreLabel(estimate?.score_0_100) : 'Not evaluated'}</small><em>{item.weight}% weight</em></div></li>;
      })}</ol>
    </section>

    {collaboration && <div className="collab-layout">
      <section className="collab-workspace" aria-labelledby="collab-workspace-heading">
        <div className="collab-section-heading"><div><p className="collab-eyebrow">Recorded opportunities</p><h2 id="collab-workspace-heading">{open.length ? `${open.length} open to review` : 'No open opportunities'}</h2></div><span>{opportunities.length} total · {opportunities.filter(item => item.status === 'evaluated').length} evaluated</span></div>
        {opportunities.length === 0 ? <p className="collab-empty-copy">No opportunities are available in this session. A saved coaching suggestion is required.</p> : <div className="collab-opportunity-tabs" role="group" aria-label="Collaboration opportunities">{opportunities.map((opportunity, index) => <button type="button" key={opportunity.opportunity_id} className={selected?.opportunity_id === opportunity.opportunity_id ? 'is-selected' : ''} aria-pressed={selected?.opportunity_id === opportunity.opportunity_id} onClick={() => setSelectedId(opportunity.opportunity_id)}><span>{index + 1}</span><strong>{humanize(opportunity.dimension)}</strong><small>{opportunity.status === 'evaluated' ? 'Evaluated' : 'Open'}{opportunity.sample_data ? ' · sample' : ''}</small></button>)}</div>}
        {selected && <motion.article className="collab-opportunity" initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .3 }}>
          <div className="collab-opportunity-heading"><span className="collab-opportunity-icon"><Sparkles aria-hidden="true" /></span><div><p>{humanize(selected.dimension)} · {selected.status === 'evaluated' ? 'Recorded' : 'Open'}</p><h3>{selected.prompt}</h3></div><span className="collab-weight">{selected.weight_percent ?? rubric.find(item => item.dimension === selected.dimension)?.weight ?? '—'}%</span></div>
          <div className="collab-source"><FileText aria-hidden="true" /><div><strong>Linked source record</strong><small>{selected.source_event_id ? selected.source_event_id : 'Source reference unavailable'}</small><span>{selected.evidence_ids?.length ?? 0} linked evidence reference{selected.evidence_ids?.length === 1 ? '' : 's'}</span></div></div>
          {formError && <p className="collab-form-error" role="alert"><AlertCircle aria-hidden="true" /> {formError}</p>}
          {actionForm()}
          {selected.status === 'open' && !passing && <button type="button" className="collab-pass" onClick={() => setPassing(true)} disabled={locked}>Pass with a recorded reason <ChevronRight aria-hidden="true" /></button>}
          {selected.sample_data && <p className="collab-hint"><Info aria-hidden="true" /> This is a sample opportunity and is not saved to learner history.</p>}
        </motion.article>}
      </section>

      <aside className="collab-sidebar">
        <section className="collab-rubric" aria-labelledby="collab-rubric-heading"><div className="collab-section-heading"><div><p className="collab-eyebrow">Collaboration rubric</p><h2 id="collab-rubric-heading">Transparent weights</h2></div></div><p>All areas support thoughtful, independent use of ideas from others.</p><ol>{rubric.map(item => {
          const estimate = score?.dimensions?.[item.dimension];
          const evaluated = (estimate?.evaluated_opportunity_count ?? 0) > 0;
          const Icon = item.icon;
          return <li key={item.dimension}><span className="collab-rubric-icon"><Icon aria-hidden="true" /></span><div><strong>{item.title}</strong><small>{item.copy}</small><span>{evaluated ? `${scoreLabel(estimate?.score_0_100)} · ${estimate?.evaluated_opportunity_count} evaluated` : 'Not evaluated yet'}</span></div><b>{item.weight}%</b></li>;
        })}</ol><p className="collab-formula">{score?.formula ?? 'Each rubric area is weighted only after genuine evaluated opportunities exist.'}</p></section>
        <section className="collab-summary"><p className="collab-eyebrow">Your collaboration summary</p><h2>{scoreLabel(score?.score_0_100)}</h2><p>{score?.interpretation ?? 'A preliminary interaction-evidence summary, not a measure of intelligence.'}</p><small>{score?.evaluated_opportunity_count ?? 0} genuine opportunities evaluated · unanswered remain unassessed</small></section>
        {v2Attempted > 0 && <section className="collab-summary collab-v2-summary" aria-labelledby="collab-v2-heading"><p className="collab-eyebrow">Structured evidence review</p><h2 id="collab-v2-heading">{scoreLabel(collaboration.v2Score?.score_0_100)}</h2><p>{collaboration.v2Score?.rubric_note ?? 'Server-checked verdicts stay separate from the original collaboration history.'}</p><small>{v2Attempted} structured rubric area{v2Attempted === 1 ? '' : 's'} attempted · unassessed states remain visible</small></section>}
        {collaboration.v2Score && v2Attempted === 0 && <p className="collab-v2-note"><ShieldCheck aria-hidden="true" /> Structured verification opens on a verification opportunity: you judge a server-held claim against the cited record.</p>}
        <p className="collab-disclaimer"><AlertCircle aria-hidden="true" /> Passing or declining is recorded honestly and is not penalized as a task score.</p>
      </aside>
    </div>}
  </main>;
}
