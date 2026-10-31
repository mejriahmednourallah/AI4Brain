# AI4BRAIN connected-agent upgrade — implementation plan

Started 22 October 2026. This document is the execution record for the connected-agent
upgrade. Product requirements remain `docs/REQUIREMENTS.md` and the preserved POC/sprint
sources; the independent judge report
`output/verification/challenge-judge-2026-10-21/REPORT.md` is preserved unchanged as the
comparison baseline and is never overwritten by our own claims.

Target loop: **activity → recorded evidence → relevant explanation → strategy → learner-chosen
practice → outcome → updated plan and Brain Twin.**

## Confirmed decisions

| Area | Decision |
|---|---|
| LLM providers | Groq and Gemini adapters behind one interface, both implemented. |
| Companion | Contextual guide, persistent conversation, one dismissible invitation after a completed activity/block. |
| Scoring | Backend owns correctness, indices, eligibility, tiers and policy. |
| Baselines | Uncoached, separate from practice, quiet phases. |
| Learner control | Coach proposes; the learner chooses. |
| Storage | SQLite canonical, additive/versioned migrations; Neo4j derived and optional. |
| Presentation | Approved artwork, world names and companion identity preserved. |
| Verification | Real browser journeys, isolated QA data, honest limitations. |

## Starting evidence (Phase 0)

Reproduced against current source before any repair:

- `scripts/coach_context_smoke.py` fails on the current tree with the judge's exact prompt and
  quoted reply: `this task family has insufficient comparable baseline evidence ... reasoning
  needs more valid task-specific evidence`. Observed state: six Memory baseline trials saved,
  12.5% index. Cause: `backend/app/coach_service.py` builds its observation from
  `recommendation` (the next-step dimension) rather than the asked-about, observed family.
- Plan staleness: `backend/app/plan_service.py` only builds a plan on explicit request; no
  trigger reconciles the active plan after a baseline family completes or a canonical decision
  is saved.
- Collaboration scoring: `backend/app/collaboration_service.py` grants pass/accepted credit for
  structurally valid actions, so participation and reasoning quality are not separated.
- Tidekeeper pads: `frontend/src/redesign/hybrid/hybrid.css` places the response channels after
  the nine-position board with no short-viewport rule, so at 1280x720 they began below the fold.

## Batches

| Batch | Deliverables | Gate |
|---|---|---|
| 0 | Reproduction, preserved baseline, contracts, ledger, source identity | This document + `scripts/coach_context_smoke.py` |
| 1 | Twin context service, subject resolution, grounded local explanation | `coach_context_smoke.py` passes |
| 2 | Groq + Gemini adapters, persisted turns, SSE, provider/consent controls | `coach_provider_smoke.py` passes with deterministic transports |
| 3 | Grounded action cards, contextual guide invitation, speech lifecycle | Connected browser journey |
| 4 | Versioned plan revision triggers, step lifecycle, ranked sequencing, budget accounting | `plan_revision_smoke.py` idempotent |
| 5 | `collaboration-v2` evidence rubric preserving `collaboration-v1` | Supported/unsupported cases differ |
| 6 | Timed viewport ergonomics, reporting clarity, full recovery matrix, evaluation harness | Reproduced defects closed |
| 7 | Materials refresh, repeated independent review, final ledger | Boundaries explicit |

## Contracts (agreed before implementation)

- **Twin context** is derived from SQLite only and carries an `evidence_revision` hash plus a
  timestamp. It separates `observed` (recorded evaluations), `learner_reported` (learner
  statements) and `suggested` (coach strategies). Only `observed` may carry measured values.
- **Subject resolution** order: explicit family named in the question → current completed
  activity / selected results family → established conversation subject → next recommendation,
  and only for questions about what to do next. Ambiguity asks one short clarification.
- **Coaching contract** versions to `coach-v2`. Stored `coach-v1` events stay readable.
- **Provider contract**: `provider_requested`, `provider_used`, `model`, `fallback_reason`,
  `status`. No silent cross-provider forwarding; failure returns a labelled local fallback.
- **Conversation turns** use a stable `request_id` plus a canonical payload hash. Exact retries
  reconcile the same turn; conflicting payloads are rejected with 409.
- **Plan** versions to `plan-v2`; `plan-v1` snapshots remain readable and unmodified.
- **Collaboration** versions to `collaboration-v2`; `collaboration-v1` scores stay readable.

## Non-negotiables

