# AI4BRAIN — Sprint 1–4 Master Execution Plan
**Baseline:** AI4BRAIN Competition POC Specification v0.3  
**Schedule:** October 18 – November 1, 2026  
**Mandate:** runnable competition proof of concept, not production MVP; no authentication or Supabase; strong adaptive personalization and auditable cognitive evidence.

## Milestones
| Sprint | Dates | Review proof |
|---|---|---|
| 1 — First Working Brain | Oct 18–21 | One real reasoning assessment generates evidence, provisional profile, graph link and adaptive decision |
| 2 — Full Cognitive Assessment | Oct 22–25 | Five exercises, 10–15-minute assessment, five-dimensional profile, cross-dimension personalization |
| 3 — Coach and Experience | Oct 26–29 | Evidence-backed AI coach, collaboration rubric, plan revisions, Analytics/RPG |
| 4 — Release and Submit | Oct 30–Nov 1 | Reliable POC + public repo + demo + report + slides + submission |

## Scope-control principles
1. Ship real scored tasks and reproducible events rather than mocked cognition.
2. Personalization is a P0 requirement; training a new model is not.
3. Keep baseline scoring separate from coached practice.
4. Every percentage is a provisional *task-performance index*, with an evidence count and uncertainty status; avoid clinical or general-intelligence claims.
5. SQLite is the canonical evidence store; Neo4j is the derived dual-brain graph.
6. Dashboard modes display the same data, never different scores.
7. Cut polish and optional bonus features before core challenge requirements.

---


# AI4BRAIN — Sprint 01: First Evidence-Driven Vertical Slice

**Specification baseline:** AI4BRAIN Competition POC v0.3  
**Sprint dates:** 18–21 October 2026 (4 calendar days; adjust to available developer capacity)  
**POC submission:** 1 November 2026  
**Sprint objective:** A user completes a genuine abstract-reasoning assessment and short adaptive practice session. The result is persisted as structured evidence; a provisional reasoning profile is created with uncertainty; a small two-brain graph links the person, task, dimension and teaching strategy; and a rule-based recommendation changes based on recorded performance.

## 1. User-visible sprint demonstration

1. Open AI4BRAIN without signing in.
2. See a high-quality welcome screen, a local-data/non-clinical notice, and a single **Start assessment** action.
3. Complete **EX-02: geometric pattern reasoning** — one practice item and six fixed scored items (2×2 patterns, four choices, one provably correct answer).
4. See an evidence-linked **Reasoning** result card: task index, correct/total, response-time summary, evidence count and **PRELIMINARY / HIGH UNCERTAINTY** notice. The other four dimensions show **Not assessed**, not zero.
5. Open a minimal **Brain Twin** graph view illustrating `Learner → DimensionEstimate → Reasoning` and `Exercise → assesses → Reasoning`, plus a coaching strategy from the Knowledge Brain.
6. Receive a next-action suggestion based on actual errors and evidence. If baseline is missing, the engine selects more assessment, **not** a fictitious weakness intervention.
7. Complete four training items of one comparable tier. A successful/unsuccessful window raises or lowers the next training difficulty; the UI shows the supporting rule and attempt IDs. If results are mixed, it holds the tier.

**Success statement:** `attempt → immutable event → scorer → profile snapshot → two-brain relationship → personalized next action`, genuinely executable in front of a judge.

## 2. Sprint backlog

| Ticket | Priority | Story / implementation task | Acceptance criterion |
|---|---|---|---|
| S1-01 | P0 | Initialize mono-repo: React/TS/Vite frontend, FastAPI backend, SQLite, one Neo4j Compose service | Single documented local startup; no login, no Supabase |
| S1-02 | P0 | Design 3 UI views: Welcome, Assessment, Brain Twin/result; responsive desktop-first | Clear states for start, loading, answer selection, completion and error |
| S1-03 | P0 | Define versioned `ExerciseConfig`, `TrialEvent`, `ProfileSnapshot`, `RecommendationEvent` contracts | Frontend/backend agree on IDs, scores, latency, mode, exercise version and evidence refs |
| S1-04 | P0 | Implement EX-02 baseline: practice + six deterministic, reviewed geometric pattern items, four options each | Every item has exactly one correct answer; scored mode has no hints |
| S1-05 | P0 | Persist trial events to SQLite with session ID and item version | Reload preserves the completed attempt and prevents accidental double submission |
| S1-06 | P0 | Implement deterministic reasoning scoring and profile snapshot | Six-item accuracy shown as a **task-performance index**; incomplete baseline is marked incomplete; every result references attempt IDs |
| S1-07 | P0 | Seed Neo4j Knowledge Brain and minimal Cognitive Brain Twin, then update from score snapshot | UI can inspect learner→estimate, item→exercise→dimension, strategy→dimension, with evidence link |
| S1-08 | P0 | Implement minimal recommendation logic for reasoning | Missing baseline→assessment; completed baseline→training at conservative tier; selected rationale stores evidence IDs and policy version |
| S1-09 | P0 | Implement four comparable training trials and difficulty controller | 3–4 unassisted successes→up one tier; 0–1 successes→down; 2→hold; event persists |
| S1-10 | P1 | Show one polished evidence-linked rationale and graph relationship exploration | Reviewer can see **why** the app chose the next action and what observation supports it |
| S1-11 | P0 | Manual demo smoke check and README | End-to-end run works after refreshing; seed history is explicitly labeled as sample data if used |

