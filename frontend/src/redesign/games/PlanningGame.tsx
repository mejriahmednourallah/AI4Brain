import { motion, useReducedMotion } from 'motion/react';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, CornerUpLeft, Flag, Keyboard, RotateCcw, Route, Target } from 'lucide-react';
import type { CSSProperties, KeyboardEvent, ReactNode } from 'react';
import { useId } from 'react';
import './planning-game.css';

export type PlanningDirection = 'up' | 'down' | 'left' | 'right';
export type PlanningGameProps = {
  width: number;
  height: number;
  walls: readonly (readonly [number, number])[];
  start: readonly [number, number];
  goal: readonly [number, number];
  position: readonly [number, number];
  movesAttempted: number;
  legalMoves: number;
  blockedMoves: number;
  feedback?: string;
  reached: boolean;
  pending: boolean;
  submitting: boolean;
  paused: boolean;
  inputLocked?: boolean;
  onMove: (direction: PlanningDirection) => void;
  onUndo: () => void;
  onRestart: () => void;
  onRetry: () => void;
};

const DIRECTIONS: readonly { direction: PlanningDirection; label: string; icon: ReactNode }[] = [
  { direction: 'up', label: 'Move up', icon: <ArrowUp aria-hidden="true" /> },
  { direction: 'left', label: 'Move left', icon: <ArrowLeft aria-hidden="true" /> },
  { direction: 'down', label: 'Move down', icon: <ArrowDown aria-hidden="true" /> },
  { direction: 'right', label: 'Move right', icon: <ArrowRight aria-hidden="true" /> },
];
const KEY_TO_DIRECTION: Record<string, PlanningDirection> = {
  ArrowUp: 'up', w: 'up', W: 'up', ArrowDown: 'down', s: 'down', S: 'down',
  ArrowLeft: 'left', a: 'left', A: 'left', ArrowRight: 'right', d: 'right', D: 'right',
};
import paverA from './assets/prepared/planning-paver-1.png';
import paverB from './assets/prepared/planning-paver-2.png';
import paverC from './assets/prepared/planning-paver-3.png';
import paverD from './assets/prepared/planning-paver-4.png';
import boulderA from './assets/prepared/planning-boulder-1.png';
import boulderB from './assets/prepared/planning-boulder-2.png';
import pawnArt from './assets/prepared/planning-pawn.png';
import portalArt from './assets/prepared/planning-portal.png';

const PAVERS = [paverA, paverB, paverC, paverD];
const BOULDERS = [boulderA, boulderB];

/** The back edge of the board is slightly narrower and shorter, as on the approved board. */
const BACK_SCALE = 0.93;

type RowGeometry = { top: number; height: number; cellWidth: number; leftInset: number };

function boardRows(rows: number): RowGeometry[] {
  const weights = Array.from({ length: rows }, (_, y) => (rows === 1 ? 1 : 1 - (1 - BACK_SCALE) * (y / (rows - 1))));
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let consumed = 0;
  return weights.map((weight) => {
    const geometry = { top: (consumed / total) * 100, height: (weight / total) * 100, cellWidth: weight * 100, leftInset: ((1 - weight) * 100) / 2 };
    consumed += weight;
    return geometry;
  });
}

const variantOf = (x: number, y: number, count: number) => (x * 3 + y * 5 + (x * y) % 7) % count;
const mirroredAt = (x: number, y: number) => (x + y * 2) % 2 === 0;


