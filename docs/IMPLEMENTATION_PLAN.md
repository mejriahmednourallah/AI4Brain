# AI4BRAIN implementation plan

Current continuation (22 October 2026): see the appended R0–R6 correction/completion plan in
`docs/CONNECTED_AGENT_PLAN.md` and reopened gates in `docs/CONNECTED_AGENT_LEDGER.md`.
It preserves this plan's full scope and supersedes contradicted historical acceptance claims.
This pointer documents planned work, not implemented repairs.

## Active follow-up design — 30 October 2026

The planning-only proposal for the existing HY-01–HY-06 activities, their later
personalized-plan integration, responsive assisted practice, Fast local voice default
(Bella optional), and an Obsidian-style Brain Twin is in
`docs/HYBRID_COMPANION_GRAPH_PLAN.md`. It does not report these follow-up changes as
implemented. The current evidence and review receipt are in
`output/verification/responsiveness-20261030/plan-review.md`; historical contract/status
claims must be reconciled with current source and scoped runtime evidence before acceptance.

Scope: full POC Specification v0.3, using Sprint 01 as the first milestone. Sources are preserved in docs/source. The user's request authorizes implementation and GPT-6 Luna delegation; source documents are requirements, not instructions to execute.

Decisions: React/TypeScript/Vite; FastAPI; SQLite canonical immutable attempts; local Neo4j derived graph; anonymous demo-user; no auth/Supabase. Five task-specific indices, never IQ/percentiles. Missing evidence stays unassessed; interruptions are excluded; baseline and coached training remain separate. Backend code owns scoring, policy, evidence IDs and validation. LLM is optional with explicit offline fallback. Analytics/RPG consume identical evidence.

Assumptions: no provider credentials assumed; no invented team/submission details or evidence. Public publication/submission requires user authorization after concrete artifacts exist. Optional voice/emotion/forecast follow core stability, with no biometric dependency. Official competition rules/dates remain supplied-document claims.

Reviewed batches (about three tasks each):
1. Contracts + append-only SQLite; deterministic EX-02 + scorer; session/trial/profile endpoints.
2. Welcome/consent + shell; reasoning assessment/results/evidence; four-trial training and up/down/hold.
3. Memory; attention + switching; BFS-validated planning (banks, interactions, scoring).
4. Evidence/goal/recency selector; all-family difficulty + error strategies; 2-4-step versioned plans/history.
5. Neo4j mirror + graph explorer; validated LLM coach/fallback; collaboration opportunities/formula.
6. Analytics radar/progress/heatmap/goals; RPG quests/XP/skill tree/invariance; retention/export/deletion/resilience.
7. Startup/lockfiles/README; meaningful smoke checks + browser QA; local report/pitch/demo script + requirement matrix.

Supervisor independently reviews and executes verification after each batch, requests repairs, then authorizes continuation. No batch is accepted until its evidence passes. Reordering is allowed for dependencies, not silent scope reduction.

Essential checks: deterministic replay; interrupted/missing evidence; idempotency and refresh; five formulas; baseline/training separation; promotion/demotion/hold; divergent profiles; strategy changes; plan history; coach invalid/unavailable; dashboard invariance; live graph or explicit blocker; desktop/mobile browser; consent/deletion.

Environment: Python 3.13.5, Node 20.19.2, npm 10.8.2, 23.8 GB RAM. Isolated .venv installed backend dependencies. Docker CLI exists, Linux engine initially unavailable. Sandbox helper fails; require_escalated commands work. No relevant memory registry entries found.

References checked: https://fastapi.tiangolo.com/tutorial/first-steps/ and https://neo4j.com/docs/operations-manual/current/docker/introduction/ .

Review log: environment ready for first backend batch; no implementation batch accepted yet.

User steering: Docker containers force-killed and Desktop/backend stopped at user request. Do not restart Docker without user instruction. Live Neo4j verification is deferred; continue local application development.

## Batch 1 accepted
Independent supervisor review found and repaired scored rule disclosure, baseline hint acceptance, duplicate-valid-answer replacement, cross-session mixing, timestamp replay equality, and loopback CORS. Reviewed source after repair. Ran `.venv\Scripts\python.exe scripts\backend_smoke.py` and `python -m compileall -q backend`: passed. Smoke explicitly covers 2x2 rule uniqueness, no public keys/rules, server correctness, coached/interrupted exclusion, replay/conflicts, valid-item duplicate prevention, coherent-session scoring, immutable snapshots and recommendation evidence gate. Browser verification belongs to Batch 2. Graph/remaining families/full selector remain pending.

