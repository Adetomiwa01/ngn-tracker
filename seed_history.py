"""
One-time backfill script. Run this locally BEFORE deploying (or any time you
want to seed history.json with recent days), not on every server request.

This does NOT run automatically on the server -- it's a manual, one-off tool
so the backfill calls never eat into your ongoing 100/month budget.

Usage:
    export EXCHANGE_API_KEY=your_key_here
    python seed_history.py

Uses the /historical endpoint (one date per call) since /timeframe (date-range,
one call for many dates) is often gated to paid plans. Costs up to `DAYS` API
calls, once.
"""
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_KEY = os.environ.get("EXCHANGE_API_KEY", "")
BASE_URL = "https://api.exchangerate.host"
DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

DAYS = 10  # how many past days to backfill -- costs this many API calls, once


def fetch_historical(date_str):
    res = requests.get(
        f"{BASE_URL}/historical",
        params={"access_key": API_KEY, "date": date_str, "source": "USD", "currencies": "NGN"},
        timeout=10,
    )
    if not res.ok:
        return None
    data = res.json()
    if not data.get("success"):
        return None
    return (data.get("quotes") or {}).get("USDNGN") or (data.get("rates") or {}).get("NGN")


def main():
    if not API_KEY:
        raise SystemExit("Set EXCHANGE_API_KEY first: export EXCHANGE_API_KEY=your_key_here")

    DATA_DIR.mkdir(exist_ok=True)

    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    else:
        history = {"readings": [], "last_fetch_unix": 0}

    existing_dates = {r["date"] for r in history["readings"]}
    today = datetime.now(timezone.utc).date()
    added = 0

    for i in range(DAYS, 0, -1):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if date_str in existing_dates:
            print(f"  {date_str}: already have this, skipping")
            continue
        rate = fetch_historical(date_str)
        if rate is None:
            print(f"  {date_str}: no data / call failed, skipping")
            continue
        history["readings"].append({"date": date_str, "rate": rate})
        print(f"  {date_str}: {rate:.2f}  (added)")
        added += 1

    history["readings"].sort(key=lambda r: r["date"])
    history["readings"] = history["readings"][-180:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nDone. Added {added} new readings. Total readings: {len(history['readings'])}")
    print("Note: this used up to", DAYS, "API calls, one time. Your regular server")
    print("caching (app.py) is unaffected and continues on its normal refresh schedule.")


if __name__ == "__main__":
    main()
