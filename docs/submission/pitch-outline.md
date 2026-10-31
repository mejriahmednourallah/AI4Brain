# AI4BRAIN pitch outline

> **Regeneration note (22 October 2026):** the narration and sources in `scripts/build_submission_pitch.mjs` were updated to the current contracts, but the deck on disk (`AI4BRAIN-Pitch.pptx`) still dates from 19 October. Rebuilding it requires the presentations runtime in this environment, which currently fails to resolve its artifact-tool module; regenerate and re-inspect the rendered slides before any external use.

**Target:** 8 minutes, 11 slides. Supplied brief limits and dates have not been independently verified. Use actual rendered application captures only after current browser acceptance; label supervisor-operated QA as software evidence. No team or participant claims are included.

| Slide | Time | Purpose and narration | Evidence |
|---|---:|---|---|
| 1. AI4BRAIN | 0:40 | Introduce the local software demonstrator and its narrow claim: a saved response can be traced to an estimate and next step. | `docs/submission/technical-report.md`; `README.md` |
| 2. A short, focused journey | 0:45 | Explain notice/consent, practice, five task families, evidence view and optional training. State that camera and microphone are not required. | `docs/source/POC_SPEC_EXTRACTED.txt`; current approved browser capture after review |
| 3. Five task-specific indices | 0:45 | Show the five denominators and formulas. Clarify that the indices are not cross-family rankings. | `backend/app/battery_scoring.py`; `backend/app/scoring.py` |
| 4. Canonical evidence flow | 0:50 | Trace browser response to server evaluation and canonical SQLite event, then profile, recommendation and optional graph mirror. | `backend/app/main.py`; `backend/app/storage.py`; `backend/app/graph_service.py` |
| 5. An evidence gate before personalization | 0:55 | Explain why missing evidence requests assessment instead of being scored as zero or called a weakness. | `backend/app/selector.py`; `backend/app/policy.py` |
| 6. Selection and progression | 0:45 | Explain selector weights and four-item up/down/hold decision with task-specific success rules. | `backend/app/selector.py`; `backend/app/difficulty.py`; `backend/app/strategy.py` |
| 7. Plans retain their reasons | 0:40 | Explain plan goal, budget, tiers, evidence references and retained history, and that the saved tier and the launch tier come from one policy source. | `backend/app/plan_v2.py`; `scripts/plan_revision_smoke.py` |
| 8. A bounded text coach | 0:40 | Describe the grounded local fallback, field-bound validation, per-request consent for remote use, honest provider/timeout labels, learner-chosen actions and optional local speech. No live provider call is claimed. | `backend/app/coach_v2.py`; `backend/app/coach_routes.py`; `scripts/coach_v2_smoke.py`; `scripts/r1_rj01_rj02_smoke.py` |
| 9. One profile, two presentations | 0:50 | Show Analytics and RPG as presentations over shared task evidence. XP and levels are engagement markers only. | `backend/app/dashboard_service.py`; `scripts/dashboard_smoke.py`; fresh browser capture after review |
| 10. Software checks and their limits | 0:50 | Summarize the forty-case evaluation, the sixty-eight-case recovery matrix, the six-viewport timed-control hit test and the rehearsed lifecycle. Label QA attempts as software tests, not participant results. | `output/verification/r4-forty-cases.json`; `r5-recovery-matrix.json`; `r3-r5-browser/tidekeeper-hit-targets.json`; `r6-reproduction/REPORT.md` |
| 11. Four sprints to a release | 0:20 | Close with the four-sprint route and remaining gates: per-activity browser fault injection, an independent review of the frozen tree, human review, clean-machine rehearsal, real recording and verified destination details. | `docs/source/AI4BRAIN_Sprints_01_to_04_Execution_Plan.md`; `docs/SPRINT_STATUS.md` |

The current UI pass has browser interactions across all five families, memory recovery, reasoning baseline, and desktop/mobile welcome and companion docking. A planning remount recovery repair needs a targeted rerun; dashboard UI integration and remaining coach/data-control flows still need review. Do not show the known intermediate welcome screenshot with the compressed layout. Current read-only Neo4j verification is recorded separately from the earlier authenticated write/read and idempotent-sync check.

