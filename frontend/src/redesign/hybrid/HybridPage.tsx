import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Gamepad2, LoaderCircle, ShieldCheck } from 'lucide-react';
import { CourierGame } from './CourierGame';
import { LivingArchiveGame } from './LivingArchiveGame';
import { fetchHybridCatalog, fetchHybridSummary, type HybridActivity, type HybridOutcome } from './hybridClient';
import './hybrid.css';
import { CrystalGame } from '../crystal/CrystalGame';
import { BridgeCouncilGame, HarborDispatchGame, ShiftingMarketGame, TidekeeperGame } from './SupplementalGames';
import { useGameArt } from '../games/useGameArt';
import type { CompanionCheckpointHandler, TimedWindowHandler } from '../../companionCheckpoint';

type SummaryActivity = HybridActivity & {
  attempts: number;
  unassisted_attempts: number;
  assisted_attempts: number;
  latest: HybridOutcome | null;
};
function latestActivityText(activityId:string,outcomes:Record<string,any>){
  if(activityId==='HY-01')return `${outcomes.promises_satisfied}/${outcomes.promises_total} promises kept`;
  if(activityId==='HY-02')return `Position ${outcomes.position_correct}/${outcomes.position_total}; symbol ${outcomes.symbol_correct}/${outcomes.symbol_total}`;
  if(activityId==='HY-03')return `Order ${outcomes.shipment_order_matches}/${outcomes.shipment_order_total}; routing ${outcomes.routing_matches}/${outcomes.routing_total}`;
  if(activityId==='HY-04')return `${outcomes.correct_dispatches}/${outcomes.dispatch_total} dispatch decisions; ${outcomes.ignored_distractors} distractors ignored`;
  if(activityId==='HY-05')return `${outcomes.relations_satisfied??0}/${outcomes.relations_total??0} relations satisfied`;
  if(activityId==='HY-06')return `${outcomes.final_route?.feasible?'Feasible':'Unresolved'} route; advice decision ${outcomes.advice_decision??'none'}`;
  return 'Outcome recorded';
}

export type HybridLaunchRef = HybridActivity['activity_id'] | 'crystal';

export type HybridPageProps = {
  sessionId: string | null;
  /** Optional direct destination for a parent-owned plan/navigation flow. */
  initialActivityId?: HybridLaunchRef | null;
  /** A canonical attempt created by a plan-step launch; do not create another one. */
  initialAttemptId?: string | null;
  onChanged?: () => void;
  onActivityActiveChange?: (active: boolean) => void;
  onCheckpoint?: CompanionCheckpointHandler;
  onTimedWindowChange?: TimedWindowHandler;
  /** Lets the parent return to its plan after a launched activity exits. */
  onActivityExit?: () => void;
};

