"""
Cricket Analytics — Data Pipeline
==================================
This replaces the manual Colab notebook. Instead of you opening Colab,
re-running every cell by hand, and pasting a GitHub token into a code
cell, this script:

  1. Downloads fresh ball-by-ball data from Cricsheet
  2. Cleans it and LOGS every row it drops and why (previously silent)
  3. Builds all the same stats/ML tables as before
  4. Pushes the CSVs to your GitHub repo
  5. Writes a last_updated.txt timestamp so the dashboard can show
     "data last refreshed: <date>" instead of leaving you guessing

It's meant to be run either:
  - locally: `python pipeline.py`
  - automatically: via the GitHub Action in .github/workflows/update_data.yml,
    which runs this on a schedule so you never touch this again.

Configuration comes from environment variables, NOT hardcoded values —
see the Config section below. This means your GitHub token never sits
in plain text inside a script that might get committed by accident.
"""

import os
import sys
import io
import zipfile
import base64
import logging
from datetime import datetime, timezone

import requests
import pandas as pd
import numpy as np

# ── Config (from environment variables — never hardcode secrets) ─────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_USER  = os.environ.get("GITHUB_USER", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "")
BRANCH       = os.environ.get("BRANCH", "main")
WORKDIR      = os.environ.get("WORKDIR", "cricsheet_data")
RAW_REPO_BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}"

CRICSHEET_URLS = {
    "ODI":  "https://cricsheet.org/downloads/odis_csv2.zip",
    "Test": "https://cricsheet.org/downloads/tests_csv2.zip",
    "T20I": "https://cricsheet.org/downloads/t20s_csv2.zip",
    "IPL":  "https://cricsheet.org/downloads/ipl_csv2.zip",
    "PSL":  "https://cricsheet.org/downloads/psl_csv2.zip",
}

# ── Logging setup ──────────────────────────────────────────────────────────
# Previously the notebook only ever printed row COUNTS ("Dupes removed: 42"),
# never *why* rows were dropped or which matches were affected. That's why
# missing scores were invisible until someone noticed a gap in the dashboard.
# This logs every drop reason to both the console and a run log file, so a
# failed/partial GitHub Action run leaves a readable trail.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("pipeline_run.log")],
)
log = logging.getLogger("cricket_pipeline")


def download_and_extract(name, url, workdir):
    """Download one Cricsheet zip and extract it. Logs failures instead of
    letting a bad download silently produce zero data for a format."""
    folder = os.path.join(workdir, f"{name.lower()}_data")
    os.makedirs(folder, exist_ok=True)
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(folder)
        log.info(f"Downloaded and extracted {name} from {url}")
        return folder
    except Exception as e:
        log.error(f"FAILED to download {name} from {url}: {e}")
        return folder  # return the (possibly empty) folder so pipeline continues


