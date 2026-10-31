import { ArrowRight, CornerUpLeft, Eye, EyeOff, RotateCcw } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import tileGold from './assets/prepared/memory-tile-gold.png';
import tilePlain from './assets/prepared/memory-tile-plain.png';
import tileTeal from './assets/prepared/memory-tile-teal.png';
import './memory-game.css';

export type MemoryGameProps = {
  rows: number;
  columns: number;
  sequenceLength: number;
  playing: boolean;
  watched: boolean;
  activeCell: number | null;
  playPosition: number;
  chosen: readonly number[];
  replayAllowed: boolean;
  /** True while the cue currently playing is an assisted replay of the same route. */
  replaying: boolean;
  pending: boolean;
  submitting: boolean;
  paused: boolean;
  onChoose: (cell: number) => void;
  onUndo: () => void;
  onReplay: () => void;
  onRetry: () => void;
};

type Phase = 'preparing' | 'watch' | 'replay' | 'turn' | 'pending' | 'saving' | 'paused';

/** Every phase gets its own label and instruction so the dock never describes another state. */
const PHASE_LABEL: Record<Phase, string> = {
  preparing: 'PREPARING THE PATH',
  watch: 'WATCH PHASE',
  replay: 'ASSISTED REPLAY',
  turn: 'YOUR TURN',
  pending: 'SAVED RESPONSE',
  saving: 'SAVING RESPONSE',
  paused: 'PAUSED',
};

const PHASE_NOTE: Record<Phase, string> = {
  preparing: 'Get ready — the lanterns light one at a time, then the board opens for your route.',
  watch: 'Watch each stop in order. Your turn opens when the last lantern fades.',
  replay: 'Assisted replay · recorded as assisted, not unassisted evidence.',
  turn: 'Repeat the route in order: tap a trail stone, or focus it and press Enter.',
  pending: 'Your saved route is waiting. Retry it to continue.',
  saving: 'Your route is being recorded and input is locked until saving finishes.',
  paused: 'Paused. Resume when you are ready to continue.',
};

/** Same wording rule for the instruction card above the board. */
const PHASE_HEADLINE: Record<Phase, { eyebrow: string; strong: string }> = {
  preparing: { eyebrow: 'MEMORY ROUTE', strong: 'The grove is lighting your route.' },
  watch: { eyebrow: 'WATCH THE LANTERNS', strong: 'Remember their order.' },
  replay: { eyebrow: 'ASSISTED REPLAY', strong: 'Watch the same route once more.' },
  turn: { eyebrow: 'MEMORY ROUTE', strong: 'Walk the route from memory.' },
  pending: { eyebrow: 'SAVED ROUTE', strong: 'Your saved route is ready to retry.' },
  saving: { eyebrow: 'SAVING RESPONSE', strong: 'Your route is being recorded.' },
  paused: { eyebrow: 'PAUSED', strong: 'Resume when you are ready.' },
};

/**
 * The approved plate carves concentric rings around a diamond core in every cell. The
 * prepared stone cutouts (memory-tile-plain / -gold / -teal) are the approved extraction
 * of exactly that tile: weathered stone, cracks, moss and the engraved diamond emblem.
 * They are used as the tile surface, so the carving on screen is the approved artwork
 * rather than a hand-drawn approximation. The lit treatment adds a raised halo, a
 * non-colour pip and a hollow pip for the assisted tone, so no cue depends on colour.
 */
