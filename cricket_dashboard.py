import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Cricket Analytics", layout="wide", page_icon="🏏",
                   initial_sidebar_state="collapsed")

# ── Theme (light/dark) ─────────────────────────────────────────────────────────
# Read the saved choice before the toggle widget itself is drawn further down
# the page — this is safe in Streamlit because session_state persists across
# reruns, so on the run right after someone flips the switch, this already
# reflects their new choice even though the widget itself renders later.
IS_LIGHT = st.session_state.get("is_light_mode", False)

RAW_BASE = "https://raw.githubusercontent.com/mmrayyan2005-dev/cricket-analytics_-/main"

if IS_LIGHT:
    # "Scorecard Paper" — Wisden almanac page: cream leaf, oxblood ink stamp
    BG="#f3ecd8"; CARD="#fffdf6"; TEXT="#26211a"; GRID="#ded2ab"
    SURFACE="#fbf6e9"; BORDER="#ded2ab"; MUTED="#8a7f60"; SUBTLE="#55493a"
    SHADOW="0 4px 20px rgba(38,33,26,.10)"
    ACCENT="#8a3226"; ACCENT2="#b3891f"
else:
    # "Floodlit Pavilion" — deep turf-night green, Wisden-yellow scoreboard
    # numerals, oxblood ledger-ink for secondary accents.
    BG="#0b150f"; CARD="#16241a"; TEXT="#f3ecd8"; GRID="#2c4030"
    SURFACE="#101c14"; BORDER="#2c4030"; MUTED="#74836f"; SUBTLE="#c3bb9e"
    SHADOW="0 6px 28px rgba(0,0,0,.55)"
    ACCENT="#e3b431"; ACCENT2="#8a3226"
FC={"ODI":"#3f7a52","Test":"#8a95a8","T20I":"#e3b431",
    "IPL":"#8a3226","PSL":"#2f8f5b","WPL":"#b2557a","BBL":"#d9772b","CPL":"#2f9aa0"}
FORMATS=["ODI","Test","T20I","IPL","PSL","WPL","BBL","CPL"]
FORMAT_META={
    "ODI":("🌐","#3f7a52","#529a68"),"Test":("🏛️","#8a95a8","#a8b2c2"),
    "T20I":("⚡","#e3b431","#edc862"),"IPL":("🏏","#8a3226","#aa4a3c"),
    "PSL":("🟢","#2f8f5b","#3fae72"),"WPL":("🌹","#b2557a","#c97694"),
    "BBL":("🔥","#d9772b","#e8974f"),"CPL":("🌊","#2f9aa0","#45bcc2"),
}
BASE=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
          font=dict(color=TEXT,family="PT Serif,serif",size=12),
          legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1,
                      bgcolor="rgba(0,0,0,0)",font=dict(size=11)),
          xaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
          yaxis=dict(showgrid=True,gridcolor=GRID,zeroline=False,color=TEXT,fixedrange=True),
          dragmode=False,
          hoverlabel=dict(bgcolor=CARD,bordercolor=ACCENT,font=dict(color=TEXT,size=12,family="PT Serif,serif")),
          hovermode="closest")
M_DEFAULT=dict(l=8,r=8,t=48,b=8)
M_BARV=dict(l=8,r=8,t=48,b=60)
CFG=dict(config={"displayModeBar":False,"scrollZoom":False,"doubleClick":False,"responsive":True},use_container_width=True)

# ── V17 UI + comprehensive CSS ────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=PT+Serif:ital,wght@0,400;0,700;1,400&family=Space+Mono:wght@400;700&display=swap');
:root{
  --bg:#0b150f;--surface:#101c14;--card:#16241a;--border:#2c4030;
  --accent:#e3b431;--accent2:#8a3226;--warn:#e3b431;--gold:#e3b431;
  --text:#f3ecd8;--muted:#74836f;--subtle:#c3bb9e;
  --radius:10px;--radius-sm:6px;
  --font-head:'Big Shoulders Display',sans-serif;--font-body:'PT Serif',serif;--font-data:'Space Mono',monospace;
  --shadow:0 6px 28px rgba(0,0,0,.55);
}
html,body,[class*="css"]{font-family:var(--font-body);background:var(--bg);color:var(--text)}
.stApp{
  background-color:var(--bg);
  background-image:
    radial-gradient(ellipse 900px 460px at 50% -8%, rgba(227,180,49,.07) 0%, transparent 62%),
    repeating-linear-gradient(100deg, rgba(243,236,216,.014) 0 120px, rgba(243,236,216,.026) 120px 124px, transparent 124px 240px);
  background-attachment:fixed;
}
.block-container{padding:0 !important;max-width:100% !important}
[data-testid="stSidebar"]{display:none !important}
h1,h2,h3,h4,.ca-section-title,.ca-feature-title,.ca-player-name{font-family:var(--font-head)!important;letter-spacing:.2px}

/* ── Metrics: scoreboard flip-panel ── */
[data-testid="stMetric"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:4px!important;padding:14px 16px!important;position:relative;overflow:hidden;transition:border-color .25s,transform .2s;box-shadow:var(--shadow)}
[data-testid="stMetric"]:hover{border-color:var(--accent)!important;transform:translateY(-2px)}
[data-testid="stMetric"]::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent);opacity:.85}
[data-testid="stMetricLabel"]{font-family:var(--font-body)!important;font-size:10px!important;font-weight:700!important;color:var(--muted)!important;text-transform:uppercase;letter-spacing:1.4px!important}
[data-testid="stMetricValue"]{font-family:var(--font-data)!important;font-size:22px!important;font-weight:700!important;color:var(--text)!important;line-height:1.2!important;letter-spacing:-0.3px!important}
[data-testid="stMetricDelta"]{font-size:11px!important}

/* ── Tabs ── */
div[data-baseweb="tab-list"]{gap:4px!important;flex-wrap:wrap!important;background:transparent!important;border-bottom:1px solid var(--border)!important;padding-bottom:6px!important}
div[data-baseweb="tab"]{border-radius:var(--radius-sm)!important;padding:7px 16px!important;background:var(--card)!important;font-weight:700!important;font-size:12px!important;color:var(--subtle)!important;border:1px solid var(--border)!important;transition:all .2s!important;font-family:var(--font-body)!important}
div[data-baseweb="tab"]:hover{border-color:var(--accent)!important;color:var(--text)!important}
div[data-baseweb="tab"][aria-selected="true"]{background:rgba(227,180,49,.1)!important;border-color:var(--accent)!important;color:var(--accent)!important;box-shadow:none!important}
div[data-baseweb="tab-highlight"],div[data-baseweb="tab-border"]{display:none!important}

/* ── Inputs ── */
[data-testid="stTextInput"] input{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important;font-family:var(--font-body)!important;font-size:14px!important;padding:11px 14px!important;transition:border-color .2s,box-shadow .2s!important}
[data-testid="stTextInput"] input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(227,180,49,.15)!important;outline:none!important}
[data-testid="stTextInput"] input::placeholder{color:var(--muted)!important}
[data-testid="stSelectbox"]>div>div{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important;transition:border-color .2s!important}
[data-testid="stSelectbox"]>div>div:hover{border-color:var(--accent)!important}
[data-testid="stRadio"]>div{flex-wrap:wrap!important;gap:5px!important}
[data-testid="stRadio"] label{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;padding:5px 13px!important;font-size:12px!important;font-weight:700!important;color:var(--subtle)!important;cursor:pointer;transition:all .15s!important;font-family:var(--font-body)!important}
[data-testid="stRadio"] label:hover{border-color:var(--accent)!important;color:var(--text)!important}
[data-testid="stRadio"] label:has(input:checked){border-color:var(--accent)!important;color:var(--accent)!important;background:rgba(227,180,49,.09)!important}

/* ── Sliders ── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"]{background:var(--accent)!important;border-color:var(--accent)!important;box-shadow:0 0 0 4px rgba(227,180,49,.18)!important}
[data-testid="stSlider"] [data-baseweb="slider"] div[class*="Track"]{background:var(--border)!important}

/* ── DataFrames ── */
.stDataFrame{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important;box-shadow:var(--shadow)}
.stDataFrame thead th{font-size:10px!important;font-weight:700!important;text-transform:uppercase;letter-spacing:.8px;background:var(--surface)!important;color:var(--muted)!important;padding:10px 14px!important;border-bottom:1px solid var(--border)!important}
.stDataFrame tbody td{font-family:var(--font-data)!important;font-size:12px!important;padding:9px 14px!important;border-bottom:1px solid var(--border)!important}
.stDataFrame tbody tr:hover td{background:rgba(193,68,45,.03)!important}
.stDataFrame tbody tr:first-child td{color:var(--gold)!important;font-weight:600!important}

/* ── Spinner / Loading ── */
[data-testid="stSpinner"]>div{border-color:var(--accent) transparent transparent transparent!important}

/* ── Captions ── */
[data-testid="stCaptionContainer"]{color:var(--muted)!important;font-size:11px!important;line-height:1.6!important;padding:2px 0 8px!important}

/* ── Headings ── */
h1,h2,h3,h4{font-family:var(--font-head)!important;letter-spacing:-0.3px!important;color:var(--text)!important}
h4{font-size:14px!important;font-weight:700!important;margin:18px 0 8px!important;color:var(--subtle)!important;text-transform:uppercase;letter-spacing:.8px!important}

/* ── Section divider ── */
hr{border:none!important;border-top:1px solid var(--border)!important;margin:20px 0!important}
.ca-divider{display:flex;align-items:center;gap:12px;margin:20px 0 16px}
.ca-divider-line{flex:1;height:1px;background:var(--border)}
.ca-divider-label{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;white-space:nowrap}

/* ── Back button ── */
[data-testid="stButton"] button[kind="secondary"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--subtle)!important;font-size:12px!important;font-weight:600!important;padding:6px 16px!important;transition:all .15s!important;margin-bottom:14px!important}
[data-testid="stButton"] button[kind="secondary"]:hover{border-color:var(--accent)!important;color:var(--accent)!important;background:rgba(193,68,45,.06)!important}

/* ── Alerts / Error / Info ── */
[data-testid="stAlert"]{border-radius:var(--radius-sm)!important;border-left:3px solid!important;font-size:13px!important;padding:10px 14px!important}
[data-testid="stAlert"][data-type="error"]{background:rgba(255,77,109,.06)!important;border-color:var(--warn)!important}
[data-testid="stAlert"][data-type="info"]{background:rgba(201,162,39,.06)!important;border-color:var(--accent2)!important}
[data-testid="stAlert"][data-type="warning"]{background:rgba(251,191,36,.06)!important;border-color:var(--gold)!important}
[data-testid="stAlert"][data-type="success"]{background:rgba(193,68,45,.06)!important;border-color:var(--accent)!important}

/* ── Plotly chart wrappers ── */
.js-plotly-plot{touch-action:pan-y!important}
[data-testid="stPlotlyChart"]{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important;background:var(--card)!important;box-shadow:var(--shadow)}

