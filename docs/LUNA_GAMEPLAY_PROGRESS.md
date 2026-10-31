# Luna gameplay implementation progress

This note records implementation and local verification for the gameplay batch. It does not claim human play acceptance or independent browser acceptance.

## Delivered in this batch

- Repaired the personalization smoke fixture order for repeated up/hold/down decisions without weakening the canonical tier guard.
- Generalized hybrid client contracts and mounted the versioned Living Archive (HY-05) alongside the preserved Courier's Promise (HY-01).
- Added the Shifting Market (HY-03): timed order study, color sorting then shape sorting, recorded parcel/bin choices, descriptive outcome, boundary assistance and deterministic replay.
- Added Tidekeeper (HY-02): fixed response-window n-back stream with separate position/symbol choices, event-timed responses, full stream coverage gate, and exposed current cues only.
- Added Harbor Dispatch (HY-04): timed manifest, server-streamed wave arrivals, marked-route and distractor decisions, wave-boundary strategy assistance, and dispatch outcome review.
- Added the Bridge Council (HY-06): proposal route, recorded council advice stimuli (supported, incorrect or uncertain), accept/reject/hold decision with evidence references, final route, key/closed-edge checks, and checkpoint assistance.
- Added independent Crystal Reasoning form `crystal-reasoning-v1`, with separate `crystal_attempts`, `crystal_events`, `crystal_outcomes`, append-only triggers, version provenance and linked event evidence. It is available as a separate form and is not a catalog HY activity.
- Fixed hybrid start retry identity, atomic assistance persistence, session learner ownership, and activity-specific assistance checkpoint enforcement. HY-05 completion is rejected unless committed or already a complete valid arrangement.
- Game reloads reconcile canonical attempt/action history. HY-03 encode replay after its deadline records a `hidden_information_replay` exposure before restarting the instruction window. Start, answer, action and assistance requests retain stable pending identities across retries.
- Follow-up review fixes prevent HY-06 completion from being overwritten by a catalog refresh, expose HY-05 cited evidence records, require one valid unique cargo choice per HY-03 cargo item, and allow Tidekeeper's accepted response to retry cue retrieval without reposting.

## Verification completed

- `scripts/personalization_smoke.py`: passed (explicit tier transition fixture).
- `scripts/luna_hybrid_batch1_smoke.py`: passed in a temporary SQLite database; includes HY-05 clue uniqueness, valid/conflicting placement, commit and assistance gates, replay conflicts, assisted exclusion, and EX isolation.
- `scripts/luna_hy03_hy06_smoke.py`: passed in a temporary SQLite database; verifies HY-03 switch boundary and correct routing, all three deterministic advice scenarios, decision evidence, checkpoint gates and completion outcomes.
- `scripts/luna_hy02_hy04_smoke.py`: passed in a temporary SQLite database; verifies hidden future stream, current-cue order, exact/conflicting retries, response timing, completion coverage and assistance boundaries.
- `scripts/luna_crystal_smoke.py`: passed in a temporary SQLite database; checks 250 generated forms for four distinct choices, no answer-key fields, start/answer exact replay and conflicts, outcome/evidence persistence and immutability.
- `python -m compileall -q backend/app/crystal_reasoning.py backend/app/hybrid_activities.py backend/app/hybrid_routes.py`: passed.
- Frontend `npm run build` from `frontend`: passed after these UI changes; Vite reports its existing large-chunk advisory.

## Review and integration boundary

The parent owns shared application route registration, lifecycle/export/deletion integration, companion muting, broad status documents and independent browser review. Crystal registration is `register_crystal_routes(app, store)` from `backend.app.crystal_reasoning`; the parent has wired it into `main.py`. `HybridPage` exposes optional `onActivityActiveChange(active)` to support muting during activities. No clinical or cognitive-score interpretation is produced. Automated build/smokes do not constitute manual play, accessibility review or independent browser acceptance.
