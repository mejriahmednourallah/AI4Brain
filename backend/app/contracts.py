from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"
EXERCISE_VERSION = "1.0.0"
LEGACY_TRAINING_EXERCISE_VERSION = "training-v1"
TRAINING_EXERCISE_VERSION = "training-v2"
SCORING_VERSION = "score-v1"
POLICY_VERSION = "recommendation-v1"

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Tile(StrictModel):
    shape: Literal["circle", "triangle", "square", "diamond", "arrow"]
    count: int = Field(default=1, ge=1, le=4)
    fill: Literal["outline", "solid"] = "outline"
    rotation: int = Field(default=0, ge=0, le=270)

class PatternChoice(StrictModel):
    choice_id: Literal["A", "B", "C", "D"]
    tile: Tile

class ExerciseItem(StrictModel):
    item_id: str
    prompt: str
    layout: Literal["2x2"] = "2x2"
    pattern: dict[Literal["top_left", "top_right", "bottom_left", "bottom_right"], Tile | None]
    choices: list[PatternChoice]
    difficulty: str
    category: Literal["visual_pattern"] = "visual_pattern"

class BatteryExerciseItem(StrictModel):
    item_id: str
    prompt: str = ""
    stimulus: dict[str, Any]

class ExerciseConfig(StrictModel):
    schema_version: str = SCHEMA_VERSION
    exercise_id: str = "EX-02"
    exercise_version: str = EXERCISE_VERSION
    phase: Literal["practice", "baseline", "training", "reassessment"]
    items: list[ExerciseItem | BatteryExerciseItem]
    instructions: str
    scoring: str | None = None
    difficulty_tier: str | None = None
    training_block_id: str | None = None
    challenge_seed: str | None = None
    # Canonical size of the tier-decision window, published for progress copy only.
    decision_trial_count: int | None = None

class SessionCreate(StrictModel):
    learner_id: str = "demo-user"
    consent_accepted: bool = False
    dashboard_mode: Literal["analytics", "rpg"] = "analytics"

class SessionRecord(StrictModel):
    id: str
    learner_id: str
    started_at: datetime
    status: Literal["active", "completed"]

class TrialSubmission(StrictModel):
    event_id: str
    session_id: str
    learner_id: str = "demo-user"
    phase: Literal["practice", "baseline", "training", "reassessment"]
    exercise_id: Literal["EX-01", "EX-02", "EX-03", "EX-04", "EX-05"] = "EX-02"
    exercise_version: str = EXERCISE_VERSION
    item_id: str
    choice: Literal["A", "B", "C", "D"] | None = None
    training_block_id: str | None = None
    response_time_ms: float | None = Field(default=None, ge=0)
    visibility_interrupted: bool = False
    hint_count: int = Field(default=0, ge=0)
    restart_count: int = Field(default=0, ge=0)
    # Replayed cue exposures. Recorded as assistance, never as unassisted evidence.
    replay_count: int = Field(default=0, ge=0)
    stimulus_onset_ms: float | None = Field(default=None, ge=0)
    response_data: dict[str, Any] | None = None

class TrainingBlockCreate(StrictModel):
    session_id: str
    exercise_id: Literal["EX-01", "EX-02", "EX-03", "EX-04", "EX-05"] = "EX-02"
    # Omitted for an explicit world choice: the server resolves the family's canonical
    # current tier. A supplied tier is validated against the recorded decision.
    tier: Literal["tier-1", "tier-2", "tier-3"] | None = None

class NextRecommendationRequest(StrictModel):
    session_id: str | None = None
    budget_minutes: int | None = Field(default=None, ge=4, le=60)
    goal_dimension: Literal["working_memory", "reasoning", "attention_inhibition", "flexibility", "planning"] | None = None
    # Omitted means "no availability constraint". An explicit list, including an empty one,
    # is a real constraint: an empty list must not be treated as "everything is available".
    available_dimensions: list[Literal["working_memory", "reasoning", "attention_inhibition",
                                       "flexibility", "planning"]] | None = None

class PlanNextRequest(NextRecommendationRequest):
    # Optional enrichment availability is independent of the five core-family constraint.
    # An explicit empty list excludes enrichment; omission allows eligible catalog entries.
    available_activities: list[Literal["HY-01", "HY-02", "HY-03", "HY-04", "HY-05", "HY-06", "CRYSTAL"]] | None = None

class TrialResult(StrictModel):
    event_id: str
    session_id: str
    item_id: str
    phase: str
    correct: bool | None
    error_type: str | None
    scoring_version: str
    visibility_interrupted: bool
    scored: bool
    replayed: bool = False
    difficulty_decision: dict[str, Any] | None = None
    valid_training_count: int | None = None

class ProfileSnapshot(StrictModel):
    id: str
    learner_id: str
    scoring_version: str
    dimension: str
    index_0_100: float | None
    uncertainty_status: str
    evidence_count: int
    completed: bool
    evidence_ids: list[str]
    interrupted_count: int
    created_at: datetime

class Recommendation(StrictModel):
    id: str
    learner_id: str
    action: Literal["complete_baseline", "additional_assessment", "targeted_training", "reasoning_training",
                    "no_available_activity"]
    exercise_id: str | None = None
    tier: str | None = None
    reason_codes: list[str]
    evidence_ids: list[str]
    policy_version: str
    created_at: datetime
    dimension: str | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    selected_strategy_id: str | None = None
    budget_minutes: int = 0
    availability: dict[str, Any] | None = None


class PreferenceUpdate(StrictModel):
    session_id: str
    dashboard_mode: Literal["analytics", "rpg"]
    goal_dimension: Literal["working_memory", "reasoning", "attention_inhibition", "flexibility", "planning"] | None = None
