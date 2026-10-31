# Current goal and sprint review

## Full Docker Compose package — 22 October 2026

The user's full-stack packaging request is implemented in `compose.yaml`: built React/Nginx,
FastAPI with local CPU KittenTTS, canonical SQLite on a persistent volume, and Neo4j on its
own persistent volume. `scripts/compose-up.ps1` starts the stack; `docs/DOCKER.md` covers
ports, cache warm-up, explicit SQLite import and consistent backup. Credentials and learner
history are excluded from images and the portable source ZIP.

Actual Linux image builds and isolated `ai4brain-compose-qa` runtime checks passed: browser
render, built assets, API/docs proxy, save/exact retry, local coach/SSE, connected SQLite-derived
Neo4j mirror, real speech synthesis, restart/replacement persistence, and backup/import.
The archive's file hashes and extracted Compose configuration validate. See
`output/verification/docker-compose-2026-10-22/REPORT.md` for scope and limitations. The
primary native database and legacy graph volumes were not imported or modified.

## Generalisation benchmark — first frozen run, 22 October 2026

The workstream that the last rejudgment described as "specification only" now has an executable
benchmark, and its first reserved run has been recorded.

- `tests/generalisation/manifest.json`: **72 named cases** — 30 task variations, 12 learner
  situations, 30 constraints — split **48 development / 24 reserved**, each with an expectation
  written as a specification rule.
- `scripts/generalisation_eval.py`: runs the candidate over its real HTTP surface on a disposable
  database, evaluates each expectation with its own rule implementation, and scores two simple
  comparators (`naive_order`, `fixed_tier1`).
- **Development: 48/48 pass. Reserved (first frozen run): 24/24 pass.** Both comparators score
  0/5 (development) and 0/3 (reserved) on the decision-shaped cases, so the suite is not trivial.
- `tests/generalisation/FREEZE.json` pins the source and manifest hashes; a reserved run is refused
  after any source change, and the reserved pool has now been observed once.

Limits: the evaluator and the candidate share authors, so this is not an independent oracle;
comparators are deliberately simple; no participant, transfer or growth claim follows.

## Rejudge fixes — PV-01 to PV-04, 22 October 2026

The latest independent rejudgment reproduced four remaining problems. All four are now fixed and
covered by `scripts/r7_rejudge_fixes_smoke.py` (12/12) plus a full regression run.

- **PV-01 (RJ-03 reopened):** generated prose could restate a measured fact and still be labelled
  validated. Provider prose may now not restate any measurement at all — digits, spelled-out
  numbers and noun-plus-value constructions are all rejected, so the backend keeps its own facts.
- **PV-02:** an explicit empty availability list meant "every family". Omitted availability is now
  distinct from a real constraint, unknown identifiers are rejected with 422, an empty or
  unsatisfiable constraint returns `no_available_activity`, and the plan API accepts and applies
  the constraint instead of rejecting the field.
- **PV-03:** the recommendation and the saved plan could name different next activities. One
  resolver outcome now leads the plan (`resolved_next_step`), and when the budget cannot fund it
  the plan says `resolved_family_over_budget` and offers the budget change required.
- **PV-04:** `personalization_smoke.py` was launching against a genuinely stale plan. The fixture
  now asserts the stale-plan 409 and reconciles first, so the tier guard is unchanged and the
  suite is clean again.

Regression after the fixes: thirteen suites plus the 40-case manifest (40/40) and the recovery
matrix (68/68) all exit 0. Not claimed: the G0–G5 generalisation benchmark, live provider or
participant evidence, and independent judgment of generated-prose helpfulness.

## R1–R5 execution result — 22 October 2026

The appended correction plan has been executed repair-first, and every claim below is backed by
a receipt produced in this session on the current tree. No hosted provider was called, no
Docker workload was started, and every database used was a disposable fixture under
`output/verification`.

| Batch | Outcome | Receipt |
|---|---|---|
| R1 (RJ-01, RJ-02) | Reservation before generation, leaner lifecycle generation/deleting guard, late-reply invalidation, complete export and scoped deletion | `scripts/r1_rj01_rj02_smoke.py` PASS |
| R2 (RJ-03, RJ-04, RJ-06) | Field-bound facts, rejection of unsupported certainty and clinical assertions, distinct provider-timeout status, role-aware history, single authoritative tier | `scripts/r2_rj03_rj04_rj06_smoke.py` PASS |
| R3 (RJ-05, RJ-07) | Action recording and routing verified in a real browser; local KittenTTS Conversation playback, pause/resume/stop, disable and unmount cleanup, silence during a timed cue; Tidekeeper pads measured at six viewports | `output/verification/r3-r5-browser/{actions-and-claims,speech-verification,speech-quiet,tidekeeper-hit-targets}.json` |
| R4 (RJ-08 + 40 cases) | Verdicts derived from the saved record, safe adjudicating context, and a named 40-case suite | `output/verification/r4-forty-cases.json` (40/40) |
| R5 (recovery matrix) | Rejected save, lost reply, conflicting payload, failed GET, reload restore and interrupted completion for all five families and six hybrids | `output/verification/r5-recovery-matrix.json` (68/68) |
| R6 (reproduction and rehearsal) | Every reproduced finding re-run against the current tree; the documented start/stop lifecycle rehearsed; materials refreshed | `output/verification/r6-reproduction/REPORT.md`, `output/verification/r6-rehearsal/final-journey.json` |

Defects found by that evaluation and fixed in the same pass:

- `hybrid.css`: at 1280×720 the four Tidekeeper pads began below the fold, at 1024×768 their
  lower edge was clipped, the mobile viewports overflowed horizontally by 60px, and the
  landscape phone hid the pads entirely. Fixed by a short-viewport chrome compaction, a
  `minmax(0,1fr)` play-surface column, and a landscape board/pads split. No cue timing changed.
- `coach_v2.py`: provider prose could assert certainty or a clinical diagnosis. Both are now
  rejected, with the certainty rule bound to the recorded uncertainty status.
- `coach_v2.py`: a provider timeout was reported as generic unavailability; it now reports
  `status=timeout` with `fallback_reason=provider_timeout`.
- `storage.py`: an abandoned in-progress reservation could block its own retry forever; a stale
  reservation is now reclaimable by the exact retry.
- `speech_service.py`: whitespace-only speech text reached the synthesiser and raised an internal
  error; it is now a validation error.
- `coach_routes.py`: a superseded reservation reported "learner data was deleted"; the message now
  distinguishes deletion from a changed reservation.
- `scripts/start.ps1` and `scripts/stop.ps1`: both crashed with a type-conversion error whenever
  `output/runtime/processes.json` existed, because `ConvertFrom-Json` returned the stored array as
  one pipeline item. Both now flatten the file and ignore non-scalar ids. Rehearsed end to end:
  start reported health and web readiness in 19.9 s, a read-only journey across twelve page views
  rendered every heading with no horizontal overflow and no console error, and stop removed both
  processes and the pid file.

Still open, and deliberately not claimed as done:

- Browser fault injection has been re-run for the hybrid action path; the canonical save path's
  browser fault-injection receipts are from earlier phases and the R5 matrix re-covers it at the
  HTTP layer for every game.
- A clean-machine rehearsal with cold package caches (the rehearsal above reused this machine's
  environment) and a new independent review of the frozen tree by a worker that did not write the
  code; the authorised subagent quota is exhausted, so `r6-reproduction/REPORT.md` is a supervisor
  rerun rather than an independent acceptance.
