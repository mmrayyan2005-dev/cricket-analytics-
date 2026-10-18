"""
Cricket Analytics dashboard — v18 (built for the v15 notebook outputs).

Everything on screen is written in plain English: no jargon without a one-line explanation,
every page starts with "what is this?", and empty / missing data always gives a friendly message
instead of an error.
"""
import io
import re
import difflib
import inspect
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

try:
    from groq import Groq
except Exception:          # the chat bot is optional — the rest of the app works without it
    Groq = None

st.set_page_config(page_title="Cricket Analytics", layout="wide", page_icon="🏏",
                   initial_sidebar_state="expanded")

RAW_BASE = "https://raw.githubusercontent.com/mmrayyan2005-dev/cricket-analytics_-/main"

# ══════════════════════════════════════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════════════════════════════════════
IS_LIGHT = st.session_state.get("is_light_mode", False)
if IS_LIGHT:
    BG, CARD, TEXT, GRID = "#f2f5fc", "#ffffff", "#0e1730", "#e3e8f5"
    SURFACE, BORDER, MUTED, SUBTLE = "#ffffff", "#e3e8f5", "#71799c", "#3d4870"
    SHADOW = "0 6px 22px rgba(15,30,80,.08)"
    ACCENT, ACCENT2 = "#ff5a1f", "#2557e8"
    ACC_RGB, ACC2_RGB = "255,90,31", "37,87,232"
else:
    BG, CARD, TEXT, GRID = "#0a1024", "#131b3a", "#f3f6ff", "#28345f"
    SURFACE, BORDER, MUTED, SUBTLE = "#0d1430", "#28345f", "#8189b3", "#c7cdea"
    SHADOW = "0 10px 32px rgba(0,6,30,.5)"
    ACCENT, ACCENT2 = "#ff6a2e", "#3d7bff"
    ACC_RGB, ACC2_RGB = "255,106,46", "61,123,255"

FORMATS = ["ODI", "Test", "T20I", "IPL", "PSL", "WPL", "BBL", "CPL", "SA20", "NT20"]
FC = {"ODI": "#3f7a52", "Test": "#8a95a8", "T20I": "#ff6a2e", "IPL": "#3d7bff", "PSL": "#2f8f5b",
      "WPL": "#b2557a", "BBL": "#d9772b", "CPL": "#2f9aa0", "SA20": "#8e5bd9", "NT20": "#c0392b"}
FORMAT_ICON = {"ODI": "🌐", "Test": "🏛️", "T20I": "⚡", "IPL": "🏏", "PSL": "🟢", "WPL": "🌹",
               "BBL": "🔥", "CPL": "🌊", "SA20": "🦁", "NT20": "🌧️"}
FORMAT_LONG = {
    "ODI": "ODI — One-Day Internationals (50 overs a side)",
    "Test": "Test — five-day international matches",
    "T20I": "T20I — Twenty20 Internationals",
    "IPL": "IPL — Indian Premier League",
    "PSL": "PSL — Pakistan Super League",
    "WPL": "WPL — Women's Premier League (India)",
    "BBL": "BBL — Big Bash League (Australia)",
    "CPL": "CPL — Caribbean Premier League",
    "SA20": "SA20 — South Africa's T20 league",
    "NT20": "T20 Blast — England's county T20 competition (listed as NT20)",
}
FMT_NAME = {"NT20": "T20 Blast"}


def fl(f):
    """Friendly format name."""
    return FMT_NAME.get(f, f)


GENDER_NAME = {"male": "Men's", "female": "Women's"}

BASE = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=TEXT, family="Inter,sans-serif", size=12),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
            xaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, color=TEXT, fixedrange=True),
            yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, color=TEXT, fixedrange=True),
            dragmode=False,
            hoverlabel=dict(bgcolor=CARD, bordercolor=ACCENT, font=dict(color=TEXT, size=12)),
            hovermode="closest")
M_DEFAULT = dict(l=8, r=8, t=48, b=8)
M_BARV = dict(l=8, r=8, t=48, b=60)
PCFG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False, "responsive": True}


def _stretch(fn):
    """Streamlit renamed `use_container_width=True` to `width='stretch'`; support both."""
    try:
        params = inspect.signature(fn).parameters
    except Exception:
        params = {}
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


PLT, DF, BTN = _stretch(st.plotly_chart), _stretch(st.dataframe), _stretch(st.button)

ROOT_CSS = (":root{--bg:%s;--surface:%s;--card:%s;--border:%s;--accent:%s;--accent2:%s;"
            "--accent-rgb:%s;--accent2-rgb:%s;--text:%s;--muted:%s;--subtle:%s;--shadow:%s;"
            "--radius:16px;--radius-sm:12px;--radius-pill:999px;}"
            % (BG, SURFACE, CARD, BORDER, ACCENT, ACCENT2, ACC_RGB, ACC2_RGB, TEXT, MUTED, SUBTLE, SHADOW))

STATIC_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
.stApp{background-color:var(--bg);color:var(--text);
  background-image:radial-gradient(ellipse 900px 460px at 50% -8%, rgba(var(--accent2-rgb),.14) 0%, transparent 62%),
  radial-gradient(ellipse 700px 400px at 100% 0%, rgba(var(--accent-rgb),.08) 0%, transparent 60%);background-attachment:fixed}
.block-container{padding-top:2.2rem!important;padding-bottom:4rem!important;max-width:1180px!important}
footer{visibility:hidden}
header[data-testid="stHeader"]{background:transparent}
h1,h2,h3,h4,h5{font-family:'Poppins',sans-serif!important;color:var(--text)!important;letter-spacing:-.2px}
h4{font-size:16px!important;margin:18px 0 8px!important}
.stMarkdown,.stMarkdown p,.stMarkdown li,[data-testid="stWidgetLabel"] p,label{color:var(--text)!important}
[data-testid="stCaptionContainer"]{color:var(--muted)!important;font-size:12px!important;line-height:1.55!important}
hr{border:none!important;border-top:1px solid var(--border)!important;margin:18px 0!important}

/* sidebar */
[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border)!important}
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stSidebarContent"]{padding:4px 14px 30px!important}
.ca-brand{display:flex;align-items:center;gap:10px;padding:6px 4px 12px;border-bottom:1px solid var(--border);margin-bottom:6px}
.ca-brand-text{font-family:'Poppins',sans-serif;font-size:17px;font-weight:800;color:var(--text)}
.ca-brand-text span{background:linear-gradient(120deg,var(--accent2),var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.ca-status{font-size:11px;color:var(--muted);margin:0 0 12px 2px}
.ca-nav-group{font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);margin:16px 4px 6px}
[data-testid="stSidebar"] [data-testid="stButton"] button{width:100%!important;text-align:left!important;justify-content:flex-start!important;
  background:transparent!important;border:1px solid transparent!important;border-radius:10px!important;color:var(--subtle)!important;
  font-weight:600!important;font-size:13px!important;padding:8px 12px!important;margin-bottom:2px!important;box-shadow:none!important}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{background:rgba(var(--accent2-rgb),.10)!important;color:var(--text)!important}
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;
  color:#fff!important;border:none!important;box-shadow:0 4px 14px rgba(var(--accent-rgb),.28)!important}

/* chat launcher */
.st-key-ca_chat_corner{position:fixed;top:58px;right:24px;z-index:999999;width:auto}
.st-key-ca_chat_corner [data-testid="stPopover"]>button,.st-key-ca_chat_corner [data-testid="stPopoverButton"]{
  background:linear-gradient(120deg,var(--accent2),var(--accent))!important;color:#fff!important;border:none!important;
  border-radius:var(--radius-pill)!important;font-weight:700!important;font-size:12.5px!important;padding:8px 18px!important;
  box-shadow:0 6px 18px rgba(var(--accent-rgb),.35)!important;white-space:nowrap!important}

/* number cards */
[data-testid="stMetric"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius)!important;
  padding:14px 16px!important;position:relative;overflow:hidden;box-shadow:var(--shadow)}
[data-testid="stMetric"]::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--accent2),var(--accent))}
[data-testid="stMetricLabel"]{font-size:11px!important;font-weight:700!important;color:var(--muted)!important}
[data-testid="stMetricLabel"] p{color:var(--muted)!important}
[data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace!important;font-size:22px!important;font-weight:700!important;color:var(--text)!important}
.element-container:has([data-testid="stMetric"]){margin-bottom:8px!important}

/* tabs, radios, inputs */
div[data-baseweb="tab-list"]{gap:6px!important;flex-wrap:wrap!important;border-bottom:1px solid var(--border)!important;padding-bottom:8px!important}
div[data-baseweb="tab"]{border-radius:var(--radius-pill)!important;padding:7px 16px!important;background:var(--card)!important;font-weight:700!important;
  font-size:12.5px!important;color:var(--subtle)!important;border:1px solid var(--border)!important}
