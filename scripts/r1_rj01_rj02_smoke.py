"""Isolated R1 probes for learner lifecycle scope and coaching request identity.

The fixture database is created below ``output/verification`` and removed after
the run.  No primary learner database, provider, or Neo4j instance is used.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from backend.app.lifecycle_service import delete_learner_data, export_learner_data
from backend.app.storage import Store, utc_now


def lifecycle_probe(path: Path) -> dict:
    store = Store(path)
    demo = store.create_session("r1-demo-session", "demo-user")
    other = store.create_session("r1-other-session", "other-learner")
    demo_event_id = str(uuid.uuid4())
    other_event_id = str(uuid.uuid4())
    store.add_event(demo_event_id, demo["id"], "collaboration_opportunity_issued", {
        "event_id": demo_event_id, "session_id": demo["id"], "learner_id": "demo-user",
        "event_type": "collaboration_opportunity_issued", "opportunity_id": "demo-opportunity",
        "sample_data": False, "recorded_at": utc_now(),
    })
    store.add_event(other_event_id, other["id"], "evidence_saved", {
        "event_id": other_event_id, "session_id": other["id"], "learner_id": "other-learner",
        "event_type": "evidence_saved", "sample_data": False, "recorded_at": utc_now(),
    })
    with closing(store.connect()) as db:
        db.execute(
            "INSERT INTO collaboration_claims VALUES (?,?,?,?,?,?,?,?,?)",
            ("demo-claim", "demo-opportunity", None, None, demo_event_id, "demo", "supported", "demo", utc_now()),
        )
        db.execute(
            "INSERT INTO collaboration_claims VALUES (?,?,?,?,?,?,?,?,?)",
            ("other-claim", "other-opportunity", None, other["id"], other_event_id,
             "other", "supported", "other", utc_now()),
        )
        db.commit()
    request_id = "r1-export-turn"
    store.reserve_coach_turn({
        "request_id": request_id, "learner_id": "demo-user", "session_id": demo["id"],
        "coach_version": "coach-v2", "payload_hash": "export-hash", "message": "A saved question.",
        "request": {"session_id": demo["id"], "message": "A saved question.", "request_id": request_id},
    })
    store.complete_coach_turn(request_id, response={"request_id": request_id, "answer": "saved"},
                              status="completed", provider_used="local", model=None)
    store.set_coach_conversation(demo["id"], "demo-user", "local", False, "EX-01")
    store.save_plan({
        "plan_id": "r1-demo-plan", "learner_id": "demo-user", "profile_snapshot_id": None,
        "policy_version": "plan-v2", "goal": "memory", "budget_minutes": 10,
        "estimated_time_minutes": 5, "reason_codes": ["r1"], "rationale": "isolated",
        "steps": [], "evidence_ids": [demo_event_id], "features": {}, "alternatives": [],
        "decision_fingerprint": ["r1"], "status": "active", "created_at": utc_now(),
        "plan_version": "plan-v2", "trigger": "r1-probe", "budget_note": "bounded",
    })
    exported = export_learner_data(store)
    assert len(exported["coach_turns"]) == 1
    assert len(exported["coach_conversations"]) == 1
    assert len(exported["collaboration_claims"]) == 1
    assert exported["training_plans"][0]["plan_extra"]["plan_version"] == "plan-v2"
    assert json.loads(exported["training_plans"][0]["plan_extra_json"])["plan_version"] == "plan-v2"
    assert exported["training_plans"][0]["plan_extra"]["trigger"] == "r1-probe"
    before = path.exists()
    deleted = delete_learner_data(store)
    with closing(store.connect()) as db:
        remaining = {
            "demo_sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE learner_id='demo-user'").fetchone()[0],
            "demo_turns": db.execute("SELECT COUNT(*) FROM coach_turns WHERE learner_id='demo-user'").fetchone()[0],
            "demo_conversations": db.execute("SELECT COUNT(*) FROM coach_conversations WHERE learner_id='demo-user'").fetchone()[0],
            "claims": db.execute("SELECT COUNT(*) FROM collaboration_claims").fetchone()[0],
            "other_sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE learner_id='other-learner'").fetchone()[0],
            "other_claims": db.execute("SELECT COUNT(*) FROM collaboration_claims WHERE claim_id='other-claim'").fetchone()[0],
        }
    assert before and path.exists()
    assert remaining == {"demo_sessions": 0, "demo_turns": 0, "demo_conversations": 0,
                         "claims": 1, "other_sessions": 1, "other_claims": 1}, remaining
    assert deleted["deleted_row_counts"]["coach_turns"] == 1
    assert deleted["deleted_row_counts"]["coach_conversations"] == 1
    assert deleted["deleted_row_counts"]["collaboration_claims"] == 1
    return {"exported": {"coach_turns": 1, "coach_conversations": 1,
                         "collaboration_claims": 1, "plan_extra": True},
            "deleted": deleted["deleted_row_counts"], "remaining": remaining}


class FakeAdapter:
    name = "groq"
    model = "r1-fake-model"
    default_model = "r1-fake-model"

    def __init__(self) -> None:
        self.calls = 0
        self.lock = threading.Lock()
        self.block_next = False
        self.started = threading.Event()
        self.release = threading.Event()

    def configured(self) -> bool:
        return True

    def complete(self, payload, message, baseline, *, transport=None):
        with self.lock:
            self.calls += 1
            should_block = self.block_next
            self.block_next = False
        if should_block:
            self.started.set()
            assert self.release.wait(10), "blocked fake provider was not released"
        time.sleep(0.05)
        return {
            "observation": baseline["observation"],
            "explanation": "The saved evidence is the part to inspect first.",
            "strategy_id": baseline["strategy_id"],
            "follow_up": "Which saved detail should we inspect first?",
            "next_step_note": baseline["next_step_note"],
            "evidence_ids": list(baseline["evidence_ids"]),
            "recommended_exercise_id": baseline["recommended_exercise_id"],
            "recommended_difficulty": baseline["recommended_difficulty"],
            "clarification": None,
        }


def coaching_probe(path: Path) -> dict:
    os.environ["AI4BRAIN_DB"] = str(path)
    from fastapi.testclient import TestClient
    from backend.app import coach_routes
    from backend.app import provider_adapters
    from backend.app.main import app, store

    fake = FakeAdapter()
    provider_adapters.ADAPTERS["groq"] = fake
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        base = {"session_id": sid, "message": "What does my saved evidence suggest?",
                "provider": "groq", "allow_remote": True, "provider_consent_recorded": True}
        request_id = "r1-json-request"
        first = client.post("/api/coach", json={**base, "request_id": request_id})
        assert first.status_code == 200, first.text
        first.json()
        replay = client.post("/api/coach", json={**base, "request_id": request_id})
        assert replay.status_code == 200 and replay.json()["replayed"] is True
        conflict = client.post("/api/coach", json={**base, "request_id": request_id,
                                                     "message": "A conflicting payload."})
        assert conflict.status_code == 409
        sse = client.post("/api/coach/stream", json={**base, "request_id": request_id})
        assert sse.status_code == 200 and "event: answer" in sse.text
        assert fake.calls == 1
        with closing(store.connect()) as db:
            event_count = db.execute(
                "SELECT COUNT(*) FROM events WHERE type='coaching_message_sent'").fetchone()[0]
        assert event_count == 1

        concurrent_id = "r1-concurrent-request"
        concurrent_body = {**base, "request_id": concurrent_id}

        def json_call():
            with TestClient(app) as local:
                return local.post("/api/coach", json=concurrent_body)

        def sse_call():
            with TestClient(app) as local:
                return local.post("/api/coach/stream", json=concurrent_body)

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda call: call(), (json_call, sse_call)))
        assert all(response.status_code in {200, 409} for response in responses)
        concurrent_statuses = sorted(response.status_code for response in responses)
        assert concurrent_statuses == [200, 409], concurrent_statuses
        assert fake.calls == 2, fake.calls
        with closing(store.connect()) as db:
            concurrent_events = db.execute(
                "SELECT COUNT(*) FROM events WHERE type='coaching_message_sent' "
                "AND json_extract(payload_json,'$.request_id')=?", (concurrent_id,)).fetchone()[0]
        assert concurrent_events == 1

        failed_id = "r1-failed-retry"
        failed_body = {**base, "request_id": failed_id}
        failed_request = coach_routes.CoachRequest(**failed_body)
        store.reserve_coach_turn({
            "request_id": failed_id, "learner_id": "demo-user", "session_id": sid,
            "coach_version": "coach-v2", "payload_hash": coach_routes._payload_hash(failed_request),
            "message": failed_request.message, "request": failed_request.model_dump(),
        })
        blocked = client.post("/api/coach", json=failed_body)
        assert blocked.status_code == 409 and fake.calls == 2
        store.fail_coach_turn(failed_id, "simulated_failure")
        failed = client.post("/api/coach", json=failed_body)
        assert failed.status_code == 200
        assert client.post("/api/coach", json=failed_body).json()["replayed"] is True
        with closing(store.connect()) as db:
            canonical_events_before_delete = db.execute(
                "SELECT COUNT(*) FROM events WHERE type='coaching_message_sent'").fetchone()[0]
        other = store.create_session("r1-delete-other-session", "other-learner")
        blocked_id = "r1-delete-in-flight"
        blocked_body = {**base, "request_id": blocked_id}
        fake.block_next = True
        response_holder = []

        def blocked_call():
            with TestClient(app) as local:
                response_holder.append(local.post("/api/coach", json=blocked_body))

        worker = threading.Thread(target=blocked_call)
        worker.start()
        assert fake.started.wait(10), "request did not reach the blocked provider"
        deleted = delete_learner_data(store, "demo-user")
        fake.release.set()
        worker.join(10)
        assert not worker.is_alive() and response_holder and response_holder[0].status_code == 409
        with closing(store.connect()) as db:
            after_delete = {
                "target_sessions": db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE learner_id='demo-user'").fetchone()[0],
                "target_turns": db.execute(
                    "SELECT COUNT(*) FROM coach_turns WHERE learner_id='demo-user'").fetchone()[0],
                "target_conversations": db.execute(
                    "SELECT COUNT(*) FROM coach_conversations WHERE learner_id='demo-user'").fetchone()[0],
                "target_events": db.execute(
                    "SELECT COUNT(*) FROM events e JOIN sessions s ON s.id=e.session_id "
                    "WHERE s.learner_id='demo-user'").fetchone()[0],
                "other_sessions": db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE learner_id='other-learner'").fetchone()[0],
            }
        assert path.exists()
        assert after_delete == {
            "target_sessions": 0, "target_turns": 0, "target_conversations": 0,
            "target_events": 0, "other_sessions": 1,
        }, after_delete
        assert deleted["database_file_preserved"] is True
        return {"json_replay": True, "sse_replay": True, "conflict_status": conflict.status_code,
                "in_progress_status": blocked.status_code, "failed_retry": True,
                "concurrent_statuses": concurrent_statuses,
                "provider_calls": fake.calls,
                "canonical_events_before_delete": canonical_events_before_delete,
                "delete_in_flight_status": response_holder[0].status_code,
                "delete_afterward": after_delete}


def main() -> None:
    receipt = ROOT / "output" / "verification" / "r1-rj01-rj02.json"
    isolated_dir = ROOT / "output" / "verification" / "r1-isolated"
    isolated_dir.mkdir(parents=True, exist_ok=True)
    lifecycle_db = isolated_dir / "lifecycle.sqlite3"
    coaching_db = isolated_dir / "coaching.sqlite3"
    for path in (lifecycle_db, coaching_db):
        if path.exists():
            path.unlink()
    result = {"scope": "RJ-01/RJ-02", "isolated": True,
              "lifecycle": lifecycle_probe(lifecycle_db),
              "coaching": coaching_probe(coaching_db)}
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.rmtree(isolated_dir, ignore_errors=True)
    print("PASS R1 RJ-01/RJ-02:", json.dumps(result["coaching"], sort_keys=True))


if __name__ == "__main__":
    main()
