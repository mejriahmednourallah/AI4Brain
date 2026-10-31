# Connected-agent completion ledger

## Generalisation continuation â€” planned, 22 October 2026

The G0â€“G5 appendix in `CONNECTED_AGENT_PLAN.md` adds the three human-selected tracks:
unseen learner situations, unseen task variations and unexpected constraints. All new
implementation/evaluation tasks start open. Proposed benchmark: 36 development + 36 reserved
synthetic scenarios, with split/version provenance, independent oracles and fair comparators.
No human participants or learning-benefit evidence exist. Participant protocol is preparation
only. TTS/provider testing is deferred from the active focus at the human's direction.

Trusted integrated evaluation depends on the reopened R1/R2 contracts and activity-action
wiring. The 40-case coaching suite and prior broad game QA remain separate evidence.
No agents/services were started and no app code was changed by this plan amendment.

## Reopened acceptance gates â€” 22 October 2026 rejudgment

The correction/completion appendix in `CONNECTED_AGENT_PLAN.md` extends the previous plan.
The states below supersede contradictory completed labels in older entries; historical
evidence is retained. They were reopened as findings and are now updated with the repairs and
receipts recorded in the R1â€“R5 section below.

| Finding | Current state | Next acceptance gate |
|---|---|---|
| RJ-01 export/deletion omissions | Repaired and verified on a disposable database: coaching turns, conversations, collaboration claims and plan metadata are exported, deletion is learner-scoped and blocks late replies | Residual: real-browser export/deletion journey, Neo4j mirror erasure with the mirror enabled |
| RJ-02 duplicate coaching side effects | Repaired and verified: reservation before generation, replay/conflict/in-progress/concurrent/abandoned cases pass | Residual: live provider exactly-once is explicitly not promised |
| RJ-03 false facts/recommendations accepted | Repaired and verified: field-bound numbers, family/tier/strategy/evidence whitelists, plus new certainty and clinical-assertion rejection | Residual: independently judged helpfulness of generated prose |
| RJ-04 plan tier mismatch | Repaired and verified: one authoritative tier for the saved plan and the launch, stale/mismatched launches refused | Residual: late-response and reload cases in a real browser |
| RJ-05 companion actions/speech integration | Verified in a real browser: an approved action records once and opens practice, real local KittenTTS playback with pause/resume/stop, disable and unmount cleanup, and the companion is absent during a timed activity | Residual: human voice audition, superseded-reply and missing-model cases |
| RJ-06 incomplete model history | Repaired and verified: bounded, ordered learner/assistant turns with provenance from this session only | Residual: live provider round-trip |
| RJ-07 Tidekeeper pad occlusion | Repaired and verified: every pad centre and near-edge point hit its own control at 320Ã—812, 375Ã—812, 812Ã—375, 1024Ã—768, 1280Ã—720 and 1440Ã—1000, with real mouse clicks and keyboard activation | Residual: human visual acceptance |
| RJ-08 opaque/biased verification claims | Repaired and verified: verdicts are derived per claim (supported/contradicted/insufficient) and the saved record is inspectable before the verdict in a real browser | Residual: independently judged rubric helpfulness |

Carry-forward gates: named 40-case suite (now executed: 40/40 pass, `output/verification/r4-forty-cases.json`);
all-game recovery matrix (now executed: 68/68 pass, `output/verification/r5-recovery-matrix.json`);
real configured provider tests (configuration unavailable in the audit); reference fidelity;
human KittenTTS audition; clean/offline setup rehearsal; materials refresh and an independent
new review of the frozen tree.
All six hybrids and crystal already exist. No new implementation percentage is certified.
Evidence: `output/verification/challenge-rejudge-2026-10-22/REPORT.md` and probe receipts.

Live record for the connected-agent upgrade. Updated 22 October 2026. Implementation,
automated verification, browser verification and human acceptance are separate columns and are
never collapsed into one completion claim.

