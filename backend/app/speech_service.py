"""Local KittenTTS companion speech.

Facts pinned from the upstream project (Apache-2.0 package, ONNX lightweight models):
  * package: kittenml 0.9.4, installed into the project venv
  * model:   KittenML/kitten-tts-mini-0.8 (80M ONNX, CPU execution provider)
  * output:  24 kHz mono float samples, written here as 16-bit PCM WAV
  * download: only on first use, cached under AI4BRAIN_TTS_CACHE (default data/models/kittentts)

Synthesis is CPU bound, so it always runs on a bounded worker thread: a cold model
load or a long reply can never block API scoring, task input or timed cues.
Nothing leaves the machine: the learner's text is synthesised locally.
"""
from __future__ import annotations

import io
import hashlib
import json
import os
import threading
import wave
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path

import soundfile as sf
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .storage import utc_now

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT_DIR / "data" / "models" / "kittentts"

PACKAGE_VERSION = "0.9.4"
MODEL_ID = "KittenML/kitten-tts-mini-0.8"
SAMPLE_RATE = 24000
MAX_TEXT_LENGTH = 320
MAX_PENDING = 2
MAX_AUDIO_CACHE_ENTRIES = 64
MAX_AUDIO_CACHE_BYTES = 4 * 1024 * 1024
SPEECH_CACHE_VERSION = "speech-cache-v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpeechRequest(StrictModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice: str = Field(default="Bella", max_length=40)
    speed: float = Field(default=1.0, ge=0.6, le=1.4)
    session_id: str | None = None
    evidence_revision: str | None = Field(default=None, max_length=160)
    subject: str | None = Field(default=None, max_length=80)


class SpeechPreferenceRequest(StrictModel):
    session_id: str = Field(min_length=1, max_length=120)
    mode: str = Field(pattern="^(fast_local|bella|muted)$")
    enabled: bool
    voice: str = Field(default="Bella", max_length=40)
    speed: float = Field(default=1.0, ge=0.6, le=1.4)


class SpeechWarmRequest(StrictModel):
    session_id: str = Field(min_length=1, max_length=120)


class FastLocalSpeechRequest(StrictModel):
    session_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=300)
    evidence_revision: str | None = Field(default=None, max_length=160)
    subject: str | None = Field(default=None, max_length=80)


class SpeechBusy(RuntimeError):
    """Raised when too many syntheses are already queued."""


class SpeechSuperseded(RuntimeError):
    """Raised when a newer speech request replaced this one before synthesis."""