div[data-baseweb="tab"][aria-selected="true"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;border-color:transparent!important;color:#fff!important}
div[data-baseweb="tab-highlight"],div[data-baseweb="tab-border"]{display:none!important}
[data-testid="stRadio"]>div{flex-wrap:wrap!important;gap:8px!important}
[data-testid="stRadio"] label{display:flex!important;align-items:center!important;background:var(--card)!important;border:1px solid var(--border)!important;
  border-radius:var(--radius-pill)!important;padding:7px 15px!important;font-size:12.5px!important;font-weight:700!important;color:var(--subtle)!important;cursor:pointer}
[data-testid="stRadio"] label>div:first-child{display:none!important}
[data-testid="stRadio"] label:hover{border-color:var(--accent)!important}
[data-testid="stRadio"] label:has(input:checked){border-color:transparent!important;color:#fff!important;background:linear-gradient(120deg,var(--accent2),var(--accent))!important}
[data-testid="stRadio"] label:has(input:checked) p{color:#fff!important}
[data-testid="stTextInput"] input{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-pill)!important;
  color:var(--text)!important;font-size:14px!important;padding:11px 18px!important}
[data-testid="stTextInput"] input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(var(--accent-rgb),.18)!important}
[data-testid="stSelectbox"]>div>div{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;color:var(--text)!important}
div[data-baseweb="popover"] ul,ul[role="listbox"]{background:var(--card)!important}
li[role="option"]{color:var(--text)!important}
button[kind="primary"]{background:linear-gradient(120deg,var(--accent2),var(--accent))!important;border:none!important;border-radius:var(--radius-pill)!important;color:#fff!important;font-weight:700!important}
button[kind="secondary"]{border-radius:var(--radius-pill)!important}
[data-testid="stExpander"]{border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important;background:var(--card)!important}
[data-testid="stExpander"] summary p{color:var(--subtle)!important;font-weight:700!important}
[data-testid="stAlert"]{border-radius:var(--radius-sm)!important}
.stDataFrame{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important}
[data-testid="stPlotlyChart"]{border-radius:var(--radius)!important;overflow:hidden!important;border:1px solid var(--border)!important;background:var(--card)!important;box-shadow:var(--shadow)}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:var(--radius)!important}

/* banner, tips, pills, record cards */
.ca-banner{display:flex;align-items:center;gap:16px;padding:18px 22px;border-radius:var(--radius);margin:0 0 18px 0;
  background:linear-gradient(120deg,var(--accent2),var(--accent));box-shadow:var(--shadow)}
.ca-banner-icon{font-size:34px;line-height:1}
.ca-banner-title{font-family:'Poppins',sans-serif;color:#fff;font-size:20px;font-weight:800;line-height:1.2}
.ca-banner-sub{color:rgba(255,255,255,.88);font-size:13px;margin-top:3px}
.ca-insight{background:rgba(var(--accent2-rgb),.08);border:1px solid rgba(var(--accent2-rgb),.25);border-radius:var(--radius-sm);
  padding:11px 15px;margin:4px 0 14px;font-size:13px;color:var(--subtle);line-height:1.6}
.ca-insight b{color:var(--text)}
.ca-pill{background:rgba(var(--accent2-rgb),.10);border:1px solid rgba(var(--accent2-rgb),.28);padding:3px 11px;border-radius:var(--radius-pill);
  font-size:11px;font-weight:700;white-space:nowrap;display:inline-block;margin:2px 3px 2px 0}
.ca-big{font-family:'Poppins',sans-serif;font-size:34px;font-weight:800;color:var(--text);line-height:1.1}
.ca-bigsub{font-size:13px;color:var(--muted)}
.ca-record{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:15px 17px;box-shadow:var(--shadow)}
.ca-record .lbl{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.ca-record .nm{font-family:'Poppins',sans-serif;font-size:16px;font-weight:800;color:var(--text);margin-top:5px}
.ca-record .val{font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:800;margin-top:2px}
.ca-record .sub{font-size:11px;color:var(--subtle);margin-top:2px}
@media (max-width:640px){
  .block-container{padding-left:.8rem!important;padding-right:.8rem!important}
  .st-key-ca_chat_corner{top:50px;right:10px}
  [data-testid="stMetricValue"]{font-size:18px!important}
  [data-testid="stHorizontalBlock"]{flex-direction:column!important;gap:8px!important}
  [data-testid="stHorizontalBlock"]>div[data-testid="column"]{width:100%!important;min-width:100%!important;flex:1 1 100%!important}
}
"""
st.markdown(f"<style>{ROOT_CSS}{STATIC_CSS}</style>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PLAIN-LANGUAGE WORDS
# ══════════════════════════════════════════════════════════════════════════════
GLOSSARY = {
    "batting average": "Runs a batter scores, on average, for every time they get out. Higher = more consistent run-scorer.",
    "runs per dismissal": "Runs a batter scores, on average, for every time they get out. Higher = better.",
    "scoring speed": "Runs scored per 100 balls faced. Higher = scores faster.",
    "runs per 100 balls": "Runs scored per 100 balls faced. Higher = scores faster.",
    "no-run balls": "Share of balls where no run was scored. For a batter, lower is better; for a bowler, higher is better.",
    "boundary": "Share of balls hit for four or six.",
    "centuries": "Innings of 100 runs or more.",
    "half-centuries": "Innings of 50 to 99 runs.",
    "best score": "The highest score in a single innings.",
    "ducks": "Times the batter was out without scoring.",
    "times out": "How many times the batter got out.",
    "overall rating": "A 0–100 score comparing this player with the other regular players of the same format (50 = typical, 90+ = elite). "
                      "Only players with enough games get a rating.",
    "runs per over": "Runs a bowler gives away per over (6 balls). Lower = harder to score against.",
    "runs per wicket": "Runs a bowler gives away for each wicket taken. Lower = better.",
    "balls per wicket": "Balls bowled for each wicket taken. Lower = takes wickets more often.",
    "5-wicket": "Innings where the bowler took five or more wickets.",
    "best figures": "Best bowling in one innings, written wickets/runs (e.g. 5/23 = 5 wickets for 23 runs).",
    "wickets": "Batters the bowler has got out.",
    "matches": "Matches played (in the data).",
    "runs": "Total runs scored.",
    "team strength": "A rating (called Elo) that goes up when a team wins and down when it loses, more so against strong teams. 1500 = average.",
    "form score": "100 = playing exactly as well as their own career level over the last 2 years. Above = better than usual, below = worse.",
}


def glossary_help(label):
    low = label.lower()
    for term, text in GLOSSARY.items():
        if term in low:
            return text
    return None


BAT_COLS = {"striker": "Batter", "matches": "Matches", "innings": "Innings", "runs": "Runs", "average": "Runs per dismissal",
            "strike_rate": "Runs per 100 balls", "fours": "Fours", "sixes": "Sixes", "hundreds": "Centuries",
            "fifties": "Half-centuries", "highest": "Best score", "player_score": "Overall rating", "dot_pct": "No-run balls %",
            "boundary_pct": "Boundary %", "balls_faced": "Balls faced", "dismissals": "Times out", "year": "Year",
            "opponent": "Against", "venue": "Ground", "bowler": "Bowler", "format": "Format"}
BOWL_COLS = {"bowler": "Bowler", "matches": "Matches", "innings": "Innings", "wickets": "Wickets", "economy": "Runs per over",
             "average": "Runs per wicket", "strike_rate": "Balls per wicket", "dot_pct": "No-run balls %",
             "five_wkts": "5-wicket hauls", "best_bowling": "Best figures", "player_score": "Overall rating", "overs": "Overs",
             "balls": "Balls", "runs_given": "Runs given", "year": "Year", "opponent": "Against", "venue": "Ground",
             "striker": "Batter", "balls_bowled": "Balls bowled", "format": "Format"}

BAT_RANK = {"Most runs": "runs", "Best batting average": "average", "Fastest scoring": "strike_rate",
            "Most sixes": "sixes", "Most centuries": "hundreds", "Highest overall rating": "player_score"}
BOWL_RANK = {"Most wickets": "wickets", "Fewest runs per over": "economy", "Fewest runs per wicket": "average",
             "Most no-run balls": "dot_pct", "Most 5-wicket hauls": "five_wkts", "Highest overall rating": "player_score"}
LOWER_IS_BETTER = {"economy", "average_bowl"}

FORM_WORDS = {"On Fire": "🔥 On fire", "Good": "👍 Good form", "Average": "😐 Steady", "Poor": "📉 Struggling",
              "Not enough data": "Not enough recent games"}
FORM_COLOR = {"On Fire": "#ff6a2e", "Good": "#2f8f5b", "Average": "#8a95a8", "Poor": "#c0392b"}
LOAD_ORDER = ["Light load", "Normal load", "Heavy load", "Very heavy load"]
LOAD_WORDS = {"Light load": "🟢 Light", "Normal load": "🟡 Normal", "Heavy load": "🟠 Heavy", "Very heavy load": "🔴 Very heavy"}

# ══════════════════════════════════════════════════════════════════════════════
# SMALL HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def isnum(x):
    try:
        return bool(pd.notna(x)) and bool(np.isfinite(float(x)))
    except Exception:
        return False


def fnum(x, nd=1, dash="—"):
    return f"{float(x):,.{nd}f}" if isnum(x) else dash


def fint(x, dash="—"):
    return f"{int(round(float(x))):,}" if isnum(x) else dash


def pct(x, nd=1):
    return f"{float(x):.{nd}f}%" if isnum(x) else "—"


def avg_text(avg, dism):
    if isnum(avg):
        return fnum(avg, 1)
    return "Never out" if isnum(dism) and float(dism) == 0 else "—"


def pretty_date(s):
    try:
        return pd.to_datetime(s).strftime("%d %b %Y")
    except Exception:
        return str(s) if s else "—"


def ordered(fs):
    return sorted([f for f in fs if pd.notna(f)], key=lambda x: FORMATS.index(x) if x in FORMATS else 99)


def metrics(d, per_row=3):
    items = list(d.items())
    for i in range(0, len(items), per_row):
        chunk = items[i:i + per_row]
        cols = st.columns(len(chunk))
        for c, (k, v) in zip(cols, chunk):
            c.metric(k, v, help=glossary_help(k))


def banner(emoji, title, sub):
    st.markdown(f'<div class="ca-banner"><div class="ca-banner-icon">{emoji}</div><div>'
                f'<div class="ca-banner-title">{title}</div><div class="ca-banner-sub">{sub}</div></div></div>',
                unsafe_allow_html=True)


def tip(html):
    st.markdown(f'<div class="ca-insight">{html}</div>', unsafe_allow_html=True)


def nice_table(df, cols, kind="bat", extra=None):
    """Show a table with plain-English column names."""
    if df is None or df.empty:
        return
    names = dict(BAT_COLS if kind == "bat" else BOWL_COLS)
    if extra:
        names.update(extra)
    cols = [c for c in cols if c in df.columns]
    out = df[cols].rename(columns=names).reset_index(drop=True)
    st.dataframe(out, hide_index=True, **DF)


# ── chart helpers (all return an already-styled figure; show() draws it) ─────────
def style(fig, h=380, margin=None):
    fig.update_layout(**BASE, height=h, margin=margin or M_DEFAULT)
    return fig


def show(fig):
    st.plotly_chart(fig, config=PCFG, **PLT)


def bar_h(df, x, y, title, scale="Blues", xlabel="", min_h=360):
    df = df.dropna(subset=[x])
    if df.empty:
        return None
    h = max(min_h, len(df) * 46 + 90)
    xmax = float(df[x].max()) * 1.22 or 1
    fig = px.bar(df, x=x, y=y, orientation="h", color=x, color_continuous_scale=scale, title=title)
    fig.update_traces(marker_line_width=0, text=df[x].round(1).astype(str), textposition="outside",
                      textfont=dict(size=11, color=TEXT), cliponaxis=False,
                      hovertemplate="<b>%{y}</b><br>" + (xlabel or x) + ": <b>%{x:.1f}</b><extra></extra>")
    fig.update_layout(**BASE, height=h, coloraxis_showscale=False, margin=dict(l=20, r=90, t=48, b=8), bargap=0.28)
    fig.update_yaxes(categoryorder="total ascending", showgrid=False, title="", tickfont=dict(size=12, color=TEXT),
                     automargin=True, tickmode="linear")
    fig.update_xaxes(showgrid=True, gridcolor=GRID, title=xlabel, tickfont=dict(size=11), range=[0, xmax])
    return fig


def bar_v(df, x, y, title, color, h=340, ylabel=""):
    if df is None or df.empty:
        return None
    fig = px.bar(df, x=x, y=y, text=y, title=title, color_discrete_sequence=[color])
    fig.update_traces(textposition="outside", textfont=dict(size=11, color=TEXT), marker_line_width=0,
                      hovertemplate="<b>%{x}</b><br>" + (ylabel or y) + ": <b>%{y}</b><extra></extra>")
    fig.update_layout(**BASE, height=h, showlegend=False, margin=M_BARV)
    fig.update_xaxes(tickmode="linear", tickangle=-40, showgrid=False, automargin=True, title="")
    fig.update_yaxes(showgrid=True, gridcolor=GRID, title=ylabel)
    if x == "year":
        fig.update_xaxes(dtick=1, tickformat="d")
    return fig


def line(df, x, y, title, color, h=280, ylabel="", ref=None, ref_label=""):
    d = df.dropna(subset=[y]) if df is not None else None
    if d is None or d.empty:
        return None
    fig = px.line(d, x=x, y=y, markers=True, title=title)
    fig.update_traces(line=dict(color=color, width=3), marker=dict(size=8, color=color, line=dict(width=2, color=BG)),
                      hovertemplate="<b>%{x}</b><br>" + (ylabel or y) + ": <b>%{y:.2f}</b><extra></extra>")
    fig.update_layout(**BASE, height=h, margin=M_DEFAULT)
    fig.update_yaxes(title=ylabel)
    if ref is not None and isnum(ref):
        fig.add_hline(y=float(ref), line_dash="dash", line_color="#fdcb6e", annotation_text=ref_label,
                      annotation_position="bottom right", annotation_font=dict(color="#fdcb6e", size=11))
    if x == "year":
        fig.update_xaxes(dtick=1, tickformat="d", title="")
    return fig


def donut(labels, values, colors, title):
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.55,
                           marker=dict(colors=colors, line=dict(color=BG, width=3)),
                           textinfo="percent+label", textfont=dict(size=13, color=TEXT),
                           hovertemplate="<b>%{label}</b><br>%{value:,}<br>%{percent}<extra></extra>"))
    fig.update_layout(**BASE, height=320, title=title, showlegend=False, margin=M_DEFAULT)
    return fig


def show_or_note(fig, note="Not enough data to draw this chart."):
    if fig is None:
        st.caption(note)
    else:
        show(fig)


def record_card(label, name, value, sub, color):
    return (f'<div class="ca-record"><div class="lbl">{label}</div><div class="nm">{name}</div>'
            f'<div class="val" style="color:{color}">{value}</div><div class="sub">{sub}</div></div>')


def record_grid(cards):
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:18px">'
                + "".join(cards) + "</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════
CSV_FILES = [
    "cricket_batting_stats.csv", "cricket_bowling_stats.csv", "cricket_batting_by_format.csv", "cricket_bowling_by_format.csv",
    "cricket_batting_yearly.csv", "cricket_bowling_yearly.csv", "cricket_batting_venue.csv", "cricket_batting_opponent.csv",
    "cricket_bowling_venue.csv", "cricket_bowling_opponent.csv", "cricket_batter_vs_bowler.csv", "cricket_bowler_vs_batter.csv",
    "cricket_bat_form_ratings.csv", "cricket_bowl_form_ratings.csv", "cricket_bat_similarity.csv", "cricket_bowl_similarity.csv",
    "cricket_player_registry.csv",
]


def _fetch_one(name):
    try:
        r = requests.get(f"{RAW_BASE}/{name}", timeout=25)
        r.raise_for_status()
        return name, r.content, None
    except Exception as e:
        return name, None, str(e)


@st.cache_data(ttl=3600, show_spinner=False)
def load():
    fetched, errors = {}, []
    with ThreadPoolExecutor(max_workers=len(CSV_FILES)) as ex:       # network calls in parallel (safe)
        for name, content, err in ex.map(_fetch_one, CSV_FILES):
            fetched[name] = content
            if err:
                errors.append((name, err))
    out = {}
    for name in CSV_FILES:                                            # parsing one by one (pandas is not thread-safe)
        content = fetched.get(name)
        if content is None:
            out[name] = pd.DataFrame()
            continue
        try:
            out[name] = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            out[name] = pd.DataFrame()
            errors.append((name, str(e)))
    return out, errors


@st.cache_data(ttl=3600, show_spinner=False)
def get_csv(name):
    """Optional / page-specific files. Missing file = empty table (pages show a friendly message)."""
    try:
        return pd.read_csv(f"{RAW_BASE}/{name}")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_last_updated():
    try:
        r = requests.get(f"{RAW_BASE}/last_updated.txt", timeout=6)
        if r.status_code == 200:
            return r.text.strip()
    except Exception:
        pass
    return None


def freshness():
    txt = get_last_updated()
    upd = cut = None
    if txt:
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        upd = lines[0] if lines else None
        for l in lines[1:]:
            if "cutoff" in l.lower():
                cut = l.split(":", 1)[-1].strip()
    return upd, cut


with st.spinner("Loading cricket data…"):
    D, load_errors = load()

batting, bowling = D["cricket_batting_stats.csv"], D["cricket_bowling_stats.csv"]
bat_fmt, bowl_fmt = D["cricket_batting_by_format.csv"], D["cricket_bowling_by_format.csv"]
bat_yr, bowl_yr = D["cricket_batting_yearly.csv"], D["cricket_bowling_yearly.csv"]
bat_ven, bat_opp = D["cricket_batting_venue.csv"], D["cricket_batting_opponent.csv"]
bowl_ven, bowl_opp = D["cricket_bowling_venue.csv"], D["cricket_bowling_opponent.csv"]
bvb, wvb = D["cricket_batter_vs_bowler.csv"], D["cricket_bowler_vs_batter.csv"]
bat_form, bowl_form = D["cricket_bat_form_ratings.csv"], D["cricket_bowl_form_ratings.csv"]
bat_sim, bowl_sim = D["cricket_bat_similarity.csv"], D["cricket_bowl_similarity.csv"]
REG = D["cricket_player_registry.csv"]

if bat_fmt.empty and bowl_fmt.empty:
    st.error("😕 The cricket data couldn't be loaded right now. Please check your internet connection, "
             "then press **🔄 Refresh** in the left menu. If it keeps happening, the data files in the GitHub repository may be missing.")
    for name, err in load_errors[:5]:
        st.caption(f"{name}: {err}")
    st.stop()

ALL_FMT = ordered(set(bat_fmt["format"].dropna()) | set(bowl_fmt["format"].dropna())) or FORMATS

# ── player name index (names are Cricsheet's stable-id based labels) ───────────────
_names = set()
for _df, _c in ((bat_fmt, "striker"), (bowl_fmt, "bowler")):
    if not _df.empty and _c in _df.columns:
        _names.update(_df[_c].dropna().astype(str).tolist())
NAME_SET = _names
NAME_LIST = sorted(_names)
NAME_LOWER = {n.lower(): n for n in NAME_LIST}
REG_INFO = {}
if not REG.empty and {"label", "spellings"}.issubset(REG.columns):
    _m = REG["matches"] if "matches" in REG.columns else pd.Series(0, index=REG.index)
    REG_INFO = {l: (s, m) for l, s, m in zip(REG["label"], REG["spellings"].astype(str), _m)}

NAME_ALIASES = {
    "steve smith": "SPD Smith", "smith": "SPD Smith", "hazelwood": "JR Hazlewood", "hazlewood": "JR Hazlewood",
    "warner": "DA Warner", "david warner": "DA Warner", "rohit": "RG Sharma", "rohit sharma": "RG Sharma",
    "bumrah": "JJ Bumrah", "jasprit bumrah": "JJ Bumrah", "starc": "MA Starc", "mitchell starc": "MA Starc",
    "kohli": "V Kohli", "virat kohli": "V Kohli", "virat": "V Kohli", "babar": "Babar Azam", "stokes": "BA Stokes",
    "ben stokes": "BA Stokes", "root": "JE Root", "joe root": "JE Root", "anderson": "JM Anderson", "broad": "SCJ Broad",
    "buttler": "JC Buttler", "jos buttler": "JC Buttler", "maxwell": "GJ Maxwell", "dhoni": "MS Dhoni",
    "tendulkar": "SR Tendulkar", "sachin": "SR Tendulkar", "ponting": "RT Ponting", "sangakkara": "KC Sangakkara",
    "malinga": "SL Malinga", "shaheen": "Shaheen Shah Afridi", "rizwan": "Mohammad Rizwan", "rashid": "Rashid Khan",
    "smriti": "S Mandhana", "mandhana": "S Mandhana", "smriti mandhana": "S Mandhana", "harmanpreet": "H Kaur",
    "healy": "AJ Healy", "perry": "EA Perry", "kl rahul": "KL Rahul", "rahul": "KL Rahul",
}


def candidate_players(q, limit=15):
    """Every spelling of every person is searched (e.g. 'Virat' finds 'V Kohli'). Best-known players come first."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    out = []
    al = NAME_ALIASES.get(q.lower())
    if al and al in NAME_SET:
        out.append(al)
    if q in NAME_SET:
        out.append(q)
    elif q.lower() in NAME_LOWER:
        out.append(NAME_LOWER[q.lower()])
    pat = r"(?i)\b" + re.escape(q)
    if not REG.empty and "spellings" in REG.columns and "label" in REG.columns:
        m = REG[REG["spellings"].astype(str).str.contains(pat, na=False, regex=True)]
        m = m[m["label"].isin(NAME_SET)]
        if "matches" in m.columns:
            m = m.sort_values("matches", ascending=False)
        out += m["label"].tolist()[:limit * 2]
    if len(out) < limit:
        rx = re.compile(pat)
        out += [n for n in NAME_LIST if rx.search(n)][:limit * 2]
    return list(dict.fromkeys(out))[:limit]


def cand_label(label):
    info = REG_INFO.get(label)
    if not info:
        return label
    spell, m = info
    others = [s.strip() for s in spell.split("|") if s.strip() and s.strip() != label]
    extra = f" (also written {', '.join(others)[:40]})" if others else ""
    n = f" · {int(m)} matches" if isnum(m) else ""
    return f"{label}{extra}{n}"


def best_name(label):
    info = REG_INFO.get(label)
    if info:
        sp = [s.strip() for s in info[0].split("|") if s.strip()]
        if sp:
            return max(sp, key=len)
    return label


def _set_q(key, val):
    st.session_state[key] = val


def player_search(label, default, key, role=""):
    """One friendly search box: type any part of a name, then pick from the matches."""
    q = st.text_input(label, value=default, key=f"{key}_q", placeholder="Type a name — e.g. Kohli, Babar Azam, Smriti Mandhana")
    cands = candidate_players(q)
    if not cands:
        if q.strip():
            close = difflib.get_close_matches(q, NAME_LIST, n=4, cutoff=0.55)
            st.warning(f"We couldn't find anyone called “{q}”. Check the spelling, or try just the surname.")
            if close:
                st.caption("Did you mean:")
                for s in close:
                    st.button(s, key=f"{key}_sug_{s}", on_click=_set_q, args=(f"{key}_q", s))
            else:
                st.caption("If this is a very recent debutant, they may not be in the data yet — new matches usually appear after 2–3 days.")
        return None
    if len(cands) == 1:
        return cands[0]
    return st.selectbox("Several players match — which one do you mean?", cands, format_func=cand_label, key=f"{key}_sel")


def rows(df, col, label):
    if df is None or df.empty or col not in df.columns:
        return pd.DataFrame({"format": []})
    return df[df[col] == label]


def fmt_pick(options, key, label="Format"):
    options = list(options)
    if not options:
        return None
    return st.radio(label, options, format_func=fl, horizontal=True, key=key)


def gender_pick(df, key):
    """Men's / women's cricket are never mixed together."""
    if df is None or df.empty or "gender" not in df.columns:
        return df, None
    gs = [g for g in ("male", "female") if g in set(df["gender"].dropna())]
    if not gs:
        return df, None
    if len(gs) == 1:
        return df[df["gender"] == gs[0]], gs[0]
    g = st.radio("Show", gs, format_func=lambda x: GENDER_NAME[x] + " cricket", horizontal=True, key=key)
    return df[df["gender"] == g], g


# ── Wikipedia photo + bio (optional extra; stats never depend on it) ─────────────
WIKI_NAMES = {
    "V Kohli": "Virat Kohli", "SPD Smith": "Steve Smith cricketer", "DA Warner": "David Warner cricketer", "RG Sharma": "Rohit Sharma",
    "JJ Bumrah": "Jasprit Bumrah", "MA Starc": "Mitchell Starc", "JR Hazlewood": "Josh Hazlewood", "BA Stokes": "Ben Stokes",
    "JE Root": "Joe Root", "JM Anderson": "James Anderson cricketer", "SCJ Broad": "Stuart Broad", "KC Sangakkara": "Kumar Sangakkara",
    "SR Tendulkar": "Sachin Tendulkar", "RT Ponting": "Ricky Ponting", "SL Malinga": "Lasith Malinga", "JC Buttler": "Jos Buttler",
    "GJ Maxwell": "Glenn Maxwell cricketer", "S Mandhana": "Smriti Mandhana", "H Kaur": "Harmanpreet Kaur", "AJ Healy": "Alyssa Healy",
    "EA Perry": "Ellyse Perry", "KL Rahul": "KL Rahul cricketer", "NR Sciver": "Nat Sciver-Brunt", "AMC Kerr": "Amelia Kerr",
}
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _clean_wiki(v):
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", v)
    v = re.sub(r"\{\{[^}]*\}\}", "", v)
    return re.sub(r"<[^>]+>", "", v).strip()


@st.cache_data(ttl=3600, show_spinner=False)
def get_wiki(label, search_name):
    ua = {"User-Agent": "CricketAnalyticsApp/3.0"}
    try:
        query = WIKI_NAMES.get(label) or f"{search_name} cricketer"
        sr = requests.get("https://en.wikipedia.org/w/api.php", timeout=8, headers=ua,
                          params={"action": "query", "list": "search", "srsearch": query, "format": "json", "utf8": 1, "srlimit": 5})
        sr.raise_for_status()
        results = sr.json().get("query", {}).get("search", [])
        if not results:
            return None
        target = (WIKI_NAMES.get(label) or search_name).replace(" cricketer", "").lower()

        def score(r):
            snip = re.sub(r"<[^>]+>", "", r.get("snippet", "")).lower()
            sim = difflib.SequenceMatcher(None, target, r.get("title", "").lower().replace("(cricketer)", "").strip()).ratio()
            s = sim * 20 + (3 if "cricket" in snip else 0)
            if any(w in snip for w in ("footballer", "actor", "musician", "politician")) and "cricket" not in snip:
                s -= 5
            return s - (15 if sim < 0.4 else 0)

        best = max(results, key=score)
        if score(best) <= 0:
            return None                                   # no confident match → no card, rather than a wrong person
        title = best["title"]
        rr = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_"), timeout=8, headers=ua)
        rr.raise_for_status()
        data = rr.json()
        if data.get("type") == "disambiguation":
            return None
        bio = data.get("extract", "")
        sents = [s.strip() for s in bio.split(". ") if len(s.strip()) > 15]
        bio = ". ".join(sents[:3]) + ("." if sents and not sents[-1].endswith(".") else "")
        born, role = "", ""
        try:
            ir = requests.get("https://en.wikipedia.org/w/api.php", timeout=8, headers=ua,
                              params={"action": "query", "titles": title, "prop": "revisions", "rvprop": "content",
                                      "rvslots": "main", "format": "json", "rvsection": 0})
            pages = ir.json().get("query", {}).get("pages", {})
            wt = next(iter(pages.values())).get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
            m = re.search(r"\{\{\s*birth date(?: and age)?\s*\|([^}]+)\}\}", wt, re.I)
            if m:
                nums = [p.strip() for p in m.group(1).split("|") if p.strip().isdigit()]
                if len(nums) >= 3 and 1 <= int(nums[1]) <= 12:
                    born = f"{int(nums[2])} {MONTHS[int(nums[1])]} {nums[0]}"
            rm = re.search(r"\|\s*role\s*=\s*([^\n|]+)", wt, re.I)
            if rm:
                role = _clean_wiki(rm.group(1))
        except Exception:
            pass
        return {"title": data.get("title", title), "bio": bio, "img": data.get("thumbnail", {}).get("source", ""),
                "born": born, "role": role or data.get("description", "")[:60]}
    except Exception:
        return None


def show_player_card(label, compact=False):
    card = get_wiki(label, best_name(label))
    with st.container(border=True):
        if not card:
            st.markdown(f"#### {label}")
            st.caption("No photo or bio found for this name — the numbers below are not affected.")
            return
        ic, tc = st.columns([1, 9] if not compact else [1, 12], gap="small")
        with ic:
            if card["img"]:
                st.image(card["img"], width=72 if compact else 96)
        with tc:
            st.markdown(("##### " if compact else "#### ") + card["title"])
            bits = []
            if card["born"]:
                bits.append(f"🎂 Born {card['born']}")
            if card["role"]:
                bits.append(f"🏏 {card['role'][:40]}")
            if bits:
                st.caption("  •  ".join(bits))
            if card["bio"] and not compact:
                st.caption(card["bio"])
        if not compact:
            st.caption("Photo and bio come from Wikipedia and may occasionally belong to a different person with the same name.")


# ══════════════════════════════════════════════════════════════════════════════
# PREDICTION HELPERS (win probability model)
# ══════════════════════════════════════════════════════════════════════════════
WP_FEATURES = ["elo_diff", "form_diff", "team1_h2h_rate", "venue_diff", "toss_advantage", "toss_field",
               "toss_x_field", "toss_known", "min_matches_played"]


@st.cache_resource(ttl=3600, show_spinner=False)
def load_wp_model():
    try:
        import pickle
        r = requests.get(f"{RAW_BASE}/win_probability_model.pkl", timeout=40)
        r.raise_for_status()
        return pickle.loads(r.content)
    except Exception:
        return None


def _wp_mirror(X):
    M = X.copy()
    M["elo_diff"], M["form_diff"], M["venue_diff"] = -X["elo_diff"], -X["form_diff"], -X["venue_diff"]
    M["team1_h2h_rate"], M["toss_advantage"], M["toss_x_field"] = 1 - X["team1_h2h_rate"], 1 - X["toss_advantage"], -X["toss_x_field"]
    return M


def wp_probability(model, elo_diff, form_diff, h2h_rate, venue_diff, min_played, team_a_won_toss=None, toss_choice=None):
    """P(team A wins). Same recipe the notebook used. Unknown toss info is averaged over every possibility."""
    elo_only = 1 / (1 + 10 ** (-elo_diff / 400))
    if model is None:
        return float(elo_only), False
    rows_ = []
    for ta in ([team_a_won_toss] if team_a_won_toss is not None else [True, False]):
        for d in ([toss_choice] if toss_choice else ["bat", "field"]):
            tw, tf = (1 if ta else 0), (1 if d == "field" else 0)
            rows_.append({"elo_diff": elo_diff, "form_diff": form_diff, "team1_h2h_rate": h2h_rate, "venue_diff": venue_diff,
                          "toss_advantage": tw, "toss_field": tf, "toss_x_field": (2 * tw - 1) * (2 * tf - 1),
                          "toss_known": 1, "min_matches_played": min_played})
    X = pd.DataFrame(rows_)[WP_FEATURES]
    try:
        p = 0.5 * (model.predict_proba(X)[:, 1] + 1 - model.predict_proba(_wp_mirror(X))[:, 1])
        return float(p.mean()), True
    except Exception:
        return float(elo_only), False


RECOGNIZED_TEAMS = {"Afghanistan", "Australia", "Bangladesh", "England", "India", "Ireland", "New Zealand", "Pakistan", "South Africa",
                    "Sri Lanka", "West Indies", "Zimbabwe", "Scotland", "Netherlands", "Nepal", "UAE", "United Arab Emirates",
                    "Namibia", "Oman", "USA", "United States of America", "Canada", "Papua New Guinea", "Kenya", "Uganda",
                    "Hong Kong", "Singapore", "Malaysia", "Bermuda", "Jersey", "Guernsey", "Italy", "Germany", "Denmark", "Qatar",
                    "Saudi Arabia", "Kuwait", "Bahrain", "Tanzania", "Nigeria", "Botswana", "Ghana", "Japan", "Thailand"}


def is_real_country(name):
    return name in RECOGNIZED_TEAMS


def mval(mdf, model, metric):
    if mdf is None or mdf.empty or not {"model", "metric", "value"}.issubset(mdf.columns):
        return None
    s = mdf[(mdf["model"] == model) & (mdf["metric"] == metric)]["value"]
    return float(s.iloc[0]) if len(s) and isnum(s.iloc[0]) else None


def best_win_model(mdf):
    """The notebook keeps whichever of the two models had the lower log-loss on validation; both are listed in the metrics file."""
    a = mval(mdf, "win_probability_Logistic Regression", "LogLoss")
    b = mval(mdf, "win_probability_Random Forest", "LogLoss")
    cands = {k: v for k, v in {"Logistic Regression": a, "Random Forest": b}.items() if v is not None}
    return min(cands, key=cands.get) if cands else None


# ══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════
HOME = "🏠 Home"
P_FIND, P_COMPARE, P_YEARS = "🔍 Find a Player", "⚔️ Compare Two Players", "📈 Career by Year"
P_WHERE, P_BVB = "🏟️ Grounds & Opponents", "🤜 Batter vs Bowler"
P_TOP, P_LEAGUE, P_FORM, P_SIM = "🏆 Top Players", "🏅 League Records", "🔥 Who's in Form", "🤖 Similar Players"
P_RESULTS, P_WIN = "📋 Match Results", "🎯 Who Will Win?"
P_RUNS, P_WORK = "🔮 Run Forecast", "💪 Bowler Workload"
P_ABOUT = "ℹ️ About This Data"

PAGE_GROUPS = [
    (None, [HOME]),
    ("Players", [P_FIND, P_COMPARE, P_YEARS, P_WHERE, P_BVB]),
    ("Rankings", [P_TOP, P_LEAGUE, P_FORM, P_SIM]),
    ("Matches & predictions", [P_RESULTS, P_WIN, P_RUNS, P_WORK]),
    ("Help", [P_ABOUT]),
]

if "page" not in st.session_state:
    st.session_state["page"] = HOME
if "nav_history" not in st.session_state:
    st.session_state["nav_history"] = []


def goto(page):
    cur = st.session_state.get("page", HOME)
    if cur != page:
        st.session_state["nav_history"].append(cur)
        st.session_state["page"] = page


def go_back():
    hist = st.session_state.get("nav_history", [])
    if hist:
        st.session_state["page"] = hist.pop()


def _refresh():
    st.cache_data.clear()
    st.cache_resource.clear()


section = st.session_state["page"]
upd, cutoff = freshness()

with st.sidebar:
    st.markdown('<div class="ca-brand"><span style="font-size:26px">🏏</span>'
                '<span class="ca-brand-text">Cricket<span>Analytics</span></span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ca-status">Data up to <b>{pretty_date(cutoff)}</b></div>' if cutoff else
                '<div class="ca-status">Powered by Cricsheet data</div>', unsafe_allow_html=True)
    u1, u2 = st.columns(2)
    with u1:
        st.button("🔄 Refresh", help="Reload the newest data now", key="_refresh_btn", on_click=_refresh)
    with u2:
        st.toggle("☀️ Light" if not IS_LIGHT else "🌙 Dark", key="is_light_mode", help="Switch between dark and light colours")
    for group_label, group_pages in PAGE_GROUPS:
        if group_label:
            st.markdown(f'<div class="ca-nav-group">{group_label}</div>', unsafe_allow_html=True)
        for p in group_pages:
            st.button(p, key=f"nav_{p}", on_click=goto, args=(p,), type="primary" if section == p else "secondary", **BTN)

# ══════════════════════════════════════════════════════════════════════════════
# CRICKET CHAT BOT (optional)
# ══════════════════════════════════════════════════════════════════════════════
STOPWORDS = set("""what is are was were the a an of in on at to for and or who how much many did does do has have had score scores highest
best top most runs run wicket wickets average strike rate economy stats stat statistics career total number tell me about compare vs
versus between player batting bowling match matches game games odi odis test tests t20 t20i ipl psl bbl cpl wpl format overall record
records hundred hundreds fifty fifties century centuries when where why which his her he she their it this that currently current hit
hits get gets got with from you i can please know out all time times win wins won lost lose team teams""".split())


def get_player_stats_context(query):
    words = [w.strip(".,?!") for w in query.split()]
    phrases = []
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            pw = words[i:i + n]
            if any(w.lower() in STOPWORDS or len(w) < 2 for w in pw):
                continue
            phrases.append(" ".join(pw))
    blocks, seen = [], set()
    for ph in phrases:
        if len(blocks) >= 3 or len(ph) < 3:
            continue
        c = candidate_players(ph, limit=1)
        if not c or c[0] in seen:
            continue
        name = c[0]
        seen.add(name)
        lines = []
        for _, r in rows(bat_fmt, "striker", name).iterrows():
            lines.append(f"  {r['format']}: {r['matches']} matches, {r['runs']} runs, average {r.get('average')}, strike rate {r.get('strike_rate')}, "
                         f"{r.get('hundreds')} hundreds, {r.get('fifties')} fifties, best {r.get('highest')}")
        if lines:
            blocks.append(f"{name} — batting:\n" + "\n".join(lines))
        lines = []
        for _, r in rows(bowl_fmt, "bowler", name).iterrows():
            lines.append(f"  {r['format']}: {r['matches']} matches, {r['wickets']} wickets, average {r.get('average')}, "
                         f"economy {r.get('economy')}, best {r.get('best_bowling')}")
        if lines:
            blocks.append(f"{name} — bowling:\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def render_cricket_chat():
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    with st.popover("🤖 Ask the Cricket Bot"):
        st.markdown("**🏏 Ask me anything about cricket**")
        st.caption("For example: “How many runs has Babar Azam scored in ODIs?” or “What is a googly?”")
        box = st.container(height=300)
        with box:
            for m in st.session_state.chat_messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
        with st.form(key="cricket_chat_form", clear_on_submit=True):
            q = st.text_input("Your question", label_visibility="collapsed", placeholder="Type your question here…")
            sent = st.form_submit_button("Send")
            if sent and q:
                st.session_state.chat_messages.append({"role": "user", "content": q})
                try:
                    key = st.secrets.get("GROQ_API_KEY", "")
                except Exception:
                    key = ""
                if Groq is None:
                    reply = "The chat bot isn't installed on this server yet (the `groq` package is missing)."
                elif not key:
                    reply = "The chat bot isn't switched on yet — a GROQ_API_KEY needs to be added to the app's secrets."
                else:
                    ctx = get_player_stats_context(q)
                    sysmsg = ("You are a friendly cricket assistant inside a cricket dashboard. Explain things simply, as to a beginner. "
                              "If the dashboard data below is relevant, use those exact numbers and never invent statistics.\n\n")
                    if ctx:
                        sysmsg += f"--- Dashboard data ---\n{ctx}\n--- End data ---"
                    try:
                        resp = Groq(api_key=key).chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "system", "content": sysmsg}] + st.session_state.chat_messages[-10:])
                        reply = resp.choices[0].message.content
                    except Exception as e:
                        reply = f"Sorry, the chat bot could not answer just now ({e})."
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.rerun()


with st.container(key="ca_chat_corner"):
    render_cricket_chat()

if section != HOME and st.session_state.get("nav_history"):
    prev = st.session_state["nav_history"][-1]
    st.button(f"← Back to {' '.join(prev.split()[1:]) or prev}", key="_back_btn", on_click=go_back)

# ══════════════════════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════════════════════


def _home_search():
    q = st.session_state.get("home_q", "").strip()
    if q:
        st.session_state["ps_q"] = q
        goto(P_FIND)


def page_home():
    pills = "".join(f'<span class="ca-pill" style="color:{FC.get(f, ACCENT)}">{FORMAT_ICON.get(f, "🏏")} {fl(f)}</span>' for f in ALL_FMT)
    fresh = f"Data up to {pretty_date(cutoff)}" if cutoff else "Ball-by-ball data from Cricsheet"
    st.markdown(f"""<div class="ca-banner" style="padding:26px 26px;flex-direction:column;align-items:flex-start;gap:8px">
      <div class="ca-banner-title" style="font-size:28px">🏏 Cricket Analytics</div>
      <div class="ca-banner-sub" style="font-size:14px">Look up any player, compare players, and see which team is more likely to win — explained in plain English.</div>
      <div style="margin-top:6px">{pills}</div>
      <div class="ca-banner-sub" style="margin-top:4px">📅 {fresh}</div></div>""", unsafe_allow_html=True)

    st.markdown("#### 🔍 Start here — search for a player")
    st.text_input("Player", placeholder="Type a name and press Enter — Kohli, Babar Azam, Smriti Mandhana, Bumrah…",
                  key="home_q", label_visibility="collapsed", on_change=_home_search)

    st.markdown("#### What would you like to do?")
    features = [
        ("🔍", "Find a player", "See any player's career numbers and form", P_FIND),
        ("⚔️", "Compare two players", "Who is better? Side by side", P_COMPARE),
        ("🎯", "Who will win?", "Pick two teams and see their chances", P_WIN),
        ("🔮", "Run forecast", "How many runs might a batter score next season?", P_RUNS),
        ("🏆", "Top players", "The best batters and bowlers in each format", P_TOP),
        ("🔥", "Who's in form?", "Who is playing well (or badly) right now", P_FORM),
        ("💪", "Bowler workload", "Who has been bowling a lot lately?", P_WORK),
        ("📋", "Match results", "Every past result, by team", P_RESULTS),
        ("🏟️", "Grounds & opponents", "Where and against whom a player does best", P_WHERE),
        ("🤜", "Batter vs bowler", "How a batter fares against a bowler", P_BVB),
        ("🏅", "League records", "IPL, PSL, BBL… record books", P_LEAGUE),
        ("🤖", "Similar players", "Players who play in a similar style", P_SIM),
    ]
    cols = st.columns(4)
    for i, (emoji, title, desc, target) in enumerate(features):
        with cols[i % 4]:
            st.button(f"{emoji} **{title}**\n\n{desc}", key=f"feat_{i}", on_click=goto, args=(target,), **BTN)

    st.markdown("---")
    st.markdown("#### 🏆 Quick look — the top 5")
    f = fmt_pick(ALL_FMT, "home_fmt")
    bs, _ = gender_pick(bat_fmt[bat_fmt["format"] == f], "home_g")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Most runs**")
        t = bs.sort_values("runs", ascending=False).head(5)
        nice_table(t, ["striker", "matches", "runs", "average"], "bat")
    with c2:
        st.markdown("**Most wickets**")
        ws = bowl_fmt[bowl_fmt["format"] == f]
        if "gender" in ws.columns and "gender" in bs.columns and len(bs):
            ws = ws[ws["gender"] == bs["gender"].iloc[0]]
        nice_table(ws.sort_values("wickets", ascending=False).head(5), ["bowler", "matches", "wickets", "economy"], "bowl")

    with st.expander("📖 New to cricket stats? What the words mean"):
        items = [(k, v) for k, v in GLOSSARY.items() if k not in ("runs per dismissal", "runs per 100 balls", "matches", "runs")]
        gc = st.columns(2)
        for i, (term, text) in enumerate(items):
            gc[i % 2].markdown(f"**{term.capitalize()}** — {text}")
        st.caption("Every number card in this app also has a small **?** you can hover over for its meaning.")
    st.caption("NT20 in the data means England's T20 Blast. See **ℹ️ About This Data** for how everything works and how accurate the predictions are.")


def show_form(r, kind):
    label = r.get("form_label", "Not enough data")
    if label == "Not enough data" or not isnum(r.get("form_score")):
        st.caption("📊 Recent form: not enough games in the last 2 years to judge.")
        return
    color = FORM_COLOR.get(label, "#8a95a8")
    if kind == "bat":
        detail = (f"last 2 years: average {fnum(r.get('recent_avg'))}, speed {fnum(r.get('recent_sr'))} "
                  f"· career: average {fnum(r.get('career_avg'))}, speed {fnum(r.get('career_sr'))}")
    else:
        detail = (f"last 2 years: {fnum(r.get('recent_econ'), 2)} runs per over, {fnum(r.get('recent_avg'))} runs per wicket "
                  f"· career: {fnum(r.get('career_econ'), 2)} and {fnum(r.get('career_avg'))}")
    st.markdown(f'<span class="ca-pill" style="color:{color};border-color:{color}66">{FORM_WORDS.get(label, label)}</span> '
                f'<span style="font-size:12px;color:var(--muted)">Form score {fnum(r["form_score"], 0)} (100 = their normal level) — {detail}</span>',
                unsafe_allow_html=True)


def rating_text(p):
    s = p.get("player_score")
    if not isnum(s):
        return "Not rated"
    return f"{float(s):.0f} / 100"


def rating_caption(p):
    conf = {"High": "based on a large number of games", "Medium": "based on enough games to be fair",
            "Low": "based on a small number of games — take with a pinch of salt"}.get(p.get("score_confidence"), "")
    if isnum(p.get("player_score")):
        st.caption(f"⭐ Overall rating {float(p['player_score']):.0f}/100 compares this player with other players of the same format "
                   f"(50 = typical, 90+ = elite), {conf}.")
    else:
        st.caption("⭐ No overall rating yet — a player needs a minimum number of runs or wickets to be rated fairly.")


def batting_tab(label, fmt, p):
    m = int(p["matches"])
    avg, dism = p.get("average"), p.get("dismissals")
    avg_phrase = (f"averaging **{float(avg):.1f}** runs each time they were out" if isnum(avg)
                  else "and have never been dismissed in this data")
    st.markdown(f"**{label}** has scored **{fint(p['runs'])} runs** in **{m} {fl(fmt)} matches**, {avg_phrase}, "
                f"scoring at about **{fnum(p.get('strike_rate'), 0)} runs per 100 balls**.")
    if m < 10:
        st.caption(f"ℹ️ Only {m} match(es) in the data — a small sample, so the numbers can change a lot with one innings.")
    fr = rows(bat_form, "striker", label)
    fr = fr[fr["format"] == fmt] if "format" in fr.columns else fr
    if len(fr):
        show_form(fr.iloc[0], "bat")
    metrics({"Matches": m, "Runs": fint(p["runs"]), "Batting average": avg_text(avg, dism)})
    metrics({"Scoring speed (runs per 100 balls)": fnum(p.get("strike_rate")), "Fours": fint(p.get("fours")), "Sixes": fint(p.get("sixes"))})
    metrics({"Times out": fint(dism), "No-run balls %": pct(p.get("dot_pct")), "Boundary %": pct(p.get("boundary_pct"))})
    metrics({"Centuries (100+)": fint(p.get("hundreds")), "Half-centuries (50–99)": fint(p.get("fifties")),
             "Best score": fint(p.get("highest")), "Ducks (out for 0)": fint(p.get("ducks")), "Overall rating (0–100)": rating_text(p)})
    rating_caption(p)
    fr_, sx = int(p.get("fours", 0) or 0) * 4, int(p.get("sixes", 0) or 0) * 6
    other = max(0, int(p["runs"]) - fr_ - sx)
    if fr_ + sx + other > 0:
        show(donut(["From fours", "From sixes", "Running between wickets"], [fr_, sx, other], [FC.get(fmt, ACCENT2), "#d63031", "#636e72"],
                   "Where the runs came from"))
    proj = get_csv("cricket_player_forecast.csv")
    if not proj.empty and "striker" in proj.columns:
        pr = proj[(proj["striker"] == label) & (proj["format"] == fmt)]
        if len(pr):
            r = pr.iloc[0]
            st.info(f"🔮 **Forecast:** about **{fint(r['projected_next_season_runs'])} runs** in {r.get('projection_season', 'the next season')} "
                    f"(likely {fint(r['projected_low'])}–{fint(r['projected_high'])}) — if selected. More on the **Run Forecast** page.")


def bowling_tab(label, fmt, p):
    m = int(p["matches"])
    wk = p.get("wickets")
    st.markdown(f"**{label}** has taken **{fint(wk)} wickets** in **{m} {fl(fmt)} matches**, giving away about "
                f"**{fnum(p.get('economy'), 2)} runs per over**.")
    if m < 10:
        st.caption(f"ℹ️ Only {m} match(es) in the data — a small sample.")
    fr = rows(bowl_form, "bowler", label)
    fr = fr[fr["format"] == fmt] if "format" in fr.columns else fr
    if len(fr):
        show_form(fr.iloc[0], "bowl")
    wavg = fnum(p.get("average")) if isnum(p.get("average")) else "No wickets yet"
    wsr = fnum(p.get("strike_rate")) if isnum(p.get("strike_rate")) else "No wickets yet"
    metrics({"Matches": m, "Wickets": fint(wk), "Runs per over": fnum(p.get("economy"), 2)})
    metrics({"Runs per wicket": wavg, "Balls per wicket": wsr, "No-run balls %": pct(p.get("dot_pct"))})
    best = p.get("best_bowling")
    metrics({"5-wicket hauls": fint(p.get("five_wkts")), "Best figures": str(best) if pd.notna(best) else "—",
             "Overall rating (0–100)": rating_text(p)})
    rating_caption(p)


def page_find():
    banner("🔍", "Find a Player", "Career numbers, current form and a plain-English summary for any player")
    tip("Type any part of a name — a first name, surname or full name. Then choose a <b>format</b> (ODI, Test, IPL…) to see their numbers in it.")
    label = player_search("Player name", "Kohli", "ps")
    if not label:
        return
    b_all, w_all = rows(bat_fmt, "striker", label), rows(bowl_fmt, "bowler", label)
    avl = ordered(set(b_all["format"]) | set(w_all["format"]))
    if not avl:
        st.info(f"{label} has no recorded matches in the data yet.")
        return
    fmt = fmt_pick(avl, "ps_fmt")
    show_player_card(label)
    bat, bowl = b_all[b_all["format"] == fmt], w_all[w_all["format"] == fmt]
    names = (["🏏 Batting"] if len(bat) else []) + (["🎳 Bowling"] if len(bowl) else []) + ["📈 Year by year"]
    tabs = st.tabs(names)
    i = 0
    if len(bat):
        with tabs[i]:
            batting_tab(label, fmt, bat.iloc[0])
        i += 1
    if len(bowl):
        with tabs[i]:
            bowling_tab(label, fmt, bowl.iloc[0])
        i += 1
    with tabs[i]:
        years_view(label, fmt, bool(len(bat)), bool(len(bowl)))
    st.caption("ℹ️ Numbers come from Cricsheet's ball-by-ball records. Cricsheet doesn't cover every match ever played (especially older and "
               "some domestic matches), so career totals can be lower than official records.")


def years_view(label, fmt, has_bat, has_bowl):
    clr = FC.get(fmt, ACCENT2)
    shown = False
    if has_bat:
        by = rows(bat_yr, "striker", label)
        by = by[by["format"] == fmt].sort_values("year") if "format" in by.columns else by
        if len(by):
            shown = True
            st.markdown("**🏏 Batting, year by year**")
            show_or_note(bar_v(by, "year", "runs", "Runs scored each year", clr, ylabel="Runs"))
            if len(by) > 1:
                c1, c2 = st.columns(2)
                career = rows(bat_fmt, "striker", label)
                career = career[career["format"] == fmt]
                cavg = career["average"].iloc[0] if len(career) else None
                csr = career["strike_rate"].iloc[0] if len(career) else None
                with c1:
                    show_or_note(line(by, "year", "average", "Runs per dismissal each year", clr, 280, "Batting average", cavg, "Career"))
                with c2:
                    show_or_note(line(by, "year", "strike_rate", "Scoring speed each year", "#fbbf24", 280, "Runs per 100 balls", csr, "Career"))
            else:
                st.caption("Only one year of data so far — trend lines need at least two years.")
            nice_table(by, ["year", "matches", "runs", "average", "strike_rate", "fours", "sixes"], "bat")
    if has_bowl:
        by = rows(bowl_yr, "bowler", label)
        by = by[by["format"] == fmt].sort_values("year") if "format" in by.columns else by
        if len(by):
            shown = True
            st.markdown("**🎳 Bowling, year by year**")
            show_or_note(bar_v(by, "year", "wickets", "Wickets taken each year", "#d63031", ylabel="Wickets"))
            if len(by) > 1:
                c1, c2 = st.columns(2)
                career = rows(bowl_fmt, "bowler", label)
                career = career[career["format"] == fmt]
                with c1:
                    show_or_note(line(by, "year", "economy", "Runs per over each year", "#d63031", 280, "Runs per over",
                                      career["economy"].iloc[0] if len(career) else None, "Career"))
                with c2:
                    show_or_note(line(by, "year", "average", "Runs per wicket each year", "#6c5ce7", 280, "Runs per wicket",
                                      career["average"].iloc[0] if len(career) else None, "Career"))
            nice_table(by, ["year", "matches", "wickets", "economy", "average", "dot_pct"], "bowl")
    if not shown:
        st.caption("No year-by-year breakdown available for this player in this format.")


def page_years():
    banner("📈", "Career by Year", "See how a player's numbers have changed season by season")
    label = player_search("Player name", "Kohli", "yr")
    if not label:
        return
    b, w = rows(bat_yr, "striker", label), rows(bowl_yr, "bowler", label)
    avl = ordered(set(b["format"]) | set(w["format"]))
    if not avl:
        st.info("No year-by-year data for this player.")
        return
    fmt = fmt_pick(avl, "yr_fmt")
    years_view(label, fmt, True, True)


def _norm_pair(a, b, higher_better=True):
    a, b = (float(a) if isnum(a) else 0.0), (float(b) if isnum(b) else 0.0)
    if higher_better:
        mx = max(a, b, 1e-9)
        return round(a / mx * 100, 1), round(b / mx * 100, 1)
    vals = [v for v in (a, b) if v > 0]
    if not vals:
        return 0.0, 0.0
    mn = min(vals)
    return (round(mn / a * 100, 1) if a > 0 else 0.0), (round(mn / b * 100, 1) if b > 0 else 0.0)


def page_compare():
    banner("⚔️", "Compare Two Players", "Pick two players and see who comes out ahead")
    c1, c2 = st.columns(2)
    with c1:
        a = player_search("First player", "Kohli", "cmp1")
    with c2:
        b = player_search("Second player", "Babar Azam", "cmp2")
    kind = st.radio("Compare their…", ["Batting", "Bowling"], horizontal=True, key="cmp_kind")
    if not a or not b:
        return
    if a == b:
        st.warning("Please pick two different players.")
        return
    bat = kind == "Batting"
    src, col = (bat_fmt, "striker") if bat else (bowl_fmt, "bowler")
    ra, rb = rows(src, col, a), rows(src, col, b)
    common = ordered(set(ra["format"]) & set(rb["format"]))
    if not common:
        st.info(f"{a} and {b} don't have {kind.lower()} records in a format they have both played, so there's nothing to compare. Try the other option above.")
        return
    fmt = fmt_pick(common, "cmp_fmt")
    pa, pb = ra[ra["format"] == fmt].iloc[0], rb[rb["format"] == fmt].iloc[0]
    k1, k2 = st.columns(2)
    with k1:
        show_player_card(a, compact=True)
    with k2:
        show_player_card(b, compact=True)
    st.markdown(f"#### {'🏏' if bat else '🎳'} {kind} in {fl(fmt)}")
    if bat:
        spec = [("Matches", "matches", True, 0), ("Runs", "runs", True, 0), ("Batting average (runs per dismissal)", "average", True, 1),
                ("Scoring speed (runs per 100 balls)", "strike_rate", True, 1), ("Fours", "fours", True, 0), ("Sixes", "sixes", True, 0),
                ("Centuries", "hundreds", True, 0), ("Boundary %", "boundary_pct", True, 1), ("No-run balls % (lower is better)", "dot_pct", False, 1),
                ("Overall rating (0–100)", "player_score", True, 0)]
    else:
        spec = [("Matches", "matches", True, 0), ("Wickets", "wickets", True, 0), ("Runs per over (lower is better)", "economy", False, 2),
                ("Runs per wicket (lower is better)", "average", False, 1), ("Balls per wicket (lower is better)", "strike_rate", False, 1),
                ("No-run balls %", "dot_pct", True, 1), ("5-wicket hauls", "five_wkts", True, 0), ("Overall rating (0–100)", "player_score", True, 0)]
    table, wa, wb = [], 0, 0
    for lab, c, hib, nd in spec:
        va, vb = pa.get(c), pb.get(c)
        fa, fb = fnum(va, nd), fnum(vb, nd)
        if isnum(va) and isnum(vb) and float(va) != float(vb):
            a_better = (float(va) > float(vb)) == hib
            if c not in ("matches",):
                wa, wb = wa + a_better, wb + (not a_better)
            if a_better:
                fa += "  ✅"
            else:
                fb += "  ✅"
        table.append({"": lab, a: fa, b: fb})
    st.dataframe(pd.DataFrame(table), hide_index=True, **DF)
    if wa != wb:
        lead, n_l, n_o = (a, wa, wb) if wa > wb else (b, wb, wa)
        st.success(f"**{lead}** comes out ahead on {n_l} of {wa + wb} measures (the ✅ marks the better number).")
    else:
        st.info("It's a dead heat — they are ahead on the same number of measures.")
    st.caption("A small sample can mislead: check the number of matches before deciding who is “better”.")

    if bat:
        vol = [("Runs", "runs"), ("Fours", "fours"), ("Sixes", "sixes")]
        qual = [("Batting average", "average"), ("Runs per 100 balls", "strike_rate")]
    else:
        vol = [("Wickets", "wickets"), ("5-wicket hauls", "five_wkts")]
        qual = [("Runs per over", "economy"), ("Runs per wicket", "average")]
    for title, grp in (("Totals", vol), ("Averages and rates", qual)):
        fig = go.Figure()
        for nm, p_, colr in ((a, pa, FC["ODI"]), (b, pb, FC["Test"])):
            vals = [float(p_.get(c)) if isnum(p_.get(c)) else 0 for _, c in grp]
            fig.add_trace(go.Bar(name=nm, y=[l for l, _ in grp], x=vals, orientation="h", marker=dict(color=colr),
                                 text=[f"{v:,.1f}" for v in vals], textposition="outside", cliponaxis=False, textfont=dict(color=TEXT)))
        mx = max([float(p_.get(c)) for p_ in (pa, pb) for _, c in grp if isnum(p_.get(c))] + [1]) * 1.25
        fig.update_layout(**BASE, barmode="group", title=title, height=max(240, len(grp) * 130), margin=dict(l=20, r=90, t=48, b=8))
        fig.update_xaxes(range=[0, mx])
        fig.update_yaxes(showgrid=False, automargin=True)
        show(fig)

    st.markdown("#### 🕸️ Shape of their game")
    tip("Each corner is scored 0–100 against the <b>better of the two players</b>, and every corner is set so that <b>bigger = better</b>. "
        "A bigger shape means a more complete player.")
    if bat:
        cats = ["Batting average", "Scoring speed", "Boundary %", "Hard to dismiss in scoring balls"]
        pairs = [_norm_pair(pa.get("average"), pb.get("average")), _norm_pair(pa.get("strike_rate"), pb.get("strike_rate")),
                 _norm_pair(pa.get("boundary_pct"), pb.get("boundary_pct")),
                 _norm_pair(100 - float(pa.get("dot_pct") or 0), 100 - float(pb.get("dot_pct") or 0))]
    else:
        cats = ["Wickets", "Stingy (runs per over)", "Cheap wickets (runs per wicket)", "Quick wickets (balls per wicket)", "No-run balls"]
        pairs = [_norm_pair(pa.get("wickets"), pb.get("wickets")), _norm_pair(pa.get("economy"), pb.get("economy"), False),
                 _norm_pair(pa.get("average"), pb.get("average"), False), _norm_pair(pa.get("strike_rate"), pb.get("strike_rate"), False),
                 _norm_pair(pa.get("dot_pct"), pb.get("dot_pct"))]
    v1, v2 = [p_[0] for p_ in pairs], [p_[1] for p_ in pairs]
    fig = go.Figure()
    for nm, vv, colr in ((a, v1, FC["ODI"]), (b, v2, FC["Test"])):
        fig.add_trace(go.Scatterpolar(r=vv + vv[:1], theta=cats + cats[:1], fill="toself", name=nm, line=dict(color=colr, width=2.5), opacity=0.75))
    fig.update_layout(**BASE, height=440, margin=dict(l=60, r=60, t=40, b=40),
                      polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(visible=True, gridcolor=GRID, color=TEXT, range=[0, 105], tickfont=dict(size=9)),
                                 angularaxis=dict(gridcolor=GRID, tickfont=dict(size=11, color=TEXT))))
    show(fig)

    yr_src, yc, y_metric = (bat_yr, "striker", "runs") if bat else (bowl_yr, "bowler", "wickets")
    ya, yb = rows(yr_src, yc, a), rows(yr_src, yc, b)
    if len(ya) and len(yb) and "format" in ya.columns:
        ya, yb = ya[ya["format"] == fmt].assign(player=a), yb[yb["format"] == fmt].assign(player=b)
        both = pd.concat([ya, yb]).sort_values("year")
        if len(both):
            fig = px.line(both, x="year", y=y_metric, color="player", markers=True, title=f"{y_metric.capitalize()} each year",
                          color_discrete_map={a: FC["ODI"], b: FC["Test"]})
            fig.update_traces(line=dict(width=3), marker=dict(size=9))
            fig.update_layout(**BASE, height=340, margin=dict(l=50, r=20, t=48, b=40))
            fig.update_xaxes(dtick=1, tickformat="d", title="")
            show(fig)


