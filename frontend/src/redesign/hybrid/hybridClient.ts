/** Canonical hybrid-v1 API client. Presentation never decides correctness. */
export type HybridActivity = {
  activity_id: string;
  activity_version: string;
  config_version: string;
  title: string;
  world: string;
  summary: string;
  scenarios: string;
  status: string;
  assistance_windows: string[];
  assistance_exposures: string[];
};

export type CourierConfig = {
  activity_id: string;
  activity_version: string;
  mode: string;
  tier: string;
  seed: string;
  board: { cols: number; rows: number; start: [number, number]; walls: [number, number][] };
  destinations: { destination_id: string; cell: [number, number] }[];
  parcels: { parcel_id: string; cell: [number, number] }[];
  gates: { gate_id: string; cell: [number, number] }[];
  bell: { after_moves: number };
  plans: { order: number; parcel_id: string; destination_id: string; cue: string; promise: string }[];
  encode_ms: number;
  assistance_windows?: string[];
};

export type LivingArchiveConfig = {
  activity_id: 'HY-05';
  activity_version: string;
  config_version: string;
  mode: string;
  tier: string;
  seed: string;
  encode_ms: number;
  objects: { object_id: string; label: string }[];
  slots: number[];
  clues: { clue_id: string; left: string; right: string; relation: string; text: string }[];
  assistance_windows: string[];
};

export type GenericHybridConfig = {
  activity_id: string;
  activity_version: string;
  config_version: string;
  mode: string;
  tier: string;
  seed: string;
  [key: string]: unknown;
};
export type HybridConfig = CourierConfig | LivingArchiveConfig | GenericHybridConfig;

export type HybridAttempt = {
  attempt_id: string;
  event_id: string;
  session_id: string;
  activity_id: string;
  activity_version: string;
  mode: string;
  difficulty_tier: string;
  seed: string;
  config: HybridConfig;
  assistance: { windows: string[]; exposures: string[]; policy: string };
  created_at: string;
};

export type PromiseResult = {
  order: number;
  parcel_id: string;
  destination_id: string;
  cue: string;
  promise: string;
  satisfied: boolean;
  reason: string;
  cue_met: boolean;
  wrong_destination?: boolean;
};

export type HybridOutcome = {
  attempt_id: string;
  activity_id: string;
  activity_version: string;
  evaluation_version: string;
  completion_state: string;
  assisted: boolean;
  excluded_from_unassisted: boolean;
  outcomes: {
    promises_satisfied: number;
    promises_total: number;
    cue_misses: number;
    wrong_destination_deliveries: number;
    order_deviations: number;
    moves: number;
    optimal_moves: number;
    path_overhead: number;
    blocked_moves: number;
    bell: { after_moves: number; rang: boolean };
    promises: PromiseResult[];
    committed?: boolean;
    complete_placement?: boolean;
    valid_arrangement?: boolean;
    objects_placed?: number;
    object_count?: number;
    relations_satisfied?: number;
    relations_total?: number;
    placement?: (string | null)[];
    first_conflict?: { clue_id: string; relation: string; left: string; right: string; satisfied: boolean; recorded_clue: string } | null;
    conflicts?: { clue_id: string; relation: string; left: string; right: string; satisfied: boolean; recorded_clue: string }[];
    placement_history?: { event_id?: string; sequence?: number; object_id: string; slot_index: number; displaced_object_id: string | null }[];
    valid_alternatives?: string[][];
    [key: string]: unknown;
  };
  evidence_ids: string[];
  limitations: string[];
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((entry: { msg?: string }) => entry?.msg ?? 'Invalid request').join('; ')
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload as T;
}

export const hybridUid = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;

export const fetchHybridCatalog = () =>
  request<{ activities: HybridActivity[]; note: string }>('/api/hybrid/catalog');

export const fetchHybridSummary = (learnerId: string) =>
  request<{
    activities: (HybridActivity & { attempts: number; unassisted_attempts: number; assisted_attempts: number; latest: HybridOutcome | null })[];
    note: string;
  }>(`/api/hybrid/summary/${encodeURIComponent(learnerId)}`);

export const startHybridAttempt = (body: {
  event_id: string;
  session_id: string;
  activity_id: string;
  activity_version: string;
  config_version?: string;
  mode: 'tutorial' | 'training' | 'challenge';
  difficulty_tier: string;
  seed?: string;
}) => request<HybridAttempt>('/api/hybrid/attempts', { method: 'POST', body: JSON.stringify(body) });

export const recordHybridAction = (attemptId: string, body: {
  event_id: string;
  sequence: number;
  action_type: 'move' | 'deliver' | 'select' | 'commit' | 'respond' | 'switch' | 'advise';
  payload: Record<string, unknown>;
  elapsed_ms?: number | null;
}) =>
  request<{ accepted: boolean; replayed: boolean; event_id: string; sequence: number }>(
    `/api/hybrid/attempts/${attemptId}/actions`,
    { method: 'POST', body: JSON.stringify({ attempt_id: attemptId, ...body }) },
  );

export const recordHybridAssistance = (attemptId: string, body: {
  event_id: string;
  exposure_kind: string;
  checkpoint: string;
  checkpoint_version?: string;
  source_event_id?: string | null;
}) =>
  request<{ accepted: boolean; event_id: string; sequence: number }>(
    `/api/hybrid/attempts/${attemptId}/assistance`,
    { method: 'POST', body: JSON.stringify({ attempt_id: attemptId, ...body }) },
  );

export type Hy02ReviewCue = { cue_id: string; position: number; symbol: string };
export type Hy02ReviewHistory = {
  attempt_id: string;
  activity_id: 'HY-02';
  activity_version: string;
  config_version: string;
  n_back: number;
  stream_count: number;
  assistance_event_id: string;
  trials: {
    trial_index: number;
    cue_event_id: string;
    history_cues: Hy02ReviewCue[];
    current_cue: Hy02ReviewCue;
    comparison_cue: Hy02ReviewCue | null;
    response_time_ms: number | null;
    position_match_expected: boolean;
    position_match_response: boolean;
    position_correct: boolean;
    symbol_match_expected: boolean;
    symbol_match_response: boolean;
    symbol_correct: boolean;
  }[];
};

export const fetchHy02ReviewHistory = (attemptId: string, sessionId: string, assistanceEventId: string) =>
  request<Hy02ReviewHistory>(
    `/api/hybrid/attempts/${encodeURIComponent(attemptId)}/review-history?session_id=${encodeURIComponent(sessionId)}&assistance_event_id=${encodeURIComponent(assistanceEventId)}`,
  );

export const completeHybridAttempt = (attemptId: string, body: {
  event_id: string;
  interrupted?: boolean;
  visibility_interrupted?: boolean;
  response_time_ms?: number | null;
}) =>
  request<HybridOutcome>(`/api/hybrid/attempts/${attemptId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ attempt_id: attemptId, ...body }),
  });

export const fetchHybridAttempt = (attemptId: string) =>
  request<{ attempt_id: string; session_id: string; activity_id: string; activity_version: string; mode: string; difficulty_tier: string; seed: string; config_version: string; status: string; started_at: string; config: HybridConfig; events: { event_id: string; sequence: number; type: string; payload: Record<string, unknown> }[]; assistance: { event_id: string; exposure_kind: string; checkpoint: string; source_event_id: string | null }[]; outcome: HybridOutcome | null }>(
    `/api/hybrid/attempts/${attemptId}`,
  );
