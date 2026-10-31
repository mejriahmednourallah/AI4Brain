# Submission artifact QA and remaining release gates

Updated: 19 October 2026. These records cover local artifact construction and software evidence only. They do not establish a participant study, clinical validity, public release or external submission.

## Current artifacts

| Artifact | Local check | Result and scope |
|---|---|---|
| `AI4BRAIN-Technical-Report.pdf` | ReportLab build, `pypdf` page/text check, Poppler render and page-by-page visual inspection | PASS: 3 A4 pages, under the 8-page limit. All three rendered pages were inspected; tables, headings, margins and page numbers are visible without clipping. |
| `AI4BRAIN-Pitch.pptx` | Artifact Tool export, finalizer package/layout/font checks, first-party re-import, 11 PNG renders and slide-by-slide visual inspection | PASS: 11 slides, under the 15-slide limit; 16:9; package integrity and layout validators report zero findings; Arial is consistently recorded; two native tables are present; first-party import passed. All slides were rendered. The contact sheet and full-size slide images are saved under `output/submission-qa/`. |
| `demo-script.md` / `demo-narration.txt` | Content and timing review | READY AS A RECORDING PLAN: six chapters total 255 seconds (4:15), with synthetic voice disclosure, QA-data disclosure, and instructions that narration must match actual app state. No video has been recorded. |

`build_submission_report.py` enforces the eight-page ceiling. `build_submission_pitch.mjs` produces the canonical deck and validation receipt under `tmp/submission-pitch-build/`. Earlier generated `AI4BRAIN-Pitch-Review*.pptx` drafts were moved into `output/submission-qa/`; the canonical files remain in `docs/submission/`.

Visual records:

- Report pages: `output/submission-qa/final-report-1.png`, `final-report-2.png`, `final-report-3.png`.
- Pitch contact sheet: `output/submission-qa/AI4BRAIN-Pitch-contact-sheet.png`.
- Full-size pitch render: `output/submission-qa/final-pitch/slide-1.png` through `slide-11.png`.

The PDF renderer emitted a `No display font for 'Symbol'` diagnostic during rasterization. Every page rendered and the visual inspection found no missing-glyph box or clipped text. This is recorded as a renderer warning rather than treated as proof of any native PDF viewer behavior. The PPTX was rendered and imported with the bundled presentation runtime; it was not opened in Microsoft PowerPoint or Google Slides.

Automated browser QA and software smoke evidence are described in the report and `output/verification/`. They are not participant outcomes. Current browser checks cover interactions across all five task families, memory recovery, reasoning baseline, desktop/mobile welcome and companion docking. A planning remount-recovery repair awaits a targeted rerun. Dashboard UI integration and the remaining integrated coach/data flows still need review. Current Neo4j read-only verification is recorded in `output/verification/NEO4J_CURRENT.md`; the optional mirror remains derived from canonical SQLite evidence.

## Exact work still required before release

1. Finish and independently review the refreshed UI: rerun the planning recovery path after the keyed-remount repair; complete unified dashboard UI integration; review Analytics/RPG evidence invariance, coach fallback, plan actions, Quest, graph, data controls, keyboard/reduced-motion behavior and mobile layout. Re-run the production build and relevant isolated smokes against the final integrated tree.
2. Perform a clean-start rehearsal using an explicitly disposable SQLite database. Preserve the primary local database and unknown-provenance learner session. Confirm the app starts from documented commands with Neo4j optional and no private data copied into the release directory.
3. Record an actual 3-5 minute walkthrough, targeting 4:15. Use the real integrated application and isolated QA data with the visible disclosure “Automated QA data - software demonstration only; not participant or cognitive-performance data.” Show overview, evidence, plan, local coach, a real completed training decision, Quest and derived graph. If no completed decision exists in the isolated QA copy, complete a genuine four-item block before the take; narrate the saved result rather than promising promotion. Do not use old screenshot cutaways, invent outcomes or imply QA values describe a person. Review the whole saved video for disclosure, legibility, accidental actions and secret/path exposure.
4. Complete final human acceptance of the report, deck, application and recording. Resolve any findings and rerender affected artifacts; update this QA record with the accepted revision.
5. Verify the official submission rules, deadline, file format/size limits, required forms and destination from an authoritative current source. The source brief's competition dates/rules have not been independently verified.
6. Confirm the target repository or submission destination, ownership, license, project/team attribution, contact details and permitted package contents. No team names, contact, public URL or official submission destination were supplied, so none are invented here.
7. Prepare and inspect the final release package, excluding `.env`, credentials, Neo4j secrets, SQLite databases, exports, private histories, temp builds, QA captures not intended for release and generated validation files unless explicitly required. Verify the exact package file list and checksums.
8. Obtain the user's separate approval before publishing a public repository or submitting externally. Neither action has been performed.
