from __future__ import annotations

from datetime import date

import httpx

from finn.sources import nse
from finn.sources import xbrl
from finn.sources.fetch import Fetcher


XBRLI = "http://www.xbrl.org/2003/instance"
INR_NS = "http://www.xbrl.org/2003/iso4217"
GAAP = "https://www.nseindia.com/xbrl/ind-as/2026"


def _context(ref: str, start: str | None = None, end: str | None = None, *, instant: bool = False,
             dimension: bool = False) -> str:
    period = f"<xbrli:instant>{end}</xbrli:instant>" if instant else f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>"
    segment = '<xbrli:segment><xbrldi:explicitMember dimension="ex:RegionAxis">ex:WestMember</xbrldi:explicitMember></xbrli:segment>' if dimension else ""
    return (f'<xbrli:context id="{ref}"><xbrli:entity><xbrli:identifier scheme="urn:test">INE000T01011</xbrli:identifier>{segment}</xbrli:entity>'
            f"<xbrli:period>{period}</xbrli:period></xbrli:context>")


def _fact(name: str, value: int, context: str) -> str:
    return f'<in:{name} contextRef="{context}" unitRef="INR" decimals="-3">{value}</in:{name}>'


def _xbrl(period_end: str, revenue: int, expenses: int, finance: int, depreciation: int,
          pbt: int, pat: int, *, bank: bool = False) -> bytes:
    end = date.fromisoformat(period_end)
    quarter_start = {3: "01-01", 6: "04-01", 9: "07-01", 12: "10-01"}[end.month]
    qstart = f"{end.year}-{quarter_start}"
    march = f"{end.year}-03-31" if end.month > 3 else f"{end.year - 1}-03-31"
    items = [_context("q", qstart, period_end), _context("ytd", f"{end.year - (1 if end.month <= 3 else 0)}-04-01", period_end),
             _context("now", end=period_end, instant=True), _context("march", end=march, instant=True),
             _context("segment", qstart, period_end, dimension=True)]
    if bank:
        quarter_facts = [_fact("InterestEarned", revenue, "q"), _fact("InterestExpended", expenses, "q"),
                         _fact("OperatingProfitBeforeProvisionAndContingencies", finance, "q"),
                         _fact("ProvisionsOtherThanTaxAndContingencies", depreciation, "q"),
                         _fact("ProfitLossFromOrdinaryActivitiesBeforeTax", pbt, "q"), _fact("ProfitLossForThePeriod", pat, "q")]
    else:
        quarter_facts = [_fact("RevenueFromOperations", revenue, "q"), _fact("Expenses", expenses, "q"),
                         _fact("FinanceCosts", finance, "q"),
                         _fact("DepreciationDepletionAndAmortisationExpense", depreciation, "q"),
                         _fact("ProfitBeforeTax", pbt, "q"), _fact("ProfitLossForPeriod", pat, "q")]
    ytd_facts = [_fact("RevenueFromOperations", revenue * 2, "ytd"), _fact("Expenses", expenses * 2, "ytd"),
                 _fact("FinanceCosts", finance * 2, "ytd"),
                 _fact("DepreciationDepletionAndAmortisationExpense", depreciation * 2, "ytd"),
                 _fact("CashFlowsFromUsedInOperatingActivities", 40_000_000_000, "ytd"),
                 _fact("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", 2_000_000_000, "ytd"),
                 _fact("ProfitLossForPeriod", 36_000_000_000, "ytd")]
    if end.month == 6:
        # Q1 is itself year-to-date. A second P&L measurement with different
        # values for the identical duration would be contradictory.
        ytd_facts = ytd_facts[4:6]
    balance_facts = []
    for context, base in (("now", 1_000_000_000_000), ("march", 900_000_000_000)):
        balance_facts.extend([_fact("Assets", base, context), _fact("Equity", base // 2, context),
                              _fact("Liabilities", base // 2, context), _fact("CashAndCashEquivalents", base // 10, context),
                              _fact("Borrowings", base // 20, context)])
    injection = _fact("RevenueFromOperations", 999_999_000_000, "segment")
    xml = (f'<xbrli:xbrl xmlns:xbrli="{XBRLI}" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="{INR_NS}" xmlns:in="{GAAP}" xmlns:ex="urn:example">'
           f'{"".join(items)}<xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>'
           f'{"".join(quarter_facts + ytd_facts + balance_facts)}{injection}</xbrli:xbrl>')
    return xml.encode()


def _feed_row(end: str, path: str, seq: str) -> dict:
    end_date = date.fromisoformat(end)
    return {"symbol": "TESTCO", "type": "Integrated Filing- Financials", "type_Sub": "Original",
            "consolidated": "Consolidated", "qe_Date": end_date.strftime("%d-%b-%Y"),
            "creation_Date": "23-Oct-2026 20:20:00", "broadcast_Date": "23-Oct-2026 20:21:00",
            "seq_Id": seq, "xbrl": f"https://nsearchives.nseindia.com/corporate/xbrl/{path}.xml",
            "pdf_attach": f"https://nsearchives.nseindia.com/corporate/{path}.pdf"}


def test_parse_xbrl_keeps_exact_non_dimensional_facts_and_scales_inline_values():
    xml = (f'<xbrli:xbrl xmlns:xbrli="{XBRLI}" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="{INR_NS}" xmlns:in="{GAAP}" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:ex="urn:example">'
           f'{_context("q", "2026-07-01", "2026-09-30")}{_context("segment", "2026-07-01", "2026-09-30", dimension=True)}'
           '<xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>'
           '<in:RevenueFromOperations contextRef="q" unitRef="INR" decimals="-3">492440000000</in:RevenueFromOperations>'
           '<in:RevenueFromOperations contextRef="segment" unitRef="INR">999999999999</in:RevenueFromOperations>'
           '<ix:nonFraction name="in:ProfitBeforeTax" contextRef="q" unitRef="INR" scale="6" decimals="-3">110.63</ix:nonFraction>'
           '</xbrli:xbrl>').encode()
    parsed = xbrl.parse_xbrl(xml)
    assert parsed["fact_count"] == 2
    assert {fact["concept"]: fact["value_text"] for fact in parsed["facts"]} == {
        "RevenueFromOperations": "492440000000", "ProfitBeforeTax": "110630000"
    }


def test_refresh_builds_deterministic_quarterly_scorecard_and_pull_cards(env, monkeypatch):
    settings, store, master_fetcher, _ = env
    assert nse.refresh_security_master(store, master_fetcher)[0]
    company = nse.resolve_company(store, "TESTCO")
    rows = [
        _feed_row("2025-09-30", "period_2025q2", "1"),
        _feed_row("2026-03-31", "period_2025fy", "5"),
        _feed_row("2026-06-30", "period_2026q1", "2"),
        _feed_row("2026-09-30", "period_2026q2", "3"),
    ]
    docs = {
        rows[0]["xbrl"]: _xbrl("2025-09-30", 80_000_000_000, 60_000_000_000, 1_000_000_000, 2_000_000_000, 20_000_000_000, 16_000_000_000),
        rows[1]["xbrl"]: _xbrl("2026-03-31", 70_000_000_000, 60_000_000_000, 1_000_000_000, 2_000_000_000, 15_000_000_000, 12_000_000_000),
        rows[2]["xbrl"]: _xbrl("2026-06-30", 90_000_000_000, 68_000_000_000, 1_400_000_000, 2_400_000_000, 22_000_000_000, 17_000_000_000),
        rows[3]["xbrl"]: _xbrl("2026-09-30", 100_000_000_000, 75_000_000_000, 1_500_000_000, 2_500_000_000, 25_000_000_000, 18_000_000_000),
    }
    def handler(request):
        if request.url.path == "/api/integrated-filing-results":
            return httpx.Response(200, json={"data": rows, "size": len(rows), "page": 0, "totalCount": len(rows)})
        body = docs.get(str(request.url))
        return httpx.Response(200, content=body, headers={"content-type": "application/xml"}) if body else httpx.Response(404)
    fetcher = Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval_s=0)
    report = xbrl.refresh_company(store, fetcher, company, quarters=8)
    assert report["state"] == "completed" and report["stored"] == 4
    score = xbrl.build_scorecard(store, company, basis="consolidated")
    metrics = {row["key"]: row for row in score["metrics"]}
    assert metrics["revenue"]["current"]["value_crore"] == "10000"
    assert metrics["revenue"]["qoq_pct"] == 11.1 and metrics["revenue"]["yoy_pct"] == 25.0
    assert metrics["ebitda"]["current"]["value_crore"] == "2900"
    assert metrics["ebitda"]["derivation"] and metrics["ebitda"]["source"]["xbrl_hash"]
    assert metrics["revenue"]["comparative_sources"]["previous_quarter"]["pdf_url"].endswith("period_2026q1.pdf")
    cards = xbrl.build_financial_cards(store, company)
    balance = {row["key"]: row for row in cards["cards"]["balance_sheet"]["items"]}
    assert balance["assets"]["current"]["value_crore"] == "100000"
    assert balance["assets"]["previous_march"]["value_crore"] == "90000"
    assert cards["cards"]["cash_quality"]["free_cash_flow"]["value_crore"] == "3800"
    assert cards["cards"]["cash_quality"]["cash_conversion_pct"] == 111.1
    summary = {row["key"]: row for row in cards["cards"]["financial_snapshot"]["items"]}
    assert summary["revenue"]["value"]["value_crore"] == "10000"
    assert summary["ebitda"]["value"]["value"] == "29.0" and summary["pat"]["value"]["value"] == "18.0"
    assert balance["debt_to_equity"]["value"] == "0.10" and balance["net_cash_debt"]["value"] == "5000"
    trajectory = cards["cards"]["trajectory"]["items"]
    assert len(trajectory) == 4
    assert trajectory[0]["revenue"]["value_crore"] == "10000" and trajectory[0]["ebitda_margin_pct"] == 29.0
    annual = next(row["annual"] for row in trajectory if row["period_end"] == "2026-03-31")
    assert annual["revenue"]["value_crore"] == "14000" and annual["source"]["xbrl_hash"]
    historical = xbrl.build_scorecard(store, company, cutoff_utc="2025-04-30T23:59:59+05:30")
    assert not historical["available"]
    assert xbrl.build_scorecard(store, company, basis="standalone")["available"] is False


def test_bank_scorecard_uses_bank_tags_and_never_labels_ebitda(env):
    settings, store, master_fetcher, _ = env
    assert nse.refresh_security_master(store, master_fetcher)[0]
    company = nse.resolve_company(store, "TESTCO")
    row = _feed_row("2026-09-30", "bank_2026q2", "4")
    xml = _xbrl("2026-09-30", 951_316_300_000, 506_674_300_000, 328_715_400_000,
                42_090_000_000, 110_630_000_000, 78_380_000_000, bank=True)
    # Store a verified feed/XBRL version through the same ingestion path.
    def handler(request):
        if request.url.path == "/api/integrated-filing-results":
            return httpx.Response(200, json={"data": [row], "size": 1, "page": 0, "totalCount": 1})
        return httpx.Response(200, content=xml, headers={"content-type": "application/xml"})
    fetcher = Fetcher(store, client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval_s=0)
    xbrl.refresh_company(store, fetcher, company, quarters=1)
    score = xbrl.build_scorecard(store, company)
    metrics = {item["key"]: item for item in score["metrics"]}
    assert score["bank_taxonomy"] is True
    assert "ebitda" not in metrics and metrics["net_interest_income"]["current"]["value_crore"] == "44464.2"
    assert metrics["operating_profit_before_provisions"]["current"]["value_crore"] == "32871.54"
    assert "pbt" in metrics and "pat" in metrics


def test_infy_oracle_tags_and_revision_cutoff(env):
    _, store, master_fetcher, _ = env
    assert nse.refresh_security_master(store, master_fetcher)[0]
    company = nse.resolve_company(store, "TESTCO")
    original = _feed_row("2026-09-30", "original", "1")
    revision = {**_feed_row("2026-09-30", "revision", "2"), "type_Sub": "Revision",
                "broadcast_Date": "24-Oct-2026 20:21:00"}
    invalid = _feed_row("2026-06-30", "invalid", "3")
    original_xml = _xbrl("2026-09-30", 492_440_000_000, 390_290_000_000, 1_150_000_000,
                        13_590_000_000, 110_630_000_000, 78_380_000_000)
    revised_xml = original_xml.replace(b"492440000000", b"492450000000")
    wrong_xml = _xbrl("2026-06-30", 1, 1, 1, 1, 1, 1).replace(b"INE000T01011", b"INE000O01011")

    def handler(request):
        if "integrated-filing-results" in request.url.path:
            return httpx.Response(200, json={"data": [original, revision, invalid], "totalCount": 3})
        bodies = {"original.xml": original_xml, "revision.xml": revised_xml, "invalid.xml": wrong_xml}
        return httpx.Response(200, content=bodies[request.url.path.rsplit("/", 1)[-1]])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = xbrl.refresh_company(store, Fetcher(store, client=client, min_interval_s=0), company)
    assert report["stored"] == 2
    assert report["issues"][0]["state"] == "identity_unverified"
    before = xbrl.build_scorecard(store, company, cutoff_utc="2026-10-23T21:00:00+05:30")
    values = {metric["key"]: metric["current"]["value_crore"] for metric in before["metrics"]}
    assert values == {"revenue": "49244", "ebitda": "11689", "pbt": "11063", "pat": "7838"}
    assert before["source"]["revision"] == "Original"
    current = xbrl.scorecard_for_attachment(store, company, revision["pdf_attach"].replace(".com", ".in"), None)
    assert current["source"]["revision"] == "Revision"
    assert current["metrics"][0]["current"]["value_crore"] == "49245"
    assert xbrl.scorecard_for_attachment(store, company, "https://example.org/corporate/revision.pdf", None) is None


def test_date_only_publication_is_conservative():
    stamp, raw = xbrl._publication_stamp({"broadcast_Date": "2025-04-30"})
    assert raw == "2025-04-30"
    assert stamp == "2025-04-30T18:29:59+00:00"


def test_auto_basis_picks_newest_quarter_within_the_cutoff(env):
    _, store, master_fetcher, _ = env
    assert nse.refresh_security_master(store, master_fetcher)[0]
    company = nse.resolve_company(store, "TESTCO")
    rows = [_feed_row("2026-06-30", "old", "1"),
            {**_feed_row("2026-09-30", "new", "2"), "consolidated": "Standalone",
             "broadcast_Date": "24-Oct-2026 20:21:00", "creation_Date": "24-Oct-2026 20:20:00"}]

    def handler(request):
        if "integrated-filing-results" in request.url.path:
            return httpx.Response(200, json={"data": rows, "totalCount": len(rows)})
        period = "2026-06-30" if request.url.path.endswith("/old.xml") else "2026-09-30"
        return httpx.Response(200, content=_xbrl(period, 100, 50, 2, 3, 50, 30))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        xbrl.refresh_company(store, Fetcher(store, client=client, min_interval_s=0), company)

    current = xbrl.build_financial_cards(store, company, basis="auto")
    assert current["basis"] == "standalone"
    assert current["periods_by_basis"] == {"consolidated": "2026-06-30", "standalone": "2026-09-30"}
    historical = xbrl.build_financial_cards(store, company, basis="auto", cutoff_utc="2026-10-23T20:22:00+05:30")
    assert historical["basis"] == "consolidated"
    assert historical["periods_by_basis"]["standalone"] is None