def split_view(src, name_col, label, fmt, kind, dim, dim_word, key):
    d = src[(src[name_col] == label) & (src["format"] == fmt)] if len(src) else pd.DataFrame()
    if d.empty:
        st.info(f"No {kind.lower()} numbers for this player in {fl(fmt)} by {dim_word}.")
        return
    mx = int(d["innings"].max()) if "innings" in d.columns else 1
    min_inn = st.slider(f"Only count {dim_word}s where they played at least this many innings", 1, max(2, min(mx, 20)), min(2, max(1, mx)), key=f"{key}_min")
    d = d[d["innings"] >= min_inn] if "innings" in d.columns else d
    if kind == "Batting":
        opts = {"Total runs": "runs", "Batting average": "average", "Scoring speed (runs per 100 balls)": "strike_rate", "Fours": "fours", "Sixes": "sixes"}
        cols = [dim, "innings", "runs", "average", "strike_rate", "fours", "sixes"]
        scale = "Blues"
    else:
        opts = {"Wickets": "wickets", "Runs per over (lower is better)": "economy", "Runs per wicket (lower is better)": "average",
                "No-run balls %": "dot_pct"}
        cols = [dim, "innings", "wickets", "economy", "average", "dot_pct"]
        scale = "Reds"
    pick = st.selectbox("Measure", list(opts), key=f"{key}_m")
    m = opts[pick]
    asc = kind == "Bowling" and m in ("economy", "average")
    top = d.dropna(subset=[m]).sort_values(m, ascending=asc).head(15)
    fig = bar_h(top, m, dim, f"{label} — {pick} by {dim_word} ({fl(fmt)})", scale, pick)
    show_or_note(fig, f"Nothing to show — try lowering the minimum innings.")
    nice_table(d.sort_values(m, ascending=asc), cols, "bat" if kind == "Batting" else "bowl")


