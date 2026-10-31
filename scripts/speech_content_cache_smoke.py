"""Fast-local content cache hit, stale-revision and lifecycle race checks; no SAPI/provider calls."""
from __future__ import annotations

import io
import asyncio
import os
import sys
import threading
import tempfile
import uuid
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory(prefix="ai4brain-speech-content-cache-")
os.environ["AI4BRAIN_DB"] = str(Path(TEMP.name) / "speech-cache.sqlite3")
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient
from fastapi import HTTPException
from backend.app.main import app, store
from backend.app import speech_service, windows_sapi, lifecycle_routes
from backend.app.speech_service import FastLocalSpeechRequest
from backend.app.twin_context import _revision


def fake_wav() -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(22050)
        output.writeframes(bytes(22050))
    return stream.getvalue()


class FakeSapiWorker:
    voice_name = "Synthetic local voice"
    def __init__(self):
        self.calls = 0
        self.block_next = False
        self.started = threading.Event()
        self.release = threading.Event()
        self.prepared = threading.Event()
        self.prepare_started = threading.Event()
        self.prepare_release = threading.Event()
        self.prepare_release.set()
        self.block_prepare_next = False
        self.prepare_calls = 0
        self.shutdown_calls = 0
    def prepare(self):
        self.prepare_calls += 1
        self.prepare_started.set()
        if self.block_prepare_next:
            self.block_prepare_next = False
            if not self.prepare_release.wait(5):
                raise RuntimeError("test prewarm timeout")
        self.prepared.set()
        return self.voice_name
    def synthesize(self, _text):
        self.calls += 1
        if self.block_next:
            self.block_next = False
            self.started.set()
            if not self.release.wait(5):
                raise RuntimeError("test worker timeout")
        return fake_wav()
    def shutdown(self):
        self.shutdown_calls += 1


class NoopGraphMirror:
    def erase_learner(self, _learner_id):
        return {"erasure_verified": False}


fake = FakeSapiWorker()
speech_service.clear_speech_cache_for_learner("demo-user")
windows_sapi._WORKER = fake
lifecycle_routes.GraphMirror = NoopGraphMirror

