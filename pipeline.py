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
    # A flat "balls_faced >= 10" threshold works fine for high-volume formats
    # (ODI/Test/T20I/IPL, where players rack up hundreds of matches), but it
    # wipes out almost every matchup in low-volume leagues like BBL/CPL/PSL/WPL,
    # where a player might only have 5-15 innings total in that competition —
    # not enough to ever face one bowler for 10+ balls. Use a lower bar for
    # those leagues so real matchups survive instead of being filtered to near-zero.
    LOW_VOLUME_FORMATS = {"BBL", "CPL", "PSL", "WPL"}
    low_vol_min_balls = 3
    high_vol_min_balls = 10
    is_low_volume = batter_vs_bowler["format"].isin(LOW_VOLUME_FORMATS)
    keep_mask = (
        (is_low_volume & (batter_vs_bowler["balls_faced"] >= low_vol_min_balls)) |
        (~is_low_volume & (batter_vs_bowler["balls_faced"] >= high_vol_min_balls))
    )
    batter_vs_bowler = batter_vs_bowler[keep_mask]

    bowler_vs_batter = df.groupby(["bowler", "striker", "format"]).agg(
        balls_bowled=("is_wide", lambda x: (x == 0).sum()), runs_given=("bowler_runs", "sum"),
        wickets=("is_wicket", "sum"), dot_balls=("is_dot", "sum"),
        fours_given=("runs_off_bat", lambda x: (x == 4).sum()),
        sixes_given=("runs_off_bat", lambda x: (x == 6).sum()),
    ).reset_index()
    bowler_vs_batter["economy"] = ((bowler_vs_batter["runs_given"] / bowler_vs_batter["balls_bowled"].replace(0, 1)) * 6).round(2)
    bowler_vs_batter["strike_rate"] = (bowler_vs_batter["balls_bowled"] / bowler_vs_batter["wickets"].replace(0, 1)).round(2)
    bowler_vs_batter["dot_pct"] = ((bowler_vs_batter["dot_balls"] / bowler_vs_batter["balls_bowled"].replace(0, 1)) * 100).round(2)
    # Same low-volume-league fix as batter_vs_bowler above.
    is_low_volume_bowl = bowler_vs_batter["format"].isin(LOW_VOLUME_FORMATS)
    keep_mask_bowl = (
        (is_low_volume_bowl & (bowler_vs_batter["balls_bowled"] >= low_vol_min_balls)) |
        (~is_low_volume_bowl & (bowler_vs_batter["balls_bowled"] >= high_vol_min_balls))
    )
    bowler_vs_batter = bowler_vs_batter[keep_mask_bowl]

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

    df = clean_and_validate(df)
    bat_innings, bowl_innings = build_innings_tables(df)
    batting, bowling, batting_by_format, bowling_by_format = build_career_and_milestones(df, bat_innings, bowl_innings)
    (batting_yearly, bowling_yearly, batting_venue, batting_opponent,
     bowling_venue, bowling_opponent, batter_vs_bowler, bowler_vs_batter) = build_yearly_venue_opponent_matchup(df)
    bat_ml, bowl_ml, form, bowl_form = build_ml_tables(batting_by_format, bowling_by_format,
                                                        batting_yearly, bowling_yearly)

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
