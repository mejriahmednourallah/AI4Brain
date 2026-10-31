"""Revision graph snapshots, canonical record adapters and async mirror races on disposable SQLite."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


with tempfile.TemporaryDirectory(prefix="ai4brain-graph-snapshot-") as folder:
    os.environ["AI4BRAIN_DB"] = str(Path(folder) / "graph.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"

    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    from backend.app import graph_service
    from backend.app.graph_service import (GraphMirrorCoordinator, build_graph, filter_graph_snapshot,
        graph_lifecycle_generation, graph_source_revision)
    from backend.app.graph_records import resolve_graph_record
    from backend.app.hybrid_activities import CATALOG, HYBRID_EVALUATION_VERSION
    from backend.app.hybrid_store import save_outcome
    from backend.app.plan_v3 import _reserve_launch, launch_request_fingerprint
    from backend.app.storage import Store, utc_now
    from backend.app.lifecycle_service import delete_learner_data
    import json
    from contextlib import closing

    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        plan_response = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
        assert plan_response.status_code == 200, plan_response.text
        plan = plan_response.json()
        assert plan["plan_version"] == "plan-v3"
        step = plan["steps"][0]
        plan_record = resolve_graph_record(store, "demo-user", "plan", plan["plan_id"])
        assert plan_record and plan_record["record_ref"]["version"] == plan["plan_version"]
        step_ref = resolve_graph_record(store, "demo-user", "plan_step", f"{plan['plan_id']}::{step['step_id']}")
        assert step_ref and step_ref["record"]["plan_id"] == plan["plan_id"]

        # A canonical core block and mapping provide a real plan-step -> launch -> block path.
        core_ref = step.get("activity_ref") or {"kind": "core", "id": step.get("exercise_type_id"),
                                                 "version": step.get("exercise_version")}
        if core_ref.get("kind") != "core":
            core_step = next((item for item in plan["steps"] if (item.get("activity_ref") or {}).get("kind") == "core"), None)
            assert core_step, plan["steps"]
            step = core_step
            core_ref = step["activity_ref"]
        block_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        store.create_training_block(block_id, "demo-user", sid, "tier-1", core_ref["version"],
                                    core_ref["id"], step.get("dimension_id") or "reasoning")
        start_payload = {"event_id": event_id, "session_id": sid, "learner_id": "demo-user",
                         "event_type": "training_block_started", "phase": "training",
                         "training_block_id": block_id, "exercise_id": core_ref["id"],
                         "exercise_version": core_ref["version"], "item_ids": ["graph-fixture-item"],
                         "sample_data": False, "recorded_at": utc_now()}
        store.add_event(event_id, sid, "training_block_started", start_payload)
        launch_id = str(uuid.uuid4())
        _reserve_launch(store, {"request_id": launch_id, "learner_id": "demo-user", "session_id": sid,
            "plan_id": plan["plan_id"], "step_id": step["step_id"], "activity_kind": "core",
            "activity_id": core_ref["id"], "activity_version": core_ref["version"],
            "payload_fingerprint": launch_request_fingerprint({"plan_id": plan["plan_id"], "step_id": step["step_id"]}),
            "attempt_id": block_id, "start_event_id": event_id, "status": "started",
            "destination_json": json.dumps({"kind": "core", "id": core_ref["id"]}),
            "created_at": utc_now(), "updated_at": utc_now()})
        assert resolve_graph_record(store, "demo-user", "plan_launch", launch_id)["evidence"][0]["resolvable"]
        assert resolve_graph_record(store, "demo-user", "core_training_block", block_id)["record"]["block"]["block_id"] == block_id

        # Live route starts a versioned HY attempt; outcome row is a deterministic synthetic fixture.
        hy_meta = CATALOG["HY-01"]
        hy_start_id = str(uuid.uuid4())
        hy_start = client.post("/api/hybrid/attempts", json={"event_id": hy_start_id, "session_id": sid,
            "activity_id": "HY-01", "activity_version": hy_meta["activity_version"], "config_version": hy_meta["config_version"],
            "mode": "training", "difficulty_tier": "tier-1", "seed": "graph-smoke-hy"})
        assert hy_start.status_code == 201, hy_start.text
        hy_attempt_id = hy_start.json()["attempt_id"]
        save_outcome(store, {"attempt_id": hy_attempt_id, "session_id": sid, "learner_id": "demo-user",
            "activity_id": "HY-01", "activity_version": hy_meta["activity_version"],
            "evaluation_version": HYBRID_EVALUATION_VERSION, "completion_state": "completed",
            "assisted": True, "excluded_from_unassisted": True,
            "outcomes": {"fixture_label": "synthetic adapter fixture"},
            "evidence_ids": [hy_start_id], "limitations": ["Synthetic graph adapter fixture."]})
        assert resolve_graph_record(store, "demo-user", "hybrid_attempt", hy_attempt_id)["record"]["activity_version"] == hy_meta["activity_version"]
        hy_outcome = resolve_graph_record(store, "demo-user", "hybrid_outcome", hy_attempt_id)
        assert hy_outcome and hy_outcome["evidence"][0]["resolvable"]

        # Crystal uses its canonical attempt/answer routes and evidence IDs.
        crystal_start_id = str(uuid.uuid4())
        crystal_start = client.post("/api/crystal/attempts", json={"event_id": crystal_start_id, "session_id": sid})
        assert crystal_start.status_code == 201, crystal_start.text
        crystal = crystal_start.json()
        config = crystal["config"]
        expected_value = config["grid"][0][1]
        choice = next(item["choice_id"] for item in config["choices"] if item["value"] == expected_value)
        answered = client.post(f"/api/crystal/attempts/{crystal['attempt_id']}/answer", json={
            "event_id": str(uuid.uuid4()), "choice_id": choice, "response_time_ms": 900})
        assert answered.status_code == 200, answered.text
        crystal_attempt = resolve_graph_record(store, "demo-user", "crystal_attempt", crystal["attempt_id"])
        crystal_outcome = resolve_graph_record(store, "demo-user", "crystal_outcome", crystal["attempt_id"])
        assert crystal_attempt and "config_json" not in crystal_attempt["record"]
        assert crystal_outcome and all(link["resolvable"] for link in crystal_outcome["evidence"])

        first = client.get("/api/graph/demo-user")
        assert first.status_code == 200, first.text
        graph = first.json()
        assert graph["graph_version"] == "graph-v2" and graph["snapshot_status"] == "built", graph
        node_ids = {node["id"] for node in graph["nodes"]}
        assert f"plan:{plan['plan_id']}" in node_ids
        assert f"plan-launch:{launch_id}" in node_ids and f"training-block:{block_id}" in node_ids
        assert f"hybrid-attempt:{hy_attempt_id}" in node_ids and f"hybrid-outcome:{hy_attempt_id}" in node_ids
        assert f"crystal-attempt:{crystal['attempt_id']}" in node_ids and f"crystal-outcome:{crystal['attempt_id']}" in node_ids
        assert graph["mirror_status"]["status"] == "disabled"
        assert graph["visible_node_count"] == len(graph["nodes"])
        assert graph["visible_edge_count"] == len(graph["edges"])
        assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])

        # Every source-backed activity outcome reference opens the canonical stored evidence.
        hy_node = next(node for node in graph["nodes"] if node["id"] == f"hybrid-outcome:{hy_attempt_id}")
        record_ref = hy_node["properties"]["record_ref"]
        inspected = client.get("/api/graph/demo-user/record", params={"kind": record_ref["kind"], "id": record_ref["id"]})
        assert inspected.status_code == 200 and all(link["resolvable"] for link in inspected.json()["evidence"])
        evidence_node = next(node for node in graph["nodes"] if node["id"].startswith("canonical-evidence:crystal_events:"))
        evidence_ref = evidence_node["properties"]["record_ref"]
        event_inspected = client.get("/api/graph/demo-user/record", params={"kind": "canonical_event", "id": evidence_ref["id"]})
        assert event_inspected.status_code == 200 and event_inspected.json()["record"]["source_table"] == "crystal_events"

        second = client.get("/api/graph/demo-user").json()
        assert second["snapshot_status"] == "hit" and second["revision"] == graph["revision"]
        stale = client.get("/api/graph/demo-user", params={"revision": "old-revision"}).json()
        assert stale["revision_changed"] is True and stale["revision"] == graph["revision"]
        typed = client.get("/api/graph/demo-user", params={"node_types": "HybridAttempt"}).json()
        assert typed["visible_node_count"] == 1 and typed["filtered_node_count"] == 1
        dimension = client.get("/api/graph/demo-user", params={"dimension": "reasoning"}).json()
        assert any(node["id"] == f"crystal-attempt:{crystal['attempt_id']}" for node in dimension["nodes"])
        local = client.get("/api/graph/demo-user", params={"scope": "local", "center_id": f"hybrid-attempt:{hy_attempt_id}", "depth": 1}).json()
        assert any(node["id"] == f"hybrid-outcome:{hy_attempt_id}" for node in local["nodes"])
        assert all(edge["source"] in {node["id"] for node in local["nodes"]}
                   and edge["target"] in {node["id"] for node in local["nodes"]} for edge in local["edges"])
        assert client.get("/api/graph/demo-user", params={"scope": "local", "center_id": "missing-node"}).status_code == 422
        page = client.get("/api/graph/demo-user", params={"limit": 2, "offset": 0}).json()
        page_ids = {node["id"] for node in page["nodes"]}
        assert page["visible_node_count"] == min(2, page["filtered_node_count"])
        assert all(edge["source"] in page_ids and edge["target"] in page_ids for edge in page["edges"])

        # Synthetic fixtures exercise 16, 1,000 and 5,000 nodes without claiming API timing.
        for size in (16, 1000, 5000):
            fixture = build_graph({"learner_id": f"fixture-{size}", "dimensions": {}}, item_catalog=[
                {"item_id": f"fixture-{size}-item-{index}", "exercise_id": "EX-02", "exercise_version": "fixture-v1"}
                for index in range(size)])
            viewed = filter_graph_snapshot(fixture, limit=1000)
            assert viewed["filtered_node_count"] == viewed["total_node_count"]
            assert viewed["visible_node_count"] == min(1000, viewed["total_node_count"])
            fixture_ids = {node["id"] for node in viewed["nodes"]}
            assert all(edge["source"] in fixture_ids and edge["target"] in fixture_ids for edge in viewed["edges"])

        # A newer revision replaces pending work while an older sync is in flight.
        calls: list[str] = []
        first_sync_started = threading.Event()
        release_first_sync = threading.Event()
        class RecordingMirror:
            def __init__(self, enabled=None): pass
            def sync(self, snapshot):
                calls.append(snapshot["revision"])
                if snapshot["revision"] == "r1":
                    first_sync_started.set()
                    assert release_first_sync.wait(2), "coalescing fixture timed out"
                return {"enabled": True, "connected": True, "status": "synced"}
        coordinator = GraphMirrorCoordinator(enabled=True, mirror_factory=RecordingMirror)
        generation = graph_lifecycle_generation(store, "demo-user")
        coordinator.enqueue(store, "demo-user", {"revision": "r1"}, "r1", generation)
        assert first_sync_started.wait(1), "first mirror revision did not start"
        coordinator.enqueue(store, "demo-user", {"revision": "r2"}, "r2", generation)
        release_first_sync.set()
        assert coordinator.wait_idle(), "mirror queue did not drain"
        assert calls == ["r1", "r2"], calls
        assert coordinator.status("demo-user", store)["revision"] == "r2"

        class OutageMirror:
            def __init__(self, enabled=None): pass
            def sync(self, snapshot):
                return {"enabled": True, "connected": False, "status": "unavailable", "message": "mock outage"}
        outage = GraphMirrorCoordinator(enabled=True, mirror_factory=OutageMirror)
        outage.enqueue(store, "demo-user", {"revision": "r3"}, "r3", generation)
        assert outage.wait_idle()
        assert outage.status("demo-user", store)["status"] == "degraded"

        # A queued old generation is cancelled deterministically behind a gated worker.
        cancelled_calls: list[str] = []
        blocker_started = threading.Event()
        release_blocker = threading.Event()
        class CancelMirror:
            def __init__(self, enabled=None): pass
            def sync(self, snapshot):
                cancelled_calls.append(snapshot["revision"])
                if snapshot["revision"] == "blocker":
                    blocker_started.set()
                    assert release_blocker.wait(2), "cancel queue fixture timed out"
                return {"enabled": True, "connected": True, "status": "synced"}
        cancelled = GraphMirrorCoordinator(enabled=True, mirror_factory=CancelMirror)
        cancelled.enqueue(store, "queue-gate", {"revision": "blocker"}, "blocker", 0)
        assert blocker_started.wait(1)
        cancelled.enqueue(store, "demo-user", {"revision": "old"}, "old", generation)
        cancelled.cancel_learner("demo-user", store)
        release_blocker.set()
        assert cancelled.wait_idle() and cancelled_calls == ["blocker"], cancelled_calls

        # Same learner/counts in distinct databases cannot collide in revisions or snapshots.
        scope_one_store = Store(Path(folder) / "scope-one.sqlite3")
        other_store = Store(Path(folder) / "scope-two.sqlite3")
        from fastapi import FastAPI
        from backend.app.crystal_reasoning import register_crystal_routes
        from backend.app.hybrid_routes import register_hybrid_routes
        for isolated_store in (scope_one_store, other_store):
            register_crystal_routes(FastAPI(), isolated_store)
            register_hybrid_routes(FastAPI(), isolated_store)
        primary_session = str(uuid.uuid4())
        second_session = str(uuid.uuid4())
        scope_one_store.create_session(primary_session, "same-learner")
        other_store.create_session(second_session, "same-learner")
        first_event = str(uuid.uuid4())
        second_event = str(uuid.uuid4())
        scope_one_store.add_event(first_event, primary_session, "scope_probe", {"event_id": first_event, "marker": "primary"})
        other_store.add_event(second_event, second_session, "scope_probe", {"event_id": second_event, "marker": "secondary"})
        def source_for(isolated_store):
            events = isolated_store.events(learner_id="same-learner")
            marker = next(event["event_id"] for event in events if event["event_id"] in {first_event, second_event})
            return build_graph({"learner_id": "same-learner", "dimensions": {}}, events=events,
                               goal={"dimension": "reasoning", "description": marker})
        primary_graph, _ = graph_service.get_cached_graph(scope_one_store, "same-learner", lambda: source_for(scope_one_store))
        second_graph, _ = graph_service.get_cached_graph(other_store, "same-learner", lambda: source_for(other_store))
        assert graph_source_revision(scope_one_store, "same-learner") != graph_source_revision(other_store, "same-learner")
        with closing(scope_one_store.connect()) as first_db, closing(other_store.connect()) as second_db:
            first_count = first_db.execute("SELECT count(*) FROM events").fetchone()[0]
            second_count = second_db.execute("SELECT count(*) FROM events").fetchone()[0]
            first_max_rowid = first_db.execute("SELECT COALESCE(MAX(rowid),0) FROM events").fetchone()[0]
            second_max_rowid = second_db.execute("SELECT COALESCE(MAX(rowid),0) FROM events").fetchone()[0]
        assert first_count == second_count and first_max_rowid == second_max_rowid
        primary_goal = next(node for node in primary_graph["nodes"] if node["type"] == "PracticeGoal")
        second_goal = next(node for node in second_graph["nodes"] if node["type"] == "PracticeGoal")
        assert primary_goal["properties"]["description"] == first_event
        assert second_goal["properties"]["description"] == second_event

        # Slow mirror sync never holds canonical lifecycle lock; delete cancellation
        # invalidates the in-flight write and forces erase before mirror lock release.
        started = threading.Event()
        release = threading.Event()
        mirror_calls: list[str] = []
        class SlowMirror:
            def __init__(self, enabled=None): pass
            def sync(self, snapshot):
                mirror_calls.append("sync-start")
                started.set()
                assert release.wait(2), "slow mirror fixture timed out"
                mirror_calls.append("sync-end")
                return {"enabled": True, "connected": True, "status": "synced"}
            def erase_learner(self, learner_id):
                mirror_calls.append("erase")
                return {"status": "deleted", "erasure_verified": True}
        slow = GraphMirrorCoordinator(enabled=True, mirror_factory=SlowMirror)
        slow.enqueue(store, "slow-learner", {"learner_id": "slow-learner", "revision": "slow-r1"}, "slow-r1", 0)
        assert started.wait(1), "slow mirror did not start"
        acquired = threading.Event()
        def acquire_lifecycle_lock():
            with store.coach_lifecycle_lock:
                acquired.set()
        lock_thread = threading.Thread(target=acquire_lifecycle_lock)
        lock_thread.start()
        assert acquired.wait(.5), "canonical lifecycle lock blocked by derived mirror sync"
        lock_thread.join(timeout=1)
        with store.coach_lifecycle_lock:
            slow.cancel_learner("slow-learner", store)
        release.set()
        assert slow.wait_idle(3)
        assert mirror_calls == ["sync-start", "sync-end", "erase"], mirror_calls

        graph_service.clear_graph_cache_for_learner("same-learner", scope_one_store)
        graph_service.clear_graph_cache_for_learner("same-learner", other_store)

        # Event insertion changes revision; deletion clears process-local graph snapshots.
        previous_revision = graph_source_revision(store, "demo-user")
        probe_id = str(uuid.uuid4())
        store.add_event(probe_id, sid, "graph_revision_probe", {"event_id": probe_id, "sample_data": True})
        changed = client.get("/api/graph/demo-user").json()
        assert changed["revision"] != previous_revision and changed["snapshot_status"] == "built"
        assert graph_service.GRAPH_SNAPSHOTS.entry_count() >= 1

    deletion = delete_learner_data(store)
    assert deletion["graph_snapshots_cleared"] >= 1, deletion
    assert graph_service.GRAPH_SNAPSHOTS.entry_count() == 0

print("PASS graph snapshots: revision cache/stale response, backward family filter, type/search/local/page counts, "
      "all canonical plan/core/HY/Crystal/evidence resolvers, 16/1000/5000 fixtures, coalesced/degraded/cancelled "
      "mirror queue/cancellation during slow sync and lifecycle snapshot clear, store-scope isolation; Neo4j stayed disabled")
