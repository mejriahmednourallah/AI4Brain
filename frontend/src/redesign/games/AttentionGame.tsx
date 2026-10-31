import { ArrowRight, Check, Hand, Target } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import daisArt from './assets/prepared/attention-dais.png';
import portholeArt from './assets/prepared/attention-porthole.png';
import './attention-game.css';

export type AttentionGameProps = {
  symbol: string;
  color: string;
  positiveRule: string;
  countdown: number | null;
  pacing: boolean;
  cueVisible: boolean;
  hasResponse: boolean;
  pending: boolean;
  submitting: boolean;
  paused: boolean;
  onRespond: () => void;
  onRetry: () => void;
};

const COLOR_VALUES: Readonly<Record<string, string>> = {
  blue: '#1769e0', gray: '#66717f', grey: '#66717f', graphite: '#424b57', red: '#d84c49',
  coral: '#d96652', yellow: '#a56a00', gold: '#a56a00', green: '#37865a', mint: '#347e68',
  purple: '#7356aa', violet: '#7356aa', orange: '#bd6a27', black: '#262a30', white: '#fff',
};
const SHAPE_NAMES = new Set(['circle', 'square', 'triangle', 'diamond', 'arrow']);

function SignalGlyph({ symbol, color }: { symbol: string; color: string }) {
  const shape = symbol.trim().toLowerCase();
  const resolvedColor = COLOR_VALUES[color.trim().toLowerCase()] ?? color.trim();
  const common = { fill: 'none', stroke: resolvedColor, strokeWidth: 3.2, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const };
  if (!SHAPE_NAMES.has(shape)) return <span className="rg-attention-glyph-text" style={{ color: resolvedColor }} aria-hidden="true">{symbol}</span>;
  return <svg className="rg-attention-glyph-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    {shape === 'circle' ? <circle cx="32" cy="32" r="18" {...common} />
      : shape === 'square' ? <rect x="15" y="15" width="34" height="34" rx="4" {...common} />
        : shape === 'triangle' ? <path d="M32 12 53 50H11Z" {...common} />
          : shape === 'diamond' ? <path d="m32 10 22 22-22 22-22-22Z" {...common} />
            : <path d="M11 28h27V17l16 15-16 15V36H11Z" {...common} />}
  </svg>;
}

export function AttentionGame({ symbol, color, positiveRule, countdown, pacing, cueVisible, hasResponse, pending, submitting, paused, onRespond, onRetry }: AttentionGameProps) {
  const reduceMotion = useReducedMotion();
  const valid = typeof symbol === 'string' && symbol.trim().length > 0 && typeof color === 'string' && color.trim().length > 0 &&
    typeof positiveRule === 'string' && positiveRule.trim().length > 0 &&
    (countdown === null || (Number.isInteger(countdown) && countdown >= 0));
  if (!valid) return <section className="rg-attention-game rg-attention-unavailable" aria-label="Attention task unavailable"><p>This attention task is unavailable because its signal configuration is invalid.</p></section>;

  const showCue = cueVisible && !paused && !pending && !submitting && countdown === null && !pacing;
  const responseDisabled = !showCue || hasResponse;
  const responseLabel = hasResponse ? 'Response registered' : paused ? 'Paused' : submitting ? 'Saving…' : pending ? 'Response saved' : showCue ? 'Respond' : 'Wait for the signal';
  const statusMessage = pending ? 'Your exact saved response is ready to retry.'
    : submitting ? 'Saving this observation…'
      : paused ? 'This task is paused.'
        : countdown !== null ? `The signal set begins in ${countdown}.`
          : pacing ? 'Quiet moment. The next signal resumes automatically.'
            : showCue ? (hasResponse ? 'Response registered. Keep watching until the window ends.' : 'Respond only while this signal is visible.')
              : 'Waiting for the next signal.';
  return <section className="rg-attention-game" aria-label="Attention and inhibition task">
    <div className="rg-attention-scene">
      <aside className="rg-attention-objective" aria-label="Task rule">
        <span className="rg-attention-objective-icon"><Target aria-hidden="true" /></span>
        <div><span className="rg-attention-eyebrow">SIGNAL OBSERVATORY</span><strong>{positiveRule}</strong></div>
      </aside>

      <div className={`rg-attention-instrument${showCue ? ' rg-attention-instrument-live' : ''}`}>
        <div className="rg-attention-instrument-face">
          <img className="rg-attention-porthole" src={portholeArt} alt="" aria-hidden="true" draggable={false} />
          <div className="rg-attention-bezel">
            <div className="rg-attention-lens">
              {showCue ? <div className="rg-attention-signal" role="img" aria-label={`${color} ${symbol} signal`}><SignalGlyph symbol={symbol} color={color} /></div>
                : pending ? <div className="rg-attention-lens-state">Saved response</div>
                  : submitting ? <div className="rg-attention-lens-state">Saving response</div>
                    : paused ? <div className="rg-attention-lens-state">Paused</div>
                      : countdown !== null ? <div className="rg-attention-countdown" role="group" aria-label={`Signal set begins in ${countdown}`}><strong aria-hidden="true">{countdown}</strong><span>Get ready</span></div>
                        : pacing ? <div className="rg-attention-lens-state"><strong>Quiet moment</strong><span>Next signal resumes automatically.</span></div>
                          : <div className="rg-attention-lens-state">Waiting for signal</div>}
            </div>
            <span className="rg-attention-bezel-stud rg-attention-stud-top" aria-hidden="true" />
            <span className="rg-attention-bezel-stud rg-attention-stud-right" aria-hidden="true" />
            <span className="rg-attention-bezel-stud rg-attention-stud-bottom" aria-hidden="true" />
            <span className="rg-attention-bezel-stud rg-attention-stud-left" aria-hidden="true" />
          </div>
        </div>
        <img className="rg-attention-instrument-base" src={daisArt} alt="" aria-hidden="true" draggable={false} />
      </div>

      <div className="rg-attention-response-dock">
        <motion.button type="button" className={`rg-attention-respond${hasResponse ? ' rg-attention-respond-recorded' : ''}`} onClick={onRespond} disabled={responseDisabled} aria-label={responseLabel}
          whileHover={!reduceMotion && showCue && !hasResponse ? { y: -1 } : undefined}
          whileTap={!reduceMotion && showCue && !hasResponse ? { scale: 0.975 } : undefined}
          transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 480, damping: 30 }}>
          {hasResponse ? <Check aria-hidden="true" /> : <Hand aria-hidden="true" />}
          <span>{responseLabel}</span>
        </motion.button>
        {showCue && !hasResponse && <span className="rg-attention-respond-hint" aria-hidden="true">Tap, or press Space</span>}
        {pending && <button type="button" className="rg-attention-retry" onClick={onRetry} disabled={submitting || paused}>Retry saved signal <ArrowRight aria-hidden="true" /></button>}
        <p className="rg-attention-response-status" role="status" aria-live="polite">{statusMessage}</p>
      </div>
    </div>
  </section>;
}
