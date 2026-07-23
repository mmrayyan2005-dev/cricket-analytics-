"""
Legacy Players (Pre-2008) patch for pipeline.py
=================================================
WHAT THIS DOES:
Builds a new file, cricket_legacy_pre2008.csv, listing official Wikipedia
career records (matches, runs, average, hundreds, wickets, bowling
average, best bowling) for every player whose international debut
predates 2008. Cricsheet's ball-by-ball archive barely covers these
careers, so instead of showing an empty or misleadingly low "Matches: 3"
for a 15-year veteran, this file gives the dashboard's new
"Legacy Players" page an official, sourced total to show instead.

SCOPE / HONEST LIMITATION:
This reuses the same ~150 "established international player" candidates
already being checked by build_coverage_gap_report() (players with 100+
Cricsheet-recorded matches in ODI/Test/T20I) — it does NOT do a fresh
Wikipedia search across every name in your archive, because that would
mean thousands of extra API calls per run and would make the Action
much slower. In practice this means: players who are well-represented
enough in Cricsheet to already be in that candidate list AND who debuted
before 2008 will show up here. A player whose ENTIRE career is missing
from Cricsheet (zero rows, never reaches the 100-match threshold in the
first place) won't be auto-discovered by this — those would need to be
added manually via manual_match_overrides.csv (which you already have
a mechanism for).

HOW TO INSTALL:
1. Replace your existing _fetch_wiki_infobox_stats() function with the
   version below (it now also extracts debut dates — same HTTP request,
   no extra cost).
2. Paste build_legacy_pre2008_report() anywhere below build_coverage_gap_report().
3. In main(), call it right after the coverage_gaps step, and add its
   output to files_to_save.
"""

import re
import pandas as pd


# ── STEP 1: replace your existing _fetch_wiki_infobox_stats with this ─────
def _fetch_wiki_infobox_stats(page_title, RAW_REPO_BASE=None, log=None):
    """Pull the Infobox cricketer wikitext and parse the per-format career
    stats table (column1/matches1/runs1/bat avg1/100s-50s1/wickets1/
    bowl avg1/best bowling1, column2/..., etc), PLUS the player's debut
    date fields (debutdate / odidebutdate / testdebutdate / t20idebutdate),
    used to determine if their career predates 2008.
    Returns {format_label: {"matches":.., "runs":.., "average":.., "hundreds":..,
             "wickets":.., "bowl_average":.., "best_bowling":..}}
    plus a separate top-level "debut_year" (earliest debut across formats)."""
    import requests
    try:
        ir = requests.get("https://en.wikipedia.org/w/api.php",
            params={"action": "query", "titles": page_title, "prop": "revisions",
                    "rvprop": "content", "rvslots": "main", "format": "json", "rvsection": 0},
            timeout=10, headers={"User-Agent": "CricketAnalyticsPipeline/1.0"})
        ir.raise_for_status()
        pages = ir.json().get("query", {}).get("pages", {})
        wt = next(iter(pages.values())).get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        if not wt:
            return {}, None

        _fmt_aliases = {
            "ODI":  ["odi", "one day international", "one-day international"],
            "Test": ["test"],
            "T20I": ["t20i", "twenty20 international", "t20 international"],
        }
        out = {}
        for i in range(1, 8):
            col_m = re.search(rf"\|\s*column{i}\s*=\s*([^\n\|]{{2,40}})", wt, re.IGNORECASE)
            if not col_m:
                continue
            col_label = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", col_m.group(1)).strip().lower()
            fmt_match = next((fmt for fmt, aliases in _fmt_aliases.items()
                              if any(a in col_label for a in aliases)), None)
            if not fmt_match or fmt_match in out:
                continue

            def field(names):
                for n in names:
                    m = re.search(rf"\|\s*{re.escape(n)}{i}\s*=\s*([^\n\|]{{1,20}})", wt, re.IGNORECASE)
                    if m:
                        v = re.sub(r"<[^>]+>", "", m.group(1)).replace(",", "").strip()
                        if v:
                            return v
                return None

            def to_num(v):
                if v is None:
                    return None
                m = re.search(r"[\d.]+", v)
                return float(m.group()) if m else None

            matches_v = to_num(field(["matches"]))
            runs_v = to_num(field(["runs"]))
            avg_v = to_num(field(["bat avg", "batting average", "bat_avg"]))
            hs50_v = field(["100s/50s", "100s_50s"])
            hundreds = None
            if hs50_v:
                parts = hs50_v.split("/")
                if parts and parts[0].strip().replace(".", "").isdigit():
                    hundreds = int(float(parts[0].strip()))
            wickets_v = to_num(field(["wickets"]))
            bowl_avg_v = to_num(field(["bowl avg", "bowling average", "bowl_avg"]))
            best_bowling_v = field(["best bowling", "bbi", "best_bowling"])

            if matches_v is None:
                continue
            out[fmt_match] = {
                "matches": matches_v, "runs": runs_v,
                "average": avg_v, "hundreds": hundreds,
                "wickets": wickets_v, "bowl_average": bowl_avg_v,
                "best_bowling": best_bowling_v,
            }

        # ── Debut date extraction (new) ──
        # Cricket infobox debut fields aren't per-column-indexed like the
        # stats table — they're single top-level fields, one per format,
        # e.g. |testdebutdate= 12 December 2003 |testdebutyear= 2003
        debut_years = []
        for prefix in ["odidebutyear", "testdebutyear", "t20idebutyear", "debutyear"]:
            m = re.search(rf"\|\s*{prefix}\s*=\s*([12][0-9]{{3}})", wt, re.IGNORECASE)
            if m:
                debut_years.append(int(m.group(1)))
        if not debut_years:
            # fall back to parsing a year out of the free-text debut date fields
            for prefix in ["odidebutdate", "testdebutdate", "t20idebutdate", "debutdate"]:
                m = re.search(rf"\|\s*{prefix}\s*=\s*([^\n\|]{{4,40}})", wt, re.IGNORECASE)
                if m:
                    ym = re.search(r"(19|20)\d{2}", m.group(1))
                    if ym:
                        debut_years.append(int(ym.group(0)))
        earliest_debut = min(debut_years) if debut_years else None

        return out, earliest_debut
    except Exception as e:
        if log:
            log.warning(f"Wiki infobox parse failed for '{page_title}': {e}")
        return {}, None


