"""Isolated contract tests for the completed-only HY-02 review history route."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["NEO4J_ENABLED"] = "false"


def uid() -> str:
    return str(uuid.uuid4())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai4brain-hy02-review-history-") as temp:
        os.environ["AI4BRAIN_DB"] = str(Path(temp) / "history.sqlite3")
        from fastapi.testclient import TestClient
        from backend.app.main import app, store
        from backend.app import hybrid_store as hs
        from backend.app.hybrid_activities_modules import tidekeeper

        with TestClient(app) as client:
            session_id = client.post("/api/sessions", json={
                "learner_id": "demo-user", "consent_accepted": True,
            }).json()["id"]
            other_session = store.create_session(uid(), "another-user")["id"]

            def catalog_start(activity_id: str = "HY-02", seed: str | None = None):
                catalog = {item["activity_id"]: item for item in client.get("/api/hybrid/catalog").json()["activities"]}
                meta = catalog[activity_id]
                body = {
                    "event_id": uid(), "session_id": session_id, "learner_id": "demo-user",
                    "activity_id": activity_id, "activity_version": meta["activity_version"],
                    "config_version": meta["config_version"], "mode": "training",
                    "difficulty_tier": "tier-1",
                }
                if seed is not None:
                    body["seed"] = seed
                response = client.post("/api/hybrid/attempts", json=body)
                assert response.status_code == 201, response.text
                return response.json(), meta

            def create_completed_attempt(seed: str, activity_id: str = "HY-02", historical_version: bool = False,
                                          misalign_first_cue: bool = False):
                if historical_version:
                    attempt_id, start_event_id = uid(), uid()
                    activity_version, config_version = "hy-02-v0", "0"
                    config = tidekeeper.generate(seed, "training", "tier-1")
                    # Simulate an older persisted generator stream that cannot be
                    # recovered by the current generator from the same seed.
                    for cue in config["_oracle_stream"]:
                        cue["position"] = (cue["position"] + 1) % 9
                        cue["symbol_index"] = (cue["symbol_index"] + 1) % len(config["symbols"])
                        cue["symbol"] = config["symbols"][cue["symbol_index"]]
                    config["activity_version"] = activity_version
                    config["config_version"] = config_version
                    start_payload = {
                        "event_type": "hybrid_attempt_started", "attempt_id": attempt_id,
                        "session_id": session_id, "learner_id": "demo-user", "activity_id": "HY-02",
                        "activity_version": activity_version, "mode": "training",
                        "config_version": config_version, "difficulty_tier": "tier-1",
                        "seed": seed, "hybrid_schema_version": "hybrid-v1",
                    }
                    hs.create_attempt(store, {
                        "attempt_id": attempt_id, "learner_id": "demo-user", "session_id": session_id,
                        "activity_id": "HY-02", "activity_version": activity_version, "mode": "training",
                        "config_version": config_version, "difficulty_tier": "tier-1", "seed": seed,
                        "config": config, "event_id": start_event_id, "event_payload": start_payload,
                    })
                    started = client.get(f"/api/hybrid/attempts/{attempt_id}").json()
                else:
                    started, _ = catalog_start(activity_id, seed)
                    attempt_id = started["attempt_id"]
                    config = tidekeeper.generate(seed, "training", "tier-1") if activity_id == "HY-02" else None
                if activity_id != "HY-02":
                    return started, None, None
                for index in range(config["trial_count"]):
                    cue_response = client.get(f"/api/hybrid/attempts/{attempt_id}/stimulus")
                    assert cue_response.status_code == 200, cue_response.text
                    cue = cue_response.json()
                    assert cue["index"] == index and cue["cue_id"] == config["_oracle_stream"][index]["cue_id"]
                    action = {
                        "attempt_id": attempt_id, "event_id": uid(), "sequence": index + 1,
                        "action_type": "respond", "cue_event_id": cue["cue_id"],
                        "elapsed_ms": 400, "payload": {
                            "trial_index": index, "position_match": False, "symbol_match": False,
                        },
                    }
                    if misalign_first_cue and index == 0:
                        malformed_event = {
                            "event_type": "hybrid_action_recorded", "attempt_id": attempt_id,
                            "session_id": session_id, "learner_id": "demo-user", "activity_id": "HY-02",
                            "activity_version": started["activity_version"], "action_sequence": index + 1,
                            "action_type": "respond", "action": action["payload"], "elapsed_ms": 400,
                            "cue_event_id": "wrong-cue", "visibility_interrupted": False,
                        }
                        hs.append_event(store, attempt_id, session_id, index + 1,
                                        "hybrid_action_recorded", malformed_event, action["event_id"])
                    else:
                        saved = client.post(f"/api/hybrid/attempts/{attempt_id}/actions", json=action)
                        assert saved.status_code == 201, saved.text
                completion_event_id = uid()
                completed = client.post(f"/api/hybrid/attempts/{attempt_id}/complete", json={
                    "attempt_id": attempt_id, "event_id": completion_event_id,
                })
                assert completed.status_code == 200, completed.text
                return started, completion_event_id, completed.json()

            def create_legacy_fixture(seed: str, response_count: int = 12,
                                      malformed_action: bool = False, malformed_outcome: bool = False):
                attempt_id, start_event_id = uid(), uid()
                config = tidekeeper.generate(seed, "training", "tier-1")
                config["activity_version"], config["config_version"] = "hy-02-v0", "0"
                start_payload = {
                    "event_type": "hybrid_attempt_started", "attempt_id": attempt_id,
                    "session_id": session_id, "learner_id": "demo-user", "activity_id": "HY-02",
                    "activity_version": "hy-02-v0", "mode": "training", "config_version": "0",
                    "difficulty_tier": "tier-1", "seed": seed, "hybrid_schema_version": "hybrid-v1",
                }
                hs.create_attempt(store, {
                    "attempt_id": attempt_id, "learner_id": "demo-user", "session_id": session_id,
                    "activity_id": "HY-02", "activity_version": "hy-02-v0", "mode": "training",
                    "config_version": "0", "difficulty_tier": "tier-1", "seed": seed,
                    "config": config, "event_id": start_event_id, "event_payload": start_payload,
                })
                actions_for_evaluation = []
                for index in range(response_count):
                    cue = config["_oracle_stream"][index]
                    event_id = uid()
                    action_body = {"trial_index": index, "position_match": False, "symbol_match": False}
                    event_payload = {
                        "event_type": "hybrid_action_recorded", "attempt_id": attempt_id,
                        "session_id": session_id, "learner_id": "demo-user", "activity_id": "HY-02",
                        "activity_version": "hy-02-v0", "action_sequence": index + 1,
                        "action_type": "respond", "action": action_body, "elapsed_ms": 400,
                        "cue_event_id": cue["cue_id"], "visibility_interrupted": False,
                    }
                    if malformed_action and index == 0:
                        event_payload["action"] = ["not", "an", "object"]
                    hs.append_event(store, attempt_id, session_id, index + 1,
                                    "hybrid_action_recorded", event_payload, event_id)
                    actions_for_evaluation.append({
                        "event_id": event_id, "sequence": index + 1, "action_type": "respond",
                        "payload": action_body, "elapsed_ms": 400, "cue_event_id": cue["cue_id"],
                    })
                completion_event_id = uid()
                hs.complete_attempt(store, attempt_id, completion_event_id, session_id, {
                    "event_type": "hybrid_attempt_completed", "attempt_id": attempt_id,
                    "session_id": session_id, "learner_id": "demo-user", "activity_id": "HY-02",
                    "activity_version": "hy-02-v0", "interrupted": False,
                    "visibility_interrupted": False, "response_time_ms": None,
                    "action_count": response_count, "assistance_count": 0,
                })
                outcomes = tidekeeper.evaluate(config, actions_for_evaluation)
                if malformed_outcome:
                    outcomes["responses"] = ["not-an-object"] * response_count
                event_ids = [event["event_id"] for event in hs.attempt_events(store, attempt_id)]
                hs.save_outcome(store, {
                    "attempt_id": attempt_id, "session_id": session_id, "learner_id": "demo-user",
                    "activity_id": "HY-02", "activity_version": "hy-02-v0",
                    "evaluation_version": "hy-02-eval-v0", "completion_state": "completed",
                    "assisted": False, "excluded_from_unassisted": False, "outcomes": outcomes,
                    "evidence_ids": event_ids, "limitations": [],
                })
                return client.get(f"/api/hybrid/attempts/{attempt_id}").json(), completion_event_id

            def review_url(attempt_id: str, aid: str, sid: str = session_id):
                return f"/api/hybrid/attempts/{attempt_id}/review-history?{urlencode({'session_id': sid, 'assistance_event_id': aid})}"

            # Active reads reveal neither the stream nor expected answers.
            active, _ = catalog_start(seed="active-review-guard")
            active_id = active["attempt_id"]
            public_active = client.get(f"/api/hybrid/attempts/{active_id}").json()
            assert "_oracle_stream" not in public_active["config"]
            active_cue = client.get(f"/api/hybrid/attempts/{active_id}/stimulus").json()
            assert "position_match_expected" not in active_cue
            assert client.get(review_url(active_id, "not-yet-recorded")).status_code == 409

            # Only HY-02 is eligible; no exposure is disclosed automatically on completion.
            other, _ = catalog_start("HY-01", seed="wrong-activity")
            assert client.get(review_url(other["attempt_id"], "anything")).status_code == 409

            # Complete a canonical attempt and prove version-compatible use of stored history.
            started, completion_id, canonical_outcome = create_completed_attempt(
                "completed-history", historical_version=True)
            attempt_id = started["attempt_id"]
            assert client.get(review_url(attempt_id, "missing-exposure")).status_code == 409
            assert client.get(review_url(attempt_id, "missing-exposure", other_session)).status_code == 403

            assist_body = {
                "attempt_id": attempt_id, "event_id": "review-cue-replay-1",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": completion_id,
            }
            assisted = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=assist_body)
            assert assisted.status_code == 201 and assisted.json()["replayed"] is False, assisted.text
            exact_retry = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json=assist_body)
            assert exact_retry.status_code == 201 and exact_retry.json()["replayed"] is True, exact_retry.text
            bad_source = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                **assist_body, "event_id": "review-cue-replay-wrong-source",
                "source_event_id": started["events"][0]["event_id"],
            })
            assert bad_source.status_code == 201
            assert client.get(review_url(attempt_id, bad_source.json()["event_id"])).status_code == 409
            conflict_retry = client.post(f"/api/hybrid/attempts/{attempt_id}/assistance", json={
                **assist_body, "source_event_id": started["events"][0]["event_id"],
            })
            assert conflict_retry.status_code == 409, conflict_retry.text

            history_response = client.get(review_url(attempt_id, assisted.json()["event_id"]))
            assert history_response.status_code == 200, history_response.text
            history = history_response.json()
            with closing(store.connect()) as db:
                stored_config_json = db.execute("SELECT config_json FROM hybrid_attempts WHERE attempt_id=?",
                                                 (attempt_id,)).fetchone()["config_json"]
            private_stream = json.loads(stored_config_json)["_oracle_stream"]
            regenerated_stream = tidekeeper.generate("completed-history", "training", "tier-1")["_oracle_stream"]
            assert private_stream != regenerated_stream, "historical fixture must not be reproducible from current generator"
            assert history["activity_version"] == "hy-02-v0" and history["config_version"] == "0"
            assert history["stream_count"] == len(private_stream) == 12
            assert history["assistance_event_id"] == assisted.json()["event_id"]
            assert len(history["trials"]) == len(canonical_outcome["outcomes"]["responses"]) == 12
            for index, trial in enumerate(history["trials"]):
                cue = private_stream[index]
                assert trial["trial_index"] == index and trial["cue_event_id"] == cue["cue_id"]
                assert trial["current_cue"] == {"cue_id": cue["cue_id"], "position": cue["position"], "symbol": cue["symbol"]}
                prior = private_stream[index - history["n_back"]] if index >= history["n_back"] else None
                assert trial["comparison_cue"] == (
                    {"cue_id": prior["cue_id"], "position": prior["position"], "symbol": prior["symbol"]}
                    if prior is not None else None
                )
                assert trial["history_cues"] == [
                    {"cue_id": item["cue_id"], "position": item["position"], "symbol": item["symbol"]}
                    for item in private_stream[max(0, index-history["n_back"]):index]
                ]
                assert trial["position_match_expected"] == canonical_outcome["outcomes"]["responses"][index]["position_match_expected"]
                assert trial["symbol_match_expected"] == canonical_outcome["outcomes"]["responses"][index]["symbol_match_expected"]
            assert "_oracle_stream" not in history
            ordinary_after = client.get(f"/api/hybrid/attempts/{attempt_id}").json()
            assert "_oracle_stream" not in ordinary_after["config"]
            assert ordinary_after["outcome"] == canonical_outcome
            assert client.get(review_url(attempt_id, assisted.json()["event_id"], other_session)).status_code == 403
            assert client.get(review_url(attempt_id, "wrong-assistance-id")).status_code == 409
            assert client.get(review_url(attempt_id, "review-cue-replay-1")).status_code == 200

            # Interrupted attempts remain ineligible even if a post-window exposure is recorded.
            interrupted, _ = catalog_start(seed="interrupted-history")
            interrupted_id = interrupted["attempt_id"]
            interrupted_completion = uid()
            interrupted_result = client.post(f"/api/hybrid/attempts/{interrupted_id}/complete", json={
                "attempt_id": interrupted_id, "event_id": interrupted_completion, "interrupted": True,
            })
            assert interrupted_result.status_code == 200 and interrupted_result.json()["completion_state"] == "interrupted"
            interrupted_help = client.post(f"/api/hybrid/attempts/{interrupted_id}/assistance", json={
                "attempt_id": interrupted_id, "event_id": "interrupted-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": interrupted_completion,
            })
            assert interrupted_help.status_code == 201
            assert client.get(review_url(interrupted_id, interrupted_help.json()["event_id"])).status_code == 409

            # Simulate legacy/incomplete stored data on temp DB only; never regenerate a missing stream.
            missing_stream, missing_stream_completion, _ = create_completed_attempt("history-no-stream")
            missing_stream_help = client.post(f"/api/hybrid/attempts/{missing_stream['attempt_id']}/assistance", json={
                "attempt_id": missing_stream["attempt_id"], "event_id": "missing-stream-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": missing_stream_completion,
            })
            assert missing_stream_help.status_code == 201
            with closing(store.connect()) as db:
                row = db.execute("SELECT config_json FROM hybrid_attempts WHERE attempt_id=?", (missing_stream["attempt_id"],)).fetchone()
                old_config = json.loads(row["config_json"])
                old_config.pop("_oracle_stream", None)
                db.execute("UPDATE hybrid_attempts SET config_json=? WHERE attempt_id=?",
                           (json.dumps(old_config, sort_keys=True, separators=(",", ":")), missing_stream["attempt_id"]))
                db.commit()
            assert client.get(review_url(missing_stream["attempt_id"], missing_stream_help.json()["event_id"])).status_code == 409

            partial, partial_completion = create_legacy_fixture("legacy-incomplete", response_count=1)
            partial_id = partial["attempt_id"]
            partial_help = client.post(f"/api/hybrid/attempts/{partial_id}/assistance", json={
                "attempt_id": partial_id, "event_id": "legacy-partial-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": partial_completion,
            })
            assert partial_help.status_code == 201
            assert client.get(review_url(partial_id, partial_help.json()["event_id"])).status_code == 409

            malformed_outcome, malformed_outcome_completion = create_legacy_fixture(
                "legacy-malformed-outcome", malformed_outcome=True)
            malformed_outcome_id = malformed_outcome["attempt_id"]
            malformed_outcome_help = client.post(f"/api/hybrid/attempts/{malformed_outcome_id}/assistance", json={
                "attempt_id": malformed_outcome_id, "event_id": "legacy-malformed-outcome-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": malformed_outcome_completion,
            })
            assert malformed_outcome_help.status_code == 201
            assert client.get(review_url(malformed_outcome_id, malformed_outcome_help.json()["event_id"])).status_code == 409

            malformed_action, malformed_action_completion = create_legacy_fixture(
                "legacy-malformed-action", malformed_action=True)
            malformed_action_id = malformed_action["attempt_id"]
            malformed_action_help = client.post(f"/api/hybrid/attempts/{malformed_action_id}/assistance", json={
                "attempt_id": malformed_action_id, "event_id": "legacy-malformed-action-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": malformed_action_completion,
            })
            assert malformed_action_help.status_code == 201
            assert client.get(review_url(malformed_action_id, malformed_action_help.json()["event_id"])).status_code == 409

            malformed_config, malformed_config_completion, _ = create_completed_attempt(
                "legacy-malformed-config", historical_version=True)
            malformed_config_id = malformed_config["attempt_id"]
            malformed_config_help = client.post(f"/api/hybrid/attempts/{malformed_config_id}/assistance", json={
                "attempt_id": malformed_config_id, "event_id": "legacy-malformed-config-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": malformed_config_completion,
            })
            assert malformed_config_help.status_code == 201
            with closing(store.connect()) as db:
                valid_config_json = db.execute("SELECT config_json FROM hybrid_attempts WHERE attempt_id=?",
                                               (malformed_config_id,)).fetchone()["config_json"]
                db.execute("UPDATE hybrid_attempts SET config_json=? WHERE attempt_id=?",
                           ("{ malformed", malformed_config_id))
                db.commit()
            assert client.get(review_url(malformed_config_id, malformed_config_help.json()["event_id"])).status_code == 409
            with closing(store.connect()) as db:
                db.execute("UPDATE hybrid_attempts SET config_json=? WHERE attempt_id=?",
                           (valid_config_json, malformed_config_id))
                db.commit()

            misaligned, misaligned_completion, _ = create_completed_attempt(
                "history-misaligned", misalign_first_cue=True)
            misaligned_help = client.post(f"/api/hybrid/attempts/{misaligned['attempt_id']}/assistance", json={
                "attempt_id": misaligned["attempt_id"], "event_id": "misaligned-replay",
                "exposure_kind": "cue_replay", "checkpoint": "post_window",
                "source_event_id": misaligned_completion,
            })
            assert misaligned_help.status_code == 201
            assert client.get(review_url(misaligned["attempt_id"], misaligned_help.json()["event_id"])).status_code == 409

            deleted, _, _ = create_completed_attempt("history-deleted")
            deleted_id = deleted["attempt_id"]
            deletion = client.post("/api/data/demo-user/delete", json={"confirmation": "DELETE LOCAL DATA"})
            assert deletion.status_code == 200 and deletion.json()["database_file_preserved"] is True
            assert client.get(review_url(deleted_id, "deleted-replay")).status_code == 404
            assert store.get_session(other_session) is not None, "scoped deletion must preserve the unrelated temporary user"

            print("hy02_review_history_contract_smoke: PASS; completed-only stored-stream projection, replay-assistance gate, session ownership, immutable outcome, exact/conflicting retry, non-regenerable historical stream, interrupted/active/partial/malformed/misaligned/deleted guards")


if __name__ == "__main__":
    main()
