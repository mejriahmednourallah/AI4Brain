# Hybrid/companion/graph implementation ledger

30 October 2026. The human authorized execution of
`docs/HYBRID_COMPANION_GRAPH_PLAN.md`: “launch the implementation plan”.
The implementation goal is active. This ledger distinguishes assigned work from verified results.

## Current work: foundation recovery review and plan integration

Exactly two reused GPT-6 Luna medium workers are running:

| Owner | Three assigned tasks | Status |
|---|---|---|
| Luna A — `games_playability_audit` | Fast/Bella/Muted controller; local-first reply UI; safe practice checkpoints | Frontend plan journey independently accepted after navigation-race repair; companion frontend running |
| Luna B — `graph_exploration_audit` | Revision graph snapshots; asynchronous mirror; canonical plan/HY graph adapters | Backend foundation, plan-v3 corrections and companion backend independently accepted; graph backend running |
| Supervisor | Shared contracts and integration, source/check receipts, independent review before dependent batches | Independently ran foundation smoke successfully; reviewing plan launch and lifecycle contract |

Frontend worker owns `frontend/src/redesign/hybrid/**` and `redesign/crystal/**`.
Backend worker owns assigned hybrid/crystal backend/activity modules and their scoped checks.
Neither edits shared App routing, shared DTO clients, global persistence or plan/coach/graph modules
without integration agreement. Supervisor owns those boundaries. Application scoring, baseline
history, existing user data and approved artwork remain protected.

## Queue after independent batch review

2. Typed plan-v3 HY/Crystal scheduling, authoritative idempotent launch, canonical completion
   linkage, revised plan and compatible history.
3. Fast local voice default, Bella optional, early grounded response and bounded provider
   generation, checkpoint-based assisted practice speech and cancellation.
4. Obsidian-style force graph, local/global exploration, accessible evidence inspector/list,
   revision snapshots and optional asynchronous graph mirror.
5. Integrated browser/canonical/performance audit, fixes and replay.

No batch is complete until its concrete checks pass and supervisor review accepts the result.
Historical catalog presence and test counts do not substitute for gameplay or recovery evidence.
The investigation reports and accepted design remain preserved.

## Runtime and cost boundaries

- User's isolated fresh app: `http://127.0.0.1:5195`, API 8051.
- Worker browser QA: `http://127.0.0.1:5196`, API 8052; dedicated disposable SQLite history.
- Native/primary data and unrelated services are untouched.
- No further paid provider, hosted speech or speculative API benchmark calls are authorized
  for the worker batches. Use deterministic/local checks and existing installed dependencies.
- Workers notify the supervisor when the three-task batch is ready; routine waiting should
  not trigger repeated broad repository reads or heavy provider calls.

Evidence directory: `output/verification/implementation-20261030/`.
`starting-source.json` records the observed source hashes at launch.

## Review record

Backend foundation accepted after supervisor execution of `scripts/hybrid_foundation_smoke.py`
on disposable SQLite: all six assistance windows, owner/version guards, exact retries,
interrupted recovery, Crystal replay and EX isolation passed. Details and worker regression
results: `output/verification/implementation-20261030/batch1/backend/REPORT.md`.

Frontend gameplay evidence is recorded in the sibling `frontend/acceptance.md`. Supervisor
independently reran the reviewed Playwright fault script: rejected HY-03 action retries kept
identical body/event ID and one canonical event; accepted-but-lost Hybrid completion and
Crystal answer reconciled through GET, preserved review, and allowed distinct new attempts.
Separate receipts/screenshots are in `frontend/supervisor-repeat/`. This is bounded browser
QA, not all-branch, human or clinical acceptance. No primary data, live provider or paid
speech calls are used for these batches.

For Batch 2, frontend worker ownership expands to `PlanPage.tsx` and narrow App plan/routing
seams. Backend worker owns plan-v3 plus reviewed persistence/lifecycle hooks and the narrow
deterministic core-training launch adapter. Supervisor added additive plan availability,
plan-v3 generation/history registration and dashboard projection hooks; runtime integration
and independent acceptance remain pending. New launch records must be exported/deleted
with learner data and must never substitute hybrid evidence for core evidence.

