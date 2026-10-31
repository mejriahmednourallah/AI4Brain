/**
 * Typed client for the coach-v2 API.
 *
 * The browser never talks to a hosted provider: it only states which provider the
 * learner would allow. Provider selection, consent and every evidence-grounded
 * sentence are decided and rendered by the backend.
 */

export type CoachPhase = 'overview' | 'training' | 'baseline' | 'reassessment' | 'practice';
export type CoachProviderId = 'local' | 'groq' | 'gemini';
export type CoachExerciseId = 'EX-01' | 'EX-02' | 'EX-03' | 'EX-04' | 'EX-05';
export type CoachActionId = 'inspect_evidence' | 'try_strategy' | 'open_practice' | 'change_focus';

export type CoachTurnRequest = {
  session_id: string;
  message: string;
  allow_remote: boolean;
  phase: CoachPhase;
  training_block_id?: string | null;
  item_id?: string | null;
  request_id?: string | null;
  provider: CoachProviderId;
  focus_exercise_id?: CoachExerciseId | null;
  subject_exercise_id?: CoachExerciseId | null;
  provider_consent_recorded: boolean;
};

export type CoachProviderInfo = {
  configured: boolean;
  model: string;
  default_model: string;
};

export type CoachProviderStatus = {
  providers: Record<string, CoachProviderInfo>;
  default: string;
  note: string;
};

export type CoachSubject = {
  exercise_id: string | null;
  dimension: string | null;
  label: string | null;
  resolved_from: string;
};

export type CoachAction = {
  id: CoachActionId | (string & {});
  kind: 'navigate' | 'assistance';
  label: string;
  target?: string;
  strategy_id?: string;
  exercise_id?: string;
};

export type CoachReply = {
  observation: string;
  explanation: string;
  rationale: string;
  strategy_id: string | null;
  strategy_title: string | null;
  strategy_guidance: string | null;
  follow_up: string;
  caveat: string;
  evidence_ids: string[];
  recommended_exercise_id: string | null;
  recommended_difficulty: string | null;
  next_step_note: string;
  clarification: string | null;
  actions: CoachAction[];
};

export type CoachTurnResult = {
  coach_version: string;
  source: string;
  provider_status: string;
  provider_requested: string;
  provider_used: string;
  model: string | null;
  fallback_reason: string | null;
  evidence_revision: string;
  spoken_summary: string | null;
  subject: CoachSubject;
  response: CoachReply;
  assisted_training: boolean;
  relevant_evidence_ids: string[];
  context_limitations: string[];
  event_id: string;
  opportunities: unknown[];
  replayed?: boolean;
  local_response?: CoachLocalResponse | null;
};

export type CoachLocalResponse = {
  request_id: string;
  status: string;
  label: string;
  source: string;
  provider_status: string;
  provider_requested: string;
  provider_used: string;
  model: string | null;
  evidence_revision: string;
  spoken_summary: string | null;
  subject: CoachSubject;
  response: string;
  assisted_training: boolean;
  relevant_evidence_ids: string[];
  context_limitations: string[];
  provider_requested_opt_in: boolean;
};

export type CoachStoredTurn = {
  requestId: string;
  message: string;
  status: string;
  providerUsed: string | null;
  subjectExerciseId: string | null;
  evidenceRevision: string | null;
  createdAt: string;
  answer: CoachTurnResult | null;
};

export type CoachConversation = {
  sessionId: string;
  subjectExerciseId: string | null;
  provider: string;
  consentRecorded: boolean;
  turns: CoachStoredTurn[];
};

export type CoachStreamEvidence = {
  subject: CoachSubject;
  evidence_ids: string[];
  evidence_revision: string;
  limitations: string[];
};

export type CoachStreamHandlers = {
  signal?: AbortSignal;
  onAcknowledged?: (payload: { request_id: string | null; started_at: string }) => void;
  onEvidence?: (payload: CoachStreamEvidence) => void;
  onLocalResponse?: (payload: CoachLocalResponse) => void;
};

export type CoachCancelHandle = {
  signal: AbortSignal;
  cancel: (reason?: string) => void;
};

export class CoachRequestError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'CoachRequestError';
    this.status = status;
    this.detail = detail;
  }
}

// The app is served from the same origin as the API and declares no VITE_API_BASE,
// so the coach endpoints are addressed with relative paths.
const PROVIDERS_PATH = '/api/coach/providers';
const COACH_PATH = '/api/coach';
const STREAM_PATH = '/api/coach/stream';
const CONVERSATION_PATH = '/api/coach/conversation';

export function createCoachCancel(): CoachCancelHandle {
  const controller = new AbortController();
  return {
    signal: controller.signal,
    cancel: (reason?: string) => {
      if (!controller.signal.aborted) controller.abort(reason ?? 'cancelled');
    },
  };
}

/** One id per learner turn; an exact retry reuses it so the server reconciles instead of duplicating. */
export function newRequestId(): string {
  return crypto.randomUUID();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
}

