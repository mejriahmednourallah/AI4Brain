# Hybrid plans, responsive companion and explorable Brain Twin

30 October 2026. **Design and investigation, not implemented repairs.** This adds the
missing integration to `CONNECTED_AGENT_PLAN.md`; its earlier open correctness and
recovery gates remain in force. Evidence directory:
`output/verification/responsiveness-20261030/`.

## Confirmed intent and decisions

The human confirmed this scope during this planning pass:

1. Make the six existing HY-01–HY-06 activities genuinely playable; verify their actual
   implementation rather than interpreting a catalog card as a finished game.
2. Introduce them later in the personalized plan, with a working plan-to-game-to-outcome loop.
3. Make the companion respond promptly and speak during practice. Actual help must be
   recorded as assistance; uncoached scored baselines remain quiet.
4. Make Brain Twin navigable like an Obsidian graph, with real connected records.
5. Preserve existing learner data, approved artwork, canonical scoring and historical events.

The human selected **Fast voice by default; Bella/KittenTTS remains optional**. Fast mode
uses local system speech where available and cached short companion lines. It introduces
no new paid speech service. Autonomous means bounded, useful prompts with learner control,
not unsolicited continuous conversation or hidden answers.

Assumptions to carry into implementation: normal plans finish the five baselines before
recommending hybrid enrichment; manual Hybrid Lab practice remains available with clear
consent/session entry. Crystal Reasoning stays a separate versioned activity, not a seventh
HY ID. Only eligible unassisted hybrid records may inform a separate hybrid-selection policy;
assisted attempts remain excluded from adaptive eligibility as required by `HYBRID_CONTRACT.md`.
No hybrid outcome becomes an EX score, EX tier decision, baseline coverage or XP.

## What the current investigation establishes

| Area | Current evidence | Consequence |
|---|---|---|
| Planner | `plan_v2.py` ranks five EX families, estimates EX durations and creates EX assessment/training steps; its UI/launch contract has no hybrid step | Waiting for more learner data cannot make an HY appear. A versioned integration is missing. |
| Games | Six activity implementations, catalog/API routes and separate stores exist; fresh browser audit finds all six cards and Crystal | They are not merely absent source files. Each mechanic and lifecycle still needs individual runtime acceptance. |
| Hybrid entry | Separate Hybrid Lab route; consent/session, artwork readiness and activity start precede controls | Test every gate and give actionable explanations instead of disabled or indefinite entry states. |
| Companion | `App.tsx` quiets the companion during every active hybrid; speech defaults to disabled with automatic replies off | Proactive practice speech is not an existing working default. It needs an explicit phase/checkpoint policy. |
| Text | One isolated local reply: 0.185s; one real, validated Gemini reply: 2.978s | These are samples, not percentiles. Do not blame all delay on model choice. |
| Current speech | 50-character Bella line: 27.593s cold, 4.887s warm. 199-character reply: 16.274s warm | Model loading plus full-utterance synthesis is on the critical path. A longer provider timeout does not fix it. |
| Browser-local speech | Headless Edge selected local English Mark; speech `start` event at 1.061s cold and 0.526s warm; total completion 3.562s and 3.044s | One click-triggered capability sample each; warm start is 26ms above the proposed 500ms target. `start` is not speaker-loopback timing or voice-quality acceptance. |
| Delivery | Backend builds the hosted answer before sending evidence; frontend speech waits for the entire WAV blob | SSE acknowledgement is not early meaningful content; a WAV response is not streaming playback. |
| Graph | Hand-positioned SVG renders representatives per type; actual records are in lists; record-open callback is unwired | Preserve the inspector but replace the overview renderer and connect evidence actions. |
| Data | Separate empty SQLite profiles on 8051/5195 and 8052/5196; no scored history seeded | Measurements and browser probes do not alter primary learner history. |

Timing evidence: `latency-samples.json`. Local-voice availability/start-event evidence:
`voice-capability.json`. Game and graph reports live in `games/` and `graph/`.
Treat historical “browser verified” entries as previous evidence, not acceptance of this change.
The top of `HYBRID_CONTRACT.md` also has a stale implementation-status statement; reconcile
it against the actual catalog and the new per-game audit before claiming completion.

