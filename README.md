# NGN/USD Tracker (Python backend)

## Why a backend

The free exchangerate.host plan allows 100 requests/month. A pure client-side version
re-fetches on every page load, which burns through that fast if you check it often. This
backend calls the API **on a fixed schedule only** (every `REFRESH_HOURS`, default 8 — about
90 calls/month, safely under the limit) and caches the result in `data/history.json`.
Reloading the page costs **zero** additional API requests — it just reads the cache.

Change `REFRESH_HOURS` in `app.py` to `24` for a stricter ~30 requests/month budget with daily
updates instead.

## Setup

```bash
pip install -r requirements.txt
export EXCHANGE_API_KEY=your_key_here      # on Windows (cmd): set EXCHANGE_API_KEY=your_key_here
python app.py
```

Open **http://localhost:5000**

## How the caching works

- First request: no cache exists, so it calls the API once, stores the reading, and starts
  building `data/history.json`.
- Every request after that: if the cache is younger than `REFRESH_HOURS`, it's served as-is,
  no API call made.
- Once the cache goes stale, the *next* page load triggers exactly one API call to refresh it
  — not one call per visitor, one call total until the next refresh window.
- If the API call fails (rate limit, network issue, bad key), the last good cached data keeps
  being served, with an error note shown on the page — the tracker never goes blank because of
  a failed refresh.

## Files

```
ngn-tracker-v3/
├── app.py              # Flask backend, caching logic
├── requirements.txt
├── static/index.html   # frontend, plain/utilitarian design, calls only /api/rate
└── data/history.json   # generated on first run — your accumulating rate history
```

## Deploying beyond localhost

To make this reachable outside your own machine (e.g. to check it from your phone), it needs
hosting somewhere that can keep a Python process running — Render, Railway, PythonAnywhere,
or similar all have free tiers suited to a small Flask app like this. Set `EXCHANGE_API_KEY`
as an environment variable on whichever platform you choose, same as locally.
