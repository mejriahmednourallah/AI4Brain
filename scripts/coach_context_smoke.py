"""Reproduce the judge finding: a Memory question must not receive missing-Reasoning advice.

Disposable SQLite, graph network off, no remote provider. The assertions distinguish
observed evidence (saved Memory trials) from a learner question about that evidence.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUESTION = "I struggled to remember the route. How should I change my strategy, and what exactly do my mistakes show?"

with tempfile.TemporaryDirectory(prefix="ai4brain-coach-context-") as folder:
    os.environ["AI4BRAIN_DB"] = str(Path(folder) / "coach.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"
    from fastapi.testclient import TestClient
    from backend.app.main import app

    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        memory = client.get("/api/exercises/EX-01", params={"phase": "baseline", "session_id": sid}).json()
        assert memory["exercise_version"] == "memory-v2", memory.get("exercise_version")

        # Three of twenty-four recalled positions: the judge's observed Memory state.
        correct = 0
        for item in memory["items"]:
            sequence = list(item["stimulus"]["sequence"])
            # Keep exactly the first position right and shift the rest: 3/24 overall.
            chosen = [sequence[0], *[((position + 1) % 9) for position in sequence[1:]]]
            correct += 1
            body = {
                "session_id": sid,
                "event_id": str(uuid.uuid4()),
                "exercise_id": memory["exercise_id"],
                "exercise_version": memory["exercise_version"],
                "phase": memory["phase"],
                "item_id": item["item_id"],
                "response_data": {"selected_sequence": chosen},
                "response_time_ms": 1400,
            }
            saved = client.post("/api/trials", json=body)
            assert saved.status_code == 200, saved.text

        profile = client.get("/api/profile/demo-user").json()["dimensions"]["working_memory"]
        assert profile["correct_positions"] == correct and profile["index_0_100"] == round(100 * correct / 24, 2), profile

        reply = client.post("/api/coach", json={"session_id": sid, "message": QUESTION, "phase": "overview"})
        assert reply.status_code == 200, reply.text
        payload = reply.json()
        text = " ".join(
            str(payload["response"].get(field, ""))
            for field in ("observation", "explanation", "rationale", "follow_up")
        ).casefold()

        # The answer must reflect the observed Memory evidence.
        assert "memory" in text or "working memory" in text, text
        assert "insufficient comparable baseline" not in text, text
        assert "complete the uncoached baseline first" not in text.casefold(), text
        # The quoted index must be the canonical saved value, not a plausible-looking number.
        assert str(profile["index_0_100"]) in text, (profile["index_0_100"], text)

        # A next step may be mentioned, but it must not replace the answer to the question.
        primary = str(payload["response"].get("observation", "")).casefold()
        assert "memory" in primary or "working memory" in primary, primary

        # No score or policy change from coaching, and the turn is recorded as assistance-free context.
        after = client.get("/api/profile/demo-user").json()["dimensions"]["working_memory"]
        assert after["index_0_100"] == profile["index_0_100"], after
        assert payload["source"] == "local_fallback" and payload["assisted_training"] is False, payload

print("PASS coach-context: a completed Memory baseline answers a Memory question with its own observed evidence and strategy")