Preserve primary learner data; destructive checks only on isolated copies. Neo4j is the only
authorized Docker workload. No secrets in output, no invented participant/clinical/benefit
claims, no fabricated browser or provider results. A build or schema pass is not visual,
audible, participant or human acceptance.

## Appended correction and completion plan — 22 October 2026

**Planning amendment only: no application fixes are claimed by this update.** This extends
Batches 0–7 and the two-Luna completion plan without removing their scope or rebuilding
working features. Acceptance claims contradicted by the latest audit are reopened below.

Evidence: `output/verification/challenge-rejudge-2026-10-22/REPORT.md`, its 59-point
`scorecard.json` and supervisor receipts. Phase A 69/100 and weighted readiness 57.4/100
are judging scores, not development-completion percentages. The human's 90–95% development
target remains an objective, not a certified result or promised competition score.

### Understanding and assumptions carried forward

- Finish evidence → explanation → strategy → learner-chosen practice → outcome → updated
  plan/Twin, including KittenTTS and the preceding plan's incomplete acceptance work.
- Backend/SQLite own facts, scores, eligibility, tiers and canonical evidence. Preserve
  immutable history, baseline/training separation, assistance/interruption exclusion and
  version compatibility. Never weaken policy or rewrite history to satisfy a fixture.
- Preserve primary data, approved artwork, companion identity and world vocabulary. Compare
  against the human-approved images; replacement concepts remain previews until approved.
- Reuse two GPT-6 Luna medium implementation workers in approximately three-task batches;
  supervisor independently reviews and integrates. This amendment launches no workers.
- No hosted credentials are assumed. Offline/mocked verification proceeds independently;
  live provider tests need authorized configuration and explicit hosted-data consent.
- Clinical/participant validation, publication, committee submission and final recording
  remain external/deferred. Neo4j is the only authorized Docker workload.

Decision: targeted contract repairs followed by end-to-end verification. A broad rewrite
adds regression risk; cosmetic-only repairs leave the reproduced contract failures intact.
All six hybrids and the separate crystal form are already integrated and must be verified,
not listed again as missing implementations.

### Reconciliation with the preceding plan

| Previous scope | Current position | Appended requirement |
|---|---|---|
| B1 Twin context | Original Memory subject failure repaired | Preserve; broaden all-family, ambiguity and missing-evidence cases |
| B2 providers/turns | Adapters exist; mocks passed; RJ-02/03/06 remain | Request reservation, factual/policy binding and role-aware history; live checks separately |
| B3 actions/invitation/speech | RJ-05 action integration missing | Working practice/strategy/evidence actions, invitation and Conversation KittenTTS lifecycle |
| B4 evolving plans | Reconciliation exists; RJ-04 tier mismatch | One authoritative tier for saved plan and launch; complete lifecycle/budget cases |
| B5 collaboration | Structured verdict present; RJ-08 detail/bias | Inspectable adjudicating evidence, balanced outcomes and meaningful credit |
| B6 ergonomics/recovery/40 cases | RJ-07 active-control overlap; final matrix incomplete | Actual timed controls, per-game recovery and individually reported 40-case suite |
| Original privacy scope | RJ-01 new records escape lifecycle | Complete export/deletion, retention and in-flight deletion handling |
| Earlier visual/game plan | New games integrated; fidelity unaccepted | Remaining mismatch registers, pages, companion, accessibility and final-tree journeys |
| B7 materials/review | Rejudge complete; new defects open | Close defects, refresh truthful materials and rerun independent judgment |

### R0 — checkpoint and reproduce (supervisor, three tasks)

1. Record source identity, owned QA services and disposable database. Preserve audit receipts;
   turn each confirmed counterexample into a reproducible regression without real provider traffic.
2. Reconcile status: implementation, automated pass, browser verification, reference comparison
   and human acceptance are separate. Inherited evidence is labeled; failed gates reopen.
3. Assign exclusive files before dispatch; define shared contract boundaries and batch reviews.

Gate: every RJ ID has an owner, reproduction and expected result. No data/scoring/artwork changes
are hidden inside setup.

### R1 — privacy and exactly-once coaching (backend worker + supervisor)

1. **RJ-01:** inventory learner-owned tables/JSON fields/caches/mirror references. Extend
   versioned export to coach turns, conversations, collaboration claims and complete plan
   metadata. Make deletion transactionally scoped, clear frontend retained state/audio, and
   prevent late in-flight replies from restoring deleted data. Preserve unrelated learners,
   event immutability protections and the database file. Check derived mirrors and TTS caches.
