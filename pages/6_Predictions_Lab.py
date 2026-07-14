"""
Predictions Lab — extended analytics page for the cricket-analytics_- app.

Drop this file into your Streamlit app's `pages/` folder (multi-page app pattern),
e.g. pages/6_🔮_Predictions_Lab.py, and it'll show up as its own tab in the sidebar
alongside your existing pages.

Reads everything from GitHub raw URLs (same pattern as your core app) —
no local files, no recomputation, just loads what Step 16 of the notebook pushed:
  - cricket_matches_info.csv        (match history + rolling form/H2H)
  - cricket_latest_team_form.csv    (each team's most recent form value)
  - cricket_win_prob_test.csv       (held-out test predictions for calibration)
  - cricket_run_forecast.csv        (next-season projections + SHAP contributions)
  - cricket_bowler_workload.csv     (ACWR injury-risk index)
  - cricket_data_integrity_report.csv
  - cricket_model_metrics.csv
  - win_probability_model.pkl / run_forecast_model.pkl (for LIVE predictions)

requirements.txt needs: streamlit, pandas, plotly, joblib, requests, scikit-learn
"""

import io
import json

import joblib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── CONFIG — match this to your repo ────────────────────────────────────────
GITHUB_USER = "mmrayyan2005-dev"
GITHUB_REPO = "cricket-analytics_-"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/"
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Predictions Lab", page_icon="🔮", layout="wide")


@st.cache_data(ttl=1800, show_spinner=False)
def load_csv(filename):
    try:
        return pd.read_csv(RAW_BASE + filename)
    except Exception:
        return pd.DataFrame()


