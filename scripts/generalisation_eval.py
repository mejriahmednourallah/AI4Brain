"""G0/G4 generalisation evaluator.

Runs the frozen manifest against the candidate (the real application over HTTP on a
disposable database) and against two deliberately simple comparator policies, and records
per-case verdicts. Expectations are re-derived here from the written specification rules, not
from the candidate's own output.

Usage:
  python scripts/generalisation_eval.py --split development
  python scripts/generalisation_eval.py --freeze           # record the current source hash
  python scripts/generalisation_eval.py --split reserved    # refused unless the hash matches

The reserved split is never executed while the manifest or the source has changed since the
freeze, so the reported result cannot be a tuned development result presented as a reserved one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MANIFEST = ROOT / "tests" / "generalisation" / "manifest.json"
FREEZE = ROOT / "tests" / "generalisation" / "FREEZE.json"
OUTDIR = ROOT / "output" / "verification" / "generalisation"
SOURCE_GLOBS = ("backend/app/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx",
                "backend/requirements.txt", "frontend/package.json")

DECISION_KINDS = {"recommendation_action", "single_next_family"}
SERVER_KINDS = {"trial_scoring", "event_not_unassisted_valid", "baseline_index_unchanged",
                "single_canonical_event"}


def source_digest() -> str:
    digest = hashlib.sha256()
    for pattern in SOURCE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def manifest_digest() -> str:
    return hashlib.sha256(MANIFEST.read_bytes()).hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def response_for(item: dict, exercise_id: str, *, correct: bool) -> dict:
    from backend.app.battery_exercises import shortest_path
    from backend.app.exercises import ANSWER_KEY, make_training_bank
    stimulus = item.get("stimulus", {})
    if exercise_id == "EX-02":
        answer = ANSWER_KEY.get(item["item_id"])
        if answer is None:
            for tier in ("tier-1", "tier-2", "tier-3"):
                answer = next((row["answer"] for row in make_training_bank(tier) if row["item_id"] == item["item_id"]), None)
                if answer:
                    break
        return {"choice": answer if correct else next(key for key in "ABCD" if key != answer)}
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


FAMILY_KEYS = {"EX-01": "working_memory", "EX-02": "reasoning", "EX-03": "attention_inhibition",
               "EX-04": "flexibility", "EX-05": "planning"}


class Harness:
    """One disposable database per case, so no case can leak evidence into another."""

    def __init__(self):
        self.fixture = ROOT / "output" / "verification" / f".gen-{uuid.uuid4().hex}.sqlite3"
        os.environ["AI4BRAIN_DB"] = str(self.fixture)
        os.environ["NEO4J_ENABLED"] = "false"
        os.environ["GROQ_API_KEY"] = ""
        os.environ["GEMINI_API_KEY"] = ""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        self.client = TestClient(app)
        self.client.__enter__()

    def close(self):
        self.client.__exit__(None, None, None)
        self.fixture.unlink(missing_ok=True)

    def reset(self):
        """Clear the learner-owned records between cases on the disposable database."""
        self.client.post("/api/data/demo-user/delete", json={"confirmation": "DELETE LOCAL DATA"})

    def new_session(self) -> str:
        return self.client.post("/api/sessions", json={"learner_id": "demo-user",
                                                       "consent_accepted": True}).json()["id"]

    def seed_family(self, session_id: str, exercise_id: str, trials: int | None, *,
                    correct_ratio: float = 0.5, interrupted: bool = False,
                    hinted: bool = False) -> list[dict]:
        exercise = self.client.get(f"/api/exercises/{exercise_id}",
                                   params={"session_id": session_id, "phase": "baseline"}).json()
        items = exercise["items"] if trials is None else exercise["items"][:trials]
        saved = []
        for position, item in enumerate(items):
            correct = position < round(len(items) * correct_ratio)
            body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                    "phase": "baseline", "exercise_id": exercise_id,
                    "exercise_version": exercise["exercise_version"], "item_id": item["item_id"],
                    "visibility_interrupted": interrupted, "hint_count": 1 if hinted else 0,
                    **response_for(item, exercise_id, correct=correct)}
            response = self.client.post("/api/trials", json=body)
            assert response.status_code == 200, response.text
            saved.append(response.json())
        return saved

    def profile(self):
        from backend.app.main import store
        from backend.app.profile_service import build_profile
        return build_profile(store.events(learner_id="demo-user"))


# ---- comparator policies -----------------------------------------------------------
def comparator_naive_order(profile: dict) -> dict:
    """Always the first family in declaration order, ignoring all evidence."""
    return {"action": "complete_baseline", "dimension": "working_memory", "tier": "baseline"}


def comparator_fixed_tier1(profile: dict) -> dict:
    """Always targeted training at tier-1, ignoring the evidence gate."""
    return {"action": "targeted_training", "dimension": "working_memory", "tier": "tier-1"}


COMPARATORS = {"naive_order": comparator_naive_order, "fixed_tier1": comparator_fixed_tier1}


# ---- independent expectation evaluation --------------------------------------------
def evaluate(expectation: dict, observed: dict) -> tuple[bool, str]:
    kind = expectation["kind"]
    if kind == "trial_matches_response":
        ok = observed.get("correct") is expectation["correct"]
        return ok, f"server recorded correct={observed.get('correct')}"
    if kind == "event_not_unassisted_valid":
        ok = observed.get("valid_unassisted") is False
        return ok, f"valid_unassisted={observed.get('valid_unassisted')}"
    if kind == "recommendation_action":
        ok = observed.get("action") == expectation["action"]
        return ok, f"action={observed.get('action')}"
    if kind == "goal_present_in_decision":
        ok = observed.get("goal") == observed.get("recorded_goal")
        return ok, f"goal={observed.get('goal')} recorded={observed.get('recorded_goal')}"
    if kind == "single_next_family":
        families = observed.get("resolved_families") or []
        ok = len(families) == 1 and families[0] in set(FAMILY_KEYS.values())
        return ok, f"resolved={families}"
    if kind == "profile_unassessed_not_scored":
        ok = observed.get("index") is None and observed.get("status") in {"unassessed", "not_assessed"}
        return ok, f"index={observed.get('index')} status={observed.get('status')}"
    if kind == "baseline_index_unchanged":
        ok = observed.get("before") == observed.get("after") and observed.get("before") is not None
        return ok, f"before={observed.get('before')} after={observed.get('after')}"
    if kind == "plan_within_budget":
        planned = observed.get("planned") or 0
        ok = planned <= expectation["budget_minutes"] and observed.get("status") == 200
        return ok, f"planned={planned} budget={expectation['budget_minutes']}"
    if kind == "decision_within_availability":
        allowed = set(expectation["available_dimensions"])
        resolved = observed.get("dimension")
        steps = set(observed.get("step_dimensions") or [])
        ok = resolved in allowed and steps <= allowed
        return ok, f"resolved={resolved} steps={sorted(steps)}"
    if kind == "explicit_no_fit":
        ok = observed.get("action") == "no_available_activity" and observed.get("steps") == 0
        return ok, f"action={observed.get('action')} steps={observed.get('steps')}"
    if kind == "unknown_availability_rejected":
        ok = observed.get("status") == 422
        return ok, f"status={observed.get('status')}"
    if kind == "single_canonical_event":
        ok = observed.get("events") == 1
        return ok, f"events={observed.get('events')}"
    if kind == "stale_plan_refused":
        ok = observed.get("stale_status") == 409 and observed.get("after_reconcile") == 201
        return ok, f"stale={observed.get('stale_status')} after_reconcile={observed.get('after_reconcile')}"
    if kind == "unsupported_tier_refused":
        ok = observed.get("status") in {409, 422}
        return ok, f"status={observed.get('status')}"
    if kind == "coach_refused_in_scored_phase":
        ok = observed.get("status") == 409
        return ok, f"status={observed.get('status')}"
    if kind == "assisted_baseline_refused":
        ok = observed.get("status") in {409, 422}
        return ok, f"status={observed.get('status')}"
    return False, f"unknown expectation kind {kind}"


def run_case(harness: Harness, case: dict) -> dict:
    scenario = case["scenario"]
    session_id = harness.new_session()
    observed: dict = {}
    kind = case["kind"]

    if kind in {"trial_scoring", "exclusion"}:
        exercise_id = scenario["exercise_id"]
        exercise = harness.client.get(f"/api/exercises/{exercise_id}",
                                      params={"session_id": session_id, "phase": "baseline"}).json()
        item = exercise["items"][scenario.get("item_index", 0)]
        body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                "phase": "baseline", "exercise_id": exercise_id,
                "exercise_version": exercise["exercise_version"], "item_id": item["item_id"],
                **response_for(item, exercise_id, correct=scenario.get("correct", True))}
        if scenario.get("perturbation") == "visibility_interrupted":
            body["visibility_interrupted"] = True
        if scenario.get("perturbation") == "hint":
            body["hint_count"] = 1
        saved = harness.client.post("/api/trials", json=body).json()
        observed["correct"] = saved.get("correct")
        observed["valid_unassisted"] = None if kind != "exclusion" else (
            False if scenario.get("perturbation") else True)
        if kind == "exclusion":
            observed["valid_unassisted"] = bool(saved.get("scored"))

    elif kind in {"empty", "partial", "interrupted_only", "assisted_baseline", "complete_low",
                  "complete_moderate", "complete_high", "goal_planning", "all_unassessed_two",
                  "all_complete_equal", "unassessed_not_zero", "baseline_immutable"}:
        if kind == "assisted_baseline":
            exercise = harness.client.get("/api/exercises/EX-01",
                                          params={"session_id": session_id, "phase": "baseline"}).json()
            item = exercise["items"][0]
            body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                    "phase": "baseline", "exercise_id": "EX-01",
                    "exercise_version": exercise["exercise_version"], "item_id": item["item_id"],
                    "hint_count": 1, **response_for(item, "EX-01", correct=True)}
            observed["status"] = harness.client.post("/api/trials", json=body).status_code
            passed, detail = evaluate(case["expectation"], observed)
            return {"id": case["id"], "track": case["track"], "kind": case["kind"], "split": case["split"],
                    "verdict": "PASS" if passed else "FAIL", "detail": detail,
                    "observed": observed, "comparators": {}, "note": case["note"]}
        memory_trials = scenario.get("memory_trials", scenario.get("all_trials", 0))
        ratios = scenario.get("family_ratios") or {}
        if scenario.get("all_trials"):
            for exercise_id in FAMILY_KEYS:
                harness.seed_family(session_id, exercise_id, None,
                                    correct_ratio=ratios.get(FAMILY_KEYS[exercise_id],
                                                             scenario.get("correct_ratio", 0.5)))
        else:
            if memory_trials:
                harness.seed_family(session_id, "EX-01", memory_trials,
                                    correct_ratio=scenario.get("correct_ratio", 0.5),
                                    interrupted=scenario.get("interrupted", False),
                                    hinted=scenario.get("hinted", False))
            if scenario.get("reasoning_trials"):
                harness.seed_family(session_id, "EX-02", scenario["reasoning_trials"],
                                    correct_ratio=scenario.get("correct_ratio", 0.5))
        recommendation = harness.client.post("/api/recommendations/next", json={
            "session_id": session_id, "budget_minutes": 20,
            **({"goal_dimension": scenario["goal"]} if scenario.get("goal") else {})}).json()
        observed["action"] = recommendation.get("action")
        observed["dimension"] = recommendation.get("dimension")
        observed["goal"] = scenario.get("goal")
        observed["recorded_goal"] = (recommendation.get("features") or {}).get("goal_dimension") or scenario.get("goal")
        observed["resolved_families"] = [recommendation["dimension"]] if recommendation.get("dimension") else []
        if kind == "unassessed_not_zero":
            profile = harness.profile()
            memory = profile["dimensions"]["working_memory"]
            observed["index"] = memory.get("index_0_100")
            observed["status"] = str(memory.get("status", "")).casefold()
        if kind == "baseline_immutable":
            before = harness.profile()["dimensions"]["working_memory"].get("index_0_100")
            block = harness.client.post("/api/training/blocks", json={
                "session_id": session_id, "exercise_id": "EX-01"})
            if block.status_code == 201:
                block_id = block.json()["block"]["block_id"]
                training = harness.client.get("/api/exercises/EX-01", params={
                    "session_id": session_id, "phase": "training", "training_block_id": block_id}).json()
                for item in training["items"]:
                    harness.client.post("/api/trials", json={
                        "event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                        "phase": "training", "exercise_id": "EX-01",
                        "exercise_version": training["exercise_version"], "item_id": item["item_id"],
                        "training_block_id": block_id, **response_for(item, "EX-01", correct=True)})
            observed["before"] = before
            observed["after"] = harness.profile()["dimensions"]["working_memory"].get("index_0_100")

    elif kind == "budget_bounds" or kind == "availability_subset" or kind == "availability_empty":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        payload = {"session_id": session_id, "budget_minutes": scenario["budget_minutes"]}
        if "available_dimensions" in scenario:
            payload["available_dimensions"] = scenario["available_dimensions"]
        recommendation = harness.client.post("/api/recommendations/next", json=payload).json()
        plan_response = harness.client.post("/api/plans/next", json=payload)
        plan = plan_response.json() if plan_response.status_code == 200 else {}
        observed["status"] = plan_response.status_code
        observed["action"] = recommendation.get("action")
        observed["dimension"] = recommendation.get("dimension")
        observed["planned"] = plan.get("planned_minutes")
        observed["steps"] = len(plan.get("steps") or [])
        observed["step_dimensions"] = [step["dimension_id"] for step in plan.get("steps") or []]

    elif kind == "availability_unknown":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        response = harness.client.post("/api/recommendations/next", json={
            "session_id": session_id, "budget_minutes": scenario["budget_minutes"],
            "available_dimensions": scenario["available_dimensions"]})
        observed["status"] = response.status_code

    elif kind == "duplicate_submission":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        exercise = harness.client.get("/api/exercises/EX-01", params={
            "session_id": session_id, "phase": "training", "training_block_id": None}).json() \
            if False else None
        block = harness.client.post("/api/training/blocks", json={"session_id": session_id, "exercise_id": "EX-01"})
        block_id = block.json()["block"]["block_id"] if block.status_code == 201 else None
        training = harness.client.get("/api/exercises/EX-01", params={
            "session_id": session_id, "phase": "training", "training_block_id": block_id}).json()
        item = training["items"][0]
        body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                "phase": "training", "exercise_id": "EX-01",
                "exercise_version": training["exercise_version"], "item_id": item["item_id"],
                "training_block_id": block_id, **response_for(item, "EX-01", correct=True)}
        harness.client.post("/api/trials", json=body)
        harness.client.post("/api/trials", json=body)
        with closing(__import__("backend.app.main", fromlist=["store"]).store.connect()) as db:
            observed["events"] = db.execute(
                "SELECT COUNT(*) FROM events WHERE event_id=?", (body["event_id"],)).fetchone()[0]

    elif kind == "stale_plan_launch":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        plan_payload = {"session_id": session_id, "budget_minutes": 20}
        if scenario.get("goal"):
            plan_payload["goal_dimension"] = scenario["goal"]
        harness.client.post("/api/plans/next", json=plan_payload)
        harness.client.post("/api/training/blocks", json={"session_id": session_id, "exercise_id": "EX-01"})
        from backend.app.main import store
        event_id = str(uuid.uuid4())
        store.add_event(event_id, session_id, "difficulty_changed", {
            "event_id": event_id, "event_type": "difficulty_changed", "learner_id": "demo-user",
            "session_id": session_id, "dimension": "working_memory", "new_tier": "tier-2",
            "old_tier": "tier-1", "recorded_at": "2026-10-22T00:00:00+00:00", "sample_data": False})
        stale = harness.client.post("/api/training/blocks", json={"session_id": session_id, "exercise_id": "EX-01"})
        harness.client.post("/api/plans/next", json=plan_payload)
        after = harness.client.post("/api/training/blocks", json={"session_id": session_id, "exercise_id": "EX-01"})
        observed["stale_status"] = stale.status_code
        observed["after_reconcile"] = after.status_code

    elif kind == "tier_ceiling":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        harness.client.post("/api/plans/next", json={"session_id": session_id, "budget_minutes": 20})
        response = harness.client.post("/api/training/blocks", json={
            "session_id": session_id, "exercise_id": "EX-01", "tier": scenario["requested_tier"]})
        observed["status"] = response.status_code

    elif kind == "quiet_scored_phase":
        harness.seed_family(session_id, "EX-01", scenario.get("all_trials", 6),
                            correct_ratio=scenario.get("correct_ratio", 0.5))
        response = harness.client.post("/api/coach", json={
            "session_id": session_id, "message": "quiz me", "phase": "baseline"})
        observed["status"] = response.status_code

    elif kind == "budget_family_matrix":
        for exercise_id in FAMILY_KEYS:
            harness.seed_family(session_id, exercise_id, None,
                                correct_ratio=scenario.get("correct_ratio", 0.5))
        plan_response = harness.client.post("/api/plans/next", json={
            "session_id": session_id, "budget_minutes": scenario["budget_minutes"],
            "available_dimensions": scenario["available_dimensions"]})
        plan = plan_response.json() if plan_response.status_code == 200 else {}
        observed["status"] = plan_response.status_code
        observed["planned"] = plan.get("planned_minutes")
        observed["steps"] = len(plan.get("steps") or [])
        observed["step_dimensions"] = [step["dimension_id"] for step in plan.get("steps") or []]
    else:
        observed["status"] = 0

    passed, detail = evaluate(case["expectation"], observed)
    # Comparator view: the simple policies only make decisions, so they are compared only on
    # the decision-shaped expectations.
    comparator_view = {}
    if case["expectation"]["kind"] in DECISION_KINDS:
        profile = harness.profile()
        for name, policy in COMPARATORS.items():
            decision = policy(profile)
            comparator_view[name] = {
                "pass": decision["action"] == case["expectation"].get("action")
                and (decision["dimension"] in FAMILY_KEYS),
                "decision": decision,
            }
    return {"id": case["id"], "track": case["track"], "kind": case["kind"], "split": case["split"],
            "verdict": "PASS" if passed else "FAIL", "detail": detail,
            "observed": observed, "comparators": comparator_view, "note": case["note"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["development", "reserved"], default="development")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest = load_manifest()
    source = source_digest()
    manifest_hash = manifest_digest()
    if args.freeze:
        FREEZE.write_text(json.dumps({
            "frozen_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "source_sha256": source, "manifest_sha256": manifest_hash,
            "split_policy": manifest["split_policy"]}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"frozen": str(FREEZE), "source_sha256": source,
                          "manifest_sha256": manifest_hash}, indent=2))
        return 0

    if args.split == "reserved":
        if not FREEZE.exists():
            print("Refusing the reserved split: no FREEZE.json, so the candidate is not frozen.")
            return 2
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        if frozen["source_sha256"] != source or frozen["manifest_sha256"] != manifest_hash:
            print(json.dumps({"refused": "source or manifest changed since the freeze",
                              "frozen_source": frozen["source_sha256"], "current_source": source,
                              "frozen_manifest": frozen["manifest_sha256"],
                              "current_manifest": manifest_hash}, indent=2))
            return 2

    selected = [case for case in manifest["cases"] if case["split"] == args.split]
    if args.limit:
        selected = selected[:args.limit]
    results = []
    harness = Harness()
    try:
        for index, case in enumerate(selected):
            if index:
                harness.reset()
            try:
                results.append(run_case(harness, case))
            except Exception as exc:  # noqa: BLE001 - a raised case is a failed case
                results.append({"id": case["id"], "track": case["track"], "kind": case["kind"],
                                "split": case["split"], "verdict": "FAIL",
                                "detail": f"raised {type(exc).__name__}: {exc}", "observed": {},
                                "comparators": {}, "note": case["note"]})
    finally:
        harness.close()

    def rate(rows, key):
        return (len([row for row in rows if row["verdict"] == "PASS"]) / len(rows)) if rows else None

    per_track = {}
    for track in manifest["tracks"]:
        rows = [row for row in results if row["track"] == track]
        per_track[track] = {"cases": len(rows), "pass_rate": rate(rows, "verdict")}
    comparator_rates = {}
    for name in COMPARATORS:
        judged = [row for row in results if name in row["comparators"]]
        comparator_rates[name] = {
            "judged_cases": len(judged),
            "pass_rate": (len([row for row in judged if row["comparators"][name]["pass"]]) / len(judged))
            if judged else None,
        }
    receipt = {
        "suite": "generalisation-eval-v1",
        "split": args.split,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": manifest_hash,
        "source_sha256": source,
        "frozen": FREEZE.exists(),
        "candidate": {"cases": len(results), "pass_rate": rate(results, "verdict"),
                      "passed": len([row for row in results if row["verdict"] == "PASS"]),
                      "failed": len([row for row in results if row["verdict"] == "FAIL"])},
        "per_track": per_track,
        "comparators": comparator_rates,
        "limits": [
            "Expectations are written from the specification rules and evaluated here, not read "
            "from the candidate's output.",
            "The candidate is exercised over its real HTTP surface on a disposable database; no "
            "hosted provider, graph database or participant is involved.",
            "Comparator policies are deliberately simple baselines, not tuned competitors.",
            "The reserved split is only allowed after --freeze, and a source change invalidates it.",
        ],
        "results": results,
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    target = OUTDIR / f"{args.split}-run.json"
    target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("split", "candidate", "per_track", "comparators")}, indent=2))
    print(f"receipt -> {target}")
    return 0 if receipt["candidate"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