**Explicitly out of sprint:** other four exercise families, full baseline radar, RPG dashboard, LLM coaching, collaboration scoring, voice, forecasts, auth, Supabase, peer rankings, multiuser cloud operations, training any ML model, formal QA suite. Those remain in subsequent sprints, not removed from the complete POC scope.

## 3. Contract sketch

### Canonical attempt event (SQLite)

```json
{
  "event_id": "uuid",
  "learner_id": "demo-user",
  "session_id": "uuid",
  "event_type": "assessment_trial_completed",
  "phase": "baseline",
  "dimension": "reasoning",
  "exercise_id": "EX-02",
  "exercise_version": "1.0.0",
  "item_id": "reasoning-pattern-001",
  "item_difficulty": "baseline-medium",
  "response": { "choice": "B" },
  "evaluation": { "correct": true, "error_type": null, "scoring_version": "score-v1" },
  "timing": { "response_time_ms": 2450.5, "visibility_interrupted": false },
  "interaction": { "hint_count": 0, "restart_count": 0 },
  "recorded_at": "2026-10-18T12:00:00Z"
}
```

Generate the canonical correctness result server-side using the versioned item bank; do not trust the client's `correct` value. Record response timing client-side and label it approximate/browser-dependent. Exclude interrupted trials from scored baseline summaries.

### Core persistence tables

- `sessions`: `id`, `learner_id`, `started_at`, `status`
- `events`: `event_id`, `session_id`, `type`, `payload_json`, `created_at` (append-only; duplicate IDs rejected)
- `profile_snapshots`: `id`, `learner_id`, `scoring_version`, `dimension`, `index_0_100`, `uncertainty_status`, `evidence_ids_json`, `created_at`
- `recommendations`: `id`, `snapshot_id`, `policy_version`, `action`, `exercise_id`, `tier`, `reason_codes_json`, `evidence_ids_json`, `created_at`

### Proposed minimal API

- `POST /api/sessions` — create local anonymous session.
- `GET /api/exercises/EX-02?phase=baseline` — deterministic item list **without answer keys**.
- `POST /api/trials` — submit a trial; server evaluates and saves it idempotently.
- `GET /api/profile/demo-user` — latest provisional reasoning snapshot, evidence status and progress.
- `POST /api/recommendations/next` — select and persist next assessment/training action.
- `GET /api/graph/demo-user` — small evidence-linked graph representation for the UI.

## 4. Minimal two-brain schema

**Knowledge Brain:** `(:CognitiveDimension {id:'reasoning'})`, `(:ExerciseType {id:'EX-02'})`, `(:ExerciseItem)`, `(:TrainingStrategy)` with edges `ASSESSES`, `INSTANCE_OF`, `TARGETS`.

**Cognitive Brain Twin:** `(:Learner {id:'demo-user'})`, `(:DimensionEstimate)`, `(:ProfileSnapshot)`, `(:EvidenceSummary)` with edges `HAS_ESTIMATE`, `FOR_DIMENSION`, `CAPTURES`, `SUPPORTED_BY`.

SQLite remains the authoritative event store. Neo4j nodes are derived/inspectable views, not independent sources of truth. Keep the graph tiny and purposeful.

## 5. Adaptive rules in this sprint

- **Evidence gate:** If six valid baseline reasoning items have not been completed, recommend finishing the baseline. Do not rank a learner on partially completed evidence.
- **Post-baseline:** Recommend a short reasoning-training block; explain that six items produce a high-uncertainty, task-specific estimate.
- **Training tier:** For four unassisted, uninterrupted, comparable trials at the same tier: ≥3 successes means +1 tier; ≤1 means −1 tier (or hint/hold at minimum); exactly 2 means hold. Save the specific trial IDs, old/new tiers and rule version `difficulty-v1`.
- **Error response:** Wrong rotation pattern → visual rotation contrast; wrong shape-count rule → step-by-step count comparison. These are *candidate training strategies*, not diagnoses.
- **Profile history:** Training evidence and baseline evidence are tagged separately; do not inflate a fixed baseline score using coached practice trials.

## 6. UI requirements

**Welcome:** AI4BRAIN title, 15-second explanation of two brains, clear **Start** CTA, non-clinical and local-data notice.

**Assessment:** progress `Item 2 of 6`, one central puzzle, four option cards, selected state, next step, time/progress status. No dashboard distractions during testing.