@st.cache_resource(ttl=1800, show_spinner=False)
def load_model(filename):
    try:
        resp = requests.get(RAW_BASE + filename, timeout=15)
        resp.raise_for_status()
        return joblib.load(io.BytesIO(resp.content))
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def load_json(filename):
    try:
        resp = requests.get(RAW_BASE + filename, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


matches_info = load_csv("cricket_matches_info.csv")
latest_form = load_csv("cricket_latest_team_form.csv")
wp_test = load_csv("cricket_win_prob_test.csv")
forecast = load_csv("cricket_run_forecast.csv")
workload = load_csv("cricket_bowler_workload.csv")
integrity_df = load_csv("cricket_data_integrity_report.csv")
model_metrics = load_csv("cricket_model_metrics.csv")
feature_meta = load_json("model_features.json")

win_model = load_model("win_probability_model.pkl")
forecast_model = load_model("run_forecast_model.pkl")

st.title("🔮 Predictions Lab")
st.caption(
    "Win probability · player forecasting · bowler workload risk · data QA — "
    "built on top of the core cricket analytics app."
)

if matches_info.empty:
    st.warning(
        "Couldn't load extended analytics files from GitHub yet. "
        "Run Step 16 of the notebook to generate and push them, then refresh."
    )
    st.stop()

tab_wp, tab_forecast, tab_workload, tab_qa = st.tabs(
    ["🏆 Win Probability", "📈 Player Forecast", "🎽 Bowler Workload", "🔍 Data Integrity"]
)

# ── TAB 1: WIN PROBABILITY ───────────────────────────────────────────────────
with tab_wp:
    st.subheader("Live Matchup Predictor")

    teams = sorted(set(matches_info["team1"]).union(matches_info["team2"]))
    col1, col2, col3 = st.columns(3)
    with col1:
        team1 = st.selectbox("Team 1", teams, index=0)
    with col2:
        remaining = [t for t in teams if t != team1]
        team2 = st.selectbox("Team 2", remaining, index=0)
    with col3:
        toss_winner = st.radio("Toss winner", [team1, team2], horizontal=True)

    if win_model is not None and not latest_form.empty:
        def get_form(team):
            row = latest_form[latest_form["team"] == team]
            return float(row["form"].values[0]) if not row.empty else 0.5

        t1_form = get_form(team1)
        t2_form = get_form(team2)

        h2h_matches = matches_info[
            ((matches_info["team1"] == team1) & (matches_info["team2"] == team2))
            | ((matches_info["team1"] == team2) & (matches_info["team2"] == team1))
        ]
        if len(h2h_matches) > 0:
            t1_wins = (h2h_matches["winner"] == team1).sum()
            h2h_rate = t1_wins / len(h2h_matches)
        else:
            h2h_rate = 0.5

        toss_advantage = 1 if toss_winner == team1 else 0

        input_row = pd.DataFrame([{
            "team1_form": t1_form,
            "team2_form": t2_form,
            "team1_h2h_rate": h2h_rate,
            "toss_advantage": toss_advantage,
        }])
        # align column order with what the model was trained on
        if feature_meta.get("win_prob_features"):
            input_row = input_row[feature_meta["win_prob_features"]]

        proba_team1 = win_model.predict_proba(input_row)[0][1]

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(proba_team1 * 100, 1),
            number={"suffix": "%"},
            title={"text": f"{team1} win probability"},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": "darkgreen" if proba_team1 > 0.5 else "darkred"},
                   "steps": [{"range": [0, 50], "color": "#fde2e2"},
                             {"range": [50, 100], "color": "#dbf5db"}]},
        ))
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"{team1} recent form: {t1_form:.2f} · {team2} recent form: {t2_form:.2f} · "
            f"H2H win rate ({team1}): {h2h_rate:.2f} · matches faced: {len(h2h_matches)}"
        )
    else:
        st.info("Model or form data not available yet.")

    st.divider()
    st.subheader("Model Performance")
    if not model_metrics.empty:
        wp_metrics = model_metrics[model_metrics["model"].str.contains("win_probability")]
        cols = st.columns(len(wp_metrics))
        for c, (_, row) in zip(cols, wp_metrics.iterrows()):
            c.metric(f"{row['model'].replace('win_probability_', '')} {row['metric']}", f"{row['value']:.3f}")

    if not wp_test.empty:
        st.caption("Calibration check — predicted probability vs actual outcome on held-out matches")
        wp_test_sorted = wp_test.sort_values("predicted_proba").reset_index(drop=True)
        wp_test_sorted["bucket"] = pd.qcut(wp_test_sorted["predicted_proba"], 10, duplicates="drop")
        calib = wp_test_sorted.groupby("bucket").agg(
            predicted=("predicted_proba", "mean"), actual=("actual", "mean")
        ).reset_index()
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=calib["predicted"], y=calib["actual"], mode="markers+lines", name="Model"))
        fig2.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line=dict(dash="dash")))
        fig2.update_layout(xaxis_title="Predicted probability", yaxis_title="Actual win rate", height=350)
        st.plotly_chart(fig2, use_container_width=True)

