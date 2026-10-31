import { useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, Check, CircleHelp, Flag, RotateCcw, X } from 'lucide-react';
import archiveScene from '../games/assets/scene35.png';
import relicStone from '../games/assets/prepared/reasoning-slab.png';
import relicMark from '../games/assets/prepared/reasoning-bracket.png';
import relicCrystal from '../games/assets/prepared/reasoning-crystal-blue.png';
import reviewAmber from '../games/assets/prepared/reasoning-crystal-amber.png';
import reviewBlue from '../games/assets/prepared/reasoning-crystal-blue.png';
import reviewJade from '../games/assets/prepared/hybrid-medallion-leaf.png';
import reviewIvory from '../games/assets/prepared/hybrid-envelope.png';
import reviewViolet from '../games/assets/prepared/hybrid-key.png';
import reviewSaffron from '../games/assets/prepared/hybrid-medallion-lantern.png';
import {
  completeHybridAttempt, fetchHybridAttempt, hybridUid, recordHybridAction, recordHybridAssistance,
  startHybridAttempt, type HybridActivity, type HybridAttempt, type HybridOutcome, type LivingArchiveConfig,
} from './hybridClient';
import { emitCompanionCheckpoint, type CompanionCheckpointHandler, type TimedWindowHandler } from '../../companionCheckpoint';

type Phase = 'ready' | 'encode' | 'play' | 'commit' | 'review';
type ArchiveAction = { event_id: string; sequence: number; action_type: 'select'; payload: { object_id: string; slot_index: number }; elapsed_ms: number }
  | { event_id: string; sequence: number; action_type: 'commit'; payload: Record<string, never>; elapsed_ms: number };
type StartRequest = { event_id: string; session_id: string; activity_id: string; activity_version: string; mode: 'tutorial' | 'training'; difficulty_tier: string };
type AssistanceRequest = { event_id: string; attempt_id: string; exposure_kind: string; checkpoint: string; checkpoint_version: string; source_event_id: string };
type CompletionRequest = { event_id: string; attempt_id: string; interrupted: boolean; response_time_ms: number | null };
type Pending = { attempt_id?: string; session_id: string; action?: ArchiveAction; start_request?: StartRequest;
  assistance_request?: AssistanceRequest; completion_request?: CompletionRequest; phase?: Phase; encode_deadline_ms?: number; launched?: boolean };
const STORAGE_KEY = 'ai4brain.hy05.pending.v1';

export type LivingArchiveGameProps = { activity: HybridActivity; sessionId: string; initialAttemptId?: string | null; onCheckpoint?: CompanionCheckpointHandler; onTimedWindowChange?: TimedWindowHandler; onExit: () => void; onRecorded: () => void };

function placeObject(current: (string | null)[], objectId: string, slot: number) {
  const next = [...current];
  const oldSlot = next.indexOf(objectId);
  const displaced = next[slot];
  if (oldSlot >= 0) next[oldSlot] = displaced ?? null;
  next[slot] = objectId;
  return next;
}