- Human KittenTTS audition, human visual acceptance, expert accessibility/security/licence
  review, reference-fidelity registers, and any participant or clinical evidence.
- Live Groq/Gemini behaviour: no authorised configuration was used, so every provider result is
  deterministic-transport evidence only.
- A real 3–5 minute demo recording, a rebuilt and re-inspected pitch deck (the pitch builder cannot
  resolve its artifact-tool module in this environment, so `AI4BRAIN-Pitch.pptx` still dates from
  19 October), verified submission destination and external release.

## Active planning focus: generalisation — 22 October 2026

The human selected three tracks: unseen learner situations, unseen task variations and
unexpected constraints, with no participants available. The G0–G5 proposal appended to
`CONNECTED_AGENT_PLAN.md` covers a shared decision contract, reserved software evaluation,
independent oracles/comparators and a future participant protocol. This is planned scope,
not a successful benchmark or a new score. Current focus defers TTS/provider testing;
existing repair and acceptance backlog remains intact.

## Current correction plan — 22 October 2026

The latest independent rejudgment reopened eight implementation findings. The appended
R0–R6 correction/completion plan in `CONNECTED_AGENT_PLAN.md` is the next execution sequence;
`CONNECTED_AGENT_LEDGER.md` records the reopened gates. This amendment is planning only.
Older statements below that all turn retries, generated facts, lifecycle coverage or timed
controls are accepted are superseded where contradicted by the new audit receipts.

Order: checkpoint/reproduce → privacy/request identity → truthful coach/history/plan tiers →
companion actions/KittenTTS/Tidekeeper → collaboration/40 cases → remaining visual/game/recovery
acceptance → reproducibility/materials/review. Use the existing two Luna medium lanes with
supervisor integration; no new games need rebuilding. The 90–95% development target remains
uncertified, and the 69/100 application judgment is not a completion percentage.

## UX/UI polish pass — 22 October 2026

A screenshot-led review of Home, Insights, Plan, Collaboration, Evidence graph, Hybrid lab,
Practice entry and Data & privacy at 1440×1000 and 390×844 found thirteen rendering or copy
defects and fixed all of them: a single-snapshot chart that read as a stray glyph, a raw
`PRELIMINARY_HIGH_UNCERTAINTY` value, edge labels clipped by graph nodes, truncated plan focus
labels, two pluralisation bugs, a mislabelled "strategy" that was actually policy rationale, a
stale saved suggestion presented as current, a collapsed collaboration workspace, the mobile
bottom navigation covering Home's last card, a wrapped desktop navigation label, and a saved
session that produced an unending "session not found" retry. Evidence, captures and exact scope
are in `output/verification/ui-polish-2026-10-22/REPORT.md`; final captures show zero console
errors and zero horizontal overflow. This is software/layout verification, not human visual or
audible acceptance.

## Connected-agent upgrade — 22 October 2026

The five implementation findings in the independent judge report
(`output/verification/challenge-judge-2026-10-21/REPORT.md`, preserved unchanged) now have
scoped repairs with automated evidence. Plan and ledger: `docs/CONNECTED_AGENT_PLAN.md` and
`docs/CONNECTED_AGENT_LEDGER.md`.

- **Coaching answered the wrong subject.** Reproduced first with the judge's exact prompt, then
  repaired: a SQLite-derived Twin context now separates observed evidence, learner reports and
  suggestions, and subject resolution prefers an explicitly named family, then the current
  activity, then the conversation subject, then the next recommendation. The Memory question now
  answers from the saved Memory baseline and reports the next step separately
  (`scripts/coach_context_smoke.py`).
- **Replies were restricted to prewritten strings.** `coach-v2` generates free-form explanations
  through one provider interface with Groq and Gemini adapters, then validates every identifier,
  strategy, action, tier and number against backend-supplied values before display; the factual
  observation, evidence list and caveat stay backend-rendered. Turns persist with a request id
  and payload hash, exact retries reconcile, conflicts return 409, and an SSE endpoint streams
  acknowledgement, evidence and only the validated answer. All verified with deterministic
  in-process transports; **no live provider call was made and no credentials exist here**
  (`scripts/coach_v2_smoke.py`).
- **Plans could stay stale.** `plan-v2` reconciles the active plan after a baseline family
  completes, a canonical training decision and a goal change, with one revision per meaningful
  trigger, deliberate ranking instead of fixed later-family order, activity-specific duration
  estimates and explicit budget accounting (`scripts/plan_revision_smoke.py`). A dashboard-mode
  change deliberately does not touch the plan.
- **Collaboration rewarded structure.** `collaboration-v2` keeps the accepted weights but earns
  credit only from checkable references: a verdict is compared with canonical ground truth held
  server-side, unreferenced text earns nothing, following advice is not scored as autonomy, and
  unassessable dimensions stay unassessed. `collaboration-v1` records remain readable
  (`scripts/collaboration_v2_smoke.py`).
- **Connected surfaces are now exercised together.** The Collaboration page preserves its v1
  action history while adding the v2 server-held verification claim and structured verdict path.
  An isolated browser journey opened the companion during Memory practice, rendered separate
  evidence/explanation/strategy/next-step blocks, restored the saved conversation after reload,
  and recorded zero page errors or non-abort request failures
  (`output/verification/companion-browser-qa/REPORT.md`). Hosted providers remained explicitly
  unconfigured. The tier-ceiling fixture now establishes canonical prerequisite decisions before
  requesting tier 3, and `scripts/backend_smoke.py` passes without weakening the guard.
- **Timed controls below the fold / ambiguous counts.** Decisions now report assisted and
  interrupted trial counts with an explicit label note; Tidekeeper has compact short-viewport
  rules. The count change is API-verified; **the Tidekeeper viewport change has not yet been
  measured in a browser**, and the ledger marks it open.

Frontend: the learner-experience worker added a conversation panel
(`frontend/src/redesign/companion/`) with provider/consent controls, separated evidence,
explanation, next-step and limits blocks, backend-only action cards, cancel/retry with stable
request identity and restored history. It is mounted as a second mode inside the existing
companion card. TypeScript and the production build pass; **no browser journey has been run for
the new panel yet**.

A pre-existing `scripts/backend_smoke.py` tier-3 fixture conflict with the intentional server
tier guard is recorded in the ledger rather than silently repaired.

## Fresh first-time-user audit and repairs — 21 October 2026

User requested a fresh, uninformed browser tester followed by supervisor triage and fixes.
The GPT-6 Luna medium tester produced `output/verification/naive-user-audit-2026-10-21/findings.md`
with 24 screenshots and explicit partial coverage. Supervisor triage and repair evidence is
`review-and-repair.md` in that directory. A real infeasible Courier tutorial led to discovery
and repair of three canonical gameplay defects: impossible before-bell routes, aliased Tier 3
plots and duplicate parcel pickup. New HY-01 v2 preserves historical v1 semantics; 240 generated
cases and exact version/retry regressions pass. Root browser replay completed tutorial 1/1 and
Tier 3 4/4. Numbered parcels/promise mappings and icon lifecycle were corrected; navigation now
says Resume assessment for an unfinished saved session. This audit is not exhaustive acceptance:
three baselines and Tidekeeper were partial in the discovery run, and the auditor's follow-up
browser became unavailable. See the report for precise coverage and remaining checks.

## Latest supervisor continuation — 21 October 2026

