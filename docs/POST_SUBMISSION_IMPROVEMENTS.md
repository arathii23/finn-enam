# FINN practical-use improvements - 4 November 2026

The user reports that the assessment has already been submitted. This continuation improves the
existing product in the local working tree; it has not committed, pushed, deployed or sent a new
submission. Earlier dated status claims describe earlier checkpoints.

## A useful everyday journey

The intended user is a self-directed Indian equity investor or research associate reviewing a small
watchlist: a brief portfolio check, then a deeper source check around results or an important notice.
The prepared Review universe still has 15 holdings; company research also accepts direct NSE symbols.
These workflow choices have been exercised locally, not validated through investor interviews yet.

1. In the live app, choose **Review > Current filings > Check latest filings**. Inspect the check
   time and each holding's source gaps, narrow by company/type, and open an original filing.
2. Select **Read & research filing**, or find a company by name/symbol. Choose the historical
   demo or current sources and ask a specific question. A page open is read-only; a research
   action explicitly checks sources and reads the selected attachment.
3. Open the exact evidence, **Save point** / **Save quote** / **Keep as follow-up**, and add your
   own note in **Notebook**. Mark it followed up and export Markdown when needed. Sources, user
   annotations and model-written claims keep their own provenance.

## What changed

- Current exchange metadata checks cover up to 15 known holdings and seven IST calendar dates by
  default. They have a 45-second budget, short socket timeouts, no retries, a 2 MiB response cap,
  company/date/URL checks, a 15-minute cache, atomic reports and per-holding failure states.
  Valid earlier records survive a failed refresh. No PDFs or model calls occur in this check.
- Current-source research rechecks bounded annual-report/transcript candidates, retains publication
  proof and identity gates, and can explicitly download a selected company-bound event attachment.
  Sources published after the reference cutoff or without publication proof stay excluded. An
  earlier publication date keeps its original proof when the same PDF is reattached later.
  Discovery accepts verified standalone-name dialogue and explicit call titles later in a bundled
  PDF; a roster, an intimation cover or an AGM-only transcript does not become an earnings call.
- Question search uses the question's topics instead of letting generic business prose dominate.
  A missing auditor-resignation topic does not produce a CFO/director resignation as its answer.
  Explicit negative disclosures remain usable. Missing topics return a named evidence gap.
- Source quotations preserve adjacent conditions instead of cutting them to 360 characters.
  Short following conditions split into another chunk retain their own quote and evidence ID;
  the headline is omitted if its known condition cannot fit the bounded brief. Newer equally
  relevant transcripts are preferred, and cited context survives the retrieval cap.
  Keyless briefs rank the chosen statements, prioritize management answers for guidance questions,
  avoid repeating near-identical statements in a media/analyst bundle, and keep page-break context
  with its continuation. Different figures or qualifications are not deduplicated. Each displayed
  quote shows its own source publication date. Saving a context-linked quote retains the complete
  cited group in the notebook, so a page-break condition is not lost on save or export.
- Useful keyless briefs now appear in Saved research. Static question/event/retry actions lead
  to a prefilled live-app link rather than a static-mode error. Company search accepts names
  within the portfolio as well as direct symbols. Research drafts survive navigation in the tab.
- The notebook stores cited points, quotes, questions and personal follow-up notes in the browser.
  It supports search, open/done status, removal and Markdown export with document URLs, pages,
  passage IDs, speakers where available, source hashes and evidence cutoffs. Notes do not go to
  an AI provider. It is local to the browser/origin and does not sync across the two app links.
- Market rows show their actual session date separately from fetch time. Refresh failures retain
  and identify the earlier snapshot. Missing/short provider arrays and malformed individual rows
  cannot crash the entire portfolio; unknown prices/volume stay unknown. Current review does not
  promote April 2025 stored prices into current-day alerts. Live thresholds apply to the optional
  market snapshot too. Postal-ballot results no longer masquerade as financial-results alerts.
- Keyless is the code, Docker and blueprint default. Ambient old credentials cannot select a
  model. Explicit Gemini settings remain supported; optional Groq and free-only OpenRouter
  adapters use the same downstream evidence validation and fall back to source extracts.
  No account, credential, billing or existing hosted setting was changed.

