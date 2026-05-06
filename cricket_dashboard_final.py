
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Cricket Analytics — All Formats", layout="wide", page_icon="🏏")

FORMAT_COLORS = {"ODI":"#2ecc71","Test":"#3498db","T20I":"#e74c3c","IPL":"#f39c12","PSL":"#9b59b6","All":"#95a5a6"}

@st.cache_data
def load_data():
    batting          = pd.read_csv("cricket_batting_stats.csv")
    bowling          = pd.read_csv("cricket_bowling_stats.csv")
    bat_fmt          = pd.read_csv("cricket_batting_by_format.csv")
    bowl_fmt         = pd.read_csv("cricket_bowling_by_format.csv")
    batting_yearly   = pd.read_csv("cricket_batting_yearly.csv")
    bowling_yearly   = pd.read_csv("cricket_bowling_yearly.csv")
    batting_venue    = pd.read_csv("cricket_batting_venue.csv")
    batting_opponent = pd.read_csv("cricket_batting_opponent.csv")
    bowling_venue    = pd.read_csv("cricket_bowling_venue.csv")
    bowling_opponent = pd.read_csv("cricket_bowling_opponent.csv")
    batter_vs_bowler = pd.read_csv("cricket_batter_vs_bowler.csv")
    bowler_vs_batter = pd.read_csv("cricket_bowler_vs_batter.csv")
    return (batting, bowling, bat_fmt, bowl_fmt, batting_yearly, bowling_yearly,
            batting_venue, batting_opponent, bowling_venue, bowling_opponent,
            batter_vs_bowler, bowler_vs_batter)

(batting, bowling, bat_fmt, bowl_fmt, batting_yearly, bowling_yearly,
 batting_venue, batting_opponent, bowling_venue, bowling_opponent,
 batter_vs_bowler, bowler_vs_batter) = load_data()

ALL_FORMATS = ["All", "ODI", "Test", "T20I", "IPL", "PSL"]

st.sidebar.title("🏏 Cricket Analytics")
fmt_filter = st.sidebar.selectbox("Format", ALL_FORMATS)
section = st.sidebar.radio("Navigate", [
    "🔍 Player Search",
    "⚔️  Head to Head",
    "🏟️  Player vs Venue",
    "🌍 Player vs Opponent",
    "🤜 Batter vs Bowler",
    "📈 Performance Over Years",
    "🏆 Leaderboard"
])

def filter_fmt(df, col="format"):
    return df if fmt_filter == "All" else df[df[col] == fmt_filter]

def find_batter(name, df=None):
    src = bat_fmt if df is None else df
    src = filter_fmt(src)
    return src[src["striker"].str.contains(name, case=False, na=False)]

def find_bowler(name, df=None):
    src = bowl_fmt if df is None else df
    src = filter_fmt(src)
    return src[src["bowler"].str.contains(name, case=False, na=False)]

