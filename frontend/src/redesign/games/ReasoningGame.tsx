import { ArrowRight, RotateCcw } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import { useId } from 'react';
import bracketArt from './assets/prepared/reasoning-bracket.png';
import crystalAmberArt from './assets/prepared/reasoning-crystal-amber.png';
import crystalBlueArt from './assets/prepared/reasoning-crystal-blue.png';
import plaqueSquareArt from './assets/prepared/reasoning-plaque-square.png';
import plaqueWideArt from './assets/prepared/reasoning-plaque-wide.png';
import slabArt from './assets/prepared/reasoning-slab.png';
import './reasoning-game.css';

export type ReasoningShape = 'circle' | 'square' | 'triangle' | 'diamond' | 'arrow';
export type ReasoningTileData = {
  shape: ReasoningShape;
  count: number;
  fill: 'outline' | 'solid';
  rotation: number;
};
export type ReasoningPosition = 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right';
export type ReasoningPattern = Record<ReasoningPosition, ReasoningTileData | null>;
export type ReasoningChoice = { choice_id: string; tile: ReasoningTileData };
export type ReasoningGameProps = {
  pattern: ReasoningPattern;
  choices: readonly ReasoningChoice[];
  selected: string | null;
  sending: boolean;
  pending: boolean;
  submitting: boolean;
  paused: boolean;
  onChoose: (id: string) => void;
  onRetry: () => void;
};

const POSITIONS: readonly { key: ReasoningPosition; label: string }[] = [
  { key: 'top_left', label: 'Top left' },
  { key: 'top_right', label: 'Top right' },
  { key: 'bottom_left', label: 'Bottom left' },
  { key: 'bottom_right', label: 'Bottom right' },
];
const SHAPES: readonly ReasoningShape[] = ['circle', 'square', 'triangle', 'diamond', 'arrow'];
const BRACKETS = ['top-left', 'top-right', 'bottom-right', 'bottom-left'] as const;

function isValidTile(tile: ReasoningTileData | null | undefined): tile is ReasoningTileData {
  return tile != null && SHAPES.includes(tile.shape) && Number.isInteger(tile.count) && tile.count >= 1 && tile.count <= 4 &&
    (tile.fill === 'outline' || tile.fill === 'solid') && Number.isInteger(tile.rotation) && tile.rotation >= 0 && tile.rotation <= 270;
}

function PatternTile({ tile }: { tile: ReasoningTileData }) {
  const color = tile.fill === 'solid' ? '#1e46c9' : '#274fbd';
  const fill = tile.fill === 'solid' ? color : 'none';
  return <svg className="rg-reasoning-pattern-tile" viewBox="0 0 140 88" aria-hidden="true" focusable="false">
    {Array.from({ length: tile.count }, (_, index) => {
      const x = 70 + (index - (tile.count - 1) / 2) * 31;
      const y = 44;
      const common = { fill, stroke: tile.fill === 'solid' ? '#16307f' : color, strokeWidth: 3.4, strokeLinejoin: 'round' as const, transform: `rotate(${tile.rotation} ${x} ${y})` };
      if (tile.shape === 'circle') return <circle key={index} cx={x} cy={y} r="12" {...common} />;
      if (tile.shape === 'square') return <rect key={index} x={x - 11} y={y - 11} width="22" height="22" rx="3" {...common} />;
      if (tile.shape === 'triangle') return <path key={index} d={`M${x} ${y - 14}L${x + 14} ${y + 12}H${x - 14}Z`} {...common} />;
      if (tile.shape === 'arrow') return <path key={index} d={`M${x - 14} ${y - 4}H${x + 4}V${y - 12}L${x + 16} ${y}L${x + 4} ${y + 12}V${y + 4}H${x - 14}Z`} {...common} />;
      return <path key={index} d={`M${x} ${y - 15}L${x + 15} ${y}L${x} ${y + 15}L${x - 15} ${y}Z`} {...common} />;
    })}
  </svg>;
}

function tileDescription(tile: ReasoningTileData): string {
  return `${tile.count} ${tile.fill} ${tile.shape}${tile.rotation ? `, rotated ${tile.rotation} degrees` : ''}`;
}