**Result/Brain Twin:** `Reasoning: 4/6 · 67% task accuracy (illustrative)` and `High uncertainty / 6 scored items`; four unassessed dimensions as placeholders; `Why this score?` reveals six attempt records; `Next exercise` reveals recommendation reasoning. Minimal graph view should be readable on a laptop, not an enormous draggable canvas.

**Training:** action, current tier, a four-item block, and after the block a before/after tier and `Why did it change?` panel.

## 7. Four-day schedule

| Day | Focus | End-of-day evidence |
|---|---|---|
| **Oct 18** | Repository, UI shell, contracts, local FastAPI/SQLite | Welcome + exercise screen functional; local API running |
| **Oct 19** | EX-02 six-item bank, answer handling, event persistence, scorer | Complete baseline and refresh without losing attempts |
| **Oct 20** | Seed Neo4j two-brain graph, profile snapshots and `Why?` screen | See event-linked graph and provisional reasoning index |
| **Oct 21** | Recommendation rule, four-item training block, difficulty change, UX cleanup | Full 3-minute internal demo of the causal loop |

## 8. Definition of Done

- [ ] Fresh local setup runs with documented commands.
- [ ] A participant can complete the real six-item EX-02 assessment without authentication.
- [ ] Server evaluates correct answers; events survive refresh; duplicate submissions don't create two scores.
- [ ] Provisional task-performance index shows evidence count and high uncertainty, never a cognitive diagnosis or percentile.
- [ ] New snapshot is historically retained and traceable to attempts.
- [ ] Neo4j graph visibly connects dimension, exercise, strategy, learner and evidence.
- [ ] The system explains its selected next action with reason codes and evidence references.
- [ ] Four real comparable training attempts can cause a visible up/down/hold difficulty decision, while baseline accuracy stays unchanged.
- [ ] A broken LLM connection cannot break this demo (there is no LLM dependency in Sprint 1).
- [ ] Manual smoke walkthrough and error states work on laptop screen.

## 9. Known tradeoffs

- Six reasoning items support only a **preliminary exercise-specific score**, not a stable cognitive trait estimate. Do not give it a falsely narrow numeric confidence interval.
- Do not calculate an overall intelligence score or compare the reasoning percentage numerically against other cognitive dimensions.
- The graph's primary value is auditability and relation-aware strategy selection; the core event loop must still work if graph visualization is temporarily unavailable.
- This sprint does **not** demonstrate all official challenge layers yet. The other four dimensions, full dashboards and AI collaboration score are required later.

## 10. Sprint review script (3 minutes)

**0:00–0:30:** Open welcome and explain evidence-grounded reasoning assessment.  
**0:30–1:15:** Complete a short selection of real reasoning items, then show the saved baseline.  
**1:15–1:55:** Open the Brain Twin; inspect the evidence count, high uncertainty and linked Knowledge Brain strategy.  
**1:55–2:35:** Run a short adaptive training block and reveal a justified tier decision.  
**2:35–3:00:** Refresh and show history persists; explain what's next in Sprint 2.

**Sprint 2 starts only after this vertical slice is credible:** add EX-01, EX-03, EX-04 and EX-05 with the same event/scoring contract, then connect the full personalized selection policy.


---


# AI4BRAIN — Sprint 02: Complete Cognitive Assessment and Adaptive Profile

**Specification:** AI4BRAIN POC v0.3  
**Dates:** 22–25 October 2026  
**Depends on:** Sprint 01 functioning reasoning assessment, event store, scoring/history and minimal Neo4j connection  
**Goal:** Complete the 10–15-minute, five-dimension baseline and make the adaptation policy work across dimensions, not only reasoning.

## 1. Sprint review outcome

A new user starts without an account and completes five task families in approximately 12 minutes. Every valid trial is stored as structured evidence; each dimension gets its own *preliminary task-performance index* (not an intelligence or clinical score), visible evidence count and uncertainty status. The system chooses whether to assess or train based on evidence sufficiency and can recommend genuinely different next tasks to two contrasting learner profiles. It saves an actionable multi-step plan and its rationale.

## 2. Exact backlog (build order)

