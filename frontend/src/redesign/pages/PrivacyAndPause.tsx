import { useEffect, useId, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock3, Database, Download, Info, Network, Pause, Play, Settings, ShieldCheck, Trash2, X } from 'lucide-react';
import { motion, useReducedMotion } from 'motion/react';
import './privacy-pause.css';

export type PrivacyNotice = {
  retention?: unknown;
  uncertainty?: unknown;
  remote_processing?: unknown;
  storage?: unknown;
  mirror_reconciliation?: unknown;
};
export type DeleteResult = {
  message?: string;
  deleted?: boolean;
  complete?: boolean;
  mirror?: { erasure_verified?: boolean; status?: string; message?: string } | null;
};
export type PrivacyPageProps = {
  open?: boolean;
  notice: PrivacyNotice | null;
  loading: boolean;
  error: string | null;
  exporting: boolean;
  deleting: boolean;
  reconciling: boolean;
  deleteResult: DeleteResult | null;
  onClose: () => void;
  onExport: () => void;
  onDelete: () => void;
  onReconcile: () => void;
};

export type PauseOverlayProps = {
  open: boolean;
  taskLabel?: string | null;
  worldName?: string | null;
  phaseLabel?: string | null;
  canResume?: boolean;
  busy?: boolean;
  betweenSignals?: boolean;
  savedResponsePending?: boolean;
  savedInterruptionPending?: boolean;
  draftAvailable?: boolean;
  onResume: () => void;
  onRetrySavedResponse?: () => void;
  onRetrySavedInterruption?: () => void;
  onSubmitDraft?: () => void;
  onLeave: () => void;
  leaveLabel?: string | null;
};

function display(value: unknown): string {
  if (value === null || value === undefined) return 'Not reported';
  if (typeof value === 'string') return value;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.map(item => typeof item === 'object' ? JSON.stringify(item) : String(item)).join(', ');
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return String(record.summary ?? record.message ?? record.description ?? record.note ?? record.status ?? JSON.stringify(value));
  }
  return String(value);
}

// The focus lifecycle must depend only on `open`: an inline close handler or a
// parent busy/rerender must never re-run cleanup, pull focus away mid-typing or
// restore a stale trigger.
function useModalFocus(open: boolean, onClose: () => void, locked: boolean) {
  const dialog = useRef<HTMLElement>(null);
  const closeRef = useRef(onClose);
  const lockedRef = useRef(locked);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => { lockedRef.current = locked; }, [locked]);
  useEffect(() => {
    if (!open) return;
    const host = dialog.current;
    const prior = document.activeElement as HTMLElement | null;
    const frame = requestAnimationFrame(() => host?.querySelector<HTMLElement>('button:not(:disabled), input:not(:disabled), summary')?.focus());
    const focusables = () => Array.from(host?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])') ?? []).filter(element => element.offsetParent !== null);
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!lockedRef.current) closeRef.current();
        return;
      }
      if (event.key !== 'Tab' || !host) return;
      const list = focusables();
      if (!list.length) { event.preventDefault(); return; }
      const active = document.activeElement as HTMLElement | null;
      const index = active ? list.indexOf(active) : -1;
      if (event.shiftKey ? index <= 0 : index === list.length - 1 || index === -1) {
        event.preventDefault();
        (event.shiftKey ? list[list.length - 1] : list[0]).focus();
      }
    };
    document.addEventListener('keydown', keydown, true);
    // The shell marks background regions inert while a modal is open and removes that
    // in a sibling effect, so a single synchronous focus call can land on an inert
    // control and silently leave focus on the body. Retry once the cleanup settles.
    const restoreFocus = () => {
      const usable = prior && prior !== document.body && prior !== document.documentElement && document.contains(prior) && !prior.closest('[inert]');
      if (usable && prior) { prior.focus(); return; }
      const isUsable = (element: HTMLElement | null) => Boolean(element && element.offsetParent !== null && !element.closest('[inert]'));
      // The explicitly marked trigger wins; document order must not decide it.
      const marked = document.querySelector<HTMLElement>('[data-modal-return]');
      if (isUsable(marked)) { marked?.focus(); return; }
      const candidates = Array.from(document.querySelectorAll<HTMLElement>('.adventure-mobile-nav button, .adventure-sidebar button, header button, header a'));
      candidates.find(isUsable)?.focus();
    };
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', keydown, true);
      restoreFocus();
      const retry = window.setTimeout(restoreFocus, 0);
      window.setTimeout(() => window.clearTimeout(retry), 200);
    };
  }, [open]);
  return dialog;
}

