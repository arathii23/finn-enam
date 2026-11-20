from datetime import date, datetime, timezone

from finn.calendar_feed import FEEDS, render_calendar, select_events


def test_calendar_folds_utf8_escapes_and_keeps_stable_deduplicated_ids():
    feeds = [
        (FEEDS[0], [{"symbol": "INFY", "date": "18-Nov-2026", "purpose": "Financial Results", "bm_desc": "Results"}]),
        (FEEDS[1], [{"bm_symbol": "INFY", "bm_date": "18-Nov-2026", "bm_purpose": "Board Meeting",
                     "bm_desc": "Board meeting for results, followed by Q&A; " + "₹" * 30,
                     "attachment": "https://nsearchives.nseindia.in/corporate/approved.pdf"}]),
        (FEEDS[2], [{"symbol": "INFY", "recDate": "20-Nov-2026", "subject": "Dividend"},
                    {"symbol": "OTHER", "recDate": "20-Nov-2026", "subject": "Dividend"},
                    {"symbol": "INFY", "recDate": "16-Nov-2026", "subject": "Old dividend"}]),
    ]
    events = select_events(feeds, ["INFY"], date(2026, 11, 17))
    first = render_calendar(events, datetime(2026, 11, 17, tzinfo=timezone.utc))
    later = render_calendar(events, datetime(2026, 11, 18, tzinfo=timezone.utc))
    assert first.count(b"BEGIN:VEVENT") == 2
    assert b"DTSTART;VALUE=DATE:20261118\r\nDTEND;VALUE=DATE:20261119" in first
    assert b"board meeting" not in first
    assert b"results\\, followed by Q&A\\;" in first
    assert b"https://nsearchives.nseindia.in/corporate/approved.pdf" in first
    assert [row for row in first.splitlines() if row.startswith(b"UID:")] == [row for row in later.splitlines() if row.startswith(b"UID:")]
    assert all(len(row) <= 75 for row in first.splitlines())
