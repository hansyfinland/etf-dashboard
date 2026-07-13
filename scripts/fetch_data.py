#!/usr/bin/env python3
"""
Fetches ~13 months of daily closes for the portfolio's ETFs from Stooq
and writes data.json for the dashboard to read.

This runs server-side (GitHub Actions), not in a browser, so the CORS
restriction that blocks client-side fetch() calls does not apply here.
"""
import csv
import io
import json
import sys
import time
from datetime import date, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOLDINGS = [
    {"t": "SPY",  "w": 13, "cls": "Equities"},
    {"t": "QQQ",  "w": 5,  "cls": "Equities"},
    {"t": "IWM",  "w": 4,  "cls": "Equities"},
    {"t": "USMV", "w": 6,  "cls": "Equities"},
    {"t": "EFA",  "w": 8,  "cls": "Equities"},
    {"t": "EEMV", "w": 4,  "cls": "Equities"},
    {"t": "VGIT", "w": 5,  "cls": "Fixed Income"},
    {"t": "VTIP", "w": 10, "cls": "Fixed Income"},
    {"t": "SGOV", "w": 6,  "cls": "Fixed Income"},
    {"t": "GLD",  "w": 14, "cls": "Real Assets"},
    {"t": "PDBC", "w": 7,  "cls": "Real Assets"},
    {"t": "DBMF", "w": 12, "cls": "Alternatives"},
    {"t": "KMLM", "w": 6,  "cls": "Alternatives"},
]

# A normal browser-style User-Agent avoids being blocked as an obvious bot.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def stooq_url(ticker: str) -> str:
    d2 = date.today()
    d1 = d2 - timedelta(days=395)  # ~13 months, gives buffer for the 12M window
    fmt = lambda d: d.strftime("%Y%m%d")
    return (
        f"https://stooq.com/q/d/l/?s={ticker.lower()}.us"
        f"&d1={fmt(d1)}&d2={fmt(d2)}&i=d"
    )


def fetch_ticker(ticker: str, retries: int = 3):
    url = stooq_url(ticker)
    last_err = None
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(raw))
            rows = [r for r in reader if r.get("Close")]
            if len(rows) < 2:
                raise ValueError(f"Not enough rows returned for {ticker}")
            dates = [r["Date"] for r in rows]
            closes = [float(r["Close"]) for r in rows]
            return {"dates": dates, "closes": closes}
        except (HTTPError, URLError, ValueError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {ticker} after {retries} attempts: {last_err}")


def main():
    out = {"generated_at": None, "holdings": {}}
    from datetime import datetime, timezone
    out["generated_at"] = datetime.now(timezone.utc).isoformat()

    failures = []
    for h in HOLDINGS:
        try:
            series = fetch_ticker(h["t"])
            closes = series["closes"]
            price = closes[-1]
            prev = closes[-2]
            first = closes[0]
            out["holdings"][h["t"]] = {
                "weight": h["w"],
                "class": h["cls"],
                "dates": series["dates"],
                "closes": closes,
                "price": price,
                "day_change_pct": (price - prev) / prev * 100,
                "ret_12m_pct": (price - first) / first * 100,
            }
            print(f"OK   {h['t']}: {len(closes)} points, last close {price}")
        except Exception as e:
            failures.append(h["t"])
            print(f"FAIL {h['t']}: {e}", file=sys.stderr)
        time.sleep(1)  # be polite between requests

    with open("data.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nWrote data.json with {len(out['holdings'])}/{len(HOLDINGS)} holdings.")
    if failures:
        print(f"Failed tickers: {failures}", file=sys.stderr)
        # Don't hard-fail the whole workflow over one bad ticker;
        # the dashboard will show 'n/a' for anything missing.


if __name__ == "__main__":
    main()