/* ── Columns ── */
div[data-testid="stHorizontalBlock"]>div[data-testid="column"]{min-width:0!important;flex:1 1 auto}

/* ── Animations ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes shimmer{0%{background-position:-200% center}100%{background-position:200% center}}
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.75)}}
.ca-fade{animation:fadeUp .4s ease both}
.ca-shimmer{background:linear-gradient(90deg,var(--accent) 0%,var(--accent2) 40%,var(--accent) 80%);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 3s linear infinite}
.ca-live{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);animation:pulse-dot 1.8s ease infinite;vertical-align:middle;margin-right:4px}

/* ── TOP NAV: scoreboard header bar ── */
.ca-topnav{position:sticky;top:0;z-index:999;background:var(--surface);border-bottom:2px solid var(--accent);padding:0 24px;display:flex;align-items:center;gap:0;height:56px;width:100%;box-sizing:border-box}
.ca-topnav-brand{display:flex;align-items:center;gap:8px;font-family:var(--font-head);font-size:18px;font-weight:800;letter-spacing:.4px;color:var(--text);white-space:nowrap;margin-right:24px;flex-shrink:0;text-transform:uppercase}
.ca-topnav-brand span{color:var(--accent)}
.ca-topnav-links{display:flex;align-items:center;gap:2px;flex:1;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.ca-topnav-links::-webkit-scrollbar{display:none}
.ca-navbtn{display:flex;align-items:center;gap:5px;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:700;color:var(--subtle);white-space:nowrap;cursor:pointer;border:none;background:transparent;transition:all .15s;font-family:var(--font-body);text-decoration:none}
.ca-navbtn:hover{background:rgba(227,180,49,.08);color:var(--text)}
.ca-navbtn.active{background:rgba(227,180,49,.12);color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent)}
.ca-topnav-status{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:3px;background:rgba(227,180,49,.08);border:1px solid rgba(227,180,49,.25);font-size:10px;font-weight:700;color:var(--accent);white-space:nowrap;flex-shrink:0;margin-left:12px;font-family:var(--font-data)}
.ca-content{padding:20px 24px 60px}

/* ── Section cards: seam-stitch divider (cricket-ball seam motif) ── */
.ca-section-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px;box-shadow:var(--shadow);position:relative}
.ca-section-card::before{content:'';position:absolute;top:0;left:16px;right:16px;height:2px;
  background-image:repeating-linear-gradient(90deg,var(--accent) 0 4px,transparent 4px 8px,var(--accent2) 8px 12px,transparent 12px 16px);opacity:.55}
.ca-section-header{display:flex;align-items:center;gap:10px;margin-bottom:16px}
.ca-section-emoji{font-size:24px;line-height:1}
.ca-section-title{font-family:var(--font-head);font-size:19px;font-weight:800;color:var(--text);text-transform:uppercase;letter-spacing:.3px}
.ca-section-sub{font-size:12px;color:var(--muted);margin-top:2px;font-family:var(--font-body)}

/* ── Home grid ── */
.ca-home-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:24px}
.ca-feature-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;cursor:pointer;transition:all .22s;text-decoration:none;display:block;box-shadow:var(--shadow)}
.ca-feature-card:hover{border-color:var(--accent);transform:translateY(-3px);box-shadow:0 8px 32px rgba(0,0,0,.5)}
.ca-feature-icon{font-size:28px;margin-bottom:10px}
.ca-feature-title{font-family:var(--font-head);font-size:16px;font-weight:800;color:var(--text);margin-bottom:4px;text-transform:uppercase}
.ca-feature-desc{font-size:12px;color:var(--muted);line-height:1.5;font-family:var(--font-body)}

/* ── Player card ── */
.ca-player-card{display:flex;gap:14px;align-items:flex-start;overflow:hidden;box-sizing:border-box}
.ca-player-img{flex-shrink:0}
.ca-player-info{flex:1;min-width:0}
.ca-player-name{font-family:var(--font-head);color:var(--text);font-weight:800;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:.2px;text-transform:uppercase}
.ca-player-pills{display:flex;flex-wrap:wrap;margin-bottom:7px}
.ca-player-bio{color:var(--muted);font-size:11px;line-height:1.6;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;font-family:var(--font-body)}
.ca-pill{background:rgba(227,180,49,.06);border:1px solid rgba(227,180,49,.18);padding:3px 9px;border-radius:3px;font-size:10px;font-weight:700;white-space:nowrap;display:inline-block;margin:2px 2px 2px 0;transition:border-color .15s;font-family:var(--font-data)}
.ca-pill:hover{border-color:var(--accent)}

/* ── Insight box ── */
.ca-insight{background:rgba(227,180,49,.05);border:1px solid rgba(227,180,49,.18);border-radius:var(--radius-sm);padding:10px 14px;margin:8px 0 14px;font-size:12px;color:var(--subtle);line-height:1.6;font-family:var(--font-body)}
.ca-insight strong{color:var(--accent)}

/* ── Mobile ── */
@media(max-width:640px){
  .ca-content{padding:12px 14px 40px}
  .ca-topnav{padding:0 12px;height:52px}
  .ca-topnav-brand{font-size:14px;margin-right:10px}
  .ca-navbtn{padding:5px 8px;font-size:11px}
  .ca-navbtn .nav-label{display:none}
  .ca-topnav-status{display:none}
  [data-testid="stMetricValue"]{font-size:18px!important}
  [data-testid="stMetricLabel"]{font-size:9px!important}
  [data-testid="stMetric"]{padding:10px 12px!important}
  [data-testid="stHorizontalBlock"]{flex-direction:column!important;gap:8px!important}
  [data-testid="stHorizontalBlock"]>div[data-testid="column"]{width:100%!important;min-width:100%!important;flex:1 1 100%!important}
  div[data-baseweb="tab"]{padding:5px 8px!important;font-size:10px!important}
  .stPlotlyChart{overflow-x:auto!important;-webkit-overflow-scrolling:touch!important}
  .stDataFrame{overflow-x:auto!important}
  [data-testid="stRadio"] label{font-size:11px!important;padding:4px 8px!important}
  .ca-home-grid{grid-template-columns:1fr 1fr}
  .ca-feature-icon{font-size:22px;margin-bottom:6px}
  .ca-feature-title{font-size:13px}
  .ca-feature-desc{display:none}
  [data-testid="stPlotlyChart"]{border-radius:var(--radius-sm)!important}
}
@media(min-width:641px) and (max-width:900px){
  .ca-content{padding:16px 18px 40px}
  [data-testid="stMetricValue"]{font-size:20px!important}
  div[data-baseweb="tab"]{font-size:12px!important;padding:6px 12px!important}
}
</style>""", unsafe_allow_html=True)

if IS_LIGHT:
    # Light mode override: re-declares the same CSS custom properties with
    # light values. This works via normal CSS cascade — a later :root block
    # overrides the earlier one's variable values — so every rule in the
    # static stylesheet above (which all reference var(--bg), var(--card)
    # etc.) picks up the light palette automatically, with zero duplication
    # of the ~250 lines of rules above.
    st.markdown(f"""<style>
:root{{
  --bg:{BG};--surface:{SURFACE};--card:{CARD};--border:{BORDER};
  --text:{TEXT};--muted:{MUTED};--subtle:{SUBTLE};
  --shadow:{SHADOW};--accent:{ACCENT};--accent2:{ACCENT2};--warn:{ACCENT};--gold:{ACCENT2};
}}
.ca-topnav{{background:{SURFACE}!important;border-bottom:2px solid {ACCENT}!important}}
.ca-topnav-brand{{color:{TEXT}!important}}
[data-testid="stMetricValue"]{{color:{TEXT}!important}}
.stDataFrame tbody tr:hover td{{background:rgba(138,50,38,.06)!important}}
[data-testid="stRadio"] label{{color:{SUBTLE}!important}}
</style>""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
# NOTE: previously this fetched 18 CSVs one-by-one over the network in sequence.
# Each fetch has its own round-trip latency, so 18 sequential calls meant the
# app waited for #1 to fully finish before even starting #2, and so on.
# Fetching them concurrently (ThreadPoolExecutor) means all 18 requests are
# in flight at once, so total load time ≈ the slowest single file, not the sum
# of all 18. This is the main fix for "the app takes forever after the cache
# expires every hour."
from concurrent.futures import ThreadPoolExecutor

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

import io

def _fetch_one(name):
    """Phase 1: network fetch only — safe to run concurrently."""
    try:
        r = requests.get(f"{RAW_BASE}/{name}", timeout=20)
        r.raise_for_status()
        return (name, r.content, None)
    except Exception as e:
        # Previously a bare `except: return pd.DataFrame()` swallowed every
        # error silently, so a renamed/missing file just quietly became an
        # empty table with zero indication anything went wrong. Now we
        # collect the failure so it can be shown in the app (see load_errors).
        return (name, None, str(e))

@st.cache_data(ttl=3600, show_spinner=False)
def load():
    fetched = {}
    errors = []
    # Phase 1: fetch all 18 files concurrently — network I/O is thread-safe,
    # so this is where the ThreadPoolExecutor speedup is safe to use.
    with ThreadPoolExecutor(max_workers=len(CSV_FILES)) as ex:
        for name, content, err in ex.map(_fetch_one, CSV_FILES):
            fetched[name] = content
            if err:
                errors.append((name, err))

    # Phase 2: parse sequentially. pandas' CSV parser (backed by the C/pyarrow
    # engine) is NOT reliably thread-safe — running pd.read_csv() concurrently
    # across 18 threads was causing an intermittent segmentation fault that
    # crashed the whole app with no Python traceback. Parsing one file at a
    # time here, after all network calls are already done, avoids that while
    # keeping the actual slow part (network fetch) fully concurrent.
    results = {}
    for name in CSV_FILES:
        content = fetched.get(name)
        if content is None:
            results[name] = pd.DataFrame()
            continue
        try:
            results[name] = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            results[name] = pd.DataFrame()
            errors.append((name, str(e)))

    ordered = [results[name] for name in CSV_FILES]
    return (*ordered, errors)

@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache — this data updates every 30 min via Action
def load_live_matches():
    try:
        df = pd.read_csv(f"{RAW_BASE}/cricket_live_matches.csv")
        return df
    except Exception:
        return pd.DataFrame()

