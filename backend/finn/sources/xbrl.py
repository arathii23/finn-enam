"""Exchange integrated-filing XBRL retrieval and deterministic financial read models.

Only financial XBRL listed in NSE's symbol-filtered integrated-filing feed is
accepted. The exact feed row supplies the issuer, reporting quarter, version,
and exchange publication time. Facts with dimensional contexts are retained out
of this first cut; no values are inferred from prose or model output.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

from ..config import IST
from ..contracts import Company
from ..db import Store, sha256_bytes, utcnow
from . import nse
from .fetch import Fetcher, NSE_HOSTS, UnsafeURL, validate_public_https

INTEGRATED_RESULTS_API = "https://www.nseindia.com/api/integrated-filing-results"
PAGE_SIZE = 100
MAX_PAGES = 10
MAX_PERIODS_PER_BASIS = 8
PARSER_VERSION = "nse-xbrl-no-dimension-v1"
_INR_PER_CRORE = Decimal("10000000")


def integrated_filing_url(symbol: str, page: int = 0, size: int = PAGE_SIZE) -> str:
    if not re.fullmatch(r"[A-Z0-9&-]{1,20}", symbol.upper()):
        raise ValueError("invalid NSE symbol")
    if page < 0 or not 1 <= size <= PAGE_SIZE:
        raise ValueError("invalid integrated-filing page bounds")
    return INTEGRATED_RESULTS_API + "?" + urlencode(
        {"index": "equities", "symbol": symbol.upper(), "page": page, "size": size}
    )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _parse_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _publication_stamp(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Use the latest parseable exchange publication timestamp conservatively."""
    stamps = []
    for key in ("creation_Date", "broadcast_Date"):
        raw = row.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        raw = raw.strip()
        parsed = nse.parse_nse_timestamp(raw)
        day = _parse_date(raw) if parsed is None else None
        if day:
            parsed = datetime.combine(date.fromisoformat(day), time(23, 59, 59), IST).astimezone(timezone.utc).isoformat()
        elif parsed is None:
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                parsed = dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                continue
        stamps.append((parsed, raw))
    return max(stamps) if stamps else (None, None)


def _basis(row: Dict[str, Any]) -> Optional[str]:
    value = str(row.get("consolidated") or "").strip().lower()
    if value == "consolidated":
        return "consolidated"
    if value == "standalone":
        return "standalone"
    return None


def _period_end(row: Dict[str, Any]) -> Optional[str]:
    return _parse_date(row.get("qe_Date") or row.get("quarterEndDate") or row.get("periodEnd"))


def _allowed_exchange_file(url: Any, extensions: Tuple[str, ...]) -> Optional[str]:
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip()
    try:
        validate_public_https(value)
    except UnsafeURL:
        return None
    parsed = urlparse(value)
    if parsed.hostname not in NSE_HOSTS or not parsed.path.lower().endswith(extensions):
        return None
    return value


def same_exchange_file(left: Optional[str], right: Optional[str]) -> bool:
    """Exact NSE archive path equality across the explicitly trusted .com/.in mirrors."""
    if not left or not right:
        return False
    a, b = urlparse(left.strip()), urlparse(right.strip())
    if a.scheme != "https" or b.scheme != "https" or a.hostname not in NSE_HOSTS or b.hostname not in NSE_HOSTS:
        return False
    def normalized(host: str) -> str:
        for suffix in ("nseindia.com", "nseindia.in"):
            if host == suffix or host.endswith("." + suffix):
                return host[:-len(suffix)] + "nseindia"
        return host
    return (not any((a.username, b.username, a.password, b.password))
            and normalized(a.hostname) == normalized(b.hostname) and a.path == b.path and a.query == b.query)


def _financial_rows(records: Iterable[Any], symbol: str) -> Tuple[List[Dict[str, Any]], int]:
    rows, rejected = [], 0
    for row in records:
        if not isinstance(row, dict):
            rejected += 1
            continue
        row_symbol = row.get("symbol")
        kind = str(row.get("type") or "").lower()
        basis = _basis(row)
        end = _period_end(row)
        publication, _raw = _publication_stamp(row)
        xbrl_url = (_allowed_exchange_file(row.get("xbrl"), (".xml", ".xhtml", ".xbrl"))
                    or _allowed_exchange_file(row.get("ixbrl"), (".html", ".xhtml")))
        if (not isinstance(row_symbol, str) or row_symbol.upper() != symbol.upper()
                or "financial" not in kind or "governance" in kind or not basis or not end
                or not publication or not xbrl_url):
            rejected += 1
            continue
        rows.append({**row, "_basis": basis, "_period_end": end, "_published_at": publication,
                     "_published_at_raw": _raw,
                     "_xbrl_url": xbrl_url,
                     "_pdf_url": _allowed_exchange_file(row.get("pdf_attach"), (".pdf",))})
    return rows, rejected


