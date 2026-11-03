# FINN final product and submission-readiness plan

31 October 2026 (IST). Plan derived from both assignment PDFs and the current application.
This is an execution plan, not evidence that the checks below have passed. See the latest
`BUILD_STATUS.md` entry for measured results.

## What the brief actually asks

The main brief evaluates building ability, creativity, product sense, judgment and architecture.
It sets a qualitative bar: concise, useful, interactive, mobile-first, primary-source-grounded and
cost-conscious. It does **not** provide a numerical scorecard or weights. Do not invent one.

- Required deliverables: usable mobile prototype, repository, authentic AI build conversations and a
  covering email describing choices, trade-offs, omissions and next steps. Deadline: 1 November 2026.
- Product scope: Push and Pull; 15–20 mixed portfolio companies; a handful of research demonstrations
  (say 3–5), with a generic engine that can work on unfamiliar NSE tickers where data exists.
  Research examples may be inside or outside the portfolio.
- Three working inputs: EOD price/volume, exchange announcements/filings, annual reports/transcripts.
- Pull discipline: primary sources only; no news, broker commentary or company facts from model memory.
- The announcement categories are a reference. The eight Pull outputs are explicitly a **menu**.
  The two Push examples and four-quarter narrative example are illustrations of valuable depth,
  not a mandate to generate unsupported content or build every glossary term into the UI.
- The four named quarterly metrics are Revenue, EBITDA, PBT and PAT. Missing or unreadable metrics
  must be identified, not guessed. Financial basis, units, periods and comparable denominators matter.

## Criteria and acceptance matrix

| Criterion | Baseline observation | Acceptance check |
|---|---|---|
| Financial trust | Evidence plumbing exists; matching strings do not prove semantic correctness | Unknown citations, unsupported numbers/labels, mixed bases and misaligned periods abstain; inspect representative real values against their own source pages |
| Portfolio and data | 15 holdings populated; source coverage varies | Identity and coverage visible for every holding; missing sources never appear as an all-clear |
| Chosen digest period | Fixed historical filing window | User can select recent replay periods/full window; UI labels historical cutoff and selected period; events and counts use the same range |
| Filtering and attention | Tiers exist, but the default feed exposes many records | Filter attention/category/company, progressively reveal extra filings, and keep all records reachable |
| Routine disclosure | “Show routine” currently reveals explanation rather than records | Toggle reveals actual routine filings and their available attachment links |
| EOD alerts | Configurable in-app flags, not a delivered notification service | Thresholds have visible applied state; zero is preserved; session/baseline dates are clear; no causal claim or false real-time delivery claim |
| Quarterly first cut | Selected cached tables; EBITDA honestly absent | Show current and comparable prior values, units/basis, QoQ/YoY, evidence and explicit omissions; never derive unsupported EBITDA |
| Management background | Two primary filing profiles; both predate digest | Appointment/profile evidence stays separate; roles/dates and earlier filing context remain visible; unsupported layouts omit |
| Narrative vs numbers | Useful annual guidance/outcome comparison from available call history | Label available history and annual scope; do not imply a completed last-four-quarter tracker; metric/year/entity/currency gates hold |
| Research questions | Backend supports questions, UI does not expose them | User can enter a company-specific question and act on a suggested follow-up; errors preserve context |
| Saved research | Three completed research demos exist but are hard to discover | Open labelled saved results directly without generation; show generation date/cutoff and distinguish a fresh request |
| Generic research | Generic discovery implemented; real cold-source check still needed | Two non-demo tickers start with master data only, discover dated primary records or report precise bounded gaps; no prefilled URLs |
| Professional usability | Existing responsive checks; workflow still has friction | Review → company → saved research → exact evidence → back works without losing context; clear loading/empty/error states and keyboard/touch access |
| Efficiency | Small ledger, model routing, caps and caches | Reading saved results makes zero model calls; cap remains $5 total/$0.25 per job; cache/refresh behavior is explicit |
| Submission access | Local app verified; public access and reviewer links pending | Hosted/mobile link, persistence, physical phone, approved repo/push and authentic history links verified before submission |

## Execution order and scope