Backend Batch 2 accepted after supervisor source review and independent successful runs of
`batch2/backend/plan_v3_smoke.py` and `scripts/plan_revision_smoke.py`. This covers deterministic
launch mapping, actual core block retries, optional-activity eligibility, constraints,
canonical outcome projection, export/deletion and revision stability. Browser plan flow
remains pending. QA API 8052 was restarted on the same isolated database with provider calls
disabled; user API 8051 and UI 5195 remain untouched. See `batch2/backend/REPORT.md`.

Additional supervisor source review reopened three bounded Batch 2 items: accepted alternate
request IDs were not durably bound as launch aliases; core training mappings were omitted
from the read-time completion projection; and hybrid completion projections dropped assistance
metadata. Backend worker must add targeted regressions and repairs before the next acceptance.
Earlier passing smoke receipts remain valid for their stated cases, not these uncovered paths.

The reopened items are now repaired and independently replayed in `plan_revision_smoke.py`:
immutable request aliases with export/deletion, canonical core decision/item completion,
and HY assistance/exclusion projection. Backend Batch 3 also independently passed
`coach_v2_smoke.py` and `coach_speech_cache_smoke.py`. Source review confirms local grounded
progress precedes optional explanation, bounded provider ownership, and consent-scoped
speech cache behavior. These use mocked providers/synthesis; actual voice/browser integration
and physical audible quality are not implied. See `batch3/backend/backend-batch3-review.md`.

Supervisor frontend plan review found an actual startup navigation race: Home's Plan action
bypassed the navigation generation guard, allowing delayed restore to return to Welcome.
Worker repaired deliberate-navigation callbacks and guarded restore/launch routing. Its
delayed-session cases pass for complete and incomplete profiles. Supervisor then independently
completed the planned HY-03 browser journey with lost launch reply: same canonical attempt,
four real route inputs, one completed outcome, completion references on the saved plan, and
unchanged baseline dimensions/snapshots/XP. Evidence: `batch2/frontend/supervisor-journey/`;
the earlier failure is retained as `startup-race-before-fix.json`. Imperfect route answers
are completion/recovery evidence, not a solved-mechanic or participant claim.

Frontend companion ownership is expanded to the speech controller, Companion, App companion
seams and minimal game checkpoint adapters for the three-task batch. Graph UI remains queued.

Graph backend's first independent snapshot/regression runs passed, but source review reopened
two requirements before acceptance: database identity must scope revision/cache/mirror keys,
and blocking Neo4j work must not hold the canonical coach/plan lifecycle lock. Worker is adding
equal-count/different-database isolation and slow-mirror/deletion-race regressions. Existing
graph smoke passes do not establish those uncovered properties. No graph runtime rollout yet.

31 October: both reopened graph issues were repaired. Supervisor independently reran
`scripts/graph_snapshot_smoke.py`: database-scoped isolation and the slow-mirror deletion
race passed along with graph filtering and canonical reference fixtures. Browser UI and
live Neo4j remain unverified. The graph worker is implementing the separate interactive
frontend while the companion worker continues; shared App ownership stays with companion.

31 October integration: App graph query and canonical-record callbacks are wired. Supervisor
independently replayed the repaired Planning neighborhood: 79 displayed nodes and 78 links
matched the QA API. Real scored Memory baseline was quiet; an HY-02 hint remained hidden
until its assistance event was accepted. Bella opt-in produced a local short playback;
human listening remains pending. Fast local synthesis returned `synthesis-failed` in both
the app and a separate blank Edge control, so the fast-audio target is not met on this
machine. Courier and Archive reload/completion spot checks passed, but were not controlled
lost-acknowledgement tests. See `batch3/frontend/APP_GRAPH_INTEGRATION.md` and
`batch4/graph/frontend-evidence.md` for receipts and limits.

