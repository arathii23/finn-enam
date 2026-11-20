# FINN - primary-source investor research

A mobile-first workflow for following Indian listed companies: notice a filing, inspect its source, ask a focused question, and save what matters.

### [Open the main app](https://arathii23.github.io/finn-enam/)

[Live research app](https://finn-mow9.onrender.com) · [Phone alerts](https://arathii23.github.io/finn-enam/#/alerts) · [Source and verification notes](docs/README.md)

<a href="https://arathii23.github.io/finn-enam/">
  <img src="docs/assets/finn-qr.png" alt="Scan to open the FINN main app on your phone" width="222" height="222">
</a>

**Scan with your phone camera, or use the app link above.** The web app opens without a login. Optional phone notifications use the free ntfy app.

## Try it in a minute

1. **Review:** open a filing from the 15-company portfolio and inspect the original exchange source. Use "Since your last visit" to resume your review.
2. **Research:** open a company or saved brief, ask a focused question in the live app, and follow the evidence to its passage and PDF page.
3. **Results:** inspect the quarter, standalone/consolidated basis, calculations, revisions and source links.
4. **Alerts:** choose companies and filing types, connect ntfy, receive a test and enable personal notifications.

## What I built

| Investor task | FINN's workflow |
| --- | --- |
| Keep up with holdings | Recent-filings digest, company/type filters, priority tiers and source-check coverage |
| Check a claim | Annual reports, earnings-call transcripts and exchange filings with exact citations and visible gaps |
| Understand results | Quarterly comparisons, labelled derived figures, bank-specific metrics and PDF/XBRL discrepancy checks |
| Follow relevant updates | Personal company/type alerts, durable preferences, pause/resume, recovery and deletion |
| Return to research | Browser-local cited notebook, notes, follow-up status and Markdown export |
| Inspect reliability | Source dates, publication-cutoff rules, Trust view and dated verification records |

The public deployment is **keyless by default**. Code selects relevant source quotations, ranks filings and performs arithmetic. Optional model providers are configured on the server; a reviewer needs no API key.

**Repository checks (21 November 2026):** 272 backend tests passed; live and Pages production builds passed; the QR image decoded to the main-app URL.

## Data freshness and scope

The main app includes published snapshots and feeds; its dates and coverage show what was actually checked. The live research app supports explicit current-source checks. Historical replay is separate and retains its **30 April 2025** evidence cutoff.

Phone test requests are checked about every five minutes and filing checks are due about every thirty minutes. Free hosting, source failures and service limits can delay updates. Price data is an end-of-day snapshot, not a streaming intraday feed.

## Explore the repository

The project is grouped into **two main folders**, plus GitHub's workflow folder:

```text
app/
  backend/       Python / FastAPI, source retrieval, research and tests
  frontend/      React / TypeScript mobile interface
  manifests/     Portfolio and historical replay metadata
  scripts/       Verification, snapshots, data publishing and alert tools
docs/
  README.md      Guide to the documentation
  DEVELOPMENT.md Local setup, checks and architecture
  assets/        Main-app QR code
  assignment/    Original challenge briefs
  planning/      Feasibility review, specification and source-access audit
.github/
  workflows/     Automated checks and data jobs
```

[Run it locally](docs/DEVELOPMENT.md) · [Phone-alert setup and evidence](docs/PHONE_ALERTS_PILOT.md) · [Results verification](docs/FINN_V2_VERIFICATION.md) · [Build checkpoints](docs/BUILD_STATUS.md)

Docker and Render configuration remain at the repository root. Private credentials, subscriber data, local corpus files and submission exports are excluded from Git.