The current completion record is `LUNA_COMPLETION_REVIEW.md` and `LUNA_COMPLETION_LEDGER.md`.
Two GPT-6 Luna medium workers implemented the accepted missing activity scope, followed by
supervisor integration and real browser repairs. All six hybrids and the separate crystal
form exist; all five baselines and all six hybrid completion journeys were replayed on
disposable QA data. Production/structural/API checks remain separate from image acceptance.
Quest island map, responsive clipping/interception, completion identity and genuine network
recovery were repaired. Primary learner data is untouched. Full reference acceptance and
the final new-game recovery matrix remain open; 95% and release readiness are not certified.
Older dated gates and worker counts below are historical and superseded by the current
two-worker authorization and completion records.

Current human authorization, 19 October: continue across other pages and all existing games while the separate Home agent repairs the reported scroll/sidebar overlap. The earlier Home-only dispatch gate below is superseded; Home visual acceptance is still open. The supervisor manages two parallel work chats under disjoint file ownership and independently reviews integration. See UI_REBUILD_CONTROL.md for the current completion objective, lane ownership and the new top/mid/bottom scroll-overlap regression requirement. The parent goal service still refuses replacement of its old unfinished usage-limited goal.

Latest visual steering, 19 October: use the approved illustrated-adventure review package in `output/visual-design-review-2026-10-19`, exclude rejected boards 32/33, preserve the existing companion, and implement one page at a time with independent review. Home now has typed presentation boundaries, a reusable world catalog/primitives and extracted shared navigation. Its build, five adapter checks, consent/retry/session/plan behavior and eight responsive widths passed independent software QA. Exact pixel fidelity remains unaccepted; subsequent pages have not been authorized to advance past this gate. See `output/verification/home-2026-10-19/HOME_REVIEW.md` for evidence and remaining visual differences. This does not mark the overall project goal complete.

Working goal: deliver the complete AI4BRAIN POC using the supplied Sprints 01–04 Execution Plan, with GPT-6 Luna implementing scoped batches and the supervisor independently reviewing code, rendered screens and behavior. The user's latest priority is a substantial improvement to the games, animation, overall visual quality and reference-matched companion.

Roadmap source: [Sprints 01–04](source/AI4BRAIN_Sprints_01_to_04_Execution_Plan.md). The document is requirements evidence; user instructions and accepted project decisions govern execution. Dates and competition constraints are supplied-document claims.

## Current sprint position

| Sprint | Implemented evidence | Remaining review / work |
| --- | --- | --- |
| 01 — First Working Brain | Versioned reasoning bank, immutable attempts, exact replay, snapshots, four-trial difficulty and local graph have passed supervisor API/browser checks. | Core implementation and the 19 October read-only Neo4j recheck passed; retain software-QA limitations. |
| 02 — Full Cognitive Assessment | All five task families completed in the redesigned browser flow: 1 memory practice + 6 baseline, 1 reasoning practice + 6 baseline, 6 attention practice + 40 baseline, 4 flexibility practice + 24 baseline, and 1 planning tutorial + 3 baseline puzzles. | Core development QA passed; final release audit is deferred. Browser checks are software QA, not human participant or clinical validation. |
| 03 — Coach and Experience | Real collaboration actions across all five rubric dimensions, session-scoped collaboration cards, dashboard mode invariance, exact retry/recovery, assisted-training HOLD, successful tier change, mobile/reduced-motion and keyboard checks passed in independent browser QA. | Dashboard completion and inspected report/deck drafts are recorded below. Final release audit is deferred; user/clinical validation is not claimed. |
| 04 — Release and Submit | Setup/start/stop scripts, README, source traceability and report/pitch/demo content exist. The isolated deletion walkthrough and primary learner-data preservation were browser verified. | Report/deck remain inspected review drafts; the actual 3–5-minute recording and final release audit are deferred. Clean dependency installation and isolated startup rehearsal passed on this machine. Publication and committee submission remain deferred until a concrete result is ready and the user authorizes it. |

## Earlier active batch plan — superseded by the verification update below

1. Game craft and lifecycle: one focused game shell, five richer native interactions, explicit attention readiness, static scored cues, retained timing/replay/interruption guards.
2. Companion fidelity: rebuild from `ui-reframe/07-companion-states.png`; organic graphite body, fixed round white eyes and moving pupils, meaningful Motion states, quiet scored assessment, accessible dock/hide/chat.
3. Product experience: clearer welcome, refined layout and typography, richer evidence-backed Analytics/Quest, Motion transitions, integrated companion.

Implementation uses Motion for React (`motion/react`, previously Framer Motion), installed in the existing React/Vite project. The UI/UX skill was consulted; its spacious/minimal interaction guidance fits, while its generic orange landing-page palette is not adopted over the approved white/graphite/blue direction. Family-specific soft accents may support game identity.

## Historical acceptance gate — superseded by the verification update below

- Production build and relevant existing API smoke checks.
- Real browser checks at desktop and 375px: welcome, selection, all five task controls, attention start/window, interruption/retry, training decision, saved plan and coach.
- Match the reference companion by visual comparison; test blink/look/loading/reply, reduced motion, keyboard docking and hidden state.
- Baseline items/formulas stay versioned. No correctness hints during scoring, no fabricated scores, missing evidence remains unassessed, and dashboard modes share evidence.
- Preserve `data/ai4brain.sqlite3`, including the session of unknown provenance. Use only isolated QA data for recording/deletion checks. Neo4j alone remains the authorized Docker service.

## Development-first steering — 19 October 2026

The user asked to leave GitHub/submission details aside and focus on development. Publication/submission and additional recording work are deferred; local report/deck files are review drafts.

Latest independent checks: battery, personalization, canonical backend, dashboard, coach API, collaboration API, lifecycle and graph-degradation smokes passed with isolated databases. Neo4j was restored alone and passed live read-only canonical-reference checks. The redesigned memory/reasoning/attention/flexibility/planning flows ran in isolated browser QA; attention preserved full fixed windows and planning saved-response retry locked edits and replayed the identical request.

The development repair batch described below was still under QA when this historical note was written. Its planned checks and intermediate status are superseded by the independent results dated 19 October 2026 at the end of this file.

## Independent browser verification update — 19 October 2026

This is the authoritative current development status and supersedes the earlier pending visual/lifecycle/collaboration checks above. It records supervisor-run software QA in isolated browser/API environments; no human participant, clinical or live-provider validation is claimed.

All five task families completed in the browser with their documented practice and baseline counts. Planning saved-response recovery preserved the exact request after an ambiguous network failure. A successful trial POST followed by a simulated session GET 503 recovered with GET-only reconciliation and no second POST. The interruption test injected the registered browser blur handler, then failed the follow-up GET: the interrupted board reset to its start with zero moves, locked input, recorded one interruption POST and recovered via GET only. Automated Chrome tab switching did not emit blur, so the interruption result is specifically an injected-handler check, not a manual visibility-event acceptance claim.

Training navigation consumed assisted planning items without counting them as unassisted difficulty evidence. A four-attempt block containing one assisted response produced HOLD with three eligible attempts and four supporting references; a subsequent four-eligible-attempt block saved a successful tier 1 to tier 2 decision. A separate baseline-isolation artifact confirms all five baseline indices, evidence references and snapshot references remained unchanged.

All five real collaboration UI actions were completed; the score remained unavailable until the fifth rubric dimension evaluated, then reached 100. The actions saved a real goal and plan revision. Analytics and Quest used the same dashboard evidence and actual participation XP (380). A simulated dashboard 503 exposed keyboard retry while preserving the saved session ID. Isolated disposable-database export and typed deletion cleared the local session and returned to welcome; primary learner data remained intact. The current primary API returned HTTP 200 for the dashboard after integration.