Final focused checks: frontend production build, `battery_smoke.py`, and
`plan_revision_smoke.py` passed; the frontend build retains a large-chunk advisory. The
primary SQLite hash still equals its starting hash. The isolated interactive API 8051 was
restarted from its recorded configuration on the same database; UI 5195 remained running,
and health, graph, plan and speech endpoints returned 200. No provider call was made.
The complete objective remains open while Fast voice failure, performance checks and
the remaining comprehensive browser/fault-injection and human acceptance gates remain.

Local coach timing: 20/20 local-only SSE responses succeeded; first local-response receipt
median 220.589 ms, nearest-rank p95 649.706 ms, maximum 1493.430 ms. A second sample did
not show an improvement (p95 817.786 ms), and the unproven optimization was reverted.
These client-side timings include transport/buffering and miss the proposed 500 ms p95.
Fast-voice read-only diagnosis found audio services running and endpoints reporting healthy;
headed Edge still produced `synthesis-failed` on both the app and an independent blank page.
No OS changes were made. See `batch3/frontend/FAST_LOCAL_DIAGNOSIS.md` and the raw timing
receipts in `batch3/backend/`.

Continuation: user reaffirmed the approved generated images and their feedback as the visual
source of truth. The later Evidence reference is `output/visual-design-review-2026-10-19/11-evidence.png`;
the current interactive graph differs in scenery, medallions and composition. A compact
inspector revision reduced an observed full-page capture from 17,735 to 1,852 pixels while
keeping record fields, evidence and relationships available through keyboard-operable
disclosures. Production build and local-neighborhood browser replay passed; independent
keyboard/mobile disclosure review is recorded by the graph worker. This does not establish
visual fidelity or human acceptance. Courier reference `22-future-courier.png` differs
substantially from the current grid/control composition and is under a separate image-led pass.

Controlled QA fault injection now additionally covers HY-01 and HY-05 accepted-but-lost
action replies, same-tab restoration, and 503 retries with matching event IDs/bodies and one
canonical event each. HY-05's final automation click timed out after the successful response
removed the retry control; the raw network/GET evidence and limitation are retained at
`batch2/frontend/hy01-hy05-recovery-exact-state/recovery-report.md`.

On this Windows machine, an independent built-in System.Speech probe synthesized a short
synthetic sentence to a 95,046-byte in-memory WAV, despite Edge Web Speech reporting
`synthesis-failed` for an installed local voice. A consent-scoped local SAPI fallback is
under implementation; no reliability or latency result is claimed yet.

Continuation progress: HY-01 and HY-05 controlled accepted-lost action replies and exact
503 retries were captured on disposable QA data; HY-05's automated click timed out after
its successful retry removed the control, so the network and canonical receipts, not a
clean click assertion, support that result. Courier received image-led scenery/dock and
approved stone/pawn assets; its rectangular grid and unsupported Undo/Restart/Pause still
do not match reference 22. Archive's actual tier-3 review was captured against reference 26
and rebuilt with real saved clues/placements/conflict in a three-column scenic composition.
Its same-attempt desktop/mobile/reload screenshots exist and a no-output TypeScript check
passed, but keyboard gameplay and a new production build remain open.

An opted-in Windows SAPI fallback now produces local WAV in memory with explicit non-XML
speech, no remote service, lifecycle checks, and a private bounded cache. Direct QA HTTP
samples were 20/20 valid WAVs (warm median 58.9 ms, warm p95 68.1 ms; cold 2351 ms), but
the controlled browser fallback exposed a 409 caused by incompatible revision scopes. A
revision compatibility repair and full regression are in progress; browser playback and
the user's running API have not yet been verified with that repair. C: reached zero free
bytes; only this task's reproducible `frontend/dist` was removed (about 46 MB). Space is
still critically low, and the user was asked to free at least 2 GB before normal builds
and browser QA resume. Do not treat screenshots, latency or partial tests as completion.

After the user explicitly requested forced Docker cleanup, all 23 running containers were
stopped, all 35 remaining images were force-deleted, and Docker build-cache pruning ran.
Engine verification showed zero running containers, zero images, 37 stopped container records
and 24 preserved named volumes. Docker Desktop was stopped; Windows free space recovered to
about 13.8 GB. Other projects must pull/rebuild their images before their containers can run.

