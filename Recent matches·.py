"""
recent_matches.py
Fetches CURRENT / ACTIVE cricket matches from CricketData.org (CricAPI)
and saves them as cricket_live_matches.csv — kept separate from the
Cricsheet-based historical tables.

Requires env var: CRICKETDATA_API_KEY
"""

import os
import sys
import csv
import requests

API_URL = "https://api.cricapi.com/v1/currentMatches"
OUTPUT_FILE = "cricket_live_matches.csv"


def fetch_current_matches(api_key: str) -> list:
    """Fetch all current matches from CricketData.org, filtered to only
    matches that are actively in progress (started, not ended)."""
    params = {"apikey": api_key, "offset": 0}

    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "success":
        raise RuntimeError(f"API error: {payload.get('status')} - {payload}")

    all_matches = payload.get("data", [])

    active = [
        m for m in all_matches
        if m.get("matchStarted") and not m.get("matchEnded")
    ]
    return active


def flatten_match(m: dict) -> dict:
    """Turn one match's JSON into a flat row for CSV."""
    scores = m.get("score", []) or []
    score_summary = " | ".join(
        f"{s.get('inning', '')}: {s.get('r', '?')}/{s.get('w', '?')} "
        f"({s.get('o', '?')} ov)"
        for s in scores
    )

    teams = m.get("teams", [])

    return {
        "match_id": m.get("id", ""),
        "match_name": m.get("name", ""),
        "match_type": m.get("matchType", ""),
        "status": m.get("status", ""),
        "venue": m.get("venue", ""),
        "date": m.get("date", ""),
        "dateTimeGMT": m.get("dateTimeGMT", ""),
        "team1": teams[0] if len(teams) > 0 else "",
        "team2": teams[1] if len(teams) > 1 else "",
        "score_summary": score_summary,
        "series_id": m.get("series_id", ""),
    }


def main():
    api_key = os.environ.get("CRICKETDATA_API_KEY")
    if not api_key:
        print("ERROR: CRICKETDATA_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    try:
        active_matches = fetch_current_matches(api_key)
    except Exception as e:
        print(f"ERROR fetching current matches: {e}", file=sys.stderr)
        sys.exit(1)

    rows = [flatten_match(m) for m in active_matches]

    fieldnames = [
        "match_id", "match_name", "match_type", "status", "venue",
        "date", "dateTimeGMT", "team1", "team2", "score_summary", "series_id",
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} active match(es) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
