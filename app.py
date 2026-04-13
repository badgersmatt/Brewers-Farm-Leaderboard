"""
Milwaukee Brewers Farm System Leaderboard
==========================================
Uses the MLB Stats API (statsapi.mlb.com) for structured JSON data.
"""

from __future__ import annotations

import math
from datetime import datetime, date

import pandas as pd
import requests
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Brewers Farm Leaderboard",
    page_icon="🧀",
    layout="wide",
)

# ── Theme CSS ─────────────────────────────────────────────────────────────────
BREWERS_CSS = """
<style>
/* ── Base ─────────────────────────────────────────────────── */
.stApp {
    background: linear-gradient(160deg, #050f24 0%, #0A2351 60%, #0d2a5e 100%);
    min-height: 100vh;
}
/* Kill the white header bar */
[data-testid="stHeader"] {
    background-color: #050f24 !important;
    background: #050f24 !important;
    border-bottom: 1px solid rgba(255,197,47,0.08) !important;
}
[data-testid="stDecoration"] {
    background-image: none !important;
    background: #050f24 !important;
    display: none !important;
}
.stAppToolbar { background: transparent !important; }
.stMainBlockContainer { padding-top: 1.5rem !important; max-width: 1400px; }

/* ── Typography ───────────────────────────────────────────── */
h1 {
    background: linear-gradient(90deg, #FFC52F 0%, #ffe08a 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.6rem !important;
    font-weight: 900 !important;
    letter-spacing: -1.5px;
    line-height: 1.1 !important;
    margin-bottom: 0.1rem !important;
}
h2, h3 { color: #FFC52F !important; font-weight: 700 !important; letter-spacing: -0.3px; }
p, .stMarkdown p, label, span { color: rgba(255,255,255,0.88) !important; }
.stCaption p { color: rgba(255,255,255,0.42) !important; font-size: 0.78rem !important; }
code { color: #FFC52F !important; background: rgba(255,197,47,0.1) !important; }

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #040d1f !important;
    border-right: 1px solid rgba(255,197,47,0.1);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #FFC52F !important; }

/* ── Metric Cards ─────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(255,197,47,0.07) 0%, rgba(255,255,255,0.03) 100%);
    border: 1px solid rgba(255,197,47,0.18);
    border-radius: 16px;
    padding: 1.1rem 1.3rem !important;
    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(255,197,47,0.45);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
[data-testid="stMetricLabel"] {
    color: rgba(255,255,255,0.45) !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
[data-testid="stMetricValue"] {
    color: #FFC52F !important;
    font-weight: 800 !important;
    font-size: 2.1rem !important;
    line-height: 1.1 !important;
}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,197,47,0.1);
    border-radius: 14px;
    gap: 4px;
    padding: 5px;
    margin-bottom: 1rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    color: rgba(255,255,255,0.5) !important;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 0.5rem 1.1rem;
    transition: all 0.2s ease;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: rgba(255,255,255,0.85) !important;
    background: rgba(255,255,255,0.06) !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #FFC52F 0%, #ffd966 100%) !important;
    color: #0A2351 !important;
    font-weight: 800 !important;
    box-shadow: 0 3px 12px rgba(255,197,47,0.35);
}

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #FFC52F, #e6b000) !important;
    color: #0A2351 !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(255,197,47,0.2);
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(255,197,47,0.4) !important;
}

/* ── Form inputs ──────────────────────────────────────────── */
/* Selectbox & multiselect container */
[data-baseweb="select"] > div:first-child {
    background-color: rgba(5, 20, 55, 0.85) !important;
    border: 1px solid rgba(255,197,47,0.22) !important;
    border-radius: 10px !important;
    transition: border-color 0.2s;
}
[data-baseweb="select"] > div:first-child:hover { border-color: rgba(255,197,47,0.5) !important; }
[data-baseweb="select"] span,
[data-baseweb="select"] div { color: rgba(255,255,255,0.9) !important; }
[data-baseweb="select"] svg { fill: rgba(255,197,47,0.6) !important; }
[data-baseweb="select"] input { color: white !important; background: transparent !important; }

/* Multiselect tags */
[data-baseweb="tag"] {
    background: linear-gradient(135deg, #FFC52F, #e6b000) !important;
    border-radius: 6px !important;
    border: none !important;
}
[data-baseweb="tag"] span { color: #0A2351 !important; font-weight: 700 !important; }
[data-baseweb="tag"] svg,
[data-baseweb="tag"] button svg { fill: #0A2351 !important; }

/* ── Dropdown popover (portal-rendered, outside .stApp) ───── */
[data-baseweb="popover"] {
    background-color: #0b1e4a !important;
    border: 1px solid rgba(255,197,47,0.2) !important;
    border-radius: 12px !important;
    box-shadow: 0 12px 40px rgba(0,0,0,0.6) !important;
    overflow: hidden !important;
}
[data-baseweb="popover"] > div { background-color: #0b1e4a !important; }
[data-baseweb="menu"],
[data-baseweb="list"] {
    background-color: #0b1e4a !important;
    max-height: 320px !important;
    overflow-y: auto !important;
}
/* The UL that holds all options */
[data-baseweb="menu"] ul,
[data-baseweb="list"] ul { background-color: #0b1e4a !important; }
[role="option"] {
    background-color: #0b1e4a !important;
    color: rgba(255,255,255,0.88) !important;
    font-size: 0.88rem !important;
    transition: background-color 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
[role="option"]:hover {
    background-color: rgba(255,197,47,0.14) !important;
    color: white !important;
}
[aria-selected="true"][role="option"] {
    background-color: rgba(255,197,47,0.2) !important;
    color: #FFC52F !important;
    font-weight: 600 !important;
}
/* Multiselect dropdown item text specifically */
[data-baseweb="menu"] [data-testid="stMarkdownContainer"] p,
[data-baseweb="popover"] span,
[data-baseweb="popover"] p { color: rgba(255,255,255,0.88) !important; }

/* ── Text inputs ──────────────────────────────────────────── */
textarea,
[data-testid="stTextInput"] input {
    background-color: rgba(5, 20, 55, 0.85) !important;
    border: 1px solid rgba(255,197,47,0.22) !important;
    border-radius: 10px !important;
    color: white !important;
    transition: border-color 0.2s;
}
textarea:focus,
[data-testid="stTextInput"] input:focus {
    border-color: rgba(255,197,47,0.6) !important;
    box-shadow: 0 0 0 3px rgba(255,197,47,0.1) !important;
}

/* ── Slider ───────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
    background-color: #FFC52F !important;
    border-color: #FFC52F !important;
    box-shadow: 0 0 0 3px rgba(255,197,47,0.25) !important;
}
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] { color: rgba(255,255,255,0.35) !important; }

/* ── Checkbox ─────────────────────────────────────────────── */
[data-testid="stCheckbox"] label p { color: rgba(255,255,255,0.85) !important; }

/* ── Dataframes ───────────────────────────────────────────── */
[data-testid="stDataFrameResizable"] {
    border: 1px solid rgba(255,197,47,0.14) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}
/* Column header sort text — Glide Data Grid renders text in canvas so
   CSS can't reach it directly, but we can lighten the wrapper bg so
   the contrast stays readable when the column is active */
[data-testid="stDataFrame"] { color: white !important; }
/* The sort selectbox label (sidebar sort dropdown) */
.stSelectbox label { color: rgba(255,255,255,0.7) !important; }
.stSelectbox [data-baseweb="select"] span { color: white !important; font-weight: 500 !important; }

/* ── Expanders ────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,197,47,0.18) !important;
    border-radius: 14px !important;
    overflow: hidden;
    margin-top: 0.75rem;
}
details > summary {
    color: #FFC52F !important;
    font-weight: 700 !important;
    padding: 0.75rem 1rem;
    transition: background 0.2s;
}
details > summary:hover { background: rgba(255,197,47,0.06) !important; }
details[open] > summary { border-bottom: 1px solid rgba(255,197,47,0.1); }

/* ── Alerts ───────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border-left-width: 4px !important;
}
[data-testid="stAlert"][data-baseweb="notification"] { border-left-color: #FFC52F !important; }

/* ── Divider ──────────────────────────────────────────────── */
hr { border-color: rgba(255,197,47,0.1) !important; margin: 1.5rem 0 !important; }

/* ── Spinner ──────────────────────────────────────────────── */
[data-testid="stSpinner"] > div { border-top-color: #FFC52F !important; }

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: rgba(255,197,47,0.25); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,197,47,0.45); }

/* ── Game log panel ───────────────────────────────────────── */
.game-log-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 0 0.5rem;
    border-bottom: 1px solid rgba(255,197,47,0.15);
    margin-bottom: 0.75rem;
}
</style>
"""

