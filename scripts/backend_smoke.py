"""Focused API smoke checks for baseline evidence and adaptive training."""
from __future__ import annotations

import os
import tempfile
import uuid
import sys
from contextlib import closing
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="ai4brain-smoke-") as tmp:
    os.environ["AI4BRAIN_DB"] = str(Path(tmp) / "smoke.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"
    from fastapi.testclient import TestClient
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.main import app
    from app.exercises import ITEM_BANK, BASELINE_ITEM_IDS, evaluate, expected_tile
    from app.exercises import TRAINING_EXERCISE_VERSION, LEGACY_TRAINING_EXERCISE_VERSION, make_training_bank
    from app.scoring import score_reasoning
    from app.main import store

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    exercise = client.get("/api/exercises/EX-02?phase=baseline").json()
    assert len(exercise["items"]) == 6
    assert all("answer" not in item and "rule_type" not in item for item in exercise["items"])
    assert all("bottom_right" in item["pattern"] and item["pattern"]["bottom_right"] is None for item in exercise["items"])
    assert all(len(item["choices"]) == 4 and all("tile" in option for option in item["choices"]) for item in exercise["items"])
    # Generative template evaluator proves one answer and classifies every wrong option as wrong.
    for item_id in BASELINE_ITEM_IDS:
        bank_item = ITEM_BANK[item_id]
        matching = [key for key, choice in bank_item["choices"].items() if choice == expected_tile(bank_item)]
        assert matching == [bank_item["answer"]]
        assert sum(evaluate(item_id, key)[0] for key in bank_item["choices"]) == 1
        for wrong in set(bank_item["choices"]) - {bank_item["answer"]}:
            assert evaluate(item_id, wrong)[0] is False
    coached = {"event_id": "coached", "session_id": "s", "session_started_at": "2026-01-01", "created_at": "2026-01-01", "payload": {"phase": "baseline", "exercise_id": "EX-02", "item_id": BASELINE_ITEM_IDS[0], "interaction": {"hint_count": 1, "visibility_interrupted": False}, "evaluation": {"correct": True}, "timing": {}}}
    assert score_reasoning([coached])["evidence_count"] == 0
    assert client.post("/api/sessions", json={"learner_id":"demo-user"}).status_code==400
    session = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True}).json()
    sid = session["id"]

    # An interrupted attempt remains in history but does not fill the baseline slot.
    item0 = exercise["items"][0]
    event_id = str(uuid.uuid4())
    data = {"event_id": event_id, "session_id": sid, "item_id": item0["item_id"], "phase": "baseline", "choice": "A", "visibility_interrupted": True}
    first = client.post("/api/trials", json=data)
    assert first.status_code == 200 and not first.json()["scored"]
    assert client.get("/api/profile/demo-user").json()["dimensions"]["reasoning"]["evidence_count"] == 0
    # Exact retry is idempotent; changed payload with same key is rejected.
    assert client.post("/api/trials", json=data).json()["replayed"] is True
    conflict = client.post("/api/trials", json={**data, "choice": "B"})
    assert conflict.status_code == 409

    # Hints cannot be submitted on baseline; the same item may only be retried after interruption.
    hint = client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": sid, "item_id": item0["item_id"], "phase": "baseline", "choice": "B", "hint_count": 1})
    assert hint.status_code == 422
    # Retry the interrupted item with a fresh event ID and answer every item correctly.
    for index, item in enumerate(exercise["items"]):
        if index == 0:
            # Public item metadata intentionally has no key. The known fixture's answer is B.
            choice = "B"
        elif index == 1:
            choice = "A"
        elif index == 2:
            choice = "C"
        elif index == 3:
            choice = "C"
        elif index == 4:
            choice = "A"
        else:
            choice = "B"
        resp = client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": sid, "item_id": item["item_id"], "phase": "baseline", "choice": choice, "response_time_ms": 1200})
        assert resp.status_code == 200, resp.text
        saved = client.get(f"/api/sessions/{sid}/events").json()["events"][-1]["payload"]
        assert saved["recorded_at"] and saved["stimulus_config"]["layout"] == "2x2" and saved["sample_data"] is False
    duplicate_valid = client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": sid, "item_id": item0["item_id"], "phase": "baseline", "choice": "A"})
    assert duplicate_valid.status_code == 409
    training = client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": sid, "item_id": item0["item_id"], "phase": "training", "choice": "B"})
    assert training.status_code == 422
    result = client.get("/api/profile/demo-user").json()
    reasoning = result["dimensions"]["reasoning"]
    assert reasoning["completed"] is True and reasoning["evidence_count"] == 6 and reasoning["index_0_100"] == 100
    assert reasoning["interrupted_count"] == 1 and "HIGH_UNCERTAINTY" in reasoning["uncertainty_status"]
    assert all(result["dimensions"][d]["status"] == "NOT_ASSESSED" for d in ("working_memory", "attention_inhibition", "flexibility", "planning"))
    snapshot_before = reasoning["latest_snapshot_id"]
    # A client cannot provide correctness: unknown keys are rejected by the contract.
    invalid = client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": sid, "item_id": exercise["items"][0]["item_id"], "phase": "baseline", "choice": "A", "correct": True})
    assert invalid.status_code == 422
    # Resume and evidence endpoints expose persisted attempt history.
    resumed = client.get(f"/api/sessions/{sid}").json()
    assert resumed["event_count"] == 8 and len(resumed["events"]) == 8
    assert len(client.get("/api/profile/demo-user/evidence").json()["events"]) == 8
    # Replayed requests do not create another snapshot.
    assert client.post("/api/trials", json={"event_id": event_id, "session_id": sid, "item_id": item0["item_id"], "phase": "baseline", "choice": "A", "visibility_interrupted": True}).json()["replayed"] is True
    assert client.get("/api/profile/demo-user").json()["dimensions"]["reasoning"]["latest_snapshot_id"] == snapshot_before
    # A pre-v2 block still resolves its original four fixed items and accepts an exact saved retry.
    legacy_block_id=str(uuid.uuid4())
    store.create_training_block(legacy_block_id,"demo-user",sid,"tier-1",LEGACY_TRAINING_EXERCISE_VERSION)
    legacy_get=client.get(f"/api/training/blocks/{legacy_block_id}")
    assert legacy_get.status_code==200 and legacy_get.json()["exercise"]["exercise_version"]==LEGACY_TRAINING_EXERCISE_VERSION
    legacy_rows=make_training_bank("tier-1",version=LEGACY_TRAINING_EXERCISE_VERSION)
    assert len(legacy_get.json()["exercise"]["items"])==4
    legacy_row=legacy_rows[0];legacy_event_id=str(uuid.uuid4())
    legacy_body={"event_id":legacy_event_id,"session_id":sid,"phase":"training","exercise_id":"EX-02",
        "exercise_version":LEGACY_TRAINING_EXERCISE_VERSION,"training_block_id":legacy_block_id,
        "item_id":legacy_row["item_id"],"choice":legacy_row["answer"]}
    legacy_first=client.post("/api/trials",json=legacy_body);legacy_retry=client.post("/api/trials",json=legacy_body)
    assert legacy_first.status_code==200 and legacy_retry.status_code==200 and legacy_retry.json()["replayed"]
    assert client.post("/api/trials",json={**legacy_body,"choice":next(x for x in "ABCD" if x!=legacy_row["answer"])}).status_code==409
    # Four-trial tier controller: promotion, hold, demotion; decisions are persisted once per block.
    def run_training_block(tier, correctness):
        created = client.post("/api/training/blocks", json={"session_id": sid, "tier": tier})
        assert created.status_code == 201, created.text
        block = created.json()["block"]["block_id"]
        config = created.json()["exercise"]
        assert len(config["items"]) == 8 and config["exercise_version"] == TRAINING_EXERCISE_VERSION
        assert all("answer" not in item and item["difficulty"] == tier for item in config["items"])
        source = make_training_bank(tier, block, TRAINING_EXERCISE_VERSION)
        for index, training_item in enumerate(config["items"][:4]):
            correct_choice = source[index]["answer"]
            choice = correct_choice if correctness[index] else next(key for key in ("A","B","C","D") if key != correct_choice)
            response=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_id":"EX-02","exercise_version":TRAINING_EXERCISE_VERSION,"training_block_id":block,"item_id":training_item["item_id"],"choice":choice})
            assert response.status_code==200,response.text
            if index==3:return block,response.json()["difficulty_decision"]
        raise AssertionError("unreachable")
    up_block,up=run_training_block("tier-1",[True,True,True,True])
    assert up["action"]=="up" and up["old_tier"]=="tier-1" and up["new_tier"]=="tier-2" and len(up["evidence_ids"])==4
    assert client.get(f"/api/training/blocks/{up_block}").json()["difficulty_decision"]["action"]=="up"
    # The adaptation is an immutable event, written exactly once with the decision.
    up_adaptations=[e for e in client.get(f"/api/sessions/{sid}/events").json()["events"] if e["type"]=="difficulty_changed" and e["payload"].get("training_block_id")==up_block]
    assert len(up_adaptations)==1 and up_adaptations[0]["payload"]["sample_data"] is False and len(up_adaptations[0]["payload"]["evidence_ids"])==4
    # Exact fourth-event replay returns the same immutable decision; no second promotion.
    block_events=[e for e in client.get(f"/api/sessions/{sid}/events").json()["events"] if e["payload"].get("training_block_id")==up_block and e["type"]=="training_trial_completed"]
    last=block_events[-1]["payload"]
    replay=client.post("/api/trials",json={"event_id":last["event_id"],"session_id":sid,"phase":"training","exercise_id":"EX-02","exercise_version":"training-v2","training_block_id":up_block,"item_id":last["item_id"],"choice":last["response"]["choice"]})
    assert replay.status_code==200 and replay.json()["replayed"] and replay.json()["difficulty_decision"]["new_tier"]=="tier-2"
    duplicate=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_version":"training-v2","training_block_id":up_block,"item_id":last["item_id"],"choice":last["response"]["choice"]})
    assert duplicate.status_code==409
    _,hold=run_training_block("tier-2",[True,True,False,False])
    assert hold["action"]=="hold" and hold["new_tier"]=="tier-2"
    _,down=run_training_block("tier-2",[False,False,False,False])
    assert down["action"]=="down" and down["new_tier"]=="tier-1"
    # Establish the canonical tier-3 decision before requesting a tier-3 block;
    # the API intentionally rejects tiers that the family has not earned.
    _,promote_to_tier2=run_training_block("tier-1",[True,True,True,True])
    assert promote_to_tier2["action"]=="up" and promote_to_tier2["new_tier"]=="tier-2"
    _,promote_to_ceiling=run_training_block("tier-2",[True,True,True,True])
    assert promote_to_ceiling["action"]=="up" and promote_to_ceiling["new_tier"]=="tier-3"
    _,ceiling=run_training_block("tier-3",[True,True,True,True])
    assert ceiling["action"]=="hold" and ceiling["old_tier"]=="tier-3" and ceiling["new_tier"]=="tier-3"
    assert client.get("/api/profile/demo-user").json()["dimensions"]["reasoning"]["latest_snapshot_id"] == snapshot_before
    # Hints and interruption do not count toward a training window; interrupted item can be retried.
    pending=client.post("/api/training/blocks",json={"session_id":sid,"tier":"tier-1"}).json()
    pending_id=pending["block"]["block_id"]; pending_items=pending["exercise"]["items"]
    first_train=pending_items[0]
    interrupted=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_version":"training-v2","training_block_id":pending_id,"item_id":first_train["item_id"],"visibility_interrupted":True})
    assert interrupted.status_code==200 and interrupted.json()["difficulty_decision"] is None
    server_items=make_training_bank("tier-1",pending_id,TRAINING_EXERCISE_VERSION)
    right=server_items[0]["answer"]
    retried=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_version":"training-v2","training_block_id":pending_id,"item_id":first_train["item_id"],"choice":right})
    assert retried.status_code==200
    hinted=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_version":"training-v2","training_block_id":pending_id,"item_id":pending_items[1]["item_id"],"choice":"A","hint_count":1})
    assert hinted.status_code==200 and hinted.json()["difficulty_decision"] is None
    # Complete remaining distinct items: the hinted attempt closes with a hold and explicit gather-more-evidence reason.
    for i in (2,3):
        item=pending_items[i]; choice=make_training_bank("tier-1",pending_id,TRAINING_EXERCISE_VERSION)[i]["answer"]
        response=client.post("/api/trials",json={"event_id":str(uuid.uuid4()),"session_id":sid,"phase":"training","exercise_version":"training-v2","training_block_id":pending_id,"item_id":item["item_id"],"choice":choice})
        assert response.status_code==200
    incomplete_hold=response.json()["difficulty_decision"]
    assert incomplete_hold["action"]=="hold" and incomplete_hold["valid_trial_count"]==3 and "gather more evidence" in incomplete_hold["rationale"]
    # A newer session with five valid items cannot borrow the sixth from the older session.
    newer = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True}).json()["id"]
    for item in exercise["items"][:5]:
        assert client.post("/api/trials", json={"event_id": str(uuid.uuid4()), "session_id": newer, "item_id": item["item_id"], "phase": "baseline", "choice": ITEM_BANK[item["item_id"]]["answer"]}).status_code == 200
    latest_result = client.get("/api/profile/demo-user").json()["dimensions"]["reasoning"]
    assert latest_result["completed"] is False and latest_result["evidence_count"] == 5 and latest_result["assessment_session_id"] == newer
    with closing(store.connect()) as db:
        snapshot_count = db.execute("SELECT COUNT(*) FROM profile_snapshots").fetchone()[0]
    assert snapshot_count == 12
    history = client.get("/api/profile/demo-user/evidence").json()
    assert len([event for event in history["events"] if event["type"] == "assessment_trial_completed"]) == 12
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    for origin in origins:
        preflight = client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert preflight.headers.get("access-control-allow-origin") == origin
    recommendation = client.post("/api/recommendations/next").json()
    assert recommendation["action"] == "complete_baseline" and recommendation["evidence_ids"]

print("PASS: EX-02 2x2 uniqueness and server scoring; baseline replay/coaching/interruption protections; session-coherent snapshots; consent/resume/evidence/CORS; training promotion/hold/demotion/tier ceiling, immutable once-per-block decision events, interruption retry, hinted-evidence hold, and baseline snapshot isolation")







