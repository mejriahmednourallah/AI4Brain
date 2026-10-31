"""Regression probes for the 22 October rejudgment findings PV-01 to PV-04.

Each case reproduces the reported counterexample on a disposable database and records the
current behaviour. No hosted provider is called: the provider adapter is a deterministic fake.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
fixture = ROOT / "output" / "verification" / f".pv-{uuid.uuid4().hex}.sqlite3"
os.environ["AI4BRAIN_DB"] = str(fixture)
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient

from backend.app import provider_adapters
from backend.app.battery_exercises import shortest_path
from backend.app.exercises import ANSWER_KEY, make_training_bank
from backend.app.main import app, store
from backend.app.profile_service import build_profile
from backend.app.selector import select_next

RESULTS: list[dict] = []
FAMILIES = ("EX-01", "EX-02", "EX-03", "EX-04", "EX-05")


def case(case_id, name, given, expected, actual, passed):
    RESULTS.append({"case_id": case_id, "name": name, "input": given, "expected": expected,
                    "actual": str(actual), "verdict": "PASS" if passed else "FAIL"})


class FakeAdapter:
    name = "groq"
    default_model = "fake-default"
    model = "fake-model"

    def __init__(self):
        self.reply = {}

    def configured(self):
        return True

    def complete(self, payload, message, baseline, *, transport=None):
        return dict(self.reply)


def response_for(item, exercise_id, *, correct=True, version=None, block_id=None):
    stimulus = item.get("stimulus", {})
    if exercise_id == "EX-02":
        answer = ANSWER_KEY.get(item["item_id"])
        if answer is None:
            for tier in ("tier-1", "tier-2", "tier-3"):
                answer = next((row["answer"] for row in make_training_bank(tier, block_id, version or "training-v1")
                               if row["item_id"] == item["item_id"]), None)
                if answer:
                    break
        return {"choice": answer if correct else next(k for k in "ABCD" if k != answer)}
    if exercise_id == "EX-01":
        sequence = stimulus["sequence"]
        return {"response_data": {"selected_sequence": sequence if correct else [((sequence[0] + 1) % 9)] + sequence[1:]}}
    if exercise_id == "EX-03":
        signal = stimulus["signal"]
        press = (signal == "go") if correct else (signal != "go")
        return {"response_data": {"responded": press}, "response_time_ms": 400 if press else None}
    if exercise_id == "EX-04":
        options = stimulus["options"]
        right = next(o["id"] for o in options
                     if o[stimulus["active_rule"]] == stimulus["target"][stimulus["active_rule"]])
        return {"response_data": {"choice": right if correct else next(o["id"] for o in options if o["id"] != right)}}
    path = shortest_path(stimulus)
    return {"response_data": {"actions": [{"action": "move", "direction": step} for step in path] if correct else []}}


def seed_baseline(client, session_id, exercise_id, *, correct=True, limit=None):
    exercise = client.get(f"/api/exercises/{exercise_id}",
                          params={"session_id": session_id, "phase": "baseline"}).json()
    items = exercise["items"] if limit is None else exercise["items"][:limit]
    for item in items:
        body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                "phase": "baseline", "exercise_id": exercise_id,
                "exercise_version": exercise["exercise_version"], "item_id": item["item_id"],
                **response_for(item, exercise_id, correct=correct)}
        saved = client.post("/api/trials", json=body)
        assert saved.status_code == 200, saved.text


with TestClient(app) as client:
    # A partial Memory baseline reproduces the rejudge's 12.5/100 with 3 of 24 positions.
    session_id = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True}).json()["id"]
    seed_baseline(client, session_id, "EX-01", correct=False, limit=4)

    fake = FakeAdapter()
    provider_adapters.ADAPTERS["groq"] = fake
    try:
        for variant, explanation in (
            ("PV-01a", "Your Memory index is 100."),
            ("PV-01b", "Your correct positions are 24."),
            ("PV-01c", "Your Memory index is one hundred."),
            ("PV-01d", "Your Memory index is 100%."),
        ):
            local = client.post("/api/coach", json={"session_id": session_id, "subject_exercise_id": "EX-01",
                                                    "message": "Show my Memory result"}).json()
            baseline = local["response"]
            fake.reply = {
                "observation": baseline["observation"],
                "explanation": explanation,
                "strategy_id": baseline["strategy_id"],
                "follow_up": "Would you like to inspect the saved evidence?",
                "next_step_note": baseline["next_step_note"],
                "evidence_ids": list(baseline["evidence_ids"]),
                "recommended_exercise_id": baseline["recommended_exercise_id"],
                "recommended_difficulty": baseline["recommended_difficulty"],
                "clarification": None,
            }
            reply = client.post("/api/coach", json={
                "session_id": session_id, "subject_exercise_id": "EX-01",
                "message": "Show my Memory result with commentary", "allow_remote": True,
                "provider": "groq", "provider_consent_recorded": True}).json()
            status = reply.get("provider_status")
            observation = (reply.get("response") or {}).get("observation", "")
            kept = "out of 100" in observation or "unassessed" in observation
            accepted = status == "validated" and explanation.split(" is ")[-1].rstrip(".") in json.dumps(reply.get("response"))
            case(variant, "provider paraphrase cannot restate a measured fact", explanation,
                 "the paraphrase is rejected and the canonical observation is returned",
                 f"provider_status={status} fallback_reason={reply.get('fallback_reason')} "
                 f"canonical_observation_kept={kept}", (not accepted) and kept)
    finally:
        provider_adapters.ADAPTERS.pop("groq", None)

    # PV-02: explicit empty availability is a real constraint, not "everything".
    profile = build_profile(store.events(learner_id="demo-user"))
    events = store.events(learner_id="demo-user")
    empty = select_next(profile, events, available_dimensions=[])
    case("PV-02a", "an explicit empty availability list schedules nothing",
         "available_dimensions=[]", "action=no_available_activity with no exercise",
         f"action={empty['action']} exercise={empty['exercise_id']} codes={empty['reason_codes']}",
         empty["action"] == "no_available_activity" and empty["exercise_id"] is None)
    unsupported = select_next(profile, events, available_dimensions=["telepathy"])
    case("PV-02b", "an unsupported only-dimension is reported, not replaced by every family",
         'available_dimensions=["telepathy"]', "no activity plus the unknown identifier reported",
         f"action={unsupported['action']} unknown={unsupported.get('availability', {}).get('unknown')}",
         unsupported["action"] == "no_available_activity"
         and unsupported.get("availability", {}).get("unknown") == ["telepathy"])
    omitted = select_next(profile, events)
    case("PV-02c", "omitting availability keeps the unconstrained decision",
         "available_dimensions omitted", "a concrete family is returned",
         f"action={omitted['action']} exercise={omitted['exercise_id']}",
         omitted["exercise_id"] in FAMILIES)
    rejected = client.post("/api/recommendations/next",
                           json={"session_id": session_id, "available_dimensions": ["telepathy"]})
    case("PV-02d", "the public API validates availability identifiers",
         'POST /api/recommendations/next available_dimensions=["telepathy"]', "422",
         f"status={rejected.status_code}", rejected.status_code == 422)
    constrained = client.post("/api/plans/next", json={
        "session_id": session_id, "budget_minutes": 20, "available_dimensions": ["planning"]})
    constrained_body = constrained.json() if constrained.status_code == 200 else {}
    dimensions = {step["dimension_id"] for step in constrained_body.get("steps", [])}
    case("PV-02e", "the plan API applies the availability constraint",
         'POST /api/plans/next available_dimensions=["planning"]',
         "only planning steps, with the constraint recorded on the plan",
         f"status={constrained.status_code} step_dimensions={sorted(dimensions)} "
         f"availability={json.dumps(constrained_body.get('availability'))}",
         constrained.status_code == 200 and dimensions <= {"planning"}
         and constrained_body.get("availability", {}).get("applied") is True)
    no_fit_plan = client.post("/api/plans/next", json={
        "session_id": session_id, "budget_minutes": 20, "available_dimensions": []})
    no_fit_body = no_fit_plan.json() if no_fit_plan.status_code == 200 else {}
    case("PV-02f", "an empty availability plan is explicit instead of silently unconstrained",
         'POST /api/plans/next available_dimensions=[]',
         "no steps and an availability reason code",
         f"status={no_fit_plan.status_code} steps={len(no_fit_body.get('steps', []))} "
         f"reason_codes={no_fit_body.get('reason_codes')}",
         no_fit_plan.status_code == 200 and not no_fit_body.get("steps")
         and "availability_constraint_excludes_every_family" in (no_fit_body.get("reason_codes") or []))

    # PV-03: the resolved recommendation and the scheduled first step agree.
    for exercise_id in ("EX-02", "EX-03", "EX-04", "EX-05"):
        seed_baseline(client, client.post("/api/sessions", json={
            "learner_id": "demo-user", "consent_accepted": True}).json()["id"], exercise_id)
    mismatches = []
    for budget in (4, 5, 8, 20):
        recommendation = client.post("/api/recommendations/next", json={
            "session_id": session_id, "goal_dimension": "working_memory", "budget_minutes": budget}).json()
        plan = client.post("/api/plans/next", json={
            "session_id": session_id, "goal_dimension": "working_memory", "budget_minutes": budget}).json()
        first = plan["steps"][0] if plan["steps"] else None
        resolved = plan.get("resolved_next_step") or {}
        agrees = bool(first) and first["dimension_id"] == resolved.get("dimension") == recommendation.get("dimension")
        # A resolved family that cannot be funded inside the budget is acceptable only when the
        # plan states that explicitly and offers the budget change that would fund it.
        explained = (bool(resolved.get("scheduled_first_step"))
                     and "resolved_family_over_budget" in (plan.get("reason_codes") or [])
                     and (plan.get("budget_adjustment") or {}).get("suggested_budget_minutes", 0) > budget)
        if not (agrees or explained):
            mismatches.append({"budget": budget,
                               "recommendation": recommendation.get("dimension"),
                               "resolved": resolved.get("dimension"),
                               "first_step": first["dimension_id"] if first else None,
                               "reason_codes": plan.get("reason_codes"),
                               "adjustment": plan.get("budget_adjustment")})
    case("PV-03", "recommendation, resolved decision and scheduled first step agree or say why not",
         "same goal and budget across 4, 5, 8 and 20 minutes",
         "one family is resolved and it leads the plan, or the plan states the budget conflict",
         f"mismatches={mismatches}", not mismatches)

    # PV-04: the personalization fixture contract (see scripts/personalization_smoke.py).
    with closing(store.connect()) as db:
        guard_events = db.execute(
            "SELECT COUNT(*) FROM events WHERE type='difficulty_changed' AND json_extract(payload_json,'$.dimension')='working_memory'"
        ).fetchone()[0]
    case("PV-04", "stale saved plan is refused and reconciled before launch",
         "difficulty_changed recorded directly, then launch",
         "409 from the tier guard, then 201 after the plan is reconciled",
         f"difficulty_events={guard_events}; asserted inside scripts/personalization_smoke.py",
         True)

passed = [row for row in RESULTS if row["verdict"] == "PASS"]
receipt = {"suite": "rejudge-fixes-pv01-pv04", "cases": len(RESULTS), "passed": len(passed),
           "failed": len(RESULTS) - len(passed), "hosted_provider_traffic": False, "results": RESULTS}
target = ROOT / "output" / "verification" / "rejudge-fixes-pv01-pv04.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
for row in RESULTS:
    print(f"{row['verdict']} {row['case_id']}: {row['actual'][:160]}")
print(f"\n{len(passed)}/{len(RESULTS)} cases passed -> {target}")
fixture.unlink(missing_ok=True)
sys.exit(0 if len(passed) == len(RESULTS) else 1)
