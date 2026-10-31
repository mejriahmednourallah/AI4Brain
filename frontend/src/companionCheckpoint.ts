export type CompanionCheckpointSignal = {
  id: string;
  sessionId: string;
  activityId: string;
  attemptId: string;
  kind: 'ready' | 'checkpoint' | 'completed' | 'assistance';
  text: string;
  evidenceRevision?: string;
  subject?: string;
};

export type CompanionCheckpointHandler = (signal: CompanionCheckpointSignal) => void;
export type TimedWindowHandler = (active: boolean) => void;
export function emitCompanionCheckpoint(
  callback: CompanionCheckpointHandler | undefined,
  signal: CompanionCheckpointSignal,
): void {
  if (signal.sessionId && signal.attemptId && signal.id && signal.text.trim()) callback?.(signal);
}