Current bounded browser audit (isolated synthetic consented session, API 8052 / UI 5196;
`output/verification/responsiveness-20261030/games/browser-audit.md`): HY-01 completed its
tutorial (1/1); HY-06 completed route/advice interaction and recorded that the contradictory
advice was not justified by evidence; Crystal completed one prompt/action path. HY-02's
12-cue stream completed, but automation latency exceeded its 2.1s window so timed responses
were not verified (position 7/12, symbol 5/12 includes misses/defaults). HY-03 and HY-04
accepted initial actions but were left active. HY-05 restored active play state after reload
and reopening the lab, but its route reset to welcome and completion was not checked. Thus
HY-01/HY-06 and one Crystal answer have completion evidence; HY-02 timed-input behavior,
HY-03/04/05 completion, Crystal repeated rounds/reload, and HY-05 route continuity remain open.
Available screenshots are listed in the browser audit; these bounded checks do not establish
full playability, accessibility or recovery.

## Decision log and alternatives

| Decision | Alternatives considered | Reason |
|---|---|---|
| Repair and integrate existing six HY activities | Rebuild/rename them or add new concepts | Preserve requested mechanics, IDs, versions and saved attempts. |
| Plan-v3 typed activities with backward compatibility | Pretend HY is an EX family; add UI-only cards | Scheduling, launch, completion and replay must share a server contract. |
| Fast local voice default, Bella optional | Bella-only optimization; another paid speech API | The measured CPU synthesis delay is substantial; user explicitly accepted the local-voice trade-off. |
| Immediate canonical local response, optional validated Gemini explanation | Wait for a long hosted reply; expose raw generated tokens | Improve responsiveness while keeping factual validation intact. |
| Local 2D force layout with a DOM list/inspector | Another fixed representative map; immediate 3D/WebGL rewrite | Match the requested interaction without making geometry into evidence or adding needless scope. |
| Exactly two reused Luna medium workers and supervisor integration | Additional independent agents editing shared files | User preference, clear ownership and lower coordination/API overhead. |

## 1. Make each hybrid a complete activity

Use a catalog entry as a capability contract, not a promise inferred from a title.
Each entry has ID/version, mechanic, supported input modes, preparation states, real
duration estimate, assistance windows, completion conditions and availability reason.

| Activity | Minimum real mechanic to demonstrate | Completion/recovery proof |
|---|---|---|
| HY-01 Courier's Promise | Learn promises, walk/pick up/deliver, react to the bell/checkpoints | Saved ordered moves/deliveries; outcome reasons and evidence; resume the same attempt |
| HY-02 Tidekeeper | Actual n-back cue stream; independent position/symbol match and no-match actions | Every cue accepted once; omissions/rejections retained; interrupted streams excluded honestly |
| HY-03 Shifting Market | Encode shipment order, choose parcels, route by current rule, switch rule | Both order and routing evaluated; pending action retry; refresh cannot silently replay hidden sequence |
| HY-04 Harbor Dispatch | Encode manifest, route marked/unmarked arrivals, handle distractors/wave changes | Dispatch outcomes and timing; between-wave help; interruption/duplicate response handling |
| HY-05 Living Archive | Encode clues, place artifacts, commit and review the actual constraints | Constraint evaluation, assistance provenance, reconstructed saved board and immutable review |
| HY-06 Bridge Council | Propose a route, inspect advice and evidence, accept/modify/reject, commit | Feasibility and reasoning records; stimulus advice distinct from extra companion help |
| Crystal Reasoning | Separate 3×3 form with actual selectable answers and versioned evaluation | Own attempt/outcome namespace; no fixed baseline substitution |

For every activity verify the complete path: new profile → consent → entry → instructions →
explicit readiness/start → first real input → accepted save → outcome → review → return.
Also verify reopen, reload mid-attempt, a lost save reply and an actual failed request.
Use the existing intended mechanics/generators/oracles as the starting point; fix confirmed
missing behavior instead of rebuilding components that already work.

Lifecycle UI must distinguish `preparing`, `ready`, `playing`, `saving`, `recovering`,
`complete` and `failed`. Artwork/network failures get an explanation and retry. No timer
starts until required artwork/configuration is ready. Inputs lock only for their real
pending operation; one request never strands the activity. Preserve normal browser clocks.

## 2. Integrate hybrids into the personalized plan

The existing hybrid-v1 contract deliberately excludes hybrid records from the old
recommendation policy. The newly confirmed request changes **future scheduling**, not
historical scoring. Add a plan-v3 policy/addendum; preserve hybrid-v1 attempts and evaluators.

### Shared step contract

Keep stable step IDs, plan revision, status, estimate, reasons and evidence, but add a
discriminated activity reference:

