import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bell,
  Check,
  CircleHelp,
  Flag,
  Package,
  RotateCcw,
  X,
} from 'lucide-react';
import {
  completeHybridAttempt,
  fetchHybridAttempt,
  hybridUid,
  recordHybridAction,
  recordHybridAssistance,
  startHybridAttempt,
  type CourierConfig,
  type HybridActivity,
  type HybridAttempt,
  type HybridOutcome,
} from './hybridClient';
import { matchesCourierActionEvent, matchesCourierCompletionEvent, replayCourierEvents } from './courierRecovery.js';
import { emitCompanionCheckpoint, type CompanionCheckpointHandler, type TimedWindowHandler } from '../../companionCheckpoint';
import './hybrid.css';

type Phase = 'ready' | 'encode' | 'play' | 'review';
type Direction = 'up' | 'down' | 'left' | 'right';
type CourierAction = { event_id: string; sequence: number; action_type: 'move' | 'deliver'; payload: Record<string, unknown>; elapsed_ms: number };

const DIRECTION_VECTOR: Record<Direction, [number, number]> = {
  up: [0, -1],
  down: [0, 1],
  left: [-1, 0],
  right: [1, 0],
};

const KEY_TO_DIRECTION: Record<string, Direction> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  w: 'up',
  s: 'down',
  a: 'left',
  d: 'right',
};

const TIERS = [
  { id: 'tutorial', label: 'Tutorial', detail: '3×4 garden · 1 promise' },
  { id: 'tier-1', label: 'Tier 1', detail: '4×5 garden · 2 promises' },
  { id: 'tier-2', label: 'Tier 2', detail: '4×6 garden · 3 promises' },
  { id: 'tier-3', label: 'Tier 3', detail: '5×6 garden · 4 promises' },
];

const key = (x: number, y: number) => `${x},${y}`;
const parcelLabel = (parcelId: string) => {
  const match = parcelId.match(/^(?:parcel-)?(\d+)$/i);
  return match ? `Parcel ${match[1]}` : parcelId;
};

export type CourierGameProps = {
  activity: HybridActivity;
  sessionId: string;
  initialAttemptId?: string | null;
  onCheckpoint?: CompanionCheckpointHandler;
  onTimedWindowChange?: TimedWindowHandler;
  onExit: () => void;
  onRecorded: () => void;
};

