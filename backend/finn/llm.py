"""Optional model adapters with a shared cost ledger and a keyless product floor.

Model choice follows the pre-build specification section 6. Runtime access is NOT assumed:
without the selected provider's key the adapter reports `model_unavailable`. Schema
compliance is not treated as correctness: the caller validates citations and numbers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from .config import Settings
from .db import Store, new_id, utcnow

# Published standard short-context rates per million tokens (spec section 6, checked 30 Oct 2026).
# These are list prices used for conservative reservations, not measured costs.
PRICES_PER_MTOK = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    # Google AI Studio free tier: no per-token charge (rate-limited, not metered).
    "gemini-2.0-flash": (0.0, 0.0),
    "gemini-2.5-flash": (0.0, 0.0),
    # Groq's published Developer-plan list prices, checked 4 Nov 2026. Free-tier
    # entitlement is account-level and cannot be established from a key string.
    # Keep conservative reservations even when the operator uses a Free account.
    "groq:openai/gpt-oss-20b": (0.075, 0.30),
    "groq:openai/gpt-oss-120b": (0.15, 0.60),
}
# Anthropic rates checked against official pricing on 30 October 2026.
# Requests are bounded below both providers' long-context pricing thresholds.


class ModelUnavailable(Exception):
    pass


class BudgetExceeded(Exception):
    pass


@dataclass
class ModelResult:
    status: str  # completed | incomplete | refused | error
    data: Optional[Dict[str, Any]]
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")))  # conservative byte-based estimate, not a measured token count


def model_prices(model: str):
    if model in PRICES_PER_MTOK:
        return PRICES_PER_MTOK[model]
    # Any Gemini model is used only on the free tier (no per-token charge); this keeps the
    # app working across Gemini model-name changes without editing a price table.
    if model.startswith("gemini-"):
        return (0.0, 0.0)
    if model.startswith("openrouter:") and (model == "openrouter:openrouter/free" or model.endswith(":free")):
        return (0.0, 0.0)
    raise ModelUnavailable("model has no configured price; add a verified rate before making calls")


class Ledger:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.settings = store, settings

    def spent_or_reserved(self) -> float:
        row = self.store.query_one(
            "SELECT COALESCE(SUM(CASE WHEN actual_usd IS NOT NULL THEN actual_usd ELSE reserved_usd END),0) AS s FROM model_calls"
        )
        return float(row["s"]) if row else 0.0

    def reserve(self, job_id: Optional[str], model: str, input_tokens: int, max_output: int) -> str:
        pin, pout = model_prices(model)
        reserve = (input_tokens * pin + max_output * pout) / 1e6
        call_id = new_id("call")
        # The store lock covers both the budget check and reservation insertion.
        with self.store.connect() as conn:
            aggregate = "COALESCE(SUM(COALESCE(actual_usd,reserved_usd)),0)"
            spent = float(conn.execute(f"SELECT {aggregate} FROM model_calls").fetchone()[0])
            job_spent = float(conn.execute(f"SELECT {aggregate} FROM model_calls WHERE job_id=?", (job_id,)).fetchone()[0]) if job_id else 0.0
            if job_spent + reserve > self.settings.job_budget_usd:
                raise BudgetExceeded(f"call plus prior reservations exceed per-job cap ${self.settings.job_budget_usd:.2f}")
            if spent + reserve > self.settings.api_budget_usd:
                raise BudgetExceeded("application API budget would be exceeded")
            conn.execute("INSERT INTO model_calls VALUES (?,?,?,?,?,?,?,?,?)",
                         (call_id, job_id, model, reserve, None, None, None, "reserved", utcnow()))
        return call_id

    def reconcile(self, call_id: str, model: str, usage: Dict[str, Any], status: str) -> float:
        if not usage:
            # A timeout may still have been billed. Keep its reservation until
            # usage is known rather than releasing budget optimistically.
            self.store.execute("UPDATE model_calls SET status=? WHERE call_id=?", (status, call_id))
            row = self.store.query_one("SELECT reserved_usd FROM model_calls WHERE call_id=?", (call_id,))
            return float(row["reserved_usd"])
        pin, pout = model_prices(model)
        it, ot = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        cache_writes = int(usage.get("cache_creation_input_tokens") or 0)
        cache_reads = int(usage.get("cache_read_input_tokens") or 0)
        # No cache creation is requested; count unexpected cached usage
        # conservatively rather than treating it as free.
        actual = ((it + cache_reads + 2 * cache_writes) * pin + ot * pout) / 1e6
        self.store.execute("UPDATE model_calls SET actual_usd=?, input_tokens=?, output_tokens=?, status=? WHERE call_id=?",
                           (actual, it, ot, status, call_id))
        return actual


class ResponsesClient:
    def __init__(self, settings: Settings, store: Store, http: Optional[httpx.Client] = None):
        self.settings = settings
        self.ledger = Ledger(store, settings)
        self.http = http or httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))

    def generate(self, *, job_id: Optional[str], model: str, effort: str, system: str, user: str,
                 schema: Dict[str, Any], schema_name: str, max_output_tokens: int = 2500) -> ModelResult:
        if not self.settings.openai_api_key:
            raise ModelUnavailable("OPENAI_API_KEY is not configured on the server")
        if not model.startswith("gpt-"):
            raise ModelUnavailable("selected model does not belong to the OpenAI provider")
        in_tokens = estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(json.dumps(schema)) + 1024
        if in_tokens > 24000:
            return ModelResult("error", None, model, error=f"input estimate {in_tokens} tokens exceeds 24,000 budget")
        call_id = self.ledger.reserve(job_id, model, in_tokens, max_output_tokens)
        body = {
            "model": model,
            "input": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "text": {"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
            "reasoning": {"effort": effort},
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        try:
            resp = self.http.post(f"{self.settings.openai_base_url}/responses", json=body,
                                  headers={"Authorization": f"Bearer {self.settings.openai_api_key}"})
        except httpx.HTTPError as exc:
            self.ledger.reconcile(call_id, model, {}, "transport_error")
            return ModelResult("error", None, model, error=f"transport error: {exc.__class__.__name__}")
        if resp.status_code != 200:
            self.ledger.reconcile(call_id, model, {}, f"http_{resp.status_code}")
            detail = ""
            try:
                detail = resp.json().get("error", {}).get("code") or ""
            except Exception:  # noqa: BLE001
                pass
            return ModelResult("error", None, model, error=f"provider HTTP {resp.status_code} {detail}".strip())
        return self._parse(resp.json(), call_id, model)

    def _parse(self, payload: Dict[str, Any], call_id: str, model: str) -> ModelResult:
        usage = payload.get("usage") or {}
        cost = self.ledger.reconcile(call_id, model, usage, payload.get("status", "unknown"))
        usage = {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "cost_usd_list_price": round(cost, 6)}
        if payload.get("status") == "incomplete":
            reason = (payload.get("incomplete_details") or {}).get("reason")
            return ModelResult("incomplete", None, model, usage, error=f"incomplete: {reason}")
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "refusal":
                    return ModelResult("refused", None, model, usage, error="model refused")
                if part.get("type") == "output_text":
                    try:
                        return ModelResult("completed", json.loads(part["text"]), model, usage)
                    except (json.JSONDecodeError, KeyError):
                        return ModelResult("error", None, model, usage, error="output was not valid JSON")
        return ModelResult("error", None, model, usage, error="no output_text in response")


class AnthropicClient(ResponsesClient):
    """Messages API with JSON schema output and no external browsing/tools.

    Protocol and rates: platform.claude.com/docs/en/build-with-claude/structured-outputs
    and platform.claude.com/docs/en/about-claude/pricing (checked 30 Oct 2026).
    """

    def generate(self, *, job_id: Optional[str], model: str, effort: str, system: str, user: str,
                 schema: Dict[str, Any], schema_name: str, max_output_tokens: int = 4000) -> ModelResult:
        if not self.settings.anthropic_api_key:
            raise ModelUnavailable("ANTHROPIC_API_KEY is not configured on the server")
        if not model.startswith("claude-"):
            raise ModelUnavailable("selected model does not belong to the Anthropic provider")
        in_tokens = estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(json.dumps(schema)) + 1024
        if in_tokens > 24000:
            return ModelResult("error", None, model, error=f"input estimate {in_tokens} tokens exceeds 24,000 budget")
        call_id = self.ledger.reserve(job_id, model, in_tokens, max_output_tokens)
        body = {"model": model, "max_tokens": max_output_tokens, "system": system,
                "messages": [{"role": "user", "content": user}],
                "output_config": {"format": {"type": "json_schema", "schema": schema}, "effort": effort}}
        try:
            resp = self.http.post(f"{self.settings.anthropic_base_url}/messages", json=body,
                                  headers={"x-api-key": self.settings.anthropic_api_key,
                                           "anthropic-version": "2023-06-01", "content-type": "application/json"})
        except httpx.HTTPError as exc:
            self.ledger.reconcile(call_id, model, {}, "transport_error")
            return ModelResult("error", None, model, error=f"transport error: {exc.__class__.__name__}")
        if resp.status_code != 200:
            self.ledger.reconcile(call_id, model, {}, f"http_{resp.status_code}")
            # Authentication, model access and rate-limit failures are not
            # malformed answers; do not automatically escalate and retry them.
            raise ModelUnavailable(f"Anthropic API returned HTTP {resp.status_code}; check credentials, model access and quota")
        try:
            payload = resp.json()
        except ValueError:
            self.ledger.reconcile(call_id, model, {}, "invalid_response")
            return ModelResult("error", None, model, error="provider returned invalid JSON")
        usage = payload.get("usage") or {}
        cost = self.ledger.reconcile(call_id, model, usage, payload.get("stop_reason", "unknown"))
        usage = {**usage, "cost_usd_list_price": round(cost, 6), "provider": "anthropic"}
        if payload.get("stop_reason") in ("max_tokens", "model_context_window_exceeded"):
            return ModelResult("incomplete", None, model, usage, error=f"incomplete: {payload['stop_reason']}")
        if payload.get("stop_reason") == "refusal":
            return ModelResult("refused", None, model, usage, error="model refused")
        text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            return ModelResult("completed", data, model, usage)
        except ValueError:
            return ModelResult("error", None, model, usage, error="output was not a JSON object")


class GeminiClient(ResponsesClient):
    """Google Gemini via its OpenAI-compatible Chat Completions endpoint.

    The free Google AI Studio tier gives real synthesis at zero per-token cost (it is
    rate-limited, not metered), so FINN can route on-demand research through a capable model
    for free. A 429/5xx or an auth failure raises ModelUnavailable, and the caller falls
    back to the deterministic keyless source brief — the app never hard-depends on it.
    Docs: ai.google.dev/gemini-api/docs/openai (OpenAI compatibility).
    """

    _resolved_model: Optional[str] = None  # cached per-process after discovery

    def _resolve_model(self, requested: str) -> str:
        """Return a model the key can actually use. Gemini's free-tier model names change over
        time, so if the requested one isn't listed we discover an available flash model instead of
        hard-failing with a 404. Result is cached for the process."""
        if type(self)._resolved_model:
            return type(self)._resolved_model
        chosen = requested
        try:
            resp = self.http.get(f"{self.settings.gemini_base_url}/models",
                                 headers={"Authorization": f"Bearer {self.settings.gemini_api_key}"},
                                 timeout=httpx.Timeout(20.0, connect=8.0))
            if resp.status_code == 200:
                ids = []
                for m in (resp.json().get("data") or []):
                    mid = (m.get("id") or "").split("/")[-1]  # strip any "models/" prefix
                    if mid.startswith("gemini-"):
                        ids.append(mid)
                if ids and requested not in ids:
                    skip = ("embedding", "tts", "image", "vision", "audio", "live", "robotics", "computer-use")
                    # Prefer a stable GA flash model; "latest"/preview aliases overload more often.
                    prefs = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]
                    chosen = (next((p for p in prefs if p in ids), None)
                              or next((m for m in ids if "flash" in m and not any(s in m for s in skip)), None)
                              or next((m for m in ids if not any(s in m for s in skip)), None)
                              or ids[0])
        except httpx.HTTPError:
            pass  # keep the requested model; a real failure surfaces on the generate call
        type(self)._resolved_model = chosen
        return chosen

    def generate(self, *, job_id: Optional[str], model: str, effort: str, system: str, user: str,
                 schema: Dict[str, Any], schema_name: str, max_output_tokens: int = 2500) -> ModelResult:
        if not self.settings.gemini_api_key:
            raise ModelUnavailable("GEMINI_API_KEY is not configured on the server")
        if not model.startswith("gemini-"):
            raise ModelUnavailable("selected model does not belong to the Gemini provider")
        model = self._resolve_model(model)
        in_tokens = estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(json.dumps(schema)) + 1024
        if in_tokens > 24000:
            return ModelResult("error", None, model, error=f"input estimate {in_tokens} tokens exceeds 24,000 budget")
        call_id = self.ledger.reserve(job_id, model, in_tokens, max_output_tokens)
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
            # Gemini 2.5 flash is a reasoning model: its internal thinking counts against the output
            # budget, so give generous headroom or the structured JSON gets truncated ("length").
            "max_tokens": max(max_output_tokens, 8192),
            "temperature": 0,
        }
        import time as _time
        resp = None
        for attempt in range(3):
            try:
                resp = self.http.post(f"{self.settings.gemini_base_url}/chat/completions", json=body,
                                      headers={"Authorization": f"Bearer {self.settings.gemini_api_key}"})
            except httpx.HTTPError as exc:
                if attempt < 2:
                    _time.sleep(1.5 * (attempt + 1)); continue
                self.ledger.reconcile(call_id, model, {}, "transport_error")
                return ModelResult("error", None, model, error=f"transport error: {exc.__class__.__name__}")
            # Free/preview models can be briefly overloaded; retry transient errors before degrading.
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                _time.sleep(2.0 * (attempt + 1)); continue
            break
        if resp.status_code != 200:
            self.ledger.reconcile(call_id, model, {}, f"http_{resp.status_code}")
            # Rate limit, auth and access failures are not malformed answers; degrade to keyless.
            raise ModelUnavailable(f"Gemini API returned HTTP {resp.status_code} after retries; the free model may be momentarily overloaded or rate-limited—retry shortly")
        try:
            payload = resp.json()
        except ValueError:
            self.ledger.reconcile(call_id, model, {}, "invalid_response")
            return ModelResult("error", None, model, error="provider returned invalid JSON")
        u = payload.get("usage") or {}
        usage_norm = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")}
        cost = self.ledger.reconcile(call_id, model, usage_norm, payload.get("choices", [{}])[0].get("finish_reason", "unknown"))
        usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                 "cost_usd_list_price": round(cost, 6), "provider": "gemini"}
        choices = payload.get("choices") or []
        if not choices:
            return ModelResult("error", None, model, usage, error="no choices in response")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            return ModelResult("incomplete", None, model, usage, error="incomplete: max tokens reached")
        content = (choice.get("message") or {}).get("content")
        if not content:
            return ModelResult("refused", None, model, usage, error="model returned empty content")
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            return ModelResult("completed", data, model, usage)
        except ValueError:
            return ModelResult("error", None, model, usage, error="output was not a JSON object")


def _matches_output_schema(value: Any, schema: Dict[str, Any]) -> bool:
    """Check the structural keywords used by FINN's two output contracts.

    A router or provider can return JSON despite an upstream schema mismatch. Reject
    wrong field types before the source validators consume it; this is not an
    entailment/financial-correctness check.
    """
    kinds = schema.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds] if kinds else []
    tests = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "null": lambda x: x is None,
             "boolean": lambda x: isinstance(x, bool),
             "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
             "integer": lambda x: isinstance(x, int) and not isinstance(x, bool)}
    if kinds and not any(kind in tests and tests[kind](value) for kind in kinds):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        return all(_matches_output_schema(v, properties[k]) for k, v in value.items() if k in properties)
    if isinstance(value, list) and "items" in schema:
        return all(_matches_output_schema(v, schema["items"]) for v in value)
    return True


class FreeCompletionsClient(ResponsesClient):
    """Shared bounded adapter for explicitly selected Groq/OpenRouter accounts.

    One HTTP request per generate call: auth, quota, transport and provider failures
    immediately return control to the source-brief fallback. No cross-provider
    retries, account creation, tools, browsing or paid OpenRouter routing.
    """

    provider = ""
    endpoint = ""

    def __init__(self, settings: Settings, store: Store, http: Optional[httpx.Client] = None):
        super().__init__(settings, store, http=http or httpx.Client(timeout=httpx.Timeout(45.0, connect=8.0)))

    def _request_options(self, model: str, max_output: int, effort: str) -> Dict[str, Any]:
        return {"max_tokens": max_output}

    def generate(self, *, job_id: Optional[str], model: str, effort: str, system: str, user: str,
                 schema: Dict[str, Any], schema_name: str, max_output_tokens: int = 2500) -> ModelResult:
        key = getattr(self.settings, f"{self.provider}_api_key")
        if not key or not key.strip():
            raise ModelUnavailable(f"{self.provider.upper()}_API_KEY is not configured on the server")
        max_output = max(4096, min(max_output_tokens, 8192))
        options = self._request_options(model, max_output, effort)  # validates model before ledger/network
        ledger_model = f"{self.provider}:{model}"
        in_tokens = estimate_tokens(system) + estimate_tokens(user) + estimate_tokens(json.dumps(schema)) + 1024
        if in_tokens > 24000:
            return ModelResult("error", None, model, error=f"input estimate {in_tokens} tokens exceeds 24,000 budget")
        call_id = self.ledger.reserve(job_id, ledger_model, in_tokens, max_output)
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
            "temperature": 0,
            **options,
        }
        try:
            response = self.http.post(self.endpoint, json=body,
                                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        except httpx.HTTPError:
            self.ledger.reconcile(call_id, ledger_model, {}, "transport_error")
            raise ModelUnavailable(f"{self.provider.title()} is unreachable; cited source extracts remain available") from None
        if response.status_code != 200:
            self.ledger.reconcile(call_id, ledger_model, {}, f"http_{response.status_code}")
            # Never reflect provider error bodies: they may echo credentials or source text.
            raise ModelUnavailable(f"{self.provider.title()} returned HTTP {response.status_code}; "
                                   "check server credentials or free quota. Cited source extracts remain available")
        try:
            if len(response.content) > 2 * 1024 * 1024:
                raise ValueError("response too large")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid provider payload")
        except ValueError:
            self.ledger.reconcile(call_id, ledger_model, {}, "invalid_response")
            return ModelResult("error", None, model, error="provider returned an invalid response")
        raw_usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        def count(name):
            value = raw_usage.get(name)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        normal_usage = {"input_tokens": count("prompt_tokens"), "output_tokens": count("completion_tokens")}
        if any(v is None for v in normal_usage.values()):
            normal_usage = {}
        choices = payload.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        finish = choice.get("finish_reason", "unknown")
        cost = self.ledger.reconcile(call_id, ledger_model, normal_usage, finish)
        actual_model = payload.get("model") if isinstance(payload.get("model"), str) else model
        usage = {**normal_usage, "cost_usd_list_price": round(cost, 6), "provider": self.provider,
                 "requested_model": model}
        if finish == "length":
            return ModelResult("incomplete", None, actual_model, usage, error="incomplete: max tokens reached")
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        if message.get("refusal") or finish == "content_filter":
            return ModelResult("refused", None, actual_model, usage, error="model refused")
        content = message.get("content")
        try:
            data = json.loads(content) if isinstance(content, str) else None
            if not isinstance(data, dict) or not _matches_output_schema(data, schema):
                raise ValueError("invalid output structure")
            return ModelResult("completed", data, actual_model, usage)
        except ValueError:
            return ModelResult("error", None, actual_model, usage, error="output did not match the requested JSON structure")


class GroqClient(FreeCompletionsClient):
    """Groq Free-plan option; list-price reservations also bound upgraded accounts."""

    provider = "groq"
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _request_options(self, model: str, max_output: int, effort: str) -> Dict[str, Any]:
        if model not in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
            raise ModelUnavailable("Groq model is not in FINN's verified schema/price allowlist")
        return {"max_completion_tokens": max_output,
                "reasoning_effort": effort if effort in ("low", "medium", "high") else "low"}


class OpenRouterClient(FreeCompletionsClient):
    """Free variants only, with zero-price and data-policy routing guards."""

    provider = "openrouter"
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def _request_options(self, model: str, max_output: int, effort: str) -> Dict[str, Any]:
        if model != "openrouter/free" and not ("/" in model and model.endswith(":free")):
            raise ModelUnavailable("FINN allows only openrouter/free or an explicit :free model; paid routing is disabled")
        return {"max_tokens": max_output,
                "provider": {"require_parameters": True, "data_collection": "deny",
                             "max_price": {"prompt": 0, "completion": 0}}}


def create_model_client(settings: Settings, store: Store) -> ResponsesClient:
    if settings.model_provider == "keyless":
        raise ModelUnavailable("Keyless mode is selected; source briefs do not use a model")
    if settings.model_provider == "anthropic":
        return AnthropicClient(settings, store)
    if settings.model_provider == "gemini":
        return GeminiClient(settings, store)
    if settings.model_provider == "groq":
        return GroqClient(settings, store)
    if settings.model_provider == "openrouter":
        return OpenRouterClient(settings, store)
    if settings.model_provider == "openai":
        return ResponsesClient(settings, store)
    raise ModelUnavailable("No supported model provider was explicitly selected")
