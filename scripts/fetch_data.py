#!/usr/bin/env python3
"""
Fetches ~12 months of daily closes for the portfolio's ETFs from Yahoo
Finance's public chart endpoint and writes data.json for the dashboard
to read.
 
This runs server-side (GitHub Actions), not in a browser, so browser CORS
restrictions do not apply here. We use Yahoo instead of Stooq because
Stooq's download endpoint enforces a per-IP daily rate limit that's
frequently already exhausted on GitHub's shared runner IP ranges.
"""
import json
import sys
import time
from datetime import datetime, timezone
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
 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
 
# Two Yahoo endpoints exist (query1/query2) that occasionally differ in
# availability; try both.
YAHOO_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
 
 
def yahoo_url(host: str, ticker: str) -> str:
    return (
        f"https://{host}/v8/finance/chart/{ticker}"
        f"?range=1y&interval=1d&includePrePost=false"
    )
 
 
def fetch_ticker(ticker: str, retries: int = 3):
    last_err = None
    for attempt in range(retries):
        host = YAHOO_HOSTS[attempt % len(YAHOO_HOSTS)]
        url = yahoo_url(host, ticker)
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            result = payload.get("chart", {}).get("result")
            if not result:
                err = payload.get("chart", {}).get("error")
                raise ValueError(f"No result in response ({err})")
            r0 = result[0]
            timestamps = r0.get("timestamp") or []
            closes_raw = (
                r0.get("indicators", {}).get("quote", [{}])[0].get("close") or []
            )
            if len(timestamps) < 2 or len(closes_raw) < 2:
                raise ValueError("Not enough rows returned")
 
            dates, closes = [], []
            for ts, c in zip(timestamps, closes_raw):
                if c is None:
                    continue  # skip non-trading / missing days
                dates.append(
                    datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                )
                closes.append(float(c))
 
            if len(closes) < 2:
                raise ValueError("All closes were null")
 
            return {"dates": dates, "closes": closes}
        except (HTTPError, URLError, ValueError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {ticker} after {retries} attempts: {last_err}")
 
 
def main():
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "holdings": {}}
 
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
        time.sleep(0.5)  # be polite between requests
 
    with open("data.json", "w") as f:
        json.dump(out, f, indent=2)
 
    print(f"\nWrote data.json with {len(out['holdings'])}/{len(HOLDINGS)} holdings.")
    if failures:
        print(f"Failed tickers: {failures}", file=sys.stderr)
 
 
if __name__ == "__main__":
    main()
 
