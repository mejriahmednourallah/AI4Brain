"""Forty named R4 evaluation cases for the connected agent.

This is the supervisor evaluation manifest required by the R0-R6 correction plan.
Each case records its input, the expectation, the observed behaviour, an individual
verdict and the source of the assertion. It runs against a disposable SQLite
database, never against hosted providers, and uses the single-learner product
surface deliberately: the application is local and single-learner, so the cases are
ordered so that no case can silently change the evidence another case depends on.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
fixture = ROOT / "output" / "verification" / f".r4-cases-{uuid.uuid4().hex}.sqlite3"
os.environ["AI4BRAIN_DB"] = str(fixture)
os.environ["NEO4J_ENABLED"] = "false"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from contextlib import closing

from fastapi.testclient import TestClient

from backend.app import coach_routes, provider_adapters
from backend.app.battery_exercises import shortest_path
from backend.app.coach_v2 import grounded_reply, validate_generated
from backend.app.exercises import ANSWER_KEY, make_training_bank
from backend.app.main import app, store
from backend.app.twin_context import build_twin_context

CASES: list[dict[str, object]] = []
FAMILIES = {"EX-01": "working_memory", "EX-02": "reasoning", "EX-03": "attention_inhibition",
            "EX-04": "flexibility", "EX-05": "planning"}


def record(case_id, group, name, given, expected, actual, passed, source):
    CASES.append({"case_id": case_id, "group": group, "name": name, "input": given,
                  "expected": expected, "actual": actual, "verdict": "PASS" if passed else "FAIL",
                  "source": source})


def run(case_id, group, name, given, expected, source, probe):
    try:
        actual, passed = probe()
    except Exception as exc:  # noqa: BLE001 - a raised probe is a failed case, not a crashed suite
        actual, passed = f"raised {type(exc).__name__}: {exc}", False
    record(case_id, group, name, given, expected, str(actual), bool(passed), source)


class FakeAdapter:
    def __init__(self, reply=None, raises: Exception | None = None, name: str = "groq"):
        self.name = name
        self.default_model = "fake-default"
        self.model = "fake-model"
        self.reply = reply
        self.raises = raises
        self.calls = 0
        self.last_payload = None

    def configured(self):
        return True

    def complete(self, payload, message, baseline, *, transport=None):
        self.calls += 1
        self.last_payload = payload
        if self.raises:
            raise self.raises
        return dict(self.reply or {})


def provider_shape(baseline, **changes):
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
        right = next(option["id"] for option in options
                     if option[stimulus["active_rule"]] == stimulus["target"][stimulus["active_rule"]])
        return {"response_data": {"choice": right if correct else next(o["id"] for o in options if o["id"] != right)}}
    path = shortest_path(stimulus)
    return {"response_data": {"actions": [{"action": "move", "direction": step} for step in path] if correct else []}}


def seed_baseline(client, session_id, exercise_id, limit=None):
    exercise = client.get(f"/api/exercises/{exercise_id}",
                          params={"session_id": session_id, "phase": "baseline"}).json()
    items = exercise["items"] if limit is None else exercise["items"][:limit]
    for item in items:
        body = {"event_id": str(uuid.uuid4()), "session_id": session_id, "learner_id": "demo-user",
                "phase": "baseline", "exercise_id": exercise_id,
                "exercise_version": exercise["exercise_version"], "item_id": item["item_id"],
                **response_for(item, exercise_id)}
        saved = client.post("/api/trials", json=body)
        assert saved.status_code == 200, saved.text


def numbers(text):
    cleaned, digits = [], ""
    for char in str(text):
        if char.isdigit() or char == ".":
            digits += char
        else:
            if digits:
                cleaned.append(digits.strip("."))
            digits = ""
    if digits:
        cleaned.append(digits.strip("."))
    return {value for value in cleaned if value}


def coaching_events(event_type, request_id=None):
    with closing(store.connect()) as db:
        if request_id is None:
            row = db.execute("SELECT COUNT(*) FROM events WHERE type=?", (event_type,)).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) FROM events WHERE type=? AND "
                             "json_extract(payload_json,'$.request_id')=?", (event_type, request_id)).fetchone()
    return int(row[0])


with TestClient(app) as client:
    seeded = client.post("/api/sessions", json={"learner_id": "demo-user", "consent_accepted": True}).json()["id"]

    # B. Missing, partial, ambiguous and learner-reported evidence (before any baseline exists) ---
    def missing_evidence():
        reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-03",
                                                "message": "How am I doing in Attention?"}).json()["response"]
        observation = reply["observation"].casefold()
        passed = ("unassessed" in observation or "no complete uncoached baseline" in observation) and reply["evidence_ids"] == []
        return f"observation={reply['observation']!r} evidence_ids={reply['evidence_ids']}", passed

    run("B1", "missing_partial_ambiguous", "unassessed family is reported without an invented index",
        "no saved baseline for Attention", "the reply says it is unassessed and cites no evidence",
        "backend/app/coach_v2.py::factual_observation", missing_evidence)

    def ambiguous_question():
        # A session without a conversation or current activity, so ambiguity is reachable.
        quiet_session = client.post("/api/sessions", json={
            "learner_id": "demo-user", "consent_accepted": True}).json()["id"]
        reply = client.post("/api/coach", json={"session_id": quiet_session,
                                                "message": "Is Memory or Reasoning weaker for me?"}).json()
        answer = reply["response"]
        passed = bool(answer.get("clarification")) and reply["subject"]["exercise_id"] is None
        return f"clarification={answer.get('clarification')!r} subject={reply['subject']['exercise_id']}", passed

    run("B2", "missing_partial_ambiguous", "an ambiguous family question asks one clarification",
        "two families named with equal weight", "a clarification question and no family claim",
        "backend/app/twin_context.py::resolve_subject", ambiguous_question)

    def unknown_family():
        reply = client.post("/api/coach", json={"session_id": seeded, "message": "How am I doing in telepathy?"}).json()
        answer = reply["response"]
        passed = "telepathy" not in json.dumps(answer.get("evidence_ids") or []).casefold() and (
            answer.get("clarification") is not None or reply["subject"]["exercise_id"] in FAMILIES)
        return f"subject={reply['subject']['exercise_id']} clarification={answer.get('clarification')!r}", passed

    run("B3", "missing_partial_ambiguous", "an unknown family name is not turned into evidence",
        "a family that does not exist", "no invented family, evidence or index",
        "backend/app/twin_context.py::resolve_subject", unknown_family)

    seed_baseline(client, seeded, "EX-02", limit=2)

    def partial_evidence():
        reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                "message": "What is my reasoning index?"}).json()["response"]
        text = " ".join((reply["observation"], reply["explanation"])).casefold()
        passed = "unassessed" in text or "will not describe an index" in text or "will not infer" in text
        return f"observation+explanation={text[:200]!r}", passed

    run("B4", "missing_partial_ambiguous", "a partial baseline is described as incomplete",
        "two of six Reasoning baseline trials saved", "no index is inferred from partial evidence",
        "backend/app/coach_v2.py::factual_observation", partial_evidence)

    def learner_report_separated():
        before = build_twin_context(store, "demo-user", focus_exercise_id="EX-02")
        after = build_twin_context(store, "demo-user", focus_exercise_id="EX-02",
                                   learner_reports=[{"text": "I think I scored 100 on Reasoning."}])
        passed = (before["families"]["reasoning"]["index_0_100"] == after["families"]["reasoning"]["index_0_100"]
                  and bool(after.get("learner_reported")))
        return (f"index_before={before['families']['reasoning']['index_0_100']} "
                f"index_after={after['families']['reasoning']['index_0_100']} "
                f"learner_reported={len(after.get('learner_reported') or [])}"), passed

    run("B5", "missing_partial_ambiguous", "a learner statement cannot change measured evidence",
        "the learner claims a score of 100", "the canonical index is unchanged and the statement is separate",
        "backend/app/twin_context.py::build_twin_context", learner_report_separated)

    # A. Five family-specific explanations --------------------------------------------------------
    # Each family is seeded through its own session so item-level duplicate protection is honoured
    # while the learner-level evidence still aggregates.
    for exercise_id in FAMILIES:
        seed_baseline(client, client.post("/api/sessions", json={
            "learner_id": "demo-user", "consent_accepted": True}).json()["id"], exercise_id)
    context = build_twin_context(store, "demo-user")
    indices = {exercise_id: context["families"][dimension].get("index_0_100")
               for exercise_id, dimension in FAMILIES.items()}

    for index, (exercise_id, dimension) in enumerate(FAMILIES.items(), start=1):
        label = context["families"][dimension].get("label", exercise_id)

        def probe_family(exercise_id=exercise_id, dimension=dimension, label=label):
            reply = client.post("/api/coach", json={
                "session_id": seeded, "subject_exercise_id": exercise_id,
                "message": f"Show my {label} result"}).json()
            answer = reply["response"]
            canonical = context["families"][dimension].get("index_0_100")
            seen = numbers(answer["observation"])
            others = {str(value) for eid, value in indices.items() if eid != exercise_id and value is not None}
            leaked = (others - {str(canonical)}) & seen if canonical is not None else set()
            passed = (reply["subject"]["exercise_id"] == exercise_id
                      and canonical is not None and f"{canonical:g}" in seen and not leaked)
            return (f"subject={reply['subject']['exercise_id']} canonical={canonical} "
                    f"numbers={sorted(seen)} leaked={sorted(leaked)}"), passed

        run(f"A{index}", "family_explanations", f"{exercise_id} quotes only its own canonical evidence",
            f"question about {exercise_id} with a completed baseline",
            "the asked family is the subject, its canonical index appears and no other family index leaks",
            "scripts/r4_case_manifest.py", probe_family)

    # C. Factual, policy, assistance, clinical and identifier attacks ------------------------------
    context_r = build_twin_context(store, "demo-user", focus_exercise_id="EX-02",
                                   learner_reports=[{"text": "show my reasoning result"}])
    context_r["assisted_training"] = False
    subject_r = {"exercise_id": "EX-02", "dimension": "reasoning", "source": "explicit_selection"}
    baseline_r = grounded_reply(context_r, subject_r, "show my reasoning result")
    attacks = (
        ("C1", "invented index value, including the rejudge paraphrases",
         [{"explanation": "Your reasoning index is 87."},
          {"explanation": "Your Memory index is 100."},
          {"explanation": "Your correct positions are 24."},
          {"explanation": "Your Memory index is one hundred."},
          {"follow_up": "Your reasoning score is twenty out of hundred."}]),
        ("C2", "percentage or number taken from another field",
         [{"follow_up": "You improved by 87%."},
          {"follow_up": "Your index is 100%."},
          {"explanation": "You improved by 24 positions."}]),
        ("C3", "wrong tier recommendation", [{"recommended_difficulty": "tier-3"}]),
        ("C4", "assistance claim", [{"explanation": "I gave you a hint and guided your answer."}]),
        ("C5", "certainty claim", [{"explanation": "This result is reliable and certain."}]),
        ("C6", "clinical claim", [{"explanation": "You meet the criteria for a clinical diagnosis."}]),
        ("C7", "invented evidence id", [{"evidence_ids": ["not-a-real-event"]}]),
        ("C8", "invented exercise id", [{"recommended_exercise_id": "EX-09"}]),
    )
    for case_id, label, variants in attacks:
        def probe_attack(variants=variants):
            accepted = []
            for changes in variants:
                try:
                    validate_generated(provider_shape(baseline_r, **changes), baseline_r, context_r, subject_r)
                except ValueError:
                    continue
                accepted.append(changes)
            if accepted:
                return f"accepted {len(accepted)} of {len(variants)} variants: {accepted[:2]}", False
            return f"all {len(variants)} variant(s) rejected", True

        run(case_id, "adversarial_outputs", f"provider output is rejected: {label}",
            json.dumps(variants), "every variant raises ValueError and the canonical reply is kept",
            "backend/app/coach_v2.py::validate_generated", probe_attack)

    fake = FakeAdapter()
    provider_adapters.ADAPTERS["groq"] = fake

    # D. History, actions, strategy and plan coherence -------------------------------------------
    def follow_up_history():
        first = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                "message": "What should I try for Reasoning?",
                                                "allow_remote": True, "provider": "groq",
                                                "provider_consent_recorded": True}).json()
        fake.reply = provider_shape(first["response"])
        client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                        "message": "What did you recommend before?",
                                        "allow_remote": True, "provider": "groq",
                                        "provider_consent_recorded": True})
        history = fake.last_payload["prior_turns"]
        roles = [row["role"] for row in history]
        passed = roles[:2] == ["learner", "assistant"] and first["request_id"] in json.dumps(history)
        return f"roles={roles} prior_reply_referenced={first['request_id'] in json.dumps(history)}", passed

    run("D1", "history_actions_plan", "a follow-up includes the prior validated assistant turn",
        "second question in the same session", "ordered learner/assistant turns containing the earlier reply",
        "backend/app/coach_routes.py::_validated_history", follow_up_history)

    def action_recorded_once():
        reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                "message": "What should I practise next"}).json()
        offered = next((action for action in reply["response"]["actions"] if action["id"] == "inspect_evidence"), None)
        if offered is None:
            return f"offered actions={[a['id'] for a in reply['response']['actions']]}", False
        body = {"session_id": seeded, "request_id": reply["request_id"], "action_id": "inspect_evidence",
                "target": offered["target"], "exercise_id": offered.get("exercise_id")}
        first = client.post("/api/coach/actions", json=body)
        second = client.post("/api/coach/actions", json=body)
        events = coaching_events("coach_action_selected")
        passed = (first.status_code == 200 and second.status_code == 200
                  and second.json().get("replayed") is True and events == 1)
        return f"first={first.status_code} second={second.status_code} " \
               f"replayed={second.json().get('replayed')} events={events}", passed

    run("D2", "history_actions_plan", "an approved action is recorded once and replayed exactly",
        "inspect_evidence chosen twice", "200 then a replayed 200 with a single saved action event",
        "backend/app/coach_routes.py::POST /api/coach/actions", action_recorded_once)

    def action_tampered():
        reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                "message": "What should I practise next"}).json()
        response = client.post("/api/coach/actions", json={
            "session_id": seeded, "request_id": reply["request_id"], "action_id": "inspect_evidence",
            "target": "https://example.invalid/steal"})
        return f"status={response.status_code} detail={response.text[:120]}", response.status_code == 409

    run("D3", "history_actions_plan", "a tampered action target is refused",
        "action target changed after the reply was saved", "409 before any navigation or event",
        "backend/app/coach_routes.py::POST /api/coach/actions", action_tampered)

    def unknown_request_action():
        response = client.post("/api/coach/actions", json={
            "session_id": seeded, "request_id": str(uuid.uuid4()), "action_id": "open_practice"})
        return f"status={response.status_code}", response.status_code in {404, 409}

    run("D4", "history_actions_plan", "an action for an unknown turn cannot be selected",
        "random request id", "4xx rejection", "backend/app/coach_routes.py::POST /api/coach/actions",
        unknown_request_action)

    def plan_tier_matches_launch():
        plan = client.post("/api/plans/next", json={"session_id": seeded, "budget_minutes": 30}).json()
        step = next(row for row in plan["steps"] if row["exercise_type_id"] == "EX-02")
        launch = client.post("/api/training/blocks", json={"session_id": seeded, "exercise_id": "EX-02"})
        passed = (launch.status_code == 201 and launch.json()["block"]["tier"] == step["launch_tier"]
                  and launch.json()["plan_alignment"]["matched"] is True)
        return f"plan_tier={step['launch_tier']} launch={launch.status_code} " \
               f"aligned={launch.json().get('plan_alignment')}", passed

    run("D5", "history_actions_plan", "the saved plan tier and the launched tier are the same authority",
        "plan then launch EX-02", "identical tier and matched alignment",
        "backend/app/plan_v2.py::authoritative_training_tier", plan_tier_matches_launch)

    def unsupported_tier_rejected():
        response = client.post("/api/training/blocks", json={
            "session_id": seeded, "exercise_id": "EX-02", "tier": "tier-3"})
        return f"status={response.status_code}", response.status_code in {409, 422}

    run("D6", "history_actions_plan", "a launch tier above the recorded decision is refused",
        "tier-3 requested while the policy says tier-1", "409 or 422, never a silent promotion",
        "backend/app/main.py::POST /api/training/blocks", unsupported_tier_rejected)

    # E. Retry, conflict, concurrency, restart and cancel -----------------------------------------
    replay_body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "Retry probe",
                   "request_id": str(uuid.uuid4())}

    def retry_replays():
        first = client.post("/api/coach", json=replay_body)
        second = client.post("/api/coach", json=replay_body)
        passed = (first.status_code == 200 and second.status_code == 200
                  and second.json().get("replayed") is True
                  and second.json()["request_id"] == first.json()["request_id"]
                  and coaching_events("coaching_message_sent", replay_body["request_id"]) == 1)
        return f"first={first.status_code} second={second.status_code} " \
               f"replayed={second.json().get('replayed')} events=" \
               f"{coaching_events('coaching_message_sent', replay_body['request_id'])}", passed

    run("E1", "retry_concurrency", "an exact retry replays the saved answer", "the same request id and payload twice",
        "one canonical answer and one saved event", "backend/app/storage.py::reserve_coach_turn", retry_replays)

    def conflicting_payload():
        response = client.post("/api/coach", json={**replay_body, "message": "Different question"})
        return f"status={response.status_code}", response.status_code == 409

    run("E2", "retry_concurrency", "a conflicting payload for a saved request is refused",
        "the same request id with a different message", "409 before side effects",
        "backend/app/storage.py::reserve_coach_turn", conflicting_payload)

    in_flight_body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "in progress",
                      "request_id": str(uuid.uuid4())}
    in_flight_request = coach_routes.CoachRequest(**in_flight_body)
    store.reserve_coach_turn({
        "request_id": in_flight_body["request_id"], "learner_id": "demo-user", "session_id": seeded,
        "subject_exercise_id": "EX-02", "subject_dimension": "reasoning", "subject_source": "explicit_selection",
        "provider_requested": "local", "coach_version": "coach-v2",
        "payload_hash": coach_routes._payload_hash(in_flight_request),
        "message": in_flight_body["message"], "request": in_flight_request.model_dump(),
    })

    def in_progress_conflict():
        response = client.post("/api/coach", json=in_flight_body)
        return f"status={response.status_code} detail={response.text[:120]}", response.status_code == 409

    run("E3", "retry_concurrency", "a reserved in-progress request blocks a duplicate",
        "duplicate while the first is still generating", "409 and no second canonical event",
        "backend/app/storage.py::reserve_coach_turn", in_progress_conflict)

    def concurrent_duplicate():
        body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "Concurrent probe",
                "request_id": str(uuid.uuid4())}
        results = []
        lock = threading.Lock()

        def call():
            with TestClient(app) as local:
                response = local.post("/api/coach", json=body)
            with lock:
                results.append(response.status_code)

        threads = [threading.Thread(target=call) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        events = coaching_events("coaching_message_sent", body["request_id"])
        passed = sorted(results) == [200, 409] and events == 1
        return f"statuses={sorted(results)} canonical_events={events}", passed

    run("E4", "retry_concurrency", "concurrent duplicates produce one canonical result",
        "two simultaneous identical requests", "one 200, one 409 and a single saved event",
        "backend/app/coach_routes.py::_reserve", concurrent_duplicate)

    def failed_turn_retryable():
        body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "Failure probe",
                "request_id": str(uuid.uuid4())}
        request = coach_routes.CoachRequest(**body)
        store.reserve_coach_turn({
            "request_id": body["request_id"], "learner_id": "demo-user", "session_id": seeded,
            "subject_exercise_id": "EX-02", "subject_dimension": "reasoning",
            "subject_source": "explicit_selection", "provider_requested": "local",
            "coach_version": "coach-v2", "payload_hash": coach_routes._payload_hash(request),
            "message": body["message"], "request": request.model_dump(),
        })
        store.fail_coach_turn(body["request_id"], "probe_failure")
        retried = client.post("/api/coach", json=body)
        events = coaching_events("coaching_message_sent", body["request_id"])
        passed = retried.status_code == 200 and retried.json()["request_id"] == body["request_id"] and events == 1
        return f"status={retried.status_code} canonical_events={events}", passed

    run("E5", "retry_concurrency", "a failed attempt can be retried and completes once",
        "a reserved turn marked failed, then retried", "200 with the same request id and one event",
        "backend/app/storage.py::fail_coach_turn", failed_turn_retryable)

    def stream_then_json():
        body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "Stream probe",
                "request_id": str(uuid.uuid4())}
        with client.stream("POST", "/api/coach/stream", json=body) as stream:
            stream_status = stream.status_code
            first_event = next(stream.iter_lines(), None)
        # The browser dropped the stream. Give the server thread a moment to finish or
        # abandon the reservation, then retry the exact same request id.
        page_gone = None
        for _ in range(20):
            with closing(store.connect()) as db:
                row = db.execute("SELECT status FROM coach_turns WHERE request_id=?",
                                 (body["request_id"],)).fetchone()
            page_gone = row["status"] if row else None
            if page_gone != "in_progress":
                break
            threading_event = 0.25
            import time as _time
            _time.sleep(threading_event)
        reclaimed = False
        if page_gone == "in_progress":
            with closing(store.connect()) as db:
                db.execute("UPDATE coach_turns SET updated_at=? WHERE request_id=?",
                           ("2020-01-01T00:00:00+00:00", body["request_id"]))
                db.commit()
            reclaimed = True
        retried = client.post("/api/coach", json=body)
        events = coaching_events("coaching_message_sent", body["request_id"])
        with closing(store.connect()) as db:
            lifecycle = dict(db.execute("SELECT generation,deleting FROM learner_lifecycle WHERE learner_id='demo-user'").fetchone() or {})
            turn_row = dict(db.execute("SELECT status,lifecycle_generation FROM coach_turns WHERE request_id=?",
                                       (body["request_id"],)).fetchone() or {})
        passed = (stream_status == 200 and first_event is not None
                  and retried.status_code == 200 and events == 1)
        return f"stream={stream_status} first_event={str(first_event)[:40]!r} status_when_retried={page_gone} " \
               f"stale_reclaim={reclaimed} json_retry={retried.status_code} " \
               f"detail={retried.text[:100]} canonical_events={events} lifecycle={lifecycle} turn={turn_row}", passed

    run("E6", "retry_concurrency", "an abandoned stream is reclaimed by its exact retry",
        "SSE stream closed early, then the same request id retried as JSON",
        "the retry is accepted and leaves exactly one canonical event",
        "backend/app/storage.py::reserve_coach_turn (stale in-progress reclaim)", stream_then_json)

    # F. Provider consent, availability, timeout, malformed output and status ---------------------
    def consent_required():
        reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                "message": "Use the hosted model", "allow_remote": True,
                                                "provider": "groq", "provider_consent_recorded": False}).json()
        passed = reply.get("provider_status") == "consent_required" and reply.get("provider_used") == "local"
        return f"provider_status={reply.get('provider_status')} provider_used={reply.get('provider_used')}", passed

    run("F1", "provider_states", "hosted generation needs recorded consent each time",
        "allow_remote with consent false", "consent_required and a local answer",
        "backend/app/coach_routes.py::_resolve_provider", consent_required)

    def provider_unavailable():
        without = FakeAdapter()
        without.configured = lambda: False  # type: ignore[method-assign]
        provider_adapters.ADAPTERS["groq"] = without
        try:
            reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                    "message": "Use the hosted model", "allow_remote": True,
                                                    "provider": "groq",
                                                    "provider_consent_recorded": True}).json()
        finally:
            provider_adapters.ADAPTERS["groq"] = fake
        passed = reply.get("provider_status") in {"not_configured", "unavailable"} and bool(reply.get("response"))
        return f"provider_status={reply.get('provider_status')} fallback_reason={reply.get('fallback_reason')}", passed

    run("F2", "provider_states", "an unconfigured provider still returns a labelled local answer",
        "provider not configured", "a fallback status with a complete local reply",
        "backend/app/coach_v2.py::reply_v2", provider_unavailable)

    def provider_timeout():
        timing = FakeAdapter(raises=TimeoutError("simulated provider timeout"))
        provider_adapters.ADAPTERS["groq"] = timing
        try:
            reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                    "message": "Use the hosted model", "allow_remote": True,
                                                    "provider": "groq",
                                                    "provider_consent_recorded": True}).json()
        finally:
            provider_adapters.ADAPTERS["groq"] = fake
        passed = reply.get("provider_status") == "timeout" and bool(reply.get("response"))
        return f"provider_status={reply.get('provider_status')} fallback_reason={reply.get('fallback_reason')}", passed

    run("F3", "provider_states", "a provider timeout is labelled and the local answer is returned",
        "the adapter raises TimeoutError", "provider_status=timeout with the canonical reply",
        "backend/app/coach_v2.py::reply_v2", provider_timeout)

    def provider_malformed():
        provider_adapters.ADAPTERS["groq"] = FakeAdapter(reply={})
        try:
            reply = client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-02",
                                                    "message": "Use the hosted model", "allow_remote": True,
                                                    "provider": "groq",
                                                    "provider_consent_recorded": True}).json()
        finally:
            provider_adapters.ADAPTERS["groq"] = fake
        answer = reply.get("response") or {}
        passed = reply.get("provider_status") != "validated" and answer.get("observation") is not None
        return f"provider_status={reply.get('provider_status')} " \
               f"fallback_reason={reply.get('fallback_reason')} observation_present={answer.get('observation') is not None}", passed

    run("F4", "provider_states", "malformed provider output is not presented as validated",
        "the adapter returns an empty object", "a non-validated status with the canonical reply",
        "backend/app/coach_v2.py::validate_generated", provider_malformed)

    def provider_status_endpoint():
        body = client.get("/api/coach/providers").json()
        text = json.dumps(body)
        leaks = [marker for marker in ("sk-", "AIza", "api_key=", "GROQ_API_KEY", "GEMINI_API_KEY") if marker in text]
        providers = body.get("providers") or {}
        passed = not leaks and {"groq", "gemini"} <= set(providers)
        return f"providers={sorted(providers)} leaks={leaks}", passed

    run("F5", "provider_states", "the provider status endpoint reports state without secrets",
        "GET /api/coach/providers", "both adapters described and no credential material",
        "backend/app/coach_routes.py::/api/coach/providers", provider_status_endpoint)

    # G. Quiet, speech, export and deletion ------------------------------------------------------
    client.post("/api/coach", json={"session_id": seeded, "subject_exercise_id": "EX-01",
                                    "message": "Export probe question"})

    def export_includes_new_tables():
        exported = client.get("/api/data/demo-user/export").json()
        sections = exported.get("export", exported)
        text = json.dumps(sections)
        passed = all(key in text for key in ("coach_turns", "coach_conversations"))
        return f"keys={sorted(sections)[:10] if isinstance(sections, dict) else type(sections).__name__}", passed

    run("G1", "quiet_speech_lifecycle", "export carries coaching and conversation records",
        "GET export after chats", "the new learner-owned tables appear in the export",
        "backend/app/lifecycle_service.py::export_learner_data", export_includes_new_tables)

    def speech_status():
        status = client.get("/api/companion/speech/status").json()
        passed = status.get("local_only") is True and status.get("engine") == "KittenTTS"
        return f"engine={status.get('engine')} local_only={status.get('local_only')} model={status.get('model')}", passed

    run("G2", "quiet_speech_lifecycle", "speech status is local-only and identifies the model",
        "GET /api/companion/speech/status", "KittenTTS with local_only true",
        "backend/app/speech_service.py", speech_status)

    def speech_limits():
        too_long = client.post("/api/companion/speech", json={"text": "x" * 4000, "voice": "Bella"})
        empty = client.post("/api/companion/speech", json={"text": "   ", "voice": "Bella"})
        passed = too_long.status_code in {400, 413, 422} and empty.status_code in {400, 422}
        return f"long={too_long.status_code} whitespace={empty.status_code}", passed

    run("G3", "quiet_speech_lifecycle", "speech input length and empty text are validated",
        "4000 characters and whitespace-only text", "both refused before synthesis",
        "backend/app/speech_service.py::speech", speech_limits)

    def deletion_invalidates_in_flight():
        store.create_session("r4-other-learner-session", "other-learner")
        with closing(store.connect()) as db:
            other_before = db.execute("SELECT COUNT(*) FROM sessions WHERE learner_id='other-learner'").fetchone()[0]
        body = {"session_id": seeded, "subject_exercise_id": "EX-02", "message": "delete probe",
                "request_id": str(uuid.uuid4())}
        request = coach_routes.CoachRequest(**body)
        store.reserve_coach_turn({
            "request_id": body["request_id"], "learner_id": "demo-user", "session_id": seeded,
            "subject_exercise_id": "EX-02", "subject_dimension": "reasoning",
            "subject_source": "explicit_selection", "provider_requested": "local",
            "coach_version": "coach-v2", "payload_hash": coach_routes._payload_hash(request),
            "message": body["message"], "request": request.model_dump(),
        })
        deleted = client.post("/api/data/demo-user/delete", json={"confirmation": "DELETE LOCAL DATA"})
        late = client.post("/api/coach", json=body)
        with closing(store.connect()) as db:
            other_after = db.execute("SELECT COUNT(*) FROM sessions WHERE learner_id='other-learner'").fetchone()[0]
        passed = (deleted.status_code == 200 and late.status_code in {404, 409}
                  and other_before == other_after == 1)
        return f"delete={deleted.status_code} late_reply={late.status_code} " \
               f"other_learner_sessions={other_before}->{other_after}", passed

    run("G4", "quiet_speech_lifecycle", "deletion invalidates an in-flight reply and keeps other learners",
        "delete the learner while a reply is reserved", "the late reply is refused and unrelated rows survive",
        "backend/app/lifecycle_service.py::delete_learner_data", deletion_invalidates_in_flight)

    def deletion_cleared_records():
        with closing(store.connect()) as db:
            counts = {
                "sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE learner_id='demo-user'").fetchone()[0],
                "turns": db.execute("SELECT COUNT(*) FROM coach_turns WHERE learner_id='demo-user'").fetchone()[0],
                "conversations": db.execute("SELECT COUNT(*) FROM coach_conversations WHERE learner_id='demo-user'").fetchone()[0],
            }
        passed = all(value == 0 for value in counts.values())
        return f"remaining={counts}", passed

    run("G5", "quiet_speech_lifecycle", "deletion clears the learner-owned coaching records",
        "after the delete request", "no sessions, turns or conversations remain for that learner",
        "backend/app/lifecycle_service.py::delete_learner_data", deletion_cleared_records)

provider_adapters.ADAPTERS.pop("groq", None)

passed = [case for case in CASES if case["verdict"] == "PASS"]
failed = [case for case in CASES if case["verdict"] == "FAIL"]
receipt = {
    "suite": "r4-forty-case-manifest",
    "case_count": len(CASES),
    "passed": len(passed),
    "failed": len(failed),
    "hosted_provider_traffic": False,
    "fixture": "disposable SQLite created under output/verification and deleted after the run",
    "groups": {group: len([case for case in CASES if case["group"] == group])
               for group in sorted({str(case["group"]) for case in CASES})},
    "cases": CASES,
}
target = ROOT / "output" / "verification" / "r4-forty-cases.json"
target.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
for case in CASES:
    print(f"{case['verdict']} {case['case_id']:>3} {case['name']}: {case['actual'][:150]}")
print(f"\n{len(passed)}/{len(CASES)} cases passed -> {target}")
fixture.unlink(missing_ok=True)
sys.exit(0 if not failed else 1)