export function MemoryGame({ rows, columns, sequenceLength, playing, watched, activeCell, playPosition, chosen, replayAllowed, replaying, pending, submitting, paused, onChoose, onUndo, onReplay, onRetry }: MemoryGameProps) {
  const reduceMotion = useReducedMotion();
  const sizeIsValid = Number.isSafeInteger(rows) && rows > 0 && Number.isSafeInteger(columns) && columns > 0 && Number.isSafeInteger(rows * columns);
  const count = sizeIsValid ? rows * columns : 0;
  const sequenceIsValid = Number.isSafeInteger(sequenceLength) && sequenceLength > 0;
  const cellIsValid = (cell: number) => Number.isSafeInteger(cell) && cell >= 0 && cell < count;
  const valid = sizeIsValid && sequenceIsValid && Array.isArray(chosen) && chosen.length <= sequenceLength && chosen.every(cellIsValid) && (activeCell === null || cellIsValid(activeCell));
  const regionRef = useRef<HTMLDivElement>(null);
  const [regionScrolls, setRegionScrolls] = useState(false);

  // The region is focusable and its aria-label describes scrolling, so the label has to
  // follow the real layout: it may scroll on phones and short landscape screens, and it
  // must not claim scrolling where the CSS hides overflow.
  useEffect(() => {
    const node = regionRef.current;
    if (!node) return;
    const measure = () => setRegionScrolls(node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    for (const child of Array.from(node.children)) observer.observe(child);
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [count, rows, columns]);

  if (!valid) return <section className="rg-memory-game rg-memory-unavailable" aria-label="Memory puzzle unavailable"><p>This memory puzzle is unavailable because its board configuration is invalid.</p></section>;

  const locked = pending || submitting || paused;
  const accepting = watched && !playing && !locked && chosen.length < sequenceLength;
  const canUndo = chosen.length > 0 && !playing && !locked;
  const canReplay = replayAllowed && watched && !playing && !locked;
  const cueVisible = playing && activeCell !== null && !pending && !submitting && !paused;
  const stopVisible = playing && playPosition > 0 && !pending && !submitting && !paused;
  const tone = replaying ? 'teal' : 'gold';
  const phase: Phase = pending ? 'pending' : submitting ? 'saving' : paused ? 'paused' : playing ? (replaying ? 'replay' : 'watch') : watched ? 'turn' : 'preparing';
  const phaseLabel = PHASE_LABEL[phase];
  const dockNote = PHASE_NOTE[phase];
  const headline = PHASE_HEADLINE[phase];
  const statusText = pending ? 'Saved response ready to retry'
    : submitting ? 'Saving your response…'
      : paused ? 'Paused'
        : stopVisible ? `Stop ${playPosition} of ${sequenceLength}${replaying ? ' · assisted replay' : ''}`
          : playing ? 'Get ready to watch'
            : watched ? `Your turn · ${chosen.length} of ${sequenceLength} stops entered`
              : 'The sequence begins automatically';
  const style = {
    '--rg-memory-columns': columns,
    '--rg-memory-rows': rows,
    '--rg-memory-tile-plain': `url(${tilePlain})`,
    '--rg-memory-tile-gold': `url(${tileGold})`,
    '--rg-memory-tile-teal': `url(${tileTeal})`,
  } as CSSProperties;
  const boardLabel = `${rows} rows by ${columns} columns memory board. ${regionScrolls
    ? 'The board is larger than this area, so scroll or pan inside it to reach every trail stone.'
    : 'Every trail stone fits inside this area, so there is nothing to scroll here.'}`;

  return <section className="rg-memory-game" aria-label="Memory sequence puzzle">
    <div className="rg-memory-scene">
      <aside className="rg-memory-objective" aria-label="Memory instructions">
        <span className="rg-memory-objective-icon" aria-hidden="true">{playing ? <Eye /> : watched ? <EyeOff /> : <Eye />}</span>
        <div><span className="rg-memory-eyebrow">{headline.eyebrow}</span><strong>{headline.strong}</strong></div>
      </aside>

      <div className="rg-memory-board-region" role="region" aria-label={boardLabel} tabIndex={0} ref={regionRef}>
        <div className="rg-memory-slab">
          <span className="rg-memory-plinth" aria-hidden="true" />
          <div className="rg-memory-grid" style={style} role="group" aria-label={`${rows} by ${columns} memory board`}>
            {Array.from({ length: count }, (_, cell) => {
              const ordinals = playing ? [] : chosen.flatMap((selectedCell, index) => selectedCell === cell ? [index + 1] : []);
              const lit = cueVisible && activeCell === cell;
              const accessible = ordinals.length ? `, selected stops ${ordinals.join(', ')}` : '';
              return <motion.button type="button" className={`rg-memory-tile${lit ? ` rg-memory-lit rg-memory-lit-${tone}` : ''}${ordinals.length ? ' rg-memory-selected' : ''}`}
                whileHover={!reduceMotion && accepting ? { y: -2, scale: 1.015 } : undefined}
                whileTap={!reduceMotion && accepting ? { y: 2, scale: 0.97 } : undefined}
                transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 28 }}
                key={cell} disabled={!accepting} onClick={() => onChoose(cell)} aria-label={`Trail stone ${cell + 1}${lit ? `, illuminated stop ${playPosition} of ${sequenceLength}${replaying ? ', assisted replay' : ''}` : ''}${accessible}`}>
                {lit && <span className="rg-memory-lit-halo" aria-hidden="true" />}
                {lit && <span className="rg-memory-lit-mark" aria-hidden="true" />}
                {ordinals.length > 0 && <span className="rg-memory-order" aria-hidden="true">{ordinals.join(',')}</span>}
              </motion.button>;
            })}
          </div>
        </div>
      </div>

      <div className="rg-memory-dock" aria-label="Memory phase and controls">
        <div className="rg-memory-dock-head">
          <span className="rg-memory-dock-label">{phaseLabel}</span>
          <span className="rg-memory-dots" role="img" aria-label={`Cue ${Math.max(0, playPosition)} of ${sequenceLength} shown`}>
            {Array.from({ length: sequenceLength }, (_, index) => <span key={index} className={`rg-memory-dot${playPosition > index ? ' is-done' : ''}`} aria-hidden="true" />)}
          </span>
        </div>
        <div className="rg-memory-watch-status" aria-live="polite" aria-atomic="true">
          {pending ? <EyeOff aria-hidden="true" /> : submitting || paused || (watched && !playing) ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
          <span>{statusText}</span>
        </div>
        <p className="rg-memory-dock-note">{dockNote}</p>
        <div className="rg-memory-controls" role="group" aria-label="Memory route controls">
          <button type="button" className="rg-memory-action rg-memory-undo" onClick={onUndo} disabled={!canUndo} aria-label="Undo last stop"><CornerUpLeft aria-hidden="true" /><span>Undo last stop</span></button>
          {replayAllowed && <button type="button" className="rg-memory-action rg-memory-replay" onClick={onReplay} disabled={!canReplay} aria-label="Replay route"><RotateCcw aria-hidden="true" /><span>Replay route</span></button>}
          {pending && <button type="button" className="rg-memory-action rg-memory-retry" onClick={onRetry} disabled={submitting || paused} aria-label="Retry saved route">Retry saved route <ArrowRight aria-hidden="true" /></button>}
        </div>
      </div>
    </div>
  </section>;
}