2. **RJ-02:** atomically reserve request ID plus canonical payload hash before generation or
   events. JSON and SSE share reserved/in-progress/completed/failed lifecycle. Replay completed
   exact retries and reject conflicting payloads before side effects. Define bounded restart/
   abandoned-request recovery. A remote timeout is ambiguous: guarantee one canonical result/
   event, but do not promise remote exactly-once execution without provider support.
3. Test populated new tables, complete exports, deletion while a reply is pending, reload,
   another learner's survival, sequential/concurrent/cross-endpoint retries, disconnect and restart.

Gate: the audit's lifecycle and retry counterexamples no longer reproduce; no targeted learner
rows remain after deletion and accepted immutable requests produce one canonical result/event.

### R2 — truthful coaching, full history and coherent plan tiers (backend worker)

1. **RJ-03:** bind generated facts to specific evidence fields, not a global bag of numbers.
   Server-render factual clauses, uncertainty, family, tier, strategy and allowed actions.
   Reject or replace conflicting generated explanations; schema compliance is not proof of
   factual truth. Keep suggestions labeled and provider/fallback status honest. Test legitimate
   numbers taken from wrong fields, wrong families/tiers, invented IDs and assistance claims.
2. **RJ-06:** include bounded correctly ordered learner AND prior validated assistant turns,
   with evidence revision/provenance. Exclude aborted, unvalidated, other-session and deleted
   turns. Recheck hosted consent each time; no silent forwarding. Verify cancellation and
   timeout behavior; distinguish acknowledgement latency from first useful content.
3. **RJ-04:** saved plan display and actual launch resolve the same authoritative current tier.
   Preserve versions/history. Cover UP/HOLD/DOWN, baseline gates, explicit world selection,
   goal changes, reload, late responses, active/completed/superseded steps, budgets and duration
   samples. Changing dashboard mode must not revise the plan or canonical evidence.

Gate: 12.5 cannot become a validated 100-index claim; no wrong next-step/tier can masquerade as
policy; follow-ups resolve prior assistant advice; promoted tier-2 plans and launches agree.

### R3 — companion actions, KittenTTS and Tidekeeper (experience worker + supervisor)

1. **RJ-05 actions:** wire backend-approved Open practice, Try strategy and Inspect evidence
   through supervisor-owned routing. Explain disabled actions; learner choice is required.
   Verify current/superseded suggestions, double activation, navigation, return and reload.
   Confirm the previous plan's single dismissible post-activity invitation is actually present.
2. **KittenTTS:** support Conversation as well as Quick answer using validated messages.
   Verify voice/settings persistence, play/stop/mute, one audio owner, cancellation, superseded
   reply, navigation/unmount cleanup, cold/warm synthesis, offline/model-cache behavior,
   missing model and text fallback. Silence/abort during scored or interrupted phases;
   no narrated hints. Preserve configured voice; human audition decides quality. Old timing
   measurements are reference evidence, not invented performance guarantees.
3. **RJ-07:** reserve space and fix Tidekeeper board/control overlap. During real active timed
   play verify every enabled pad center and near-edge hit target, actual clicks and keyboard,
   without scrolling/pause workarounds or timing changes. Required viewports: 320×812,
   375×812, 812×375, 1024×768, 1280×720 and 1440×1000.

Gate: explanation → chosen action → practice → saved outcome → updated plan works in-browser;
speech is owned/cancellable/quiet where required; all four pads accept intended live input.

### R4 — inspectable collaboration and 40-case quality suite

1. **RJ-08 backend:** deterministic supported, contradicted and genuinely insufficient cases;
   no constant-answer shortcut. Keep answers server-side, v1 history readable and the accepted
   20/25/20/20/15 weights. Explain partial credit; unassessed remains unassessed. This is a
   descriptive software rubric, not validated AI literacy.
2. **RJ-08 UI:** display the safe completed-task response, evaluation, assistance/interruption
   status and source needed to adjudicate the particular claim. Never expose answers to active/
   unseen scored items. Test unavailable/stale/mismatched records, inspect-before-verdict,
   all verdicts, persistence and the complete five-area aggregate.
3. **Supervisor evaluation manifest:** define expected facts/actions/policy before judging
   each output. Forty named cases: five family-specific explanations; five missing/partial/
   ambiguous/learner-report cases; eight factual/policy/assistance/clinical/ID attacks; six
   history/action/strategy/plan cases; six retry/conflict/concurrency/restart/cancel cases;
   five provider-consent/unavailable/timeout/malformed/status cases; five quiet/speech/
   lifecycle/export/deletion cases. Record input, expected/actual, individual verdict and source.

