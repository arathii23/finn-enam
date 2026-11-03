# Covering email — review draft, not sent

Recipient: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Replace the bracketed links, verify reviewer access and the physical-phone test, and obtain final
approval before sending. This draft describes the implemented scope; it does not claim deployment.

---

Hi team,

I built FINN around two questions an investor returns to: **what changed across my holdings, and
what do the company's own sources establish?**

**Review** covers a mixed 15-company NSE portfolio. A selectable historical period, company/type
filters, explainable attention tiers and configurable EOD flags help narrow the feed. Routine
filings stay accessible. The original exchange description and attachment are available beside
each event; a price move is never attributed to a filing as its cause.

**Research** lets the user open a saved brief or ask a focused company/event question. Three
prepared examples span IT services, banking and building products. Answers use annual reports,
call transcripts and exchange filings, with exact passages, PDF pages, source dates and explicit
evidence gaps. The demo is labelled as a replay with a 30 April 2025 evidence cutoff.

Two focused analytical views complement the briefs: management guidance versus the disclosed
outcome, with metric/period/currency/entity checks and visible qualifications; and quarterly
headline figures with prior values and calculated QoQ/YoY changes. Unsupported numbers—including
EBITDA when not explicitly disclosed—are omitted. Appointment profiles quote the primary filing,
with separate evidence for the appointment and background.

On cost and model choice: FINN is **free to run and free to evaluate**. The default build uses no
model at all — deterministic code handles prioritisation, arithmetic, appointment parsing and a
query-aware **verbatim source brief** that quotes and cites the most relevant primary-source
sentences for a fresh question (figures quoted, never computed). For genuine AI synthesis the app
routes through Google Gemini's **free tier** (zero per-token cost) behind the same citation/number/
speaker validation; a rate limit degrades gracefully back to the keyless brief. This is deliberate
model routing — cheap/free where it suffices, with paid providers selectable but never required.
Saved results read without any model call, and the earlier development ledger stayed under $1.

I deliberately left out intraday feeds, notification delivery, investment recommendations and an
exhaustive financial-analysis suite. The guidance comparison uses available annual disclosures,
not a claimed complete four-quarter promise history. Automated source checks do not establish
universal model accuracy; selected results were also inspected against their sources.

Next I would broaden issuer/layout coverage, validate the workflow with investors, and add a
monitored notification channel with production retrieval and persistence checks.

Prototype (open on a phone — no install, no login): [static HTTPS link + QR]
  A read-only snapshot on a free CDN that never sleeps: full digest, saved briefs, quarterly,
  management, narrative and primary-source evidence. On-demand research runs on the optional
  live backend (keyless, or free Gemini); [live link if deployed, else "run locally — see README"].
Repository: [verified GitHub link]
Authentic AI build conversations: [verified Claude and Codex share/export links]

Regards,
[Name]