def _clean(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= MAX_TEXT_LENGTH:
        return collapsed
    cut = collapsed[:MAX_TEXT_LENGTH]
    for stop in (". ", "! ", "? "):
        index = cut.rfind(stop)
        if index > MAX_TEXT_LENGTH // 2:
            return cut[: index + 1]
    return cut


class SpeechEngine:
    """Single-flight local synthesis with explicit supersede semantics."""

    def __init__(self) -> None:
        self._model = None
        self._model_error: str | None = None
        self._load_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kittentts")
        self._pending_lock = threading.Lock()
        self._pending = 0
        self._ticket_lock = threading.Lock()
        self._ticket = 0
        self._newest_ticket = 0
        self._warm_future = None
        self._warm_state = "not_requested"
        self._warm_lock = threading.Lock()

    @property
    def cache_dir(self) -> Path:
        chosen = Path(os.environ.get("AI4BRAIN_TTS_CACHE", DEFAULT_CACHE))
        chosen.mkdir(parents=True, exist_ok=True)
        return chosen

    def status(self) -> dict:
        return {
            "engine": "KittenTTS",
            "package": f"kittenml {PACKAGE_VERSION}",
            "model": MODEL_ID,
            "model_parameters": "80M",
            "backend": "onnxruntime cpu",
            "license": "Apache-2.0 (package); model card license on Hugging Face",
            "local_only": True,
            "sample_rate": SAMPLE_RATE,
            "format": "audio/wav 16-bit PCM mono",
            "loaded": self._model is not None,
            "warm_state": self._warm_state,
            "load_error": self._model_error,
            "max_text_length": MAX_TEXT_LENGTH,
            "voices": list(self._model.available_voices) if self._model is not None else [],
            "cache": "data/models/kittentts (local, redownload-free after first use)",
        }

    def _load(self):
        with self._load_lock:
            if self._model is not None:
                return self._model
            if self._model_error:
                raise RuntimeError(self._model_error)
            try:
                from kittenml import KittenTTS

                self._model = KittenTTS(MODEL_ID, cache_dir=str(self.cache_dir), backend="cpu")
            except Exception as error:  # noqa: BLE001 - surfaced as a readable status
                self._model_error = f"{type(error).__name__}: {error}"[:400]
                raise RuntimeError(self._model_error) from error
            return self._model

    def warm(self) -> dict:
        model = self._load()
        return self.status() | {"voices": list(model.available_voices)}

    def warm_background(self) -> dict:
        with self._warm_lock:
            if self._warm_future is not None and not self._warm_future.done():
                return {"accepted": True, "warm_state": "warming"}
            if self._model is not None:
                self._warm_state = "loaded"
                return {"accepted": True, "warm_state": "loaded"}
            self._warm_state = "warming"
            self._warm_future = self._executor.submit(self._warm_task)
            return {"accepted": True, "warm_state": "warming"}

    def _warm_task(self) -> None:
        try:
            self.warm()
            self._warm_state = "loaded"
        except Exception as error:  # surfaced by status; warm request itself stays non-blocking
            self._model_error = f"{type(error).__name__}: {error}"[:400]
            self._warm_state = "error"

    def _next_ticket(self) -> int:
        with self._ticket_lock:
            self._ticket += 1
            self._newest_ticket = self._ticket
            return self._ticket

    def reserve(self) -> int:
        """Claim a queue slot on the calling thread so bursts are bounded and stale work is skipped."""
        ticket = self._next_ticket()
        with self._pending_lock:
            if self._pending >= MAX_PENDING:
                raise SpeechBusy("too many speech requests are already queued")
            self._pending += 1
        return ticket

    def _is_stale(self, ticket: int) -> bool:
        with self._ticket_lock:
            return ticket != self._newest_ticket

    def _end(self) -> None:
        with self._pending_lock:
            self._pending = max(0, self._pending - 1)

    def synthesise(self, ticket: int, text: str, voice: str, speed: float) -> bytes:
        try:
            if self._is_stale(ticket):
                raise SpeechSuperseded("a newer speech request replaced this one")
            model = self._load()
            if self._is_stale(ticket):
                raise SpeechSuperseded("a newer speech request replaced this one")
            voices = set(model.available_voices)
            chosen = voice if voice in voices else "Bella"
            audio = model.generate(_clean(text), voice=chosen, speed=float(speed))
            buffer = io.BytesIO()
            sf.write(buffer, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
            return buffer.getvalue()
        finally:
            self._end()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


_ENGINE: SpeechEngine | None = None
_ENGINE_LOCK = threading.Lock()
_AUDIO_CACHE: OrderedDict[tuple, tuple[str, bytes]] = OrderedDict()
_AUDIO_CACHE_BYTES = 0
_AUDIO_CACHE_LOCK = threading.RLock()


def clear_speech_cache_for_learner(learner_id: str) -> int:
    """Erase private synthesized audio for a learner after lifecycle deletion."""
    global _AUDIO_CACHE_BYTES
    with _AUDIO_CACHE_LOCK:
        keys = [key for key, (owner, _wav) in _AUDIO_CACHE.items() if owner == learner_id]
        for key in keys:
            _owner, wav = _AUDIO_CACHE.pop(key)
            _AUDIO_CACHE_BYTES -= len(wav)
        return len(keys)


def _session_and_consent(store, session_id: str) -> tuple[dict, dict]:
    session = store.get_session(session_id)
    if not session or session.get("learner_id") != "demo-user":
        raise HTTPException(status_code=404, detail="session not found")
    consent = next((event for event in store.events(session_id=session_id)
                    if event.get("type") == "consent_recorded"
                    and (event.get("payload", {}).get("consent") or {}).get("accepted") is True), None)
    if consent is None:
        raise HTTPException(status_code=409, detail="An accepted local-data consent is required for session-scoped voice")
    return session, consent


def _speech_preferences(store, session_id: str) -> dict:
    events = store.events(session_id=session_id)
    event = next((item for item in reversed(events) if item.get("type") == "speech_preference_changed"), None)
    return dict((event or {}).get("payload", {}).get("preferences") or {
        "mode": "fast_local", "enabled": False, "voice": "Bella", "speed": 1.0,
    })


def _current_generation(store, learner_id: str) -> int:
    from contextlib import closing
    with closing(store.connect()) as db:
        row = db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id=?", (learner_id,)).fetchone()
    if row and row["deleting"]:
        raise HTTPException(status_code=409, detail="learner data lifecycle is in progress")
    return int(row["generation"]) if row else 0


def _fast_local_opt_in(store, session_id: str, generation: int | None = None) -> tuple[str, int] | None:
    """Read the local consent, saved opt-in and generation under the lifecycle lock."""
    lock = getattr(store, "coach_lifecycle_lock", None)
    with lock if lock is not None else nullcontext():
        session, _consent = _session_and_consent(store, session_id)
        preferences = _speech_preferences(store, session_id)
        if preferences.get("mode") != "fast_local" or preferences.get("enabled") is not True:
            return None
        current_generation = _current_generation(store, session["learner_id"])
        if generation is not None and current_generation != generation:
            return None
        return session["learner_id"], current_generation


def _prewarm_sapi_reserved(worker, store, session_id: str, learner_id: str, generation: int) -> None:
    """Initialize the worker only while the same consented local opt-in still owns it."""
    try:
        if _fast_local_opt_in(store, session_id, generation) != (learner_id, generation):
            return
        worker.prepare()
        if _fast_local_opt_in(store, session_id, generation) != (learner_id, generation):
            worker.shutdown()
    except Exception:
        # The next local utterance still has its normal bounded startup/fallback path.
        return
    finally:
        _SAPI_PENDING.release()


def _release_cancelled_sapi_prewarm(future) -> None:
    if future.cancelled():
        _SAPI_PENDING.release()


_NON_EVIDENCE_REVISION_SUFFIX_TYPES = frozenset({
    "consent_recorded",
    "coaching_message_sent",
    "collaboration_opportunity_issued",
    "speech_preference_changed",
})
_MAX_BENIGN_REVISION_SUFFIX_EVENTS = 16


def _evidence_revision_matches_current_or_benign_suffix(
    store, learner_id: str, session_id: str, expected_revision: str,
) -> bool:
    """Accept an exact learner-wide revision or its saved coach reply's benign event suffix.

    Coach context revisions cover all learner sessions. Saving that reply and its
    collaboration opportunities appends non-measurement records afterward, so
    those exact response records may follow the revision. Any scored, practice,
    interruption, plan, or unknown event after the prefix makes it stale.
    """
    from .twin_context import _revision

    events = store.events(learner_id=learner_id)
    if _revision(events) == expected_revision:
        return True
    max_suffix = min(_MAX_BENIGN_REVISION_SUFFIX_EVENTS, max(0, len(events) - 1))
    for suffix_size in range(1, max_suffix + 1):
        prefix_size = len(events) - suffix_size
        if _revision(events[:prefix_size]) != expected_revision:
            continue
        suffix = events[prefix_size:]
        if not suffix or any(event.get("type") not in _NON_EVIDENCE_REVISION_SUFFIX_TYPES
                             for event in suffix):
            continue
        matching_reply = any(
            event.get("type") == "coaching_message_sent"
            and event.get("session_id") == session_id
            and (event.get("payload") or {}).get("evidence_revision") == expected_revision
            for event in suffix
        )
        if matching_reply:
            return True
    return False


def _cached_audio(key: tuple) -> bytes | None:
    with _AUDIO_CACHE_LOCK:
        hit = _AUDIO_CACHE.get(key)
        if hit is None:
            return None
        _AUDIO_CACHE.move_to_end(key)
        return hit[1]


def _discard_stale_session_audio(session_id: str, generation: int, evidence_revision: str) -> None:
    global _AUDIO_CACHE_BYTES
    with _AUDIO_CACHE_LOCK:
        stale = [key for key in _AUDIO_CACHE
                 if len(key) > 3 and key[1] == session_id and key[2] == generation
                 and key[3] != evidence_revision]
        for key in stale:
            _owner, wav = _AUDIO_CACHE.pop(key)
            _AUDIO_CACHE_BYTES -= len(wav)


def _store_cached_audio(key: tuple, learner_id: str, wav: bytes) -> None:
    global _AUDIO_CACHE_BYTES
    if len(wav) > MAX_AUDIO_CACHE_BYTES:
        return
    with _AUDIO_CACHE_LOCK:
        old = _AUDIO_CACHE.pop(key, None)
        if old:
            _AUDIO_CACHE_BYTES -= len(old[1])
        _AUDIO_CACHE[key] = (learner_id, wav)
        _AUDIO_CACHE_BYTES += len(wav)
        while len(_AUDIO_CACHE) > MAX_AUDIO_CACHE_ENTRIES or _AUDIO_CACHE_BYTES > MAX_AUDIO_CACHE_BYTES:
            _key, (_owner, removed) = _AUDIO_CACHE.popitem(last=False)
            _AUDIO_CACHE_BYTES -= len(removed)


def get_engine() -> SpeechEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = SpeechEngine()
        return _ENGINE


def register_speech_routes(app: FastAPI, store=None) -> None:
    app.router.add_event_handler("shutdown", _shutdown_local_speech)

    @app.get("/api/companion/speech/status")
    def speech_status():
        return get_engine().status()

    @app.get("/api/companion/speech/preferences")
    def speech_preferences(session_id: str):
        if store is None:
            raise HTTPException(status_code=503, detail="Session preferences are unavailable")
        _session_and_consent(store, session_id)
        return {"session_id": session_id, "preferences": _speech_preferences(store, session_id)}

    @app.post("/api/companion/speech/preferences")
    def save_speech_preferences(body: SpeechPreferenceRequest):
        if store is None:
            raise HTTPException(status_code=503, detail="Session preferences are unavailable")
        lifecycle_lock = getattr(store, "coach_lifecycle_lock", None)
        with lifecycle_lock if lifecycle_lock is not None else nullcontext():
            _session_and_consent(store, body.session_id)
            preferences = {"mode": body.mode, "enabled": body.enabled, "voice": body.voice,
                           "speed": body.speed, "updated_at": utc_now()}
            event_id = str(__import__("uuid").uuid4())
            event, replayed = store.add_event(event_id, body.session_id, "speech_preference_changed", {
                "event_id": event_id, "session_id": body.session_id, "learner_id": "demo-user",
                "event_type": "speech_preference_changed", "preferences": preferences,
                "sample_data": False, "recorded_at": utc_now(),
            })
        return {"event": event, "preferences": preferences, "replayed": replayed}

    @app.post("/api/companion/speech/warm")
    def speech_warm(body: SpeechWarmRequest | None = None):
        if store is None or body is None:
            raise HTTPException(status_code=422, detail="An explicit session-scoped Bella opt-in is required")
        _session_and_consent(store, body.session_id)
        preferences = _speech_preferences(store, body.session_id)
        if preferences.get("mode") != "bella" or preferences.get("enabled") is not True:
            raise HTTPException(status_code=409, detail="Bella warmup requires an enabled Bella preference")
        engine = get_engine()
        return engine.warm_background()

    @app.post("/api/companion/speech/fast-local/warm")
    def speech_fast_local_warm(body: SpeechWarmRequest):
        """Start the installed Windows voice after explicit session-scoped local opt-in."""
        if store is None:
            raise HTTPException(status_code=503, detail="Session-scoped voice is unavailable")
        ownership = _fast_local_opt_in(store, body.session_id)
        if ownership is None:
            raise HTTPException(status_code=409, detail="Fast local warmup requires an enabled Fast local preference")
        if not _SAPI_PENDING.acquire(blocking=False):
            return {"accepted": True, "warm_state": "already_active"}
        from . import windows_sapi
        worker = windows_sapi.get_worker()
        try:
            future = _SAPI_EXECUTOR.submit(_prewarm_sapi_reserved, worker, store, body.session_id, *ownership)
            future.add_done_callback(_release_cancelled_sapi_prewarm)
        except Exception as error:
            _SAPI_PENDING.release()
            raise HTTPException(status_code=503, detail="Local Windows voice could not be prepared") from error
        return {"accepted": True, "warm_state": "warming"}

    @app.post("/api/companion/speech")
    async def speech(body: SpeechRequest):
        import asyncio

        if not body.text.strip():
            raise HTTPException(status_code=422, detail="Speech text must contain audible characters")
        cache_key = None
        learner_id = None
        lifecycle_generation = None
        if body.session_id:
            if store is None:
                raise HTTPException(status_code=503, detail="Session-scoped voice is unavailable")
            session, _consent = _session_and_consent(store, body.session_id)
            learner_id = session["learner_id"]
            preferences = _speech_preferences(store, body.session_id)
            if preferences.get("mode") != "bella" or preferences.get("enabled") is not True:
                raise HTTPException(status_code=409, detail="Bella synthesis requires an enabled Bella preference")
            if body.voice != preferences.get("voice", "Bella") or float(body.speed) != float(preferences.get("speed", 1.0)):
                raise HTTPException(status_code=409, detail="Voice and speed must match the saved Bella preference")
            lifecycle_generation = _current_generation(store, learner_id)
            if body.evidence_revision and body.subject:
                _discard_stale_session_audio(body.session_id, lifecycle_generation, body.evidence_revision)
                cache_key = (learner_id, body.session_id, lifecycle_generation,
                             body.evidence_revision, body.subject,
                             hashlib.sha256(_clean(body.text).encode("utf-8")).hexdigest(),
                             body.voice, float(body.speed), SPEECH_CACHE_VERSION, MODEL_ID)
                cached = _cached_audio(cache_key)
                if cached is not None:
                    return Response(content=cached, media_type="audio/wav", headers={
                        "X-Speech-Engine": "KittenTTS", "X-Speech-Model": MODEL_ID,
                        "X-Speech-Cache": "hit", "Cache-Control": "private, no-store",
                    })
        engine = get_engine()
        loop = asyncio.get_running_loop()
        try:
            ticket = engine.reserve()
        except SpeechBusy as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        try:
            wav = await loop.run_in_executor(engine._executor, engine.synthesise, ticket, body.text, body.voice, body.speed)
        except SpeechBusy as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        except SpeechSuperseded as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Speech text was rejected: {error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=f"Local voice unavailable: {error}") from error
        if cache_key is not None and learner_id is not None:
            try:
                if _current_generation(store, learner_id) == lifecycle_generation:
                    _store_cached_audio(cache_key, learner_id, wav)
            except HTTPException:
                # A deleted/lifecycle-changing learner must not repopulate private audio.
                pass
        seconds = max(0.0, (len(wav) - 44) / (SAMPLE_RATE * 2))
        return Response(content=wav, media_type="audio/wav", headers={
            "X-Speech-Engine": "KittenTTS",
            "X-Speech-Model": MODEL_ID,
            "X-Speech-Seconds": f"{seconds:.2f}",
            "X-Speech-Sample-Rate": str(SAMPLE_RATE),
            "X-Speech-Cache": "miss" if cache_key is not None else "disabled",
            "Cache-Control": "private, no-store" if cache_key is not None else "no-store",
        })

    @app.post("/api/companion/speech/fast-local")
    async def speech_fast_local(body: FastLocalSpeechRequest, request: Request):
        """Synthesize a short excerpt with an installed local Windows English voice."""
        import asyncio
        from . import windows_sapi

        if store is None:
            raise HTTPException(status_code=503, detail="Session-scoped voice is unavailable")
        if not body.text.strip():
            raise HTTPException(status_code=422, detail="Speech text must contain audible characters")
        cache_key = None
        lifecycle_lock = getattr(store, "coach_lifecycle_lock", None)
        lock_context = lifecycle_lock if lifecycle_lock is not None else nullcontext()
        with lock_context:
            session, _consent = _session_and_consent(store, body.session_id)
            learner_id = session["learner_id"]
            preferences = _speech_preferences(store, body.session_id)
            if preferences.get("mode") != "fast_local" or preferences.get("enabled") is not True:
                raise HTTPException(status_code=409, detail="Fast local speech requires an enabled Fast local preference")
            lifecycle_generation = _current_generation(store, learner_id)
            if body.evidence_revision and not _evidence_revision_matches_current_or_benign_suffix(
                store, learner_id, body.session_id, body.evidence_revision,
            ):
                raise HTTPException(status_code=409, detail="Evidence changed before local speech could start")
            worker = windows_sapi.get_worker()
            if body.evidence_revision and body.subject:
                # Evidence and consent are revalidated under the lifecycle lock above before
                # every hit. Cache the rendered bytes by their exact spoken content and owner,
                # not by the evidence revision: benign coach-only events advance that revision
                # even when the grounded sentence is identical. A stale revision still fails
                # before lookup, while changed text, subject, session, generation, voice, or
                # synthesis version cannot reuse this entry.
                cache_key = ("windows-sapi-content", learner_id, body.session_id, lifecycle_generation,
                             body.subject, hashlib.sha256(_clean(body.text).encode("utf-8")).hexdigest(),
                             worker.voice_name or "Windows local English voice",
                             windows_sapi.SAPI_VERSION, SPEECH_CACHE_VERSION)
                cached = _cached_audio(cache_key)
                if cached is not None:
                    return Response(content=cached, media_type="audio/wav", headers={
                        "X-Speech-Engine": "Windows SAPI local English",
                        "X-Speech-Voice": worker.voice_name or "Windows local English voice",
                        "X-Speech-Cache": "hit", "Cache-Control": "private, no-store",
                    })

        if not await _acquire_sapi_slot_bounded():
            raise HTTPException(status_code=429, detail="A local voice request is already running")
        submitted = False
        try:
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="The local speech request was cancelled")
            # A request may wait behind the one-time opt-in prewarm. Revalidate
            # ownership and consent before passing any text to the local worker.
            with lock_context:
                current_session, _current_consent = _session_and_consent(store, body.session_id)
                if current_session.get("learner_id") != learner_id:
                    raise HTTPException(status_code=409, detail="Session ownership changed before local speech started")
                current_preferences = _speech_preferences(store, body.session_id)
                if current_preferences.get("mode") != "fast_local" or current_preferences.get("enabled") is not True:
                    raise HTTPException(status_code=409, detail="Fast local speech was withdrawn before audio synthesis")
                if _current_generation(store, learner_id) != lifecycle_generation:
                    raise HTTPException(status_code=409, detail="Learner data changed before local speech started")
                if body.evidence_revision and not _evidence_revision_matches_current_or_benign_suffix(
                    store, learner_id, body.session_id, body.evidence_revision,
                ):
                    raise HTTPException(status_code=409, detail="Evidence changed before local speech could start")
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(_SAPI_EXECUTOR, _synthesize_sapi_reserved, worker, _clean(body.text))
            submitted = True
            try:
                wav = await asyncio.wait_for(future, timeout=12)
            except asyncio.TimeoutError as error:
                raise HTTPException(status_code=504, detail="Local Windows speech timed out") from error
            except windows_sapi.WindowsSapiBusy as error:
                raise HTTPException(status_code=429, detail="A local voice request is already running") from error
            except (windows_sapi.WindowsSapiUnavailable, windows_sapi.WindowsSapiTimeout) as error:
                raise HTTPException(status_code=503, detail="Local Windows speech could not synthesize this excerpt") from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail="Speech text is invalid for the local voice") from error
        finally:
            if not submitted:
                _SAPI_PENDING.release()

        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="The local speech request was cancelled")
        try:
            with wave.open(io.BytesIO(wav), "rb") as audio:
                channels, sample_rate, frames = audio.getnchannels(), audio.getframerate(), audio.getnframes()
                if channels not in (1, 2) or not 8000 <= sample_rate <= 48000 or frames <= 0:
                    raise ValueError("unsupported WAV metadata")
                seconds = frames / sample_rate
        except Exception as error:
            raise HTTPException(status_code=503, detail="Windows local speech returned invalid audio") from error

        with lock_context:
            current_session, _current_consent = _session_and_consent(store, body.session_id)
            if current_session.get("learner_id") != learner_id:
                raise HTTPException(status_code=409, detail="Session ownership changed while local speech was being prepared")
            current_preferences = _speech_preferences(store, body.session_id)
            if current_preferences.get("mode") != "fast_local" or current_preferences.get("enabled") is not True:
                raise HTTPException(status_code=409, detail="Fast local speech was withdrawn while the audio was being prepared")
            if _current_generation(store, learner_id) != lifecycle_generation:
                raise HTTPException(status_code=409, detail="Learner data changed while local speech was being prepared")
            if body.evidence_revision and not _evidence_revision_matches_current_or_benign_suffix(
                store, learner_id, body.session_id, body.evidence_revision,
            ):
                raise HTTPException(status_code=409, detail="Evidence changed while local speech was being prepared")
            if cache_key is not None:
                _store_cached_audio(cache_key, learner_id, wav)
        return Response(content=wav, media_type="audio/wav", headers={
            "X-Speech-Engine": "Windows SAPI local English",
            "X-Speech-Voice": worker.voice_name or "Windows local English voice",
            "X-Speech-Seconds": f"{seconds:.2f}",
            "X-Speech-Sample-Rate": str(sample_rate),
            "X-Speech-Channels": str(channels),
            "X-Speech-Cache": "miss" if cache_key is not None else "disabled",
            "Cache-Control": "private, no-store",
        })


_SAPI_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="windows-sapi")
_SAPI_PENDING = threading.BoundedSemaphore(1)
SAPI_SLOT_WAIT_SECONDS = 2.0


async def _acquire_sapi_slot_bounded(timeout: float = SAPI_SLOT_WAIT_SECONDS) -> bool:
    """Let a just-started local voice prewarm finish without blocking the event loop."""
    import asyncio

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        if _SAPI_PENDING.acquire(blocking=False):
            return True
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(0.025, remaining))


def _synthesize_sapi_reserved(worker, text: str) -> bytes:
    try:
        return worker.synthesize(text)
    finally:
        _SAPI_PENDING.release()


def _shutdown_local_speech() -> None:
    from . import windows_sapi

    windows_sapi.shutdown_worker()
    _SAPI_EXECUTOR.shutdown(wait=False, cancel_futures=True)