# ── Constants ─────────────────────────────────────────────────────────────────
BREWERS_ORG_ID = 158
CURRENT_YEAR   = datetime.now().year

BASE    = "https://statsapi.mlb.com/api/v1"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "BrewersFarmLeaderboard/4.0"})

LEVEL_YEARS_TO_MLB = {
    "AAA":      0.8,
    "AA":       1.5,
    "High-A":   2.5,
    "Single-A": 3.5,
    "ACL/DSL":  5.0,
}

LEVEL_COLOR = {
    "AAA":      "#22c55e",
    "AA":       "#3b82f6",
    "High-A":   "#a855f7",
    "Single-A": "#f97316",
    "ACL/DSL":  "#94a3b8",
}

HITTING_DISPLAY  = ["Player", "Level", "Pos", "Age", "G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO", "Proj Debut"]
PITCHING_DISPLAY = ["Player", "Level", "Pos", "Age", "G", "GS", "IP", "ERA", "WHIP", "SO", "BB", "K/BB", "SV", "HLD", "W", "L", "Proj Debut"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_get(url: str, params: dict | None = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def age_from_dob(dob_str: str | None) -> int | None:
    if not dob_str:
        return None
    try:
        dob   = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def projected_debut(level_key: str, age: int | None, perf_score: float) -> str:
    if age is None:
        return "Unknown"
    base       = LEVEL_YEARS_TO_MLB.get(level_key, 3.0)
    age_f      = (age - 22) * 0.15
    years      = max(0.3, base - age_f - perf_score)
    debut_year = CURRENT_YEAR + round(years)
    return str(debut_year)


def hitter_perf_score(row: pd.Series) -> float:
    ops = row.get("OPS", 0) or 0
    hr  = row.get("HR",  0) or 0
    ab  = row.get("AB",  1) or 1
    sb  = row.get("SB",  0) or 0
    score = 0.0
    if   ops >= 1.000: score += 0.25
    elif ops >= 0.900: score += 0.20
    elif ops >= 0.800: score += 0.10
    hr_rate = hr / ab
    if   hr_rate >= 0.05: score += 0.15
    elif hr_rate >= 0.03: score += 0.08
    if   sb >= 15: score += 0.10
    elif sb >= 8:  score += 0.05
    return min(score, 0.5)


def pitcher_perf_score(row: pd.Series) -> float:
    era  = row.get("ERA",  99) or 99
    whip = row.get("WHIP", 99) or 99
    kbb  = row.get("K/BB",  0) or 0
    score = 0.0
    if   era <= 2.00: score += 0.20
    elif era <= 3.00: score += 0.15
    elif era <= 4.00: score += 0.08
    if   whip <= 1.00: score += 0.15
    elif whip <= 1.20: score += 0.08
    if   kbb >= 4.0: score += 0.15
    elif kbb >= 2.5: score += 0.08
    return min(score, 0.5)


def level_key_from_sport(sport_id: int, fallback: str = "?") -> str:
    return {11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A", 16: "ACL/DSL"}.get(sport_id, fallback)


def valid_player_id(pid) -> bool:
    """Return True if pid is a usable integer player ID."""
    if pid is None:
        return False
    try:
        return not pd.isna(pid)
    except (TypeError, ValueError):
        return True   # non-float, assume valid


# ── MLB Stats API ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def fetch_affiliates() -> list[dict]:
    data = safe_get(f"{BASE}/teams", params={"sportIds": "11,12,13,14,16", "season": CURRENT_YEAR})
    out  = []
    for team in data.get("teams", []):
        if team.get("parentOrgId") == BREWERS_ORG_ID and team.get("id") != BREWERS_ORG_ID:
            sport    = team.get("sport", {})
            sport_id = sport.get("id")
            lk       = level_key_from_sport(sport_id)
            out.append({
                "id":         team["id"],
                "name":       team["name"],
                "sport_id":   sport_id,
                "level_key":  lk,
                "level_name": f"{lk} {team['name']}",
            })
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_mlb_active_roster() -> set[str]:
    try:
        data = safe_get(f"{BASE}/teams/{BREWERS_ORG_ID}/roster", params={"rosterType": "active"})
        return {p["person"]["fullName"].strip().lower()
                for p in data.get("roster", []) if p.get("person", {}).get("fullName")}
    except Exception:
        return set()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_game_log(player_id: int, group: str) -> pd.DataFrame:
    try:
        data   = safe_get(f"{BASE}/people/{player_id}/stats", params={
            "stats": "gameLog", "group": group,
            "season": CURRENT_YEAR, "gameType": "R",
        })
        splits = data.get("stats", [{}])[0].get("splits", [])
        rows   = []
        for split in splits:
            s   = split.get("stat", {})
            opp = split.get("opponent", {})
            opp_abbr = opp.get("abbreviation") or opp.get("name", "")
            loc = "vs" if split.get("isHome") else "@"

            if group == "hitting":
                rows.append({
                    "Date": split.get("date", ""),
                    "Opp":  f"{loc} {opp_abbr}",
                    "AB":   int(s.get("atBats",      0) or 0),
                    "R":    int(s.get("runs",         0) or 0),
                    "H":    int(s.get("hits",         0) or 0),
                    "2B":   int(s.get("doubles",      0) or 0),
                    "3B":   int(s.get("triples",      0) or 0),
                    "HR":   int(s.get("homeRuns",     0) or 0),
                    "RBI":  int(s.get("rbi",          0) or 0),
                    "BB":   int(s.get("baseOnBalls",  0) or 0),
                    "SO":   int(s.get("strikeOuts",   0) or 0),
                    "SB":   int(s.get("stolenBases",  0) or 0),
                    "AVG":  round(float(s.get("avg", 0) or 0), 3),
                })
            else:
                dec = ""
                if   int(s.get("wins",   0) or 0): dec = "W"
                elif int(s.get("losses", 0) or 0): dec = "L"
                elif int(s.get("saves",  0) or 0): dec = "SV"
                elif int(s.get("holds",  0) or 0): dec = "HLD"
                rows.append({
                    "Date": split.get("date", ""),
                    "Opp":  f"{loc} {opp_abbr}",
                    "Dec":  dec,
                    "IP":   round(float(s.get("inningsPitched", 0) or 0), 1),
                    "H":    int(s.get("hits",        0) or 0),
                    "R":    int(s.get("runs",         0) or 0),
                    "ER":   int(s.get("earnedRuns",   0) or 0),
                    "BB":   int(s.get("baseOnBalls",  0) or 0),
                    "SO":   int(s.get("strikeOuts",   0) or 0),
                    "HR":   int(s.get("homeRuns",     0) or 0),
                    "ERA":  round(float(s.get("era",  0) or 0), 2),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Date", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_hitting(team_id: int, sport_id: int, level_key: str, level_name: str) -> pd.DataFrame:
    try:
        data = safe_get(f"{BASE}/stats", params={
            "stats": "season", "group": "hitting",
            "season": CURRENT_YEAR, "teamId": team_id, "sportId": sport_id,
            "playerPool": "All",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p   = split.get("player", {})
            s   = split.get("stat",   {})
            dob = p.get("birthDate") or p.get("person", {}).get("birthDate")
            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       split.get("position", {}).get("abbreviation", ""),
                "Age":       age_from_dob(dob),
                "G":         int(s.get("gamesPlayed",  0) or 0),
                "AB":        int(s.get("atBats",       0) or 0),
                "AVG":       round(float(s.get("avg",  0) or 0), 3),
                "OBP":       round(float(s.get("obp",  0) or 0), 3),
                "SLG":       round(float(s.get("slg",  0) or 0), 3),
                "OPS":       round(float(s.get("ops",  0) or 0), 3),
                "HR":        int(s.get("homeRuns",     0) or 0),
                "RBI":       int(s.get("rbi",          0) or 0),
                "SB":        int(s.get("stolenBases",  0) or 0),
                "BB":        int(s.get("baseOnBalls",  0) or 0),
                "SO":        int(s.get("strikeOuts",   0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Proj Debut"] = df.apply(
            lambda r: projected_debut(r["level_key"], r["Age"], hitter_perf_score(r)), axis=1
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_pitching(team_id: int, sport_id: int, level_key: str, level_name: str) -> pd.DataFrame:
    try:
        data = safe_get(f"{BASE}/stats", params={
            "stats": "season", "group": "pitching",
            "season": CURRENT_YEAR, "teamId": team_id, "sportId": sport_id,
            "playerPool": "All",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p   = split.get("player", {})
            s   = split.get("stat",   {})
            dob = p.get("birthDate") or p.get("person", {}).get("birthDate")
            so  = int(s.get("strikeOuts",   0) or 0)
            bb  = int(s.get("baseOnBalls",  0) or 0)
            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       split.get("position", {}).get("abbreviation", "P"),
                "Age":       age_from_dob(dob),
                "G":         int(s.get("gamesPitched", 0) or 0),
                "GS":        int(s.get("gamesStarted", 0) or 0),
                "IP":        round(float(s.get("inningsPitched", 0) or 0), 1),
                "ERA":       round(float(s.get("era",  0) or 0), 2),
                "WHIP":      round(float(s.get("whip", 0) or 0), 2),
                "SO":        so,
                "BB":        bb,
                "K/BB":      round(so / bb, 2) if bb > 0 else None,
                "SV":        int(s.get("saves",  0) or 0),
                "HLD":       int(s.get("holds",  0) or 0),
                "W":         int(s.get("wins",   0) or 0),
                "L":         int(s.get("losses", 0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Proj Debut"] = df.apply(
            lambda r: projected_debut(r["level_key"], r["Age"], pitcher_perf_score(r)), axis=1
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    affiliates = fetch_affiliates()
    mlb_active = fetch_mlb_active_roster()

    hitter_frames:  list[pd.DataFrame] = []
    pitcher_frames: list[pd.DataFrame] = []
    loaded: list[str] = []
    failed: list[str] = []

    for aff in affiliates:
        hit = fetch_team_hitting( aff["id"], aff["sport_id"], aff["level_key"], aff["level_name"])
        pit = fetch_team_pitching(aff["id"], aff["sport_id"], aff["level_key"], aff["level_name"])
        if hit.empty and pit.empty:
            failed.append(aff["level_name"])
        else:
            loaded.append(aff["level_name"])
            if not hit.empty: hitter_frames.append(hit)
            if not pit.empty: pitcher_frames.append(pit)

    hitters  = pd.concat(hitter_frames,  ignore_index=True) if hitter_frames  else pd.DataFrame()
    pitchers = pd.concat(pitcher_frames, ignore_index=True) if pitcher_frames else pd.DataFrame()

    if not hitters.empty:
        hitters  = hitters[ ~hitters["Player"].str.lower().isin(mlb_active)].copy()
    if not pitchers.empty:
        pitchers = pitchers[~pitchers["Player"].str.lower().isin(mlb_active)].copy()

    return hitters, pitchers, loaded, failed


def add_favorites(df: pd.DataFrame, favorites: set[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["⭐"] = out["Player"].str.lower().isin(favorites)
    return out


def hot_hitters(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return df
    d = df[df["G"] >= 5].copy()
    d["Heat"] = d.apply(
        lambda r: (r["OPS"] or 0) * math.log1p(r["G"]) - 0.003 * (r["SO"] or 0), axis=1
    )
    return d.sort_values("Heat", ascending=False).head(top_n)


def hot_pitchers(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return df
    d = df[(df["G"] >= 3) & (df["IP"] >= 5)].copy()
    d["Heat"] = d.apply(
        lambda r: (
            -(r["ERA"]  or 9.0) * 0.40
            -(r["WHIP"] or 2.0) * 2.00
            + (r["K/BB"] or 0)  * 0.30
            + math.log1p(r["SO"] or 0) * 0.20
        ), axis=1,
    )
    return d.sort_values("Heat", ascending=False).head(top_n)


def render_game_log(pid, pname: str, group: str) -> None:
    """Fetch and render a player's game log inside an expander."""
    if not valid_player_id(pid):
        st.warning("Player ID unavailable — cannot load game log.")
        return

    with st.expander(f"📊 {pname} — {CURRENT_YEAR} Game Log", expanded=True):
        with st.spinner("Loading game log…"):
            log = fetch_game_log(int(pid), group)

        if log.empty:
            st.info("No game log data available yet for this player.")
            return

        # ── Summary strip ──────────────────────────────────────
        if group == "hitting":
            total_ab = log["AB"].sum()
            total_h  = log["H"].sum()
            seas_avg = f"{total_h/total_ab:.3f}" if total_ab > 0 else ".000"
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Games",  len(log))
            mc2.metric("AVG",    seas_avg)
            mc3.metric("HR",     log["HR"].sum())
            mc4.metric("RBI",    log["RBI"].sum())
            mc5.metric("SB",     log["SB"].sum())

            st.dataframe(
                log, use_container_width=True, hide_index=True,
                column_config={"AVG": st.column_config.NumberColumn(format="%.3f")},
            )

            # Hits per game chart (most recent → left)
            chart_data = log[["Date", "H"]].set_index("Date").sort_index()
            if len(chart_data) > 1:
                st.caption("Hits per game (chronological)")
                st.bar_chart(chart_data, color="#FFC52F", height=160)

        else:  # pitching
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Apps",   len(log))
            mc2.metric("IP",     f"{log['IP'].sum():.1f}")
            mc3.metric("ERA",    f"{log['ERA'].iloc[0]:.2f}" if len(log) else "—")
            mc4.metric("SO",     log["SO"].sum())
            mc5.metric("BB",     log["BB"].sum())

            st.dataframe(
                log, use_container_width=True, hide_index=True,
                column_config={
                    "IP":  st.column_config.NumberColumn(format="%.1f"),
                    "ERA": st.column_config.NumberColumn(format="%.2f"),
                },
            )

            chart_data = log[["Date", "SO"]].set_index("Date").sort_index()
            if len(chart_data) > 1:
                st.caption("Strikeouts per appearance (chronological)")
                st.bar_chart(chart_data, color="#FFC52F", height=160)


# ══════════════════════════════════════════════════════════════════════════════
# Session state
# ══════════════════════════════════════════════════════════════════════════════
if "sel_hitter" not in st.session_state:
    st.session_state.sel_hitter  = None   # {"player_id": int, "name": str}
if "sel_pitcher" not in st.session_state:
    st.session_state.sel_pitcher = None


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(BREWERS_CSS, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.25rem">
  <span style="font-size:2.8rem;line-height:1">🧀</span>
  <div>
    <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.18em;
                color:rgba(255,197,47,0.55);text-transform:uppercase;margin-bottom:2px">
      Milwaukee Brewers
    </div>
    <h1 style="margin:0;padding:0">Farm System Leaderboard</h1>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:1rem 0 0.5rem">
      <div style="font-size:2.5rem">🧀</div>
      <div style="color:#FFC52F;font-weight:800;font-size:1rem;letter-spacing:-0.3px">
        Brewers Farm Tracker
      </div>
      <div style="color:rgba(255,255,255,0.35);font-size:0.7rem;margin-top:2px">
        {year} season · live data
      </div>
    </div>
    """.format(year=CURRENT_YEAR), unsafe_allow_html=True)

    st.divider()
    st.markdown("**⭐ Favorite Players**")
    favorite_text = st.text_area(
        "Pin players to top",
        placeholder="Jackson Chourio, Sal Frelick, …",
        help="Comma-separated player names. They'll float to the top of every leaderboard.",
        label_visibility="collapsed",
    )
    show_only_favorites = st.checkbox("Show favorites only")

    st.divider()
    st.markdown("**🔍 Filters**")
    min_games_h = st.slider("Min hitter games",  0, 60, 0)
    min_games_p = st.slider("Min pitcher apps",  0, 30, 0)

    st.divider()
    st.caption(
        "Data via MLB Stats API · 15-min cache  \n"
        "Active MLB roster excluded automatically"
    )

favorites = {n.strip().lower() for n in favorite_text.split(",") if n.strip()}

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading Brewers affiliate stats…"):
    hitters, pitchers, loaded_levels, failed_levels = load_all_data()

hitters  = add_favorites(hitters,  favorites)
pitchers = add_favorites(pitchers, favorites)

# ── Level filter ──────────────────────────────────────────────────────────────
all_levels = sorted(set(
    list(hitters["Level"].unique()  if not hitters.empty  else []) +
    list(pitchers["Level"].unique() if not pitchers.empty else [])
))
selected_levels = st.multiselect(
    "Levels to include", all_levels, default=all_levels,
    help="Filter the leaderboards to specific affiliate levels.",
)


def apply_filters(df: pd.DataFrame, min_g: int) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[df["Level"].isin(selected_levels)].copy()
    df = df[df["G"].fillna(0) >= min_g].copy()
    if show_only_favorites:
        df = df[df["⭐"]].copy()
    return df


hitters  = apply_filters(hitters,  min_games_h)
pitchers = apply_filters(pitchers, min_games_p)

# ── Summary metrics ───────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:1.25rem'></div>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hitters tracked",   0 if hitters.empty  else len(hitters))
c2.metric("Pitchers tracked",  0 if pitchers.empty else len(pitchers))
c3.metric("Active affiliates", len(loaded_levels))
if failed_levels:
    acl_dsl_only = all("ACL" in l or "DSL" in l for l in failed_levels)
    c4.metric("Pending levels", len(failed_levels))
    if acl_dsl_only:
        st.info(
            "**ACL & DSL rookie leagues** haven't started yet — they open in June/July. "
            "Those rosters will populate automatically once games begin."
        )
    else:
        st.warning("No data for: " + ", ".join(failed_levels))

if hitters.empty and pitchers.empty:
    st.error("No affiliate stats returned. The MLB Stats API may be unavailable — try again in a moment.")
    st.stop()

# ── Column configs ────────────────────────────────────────────────────────────
HIT_CFG = {
    "Player": st.column_config.TextColumn(width="large"),
    "Level":  st.column_config.TextColumn(width="large"),
    "Pos":    st.column_config.TextColumn("Pos",  width="small"),
    "Age":    st.column_config.NumberColumn("Age", width="small"),
    "G":      st.column_config.NumberColumn("G",   width="small"),
    "AB":     st.column_config.NumberColumn("AB",  width="small"),
    "HR":     st.column_config.NumberColumn("HR",  width="small"),
    "RBI":    st.column_config.NumberColumn("RBI", width="small"),
    "SB":     st.column_config.NumberColumn("SB",  width="small"),
    "BB":     st.column_config.NumberColumn("BB",  width="small"),
    "SO":     st.column_config.NumberColumn("SO",  width="small"),
    "AVG":    st.column_config.NumberColumn("AVG", format="%.3f", width="small"),
    "OBP":    st.column_config.NumberColumn("OBP", format="%.3f", width="small"),
    "SLG":    st.column_config.NumberColumn("SLG", format="%.3f", width="small"),
    "OPS":    st.column_config.ProgressColumn("OPS", format="%.3f", min_value=0, max_value=1.2),
    "Proj Debut": st.column_config.TextColumn("Proj Debut", width="small"),
    "⭐":     st.column_config.CheckboxColumn(label="Fav", width="small"),
}
PIT_CFG = {
    "Player": st.column_config.TextColumn(width="large"),
    "Level":  st.column_config.TextColumn(width="large"),
    "Pos":    st.column_config.TextColumn("Pos",  width="small"),
    "Age":    st.column_config.NumberColumn("Age", width="small"),
    "G":      st.column_config.NumberColumn("G",   width="small"),
    "GS":     st.column_config.NumberColumn("GS",  width="small"),
    "W":      st.column_config.NumberColumn("W",   width="small"),
    "L":      st.column_config.NumberColumn("L",   width="small"),
    "SV":     st.column_config.NumberColumn("SV",  width="small"),
    "HLD":    st.column_config.NumberColumn("HLD", width="small"),
    "SO":     st.column_config.NumberColumn("SO",  width="small"),
    "BB":     st.column_config.NumberColumn("BB",  width="small"),
    "IP":     st.column_config.NumberColumn("IP",  format="%.1f", width="small"),
    "ERA":    st.column_config.NumberColumn("ERA", format="%.2f", width="small"),
    "WHIP":   st.column_config.NumberColumn("WHIP",format="%.2f", width="small"),
    "K/BB":   st.column_config.NumberColumn("K/BB",format="%.2f", width="small"),
    "Proj Debut": st.column_config.TextColumn("Proj Debut", width="small"),
    "⭐":     st.column_config.CheckboxColumn(label="Fav", width="small"),
}

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_h, tab_p, tab_hot, tab_debut = st.tabs(
    ["🏏  Hitters", "⚾  Pitchers", "🔥  Who's Hot", "📅  Proj. Debuts"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Hitters tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_h:
    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 3])
    sort_h    = ctrl1.selectbox("Sort by", ["OPS","HR","RBI","AVG","OBP","SLG","SB","BB","SO"], key="sort_h")
    pos_opts  = sorted(hitters["Pos"].dropna().unique()) if not hitters.empty else []
    pos_filt  = ctrl2.multiselect("Position", pos_opts, key="pos_h")
    search_h  = ctrl3.text_input("🔎 Search player", key="search_h", placeholder="e.g. Chourio")

    view = hitters.copy()
    if pos_filt:
        view = view[view["Pos"].isin(pos_filt)]
    if search_h:
        view = view[view["Player"].str.contains(search_h, case=False, na=False)]

    if not view.empty:
        view = view.sort_values(["⭐", sort_h, "Player"], ascending=[False, False, True]).reset_index(drop=True)
        cols = [c for c in HITTING_DISPLAY + ["⭐"] if c in view.columns]

        st.caption("Click any row to view that player's game-by-game log.")
        event = st.dataframe(
            view[cols],
            use_container_width=True,
            hide_index=True,
            column_config=HIT_CFG,
            on_select="rerun",
            selection_mode="single-row",
            key="hitter_table",
        )
        sel = event.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            st.session_state.sel_hitter = {"player_id": row.get("player_id"), "name": row["Player"]}

        if st.session_state.sel_hitter:
            info = st.session_state.sel_hitter
            render_game_log(info["player_id"], info["name"], "hitting")
    else:
        st.info("No hitters match the current filters.")

# ══════════════════════════════════════════════════════════════════════════════
# Pitchers tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_p:
    ctrl1, ctrl2 = st.columns([2, 3])
    sort_p   = ctrl1.selectbox("Sort by", ["ERA","WHIP","SO","K/BB","SV","IP","W"], key="sort_p")
    search_p = ctrl2.text_input("🔎 Search player", key="search_p", placeholder="e.g. Hendrick")
    asc_p    = sort_p in {"ERA", "WHIP"}

    view = pitchers.copy()
    if search_p:
        view = view[view["Player"].str.contains(search_p, case=False, na=False)]

    if not view.empty:
        view = view.sort_values(["⭐", sort_p, "Player"], ascending=[False, asc_p, True]).reset_index(drop=True)
        cols = [c for c in PITCHING_DISPLAY + ["⭐"] if c in view.columns]

        st.caption("Click any row to view that player's game-by-game log.")
        event = st.dataframe(
            view[cols],
            use_container_width=True,
            hide_index=True,
            column_config=PIT_CFG,
            on_select="rerun",
            selection_mode="single-row",
            key="pitcher_table",
        )
        sel = event.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            st.session_state.sel_pitcher = {"player_id": row.get("player_id"), "name": row["Player"]}

        if st.session_state.sel_pitcher:
            info = st.session_state.sel_pitcher
            render_game_log(info["player_id"], info["name"], "pitching")
    else:
        st.info("No pitchers match the current filters.")

# ══════════════════════════════════════════════════════════════════════════════
# Who's Hot tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_hot:
    st.info(
        "**How the Heat Index works** — this ranks players by season-to-date performance, "
        "not just recent games (the leaderboard API returns cumulative stats only). "
        "**Hitters:** `OPS × log(G+1) − 0.003 × SO` — rewards high on-base + power, "
        "weights for sample size, penalises strikeouts. "
        "**Pitchers:** `−ERA×0.4 − WHIP×2 + K/BB×0.3 + log(SO+1)×0.2` — "
        "lower ERA/WHIP and higher strikeout rate push the score up. "
        "Minimums: 5 G (hitters), 3 G + 5 IP (pitchers).",
        icon="ℹ️",
    )
    hh = hot_hitters(hitters)
    hp = hot_pitchers(pitchers)

    ch, cp = st.columns(2)
    with ch:
        st.markdown("#### 🔥 Hottest Hitters")
        if not hh.empty:
            display_cols = [c for c in ["Player","Level","Pos","G","OPS","HR","RBI","SB"] if c in hh.columns]
            st.dataframe(
                hh[display_cols].reset_index(drop=True),
                use_container_width=True, hide_index=True,
                column_config={
                    "OPS": st.column_config.ProgressColumn("OPS", format="%.3f", min_value=0, max_value=1.2),
                },
            )
        else:
            st.info("Not enough games played yet.")

    with cp:
        st.markdown("#### 🔥 Hottest Pitchers")
        if not hp.empty:
            display_cols = [c for c in ["Player","Level","Pos","G","ERA","WHIP","SO","K/BB"] if c in hp.columns]
            st.dataframe(
                hp[display_cols].reset_index(drop=True),
                use_container_width=True, hide_index=True,
                column_config={
                    "ERA":  st.column_config.NumberColumn(format="%.2f"),
                    "WHIP": st.column_config.NumberColumn(format="%.2f"),
                    "K/BB": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        else:
            st.info("Not enough games played yet.")

# ══════════════════════════════════════════════════════════════════════════════
# Projected Debuts tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_debut:
    st.caption(
        "Estimates only — derived from current affiliate level, age, and performance. "
        "Not a scout forecast. Formula: level baseline adjusted for age (older = faster) "
        "and elite stats (up to +6 months acceleration)."
    )

    frames = []
    if not hitters.empty:
        frames.append(
            hitters[["Player","Level","Pos","Age","OPS","Proj Debut","⭐"]].assign(Type="Hitter")
        )
    if not pitchers.empty:
        frames.append(
            pitchers[["Player","Level","Pos","Age","ERA","Proj Debut","⭐"]].assign(Type="Pitcher")
        )

    if frames:
        all_players = pd.concat(frames, ignore_index=True)
        all_players["Proj Debut Year"] = pd.to_numeric(
            all_players["Proj Debut"].replace("Unknown", pd.NA), errors="coerce"
        )
        all_players = all_players.sort_values(
            ["⭐", "Proj Debut Year", "Player"], ascending=[False, True, True]
        ).reset_index(drop=True)

        cols = [c for c in ["Player","Type","Level","Pos","Age","Proj Debut","⭐"] if c in all_players.columns]
        st.dataframe(
            all_players[cols], use_container_width=True, hide_index=True,
            column_config={"⭐": st.column_config.CheckboxColumn(label="Fav", width="small")},
        )

        by_year = (
            all_players.dropna(subset=["Proj Debut Year"])
            .groupby("Proj Debut Year").size()
            .reset_index(name="Prospects")
        )
        if not by_year.empty:
            st.markdown("#### Pipeline by Projected Debut Year")
            st.bar_chart(by_year.set_index("Proj Debut Year"), color="#FFC52F", height=220)
    else:
        st.info("No data available.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Milwaukee Brewers Farm System Leaderboard · {CURRENT_YEAR} season · "
    "Data: MLB Stats API (statsapi.mlb.com) · Refreshed every 15 min · "
    "Active MLB roster excluded · Projected debuts are estimates, not scout forecasts."
)