Archive review now has a real tier-3 before/after comparison against image26; keyboard
selection, six placements, commit, one canonical completion and review recovery were
exercised. Its original scene and unsupported pictured controls remain visual/product gaps.
Tidekeeper's reference23 depicts a between-round interaction absent from its v1 timed
mechanics; image-led scenery/board work is in progress without fabricating those controls.

Windows Fast voice now has an opt-in local SAPI fallback that synthesizes in memory, treats
text as literal rather than speech XML, and checks consent, lifecycle and evidence revision.
A real Edge QA autoplay run showed natural Web Speech failure followed by SAPI playback of
a short server-authored canonical summary; route navigation stopped playback. Focused coach,
speech-excerpt and lifecycle tests passed. Human audibility, 20-sample browser latency, and
the 500 ms first-meaningful-reply p95 budget remain open; current user's 8051 API is not yet
restarted with these newer backend changes. QA API 8052 is isolated and providers disabled.

The user explicitly authorized force-stopping Docker containers and deleting images/build
cache. All 23 running containers were stopped, all Docker images were force-deleted, and
build-cache prune completed; 37 stopped container records and 24 named volumes were
preserved. Docker Desktop was then stopped; C: recovered approximately 13.8 GB. Existing
container images must be rebuilt or pulled before those containers can run again.

The SAPI revision-scope fix passed independent coach and SAPI smoke checks, including
multi-session evidence and deletion/mute races; a real fallback browser test still remains.
Archive no-output TypeScript passed; full build, keyboard and image comparison remain active.

Latest continuation supersedes older pending-status entries above: Archive's keyboard
completion and review recovery were exercised on isolated data, and the production build
passed. A Tidekeeper 12-cue browser run recorded 12 successful action responses, unique
event IDs and a completed outcome; earlier separate 422 observations remain unexplained.
Independent comparison with reference 23 shows substantial remaining differences in the
header, brass-and-blue board, review panel and dock. The reference's between-round controls
do not all have corresponding v1 mechanics; visual resemblance cannot establish gameplay
or scoring semantics. Graph reference comparison and the user's isolated API refresh are
still in progress. Docker Desktop is stopped and C: had approximately 12.8 GiB free when
checked again; named volumes were retained.

The isolated user API on 8051 was subsequently restarted from its owned receipt and private
configuration without printing credentials or making provider calls. Its isolated profile
retained one session and three events; health, graph, plan and speech routes returned 200.
The UI process stayed running. Receipt: `output/verification/responsiveness-20261030/api8051-restart-receipt.json`.
This makes the newer local voice backend available; it is not evidence of human-audible
quality or proof that the latency targets have been met.

Graph comparison with approved image 11 remains open: the revised canvas shows the scenic
background and a real selected-record medallion, but the reference's large brass category
medallions, relationship labels and full-height composition are not yet matched. Desktop
and mobile captures report 79 real visible nodes, 78 local edges, 79 keyboard-list entries,
no horizontal overflow and no page errors. Those measurements do not prove performance at
the 1,000- and 5,000-node acceptance sizes. Tidekeeper's previous 422 response bodies were
not retained by the capture harness or access logs, so their cause remains unknown.

Harbor Dispatch lost-reply testing accepted one action, retried its exact saved payload,
and canonical GET showed one event. A reload displayed a saved-attempt resume gate; the
initial automation timeout was caused by expecting the live arrival before activating that
gate. A second empty attempt appeared during re-entry and its origin is under investigation.
Completion and Bridge Council's controlled recovery remain pending. Comparison with image
25 also confirms that Dispatch's current flat lane panel differs substantially from the
approved harbor scene, rule card and dock.

Graph review found that the layout worker caps input at 5,000 nodes and 30,000 links.
Accessible disclosure and truthful loaded-versus-rendered counts are being implemented;
the graph benchmark and large-graph interaction checks have not yet established acceptance.

The original Harbor Dispatch attempt resumed via the gate and completed. Source review
confirmed a stale-effect fallthrough in the shared supplemental-game attempt hook: after a
saved-attempt fetch resolves following cleanup, it can initiate a new attempt. This is
consistent with the observed extra empty attempt, although that individual unmount was not
instrumented. A cancellation fix and delayed-fetch/unmount regression are in progress.