At 375px, content and panels stayed within the 360px content area without horizontal overflow. Reduced-motion behavior, Escape handling, focus restoration and keyboard retry passed. A subsequent read-only Neo4j recheck passed on 19 October 2026 with all 158 unique canonical references resolving. Only minyar-neo4j-1 was running and healthy.

Report and pitch artifacts remain review drafts. The user deferred publication/submission and additional recording work. The whole-project scope audit remains open; do not mark the overall goal complete from this batch alone.

## Dashboard-completion batch — implementation and independent review

The scope audit identified missing Analytics saved-focus/collaboration summaries and Quest skill-tree/milestones. Luna implemented both. Parent verified all five connected branches, real selected indices/coverage/plan tiers, four canonical milestones and their references, and 375px layouts. A fresh disposable learner had zero XP, null collaboration score, five unassessed branches and no earned milestones. Delayed preference reads, rapid writes and reload persistence passed while profile/history/plan/recommendation/activity/coverage/collaboration/milestones stayed identical. Final focus-clear check and source-copy build are recorded in the acceptance note below when complete.

## Dashboard and environment acceptance — 19 October 2026

The current dashboard-completion batch is accepted after independent code, API and browser review. Saved focus and collaboration summaries, connected Quest map, canonical milestones, populated/fresh states, mobile bounds, keyboard/reduced motion, delayed preference races, focus save/clear and reload passed. Final production build and expanded dashboard smoke passed. Primary API serves the new DTO and existing learner records were preserved. See output/verification/DASHBOARD_V3_REVIEW.md.

Clean dependency installation and empty-profile HTTP startup passed in a disposable source copy on this machine. Startup scripts now enforce documented runtime minimums, clean their own failed launches and retain verified ownership across repeated starts. Parent independently checked start → start again → stop; no owned QA listener remained. See output/verification/CLEAN_START_REHEARSAL.md and parent-start-repeat-proof.json.

Development work is the priority. Final recording, finalizing the review artifacts, GitHub publication and committee submission remain deferred. Optional voice, voluntary check-in and forecast remain omitted as allowed by the POC scope. Do not mark the entire goal complete from this development acceptance.

## Full-specification observations/timing batch — open

A fresh source audit against the entire POC and four-sprint plan found gaps beyond the earlier flow checklist: task-specific descriptive observations were not visible, EX-03 persisted item-load onset rather than its armed cue onset, and the assessment shell lacked elapsed time. Earlier accepted dashboard checks remain valid for their stated scope; they did not prove these requirements.

Luna is implementing a reviewed three-task batch: canonical baseline observation details shared by both modes; explicit per-cue timing with null no-response timestamps and unchanged immutable retry; and a server-started session elapsed clock. Source audits are output/verification/FRONTEND_SPEC_COMPLETION_AUDIT.md and BACKEND_SPEC_COMPLETION_AUDIT.md. Parent acceptance requires real delayed-readiness attention capture, complete/empty observation states, mobile bounds, reload timing and unchanged baseline scoring/retry semantics. No primary participant evidence will be generated for QA.

## Approved redesign integration and defect repair - 19 October 2026

The approved illustrated-adventure presentations are now mounted in the canonical application instead of existing only as lane components. All five game presentations render inside the existing task state machines in frontend/src/TaskComponents.tsx, and Plan, Insights (Analytics and Quest), Practice entry/completion, Evidence, Collaboration and Privacy/Pause render through adapters in frontend/src/App.tsx. No presentation component fetches, scores, keeps a clock, owns trial logic or holds an answer key.

Assignment defects reproduced and repaired: the phone memory grid now fits a standard 3x3 board in one view (327 px board, nine 100 px tiles, no internal scroll); null observations and null snapshots are unavailable instead of fabricated 0% while a genuine 0 is kept; the radar draws only assessed dimensions with explicit not-assessed marks; a missing privacy notice reports mirror status unavailable instead of claiming a clean mirror; pause keeps the canonical saved-response, saved-interruption and planning-draft recovery actions; privacy and pause roots use scoped box sizing with bounded widths; collaboration inspection requires an explicit successful outcome and keeps drafts with accessible errors on failure; Evidence exposes every supplied node type including unknown ones; practice decision copy distinguishes assisted HOLD from the normal success rule.

Additional real defects found during browser verification were also fixed: memory playback never started because the startup delay shared the timer ref the playback effect clears; memory could commit a sequence the learner never entered; navigating to Assessment with a stale training exercise blanked the page; practice entry showed a stale assessment world; a React title-children warning; and the companion occluded the mobile game dock (hidden on mobile game pages only, companion source unchanged).

Verification: npm run build passed; game structural suite 62/62; page structural suite 36/36 (up from 29 with new null, radar, XP, evidence-type, mirror, pause-recovery and assisted-hold fixtures). Browser DOM measurements and behavioral outcomes were collected against an isolated database copy on ports 8011/5190; primary learner data was not written. Registration remains open for Attention cue onset in a visible window, saved-response/interruption retry as one continuous browser journey, artwork fidelity of Planning/Reasoning and the Plan/Analytics/Quest/Evidence pages against approved references, reduced-motion and narrow-landscape passes, and human visual acceptance. Packet: output/verification/ui-rebuild/games/full-audit/FIX_REPORT.md.

## Deep QA repair pass - 20 October 2026

The independent deep QA audit (output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20) reported six P1 and seven P2 frontend defects. This pass reproduced each against current source, repaired the well-understood ones and replayed them in a real browser against a fresh disposable database.

Browser-verified fixed: the timed Memory board no longer scrolls internally at 1440x1000 (region 628px, content 628px, every cue marking visible); an explicitly chosen world is no longer abandoned after its practice item (Reasoning stayed Reasoning while Memory was incomplete); a delayed memory graph response can no longer overwrite the newly selected family's evidence; a transient dashboard 503 no longer discards loaded insights or Home participation; the training header reports the canonical four-attempt decision window instead of the bank size.

Fixed at source with replay pending: attention pause/resume deadlock (stale paused closure in the shared commit hook), inline recovery no longer re-posts an accepted save (routed through the canonical accepted/pending recovery), planning paver alignment (a leftover half-cell translate), modal focus restoration when the originating control unmounts, training coach membership resolved against the block seed and version, and readable validation error text instead of "[object Object]".

Still open: tier promotion does not yet propagate into the world-launch path when the canonical selector's gate points at a different incomplete family; collaboration inspection still does not render the cited source record; the mobile footer hit target is still covered by the fixed navigation; the Memory replay assistance policy needs an explicit decision (a replayed attempt is currently recorded as unassisted); page and game visual fidelity against the approved references is unchanged; the six hybrid games are not implemented. Packet: output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/REPAIR_PASS.md.

## Batch 1 of the repair plan - 20 October 2026

QA-04 is now closed server-side: an explicit world choice no longer sends a client tier ? the server resolves the family's canonical current tier from its latest immutable difficulty_changed event, rejects a supplied tier above that decision, and keeps the family's own baseline-eligibility check. Browser proof in one session: Reasoning promoted Tier 1 -> Tier 2, then reopened from Home as a tier-2 block with the POST body carrying only session and exercise, and a reload restored the same tier-2 block.

QA-05 is closed end to end. Coaching the current tier-2 item returns 200 with assisted_training true; the coached trial records hint_count 1 and scored false; the four-trial block yields HOLD at tier-2 with valid_trial_count 3 and the assisted-exclusion reason codes. Item-level rejection still returns 422 and block/session/phase rejections still return 409/404.