export function ReasoningGame({ pattern, choices, selected, sending, pending, submitting, paused, onChoose, onRetry }: ReasoningGameProps) {
  const id = useId();
  const reduceMotion = useReducedMotion();
  if (pattern == null || !Array.isArray(choices)) return <section className="rg-reasoning-game rg-reasoning-unavailable" aria-label="Reasoning puzzle unavailable"><p>This reasoning puzzle is unavailable because its pattern configuration is invalid.</p></section>;
  const positionEntries = POSITIONS.map(({ key, label }) => ({ key, label, tile: pattern[key] }));
  const missingCount = positionEntries.filter(entry => entry.tile === null).length;
  const validPattern = missingCount === 1 && positionEntries.every(entry => entry.tile === null || isValidTile(entry.tile));
  const validChoices = choices.length === 4 && choices.every(choice => choice != null && typeof choice.choice_id === 'string' && isValidTile(choice.tile)) &&
    new Set(choices.map(choice => choice.choice_id)).size === 4 &&
    ['A', 'B', 'C', 'D'].every(id => choices.some(choice => choice.choice_id === id && isValidTile(choice.tile)));
  const selectedIsValid = selected === null || choices.some(choice => choice.choice_id === selected);
  if (!validPattern || !validChoices || !selectedIsValid) return <section className="rg-reasoning-game rg-reasoning-unavailable" aria-label="Reasoning puzzle unavailable"><p>This reasoning puzzle is unavailable because its pattern configuration is invalid.</p></section>;

  const locked = pending || submitting || paused || sending;
  return <section className="rg-reasoning-game" aria-label="Reasoning puzzle">
    <div className="rg-reasoning-scene">
      <img className="rg-reasoning-prop rg-reasoning-prop-left" src={crystalBlueArt} alt="" aria-hidden="true" draggable={false} />
      <img className="rg-reasoning-prop rg-reasoning-prop-right" src={crystalAmberArt} alt="" aria-hidden="true" draggable={false} />
      <div className="rg-reasoning-heading">
        <span className="rg-reasoning-kicker">PATTERN ATELIER</span>
        <h1>Complete the constellation.</h1>
        <p>Study the relationships, then choose the tile that continues the pattern.</p>
      </div>

      <div className="rg-reasoning-tablet">
        <img className="rg-reasoning-tablet-base" src={slabArt} alt="" aria-hidden="true" draggable={false} />
        <div className="rg-reasoning-tablet-frame">
          <div className="rg-reasoning-matrix" role="group" aria-label="Two by two visual pattern puzzle">
            {POSITIONS.map(({ key, label }) => {
              const tile = pattern[key];
              return <div className={`rg-reasoning-matrix-cell${tile === null ? ' rg-reasoning-missing' : ''}`} role="img" aria-label={tile ? `${label}: ${tileDescription(tile)}` : `${label}: missing tile`} key={key}>
                <img className="rg-reasoning-cell-plaque" src={plaqueSquareArt} alt="" aria-hidden="true" draggable={false} />
                {tile ? <PatternTile tile={tile} /> : <span className="rg-reasoning-question" aria-hidden="true">?</span>}
              </div>;
            })}
            <span className="rg-reasoning-stud" aria-hidden="true" />
          </div>
          {BRACKETS.map(position => <img key={position} className={`rg-reasoning-bracket rg-reasoning-bracket-${position}`} src={bracketArt} alt="" aria-hidden="true" draggable={false} />)}
        </div>
      </div>

      <section className="rg-reasoning-answer-shelf" aria-labelledby={`${id}-answer-title`}>
        <div className="rg-reasoning-shelf-heading">
          <img className="rg-reasoning-shelf-plaque" src={plaqueWideArt} alt="" aria-hidden="true" draggable={false} />
          <h2 id={`${id}-answer-title`}>Which tile completes the pattern?</h2>
          <p>Choose once. The next puzzle follows automatically.</p>
        </div>
        <div className="rg-reasoning-choices" role="group" aria-label="Choose the pattern tile">
          {choices.map(({ choice_id, tile }) => <motion.button type="button" className={`rg-reasoning-choice${selected === choice_id ? ' rg-reasoning-choice-selected' : ''}`} key={choice_id}
            whileHover={!reduceMotion && !locked ? { y: -2 } : undefined}
            whileTap={!reduceMotion && !locked ? { scale: 0.975 } : undefined}
            transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 440, damping: 30 }}
            onClick={() => onChoose(choice_id)} disabled={locked} aria-pressed={selected === choice_id} aria-label={`Option ${choice_id}: ${tileDescription(tile)}`}>
            <img className="rg-reasoning-choice-plaque" src={plaqueWideArt} alt="" aria-hidden="true" draggable={false} />
            <span className="rg-reasoning-choice-stone"><PatternTile tile={tile} /></span>
            <span className="rg-reasoning-choice-id">{choice_id}</span>
          </motion.button>)}
        </div>
        {pending && <button type="button" className="rg-reasoning-retry" onClick={onRetry} disabled={submitting || paused}>Retry saved response <RotateCcw aria-hidden="true" /><ArrowRight aria-hidden="true" /></button>}
        {pending ? <p className="rg-reasoning-state" role="status">Saved response ready to retry.</p> : submitting || sending ? <p className="rg-reasoning-state" role="status">Saving this observation…</p> : paused ? <p className="rg-reasoning-state" role="status">This puzzle is paused.</p> : null}
      </section>
    </div>
  </section>;
}