with TestClient(app) as client:
    session_id = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
    preference = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "fast_local", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert preference.status_code == 200, preference.text
    coach = client.post("/api/coach", json={
        "session_id": session_id, "message": "What should I practice next?", "allow_remote": False,
    })
    assert coach.status_code == 200, coach.text
    answer = coach.json()
    body = {"session_id": session_id, "text": answer["spoken_summary"],
            "evidence_revision": answer["evidence_revision"], "subject": answer["subject"]["exercise_id"]}

    # A first speech request arriving while the opt-in worker warmup owns the
    # single SAPI slot waits briefly, then synthesizes once after opt-in recheck.
    fake.block_prepare_next = True
    fake.prepared.clear(); fake.prepare_started.clear(); fake.prepare_release.clear()
    warm = client.post("/api/companion/speech/fast-local/warm", json={"session_id": session_id})
    assert warm.status_code == 200 and warm.json()["accepted"] is True, warm.text
    assert fake.prepare_started.wait(2) and fake.calls == 0
    during_warm_result = {}
    during_warm_thread = threading.Thread(target=lambda: during_warm_result.setdefault("response", client.post(
        "/api/companion/speech/fast-local", json=body)))
    during_warm_thread.start()
    threading.Event().wait(0.1)
    assert during_warm_thread.is_alive(), "speech should wait behind active prewarm, not fail with 429"
    fake.prepare_release.set()
    during_warm_thread.join(5)
    assert not during_warm_thread.is_alive()
    assert during_warm_result["response"].status_code == 200, during_warm_result["response"].text
    assert during_warm_result["response"].headers["x-speech-cache"] == "miss" and fake.calls == 1

    first = during_warm_result["response"]
    exact_retry = client.post("/api/companion/speech/fast-local", json=body)
    assert first.status_code == exact_retry.status_code == 200
    assert first.headers["x-speech-cache"] == "miss"
    assert exact_retry.headers["x-speech-cache"] == "hit" and fake.calls == 1
    sapi_key = next(key for key in speech_service._AUDIO_CACHE if key[0] == "windows-sapi-content")
    generation = speech_service._current_generation(store, "demo-user")
    bella_stale_key = ("demo-user", session_id, generation, "old-revision", "EX-01",
                       "text-hash", "Bella", 1.0, speech_service.SPEECH_CACHE_VERSION, "model")
    speech_service._store_cached_audio(bella_stale_key, "demo-user", b"RIFF-bella")
    speech_service._discard_stale_session_audio(session_id, generation, "new-revision")
    assert bella_stale_key not in speech_service._AUDIO_CACHE
    assert sapi_key in speech_service._AUDIO_CACHE, "Bella revision cleanup evicted the namespaced SAPI content entry"

    # New canonical revision, same exact grounded bytes/subject/owner: revalidation
    # passes and content-addressed audio is reusable without retaining stale revision.
    revision_2 = _revision(store.events(learner_id="demo-user"))
    assert revision_2 != body["evidence_revision"]
    same_content_new_revision = client.post("/api/companion/speech/fast-local", json={
        **body, "evidence_revision": revision_2,
    })
    assert same_content_new_revision.status_code == 200
    assert same_content_new_revision.headers["x-speech-cache"] == "hit" and fake.calls == 1

    # Different audio text has a different content key and must synthesize anew.
    changed_text = client.post("/api/companion/speech/fast-local", json={
        **body, "evidence_revision": revision_2, "text": body["text"] + " Please read the written reply.",
    })
    assert changed_text.status_code == 200 and changed_text.headers["x-speech-cache"] == "miss"
    assert fake.calls == 2

    # A later unknown/evidence event invalidates the old revision before cache lookup.
    unknown_event_id = str(uuid.uuid4())
    store.add_event(unknown_event_id, session_id, "mock_context_changed", {
        "event_id": unknown_event_id, "session_id": session_id, "learner_id": "demo-user", "sample_data": True,
    })
    stale = client.post("/api/companion/speech/fast-local", json={**body, "evidence_revision": revision_2})
    assert stale.status_code == 409 and fake.calls == 2, stale.text

    # If the learner mutes while a warmup is running, a waiting speech request
    # is revalidated before worker synthesis and cannot speak/cache stale text.
    current_revision = _revision(store.events(learner_id="demo-user"))
    fake.block_prepare_next = True
    fake.prepare_started.clear(); fake.prepare_release.clear(); fake.prepared.clear()
    warm = client.post("/api/companion/speech/fast-local/warm", json={"session_id": session_id})
    assert warm.status_code == 200, warm.text
    assert fake.prepare_started.wait(2)
    cache_before_warm_mute = set(speech_service._AUDIO_CACHE)
    waiting_result = {}
    waiting_thread = threading.Thread(target=lambda: waiting_result.setdefault("response", client.post(
        "/api/companion/speech/fast-local", json={**body, "evidence_revision": current_revision,
            "text": "A sentence waiting for local voice."})))
    waiting_thread.start()
    threading.Event().wait(0.1)
    assert waiting_thread.is_alive(), "speech request did not wait for the active prewarm"
    muted_during_warm = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "muted", "enabled": False, "voice": "Bella", "speed": 1.0,
    })
    assert muted_during_warm.status_code == 200, muted_during_warm.text
    fake.prepare_release.set()
    waiting_thread.join(5)
    assert not waiting_thread.is_alive()
    assert waiting_result["response"].status_code == 409, waiting_result["response"].text
    assert fake.calls == 2 and fake.shutdown_calls >= 1
    assert set(speech_service._AUDIO_CACHE) == cache_before_warm_mute

    # Mute during synthesis must invalidate the request and avoid cache insertion.
    reenabled_for_synthesis = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "fast_local", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert reenabled_for_synthesis.status_code == 200, reenabled_for_synthesis.text
    current_revision = _revision(store.events(learner_id="demo-user"))
    cache_before_mute = set(speech_service._AUDIO_CACHE)
    fake.block_next = True
    mute_result = {}
    mute_thread = threading.Thread(target=lambda: mute_result.setdefault("response", client.post(
        "/api/companion/speech/fast-local", json={**body, "evidence_revision": current_revision,
            "text": "A new private sentence."})))
    mute_thread.start()
    assert fake.started.wait(3), "synthesis did not reach the controlled worker"
    muted = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "muted", "enabled": False, "voice": "Bella", "speed": 1.0,
    })
    assert muted.status_code == 200, muted.text
    fake.release.set()
    mute_thread.join(5)
    assert not mute_thread.is_alive()
    assert mute_result["response"].status_code == 409, mute_result["response"].text
    muted_warm = client.post("/api/companion/speech/fast-local/warm", json={"session_id": session_id})
    assert muted_warm.status_code == 409, muted_warm.text
    assert not (set(speech_service._AUDIO_CACHE) - cache_before_mute), "muted synthesis repopulated audio cache"

    # Simulate route navigation aborting a request that was waiting behind SAPI
    # work: after the slot frees, the disconnected request must not synthesize.
    reenabled_for_cancel = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "fast_local", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert reenabled_for_cancel.status_code == 200, reenabled_for_cancel.text
    current_revision = _revision(store.events(learner_id="demo-user"))
    fast_local_route = next(route.endpoint for route in app.routes
                            if getattr(route, "path", "") == "/api/companion/speech/fast-local")
    class DisconnectedRequest:
        async def is_disconnected(self):
            return True
    calls_before_cancel = fake.calls
    assert speech_service._SAPI_PENDING.acquire(blocking=False)
    loop = asyncio.new_event_loop()
    loop.call_later(0.05, speech_service._SAPI_PENDING.release)
    try:
        try:
            loop.run_until_complete(fast_local_route(
                FastLocalSpeechRequest(session_id=session_id, text="A route-cancelled sentence.",
                                       evidence_revision=current_revision, subject=body["subject"]),
                DisconnectedRequest()))
            raise AssertionError("disconnected route unexpectedly received speech audio")
        except HTTPException as error:
            assert error.status_code == 499, error.status_code
    finally:
        loop.close()
    assert fake.calls == calls_before_cancel, "route-cancelled request synthesized text"

    # Deletion during synthesis increments lifecycle generation and clears all
    # learner audio; late synthesis cannot repopulate the cache.
    reenabled = client.post("/api/companion/speech/preferences", json={
        "session_id": session_id, "mode": "fast_local", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert reenabled.status_code == 200, reenabled.text
    current_revision = _revision(store.events(learner_id="demo-user"))
    fake.started.clear(); fake.release.clear(); fake.block_next = True
    delete_result = {}
    late_result = {}
    delete_thread = threading.Thread(target=lambda: late_result.setdefault("response", client.post(
        "/api/companion/speech/fast-local", json={**body, "evidence_revision": current_revision,
            "text": "A deletion-race sentence."})))
    delete_thread.start()
    assert fake.started.wait(3), "deletion-race synthesis did not start"
    deletion = client.post("/api/data/demo-user/delete", json={"confirmation": "DELETE LOCAL DATA"})
    assert deletion.status_code == 200, deletion.text
    delete_result.update(deletion.json())
    fake.release.set()
    delete_thread.join(5)
    assert not delete_thread.is_alive()
    assert late_result["response"].status_code in {404, 409}, late_result["response"].text
    assert not any(owner == "demo-user" for owner, _wav in speech_service._AUDIO_CACHE.values()), \
        "late synthesis repopulated cache after learner deletion"
    assert delete_result["speech_cache_entries_cleared"] >= 1, delete_result

speech_service.clear_speech_cache_for_learner("demo-user")
windows_sapi._WORKER = None
print("PASS fast-local content cache: exact content reused across validated revisions; changed text and stale evidence rejected; mute and deletion races cannot cache late audio; SAPI was faked")
