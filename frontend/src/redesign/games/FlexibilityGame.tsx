import { ArrowRight, Info, RotateCcw } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import plaqueAArt from './assets/prepared/flexibility-plaque-a.png';
import plaqueBArt from './assets/prepared/flexibility-plaque-b.png';
import plaqueWideArt from './assets/prepared/flexibility-plaque-wide.png';
import './flexibility-game.css';

export type FlexibilityShape = 'circle' | 'square' | 'triangle' | 'diamond';
export type FlexibilityOption = { id: string; color: string; shape: string };
export type FlexibilityTarget = { color: string; shape: string };
export type FlexibilityRule = 'color' | 'shape';
export type FlexibilityGameProps = {
  target: FlexibilityTarget;
  activeRule: string;
  ruleChanged: boolean;
  options: readonly FlexibilityOption[];
  selected: string | null;
  sending: boolean;
  pending: boolean;
  submitting: boolean;
  paused: boolean;
  onChoose: (id: string) => void;
  onRetry: () => void;
};

const COLOR_VALUES: Readonly<Record<string, string>> = {
  blue: '#1769e0', red: '#d84c49', yellow: '#d39a12', purple: '#7356aa',
};
const SHAPES = new Set<FlexibilityShape>(['circle', 'square', 'triangle', 'diamond']);

function resolvedColor(value: string): string | null {
  return COLOR_VALUES[value.trim().toLowerCase()] ?? null;
}
function resolvedShape(value: string): FlexibilityShape | null {
  const shape = value.trim().toLowerCase() as FlexibilityShape;
  return SHAPES.has(shape) ? shape : null;
}
function validTarget(value: FlexibilityTarget | null | undefined): value is FlexibilityTarget {
  return value != null && typeof value === 'object' && resolvedColor(value.color) !== null && resolvedShape(value.shape) !== null;
}
function validOptions(options: readonly FlexibilityOption[] | null | undefined): options is readonly FlexibilityOption[] {
  if (!Array.isArray(options) || options.length < 2 || options.length > 4) return false;
  const ids = new Set<string>();
  return options.every(option => {
    if (option == null || typeof option.id !== 'string' || !option.id.trim() || ids.has(option.id)) return false;
    ids.add(option.id);
    return resolvedColor(option.color) !== null && resolvedShape(option.shape) !== null;
  });
}

function Stimulus({ color, shape, className = '' }: { color: string; shape: string; className?: string }) {
  const fill = resolvedColor(color) ?? '#66717f';
  const normalized = resolvedShape(shape) ?? 'diamond';
  const common = { fill, stroke: '#21314d', strokeWidth: 1.8, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const };
  return <svg className={`rg-flex-stimulus ${className}`.trim()} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    {normalized === 'circle' ? <circle cx="32" cy="32" r="20" {...common} />
      : normalized === 'square' ? <rect x="13" y="13" width="38" height="38" rx="5" {...common} />
        : normalized === 'triangle' ? <path d="M32 10 55 52H9Z" {...common} />
          : <path d="m32 8 24 24-24 24-24-24Z" {...common} />}
  </svg>;
}

function RuleMark({ rule, target }: { rule: FlexibilityRule; target: FlexibilityTarget }) {
  if (rule === 'color') return <span className="rg-flex-rule-mark rg-flex-rule-color" aria-hidden="true"><span style={{ background: resolvedColor(target.color) ?? '#66717f' }} /></span>;
  return <span className="rg-flex-rule-mark rg-flex-rule-shape" aria-hidden="true"><Stimulus color="graphite" shape={target.shape} /></span>;
}