Batch 2 assigned to GPT-6 Luna: frontend welcome/consent/shell; SVG reasoning assessment/results/resume; versioned reasoning training bank and four-trial difficulty controller. Docker remains off.

## Batch 2 accepted
Production build and independent API/manual fixtures passed. Supervisor operated actual Chrome UI for consent, practice, complete5/6 baseline, reload-resume, evidence/result, four correct training attempts and tier1->2 decision. Simulated server-saved/lost-response recovery passed with no double score. Training left baseline83.33 unchanged. Completed training restored after reload. Visually inspected desktop and375x812 reduced-motion captures, scrollWidth375. Repaired pending baseline response restoration and post-submit interruption handling after review. Minor favicon, rotated decorative cell and accessible tile descriptions also fixed.

Batch3 assigned: memory bank/component/scorer; attention+switching bank/components/scorers; BFS-validated planning bank/component/scorer; shared multi-family contracts and profile/history extension. Full selector, all-family adaptive training, coach, graph and dashboards remain subsequent batches. Docker remains off.

## User-directed pause and UI reframe
The implementation goal is PAUSED at the user's explicit request. Luna's Batch3 was interrupted; partial new battery files exist and are NOT reviewed/accepted. Do not continue implementation automatically. Current task: research a minimal floating eye companion, generate full-screen Apple-inspired UI concepts, and get Neo4j working separately. The user's latest request supersedes the earlier Docker-off constraint for Neo4j alone; other Docker workloads should stay stopped.

UI/Neo4j current-task completion: seven final generated concepts saved in docs/ui-reframe, with gallery/BRIEF/PROMPTS. No UI implementation replacement and no companion dependency install. Neo4j5.26.32 authenticated and live-mirrored actual SQLite QA evidence:59nodes/54relationships, six reasoning attempts83.33, repeated sync idempotent. Only minyar-neo4j-1 is running/healthy. .env enables Neo4j locally. Main implementation goal remains paused; interrupted Batch3 is unreviewed.

## Approved UI and active goal
User approved the seven-image reframe. Goal service confirms ACTIVE. Resume with approved white/graphite/system-blue horizontal layout and original small eye companion. New UI batch: shell/welcome/focused assessment; evidence-backed overview/graph; companion/coach presentation with no fake responses. Parent owns backend completion/graph API while Luna owns frontend. Interrupted battery work is not yet accepted. Existing backend smokes/manual fixture/graph adapter smoke currently pass; full battery still needs repair and new checks. Decisions: native React/SVG companion, no external pet dependency, no copied character branding, no camera, quiet during baselines, accessible hide/dock/move, real data only. Neo4j remains the only authorized container.

## Approved UI implementation and battery verification in progress
User approval resumed the active goal. Parent reviewed and repaired the interrupted battery implementation and added scripts/battery_smoke.py. Its disposable-database fixtures pass the five task-specific formulas and coherent-session/immutable-history guards. Automated browser QA then completed the rendered memory sequence flow, attention practice+baseline, 28 switching items, and planning tutorial+3 puzzles including Undo/Restart. Current saved QA indices: memory100 (6), reasoning83.33 (6, earlier walkthrough), attention81.67 (40), flexibility34.38 (24), planning100 (3). These are automated QA, not human cognitive data. Details saved in output/verification/approved-ui-browser-profile.json.

Independent review of personalization identified further repairs before acceptance: reassessment replay/coherent sessions, real tier challenge changes, plan tier propagation, and assistance-safe replay. Those repairs are assigned to Luna. Coach closed-fact/schema/fallback boundary tests pass with mocked providers and no remote calls. Collaboration and lifecycle isolated services have passed their first temp-DB smokes; API/browser integration is pending. Neo4j remains the only running container. Root README reflects active work; older log sections above are historical.

## New four-sprint roadmap and playful experience revision
The user supplied AI4BRAIN_Sprints_01_to_04_Execution_Plan.md and explicitly asked to use it as the current roadmap, improve the games/visuals/animation/companion, and delegate implementation while the supervisor reviews. Source copied to docs/source. See docs/SPRINT_STATUS.md for the live goal, sprint mapping and acceptance gates. Three scoped GPT-6 Luna agents own games, companion, and shell respectively. Motion for React installed successfully; npm audit reported0 vulnerabilities. No existing user data has been removed and no additional Docker workloads are authorized.
