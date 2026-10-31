"""Groq and Gemini adapters behind one provider interface.

Both providers expose an OpenAI-compatible ``/chat/completions`` route, so the
transport shape is shared while credentials, base URLs, model defaults and
configuration checks stay adapter-specific. Credentials are read server-side and
are never returned to a client or written to an event.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

CONNECT_TIMEOUT_SECONDS = 3.0
TOTAL_TIMEOUT_SECONDS = 8.0
MAX_COMPLETION_TOKENS = 900

SYSTEM_PROMPT = (
    "You are the AI4BRAIN practice coach. You may explain only the evidence supplied in the "
    "context: saved task results, recorded error counts, strategies and the next recommendation. "
    "Never invent a score, evidence id, task family, strategy, difficulty or improvement. Never "
    "diagnose, infer IQ, or claim scientific certainty. Distinguish measured results from what the "
    "learner reports. Answer the learner's question about the resolved subject family first, and "
    "refer to the next recommendation separately as a scheduling suggestion. Return the required "
    "JSON object only. The server writes all factual measurements into the observation block. "
    "In explanation, follow_up and clarification, do not repeat any measured value, quantity, "
    "score, index, percentage, correct-position count or difficulty label. Use no digits or "
    "spelled-out numbers (including one, first, second) in those prose fields. Avoid measurement "
    "assertions such as 'your score is' or 'your results are'. Explain the recorded strategy "
    "qualitatively instead. Do not claim hints or assistance unless assisted_training is true. "
    "Use only the supplied allowed identifiers in structured ID fields, or null; never invent them. "
    "For this explanation-only integration, set strategy_id, recommended_exercise_id, "
    "recommended_difficulty and clarification to null, evidence_ids to an empty array, "
    "and observation and next_step_note to empty strings: the server fills those fields itself. "
    "Keep the explanation under 100 words and the follow-up to a short question."
)

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "observation": {"type": "string"},
        "explanation": {"type": "string"},
        "strategy_id": {"type": ["string", "null"]},
        "follow_up": {"type": "string"},
        "next_step_note": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "recommended_exercise_id": {"type": ["string", "null"]},
        "recommended_difficulty": {"type": ["string", "null"]},
        "clarification": {"type": ["string", "null"]},
    },
    "required": ["observation", "explanation", "strategy_id", "follow_up", "next_step_note",
                 "evidence_ids", "recommended_exercise_id", "recommended_difficulty", "clarification"],
    "additionalProperties": False,
}


class ProviderAdapter:
    """Shared OpenAI-compatible chat implementation."""

    name = "provider"
    default_base_url = ""
    default_model = ""
    key_variable = ""
    model_variable = ""
    base_variable = ""
    supports_json_schema = True

    @property
    def model(self) -> str:
        return (os.getenv(self.model_variable) or self.default_model).strip()

    @property
    def base_url(self) -> str:
        return (os.getenv(self.base_variable) or self.default_base_url).rstrip("/")

    @property
    def api_key(self) -> str:
        return (os.getenv(self.key_variable) or "").strip()

    def configured(self) -> bool:
        return bool(self.api_key)

    def request_body(self, payload: dict[str, Any], message: str, baseline: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": 0.2,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({
                    "question": message[:2000],
                    "context": payload,
                    "backend_factual_summary": baseline.get("observation"),
                    "allowed_strategy_id": baseline.get("strategy_id"),
                    "allowed_evidence_ids": baseline.get("evidence_ids"),
                    "allowed_recommended_exercise_id": baseline.get("recommended_exercise_id"),
                    "allowed_recommended_difficulty": baseline.get("recommended_difficulty"),
                }, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "ai4brain_coach_v2", "strict": True, "schema": OUTPUT_SCHEMA}},
        }

    def complete(self, payload: dict[str, Any], message: str, baseline: dict[str, Any], *,
                 transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
        # A deployment may allow slower hosted inference while retaining a
        # bounded deadline and the same evidence validation/fallback policy.
        configured_timeout = float(os.getenv('AI4BRAIN_PROVIDER_TIMEOUT_SECONDS', str(TOTAL_TIMEOUT_SECONDS)))
        # This value cannot override the product's hard eight-second ceiling.
        bounded_total = min(TOTAL_TIMEOUT_SECONDS, max(3.0, configured_timeout))
        timeout = httpx.Timeout(bounded_total, connect=min(CONNECT_TIMEOUT_SECONDS, bounded_total))
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(self.base_url + "/chat/completions",
                                   headers={"Authorization": f"Bearer {self.api_key}"},
                                   json=self.request_body(payload, message, baseline))
            response.raise_for_status()
            body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") not in {"stop", "length"}:
            raise ValueError(f"Provider finished with {choice.get('finish_reason')!r}")
        content = (choice.get("message") or {}).get("content") or ""
        if not content.strip():
            raise ValueError("Provider returned an empty message")
        return json.loads(content)


class GroqAdapter(ProviderAdapter):
    name = "groq"
    default_base_url = "https://api.groq.com/openai/v1"
    default_model = "openai/gpt-oss-20b"
    key_variable = "GROQ_API_KEY"
    model_variable = "GROQ_MODEL"
    base_variable = "GROQ_BASE_URL"


class GeminiAdapter(ProviderAdapter):
    name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    default_model = "gemini-3.8-flash"
    key_variable = "GEMINI_API_KEY"
    model_variable = "GEMINI_MODEL"
    base_variable = "GEMINI_BASE_URL"


ADAPTERS: dict[str, ProviderAdapter] = {"groq": GroqAdapter(), "gemini": GeminiAdapter()}


def adapter_for(name: str | None) -> ProviderAdapter | None:
    return ADAPTERS.get(str(name or "").strip().casefold())