export function CourierGame({ activity, sessionId, initialAttemptId, onCheckpoint, onTimedWindowChange, onExit, onRecorded }: CourierGameProps) {
  const [phase, setPhase] = useState<Phase>('ready');
  const [tier, setTier] = useState('tier-1');
  const [attempt, setAttempt] = useState<HybridAttempt | null>(null);
  const [config, setConfig] = useState<CourierConfig | null>(null);
  const [outcome, setOutcome] = useState<HybridOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [position, setPosition] = useState<[number, number]>([0, 0]);
  const [carried, setCarried] = useState<string | null>(null);
  const [deliveredParcels, setDeliveredParcels] = useState<string[]>([]);
  const [moves, setMoves] = useState(0);
  const [gatesSeen, setGatesSeen] = useState<string[]>([]);
  const [blocked, setBlocked] = useState(0);
  const [deliveries, setDeliveries] = useState(0);
  const [assisted, setAssisted] = useState(false);
  const [reminder, setReminder] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [pendingAction, setPendingAction] = useState<CourierAction | null>(null);
  const [recoveryTick, setRecoveryTick] = useState(0);
  const sequence = useRef(1);
  const startedAt = useRef(0);
  const completionInflight = useRef(false);
  const actionInflight = useRef(false);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const activeAttemptKey = `hy-active-courier:${sessionId}:${activity.activity_id}`;
  useEffect(()=>{
    if(attempt&&phase!=='review')emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:ready`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'ready',text:`${activity.title} is ready. Begin when you are comfortable.`});
  },[attempt?.attempt_id,phase,sessionId,activity.activity_id,activity.title,onCheckpoint]);
  useEffect(()=>{onTimedWindowChange?.(phase==='encode');return()=>onTimedWindowChange?.(false)},[phase,onTimedWindowChange]);
  useEffect(()=>{if(attempt&&phase==='play')emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:play-open`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'checkpoint',text:'The timed introduction has ended. Continue with the activity when you are ready.'});},[attempt?.attempt_id,phase,sessionId,activity.activity_id,onCheckpoint]);
  const startRequestKey = `hy-pending-courier-start:${sessionId}:${activity.activity_id}`;
  const pendingActionKey = (attemptId: string) => `hy-pending-action:${attemptId}`;
  const completionPending = Boolean(attempt && localStorage.getItem(`hy-pending-completion:${attempt.attempt_id}`));

  // Restore active canonical state after reload. Stored events are the source
  // of truth; local pending bodies are retained until an exact replay succeeds.
  useEffect(() => {
    const attemptId = initialAttemptId ?? localStorage.getItem(activeAttemptKey);
    if (attemptId && initialAttemptId) localStorage.setItem(activeAttemptKey, attemptId);
    if (!attemptId) {
      if (localStorage.getItem(startRequestKey)) setError('A saved start request needs an exact retry.');
      return;
    }
    setRecovering(true);
    const completionKey = `hy-pending-completion:${attemptId}`;
    let live = true;
    void (async () => {
      try {
        const stored = await fetchHybridAttempt(attemptId);
        if (!live) return;
        setError(null);
        const courierConfig = stored.config as CourierConfig;
        const actionEvents = stored.events
          .filter(event => event.type === 'hybrid_action_recorded')
          .sort((left, right) => Number(left.payload.action_sequence ?? left.sequence) - Number(right.payload.action_sequence ?? right.sequence));
        const actionKey = pendingActionKey(attemptId);
        const rawAction = localStorage.getItem(actionKey);
        const pending = rawAction ? JSON.parse(rawAction) as CourierAction : null;
        if (pending) {
          const event = stored.events.find(candidate => candidate.event_id === pending.event_id);
          if (event) {
            if (matchesCourierActionEvent(event, pending)) localStorage.removeItem(actionKey);
            else setError('A saved action ID conflicts with its canonical event; the board is locked for review.');
          } else setError('A saved action needs an exact retry before the courier can continue.');
        }
        const replay = replayCourierEvents(courierConfig, stored.events);
        const startEvent = stored.events.find(event => event.type === 'hybrid_attempt_started');
        setAttempt({
          attempt_id: stored.attempt_id, event_id: startEvent?.event_id ?? '', session_id: stored.session_id,
          activity_id: stored.activity_id, activity_version: stored.activity_version, mode: stored.mode,
          difficulty_tier: stored.difficulty_tier, seed: stored.seed, config: courierConfig,
          assistance: { windows: courierConfig.assistance_windows ?? [], exposures: stored.assistance.map(item => item.exposure_kind), policy: '' },
          created_at: stored.started_at,
        });
        setConfig(courierConfig);
        setTier(stored.difficulty_tier);
        setPosition(replay.position);
        setCarried(replay.carried);
        setDeliveredParcels(replay.deliveredParcels);
        setMoves(replay.moves);
        setGatesSeen(replay.gatesSeen);
        setDeliveries(replay.deliveries);
        setAssisted(stored.assistance.length > 0);
        sequence.current = actionEvents.length + 1;
        setPendingAction(localStorage.getItem(actionKey) ? JSON.parse(localStorage.getItem(actionKey)!) as CourierAction : null);
        startedAt.current = performance.now() - Math.max(0, ...actionEvents.map(event => Number(event.payload.elapsed_ms ?? 0)));
        const completionRaw = localStorage.getItem(completionKey);
        let result: HybridOutcome | null = null;
        if (stored.outcome && completionRaw) {
          const event = stored.events.find(candidate => candidate.type === 'hybrid_attempt_completed');
          const request = JSON.parse(completionRaw) as Record<string, unknown>;
          if (!matchesCourierCompletionEvent(event, request)) {
            setError('The saved completion request conflicts with the canonical completion; it was kept for review.');
            return;
          }
          localStorage.removeItem(completionKey);
          result = stored.outcome;
        } else if (stored.outcome) result = stored.outcome;
        else if (completionRaw) result = await completeHybridAttempt(attemptId, JSON.parse(completionRaw));
        if (!live) return;
        if (result) {
          setOutcome(result);
          setPhase('review');
          localStorage.removeItem(completionKey);
          localStorage.removeItem(activeAttemptKey);
          localStorage.removeItem(`hy-courier-phase:${attemptId}`);
          localStorage.removeItem(`hy-courier-encode-start:${attemptId}`);
          onRecorded();
        } else if (actionEvents.length > 0 || localStorage.getItem(`hy-courier-phase:${attemptId}`) === 'play') {
          setPhase('play');
        } else {
          const encodeKey = `hy-courier-encode-start:${attemptId}`;
          let encodeStartedAt = Number(localStorage.getItem(encodeKey));
          if (!encodeStartedAt) {
            encodeStartedAt = Date.now();
            localStorage.setItem(encodeKey, String(encodeStartedAt));
          }
          const remainingMs = Math.max(0, courierConfig.encode_ms - (Date.now() - encodeStartedAt));
          if (remainingMs <= 0) {
            const interrupted = { event_id: hybridUid(), interrupted: true, response_time_ms: null };
            localStorage.setItem(completionKey, JSON.stringify(interrupted));
            const interruptedResult = await completeHybridAttempt(attemptId, interrupted);
            if (!live) return;
            setOutcome(interruptedResult);
            setPhase('review');
            localStorage.removeItem(completionKey);
            localStorage.removeItem(activeAttemptKey);
            localStorage.removeItem(`hy-courier-phase:${attemptId}`);
            localStorage.removeItem(`hy-courier-encode-start:${attemptId}`);
            onRecorded();
          } else {
            setPhase('encode');
            setCountdown(Math.max(1, Math.ceil(remainingMs / 1000)));
          }
        }
      } catch (caught) {
        if (live) setError(caught instanceof Error ? caught.message : 'Could not reconcile the saved completion.');
      } finally {
        if (live) setRecovering(false);
      }
    })();
    return () => { live = false; };
  }, [activeAttemptKey, initialAttemptId, onRecorded, recoveryTick, startRequestKey]);

  const walls = useMemo(() => new Set((config?.board.walls ?? []).map(([x, y]) => key(x, y))), [config]);
  const parcelCells = useMemo(
    () => new Map((config?.parcels ?? []).map(p => [key(p.cell[0], p.cell[1]), p.parcel_id])),
    [config],
  );
  const destinationCells = useMemo(
    () => new Map((config?.destinations ?? []).map(d => [key(d.cell[0], d.cell[1]), d.destination_id])),
    [config],
  );
  const gateCells = useMemo(() => new Map((config?.gates ?? []).map(g => [key(g.cell[0], g.cell[1]), g.gate_id])), [config]);
  const bellRang = config ? moves >= config.bell.after_moves : false;
  const formatPromise = (plan: { parcel_id: string; promise: string; cue?: string }) => {
    const promise = config?.activity_version === 'hy-01-v2' && plan.cue === 'after_gate_a'
      ? plan.promise.replace(/the first garden gate/gi, 'gate A')
      : plan.promise;
    return `${parcelLabel(plan.parcel_id)}: ${promise}`;
  };

  const begin = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const savedStart = localStorage.getItem(startRequestKey);
      const startRequest = savedStart ? JSON.parse(savedStart) : {
        event_id: hybridUid(),
        session_id: sessionId,
        activity_id: activity.activity_id,
        activity_version: activity.activity_version,
        config_version: activity.config_version,
        mode: tier === 'tutorial' ? 'tutorial' : 'training',
        difficulty_tier: tier,
      };
      if (!savedStart) localStorage.setItem(startRequestKey, JSON.stringify(startRequest));
      const started = await startHybridAttempt(startRequest);
      const courierConfig = started.config as CourierConfig;
      setAttempt(started);
      localStorage.setItem(activeAttemptKey, started.attempt_id);
      localStorage.removeItem(startRequestKey);
      localStorage.setItem(`hy-courier-encode-start:${started.attempt_id}`, String(Date.now()));
      localStorage.setItem(`hy-courier-phase:${started.attempt_id}`, 'encode');
      setConfig(courierConfig);
      setPosition(courierConfig.board.start);
      setCarried(null);
      setDeliveredParcels([]);
      setMoves(0);
      setGatesSeen([]);
      setBlocked(0);
      setDeliveries(0);
      setAssisted(false);
      setOutcome(null);
      setPendingAction(null);
      sequence.current = 1;
      setPhase('encode');
      setCountdown(Math.max(1, Math.round(courierConfig.encode_ms / 1000)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The attempt could not be started.');
    } finally {
      setBusy(false);
    }
  }, [activity.activity_id, activity.activity_version, activeAttemptKey, sessionId, startRequestKey, tier]);

  useEffect(() => {
    if (phase !== 'encode') return;
    const timer = window.setInterval(() => {
      setCountdown(value => {
        if (value <= 1) {
          window.clearInterval(timer);
          const attemptId = localStorage.getItem(activeAttemptKey);
          if (attemptId) localStorage.setItem(`hy-courier-phase:${attemptId}`, 'play');
          setPhase('play');
          startedAt.current = performance.now();
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeAttemptKey, phase]);

  useEffect(() => {
    if (!reminder) return;
    const timer = window.setTimeout(() => setReminder(false), 6000);
    return () => window.clearTimeout(timer);
  }, [reminder]);

  const applyAcceptedAction = useCallback((request: CourierAction) => {
    if (request.action_type === 'move') {
      const direction = request.payload.direction as Direction;
      const [dx, dy] = DIRECTION_VECTOR[direction];
      const next: [number, number] = [position[0] + dx, position[1] + dy];
      setPosition(next);
      setMoves(value => value + 1);
      const gate = gateCells.get(key(...next));
      if (gate) setGatesSeen(seen => (seen.includes(gate) ? seen : [...seen, gate]));
      if (!carried) {
        const parcel = parcelCells.get(key(...next));
        if (parcel && (config?.activity_version !== 'hy-01-v2' || !deliveredParcels.includes(parcel))) setCarried(parcel);
      }
    } else {
      const parcel = String(request.payload.parcel_id ?? carried ?? '');
      if (destinationCells.has(key(...position))) {
        if (config?.activity_version === 'hy-01-v2' && parcel) setDeliveredParcels(current => current.includes(parcel) ? current : [...current, parcel]);
        setCarried(null);
        setDeliveries(value => value + 1);
      }
    }
  }, [carried, config?.activity_version, deliveredParcels, destinationCells, gateCells, parcelCells, position]);

  const submitAction = useCallback(async (actionType: CourierAction['action_type'], payload: Record<string, unknown>) => {
    if (!attempt || actionInflight.current) return;
    const storageKey = pendingActionKey(attempt.attempt_id);
    const savedRaw = localStorage.getItem(storageKey);
    let request: CourierAction;
    if (savedRaw) {
      request = JSON.parse(savedRaw) as CourierAction;
      if (request.action_type !== actionType || JSON.stringify(request.payload) !== JSON.stringify(payload)) {
        setPendingAction(request);
        setError('Retry the exact saved action before continuing.');
        return;
      }
    } else {
      request = {
        event_id: hybridUid(), sequence: sequence.current, action_type: actionType, payload,
        elapsed_ms: Math.round(performance.now() - startedAt.current),
      };
      localStorage.setItem(storageKey, JSON.stringify(request));
    }
    actionInflight.current = true;
    setPendingAction(request);
    setBusy(true);
    setError(null);
    try {
      await recordHybridAction(attempt.attempt_id, request);
      localStorage.removeItem(storageKey);
      sequence.current = request.sequence + 1;
      setPendingAction(null);
      setError('');
      applyAcceptedAction(request);
      emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'checkpoint',text:'That game action was saved. Continue when you are ready.'});
    } catch (caught) {
      setPendingAction(request);
      setError(caught instanceof Error ? caught.message : 'The action could not be recorded. Retry the exact saved action.');
    } finally {
      actionInflight.current = false;
      setBusy(false);
    }
  }, [applyAcceptedAction, attempt, onCheckpoint, sessionId, activity.activity_id]);

  const sendMove = useCallback(async (direction: Direction) => {
    if (!attempt || !config || phase !== 'play' || busy || recovering || completionPending || pendingAction) return;
    const [dx, dy] = DIRECTION_VECTOR[direction];
    const [x, y] = position;
    const next: [number, number] = [x + dx, y + dy];
    const inside = next[0] >= 0 && next[0] < config.board.cols && next[1] >= 0 && next[1] < config.board.rows;
    if (!inside || walls.has(key(next[0], next[1]))) {
      setBlocked(value => value + 1);
      return;
    }
    await submitAction('move', { direction });
  }, [attempt, busy, recovering, completionPending, config, pendingAction, phase, position, submitAction, walls]);

  const deliver = useCallback(async () => {
    if (!attempt || !carried || phase !== 'play' || busy || recovering || completionPending || pendingAction) return;
    await submitAction('deliver', { parcel_id: carried });
  }, [attempt, busy, recovering, completionPending, carried, pendingAction, phase, submitAction]);

  const askForReminder = useCallback(async () => {
    if (!attempt || busy || recovering || completionPending || pendingAction) return;
    setBusy(true);
    setError(null);
    try {
      // The exposure is recorded before any promise text is shown again.
      const request = {
        event_id: hybridUid(),
        exposure_kind: 'intention_reminder',
        checkpoint: 'safe_checkpoint',
        checkpoint_version: '1',
      };
      await recordHybridAssistance(attempt.attempt_id, request);
      setAssisted(true);
      setReminder(true);
      emitCompanionCheckpoint(onCheckpoint,{id:request.event_id,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'assistance',text:'The recorded intention reminder is available with this checkpoint.'});
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Assistance is not available right now.');
    } finally {
      setBusy(false);
    }
  }, [attempt, busy, recovering, completionPending, pendingAction, onCheckpoint, sessionId, activity.activity_id]);

  const finish = useCallback(async (interrupted = false) => {
    if (!attempt || busy || completionInflight.current) return;
    if (pendingAction || localStorage.getItem(pendingActionKey(attempt.attempt_id))) {
      setError('Retry the exact saved action before completing this attempt.');
      return;
    }
    completionInflight.current = true;
    setBusy(true);
    setError(null);
    const completionKey = `hy-pending-completion:${attempt.attempt_id}`;
    let raw = localStorage.getItem(completionKey);
    let request: { event_id: string; interrupted: boolean; response_time_ms: number | null };
    if (raw) {
      request = JSON.parse(raw);
      if (request.interrupted !== interrupted) {
        setError('A completion is already pending; retry its exact saved request.');
        setBusy(false);
        completionInflight.current = false;
        return;
      }
    } else {
      request = {
        event_id: hybridUid(),
        interrupted,
        response_time_ms: startedAt.current ? Math.round(performance.now() - startedAt.current) : null,
      };
      localStorage.setItem(completionKey, JSON.stringify(request));
    }
    try {
      const result = await completeHybridAttempt(attempt.attempt_id, request);
      localStorage.removeItem(completionKey);
      localStorage.removeItem(activeAttemptKey);
      localStorage.removeItem(`hy-courier-phase:${attempt.attempt_id}`);
      localStorage.removeItem(`hy-courier-encode-start:${attempt.attempt_id}`);
      setOutcome(result);
      setPhase('review');
      if(!interrupted)emitCompanionCheckpoint(onCheckpoint,{id:`${attempt.attempt_id}:completed`,sessionId,activityId:activity.activity_id,attemptId:attempt.attempt_id,kind:'completed',text:'The activity is complete. The saved outcome is ready to review.'});
      onRecorded();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The attempt could not be completed.');
    } finally {
      completionInflight.current = false;
      setBusy(false);
    }
  }, [activeAttemptKey, attempt, busy, onRecorded, pendingAction, onCheckpoint, sessionId, activity.activity_id]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const direction = KEY_TO_DIRECTION[event.key];
    if (!direction) return;
    event.preventDefault();
    void sendMove(direction);
  };

  const remaining = config ? config.parcels.length - deliveries : 0;
  const canDeliver = Boolean(destinationCells.has(key(position[0], position[1])));

  return (
    <section className="hy-game" aria-label={`${activity.title} activity`}>
      <header className="hy-game-header">
        <div>
          <p className="hy-eyebrow">Hybrid · {activity.world}</p>
          <h1>{activity.title}</h1>
          <p className="hy-sub">{activity.summary}</p>
        </div>
        <div className="hy-game-header-actions">
          <span className={`hy-chip ${assisted ? 'is-warn' : ''}`}>
            {outcome?.completion_state === 'interrupted' ? 'Interrupted attempt' : assisted ? 'Assisted attempt' : 'Unassisted attempt'}
          </span>
          <button type="button" className="hy-ghost" onClick={() => (phase === 'play' || phase === 'encode' ? void finish(true) : onExit())}>
            <X size={16} /> {phase === 'play' || phase === 'encode' ? 'Leave and record' : 'Back to hybrid lab'}
          </button>
        </div>
      </header>

      {error && (
        <p className="hy-error" role="alert">
          {error}
          {pendingAction && <button type="button" className="hy-ghost" disabled={busy} onClick={() => void submitAction(pendingAction.action_type, pendingAction.payload)}>Retry exact saved action</button>}
          {!pendingAction && localStorage.getItem(startRequestKey) && <button type="button" className="hy-ghost" disabled={busy} onClick={() => void begin()}>Retry exact saved start</button>}
          {!pendingAction && localStorage.getItem(activeAttemptKey) && <button type="button" className="hy-ghost" disabled={busy} onClick={() => setRecoveryTick(value => value + 1)}>Retry saved progress refresh</button>}
        </p>
      )}

      {phase === 'ready' && (
        <div className="hy-panel">
          <h2>Choose the garden</h2>
          <p>
            You will be shown {tier === 'tutorial' ? 'one delivery promise' : 'remembered delivery promises'} for a few
            seconds. The garden then hides them: walk, pick up the parcels and deliver each one only when its promise
            allows it.
          </p>
          <div className="hy-tiers" role="radiogroup" aria-label="Difficulty">
            {TIERS.map(option => (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={tier === option.id}
                className={`hy-tier ${tier === option.id ? 'is-selected' : ''}`}
                onClick={() => setTier(option.id)}
              >
                <strong>{option.label}</strong>
                <span>{option.detail}</span>
              </button>
            ))}
          </div>
          <div className="hy-policy">
            <CircleHelp size={16} />
            <span>
              A reminder that reveals a promise marks this attempt as assisted and excludes it from unassisted summaries.
              Assistance is offered before play and at safe checkpoints, never silently.
            </span>
          </div>
          <button type="button" className="hy-primary" onClick={() => void begin()} disabled={busy || recovering}>
            <Flag size={16} /> {recovering ? 'Restoring…' : busy ? 'Preparing…' : 'Start attempt'}
          </button>
        </div>
      )}

      {phase === 'encode' && config && (
        <div className="hy-panel hy-encode">
          <h2>Remember your promises</h2>
          <p className="hy-countdown" role="status">
            Garden opens in {countdown}s
          </p>
          <ol className="hy-promises">
            {[...config.plans].sort((a, b) => a.order - b.order).map(plan => (
              <li key={plan.parcel_id}>
                <Package size={16} />
                <span>{formatPromise(plan)}</span>
              </li>
            ))}
          </ol>
          <button type="button" className="hy-ghost" onClick={() => {
            if (attempt) localStorage.setItem(`hy-courier-phase:${attempt.attempt_id}`, 'play');
            startedAt.current = performance.now();
            setPhase('play');
          }}>
            Start walking now
          </button>
        </div>
      )}

      {phase === 'play' && config && attempt && (
        <div className="hy-courier-stage">
          <aside className="hy-courier-promises" aria-label="Promise visibility">
            <div className="hy-courier-card-heading">
              <span className="hy-eyebrow">Courier notes</span>
              <h2>{reminder ? 'Recorded reminder' : 'Your promises'}</h2>
            </div>
            {reminder ? (
              <ol className="hy-courier-promise-list">
                {[...config.plans].sort((a, b) => a.order - b.order).map(plan => (
                  <li key={plan.parcel_id}><span className="hy-courier-seal" aria-hidden="true"><Package size={18} /></span><span>{formatPromise(plan)}</span></li>
                ))}
              </ol>
            ) : (
              <div className="hy-courier-sealed">
                <span className="hy-courier-seal" aria-hidden="true"><Package size={19} /></span>
                <p>The remembered promises are hidden while you walk.</p>
                <small>Use the recorded reminder at a safe checkpoint if you want to see them again.</small>
              </div>
            )}
          </aside>

          <div className="hy-courier-board-area">
            <div className="hy-board-wrap">
            <div
              className="hy-board"
              role="grid"
              aria-label={`Garden for ${activity.title}: ${config.board.cols} columns by ${config.board.rows} rows`}
              tabIndex={0}
              onKeyDown={onKeyDown}
              ref={boardRef}
              style={{ gridTemplateColumns: `repeat(${config.board.cols}, minmax(0, 1fr))` }}
            >
              {Array.from({ length: config.board.rows }, (_, y) =>
                Array.from({ length: config.board.cols }, (_, x) => {
                  const cellKey = key(x, y);
                  const isWall = walls.has(cellKey);
                  const isPawn = position[0] === x && position[1] === y;
                  const parcel = parcelCells.get(cellKey);
                  const parcelHiddenForV2 = config.activity_version === 'hy-01-v2'
                    && (parcel === carried || deliveredParcels.includes(parcel ?? ''));
                  const showParcel = Boolean(parcel && !isPawn && !parcelHiddenForV2);
                  const destination = destinationCells.get(cellKey);
                  const gate = gateCells.get(cellKey);
                  const parts = [isWall ? 'hedge' : 'path'];
                  if (gate) parts.push(`gate ${gate}`);
                  if (destination) parts.push(`plot ${destination.split('-')[1]}`);
                  if (showParcel && parcel) parts.push(parcelLabel(parcel));
                  if (isPawn) parts.push('courier');
                  return (
                    <div
                      key={cellKey}
                      role="gridcell"
                      aria-label={`Column ${x + 1}, row ${y + 1}: ${parts.join(', ')}`}
                      className={`hy-cell ${isWall ? 'is-wall' : ''} ${destination ? 'is-plot' : ''} ${gate ? 'is-gate' : ''}`}
                    >
                      {destination && <Flag className="hy-plot-flag" size={18} aria-hidden />}
                      {gate && <span className="hy-gate-mark" aria-hidden>{gate === 'gate-a' ? 'A' : 'B'}</span>}
                      {showParcel && parcel && (
                        <span className="hy-parcel-token" aria-label={parcelLabel(parcel)}>
                          <Package className="hy-parcel" size={16} aria-hidden />
                          <span>{parcelLabel(parcel).replace('Parcel ', '')}</span>
                        </span>
                      )}
                      {isPawn && <span className="hy-courier" aria-hidden />}
                    </div>
                  );
                }),
              )}
            </div>
            <p className="hy-board-help">
              Arrow keys or WASD to walk · you pick a parcel up by stepping on it · deliver only while standing on its plot.
            </p>
          </div>
          </div>

          <aside className="hy-hud hy-courier-coach" aria-label="Courier coach and status">
            <div className="hy-courier-coach-heading"><span className="hy-eyebrow">Coach</span><strong>Plan your next move</strong></div>
            <div className="hy-hud-row">
              <span>Carrying</span>
              <strong>{carried ? parcelLabel(carried) : 'nothing'}</strong>
            </div>
            <div className="hy-hud-row">
              <span>Plots visited</span>
              <strong>{deliveries} of {config.parcels.length}</strong>
            </div>
            <div className="hy-hud-row">
              <span>Moves</span>
              <strong>{moves}</strong>
            </div>
            <div className="hy-hud-row">
              <span>Gates passed</span>
              <strong>{gatesSeen.length ? gatesSeen.join(', ') : 'none'}</strong>
            </div>
            <div className={`hy-hud-row ${bellRang ? 'is-loud' : ''}`}>
              <Bell size={15} />
              <strong>{bellRang ? `bell rang at move ${config.bell.after_moves}` : `bell rings after move ${config.bell.after_moves}`}</strong>
            </div>
            {blocked > 0 && <p className="hy-hint-line">{blocked} blocked step{blocked === 1 ? '' : 's'} (hedges).</p>}
            <button type="button" className="hy-ghost" onClick={() => void askForReminder()} disabled={busy || recovering || completionPending || Boolean(pendingAction)}>
              <CircleHelp size={16} /> Review clue · recorded assistance
            </button>
          </aside>

          <nav className="hy-courier-dock" aria-label="Courier controls">
            <div className="hy-courier-dock-note" role="status">
              <span className="hy-eyebrow">Route status</span>
              <strong>{remaining} promise{remaining === 1 ? '' : 's'} remaining</strong>
              <small>Progress is evaluated from saved actions.</small>
            </div>
            <div className="hy-movepad" role="group" aria-label="Walk">
              <button type="button" className="hy-move is-up" aria-label="Walk up" onClick={() => void sendMove('up')} disabled={busy || recovering || completionPending || Boolean(pendingAction)}><ArrowUp size={18} /></button>
              <button type="button" className="hy-move is-left" aria-label="Walk left" onClick={() => void sendMove('left')} disabled={busy || recovering || completionPending || Boolean(pendingAction)}><ArrowLeft size={18} /></button>
              <button type="button" className="hy-move is-down" aria-label="Walk down" onClick={() => void sendMove('down')} disabled={busy || recovering || completionPending || Boolean(pendingAction)}><ArrowDown size={18} /></button>
              <button type="button" className="hy-move is-right" aria-label="Walk right" onClick={() => void sendMove('right')} disabled={busy || recovering || completionPending || Boolean(pendingAction)}><ArrowRight size={18} /></button>
            </div>
            <div className="hy-courier-dock-actions">
              <button type="button" className="hy-primary" onClick={() => void deliver()} disabled={busy || recovering || completionPending || Boolean(pendingAction) || !carried || !canDeliver}><Check size={16} /> Deliver here</button>
              <button type="button" className="hy-ghost" onClick={() => void finish(false)} disabled={busy || recovering || completionPending || Boolean(pendingAction)}><Flag size={16} /> Finish and review</button>
            </div>
          </nav>
        </div>
      )}

      {phase === 'review' && outcome && (
        <div className="hy-panel hy-review">
          <h2>{outcome.completion_state === 'interrupted' ? 'Attempt recorded as interrupted' : 'Attempt complete'}</h2>
          <p className={`hy-chip ${outcome.excluded_from_unassisted ? 'is-warn' : 'is-ok'}`}>
            {outcome.completion_state === 'interrupted' ? 'Interrupted — excluded from unassisted summaries' : outcome.assisted ? 'Assisted — excluded from unassisted summaries' : 'Unassisted attempt'}
          </p>
          <dl className="hy-stats">
            <div><dt>Promises kept</dt><dd>{outcome.outcomes.promises_satisfied} / {outcome.outcomes.promises_total}</dd></div>
            <div><dt>Wrong-plot deliveries</dt><dd>{outcome.outcomes.wrong_destination_deliveries}</dd></div>
            <div><dt>Cue misses</dt><dd>{outcome.outcomes.cue_misses}</dd></div>
            <div><dt>Order deviations</dt><dd>{outcome.outcomes.order_deviations}</dd></div>
            <div><dt>Moves</dt><dd>{outcome.outcomes.moves} (lower bound {outcome.outcomes.optimal_moves})</dd></div>
            <div><dt>Detour</dt><dd>{outcome.outcomes.path_overhead}</dd></div>
          </dl>
          <ol className="hy-promises">
            {outcome.outcomes.promises.map(promise => (
              <li key={promise.parcel_id} className={promise.satisfied ? 'is-met' : 'is-missed'}>
                {promise.satisfied ? <Check size={16} /> : <X size={16} />}
                <span>
                  {formatPromise(promise)}
                  <em>{promise.reason}</em>
                </span>
              </li>
            ))}
          </ol>
          <p className="hy-hint-line">
            {outcome.evidence_ids.length} immutable evidence records · evaluation {outcome.evaluation_version} · activity{' '}
            {outcome.activity_version}
          </p>
          <ul className="hy-limits">
            {outcome.limitations.map(limit => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
          <div className="hy-review-actions">
            <button type="button" className="hy-primary" onClick={() => void begin()} disabled={busy}>
              <RotateCcw size={16} /> Attempt again
            </button>
            <button type="button" className="hy-ghost" onClick={onExit}>
              Back to hybrid lab
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
