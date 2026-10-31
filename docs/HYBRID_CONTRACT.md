# hybrid-v1 evidence and assistance contract

Status: implemented and browser-verified for HY-01 (The Courier's Promise). HY-02 to HY-06 are
not implemented yet; the contract below is the versioned shape they must use.

## Why a separate contract

Hybrid activities are original activities, not new instances of the five fixed task families.
They therefore contribute to **none** of the five baseline indices. Their records live in their
own append-only SQLite tables and never pass through an EX scorer, the difficulty tier machine,
the recommendation policy or participation XP.

| Concern | EX activities | Hybrid activities |
| --- | --- | --- |
| Tables | `events`, `event_submissions` | `hybrid_attempts`, `hybrid_events`, `hybrid_assistance`, `hybrid_outcomes` |
| Scorer | `scoring.py`, `battery_scoring.py` | `hybrid_activities.evaluate` per activity version |
| Index | contributes to a family index | descriptive outcomes only, no cross-task score |
| Schema version | `SCHEMA_VERSION` / `EXERCISE_VERSION` | `hybrid-v1` / `<activity>-v1` |
| Assistance signal | `hint_count`, `replay_count`, `assisted_training` | `hybrid_assistance` rows + `excluded_from_unassisted` |

Verified: after a hybrid session that recorded an assisted and an unassisted attempt, the EX
session event list contained only `consent_recorded`, and all five dimensions stayed
`INCOMPLETE_BASELINE` with a null index (`output/verification/hybrid/hy01-contract.json`).

## Shared hybrid-v1 fields

Every record carries: immutable `event_id`, `session_id`, `learner_id`, `attempt_id`, `activity_id`
(HY-01…HY-06), `activity_version`, `mode` (`tutorial` | `training` | `challenge`),
`config_version`, `difficulty_tier`, `seed`, the full `config` needed to reproduce the activity,
ordered actions with their `action_sequence`, approximate `elapsed_ms`, interruption and
visibility-interruption flags, canonical assistance exposures with `source_event_id`,
backend-derived `outcomes` with `evaluation_version`, and `evidence_ids` listing every immutable
record that supports the review.

## Event types

| Event type | When | Idempotency |
| --- | --- | --- |
| `hybrid_attempt_started` | attempt creation, sequence 0 | re-posting the same start with the same seed/config returns the stored attempt; a different config is `409` |
| `hybrid_action_recorded` | each move/deliver/respond action | same `event_id` + same payload returns the stored event (`replayed: true`); the same `event_id` with a different payload is `409`; a skipped `action_sequence` is `409` |
| `hybrid_assistance_exposed` | before any help is shown | recorded before the help renders; a second exposure in a closed window is `409` |
| `hybrid_attempt_completed` | completion, evaluation and outcome | completing twice returns the stored outcome (no re-evaluation, no duplicate evidence) |

`hybrid_events` is append-only (`BEFORE UPDATE`/`BEFORE DELETE` triggers raise), and
`(attempt_id, sequence)` is unique. `hybrid_assistance` and `hybrid_outcomes` are immutable.

## Assistance policy (user-approved, 20 October 2026)

* Tutorials are separate from unassisted training evidence.
* Revealing a remembered intention, replaying hidden cues, revealing a hidden clue, a solution
  hint or an oracle route suggestion is assistance. The exposure is recorded first, then shown.
* An assisted attempt is retained in a clearly labelled review and excluded from unassisted
  summaries and from any adaptive eligibility. It is never erased or presented as unaided.
* Normal information that the versioned configuration explicitly shows (the encode phase, a
  visible rule sign, an advice card being evaluated) is part of the task, not assistance.
* In HY-06 the advice under evaluation — including deliberately incorrect or uncertain advice —
  is a recorded stimulus. Extra help that reveals the correct judgement or route is assistance.
* Windows are enforced server-side; help never silently pauses a deadline.

| Activity | Allowed assistance windows |
| --- | --- |
| HY-01 | `pre_play`, `safe_checkpoint`, `post_completion` |
| HY-02 | `pre_block`, `post_window` |
| HY-03 | `pre_play`, `boundary` |
| HY-04 | `pre_wave`, `between_waves` |
| HY-05 | `pre_encoding`, `post_commit` |
| HY-06 | `advice_checkpoint`, `post_commit` |

`pre_*` windows close permanently once the first action is recorded; `post_completion` requires the
attempt to be completed first.

## Determinism

`seed` is client-supplied or derived from `sha256(session_id|activity_id|event_id)`. Generators are
pure functions of `(seed, activity_id, activity_version, mode, tier)`. Re-starting with the same
seed reproduced a byte-identical configuration in QA (`determinism.same_seed_identical_config:
true`).

## HY-01 mechanics and outcomes

Board, walls, start, plots, parcels, gates and the bell threshold come from the stored config.
The player sees the promises during `encode_ms`, then the garden hides them. Stepping on a parcel
picks it up; `deliver` acts on the current cell. The bell "rings" when the recorded move count
reaches `bell.after_moves`.

Recorded outcomes: `promises_satisfied`, `promises_total`, `cue_misses`,
`wrong_destination_deliveries`, `order_deviations`, `moves`, `optimal_moves` (BFS lower bound for
the promised order), `path_overhead`, `blocked_moves`, per-promise `reason`, `bell.rang`, plus the
ordered deliveries, pickups and gates visited. No correctness is computed on the client.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/hybrid/catalog` | implemented activities, versions, assistance windows |
| POST | `/api/hybrid/attempts` | start an attempt, return the config and reproducibility fields |
| GET | `/api/hybrid/attempts/{attempt_id}` | attempt, ordered events, assistance rows, outcome |
| POST | `/api/hybrid/attempts/{attempt_id}/actions` | append one ordered action |
| POST | `/api/hybrid/attempts/{attempt_id}/assistance` | record an assistance exposure |
| POST | `/api/hybrid/attempts/{attempt_id}/complete` | evaluate, store and return the outcome |
| GET | `/api/hybrid/summary/{learner_id}` | per-activity attempts, unassisted vs assisted, latest outcome |

## Evidence

* `output/verification/hybrid/verify_hybrid_contract.py` → `hy01-contract.json`
* `output/verification/hybrid/verify_hy01_browser.cjs` → `hy01-browser/` (screenshots + result)
* QA stack: isolated API `:8021` against a disposable database, Vite `:5190`. No primary learner
  data was written.
