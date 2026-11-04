# Free resources for FINN

Checked against official provider documentation on **4 November 2026**. Provider support
has offline transport and failure tests; neither new provider has been called with a real
key or source-reviewed for answer quality. No new account, key, credit purchase or billing
change was made.

FINN's default is `FINN_MODEL_PROVIDER=keyless` when the variable is omitted. Old keys in a
shell or settings file do not silently activate a model. Review, saved research, exact
evidence and new extractive source briefs continue without any model provider.

## Small practical provider set

| Option | What it adds | Free-use boundary |
|---|---|---|
| Keyless source brief | Exact, query-relevant sentences from eligible company documents, with evidence links | No model account or key; existing source-access limits still apply |
| Gemini | Optional synthesis through the existing validation path | Use an eligible Google AI Studio free-tier project; paid account settings are outside FINN's control |
| Groq | A second optional synthesis backend; default `openai/gpt-oss-20b`, with strict JSON-schema output | Stay on Groq's Free plan. Model availability and quota depend on the account. Upgrading enables usage charges |
| OpenRouter | Free-model routing when a suitable free endpoint is available | Only `openrouter/free` or a model ID ending in `:free`; FINN also sends zero-price and data-policy guards |

These are alternative operator-selected backends. FINN does not spread a question across
providers, rotate keys to evade limits, or silently substitute a paid model. A quota/auth/
transport error returns the cited source brief. The new adapters make one HTTP request per
generation attempt and have no default escalation model.

## Server setup

Save a key only in the ignored local `.env` or the host's secret settings. Never put it in
a frontend build, GitHub Pages settings exposed as `VITE_*`, a public repository, or a chat.
The visitor never needs to supply a key.

Choose one configuration:

```dotenv
# Default: no model calls, even when other provider keys are present.
FINN_MODEL_PROVIDER=keyless
```

```dotenv
# Groq: create your own key in https://console.groq.com/keys
# Check that the account remains on the Free plan before enabling it.
FINN_MODEL_PROVIDER=groq
GROQ_API_KEY=your-server-key
FINN_MODEL_PRIMARY=openai/gpt-oss-20b
FINN_MODEL_ESCALATION=
```

Groq uses `https://api.groq.com/openai/v1/chat/completions`. FINN permits only the two
documented GPT-OSS models (`openai/gpt-oss-20b` and `openai/gpt-oss-120b`) whose strict
schema support and list prices were checked. Account-level free eligibility cannot be
proved from an API-key string. The shared budget ledger therefore conservatively reserves
Groq's Developer-plan list prices: 20B input/output **$0.075/$0.30 per million tokens**;
120B **$0.15/$0.60**. Those reservations are estimates, not a bill or a claim of spending
on a Free account. The existing $5 application and $0.25/job ceilings still apply.

```dotenv
# OpenRouter: create your own key in https://openrouter.ai/settings/keys
FINN_MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=your-server-key
FINN_MODEL_PRIMARY=openrouter/free
FINN_MODEL_ESCALATION=
```

OpenRouter uses `https://openrouter.ai/api/v1/chat/completions`. `openrouter/free` chooses
among available free models supporting the requested structured-output features. To keep
one model stable for evaluation, select an available explicit `vendor/model:free` ID.
FINN rejects other IDs before the request and sends `provider.max_price` with zero prompt
and completion prices, `require_parameters=true`, and `data_collection=deny`. If no eligible
endpoint remains, the app uses source extracts. It does not loosen these constraints.
The returned model ID is retained for provenance; free-router answers can vary between runs.

After changing settings, restart the backend. A static snapshot continues to use saved
read models; enabling a backend provider does not add synthesis to an offline static bundle.

## Limits and data handling

- **Groq:** exact organization RPM/TPM/daily limits are shown in the account's Limits page;
  public example limits are not a capacity guarantee. The Free-to-Developer upgrade requires
  a payment method and introduces usage billing. Groq says inference content is not retained
  by default, with exceptions for reliability/abuse investigations and features such as
  batch jobs. FINN uses ordinary synchronous inference, no batch/fine-tuning or external tools.
- **OpenRouter:** free requests have account-level minute/daily caps. Read the current
  `free_model_daily_requests` policy via the account/keys dashboard or official key API;
  do not create extra keys/accounts as a quota workaround. Prompts pass through both
  OpenRouter and the selected upstream provider. FINN requests non-collecting provider
  routes, but this is not a promise of absolute zero retention; platform legal/safety
  exceptions and account privacy settings still apply.
- **Public-source discipline:** FINN sends only the current question and selected eligible
  primary-source passages through the existing writer. Personal notes should stay local;
  never place confidential holdings, client data or nonpublic information into a free
  provider merely because its token price is zero.

The free options increase availability; they do not establish better financial accuracy.
Every generated claim still passes citation/number/speaker checks. Representative outputs
need review against their own source pages before comparing provider quality. Correct JSON
does not establish a faithful qualification, correct period or financial comparability.

## Official references

- [Groq Free and Developer plan billing](https://console.groq.com/docs/billing-faqs)
- [Groq account rate limits](https://console.groq.com/docs/rate-limits)
- [Groq supported models and list prices](https://console.groq.com/docs/models)
- [Groq OpenAI-compatible endpoint](https://console.groq.com/docs/openai)
- [Groq strict structured-output models](https://console.groq.com/docs/structured-outputs)
- [Groq data handling](https://console.groq.com/docs/your-data)
- [OpenRouter free-model router](https://openrouter.ai/openrouter/free)
- [OpenRouter API limits and per-key quota fields](https://openrouter.ai/docs/api/reference/limits)
- [OpenRouter parameter, data-policy and maximum-price routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter data handling and privacy settings](https://openrouter.ai/docs/guides/privacy/data-collection)