```ts
type ActivityRef =
  | { kind: 'core'; exerciseId: CoreExerciseId; phase: CorePhase; version: string }
  | { kind: 'hybrid'; activityId: HybridActivityId; version: string; mode: HybridMode }
  | { kind: 'crystal'; formId: string; version: string };
```

Do not remove old EX fields until every reader is migrated. Read plan-v2 history through
a compatible adapter; persist a new plan revision rather than rewriting history.
Evidence references carry a namespace so hybrid events are never resolved as EX events.

### Eligibility and scheduling

- Missing baseline evidence keeps the assessment plan explicit. Manual practice stays available.
- Once the later-practice gate is met, rank eligible HY choices from declared task-family
  relevance, learner goal, available activities, time budget and exposure recency.
- Start with a documented deterministic hybrid policy and an appropriate catalog tier;
  never inherit an EX promotion as a hybrid tier or let an LLM assign difficulty.
- Keep at least the canonical resolved core next step where the budget allows. Add a
  hybrid enrichment step when eligible; rotate eligible HY activities across sessions,
  with an explicit “Explore more” route instead of stuffing every game into one short plan.
- Offer an optional hybrid focus preference and show *why this activity*, duration,
  assistance status and what remains unassessed. Do not claim transfer or clinical benefit.
- Explicit empty availability means no available activity. Persist constraints across
  goal changes, refresh and reconciliation; unknown activity IDs are rejected.
- Keep recommendation, saved plan, displayed tier and actual launch on one decision revision.
  Respect the existing unresolved constraint/decision-snapshot gates in the prior ledger.

### Launch, completion and persistence

Introduce a server-owned plan-step launch boundary that validates plan revision, session,
eligibility, catalog version and idempotency. It dispatches to the existing core, hybrid
or crystal attempt API and returns a typed destination. Reload/retry returns the same
active attempt; it does not silently start another one.

Link plan steps to canonical attempts through an additive namespaced mapping. Derive
completion from the accepted outcome, not a front-end click. Assisted completed practice
can finish a practice step with its label retained; it cannot satisfy an unassisted
performance/difficulty gate. Interruptions remain interrupted. Preserve before/after plan
history, export/deletion coverage and exact retry payloads. Update Home, Plan, Practice
entry, coach actions and review-return navigation together.

## 3. Make text and voice responsive

### Text path

Validate session/subject and capture one evidence revision first. Immediately send a
meaningful server-authored observation/next action; do not wait for Gemini to send that
content. Then request a short optional explanation from the configured Flash adapter.
Publish generated prose only after the existing validation boundary passes. A displayed
local response and a later Gemini explanation have explicit source/status labels.

Bound remote waits, cancellation and queue size. At the response budget, retain the useful
local answer and offer retry; do not leave a spinner for 45 seconds. Late results must be
cancelled or reconciled to their original request owner without unexpected speech.
Reuse the immutable request-ID reservation; no double provider call or double event on retry.
Cache only by consent, learner/session, evidence revision, subject, prompt and model version;
invalidate on changed evidence or deletion. No extra LLM judge call for ordinary interaction.

### Voice path

Add a single speech interface with `Fast local`, `Bella quality`, `Muted` and clear engine
status. A one-time **Enable companion audio** action unlocks playback under browser policy;
persist the learner's preference. Audio blocking or missing voices gets a clear text fallback.

Fast mode chooses an installed English voice with `localService === true`, waits for
voice availability correctly and never silently selects a remote system voice. Use
preloaded, versioned generic clips for common transition phrases; do not synthesize those
through a hosted LLM every time. Keep each utterance on one engine and disclose fallback.
Capability and browser start-event measurements are not human voice-quality acceptance.

Bella stays optional. Warm it in a bounded background task after opt-in, cache generic
utterances by text/voice/speed/model version and synthesize short complete sentences rather
than concatenating observation, explanation, rationale, follow-up and caveat into a long
spoken paragraph. Preserve the full written answer. Personalized caches must be private,
bounded and cleared on learner deletion. Do not block games, saves or plan navigation on
model loading or audio. Do not assume the newer KittenTTS streaming API exists in the
installed ONNX package, or that calling it removes first-chunk synthesis time.

### Autonomous companion policy

