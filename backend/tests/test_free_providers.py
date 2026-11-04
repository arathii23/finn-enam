"""Offline safety/protocol regressions for optional Groq and free-only OpenRouter.

All keys, companies and transports here are synthetic. No real provider is contacted.
"""
import json
from dataclasses import replace

import httpx
import pytest

from finn import config
from finn.config import get_settings
from finn.contracts import ResearchRequest
from finn.ingest import ingest_replay
from finn.llm import GroqClient, ModelUnavailable, OpenRouterClient, create_model_client
from finn.replay import load_manifest
from finn.research import run_research
from finn.sources.nse import resolve_company


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"],
          "properties": {"items": {"type": "array", "items": {"type": "string"}}}}


def _settings(env, provider):
    return replace(env[0], model_provider=provider, groq_api_key="fake-groq-key",
                   openrouter_api_key="fake-openrouter-key", model_escalation="")


def _call(client, model, **kw):
    return client.generate(job_id="test-provider-job", model=model, effort="low", system="Use only supplied evidence.",
                           user="Quote the evidence in JSON.", schema=SCHEMA, schema_name="test_items", **kw)


def _completion(content=None, finish="stop", model="resolved-model", **extra):
    return {"model": model, "choices": [{"finish_reason": finish,
            "message": {"content": content if content is not None else json.dumps({"items": ["Source quote."]})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}, **extra}


def test_default_is_keyless_even_with_old_paid_keys(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("FINN_MODEL_PROVIDER", raising=False)
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                 "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setenv(name, "old-ambient-key")
    monkeypatch.delenv("FINN_MODEL_PRIMARY", raising=False)
    settings = get_settings()
    assert settings.model_provider == "keyless"
    assert not settings.model_configured
    assert settings.model_primary == ""


@pytest.mark.parametrize("provider,key,model", [
    ("groq", "GROQ_API_KEY", "openai/gpt-oss-20b"),
    ("openrouter", "OPENROUTER_API_KEY", "openrouter/free"),
    ("gemini", "GEMINI_API_KEY", "gemini-2.5-flash"),
])
def test_model_provider_must_be_explicit(monkeypatch, provider, key, model):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setenv("FINN_MODEL_PROVIDER", provider)
    monkeypatch.setenv(key, "fake-test-key")
    monkeypatch.delenv("FINN_MODEL_PRIMARY", raising=False)
    monkeypatch.delenv("FINN_MODEL_ESCALATION", raising=False)
    settings = get_settings()
    assert settings.model_configured and settings.model_api_key_env == key
    assert settings.model_primary == model
    if provider != "gemini":
        assert settings.model_escalation == ""


@pytest.mark.parametrize("provider,klass,model,keyfield", [
    ("groq", GroqClient, "openai/gpt-oss-20b", "groq_api_key"),
    ("openrouter", OpenRouterClient, "openrouter/free", "openrouter_api_key"),
])
def test_missing_key_never_sends_request(env, provider, klass, model, keyfield):
    calls = []
    settings = replace(_settings(env, provider), **{keyfield: None})
    http = httpx.Client(transport=httpx.MockTransport(lambda req: calls.append(req)))
    with pytest.raises(ModelUnavailable):
        _call(klass(settings, env[1], http=http), model)
    assert not calls
    assert env[1].query_one("SELECT COUNT(*) AS n FROM model_calls")["n"] == 0


def test_groq_protocol_and_conservative_paid_tier_reservation(env):
    calls = []
    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        assert str(req.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer fake-groq-key"
        assert body["model"] == "openai/gpt-oss-20b"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["max_completion_tokens"] >= 4096
        assert body["reasoning_effort"] == "low"
        assert "tools" not in body
        return httpx.Response(200, json=_completion(model="openai/gpt-oss-20b"))
    settings = _settings(env, "groq")
    assert isinstance(create_model_client(settings, env[1]), GroqClient)
    result = _call(GroqClient(settings, env[1], http=httpx.Client(transport=httpx.MockTransport(handler))),
                   "openai/gpt-oss-20b")
    assert result.status == "completed" and result.data == {"items": ["Source quote."]}
    assert len(calls) == 1 and result.usage["provider"] == "groq"
    row = env[1].query_one("SELECT model,reserved_usd,actual_usd FROM model_calls")
    assert row["model"] == "groq:openai/gpt-oss-20b"
    assert row["reserved_usd"] > 0
    assert row["actual_usd"] == pytest.approx((100*.075+20*.30)/1e6)


def test_openrouter_keeps_free_and_data_policy_guards(env):
    calls = []
    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert body["provider"] == {"require_parameters": True, "data_collection": "deny",
                                    "max_price": {"prompt": 0, "completion": 0}}
        assert body["model"] == "openrouter/free" and "models" not in body
        return httpx.Response(200, json=_completion(model="vendor/resolved:free"))
    settings = _settings(env, "openrouter")
    assert isinstance(create_model_client(settings, env[1]), OpenRouterClient)
    result = _call(OpenRouterClient(settings, env[1], http=httpx.Client(transport=httpx.MockTransport(handler))),
                   "openrouter/free")
    assert result.status == "completed" and result.model == "vendor/resolved:free"
    assert result.usage["requested_model"] == "openrouter/free"
    assert result.usage["cost_usd_list_price"] == 0 and len(calls) == 1


@pytest.mark.parametrize("klass,provider,model", [
    (OpenRouterClient, "openrouter", "openai/paid-model"),
    (OpenRouterClient, "openrouter", "openrouter/auto"),
    (GroqClient, "groq", "llama-3.3-70b-versatile"),
    (GroqClient, "groq", "unverified-model"),
])
def test_unapproved_model_rejected_before_network_and_budget(env, klass, provider, model):
    calls = []
    client = klass(_settings(env, provider), env[1],
                   http=httpx.Client(transport=httpx.MockTransport(lambda req: calls.append(req))))
    with pytest.raises(ModelUnavailable):
        _call(client, model)
    assert not calls
    assert env[1].query_one("SELECT COUNT(*) AS n FROM model_calls")["n"] == 0


@pytest.mark.parametrize("status", [401, 402, 403, 429, 503])
def test_provider_http_failures_do_not_retry_or_echo_error_body(env, status):
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(status, json={"error": {"message": "fake-openrouter-key private source text"}})
    client = OpenRouterClient(_settings(env, "openrouter"), env[1],
                              http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ModelUnavailable) as exc:
        _call(client, "openrouter/free")
    assert "fake-openrouter-key" not in str(exc.value) and "private source text" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.parametrize("payload,expected", [
    (_completion(finish="length"), "incomplete"),
    (_completion(finish="content_filter"), "refused"),
    (_completion(content="not JSON"), "error"),
    (_completion(content='{"items": "wrong type"}'), "error"),
    (_completion(content='{"items": ["ok"], "unrequested": true}'), "error"),
    ({"choices": []}, "error"),
    (["wrong root"], "error"),
])
def test_malformed_or_truncated_outputs_are_not_completed(env, payload, expected):
    http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))
    result = _call(OpenRouterClient(_settings(env, "openrouter"), env[1], http=http), "openrouter/free")
    assert result.status == expected and result.data is None


def test_quota_failure_completes_with_cited_source_brief(env):
    settings, store, fetcher, _ = env
    cfg = load_manifest(settings.manifest_path)
    ingest_replay(store, fetcher, settings, cfg, ["TESTCO"], log=lambda s: None)
    settings = replace(_settings(env, "openrouter"), model_primary="openrouter/free")
    calls = []
    def limited(req):
        calls.append(req)
        return httpx.Response(429, json={"error": {"message": "free daily quota exhausted"}})
    client = OpenRouterClient(settings, store, http=httpx.Client(transport=httpx.MockTransport(limited)))
    state, out = run_research(store, settings, cfg, resolve_company(store, "TESTCO"),
                              ResearchRequest(symbol="TESTCO", question="What supports the growth outlook?"),
                              client, "quota-test", lambda s: None)
    assert state == "partial" and out.generation.status == "model_unavailable"
    assert len(calls) == 1 and out.source_brief and out.source_brief.highlights
    for highlight in out.source_brief.highlights:
        source = store.query_one("SELECT text FROM passages WHERE passage_id=?", (highlight.evidence_id,))
        assert highlight.quote.rstrip("…").strip() in source["text"]