| ID | P | Ticket | Acceptance criterion | Depends on |
|---|---|---|---|---|
| S2-01 | P0 | Generalize shared `ExerciseShell` for five task plugins | All five use identical session, progress, pause/visibility and submission lifecycle | S1-03 |
| S2-02 | P0 | Implement EX-01 working memory | 3×3 light-up grid, practice + six scored trials at lengths 3–5, order captured and reproducible | S2-01 |
| S2-03 | P0 | Implement EX-03 attention/inhibition | 6 practice + 40 scored Go/no-go trials (30 Go/10 No-go); records omission, commission, correct trials and response windows | S2-01 |
| S2-04 | P0 | Implement EX-04 cognitive flexibility | 24 scored trials with approximately eight switch and sixteen repeat cases; stores cue, rule, answer, correctness and switch/repeat metrics | S2-01 |
| S2-05 | P0 | Implement EX-05 planning | 3 short, solvable move puzzles, shortest paths validated by BFS; logs legal/illegal moves and restarts | S2-01 |
| S2-06 | P0 | Implement versioned scorers per dimension | Scores computed on server from canonical item definitions; interrupted/incomplete assessments flagged, not silently included | S2-02–05 |
| S2-07 | P0 | Build full baseline flow | Intro → five exercises → completion screen, with elapsed time, clear instructions and no coaching/hints during scored trials | S2-02–06 |
| S2-08 | P0 | Historical five-dimensional Brain Twin | Immutable snapshots with five values, evidence IDs, statuses; missing data reads **Not assessed**; Neo4j summary relationships sync | S2-06 |
| S2-09 | P0 | Add evidence/uncertainty panel | Shows score meaning, sample size, limitations and why interval may not be available; no fictitious precision | S2-08 |
| S2-10 | P0 | Implement global `assess vs train` policy | Low/absent evidence returns assessment; usable evidence returns training; policy reasoning persisted | S2-08 |
| S2-11 | P0 | Implement dimension prioritization and plan builder | Weighted policy uses within-task performance gap, declared goal, recency, uncertainty; returns 2–4 steps with evidence references | S2-10 |
| S2-12 | P0 | Generalize difficulty controller and error mapping | Task-family success definitions and error codes configured; four comparable unassisted attempts cause up/down/hold | S2-11 |
| S2-13 | P1 | Graph explorer and baseline results polish | Knowledge dimension↔exercise↔strategy and learner↔estimate↔evidence visible, readable on laptop | S2-08 |
| S2-14 | P0 | End-to-end manual smoke check and contrasting demo profiles | Both profiles produce different, justified recommendations; all five scores survive reload; seeded records labeled **Sample data** | All |

## 3. Assessment specifications (do not silently change)

| ID / dimension | Baseline | Scoring concept | Evidence caveat |
|---|---|---|---|
| EX-01 Working memory | Six 3×3 spatial-sequence trials, two each length 3/4/5 | Correctly reproduced positions divided by positions presented; separately show longest fully correct sequence | Very short sample, affected by vision/input/familiarity |
| EX-02 Reasoning | Six nonverbal pattern items (from Sprint 01) | Correct / 6 × 100 | Not a validated reasoning capacity measurement |
| EX-03 Attention and inhibition | 40 Go/no-go trials (30/10) | 50 × (Go hit rate + No-go correct-rejection rate), each rate 0–1 | Browser/device timing, motor ability, class imbalance |
| EX-04 Flexibility | 24 sorting trials with about eight rule changes | 50 × (switch accuracy + repeat accuracy), each rate 0–1 | Few switch observations; instructions confound |
| EX-05 Planning | Three minimum-move puzzles with BFS-verified paths | Mean capped 100 × optimal/actual legal moves for completed tasks; zero if unfinished | Very little data; do not present a narrow interval |

These five indices are **not comparable norms**: an 80 in one cannot be called categorically better cognition than a 70 in another. Radar charts later will explicitly explain their task-family scales. For comparable fixed binary item sets, an illustrative Beta posterior can be shown only with its assumptions; otherwise use categorical **High uncertainty / Insufficient evidence**.

## 4. Implementation sequence by day

### October 22 — Two exercise families + shared shell
1. Refactor Sprint 01 EX-02 into reusable `ExerciseShell` / lifecycle contracts; do not change existing scoring.
2. Complete EX-01 working-memory component and its six fixed trial configs.
3. Complete EX-03 Go/no-go component and trial schedule; record trial metadata and visibility interruptions.
4. Manually play each from first instruction through persisted results.

### October 23 — Two remaining families + scoring
1. Implement EX-04 cue-guided switching, with nonambiguous color/shape choices.
2. Implement EX-05 legal move engine and BFS shortest-path answer verifier.
3. Implement server scorers for all families; version all rules and item banks.
4. Ensure each exercise can restore a prior session and cannot double-count duplicate events.

### October 24 — Full Brain Twin and assessment flow
1. Build five-exercise baseline orchestrator targeting 10–15 minutes total.
2. Save complete `ProfileSnapshot` with five independent indices and evidence/status fields.
3. Mirror derived relationships to Neo4j, with SQLite as canonical event source.
4. Build five-dimension results grid, evidence drill-down and uncertainty caveats.

### October 25 — Real multi-dimensional adaptation
1. Implement missing-evidence gate, weighted dimension selector, recency/goal/uncertainty inputs.
2. Produce a `TrainingPlan` of 2–4 ranked steps with `source_evidence_ids` and `policy_version`.
3. Extend four-trial tier change and task-specific error strategy mapping beyond reasoning.
4. Run two opposite demo profiles (flag sample data); inspect why each receives a different next action.

## 5. Backend contracts to add