Create a shared phase/checkpoint signal instead of the blanket active-hybrid mute.
Allowed triggers: first welcome after opt-in, activity instructions/readiness, safe practice
checkpoint, completed attempt, recorded decision and materially revised plan. Deduplicate
by canonical transition/event ID; rate-limit and dismiss repeat invitations. Never launch
unbounded timer-driven conversations or repeated provider calls on React renders.

An informative hint records assistance **before** its text/audio is exposed. Use the
activity's server-approved assistance window; stale/deleted/wrong-owner events cannot speak.
Respect HY-01 pre-play/checkpoints, HY-02 pre-block/post-window, HY-03 boundaries, HY-04
between waves, HY-05 allowed encode/commit boundaries and HY-06 advice/commit checkpoints.
Advice that is itself the HY-06 stimulus is not rewritten as a companion verdict.

Scored baselines and active unassisted response windows stay quiet. Ordinary task
instructions and encouragement do not automatically count as solution help, but must not
disturb timed response measurements. Pause/stop, new context, visibility changes, route
changes, logout and deletion cancel both synthesis and playback. Reopening saved chat
must not replay old replies automatically.

## 4. Brain Twin with Obsidian-style exploration

Preserve graph-v2 IDs, directed relationships, evidence properties and optional mirror
status. Layout is a view of stored relationships, never new inferred psychological claims.

Use a 2D Canvas renderer with a bounded force simulation in a Web Worker (a small vetted
`d3-force` dependency is a candidate), plus the existing DOM inspector and an accessible
searchable list. Start from a seeded layout, preserve positions across refresh and stop
the simulation when settled, hidden or reduced motion is enabled. Benchmark this choice
against the actual graph sizes before installation/migration; an SVG variant is the
lower-complexity fallback for bounded small graphs. WebGL/3D is not required.

Required controls: pan, wheel/button zoom, fit/reset, node drag/pin/unpin, hover/focus
neighbor emphasis, labels that adapt to zoom, search, node-type/family filters and an
explicit global/local neighborhood toggle with depth. Selecting a node opens its real
record/evidence inspector; selecting an edge explains its recorded type/direction.
Provide keyboard selection/navigation, visible focus, touch controls and an equivalent
list. Show visible/total counts; never hide omitted nodes behind representative stand-ins.

Connect the currently missing open-evidence callback. Add plan-step/hybrid-attempt/outcome
nodes only through explicit canonical adapters and namespaced references. No client writes
layout positions into canonical evidence. Keep stale-request guards and selected-node
identity; handle deleted/filtered-out nodes gracefully.

Do not synchronize the entire Neo4j mirror on every local graph read. Build/reuse a graph
snapshot keyed to evidence revision and apply filtering/paging before expensive work.
Mirror updates are derived background work with honest pending/degraded status; the app
must stay usable while Neo4j is unavailable. No unrelated Docker workloads are required.

## Execution order and ownership

Reuse exactly two `gpt-6-luna`, medium workers. Review roughly three scoped tasks per
worker per batch; do not advance a dependent batch from screenshots or claimed test counts.

| Batch | Luna A: game/front-end ownership | Luna B: backend/data ownership | Supervisor integration/review |
|---|---|---|---|
| 0 — current investigation | Reproduce all HY launches; exercise mechanics/lifecycles; produce per-game evidence | Graph/planner contract audit; current DTO/renderer limits; migration/risk report | Isolated runtime, Gemini/TTS timing, Serena references, RTK inspection and confirmed design |
| 1 — playable foundation | Repair entry/session/readiness; repair actual game input/mechanics; finish review/reload behavior | Catalog capability validation; pending-action/completion recovery; assistance-window/oracle acceptance | Shared state/typed contracts; independently replay all six before planner rollout |
| 2 — plan integration | Typed HY/crystal plan cards; entry/resume/return views; responsive and keyboard paths | Plan-v3 eligibility/budget ranking; idempotent launch linkage; outcome-driven reconciliation/history | Own App routing and shared adapters; inspect plan→game→outcome→revised plan end to end |
| 3 — responsive companion | Context/checkpoint signals in game views; assistance affordances; cancellation/accessibility integration | Early canonical response; bounded provider path; local speech cache/warmup/ownership backend | Own companion controller/Fast browser speech; verify opt-in, provenance, latency and no scored coaching |
| 4 — graph | Force-layout viewport/worker; search/local/global interaction; accessible inspector/list | Revision snapshots/filtering; asynchronous mirror lifecycle; canonical plan/HY graph adapters | Review performance and semantics; connect record-open actions and run degraded/race scenarios |
| 5 — final repair | Fix browser/interaction findings; finish viewport checks; clean status documentation | Fix canonical/lifecycle findings; schema/export/deletion checks; deterministic regressions | Blind user journey, independent saved-record checks, final repair and user acceptance |