export function PlanningGame({ width, height, walls, start, goal, position, movesAttempted, legalMoves, blockedMoves, feedback, reached, pending, submitting, paused, inputLocked = false, onMove, onUndo, onRestart, onRetry }: PlanningGameProps) {
  const reduce = useReducedMotion();
  const helpId = `rg-planning-help-${useId().replace(/:/g, '')}`;
  const locked = inputLocked || reached || pending || submitting || paused;
  const validSize = Number.isSafeInteger(width) && width > 0 && Number.isSafeInteger(height) && height > 0;
  const cols = validSize ? width : 0;
  const rows = validSize ? height : 0;
  const isCell = (point: readonly [number, number] | null | undefined) => Array.isArray(point) && Number.isSafeInteger(point[0]) && Number.isSafeInteger(point[1]) && point[0] >= 0 && point[0] < cols && point[1] >= 0 && point[1] < rows;
  const validBoard = validSize && Array.isArray(walls) && isCell(start) && isCell(goal) && isCell(position) && walls.every(isCell);
  const onBoardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (locked || event.repeat || event.altKey || event.ctrlKey || event.metaKey) return;
    const direction = KEY_TO_DIRECTION[event.key];
    if (!direction) return;
    event.preventDefault();
    onMove(direction);
  };

  if (!validBoard) return <section className="rg-planning-game rg-planning-unavailable" aria-label="Planning puzzle unavailable"><p>This puzzle is unavailable because its board configuration is invalid.</p></section>;
  const rowsGeometry = boardRows(rows);
  const wallSet = new Set(walls.map(([x, y]) => `${x},${y}`));
  const pawnRow = rowsGeometry[position[1]];
  const pawnCell = pawnRow.cellWidth / cols;
  const pawnLeft = pawnRow.leftInset + (position[0] + 0.5) * pawnCell;
  const pawnTop = pawnRow.top + pawnRow.height / 2;

  return <section className="rg-planning-game" aria-label="Planning puzzle">
    <div className="rg-planning-game-scene">
      <div className="rg-planning-stage">
        <div className="rg-planning-board-wrap">
          <div className="rg-planning-board" role="grid"
            style={{ '--rg-planning-aspect': `${cols} / ${(rows * 0.84).toFixed(3)}`, '--rg-planning-cols': cols, '--rg-planning-rows': rows } as CSSProperties}
            aria-label={`Maze with ${rows} rows and ${cols} columns. Marker on row ${position[1] + 1}, column ${position[0] + 1}. Focus the board to use arrow keys or WASD.`}
            aria-rowcount={rows} aria-colcount={cols} aria-disabled={locked} aria-describedby={helpId} tabIndex={locked ? -1 : 0} onKeyDown={onBoardKeyDown}>
            {rowsGeometry.map((row, y) => <div className="rg-planning-row" role="row" aria-rowindex={y + 1} key={`row-${y}`}
              style={{ top: `${row.top}%`, height: `${row.height}%`, left: `${row.leftInset}%`, width: `${row.cellWidth}%` }}>
              {Array.from({ length: cols }, (_, x) => {
                const isWall = wallSet.has(`${x},${y}`);
                const isGoal = goal[0] === x && goal[1] === y;
                const isStart = start[0] === x && start[1] === y;
                return <div className="rg-planning-cell" role="gridcell" aria-rowindex={y + 1} aria-colindex={x + 1}
                  aria-label={`Row ${y + 1}, column ${x + 1}${isWall ? ', boulder' : ', paver'}${isStart ? ', trailhead' : ''}${isGoal ? ', portal' : ''}`}
                  style={{ transform: `rotate(${(((x * 7 + y * 13) % 5) - 2) * 0.35}deg)` }}
                  key={`cell-${x}`}>
                  <img className="rg-planning-tile" src={PAVERS[variantOf(x, y, PAVERS.length)]} alt=""
                    style={{ transform: mirroredAt(x, y) ? 'scaleX(-1)' : undefined }} draggable={false} />
                  {isWall && <img className="rg-planning-obstacle" src={BOULDERS[variantOf(x, y, BOULDERS.length)]} alt=""
                    style={{ transform: `translate(-50%, -52%)${mirroredAt(x, y) ? ' scaleX(-1)' : ''}` }} draggable={false} />}
                  {isGoal && <img className="rg-planning-portal-art" src={portalArt} alt="" draggable={false} />}
                </div>;
              })}
            </div>)}
            <motion.img className="rg-planning-pawn-art" src={pawnArt} alt="" draggable={false}
              initial={false} animate={{ left: `${pawnLeft}%`, top: `${pawnTop}%` }}
              transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 320, damping: 26 }}
              style={{ width: `${(pawnRow.cellWidth / cols) * 0.66}%` }} />
          </div>
          <p className="rg-planning-board-help" id={helpId}>The blue pawn starts at the trailhead. Find your own route to the portal.</p>
        </div>
        <aside className="rg-planning-objective-panel" aria-label="Route objective and progress">
          <div className="rg-planning-objective-line"><span className="rg-planning-objective-icon" aria-hidden="true"><Target /></span><div><span className="rg-planning-panel-kicker">YOUR OBJECTIVE</span><strong>{reached ? 'Portal reached' : 'Reach the portal'}</strong></div></div>
          <div className="rg-planning-objective-line rg-planning-secondary"><span className="rg-planning-objective-icon rg-planning-route-icon" aria-hidden="true"><Route /></span><div><span className="rg-planning-panel-kicker">WAYFINDER</span><strong>Find an efficient route</strong></div></div>
          <div className="rg-planning-counts" aria-label="Move counts">
            <div><span>Moves</span><strong>{movesAttempted}</strong></div>
            <div><span>Legal steps</span><strong>{legalMoves}</strong></div>
            <div><span>Blocked</span><strong>{blockedMoves}</strong></div>
          </div>
          {pending && <button className="rg-planning-retry-button" type="button" onClick={onRetry} disabled={submitting || paused}>Retry saved route <ArrowRight aria-hidden="true" /></button>}
          {paused && <p className="rg-planning-state-note">Paused · your route is ready when you return.</p>}
        </aside>
        <div className="rg-planning-control-dock" role="group" aria-label="Route controls">
          <div className="rg-planning-dock-actions">
            <button type="button" className="rg-planning-soft-control" onClick={onUndo} disabled={locked} aria-label="Undo last move"><CornerUpLeft aria-hidden="true" /><span>Undo</span></button>
            <button type="button" className="rg-planning-soft-control" onClick={onRestart} disabled={locked} aria-label="Restart route"><RotateCcw aria-hidden="true" /><span>Restart</span></button>
            <div className="rg-planning-direction-pad" aria-label="Move controls">
              {DIRECTIONS.map(({ direction, label, icon }) => <button type="button" className={`rg-planning-direction rg-planning-direction-${direction}`} key={direction} onClick={() => onMove(direction)} disabled={locked} aria-label={label}>{icon}</button>)}
            </div>
            <div className="rg-planning-dock-hint"><Keyboard aria-hidden="true" /><span>Arrow keys or WASD</span></div>
            <div className="rg-planning-dock-hint rg-planning-finish-hint"><Flag aria-hidden="true" /><span>Completes when you reach the portal.</span></div>
          </div>
        </div>
      </div>
      <p className="rg-planning-game-feedback" aria-live="polite">{pending ? 'Your exact saved route is ready to retry.' : feedback || (reached ? submitting ? 'Route reached. Saving this attempt…' : 'Portal reached.' : '')}</p>
    </div>
  </section>;
}
