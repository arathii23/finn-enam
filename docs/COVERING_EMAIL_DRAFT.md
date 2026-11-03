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

Prototype — two free links, both open on a phone with no install or login:
  • Always-on demo (GitHub Pages, never sleeps): https://arathii23.github.io/finn-enam/
    Full digest, saved research briefs, quarterly tables, management cards, narrative-vs-numbers,
    primary-source evidence, and live market prices that auto-refresh every ~5 minutes.
  • Live research backend (Render free, Gemini-powered): https://finn-mow9.onrender.com
    Adds on-demand research for any NSE ticker with real AI synthesis (free Google Gemini),
    grounded in and validated against the primary sources. Free instances sleep after ~15 min idle
    and wake in ~1 minute, so the always-on link above is the primary one.
Repository: https://github.com/arathii23/finn-enam
AI build history:
  • Claude Code (primary coding agent): https://claude.ai/share/e6988c97-2cb5-49ec-a81c-29eb6924848d
  • ChatGPT: [your ChatGPT share link]

Regards,
[Name]
