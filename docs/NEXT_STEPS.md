# FINN — next steps and evaluation continuity

30 October 2026 (IST). Submission deadline supplied by the brief: 1 November 2026. Evaluation timing and the exact credit-expiry timestamp are unknown. The user's API credits expire in two days; this is user-reported, not an independently inspected billing balance.

## Immediate issue: fixed locally

The screenshot came from FINN's $0.10 application test limit, not a confirmed shortage in the Anthropic account. Its conservative reservation exceeded the remaining allowance. The private local configuration now permits **$5 total development usage, $0.25 per job**, with Sonnet selected and escalation disabled. This is a ceiling, not a target to spend.

An explicit retry now recovers budget/provider-blocked jobs, preserves the company/event/question and keeps completed or in-flight jobs deduplicated. The original failed attempt remains visible as an old record. Open the recovered result at:

http://127.0.0.1:8000/#/c/INFY/research/job_f086215b7e674b9f

That result completed through the real browser in about eight seconds over the ingested corpus. A repeat request reused it without another model call. Current verification: 25 logic/provider tests and TypeScript/Vite build passed. This does not establish cold retrieval latency, full model accuracy or public availability.

## Use the expiring credits for durable work

Use them for the ten-packet model evaluation, source extraction checks, unfamiliar-ticker research tests and reviewer demonstrations that are genuinely generated and audited. Save the source PDFs, publication proofs, hashes, evidence passages, prompts, outputs, usage and build conversations. Store reviewed demo results alongside their dates and document coverage. Do not spend simply to exhaust the balance or precompute unsupported answers.

The existing database and files already support persisted result/evidence inspection. They survive only if they are preserved when deploying. The current key-free reading regression proves access to an existing saved job; a complete hosted outage/expiry rehearsal remains to be performed.

## Keep evaluation working after credit expiry

Two complementary paths are necessary:

1. **Reviewed historical demonstration:** prepare the three verified research examples through the normal pipeline and preserve them on persistent hosting. Label original event dates, evidence cutoff and when the research was generated. These examples should open without a fresh model call. At present only INFY has the locally verified path; HCLTECH/POLYCAB are not certified by this plan.
2. **Fresh research:** maintain a valid server-side API credential and a credit balance valid throughout evaluation, with an appropriate app spending cap. A new ticker or question needs this path. Cached examples cannot satisfy the assignment's unfamiliar-ticker requirement on their own.

Expiring credits cannot be converted into future live API access by saving the API key. If no other usable balance remains, arrange a funded balance or a separately configured and tested provider before expiry. Do not buy anything, enable automatic recharge or expose the key as part of this document. The owner should check the actual expiry timestamp in Console Billing and ensure the chosen account remains funded beyond the evaluation period.

Official billing references: [Claude API billing](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage), [monthly API credits and expiry](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers). Which credit programme applies to this account has not been verified.

Do not conceal service failures or present saved research as newly generated. Preserve useful saved evidence when generation is unavailable, label it clearly and keep fresh research honest. Add owner-facing readiness checks for credentials, spend allowance, source coverage and persistent storage before submission.

## Build sequence from here

| Order | Deliverable | Exit check |
|---|---|---|
| 1 | Complete the small source/abstention model evaluation | Ten labelled packets; audit critical entity/metric/period/basis/qualification fields and citations. Keep automated comparison verdicts disabled. |
| 2 | General document discovery | Two non-demo companies from different sectors, including a smaller issuer, succeed from empty caches without prefilled document URLs; retrieve annual-report and transcript passages. Repeat from the intended host. |
| 3 | Three reliable prepared research examples | Verify each source chain, publication cutoff and generated claim; resolve HCLTECH proof and verify POLYCAB or replace it based on evidence. |
| 4 | Fifteen-company review queue | All holdings resolve; EOD/announcement coverage is explicit; related filings remain accessible; an event leads into contextual research and evidence. |
| 5 | Public deployment and evaluation continuity | Persistent source/job storage; server-side key only; funded access through evaluation; saved demos readable without generation; fresh ticker actually invokes research; restart and outage behaviour checked. Hosting cost and final publication require concrete review before activation. |
| 6 | Phone verification and submission package | Real phone run, three-minute demo, public link, repository, authentic conversation links and short covering email. Test reviewer access and record any remaining gaps. |

The first unfamiliar-company checks and deployment feasibility should happen before spending time on presentation polish. A working local INFY demonstration is not yet a working general research product. The visual review queue should follow reliable evidence access, rather than conceal its absence.

## Owner actions that cannot be inferred from the code

- Confirm the exact credit expiry in Claude Console Billing and provide a funded balance valid for the evaluation period. Never paste credentials into chat.
- Choose/approve the final hosting arrangement after its costs and persistent storage are reviewable.
- Perform the physical-phone check and verify external reviewer access to the final URL and authentic conversation records.

No public hosting, provider purchase, expiry extension or submission has occurred in this repair pass.