function normalizeActions(value: unknown): CoachAction[] {
  if (!Array.isArray(value)) return [];
  const actions: CoachAction[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const id = asString(record.id);
    const kind = asString(record.kind);
    const label = asString(record.label);
    if (!id || !label) continue;
    if (kind !== 'navigate' && kind !== 'assistance') continue;
    const action: CoachAction = { id, kind, label };
    const target = asString(record.target);
    const strategyId = asString(record.strategy_id);
    const exerciseId = asString(record.exercise_id);
    if (target) action.target = target;
    if (strategyId) action.strategy_id = strategyId;
    if (exerciseId) action.exercise_id = exerciseId;
    actions.push(action);
  }
  return actions;
}

export function normalizeTurnResult(raw: unknown): CoachTurnResult | null {
  const record = asRecord(raw);
  if (!record) return null;
  const subject = asRecord(record.subject);
  const reply = asRecord(record.response);
  if (!reply) return null;
  return {
    coach_version: asString(record.coach_version) ?? '',
    source: asString(record.source) ?? '',
    provider_status: asString(record.provider_status) ?? 'unknown',
    provider_requested: asString(record.provider_requested) ?? 'local',
    provider_used: asString(record.provider_used) ?? 'local',
    model: asString(record.model),
    fallback_reason: asString(record.fallback_reason),
    evidence_revision: asString(record.evidence_revision) ?? '',
    spoken_summary: asString(record.spoken_summary),
    subject: {
      exercise_id: asString(subject?.exercise_id),
      dimension: asString(subject?.dimension),
      label: asString(subject?.label),
      resolved_from: asString(subject?.resolved_from) ?? 'unknown',
    },
    response: {
      observation: asString(reply.observation) ?? '',
      explanation: asString(reply.explanation) ?? '',
      rationale: asString(reply.rationale) ?? '',
      strategy_id: asString(reply.strategy_id),
      strategy_title: asString(reply.strategy_title),
      strategy_guidance: asString(reply.strategy_guidance),
      follow_up: asString(reply.follow_up) ?? '',
      caveat: asString(reply.caveat) ?? '',
      evidence_ids: asStringArray(reply.evidence_ids),
      recommended_exercise_id: asString(reply.recommended_exercise_id),
      recommended_difficulty: asString(reply.recommended_difficulty),
      next_step_note: asString(reply.next_step_note) ?? '',
      clarification: asString(reply.clarification),
      actions: normalizeActions(reply.actions),
    },
    assisted_training: record.assisted_training === true,
    relevant_evidence_ids: asStringArray(record.relevant_evidence_ids),
    context_limitations: asStringArray(record.context_limitations),
    event_id: asString(record.event_id) ?? '',
    opportunities: Array.isArray(record.opportunities) ? (record.opportunities as unknown[]) : [],
    replayed: record.replayed === true,
    local_response: normalizeLocalResponse(record.local_response),
  };
}

function normalizeLocalResponse(raw: unknown): CoachLocalResponse | null {
  const record = asRecord(raw);
  if (!record) return null;
  const responseObject = asRecord(record.response);
  const spokenSummary = asString(record.spoken_summary);
  const responseText = asString(record.response) ?? (responseObject
    ? [responseObject.observation, responseObject.explanation, responseObject.rationale,
      responseObject.strategy_title, responseObject.strategy_guidance, responseObject.next_step_note,
      responseObject.follow_up, responseObject.caveat, responseObject.clarification]
      .map(asString).filter((part): part is string => Boolean(part?.trim())).join(' ')
    : null);
  const displayResponse = responseText ?? spokenSummary;
  if (!displayResponse) return null;
  const subject = asRecord(record.subject);
  return {
    request_id: asString(record.request_id) ?? '',
    status: asString(record.status) ?? 'local_only',
    label: asString(record.label) ?? 'Local answer',
    source: asString(record.source) ?? 'server_grounded_local',
    provider_status: asString(record.provider_status) ?? 'local_only',
    provider_requested: asString(record.provider_requested) ?? 'local',
    provider_used: asString(record.provider_used) ?? 'local',
    model: asString(record.model),
    evidence_revision: asString(record.evidence_revision) ?? '',
    spoken_summary: spokenSummary,
    subject: {
      exercise_id: asString(subject?.exercise_id), dimension: asString(subject?.dimension),
      label: asString(subject?.label), resolved_from: asString(subject?.resolved_from) ?? 'unknown',
    },
    response: displayResponse,
    assisted_training: record.assisted_training === true,
    relevant_evidence_ids: asStringArray(record.relevant_evidence_ids),
    context_limitations: asStringArray(record.context_limitations),
    provider_requested_opt_in: record.provider_requested_opt_in === true,
  };
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const record = asRecord(body);
    const detail = record ? record.detail ?? record.error : null;
    if (typeof detail === 'string' && detail.trim()) return detail;
  } catch {
    // The body was not JSON; fall through to a status-based description.
  }
  if (response.status === 404) return 'This session is not available on the server.';
  if (response.status === 409) return 'The coach could not record this turn.';
  return `The coach request failed (${response.status}).`;
}

