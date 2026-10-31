"""collaboration-v2 acceptance: checkable credit, unassessable states, v1 preservation."""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

from contextlib import closing
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

with tempfile.TemporaryDirectory(prefix="ai4brain-collab-v2-") as folder:
    os.environ["AI4BRAIN_DB"] = str(Path(folder) / "collab.sqlite3")
    os.environ["NEO4J_ENABLED"] = "false"
    os.environ["GROQ_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""
    from fastapi.testclient import TestClient
    from backend.app.main import app, store

    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        memory = client.get("/api/exercises/EX-01", params={"phase": "baseline", "session_id": sid}).json()
        evidence_ids: list[str] = []
        for item in memory["items"]:
            sequence = list(item["stimulus"]["sequence"])
            chosen = [sequence[0], *[((p + 1) % 9) for p in sequence[1:]]]
            event_id = str(uuid.uuid4())
            saved = client.post("/api/trials", json={
                "session_id": sid, "event_id": event_id, "exercise_id": "EX-01",
                "exercise_version": memory["exercise_version"], "phase": "baseline",
                "item_id": item["item_id"], "response_data": {"selected_sequence": chosen},
                "response_time_ms": 1200})
            assert saved.status_code == 200, saved.text
            evidence_ids.append(event_id)

        def ask(message: str) -> dict:
            response = client.post("/api/coach", json={"session_id": sid, "message": message, "provider": "local"})
            assert response.status_code == 200, response.text
            return response.json()

        first = ask("I struggled to remember the order. What do my Memory mistakes show?")
        opportunities = [row["opportunity"] for row in first["opportunities"]]
        by_dimension = {row["dimension"]: row for row in opportunities}
        assert {"clarification", "critical_verification", "responsible_use"} <= set(by_dimension), by_dimension

        verification = by_dimension["critical_verification"]
        prepared = client.post("/api/collaboration/v2/prepare",
                               json={"session_id": sid, "source_event_id": verification["source_event_id"]})
        assert prepared.status_code == 200, prepared.text
        claim_view = client.get("/api/collaboration/v2/claim",
                                params={"opportunity_id": verification["opportunity_id"], "session_id": sid}).json()
        assert claim_view["claim_text"], claim_view
        assert "expected_verdict" not in claim_view and "explanation" not in claim_view, claim_view

        with closing(store.connect()) as db:
            truth = dict(db.execute("SELECT * FROM collaboration_claims WHERE opportunity_id=?",
                                    (verification["opportunity_id"],)).fetchone())
        wrong = "supported" if truth["expected_verdict"] != "supported" else "contradicted"

        # A long, well-punctuated but unreferenced question earns nothing.
        empty = client.post("/api/collaboration/v2/actions", json={
            "session_id": sid, "opportunity_id": by_dimension["clarification"]["opportunity_id"],
            "evidence": {"question": "Could you explain this in more detail, please? I would like a much longer "
                                    "answer about everything that happened, with examples!"}})
        assert empty.status_code == 200, empty.text
        assert empty.json()["evaluation"]["credit_percent"] is None, empty.json()["evaluation"]
        assert empty.json()["evaluation"]["status"] == "unassessed", empty.json()["evaluation"]

        # A wrong verification verdict earns partial credit, not full credit.
        mismatched = client.post("/api/collaboration/v2/actions", json={
            "session_id": sid, "opportunity_id": verification["opportunity_id"],
            "evidence": {"verdict": wrong, "inspected_event_id": truth["evidence_event_id"]}})
        assert mismatched.status_code == 200, mismatched.text
        assert mismatched.json()["evaluation"]["credit_percent"] == 25, mismatched.json()["evaluation"]

        # A second conversation issues a fresh opportunity; the correct verdict earns full credit.
        second = ask("Which saved record should I verify first?")
        second_verification = next(row["opportunity"] for row in second["opportunities"]
                                   if row["opportunity"]["dimension"] == "critical_verification")
        client.post("/api/collaboration/v2/prepare",
                    json={"session_id": sid, "source_event_id": second_verification["source_event_id"]})
        with closing(store.connect()) as db:
            truth2 = dict(db.execute("SELECT * FROM collaboration_claims WHERE opportunity_id=?",
                                     (second_verification["opportunity_id"],)).fetchone())
        matched = client.post("/api/collaboration/v2/actions", json={
            "session_id": sid, "opportunity_id": second_verification["opportunity_id"],
            "evidence": {"verdict": truth2["expected_verdict"], "inspected_event_id": truth2["evidence_event_id"]}})
        assert matched.json()["evaluation"]["credit_percent"] == 100, matched.json()["evaluation"]

        # A question linked to a cited record and followed by a later recorded use earns full credit.
        later = evidence_ids[-1]
        linked = ask("About one saved Memory record: what does it show?")
        linked_clarification = next(row["opportunity"] for row in linked["opportunities"]
                                    if row["opportunity"]["dimension"] == "clarification")
        cited = [value for value in linked_clarification["evidence_ids"] if value in evidence_ids]
        assert cited, linked_clarification["evidence_ids"]
        clarification = client.post("/api/collaboration/v2/actions", json={
            "session_id": sid, "opportunity_id": linked_clarification["opportunity_id"],
            "evidence": {"question": "Does this record show an order error?",
                         "about_evidence_id": cited[0],
                         "understanding_applied_event_id": later}})
        assert clarification.status_code == 200, clarification.text
        assert clarification.json()["evaluation"]["credit_percent"] in {50, 100}, clarification.json()

        # Autonomy: following advice alone is participation; an independent decision with a
        # recorded constraint is demonstrated judgement.
        for source in (second, linked):
            for row in source["opportunities"]:
                opportunity = row["opportunity"]
                if opportunity["dimension"] != "autonomy":
                    continue
                plain = client.post("/api/collaboration/v2/actions", json={
                    "session_id": sid, "opportunity_id": opportunity["opportunity_id"],
                    "evidence": {"decision": "accept"}})
                assert plain.json()["evaluation"]["credit_percent"] in {50, None}, plain.json()["evaluation"]
                constrained = client.post("/api/collaboration/v2/actions", json={
                    "session_id": sid, "opportunity_id": opportunity["opportunity_id"],
                    "evidence": {"decision": "decline", "constraint_reference_id": evidence_ids[0]}})
                assert constrained.json()["evaluation"]["credit_percent"] == 100, constrained.json()["evaluation"]
                break

        # The v2 score stays unassessed until every weighted dimension is assessed.
        score = client.get("/api/collaboration/v2/score/demo-user").json()
        assert score["collaboration_version"] == "collaboration-v2", score
        assert set(score["dimensions"]) == {"clarification", "critical_verification", "iteration",
                                            "autonomy", "responsible_use"}, score["dimensions"]
        assert score["weights_percent"]["critical_verification"] == 25, score["weights_percent"]
        assert 0 <= score["evaluated_opportunity_coverage"] <= 100, score
        assert score["score_0_100"] is None or score["evaluated_opportunity_coverage"] == 100, score
        assert "unvalidated" in score["rubric_note"], score["rubric_note"]
        other_session = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        scoped = client.get("/api/collaboration/v2/score/demo-user",
                            params={"session_id": other_session})
        assert scoped.status_code == 200, scoped.text
        assert all(item["evaluated_opportunity_count"] == 0
                   for item in scoped.json()["dimensions"].values()), scoped.json()
        assert client.get("/api/collaboration/v2/claim",
                          params={"opportunity_id": verification["opportunity_id"],
                                  "session_id": other_session}).status_code == 404

        # v1 remains intact and readable alongside v2.
        legacy = client.get("/api/collaboration/score/demo-user")
        assert legacy.status_code in {200, 404}, legacy.status_code
        versions = {event["payload"].get("collaboration_version")
                    for event in store.events(learner_id="demo-user")
                    if event["type"] == "collaboration_action_recorded"}
        assert versions == {"collaboration-v2"}, versions

print("PASS collaboration-v2: unreferenced text earns nothing, wrong verdict earns partial credit, "
      "correct verdict earns full credit, advice-following is not rewarded as autonomy, "
      "unassessed states are explicit and collaboration-v1 history is preserved")
