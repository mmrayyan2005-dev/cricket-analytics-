import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import io
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from groq import Groq

st.set_page_config(page_title="Cricket Analytics", layout="wide", page_icon="🏏",
                   initial_sidebar_state="expanded")

# ── Theme (light/dark) + men's/women's choice ─────────────────────────────────
# Both are read from session_state BEFORE their widgets are drawn (the widgets live
# in the sidebar further down) — safe because session_state persists across reruns.
IS_LIGHT = st.session_state.get("is_light_mode", False)

# v9 notebook tags every player/match/team with gender ('male'/'female'). This is the
# global switch so women never show up inside men's leaderboards (and vice versa).
GENDER_MAP = {"Men's": "male", "Women's": "female"}
GENDER_PICK = "All"
GENDER = None

def gf(df):
    """Filter a table to the chosen men's/women's pool. Tables without a gender column pass through."""
    if df is None or df.empty or "gender" not in df.columns or GENDER is None:
        return df
    return df[df["gender"] == GENDER]

RAW_BASE = "https://raw.githubusercontent.com/mmrayyan2005-dev/cricket-analytics_-/main"

if IS_LIGHT:
    BG="#f2f5fc"; CARD="#ffffff"; TEXT="#0e1730"; GRID="#e3e8f5"
    SURFACE="#ffffff"; BORDER="#e3e8f5"; MUTED="#71799c"; SUBTLE="#3d4870"
    SHADOW="0 6px 22px rgba(15,30,80,.08)"
    ACCENT="#ff5a1f"; ACCENT2="#2557e8"
else:
    BG="#0a1024"; CARD="#131b3a"; TEXT="#f3f6ff"; GRID="#28345f"
    SURFACE="#0d1430"; BORDER="#28345f"; MUTED="#8189b3"; SUBTLE="#c7cdea"
    SHADOW="0 10px 32px rgba(0,6,30,.5)"
    ACCENT="#ff6a2e"; ACCENT2="#3d7bff"

# Pipeline-aligned format scope: exactly the 8 competitions loaded by pipeline.py
FC={"ODI":"#3f7a52","Test":"#8a95a8","T20I":"#ff6a2e",
    "IPL":"#3d7bff","PSL":"#2f8f5b","WPL":"#b2557a","BBL":"#d9772b","CPL":"#2f9aa0",
}
FORMATS=["ODI","Test","T20I","IPL","PSL","WPL","BBL","CPL"]
FORMAT_META={
    "ODI":("🌐","#3f7a52","#529a68"),"Test":("🏛️","#8a95a8","#a8b2c2"),
    "T20I":("⚡","#ff6a2e","#ff8c5c"),"IPL":("🏏","#3d7bff","#6d9bff"),
    "PSL":("🟢","#2f8f5b","#3fae72"),"WPL":("🌹","#b2557a","#c97694"),
    "BBL":("🔥","#d9772b","#e8974f"),"CPL":("🌊","#2f9aa0","#45bcc2"),
}
INTERNATIONAL_FORMATS = {"ODI","Test","T20I"}
FRANCHISE_FORMATS = {"IPL","PSL","BBL","CPL","WPL"}

def order_fmts(lst):
    return sorted(lst, key=lambda x: FORMATS.index(x) if x in FORMATS else 99)

BASE=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT,family="Inter,sans-serif",size=12),
          legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1,
                      bgcolor="rgba(0,0,0,0)",font=dict(size=11)),
          xaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
          yaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
          dragmode=False,
          hoverlabel=dict(bgcolor=CARD,bordercolor=ACCENT,font=dict(color=TEXT,size=12,family="Inter,sans-serif")),
          hovermode="closest")
M_DEFAULT=dict(l=8,r=8,t=48,b=8)
M_BARV=dict(l=8,r=8,t=48,b=60)
CFG=dict(config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False,"responsive":True},use_container_width=True)

# ── UI + comprehensive CSS ────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
:root{
  --bg:#0a1024;--surface:#0d1430;--card:#131b3a;--border:#28345f;
  --accent:#ff6a2e;--accent2:#3d7bff;--warn:#ff6a2e;--gold:#ff6a2e;
  --accent-rgb:255,106,46;--accent2-rgb:61,123,255;
  --text:#f3f6ff;--muted:#8189b3;--subtle:#c7cdea;
  --radius:18px;--radius-sm:12px;--radius-pill:999px;
  --font-head:'Poppins',sans-serif;--font-body:'Inter',sans-serif;--font-data:'JetBrains Mono',monospace;
  --shadow:0 10px 32px rgba(0,6,30,.5);
}
html,body,[class*="css"]{font-family:var(--font-body);background:var(--bg);color:var(--text)}
.stApp{
  background-color:var(--bg);
  background-image:
    radial-gradient(ellipse 900px 460px at 50% -8%, rgba(var(--accent2-rgb),.14) 0%, transparent 62%),
    radial-gradient(ellipse 700px 400px at 100% 0%, rgba(var(--accent-rgb),.08) 0%, transparent 60%),
    linear-gradient(180deg, rgba(255,255,255,.02) 0%, transparent 8%);
  background-attachment:fixed;
}
.block-container{padding:0 !important;max-width:100% !important}
h1,h2,h3,h4,.ca-section-title,.ca-feature-title,.ca-player-name{font-family:var(--font-head)!important;letter-spacing:.2px}

/* Sidebar navigation */
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebar"]>div{padding-top:8px!important}
[data-testid="stSidebarContent"]{padding:4px 14px 30px!important}
[data-testid="stSidebarNav"]{display:none!important}
.ca-brand{display:flex;align-items:center;gap:10px;padding:6px 4px 14px;margin-bottom:6px;border-bottom:1px solid var(--border)}
.ca-brand-mark{font-size:26px;line-height:1}
.ca-brand-text{font-family:'Poppins',sans-serif;font-size:17px;font-weight:800;letter-spacing:-.2px;color:var(--text)}
.ca-brand-text span{background:linear-gradient(120deg,var(--accent2),var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.ca-brand-status{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:600;color:var(--accent);font-family:var(--font-data);margin:0 0 14px 2px}
.ca-nav-group{font-size:10px;font-weight:800;letter-spacing:1.3px;text-transform:uppercase;color:var(--muted);margin:16px 4px 6px;display:flex;align-items:center;gap:6px}
[data-testid="stSidebar"] [data-testid="stButton"] button{width:100%!important;text-align:left!important;justify-content:flex-start!important;
  background:transparent!important;border:1px solid transparent!important;border-radius:10px!important;color:var(--subtle)!important;
  font-weight:600!important;font-size:13px!important;padding:9px 12px!important;margin-bottom:3px!important;box-shadow:none!important;
  transition:all .15s!important}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{background:rgba(var(--accent2-rgb),.10)!important;color:var(--text)!important;
  border-color:rgba(var(--accent2-rgb),.25)!important;transform:none!important}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;
  color:#fff!important;font-weight:700!important;box-shadow:0 4px 14px rgba(var(--accent-rgb),.28)!important;border:none!important}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover{transform:none!important}
.ca-sidebar-utility [data-testid="stButton"] button{background:var(--card)!important;border:1px solid var(--border)!important;
  border-radius:var(--radius-pill)!important;font-size:11.5px!important;padding:6px 10px!important;text-align:center!important;
  justify-content:center!important}
.ca-sidebar-utility [data-testid="stButton"] button:hover{border-color:var(--accent)!important;color:var(--accent)!important}

/* Floating chat launcher */
.st-key-ca_chat_corner{position:fixed;top:58px;right:24px;z-index:999999;width:auto}
.st-key-ca_chat_corner [data-testid="stPopover"]{width:auto!important}
.st-key-ca_chat_corner [data-testid="stPopover"]>button,
.st-key-ca_chat_corner [data-testid="stPopoverButton"]{
  background:linear-gradient(120deg,var(--accent2),var(--accent))!important;color:#fff!important;
  border:none!important;border-radius:var(--radius-pill)!important;font-weight:700!important;
  font-size:12.5px!important;padding:8px 18px!important;box-shadow:0 6px 18px rgba(var(--accent-rgb),.35)!important;
  white-space:nowrap!important}
@media (max-width:640px){
  .st-key-ca_chat_corner{top:50px;right:10px}
  .st-key-ca_chat_corner [data-testid="stPopover"]>button,
  .st-key-ca_chat_corner [data-testid="stPopoverButton"]{padding:6px 12px!important;font-size:11px!important}
}

/* Metrics */
[data-testid="stMetric"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius)!important;padding:16px 18px!important;position:relative;overflow:hidden;transition:border-color .25s,transform .2s;box-shadow:var(--shadow)}
[data-testid="stMetric"]:hover{border-color:var(--accent)!important;transform:translateY(-3px)}
[data-testid="stMetric"]::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;border-radius:var(--radius) var(--radius) 0 0;background:linear-gradient(90deg,var(--accent2),var(--accent))}
[data-testid="stMetricLabel"]{font-family:var(--font-body)!important;font-size:10px!important;font-weight:700!important;color:var(--muted)!important;text-transform:uppercase;letter-spacing:1.2px!important}
[data-testid="stMetricValue"]{font-family:var(--font-data)!important;font-size:23px!important;font-weight:700!important;color:var(--text)!important;line-height:1.2!important;letter-spacing:-0.3px!important}
[data-testid="stMetricDelta"]{font-size:11px!important}

/* Tabs */
div[data-baseweb="tab-list"]{gap:6px!important;flex-wrap:wrap!important;background:transparent!important;border-bottom:1px solid var(--border)!important;padding-bottom:8px!important}
div[data-baseweb="tab"]{border-radius:var(--radius-pill)!important;padding:8px 18px!important;background:var(--card)!important;font-weight:700!important;font-size:12px!important;color:var(--subtle)!important;border:1px solid var(--border)!important;transition:all .2s!important;font-family:var(--font-body)!important}
div[data-baseweb="tab"]:hover{border-color:var(--accent)!important;color:var(--text)!important}
div[data-baseweb="tab"][aria-selected="true"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;border-color:transparent!important;color:#fff!important;box-shadow:0 4px 14px rgba(var(--accent-rgb),.35)!important}
div[data-baseweb="tab-highlight"],div[data-baseweb="tab-border"]{display:none!important}

/* Inputs */
[data-testid="stTextInput"] input{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-pill)!important;color:var(--text)!important;font-family:var(--font-body)!important;font-size:14px!important;padding:12px 18px!important;transition:border-color .2s,box-shadow .2s!important}
[data-testid="stTextInput"] input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(var(--accent-rgb),.18)!important;outline:none!important}
[data-testid="stTextInput"] input::placeholder{color:var(--muted)!important}
[data-testid="stSelectbox"]>div>div{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important;transition:border-color .2s!important}
[data-testid="stSelectbox"]>div>div:hover{border-color:var(--accent)!important}
[data-testid="stRadio"]>div{flex-wrap:wrap!important;gap:8px!important}
[data-testid="stRadio"] label{display:flex!important;align-items:center!important;background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-pill)!important;padding:8px 16px!important;font-size:12.5px!important;font-weight:700!important;color:var(--subtle)!important;cursor:pointer;transition:all .15s!important;font-family:var(--font-body)!important}
[data-testid="stRadio"] label>div:first-child{display:none!important}
[data-testid="stRadio"] label>div{margin:0!important}
[data-testid="stRadio"] label:hover{border-color:var(--accent)!important;color:var(--text)!important;transform:translateY(-1px)}
[data-testid="stRadio"] label:has(input:checked){border-color:transparent!important;color:#fff!important;background:linear-gradient(120deg,var(--accent2),var(--accent))!important;box-shadow:0 4px 14px rgba(var(--accent-rgb),.3)!important}

/* Sliders */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"]{background:var(--accent)!important;border-color:var(--accent)!important;box-shadow:0 0 0 4px rgba(var(--accent-rgb),.2)!important}
[data-testid="stSlider"] [data-baseweb="slider"] div[class*="Track"]{background:var(--border)!important}

/* DataFrames */
.stDataFrame{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important;box-shadow:var(--shadow)}
.stDataFrame thead th{font-size:10px!important;font-weight:700!important;text-transform:uppercase;letter-spacing:.8px;background:var(--surface)!important;color:var(--muted)!important;padding:10px 14px!important;border-bottom:1px solid var(--border)!important}
.stDataFrame tbody td{font-family:var(--font-data)!important;font-size:12px!important;padding:9px 14px!important;border-bottom:1px solid var(--border)!important}
.stDataFrame tbody tr:hover td{background:rgba(var(--accent2-rgb),.06)!important}
.stDataFrame tbody tr:first-child td{color:var(--gold)!important;font-weight:600!important}

[data-testid="stSpinner"]>div{border-color:var(--accent) transparent transparent transparent!important}
[data-testid="stCaptionContainer"]{color:var(--muted)!important;font-size:11px!important;line-height:1.6!important;padding:2px 0 8px!important}

h1,h2,h3,h4{font-family:var(--font-head)!important;letter-spacing:-0.3px!important;color:var(--text)!important}
h4{font-size:14px!important;font-weight:700!important;margin:18px 0 8px!important;color:var(--subtle)!important;text-transform:uppercase;letter-spacing:.8px!important}

hr{border:none!important;border-top:1px solid var(--border)!important;margin:20px 0!important}
.ca-divider{display:flex;align-items:center;gap:12px;margin:20px 0 16px}
.ca-divider-line{flex:1;height:1px;background:var(--border)}
.ca-divider-label{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;white-space:nowrap}

[data-testid="stButton"] button[kind="secondary"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-pill)!important;color:var(--subtle)!important;font-size:12px!important;font-weight:600!important;padding:6px 16px!important;transition:all .15s!important;margin-bottom:14px!important}
[data-testid="stButton"] button[kind="secondary"]:hover{border-color:var(--accent)!important;color:var(--accent)!important;background:rgba(var(--accent-rgb),.08)!important}

[data-testid="stButton"] button[kind="primary"],
button[kind="primary"],
.stButton>button[kind="primary"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;border:none!important;border-radius:var(--radius-pill)!important;color:#fff!important;font-weight:700!important;font-size:13px!important;padding:8px 20px!important;box-shadow:0 4px 14px rgba(var(--accent-rgb),.3)!important;transition:transform .15s,box-shadow .15s!important}
[data-testid="stButton"] button[kind="primary"]:hover,
button[kind="primary"]:hover,
.stButton>button[kind="primary"]:hover{transform:translateY(-2px)!important;box-shadow:0 8px 22px rgba(var(--accent-rgb),.4)!important}

/* Expanders (three Streamlit DOM generations covered on purpose) */
[data-testid="stExpander"],
div.streamlit-expander{border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;background:var(--card)!important;overflow:hidden!important;margin:8px 0!important}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader{font-family:var(--font-body)!important;font-size:12.5px!important;font-weight:700!important;color:var(--subtle)!important;padding:10px 14px!important;background:var(--card)!important;transition:color .15s!important}
[data-testid="stExpander"] summary:hover,
.streamlit-expanderHeader:hover{color:var(--accent)!important}
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
.streamlit-expanderContent{border-top:1px solid var(--border)!important;padding:12px 14px!important;background:var(--card)!important}
details{border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--card);overflow:hidden;margin:8px 0}
details summary{padding:10px 14px;color:var(--subtle);cursor:pointer}

[data-testid="stCheckbox"] label{font-family:var(--font-body)!important;font-size:13px!important;color:var(--subtle)!important}

@keyframes bannerFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
.ca-banner-icon{animation:bannerFloat 3.5s ease-in-out infinite}

::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:8px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}

.element-container:has([data-testid="stMetric"]){margin-bottom:10px!important}
.ca-section-card + .ca-section-card{margin-top:4px}

@keyframes driftGlow{
  0%{transform:translate(0,0) scale(1)}
  50%{transform:translate(-2%,3%) scale(1.08)}
  100%{transform:translate(0,0) scale(1)}
}
.stApp::before{
  content:'';position:fixed;top:-20%;right:-10%;width:60vw;height:60vw;max-width:800px;max-height:800px;
  background:radial-gradient(circle,rgba(var(--accent2-rgb),.10) 0%,transparent 70%);
  animation:driftGlow 22s ease-in-out infinite;pointer-events:none;z-index:0;
}

[data-testid="stAlert"]{border-radius:var(--radius-sm)!important;border-left:3px solid!important;font-size:13px!important;padding:10px 14px!important}
[data-testid="stAlert"][data-type="error"]{background:rgba(255,77,109,.06)!important;border-color:var(--warn)!important}
[data-testid="stAlert"][data-type="info"]{background:rgba(var(--accent2-rgb),.08)!important;border-color:var(--accent2)!important}
[data-testid="stAlert"][data-type="warning"]{background:rgba(var(--accent-rgb),.08)!important;border-color:var(--gold)!important}
[data-testid="stAlert"][data-type="success"]{background:rgba(var(--accent-rgb),.08)!important;border-color:var(--accent)!important}

.js-plotly-plot{touch-action:pan-y!important}
[data-testid="stPlotlyChart"]{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important;background:var(--card)!important;box-shadow:var(--shadow)}

div[data-testid="stHorizontalBlock"]>div[data-testid="column"]{min-width:0!important;flex:1 1 auto}

@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes shimmer{0%{background-position:-200% center}100%{background-position:200% center}}
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.75)}}
.ca-fade{animation:fadeUp .4s ease both}
.ca-shimmer{background:linear-gradient(90deg,var(--accent) 0%,var(--accent2) 40%,var(--accent) 80%);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 3s linear infinite}
.ca-live{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);animation:pulse-dot 1.8s ease infinite;vertical-align:middle;margin-right:4px}

.ca-content{padding:20px 24px 60px}

.ca-section-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.ca-section-card::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,var(--accent2),var(--accent))}

.ca-pill{background:rgba(var(--accent2-rgb),.08);border:1px solid rgba(var(--accent2-rgb),.25);padding:3px 10px;border-radius:var(--radius-pill);font-size:10px;font-weight:700;white-space:nowrap;display:inline-block;margin:2px 2px 2px 0;transition:border-color .15s;font-family:var(--font-data)}
.ca-pill:hover{border-color:var(--accent)}

.ca-insight{background:rgba(var(--accent-rgb),.07);border:1px solid rgba(var(--accent-rgb),.2);border-radius:var(--radius-sm);padding:12px 16px;margin:8px 0 14px;font-size:12px;color:var(--subtle);line-height:1.6;font-family:var(--font-body)}
.ca-insight strong{color:var(--accent)}

@media(max-width:640px){
  .ca-content{padding:12px 14px 40px}
  [data-testid="stMetricValue"]{font-size:18px!important}
  [data-testid="stMetricLabel"]{font-size:9px!important}
  [data-testid="stMetric"]{padding:10px 12px!important}
  [data-testid="stHorizontalBlock"]{flex-direction:column!important;gap:8px!important}
  [data-testid="stHorizontalBlock"]>div[data-testid="column"]{width:100%!important;min-width:100%!important;flex:1 1 100%!important}
  div[data-baseweb="tab"]{padding:5px 8px!important;font-size:10px!important}
  .stPlotlyChart{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important}
  .stDataFrame{overflow-x:auto!important}
  [data-testid="stRadio"] label{font-size:11px!important;padding:4px 8px!important}
  [data-testid="stPlotlyChart"]{border-radius:var(--radius-sm)!important}
}
@media(min-width:641px) and (max-width:900px){
  .ca-content{padding:16px 18px 40px}
  [data-testid="stMetricValue"]{font-size:20px!important}
  div[data-baseweb="tab"]{font-size:12px!important;padding:6px 12px!important}
}
</style>""", unsafe_allow_html=True)

if IS_LIGHT:
    st.markdown(f"""<style>
:root{{
  --bg:{BG};--surface:{SURFACE};--card:{CARD};--border:{BORDER};
  --text:{TEXT};--muted:{MUTED};--subtle:{SUBTLE};
  --shadow:{SHADOW};--accent:{ACCENT};--accent2:{ACCENT2};--warn:{ACCENT};--gold:{ACCENT2};
  --accent-rgb:255,90,31;--accent2-rgb:37,87,232;
}}
[data-testid="stMetricValue"]{{color:{TEXT}!important}}
.stDataFrame tbody tr:hover td{{background:rgba(37,87,232,.05)!important}}
[data-testid="stRadio"] label{{color:{SUBTLE}!important}}
</style>""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
# All 18 core CSVs are fetched concurrently (network is thread-safe) and parsed
# sequentially afterwards (pandas' parser is not reliably thread-safe).
CSV_FILES = [
    "cricket_batting_stats.csv","cricket_bowling_stats.csv",
    "cricket_batting_by_format.csv","cricket_bowling_by_format.csv",
    "cricket_batting_yearly.csv","cricket_bowling_yearly.csv",
    "cricket_batting_venue.csv","cricket_batting_opponent.csv",
    "cricket_bowling_venue.csv","cricket_bowling_opponent.csv",
    "cricket_batter_vs_bowler.csv","cricket_bowler_vs_batter.csv",
    "cricket_bat_form_ratings.csv","cricket_bowl_form_ratings.csv",
    "cricket_bat_similarity.csv","cricket_bowl_similarity.csv",
    "cricket_bat_innings.csv","cricket_bowl_innings.csv",
]

def _fetch_one(name):
    try:
        r = requests.get(f"{RAW_BASE}/{name}", timeout=20)
        r.raise_for_status()
        return (name, r.content, None)
    except Exception as e:
        return (name, None, str(e))

@st.cache_data(ttl=3600, show_spinner=False)
def load():
    fetched, errors = {}, []
    with ThreadPoolExecutor(max_workers=len(CSV_FILES)) as ex:
        for name, content, err in ex.map(_fetch_one, CSV_FILES):
            fetched[name] = content
            if err:
                errors.append((name, err))
    results = {}
    for name in CSV_FILES:
        content = fetched.get(name)
        if content is None:
            results[name] = pd.DataFrame()
            continue
        try:
            df = pd.read_csv(io.BytesIO(content))
            # v9 innings tables are keyed on (match, innings, player), so a legitimate row is never
            # byte-identical to another — exact duplicates can only be a re-appended match.
            before = len(df)
            df = df.drop_duplicates()
            if len(df) < before:
                errors.append((name, f"dropped {before - len(df)} exact-duplicate row(s)"))
            results[name] = df
        except Exception as e:
            results[name] = pd.DataFrame()
            errors.append((name, str(e)))
    return (*[results[n] for n in CSV_FILES], errors)

@st.cache_data(ttl=300, show_spinner=False)
def load_live_matches():
    try:
        return pd.read_csv(f"{RAW_BASE}/cricket_live_matches.csv")
    except Exception:
        return pd.DataFrame()

