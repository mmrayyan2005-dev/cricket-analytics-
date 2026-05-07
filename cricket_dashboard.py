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
            xaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
            yaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
            dragmode=False)

# Each chart type uses its own margin via update_layout
M_DEFAULT = dict(l=8,r=8,t=48,b=8)
M_BARV    = dict(l=8,r=8,t=48,b=60)
M_BARH    = dict(l=180,r=16,t=48,b=8)

CFG = dict(
    config={
        "displayModeBar": False,   # hide toolbar (no edit/lasso buttons)
        "scrollZoom": False,        # no scroll-to-zoom
        "doubleClick": False,       # no double-click reset
        "showTips": False,
        "modeBarButtonsToRemove": [
            "zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d",
            "autoScale2d","resetScale2d","hoverClosestCartesian",
            "hoverCompareCartesian","toggleSpikelines"
        ],
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
    # 52px per row guarantees no label overlap regardless of name length
    h = max(420, len(df) * 52)
    fig=px.bar(df,x=x,y=y,orientation="h",color=col,color_continuous_scale=scale,title=title)
    fig.update_traces(marker_line_width=0, marker_line_color="rgba(0,0,0,0)")
    fig.update_layout(
        **BASE,
        height=h,
        coloraxis_showscale=False,
        margin=dict(l=210, r=50, t=48, b=8),
        bargap=0.35,        # space between bars so labels breathe
    )
    fig.update_yaxes(
        categoryorder="total ascending",
        showgrid=False,
        title="",
        tickfont=dict(size=13, color=TEXT),
        automargin=True,    # plotly auto-widens left margin if names overflow
        ticklabeloverflow="allow",
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID, title="", tickfont=dict(size=11))
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

def page_banner(emoji, title, subtitle, grad_a, grad_b, glow):
    st.markdown(f"""
<div style="background:linear-gradient(135deg,{grad_a} 0%,{grad_b} 100%);
            border-radius:16px;padding:22px 24px;margin:0 0 20px 0;
            border:1px solid {glow}44;position:relative;overflow:hidden">
  <div style="position:absolute;top:-30px;right:-30px;width:140px;height:140px;
              background:radial-gradient(circle,{glow}33 0%,transparent 70%);
              pointer-events:none"></div>
  <div style="display:flex;align-items:center;gap:14px">
    <div style="font-size:40px;filter:drop-shadow(0 0 8px {glow}88)">{emoji}</div>
    <div>
      <div style="color:#fff;font-size:20px;font-weight:800;letter-spacing:-0.3px">{title}</div>
      <div style="color:#aabbcc;font-size:13px;margin-top:3px">{subtitle}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ══ 1. PLAYER SEARCH ═══════════════════════════════════
if section=="🔍 Player Search":
    # ── Always show hero first ──────────────────────────
    st.markdown("""
<div style="background:linear-gradient(135deg,#0d1b2a 0%,#1a1f3a 50%,#0d1b2a 100%);
            border-radius:20px;padding:36px 24px 28px 24px;margin:0 0 24px 0;
            border:1px solid #2d3561;text-align:center;position:relative;overflow:hidden">

  <!-- coloured glow blobs -->
  <div style="position:absolute;top:-40px;left:-40px;width:180px;height:180px;
              background:radial-gradient(circle,#00b89455 0%,transparent 70%);pointer-events:none"></div>
  <div style="position:absolute;bottom:-40px;right:-40px;width:180px;height:180px;
              background:radial-gradient(circle,#6c5ce755 0%,transparent 70%);pointer-events:none"></div>
  <div style="position:absolute;top:30px;right:20px;width:120px;height:120px;
              background:radial-gradient(circle,#d6303133 0%,transparent 70%);pointer-events:none"></div>

  <div style="font-size:60px;line-height:1;margin-bottom:10px;filter:drop-shadow(0 0 12px #00b89466)">🏏</div>
  <h1 style="color:#ffffff;margin:0 0 6px 0;font-size:30px;font-weight:800;
             letter-spacing:-0.5px;text-shadow:0 2px 12px #0007">
    Cricket Analytics
  </h1>
  <p style="color:#8899bb;font-size:15px;margin:0 0 22px 0">
    Ball-by-ball records · Every major format
  </p>

  <!-- Format pills with glow -->
  <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-bottom:26px">
    <span style="background:linear-gradient(135deg,#00b894,#00cec9);color:#fff;
                 padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;
                 box-shadow:0 0 12px #00b89455">ODI</span>
    <span style="background:linear-gradient(135deg,#0984e3,#74b9ff);color:#fff;
                 padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;
                 box-shadow:0 0 12px #0984e355">Test</span>
    <span style="background:linear-gradient(135deg,#d63031,#ff7675);color:#fff;
                 padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;
                 box-shadow:0 0 12px #d6303155">T20I</span>
    <span style="background:linear-gradient(135deg,#e17055,#fdcb6e);color:#fff;
                 padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;
                 box-shadow:0 0 12px #e1705555">IPL</span>
    <span style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);color:#fff;
                 padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;
                 box-shadow:0 0 12px #6c5ce755">PSL</span>
  </div>

  <!-- Feature cards -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;
              max-width:500px;margin:0 auto 22px auto">
    <div style="background:linear-gradient(135deg,#1e2a3a,#1e2130);
                border-radius:14px;padding:16px 8px;border:1px solid #00b89433">
      <div style="font-size:24px;margin-bottom:6px">🏏</div>
      <div style="color:#00b894;font-weight:700;font-size:14px">Batting</div>
      <div style="color:#778;font-size:11px;margin-top:3px">Runs · Avg · SR</div>
    </div>
    <div style="background:linear-gradient(135deg,#1a2a3a,#1e2130);
                border-radius:14px;padding:16px 8px;border:1px solid #0984e333">
      <div style="font-size:24px;margin-bottom:6px">🎳</div>
      <div style="color:#0984e3;font-weight:700;font-size:14px">Bowling</div>
      <div style="color:#778;font-size:11px;margin-top:3px">Wkts · Econ · SR</div>
    </div>
    <div style="background:linear-gradient(135deg,#1e1a3a,#1e2130);
                border-radius:14px;padding:16px 8px;border:1px solid #6c5ce733">
      <div style="font-size:24px;margin-bottom:6px">⚔️</div>
      <div style="color:#a29bfe;font-weight:700;font-size:14px">Matchups</div>
      <div style="color:#778;font-size:11px;margin-top:3px">Bat vs Bowl</div>
    </div>
  </div>

  <p style="color:#556;font-size:13px;margin:0">
    Try: <span style="color:#00b894;font-weight:600">Babar</span> ·
         <span style="color:#0984e3;font-weight:600">Kohli</span> ·
         <span style="color:#d63031;font-weight:600">Smith</span> ·
         <span style="color:#e17055;font-weight:600">Bumrah</span> ·
         <span style="color:#6c5ce7;font-weight:600">Rashid</span>
  </p>
</div>""", unsafe_allow_html=True)

    name=st.text_input("🔍  Search player","",placeholder="Type a name e.g. Babar, Kohli, Smith...")
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
    page_banner("⚔️","Head to Head","Pick two players and see who dominates across formats","#1a0a2e","#2d1b4e","#6c5ce7")
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
            LABELS = {
                "runs":"Runs","fours":"Fours (4s)","sixes":"Sixes (6s)",
                "average":"Batting Avg","strike_rate":"Strike Rate",
                "dot_pct":"Dot Ball %","boundary_pct":"Boundary %"
            }
            for title,ml in [("🏏 Volume",["runs","fours","sixes"]),
                              ("📈 Rates",["average","strike_rate"]),
                              ("📊 Percentages",["dot_pct","boundary_pct"])]:
                pretty = [LABELS.get(m,m) for m in ml]
                v1 = [float(p1.get(m,0)) for m in ml]
                v2 = [float(p2.get(m,0)) for m in ml]
                fig=go.Figure()
                # horizontal grouped bars — easier to read on mobile
                fig.add_trace(go.Bar(
                    name=p1n, y=pretty, x=v1, orientation="h",
                    marker=dict(color=FC["ODI"],opacity=0.9,line=dict(width=0)),
                    text=[f"{v:.1f}" for v in v1], textposition="outside",
                    textfont=dict(size=11,color=TEXT)
                ))
                fig.add_trace(go.Bar(
                    name=p2n, y=pretty, x=v2, orientation="h",
                    marker=dict(color=FC["Test"],opacity=0.9,line=dict(width=0)),
                    text=[f"{v:.1f}" for v in v2], textposition="outside",
                    textfont=dict(size=11,color=TEXT)
                ))
                fig.update_layout(**BASE,barmode="group",title=title,
                                  height=max(180,len(ml)*90),
                                  margin=dict(l=120,r=60,t=48,b=8))
                fig.update_yaxes(showgrid=False,tickfont=dict(size=13),title="",
                                 automargin=False)
                fig.update_xaxes(showgrid=True,gridcolor=GRID,title="",fixedrange=True)
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
    page_banner("🏟️","Player vs Venue","How does a player perform at different grounds around the world?","#0a1a1a","#0d2b2b","#00b894")
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
    page_banner("🌍","Player vs Opponent","Find out which teams a player dominates — and which trouble them","#0a1020","#0d1e3a","#0984e3")
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
    page_banner("🤜","Batter vs Bowler","The ultimate matchup — who has the edge ball by ball?","#1a0a0a","#2e1010","#d63031")
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
    page_banner("📈","Performance Over Years","Track how a player has evolved season by season","#0a150a","#0d2a10","#00b894")
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
    page_banner("🏆","Leaderboard","The greatest of all time — ranked by format and stat","#1a1400","#2e2400","#fdcb6e")
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