def fetch_integrated_rows(fetcher: Fetcher, company: Company, *, page_size: int = PAGE_SIZE,
                          max_pages: int = MAX_PAGES) -> Dict[str, Any]:
    """Read the complete bounded financial feed and retain its page provenance."""
    records: List[Dict[str, Any]] = []
    pages: List[Dict[str, Any]] = []
    rejected = 0
    total_count: Optional[int] = None
    returned_count = 0
    for page in range(max_pages):
        url = integrated_filing_url(company.symbol, page, page_size)
        result = fetcher.get(url, source_kind="nse_integrated_results", expect="json", company_id=company.company_id,
                             headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"})
        if not result.ok:
            return {"state": result.state, "issue": f"NSE integrated filing feed: {result.state}",
                    "records": records, "pages": pages, "rejected": rejected}
        payload = result.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return {"state": "invalid_document", "issue": "NSE integrated filing response has no data list",
                    "records": records, "pages": pages, "rejected": rejected}
        pages.append({"url": result.final_url or result.url, "hash": result.content_hash,
                      "returned_page": payload.get("page"), "size": payload.get("size")})
        if isinstance(payload.get("totalCount"), int) and payload["totalCount"] >= 0:
            total_count = payload["totalCount"]
        safe, bad = _financial_rows(data, company.symbol)
        for record in safe:
            record["_feed_url"] = result.final_url or result.url
            record["_feed_hash"] = result.content_hash
        records.extend(safe)
        returned_count += len(data)
        rejected += bad
        if not data or (total_count is not None and returned_count >= total_count):
            break
        if total_count is None and len(data) < page_size:
            break
    return {"state": "fetched", "issue": None, "records": records, "pages": pages, "rejected": rejected}


def _period_parts(context: ET.Element) -> Tuple[Optional[str], Optional[str], str]:
    period = next((child for child in context if _local(child.tag) == "period"), None)
    if period is None:
        return None, None, "unknown"
    start = next((child.text for child in period if _local(child.tag) == "startDate"), None)
    end = next((child.text for child in period if _local(child.tag) in ("endDate", "instant")), None)
    start_date, end_date = _parse_date(start), _parse_date(end)
    kind = "duration" if start_date and end_date else "instant" if end_date else "unknown"
    return start_date, end_date, kind


def _context_dimensions(context: ET.Element) -> List[str]:
    return ["/".join(_local(child.tag) + ":" + (child.text or "").strip()
                     for child in elem.iter() if child is not elem)
            for elem in context.iter() if _local(elem.tag) in ("explicitMember", "typedMember")]


def _unit_string(unit: Optional[ET.Element]) -> Optional[str]:
    if unit is None:
        return None
    divide = next((x for x in unit.iter() if _local(x.tag) == "divide"), None)
    if divide is not None:
        numerator = next((x for x in divide if _local(x.tag) == "unitNumerator"), None)
        denominator = next((x for x in divide if _local(x.tag) == "unitDenominator"), None)
        num = ".".join(_local(x.text or "") for x in (numerator or []))
        den = ".".join(_local(x.text or "") for x in (denominator or []))
        return f"{num}/{den}" if num and den else num or den or None
    measures = [_local(x.text or "") for x in unit if _local(x.tag) == "measure"]
    return ".".join(value for value in measures if value) or None


def _decimal_value(raw: str, scale: Optional[str], sign: Optional[str]) -> Optional[str]:
    try:
        number = Decimal(raw.strip().replace(",", ""))
        if scale:
            number *= Decimal(10) ** int(scale)
        if sign == "-":
            number = -number
        if not number.is_finite():
            return None
        return format(number.normalize(), "f")
    except (InvalidOperation, ValueError, OverflowError):
        return None


def parse_xbrl(data: bytes) -> Dict[str, Any]:
    """Parse numeric facts with a non-dimensional context; values stay exact decimals."""
    if len(data) > 50 * 1024 * 1024:
        raise ValueError("XBRL document exceeds the parser size limit")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, flags=re.IGNORECASE):
        raise ValueError("XBRL document declarations are not accepted")
    root = ET.fromstring(data)
    contexts: Dict[str, Dict[str, Any]] = {}
    entities = set()
    for elem in root.iter():
        if _local(elem.tag) != "context":
            continue
        ref = elem.attrib.get("id")
        if not ref or _context_dimensions(elem):
            continue
        identifier = next((child.text.strip() for child in elem.iter()
                           if _local(child.tag) == "identifier" and child.text), None)
        if not identifier:
            continue
        entities.add(identifier)
        start, end, kind = _period_parts(elem)
        contexts[ref] = {"period_start": start, "period_end": end, "period_kind": kind}
    units = {elem.attrib.get("id"): _unit_string(elem) for elem in root.iter()
             if _local(elem.tag) == "unit" and elem.attrib.get("id")}
    facts = []
    occurrences: Dict[Tuple[str, str], int] = {}
    for elem in root.iter():
        context_ref = elem.attrib.get("contextRef")
        unit_ref = elem.attrib.get("unitRef")
        if (not context_ref or context_ref not in contexts or not unit_ref or not elem.text
                or elem.attrib.get("nil", "false").lower() == "true"):
            continue
        value = _decimal_value(elem.text, elem.attrib.get("scale"), elem.attrib.get("sign"))
        if value is None:
            continue
        namespace = elem.tag[1:].split("}", 1)[0] if isinstance(elem.tag, str) and elem.tag.startswith("{") else ""
        concept = _local(elem.tag)
        if concept.lower() == "nonfraction" and elem.attrib.get("name"):
            qname = elem.attrib["name"]
            namespace, _, local_name = qname.rpartition(":")
            concept = local_name or qname
        occurrence_key = (context_ref, namespace + ":" + concept)
        occurrence = occurrences.get(occurrence_key, 0)
        occurrences[occurrence_key] = occurrence + 1
        facts.append({**contexts[context_ref], "context_ref": context_ref, "concept": concept,
                      "namespace": namespace, "value_text": value, "unit": units.get(unit_ref),
                      "decimals": elem.attrib.get("decimals"), "dimensions": [], "occurrence": occurrence})
    return {"facts": facts, "context_count": len(contexts), "fact_count": len(facts),
            "entity_identifier": next(iter(entities)) if len(entities) == 1 else None}


def _filing_id(row: Dict[str, Any], company: Company, content_hash: str) -> str:
    raw = "|".join((company.company_id, row["_basis"], row["_period_end"], str(row.get("seq_Id") or ""),
                    row["_published_at"], row["_xbrl_url"], content_hash))
    return hashlib.sha256(raw.encode()).hexdigest()