export function PrivacyPage({ open = true, notice, loading, error, exporting, deleting, reconciling, deleteResult, onClose, onExport, onDelete, onReconcile }: PrivacyPageProps) {
  const reduceMotion = useReducedMotion();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const inputId = useId();
  const dialog = useModalFocus(open, onClose, deleting);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (confirmOpen) window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [confirmOpen]);
  useEffect(() => {
    if (deleteResult?.deleted || deleteResult?.complete) {
      setConfirmOpen(false);
      setConfirmation('');
    }
  }, [deleteResult]);
  if (!open) return null;
  // Absence of notice data is not proof that the mirror is clean. Only an
  // authoritative notice response or delete result may state mirror state.
  const mirrorKnown = Boolean(deleteResult?.mirror) || notice !== null;
  const mirror = deleteResult?.mirror ?? (notice !== null ? (notice.mirror_reconciliation as { status?: string; message?: string; erasure_verified?: boolean } | null | undefined) ?? null : null);
  const mirrorPending = Boolean(mirrorKnown && mirror && (mirror.erasure_verified === false || (/pending|retry|failed/i.test(String(mirror.status ?? '')) && !mirror.erasure_verified)));
  const mirrorCopy = !mirrorKnown ? (loading ? 'Loading mirror status…' : 'Mirror status unavailable.')
    : mirror ? display(mirror.message ?? mirror.status ?? mirror)
      : 'No pending graph-mirror erasure is recorded.';
  return <div className="privacy-shade">
    <motion.section ref={dialog} className="privacy-dialog" role="dialog" aria-modal="true" aria-labelledby="privacy-title" aria-describedby="privacy-intro" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : .28 }}>
      <button type="button" className="privacy-close" onClick={onClose} disabled={deleting} aria-label="Close data and privacy"><X aria-hidden="true" /></button>
      <div className="privacy-heading"><p className="privacy-eyebrow">Local data management</p><h1 id="privacy-title">Your data, on this device.</h1><p id="privacy-intro">Review what is stored, export a copy, or delete the local learner record. Exported copies are managed separately.</p></div>
      {loading ? <p className="privacy-state" role="status">Loading the current data notice…</p> : <div className="privacy-cards">
        <article><span className="privacy-card-icon"><Database aria-hidden="true" /></span><div><h2>Local storage</h2><p>{display(notice?.storage)}</p></div></article>
        <article><span className="privacy-card-icon"><Settings aria-hidden="true" /></span><div><h2>Processing</h2><p>{display(notice?.remote_processing)}</p></div></article>
        <article><span className="privacy-card-icon"><Network aria-hidden="true" /></span><div><h2>Graph mirror</h2><p>{mirrorCopy}</p></div></article>
        <article><span className="privacy-card-icon"><Info aria-hidden="true" /></span><div><h2>Uncertainty</h2><p>{display(notice?.uncertainty)}</p></div></article>
        <article><span className="privacy-card-icon"><Clock3 aria-hidden="true" /></span><div><h2>Retention</h2><p>{display(notice?.retention)}</p></div></article>
      </div>}
      {error && <p className="privacy-error" role="alert"><AlertCircle aria-hidden="true" /> {error}</p>}
      {deleteResult?.message && <p className="privacy-success" role="status"><CheckCircle2 aria-hidden="true" /> {deleteResult.message}</p>}
      {mirrorPending && <div className="privacy-mirror-pending" role="status"><div><strong>Graph mirror erasure is still pending.</strong><p>{display(mirror?.message ?? mirror?.status)}</p></div><button type="button" onClick={onReconcile} disabled={reconciling}>{reconciling ? 'Checking…' : 'Reconcile mirror'}</button></div>}
      <div className="privacy-actions">
        <button type="button" className="privacy-button privacy-button-secondary" onClick={onExport} disabled={exporting || deleting}><Download aria-hidden="true" /> {exporting ? 'Preparing export…' : 'Export my data'}</button>
        <button type="button" className="privacy-button privacy-button-danger" onClick={() => setConfirmOpen(true)} disabled={deleting || Boolean(deleteResult?.deleted) || Boolean(deleteResult?.complete)}><Trash2 aria-hidden="true" /> Delete local data</button>
      </div>
      {confirmOpen && <section className="privacy-confirm" aria-labelledby="privacy-confirm-title">
        <h2 id="privacy-confirm-title">Confirm local deletion</h2>
        <p>This permanently deletes the local learner profile, sessions, assessment and practice events, derived estimates, and saved plans. It cannot be undone. Any exported file remains outside this deletion.</p>
        <label htmlFor={inputId}>Type <strong>DELETE LOCAL DATA</strong> to confirm</label>
        <input ref={inputRef} id={inputId} value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" disabled={deleting} />
        <div><button type="button" className="privacy-button privacy-button-secondary" onClick={() => { setConfirmOpen(false); setConfirmation(''); }} disabled={deleting}>Cancel</button><button type="button" className="privacy-button privacy-button-danger" onClick={onDelete} disabled={confirmation !== 'DELETE LOCAL DATA' || deleting}>{deleting ? 'Deleting…' : 'Confirm deletion'}</button></div>
      </section>}
      <p className="privacy-footnote"><ShieldCheck aria-hidden="true" /> Only the active local record is affected. Exported copies and other files are managed separately. Press Escape to close.</p>
    </motion.section>
  </div>;
}