Owner key: **SUP** supervisor, **W1** backend/evidence worker, **W2** learner-experience worker.

## Repairs and verification â€” 22 October 2026 (R1â€“R5)

Executed in this session on the current tree, with a disposable SQLite database per suite,
no hosted provider traffic and Neo4j left as the only optional Docker workload (not started).

| Area | What changed | How it was checked | Result |
|---|---|---|---|
| RJ-01 / RJ-02 | Atomic reservation before generation, learner lifecycle generation/deleting guard, late-reply invalidation, export and scoped deletion covering coaching turns, conversations and claims | `scripts/r1_rj01_rj02_smoke.py` | PASS (replay, conflict, in-progress, concurrent 200/409, delete-in-flight 409, target rows 0, other learner intact) |
| RJ-03 / RJ-04 / RJ-06 | Field-bound factual validation; new rejection of unsupported certainty and of clinical/diagnostic assertions about the learner; distinguishable provider timeout status; ordered role-aware history; one authoritative training tier | `scripts/r2_rj03_rj04_rj06_smoke.py` | PASS |
| RJ-05 actions | `POST /api/coach/actions` records an offered action once, replays exactly, refuses a tampered target | real browser (`actions-and-claims.cjs`) + `scripts/r4_collaboration_claims_smoke.py` | PASS: one 200 call, practice opened, no page errors |
| RJ-05 speech | Local KittenTTS on the Conversation surface with one audio owner | real browser (`speech-verification.cjs`, `speech-quiet.cjs`) and a direct synthesis request | PASS: POST 200 â†’ "Playing local synthetic voice", pause/resume/stop, disable hides controls, unmount leaves nothing playing, no speech request during a timed cue |
| RJ-07 pads | Short-viewport chrome compaction, a constrained play-surface grid column, and a landscape board/pads split in `hybrid.css`; no timing change | real browser (`tidekeeper-hit-targets.cjs`) at six viewports | PASS at all six viewports: pads inside the viewport, five probe points per pad hit their own button, â‰¥44px targets, no horizontal overflow, real click and Space both register |
| RJ-08 claims | Per-claim derived verdicts, safe adjudicating context, flattened inspection payload | real browser (`actions-and-claims.cjs`) | PASS: context facts, saved response/evaluation, verdict recorded 25% |
| R4 | 40 named evaluation cases across seven groups | `scripts/r4_case_manifest.py` | 40/40 PASS (`output/verification/r4-forty-cases.json`) |
| R5 | Per-game recovery matrix: rejected save, lost reply, conflicting payload, failed GET, reload restore, interrupted completion | `scripts/r5_recovery_matrix.py` | 68/68 PASS (`output/verification/r5-recovery-matrix.json`) |
| G3 speech input | Whitespace-only text now returns 422 instead of an internal synthesis error | `scripts/r4_case_manifest.py` case G3 | PASS |
| R6 lifecycle | `scripts/start.ps1` and `scripts/stop.ps1` crashed with a type-conversion error whenever a saved pid file existed | documented start â†’ health/web ready â†’ read-only page journey â†’ stop | Fixed; start 19.9 s, 12/12 page views with a heading, 0 overflow, 0 console errors, clean stop |
| R6 reproduction | Every reproduced finding re-run against the current tree | `output/verification/r6-reproduction/REPORT.md` | All eight closed; the rerun also found the start/stop script crash |
| R6 materials | Technical report rewritten around the current contracts and regenerated as a 4-page PDF; demo script and narration gained the learner-chosen action and local-speech beats; requirement matrix CA rows refreshed; pitch narration and sources updated in the builder | `docs/submission/*`, `docs/REQUIREMENTS.md` | Refreshed except the rendered deck: the pitch builder cannot resolve its artifact-tool module in this environment, so `AI4BRAIN-Pitch.pptx` still dates from 19 October and is flagged in `pitch-outline.md` |

Deliberate limits of this evidence:

- Every failure above was injected at the client or HTTP boundary, or measured in the
  browser for the layout and companion cases. No live Groq or Gemini call was made.
- Human KittenTTS audition, human visual acceptance, expert accessibility/security/licence
  review, publication and any clinical or participant evidence remain external.
- Browser fault injection for the canonical save path was recorded in earlier phases; the
  R5 matrix re-covers those paths at the HTTP layer for every game, and does not replace a
  fresh browser fault-injection journey for each of the eleven activities.
- A clean-machine rehearsal with cold package caches and an independent review by a worker that
  did not write the code are both still outstanding; the R6 rehearsal and rerun in
  `output/verification/r6-reproduction/REPORT.md` are supervisor-run.


- `done` â€” implemented and verified by the stated evidence.
- `partial` â€” implemented but verification or coverage is incomplete.
- `open` â€” not implemented or not reproduced yet.
- `n/a` â€” outside development scope (human or external action).

## Generalisation benchmark (G0–G4 first run) — 22 October 2026

The rejudgment recorded that the generalisation workstream existed only as a specification. It now
has a frozen manifest, an evaluator with two comparators and a first reserved run.

| Item | State |
|---|---|
| Manifest | `tests/generalisation/manifest.json` — 72 named cases (30 task variations, 12 learner situations, 30 constraints), 48 development and 24 reserved, each with an expectation expressed as a specification rule |
| Evaluator | `scripts/generalisation_eval.py` — materialises each scenario over the real HTTP surface on a disposable database, evaluates the expectation with its own rule implementation (not the candidate's output), records per-case verdicts, source hash and comparator scores |
| Comparators | `naive_order` (always the first family, ignoring evidence) and `fixed_tier1` (always tier-1 training, ignoring the evidence gate) |
| Freeze | `tests/generalisation/FREEZE.json` records the source and manifest SHA-256; the reserved split is refused if either changes |
| Development run | 48/48 pass (variations 20/20, situations 8/8, constraints 20/20); both comparators 0/5 on the decision-shaped cases — `output/verification/generalisation/development-run.json` |
| Reserved run (first, frozen) | 24/24 pass (variations 10/10, situations 4/4, constraints 10/10); both comparators 0/3 — `output/verification/generalisation/reserved-run.json` |

Honest limits: the reserved pool has now been observed once, so any further source change
invalidates the freeze and the next reserved run is a new measurement, not a repetition of this
one. The freeze covers the application source and the manifest, not the evaluator script itself,
so changing the evaluator would not trip the guard. Expectations are specification-derived but the
evaluator and the candidate share authors, so this is not an independent oracle, and comparator
policies are deliberately simple baselines rather than tuned competitors. No participant, transfer
or growth claim follows from it.


The latest rejudgment reproduced four new problems after the R1–R5 pass. All four were addressed
and are covered by `scripts/r7_rejudge_fixes_smoke.py` (12/12) and
`output/verification/rejudge-fixes-pv01-pv04.json`.

| Finding | Correction | Evidence |
|---|---|---|
| PV-01 (RJ-03 reopened): factual paraphrases escaped the validator — "Your Memory index is 100.", "Your correct positions are 24." and "Your Memory index is one hundred." were accepted as validated while the canonical record said 12.5/100 and 3 of 24 positions | Generated prose may no longer restate a measurement at all. Any digit, any spelled-out number, or any noun-plus-value construction (`index/score/results/percent/correct positions/error rate` followed by `is/are/of/at/…`) is rejected, so the backend always keeps its own factual clauses and falls back to the validated local answer | `backend/app/coach_v2.py`; probe cases PV-01a–PV-01d |
| PV-02: an explicit empty availability list silently meant "every family is available" | Omitted availability means no constraint; an explicit list, including an empty one or unknown identifiers, is a real constraint that returns `no_available_activity` with the constraint recorded, and the API rejects unknown identifiers with 422 | `backend/app/selector.py`, `backend/app/contracts.py`, `backend/app/main.py`; cases PV-02a–PV-02f |
| PV-03: different surfaces resolved different next activities (the recommendation said Reasoning while the saved plan held only Planning) | One resolver outcome now leads the plan: `resolved_next_step` records the recommendation, the schedule places that family first, and when the budget cannot fund it the plan states `resolved_family_over_budget` and offers the budget change required | `backend/app/plan_v2.py`, `backend/app/main.py`; case PV-03 across 4, 5, 8 and 20 minutes |
| PV-04: `personalization_smoke.py` failed because it launched against a genuinely stale plan | The fixture now asserts the stale-plan 409 first and then reconciles the plan before launching, so the authoritative tier guard stays intact and the fixture tests the real contract | `scripts/personalization_smoke.py`; case PV-04 |

Full regression after these changes: `plan_revision_smoke`, `personalization_smoke`,
`dashboard_smoke`, `backend_smoke`, `battery_smoke`, `coach_v2_smoke`, `coach_api_smoke`,
`coach_context_smoke`, `r1_rj01_rj02_smoke`, `r2_rj03_rj04_rj06_smoke`,
`r4_collaboration_claims_smoke`, `collaboration_v2_smoke`, `lifecycle_smoke`, the 40-case
manifest (40/40) and the recovery matrix (68/68) all exit 0.

Not claimed: the G0–G5 generalisation benchmark (scenario IDs, frozen split, comparators and a
reserved run) remains specification only; no participant, clinical or live-provider evidence
exists, and generated-prose helpfulness is not independently judged.

## Ledger

| ID | Finding / requirement | Owner | Implementation | Verification | Evidence | Remaining dependency | Acceptance |
|---|---|---|---|---|---|---|---|
| A0-1 | Preserve original judge report as baseline | SUP | done | n/a | `output/verification/challenge-judge-2026-10-21/REPORT.md` unchanged | â€” | Accepted as starting baseline |
| A0-2 | Reproduce the Memory-question/Reasoning-answer defect | SUP | done | done (failed on the current tree first) | `scripts/coach_context_smoke.py` reproduced the judge's exact reply before repair | â€” | Defect confirmed then closed |
| A0-3 | Persistent ledger and plan | SUP | done | n/a | `docs/CONNECTED_AGENT_PLAN.md`, this file | kept current each batch | â€” |
| B1-1 | Shared Twin context with observed/reported/suggested separation | SUP | done | done | `backend/app/twin_context.py`; evidence revision over canonical events | â€” | Automated pass |
| B1-2 | Subject resolution: explicit family â†’ current activity â†’ conversation â†’ next step | SUP | done | done | `resolve_subject`; ambiguous questions ask one clarification | â€” | Automated pass |
| B1-3 | Memory-context regression (judge finding 1) | SUP | done | done | `scripts/coach_context_smoke.py` PASS | â€” | Automated pass; human wording review pending |
| B2-1 | Groq and Gemini adapters behind one interface | W1/SUP | done | done with deterministic transports | `backend/app/provider_adapters.py`; `scripts/coach_v2_smoke.py` | live credentials absent | Automated pass; **no live provider call made** |
| B2-2 | Persisted turns with request identity and conflict rejection | SUP | done | done | `coach_turns` / `coach_conversations`; exact retry reuses one turn; conflicting payload â†’ 409 | â€” | Automated pass |
| B2-3 | SSE: acknowledgement â†’ evidence â†’ validated answer | SUP | done | done | `POST /api/coach/stream`; event order asserted in `coach_v2_smoke.py` | â€” | Automated pass; latency targets unmeasured without a live provider |
| B2-4 | Provider selection, per-provider consent, honest fallback labels | W2/SUP | done | done (isolated browser) | `frontend/src/redesign/companion/**` plus the `Companion.tsx` conversation tab; local provider rendered, Groq/Gemini reported not configured, hosted consent remained explicit (`output/verification/companion-browser-qa/REPORT.md`) | live credentials absent | **Software verification complete; live provider and human acceptance open** |
| B3-1 | Grounded action cards and evidence links from the backend only | W2 | done | done (isolated browser + deterministic API) | `CompanionCoach` renders backend-supplied evidence, explanation, strategy, next step and actions; Memory subject and unassessed state were browser-checked | independent quality review open | Human/helpfulness acceptance open |
| B3-2 | Quiet during scored work | W2/SUP | done | done (server/client smoke; browser panel opened during practice) | Route rejects baseline/reassessment with 409; client `quiet` disables input and aborts in-flight turns; no page/non-abort request errors in the journey | full timed matrix open | Software verification complete; full gameplay acceptance open |
| B3-3 | Speech for validated replies only | existing | done (pre-existing) | done (Conversation parity, browser) | `CompanionSpeech` unchanged and still gated on completed replies | audible acceptance pending | Human acceptance pending |
| B4-1 | `plan-v2` automatic revisions, idempotent | SUP | done | done | `backend/app/plan_v2.py`; `scripts/plan_revision_smoke.py` | â€” | Automated pass |
| B4-2 | Step lifecycle and completed-baseline-not-missing | SUP | done | done | lifecycle fields plus `superseded_steps`; a completed family is no longer `unassessed_baseline` | UI presentation of the lifecycle is still simple | Automated pass |
| B4-3 | Deliberate ranking, activity-specific durations, budget accounting | SUP | done | done | `rank_families`, `estimate_durations`, `budget_note` / `budget_adjustment` | â€” | Automated pass |
| B5-1 | `collaboration-v2` with v1 preserved and checkable credit | SUP | done | done | `backend/app/collaboration_v2.py`; server-held claim truths | â€” | Automated pass |
| B5-2 | Supported vs unsupported collaboration difference | SUP | done | done | wrong verdict 25, correct verdict 100, unreferenced text unassessed | â€” | Automated pass |
| B5-3 | Collaboration v2 explanation UI | SUP | done | done (build + v2 smoke; browser empty-state journey) | Collaboration page preserves v1 and adds server-held v2 verification claim, inspect-before-judgement controls and structured verdict submission; `collaboration_v2_smoke.py` covers canonical scoring and session scoping | saved-opportunity browser claim journey open | Software verification complete; browser claim journey open |
| B6-1 | Tidekeeper controls reachable in a timed window | SUP | done | done (six-viewport hit test, browser) | compact short-viewport rules plus narrow-width stacking in `hybrid.css`; built-stylesheet probe at 1280x720, 1024x768, 812x375, 375x812 and 1440x1000 reports both pads inside the viewport and zero horizontal overflow (`output/verification/luna-completion/supervisor/tidekeeper-timed-layout.json`) | **in-game timed-window acceptance still open**; the probe measures layout, not cue timing | Layout verified; gameplay acceptance open |
| B6-2 | Assisted-trial count and event-vs-attempt labelling | SUP | done | done (API) | `assisted_trial_count`, `interrupted_trial_count`, `count_note` on decisions and block state | UI already reads the field | Automated pass; browser check open |
| B6-3 | 40-scenario coaching suite | SUP | done | done (40/40, `scripts/r4_case_manifest.py`) | deterministic scenarios across `coach_context_smoke`, `coach_v2_smoke`, `collaboration_v2_smoke`; isolated browser journey in `output/verification/companion-browser-qa/REPORT.md` | full 40-case set and independent quality review open | Open |
| B6-4 | Recovery matrix across affected games | SUP | done | done at HTTP layer for all eleven activities (68/68, `scripts/r5_recovery_matrix.py`); per-activity browser fault injection still open | exact-retry/conflict/SSE/consent gate covered for coaching | per-game interruption matrix unchanged from prior work | Open |
| B7-1 | Live provider status honesty | SUP | done | done | `/api/coach/providers` reports `configured:false` without credentials; the smoke asserts no key is exposed | credentials unavailable | Reported honestly |
| B7-2 | Independent repeated 59-point review | SUP | open | open | â€” | after B1â€“B6 | External action |
| H-1 | Human visual/audible acceptance | human | n/a | n/a | â€” | â€” | Pending human |
| H-2 | Participant benefit / clinical claims | external | n/a | n/a | â€” | â€” | Out of scope |
| H-3 | Recording, publication, competition submission | human | n/a | n/a | â€” | â€” | Deferred release work |

## Deliberate behaviour changes

- `/api/preferences` with an unchanged goal no longer touches the plan or event history;
  dashboard-mode invariance is preserved (`dashboard_smoke.py`).
- A goal change now reconciles the active plan, so `dashboard.plan.latest` can differ from an
  earlier manual plan. `dashboard_smoke.py` asserts the documented revision chain instead of
  plan-id equality.
- `coach-v2` replaces the closed-string remote coach. `coach-v1` events stay readable and the
  `coach_smoke.py` boundary suite still passes against the v1 module.

## Fixture and error-path repairs

- `scripts/backend_smoke.py` now earns the tier-2 and tier-3 decisions canonically before
  exercising the tier-3 ceiling. The server guard remains unchanged, and the smoke passes.
- `/api/preferences` catches only expected SQLite/validation-shape failures during optional plan
  reconciliation and logs the exception with the session and goal context; it no longer hides
  arbitrary exceptions.

## Team and model availability

The plan specifies two GPT-6 Luna implementation workers. **No GPT-6 Luna model is available in
this runtime's delegation tool** (available: `deepseek/*`, `oaicopilot/glm-*`). Rather than
invent an identifier or claim a model ran, the learner-experience batch was executed by one
general-purpose subagent on the available model, and the backend/evidence batch was implemented
and verified directly by the supervisor. No Auto routing or hidden substitution is claimed.

## Verification commands

```
.venv\Scripts\python.exe scripts\coach_context_smoke.py
.venv\Scripts\python.exe scripts\coach_v2_smoke.py
.venv\Scripts\python.exe scripts\coach_api_smoke.py
.venv\Scripts\python.exe scripts\coach_smoke.py
.venv\Scripts\python.exe scripts\plan_revision_smoke.py
.venv\Scripts\python.exe scripts\collaboration_v2_smoke.py
.venv\Scripts\python.exe scripts\collaboration_smoke.py
.venv\Scripts\python.exe scripts\interaction_api_smoke.py
.venv\Scripts\python.exe scripts\battery_smoke.py
.venv\Scripts\python.exe scripts\personalization_smoke.py
.venv\Scripts\python.exe scripts\dashboard_smoke.py
.venv\Scripts\python.exe scripts\lifecycle_smoke.py
.venv\Scripts\python.exe scripts\r1_rj01_rj02_smoke.py
.venv\Scripts\python.exe scripts\r2_rj03_rj04_rj06_smoke.py
.venv\Scripts\python.exe scripts\r4_collaboration_claims_smoke.py
.venv\Scripts\python.exe scripts\r4_case_manifest.py
.venv\Scripts\python.exe scripts\r5_recovery_matrix.py
.venv\Scripts\python.exe scripts\r7_rejudge_fixes_smoke.py
cd frontend; npx tsc --noEmit; npm run build
```

Real-browser QA (isolated API on :8000 and Vite on :5173 with a disposable seeded database;
`NODE_PATH` must point at the bundled Playwright install):

```
node output/verification/r3-r5-browser/actions-and-claims.cjs <session-id>
node output/verification/r3-r5-browser/tidekeeper-hit-targets.cjs <session-id>
node output/verification/r3-r5-browser/speech-verification.cjs <session-id>
node output/verification/r3-r5-browser/speech-quiet.cjs <session-id>
```

All of the above passed on 22 October 2026 except the recorded pre-existing `backend_smoke.py`
tier-3 fixture. The browser scripts require the two isolated QA services and a seeded session
identifier; they never touch the primary learner database.



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