# ═══════════════════════════════════════════════════════
# 1. PLAYER SEARCH
# ═══════════════════════════════════════════════════════
if section == "🔍 Player Search":
    st.title(f"🔍 Player Profile  [{fmt_filter}]")
    name = st.text_input("Enter player name (e.g. Kohli, Babar, Malinga)", "")
    if name:
        bat  = find_batter(name)
        bowl = find_bowler(name)
        if len(bat) == 0 and len(bowl) == 0:
            st.error(f"No player found for '{name}'. Try a last name.")
        else:
            if len(bat) > 0:
                p = bat.sort_values("runs", ascending=False).iloc[0]
                st.subheader(f"🏏 Batting — {p["striker"]}")
                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("Matches",      int(p["matches"]))
                c2.metric("Runs",         int(p["runs"]))
                c3.metric("Average",      p["average"])
                c4.metric("Strike Rate",  p["strike_rate"])
                c5.metric("Sixes",        int(p["sixes"]))

                # Format breakdown bar chart
                bat_all = bat_fmt[bat_fmt["striker"].str.contains(name, case=False, na=False)]
                if len(bat_all) > 1:
                    fig0 = px.bar(bat_all, x="format", y="runs", color="format",
                                  color_discrete_map=FORMAT_COLORS,
                                  title=f"{p["striker"]} — Runs by Format")
                    st.plotly_chart(fig0, use_container_width=True)

                by = batting_yearly[batting_yearly["striker"].str.contains(name, case=False, na=False)]
                by = filter_fmt(by)
                if len(by) > 0:
                    fig = px.line(by, x="year", y="runs", color="format",
                                  color_discrete_map=FORMAT_COLORS,
                                  title=f"{p["striker"]} — Runs per Year", markers=True)
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()
            if len(bowl) > 0:
                p2 = bowl.sort_values("wickets", ascending=False).iloc[0]
                st.subheader(f"🎳 Bowling — {p2["bowler"]}")
                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("Matches",     int(p2["matches"]))
                c2.metric("Wickets",     int(p2["wickets"]))
                c3.metric("Economy",     p2["economy"])
                c4.metric("Average",     p2["average"])
                c5.metric("Strike Rate", p2["strike_rate"])

                bowl_all = bowl_fmt[bowl_fmt["bowler"].str.contains(name, case=False, na=False)]
                if len(bowl_all) > 1:
                    fig0b = px.bar(bowl_all, x="format", y="wickets", color="format",
                                   color_discrete_map=FORMAT_COLORS,
                                   title=f"{p2["bowler"]} — Wickets by Format")
                    st.plotly_chart(fig0b, use_container_width=True)

                by2 = bowling_yearly[bowling_yearly["bowler"].str.contains(name, case=False, na=False)]
                by2 = filter_fmt(by2)
                if len(by2) > 0:
                    fig2 = px.line(by2, x="year", y="wickets", color="format",
                                   color_discrete_map=FORMAT_COLORS,
                                   title=f"{p2["bowler"]} — Wickets per Year", markers=True)
                    st.plotly_chart(fig2, use_container_width=True)

# ═══════════════════════════════════════════════════════
# 2. HEAD TO HEAD
# ═══════════════════════════════════════════════════════
elif section == "⚔️  Head to Head":
    st.title(f"⚔️ Head to Head  [{fmt_filter}]")
    col1, col2 = st.columns(2)
    p1_name = col1.text_input("Player 1", "Kohli")
    p2_name = col2.text_input("Player 2", "Babar Azam")
    if p1_name and p2_name:
        b1 = find_batter(p1_name)
        b2 = find_batter(p2_name)
        if len(b1) == 0 or len(b2) == 0:
            st.error("One or both players not found!")
        else:
            p1 = b1.groupby("striker").sum(numeric_only=True).reset_index().iloc[0]
            p2 = b2.groupby("striker").sum(numeric_only=True).reset_index().iloc[0]
            p1n = b1["striker"].iloc[0]
            p2n = b2["striker"].iloc[0]
            st.subheader("🏏 Batting Comparison")
            metrics = ["runs","average","strike_rate","fours","sixes","dot_pct","boundary_pct"]
            fig = go.Figure(data=[
                go.Bar(name=p1n, x=metrics, y=[float(p1.get(m,0)) for m in metrics], marker_color="#2ecc71"),
                go.Bar(name=p2n, x=metrics, y=[float(p2.get(m,0)) for m in metrics], marker_color="#3498db")
            ])
            fig.update_layout(barmode="group", title="Batting Metrics")
            st.plotly_chart(fig, use_container_width=True)

            # Format breakdown
            b1_fmt = bat_fmt[bat_fmt["striker"].str.contains(p1_name, case=False, na=False)].copy()
            b2_fmt = bat_fmt[bat_fmt["striker"].str.contains(p2_name, case=False, na=False)].copy()
            b1_fmt["player"] = p1n
            b2_fmt["player"] = p2n
            fig_fmt = px.bar(pd.concat([b1_fmt, b2_fmt]), x="format", y="runs",
                             color="player", barmode="group",
                             title="Runs by Format Comparison")
            st.plotly_chart(fig_fmt, use_container_width=True)

