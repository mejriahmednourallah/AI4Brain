import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { MotionConfig } from 'motion/react';
import { ArrowLeft, Pause } from 'lucide-react';
import { AttentionGame } from './redesign/games/AttentionGame';
import { FlexibilityGame } from './redesign/games/FlexibilityGame';
import { MemoryGame } from './redesign/games/MemoryGame';
import { PlanningGame } from './redesign/games/PlanningGame';
import { ReasoningGame } from './redesign/games/ReasoningGame';
import { useGameArt } from './redesign/games/useGameArt';
import './game-experience.css';

export type Exercise = {
  exercise_id: string;
  exercise_version: string;
  phase: 'practice' | 'baseline' | 'training' | 'reassessment';
  items: any[];
  instructions: string;
  difficulty_tier?: string | null;
  training_block_id?: string | null;
  decision_trial_count?: number | null;
};
export type JourneyProgress = { familyIndex: number; familyCount: number; completedFamilies?: number };
type Props = {
  exercise: Exercise;
  item: any;
  index: number;
  selected: string | null;
  setSelected: (value: string | null) => void;
  savedResponse: any;
  submitting: boolean;
  pending: boolean;
  onSubmit: (data?: Record<string, any>, choice?: string, responseTime?: number | null, stimulusOnset?: number | null) => void | Promise<void>;
  onStimulusOnset?: (onset: number | null) => void;
  resetKey: number;
  sessionStartedAt?: string | null;
  journeyProgress?: JourneyProgress;
  onPause?: (draft?: Record<string, any>) => void;
  paused?: boolean;
  onCueActivity?: (active: boolean) => void;
  /** Canonical recovery entry point: accepted saves refresh, pending saves retry exactly. */
  onRecover?: () => void;
};