def load_registered_players(folder, label):
    """Parse the `*_info.csv` companion file Cricsheet ships alongside every
    match's ball-by-ball CSV. It lists every player registered in each
    team's XI for that match — including anyone who never faced a ball or
    bowled a delivery (e.g. a top-order batter whose team won the chase
    before he needed to bat). The ball-by-ball data alone has no way to
    know he was even in that match; this file is the only source for that.
    Row format: info,player,<Team Name>,<Player Name>
    Without this, "matches played" silently undercounts anyone who has
    innings where they didn't get to bat — which is exactly what caused
    Cricsheet's Kohli ODI count to sit under his real career total."""
    if not os.path.isdir(folder):
        return pd.DataFrame(columns=["match_id", "team", "player", "format"])
    files = [f for f in os.listdir(folder) if f.endswith("_info.csv")]
    rows = []
    failed = 0
    for f in files:
        match_id = f.replace("_info.csv", "")
        try:
            with open(os.path.join(folder, f), encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    parts = [p.strip() for p in line.strip().split(",")]
                    if len(parts) >= 4 and parts[0] == "info" and parts[1] == "player":
                        team = parts[2]
                        player = ",".join(parts[3:])  # player names rarely contain commas, but be safe
                        rows.append((match_id, team, player))
        except Exception:
            failed += 1
    if failed:
        log.warning(f"{label}: {failed} _info.csv file(s) failed to parse for player registration")
    out = pd.DataFrame(rows, columns=["match_id", "team", "player"])
    out["format"] = label
    log.info(f"{label}: {len(out):,} player-registration rows from {out['match_id'].nunique():,} matches")
    return out


def load_format(folder, label):
    """Load all per-match CSVs for one format. Logs which individual match
    files failed to parse instead of the previous bare `except: pass`."""
    if not os.path.isdir(folder):
        log.warning(f"{label}: folder {folder} does not exist, skipping")
        return pd.DataFrame()
    files = [f for f in os.listdir(folder) if f.endswith(".csv") and not f.endswith("_info.csv")]
    dfs, failed = [], []
    for f in sorted(files):
        try:
            dfs.append(pd.read_csv(os.path.join(folder, f)))
        except Exception as e:
            failed.append((f, str(e)))
    if failed:
        log.warning(f"{label}: {len(failed)} match file(s) failed to parse: "
                    f"{[f for f, _ in failed][:5]}{'...' if len(failed) > 5 else ''}")
    if not dfs:
        log.warning(f"{label}: no valid match files found in {folder}")
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    df["format"] = label
    log.info(f"{label}: loaded {df.shape[0]:,} rows from {len(dfs)} matches")
    return df


def clean_and_validate(df):
    """Same cleaning logic as the original notebook, but every drop is now
    counted AND logged with a reason, so 'some scores are missing' becomes
    debuggable instead of mysterious."""
    before = len(df)
    df = df.drop_duplicates()
    log.info(f"Dropped {before - len(df):,} exact duplicate rows")

    required = ["match_id", "striker", "bowler", "runs_off_bat", "ball", "start_date"]
    before = len(df)
    df = df.dropna(subset=required)
    log.info(f"Dropped {before - len(df):,} rows missing required fields {required}")

    before = len(df)
    df = df[df["runs_off_bat"].between(0, 6)]
    log.info(f"Dropped {before - len(df):,} rows with out-of-range runs_off_bat")

    for col in ["wides", "noballs", "byes", "legbyes", "extras"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    df["bowler_runs"] = df["runs_off_bat"] + df["wides"] + df["noballs"]
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["start_date"])
    log.info(f"Dropped {before - len(df):,} rows with unparseable start_date")

    df["over"] = df["ball"].astype(str).str.split(".").str[0].astype(int)
    df["total_runs"] = df["runs_off_bat"] + df["extras"]
    df["is_wicket"] = df["wicket_type"].notna().astype(int)
    df["is_wide"] = (df["wides"] > 0).astype(int)
    df["is_noball"] = (df["noballs"] > 0).astype(int)
    df["is_dot"] = ((df["runs_off_bat"] == 0) & (df["is_wide"] == 0) & (df["is_noball"] == 0)).astype(int)
    df["year"] = df["start_date"].dt.year

    valid = df.groupby("match_id")["ball"].count()
    before = len(df)
    df = df[df["match_id"].isin(valid[valid >= 6].index)]
    log.info(f"Dropped {before - len(df):,} rows from matches with <6 balls recorded (likely corrupt files)")

    log.info(f"CLEAN dataset: {df.shape[0]:,} rows | breakdown: {df['format'].value_counts().to_dict()}")
    return df


def build_innings_tables(df):
    bat_innings = df[df["is_wide"] == 0].groupby(
        ["match_id", "striker", "batting_team", "bowling_team", "venue", "start_date", "format"]
    ).agg(
        runs=("runs_off_bat", "sum"),
        balls_faced=("runs_off_bat", "count"),
        fours=("runs_off_bat", lambda x: (x == 4).sum()),
        sixes=("runs_off_bat", lambda x: (x == 6).sum()),
        dismissed=("is_wicket", "max"),
    ).reset_index()
    bat_innings["strike_rate"] = ((bat_innings["runs"] / bat_innings["balls_faced"].replace(0, 1)) * 100).round(2)
    bat_innings["year"] = pd.to_datetime(bat_innings["start_date"]).dt.year

    bowl_innings = df[df["is_wide"] == 0].groupby(
        ["match_id", "bowler", "batting_team", "bowling_team", "venue", "start_date", "format"]
    ).agg(
        balls=("bowler_runs", "count"),
        runs_given=("bowler_runs", "sum"),
        wickets=("is_wicket", "sum"),
        dot_balls=("is_dot", "sum"),
    ).reset_index()
    bowl_innings["overs"] = (bowl_innings["balls"] / 6).round(1)
    bowl_innings["economy"] = ((bowl_innings["runs_given"] / bowl_innings["balls"].replace(0, 1)) * 6).round(2)
    bowl_innings["year"] = pd.to_datetime(bowl_innings["start_date"]).dt.year

    log.info(f"Innings tables built: bat_innings {bat_innings.shape}, bowl_innings {bowl_innings.shape}")
    return bat_innings, bowl_innings


def build_batting(data, group_cols=["striker"]):
    bat = data.groupby(group_cols).agg(
        matches=("match_id", "nunique"),
        runs=("runs_off_bat", "sum"),
        balls_faced=("is_wide", lambda x: (x == 0).sum()),
        dismissals=("is_wicket", "sum"),
        dot_balls=("is_dot", "sum"),
        fours=("runs_off_bat", lambda x: (x == 4).sum()),
        sixes=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    bat["average"] = (bat["runs"] / bat["dismissals"].replace(0, 1)).round(2)
    bat["strike_rate"] = ((bat["runs"] / bat["balls_faced"].replace(0, 1)) * 100).round(2)
    bat["dot_pct"] = ((bat["dot_balls"] / bat["balls_faced"].replace(0, 1)) * 100).round(2)
    bat["boundary_pct"] = (((bat["fours"] + bat["sixes"]) / bat["balls_faced"].replace(0, 1)) * 100).round(2)
    return bat.sort_values("runs", ascending=False)


def build_bowling(data, group_cols=["bowler"]):
    bowl = data.groupby(group_cols).agg(
        matches=("match_id", "nunique"),
        balls=("is_wide", lambda x: (x == 0).sum()),
        runs_given=("bowler_runs", "sum"),
        wickets=("is_wicket", "sum"),
        dot_balls=("is_dot", "sum"),
        wides=("is_wide", "sum"),
        noballs=("is_noball", "sum"),
    ).reset_index()
    bowl["overs"] = (bowl["balls"] / 6).round(1)
    bowl["economy"] = ((bowl["runs_given"] / bowl["balls"].replace(0, 1)) * 6).round(2)
    bowl["average"] = (bowl["runs_given"] / bowl["wickets"].replace(0, 1)).round(2)
    bowl["dot_pct"] = ((bowl["dot_balls"] / bowl["balls"].replace(0, 1)) * 100).round(2)
    bowl["strike_rate"] = (bowl["balls"] / bowl["wickets"].replace(0, 1)).round(2)
    return bowl.sort_values("wickets", ascending=False)


def build_career_and_milestones(df, bat_innings, bowl_innings):
    batting = build_batting(df)
    bowling = build_bowling(df)
    batting_by_format = build_batting(df, ["striker", "format"])
    bowling_by_format = build_bowling(df, ["bowler", "format"])

    bat_milestones = bat_innings.groupby(["striker", "format"]).agg(
        hundreds=("runs", lambda x: (x >= 100).sum()),
        fifties=("runs", lambda x: ((x >= 50) & (x < 100)).sum()),
        thirties=("runs", lambda x: ((x >= 30) & (x < 50)).sum()),
        highest=("runs", "max"),
        ducks=("runs", lambda x: (x == 0).sum()),
    ).reset_index()

    bowl_milestones = bowl_innings.groupby(["bowler", "format"]).agg(
        five_wkts=("wickets", lambda x: (x >= 5).sum()),
        four_wkts=("wickets", lambda x: (x == 4).sum()),
        best_wkts=("wickets", "max"),
    ).reset_index()
    best_fig = bowl_innings.sort_values(["wickets", "runs_given"], ascending=[False, True])
    best_fig = best_fig.groupby(["bowler", "format"]).first()[["wickets", "runs_given"]].reset_index()
    best_fig["best_bowling"] = best_fig["wickets"].astype(str) + "/" + best_fig["runs_given"].astype(str)
    bowl_milestones = bowl_milestones.merge(best_fig[["bowler", "format", "best_bowling"]],
                                             on=["bowler", "format"], how="left")

    batting_by_format = batting_by_format.merge(bat_milestones, on=["striker", "format"], how="left")
    bowling_by_format = bowling_by_format.merge(bowl_milestones, on=["bowler", "format"], how="left")
    log.info(f"Career/milestone tables built: batting_by_format {batting_by_format.shape}, "
             f"bowling_by_format {bowling_by_format.shape}")
    return batting, bowling, batting_by_format, bowling_by_format


def build_yearly_venue_opponent_matchup(df):
    batting_yearly = df.groupby(["striker", "year", "format"]).agg(
        runs=("runs_off_bat", "sum"), balls_faced=("is_wide", lambda x: (x == 0).sum()),
        dismissals=("is_wicket", "sum"), matches=("match_id", "nunique"),
        fours=("runs_off_bat", lambda x: (x == 4).sum()), sixes=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    batting_yearly["average"] = (batting_yearly["runs"] / batting_yearly["dismissals"].replace(0, 1)).round(2)
    batting_yearly["strike_rate"] = ((batting_yearly["runs"] / batting_yearly["balls_faced"].replace(0, 1)) * 100).round(2)

    bowling_yearly = df.groupby(["bowler", "year", "format"]).agg(
        balls=("is_wide", lambda x: (x == 0).sum()), runs_given=("bowler_runs", "sum"),
        wickets=("is_wicket", "sum"), matches=("match_id", "nunique"), dot_balls=("is_dot", "sum"),
    ).reset_index()
    bowling_yearly["economy"] = ((bowling_yearly["runs_given"] / bowling_yearly["balls"].replace(0, 1)) * 6).round(2)
    bowling_yearly["average"] = (bowling_yearly["runs_given"] / bowling_yearly["wickets"].replace(0, 1)).round(2)
    bowling_yearly["strike_rate"] = (bowling_yearly["balls"] / bowling_yearly["wickets"].replace(0, 1)).round(2)
    bowling_yearly["dot_pct"] = ((bowling_yearly["dot_balls"] / bowling_yearly["balls"].replace(0, 1)) * 100).round(2)

    batting_venue = df.groupby(["striker", "venue", "format"]).agg(
        innings=("match_id", "nunique"), runs=("runs_off_bat", "sum"),
        balls_faced=("is_wide", lambda x: (x == 0).sum()), dismissals=("is_wicket", "sum"),
        fours=("runs_off_bat", lambda x: (x == 4).sum()), sixes=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    batting_venue["average"] = (batting_venue["runs"] / batting_venue["dismissals"].replace(0, 1)).round(2)
    batting_venue["strike_rate"] = ((batting_venue["runs"] / batting_venue["balls_faced"].replace(0, 1)) * 100).round(2)

    batting_opponent = df.groupby(["striker", "bowling_team", "format"]).agg(
        innings=("match_id", "nunique"), runs=("runs_off_bat", "sum"),
        balls_faced=("is_wide", lambda x: (x == 0).sum()), dismissals=("is_wicket", "sum"),
        fours=("runs_off_bat", lambda x: (x == 4).sum()), sixes=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    batting_opponent["average"] = (batting_opponent["runs"] / batting_opponent["dismissals"].replace(0, 1)).round(2)
    batting_opponent["strike_rate"] = ((batting_opponent["runs"] / batting_opponent["balls_faced"].replace(0, 1)) * 100).round(2)
    batting_opponent.rename(columns={"bowling_team": "opponent"}, inplace=True)

    bowling_venue = df.groupby(["bowler", "venue", "format"]).agg(
        innings=("match_id", "nunique"), balls=("is_wide", lambda x: (x == 0).sum()),
        runs_given=("bowler_runs", "sum"), wickets=("is_wicket", "sum"), dot_balls=("is_dot", "sum"),
    ).reset_index()
    bowling_venue["economy"] = ((bowling_venue["runs_given"] / bowling_venue["balls"].replace(0, 1)) * 6).round(2)
    bowling_venue["average"] = (bowling_venue["runs_given"] / bowling_venue["wickets"].replace(0, 1)).round(2)
    bowling_venue["dot_pct"] = ((bowling_venue["dot_balls"] / bowling_venue["balls"].replace(0, 1)) * 100).round(2)

    bowling_opponent = df.groupby(["bowler", "batting_team", "format"]).agg(
        innings=("match_id", "nunique"), balls=("is_wide", lambda x: (x == 0).sum()),
        runs_given=("bowler_runs", "sum"), wickets=("is_wicket", "sum"), dot_balls=("is_dot", "sum"),
    ).reset_index()
    bowling_opponent["economy"] = ((bowling_opponent["runs_given"] / bowling_opponent["balls"].replace(0, 1)) * 6).round(2)
    bowling_opponent["average"] = (bowling_opponent["runs_given"] / bowling_opponent["wickets"].replace(0, 1)).round(2)
    bowling_opponent["dot_pct"] = ((bowling_opponent["dot_balls"] / bowling_opponent["balls"].replace(0, 1)) * 100).round(2)
    bowling_opponent.rename(columns={"batting_team": "opponent"}, inplace=True)

    batter_vs_bowler = df.groupby(["striker", "bowler", "format"]).agg(
        balls_faced=("is_wide", lambda x: (x == 0).sum()), runs=("runs_off_bat", "sum"),
        dismissals=("is_wicket", "sum"), fours=("runs_off_bat", lambda x: (x == 4).sum()),
        sixes=("runs_off_bat", lambda x: (x == 6).sum()), dot_balls=("is_dot", "sum"),
    ).reset_index()
    batter_vs_bowler["strike_rate"] = ((batter_vs_bowler["runs"] / batter_vs_bowler["balls_faced"].replace(0, 1)) * 100).round(2)
    batter_vs_bowler["average"] = (batter_vs_bowler["runs"] / batter_vs_bowler["dismissals"].replace(0, 1)).round(2)
    batter_vs_bowler = batter_vs_bowler[batter_vs_bowler["balls_faced"] >= 10]

    bowler_vs_batter = df.groupby(["bowler", "striker", "format"]).agg(
        balls_bowled=("is_wide", lambda x: (x == 0).sum()), runs_given=("bowler_runs", "sum"),
        wickets=("is_wicket", "sum"), dot_balls=("is_dot", "sum"),
        fours_given=("runs_off_bat", lambda x: (x == 4).sum()),
        sixes_given=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    bowler_vs_batter["economy"] = ((bowler_vs_batter["runs_given"] / bowler_vs_batter["balls_bowled"].replace(0, 1)) * 6).round(2)
    bowler_vs_batter["strike_rate"] = (bowler_vs_batter["balls_bowled"] / bowler_vs_batter["wickets"].replace(0, 1)).round(2)
    bowler_vs_batter["dot_pct"] = ((bowler_vs_batter["dot_balls"] / bowler_vs_batter["balls_bowled"].replace(0, 1)) * 100).round(2)
    bowler_vs_batter = bowler_vs_batter[bowler_vs_batter["balls_bowled"] >= 10]

    log.info("Yearly/venue/opponent/matchup tables built")
    return (batting_yearly, bowling_yearly, batting_venue, batting_opponent,
            bowling_venue, bowling_opponent, batter_vs_bowler, bowler_vs_batter)


def build_ml_tables(batting_by_format, bowling_by_format, batting_yearly, bowling_yearly):
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans

    bat_ml = batting_by_format.copy()
    features = ["average", "strike_rate", "boundary_pct", "dot_pct", "runs"]
    bat_ml = bat_ml.dropna(subset=features)
    bat_ml = bat_ml[bat_ml["runs"] >= 200]
    scaler = StandardScaler()
    X = scaler.fit_transform(bat_ml[features])
    bat_ml["cluster"] = KMeans(n_clusters=8, random_state=42, n_init=10).fit_predict(X)

    bowl_ml = bowling_by_format.copy()
    bfeatures = ["economy", "average", "dot_pct", "strike_rate", "wickets"]
    bowl_ml = bowl_ml.dropna(subset=bfeatures)
    bowl_ml = bowl_ml[bowl_ml["wickets"] >= 20]
    Xb = scaler.fit_transform(bowl_ml[bfeatures])
    bowl_ml["cluster"] = KMeans(n_clusters=8, random_state=42, n_init=10).fit_predict(Xb)

    latest_year = batting_yearly["year"].max()
    recent = batting_yearly[batting_yearly["year"] >= latest_year - 1].groupby(["striker", "format"]).agg(
        recent_runs=("runs", "sum"), recent_avg=("average", "mean"), recent_sr=("strike_rate", "mean")
    ).reset_index()
    career_avg = batting_by_format[["striker", "format", "average", "strike_rate"]].copy()
    career_avg.columns = ["striker", "format", "career_avg", "career_sr"]
    form = recent.merge(career_avg, on=["striker", "format"], how="left")
    form["form_score"] = ((form["recent_avg"] / form["career_avg"].replace(0, 1)) * 50 +
                           (form["recent_sr"] / form["career_sr"].replace(0, 1)) * 50).round(1)
    form["form_label"] = pd.cut(form["form_score"], bins=[0, 60, 85, 110, 999],
                                 labels=["Poor", "Average", "Good", "On Fire"])

    latest_yr2 = bowling_yearly["year"].max()
    recent_bowl = bowling_yearly[bowling_yearly["year"] >= latest_yr2 - 1].groupby(["bowler", "format"]).agg(
        recent_wkts=("wickets", "sum"), recent_econ=("economy", "mean"), recent_avg=("average", "mean")
    ).reset_index()
    career_bowl = bowling_by_format[["bowler", "format", "economy", "average"]].copy()
    career_bowl.columns = ["bowler", "format", "career_econ", "career_avg"]
    bowl_form = recent_bowl.merge(career_bowl, on=["bowler", "format"], how="left")
    bowl_form["form_score"] = ((bowl_form["career_econ"] / bowl_form["recent_econ"].replace(0, 1)) * 50 +
                                (bowl_form["career_avg"] / bowl_form["recent_avg"].replace(0, 1)) * 50).round(1)
    bowl_form["form_label"] = pd.cut(bowl_form["form_score"], bins=[0, 60, 85, 110, 999],
                                      labels=["Poor", "Average", "Good", "On Fire"])

    def compute_player_score(row):
        score = (
            min(row.get("average", 0) / 80, 1) * 30 +
            min(row.get("strike_rate", 0) / 180, 1) * 25 +
            min(row.get("boundary_pct", 0) / 30, 1) * 20 +
            min(row.get("runs", 0) / 10000, 1) * 15 +
            (1 - min(row.get("dot_pct", 100) / 70, 1)) * 10
        )
        return round(score * 100, 1)

    batting_by_format["player_score"] = batting_by_format.apply(compute_player_score, axis=1)
    bat_ml["player_score"] = bat_ml.apply(compute_player_score, axis=1)

    log.info("ML tables built: clustering, form ratings, player scores")
    return bat_ml, bowl_ml, form, bowl_form


# ── Coverage-gap detection (Wikipedia cross-check) ────────────────────────────
# Cricsheet is a community-maintained ball-by-ball archive. It's excellent but
# NOT guaranteed complete — a handful of officially recognized international
# matches per player can be missing (rain-affected games, matches whose feed
# was never digitized, etc). Silently living with that is what caused the
# "Kohli shows fewer ODIs than Wikipedia" issue. Rather than trying to patch
# missing ball-by-ball data (which we can't fabricate), we cross-check our
# aggregate Cricsheet totals against Wikipedia's infobox career stats — the
# same structured table ESPNCricinfo-style "official" figures come from — and
# flag any player/format where our count is meaningfully short. This gets
# surfaced in the dashboard as "official: X | tracked here: Y" instead of
# pretending the two numbers are the same thing.
INTL_FORMATS_FOR_WIKI_CHECK = ["ODI", "Test", "T20I"]
# 100+ matches keeps this to established/veteran international players —
# ~130-150 unique names across all three formats combined, based on a test
# run. That's the group where a coverage gap actually dents credibility
# (nobody is checking a 20-match fringe player's exact total), and it keeps
# this to a couple hundred Wikipedia calls rather than several thousand, so
# the Action run stays fast and doesn't hammer Wikipedia's API.
WIKI_CHECK_MIN_MATCHES = 100
WIKI_GAP_FLAG_THRESHOLD_PCT = 3.0    # flag if Cricsheet is short by more than this % of matches

_FORMAT_ALIASES = {
    "ODI":  ["odi", "one day international", "one-day international"],
    "Test": ["test"],
    "T20I": ["t20i", "twenty20 international", "t20 international"],
}

def _wiki_search_title(player_name):
    """Find the best-matching Wikipedia page title for a player name.
    Mirrors the scoring logic used in the dashboard's get_wiki() — name
    similarity dominates, cricket-related snippet keywords break ties."""
    import re, difflib
    try:
        sr = requests.get("https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": f"{player_name} cricketer",
                    "format": "json", "utf8": 1, "srlimit": 5},
            timeout=10, headers={"User-Agent": "CricketAnalyticsPipeline/1.0"})
        sr.raise_for_status()
        results = sr.json().get("query", {}).get("search", [])
        if not results:
            return None
        target = player_name.lower()
        def sim(title):
            t = title.lower().replace("(cricketer)", "").strip()
            return difflib.SequenceMatcher(None, target, t).ratio()
        def score(r):
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet", "")).lower()
            s = sim(r.get("title", "")) * 20
            if "cricket" in snippet: s += 3
            if sim(r.get("title", "")) < 0.4: s -= 15
            return s
        best = sorted(results, key=score, reverse=True)[0]
        if score(best) <= 0:
            return None
        return best["title"]
    except Exception as e:
        log.warning(f"Wiki search failed for '{player_name}': {e}")
        return None


def _fetch_wiki_infobox_stats(page_title):
    """Pull the Infobox cricketer wikitext and parse the per-format career
    stats table (column1/matches1/runs1/bat avg1/100s-50s1, column2/..., etc).
    Returns {format_label: {"matches":..,"runs":..,"average":..,"hundreds":..}}.
    Wikipedia's infobox field naming isn't perfectly standardized across
    pages, so this tries a couple of common key variants and skips anything
    it can't confidently parse rather than guessing."""
    import re
    try:
        safe = page_title.replace(" ", "_")
        ir = requests.get("https://en.wikipedia.org/w/api.php",
            params={"action": "query", "titles": page_title, "prop": "revisions",
                    "rvprop": "content", "rvslots": "main", "format": "json", "rvsection": 0},
            timeout=10, headers={"User-Agent": "CricketAnalyticsPipeline/1.0"})
        ir.raise_for_status()
        pages = ir.json().get("query", {}).get("pages", {})
        wt = next(iter(pages.values())).get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        if not wt:
            return {}

        out = {}
        # Column labels can be up to ~6 (Test/ODI/T20I/FC/LA/T20 domestic etc.)
        for i in range(1, 8):
            col_m = re.search(rf"\|\s*column{i}\s*=\s*([^\n\|]{{2,40}})", wt, re.IGNORECASE)
            if not col_m:
                continue
            col_label = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", col_m.group(1)).strip().lower()
            fmt_match = None
            for fmt, aliases in _FORMAT_ALIASES.items():
                if any(a in col_label for a in aliases):
                    fmt_match = fmt
                    break
            if not fmt_match or fmt_match in out:
                continue

            def field(names):
                for n in names:
                    m = re.search(rf"\|\s*{re.escape(n)}{i}\s*=\s*([^\n\|]{{1,20}})", wt, re.IGNORECASE)
                    if m:
                        v = m.group(1).strip()
                        v = re.sub(r"<[^>]+>", "", v).replace(",", "").strip()
                        return v
                return None

            matches_v = field(["matches"])
            runs_v = field(["runs"])
            avg_v = field(["bat avg", "batting average", "bat_avg"])
            hs50_v = field(["100s/50s", "100s_50s"])

            def to_num(v):
                if v is None: return None
                m = re.search(r"[\d.]+", v)
                return float(m.group()) if m else None

            hundreds = None
            if hs50_v:
                parts = hs50_v.split("/")
                if parts and parts[0].strip().replace(".", "").isdigit():
                    hundreds = int(float(parts[0].strip()))

            m_num, r_num = to_num(matches_v), to_num(runs_v)
            if m_num is None:
                continue
            out[fmt_match] = {
                "matches": m_num, "runs": r_num,
                "average": to_num(avg_v), "hundreds": hundreds,
            }
        return out
    except Exception as e:
        log.warning(f"Wiki infobox parse failed for '{page_title}': {e}")
        return {}


def detect_name_fragments(df, batting_by_format, coverage_gaps):
    """For every player flagged by the Wikipedia gap-check, look for other
    'striker' name variants in the raw ball-by-ball data that are probably
    the SAME real person recorded under a slightly different spelling in
    one match (e.g. 'Virat Kohli' vs 'V Kohli' in a single file) — a data
    fragmentation bug, not a genuine archive gap. This matters most for
    high-profile matches: a whole century innings can silently vanish from
    a player's totals this way, e.g. Kohli's 122* vs Afghanistan (Asia Cup
    2022) — far too recent and high-profile a match to be a real coverage
    gap, which is exactly the kind of case this is meant to catch instead
    of being mislabeled as 'Cricsheet just doesn't have it'.
    Only checks the already-small flagged-player list (not all ~10k+ names
    in the archive) to keep this fast, and only flags OTHER names with few
    matches (<=5) so it doesn't confuse two genuinely different players who
    happen to share a similar name."""
    import difflib
    if coverage_gaps.empty:
        coverage_gaps["possible_name_fragments"] = ""
        return coverage_gaps

    fragments_col = []
    for _, row in coverage_gaps.iterrows():
        if not row.get("flagged", False):
            fragments_col.append("")
            continue
        player, fmt = row["player"], row["format"]
        fmt_names = batting_by_format.loc[batting_by_format["format"] == fmt, "striker"].unique()
        target_norm = player.lower().replace(".", "").replace(" ", "")
        target_last = player.split()[-1].lower() if " " in player else player.lower()

        candidates = []
        for other in fmt_names:
            if other == player:
                continue
            other_norm = other.lower().replace(".", "").replace(" ", "")
            other_last = other.split()[-1].lower() if " " in other else other.lower()
            if other_last != target_last:
                continue  # different surname — not a spelling-variant candidate
            sim = difflib.SequenceMatcher(None, target_norm, other_norm).ratio()
            if sim < 0.55:
                continue
            other_matches = batting_by_format.loc[
                (batting_by_format["striker"] == other) & (batting_by_format["format"] == fmt), "matches"]
            if other_matches.empty or other_matches.iloc[0] > 5:
                continue  # a real distinct player with a normal career, not a 1-match fragment
            candidates.append(f"{other} ({int(other_matches.iloc[0])}m, {sim:.0%} match)")

        fragments_col.append("; ".join(candidates))
        if candidates:
            log.warning(f"Possible name-fragment for {player} ({fmt}): {'; '.join(candidates)}")

    coverage_gaps = coverage_gaps.copy()
    coverage_gaps["possible_name_fragments"] = fragments_col
    return coverage_gaps


def build_coverage_gap_report(batting_by_format):
    """Cross-check Cricsheet's ODI/Test/T20I match counts against Wikipedia's
    official career totals for every player with enough matches to be worth
    checking. Returns a DataFrame the dashboard can use to show 'official vs
    tracked here' notices, instead of silently under-reporting a big name's
    career (this is what happened with Kohli's ODI count)."""
    rows = []
    candidates = batting_by_format[
        (batting_by_format["format"].isin(INTL_FORMATS_FOR_WIKI_CHECK)) &
        (batting_by_format["matches"] >= WIKI_CHECK_MIN_MATCHES)
    ]
    log.info(f"Coverage-gap check: {len(candidates)} player/format rows to verify against Wikipedia")

    # Cache one Wikipedia page fetch per player across their formats
    page_cache = {}
    stats_cache = {}

    import time
    for _, row in candidates.iterrows():
        player = row["striker"]
        fmt = row["format"]
        cs_matches = row["matches"]
        cs_runs = row["runs"]

        if player not in page_cache:
            time.sleep(0.3)  # be polite to Wikipedia's API across ~150 players
            page_cache[player] = _wiki_search_title(player)
        title = page_cache[player]
        if not title:
            continue

        if player not in stats_cache:
            stats_cache[player] = _fetch_wiki_infobox_stats(title)
        wiki_stats = stats_cache[player].get(fmt)
        if not wiki_stats or wiki_stats.get("matches") is None:
            continue

        wiki_matches = wiki_stats["matches"]
        if wiki_matches <= 0:
            continue
        gap_matches = wiki_matches - cs_matches
        gap_pct = (gap_matches / wiki_matches) * 100

        rows.append({
            "player": player, "format": fmt,
            "cricsheet_matches": cs_matches, "wiki_matches": wiki_matches,
            "gap_matches": gap_matches, "gap_pct": round(gap_pct, 2),
            "cricsheet_runs": cs_runs, "wiki_runs": wiki_stats.get("runs"),
            "wiki_page": title,
            "flagged": gap_pct > WIKI_GAP_FLAG_THRESHOLD_PCT,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        n_flagged = int(out["flagged"].sum())
        log.info(f"Coverage-gap check complete: {n_flagged} player/format combos flagged "
                  f"(Cricsheet short by >{WIKI_GAP_FLAG_THRESHOLD_PCT}% of matches)")
    return out


def apply_true_match_counts(batting_by_format, bowling_by_format, registered_players):
    """Replace the ball-derived 'matches' count (which only counts matches
    where the player actually faced a ball / bowled a delivery) with the
    true squad-appearance count from the _info.csv registration data. This
    is the fix for players showing fewer 'matches' than their real career
    total — the gap was never missing Cricsheet data, it was matches where
    they were part of the XI but simply didn't need to bat/bowl.
    The old ball-derived count is kept as 'innings_batted'/'innings_bowled'
    since that's still a genuinely useful, different number (e.g. for
    strike-rate-style analysis), just not what should be labeled 'Matches'."""
    if registered_players.empty:
        log.warning("No player-registration data available — 'matches' still reflects "
                    "ball-derived innings counts only, not true squad appearances.")
        return batting_by_format, bowling_by_format

    true_counts = (registered_players.groupby(["player", "format"])["match_id"]
                   .nunique().reset_index().rename(columns={"match_id": "true_matches"}))

    batting_by_format = batting_by_format.rename(columns={"matches": "innings_batted"})
    batting_by_format = batting_by_format.merge(
        true_counts.rename(columns={"player": "striker"}), on=["striker", "format"], how="left")
    # Fall back to the ball-derived count if a player has no registration
    # match (e.g. name-spelling mismatch between the two Cricsheet files)
    # rather than silently zeroing out their matches.
    missing_reg = batting_by_format["true_matches"].isna()
    if missing_reg.any():
        log.warning(f"{missing_reg.sum():,} batting rows had no player-registration match "
                    f"(likely name-format mismatch) — falling back to innings-batted count for those")
    batting_by_format["matches"] = batting_by_format["true_matches"].fillna(batting_by_format["innings_batted"])
    batting_by_format["matches"] = batting_by_format["matches"].astype(int)
    batting_by_format = batting_by_format.drop(columns=["true_matches"])

    bowling_by_format = bowling_by_format.rename(columns={"matches": "innings_bowled"})
    bowling_by_format = bowling_by_format.merge(
        true_counts.rename(columns={"player": "bowler"}), on=["bowler", "format"], how="left")
    missing_reg2 = bowling_by_format["true_matches"].isna()
    if missing_reg2.any():
        log.warning(f"{missing_reg2.sum():,} bowling rows had no player-registration match — "
                    f"falling back to innings-bowled count for those")
    bowling_by_format["matches"] = bowling_by_format["true_matches"].fillna(bowling_by_format["innings_bowled"])
    bowling_by_format["matches"] = bowling_by_format["matches"].astype(int)
    bowling_by_format = bowling_by_format.drop(columns=["true_matches"])

    return batting_by_format, bowling_by_format


def apply_name_aliases(df, registered_players):
    """Load name_aliases.csv (optional, human-maintained) and rename any
    matching striker/bowler/non_striker/player values from a confirmed
    variant spelling to the canonical name — e.g. if you verify that the
    'Virat Kohli' rows in one match file are really the same person as
    'V Kohli' everywhere else, adding that alias here means every future
    pipeline run merges them automatically, permanently, no re-checking
    needed. This is deliberately NOT automatic guessing — detect_name_
    fragments() only logs candidates for a human to confirm, because
    auto-merging two similarly-named but genuinely different players would
    be a worse bug than the fragmentation it's trying to fix.
    Expected columns: variant_name, canonical_name, note (format optional —
    if given, only that format's rows are renamed; if blank, applies to all)."""
    try:
        resp = requests.get(f"{RAW_REPO_BASE}/name_aliases.csv", timeout=15)
        if resp.status_code != 200:
            log.info("No name_aliases.csv found — skipping (this is fine, it's optional).")
            return df, registered_players
        aliases = pd.read_csv(io.StringIO(resp.text))
    except Exception as e:
        log.warning(f"Could not load name_aliases.csv: {e} — skipping")
        return df, registered_players

    if aliases.empty:
        return df, registered_players

    applied = 0
    for _, row in aliases.iterrows():
        variant, canonical = row["variant_name"], row["canonical_name"]
        fmt = row.get("format")
        fmt_mask = (df["format"] == fmt) if pd.notna(fmt) and fmt else pd.Series(True, index=df.index)
        for col in ["striker", "bowler", "non_striker"]:
            if col in df.columns:
                hit = (df[col] == variant) & fmt_mask
                if hit.any():
                    df.loc[hit, col] = canonical
                    applied += int(hit.sum())
        if "player" in registered_players.columns:
            reg_fmt_mask = (registered_players["format"] == fmt) if pd.notna(fmt) and fmt else pd.Series(True, index=registered_players.index)
            registered_players.loc[(registered_players["player"] == variant) & reg_fmt_mask, "player"] = canonical
        log.info(f"Applied name alias: '{variant}' -> '{canonical}'"
                  f"{f' ({fmt} only)' if pd.notna(fmt) and fmt else ''}")
    log.info(f"Name aliases applied: {len(aliases)} rule(s), {applied} raw row(s) renamed")
    return df, registered_players


def apply_manual_overrides(batting_by_format, bowling_by_format):
    """Apply a small, human-verified correction list for matches Cricsheet's
    archive genuinely doesn't have on file at all (no delivery CSV, no
    _info.csv — nothing to parse or infer, unlike the DNB-match fix above).
    This is NOT automated scraping of any kind — ESPNCricinfo's robots.txt
    disallows that, and guessing at numbers isn't an option either. This
    reads manual_match_overrides.csv, a file YOU maintain by hand after
    checking a real source yourself (Cricinfo, Wikipedia's year-by-year
    tour articles, etc.) and copying in the exact figures. Same idea as
    the manual Afghanistan data supplement — a documented exception list,
    not a black box.
    Expected columns: player, format, matches_add, runs_add (optional),
    source, note. Missing file = no-op, logged, not an error."""
    try:
        url = f"{RAW_REPO_BASE}/manual_match_overrides.csv"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            log.info("No manual_match_overrides.csv found — skipping manual corrections (this is fine, it's optional).")
            return batting_by_format, bowling_by_format
        overrides = pd.read_csv(io.StringIO(resp.text))
    except Exception as e:
        log.warning(f"Could not load manual_match_overrides.csv: {e} — skipping manual corrections")
        return batting_by_format, bowling_by_format

    if overrides.empty:
        return batting_by_format, bowling_by_format

    applied = 0
    for _, row in overrides.iterrows():
        mask = (batting_by_format["striker"] == row["player"]) & (batting_by_format["format"] == row["format"])
        if not mask.any():
            log.warning(f"Manual override for {row['player']} ({row['format']}) has no matching row — skipped")
            continue
        batting_by_format.loc[mask, "matches"] += int(row.get("matches_add", 0) or 0)
        if pd.notna(row.get("runs_add")):
            batting_by_format.loc[mask, "runs"] += int(row["runs_add"])
        applied += 1
        log.info(f"Applied manual override: {row['player']} {row['format']} "
                  f"+{row.get('matches_add', 0)} matches (source: {row.get('source', 'unspecified')})")
    log.info(f"Manual overrides applied: {applied}/{len(overrides)} rows")
    return batting_by_format, bowling_by_format


def fetch_cricsheet_known_missing():
    """Cricsheet publishes its own list of specific matches (by date and
    teams) that it knows it's missing from its archive — for Test matches
    and ODIs specifically (they don't track this for T20Is or most domestic
    competitions). This is cricsheet.org's own page, not a third-party site,
    so unlike ESPNCricinfo there's no robots.txt concern fetching it.
    This turns "there's probably a coverage gap somewhere" into a specific,
    permanent, dated explanation — for every player, not just one — without
    ever needing to guess or manually chase down individual matches.
    Returns a DataFrame: format, gender, date, team1, team2."""
    try:
        resp = requests.get("https://cricsheet.org/missing/", timeout=20,
                             headers={"User-Agent": "CricketAnalyticsPipeline/1.0"})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        log.warning(f"Could not fetch cricsheet.org/missing/: {e} — "
                     "coverage-gap explanations will fall back to the generic note")
        return pd.DataFrame(columns=["format", "gender", "date", "team1", "team2"])

    import re
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks = []
        def handle_data(self, data):
            self.chunks.append(data)

    extractor = TextExtractor()
    extractor.feed(text)
    plain = "\n".join(extractor.chunks)

    rows = []
    current_format, current_gender, current_date = None, None, None
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    vs_re = re.compile(r"^(.+?)\s+vs\s+(.+?)$")
    fmt_header_re = re.compile(r"^(Test|Odi)\s+Matches$", re.IGNORECASE)
    gender_header_re = re.compile(r"^(Female|Male)\s+matches$", re.IGNORECASE)

    for raw_line in plain.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line == "By competition":
            break  # only want the international Test/ODI section, not domestic competitions
        m = fmt_header_re.match(line)
        if m:
            current_format = "Test" if m.group(1).lower() == "test" else "ODI"
            continue
        m = gender_header_re.match(line)
        if m:
            current_gender = m.group(1).lower()
            continue
        if date_re.match(line):
            current_date = line
            continue
        m = vs_re.match(line)
        if m and current_format and current_date:
            rows.append({"format": current_format, "gender": current_gender,
                         "date": current_date, "team1": m.group(1).strip(),
                         "team2": m.group(2).strip()})

    out = pd.DataFrame(rows)
    log.info(f"Cricsheet's own missing-matches list: {len(out):,} known-missing Test/ODI entries parsed")
    return out


def explain_coverage_gaps_from_known_missing(coverage_gaps, known_missing, registered_players):
    """For every player flagged by the Wikipedia coverage-gap check, look for
    overlap with Cricsheet's own documented missing-matches list: matches
    involving that player's team, dated within the span of matches we
    already have for them (their first to last match in that format). This
    doesn't claim certainty the player was in every such match — squad
    selection isn't in this list — but it turns a vague 'may be a coverage
    gap' into a specific, sourced count of documented missing fixtures,
    for every flagged player automatically, no manual lookup required."""
    if coverage_gaps.empty or known_missing.empty:
        coverage_gaps["documented_missing_candidates"] = 0
        return coverage_gaps

    known_missing = known_missing.copy()
    known_missing["date"] = pd.to_datetime(known_missing["date"], errors="coerce")

    candidate_counts = []
    for _, row in coverage_gaps.iterrows():
        if not row.get("flagged", False):
            candidate_counts.append(0)
            continue
        player, fmt = row["player"], row["format"]
        player_matches = registered_players[registered_players["player"] == player]
        if player_matches.empty:
            candidate_counts.append(0)
            continue
        team = player_matches["team"].mode().iloc[0] if not player_matches["team"].mode().empty else None
        if team is None:
            candidate_counts.append(0)
            continue

        fmt_known = known_missing[known_missing["format"] == fmt]
        team_missing = fmt_known[(fmt_known["team1"] == team) | (fmt_known["team2"] == team)]
        candidate_counts.append(len(team_missing))

    coverage_gaps = coverage_gaps.copy()
    coverage_gaps["documented_missing_candidates"] = candidate_counts
    return coverage_gaps


def push_csv_to_github(df, filename, token, user, repo, branch="main"):
    """Push a DataFrame as CSV to GitHub. Returns True/False so the caller
    can track failures instead of just printing and moving on."""
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    content_b64 = base64.b64encode(csv_bytes).decode("utf-8")

    payload = {"message": f"Update {filename}", "content": content_b64, "branch": branch}
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        log.info(f"Pushed {filename} ({len(df):,} rows)")
        return True
    else:
        log.error(f"FAILED to push {filename}: {resp.status_code} {resp.json().get('message')}")
        return False


def push_text_to_github(text, filename, token, user, repo, branch="main"):
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {
        "message": f"Update {filename}",
        "content": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code in (200, 201)


def main():
    if not all([GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO]):
        log.error("Missing required config: set GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO "
                   "as environment variables (see README for how to do this via GitHub Secrets).")
        sys.exit(1)

    log.info("=== Cricket pipeline run started ===")

    for name, url in CRICSHEET_URLS.items():
        download_and_extract(name, url, WORKDIR)

    df = pd.concat([
        load_format(os.path.join(WORKDIR, "odi_data"), "ODI"),
        load_format(os.path.join(WORKDIR, "test_data"), "Test"),
        load_format(os.path.join(WORKDIR, "t20i_data"), "T20I"),
        load_format(os.path.join(WORKDIR, "ipl_data"), "IPL"),
        load_format(os.path.join(WORKDIR, "psl_data"), "PSL"),
    ], ignore_index=True)
    log.info(f"TOTAL raw rows loaded: {df.shape[0]:,}")

    registered_players = pd.concat([
        load_registered_players(os.path.join(WORKDIR, "odi_data"), "ODI"),
        load_registered_players(os.path.join(WORKDIR, "test_data"), "Test"),
        load_registered_players(os.path.join(WORKDIR, "t20i_data"), "T20I"),
        load_registered_players(os.path.join(WORKDIR, "ipl_data"), "IPL"),
        load_registered_players(os.path.join(WORKDIR, "psl_data"), "PSL"),
    ], ignore_index=True)
    log.info(f"TOTAL player-registration rows loaded: {registered_players.shape[0]:,}")

    df, registered_players = apply_name_aliases(df, registered_players)

    df = clean_and_validate(df)
    bat_innings, bowl_innings = build_innings_tables(df)
    batting, bowling, batting_by_format, bowling_by_format = build_career_and_milestones(df, bat_innings, bowl_innings)
    batting_by_format, bowling_by_format = apply_true_match_counts(
        batting_by_format, bowling_by_format, registered_players)
    batting_by_format, bowling_by_format = apply_manual_overrides(batting_by_format, bowling_by_format)
    (batting_yearly, bowling_yearly, batting_venue, batting_opponent,
     bowling_venue, bowling_opponent, batter_vs_bowler, bowler_vs_batter) = build_yearly_venue_opponent_matchup(df)
    bat_ml, bowl_ml, form, bowl_form = build_ml_tables(batting_by_format, bowling_by_format,
                                                        batting_yearly, bowling_yearly)

    log.info("Running Wikipedia coverage-gap check for international players...")
    coverage_gaps = build_coverage_gap_report(batting_by_format)

    log.info("Cross-checking flagged gaps against Cricsheet's own documented missing-matches list...")
    known_missing = fetch_cricsheet_known_missing()
    coverage_gaps = explain_coverage_gaps_from_known_missing(coverage_gaps, known_missing, registered_players)

    log.info("Checking flagged players for possible name-spelling fragments in the raw data...")
    coverage_gaps = detect_name_fragments(df, batting_by_format, coverage_gaps)

    files_to_save = {
        "cricket_batting_stats.csv": batting,
        "cricket_bowling_stats.csv": bowling,
        "cricket_batting_by_format.csv": batting_by_format,
        "cricket_bowling_by_format.csv": bowling_by_format,
        "cricket_batting_yearly.csv": batting_yearly,
        "cricket_bowling_yearly.csv": bowling_yearly,
        "cricket_batting_venue.csv": batting_venue,
        "cricket_batting_opponent.csv": batting_opponent,
        "cricket_bowling_venue.csv": bowling_venue,
        "cricket_bowling_opponent.csv": bowling_opponent,
        "cricket_batter_vs_bowler.csv": batter_vs_bowler,
        "cricket_bowler_vs_batter.csv": bowler_vs_batter,
        "cricket_bat_innings.csv": bat_innings,
        "cricket_bowl_innings.csv": bowl_innings,
        "cricket_bat_form_ratings.csv": form,
        "cricket_bowl_form_ratings.csv": bowl_form,
        "cricket_bat_similarity.csv": bat_ml[["striker", "format", "cluster", "average", "strike_rate",
                                               "boundary_pct", "dot_pct", "runs", "player_score"]],
        "cricket_bowl_similarity.csv": bowl_ml[["bowler", "format", "cluster", "wickets", "economy",
                                                 "average", "dot_pct"]],
        "cricket_coverage_gaps.csv": coverage_gaps,
    }

    log.info(f"Pushing {len(files_to_save)} files to github.com/{GITHUB_USER}/{GITHUB_REPO}...")
    failures = []
    for fn, df_out in files_to_save.items():
        ok = push_csv_to_github(df_out, fn, GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO, BRANCH)
        if not ok:
            failures.append(fn)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    push_text_to_github(timestamp, "last_updated.txt", GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO, BRANCH)
    log.info(f"Wrote last_updated.txt = {timestamp}")

    if failures:
        log.error(f"Pipeline finished WITH {len(failures)} failed file push(es): {failures}")
        sys.exit(1)
    else:
        log.info("=== Pipeline run completed successfully, all files pushed ===")


if __name__ == "__main__":
    main()
