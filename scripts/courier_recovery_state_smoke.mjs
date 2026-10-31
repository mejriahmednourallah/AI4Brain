import assert from 'node:assert/strict';
import { matchesCourierActionEvent, matchesCourierCompletionEvent, replayCourierEvents } from '../frontend/src/redesign/hybrid/courierRecovery.js';

const config = {
  activity_version: 'hy-01-v2',
  board: { cols: 3, rows: 2, start: [0, 0], walls: [[1, 0]] },
  parcels: [{ parcel_id: 'parcel-1', cell: [1, 1] }, { parcel_id: 'parcel-2', cell: [2, 1] }],
  destinations: [{ destination_id: 'plot-A', cell: [2, 0] }, { destination_id: 'plot-B', cell: [0, 1] }],
  gates: [{ gate_id: 'gate-a', cell: [0, 1] }],
};
const action = (sequence, type, payload) => ({
  event_id: `event-${sequence}`, sequence, type: 'hybrid_action_recorded',
  payload: { action_sequence: sequence, action_type: type, action: payload, elapsed_ms: sequence * 100 },
});
const events = [
  action(1, 'move', { direction: 'right' }), // hedge: canonical evaluator ignores the move
  action(2, 'move', { direction: 'up' }), // outside board
  action(3, 'move', { direction: 'down' }),
  action(4, 'move', { direction: 'right' }), // parcel 1
  action(5, 'deliver', { parcel_id: 'parcel-1' }), // path, not a plot: keep carrying
  action(6, 'move', { direction: 'right' }), // carrying: parcel 2 is not collected
  action(7, 'move', { direction: 'up' }),
  action(8, 'deliver', { parcel_id: 'parcel-1' }),
  action(9, 'move', { direction: 'down' }), // parcel 2
  action(10, 'move', { direction: 'left' }),
  action(11, 'move', { direction: 'left' }),
  action(12, 'deliver', { parcel_id: 'parcel-2' }),
  action(13, 'move', { direction: 'right' }), // empty-handed revisit of delivered parcel 1
  action(14, 'move', { direction: 'left' }),
];
const state = replayCourierEvents(config, events);
assert.deepEqual(state.position, [0, 1]);
assert.equal(state.moves, 9);
assert.equal(state.deliveries, 2);
assert.equal(state.carried, null);
assert.deepEqual(state.deliveredParcels, ['parcel-1', 'parcel-2']);
assert.deepEqual(state.gatesSeen, ['gate-a']);
assert.deepEqual(replayCourierEvents(config, [...events].reverse()), state);
assert.equal(replayCourierEvents({ ...config, activity_version: 'hy-01-v1' }, events).carried, 'parcel-1');

const actionRequest = { event_id: 'event-1', sequence: 1, action_type: 'move', payload: { direction: 'right' }, elapsed_ms: 100 };
assert.equal(matchesCourierActionEvent(events[0], actionRequest), true);
assert.equal(matchesCourierActionEvent(events[0], { ...actionRequest, elapsed_ms: 101 }), false);
assert.equal(matchesCourierActionEvent(events[0], { ...actionRequest, payload: { direction: 'down' } }), false);

const completion = {
  event_id: 'completion-1', sequence: 11, type: 'hybrid_attempt_completed',
  payload: { interrupted: false, visibility_interrupted: false, response_time_ms: 3210 },
};
assert.equal(matchesCourierCompletionEvent(completion, { event_id: 'completion-1', interrupted: false, response_time_ms: 3210 }), true);
assert.equal(matchesCourierCompletionEvent(completion, { event_id: 'completion-1', interrupted: true, response_time_ms: 3210 }), false);
assert.equal(matchesCourierCompletionEvent(completion, { event_id: 'other', interrupted: false, response_time_ms: 3210 }), false);

console.log('courier_recovery_state_smoke: PASS; canonical blocked-step replay, plot-only deliveries, v2 no-repickup, exact action/completion identity.');