export async function fetchProviderStatus(signal?: AbortSignal): Promise<CoachProviderStatus> {
  const response = await fetch(PROVIDERS_PATH, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'omit',
    signal,
  });
  if (!response.ok) throw new CoachRequestError(response.status, await readDetail(response));
  const body = asRecord(await response.json());
  const providersRaw = body ? asRecord(body.providers) : null;
  const providers: Record<string, CoachProviderInfo> = {};
  for (const [name, value] of Object.entries(providersRaw ?? {})) {
    const info = asRecord(value);
    if (!info) continue;
    providers[name] = {
      configured: info.configured === true,
      model: asString(info.model) ?? '',
      default_model: asString(info.default_model) ?? '',
    };
  }
  return {
    providers,
    default: asString(body?.default) ?? 'local',
    note: asString(body?.note) ?? '',
  };
}

export async function fetchConversation(sessionId: string, signal?: AbortSignal): Promise<CoachConversation> {
  const response = await fetch(`${CONVERSATION_PATH}?session_id=${encodeURIComponent(sessionId)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'omit',
    signal,
  });
  if (!response.ok) throw new CoachRequestError(response.status, await readDetail(response));
  const body = asRecord(await response.json());
  const turnsRaw = body && Array.isArray(body.turns) ? body.turns : [];
  const turns: CoachStoredTurn[] = [];
  for (const item of turnsRaw) {
    const turn = asRecord(item);
    if (!turn) continue;
    const requestId = asString(turn.request_id);
    if (!requestId) continue;
    turns.push({
      requestId,
      message: asString(turn.message) ?? '',
      status: asString(turn.status) ?? 'completed',
      providerUsed: asString(turn.provider_used),
      subjectExerciseId: asString(turn.subject),
      evidenceRevision: asString(turn.evidence_revision),
      createdAt: asString(turn.created_at) ?? '',
      answer: turn.response ? normalizeTurnResult(turn.response) : null,
    });
  }
  return {
    sessionId: asString(body?.session_id) ?? sessionId,
    subjectExerciseId: body ? asString(body.subject_exercise_id) : null,
    provider: asString(body?.provider) ?? 'local',
    consentRecorded: body ? body.consent_recorded === true : false,
    turns,
  };
}

export async function sendCoachTurn(body: CoachTurnRequest, signal?: AbortSignal): Promise<CoachTurnResult> {
  const response = await fetch(COACH_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
    credentials: 'omit',
    signal,
  });
  if (!response.ok) throw new CoachRequestError(response.status, await readDetail(response));
  const answer = normalizeTurnResult(await response.json());
  if (!answer) throw new CoachRequestError(response.status, 'The coach returned an unreadable answer.');
  return answer;
}

function parseFrame(frame: string): { event: string; data: string } | null {
  let event = 'message';
  const data: string[] = [];
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
    if (!line || line.startsWith(':')) continue;
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
  }
  if (!data.length) return null;
  return { event, data: data.join('\n') };
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/**
 * POST /api/coach/stream read through a ReadableStream (EventSource cannot send a body).
 * Resolves with the validated `answer` event; rejects if the stream ends without one.
 */
export async function streamCoachTurn(
  body: CoachTurnRequest,
  handlers: CoachStreamHandlers = {},
): Promise<CoachTurnResult> {
  const response = await fetch(STREAM_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    credentials: 'omit',
    signal: handlers.signal,
  });
  if (!response.ok) throw new CoachRequestError(response.status, await readDetail(response));
  if (!response.body) throw new CoachRequestError(502, 'The coach stream had no readable body.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer: CoachTurnResult | null = null;

  const consume = (frame: string) => {
    const parsed = parseFrame(frame);
    if (!parsed) return;
    if (parsed.event === 'acknowledged') {
      const payload = asRecord(parseJson(parsed.data));
      handlers.onAcknowledged?.({
        request_id: payload ? asString(payload.request_id) : null,
        started_at: payload ? asString(payload.started_at) ?? '' : '',
      });
      return;
    }
    if (parsed.event === 'evidence') {
      const payload = asRecord(parseJson(parsed.data));
      if (!payload) return;
      const subject = asRecord(payload.subject);
      handlers.onEvidence?.({
        subject: {
          exercise_id: asString(subject?.exercise_id),
          dimension: asString(subject?.dimension),
          label: asString(subject?.label),
          resolved_from: asString(subject?.resolved_from) ?? 'unknown',
        },
        evidence_ids: asStringArray(payload.evidence_ids),
        evidence_revision: asString(payload.evidence_revision) ?? '',
        limitations: asStringArray(payload.limitations),
      });
      return;
    }
    if (parsed.event === 'local_response') {
      const payload = normalizeLocalResponse(parseJson(parsed.data));
      if (payload) handlers.onLocalResponse?.(payload);
      return;
    }
    if (parsed.event === 'answer') {
      answer = normalizeTurnResult(parseJson(parsed.data));
    }
  };

  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      for (const frame of frames) consume(frame);
    }
    buffer += decoder.decode();
    if (buffer.trim()) consume(buffer);
  } finally {
    reader.releaseLock();
  }

  if (!answer) throw new CoachRequestError(502, 'The coach stream ended before an answer arrived.');
  return answer;
}