# ── STEP 2: new function — paste below build_coverage_gap_report() ────────
LEGACY_DEBUT_CUTOFF_YEAR = 2008

def build_legacy_pre2008_report(batting_by_format, bowling_by_format, log,
                                  wiki_search_title_fn, min_matches=100):
    """For every established international player (100+ Cricsheet matches,
    same candidate pool as the coverage-gap check), fetch their Wikipedia
    debut year + official career totals, and keep only those whose
    earliest recorded debut is before LEGACY_DEBUT_CUTOFF_YEAR (2008).
    Returns a long-format DataFrame: one row per player/format, with both
    batting and bowling official totals side by side (a bowler's row will
    just have blank runs/average, and vice versa)."""
    import time

    candidates = batting_by_format[batting_by_format["matches"] >= min_matches][["striker", "format"]].rename(
        columns={"striker": "player"})
    bowl_candidates = bowling_by_format[bowling_by_format["matches"] >= min_matches][["bowler", "format"]].rename(
        columns={"bowler": "player"})
    all_players = sorted(set(candidates["player"]) | set(bowl_candidates["player"]))
    log.info(f"Legacy pre-2008 check: {len(all_players)} established player(s) to verify debut year for")

    rows = []
    page_cache, stats_cache, debut_cache = {}, {}, {}

    for player in all_players:
        if player not in page_cache:
            time.sleep(0.3)
            page_cache[player] = wiki_search_title_fn(player)
        title = page_cache[player]
        if not title:
            continue
        if player not in stats_cache:
            stats_cache[player], debut_cache[player] = _fetch_wiki_infobox_stats(title, log=log)
        career_stats = stats_cache[player]
        debut_year = debut_cache[player]

        if debut_year is None or debut_year >= LEGACY_DEBUT_CUTOFF_YEAR:
            continue  # not a legacy (pre-2008) player, or debut year unknown — skip rather than guess

        for fmt, stats in career_stats.items():
            rows.append({
                "player": player, "format": fmt, "debut_year": debut_year,
                "matches": stats.get("matches"), "runs": stats.get("runs"),
                "average": stats.get("average"), "hundreds": stats.get("hundreds"),
                "wickets": stats.get("wickets"), "bowl_average": stats.get("bowl_average"),
                "best_bowling": stats.get("best_bowling"), "wiki_page": title,
            })

    out = pd.DataFrame(rows)
    log.info(f"Legacy pre-2008 report: {len(out):,} player/format record(s) "
             f"across {out['player'].nunique() if not out.empty else 0} player(s) with debut before "
             f"{LEGACY_DEBUT_CUTOFF_YEAR}")
    return out


# ── STEP 3: in main(), after the coverage_gaps step, add: ─────────────────
#
#   log.info("Checking for established players whose careers began before 2008...")
#   legacy_pre2008 = build_legacy_pre2008_report(
#       batting_by_format, bowling_by_format, log, _wiki_search_title)
#
# ── and add this line to files_to_save: ────────────────────────────────────
#
#   "cricket_legacy_pre2008.csv": legacy_pre2008,