1. **Financial trust first.** Tighten deterministic quarterly validation around labels, units, basis,
   period alignment and number boundaries; bind each presented metric to its own evidence. Preserve
   existing audited demonstrations only when they meet the tightened contract. Add meaningful
   regressions for the actual failure modes. Show missing metrics and the absolute prior values.
2. **Make Review a professional daily workflow.** Add a chosen historical period, attention/category/
   company filters, shorter source-derived subjects, progressive disclosure, actual routine records,
   and clear counts. Persist useful preferences while keeping the applied state honest. Keep evidence
   and company context one action away. Do not add email/SMS/notification delivery in this pass.
3. **Make research discoverable and intentional.** Surface the existing saved research, label it as
   saved, expose custom questions and actionable follow-ups, and avoid surprise generation from
   read-only navigation. Keep the three genuine demonstrations; breadth is secondary to reliability.
4. **Verify complete journeys.** Full backend suite, official frontend build, evidence/source checks,
   360/390/430 CSS-pixel browser checks, keyboard/touch checks, copied-store restart smoke and two
   bounded keyless cold-source checks. Record actual outcomes and ledger delta, including failures.
5. **Reconcile the submission package.** Update current-state documentation and the unsent covering
   draft. It must no longer describe full portfolio ingestion or Numbers vs Narrative as future work.
   Preserve all original conversations and the ignored source/result store.
6. **Shipping gates remain separate.** User approval still precedes paid hosting, public deployment,
   repository publication/push and sending the submission. A local polish pass does not establish
   hosted source access, persistence, physical-phone behavior or evaluator access.

Avoid adding all eight research sections, speculative financial conclusions, outside biographies,
intraday features or a broad redesign merely to increase apparent completeness. The brief explicitly
prefers a focused reliable workflow. No physical-user study or time-saving measurement is claimed.

## Proposed no-spend restart/read-only smoke

Do not run the existing `scripts/smoke.py` unchanged against production data: it submits a research
job. Use a separate audit directory and only GET requests. The service may update identity/startup
metadata in its copied SQLite; it must not modify the production database or source files.

Preparation, from the repo root:

```bash
.venv/bin/python - <<'PY'
import sqlite3, tempfile
from pathlib import Path
root = Path.cwd()
audit = Path(tempfile.mkdtemp(prefix='finn-readonly-', dir='/private/tmp'))
source = sqlite3.connect(f'file:{root / "data/finn.sqlite3"}?mode=ro', uri=True)
dest = sqlite3.connect(audit / 'finn.sqlite3')
source.backup(dest)  # consistent snapshot, including committed WAL state
dest.close(); source.close()
(audit / 'sources').symlink_to(root / 'data/sources', target_is_directory=True)
print(audit)
PY
```

Copy the printed audit path into `FINN_DATA_DIR`; inspect port 8765 before starting. Root runs the
server, with both model keys explicitly empty so `.env` cannot restore them:

```bash
cd backend
env -u ANTHROPIC_BASE_URL OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  FINN_DATA_DIR=/private/tmp/finn-readonly-REPLACE \
  ../.venv/bin/python -m finn serve --host 127.0.0.1 --port 8765
```

Use HTTP timeouts of 10 seconds and at most 30 seconds for startup. Select an existing completed
job from the copied database, then GET health, the frontend, company overview, portfolio, management,
narrative, cached quarterly data, the saved job, one cited passage and its cached PDF. Check PDF bytes
start `%PDF-` and their SHA-256 equals document metadata. Do not POST research or call ingestion.
Save canonical saved-job/result and PDF hashes, stop/restart the same isolated server, repeat the GETs
and compare. Assert audit `model_calls` count and total match the pre-test copy, and independently
check production `model_calls` is unchanged. Stop this audit server when finished. A successful local
restart does not certify the proposed host's persistent disk.

## Proposed bounded, keyless cold-source check

Local master was read without network and contains:

| Symbol | Legal name | Series | ISIN |
|---|---|---|---|
| POLYCAB | Polycab India Limited | EQ | INE455K01017 |
| ASIANPAINT | Asian Paints Limited | EQ | INE021A01026 |

