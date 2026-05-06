import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Cricket Analytics — All Formats", layout="wide", page_icon="🏏")

FORMAT_COLORS = {"ODI":"#2ecc71","Test":"#3498db","T20I":"#e74c3c","IPL":"#f39c12","PSL":"#9b59b6"}

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

st.sidebar.title("🏏 Cricket Analytics")
section = st.sidebar.radio("Navigate", [
    "🔍 Player Search",
    "⚔️  Head to Head",
    "🏟️  Player vs Venue",
    "🌍 Player vs Opponent",
    "🤜 Batter vs Bowler",
    "📈 Performance Over Years",
    "🏆 Leaderboard"
])

FORMATS = ["ODI", "Test", "T20I", "IPL", "PSL"]

# ═══════════════════════════════════════════════════════
# 1. PLAYER SEARCH  — format chosen AFTER player name
# ═══════════════════════════════════════════════════════
if section == "🔍 Player Search":
    st.title("🔍 Player Profile")

    name = st.text_input("Enter player name (e.g. Babar, Kohli, Malinga)", "")

    if name:
        # Check which formats this player actually has data in
        available_bat  = bat_fmt[bat_fmt["striker"].str.contains(name, case=False, na=False)]["format"].unique().tolist()
        available_bowl = bowl_fmt[bowl_fmt["bowler"].str.contains(name, case=False, na=False)]["format"].unique().tolist()
        available = sorted(set(available_bat + available_bowl), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)

        if not available:
            st.error(f"No player found for '{name}'. Try a last name.")
            st.stop()

        fmt = st.radio("Select Format", available, horizontal=True)

        bat  = bat_fmt[(bat_fmt["striker"].str.contains(name, case=False, na=False)) & (bat_fmt["format"] == fmt)]
        bowl = bowl_fmt[(bowl_fmt["bowler"].str.contains(name, case=False, na=False)) & (bowl_fmt["format"] == fmt)]

        # ── Batting card ──────────────────────────────────────
        if len(bat) > 0:
            p = bat.sort_values("runs", ascending=False).iloc[0]
            player_name = p["striker"]
            st.subheader(f"🏏 {player_name} — Batting ({fmt})")

            c1,c2,c3,c4,c5,c6 = st.columns(6)
            c1.metric("Matches",     int(p["matches"]))
            c2.metric("Runs",        int(p["runs"]))
            c3.metric("Average",     p["average"])
            c4.metric("Strike Rate", p["strike_rate"])
            c5.metric("4s",          int(p["fours"]))
            c6.metric("6s",          int(p["sixes"]))

            c7,c8,c9,c10 = st.columns(4)
            c7.metric("Dismissals",   int(p["dismissals"]))
            c8.metric("Balls Faced",  int(p["balls_faced"]))
            c9.metric("Dot Ball %",   f"{p['dot_pct']}%")
            c10.metric("Boundary %",  f"{p['boundary_pct']}%")

            # Runs per year — bar chart (cleaner than multi-axis line)
            by = batting_yearly[
                (batting_yearly["striker"].str.contains(name, case=False, na=False)) &
                (batting_yearly["format"] == fmt)
            ]
            if len(by) > 1:
                st.markdown("**Runs per Year**")
                fig = px.bar(by.sort_values("year"), x="year", y="runs",
                             color_discrete_sequence=[FORMAT_COLORS.get(fmt,"#2ecc71")],
                             text="runs")
                fig.update_traces(textposition="outside")
                fig.update_layout(xaxis=dict(tickmode="linear"), yaxis_title="Runs", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            # Average & SR trend — separate charts to avoid misleading dual-axis
            if len(by) > 1:
                col_a, col_b = st.columns(2)
                with col_a:
                    fig2 = px.line(by.sort_values("year"), x="year", y="average",
                                   markers=True, title="Batting Average per Year",
                                   color_discrete_sequence=[FORMAT_COLORS.get(fmt,"#2ecc71")])
                    fig2.update_layout(yaxis_title="Average")
                    st.plotly_chart(fig2, use_container_width=True)
                with col_b:
                    fig3 = px.line(by.sort_values("year"), x="year", y="strike_rate",
                                   markers=True, title="Strike Rate per Year",
                                   color_discrete_sequence=["#f39c12"])
                    fig3.update_layout(yaxis_title="Strike Rate")
                    st.plotly_chart(fig3, use_container_width=True)

            # Boundary breakdown pie
            st.markdown("**Scoring Breakdown**")
            fours_runs = int(p["fours"]) * 4
            sixes_runs = int(p["sixes"]) * 6
            other_runs = max(0, int(p["runs"]) - fours_runs - sixes_runs)
            pie_df = pd.DataFrame({"Source": ["Fours","Sixes","Singles/Twos/Threes"],
                                   "Runs":   [fours_runs, sixes_runs, other_runs]})
            fig_pie = px.pie(pie_df, names="Source", values="Runs",
                             color_discrete_sequence=["#2ecc71","#e74c3c","#3498db"],
                             hole=0.4)
            fig_pie.update_traces(textinfo="percent+label")
            col_pie, col_space = st.columns([1,1])
            with col_pie:
                st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # ── Bowling card ──────────────────────────────────────
        if len(bowl) > 0:
            p2 = bowl.sort_values("wickets", ascending=False).iloc[0]
            st.subheader(f"🎳 {p2['bowler']} — Bowling ({fmt})")

            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Matches",     int(p2["matches"]))
            c2.metric("Wickets",     int(p2["wickets"]))
            c3.metric("Economy",     p2["economy"])
            c4.metric("Average",     p2["average"])
            c5.metric("Strike Rate", p2["strike_rate"])

            by2 = bowling_yearly[
                (bowling_yearly["bowler"].str.contains(name, case=False, na=False)) &
                (bowling_yearly["format"] == fmt)
            ]
            if len(by2) > 1:
                st.markdown("**Wickets per Year**")
                fig4 = px.bar(by2.sort_values("year"), x="year", y="wickets",
                              color_discrete_sequence=[FORMAT_COLORS.get(fmt,"#e74c3c")],
                              text="wickets")
                fig4.update_traces(textposition="outside")
                fig4.update_layout(xaxis=dict(tickmode="linear"), showlegend=False)
                st.plotly_chart(fig4, use_container_width=True)

                col_a, col_b = st.columns(2)
                with col_a:
                    fig5 = px.line(by2.sort_values("year"), x="year", y="economy",
                                   markers=True, title="Economy per Year",
                                   color_discrete_sequence=["#e74c3c"])
                    st.plotly_chart(fig5, use_container_width=True)
                with col_b:
                    fig6 = px.line(by2.sort_values("year"), x="year", y="average",
                                   markers=True, title="Bowling Average per Year",
                                   color_discrete_sequence=["#9b59b6"])
                    st.plotly_chart(fig6, use_container_width=True)

        if len(bat) == 0 and len(bowl) == 0:
            st.warning(f"No {fmt} data found for '{name}'.")

# ═══════════════════════════════════════════════════════
# 2. HEAD TO HEAD
# ═══════════════════════════════════════════════════════
elif section == "⚔️  Head to Head":
    st.title("⚔️ Head to Head Comparison")
    col1, col2 = st.columns(2)
    p1_name = col1.text_input("Player 1", "Kohli")
    p2_name = col2.text_input("Player 2", "Babar Azam")

    if p1_name and p2_name:
        fmt = st.radio("Format", FORMATS, horizontal=True)

        b1 = bat_fmt[(bat_fmt["striker"].str.contains(p1_name, case=False, na=False)) & (bat_fmt["format"] == fmt)]
        b2 = bat_fmt[(bat_fmt["striker"].str.contains(p2_name, case=False, na=False)) & (bat_fmt["format"] == fmt)]

        if len(b1) == 0 or len(b2) == 0:
            st.error(f"One or both players have no {fmt} data.")
        else:
            p1 = b1.iloc[0]; p2 = b2.iloc[0]
            p1n = p1["striker"];  p2n = p2["striker"]
            st.subheader(f"🏏 Batting — {fmt}")

            # Separate charts per metric to avoid scale distortion
            metrics_pct  = ["dot_pct","boundary_pct"]
            metrics_rate = ["average","strike_rate"]
            metrics_vol  = ["runs","fours","sixes"]

            for title, mlist in [("Volume (Runs / 4s / 6s)", metrics_vol),
                                  ("Rates (Average / Strike Rate)", metrics_rate),
                                  ("Percentages", metrics_pct)]:
                fig = go.Figure(data=[
                    go.Bar(name=p1n, x=mlist, y=[float(p1.get(m,0)) for m in mlist], marker_color="#2ecc71"),
                    go.Bar(name=p2n, x=mlist, y=[float(p2.get(m,0)) for m in mlist], marker_color="#3498db")
                ])
                fig.update_layout(barmode="group", title=title, height=300)
                st.plotly_chart(fig, use_container_width=True)

            # Yearly runs line
            by1 = batting_yearly[(batting_yearly["striker"].str.contains(p1_name, case=False, na=False)) & (batting_yearly["format"]==fmt)].copy()
            by2 = batting_yearly[(batting_yearly["striker"].str.contains(p2_name, case=False, na=False)) & (batting_yearly["format"]==fmt)].copy()
            if len(by1) > 0 and len(by2) > 0:
                by1["player"] = p1n; by2["player"] = p2n
                fig3 = px.line(pd.concat([by1,by2]), x="year", y="runs",
                               color="player", markers=True, title=f"Runs Per Year ({fmt})")
                st.plotly_chart(fig3, use_container_width=True)

            # Bowling comparison
            bw1 = bowl_fmt[(bowl_fmt["bowler"].str.contains(p1_name, case=False, na=False)) & (bowl_fmt["format"]==fmt)]
            bw2 = bowl_fmt[(bowl_fmt["bowler"].str.contains(p2_name, case=False, na=False)) & (bowl_fmt["format"]==fmt)]
            if len(bw1) > 0 and len(bw2) > 0:
                st.subheader(f"🎳 Bowling — {fmt}")
                pw1 = bw1.iloc[0]; pw2 = bw2.iloc[0]
                for title, mlist in [("Wickets / Dot %", ["wickets","dot_pct"]),
                                     ("Economy / Average / SR", ["economy","average","strike_rate"])]:
                    fig4 = go.Figure(data=[
                        go.Bar(name=pw1["bowler"], x=mlist, y=[float(pw1.get(m,0)) for m in mlist], marker_color="#e74c3c"),
                        go.Bar(name=pw2["bowler"], x=mlist, y=[float(pw2.get(m,0)) for m in mlist], marker_color="#9b59b6")
                    ])
                    fig4.update_layout(barmode="group", title=title, height=300)
                    st.plotly_chart(fig4, use_container_width=True)

# ═══════════════════════════════════════════════════════
# 3. PLAYER VS VENUE
# ═══════════════════════════════════════════════════════
elif section == "🏟️  Player vs Venue":
    st.title("🏟️ Player vs Venue")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting","Bowling"], horizontal=True)

    if name:
        if stat_type == "Batting":
            src = batting_venue[batting_venue["striker"].str.contains(name, case=False, na=False)]
        else:
            src = bowling_venue[bowling_venue["bowler"].str.contains(name, case=False, na=False)]

        if len(src) == 0:
            st.error("Player not found!")
        else:
            avail_fmts = sorted(src["format"].unique().tolist(), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)
            fmt = st.radio("Format", avail_fmts, horizontal=True)
            df_v = src[src["format"] == fmt]

            if stat_type == "Batting":
                metric = st.selectbox("Metric", ["runs","average","strike_rate","fours","sixes"])
                df_v = df_v.sort_values(metric, ascending=False).head(20)
                fig = px.bar(df_v, x=metric, y="venue", orientation="h",
                             color=metric, color_continuous_scale="Greens",
                             title=f"{df_v['striker'].iloc[0]} — {metric} by Venue ({fmt})")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=600)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_v[["venue","innings","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
            else:
                metric = st.selectbox("Metric", ["wickets","economy","average","dot_pct"])
                df_v = df_v.sort_values(metric, ascending=False).head(20)
                fig = px.bar(df_v, x=metric, y="venue", orientation="h",
                             color=metric, color_continuous_scale="Reds",
                             title=f"{df_v['bowler'].iloc[0]} — {metric} by Venue ({fmt})")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=600)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_v[["venue","innings","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 4. PLAYER VS OPPONENT
# ═══════════════════════════════════════════════════════
elif section == "🌍 Player vs Opponent":
    st.title("🌍 Player vs Opponent")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting","Bowling"], horizontal=True)

    if name:
        if stat_type == "Batting":
            src = batting_opponent[batting_opponent["striker"].str.contains(name, case=False, na=False)]
        else:
            src = bowling_opponent[bowling_opponent["bowler"].str.contains(name, case=False, na=False)]

        if len(src) == 0:
            st.error("Player not found!")
        else:
            avail_fmts = sorted(src["format"].unique().tolist(), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)
            fmt = st.radio("Format", avail_fmts, horizontal=True)
            df_o = src[src["format"] == fmt]

            if stat_type == "Batting":
                metric = st.selectbox("Metric", ["runs","average","strike_rate","fours","sixes"])
                df_o = df_o.sort_values(metric, ascending=False)
                fig = px.bar(df_o, x=metric, y="opponent", orientation="h",
                             color=metric, color_continuous_scale="Blues",
                             title=f"{df_o['striker'].iloc[0]} — {metric} vs Each Team ({fmt})")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=500)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_o[["opponent","innings","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
            else:
                metric = st.selectbox("Metric", ["wickets","economy","average","dot_pct"])
                df_o = df_o.sort_values(metric, ascending=False)
                fig = px.bar(df_o, x=metric, y="opponent", orientation="h",
                             color=metric, color_continuous_scale="Purples",
                             title=f"{df_o['bowler'].iloc[0]} — {metric} vs Each Team ({fmt})")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=500)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_o[["opponent","innings","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 5. BATTER VS BOWLER
# ═══════════════════════════════════════════════════════
elif section == "🤜 Batter vs Bowler":
    st.title("🤜 Batter vs Bowler Matchups")
    matchup_type = st.radio("Look up a...", ["Batter","Bowler"], horizontal=True)

    if matchup_type == "Batter":
        name = st.text_input("Enter batter name", "Babar Azam")
        if name:
            src = batter_vs_bowler[batter_vs_bowler["striker"].str.contains(name, case=False, na=False)]
            if len(src) == 0:
                st.error("Batter not found!")
            else:
                avail_fmts = sorted(src["format"].unique().tolist(), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)
                fmt = st.radio("Format", avail_fmts, horizontal=True)
                df_m = src[src["format"] == fmt].sort_values("balls_faced", ascending=False)
                st.subheader(f"{df_m['striker'].iloc[0]} vs bowlers in {fmt} (10+ balls faced)")
                metric = st.selectbox("Sort by", ["balls_faced","runs","strike_rate","dismissals"])
                df_m = df_m.sort_values(metric, ascending=False).head(25)
                fig = px.bar(df_m, x=metric, y="bowler", orientation="h",
                             color=metric, color_continuous_scale="Greens",
                             title=f"Top 25 Bowlers faced — {metric}")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=600)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_m[["bowler","balls_faced","runs","strike_rate","dismissals","fours","sixes"]].reset_index(drop=True))
    else:
        name = st.text_input("Enter bowler name", "Shaheen")
        if name:
            src = bowler_vs_batter[bowler_vs_batter["bowler"].str.contains(name, case=False, na=False)]
            if len(src) == 0:
                st.error("Bowler not found!")
            else:
                avail_fmts = sorted(src["format"].unique().tolist(), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)
                fmt = st.radio("Format", avail_fmts, horizontal=True)
                df_m = src[src["format"] == fmt]
                st.subheader(f"{df_m['bowler'].iloc[0]} vs batters in {fmt} (10+ balls bowled)")
                metric = st.selectbox("Sort by", ["wickets","economy","dot_pct","runs_given"])
                df_m = df_m.sort_values(metric, ascending=(metric in ["economy","dot_pct"])).head(25)
                fig = px.bar(df_m, x=metric, y="striker", orientation="h",
                             color=metric, color_continuous_scale="Reds",
                             title=f"Top 25 Batters bowled to — {metric}")
                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=600)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_m[["striker","balls_bowled","runs_given","wickets","economy","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 6. PERFORMANCE OVER YEARS
# ═══════════════════════════════════════════════════════
elif section == "📈 Performance Over Years":
    st.title("📈 Performance Over Years")
    name      = st.text_input("Enter player name", "Kohli")
    stat_type = st.radio("Type", ["Batting","Bowling"], horizontal=True)

    if name:
        if stat_type == "Batting":
            src = batting_yearly[batting_yearly["striker"].str.contains(name, case=False, na=False)]
        else:
            src = bowling_yearly[bowling_yearly["bowler"].str.contains(name, case=False, na=False)]

        if len(src) == 0:
            st.error("Player not found!")
        else:
            avail_fmts = sorted(src["format"].unique().tolist(), key=lambda x: FORMATS.index(x) if x in FORMATS else 99)
            fmt = st.radio("Format", avail_fmts, horizontal=True)
            by = src[src["format"] == fmt].sort_values("year")

            if stat_type == "Batting":
                col_a, col_b = st.columns(2)
                with col_a:
                    fig1 = px.bar(by, x="year", y="runs", text="runs",
                                  title="Runs per Year",
                                  color_discrete_sequence=[FORMAT_COLORS.get(fmt,"#2ecc71")])
                    fig1.update_traces(textposition="outside")
                    fig1.update_layout(xaxis=dict(tickmode="linear"))
                    st.plotly_chart(fig1, use_container_width=True)
                with col_b:
                    fig2 = px.bar(by, x="year", y="matches", text="matches",
                                  title="Matches per Year",
                                  color_discrete_sequence=["#95a5a6"])
                    fig2.update_traces(textposition="outside")
                    fig2.update_layout(xaxis=dict(tickmode="linear"))
                    st.plotly_chart(fig2, use_container_width=True)
                fig3 = px.line(by, x="year", y=["average","strike_rate"],
                               markers=True, title="Average vs Strike Rate per Year")
                st.plotly_chart(fig3, use_container_width=True)
                st.dataframe(by[["year","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    fig1 = px.bar(by, x="year", y="wickets", text="wickets",
                                  title="Wickets per Year",
                                  color_discrete_sequence=[FORMAT_COLORS.get(fmt,"#e74c3c")])
                    fig1.update_traces(textposition="outside")
                    fig1.update_layout(xaxis=dict(tickmode="linear"))
                    st.plotly_chart(fig1, use_container_width=True)
                with col_b:
                    fig2 = px.line(by, x="year", y="economy",
                                   markers=True, title="Economy per Year",
                                   color_discrete_sequence=["#e74c3c"])
                    st.plotly_chart(fig2, use_container_width=True)
                st.dataframe(by[["year","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ═══════════════════════════════════════════════════════
# 7. LEADERBOARD
# ═══════════════════════════════════════════════════════
elif section == "🏆 Leaderboard":
    st.title("🏆 Leaderboard")
    fmt = st.radio("Format", FORMATS, horizontal=True)
    tab1, tab2 = st.tabs(["🏏 Batting", "🎳 Bowling"])

    with tab1:
        bat_src = bat_fmt[bat_fmt["format"] == fmt]
        col1, col2 = st.columns(2)
        sort_by  = col1.selectbox("Rank by", ["runs","average","strike_rate","sixes","fours","boundary_pct"])
        min_runs = col2.slider("Minimum runs", 0, 3000, 200, 100)
        top_n    = st.slider("Show top N", 5, 30, 15)
        lb = bat_src[bat_src["runs"] >= min_runs].sort_values(sort_by, ascending=False).head(top_n)
        lb = lb.reset_index(drop=True)
        lb.insert(0, "Rank", range(1, len(lb)+1))
        fig = px.bar(lb, x=sort_by, y="striker", orientation="h",
                     color=sort_by, color_continuous_scale="Greens",
                     title=f"Top {top_n} {fmt} Batters by {sort_by}",
                     labels={"striker":"Player"})
        fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=max(400, top_n*28))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(lb[["Rank","striker","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))

    with tab2:
        bowl_src = bowl_fmt[bowl_fmt["format"] == fmt]
        col1, col2 = st.columns(2)
        sort_by2 = col1.selectbox("Rank by", ["wickets","economy","average","dot_pct","strike_rate"])
        min_wkts = col2.slider("Minimum wickets", 0, 100, 10, 5)
        top_n2   = st.slider("Show top N bowlers", 5, 30, 15)
        lb2 = bowl_src[bowl_src["wickets"] >= min_wkts].sort_values(
            sort_by2, ascending=(sort_by2 in ["economy","average","strike_rate"])
        ).head(top_n2)
        lb2 = lb2.reset_index(drop=True)
        lb2.insert(0, "Rank", range(1, len(lb2)+1))
        fig2 = px.bar(lb2, x="wickets", y="bowler", orientation="h",
                      color="economy", color_continuous_scale="Reds_r",
                      title=f"Top {top_n2} {fmt} Bowlers",
                      labels={"bowler":"Player"})
        fig2.update_layout(yaxis={"categoryorder":"total ascending"}, height=max(400, top_n2*28))
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(lb2[["Rank","bowler","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))