export function FlexibilityGame({ target, activeRule, ruleChanged, options, selected, sending, pending, submitting, paused, onChoose, onRetry }: FlexibilityGameProps) {
  const reduceMotion = useReducedMotion();
  const rule = String(activeRule ?? '').trim().toLowerCase();
  const validRule = rule === 'color' || rule === 'shape';
  const selectedIsValid = selected === null || (Array.isArray(options) && options.some(option => option.id === selected));
  if (!validTarget(target) || !validRule || !validOptions(options) || !selectedIsValid) {
    return <section className="rg-flex-game rg-flex-unavailable" aria-label="Flexibility puzzle unavailable"><p>This rule-shifting puzzle is unavailable because its configuration is invalid.</p></section>;
  }

  const locked = pending || submitting || paused || sending;
  const ruleRule = rule as FlexibilityRule;
  const targetLabel = `${target.color} ${target.shape}`;
  const statusMessage = pending ? 'Saved choice ready to retry.'
    : submitting || sending ? 'Saving this choice…'
      : paused ? 'This puzzle is paused.'
        : 'One choice, then onward. The next rule follows automatically.';

  return <section className="rg-flex-game" aria-label="Rule-shifting puzzle">
    <div className="rg-flex-scene">
      <div className="rg-flex-rule-panel">
        <img className="rg-flex-rule-plaque" src={plaqueWideArt} alt="" aria-hidden="true" draggable={false} />
        <span className="rg-flex-kicker">ACTIVE RULE</span>
        <div className="rg-flex-rule-line">
          <RuleMark rule={ruleRule} target={target} />
          <strong>{ruleRule.toUpperCase()}</strong>
        </div>
        <p>Match the target by {ruleRule}.</p>
        {ruleChanged && <motion.span className="rg-flex-rule-change" initial={reduceMotion ? false : { opacity: 0, y: 5, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 430, damping: 28 }}>The rule changed</motion.span>}
      </div>

      <div className="rg-flex-board">
        <div className="rg-flex-target-pedestal">
          <img className="rg-flex-plaque" src={plaqueAArt} alt="" aria-hidden="true" draggable={false} />
          <span className="rg-flex-pedestal-label">Target</span>
          <span className="rg-flex-target-well" role="img" aria-label={`Target: ${targetLabel}`}><Stimulus color={target.color} shape={target.shape} /></span>
          <span className="rg-flex-pedestal-copy">{targetLabel}</span>
        </div>

        <div className="rg-flex-options-panel">
          <div className="rg-flex-options" role="group" aria-label={`Choose the option matching the target by ${ruleRule}`}>
            {options.map(option => {
              const label = `${option.color} ${option.shape}`;
              return <motion.button type="button" key={option.id} className={`rg-flex-option${selected === option.id ? ' rg-flex-option-selected' : ''}`} onClick={() => onChoose(option.id)} disabled={locked} aria-pressed={selected === option.id} aria-label={`Option ${option.id}: ${label}`} whileHover={!reduceMotion && !locked ? { y: -2 } : undefined} whileTap={!reduceMotion && !locked ? { scale: 0.975 } : undefined} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 440, damping: 30 }}>
                <img className="rg-flex-plaque" src={plaqueBArt} alt="" aria-hidden="true" draggable={false} />
                <span className="rg-flex-option-id" aria-hidden="true">{option.id}</span>
                <span className="rg-flex-option-well"><Stimulus color={option.color} shape={option.shape} /></span>
                <span className="rg-flex-option-copy">{label}</span>
              </motion.button>;
            })}
          </div>
          <span className="rg-flex-panel-star" aria-hidden="true" />
        </div>
      </div>

      <div className="rg-flex-dock">
        <span className="rg-flex-dock-icon" aria-hidden="true"><Info /></span>
        <div className="rg-flex-dock-copy">
          <strong>{pending ? 'Your exact saved choice is ready' : paused ? 'Take your time' : 'One choice, then onward'}</strong>
          <span role="status" aria-live="polite">{statusMessage}</span>
        </div>
        {pending && <button type="button" className="rg-flex-retry" onClick={onRetry} disabled={submitting || paused}>Retry saved choice <RotateCcw aria-hidden="true" /><ArrowRight aria-hidden="true" /></button>}
      </div>
    </div>
  </section>;
}
