# FINN v2 local verification · 17 November 2026 (IST)

## Exchange access

The Mac retrieved 28 announcement records across all 15 holdings for 11–17 November in 17 seconds. The security-master CSV and 17 April 2025 bhavcopy CSV each returned HTTP 200 from `nsearchives.nseindia.com` without a redirect. The calendar API and the board-meeting API redirected from `.com` to `.in`. The corporate actions API also returned usable JSON on `.in`.

## Results coverage and timing

The keyless exchange run stored 212 verified filing versions and 34,673 non-dimensional numeric facts in an isolated working copy. The table shows the newest eligible quarter on each basis and wall-clock seconds for the exchange retrieval. A scorecard is available for September 2026 for every holding on at least one basis. CERA has September 2026 standalone; its newest available consolidated quarter is June 2025. The UI labels the basis and points to the newer filing. Two older LT XML URLs returned 404 on both archive hosts. Its September 2026 scorecard is available.

| Holding | Consolidated | Standalone | Seconds |
|---|---|---|---:|
| INFY | Sep 2026 | Sep 2026 | 7.77 |
| HCLTECH | Sep 2026 | Sep 2026 | 9.30 |
| RELIANCE | Sep 2026 | Sep 2026 | 8.00 |
| HDFCBANK | Sep 2026 | Sep 2026 | 7.94 |
| ICICIBANK | Sep 2026 | Sep 2026 | 8.35 |
| BHARTIARTL | Sep 2026 | Sep 2026 | 9.97 |
| LT | Sep 2026 | Sep 2026 | 11.00 |
| MARUTI | Sep 2026 | Sep 2026 | 7.99 |
| HINDUNILVR | Sep 2026 | Sep 2026 | 8.01 |
| SUNPHARMA | Sep 2026 | Sep 2026 | 8.23 |
| ULTRACEMCO | Sep 2026 | Sep 2026 | 8.06 |
| TITAN | Sep 2026 | Sep 2026 | 7.97 |
| TRENT | Sep 2026 | Sep 2026 | 8.05 |
| ASTRAL | Sep 2026 | Sep 2026 | 8.55 |
| CERA | Jun 2025 | Sep 2026 | 5.69 |

The September 2026 reference checks reproduced Infosys revenue ₹49,244 crore, derived EBITDA ₹11,689 crore, PBT ₹11,063 crore and PAT ₹7,838 crore. HDFC Bank’s NII was ₹44,464.20 crore, operating profit before provisions ₹32,871.54 crore and provisions ₹4,209 crore. The dated evaluation JSON records the source URLs and SHA-256 hashes.

### March 2025 PDF comparison

Numeric pairs below are PDF / consolidated XBRL in crore. The Infosys PDF card does not label its basis. The HCLTech and UltraTech PDF cards leave currency unidentified. Consequently, equality here is numeric agreement and does not independently resolve those metadata gaps.

| Holding | Revenue | PBT | PAT |
|---|---:|---:|---:|
| INFY | 40,925 / 40,925 | 9,663 / 9,663 | 7,038 / 7,038 |
| HCLTECH | 30,246 / 30,246 | 5,735 / 5,735 | 4,309 / 4,309 |
| ULTRACEMCO | 23,063.32 / 23,063.32 | **3,100.84 / 3,111.61** | 2,474.79 / 2,474.79 |

UltraTech’s PBT differs by ₹10.77 crore. The company scorecard displays both values together when the PDF and XBRL cards cover the same quarter and basis. The XBRL value comes from its tagged PBT and no equivalence is assumed. [Infosys XBRL](https://nsearchives.nseindia.in/corporate/xbrl/INTEGRATED_FILING_INDAS_1417999_17042025113633_WEB.xml), [HCLTech XBRL](https://nsearchives.nseindia.in/corporate/xbrl/INTEGRATED_FILING_INDAS_1422697_22042025070125_WEB.xml), [UltraTech XBRL](https://nsearchives.nseindia.in/corporate/xbrl/INTEGRATED_FILING_INDAS_1426913_28042025082714_WEB.xml).

A valid integrated-results row frequently carries an XBRL file and an inline XBRL link without a PDF. The Review card joins by exact exchange attachment across the two host families. The original announcement remains accessible when there is no exact match.

## Alerts and calendar

The real `alerts --dry-run` checked all 15 holdings and listed four candidate filing alerts. The state file was absent after the run and no ntfy request was sent. The local calendar command consumed the three verified exchange endpoints and returned a valid calendar with zero upcoming portfolio events found in their returned lists. The exchange lists may be incomplete, so the calendar is an additional view of exchange entries.

After approval, add a private `NTFY_TOPIC` secret and subscribe to it in ntfy. Run the workflow manually with dry-run selected to verify its NSE probe and Render fallback, then run an approved test on the private topic. Verify arrival on the phone and compare it with the recorded exchange publication time. Set `FINN_ALERTS_ENABLED=1` only when ready to enable the schedule. After approving a public topic, use `scripts/make_qr.py --public-alert-topic TOPIC --out frontend/public` to build the public subscription link and QR code before building the site. ntfy.sh topics can be read or posted to by anyone who knows their name.

## Build and layout checks

- The keyless backend suite passed 233 tests. Both the live and static frontend builds passed.
- Chrome passed 24 layout checks across both builds at 360, 390 and 430 px. The checks covered Trust, Review and Alerts, the populated Infosys scorecard with expanded evidence, and the UltraTech comparison banner.
- Seed verification found 108 existing replay read models and the saved jobs unchanged. It checked 386 XBRL source timestamps against the 30 April 2025 replay cutoff and found no violations. It also checked 43 extracts for exactness.
- Workflow YAML parsed locally. GitHub runner execution, Render fallback, deployment and physical phone delivery were outside the local checks.

[Layout results](evaluation/2026-11-17/layout_report.json).

## Evaluation

The final dated run used the frozen seed plus the locally downloaded NSE XBRL records. The report retains the initial run and its two failures. One partially overlapping question still failed: a question about a Martian greenhouse matched genuine greenhouse text and carried a gap about the missing term. The six-sector evaluation therefore does not claim perfect relevance. The filing-instruction result covers the specific synthetic fixture.

[Final evaluation](evaluation/2026-11-17/README.md) · [Machine-readable report](evaluation/2026-11-17/eval_report.json) · [Initial run](evaluation/2026-11-17/initial_eval_report.json).