# ── New: Predictions Lab data loaders ─────────────────────────────────────────
# These back the Match Results / Player Forecast / Bowler Workload / Win
# Probability pages. Each returns an empty DataFrame on any failure (missing
# file, bad push, wrong repo, etc.) rather than crashing the app — the pages
# themselves check for empty and show a clear "not available yet" message
# instead. This matters right now specifically because the notebook push for
# these files has been unreliable (token/repo issues), so the dashboard needs
# to keep working even when some of these are missing.
def _try_load(filename):
    try:
        return pd.read_csv(f"{RAW_BASE}/{filename}")
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_match_results():
    return _try_load("cricket_matches_info.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_player_forecast():
    return _try_load("cricket_run_forecast.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_bowler_workload():
    return _try_load("cricket_bowler_workload.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_win_prob_test():
    return _try_load("cricket_win_prob_test.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_model_metrics():
    return _try_load("cricket_model_metrics.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_latest_team_form():
    return _try_load("cricket_latest_team_form.csv")

@st.cache_data(ttl=3600, show_spinner=False)
def load_coverage_gaps():
    # Cricsheet vs Wikipedia official career totals, built by pipeline.py's
    # build_coverage_gap_report(). Missing/old repo without this file yet
    # just returns empty — show_player_card's gap notice below no-ops on that.
    return _try_load("cricket_coverage_gaps.csv")

RECOGNIZED_TEAMS = {
    "Afghanistan","Australia","Bangladesh","England","India","Ireland","New Zealand",
    "Pakistan","South Africa","Sri Lanka","West Indies","Zimbabwe",
    "Scotland","Netherlands","Nepal","UAE","United Arab Emirates","Namibia","Oman",
    "USA","United States of America","Canada","Papua New Guinea","Kenya","Uganda",
    "Hong Kong","Singapore","Malaysia","Bermuda","Jersey","Guernsey",
}
def is_real_country(name):
    """Filters out domestic franchise/club teams (e.g. 'Adelaide Strikers',
    'Africa XI') from pickers meant for a general audience — a layman
    shouldn't see a franchise team name and wonder why it's 'playing' a
    country. This isn't exhaustive but covers every ODI/Test/T20I side."""
    return name in RECOGNIZED_TEAMS

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

# Surface load failures instead of hiding them as silently-empty tables.
# This is what was previously making "some data missing" impossible to debug —
# a failed fetch just looked like a normal empty dataset with no explanation.
if load_errors:
    with st.expander(f"⚠️ {len(load_errors)} data file(s) failed to load — click for details", expanded=False):
        for name, err in load_errors:
            st.caption(f"**{name}**: {err}")

def get_all_formats(df,col="format"):
    if df.empty or col not in df.columns: return ["ODI","Test","T20I","IPL","PSL"]
    return sorted(df[col].unique().tolist(),key=lambda x:FORMATS.index(x) if x in FORMATS else 99)

ALL_FMT=get_all_formats(bat_fmt)

def avail(df,col):
    return sorted(df[col].unique().tolist(),key=lambda x:FORMATS.index(x) if x in FORMATS else 99)

# ── Player name autocomplete ──────────────────────────────────────────────────
# Previously every player search was a plain free-text box — you had to know
# and correctly spell the exact Cricsheet name (e.g. "V Kohli" not "Kohli").
# This builds one master list of every player name that exists in the data
# (batters + bowlers, all formats) so we can offer live suggestions as you
# type, similar to a Google search dropdown.
@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_names():
    # Previously only pulled from the overall career-totals files
    # (cricket_batting_stats.csv / cricket_bowling_stats.csv). Anyone
    # added via career_overrides_batting.csv (e.g. a brand-new debutant
    # whose match Cricsheet doesn't have yet) only gets written into
    # batting_by_format/bowling_by_format, not those two files — so their
    # name never made it into this list, and searching their exact name
    # incorrectly fell through to "no exact match, did you mean...?"
    # instead of finding them directly. Pulling from all four sources
    # fixes this generally, for any current or future override.
    names = set()
    if not batting.empty and "striker" in batting.columns:
        names.update(batting["striker"].dropna().unique().tolist())
    if not bowling.empty and "bowler" in bowling.columns:
        names.update(bowling["bowler"].dropna().unique().tolist())
    if not bat_fmt.empty and "striker" in bat_fmt.columns:
        names.update(bat_fmt["striker"].dropna().unique().tolist())
    if not bowl_fmt.empty and "bowler" in bowl_fmt.columns:
        names.update(bowl_fmt["bowler"].dropna().unique().tolist())
    return sorted(names)

ALL_PLAYER_NAMES = get_all_player_names()

def player_input(label, default, key=None):
    """Dropdown with every known player name, searchable by typing — this is
    what gives the 'type ba, see Babar Azam / Brad Hogg' suggestion behavior.
    Falls back gracefully if the default isn't in the list (e.g. first run)."""
    options = ALL_PLAYER_NAMES if ALL_PLAYER_NAMES else [default]
    try:
        idx = options.index(default)
    except ValueError:
        idx = 0
    return st.selectbox(label, options, index=idx, key=key,
                         help="Start typing to search — matches filter as you type, like a search engine.")

# ── V12 smart find_rows (more thorough) ──────────────────────────────────────
def find_rows(df, name_col, query):
    import re as _re
    if df.empty: return pd.DataFrame()
    q = query.strip()
    if not q: return pd.DataFrame()
    parts = q.split()
    mask = df[name_col].str.match(r"(?i)^"+_re.escape(q)+r"$", na=False)
    if mask.any(): return df[mask]
    mask = df[name_col].str.contains(_re.escape(q), case=False, na=False)
    if mask.any(): return df[mask]
    if len(parts) >= 2:
        initial = parts[0][0].upper()
        last = _re.escape(parts[-1])
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
    if x == "year":
        fig.update_xaxes(dtick=1, tickformat="d")
    return fig

def line(df, x, y, title, color, h=280):
    if df.empty: return go.Figure()
    fig = px.line(df,x=x,y=y,markers=True,title=title)
    fig.update_traces(line=dict(color=color,width=3),
                      marker=dict(size=8,color=color,line=dict(width=2,color=BG)),
                      hovertemplate="<b>%{x}</b><br>" + y + ": <b>%{y:.2f}</b><extra></extra>")
    fig.update_layout(**BASE,height=h,margin=M_DEFAULT)
    if x == "year":
        # Defensive safeguard: force whole-number ticks on year axes so a
        # short data range (e.g. only 2 years) can't make Plotly's default
        # auto-tick logic show fractional years like 2025.2, 2025.4 —
        # regardless of the underlying column's exact dtype.
        fig.update_xaxes(dtick=1, tickformat="d")
    return fig

def donut(labels, values, colors, title):
    fig = go.Figure(go.Pie(labels=labels,values=values,hole=0.55,
        marker=dict(colors=colors,line=dict(color=BG,width=3)),
        textinfo="percent+label",textfont=dict(size=13,color=TEXT),
        hovertemplate="<b>%{label}</b><br>Runs: <b>%{value}</b><br>Share: <b>%{percent}</b><extra></extra>"))
    fig.update_layout(**BASE,height=320,title=title,showlegend=False,margin=M_DEFAULT)
    return fig

def metrics(d):
    items=list(d.items()); chunk=3
    for i in range(0,len(items),chunk):
        cols=st.columns(len(items[i:i+chunk]))
        for c,(k,v) in zip(cols,items[i:i+chunk]): c.metric(k,v)

def _hex_to_rgba(hex_color, alpha=0.18):
    """Convert hex color like #00e5a0 to rgba(193,68,45,0.18)."""
    h = hex_color.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    try:
        r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"
    except:
        return f"rgba(100,100,100,{alpha})"

def radar(categories, values1, values2, name1, name2, color1, color2, title):
    """Radar / spider chart for head-to-head comparisons."""
    cats = categories + [categories[0]]
    v1 = values1 + [values1[0]]
    v2 = values2 + [values2[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill="toself", name=name1,
        line=dict(color=color1, width=2.5),
        fillcolor=_hex_to_rgba(color1, 0.18),
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}<extra>" + name1 + "</extra>"))
    fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill="toself", name=name2,
        line=dict(color=color2, width=2.5),
        fillcolor=_hex_to_rgba(color2, 0.18),
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}<extra>" + name2 + "</extra>"))
    fig.update_layout(**BASE, title=title, height=440,
        polar=dict(bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, gridcolor=GRID, color=TEXT,
                            tickfont=dict(size=9), range=[0,110]),
            angularaxis=dict(gridcolor=GRID, linecolor=GRID,
                             tickfont=dict(size=12, color=TEXT))),
        margin=dict(l=50,r=50,t=60,b=50))
    return fig

def scatter(df, x, y, text_col, color, title, x_label="", y_label=""):
    """Scatter plot with player name labels."""
    if df.empty: return go.Figure()
    fig = px.scatter(df, x=x, y=y, text=text_col, title=title,
                     color_discrete_sequence=[color])
    fig.update_traces(
        marker=dict(size=9, opacity=0.85, line=dict(width=1, color=BG)),
        textposition="top center", textfont=dict(size=9, color=TEXT),
        hovertemplate="<b>%{text}</b><br>" + (x_label or x) + ": <b>%{x:.1f}</b><br>" + (y_label or y) + ": <b>%{y:.1f}</b><extra></extra>")
    fig.update_layout(**BASE, height=480, margin=dict(l=50,r=20,t=48,b=50),
                      xaxis_title=x_label or x, yaxis_title=y_label or y)
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=True, gridcolor=GRID)
    return fig

def form_delta_html(recent_val, career_val, label, higher_is_better=True):
    """Return a styled HTML badge showing form vs career average."""
    if not recent_val or not career_val: return ""
    diff = recent_val - career_val
    pct = (diff / career_val * 100) if career_val else 0
    good = (diff > 0) == higher_is_better
    color = "#3a7a54" if good else "#8a3226"
    arrow = "▲" if diff > 0 else "▼"
    return (f'<span style="background:{color}18;border:1px solid {color}44;'
            f'color:{color};padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">'
            f'{arrow} {abs(pct):.1f}% vs career {label}</span>')

# ── V12 page_banner (richer gradient + pattern) ──────────────────────────────
def page_banner(emoji, title, subtitle, ga, gb, glow):
    st.markdown(f"""<div class="ca-fade" style="
      background:linear-gradient(120deg,{ga} 0%,{gb} 100%);
      border-radius:var(--radius);padding:18px 22px;margin:0 0 20px 0;
      border:1px solid {glow}33;display:flex;align-items:center;gap:16px;
      position:relative;overflow:hidden">
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(
        -45deg,transparent,transparent 18px,rgba(255,255,255,.015) 18px,rgba(255,255,255,.015) 19px);pointer-events:none"></div>
      <div style="font-size:36px;line-height:1;flex-shrink:0">{emoji}</div>
      <div>
        <div style="font-family:'Big Shoulders Display',sans-serif;color:#fff;font-size:19px;font-weight:800;letter-spacing:-0.3px;line-height:1.2">{title}</div>
        <div style="color:rgba(255,255,255,.5);font-size:12px;margin-top:3px">{subtitle}</div>
      </div>
    </div>""", unsafe_allow_html=True)

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

# ── Known data errors: player/format combos that are factually impossible ────
# These aren't display bugs — they come from Cricsheet itself (likely a name
# collision with a different player who shares a similar name string in
# their raw data). E.g. Pakistani players are barred from the IPL entirely,
# so any "Babar Azam — IPL" record is definitely wrong, not a real match.
# Add more entries here as they're spotted; this filters them out of every
# page that shows per-format stats, rather than fixing it in one spot.
KNOWN_BAD_PLAYER_FORMATS = {
    ("Babar Azam", "IPL"),
}
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
}

@st.cache_data(ttl=600, show_spinner=False)  # shorter cache for failures — was 3600s (1hr), meaning a single
                                              # transient Wikipedia hiccup for someone as unambiguous as
                                              # "V Kohli" would get stuck showing "unavailable" for a full
                                              # hour. 10 minutes lets a real, working lookup recover fast.
def get_wiki(cricsheet_name, search_name):
    try:
        import re, time
        wiki_title=WIKI_NAMES.get(cricsheet_name, search_name+" cricketer")

        # Retry once on transient network failures (timeout, rate limit,
        # momentary Wikipedia hiccup) before giving up — this is the most
        # likely reason an unambiguous, famous name like "V Kohli" would
        # ever show "profile unavailable".
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

        # Previously this always took results[0] — Wikipedia's plain text
        # search often ranks a more famous, unrelated person with a similar
        # surname above the actual (often less famous/younger) cricketer,
        # which is exactly how a wrong photo/bio ends up attached to the
        # right stats. Instead, score every candidate in the top 5 and pick
        # whichever one actually looks like a cricketer, rather than
        # trusting Wikipedia's raw ranking blindly.
        #
        # BUG FIX: the original version only scored candidates on whether
        # their snippet mentioned cricket-y keywords — it never checked
        # whether the page TITLE actually resembled the name being searched
        # at all. That's how an unrelated (but keyword-rich) cricketer's
        # page could outrank the real match — e.g. a search for "Babar Azam"
        # matching Sunil Gavaskar's page instead, just because Gavaskar's
        # snippet happened to score higher on cricket-keyword density.
        # Name similarity is now the dominant factor; keyword matching only
        # breaks ties between genuinely name-similar candidates.
        import difflib
        target_name = wiki_title.replace(" cricketer", "").strip().lower()
        def _name_similarity(title):
            t = title.lower().replace("(cricketer)","").strip()
            return difflib.SequenceMatcher(None, target_name, t).ratio()

        def _score(result):
            snippet = re.sub(r"<[^>]+>", "", result.get("snippet", "")).lower()
            title = result.get("title", "")
            name_sim = _name_similarity(title)   # 0.0 - 1.0
            score = name_sim * 20   # dominant factor — must actually be the right person
            if "cricket" in snippet: score += 3
            if "batsman" in snippet or "bowler" in snippet or "batter" in snippet: score += 1
            if "wicket-keeper" in snippet or "all-rounder" in snippet: score += 1
            # Penalize obvious non-cricketer pages that still matched the name
            if any(w in snippet for w in ["footballer","actor","musician","politician","author"]) \
               and "cricket" not in snippet:
                score -= 5
            # A title that barely resembles the searched name at all should
            # never win, regardless of how "cricket-y" its snippet reads.
            if name_sim < 0.4:
                score -= 15
            return score

        scored = sorted(results, key=_score, reverse=True)
        best_score = _score(scored[0])
        if best_score <= 0:
            # None of the candidates clearly look like a cricketer — flag
            # this as a low-confidence match instead of silently attaching
            # a possibly-wrong bio/photo, so it shows up in diagnostics.
            st.session_state.setdefault("wiki_low_confidence", []).append(
                (cricsheet_name, f"no candidate clearly matched 'cricketer' — using best guess '{scored[0]['title']}'"))
        page_title=scored[0]["title"]
        safe=page_title.replace(" ","_")
        rr=requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe}",
            timeout=8,headers={"User-Agent":"CricketAnalyticsApp/2.0"})
        rr.raise_for_status(); data=rr.json()

        # Wikipedia's own API flags disambiguation pages explicitly via
        # this "type" field. Previously we had no check for this, so a
        # common name (e.g. "Shoaib Khan", shared by 6+ real cricketers)
        # would pull the disambiguation page's "X may refer to..." text
        # and display it as if it were one specific person's biography —
        # visibly wrong and confusing. Reject it outright instead.
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
        result = {"title":data.get("title",page_title),"bio":bio,"img":img,
                "born":born[:60] if born else "",
                "odi_debut":odi_d or any_d,"test_debut":test_d or any_d,"t20_debut":t20_d or any_d,
                "ipl_debut":"","psl_debut":"","wpl_debut":"",
                "role":role_raw[:60] if role_raw else "",
                "nation":nation[:40] if nation else ""}
        # Previously a missing birth date was silently invisible — you'd only
        # notice by scrolling every player card and eyeballing which ones lack
        # a 🎂 pill. Now we log it once per session so you can see exactly
        # which names need a manual entry in WIKI_NAMES (usually a nickname/
        # spelling mismatch, or the infobox using a template this regex
        # doesn't cover yet).
        if not result["born"]:
            st.session_state.setdefault("wiki_missing_field", []).append(
                (cricsheet_name, "no birth date found on matched page: " + result["title"]))
        return result
    except Exception as e:
        # Previously a bare `except: return None` meant every failure —
        # network timeout, no search results, wrong page match, malformed
        # infobox — looked identical: a blank "Profile unavailable" card.
        # Logging the real reason here means you can tell "Wikipedia has no
        # page for this name" apart from "the request timed out."
        st.session_state.setdefault("wiki_missing_full", []).append((cricsheet_name, str(e)))
        return None