export function PauseOverlay({ open, taskLabel, worldName, phaseLabel, canResume = true, busy = false, betweenSignals = false, savedResponsePending = false, savedInterruptionPending = false, draftAvailable = false, onResume, onRetrySavedResponse, onRetrySavedInterruption, onSubmitDraft, onLeave, leaveLabel }: PauseOverlayProps) {
  const reduceMotion = useReducedMotion();
  const dialog = useModalFocus(open, () => { if (canResume) onResume(); }, busy);
  if (!open) return null;
  const recovery = savedResponsePending || savedInterruptionPending;
  return <div className="privacy-pause-shade">
    <motion.section ref={dialog} className="privacy-pause-dialog" role="dialog" aria-modal="true" aria-labelledby="pause-title" aria-describedby="pause-copy" initial={reduceMotion ? false : { opacity: 0, scale: .98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: reduceMotion ? 0 : .22 }}>
      <span className="privacy-pause-icon"><Pause aria-hidden="true" /></span>
      <h1 id="pause-title">Take a moment.</h1>
      <p id="pause-copy">Your task is paused.</p>
      {(worldName || taskLabel) && <p className="privacy-pause-context">{[worldName, taskLabel, phaseLabel].filter(Boolean).join(' · ')}</p>}
      <div className="privacy-pause-actions">
        {savedInterruptionPending && onRetrySavedInterruption && <button type="button" className="privacy-pause-secondary" onClick={onRetrySavedInterruption} disabled={busy}>Retry saved interruption</button>}
        {savedResponsePending && onRetrySavedResponse && <button type="button" className="privacy-pause-secondary" onClick={onRetrySavedResponse} disabled={busy}>Retry saved response</button>}
        <button type="button" className="privacy-pause-primary" onClick={onResume} disabled={!canResume || busy}><Play aria-hidden="true" /> {busy ? 'Resuming…' : 'Resume task'}</button>
        {draftAvailable && onSubmitDraft && <button type="button" className="privacy-pause-secondary" onClick={onSubmitDraft} disabled={busy}>Record this attempt and return</button>}
        <button type="button" className={recovery || draftAvailable ? 'privacy-pause-secondary' : 'privacy-pause-primary'} onClick={onLeave} disabled={busy}><X aria-hidden="true" /> {leaveLabel ?? 'Leave task'}</button>
      </div>
      <p className="privacy-pause-note"><Info aria-hidden="true" /> Leaving an unfinished attempt records an interruption, and the attempt stays recoverable. {betweenSignals ? 'This pause is between active signal windows.' : 'Recorded progress stays with this session.'}</p>
    </motion.section>
  </div>;
}