def _store_filing(store: Store, company: Company, row: Dict[str, Any], feed_page: Dict[str, Any],
                  fetcher: Fetcher) -> Dict[str, Any]:
    result = fetcher.get(row["_xbrl_url"], source_kind="nse_integrated_xbrl", expect="xml",
                         company_id=company.company_id, headers={"Accept": "application/xml,text/xml,application/xhtml+xml"})
    if not result.ok or not result.content_hash:
        return {"symbol": company.symbol, "period_end": row["_period_end"], "basis": row["_basis"],
                "state": result.state, "issue": result.error or "XBRL source unavailable"}
    try:
        parsed = parse_xbrl(result.content or b"")
    except (ValueError, ET.ParseError) as exc:
        parsed = {"facts": [], "fact_count": 0, "context_count": 0, "entity_identifier": None}
        parse_issue = f"XBRL parse failed: {exc.__class__.__name__}"
    else:
        parse_issue = None
    period_bound = any(f.get("period_end") == row["_period_end"] for f in parsed["facts"])
    entity = (parsed["entity_identifier"] or "").upper()
    is_isin = bool(re.fullmatch(r"IN[A-Z0-9]{10}", entity))
    identity_ok = bool(entity and (not is_isin or entity == company.isin.upper()))
    if not identity_ok:
        state, issue = "identity_unverified", "XBRL contexts have missing, conflicting or wrong-company identifiers."
    elif not period_bound:
        state, issue = "period_unverified", "No non-dimensional numeric fact proves the exchange quarter end."
    else:
        state, issue = "verified", None
    issue = parse_issue or issue
    filing_id = _filing_id(row, company, result.content_hash)
    filing = {
        "filing_id": filing_id, "company_id": company.company_id, "symbol": company.symbol,
        "basis": row["_basis"], "period_end": row["_period_end"], "filing_type": str(row.get("type") or ""),
        "revision": str(row.get("type_Sub") or "Original"), "seq_id": str(row.get("seq_Id") or ""),
        "published_at": row["_published_at"], "published_at_raw": row.get("_published_at_raw"),
        "feed_url": row.get("_feed_url") or feed_page.get("url") or INTEGRATED_RESULTS_API,
        "feed_hash": row.get("_feed_hash") or feed_page.get("hash"),
        "raw_record": json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, sort_keys=True),
        "xbrl_url": row["_xbrl_url"], "xbrl_final_url": result.final_url,
        "xbrl_hash": result.content_hash, "pdf_url": row.get("_pdf_url"), "retrieved_at": result.retrieved_at,
        "facts_count": len(parsed["facts"]), "parse_state": state, "issue": issue,
    }
    columns = tuple(filing)
    fact_rows = []
    for fact in parsed["facts"] if state == "verified" else ():
        fact_id = hashlib.sha256((filing_id + "|" + fact["context_ref"] + "|" + fact["namespace"] + "|" +
                                  fact["concept"] + "|" + str(fact["occurrence"])).encode()).hexdigest()
        fact_rows.append((fact_id, filing_id, fact["context_ref"], fact["period_start"], fact["period_end"],
                          fact["period_kind"], fact["concept"], fact["namespace"], fact["value_text"], fact["unit"],
                          fact["decimals"], "[]"))
    with store.connect() as conn:
        conn.execute(f"INSERT OR REPLACE INTO xbrl_filings ({','.join(columns)}) "
                     f"VALUES ({','.join('?' for _ in columns)})", tuple(filing.values()))
        conn.execute("DELETE FROM xbrl_facts WHERE filing_id=?", (filing_id,))
        conn.executemany("INSERT INTO xbrl_facts (fact_id,filing_id,context_ref,period_start,period_end,period_kind,"
                         "concept,namespace,value_text,unit,decimals,dimensions_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         fact_rows)
    return {"symbol": company.symbol, "period_end": row["_period_end"], "basis": row["_basis"],
            "revision": filing["revision"], "published_at": row["_published_at"], "state": state,
            "facts": len(parsed["facts"]), "issue": issue, "xbrl_hash": result.content_hash}


def refresh_company(store: Store, fetcher: Fetcher, company: Company,
                    quarters: int = MAX_PERIODS_PER_BASIS) -> Dict[str, Any]:
    if not 1 <= quarters <= 12:
        raise ValueError("choose between 1 and 12 quarters")
    started = datetime.now(timezone.utc)
    feed = fetch_integrated_rows(fetcher, company)
    if feed["state"] != "fetched":
        return {"symbol": company.symbol, "state": feed["state"], "issue": feed["issue"],
                "records": 0, "stored": 0, "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2)}
    if not feed["records"]:
        return {"symbol": company.symbol, "state": "partial", "issue": "No verifiable financial filing rows were returned for this symbol.",
                "feed_pages": len(feed["pages"]), "records_seen": 0, "selected_versions": 0,
                "rejected_rows": feed["rejected"], "stored": 0, "issues": [], "filings": [],
                "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2)}
    # Keep every version of the most recent bounded quarter/basis groups. The
    # scorecard selects the latest publication while preserving older versions.
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in feed["records"]:
        grouped.setdefault((row["_basis"], row["_period_end"]), []).append(row)
    selected_keys = set()
    for basis in ("consolidated", "standalone"):
        period_ends = sorted({end for b, end in grouped if b == basis}, reverse=True)[:quarters]
        selected_keys.update((basis, end) for end in period_ends)
    selected = []
    seen = set()
    for key in sorted(selected_keys, key=lambda item: (item[1], item[0])):
        versions = grouped[key]
        # Keep each source revision; de-duplicate repeat feed pages only.
        for row in versions:
            marker = (key, str(row.get("seq_Id") or ""), row["_xbrl_url"], row["_published_at"])
            if marker not in seen:
                seen.add(marker)
            selected.append((row, {"url": row.get("_feed_url"), "hash": row.get("_feed_hash")}))
    results = []
    for row, page in selected:
        # An explicit date-only record is conservatively available only at the
        # end of that IST date, matching the rest of FINN's publication policy.
        results.append(_store_filing(store, company, row, page, fetcher))
    return {"symbol": company.symbol, "state": "completed" if all(r["state"] == "verified" for r in results) else "partial",
            "feed_pages": len(feed["pages"]), "records_seen": len(feed["records"]), "selected_versions": len(selected),
            "rejected_rows": feed["rejected"], "stored": sum(r["state"] == "verified" for r in results),
            "issues": [r for r in results if r["state"] != "verified"], "filings": results,
            "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2)}


def _quarter_start(end: date) -> Optional[date]:
    if end.month == 3 and end.day == 31:
        return date(end.year, 1, 1)
    if end.month == 6 and end.day == 30:
        return date(end.year, 4, 1)
    if end.month == 9 and end.day == 30:
        return date(end.year, 7, 1)
    if end.month == 12 and end.day == 31:
        return date(end.year, 10, 1)
    return None


_CONCEPTS = {
    "revenue": ("RevenueFromOperations", "RevenueFromOperationsOfTheEntity", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    "expenses": ("Expenses", "TotalExpenses"),
    "finance_costs": ("FinanceCosts", "FinanceCost"),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense", "DepreciationAndAmortisationExpense"),
    "pbt": ("ProfitBeforeTax", "ProfitLossFromOrdinaryActivitiesBeforeTax"),
    "pat": ("ProfitLossForPeriod", "ProfitLossForThePeriod", "ProfitLoss", "ProfitAfterTax"),
    "eps": ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "BasicEarningsLossPerShare"),
    "interest_earned": ("InterestEarned",),
    "interest_expended": ("InterestExpended",),
    "operating_profit_before_provisions": ("OperatingProfitBeforeProvisionAndContingencies",),
    "provisions": ("ProvisionsOtherThanTaxAndContingencies", "ProvisionsAndContingencies"),
    "assets": ("Assets",), "equity": ("Equity",),
    "liabilities": ("Liabilities",), "cash": ("CashAndCashEquivalents", "CashAndCashEquivalentsAtCarryingValue"),
    "receivables": ("TradeReceivables", "TradeAndOtherCurrentReceivables"),
    "inventories": ("Inventories",), "borrowings": ("Borrowings",),
    "operating_cash_flow": ("CashFlowsFromUsedInOperatingActivities",),
    "capex": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "advances": ("Advances", "LoansAndAdvances"), "deposits": ("Deposits",),
}


def _quarter_filing_map(store: Store, company_id: str, basis: str, cutoff_utc: Optional[str]) -> Dict[str, Dict[str, Any]]:
    rows = store.query("SELECT * FROM xbrl_filings WHERE company_id=? AND basis=? AND parse_state='verified' "
                       "ORDER BY period_end DESC, published_at DESC, filing_id", (company_id, basis))
    by_period: Dict[str, Dict[str, Any]] = {}
    cutoff = datetime.fromisoformat(cutoff_utc) if cutoff_utc else datetime.now(timezone.utc)
    for row in rows:
        try:
            published = datetime.fromisoformat(row["published_at"])
        except (TypeError, ValueError):
            continue
        if cutoff and (published.tzinfo is None or published > cutoff):
            continue
        end = date.fromisoformat(row["period_end"])
        if _quarter_start(end) is None or end.isoformat() in by_period:
            continue
        by_period[end.isoformat()] = row
    return by_period


def latest_result_period(store: Store, company_id: str) -> Optional[str]:
    """Latest verified exchange XBRL quarter on either reporting basis."""
    return max((period for basis in ("consolidated", "standalone")
                for period in _quarter_filing_map(store, company_id, basis, None)), default=None)


def scorecard_for_attachment(store: Store, company: Company, attachment_url: Optional[str],
                             cutoff_utc: Optional[str]) -> Optional[Dict[str, Any]]:
    if not attachment_url:
        return None
    for basis in ("consolidated", "standalone"):
        periods = _quarter_filing_map(store, company.company_id, basis, cutoff_utc)
        for period, filing in periods.items():
            inline_url = _allowed_exchange_file(json.loads(filing["raw_record"]).get("ixbrl"), (".html", ".xhtml"))
            if any(same_exchange_file(url, attachment_url) for url in
                   (filing["pdf_url"], filing["xbrl_url"], inline_url)):
                card = build_scorecard(store, company, basis=basis, cutoff_utc=cutoff_utc, period_end=period)
                return card if card["available"] else None
    return None


def _previous_quarter_end(end: date) -> Optional[date]:
    if end.month == 3 and end.day == 31:
        return date(end.year - 1, 12, 31)
    if end.month == 6 and end.day == 30:
        return date(end.year, 3, 31)
    if end.month == 9 and end.day == 30:
        return date(end.year, 6, 30)
    if end.month == 12 and end.day == 31:
        return date(end.year, 9, 30)
    return None


def _quarter_facts(store: Store, filing: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    rows = store.query("SELECT * FROM xbrl_facts WHERE filing_id=? ORDER BY fact_id", (filing["filing_id"],))
    end = date.fromisoformat(filing["period_end"])
    start = _quarter_start(end).isoformat()
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row["period_kind"] != "duration" or row["period_start"] != start or row["period_end"] != end.isoformat():
            continue
        result.setdefault(row["concept"], []).append(row)
    return result


def _instant_facts(store: Store, filing: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    rows = store.query("SELECT * FROM xbrl_facts WHERE filing_id=? ORDER BY fact_id", (filing["filing_id"],))
    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row["period_kind"] == "instant":
            result.setdefault(row["concept"], []).append(row)
    return result


def _fact(facts: Dict[str, List[Dict[str, Any]]], key: str) -> Optional[Dict[str, Any]]:
    for concept in _CONCEPTS.get(key, (key,)):
        candidates = facts.get(concept, [])
        if candidates:
            preferred = [row for row in candidates if row.get("unit") == ("INR/shares" if key == "eps" else "INR")]
            candidates = preferred or candidates
            if len({(row["value_text"], row.get("unit")) for row in candidates}) != 1:
                return None  # conflicting equivalent contexts cannot justify one value
            return candidates[0]
    return None


def _fact_at(facts: Dict[str, List[Dict[str, Any]]], key: str, period_end: Optional[str]) -> Optional[Dict[str, Any]]:
    if not period_end:
        return None
    selected = {concept: [row for row in facts.get(concept, []) if row.get("period_end") == period_end]
                for concept in _CONCEPTS.get(key, (key,))}
    return _fact(selected, key)


def _money_value(fact: Optional[Dict[str, Any]]) -> Optional[Decimal]:
    if not fact or not fact.get("unit"):
        return None
    if not re.search(r"\bINR\b", fact["unit"], re.I) or "/" in fact["unit"]:
        return None
    try:
        return Decimal(fact["value_text"])
    except InvalidOperation:
        return None


def _number(value: Decimal, unit: str) -> Dict[str, Any]:
    display = value / _INR_PER_CRORE if unit == "INR" else value
    return {"value_raw": format(value, "f"), "unit": unit,
            "value_crore": format(display, "f") if unit == "INR" else None}


def _display_value(value: Optional[Decimal], unit: str = "INR") -> Optional[Dict[str, Any]]:
    return _number(value, unit) if value is not None else None


def _latest_fact_value(store: Store, filing: Optional[Dict[str, Any]], key: str, *, instant: bool = False) -> Optional[Decimal]:
    if not filing:
        return None
    facts = _instant_facts(store, filing) if instant else _quarter_facts(store, filing)
    return _money_value(_fact(facts, key))


def _source_meta(filing: Dict[str, Any], facts: Dict[str, List[Dict[str, Any]]], concept_keys: Iterable[str]) -> Dict[str, Any]:
    concepts = []
    for key in concept_keys:
        fact = _fact(facts, key)
        if fact:
            concepts.append({"role": key, "concept": fact["concept"], "namespace": fact["namespace"],
                             "raw_value": fact["value_text"], "unit": fact["unit"], "decimals": fact["decimals"],
                             "period_start": fact["period_start"], "period_end": fact["period_end"]})
    return {"filing_id": filing["filing_id"], "period_end": filing["period_end"], "published_at": filing["published_at"],
            "revision": filing["revision"], "basis": filing["basis"], "xbrl_url": filing["xbrl_url"],
            "xbrl_hash": filing["xbrl_hash"], "pdf_url": filing["pdf_url"], "concepts": concepts}


def _metric_payload(store: Store, metric: str, label: str, current: Optional[Decimal], previous: Optional[Decimal],
                    year_ago: Optional[Decimal], current_filing: Dict[str, Any], current_facts: Dict[str, List[Dict[str, Any]]],
                    roles: Iterable[str], *, unit: str = "INR", formula: Optional[str] = None,
                    derivation: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    def pct(base):
        if current is None or base in (None, Decimal(0)):
            return None
        return float(((current - base) / abs(base) * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return {"key": metric, "label": label, "unit": "₹ crore" if unit == "INR" else unit,
            "current": _display_value(current, unit), "previous_quarter": _display_value(previous, unit),
            "year_ago_quarter": _display_value(year_ago, unit), "qoq_pct": pct(previous), "yoy_pct": pct(year_ago),
            "source": _source_meta(current_filing, current_facts, roles), "formula": formula,
            "derivation": derivation or []}


def build_scorecard(store: Store, company: Company, *, basis: str = "consolidated",
                    cutoff_utc: Optional[str] = None, period_end: Optional[str] = None) -> Dict[str, Any]:
    if basis not in ("consolidated", "standalone"):
        raise ValueError("basis must be consolidated or standalone")
    periods = _quarter_filing_map(store, company.company_id, basis, cutoff_utc)
    current_end = (period_end if period_end in periods else None) if period_end else max(periods, default=None)
    base = {"symbol": company.symbol, "legal_name": company.legal_name, "basis": basis,
            "mode": "replay" if cutoff_utc else "live", "cutoff": cutoff_utc,
            "available": False, "period_end": current_end, "periods": sorted(periods, reverse=True),
            "metrics": [], "gaps": [], "method": "Deterministic values from exchange integrated-filing XBRL; no model call."}
    if not current_end:
        base["gaps"] = ["No verified exchange XBRL quarter is stored for this basis and publication cutoff."]
        if not cutoff_utc:
            attempt = store.query_one("SELECT state FROM fetch_attempts WHERE company_id=? AND "
                                      "source_kind='nse_integrated_results' ORDER BY finished_at DESC LIMIT 1",
                                      (company.company_id,))
            detail = store.query_one("SELECT issue FROM xbrl_filings WHERE company_id=? AND basis=? AND "
                                     "issue IS NOT NULL ORDER BY period_end DESC, published_at DESC LIMIT 1",
                                     (company.company_id, basis))
            if attempt and attempt["state"] != "fetched":
                base["gaps"].append(f"Latest NSE integrated results attempt: {attempt['state']}.")
            elif detail:
                base["gaps"].append(detail["issue"])
            else:
                base["gaps"].append("This copy of FINN has no verified source for the selected basis.")
        return base
    latest = periods[current_end]
    superseded = None
    if latest["revision"].lower() == "revision":
        superseded = store.query_one(
            "SELECT * FROM xbrl_filings WHERE company_id=? AND basis=? AND period_end=? AND parse_state='verified' "
            "AND published_at<? ORDER BY published_at DESC, filing_id LIMIT 1",
            (company.company_id, basis, current_end, latest["published_at"]))
    latest_facts = _quarter_facts(store, latest)
    current_date = date.fromisoformat(current_end)
    previous_date = _previous_quarter_end(current_date)
    previous_end = previous_date.isoformat() if previous_date else None
    expected_year_ago = date(current_date.year - 1, current_date.month, current_date.day).isoformat()
    year_ago_end = expected_year_ago
    previous = periods.get(previous_end) if previous_end else None
    year_ago = periods.get(year_ago_end) if year_ago_end else None
    bank = any(_fact(latest_facts, role) for role in ("interest_earned", "interest_expended", "operating_profit_before_provisions"))
    metric_defs = ([
        ("net_interest_income", "Net interest income", ("interest_earned", "interest_expended")),
        ("operating_profit_before_provisions", "Operating profit before provisions", ("operating_profit_before_provisions",)),
        ("provisions", "Provisions", ("provisions",)), ("pbt", "Profit before tax", ("pbt",)),
        ("pat", "Profit after tax", ("pat",)),
    ] if bank else [
        ("revenue", "Revenue from operations", ("revenue",)),
        ("ebitda", "EBITDA (derived)", ("revenue", "expenses", "finance_costs", "depreciation")),
        ("pbt", "Profit before tax", ("pbt",)), ("pat", "Profit after tax", ("pat",)),
    ])

    metrics = []
    for key, label, roles in metric_defs:
        def calc(filing):
            if not filing:
                return None
            f = _quarter_facts(store, filing)
            if key == "ebitda":
                revenue, expenses = _money_value(_fact(f, "revenue")), _money_value(_fact(f, "expenses"))
                finance, depreciation = _money_value(_fact(f, "finance_costs")), _money_value(_fact(f, "depreciation"))
                return revenue - (expenses - finance - depreciation) if all(v is not None for v in (revenue, expenses, finance, depreciation)) else None
            if key == "net_interest_income":
                earned, expended = _money_value(_fact(f, "interest_earned")), _money_value(_fact(f, "interest_expended"))
                return earned - expended if earned is not None and expended is not None else None
            return _money_value(_fact(f, key))
        current_value, prev_value, year_value = calc(latest), calc(previous), calc(year_ago)
        if current_value is None:
            base["gaps"].append(f"{label}: a required exchange-tagged input is missing or does not use INR.")
            continue
        derivation = []
        formula = None
        if key == "ebitda":
            formula = "Revenue from operations − (Expenses − Finance costs − Depreciation and amortisation)"
            for role in roles:
                fact = _fact(latest_facts, role)
                if fact:
                    derivation.append({"role": role, "concept": fact["concept"], "value_raw": fact["value_text"], "unit": fact["unit"]})
        elif key == "net_interest_income":
            formula = "Interest earned − Interest expended"
            for role in roles:
                fact = _fact(latest_facts, role)
                if fact:
                    derivation.append({"role": role, "concept": fact["concept"], "value_raw": fact["value_text"], "unit": fact["unit"]})
        metric_row = _metric_payload(store, key, label, current_value, prev_value, year_value, latest,
                                      latest_facts, roles, formula=formula, derivation=derivation)
        metric_row["comparative_sources"] = {
            "previous_quarter": _source_meta(previous, _quarter_facts(store, previous), roles) if previous else None,
            "year_ago_quarter": _source_meta(year_ago, _quarter_facts(store, year_ago), roles) if year_ago else None,
        }
        if superseded and (old_value := calc(superseded)) is not None:
            metric_row["previous"] = {"published_at": superseded["published_at"],
                                      "value": _display_value(old_value), "url": superseded["xbrl_url"]}
        metrics.append(metric_row)
    for metric in metrics:
        metric["qoq_period_end"] = previous_end
        metric["yoy_period_end"] = year_ago_end
        if metric["qoq_pct"] is None:
            base["gaps"].append(f"{metric['label']} QoQ: previous-quarter XBRL fact is unavailable.")
        if metric["yoy_pct"] is None:
            base["gaps"].append(f"{metric['label']} YoY: year-ago-quarter XBRL fact is unavailable.")
    base.update(available=bool(metrics), metrics=metrics,
                period_label=f"Quarter ended {current_end}", source=_source_meta(latest, latest_facts, []),
                comparative_periods={"previous_quarter": previous_end, "year_ago_quarter": year_ago_end},
                bank_taxonomy=bank,
                earnings_call_note="Quarter facts are selected from the quarter-duration context, not year-to-date totals.")
    if not base["available"]:
        base["gaps"].append("No headline metrics passed the source and unit checks.")
    return base


def build_financial_cards(store: Store, company: Company, *, basis: str = "consolidated",
                          cutoff_utc: Optional[str] = None) -> Dict[str, Any]:
    """Deterministic Pull cards whose visible values all carry their formula and evidence."""
    periods_by_basis = {name: max(_quarter_filing_map(store, company.company_id, name, cutoff_utc), default=None)
                        for name in ("consolidated", "standalone")}
    if basis == "auto":
        basis = max(periods_by_basis, key=lambda name: periods_by_basis[name] or "")
    score = build_scorecard(store, company, basis=basis, cutoff_utc=cutoff_utc)
    periods = _quarter_filing_map(store, company.company_id, basis, cutoff_utc)
    ordered = sorted(periods, reverse=True)
    latest = periods[ordered[0]] if ordered else None
    alternate_basis = "standalone" if basis == "consolidated" else "consolidated"
    alternate_period = periods_by_basis[alternate_basis]
    bs = _instant_facts(store, latest) if latest else {}
    qfacts = _quarter_facts(store, latest) if latest else {}
    metrics = {m["key"]: m for m in score.get("metrics", [])}
    snapshot = []
    summary_items = ([ ("net_interest_income", "Net interest income", metrics.get("net_interest_income")),
                       ("operating_profit_before_provisions", "Operating profit before provisions", metrics.get("operating_profit_before_provisions")),
                       ("pat", "PAT", metrics.get("pat")), ("eps", "Basic EPS", None) ]
                     if score.get("bank_taxonomy") else
                     [("revenue", "Revenue", metrics.get("revenue")), ("ebitda", "EBITDA margin", metrics.get("ebitda")),
                      ("pat", "PAT margin", metrics.get("pat")), ("eps", "Basic EPS", None)])
    for key, label, source in summary_items:
        if key == "ebitda":
            rev = metrics.get("revenue", {}).get("current", {}).get("value_crore")
            ebitda = metrics.get("ebitda", {}).get("current", {}).get("value_crore")
            value = Decimal(ebitda) / Decimal(rev) * 100 if rev and Decimal(rev) and ebitda else None
            value_obj = {"value": format(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f"), "unit": "%"} if value is not None else None
        elif key == "pat" and not score.get("bank_taxonomy"):
            rev = metrics.get("revenue", {}).get("current", {}).get("value_crore")
            pat = metrics.get("pat", {}).get("current", {}).get("value_crore")
            value = Decimal(pat) / Decimal(rev) * 100 if rev and Decimal(rev) and pat else None
            value_obj = {"value": format(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f"), "unit": "%"} if value is not None else None
        elif key == "eps":
            fact = _fact(qfacts, "eps")
            try:
                value_obj = {"value": fact["value_text"], "unit": fact["unit"]} if fact else None
            except (KeyError, TypeError):
                value_obj = None
        else:
            value_obj = source["current"] if source else None
        snapshot.append({"key": key, "label": label, "value": value_obj,
                         "formula": ("EBITDA ÷ revenue × 100" if key == "ebitda" else
                                     "PAT ÷ revenue × 100" if key == "pat" and not score.get("bank_taxonomy") else None),
                         "growth": ({"qoq_pct": source.get("qoq_pct"), "yoy_pct": source.get("yoy_pct"),
                                     "qoq_period_end": source.get("qoq_period_end"), "yoy_period_end": source.get("yoy_period_end")}
                                    if key == "revenue" and source else None),
                         "source": source.get("source") if source else (_source_meta(latest, qfacts, ("eps",)) if key == "eps" and latest else None)})
    balance = []
    current_bs_date = latest["period_end"] if latest else None
    prior_march = max((row["period_end"] for values in bs.values() for row in values
                       if row.get("period_end", "") < (current_bs_date or "")
                       and row.get("period_end", "")[5:] == "03-31"), default=None)
    current_bs = {concept: [row for row in values if row.get("period_end") == current_bs_date]
                  for concept, values in bs.items()}
    prior_bs = {concept: [row for row in values if row.get("period_end") == prior_march]
                for concept, values in bs.items()}
    balance_roles = [("assets", "Assets"), ("equity", "Equity"), ("liabilities", "Liabilities"),
                     ("cash", "Cash and cash equivalents"), ("receivables", "Trade receivables"),
                     ("inventories", "Inventories"), ("borrowings", "Borrowings")]
    if score.get("bank_taxonomy"):
        balance_roles.extend([("advances", "Advances"), ("deposits", "Deposits")])
    for key, label in balance_roles:
        fact = _fact(current_bs, key)
        old_fact = _fact(prior_bs, key)
        value, old_value = _money_value(fact), _money_value(old_fact)
        balance.append({"key": key, "label": label, "current": _display_value(value),
                        "previous_march": _display_value(old_value), "tagged": value is not None,
                        "concept": fact["concept"] if fact else None, "period_end": current_bs_date,
                        "comparison_period_end": prior_march, "raw_value": fact["value_text"] if fact else None,
                        "source": _source_meta(latest, current_bs, (key,)) if latest else None,
                        "previous_march_source": _source_meta(latest, prior_bs, (key,)) if latest and old_fact else None})
    eq = next((x for x in balance if x["key"] == "equity"), None)
    cash = next((x for x in balance if x["key"] == "cash"), None)
    debt = next((x for x in balance if x["key"] == "borrowings"), None)
    if debt and debt["tagged"] and eq and eq["tagged"] and Decimal(eq["current"]["value_crore"] or "0") != 0:
        balance.append({"key": "debt_to_equity", "label": "Debt to equity", "value": format(
            (Decimal(debt["current"]["value_crore"]) / Decimal(eq["current"]["value_crore"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f"),
            "unit": "×", "formula": "Borrowings ÷ equity",
            "source": _source_meta(latest, current_bs, ("borrowings", "equity")) if latest else None})
    if not score.get("bank_taxonomy") and cash and cash["tagged"] and debt and debt["tagged"]:
        net_cash = Decimal(cash["current"]["value_crore"]) - Decimal(debt["current"]["value_crore"])
        balance.append({"key": "net_cash_debt", "label": "Net cash / (debt)", "value": format(net_cash, "f"),
                        "unit": "₹ crore", "formula": "Cash and cash equivalents − borrowings",
                        "source": _source_meta(latest, current_bs, ("cash", "borrowings")) if latest else None})
    cash_filing = next((periods[end] for end in ordered if end[5:] in {"03-31", "09-30"}), None)
    cash_quality = {"period_end": cash_filing["period_end"] if cash_filing else None, "period_type": None,
                    "operating_cash_flow": None, "pat": None, "cash_conversion_pct": None,
                    "capex": None, "free_cash_flow": None, "gaps": []}
    if cash_filing:
        # A current half-year cash flow is a year-to-date duration. We show it
        # as such and compare only to the same filing's year-to-date PAT.
        facts = store.query("SELECT * FROM xbrl_facts WHERE filing_id=? ORDER BY fact_id", (cash_filing["filing_id"],))
        all_facts: Dict[str, List[Dict[str, Any]]] = {}
        end_date = date.fromisoformat(cash_filing["period_end"])
        fiscal_start = f"{end_date.year if end_date.month >= 4 else end_date.year - 1}-04-01"
        for row in facts:
            if row["period_kind"] == "duration" and row["period_end"] == cash_filing["period_end"] and row["period_start"] == fiscal_start:
                all_facts.setdefault(row["concept"], []).append(row)
        cf = _fact(all_facts, "operating_cash_flow")
        capex_fact = _fact(all_facts, "capex")
        pat_fact = _fact(all_facts, "pat")
        cf_value, capex_value, pat_value = _money_value(cf), _money_value(capex_fact), _money_value(pat_fact)
        cash_quality["period_type"] = "Full year" if end_date.month == 3 else "Half year"
        cash_quality["period_start"] = fiscal_start
        cash_quality["operating_cash_flow"] = _display_value(cf_value)
        cash_quality["pat"] = _display_value(pat_value)
        if cf_value is not None and pat_value is not None and pat_value != 0:
            cash_quality["cash_conversion_pct"] = float((cf_value / pat_value * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        cash_quality["capex"] = _display_value(capex_value)
        cash_quality["sources"] = {"operating_cash_flow": _source_meta(cash_filing, all_facts, ("operating_cash_flow",)) if cf else None,
                                    "pat": _source_meta(cash_filing, all_facts, ("pat",)) if pat_fact else None,
                                    "capex": _source_meta(cash_filing, all_facts, ("capex",)) if capex_fact else None}
        if cf_value is not None and capex_value is not None:
            cash_quality["free_cash_flow"] = _display_value(cf_value - abs(capex_value))
            cash_quality["free_cash_flow_formula"] = "Operating cash flow less tagged capex"
        if cf_value is None: cash_quality["gaps"].append("Operating cash flow: no matching YTD fact is tagged.")
        if pat_value is None: cash_quality["gaps"].append("PAT: no matching YTD fact is tagged for cash conversion.")
        if capex_value is None: cash_quality["gaps"].append("Capex: no matching YTD acquisition fact is tagged.")
    else:
        cash_quality["gaps"].append("No verified half-year or full-year XBRL filing is stored.")
    trajectory = []
    for end in ordered[:8]:
        filing = periods[end]
        f = _quarter_facts(store, filing)
        def q_value(key):
            return _money_value(_fact(f, key))
        bank = bool(_fact(f, "interest_earned") and _fact(f, "interest_expended"))
        if bank:
            earned, expended = q_value("interest_earned"), q_value("interest_expended")
            revenue = earned - expended if earned is not None and expended is not None else None
            expenses = finance = depreciation = None
        else:
            revenue, expenses = q_value("revenue"), q_value("expenses")
            finance, depreciation = q_value("finance_costs"), q_value("depreciation")
        pat = q_value("pat")
        ebitda = revenue - (expenses - finance - depreciation) if all(x is not None for x in (revenue, expenses, finance, depreciation)) else None
        annual = None
        end_date = date.fromisoformat(end)
        if end_date.month == 3 and end_date.day == 31:
            raw_ytd = store.query("SELECT * FROM xbrl_facts WHERE filing_id=? AND period_kind='duration' AND period_end=? ORDER BY fact_id",
                                  (filing["filing_id"], end))
            ytd_map: Dict[str, List[Dict[str, Any]]] = {}
            fiscal_start = f"{end_date.year - 1}-04-01"
            for item in raw_ytd:
                if item.get("period_start") == fiscal_start:
                    ytd_map.setdefault(item["concept"], []).append(item)
            annual_revenue = _money_value(_fact(ytd_map, "revenue"))
            annual_pat = _money_value(_fact(ytd_map, "pat"))
            annual_expenses = _money_value(_fact(ytd_map, "expenses"))
            annual_finance = _money_value(_fact(ytd_map, "finance_costs"))
            annual_depreciation = _money_value(_fact(ytd_map, "depreciation"))
            annual_ebitda = (annual_revenue - (annual_expenses - annual_finance - annual_depreciation)
                             if all(v is not None for v in (annual_revenue, annual_expenses, annual_finance, annual_depreciation)) else None)
            annual = {"revenue": _display_value(annual_revenue), "pat": _display_value(annual_pat),
                      "ebitda_margin_pct": float((annual_ebitda / annual_revenue * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
                      if annual_ebitda is not None and annual_revenue else None,
                      "source": _source_meta(filing, ytd_map, ("revenue", "expenses", "finance_costs", "depreciation", "pat"))}
        trajectory.append({"period_end": end, "revenue": _display_value(revenue),
                           "revenue_label": "Net interest income" if bank else "Revenue",
                           "operating_profit_before_provisions": _display_value(q_value("operating_profit_before_provisions")) if bank else None,
                           "ebitda_margin_pct": float((ebitda / revenue * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) if ebitda is not None and revenue else None,
                           "pat": _display_value(pat), "annual": annual,
                           "source": _source_meta(filing, f, ("interest_earned", "interest_expended", "pat") if bank else
                                                  ("revenue", "expenses", "finance_costs", "depreciation", "pat"))})
    balance_gaps = [f"{item['label']}: not tagged, not shown." for item in balance if item.get("tagged") is False]
    ratios = {item["key"] for item in balance if item.get("formula")}
    if "debt_to_equity" not in ratios:
        balance_gaps.append("Debt to equity: dated borrowings and nonzero equity are required.")
    if not score.get("bank_taxonomy") and "net_cash_debt" not in ratios:
        balance_gaps.append("Net cash or debt: dated cash and borrowings are required.")
    if latest and not prior_march:
        balance_gaps.append("Prior 31 March comparison: no prior-year-end instant is tagged in this filing.")
    elif latest:
        balance_gaps.extend(f"{item['label']} prior 31 March value: not tagged, not shown."
                             for item in balance if item.get("tagged") and item.get("previous_march") is None)
    if not score.get("bank_taxonomy") and not (debt and debt["tagged"] and eq and eq["tagged"]):
        balance_gaps.append("Debt to equity and net cash/debt: not shown because required tagged values are missing.")
    trajectory_gaps = []
    if len(trajectory) < 6:
        trajectory_gaps.append(f"Only {len(trajectory)} verified quarter(s) are available; trajectory is incomplete.")
    for row in trajectory:
        if row["revenue"] is None: trajectory_gaps.append(f"{row['revenue_label']}: not tagged for quarter ended {row['period_end']}.")
        if row["pat"] is None: trajectory_gaps.append(f"PAT: not tagged for quarter ended {row['period_end']}.")
        if row["revenue_label"] == "Revenue" and row["ebitda_margin_pct"] is None:
            trajectory_gaps.append(f"EBITDA margin: not tagged or inputs missing for quarter ended {row['period_end']}.")
    cards = {"financial_snapshot": {"items": snapshot,
             "gaps": [f"{item['label']}: not tagged or prerequisites unavailable; not shown." for item in snapshot if item["value"] is None]},
             "balance_sheet": {"items": balance, "as_of": latest["period_end"] if latest else None,
             "comparison_period": prior_march, "gaps": balance_gaps},
             "cash_quality": cash_quality, "trajectory": {"items": trajectory,
             "gaps": trajectory_gaps}}
    return {"symbol": company.symbol, "basis": basis, "mode": score["mode"], "cutoff": cutoff_utc,
            "available": score["available"], "scorecard": score, "cards": cards,
            "other_basis": {"name": alternate_basis, "period_end": alternate_period},
            "periods_by_basis": periods_by_basis,
            "gaps": score["gaps"]}