The same saved-fetch fallthrough was independently found in Crystal Reasoning; both fixes
and delayed-fetch regressions remain pending. Archive restore was also identified for a
separate stale-lifecycle review; accepted writes and pending retry payloads must be retained.
Bridge Council's accepted-lost action, retry and reload reached its advice view, while its
decision/completion remains unverified. The graph cap UI's first 5,001-node selection check
failed and is under investigation; a successful build is not evidence of that interaction.

Harbor Dispatch received a scenic stage, rule/arrival cards and a real action dock; a
browser run recorded eight actions and one completion, including keyboard activation. The
supervisor compared the desktop/mobile screenshots with approved image 25: the large empty
transparent arches and open-sea setting remain substantially different from its populated,
perspective stone harbor channels. Visual fidelity remains open. A separate unexpected
synthetic start during this run is consistent with the already-confirmed stale-fetch
fallthrough; the fix and regression remain pending. No primary data was used.

The supplemental hybrid and Crystal restore effects now return after a delayed saved-fetch
if the component has unmounted. The production build passed, and a browser regression
delayed the real restore responses, navigated away, and intercepted zero new start requests
for both activities; the isolated receipt is `batch4/frontend/hy04-hy06-recovery/delayed_restore_unmount_guard.json`.
This closes the tested fallthrough, not the separate Archive lifecycle review or the full
recovery matrix. The latest graph cap rerun was invalidated by frontend HMR and remains open.

The subsequent isolated synthetic graph cap rerun passed all six focused assertions: API
pagination disclosure, loaded counts, 5,001st record selection and inclusion in the map,
list reachability, the 30,000-link positioning disclosure with 30,001 links passed to the
canvas, and no page errors. Receipt: `batch4/graph/visual-fidelity/graph-truncation-smoke.json`.
This does not establish 1,000/5,000-node full-app latency or frame rate, or visual fidelity.

An isolated headless Edge microbenchmark measured the actual layout worker at 404.1 ms
for a synthetic 1,000-node chain and 1,142.3 ms for 5,000 nodes; a 5,000-node/30,000-edge
case took 1,171.2 ms. Its separate canvas loops are synthetic and do not measure the full
React graph, browser frame cadence or app-ready time. Raw results: `batch4/graph/visual-fidelity/graph-performance-probe.json`.
Dispatch's second asset pass still showed floating stonework and translucent lanes, not
the approved harbor; an image-based scenery option is being assessed.

Two crops of approved image 25 were inspected in `batch4/frontend/reference-crop-assessment/`.
Although they exclude the preview's controls, both retain sample boats, destination flags and
symbol-labeled cargo. They were not integrated because these may be read as live game state;
the approved harbor composition remains an open visual task. HY-06 completion and the
separate Archive stale-lifecycle investigation remain outstanding.

An integrated synthetic `EvidenceGraphCanvas` probe reports first layout readiness near
985 ms for 1,000 nodes and 2.64 s for 5,000 nodes, with much longer headless animation
frame intervals during pan/zoom. A same-environment idle canvas control had a 16.7 ms
median frame interval. The graph-specific cost or instrumentation effect is not yet
isolated; actual draw profiling and any repair are pending. Raw integrated receipt:
`batch4/graph/visual-fidelity/graph-integrated-browser-probe.json`. Do not treat these
synthetic headless samples as physical-display FPS or established acceptance.

Bridge Council's controlled lost-reply/reload journey continued on the same isolated
attempt through evidence inspection, a hold decision, a feasible resolution route and
one completed canonical outcome. No new start request occurred in the continuation;
the receipt is `batch4/frontend/hy04-hy06-recovery/hy06-completion.json`. This covers
that route and recovery path, not every advice or assistance branch.