def page_where():
    banner("🏟️", "Grounds & Opponents", "Where does a player do best — and which teams do they find easy or hard?")
    label = player_search("Player name", "Kohli", "wh")
    if not label:
        return
    kind = st.radio("Look at their…", ["Batting", "Bowling"], horizontal=True, key="wh_kind")
    ven, opp, col = (bat_ven, bat_opp, "striker") if kind == "Batting" else (bowl_ven, bowl_opp, "bowler")
    mine = rows(ven, col, label)
    if mine.empty:
        st.info(f"No {kind.lower()} record found for this player. Try the other option above, or another spelling.")
        return
    fmt = fmt_pick(ordered(set(mine["format"])), "wh_fmt")
    t1, t2 = st.tabs(["🏟️ At each ground", "🌍 Against each team"])
    with t1:
        split_view(ven, col, label, fmt, kind, "venue", "ground", "whv")
    with t2:
        split_view(opp, col, label, fmt, kind, "opponent", "team", "who")


def page_bvb():
    banner("🤜", "Batter vs Bowler", "Who wins the battle — the batter or the bowler?")
    mode = st.radio("What do you want to see?", ["One batter against one bowler", "A batter against many bowlers",
                                                  "A bowler against many batters"], key="bvb_mode")
    if mode.startswith("One"):
        c1, c2 = st.columns(2)
        with c1:
            a = player_search("Batter", "Kohli", "bvb_a")
        with c2:
            b = player_search("Bowler", "Starc", "bvb_b")
        if not a or not b:
            return
        d = bvb[(bvb["striker"] == a) & (bvb["bowler"] == b)] if len(bvb) else pd.DataFrame()
        if d.empty:
            st.info(f"{a} hasn't faced {b} often enough in the data (we need at least 10 balls) to show a fair result.")
            return
        fmt = fmt_pick(ordered(set(d["format"])), "bvb_fmt")
        r = d[d["format"] == fmt].iloc[0]
        out = int(r["dismissals"]) if isnum(r.get("dismissals")) else 0
        st.markdown(f"In **{fl(fmt)}**, **{a}** has faced **{b}** for **{int(r['balls_faced'])} balls**, scoring **{int(r['runs'])} runs** "
                    f"({fnum(r.get('strike_rate'), 0)} runs per 100 balls) and getting out to this bowler **{out} time(s)**.")
        metrics({"Balls faced": int(r["balls_faced"]), "Runs": int(r["runs"]), "Times out": out})
        metrics({"Fours": fint(r.get("fours")), "Sixes": fint(r.get("sixes")), "No-run balls": fint(r.get("dot_balls"))})
        st.caption("Only dismissals credited to the bowler count here (not run-outs).")
        return
    if mode.startswith("A batter"):
        a = player_search("Batter", "Babar Azam", "bvb_one")
        if not a:
            return
        src = rows(bvb, "striker", a)
        if src.empty:
            st.info("Not enough face-offs recorded for this batter (we need at least 10 balls against a bowler).")
            return
        fmt = fmt_pick(ordered(set(src["format"])), "bvb_f1")
        opts = {"Balls faced": "balls_faced", "Runs scored": "runs", "Scoring speed": "strike_rate", "Times out": "dismissals"}
        pick = st.selectbox("Show the top 15 by…", list(opts), key="bvb_m1")
        d = src[src["format"] == fmt].dropna(subset=[opts[pick]]).sort_values(opts[pick], ascending=False).head(15)
        show_or_note(bar_h(d, opts[pick], "bowler", f"Bowlers {a} has faced — {pick.lower()} ({fl(fmt)})", "Greens", pick))
        nice_table(d, ["bowler", "balls_faced", "runs", "strike_rate", "dismissals"], "bat",
                   {"balls_faced": "Balls faced", "strike_rate": "Runs per 100 balls"})
    else:
        b = player_search("Bowler", "Shaheen", "bvb_two")
        if not b:
            return
        src = rows(wvb, "bowler", b)
        if src.empty:
            st.info("Not enough face-offs recorded for this bowler (we need at least 10 balls against a batter).")
            return
        fmt = fmt_pick(ordered(set(src["format"])), "bvb_f2")
        opts = {"Wickets taken": "wickets", "Balls bowled": "balls_bowled", "Runs per over": "economy", "Runs given": "runs_given"}
        pick = st.selectbox("Show the top 15 by…", list(opts), key="bvb_m2")
        asc = opts[pick] == "economy"
        d = src[src["format"] == fmt].dropna(subset=[opts[pick]]).sort_values(opts[pick], ascending=asc).head(15)
        show_or_note(bar_h(d, opts[pick], "striker", f"Batters {b} has bowled to — {pick.lower()} ({fl(fmt)})", "Reds", pick))
        nice_table(d, ["striker", "balls_bowled", "runs_given", "wickets", "economy"], "bowl")