Gate: the displayed evidence supports adjudication; trivial verdict guessing fails the varied
set. Automated correctness, independently reviewed helpfulness and real-provider behavior
are separate results. Live subsets remain open until actually run; mocks cannot fill them.

### R5 — carry forward all remaining acceptance work

1. **Experience lane:** reconcile Memory/Planning/Reasoning/Attention/Flexibility mismatch
   registers against 02–06; compare Home 01, companion 07 and pages 07–15. Capture comparable
   viewport/state images and itemize open differences. Verify Motion/reduced motion, focus,
   keyboard, touch targets, long text, loading/empty/error/retry and footer clearance. Asset
   imports/geometry checks do not certify fidelity. Preserve final human visual acceptance.
2. **Canonical/gameplay lane:** derive expectations from requirements before outputs. Verify
   all five baselines, task-specific formulas, canonical UP/HOLD/DOWN and assistance/interruption
   exclusion; all six hybrid tutorials/completions; separate crystal version/records; evidence,
   export and deletion for every activity. Supplemental games must not alter frozen EX indices,
   canonical difficulty or XP through unintended paths. Do not fabricate participant history.
3. **Supervisor recovery matrix:** per game/phase cover pause/blur, resume, reload, rejected
   POST, accepted POST/lost reply, accepted POST/failed GET and retry. Use real browser fault
   injection for each distinct shared save/recovery path plus each game's state restoration;
   API regressions cover each game. Require immutable pending payloads, one canonical event,
   GET-only reconciliation after accepted saves, full timing windows and no dead ends. Repeat
   graph races, retained dashboard, world routing, four-attempt labels and modal focus.

Gate: final-tree coverage is explicit, severe implementation defects closed and residual items
named. Untested major paths cannot be called polish. Generalisation/growth claims remain limited
without credible separate evaluation; more games do not themselves prove transfer.

### R6 — reproducibility, materials and final independent review

1. Rehearse documented install/start/restart/stop and offline/model-cache behavior in an isolated
   environment. Distinguish clean setup from reused caches. Check local-mode egress, hosted
   opt-in, service ownership and model/asset attribution; no destructive host cleanup.
2. Refresh technical report, deck, requirement matrix, ledger and demo script to accepted code.
   Preserve brief limits, English, uncertainty and honest limitations; no invented team details.
   Prepare reviewable artifacts without publication, submission or final recording.
3. Supervisor reruns original RJ reproductions and 59-point judgment. Once code is frozen, reuse
   an authorized worker for an uninformed browser journey, then reproduce its findings. Feed
   new defects back to their owner and repeat affected checks; no worker self-acceptance.

Gate: source identity, screenshots, per-case results, limitations and remaining external gates
are linked. Owned QA services stopped and temporary configs removed. Human visual/audio,
expert accessibility/security/licence review and actual defense/release are separately tracked.

### Team, dependencies and reporting

| Owner | Lane | Shared boundary |
|---|---|---|
| Luna 1, medium | Game/hybrid presentation, companion UI/speech, collaboration display, reference comparisons | Supervisor owns App/task routing and shared shell/state |
| Luna 2, medium | Coach/provider/history, plan policy, collaboration evaluation, canonical fixtures | Supervisor reviews/integrates storage/lifecycle/event transactions |
| Supervisor | Shared files, source/QA isolation, reproductions, integration and independent acceptance | Review roughly three-task returns before dependent work |

R0 precedes dispatch. R1 persistence contracts precede dependent R2/R4 work. Independent
R3 Tidekeeper/layout work can run in parallel. R2 action/history contracts precede final
R3 integration. R4/R5 follow accepted repairs; R6 follows integrated checks. Assign speech
backend/UI files explicitly before parallel edits. Never silently expand file ownership.

Each return includes task IDs, changed files, before/after reproduction, final check results,
browser screenshots for UI claims, unresolved issues and next tasks. Supervisor reproduces
instead of accepting the worker's completed label. Preserve trusted old evidence without
counting it as a fresh final-tree pass.

State progression: planned → implementing → automated pass → browser verified → independently
accepted, with reference/human acceptance separate. RJ-01…RJ-08 start **open**. Existing Memory
context repair, restored chats and integrated new games remain implemented, not rebuilt.

