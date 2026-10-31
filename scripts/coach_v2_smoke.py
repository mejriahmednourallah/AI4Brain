"""coach-v2 provider, persistence and streaming checks with no live network.

Both adapters are exercised through deterministic in-process transports, so a passing
result proves the adapter contract, validation and recovery paths — not that a hosted
provider is reachable or that its prose is good.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUESTION = "Why did my Memory answers lose the order, and what should I try?"


class FakeAdapter:
    """Deterministic stand-in for a hosted adapter; never touches the network."""

    def __init__(self, name: str, reply: dict | None = None, raises: Exception | None = None):
        self.name = name
        self.default_model = f"{name}-default-model"
        self.model = f"{name}-model-under-test"
        self.reply = reply
        self.raises = raises
        self.calls = 0
        self.last_payload: dict | None = None

    def configured(self) -> bool:
        return True

    def complete(self, payload, message, baseline, *, transport=None):
        self.calls += 1
        self.last_payload = payload
        if self.raises:
            raise self.raises
        # A real provider returns only the declared schema fields, never backend extras.
        return dict(self.reply or {})


def generated(baseline: dict, **changes) -> dict:
    return {
        "observation": baseline["observation"],
        "explanation": "Your saved responses lost the order between the cue and your answer.",
        "strategy_id": baseline["strategy_id"],
        "follow_up": "Which part of the saved evidence should we inspect first?",
        "next_step_note": baseline["next_step_note"],
        "evidence_ids": list(baseline["evidence_ids"]),
        "recommended_exercise_id": baseline["recommended_exercise_id"],
        "recommended_difficulty": baseline["recommended_difficulty"],
        "clarification": None,
        **changes,
    }


with tempfile.TemporaryDirectory(prefix="ai4brain-coach-v2-") as folder:
    os.environ["AI4BRAIN_DB"] = str(Path(folder) / "coach-v2.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"
    os.environ["GROQ_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""

    import httpx
    from fastapi.testclient import TestClient
    from backend.app import provider_adapters
    from backend.app import coach_routes
    from backend.app.main import app, store
    from backend.app.coach_v2 import (MAX_SPOKEN_SUMMARY_CHARS, SPOKEN_SUMMARY_FALLBACK,
                                      grounded_spoken_summary)
    from backend.app.twin_context import FAMILIES

    # Spoken summaries are server-rendered from the canonical family snapshot,
    # remain short, and never borrow another family's fact for a mismatched subject.
    for exercise_id, family_config in FAMILIES.items():
        family = {"exercise_id": exercise_id, "label": family_config["label"], "completed": True,
                  "index_0_100": 62.5, "uncertainty_status": "PRELIMINARY_HIGH_UNCERTAINTY"}
        context = {"evidence_revision": "fixture-revision", "families": {family_config["dimension"]: family}}
        subject = {"exercise_id": exercise_id, "dimension": family_config["dimension"], "source": "explicit"}
        summary = grounded_spoken_summary(context, subject)
        assert family_config["label"] in summary and "62.5" in summary and "high uncertainty" in summary
        assert len(summary) <= MAX_SPOKEN_SUMMARY_CHARS

    precision_config = FAMILIES["EX-05"]
    precision_family = {"exercise_id": "EX-05", "label": precision_config["label"], "completed": True,
                        "index_0_100": 83.33, "uncertainty_status": "PRELIMINARY_HIGH_UNCERTAINTY"}
    precision_summary = grounded_spoken_summary({"evidence_revision": "fixture-revision",
        "families": {precision_config["dimension"]: precision_family}}, {
        "exercise_id": "EX-05", "dimension": precision_config["dimension"], "source": "explicit"})
    assert "83.33" in precision_summary and "83.3 out" not in precision_summary

    unassessed_config = FAMILIES["EX-04"]
    unassessed = {"exercise_id": "EX-04", "label": unassessed_config["label"], "completed": False,
                  "index_0_100": None, "uncertainty_status": "INCOMPLETE_BASELINE"}
    unassessed_context = {"evidence_revision": "fixture-revision",
                          "families": {unassessed_config["dimension"]: unassessed}}
    unassessed_summary = grounded_spoken_summary(unassessed_context, {
        "exercise_id": "EX-04", "dimension": unassessed_config["dimension"], "source": "explicit"})
    assert "unassessed" in unassessed_summary.casefold() and "index" in unassessed_summary.casefold()
    assert "62.5" not in unassessed_summary and len(unassessed_summary) <= MAX_SPOKEN_SUMMARY_CHARS
    stale_subject = grounded_spoken_summary(unassessed_context, {
        "exercise_id": "EX-05", "dimension": unassessed_config["dimension"], "source": "explicit"})
    stale_context = grounded_spoken_summary({"families": {unassessed_config["dimension"]: unassessed}}, {
        "exercise_id": "EX-04", "dimension": unassessed_config["dimension"], "source": "explicit"})
    assert stale_subject == SPOKEN_SUMMARY_FALLBACK and stale_context == SPOKEN_SUMMARY_FALLBACK
    unresolved = grounded_spoken_summary({"evidence_revision": "fixture-revision", "families": {}},
        {"exercise_id": None, "dimension": None, "source": "unresolved"})
    assert "which task family" in unresolved.casefold() and len(unresolved) <= MAX_SPOKEN_SUMMARY_CHARS

    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        memory = client.get("/api/exercises/EX-01", params={"phase": "baseline", "session_id": sid}).json()
        for item in memory["items"]:
            sequence = list(item["stimulus"]["sequence"])
            chosen = [sequence[0], *[((position + 1) % 9) for position in sequence[1:]]]
            saved = client.post("/api/trials", json={
                "session_id": sid, "event_id": str(uuid.uuid4()), "exercise_id": "EX-01",
                "exercise_version": memory["exercise_version"], "phase": "baseline",
                "item_id": item["item_id"], "response_data": {"selected_sequence": chosen},
                "response_time_ms": 1300})
            assert saved.status_code == 200, saved.text

        # 1. Provider status never exposes credentials.
        status = client.get("/api/coach/providers").json()
        assert set(status["providers"]) == {"groq", "gemini"}, status
        assert all(item["configured"] is False for item in status["providers"].values()), status
        assert "key" not in json.dumps(status).casefold(), status
        assert status["providers"]["groq"]["default_model"] == "openai/gpt-oss-20b", status
        assert status["providers"]["gemini"]["default_model"] == "gemini-3.8-flash", status

        # 2. A Memory question must resolve to Memory, not the next recommendation.
        base = client.post("/api/coach", json={"session_id": sid, "message": QUESTION}).json()
        assert base["subject"]["label"] == "Memory", base["subject"]
        assert base["subject"]["resolved_from"] in {"explicit", "current_activity", "conversation_subject"}, base["subject"]
        assert str(client.get("/api/profile/demo-user").json()["dimensions"]["working_memory"]["index_0_100"]) in \
            base["response"]["observation"], base["response"]["observation"]
        assert base["spoken_summary"] and len(base["spoken_summary"]) <= MAX_SPOKEN_SUMMARY_CHARS
        assert "Memory" in base["spoken_summary"] and "uncertainty" in base["spoken_summary"].casefold()

        # 3. Hosted provider without consent must not send anything.
        fake = FakeAdapter("groq")
        provider_adapters.ADAPTERS["groq"] = fake
        gated = client.post("/api/coach", json={"session_id": sid, "message": QUESTION, "allow_remote": True,
                                                "provider": "groq", "provider_consent_recorded": False}).json()
        assert gated["provider_status"] == "consent_required", gated["provider_status"]
        assert gated["provider_used"] == "local" and fake.calls == 0, (gated["provider_used"], fake.calls)

        # 4. A validated generated answer keeps the backend's factual summary.
        baseline = gated["response"]
        fake.reply = generated(base["response"])
        remote = client.post("/api/coach", json={"session_id": sid, "message": QUESTION, "allow_remote": True,
                                                 "provider": "groq", "provider_consent_recorded": True}).json()
        assert remote["source"] == "configured_provider" and remote["provider_status"] == "validated", remote
        assert remote["provider_used"] == "groq" and remote["model"] == "groq-model-under-test", remote
        assert remote["response"]["observation"] == base["response"]["observation"], "observation must stay backend-rendered"
        assert remote["spoken_summary"] == base["spoken_summary"]
        assert remote["response"]["generated_explanation"] is True, remote["response"]
        assert fake.last_payload and "prior_turns" in fake.last_payload, "bounded context must be sent"

        # 5. Invented numbers, identifiers and strategies are rejected, with a labelled fallback.
        for changes in ({"explanation": "You improved by 30 points."},
                        {"evidence_ids": ["invented-id"]},
                        {"strategy_id": "made-up-strategy"},
                        {"recommended_exercise_id": "EX-99"},
                        {"recommended_difficulty": "tier-9"},
                        {"follow_up": "x" * 500}):
            fake.reply = generated(base["response"], **changes)
            refused = client.post("/api/coach", json={"session_id": sid, "message": QUESTION, "allow_remote": True,
                                                      "provider": "groq", "provider_consent_recorded": True}).json()
            assert refused["source"] == "local_fallback", changes
            assert refused["provider_status"] == "unavailable_or_invalid", (changes, refused["provider_status"])
            assert refused["provider_used"] == "local", refused["provider_used"]

        # 6. A provider outage falls back without forwarding to the other provider.
        gemini = FakeAdapter("gemini", raises=httpx.ReadTimeout("timeout"))
        provider_adapters.ADAPTERS["gemini"] = gemini
        groq_calls_before = fake.calls
        outage = client.post("/api/coach", json={"session_id": sid, "message": QUESTION, "allow_remote": True,
                                                 "provider": "gemini", "provider_consent_recorded": True}).json()
        assert outage["source"] == "local_fallback" and outage["provider_status"] == "timeout", outage
        assert outage["provider_requested"] == "gemini", outage["provider_requested"]
        assert fake.calls == groq_calls_before, "a failed Gemini call must not be rerouted to Groq"
        assert gemini.calls == 1, gemini.calls

        # 7. Exact retries reconcile one turn; conflicting payloads are rejected.
        request_id = str(uuid.uuid4())
        body = {"session_id": sid, "message": QUESTION, "request_id": request_id, "provider": "local"}
        first = client.post("/api/coach", json=body)
        assert first.status_code == 200, first.text
        replay = client.post("/api/coach", json=body)
        assert replay.status_code == 200 and replay.json().get("replayed") is True, replay.text
        assert replay.json()["event_id"] == first.json()["event_id"], "an exact retry must reuse the same turn"
        conflict = client.post("/api/coach", json={**body, "message": QUESTION + " Also, why?"})
        assert conflict.status_code == 409, conflict.text
        turns = [e for e in store.events(learner_id="demo-user") if e["type"] == "coaching_message_sent"]
        assert len([e for e in turns if (e["payload"] or {}).get("request_id") == request_id]) == 1, turns

        # 8. The conversation is restorable after reload.
        history = client.get("/api/coach/conversation", params={"session_id": sid}).json()
        assert history["turns"], history
        assert history["subject_exercise_id"] == "EX-01", history["subject_exercise_id"]
        assert all(turn["request_id"] and turn["status"] for turn in history["turns"]), history["turns"]

        # 9. The grounded local answer is emitted before any optional provider prose.
        other_session = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        stream = client.post("/api/coach/stream", json={"session_id": sid, "message": QUESTION,
                                                       "provider": "local", "request_id": str(uuid.uuid4())})
        assert stream.status_code == 200, stream.text
        events = [line.split(":", 1)[1].strip() for line in stream.text.splitlines() if line.startswith("event:")]
        assert events[:3] == ["acknowledged", "evidence", "local_response"], events
        assert events[-2:] == ["answer", "done"], events
        local_payload = [line for line in stream.text.splitlines() if line.startswith("data: ")][2]
        local_parsed = json.loads(local_payload[len("data: "):])
        evidence_payload = [line for line in stream.text.splitlines() if line.startswith("data: ")][1]
        evidence_parsed = json.loads(evidence_payload[len("data: "):])
        assert local_parsed["source"] == "server_grounded_local", local_parsed
        assert local_parsed["label"] == "Local answer.", local_parsed
        assert local_parsed["evidence_revision"] and local_parsed["response"]["observation"], local_parsed
        assert local_parsed["spoken_summary"] and len(local_parsed["spoken_summary"]) <= MAX_SPOKEN_SUMMARY_CHARS
        answer_payload = [line for line in stream.text.splitlines() if line.startswith("data: ")][-2]
        parsed = json.loads(answer_payload[len("data: "):])
        assert parsed["response"]["observation"], parsed
        assert parsed["spoken_summary"] == local_parsed["spoken_summary"]
        assert local_parsed["request_id"] == parsed["request_id"]
        assert local_parsed["subject"] == parsed["subject"]
        assert local_parsed["evidence_revision"] == parsed["evidence_revision"]
        assert evidence_parsed["evidence_revision"] == parsed["evidence_revision"], \
            (evidence_parsed["evidence_revision"], parsed["evidence_revision"])

        # A local reply remains playable after its own non-evidence records and
        # another session's consent append to the learner-wide event stream.
        from backend.app import windows_sapi
        from backend.app import speech_service
        import io
        import wave
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(22050); audio.writeframes(bytes(22050))

        class FakeSapiWorker:
            voice_name = "Synthetic local voice"
            calls = 0

            def synthesize(self, _text):
                self.calls += 1
                return audio_buffer.getvalue()

            def shutdown(self):
                return None

        # A second-session consent appended after the answer must not detach the
        # spoken summary from the learner-wide revision used by that answer.
        later_session = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        assert later_session != sid
        speech_preferences = client.post("/api/companion/speech/preferences", json={
            "session_id": sid, "mode": "fast_local", "enabled": True, "voice": "Bella", "speed": 1.0})
        assert speech_preferences.status_code == 200, speech_preferences.text
        fake_sapi = FakeSapiWorker()
        windows_sapi._WORKER = fake_sapi
        speech_body = {"session_id": sid, "text": parsed["spoken_summary"],
                       "evidence_revision": parsed["evidence_revision"],
                       "subject": parsed.get("subject", {}).get("exercise_id") or "EX-01"}
        speech_response = client.post("/api/companion/speech/fast-local", json=speech_body)
        assert speech_response.status_code == 200, speech_response.text
        assert speech_response.headers["x-speech-cache"] == "miss" and fake_sapi.calls == 1
        speech_replay = client.post("/api/companion/speech/fast-local", json=speech_body)
        assert speech_replay.status_code == 200 and speech_replay.headers["x-speech-cache"] == "hit"
        assert fake_sapi.calls == 1

        # 9a. A slow mocked provider cannot delay the local fallback past the configured deadline.
        class SlowAdapter(FakeAdapter):
            def complete(self, payload, message, baseline, *, transport=None):
                self.calls += 1
                time.sleep(0.15)
                return generated(baseline)

        old_adapter = provider_adapters.ADAPTERS["gemini"]
        old_deadline = coach_routes.REMOTE_DEADLINE_SECONDS
        slow = SlowAdapter("gemini")
        provider_adapters.ADAPTERS["gemini"] = slow
        coach_routes.REMOTE_DEADLINE_SECONDS = 0.02
        slow_body = coach_routes.CoachRequest(session_id=sid, message=QUESTION, allow_remote=True,
                                              provider="gemini", provider_consent_recorded=True)
        slow_built = coach_routes._build_answer(store, slow_body)
        started = time.perf_counter()
        coach_routes._apply_optional_explanation(store, slow_body, slow_built)
        elapsed = time.perf_counter() - started
        assert elapsed < 0.12, elapsed
        assert slow_built["answer"]["provider_status"] == "timeout", slow_built["answer"]
        time.sleep(0.18)
        assert slow_built["answer"]["provider_status"] == "timeout", "late prose must not overwrite the fallback"
        coach_routes.REMOTE_DEADLINE_SECONDS = old_deadline
        provider_adapters.ADAPTERS["gemini"] = old_adapter
        assert provider_adapters.TOTAL_TIMEOUT_SECONDS == 8.0

        class ContextChangingAdapter(FakeAdapter):
            def complete(self, payload, message, baseline, *, transport=None):
                event_id = str(uuid.uuid4())
                store.add_event(event_id, sid, "mock_context_changed", {"event_id": event_id,
                    "session_id": sid, "learner_id": "demo-user", "sample_data": True})
                return generated(baseline)

        provider_adapters.ADAPTERS["gemini"] = ContextChangingAdapter("gemini")
        stale_body = coach_routes.CoachRequest(session_id=sid, message=QUESTION, allow_remote=True,
                                               provider="gemini", provider_consent_recorded=True)
        stale_built = coach_routes._build_answer(store, stale_body)
        local_explanation = stale_built["answer"]["response"]["explanation"]
        coach_routes._apply_optional_explanation(store, stale_body, stale_built)
        assert stale_built["answer"]["provider_status"] == "stale_context", stale_built["answer"]
        assert stale_built["answer"]["fallback_reason"] == "evidence_revision_changed"
        assert stale_built["answer"]["response"]["explanation"] == local_explanation
        provider_adapters.ADAPTERS["gemini"] = old_adapter

        # An exact retry during an active remote wait receives persisted progress without a second call.
        pending_adapter = FakeAdapter("gemini", reply={})
        provider_adapters.ADAPTERS["gemini"] = pending_adapter
        pending_id = str(uuid.uuid4())
        pending_body = coach_routes.CoachRequest(session_id=sid, message=QUESTION, allow_remote=True,
                                                 provider="gemini", provider_consent_recorded=True,
                                                 request_id=pending_id)
        pending_body, pending_state, pending_turn = coach_routes._reserve(store, pending_body)
        assert pending_state == "owner"
        pending_built = coach_routes._build_answer(store, pending_body)
        pending_progress = coach_routes._local_progress(pending_body, pending_built)
        store.save_coach_progress(pending_id, pending_progress,
                                  lifecycle_generation=int(pending_turn["lifecycle_generation"]))
        retry_during_wait = client.post("/api/coach", json={
            "session_id": sid, "message": QUESTION, "allow_remote": True, "provider": "gemini",
            "provider_consent_recorded": True, "request_id": pending_id,
        })
        assert retry_during_wait.status_code == 200, retry_during_wait.text
        assert retry_during_wait.json()["replayed"] is True
        assert retry_during_wait.json()["label"] == "Local answer; explanation pending."
        assert pending_adapter.calls == 0, pending_adapter.calls
        provider_adapters.ADAPTERS["gemini"] = old_adapter

        # 10. Coaching never changes canonical indices.
        profile = client.get("/api/profile/demo-user").json()["dimensions"]["working_memory"]
        assert profile["index_0_100"] is not None and profile["evidence_count"] == 6, profile

        # A new scored event in another learner session invalidates that saved
        # reply revision and cannot synthesize or reuse the prior cached audio.
        other_baseline = client.get("/api/exercises/EX-01", params={
            "phase": "baseline", "session_id": other_session}).json()
        other_item = other_baseline["items"][0]
        scored = client.post("/api/trials", json={
            "session_id": other_session, "event_id": str(uuid.uuid4()), "exercise_id": "EX-01",
            "exercise_version": other_baseline["exercise_version"], "phase": "baseline",
            "item_id": other_item["item_id"],
            "response_data": {"selected_sequence": list(other_item["stimulus"]["sequence"])},
            "response_time_ms": 1200,
        })
        assert scored.status_code == 200, scored.text
        stale_reply = client.post("/api/companion/speech/fast-local", json=speech_body)
        assert stale_reply.status_code == 409 and fake_sapi.calls == 1, stale_reply.text

print("PASS coach-v2: provider status, subject resolution, consent gate, validated generation, "
      "invented-value rejection, timeout fallback, exact-retry reconciliation, restore and local-first SSE order")
