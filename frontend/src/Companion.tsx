import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { CompanionSpeech, type CompanionSpeechPhase } from './CompanionSpeech';
import type { CompanionCheckpointSpeech } from './CompanionSpeech';
import { CompanionCoach } from './redesign/companion/CompanionCoach';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react';
import './companion.css';

type CompanionProps = {
  page: string;
  phase?: string;
  decision: any;
  sessionId: string | null;
  itemId?: string;
  blockId: string | null;
  quietTask?: boolean;
  checkpoint?: CompanionCheckpointSpeech | null;
  onRecorded: () => void;
  onCoachNavigate?: (target: string) => void;
  onCoachRequestStrategy?: (strategyId: string, exerciseId: string | null) => void;
  onCoachAction?: (selection: {
    requestId: string;
    actionId: string;
    target?: string;
    strategyId?: string;
    exerciseId?: string | null;
  }) => void | Promise<void>;
};

type Corner = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
type CoachResponse = {
  source?: string;
  evidence_revision?: string;
  spoken_summary?: string | null;
  subject?: { exercise_id?: string | null; dimension?: string | null; label?: string | null };
  response?: {
    observation?: string;
    explanation?: string;
    rationale?: string;
    caveat?: string;
    evidence_ids?: string[];
    strategy_id?: string | null;
    recommended_exercise_id?: string | null;
    recommended_difficulty?: string | null;
    follow_up?: string;
  };
  opportunities?: Array<{ opportunity?: { prompt?: string; dimension?: string; opportunity_id?: string }; replayed?: boolean }>;
};

const HIDDEN_KEY = 'ai4brain.companion';
const CORNER_KEY = 'ai4brain.companion.corner';
const START_CORNER: Corner = 'bottom-right';
const DIMENSIONS: Record<string, string> = {
  'EX-01': 'Memory', 'EX-02': 'Reasoning', 'EX-03': 'Attention & inhibition',
  'EX-04': 'Flexibility', 'EX-05': 'Planning',
};

function isCorner(value: string | null): value is Corner {
  return value === 'top-left' || value === 'top-right' || value === 'bottom-left' || value === 'bottom-right';
}

function useSavedCorner(): [Corner, (value: Corner) => void] {
  const [corner, setCorner] = useState<Corner>(() => {
    const value = window.localStorage.getItem(CORNER_KEY);
    return isCorner(value) ? value : START_CORNER;
  });
  const save = (value: Corner) => {
    setCorner(value);
    window.localStorage.setItem(CORNER_KEY, value);
  };
  return [corner, save];
}