# ── TAB 2: PLAYER FORECAST ───────────────────────────────────────────────────
with tab_forecast:
    st.subheader("Next-Season Run Projections")

    if not forecast.empty:
        fmt_options = sorted(forecast["format"].dropna().unique())
        fmt_pick = st.selectbox("Format", fmt_options, key="forecast_fmt")
        fdata = forecast[forecast["format"] == fmt_pick].sort_values("predicted_runs", ascending=False)

        st.dataframe(
            fdata[["striker", "year", "runs", "predicted_runs"]].head(20),
            use_container_width=True, hide_index=True,
        )

        fig3 = px.scatter(
            fdata, x="runs", y="predicted_runs", hover_name="striker",
            labels={"runs": "Actual runs", "predicted_runs": "Predicted runs"},
            title="Predicted vs actual — next-season runs",
        )
        max_val = max(fdata["runs"].max(), fdata["predicted_runs"].max()) if len(fdata) else 100
        fig3.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val, line=dict(dash="dash", color="gray"))
        st.plotly_chart(fig3, use_container_width=True)

        st.divider()
        st.subheader("Why this prediction? (SHAP breakdown)")
        player_pick = st.selectbox("Player", fdata["striker"].unique(), key="forecast_player")
        prow = fdata[fdata["striker"] == player_pick].iloc[0]

        shap_cols = [c for c in fdata.columns if c.startswith("shap_") and c != "shap_base_value"]
        if shap_cols:
            contrib = pd.DataFrame({
                "feature": [c.replace("shap_", "") for c in shap_cols],
                "contribution": [prow[c] for c in shap_cols],
            }).sort_values("contribution")
            fig4 = px.bar(
                contrib, x="contribution", y="feature", orientation="h",
                color="contribution", color_continuous_scale=["red", "lightgray", "green"],
                title=f"{player_pick} — base {prow.get('shap_base_value', 0):.0f} runs "
                      f"→ predicted {prow['predicted_runs']:.0f} runs",
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("SHAP contribution columns not found — re-run Step 16 to include them.")

        mae_row = model_metrics[(model_metrics["model"] == "run_forecast_rf") & (model_metrics["metric"] == "MAE")]
        r2_row = model_metrics[(model_metrics["model"] == "run_forecast_rf") & (model_metrics["metric"] == "R2")]
        c1, c2 = st.columns(2)
        if not mae_row.empty:
            c1.metric("Model MAE", f"{mae_row['value'].values[0]:.1f} runs")
        if not r2_row.empty:
            c2.metric("Model R²", f"{r2_row['value'].values[0]:.3f}")
    else:
        st.info("Forecast data not available yet.")

# ── TAB 3: BOWLER WORKLOAD ───────────────────────────────────────────────────
with tab_workload:
    st.subheader("Bowler Workload / Injury-Risk (ACWR)")

    if not workload.empty:
        risk_counts = workload["risk_flag"].value_counts().reset_index()
        risk_counts.columns = ["risk_flag", "count"]
        fig5 = px.pie(risk_counts, names="risk_flag", values="count", title="Risk distribution across all bowler-matches")
        st.plotly_chart(fig5, use_container_width=True)

        bowlers = sorted(workload["bowler"].dropna().unique())
        bowler_pick = st.selectbox("Bowler", bowlers)
        bdata = workload[workload["bowler"] == bowler_pick].sort_values("start_date")
        bdata["start_date"] = pd.to_datetime(bdata["start_date"])

        fig6 = go.Figure()
        fig6.add_trace(go.Scatter(x=bdata["start_date"], y=bdata["acwr"], mode="lines+markers", name="ACWR"))
        fig6.add_hrect(y0=0.8, y1=1.3, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Safe zone")
        fig6.add_hrect(y0=1.3, y1=1.5, fillcolor="yellow", opacity=0.15, line_width=0, annotation_text="Caution")
        fig6.add_hrect(y0=1.5, y1=bdata["acwr"].max() + 0.5 if len(bdata) else 2, fillcolor="red", opacity=0.1, line_width=0, annotation_text="High risk")
        fig6.update_layout(title=f"{bowler_pick} — workload trend over time", yaxis_title="ACWR", height=400)
        st.plotly_chart(fig6, use_container_width=True)

        st.subheader("Currently flagged high-risk bowlers")
        high_risk = workload[workload["risk_flag"] == "High injury risk"].sort_values("start_date", ascending=False)
        st.dataframe(high_risk[["bowler", "start_date", "acwr"]].head(15), use_container_width=True, hide_index=True)
    else:
        st.info("Workload data not available yet.")

# ── TAB 4: DATA INTEGRITY ────────────────────────────────────────────────────
with tab_qa:
    st.subheader("Data Integrity Audit")
    st.caption("Runs automatically every time the pipeline executes — flags issues before they reach the app.")

    if not integrity_df.empty:
        cols = st.columns(len(integrity_df))
        for c, (_, row) in zip(cols, integrity_df.iterrows()):
            ok = row["count"] == 0
            c.metric(
                row["check"].replace("_", " ").title(),
                int(row["count"]),
                delta="✓ clean" if ok else "⚠ needs review",
                delta_color="normal" if ok else "inverse",
            )
        if integrity_df["count"].sum() == 0:
            st.success("No integrity issues detected in the current dataset.")
        else:
            st.warning("Some checks flagged issues — review the affected rows before trusting downstream stats.")
    else:
        st.info("Integrity report not available yet.")
