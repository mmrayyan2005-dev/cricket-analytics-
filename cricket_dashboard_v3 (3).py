import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Cricket Analytics", layout="wide", page_icon="🏏",
                   initial_sidebar_state="collapsed")

FC = {"ODI":"#00b894","Test":"#0984e3","T20I":"#d63031","IPL":"#e17055","PSL":"#6c5ce7"}
FORMATS = ["ODI","Test","T20I","IPL","PSL"]
BG = "#0f1117"; CARD = "#1e2130"; TEXT = "#f0f0f0"; GRID = "#2a2d3e"

BASE = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT, family="Inter,sans-serif", size=12),
            legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1,
                        bgcolor="rgba(0,0,0,0)",font=dict(size=11)),
            xaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT),
            yaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT))

# Each chart type uses its own margin via update_layout
M_DEFAULT = dict(l=8,r=8,t=48,b=8)
M_BARV    = dict(l=8,r=8,t=48,b=60)
M_BARH    = dict(l=180,r=16,t=48,b=8)

CFG = dict(
    config={
        "staticPlot": True,      # completely disables touch zoom/pan/shape changes
        "responsive": True,
    },
    use_container_width=True
)

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{{font-family:'Inter',sans-serif;background:{BG};color:{TEXT}}}
[data-testid="stMetric"]{{background:{CARD};border-radius:12px;padding:12px 16px;border:1px solid {GRID}}}
[data-testid="stMetricLabel"]{{font-size:11px;color:#aaa;text-transform:uppercase;letter-spacing:.5px}}
[data-testid="stMetricValue"]{{font-size:22px;font-weight:700;color:{TEXT}}}
[data-testid="column"]{{min-width:90px!important}}
.js-plotly-plot{{touch-action:pan-y!important}}
</style>""", unsafe_allow_html=True)

@st.cache_data
def load():
    return (pd.read_csv("cricket_batting_stats.csv"),
            pd.read_csv("cricket_bowling_stats.csv"),
            pd.read_csv("cricket_batting_by_format.csv"),
            pd.read_csv("cricket_bowling_by_format.csv"),
            pd.read_csv("cricket_batting_yearly.csv"),
            pd.read_csv("cricket_bowling_yearly.csv"),
            pd.read_csv("cricket_batting_venue.csv"),
            pd.read_csv("cricket_batting_opponent.csv"),
            pd.read_csv("cricket_bowling_venue.csv"),
            pd.read_csv("cricket_bowling_opponent.csv"),
            pd.read_csv("cricket_batter_vs_bowler.csv"),
            pd.read_csv("cricket_bowler_vs_batter.csv"))

(batting,bowling,bat_fmt,bowl_fmt,bat_yr,bowl_yr,
 bat_ven,bat_opp,bowl_ven,bowl_opp,bvb,wvb) = load()

# Common nickname → Cricsheet full name mapping
NAME_ALIASES = {
    "steve smith":    "SPD Smith",
    "smith":          "SPD Smith",
    "hazelwood":      "JR Hazlewood",
    "josh hazelwood": "JR Hazlewood",
    "hazlewood":      "JR Hazlewood",
    "warner":         "DA Warner",
    "david warner":   "DA Warner",
    "rohit":          "RG Sharma",
    "rohit sharma":   "RG Sharma",
    "bumrah":         "JJ Bumrah",
    "jasprit bumrah": "JJ Bumrah",
    "starc":          "MA Starc",
    "mitchell starc": "MA Starc",
    "kohli":          "V Kohli",
    "virat kohli":    "V Kohli",
    "babar":          "Babar Azam",
    "de villiers":    "AB de Villiers",
    "ab de villiers": "AB de Villiers",
    "stokes":         "BA Stokes",
    "ben stokes":     "BA Stokes",
    "root":           "JE Root",
    "joe root":       "JE Root",
    "anderson":       "JM Anderson",
    "james anderson": "JM Anderson",
    "broad":          "SCJ Broad",
    "stuart broad":   "SCJ Broad",
    "afridi":         "Shahid Afridi",
    "shaheen":        "Shaheen Shah Afridi",
    "rizwan":         "Mohammad Rizwan",
    "rashid":         "Rashid Khan",
    "buttler":        "JC Buttler",
    "jos buttler":    "JC Buttler",
    "maxwell":        "GJ Maxwell",
    "glenn maxwell":  "GJ Maxwell",
    "dhoni":          "MS Dhoni",
    "sachin":         "SR Tendulkar",
    "tendulkar":      "SR Tendulkar",
    "ponting":        "RT Ponting",
    "ricky ponting":  "RT Ponting",
    "kumara sangakkara": "KC Sangakkara",
    "sangakkara":     "KC Sangakkara",
    "malinga":        "SL Malinga",
}

def resolve_name(name):
    """Return search term — alias if found, else original."""
    return NAME_ALIASES.get(name.strip().lower(), name)

st.sidebar.title("🏏 Cricket Analytics")
section = st.sidebar.radio("Navigate",[
    "🔍 Player Search","⚔️ Head to Head","🏟️ Player vs Venue",
    "🌍 Player vs Opponent","🤜 Batter vs Bowler",
    "📈 Performance Over Years","🏆 Leaderboard"])

def avail(df,col):
    return sorted(df[col].unique().tolist(), key=lambda x:FORMATS.index(x) if x in FORMATS else 99)

def ch(fig,h=320,margin=None):
    fig.update_layout(**BASE, height=h, margin=margin or M_DEFAULT)
    st.plotly_chart(fig,**CFG)

def bar_h(df,x,y,col,scale,title):
    h = max(380,len(df)*38)
    fig=px.bar(df,x=x,y=y,orientation="h",color=col,color_continuous_scale=scale,title=title)
    fig.update_traces(marker_line_width=0)
    # large left margin so player names never get cut off
    fig.update_layout(**BASE,height=h,coloraxis_showscale=False,margin=M_BARH)
    fig.update_yaxes(categoryorder="total ascending",showgrid=False,
                     tickfont=dict(size=12),automargin=True)
    fig.update_xaxes(showgrid=True,gridcolor=GRID)
    return fig

def bar_v(df,x,y,title,color,h=340):
    fig=px.bar(df,x=x,y=y,text=y,title=title,color_discrete_sequence=[color])
    fig.update_traces(textposition="outside",textfont=dict(size=11,color=TEXT),marker_line_width=0)
    fig.update_layout(**BASE,height=h,showlegend=False,margin=M_BARV)
    fig.update_xaxes(tickmode="linear",tickangle=-40,showgrid=False,
                     tickfont=dict(size=11),automargin=True)
    fig.update_yaxes(showgrid=True,gridcolor=GRID)
    return fig

def line(df,x,y,title,color,h=260):
    fig=px.line(df,x=x,y=y,markers=True,title=title)
    fig.update_traces(line=dict(color=color,width=2.5),
                      marker=dict(size=7,color=color,line=dict(width=1.5,color=BG)))
    fig.update_layout(**BASE,height=h)
    return fig

def donut(labels,values,colors,title):
    fig=go.Figure(go.Pie(labels=labels,values=values,hole=0.52,
        marker=dict(colors=colors,line=dict(color=BG,width=2)),
        textinfo="percent+label",textfont=dict(size=12,color=TEXT)))
    fig.update_layout(**BASE,height=300,title=title,showlegend=False)
    return fig

def metrics(d):
    cols=st.columns(len(d))
    for c,(k,v) in zip(cols,d.items()): c.metric(k,v)

# ══ 1. PLAYER SEARCH ═══════════════════════════════════
if section=="🔍 Player Search":
    st.title("🔍 Player Profile")
    name=st.text_input("Player name (e.g. Babar, Kohli, Malinga)","")
    if not name:
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#1e2130,#2d3561);border-radius:16px;
            padding:32px;margin:16px 0;border:1px solid #3d4166;text-align:center">
  <div style="font-size:52px;margin-bottom:8px">🏏</div>
  <h2 style="color:#f0f0f0;margin:0 0 8px 0">Cricket Analytics</h2>
  <p style="color:#aaa;font-size:15px;margin:0">
    Search any player • Compare formats • ODI · Test · T20I · IPL · PSL
  </p>
  <div style="margin-top:20px;display:flex;justify-content:center;gap:12px;flex-wrap:wrap">
    <span style="background:#00b894;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px">ODI</span>
    <span style="background:#0984e3;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px">Test</span>
    <span style="background:#d63031;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px">T20I</span>
    <span style="background:#e17055;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px">IPL</span>
    <span style="background:#6c5ce7;color:#fff;padding:4px 12px;border-radius:20px;font-size:13px">PSL</span>
  </div>
  <p style="color:#888;font-size:13px;margin-top:16px">
    💡 Try: Babar, Kohli, Smith, Hazelwood, Rashid, Malinga...
  </p>
</div>""", unsafe_allow_html=True)
    if name:
        sname=resolve_name(name)
        ab=bat_fmt[bat_fmt["striker"].str.contains(sname,case=False,na=False)]["format"].unique().tolist()
        aw=bowl_fmt[bowl_fmt["bowler"].str.contains(sname,case=False,na=False)]["format"].unique().tolist()
        avl=sorted(set(ab+aw),key=lambda x:FORMATS.index(x) if x in FORMATS else 99)
        if not avl: st.error(f"No player found for '{name}'."); st.stop()

        fmt=st.radio("📋 Format",avl,horizontal=True)
        clr=FC.get(fmt,"#00b894")
        bat=bat_fmt[(bat_fmt["striker"].str.contains(sname,case=False,na=False))&(bat_fmt["format"]==fmt)]
        bowl=bowl_fmt[(bowl_fmt["bowler"].str.contains(sname,case=False,na=False))&(bowl_fmt["format"]==fmt)]

        if len(bat)>0:
            p=bat.sort_values("runs",ascending=False).iloc[0]
            st.subheader(f"🏏 {p['striker']} — Batting ({fmt})")
            metrics({"Matches":int(p["matches"]),"Runs":f"{int(p['runs']):,}","Average":p["average"]})
            metrics({"Strike Rate":p["strike_rate"],"4s":int(p["fours"]),"6s":int(p["sixes"])})
            metrics({"Dismissals":int(p["dismissals"]),"Dot Ball %":f"{p['dot_pct']}%","Boundary %":f"{p['boundary_pct']}%"})

            by=bat_yr[(bat_yr["striker"].str.contains(sname,case=False,na=False))&(bat_yr["format"]==fmt)].sort_values("year")
            if len(by)>1:
                ch(bar_v(by,"year","runs","Runs per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by,"year","average","Batting Average",clr),260)
                with c2: ch(line(by,"year","strike_rate","Strike Rate","#fdcb6e"),260)
            fr=int(p["fours"])*4; sr=int(p["sixes"])*6; or_=max(0,int(p["runs"])-fr-sr)
            ch(donut(["Fours","Sixes","Other"],[fr,sr,or_],[clr,"#d63031","#636e72"],"Scoring Breakdown"),300)

        st.divider()
        if len(bowl)>0:
            p2=bowl.sort_values("wickets",ascending=False).iloc[0]
            st.subheader(f"🎳 {p2['bowler']} — Bowling ({fmt})")
            metrics({"Matches":int(p2["matches"]),"Wickets":int(p2["wickets"]),"Economy":p2["economy"]})
            metrics({"Average":p2["average"],"Strike Rate":p2["strike_rate"],"Dot Ball %":f"{p2['dot_pct']}%"})
            by2=bowl_yr[(bowl_yr["bowler"].str.contains(sname,case=False,na=False))&(bowl_yr["format"]==fmt)].sort_values("year")
            if len(by2)>1:
                ch(bar_v(by2,"year","wickets","Wickets per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by2,"year","economy","Economy Rate","#d63031"),260)
                with c2: ch(line(by2,"year","average","Bowling Average","#6c5ce7"),260)
        if len(bat)==0 and len(bowl)==0:
            st.warning(f"No {fmt} data for '{name}'.")

# ══ 2. HEAD TO HEAD ════════════════════════════════════
elif section=="⚔️ Head to Head":
    st.title("⚔️ Head to Head")
    c1,c2=st.columns(2)
    n1=c1.text_input("Player 1","Kohli"); n2=c2.text_input("Player 2","Babar Azam")
    fmt=st.radio("Format",FORMATS,horizontal=True)
    if n1 and n2:
        b1=bat_fmt[(bat_fmt["striker"].str.contains(n1,case=False,na=False))&(bat_fmt["format"]==fmt)]
        b2=bat_fmt[(bat_fmt["striker"].str.contains(n2,case=False,na=False))&(bat_fmt["format"]==fmt)]
        if len(b1)==0 or len(b2)==0: st.error(f"One or both players have no {fmt} data.")
        else:
            p1=b1.iloc[0]; p2=b2.iloc[0]; p1n=p1["striker"]; p2n=p2["striker"]
            st.subheader(f"🏏 Batting — {fmt}")
            for title,ml in [("Volume — Runs / 4s / 6s",["runs","fours","sixes"]),
                              ("Rates — Average / Strike Rate",["average","strike_rate"]),
                              ("% Stats — Dot / Boundary",["dot_pct","boundary_pct"])]:
                fig=go.Figure([
                    go.Bar(name=p1n,x=ml,y=[float(p1.get(m,0)) for m in ml],
                           marker=dict(color=FC["ODI"],opacity=0.9,line=dict(width=0))),
                    go.Bar(name=p2n,x=ml,y=[float(p2.get(m,0)) for m in ml],
                           marker=dict(color=FC["Test"],opacity=0.9,line=dict(width=0)))])
                fig.update_layout(**BASE,barmode="group",title=title,height=280)
                st.plotly_chart(fig,**CFG)
            by1=bat_yr[(bat_yr["striker"].str.contains(n1,case=False,na=False))&(bat_yr["format"]==fmt)].copy()
            by2y=bat_yr[(bat_yr["striker"].str.contains(n2,case=False,na=False))&(bat_yr["format"]==fmt)].copy()
            if len(by1)>0 and len(by2y)>0:
                by1["player"]=p1n; by2y["player"]=p2n
                fy=px.line(pd.concat([by1,by2y]),x="year",y="runs",color="player",markers=True,
                           title=f"Runs per Year — {fmt}",
                           color_discrete_map={p1n:FC["ODI"],p2n:FC["Test"]})
                fy.update_traces(line=dict(width=2.5),marker=dict(size=7))
                fy.update_layout(**BASE,height=300); st.plotly_chart(fy,**CFG)

# ══ 3. PLAYER VS VENUE ═════════════════════════════════
elif section=="🏟️ Player vs Venue":
    st.title("🏟️ Player vs Venue")
    name=st.text_input("Player name","Kohli")
    st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        src=(bat_ven[bat_ven["striker"].str.contains(name,case=False,na=False)] if st_=="Batting"
             else bowl_ven[bowl_ven["bowler"].str.contains(name,case=False,na=False)])
        if len(src)==0: st.error("Player not found!")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            df_v=src[src["format"]==fmt]
            if st_=="Batting":
                m=st.selectbox("Metric",["runs","average","strike_rate","fours","sixes"])
                df_v=df_v.sort_values(m,ascending=False).head(15)
                ch(bar_h(df_v,m,"venue",m,"Greens",f"{df_v['striker'].iloc[0]} — {m} by Venue ({fmt})"))
                st.dataframe(df_v[["venue","innings","runs","average","strike_rate"]].reset_index(drop=True))
            else:
                m=st.selectbox("Metric",["wickets","economy","average","dot_pct"])
                df_v=df_v.sort_values(m,ascending=False).head(15)
                ch(bar_h(df_v,m,"venue",m,"Reds",f"{df_v['bowler'].iloc[0]} — {m} by Venue ({fmt})"))
                st.dataframe(df_v[["venue","innings","wickets","economy","average"]].reset_index(drop=True))

# ══ 4. PLAYER VS OPPONENT ══════════════════════════════
elif section=="🌍 Player vs Opponent":
    st.title("🌍 Player vs Opponent")
    name=st.text_input("Player name","Kohli")
    st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        src=(bat_opp[bat_opp["striker"].str.contains(name,case=False,na=False)] if st_=="Batting"
             else bowl_opp[bowl_opp["bowler"].str.contains(name,case=False,na=False)])
        if len(src)==0: st.error("Player not found!")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            df_o=src[src["format"]==fmt]
            if st_=="Batting":
                m=st.selectbox("Metric",["runs","average","strike_rate","fours","sixes"])
                df_o=df_o.sort_values(m,ascending=False)
                ch(bar_h(df_o,m,"opponent",m,"Blues",f"{df_o['striker'].iloc[0]} — {m} vs Teams ({fmt})"))
                st.dataframe(df_o[["opponent","innings","runs","average","strike_rate"]].reset_index(drop=True))
            else:
                m=st.selectbox("Metric",["wickets","economy","average","dot_pct"])
                df_o=df_o.sort_values(m,ascending=False)
                ch(bar_h(df_o,m,"opponent",m,"Purples",f"{df_o['bowler'].iloc[0]} — {m} vs Teams ({fmt})"))
                st.dataframe(df_o[["opponent","innings","wickets","economy","average"]].reset_index(drop=True))

# ══ 5. BATTER VS BOWLER ════════════════════════════════
elif section=="🤜 Batter vs Bowler":
    st.title("🤜 Batter vs Bowler")
    mt=st.radio("Look up a...",["Batter","Bowler"],horizontal=True)
    if mt=="Batter":
        name=st.text_input("Batter name","Babar Azam")
        if name:
            src=bvb[bvb["striker"].str.contains(name,case=False,na=False)]
            if len(src)==0: st.error("Not found!")
            else:
                fmt=st.radio("Format",avail(src,"format"),horizontal=True)
                df_m=src[src["format"]==fmt]
                m=st.selectbox("Sort by",["balls_faced","runs","strike_rate","dismissals"])
                df_m=df_m.sort_values(m,ascending=False).head(20)
                ch(bar_h(df_m,m,"bowler",m,"Greens",f"Top 20 bowlers faced — {m} ({fmt})"))
                st.dataframe(df_m[["bowler","balls_faced","runs","strike_rate","dismissals"]].reset_index(drop=True))
    else:
        name=st.text_input("Bowler name","Shaheen")
        if name:
            src=wvb[wvb["bowler"].str.contains(name,case=False,na=False)]
            if len(src)==0: st.error("Not found!")
            else:
                fmt=st.radio("Format",avail(src,"format"),horizontal=True)
                df_m=src[src["format"]==fmt]
                m=st.selectbox("Sort by",["wickets","economy","dot_pct","runs_given"])
                df_m=df_m.sort_values(m,ascending=(m in ["economy","dot_pct"])).head(20)
                ch(bar_h(df_m,m,"striker",m,"Reds",f"Top 20 batters bowled to — {m} ({fmt})"))
                st.dataframe(df_m[["striker","balls_bowled","runs_given","wickets","economy"]].reset_index(drop=True))

# ══ 6. PERFORMANCE OVER YEARS ══════════════════════════
elif section=="📈 Performance Over Years":
    st.title("📈 Performance Over Years")
    name=st.text_input("Player name","Kohli")
    st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        src=(bat_yr[bat_yr["striker"].str.contains(name,case=False,na=False)] if st_=="Batting"
             else bowl_yr[bowl_yr["bowler"].str.contains(name,case=False,na=False)])
        if len(src)==0: st.error("Player not found!")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            by=src[src["format"]==fmt].sort_values("year")
            clr=FC.get(fmt,"#00b894")
            if st_=="Batting":
                ch(bar_v(by,"year","runs","Runs per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by,"year","average","Batting Average",clr),260)
                with c2: ch(line(by,"year","strike_rate","Strike Rate","#fdcb6e"),260)
                st.dataframe(by[["year","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
            else:
                ch(bar_v(by,"year","wickets","Wickets per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by,"year","economy","Economy Rate","#d63031"),260)
                with c2: ch(line(by,"year","average","Bowling Average","#6c5ce7"),260)
                st.dataframe(by[["year","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ══ 7. LEADERBOARD ═════════════════════════════════════
elif section=="🏆 Leaderboard":
    st.title("🏆 Leaderboard")
    fmt=st.radio("Format",FORMATS,horizontal=True)
    tab1,tab2=st.tabs(["🏏 Batting","🎳 Bowling"])
    with tab1:
        bs=bat_fmt[bat_fmt["format"]==fmt]
        c1,c2=st.columns(2)
        sb=c1.selectbox("Rank by",["runs","average","strike_rate","sixes","fours","boundary_pct"])
        mr=c2.slider("Min runs",0,3000,200,100)
        tn=st.slider("Top N",5,30,15)
        lb=bs[bs["runs"]>=mr].sort_values(sb,ascending=False).head(tn).reset_index(drop=True)
        lb.insert(0,"Rank",range(1,len(lb)+1))
        ch(bar_h(lb,sb,"striker",sb,"Teal",f"Top {tn} {fmt} Batters — {sb}"),max(350,tn*30))
        st.dataframe(lb[["Rank","striker","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
    with tab2:
        ws=bowl_fmt[bowl_fmt["format"]==fmt]
        c1,c2=st.columns(2)
        sb2=c1.selectbox("Rank by",["wickets","economy","average","dot_pct","strike_rate"])
        mw=c2.slider("Min wickets",0,100,10,5)
        tn2=st.slider("Top N bowlers",5,30,15)
        lb2=ws[ws["wickets"]>=mw].sort_values(sb2,ascending=(sb2 in ["economy","average","strike_rate"])).head(tn2).reset_index(drop=True)
        lb2.insert(0,"Rank",range(1,len(lb2)+1))
        ch(bar_h(lb2,"wickets","bowler","economy","Sunset",f"Top {tn2} {fmt} Bowlers"),max(350,tn2*30))
        st.dataframe(lb2[["Rank","bowler","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))