async function postCoach(body: Record<string, unknown>, signal?: AbortSignal): Promise<CoachResponse> {
  const response = await fetch('/api/coach', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error('coach-unavailable');
  return response.json() as Promise<CoachResponse>;
}

function humanStatus(source?: string): string | null {
  if (source === 'local_fallback') return 'Local coach';
  if (source === 'configured_provider') return 'Evidence checked';
  return null;
}

export default function Companion({
  page,
  phase,
  checkpoint = null,
  decision,
  sessionId,
  itemId,
  blockId,
  quietTask = false,
  onRecorded,
  onCoachNavigate,
  onCoachRequestStrategy,
  onCoachAction,
}: CompanionProps) {
  const [corner, saveCorner] = useSavedCorner();
  const [hidden, setHidden] = useState(() => window.localStorage.getItem(HIDDEN_KEY) === 'hidden');
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<'quick' | 'conversation'>('quick');
  const [message, setMessage] = useState('');
  const [coach, setCoach] = useState<CoachResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [blink, setBlink] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [speechPhase, setSpeechPhase] = useState<CompanionSpeechPhase>('idle');
  const [speechCancelToken, setSpeechCancelToken] = useState(0);
  const [conversationSpeech, setConversationSpeech] = useState<{ text: string; key: string; evidenceRevision?: string; subject?: string }>({ text: '', key: '' });
  const [invitationDismissed, setInvitationDismissed] = useState(false);
  const coachRequest = useRef(0);
  const coachAbort = useRef<AbortController | null>(null);
  const coachOwner = useRef('');
  const autoSpokenOwner = useRef('');
  const contextKey = `${sessionId ?? ''}|${page}|${phase ?? ''}|${blockId ?? ''}|${itemId ?? ''}`;
  const dragOrigin = useRef<{ x: number; y: number; pointerId: number } | null>(null);
  const wasDragged = useRef(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLElement>(null);
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const reducedMotion = useReducedMotion();
  const quiet = quietTask || phase === 'quiet' || phase === 'scored' || (
    page === 'assessment' && (phase === 'baseline' || phase === 'reassessment')
  );
  const coachAllowed = !quiet && Boolean(sessionId) && (
    ['welcome', 'overview', 'plan', 'brain', 'collaboration', 'hybrid'].includes(page) || page === 'practice' ||
    (page === 'assessment' && phase === 'practice')
  );
  const coachPhase = (page === 'practice' && Boolean(decision)) || ['welcome', 'overview', 'plan', 'brain', 'collaboration', 'hybrid'].includes(page)
    ? 'overview'
    : phase === 'training' ? 'training' : 'practice';
  const completedTrainingDecision = page === 'practice' && Boolean(
    decision?.old_tier && decision?.new_tier && decision?.rationale && decision?.trial_count === 4 &&
    decision?.valid_trial_count === 4 && Array.isArray(decision?.evidence_ids) && decision.evidence_ids.length === 4 &&
    (decision?.action === 'up' || decision?.action === 'down'),
  );
  const state = quiet ? 'quiet' : loading || speechPhase === 'preparing' ? 'thinking' : speechPhase === 'playing' ? 'speaking' : completedTrainingDecision && decision.action === 'up' ? 'success' : open ? 'looking' : 'idle';
  const eyeX = useSpring(useMotionValue(0), { stiffness: 230, damping: 22, mass: 0.4 });
  const eyeY = useSpring(useMotionValue(0), { stiffness: 230, damping: 22, mass: 0.4 });
  const dockRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    coachRequest.current += 1;
    coachAbort.current?.abort();
    setCoach(null);
    setLoading(false);
    setError(false);
    setSpeechPhase('idle');
    setConversationSpeech({ text: '', key: '' });
    setInvitationDismissed(false);
    setOpen(false);
    return () => { coachRequest.current += 1; coachAbort.current?.abort(); };
  }, [contextKey, quiet]);

  useEffect(() => {
    if (!hidden && open) return;
    coachRequest.current += 1;
    coachAbort.current?.abort(hidden ? 'companion-hidden' : 'companion-closed');
    coachAbort.current = null;
    setLoading(false);
  }, [hidden, open]);
  useEffect(()=>{
    const onVisibility=()=>{if(document.visibilityState==='hidden'){coachRequest.current+=1;coachAbort.current?.abort('page-hidden');coachAbort.current=null;setLoading(false);}};
    document.addEventListener('visibilitychange',onVisibility);
    return()=>document.removeEventListener('visibilitychange',onVisibility);
  },[]);

  useEffect(() => {
    if (!open || hidden) setSpeechPhase('idle');
  }, [open, hidden]);

  useEffect(() => {
    const header = document.querySelector<HTMLElement>('.top-nav');
    let frame = 0;
    const measure = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        const bottom = header?.getBoundingClientRect().bottom ?? 76;
        dockRef.current?.style.setProperty('--companion-header-bottom', `${Math.max(0, Math.ceil(bottom))}px`);
      });
    };
    measure();
    const observer = header && typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (header && observer) observer.observe(header);
    window.addEventListener('resize', measure, { passive: true });
    window.addEventListener('scroll', measure, { passive: true, capture: true });
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    if (quiet || reducedMotion || hidden) return;
    let blinkTimer = 0;
    let openTimer = 0;
    const schedule = () => {
      blinkTimer = window.setTimeout(() => {
        setBlink(true);
        openTimer = window.setTimeout(() => setBlink(false), 135);
        schedule();
      }, 3200 + Math.random() * 2200);
    };
    schedule();
    return () => { window.clearTimeout(blinkTimer); window.clearTimeout(openTimer); };
  }, [quiet, reducedMotion, hidden]);

  useEffect(() => {
    if (quiet || !open) return;
    const focusTimer = window.setTimeout(() => messageRef.current?.focus(), 120);
    return () => window.clearTimeout(focusTimer);
  }, [quiet, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      setOpen(false);
      window.requestAnimationFrame(() => triggerRef.current?.focus());
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    if (quiet) setOpen(false);
  }, [quiet]);

  useEffect(() => {
    if (quiet || reducedMotion || hidden) {
      eyeX.jump(0);
      eyeY.jump(0);
      return;
    }
    let frame = 0;
    let clientX = window.innerWidth / 2;
    let clientY = window.innerHeight / 2;
    const move = (event: PointerEvent) => {
      const origin = dragOrigin.current;
      if (origin) {
        if (Math.hypot(event.clientX - origin.x, event.clientY - origin.y) >= 8) setDragging(true);
        return;
      }
      clientX = event.clientX;
      clientY = event.clientY;
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        const trigger = triggerRef.current;
        if (!trigger || dragOrigin.current) return;
        const rect = trigger.getBoundingClientRect();
        eyeX.set(Math.max(-2.6, Math.min(2.6, (clientX - rect.left - rect.width / 2) / 25)));
        eyeY.set(Math.max(-1.8, Math.min(1.8, (clientY - rect.top - rect.height / 2) / 25)));
      });
    };
    window.addEventListener('pointermove', move, { passive: true });
    return () => {
      window.removeEventListener('pointermove', move);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [quiet, reducedMotion, hidden, eyeX, eyeY]);

  const reposition = (next: Corner) => saveCorner(next);
  const dockBy = (key: string) => {
    if (quiet) return;
    const vertical = key === 'ArrowUp' ? 'top' : key === 'ArrowDown' ? 'bottom' : corner.startsWith('top') ? 'top' : 'bottom';
    const horizontal = key === 'ArrowLeft' ? 'left' : key === 'ArrowRight' ? 'right' : corner.endsWith('left') ? 'left' : 'right';
    reposition(`${vertical}-${horizontal}` as Corner);
  };

  const hide = () => {
    window.localStorage.setItem(HIDDEN_KEY, 'hidden');
    setHidden(true);
    setOpen(false);
  };
  const show = () => {
    window.localStorage.removeItem(HIDDEN_KEY);
    setHidden(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const handleConversationReply = useCallback((text: string, replyKey: string, context?: { evidenceRevision?: string; subject?: string }) => {
    setConversationSpeech({ text, key: `${contextKey}|conversation|${replyKey}`, ...context });
  }, [contextKey]);
  const stopCoachAndSpeech = useCallback(() => {
    coachRequest.current += 1;
    coachAbort.current?.abort('learner-stopped');
    coachAbort.current = null;
    setLoading(false);
    setSpeechCancelToken(value=>value+1);
  }, []);

  const ask = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const clean = message.trim();
    if (!sessionId || clean.length < 3 || !coachAllowed || quiet || loading) return;
    if (coachPhase === 'training' && (!blockId || !itemId)) { setError(true); return; }
    setLoading(true);
    setError(false);
    setCoach(null);
    const generation = ++coachRequest.current;
    coachAbort.current?.abort();
    const controller = new AbortController();
    coachAbort.current = controller;
    const body: Record<string, unknown> = {
      session_id: sessionId,
      message: clean,
      allow_remote: false,
      phase: coachPhase,
    };
    if (coachPhase === 'training') {
      if (blockId) body.training_block_id = blockId;
      if (itemId) body.item_id = itemId;
    }
    try {
      const result = await postCoach(body, controller.signal);
      if (controller.signal.aborted || generation !== coachRequest.current) return;
      coachOwner.current = contextKey;
      setCoach(result);
      onRecorded();
    } catch {
      if (!controller.signal.aborted && generation === coachRequest.current) setError(true);
    } finally {
      if (generation === coachRequest.current) setLoading(false);
    }
  };

  if (hidden) {
    return <button className="companion-restore" type="button" onClick={show}>Show companion</button>;
  }

  const response = coachOwner.current === contextKey ? coach?.response : undefined;
  const spokenText = response
    ? [response.observation, response.explanation, response.rationale, response.follow_up, response.caveat]
        .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
        .join(' ')
    : '';
  const status = humanStatus(coach?.source);
  const trainingDecisionText = completedTrainingDecision
    ? `${String(decision.old_tier).replaceAll('-', ' ')} to ${String(decision.new_tier).replaceAll('-', ' ')}. ${decision.rationale}`
    : null;
  const invitationText = completedTrainingDecision
    ? decision.action === 'up'
      ? 'This block is complete. You can choose another practice step when you are ready.'
      : 'This block is complete. You can choose a different strategy or focus when you are ready.'
    : null;
  const speechText = mode === 'conversation' ? conversationSpeech.text : (coach?.spoken_summary ?? spokenText);
  const speechReplyKey = mode === 'conversation' ? conversationSpeech.key : `${contextKey}|quick|${coachRequest.current}`;
  const speechContext = mode === 'conversation'
    ? { evidenceRevision: conversationSpeech.evidenceRevision, subject: conversationSpeech.subject }
    : { evidenceRevision: coach?.evidence_revision, subject: coach?.subject?.exercise_id ?? undefined };
  const boxVariants = {
    idle: { scaleX: 1, scaleY: 1, y: 0 },
    looking: { scaleX: 1.015, scaleY: 0.98, y: -1 },
    thinking: { scaleX: 0.985, scaleY: 1.018, y: -1 },
    speaking: { scaleX: [1, 1.025, 1], scaleY: [1, 0.98, 1], y: [0, -1, 0] },
    quiet: { scaleX: 1, scaleY: 1, y: 0 },
    success: { scaleX: [1, 1.03, 1], scaleY: [1, 0.98, 1], y: [0, -1, 0] },
  };

  return (
    <div ref={dockRef} className={`companion-dock companion-${corner}${open ? ' companion-open' : ''}${quiet ? ' companion-is-quiet' : ''}`}>
      {open && (
        <section ref={popoverRef} className="companion-card" role="dialog" aria-labelledby={titleId}>
          <header className="companion-card-header">
            <strong id={titleId}>{coachAllowed ? 'Need a hand?' : 'Your companion'}</strong>
            <button className="companion-icon-button" type="button" aria-label="Close companion panel" onClick={() => {
              setOpen(false);
              window.requestAnimationFrame(() => triggerRef.current?.focus());
            }}>×</button>
          </header>
          {trainingDecisionText && <p className="companion-decision" role="status">{trainingDecisionText}</p>}
          {invitationText && !invitationDismissed && (
            <aside className="companion-decision" role="status">
              <span>{invitationText}</span>
              <button type="button" className="companion-hide" onClick={() => setInvitationDismissed(true)}>Not now</button>
            </aside>
          )}
          {coachAllowed && (
            <div className="companion-mode-tabs" role="tablist" aria-label="Companion mode">
              <button type="button" role="tab" aria-selected={mode === 'quick'} className={mode === 'quick' ? 'is-active' : ''}
                onClick={() => setMode('quick')}>Quick answer</button>
              <button type="button" role="tab" aria-selected={mode === 'conversation'} className={mode === 'conversation' ? 'is-active' : ''}
                onClick={() => setMode('conversation')}>Conversation</button>
            </div>
          )}
          {coachAllowed && mode === 'conversation' ? (
            <CompanionCoach
              sessionId={sessionId as string}
              focusExerciseId={decision?.exercise_id ?? null}
              phase={phase === 'training' ? 'training' : page === 'practice' ? 'practice' : 'overview'}
              trainingBlockId={blockId}
              itemId={itemId ?? null}
              quiet={quiet}
              onNavigate={onCoachNavigate}
              onRequestStrategy={onCoachRequestStrategy}
              onActionSelected={onCoachAction}
              onReplyText={handleConversationReply}
              cancelToken={speechCancelToken}
              onClose={() => setMode('quick')}
              onTurnRecorded={onRecorded}
            />
          ) : coachAllowed ? (
            <>
              <p className="companion-invite">Ask about recorded evidence or your next practice step.</p>
              <form className="companion-form" onSubmit={(event) => void ask(event)}>
                <label htmlFor={`${titleId}-message`}>Your question</label>
                <textarea
                  ref={messageRef}
                  id={`${titleId}-message`}
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  maxLength={500}
                  rows={3}
                  placeholder="What would you like to understand?"
                  disabled={loading}
                />
                <button type="submit" className="companion-ask" disabled={message.trim().length < 3 || loading || (coachPhase === 'training' && (!blockId || !itemId))}>
                  {loading ? 'Reviewing saved evidence…' : 'Ask a question'}
                </button>
              </form>
              {error && <p className="companion-error" role="alert">The local coach is unavailable right now. Your question was not sent anywhere else. Try again shortly.</p>}
              {response && (
                <div className="companion-answer" aria-live="polite">
                  {status && <p className="companion-source">{status}</p>}
                  {response.observation && <p><strong>Recorded observation</strong>{response.observation}</p>}
                  {response.explanation && <p>{response.explanation}</p>}
                  {response.recommended_exercise_id && <p><strong>Suggested activity</strong>{DIMENSIONS[response.recommended_exercise_id] ?? 'A saved task'}{response.recommended_difficulty ? ` · ${response.recommended_difficulty.replaceAll('-', ' ')}` : ''}</p>}
                  {response.rationale && <p><strong>Why this suggestion</strong>{response.rationale}</p>}
                  {response.strategy_id && <p><strong>Practice strategy</strong>{response.strategy_id.replaceAll('_', ' ')}</p>}
                  {response.follow_up && <p>{response.follow_up}</p>}
                  {response.caveat && <p className="companion-caveat">{response.caveat}</p>}
                  {response.evidence_ids?.length ? <details className="companion-evidence">
                    <summary>View linked evidence ({response.evidence_ids.length})</summary>
                    <ul>{response.evidence_ids.map((id) => <li key={id}><code>{id}</code></li>)}</ul>
                  </details> : null}
                  {coach?.opportunities?.some((row) => typeof row.opportunity?.prompt === 'string' && row.opportunity.prompt.trim()) && (
                    <details className="companion-opportunities">
                      <summary>See available follow-ups</summary>
                      <ul>{coach.opportunities.map((row) => {
                        const opportunity = row.opportunity;
                        if (!opportunity || typeof opportunity.prompt !== 'string' || !opportunity.prompt.trim()) return null;
                        return <li key={opportunity.opportunity_id ?? opportunity.prompt}>{opportunity.prompt}</li>;
                      })}</ul>
                    </details>
                  )}
                </div>
              )}
            </>
          ) : <p className="companion-invite">{sessionId ? 'Return to Home or Insights to ask about your saved evidence.' : 'Start a local session to ask about your results or practice.'}</p>}
          {!quiet && <div className="companion-controls">
            <label htmlFor={`${titleId}-corner`}>Move companion to a corner</label>
            <select id={`${titleId}-corner`} value={corner} onChange={(event) => reposition(event.target.value as Corner)}>
              <option value="top-left">Top left</option><option value="top-right">Top right</option>
              <option value="bottom-left">Bottom left</option><option value="bottom-right">Bottom right</option>
            </select>
            <button type="button" className="companion-hide" onClick={hide}>Hide companion</button>
          </div>}
        </section>
      )}
      <CompanionSpeech sessionId={sessionId} text={speechText} quiet={quiet || hidden} titleId={titleId}
        visible={open && coachAllowed && !hidden} onPhaseChange={setSpeechPhase} replyKey={speechReplyKey}
        ownershipKey={contextKey} onStop={stopCoachAndSpeech} autoSpokenOwner={autoSpokenOwner} speechContext={speechContext} checkpoint={checkpoint}/>
      <motion.button
        ref={triggerRef}
        type="button"
        className={`companion-trigger${quiet ? ' is-quiet' : ''}${dragging ? ' is-dragging' : ''}`}
        aria-label={quiet ? 'Companion resting during active task' : open ? 'Close companion options' : 'Open companion options'}
        aria-expanded={open}
        aria-describedby={`${titleId}-hint`}
        title={quiet ? 'Quiet during active task' : "Ready when you're ready · drag to move"}
        animate={boxVariants[state]}
        transition={quiet || reducedMotion
          ? { duration: 0 }
          : state === 'thinking' || state === 'speaking' || state === 'success'
          ? { type: 'spring', stiffness: 330, damping: 20, duration: 0.8 }
          : { type: 'spring', stiffness: 430, damping: 29, duration: 0.55 }}
        onClick={() => {
          if (quiet || wasDragged.current) { wasDragged.current = false; return; }
          setOpen((value) => !value);
        }}
        onPointerDown={(event) => {
          if (quiet || event.button !== 0) return;
          dragOrigin.current = { x: event.clientX, y: event.clientY, pointerId: event.pointerId };
          wasDragged.current = false;
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerUp={(event) => {
          const origin = dragOrigin.current;
          if (!origin || origin.pointerId !== event.pointerId) return;
          const dx = event.clientX - origin.x;
          const dy = event.clientY - origin.y;
          if (Math.hypot(dx, dy) >= 8) wasDragged.current = true;
          if (Math.hypot(dx, dy) >= 22) {
            const vertical = event.clientY < window.innerHeight / 2 ? 'top' : 'bottom';
            const horizontal = event.clientX < window.innerWidth / 2 ? 'left' : 'right';
            reposition(`${vertical}-${horizontal}` as Corner);
          }
          dragOrigin.current = null;
          setDragging(false);
        }}
        onPointerCancel={() => { dragOrigin.current = null; setDragging(false); }}
        onKeyDown={(event) => {
          if (quiet) return;
          if (event.key.startsWith('Arrow')) { event.preventDefault(); dockBy(event.key); }
          if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false); }
        }}
        onLostPointerCapture={() => { if (dragOrigin.current) { dragOrigin.current = null; setDragging(false); } }}
      >
        <span id={`${titleId}-hint`} className="companion-sr-only">{quiet ? 'No hints or feedback during this active task.' : 'Helpful when invited. Press Enter to ask the coach, or use arrow keys to move to a safe corner.'}</span>
        <svg className="companion-face" viewBox="0 0 80 58" aria-hidden="true" focusable="false">
          <defs>
            <radialGradient id={`${titleId}-graphite`} cx="37%" cy="19%" r="86%">
              <stop offset="0" stopColor="#56575a" />
              <stop offset="0.38" stopColor="#343538" />
              <stop offset="0.78" stopColor="#202123" />
              <stop offset="1" stopColor="#171819" />
            </radialGradient>
            <filter id={`${titleId}-shadow`} x="-45%" y="-55%" width="190%" height="210%">
              <feGaussianBlur stdDeviation="3.2" />
            </filter>
          </defs>
          <ellipse cx="40" cy="48" rx="27" ry="4.1" fill="#101114" opacity=".22" filter={`url(#${titleId}-shadow)`} />
          <motion.path
            d="M5 29.2C5 14.1 16.2 5.9 32.1 5.2c8.4-.4 13.1 1.4 16.1 1.4 4 0 6.6-1.6 11.5-.7C73.7 8.2 76 18.2 75.2 29.1c-.9 14.8-12.6 22.7-30.7 23.2-6.2.2-9.1-.5-13.7-.4C15.8 52.3 5 43.4 5 29.2Z"
            fill={`url(#${titleId}-graphite)`}
            initial={false}
            animate={state === 'success' && !reducedMotion ? { scaleX: [1, 1.02, 1], scaleY: [1, 0.98, 1] } : { scaleX: 1, scaleY: 1 }}
            transition={quiet || reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 310, damping: 21, duration: 0.75 }}
            style={{ transformOrigin: 'center' }}
          />
          {quiet ? (
            <g className="companion-closed-eyes" stroke="#fff" strokeWidth="3" strokeLinecap="round">
              <path d="M22 29h11" /><path d="M47 29h11" />
            </g>
          ) : (
            <g>
              <motion.ellipse cx="28" cy="29" rx="8.2" ry="9.2" fill="#fff" animate={{ scaleY: blink ? 0.09 : 1 }} transition={{ duration: 0.09 }} style={{ transformOrigin: '28px 29px' }} />
              <motion.ellipse cx="52" cy="29" rx="8.2" ry="9.2" fill="#fff" animate={{ scaleY: blink ? 0.09 : 1 }} transition={{ duration: 0.09 }} style={{ transformOrigin: '52px 29px' }} />
              <motion.circle cx="29.4" cy="29" r="3.35" fill="#131416" style={{ x: eyeX, y: eyeY }} />
              <motion.circle cx="53.4" cy="29" r="3.35" fill="#131416" style={{ x: eyeX, y: eyeY }} />
            </g>
          )}
          {state === 'thinking' && <circle cx="66" cy="10" r="2.1" fill="#b8c0ca" opacity=".85" />}
        </svg>
      </motion.button>
      <span className="companion-sr-only" aria-live="polite">{quiet ? 'Quiet task' : state === 'thinking' ? 'Reviewing your question' : state === 'speaking' ? 'Coach response received' : state === 'success' ? 'Training decision recorded' : ''}</span>
    </div>
  );
}