Completion target: every major accepted feature reachable, no known severe implementation
defects, integrated recovery matrix checked, approved-reference comparisons performed, only
itemized minor finishes/external acceptance remaining. Do not certify 90–95% from test totals,
an elapsed timebox or a worker report. Completing development does not guarantee 90–95 jury points.

## Appended generalisation workstream — 22 October 2026

**Design proposal and implementation plan; not implemented or evaluated by this amendment.**
The human selected three tracks: unseen learner situations, unseen task variations and
unexpected constraints. No participants are available: prepare software evidence and a
future participant protocol. The latest direction is generalisation; TTS testing and provider
integration are deferred from this active workstream, not silently removed from the backlog.

### Understanding and success criteria

1. Demonstrate that the existing system makes coherent, safe decisions on new combinations
   of evidence, history, goals and constraints, rather than only the examples used to build it.
2. Demonstrate mechanical correctness and grounded guidance for reserved configurations of
   supported tasks. New artwork, repeated item IDs or random seeds alone are insufficient.
3. Demonstrate adaptation to changed budgets, availability and goals without bypassing
   assessment gates or silently changing canonical evidence.
4. Keep backend policy authoritative and maintain agreement between Twin, recommendation,
   plan, explanation and actual activity launch.
5. Preserve primary data, approved visuals, existing versions and non-clinical interpretation.
6. Report software generalisation separately from human improvement, retention and transfer.

The brief lists generalisation at 25% without a detailed operational definition. This is
our explicit evaluation proposal, not an invented official sub-rubric or a promise of extra
points. Lack of a participant study does not automatically defeat software generalisation;
synthetic cases likewise cannot prove human cognitive benefit.

### Approach and decision log

| Option | Benefit | Limitation / decision |
|---|---|---|
| More demonstration prompts and games only | Fast visible variety | Reject as primary evidence: bespoke examples may hide hardcoded behavior |
| Shared decision contract + reserved evaluation set | Auditable adaptation with existing app architecture | Recommended; independently define expected behavior and freeze versions |
| Train a new adaptive model / run efficacy study now | Could address later learning questions | Defer: no participant access or training evidence; not necessary for current software goals |

Proposed defaults: 72 named synthetic scenarios; 36 development and 36 reserved evaluation,
balanced across the three tracks. These numbers are coverage targets, not statistical power
or jury weights. Freeze the specification and split before implementation; freeze source and
provider settings before scoring. This is an auditable engineering split, not proof the
scenarios were absent from an LLM's pretraining. True external blind evaluation remains separate.

### Shared implementation contract

Add a versioned decision context/resolution boundary around the existing selector and planner.
Avoid a wholesale rewrite or a new autonomous LLM policy engine. Proposed objects:

- `DecisionContext`: evidence revision, session/learner scope, current canonical tiers,
  assessed/unassessed families, assisted/interrupted exclusions, goal, prior selections and
  versioned duration estimates. Record which fields are observed versus reported.
- `ExecutionConstraints`: explicit time budget, allowed activity IDs, supported input mode,
  provider/network availability and current scored/quiet phase. Read device capabilities from
  explicit supported settings; never infer cognitive traits from device type. Existing API
  boundaries apply: reject unsupported budget values or offer a documented alternative rather
  than silently clamping them. An explicit empty availability list means none, not all.
- `ResolvedDecision`: eligible candidates, chosen activity/version/tier or explicit no-fit,
  reason codes, evidence references, rejected alternatives with reasons, estimated duration,
  uncertainty, constraints revision and policy version. Distinguish estimated from guaranteed
  completion time. Backend actions reference this decision, not arbitrary generated prose.

Eligibility precedes ranking. Missing evidence remains missing; a stated difficulty is not a
measured score. A tight budget never authorizes coached baseline scoring. If no eligible
activity fits, offer learner-approved alternatives (short unscored practice where supported,
more time, another available activity, or defer), with honest tradeoffs. Do not invent a new
short scored baseline or violate the existing plan-step contract without an explicit versioned
change. Refresh decisions at launch when evidence/constraints changed; retain prior versions.

All surfaces consume the same resolved decision: selector, plan, Twin summary, coach allowed
actions and launch adapter. The LLM may explain it or propose a goal/constraint change; the
learner confirms that change before it affects policy. Do not let a fabricated conversation
claim override saved evidence, tier eligibility or selected activities.

### Track G-A — unseen learner situations