# ── show_player_card (rebuilt on native Streamlit components) ────────────────
# Previously this built one large custom HTML block via an f-string and
# rendered it with st.markdown(unsafe_allow_html=True). Even with every text
# field escaped, some players' cards still rendered as literal visible tags
# instead of a styled card for reasons that were hard to pin down further
# without live access to the deployed app. Rather than keep chasing the
# exact character/condition causing it, this rebuilds the same visual layout
# using Streamlit's own components (st.columns, st.image, st.caption) —
# these can't "leak" as raw text the way hand-built HTML can, since
# Streamlit itself controls how they render rather than relying on the
# browser to correctly parse a hand-assembled string.
import html as _html

def show_player_card(cricsheet_name, search_name, fmt="ODI", compact=False):
    card=get_wiki(cricsheet_name,search_name)
    with st.container(border=True):
        if not card:
            st.caption(f"📖 Profile unavailable for {cricsheet_name}")
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

# ── TOP NAVIGATION BAR (V13) ──────────────────────────────────────────────────
PAGES=["🏠 Home","📋 Match Results","🔮 Player Forecast","💪 Bowler Workload","🎯 Win Probability","🔍 Player Search","⚔️ Head to Head","🏟️ vs Venue",
       "🌍 vs Opponent","🤜 Batter vs Bowler","📈 Over Years",
       "🏆 Leaderboard","🤖 Similar Players","🔥 Form & Ratings"]

if "page" not in st.session_state: st.session_state["page"]="🏠 Home"
if "nav_history" not in st.session_state: st.session_state["nav_history"]=[]

# Apply any pending navigation BEFORE widgets are rendered
if st.session_state.get("_go"):
    dest = st.session_state["_go"]
    del st.session_state["_go"]
    cur = st.session_state.get("page","🏠 Home")
    if cur != dest:
        st.session_state["nav_history"].append(cur)
    st.session_state["page"] = dest

# Handle in-app back navigation
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

