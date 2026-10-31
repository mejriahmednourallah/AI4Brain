# Local companion speech (KittenTTS)

## Selected dependency and model

| Item | Value | Source |
| --- | --- | --- |
| Package | `kittenml` 0.9.4 | PyPI, installed into `.venv` |
| Model | `KittenML/kitten-tts-mini-0.8` (80M parameters, ONNX) | Hugging Face, fetched on first use |
| Backend | `onnxruntime` CPU execution provider | no GPU required |
| Output | 24 kHz mono, written as 16-bit PCM WAV | engine contract |
| Package licence | Apache-2.0 | upstream repository badge/LICENSE |
| Model licence | per the model card on Hugging Face | verify before redistribution |
| Install shape | `pip install kittenml --no-deps` plus `onnxruntime espeakng_loader phonemizer soundfile numpy huggingface_hub` | upstream `docs/onnx-models.md` |

The lightweight ONNX family was chosen over the 1.7B "KittenTTS 2" model because this product only
needs short, occasional companion replies on a CPU-only Windows machine; the 1.7B model would add a
PyTorch stack and roughly 6 GB of working memory for no product benefit here. PyTorch is
deliberately **not** installed.

## Measured behaviour (this machine, CPU)

| Measurement | Value |
| --- | --- |
| Cold model load incl. first-time download | 26.6 s |
| Cached model load + first synthesis (cold process) | 8.4 s |
| Warm synthesis, short reply | 1.8–2.2 s for 3.3 s of audio |
| Audio check | 24 000 Hz, mono, peak 0.50, RMS 0.084 (speech, not silence) |
| Burst of 5 concurrent requests | 2 × `409` (superseded), 3 × `429` (queue full) — no unbounded queue, no overlapping synthesis |

Model cache: `data/models/kittentts` (override with `AI4BRAIN_TTS_CACHE`). After the first
successful download the engine works offline.

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/companion/speech/status` | engine, model, licence, sample rate, voices, loaded flag, text cap |
| POST | `/api/companion/speech/warm` | loads the model and returns the status with voices |
| POST | `/api/companion/speech` | `{text, voice, speed}` → `audio/wav`; `422` invalid payload, `429` queue full, `409` superseded, `503` model unavailable |

Synthesis runs on a single worker thread, so it can never block API scoring, task input or timed
cues. Text is capped at 320 characters, cut on a sentence boundary. The learner's text is never
sent anywhere; only the first-day model download contacts Hugging Face.

## UI behaviour

* Off by default; the user enables "Speak replies locally (KittenTTS)" in the companion panel.
* Voice, speed (0.8/1.0/1.2) and an explicit "speak each new reply automatically" option, all
  persisted in `localStorage` under `ai4brain.speech`.
* Play / Pause / Resume / Replay / Stop controls; the written reply is always complete without audio.
* Latest reply owns the audio: a new reply or a new question aborts the pending request, stops the
  current audio and starts fresh. Navigating away or unmounting stops and revokes the blob URL.
* Scored baseline/reassessment phases silence the companion and suppress new speech entirely.
* Speaking an already-authorized hint does not create trial evidence, change assistance status or
  award XP; it only reads text the learner already has.
* Errors are shown as "Local voice unavailable (…)" with the written reply still usable.

## Verified in a real browser

`output/verification/hybrid/verify_speech_browser.cjs` produced
`output/verification/hybrid/speech-browser/result.json`:

* speech setting starts disabled and persists across a reload;
* asking the coach produced a validated reply, Play played real audio (`audio.play()` resolved and
  the UI reported "Playing local synthetic voice"), Pause/Resume/Stop all changed state;
* a new question during playback stopped the old audio and started a new synthesis instead of
  talking over it;
* the speech response was `200` with `content-length: 1105244` and `x-speech-seconds: 23.02`;
* no `4xx`/`5xx` responses and no page errors during the journey.

## Not claimed

* No audible-quality judgement is made here; the checks are file-level (sample rate, duration,
  peak/RMS) and browser-level (playback started, controls changed state). Listening review remains a
  human acceptance item.
* No phoneme lip-sync is implemented; the companion shows generic speaking motion driven by real
  playback state, not mouth-shape alignment.
