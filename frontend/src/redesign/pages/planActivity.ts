import type { PlanStep } from './PlanPage';

export type PlanActivityRef = NonNullable<PlanStep['activity_ref']>;
export type PlanStepLaunchBody = {
  request_id: string;
  session_id: string;
  mode?: string;
  difficulty_tier?: string;
};
export type PlanStepLaunchResponse = {
  plan_id: string;
  step_id: string;
  activity_ref: PlanActivityRef;
  attempt_ref: { kind: 'core' | 'hybrid' | 'crystal'; id: string; version: string };
  destination: { kind: 'core' | 'hybrid' | 'crystal'; id: string };
  status: 'started';
  idempotent_replay: boolean;
};
export type PersistedPlanLaunch = {
  plan_id: string;
  step_id: string;
  request_body: PlanStepLaunchBody;
  activity_ref: PlanActivityRef;
  response?: PlanStepLaunchResponse;
};

export function isPlanActivityRef(value: unknown): value is PlanActivityRef {
  if (!value || typeof value !== 'object') return false;
  const ref = value as Record<string, unknown>;
  return ['core', 'hybrid', 'crystal'].includes(String(ref.kind))
    && typeof ref.id === 'string' && typeof ref.version === 'string';
}

export function parsePersistedPlanLaunch(raw: string | null): PersistedPlanLaunch | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as PersistedPlanLaunch;
    if (typeof value.plan_id !== 'string' || typeof value.step_id !== 'string'
      || typeof value.request_body?.request_id !== 'string' || typeof value.request_body?.session_id !== 'string'
      || !isPlanActivityRef(value.activity_ref)) return null;
    return value;
  } catch { return null; }
}