Graph profiling identified expensive individual edge strokes and per-node shadows. The
canvas now batches edge paths by visual state, uses adjacency for highlighting and keeps
the selected-node shadow while dropping ordinary-node shadows. An isolated actual-canvas
synthetic measurement reported 5,000-node/30,000-link median draw time of 383.5 ms before
and 8.7 ms after; the earlier raw profile file was overwritten, so the before figure is
retained only in the worker's reported output, not as a reconstructable raw receipt. The
current after receipt is `batch4/graph/visual-fidelity/graph-canvas-profile.json`. Integrated
frame cadence and visual/interaction regression remain pending.

A separate instrumented synthetic browser probe confirmed that selecting a global graph
record previously restarted the 5,000-node layout worker. After narrowing the dependency,
the same selection caused no new worker post, while local neighborhood entry/recentering
still ran. Before/after receipts are `graph-selection-worker-probe-before.json` and
`graph-selection-worker-probe-after.json` in `batch4/graph/visual-fidelity/`. This proves
that bounded behavior, not that integrated frame-time targets are met.

Subsequent graph verification passed production build, synthetic pointer selection and
highlighting, the 5,001-record keyboard case, and the edge-cap disclosure. Actual canvas
draw p95 measured 2.9 ms (1k/999), 9.1 ms (5k/4,999), and 14.6 ms (5k/30k). The integrated
headless app still exhibited long main-thread tasks; its final frame sample was too sparse
to establish FPS or acceptance. See `batch4/graph/frontend-evidence.md` for limitations.

Archive's restore continuation now has lifecycle guards in source, but its first browser
regression was inconclusive: the test's synthetic assistance referred to `test-source`,
which the API rejected with 422 before persistence. A controlled replay with a valid source
and an interceptor installed before navigation remains pending. A new-session local-only
coach timing sample measured 193.98 ms p95 for 20 requests on the existing QA API, but the
fixture has no prior history and does not establish representative browser latency; previous
larger timings remain valid for their own conditions. A source-only optimization is under
review and has not been served to the user's API.

Archive's controlled delayed-GET/unmount test now confirms no follow-up assistance/start
POST after leaving, unchanged pending JSON, and exact same-ID/body retries after injected
503 responses. Those retries were intercepted, so actual successful canonical acceptance
is still being tested. The earlier fake-source 422 was a test fixture error, not a save.
Receipt: `batch4/frontend/hy04-hy06-recovery/archive_restore_unmount_guard.json`.

The source-only coach snapshot reuse passed coach and lifecycle race smokes. In three
counterbalanced pairs on identical disposable 1,201-event databases, direct `_build_answer`
median was 64.64 ms before versus 37.35 ms after (30 samples each). This is a synthetic
function benchmark, not browser/SSE latency or proof of the 500 ms gate. Receipt:
`batch3/backend/coach-populated-old-new-benchmark.json`. The running API has not been
restarted with the change.

Archive's separate real UI assistance event was accepted once; an exact API replay returned
`replayed:true`, and same-attempt UI re-entry showed the saved clue without a new assistance
or start POST. Canonical GET still returned one matching assistance record. This is distinct
from the earlier 503-intercepted pending payload; the original live test's selector timeout
remains recorded and is not counted as a successful UI retry. Evidence:
`batch4/frontend/hy04-hy06-recovery/archive_assistance_reentry_reconcile.json`.

QA API 8052 was restarted against its existing isolated database with providers disabled;
health returned 200. Its first guarded stop returned nonzero after the verified process
tree exited; the stderr was not retained. After confirming no remaining listener or owned
process, the service was safely relaunched from the receipt. A 20-request local-only SSE
sample on the populated synthetic profile (704 events, 82 sessions before the run) measured
median 111.802 ms and p95 125.943 ms to full `local_response`, 20/20 successful. Receipt:
`batch3/backend/coach-populated-sse-latency.json`. This is an HTTP client measurement for
one synthetic profile, not browser playback timing or a general latency guarantee. The
user's 8051 service has not yet been restarted with the latest coach source.

The receipt-owned interactive API 8051 was subsequently restarted with current coach source
after verifying its launcher, child and listener. Health, graph, plan and speech checks
returned 200; the same isolated interactive database retained one session and three events,
and Vite 5195 remained running. No provider calls were made during the refresh.

