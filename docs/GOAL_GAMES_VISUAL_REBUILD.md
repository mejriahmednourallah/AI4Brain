# Project goal: faithful illustrated game experiences

Established 2026-10-20 at the human's request. This file is the durable goal record because no goal service is available in this session.

## Goal statement (unbudgeted, persistent)

### Active completion target — human instruction, 21 October 2026

Bring the accepted AI4BRAIN development scope to **90–95% completion**, leaving only minor polish,
finishes and final human visual/audible acceptance. This supersedes earlier staffing preferences:
exactly two GPT-6 Luna implementation subagents, both at medium reasoning, work in reviewed
batches while the supervisor owns shared integration, independent verification and repairs.

All major accepted features must exist and be integrated: the five approved game experiences,
the separate versioned crystal Reasoning form, all six hybrid activities, Home/pages 07–15,
the approved companion and local KittenTTS. Preserve original POC functionality, primary data,
canonical scoring/evidence, assistance exclusions and safe recovery. Missing games, broken
interactions, unresolved canonical defects, unreachable controls and unverified critical recovery
are required work; they cannot be classified as remaining polish.

The percentage is an effort-based planning estimate, never a substitute for requirement closure.
Use `docs/LUNA_COMPLETION_LEDGER.md` for current tasks, review gates and evidence. Keep the active
goal until its actual completion conditions are satisfied; a completed worker batch alone is
not goal completion. Clinical validation, publication, final recording and committee submission
remain deferred. The earlier reference authority and data/environment constraints continue.

> Rebuild the five existing game experiences to faithfully reproduce the approved generated images using the available assets; implement the six pictured hybrid games as real playable experiences; verify every iteration in the browser, preserve canonical learner evidence and task integrity, and continue correcting visible and behavioral mismatches until the requested scope is complete and ready for the human's acceptance.

Nothing in this file declares the goal complete. Completion requires all five rebuilt experiences and all six new games to exist as playable, browser-verified experiences that match the image direction, with the documented engineering checks passing. Final human visual acceptance is the human's alone.

## Authority order

1. The human's instructions.
2. The human's approved generated images in `output/visual-design-review-2026-10-19/` (`02`-`06` existing games, `22`-`27` new games, plus `10`, `14`, `15`, `07`-`15` product pages).
3. Existing code, earlier status files, earlier acceptance claims, generic UI guidance.

A later human correction overrides any earlier AI acceptance claim. Rejected images 32/33 do not return.

## Non-negotiables while implementing

- Native task integrity under the visuals: deterministic backend generation and correctness, immutable event identity, exact saved retry, GET-only recovery, interruption exclusion, explicit phase/version/mode, baseline/training separation, no scored hints or leaked answers, honest unavailable/unassessed/high-uncertainty states.
- The art layer may be raster; logical coordinates, hit targets, keyboard/touch controls and accessibility stay native.
- Timed phases preload their stimulus assets; no loading or animation may shift cue onset or duration.
- Primary learner data and source documents preserved. Destructive checks only on isolated database copies. No `.env`, provider key or Neo4j password in outputs. Neo4j alone is authorized.
- One implementation writer at a time. No extra user-visible chats, no continuously running reviewer.

## Environment facts recorded at goal start

- Session tooling has no `imagegen` skill and no image-generation tool. Raster preparation is therefore limited to deterministic extraction, trimming, alpha-edge verification and composition from the approved sheets. No synthetic replacement art will be invented; if a required piece has no source, it is recorded as a missing asset and raised with the human instead of being faked.
- Isolated QA services on 8011 (API) and 5190 (Vite) were stopped at the end of the previous batch and must be restarted for browser verification.
- Pillow and NumPy were installed into the project virtual environment for read-only image analysis and deterministic cropping.

## Backlog

Phases are ordered; later phases are not an excuse to stop early. Each game row is only closed when its browser evidence and mismatch register rows are closed.

### Phase A - asset pipeline and shared visual foundation

- A1 Goal record and backlog (this file plus the session backlog table).
- A2 Reference/asset manifest: per sheet object inventory with bounds, padding, alpha statistics, prepared outputs, consumers, and explicit missing assets.
- A3 Deterministic preparation pipeline for reusable sprites (trim, pad, alpha-edge check, variant naming, source hashes).
- A4 Shared stage/composition contract: scene layer, ground-contact treatment, perspective wrapper, native interaction layer above the art, asset preloading before timed phases.

### Phase B - rebuild the five approved game experiences (in this order)

For each: inspect target -> prepare assets -> implement -> run the real browser -> capture the same state -> compare -> list concrete mismatches -> fix -> repeat.

