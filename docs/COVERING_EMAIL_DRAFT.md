# Covering email — draft (not sent)

To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

**Do not send automatically.** Fill the [bracketed] items (deployed link, repo link, AI-history
share links), confirm the phone test, then send manually.

---

Hi team,

Attached / linked is FINN, my take on the mobile investor intelligence layer.

**What I built.** FINN is a mobile-first, primary-source research product with the two hero workflows
from the brief:
- **Review (Push):** a prioritised digest across a 15-company NSE portfolio. Each corporate filing is
  classified into leading / notable / routine tiers by an explainable rule set (mapped to your reference
  categories), with routine compliance collapsed and generic "Updates" filings re-classified from their
  subject/attachment so a results filing or transcript is never buried. End-of-day price/volume anomaly
  flags are configurable (my move-% and volume-× thresholds), raw/unadjusted, and never attributed to a
  filing as cause.
- **Research (Pull):** on-demand, grounded strictly in primary sources (annual reports + concall
  transcripts + exchange filings). Business context, management commentary, explicit evidence gaps and one
  follow-up question — every factual claim resolves to a cited passage you can open at the exact PDF page.

**Key decisions and trade-offs.**
- Primary-source discipline is enforced in code, not just prompted: generated claims are dropped unless
  every cited id is in the evidence packet, numbers appear verbatim in the cited text, the reporting basis
  (standalone/consolidated) is preserved, and the speaker/period match the source. Nothing is filled from
  the model's own knowledge.
- Historical replay with a fixed publication cutoff (30 Apr 2025), so a document is only used if it was
  provably public by then — the demo is reproducible and leak-free. A separate path researches any NSE
  ticker where data is available (build-to-generalise, not hard-wired to the demo set).
- Model routing for cost: cheap extraction-grade model evaluated against a stronger one on labelled
  packets; the stronger model (Sonnet, low effort) was retained only where source-level review justified
  it. A cost ledger reserves budget before each call and fails closed at the cap. Total application spend
  to date is well under $1.
- Deliberately left out: automated beat/miss or credibility verdicts (shown to be unsafe without stronger
  comparability gates), live intraday data, and features that would be broad-but-brittle.

**What I'd do next.** Ingest the full portfolio and add 3–5 more verified research demos; a triggered-alert
channel on top of the EOD checks; printed-page locators; and the numbers-vs-narrative guidance tracker once
its comparability gates pass independent review.

**How to try it.** [deployed phone link]. Repo: [GitHub link]. AI build history: [share links].

Thanks for a genuinely interesting problem.
[Name]