- `GET /api/exercises` and `GET /api/exercises/{id}?phase=baseline|training` — item prompts only, no answer keys; versioned configs.
- `POST /api/trials` — canonical event evaluation and idempotent recording, across all families.
- `POST /api/assessment/complete` — compute/save profile snapshot after sufficient completed valid trials.
- `GET /api/profile/demo-user` — all five estimates, observation counts, uncertainty labels, recent snapshots, and event refs.
- `POST /api/recommendations/next` — `action=assess|train`, dimension, exercise, tier, reason codes, supporting evidence.
- `GET /api/plans/current` and `GET /api/plans/history` — current and previous 2–4-step training plans.
- `GET /api/graph/demo-user` — derived graph view for evidence explanation.

## 6. Definition of Done

- [ ] All five families run from instructions through submitted, persisted evidence.
- [ ] Complete baseline fits approximately 10–15 minutes for a representative walkthrough; tune stimulus durations rather than cutting evidence silently.
- [ ] Incomplete or interrupted trials are labeled and do not corrupt scored baseline.
- [ ] The five indices are reproducible from stored events, with score versions and explicit uncertainty.
- [ ] A new, unassessed user does not receive a fictitious weak-dimension label.
- [ ] The graph and snapshots retain historical evidence.
- [ ] Two meaningfully different profiles lead to different evidence-linked next actions.
- [ ] The training plan is persisted and can be compared to its preceding version.
- [ ] No clinical, personality, cross-population or intelligence claim is made.

## 7. Out of scope / contingency

LLM chat, full analytics/RPG, voice and growth prediction wait for Sprint 03/04. If time is tight, **retain functional scored trials for all five** but reduce animation/polish; do not drop a cognitive dimension or falsely inflate score confidence. This is a competition POC, not a clinical instrument. Minimal smoke walkthrough is required, not a dedicated QA program.


---


# AI4BRAIN — Sprint 03: AI Coaching, Collaboration and Personalized Experience

**Specification:** AI4BRAIN POC v0.3  
**Dates:** 26–29 October 2026  
**Depends on:** Sprint 02 five-dimension profile, evidence-linked selector, training plan and graph  
**Goal:** Demonstrate a living coaching loop in which observed errors lead to different interventions, natural conversation yields an explainable AI Collaboration Score, and one consistent Brain Twin appears in Analytics and RPG dashboards.

## 1. Sprint review outcome

User completes targeted practice, receives evidence-grounded personalized feedback, can question the coach and refine a solution, then sees updated history and an adjusted future plan. The AI cannot fabricate scores or override the adaptation policy. The user toggles Analytics↔RPG, and neither scores nor recommendations change. Dashboard includes radar, history curves, heatmap, goals and an interpretable collaboration indicator.

## 2. Exact backlog (build order)

| ID | P | Ticket | Acceptance criterion | Depends on |
|---|---|---|---|---|
| S3-01 | P0 | Create AI coaching adapter with text-only fallback | One provider/API wrapper, timeout/error handling; if API unavailable, deterministic evidence-linked message remains usable | S2-11 |
| S3-02 | P0 | Build `CoachingContext` DTO and retrieval | Context contains latest snapshots, evidence IDs, uncertainty, selected strategy, permitted actions; no unbounded raw history | S3-01 |
| S3-03 | P0 | Enforce structured LLM response | JSON/Pydantic result with observation, explanation, exercise ID/tier, rationale, caveat; reject unsupported IDs or claims | S3-02 |
| S3-04 | P0 | Implement task-specific coaching strategies | Memory chunking, reasoning rule contrast, Go/no-go clarification, rule-switch transition cue, planning subgoals | S2-12 |
| S3-05 | P0 | Implement natural chat and intervention recording | Message, question, hint, alternative and selected strategy persist; coach links each factual observation to evidence | S3-03/04 |
| S3-06 | P0 | Define collaboration opportunities rubric | Events for clarification, critical verification, iteration, autonomy, responsible use; avoid message-count scoring | S3-05 |
| S3-07 | P0 | Compute explainable 0–100 collaboration score | Document 20/25/20/20/15 formula, per-category observation counts, unobserved categories and availability rule | S3-06 |
| S3-08 | P0 | Build Analytics dashboard | Five-dimension radar, history line, activity heatmap, goals, uncertainty drill-down, reasoning for recommendations | S2-08 |
| S3-09 | P0 | Build RPG dashboard | Levels/XP from participation and milestones, skill-tree visualization, quests mirroring current plan, evidence/uncertainty access | S3-08 |
| S3-10 | P0 | Shared dashboard data contract | Both modes receive exactly the same profile/history/plan; switching mode changes presentation only | S3-08/09 |
| S3-11 | P0 | Complete `training → update → replan` loop | A scored training attempt creates new evidence and plan revision; baseline remains tagged and unchanged | S3-04, S2-11 |
| S3-12 | P1 | Add user-preferred dashboard experience | Local setting defaults to selected style, reversible instantly; never infer fixed personality type | S3-10 |
| S3-13 | P1 | Add user-controlled frustration/confidence check-in | Can be skipped, influences pacing/coach tone only; no facial emotion inference | S3-05 |
| S3-14 | P0 | Demo rehearsal and failure cases | Coach works with network failure; dashboard invariant; collaboration score says insufficient evidence when appropriate | All |