Implementation: compose evidence/history states rather than dispatching on learner persona
names. Retain task-specific facts and separate family discussed from next recommended activity.
Support sparse evidence and safe abstention instead of filling unknown indices with zero.

Development examples (illustrative; these are not reserved cases):

| Situation | Required behavior / acceptable decision set |
|---|---|
| Weak reported Memory, mostly assisted attempts, unassessed Reasoning, Reasoning goal, five minutes | Do not call the report a measured deficit; respect evidence gates; offer an eligible fitting assessment or labeled unscored practice/no-fit; cite supporting records |
| Strong completed families but incomplete Attention | Do not fabricate Attention strength/weakness; explain the assessment gate before targeted Attention training |
| Canonical tier-2 promotion followed by goal change | Preserve tier decision and history; revised plan and launch agree with current eligibility |
| Several interrupted attempts after valid baseline | Do not count interruptions as scored failures or silently erase baseline evidence |
| Old valid evidence plus a fresh contradictory learner report | Display both with provenance; offer comparable reassessment instead of rewriting the old score |
| Same aggregate index but different error patterns | Choose grounded strategy from task-specific errors, not an identical index-only explanation |

Perturb goals, recency, evidence completeness, assistance, interruption and activity availability
independently, then combine them in reserved cases. Expected outputs should specify invariants
and allowed decisions, not force one arbitrary sentence or assume a unique best activity where
policy permits several. Distinguish deterministic eligibility from judgment about helpfulness.

### Track G-B — unseen task variations

Use the existing versioned training/hybrid/crystal generators. Reserve valid combinations of
mechanical parameters, not just seeds producing the same board structure. Examples: Memory
sequence structure within supported limits; Reasoning distractor/rule combinations; Attention
target arrangement; switching-rule transitions; Planning obstacle/route interactions; supplemental
hybrid constraints supported by their contracts. Cover boundaries and invalid inputs too.

Before generation, define legal parameter space, independent expected results and difficulty
claims. Freeze item/config/version/hash and retain it with each attempt. Compare scorers with
independently authored worked fixtures and small exhaustive oracles (e.g. route legality and
optimality), not an expected answer imported from the production evaluator. Count unsolvable,
ambiguous or rejected generated instances as generation failures; report attempted denominator.

Add metamorphic checks only when validity is established: a spatial relabeling that preserves
legal moves should preserve optimal length; exact event retry should preserve outcome; an
interruption should not create a scored failure. Do not assume colors, timing, ordering or
distractor changes preserve cognitive difficulty. Equal mechanical correctness is not evidence
of psychometric equivalence or human transfer.

Frozen baselines are unchanged. Novel probes are explicitly versioned unscored evaluation or
supplemental records, excluded from EX indices, XP and difficulty decisions unless an accepted
contract explicitly permits that evidence. Unknown mechanics/configs are rejected or honestly
marked unsupported; the model must not invent a scorer, mapping or clinical interpretation.

### Track G-C — unexpected constraints

Compose sequences of changes, not just static snapshots: initial decision → learner changes
goal/time/available activity → recomputation → launch → save/reload → inspect resulting state.
Respect pending saves and active response windows; a new preference does not mutate an active
scored trial or reinterpret a saved attempt. Apply changes at an explicit safe boundary.

Required development cases include:

- Shrink a valid budget from 20 to 5 minutes; show what fits and what is deferred. Do not
  overbook or hide an automatic budget increase.
- Make the recommended activity unavailable, then make all activities unavailable. Offer a
  supported alternative or explicit no-fit; never silently restore the excluded candidates.
- Switch goal during practice or while a save is pending; persist/reconcile the save first,
  then derive the next decision without duplication or a dead end.
- Lose hosted connectivity: retain canonical evidence, use an honestly labeled local response
  and preserve non-network gameplay. This is not a successful live-provider quality result.
- Keyboard-only/input-limited mode: offer supported accessible controls or an honest
  limitation, without converting motor/input constraints into a cognitive weakness.
- Reload with changed constraints and a stale suggestion: revalidate at launch, retain history
  and explain any changed next step.

Device behavior overlaps robustness. Report it in that category too, but do not double-count
one viewport check as independent proof of cognitive/task transfer.

### Evaluation design and leakage control

Proposed fixture layout (files not created by this planning amendment):

```
tests/generalisation/dev/                 # 12 named scenarios per track
tests/generalisation/reserved/            # 12 separate scenarios per track
tests/generalisation/manifest.json        # IDs, versions, split, checksums, provenance
scripts/generalisation_eval.py            # CLI, disposable store, individual receipts
output/verification/generalisation/<run>/ # source/model/config identity, results, captures
```