export function LivingArchiveGame({ activity, sessionId, initialAttemptId, onCheckpoint, onTimedWindowChange, onExit, onRecorded }: LivingArchiveGameProps) {
  const [phase, setPhase] = useState<Phase>('ready');
  const [tier, setTier] = useState('tier-1');
  const [attempt, setAttempt] = useState<HybridAttempt | null>(null);
  const [config, setConfig] = useState<LivingArchiveConfig | null>(null);
  const [placement, setPlacement] = useState<(string | null)[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<HybridOutcome | null>(null);
  const [evidenceEvents, setEvidenceEvents] = useState<{event_id:string;sequence:number;type:string;payload:Record<string,unknown>}[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [pending, setPending] = useState<Pending | null>(null);
  const [cluesRevealed, setCluesRevealed] = useState(false);
  const [assisted, setAssisted] = useState(false);
  const sequence = useRef(1);
  const startedAt = useRef(0);
  const completionInflight = useRef(false);
  const mountedRef = useRef(false);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  useEffect(()=>{
    if(attempt&&phase==='ready')emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:ready`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'ready',text:`${activity.title} is ready. Begin when you are comfortable.`});
    if(attempt&&phase==='play')emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:play-open`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'checkpoint',text:'The study period has ended. Continue with the activity when you are ready.'});
    onTimedWindowChange?.(phase==='encode');
    return()=>onTimedWindowChange?.(false);
  },[attempt?.attempt_id,phase,outcome,sessionId,activity.activity_id,activity.title,onCheckpoint,onTimedWindowChange]);

  const restore = useCallback(async (saved: Pending, isCurrent: () => boolean = () => true) => {
    const live = () => mountedRef.current && isCurrent();
    let retrySaved = saved;
    try {
      if (saved.start_request) {
        const started = await startHybridAttempt(saved.start_request);
        if (!live()) return;
        const archiveConfig = started.config as LivingArchiveConfig;
        setAttempt(started); setConfig(archiveConfig); setPlacement(Array(archiveConfig.objects.length).fill(null));
        const deadline = Date.now() + archiveConfig.encode_ms;
        sequence.current = 1; startedAt.current = performance.now(); setPhase('encode'); setCountdown(Math.max(1, Math.ceil(archiveConfig.encode_ms / 1000))); setPending(null);
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: started.attempt_id, session_id: sessionId, phase: 'encode', encode_deadline_ms: deadline } satisfies Pending));
        return;
      }
      if (!saved.attempt_id) throw new Error('No saved attempt identifier');
      const stored = await fetchHybridAttempt(saved.attempt_id);
      if (!live()) return;
      setEvidenceEvents(stored.events);
      if (stored.status !== 'started') {
        if (saved.completion_request) {
          const completion = stored.events.find(event => event.type === 'hybrid_attempt_completed');
          const request = saved.completion_request;
          if (!completion || completion.event_id !== request.event_id
            || Boolean(completion.payload.interrupted) !== request.interrupted
            || Boolean(completion.payload.visibility_interrupted) !== false
            || completion.payload.response_time_ms !== request.response_time_ms) {
            throw new Error('Saved completion does not match the canonical completion event.');
          }
        }
        setOutcome(stored.outcome);
        setPhase('review');
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: saved.attempt_id, session_id: sessionId, phase: 'review' } satisfies Pending));
      } else {
        const cfg = stored.config as LivingArchiveConfig;
        let restartedEncodeDeadline: number | undefined;
        if (saved.completion_request) {
          const result = stored.outcome ?? await completeHybridAttempt(saved.attempt_id, saved.completion_request);
          if (!live()) return;
          setOutcome(result); setPhase('review'); setPending(null);
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: saved.attempt_id, session_id: sessionId, phase: 'review' } satisfies Pending));
          onRecorded();
          return;
        }
        if (saved.assistance_request) {
          const present = stored.assistance.some(row => row.event_id === saved.assistance_request?.event_id);
          if (!present) await recordHybridAssistance(saved.attempt_id, saved.assistance_request);
          if (!live()) return;
          setCluesRevealed(true);
          setAssisted(true);
          if (saved.assistance_request.exposure_kind === 'hidden_information_replay') restartedEncodeDeadline = Date.now() + cfg.encode_ms;
        }
        if (stored.assistance.some(row => row.exposure_kind === 'clue_reveal')) setCluesRevealed(true);
        const actionEvents = stored.events.filter(event => event.type === 'hybrid_action_recorded');
        let next = Array<string | null>(cfg.objects.length).fill(null);
        for (const event of actionEvents) {
          const action = event.payload.action as Record<string, unknown> | undefined;
          if (event.payload.action_type === 'select' && action && typeof action.object_id === 'string' && typeof action.slot_index === 'number') {
            next = placeObject(next, action.object_id, action.slot_index);
          }
          if (event.payload.action_type === 'commit') setPhase('commit');
        }
        const startEventId = stored.events.find(event => event.type === 'hybrid_attempt_started')?.event_id ?? '';
        setAttempt({ ...savedAttemptShape(saved, cfg, startEventId), config: cfg } as HybridAttempt);
        setConfig(cfg);
        setPlacement(next);
        startedAt.current = performance.now();
        sequence.current = actionEvents.reduce((n, event) => Math.max(n, Number(event.payload.action_sequence || 0) + 1), 1);
        const committed = actionEvents.some(event => event.payload.action_type === 'commit');
        const restoredPhase: Phase = committed ? 'commit' : saved.phase ?? (actionEvents.length ? 'play' : 'encode');
        let encodeDeadline = restartedEncodeDeadline ?? saved.encode_deadline_ms ?? (saved.launched ? Date.now() + cfg.encode_ms : undefined);
        if (restoredPhase === 'encode' && actionEvents.length === 0 && encodeDeadline && encodeDeadline <= Date.now()
          && saved.assistance_request?.exposure_kind !== 'hidden_information_replay') {
          const startEventId = stored.events.find(event => event.type === 'hybrid_attempt_started')?.event_id ?? '';
          const request: AssistanceRequest = { event_id: hybridUid(), attempt_id: saved.attempt_id,
            exposure_kind: 'hidden_information_replay', checkpoint: 'pre_encoding', checkpoint_version: '1', source_event_id: startEventId };
          const retryable = { ...saved, assistance_request: request };
          retrySaved = retryable;
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify(retryable));
          await recordHybridAssistance(saved.attempt_id, request);
          if (!live()) return;
          setAssisted(true); setCluesRevealed(true);
          encodeDeadline = Date.now() + cfg.encode_ms;
        }
        setAssisted(value => value || stored.assistance.length > 0);
        setPhase(restoredPhase);
        if (restoredPhase === 'encode') setCountdown(encodeDeadline ? Math.max(0, Math.ceil((encodeDeadline - Date.now()) / 1000)) : 0);
        if (!saved.action || stored.events.some(event => event.event_id === saved.action?.event_id)) {
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: saved.attempt_id, session_id: sessionId,
            phase: restoredPhase, encode_deadline_ms: encodeDeadline } satisfies Pending));
          setPending(null);
        } else {
          setPending(saved);
          setError('A placement may still be waiting to save. Retry the exact same action to reconcile it.');
        }
      }
    } catch {
      if (live()) {
        setPending(retrySaved);
        setError('The saved archive attempt could not be loaded. Retry recovery before starting another attempt.');
      }
    }
  }, [onRecorded, sessionId]);

  useEffect(() => {
    let live = true;
    let raw = sessionStorage.getItem(STORAGE_KEY);
    if (initialAttemptId) {
      let saved: Pending | null = null;
      try { saved = raw ? JSON.parse(raw) as Pending : null; } catch { /* replace malformed session-only state with this canonical launch */ }
      if (saved?.attempt_id !== initialAttemptId || saved?.session_id !== sessionId) {
        const launched: Pending = { attempt_id: initialAttemptId, session_id: sessionId, phase: 'encode', launched: true };
        raw = JSON.stringify(launched);
        sessionStorage.setItem(STORAGE_KEY, raw);
      }
    }
    if (!raw) return () => { live = false; };
    try {
      const saved = JSON.parse(raw) as Pending;
      if (saved.session_id === sessionId) {
        setBusy(true);
        void restore(saved, () => live).finally(() => { if (live && mountedRef.current) setBusy(false); });
      }
      else sessionStorage.removeItem(STORAGE_KEY);
    } catch { sessionStorage.removeItem(STORAGE_KEY); }
    return () => { live = false; };
  }, [initialAttemptId, restore, sessionId]);

  const begin = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      let startRequest: StartRequest;
      const previous = sessionStorage.getItem(STORAGE_KEY);
      try {
        const saved = previous ? JSON.parse(previous) as Pending : null;
        startRequest = saved?.session_id === sessionId && saved.start_request ? saved.start_request : {
          event_id: hybridUid(), session_id: sessionId, activity_id: activity.activity_id,
          activity_version: activity.activity_version, mode: tier === 'tutorial' ? 'tutorial' : 'training', difficulty_tier: tier,
        };
      } catch {
        startRequest = { event_id: hybridUid(), session_id: sessionId, activity_id: activity.activity_id,
          activity_version: activity.activity_version, mode: tier === 'tutorial' ? 'tutorial' : 'training', difficulty_tier: tier };
      }
      const startPending: Pending = { session_id: sessionId, start_request: startRequest };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(startPending)); setPending(startPending);
      const started = await startHybridAttempt(startRequest);
      if (!mountedRef.current) return;
      const archiveConfig = started.config as LivingArchiveConfig;
      setAttempt(started); setConfig(archiveConfig); setPending(null);
      setPlacement(Array(archiveConfig.objects.length).fill(null)); setOutcome(null); setPending(null);
      sequence.current = 1; startedAt.current = performance.now();
      setAssisted(false); setCluesRevealed(false);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: started.attempt_id, session_id: sessionId,
        phase: 'encode', encode_deadline_ms: Date.now() + archiveConfig.encode_ms } satisfies Pending));
      setCountdown(Math.max(1, Math.ceil(archiveConfig.encode_ms / 1000))); setPhase('encode');
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'The archive could not be prepared.'); }
    finally { if (mountedRef.current) setBusy(false); }
  }, [activity.activity_id, activity.activity_version, sessionId, tier]);

  useEffect(() => {
    if (phase !== 'encode') return;
    const raw = sessionStorage.getItem(STORAGE_KEY);
    let deadline: number | null = null;
    try { deadline = raw ? ((JSON.parse(raw) as Pending).encode_deadline_ms ?? null) : null; } catch { deadline = null; }
    if (!deadline || deadline <= Date.now()) return;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((deadline! - Date.now()) / 1000));
      setCountdown(remaining);
      if (remaining === 0) { window.clearInterval(timer); setPhase('play'); persistPhase('play'); startedAt.current = performance.now(); }
    }, 200);
    return () => window.clearInterval(timer);
  }, [phase]);

  const saveAction = useCallback(async (action: Extract<ArchiveAction, { action_type: 'select' }>) => {
    if (!attempt) return;
    const saved: Pending = { attempt_id: attempt.attempt_id, session_id: sessionId, action, phase };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); setPending(saved); setBusy(true); setError(null);
    try {
      await recordHybridAction(attempt.attempt_id, action);
      if (!mountedRef.current) return;
      if (action.action_type === 'select') setPlacement(value => placeObject(value, action.payload.object_id, action.payload.slot_index));
      sequence.current += 1; setPending(null); sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: attempt.attempt_id, session_id: sessionId, phase } satisfies Pending));
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'The archive action could not be saved.'); }
    finally { if (mountedRef.current) setBusy(false); }
  }, [attempt, phase, sessionId]);

  const place = useCallback((objectId: string, slot: number) => {
    if (!attempt || phase !== 'play' || busy || pending) return;
    void saveAction({ event_id: hybridUid(), sequence: sequence.current, action_type: 'select',
      payload: { object_id: objectId, slot_index: slot }, elapsed_ms: Math.round(performance.now() - startedAt.current) });
    setSelected(null);
  }, [attempt, busy, pending, phase, saveAction]);

  const retryPending = useCallback(async () => {
    if (pending?.start_request) {
      setBusy(true); setError(null);
      try { await restore(pending); }
      finally { if (mountedRef.current) setBusy(false); }
      return;
    }
    if (pending?.assistance_request || pending?.completion_request) {
      setBusy(true); setError(null);
      try { await restore(pending); }
      catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'The saved event retry failed.'); }
      finally { if (mountedRef.current) setBusy(false); }
      return;
    }
    if (!pending?.attempt_id || !pending.action) return;
    const attemptId = pending.attempt_id;
    const action = pending.action;
    setBusy(true); setError(null);
    try {
      const stored = await fetchHybridAttempt(attemptId);
      if (!mountedRef.current) return;
      if (stored.events.some(event => event.event_id === action.event_id)) {
        await restore(pending);
        return;
      }
      await recordHybridAction(attemptId, action);
      if (!mountedRef.current) return;
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: attemptId, session_id: sessionId, phase: 'play' } satisfies Pending));
      if (action.action_type === 'select') setPlacement(value => placeObject(value, action.payload.object_id, action.payload.slot_index));
      else setPhase('commit');
      sequence.current = action.sequence + 1; setPending(null);
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'The exact action retry failed.'); }
    finally { if (mountedRef.current) setBusy(false); }
  }, [pending, restore, sessionId]);

  const commit = useCallback(async () => {
    if (!attempt || phase !== 'play' || busy || pending || placement.some(value => !value)) return;
    if (cluesRevealed) return;
    const action: Extract<ArchiveAction, { action_type: 'commit' }> = { event_id: hybridUid(), sequence: sequence.current, action_type: 'commit', payload: {}, elapsed_ms: Math.round(performance.now() - startedAt.current) };
    const saved: Pending = { attempt_id: attempt.attempt_id, session_id: sessionId, action, phase: 'play' };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); setPending(saved); setBusy(true); setError(null);
    try {
      await recordHybridAction(attempt.attempt_id, action);
      if (!mountedRef.current) return;
      sequence.current += 1; setPending(null); setPhase('commit');
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: attempt.attempt_id, session_id: sessionId, phase: 'commit' } satisfies Pending));
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'Commit could not be saved.'); }
    finally { if (mountedRef.current) setBusy(false); }
  }, [attempt, busy, cluesRevealed, pending, phase, placement, sessionId]);

  const revealClues = useCallback(async () => {
    if (!attempt || busy || phase !== 'commit') return;
    const request: AssistanceRequest = { event_id: hybridUid(), attempt_id: attempt.attempt_id, exposure_kind: 'clue_reveal',
      checkpoint: 'post_commit', checkpoint_version: '1', source_event_id: attempt.event_id };
    const saved: Pending = { attempt_id: attempt.attempt_id, session_id: sessionId, assistance_request: request, phase: 'commit' };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); setPending(saved);
    setBusy(true); setError(null);
    try {
      await recordHybridAssistance(attempt.attempt_id, request);
      if (!mountedRef.current) return;
      setCluesRevealed(true); setAssisted(true); setPending(null);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: attempt.attempt_id, session_id: sessionId, phase: 'commit' } satisfies Pending));
      emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'assistance',text:'The recorded clue replay is now available on the board.'});
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'Clues could not be replayed.'); }
    finally { if (mountedRef.current) setBusy(false); }
  }, [attempt, busy, phase, sessionId, onCheckpoint, activity.activity_id]);

  const finish = useCallback(async (interrupted = false) => {
    if (!attempt || busy || completionInflight.current) return;
    let savedRequest = pending?.completion_request;
    if (!savedRequest) {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        const stored = raw ? JSON.parse(raw) as Pending : null;
        if (stored?.attempt_id === attempt.attempt_id) savedRequest = stored.completion_request;
      } catch { /* malformed stale state is replaced with a new request */ }
    }
    if (savedRequest && savedRequest.interrupted !== interrupted) {
      setError('A completion is already pending; retry its exact saved request.');
      return;
    }
    completionInflight.current = true;
    const request: CompletionRequest = savedRequest ?? { event_id: hybridUid(), attempt_id: attempt.attempt_id, interrupted,
      response_time_ms: startedAt.current ? Math.round(performance.now() - startedAt.current) : null };
    const saved: Pending = { attempt_id: attempt.attempt_id, session_id: sessionId, completion_request: request, phase };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); setPending(saved);
    setBusy(true); setError(null);
    try {
      const result = await completeHybridAttempt(attempt.attempt_id, request);
      if (!mountedRef.current) return;
      const recorded = await fetchHybridAttempt(attempt.attempt_id);
      if (!mountedRef.current) return;
      setEvidenceEvents(recorded.events);
      setOutcome(result); setPhase('review'); setPending(null);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ attempt_id: attempt.attempt_id, session_id: sessionId, phase: 'review' } satisfies Pending)); onRecorded();
      if(!interrupted)emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:completed`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'completed',text:'The archive activity is complete. Its saved outcome is ready to review.'});
    } catch (caught) { if (mountedRef.current) setError(caught instanceof Error ? caught.message : 'The archive attempt could not be completed.'); }
    finally { completionInflight.current = false; if (mountedRef.current) setBusy(false); }
  }, [attempt, busy, onRecorded, phase, sessionId, onCheckpoint, activity.activity_id]);

  const relicArt=[relicStone,relicMark,relicCrystal];
  const relicFor=(name:string)=>{const ix=config?.objects.findIndex(object=>object.label===name)??-1;return relicArt[(Math.max(ix,0))%relicArt.length]};
  const reviewRelicByName:Record<string,string>={Amber:reviewAmber,Cobalt:reviewBlue,Jade:reviewJade,Ivory:reviewIvory,Violet:reviewViolet,Saffron:reviewSaffron};
  const reviewRelicFor=(name:string)=>reviewRelicByName[name] ?? relicStone;
  const reviewPlacement = outcome?.outcomes.placement ?? [];
  const reviewConflicts = outcome?.outcomes.conflicts ?? [];
  const reviewFirstConflict = outcome?.outcomes.first_conflict ?? null;
  const conflictLeftSlot = reviewFirstConflict ? reviewPlacement.indexOf(reviewFirstConflict.left) : -1;
  const conflictRightSlot = reviewFirstConflict ? reviewPlacement.indexOf(reviewFirstConflict.right) : -1;
  return <section className={`hy-game hy-archive${phase === 'review' ? ' is-review' : ''}`} style={phase === 'review' ? { backgroundImage: `linear-gradient(90deg,rgba(15,24,42,.26),rgba(15,24,42,.08)),url(${archiveScene})` } : undefined}>
    <div className="hy-scene-banner hy-scene-hy05" style={{backgroundImage:`linear-gradient(90deg,rgba(15,24,42,.2),rgba(15,24,42,.72)),url(${archiveScene})`}} aria-hidden="true"><span>THE LIVING ARCHIVE · RECORD THE RELATIONS</span></div>
    <header className="hy-game-header"><div><p className="hy-eyebrow">Hybrid · {activity.world}</p><h1>{activity.title}</h1><p className="hy-sub">{activity.summary}</p></div>
      {attempt && phase !== 'review' && <span className={`hy-chip ${assisted ? 'is-warn' : 'is-ok'}`}>{assisted ? 'Assisted attempt' : 'Unassisted attempt'}</span>}
      <button type="button" className="hy-ghost" onClick={() => phase === 'encode' || phase === 'play' || phase === 'commit' ? onExit() : onExit()}>
        <X size={16} /> {phase === 'encode' || phase === 'play' || phase === 'commit' ? 'Pause and return' : 'Back to hybrid lab'}
      </button>
    </header>
    {error && <div className="hy-error" role="alert">{error}{pending && <button type="button" className="hy-ghost" onClick={() => void retryPending()} disabled={busy}>{pending.start_request?'Retry exact saved start':pending.assistance_request?'Retry exact clue exposure':pending.completion_request?'Retry exact completion':'Retry exact saved action'}</button>}</div>}
    {phase === 'ready' && <div className="hy-panel"><h2>Arrange the relics</h2><p>Remember each relation, then place the relics from left to right. Use tap or keyboard: select a relic, then activate a slot to place or swap it.</p>
      <fieldset className="hy-tier-fieldset"><legend>Difficulty</legend><div className="hy-tiers">{[['tutorial','Tutorial · 4 relics'],['tier-1','Tier 1 · 4 relics'],['tier-2','Tier 2 · 5 relics'],['tier-3','Tier 3 · 6 relics']].map(([id,label]) =>
        <label key={id} className={`hy-tier ${tier===id?'is-selected':''}`}><input type="radio" name="archive-difficulty" value={id} checked={tier===id} onChange={()=>setTier(id)} /><strong>{label.split(' · ')[0]}</strong><span>{label.split(' · ')[1]}</span></label>)}</div></fieldset>
      <p className="hy-policy"><BookOpen size={16}/> Clue replay is recorded as assistance before the clue appears. Outcomes stay separate from the five fixed indices.</p>
      <button type="button" className="hy-primary" onClick={()=>void begin()} disabled={busy}><Flag size={16}/> Start archive</button></div>}
    {phase === 'encode' && config && <div className="hy-panel hy-encode"><h2>Study the relations</h2><p className="hy-countdown" role="status">Archive seals in {countdown}s</p>
      <div className="hy-archive-study-layout"><aside className="hy-archive-clue-column"><h3>Relational clues</h3><ol className="hy-archive-clues">{config.clues.map(clue=><li key={clue.clue_id}><BookOpen size={16}/><span>{clue.text}</span></li>)}</ol></aside>
      <div className={`hy-archive-relic-strip relic-count-${config.objects.length}`} aria-label="Relics in this archive">{config.objects.map(object=><figure key={object.object_id}><img src={relicFor(object.label)} alt=""/><figcaption>{object.label}</figcaption></figure>)}</div></div><button className="hy-ghost" type="button" onClick={()=>{startedAt.current=performance.now();setPhase('play');persistPhase('play');}}>Begin placement</button></div>}
    {phase === 'play' && config && <div className="hy-panel"><h2>Place the relics left to right</h2><p>Choose a relic, then tab to a slot and activate it. After placing, use Shift+Tab to return to relic choices. Selecting an occupied slot swaps the relics.</p>
      <div className="hy-archive-workspace"><aside className="hy-archive-clue-column is-sealed"><h3>Sealed clue column</h3>{config.clues.map((clue,index)=><div key={clue.clue_id}><BookOpen size={15}/><span>Clue {index+1} · sealed</span></div>)}</aside><div className="hy-archive-play-column">
      <fieldset className="hy-archive-relic-fieldset"><legend>Choose a relic</legend><div className="hy-archive-objects">{config.objects.map(object=><label key={object.object_id} className={`hy-archive-object ${selected===object.object_id?'is-selected':''}`}><input type="radio" name="archive-relic-choice" value={object.object_id} checked={selected===object.object_id} onChange={()=>setSelected(object.object_id)} disabled={busy || Boolean(pending)}/><img src={relicFor(object.label)} alt="" aria-hidden="true"/>{object.label}{placement.includes(object.object_id) ? ' · placed' : ''}</label>)}</div></fieldset>
      <div className={`hy-archive-slots archive-slab relic-count-${config.objects.length}`} style={{backgroundImage:`linear-gradient(rgba(238,229,203,.18),rgba(238,229,203,.18)),url(${relicStone})`}} role="group" aria-label="Choose a slot for the selected relic">{config.slots.map(slot=>{const object=config.objects.find(item=>item.object_id===placement[slot]);return <button type="button" key={slot} className={`hy-archive-slot ${selected && placement[slot] ? 'is-swap' : ''}`} aria-label={`Slot ${slot+1}${object ? `, ${object.label}` : ', empty'}${selected ? ', activate to place or swap selected relic' : ', select a relic first'}`} onClick={()=>selected && place(selected,slot)} disabled={busy || Boolean(pending)}>
        <span>Slot {slot+1}</span>{object?<><img src={relicFor(object.label)} alt="" aria-hidden="true"/><strong>{object.label}</strong></>:<strong>Empty</strong>}</button>})}</div></div></div>
      <button type="button" className="hy-primary" onClick={()=>void commit()} disabled={busy || Boolean(pending) || placement.some(value=>!value)}><Check size={16}/> Commit arrangement</button>
    </div>}
    {phase === 'commit' && <div className="hy-panel"><h2>Arrangement committed</h2><p>Your placement is saved. You can review a recorded clue before the oracle checks the relations.</p>
      {cluesRevealed ? <ol className="hy-archive-clues">{config?.clues.map(clue=><li key={clue.clue_id}>{clue.text}</li>)}</ol> : <button type="button" className="hy-ghost" onClick={()=>void revealClues()} disabled={busy}><CircleHelp size={16}/> Replay clues (assisted)</button>}
      <button type="button" className="hy-primary" onClick={()=>void finish()} disabled={busy}><Flag size={16}/> Check and review</button></div>}
    {phase === 'review' && outcome && <div className="hy-panel hy-review hy-archive-review">
      <div className="hy-archive-review-layout">
        <aside className="hy-archive-review-clues" aria-label="Recorded clues and their review status">
          <h2>Recorded clues</h2><p>Each relation below is read from this attempt’s saved outcome.</p>
          <ol className="hy-archive-review-clue-list">{reviewConflicts.map((conflict,index)=><li key={conflict.clue_id} className={conflict.satisfied?'is-met':'is-missed'}><span className="hy-archive-clue-index">Clue {index+1}</span><p>{conflict.recorded_clue}</p><strong>{conflict.satisfied?'Satisfied':'Conflict'}</strong></li>)}</ol>
        </aside>
        <div className="hy-archive-review-center">
          <div className={`hy-archive-slots archive-slab hy-archive-review-slab relic-count-${reviewPlacement.length}`} style={{backgroundImage:`linear-gradient(rgba(238,229,203,.12),rgba(238,229,203,.12)),url(${relicStone})`}} role="list" aria-label="Your saved placement">
            {reviewPlacement.map((name,index)=><div className="hy-archive-review-tile" role="listitem" key={`${name}-${index}`} aria-label={`Slot ${index+1}: ${name || 'Empty'}`}><span>Slot {index+1}</span>{name && <img src={reviewRelicFor(name)} alt="" aria-hidden="true"/>}<strong>{name || 'Empty'}</strong></div>)}
          </div>
          <p className="hy-archive-relation-count">{outcome.outcomes.relations_satisfied ?? 0} of {outcome.outcomes.relations_total ?? 0} recorded relations satisfied.</p>
        </div>
        <aside className="hy-archive-review-conflict" aria-label="First conflict review">
          <div className="hy-archive-review-conflict-heading"><span>Saved outcome</span><h2>{reviewFirstConflict?'Review the first conflict':outcome.outcomes.valid_arrangement?'Archive restored':'Review the relations'}</h2><p>{reviewFirstConflict?'This placement differs from one recorded relation.':'Your saved placement is compared with the recorded relations.'}</p></div>
          {reviewFirstConflict ? <>
            <div className="hy-archive-compare-pair" aria-label="Saved positions for the conflicting pair">
              <div><span>Your placement</span><strong>{reviewFirstConflict.left}</strong><small>Slot {conflictLeftSlot+1}</small></div><span className="hy-archive-compare-mark" aria-hidden="true">↔</span><div><span>Your placement</span><strong>{reviewFirstConflict.right}</strong><small>Slot {conflictRightSlot+1}</small></div>
            </div>
            <p className="hy-archive-recorded-relation"><strong>Recorded clue</strong>{reviewFirstConflict.recorded_clue}</p>
            <small className="hy-archive-review-limit">The first conflict follows the stored clue order. It does not explain why a placement was made.</small>
          </> : <div className="hy-archive-conflict is-clear"><strong>All recorded relations are satisfied.</strong><p>Your saved placement preserves each clue.</p></div>}
          <p className={`hy-chip ${outcome.excluded_from_unassisted?'is-warn':'is-ok'}`}>{outcome.assisted?'Assisted · excluded from unassisted summaries':outcome.excluded_from_unassisted?'Interrupted · excluded from unassisted summaries':'Unassisted attempt'}</p>
        </aside>
      </div>
      <div className="hy-archive-review-footer"><div><p className="hy-hint-line">{outcome.evidence_ids.length} immutable evidence records · {outcome.activity_version} · {outcome.evaluation_version}</p>
        <details className="hy-evidence"><summary>Open cited evidence records ({outcome.evidence_ids.length})</summary><ol>{outcome.evidence_ids.map(id=>{const event=evidenceEvents.find(row=>row.event_id===id);return <li key={id}><a href={`/api/hybrid/attempts/${outcome.attempt_id}#${encodeURIComponent(id)}`} target="_blank" rel="noreferrer"><code>{id}</code></a>{event&&<> · event {event.sequence} · {event.type}<details><summary>Saved payload</summary><pre>{JSON.stringify(event.payload,null,2)}</pre></details></>}</li>})}</ol><a href={`/api/hybrid/attempts/${outcome.attempt_id}`} target="_blank" rel="noreferrer">Open canonical attempt record</a></details>
        <ul className="hy-limits">{outcome.limitations.map(limit=><li key={limit}>{limit}</li>)}</ul></div>
        <div className="hy-review-actions"><button type="button" className="hy-primary" onClick={()=>{setPhase('ready');setOutcome(null);setAttempt(null);setConfig(null);}}><RotateCcw size={16}/> Try another arrangement</button><button type="button" className="hy-ghost" onClick={onExit}>Back to hybrid lab</button></div>
      </div>
    </div>}
  </section>;
}

function savedAttemptShape(saved: Pending, config: LivingArchiveConfig, eventId: string) {
  return { attempt_id: saved.attempt_id, event_id: eventId, session_id: saved.session_id, activity_id: 'HY-05', activity_version: config.activity_version,
    mode: config.mode, config_version: config.config_version, seed: config.seed, difficulty_tier: config.tier, config,
    assistance: { windows: config.assistance_windows, exposures: [], policy: '' }, created_at: '' };
}

function persistPhase(phase: Phase) {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as Pending;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...saved, phase } satisfies Pending));
  } catch { /* leave the existing canonical recovery key untouched */ }
}