Memory Replay is now recorded as canonical assistance per the human's decision: replay_count 1, scored false, excluded from unassisted eligibility, with no change to scores, thresholds or frozen baselines.

QA-13 is closed after a traced failure chain: the dialog captured body focus because the More-menu item unmounts, then selected a hidden sidebar button, then focused an inert control, then let document order pick Play. Focus now prefers the marked trigger when visible and measurable, with one deferred retry after the shell's inert cleanup. Verified on mobile Escape, mobile Close and the desktop footer trigger.

Still open in this plan: QA-02 pause replay in Attention baseline and training, QA-07 retry paths under fault injection, QA-08 collaboration source inspector, QA-11 footer hit target, the QA-09/QA-01 replay matrix, reference fidelity and the six hybrid games. Packet: output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/BATCH1_VERIFICATION.md.

## Batch 2 of the repair plan - 20 October 2026

QA-08 is closed: collaboration inspection now renders the cited immutable source record (type, phase, family, exercise, item, recorded time, scored, response, evaluation, timing, interaction, event id, linked references and an uncertainty caution) before the acknowledgement can be enabled, instead of only flipping the button to Inspected.

QA-11 is closed with the root cause found: styles.css set .app-shell{padding-bottom:0}, cancelling the mobile reservation, so the document ended underneath the fixed navigation. The reservation now sits on the footer itself plus html scroll-padding-bottom. elementFromPoint at the footer button centre resolves to that button at 375, 768x900, 812x375, 1024x768, 1440x1000 and 1920x800, and real pointer clicks open the privacy dialog.

QA-09 is closed: cell-to-tile centre deltas are 0 across 2x2 and 3x3 boards (3x3 includes a boulder) at 1440x1000, 375x812 and 812x375; the pawn sits exactly on the trailhead cell and the portal within 0.1px of the goal cell. QA-01 is closed at four viewports (628/327/141/272 of region vs content, nine tiles visible, no occluded control, no scrolling during a scored playback). QA-07 lost-reply recovery is closed from a cold reload: the pending trial restored into the practice stage, retried once, advanced a round, cleared the pending entry, and left exactly one event for its event id.

Two further defects were found and fixed while replaying. QA-15: at 812x375 every game clipped - Planning lost its board and pawn, Memory clipped its first tile row under the app header, Reasoning pushed all four answer buttons off-screen - now reflowed by short-landscape media queries with zero occluded controls. QA-16: a pending training save dead-ended on an empty assessment page ("No task is ready to open") instead of restoring into the practice stage.

Checks: npm run build passed (14.99s); presentation suite 64/64; page suite 36/36. Still open: reference fidelity against the approved plates, the six hybrid games (HY-01 to HY-06, not started), Attention/Flexibility clipped composition at 812x375, and the 40px landscape Memory tile size as a composition/tap-target decision. Packet: output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/BATCH2_VERIFICATION.md.

## Batch 3 pass 1 - visual fidelity and responsive composition - 20 October 2026

Memory was compared against approved plate 03 at 1440x1000 and two concrete mismatches were closed: the nine tiles now sit in one carved stone slab (10px stone frame, bevel and groove shadows, 5px grooves, per-tile carved inset) instead of floating as separate rounded cards, and the stage no longer draws an inner scrollbar over the artwork (task box 880/880, board region 628/628, nine 191px tiles all inside the viewport, capture screenshots/batch3-memory-1440.png). Remaining Memory differences are itemised in VISUAL_MISMATCH_REGISTER.md: tile carving is a hand-drawn diamond rather than the plate's concentric circles, only gold lit cells exist where the plate shows gold and teal, the slab is orthographic rather than in perspective, and the dock still floats over the art instead of sitting on a plate.

Narrow landscape was the largest real composition defect found. At 812x375 every game clipped: Planning lost its board and pawn and its dock sat under the fixed footer, Memory clipped its first tile row out from under the app header, and Reasoning pushed all four answer buttons to y 401 beyond a 375px viewport. Short-landscape media queries now reflow those three scenes; after the fix zero controls are occluded or off-screen in any of them.

Not started, and not claimed: Reasoning, Attention and Flexibility have not been compared against plates 04, 05 and 06; the pages 07-15 comparison has not been redone; and none of HY-01 to HY-06 exists in source. The hybrid games need their versioned canonical configs, generators and oracles before any presentation work, so they remain a separate authorised body of work rather than a styling pass. Checks in this pass: npm run build passed (15.43s), presentation suite 64/64, page suite 36/36.

## Hybrid-v1 contract, HY-01 and local KittenTTS speech - 20 October 2026

The hybrid evidence contract the human specified is now implemented and verified rather than documented: hybrid-v1 stores its own append-only tables (hybrid_attempts, hybrid_events, hybrid_assistance, hybrid_outcomes) with immutable event ids and payloads, ordered actions, exact-retry identity, conflicting-retry rejection, backend-derived outcomes with an evaluation_version, evidence links and explicit `excluded_from_unassisted`. Hybrid work never enters the EX events table, the EX scorers, difficulty tiers, recommendations or participation XP; after an assisted and an unassisted hybrid attempt the session held only consent_recorded and all five dimensions stayed INCOMPLETE_BASELINE. Assistance is enforced server-side per activity window: a pre-play window closes after the first action, an unknown exposure is 422, a wrong window for that activity is 409, and the exposure row is written before any help renders.

HY-01 The Courier's Promise is playable end to end from a new Hybrid lab destination: tier choice, encode phase with the promises, then a garden where the promises are hidden, tap/keyboard movement, pickup by stepping on a parcel, deliver on a plot, a bell threshold on the move count, an assisted reminder, and a review of promises kept, wrong-plot deliveries, cue misses, order deviations, moves against the BFS lower bound, evidence count and limitations. Browser evidence: encode -> play -> 3 moves -> deliver -> assistance POST 201 before the reminder appeared -> review 1/2 promises with 7 immutable evidence records -> reload still counted (1 unassisted / 3 assisted); zero 4xx/5xx and no page errors.

Local KittenTTS companion speech is implemented with the pinned CPU stack (kittenml 0.9.4 plus KittenML/kitten-tts-mini-0.8 ONNX, no PyTorch), a single-worker bounded queue that supersedes stale requests (burst of five: two 409 superseded, three 429 queue full), 24 kHz PCM WAV output, and an off-by-default UI with voice, speed, explicit auto-speak, play/pause/resume/replay/stop and latest-reply ownership. Browser verification produced real audio (content-length 1,105,244; x-speech-seconds 23.02), switched state on every control, stopped the old audio when a new reply arrived, persisted the setting across reload and raised no failures.

Checks: npm run build passed (14.14s); presentation suite 64/64; page suite 36/36. Still open and not claimed: HY-02/03/04/05/06 (each needs its own generator and evaluator on this contract), the separate 3x3 crystal Reasoning form, pages 07-15 reference comparison, Memory M3-M7, Attention pause replay (QA-02), and human acceptance of visual and audible quality. Contracts and setup: docs/HYBRID_CONTRACT.md and docs/COMPANION_SPEECH.md.
## Batch A progress - 20 October 2026

