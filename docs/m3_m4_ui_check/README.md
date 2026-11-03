# M3/M4 local browser verification — 31 October 2026

Actual locally served app and real stored primary-source data, not synthetic screens.
`layout_checks.json` records seven views at each of 360, 390 and 430 CSS pixels. Browser zoom was
1.3, so viewport overrides of 468/507/559 device pixels were used; `innerWidth` confirmed each
requested CSS width. Desktop scrollbar gutters remain visible. No physical phone was used.

Checks: no document-level horizontal overflow, no page error alerts, no rendered controls under
43.5 px (44 px CSS minimum with fractional rounding tolerance). Tables may scroll inside their own
container. Captured browser logs were empty. Screenshots are actual browser captures, including
the preview surface's unused space. CERA_430 shows the full appointment card.

The test server had model keys disabled. Management cards were recomputed deterministically from
stored filings. Quarterly tables and INFY research were previously generated/saved; no regeneration
was performed for these layout checks. Evidence checks exercised HDFC appointment p.1/profile p.2
and CERA profile p.2, including page-specific PDF links. Keyboard focus wrap, Escape and restoration
were checked on HDFC. Review thresholds 0/0 were applied, restored to 5/2, and Mark reviewed/Undo
was restored after the interaction check.