## Submitted-email claim check

| Email claim | Result and practical limit |
|---|---|
| What changed across 15 holdings? | Historical queue retained; live app adds an explicit recent exchange-notice check. It does not run continuous background filing monitoring. |
| Period, company/type filters and own alert thresholds | Live controls work; current and historical preferences stay separate. Static browsing retains prepared periods and directs computation to the live app. Alerts are in-app flags, not delivered notifications. |
| Original exchange text and filing | Retained; selected current attachments can be downloaded/read on demand. Metadata alone is labelled as metadata. |
| Ask a question and inspect exact primary evidence | Query-aware current/historical research, generic discovery, exact passage/PDF links and explicit gaps. Broader issuer/layout coverage remains a bounded-source problem. |
| Guidance versus delivery | Existing conservative annual comparison retained, with comparability gates and pending outcomes. No claim of a complete four-quarter promise history. |
| Quarterly numbers versus prior quarter/year | Existing verified tables and omissions retained. Four prepared tables have 3/3/3/2 metrics; INFY has verified YoY but no verified QoQ. Fresh arbitrary-layout extraction is not certified. |
| Free to use without a model key | Published and verified: the hosted app reports `keyless`, makes no model calls, and serves extracts, saved research and the notebook. Optional synthesis uses operator-selected credentials and account quotas. |
| Options beyond Gemini | Groq and free-only OpenRouter adapters and operator setup are implemented. Real-key access and source-level answer quality for these new providers are unverified. |
| Live prices refresh every few minutes | **Not met as a measured cadence.** The workflow is scheduled every five minutes, but GitHub ran it hours apart on 3 to 4 November (19:51Z, 00:18Z, 06:43Z; plus manual runs). The page shows the feed's real check time and each row's trading date, so staleness is visible. Public Yahoo data, not an intraday or licensed real-time feed. |
| Phone access without login | Responsive live and static builds are published at the existing URLs. 21 browser layout checks (7 views at 360, 390 and 430 px) passed on the hosted app; this is emulation, not a physical phone. A real-device open of both URLs remains an owner check. |

## Verification and limits

- The final backend suite passed **210 tests**, with one existing Starlette/AnyIO deprecation warning.
- Live and static production builds passed. A GitHub Pages bundle with `/finn-enam/` asset paths
  and the existing live-app/live-price URLs is prepared under ignored `tmp/practical_review/`.
- Real-app layout checks passed on five views at **360, 390 and 430 CSS pixels**: research home,
  current Review, company, saved brief and notebook. No page-wide overflow or visible action
  control below the 43 px rounding-tolerance check was found. This is not physical-phone testing.
- A saved Infosys claim opened its annual report at PDF p.337 with publication proof and a content
  hash. Closing the evidence sheet restored focus. A saved cited point and follow-up note survived
  a real page reload in the notebook. The final two-page quote group was saved through the UI;
  its Markdown download retained both pages, publication time, original URLs, hashes and the earlier
  personal note. A completed follow-up also remained completed after reload.
- A real current NSE check retrieved **49 valid recent announcement records** across the 15-holding
  portfolio in about 12 seconds on the local network. **14/15** holding checks were fully verified;
  SUNPHARMA retained eight valid records but one additional record failed validation, so its check
  remained explicitly partial. This does not certify access from Render's datacenter network.
- A fresh current Infosys run discovered its FY2025-26 annual report and Q1/Q2 FY2026-27 call
  transcripts. The newest transcript's dated NSE publication was 28 October 2026. A focused guidance
  question returned five source highlights; **5/5** were exact substrings of their own stored
  passages. Its guidance/assumptions cross a PDF page break, and both passages remain cited together.
  This checks one real question and publisher layout, not broad research accuracy.
- Six supplementary final-layout checks covered the new context-linked brief and the full notebook
  at 360/390/430 CSS pixels, with actual viewport widths verified. Both retained the same overflow
  and action-size checks. The final static bundle loaded under `/finn-enam/`, name search worked,
  and a question containing `&` reached the receiving local live app intact without auto-running.
