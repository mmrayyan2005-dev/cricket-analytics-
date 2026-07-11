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
import time
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
    letting a bad download silently produce zero data for a format.

    Includes a browser-like User-Agent header — Cricsheet's server can
    reject plain script requests with a 415 error otherwise, which is what
    caused a full pipeline failure (every format returned 0 rows)."""
    folder = os.path.join(workdir, f"{name.lower()}_data")
    os.makedirs(folder, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CricketAnalyticsPipeline/1.0; "
                      "+https://github.com/mmrayyan2005-dev/cricket-analytics_-)",
        "Accept": "*/*",
    }
    try:
        resp = requests.get(url, timeout=60, headers=headers)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extractall(folder)
        log.info(f"Downloaded and extracted {name} from {url}")
        return folder
    except Exception as e:
        log.error(f"FAILED to download {name} from {url}: {e}")
        return folder  # return the (possibly empty) folder so pipeline continues


def load_format(folder, label):
    """Load all per-match CSVs for one format. Logs which individual match
    files failed to parse instead of the previous bare `except: pass`.

    Also guards against a real bug that was causing doubled stats (e.g.
    Kohli showing 1350 IPL runs in 2026 when the true figure was 675):
    Cricsheet occasionally has the same match_id appear in more than one
    file — e.g. a corrected/reissued scorecard saved alongside the
    original under a different filename. Naively concatenating every file
    can count that match twice. We now remove exact duplicate deliveries
    (same match_id + innings + ball + players) at the row level — this
    can never discard an entire legitimate match's data, only true
    duplicate rows.
    """
    if not os.path.isdir(folder):
        log.warning(f"{label}: folder {folder} does not exist, skipping")
        return pd.DataFrame()
    files = [f for f in os.listdir(folder) if f.endswith(".csv") and not f.endswith("_info.csv")]
    dfs, failed = [], []
    for f in sorted(files):
        try:
            d = pd.read_csv(os.path.join(folder, f), low_memory=False)
            d["_source_file"] = f
            dfs.append(d)
        except Exception as e:
            failed.append((f, str(e)))
    if failed:
        log.warning(f"{label}: {len(failed)} match file(s) failed to parse: "
                    f"{[f for f, _ in failed][:5]}{'...' if len(failed) > 5 else ''}")
    if not dfs:
        log.warning(f"{label}: no valid match files found in {folder}")
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    if "match_id" in df.columns and "innings" in df.columns and "ball" in df.columns:
        # REVISED APPROACH — the previous version compared whole FILES by
        # total row count and discarded the entire "smaller" file for any
        # match_id that appeared twice. That was too aggressive: if that
        # comparison ever picked wrong for any reason (a rain-shortened
        # innings recorded as a separate legitimate file, an unrelated
        # row-count quirk, etc.), it would silently throw away real,
        # legitimate deliveries for that match — which is almost certainly
        # what caused players showing far fewer matches than they actually
        # played (e.g. 90 shown instead of 180).
        #
        # This is a much safer, more conservative fix: instead of judging
        # whole files against each other, we only remove a row if there is
        # ANOTHER row that is an exact duplicate of the same specific
        # delivery — same match, same innings, same ball number. That can
        # only happen if a match was genuinely reissued/duplicated; a
        # legitimate, unique delivery can never collide with another
        # legitimate delivery on all three of those fields at once. This
        # can never discard a real match's real data, only true duplicates.
        before = len(df)
        df = df.drop_duplicates(subset=["match_id", "innings", "ball", "striker", "bowler"], keep="first")
        removed = before - len(df)
        if removed > 0:
            log.warning(f"{label}: removed {removed:,} duplicate delivery row(s) "
                        f"(same match/innings/ball/players appearing more than once — "
                        f"likely a reissued scorecard). This is a safe, row-level removal "
                        f"that cannot discard an entire legitimate match.")

    df = df.drop(columns=["_source_file"])
    df["format"] = label
    log.info(f"{label}: loaded {df.shape[0]:,} rows from {df['match_id'].nunique() if 'match_id' in df.columns else len(dfs)} unique matches")
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


def push_csv_to_github(df, filename, token, user, repo, branch="main"):
    """Push a DataFrame as CSV to GitHub. Returns True/False so the caller
    can track failures instead of just printing and moving on.

    Includes retry logic for the sha lookup — pushing 18 files means 36+
    rapid sequential GitHub API calls, and an occasional transient
    hiccup (rate limiting, brief network blip) can make the sha lookup
    silently return nothing even though the file exists. Previously that
    meant the whole push failed with a 422 'sha wasn't supplied' error.
    Now it retries the lookup a few times with backoff before giving up,
    and if the PUT itself still fails due to a missing sha, it retries
    the entire lookup+push cycle once more from scratch."""
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    content_b64 = base64.b64encode(csv_bytes).decode("utf-8")

    def _get_sha():
        for attempt in range(3):
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.json().get("sha")
            elif r.status_code == 404:
                return None  # file genuinely doesn't exist yet — not an error
            else:
                log.warning(f"{filename}: sha lookup attempt {attempt+1} got "
                            f"unexpected status {r.status_code}, retrying...")
                time.sleep(1.5 * (attempt + 1))
        return None

    for overall_attempt in range(3):
        sha = _get_sha()
        payload = {"message": f"Update {filename}", "content": content_b64, "branch": branch}
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            log.info(f"Pushed {filename} ({len(df):,} rows)")
            return True
        elif "sha" in resp.text.lower() and overall_attempt < 2:
            wait = 3 * (overall_attempt + 1)
            log.warning(f"{filename}: push failed due to sha issue on attempt "
                        f"{overall_attempt+1} ({resp.status_code}), waiting {wait}s and retrying...")
            time.sleep(wait)
            continue
        else:
            log.error(f"FAILED to push {filename}: {resp.status_code} {resp.json().get('message')}")
            return False
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

    # If every download failed (e.g. Cricsheet rejected our requests, or
    # their site was temporarily down), df will be empty here. Previously
    # this would crash 15+ seconds later inside clean_and_validate() with a
    # confusing KeyError that gave no hint the real problem was upstream.
    # Stopping here with a clear message points straight at the real cause.
    if df.empty:
        log.error("No data was loaded from ANY format — every Cricsheet download likely "
                   "failed. Check the download errors logged above (e.g. HTTP errors) "
                   "before re-running. Stopping here instead of crashing later with a "
                   "confusing error.")
        sys.exit(1)

    # ── Diagnostic: what's the most recent date Cricsheet actually gave us,
    # per format, BEFORE any cleaning? This directly answers "is 2025/2026
    # data missing because Cricsheet doesn't have it yet, or because our
    # own cleaning step is dropping it?" — instead of guessing.
    if "start_date" in df.columns:
        raw_dates = pd.to_datetime(df["start_date"], errors="coerce")
        for fmt in df["format"].unique():
            fmt_max = raw_dates[df["format"] == fmt].max()
            log.info(f"[RAW, pre-clean] {fmt}: most recent match date = {fmt_max}")

    df = clean_and_validate(df)

    # Same check AFTER cleaning — if this max date is earlier than the raw
    # check above, our cleaning logic is dropping recent rows (a real bug
    # to fix). If it matches the raw check, Cricsheet's own archive simply
    # doesn't have newer data yet (nothing to fix on our end, just a
    # known lag to document for users).
    for fmt in df["format"].unique():
        fmt_max = df.loc[df["format"] == fmt, "start_date"].max()
        log.info(f"[CLEANED, post-clean] {fmt}: most recent match date = {fmt_max}")


    bat_innings, bowl_innings = build_innings_tables(df)
    batting, bowling, batting_by_format, bowling_by_format = build_career_and_milestones(df, bat_innings, bowl_innings)
    (batting_yearly, bowling_yearly, batting_venue, batting_opponent,
     bowling_venue, bowling_opponent, batter_vs_bowler, bowler_vs_batter) = build_yearly_venue_opponent_matchup(df)
    bat_ml, bowl_ml, form, bowl_form = build_ml_tables(batting_by_format, bowling_by_format,
                                                        batting_yearly, bowling_yearly)

    # ── Manual overrides ───────────────────────────────────────────────────
    # Cricsheet can lag behind real matches by days to weeks, especially for
    # brand-new debutants whose data isn't in the standard archive yet. This
    # reads two OPTIONAL files sitting in the repo root — manual_batting.csv
    # and manual_bowling.csv — and merges them in, so specific missing
    # players/years can be added by hand immediately instead of waiting on
    # Cricsheet or debugging name-matching. If a (striker, year, format) row
    # already exists from the real pipeline data, the manual entry is
    # ignored for that combination — manual entries only fill real gaps,
    # they never silently overwrite automated data.
    #
    # Expected columns for manual_batting.csv:
    #   striker,year,format,matches,runs,balls_faced,dismissals,fours,sixes,average,strike_rate
    # Expected columns for manual_bowling.csv:
    #   bowler,year,format,matches,balls,runs_given,wickets,economy,average
    if os.path.exists("manual_batting.csv"):
        try:
            manual_bat = pd.read_csv("manual_batting.csv")
            existing_keys = set(zip(batting_yearly["striker"], batting_yearly["year"], batting_yearly["format"]))
            new_rows = manual_bat[~manual_bat.apply(
                lambda r: (r["striker"], r["year"], r["format"]) in existing_keys, axis=1)]
            if len(new_rows) > 0:
                batting_yearly = pd.concat([batting_yearly, new_rows], ignore_index=True)
                log.info(f"Added {len(new_rows)} manual batting row(s) from manual_batting.csv "
                         f"(players/years not yet in Cricsheet's data)")
        except Exception as e:
            log.error(f"Failed to apply manual_batting.csv: {e}")

    if os.path.exists("manual_bowling.csv"):
        try:
            manual_bowl = pd.read_csv("manual_bowling.csv")
            existing_keys = set(zip(bowling_yearly["bowler"], bowling_yearly["year"], bowling_yearly["format"]))
            new_rows = manual_bowl[~manual_bowl.apply(
                lambda r: (r["bowler"], r["year"], r["format"]) in existing_keys, axis=1)]
            if len(new_rows) > 0:
                bowling_yearly = pd.concat([bowling_yearly, new_rows], ignore_index=True)
                log.info(f"Added {len(new_rows)} manual bowling row(s) from manual_bowling.csv "
                         f"(players/years not yet in Cricsheet's data)")
        except Exception as e:
            log.error(f"Failed to apply manual_bowling.csv: {e}")

    # ── Career-total overrides (targets the file that actually feeds the
    # summary cards: batting_by_format / bowling_by_format) ────────────────
    # The manual_batting.csv / manual_bowling.csv overrides above only add
    # missing YEARLY rows (for the trend chart). They do NOT touch the
    # career summary cards (Matches/Runs/Average/etc.) shown on a player's
    # main page — those come from batting_by_format.csv, a completely
    # different file. This section is the correct, tested mechanism for
    # that: an optional career_overrides_batting.csv (and _bowling.csv) in
    # the repo root can supply verified official totals for specific
    # players/formats, to correct Cricsheet's known partial coverage for
    # veteran players. Unlike the yearly override (which only fills gaps),
    # this DELIBERATELY overwrites matching (player, format) rows, since
    # the entire point is correcting known-incomplete automated numbers
    # with verified real totals — every overwrite is logged so it's never
    # silent or hidden.
    #
    # Expected columns for career_overrides_batting.csv (any subset of the
    # non-key columns is fine — only the columns you provide get updated):
    #   striker,format,matches,runs,balls_faced,dismissals,fours,sixes,
    #   average,strike_rate,dot_pct,boundary_pct,hundreds,fifties,
    #   thirties,highest,ducks
    if os.path.exists("career_overrides_batting.csv"):
        try:
            overrides = pd.read_csv("career_overrides_batting.csv")
            override_cols = [c for c in overrides.columns if c not in ("striker", "format")]
            applied, added = 0, 0
            for _, row in overrides.iterrows():
                mask = (batting_by_format["striker"] == row["striker"]) & (batting_by_format["format"] == row["format"])
                if mask.any():
                    for col in override_cols:
                        if pd.notna(row[col]):
                            batting_by_format.loc[mask, col] = row[col]
                    applied += 1
                else:
                    new_row = {c: np.nan for c in batting_by_format.columns}
                    new_row["striker"] = row["striker"]
                    new_row["format"] = row["format"]
                    for col in override_cols:
                        if pd.notna(row[col]):
                            new_row[col] = row[col]
                    batting_by_format = pd.concat([batting_by_format, pd.DataFrame([new_row])], ignore_index=True)
                    added += 1
            log.info(f"Career overrides (batting): corrected {applied} existing player/format row(s), "
                     f"added {added} new row(s), from career_overrides_batting.csv")
        except Exception as e:
            log.error(f"Failed to apply career_overrides_batting.csv: {e}")

    if os.path.exists("career_overrides_bowling.csv"):
        try:
            overrides = pd.read_csv("career_overrides_bowling.csv")
            override_cols = [c for c in overrides.columns if c not in ("bowler", "format")]
            applied, added = 0, 0
            for _, row in overrides.iterrows():
                mask = (bowling_by_format["bowler"] == row["bowler"]) & (bowling_by_format["format"] == row["format"])
                if mask.any():
                    for col in override_cols:
                        if pd.notna(row[col]):
                            bowling_by_format.loc[mask, col] = row[col]
                    applied += 1
                else:
                    new_row = {c: np.nan for c in bowling_by_format.columns}
                    new_row["bowler"] = row["bowler"]
                    new_row["format"] = row["format"]
                    for col in override_cols:
                        if pd.notna(row[col]):
                            new_row[col] = row[col]
                    bowling_by_format = pd.concat([bowling_by_format, pd.DataFrame([new_row])], ignore_index=True)
                    added += 1
            log.info(f"Career overrides (bowling): corrected {applied} existing player/format row(s), "
                     f"added {added} new row(s), from career_overrides_bowling.csv")
        except Exception as e:
            log.error(f"Failed to apply career_overrides_bowling.csv: {e}")

    # ── Dtype safety pass ────────────────────────────────────────────────
    # Manual override rows (career_overrides_*.csv, manual_*.csv) can
    # legitimately leave some numeric columns blank/NaN for a given row
    # (e.g. we didn't have verified fours/sixes for an override). When
    # that gets concatenated into a column that was previously clean
    # all-integer data, pandas silently converts the WHOLE column to a
    # mixed/ambiguous dtype. Streamlit then has to serialize these tables
    # to Arrow format for its charts and widgets — and Arrow can crash
    # natively (a segfault, not a normal Python exception) on certain
    # mixed-dtype columns. This explicitly normalizes every numeric
    # column to a safe, consistent float dtype (which handles NaN
    # cleanly) right before saving, so this can't happen regardless of
    # which fields a manual override does or doesn't provide.
    def _safe_numeric_dtypes(df):
        for col in df.columns:
            # Only touch columns that are ALREADY numeric (int64/float64).
            # Explicitly checking for numeric dtypes (rather than trying to
            # exclude text columns by name, e.g. "object") is the safe
            # direction — pandas 3.x uses a native string dtype for text
            # columns by default, which an object-only exclusion check
            # misses, and would otherwise convert player names/format
            # labels into NaN. Only ever widen known-numeric columns.
            if pd.api.types.is_integer_dtype(df[col]) or pd.api.types.is_float_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    batting = _safe_numeric_dtypes(batting)
    bowling = _safe_numeric_dtypes(bowling)
    batting_by_format = _safe_numeric_dtypes(batting_by_format)
    bowling_by_format = _safe_numeric_dtypes(bowling_by_format)
    batting_yearly = _safe_numeric_dtypes(batting_yearly)
    bowling_yearly = _safe_numeric_dtypes(bowling_yearly)
    log.info("Applied dtype-safety pass to prevent mixed-type columns from override merges")

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
    }

    log.info(f"Pushing {len(files_to_save)} files to github.com/{GITHUB_USER}/{GITHUB_REPO}...")
    failures = []
    for fn, df_out in files_to_save.items():
        ok = push_csv_to_github(df_out, fn, GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO, BRANCH)
        if not ok:
            failures.append(fn)
        time.sleep(0.5)  # small gap between pushes — reduces the chance of tripping
                          # GitHub's secondary rate limit from 18 rapid-fire requests

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    push_text_to_github(timestamp, "last_updated.txt", GITHUB_TOKEN, GITHUB_USER, GITHUB_REPO, BRANCH)
    log.info(f"Wrote last_updated.txt = {timestamp}")

    # ── Coverage report ──────────────────────────────────────────────────
    # This is honest, verifiable visibility into exactly what this run
    # actually covers — not a claim that "every player" is included, since
    # that depends entirely on what Cricsheet itself has published. Check
    # this log every run to track coverage growing (or spot a regression)
    # over time, instead of guessing.
    log.info("=== COVERAGE REPORT ===")
    total_batters = batting["striker"].nunique() if not batting.empty else 0
    total_bowlers = bowling["bowler"].nunique() if not bowling.empty else 0
    log.info(f"Unique batters captured: {total_batters:,}")
    log.info(f"Unique bowlers captured: {total_bowlers:,}")
    for fmt in df["format"].unique():
        fmt_df = df[df["format"] == fmt]
        n_matches = fmt_df["match_id"].nunique()
        n_players = pd.concat([fmt_df["striker"], fmt_df["bowler"]]).nunique()
        date_min = pd.to_datetime(fmt_df["start_date"]).min()
        date_max = pd.to_datetime(fmt_df["start_date"]).max()
        log.info(f"  {fmt}: {n_matches:,} matches | {n_players:,} unique players | "
                 f"date range {date_min.date()} to {date_max.date()}")
    log.info("=== END COVERAGE REPORT ===")

    if failures:
        log.error(f"Pipeline finished WITH {len(failures)} failed file push(es): {failures}")
        sys.exit(1)
    else:
        log.info("=== Pipeline run completed successfully, all files pushed ===")


if __name__ == "__main__":
    main()