Use a separate empty store per company; copy **only** `security_master` rows, no documents,
announcements, passages, jobs, source files or derived cache. Resolve identity from that master,
then invoke the existing generic `discover_company_sources` directly. Do not add document URLs to
the manifest or generate prose. Keep the replay cutoff so later documents cannot leak into the demo.

Exact runner proposal, from the repo root (executes network reads only when root chooses to run it):

```bash
env -u ANTHROPIC_BASE_URL OPENAI_API_KEY='' ANTHROPIC_API_KEY='' \
  PYTHONPATH="$PWD/backend" .venv/bin/python - <<'PY'
import os, subprocess, sys, tempfile
from pathlib import Path

root = Path.cwd()
audit = Path(tempfile.mkdtemp(prefix='finn-cold-', dir='/private/tmp'))
child = r'''
import json, sqlite3, sys, time
from dataclasses import replace
from pathlib import Path
import httpx
from finn.config import get_settings
from finn.db import Store
from finn.discovery import discover_company_sources
from finn.replay import classify_versions, load_manifest
from finn.sources import nse
from finn.sources.fetch import BROWSER_HEADERS, Fetcher

root, audit, symbol = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
s = replace(get_settings(), data_dir=audit,
            openai_api_key=None, anthropic_api_key=None)
assert not s.model_configured
store = Store(s.db_path, s.files_dir)
source = sqlite3.connect(f'file:{root / "data/finn.sqlite3"}?mode=ro', uri=True)
source.row_factory = sqlite3.Row
for row in source.execute('SELECT * FROM security_master'):
    store.insert('security_master', dict(row), mode='INSERT OR REPLACE')
source.close()
assert not store.query('SELECT * FROM document_versions')
company = nse.resolve_company(store, symbol)
cutoff = load_manifest(s.manifest_path).cutoff_utc
client = httpx.Client(headers=BROWSER_HEADERS,
                      timeout=httpx.Timeout(10.0, connect=5.0), follow_redirects=False)
fetcher = Fetcher(store, max_bytes=s.max_download_bytes, client=client, min_interval_s=0.5)
try:
    report = discover_company_sources(store, fetcher, s, company, cutoff,
                                     progress=lambda stage: None,
                                     deadline=time.monotonic() + 90)
finally:
    fetcher.close()
eligible, excluded = classify_versions(store, company.company_id, 'replay', cutoff)
report['audit'] = {
    'identity': company.model_dump(),
    'eligible_types': sorted({v['doc_type'] for v in eligible}),
    'eligible_count': len(eligible), 'excluded_count': len(excluded),
    'model_calls': store.query_one('SELECT COUNT(*) AS n FROM model_calls')['n'],
}
assert report['audit']['model_calls'] == 0
(audit / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(json.dumps(report['audit'], ensure_ascii=False))
'''

for symbol in ('POLYCAB', 'ASIANPAINT'):
    target = audit / symbol
    try:
        result = subprocess.run([sys.executable, '-c', child, str(root), str(target), symbol],
                                env=os.environ.copy(), capture_output=True, text=True,
                                timeout=150)
        print(symbol, 'exit', result.returncode, result.stdout, result.stderr[-1000:])
    except subprocess.TimeoutExpired:
        print(symbol, 'hard timeout after 150s; no success claim')
print('Audit artifacts:', audit)
PY
```

Bounds: 90-second cooperative discovery deadline, 150-second hard process limit per company,
10-second HTTP timeout (5-second connect), existing four 90-day announcement windows, at most three
annual-report downloads and three transcript downloads, existing download/page caps. The hard bound
also covers an in-flight parse that cannot observe the cooperative deadline. A partial result or
blocked exchange is an observed gap, not proof the generic engine succeeded. Success requires dated,
identity-checked eligible annual-report and transcript passages; source discovery alone is not a
model-reasoning or hosted-access certification. This proposal has not been executed by the planning
agent and makes no model call.

## Submission gates that remain unrun

Docker and Podman binaries are unavailable in this environment; container build/run is **unrun**.
Public hosting, hosted source access, hosted restart/persistence, funded API continuity through
evaluation, a physical-phone run, reviewer access to repository/conversation links and the final
submission are separate pending gates. Do not mark them passed from browser viewport checks.
