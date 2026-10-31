"""Batch 1 capability and lifecycle contract checks on a disposable SQLite DB."""
from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"


def uid() -> str:
    return str(uuid.uuid4())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-hybrid-foundation-") as temp:
        os.environ["AI4BRAIN_DB"] = str(Path(temp) / "qa.sqlite3")
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app.hybrid_contracts import ASSISTANCE_WINDOWS
        from backend.app.hybrid_activities import generate, evaluate

        with TestClient(app) as client:
            session_response = client.post("/api/sessions", json={
                "learner_id": "demo-user", "consent_accepted": True,
            })
            assert session_response.status_code == 201, session_response.text
            session_id = session_response.json()["id"]
            other_session = store.create_session(uid(), "other-user")

            catalog_response = client.get("/api/hybrid/catalog")
            assert catalog_response.status_code == 200
            rows = catalog_response.json()["activities"]
            catalog = {row["activity_id"]: row for row in rows}
            assert set(catalog) == {f"HY-0{i}" for i in range(1, 7)}
            for activity_id, row in catalog.items():
                assert row["activity_version"] and row["config_version"]
                assert row["status"] == "playable"
                assert row["estimated_duration_minutes"] > 0
                assert row["duration_estimate_status"] == "provisional_unmeasured"
                assert row["duration_estimate_basis"] == "initial_plan_budget_guess_not_observed"
                assert row["family_relevance"]
                assert row["relevance_scope"] == "task_mechanics_only_not_assessment"
                assert row["assistance_windows"] == list(ASSISTANCE_WINDOWS[activity_id])
                assert row["supported_lifecycle"]["exact_start_retry"]
                assert row["supported_lifecycle"]["exact_action_retry"]
                assert row["supported_lifecycle"]["exact_completion_retry"]
                assert row["contributions"] == {
                    "baseline_indices": False,
                    "ex_difficulty_tiers": False,
                    "participation_xp": False,
                }
                assert row["personalized_plan_status"] == "not_integrated"
                for mode in row["supported_modes"]:
                    config = generate(activity_id, "capability-smoke", mode, "tier-1", row["activity_version"])
                    assert config == generate(activity_id, "capability-smoke", mode, "tier-1", row["activity_version"])
                    assert isinstance(evaluate(activity_id, config, []), dict)

            def start_hybrid(activity_id: str):
                meta = catalog[activity_id]
                body = {
                    "event_id": uid(), "session_id": session_id, "learner_id": "demo-user",
                    "activity_id": activity_id, "activity_version": meta["activity_version"],
                    "config_version": meta["config_version"], "mode": "training",
                    "difficulty_tier": "tier-1",
                }
                started = client.post("/api/hybrid/attempts", json=body)
                assert started.status_code == 201, started.text
                assert client.post("/api/hybrid/attempts", json={
                    **body, "event_id": uid(), "activity_version": "unknown-version",
                }).status_code == 409
                assert client.post("/api/hybrid/attempts", json={
                    **body, "event_id": uid(), "config_version": "unknown-config",
                }).status_code == 409
                exact = client.post("/api/hybrid/attempts", json=body)
                assert exact.status_code == 201 and exact.json()["attempt_id"] == started.json()["attempt_id"]
                assert exact.json()["capabilities"] == started.json()["capabilities"]
                changed = client.post("/api/hybrid/attempts", json={**body, "seed": "different-seed"})
                assert changed.status_code == 409
                wrong_owner = client.post("/api/hybrid/attempts", json={
                    **body, "event_id": uid(), "session_id": other_session["id"],
                })
                assert wrong_owner.status_code == 403
                return started.json(), body

            def first_action(activity_id: str, attempt: dict, seq: int = 1):
                aid = attempt["attempt_id"]
                config = attempt["config"]
                if activity_id in {"HY-02", "HY-04"}:
                    cue = client.get(f"/api/hybrid/attempts/{aid}/stimulus").json()
                    if activity_id == "HY-02":
                        action_type = "respond"
                        payload = {"trial_index": cue["index"], "position_match": False, "symbol_match": False}
                    else:
                        action_type = "respond"
                        payload = {"arrival_index": cue["index"], "destination_id": None, "ignore": True}
                    return {"attempt_id": aid, "event_id": uid(), "sequence": seq,
                            "action_type": action_type, "payload": payload, "cue_event_id": cue["cue_id"]}
                if activity_id == "HY-01":
                    return {"attempt_id": aid, "event_id": uid(), "sequence": seq,
                            "action_type": "move", "payload": {"direction": "right"}}
                if activity_id == "HY-03":
                    cargo = config["cargo"][seq - 1]
                    bins = sorted(set(config["rules"]["color_bins"].values()) | set(config["rules"]["shape_bins"].values()))
                    return {"attempt_id": aid, "event_id": uid(), "sequence": seq,
                            "action_type": "select", "payload": {"cargo_id": cargo["cargo_id"], "bin_id": bins[0]}}
                if activity_id == "HY-05":
                    item = config["objects"][seq - 1]
                    return {"attempt_id": aid, "event_id": uid(), "sequence": seq,
                            "action_type": "select", "payload": {"object_id": item["object_id"], "slot_index": seq - 1}}
                return {"attempt_id": aid, "event_id": uid(), "sequence": seq,
                        "action_type": "commit", "payload": {"stage": "proposal" if seq == 1 else "resolution"}}

            for activity_id in sorted(catalog):
                started, start_body = start_hybrid(activity_id)
                attempt_id = started["attempt_id"]
                assert started["capabilities"]["activity_id"] == activity_id
                if activity_id == "HY-01":
                    _, foreign_start_body = start_hybrid(activity_id)
                    foreign_source = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                        "attempt_id": attempt_id, "event_id": uid(), "exposure_kind": "strategy_prompt",
                        "checkpoint": ASSISTANCE_WINDOWS[activity_id][0],
                        "source_event_id": foreign_start_body["event_id"],
                    })
                    assert foreign_source.status_code == 422
                if activity_id == "HY-06":
                    proposal = first_action(activity_id, started)
                    proposal_response = client.post(f"/api/hybrid/attempts/{attempt_id}/actions", json=proposal)
                    assert proposal_response.status_code == 201, proposal_response.text
                checkpoint = ASSISTANCE_WINDOWS[activity_id][0]
                exposure = {
                    "attempt_id": attempt_id, "event_id": uid(), "exposure_kind": "strategy_prompt",
                    "checkpoint": checkpoint, "source_event_id": start_body["event_id"],
                }
                bad_window = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                    **exposure, "event_id": uid(), "checkpoint": "not-a-window",
                })
                assert bad_window.status_code == 409, (activity_id, bad_window.text)
                wrong_assistance_owner = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                    **exposure, "attempt_id": uid(), "event_id": uid(),
                })
                assert wrong_assistance_owner.status_code == 409
                exposed = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=exposure)
                assert exposed.status_code == 201, (activity_id, exposed.text)
                assert not exposed.json()["replayed"]

                first = first_action(activity_id, started, 1 if activity_id != "HY-06" else 2)
                action_url = f"/api/hybrid/attempts/{attempt_id}/actions"
                action1 = client.post(action_url, json=first)
                assert action1.status_code == 201, (activity_id, action1.text)
                second = first_action(activity_id, started, 2 if activity_id != "HY-06" else 3)
                action2 = client.post(action_url, json=second)
                assert action2.status_code == 201, (activity_id, action2.text)

                # Exact pre-action help retry remains idempotent after gameplay closed its window.
                help_retry = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=exposure)
                assert help_retry.status_code == 201 and help_retry.json()["replayed"]
                changed_help = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                    **exposure, "source_event_id": second["event_id"],
                })
                assert changed_help.status_code == 409

                mismatch = client.post(action_url, json={**second, "attempt_id": uid(), "event_id": uid()})
                assert mismatch.status_code == 409
                # Retries retain the canonical event sequence even after later events exist.
                action_retry = client.post(action_url, json=first)
                assert action_retry.status_code == 201 and action_retry.json()["replayed"]
                restored = client.get(f"/api/hybrid/attempts/{attempt_id}")
                assert restored.status_code == 200
                assert [event["sequence"] for event in restored.json()["events"]] == sorted(
                    event["sequence"] for event in restored.json()["events"]
                )
                assert sum(event["event_id"] == first["event_id"] for event in restored.json()["events"]) == 1

                from backend.app import hybrid_store as hybrid_store_module
                canonical = next(event for event in restored.json()["events"] if event["event_id"] == first["event_id"])
                direct_retry, replayed = hybrid_store_module.append_event(
                    store, attempt_id, session_id, 999, "hybrid_action_recorded",
                    canonical["payload"], first["event_id"],
                )
                assert replayed and direct_retry["sequence"] == canonical["sequence"]
                assert direct_retry["recorded_at"] == canonical["payload"]["recorded_at"]
                try:
                    hybrid_store_module.append_event(
                        store, attempt_id, session_id, canonical["sequence"], "hybrid_action_recorded",
                        {"attempt_id": attempt_id, "action_sequence": 99}, uid(),
                    )
                except hybrid_store_module.HybridConflict:
                    pass
                else:
                    raise AssertionError(f"{activity_id} duplicate storage sequence was accepted")

                completion = {"attempt_id": attempt_id, "event_id": uid(), "interrupted": True}
                wrong_completion_owner = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json={
                    **completion, "attempt_id": uid(), "event_id": uid(),
                })
                assert wrong_completion_owner.status_code == 409
                finished = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json=completion)
                assert finished.status_code == 200, (activity_id, finished.text)
                assert finished.json()["completion_state"] == "interrupted"
                assert finished.json()["assisted"] and finished.json()["excluded_from_unassisted"]
                repeated_finish = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json=completion)
                assert repeated_finish.status_code == 200 and repeated_finish.json() == finished.json()
                changed_finish = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json={
                    **completion, "event_id": uid(),
                })
                assert changed_finish.status_code == 409

            crystal_meta_response = client.get("/api/crystal/catalog")
            assert crystal_meta_response.status_code == 200
            crystal_meta = crystal_meta_response.json()
            assert crystal_meta["form_version"] and crystal_meta["generator_version"]
            assert crystal_meta["duration_estimate_status"] == "provisional_unmeasured"
            assert crystal_meta["duration_estimate_basis"] == "initial_plan_budget_guess_not_observed"
            assert crystal_meta["contributions"] == {
                "baseline_indices": False,
                "ex_difficulty_tiers": False,
                "participation_xp": False,
            }
            crystal_start_body = {"event_id": uid(), "session_id": session_id,
                                  "learner_id": "demo-user", "seed": "stable-crystal"}
            crystal_start = client.post("/api/crystal/attempts", json=crystal_start_body)
            assert crystal_start.status_code == 201
            crystal = crystal_start.json()
            assert crystal["capabilities"] == crystal_meta
            assert client.post("/api/crystal/attempts", json={
                **crystal_start_body, "session_id": other_session["id"],
            }).status_code == 403
            assert client.post("/api/crystal/attempts", json=crystal_start_body).json()["attempt_id"] == crystal["attempt_id"]
            choice = next(row for row in crystal["config"]["choices"] if row["value"] == crystal["config"]["grid"][0][1])
            answer = {"event_id": uid(), "choice_id": choice["choice_id"], "response_time_ms": 10}
            answer_url = f"/api/crystal/attempts/{crystal['attempt_id']}/answer"
            answered = client.post(answer_url, json=answer)
            assert answered.status_code == 200 and answered.json()["outcome"]["correct"]
            retry_answer = client.post(answer_url, json=answer)
            assert retry_answer.status_code == 200 and retry_answer.json()["replayed"]
            assert retry_answer.json()["sequence"] == 2
            assert retry_answer.json()["outcome"] == answered.json()["outcome"]
            conflict_answer = client.post(answer_url, json={**answer, "response_time_ms": 11})
            assert conflict_answer.status_code == 409
            restored_crystal = client.get(f"/api/crystal/attempts/{crystal['attempt_id']}").json()
            assert [event["sequence"] for event in restored_crystal["events"]] == [1, 2]
            assert restored_crystal["outcome"]["evidence_ids"] == [event["event_id"] for event in restored_crystal["events"]]

            # Supplemental attempts and Crystal must not create or alter canonical EX events.
            assert [event["type"] for event in store.events(session_id=session_id)] == ["consent_recorded"]
            with closing(store.connect()) as db:
                assert db.execute("SELECT COUNT(*) FROM hybrid_outcomes").fetchone()[0] == 6
                assert db.execute("SELECT COUNT(*) FROM crystal_outcomes").fetchone()[0] == 1
                assert db.execute("SELECT COUNT(*) FROM profile_snapshots").fetchone()[0] == 0
        print("hybrid_foundation_smoke: PASS; isolated DB; capability metadata, all six assistance windows, owner/version/id guards, exact retries, interrupted recovery, Crystal replay and EX isolation")


if __name__ == "__main__":
    main()
