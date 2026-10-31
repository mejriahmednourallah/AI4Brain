from __future__ import annotations

from .contracts import SCORING_VERSION
from .exercises import BASELINE_ITEM_IDS


def score_reasoning(events: list[dict]) -> dict:
    """Score only the latest baseline session; coached/interrupted attempts never count."""
    baseline = [e for e in events if e["payload"].get("phase") == "baseline" and e["payload"].get("exercise_id") == "EX-02"]
    if not baseline:
        session_events = []
    else:
        latest_session = max(baseline, key=lambda e: (e.get("session_started_at", ""), e.get("created_at", "")))["session_id"]
        session_events = [e for e in baseline if e["session_id"] == latest_session]
    interrupted = [e for e in session_events if e["payload"].get("interaction", {}).get("visibility_interrupted", False)]
    valid_by_item: dict[str, dict] = {}
    for event in session_events:
        payload = event["payload"]
        interaction = payload.get("interaction", {})
        if interaction.get("visibility_interrupted", False) or interaction.get("hint_count", 0) > 0:
            continue
        item_id = payload.get("item_id")
        if item_id in BASELINE_ITEM_IDS and item_id not in valid_by_item:
            valid_by_item[item_id] = event
    evidence = [valid_by_item[item_id] for item_id in BASELINE_ITEM_IDS if item_id in valid_by_item]
    complete = len(evidence) == len(BASELINE_ITEM_IDS)
    correct = sum(bool(e["payload"]["evaluation"]["correct"]) for e in evidence)
    return {
        "scoring_version": SCORING_VERSION,
        "dimension": "reasoning",
        "index_0_100": round(100 * correct / 6, 2) if complete else None,
        "correct": correct if complete else None,
        "evidence_count": len(evidence),
        "completed": complete,
        "uncertainty_status": "PRELIMINARY_HIGH_UNCERTAINTY" if complete else "INCOMPLETE_BASELINE",
        "evidence_ids": [e["event_id"] for e in evidence],
        "interrupted_count": len(interrupted),
        "assessment_session_id": session_events[0]["session_id"] if session_events else None,
        "response_times_ms": [e["payload"]["timing"]["response_time_ms"] for e in evidence if e["payload"]["timing"].get("response_time_ms") is not None],
    }
