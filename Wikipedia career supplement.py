"""
Pulls career-summary stats (matches/runs/average/wickets per format) straight
from a player's Wikipedia infobox, via Wikipedia's OFFICIAL API — the same
endpoint your app already uses for player bios (en.wikipedia.org/w/api.php).

WHY WIKIPEDIA INSTEAD OF STATSGURU: Statsguru's actual data-table pages
(anything with template=results) are disallowed by ESPNcricinfo's robots.txt.
Wikipedia is the opposite: it has an official, documented API meant exactly
for this kind of programmatic access, its content is CC BY-SA licensed for
reuse, and — as verified — its cricketer articles carry a near-universal
"International career statistics" infobox table with exactly the numbers
this app needs (matches, runs, average, 100s/50s, wickets, etc. per format).

WHAT THIS SCRIPT DOES NOT DO: it doesn't try to get ball-by-ball detail
(dot balls, boundary %, etc.) — Wikipedia doesn't have that, only Cricsheet
does. This is strictly for CAREER TOTALS, to close the pre-2002 gap (and any
other gap, like Afghanistan) where Cricsheet has nothing at all.

MUST BE RUN SOMEWHERE WITH REAL INTERNET ACCESS (e.g. your GitHub Actions
runner) — it cannot run inside Claude's sandbox, which is locked to a fixed
domain allowlist that doesn't include wikipedia.org.

Usage:
    python wikipedia_career_supplement.py "Sachin Tendulkar" "Shahid Afridi" ...
    # or, to run against every player already in your batting_by_format.csv:
    python wikipedia_career_supplement.py --from-csv cricket_batting_by_format.csv
"""
import sys
import time
import re
import requests
import pandas as pd

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "cricket-analytics-personal-project/1.0 (contact: mmrayyan2005-dev)"}


def get_wikitext(title):
    """Fetch raw wikitext for a page — official API, same pattern the app
    already uses for bios, just requesting wikitext instead of the summary."""
    r = requests.get(WIKI_API, params={
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "redirects": 1,
    }, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        return None
    return data["parse"]["wikitext"]["*"]


def parse_infobox_career_stats(wikitext):
    """Parses the {{Infobox cricketer}} 'International career statistics'
    sub-template, which typically looks like:
        |columns = 4
        |column1 = Test | column2 = ODI | column3 = T20I
        |matches1 = 200 | matches2 = 463 | matches3 = 1
        |runs1 = 15921 | runs2 = 18426 | runs3 = 10
        |bat avg1 = 53.78 | ...
        |100s/50s1 = 51/68 | ...
    Field names vary slightly across articles (this template has evolved
    over the years), so this pulls whatever's present rather than assuming
    every field exists.
    """
    if not wikitext:
        return {}
    fields = ["matches", "runs", "bat avg", "100s/50s", "top score",
              "wickets", "bowl avg", "5w", "10w", "best bowling"]
    result = {}

    def _clean_col(v):
        v = v.strip()
        m = re.search(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", v)
        return m.group(2).strip() if m else v

    # column labels (Test/ODI/T20I/FC/LA) are numbered column1, column2, ...
    # Captured to end-of-line (not stopping at internal pipes), since column
    # values are usually wikilinks like [[Test cricket|Test]] which contain
    # their own pipe character.
    columns = dict(re.findall(r"\|\s*column(\d)\s*=\s*([^\n]+)", wikitext))
    columns = {k: _clean_col(v) for k, v in columns.items()}
    for field in fields:
        # e.g. |matches1 = 200 |matches2 = 463
        matches = re.findall(rf"\|\s*{re.escape(field)}(\d)\s*=\s*([^\|\n]+)", wikitext)
        for col_num, value in matches:
            fmt = columns.get(col_num, f"col{col_num}")
            result.setdefault(fmt, {})[field] = value.strip()
    return result


def fetch_player_career(title):
    wikitext = get_wikitext(title)
    stats = parse_infobox_career_stats(wikitext)
    if not stats:
        print(f"  no infobox career table found for '{title}' — may need manual entry")
    return stats


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--from-csv":
        names = pd.read_csv(sys.argv[2])["striker"].dropna().unique().tolist()
    else:
        names = sys.argv[1:]

    rows = []
    for i, name in enumerate(names):
        print(f"[{i+1}/{len(names)}] {name}")
        stats = fetch_player_career(name)
        for fmt, values in stats.items():
            row = {"player": name, "format": fmt, **values, "source": "wikipedia-infobox"}
            rows.append(row)
        time.sleep(0.5)  # be a polite, low-volume client — this is a personal project, not a crawler

    out = pd.DataFrame(rows)
    out.to_csv("wikipedia_career_supplement.csv", index=False)
    print(f"\nWrote wikipedia_career_supplement.csv ({len(out)} player-format rows, "
          f"{len(names)} players queried).")
    print("Review it, then decide how to merge these career TOTALS alongside "
          "(not blended into) your Cricsheet-derived ball-by-ball stats — "
          "they're a different kind of number and should stay labeled as such.")


if __name__ == "__main__":
    main()