Exclusive files are assigned at each batch before editing. Luna A owns
`frontend/src/redesign/hybrid/**` then its new graph components. Luna B owns explicitly
assigned backend plan/hybrid/speech/graph modules. The supervisor owns `App.tsx`, shared
front-end DTO/client adapters, companion front-end state and final integration. Agree
contracts before concurrent edits; shared persistence migrations are reviewed first.

## Acceptance gates and performance targets

Targets below are proposed acceptance budgets, not achieved benchmark results. Record
hardware/browser, cold/warm cache, graph size, network condition, raw timings and failures.
Use at least 20 local interaction samples and separate cold runs; do not label tiny
hosted-provider samples as reliable p95 statistics.

| Gate | Required evidence |
|---|---|
| All six playable | One actual browser completion and reload/resume path per HY; Crystal separately; no empty container or perpetual loader accepted |
| Plan integration | Every HY can become eligible under an explicit later-practice fixture; fresh/incomplete profiles, small budgets, empty/unknown availability and stale plans behave coherently |
| Actual launch | Plan card launches the exact saved activity/version/tier; reload resumes the same attempt; one completion updates that step once |
| Input/save correctness | Real pointer and keyboard/touch actions; immutable failed/retried payloads; no duplicate evidence; interruption/exclusion labels preserved |
| Canonical isolation | Frozen EX baseline IDs/values, EX tiers and XP unchanged by HY or Crystal; separate assisted/unassisted outcomes; all evidence resolves |
| Meaningful text | Local grounded response target ≤500ms p95 on reference machine; immediate visual acknowledgement ≤100ms; useful fallback at the bounded hosted deadline |
| Fast audio | Cached prompt target ≤300ms warm; local-system start-event target ≤500ms warm and ≤2s first opt-in on reference browser; no claim of speaker-loopback accuracy |
| Hosted explanation | Target normal validated response ≤5s; explicit local fallback by 8s for slow requests; no pending spinner indefinitely and no unvalidated streamed prose |
| Audio ownership | Zero overlapping/stale replies; stop/context change target ≤100ms; no baseline or active unassisted-window audio; help exposure recorded before first content |
| Game responsiveness | Typical control response target <100ms while TTS/provider work runs; task clocks and response windows unchanged |
| Graph interaction | Visible graph ready target ≤1s warm for 1,000 nodes; interaction target ≥30fps on reference hardware; test 16/1,000/5,000-node fixtures and label size-dependent limits |
| Responsive/accessibility | 320px portrait, 375px, 812×375, 1280×720 and desktop; center/edge hit-tests, keyboard navigation, reduced motion and a graph list alternative |
| Failure conditions | API 500/503, lost accepted reply, offline assets, unavailable OS voice, autoplay denied, concurrent speech, provider timeout, stale graph response and Neo4j outage |
| Lifecycle/privacy | New schema remains backward compatible; own learner export/deletion covers plan links and caches; secrets server-side; primary data preserved |

## Final review and definition of done

Deliver a per-activity acceptance ledger, before/after latency distributions, actual browser
screenshots/traces, plan and event reference receipts, graph interaction recordings and
relevant build/regression results. Fix and replay discovered defects before closing a gate.
Show the user both voice modes and the new graph for human sound/interaction acceptance.
Do not report a percentage of total app completion from passing tests or from this plan.

This pass implements no product behavior. Next is the reviewed implementation sequence,
starting with playable hybrids and the shared plan contract—not a cosmetic graph pass first.

## Primary technical references

- [Obsidian graph interactions and settings](https://obsidian.md/help/plugins/graph)
- [Local versus remote system voices](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService)
- [Voice-list availability event](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/voiceschanged_event)
- [d3-force and renderer separation](https://d3js.org/d3-force)
- [Gemini streaming](https://ai.google.dev/gemini-api/docs/text-generation#streaming-responses)
- [KittenTTS upstream APIs and streaming limits](https://github.com/KittenML/KittenTTS)

Serena was used selectively for the Python coach/synthesis call chain; TypeScript files
were read through targeted searches because the active project has a Python language
server. RTK was invoked explicitly for verbose Git inspection. No tooling savings are
claimed as measured API cost reductions; automatic RTK interception stays disabled.
