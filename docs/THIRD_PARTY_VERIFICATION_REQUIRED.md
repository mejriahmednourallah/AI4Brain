# Items that require third-party verification

Everything in this list is **outside** what the implementation AI can certify for itself. Each item
names the current state, the evidence that exists, and exactly what a third party must do.

Status legend: `open` = nobody has verified it yet, `self-verified` = verified only by the
implementation AI's own harness, `pending-human` = blocked on a named human decision.

## 1. Human visual acceptance (pending-human)

The approved generated images define the target. My own captures are comparison evidence, never
acceptance.

| Surface | Reference | Evidence that exists | What a human must decide |
| --- | --- | --- | --- |
| Home | `01-home.png` | implementation-run captures in `output/verification/home-2026-10-19/` | Is the illustrated-adventure identity faithfully realised? |
| Planning | `02-game-planning.png` | `VISUAL_MISMATCH_REGISTER.md` P1-P12; captures `rebuild-Planning-3x3-1586.png`, `rebuild-Planning-7x7-1586.png`, `rebuild-app-planning-375.png`; sprite check `../asset-previews/planning-sprites-checker.png` | Remaining P9-P12 items accepted or rejected |
| Memory | `03-game-memory.png` | M1-M2 closed, M3-M7 open; capture `deep-qa-2026-10-20/screenshots/batch3-memory-1440.png` | Tile carving, gold/teal treatment, perspective slab, dock plate |
| Reasoning | `04-game-reasoning.png` | **missing** - no reference comparison captured yet | Whole-surface comparison |
| Attention | `05-game-attention.png` | **missing** - only functional captures exist (`deep-qa-2026-10-20/a1b-attention/*.png`) | Cue registration inside the instrument |
| Flexibility | `06-game-flexibility.png` | **missing** - only retry captures exist (`deep-qa-2026-10-20/a2b-recovery/*.png`) | Rule sign, pedestal, material slabs |
| Pages 07-15 | `07`-`15` | Home and Insights captures only; Quest, Plan, Practice, Evidence, Collaboration, Privacy, Pause are **missing** | Each surface |
| Companion | approved `image07` guidance | graphite eye preserved; no side-by-side capture exists | Proportions/states accepted |

## 2. Audible quality and speech acceptability (pending-human)

Self-verified: real local synthesis (24 kHz mono WAV, peak 0.50, RMS 0.084), browser playback
started, pause/resume/stop/replay, latest-reply ownership, quiet-phase suppression.
**Not** verified by anyone: whether the voice is acceptable.

* Listen to the actual default-voice sample `output/verification/hybrid/tts-sample-bella.wav`
  (7.66 s, 24 kHz mono, peak 0.588, RMS 0.096, `content-length` 367 644) and the earlier
  `tts-sample-jasper.wav` and `tts-api-sample.wav` only for comparison.
* The default voice is **Bella** (human decision) in both `frontend/src/CompanionSpeech.tsx`
  (`DEFAULTS.voice`) and `backend/app/speech_service.py` (request default and the unknown-voice
  fallback). A previously saved `ai4brain.speech` selection always overrides the default and is
  never rewritten. Confirm the default choice and the speaking rate.
* Judge pronunciation of domain terms (*inhibition*, *flexibility*, tier labels).
* Confirm the first-run model download and offline cached behaviour on a fresh machine (section 7).

## 3. Canonical semantics: independent re-derivation (open)

My harness drives the app; it cannot prove the scoring rules are *correct*, only consistent.

* Re-derive the five family formulas from `backend/app/battery_scoring.py` and
  `backend/app/scoring.py` and compare with `docs/REQUIREMENTS.md`.
* Confirm the 79 baseline references (6/6/40/24/3) cannot be inflated by retries, interruptions or
  assistance, using an independent SQLite read of a QA database.
* Confirm the difficulty rule (`difficulty.py`, `difficulty-v2`) against the sprint documents:
  four-attempt window, UP/DOWN/HOLD thresholds, assisted and interrupted exclusion.
* Confirm hybrid outcomes in `hybrid_outcomes` never reach EX indices, recommendations or XP.
* Re-run `output/verification/ui-rebuild/games/full-audit/deep-qa-2026-10-20/a3_seed.py` and check
  its assertions are not tautological.
* **Derive the expected semantics from the requirements first** (`docs/REQUIREMENTS.md`,
  `docs/source/POC_SPEC_EXTRACTED.txt`), write worked expected cases by hand, and only then compare
  the specification with `battery_scoring.py`, the API responses and the isolated SQLite rows.
  Reading formulas out of the implementation and comparing a harness against the same code is not
  independent derivation.