# ═══════════════════════════════════════════════════════
# 3. PLAYER VS VENUE
# ═══════════════════════════════════════════════════════
elif section == "🏟️  Player vs Venue":
    st.title(f"🏟️ Player vs Venue  [{fmt_filter}]")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting", "Bowling"], horizontal=True)
    if name:
        if stat_type == "Batting":
            df_v = batting_venue[batting_venue["striker"].str.contains(name, case=False, na=False)]
            df_v = filter_fmt(df_v)
            if len(df_v) > 0:
                metric = st.selectbox("Metric", ["runs","average","strike_rate","fours","sixes"])
                df_v = df_v.sort_values(metric, ascending=False)
                fig = px.bar(df_v.head(20), x=metric, y="venue", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"{df_v["striker"].iloc[0]} — {metric} by Venue (Top 20)")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_v[["venue","format","innings","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
        else:
            df_v = bowling_venue[bowling_venue["bowler"].str.contains(name, case=False, na=False)]
            df_v = filter_fmt(df_v)
            if len(df_v) > 0:
                metric = st.selectbox("Metric", ["wickets","economy","average","dot_pct"])
                df_v = df_v.sort_values(metric, ascending=False)
                fig = px.bar(df_v.head(20), x=metric, y="venue", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"{df_v["bowler"].iloc[0]} — {metric} by Venue (Top 20)")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_v[["venue","format","innings","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 4. PLAYER VS OPPONENT
# ═══════════════════════════════════════════════════════
elif section == "🌍 Player vs Opponent":
    st.title(f"🌍 Player vs Opponent  [{fmt_filter}]")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting", "Bowling"], horizontal=True)
    if name:
        if stat_type == "Batting":
            df_o = batting_opponent[batting_opponent["striker"].str.contains(name, case=False, na=False)]
            df_o = filter_fmt(df_o)
            if len(df_o) > 0:
                metric = st.selectbox("Metric", ["runs","average","strike_rate","fours","sixes"])
                df_o = df_o.sort_values(metric, ascending=False)
                fig = px.bar(df_o, x=metric, y="opponent", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"{df_o["striker"].iloc[0]} — {metric} vs Each Team")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_o[["opponent","format","innings","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
        else:
            df_o = bowling_opponent[bowling_opponent["bowler"].str.contains(name, case=False, na=False)]
            df_o = filter_fmt(df_o)
            if len(df_o) > 0:
                metric = st.selectbox("Metric", ["wickets","economy","average","dot_pct"])
                df_o = df_o.sort_values(metric, ascending=False)
                fig = px.bar(df_o, x=metric, y="opponent", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"{df_o["bowler"].iloc[0]} — {metric} vs Each Team")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_o[["opponent","format","innings","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 5. BATTER VS BOWLER
# ═══════════════════════════════════════════════════════
elif section == "🤜 Batter vs Bowler":
    st.title(f"🤜 Batter vs Bowler  [{fmt_filter}]")
    matchup_type = st.radio("I want to look up a...", ["Batter", "Bowler"], horizontal=True)
    if matchup_type == "Batter":
        name = st.text_input("Enter batter name", "Kohli")
        if name:
            df_m = batter_vs_bowler[batter_vs_bowler["striker"].str.contains(name, case=False, na=False)]
            df_m = filter_fmt(df_m)
            if len(df_m) > 0:
                metric = st.selectbox("Sort by", ["runs","strike_rate","average","balls_faced","dismissals"])
                df_m = df_m.sort_values(metric, ascending=False)
                fig = px.bar(df_m.head(25), x=metric, y="bowler", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"vs Top 25 Bowlers — {metric}")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_m[["bowler","format","balls_faced","runs","average","strike_rate","dismissals","fours","sixes"]].reset_index(drop=True))
    else:
        name = st.text_input("Enter bowler name", "Malinga")
        if name:
            df_m = bowler_vs_batter[bowler_vs_batter["bowler"].str.contains(name, case=False, na=False)]
            df_m = filter_fmt(df_m)
            if len(df_m) > 0:
                metric = st.selectbox("Sort by", ["wickets","economy","dot_pct","runs_given","balls_bowled"])
                df_m = df_m.sort_values(metric, ascending=(metric in ["economy","dot_pct"]))
                fig = px.bar(df_m.head(25), x=metric, y="striker", orientation="h",
                             color="format", color_discrete_map=FORMAT_COLORS,
                             title=f"vs Top 25 Batters — {metric}")
                fig.update_layout(yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_m[["striker","format","balls_bowled","runs_given","wickets","economy","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 6. PERFORMANCE OVER YEARS
# ═══════════════════════════════════════════════════════
elif section == "📈 Performance Over Years":
    st.title(f"📈 Performance Over Years  [{fmt_filter}]")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting", "Bowling"], horizontal=True)
    if name:
        if stat_type == "Batting":
            by = batting_yearly[batting_yearly["striker"].str.contains(name, case=False, na=False)]
            by = filter_fmt(by)
            if len(by) > 0:
                metric = st.selectbox("Metric", ["runs","average","strike_rate","fours","sixes"])
                fig = px.bar(by, x="year", y=metric, color="format",
                             color_discrete_map=FORMAT_COLORS,
                             title=f"{by["striker"].iloc[0]} — {metric} per Year")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(by[["year","format","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
        else:
            by = bowling_yearly[bowling_yearly["bowler"].str.contains(name, case=False, na=False)]
            by = filter_fmt(by)
            if len(by) > 0:
                metric = st.selectbox("Metric", ["wickets","economy","average","dot_pct"])
                fig = px.bar(by, x="year", y=metric, color="format",
                             color_discrete_map=FORMAT_COLORS,
                             title=f"{by["bowler"].iloc[0]} — {metric} per Year")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(by[["year","format","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 7. LEADERBOARD
# ═══════════════════════════════════════════════════════
elif section == "🏆 Leaderboard":
    st.title(f"🏆 Leaderboards  [{fmt_filter}]")
    tab1, tab2 = st.tabs(["🏏 Batting", "🎳 Bowling"])
    bat_src  = filter_fmt(bat_fmt)  if fmt_filter != "All" else batting
    bowl_src = filter_fmt(bowl_fmt) if fmt_filter != "All" else bowling
    with tab1:
        col1, col2 = st.columns(2)
        sort_by  = col1.selectbox("Rank by", ["runs","average","strike_rate","sixes","fours","boundary_pct"])
        min_runs = col2.slider("Minimum runs", 0, 5000, 500, 100)
        top_n    = st.slider("Show top N", 5, 50, 20)
        lb = bat_src[bat_src["runs"] >= min_runs].sort_values(sort_by, ascending=False).head(top_n)
        lb.insert(0, "Rank", range(1, len(lb)+1))
        fig = px.bar(lb, x=sort_by, y="striker", orientation="h",
                     color=sort_by, color_continuous_scale="Greens",
                     title=f"Top {top_n} by {sort_by}", labels={"striker":"Player"})
        fig.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        show_cols = ["Rank","striker","format","matches","runs","average","strike_rate","fours","sixes"] if "format" in lb.columns else ["Rank","striker","matches","runs","average","strike_rate","fours","sixes"]
        st.dataframe(lb[[c for c in show_cols if c in lb.columns]].reset_index(drop=True))
    with tab2:
        col1, col2 = st.columns(2)
        sort_by2 = col1.selectbox("Rank by", ["wickets","economy","average","dot_pct","strike_rate"])
        min_wkts = col2.slider("Minimum wickets", 0, 200, 20, 10)
        top_n2   = st.slider("Show top N bowlers", 5, 50, 20)
        lb2 = bowl_src[bowl_src["wickets"] >= min_wkts].sort_values(
            sort_by2, ascending=(sort_by2 in ["economy","average","strike_rate"])
        ).head(top_n2)
        lb2.insert(0, "Rank", range(1, len(lb2)+1))
        fig2 = px.bar(lb2, x="wickets", y="bowler", orientation="h",
                      color="economy", color_continuous_scale="Reds_r",
                      title=f"Top {top_n2} Bowlers", labels={"bowler":"Player"})
        fig2.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig2, use_container_width=True)
        show_cols2 = ["Rank","bowler","format","matches","wickets","economy","average","dot_pct"] if "format" in lb2.columns else ["Rank","bowler","matches","wickets","economy","average","dot_pct"]
        st.dataframe(lb2[[c for c in show_cols2 if c in lb2.columns]].reset_index(drop=True))