# ── Optional legacy prediction files (not produced by the current pipeline) ──
# Each returns an empty DataFrame on any failure so a missing push never crashes the app.
def _try_load(filename):
    try:
        return pd.read_csv(f"{RAW_BASE}/{filename}")
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_match_results():      return _try_load("cricket_matches_info.csv")     # Step 17: matches + Elo/form/H2H features + gender
@st.cache_data(ttl=3600, show_spinner=False)
def load_team_ratings():       return _try_load("cricket_team_ratings.csv")     # Step 17: team, format, gender, elo, form, matches_played
@st.cache_data(ttl=3600, show_spinner=False)
def load_player_forecast():    return _try_load("cricket_player_forecast.csv")  # Step 16: real next-season projections
@st.cache_data(ttl=3600, show_spinner=False)
def load_run_forecast():       return _try_load("cricket_run_forecast.csv")     # Step 17: held-out season, predicted vs actual + SHAP
@st.cache_data(ttl=3600, show_spinner=False)
def load_bowler_workload():    return _try_load("cricket_bowler_workload.csv")  # Step 16: ACWR per bowler/format/match
@st.cache_data(ttl=3600, show_spinner=False)
def load_win_prob_test():      return _try_load("cricket_win_prob_test.csv")    # Step 17: test-set predictions
@st.cache_data(ttl=3600, show_spinner=False)
def load_model_metrics():      return _try_load("cricket_model_metrics.csv")    # Step 17: model, metric, value
@st.cache_data(ttl=3600, show_spinner=False)
def load_integrity_report():   return _try_load("cricket_data_integrity_report.csv")  # Step 16: check, count
@st.cache_data(ttl=3600, show_spinner=False)
def load_coverage_gaps():      return _try_load("cricket_coverage_gaps.csv")
@st.cache_data(ttl=3600, show_spinner=False)
def load_search_aliases():     return _try_load("search_aliases.csv")

@st.cache_resource(show_spinner=False, ttl=3600)
def load_wp_model():
    """The trained win-probability model the notebook pickles in Step 17. Needs scikit-learn
    installed (same major version as the notebook). Returns None if anything goes wrong, and the
    Win Probability page then falls back to a plain Elo estimate. Only ever loads from your own repo."""
    try:
        import pickle
        r = requests.get(f"{RAW_BASE}/win_probability_model.pkl", timeout=30)
        r.raise_for_status()
        return pickle.loads(r.content)
    except Exception:
        return None

RECOGNIZED_TEAMS = {
    "Afghanistan","Australia","Bangladesh","England","India","Ireland","New Zealand",
    "Pakistan","South Africa","Sri Lanka","West Indies","Zimbabwe",
    "Scotland","Netherlands","Nepal","UAE","United Arab Emirates","Namibia","Oman",
    "USA","United States of America","Canada","Papua New Guinea","Kenya","Uganda",
    "Hong Kong","Singapore","Malaysia","Bermuda","Jersey","Guernsey",
}
def is_real_country(name):
    return name in RECOGNIZED_TEAMS

def _extract_birth_year(born_str):
    if not born_str:
        return None
    matches = re.findall(r"(1[89]\d{2}|20\d{2})", born_str)
    return int(matches[-1]) if matches else None

def check_name_collision(wiki_card, fmt, year_series):
    """If the matched Wikipedia bio's birth year makes the player's match years physically
    impossible (age <14 or >50), the stats probably belong to a different person with the same name."""
    if not wiki_card or not wiki_card.get("born") or year_series is None or year_series.empty:
        return False, None
    byear = _extract_birth_year(wiki_card["born"])
    if not byear:
        return False, None
    first_year, last_year = int(year_series.min()), int(year_series.max())
    age_first, age_last = first_year - byear, last_year - byear
    if age_last > 50 or age_first < 14:
        note = (f"⚠️ **Possible name collision, not a display bug:** the photo/bio above is for someone born "
               f"{byear} ({wiki_card.get('title','this name')}), but the {fmt} match data below runs from "
               f"{first_year} to {last_year} (age {age_first}–{age_last}) — not plausible for one career. "
               f"Cricsheet stores names as plain text, so two people with the same name can be merged.")
        return True, note
    return False, None

@st.cache_data(ttl=3600, show_spinner=False)
def get_last_updated():
    try:
        r=requests.get(f"{RAW_BASE}/last_updated.txt",timeout=5)
        if r.status_code==200: return r.text.strip()
    except: pass
    return None

with st.spinner("Loading cricket data..."):
    (batting,bowling,bat_fmt,bowl_fmt,bat_yr,bowl_yr,bat_ven,bat_opp,
     bowl_ven,bowl_opp,bvb,wvb,bat_form,bowl_form,bat_sim,bowl_sim,bat_inn,bowl_inn,
     load_errors) = load()

if load_errors:
    with st.expander(f"⚠️ {len(load_errors)} data file(s) failed to load — click for details", expanded=False):
        for name, err in load_errors:
            st.caption(f"**{name}**: {err}")

def get_all_formats(df,col="format"):
    if df.empty or col not in df.columns: return ["ODI","Test","T20I","IPL","PSL"]
    return order_fmts(df[col].dropna().unique().tolist())

ALL_FMT = get_all_formats(bat_fmt)
# The uploaded pipeline loads exactly these eight formats; keep the UI driven by the data actually published.
_bf_g = gf(bat_fmt)
# Formats that actually have data for the chosen men's/women's pool (e.g. WPL only exists for women)
ALL_FMT_G = get_all_formats(_bf_g) if (_bf_g is not None and not _bf_g.empty) else ALL_FMT
LEAGUE_FMTS = [f for f in ["IPL","PSL","BBL","CPL","WPL"] if f in ALL_FMT_G]

def avail(df,col):
    return order_fmts(df[col].dropna().unique().tolist())

# ── Player name autocomplete ──────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_names():
    names = set()
    for d, c in ((batting,"striker"),(bowling,"bowler"),(bat_fmt,"striker"),(bowl_fmt,"bowler")):
        if not d.empty and c in d.columns:
            names.update(d[c].dropna().unique().tolist())
    return sorted(names)

ALL_PLAYER_NAMES = get_all_player_names()

def player_input(label, default, key=None):
    options = ALL_PLAYER_NAMES if ALL_PLAYER_NAMES else [default]
    try: idx = options.index(default)
    except ValueError: idx = 0
    return st.selectbox(label, options, index=idx, key=key,
                        help="Start typing to search — matches filter as you type.")

# ── find_rows: smart name matching ────────────────────────────────────────────
def find_rows(df, name_col, query):
    import re as _re
    if df.empty: return pd.DataFrame()
    q = query.strip()
    if not q: return pd.DataFrame()
    parts = q.split()

    # Raw Cricsheet only has "V Kohli", never "Virat Kohli" — search_aliases.csv maps full names to short ones.
    aliases = load_search_aliases()
    if not aliases.empty and "full_name" in aliases.columns:
        alias_hit = aliases[aliases["full_name"].str.contains(r"(?i)^" + _re.escape(q), na=False, regex=True)]
        if not alias_hit.empty:
            mask = df[name_col].isin(alias_hit["cricsheet_name"].unique())
            if mask.any(): return df[mask]

    mask = df[name_col].str.match(r"(?i)^"+_re.escape(q)+r"$", na=False)
    if mask.any(): return df[mask]
    mask = df[name_col].str.contains(rf"(?i)\b{_re.escape(q)}", na=False, regex=True)
    if mask.any(): return df[mask]
    if len(parts) >= 2:
        initial = parts[0][0].upper(); last = _re.escape(parts[-1])
        mask = df[name_col].str.match(rf"(?i)^{initial}.*{last}$", na=False)
        if mask.any(): return df[mask]
    if len(parts) == 1 and len(q) >= 3:
        mask = df[name_col].str.contains(rf"(?i)\b{_re.escape(q)}$", na=False, regex=True)
        if mask.any(): return df[mask]
        mask = df[name_col].str.contains(rf"(?i)^{_re.escape(q)}\b", na=False, regex=True)
        if mask.any(): return df[mask]
    return pd.DataFrame()

# ── Chart helpers ─────────────────────────────────────────────────────────────
def ch(fig, h=380, margin=None):
    fig.update_layout(**BASE, height=h, margin=margin or M_DEFAULT)
    st.plotly_chart(fig, **CFG)

def bar_h(df, x, y, col, scale, title, min_h=400):
    if df.empty: return go.Figure()
    n = len(df); h = max(min_h, n*52+80)
    xmax = float(df[x].max())*1.22
    fig = px.bar(df,x=x,y=y,orientation="h",color=col,color_continuous_scale=scale,title=title)
    fig.update_traces(marker_line_width=0,text=df[x].round(1).astype(str),
                      textposition="outside",textfont=dict(size=11,color=TEXT),cliponaxis=False,
                      hovertemplate="<b>%{y}</b><br>" + x + ": <b>%{x:.1f}</b><extra></extra>")
    fig.update_layout(**BASE,height=h,coloraxis_showscale=False,
                      margin=dict(l=20,r=90,t=48,b=8),bargap=0.28)
    fig.update_yaxes(categoryorder="total ascending",showgrid=False,title="",
                     tickfont=dict(size=12,color=TEXT),automargin=True,tickmode="linear")
    fig.update_xaxes(showgrid=True,gridcolor=GRID,title="",tickfont=dict(size=11),range=[0,xmax])
    return fig

def bar_v(df, x, y, title, color, h=360):
    if df.empty: return go.Figure()
    fig = px.bar(df,x=x,y=y,text=y,title=title,color_discrete_sequence=[color])
    fig.update_traces(textposition="outside",textfont=dict(size=12,color=TEXT),marker_line_width=0,
                      hovertemplate="<b>%{x}</b><br>" + y + ": <b>%{y}</b><extra></extra>")
    fig.update_layout(**BASE,height=h,showlegend=False,margin=M_BARV)
    fig.update_xaxes(tickmode="linear",tickangle=-40,showgrid=False,tickfont=dict(size=12),automargin=True)
    fig.update_yaxes(showgrid=True,gridcolor=GRID)
    if x == "year": fig.update_xaxes(dtick=1, tickformat="d")
    return fig

def line(df, x, y, title, color, h=280):
    if df.empty: return go.Figure()
    fig = px.line(df,x=x,y=y,markers=True,title=title)
    fig.update_traces(line=dict(color=color,width=3),
                      marker=dict(size=8,color=color,line=dict(width=2,color=BG)),
                      hovertemplate="<b>%{x}</b><br>" + y + ": <b>%{y:.2f}</b><extra></extra>")
    fig.update_layout(**BASE,height=h,margin=M_DEFAULT)
    if x == "year": fig.update_xaxes(dtick=1, tickformat="d")
    return fig

def donut(labels, values, colors, title):
    fig = go.Figure(go.Pie(labels=labels,values=values,hole=0.55,
        marker=dict(colors=colors,line=dict(color=BG,width=3)),
        textinfo="percent+label",textfont=dict(size=13,color=TEXT),
        hovertemplate="<b>%{label}</b><br>Runs: <b>%{value}</b><br>Share: <b>%{percent}</b><extra></extra>"))
    fig.update_layout(**BASE,height=320,title=title,showlegend=False,margin=M_DEFAULT)
    return fig

# ── Plain-language glossary ───────────────────────────────────────────────────
GLOSSARY = {
    "strike rate": "Runs scored per 100 balls faced. Higher = scores faster.",
    "average": "Runs scored per time a batter got out. Higher = more consistent.",
    "economy": "Runs a bowler concedes per over. Lower = more economical/stingy.",
    "dot ball": "A ball with no runs scored off it. Higher % = more pressure on the batter.",
    "boundary": "Runs from fours and sixes only. Higher % = more attacking innings.",
    "runs": "Total runs scored.",
    "wickets": "Total batters a bowler has dismissed (run-outs don't count for the bowler).",
    "matches": "Total matches played.",
    "innings": "Total individual batting/bowling turns played.",
    "50s": "Number of half-centuries (scores of 50–99).",
    "100s": "Number of centuries (scores of 100+).",
    "highest": "The single best score/figures recorded in one innings.",
    "balls faced": "Number of balls a batter faced at the crease.",
    "balls bowled": "Number of balls a bowler has delivered.",
    "overs": "One over = 6 balls bowled.",
    "not out": "Times a batter was still batting when the innings ended (not dismissed).",
    "catches": "Number of catches taken in the field.",
    "form rating": "Recent form vs career: 100 = playing exactly at career level, above 115 = On Fire, below 75 = Poor.",
    "form score": "Recent form vs career: 100 = playing exactly at career level, above 115 = On Fire, below 75 = Poor.",
    "consistency": "How steady a player's scores are match to match — higher means fewer big dips.",
    "player score": "0–100 percentile blend of a player's stats, ranked inside the same format and men's/women's pool. 50 = typical qualified player, 90+ = elite.",
    "similarity": "How closely two players' statistical profiles match, from 0% to 100%.",
    "win probability": "A model-estimated probability for the supplied match inputs. It is not a guarantee and depends on the model training data and supplied context.",
    "elo": "A historical team-strength rating used as one model input; it is not a forecast by itself.",
    "acwr": "An ACWR-style workload reference ratio. It is a workload monitor, not an injury diagnosis.",
    "clutch": "Performance specifically in tight, high-pressure situations.",
    "peak": "The best stretch of form in a player's career so far.",
}

def glossary_help(label):
    low = label.lower()
    for term, definition in GLOSSARY.items():
        if term in low: return definition
    return None

def metrics(d):
    items=list(d.items()); chunk=3
    for i in range(0,len(items),chunk):
        cols=st.columns(len(items[i:i+chunk]))
        for c,(k,v) in zip(cols,items[i:i+chunk]): c.metric(k,v,help=glossary_help(k))

def _hex_to_rgba(hex_color, alpha=0.18):
    h = hex_color.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    try:
        r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"
    except:
        return f"rgba(100,100,100,{alpha})"

def radar(categories, values1, values2, name1, name2, color1, color2, title):
    cats = categories + [categories[0]]
    v1 = values1 + [values1[0]]; v2 = values2 + [values2[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill="toself", name=name1,
        line=dict(color=color1, width=2.5), fillcolor=_hex_to_rgba(color1, 0.18),
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}<extra>" + name1 + "</extra>"))
    fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill="toself", name=name2,
        line=dict(color=color2, width=2.5), fillcolor=_hex_to_rgba(color2, 0.18),
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}<extra>" + name2 + "</extra>"))
    fig.update_layout(**BASE, title=title, height=440,
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor=GRID, color=TEXT, tickfont=dict(size=9), range=[0,110]),
            angularaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(size=12, color=TEXT))),
        margin=dict(l=50,r=50,t=60,b=50))
    return fig

def form_delta_html(recent_val, career_val, label, higher_is_better=True):
    if not recent_val or not career_val: return ""
    diff = recent_val - career_val
    pct = (diff / career_val * 100) if career_val else 0
    good = (diff > 0) == higher_is_better
    color = "#3a7a54" if good else "#3d7bff"
    arrow = "▲" if diff > 0 else "▼"
    return (f'<span style="background:{color}18;border:1px solid {color}44;'
            f'color:{color};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">'
            f'{arrow} {abs(pct):.1f}% vs career {label}</span>')

def form_label_text(frm_df, name_col, player, fmt):
    """One-line current-form caption from the v9 form-rating files (None if no row)."""
    if frm_df is None or frm_df.empty or name_col not in frm_df.columns: return None
    r = frm_df[(frm_df[name_col]==player)&(frm_df["format"]==fmt)]
    if r.empty: return None
    r = r.iloc[0]
    if pd.isna(r.get("form_score")):
        return f"📊 Current form: **{r['form_label']}** — too little recent data to rate fairly."
    return f"📊 Current form: **{r['form_label']}** ({r['form_score']:.0f}/100 — 100 means playing exactly at career level)."

def page_banner(emoji, title, subtitle, ga, gb, glow):
    st.markdown(f"""<div class="ca-fade" style="
      background:linear-gradient(120deg,{ga} 0%,{gb} 100%);
      border-radius:var(--radius);padding:18px 22px;margin:0 0 20px 0;
      border:1px solid {glow}33;display:flex;align-items:center;gap:16px;
      position:relative;overflow:hidden;box-shadow:0 8px 26px {glow}14">
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(
        -45deg,transparent,transparent 18px,rgba(255,255,255,.015) 18px,rgba(255,255,255,.015) 19px);pointer-events:none"></div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,{glow}88,transparent)"></div>
      <div class="ca-banner-icon" style="font-size:36px;line-height:1;flex-shrink:0">{emoji}</div>
      <div>
        <div style="font-family:'Poppins',sans-serif;color:#fff;font-size:19px;font-weight:800;letter-spacing:-0.3px;line-height:1.2">{title}</div>
        <div style="color:rgba(255,255,255,.5);font-size:12px;margin-top:3px">{subtitle}</div>
      </div>
    </div>""", unsafe_allow_html=True)

def record_card(icon, label, name, value, sub, color):
    return f"""<div style="background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
      padding:16px 18px;position:relative;overflow:hidden;box-shadow:var(--shadow)">
      <div style="position:absolute;top:-30px;right:-30px;width:100px;height:100px;
        background:radial-gradient(circle,{color}22 0%,transparent 70%)"></div>
      <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;
        letter-spacing:1px;display:flex;align-items:center;gap:6px;margin-bottom:8px">
        <span style="font-size:15px">{icon}</span>{label}</div>
      <div style="font-family:'Poppins',sans-serif;font-size:17px;font-weight:800;color:var(--text);
        line-height:1.25">{name}</div>
      <div style="font-family:var(--font-data);font-size:24px;font-weight:800;color:{color};margin-top:2px">{value}</div>
      <div style="font-size:11px;color:var(--subtle);margin-top:2px">{sub}</div>
    </div>"""

def record_grid(cards):
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:18px">{"".join(cards)}</div>',
                unsafe_allow_html=True)

def mval(df, model, metric):
    """Look up one number from cricket_model_metrics.csv (model, metric, value)."""
    if df is None or df.empty or not {"model","metric","value"}.issubset(df.columns): return None
    r = df[(df["model"]==model)&(df["metric"]==metric)]
    return float(r["value"].iloc[0]) if not r.empty else None

def _first_existing(df, names):
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.columns:
            return n
    return None

