const DIRECTIONS = {
  up: [0, -1],
  down: [0, 1],
  left: [-1, 0],
  right: [1, 0],
};

const cellKey = (cell) => `${cell[0]},${cell[1]}`;

/** Rebuild the displayed Courier state from immutable canonical action events. */
export function replayCourierEvents(config, events) {
  const position = [...config.board.start];
  const walls = new Set(config.board.walls.map(cellKey));
  const parcelByCell = new Map(config.parcels.map(parcel => [cellKey(parcel.cell), parcel.parcel_id]));
  const gateByCell = new Map(config.gates.map(gate => [cellKey(gate.cell), gate.gate_id]));
  const destinations = new Set(config.destinations.map(destination => cellKey(destination.cell)));
  const v2 = config.activity_version === 'hy-01-v2';
  const gatesSeen = [];
  const deliveredParcels = [];
  let carried = null;
  let moves = 0;
  let deliveries = 0;

  const sorted = [...events].sort((a, b) => Number(a.payload?.action_sequence ?? a.sequence) - Number(b.payload?.action_sequence ?? b.sequence));
  for (const event of sorted) {
    if (event.type !== 'hybrid_action_recorded') continue;
    const payload = event.payload ?? {};
    if (payload.action_type === 'move') {
      const delta = DIRECTIONS[payload.action?.direction];
      if (!delta) continue;
      const next = [position[0] + delta[0], position[1] + delta[1]];
      if (next[0] < 0 || next[0] >= config.board.cols || next[1] < 0 || next[1] >= config.board.rows || walls.has(cellKey(next))) continue;
      position[0] = next[0];
      position[1] = next[1];
      moves += 1;
      const gate = gateByCell.get(cellKey(position));
      if (gate && !gatesSeen.includes(gate)) gatesSeen.push(gate);
      if (!carried) {
        const parcel = parcelByCell.get(cellKey(position));
        if (parcel && (!v2 || !deliveredParcels.includes(parcel))) carried = parcel;
      }
    } else if (payload.action_type === 'deliver' && carried && destinations.has(cellKey(position))) {
      if (v2 && !deliveredParcels.includes(carried)) deliveredParcels.push(carried);
      carried = null;
      deliveries += 1;
    }
  }
  return { position, carried, deliveredParcels, moves, deliveries, gatesSeen };
}

/** Compare all client-supplied action identity fields with a saved canonical event. */
export function matchesCourierActionEvent(event, request) {
  const payload = event?.payload ?? {};
  return event?.event_id === request.event_id
    && Number(payload.action_sequence ?? event.sequence) === request.sequence
    && payload.action_type === request.action_type
    && JSON.stringify(payload.action ?? {}) === JSON.stringify(request.payload ?? {})
    && (payload.elapsed_ms ?? null) === (request.elapsed_ms ?? null)
    && (payload.cue_event_id ?? null) === (request.cue_event_id ?? null)
    && Boolean(payload.visibility_interrupted) === Boolean(request.visibility_interrupted);
}

/** A pending completion may be cleared only by its exact canonical event. */
export function matchesCourierCompletionEvent(event, request) {
  const payload = event?.payload ?? {};
  return event?.event_id === request.event_id
    && Boolean(payload.interrupted) === Boolean(request.interrupted)
    && Boolean(payload.visibility_interrupted) === Boolean(request.visibility_interrupted)
    && (payload.response_time_ms ?? null) === (request.response_time_ms ?? null);
}
