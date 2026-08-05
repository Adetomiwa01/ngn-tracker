"""
NGN/USD tracker backend.

Purpose: control the exchangerate.host API request budget precisely.
Free tier: 100 requests/month. This backend calls the API at most once every
REFRESH_HOURS, regardless of how many times the page is loaded, and serves a
cached result the rest of the time. Every page load = 0 extra API calls.

Run:
    pip install flask requests
    export EXCHANGE_API_KEY=your_key_here
    python app.py

Then open http://localhost:5000
"""
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

API_KEY = os.environ.get("EXCHANGE_API_KEY", "")
BASE_URL = "https://api.exchangerate.host"
DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

# 100 requests/month budget. Refreshing every 8 hours = 3/day = ~90/month,
# leaving headroom. Change to 24 for a stricter 1/day = ~30/month budget.
REFRESH_HOURS = 8

DATA_DIR.mkdir(exist_ok=True)


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"readings": [], "last_fetch_unix": 0}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def fetch_live_rate():
    """One call to the live API. Only invoked when the cache is stale."""
    if not API_KEY:
        raise RuntimeError("EXCHANGE_API_KEY environment variable is not set.")
    res = requests.get(
        f"{BASE_URL}/live",
        params={"access_key": API_KEY, "source": "USD", "currencies": "NGN"},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    if not data.get("success"):
        raise RuntimeError(data.get("error", {}).get("info", "API call failed"))
    rate = (data.get("quotes") or {}).get("USDNGN") or (data.get("rates") or {}).get("NGN")
    if not rate:
        raise RuntimeError("NGN rate not found in API response")
    return rate


def get_current_data():
    """Returns cached data, refreshing from the API only if the cache is stale."""
    history = load_history()
    now = time.time()
    age_hours = (now - history["last_fetch_unix"]) / 3600

    if age_hours >= REFRESH_HOURS or not history["readings"]:
        try:
            rate = fetch_live_rate()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            readings = history["readings"]
            if readings and readings[-1]["date"] == today:
                readings[-1]["rate"] = rate
            else:
                readings.append({"date": today, "rate": rate})
            history["readings"] = readings[-180:]  # keep last ~6 months
            history["last_fetch_unix"] = now
            history["last_fetch_error"] = None
            save_history(history)
        except Exception as e:
            # Keep serving the last good cache if the live call fails
            history["last_fetch_error"] = str(e)

    return history


@app.route("/api/rate")
def api_rate():
    history = get_current_data()
    readings = history["readings"]
    return jsonify({
        "readings": readings,
        "current": readings[-1] if readings else None,
        "cache_age_seconds": time.time() - history["last_fetch_unix"],
        "next_refresh_in_hours": max(0, REFRESH_HOURS - (time.time() - history["last_fetch_unix"]) / 3600),
        "error": history.get("last_fetch_error"),
    })


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