def prediction_context_box(title, target, horizon, cutoff=None, scope=None, assumptions=None, note=None):
    cutoff_txt = str(cutoff)[:19] if cutoff is not None and pd.notna(cutoff) else "Published dataset cutoff"
    assumptions = assumptions or []
    items = "".join("<li>"+str(x)+"</li>" for x in assumptions)
    note_html = ('<div style="margin-top:8px;font-size:11px;color:var(--muted)">'+str(note)+'</div>') if note else ''
    html = (
        '<div class="ca-section-card" style="padding:14px 16px;margin-bottom:14px">'
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">'
        '<div><div style="font-size:10px;font-weight:800;letter-spacing:1.2px;color:var(--accent);text-transform:uppercase">Prediction contract</div>'
        '<div style="font-family:var(--font-head);font-size:16px;font-weight:800;color:var(--text);margin-top:3px">'+str(title)+'</div></div>'
        '<span class="ca-pill">CUT-OFF: '+str(cutoff_txt)+'</span></div>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:12px">'
        '<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase">Target</div><div style="font-size:12px;color:var(--text);font-weight:700">'+str(target)+'</div></div>'
        '<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase">Horizon</div><div style="font-size:12px;color:var(--text);font-weight:700">'+str(horizon)+'</div></div>'
        '<div><div style="font-size:10px;color:var(--muted);text-transform:uppercase">Scope</div><div style="font-size:12px;color:var(--text);font-weight:700">'+str(scope or GENDER_PICK+' pool')+'</div></div></div>'
        '<div style="margin-top:10px;font-size:11px;color:var(--subtle);line-height:1.55"><b>Assumptions:</b><ul style="margin:4px 0 0 18px;padding:0">'+items+'</ul></div>'
        +note_html+'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def infer_cutoff(*dfs):
    vals=[]
    for df in dfs:
        if df is None or df.empty:
            continue
        for c in ("date","start_date","match_date","latest_date","data_cutoff","prediction_cutoff"):
            if c in df.columns:
                s=pd.to_datetime(df[c],errors="coerce")
                if s.notna().any():
                    vals.append(s.max())
    return max(vals) if vals else None

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return np.nan

# ── Win-probability engine (ported from notebook Step 11 predict_match) ──────
WP_FEATURES = ['elo_diff','form_diff','team1_h2h_rate','venue_diff',
               'toss_advantage','toss_field','toss_x_field','min_matches_played']
ELO_START = 1500.0

def _wp_mirror(X):
    """Same match from the other team's side — the model is trained on both views, so the
    answer is averaged over both and never depends on which team was typed first."""
    M = X.copy()
    M["elo_diff"], M["form_diff"], M["venue_diff"] = -X["elo_diff"], -X["form_diff"], -X["venue_diff"]
    M["team1_h2h_rate"], M["toss_advantage"], M["toss_x_field"] = 1-X["team1_h2h_rate"], 1-X["toss_advantage"], -X["toss_x_field"]
    return M

def predict_match_wp(team1, team2, fmt, gender, ratings, matches, toss_winner=None, toss_decision=None, venue=None):
    """P(team1 wins). Uses the trained model when loadable, else a transparent Elo blend."""
    def info(t):
        r = ratings[(ratings["team"]==t)&(ratings["format"]==fmt)]
        if "gender" in ratings.columns: r = r[r["gender"]==gender]
        if r.empty: return ELO_START, 0.5, 0
        r = r.iloc[0]; return float(r["elo"]), float(r["form"]), int(r["matches_played"])
    ea, fa, na = info(team1); eb, fb, nb = info(team2)

    pair = matches[(matches["format"]==fmt) &
                   (((matches["team1"]==team1)&(matches["team2"]==team2)) | ((matches["team1"]==team2)&(matches["team2"]==team1)))]
    if "gender" in matches.columns: pair = pair[pair["gender"]==gender]
    pair = pair[pair["winner"].isin([team1, team2])]
    w1 = int((pair["winner"]==team1).sum()); n_pair = len(pair)
    h2h_rate = (w1 + 1) / (n_pair + 2)                     # Laplace-smoothed, as in training

    tw = (toss_winner == team1); tf = str(toss_decision).lower() == "field"
    venue_diff = 0.0
    venue_note = "No venue supplied; venue effect is neutral."
    if venue and "venue" in matches.columns:
        vm = matches[matches["venue"].astype(str).str.casefold() == str(venue).casefold()]
        if "gender" in vm.columns:
            vm = vm[vm["gender"]==gender]
        if not vm.empty:
            a = vm[vm["team1"].eq(team1) | vm["team2"].eq(team1)]
            b = vm[vm["team1"].eq(team2) | vm["team2"].eq(team2)]
            aw = (a["winner"]==team1).mean() if len(a) else np.nan
            bw = (b["winner"]==team2).mean() if len(b) else np.nan
            if pd.notna(aw) and pd.notna(bw):
                venue_diff=float(aw-bw)
                venue_note=f"Venue evidence: {len(vm):,} recorded matches at {venue}."
    row = pd.DataFrame([{
        "elo_diff": ea-eb, "form_diff": fa-fb, "team1_h2h_rate": h2h_rate, "venue_diff": venue_diff,
        "toss_advantage": int(tw) if toss_winner else 0.5,
        "toss_field": int(tf) if toss_decision else 0.5,
        "toss_x_field": (2*int(tw)-1)*(2*int(tf)-1) if (toss_winner and toss_decision) else 0.0,
        "min_matches_played": min(na, nb)}])[WP_FEATURES]

    prob, mode = None, "elo"
    model = load_wp_model()
    if model is not None:
        try:
            prob = float(0.5*(model.predict_proba(row)[0,1] + 1 - model.predict_proba(_wp_mirror(row))[0,1]))
            mode = "model"
        except Exception:
            prob = None
    if prob is None:
        elo_p = 1/(1+10**(-(ea-eb)/400)); form_p = fa/(fa+fb) if (fa+fb)>0 else 0.5
        prob = 0.70*elo_p + 0.15*form_p + 0.15*h2h_rate
    return dict(prob=float(min(max(prob,0.02),0.98)), mode=mode, venue_note=venue_note, venue_diff=venue_diff,
                elo_a=ea, elo_b=eb, form_a=fa, form_b=fb,
                n_a=na, n_b=nb, h2h_a=w1, h2h_n=n_pair)

# ── Similar players: nearest neighbours on standardized stats ────────────────
# v9 notebook: "the dashboard ranks players by distance on these numbers (it no longer relies on the
# cluster label)". Totals are log-scaled, every feature is z-scored inside the same format AND
# men's/women's pool, then we take the closest players by Euclidean distance.
SIM_BAT_FEATS  = ["average","strike_rate","boundary_pct","dot_pct","runs"]
SIM_BOWL_FEATS = ["economy","average","dot_pct","strike_rate","wickets"]

def nearest_players(sim_df, name_col, feats, target_idx, n=12):
    tgt = sim_df.loc[target_idx]
    pool = sim_df[sim_df["format"]==tgt["format"]]
    if "gender" in pool.columns and pd.notna(tgt.get("gender")):
        pool = pool[pool["gender"]==tgt["gender"]]
    pool = pool.dropna(subset=feats)
    X = pool[feats].astype(float).copy()
    for c in ("runs","wickets"):
        if c in X.columns: X[c] = np.log1p(X[c])
    sd = X.std(ddof=0).replace(0, 1)
    Z = (X - X.mean()) / sd
    if target_idx not in Z.index: return pd.DataFrame()
    d = np.sqrt(((Z - Z.loc[target_idx])**2).sum(axis=1))
    out = pool.loc[d.index].assign(distance=d.round(2))
    out["match_pct"] = (100*np.exp(-out["distance"]/np.sqrt(len(feats)))).round(0).astype(int)
    out = out.drop(index=target_idx).sort_values("distance")
    return out.head(n)

# ── Name aliases ──────────────────────────────────────────────────────────────
NAME_ALIASES={
    "steve smith":"SPD Smith","smith":"SPD Smith","hazelwood":"JR Hazlewood",
    "josh hazelwood":"JR Hazlewood","hazlewood":"JR Hazlewood","warner":"DA Warner",
    "david warner":"DA Warner","rohit":"RG Sharma","rohit sharma":"RG Sharma",
    "bumrah":"JJ Bumrah","jasprit bumrah":"JJ Bumrah","starc":"MA Starc",
    "mitchell starc":"MA Starc","kohli":"V Kohli","virat kohli":"V Kohli",
    "babar":"Babar Azam","de villiers":"AB de Villiers","ab de villiers":"AB de Villiers",
    "stokes":"BA Stokes","ben stokes":"BA Stokes","root":"JE Root","joe root":"JE Root",
    "anderson":"JM Anderson","james anderson":"JM Anderson","broad":"SCJ Broad",
    "stuart broad":"SCJ Broad","afridi":"Shahid Afridi","shaheen":"Shaheen Shah Afridi",
    "rizwan":"Mohammad Rizwan","rashid":"Rashid Khan","buttler":"JC Buttler",
    "jos buttler":"JC Buttler","maxwell":"GJ Maxwell","dhoni":"MS Dhoni",
    "sachin":"SR Tendulkar","tendulkar":"SR Tendulkar","ponting":"RT Ponting",
    "sangakkara":"KC Sangakkara","malinga":"SL Malinga",
    "fakhar":"Fakhar Zaman","fakhar zaman":"Fakhar Zaman","imam":"Imam-ul-Haq",
    "iftikhar":"Iftikhar Ahmed","naseem":"Naseem Shah","shadab":"Shadab Khan",
    "smriti":"Smriti Mandhana","mandhana":"Smriti Mandhana",
    "smriti mandhana":"Smriti Mandhana","s mandhana":"S Mandhana",
    "shafali":"Shafali Verma","verma":"Shafali Verma",
    "harmanpreet":"Harmanpreet Kaur","kaur":"Harmanpreet Kaur",
    "deepti":"Deepti Sharma","mithali":"Mithali Raj","raj":"Mithali Raj",
    "jhulan":"Jhulan Goswami","goswami":"Jhulan Goswami","richa":"Richa Ghosh",
    "healy":"AJ Healy","perry":"EA Perry","gardner":"A Gardner",
    "sciver":"NR Sciver","tahlia":"TM McGrath","mcgrath":"TM McGrath",
    "amelia":"AMC Kerr","kerr":"AMC Kerr","devine":"SFM Devine",
    "kl rahul":"KL Rahul","rahul":"KL Rahul",
}
CRICSHEET_NAME={"Smriti Mandhana":"S Mandhana","Harmanpreet Kaur":"H Kaur",
                "Shafali Verma":"Shafali Verma","Deepti Sharma":"Deepti Sharma",
                "Mithali Raj":"Mithali Raj","Jhulan Goswami":"Jhulan Goswami",
                "Alyssa Healy":"AJ Healy","Ellyse Perry":"EA Perry","Ashleigh Gardner":"A Gardner"}

def resolve(name):
    display=NAME_ALIASES.get(name.strip().lower(),name)
    return CRICSHEET_NAME.get(display,display)

STOPWORDS = {
    "what","is","are","was","were","the","a","an","of","in","on","at","to",
    "for","and","or","who","how","much","many","did","does","do","has",
    "have","had","score","scores","highest","best","top","most","runs",
    "run","wicket","wickets","average","strike","rate","economy","stats",
    "stat","statistics","career","total","number","tell","me","about",
    "compare","vs","versus","between","player","batting","bowling",
    "match","matches","game","games","odi","odis","test","tests","t20",
    "t20i","t20is","ipl","psl","bbl","cpl","wpl","sa20","nt20","format","overall",
    "record","records","hundred","hundreds","fifty","fifties","century",
    "centuries","when","where","why","which","his","her","he","she",
    "their","it","this","that","currently","current","hit","hits","get",
    "gets","got","with","from","you","i","can","please","know","out",
    "all","time","times","win","wins","won","lost","lose","team","teams",
}

def get_player_stats_context(query):
    """Find a player name in the question and pull their real stats as text."""
    words = [w.strip(".,?!") for w in query.split()]
    candidates = []
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            phrase_words = words[i:i+n]
            if any(w.lower() in STOPWORDS or len(w) < 2 for w in phrase_words):
                continue
            candidates.append(" ".join(phrase_words))

    matches = []
    seen_players, seen_cands = set(), set()
    for cand in candidates:
        if len(cand) < 3 or cand.lower() in seen_cands:
            continue
        seen_cands.add(cand.lower())
        resolved = resolve(cand)
        bat_rows = find_rows(bat_fmt, "striker", resolved)
        bowl_rows = find_rows(bowl_fmt, "bowler", resolved)
        word_count = len(cand.split())

        if not bat_rows.empty:
            name = bat_rows["striker"].iloc[0]
            key = ("bat", name)
            if key not in seen_players:
                seen_players.add(key)
                lines = [f"{name} — Batting:"]
                for _, r in bat_rows.iterrows():
                    lines.append(
                        f"  {r['format']}: {r['matches']} matches, {r['runs']} runs, "
                        f"avg {r['average']}, SR {r['strike_rate']}, "
                        f"{r['fours']} fours, {r['sixes']} sixes, HS {r['highest']}, "
                        f"{r['hundreds']} hundreds, {r['fifties']} fifties"
                    )
                matches.append((word_count, "\n".join(lines)))
                if not bvb.empty and "dismissals" in bvb.columns:
                    vs_rows = bvb[bvb["striker"] == name]
                    vs_rows = vs_rows[vs_rows["dismissals"] > 0]
                    if not vs_rows.empty:
                        top_dismissals = (vs_rows.groupby("bowler")["dismissals"].sum()
                                          .sort_values(ascending=False).head(5))
                        vlines = [f"{name} — Most dismissed by:"]
                        for bowler_name, dismissal_count in top_dismissals.items():
                            vlines.append(f"  {bowler_name}: {dismissal_count} dismissals")
                        matches.append((word_count, "\n".join(vlines)))

        if not bowl_rows.empty:
            name = bowl_rows["bowler"].iloc[0]
            key = ("bowl", name)
            if key not in seen_players:
                seen_players.add(key)
                lines = [f"{name} — Bowling:"]
                for _, r in bowl_rows.iterrows():
                    lines.append(
                        f"  {r['format']}: {r['matches']} matches, {r['wickets']} wickets, "
                        f"avg {r['average']}, econ {r['economy']}, "
                        f"best {r['best_bowling']}, 5-wkt hauls {r['five_wkts']}"
                    )
                matches.append((word_count, "\n".join(lines)))

    matches.sort(key=lambda m: -m[0])
    return "\n\n".join(text for _, text in matches[:6])


def render_cricket_chat():
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    with st.popover("🤖 Ask the Cricket Bot", use_container_width=False):
        st.markdown("**🏏 Cricket Chat**")
        chat_box = st.container(height=320)
        with chat_box:
            for m in st.session_state.chat_messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

        with st.form(key="cricket_chat_form", clear_on_submit=True):
            user_q = st.text_input("Ask about any player or cricket in general...",
                                   label_visibility="collapsed")
            submitted = st.form_submit_button("Send")

            if submitted and user_q:
                st.session_state.chat_messages.append({"role": "user", "content": user_q})
                api_key = st.secrets.get("GROQ_API_KEY", "")
                if not api_key:
                    reply = "GROQ_API_KEY isn't set in secrets.toml yet."
                else:
                    data_context = get_player_stats_context(user_q)
                    system_prompt = (
                        "You are a friendly, knowledgeable cricket assistant embedded in a "
                        "cricket analytics dashboard. Answer general cricket questions from "
                        "your own knowledge. If the dashboard data below is relevant, prefer "
                        "it and cite those exact numbers — never invent stats.\n\n"
                    )
                    if data_context:
                        system_prompt += f"--- Dashboard data ---\n{data_context}\n--- End data ---"
                    try:
                        client = Groq(api_key=api_key)
                        resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "system", "content": system_prompt}]
                            + st.session_state.chat_messages[-10:],
                        )
                        reply = resp.choices[0].message.content
                    except Exception as e:
                        reply = f"Error reaching the chat model: {e}"
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.rerun()

# Known impossible player/format combos (name collisions inside Cricsheet itself)
KNOWN_BAD_PLAYER_FORMATS = {("Babar Azam", "IPL")}
def filter_valid_formats(player_name, formats_list):
    bad = {fmt for (name, fmt) in KNOWN_BAD_PLAYER_FORMATS if name == player_name}
    return [f for f in formats_list if f not in bad]

WIKI_NAMES={
    "V Kohli":"Virat Kohli","Babar Azam":"Babar Azam","SPD Smith":"Steve Smith cricketer",
    "DA Warner":"David Warner cricketer","RG Sharma":"Rohit Sharma","JJ Bumrah":"Jasprit Bumrah",
    "MA Starc":"Mitchell Starc","JR Hazlewood":"Josh Hazlewood","BA Stokes":"Ben Stokes",
    "JE Root":"Joe Root","JM Anderson":"James Anderson cricketer","SCJ Broad":"Stuart Broad",
    "KC Sangakkara":"Kumar Sangakkara","SR Tendulkar":"Sachin Tendulkar","MS Dhoni":"MS Dhoni",
    "RT Ponting":"Ricky Ponting","SL Malinga":"Lasith Malinga","Rashid Khan":"Rashid Khan cricketer",
    "Shahid Afridi":"Shahid Afridi","Mohammad Rizwan":"Mohammad Rizwan cricketer",
    "Shaheen Shah Afridi":"Shaheen Shah Afridi","JC Buttler":"Jos Buttler",
    "GJ Maxwell":"Glenn Maxwell cricketer","AB de Villiers":"AB de Villiers",
    "Fakhar Zaman":"Fakhar Zaman","Imam-ul-Haq":"Imam-ul-Haq",
    "Naseem Shah":"Naseem Shah cricketer","Shadab Khan":"Shadab Khan cricketer",
    "Smriti Mandhana":"Smriti Mandhana","Shafali Verma":"Shafali Verma",
    "Harmanpreet Kaur":"Harmanpreet Kaur","Deepti Sharma":"Deepti Sharma cricketer",
    "Mithali Raj":"Mithali Raj","Jhulan Goswami":"Jhulan Goswami",
    "Richa Ghosh":"Richa Ghosh cricketer","AJ Healy":"Alyssa Healy",
    "EA Perry":"Ellyse Perry","A Gardner":"Ashleigh Gardner",
    "NR Sciver":"Nat Sciver-Brunt","TM McGrath":"Tahlia McGrath",
    "AMC Kerr":"Amelia Kerr","SFM Devine":"Sophie Devine","KL Rahul":"KL Rahul cricketer",
    "V Suryavanshi":"Vaibhav Suryavanshi",
}