* Verify the count is of **eligible, unique** baseline items (not merely 79 rows that might include
  excluded or repeated submissions): check item ids, phases, interruption flags and assistance
  counters per family.

## 4. Clinical, educational and participant claims (must not be claimed by me)

Nothing in this repository is clinical evidence. Third-party work required before any such claim:

* Ethics approval and participant recruitment for any study use.
* Psychometric evaluation (reliability, validity, measurement invariance) of the five families.
* Age/education/language norming for any interpretation of indices.
* Review of the "not a clinical assessment" and "preliminary observation, high uncertainty" copy by a
  qualified clinician for accuracy and safety.
* Confirmation that hybrid activities are described as engagement activities, not instruments.

## 5. Accessibility conformance (open)

Self-verified: keyboard paths, visible focus, reduced-motion CSS, 44 px targets where measured, modal
focus restoration, seven viewport widths.

Third-party verification still required:

* Screen-reader walkthrough (NVDA or JAWS on Windows) of consent, a full task family, pause/recovery
  and the companion, including live-region behaviour for streamed attention cues.
* Colour-vision simulation review of the gold/teal Memory states once M4 lands, confirming the
  non-colour cue is sufficient.
* Motor-impaired and switch-access testing of the 320 px and 812Ã—375 layouts.
* An accessibility audit against WCAG 2.2 AA by someone other than the implementer.

## 6. Security, privacy and data-protection review (open)

Two different data paths exist and must be reviewed separately. Local-only speech does **not**
prove that coaching is local.

| Path | Behaviour in source | What to verify |
| --- | --- | --- |
| Companion speech (KittenTTS) | Always local: `speech_service.py` synthesises on this machine and never calls a provider. The only network use is the one-time model download from Hugging Face on first use. | Capture traffic while speaking synthetic text and confirm no learner text leaves the machine; confirm the model download happens once and is cacheable offline. |
| Companion coaching | `coach_service.py` posts `message[:2000]` plus allowed evidence context to a provider **only when `allow_remote` is true and a provider is configured**. The UI sends `allow_remote: false`, so the default path is the local deterministic template. | Confirm the default path performs no egress; confirm remote coaching is an explicit opt-in that discloses what is sent; never enable a real provider or send participant text for verification — use synthetic QA text only. |
| Story/graph mirror | Neo4j holds canonical references only. | Confirm no learner free text or transcript reaches the mirror. |

Also required from an independent reviewer:

* Retention/deletion/export behaviour against the privacy copy actually shown in the app.
* Dependency and licence review: `kittenml` 0.9.4 (Apache-2.0), the
  `KittenML/kitten-tts-mini-0.8` model card licence, and every other runtime dependency.

## 7. Environment and reproducibility (open)

* Clean-machine setup from `README`/`docs` on Windows without my local caches.
* First-run model download with the network blocked after the first use (offline).
* Reproduce measurements: cold model load 26.6 s, cached warm synthesis 1.8â€“2.2 s, production build,
  both structural suites (64/64 and 36/36).
* Verify the app can be started, restarted and stopped with the documented scripts without touching
  the primary data file.

## 8. Results currently resting only on my own harness (self-verified)

A second party should re-run these before relying on them:

| Result | Where |
| --- | --- |
| QA-02 pause/resume in baseline and training, pacing at index 10, window durations | `deep-qa-2026-10-20/a1b_attention_baseline.cjs`, `a1c_attention_training.cjs` |
| Recovery matrix (accepted-then-lost, rejected, GET-only) | `deep-qa-2026-10-20/a2b_recovery_corrected.cjs` |
| Footer hit targets at seven viewports | `deep-qa-2026-10-20/a3_browser.cjs` |
| Hybrid-v1 contract and HY-01 | `output/verification/hybrid/verify_hybrid_contract.py`, `verify_hy01_browser.cjs` |
| KittenTTS lifecycle | `output/verification/hybrid/verify_speech_browser.cjs` |
| Planning sprite geometry | `deep-qa-2026-10-20/probe_cue_window.cjs` lineage, register P1â€“P8 |

## 9. Explicitly deferred release actions (pending-human)

* Final demo recording (3â€“5 minutes).
* Publication and committee submission.
* Any statement of team facts, dates, results or participant outcomes.

## 10. Items still unfinished by me (not third-party work)

These are my remaining implementation tasks and are **not** waiting on anyone else:
HY-02â€¦HY-06, the 3Ã—3 crystal Reasoning form, pages 07â€“15 fidelity, Memory M3â€“M7, Planning P9â€“P12,
Attention/Flexibility reference comparison, the evidence-graph race replay, a real dashboard-failure
injection, and the post-reload continuation check for an explicit training block.

