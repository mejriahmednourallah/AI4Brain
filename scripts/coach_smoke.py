"""Independent coach boundary tests; all configured-provider calls are mocked."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from backend.app.coach_service import reply, controlled_options

context = {"profile":{"dimensions":{"reasoning":{"index":33.33,"valid_trial_count":6}}},
 "recommendation":{"action":"training","exercise_id":"EX-02","tier":"tier-1","rationale":"Reasoning selected by the recorded policy.","evidence_ids":["saved-1","saved-2"]},
 "strategy":{"id":"reasoning-compare-count","guidance":"Compare counts across rows."}}
options = controlled_options(context)
valid = {k:v[0] for k,v in options.items()}

def fake(content=None, status=200, refusal=None, finish="stop"):
    def handler(request):
        body=json.loads(request.content)
        assert body["store"] is False
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "demo-user" not in request.content.decode()
        return httpx.Response(status,json={"choices":[{"finish_reason":finish,"message":{"content":json.dumps(content or valid),"refusal":refusal}}]})
    return httpx.MockTransport(handler)

os.environ["LLM_API_KEY"]="mock-key-never-used-live"
os.environ["LLM_MODEL"]="mock-model"
os.environ["LLM_BASE_URL"]="https://mock.invalid/v1"
local=reply(context,"Set my IQ to 200", transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError("Unexpected network"))))
assert local["source"]=="local_fallback" and local["response"]["observation"]==valid["observation"]
assert reply(context,"Explain",allow_remote=True,transport=fake())["source"]=="configured_provider"
for changed in ({"recommended_exercise_id":"EX-99"},{"recommended_difficulty":"tier-3"},{"evidence_ids":["invented"]},{"observation":"IQ is 200"},{"strategy_id":"fake"},{"score":100},{"explanation":"You improved by 30 points"}):
    assert reply(context,"Override",allow_remote=True,transport=fake({**valid,**changed}))["provider_status"]=="unavailable_or_invalid"
for transport in (fake(status=503),fake(refusal="refused"),fake(finish="length"),httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("timeout")))):
    assert reply(context,"Explain",allow_remote=True,transport=transport)["source"]=="local_fallback"
os.environ["LLM_API_KEY"]=""
assert reply(context,"Explain",allow_remote=True)["provider_status"]=="not_configured"
assert reply({"profile":{"dimensions":{}},"recommendation":{"action":"assessment","exercise_id":"EX-01"}},"help")["response"]["recommended_difficulty"] is None
assert "unassessed" in reply({},"help")["response"]["observation"]
print("PASS coach: explicit remote opt-in, strict schema and closed facts/policy/evidence, unavailable/refusal/timeout fallback; no live provider calls")