## 3. Collaboration score contract

Five categories and **proposed**, nonvalidated weights from brief: clarification 20%, critical verification 25%, iteration 20%, autonomy 20%, responsible use 15%. Per opportunity `o`, assign a transparent rubric outcome `0`, `0.5`, or `1` and supporting interaction/event IDs; for category `k`, `C_k=mean(valid opportunity outcomes)` on [0,1]. Display the overall score only if all required categories have an observed, meaningful opportunity OR adopt a documented partial-evidence policy that makes missing categories transparent and displays the result as provisional:

`overall = 100 × Σ(w_k × C_k) / Σ(w_k for observed categories)`

Always show coverage (e.g. `3/5 categories observed`), and **do not present a partial-coverage score as a fully comparable final score**. An alternative is 'Not enough evidence' until 5/5; MVP can choose one documented rule. No points for verbosity or asking meaningless questions. Controlled coach prompts should create legitimate opportunities rather than intentionally giving incorrect factual advice without disclosure.

## 4. Coach architecture and evidence boundary

Input: `CoachingContext { profile_snapshot_id, dimension, source_evidence_ids[], uncertainty, error_codes[], allowed_strategy_ids[], chosen_intervention_id, chosen_tier, policy_version, user_question }`.

Output: validated `CoachResponse { observation, feedback, exercise_id, tier, strategy_id, rationale, source_evidence_ids[], caveat }`.

Backend owns correctness, difficulty and plan; LLM is allowed to rephrase and propose **validated** strategies only. If hallucinated evidence or invalid exercise ID, fall back to rule-based evidence message. Store both the approved intervention and any rejected proposal in local logs if useful.

## 5. Dashboard specifics

**Analytics:** five task-performance indices (not normed cognitive abilities), radar with scale caveat, progress-by-date lines, attempt heatmap, evidence counts and uncertainty, goal progress, current 2–4-step plan, AI Collaboration Score and 'why this?' drilldown.

**RPG:** a character/skill tree presentation of five dimensions, quest cards from training plan, XP for valid practice/milestones (not based on cognitive diagnosis), completed achievements, optional streak, and quick 'view underlying evidence' link. **Scores and their uncertainty remain accessible and identical.**

A single `GET /api/dashboard/demo-user` response drives both modes. Compare the response before and after a UI theme switch: no changes to profile, history or plan; only a local `dashboard_mode` setting changes.

## 6. Suggested additional API routes

- `POST /api/coach/message` — validated coach output plus rationale/evidence refs, with graceful fallback.
- `POST /api/training/complete` — log training evidence, recompute task-specific training trend, save a revised plan if warranted.
- `POST /api/collaboration/events` and `GET /api/collaboration/score` — rubric events and score breakdown.
- `GET /api/dashboard/demo-user` — profile history, heatmap buckets, goal/plan data, collaboration metadata.
- `POST /api/preferences/dashboard` — optional local preference (no account system).
- `POST /api/checkins` — optional explicit confidence/frustration self-report.

## 7. Implementation sequence by day

### October 26 — Coach foundation
1. Implement AI provider wrapper and structured prompt/result schemas.
2. Retrieve only approved Brain Twin observations and Knowledge Brain strategies.
3. Validate or reject generated evidence claims; implement text fallback.
4. Get one real reasoning coaching interaction working.

### October 27 — Full coaching and natural collaboration
1. Cover five error-to-strategy mappings and intervention events.
2. Build natural chat UI with history and clearly separated training/assessment states.
3. Define collaboration opportunity and rubric events; persist them.
4. Show explanation of each collaboration component and evidence coverage.

### October 28 — Analytics and RPG dashboard
1. Build one dashboard DTO/API with five dimensions, uncertainty, history, goals and plan.
2. Finish analytics radar, line curves and heatmap.
3. Finish RPG quests, XP, skill-tree view and evidence link.
4. Verify toggling never modifies scores, difficulty or stored plan.

### October 29 — Evolving plan and integrated demo
1. Complete a post-training plan revision grounded in stored attempts.
2. Ensure collaboration updates arise from genuine conversations.
3. Try offline/timeout coach fallback, malformed output and limited evidence.
4. Rehearse a full 4-minute demonstration and log any missing features for Sprint 04.

## 8. Definition of Done

- [ ] Coach uses real exercise evidence rather than inventing outcomes.
- [ ] Training errors lead to at least two distinct defensible interventions.
- [ ] LLM cannot change a stored assessment score or policy selection.
- [ ] Natural coaching events produce collaboration evidence with a documented calculation and coverage.
- [ ] Plan revision is historical and explainable, including justified no-change decisions.
- [ ] Analytics has radar, progress curves, heatmap, goal and uncertainty indicators.
- [ ] RPG has quest/XP/skill progression tied to actual events, not fabricated intelligence improvement.
- [ ] Both modes display identical underlying profiles and preserve data during switching.
- [ ] Text-only flow operates if speech or LLM is unavailable (LLM has rule-based fallback).