- B1 Planning / Wayfinder's Garden (`02-game-planning.png`, sheets `16`, scene `38`).
- B2 Memory / Lantern Grove (`03-game-memory.png`, sheets `17`, `28`, scene `34`).
- B3 Reasoning / Pattern Atelier (`04-game-reasoning.png`, sheets `18`, `29`, `39`, scene `35`) **including a new versioned 3x3 crystal-count form** with its own generator, answer oracle, replayable seed and distinct outcome records; the existing 2x2 geometric baseline stays available and unchanged.
- B4 Attention / Signal Observatory (`05-game-attention.png`, sheet `19`, scene `36`) with the native signal registered inside the raster lens and heading-based onset verification.
- B5 Flexibility / Shifting Gallery (`06-game-flexibility.png`, sheet `20`, scene `37`).

### Phase C - shared coaching and review surfaces

- C1 Safe coach/replay surfaces reused by the new games, built on the existing graphite eye companion and real evidence contracts (no invented facts).

### Phase D - implement the six pictured hybrid games

Each requires a versioned configuration, deterministic generator/oracle, replayable seed, real records, assistance exposure and source links. Outcomes stay distinct from the five baseline indices; no clinical or validated-test claims.

- D1 HY-01 The Courier's Promise (`22-future-courier.png`).
- D2 HY-05 The Living Archive (`26-future-archive.png`).
- D3 HY-06 The Bridge Council (`27-future-council.png`).
- D4 HY-03 The Shifting Market (`24-future-market.png`).
- D5 HY-02 Tidekeeper (`23-future-tidekeeper.png`).
- D6 HY-04 Harbor Dispatch (`25-future-dispatch.png`).

Implementation order D1, D2, D3, D4, D5, D6 is the approved staging; all six are in scope.

### Phase E - evidence, registers and acceptance

- E1 Visual mismatch register per game: target, current capture, exact discrepancy, fix, recapture, open/closed.
- E2 Desktop and phone captures for active, review, paused, loading/failure and recovery states with truthful fixture/QA provenance.
- E3 Separate columns for implementation, integration, functional tests, browser verification, visual fidelity and human acceptance.
- E4 Regression evidence per game: solvability and valid alternatives, timing, assistance, deterministic replay, correct/incorrect/uncertain advice handling.
- E5 Engineering checks after each meaningful change (frontend build, structural suites, backend tests where touched).
- E6 Human acceptance request, with open items stated plainly.

## Current state pointer

Updated as work proceeds. The authoritative per-item state lives in the backlog table and in `output/verification/ui-rebuild/games/full-audit/VISUAL_MISMATCH_REGISTER.md`.

Iteration 1 (2026-10-20): Planning rebuilt on real approved artwork.

- Deterministic preparation pipeline added at `scripts/prepare-game-assets.py`; it crops approved sheet regions, trims to alpha bounds, pads, and reports outer-ring opaque pixels so a coloured or clipped backdrop is caught before use. Output goes to `frontend/src/redesign/games/assets/prepared/` and is recorded in `output/verification/ui-rebuild/games/asset-manifest.json` with source hashes.
- Eight Planning sprites prepared from sheet 16 (4 pavers, 2 mossy boulders, cobalt pawn, stone portal), all with an empty outer ring. Verified on a contrasting checkerboard: `output/verification/ui-rebuild/games/asset-previews/planning-sprites-checker.png`.
- `PlanningGame` now composes those sprites as raster layers over approved scene 38 instead of drawing SVG pavers, boulder, pawn and portal. Cells fill with packed stone, rows are foreshortened to 0.84 with a 0.93 back-row taper, cell size tracks `46cqw / columns`, and the board is anchored on the plateau at 42-43% height.
- Board geometry is unchanged logically: the same canonical rows, columns, walls, start and goal; `role="grid"`/`role="row"`/`role="gridcell"` semantics, arrow/WASD keys and the unavailable state all still hold, and the description moved to `aria-describedby` so no decorative text sits over the art.
- The legacy decorative intro strip is hidden inside the game shell for all five games.
- Verified in the mounted app at 1586x992 and 375x812, and through the isolated fixture harness at 3x3, 7x7 and 9x9.
- Open in Planning: shell header copy and progress dots, dock lobe shape, phone top-row clipping, shell height and footer overlap. Every other game and all six hybrid games are untouched so far.

### Restarting the isolated verification environment

```
# API against the isolated copy (from backend/)
$env:AI4BRAIN_DB="<session-state>/files/qa/qa.sqlite3"; $env:NEO4J_ENABLED="false"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011

# App shell proxying to that API (from frontend/)
npx vite --config vite.qa.config.mjs

# Isolated component fixtures (from output/verification/ui-rebuild/games/full-audit/)
node prepare-preview.cjs && ../../../../.venv/Scripts/python.exe serve-preview.py
```

