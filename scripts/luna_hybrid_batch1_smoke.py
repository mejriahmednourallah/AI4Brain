"""Isolated contract and HY-05 acceptance smoke for the first Luna gameplay batch."""
from __future__ import annotations

from itertools import permutations
import os
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-luna-hy05-") as temp:
        os.environ["AI4BRAIN_DB"] = str(Path(temp) / "qa.sqlite3")
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app.hybrid_activities_modules.living_archive import generate

        client = TestClient(app)
        session = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True})
        assert session.status_code == 201
        sid = session.json()["id"]
        other = store.create_session(str(uuid.uuid4()), "other-user")
        catalog = client.get("/api/hybrid/catalog").json()
        assert {row["activity_id"] for row in catalog["activities"]} >= {"HY-01", "HY-03", "HY-05", "HY-06"}
        meta = next(row for row in catalog["activities"] if row["activity_id"] == "HY-05")

        # The relational clues have one mathematically valid solution at every tier.
        for tier in ("tutorial", "tier-1", "tier-2", "tier-3"):
            config = generate("replay-seed", "tutorial" if tier == "tutorial" else "training", tier)
            assert config == generate("replay-seed", "tutorial" if tier == "tutorial" else "training", tier)
            objects = [item["object_id"] for item in config["objects"]]
            valid = []
            for order in permutations(objects):
                pos = {name: index for index, name in enumerate(order)}
                if all(pos[c["right"]] == pos[c["left"]] + 1 for c in config["clues"]):
                    valid.append(list(order))
            assert len(valid) == 1, (tier, valid)

        start_event = str(uuid.uuid4())
        body = {"event_id": start_event, "session_id": sid, "activity_id": "HY-05",
                "activity_version": meta["activity_version"], "mode": "training", "difficulty_tier": "tier-1"}
        started = client.post("/api/hybrid/attempts", json=body)
        replay = client.post("/api/hybrid/attempts", json=body)
        assert started.status_code == 201 and replay.status_code == 201
        assert started.json()["attempt_id"] == replay.json()["attempt_id"]
        assert client.post("/api/hybrid/attempts", json={**body, "seed": "different-seed"}).status_code == 409
        assert client.post("/api/hybrid/attempts", json={**body, "config_version": "future"}).status_code == 409
        assert "solution" not in started.json()["config"]
        assert client.post("/api/hybrid/attempts", json={**body, "mode": "challenge"}).status_code == 409
        assert client.post("/api/hybrid/attempts", json={**body, "session_id": other["id"], "learner_id": "demo-user"}).status_code == 403

        config = started.json()["config"]
        objects = [item["object_id"] for item in config["objects"]]
        pos = {name: i for i, name in enumerate(objects)}
        target = next(order for order in permutations(objects)
                      if all({name: i for i, name in enumerate(order)}[c["right"]]
                             == {name: i for i, name in enumerate(order)}[c["left"]] + 1 for c in config["clues"]))
        attempt_id = started.json()["attempt_id"]
        seq = 1

        def action(event_id: str, sequence: int, kind: str, payload: dict) -> dict:
            response = client.post(f"/api/hybrid/attempts/{attempt_id}/actions", json={
                "attempt_id": attempt_id, "event_id": event_id, "sequence": sequence,
                "action_type": kind, "payload": payload,
            })
            assert response.status_code == 201, response.text
            return response.json()

        first_action_id = str(uuid.uuid4())
        first = action(first_action_id, seq, "select", {"object_id": target[0], "slot_index": 0})
        assert first["replayed"] is False
        assert action(first_action_id, seq, "select", {"object_id": target[0], "slot_index": 0})["replayed"] is True
        assert client.post(f"/api/hybrid/attempts/{attempt_id}/actions", json={
            "attempt_id": attempt_id, "event_id": first_action_id, "sequence": seq,
            "action_type": "select", "payload": {"object_id": target[1], "slot_index": 0},
        }).status_code == 409
        seq += 1
        for slot, object_id in enumerate(target[1:], 1):
            action(str(uuid.uuid4()), seq, "select", {"object_id": object_id, "slot_index": slot})
            seq += 1

        exposure_event_id = str(uuid.uuid4())
        exposure = {"event_id": exposure_event_id, "attempt_id": attempt_id, "exposure_kind": "clue_reveal",
                    "checkpoint": "post_commit", "checkpoint_version": "1", "source_event_id": started.json()["event_id"]}
        assert client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=exposure).status_code == 409
        action(str(uuid.uuid4()), seq, "commit", {})
        exposed = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=exposure)
        assert exposed.status_code == 201, exposed.text
        assert client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=exposure).status_code == 201
        assert client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={**exposure, "source_event_id": "changed"}).status_code == 409
        completed = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json={"attempt_id": attempt_id, "event_id": str(uuid.uuid4())})
        assert completed.status_code == 200, completed.text
        result = completed.json()
        assert result["assisted"] and result["excluded_from_unassisted"]
        assert result["outcomes"]["valid_arrangement"] is True
        assert result["outcomes"]["relations_satisfied"] == result["outcomes"]["relations_total"]
        assert exposure_event_id in result["evidence_ids"]
        archive_summary=next(row for row in client.get("/api/hybrid/summary/demo-user").json()["activities"] if row["activity_id"]=="HY-05")
        assert archive_summary["attempts"] == 1

        # An unassisted invalid arrangement returns a specific recorded conflict.
        second_body = {**body, "event_id": str(uuid.uuid4()), "seed": "wrong-layout-seed"}
        second = client.post("/api/hybrid/attempts", json=second_body).json()
        cfg2 = second["config"]
        objects2 = [item["object_id"] for item in cfg2["objects"]]
        target2 = next(order for order in permutations(objects2)
                       if all({name: i for i, name in enumerate(order)}[c["right"]]
                              == {name: i for i, name in enumerate(order)}[c["left"]] + 1 for c in cfg2["clues"]))
        if len(target2) > 1:
            wrong = list(target2); wrong[0], wrong[1] = wrong[1], wrong[0]
        else:
            wrong = target2
        aid2 = second["attempt_id"]
        for sequence, (slot, object_id) in enumerate(enumerate(wrong), 1):
            response = client.post(f"/api/hybrid/attempts/{aid2}/actions", json={
                "attempt_id": aid2, "event_id": str(uuid.uuid4()), "sequence": sequence,
                "action_type": "select", "payload": {"object_id": object_id, "slot_index": slot},
            })
            assert response.status_code == 201, response.text
        committed = client.post(f"/api/hybrid/attempts/{aid2}/actions", json={
            "attempt_id": aid2, "event_id": str(uuid.uuid4()), "sequence": len(wrong) + 1,
            "action_type": "commit", "payload": {},
        })
        assert committed.status_code == 201
        outcome2 = client.post(f"/api/hybrid/attempts/{aid2}/complete", json={
            "attempt_id": aid2, "event_id": str(uuid.uuid4()),
        }).json()
        bad = outcome2["outcomes"]
        assert bad["valid_arrangement"] is False and bad["first_conflict"]
        assert bad["first_conflict"] == next(item for item in bad["conflicts"] if not item["satisfied"])
        assert outcome2["excluded_from_unassisted"] is False

        # A fully valid placement may complete without an explicit commit; an
        # incomplete uncommitted placement cannot be accepted as a success.
        third = client.post("/api/hybrid/attempts", json={**body, "event_id": str(uuid.uuid4()), "seed": "valid-no-commit"}).json()
        cfg3 = third["config"]
        objects3 = [item["object_id"] for item in cfg3["objects"]]
        target3 = next(order for order in permutations(objects3)
                       if all({name: i for i, name in enumerate(order)}[c["right"]]
                              == {name: i for i, name in enumerate(order)}[c["left"]] + 1 for c in cfg3["clues"]))
        for sequence, (slot, object_id) in enumerate(enumerate(target3), 1):
            response = client.post(f"/api/hybrid/attempts/{third['attempt_id']}/actions", json={
                "attempt_id": third["attempt_id"], "event_id": str(uuid.uuid4()), "sequence": sequence,
                "action_type": "select", "payload": {"object_id": object_id, "slot_index": slot},
            })
            assert response.status_code == 201
        valid_without_commit = client.post(f"/api/hybrid/attempts/{third['attempt_id']}/complete", json={
            "attempt_id": third["attempt_id"], "event_id": str(uuid.uuid4()),
        })
        assert valid_without_commit.status_code == 200 and valid_without_commit.json()["outcomes"]["valid_arrangement"]
        fourth = client.post("/api/hybrid/attempts", json={**body, "event_id": str(uuid.uuid4()), "seed": "incomplete-no-commit"}).json()
        rejected = client.post(f"/api/hybrid/attempts/{fourth['attempt_id']}/complete", json={
            "attempt_id": fourth["attempt_id"], "event_id": str(uuid.uuid4()),
        })
        assert rejected.status_code == 409 and client.get(f"/api/hybrid/attempts/{fourth['attempt_id']}").json()["status"] == "started"

        # The hybrid route must not manufacture EX event data or scores.
        assert all(event["type"] == "consent_recorded" for event in store.events(session_id=sid))
        print("luna_hybrid_batch1_smoke: PASS; isolated db; start/action/assistance replay, HY-05 uniqueness, valid/conflicting placements, commit gate, assistance exclusion, and EX isolation")


if __name__ == "__main__":
    main()