def page_top():
    banner("🏆", "Top Players", "The best batters and bowlers, format by format")
    fmt = fmt_pick(ALL_FMT, "top_fmt")
    t1, t2 = st.tabs(["🏏 Batters", "🎳 Bowlers"])
    with t1:
        bs, _ = gender_pick(bat_fmt[bat_fmt["format"] == fmt], "top_gb")
        c1, c2, c3 = st.columns(3)
        pick = c1.selectbox("Rank by", list(BAT_RANK), key="top_bat_by")
        mr = c2.slider("At least this many runs", 0, 5000, 500, 100, key="top_bat_min")
        tn = c3.slider("How many to show", 5, 30, 15, key="top_bat_n")
        col = BAT_RANK[pick]
        lb = bs[bs["runs"] >= mr].dropna(subset=[col]).sort_values(col, ascending=False).head(tn).reset_index(drop=True)
        if lb.empty:
            st.info("No batters meet those filters — try lowering the minimum runs.")
        else:
            show_or_note(bar_h(lb, col, "striker", f"Top {len(lb)} {fl(fmt)} batters — {pick.lower()}", "Teal", pick))
            lb.insert(0, "Rank", range(1, len(lb) + 1))
            nice_table(lb, ["Rank", "striker", "matches", "runs", "average", "strike_rate", "hundreds", "highest", "player_score"], "bat", {"Rank": "Rank"})
            st.caption("Players who have never been dismissed have no batting average, so they are left out when ranking by average.")
    with t2:
        ws, _ = gender_pick(bowl_fmt[bowl_fmt["format"] == fmt], "top_gw")
        c1, c2, c3 = st.columns(3)
        pick = c1.selectbox("Rank by", list(BOWL_RANK), key="top_bowl_by")
        mw = c2.slider("At least this many wickets", 0, 300, 20, 5, key="top_bowl_min")
        tn = c3.slider("How many to show", 5, 30, 15, key="top_bowl_n")
        col = BOWL_RANK[pick]
        lb = ws[ws["wickets"] >= mw].dropna(subset=[col]).sort_values(col, ascending=col in ("economy", "average")).head(tn).reset_index(drop=True)
        if lb.empty:
            st.info("No bowlers meet those filters — try lowering the minimum wickets.")
        else:
            show_or_note(bar_h(lb, col, "bowler", f"Top {len(lb)} {fl(fmt)} bowlers — {pick.lower()}", "Sunset", pick))
            lb.insert(0, "Rank", range(1, len(lb) + 1))
            nice_table(lb, ["Rank", "bowler", "matches", "wickets", "economy", "average", "five_wkts", "best_bowling", "player_score"], "bowl", {"Rank": "Rank"})