QA-02 is now browser-verified rather than assumed. Live Attention practice on isolated QA data, three pause points (visible cue, pacing boundary, delayed save) all resumed into a live task within 1.5s, the Resume control stayed disabled while an interruption save was in flight instead of resuming into a live window, and every interrupted trial was recorded as an excluded interruption record with the item re-presented. Respond-window durations were sampled every 50ms: 1386/1555/1496/1558/1541/1570/1507 ms before a pause and 1563/1493/1555/1504/1496/1507/1552 ms after it, so the paused cycle neither shortened the window nor reused a stale cue; the single 141 ms window is the one the pause aborted. Nine session events, nine unique ids, zero duplicates, zero 4xx/5xx and no page errors; reload mid-attempt recovered to Home and then to round 5 of 6 with the Respond control live.

The recovery matrix is extended beyond the batch-1 Planning packet: Reasoning resends a rejected POST with the identical event id and payload, Flexibility issues no second trial POST after an accepted save and reconciles with GET only (session GETs 1 -> 2) before advancing with the rule switched, and Attention survives a lost reply through reload and retry with three unique posted ids for three canonical records and no duplicate canonical ids. Memory was verified through its saved-response replay rather than a fresh fault injection; that remaining gap is recorded in audit_closure QA-07 instead of being presented as covered.

Evidence: output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/a1_attention_pause.cjs with a1-attention/ (result.json, cue-windows.json, four screenshots) and a2_recovery_matrix.cjs with a2-recovery/ (result.json, three screenshots).
## Corrective batch A verification - 20 October 2026

The Batch A evidence was corrected before widening the work, following BATCH_A_INDEPENDENT_REVIEW.md.

QA-02 now covers the states the review asked for, in the right phases, with the right assertions. Attention baseline at 1440x1000: pause during the readiness countdown, during a visible cue, during a normal completed-trial save with no active cue, and at the real pacing boundary. The pacing predicate is `index > 0 && index % 10 === 0`, so the rendered boundary is round 11 of 40 (index 10) and the harness now asserts that from the rendered state, the game-phase class and the Quiet moment lens state instead of assuming a round number. Resume latency is measured with in-page `performance.now()` from the resume click to the actual `.rg-attention-signal` element rather than an enabled Respond button: 2069/2082/2089 ms for the countdown, cue and save pauses and 1465 ms for the pacing pause. Training (tier-1 block, four-attempt window) resumed with a visible cue after 2129 ms and 2087 ms, with the Resume control disabled while an interruption save was in flight. Canonical identity holds: 19 baseline-session records (13 baseline + 6 practice), 3 interrupted records with null onsets, 0 duplicate event ids and all 18 posted ids stored exactly once; the training session produced 8 records on one block id with 2 interrupted and a HOLD decision carrying trial_count 4, valid_trial_count 4, 2 successes, 4 evidence ids and the expected reason codes. Both journeys had zero unexpected errors and every required assertion passed through explicit checks that fail the harness.

A real defect was found and fixed while correcting the evidence: an explicit world choice was stored only in a ref, so a reload during the Attention baseline returned Home and did not restore the chosen family. The choice is now persisted under `ai4brain.family`, honoured by `restore()` ahead of the recommendation, and cleared when the family finishes or local data is deleted (audit_closure QA-17, fixed-verified).

The earlier practice-scope run remains valid for its demonstrated scope and is retained; its pacing label and its transport-abort case are correctly re-labelled, and the saved cue-window probe is superseded by the new recorder that samples the real stimulus element every 40 ms.

Evidence: output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/a1b_attention_baseline.cjs with a1b-attention/result.json and screenshots, plus a1c_attention_training.cjs with a1b-attention/training-result.json and training screenshots. Both scripts exit non-zero when a required assertion fails.
## Batch A2 correction and A3 progress - 20 October 2026

The recovery matrix was corrected to what the independent review asked for, and the app behaved correctly in all three corrected scenarios. Reasoning accepted-then-lost-reply: the trial POST was forwarded to the backend with route.fetch() and the canonical record was confirmed present while the browser still showed a pending retry; after reload the pending entry was correctly cleared because the save had already been accepted, the app offered its explicit continuation, and continuing landed on Baseline 1 of 6 with exactly one canonical record for that event id. Memory fresh fault injection: a 503 rejection retained the exact saved route and the retry POST had an identical sha256 to the original (two posts, one unique hash, no masked timing fields) before advancing to Baseline 1 of 6 with zero duplicate canonical ids. Flexibility accepted POST plus failed session GET: exactly one trial POST, GET-only reconciliation and a phase-aware transition to Practice 2 of 4 with the rule switched to SHAPE. All eleven required assertions are explicit and exit non-zero when violated; zero unexpected errors.

A3 is partly closed. At API level on a disposable session: all five baselines were completed through the canonical trials API (79 baseline records, 13 practice records, 0 duplicate event ids), the profile reports five assessed dimensions, a real four-attempt Attention block produced a HOLD decision with trial_count 4, valid_trial_count 4 and four evidence ids, a supplied tier above that decision is rejected 422, and reopening the family resolves the recorded tier. In the browser the footer privacy control is reachable and activatable at 375x812, 768x900, 812x375, 1024x768, 1440x1000, 1586x992 and 1920x800 with centre hit testing plus a real pointer click opening the dialog, and loaded Insights data survives a failed refresh.

Two A3 items remain open and are recorded rather than claimed. The explicit-world Practice entry is unstable: one run opened Rule Studio for Flexibility in Training at Round 1 of 4 with the family persisted and no API errors, while an identical scripted sequence left the learner on Home with no error message. That must be reproduced, diagnosed and fixed before entry/reload coherence can be called verified. The evidence-graph race was not exercised by the script at all.

The corrective defect from the previous batch stands fixed: an explicit world choice now survives reload (audit_closure QA-17).
## Entry-stability diagnosis and third-party verification list - 20 October 2026

The A3 world-entry instability reported in the previous entry is diagnosed and is not an application defect. Home intentionally disables the world islands while the restore pass is in flight (`frontend/src/home-primitives.tsx`, `disabled={loading}`), so forced clicks during loading did nothing; five repeat runs confirmed the API was still completing the restore scan at the moment of the click. With an enabled-island wait, the explicit Flexibility world opened correctly: Rule Studio, Flexibility, Training, Round 1 of 4, `ai4brain.family = EX-04` and a real block id, with no API errors. As hardening, `openWorld` now waits for an in-flight restore lock (up to 9 s) instead of returning silently, and the global error banner is no longer suppressed on the Home page.

Two A3 sub-checks remain open and are recorded as such rather than claimed: after a reload the family and block id persist but the app lands on Home and the scripted continuation path did not find an enabled continuation control within its wait, so post-reload continuation needs one clean pass; and the evidence-graph race plus a real dashboard-failure injection were not exercised.

`docs/THIRD_PARTY_VERIFICATION_REQUIRED.md` now lists everything the implementation AI cannot certify for itself: human visual acceptance per surface with its reference image, audible quality and default-voice acceptance for the KittenTTS output, independent re-derivation of the canonical scoring and difficulty rules, clinical and participant claims (which nobody may make from this repository), accessibility conformance on a screen reader and with colour-vision simulation, security/privacy and licence review, clean-machine reproducibility, the results that currently rest only on my own harness, the explicitly deferred release actions, and the remaining implementation work that is mine rather than a third party's.
## A3.1 closure, voice-default correction and third-party register repair - 20 October 2026

A3.1 is browser-verified with a fresh timestamped packet (`deep-qa-2026-10-20/a3-new/a31-result.json`). Entry opened Training round 1 of 4 for the explicitly chosen Flexibility world with a persisted block id; after reload the intended Home/Continue control was waited for until enabled and activated with a normal click, resuming the same block and round with zero duplicate scored attempts (one canonical interruption record was added and excluded, which the packet records separately); a slow restore fired four times with the world islands correctly disabled during loading and then produced a usable task; a failed restore produced an accessible error with a Retry control and recovered to a usable page. All required assertions pass and the script exits non-zero on failure.