Supervisor authors expected contracts from requirements before comparing app output. Use
isolated synthetic histories labeled `SOFTWARE_QA_SYNTHETIC`, never participant rows in the
primary store. Fix the clock, seeds, locale and settings; record browser/device conditions.
Parameter/seed sampling stays within approved generator boundaries. Do not tune on reserved
failures and then call the same set unseen: retain the first result, move exposed cases to
regression coverage, and create a new independently reserved set for later generalisation claims.
Same-workspace agents cannot guarantee technical secrecy: record who could access fixtures;
for stronger blinding, a human/external reviewer supplies cases after source freeze.

Compare three versioned systems on identical scenarios where feasible:

1. A simple fixed cycle over eligible activities, with the same safety/availability/budget
   gates. Do not weaken the comparator just to manufacture an adaptive advantage.
2. The frozen pre-generalisation app revision, to measure regressions and actual improvement.
3. The candidate shared-decision implementation.

Compare decision validity, goal/constraint satisfaction, evidence grounding, plan-launch
agreement and error-specific advice. Different wording is not automatically a better answer.
LLM fluency is evaluated separately, and an LLM must not be the sole judge of its own response.

Record per case: input and provenance; expected invariant/acceptable actions; actual decision,
plan and launch; cited records; score/assistance mutations; result; latency; source/model/config
revision; UI capture for browser claims. Separate local deterministic, mocked-provider and
real-provider runs. Repeated seeds or model responses are nested repeats, not independent people.

Proposed acceptance gates:

- Zero violations of canonical evidence, assistance exclusion, privacy, eligibility and immutable
  event identity across the declared set; any violation blocks acceptance, even if averages rise.
- Every valid mechanical fixture matches its independent oracle; unsupported/invalid configs
  fail explicitly. Report the complete generation/attempted denominator, not successes only.
- No silent constraint violation or wrong-tier/decision launch; all no-fit cases offer honest
  reasons. Report discretionary decision/helpfulness results per track and against comparators.
- Report first reserved-run failures, scenario counts and limitations. These proposed gates are
  engineering acceptance rules, not new official jury weights or population-level statistics.
- Where differences remain subjective, supervisor records rationale and ambiguity; do not
  invent a pass percentage or confidence interval from a small hand-authored scenario set.

### Implementation batches and owners

| Batch | Approximately three tasks | Owner / independent gate |
|---|---|---|
| G0 Specification and baseline | Freeze three-track invariants/split; capture comparator/source; draft fixtures and protocol | Supervisor; no final reserved expectations derived from implementation output |
| G1 Learner decisions | Shared context/resolution; error/evidence-aware decisions; all-surface contract regressions | Luna backend lane; supervisor checks G-A development cases and RJ-03/04 boundaries |
| G2 Task variations | Legal parameter manifest/version isolation; independent fixture/oracle checks; generator coverage and invalid cases | Reuse Luna backend lane after G1 shared files settle; supervisor reviews G-B |
| G3 Constraints and UI | Normalize explicit constraints; reconcile safely through plan/launch; show alternatives/no-fit/reasons | Backend + experience lanes with exclusive files; supervisor real-browser G-C replay |
| G4 Reserved evaluation | Freeze candidate; run all three systems; independently inspect failures and publish matrix | Supervisor, workers cannot mark their own acceptance; fresh external cases if available |
| G5 Protocol and demonstration | Prepare future human protocol; refresh honest generalisation narrative; rehearse surprise constraints without patching source | Supervisor/materials lane; evidence separate from participant benefit |

No agents are launched by this document. Use the already authorized two GPT-6 Luna medium
implementation lanes, not a new third worker. The experience lane owns presentation/input
adaptation and UI captures; backend lane owns decision/generator contracts and fixtures.
Supervisor owns shared routing/storage, test expectations, split integrity and independent
acceptance. Assign exact files before each roughly three-task return; avoid simultaneous
editing of selector, planner, contracts and App state.

Dependencies: G0 can start alongside repair reproduction. R1 privacy/request-identity and
R2 fact/history/tier corrections gate trusted integrated evaluation. G1/G2 can develop using
synthetic/local-only fixtures; G3 depends on stable G1 contracts and R3 activity-action wiring.
G4 follows accepted development cases and source freeze; final R6 review includes G4 evidence.
The existing 40-case coaching suite is complementary, not replaced or counted again as 72
new independent cases. No provider/TTS work is required to define this benchmark.