- The default restricted execution network could not complete the NSE check; the normal-network
  test did. That distinction is preserved in the ignored audit reports instead of blaming the app
  or claiming an inaccessible source was checked successfully.
- All app tests and manual preview runs selected keyless mode with model keys disabled. No new
  account, key, charge, paid resource, push, deployment or submission was made by this pass.
- New source/quote checks, copied databases and UI measurements are in ignored
  `tmp/practical_review/`. Earlier snapshot demonstrations retain their actual generation dates.

For provider setup, see [FREE_RESOURCES.md](FREE_RESOURCES.md). For publication order and the
existing link configuration, see [DEPLOY_FREE.md](DEPLOY_FREE.md).

## Hosted publication and verification (Claude Code, 4 November 2026)

Published to the existing destinations: source `main` and the Render service (auto-deploy from
`main`), and the GitHub Pages `gh-pages` branch. Rollback references: `main` `472813c` and
`gh-pages` `d1b5bc1`. Final published revisions are recorded in `BUILD_STATUS.md`.

**Passed on the public Render app (keyless, no model calls):**
- `/api/health`: `keyless`, 28-document seed corpus intact, `capabilities.current_source_research=true`.
- Three genuine saved briefs listed; a saved Infosys evidence sheet opened with proof and hash;
  Escape closed it and restored focus; the cached annual-report PDF streamed.
- Explicit seven-day current check from Render's datacenter: 14/15 holdings validated, 53
  announcements, SUNPHARMA left visibly partial (one record failed validation); repeat served from
  the 15-minute cache at its original timestamps. The Review page names the failed holding.
- "Read & research filing" for a Sun Pharma results notice and a focused current Infosys guidance
  question. The Infosys brief led with the 28 October 2026 call (revenue guidance 1% to 2% constant
  currency; operating margin 20% to 22%) with the assumptions passage cited as grouped context;
  5/5 highlights were exact substrings of their cited passages (checked through the evidence API).
- Identical question reuse (`reused: true`); an unsupported topic now abstains (below).
- Static-to-live handoff: the live app received the symbol and a question containing `&` intact and
  made zero research requests until the explicit "Run this question" click.
- Notebook on the hosted app: cited two-page quote saved, personal note added, reload kept it,
  marked followed up, Markdown export kept both PDF pages, speaker, publication time, passage ids,
  URL, SHA-256, evidence cutoff and the question.
- 21 layout checks (7 views at 360, 390 and 430 px): no page overflow, no tap target under 40 px.

**Defects found by this verification and fixed (216 backend tests now pass):**
1. A question about topics in no stored source (a lunar data centre, underwater cables) returned six
   confident pension-plan extracts matched on "plans" and "data". Retrieval now finds which question
   words appear in no eligible document, requires stronger overlap when some are missing, abstains
   when at least two are missing and they are half the question, and names them as a gap.
2. "What did management say about X" led with an annual-report note; management's own statements now
   come first.
3. Call-opening greetings were selected as highlights; they are excluded.
4. The 180-second research limit showed a raw `TimeoutError`; it now says documents read so far are
   saved and Retry continues.
5. A bare "—" in the market table now explains that the source did not report the previous session.

**Limits observed (not fixed):**
- The first current read of a company not in the seed exceeds the 180-second guard on the free
  CPU (Sun Pharma's 345-page annual report; Infosys). Progress is stored and the retry finished in
  about 25 seconds. Newly discovered documents vanish on redeploy (ephemeral store).
- Brief highlights outside the management section are keyword matches and can be loosely related
  (an annual-report ratio table, an older filing's impairment assumptions).
- Quotes are exact text from the PDF text layer and carry its spacing artefacts ("cauti ous").
- The price feed is best-effort (see the matrix); six holdings showed no daily change because Yahoo
  returned an empty 3 November bar for them.

**Not verified:** a real-key Groq/OpenRouter/Gemini answer; a physical phone; a container build on this
Mac (the Render build is the build evidence). No provider key was used, no account was created and no
charge was incurred.
