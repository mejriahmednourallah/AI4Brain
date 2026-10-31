"""Canonical hybrid-v1 contracts.

Hybrid activities are additive, versioned activities. They never contribute to the
five fixed EX baseline indices, and their payloads never pass through an EX scorer.
Every hybrid record carries the shared hybrid-v1 fields so a reviewer can reproduce
an attempt from its stored configuration, seed and ordered actions.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

HYBRID_SCHEMA_VERSION = "hybrid-v1"
HYBRID_EVALUATION_VERSION = "hybrid-eval-v1"

ActivityId = Literal["HY-01", "HY-02", "HY-03", "HY-04", "HY-05", "HY-06"]
ActivityMode = Literal["tutorial", "training", "challenge"]
ActionType = Literal["move", "deliver", "select", "commit", "respond", "switch", "advise"]

# Assistance windows are canonical per activity (user-approved policy, 20 October 2026).
ASSISTANCE_WINDOWS: dict[str, tuple[str, ...]] = {
    "HY-01": ("pre_play", "safe_checkpoint", "post_completion"),
    "HY-02": ("pre_block", "post_window"),
    "HY-03": ("pre_play", "boundary"),
    "HY-04": ("pre_wave", "between_waves"),
    "HY-05": ("pre_encoding", "post_commit"),
    "HY-06": ("advice_checkpoint", "post_commit"),
}

# Exposures that reveal otherwise hidden task information count as assistance.
ASSISTANCE_EXPOSURES: tuple[str, ...] = (
    "intention_reminder",
    "cue_replay",
    "clue_reveal",
    "solution_hint",
    "oracle_route_suggestion",
    "hidden_information_replay",
    "strategy_prompt",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HybridAttemptStart(StrictModel):
    event_id: str
    session_id: str
    learner_id: str = "demo-user"
    activity_id: ActivityId
    activity_version: str
    mode: ActivityMode = "training"
    config_version: str = "1"
    # Reproducibility: an omitted seed is generated once and stored with the attempt.
    seed: str | None = None
    difficulty_tier: str = "tier-1"


class HybridAttemptStartResult(StrictModel):
    attempt_id: str
    event_id: str
    session_id: str
    learner_id: str
    activity_id: str
    activity_version: str
    mode: str
    config_version: str
    seed: str
    difficulty_tier: str
    hybrid_schema_version: str = HYBRID_SCHEMA_VERSION
    config: dict[str, Any]
    assistance: dict[str, Any]
    created_at: str


class HybridActionRecord(StrictModel):
    event_id: str
    attempt_id: str
    sequence: int = Field(ge=1)
    action_type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: float | None = Field(default=None, ge=0)
    # Identity of the visible cue the action answered, when the mechanic has cues.
    cue_event_id: str | None = None
    visibility_interrupted: bool = False


class HybridAssistanceRecord(StrictModel):
    event_id: str
    attempt_id: str
    exposure_kind: str
    checkpoint: str
    checkpoint_version: str = "1"
    # Event that exposed the help (a recorded clue, replay or advice card id).
    source_event_id: str | None = None


class HybridCompletionRecord(StrictModel):
    event_id: str
    attempt_id: str
    interrupted: bool = False
    visibility_interrupted: bool = False
    response_time_ms: float | None = Field(default=None, ge=0)
    note: str | None = None


class HybridOutcome(StrictModel):
    attempt_id: str
    session_id: str
    learner_id: str
    activity_id: str
    activity_version: str
    evaluation_version: str = HYBRID_EVALUATION_VERSION
    completion_state: str
    assisted: bool
    excluded_from_unassisted: bool
    outcomes: dict[str, Any]
    evidence_ids: list[str]
    limitations: list[str]
    created_at: str