def page_league():
    banner("🏅", "League Records", "The all-time record book for each T20 league")
    leagues = [f for f in ["IPL", "PSL", "BBL", "CPL", "WPL", "SA20", "NT20"] if f in ALL_FMT] or ALL_FMT[:1]
    league = fmt_pick(leagues, "lr_league", "League")
    colr = FC.get(league, ACCENT)
    lbs, lws = bat_fmt[bat_fmt["format"] == league], bowl_fmt[bowl_fmt["format"] == league]
    if lbs.empty and lws.empty:
        st.info(f"No {fl(league)} data available yet.")
        return
    st.caption(FORMAT_LONG.get(league, league))
    cards = []
    if not lbs.empty:
        def top(col):
            d = lbs.dropna(subset=[col])
            return d.loc[d[col].idxmax()] if len(d) else None
        for lab, col, sub in (("Most runs", "runs", "career runs in this league"), ("Highest score", "highest", "best single innings"),
                              ("Most fours", "fours", "career fours"), ("Most sixes", "sixes", "career sixes")):
            r = top(col)
            if r is not None:
                cards.append(record_card(lab, r["striker"], fint(r[col]), sub, colr))
    if not lws.empty:
        d = lws.dropna(subset=["wickets"])
        if len(d):
            r = d.loc[d["wickets"].idxmax()]
            cards.append(record_card("Most wickets", r["bowler"], fint(r["wickets"]), f"in {int(r['matches'])} matches", colr))
        if "best_wkts" in lws.columns and lws["best_wkts"].notna().any():
            d = lws.dropna(subset=["best_wkts"]).sort_values(["best_wkts"], ascending=False)
            r = d.iloc[0]
            cards.append(record_card("Best bowling in an innings", r["bowler"], str(r.get("best_bowling", "—")), "wickets / runs", colr))
    if cards:
        record_grid(cards)
    t1, t2 = st.tabs(["🏏 Batting records", "🎳 Bowling records"])
    with t1:
        if lbs.empty:
            st.caption("No batting data for this league yet.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                show_or_note(bar_h(lbs.nlargest(10, "runs"), "runs", "striker", f"Most runs — {fl(league)}", "Blues", "Runs"))
                show_or_note(bar_h(lbs.dropna(subset=["fours"]).nlargest(10, "fours"), "fours", "striker", "Most fours", "Teal", "Fours"))
            with c2:
                show_or_note(bar_h(lbs.dropna(subset=["highest"]).nlargest(10, "highest"), "highest", "striker", "Highest scores", "Oranges", "Runs"))
                show_or_note(bar_h(lbs.dropna(subset=["sixes"]).nlargest(10, "sixes"), "sixes", "striker", "Most sixes", "Purples", "Sixes"))
    with t2:
        if lws.empty:
            st.caption("No bowling data for this league yet.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                show_or_note(bar_h(lws.nlargest(10, "wickets"), "wickets", "bowler", f"Most wickets — {fl(league)}", "Reds", "Wickets"))
            with c2:
                min_ov = st.slider("Only count bowlers with at least this many overs", 5, 100, 20, key="lr_min_ov")
                pool = lws[lws["overs"] >= min_ov].dropna(subset=["economy"])
                show_or_note(bar_h(pool.nsmallest(10, "economy"), "economy", "bowler", f"Hardest to score against (min {min_ov} overs)", "Greens",
                                   "Runs per over"), "No bowlers meet that overs limit — lower the slider.")


def page_form():
    banner("🔥", "Who's in Form?", "Who is playing better — or worse — than usual over the last two years")
    tip("<b>Form score</b> compares a player's last <b>2 years</b> with their <b>own career</b>. <b>100 = playing exactly at their usual level</b>. "
        "Above 100 = better than usual, below = worse. Players with too few recent games are left out so one lucky innings can't fool us.")
    fmt = fmt_pick(ALL_FMT, "fm_fmt")
    t1, t2, t3 = st.tabs(["🔥 Hot right now", "📉 Struggling", "🔍 Check one player"])

    def table_for(kind, which):
        src_f = bat_form if kind == "Batting" else bowl_form
        base = bat_fmt if kind == "Batting" else bowl_fmt
        namec = "striker" if kind == "Batting" else "bowler"
        if src_f.empty:
            st.info("Form data isn't available yet.")
            return
        d = src_f[src_f["format"] == fmt].dropna(subset=["form_score"]).merge(
            base[base["format"] == fmt][[namec, "gender", "matches"]], on=[namec], how="left")
        d, _ = gender_pick(d, f"fm_g_{kind}_{which}")
        d = d[d["matches"].fillna(0) >= 10] if "matches" in d.columns else d
        d = d[d["form_label"].isin(["On Fire", "Good"])].sort_values("form_score", ascending=False) if which == "hot" \
            else d[d["form_label"] == "Poor"].sort_values("form_score")
        d = d.head(20).copy()
        if d.empty:
            st.info("Nobody clearly " + ("ahead of" if which == "hot" else "behind") + " their usual level right now in this format.")
            return
        d["Form"] = d["form_label"].map(FORM_WORDS)
        title = ("🔥 Best form — " if which == "hot" else "📉 Biggest dips — ") + f"{kind.lower()} ({fl(fmt)})"
        show_or_note(bar_h(d, "form_score", namec, title, "Oranges" if which == "hot" else "Reds", "Form score"))
        if kind == "Batting":
            nice_table(d, [namec, "Form", "form_score", "recent_avg", "career_avg", "recent_sr", "career_sr"], "bat",
                       {"form_score": "Form score", "recent_avg": "Average (last 2 yrs)", "career_avg": "Average (career)",
                        "recent_sr": "Speed (last 2 yrs)", "career_sr": "Speed (career)", "Form": "Form"})
        else:
            nice_table(d, [namec, "Form", "form_score", "recent_econ", "career_econ", "recent_avg", "career_avg"], "bowl",
                       {"form_score": "Form score", "recent_econ": "Runs/over (last 2 yrs)", "career_econ": "Runs/over (career)",
                        "recent_avg": "Runs/wicket (last 2 yrs)", "career_avg": "Runs/wicket (career)", "Form": "Form"})

    for tab, which in ((t1, "hot"), (t2, "cold")):
        with tab:
            kind = st.radio("Show", ["Batting", "Bowling"], horizontal=True, key=f"fm_k_{which}")
            table_for(kind, which)
    with t3:
        label = player_search("Player name", "Kohli", "fm_p")
        if label:
            kind = st.radio("Look at their…", ["Batting", "Bowling"], horizontal=True, key="fm_pk")
            src = bat_form if kind == "Batting" else bowl_form
            namec = "striker" if kind == "Batting" else "bowler"
            r = rows(src, namec, label)
            r = r[r["format"] == fmt] if "format" in r.columns else r
            if len(r):
                show_form(r.iloc[0], "bat" if kind == "Batting" else "bowl")
            else:
                st.info(f"No form rating for {label} in {fl(fmt)} — they may not have played enough in the last 2 years.")
            years_view(label, fmt, kind == "Batting", kind == "Bowling")


def _similar(sim, namec, feats, label, fmt, nlog):
    me = sim[(sim[namec] == label) & (sim["format"] == fmt)]
    if me.empty:
        return None, None
    me = me.iloc[0]
    pool = sim[(sim["format"] == fmt)]
    if "gender" in pool.columns:
        pool = pool[pool["gender"] == me.get("gender")]
    pool = pool.dropna(subset=feats).copy()
    if len(pool) < 3 or not isnum(me.get(feats[0])):
        return me, None
    X = pool[feats].astype(float).copy()
    for c in nlog:
        X[c] = np.log1p(X[c])
    mu, sd = X.mean(), X.std().replace(0, 1)
    Z = (X - mu) / sd
    ref = Z[pool[namec] == label]
    if ref.empty:
        return me, None
    dist = np.sqrt(((Z - ref.iloc[0]) ** 2).sum(axis=1))
    pool["dist"] = dist
    p95 = max(float(dist.quantile(0.95)), 1e-6)
    pool["similarity"] = (100 * (1 - pool["dist"] / p95)).clip(0, 100).round(0)
    return me, pool[pool[namec] != label].sort_values("dist").head(10)


def page_sim():
    banner("🤖", "Similar Players", "Find players whose numbers look most like your favourite player's")
    tip("We compare each player's career numbers (for batters: average, scoring speed, boundaries, no-run balls and runs; for bowlers: runs per over, "
        "runs per wicket, wickets and so on) and list the players whose <b>numbers are closest</b>. <b>100% = nearly identical.</b> Men's and women's players are compared separately.")
    kind = st.radio("Player type", ["Batter", "Bowler"], horizontal=True, key="sim_kind")
    label = player_search("Player name", "Babar Azam" if kind == "Batter" else "Bumrah", "sim")
    if not label:
        return
    sim, namec = (bat_sim, "striker") if kind == "Batter" else (bowl_sim, "bowler")
    mine = rows(sim, namec, label)
    if mine.empty:
        other = rows(bowl_sim if kind == "Batter" else bat_sim, "bowler" if kind == "Batter" else "striker", label)
        hint = f" They do appear as a {'bowler' if kind == 'Batter' else 'batter'} — switch the player type above." if len(other) else ""
        need = "200 career runs" if kind == "Batter" else "20 career wickets"
        st.info(f"{label} isn't in the similarity list — players need at least {need} in a format.{hint}")
        return
    fmt = fmt_pick(ordered(set(mine["format"])), "sim_fmt")
    feats = ["average", "strike_rate", "boundary_pct", "dot_pct", "runs"] if kind == "Batter" else ["economy", "average", "dot_pct", "strike_rate", "wickets"]
    me, res = _similar(sim, namec, feats, label, fmt, ["runs"] if kind == "Batter" else ["wickets"])
    if res is None or res.empty:
        st.info("Not enough comparable players in this format to build a list.")
        return
    st.subheader(f"Players most like {label} in {fl(fmt)}")
    show_or_note(bar_h(res, "similarity", namec, f"How similar (100% = nearly identical)", "Purples", "Similarity %"))
    top3 = res.head(3)[namec].tolist()
    st.markdown("#### 🎴 The three closest")
    cc = st.columns(3)
    for i, nm in enumerate(top3):
        with cc[i]:
            show_player_card(nm, compact=True)
    res = res.assign(similarity_pct=res["similarity"].astype(int).astype(str) + "%")
    if kind == "Batter":
        nice_table(res, [namec, "similarity_pct", "runs", "average", "strike_rate", "boundary_pct", "player_score"], "bat", {"similarity_pct": "Similarity"})
    else:
        nice_table(res, [namec, "similarity_pct", "wickets", "economy", "average", "dot_pct", "player_score"], "bowl", {"similarity_pct": "Similarity"})


def result_text(r):
    w = r.get("winner")
    if pd.isna(w):
        return "No result"
    by, mg = r.get("winner_by"), r.get("winner_margin")
    if pd.notna(by) and pd.notna(mg):
        try:
            mg = int(float(mg))
        except Exception:
            pass
        return f"{w} won by {mg} {by}"
    return f"{w} won"


def page_results():
    banner("📋", "Match Results", "Every completed match with a result — who won, where, and by how much")
    res = get_csv("cricket_matches_info.csv")
    if res.empty:
        st.info("Match results aren't available yet. They appear once the notebook has uploaded `cricket_matches_info.csv` to GitHub.")
        return
    fmt = fmt_pick(ordered(set(res["format"].dropna())), "mr_fmt", "Competition")
    rf = res[res["format"] == fmt]
    rf, _ = gender_pick(rf, "mr_g")
    if fmt in ("ODI", "Test", "T20I"):
        rf = rf[rf["team1"].apply(is_real_country) & rf["team2"].apply(is_real_country)]
    teams = sorted(set(rf["team1"].dropna()) | set(rf["team2"].dropna()))
    t1, t2 = st.tabs(["📜 Match list", "⚔️ Team vs team"])
    with t1:
        tf = st.selectbox("Show matches of…", ["All teams"] + teams, key="mr_team")
        sh = rf if tf == "All teams" else rf[(rf["team1"] == tf) | (rf["team2"] == tf)]
        sh = sh.sort_values("date", ascending=False).copy()
        sh["Result"] = sh.apply(result_text, axis=1)
        st.caption(f"{len(sh):,} matches (newest first)")
        nice_table(sh.head(500), ["date", "team1", "team2", "venue", "Result", "toss_winner", "toss_decision", "player_of_match"], "bat",
                   {"date": "Date", "team1": "Team 1", "team2": "Team 2", "venue": "Ground", "toss_winner": "Won the toss",
                    "toss_decision": "Chose to", "player_of_match": "Player of the match", "Result": "Result"})
        if len(sh) > 500:
            st.caption("Showing the newest 500. Pick a team above to narrow the list.")
    with t2:
        if len(teams) < 2:
            st.info("Not enough teams to compare.")
        else:
            c1, c2 = st.columns(2)
            a = c1.selectbox("Team A", teams, index=0, key="mr_a")
            b = c2.selectbox("Team B", teams, index=1, key="mr_b")
            if a == b:
                st.warning("Pick two different teams.")
            else:
                h = rf[((rf["team1"] == a) & (rf["team2"] == b)) | ((rf["team1"] == b) & (rf["team2"] == a))]
                if h.empty:
                    st.info(f"{a} and {b} haven't played each other in this competition (in the data).")
                else:
                    wa, wb = int((h["winner"] == a).sum()), int((h["winner"] == b).sum())
                    st.markdown(f"**{a}** and **{b}** have met **{len(h)}** times: {a} won **{wa}**, {b} won **{wb}**"
                                + (f", and {len(h) - wa - wb} had no winner." if len(h) - wa - wb > 0 else "."))
                    show(style(donut([a, b, "No winner"], [wa, wb, max(len(h) - wa - wb, 0)], [FC["ODI"], FC["Test"], "#636e72"], f"{a} vs {b}"), 300))
                    h = h.sort_values("date", ascending=False).copy()
                    h["Result"] = h.apply(result_text, axis=1)
                    nice_table(h.head(100), ["date", "venue", "Result"], "bat", {"date": "Date", "venue": "Ground"})


def page_win():
    banner("🎯", "Who Will Win?", "Pick two teams and see who is more likely to win — and why")
    ratings, results, mdf = get_csv("cricket_team_ratings.csv"), get_csv("cricket_matches_info.csv"), get_csv("cricket_model_metrics.csv")
    if ratings.empty or results.empty:
        st.info("Win-chance data isn't available yet. It appears once the notebook has uploaded `cricket_team_ratings.csv` and `cricket_matches_info.csv`.")
        return
    tip("This is a <b>chance, not a promise</b>. We look at how strong each team has been, their last 10 results, their head-to-head record, "
        "the ground and the toss. Cricket is unpredictable — even the best model is only a little better than a coin flip in T20 leagues.")
    wp_formats = ordered(set(ratings["format"].dropna()))
    fmt = fmt_pick(wp_formats, "wp_fmt", "Competition")
    rf = ratings[ratings["format"] == fmt]
    genders = [g for g in ("male", "female") if g in set(rf["gender"].dropna())]
    gender = st.radio("Show", genders, format_func=lambda g: GENDER_NAME[g] + " cricket", horizontal=True, key="wp_g") if len(genders) > 1 else (genders[0] if genders else None)
    if gender:
        rf = rf[rf["gender"] == gender]
    pool = results[results["format"] == fmt].copy()
    if gender and "gender" in pool.columns:
        pool = pool[pool["gender"] == gender]
    pool["_d"] = pd.to_datetime(pool["date"], errors="coerce")
    teams_df = rf[rf["matches_played"] >= 5]
    newest = pool["_d"].max()
    if pd.notna(newest):
        recent = pool[pool["_d"] >= newest - pd.Timedelta(days=730)]
        active = set(recent["team1"].dropna()) | set(recent["team2"].dropna())
        if active:
            teams_df = teams_df[teams_df["team"].isin(active)]
    if fmt in ("ODI", "Test", "T20I"):
        teams_df = teams_df[teams_df["team"].apply(is_real_country)]
    teams = sorted(teams_df["team"].unique().tolist())
    if len(teams) < 2:
        st.info("Not enough rated teams for this competition yet.")
        return
    kk = f"{fmt}_{gender}"
    c1, c2 = st.columns(2)
    A = c1.selectbox("Team A", teams, index=0, key=f"wp_a_{kk}")
    B = c2.selectbox("Team B", teams, index=1, key=f"wp_b_{kk}")
    if A == B:
        st.warning("Please pick two different teams.")
        return
    venues = pd.concat([pool[pool["team1"].isin([A, B]) | pool["team2"].isin([A, B])]["venue"]]).dropna()
    vlist = ["Don't know / neutral ground"] + venues.value_counts().head(60).index.tolist()
    venue = st.selectbox("Where is the match played? (optional)", vlist, key=f"wp_v_{kk}")
    toss_pick = st.radio("Who won the toss?", [A, B, "Not decided yet"], horizontal=True, key=f"wp_t_{kk}")
    choice = None
    if toss_pick != "Not decided yet":
        d = st.radio("The toss winner chose to…", ["bat", "field", "Not sure"], horizontal=True, key=f"wp_d_{kk}")
        choice = None if d == "Not sure" else d
    ra, rb = teams_df[teams_df["team"] == A].iloc[0], teams_df[teams_df["team"] == B].iloc[0]
    h = pool[((pool["team1"] == A) & (pool["team2"] == B)) | ((pool["team1"] == B) & (pool["team2"] == A))]
    decided = int(h["winner"].isin([A, B]).sum())
    a_wins = int((h["winner"] == A).sum())
    h2h = (a_wins + 1) / (decided + 2)
    vdiff, vtxt = 0.0, None
    if not venue.startswith("Don't"):
        def rec(t):
            g = pool[((pool["team1"] == t) | (pool["team2"] == t)) & (pool["venue"] == venue)]
            return int((g["winner"] == t).sum()), len(g)
        (wa_, ga_), (wb_, gb_) = rec(A), rec(B)
        vdiff = (wa_ + 1) / (ga_ + 2) - (wb_ + 1) / (gb_ + 2)
        vtxt = f"At {venue}: {A} has won {wa_} of {ga_}, {B} has won {wb_} of {gb_}."
    model = load_wp_model()
    p, used = wp_probability(model, float(ra["elo"]) - float(rb["elo"]), float(ra["form"]) - float(rb["form"]), h2h, vdiff,
                             min(int(ra["matches_played"]), int(rb["matches_played"])),
                             None if toss_pick == "Not decided yet" else (toss_pick == A), choice)
    pa = round(max(5.0, min(95.0, p * 100)), 1)
    pb = round(100 - pa, 1)
    fav, favp = (A, pa) if pa >= pb else (B, pb)
    st.markdown(f"### 🎯 {fav} is the favourite — about **{favp:.0f}%** chance")
    fig = go.Figure(go.Bar(x=[pa, pb], y=[A, B], orientation="h", marker_color=[FC["ODI"], FC["Test"]],
                           text=[f"{pa}%", f"{pb}%"], textposition="outside", textfont=dict(size=16, color=TEXT)))
    fig.update_layout(**BASE, height=210, showlegend=False, margin=dict(l=20, r=60, t=10, b=10))
    fig.update_xaxes(range=[0, 108], title="Chance of winning (%)")
    show(fig)
    if abs(pa - 50) < 8:
        st.info("This one is very close — it could easily go either way.")
    st.markdown("**Why?**")
    ea, eb = float(ra["elo"]), float(rb["elo"])
    lines = []
    lines.append(f"Team strength: {A} {ea:.0f} vs {B} {eb:.0f}" + (" — about equal." if abs(ea - eb) < 25 else f" — {A if ea > eb else B} is rated stronger.")
                 + " (1500 is an average team.)")
    lines.append(f"Recent results (last 10 matches): {A} {float(ra['form']) * 100:.0f}% vs {B} {float(rb['form']) * 100:.0f}% (a small boost is added so one game can't swing it).")
    lines.append(f"Head to head: {A} has won {a_wins} of {decided} meetings." if decided else f"{A} and {B} haven't met in this competition in the data.")
    if vtxt:
        lines.append(vtxt)
    lines.append("Toss: not decided yet — we averaged over every possible toss result." if toss_pick == "Not decided yet" else
                 f"Toss: {toss_pick} won it" + (f" and chose to {choice}." if choice else "."))
    for l in lines:
        st.markdown("- " + l)
    if min(int(ra["matches_played"]), int(rb["matches_played"])) < 15:
        st.warning("One of these teams has a short record here, so its rating is still settling — treat the number with extra caution.")
    if not used:
        st.caption("ℹ️ The full prediction model couldn't be loaded, so this is a simpler estimate based only on the team strength ratings.")
    with st.expander("📊 How accurate has this been in the past?"):
        accuracy_report(mdf, compact=True)


def accuracy_report(mdf, compact=False):
    best = best_win_model(mdf)
    if mdf is None or mdf.empty:
        st.info("The accuracy report appears once the notebook has uploaded `cricket_model_metrics.csv`.")
        return
    acc = mval(mdf, f"win_probability_{best}", "Accuracy") if best else None
    elo_acc = mval(mdf, "win_probability_baseline_higher_elo", "Accuracy")
    if acc is not None:
        d = {"Picked the winner correctly": f"{acc * 100:.1f}%"}
        if elo_acc is not None:
            d["“Higher-rated team wins” rule"] = f"{elo_acc * 100:.1f}%"
        d["Coin flip"] = "50%"
        metrics(d)
        st.caption("Measured on the newest 20% of matches, which the model never saw while learning.")
    lo, hi = mval(mdf, "win_probability_best_vs_elo_only", "LogLoss gain CI low"), mval(mdf, "win_probability_best_vs_elo_only", "LogLoss gain CI high")
    if lo is not None and hi is not None:
        if lo > 0:
            st.success("The extra clues (form, head-to-head, ground, toss) genuinely help beyond the team strength rating alone.")
        else:
            st.info("The extra clues don't clearly beat the team strength rating alone on this test, so the rating is doing most of the work.")
    wt = get_csv("cricket_win_prob_test.csv")
    if not wt.empty and {"predicted_proba", "actual"}.issubset(wt.columns):
        wt = wt.dropna(subset=["predicted_proba", "actual"]).copy()
        wt["bin"] = pd.cut(wt["predicted_proba"], [0, .3, .4, .5, .6, .7, 1.0])
        cal = wt.groupby("bin", observed=True).agg(n=("actual", "size"), predicted=("predicted_proba", "mean"), actual=("actual", "mean")).reset_index()
        if len(cal):
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GRID, dash="dot"), name="Perfect"))
            fig.add_trace(go.Scatter(x=cal["predicted"], y=cal["actual"], mode="lines+markers", name="This model",
                                     line=dict(color=ACCENT, width=3), marker=dict(size=9)))
            fig.update_layout(**BASE, height=320, title="When we say “70%”, how often does it really happen?", margin=dict(l=50, r=20, t=48, b=50))
            fig.update_xaxes(title="What we predicted", range=[0, 1])
            fig.update_yaxes(title="How often it happened", range=[0, 1])
            show(fig)
            st.caption("The closer the orange line is to the dotted line, the more honest the percentages are.")
    if not compact:
        st.dataframe(mdf[mdf["model"].astype(str).str.startswith("win_probability")].reset_index(drop=True), hide_index=True, **DF)