## 9. Out of scope / contingency

No voice cloning, emotion detection from face, production messaging queues, live group rankings or predictive claims on one session. If time is tight, **keep the coach structured and explainable**, and reduce RPG visual effects rather than remove adaptive decisions, collaboration coverage or required dashboard views. Even without a live voice feature, all mandatory challenge layers should work.


---


# AI4BRAIN — Sprint 04: Competition POC Release and Submission

**Specification:** AI4BRAIN POC v0.3  
**Dates:** 30 October – 1 November 2026 (hard submission deadline on November 1)  
**Depends on:** Functional Sprint 01–03 baseline, dynamic profile, adaptive decisions, AI coach, collaboration score and dashboards  
**Goal:** Deliver a reproducible public competition POC and required submission artifacts, with a compelling 3–5-minute demonstration and honest scientific limitations.

## 1. Sprint review outcome

A fresh judge can obtain the public code, start the app using documented steps, complete real cognitive assessment trials, inspect evidence-backed recommendations and profile updates, switch between two dashboard modes and understand a clearly explained AI Collaboration Score. Submitted assets include public GitHub, demo video, maximum-8-page report and maximum-15-slide presentation, all in English.

## 2. Exact backlog (build order)

| ID | P | Ticket | Acceptance criterion | Depends on |
|---|---|---|---|---|
| S4-01 | P0 | Freeze scope, identify broken P0 paths | One release checklist; drop decorative features before mandatory ones | All prior |
| S4-02 | P0 | Rehearse complete fresh-session workflow | No dead end from Welcome → Baseline → Profile → Coach → Training → Replan → Dashboard | S4-01 |
| S4-03 | P0 | Stabilize persistence, graph and restart | Local restart/reload preserves events/history, SQLite authoritative if Neo4j temporarily unavailable | S4-02 |
| S4-04 | P0 | Verify adaptation scenarios and scoring | Up/down/hold, assess-before-train, two-profile divergence, incomplete evidence and LLM fallback demonstrable | S4-02 |
| S4-05 | P0 | Make privacy/safety behaviors visible | Local-data and non-clinical notice, no-camera/mic path, deletion/reset action, consent/retention described | S4-02 |
| S4-06 | P1 | Optional bonus: voice coaching | Only if core stable; permitted voice/stock browser TTS, off switch, full text fallback | S4-02 |
| S4-07 | P1 | Optional bonus: emotion-aware check-in | Explicit voluntary check-in with skip; no inferred biometric emotions | S4-02 |
| S4-08 | P2 | Optional bonus: uncertainty-aware projection | Show only after sufficient historical evidence; otherwise 'Not enough data' | S4-02 |
| S4-09 | P0 | Prepare credible demo personas/data | Any prerecorded/seeding explicitly labeled **Sample data**, real live attempt shown in video | S4-02 |
| S4-10 | P0 | Record and edit final 3–5-minute demo | Actual end-to-end behavior visible; audio/captions, no invented scores, within required duration | S4-09 |
| S4-11 | P0 | Complete technical report (≤8 pages) | Method, architecture, event/score/adaptation, uncertainty, ethics, results, limitations, reproducibility | S4-04 |
| S4-12 | P0 | Complete presentation (≤15 slides) | Judges can understand problem, differentiators, architecture, live evidence, methods and honest limits | S4-10 |
| S4-13 | P0 | Public repository and run instructions | README, setup commands, dependencies, `.env.example`, data reset, screenshots, license choice, no exposed secrets | S4-03 |
| S4-14 | P0 | Final artifact audit and submit | All links viewable without credentials, version/tag fixed, committee form submitted before deadline | S4-10–13 |

## 3. Hard deliverables and constraints

| Artifact | Official constraint | Minimum content |
|---|---|---|
| GitHub repository | Public at submission | Runnable source, README, data source notes, environment/setup, known limitations |
| Demo video | 3–5 minutes | Real scored trial, dynamic evidence/profile, personalized recommendation, coach/collaboration, dashboard switch |
| Technical report | Maximum 8 pages | Sections below; the general brief lists a report even though preselection list is slightly inconsistent |
| Presentation | Maximum 15 slides | Slides below and clear concise pitch |
| Language | English | All official deliverables and prepared defense |
| Submission | Before 1 November 2026 deadline | Verify committee form URL; the provided PDF does not show a usable link |

## 4. Recommended 4-minute-30-second video storyboard

| Segment | Timing | Show |
|---|---|---|
| Hook and problem | 0:00–0:25 | Personalized cognitive growth, not a chat-only tutor |
| Real assessment | 0:25–1:05 | One or more actual interactive reasoning trials and recorded evidence |
| Cognitive Brain Twin | 1:05–1:45 | Five dimensions, task indices, uncertainty, historical evidence |
| Two-brain differentiation | 1:45–2:20 | Knowledge graph connects observations → tasks → training strategies |
| Personalized choice | 2:20–3:00 | Two evidence profiles yield different next actions, with reason codes |
| Coaching + collaboration | 3:00–3:40 | User questions coach, resulting scored opportunity is explained |
| Training → revised plan | 3:40–4:05 | New attempt changes tier or plan for a documented reason |
| Analytics ↔ RPG | 4:05–4:25 | One data model, two presentation styles |
| Final claim/limitations | 4:25–4:30 | Explain prototype scope and evidence limits |