Two product fixes came out of this: `openWorld` now waits for an in-flight restore instead of silently dropping a world click, and a navigation generation guard stops a slow restore from overriding a learner navigation (`settlePage`). Both are covered by the A3.1 packet.

A3.2 and A3.3 remain open and are recorded as such. The graph race issued both requests but the Evidence surface ended with no dimension pressed (it rendered Insights), and the dashboard fault was consumed by the Home refresh, so the Insights error-and-Retry path was never exercised. Both need one more pass with the fault scoped to the Insights entry and the race observed on the actual surface.

The default companion voice is now Bella in both `frontend/src/CompanionSpeech.tsx` and `backend/app/speech_service.py` (request default and unknown-voice fallback); a saved `ai4brain.speech` selection still overrides it and is never rewritten. A Bella acceptance sample was generated through the API: `output/verification/hybrid/tts-sample-bella.wav`, 24 kHz mono, 7.66 s, peak 0.588, RMS 0.096.

`docs/THIRD_PARTY_VERIFICATION_REQUIRED.md` was corrected: the voice statement now matches source, the privacy section separates the always-local speech path from the opt-in remote coaching path that can send `message[:2000]` plus evidence context, the visual table points each surface at its real captures and marks missing evidence as missing instead of linking unrelated packets, the semantic section now requires derivation from the requirements before comparing code and SQLite, and timing figures are described as observations with hardware, cache and model identity rather than portable thresholds.

## A3 closure: evidence-graph race, Insights fault injection and a duplicate-render defect - 20 October 2026

A3.2 and A3.3 are now browser-verified with fresh packets in `output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/a3-new/` (`a32-a33-final.json`, plus the superseded `a32-a33-result.json` retained as failed evidence). Both scripts exit non-zero on any violated assertion.

A real regression was found and fixed while doing this. The `{page==='brain'}` EvidencePage render line had been dropped and then re-added twice during earlier edits, so the Evidence route rendered no page of its own (the app fell through to the previously selected surface) and, once restored, mounted two identical EvidencePage instances (10 family buttons for 5 families, two `aria-pressed` matches). `frontend/src/App.tsx` now has exactly one render block per route; a per-route count check was run for welcome, overview, plan, collaboration, brain, hybrid, practice and assessment.

A3.2 (13/13) drives the rendered surface rather than the request log. Reference payload signatures were captured for all five families (Reasoning 50 nodes, Memory 58, Planning 27, Flexibility 89, Attention 1087), then: Planning's `/api/graph` response was held, Memory was selected and its payload painted while Planning was outstanding, and releasing Planning left the rendered Memory payload, its node summary and its pressed state intact. In the reverse-arrival case both Flexibility and Attention were held; releasing the older Flexibility response first left the previously rendered Reasoning payload untouched (the stale-payload guard held), then releasing Attention painted its 1087-node payload with Attention still the only pressed family. Large graphs need roughly 1.2 s to paint here, so the harness waits on the expected payload signature instead of a fixed sleep.

A3.3 (6/6) records structured loaded values (summary pairs, all five family aria-labels, detail heading and metric values), then lets exactly one real `/api/dashboard/demo-user` refresh from the Insights entry return 503. `intercepted` was 1 on that request; an accessible `role="alert"` reading "Saved insights could not refresh. Showing the last loaded data." appeared with a Try again control; every captured value was byte-identical (Task families 5/5, Evidence records 870, Collaboration not enough evidence); pressing Try again with the browser issued a 200, cleared the alert and produced identical structured data. The only console error in the packet is the deliberately injected 503.

## B1 approved asset pipeline and B2 Memory M3-M6 - 20 October 2026

B1 is complete. `scripts/prepare-game-assets.py` now extracts 55 sprites from the approved sheets 16, 19, 20, 28, 29, 30, 31 and 39, and records for each one the source hash, the crop box, the trimmed box, the output hash, the measured alpha edge quality, the intended consumer module and four preview artefacts (checkerboard, approved scene, 3x corner magnification, per-group contact sheet). Three crops required edge investigation: `reasoning-plaque-wide` and `reasoning-bracket` contained neighbouring fragments, while the faint `harbor-flag-ivory` pixels were part of the bridge's anti-aliased edge. The crop definitions were corrected and regenerated; the current manifest reports zero prepared-output crop-edge pixels for all 55 assets. A second run reproduced identical output hashes, so the pipeline is deterministic. The manifest also carries four reviewed alternates (17 and 18 are presentation repeats of 28 and 29; 21 was already delivered as `/art/adventure/*`; 32/33 are rejected) and three honest missing entries: `hybrid-tide-dial`, `hybrid-market-goods` and `memory-tile-stack`, each with the reason and the native-geometry handling instead of invented art. The correct inventory is 8 Planning sprites plus 47 additional prepared sprites, for 55 total. Approved sources are never modified.

B2 implements M3 to M6 on the Memory game. The tile carving is now three concentric engraved rings plus a diamond and core; the slab carries deeper stone grooves and a static perspective tilt on desktop only; the cue has both approved tones (gold on the first pass, teal on the assisted Replay pass) with a non-colour pip, a filled-versus-open core and explicit "assisted replay" wording in the dock; and the bottom dock is now one raised ivory plate holding the phase label, one dot per canonical sequence stop, the live status, the note and the unchanged native Undo/Replay/Retry controls. Accumulated cue history was deliberately rejected: showing earlier stops together would hand the route to the learner and contaminate the unassisted evidence. M7 (shared game shell header) stays open because it is shared across all five games and belongs with B3.

Evidence: `deep-qa-2026-10-20/memory-visual/memory-visual.json` (21 assertions, 0 failures) with desktop 1440x1000 and phone 390x844 captures of the watch phase, the learner turn and the assisted replay, plus pointer/keyboard mapping checks through the perspective transform and a proof that all nine tiles stay inside the board region without inner scrolling during the cue. The production build passes. Human visual acceptance of these screens remains explicitly pending.

Remaining in this batch series: B3 Planning P9-P12 plus the shared shell regression across all five games, then Reasoning/Attention/Flexibility fidelity, pages 07-15, HY-02 to HY-06, the versioned 3x3 crystal Reasoning form, companion image-07 fidelity and KittenTTS quality/lifecycle.

## B3 shared shell and Planning dock - 21 October 2026

Active continuation steering: the human approved exactly two GPT-6 Luna medium implementation
workers and then requested **90–95% development completion, leaving only minor polish and
finishes**. Both workers have been launched; the supervisor owns shared integration, independent
checks and repairs. Current durable goal/ledger: `GOAL_GAMES_VISUAL_REBUILD.md` and
`LUNA_COMPLETION_LEDGER.md`. Missing games, broken flows or unverified critical recovery remain
required implementation, not polish. New human direction supersedes historical staffing notes.

The shared game header was rebuilt once for all five games (M7/P9). It is now a title block
(`Planning / Route Garden`, `Working memory / Memory Grove`, ...), a lane string derived from the
running exercise (`Baseline · Uncoached` for baselines and reassessments, `Training · Tier n` only
when the server actually sent a tier, otherwise the plain phase), one dot per canonical round
(hidden above eight rounds so a 40-trial baseline does not draw forty dots), the round and
five-world copy, the session clock, and the Back/Pause pills. Nothing is hardcoded from the
reference: the dots count comes from the decision window or the item bank and the tier comes from
`difficulty_tier`.

