# First-time-user audit and repair loop

Requested by the human, 21 October 2026. This is an execution plan, not an acceptance claim.

## Roles and sequence

1. Fresh GPT-6 Luna medium auditor, with no inherited conversation, previous bug list,
   source inspection or answer keys. It uses visible instructions and actual browser controls.
   It reports problems and uncertainty without editing application code.
2. Supervisor independently reproduces each reported issue and separates functional defects,
   usability confusion and visual preferences. Screenshots alone do not prove a dead control;
   native clicks, keyboard actions and resulting state must support that claim.
3. Reuse an existing implementation worker for approximately three confirmed repairs at a
   time, under exclusive file ownership. Supervisor owns shared routing/state integration.
   Do not change frontend code while the discovery audit is still using it.
4. Supervisor reviews changes, runs checks appropriate to the change, and repeats the exact
   browser reproduction. The auditor revisits repaired paths without being coached through
   them. Keep unresolved issues and untested surfaces visible in the final report.

## Coverage

Fresh onboarding; five core games; all six hybrids; separate Crystal Reasoning; wrong choices;
keyboard and pointer; pause/resume; leave/return; reload; results and practice progression;
Home, Analytics/Quest, plan, Evidence, collaboration, privacy, companion and speech controls.
Desktop 1440x1000, mobile 375x812 and 320x812, landscape 812x375. Auditing software behavior
does not confer human visual/audible, assistive-technology or clinical acceptance.

Every finding records ID, severity, category, visible activity/phase, viewport, exact steps,
expected/actual behavior, screenshot paths, repeatability and confidence. Record positive
coverage and exclusions as well as failures. Difficulty solving a task is not itself a bug.

## Isolation and evidence

- Browser origin: `http://localhost:5192/` (fresh origin).
- API: loopback 8031, owned by this audit only; PID and shell handles recorded at startup.
- Disposable database: `output/verification/naive-user-audit-2026-10-21/naive.sqlite3`.
- Neo4j and remote coaching disabled for this QA process; primary configuration/data untouched.
- Evidence: `output/verification/naive-user-audit-2026-10-21/`.
- No new generated asset integration: the human and approved images remain visual authority.
- Stop owned services and remove the temporary Vite QA config at the end; retain evidence.

## Repair order

Blocked journeys/data correctness -> broken controls/recovery -> confusing instructions or
feedback -> responsive/accessibility defects -> reference-aligned visual fine-tuning.
Never certify overall completion from a passing build or from an implementation worker's report.
