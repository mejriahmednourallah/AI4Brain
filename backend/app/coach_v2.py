"""coach-v2: evidence-grounded coaching bound to a resolved subject family.

Differences from ``coach-v1`` (kept readable for stored history):

* the answer is about the family the learner asked about, not only the family the
  policy recommends next;
* the factual ``observation`` is rendered by the backend from canonical evidence;
* the explanation may be generated, but every identifier, number, strategy and
  action is validated against backend-supplied values afterwards;
* the next-step recommendation is reported separately from the subject answer.

A passing schema check never proves the prose is right, so relevance is reviewed
separately from structure.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .twin_context import FAMILIES, CAVEAT, provider_payload, subject_family

COACH_VERSION = "coach-v2"
MAX_ANSWER_WORDS = 220
MAX_SPOKEN_SUMMARY_CHARS = 120
SPOKEN_SUMMARY_FALLBACK = "Please review the written reply for details."
SPOKEN_SUMMARY_CLARIFICATION = (
    "Which task family should I summarize: Memory, Reasoning, Attention, Flexibility, or Planning?"
)
NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
PERCENT_CLAIM = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
OUT_OF_HUNDRED = re.compile(r"\b(\d+(?:\.\d+)?)\s+out\s+of\s+100\b", re.IGNORECASE)
ASSISTANCE_CLAIM = re.compile(r"\b(?:hint|hints|assisted|assistance|coached|helped\s+you\s+answer)\b", re.IGNORECASE)
# Certainty prose is only allowed when the recorded uncertainty status is settled.
CERTAINTY_CLAIM = re.compile(r"\b(?:certain|certainly|definitive|definitively|guaranteed|proves?|proven|reliable|reliably|confident)\b", re.IGNORECASE)
# Measured facts are server-authored. Generated prose may not restate them in any form:
# digits, spelled-out numbers, or a noun-plus-value construction all count as a fact claim.
SPELLED_NUMBER = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
    r"ninety|hundred|thousand|dozen|twice|thrice)\b", re.IGNORECASE)
FACTUAL_ASSERTION = re.compile(
    r"\b(?:index|score|scores|percentage|percent|accuracy|results?|correct\s+positions?|error\s+rate)\b"
    r"[^.]{0,40}\b(?:is|are|was|were|equals?|of|at|reached|stands?|shows?|recorded)\b", re.IGNORECASE)
# A statement that the learner has a condition, not a mention of what this is not.
CLINICAL_ASSERTION = re.compile(
    r"\b(?:you(?:'ve| have| meet| meets| show| shows| suffer)|your (?:diagnosis|condition)|this (?:proves|shows) you)\b"
    r"[^.]{0,90}\b(?:diagnos\w*|disorder|adhd|autis\w*|depress\w*|anxiety|clinical|medical condition|prescri\w*|iq)\b",
    re.IGNORECASE)

ACTION_DEFINITIONS = {
    "try_strategy": "Try this strategy",
    "open_practice": "Open practice",
    "inspect_evidence": "Inspect evidence",
    "change_focus": "Change focus",
}


class CoachV2Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observation: str = Field(max_length=1200)
    explanation: str = Field(max_length=1500)
    strategy_id: str | None
    follow_up: str = Field(max_length=400)
    next_step_note: str = Field(max_length=600)
    evidence_ids: list[str]
    recommended_exercise_id: str | None
    recommended_difficulty: str | None
    clarification: str | None


def _number_set(value: Any) -> set[str]:
    return set(NUMBER.findall(json.dumps(value, default=str)))


def _percent(value: Any) -> str:
    if value is None:
        return "not yet measured"
    return f"{value}"


def factual_observation(family: dict[str, Any] | None, label: str) -> str:
    if family is None:
        return f"I could not identify which task family you mean, so nothing here is a measured observation about a specific family."
    if not family["completed"]:
        return (f"{label} is unassessed: no complete uncoached baseline is saved yet, so I will not describe an index "
                f"or a weakness. {family['evidence_count']} of {family['required_evidence_count']} required trials are recorded.")
    return (f"Your most recent {label} baseline recorded {_percent(family['index_0_100'])} out of 100 from "
            f"{family['evidence_count']} saved baseline trials, and its uncertainty status is {family['uncertainty_status']}.")


def grounded_spoken_summary(context: dict[str, Any], subject: dict[str, Any]) -> str:
    """Make a brief spoken sentence only from the resolved canonical subject profile."""
    revision = context.get("evidence_revision")
    if not isinstance(revision, str) or not revision:
        return SPOKEN_SUMMARY_FALLBACK
    if subject.get("source") in {"ambiguous", "unresolved"}:
        return SPOKEN_SUMMARY_CLARIFICATION

    exercise_id = subject.get("exercise_id")
    family = subject_family(context, subject)
    config = FAMILIES.get(exercise_id or "")
    if not family or not config or family.get("exercise_id") != exercise_id:
        return SPOKEN_SUMMARY_FALLBACK
    label = config["label"]
    status = str(family.get("uncertainty_status") or "").upper()
    if not family.get("completed") or "INCOMPLETE" in status or "NOT_ASSESSED" in status:
        summary = f"{label} is unassessed; no baseline index is available."
    else:
        value = family.get("index_0_100")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= value <= 100:
            summary = f"{label} baseline is recorded, but no index is available."
        else:
            # Scoring stores indices at two decimals; preserve that exact value.
            score = f"{float(value):g}"
            if "HIGH_UNCERTAINTY" in status:
                uncertainty = "with high uncertainty."
            elif "LOW_UNCERTAINTY" in status:
                uncertainty = "with low uncertainty."
            elif "CONFIRMED" in status:
                uncertainty = "with a confirmed uncertainty status."
            elif "STABLE" in status:
                uncertainty = "with a stable uncertainty status."
            else:
                uncertainty = "with an unclassified uncertainty status."
            summary = f"Your {label} baseline index is {score} out of 100, {uncertainty}"

    return summary if len(summary) <= MAX_SPOKEN_SUMMARY_CHARS else SPOKEN_SUMMARY_FALLBACK


def _memory_detail(family: dict[str, Any]) -> str:
    error = family["error_summary"]
    correct, total = error.get("correct_positions"), error.get("total_positions")
    if correct is None or total is None:
        return "The saved Memory trials do not carry a position breakdown."
    span = error.get("longest_fully_correct_span")
    detail = f"You recalled {correct} of {total} presented positions correctly"
    if span is not None:
        detail += f", and the longest sequence you reproduced in full order was {span}"
    detail += (" positions. The saved responses show order being lost between the cue and your answer; they do not "
               "establish why that happened.") if (correct < total) else " positions. That is a complete recall in this sample."
    return detail


def _attention_detail(family: dict[str, Any]) -> str:
    error = family["error_summary"]
    hits, omissions = error.get("go_hits"), error.get("go_omissions")
    rejections, commissions = error.get("no_go_correct_rejections"), error.get("no_go_commissions")
    parts = []
    if hits is not None and omissions is not None:
        parts.append(f"you responded to {hits} go signals and missed {omissions}")
    if rejections is not None and commissions is not None:
        parts.append(f"you correctly withheld on {rejections} no-go signals and responded to {commissions} of them")
    if not parts:
        return "The saved Attention trials do not carry a signal breakdown."
    detail = ("The saved responses show " + "; ".join(parts) + ".")
    if (commissions or 0) > 0 and (commissions or 0) >= (omissions or 0):
        detail += " Errors concentrate on withholding rather than missing the signal."
    elif (omissions or 0) > 0:
        detail += " Errors concentrate on missing the signal rather than withholding when you should."
    return detail


def _flexibility_detail(family: dict[str, Any]) -> str:
    error = family["error_summary"]
    switch_correct, switch_trials = error.get("switch_correct"), error.get("switch_trials")
    repeat_correct, repeat_trials = error.get("repeat_correct"), error.get("repeat_trials")
    if switch_correct is None or repeat_correct is None:
        return "The saved Flexibility trials do not carry a switch/repeat breakdown."
    detail = (f"You were correct on {switch_correct} of {switch_trials} rule-switch trials and {repeat_correct} of "
              f"{repeat_trials} repeat trials.")
    previous = error.get("error_previous_rule") or 0
    if previous:
        detail += f" {previous} of the switch errors matched the previous rule."
    return detail


def _planning_detail(family: dict[str, Any]) -> str:
    error = family["error_summary"]
    completed, excess = error.get("completed_puzzles"), error.get("excess_moves")
    if completed is None:
        return "The saved Planning puzzles do not carry a route breakdown."
    detail = f"You completed {completed} of 3 puzzles"
    if excess is not None:
        detail += f" with {excess} excess legal moves beyond the shortest route in total"
    if error.get("illegal_moves"):
        detail += f", and {error['illegal_moves']} attempted moves were blocked by a wall or edge"
    return detail + "."


def _reasoning_detail(family: dict[str, Any]) -> str:
    error = family["error_summary"]
    correct, count = error.get("correct"), error.get("evidence_count")
    if correct is None:
        return "The saved Reasoning trials do not carry a correct-response count."
    return f"You answered {correct} of the {count} saved baseline matrices correctly."


DETAIL = {
    "EX-01": _memory_detail,
    "EX-02": _reasoning_detail,
    "EX-03": _attention_detail,
    "EX-04": _flexibility_detail,
    "EX-05": _planning_detail,
}
DEFAULT_STRATEGY_TEXT = {
    "EX-01": ("Chunk the sequence into two or three short groups and rehearse the groups in order before answering.",
              "memory-chunk-sequence"),
    "EX-02": ("Compare candidate rules against one contrasting example and check the same change in both rows.",
              "reasoning-contrast-example"),
    "EX-03": ("Keep the go target in view and rehearse the withholding cue before each timed block.",
              "attention-target-reminder"),
    "EX-04": ("Name the active rule aloud at each transition before comparing the options.",
              "switch-transition-cue"),
    "EX-05": ("Break the route into subgoals and compare the next move against the shortest remaining path.",
              "planning-subgoals"),
}


def strategy_for_subject(context: dict[str, Any], exercise_id: str | None) -> dict[str, Any] | None:
    if not exercise_id:
        return None
    for row in context["suggested"]:
        if row.get("exercise_id") == exercise_id:
            return {"id": row.get("id"), "title": row.get("title"), "guidance": row.get("guidance"),
                    "source": row.get("source", "recorded_server_evaluation"),
                    "evidence_ids": row.get("source_evidence_ids", [])}
    guidance, strategy_id = DEFAULT_STRATEGY_TEXT.get(exercise_id, (None, None))
    if not guidance:
        return None
    return {"id": strategy_id, "title": guidance.split(",")[0].strip(), "guidance": guidance,
            "source": "general_practice_suggestion", "evidence_ids": []}


def allowed_actions(context: dict[str, Any], subject: dict[str, Any]) -> list[dict[str, Any]]:
    family = subject_family(context, subject)
    actions: list[dict[str, Any]] = []
    strategy = strategy_for_subject(context, subject.get("exercise_id"))
    if family and family["completed"]:
        actions.append({"id": "inspect_evidence", "kind": "navigate", "label": ACTION_DEFINITIONS["inspect_evidence"],
                        "target": "/evidence", "exercise_id": subject.get("exercise_id")})
    if strategy:
        actions.append({"id": "try_strategy", "kind": "assistance", "label": ACTION_DEFINITIONS["try_strategy"],
                        "strategy_id": strategy["id"], "exercise_id": subject.get("exercise_id")})
    if family:
        actions.append({"id": "open_practice", "kind": "navigate", "label": ACTION_DEFINITIONS["open_practice"],
                        "target": f"/practice?family={subject.get('dimension')}",
                        "exercise_id": subject.get("exercise_id")})
    actions.append({"id": "change_focus", "kind": "navigate", "label": ACTION_DEFINITIONS["change_focus"],
                    "target": "/plan", "exercise_id": context["next_step"].get("exercise_id")})
    return actions


def _next_step_note(context: dict[str, Any], subject: dict[str, Any]) -> str:
    step = context["next_step"]
    label = FAMILIES.get(step.get("exercise_id") or "", {}).get("label", "the next activity")
    reasons = ", ".join(step.get("reason_codes") or []) or "the recorded selection policy"
    if step.get("exercise_id") == subject.get("exercise_id"):
        return f"Separately, the policy also points at {label} for your next block because of {reasons}."
    return (f"Separately, the policy's next recommendation is {label}, because of {reasons}. That is a scheduling "
            f"decision about what to do next, not part of the {FAMILIES.get(subject.get('exercise_id') or '', {}).get('label', 'task')} result above.")


def grounded_reply(context: dict[str, Any], subject: dict[str, Any], message: str) -> dict[str, Any]:
    """Deterministic, evidence-bound answer used locally and as the fallback."""
    label = FAMILIES.get(subject.get("exercise_id") or "", {}).get("label")
    family = subject_family(context, subject)
    asked = message.casefold()
    if subject.get("source") == "ambiguous" or subject.get("source") == "unresolved":
        clarification = subject.get("clarification") or "Which task family should I look at?"
        return {
            "observation": "I have not picked a family for this question yet, so I will not describe evidence that may be about the wrong task.",
            "explanation": clarification,
            "strategy_id": None, "strategy_title": None, "strategy_guidance": None,
            "follow_up": clarification,
            "caveat": CAVEAT,
            "evidence_ids": [],
            "recommended_exercise_id": context["next_step"].get("exercise_id"),
            "recommended_difficulty": context["next_step"].get("tier"),
            "next_step_note": _next_step_note(context, subject),
            "clarification": clarification,
            "actions": allowed_actions(context, subject),
        }

    observation = factual_observation(family, label or "This family")
    explanation_parts: list[str] = []
    if family and family["completed"]:
        explanation_parts.append(DETAIL[subject["exercise_id"]](family))
    elif family:
        explanation_parts.append(f"No {label} index exists yet, and I will not infer one from an incomplete or "
                                 f"interrupted baseline.")
    if any(word in asked for word in ("why", "recommend", "select", "priority", "plan")):
        explanation_parts.append("Activity selection combines the task-specific performance gap, your stated goal, "
                                 "practice recency and evidence uncertainty, with periodic exploration of a "
                                 "least-recently-practised family.")
    if any(word in asked for word in ("uncertain", "diagnos", "iq", "clinical", "reliable")):
        explanation_parts.append(CAVEAT)
    strategy = strategy_for_subject(context, subject.get("exercise_id"))
    if strategy:
        explanation_parts.append(f"One recorded option is: {strategy['guidance']}")
    if not explanation_parts:
        explanation_parts.append("Ask about a saved result, a strategy, or the next recommendation and I will answer from the recorded evidence.")

    follow_up = next((text for text in (
        f"Would you like me to explain which part of the {label} evidence to inspect first?",
        "Would you like me to clarify how that compares with a different family?",
        "Should we check the saved evidence together before you choose a practice block?",
    ) if text), "What would you like to clarify?")
    evidence_ids = list(family["evidence_ids"]) if family else []
    rationale_bits = [f"This answer cites {len(evidence_ids)} saved {label or 'task'} records and the recorded "
                      f"uncertainty status for that family."]
    if strategy:
        rationale_bits.append(f"The strategy is the recorded server-selected option for this family, not a generated claim.")
    rationale_bits.append("No index, tier or eligibility was changed by this conversation.")
    return {
        "observation": observation,
        "explanation": " ".join(explanation_parts),
        "rationale": " ".join(rationale_bits),
        "strategy_id": strategy["id"] if strategy else None,
        "strategy_title": strategy["title"] if strategy else None,
        "strategy_guidance": strategy["guidance"] if strategy else None,
        "follow_up": follow_up,
        "caveat": CAVEAT,
        "evidence_ids": evidence_ids,
        "recommended_exercise_id": context["next_step"].get("exercise_id"),
        "recommended_difficulty": context["next_step"].get("tier"),
        "next_step_note": _next_step_note(context, subject),
        "clarification": None,
        "actions": allowed_actions(context, subject),
    }


def validate_generated(raw: dict[str, Any], baseline: dict[str, Any], context: dict[str, Any],
                       subject: dict[str, Any]) -> CoachV2Output:
    """Reject provider claims that are not bound to the canonical subject fields."""
    output = CoachV2Output.model_validate(raw)
    allowed_evidence = {str(value) for value in baseline["evidence_ids"]} | {
        str(attempt["evidence_id"]) for attempt in context["observed"]["attempts"] if attempt.get("evidence_id")}
    unknown = [value for value in output.evidence_ids if value not in allowed_evidence]
    if unknown:
        raise ValueError("Provider cited evidence that is not in the supplied context")
    canonical_exercise = context["next_step"].get("exercise_id")
    if output.recommended_exercise_id not in {None, canonical_exercise}:
        raise ValueError("Provider recommended a different task family than the server policy")
    canonical_tier = context["next_step"].get("tier")
    allowed_tiers = {None}
    if canonical_tier:
        allowed_tiers.add(canonical_tier)
    if canonical_tier is None and context["next_step"].get("action") in {"complete_baseline", "additional_assessment"}:
        allowed_tiers.add("baseline")
    if output.recommended_difficulty not in allowed_tiers:
        raise ValueError("Provider recommended a different difficulty tier than the server policy")
    strategy = strategy_for_subject(context, subject.get("exercise_id"))
    if output.strategy_id not in {None, strategy["id"] if strategy else None}:
        raise ValueError("Provider invented a strategy")
    family = subject_family(context, subject)
    generated_prose = " ".join((output.explanation, output.follow_up, output.clarification or ""))
    # Facts are rendered by the backend from canonical fields. Provider prose may explain and
    # advise, but it may not restate a measurement: digits, spelled-out numbers and
    # noun-plus-value constructions are all rejected so paraphrase cannot bypass the boundary.
    if NUMBER.search(generated_prose):
        raise ValueError("Provider restated a measured value; facts are server-authored")
    spelled = SPELLED_NUMBER.findall(generated_prose)
    if spelled:
        raise ValueError(f"Provider spelled out a value instead of leaving facts to the server: {spelled[:3]}")
    assertion = FACTUAL_ASSERTION.search(generated_prose)
    if assertion:
        raise ValueError(f"Provider made a factual assertion the server must author: {assertion.group(0)[:60]!r}")
    if not context.get("assisted_training") and ASSISTANCE_CLAIM.search(generated_prose):
        raise ValueError("Provider made an assistance claim without a recorded assisted-training context")
    uncertainty = (family or {}).get("uncertainty_status")
    prose = " ".join((output.explanation, output.follow_up, output.clarification or "")).casefold()
    if uncertainty and "high_uncertainty" in uncertainty.casefold():
        if re.search(r"\b(?:low|no)\s+uncertainty\b|\b(?:certain|reliable|definitive)\b", prose):
            raise ValueError("Provider contradicted the canonical uncertainty status")
    if CERTAINTY_CLAIM.search(prose):
        settled = bool(uncertainty) and uncertainty.casefold() in {"confirmed", "low_uncertainty", "stable"}
        if not settled:
            raise ValueError("Provider asserted certainty the recorded uncertainty status does not support")
    if CLINICAL_ASSERTION.search(prose):
        raise ValueError("Provider made a clinical or diagnostic assertion about the learner")
    if family and not family.get("completed") and re.search(
            r"\b(?:score|index|percent|percentage|improved|declined)\b", prose):
        raise ValueError("Provider described an unassessed family as measured")
    if len((output.explanation or "").split()) > MAX_ANSWER_WORDS:
        raise ValueError("Provider answer exceeded the bounded length")
    return output


def reply_v2(context: dict[str, Any], subject: dict[str, Any], message: str, *,
             allow_remote: bool = False, provider: str = "local",
             transport: httpx.BaseTransport | None = None, adapters: Any = None) -> dict[str, Any]:
    baseline = grounded_reply(context, subject, message)
    result: dict[str, Any] = {
        "coach_version": COACH_VERSION,
        "source": "local_fallback",
        "provider_status": "local_only",
        "provider_requested": provider,
        "provider_used": "local",
        "model": None,
        "fallback_reason": None,
        "evidence_revision": context["evidence_revision"],
        "spoken_summary": grounded_spoken_summary(context, subject),
        "subject": {"exercise_id": subject.get("exercise_id"), "dimension": subject.get("dimension"),
                    "label": FAMILIES.get(subject.get("exercise_id") or "", {}).get("label"),
                    "resolved_from": subject.get("source")},
        "response": dict(baseline),
    }
    if not allow_remote:
        return result
    if adapters is None:  # pragma: no cover - import guarded so local use never needs the adapters
        from .provider_adapters import ADAPTERS
        adapters = ADAPTERS
    adapter = adapters.get(provider)
    if adapter is None:
        result["provider_status"] = "unknown_provider"
        result["fallback_reason"] = "unknown_provider"
        result["provider_used"] = "local"
        return result
    if not adapter.configured():
        result["provider_status"] = "not_configured"
        result["fallback_reason"] = "credentials_missing"
        return result
    try:
        generated = adapter.complete(provider_payload(context, subject), message, baseline, transport=transport)
        validated = validate_generated(generated, baseline, context, subject)
        merged = {**baseline, **validated.model_dump()}
        # The recorded-evidence summary is always rendered by the backend from canonical data.
        merged["observation"] = baseline["observation"]
        merged["evidence_ids"] = list(baseline["evidence_ids"])
        merged["caveat"] = baseline["caveat"]
        merged["actions"] = baseline["actions"]
        merged["strategy_id"] = baseline.get("strategy_id")
        merged["strategy_title"] = baseline.get("strategy_title")
        merged["strategy_guidance"] = baseline.get("strategy_guidance")
        merged["recommended_exercise_id"] = baseline.get("recommended_exercise_id")
        merged["recommended_difficulty"] = baseline.get("recommended_difficulty")
        merged["next_step_note"] = baseline.get("next_step_note")
        merged["clarification"] = baseline.get("clarification")
        result.update(source="configured_provider", provider_status="validated",
                      provider_used=adapter.name, model=adapter.model,
                      response={**merged, "generated_explanation": True})
    except ValueError as caught:
        result["provider_status"] = "unavailable_or_invalid"
        result["fallback_reason"] = "invalid_output"
        result["review_note"] = str(caught)[:200]
    except (TimeoutError, httpx.TimeoutException):
        result["provider_status"] = "timeout"
        result["fallback_reason"] = "provider_timeout"
    except httpx.HTTPError:
        result["provider_status"] = "unavailable_or_invalid"
        result["fallback_reason"] = "provider_unavailable"
    return result


def provider_statuses(adapters: Any = None) -> dict[str, Any]:
    if adapters is None:  # pragma: no cover
        from .provider_adapters import ADAPTERS
        adapters = ADAPTERS
    return {name: {"configured": adapter.configured(), "model": adapter.model,
                   "default_model": adapter.default_model}
            for name, adapter in adapters.items()}