Planning P10-P12: the dock lobe is now a pseudo-element of the direction pad, so it follows the
pad's real position inside the dock and the pad sits raised inside it; the phone scene reserves
30 px of head top padding and the portal sprite overhang was reduced, which removes the 375 px
top-row and portal clipping; the shell was measured at 1586x992 to fill the viewport with zero
top and bottom gap.

Evidence: `deep-qa-2026-10-20/shell-b3/shell-b3.json` (all assertions pass across five games at
1440x1000 and Planning at 1586x992, 1024x768, 812x375 and 375x812) and
`deep-qa-2026-10-20/planning-gameplay/planning-gameplay.json` (pointer moves 0->2 with the pawn
actually shifting, Undo 2->1, ArrowRight moving the pawn, ArrowUp into the edge raising Blocked to
1, Restart returning the pawn to the trailhead with legal steps 0 while keeping the 5x5 board with
3 boulders and the blocked history, zero scored trial POSTs, zero console errors).

One naming difference stays open rather than being silently changed: the approved plates name the
worlds `Wayfinder's Garden`, `Lantern Grove`, `Pattern Atelier`, `Signal Observatory` and
`Shifting Gallery`, while the application names them `Route Garden`, `Memory Grove`,
`Pattern Observatory`, `Signal Harbor` and `Rule Studio`. The header uses the application names so
Home, Insights and the games stay consistent; adopting the approved names is a single vocabulary
change if the human wants it.

## Luna one-hour checkpoint — 21 October 2026
Exactly two Luna medium workers completed scoped batches. Six hybrids and separate crystal-count form integrated; supervisor independently replayed HY02–06 plus crystal, repaired lifecycle/ownership/recovery/Memory issues. Final build, TypeScript, pages36/36, gamepresentations64/64 and isolated canonical smokes pass. Goal remains active; 95% and final image fidelity are not certified. Current evidence/remaining work: docs/LUNA_COMPLETION_REVIEW.md. Owned isolated QA8031/5191 retained for continuation; primary data untouched.

## Fresh fix confirmation and recovery repairs — 21 October 2026

Supervisor continued the blind-audit follow-up in the actual browser on a disposable copy.
Original NQA-01–05 remain repaired; fresh canonical Courier v2 240-case checks pass.
New NQA-06–09 close immutable Courier action retry, canonical reload reconstruction,
explicit interrupted/assisted review labels and input locking during pending completion.
Lost action/completion response tests include exact request SHA256 and GET-only reconciliation.
The tutorial recovered through two reloads and completed 1/1 at seven moves, ten unique events.

Remaining core baseline gaps were replayed: Memory 6/6, Attention 40/40, Flexibility 24/24.
Together with retained Reasoning/Planning discovery evidence, the saved profile is 5/5;
SQLite independently confirms 79 unique uninterrupted scored baseline records and family/item
pairs. A fresh twelve-cue Tidekeeper block also completed with fourteen evidence records.
Production build/TypeScript, recovery-state, hybrid gameplay and scoped lifecycle suites pass.
Evidence and honest remaining coverage: `output/verification/fix-confirmation-2026-10-21/REPORT.md`.
This does not certify final plate fidelity, every-game browser fault coverage or 95% completion.
Owned QA services stopped and temporary config removed after verification; primary data untouched.


## Independent plan verification - 22 October 2026 (latest audit)

Report: `output/verification/plan-rejudge-2026-10-22/REPORT.md`; full 59-point scorecard
alongside it. This supersedes blanket RJ-03 closure claims above: the exact synthetic
explanation `Your Memory index is 100.` and other factual paraphrases still pass as
validated against a 12.5 baseline. RJ-03 remains OPEN, HIGH. No app repairs in this audit.

Fresh R1/R2, R4 40/40, R5 68/68, coach context, plan revision, collaboration claims and
dashboard checks pass. Production build passes after scoped sandbox-path escalation.
Personalization smoke fails at its directly inserted tier-change fixture because the
saved plan is stale; resolve its contract without weakening authoritative tier guards.
Supervisor browser confirmed Try this strategy -> Memory practice, detailed cited record
inspection, and four reachable Tidekeeper pad centers with real response clicks at
1280x720. Other viewports and broader journeys remain inherited evidence.

G0-G5 is largely PLANNED: no 72-case manifest/split/comparators/reserved run. Exploratory
probes show empty availability falling back to all dimensions, public availability input
unsupported, and Reasoning recommendation versus Planning-only five-minute plan. Nominal
40/68 pass counts are separate regression evidence, not generalisation completion.

Rehearsal scores: Phase A 75/100 (was 69); Phase B readiness 44/100 (was 40); weighted
62.6 (was 57.4); generalisation 6/25. These are not completion percentages or official
results. No human study is imposed as a software-benchmark prerequisite. Hosted/TTS tests
remained deferred; primary data, approved assets and Docker workloads were preserved.


## Focused generalisation rejudgment - 22 October 2026 (after R7)

Independent supervisor report: `output/verification/generalisation-rejudge-2026-10-22/REPORT.md`.
The executable benchmark exists. Fresh runs reproduce 48/48 development, 24/24 reserved,
12/12 declared R7 rows, and a clean personalization suite. Original benchmark/freeze bytes
were preserved. This is a repeated observed pool, not a new blind evaluation.

The blanket comparator-advantage conclusion is withdrawn pending repair: comparator dimension
labels are checked against EX-id keys, forcing zero scores; single-family expectations also
lack the expected action used by that scorer. Applying existing candidate predicates
consistently to the saved comparator outputs gives 3/5 dev and 2/3 reserved for each baseline,
not zero. This recalculation is a metatest, not a corrected/fair benchmark result.

Remaining verified defects: saved plans drop availability/resolved-next/selection-policy fields;
goal-triggered reconciliation clears Planning-only and explicit empty restrictions; recent
Memory practice plus exploration boundaries causes recommendation/plan disagreement (4/8
pairs); number-free false claims ("You recalled every position correctly", "No mistakes were
recorded in your Memory responses") still pass the provider boundary against a 3/24 baseline.
The original numeric paraphrases now fail as intended. Broad factual correctness remains open.

Generalisation rehearsal judgment: 9/25 (previous 6). No new overall application score was
assigned by this focused pass. Fix comparator/weak assertion/freeze scope, persist constraints,
and share a stable decision snapshot before using a new independently reserved pool. Preserve
the current set as exposed regression coverage. A complete participant protocol is still
preparatory work; actual recruitment/data and human/expert/release acceptance stay separate.
No application fixes, hosted calls, TTS tests, primary-data or Docker changes in this audit.

## Planning-only follow-up design — 30 October 2026

`docs/HYBRID_COMPANION_GRAPH_PLAN.md` proposes follow-up work for the existing HY-01–HY-06
activities, their later personalized-plan integration, assisted practice with quiet scored
baselines, Fast local voice by default with Bella optional, and Obsidian-style Brain Twin
navigation. This is a design/review artifact; no product behavior is claimed fixed here.
The latest limited disposable-profile probe completed HY-01 tutorial, completed one HY-02
12-cue stream, and collected partial input/reload probes for HY-03–HY-06; it did not provide
completion proof for HY-03–HY-06 or launch Crystal. See the plan's per-game limits and
`output/verification/responsiveness-20261030/plan-review.md` before using older status rows
as acceptance for this follow-up. Supplied timing samples remain single observations, not
latency distributions; no new provider, package, runtime, or application changes were made.
