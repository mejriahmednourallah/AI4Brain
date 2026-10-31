import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  CloudOff,
  LoaderCircle,
  MessageCircleQuestion,
  RotateCcw,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import {
  CoachRequestError,
  createCoachCancel,
  fetchConversation,
  fetchProviderStatus,
  newRequestId,
  streamCoachTurn,
  type CoachAction,
  type CoachExerciseId,
  type CoachLocalResponse,
  type CoachPhase,
  type CoachProviderId,
  type CoachProviderStatus,
  type CoachReply,
  type CoachStoredTurn,
  type CoachSubject,
  type CoachTurnRequest,
} from './coachClient';
import './companion-coach.css';

export type CompanionCoachProps = {
  sessionId: string;
  focusExerciseId?: string | null;
  phase?: 'overview' | 'training' | 'practice';
  trainingBlockId?: string | null;
  itemId?: string | null;
  quiet?: boolean;
  onNavigate?: (target: string) => void;
  onRequestStrategy?: (strategyId: string, exerciseId: string | null) => void;
  onActionSelected?: (selection: {
    requestId: string;
    actionId: string;
    target?: string;
    strategyId?: string;
    exerciseId?: string | null;
  }) => void | Promise<void>;
  onReplyText?: (text: string, replyKey: string, context?: { evidenceRevision?: string; subject?: string }) => void;
  onTurnRecorded?: () => void;
  onClose?: () => void;
  cancelToken?: number;
};

const MAX_MESSAGE = 2000;
const MIN_MESSAGE = 3;
const MAX_LISTED_EVIDENCE = 6;

const FAMILY_LABELS: Record<string, string> = {
  'EX-01': 'Memory',
  'EX-02': 'Reasoning',
  'EX-03': 'Attention and inhibition',
  'EX-04': 'Flexibility',
  'EX-05': 'Planning',
};

const EXERCISE_IDS: readonly string[] = ['EX-01', 'EX-02', 'EX-03', 'EX-04', 'EX-05'];
const PROVIDER_IDS: readonly CoachProviderId[] = ['local', 'groq', 'gemini'];

type TurnStatus = 'waiting' | 'complete' | 'cancelled' | 'error' | 'incomplete';

type CoachMessageView = {
  key: string;
  text: string;
  status: TurnStatus;
  reply: CoachReply | null;
  subject: CoachSubject | null;
  evidenceIds: string[];
  limitations: string[];
  providerRequested: string | null;
  providerUsed: string | null;
  providerStatus: string | null;
  fallbackReason: string | null;
  model: string | null;
  errorDetail: string | null;
  retry: CoachTurnRequest | null;
  retrySameRequest: boolean;
  localResponse: CoachLocalResponse | null;
};

function isExerciseId(value: string | null | undefined): value is CoachExerciseId {
  return typeof value === 'string' && EXERCISE_IDS.includes(value);
}

function isProviderId(value: string | null | undefined): value is CoachProviderId {
  return value === 'local' || value === 'groq' || value === 'gemini';
}