def page_runs():
    banner("🔮", "Run Forecast", "How many runs might a batter score in their next season?")
    proj, back, mdf = get_csv("cricket_player_forecast.csv"), get_csv("cricket_run_forecast.csv"), get_csv("cricket_model_metrics.csv")
    if proj.empty and back.empty:
        st.info("Forecast data isn't available yet. It appears once the notebook has uploaded `cricket_player_forecast.csv`.")
        return
    tip("A <b>season</b> means one edition of a league (e.g. IPL 2027) or, for Test/ODI/T20I, the <b>next 12 months</b>. The forecast is the total runs we expect "
        "<b>if the batter is picked and fit for the whole season</b>. It is an estimate from recent seasons — not a guarantee.")
    t1, t2, t3 = st.tabs(["🔍 Look up a player", "📈 Biggest projected scorers", "🧪 How good is the forecast?"])
    with t1:
        if proj.empty:
            st.info("Next-season forecasts aren't available yet.")
        else:
            label = player_search("Batter", "Kohli", "rf")
            if label:
                pr = proj[proj["striker"] == label]
                if pr.empty:
                    st.info(f"There's no forecast for {label}. Forecasts exist only for batters who played at least 3 matches (2 in Tests) in the last "
                            f"finished season, in competitions that are still running.")
                else:
                    fmt = fmt_pick(ordered(set(pr["format"])), "rf_fmt")
                    r = pr[pr["format"] == fmt].iloc[0]
                    last, nxt, lo, hi = float(r["last_season_runs"]), float(r["projected_next_season_runs"]), float(r["projected_low"]), float(r["projected_high"])
                    st.markdown(f"##### {label} — {fl(fmt)} — {r.get('projection_season', 'next season')}")
                    st.markdown(f'<div class="ca-big">about {nxt:,.0f} runs</div><div class="ca-bigsub">likely somewhere between '
                                f'<b>{lo:,.0f}</b> and <b>{hi:,.0f}</b> — if selected and fit all season</div>', unsafe_allow_html=True)
                    fig = go.Figure(go.Bar(x=[f"{r.get('last_season', 'Last season')} (actual)", f"{r.get('projection_season', 'Next season')} (forecast)"],
                                           y=[last, nxt], marker_color=[FC.get(fmt, ACCENT2), "#a29bfe"], text=[f"{last:,.0f}", f"{nxt:,.0f}"],
                                           textposition="outside", textfont=dict(size=15, color=TEXT),
                                           error_y=dict(type="data", symmetric=False, array=[0, max(hi - nxt, 0)], arrayminus=[0, max(nxt - lo, 0)],
                                                        color=ACCENT)))
                    fig.update_layout(**BASE, height=340, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
                    fig.update_yaxes(title="Runs", rangemode="tozero")
                    show(fig)
                    metrics({"Matches expected": fnum(r.get("projected_matches"), 0), "Runs per match": fnum(r.get("projected_runs_per_match"), 1),
                             "Matches last season": fint(r.get("last_season_matches"))})
                    if isnum(r.get("p_plays_next_season")):
                        st.markdown(f"🎟️ **Will he/she even play?** In the past, about **{float(r['p_plays_next_season']) * 100:.0f}%** of regular batters "
                                    f"like this played in the following season. The forecast above only counts seasons where they do.")
                    hd = str(r.get("history_depth", ""))
                    if hd:
                        st.caption(f"📚 How much history the forecast is built on: {hd}. Even with a lot of history, a season total is very uncertain — injuries and "
                                   f"team changes can't be seen in the data.")
                    if isinstance(r.get("basis_text"), str):
                        with st.expander("How was this number worked out?"):
                            st.write(r["basis_text"])
    with t2:
        if proj.empty:
            st.info("Next-season forecasts aren't available yet.")
        else:
            fmt = fmt_pick(ordered(set(proj["format"])), "rf_top_fmt")
            ff, _ = gender_pick(proj[proj["format"] == fmt], "rf_top_g")
            top = ff.dropna(subset=["projected_next_season_runs"]).sort_values("projected_next_season_runs", ascending=False).head(15)
            if top.empty:
                st.info("No forecasts for this format.")
            else:
                st.caption(f"Season being forecast: {top['projection_season'].iloc[0] if 'projection_season' in top.columns else 'next season'}")
                show_or_note(bar_h(top, "projected_next_season_runs", "striker", f"Top 15 projected run-scorers — {fl(fmt)}", "Purples", "Forecast runs"))
                top = top.assign(Range=top["projected_low"].round(0).astype(int).astype(str) + " – " + top["projected_high"].round(0).astype(int).astype(str))
                nice_table(top, ["striker", "last_season_runs", "projected_next_season_runs", "Range", "projected_matches"], "bat",
                           {"last_season_runs": "Runs last season", "projected_next_season_runs": "Forecast runs", "Range": "Likely range",
                            "projected_matches": "Matches expected"})
    with t3:
        if back.empty or "predicted_runs" not in back.columns:
            st.info("The accuracy check isn't available yet (`cricket_run_forecast.csv`).")
        else:
            mae_m = mval(mdf, "run_forecast_deployed", "MAE")
            mae_n = mval(mdf, "run_forecast_naive", "MAE")
            mae_r = mval(mdf, "run_forecast_roll3", "MAE")
            cov = mval(mdf, "run_forecast_deployed", "Range coverage (target 0.80)")
            bt = back.dropna(subset=["runs", "predicted_runs"]).copy()
            if mae_m is None:
                mae_m = float((bt["runs"] - bt["predicted_runs"]).abs().mean())
            st.markdown(f"On the newest finished season — which the forecast had **never seen** — it missed the real total by about **{mae_m:.0f} runs** on average.")
            d = {"Our forecast: typical miss": f"{mae_m:.0f} runs"}
            if mae_n is not None:
                d["“Same as last season”: typical miss"] = f"{mae_n:.0f} runs"
            if mae_r is not None:
                d["“Average of last 3 seasons”: typical miss"] = f"{mae_r:.0f} runs"
            metrics(d)
            base = [v for v in (mae_n, mae_r) if v is not None]
            if base:
                (st.success if mae_m < min(base) else st.warning)(
                    "The forecast beats both simple rules of thumb." if mae_m < min(base) else
                    "The forecast does NOT clearly beat a simple rule of thumb — treat it as rough guidance only.")
            if cov is not None:
                st.caption(f"The “likely range” held the real total {cov * 100:.0f}% of the time (the aim is about 80%).")
            bt["miss"] = (bt["runs"] - bt["predicted_runs"]).abs()
            per = bt.groupby("format").agg(Batters=("runs", "size"), Typical_miss=("miss", "mean")).round(0).reset_index()
            per["format"] = per["format"].map(fl)
            st.dataframe(per.rename(columns={"format": "Format", "Typical_miss": "Typical miss (runs)"}), hide_index=True, **DF)
            fig = px.scatter(bt, x="predicted_runs", y="runs", color="format", hover_name="striker", color_discrete_map=FC,
                             title="Forecast vs what really happened (closer to the dotted line = better)")
            mx = float(max(bt["runs"].max(), bt["predicted_runs"].max()))
            fig.add_shape(type="line", x0=0, y0=0, x1=mx, y1=mx, line=dict(color=MUTED, dash="dot"))
            fig.update_layout(**BASE, height=440, margin=dict(l=50, r=20, t=48, b=50), xaxis_title="Forecast runs", yaxis_title="Actual runs")
            show(fig)


def page_work():
    banner("💪", "Bowler Workload", "How much has a bowler been bowling lately?")
    tip("This page counts the <b>balls a bowler has bowled in recent matches</b> and compares them with other bowlers of the same type. "
        "It is <b>not an injury prediction</b> — the data has no injury information and doesn't cover every match played, so real workloads can be higher.")
    cur, fc = get_csv("cricket_bowler_workload_current.csv"), get_csv("cricket_bowler_workload_forecast.csv")
    if cur.empty and fc.empty:
        st.info("Workload data isn't available yet. It appears once the notebook has uploaded `cricket_bowler_workload_current.csv`.")
        return
    t1, t2 = st.tabs(["📋 Who has bowled a lot lately", "🔍 Look up a bowler"])
    with t1:
        if cur.empty:
            st.info("No current workload snapshot yet.")
        else:
            d, _ = gender_pick(cur, "wk_g")
            types = ["All"] + [t for t in ("Test", "ODI", "T20") if t in set(d["bowler_type"].dropna())]
            typ = st.radio("Bowler type (the format they bowl most)", types, horizontal=True, key="wk_t")
            if typ != "All":
                d = d[d["bowler_type"] == typ]
            d = d[d["risk_flag"].notna()]
            if d.empty:
                st.info("No bowlers to show for these choices.")
            else:
                if isnum(d["as_of"].iloc[0] if "as_of" in d.columns else None) or "as_of" in d.columns:
                    st.caption(f"As of {pretty_date(d['as_of'].iloc[0])}. “Last 28 days” means the 28 days before this date.")
                counts = d["risk_flag"].value_counts().reindex(LOAD_ORDER).fillna(0)
                cdf = pd.DataFrame({"Workload": [LOAD_WORDS[k] for k in counts.index], "Bowlers": counts.values.astype(int)})
                show_or_note(bar_v(cdf, "Workload", "Bowlers", "How busy have bowlers been in the last 28 days?", ACCENT2, 300, "Bowlers"))
                heavy = d[d["risk_flag"].isin(["Very heavy load", "Heavy load"]) & (d["matches_28d"] > 0)].sort_values("load_percentile", ascending=False).head(30).copy()
                st.markdown("#### 🟠 Bowlers who have bowled the most lately")
                if heavy.empty:
                    st.success("Nobody is currently in the heavy range.")
                else:
                    heavy["Workload"] = heavy["risk_flag"].map(LOAD_WORDS)
                    heavy["Overs (last 7 days)"] = (heavy["acute_balls"] / 6).round(1)
                    heavy["Overs (last 28 days)"] = (heavy["load_28d"] / 6).round(1)
                    heavy["Busier than"] = heavy["load_percentile"].round(0).astype(int).astype(str) + "% of similar bowlers"
                    heavy["Last played"] = pd.to_datetime(heavy["last_match_date"], errors="coerce").dt.strftime("%d %b %Y")
                    nice_table(heavy, ["bowler", "bowler_type", "Workload", "Overs (last 7 days)", "Overs (last 28 days)", "matches_28d", "Busier than", "Last played"],
                               "bowl", {"bowler_type": "Usual format", "matches_28d": "Matches (28 days)"})
                    st.caption("Wides and no-balls are counted as work done, so “overs” here are slightly more than the scorecard overs.")
    with t2:
        label = player_search("Bowler", "Bumrah", "wk")
        if label:
            r = cur[cur["bowler"] == label] if not cur.empty else pd.DataFrame()
            if len(r):
                r = r.iloc[0]
                st.markdown(f"**{label}** — usually a **{r['bowler_type']}** bowler. " + str(r.get("workload_note", "")))
                metrics({"Overs bowled, last 7 days": fnum(r["acute_balls"] / 6, 1), "Overs bowled, last 28 days": fnum(r["load_28d"] / 6, 1),
                         "Workload level": LOAD_WORDS.get(r.get("risk_flag"), "Not rated")})
            else:
                st.caption("No current workload snapshot — this bowler may not have played in the last 90 days.")
            f = fc[fc["bowler"] == label] if not fc.empty else pd.DataFrame()
            if len(f):
                st.markdown("#### 🎳 How many overs next match?")
                st.caption("If the bowler bowls in their next match of that format (we can't predict selection).")
                for _, x in f.iterrows():
                    st.markdown(f"- **{fl(x['format'])}:** {x['expected_overs_text']}")
            hist = get_csv("cricket_bowler_workload.csv")
            h = hist[hist["bowler"] == label].copy() if not hist.empty else pd.DataFrame()
            if len(h):
                h["start_date"] = pd.to_datetime(h["start_date"], errors="coerce")
                h = h.sort_values("start_date")
                h["Overs in the 28 days before"] = (h["load_28d"] / 6).round(1)
                fig = px.line(h, x="start_date", y="Overs in the 28 days before", markers=True, title=f"{label} — workload over time")
                fig.update_traces(line=dict(color=ACCENT, width=3))
                fig.update_layout(**BASE, height=320, margin=M_DEFAULT)
                fig.update_xaxes(title="")
                show(fig)
            elif not len(r) and not len(f):
                st.info("No workload information for this bowler.")


def page_about():
    banner("ℹ️", "About This Data", "Where the numbers come from, what the predictions mean, and how far to trust them")
    t1, t2, t3, t4 = st.tabs(["📚 Where the data comes from", "🔮 What the predictions mean", "🧪 Accuracy report card", "⚠️ Things to keep in mind"])
    with t1:
        st.markdown("All numbers are worked out from **Cricsheet**, a free, community-made archive that records **every ball** of many matches. "
                    "That is why this app can show things like how a batter fares against one particular bowler.")
        if cutoff:
            st.markdown(f"**Data is up to:** {pretty_date(cutoff)}" + (f"  ·  last refreshed {upd}" if upd else ""))
        man = get_csv("cricket_data_manifest.csv")
        if not man.empty:
            r = man.iloc[0]
            metrics({"Matches": fint(r.get("matches")), "Balls recorded": fint(r.get("rows")),
                     "From": pretty_date(r.get("date_start"))})
        st.markdown("**Competitions covered**")
        for f in ALL_FMT:
            st.markdown(f"- {FORMAT_ICON.get(f, '🏏')} {FORMAT_LONG.get(f, f)}")
        st.markdown("Men's and women's cricket are always kept apart, and every player is identified by Cricsheet's unique ID — so two different players with the "
                    "same name are no longer mixed up, and one player with two spellings is no longer split in two.")
    with t2:
        st.markdown("""
**🎯 Who will win?** — the chance that Team A beats Team B in a match. Built from team strength ratings, recent results, head-to-head record, the ground and the toss.

**🔮 Run forecast** — the total runs one batter might score in their *next season*, **if they are picked and fit**. It is not the next match, not an average, and not a probability.

**💪 Bowler workload** — a simple count of balls bowled recently, compared with similar bowlers. **Not** a medical or injury prediction.

**🎳 Overs next match** — how many overs a bowler might bowl **if** they bowl in their next match. It doesn't predict whether they will be picked.

**⭐ Overall rating (0–100)** — not a prediction. It describes a player's career so far compared with regular players of the same format. 50 = typical, 90+ = elite.
""")
    with t3:
        st.markdown("**Win chances**")
        accuracy_report(get_csv("cricket_model_metrics.csv"))
        st.markdown("**Run forecast** — see the *🧪 How good is the forecast?* tab on the Run Forecast page.")
    with t4:
        st.markdown("""
- **Not every match is in the data.** Cricsheet doesn't have all domestic first-class or county matches and some leagues, so totals can be lower than official records — especially for older careers.
- **Afghanistan's matches are not published by Cricsheet**, so Afghanistan has no team rating and results against it are missing from other teams' records.
- **The win model doesn't know who is playing.** Injuries, rested stars and team selection are invisible to it.
- **T20 leagues are close to coin flips.** Expect predictions to be only a few points better than guessing.
- **Small samples mislead.** A player with 3 matches can look amazing or awful — the match count is always shown for that reason.
- **"NT20" means England's T20 Blast.**
""")
        if load_errors:
            with st.expander(f"⚙️ Technical: {len(load_errors)} data file(s) had a problem loading"):
                for name, err in load_errors:
                    st.caption(f"{name}: {err}")


PAGES = {HOME: page_home, P_FIND: page_find, P_COMPARE: page_compare, P_YEARS: page_years, P_WHERE: page_where, P_BVB: page_bvb,
         P_TOP: page_top, P_LEAGUE: page_league, P_FORM: page_form, P_SIM: page_sim, P_RESULTS: page_results, P_WIN: page_win,
         P_RUNS: page_runs, P_WORK: page_work, P_ABOUT: page_about}

PAGES.get(section, page_home)()

st.markdown("---")
st.caption("Data: Cricsheet.org (open data). Predictions are estimates for fun and insight — not betting or selection advice.")
