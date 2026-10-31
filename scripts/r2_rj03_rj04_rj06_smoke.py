"""Isolated R2 probes for grounded coaching, validated history and plan tiers."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
fixture = ROOT / "output" / "verification" / f".r2-{uuid.uuid4().hex}.sqlite3"
os.environ["AI4BRAIN_DB"] = str(fixture)
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient

from backend.app import provider_adapters
from backend.app.coach_v2 import grounded_reply, validate_generated
from backend.app.exercises import evaluate
from backend.app.main import app, store
from backend.app.plan_v2 import reconcile_plan
from backend.app.storage import utc_now
from backend.app.twin_context import build_twin_context


class FakeAdapter:
    def __init__(self, reply: dict | None = None):
        self.name = "groq"
        self.default_model = "fake-default"
        self.model = "fake-model"
        self.reply = reply
        self.calls = 0
        self.last_payload: dict | None = None

    def configured(self) -> bool:
        return True

    def complete(self, payload, message, baseline, *, transport=None):
        self.calls += 1
        self.last_payload = payload
        return dict(self.reply or {})


def provider_shape(baseline: dict, **changes) -> dict:
    return {
        "observation": baseline["observation"],
        "explanation": "The saved responses show the recorded pattern without adding a new result.",
        "strategy_id": baseline["strategy_id"],
        "follow_up": "Would you like to inspect the saved evidence?",
        "next_step_note": baseline["next_step_note"],
        "evidence_ids": list(baseline["evidence_ids"]),
        "recommended_exercise_id": baseline["recommended_exercise_id"],
        "recommended_difficulty": baseline["recommended_difficulty"],
        "clarification": None,
        **changes,
    }


def add_difficulty_event(session_id: str, tier: str, reference: str) -> None:
    event_id = str(uuid.uuid4())
    store.add_event(event_id, session_id, "difficulty_changed", {
        "event_id": event_id, "event_type": "difficulty_changed", "learner_id": "demo-user",
        "session_id": session_id, "dimension": "reasoning", "new_tier": tier,
        "old_tier": "tier-1" if tier != "tier-1" else "tier-2",
        "sample_data": False, "recorded_at": utc_now(),
        "reference": reference,
    })


try:
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]
        other_sid = client.post("/api/sessions", json={"consent_accepted": True}).json()["id"]

        # RJ-04 baseline gate, then one plan whose launch tier is policy-authored.
        blocked = client.post("/api/training/blocks", json={"session_id": sid, "exercise_id": "EX-02"})
        assert blocked.status_code == 409, blocked.text
        created = client.post("/api/plans/next", json={"session_id": sid, "budget_minutes": 30})
        assert created.status_code == 200, created.text
        reasoning = client.get("/api/exercises/EX-02", params={"session_id": sid}).json()
        for item in reasoning["items"]:
            choice = next(c["choice_id"] for c in item["choices"]
                          if evaluate(item["item_id"], c["choice_id"])[0])
            saved = client.post("/api/trials", json={
                "session_id": sid, "event_id": str(uuid.uuid4()), "exercise_id": "EX-02",
                "exercise_version": reasoning["exercise_version"], "phase": "baseline",
                "item_id": item["item_id"], "choice": choice, "response_time_ms": 900})
            assert saved.status_code == 200, saved.text
        plan = store.latest_plan("demo-user")
        step = next((row for row in plan["steps"] if row["exercise_type_id"] == "EX-02"), None)
        assert step is not None, plan
        assert step["action"] == "targeted_training" and step["launch_tier"] == "tier-1", step
        launch = client.post("/api/training/blocks", json={"session_id": sid, "exercise_id": "EX-02"})
        assert launch.status_code == 201, launch.text
        assert launch.json()["block"]["tier"] == step["launch_tier"]
        assert launch.json()["plan_alignment"]["matched"] is True

        # UP, HOLD and DOWN are each represented by the same authoritative event
        # source consumed by both plan-v2 and the launch guard.
        for index, expected in enumerate(("tier-2", "tier-2", "tier-1"), start=1):
            add_difficulty_event(sid, expected, f"r2-tier-{index}")
            revised = reconcile_plan(store, {"kind": "r2_tier_probe", "reference": f"r2-{index}"}, session_id=sid)
            tier_step = next(row for row in revised["steps"] if row["exercise_type_id"] == "EX-02")
            assert tier_step["launch_tier"] == expected and tier_step["difficulty_tier"] == expected, tier_step
            launched = client.post("/api/training/blocks", json={"session_id": sid, "exercise_id": "EX-02"})
            assert launched.status_code == 201, launched.text
            assert launched.json()["block"]["tier"] == expected, launched.json()
            assert launched.json()["plan_alignment"]["matched"] is True
            if expected == "tier-2":
                compatibility = client.post("/api/training/blocks", json={
                    "session_id": sid, "exercise_id": "EX-02", "tier": "tier-1"})
                assert compatibility.status_code == 201, compatibility.text
                assert compatibility.json()["plan_alignment"]["matched"] is False

        # RJ-03: adversarial provider prose cannot override canonical fields.
        context = build_twin_context(store, "demo-user", focus_exercise_id="EX-02",
                                     learner_reports=[{"text": "show my reasoning result"}])
        context["assisted_training"] = False
        subject = {"exercise_id": "EX-02", "dimension": "reasoning", "source": "explicit_selection"}
        baseline = grounded_reply(context, subject, "show my reasoning result")
        context["families"]["reasoning"]["index_0_100"] = 12.5
        context["families"]["reasoning"]["uncertainty_status"] = "PRELIMINARY_HIGH_UNCERTAINTY"
        baseline = grounded_reply(context, subject, "show my reasoning result")
        assert "12.5" in baseline["observation"], baseline["observation"]
        wrong_family = "EX-01" if baseline["recommended_exercise_id"] != "EX-01" else "EX-02"
        cases = (
            {"explanation": "Your result was 100%."},
            {"follow_up": "You improved by 100%."},
            {"recommended_exercise_id": wrong_family},
            {"recommended_difficulty": "tier-3"},
            {"explanation": "This is reliable and certain."},
            {"explanation": "I gave you a hint and helped you answer."},
        )
        for changes in cases:
            try:
                validate_generated(provider_shape(baseline, **changes), baseline, context, subject)
            except ValueError:
                pass
            else:
                raise AssertionError(f"adversarial provider output was accepted: {changes}")
        assert validate_generated(provider_shape(baseline), baseline, context, subject)

        # Unassessed evidence cannot be converted into a measured result.
        unassessed = {"exercise_id": "EX-01", "dimension": "working_memory", "source": "explicit_selection"}
        unassessed_baseline = grounded_reply(context, unassessed, "show Memory")
        try:
            validate_generated(provider_shape(unassessed_baseline,
                                              explanation="Your score improved by 20 percent."),
                               unassessed_baseline, context, unassessed)
        except ValueError:
            pass
        else:
            raise AssertionError("unassessed provider claim was accepted")

        # RJ-06: only completed turns from this session are sent, with provenance.
        fake = FakeAdapter()
        provider_adapters.ADAPTERS["groq"] = fake
        first = client.post("/api/coach", json={
            "session_id": sid, "message": "What should I try for Reasoning?",
            "subject_exercise_id": "EX-02"}).json()
        fake.reply = provider_shape(first["response"])
        failed_id = str(uuid.uuid4())
        store.reserve_coach_turn({
            "request_id": failed_id, "learner_id": "demo-user", "session_id": sid,
            "subject_exercise_id": "EX-02", "subject_dimension": "reasoning",
            "subject_source": "explicit_selection", "provider_requested": "local",
            "coach_version": "coach-v2", "payload_hash": failed_id,
            "message": "failed", "request": {"message": "failed"},
        })
        store.fail_coach_turn(failed_id, "probe_failure")
        in_progress_id = str(uuid.uuid4())
        store.reserve_coach_turn({
            "request_id": in_progress_id, "learner_id": "demo-user", "session_id": sid,
            "subject_exercise_id": "EX-02", "subject_dimension": "reasoning",
            "subject_source": "explicit_selection", "provider_requested": "local",
            "coach_version": "coach-v2", "payload_hash": in_progress_id,
            "message": "in progress", "request": {"message": "in progress"},
        })
        other = client.post("/api/coach", json={
            "session_id": other_sid, "message": "What should I try for Reasoning?",
            "subject_exercise_id": "EX-02"}).json()
        second = client.post("/api/coach", json={
            "session_id": sid, "message": "What did you recommend before?",
            "subject_exercise_id": "EX-02", "allow_remote": True, "provider": "groq",
            "provider_consent_recorded": True}).json()
        assert second["provider_status"] == "validated", second
        history = fake.last_payload["prior_turns"]
        assert [row["role"] for row in history] == ["learner", "assistant"], history
        assert all(row["provenance"] in {"learner_request", "validated_assistant_turn"} for row in history)
        assert first["request_id"] in json.dumps(history)
        assert failed_id not in json.dumps(history) and in_progress_id not in json.dumps(history)
        assert other["request_id"] not in json.dumps(history)
        visible = client.get("/api/coach/conversation", params={"session_id": sid}).json()["turns"]
        assert all(row["status"] == "completed" for row in visible)
        assert not any(row["request_id"] in {failed_id, in_progress_id} for row in visible)

    receipt = {
        "status": "PASS",
        "batch": "R2",
        "requirements": ["RJ-03", "RJ-04", "RJ-06"],
        "checks": ["RJ-03 adversarial field binding", "RJ-04 baseline/UP/HOLD/DOWN plan launch agreement",
                   "RJ-06 bounded validated history and follow-up"],
        "live_provider": "not exercised",
        "browser": "not exercised",
    }
    receipt_path = ROOT / "output" / "verification" / "r2-rj03-rj04-rj06.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
finally:
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{fixture}{suffix}")
        if path.exists():
            path.unlink()