### Future participant protocol — prepared, not executed

Draft hypotheses, recruitment/consent, eligibility, privacy/deletion, session schedule and
analysis before recruitment. Obtain the appropriate human/institutional review before use.
Start with a feasibility pilot to assess instructions, completion, usability and dropout;
choose later sample size from the intended effect/precision and study design, not a convenient
number that is falsely called sufficient evidence of efficacy.

For a later learning study, separate familiar-task practice from reserved comparable task
performance and a delayed retention measurement. Counterbalance alternate forms and account
for task familiarity. Use a fair active comparison with matched contact/time/feedback where
feasible. Predefine primary outcomes, exclusions, missing-data handling and exploratory analyses.
Near-task improvement, far transfer and clinical benefit are distinct claims; do not infer the
latter two from game scores or a brief feasibility pilot. No participant data/results exist yet.

### Handoff and progress language

Deliverables at implementation completion: versioned shared decision contract; three-track
development/reserved manifest; independent oracle fixtures; comparator scripts; per-case
receipts and browser evidence; failure/regression register; future participant protocol; and
an updated jury narrative showing observed strengths and unresolved limits.

Allowed claim after successful software evaluation: "On the declared reserved software
scenarios, this version respected the tested evidence and constraint contracts; per-track
results and failures are attached." Disallowed: "proved cognitive growth", "generalises to
all learners" or an automatic jump from 6/25 to a promised score. Rejudge actual evidence using
the original category weights; do not convert benchmark completion into jury points.

## Execution record — R1–R5, 22 October 2026

This record is written after the work, not before it. Each line names the receipt that a
reader can re-run; no percentage is certified and no external acceptance is implied.

- **R1 complete (automated).** `scripts/r1_rj01_rj02_smoke.py` passes: exact replay, conflicting
  payload 409, in-progress 409, concurrent JSON/SSE 200/409 with one canonical event, deletion
  during a pending reply 409 with zero target rows left and the other learner intact.
- **R2 complete (automated).** `scripts/r2_rj03_rj04_rj06_smoke.py` passes: field-bound numbers,
  family/tier/strategy/evidence whitelists, ordered learner+assistant history from this session
  only, and plan/launch tier agreement under UP/HOLD/DOWN.
- **R3 complete (browser).** `output/verification/r3-r5-browser/actions-and-claims.json` shows one
  approved action recorded once, practice opened and the collaboration claim inspectable with a
  derived verdict. `speech-verification.json` and `speech-quiet.json` show real local KittenTTS
  playback with pause/resume/stop, clean disable and unmount, and no coaching speech while a timed
  cue is live. `tidekeeper-hit-targets.json` shows every pad hit target inside the viewport at
  320×812, 375×812, 812×375, 1024×768, 1280×720 and 1440×1000 with real mouse and keyboard input.
- **R4 complete (automated).** `scripts/r4_case_manifest.py` runs the named forty cases across
  family explanations, missing/partial/ambiguous evidence, adversarial output, history/action/plan,
  retry/concurrency/restart, provider states and quiet/speech/lifecycle; 40/40 pass and the
  receipt carries input, expectation, observation, verdict and source per case.
- **R5 complete at the HTTP layer (automated).** `scripts/r5_recovery_matrix.py` covers rejected
  save, lost reply, conflicting payload, failed GET, reload restore and interrupted completion for
  the five canonical families and the six hybrids: 68/68 pass.
- **R6 partially complete.** Reproduction and regression entry points are updated and the ledger,
  status and this plan record the current state. The documented start/stop lifecycle was rehearsed
  and a real pid-file parsing crash in both scripts was fixed; every reproduced finding was re-run
  against the current tree (`output/verification/r6-reproduction/REPORT.md`); the technical report
  and PDF, demo script, narration and requirement matrix were refreshed. Still outstanding: a
  clean-machine setup rehearsal with cold caches, a rebuilt and re-inspected pitch deck (the pitch
  builder cannot resolve its artifact-tool module here), per-activity browser fault injection, and
  a new independent review of the frozen tree by a worker that did not write the code.

Defects repaired by this pass are listed in `docs/SPRINT_STATUS.md` under the R1–R5 execution
result. The largest was RJ-07: the timed pads were genuinely unreachable at 1280×720 and clipped
at 1024×768, and the mobile viewports overflowed horizontally.
