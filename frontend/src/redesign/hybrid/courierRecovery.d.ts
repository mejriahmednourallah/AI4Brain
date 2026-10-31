import type { CourierConfig } from './hybridClient';

export type CourierRecoveryEvent = {
  event_id: string;
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
};

export type CourierReplayState = {
  position: [number, number];
  carried: string | null;
  deliveredParcels: string[];
  moves: number;
  deliveries: number;
  gatesSeen: string[];
};

export function replayCourierEvents(config: CourierConfig, events: CourierRecoveryEvent[]): CourierReplayState;
export function matchesCourierActionEvent(event: CourierRecoveryEvent | undefined, request: Record<string, unknown>): boolean;
export function matchesCourierCompletionEvent(event: CourierRecoveryEvent | undefined, request: Record<string, unknown>): boolean;