Use real score calculations. If an example uses preloaded historical activity, stamp **Sample data** on it. Do not promise 'increased intelligence' based on a short assessment.

## 5. Technical report outline (≤8 pages)

1. **Problem and requirements** — cognitive growth objective, scope and challenge mapping.
2. **System architecture** — Knowledge Brain, Cognitive Brain Twin, assessment, personalization and coach.
3. **Task design** — five task families, baseline samples, raw events, bias and device limitations.
4. **Scoring and uncertainty** — versioned indices, evidence counts, why indices are not population norms.
5. **Adaptive engine** — assess/train gate, selection heuristic, four-attempt tier controller and error-to-strategy mapping.
6. **Coaching, collaboration and dashboards** — LLM guardrails, documented rubric, two views of the same measurements.
7. **Demonstration and observed results** — real examples, sample-data labels, screenshots and failure-path handling.
8. **Ethics, limitations and future work** — consent, retention/deletion, scientific validation needs, bonus features.

This is a proposed page allocation, not proof that every section will naturally fit; prioritize within the eight-page maximum.

## 6. Presentation structure (≤15 slides)

Suggested 12 slides: (1) title/problem; (2) why a conventional tutor is insufficient; (3) end-to-end user journey; (4) two brains; (5) five cognitive exercises; (6) evidence and uncertainty; (7) adaptive personalization policy; (8) explainable AI coach; (9) collaboration score; (10) Analytics/RPG personalization; (11) demo/results and failure handling; (12) limitations, ethics and next steps.

## 7. Implementation sequence by day

### October 30 — Stabilize + optional feature gate
1. Freeze functional requirements and identify any broken mandatory workflow.
2. Run through live assessment, scoring, history, graph, recommendation, coaching, collaboration and dashboard switch.
3. Repair critical errors, unexpected reload behavior, missing-evidence cases and coach fallback.
4. Only if the above passes, add voice output or explicit check-in; cut speculative forecast if not grounded.

### October 31 — Package submission artifacts
1. Record final 3–5-minute demo and verify every on-screen value's source.
2. Finish the maximum-eight-page technical report and maximum-15-slide presentation.
3. Review public README and local Docker/FastAPI/Vite startup steps.
4. Remove API keys and test data that should not be public; tag a candidate release.

### November 1 — Final verification and submission
1. Fresh-clone or clean-machine startup using README; run a 5–10-minute manual demo path.
2. Verify video viewability, artifact length/page/slide limits, and repository permissions.
3. Confirm committee submission endpoint; PDF did not include an actual usable URL.
4. Submit ahead of deadline and retain proof/confirmation if issued.

## 8. Definition of Done

- [ ] All challenge-mandatory features are demonstrated at POC depth.
- [ ] Five-dimensional baseline produces task-specific estimates with history and uncertainty.
- [ ] Two-brain relationships and real personalized decisions are inspectable.
- [ ] AI coach has structured evidence and safe fallback, collaboration rubric documented.
- [ ] Analytics and RPG show the same scores; radar/progress/heatmap/goals accessible.
- [ ] No camera or voice permission is required to use the system.
- [ ] Local data reset/delete function works, and handling policy is documented.
- [ ] Public repository boots from instructions without hidden credentials.
- [ ] 3–5-minute video, ≤8-page report and ≤15-slide presentation all exist in English.
- [ ] The organizer's actual submission mechanism is verified and submission completed by November 1.

## 9. Scope-cutting order if time slips

1. **Cut first:** predictive growth, custom voice cloning, rich decorative animations, advanced onboarding.
2. **Cut next:** optional check-ins, hybrid layouts, elaborate Neo4j graph animations.
3. **Preserve:** all five basic scored exercises, historical evidence and uncertainty, assess-versus-train selection, adaptive difficulty, explainable coach, collaboration formula, required dashboard visualizations, privacy notice and runnable demo.
4. If Neo4j service fails during presentation, fall back to a read-only graph snapshot/edge list from SQLite, visibly identified as a fallback. **Never fabricate updates as if graph sync had succeeded.**

## 10. Release readiness checklist

- [ ] Fresh session and restart paths complete.
- [ ] No 'Not assessed' value rendered as zero; no fake percentile/diagnosis.
- [ ] Responses idempotent and scores recalculable from canonical attempts.
- [ ] No accidental API key exposure in GitHub or video.
- [ ] Demo historical data, if any, clearly labeled sample.
- [ ] Functional offline/error path for LLM or graph failure.
- [ ] All project artifacts in English and within official limits.
- [ ] The repository and media links open in a private browser window.


---
