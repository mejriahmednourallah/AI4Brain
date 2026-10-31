"""Supervisor regression: original activities participate in scoped data lifecycle."""
from __future__ import annotations

import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-luna-lifecycle-") as folder:
        os.environ["AI4BRAIN_DB"] = str(Path(folder) / "qa.sqlite3")
        os.environ["NEO4J_ENABLED"] = "false"
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app.lifecycle_service import delete_learner_data, export_learner_data

        with TestClient(app) as client:
            catalog = client.get('/api/hybrid/catalog')
            assert catalog.status_code == 200, catalog.text
            courier = next(activity for activity in catalog.json()['activities'] if activity['activity_id'] == 'HY-01')
            attempts = {}
            for learner in ("demo-user", "qa-other-learner"):
                if learner == "demo-user":
                    response = client.post("/api/sessions", json={"learner_id": learner, "consent_accepted": True})
                    assert response.status_code == 201, response.text
                    session = response.json()["id"]
                else:
                    # The POC API intentionally supports only demo-user. Seed an unrelated
                    # storage fixture to prove deletion does not broaden its scope.
                    session = store.create_session("qa-other-session", learner)["id"]
                started = client.post("/api/hybrid/attempts", json={
                    "event_id": str(uuid.uuid4()), "session_id": session, "learner_id": learner,
                    "activity_id": "HY-01", "activity_version": courier['activity_version'],
                    "config_version": courier['config_version'], "seed": "lifecycle-software-qa",
                })
                assert started.status_code == 201, started.text
                attempt = started.json()["attempt_id"]
                attempts[learner] = attempt
                helped = client.post(f"/api/hybrid/attempts/{attempt}/assistance", json={
                    "event_id": str(uuid.uuid4()), "attempt_id": attempt,
                    "exposure_kind": "intention_reminder", "checkpoint": "pre_play",
                })
                assert helped.status_code == 201, helped.text
                completed = client.post(f"/api/hybrid/attempts/{attempt}/complete", json={
                    "event_id": str(uuid.uuid4()), "attempt_id": attempt, "interrupted": True,
                })
                assert completed.status_code == 200, completed.text
                assert completed.json()["excluded_from_unassisted"] is True
                crystal = client.post('/api/crystal/attempts', json={
                    'event_id': str(uuid.uuid4()), 'session_id': session, 'learner_id': learner,
                    'seed': 'lifecycle-crystal-software-qa',
                })
                assert crystal.status_code == 201, crystal.text
                crystal_data = crystal.json()
                answered = client.post(f"/api/crystal/attempts/{crystal_data['attempt_id']}/answer", json={
                    'event_id': str(uuid.uuid4()), 'choice_id': crystal_data['config']['choices'][0]['choice_id'],
                    'response_time_ms': 1234,
                })
                assert answered.status_code == 200, answered.text

            exported = export_learner_data(store)
            assert len(exported["hybrid_attempts"]) == 1
            assert len(exported["hybrid_events"]) == 3
            assert len(exported["hybrid_assistance"]) == 1
            assert len(exported["hybrid_outcomes"]) == 1
            assert exported["hybrid_attempts"][0]["attempt_id"] == attempts["demo-user"]
            assert "config" in exported["hybrid_attempts"][0]
            assert exported["hybrid_outcomes"][0]["assisted"] is True
            assert [len(exported[key]) for key in ('crystal_attempts', 'crystal_events', 'crystal_outcomes')] == [1, 2, 1]
            other_before = export_learner_data(store, "qa-other-learner")
            with closing(store.connect()) as db:
                before = {r["name"]: r["sql"] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")}
            deleted = delete_learner_data(store)
            assert deleted["deleted_row_counts"]["hybrid_attempts"] == 1
            assert deleted["deleted_row_counts"]["hybrid_events"] == 3
            assert deleted['deleted_row_counts']['crystal_events'] == 2
            empty = export_learner_data(store)
            assert all(not empty[key] for key in ("sessions", "events", "hybrid_attempts", "hybrid_events", "hybrid_assistance", "hybrid_outcomes", "crystal_attempts", "crystal_events", "crystal_outcomes"))
            other_after = export_learner_data(store, "qa-other-learner")
            for key in other_before:
                if key != "exported_at":
                    assert other_before[key] == other_after[key], key
            with closing(store.connect()) as db:
                after = {r["name"]: r["sql"] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")}
                assert before == after
                try:
                    db.execute("DELETE FROM hybrid_events WHERE attempt_id=?", (attempts["qa-other-learner"],))
                except sqlite3.IntegrityError:
                    pass
                else:
                    raise AssertionError("hybrid immutability guard missing after deletion")
            print(json.dumps({"pass": True, "hybrid_export": [1, 3, 1, 1], "crystal_export": [1, 2, 1], "scoped_delete": True,
                              "other_learner_unchanged": True, "all_triggers_restored": True}))


if __name__ == "__main__":
    main()