Shifting Market now uses the approved Gallery backdrop, configured sorting trays and
data-derived color/shape markers. An isolated plan-launched browser run recorded four
actions and one canonical completion, with 4/4 order and 4/4 routing; build passed.
Desktop/mobile captures are in `batch5/frontend/`. Supervisor comparison confirms the
scene is closer but the full-screen shell, relative proportions, companion panel and dock
still differ from reference 24. Configured game semantics take precedence over sample
controls in the image. Browser companion timing remains in progress.

The subsequent checkpointed Edge browser companion run recorded 20/20 local-only replies
and 20/20 SAPI HTML-audio `playing` events, with route-change cancellation and unchanged
assessment/training trial counts. Warm UI local-reply median was 726.3 ms and p95 1,364 ms;
observed speech-start median was 1,295.75 ms. Those are browser samples on one synthetic
fixture, and the UI timing misses the plan's 500 ms p95 target. Failed/interrupted harness
attempts remain preserved. Receipt: `batch3/backend/companion-20-sample-browser.json`.
The critical path and an earlier safe local response/speech start are being investigated.

Follow-up trace corrected the earlier interpretation of the speech timing: the client
enters the SAPI request shortly after the local-response handler; the harness previously
labelled response-header receipt as request start. One sample initiated SAPI at 609 ms,
received headers at 1,497 ms and observed audio playing at 1,910 ms. This is one sample,
not a complete latency distribution. Safe cache reuse across revisions is being evaluated
with revision, consent, lifecycle, deletion and content checks retained.

Fast-local cache source now keys audio by learner, session, lifecycle generation, subject,
cleaned-text hash, voice and engine/cache versions, revalidating consent and evidence before
reuse. Focused isolated tests cover same-content valid revisions, stale evidence, changed
text, mute/deletion races and separation from Bella cache eviction. Real endpoint/browser
hit and playback timing after the change remain pending; no speedup is claimed from tests.

Local SAPI profiling measured one 717.92 ms cold synthesis versus 17.18/15.94 ms warm
for the same short synthetic text. A consent-scoped background prewarm route and bounded
speech-slot wait are in source; focused tests cover immediate speech during warmup,
muting and disconnect before synthesis. Frontend opt-in wiring and real browser cold/warm
comparison remain pending. During Bridge Council review, the first new screenshot showed
the map clipping the route-planning panel; that visual defect is being corrected.

The route-panel overlap was corrected and the isolated Bridge Council continuation completed
with one outcome; some edge-cost badges still overlap nodes and are being repaired. The
post-prewarm real-browser speech check produced 3/3 playback starts and route cancellation,
but first playback was 4,180 ms after Send. Two later content-cache hits received headers
after 1,104 and 900 ms and played at 1,151 and 1,196 ms; three samples do not support a
stable percentile or close the audio target. Receipt: `batch3/backend/companion-sapi-prewarm-final.json`.
The reason cache hits remain slow is under investigation.

Bridge Council's responsive edge labels now avoid platform and label overlaps in the tested
desktop/390 px cases; its keyboard-opened table matched all eight canonical edges, costs and
states. The full proposal/advice/resolution journey produced one completion. The reference
27 floating-island composition remains visually unmatched. Receipt:
`batch6/frontend/hy06-edge-label-acceptance.json`.

Test-only profiling on a disposable populated database found 100–297 ms of speech wait
on the coach lifecycle lock in controlled concurrent runs, explaining part but not all of
the slow browser cache-hit observation. Coach finalization now fetches consent from the
current session instead of the full learner history; a focused regression verifies separate
session consent isolation, and lifecycle/deletion and speech-cache race smokes passed.
The change has not yet been measured in the live browser; see
`batch3/backend/profile-fast-local-live-lock.json` for the instrumented results.

After the session-consent optimization, a separate 20-turn Edge QA browser run observed
20/20 local replies and playback starts with route cancellation, but UI reply median/p95
were 1,094/1,603 ms and speech-start median was 1,530 ms. The prior nonrandom browser run
had lower UI median/p95 (726/1,324 ms); these different samples do not establish causality
and the speed gate remains open. Receipt: `batch3/backend/companion-sapi-consent-optimization-20-retry.json`.
Tidekeeper review source inspection also found that responses were labelled “miss” even
for false alarms; a truthful expected-versus-recorded channel review is being implemented.