@st.cache_data(ttl=600, show_spinner=False)  # short cache so one transient Wikipedia hiccup recovers quickly
def get_wiki(cricsheet_name, search_name):
    try:
        import re, time
        wiki_title=WIKI_NAMES.get(cricsheet_name, search_name+" cricketer")

        sr = None
        for attempt in range(2):
            try:
                sr=requests.get("https://en.wikipedia.org/w/api.php",
                    params={"action":"query","list":"search","srsearch":wiki_title,
                            "format":"json","utf8":1,"srlimit":5},
                    timeout=8,headers={"User-Agent":"CricketAnalyticsApp/2.0"})
                sr.raise_for_status()
                break
            except Exception:
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise
        results=sr.json().get("query",{}).get("search",[])
        if not results:
            st.session_state.setdefault("wiki_missing_full", []).append(
                (cricsheet_name, f"no Wikipedia search results for '{wiki_title}'"))
            return None

        # Name similarity is the dominant factor; cricket keywords only break ties.
        import difflib
        target_name = wiki_title.replace(" cricketer", "").strip().lower()
        def _name_similarity(title):
            t = title.lower().replace("(cricketer)","").strip()
            return difflib.SequenceMatcher(None, target_name, t).ratio()

        def _score(result):
            snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).lower()
            title = result.get("title", "")
            name_sim = _name_similarity(title)
            score = name_sim * 20
            if "cricket" in snippet: score += 3
            if "batsman" in snippet or "bowler" in snippet or "batter" in snippet: score += 1
            if "wicket-keeper" in snippet or "all-rounder" in snippet: score += 1
            if any(w in snippet for w in ["footballer","actor","musician","politician","author"]) \
               and "cricket" not in snippet:
                score -= 5
            if name_sim < 0.4:
                score -= 15
            return score

        scored = sorted(results, key=_score, reverse=True)
        best_score = _score(scored[0])
        if best_score <= 0:
            st.session_state.setdefault("wiki_low_confidence", []).append(
                (cricsheet_name, f"no candidate clearly matched 'cricketer' — using best guess '{scored[0]['title']}'"))
        page_title=scored[0]["title"]
        safe=page_title.replace(" ","_")
        rr=requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe}",
            timeout=8,headers={"User-Agent":"CricketAnalyticsApp/2.0"})
        rr.raise_for_status(); data=rr.json()

        if data.get("type") == "disambiguation":
            st.session_state.setdefault("wiki_low_confidence", []).append(
                (cricsheet_name, f"'{page_title}' is a Wikipedia disambiguation page "
                                  f"(name shared by multiple real people) — profile withheld "
                                  f"rather than showing the wrong person's bio."))
            return None

        img=data.get("thumbnail",{}).get("source","")
        bio=data.get("extract","")
        sents=[s.strip() for s in bio.split(".") if len(s.strip())>15]
        bio=". ".join(sents[:5])+"." if sents else bio[:600]
        bio=bio.replace("..",".")
        ir=requests.get("https://en.wikipedia.org/w/api.php",
            params={"action":"query","titles":page_title,"prop":"revisions",
                    "rvprop":"content","rvslots":"main","format":"json","rvsection":0},
            timeout=8,headers={"User-Agent":"CricketAnalyticsApp/2.0"})
        ir.raise_for_status()
        pages=ir.json().get("query",{}).get("pages",{})
        wt=next(iter(pages.values())).get("revisions",[{}])[0].get("slots",{}).get("main",{}).get("*","")
        def clean(v):
            v=re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]",r"\2",v)
            v=re.sub(r"\{\{[^}]+\}\}","",v); v=re.sub(r"<[^>]+>","",v)
            v=re.sub(r"\[\[.*?\]\]","",v)
            return v.strip().strip("|").strip()
        def ef(text,keys):
            for k in keys:
                m=re.search(r"\|\s*"+re.escape(k)+r"\s*=\s*([^\n\|}{]{2,80})",text,re.IGNORECASE)
                if m:
                    v=clean(m.group(1))
                    if len(v)>3 and "[[" not in v: return v
            return ""
        def er(text,keys):
            for k in keys:
                m=re.search(r"\|\s*"+re.escape(k)+r"\s*=\s*([^\n]{2,150})",text,re.IGNORECASE)
                if m: return m.group(1).strip()
            return ""
        def pd2(v):
            if not v: return ""
            mo=["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            m=re.search(r"\{\{(?:dts|birth date(?:[^|]*)?)[\s|]+([\d]{4})[|\s]+([\d]{1,2})[|\s]+([\d]{1,2})",v,re.IGNORECASE)
            if m:
                try: return f"{int(m.group(3))} {mo[int(m.group(2))]} {m.group(1)}"
                except: pass
            m2=re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})",v)
            if m2:
                try:
                    mx=int(m2.group(2))
                    if 1<=mx<=12: return f"{int(m2.group(3))} {mo[mx]} {m2.group(1)}"
                except: pass
            m3=re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",v)
            if m3: return f"{int(m3.group(1))} {m3.group(2)[:3].capitalize()} {m3.group(3)}"
            m4=re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",v)
            if m4: return f"{int(m4.group(2))} {m4.group(1)[:3].capitalize()} {m4.group(3)}"
            return ""
        born=""
        bd=re.search(r"\{\{birth date(?:\s*and age)?\s*\|([^}]+)\}\}",wt,re.IGNORECASE)
        if bd:
            parts2=[p.strip() for p in bd.group(1).split("|") if p.strip().isdigit()]
            if len(parts2)>=3:
                mo2=["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                try: born=f"{int(parts2[2])} {mo2[int(parts2[1])]} {parts2[0]}"
                except: pass
        if not born: born=ef(wt,["birth_date","birthdate","born"])
        odi_d=pd2(er(wt,["odidebutdate","ODIdebutdate","odi_debut_date"]))
        test_d=pd2(er(wt,["testdebutdate","Testdebutdate","test_debut_date"]))
        t20_d=pd2(er(wt,["t20idebutdate","T20Idebutdate","T20debutdate","t20_debut_date"]))
        any_d=pd2(er(wt,["debutdate","debut_date","internationaldebutdate"]))
        role_raw=ef(wt,["role","batting_style","batting style","bowling_style","bowling style"])
        role_raw=re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]",r"\2",role_raw)
        role_raw=re.sub(r"\{\{[^}]+\}\}","",role_raw).strip()
        desc=data.get("description","")
        if not role_raw or "[[" in role_raw or len(role_raw)<3:
            role_raw=desc[:60] if desc else ""
        nation=ef(wt,["country","nationality","national_side","national side"])

        # Official per-format career totals from the infobox mini-table (fallback for careers Cricsheet barely covers)
        career_stats = {}
        _fmt_aliases = {"ODI": ["odi", "one day international", "one-day international"],
                        "Test": ["test"], "T20I": ["t20i", "twenty20 international", "t20 international"]}
        for i in range(1, 8):
            col_m = re.search(rf"\|\s*column{i}\s*=\s*([^\n\|]{{2,40}})", wt, re.IGNORECASE)
            if not col_m:
                continue
            col_label = clean(col_m.group(1)).lower()
            fmt_match = next((fmt for fmt, aliases in _fmt_aliases.items()
                              if any(a in col_label for a in aliases)), None)
            if not fmt_match or fmt_match in career_stats:
                continue
            def _field(names):
                for n in names:
                    m = re.search(rf"\|\s*{re.escape(n)}{i}\s*=\s*([^\n\|]{{1,20}})", wt, re.IGNORECASE)
                    if m:
                        v = re.sub(r"<[^>]+>", "", m.group(1)).replace(",", "").strip()
                        if v: return v
                return None
            def _num(v):
                if not v: return None
                m = re.search(r"[\d.]+", v)
                return float(m.group()) if m else None
            matches_v, runs_v = _num(_field(["matches"])), _num(_field(["runs"]))
            avg_v = _num(_field(["bat avg", "batting average", "bat_avg"]))
            hs50 = _field(["100s/50s", "100s_50s"])
            hundreds = int(float(hs50.split("/")[0])) if hs50 and hs50.split("/")[0].replace(".", "").isdigit() else None
            top_score_raw = _field(["top score", "high score", "hs", "best score"])
            top_score_v = _num(top_score_raw) if top_score_raw else None
            wickets_v = _num(_field(["wickets"]))
            bowl_avg_v = _num(_field(["bowl avg", "bowling average", "bowl_avg"]))
            best_bowling_v = _field(["best bowling", "bbi", "best_bowling"])
            if matches_v is not None:
                career_stats[fmt_match] = {"matches": int(matches_v),
                    "runs": int(runs_v) if runs_v is not None else None,
                    "average": avg_v, "hundreds": hundreds, "top_score": top_score_v,
                    "wickets": int(wickets_v) if wickets_v is not None else None,
                    "bowl_average": bowl_avg_v,
                    "best_bowling": best_bowling_v}

        result = {"title":data.get("title",page_title),"bio":bio,"img":img,
                "born":born[:60] if born else "",
                "odi_debut":odi_d or any_d,"test_debut":test_d or any_d,"t20_debut":t20_d or any_d,
                "ipl_debut":"","psl_debut":"","wpl_debut":"",
                "role":role_raw[:60] if role_raw else "",
                "nation":nation[:40] if nation else "",
                "career_stats":career_stats}
        if not result["born"]:
            st.session_state.setdefault("wiki_missing_field", []).append(
                (cricsheet_name, "no birth date found on matched page: " + result["title"]))
        return result
    except Exception as e:
        st.session_state.setdefault("wiki_missing_full", []).append((cricsheet_name, str(e)))
        return None

# ── show_player_card (native Streamlit components so tags can never leak as raw text) ──
import html as _html

def show_player_card(cricsheet_name, search_name, fmt="ODI", compact=False):
    card=get_wiki(cricsheet_name,search_name)
    with st.container(border=True):
        if not card:
            st.caption(f"🖼️ No Wikipedia bio/photo found for {cricsheet_name} — this only affects the bio card, not the stats below.")
            return
        img_col, info_col = st.columns([1,9], gap="small") if not compact else st.columns([1,12], gap="small")
        with img_col:
            if card["img"]:
                st.image(card["img"], width=72 if compact else 96)
        with info_col:
            name_sz = "##### " if compact else "#### "
            st.markdown(f"{name_sz}{card['title']}")
            fmt_key={"ODI":"odi_debut","Test":"test_debut","T20I":"t20_debut","IPL":"ipl_debut",
                     "PSL":"psl_debut","WPL":"wpl_debut","BBL":"odi_debut","CPL":"odi_debut"}.get(fmt,"odi_debut")
            debut=card.get(fmt_key,"") or card.get("odi_debut","") or card.get("test_debut","") or card.get("t20_debut","")
            pill_parts=[]
            if card["born"]: pill_parts.append(f"🎂 {card['born']}")
            if card["nation"]: pill_parts.append(f"🌍 {card['nation']}")
            if card["role"]: pill_parts.append(f"🏏 {card['role'][:30]}")
            if debut: pill_parts.append(f"🎯 {fmt} debut {debut}")
            if pill_parts:
                st.caption("  •  ".join(pill_parts))
            max_sents=2 if compact else 4
            short_bio=". ".join(card["bio"].split(". ")[:max_sents])+"." if card["bio"] else ""
            if short_bio:
                st.caption(short_bio)

# ── SIDEBAR NAVIGATION ─────────────────────────────────────────────────────────
PAGE_GROUPS=[
    (None, ["🏠 Home"]),
    ("🔍 Player Tools", ["🔍 Player Search","⚔️ Head to Head","🏟️ vs Venue","🌍 vs Opponent","🤜 Batter vs Bowler","📈 Over Years"]),
    ("🏆 Records & Rankings", ["🏆 Leaderboard","🏅 League Records"]),
    ("🤖 Insights", ["🤖 Similar Players","🔥 Form & Ratings"]),
    ("🛡️ Data Quality", ["🛡️ Data Integrity"]),
]
PAGES=[p for _,grp in PAGE_GROUPS for p in grp]

if "page" not in st.session_state: st.session_state["page"]="🏠 Home"
if "nav_history" not in st.session_state: st.session_state["nav_history"]=[]

if st.session_state.get("_go"):
    dest = st.session_state["_go"]
    del st.session_state["_go"]
    cur = st.session_state.get("page","🏠 Home")
    if cur != dest:
        st.session_state["nav_history"].append(cur)
    st.session_state["page"] = dest

if st.session_state.get("_back"):
    del st.session_state["_back"]
    hist = st.session_state.get("nav_history",[])
    if hist:
        prev = hist.pop()
        st.session_state["nav_history"] = hist
        st.session_state["page"] = prev

last_upd=get_last_updated()
pkt=datetime.now(timezone(timedelta(hours=5)))
status_txt=f"Updated {last_upd}" if last_upd else f"{pkt.strftime('%H:%M')} PKT"

section = st.session_state["page"]

with st.sidebar:
    st.markdown(f"""<div class="ca-brand">
      <span class="ca-brand-mark">🏏</span>
      <span class="ca-brand-text">Cricket<span>Analytics</span></span>
    </div>
    <div class="ca-brand-status"><span class="ca-live"></span>{status_txt}</div>""", unsafe_allow_html=True)

    st.markdown('<div class="ca-sidebar-utility">', unsafe_allow_html=True)
    ucol1, ucol2 = st.columns(2)
    with ucol1:
        if st.button("🔄 Refresh", help="Force-reload the latest data now", key="_refresh_btn"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    with ucol2:
        st.toggle("☀️ Light" if not IS_LIGHT else "🌙 Dark", key="is_light_mode",
                  help="Switch between dark and light mode")
    st.markdown('</div>', unsafe_allow_html=True)

    st.caption("📦 Source: current Cricsheet pipeline · 8 loaded competitions")

    for group_label, group_pages in PAGE_GROUPS:
        if group_label:
            st.markdown(f'<div class="ca-nav-group">{group_label}</div>', unsafe_allow_html=True)
        for p in group_pages:
            is_active = (section == p)
            if st.button(p, key=f"navbtn_{p}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                if not is_active:
                    st.session_state["_go"] = p
                    st.rerun()

chat_corner = st.container(key="ca_chat_corner")
with chat_corner:
    render_cricket_chat()

st.markdown('<div class="ca-content">', unsafe_allow_html=True)

if section != "🏠 Home" and st.session_state.get("nav_history"):
    prev_page = st.session_state["nav_history"][-1]
    prev_label = " ".join(prev_page.split()[1:]) if len(prev_page.split()) > 1 else prev_page
    if st.button(f"← Back  to {prev_label}", key="_back_btn", type="secondary"):
        st.session_state["_back"] = True
        st.rerun()

# ══ HOME ═════════════════════════════════════════════════════════════════════
if section=="🏠 Home":
    fmt_pills="".join([
        f'<span style="background:{FORMAT_META.get(f,("","#00e5a0",""))[1]}18;'
        f'color:{FORMAT_META.get(f,("","#00e5a0",""))[1]};'
        f'border:1px solid {FORMAT_META.get(f,("","#00e5a0",""))[1]}44;'
        f'padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700">'
        f'{FORMAT_META.get(f,("🏏","",""))[0]} {f}</span>'
        for f in ALL_FMT
    ])
    st.markdown(f"""<div class="ca-fade" style="background:linear-gradient(150deg,#080c14,#0c1628,#080c14);
      border-radius:16px;padding:36px 32px 28px;margin-bottom:24px;
      border:1px solid var(--border);position:relative;overflow:hidden">
      <div style="position:absolute;top:-80px;left:20%;width:400px;height:300px;background:radial-gradient(ellipse,rgba(61,123,255,.06) 0%,transparent 70%);pointer-events:none"></div>
      <div style="position:absolute;bottom:-60px;right:5%;width:300px;height:220px;background:radial-gradient(ellipse,rgba(255,106,46,.05) 0%,transparent 70%);pointer-events:none"></div>
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,106,46,.03) 39px,rgba(255,106,46,.03) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,106,46,.03) 39px,rgba(255,106,46,.03) 40px);pointer-events:none"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
        <span style="font-size:40px">🏏</span>
        <div>
          <h1 style="font-family:'Poppins',sans-serif;color:#fff;margin:0;font-size:30px;font-weight:800;letter-spacing:-0.5px">Cricket <span class="ca-shimmer">Analytics</span></h1>
          <p style="color:var(--muted);font-size:13px;margin:4px 0 0">Ball-by-ball data · All-time records · {len(ALL_FMT)} competitions · men's &amp; women's</p>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 18px">{fmt_pills}</div>
      <div style="display:flex;align-items:center;gap:8px;background:rgba(61,123,255,.06);border:1px solid rgba(61,123,255,.15);border-radius:20px;padding:6px 14px;width:fit-content">
        <span class="ca-live"></span>
        <span style="font-size:11px;font-weight:600;color:var(--accent)">Published dataset · refreshed by the Cricsheet pipeline</span>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("#### 🔍 Quick Player Search")
    qname=st.text_input("","",placeholder="Type a player name — Babar, Kohli, Smriti, Shaheen, Maxwell...",
                        key="home_search",label_visibility="collapsed")
    if qname:
        st.session_state["_go"]="🔍 Player Search"
        st.session_state["ps_name"]=qname
        st.rerun()

    with st.expander("📖 New to cricket stats? Quick glossary — what the numbers mean"):
        st.caption("Every stat card in this app also has a small **?** you can hover over for its definition. Here's the full list:")
        g_items = list(GLOSSARY.items())
        g_cols = st.columns(2)
        for i, (term, definition) in enumerate(g_items):
            g_cols[i % 2].markdown(
                f'<div class="ca-pill" style="display:block;white-space:normal;margin-bottom:6px;padding:8px 12px">'
                f'<span style="color:var(--accent);text-transform:capitalize">{term}</span>'
                f'<br><span style="color:var(--subtle);font-family:var(--font-body);font-weight:400">{definition}</span></div>',
                unsafe_allow_html=True)

    st.markdown("#### Explore")
    features=[
        ("📊","Career Statistics","Batting and bowling records from the published ball-by-ball dataset","🏆 Leaderboard"),
        ("🔎","Player Search","Explore one player's statistics across every loaded format","🔍 Player Search"),
        ("⚔️","Head to Head","Compare any two players side by side","⚔️ Head to Head"),
        ("🏟️","Player vs Venue","How a player performs at each ground","🏟️ vs Venue"),
        ("🌍","vs Opponent","Dominance stats against each team","🌍 vs Opponent"),
        ("🤜","Batter vs Bowler","Ball-by-ball matchup data","🤜 Batter vs Bowler"),
        ("📈","Career Timeline","Year-by-year performance charts","📈 Over Years"),
        ("🏆","Leaderboard","Top players ranked by format & stat","🏆 Leaderboard"),
        ("🏅","League Records","Highest score, most fours & sixes by league","🏅 League Records"),
        ("🤖","Similar Players","Statistical look-alikes for any player","🤖 Similar Players"),
        ("🔥","Form & Ratings","Who's hot, who's cold right now","🔥 Form & Ratings"),
    ]
    cols=st.columns(4)
    for i,(emoji,title,desc,target) in enumerate(features):
        with cols[i%4]:
            if st.button(f"{emoji} **{title}**\n\n{desc}",key=f"feat_{i}",use_container_width=True):
                st.session_state["_go"]=target; st.rerun()

    st.markdown("---")
    st.markdown(f"#### 🏆 Quick Leaderboard — {GENDER_PICK}")
    ql_fmt=st.radio("Format",ALL_FMT_G,horizontal=True,key="ql_fmt")
    qlc1,qlc2=st.columns(2)
    with qlc1:
        st.markdown("**Top 5 Batters by Runs**")
        top_bat=gf(bat_fmt)[gf(bat_fmt)["format"]==ql_fmt].sort_values("runs",ascending=False).head(5)[["striker","runs","average","strike_rate"]] if not bat_fmt.empty else pd.DataFrame()
        if not top_bat.empty: st.dataframe(top_bat.reset_index(drop=True),hide_index=True)
    with qlc2:
        st.markdown("**Top 5 Bowlers by Wickets**")
        top_bowl=gf(bowl_fmt)[gf(bowl_fmt)["format"]==ql_fmt].sort_values("wickets",ascending=False).head(5)[["bowler","wickets","economy","average"]] if not bowl_fmt.empty else pd.DataFrame()
        if not top_bowl.empty: st.dataframe(top_bowl.reset_index(drop=True),hide_index=True)

# ══ LIVE MATCHES (not in the nav; kept for the optional CricAPI file) ═════════
elif section=="🔴 Live Matches":
    page_banner("🔴","Live Matches","Matches currently in progress — from CricketData.org, updated every 30 min","#1a0508","#2e0a12","#ff4d6d")
    live_df = load_live_matches()
    if live_df.empty:
        st.info("No matches are live right now. Check back soon — this refreshes every 30 minutes.")
    else:
        for _, m in live_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                with c1:
                    st.markdown(f"**{m.get('match_name','')}**")
                    st.caption(f"📍 {m.get('venue','')}  •  {m.get('match_type','').upper()}  •  {m.get('status','')}")
                    if m.get('score_summary'):
                        st.markdown(f"`{m['score_summary']}`")
                with c2:
                    st.caption(f"{m.get('team1','')} vs {m.get('team2','')}")
        st.caption("ℹ️ Sourced from CricketData.org (CricAPI) — separate from the Cricsheet-based career stats elsewhere in this app.")

# ══ MATCH RESULTS ═════════════════════════════════════════════════════════════
elif section=="📋 Match Results":
    page_banner("📋","Match Results","Every completed match with a result — winner, margin, venue, toss","#0d1210","#1a251c","#8a95a8")
    results = gf(load_match_results())
    if results is None or results.empty:
        st.info(f"No {GENDER_PICK.lower()} match results available. This page reads `cricket_matches_info.csv` "
                f"(notebook Step 17) — check that push succeeded, or switch men's/women's in the sidebar.")
    else:
        fmt_opts = order_fmts(results["format"].dropna().unique().tolist()) if "format" in results.columns else []
        fmt = st.radio("Competition", fmt_opts, horizontal=True) if fmt_opts else None
        rf = results[results["format"]==fmt] if fmt else results

        # International formats are country-vs-country, so franchise/odd sides are filtered out;
        # franchise leagues are club competitions and are left alone.
        if fmt in INTERNATIONAL_FORMATS and "team1" in rf.columns:
            rf = rf[rf["team1"].apply(is_real_country) & rf["team2"].apply(is_real_country)]

        teams = sorted(set(rf["team1"].dropna().unique().tolist() + rf["team2"].dropna().unique().tolist())) if "team1" in rf.columns else []
        tab1, tab2 = st.tabs(["📜 Match List", "⚔️ Head to Head"])

        with tab1:
            team_filter = st.selectbox("Filter by team (optional)", ["All teams"]+teams)
            rf_show = rf if team_filter=="All teams" else rf[(rf["team1"]==team_filter)|(rf["team2"]==team_filter)]
            show_cols = [c for c in ["date","team1","team2","venue","city","toss_winner","toss_decision",
                                      "winner","winner_by","winner_margin","player_of_match"] if c in rf_show.columns]
            rf_show = rf_show.sort_values("date", ascending=False) if "date" in rf_show.columns else rf_show
            st.dataframe(rf_show[show_cols].reset_index(drop=True), hide_index=True)
            st.caption(f"{len(rf_show):,} matches shown (matches with no result are excluded)")

        with tab2:
            if len(teams) >= 2:
                c1, c2 = st.columns(2)
                t1 = c1.selectbox("Team A", teams, index=0, key="h2h_t1")
                t2 = c2.selectbox("Team B", teams, index=1 if len(teams)>1 else 0, key="h2h_t2")
                if t1 and t2 and t1 != t2:
                    h2h = rf[((rf["team1"]==t1)&(rf["team2"]==t2))|((rf["team1"]==t2)&(rf["team2"]==t1))]
                    if h2h.empty:
                        st.info(f"No recorded matches between {t1} and {t2}.")
                    else:
                        t1_wins = int((h2h["winner"]==t1).sum())
                        t2_wins = int((h2h["winner"]==t2).sum())
                        no_result = len(h2h) - t1_wins - t2_wins
                        metrics({f"{t1} wins": t1_wins, f"{t2} wins": t2_wins, "Total matches": len(h2h)})
                        ch(donut([t1, t2, "No result/other"], [t1_wins, t2_wins, max(no_result,0)],
                                 [FC["ODI"], FC["Test"], "#636e72"], f"{t1} vs {t2} — Head to Head"), 300)
                        show_cols2 = [c for c in ["date","venue","winner","winner_by","winner_margin"] if c in h2h.columns]
                        st.dataframe(h2h.sort_values("date", ascending=False)[show_cols2].reset_index(drop=True), hide_index=True)
                else:
                    st.caption("Pick two different teams.")
            else:
                st.info("Not enough team data to build a head-to-head view.")

# ══ PLAYER FORECAST ═══════════════════════════════════════════════════════════
elif section=="🔮 Player Forecast":
    page_banner("🔮","Player Forecast","Forward run projection with explicit target period, cutoff and assumptions","#1a1408","#2e2410","#ff6a2e")
    pf=load_player_forecast(); rf_out=load_run_forecast(); mm=load_model_metrics()
    cutoff=infer_cutoff(pf,rf_out,bat_yr,bat_fmt)
    prediction_context_box(
        "Projected batter runs",
        "One batter's total runs in the published future season/window",
        "The projection year / target period published by the notebook",
        cutoff=cutoff,
        scope=f"{GENDER_PICK} • selected format • qualified active batters",
        assumptions=[
            "The batter is available and selected for the target period.",
            "The batter receives broadly comparable batting opportunity.",
            "Future injuries, selection, schedule and batting-order changes are not known.",
            "This is a forward total, not a next-match score."
        ],
        note="The dashboard displays the notebook's published forecast; it does not silently recompute a different forecast."
    )
    if pf.empty and rf_out.empty:
        st.info("Forecast data isn't available yet. Publish the forecast files from the notebook.")
    else:
        tab1,tab2,tab3=st.tabs(["🔍 Look Up a Player","📈 Who's Trending","🧪 Held-out Validation"])
        _gmap=bat_fmt[["striker","format","gender"]].drop_duplicates(["striker","format"]) if ("gender" in bat_fmt.columns and not bat_fmt.empty) else None
        pf_g=pf.merge(_gmap,on=["striker","format"],how="left") if (_gmap is not None and not pf.empty) else pf
        pf_g=gf(pf_g)
        with tab1:
            if pf.empty: st.info("`cricket_player_forecast.csv` isn't available yet.")
            else:
                pname=player_input("Player name",resolve("Kohli"),key="forecast_player")
                prow=find_rows(pf,"striker",resolve(pname)) if pname else pd.DataFrame()
                if prow.empty:
                    st.info(f"No published projection for '{pname}'. This usually means the notebook's eligibility/history rule was not met.")
                else:
                    fmts=order_fmts(prow["format"].dropna().unique().tolist())
                    pick_fmt=st.radio("Format",fmts,horizontal=True,key="pf_fmt")
                    r=prow[prow["format"]==pick_fmt].iloc[0]
                    last_y=int(r["last_season_year"]) if pd.notna(r.get("last_season_year",np.nan)) else None
                    proj_y=int(r["projection_year"]) if pd.notna(r.get("projection_year",np.nan)) else None
                    actual=safe_float(r.get("last_season_runs",np.nan)); pred=safe_float(r.get("projected_next_season_runs",np.nan))
                    st.markdown(f"### {r['striker']} — {pick_fmt}")
                    st.caption(f"Projection target: **{proj_y if proj_y else 'defined future period'}** • reference season: **{last_y if last_y else '—'}**")
                    if pd.notna(pred):
                        delta=pred-actual if pd.notna(actual) else np.nan
                        metrics({"Reference-season runs":f"{actual:.0f}" if pd.notna(actual) else "—","Projected runs":f"{pred:.0f}","Change vs reference":f"{delta:+.0f}" if pd.notna(delta) else "—"})
                        lo=safe_float(r.get("prediction_low",r.get("lower_bound",np.nan))); hi=safe_float(r.get("prediction_high",r.get("upper_bound",np.nan)))
                        if pd.notna(lo) and pd.notna(hi):
                            st.info(f"Published forecast interval: **{lo:.0f}–{hi:.0f} runs**. This is an uncertainty interval, not a guarantee.")
                        fig=go.Figure(go.Bar(x=[f"{last_y} actual" if last_y else "Reference",f"{proj_y} projected" if proj_y else "Projection"],
                                             y=[actual if pd.notna(actual) else 0,pred],
                                             text=[f"{actual:.0f}" if pd.notna(actual) else "—",f"{pred:.0f}"],textposition="outside",
                                             marker_color=[FC.get(pick_fmt,ACCENT2),ACCENT]))
                        fig.update_layout(**BASE,height=340,showlegend=False,margin=dict(l=20,r=30,t=20,b=20),yaxis_title="Runs")
                        st.plotly_chart(fig,**CFG)
                    prov=[c for c in ["training_start","training_end","prediction_cutoff","projection_year","target_period","model","model_name","training_seasons","history_seasons","eligible"] if c in r.index]
                    if prov:
                        with st.expander("🔎 Forecast provenance"):
                            st.dataframe(pd.DataFrame({"Field":prov,"Value":[str(r[c]) for c in prov]}),hide_index=True)
        with tab2:
            if pf_g is None or pf_g.empty: st.info(f"No {GENDER_PICK.lower()} projections available.")
            else:
                fmt2=st.radio("Format",order_fmts(pf_g["format"].dropna().unique().tolist()),horizontal=True,key="forecast_fmt")
                how=st.radio("Rank by",["Most projected runs","Biggest projected rise","Biggest projected drop"],horizontal=True,key="forecast_rank")
                ff=pf_g[pf_g["format"]==fmt2].dropna(subset=["projected_next_season_runs","last_season_runs"]).copy()
                py=int(ff["projection_year"].iloc[0]) if not ff.empty and pd.notna(ff["projection_year"].iloc[0]) else ""
                ff["change"]=ff["projected_next_season_runs"]-ff["last_season_runs"]
                if how=="Most projected runs":
                    top_n=ff.nlargest(15,"projected_next_season_runs"); ch(bar_h(top_n,"projected_next_season_runs","striker","projected_next_season_runs","Purples",f"Top projected run totals — {fmt2} {py}"))
                elif how=="Biggest projected rise":
                    top_n=ff[ff["last_season_runs"]>=100].nlargest(15,"change"); ch(bar_h(top_n,"change","striker","change","Greens",f"Largest projected increase — {fmt2} {py}"))
                else:
                    top_n=ff[ff["last_season_runs"]>=100].assign(drop=lambda d:-d["change"]).nlargest(15,"drop"); ch(bar_h(top_n,"drop","striker","drop","Reds",f"Largest projected decrease — {fmt2} {py}"))
                st.caption("Conditional projections from the published forecast file; not a ranking of overall player quality.")
        with tab3:
            if rf_out.empty: st.info("Held-out validation data isn't available yet.")
            elif {"runs","predicted_runs"}.issubset(rf_out.columns):
                d=rf_out.dropna(subset=["runs","predicted_runs"]).copy(); d["error"]=d["predicted_runs"]-d["runs"]
                metrics({"Test rows":f"{len(d):,}","MAE":f"{d['error'].abs().mean():.1f} runs","Bias":f"{d['error'].mean():+.1f} runs"})
                fig=px.scatter(d,x="runs",y="predicted_runs",hover_name="striker" if "striker" in d.columns else None,title="Held-out: actual vs predicted runs")
                lim=max(float(d[["runs","predicted_runs"]].max().max()),1); fig.add_shape(type="line",x0=0,y0=0,x1=lim,y1=lim,line=dict(color=MUTED,dash="dash"))
                fig.update_layout(**BASE,height=380,margin=M_DEFAULT,xaxis_title="Actual runs",yaxis_title="Predicted runs"); st.plotly_chart(fig,**CFG)
                st.caption("This tests future-period generalization. It does not mean the model has never seen the player before.")
# ══ BOWLER WORKLOAD ═══════════════════════════════════════════════════════════
elif section=="💪 Bowler Workload":
    page_banner("💪","Bowler Workload","Recent bowling load — legal-ball overs separated from delivery workload","#1a0d08","#2e1a10","#3d7bff")
    workload=load_bowler_workload()
    ratio_col=_first_existing(workload,["acwr","workload_ratio","acute_chronic_ratio"])
    risk_col=_first_existing(workload,["risk_flag","load_flag","workload_flag"])
    prediction_context_box(
        "Bowler workload monitor",
        "Recent bowling load relative to the notebook's defined baseline",
        "Notebook-defined recent workload windows",
        cutoff=infer_cutoff(workload,bowl_yr),
        scope=f"{GENDER_PICK} • selected format • bowlers with sufficient history",
        assumptions=[
            "Legal balls are used to calculate overs.",
            "Delivery-level workload follows the notebook definition.",
            "The ratio is a workload-monitoring statistic, not a medical diagnosis.",
            "A high/caution flag does not establish that an injury will occur.",
            "This page does not predict selection."
        ],
        note="Use Data Integrity to verify the underlying ball-count and workload checks."
    )
    if workload.empty:
        st.info("Workload data isn't available yet — publish `cricket_bowler_workload.csv` from the notebook.")
    else:
        workload=workload.copy()
        if "start_date" in workload.columns: workload["start_date"]=pd.to_datetime(workload["start_date"],errors="coerce")
        st.markdown('<div class="ca-insight"><strong>Important:</strong> this is a workload monitor, not an injury-risk probability. Overs and delivery counts are separate quantities.</div>',unsafe_allow_html=True)
        tab1,tab2=st.tabs(["📊 Current Load","🔍 Look Up a Bowler"])
        with tab1:
            fmts=order_fmts(workload["format"].dropna().unique().tolist()) if "format" in workload.columns else []
            wfmt=st.radio("Format",fmts,horizontal=True,key="wl_fmt") if fmts else None
            window=st.radio("Show latest activity within",["6 months","1 year","2 years"],index=1,horizontal=True,key="wl_window")
            days={"6 months":183,"1 year":365,"2 years":730}[window]
            wr=workload[workload["format"]==wfmt] if wfmt else workload
            if risk_col: wr=wr[wr[risk_col].notna()]
            if wr.empty or "start_date" not in wr.columns:
                st.info("Not enough rated workload records for this view.")
            else:
                latest=wr.sort_values("start_date").groupby("bowler").tail(1); maxdate=workload["start_date"].max()
                cutoff_date=maxdate-pd.Timedelta(days=days) if pd.notna(maxdate) else None
                if cutoff_date is not None: latest=latest[latest["start_date"]>=cutoff_date]
                st.caption(f"Activity window: {cutoff_date.date() if cutoff_date is not None else '—'} → {maxdate.date() if pd.notna(maxdate) else '—'}")
                if risk_col and not latest.empty:
                    counts=latest[risk_col].value_counts().reset_index(); counts.columns=["flag","count"]
                    ch(bar_v(counts,"flag","count",f"Published workload flags — {wfmt}","#3d7bff"),320)
                    flagged=latest[latest[risk_col].astype(str).str.contains("high|caution",case=False,na=False)]
                    if flagged.empty: st.success("No high/caution workload flags in the published table.")
                    else: st.warning("Flags describe workload state only; they are not predictions of injury.")
                cols=[c for c in ["bowler","start_date","overs_bowled","balls_bowled","deliveries",ratio_col,risk_col] if c and c in latest.columns]
                if cols:
                    show=latest.sort_values(ratio_col,ascending=False)[cols] if ratio_col else latest[cols]
                    st.dataframe(show.reset_index(drop=True),hide_index=True)
        with tab2:
            bname=player_input("Bowler name",resolve("Bumrah"),key="workload_player")
            if bname and "bowler" in workload.columns:
                brow=find_rows(workload,"bowler",resolve(bname))
                if brow.empty: st.warning(f"No published workload data for '{bname}'.")
                else:
                    bf=order_fmts(brow["format"].dropna().unique().tolist()); bpick=st.radio("Format",bf,horizontal=True,key="wl_player_fmt") if len(bf)>1 else bf[0]
                    brow=brow[brow["format"]==bpick].sort_values("start_date") if "format" in brow.columns else brow
                    if ratio_col and "start_date" in brow.columns:
                        figa=px.line(brow,x="start_date",y=ratio_col,markers=True,title=f"{brow['bowler'].iloc[0]} — workload ratio ({bpick})")
                        figa.add_hline(y=1.0,line_dash="dot",line_color=MUTED,annotation_text="1.0 reference")
                        figa.update_layout(**BASE,height=340,margin=M_DEFAULT,yaxis_title=ratio_col); st.plotly_chart(figa,**CFG)
                    cols=[c for c in ["start_date","format","overs_bowled","balls_bowled","deliveries",ratio_col,risk_col] if c and c in brow.columns]
                    if cols: st.dataframe(brow.sort_values("start_date",ascending=False)[cols].reset_index(drop=True),hide_index=True)
# ══ WIN PROBABILITY ═══════════════════════════════════════════════════════════
elif section=="🎯 Win Probability":
    page_banner("🎯","Win Probability","A model estimate for one explicitly defined match context","#0d150d","#1a2a18","#3a7a54")
    ratings=load_team_ratings(); results_wp=load_match_results()
    prediction_context_box(
        "Match win probability",
        "Model-estimated probability of Team A winning the supplied match",
        "The supplied match context",
        cutoff=infer_cutoff(ratings,results_wp),
        scope=f"{GENDER_PICK} • selected format • teams • optional venue/toss",
        assumptions=[
            "Team A, Team B and format are fixed inputs.",
            "Venue is used when supplied and supported by loaded historical data.",
            "An unknown toss remains unknown; it is not invented.",
            "The output is a model probability, not a certainty.",
            "Small historical samples can make the estimate unstable."
        ],
        note="Changing format, gender, teams, venue or toss context can change the result."
    )
    if ratings.empty or results_wp.empty or "elo" not in ratings.columns:
        st.info("Win-probability data isn't available yet — publish team ratings and match-result files from the notebook.")
    else:
        rg=ratings[ratings["gender"]==GENDER] if "gender" in ratings.columns else ratings
        fmts=order_fmts(rg["format"].dropna().unique().tolist())
        if not fmts: st.info(f"No {GENDER_PICK.lower()} team ratings available.")
        else:
            wp_fmt=st.radio("Format",fmts,horizontal=True,key="wp_fmt")
            pool=rg[(rg["format"]==wp_fmt)&(rg["matches_played"]>=5)].sort_values("elo",ascending=False)
            if wp_fmt in INTERNATIONAL_FORMATS: pool=pool[pool["team"].apply(is_real_country)]
            teams=pool["team"].tolist()
            if len(teams)<2: st.info("Not enough rated teams in this format.")
            else:
                c1,c2=st.columns(2); team_a=c1.selectbox("Team A",teams,index=0,key="wp_team_a"); team_b=c2.selectbox("Team B",teams,index=1,key="wp_team_b")
                if "venue" in results_wp.columns:
                    vv=results_wp.loc[results_wp["format"].eq(wp_fmt),"venue"].dropna().astype(str).unique().tolist() if "format" in results_wp.columns else []
                    venue_opts=["No venue / neutral"]+sorted(vv)
                else: venue_opts=["No venue / neutral"]
                venue=st.selectbox("Venue",venue_opts,key="wp_venue")
                toss_pick=st.radio("Toss winner",["Unknown / doesn't matter",team_a,team_b],horizontal=True,key="wp_toss")
                toss_dec=None
                if toss_pick!="Unknown / doesn't matter": toss_dec=st.radio("Toss decision",["bat","field"],horizontal=True,key="wp_toss_dec")
                if team_a==team_b: st.warning("Pick two different teams.")
                else:
                    res=predict_match_wp(team_a,team_b,wp_fmt,GENDER,ratings,results_wp,
                                         toss_winner=None if toss_pick.startswith("Unknown") else toss_pick,toss_decision=toss_dec,
                                         venue=None if venue.startswith("No venue") else venue)
                    pa=round(res["prob"]*100,1); pb=round(100-pa,1)
                    st.markdown(f"### {team_a} **{pa}%**  vs  {team_b} **{pb}%**")
                    fig=go.Figure(go.Bar(x=[pa,pb],y=[team_a,team_b],orientation="h",marker_color=[FC.get(wp_fmt,ACCENT2),ACCENT],text=[f"{pa}%",f"{pb}%"],textposition="outside"))
                    fig.update_layout(**BASE,height=220,showlegend=False,margin=dict(l=20,r=60,t=20,b=20)); fig.update_xaxes(range=[0,105]); st.plotly_chart(fig,**CFG)
                    tbl=pd.DataFrame({"Input / evidence":["Elo rating","Recent form","Head-to-head","Matches in rating history","Venue context"],
                                      team_a:[f"{res['elo_a']:.0f}",f"{res['form_a']*100:.0f}%",f"{res['h2h_a']} of {res['h2h_n']}",res["n_a"],res["venue_note"]],
                                      team_b:[f"{res['elo_b']:.0f}",f"{res['form_b']*100:.0f}%",f"{res['h2h_n']-res['h2h_a']} of {res['h2h_n']}",res["n_b"],"Same supplied context"]})
                    st.dataframe(tbl,hide_index=True); st.caption(f"Model mode: {res['mode']} • {res['venue_note']}")
                    if min(res["n_a"],res["n_b"])<15: st.warning("At least one team has fewer than 15 rated matches; the estimate may be unstable.")
# ══ PREDICTION GUIDE ═══════════════════════════════════════════════════════════
elif section=="🧭 Prediction Guide":
    page_banner("🧭","Prediction Guide","What every number means before you use it","#0b1020","#18264a","#3d7bff")
    st.markdown("""
    <div class="ca-section-card">
      <h3 style="margin-top:0">The dashboard's prediction contract</h3>
      <p style="color:var(--subtle);line-height:1.7">
      A prediction is only meaningful when its <b>target, time horizon, data cutoff, population and assumptions</b> are visible.
      </p>
    </div>
    """,unsafe_allow_html=True)
    rows=[
        ["Projected runs","Batter's total runs in the published future season/window","Future season/window","Selected format + gender + qualified active batters","Not a next-match score"],
        ["Win probability","Model-estimated probability Team A wins","Supplied match context","Selected teams + format + optional venue/toss","Not a certainty"],
        ["Bowler workload","Published recent bowling-load statistic","Notebook-defined recent window","Selected format + gender + sufficient history","Not an injury diagnosis or selection forecast"],
        ["Player Score","0–100 descriptive percentile-style score","Current published data","Same format/gender qualified pool","Not a future-performance probability"],
        ["Form Rating","Recent performance relative to career reference","Published recent form window","Selected format/gender","Not a guarantee of next-match performance"]
    ]
    st.dataframe(pd.DataFrame(rows,columns=["Metric","What it measures","Time horizon","Population","What it does NOT mean"]),hide_index=True)
    st.markdown("### 🔬 Data provenance")
    cutoff=infer_cutoff(bat_yr,bowl_yr,bat_fmt,bowl_fmt,load_match_results(),load_player_forecast(),load_bowler_workload(),load_team_ratings())
    metrics({"Published cutoff":str(cutoff.date()) if cutoff is not None else "Not available","Gender pool":GENDER_PICK,"Formats loaded":len(ALL_FMT_G),
             "Prediction tables loaded":sum(not d.empty for d in [load_player_forecast(),load_bowler_workload(),load_team_ratings()])})
    with st.expander("⚠️ Interpretation rules"):
        st.markdown("""
        - **Projected runs are totals**, not next-match scores.
        - **A workload flag is not an injury probability.**
        - **Win probability is conditional on the supplied match context.**
        - **Unknown toss is not a guessed toss.**
        - **Player Score is descriptive, not predictive.**
        - **Held-out validation must be separated from training data.**
        - **A prediction without a visible cutoff and horizon is incomplete.**
        """)
# ══ MODEL ACCURACY ════════════════════════════════════════════════════════════
elif section=="🧪 Model Accuracy":
    page_banner("🧪","Model Accuracy","How good are the predictions — measured on matches the models never saw","#0a0d14","#141c2e","#8a95a8")
    mm = load_model_metrics(); wpt = load_win_prob_test()
    if mm.empty and wpt.empty:
        st.info("Model metrics aren't available yet — this page reads `cricket_model_metrics.csv` and `cricket_win_prob_test.csv` (notebook Step 17).")
    else:
        st.markdown('<div class="ca-insight"><strong>Evaluation uses the held-out future period defined by the notebook.</strong> '
                    'The test rows are not used to fit the evaluated model. For run forecasts this is a future-period test, '
                    'not a claim that the model has never seen the player before. Baseline comparisons are shown alongside model error.</div>', unsafe_allow_html=True)

        st.markdown("#### 🎯 Win-probability model")
        acc = mval(mm,"win_probability_best","Accuracy"); auc = mval(mm,"win_probability_best","AUC")
        base_elo = mval(mm,"win_probability_baseline_higher_elo","Accuracy")
        if acc is not None:
            metrics({"Accuracy (best model)": f"{acc*100:.1f}%", "'Higher Elo wins' baseline": f"{base_elo*100:.1f}%" if base_elo is not None else "—",
                     "AUC (0.5 = coin flip)": f"{auc:.3f}" if auc is not None else "—"})
            if base_elo is not None:
                if acc > base_elo: st.success(f"✅ Beats the simple 'higher-Elo-wins' rule by {(acc-base_elo)*100:.1f} percentage points.")
                else: st.warning("⚠️ Not beating the simple 'higher-Elo-wins' rule on this test set — the extra features add little here.")
            pv = mm[mm["model"].astype(str).str.startswith("win_probability") & (mm["metric"]!="")].pivot_table(index="model", columns="metric", values="value")
            if not pv.empty:
                pv.index = [i.replace("win_probability_","").replace("_"," ").title() for i in pv.index]
                with st.expander("📋 Full metrics table (lower is better for LogLoss and Brier)"):
                    st.dataframe(pv.round(3))

        if not wpt.empty and {"predicted_proba","actual"}.issubset(wpt.columns):
            d = wpt.dropna(subset=["predicted_proba","actual"]).copy()
            d["bin"] = pd.cut(d["predicted_proba"], bins=np.linspace(0,1,11), include_lowest=True)
            cal = d.groupby("bin", observed=True).agg(pred=("predicted_proba","mean"), obs=("actual","mean"), n=("actual","size")).reset_index()
            figc = go.Figure()
            figc.add_trace(go.Scatter(x=[0,1], y=[0,1], mode="lines", name="Perfectly calibrated", line=dict(color=MUTED, dash="dash")))
            figc.add_trace(go.Scatter(x=cal["pred"], y=cal["obs"], mode="lines+markers", name="Model",
                                      line=dict(color=ACCENT, width=3), marker=dict(size=cal["n"].clip(upper=400)/20+6),
                                      customdata=cal["n"], hovertemplate="Predicted %{x:.0%}<br>Actually won %{y:.0%}<br>%{customdata} matches<extra></extra>"))
            figc.update_layout(**BASE, height=380, title="Calibration — when it says 70%, does the team win ~70% of the time?",
                               xaxis_title="Predicted win probability", yaxis_title="Share that actually won", margin=dict(l=50,r=20,t=48,b=50))
            figc.update_xaxes(range=[0,1], tickformat=".0%"); figc.update_yaxes(range=[0,1], tickformat=".0%")
            st.plotly_chart(figc, **CFG)
            st.caption("Points hugging the dashed diagonal mean the percentages can be taken at face value.")

            if "format" in d.columns:
                d["hit"] = ((d["predicted_proba"]>0.5) == (d["actual"]==1))
                pf_acc = d.groupby("format").agg(accuracy=("hit","mean"), matches=("hit","size")).reset_index()
                pf_acc["accuracy"] = (pf_acc["accuracy"]*100).round(1)
                pf_acc = pf_acc.set_index("format").loc[order_fmts(pf_acc["format"].tolist())].reset_index()
                figf = px.bar(pf_acc, x="format", y="accuracy", text="accuracy", color="format", color_discrete_map=FC,
                              title="Accuracy by competition on the test matches")
                figf.update_traces(textposition="outside", textfont=dict(color=TEXT), customdata=pf_acc["matches"],
                                   hovertemplate="%{x}: %{y}% over %{customdata} matches<extra></extra>")
                figf.add_hline(y=50, line_dash="dot", line_color=MUTED, annotation_text="coin flip", annotation_font=dict(size=10,color=MUTED))
                figf.update_layout(**BASE, height=360, showlegend=False, margin=M_BARV)
                figf.update_yaxes(range=[0,100], title="Accuracy %")
                st.plotly_chart(figf, **CFG)
                st.caption("T20 leagues sit close to 50% — the sport is genuinely that unpredictable. Internationals are more predictable because team strength differs more.")

        st.markdown("#### 🔮 Run-forecast model")
        m_mae, n_mae, r_mae = mval(mm,"run_forecast_rf","MAE"), mval(mm,"run_forecast_naive","MAE"), mval(mm,"run_forecast_roll3","MAE")
        if m_mae is not None:
            figm = go.Figure(go.Bar(x=["Model","'Same as last year'","'3-season average'"], y=[m_mae, n_mae or 0, r_mae or 0],
                                    marker_color=[ACCENT, MUTED, MUTED], text=[f"{v:.1f}" for v in [m_mae, n_mae or 0, r_mae or 0]],
                                    textposition="outside", textfont=dict(color=TEXT)))
            figm.update_layout(**BASE, height=320, title="Average error per player-season, in runs (lower is better)", showlegend=False, margin=M_BARV)
            st.plotly_chart(figm, **CFG)
            base_best = min([x for x in (n_mae, r_mae) if x is not None], default=None)
            if base_best is not None:
                if m_mae < base_best: st.success(f"✅ The model is {base_best-m_mae:.1f} runs more accurate than the best baseline.")
                else: st.warning("⚠️ The model is not beating a simple baseline on the held-out season — projections should be read as rough.")
        else:
            st.caption("Run-forecast metrics aren't in the metrics file yet.")

# ══ DATA INTEGRITY ════════════════════════════════════════════════════════════
elif section=="🛡️ Data Integrity":
    page_banner("🛡️","Data Integrity","Live checks on the CSV tables produced by the current Cricsheet pipeline","#0a1510","#122a1e","#3a7a54")
    rep = load_integrity_report()
    CHECK_INFO = {
        "duplicate_batting_rows":("Duplicate batting rows","Same batter listed twice in one innings — would double their runs.",True),
        "duplicate_bowling_rows":("Duplicate bowling rows","Same bowler listed twice in one innings — would double their wickets.",True),
        "impossible_run_rate_rows":("Impossible run rates","More than 6 runs per ball faced in an innings.",True),
        "innings_over_400_runs":("Innings over 400","Above the all-time record — means two innings were added together.",True),
        "bowling_innings_over_10_wkts":("Bowling innings over 10 wickets","Impossible in one innings — same 'added together' bug.",True),
        "ducks_not_dismissed":("Ducks that weren't out","A duck needs a dismissal — checks the dismissal logic.",True),
        "extreme_strike_rate_innings":("Extreme strike-rate innings","Statistical outliers (4+ standard deviations). Often real — e.g. 20 off 4 balls — so this is for review, not an error.",False),
    }
    if rep.empty or not {"check","count"}.issubset(rep.columns):
        st.info("The current pipeline does not publish a separate integrity-report CSV. The live checks below are run directly on the same CSV tables this dashboard loads.")
    else:
        rows = []
        for _, r in rep.iterrows():
            label, why, hard = CHECK_INFO.get(r["check"], (str(r["check"]).replace("_"," ").title(), "", True))
            n = int(r["count"])
            status = "✅ OK" if n==0 else ("⚠️ Error" if hard else "ℹ️ Review")
            rows.append({"Check":label, "Found":n, "Status":status, "What it means":why, "_hard":hard})
        out = pd.DataFrame(rows)
        hard_fail = out[(out["_hard"]) & (out["Found"]>0)]
        if hard_fail.empty: st.success("✅ Every hard integrity check passed — no double-counted innings or impossible numbers in the published data.")
        else: st.error(f"⚠️ {len(hard_fail)} check(s) found problems in the published data — see below.")
        st.dataframe(out.drop(columns="_hard"), hide_index=True)

    st.markdown("#### 🔁 Live re-check of the files this app actually loaded")
    st.caption("Same tests, run right now on the CSVs the dashboard is reading — so you know the numbers on screen match what the notebook audited.")
    live = {}
    if not bat_inn.empty and {"match_id","innings","striker"}.issubset(bat_inn.columns):
        live["duplicate_batting_rows"] = int((bat_inn.groupby(["match_id","innings","striker"]).size()>1).sum())
        if {"runs","balls_faced"}.issubset(bat_inn.columns):
            live["impossible_run_rate_rows"] = int((bat_inn["runs"] > bat_inn["balls_faced"]*6).sum())
            live["innings_over_400_runs"] = int((bat_inn["runs"]>400).sum())
        if {"is_duck","dismissed"}.issubset(bat_inn.columns):
            live["ducks_not_dismissed"] = int(((bat_inn["is_duck"]==1)&(bat_inn["dismissed"]==0)).sum())
    if not bowl_inn.empty and {"match_id","innings","bowler"}.issubset(bowl_inn.columns):
        live["duplicate_bowling_rows"] = int((bowl_inn.groupby(["match_id","innings","bowler"]).size()>1).sum())
        if "wickets" in bowl_inn.columns:
            live["bowling_innings_over_10_wkts"] = int((bowl_inn["wickets"]>10).sum())
    if not live:
        st.info("Innings files aren't loaded, so a live re-check isn't possible.")
    else:
        lrows = [{"Check":CHECK_INFO.get(k,(k,"",True))[0], "Found now":v, "Status":"✅ OK" if v==0 else "⚠️ Error"} for k,v in live.items()]
        st.dataframe(pd.DataFrame(lrows), hide_index=True)
        if all(v==0 for v in live.values()):
            st.caption(f"Checked {len(bat_inn):,} batting innings and {len(bowl_inn):,} bowling innings.")

    st.markdown("#### 🌐 International coverage-gap report")
    gaps = load_coverage_gaps()
    if gaps.empty:
        st.caption("No published coverage-gap rows are available. The pipeline cross-checks established international players against Wikipedia and Cricsheet's documented missing-match list.")
    else:
        show = gaps.copy()
        if "flagged" in show.columns:
            show = show[show["flagged"] == True].copy()
        cols = [c for c in ["player","format","cricsheet_matches","wiki_matches","gap_matches","gap_pct","documented_missing_candidates","possible_name_fragments"] if c in show.columns]
        if show.empty:
            st.success("✅ No international player/format coverage gaps crossed the pipeline's flag threshold.")
        elif cols:
            st.warning(f"{len(show):,} player/format row(s) are flagged as potentially under-covered. This is a coverage warning, not fabricated missing data.")
            st.dataframe(show[cols].sort_values("gap_pct", ascending=False).reset_index(drop=True), hide_index=True)
            st.caption("The pipeline does not invent missing matches. It reports the tracked Cricsheet total alongside the external reference and documented missing-match candidates.")

# ══ PLAYER SEARCH ═════════════════════════════════════════════════════════════
elif section=="🔍 Player Search":
    if st.session_state.get("ps_name","") and "ps_input" not in st.session_state:
        st.session_state["ps_input"] = st.session_state["ps_name"]
    st.session_state["ps_name"] = ""
    fmt_pills="".join([
        f'<span style="background:{FORMAT_META.get(f,("","#00e5a0",""))[1]}18;color:{FORMAT_META.get(f,("","#00e5a0",""))[1]};border:1px solid {FORMAT_META.get(f,("","#00e5a0",""))[1]}44;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700">'
        f'{FORMAT_META.get(f,("🏏","",""))[0]} {f}</span>' for f in ALL_FMT])
    chips=[("Babar","#d98e2b"),("Kohli","#3a7a54"),("Bumrah","#8a95a8"),("Smriti","#b2557a"),("Shaheen","#ff6a2e"),("Maxwell","#3d7bff")]
    chip_html="".join([f'<span style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);color:{c};padding:3px 12px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap">{n}</span>' for n,c in chips])
    st.markdown(f"""<div class="ca-fade" style="background:linear-gradient(160deg,#080c14,#0c1628,#080c14);
      border-radius:14px;padding:24px 28px 20px;margin-bottom:20px;border:1px solid var(--border);
      position:relative;overflow:hidden">
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,106,46,.04) 39px,rgba(255,106,46,.04) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,106,46,.04) 39px,rgba(255,106,46,.04) 40px);pointer-events:none"></div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">{fmt_pills}</div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <span style="font-size:11px;color:var(--muted);font-weight:600;white-space:nowrap">Quick search →</span>
        {chip_html}
      </div>
      <p style="color:var(--muted);font-size:12px;margin:10px 0 0">Search any player — men's or women's — across all formats · Ball-by-ball stats · Wikipedia profiles</p>
    </div>""", unsafe_allow_html=True)

    name=st.text_input("",placeholder="🔍  Player name — e.g. Babar, Kohli, Smriti, Shaheen...",
                       label_visibility="collapsed",key="ps_input")
    name = st.session_state.get("ps_input","") or ""
    if name:
        sname=resolve(name)
        ab_rows=find_rows(bat_fmt,"striker",sname)
        aw_rows=find_rows(bowl_fmt,"bowler",sname)
        ab=ab_rows["format"].unique().tolist() if not ab_rows.empty else []
        aw=aw_rows["format"].unique().tolist() if not aw_rows.empty else []
        avl=order_fmts(set(ab+aw))
        avl=filter_valid_formats(sname, avl)
        if not avl:
            import difflib
            close = difflib.get_close_matches(name, ALL_PLAYER_NAMES, n=5, cutoff=0.5)
            substr = [n for n in ALL_PLAYER_NAMES if name.lower() in n.lower()][:5]
            suggestions = list(dict.fromkeys(close + substr))
            if suggestions:
                st.warning(f"No exact match for '{name}'. Did you mean one of these?")
                for s in suggestions:
                    if st.button(s, key=f"suggest_{s}"):
                        # ps_input can't be set after its widget exists; "ps_name" is copied into it before the widget is created.
                        st.session_state["ps_name"] = s
                        if "ps_input" in st.session_state:
                            del st.session_state["ps_input"]
                        st.rerun()
            else:
                st.error(f"No data found for '{name}', and no similar name exists anywhere in the dataset. "
                         f"This most likely means Cricsheet doesn't have this player's match data yet "
                         f"(common for very recent debuts) — not a search/spelling issue. "
                         f"You can add their stats manually via manual_batting.csv / manual_bowling.csv "
                         f"in the repo until Cricsheet catches up.")
            st.stop()
        fmt=st.radio("📋 Format",avl,horizontal=True)
        clr=FC.get(fmt,"#3d7bff")
        bat=find_rows(bat_fmt[bat_fmt["format"]==fmt],"striker",sname)
        bowl=find_rows(bowl_fmt[bowl_fmt["format"]==fmt],"bowler",sname)
        display_name=bat["striker"].iloc[0] if len(bat)>0 else (bowl["bowler"].iloc[0] if len(bowl)>0 else sname)
        show_player_card(display_name,name,fmt)

        lu=get_last_updated()
        if lu:
            st.markdown(f"""<div style="background:rgba(61,123,255,.06);border:1px solid rgba(61,123,255,.2);
              border-radius:8px;padding:8px 14px;margin:0 0 14px;display:flex;align-items:center;gap:8px">
              <span>✅</span>
              <span style="font-size:11px;color:#00e5a0">Data last updated: <strong>{lu}</strong> — auto-updated daily from Cricsheet.</span></div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style="background:rgba(255,106,46,.07);border:1px solid rgba(255,106,46,.25);
              border-radius:8px;padding:8px 14px;margin:0 0 14px;display:flex;align-items:center;gap:8px">
              <span>⚠️</span>
              <span style="font-size:11px;color:#fbbf24">Stats reflect Cricsheet's latest data. Very recent matches (last 2-3 days) may not yet be included.</span>
            </div>""", unsafe_allow_html=True)
        st.caption("ℹ️ Stats reflect the eight competitions actually downloaded and processed by the current pipeline. Cricsheet is a community-maintained "
                   "open archive and doesn't have complete coverage of every officially recognized match, especially "
                   "older ones — so totals here may be lower than official career records for veteran players.")

        if len(bat)==0 and len(bowl)==0:
            st.warning(f"No {fmt} data for '{display_name}'.")
        else:
            tab_labels=[]
            if len(bat)>0: tab_labels.append("🏏 Batting")
            if len(bowl)>0: tab_labels.append("🎳 Bowling")
            if len(bat)>0 or len(bowl)>0: tab_labels.append("📈 Charts")
            tabs=st.tabs(tab_labels); ti=0

            if len(bat)>0:
                with tabs[ti]:
                    p=bat.sort_values("runs",ascending=False).iloc[0]
                    gaps=load_coverage_gaps()
                    if not gaps.empty and "flagged" in gaps.columns:
                        grow=gaps[(gaps["player"]==p.get("striker",display_name)) & (gaps["format"]==fmt) & (gaps["flagged"]==True)]
                        if not grow.empty:
                            g=grow.iloc[0]
                            documented = int(g["documented_missing_candidates"]) if pd.notna(g.get("documented_missing_candidates")) else 0
                            fragments = g.get("possible_name_fragments", "") or ""
                            documented_note = (
                                f" Cricsheet's own published missing-matches list includes {documented} {fmt} fixture(s) "
                                f"involving this team during their playing career — likely explains some or all of this gap."
                                if documented > 0 else
                                " This is a known Cricsheet coverage gap, not a stale cache."
                            )
                            fragment_note = (
                                f"<br>🔎 <strong>Possible fix, not a real gap:</strong> found similarly-named row(s) in the raw "
                                f"data that may be this player recorded under a different spelling in a specific match — "
                                f"{fragments}. Verify and add to name_aliases.csv to merge permanently."
                                if fragments else ""
                            )
                            st.markdown(f"""<div style="background:rgba(255,106,46,.08);border:1px solid rgba(255,106,46,.3);
                              border-radius:8px;padding:8px 14px;margin:0 0 10px;font-size:12px;color:#fbbf24">
                              ⚠️ <strong>Official record (Wikipedia): {int(g['wiki_matches'])} {fmt} matches
                              {(', ' + format(int(g['wiki_runs']), ',') + ' runs') if pd.notna(g.get('wiki_runs')) else ''}</strong>
                              — this app currently tracks {int(g['cricsheet_matches'])} from Cricsheet's ball-by-ball archive
                              ({abs(g['gap_pct']):.1f}% short).{documented_note}{fragment_note}</div>""",
                              unsafe_allow_html=True)

                    wiki_card = get_wiki(display_name, name)
                    cs = (wiki_card or {}).get("career_stats", {}).get(fmt)

                    yrs = bat_yr[(bat_yr["format"]==fmt) & (bat_yr["striker"]==p.get("striker",display_name))]["year"] \
                          if not bat_yr.empty and "striker" in bat_yr.columns else pd.Series(dtype=float)
                    is_collision, collision_note = check_name_collision(wiki_card, fmt, yrs)

                    if is_collision:
                        st.info(f"No verified {fmt} record available for this player.")
                    else:
                        use_official = cs and cs.get("matches") and cs["matches"] > int(p["matches"])
                        if use_official:
                            disp_matches = cs["matches"]
                            disp_runs = cs["runs"] if cs.get("runs") is not None else int(p["runs"])
                            disp_avg = cs["average"] if cs.get("average") is not None else p["average"]
                            disp_100s = cs["hundreds"] if cs.get("hundreds") is not None else \
                                (int(p["hundreds"]) if "hundreds" in p.index and pd.notna(p.get("hundreds")) else "—")
                            st.caption(f"📖 Overall record includes {cs['matches'] - int(p['matches'])} match(es) from "
                                       f"before Cricsheet's ball-by-ball coverage begins for this player — Matches/Runs/"
                                       f"Average/100s below are the full official career total (Wikipedia). Strike rate, "
                                       f"boundary breakdown, and charts further down only reflect the {int(p['matches'])} "
                                       f"match(es) Cricsheet has ball-by-ball detail for.")
                        else:
                            disp_matches = int(p["matches"])
                            disp_runs = int(p["runs"])
                            disp_avg = p["average"]
                            disp_100s = int(p["hundreds"]) if "hundreds" in p.index and pd.notna(p.get("hundreds")) else "—"

                        # Recomputed from the per-innings file (one row per match+innings, so Test highest score is correct)
                        _innings = bat_inn[(bat_inn["striker"]==p["striker"]) & (bat_inn["format"]==fmt)] \
                                   if not bat_inn.empty and "striker" in bat_inn.columns else pd.DataFrame()

                        if not _innings.empty and {"fours","sixes","balls_faced","dismissed"}.issubset(_innings.columns):
                            live_fours = int(_innings["fours"].sum())
                            live_sixes = int(_innings["sixes"].sum())
                            live_balls = int(_innings["balls_faced"].sum())
                            live_runs = int(_innings["runs"].sum())
                            live_dismissals = int(_innings["dismissed"].sum())
                            live_sr = round((live_runs/live_balls)*100, 2) if live_balls else p["strike_rate"]
                            live_boundary_pct = round(((live_fours+live_sixes)/live_balls)*100, 2) if live_balls else p["boundary_pct"]
                        else:
                            live_fours, live_sixes = int(p["fours"]), int(p["sixes"])
                            live_sr, live_dismissals = p["strike_rate"], int(p["dismissals"])
                            live_boundary_pct = p["boundary_pct"]

                        metrics({"Matches":disp_matches,"Runs":f"{disp_runs:,}","Average":disp_avg})
                        metrics({"Strike Rate":live_sr,"4s":live_fours,"6s":live_sixes})
                        metrics({"Dismissals":live_dismissals,"Dot Ball %":f"{p['dot_pct']}%","Boundary %":f"{live_boundary_pct}%"})
                        h100=disp_100s

                        if not _innings.empty and "runs" in _innings.columns:
                            hs = int(_innings["runs"].max())
                            h50 = int(((_innings["runs"] >= 50) & (_innings["runs"] < 100)).sum())
                            dk = int(((_innings["runs"] == 0) & (_innings["dismissed"]==1)).sum()) if "dismissed" in _innings.columns else int((_innings["runs"] == 0).sum())
                        else:
                            h50=int(p["fifties"]) if "fifties" in p.index and pd.notna(p.get("fifties")) else "—"
                            hs=int(p["highest"]) if "highest" in p.index and pd.notna(p.get("highest")) else "—"
                            dk=int(p["ducks"]) if "ducks" in p.index and pd.notna(p.get("ducks")) else "—"

                        if use_official and cs.get("top_score") is not None and isinstance(hs, int):
                            if cs["top_score"] > hs:
                                hs = int(cs["top_score"])

                        ps_=round(float(p["player_score"]),1) if "player_score" in p.index and pd.notna(p.get("player_score")) else "—"
                        metrics({"100s":h100,"50s":h50,"Highest":hs,"Ducks":dk,"Player Score":ps_})
                        st.caption("Player Score is a 0–100 percentile blend ranked inside this format and men's/women's pool "
                                   "(50 = typical qualified player, 90+ = elite). Only comparable within the same format.")
                        _ft = form_label_text(bat_form, "striker", p["striker"], fmt)
                        if _ft: st.markdown(_ft)
                        fr=int(p["fours"])*4; sr_=int(p["sixes"])*6; or_=max(0,int(p["runs"])-fr-sr_)
                        ch(donut(["Fours","Sixes","Other"],[fr,sr_,or_],[clr,"#d63031","#636e72"],"Scoring Breakdown"),300)

                        with st.expander("🔍 Verify this player's raw match count (bypasses all display logic)"):
                            if not bat_inn.empty and "striker" in bat_inn.columns:
                                _verify_name = p["striker"]
                                raw_rows = bat_inn[(bat_inn["striker"]==_verify_name) & (bat_inn["format"]==fmt)]
                                raw_match_count = raw_rows["match_id"].nunique()
                                st.write(f"**Independently counted matches in `cricket_bat_innings.csv` for {_verify_name} ({fmt}): {raw_match_count}**")
                                st.write(f"**Matches shown in the card above: {int(p['matches'])}**")
                                if raw_match_count == int(p["matches"]):
                                    st.success("✅ These match exactly — the card is correctly displaying everything "
                                               "that exists in the CSV. If this number is lower than the player's real "
                                               "career total, that's Cricsheet's own data coverage, not an app bug.")
                                else:
                                    st.error(f"⚠️ These DON'T match ({raw_match_count} vs {int(p['matches'])}) — "
                                             f"this is a genuine display/aggregation bug, please report this exact "
                                             f"player name and both numbers.")
                                if raw_match_count > 0:
                                    dates = pd.to_datetime(raw_rows["start_date"])
                                    st.caption(f"Date range of matches found: {dates.min().date()} to {dates.max().date()}")
                            else:
                                st.warning("Raw innings data not available to verify against.")
                ti+=1
            if len(bowl)>0:
                with tabs[ti]:
                    p2=bowl.sort_values("wickets",ascending=False).iloc[0]
                    wiki_card2 = get_wiki(display_name, name)
                    cs2 = (wiki_card2 or {}).get("career_stats", {}).get(fmt)

                    yrs2 = bowl_yr[(bowl_yr["format"]==fmt) & (bowl_yr["bowler"]==p2.get("bowler",display_name))]["year"] \
                           if not bowl_yr.empty and "bowler" in bowl_yr.columns else pd.Series(dtype=float)
                    is_collision2, collision_note2 = check_name_collision(wiki_card2, fmt, yrs2)

                    if is_collision2:
                        st.info(f"No verified {fmt} record available for this player.")
                    else:
                        use_official2 = cs2 and cs2.get("wickets") and cs2.get("matches") and cs2["matches"] > int(p2["matches"])
                        if use_official2:
                            disp_matches2 = cs2["matches"]
                            disp_wkts = cs2["wickets"]
                            disp_avg2 = cs2["bowl_average"] if cs2.get("bowl_average") is not None else p2["average"]
                            disp_bb = cs2["best_bowling"] if cs2.get("best_bowling") else p2.get("best_bowling","—")
                            st.caption(f"📖 Overall record includes {cs2['matches'] - int(p2['matches'])} match(es) from "
                                       f"before Cricsheet's ball-by-ball coverage begins for this player — Matches/Wickets/"
                                       f"Average/Best Bowling below are the full official career total (Wikipedia). Economy "
                                       f"and dot % further down only reflect the {int(p2['matches'])} match(es) Cricsheet "
                                       f"has ball-by-ball detail for.")
                        else:
                            disp_matches2 = int(p2["matches"])
                            disp_wkts = int(p2["wickets"])
                            disp_avg2 = p2["average"]
                            disp_bb = p2.get("best_bowling","—") if "best_bowling" in p2.index else "—"

                        _bowl_innings = bowl_inn[(bowl_inn["bowler"]==p2["bowler"]) & (bowl_inn["format"]==fmt)] \
                                        if not bowl_inn.empty and "bowler" in bowl_inn.columns else pd.DataFrame()
                        if not _bowl_innings.empty and {"balls","runs_given","wickets","dot_balls"}.issubset(_bowl_innings.columns):
                            live_balls2 = int(_bowl_innings["balls"].sum())
                            live_runs_given = int(_bowl_innings["runs_given"].sum())
                            live_wkts2 = int(_bowl_innings["wickets"].sum())
                            live_dots = int(_bowl_innings["dot_balls"].sum())
                            live_economy = round((live_runs_given/live_balls2)*6, 2) if live_balls2 else p2["economy"]
                            live_bowl_sr = round(live_balls2/live_wkts2, 2) if live_wkts2 else p2["strike_rate"]
                            live_dot_pct = round((live_dots/live_balls2)*100, 2) if live_balls2 else p2["dot_pct"]
                        else:
                            live_economy, live_bowl_sr, live_dot_pct = p2["economy"], p2["strike_rate"], p2["dot_pct"]

                        metrics({"Matches":disp_matches2,"Wickets":disp_wkts,"Economy":live_economy})
                        metrics({"Average":disp_avg2,"Strike Rate":live_bowl_sr,"Dot %":f"{live_dot_pct}%"})
                        fw=int(p2["five_wkts"]) if "five_wkts" in p2.index and pd.notna(p2.get("five_wkts")) else "—"
                        bps=round(float(p2["player_score"]),1) if "player_score" in p2.index and pd.notna(p2.get("player_score")) else "—"
                        metrics({"5-Wkt Hauls":fw,"Best Bowling":disp_bb,"Player Score":bps})
                        _ft2 = form_label_text(bowl_form, "bowler", p2["bowler"], fmt)
                        if _ft2: st.markdown(_ft2)
                ti+=1
            with tabs[ti]:
                if len(bat)>0:
                    p=bat.sort_values("runs",ascending=False).iloc[0]; en=p["striker"]
                    by=bat_yr[(bat_yr["format"]==fmt)&(bat_yr["striker"]==en)].sort_values("year") if not bat_yr.empty else pd.DataFrame()
                    if len(by)>=1:
                        st.markdown("**🏏 Batting Trends**")
                        ch(bar_v(by,"year","runs","Runs per Year",clr))
                        if len(by)>1:
                            c1,c2=st.columns(2)
                            with c1: ch(line(by,"year","average","Batting Average",clr),260)
                            with c2: ch(line(by,"year","strike_rate","Strike Rate","#fbbf24"),260)
                        else:
                            st.caption("ℹ️ Only one season of data recorded so far — trend lines (average/strike "
                                       "rate over time) need at least two seasons to be meaningful.")
                    else:
                        st.caption("No yearly breakdown available for this player/format yet.")
                if len(bowl)>0:
                    p2=bowl.sort_values("wickets",ascending=False).iloc[0]; en2=p2["bowler"]
                    by2=bowl_yr[(bowl_yr["format"]==fmt)&(bowl_yr["bowler"]==en2)].sort_values("year") if not bowl_yr.empty else pd.DataFrame()
                    if len(by2)>=1:
                        st.markdown("**🎳 Bowling Trends**")
                        ch(bar_v(by2,"year","wickets","Wickets per Year",clr))
                        if len(by2)>1:
                            c1,c2=st.columns(2)
                            with c1: ch(line(by2,"year","economy","Economy Rate","#d63031"),260)
                            with c2: ch(line(by2,"year","average","Bowling Average","#6c5ce7"),260)
                            if "dot_pct" in by2.columns:
                                ch(line(by2,"year","dot_pct","Dot Ball % by Year","#00cec9"),240)
                        else:
                            st.caption("ℹ️ Only one season of data recorded so far — trend lines need at least "
                                       "two seasons to be meaningful.")
                    else:
                        st.caption("No yearly breakdown available for this player/format yet.")

# ══ HEAD TO HEAD ══════════════════════════════════════════════════════════════
elif section=="⚔️ Head to Head":
    page_banner("⚔️","Head to Head","Pick two players and see who dominates across formats","#1a0808","#2e1210","#3d7bff")
    c1,c2=st.columns(2)
    n1=c1.text_input("Player 1","Kohli"); n2=c2.text_input("Player 2","Babar Azam")
    fmt=st.radio("Format",ALL_FMT,horizontal=True)
    if n1 and n2:
        s1=resolve(n1); s2=resolve(n2)
        b1=find_rows(bat_fmt[bat_fmt["format"]==fmt],"striker",s1)
        b2=find_rows(bat_fmt[bat_fmt["format"]==fmt],"striker",s2)
        if len(b1)==0 or len(b2)==0:
            st.error(f"One or both players have no {fmt} batting data.")
        else:
            p1=b1.iloc[0]; p2_=b2.iloc[0]; p1n=p1["striker"]; p2n=p2_["striker"]
            cc1,cc2=st.columns(2)
            with cc1: show_player_card(p1n,n1,fmt,compact=True)
            with cc2: show_player_card(p2n,n2,fmt,compact=True)
            st.subheader(f"🏏 Batting — {fmt}")
            LABELS={"runs":"Runs","fours":"Fours","sixes":"Sixes","average":"Avg",
                    "strike_rate":"Strike Rate","dot_pct":"Dot %","boundary_pct":"Boundary %"}
            for title,ml in [("🏏 Volume",["runs","fours","sixes"]),
                              ("📈 Rates",["average","strike_rate"]),
                              ("📊 Percentages",["dot_pct","boundary_pct"])]:
                pretty=[LABELS.get(m,m) for m in ml]
                v1=[float(p1.get(m,0)) for m in ml]; v2=[float(p2_.get(m,0)) for m in ml]
                xmax=max(v1+v2)*1.22 if max(v1+v2)>0 else 10
                fig=go.Figure()
                fig.add_trace(go.Bar(name=p1n,y=pretty,x=v1,orientation="h",
                    marker=dict(color=FC["ODI"],opacity=0.9,line=dict(width=0)),
                    text=[f"{v:.1f}" for v in v1],textposition="outside",
                    textfont=dict(size=12,color=TEXT),cliponaxis=False))
                fig.add_trace(go.Bar(name=p2n,y=pretty,x=v2,orientation="h",
                    marker=dict(color=FC["Test"],opacity=0.9,line=dict(width=0)),
                    text=[f"{v:.1f}" for v in v2],textposition="outside",
                    textfont=dict(size=12,color=TEXT),cliponaxis=False))
                fig.update_layout(**BASE,barmode="group",title=title,
                                  height=max(260,len(ml)*140),
                                  margin=dict(l=20,r=110,t=48,b=8),bargap=0.25,bargroupgap=0.08)
                fig.update_yaxes(showgrid=False,tickfont=dict(size=13),title="",automargin=True)
                fig.update_xaxes(showgrid=True,gridcolor=GRID,title="",fixedrange=True,range=[0,xmax])
                st.plotly_chart(fig,**CFG)
            by1=find_rows(bat_yr[bat_yr["format"]==fmt],"striker",s1).copy() if not bat_yr.empty else pd.DataFrame()
            by2y=find_rows(bat_yr[bat_yr["format"]==fmt],"striker",s2).copy() if not bat_yr.empty else pd.DataFrame()
            if len(by1)>0 and len(by2y)>0:
                by1["player"]=p1n; by2y["player"]=p2n
                combined=pd.concat([by1,by2y]).sort_values("year")
                fy=px.line(combined,x="year",y="runs",color="player",markers=True,
                           title=f"Runs per Year — {fmt}",
                           color_discrete_map={p1n:FC["ODI"],p2n:FC["Test"]})
                fy.update_traces(line=dict(width=3),marker=dict(size=9))
                fy.update_layout(**BASE,height=360,margin=dict(l=50,r=20,t=48,b=40))
                fy.update_xaxes(title="Year",tickmode="linear",dtick=2,showgrid=True,gridcolor=GRID)
                fy.update_yaxes(title="Runs",showgrid=True,gridcolor=GRID)
                st.plotly_chart(fy,**CFG)
                fy2=px.line(combined,x="year",y="average",color="player",markers=True,
                            title=f"Batting Average — {fmt}",
                            color_discrete_map={p1n:FC["ODI"],p2n:FC["Test"]})
                fy2.update_traces(line=dict(width=3),marker=dict(size=9))
                fy2.update_layout(**BASE,height=300,margin=dict(l=50,r=20,t=48,b=40))
                fy2.update_xaxes(title="Year",tickmode="linear",dtick=2,showgrid=True,gridcolor=GRID)
                fy2.update_yaxes(title="Average",showgrid=True,gridcolor=GRID)
                st.plotly_chart(fy2,**CFG)

            st.markdown("### 🕸️ Head-to-Head Radar")
            st.markdown('<div class="ca-insight">Each axis is <strong>normalized 0–100</strong> relative to both players — so the shape shows who dominates which dimension, not raw values. A larger filled area = more rounded player.</div>', unsafe_allow_html=True)
            radar_metrics=["average","strike_rate","boundary_pct","dot_pct"]
            radar_labels=["Average","Strike Rate","Boundary %","Dot %"]
            v1_raw=[float(p1.get(m,0)) for m in radar_metrics]
            v2_raw=[float(p2_.get(m,0)) for m in radar_metrics]
            combined_max=[max(a,b,0.001) for a,b in zip(v1_raw,v2_raw)]
            v1_norm=[round(a/mx*100,1) for a,mx in zip(v1_raw,combined_max)]
            v2_norm=[round(b/mx*100,1) for b,mx in zip(v2_raw,combined_max)]
            st.plotly_chart(radar(radar_labels,v1_norm,v2_norm,p1n,p2n,FC["ODI"],FC["Test"],
                f"Batting Profile — {fmt}"),**CFG)

# ══ VS VENUE ══════════════════════════════════════════════════════════════════
elif section=="🏟️ vs Venue":
    page_banner("🏟️","Player vs Venue","How does a player perform at different grounds?","#0a1510","#122a1e","#3a7a54")
    name=player_input("Player name",resolve("Kohli")); st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        sname=resolve(name)
        src=find_rows(bat_ven,"striker",sname) if st_=="Batting" else find_rows(bowl_ven,"bowler",sname)
        if len(src)==0:
            st.error("Player not found! Try a different spelling.")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            df_v=src[src["format"]==fmt]
            if st_=="Batting":
                m=st.selectbox("Metric",["runs","average","strike_rate","fours","sixes"])
                df_top=df_v.sort_values(m,ascending=False).head(20)
                ch(bar_h(df_top,m,"venue",m,"Greens",f"{df_top['striker'].iloc[0]} — {m} by Venue ({fmt})"))
                if "innings" in df_v.columns and "average" in df_v.columns and len(df_v)>=3:
                    st.markdown("#### 📍 Consistency Map — Innings vs Average per Venue")
                    st.caption("Top-right = visits often AND scores big. Bubble size = total runs.")
                    df_sc=df_v.copy()
                    bsz=df_sc["runs"].fillna(0) if "runs" in df_sc.columns else None
                    fig_sc=px.scatter(df_sc,x="innings",y="average",text="venue",
                        size=bsz,size_max=45,color="average",color_continuous_scale="Greens",
                        title=f"Venue Consistency — {fmt}",
                        hover_data={k:True for k in ["venue","innings","runs","average","strike_rate"] if k in df_sc.columns})
                    fig_sc.update_traces(textposition="top center",textfont=dict(size=8,color=TEXT),
                        hovertemplate="<b>%{text}</b><br>Innings: %{x}<br>Avg: %{y:.1f}<extra></extra>")
                    fig_sc.update_layout(**BASE,height=460,coloraxis_showscale=False,
                        margin=dict(l=50,r=20,t=48,b=50),xaxis_title="Innings Played",yaxis_title="Batting Average")
                    fig_sc.update_xaxes(showgrid=True,gridcolor=GRID)
                    fig_sc.update_yaxes(showgrid=True,gridcolor=GRID)
                    st.plotly_chart(fig_sc,**CFG)
                st.dataframe(df_v.sort_values(m,ascending=False)[["venue","innings","runs","average","strike_rate"]].reset_index(drop=True))
            else:
                m=st.selectbox("Metric",["wickets","economy","average","dot_pct"])
                df_top=df_v.sort_values(m,ascending=False).head(20)
                ch(bar_h(df_top,m,"venue",m,"Reds",f"{df_top['bowler'].iloc[0]} — {m} by Venue ({fmt})"))
                if "innings" in df_v.columns and "economy" in df_v.columns and len(df_v)>=3:
                    st.markdown("#### 📍 Economy Map — Innings vs Economy per Venue")
                    st.caption("Bottom-right = bowls a lot AND stays economical. Bubble size = wickets.")
                    df_sc2=df_v.copy()
                    bsz2=df_sc2["wickets"].fillna(0) if "wickets" in df_sc2.columns else None
                    fig_sc2=px.scatter(df_sc2,x="innings",y="economy",text="venue",
                        size=bsz2,size_max=45,color="economy",color_continuous_scale="Reds_r",
                        title=f"Venue Economy — {fmt}",
                        hover_data={k:True for k in ["venue","innings","wickets","economy","average"] if k in df_sc2.columns})
                    fig_sc2.update_traces(textposition="top center",textfont=dict(size=8,color=TEXT),
                        hovertemplate="<b>%{text}</b><br>Innings: %{x}<br>Economy: %{y:.2f}<extra></extra>")
                    fig_sc2.update_layout(**BASE,height=460,coloraxis_showscale=False,
                        margin=dict(l=50,r=20,t=48,b=50),xaxis_title="Innings Bowled",yaxis_title="Economy Rate")
                    fig_sc2.update_xaxes(showgrid=True,gridcolor=GRID)
                    fig_sc2.update_yaxes(showgrid=True,gridcolor=GRID)
                    st.plotly_chart(fig_sc2,**CFG)
                st.dataframe(df_v.sort_values(m,ascending=False)[["venue","innings","wickets","economy","average"]].reset_index(drop=True))

# ══ VS OPPONENT ═══════════════════════════════════════════════════════════════
elif section=="🌍 vs Opponent":
    page_banner("🌍","Player vs Opponent","Find which teams a player dominates — and which trouble them","#0a1018","#121e30","#8a95a8")
    name=player_input("Player name",resolve("Kohli")); st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        sname=resolve(name)
        src=find_rows(bat_opp,"striker",sname) if st_=="Batting" else find_rows(bowl_opp,"bowler",sname)
        if len(src)==0: st.error("Player not found! Try a different spelling.")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            df_o=src[src["format"]==fmt]
            if st_=="Batting":
                m=st.selectbox("Metric",["runs","average","strike_rate","fours","sixes"])
                df_o_s=df_o.sort_values(m,ascending=False)
                ch(bar_h(df_o_s,m,"opponent",m,"Blues",f"{df_o_s['striker'].iloc[0]} — {m} vs Teams ({fmt})"))
                if "innings" in df_o.columns and "average" in df_o.columns and len(df_o)>=3:
                    st.markdown("#### 🎯 Dominance Map — Which Teams Does He Master?")
                    st.caption("Top-right = plays them often AND scores big. Bottom-left = struggles.")
                    med_avg = float(df_o["average"].median()) if "average" in df_o.columns else 0
                    med_inn = float(df_o["innings"].median()) if "innings" in df_o.columns else 0
                    fig_dom=px.scatter(df_o,x="innings",y="average",text="opponent",
                        size="runs" if "runs" in df_o.columns else None,size_max=50,
                        color="average",color_continuous_scale="Blues",
                        title=f"Batting Dominance by Opponent ({fmt})")
                    fig_dom.update_traces(textposition="top center",textfont=dict(size=9,color=TEXT),
                        hovertemplate="<b>%{text}</b><br>Innings: %{x}<br>Avg: %{y:.1f}<extra></extra>")
                    fig_dom.add_hline(y=med_avg,line_dash="dot",line_color=GRID,
                                      annotation_text="Median avg",annotation_font=dict(size=9,color=TEXT))
                    fig_dom.add_vline(x=med_inn,line_dash="dot",line_color=GRID,
                                      annotation_text="Median innings",annotation_font=dict(size=9,color=TEXT))
                    fig_dom.update_layout(**BASE,height=480,coloraxis_showscale=False,
                        margin=dict(l=50,r=20,t=48,b=50),xaxis_title="Innings Played",yaxis_title="Batting Average")
                    fig_dom.update_xaxes(showgrid=True,gridcolor=GRID)
                    fig_dom.update_yaxes(showgrid=True,gridcolor=GRID)
                    st.plotly_chart(fig_dom,**CFG)
                st.dataframe(df_o.sort_values(m,ascending=False)[["opponent","innings","runs","average","strike_rate"]].reset_index(drop=True))
            else:
                m=st.selectbox("Metric",["wickets","economy","average","dot_pct"])
                df_o_s=df_o.sort_values(m,ascending=False)
                ch(bar_h(df_o_s,m,"opponent",m,"Purples",f"{df_o_s['bowler'].iloc[0]} — {m} vs Teams ({fmt})"))
                if "innings" in df_o.columns and "economy" in df_o.columns and len(df_o)>=3:
                    st.markdown("#### 🎯 Bowling Dominance Map")
                    st.caption("Top-right = bowls them often AND takes wickets. Bottom = struggles for wickets.")
                    fig_dom2=px.scatter(df_o,x="innings",y="wickets" if "wickets" in df_o.columns else "economy",
                        text="opponent",size="wickets" if "wickets" in df_o.columns else None,size_max=50,
                        color="economy",color_continuous_scale="Purples_r",
                        title=f"Bowling Dominance by Opponent ({fmt})")
                    fig_dom2.update_traces(textposition="top center",textfont=dict(size=9,color=TEXT),
                        hovertemplate="<b>%{text}</b><br>Innings: %{x}<br>Wickets: %{y}<extra></extra>")
                    fig_dom2.update_layout(**BASE,height=480,coloraxis_showscale=False,
                        margin=dict(l=50,r=20,t=48,b=50),xaxis_title="Innings Bowled",yaxis_title="Wickets")
                    fig_dom2.update_xaxes(showgrid=True,gridcolor=GRID)
                    fig_dom2.update_yaxes(showgrid=True,gridcolor=GRID)
                    st.plotly_chart(fig_dom2,**CFG)
                st.dataframe(df_o.sort_values(m,ascending=False)[["opponent","innings","wickets","economy","average"]].reset_index(drop=True))

# ══ BATTER VS BOWLER ══════════════════════════════════════════════════════════
elif section=="🤜 Batter vs Bowler":
    page_banner("🤜","Batter vs Bowler","The ultimate matchup — who has the edge ball by ball?","#1a0a08","#2e1410","#3d7bff")
    mt=st.radio("Look up a...",["Batter","Bowler"],horizontal=True)
    st.caption("Only matchups of 10+ balls are recorded. A batter's dismissals here count only wickets credited to that bowler (run-outs excluded).")
    if mt=="Batter":
        name=player_input("Batter name",resolve("Babar Azam"),key="bvb_batter")
        if name:
            sname=resolve(name)
            src=find_rows(bvb,"striker",sname)
            if len(src)==0: st.error("Not found!")
            else:
                fmt=st.radio("Format",avail(src,"format"),horizontal=True)
                df_m=src[src["format"]==fmt]
                m=st.selectbox("Sort by",["balls_faced","runs","strike_rate","dismissals"])
                df_m=df_m.sort_values(m,ascending=False).head(20)
                ch(bar_h(df_m,m,"bowler",m,"Greens",f"Top 20 bowlers faced — {m} ({fmt})"))
                st.dataframe(df_m[["bowler","balls_faced","runs","strike_rate","dismissals"]].reset_index(drop=True))
    else:
        name=player_input("Bowler name",resolve("Shaheen"),key="bvb_bowler")
        if name:
            sname=resolve(name)
            src=find_rows(wvb,"bowler",sname)
            if len(src)==0: st.error("Not found!")
            else:
                fmt=st.radio("Format",avail(src,"format"),horizontal=True)
                df_m=src[src["format"]==fmt]
                m=st.selectbox("Sort by",["wickets","economy","dot_pct","runs_given"])
                df_m=df_m.sort_values(m,ascending=(m in ["economy","dot_pct"])).head(20)
                ch(bar_h(df_m,m,"striker",m,"Reds",f"Top 20 batters bowled to — {m} ({fmt})"))
                st.dataframe(df_m[["striker","balls_bowled","runs_given","wickets","economy"]].reset_index(drop=True))

# ══ PERFORMANCE OVER YEARS ════════════════════════════════════════════════════
elif section=="📈 Over Years":
    page_banner("📈","Performance Over Years","Track how a player has evolved season by season","#141008","#241c10","#ff6a2e")
    name=player_input("Player name",resolve("Kohli")); st_=st.radio("Type",["Batting","Bowling"],horizontal=True)
    if name:
        sname=resolve(name)
        src=find_rows(bat_yr,"striker",sname) if st_=="Batting" else find_rows(bowl_yr,"bowler",sname)
        if len(src)==0: st.error("Player not found!")
        else:
            fmt=st.radio("Format",avail(src,"format"),horizontal=True)
            by=src[src["format"]==fmt].sort_values("year"); clr=FC.get(fmt,"#00b894")
            if st_=="Batting":
                ch(bar_v(by,"year","runs","Runs per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by,"year","average","Batting Average",clr),280)
                with c2: ch(line(by,"year","strike_rate","Strike Rate","#fdcb6e"),280)
                st.dataframe(by[["year","matches","runs","average","strike_rate","fours","sixes"]].reset_index(drop=True))
            else:
                ch(bar_v(by,"year","wickets","Wickets per Year",clr))
                c1,c2=st.columns(2)
                with c1: ch(line(by,"year","economy","Economy Rate","#d63031"),280)
                with c2: ch(line(by,"year","average","Bowling Average","#6c5ce7"),280)
                if "dot_pct" in by.columns:
                    ch(line(by,"year","dot_pct","Dot Ball % by Year","#00cec9"),240)
                st.dataframe(by[["year","matches","wickets","economy","average","dot_pct","balls"]].reset_index(drop=True) if "balls" in by.columns else by[["year","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ══ LEADERBOARD ═══════════════════════════════════════════════════════════════
elif section=="🏆 Leaderboard":
    page_banner("🏆","Leaderboard","The greatest — ranked by format and stat","#1a1608","#2e2610","#ff6a2e")
    st.caption(f"Showing the {GENDER_PICK.lower()} pool — the published dataset.")
    fmt=st.radio("Format",ALL_FMT_G,horizontal=True)
    tab1,tab2=st.tabs(["🏏 Batting","🎳 Bowling"])
    with tab1:
        bs=gf(bat_fmt); bs=bs[bs["format"]==fmt]
        c1,c2=st.columns(2)
        sb=c1.selectbox("Rank by",["runs","average","strike_rate","sixes","hundreds","player_score"])
        mr=c2.slider("Min runs",0,3000,200,100); tn=st.slider("Top N",5,50,20)
        lb=bs[bs["runs"]>=mr].dropna(subset=[sb]).sort_values(sb,ascending=False).head(tn).reset_index(drop=True)
        lb.insert(0,"Rank",range(1,len(lb)+1))
        if lb.empty:
            st.info("No batters meet that minimum.")
        else:
            ch(bar_h(lb,sb,"striker",sb,"Teal",f"Top {tn} {fmt} Batters — {sb}"))
            if "runs" in lb.columns and "average" in lb.columns and len(lb)>=4:
                st.markdown("#### 💠 Runs vs Average — The Elite Quadrant")
                st.markdown('<div class="ca-insight"><strong>Top-right</strong> = high volume AND high quality. <strong>Color</strong> = strike rate. The dotted lines are median splits — names above both lines are the true greats of this format.</div>', unsafe_allow_html=True)
                med_r=float(lb["runs"].median()); med_a=float(lb["average"].median())
                fig_sc=px.scatter(lb,x="runs",y="average",text="striker",
                    color="strike_rate" if "strike_rate" in lb.columns else None,
                    color_continuous_scale="Teal",size_max=18,
                    title=f"Runs vs Average — {fmt} (Top {tn})",
                    hover_data={k:True for k in ["striker","runs","average","strike_rate","matches"] if k in lb.columns})
                fig_sc.update_traces(marker=dict(size=10,opacity=0.9,line=dict(width=1,color=BG)),
                    textposition="top center",textfont=dict(size=8,color=TEXT),
                    hovertemplate="<b>%{text}</b><br>Runs: %{x:,}<br>Avg: %{y:.1f}<extra></extra>")
                fig_sc.add_hline(y=med_a,line_dash="dot",line_color=GRID,annotation_text=f"Median avg {med_a:.0f}",annotation_font=dict(size=9,color=TEXT))
                fig_sc.add_vline(x=med_r,line_dash="dot",line_color=GRID,annotation_text=f"Median runs {med_r:.0f}",annotation_font=dict(size=9,color=TEXT))
                fig_sc.update_layout(**BASE,height=460,coloraxis_showscale=True,
                    coloraxis_colorbar=dict(title="SR",tickfont=dict(size=9)),
                    margin=dict(l=50,r=60,t=48,b=50),xaxis_title="Total Runs",yaxis_title="Batting Average")
                fig_sc.update_xaxes(showgrid=True,gridcolor=GRID)
                fig_sc.update_yaxes(showgrid=True,gridcolor=GRID)
                st.plotly_chart(fig_sc,**CFG)
            show_cols=[c for c in ["Rank","striker","matches","runs","average","strike_rate","hundreds","fifties","highest","player_score"] if c in lb.columns]
            st.dataframe(lb[show_cols].reset_index(drop=True))
    with tab2:
        ws=gf(bowl_fmt); ws=ws[ws["format"]==fmt]
        c1,c2=st.columns(2)
        sb2=c1.selectbox("Rank by",["wickets","economy","average","dot_pct","five_wkts","player_score"])
        mw=c2.slider("Min wickets",0,100,10,5); tn2=st.slider("Top N bowlers",5,50,20)
        lb2=ws[ws["wickets"]>=mw].dropna(subset=[sb2]).sort_values(sb2,ascending=(sb2 in ["economy","average"])).head(tn2).reset_index(drop=True)
        lb2.insert(0,"Rank",range(1,len(lb2)+1))
        if lb2.empty:
            st.info("No bowlers meet that minimum.")
        else:
            ch(bar_h(lb2,"wickets","bowler","economy","Sunset",f"Top {tn2} {fmt} Bowlers"))
            if "wickets" in lb2.columns and "economy" in lb2.columns and len(lb2)>=4:
                st.markdown("#### 💠 Wickets vs Economy — The Elite Quadrant")
                st.caption("Top-right = high wickets AND economical. The match-winners.")
                fig_sc2=px.scatter(lb2,x="wickets",y="economy",text="bowler",
                    color="average" if "average" in lb2.columns else None,
                    color_continuous_scale="Reds_r",
                    title=f"Wickets vs Economy — {fmt} (Top {tn2})",
                    hover_data={k:True for k in ["bowler","wickets","economy","average","matches"] if k in lb2.columns})
                fig_sc2.update_traces(marker=dict(size=10,opacity=0.9,line=dict(width=1,color=BG)),
                    textposition="top center",textfont=dict(size=8,color=TEXT),
                    hovertemplate="<b>%{text}</b><br>Wickets: %{x}<br>Economy: %{y:.2f}<extra></extra>")
                med_w=float(lb2["wickets"].median()); med_e=float(lb2["economy"].median())
                fig_sc2.add_hline(y=med_e,line_dash="dot",line_color=GRID,annotation_text=f"Median econ {med_e:.1f}",annotation_font=dict(size=9,color=TEXT))
                fig_sc2.add_vline(x=med_w,line_dash="dot",line_color=GRID,annotation_text=f"Median wkts {med_w:.0f}",annotation_font=dict(size=9,color=TEXT))
                fig_sc2.update_layout(**BASE,height=460,coloraxis_showscale=True,
                    coloraxis_colorbar=dict(title="Avg",tickfont=dict(size=9)),
                    margin=dict(l=50,r=60,t=48,b=50),xaxis_title="Total Wickets",yaxis_title="Economy Rate")
                fig_sc2.update_xaxes(showgrid=True,gridcolor=GRID)
                fig_sc2.update_yaxes(showgrid=True,gridcolor=GRID)
                st.plotly_chart(fig_sc2,**CFG)
            show_cols2=[c for c in ["Rank","bowler","matches","wickets","economy","average","five_wkts","best_bowling","player_score"] if c in lb2.columns]
            st.dataframe(lb2[show_cols2].reset_index(drop=True))

# ══ LEAGUE RECORDS ════════════════════════════════════════════════════════════
elif section=="🏅 League Records":
    page_banner("🏅","League Records","The all-time record book — one league at a time","#140c1e","#241436","#b25de0")
    if not LEAGUE_FMTS:
        st.info(f"No {GENDER_PICK.lower()} league data available — try switching men's/women's in the sidebar.")
    else:
        league = st.radio("League", LEAGUE_FMTS, horizontal=True, key="lr_league")
        icon, c1, c2 = FORMAT_META.get(league, ("🏏", ACCENT, ACCENT))
        lbs = gf(bat_fmt); lbs = lbs[lbs["format"]==league]
        lws = gf(bowl_fmt); lws = lws[lws["format"]==league]

        if lbs.empty and lws.empty:
            st.info(f"No {league} data available yet.")
        else:
            st.markdown(f"#### {icon} {league} — Headline Records")
            cards = []
            if not lbs.empty:
                top_runs = lbs.loc[lbs["runs"].idxmax()]
                top_hs   = lbs.loc[lbs["highest"].idxmax()]
                top_4s   = lbs.loc[lbs["fours"].idxmax()]
                top_6s   = lbs.loc[lbs["sixes"].idxmax()]
                cards += [
                    record_card("🏃","Most Runs", top_runs["striker"], f'{int(top_runs["runs"]):,}',
                                f'in {int(top_runs["matches"])} matches', c1),
                    record_card("💯","Highest Individual Score", top_hs["striker"], f'{top_hs["highest"]:.0f}',
                                "best single innings", c1),
                    record_card("🍀","Most Fours", top_4s["striker"], f'{int(top_4s["fours"]):,}',
                                "career 4s in this league", c1),
                    record_card("🚀","Most Sixes", top_6s["striker"], f'{int(top_6s["sixes"]):,}',
                                "career 6s in this league", c1),
                ]
            if not lws.empty:
                top_wkts = lws.loc[lws["wickets"].idxmax()]
                top_best = lws.loc[lws["best_wkts"].idxmax()] if "best_wkts" in lws.columns else None
                cards.append(record_card("🎯","Most Wickets", top_wkts["bowler"], f'{int(top_wkts["wickets"]):,}',
                                          f'in {int(top_wkts["matches"])} matches', c2))
                if top_best is not None:
                    bb = str(top_best.get("best_bowling","—")).replace(".0","")
                    cards.append(record_card("🔥","Best Bowling Figures", top_best["bowler"],
                                              bb, "single-innings haul", c2))
            record_grid(cards)

            tab1, tab2 = st.tabs(["🏏 Batting Records", "🎳 Bowling Records"])
            with tab1:
                if lbs.empty:
                    st.caption("No batting data for this league yet.")
                else:
                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        ch(bar_h(lbs.nlargest(10,"runs"),"runs","striker","runs","Blues",f"Top 10 Run Scorers — {league}"))
                        ch(bar_h(lbs.nlargest(10,"fours"),"fours","striker","fours","Teal",f"Most Fours — {league}"))
                    with bcol2:
                        ch(bar_h(lbs.nlargest(10,"highest"),"highest","striker","highest","Oranges",f"Highest Individual Scores — {league}"))
                        ch(bar_h(lbs.nlargest(10,"sixes"),"sixes","striker","sixes","Purples",f"Most Sixes — {league}"))
            with tab2:
                if lws.empty:
                    st.caption("No bowling data for this league yet.")
                else:
                    wcol1, wcol2 = st.columns(2)
                    with wcol1:
                        ch(bar_h(lws.nlargest(10,"wickets"),"wickets","bowler","wickets","Reds",f"Most Wickets — {league}"))
                    with wcol2:
                        min_ov = st.slider("Min overs (for economy record)", 5, 50, 15, key="lr_min_ov")
                        econ_pool = lws[lws["overs"]>=min_ov]
                        if not econ_pool.empty:
                            ch(bar_h(econ_pool.nsmallest(10,"economy"),
                                     "economy","bowler","economy","Greens",f"Best Economy — {league} (min {min_ov} overs)"))
                        else:
                            st.caption("No bowlers meet that overs threshold yet — lower the slider.")

# ══ SIMILAR PLAYERS ═══════════════════════════════════════════════════════════
elif section=="🤖 Similar Players":
    page_banner("🤖","Similar Players","Find cricketers whose numbers look just like your favourite's","#0a0d14","#141c2e","#8a95a8")
    st.markdown("Ranks players by **how close their stats are** (average, strike rate, boundary %, dot %, volume) "
                "to the one you pick — compared only within the **same format and men's/women's pool**, so a Test "
                "grafter is never matched with a T20 slogger.")
    st_type=st.radio("Type",["Batter","Bowler"],horizontal=True)
    name=player_input("Player name",resolve("Babar"),key="leaderboard_player")
    _sim_formats = ALL_FMT if ALL_FMT else FORMATS
    if name:
        _sn = resolve(name)
        _played = set()
        if not bat_fmt.empty and "striker" in bat_fmt.columns:
            _played |= set(find_rows(bat_fmt, "striker", _sn)["format"].dropna().unique().tolist())
        if not bowl_fmt.empty and "bowler" in bowl_fmt.columns:
            _played |= set(find_rows(bowl_fmt, "bowler", _sn)["format"].dropna().unique().tolist())
        if _played:
            _sim_formats = [f for f in _sim_formats if f in _played]
    fmt=st.radio("Format",_sim_formats,horizontal=True)
    if name:
        sname=resolve(name)
        if st_type=="Batter":
            src=find_rows(bat_sim[bat_sim["format"]==fmt],"striker",sname)
            if len(src)==0:
                has_bowl=not find_rows(bowl_sim[bowl_sim["format"]==fmt],"bowler",sname).empty
                hint=" (They appear as a Bowler — try switching to Bowler above.)" if has_bowl else ""
                st.error(f"No similarity data for '{name}' in {fmt}. Batters need 200+ runs in a format.{hint}")
            else:
                tgt_idx = src.index[0]; p = src.iloc[0]
                same = nearest_players(bat_sim, "striker", SIM_BAT_FEATS, tgt_idx, n=12)
                st.subheader(f"Players most similar to {p['striker']} in {fmt}")
                cl = int(p["cluster"]) if "cluster" in p.index and pd.notna(p["cluster"]) else -1
                st.caption(f"⭐ Player Score: {p.get('player_score','—')}" + (f" | Playing-style group #{cl}" if cl>=0 else "") +
                           f" | {len(same)} closest matches found")
                if same.empty:
                    st.info("Not enough comparable players in this pool.")
                else:
                    ch(bar_h(same,"match_pct","striker","average","Purples",f"Closest batting profiles — {fmt} (match %)"))
                    st.caption("Match % = how close the stat profile is (100 = identical). Colour = batting average.")
                    st.markdown("#### 🎴 Top Similar Players")
                    top4=same.head(4)["striker"].tolist()
                    card_cols=st.columns(min(len(top4),2))
                    for i,pname_s in enumerate(top4):
                        with card_cols[i%2]:
                            show_player_card(pname_s,pname_s,fmt,compact=True)
                    st.dataframe(same[["striker","match_pct","runs","average","strike_rate","boundary_pct","player_score"]].reset_index(drop=True))
        else:
            src=find_rows(bowl_sim[bowl_sim["format"]==fmt],"bowler",sname)
            if len(src)==0:
                has_bat=not find_rows(bat_sim[bat_sim["format"]==fmt],"striker",sname).empty
                hint=" (They appear as a Batter — try switching to Batter above.)" if has_bat else ""
                st.error(f"No similarity data for '{name}' in {fmt}. Bowlers need 20+ wickets in a format.{hint}")
            else:
                tgt_idx = src.index[0]; p = src.iloc[0]
                same = nearest_players(bowl_sim, "bowler", SIM_BOWL_FEATS, tgt_idx, n=12)
                st.subheader(f"Bowlers most similar to {p['bowler']} in {fmt}")
                cl = int(p["cluster"]) if "cluster" in p.index and pd.notna(p["cluster"]) else -1
                st.caption(f"⭐ Player Score: {p.get('player_score','—')}" + (f" | Playing-style group #{cl}" if cl>=0 else "") +
                           f" | {len(same)} closest matches found")
                if same.empty:
                    st.info("Not enough comparable players in this pool.")
                else:
                    ch(bar_h(same,"match_pct","bowler","economy","Reds",f"Closest bowling profiles — {fmt} (match %)"))
                    st.caption("Match % = how close the stat profile is (100 = identical). Colour = economy rate.")
                    top4b=same.head(4)["bowler"].tolist()
                    st.markdown("#### 🎴 Top Similar Bowlers")
                    card_cols2=st.columns(min(len(top4b),2))
                    for i,bname_s in enumerate(top4b):
                        with card_cols2[i%2]:
                            show_player_card(bname_s,bname_s,fmt,compact=True)
                    st.dataframe(same[["bowler","match_pct","wickets","economy","average","dot_pct","player_score"]].reset_index(drop=True))

# ══ FORM & RATINGS ════════════════════════════════════════════════════════════
elif section=="🔥 Form & Ratings":
    page_banner("🔥","Form & Ratings","Player form by year, who's in form right now, and percentile player scores","#1a0d08","#2e1810","#3d7bff")
    fmt=st.radio("Format",ALL_FMT_G,horizontal=True)
    tab1,tab2,tab3,tab4=st.tabs(["🔍 Player Form","🔥 Hot List","📉 Cold List","⭐ Player Scores"])

    # ── Tab 1: Player year-by-year form ──────────────────────────────────────
    with tab1:
        st.markdown("#### Year-by-year form with career reference lines")
        fname=player_input("Player name",resolve("Kohli"),key="form_player")
        ftype=st.radio("Type",["Batting","Bowling"],horizontal=True,key="form_type")
        if fname:
            fsname=resolve(fname)
            if ftype=="Batting":
                pyr=find_rows(bat_yr[bat_yr["format"]==fmt],"striker",fsname)
                if pyr.empty:
                    has_bowl=not find_rows(bowl_yr[bowl_yr["format"]==fmt],"bowler",fsname).empty
                    hint=f" (They do have **bowling** data in {fmt} — try switching to Bowling above.)" if has_bowl else ""
                    st.error(f"No {fmt} yearly batting data for '{fname}'.{hint}")
                else:
                    pyr=pyr.sort_values("year"); pname=pyr["striker"].iloc[0]
                    career=find_rows(bat_fmt[bat_fmt["format"]==fmt],"striker",fsname)
                    cavg=float(career["average"].iloc[0]) if len(career)>0 else None
                    csr=float(career["strike_rate"].iloc[0]) if len(career)>0 else None
                    latest=pyr.iloc[-1]
                    _ft=form_label_text(bat_form,"striker",pname,fmt)
                    if _ft: st.markdown(_ft)
                    metrics({"Latest Year":int(latest["year"]),"Runs":f"{int(latest['runs']):,}",
                             "Avg (latest)":round(float(latest["average"]),1),
                             "SR (latest)":round(float(latest["strike_rate"]),1),
                             "Matches":int(latest["matches"])})
                    if cavg or csr:
                        badges=""
                        if cavg: badges+=form_delta_html(float(latest["average"]),cavg,"avg",True)+" "
                        if csr: badges+=form_delta_html(float(latest["strike_rate"]),csr,"SR",True)
                        if badges.strip():
                            st.markdown(f'<div style="margin:4px 0 12px;display:flex;gap:6px;flex-wrap:wrap">{badges}</div>',unsafe_allow_html=True)
                    clr=FC.get(fmt,"#00b894")
                    ch(bar_v(pyr,"year","runs",f"{pname} — Runs per Year ({fmt})",clr))
                    c1,c2=st.columns(2)
                    fig_avg=px.line(pyr,x="year",y="average",markers=True,title=f"{pname} — Batting Average by Year")
                    fig_avg.update_traces(line=dict(color=clr,width=3),
                                          marker=dict(size=9,color=clr,line=dict(width=2,color=BG)))
                    if cavg:
                        fig_avg.add_hline(y=cavg,line_dash="dash",line_color="#fdcb6e",
                                          annotation_text=f"Career avg {cavg:.1f}",
                                          annotation_position="bottom right",
                                          annotation_font=dict(color="#fdcb6e",size=11))
                    fig_avg.update_layout(**BASE,height=300,margin=M_DEFAULT)
                    with c1: st.plotly_chart(fig_avg,**CFG)
                    fig_sr=px.line(pyr,x="year",y="strike_rate",markers=True,title=f"{pname} — Strike Rate by Year")
                    fig_sr.update_traces(line=dict(color="#fbbf24",width=3),
                                         marker=dict(size=9,color="#fbbf24",line=dict(width=2,color=BG)))
                    if csr:
                        fig_sr.add_hline(y=csr,line_dash="dash",line_color="#e17055",
                                         annotation_text=f"Career SR {csr:.1f}",
                                         annotation_position="bottom right",
                                         annotation_font=dict(color="#e17055",size=11))
                    fig_sr.update_layout(**BASE,height=300,margin=M_DEFAULT)
                    with c2: st.plotly_chart(fig_sr,**CFG)
                    fig_b=go.Figure()
                    fig_b.add_trace(go.Bar(name="4s",x=pyr["year"],y=pyr["fours"],marker_color="#00e5a0",opacity=0.85))
                    fig_b.add_trace(go.Bar(name="6s",x=pyr["year"],y=pyr["sixes"],marker_color="#d63031",opacity=0.85))
                    fig_b.update_layout(**BASE,barmode="group",title="Boundaries by Year",height=280,margin=M_BARV,bargap=0.25)
                    st.plotly_chart(fig_b,**CFG)
                    st.dataframe(pyr[["year","matches","runs","average","strike_rate","fours","sixes","dismissals"]].reset_index(drop=True))
            else:
                pyr=find_rows(bowl_yr[bowl_yr["format"]==fmt],"bowler",fsname)
                if pyr.empty:
                    has_bat=not find_rows(bat_yr[bat_yr["format"]==fmt],"striker",fsname).empty
                    hint=f" (They do have **batting** data in {fmt} — try switching to Batting above.)" if has_bat else ""
                    st.error(f"No {fmt} yearly bowling data for '{fname}'.{hint}")
                else:
                    pyr=pyr.sort_values("year"); pname=pyr["bowler"].iloc[0]
                    career=find_rows(bowl_fmt[bowl_fmt["format"]==fmt],"bowler",fsname)
                    cecon=float(career["economy"].iloc[0]) if len(career)>0 else None
                    cavg=float(career["average"].iloc[0]) if len(career)>0 else None
                    latest=pyr.iloc[-1]
                    _ft=form_label_text(bowl_form,"bowler",pname,fmt)
                    if _ft: st.markdown(_ft)
                    metrics({"Latest Year":int(latest["year"]),"Wickets":int(latest["wickets"]),
                             "Economy (latest)":round(float(latest["economy"]),2),
                             "Average (latest)":round(float(latest["average"]),1),
                             "Matches":int(latest["matches"])})
                    if cecon or cavg:
                        badges2=""
                        if cecon: badges2+=form_delta_html(float(latest["economy"]),cecon,"econ",False)+" "
                        if cavg: badges2+=form_delta_html(float(latest["average"]),cavg,"avg",False)
                        if badges2.strip():
                            st.markdown(f'<div style="margin:4px 0 12px;display:flex;gap:6px;flex-wrap:wrap">{badges2}</div>',unsafe_allow_html=True)
                    clr=FC.get(fmt,"#d63031")
                    ch(bar_v(pyr,"year","wickets",f"{pname} — Wickets per Year ({fmt})","#d63031"))
                    c1,c2=st.columns(2)
                    fig_econ=px.line(pyr,x="year",y="economy",markers=True,title=f"{pname} — Economy by Year")
                    fig_econ.update_traces(line=dict(color="#d63031",width=3),
                                           marker=dict(size=9,color="#d63031",line=dict(width=2,color=BG)))
                    if cecon:
                        fig_econ.add_hline(y=cecon,line_dash="dash",line_color="#fdcb6e",
                                           annotation_text=f"Career econ {cecon:.2f}",
                                           annotation_position="top right",
                                           annotation_font=dict(color="#fdcb6e",size=11))
                    fig_econ.update_layout(**BASE,height=300,margin=M_DEFAULT)
                    with c1: st.plotly_chart(fig_econ,**CFG)
                    fig_avg2=px.line(pyr,x="year",y="average",markers=True,title=f"{pname} — Bowling Average by Year")
                    fig_avg2.update_traces(line=dict(color="#6c5ce7",width=3),
                                           marker=dict(size=9,color="#6c5ce7",line=dict(width=2,color=BG)))
                    if cavg:
                        fig_avg2.add_hline(y=cavg,line_dash="dash",line_color="#fdcb6e",
                                           annotation_text=f"Career avg {cavg:.1f}",
                                           annotation_position="top right",
                                           annotation_font=dict(color="#fdcb6e",size=11))
                    fig_avg2.update_layout(**BASE,height=300,margin=M_DEFAULT)
                    with c2: st.plotly_chart(fig_avg2,**CFG)
                    if "dot_pct" in pyr.columns:
                        fig_dot=px.line(pyr,x="year",y="dot_pct",markers=True,title=f"{pname} — Dot Ball % by Year")
                        fig_dot.update_traces(line=dict(color="#00cec9",width=3),marker=dict(size=8,color="#00cec9"))
                        fig_dot.update_layout(**BASE,height=260,margin=M_DEFAULT)
                        st.plotly_chart(fig_dot,**CFG)
                    show_cols=[c for c in ["year","matches","wickets","economy","average","dot_pct","balls"] if c in pyr.columns]
                    st.dataframe(pyr[show_cols].reset_index(drop=True))

    FORM_EXPLAIN = ("Form score compares each player's **last two seasons with their own career**: **100 = playing exactly at career level**, "
                    "above 115 = **On Fire**, below 75 = **Poor**. Small samples are pulled toward the career numbers, and players with too "
                    "little recent or career data are left unrated instead of guessed at.")

    # ── Tab 2: Hot List (v9 form ratings) ─────────────────────────────────────
    with tab2:
        ftype2=st.radio("Type",["Batting","Bowling"],horizontal=True,key="hot_type")
        st.caption(FORM_EXPLAIN)
        if ftype2=="Batting" and not bat_form.empty:
            _c = gf(bat_fmt); _c = _c[_c["format"]==fmt][["striker","matches","runs"]].rename(columns={"runs":"career_runs"})
            src = bat_form[bat_form["format"]==fmt].merge(_c, on="striker", how="inner")
            src = src[src["form_score"].notna() & (src["career_runs"]>=200)]
            hot = src.sort_values("form_score", ascending=False).head(25)
            if len(hot)>0:
                ch(bar_h(hot,"form_score","striker","form_score","Oranges",f"🔥 In-form batters — form score ({fmt}, {GENDER_PICK.lower()})"))
                sc=[c for c in ["striker","form_label","form_score","recent_avg","career_avg","recent_sr","career_sr","recent_runs","recent_balls"] if c in hot.columns]
                st.dataframe(hot[sc].reset_index(drop=True))
            else: st.info("No rated batters in this format right now.")
        elif ftype2=="Bowling" and not bowl_form.empty:
            _c = gf(bowl_fmt); _c = _c[_c["format"]==fmt][["bowler","matches","wickets"]].rename(columns={"wickets":"career_wkts"})
            src2 = bowl_form[bowl_form["format"]==fmt].merge(_c, on="bowler", how="inner")
            src2 = src2[src2["form_score"].notna() & (src2["career_wkts"]>=20)]
            hot2 = src2.sort_values("form_score", ascending=False).head(25)
            if len(hot2)>0:
                ch(bar_h(hot2,"form_score","bowler","form_score","Reds",f"🔥 In-form bowlers — form score ({fmt}, {GENDER_PICK.lower()})"))
                sc2=[c for c in ["bowler","form_label","form_score","recent_wkts","recent_econ","career_econ","recent_avg","career_avg"] if c in hot2.columns]
                st.dataframe(hot2[sc2].reset_index(drop=True))
            else: st.info("No rated bowlers in this format right now.")

    # ── Tab 3: Cold List ──────────────────────────────────────────────────────
    with tab3:
        ftype3=st.radio("Type",["Batting","Bowling"],horizontal=True,key="cold_type")
        st.caption(FORM_EXPLAIN)
        if ftype3=="Batting" and not bat_form.empty:
            _c = gf(bat_fmt); _c = _c[_c["format"]==fmt][["striker","matches","runs"]].rename(columns={"runs":"career_runs"})
            src = bat_form[bat_form["format"]==fmt].merge(_c, on="striker", how="inner")
            src = src[src["form_score"].notna() & (src["career_runs"]>=200)]
            cold = src[src["form_label"]=="Poor"].sort_values("form_score").head(20)
            if len(cold)>0:
                ch(bar_h(cold,"form_score","striker","form_score","Reds",f"📉 Struggling batters — form score ({fmt}, {GENDER_PICK.lower()})"))
                sc=[c for c in ["striker","form_label","form_score","recent_avg","career_avg","recent_sr","career_sr"] if c in cold.columns]
                st.dataframe(cold[sc].reset_index(drop=True))
            else: st.info("No rated batters in poor form right now.")
        elif ftype3=="Bowling" and not bowl_form.empty:
            _c = gf(bowl_fmt); _c = _c[_c["format"]==fmt][["bowler","matches","wickets"]].rename(columns={"wickets":"career_wkts"})
            src2 = bowl_form[bowl_form["format"]==fmt].merge(_c, on="bowler", how="inner")
            src2 = src2[src2["form_score"].notna() & (src2["career_wkts"]>=20)]
            cold2 = src2[src2["form_label"]=="Poor"].sort_values("form_score").head(20)
            if len(cold2)>0:
                ch(bar_h(cold2,"form_score","bowler","form_score","Reds",f"📉 Struggling bowlers — form score ({fmt}, {GENDER_PICK.lower()})"))
                sc2=[c for c in ["bowler","form_label","form_score","recent_econ","career_econ","recent_avg","career_avg"] if c in cold2.columns]
                st.dataframe(cold2[sc2].reset_index(drop=True))
            else: st.info("No rated bowlers in poor form right now.")

    # ── Tab 4: Player Scores ──────────────────────────────────────────────────
    with tab4:
        ps_type=st.radio("Type",["Batting","Bowling"],horizontal=True,key="ps_type")
        st.caption("Player Score is a **percentile** (0–100) inside the same format and men's/women's pool: 50 = a typical qualified player, "
                   "90+ = elite. Scores are **only comparable within a format** — a Test 80 and a T20 80 are each 'top of their own game'.")
        if ps_type=="Batting":
            ps=gf(bat_sim); ps=ps[ps["format"]==fmt].sort_values("player_score",ascending=False).head(25) if not bat_sim.empty else pd.DataFrame()
            if len(ps)>0:
                ch(bar_h(ps,"player_score","striker","player_score","Teal",f"⭐ Top 25 Batter Scores ({fmt}, {GENDER_PICK.lower()})"))
                st.caption("Score = Average 30% · Strike Rate 25% · Boundary% 20% · Runs volume 15% · Fewer dot balls 10% (each as a percentile rank)")
                st.dataframe(ps[["striker","player_score","average","strike_rate","boundary_pct","runs"]].reset_index(drop=True))
            else: st.info(f"No batting player score data for {fmt} yet.")
        else:
            ps2=gf(bowl_sim); ps2=ps2[ps2["format"]==fmt].sort_values("player_score",ascending=False).head(25) if not bowl_sim.empty else pd.DataFrame()
            if len(ps2)>0:
                ch(bar_h(ps2,"player_score","bowler","player_score","Purples",f"⭐ Top 25 Bowler Scores ({fmt}, {GENDER_PICK.lower()})"))
                st.caption("Score = Wickets 30% · Economy 25% · Average 25% · Dot Ball% 20% (each as a percentile rank)")
                show_bowl=[c for c in ["bowler","player_score","wickets","economy","average","dot_pct"] if c in ps2.columns]
                st.dataframe(ps2[show_bowl].reset_index(drop=True))
            else: st.info(f"No bowling player score data for {fmt} yet.")

st.markdown('</div>', unsafe_allow_html=True)

# ── Diagnostics panel ─────────────────────────────────────────────────────────
_missing_full = st.session_state.get("wiki_missing_full", [])
_missing_field = st.session_state.get("wiki_missing_field", [])
_low_confidence = st.session_state.get("wiki_low_confidence", [])
_total_issues = len(_missing_full) + len(_missing_field) + len(_low_confidence)
if _total_issues:
    with st.expander(f"🔧 Data diagnostics — {_total_issues} profile lookup issue(s) this session", expanded=False):
        if _low_confidence:
            st.caption("**⚠️ Possibly wrong photo/bio** (no search result clearly matched 'cricketer' — "
                       "add a manual entry to WIKI_NAMES with the exact Wikipedia page title to fix):")
            for name, reason in _low_confidence:
                st.caption(f"• {name} — {reason}")
        if _missing_full:
            st.caption("**Profiles that failed to load entirely** (add a manual entry to WIKI_NAMES to fix):")
            for name, reason in _missing_full:
                st.caption(f"• {name} — {reason}")
        if _missing_field:
            st.caption("**Profiles found but missing birth date** (infobox format not recognized):")
            for name, reason in _missing_field:
                st.caption(f"• {name} — {reason}")