const worlds: Record<string, { name: string; place: string; verb: string }> = {
  'EX-01': { name: 'Lantern Grove', place: 'A quiet trail through the grove', verb: 'Remember the route' },
  'EX-02': { name: 'Pattern Atelier', place: 'Signals across the night sky', verb: 'Complete the constellation' },
  'EX-03': { name: 'Signal Observatory', place: 'A lighthouse watches the water', verb: 'Read each signal' },
  'EX-04': { name: 'Shifting Gallery', place: 'A workshop of changing patterns', verb: 'Follow the active rule' },
  'EX-05': { name: "Wayfinder's Garden", place: 'A winding garden path', verb: 'Find your way through' },
};
const taskName: Record<string, string> = {
  'EX-01': 'Working memory', 'EX-02': 'Visual reasoning', 'EX-03': 'Attention & inhibition',
  'EX-04': 'Cognitive flexibility', 'EX-05': 'Planning',
};
const phaseName: Record<Exercise['phase'], string> = {
  practice: 'Practice', baseline: 'Baseline', training: 'Training', reassessment: 'Reassessment',
};
const familyOrder = ['EX-01', 'EX-02', 'EX-03', 'EX-04', 'EX-05'];
const familyIndex = (exerciseId: string) => familyOrder.indexOf(exerciseId);
/** The compact round count keeps the five-world position available without a progress bar. */
const journeyPosition = (journey: JourneyProgress | undefined, exerciseId: string) => {
  const atFamily = journey?.familyIndex ?? Math.max(0, familyIndex(exerciseId));
  const families = journey?.familyCount ?? familyOrder.length;
  return `World ${Math.min(atFamily + 1, families)} of ${families}`;
};
const elapsedText = (seconds: number | null) => seconds === null
  ? 'Time unavailable'
  : `Session ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

function useCommit(p: Props) {
  const locked = useRef(false);
  // The returned callback must keep a stable identity so cue windows and timers do
  // not restart, but it must never read a stale paused/submitting flag: a pause
  // cycle that leaves those dependencies untouched would otherwise memoize a
  // callback that silently swallows the trial and deadlocks the task.
  const blocked = useRef(false);
  blocked.current = Boolean(p.paused || p.submitting);
  const submit = useRef(p.onSubmit);
  submit.current = p.onSubmit;
  useEffect(() => { locked.current = false; }, [p.item.item_id, p.pending]);
  return useCallback((data?: Record<string, any>, choice?: string, responseTime?: number | null, stimulusOnset?: number | null) => {
    if (locked.current || blocked.current) return;
    locked.current = true;
    void Promise.resolve(submit.current(data, choice, responseTime, stimulusOnset)).catch(() => undefined);
  }, []);
}

function ReasoningTask({ p }: { p: Props }) {
  const { item } = p;
  const commit = useCommit(p);
  const [sendingChoice, setSendingChoice] = useState<string | null>(null);
  const choose = (id: string) => {
    if (p.pending || p.submitting || p.paused || sendingChoice) return;
    setSendingChoice(id);
    p.setSelected(id);
    commit(undefined, id);
  };
  return <div className="focused-task game-board-reasoning">
    <ReasoningGame
      pattern={(item.pattern ?? {}) as never}
      choices={(item.choices ?? []) as never}
      selected={typeof p.selected === 'string' ? p.selected : null}
      sending={Boolean(sendingChoice)}
      pending={p.pending}
      submitting={p.submitting}
      paused={Boolean(p.paused)}
      onChoose={choose}
      onRetry={() => (p.onRecover ? p.onRecover() : commit())}
    />
  </div>;
}

function MemoryTask({ p }: { p: Props }) {
  const s = p.item.stimulus ?? {};
  const seq = Array.isArray(s.sequence) ? s.sequence as number[] : [];
  const rows = Math.max(1, Number(s.rows ?? 3)), columns = Math.max(1, Number(s.columns ?? 3));
  const commit = useCommit(p);
  const [playIndex, setPlayIndex] = useState(-1);
  const [playPosition, setPlayPosition] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [watched, setWatched] = useState(false);
  const [chosen, setChosen] = useState<number[]>(p.savedResponse?.selected_sequence ?? []);
  // Presentation-only flag: the cue currently playing is an assisted replay. It never
  // changes what is recorded; the canonical payload already carries replay_count.
  const [assistedReplay, setAssistedReplay] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const commitTimer = useRef<number | undefined>(undefined);
  const chosenRef = useRef<number[]>(p.savedResponse?.selected_sequence ?? []);
  // A response may only be committed after a deliberate learner choice in this
  // attempt; restored/pending payloads alone must never auto-submit a trial.
  const armed = useRef(false);
  const replayAllowed = p.exercise.phase === 'practice' || p.exercise.phase === 'training';
  // A replayed cue is assistance. The attempt is still recorded, but it must be
  // reported so the server never counts it as unassisted evidence.
  const replayUsed = useRef(false);

  useEffect(() => {
    window.clearTimeout(timer.current);
    window.clearTimeout(commitTimer.current);
    chosenRef.current = p.savedResponse?.selected_sequence ?? [];
    armed.current = false;
    replayUsed.current = false;
    setAssistedReplay(false);
    setChosen(chosenRef.current);
    setPlayIndex(-1);
    setPlayPosition(-1);
    setWatched(false);
    setPlaying(false);
    return () => { window.clearTimeout(timer.current); window.clearTimeout(commitTimer.current); };
  }, [p.item.item_id, p.resetKey, p.pending]);

  useEffect(() => {
    if (p.paused || p.pending || playing || watched) return;
    // Own timer: the cue-playback effect clears the shared ref on every run and
    // must not cancel this startup delay.
    const startup = window.setTimeout(() => setPlaying(true), 420);
    return () => window.clearTimeout(startup);
  }, [p.paused, p.pending, playing, watched, p.item.item_id, p.resetKey]);

  useEffect(() => { if (p.paused && playing) setPlayIndex(-1); }, [p.paused, playing]);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!playing || p.pending || p.paused) return;
    let index = 0, live = true;
    const interval = Math.max(340, Number(s.playback_ms ?? 620));
    const onTime = Math.min(430, Math.round(interval * .64));
    const offTime = Math.max(105, interval - onTime);
    const next = () => {
      if (!live) return;
      if (document.visibilityState !== 'visible') { timer.current = window.setTimeout(next, 160); return; }
      if (index >= seq.length) { setPlayIndex(-1); setPlayPosition(-1); setPlaying(false); setWatched(true); return; }
      setPlayPosition(index + 1);
      setPlayIndex(seq[index]);
      timer.current = window.setTimeout(() => {
        if (!live) return;
        setPlayIndex(-1);
        timer.current = window.setTimeout(() => { index += 1; next(); }, offTime);
      }, onTime);
    };
    timer.current = window.setTimeout(next, 280);
    return () => { live = false; window.clearTimeout(timer.current); };
  }, [playing, p.item.item_id, p.resetKey, p.pending, p.paused, seq.length, s.playback_ms]);

  useEffect(() => {
    if (p.paused) { window.clearTimeout(commitTimer.current); return; }
    if (p.pending || p.submitting || !armed.current || chosenRef.current.length !== seq.length || !seq.length) return;
    const lockedSequence = [...chosenRef.current];
    commitTimer.current = window.setTimeout(() => {
      if (!p.paused && chosenRef.current.length === lockedSequence.length && lockedSequence.every((v, i) => v === chosenRef.current[i])) {
        commit({ selected_sequence: lockedSequence, replay_count: replayUsed.current ? 1 : 0 });
      }
    }, 620);
    return () => window.clearTimeout(commitTimer.current);
  }, [p.paused, p.pending, p.submitting, chosen.length, seq.length, commit]);

  const choose = (cell: number) => {
    if (!watched || playing || p.pending || p.submitting || p.paused || chosenRef.current.length >= seq.length) return;
    window.clearTimeout(commitTimer.current);
    const next = [...chosenRef.current, cell];
    chosenRef.current = next;
    armed.current = true;
    setChosen(next);
  };
  const undo = () => {
    if (p.pending || p.submitting || p.paused || !chosenRef.current.length) return;
    window.clearTimeout(commitTimer.current);
    const next = chosenRef.current.slice(0, -1);
    chosenRef.current = next;
    setChosen(next);
  };
  const replay = () => {
    if (!replayAllowed || p.pending || p.submitting || p.paused || playing) return;
    window.clearTimeout(commitTimer.current);
    chosenRef.current = [];
    armed.current = false;
    replayUsed.current = true;
    setAssistedReplay(true);
    setChosen([]);
    setWatched(false);
    setPlaying(true);
  };

  return <div className="focused-task game-board-memory">
    <MemoryGame
      rows={rows}
      columns={columns}
      sequenceLength={seq.length}
      playing={playing}
      watched={watched}
      activeCell={playIndex >= 0 ? playIndex : null}
      playPosition={playPosition}
      chosen={chosen}
      replayAllowed={replayAllowed}
      replaying={assistedReplay}
      pending={p.pending}
      submitting={p.submitting}
      paused={Boolean(p.paused)}
      onChoose={choose}
      onUndo={undo}
      onReplay={replay}
      onRetry={() => (p.onRecover ? p.onRecover() : commit(p.savedResponse?.selected_sequence ? { selected_sequence: p.savedResponse.selected_sequence } : undefined))}
    />
  </div>;
}

function AttentionTask({ p, onCueActivity }: { p: Props; onCueActivity?: (active: boolean) => void }) {
  const { item, exercise } = p;
  const s = item.stimulus ?? {};
  const blockKey = `${exercise.exercise_id}:${exercise.exercise_version}:${exercise.phase}:${exercise.training_block_id ?? 'assessment'}:${p.resetKey}`;
  const commit = useCommit(p);
  const [countdown, setCountdown] = useState<number | null>(3);
  const [armedBlock, setArmedBlock] = useState<string | null>(null);
  const [boundaryReadyItem, setBoundaryReadyItem] = useState<string | null>(null);
  const startedBlock = useRef<string | null>(null);
  const [cueVisible, setCueVisible] = useState(false);
  const [hasResponse, setHasResponse] = useState(false);
  const responded = useRef(false);
  const responseMs = useRef<number | null>(null);
  const onset = useRef<number | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const countdownTimer = useRef<number | undefined>(undefined);
  const symbol = String(s.symbol ?? s.shape ?? s.glyph ?? '');
  const color = String(s.color ?? 'graphite');
  const configuredTarget = exercise.items.find((row: any) => String(row.stimulus?.signal).toLowerCase() === 'go')?.stimulus;
  const targetLabel = configuredTarget ? `${configuredTarget.color ?? ''} ${configuredTarget.symbol ?? configuredTarget.shape ?? 'target'}`.trim() : '';
  const positiveRule = targetLabel
    ? `Respond only to the ${targetLabel}. Withhold for every other symbol and color pairing.`
    : exercise.instructions || 'Respond to the configured target. Withhold for other signals.';
  const atPacingPoint = p.index > 0 && p.index % 10 === 0;
  const pacing = atPacingPoint && boundaryReadyItem !== item.item_id;
  const commitTrial = () => {
    if (p.pending || p.submitting) return;
    const rt = responded.current ? responseMs.current : null;
    commit({ responded: responded.current }, undefined, rt, onset.current);
  };

  useEffect(() => {
    if (startedBlock.current === blockKey) {
      if (!p.pending && armedBlock !== blockKey && countdown === null) setArmedBlock(blockKey);
      return;
    }
    startedBlock.current = blockKey;
    window.clearTimeout(countdownTimer.current);
    window.clearTimeout(timer.current);
    p.onStimulusOnset?.(null);
    responded.current = false;
    responseMs.current = null;
    onset.current = null;
    setHasResponse(false);
    setCueVisible(false);
    if (p.pending) { setCountdown(null); setArmedBlock(null); return; }
    setArmedBlock(null);
    setCountdown(3);
    return () => { window.clearTimeout(countdownTimer.current); window.clearTimeout(timer.current); };
  // The block key starts a single entry countdown; each item then proceeds automatically.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blockKey, p.pending]);

  useEffect(() => {
    if (p.paused || p.pending || countdown === null) return;
    countdownTimer.current = window.setTimeout(() => {
      if (countdown <= 1) { setCountdown(null); setArmedBlock(blockKey); }
      else setCountdown(countdown - 1);
    }, 620);
    return () => window.clearTimeout(countdownTimer.current);
  }, [blockKey, p.paused, p.pending, countdown]);

  useEffect(() => {
    if (!p.paused) return;
    window.clearTimeout(timer.current);
    window.clearTimeout(countdownTimer.current);
    if (cueVisible) {
      setCueVisible(false);
      setHasResponse(false);
      responded.current = false;
      responseMs.current = null;
      onset.current = null;
      p.onStimulusOnset?.(null);
    }
    onCueActivity?.(false);
  }, [p.paused, cueVisible, onCueActivity, p.onStimulusOnset]);

  useEffect(() => {
    if (!atPacingPoint || boundaryReadyItem === item.item_id || p.pending || p.paused) return;
    const timerId = window.setTimeout(() => setBoundaryReadyItem(item.item_id), 1300);
    return () => window.clearTimeout(timerId);
  }, [atPacingPoint, boundaryReadyItem, item.item_id, p.pending, p.paused]);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (p.pending || p.paused || armedBlock !== blockKey || countdown !== null || pacing) return;
    responded.current = false;
    responseMs.current = null;
    setHasResponse(false);
    const frame = window.requestAnimationFrame(() => setCueVisible(true));
    return () => { window.cancelAnimationFrame(frame); window.clearTimeout(timer.current); onCueActivity?.(false); };
  // Item identity changes only after the prior fixed window has committed.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blockKey, armedBlock, countdown, item.item_id, p.pending, p.paused, s.response_window_ms, onCueActivity, pacing]);

  useLayoutEffect(() => {
    if (!cueVisible || p.pending || p.paused || pacing || armedBlock !== blockKey) return;
    const shownAt = performance.now();
    onset.current = shownAt;
    p.onStimulusOnset?.(shownAt);
    onCueActivity?.(true);
    timer.current = window.setTimeout(() => {
      setCueVisible(false);
      onCueActivity?.(false);
      commitTrial();
    }, Math.max(300, Number(s.response_window_ms ?? 1500)));
    return () => window.clearTimeout(timer.current);
  // The committed cue is timestamped immediately before its first paint.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cueVisible, blockKey, armedBlock, item.item_id, p.pending, p.paused, pacing, s.response_window_ms, onCueActivity]);

  const capture = () => {
    if (!cueVisible || p.pending || p.submitting || p.paused || responded.current) return;
    responded.current = true;
    responseMs.current = Math.max(0, performance.now() - (onset.current ?? performance.now()));
    setHasResponse(true);
  };
  useEffect(() => {
    if (!cueVisible) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.repeat || p.paused || ![' ', 'Enter'].includes(event.key)) return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest('button,input,textarea,select,[contenteditable="true"],[role="dialog"]')) return;
      event.preventDefault();
      capture();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [cueVisible, p.paused]);

  return <div className="focused-task game-board-attention">
    <AttentionGame
      symbol={symbol}
      color={color}
      positiveRule={positiveRule}
      countdown={countdown}
      pacing={pacing}
      cueVisible={cueVisible}
      hasResponse={hasResponse}
      pending={p.pending}
      submitting={p.submitting}
      paused={Boolean(p.paused)}
      onRespond={capture}
      onRetry={() => (p.onRecover ? p.onRecover() : commit())}
    />
  </div>;
}

function SwitchingTask({ p }: { p: Props }) {
  const s = p.item.stimulus ?? {};
  const commit = useCommit(p);
  const [sending, setSending] = useState(false);
  const target = s.target ?? {};
  const activeRule = String(s.active_rule ?? 'shape');
  const choose = (id: string) => {
    if (p.pending || p.submitting || p.paused || sending) return;
    setSending(true);
    p.setSelected(id);
    commit({ choice: id }, id);
  };
  return <div className="focused-task game-board-switching">
    <FlexibilityGame
      target={target}
      activeRule={activeRule}
      ruleChanged={Boolean(s.switch)}
      options={(s.options ?? []) as never}
      selected={typeof p.selected === 'string' ? p.selected : null}
      sending={sending}
      pending={p.pending}
      submitting={p.submitting}
      paused={Boolean(p.paused)}
      onChoose={choose}
      onRetry={() => (p.onRecover ? p.onRecover() : commit())}
    />
  </div>;
}

type MazeState = { position: number[]; legalMoves: number; movesAttempted: number; blockedMoves: number };
function mazeState(board: any, actions: any[]): MazeState {
  let position = [...(board.start ?? [0, 0])], stack: number[][] = [], legalMoves = 0, movesAttempted = 0, blockedMoves = 0;
  const delta: Record<string, number[]> = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
  for (const action of actions) {
    if (action.action === 'restart') { position = [...(board.start ?? [0, 0])]; stack = []; legalMoves = 0; continue; }
    if (action.action === 'undo') { if (stack.length) { position = stack.pop()!; legalMoves = Math.max(0, legalMoves - 1); } continue; }
    if (action.action !== 'move') continue;
    movesAttempted += 1;
    const step = delta[action.direction] ?? [0, 0], x = position[0] + step[0], y = position[1] + step[1];
    const blocked = x < 0 || x >= board.width || y < 0 || y >= board.height || (board.walls ?? []).some((wall: number[]) => wall[0] === x && wall[1] === y);
    if (blocked) { blockedMoves += 1; continue; }
    stack.push(position); position = [x, y]; legalMoves += 1;
  }
  return { position, legalMoves, movesAttempted, blockedMoves };
}

function PlanningTask({ p, onActionsChange }: { p: Props; onActionsChange: (actions: any[]) => void }) {
  const board = p.item.stimulus ?? {};
  const [actions, setActions] = useState<any[]>(p.savedResponse?.actions ?? []);
  const [feedback, setFeedback] = useState('');
  const [celebrating, setCelebrating] = useState(false);
  const commit = useCommit(p);
  const lockRef = useRef(false);
  const state = mazeState(board, actions);
  const pos = state.position, goalPosition = board.goal ?? [0, 0];
  const reachedGoal = pos[0] === goalPosition[0] && pos[1] === goalPosition[1];
  const safeCelebration = (p.exercise.phase === 'practice' || p.exercise.phase === 'training') && celebrating;
  const locked = p.pending || p.submitting || p.paused || lockRef.current;

  useEffect(() => { setActions(p.savedResponse?.actions ?? []); setFeedback(''); setCelebrating(false); lockRef.current = false; }, [p.item.item_id, p.resetKey, p.pending]);
  useEffect(() => { onActionsChange(actions); }, [actions, onActionsChange]);
  useEffect(() => {
    if (p.paused) { if (!p.submitting) lockRef.current = false; return; }
    if (!reachedGoal || p.pending || p.submitting || lockRef.current) return;
    lockRef.current = true;
    setCelebrating(p.exercise.phase === 'practice' || p.exercise.phase === 'training');
    const timer = window.setTimeout(() => commit({ actions }), 580);
    return () => window.clearTimeout(timer);
  }, [reachedGoal, p.pending, p.submitting, p.paused, p.exercise.phase, actions, commit]);

  const move = (direction: string) => {
    if (locked) return;
    const delta: Record<string, number[]> = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
    const step = delta[direction] ?? [0, 0], x = pos[0] + step[0], y = pos[1] + step[1];
    const blocked = x < 0 || x >= board.width || y < 0 || y >= board.height || (board.walls ?? []).some((wall: number[]) => wall[0] === x && wall[1] === y);
    setActions(current => [...current, { action: 'move', direction }]);
    setFeedback(blocked ? 'The path is blocked. Choose another direction.' : '');
  };
  const undo = () => { if (locked) return; setActions(current => [...current, { action: 'undo' }]); setFeedback('Last move undone.'); };
  const restart = () => { if (locked) return; setActions(current => [...current, { action: 'restart' }]); setFeedback('Back at the trailhead.'); };

  return <div className={`focused-task game-board-planning${safeCelebration ? ' route-arrived' : ''}`}>
    <h1 className="game-sr-only">Wayfinder's Garden: {safeCelebration ? 'The garden path is open.' : 'Find a route to the gate.'}</h1>
    <PlanningGame
      width={Number(board.width ?? 5)}
      height={Number(board.height ?? 5)}
      walls={(board.walls ?? []) as never}
      start={(board.start ?? [0, 0]) as never}
      goal={goalPosition as never}
      position={pos as never}
      movesAttempted={state.movesAttempted}
      legalMoves={state.legalMoves}
      blockedMoves={state.blockedMoves}
      feedback={feedback}
      reached={reachedGoal}
      pending={p.pending}
      submitting={p.submitting}
      paused={Boolean(p.paused)}
      inputLocked={lockRef.current && !reachedGoal}
      onMove={direction => move(direction)}
      onUndo={undo}
      onRestart={restart}
      onRetry={() => (p.onRecover ? p.onRecover() : commit())}
    />
  </div>;
}

function GameHeader({ p, seconds, planningDraft }: { p: Props; seconds: number | null; planningDraft?: Record<string, any> }) {
  const exercise = p.exercise, world = worlds[exercise.exercise_id] ?? worlds['EX-02'];
  // Training measures progress against the canonical decision window, not the size of
  // the generated bank: the block completes after its four-attempt window.
  const windowCount = exercise.phase === 'training' ? Number(exercise.decision_trial_count ?? 0) || null : null;
  const localCount = windowCount ?? exercise.items.length;
  const localIndex = Math.min(p.index + 1, Math.max(1, localCount));
  // The lane states only what the server actually configured: a baseline never receives
  // hints, and a tier is shown only when the running exercise carries one.
  const tierMatch = String(exercise.difficulty_tier ?? '').match(/tier[-_ ]?(\d)/i);
  const tierLabel = tierMatch ? `Tier ${tierMatch[1]}` : null;
  const lane = exercise.phase === 'baseline' ? 'Baseline · Uncoached'
    : exercise.phase === 'reassessment' ? 'Reassessment · Uncoached'
      : exercise.phase === 'training' ? (tierLabel ? `Training · ${tierLabel}` : 'Training')
        : (tierLabel ? `Practice · ${tierLabel}` : 'Practice');
  // A long generated bank (for example a 40-trial baseline) keeps the text count only.
  const dotCount = localCount > 0 && localCount <= 8 ? localCount : 0;
  return <header className="adventure-header game-shell-header">
    <div className="adventure-title-block">
      <span className="adventure-title">
        <span className="adventure-title-full">{taskName[exercise.exercise_id]}<b aria-hidden="true"> / </b>{world.name}</span>
        <span className="adventure-title-compact">{taskName[exercise.exercise_id]}</span>
      </span>
      <span className="adventure-lane" aria-label={`${phaseName[exercise.phase]} phase, ${lane}`}>{lane}</span>
    </div>
    <div className="adventure-round-summary">
      {dotCount > 0 && <span className="adventure-round-dots" role="img" aria-label={`Round ${localIndex} of ${localCount}`}>
        {Array.from({ length: dotCount }, (_, index) => <span key={index} className={`adventure-round-dot${index === localIndex - 1 ? ' is-current' : index < localIndex - 1 ? ' is-done' : ''}`} />)}
      </span>}
      <span className="adventure-round-copy"><span>Round {localIndex} of {localCount || 1}</span><span className="adventure-world-position">{journeyPosition(p.journeyProgress, exercise.exercise_id)}</span></span>
    </div>
    <div className="adventure-header-tools"><span className="session-elapsed" title="Elapsed since this local session started, including breaks.">{elapsedText(seconds)}</span>{p.onPause && <><button className="adventure-pause adventure-back-action" onClick={() => p.onPause?.(exercise.exercise_id === 'EX-05' ? planningDraft : undefined)} disabled={p.submitting} aria-label="Back to the game menu" title="Back"><ArrowLeft size={16} /><span>Back</span></button><button className="adventure-pause" onClick={() => p.onPause?.(exercise.exercise_id === 'EX-05' ? planningDraft : undefined)} disabled={p.submitting} aria-label="Pause game" title="Pause"><Pause size={16} /><span>Pause</span></button></>}</div>
  </header>;
}

export default function TaskRenderer(p: Props) {
  const art = useGameArt(p.exercise.exercise_id);
  const [now, setNow] = useState(() => Date.now());
  const [attentionCueActive, setAttentionCueActive] = useState(false);
  const [planningDraft, setPlanningDraft] = useState<Record<string, any> | undefined>();
  const updatePlanningDraft = useCallback((actions: any[]) => setPlanningDraft({ actions }), []);
  useEffect(() => { setAttentionCueActive(false); }, [p.exercise.exercise_id, p.exercise.phase, p.exercise.training_block_id, p.resetKey]);
  useEffect(() => { p.onCueActivity?.(attentionCueActive); return () => p.onCueActivity?.(false); }, [attentionCueActive, p.onCueActivity]);
  useEffect(() => { setPlanningDraft(undefined); }, [p.exercise.exercise_id, p.exercise.phase, p.item.item_id, p.resetKey]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const started = p.sessionStartedAt ? Date.parse(p.sessionStartedAt) : NaN;
  const elapsed = Number.isFinite(started) && started > 0 ? Math.max(0, Math.floor((now - started) / 1000)) : null;
  const world = worlds[p.exercise.exercise_id] ?? worlds['EX-02'];
  const content = p.exercise.exercise_id === 'EX-01' ? <MemoryTask key={`${p.exercise.phase}:${p.item.item_id}:${p.resetKey}`} p={p} />
    : p.exercise.exercise_id === 'EX-03' ? <AttentionTask key={`${p.exercise.phase}:${p.exercise.training_block_id ?? 'assessment'}:${p.resetKey}`} p={p} onCueActivity={setAttentionCueActive} />
      : p.exercise.exercise_id === 'EX-04' ? <SwitchingTask key={`${p.exercise.phase}:${p.item.item_id}:${p.resetKey}`} p={p} />
        : p.exercise.exercise_id === 'EX-05' ? <PlanningTask key={`${p.exercise.phase}:${p.item.item_id}:${p.resetKey}`} p={p} onActionsChange={updatePlanningDraft} />
          : <ReasoningTask key={`${p.exercise.phase}:${p.item.item_id}:${p.resetKey}`} p={p} />;
  return <MotionConfig reducedMotion="user"><section aria-label={`${world.name} game`} className={`assessment-view game-shell game-phase-${p.exercise.phase} game-world-${p.exercise.exercise_id.toLowerCase()}${p.paused ? ' game-is-paused' : ''}`}>
    <div className="adventure-backdrop" aria-hidden="true"><span /><span /><span /><span /></div>
    <GameHeader p={p} seconds={elapsed} planningDraft={planningDraft} />
    <div className="adventure-main"><div className="adventure-world-intro"><span className="world-kicker"><i /> {world.place}</span><span className="world-phase">{world.verb}</span></div>{art.status === 'ready' ? content : <div className="game-art-preparing" role={art.status === 'error' ? 'alert' : 'status'}><p>{art.status === 'error' ? 'The local scene could not be prepared. Your task has not started.' : 'Preparing the scene. Your task starts when the artwork is ready.'}</p>{art.status === 'error' && <button type="button" onClick={art.retry}>Retry scene preparation</button>}</div>}</div>
    <footer className="assessment-footer game-footer"><span>Task-specific observation</span><span>Not a clinical assessment</span><span>Timing is approximate</span></footer>
  </section></MotionConfig>;
}