export function HybridPage({ sessionId, initialActivityId, initialAttemptId, onChanged, onActivityActiveChange, onCheckpoint, onTimedWindowChange, onActivityExit }: HybridPageProps) {
  const [activities, setActivities] = useState<SummaryActivity[]>([]);
  const [catalogReady, setCatalogReady] = useState(false);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [crystalSelected, setCrystalSelected] = useState(false);
  const [entryHydratedFor, setEntryHydratedFor] = useState<string | null>(null);
  const art = useGameArt(selected ?? (crystalSelected ? 'EX-02' : 'catalog'));
  useEffect(()=>{onActivityActiveChange?.(Boolean(selected||crystalSelected));return()=>onActivityActiveChange?.(false)},[selected,crystalSelected,onActivityActiveChange]);

  useEffect(() => {
    if (!sessionId) {
      setSelected(null);
      setCrystalSelected(false);
      setEntryHydratedFor(null);
      return;
    }
    const saved = localStorage.getItem(`hy-entry:${sessionId}`);
    if (saved === 'crystal') { setCrystalSelected(true); setSelected(null); }
    else if (saved) { setSelected(saved); setCrystalSelected(false); }
    else { setSelected(null); setCrystalSelected(false); }
    setEntryHydratedFor(sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !initialActivityId) return;
    if (initialActivityId === 'crystal') { setSelected(null); setCrystalSelected(true); }
    else { setSelected(initialActivityId); setCrystalSelected(false); }
  }, [sessionId, initialActivityId]);

  const exitActivity = useCallback(() => {
    setSelected(null);
    setCrystalSelected(false);
    onTimedWindowChange?.(false);
    onActivityExit?.();
  }, [onActivityExit, onTimedWindowChange, onCheckpoint, sessionId]);

  useEffect(() => {
    if (!sessionId || entryHydratedFor !== sessionId) return;
    if (selected) localStorage.setItem(`hy-entry:${sessionId}`, selected);
    else if (crystalSelected) localStorage.setItem(`hy-entry:${sessionId}`, 'crystal');
    else localStorage.removeItem(`hy-entry:${sessionId}`);
  }, [sessionId, entryHydratedFor, selected, crystalSelected]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const catalog = await fetchHybridCatalog();
      setCatalogReady(true);
      let summary: SummaryActivity[] = catalog.activities.map(activity => ({
        ...activity,
        attempts: 0,
        unassisted_attempts: 0,
        assisted_attempts: 0,
        latest: null,
      }));
      setNote(catalog.note);
      setSummaryError(null);
      try {
        const saved = await fetchHybridSummary('demo-user');
        summary = saved.activities;
        setNote(saved.note);
      } catch (caught) {
        setSummaryError(caught instanceof Error ? caught.message : 'Saved activity history is temporarily unavailable.');
      }
      setActivities(summary);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The hybrid catalogue is unavailable.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = activities.find(activity => activity.activity_id === selected) ?? null;

  if ((selected || crystalSelected) && art.status !== 'ready') return <main className="hy-page"><div className="hy-panel"><p role={art.status === 'error' ? 'alert' : 'status'}>{art.status === 'error' ? 'Local artwork could not be prepared. The activity has not started and no timer is running.' : 'Preparing the local scene before the activity starts…'}</p>{art.status === 'error' && <button className="hy-primary" onClick={art.retry}>Retry scene preparation</button>}<button className="hy-ghost" onClick={exitActivity}>Back to activities</button></div></main>;
  if (crystalSelected) return <main className="hy-page"><CrystalGame sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onExit={exitActivity} onRecorded={()=>onChanged?.()} /></main>;

  if (selected && active) {
    return (
      <main className="hy-page">
        {active.activity_id === 'HY-01' ? <CourierGame
          activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange}
          onExit={() => { exitActivity(); void load(); onChanged?.(); }}
          onRecorded={() => { void load(); onChanged?.(); }}
        /> : active.activity_id === 'HY-05' ? <LivingArchiveGame
          activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange}
          onExit={() => { exitActivity(); void load(); onChanged?.(); }}
          onRecorded={() => { void load(); onChanged?.(); }}
        /> : active.activity_id === 'HY-02' ? <TidekeeperGame activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange} onExit={()=>{exitActivity();void load();onChanged?.();}} onRecorded={()=>{void load();onChanged?.();}} /> : active.activity_id === 'HY-03' ? <ShiftingMarketGame activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange} onExit={()=>{exitActivity();void load();onChanged?.();}} onRecorded={()=>{void load();onChanged?.();}} /> : active.activity_id === 'HY-04' ? <HarborDispatchGame activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange} onExit={()=>{exitActivity();void load();onChanged?.();}} onRecorded={()=>{void load();onChanged?.();}} /> : active.activity_id === 'HY-06' ? <BridgeCouncilGame activity={active} sessionId={sessionId ?? ''} initialAttemptId={initialAttemptId} onCheckpoint={onCheckpoint} onTimedWindowChange={onTimedWindowChange} onExit={()=>{exitActivity();void load();onChanged?.();}} onRecorded={()=>{void load();onChanged?.();}} /> : null}
      </main>
    );
  }

  return (
    <main className="hy-page">
      <header className="hy-page-header">
        <p className="hy-eyebrow">Original activities</p>
        <h1>Hybrid practice</h1>
        <p className="hy-sub">
          These activities are separate from the five fixed baseline indices. They record their own descriptive outcomes,
          never a cognitive score, and every assisted attempt stays labelled.
        </p>
      </header>

      {error && (
        <div className="hy-panel">
          <p className="hy-error" role="alert">{error}</p>
          <button type="button" className="hy-ghost" onClick={() => void load()}>
            <ArrowLeft size={16} /> Try again
          </button>
        </div>
      )}

      {loading && !activities.length && (
        <div className="hy-panel hy-loading">
          <LoaderCircle className="spin" size={20} /> Loading the hybrid catalogue…
        </div>
      )}

      {!sessionId && <section className="hy-panel hy-session-gate" role="status"><h2>Start a local session to play</h2><p>These activities save their own attempts under your consented local session. Return to Welcome, accept the preliminary-observations notice, and start a session; your existing records are not replaced.</p></section>}
      {summaryError && <p className="hy-policy" role="status">The catalogue is available, but saved activity history could not be loaded. <button className="hy-ghost" type="button" onClick={()=>void load()}>Retry catalogue and history</button></p>}

      <div className="hy-cards" aria-busy={loading}>
        <article className="hy-card" aria-label="Crystal Reasoning"><div className="hy-card-top"><span className="hy-card-id">Separate form</span><span className="hy-chip">Independent records</span></div><h2>Crystal Reasoning</h2><p className="hy-card-world">Crystal Observatory</p><p>A versioned visual pattern form with its own evidence and outcome records.</p><p className="hy-card-scenario">Not an HY activity and not part of a fixed baseline index.</p><button type="button" className="hy-primary" disabled={!sessionId || (!catalogReady && loading)} onClick={()=>setCrystalSelected(true)}>{!sessionId?'Start a local session first':!catalogReady&&loading?'Loading activities…':'Open separate form'}</button></article>
        {activities.map(activity => (
          <article key={activity.activity_id} className="hy-card" aria-label={activity.title}>
            <div className="hy-card-top">
              <span className="hy-card-id">{activity.activity_id}</span>
              <span className={`hy-chip ${activity.attempts ? 'is-ok' : ''}`}>
                {activity.attempts ? `${activity.attempts} recorded` : 'Not attempted'}
              </span>
            </div>
            <h2>{activity.title}</h2>
            <p className="hy-card-world">{activity.world}</p>
            <p>{activity.summary}</p>
            <p className="hy-card-scenario">{activity.scenarios}</p>
            <dl className="hy-card-stats">
              <div><dt>Unassisted</dt><dd>{activity.unassisted_attempts}</dd></div>
              <div><dt>Assisted</dt><dd>{activity.assisted_attempts}</dd></div>
              <div><dt>Version</dt><dd>{activity.activity_version}</dd></div>
            </dl>
            {activity.latest && (
              <p className="hy-card-latest">
                Latest: {latestActivityText(activity.activity_id,activity.latest.outcomes)} ·{' '}
                {activity.latest.excluded_from_unassisted ? 'assisted or interrupted' : 'unassisted'}
              </p>
            )}
            <button
              type="button"
              className="hy-primary"
              onClick={() => setSelected(activity.activity_id)}
              disabled={!sessionId || (!catalogReady && loading)}
            >
              <Gamepad2 size={16} /> {!sessionId ? 'Start a local session first' : !catalogReady && loading ? 'Loading activities…' : 'Enter activity'}
            </button>
          </article>
        ))}
      </div>

      {note && (
        <p className="hy-policy">
          <ShieldCheck size={16} /> {note}
        </p>
      )}
    </main>
  );
}