Tidekeeper's read-only review of an existing completed attempt now shows expected and
recorded decisions per channel, with correct rejection, missed match and false-alarm labels;
it explains that No match may be a window-end default. Twelve rows matched the canonical
outcome at desktop and mobile, with no POSTs or changed records. That outcome contained no
false alarms, so a distinct synthetic false-alarm case remains to be verified. The reference
cue-board history cannot be reconstructed from stored public outcome fields.

The earlier Tidekeeper 422 concern was reproduced in a fresh synthetic browser session:
duplicate stimulus GETs reset the cue onset after both input clicks, producing
`elapsed_ms:-2723` and an API rejection. Raw trace: `batch5/frontend/tidekeeper-review/hy02-negative-elapsed-fresh-trace.json`.
A cue-identity/onset fix and real timed regression are in progress; do not treat the prior
successful 12-cue run as proof that this race cannot happen.

A bounded companion browser comparison measured five dev samples (UI reply median/p95
1,165/1,635 ms) and five production-preview samples (989/1,063 ms), all local replies and
playback starts successful. The small sequential nonrandom runs had different backend
warmth; they do not prove a production-build speedup or close the latency gate.

The new disposable `scripts/plan_v3_activity_matrix_smoke.py` exercised the incomplete
baseline gate, empty availability and bounded budget, then individually selected and
launched HY-01 through HY-06 and Crystal via plan-v3. It checked launch replay, canonical
actions/outcomes and plan completion projection for each; this is synthetic backend/API
evidence, not a browser journey for every activity. Independent rerun remains pending.

Supervisor independently reran the seven-activity matrix on the bundled project Python;
it exited 0 and reported seven plan launches/completion projections, 79 synthetic baseline
trials and zero training trials. This supersedes the prior pending-rerun note.

Tidekeeper's onset and failed-stimulus retry paths are now fixed. The isolated browser
replay recorded 12 unique canonical actions with elapsed values in 0–2,100 ms, real false
alarms and an accepted-lost action exact retry; a separate 503→retry path saved a response
at 398 ms with the unchanged 2,100 ms window. The pre-fix 422 evidence is retained in
`batch5/frontend/tidekeeper-review/REPORT.md`. Reference 23's visual match remains open.

An isolated HY-02 assisted-practice browser test forced the first help save to 503: the
hint remained hidden, the retry used the same body and event ID, the accepted 201 produced
one canonical assistance record and then revealed the hint. The ready checkpoint played,
but assistance-specific speech did not. A narrow cooldown bypass alone did not resolve it;
the checkpoint delivery/speech path remains under investigation. Receipt:
`batch7/frontend/assisted-practice-speech-acceptance.json`.

The missing assistance checkpoint was traced to fresh HY-02/HY-04 attempts having no
events from which to infer a session ID. Both now use the explicit session prop; an
assistance checkpoint may also bypass the general proactive cooldown, while per-ID dedupe
and quiet-window checks remain. A fresh HY-02 browser run verified forced 503, hidden hint,
identical retry, one accepted assistance record, then the assistance-specific SAPI audio
`playing` event. This is one assisted checkpoint path; broader speech timing remains open.

HY-04 was also verified in an isolated fresh attempt: no new speech or active audio during
the timed manifest, one saved assistance event with the correct session, assistance-specific
audio playback, and no duplicate on rerender. Receipt:
`batch7/frontend/hy04-assisted-practice-speech-acceptance-corrected.json`.
The current frontend build passed with the existing large-chunk advisory.

Read-only HY-02 investigation found that its actual cue stream is persisted privately in
the attempt configuration. A completed-only review API and user-requested, separately
logged replay are being implemented against that stored stream, with no active-attempt
disclosure or changes to the immutable original outcome; historical compatibility remains
to be tested. The earlier statement that cue images cannot be reconstructed applied to the
public outcome alone, not to the server's persisted private config.