function providerLabel(name: string | null | undefined): string {
  if (!name) return 'The local coach';
  if (name === 'local') return 'The local coach';
  if (name === 'groq') return 'Groq';
  if (name === 'gemini') return 'Gemini';
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function subjectLabel(subject: CoachSubject | null): string | null {
  if (!subject) return null;
  if (subject.label) return subject.label;
  if (subject.exercise_id) return FAMILY_LABELS[subject.exercise_id] ?? subject.exercise_id;
  return null;
}

function subjectOrigin(resolvedFrom: string | undefined): string {
  switch (resolvedFrom) {
    case 'explicit':
      return 'from the family you named';
    case 'current_activity':
      return 'from the activity you just finished';
    case 'conversation_subject':
      return 'continuing this conversation';
    case 'recommendation':
      return 'from the next recommendation';
    case 'next_step':
      return 'from your next step';
    case 'explicit_selection':
      return 'from the family you selected';
    case 'ambiguous':
      return 'two families matched, so the next answer may ask which one you mean';
    case 'unresolved':
      return 'nothing matched yet, so the answer may ask which family you mean';
    default:
      return 'from your saved conversation';
  }
}

function providerNote(
  providerStatus: string | null,
  fallbackReason: string | null,
  providerRequested: string | null,
  providerUsed: string | null,
  model: string | null,
): string | null {
  switch (providerStatus) {
    case 'local_only':
      return 'Answered by the local coach on this server. No text left this device.';
    case 'not_configured':
      return `${providerLabel(providerRequested)} is not configured on this server; your message stayed local.`;
    case 'consent_required':
      return 'Consent for a hosted provider was not recorded for this turn, so the local coach answered.';
    case 'validated':
      return `${providerLabel(providerUsed)}${model ? ` (${model})` : ''} helped phrase this answer after the evidence check. The evidence block is always rendered on this server.`;
    case 'unavailable_or_invalid':
      return `${providerLabel(providerRequested)} was unavailable or its draft failed the evidence check, so the local coach answered instead.`;
    case 'unknown_provider':
      return `${providerLabel(providerRequested)} is not a provider on this server, so the local coach answered instead.`;
    case null:
      return null;
    default:
      return fallbackReason
        ? `The local coach answered instead (${fallbackReason.replace(/_/g, ' ')}).`
        : null;
  }
}

function describeError(error: unknown): string {
  if (error instanceof CoachRequestError) return error.detail;
  if (error instanceof TypeError) {
    return 'The coach could not be reached. Check that the local server is running, then retry.';
  }
  if (error instanceof Error && error.message) return error.message;
  return 'The coach request failed.';
}

function toMessageView(turn: CoachStoredTurn): CoachMessageView {
  const answer = turn.answer;
  const subject: CoachSubject | null = answer
    ? answer.subject
    : turn.subjectExerciseId
      ? {
          exercise_id: turn.subjectExerciseId,
          dimension: null,
          label: FAMILY_LABELS[turn.subjectExerciseId] ?? null,
          resolved_from: 'saved',
        }
      : null;
  return {
    key: turn.requestId,
    text: turn.message,
    status: answer ? 'complete' : turn.status === 'cancelled' ? 'cancelled' : 'incomplete',
    reply: answer ? answer.response : null,
    subject,
    evidenceIds: answer ? answer.response.evidence_ids : [],
    limitations: answer ? answer.context_limitations : [],
    providerRequested: answer ? answer.provider_requested : null,
    providerUsed: answer ? answer.provider_used : turn.providerUsed,
    providerStatus: answer ? answer.provider_status : null,
    fallbackReason: answer ? answer.fallback_reason : null,
    model: answer ? answer.model : null,
    errorDetail: answer ? null : 'This turn was saved without a stored answer, so there is nothing to show.',
    retry: null,
    retrySameRequest: false,
    localResponse: answer?.local_response ?? null,
  };
}

function speechText(reply: CoachReply): string {
  return [
    reply.observation,
    reply.explanation,
    reply.rationale,
    reply.follow_up,
    reply.caveat,
  ].filter((part): part is string => typeof part === 'string' && part.trim().length > 0).join(' ');
}

type TurnProps = {
  message: CoachMessageView;
  retryDisabled: boolean;
  quiet: boolean;
  onNavigate?: (target: string) => void;
  onRequestStrategy?: (strategyId: string, exerciseId: string | null) => void;
  onActionSelected?: CompanionCoachProps['onActionSelected'];
  onPrefill: (text: string) => void;
  onRetry: (message: CoachMessageView) => void;
};

function Turn({
  message,
  retryDisabled,
  quiet,
  onNavigate,
  onRequestStrategy,
  onActionSelected,
  onPrefill,
  onRetry,
}: TurnProps) {
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const pendingActionRef = useRef<string | null>(null);
  const reply = message.reply;
  const ids = reply ? reply.evidence_ids : message.evidenceIds;
  const actions: CoachAction[] = reply ? reply.actions : [];
  const inspectAction = actions.find(action => action.id === 'inspect_evidence' && action.kind === 'navigate');
  const inspectTarget = inspectAction?.target ?? null;
  const otherActions = actions.filter(action => action.id !== 'inspect_evidence');
  const note = reply
    ? providerNote(
        message.providerStatus,
        message.fallbackReason,
        message.providerRequested,
        message.providerUsed,
        message.model,
      )
    : null;
  const selectAction = async (
    action: CoachAction,
    activate: () => void,
  ) => {
    if (pendingActionRef.current === action.id) return;
    pendingActionRef.current = action.id;
    setPendingActionId(action.id);
    try {
      activate();
      await onActionSelected?.({
        requestId: message.key,
        actionId: action.id,
        ...(action.target ? { target: action.target } : {}),
        ...(action.strategy_id ? { strategyId: action.strategy_id } : {}),
        exerciseId: action.exercise_id ?? null,
      });
    } finally {
      pendingActionRef.current = null;
      setPendingActionId(null);
    }
  };

  return (
    <article className="companion-coach-turn" data-status={message.status}>
      <p className="companion-coach-question">{message.text}</p>

      {message.status === 'waiting' && (
        <p className="companion-coach-working">
          <LoaderCircle aria-hidden="true" size={15} />
          {message.localResponse
            ? 'The local answer is ready; the optional explanation is still pending.'
            : `Reading your saved evidence${message.subject ? ` about ${subjectLabel(message.subject) ?? 'this family'}` : ''}…`}
        </p>
      )}

      {message.localResponse && (
        <section className="companion-coach-block companion-coach-local-progress" aria-label="Local answer">
          <p className="companion-coach-provenance">{message.localResponse.label || 'Local answer'}</p>
          <p>{message.localResponse.response}</p>
          {message.localResponse.status === 'explanation_pending' && <p className="companion-coach-record-count">The optional explanation is pending. This grounded local answer remains available now.</p>}
        </section>
      )}

      {message.status === 'cancelled' && (
        <p className="companion-coach-note">
          Cancelled before the companion answered. No answer was written for this turn.
        </p>
      )}

      {message.status === 'incomplete' && (
        <p className="companion-coach-note">{message.errorDetail}</p>
      )}

      {message.status === 'error' && (
        <div className="companion-coach-failure">
          <p role="alert" className="companion-coach-note">{message.errorDetail}</p>
          <button type="button" className="companion-coach-button" onClick={() => onRetry(message)} disabled={retryDisabled}>
            <RotateCcw aria-hidden="true" size={15} />
            {message.retrySameRequest ? 'Retry' : 'Ask again'}
          </button>
        </div>
      )}

      {reply && (
        <>
          <section className="companion-coach-block companion-coach-evidence" aria-label="Recorded evidence">
            <h4>Recorded evidence</h4>
            <p>{reply.observation || 'No recorded observation was stored with this turn.'}</p>
            {ids.length > 0 && (
              <div className="companion-coach-record-list">
                <p className="companion-coach-record-count">
                  {ids.length} saved record{ids.length === 1 ? '' : 's'} cited
                </p>
                <ul>
                  {ids.slice(0, MAX_LISTED_EVIDENCE).map(id => (
                    <li key={id}><code>{id}</code></li>
                  ))}
                </ul>
                {ids.length > MAX_LISTED_EVIDENCE && (
                  <p className="companion-coach-record-count">
                    and {ids.length - MAX_LISTED_EVIDENCE} more
                  </p>
                )}
              </div>
            )}
            {inspectAction && (
              onNavigate && inspectTarget
                ? <button
                    type="button"
                    className="companion-coach-link"
                    disabled={pendingActionId === inspectAction.id}
                    onClick={() => void selectAction(inspectAction, () => onNavigate(inspectTarget))}
                  >
                    {pendingActionId === inspectAction.id ? 'Opening evidence…' : 'Inspect evidence'}
                  </button>
                : <div className="companion-coach-unavailable">
                    <button type="button" className="companion-coach-link" disabled aria-describedby={`${message.key}-inspect-note`}>Inspect evidence</button>
                    <span id={`${message.key}-inspect-note`}>Available from the host shell when it supplies the evidence target.</span>
                  </div>
            )}
          </section>

          <section className="companion-coach-block" aria-label="Explanation">
            <h4>Explanation</h4>
            <p>{reply.explanation || 'No explanation was stored with this turn.'}</p>
          </section>

          {(reply.strategy_title || reply.strategy_guidance) && (
            <section className="companion-coach-block companion-coach-strategy" aria-label="Recorded strategy">
              <h4>Recorded strategy</h4>
              {reply.strategy_title && <p className="companion-coach-strategy-title">{reply.strategy_title}</p>}
              {reply.strategy_guidance && <p>{reply.strategy_guidance}</p>}
            </section>
          )}

          <section className="companion-coach-block companion-coach-next" aria-label="Next step">
            <h4>Next step</h4>
            <p>{reply.next_step_note || 'No next step was stored with this turn.'}</p>
            {(reply.recommended_exercise_id || reply.recommended_difficulty) && (
              <p className="companion-coach-record-count">
                {FAMILY_LABELS[reply.recommended_exercise_id ?? ''] ?? reply.recommended_exercise_id ?? 'No family'}
                {reply.recommended_difficulty ? ` · ${reply.recommended_difficulty}` : ''}
              </p>
            )}
          </section>

          {otherActions.length > 0 && (
            <div className="companion-coach-actions" role="group" aria-label="Suggested next actions">
              {otherActions.map(action => {
                const strategyId = action.strategy_id;
                if (action.kind === 'assistance') {
                  if (!strategyId || !onRequestStrategy || quiet) {
                    return (
                      <div className="companion-coach-unavailable" key={action.id}>
                        <button type="button" className="companion-coach-button" disabled aria-describedby={`${message.key}-${action.id}-note`}>{action.label}</button>
                        <span id={`${message.key}-${action.id}-note`}>
                          {quiet ? 'Quiet during scored work; choose a strategy after this phase.' : 'Unavailable here because this shell has not connected the strategy action.'}
                        </span>
                      </div>
                    );
                  }
                  return (
                    <button
                      type="button"
                      key={action.id}
                      className="companion-coach-button"
                      disabled={pendingActionId === action.id}
                      onClick={() => void selectAction(action, () => onRequestStrategy(strategyId, action.exercise_id ?? null))}
                    >
                      {pendingActionId === action.id ? 'Applying…' : action.label}
                    </button>
                  );
                }
                const target = action.target;
                if (!target || !onNavigate || quiet) {
                  return (
                    <div className="companion-coach-unavailable" key={action.id}>
                      <button type="button" className="companion-coach-button" disabled aria-describedby={`${message.key}-${action.id}-note`}>{action.label}</button>
                      <span id={`${message.key}-${action.id}-note`}>
                        {quiet ? 'Quiet during scored work; choose another action after this phase.' : 'Unavailable here because this shell has not connected the backend target.'}
                      </span>
                    </div>
                  );
                }
                return (
                  <button
                    type="button"
                    key={action.id}
                    className="companion-coach-button"
                    disabled={pendingActionId === action.id}
                    onClick={() => void selectAction(action, () => onNavigate(target))}
                  >
                    {pendingActionId === action.id ? 'Opening…' : action.label}
                  </button>
                );
              })}
            </div>
          )}

          {reply.follow_up && (
            <button type="button" className="companion-coach-followup" onClick={() => onPrefill(reply.follow_up)}>
              <MessageCircleQuestion aria-hidden="true" size={15} />
              <span>{reply.follow_up}</span>
            </button>
          )}

          {reply.caveat && (
            <p className="companion-coach-caveat">
              <AlertTriangle aria-hidden="true" size={15} />
              <span>{reply.caveat}</span>
            </p>
          )}

          {reply.rationale && (
            <details className="companion-coach-disclosure">
              <summary>
                Why this suggestion
                <ChevronDown aria-hidden="true" size={15} />
              </summary>
              <p>{reply.rationale}</p>
            </details>
          )}

          {message.limitations.length > 0 && (
            <details className="companion-coach-disclosure">
              <summary>
                Limits
                <ChevronDown aria-hidden="true" size={15} />
              </summary>
              <ul>
                {message.limitations.map(limit => <li key={limit}>{limit}</li>)}
              </ul>
            </details>
          )}

          {note && <p className="companion-coach-provenance">{note}</p>}
        </>
      )}
    </article>
  );
}

export function CompanionCoach({
  sessionId,
  focusExerciseId = null,
  phase = 'overview',
  trainingBlockId = null,
  itemId = null,
  quiet = false,
  onNavigate,
  onRequestStrategy,
  onActionSelected,
  onReplyText,
  onTurnRecorded,
  onClose,
  cancelToken = 0,
}: CompanionCoachProps) {
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<CoachMessageView[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(Boolean(sessionId));
  const [historyNote, setHistoryNote] = useState<string | null>(null);
  const [providers, setProviders] = useState<CoachProviderStatus | null>(null);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [provider, setProvider] = useState<CoachProviderId>('local');
  const [consent, setConsent] = useState(false);
  const [announcement, setAnnouncement] = useState('');

  const generation = useRef(0);
  const activeRequest = useRef<ReturnType<typeof createCoachCancel> | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const hintId = useId();
  const lastCancelToken = useRef(cancelToken);

  const phaseValue: CoachPhase = phase;

  useEffect(() => {
    const handle = createCoachCancel();
    fetchProviderStatus(handle.signal)
      .then(status => setProviders(status))
      .catch(error => {
        if (handle.signal.aborted) return;
        setProvidersError(describeError(error));
      });
    return () => handle.cancel('unmounted');
  }, []);

  useEffect(() => {
    generation.current += 1;
    const owner = generation.current;
    activeRequest.current?.cancel('session-changed');
    activeRequest.current = null;
    setBusyKey(null);
    setMessages([]);
    setDraft('');
    setHistoryNote(null);
    setAnnouncement('');
    if (!sessionId) {
      setRestoring(false);
      return;
    }
    const handle = createCoachCancel();
    setRestoring(true);
    fetchConversation(sessionId, handle.signal)
      .then(conversation => {
        if (handle.signal.aborted || generation.current !== owner) return;
        const restored = conversation.turns.map(toMessageView);
        setMessages(restored);
        // History is rendered for review only; reopening the companion never speaks old replies.
        if (isProviderId(conversation.provider)) setProvider(conversation.provider);
        setConsent(conversation.consentRecorded);
        if (!restored.length) setHistoryNote('No saved conversation for this session yet.');
      })
      .catch(error => {
        if (handle.signal.aborted || generation.current !== owner) return;
        setHistoryNote(`Saved conversation unavailable: ${describeError(error)}`);
      })
      .finally(() => {
        if (handle.signal.aborted || generation.current !== owner) return;
        setRestoring(false);
      });
    return () => {
      generation.current += 1;
      handle.cancel('session-changed');
    };
  }, [onReplyText, sessionId]);

  useEffect(() => {
    if (!quiet) return;
    // A scored window must not receive an answer started moments earlier.
    activeRequest.current?.cancel('quiet');
  }, [quiet]);

  useEffect(()=>{
    const onVisibility=()=>{if(document.visibilityState==='hidden')activeRequest.current?.cancel('page-hidden');};
    document.addEventListener('visibilitychange',onVisibility);
    return()=>document.removeEventListener('visibilitychange',onVisibility);
  },[]);

  useEffect(()=>{
    if(lastCancelToken.current===cancelToken)return;
    lastCancelToken.current=cancelToken;
    const request=activeRequest.current;
    if(!request)return;
    request.cancel('learner-stopped');
    activeRequest.current=null;
    setBusyKey(null);
    setMessages(current=>current.map(message=>message.status==='waiting'
      ? message.localResponse
        ? { ...message, status:'incomplete', errorDetail:'The local answer is saved; its optional explanation was stopped.' }
        : { ...message, status:'cancelled' }
      : message));
  },[cancelToken]);

  useEffect(() => {
    if (!onClose) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    log.scrollTop = log.scrollHeight;
  }, [messages.length, busyKey]);

  const remoteAllowed = provider !== 'local' && consent;
  const selectedInfo = providers ? providers.providers[provider] : undefined;
  const hostedNotConfigured = provider !== 'local' && Boolean(providers) && !selectedInfo?.configured;

  const subjectForHeader = useMemo<CoachSubject | null>(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const candidate = messages[index];
      if (candidate.subject && (candidate.subject.exercise_id || candidate.subject.label)) return candidate.subject;
    }
    if (isExerciseId(focusExerciseId)) {
      return {
        exercise_id: focusExerciseId,
        dimension: null,
        label: FAMILY_LABELS[focusExerciseId] ?? null,
        resolved_from: 'current_activity',
      };
    }
    return null;
  }, [messages, focusExerciseId]);

  const buildBody = useCallback((message: string, requestId: string): CoachTurnRequest => {
    const remote = provider !== 'local' && consent;
    const body: CoachTurnRequest = {
      session_id: sessionId,
      message,
      allow_remote: remote,
      phase: phaseValue,
      training_block_id: trainingBlockId ?? null,
      item_id: itemId ?? null,
      request_id: requestId,
      provider,
      focus_exercise_id: isExerciseId(focusExerciseId) ? focusExerciseId : null,
      subject_exercise_id: null,
      provider_consent_recorded: remote,
    };
    return body;
  }, [consent, focusExerciseId, itemId, phaseValue, provider, sessionId, trainingBlockId]);

  const runTurn = useCallback(async (body: CoachTurnRequest) => {
    const key = body.request_id ?? newRequestId();
    const owner = generation.current;
    const handle = createCoachCancel();
    activeRequest.current = handle;
    setBusyKey(key);
    setAnnouncement('');
    try {
      const result = await streamCoachTurn({ ...body, request_id: key }, {
        signal: handle.signal,
        onEvidence: payload => {
          if (generation.current !== owner) return;
          setMessages(current => current.map(item => (item.key === key
            ? { ...item, subject: payload.subject, evidenceIds: payload.evidence_ids }
            : item)));
        },
        onLocalResponse: payload => {
          if (generation.current !== owner || payload.request_id !== key) return;
          setMessages(current => current.map(item => (item.key === key
            ? { ...item, localResponse: payload, subject: payload.subject, evidenceIds: payload.relevant_evidence_ids }
            : item)));
          const localSpeech = payload.spoken_summary?.trim() || payload.response.trim();
          if (localSpeech && payload.evidence_revision) onReplyText?.(localSpeech, key,
            { evidenceRevision: payload.evidence_revision, subject: payload.subject.exercise_id ?? undefined });
          setAnnouncement(payload.label || 'Local answer available.');
        },
      });
      if (generation.current !== owner) return;
      setMessages(current => current.map(item => (item.key === key
        ? {
            ...item,
            status: 'complete',
            reply: result.response,
            subject: result.subject,
            evidenceIds: result.response.evidence_ids,
            limitations: result.context_limitations,
            providerRequested: result.provider_requested,
            providerUsed: result.provider_used,
            providerStatus: result.provider_status,
            fallbackReason: result.fallback_reason,
            model: result.model,
            errorDetail: null,
            retry: null,
            retrySameRequest: false,
          }
        : item)));
      onReplyText?.(result.spoken_summary?.trim() || speechText(result.response), key,
        { evidenceRevision: result.evidence_revision, subject: result.subject.exercise_id ?? undefined });
      setAnnouncement('Companion replied.');
      onTurnRecorded?.();
    } catch (error) {
      if (generation.current !== owner) return;
      if (handle.signal.aborted) {
        setMessages(current => current.map(item => (item.key === key
          ? item.localResponse
            ? { ...item, status: 'incomplete', errorDetail: 'The local answer is saved; its optional explanation stopped.', retry: body }
            : { ...item, status: 'cancelled', retry: body }
          : item)));
        setAnnouncement('The request was stopped. Any saved local answer remains available.');
        return;
      }
      const detail = describeError(error);
      const conflictNeedsNewId = error instanceof CoachRequestError
        && error.status === 409
        && /incomplete/i.test(error.detail);
      setMessages(current => current.map(item => (item.key === key
        ? {
            ...item,
            status: 'error',
            errorDetail: detail,
            retry: body,
            retrySameRequest: !conflictNeedsNewId,
          }
        : item)));
      setAnnouncement('The companion could not answer. A retry control is available.');
    } finally {
      if (activeRequest.current === handle) {
        activeRequest.current = null;
        setBusyKey(current => (current === key ? null : current));
      }
      inputRef.current?.focus();
    }
  }, [onReplyText, onTurnRecorded]);

  const sendNew = () => {
    const message = draft.trim();
    if (quiet || !sessionId || message.length < MIN_MESSAGE || message.length > MAX_MESSAGE) return;
    const requestId = newRequestId();
    const body = buildBody(message, requestId);
    setMessages(current => [...current, {
      key: requestId,
      text: message,
      status: 'waiting',
      reply: null,
      subject: null,
      evidenceIds: [],
      limitations: [],
      providerRequested: null,
      providerUsed: null,
      providerStatus: null,
      fallbackReason: null,
      model: null,
      errorDetail: null,
      retry: null,
      retrySameRequest: false,
      localResponse: null,
    }]);
    setDraft('');
    inputRef.current?.focus();
    void runTurn(body);
  };

  const retry = (message: CoachMessageView) => {
    if (!message.retry || quiet) return;
    const body = message.retrySameRequest
      ? message.retry
      : { ...message.retry, request_id: newRequestId() };
    setMessages(current => current.map(item => (item.key === message.key
      ? { ...item, key: body.request_id ?? item.key, status: 'waiting', errorDetail: null }
      : item)));
    void runTurn(body);
  };

  const cancel = () => {
    activeRequest.current?.cancel('cancelled');
  };

  const lastRetryable = [...messages].reverse().find(item => item.retry !== null && (item.status === 'error' || item.status === 'cancelled'));

  const prefill = (text: string) => {
    setDraft(text.slice(0, MAX_MESSAGE));
    inputRef.current?.focus();
  };

  const words = draft.trim() ? draft.trim().split(/\s+/).length : 0;
  const canSend = !quiet
    && !restoring
    && busyKey === null
    && Boolean(sessionId)
    && draft.trim().length >= MIN_MESSAGE
    && draft.trim().length <= MAX_MESSAGE;
  const headerSubject = subjectLabel(subjectForHeader);
  const subjectPrefix = messages.length === 0 ? 'Questions will be about' : 'Talking about';

  return (
    <section className="companion-coach" role="region" aria-label="Conversation with the practice companion">
      <header className="companion-coach-header">
        <div className="companion-coach-brand">
          <span className="companion-coach-mark" aria-hidden="true"><Sparkles size={17} /></span>
          <div>
            <h3>Practice companion</h3>
            <p className="companion-coach-subtitle">
              {remoteAllowed ? 'Hosted provider allowed for this conversation' : 'Local coaching on this server'}
            </p>
          </div>
        </div>
        {onClose && (
          <button type="button" className="companion-coach-icon" onClick={onClose} aria-label="Close the companion conversation">
            <X aria-hidden="true" size={18} />
          </button>
        )}
      </header>

      <p className="companion-coach-subject">
        {headerSubject
          ? <>{subjectPrefix} <strong>{headerSubject}</strong> · {subjectOrigin(subjectForHeader?.resolved_from)}</>
          : 'No task family is pinned yet. Ask about Memory, Reasoning, Attention, Flexibility or Planning.'}
      </p>

      <div
        className="companion-coach-log"
        role="log"
        aria-live="polite"
        aria-busy={busyKey !== null}
        ref={logRef}
      >
        {restoring && <p className="companion-coach-note">Loading your saved conversation…</p>}
        {!restoring && historyNote && <p className="companion-coach-note">{historyNote}</p>}
        {!restoring && !historyNote && messages.length === 0 && (
          <p className="companion-coach-note">
            Ask about a saved result, a strategy, or the next recommendation. Answers cite saved evidence only.
          </p>
        )}
        {messages.map(message => (
          <Turn
            key={message.key}
            message={message}
            retryDisabled={busyKey !== null || quiet}
            quiet={quiet}
            onNavigate={onNavigate}
            onRequestStrategy={onRequestStrategy}
            onActionSelected={onActionSelected}
            onPrefill={prefill}
            onRetry={retry}
          />
        ))}
      </div>

      <p className="companion-coach-sr" role="status">{announcement}</p>

      <div className="companion-coach-composer">
        <label className="companion-coach-label" htmlFor={`${hintId}-input`}>Your question</label>
        <textarea
          id={`${hintId}-input`}
          ref={inputRef}
          className="companion-coach-input"
          value={draft}
          rows={3}
          maxLength={MAX_MESSAGE}
          placeholder={quiet ? 'Coaching is quiet during scored work.' : 'What would you like to understand?'}
          aria-describedby={hintId}
          disabled={quiet}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              if (canSend) sendNew();
            }
          }}
        />
        <p className="companion-coach-hint" id={hintId}>
          {quiet
            ? 'Coaching is quiet during scored work.'
            : `${words} word${words === 1 ? '' : 's'} · ${draft.length}/${MAX_MESSAGE} characters · Enter sends, Shift+Enter adds a line`}
        </p>
        <div className="companion-coach-controls">
          <button
            type="button"
            className="companion-coach-send"
            onClick={sendNew}
            disabled={!canSend}
          >
            <SendHorizontal aria-hidden="true" size={16} />
            Send
          </button>
          <button
            type="button"
            className="companion-coach-button"
            onClick={cancel}
            disabled={busyKey === null}
          >
            Cancel
          </button>
          {lastRetryable && (
            <button
              type="button"
              className="companion-coach-button"
              onClick={() => retry(lastRetryable)}
              disabled={busyKey !== null || quiet}
            >
              <RotateCcw aria-hidden="true" size={15} />
              Retry
            </button>
          )}
        </div>
      </div>

      <div className="companion-coach-providers">
        <label className="companion-coach-label" htmlFor={`${hintId}-provider`}>Provider</label>
        <select
          id={`${hintId}-provider`}
          className="companion-coach-select"
          value={provider}
          disabled={restoring}
          onChange={event => {
            const next = event.target.value;
            if (isProviderId(next)) setProvider(next);
          }}
        >
          {PROVIDER_IDS.map(name => (
            <option key={name} value={name}>
              {name === 'local' ? 'Local coach (this server)' : providerLabel(name)}
            </option>
          ))}
        </select>

        <label className="companion-coach-consent">
          <input
            type="checkbox"
            checked={consent}
            disabled={restoring}
            onChange={event => setConsent(event.target.checked)}
          />
          <span>Allow this conversation to use a hosted provider</span>
        </label>

        {providers ? (
          <ul className="companion-coach-provider-list">
            {(['groq', 'gemini'] as const).map(name => {
              const info = providers.providers[name];
              return (
                <li key={name}>
                  <span>{providerLabel(name)}</span>
                  <span className={info?.configured ? 'is-ready' : 'is-missing'}>
                    {info?.configured ? 'configured on this server' : 'not configured'}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="companion-coach-note">
            {providersError ?? 'Checking which providers this server has…'}
          </p>
        )}

        {hostedNotConfigured && (
          <p className="companion-coach-honest">
            <CloudOff aria-hidden="true" size={15} />
            <span>{providerLabel(provider)} is not configured on this server; your message stays local.</span>
          </p>
        )}
        {!hostedNotConfigured && provider !== 'local' && !consent && (
          <p className="companion-coach-honest">
            <ShieldCheck aria-hidden="true" size={15} />
            <span>Without the consent box ticked, this message is answered locally.</span>
          </p>
        )}
        {remoteAllowed && !hostedNotConfigured && (
          <p className="companion-coach-honest">
            <ShieldCheck aria-hidden="true" size={15} />
            <span>This turn may be sent to {providerLabel(provider)}. The evidence block is still rendered on this server.</span>
          </p>
        )}
      </div>
    </section>
  );
}

export default CompanionCoach;
