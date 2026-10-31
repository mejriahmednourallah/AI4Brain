"""Versioned, transparent personalization policy constants."""
POLICY_VERSION = "personalization-v1"
DIFFICULTY_POLICY_VERSION = "difficulty-v2"
PLAN_POLICY_VERSION = "training-plan-v1"
DIMENSION_TO_EXERCISE = {"working_memory":"EX-01","reasoning":"EX-02","attention_inhibition":"EX-03","flexibility":"EX-04","planning":"EX-05"}
EXERCISE_TO_DIMENSION = {v:k for k,v in DIMENSION_TO_EXERCISE.items()}
DISPLAY_NAMES = {"working_memory":"Working memory","reasoning":"Reasoning","attention_inhibition":"Attention and inhibition","flexibility":"Cognitive flexibility","planning":"Planning"}
WEIGHTS = {"performance_gap":.40,"user_goal_weight":.25,"practice_recency":.20,"uncertainty_need":.15}
BASELINE_REQUIRED = {"working_memory":6,"reasoning":6,"attention_inhibition":40,"flexibility":24,"planning":3}
DEFAULT_BUDGET_MINUTES = 12
MIN_PLAN_STEPS = 2
MAX_PLAN_STEPS = 4
