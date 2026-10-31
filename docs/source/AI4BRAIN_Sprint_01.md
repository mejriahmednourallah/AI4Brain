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