# NOTE: the previous top nav was a hand-built HTML/JS bar with onclick
# handlers that reached into the sidebar's radio buttons via JS. On
# Streamlit Community Cloud this silently failed to render at all for
# this app — the whole bar was just missing, with no error, because
# Streamlit's sandboxing can drop injected <script>/<button> markup in
# ways that don't show up as a Python exception. Rather than keep
# debugging an unreliable custom nav, this replaces it with a native
# st.radio(horizontal=True) — guaranteed to render every time, since
# it's a real Streamlit widget rather than raw HTML we're hoping survives.
navcol1, navcol2, navcol3 = st.columns([5,1,1])
with navcol1:
    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;padding:8px 4px 4px">
      <span style="font-family:'Big Shoulders Display',sans-serif;font-size:16px;font-weight:800;color:{TEXT}">🏏 Cricket<span style="color:var(--accent)">Analytics</span></span>
      <span style="margin-left:auto;font-size:10px;font-weight:600;color:var(--accent);display:flex;align-items:center;gap:5px">
        <span class="ca-live"></span>{status_txt}</span>
    </div>""", unsafe_allow_html=True)
with navcol2:
    # The app caches data for up to an hour for speed — if you just pushed
    # fresh data from the notebook and it's not showing yet, this clears
    # the cache immediately instead of waiting.
    if st.button("🔄 Refresh", help="Force-reload the latest data now"):
        st.cache_data.clear()
        st.rerun()
with navcol3:
    st.toggle("☀️ Light" if not IS_LIGHT else "🌙 Dark", key="is_light_mode",
              help="Switch between dark and light mode")

section=st.radio("",PAGES,key="page",horizontal=True,label_visibility="collapsed")

st.markdown('<div class="ca-content">', unsafe_allow_html=True)

# ── In-app Back button (shown on all pages except Home) ──────────────────────
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
      <div style="position:absolute;top:-80px;left:20%;width:400px;height:300px;background:radial-gradient(ellipse,rgba(193,68,45,.06) 0%,transparent 70%);pointer-events:none"></div>
      <div style="position:absolute;bottom:-60px;right:5%;width:300px;height:220px;background:radial-gradient(ellipse,rgba(201,162,39,.05) 0%,transparent 70%);pointer-events:none"></div>
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(201,162,39,.03) 39px,rgba(201,162,39,.03) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(201,162,39,.03) 39px,rgba(201,162,39,.03) 40px);pointer-events:none"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
        <span style="font-size:40px">🏏</span>
        <div>
          <h1 style="font-family:'Big Shoulders Display',sans-serif;color:#fff;margin:0;font-size:30px;font-weight:800;letter-spacing:-0.5px">Cricket <span class="ca-shimmer">Analytics</span></h1>
          <p style="color:var(--muted);font-size:13px;margin:4px 0 0">Ball-by-ball data · All-time records · 8 formats</p>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin:16px 0 18px">{fmt_pills}</div>
      <div style="display:flex;align-items:center;gap:8px;background:rgba(193,68,45,.06);border:1px solid rgba(193,68,45,.15);border-radius:20px;padding:6px 14px;width:fit-content">
        <span class="ca-live"></span>
        <span style="font-size:11px;font-weight:600;color:var(--accent)">Auto-updated daily · Cricsheet (2-3 day lag)</span>
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("#### 🔍 Quick Player Search")
    qname=st.text_input("","",placeholder="Type a player name — Babar, Kohli, Smriti, Shaheen, Maxwell...",
                        key="home_search",label_visibility="collapsed")
    if qname:
        st.session_state["_go"]="🔍 Player Search"
        st.session_state["ps_name"]=qname
        st.rerun()

    st.markdown("#### Explore")
    features=[
        ("⚔️","Head to Head","Compare any two players side by side","⚔️ Head to Head"),
        ("🏟️","Player vs Venue","How a player performs at each ground","🏟️ vs Venue"),
        ("🌍","vs Opponent","Dominance stats against each team","🌍 vs Opponent"),
        ("🤜","Batter vs Bowler","Ball-by-ball matchup data","🤜 Batter vs Bowler"),
        ("📈","Career Timeline","Year-by-year performance charts","📈 Over Years"),
        ("🏆","Leaderboard","Top players ranked by format & stat","🏆 Leaderboard"),
        ("🤖","Similar Players","ML-powered player comparisons","🤖 Similar Players"),
        ("🔥","Form & Ratings","Who's hot, who's cold right now","🔥 Form & Ratings"),
    ]
    cols=st.columns(4)
    for i,(emoji,title,desc,target) in enumerate(features):
        with cols[i%4]:
            if st.button(f"{emoji} **{title}**\n\n{desc}",key=f"feat_{i}",use_container_width=True):
                st.session_state["_go"]=target; st.rerun()

    st.markdown("---")
    st.markdown("#### 🏆 Quick Leaderboard")
    ql_fmt=st.radio("Format",ALL_FMT,horizontal=True,key="ql_fmt")
    qlc1,qlc2=st.columns(2)
    with qlc1:
        st.markdown("**Top 5 Batters by Runs**")
        top_bat=bat_fmt[bat_fmt["format"]==ql_fmt].sort_values("runs",ascending=False).head(5)[["striker","runs","average","strike_rate"]] if not bat_fmt.empty else pd.DataFrame()
        if not top_bat.empty: st.dataframe(top_bat.reset_index(drop=True),hide_index=True)
    with qlc2:
        st.markdown("**Top 5 Bowlers by Wickets**")
        top_bowl=bowl_fmt[bowl_fmt["format"]==ql_fmt].sort_values("wickets",ascending=False).head(5)[["bowler","wickets","economy","average"]] if not bowl_fmt.empty else pd.DataFrame()
        if not top_bowl.empty: st.dataframe(top_bowl.reset_index(drop=True),hide_index=True)

# ══ LIVE MATCHES ══════════════════════════════════════════════════════════════
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
    results = load_match_results()
    if results.empty:
        st.info("Match results data isn't available yet — this page reads `cricket_matches_info.csv`, "
                "which your notebook's extended analytics push needs to have succeeded for. "
                "Check the notebook's push output once the GitHub token issue is sorted.")
    else:
        fmt_opts = sorted(results["format"].dropna().unique().tolist()) if "format" in results.columns else []
        fmt = st.radio("Competition", fmt_opts, horizontal=True) if fmt_opts else None
        rf = results[results["format"]==fmt] if fmt else results

        # International formats (country vs country) get filtered to real
        # national teams automatically. Franchise leagues (IPL/PSL/BBL/etc)
        # are, by definition, domestic club competitions — filtering THOSE
        # down to "real countries" would wipe out every team in the league,
        # which makes no sense. So this happens silently based on which
        # competition is picked, with no extra checkbox or decision needed.
        INTERNATIONAL_FORMATS = {"ODI","Test","T20I"}
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
            st.caption(f"{len(rf_show):,} matches shown")

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
    page_banner("🔮","Player Forecast","Pick a player and see their projected runs for next season","#1a1408","#2e2410","#e3b431")
    forecast = load_player_forecast()
    if forecast.empty:
        st.info("Forecast data isn't available yet — this page reads `cricket_run_forecast.csv` from your "
                "notebook's extended analytics push. Check that push succeeded once the GitHub token is fixed.")
    else:
        pred_col = "predicted_runs" if "predicted_runs" in forecast.columns else (
            "projected_next_season_runs" if "projected_next_season_runs" in forecast.columns else None)
        actual_col = "runs" if "runs" in forecast.columns else "last_season_runs"
        name_col = "striker" if "striker" in forecast.columns else None

        if not pred_col or not name_col:
            st.warning("Forecast file is missing expected columns — showing raw data instead.")
            st.dataframe(forecast.reset_index(drop=True), hide_index=True)
        else:
            for c in [actual_col, pred_col]:
                if c in forecast.columns:
                    forecast.loc[forecast[c] > 1200, c] = pd.NA

            st.markdown('<div class="ca-insight">This is a simple statistical estimate based on a player\'s recent '
                         'seasons — <strong>not a guarantee</strong>. Think of it as "if their recent trend continues," '
                         'not a prediction of exactly what will happen.</div>', unsafe_allow_html=True)

            tab1, tab2 = st.tabs(["🔍 Look Up a Player", "📈 Who's Trending Up"])

            with tab1:
                pname = player_input("Player name", resolve("Kohli"), key="forecast_player")
                if pname:
                    sname = resolve(pname)
                    prow = find_rows(forecast, name_col, sname)
                    # Always offer every format as a choice, not just the ones
                    # this player happens to have a forecast row for — so the
                    # picker looks consistent no matter who you search, and
                    # a missing format shows a clear reason instead of just
                    # not being there at all (which looked like a bug).
                    all_formats_avail = ALL_FMT if ALL_FMT else FORMATS
                    pick_fmt = st.radio("Format", all_formats_avail, horizontal=True, key="pf_fmt")
                    r_match = prow[prow["format"]==pick_fmt] if (not prow.empty and "format" in prow.columns) else pd.DataFrame()

                    if r_match.empty:
                        st.info(f"No {pick_fmt} forecast for '{pname}' — either too little recent {pick_fmt} "
                                f"match history, or they don't play this format.")
                    else:
                        r = r_match.iloc[0]
                        actual = r.get(actual_col, None)
                        pred = r.get(pred_col, None)
                        # Realistic single-season ceilings differ a lot by
                        # format — Test seasons can run much higher than a
                        # T20 league season, so one flat cap for everything
                        # was itself hiding legitimate numbers.
                        season_cap = {"Test": 2200, "ODI": 1600, "T20I": 1000}.get(pick_fmt, 1000)
                        if actual is not None and pd.notna(actual) and actual > season_cap: actual = None
                        if pred is not None and pd.notna(pred) and pred > season_cap: pred = None
                        if actual is None or pred is None or pd.isna(actual) or pd.isna(pred):
                            st.info(f"We don't have reliable {pick_fmt} forecast numbers for {r.get(name_col, pname)} yet.")
                        else:
                            actual, pred = float(actual), float(pred)
                            diff = pred - actual
                            direction = "📈 projected to score more" if diff > 0 else ("📉 projected to score fewer" if diff < 0 else "➡️ projected to stay about the same")
                            st.markdown(f"### {r.get(name_col)} — {pick_fmt or ''}")
                            st.caption(f"{direction} next season, based on recent trend.")
                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=["Last Season", "Next Season (Projected)"], y=[actual, pred],
                                marker_color=[FC.get(pick_fmt,"#8a3226"), "#a29bfe"],
                                text=[f"{actual:.0f}", f"{pred:.0f}"], textposition="outside",
                                textfont=dict(size=16, color=TEXT)))
                            fig.update_layout(**BASE, height=340, showlegend=False, margin=dict(l=20,r=20,t=20,b=20),
                                              yaxis_title="Runs")
                            st.plotly_chart(fig, **CFG)

            with tab2:
                fmt_opts2 = sorted(forecast["format"].dropna().unique().tolist()) if "format" in forecast.columns else []
                fmt2 = st.radio("Format", fmt_opts2, horizontal=True, key="forecast_fmt") if fmt_opts2 else None
                ff = forecast[forecast["format"]==fmt2] if fmt2 else forecast
                ff = ff.dropna(subset=[pred_col])
                top_n = ff.sort_values(pred_col, ascending=False).head(15)
                st.caption("Players projected to score the most next season, based on recent form.")
                ch(bar_h(top_n, pred_col, name_col, pred_col, "Purples", f"Top 15 Projected Run-Scorers ({fmt2 or 'All'})"))

# ══ BOWLER WORKLOAD ═══════════════════════════════════════════════════════════
elif section=="💪 Bowler Workload":
    page_banner("💪","Bowler Workload","Simple injury-risk check based on recent bowling load","#1a0d08","#2e1a10","#8a3226")
    workload = load_bowler_workload()
    if workload.empty:
        st.info("Workload data isn't available yet — this page reads `cricket_bowler_workload.csv` from your "
                "notebook's extended analytics push. Check that push succeeded once the GitHub token is fixed.")
    else:
        st.markdown('<div class="ca-insight">This compares how much a bowler has bowled <strong>this week</strong> vs. '
                     'their <strong>normal monthly workload</strong>. A sudden spike can be a warning sign for injury. '
                     '<strong>Bowlers without enough recent match history are left unrated</strong> instead of guessed at.</div>', unsafe_allow_html=True)
        workload_reliable = workload[workload["risk_flag"].notna()] if "risk_flag" in workload.columns else workload
        tab1, tab2 = st.tabs(["🚨 Current Risk List", "🔍 Look Up a Bowler"])

        with tab1:
            if "risk_flag" in workload_reliable.columns and not workload_reliable.empty:
                latest_per_bowler = (workload_reliable.sort_values("start_date")
                                     .groupby("bowler").tail(1)) if "start_date" in workload_reliable.columns and "bowler" in workload_reliable.columns else workload_reliable
                risk_order = ["High injury risk","Caution","Safe zone","Undertrained"]
                counts = latest_per_bowler["risk_flag"].value_counts().reindex(risk_order).fillna(0)
                ch(bar_v(pd.DataFrame({"risk_flag":counts.index,"count":counts.values}),
                          "risk_flag","count","Current Risk Distribution (bowlers with enough history to rate)","#e17055"), 320)
                high_risk = latest_per_bowler[latest_per_bowler["risk_flag"]=="High injury risk"]
                if not high_risk.empty:
                    st.markdown("#### 🚨 Bowlers Currently Flagged High Risk")
                    show_cols4 = [c for c in ["bowler","start_date","overs_bowled","acwr","risk_flag"] if c in high_risk.columns]
                    st.dataframe(high_risk.sort_values("acwr", ascending=False)[show_cols4].reset_index(drop=True), hide_index=True)
                else:
                    st.success("No bowlers currently flagged high risk.")
            else:
                st.info("Not enough bowlers have sufficient match history yet for a reliable risk reading.")

        with tab2:
            bname = player_input("Bowler name", resolve("Bumrah"), key="workload_player")
            if bname and "bowler" in workload.columns:
                sname = resolve(bname)
                brow = find_rows(workload, "bowler", sname).sort_values("start_date") if "start_date" in workload.columns else find_rows(workload,"bowler",sname)
                if brow.empty:
                    st.warning(f"No workload data for '{bname}'.")
                else:
                    if "acwr" in brow.columns and "start_date" in brow.columns:
                        ch(line(brow, "start_date", "acwr", f"{sname} — Workload Ratio Over Time", "#e17055"), 320)
                    show_cols5 = [c for c in ["start_date","overs_bowled","acwr","risk_flag"] if c in brow.columns]
                    st.dataframe(brow[show_cols5].reset_index(drop=True), hide_index=True)

# ══ WIN PROBABILITY ═══════════════════════════════════════════════════════════
elif section=="🎯 Win Probability":
    page_banner("🎯","Win Probability","Pick two teams and see who's favored to win","#0d150d","#1a2a18","#3a7a54")
    metrics_df = load_model_metrics()
    form_df = load_latest_team_form()
    results_wp = load_match_results()

    if form_df.empty or results_wp.empty:
        st.info("Win probability data isn't available yet — this page reads `cricket_latest_team_form.csv` and "
                "`cricket_matches_info.csv` from your notebook's extended analytics push. Check that push succeeded "
                "once the GitHub token is fixed.")
    else:
        # Figure out which columns actually hold the team name and a
        # 0-1-ish "form"/win-rate number, since this file's exact column
        # names come from the notebook and can vary.
        team_col = next((c for c in form_df.columns if "team" in c.lower()), None)
        form_col = next((c for c in form_df.columns if "form" in c.lower() or "rate" in c.lower()), None)

        if not team_col or not form_col:
            st.warning("Team form file is missing expected columns — showing raw data instead.")
            st.dataframe(form_df.reset_index(drop=True), hide_index=True)
        else:
            # A team's ODI record can look completely different from their
            # Test record, so the estimate needs to be format-specific, not
            # one blended number across everything.
            wp_formats = sorted(results_wp["format"].dropna().unique().tolist()) if "format" in results_wp.columns else []
            wp_fmt = st.radio("Format", wp_formats, horizontal=True, key="wp_fmt") if wp_formats else None
            h2h_pool = results_wp[results_wp["format"]==wp_fmt] if wp_fmt else results_wp

            form_fmt_col = next((c for c in form_df.columns if c.lower()=="format"), None)
            form_pool = form_df[form_df[form_fmt_col]==wp_fmt] if (form_fmt_col and wp_fmt) else form_df

            avail_teams = sorted([t for t in form_pool[team_col].dropna().unique().tolist() if is_real_country(t)])
            if len(avail_teams) < 2:
                avail_teams = sorted([t for t in form_df[team_col].dropna().unique().tolist() if is_real_country(t)])
                form_pool = form_df
            if len(avail_teams) < 2:
                st.info("Not enough recognized teams in the form data to build a matchup.")
            else:
                c1, c2 = st.columns(2)
                team_a = c1.selectbox("Team A", avail_teams, index=0, key="wp_team_a")
                team_b = c2.selectbox("Team B", avail_teams, index=1, key="wp_team_b")
                toss_pick = st.radio("Who won the toss?", [team_a, team_b, "Unknown / doesn't matter"], horizontal=True, key="wp_toss")

                if team_a == team_b:
                    st.warning("Pick two different teams.")
                else:
                    form_a_row = form_pool[form_pool[team_col]==team_a]
                    form_b_row = form_pool[form_pool[team_col]==team_b]
                    form_a = float(form_a_row[form_col].iloc[0]) if not form_a_row.empty else 0.5
                    form_b = float(form_b_row[form_col].iloc[0]) if not form_b_row.empty else 0.5
                    # Normalize in case form is stored as a percentage (0-100)
                    if form_a > 1: form_a /= 100
                    if form_b > 1: form_b /= 100

                    h2h = h2h_pool[((h2h_pool["team1"]==team_a)&(h2h_pool["team2"]==team_b))|
                                      ((h2h_pool["team1"]==team_b)&(h2h_pool["team2"]==team_a))] if "team1" in h2h_pool.columns else pd.DataFrame()
                    if not h2h.empty and "winner" in h2h.columns:
                        a_wins = int((h2h["winner"]==team_a).sum())
                        decided = int(h2h["winner"].isin([team_a,team_b]).sum())
                        h2h_component = (a_wins/decided) if decided>0 else 0.5
                    else:
                        h2h_component = 0.5
                        decided = 0

                    form_component = form_a/(form_a+form_b) if (form_a+form_b)>0 else 0.5
                    toss_component = 0.55 if toss_pick==team_a else (0.45 if toss_pick==team_b else 0.5)

                    prob_a = round((0.45*form_component + 0.35*h2h_component + 0.20*toss_component)*100, 1)
                    prob_a = max(5.0, min(95.0, prob_a))  # keep it sane — nothing is ever a "certainty"
                    prob_b = round(100-prob_a, 1)

                    st.markdown(f"### 🎯 Estimated Win Probability — {wp_fmt or ''}")
                    fig = go.Figure(go.Bar(
                        x=[prob_a, prob_b], y=[team_a, team_b], orientation="h",
                        marker_color=[FC["ODI"], FC["Test"]],
                        text=[f"{prob_a}%", f"{prob_b}%"], textposition="outside",
                        textfont=dict(size=16, color=TEXT)))
                    fig.update_layout(**BASE, height=220, showlegend=False,
                                      margin=dict(l=20,r=60,t=20,b=20))
                    fig.update_xaxes(range=[0,105])
                    st.plotly_chart(fig, **CFG)

                    st.caption(f"Based on: recent form, head-to-head record ({decided} past matches between these two), "
                               f"and toss. This is a transparent estimate, not a black-box prediction — "
                               f"weighted 45% recent form, 35% head-to-head history, 20% toss.")

        if not metrics_df.empty:
            with st.expander("📊 How accurate is this, historically?"):
                st.dataframe(metrics_df.reset_index(drop=True), hide_index=True)
                st.caption("How well the underlying model predicted match winners on past matches it hadn't seen before.")

# ══ PLAYER SEARCH ═════════════════════════════════════════════════════════════
elif section=="🔍 Player Search":
    # Pre-fill search box via session state key (value= param removed in new Streamlit)
    if st.session_state.get("ps_name","") and "ps_input" not in st.session_state:
        st.session_state["ps_input"] = st.session_state["ps_name"]
    st.session_state["ps_name"] = ""
    fmt_pills="".join([
        f'<span style="background:{FORMAT_META.get(f,("","#00e5a0",""))[1]}18;color:{FORMAT_META.get(f,("","#00e5a0",""))[1]};border:1px solid {FORMAT_META.get(f,("","#00e5a0",""))[1]}44;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700">'
        f'{FORMAT_META.get(f,("🏏","",""))[0]} {f}</span>' for f in ALL_FMT])
    chips=[("Babar","#d98e2b"),("Kohli","#3a7a54"),("Bumrah","#8a95a8"),("Smriti","#b2557a"),("Shaheen","#e3b431"),("Maxwell","#8a3226")]
    chip_html="".join([f'<span style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);color:{c};padding:3px 12px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap">{n}</span>' for n,c in chips])
    st.markdown(f"""<div class="ca-fade" style="background:linear-gradient(160deg,#080c14,#0c1628,#080c14);
      border-radius:14px;padding:24px 28px 20px;margin-bottom:20px;border:1px solid var(--border);
      position:relative;overflow:hidden">
      <div style="position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(201,162,39,.04) 39px,rgba(201,162,39,.04) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(201,162,39,.04) 39px,rgba(201,162,39,.04) 40px);pointer-events:none"></div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">{fmt_pills}</div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <span style="font-size:11px;color:var(--muted);font-weight:600;white-space:nowrap">Quick search →</span>
        {chip_html}
      </div>
      <p style="color:var(--muted);font-size:12px;margin:10px 0 0">Search any player across all formats · Ball-by-ball stats · Wikipedia profiles</p>
    </div>""", unsafe_allow_html=True)

    name=st.text_input("",placeholder="🔍  Player name — e.g. Babar, Kohli, Smriti, Shaheen...",
                       label_visibility="collapsed",key="ps_input")
    name = st.session_state.get("ps_input","") or ""
    if name:
        sname=resolve(name)
        ab_rows=find_rows(bat_fmt,"striker",sname)
        aw_rows=find_rows(bowl_fmt,"bowler",sname)
        # BUG FIX: this used to require >=3 matches before a player's format
        # was even considered "available", which silently made ANY player
        # with 1-2 recorded matches (debutants, associate-nation players,
        # part-timers) completely unfindable via search — not a display
        # issue, an invisibility issue. A player who's played even one
        # real match should be findable; we just note the small sample
        # size instead of hiding them entirely.
        ab=ab_rows["format"].unique().tolist() if not ab_rows.empty else []
        aw=aw_rows["format"].unique().tolist() if not aw_rows.empty else []
        avl=sorted(set(ab+aw),key=lambda x:FORMATS.index(x) if x in FORMATS else 99)
        avl=filter_valid_formats(sname, avl)
        if not avl:
            # Previously this just said "try a different spelling" with no
            # actual help — every missing-player report in this project
            # turned into a slow manual CSV search to find out why. Now we
            # search the actual list of every player name in the dataset
            # for close matches, so the app tells you immediately whether
            # this is a name-spelling issue (here are the close matches you
            # probably meant) or a genuine data gap (no close match exists
            # at all, meaning Cricsheet likely doesn't have this player yet).
            import difflib
            close = difflib.get_close_matches(name, ALL_PLAYER_NAMES, n=5, cutoff=0.5)
            # Also check for simple substring matches (catches cases like
            # searching "Vaibhav" when the full name is "Vaibhav Suryavanshi"
            # but the fuzzy ratio above might not rank it highly enough)
            substr = [n for n in ALL_PLAYER_NAMES if name.lower() in n.lower()][:5]
            suggestions = list(dict.fromkeys(close + substr))  # dedupe, keep order
            if suggestions:
                st.warning(f"No exact match for '{name}'. Did you mean one of these?")
                for s in suggestions:
                    if st.button(s, key=f"suggest_{s}"):
                        # NOTE: cannot set st.session_state["ps_input"] directly here —
                        # Streamlit forbids overwriting a widget's own bound key after
                        # that widget has already been instantiated in this run, and
                        # raises a StreamlitAPIException. "ps_name" is the existing
                        # hand-off variable (see top of this section) that gets copied
                        # into "ps_input" BEFORE the widget is created on the next run.
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
        clr=FC.get(fmt,"#8a3226")
        bat=find_rows(bat_fmt[bat_fmt["format"]==fmt],"striker",sname)
        bowl=find_rows(bowl_fmt[bowl_fmt["format"]==fmt],"bowler",sname)
        display_name=bat["striker"].iloc[0] if len(bat)>0 else (bowl["bowler"].iloc[0] if len(bowl)>0 else sname)
        show_player_card(display_name,name,fmt)

        # Data freshness banner
        lu=get_last_updated()
        if lu:
            st.markdown(f"""<div style="background:rgba(193,68,45,.06);border:1px solid rgba(193,68,45,.2);
              border-radius:8px;padding:8px 14px;margin:0 0 14px;display:flex;align-items:center;gap:8px">
              <span>✅</span>
              <span style="font-size:11px;color:#00e5a0">Data last updated: <strong>{lu}</strong> — auto-updated daily from Cricsheet.</span></div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style="background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.25);
              border-radius:8px;padding:8px 14px;margin:0 0 14px;display:flex;align-items:center;gap:8px">
              <span>⚠️</span>
              <span style="font-size:11px;color:#fbbf24">Stats reflect Cricsheet's latest data. Very recent matches (last 2-3 days) may not yet be included.</span>
            </div>""", unsafe_allow_html=True)
        st.caption("ℹ️ Stats reflect matches Cricsheet has ball-by-ball data for. Cricsheet is a community-maintained "
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
                            st.markdown(f"""<div style="background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3);
                              border-radius:8px;padding:8px 14px;margin:0 0 10px;font-size:12px;color:#fbbf24">
                              ⚠️ <strong>Official record (Wikipedia): {int(g['wiki_matches'])} {fmt} matches
                              {(', ' + format(int(g['wiki_runs']), ',') + ' runs') if pd.notna(g.get('wiki_runs')) else ''}</strong>
                              — this app currently tracks {int(g['cricsheet_matches'])} from Cricsheet's ball-by-ball archive
                              ({abs(g['gap_pct']):.1f}% short). This is a known Cricsheet coverage gap, not a stale cache.</div>""",
                              unsafe_allow_html=True)
                    metrics({"Matches":int(p["matches"]),"Runs":f"{int(p['runs']):,}","Average":p["average"]})
                    metrics({"Strike Rate":p["strike_rate"],"4s":int(p["fours"]),"6s":int(p["sixes"])})
                    metrics({"Dismissals":int(p["dismissals"]),"Dot Ball %":f"{p['dot_pct']}%","Boundary %":f"{p['boundary_pct']}%"})
                    h100=int(p["hundreds"]) if "hundreds" in p.index and pd.notna(p.get("hundreds")) else "—"
                    h50=int(p["fifties"]) if "fifties" in p.index and pd.notna(p.get("fifties")) else "—"
                    hs=int(p["highest"]) if "highest" in p.index and pd.notna(p.get("highest")) else "—"
                    dk=int(p["ducks"]) if "ducks" in p.index and pd.notna(p.get("ducks")) else "—"
                    ps_=round(float(p["player_score"]),1) if "player_score" in p.index and pd.notna(p.get("player_score")) else "—"
                    metrics({"100s":h100,"50s":h50,"Highest":hs,"Ducks":dk,"⭐ Score":ps_})
                    fr=int(p["fours"])*4; sr_=int(p["sixes"])*6; or_=max(0,int(p["runs"])-fr-sr_)
                    ch(donut(["Fours","Sixes","Other"],[fr,sr_,or_],[clr,"#d63031","#636e72"],"Scoring Breakdown"),300)

                    # ── Raw data verification ──────────────────────────
                    # This recomputes the match count completely
                    # independently of everything above — directly from
                    # cricket_bat_innings.csv (one row per match+player,
                    # the most granular data we have), with no
                    # aggregation, caching, or display logic in between.
                    # If this number matches the "Matches" card above,
                    # that PROVES the card is accurately reflecting what's
                    # actually in the CSV — a low number is then a real
                    # Cricsheet coverage gap, not a display bug. If they
                    # ever differ, that's a genuine bug to report back.
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
                    metrics({"Matches":int(p2["matches"]),"Wickets":int(p2["wickets"]),"Economy":p2["economy"]})
                    metrics({"Average":p2["average"],"Strike Rate":p2["strike_rate"],"Dot %":f"{p2['dot_pct']}%"})
                    fw=int(p2["five_wkts"]) if "five_wkts" in p2.index and pd.notna(p2.get("five_wkts")) else "—"
                    bb=p2.get("best_bowling","—") if "best_bowling" in p2.index else "—"
                    metrics({"5-Wkt Hauls":fw,"Best Bowling":bb})
                ti+=1
            with tabs[ti]:
                if len(bat)>0:
                    p=bat.sort_values("runs",ascending=False).iloc[0]; en=p["striker"]
                    by=bat_yr[(bat_yr["format"]==fmt)&(bat_yr["striker"]==en)].sort_values("year") if not bat_yr.empty else pd.DataFrame()
                    # BUG FIX: this used to require >1 year of data before
                    # showing ANYTHING here — for any player with just one
                    # season recorded (very common for debutants, not just
                    # override-added players), the entire Charts tab
                    # silently showed nothing at all, with no explanation.
                    # A single-season bar chart is still real, useful
                    # information — only a multi-point LINE trend
                    # genuinely needs 2+ points to mean anything.
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
    page_banner("⚔️","Head to Head","Pick two players and see who dominates across formats","#1a0808","#2e1210","#8a3226")
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
                # V12 extra: average comparison over years
                fy2=px.line(combined,x="year",y="average",color="player",markers=True,
                            title=f"Batting Average — {fmt}",
                            color_discrete_map={p1n:FC["ODI"],p2n:FC["Test"]})
                fy2.update_traces(line=dict(width=3),marker=dict(size=9))
                fy2.update_layout(**BASE,height=300,margin=dict(l=50,r=20,t=48,b=40))
                fy2.update_xaxes(title="Year",tickmode="linear",dtick=2,showgrid=True,gridcolor=GRID)
                fy2.update_yaxes(title="Average",showgrid=True,gridcolor=GRID)
                st.plotly_chart(fy2,**CFG)

            # ── Radar chart comparison ────────────────────────────────────────
            st.markdown("### 🕸️ Head-to-Head Radar")
            st.markdown('<div class="ca-insight">Each axis is <strong>normalized 0–100</strong> relative to both players — so the shape shows who dominates which dimension, not raw values. A larger filled area = more rounded player.</div>', unsafe_allow_html=True)
            radar_metrics=["average","strike_rate","boundary_pct","dot_pct"]
            radar_labels=["Average","Strike Rate","Boundary %","Dot %"]
            # Normalize each metric 0-100 across both players for radar
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
                # Scatter: innings vs average per venue — reveals consistency
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
                # Dominance scatter: innings vs average per opponent
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
                    # Quadrant lines
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
    page_banner("🤜","Batter vs Bowler","The ultimate matchup — who has the edge ball by ball?","#1a0a08","#2e1410","#8a3226")
    mt=st.radio("Look up a...",["Batter","Bowler"],horizontal=True)
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
    page_banner("📈","Performance Over Years","Track how a player has evolved season by season","#141008","#241c10","#e3b431")
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
                # V12 bonus: dot ball % over years
                if "dot_pct" in by.columns:
                    ch(line(by,"year","dot_pct","Dot Ball % by Year","#00cec9"),240)
                st.dataframe(by[["year","matches","wickets","economy","average","dot_pct","balls"]].reset_index(drop=True) if "balls" in by.columns else by[["year","matches","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ══ LEADERBOARD ═══════════════════════════════════════════════════════════════
elif section=="🏆 Leaderboard":
    page_banner("🏆","Leaderboard","The greatest — ranked by format and stat","#1a1608","#2e2610","#e3b431")
    fmt=st.radio("Format",ALL_FMT,horizontal=True)
    tab1,tab2=st.tabs(["🏏 Batting","🎳 Bowling"])
    with tab1:
        bs=bat_fmt[bat_fmt["format"]==fmt]
        c1,c2=st.columns(2)
        sb=c1.selectbox("Rank by",["runs","average","strike_rate","sixes","hundreds","player_score"])
        mr=c2.slider("Min runs",0,3000,200,100); tn=st.slider("Top N",5,50,20)
        lb=bs[bs["runs"]>=mr].sort_values(sb,ascending=False).head(tn).reset_index(drop=True)
        lb.insert(0,"Rank",range(1,len(lb)+1))
        ch(bar_h(lb,sb,"striker",sb,"Teal",f"Top {tn} {fmt} Batters — {sb}"))
        # Scatter: runs vs average — the classic "who's elite" plot
        if "runs" in lb.columns and "average" in lb.columns and len(lb)>=4:
            st.markdown("#### 💠 Runs vs Average — The Elite Quadrant")
            st.markdown('<div class="ca-insight"><strong>Top-right</strong> = high volume AND high quality. <strong>Color</strong> = strike rate. The dotted lines are median splits — names above both lines are the true greats of this format.</div>', unsafe_allow_html=True)
            st.caption("Top-right = high volume AND high quality. The true greats live there.")
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
        ws=bowl_fmt[bowl_fmt["format"]==fmt]
        c1,c2=st.columns(2)
        sb2=c1.selectbox("Rank by",["wickets","economy","average","dot_pct","five_wkts"])
        mw=c2.slider("Min wickets",0,100,10,5); tn2=st.slider("Top N bowlers",5,50,20)
        lb2=ws[ws["wickets"]>=mw].sort_values(sb2,ascending=(sb2 in ["economy","average"])).head(tn2).reset_index(drop=True)
        lb2.insert(0,"Rank",range(1,len(lb2)+1))
        ch(bar_h(lb2,"wickets","bowler","economy","Sunset",f"Top {tn2} {fmt} Bowlers"))
        # Scatter: wickets vs economy
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
        show_cols2=[c for c in ["Rank","bowler","matches","wickets","economy","average","five_wkts","best_bowling"] if c in lb2.columns]
        st.dataframe(lb2[show_cols2].reset_index(drop=True))

# ══ SIMILAR PLAYERS ═══════════════════════════════════════════════════════════
elif section=="🤖 Similar Players":
    page_banner("🤖","Similar Players","ML-powered: find cricketers who play just like your favourite","#0a0d14","#141c2e","#8a95a8")
    st.markdown("Uses **KMeans clustering + cosine similarity** on career stats to find statistically similar players.")
    st_type=st.radio("Type",["Batter","Bowler"],horizontal=True)
    name=player_input("Player name",resolve("Babar"),key="leaderboard_player"); fmt=st.radio("Format",ALL_FMT,horizontal=True)
    if name:
        sname=resolve(name)
        if st_type=="Batter":
            src=find_rows(bat_sim[bat_sim["format"]==fmt],"striker",sname)
            if len(src)==0:
                has_bowl=not find_rows(bowl_sim[bowl_sim["format"]==fmt],"bowler",sname).empty
                hint=" (They appear as a Bowler — try switching to Bowler above.)" if has_bowl else ""
                st.error(f"No ML data for '{name}' in {fmt}. They may have <200 runs.{hint}")
            else:
                p=src.iloc[0]; cluster=int(p["cluster"])
                same=bat_sim[(bat_sim["cluster"]==cluster)&(bat_sim["format"]==fmt)]
                same=same[~same["striker"].str.contains(sname,case=False,na=False)]
                same=same.sort_values("average",ascending=False).head(12)
                st.subheader(f"Players most similar to {p['striker']} in {fmt}")
                st.caption(f"⭐ Player Score: {p.get('player_score','—')} | Cluster #{cluster} | {len(same)} similar players found")
                ch(bar_h(same,"average","striker","average","Purples",f"Similar batters — {fmt}"))
                # Show compact player cards for top 4 matches
                st.markdown("#### 🎴 Top Similar Players")
                top4=same.head(4)["striker"].tolist()
                card_cols=st.columns(min(len(top4),2))
                for i,pname_s in enumerate(top4):
                    with card_cols[i%2]:
                        show_player_card(pname_s,pname_s,fmt,compact=True)
                st.dataframe(same[["striker","runs","average","strike_rate","boundary_pct","player_score"]].reset_index(drop=True))
        else:
            src=find_rows(bowl_sim[bowl_sim["format"]==fmt],"bowler",sname)
            if len(src)==0:
                has_bat=not find_rows(bat_sim[bat_sim["format"]==fmt],"striker",sname).empty
                hint=" (They appear as a Batter — try switching to Batter above.)" if has_bat else ""
                st.error(f"No ML data for '{name}' in {fmt}. They may have <20 wickets.{hint}")
            else:
                p=src.iloc[0]; cluster=int(p["cluster"])
                same=bowl_sim[(bowl_sim["cluster"]==cluster)&(bowl_sim["format"]==fmt)]
                same=same[~same["bowler"].str.contains(sname,case=False,na=False)]
                same=same.sort_values("wickets",ascending=False).head(12)
                st.subheader(f"Bowlers most similar to {p['bowler']} in {fmt}")
                st.caption(f"Cluster #{cluster} | {len(same)} similar bowlers found")
                ch(bar_h(same,"wickets","bowler","economy","Reds",f"Similar bowlers — {fmt}"))
                top4b=same.head(4)["bowler"].tolist()
                st.markdown("#### 🎴 Top Similar Bowlers")
                card_cols2=st.columns(min(len(top4b),2))
                for i,bname_s in enumerate(top4b):
                    with card_cols2[i%2]:
                        show_player_card(bname_s,bname_s,fmt,compact=True)
                st.dataframe(same[["bowler","wickets","economy","average","dot_pct"]].reset_index(drop=True))

# ══ FORM & RATINGS ════════════════════════════════════════════════════════════
elif section=="🔥 Form & Ratings":
    page_banner("🔥","Form & Ratings","Player form by year, career trend, and who's peaking right now","#1a0d08","#2e1810","#8a3226")
    fmt=st.radio("Format",ALL_FMT,horizontal=True)
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
                    latest=pyr.iloc[-1]; prev=pyr.iloc[-2] if len(pyr)>1 else latest
                    metrics({"Latest Year":int(latest["year"]),"Runs":f"{int(latest['runs']):,}",
                             "Avg (latest)":round(float(latest["average"]),1),
                             "SR (latest)":round(float(latest["strike_rate"]),1),
                             "Matches":int(latest["matches"])})
                    # Form delta badges vs career
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
                    metrics({"Latest Year":int(latest["year"]),"Wickets":int(latest["wickets"]),
                             "Economy (latest)":round(float(latest["economy"]),2),
                             "Average (latest)":round(float(latest["average"]),1),
                             "Matches":int(latest["matches"])})
                    # Form delta badges vs career
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
                    # V12 bonus: dot ball % trend
                    if "dot_pct" in pyr.columns:
                        fig_dot=px.line(pyr,x="year",y="dot_pct",markers=True,title=f"{pname} — Dot Ball % by Year")
                        fig_dot.update_traces(line=dict(color="#00cec9",width=3),marker=dict(size=8,color="#00cec9"))
                        fig_dot.update_layout(**BASE,height=260,margin=M_DEFAULT)
                        st.plotly_chart(fig_dot,**CFG)
                    show_cols=[c for c in ["year","matches","wickets","economy","average","dot_pct","balls"] if c in pyr.columns]
                    st.dataframe(pyr[show_cols].reset_index(drop=True))

    # ── Tab 2: Hot List ───────────────────────────────────────────────────────
    with tab2:
        ftype2=st.radio("Type",["Batting","Bowling"],horizontal=True,key="hot_type")
        n_yrs=st.slider("Recent window (years)",1,5,1,key="hot_yrs")
        min_inn=st.slider("Min innings",3,20,5,key="hot_inn")
        if ftype2=="Batting" and not bat_yr.empty:
            latest_yr=bat_yr["year"].max()
            recent=bat_yr[(bat_yr["format"]==fmt)&(bat_yr["year"]>=latest_yr-n_yrs+1)]
            if not bat_fmt.empty:
                gb=set(bat_fmt[(bat_fmt["format"]==fmt)&(bat_fmt["runs"]>=200)]["striker"].unique())
                recent=recent[recent["striker"].isin(gb)]
            agg=recent.groupby("striker").agg(innings=("matches","sum"),runs=("runs","sum"),
                avg=("average","mean"),sr=("strike_rate","mean"),fours=("fours","sum"),sixes=("sixes","sum")).reset_index()
            agg=agg[agg["innings"]>=min_inn].sort_values("avg",ascending=False).head(25)
            agg["avg"]=agg["avg"].round(1); agg["sr"]=agg["sr"].round(1)
            if len(agg)>0:
                mo=st.selectbox("Rank by",["avg","sr","runs","sixes"],key="hot_bat_m")
                ch(bar_h(agg.sort_values(mo,ascending=False),mo,"striker",mo,"Oranges",f"🔥 Top Batters — {mo} (last {n_yrs}yr, {fmt})"))
                st.dataframe(agg[["striker","innings","runs","avg","sr","fours","sixes"]].reset_index(drop=True))
            else: st.info("No batters meet the minimum innings threshold.")
        elif ftype2=="Bowling" and not bowl_yr.empty:
            latest_yr=bowl_yr["year"].max()
            recent=bowl_yr[(bowl_yr["format"]==fmt)&(bowl_yr["year"]>=latest_yr-n_yrs+1)]
            if not bowl_fmt.empty:
                gb=set(bowl_fmt[(bowl_fmt["format"]==fmt)&(bowl_fmt["wickets"]>=20)]["bowler"].unique())
                recent=recent[recent["bowler"].isin(gb)]
            agg=recent.groupby("bowler").agg(innings=("matches","sum"),wickets=("wickets","sum"),
                econ=("economy","mean"),avg=("average","mean"),dot_pct=("dot_pct","mean")).reset_index()
            agg=agg[agg["innings"]>=min_inn].sort_values("wickets",ascending=False).head(25)
            agg["econ"]=agg["econ"].round(2); agg["avg"]=agg["avg"].round(1)
            if len(agg)>0:
                mo=st.selectbox("Rank by",["wickets","econ","avg","dot_pct"],key="hot_bowl_m")
                ch(bar_h(agg.sort_values(mo,ascending=(mo in ["econ","avg"])),mo,"bowler",mo,"Reds",f"🔥 Top Bowlers — {mo} (last {n_yrs}yr, {fmt})"))
                st.dataframe(agg[["bowler","innings","wickets","econ","avg","dot_pct"]].reset_index(drop=True))
            else: st.info("No bowlers meet the minimum innings threshold.")

    # ── Tab 3: Cold List ──────────────────────────────────────────────────────
    with tab3:
        ftype3=st.radio("Type",["Batting","Bowling"],horizontal=True,key="cold_type")
        min_career=st.slider("Min career matches",5,30,10,key="cold_min")
        if ftype3=="Batting" and not bat_form.empty:
            src=bat_form[bat_form["format"]==fmt].copy()
            src=src.merge(bat_fmt[bat_fmt["format"]==fmt][["striker","matches","runs"]],on="striker",how="left")
            src=src[(src["runs"]>=200)&(src["matches"]>=min_career)]
            cold=src[src["form_score"]<80].sort_values("form_score").head(20)
            if len(cold)>0:
                ch(bar_h(cold,"form_score","striker","form_score","Reds",f"📉 Struggling Batters ({fmt})"))
                sc=[c for c in ["striker","form_label","form_score","recent_avg","career_avg","recent_sr","career_sr"] if c in cold.columns]
                st.dataframe(cold[sc].reset_index(drop=True))
            else: st.info("No batters in poor form right now.")
        elif ftype3=="Bowling" and not bowl_form.empty:
            src2=bowl_form[bowl_form["format"]==fmt].copy()
            src2=src2.merge(bowl_fmt[bowl_fmt["format"]==fmt][["bowler","matches","wickets"]],on="bowler",how="left")
            src2=src2[(src2["wickets"]>=20)&(src2["matches"]>=min_career)]
            cold2=src2[src2["form_score"]<80].sort_values("form_score").head(20)
            if len(cold2)>0:
                ch(bar_h(cold2,"form_score","bowler","form_score","Reds",f"📉 Struggling Bowlers ({fmt})"))
                sc2=[c for c in ["bowler","form_label","form_score","recent_econ","career_econ","recent_avg","career_avg"] if c in cold2.columns]
                st.dataframe(cold2[sc2].reset_index(drop=True))
            else: st.info("No bowlers in poor form right now.")

    # ── Tab 4: Player Scores ──────────────────────────────────────────────────
    with tab4:
        ps_type=st.radio("Type",["Batting","Bowling"],horizontal=True,key="ps_type")
        if ps_type=="Batting":
            ps=bat_sim[bat_sim["format"]==fmt].sort_values("player_score",ascending=False).head(25) if not bat_sim.empty else pd.DataFrame()
            if len(ps)>0:
                ch(bar_h(ps,"player_score","striker","player_score","Teal",f"⭐ Top 25 Batter Scores ({fmt})"))
                st.caption("Score = Average 30% · Strike Rate 25% · Boundary% 20% · Runs volume 15% · Non-dot% 10%")
                st.dataframe(ps[["striker","player_score","average","strike_rate","boundary_pct","runs"]].reset_index(drop=True))
            else: st.info(f"No batting player score data for {fmt} yet.")
        else:
            ps2=bowl_sim[bowl_sim["format"]==fmt].sort_values("player_score",ascending=False).head(25) if not bowl_sim.empty else pd.DataFrame()
            if len(ps2)>0:
                ch(bar_h(ps2,"player_score","bowler","player_score","Purples",f"⭐ Top 25 Bowler Scores ({fmt})"))
                st.caption("Score = Wickets volume 30% · Economy 25% · Average 25% · Dot Ball% 20%")
                show_bowl=[c for c in ["bowler","player_score","wickets","economy","average","dot_pct"] if c in ps2.columns]
                st.dataframe(ps2[show_bowl].reset_index(drop=True))
            else: st.info(f"No bowling player score data for {fmt} yet.")

st.markdown('</div>', unsafe_allow_html=True)

# ── Diagnostics panel ─────────────────────────────────────────────────────────
# Collects everything logged by load() and get_wiki() during this session so
# missing data has a visible, debuggable trail instead of just looking like
# "some stuff is randomly blank." Only shows up if something actually failed.
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
