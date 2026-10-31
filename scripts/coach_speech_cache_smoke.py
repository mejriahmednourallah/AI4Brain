"""Session-scoped Bella preference, warmup and private audio-cache checks; no model/network calls."""
from __future__ import annotations

import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import speech_service


class MemoryStore:
    def __init__(self):
        self.rows = {
            "s-consented": [{"event_id": "consent-1", "type": "consent_recorded",
                             "payload": {"consent": {"accepted": True}}}],
            "s-other-consented": [{"event_id": "consent-2", "type": "consent_recorded",
                                   "payload": {"consent": {"accepted": True}}}],
            "s-no-consent": [],
        }

    def get_session(self, session_id):
        return {"id": session_id, "learner_id": "demo-user"} if session_id.startswith("s-") else None

    def events(self, session_id=None, **_kwargs):
        return list(self.rows.get(session_id, []))

    def add_event(self, event_id, session_id, event_type, payload):
        row = {"event_id": event_id, "session_id": session_id, "type": event_type, "payload": payload}
        self.rows.setdefault(session_id, []).append(row)
        return row, False

    def connect(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE learner_lifecycle (learner_id TEXT, generation INTEGER, deleting INTEGER)")
        return db


class FakeEngine:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self.calls = 0
        self.warm_calls = 0

    def warm_background(self):
        self.warm_calls += 1
        return {"accepted": True, "warm_state": "warming"}

    def reserve(self):
        return 1

    def synthesise(self, _ticket, _text, _voice, _speed):
        self.calls += 1
        return b"RIFF" + bytes(80)


store = MemoryStore()
engine = FakeEngine()
speech_service.clear_speech_cache_for_learner("demo-user")
speech_service.get_engine = lambda: engine
app = FastAPI()
speech_service.register_speech_routes(app, store)

with TestClient(app) as client:
    denied = client.post("/api/companion/speech/warm", json={"session_id": "s-no-consent"})
    assert denied.status_code == 409, denied.text
    saved = client.post("/api/companion/speech/preferences", json={
        "session_id": "s-consented", "mode": "bella", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert saved.status_code == 200, saved.text
    read = client.get("/api/companion/speech/preferences", params={"session_id": "s-consented"})
    assert read.json()["preferences"]["mode"] == "bella" and read.json()["preferences"]["enabled"] is True
    warm = client.post("/api/companion/speech/warm", json={"session_id": "s-consented"})
    assert warm.status_code == 200 and warm.json()["warm_state"] == "warming", warm.text
    assert engine.warm_calls == 1

    request = {"session_id": "s-consented", "evidence_revision": "rev-a", "subject": "EX-01",
               "text": "A short private explanation.", "voice": "Bella", "speed": 1.0}
    first = client.post("/api/companion/speech", json=request)
    second = client.post("/api/companion/speech", json=request)
    assert first.status_code == second.status_code == 200
    assert first.headers["x-speech-cache"] == "miss" and second.headers["x-speech-cache"] == "hit"
    assert engine.calls == 1, engine.calls
    changed_revision = client.post("/api/companion/speech", json={**request, "evidence_revision": "rev-b"})
    assert changed_revision.headers["x-speech-cache"] == "miss" and engine.calls == 2
    other_pref = client.post("/api/companion/speech/preferences", json={
        "session_id": "s-other-consented", "mode": "bella", "enabled": True, "voice": "Bella", "speed": 1.0,
    })
    assert other_pref.status_code == 200
    other_session = client.post("/api/companion/speech", json={**request, "session_id": "s-other-consented"})
    assert other_session.headers["x-speech-cache"] == "miss" and engine.calls == 3
    assert speech_service.clear_speech_cache_for_learner("demo-user") == 2
    after_delete = client.post("/api/companion/speech", json=request)
    assert after_delete.headers["x-speech-cache"] == "miss" and engine.calls == 4

engine._executor.shutdown(wait=True)
print("PASS companion speech: consent-scoped preference, non-blocking opted-in warm request, "
      "revision/session-private cache key and learner cache clear; synthesis/model were faked")
